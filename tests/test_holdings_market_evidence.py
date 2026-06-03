"""POC2 — Holdings × Market Discovery Evidence 1차 builder 단위 테스트 (2026-06-03).

지시문 §5 / AC-1~7. 외부 fetch 0건. SQLite + cache read only.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app import etf_constituents_store, etf_nav_store, market_data_store
from app.etf_constituents_store import ConstituentRow, upsert_constituents
from app.etf_nav_store import NavDailyRow, upsert_nav_rows
from app.holdings import Holding
from app.holdings_market_evidence import build_holdings_market_evidence
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn

# ─── helpers ──────────────────────────────────────────────────────


@pytest.fixture
def market_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """market_data.sqlite 경로 격리. constituents / NAV store 도 같은 파일을 사용."""
    fake_db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr(market_data_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_constituents_store, "DEFAULT_DB_PATH", fake_db)
    monkeypatch.setattr(etf_nav_store, "DEFAULT_DB_PATH", fake_db)
    return fake_db


def _seed_kodex200_history(db: Path, end: date, length: int = 25) -> None:
    """KODEX200 (069500) + 5/10/20거래일 흐름 가능한 시계열."""
    rows: list[EtfDailyPriceRow] = []
    base = 100.0
    for i in range(length):
        d = (end - timedelta(days=length - i - 1)).isoformat()
        close = base + i * 0.5
        rows.append(EtfDailyPriceRow("069500", d, close, close, close, close, 0, 0))
    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1000, 5000.0)],
        source="TestSource",
        db_path=db,
    )
    upsert_daily_prices(rows, source="TestSource", db_path=db)


def _seed_etf_history(
    db: Path,
    ticker: str,
    name: str,
    end: date,
    closes: list[float],
) -> None:
    upsert_etf_master(
        [EtfMasterRow(ticker, name, "1", 100.0, 1000, 5000.0)],
        source="TestSource",
        db_path=db,
    )
    rows: list[EtfDailyPriceRow] = []
    for i, close in enumerate(closes):
        d = (end - timedelta(days=len(closes) - i - 1)).isoformat()
        rows.append(EtfDailyPriceRow(ticker, d, close, close, close, close, 0, 0))
    upsert_daily_prices(rows, source="TestSource", db_path=db)


def _holding(ticker: str, name: str = "") -> Holding:
    return Holding(
        ticker=ticker,
        quantity=10.0,
        avg_buy_price=10000.0,
        name=name or None,
        account_group="일반",
    )


# ─── tests ────────────────────────────────────────────────────────


def test_empty_holdings_returns_empty_response(market_db: Path) -> None:
    """빈 holdings → status=ok + 빈 리스트 + summary 0 (지시문 §4.1)."""
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=[],
        topn_payload=topn,
        db_path=market_db,
    )
    assert out["status"] == "ok"
    assert out["holdings"] == []
    assert out["summary"]["total_holdings_count"] == 0
    assert out["summary"]["matched_topn_count"] == 0


def test_holding_matched_to_topn_candidate(market_db: Path) -> None:
    """보유 ETF 가 현재 Market Discovery 후보 → matched_topn_candidate."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    _seed_etf_history(
        market_db,
        "100001",
        "Strong ETF",
        end,
        [100.0 + i * 1.0 for i in range(25)],
    )
    holdings = [_holding("100001", "Strong ETF")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    item = out["holdings"][0]
    assert item["topn_match"]["status"] == "matched_topn_candidate"
    assert item["topn_match"]["rank"] is not None
    assert out["summary"]["matched_topn_count"] == 1
    assert out["summary"]["not_in_current_topn_count"] == 0


def test_holding_not_in_current_topn(market_db: Path) -> None:
    """보유 ETF 가 후보 목록에 없으면 not_in_current_topn (지시문 §5.5)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    _seed_etf_history(
        market_db, "100002", "TopN ETF", end, [100.0 + i * 1.0 for i in range(25)]
    )
    holdings = [_holding("999999", "Not in universe")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    item = out["holdings"][0]
    assert item["topn_match"]["status"] == "not_in_current_topn"
    assert item["topn_match"]["rank"] is None
    assert out["summary"]["not_in_current_topn_count"] == 1


def test_holding_topn_unavailable_when_market_data_missing(market_db: Path) -> None:
    """market 데이터 없음 → topn unavailable + returns unavailable (지시문 §5.6)."""
    holdings = [_holding("100003")]
    topn = compute_topn(n=5, db_path=market_db)  # status=missing
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    item = out["holdings"][0]
    assert item["topn_match"]["status"] == "unavailable"
    assert item["returns"]["status"] == "unavailable"
    assert item["returns"]["one_month_return_pct"] is None
    assert item["excess_return"]["status"] == "unavailable"
    assert "market_topn status=missing" in out["warnings"]


def test_nav_discount_unavailable_when_no_cache(market_db: Path) -> None:
    """NAV cache 비어있음 → status=unavailable + source=not_integrated (지시문 §5.9)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    holdings = [_holding("069500", "KODEX 200")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    nav = out["holdings"][0]["nav_discount"]
    assert nav["status"] == "unavailable"
    assert nav["source"] == "not_integrated"
    assert nav["nav"] is None


def test_nav_discount_uses_existing_store_row(market_db: Path) -> None:
    """NAV cache 에 row 있으면 그 값 그대로 사용 (외부 fetch X)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker="069500",
                asof=end.isoformat(),
                nav=10000.0,
                market_price=10050.0,
                discount_rate_pct=0.5,
                source="test_source",
                status="ok",
                message=None,
            )
        ],
        db_path=market_db,
    )
    holdings = [_holding("069500", "KODEX 200")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    nav = out["holdings"][0]["nav_discount"]
    assert nav["status"] == "ok"
    assert nav["nav"] == 10000.0
    assert nav["market_price"] == 10050.0


def test_constituents_unavailable_when_no_cache(market_db: Path) -> None:
    """보유 ETF 구성종목 cache 비어있음 → constituents_unavailable (지시문 §5.7 / §5.8)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    _seed_etf_history(market_db, "100004", "TopN", end, [100.0 + i for i in range(25)])
    holdings = [_holding("100004", "TopN")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    overlap = out["holdings"][0]["constituents_overlap"]
    # 후보의 cache 도 없으므로 market_core_unavailable 가 1차.
    assert overlap["status"] in {"market_core_unavailable", "constituents_unavailable"}
    assert overlap["overlap_with_market_core"] == []


def test_constituents_overlap_when_cache_present(market_db: Path) -> None:
    """후보와 보유 ETF 양쪽의 구성종목 cache 가 있으면 overlap_with_market_core 채움."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    # 두 후보 ETF 가 같은 종목을 핵심으로 함 → repeated_core 후보가 됨.
    for tk, name, closes in [
        ("100100", "ETF A", [100.0 + i * 0.8 for i in range(25)]),
        ("100101", "ETF B", [100.0 + i * 0.7 for i in range(25)]),
    ]:
        _seed_etf_history(market_db, tk, name, end, closes)
    constituents_asof = end.isoformat()
    for tk in ["100100", "100101"]:
        upsert_constituents(
            [
                ConstituentRow(
                    etf_ticker=tk,
                    asof=constituents_asof,
                    source="test_source",
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=20.0,
                    etf_name=None,
                )
            ],
            db_path=market_db,
        )
    # 보유 ETF 도 같은 핵심 종목.
    upsert_constituents(
        [
            ConstituentRow(
                etf_ticker="100100",
                asof=constituents_asof,
                source="test_source",
                rank=1,
                constituent_ticker="005930",
                constituent_name="삼성전자",
                weight_pct=20.0,
                etf_name=None,
            )
        ],
        db_path=market_db,
    )
    holdings = [_holding("100100", "ETF A")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    overlap = out["holdings"][0]["constituents_overlap"]
    assert overlap["status"] == "ok"
    assert len(overlap["overlap_with_market_core"]) >= 1
    first = overlap["overlap_with_market_core"][0]
    assert first["ticker"] == "005930"
    assert first["market_core_count"] >= 2


def test_returns_excess_taken_from_candidate(market_db: Path) -> None:
    """matched candidate 의 returns / excess_return 을 그대로 옮긴다 (지시문 §5.6)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end, length=100)
    _seed_etf_history(
        market_db, "100200", "Strong", end, [100.0 + i * 1.0 for i in range(100)]
    )
    holdings = [_holding("100200", "Strong")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    item = out["holdings"][0]
    # 1m / 3m 모두 수익률 산출 가능한 시드 → ok / partial 중 하나, unavailable 아님.
    assert item["returns"]["status"] in {"ok", "partial"}
    assert (
        item["returns"]["one_month_return_pct"] is not None
        or item["returns"]["three_month_return_pct"] is not None
    )


def test_evidence_notes_no_buy_sell_language(market_db: Path) -> None:
    """evidence_notes 에 매수/매도/교체 어휘가 들어가면 실패 (지시문 §5.10)."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    holdings = [_holding("999999", "Outside")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    forbidden = ["매수", "매도", "교체", "진입", "탈락", "비중 확대", "비중 축소"]
    notes = " ".join(out["holdings"][0]["evidence_notes"])
    for word in forbidden:
        assert (
            word not in notes
        ), f"evidence_notes 에 '{word}' 어휘 포함 — 금지 (지시문 §5.10)"


def test_no_external_fetch_triggered(market_db: Path, monkeypatch) -> None:
    """builder 가 외부 source 를 호출하지 않는다 (지시문 §5.1 / §6)."""
    from app import etf_constituents_fetcher, market_data_fdr, market_naver

    def boom(*args, **kwargs):
        raise AssertionError("외부 fetch 호출 — read-only 위반")

    monkeypatch.setattr(market_data_fdr, "refresh_etf_universe", boom)
    monkeypatch.setattr(market_data_fdr, "refresh_price_history", boom)
    monkeypatch.setattr(market_naver, "fetch_many", boom)
    monkeypatch.setattr(
        etf_constituents_fetcher, "fetch_constituents", boom, raising=False
    )
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    holdings = [_holding("069500", "KODEX 200")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    assert out["status"] == "ok"
