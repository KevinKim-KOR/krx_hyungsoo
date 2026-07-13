"""PUSH Content Gap Diagnosis v1 — reproducers (Runtime Evidence v1 정합).

책임:
- PARAM runtime 경로 (실운영) 발송 없이 재현.
- Package fallback 경로 (비교 근거) 발송 없이 재현.

Runtime Evidence DB Connection v1 (2026-07-12) §11 정합화:
- 운영 Runtime 과 동일 `compose_runtime_evidence()` Composer 사용.
- active PARAM 은 legacy JSON 이 아니라 runtime_state.sqlite 를 기준으로 로드.
- Telegram 호출 · runtime status DB write · sent registry write 없음.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.runtime_evidence_composer import compose_runtime_evidence
from app.runtime_param_store import read_active_param_dict
from app.three_push_runner_common import STATE_DIR
from app.three_push_runtime_message_builder import (
    availability_summary,
    build_runtime_message,
)
from app.three_push_runtime_param import from_dict as _param_from_dict

# Runtime Evidence DB Connection v1 §11: active PARAM 은 runtime_state.sqlite 를 SSOT
# 로 사용한다. `PARAM_PATH` 는 legacy JSON 경로로 backward-compat re-export 목적으로만
# 유지되며 (upstream diagnosis 모듈 import 계약), reproducer 내부 로직에서는 사용하지
# 않는다.
PARAM_PATH = STATE_DIR / "params" / "latest_runtime_param.json"


def reproduce_param_runtime(push_kind: str) -> dict[str, Any]:
    """실제 OCI PARAM runtime 이 하는 build 를 발송 없이 재현.

    - active PARAM: runtime_state.sqlite (Cutover v1 이후 SSOT).
    - evidence: compose_runtime_evidence() — 운영 runner 와 동일 Composer.
    - message: build_runtime_message(available_sources=..., extra_notes=...).
    - 부작용 없음: DB write / JSONL append / Telegram 호출 0건.
    """
    result: dict[str, Any] = {
        "applicable": True,
        "param_available": False,
        "param_source": None,
        "param_id": None,
        "push_kind_enabled_in_param": None,
        "message_generated": False,
        "message_text_length": 0,
        "availability_summary": {},
        "content_generation_status": "runtime_unavailable",
        "selection_result_count": 0,
        "contentful_fact_count": 0,
        "unavailable_reasons": {},
        "exact_reason_code": None,
    }
    try:
        param_dict = read_active_param_dict()
    except Exception as e:  # noqa: BLE001
        # DB 부재 / active pointer 부재 / version row 부재 등 fail-closed 경로.
        msg = str(e)
        if "runtime_state DB 부재" in msg:
            result["exact_reason_code"] = "runtime_state_db_missing"
        elif "runtime_param_active pointer 부재" in msg:
            result["exact_reason_code"] = "active_pointer_missing"
        else:
            result["exact_reason_code"] = "param_load_error"
        return result

    try:
        param = _param_from_dict(param_dict)
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "param_validation_error"
        return result

    result["param_available"] = True
    result["param_source"] = param.param_source
    result["param_id"] = param.param_id
    enabled = param.is_push_kind_enabled(push_kind)
    result["push_kind_enabled_in_param"] = enabled
    if not enabled:
        result["exact_reason_code"] = "push_kind_not_in_param"
        result["content_generation_status"] = "runtime_unavailable"
        return result

    try:
        evidence = compose_runtime_evidence(push_kind)
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "runtime_evidence_error"
        return result

    try:
        text = build_runtime_message(
            push_kind=push_kind,
            param=param,
            available_sources=evidence.available_sources,
            extra_notes=evidence.extra_notes,
        )
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "runtime_message_build_error"
        return result

    result["message_generated"] = True
    result["message_text_length"] = len(text)
    result["availability_summary"] = availability_summary(evidence.available_sources)
    result["selection_result_count"] = evidence.diagnostics.get(
        "selection_result_count", 0
    )
    result["contentful_fact_count"] = evidence.diagnostics.get(
        "contentful_fact_count", 0
    )
    result["unavailable_reasons"] = evidence.diagnostics.get("unavailable_reasons", {})
    if result["contentful_fact_count"] > 0:
        result["content_generation_status"] = "content_ready"
        result["exact_reason_code"] = None
    else:
        result["content_generation_status"] = "data_insufficient"
        result["exact_reason_code"] = "no_contentful_fact"
    return result


def reproduce_package_fallback(push_kind: str) -> dict[str, Any]:
    """PC 에서 만든 package 를 읽기 전용으로 조사.

    OCI 에서는 신규 package 생성·복사·동기화 없이 존재 여부만 확인 (기존 계약).
    package 부재 시 not_applicable (실패 아님).
    """
    from scripts.three_push_oci_helpers import (
        extract_message_text,
        load_manifest,
        load_package,
        package_dir,
    )

    result: dict[str, Any] = {
        "applicable": True,
        "package_dir_exists": False,
        "manifest_loaded": False,
        "package_loaded": False,
        "package_id": None,
        "package_asof_date": None,
        "package_generation_status": None,
        "message_text_length": 0,
        "content_generation_status": "runtime_unavailable",
        "selection_result_count": 0,
        "exact_reason_code": None,
    }
    pkg_dir: Path = package_dir()
    if not pkg_dir.exists():
        result["applicable"] = False
        result["exact_reason_code"] = "package_dir_missing"
        return result
    result["package_dir_exists"] = True
    try:
        manifest = load_manifest(pkg_dir)
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "manifest_load_error"
        return result
    result["manifest_loaded"] = True
    if push_kind not in manifest.get("packages", {}):
        result["applicable"] = False
        result["exact_reason_code"] = "push_kind_not_in_manifest"
        return result
    try:
        package = load_package(pkg_dir, push_kind, manifest)
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "package_load_error"
        return result
    result["package_loaded"] = True
    result["package_id"] = package.get("package_id", "")
    result["package_asof_date"] = package.get("asof_date") or package.get("data_cutoff")
    gs: Optional[str] = (package.get("generation_status") or {}).get("status")
    result["package_generation_status"] = gs
    if gs == "failed":
        result["content_generation_status"] = "failed"
        result["exact_reason_code"] = "failed_generation_status"
        return result
    try:
        text = extract_message_text(package, push_kind)
    except Exception:  # noqa: BLE001
        result["exact_reason_code"] = "message_text_missing"
        return result
    result["message_text_length"] = len(text)
    result["content_generation_status"] = "content_ready"
    generation_status = package.get("generation_status") or {}
    result["selection_result_count"] = int(generation_status.get("selected_count") or 0)
    return result
