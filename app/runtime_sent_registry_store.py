"""Runtime sent registry store — runtime_sent_registry.

역할:
- Telegram 중복 발송 방지 상태 (Cutover v1 Q10 UNIQUE(push_kind, param_id, runtime_date_kst))
- duplicate guard 조회 · sent mark · seed insert
- Cutover v1 §7.5 · Mapping v1 §10.3 계약 준수

역할 밖:
- PARAM / execution status
- message_hash / send_status / TTL (BACKLOG §12.4)
- Telegram 실제 발송
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app import runtime_state_db as _db
from app.runtime_state_db import connection, utc_now_iso


def _default_db_path() -> Path:
    return _db.DEFAULT_DB_PATH


def contains(
    db_path: Path,
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
) -> bool:
    with connection(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM runtime_sent_registry "
            "WHERE push_kind = ? AND param_id = ? AND runtime_date_kst = ? LIMIT 1",
            (push_kind, param_id, runtime_date_kst),
        ).fetchone()
    return row is not None


def insert(
    db_path: Path,
    *,
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
    sent_at_utc: str,
    inserted_at: Optional[str] = None,
    on_conflict: str = "ignore",
) -> bool:
    """중복 시 조용히 덮어쓰지 않고 ignore (Cutover v1 Q10 · §7.5)."""
    sql = (
        "INSERT OR IGNORE INTO runtime_sent_registry "
        "(push_kind, param_id, runtime_date_kst, sent_at_utc, inserted_at) "
        "VALUES (?, ?, ?, ?, ?)"
        if on_conflict == "ignore"
        else "INSERT INTO runtime_sent_registry "
        "(push_kind, param_id, runtime_date_kst, sent_at_utc, inserted_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    with connection(db_path) as con:
        cur = con.execute(
            sql,
            (
                push_kind,
                param_id,
                runtime_date_kst,
                sent_at_utc,
                inserted_at or utc_now_iso(),
            ),
        )
    return cur.rowcount > 0


def count(db_path: Optional[Path] = None) -> int:
    p = Path(db_path or _default_db_path())
    with connection(p) as con:
        row = con.execute("SELECT COUNT(*) FROM runtime_sent_registry").fetchone()
    return int(row[0]) if row else 0


# ── High-level runner API ────────────────────────────────────────────────────


def is_already_sent(
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
    *,
    db_path: Optional[Path] = None,
) -> bool:
    p = Path(db_path or _default_db_path())
    return contains(p, push_kind, param_id, runtime_date_kst)


def mark_sent(
    *,
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
    sent_at_utc: str,
    db_path: Optional[Path] = None,
) -> bool:
    p = Path(db_path or _default_db_path())
    return insert(
        p,
        push_kind=push_kind,
        param_id=param_id,
        runtime_date_kst=runtime_date_kst,
        sent_at_utc=sent_at_utc,
    )
