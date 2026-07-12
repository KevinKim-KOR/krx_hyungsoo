"""Runtime PARAM store — runtime_param_version + runtime_param_value + runtime_param_active.

역할:
- PARAM version 정규화 write (canonical hash idempotent, Cutover v1 Q10)
- PARAM value flatten (dot notation + index suffix, Cutover v1 Q3 · Q4)
- active pointer upsert (active_scope = "three_push" default, Cutover v1 Q2)
- active PARAM reconstruction (canonical 의미 왕복)
- read/write 모두 JSON fallback 없음 fail-closed (Cutover v1 §9 · §12)

역할 밖:
- runtime_execution_status / runtime_sent_registry (각 store)
- schema 생성 (runtime_state_db.init_db 담당)
- Telegram / market DB / decision evidence DB
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app import runtime_state_db as _db
from app.runtime_state_db import (
    DEFAULT_ACTIVE_SCOPE,
    canonical_json_sha256,
    connection,
    utc_now_iso,
)


def _default_db_path() -> Path:
    # attribute lookup 매 호출 → conftest monkeypatch 가 반영됨.
    return _db.DEFAULT_DB_PATH


# ── PARAM value flatten / reconstruct (Q3 · Q4 · §7.2 계약) ──────────────────


_EXCLUDED_TOP_FIELDS = {
    "schema_version",
    "param_id",
    "created_at",
    "approved_at",
    "approved_by",
    "param_source",
    "param_description",
    "source_note",
}


def flatten_param_dict(data: dict[str, Any]) -> list[tuple[str, str, Any]]:
    """PARAM dict → (param_key, value_type, value) 리스트.

    Q3 (a) dot notation: nested dict → "runtime_policy.data_unavailable_behavior".
    Q4 (c) index suffix: list → "enabled_push_kinds[0]".
    metadata (§7.1 컬럼) 는 runtime_param_version 로 매핑되므로 flatten 제외.
    """
    out: list[tuple[str, str, Any]] = []
    for k, v in data.items():
        if k in _EXCLUDED_TOP_FIELDS:
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


def _value_of(row: dict[str, Any]) -> Any:
    vt = row["value_type"]
    if vt == "boolean":
        return None if row["boolean_value"] is None else bool(row["boolean_value"])
    if vt == "numeric":
        return row["numeric_value"]
    if vt == "text":
        return row["text_value"]
    raise RuntimeError(f"_value_of: 알 수 없는 value_type={vt!r}")


def _assign_by_path(target: dict[str, Any], path: str, value: Any) -> None:
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
        if not isinstance(cur, dict):
            raise RuntimeError(f"_assign_by_path: dict 아님 at {path!r} segment {si}")
        if idxs:
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
                if list_ref[idx] is None:
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


# ── PARAM version write / read ───────────────────────────────────────────────


def find_param_version_by_hash(
    db_path: Path, source_hash: str
) -> Optional[dict[str, Any]]:
    with connection(db_path) as con:
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
    with connection(db_path) as con:
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


def read_param_version(
    db_path: Path, param_version_id: str
) -> Optional[dict[str, Any]]:
    with connection(db_path) as con:
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


def reconstruct_param_dict(version_row: dict[str, Any]) -> dict[str, Any]:
    """DB row + values → latest_runtime_param.json 의미 구조."""
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


# ── Active pointer ───────────────────────────────────────────────────────────


def get_active_pointer(
    db_path: Path, active_scope: str = DEFAULT_ACTIVE_SCOPE
) -> Optional[dict[str, Any]]:
    with connection(db_path) as con:
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
    with connection(db_path) as con:
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


# ── High-level API (Cutover v1 대체 API) ─────────────────────────────────────


def create_param_version(
    param_dict: dict[str, Any],
    *,
    db_path: Optional[Path] = None,
) -> tuple[str, str, bool]:
    """PARAM dict 을 DB 에 등록. 이미 동일 hash version 이 있으면 재사용.

    Q10 (b) idempotent 재사용 계약: `find_param_version_by_hash` 로 hash 매칭.
    반환: (param_version_id, source_hash_sha256, created_new).
    """
    p = Path(db_path or _default_db_path())
    source_hash = canonical_json_sha256(param_dict)
    existing = find_param_version_by_hash(p, source_hash)
    if existing:
        return existing["param_version_id"], source_hash, False
    values = flatten_param_dict(param_dict)
    extra = param_dict
    insert_param_version(
        p,
        param_version_id=str(extra["param_id"]),
        schema_version=str(extra["schema_version"]),
        created_at=str(extra["created_at"]),
        approved_at=str(extra["approved_at"]),
        approved_by=str(extra["approved_by"]),
        param_source=str(extra["param_source"]),
        source_hash_sha256=source_hash,
        param_description=extra.get("param_description"),
        source_note=extra.get("source_note"),
        values=values,
    )
    return str(extra["param_id"]), source_hash, True


def activate_param_version(
    param_version_id: str,
    *,
    activated_at: Optional[str] = None,
    activated_by: str,
    db_path: Optional[Path] = None,
    active_scope: str = DEFAULT_ACTIVE_SCOPE,
) -> None:
    """runtime_param_active pointer 를 지정 version 으로 갱신 (upsert)."""
    p = Path(db_path or _default_db_path())
    set_active_pointer(
        p,
        active_param_version_id=param_version_id,
        activated_at=activated_at or utc_now_iso(),
        activated_by=activated_by,
        active_scope=active_scope,
    )


def read_active_param_dict(
    db_path: Optional[Path] = None,
    active_scope: str = DEFAULT_ACTIVE_SCOPE,
) -> dict[str, Any]:
    """active pointer → version row → reconstruct → PARAM dict.

    fail-closed (Cutover v1 §9 · §12):
      - DB 파일 부재 → RuntimeError.
      - active pointer 부재 → RuntimeError.
      - version row 부재 → RuntimeError.
    JSON fallback 코드 경로 없음.
    """
    p = Path(db_path or _default_db_path())
    if not p.exists():
        raise RuntimeError(
            f"runtime_state DB 부재 — JSON fallback 없음 (fail closed): {p}"
        )
    ptr = get_active_pointer(p, active_scope=active_scope)
    if not ptr:
        raise RuntimeError(
            "runtime_param_active pointer 부재 — JSON fallback 없음 (fail closed)"
        )
    version = read_param_version(p, ptr["active_param_version_id"])
    if not version:
        raise RuntimeError(
            f"runtime_param_version 부재: {ptr['active_param_version_id']}"
        )
    return reconstruct_param_dict(version)
