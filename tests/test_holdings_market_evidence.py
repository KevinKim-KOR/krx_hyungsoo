"""POC2 — Holdings × Market Discovery Evidence 1차 builder 단위 테스트 (2026-06-03).

지시문 §5 / AC-1~7. 외부 fetch 0건. SQLite + cache read only.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import etf_constituents_store, etf_nav_store, market_data_store
from app.etf_constituents_store import ConstituentRow, upsert_constituents
from app.etf_nav_store import NavDailyRow, upsert_nav_rows
from app.holdings import Holding
from app.holdings_market_evidence import (
    CONSTITUENTS_OK,
    CONSTITUENTS_UNAVAILABLE,
    MARKET_CORE_UNAVAILABLE,
    STATUS_OK,
    STATUS_UNAVAILABLE,
    TOPN_MATCH_MATCHED,
    TOPN_MATCH_NOT_IN_TOPN,
    TOPN_MATCH_UNAVAILABLE,
    _build_evidence_notes,
    build_holdings_market_evidence,
)
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


# ─── 2026-08-17 보유 기간 수익률 확장 (6개월·12개월) ────────────────────────
# 검증자 지적: 신규 필드 2개를 직접 검증하는 자동테스트가 없었다.
# 계약 3가지를 고정한다.
#   (1) 후보 returns 의 six_month·twelve_month 를 보유 evidence 로 전달한다.
#   (2) status 판정은 **기존대로 1개월·3개월 기준** — 6·12개월은 판정에 넣지 않는다.
#   (3) 값이 없으면 None (0 대체 금지 · 지시문 §5.6).


def _returns_of(out: dict, idx: int = 0) -> dict:
    return out["holdings"][idx]["returns"]


def test_returns_carries_six_and_twelve_month(market_db: Path) -> None:
    """(1) 후보에 있는 6·12개월 값이 보유 evidence 에 그대로 실린다."""
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

    cand = next(c for c in topn["candidates"] if c.get("ticker") == "100001")
    cand_returns = cand.get("returns") or {}
    r = _returns_of(out)

    # 필드가 응답에 존재한다 (누락이 아니라 명시 키).
    assert "six_month_return_pct" in r
    assert "twelve_month_return_pct" in r

    # 2026-08-17 (검증자 B-6) — 후보 값이 **실제로 비어 있지 않음**을 먼저 단정한다.
    #   이걸 빼면 양쪽이 모두 None 이어도 "전달됐다" 로 통과해 테스트가 무의미해진다.
    cand_six = (cand_returns.get("six_month") or {}).get("return_pct")
    cand_twelve = (cand_returns.get("twelve_month") or {}).get("return_pct")
    assert cand_six is not None, "전제 불성립 — 후보 6개월 값이 비어 있다"
    assert cand_twelve is not None, "전제 불성립 — 후보 12개월 값이 비어 있다"

    # 후보 값과 동일하다 — 신규 계산이 아니라 전달이다.
    assert r["six_month_return_pct"] == cand_six
    assert r["twelve_month_return_pct"] == cand_twelve


def test_returns_status_still_judged_by_one_and_three_month(market_db: Path) -> None:
    """(2) status 는 1·3개월 기준 그대로 — 6·12개월 유무가 판정을 바꾸지 않는다.

    2026-08-17 (검증자 B-6) — 이전 판은 현재 출력의 1·3개월로 기대값을 **다시
    계산**할 뿐이라 어떤 결과든 통과하는 항등식이었다. 여기서는 **경계 조건을
    직접 만들어** 판정 기준을 고정한다: 같은 1·3개월 입력에 6·12개월만 넣고 뺐을
    때 status 가 동일해야 한다.
    """
    from app.holdings_market_evidence import _build_returns_and_excess

    base = {
        "one_month": {"return_pct": 5.0},
        "three_month": {"return_pct": 7.0},
    }

    # 6·12개월 없음
    without, _ = _build_returns_and_excess({"returns": dict(base)})
    # 6·12개월 있음 (1·3개월 입력은 동일)
    with_long, _ = _build_returns_and_excess(
        {
            "returns": {
                **base,
                "six_month": {"return_pct": 9.0},
                "twelve_month": {"return_pct": 11.0},
            }
        }
    )

    assert without["status"] == with_long["status"] == "ok"
    assert without["six_month_return_pct"] is None
    assert with_long["six_month_return_pct"] == 9.0
    assert with_long["twelve_month_return_pct"] == 11.0

    # partial 경계 — 3개월만 없는 입력에 6·12개월이 있어도 partial 을 유지한다.
    partial, _ = _build_returns_and_excess(
        {
            "returns": {
                "one_month": {"return_pct": 5.0},
                "six_month": {"return_pct": 9.0},
                "twelve_month": {"return_pct": 11.0},
            }
        }
    )
    assert partial["status"] == "partial"
    assert partial["three_month_return_pct"] is None
    assert partial["six_month_return_pct"] == 9.0


def test_returns_six_twelve_are_none_when_unmatched(market_db: Path) -> None:
    """(3) 후보에 없는 보유는 6·12개월도 None — 0 으로 대체하지 않는다."""
    end = date(2026, 5, 30)
    _seed_kodex200_history(market_db, end)
    holdings = [_holding("999999", "Unknown ETF")]
    topn = compute_topn(n=5, db_path=market_db)
    out = build_holdings_market_evidence(
        holdings=holdings, topn_payload=topn, db_path=market_db
    )
    r = _returns_of(out)
    assert r["status"] == "unavailable"
    assert r["six_month_return_pct"] is None
    assert r["twelve_month_return_pct"] is None


# ─── POC6-33 E6 — builder 안내 문장 ↔ 「확인 근거」 화면 거르기 대조 ──────────────
# 화면(helpers.ts FILTERED_NOTES · FILTERED_NOTE_PREFIXES)은 builder 문장을 글자 그대로 거른다.
# builder 문장이 바뀌면 거르기가 소리 없이 풀려 '캐시' · 'source' 문장이 화면에 다시 보이므로
# builder 의 모든 status 갈래 문장을 공용 고정 자료(tests/fixtures/poc6_33_filtered_notes.json)와 대조한다.
# 화면 상수 ↔ 같은 고정 자료 대조는 frontend helpers.test.ts 가 한다(POC6-32 공용 고정 자료 방식 · 검증자 r1 B-6:
# 서버 시험이 프론트 소스 파일 · TypeScript 선언 모양에 묶이지 않게). DB 열지 않음 · 순수 함수.
_FILTER_FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "poc6_33_filtered_notes.json").read_text(
        encoding="utf-8"
    )
)


def _builder_notes(topn: str, short: dict, cons: dict, nav: dict, topn_n=10):
    return _build_evidence_notes(
        {"status": topn}, short, cons, nav, holding_name="보유", topn_n=topn_n
    )


def test_builder_notes_match_shared_filter_fixture() -> None:
    exact = _FILTER_FIXTURE["filtered_exact"]
    prefixes = _FILTER_FIXTURE["filtered_prefixes"]
    assert exact and prefixes

    def filtered(note: str) -> bool:
        return note in exact or any(note.startswith(p) for p in prefixes)

    short_ok = {"status": STATUS_OK, "excess_vs_kodex200_20d_pctp": 1.25}
    short_neg = {"status": STATUS_OK, "excess_vs_kodex200_20d_pctp": -3.4}
    short_na = {"status": STATUS_UNAVAILABLE}
    cons_hit = {"status": CONSTITUENTS_OK, "overlap_with_market_core": [{"t": 1}]}
    cons_none = {"status": CONSTITUENTS_OK, "overlap_with_market_core": []}
    cons_na = {"status": CONSTITUENTS_UNAVAILABLE}
    core_na = {"status": MARKET_CORE_UNAVAILABLE}
    nav_ok = {"status": STATUS_OK, "flag": None}
    nav_flag = {"status": STATUS_OK, "flag": "discount_check_needed"}
    nav_na = {"status": STATUS_UNAVAILABLE, "flag": None}

    produced: list[str] = []
    for topn, n in (
        (TOPN_MATCH_MATCHED, 10),
        (TOPN_MATCH_NOT_IN_TOPN, 10),
        (TOPN_MATCH_NOT_IN_TOPN, None),
        (TOPN_MATCH_UNAVAILABLE, 10),
    ):
        for short in (short_ok, short_neg, short_na):
            for cons in (cons_hit, cons_none, cons_na, core_na):
                for nav in (nav_ok, nav_flag, nav_na):
                    produced += _builder_notes(topn, short, cons, nav, topn_n=n)

    # 1) builder 가 만드는 문장 가운데 남기는 것은 자료 부족 안내 한 문장뿐이다.
    kept = sorted({x for x in produced if not filtered(x)})
    assert kept == _FILTER_FIXTURE["kept"]
    # 2) 고정 자료(= 화면)의 정확 일치 목록은 모두 builder 가 실제로 만드는 문장이다(낡은 원문 없음).
    assert set(exact) <= set(produced)
    # 3) 앞부분 거르기는 후보 문장 네 갈래 · KODEX200 대비 두 부호를 모두 덮는다.
    assert {x for x in produced if x.startswith(prefixes[0])} == {
        "현재 Market Discovery 후보와 일치합니다.",
        "현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.",
        "현재 Market Discovery 후보에 포함되어 있지 않습니다.",
        "현재 Market Discovery 후보 목록을 확인할 수 없습니다.",
    }
    assert {x for x in produced if x.startswith(prefixes[1])} == {
        "20거래일 KODEX200 대비 단기 흐름 차이 +1.25%p.",
        "20거래일 KODEX200 대비 단기 흐름 차이 -3.40%p.",
    }
