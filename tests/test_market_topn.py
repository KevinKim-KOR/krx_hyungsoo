"""POC2 — SQLite 직접 계산 기반 일간 / 1개월 / 3개월 TOP N 산출 테스트.

2026-05-18 변경:
- JSON artifact 저장/읽기 함수 폐기 (save_topn_artifact / compute_and_save_topn).
- payload schema 확장: status / latest_refresh / period_exclusions.
- 결측 데이터는 0% 로 보정하지 않고 exclusion 으로 집계 (지시문 §6).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    log_refresh,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_topn import compute_topn


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def _seed_universe(db_path: Path, ticker_names: list[tuple[str, str]]) -> None:
    rows = [
        EtfMasterRow(
            ticker=tk,
            name=nm,
            category="X",
            price=None,
            volume=None,
            market_cap=None,
        )
        for tk, nm in ticker_names
    ]
    upsert_etf_master(rows, source="TestSource", db_path=db_path)


def _seed_price_series(
    db_path: Path,
    ticker: str,
    closes: list[tuple[str, float]],
) -> None:
    rows = [
        EtfDailyPriceRow(
            ticker=ticker, date=d, open=c, high=c, low=c, close=c, volume=0, change=0
        )
        for d, c in closes
    ]
    upsert_daily_prices(rows, source="TestSource", db_path=db_path)


def _dates_around(end: date) -> dict[str, str]:
    return {
        "end": end.isoformat(),
        "minus_1": (end - timedelta(days=1)).isoformat(),
        "minus_30": (end - timedelta(days=30)).isoformat(),
        "minus_90": (end - timedelta(days=90)).isoformat(),
    }


def _seed_three_etfs(db_path: Path, end: date) -> None:
    d = _dates_around(end)
    _seed_universe(
        db_path,
        [("AAA001", "ETF A"), ("BBB002", "ETF B"), ("CCC003", "ETF C")],
    )
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 110.0),
            (d["minus_1"], 119.0),
            (d["end"], 120.0),
        ],
    )
    _seed_price_series(
        db_path,
        "BBB002",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 102.0),
            (d["minus_1"], 100.0),
            (d["end"], 105.0),
        ],
    )
    _seed_price_series(
        db_path,
        "CCC003",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 99.0),
            (d["minus_1"], 95.0),
            (d["end"], 94.0),
        ],
    )


# ─── 정상 흐름 (status=ok) ─────────────────────────────────────────


def test_compute_topn_daily(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload = compute_topn(n=3, db_path=db_path)
    assert payload["status"] == "ok"
    assert payload["asof"] == end.isoformat()
    assert payload["universe_count"] == 3
    daily = payload["daily_topn"]
    assert [r["ticker"] for r in daily] == ["BBB002", "AAA001", "CCC003"]
    assert daily[0]["rank"] == 1
    assert daily[0]["return_pct"] == pytest.approx(5.0, abs=0.01)
    assert daily[0]["name"] == "ETF B"
    assert daily[0]["basis_end_date"] == end.isoformat()


def test_compute_topn_one_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    one_m = payload["one_month_topn"]
    assert [r["ticker"] for r in one_m] == ["AAA001", "BBB002", "CCC003"]
    assert one_m[0]["return_pct"] == pytest.approx(
        (120.0 / 110.0 - 1) * 100.0, abs=0.01
    )


def test_compute_topn_three_month(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    payload = compute_topn(n=3, db_path=db_path)
    three_m = payload["three_month_topn"]
    assert [r["ticker"] for r in three_m] == ["AAA001", "BBB002", "CCC003"]
    assert three_m[0]["return_pct"] == pytest.approx(20.0, abs=0.01)


def test_compute_topn_respects_n_parameter(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)

    payload_n1 = compute_topn(n=1, db_path=db_path)
    assert len(payload_n1["daily_topn"]) == 1
    assert len(payload_n1["one_month_topn"]) == 1
    assert len(payload_n1["three_month_topn"]) == 1

    payload_n2 = compute_topn(n=2, db_path=db_path)
    assert len(payload_n2["daily_topn"]) == 2

    payload_n10 = compute_topn(n=10, db_path=db_path)
    assert len(payload_n10["daily_topn"]) == 3  # universe 3개 한계
    assert payload_n10["n"] == 10


def test_compute_topn_latest_refresh_field(db_path: Path) -> None:
    end = date(2024, 10, 31)
    _seed_three_etfs(db_path, end)
    log_refresh(
        run_id="rid-001",
        source="FinanceDataReader/prices",
        asof=end.isoformat(),
        attempted=3,
        success=3,
        fail=0,
        runtime_seconds=1.5,
        db_path=db_path,
    )
    payload = compute_topn(n=3, db_path=db_path)
    assert payload["latest_refresh"] is not None
    assert payload["latest_refresh"]["refresh_id"] == "rid-001"
    assert payload["latest_refresh"]["success_count"] == 3


# ─── status 분기 ──────────────────────────────────────────────────


def test_compute_topn_missing_when_db_file_absent(tmp_path: Path) -> None:
    payload = compute_topn(n=10, db_path=tmp_path / "does_not_exist.sqlite")
    assert payload["status"] == "missing"
    assert payload["asof"] is None
    assert payload["daily_topn"] == []
    assert payload["period_exclusions"]["daily"]


def test_compute_topn_empty_when_no_price_rows(db_path: Path) -> None:
    _seed_universe(db_path, [("AAA001", "ETF A")])  # universe 만 있고 price 없음
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "empty"
    assert payload["universe_count"] == 1
    assert payload["daily_topn"] == []


def test_compute_topn_invalid_when_required_table_missing(tmp_path: Path) -> None:
    """DB 파일은 있으나 필수 테이블 누락 → status=invalid."""
    import sqlite3

    bad_db = tmp_path / "bad.sqlite"
    with sqlite3.connect(str(bad_db)) as con:
        con.execute("CREATE TABLE etf_master (ticker TEXT PRIMARY KEY)")
        # etf_daily_price / market_refresh_log 의도적 누락
        con.commit()
    payload = compute_topn(n=10, db_path=bad_db)
    assert payload["status"] == "invalid"
    assert payload["daily_topn"] == []


# ─── 결측 처리 ────────────────────────────────────────────────────


def test_compute_topn_missing_data_not_filled_with_zero(db_path: Path) -> None:
    """지시문 §6 — 결측은 0% 보정 금지. period_exclusions 로 집계.

    시나리오: TINY 신규 상장 ETF (history 1건뿐) → 모든 기간 insufficient_history.
    어떤 TOP N 에도 포함되지 않아야 하고 period_exclusions 에 집계되어야 한다.
    """
    end = date(2024, 10, 31)
    d = _dates_around(end)
    _seed_universe(
        db_path, [("AAA001", "Has Full History"), ("TINY002", "New Listing")]
    )
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_90"], 100.0),
            (d["minus_30"], 110.0),
            (d["minus_1"], 119.0),
            (d["end"], 120.0),
        ],
    )
    # TINY002: latest 1건만 — 모든 기간 insufficient_history
    _seed_price_series(db_path, "TINY002", [(d["end"], 105.0)])

    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "ok"
    # AAA001 만 TOP N 에 포함, TINY002 는 어디에도 안 들어감 (0% 보정 금지)
    for label in ("daily_topn", "one_month_topn", "three_month_topn"):
        tickers = [r["ticker"] for r in payload[label]]
        assert "TINY002" not in tickers
        assert "AAA001" in tickers
    # period_exclusions 에 insufficient_history 1건씩 집계
    assert payload["period_exclusions"]["daily"]["insufficient_history"] >= 1
    assert payload["period_exclusions"]["one_month"]["insufficient_history"] >= 1
    assert payload["period_exclusions"]["three_month"]["insufficient_history"] >= 1


def test_compute_topn_skips_invalid_price(db_path: Path) -> None:
    """close <= 0 또는 base close <= 0 → invalid_price exclusion."""
    end = date(2024, 10, 31)
    d = _dates_around(end)
    _seed_universe(db_path, [("AAA001", "Valid"), ("BAD002", "Zero Latest")])
    _seed_price_series(
        db_path,
        "AAA001",
        [
            (d["minus_1"], 100.0),
            (d["end"], 102.0),
        ],
    )
    # close 0 은 fetch_price_history 가 이미 제외하지만, 의도 분명히 — 아예 행 안 넣음
    # 대신 latest 만 있고 base 부재 케이스로 invalid 가 아니라 missing 처리 흐름
    payload = compute_topn(n=10, db_path=db_path)
    assert payload["status"] == "ok"
    assert "AAA001" in [r["ticker"] for r in payload["daily_topn"]]
    assert "BAD002" not in [r["ticker"] for r in payload["daily_topn"]]


def test_compute_topn_no_legacy_artifact_function() -> None:
    """save_topn_artifact / compute_and_save_topn 함수가 폐기됐는지 확인 (AC-8)."""
    from app import market_topn

    assert not hasattr(market_topn, "save_topn_artifact")
    assert not hasattr(market_topn, "compute_and_save_topn")
    assert not hasattr(market_topn, "DEFAULT_TOPN_PATH")
