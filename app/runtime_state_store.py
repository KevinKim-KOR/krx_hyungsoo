"""SQLite runtime state 저장소 — PARAM / runtime latest status / sent registry.

역할:
- active PARAM (version + value + active pointer)
- runtime latest execution status
- sent registry / duplicate guard

역할 밖:
- market_data.sqlite (시장 evidence 전용)
- decision_evidence.sqlite (별도 STEP)
- runtime history JSONL (log/archive 유지)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

DEFAULT_DB_PATH = Path("state/runtime/runtime_state.sqlite")
DEFAULT_ACTIVE_SCOPE = "three_push"


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


_INITIALIZED_DBS: set[str] = set()


def _ensure_initialized(db_path: Path) -> None:
    key = str(db_path.resolve())
    if key in _INITIALIZED_DBS:
        return
    init_db(db_path)
    _INITIALIZED_DBS.add(key)


def init_db(db_path: Path) -> None:
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


@contextmanager
def _connection(db_path: Path) -> Iterator[sqlite3.Connection]:
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


TABLE_NAMES = (
    "runtime_param_version",
    "runtime_param_value",
    "runtime_param_active",
    "runtime_execution_status",
    "runtime_sent_registry",
)


def list_tables(db_path: Path) -> list[str]:
    with _connection(db_path) as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def integrity_check(db_path: Path) -> str:
    with _connection(db_path) as con:
        row = con.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else ""


def table_row_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with _connection(db_path) as con:
        for t in TABLE_NAMES:
            row = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            counts[t] = int(row[0]) if row else 0
    return counts


# ── PARAM hash / flatten ─────────────────────────────────────────────────────


def canonical_json_sha256(data: dict[str, Any]) -> str:
    """canonical JSON hash (Q5 확정본).

    - sort_keys=True, ensure_ascii=False, separators=(',', ':').
    - UTF-8 bytes 기준 SHA-256.
    """
    payload = json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def flatten_param_dict(data: dict[str, Any]) -> list[tuple[str, str, Any]]:
    """PARAM dict 을 (param_key, value_type, value) 리스트로 정규화 (Q3 dot notation + Q4 index).

    - nested dict → dot notation ("runtime_policy.data_unavailable_behavior").
    - list → index suffix ("enabled_push_kinds[0]").
    - metadata (schema_version, param_id, created_at, approved_at, approved_by, param_source,
      param_description, source_note) 는 flatten 대상에서 제외 — runtime_param_version 컬럼으로 매핑.
    """
    excluded_top = {
        "schema_version",
        "param_id",
        "created_at",
        "approved_at",
        "approved_by",
        "param_source",
        "param_description",
        "source_note",
    }
    out: list[tuple[str, str, Any]] = []
    for k, v in data.items():
        if k in excluded_top:
            continue
        _walk(k, v, out)
    return out


def _walk(path: str, value: Any, out: list[tuple[str, str, Any]]) -> None:
    if isinstance(value, dict):
        for sub_k, sub_v in value.items():
            _walk(f"{path}.{sub_k}", sub_v, out)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _walk(f"{path}[{i}]", item, out)
    elif isinstance(value, bool):
        out.append((path, "boolean", value))
    elif isinstance(value, (int, float)):
        out.append((path, "numeric", value))
    elif isinstance(value, str):
        out.append((path, "text", value))
    elif value is None:
        out.append((path, "text", None))
    else:
        raise RuntimeError(
            f"flatten_param_dict: 표현 불가 타입 {type(value).__name__} at {path!r}"
        )


def _split_value_columns(
    value_type: str, value: Any
) -> tuple[Optional[float], Optional[str], Optional[int]]:
    if value_type == "boolean":
        return None, None, 1 if value else 0
    if value_type == "numeric":
        return float(value), None, None
    if value_type == "text":
        return None, None if value is None else str(value), None
    raise RuntimeError(f"_split_value_columns: 알 수 없는 value_type={value_type!r}")


# ── PARAM version / active pointer ───────────────────────────────────────────


def find_param_version_by_hash(
    db_path: Path, source_hash: str
) -> Optional[dict[str, Any]]:
    with _connection(db_path) as con:
        row = con.execute(
            "SELECT param_version_id FROM runtime_param_version "
            "WHERE source_hash_sha256 = ? LIMIT 1",
            (source_hash,),
        ).fetchone()
    if not row:
        return None
    return {"param_version_id": row[0]}


def insert_param_version(
    db_path: Path,
    *,
    param_version_id: str,
    schema_version: str,
    created_at: str,
    approved_at: str,
    approved_by: str,
    param_source: str,
    source_hash_sha256: str,
    param_description: Optional[str] = None,
    source_note: Optional[str] = None,
    values: Optional[list[tuple[str, str, Any]]] = None,
) -> None:
    with _connection(db_path) as con:
        con.execute(
            "INSERT INTO runtime_param_version ("
            "param_version_id, schema_version, created_at, approved_at, approved_by, "
            "param_source, source_hash_sha256, param_description, source_note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                param_version_id,
                schema_version,
                created_at,
                approved_at,
                approved_by,
                param_source,
                source_hash_sha256,
                param_description,
                source_note,
            ),
        )
        for pk, vt, val in values or []:
            num, txt, boo = _split_value_columns(vt, val)
            con.execute(
                "INSERT INTO runtime_param_value ("
                "param_version_id, param_key, value_type, "
                "numeric_value, text_value, boolean_value) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (param_version_id, pk, vt, num, txt, boo),
            )


def get_active_pointer(
    db_path: Path, active_scope: str = DEFAULT_ACTIVE_SCOPE
) -> Optional[dict[str, Any]]:
    with _connection(db_path) as con:
        row = con.execute(
            "SELECT active_scope, active_param_version_id, activated_at, activated_by "
            "FROM runtime_param_active WHERE active_scope = ?",
            (active_scope,),
        ).fetchone()
    if not row:
        return None
    return {
        "active_scope": row[0],
        "active_param_version_id": row[1],
        "activated_at": row[2],
        "activated_by": row[3],
    }


def set_active_pointer(
    db_path: Path,
    *,
    active_param_version_id: str,
    activated_at: str,
    activated_by: str,
    active_scope: str = DEFAULT_ACTIVE_SCOPE,
) -> None:
    with _connection(db_path) as con:
        con.execute(
            "INSERT INTO runtime_param_active "
            "(active_scope, active_param_version_id, activated_at, activated_by) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(active_scope) DO UPDATE SET "
            "active_param_version_id=excluded.active_param_version_id, "
            "activated_at=excluded.activated_at, "
            "activated_by=excluded.activated_by",
            (active_scope, active_param_version_id, activated_at, activated_by),
        )


def read_param_version(
    db_path: Path, param_version_id: str
) -> Optional[dict[str, Any]]:
    with _connection(db_path) as con:
        row = con.execute(
            "SELECT param_version_id, schema_version, created_at, approved_at, "
            "approved_by, param_source, source_hash_sha256, param_description, source_note "
            "FROM runtime_param_version WHERE param_version_id = ?",
            (param_version_id,),
        ).fetchone()
        if not row:
            return None
        values = con.execute(
            "SELECT param_key, value_type, numeric_value, text_value, boolean_value "
            "FROM runtime_param_value WHERE param_version_id = ? ORDER BY param_key",
            (param_version_id,),
        ).fetchall()
    return {
        "param_version_id": row[0],
        "schema_version": row[1],
        "created_at": row[2],
        "approved_at": row[3],
        "approved_by": row[4],
        "param_source": row[5],
        "source_hash_sha256": row[6],
        "param_description": row[7],
        "source_note": row[8],
        "values": [
            {
                "param_key": v[0],
                "value_type": v[1],
                "numeric_value": v[2],
                "text_value": v[3],
                "boolean_value": None if v[4] is None else bool(v[4]),
            }
            for v in values
        ],
    }


def _value_of(v: dict[str, Any]) -> Any:
    vt = v["value_type"]
    if vt == "boolean":
        return None if v["boolean_value"] is None else bool(v["boolean_value"])
    if vt == "numeric":
        return v["numeric_value"]
    if vt == "text":
        return v["text_value"]
    raise RuntimeError(f"_value_of: 알 수 없는 value_type={vt!r}")


def _assign_by_path(target: dict[str, Any], path: str, value: Any) -> None:
    # Support tokens like 'a.b[0].c'. Split into (key, index?) segments.
    segments: list[tuple[str, list[int]]] = []
    for seg in path.split("."):
        idxs: list[int] = []
        base = seg
        while base.endswith("]") and "[" in base:
            lb = base.rfind("[")
            idx_str = base[lb + 1 : -1]  # noqa: E203  # black slice format
            idxs.insert(0, int(idx_str))
            base = base[:lb]
        segments.append((base, idxs))

    cur: Any = target
    for si, (key, idxs) in enumerate(segments):
        is_last_seg = si == len(segments) - 1
        # Enter dict key.
        if not isinstance(cur, dict):
            raise RuntimeError(f"_assign_by_path: dict 아님 at {path!r} segment {si}")
        if idxs:
            # Ensure list at cur[key], possibly nested.
            if key not in cur or not isinstance(cur[key], list):
                cur[key] = []
            list_ref = cur[key]
            for li, idx in enumerate(idxs):
                is_last_idx = li == len(idxs) - 1
                while len(list_ref) <= idx:
                    list_ref.append(None)
                if is_last_seg and is_last_idx:
                    list_ref[idx] = value
                    return
                # Descend further.
                if list_ref[idx] is None:
                    # If more idxs follow, keep list; else dict for further path.
                    list_ref[idx] = [] if li < len(idxs) - 1 else {}
                if li < len(idxs) - 1:
                    list_ref = list_ref[idx]
                else:
                    cur = list_ref[idx]
        else:
            if is_last_seg:
                cur[key] = value
                return
            if key not in cur or not isinstance(cur[key], dict):
                cur[key] = {}
            cur = cur[key]


def reconstruct_param_dict(version_row: dict[str, Any]) -> dict[str, Any]:
    """DB row + values 를 latest_runtime_param.json 의미 구조로 재구성."""
    out: dict[str, Any] = {
        "schema_version": version_row["schema_version"],
        "param_id": version_row["param_version_id"],
        "created_at": version_row["created_at"],
        "approved_at": version_row["approved_at"],
        "approved_by": version_row["approved_by"],
        "param_source": version_row["param_source"],
    }
    if version_row.get("param_description") is not None:
        out["param_description"] = version_row["param_description"]
    if version_row.get("source_note") is not None:
        out["source_note"] = version_row["source_note"]
    for v in version_row["values"]:
        _assign_by_path(out, v["param_key"], _value_of(v))
    return out


# ── runtime_execution_status ─────────────────────────────────────────────────


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
    inserted_at: str,
) -> int:
    with _connection(db_path) as con:
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
                inserted_at,
            ),
        )
    return int(cur.lastrowid or 0)


def latest_execution_status(db_path: Path) -> Optional[dict[str, Any]]:
    with _connection(db_path) as con:
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


# ── runtime_sent_registry ────────────────────────────────────────────────────


def registry_contains(
    db_path: Path, push_kind: str, param_id: str, runtime_date_kst: str
) -> bool:
    with _connection(db_path) as con:
        row = con.execute(
            "SELECT 1 FROM runtime_sent_registry "
            "WHERE push_kind = ? AND param_id = ? AND runtime_date_kst = ? LIMIT 1",
            (push_kind, param_id, runtime_date_kst),
        ).fetchone()
    return row is not None


def registry_insert(
    db_path: Path,
    *,
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
    sent_at_utc: str,
    inserted_at: str,
    on_conflict: str = "ignore",
) -> bool:
    """중복 시 조용히 덮어쓰지 않고 ignore (Q10 · §7.5 요구사항)."""
    sql = (
        "INSERT OR IGNORE INTO runtime_sent_registry "
        "(push_kind, param_id, runtime_date_kst, sent_at_utc, inserted_at) "
        "VALUES (?, ?, ?, ?, ?)"
        if on_conflict == "ignore"
        else "INSERT INTO runtime_sent_registry "
        "(push_kind, param_id, runtime_date_kst, sent_at_utc, inserted_at) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    with _connection(db_path) as con:
        cur = con.execute(
            sql, (push_kind, param_id, runtime_date_kst, sent_at_utc, inserted_at)
        )
    return cur.rowcount > 0


def registry_count(db_path: Path) -> int:
    with _connection(db_path) as con:
        row = con.execute("SELECT COUNT(*) FROM runtime_sent_registry").fetchone()
    return int(row[0]) if row else 0
