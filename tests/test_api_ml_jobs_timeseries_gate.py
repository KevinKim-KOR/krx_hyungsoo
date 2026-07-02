"""ML 실행 게이트: POST /ml/jobs/evidence-refresh 가 시계열 최신화 준비 여부를
SQLite 만 read 하여 사전 점검한다 (2026-06-30 Closeout, 지시문 §9).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api_ml_jobs
from app.api import app
from app.market_data_store import init_db
from app.market_timeseries_ingestion_service import BENCHMARK_KODEX200_TICKER
from app.market_timeseries_ingestion_store import (
    STATUS_NORMAL as INGEST_STATUS_NORMAL,
    TimeseriesIngestionStateRow,
    upsert_state as upsert_ingest_state,
)
from app.market_timeseries_refresh_state_store import (
    STATUS_OK as REFRESH_STATUS_OK,
    STATUS_RUNNING,
    TimeseriesRefreshStateRow,
    read_state as read_refresh_state,
    write_state as write_refresh_state,
)


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "market_data.sqlite"
    init_db(db_path)
    monkeypatch.setattr("app.market_data_store.DEFAULT_DB_PATH", db_path, raising=True)
    monkeypatch.setattr(
        "app.market_timeseries_ingestion_store.DEFAULT_DB_PATH",
        db_path,
        raising=True,
    )
    monkeypatch.setattr(
        "app.market_timeseries_refresh_state_store.DEFAULT_DB_PATH",
        db_path,
        raising=True,
    )
    return db_path


def _seed_ready(db: Path) -> None:
    upsert_ingest_state(
        TimeseriesIngestionStateRow(
            ticker=BENCHMARK_KODEX200_TICKER,
            ingestion_status=INGEST_STATUS_NORMAL,
            confirmed_series_start_date="2014-04-07",
            confirmed_series_end_date="2024-10-31",
            observed_trading_day_count=2500,
            source="NAVER_FDR",
            price_basis="SOURCE_CLOSE",
        ),
        db_path=db,
    )
    write_refresh_state(
        TimeseriesRefreshStateRow(
            target_asof_date="2024-10-31",
            benchmark_asof_date="2024-10-31",
            last_attempt_status=REFRESH_STATUS_OK,
            last_success_at="2024-10-31T00:05:00Z",
            eligible_ticker_count=1000,
            excluded_ticker_count=50,
        ),
        db_path=db,
    )


def test_gate_blocks_when_no_refresh_row(db: Path) -> None:
    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "시계열 최신화가 완료되지 않았습니다" in body["message"]


def test_gate_blocks_when_status_not_ok(db: Path) -> None:
    _seed_ready(db)
    row = read_refresh_state(db_path=db)
    row.last_attempt_status = "failed"
    write_refresh_state(row, db_path=db)
    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    assert resp.json()["status"] == "error"


def test_gate_blocks_when_benchmark_kodex200_missing(db: Path) -> None:
    write_refresh_state(
        TimeseriesRefreshStateRow(
            benchmark_asof_date="2024-10-31",
            last_attempt_status=REFRESH_STATUS_OK,
            eligible_ticker_count=1000,
            excluded_ticker_count=0,
        ),
        db_path=db,
    )
    client = TestClient(app)
    assert client.post("/ml/jobs/evidence-refresh").json()["status"] == "error"


def test_gate_blocks_when_eligible_zero(db: Path) -> None:
    upsert_ingest_state(
        TimeseriesIngestionStateRow(
            ticker=BENCHMARK_KODEX200_TICKER,
            ingestion_status=INGEST_STATUS_NORMAL,
            source="NAVER_FDR",
            price_basis="SOURCE_CLOSE",
        ),
        db_path=db,
    )
    write_refresh_state(
        TimeseriesRefreshStateRow(
            benchmark_asof_date="2024-10-31",
            last_attempt_status=REFRESH_STATUS_OK,
            eligible_ticker_count=0,
            excluded_ticker_count=0,
        ),
        db_path=db,
    )
    client = TestClient(app)
    assert client.post("/ml/jobs/evidence-refresh").json()["status"] == "error"


def test_gate_normalizes_running_refresh_before_check(db: Path) -> None:
    _seed_ready(db)
    row = read_refresh_state(db_path=db)
    row.last_attempt_status = STATUS_RUNNING
    write_refresh_state(row, db_path=db)
    client = TestClient(app)
    # running 이 failed 로 정규화 → 게이트 error 응답.
    assert client.post("/ml/jobs/evidence-refresh").json()["status"] == "error"
    after = read_refresh_state(db_path=db)
    assert after.last_attempt_status == "failed"


def test_gate_allows_when_ready(db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_ready(db)

    # start_evidence_refresh_job 을 stub — 실제 background job 실행 X.
    def fake_start(**kwargs):
        return {"job_id": "fake", "state": "accepted"}

    monkeypatch.setattr(api_ml_jobs, "start_evidence_refresh_job", fake_start)

    client = TestClient(app)
    resp = client.post("/ml/jobs/evidence-refresh")
    body = resp.json()
    assert body["status"] == "accepted"
