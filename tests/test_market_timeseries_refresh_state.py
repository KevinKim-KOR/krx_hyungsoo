"""market_timeseries_refresh_state SSOT 테스트 (2026-06-30 Closeout)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.market_data_store import init_db
from app.market_timeseries_refresh_state_store import (
    STATUS_FAILED,
    STATUS_OK,
    STATUS_RUNNING,
    TimeseriesRefreshStateRow,
    normalize_running_to_failed,
    read_state,
    write_state,
)


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def test_initial_state_none(fake_db: Path) -> None:
    assert read_state(db_path=fake_db) is None


def test_write_and_read_single_row(fake_db: Path) -> None:
    write_state(
        TimeseriesRefreshStateRow(
            target_asof_date="2024-10-31",
            benchmark_asof_date="2024-10-31",
            last_attempt_started_at="2024-10-31T00:00:00Z",
            last_attempt_finished_at="2024-10-31T00:05:00Z",
            last_attempt_status=STATUS_OK,
            last_success_at="2024-10-31T00:05:00Z",
            eligible_ticker_count=1000,
            excluded_ticker_count=50,
        ),
        db_path=fake_db,
    )
    row = read_state(db_path=fake_db)
    assert row is not None
    assert row.last_attempt_status == STATUS_OK
    assert row.benchmark_asof_date == "2024-10-31"
    assert row.eligible_ticker_count == 1000
    assert row.excluded_ticker_count == 50


def test_normalize_running_to_failed_preserves_success(fake_db: Path) -> None:
    write_state(
        TimeseriesRefreshStateRow(
            target_asof_date="2024-11-01",
            benchmark_asof_date="2024-10-31",
            last_attempt_started_at="2024-11-01T00:00:00Z",
            last_attempt_status=STATUS_RUNNING,
            last_success_at="2024-10-31T00:05:00Z",
            eligible_ticker_count=1000,
            excluded_ticker_count=50,
        ),
        db_path=fake_db,
    )
    changed = normalize_running_to_failed(db_path=fake_db)
    assert changed is True
    row = read_state(db_path=fake_db)
    assert row is not None
    assert row.last_attempt_status == STATUS_FAILED
    assert row.last_attempt_finished_at is not None
    # 이전 성공 기록은 유지.
    assert row.last_success_at == "2024-10-31T00:05:00Z"
    assert row.benchmark_asof_date == "2024-10-31"
    assert row.eligible_ticker_count == 1000
    assert row.excluded_ticker_count == 50


def test_normalize_no_op_when_not_running(fake_db: Path) -> None:
    write_state(
        TimeseriesRefreshStateRow(
            last_attempt_status=STATUS_OK,
        ),
        db_path=fake_db,
    )
    assert normalize_running_to_failed(db_path=fake_db) is False


def test_single_row_principle(fake_db: Path) -> None:
    write_state(
        TimeseriesRefreshStateRow(last_attempt_status=STATUS_OK), db_path=fake_db
    )
    write_state(
        TimeseriesRefreshStateRow(
            last_attempt_status=STATUS_OK, eligible_ticker_count=999
        ),
        db_path=fake_db,
    )
    import sqlite3

    con = sqlite3.connect(str(fake_db))
    try:
        (n,) = con.execute(
            "SELECT COUNT(*) FROM market_timeseries_refresh_state"
        ).fetchone()
    finally:
        con.close()
    assert n == 1
