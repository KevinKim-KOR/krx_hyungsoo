"""Market refresh state SSOT — SQLite read / write / normalize.

D-2 (2026-06-30): 기존 market_refresh_service 의 in-memory state 를
SQLite 로 영속화. SSOT 는 SQLite. in-memory 는 동기화된 캐시.

본 모듈은 market_refresh_state 테이블 (단일 행, refresh_scope='market_data')
에 대한 read / upsert / running 정규화 함수를 제공한다.

규칙:
- 별도 DB / cache / history 테이블 신설 금지.
- JSON 파일은 상태의 기준 저장소가 아니다.
- 실패가 last_success_asof_date / last_success_at 을 덮어쓰면 안 된다.
- running 상태 재시작 정규화는 detail 필드를 임의로 초기화하지 않는다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH, _ensure_initialized  # noqa: F401

REFRESH_SCOPE = "market_data"


@dataclass
class MarketRefreshStateRow:
    """SQLite market_refresh_state 단일 행. RefreshState 외부 노출 필드 전체 포함."""

    refresh_id: Optional[str] = None
    last_success_asof_date: Optional[str] = None
    last_success_at: Optional[str] = None
    last_attempt_started_at: Optional[str] = None
    last_attempt_finished_at: Optional[str] = None
    last_attempt_status: Optional[str] = None  # idle / running / completed / failed
    last_error_summary: Optional[str] = None
    asof: Optional[str] = None
    universe_count: Optional[int] = None
    price_attempted_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    updated_at: Optional[str] = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_COLS = (
    "refresh_id",
    "last_success_asof_date",
    "last_success_at",
    "last_attempt_started_at",
    "last_attempt_finished_at",
    "last_attempt_status",
    "last_error_summary",
    "asof",
    "universe_count",
    "price_attempted_count",
    "price_success_count",
    "price_fail_count",
    "runtime_seconds",
    "updated_at",
)


def read_state(db_path: Path = DEFAULT_DB_PATH) -> Optional[MarketRefreshStateRow]:
    """단일 행 조회. DB 파일 또는 행 자체가 없으면 None.

    DB 파일이 없을 때는 init_db 를 강제 호출하지 않는다 — 본 함수는 read-only.
    """
    if not db_path.exists():
        return None
    _ensure_initialized(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            f"SELECT {', '.join(_COLS)} FROM market_refresh_state "
            "WHERE refresh_scope = ?",
            (REFRESH_SCOPE,),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return MarketRefreshStateRow(**dict(zip(_COLS, row)))


def write_state(
    state: MarketRefreshStateRow,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """단일 행 upsert. updated_at 은 호출 시각으로 강제 설정."""
    _ensure_initialized(db_path)
    payload = (
        REFRESH_SCOPE,
        state.refresh_id,
        state.last_success_asof_date,
        state.last_success_at,
        state.last_attempt_started_at,
        state.last_attempt_finished_at,
        state.last_attempt_status,
        state.last_error_summary,
        state.asof,
        state.universe_count,
        state.price_attempted_count,
        state.price_success_count,
        state.price_fail_count,
        state.runtime_seconds,
        _utcnow_iso(),
    )
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO market_refresh_state (
                refresh_scope,
                refresh_id,
                last_success_asof_date,
                last_success_at,
                last_attempt_started_at,
                last_attempt_finished_at,
                last_attempt_status,
                last_error_summary,
                asof,
                universe_count,
                price_attempted_count,
                price_success_count,
                price_fail_count,
                runtime_seconds,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(refresh_scope) DO UPDATE SET
                refresh_id = excluded.refresh_id,
                last_success_asof_date = excluded.last_success_asof_date,
                last_success_at = excluded.last_success_at,
                last_attempt_started_at = excluded.last_attempt_started_at,
                last_attempt_finished_at = excluded.last_attempt_finished_at,
                last_attempt_status = excluded.last_attempt_status,
                last_error_summary = excluded.last_error_summary,
                asof = excluded.asof,
                universe_count = excluded.universe_count,
                price_attempted_count = excluded.price_attempted_count,
                price_success_count = excluded.price_success_count,
                price_fail_count = excluded.price_fail_count,
                runtime_seconds = excluded.runtime_seconds,
                updated_at = excluded.updated_at
            """,
            payload,
        )
        con.commit()
    finally:
        con.close()


def normalize_running_to_failed(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    summary: str = "interrupted_before_finish",
) -> bool:
    """재시작 시 SQLite 에 남아 있는 running 상태를 failed 로 정규화.

    - last_success_asof_date / last_success_at 은 유지.
    - detail 필드 (universe_count, price_*, runtime_seconds, asof) 도 보존.
    - finished_at 만 현재 시각으로 채우고 error_summary 에 중단 사유 기록.

    return: 정규화가 실행됐으면 True, 대상 행이 없거나 running 이 아니면 False.
    """
    current = read_state(db_path=db_path)
    if current is None or current.last_attempt_status != "running":
        return False
    now = _utcnow_iso()
    current.last_attempt_status = "failed"
    current.last_attempt_finished_at = now
    current.last_error_summary = summary
    write_state(current, db_path=db_path)
    return True


def clear_state(db_path: Path = DEFAULT_DB_PATH) -> None:
    """테스트 격리용 — market_refresh_state 단일 행 제거.

    DB 파일이 아직 존재하지 않으면 no-op (init_db 강제 호출 X) —
    "DB 부재 시 missing" 의미를 가진 기존 테스트와의 호환.
    """
    if not db_path.exists():
        return
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "DELETE FROM market_refresh_state WHERE refresh_scope = ?",
            (REFRESH_SCOPE,),
        )
        con.commit()
    finally:
        con.close()
