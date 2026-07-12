"""Runtime execution status store — runtime_execution_status.

역할:
- runner 가 매 실행마다 append 하는 latest execution status record 관리
- run_id (AUTOINCREMENT) 로 매 실행 별 row 유지
- latest_pointer 별도 없이 `ORDER BY run_id DESC LIMIT 1` 로 latest 조회

역할 밖:
- history JSONL append (Q9 (c) 확정: runner 가 직접 별도로 append)
- PARAM / sent registry
- Telegram / market DB / decision evidence DB
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app import runtime_state_db as _db
from app.runtime_state_db import connection, utc_now_iso


def _default_db_path() -> Path:
    return _db.DEFAULT_DB_PATH


def insert_execution_status(
    db_path: Path,
    *,
    push_kind: str,
    mode: str,
    status: str,
    reason: Optional[str],
    started_at: str,
    finished_at: str,
    runtime_kst: str,
    runtime_date_kst: str,
    param_id: str,
    param_source: str,
    message_text_length: int,
    availability_available: int,
    availability_unavailable_or_other: int,
    duplicate_key: str,
    telegram_attempted: bool,
    telegram_sent: bool,
    error: Optional[str],
    inserted_at: Optional[str] = None,
) -> int:
    with connection(db_path) as con:
        cur = con.execute(
            "INSERT INTO runtime_execution_status ("
            "push_kind, mode, status, reason, started_at, finished_at, "
            "runtime_kst, runtime_date_kst, param_id, param_source, "
            "message_text_length, availability_available, availability_unavailable_or_other, "
            "duplicate_key, telegram_attempted, telegram_sent, error, inserted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                push_kind,
                mode,
                status,
                reason,
                started_at,
                finished_at,
                runtime_kst,
                runtime_date_kst,
                param_id,
                param_source,
                message_text_length,
                availability_available,
                availability_unavailable_or_other,
                duplicate_key,
                1 if telegram_attempted else 0,
                1 if telegram_sent else 0,
                error,
                inserted_at or utc_now_iso(),
            ),
        )
    return int(cur.lastrowid or 0)


def insert_status_from_record(
    record: dict[str, Any],
    *,
    db_path: Optional[Path] = None,
    inserted_at: Optional[str] = None,
) -> int:
    """runner record dict → runtime_execution_status insert.

    fail-closed: DB 접근 실패 시 예외 상승. JSON fallback 없음.
    """
    p = Path(db_path or _default_db_path())
    availability = record.get("availability") or {}
    return insert_execution_status(
        p,
        push_kind=str(record.get("push_kind", "")),
        mode=str(record.get("mode", "")),
        status=str(record.get("status", "")),
        reason=record.get("reason"),
        started_at=str(record.get("started_at", "")),
        finished_at=str(record.get("finished_at", "")),
        runtime_kst=str(record.get("runtime_kst", "")),
        runtime_date_kst=str(record.get("runtime_date_kst", "")),
        param_id=str(record.get("param_id", "")),
        param_source=str(record.get("param_source", "")),
        message_text_length=int(record.get("message_text_length", 0)),
        availability_available=int(availability.get("available", 0)),
        availability_unavailable_or_other=int(
            availability.get("unavailable_or_other", 0)
        ),
        duplicate_key=str(record.get("duplicate_key", "")),
        telegram_attempted=bool(record.get("telegram_attempted", False)),
        telegram_sent=bool(record.get("telegram_sent", False)),
        error=record.get("error"),
        inserted_at=inserted_at,
    )


def latest_execution_status(db_path: Optional[Path] = None) -> Optional[dict[str, Any]]:
    p = Path(db_path or _default_db_path())
    with connection(p) as con:
        row = con.execute(
            "SELECT run_id, push_kind, mode, status, reason, started_at, finished_at, "
            "runtime_kst, runtime_date_kst, param_id, param_source, message_text_length, "
            "availability_available, availability_unavailable_or_other, duplicate_key, "
            "telegram_attempted, telegram_sent, error, inserted_at "
            "FROM runtime_execution_status ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        "run_id": row[0],
        "push_kind": row[1],
        "mode": row[2],
        "status": row[3],
        "reason": row[4],
        "started_at": row[5],
        "finished_at": row[6],
        "runtime_kst": row[7],
        "runtime_date_kst": row[8],
        "param_id": row[9],
        "param_source": row[10],
        "message_text_length": row[11],
        "availability_available": row[12],
        "availability_unavailable_or_other": row[13],
        "duplicate_key": row[14],
        "telegram_attempted": bool(row[15]),
        "telegram_sent": bool(row[16]),
        "error": row[17],
        "inserted_at": row[18],
    }
