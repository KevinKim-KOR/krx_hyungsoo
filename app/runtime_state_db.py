"""Runtime State DB 공통 helper — path / connection / schema / integrity / hash.

역할:
- DEFAULT_DB_PATH 상수
- sqlite connection context manager
- 5 table schema 초기화 orchestration
- integrity_check / list_tables / table_row_counts
- canonical JSON hash (Cutover v1 Q5 확정본)
- ISO8601 UTC timestamp helper

역할 밖:
- PARAM / execution status / sent registry 의 비즈니스 로직 (각 *_store.py 담당)
- JSON legacy IO
- Telegram / market DB / decision evidence DB
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

DEFAULT_DB_PATH = Path("state/runtime/runtime_state.sqlite")
DEFAULT_ACTIVE_SCOPE = "three_push"


# ── Schema DDL (Cutover v1 5 table — schema 변경 금지) ────────────────────────


RUNTIME_PARAM_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS runtime_param_version (
    param_version_id       TEXT PRIMARY KEY,
    schema_version         TEXT NOT NULL,
    created_at             TEXT NOT NULL,
    approved_at            TEXT NOT NULL,
    approved_by            TEXT NOT NULL,
    param_source           TEXT NOT NULL,
    source_hash_sha256     TEXT NOT NULL,
    source_data_version    TEXT,
    approval_status        TEXT,
    activated_at           TEXT,
    param_description      TEXT,
    source_note            TEXT,
    note                   TEXT
);
""".strip()

RUNTIME_PARAM_VERSION_HASH_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_runtime_param_version_hash "
    "ON runtime_param_version(source_hash_sha256);"
)

RUNTIME_PARAM_VALUE_DDL = """
CREATE TABLE IF NOT EXISTS runtime_param_value (
    param_version_id    TEXT NOT NULL,
    param_key           TEXT NOT NULL,
    value_type          TEXT NOT NULL,
    numeric_value       REAL,
    text_value          TEXT,
    boolean_value       INTEGER,
    unit                TEXT,
    description         TEXT,
    PRIMARY KEY (param_version_id, param_key),
    FOREIGN KEY (param_version_id) REFERENCES runtime_param_version(param_version_id)
);
""".strip()

RUNTIME_PARAM_ACTIVE_DDL = """
CREATE TABLE IF NOT EXISTS runtime_param_active (
    active_scope             TEXT PRIMARY KEY,
    active_param_version_id  TEXT NOT NULL,
    activated_at             TEXT NOT NULL,
    activated_by             TEXT NOT NULL,
    FOREIGN KEY (active_param_version_id) REFERENCES runtime_param_version(param_version_id)
);
""".strip()

RUNTIME_EXECUTION_STATUS_DDL = """
CREATE TABLE IF NOT EXISTS runtime_execution_status (
    run_id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    push_kind                           TEXT NOT NULL,
    mode                                TEXT NOT NULL,
    status                              TEXT NOT NULL,
    reason                              TEXT,
    started_at                          TEXT NOT NULL,
    finished_at                         TEXT NOT NULL,
    runtime_kst                         TEXT NOT NULL,
    runtime_date_kst                    TEXT NOT NULL,
    param_id                            TEXT NOT NULL,
    param_source                        TEXT NOT NULL,
    message_text_length                 INTEGER NOT NULL DEFAULT 0,
    availability_available              INTEGER NOT NULL DEFAULT 0,
    availability_unavailable_or_other   INTEGER NOT NULL DEFAULT 0,
    duplicate_key                       TEXT NOT NULL,
    telegram_attempted                  INTEGER NOT NULL DEFAULT 0,
    telegram_sent                       INTEGER NOT NULL DEFAULT 0,
    error                               TEXT,
    inserted_at                         TEXT NOT NULL
);
""".strip()

RUNTIME_EXECUTION_STATUS_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_runtime_execution_status_started_at "
    "ON runtime_execution_status(started_at);"
)

RUNTIME_SENT_REGISTRY_DDL = """
CREATE TABLE IF NOT EXISTS runtime_sent_registry (
    push_kind         TEXT NOT NULL,
    param_id          TEXT NOT NULL,
    runtime_date_kst  TEXT NOT NULL,
    sent_at_utc       TEXT NOT NULL,
    inserted_at       TEXT NOT NULL,
    PRIMARY KEY (push_kind, param_id, runtime_date_kst)
);
""".strip()


TABLE_NAMES = (
    "runtime_param_version",
    "runtime_param_value",
    "runtime_param_active",
    "runtime_execution_status",
    "runtime_sent_registry",
)


_INITIALIZED_DBS: set[str] = set()


def init_db(db_path: Path) -> None:
    """5 table + index 를 idempotent 하게 생성."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        con.execute(RUNTIME_PARAM_VERSION_DDL)
        con.execute(RUNTIME_PARAM_VERSION_HASH_INDEX_DDL)
        con.execute(RUNTIME_PARAM_VALUE_DDL)
        con.execute(RUNTIME_PARAM_ACTIVE_DDL)
        con.execute(RUNTIME_EXECUTION_STATUS_DDL)
        con.execute(RUNTIME_EXECUTION_STATUS_INDEX_DDL)
        con.execute(RUNTIME_SENT_REGISTRY_DDL)
        con.commit()
    finally:
        con.close()


def _ensure_initialized(db_path: Path) -> None:
    key = str(db_path.resolve())
    if key in _INITIALIZED_DBS:
        return
    init_db(db_path)
    _INITIALIZED_DBS.add(key)


@contextmanager
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """sqlite3 connection context manager. FK 활성화 + auto commit on success."""
    _ensure_initialized(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys = ON;")
        yield con
        con.commit()
    finally:
        con.close()


def reset_init_cache_for_testing() -> None:
    _INITIALIZED_DBS.clear()


# ── Introspection ────────────────────────────────────────────────────────────


def list_tables(db_path: Path) -> list[str]:
    with connection(db_path) as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def integrity_check(db_path: Path) -> str:
    with connection(db_path) as con:
        row = con.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else ""


def table_row_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with connection(db_path) as con:
        for t in TABLE_NAMES:
            row = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            counts[t] = int(row[0]) if row else 0
    return counts


# ── Hash / timestamp helper ──────────────────────────────────────────────────


def canonical_json_sha256(data: dict[str, Any]) -> str:
    """Cutover v1 Q5 확정본: canonical JSON → UTF-8 → SHA-256.

    - sort_keys=True (key 순서 정규화)
    - ensure_ascii=False (문자 표기 정규화)
    - separators=(",", ":") (whitespace 정규화)
    """
    payload = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
