"""POC2 — B 방향 PC 작업 1~2단계 SQLite 시장 데이터 저장소 테스트.

DDL 생성 / upsert / log / decision_evidence 미존재 가드.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    latest_refresh_log,
    list_etf_tickers,
    log_refresh,
    fetch_price_history,
    table_exists,
    upsert_daily_prices,
    upsert_etf_master,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "market_data.sqlite"


def test_init_db_creates_expected_tables_only(db_path: Path) -> None:
    init_db(db_path)
    assert table_exists("etf_master", db_path)
    assert table_exists("etf_daily_price", db_path)
    assert table_exists("market_refresh_log", db_path)
    # D-2 (2026-06-30) — market_refresh_state SQLite SSOT 영속화 테이블 추가.
    assert table_exists("market_refresh_state", db_path)

    # decision_evidence 테이블은 본 STEP 에서 생성 금지.
    assert not table_exists("decision_evidence", db_path)

    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        names = sorted(row[0] for row in cur.fetchall())
    assert names == [
        "etf_daily_price",
        "etf_master",
        "market_refresh_log",
        "market_refresh_state",
    ]


def test_upsert_etf_master_replaces_same_ticker(db_path: Path) -> None:
    rows1 = [
        EtfMasterRow(
            ticker="069500",
            name="KODEX 200",
            category="1",
            price=100.0,
            volume=1000,
            market_cap=5000.0,
        ),
        EtfMasterRow(
            ticker="379800",
            name="KODEX 미국S&P500",
            category="4",
            price=200.0,
            volume=2000,
            market_cap=6000.0,
        ),
    ]
    n1 = upsert_etf_master(rows1, source="TestSource", db_path=db_path)
    assert n1 == 2
    assert list_etf_tickers(db_path) == ["069500", "379800"]

    # 같은 ticker 재upsert — name/price 갱신, row 수는 그대로 2개
    rows2 = [
        EtfMasterRow(
            ticker="069500",
            name="KODEX 200 (rev)",
            category="1",
            price=110.0,
            volume=1500,
            market_cap=5500.0,
        ),
    ]
    upsert_etf_master(rows2, source="TestSource", db_path=db_path)
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute("SELECT name, price FROM etf_master WHERE ticker = '069500'")
        name, price = cur.fetchone()
    assert name == "KODEX 200 (rev)"
    assert price == 110.0
    assert list_etf_tickers(db_path) == ["069500", "379800"]


def test_upsert_daily_prices_is_idempotent_on_same_ticker_date(db_path: Path) -> None:
    rows = [
        EtfDailyPriceRow(
            ticker="069500",
            date="2024-10-30",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000,
            change=0.5,
        ),
        EtfDailyPriceRow(
            ticker="069500",
            date="2024-10-31",
            open=100.5,
            high=102.0,
            low=100.0,
            close=101.5,
            volume=1100,
            change=1.0,
        ),
    ]
    upsert_daily_prices(rows, source="TestSource", db_path=db_path)

    # 동일 (ticker, date) 재insert — 행 수 그대로 유지, close 만 갱신
    rows_replace = [
        EtfDailyPriceRow(
            ticker="069500",
            date="2024-10-31",
            open=100.5,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1200,
            change=1.5,
        ),
    ]
    upsert_daily_prices(rows_replace, source="TestSource", db_path=db_path)

    with sqlite3.connect(str(db_path)) as con:
        total = con.execute(
            "SELECT COUNT(*) FROM etf_daily_price WHERE ticker = '069500'"
        ).fetchone()[0]
        close_at_31 = con.execute(
            "SELECT close FROM etf_daily_price WHERE ticker = '069500' AND date = '2024-10-31'"
        ).fetchone()[0]
    assert total == 2
    assert close_at_31 == 102.0


def test_log_refresh_records_counts_and_runtime(db_path: Path) -> None:
    log_refresh(
        run_id="run-test-001",
        source="TestSource/universe",
        asof="2024-10-31",
        attempted=1107,
        success=842,
        fail=265,
        runtime_seconds=233.99,
        error_summary="498400:no_data",
        db_path=db_path,
    )
    log_refresh(
        run_id="run-test-002",
        source="TestSource/prices",
        asof="2024-10-31",
        attempted=10,
        success=10,
        fail=0,
        runtime_seconds=1.5,
        db_path=db_path,
    )

    latest_any = latest_refresh_log(db_path=db_path)
    assert latest_any is not None
    assert latest_any["run_id"] == "run-test-002"
    assert latest_any["attempted_count"] == 10
    assert latest_any["success_count"] == 10
    assert latest_any["fail_count"] == 0

    latest_universe = latest_refresh_log(source="TestSource/universe", db_path=db_path)
    assert latest_universe is not None
    assert latest_universe["run_id"] == "run-test-001"
    assert latest_universe["success_count"] == 842
    assert latest_universe["fail_count"] == 265
    assert latest_universe["error_summary"] == "498400:no_data"


def test_fetch_price_history_returns_sorted_close_only(db_path: Path) -> None:
    rows = [
        EtfDailyPriceRow("069500", "2024-10-31", 0, 0, 0, 102.0, 0, 0),
        EtfDailyPriceRow("069500", "2024-10-30", 0, 0, 0, 100.0, 0, 0),
        EtfDailyPriceRow(
            "069500", "2024-10-29", 0, 0, 0, 0.0, 0, 0
        ),  # close <= 0 → 제외
    ]
    upsert_daily_prices(rows, source="TestSource", db_path=db_path)
    history = fetch_price_history("069500", db_path=db_path)
    assert history == [("2024-10-30", 100.0), ("2024-10-31", 102.0)]


def test_decision_evidence_table_is_never_created(db_path: Path) -> None:
    """AC-10 / §5 금지사항 가드 — 어떤 경로에서도 decision_evidence 가 생성되면 안 됨."""
    init_db(db_path)
    upsert_etf_master(
        [EtfMasterRow("069500", "KODEX 200", "1", 100.0, 1000, 5000.0)],
        source="TestSource",
        db_path=db_path,
    )
    upsert_daily_prices(
        [EtfDailyPriceRow("069500", "2024-10-31", 0, 0, 0, 100.0, 0, 0)],
        source="TestSource",
        db_path=db_path,
    )
    log_refresh(
        run_id="r-1",
        source="TestSource",
        asof="2024-10-31",
        attempted=1,
        success=1,
        fail=0,
        runtime_seconds=0.1,
        db_path=db_path,
    )

    assert not table_exists("decision_evidence", db_path)
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='decision_evidence'"
        )
        assert cur.fetchone()[0] == 0
