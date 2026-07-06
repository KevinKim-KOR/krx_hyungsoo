"""PUSH Content Gap Diagnosis v1 — reproducers (2026-07-05, FIX r2 분리).

책임:
- PARAM runtime 경로 (실운영) 발송 없이 재현.
- Package fallback 경로 (비교 근거) 발송 없이 재현.

지시문 §4, §9 · Q2 (b) 확정: 기존 PUSH 발송 코드에서 pure helper 만 재사용.
subprocess / --dry-run 미사용. Telegram / 외부 API 호출 0건.
지시문 Q1 확정: `available_sources` 는 실운영과 동일하게 `None` 을 전달.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.three_push_runner_common import STATE_DIR
from app.three_push_runtime_message_builder import (
    availability_summary,
    build_runtime_message,
)
from app.three_push_runtime_param import read_param_file

PARAM_PATH = STATE_DIR / "params" / "latest_runtime_param.json"


def reproduce_param_runtime(push_kind: str) -> dict[str, Any]:
    """실제 OCI PARAM runtime 이 하는 build 를 발송 없이 재현.

    scripts/run_three_push_runtime_oci.py:169-181 그대로 —
    available_sources=None (실제 운영과 동일). Q1 확정본에 따라 주입하지 않음.
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
        "exact_reason_code": None,
    }
    if not PARAM_PATH.exists():
        result["exact_reason_code"] = "missing_latest_param"
        return result
    try:
        param = read_param_file(PARAM_PATH)
    except Exception:
        result["exact_reason_code"] = "param_load_error"
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

    # 실제 운영과 동일: available_sources=None. 축약 메시지 발생.
    try:
        text = build_runtime_message(
            push_kind=push_kind,
            param=param,
            available_sources=None,
        )
    except Exception:
        result["exact_reason_code"] = "runtime_message_build_error"
        return result

    result["message_generated"] = True
    result["message_text_length"] = len(text)
    result["availability_summary"] = availability_summary(None)
    # available_sources=None → 모든 source unavailable → 축약 메시지.
    result["selection_result_count"] = 0
    result["content_generation_status"] = "data_insufficient"
    result["exact_reason_code"] = "runtime_available_sources_not_supplied"
    return result


def reproduce_package_fallback(push_kind: str) -> dict[str, Any]:
    """PC 에서 만든 package 를 읽기 전용으로 조사.

    OCI 에서는 신규 package 생성·복사·동기화 없이 존재 여부만 확인 (Q1 확정본).
    package 부재 시 not_applicable (실패 아님).
    """
    # 지시문 §6.2 대로 기존 pure helper 직접 재사용.
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
    except Exception:
        result["exact_reason_code"] = "manifest_load_error"
        return result
    result["manifest_loaded"] = True
    if push_kind not in manifest.get("packages", {}):
        result["applicable"] = False
        result["exact_reason_code"] = "push_kind_not_in_manifest"
        return result
    try:
        package = load_package(pkg_dir, push_kind, manifest)
    except Exception:
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
    except Exception:
        result["exact_reason_code"] = "message_text_missing"
        return result
    result["message_text_length"] = len(text)
    result["content_generation_status"] = "content_ready"
    generation_status = package.get("generation_status") or {}
    result["selection_result_count"] = int(generation_status.get("selected_count") or 0)
    return result
