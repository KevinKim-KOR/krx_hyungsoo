"""Market timeseries refresh state SSOT (2026-06-30 Closeout).

CLI 최신화 실행 결과 한 건을 SQLite 에 관리한다.
- refresh_scope='daily_prices' 단일 행.
- 실행 이력 / 장기 로그가 아니다 — 최근 결과만 유지.
- D-2 의 market_refresh_state (기존 /market/refresh 용) 와는 별도.

재시작 정규화: 이전 프로세스가 완료 전에 종료되어 running 상태가 남으면
다음 CLI 또는 ML 사전 점검 시 failed 로 정규화. last_success_at /
eligible_ticker_count / benchmark_asof_date 는 유지.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH

REFRESH_SCOPE = "daily_prices"

STATUS_RUNNING = "running"
STATUS_OK = "ok"
STATUS_FAILED = "failed"


@dataclass
class TimeseriesRefreshStateRow:
    target_asof_date: Optional[str] = None
    benchmark_asof_date: Optional[str] = None
    last_attempt_started_at: Optional[str] = None
    last_attempt_finished_at: Optional[str] = None
    last_attempt_status: str = STATUS_FAILED  # 신규 행 default 는 실행 안 됨 취급 X
    last_success_at: Optional[str] = None
    eligible_ticker_count: int = 0
    excluded_ticker_count: int = 0
    error_summary: Optional[str] = None
    updated_at: Optional[str] = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_COLS = (
    "target_asof_date",
    "benchmark_asof_date",
    "last_attempt_started_at",
    "last_attempt_finished_at",
    "last_attempt_status",
    "last_success_at",
    "eligible_ticker_count",
    "excluded_ticker_count",
    "error_summary",
    "updated_at",
)


def _ensure_ready(db_path: Path) -> None:
    from app.market_data_store import _ensure_initialized, init_db

    if not db_path.exists():
        init_db(db_path)
        return
    _ensure_initialized(db_path)


def read_state(
    db_path: Optional[Path] = None,
) -> Optional[TimeseriesRefreshStateRow]:
    # late-bind DEFAULT_DB_PATH 로 monkeypatch 호환.
    if db_path is None:
        from app import market_timeseries_refresh_state_store as _self

        db_path = _self.DEFAULT_DB_PATH
    if not db_path.exists():
        return None
    _ensure_ready(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            f"SELECT {', '.join(_COLS)} FROM market_timeseries_refresh_state "
            "WHERE refresh_scope = ?",
            (REFRESH_SCOPE,),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return TimeseriesRefreshStateRow(**dict(zip(_COLS, row)))


def write_state(
    state: TimeseriesRefreshStateRow,
    *,
    db_path: Optional[Path] = None,
) -> None:
    if db_path is None:
        from app import market_timeseries_refresh_state_store as _self

        db_path = _self.DEFAULT_DB_PATH
    _ensure_ready(db_path)
    payload = (
        REFRESH_SCOPE,
        state.target_asof_date,
        state.benchmark_asof_date,
        state.last_attempt_started_at,
        state.last_attempt_finished_at,
        state.last_attempt_status,
        state.last_success_at,
        int(state.eligible_ticker_count),
        int(state.excluded_ticker_count),
        state.error_summary,
        _utcnow_iso(),
    )
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO market_timeseries_refresh_state (
                refresh_scope,
                target_asof_date,
                benchmark_asof_date,
                last_attempt_started_at,
                last_attempt_finished_at,
                last_attempt_status,
                last_success_at,
                eligible_ticker_count,
                excluded_ticker_count,
                error_summary,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(refresh_scope) DO UPDATE SET
                target_asof_date = excluded.target_asof_date,
                benchmark_asof_date = excluded.benchmark_asof_date,
                last_attempt_started_at = excluded.last_attempt_started_at,
                last_attempt_finished_at = excluded.last_attempt_finished_at,
                last_attempt_status = excluded.last_attempt_status,
                last_success_at = excluded.last_success_at,
                eligible_ticker_count = excluded.eligible_ticker_count,
                excluded_ticker_count = excluded.excluded_ticker_count,
                error_summary = excluded.error_summary,
                updated_at = excluded.updated_at
            """,
            payload,
        )
        con.commit()
    finally:
        con.close()


def normalize_running_to_failed(
    *,
    db_path: Optional[Path] = None,
    summary: str = "interrupted_before_finish",
) -> bool:
    """running 상태가 남아 있으면 failed 로 정규화. 성공 기록은 유지."""
    if db_path is None:
        from app import market_timeseries_refresh_state_store as _self

        db_path = _self.DEFAULT_DB_PATH
    current = read_state(db_path=db_path)
    if current is None or current.last_attempt_status != STATUS_RUNNING:
        return False
    now = _utcnow_iso()
    current.last_attempt_status = STATUS_FAILED
    current.last_attempt_finished_at = now
    current.error_summary = summary
    write_state(current, db_path=db_path)
    return True


def clear_state(db_path: Path = DEFAULT_DB_PATH) -> None:
    if not db_path.exists():
        return
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "DELETE FROM market_timeseries_refresh_state WHERE refresh_scope = ?",
            (REFRESH_SCOPE,),
        )
        con.commit()
    finally:
        con.close()
