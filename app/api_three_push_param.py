"""POC2 3-PUSH PARAM 적용 UI 연결 API (2026-06-20).

지시문 §5 / §6 — 사용자가 CLI 없이 UI 한 번으로 현재 운영 기준을 OCI 에 적용한다.
POC3-02D-OPS-04 에서 '전달'(OCI JSON 만)로 바뀌었고, POC5-27(PLAN 판정 2026-10-20)부터 다시
**실제 적용**이다 — OCI DB 활성값을 먼저 읽어 같으면 바꾸지 않고, 다르면 OCI 로컬 도구가 PC 값을
그대로 발행 · 활성화한 뒤 다시 읽어 확인한다(`app.three_push_param_activation`).

제공 endpoint:
  GET  /three-push/param/state   — 현재 운영 기준 카드 표시용 read-only state
  POST /three-push/param/apply   — PC 기준 생성 + OCI 적용(읽기 → 같으면 끝 · 다르면 전달 · 발행 · 확인)

frontend response 에 절대 포함하지 않는 것 (지시문 §5.2 / §6):
  param_id / manual_seed / remote path / SSH target / 파일명 / 실행 명령 /
  raw traceback / token / chat_id.

본 모듈은 내부적으로 build_manual_seed_param() / sync wrapper / verify wrapper
를 호출한다. 신규 DB / scheduler / 외부 source 0건. 기존 CLI 스크립트는 유지
(smoke test 용).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
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
# POC5-27 — 마지막 [현재 기준 OCI 적용] 결과(결과 종류 · 단계 · 비교 수 · 시각만 · ID · 경로 없음).
_ACTIVATION_STATUS_PATH = _PARAM_DIR / "param_activation_status_latest.json"
# POC5-27 판정 §5 — 이 프로세스의 적용은 한 번에 하나(두 탭 · 두 번 누름).
_APPLY_LOCK = threading.Lock()
_BUSY_MESSAGE = (
    "이미 적용이 진행 중입니다. 끝난 뒤 이 화면을 다시 열어 결과를 확인하세요."
)

# 사용자 표시용 라벨 — manual_seed 등 내부 source 명을 사용자 친화 문구로.
_DISPLAY_LABEL_MAP = {
    "manual_seed": "기본 운영 기준",
    "baseline_static": "기본 운영 기준",
}


def _format_applied_at(iso_ts: Optional[str]) -> Optional[str]:
    """ISO timestamp → 사용자 표시용 (YYYY-MM-DD HH:MM, KST). 파싱 실패 시 None.

    POC5-27 r2: 상태 파일에서 온 값이 문자열이 아니면(손상 · 배열 · 객체 · 숫자) None — 예외로
    상태 조회 전체가 실패하지 않게 한다.
    """
    if not isinstance(iso_ts, str) or not iso_ts:
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
    # POC5-27: not_applied | delivered_only | active_same | activated | failed | unconfirmed
    #          | busy(적용 진행 중) | verification_required (applying = 화면 전용)
    status: str
    display_label: str
    applied_at: Optional[str]
    oci_verified: bool
    message: str


class ParamApplyResponse(BaseModel):
    # POC5-27: active_same | activated | failed | unconfirmed | busy
    status: str
    display_label: str
    applied_at: Optional[str]
    oci_verified: bool
    message: str
    # POC3-07 (Q4): 표시용 전송 payload SHA-256. 성공 판정은 기존 oci_verified 유지
    #   (sync 스크립트의 OCI verify). hash 는 사용자 표시·대조 참고용일 뿐이다.
    content_sha256: Optional[str] = None
    # POC5-27 PLAN §4 선택 필드 — 이 요청에서 OCI 활성값을 실제로 읽었을 때만 채운다
    #   (비교한 값 수 · 그중 다른 값 수 · 읽은 시각 YYYY-MM-DD HH:MM KST). 못 읽었으면 null.
    compared: Optional[int] = None
    differing: Optional[int] = None
    checked_at: Optional[str] = None


def _latest_param_sha256() -> Optional[str]:
    """PC latest_runtime_param.json 의 SHA-256(표시용). 없으면 None.

    성공 판정에는 쓰지 않는다(기존 oci_verified 유지, Q4). 사용자 대조 참고용.
    """
    try:
        if _LATEST_PATH.exists():
            return hashlib.sha256(_LATEST_PATH.read_bytes()).hexdigest()
    except OSError:
        return None
    return None


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


def latest_param_path() -> Path:
    """PC 운영 기준 JSON 경로(호출 때 모듈 속성 — 테스트 격리를 따른다).

    POC3-02D-OPS-04 항목 6 — 「OCI 운영·적용」 ① '운영 기준 활성' 행이 OCI 활성값과 비교한다.
    """
    return _LATEST_PATH


# ── POC5-27 적용 결과 ─────────────────────────────────────────────────────
_ACTIVATION_RESULTS = frozenset({"active_same", "activated", "failed", "unconfirmed"})
_FAILED_REASON = {
    "build": "운영 기준 생성 실패",
    "precheck": "OCI 활성값을 먼저 읽지 못함",
    "budget": "시간이 모자라 쓰기 전에 멈춤",
    "deliver": "OCI 전달 실패",
    "upload": "적용 도구 전달 실패",
    "error": "적용 준비 중 오류",
    "apply:validate": "OCI 에서 값 검증 실패",
    "apply:precheck": "OCI 에서 활성값 읽기 실패",
    "apply:create": "OCI 에서 기록 실패",
    "apply:candidate": "OCI 에서 후보 검사 실패",
    "apply:activate": "OCI 에서 전환 실패",
    "apply:readback": "다시 읽은 값이 달라 직전 값으로 되돌림",
}


def _activation_message(result: str, stage: str, n: Optional[int]) -> str:
    """결과 종류 → 사용자 문장(ID · 경로 · 원문 오류 없음)."""
    nn = f" ({n}/{n})" if n else ""
    if result == "active_same":
        return f"OCI 활성값이 이미 지금 기준과 같습니다{nn}. 새로 바꾼 것은 없습니다."
    if result == "activated":
        return (
            f"OCI 활성값을 지금 기준으로 바꾸고 다시 읽어 같음을 확인했습니다{nn}. "
            "다음 실행부터 이 기준을 씁니다."
        )
    if result == "unconfirmed":
        return (
            "적용 결과를 확인하지 못했습니다. OCI 활성값이 바뀌었는지 알 수 없습니다."
        )
    if stage == "build":
        return "운영 기준 생성에 실패했습니다. OCI 에는 아무것도 보내지 않았습니다."
    reason = _FAILED_REASON.get(stage, "적용 실패")
    return f"OCI 에 적용하지 못했습니다 ({reason}). 기존 OCI 활성값이 그대로입니다."


def _read_activation_status() -> tuple[str, dict[str, Any]]:
    """param_activation_status_latest.json 의 (상태, payload) — 부재 / 손상 / 정상."""
    if not _ACTIVATION_STATUS_PATH.exists():
        return SYNC_STATE_MISSING, {}
    try:
        data = json.loads(_ACTIVATION_STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("적용 결과 파일 손상: %s", type(e).__name__)
        return SYNC_STATE_CORRUPTED, {}
    # 아는 결과 4종만 — 그 밖의 값은 '기존 값 그대로' 같은 근거 없는 문구로 보이지 않게 손상으로 본다.
    # 화면에 쓰는 칸은 종류까지 본다(배열 · 객체 값이 예외 · 엉뚱한 문구가 되지 않게 · 검증자 F2).
    if not _activation_record_ok(data):
        logger.warning("적용 결과 파일 형식 오류")
        return SYNC_STATE_CORRUPTED, {}
    return SYNC_STATE_OK, data


def _activation_record_ok(data: Any) -> bool:
    """우리가 쓰는 꼴인가 — result ∈ 4종(문자열) · stage 문자열 · n 정수/없음 · completed_at 문자열/없음."""
    if not isinstance(data, dict):
        return False
    result, stage, n = data.get("result"), data.get("stage", ""), data.get("n")
    completed_at = data.get("completed_at")
    return (
        isinstance(result, str)
        and result in _ACTIVATION_RESULTS
        and isinstance(stage, str)
        and (n is None or (isinstance(n, int) and not isinstance(n, bool) and n >= 0))
        and (completed_at is None or isinstance(completed_at, str))
    )


def _write_activation_status(record: dict[str, Any]) -> None:
    """원자적 기록(.tmp → replace). 실패해도 적용 결과 응답은 그대로 돌려준다."""
    try:
        _ACTIVATION_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _ACTIVATION_STATUS_PATH.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(_ACTIVATION_STATUS_PATH)
    except OSError as e:
        logger.warning("적용 결과 기록 실패: %s", type(e).__name__)


@router.get("/state", response_model=ParamStateResponse)
def get_param_state() -> ParamStateResponse:
    """현재 운영 기준 카드 표시용 state (지시문 §5.2).

    표시 항목:
      - display_label (예: '기본 운영 기준')
      - status (POC5-27: 마지막 적용 결과 active_same / activated / failed / unconfirmed ·
        적용 진행 중 busy · 적용 기록 없이 예전 전달 기록만 delivered_only · 없음 not_applied ·
        기록 손상 verification_required)
      - applied_at (사용자 표시용 YYYY-MM-DD HH:MM, 없으면 null)
      - oci_verified (bool)
      - message (사용자용 결과 문장)

    노출하지 않는 항목 (지시문 §5.2):
      param_id / manual_seed / remote path / SSH target / 파일명 /
      raw error / token / chat_id.
    """
    display_label = _read_latest_param_display_label()
    # POC5-27 r2(검증자 F1 전제): 적용이 진행 중이면 기록 파일은 아직 지난 결과다 — 지난 성공을
    # 지금 결과처럼 보이지 않게 '적용 중'으로 답한다(끝나면 기록이 새 결과로 바뀐다).
    if _APPLY_LOCK.locked():
        return ParamStateResponse(
            status="busy",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message=_BUSY_MESSAGE,
        )
    act_state, act = _read_activation_status()
    if act_state == SYNC_STATE_OK:
        result = act["result"]
        return ParamStateResponse(
            status=result,
            display_label=display_label,
            applied_at=_format_applied_at(act.get("completed_at")),
            oci_verified=result in ("active_same", "activated"),
            message=_activation_message(
                result, str(act.get("stage", "")), act.get("n")
            ),
        )
    if act_state == SYNC_STATE_CORRUPTED:
        return ParamStateResponse(
            status="verification_required",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message="운영 상태 파일을 읽지 못했습니다. 한 번 더 적용한 뒤 결과를 확인해 주세요.",
        )
    # POC5-27 판정 §5 — 예전 '전달' 기록은 활성화가 확인된 기록이 아니다(미적용으로 단정하지 않음).
    sync_state, sync_record = _read_sync_status()
    if sync_state == SYNC_STATE_OK and sync_record.get("status") == "success":
        at = _format_applied_at(sync_record.get("completed_at"))
        return ParamStateResponse(
            status="delivered_only",
            display_label=display_label,
            applied_at=at,
            oci_verified=False,
            message=(
                f"이전 전달 기록({at or '시각 모름'}) · 활성화 확인 없음. 지금 OCI 활성값과의 "
                "일치 여부는 위 ① '운영 기준 활성' 행에서 확인하세요."
            ),
        )
    if sync_state == SYNC_STATE_CORRUPTED:
        return ParamStateResponse(
            status="verification_required",
            display_label=display_label,
            applied_at=None,
            oci_verified=False,
            message="운영 상태 파일을 읽지 못했습니다. 한 번 더 적용한 뒤 결과를 확인해 주세요.",
        )
    return ParamStateResponse(
        status="not_applied",
        display_label=display_label,
        applied_at=None,
        oci_verified=False,
        message="아직 [현재 기준 OCI 적용]을 누르지 않았습니다.",
    )


# ── apply 동작 ─────────────────────────────────────────────────────────────
def _create_approved_manual_seed_param() -> str:
    """manual_seed PARAM 생성 → DB active pointer 갱신 (Cutover v1 §4.8).

    - DB: `runtime_param_version` 새 version + `runtime_param_active` pointer 갱신.
    - JSON: history + latest 파일도 함께 write (legacy reference / rollback source).
    - `activated_by="api_param_apply"` — cutover_seed 와 구분.
    - Refactor v1 Q7: DB IO 는 `app.runtime_param_store` 로 이동됨.
    """
    from scripts.create_three_push_runtime_param import (
        _HISTORY_DIR,
        _LATEST_PATH as _CREATE_LATEST_PATH,
    )
    from app.runtime_param_store import (
        activate_param_version,
        create_param_version,
    )
    from app.three_push_runtime_param import (
        build_manual_seed_param,
        write_param_file,
    )

    param = build_manual_seed_param()

    param_version_id, _, _ = create_param_version(param.to_dict())
    activate_param_version(
        param_version_id,
        activated_by="api_param_apply",
    )

    history_path = _HISTORY_DIR / f"{param.param_id}.json"
    write_param_file(history_path, param)
    write_param_file(_CREATE_LATEST_PATH, param)
    return param.param_id


def _run_sync_to_oci(timeout: float = 120.0) -> tuple[bool, str]:
    """sync_three_push_runtime_param.py 의 main 동등 동작을 API process 안에서 수행.

    반환: (success, error_message_internal)
      success — OCI sync + verify 모두 성공 여부
      error_message_internal — 실패 시 내부 로그용 (사용자에게는 노출 X)

    실패 시 기존 OCI latest PARAM 은 건드리지 않는다 (지시문 AC-9). POC5-27 부터 sync 는
    tmp 를 확인한 뒤에만 이름을 바꾼다(확인 스크립트가 없거나 못 올리면 실패). JSON 은 전달
    자료이고 러너의 정본은 OCI DB 활성값이다.
    """
    import subprocess
    import sys

    sync_script = _PROJECT_ROOT / "scripts" / "sync_three_push_runtime_param.py"
    try:
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return False, "sync subprocess timeout"
    except Exception as e:  # noqa: BLE001
        return False, f"sync subprocess error: {type(e).__name__}"

    if result.returncode != 0:
        # stderr 는 로그에도 남기지 않는다 — sync 로그 줄에 SSH 대상 · 원격 경로가 있다(설계 §4).
        logger.warning("sync subprocess returncode=%s", result.returncode)
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
    """[현재 기준 OCI 적용] — PC 기준 생성 + OCI 적용(POC5-27 PLAN §4 · 판정 §1 ~ §5).

    1. PC 운영 기준 생성(기존 그대로 · 코드 기본 14값 · PC DB · PC JSON).
    2. `three_push_param_activation.activate` — OCI 활성값을 먼저 읽고 같으면 끝(OCI 쓰기 0),
       다르면 전달(sync) → OCI 로컬 도구 발행 · 전환 · 다시 읽기 → 결과 4종.
    3. 결과 기록(PC 상태 파일) · ① '운영 기준 활성' 캐시를 실제로 읽은 값으로만 바꾼다.

    응답에 포함하지 않는 것(지시문 §6): param_id / SSH target / remote path / raw output / secret.
    """
    if not _APPLY_LOCK.acquire(blocking=False):
        return ParamApplyResponse(
            status="busy",
            display_label=_read_latest_param_display_label(),
            applied_at=None,
            oci_verified=False,
            message=_BUSY_MESSAGE,
        )
    try:
        return _apply_locked()
    finally:
        _APPLY_LOCK.release()


def _apply_locked() -> ParamApplyResponse:
    from app import oci_startup_status
    from app import three_push_param_activation as activation

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        _create_approved_manual_seed_param()
        # 한 번 읽은 바이트로 값과 SHA-256 을 함께 — OCI 도구가 전달된 파일이 이 내용인지 대조한다.
        raw = _LATEST_PATH.read_bytes()
        pc_dict = json.loads(raw.decode("utf-8"))
        pc_sha256 = hashlib.sha256(raw).hexdigest()
    except Exception as e:  # noqa: BLE001
        logger.error("PARAM 생성 실패: %s", e)
        outcome = activation.Outcome(activation.FAILED, "build")
    else:
        try:
            remote = activation.default_remote(
                deliver=lambda t: _run_sync_to_oci(timeout=t)[0]
            )
            outcome = activation.activate(pc_dict, remote, expect_sha256=pc_sha256)
        except Exception as e:  # noqa: BLE001 - 연결 설정 없음 등 · OCI 에 쓰기 전
            logger.error("PARAM 적용 준비 실패: %s", type(e).__name__)
            outcome = activation.Outcome(activation.FAILED, "precheck")
    completed_at = datetime.now(timezone.utc).isoformat()
    _write_activation_status(
        {
            "result": outcome.result,
            "stage": outcome.stage,
            "n": outcome.n,
            "diff": outcome.diff,
            "started_at": started_at,
            "completed_at": completed_at,
        }
    )
    # 판정 §3 — 실제로 읽은 값만 ① 캐시에 · 확인 불가면 그 상태를 ① 에도.
    oci_startup_status.record_param_apply(
        outcome.values,
        outcome.read_at or completed_at,
        unconfirmed=outcome.result == activation.UNCONFIRMED,
    )
    logger.info("PARAM 적용 결과: %s (%s)", outcome.result, outcome.stage)
    return ParamApplyResponse(
        status=outcome.result,
        display_label=_read_latest_param_display_label(),
        applied_at=_format_applied_at(completed_at),
        oci_verified=outcome.result in (activation.ACTIVE_SAME, activation.ACTIVATED),
        message=_activation_message(outcome.result, outcome.stage, outcome.n),
        content_sha256=_latest_param_sha256(),
        compared=outcome.n if outcome.values is not None else None,
        differing=outcome.diff if outcome.values is not None else None,
        checked_at=(
            _format_applied_at(outcome.read_at) if outcome.values is not None else None
        ),
    )
