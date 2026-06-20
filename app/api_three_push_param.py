"""POC2 3-PUSH PARAM 적용 UI 연결 API (2026-06-20).

지시문 §5 / §6 — 사용자가 CLI 없이 UI 한 번으로 현재 운영 기준을 OCI 에 적용.

제공 endpoint:
  GET  /three-push/param/state   — 현재 운영 기준 카드 표시용 read-only state
  POST /three-push/param/apply   — 단일 동작으로 create + approve + sync + verify

frontend response 에 절대 포함하지 않는 것 (지시문 §5.2 / §6):
  param_id / manual_seed / remote path / SSH target / 파일명 / 실행 명령 /
  raw traceback / token / chat_id.

본 모듈은 내부적으로 build_manual_seed_param() / sync wrapper / verify wrapper
를 호출한다. 신규 DB / scheduler / 외부 source 0건. 기존 CLI 스크립트는 유지
(smoke test 용).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/three-push/param", tags=["three-push-param"])

# 경로 상수 — sync 스크립트와 동일한 위치를 사용.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PARAM_DIR = _PROJECT_ROOT / "state" / "three_push" / "params"
_LATEST_PATH = _PARAM_DIR / "latest_runtime_param.json"
_SYNC_STATUS_PATH = _PARAM_DIR / "param_sync_status_latest.json"

# 사용자 표시용 라벨 — manual_seed 등 내부 source 명을 사용자 친화 문구로.
_DISPLAY_LABEL_MAP = {
    "manual_seed": "기본 운영 기준",
    "baseline_static": "기본 운영 기준",
}


def _format_applied_at(iso_ts: Optional[str]) -> Optional[str]:
    """ISO timestamp → 사용자 표시용 (YYYY-MM-DD HH:MM, KST). 파싱 실패 시 None."""
    if not iso_ts:
        return None
    try:
        s = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        from datetime import timedelta

        dt_kst = dt.astimezone(timezone(timedelta(hours=9)))
        return dt_kst.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None


# ── 응답 모델 (지시문 §6 데이터 계약) ───────────────────────────────────────
class ParamStateResponse(BaseModel):
    status: str  # not_applied | applying | applied | failed | verification_required
    display_label: str
    applied_at: Optional[str]
    oci_verified: bool
    message: str


class ParamApplyResponse(BaseModel):
    status: str  # applied | failed | verification_required
    display_label: str
    applied_at: Optional[str]
    oci_verified: bool
    message: str


# ── state 읽기 ─────────────────────────────────────────────────────────────
def _read_latest_param_display_label() -> str:
    """latest PARAM 파일에서 사용자 표시 라벨 추출. raw param_source 노출 0건.

    파일 부재 / 손상은 구분된 fallback:
      - 부재: "미적용" (사용자에게 의미 있는 상태 — 아직 한 번도 적용 안 됨)
      - 손상: "기본 운영 기준" + logger.warning (운영 상태 손상 감지가 로그에 남음)
    """
    if not _LATEST_PATH.exists():
        return "미적용"
    try:
        data = json.loads(_LATEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("latest PARAM 파일 손상: %s", type(e).__name__)
        return "기본 운영 기준"
    src = data.get("param_source") if isinstance(data, dict) else None
    if isinstance(src, str):
        return _DISPLAY_LABEL_MAP.get(src, "기본 운영 기준")
    return "기본 운영 기준"


# sync status 파일 상태 — 부재 / 손상 / 정상 3분리.
SYNC_STATE_MISSING = "missing"
SYNC_STATE_CORRUPTED = "corrupted"
SYNC_STATE_OK = "ok"


def _read_sync_status() -> tuple[str, dict[str, Any]]:
    """param_sync_status_latest.json 의 (상태, payload) 반환.

    상태:
      - SYNC_STATE_MISSING — 파일 부재 (한 번도 sync 안 됨)
      - SYNC_STATE_CORRUPTED — JSON parse 실패 또는 dict 가 아님 (운영 상태 손상)
      - SYNC_STATE_OK — 정상 read

    raw error / SSH target / remote path 는 응답에 노출하지 않고 호출자가
    사용자 친화 dict 로 변환한다.
    """
    if not _SYNC_STATUS_PATH.exists():
        return SYNC_STATE_MISSING, {}
    try:
        data = json.loads(_SYNC_STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("sync status 파일 손상: %s", type(e).__name__)
        return SYNC_STATE_CORRUPTED, {}
    if not isinstance(data, dict):
        logger.warning(
            "sync status JSON 형식 오류: 최상위가 dict 아님 (%s)", type(data).__name__
        )
        return SYNC_STATE_CORRUPTED, {}
    return SYNC_STATE_OK, data


def _status_to_user_response(sync_record: dict[str, Any]) -> dict[str, Any]:
    """sync_status 레코드를 사용자용 응답으로 변환. raw 식별자/경로 마스킹."""
    raw_status = sync_record.get("status")
    if raw_status == "success":
        return {
            "status": "applied",
            "applied_at": _format_applied_at(sync_record.get("completed_at")),
            "oci_verified": (sync_record.get("verify_status") == "success"),
            "message": "OCI 반영이 완료되었습니다.",
        }
    if raw_status == "failed":
        return {
            "status": "failed",
            "applied_at": _format_applied_at(sync_record.get("completed_at")),
            "oci_verified": False,
            "message": (
                "OCI 반영에 실패했습니다. 기존 적용 기준은 유지됩니다. "
                "운영 상세에서 마지막 확인 시각을 확인하세요."
            ),
        }
    return {
        "status": "not_applied",
        "applied_at": None,
        "oci_verified": False,
        "message": "아직 OCI 에 적용되지 않았습니다.",
    }


@router.get("/state", response_model=ParamStateResponse)
def get_param_state() -> ParamStateResponse:
    """현재 운영 기준 카드 표시용 state (지시문 §5.2).

    표시 항목:
      - display_label (예: '기본 운영 기준')
      - status (not_applied / applied / failed / verification_required)
      - applied_at (사용자 표시용 YYYY-MM-DD HH:MM, 없으면 null)
      - oci_verified (bool)
      - message (사용자용 결과 문장)

    노출하지 않는 항목 (지시문 §5.2):
      param_id / manual_seed / remote path / SSH target / 파일명 /
      raw error / token / chat_id.
    """
    display_label = _read_latest_param_display_label()
    sync_state, sync_record = _read_sync_status()
    if sync_state == SYNC_STATE_MISSING:
        return ParamStateResponse(
            status="not_applied",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message="아직 OCI 에 적용되지 않았습니다.",
        )
    if sync_state == SYNC_STATE_CORRUPTED:
        # 손상은 부재와 구분 — 사용자에게 확인 필요 상태 표시.
        return ParamStateResponse(
            status="verification_required",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message=(
                "운영 상태 파일을 읽지 못했습니다. 한 번 더 적용 후 결과를 "
                "확인해 주세요."
            ),
        )
    summary = _status_to_user_response(sync_record)
    return ParamStateResponse(
        status=summary["status"],
        display_label=display_label,
        applied_at=summary["applied_at"],
        oci_verified=summary["oci_verified"],
        message=summary["message"],
    )


# ── apply 동작 ─────────────────────────────────────────────────────────────
def _create_approved_manual_seed_param() -> str:
    """manual_seed PARAM 생성 후 latest_runtime_param.json 으로 승격.

    create_three_push_runtime_param.py 의 main 동작과 동등 — build_manual_seed_param()
    후 latest 로 쓴다. raw param_id 는 호출자가 사용자에게 노출하지 않는다.
    """
    from scripts.create_three_push_runtime_param import (
        _HISTORY_DIR,
        _LATEST_PATH as _CREATE_LATEST_PATH,
    )
    from app.three_push_runtime_param import (
        build_manual_seed_param,
        write_param_file,
    )

    param = build_manual_seed_param()
    history_path = _HISTORY_DIR / f"{param.param_id}.json"
    write_param_file(history_path, param)
    write_param_file(_CREATE_LATEST_PATH, param)
    return param.param_id


def _run_sync_to_oci() -> tuple[bool, str]:
    """sync_three_push_runtime_param.py 의 main 동등 동작을 API process 안에서 수행.

    반환: (success, error_message_internal)
      success — OCI sync + verify 모두 성공 여부
      error_message_internal — 실패 시 내부 로그용 (사용자에게는 노출 X)

    실패 시 기존 OCI latest PARAM 은 건드리지 않는다 (지시문 AC-9). sync 스크립트는
    이미 atomic rename + verify 후 교체이므로 verify 실패 시 자동 보호됨.
    """
    import subprocess
    import sys

    sync_script = _PROJECT_ROOT / "scripts" / "sync_three_push_runtime_param.py"
    try:
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, "sync subprocess timeout"
    except Exception as e:  # noqa: BLE001
        return False, f"sync subprocess error: {type(e).__name__}"

    if result.returncode != 0:
        # raw stderr 는 내부 로그용만 — 응답에 포함하지 않는다.
        logger.warning(
            "sync subprocess returncode=%s stderr=%s",
            result.returncode,
            (result.stderr or "")[:500],
        )
        return False, f"sync returncode={result.returncode}"

    # sync_status_latest.json 확인.
    sync_state, record = _read_sync_status()
    if sync_state != SYNC_STATE_OK:
        return False, f"sync_status_{sync_state}"
    if record.get("status") == "success" and record.get("verify_status") == "success":
        return True, ""
    return False, f"sync status={record.get('status')!r}"


@router.post("/apply", response_model=ParamApplyResponse)
def apply_param_to_oci() -> ParamApplyResponse:
    """단일 동작으로 PARAM 생성 + 승인 + OCI sync + verify (지시문 §5.3 / AC-6).

    내부 순서:
      1. manual_seed PARAM 생성 후 latest 로 승격
      2. sync_three_push_runtime_param 호출 (scp + atomic rename + verify)
      3. sync_status_latest.json 확인 후 사용자 응답 구성

    실패해도 기존 OCI latest PARAM 은 보호된다 (AC-9 — sync 스크립트가 verify
    실패 시 .tmp 파일만 남기고 atomic rename 을 건너뛴다).

    응답에 포함하지 않는 것 (지시문 §6):
      param_id / SSH target / remote path / raw subprocess output / secret.
    """
    display_label = _read_latest_param_display_label()
    try:
        _create_approved_manual_seed_param()
    except Exception as e:  # noqa: BLE001
        logger.error("PARAM 생성 실패: %s", e)
        return ParamApplyResponse(
            status="failed",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message=(
                "운영 기준 생성에 실패했습니다. 기존 적용 기준은 유지됩니다. "
                "운영 상세에서 마지막 확인 시각을 확인하세요."
            ),
        )

    # 생성 직후 display_label 재계산 (param_source 변경 가능성 대비).
    display_label = _read_latest_param_display_label()

    success, _internal_err = _run_sync_to_oci()
    _sync_state, sync_record = _read_sync_status()
    summary = _status_to_user_response(sync_record)
    if not success:
        summary["status"] = "failed"
        summary["oci_verified"] = False
        summary["message"] = (
            "OCI 반영에 실패했습니다. 기존 적용 기준은 유지됩니다. "
            "운영 상세에서 마지막 확인 시각을 확인하세요."
        )

    return ParamApplyResponse(
        status=summary["status"],
        display_label=display_label,
        applied_at=summary["applied_at"],
        oci_verified=summary["oci_verified"],
        message=summary["message"],
    )
