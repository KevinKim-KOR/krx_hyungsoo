"""PARAM / Runtime State DB Cutover v1 — seed / verify CLI.

허용 서브커맨드:
  seed    latest_runtime_param.json / oci_runtime_status_latest.json /
          oci_runtime_sent_registry.json 을 runtime_state.sqlite 로 seed.
  verify  DB 존재 / 5 table / active pointer / 재구성 결과 검증.

계약 (지시문 §12 sanitised 원칙 준수):
- Telegram 호출 없음. 외부 API 호출 없음. OCI SSH 자동화 없음.
- market_data.sqlite 미변경. decision_evidence.sqlite 미변경.
- available_sources=None 미변경.
- JSON fallback 없음. 실패 시 stderr 로 fail-closed 사유 출력.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app import runtime_state_db as db_helper  # noqa: E402
from app.runtime_execution_status_store import (  # noqa: E402
    insert_status_from_record,
    latest_execution_status,
)
from app.runtime_param_store import (  # noqa: E402
    activate_param_version,
    create_param_version,
    get_active_pointer,
    read_active_param_dict,
)
from app.runtime_sent_registry_store import (  # noqa: E402
    count as registry_count,
    insert as registry_insert,
)
from app.three_push_runtime_param import (  # noqa: E402
    read_param_file,
    validate_param_dict,
)

_LATEST_PARAM_JSON = Path("state/three_push/params/latest_runtime_param.json")
_STATUS_JSON = Path("state/three_push/oci_runtime_status_latest.json")
_REGISTRY_JSON = Path("state/three_push/oci_runtime_sent_registry.json")

_ACTIVATED_BY_SEED = "cutover_seed"

# FIX r1 (Refactor v1) Q6: 오염된 active pointer 를 READY 로 통과시키지 않기 위한 marker set.
# runtime state DB 의 active_pointer.activated_by 값이 아래에 포함되면 verify overall=NOT_READY.
_TEST_ACTIVATED_BY_MARKERS = frozenset({"isolation_test", "test"})


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_seed(args: argparse.Namespace) -> int:
    db_path = Path(args.db_path or db_helper.DEFAULT_DB_PATH)
    result: dict = {
        "command": "seed",
        "db_path": str(db_path),
        "steps": {},
        "warnings": [],
    }

    # 1. PARAM seed
    if not _LATEST_PARAM_JSON.exists():
        result["steps"]["param"] = {"status": "failed", "reason": "latest_param_absent"}
        _emit(result)
        return 2
    try:
        param = read_param_file(_LATEST_PARAM_JSON)
    except Exception as e:
        result["steps"]["param"] = {"status": "failed", "reason": str(e)[:400]}
        _emit(result)
        return 2

    param_version_id, source_hash, created_new = create_param_version(
        param.to_dict(), db_path=db_path
    )

    ptr_before = get_active_pointer(db_path)
    pointer_action = "no_op"
    if ptr_before is None:
        activate_param_version(
            param_version_id,
            activated_at=_now_utc_iso(),
            activated_by=_ACTIVATED_BY_SEED,
            db_path=db_path,
        )
        pointer_action = "created"
    elif ptr_before["active_param_version_id"] != param_version_id:
        activate_param_version(
            param_version_id,
            activated_at=_now_utc_iso(),
            activated_by=_ACTIVATED_BY_SEED,
            db_path=db_path,
        )
        pointer_action = "moved"
        result["warnings"].append(
            {
                "kind": "active_pointer_moved",
                "previous_param_version_id": ptr_before["active_param_version_id"],
                "new_param_version_id": param_version_id,
            }
        )

    result["steps"]["param"] = {
        "status": "ok",
        "param_version_id": param_version_id,
        "source_hash_sha256": source_hash,
        "created_new_version": created_new,
        "pointer_action": pointer_action,
    }

    # 2. runtime status seed (optional presence)
    if _STATUS_JSON.exists():
        try:
            status_record = json.loads(_STATUS_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            result["steps"]["status"] = {"status": "failed", "reason": str(e)[:400]}
            _emit(result)
            return 3
        try:
            run_id = insert_status_from_record(
                status_record, db_path=db_path, inserted_at=_now_utc_iso()
            )
            result["steps"]["status"] = {
                "status": "ok",
                "seeded_run_id": run_id,
                "absence_recorded": False,
            }
        except Exception as e:
            result["steps"]["status"] = {"status": "failed", "reason": str(e)[:400]}
            _emit(result)
            return 3
    else:
        result["steps"]["status"] = {
            "status": "ok",
            "seeded_run_id": None,
            "absence_recorded": True,
        }

    # 3. sent registry seed (optional presence)
    if _REGISTRY_JSON.exists():
        try:
            registry = json.loads(_REGISTRY_JSON.read_text(encoding="utf-8"))
        except Exception as e:
            result["steps"]["sent_registry"] = {
                "status": "failed",
                "reason": str(e)[:400],
            }
            _emit(result)
            return 4
        if not isinstance(registry, dict):
            result["steps"]["sent_registry"] = {
                "status": "failed",
                "reason": f"registry not dict: {type(registry).__name__}",
            }
            _emit(result)
            return 4
        seeded = 0
        conflicts = 0
        now = _now_utc_iso()
        for key, entry in registry.items():
            if not isinstance(entry, dict):
                result["warnings"].append(
                    {"kind": "registry_entry_not_dict", "key": key}
                )
                continue
            ok = registry_insert(
                db_path,
                push_kind=str(entry.get("push_kind", "")),
                param_id=str(entry.get("param_id", "")),
                runtime_date_kst=str(entry.get("runtime_date_kst", "")),
                sent_at_utc=str(entry.get("sent_at_utc", "")),
                inserted_at=now,
                on_conflict="ignore",
            )
            if ok:
                seeded += 1
            else:
                conflicts += 1
                result["warnings"].append(
                    {"kind": "registry_conflict_ignored", "key": key}
                )
        result["steps"]["sent_registry"] = {
            "status": "ok",
            "input_entries": len(registry),
            "inserted": seeded,
            "conflicts_ignored": conflicts,
        }
    else:
        result["steps"]["sent_registry"] = {
            "status": "ok",
            "input_entries": 0,
            "inserted": 0,
            "empty_registry_start": True,
        }

    # 4. DB summary.
    result["db"] = {
        "tables": db_helper.list_tables(db_path),
        "integrity_check": db_helper.integrity_check(db_path),
        "row_counts": db_helper.table_row_counts(db_path),
    }
    _emit(result)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    db_path = Path(args.db_path or db_helper.DEFAULT_DB_PATH)
    result: dict = {
        "command": "verify",
        "db_path": str(db_path),
        "checks": {},
    }
    if not db_path.exists():
        result["checks"]["db_exists"] = False
        result["overall"] = "FAIL_CLOSED"
        _emit(result)
        return 2
    result["checks"]["db_exists"] = True
    tables = db_helper.list_tables(db_path)
    result["checks"]["tables_present"] = sorted(db_helper.TABLE_NAMES)
    result["checks"]["tables_observed"] = tables
    missing = [t for t in db_helper.TABLE_NAMES if t not in tables]
    result["checks"]["missing_tables"] = missing
    result["checks"]["integrity_check"] = db_helper.integrity_check(db_path)
    counts = db_helper.table_row_counts(db_path)
    result["checks"]["row_counts"] = counts

    ptr = get_active_pointer(db_path)
    result["checks"]["active_pointer_exists"] = ptr is not None
    if ptr:
        result["checks"]["active_pointer"] = ptr

    # DB read + reconstruct + validate.
    reconstruct_ok = False
    reconstruct_error = None
    reconstructed_dict: dict = {}
    try:
        reconstructed_dict = read_active_param_dict(db_path)
        errors = validate_param_dict(reconstructed_dict)
        reconstruct_ok = not errors
        if errors:
            reconstruct_error = "; ".join(errors)
    except Exception as e:
        reconstruct_error = str(e)[:400]
    result["checks"]["reconstruct_active_param_ok"] = reconstruct_ok
    if reconstruct_error:
        result["checks"]["reconstruct_active_param_error"] = reconstruct_error

    # semantic match: DB reconstruction vs current latest JSON.
    if _LATEST_PARAM_JSON.exists() and reconstruct_ok:
        try:
            json_data = json.loads(_LATEST_PARAM_JSON.read_text(encoding="utf-8"))
            json_hash = db_helper.canonical_json_sha256(json_data)
            db_hash = db_helper.canonical_json_sha256(reconstructed_dict)
            result["checks"]["canonical_hash_json"] = json_hash
            result["checks"]["canonical_hash_db_reconstruction"] = db_hash
            result["checks"]["semantic_match_with_latest_json"] = json_hash == db_hash
        except Exception as e:
            result["checks"]["semantic_match_error"] = str(e)[:400]

    latest = latest_execution_status(db_path)
    result["checks"]["latest_execution_status_present"] = latest is not None
    if latest:
        result["checks"]["latest_execution_status_summary"] = {
            "run_id": latest["run_id"],
            "push_kind": latest["push_kind"],
            "status": latest["status"],
            "runtime_date_kst": latest["runtime_date_kst"],
        }

    result["checks"]["sent_registry_count"] = registry_count(db_path)
    result["checks"]["json_fallback_used"] = False

    # FIX r1 (Q3 · Q6): 판정 강화. 위험 신호 발견 시 NOT_READY + readiness_errors.
    readiness_errors: list[str] = []
    overall = "READY"
    if missing:
        overall = "NOT_READY"
        readiness_errors.append("missing_tables")
    if not result["checks"]["active_pointer_exists"]:
        overall = "NOT_READY"
        readiness_errors.append("active_pointer_missing")
    if not reconstruct_ok:
        overall = "NOT_READY"
        readiness_errors.append("reconstruct_active_param_failed")
    # test marker contamination.
    if ptr and ptr.get("activated_by") in _TEST_ACTIVATED_BY_MARKERS:
        overall = "NOT_READY"
        readiness_errors.append(
            f"active_pointer_activated_by_test_marker:{ptr.get('activated_by')}"
        )
    # semantic divergence (local DB reconstruction vs local latest JSON).
    sem = result["checks"].get("semantic_match_with_latest_json")
    if sem is False:
        overall = "NOT_READY"
        readiness_errors.append("db_reconstruction_diverges_from_latest_json")
    result["readiness_errors"] = readiness_errors
    result["overall"] = overall
    _emit(result)
    return 0 if overall == "READY" else 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PARAM / Runtime State DB Cutover — seed / verify CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_seed = sub.add_parser("seed", help="JSON → runtime_state.sqlite seed")
    p_seed.add_argument(
        "--db-path", default=None, help="override runtime_state DB path"
    )
    p_seed.set_defaults(func=cmd_seed)

    p_verify = sub.add_parser("verify", help="runtime_state.sqlite active PARAM 검증")
    p_verify.add_argument(
        "--db-path", default=None, help="override runtime_state DB path"
    )
    p_verify.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
