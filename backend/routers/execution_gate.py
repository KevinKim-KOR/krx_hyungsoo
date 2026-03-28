"""Execution Gate, Emergency Stop, Approval, Window, and Preflight APIs."""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils import KST, BASE_DIR, STATE_DIR, logger

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
EXECUTION_GATE_FILE = STATE_DIR / "execution_gate.json"
VALID_MODES = ["MOCK_ONLY", "DRY_RUN", "REAL_ENABLED"]
DEFAULT_GATE = {
    "schema": "EXECUTION_GATE_V1",
    "mode": "MOCK_ONLY",
    "updated_at": None,
    "updated_by": None,
    "reason": "Default (no gate file)",
}

APPROVALS_DIR = STATE_DIR / "approvals"
APPROVALS_FILE = APPROVALS_DIR / "real_enable_approvals.jsonl"
TICKETS_DIR = STATE_DIR / "tickets"
RECEIPTS_FILE = TICKETS_DIR / "ticket_receipts.jsonl"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"

WINDOWS_DIR = STATE_DIR / "real_enable_windows"
WINDOWS_FILE = WINDOWS_DIR / "real_enable_windows.jsonl"

ALLOWLIST_FILE = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
PREFLIGHT_DIR = BASE_DIR / "reports" / "tickets" / "preflight"

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter()

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> List[Dict]:
    """JSONL 파일 읽기"""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


def get_current_gate() -> Dict:
    """현재 Gate 상태 조회 (파일 없으면 Default)"""
    if not EXECUTION_GATE_FILE.exists():
        return DEFAULT_GATE.copy()
    try:
        data = json.loads(EXECUTION_GATE_FILE.read_text(encoding="utf-8"))
        return data
    except Exception:
        return DEFAULT_GATE.copy()


def get_emergency_stop_status() -> Dict:
    """Emergency Stop 상태 조회"""
    if not EMERGENCY_STOP_FILE.exists():
        return {
            "enabled": False,
            "updated_at": None,
            "updated_by": None,
            "reason": None,
        }
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data
    except Exception:
        return {
            "enabled": False,
            "updated_at": None,
            "updated_by": None,
            "reason": None,
        }


def get_latest_approval() -> Optional[Dict]:
    """최신 Approval 조회 (Append-only에서 상태 합성)"""
    if not APPROVALS_FILE.exists():
        return None

    approvals = read_jsonl(APPROVALS_FILE)
    if not approvals:
        return None

    # approval_id별로 이벤트 병합 (append-only 로그이므로 최신 우선)
    merged: Dict[str, Dict] = {}
    for event in approvals:
        aid = event.get("approval_id")
        if not aid:
            continue

        if aid not in merged:
            merged[aid] = event.copy()
        else:
            # 같은 approval_id의 새 이벤트: keys, status 업데이트
            if "keys" in event:
                merged[aid]["keys"] = event["keys"]
            if "status" in event:
                merged[aid]["status"] = event["status"]

    if not merged:
        return None

    # 정렬: APPROVED 우선, 그 다음 requested_at 최신
    sorted_approvals = sorted(
        merged.values(),
        key=lambda x: (
            x.get("status") == "APPROVED",  # APPROVED가 True(1)로 뒤에 정렬
            x.get("requested_at", ""),
        ),
        reverse=True,
    )

    return sorted_approvals[0] if sorted_approvals else None


def get_active_window() -> Optional[Dict]:
    """현재 ACTIVE 상태인 Window 조회 (Synthesized)"""
    if not WINDOWS_FILE.exists():
        return None

    events = read_jsonl(WINDOWS_FILE)
    if not events:
        return None

    # window_id별로 최신 상태 계산
    windows: Dict[str, Dict] = {}
    for event in events:
        wid = event.get("window_id")
        if wid not in windows:
            windows[wid] = event.copy()
        else:
            # 이벤트 타입에 따라 상태 업데이트
            if event.get("event") == "REVOKE":
                windows[wid]["status"] = "REVOKED"
            elif event.get("event") == "CONSUME":
                windows[wid]["real_executions_used"] = (
                    windows[wid].get("real_executions_used", 0) + 1
                )

    # ACTIVE window 찾기 (최신 우선)
    now = datetime.now(KST)
    active_windows = []

    for wid, window in windows.items():
        # 만료 체크
        expires_at = datetime.fromisoformat(window.get("expires_at", "2000-01-01"))
        if expires_at < now:
            window["status"] = "EXPIRED"

        # 소진 체크
        used = window.get("real_executions_used", 0)
        max_exec = window.get("max_real_executions", 1)
        if used >= max_exec and window.get("status") not in [
            "REVOKED",
            "EXPIRED",
        ]:
            window["status"] = "CONSUMED"

        if window.get("status") == "ACTIVE":
            active_windows.append(window)

    if not active_windows:
        return None

    # 최신 생성된 ACTIVE window 반환
    return max(active_windows, key=lambda w: w.get("created_at", ""))


def check_reconcile_deps() -> dict:
    """Check reconcile dependencies"""
    import sys

    result = {
        "python_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}"
            f".{sys.version_info.micro}"
        ),
        "python_ok": sys.version_info >= (3, 10),
        "pandas_installed": False,
        "pyarrow_installed": False,
        "required_missing": [],
    }

    try:
        import pandas

        result["pandas_installed"] = True
        result["pandas_version"] = pandas.__version__
    except ImportError:
        result["required_missing"].append("pandas")

    try:
        import pyarrow

        result["pyarrow_installed"] = True
        result["pyarrow_version"] = pyarrow.__version__
    except ImportError:
        result["required_missing"].append("pyarrow")

    result["all_deps_ok"] = len(result["required_missing"]) == 0 and result["python_ok"]
    return result


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GateUpdate(BaseModel):
    mode: str
    reason: str


class EmergencyStopUpdate(BaseModel):
    enabled: bool
    operator_id: str = "local_operator"
    reason: str = ""


class ApprovalRequest(BaseModel):
    requested_by: str
    reason: str


class KeyApproval(BaseModel):
    approval_id: str
    key_id: str
    approver_id: str


class WindowRequest(BaseModel):
    reason: str
    ttl_seconds: int = 600


class WindowRevoke(BaseModel):
    window_id: str
    reason: str = ""


class PreflightRequest(BaseModel):
    request_id: str
    request_type: str
    payload: dict = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/execution_gate", summary="Execution Gate 상태 조회")
def get_execution_gate():
    """현재 Gate 상태 반환 (Envelope)"""
    gate = get_current_gate()
    return {
        "status": "ready",
        "schema": "EXECUTION_GATE_V1",
        "asof": datetime.now(KST).isoformat(),
        "data": gate,
        "error": None,
    }


@router.post("/api/execution_gate", summary="Execution Gate 모드 변경")
def update_execution_gate(data: GateUpdate):
    """
    Gate 모드 변경

    Transition Rule:
    - MOCK_ONLY <-> DRY_RUN: 허용
    - Any -> MOCK_ONLY: 즉시 허용 (Emergency Stop)
    - Any -> REAL_ENABLED: 400 Bad Request (C-P.4에서 금지)
    """
    logger.info(f"Gate 변경 요청: {data.mode}")

    # Validation
    if data.mode not in VALID_MODES:
        return JSONResponse(
            status_code=400,
            content={
                "result": "FAIL",
                "message": f"Invalid mode. Must be one of {VALID_MODES}",
            },
        )

    # C-P.7: REAL_ENABLED 허용 (Worker에서 Shadow로 강제 처리됨)
    if data.mode == "REAL_ENABLED":
        logger.warning("REAL_ENABLED mode requested - Allowed for SHADOW mode (C-P.7)")
        # Note: Worker will force SHADOW processing, no real subprocess execution

    # Update Gate
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    gate_data = {
        "schema": "EXECUTION_GATE_V1",
        "mode": data.mode,
        "updated_at": datetime.now(KST).isoformat(),
        "updated_by": "local_api",
        "reason": data.reason,
    }

    EXECUTION_GATE_FILE.write_text(
        json.dumps(gate_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(f"Gate 변경 완료: {data.mode}")
    return {
        "result": "OK",
        "mode": data.mode,
        "updated_at": gate_data["updated_at"],
    }


@router.get("/api/emergency_stop", summary="Emergency Stop 상태 조회")
def get_emergency_stop():
    """현재 Emergency Stop 상태 반환"""
    status = get_emergency_stop_status()
    return {
        "status": "ready",
        "schema": "EMERGENCY_STOP_V1",
        "asof": datetime.now(KST).isoformat(),
        "data": status,
        "error": None,
    }


@router.post("/api/emergency_stop", summary="Emergency Stop 설정")
def set_emergency_stop(data: EmergencyStopUpdate):
    """Emergency Stop 상태 변경 (enabled=true면 Gate를 MOCK_ONLY로 강제)"""
    logger.info(f"Emergency Stop 변경 요청: enabled={data.enabled}")

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    stop_data = {
        "schema": "EMERGENCY_STOP_V1",
        "enabled": data.enabled,
        "updated_at": datetime.now(KST).isoformat(),
        "updated_by": data.operator_id,
        "reason": data.reason,
    }

    EMERGENCY_STOP_FILE.write_text(
        json.dumps(stop_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # enabled=true면 Gate를 MOCK_ONLY로 강제
    if data.enabled:
        gate_data = {
            "schema": "EXECUTION_GATE_V1",
            "mode": "MOCK_ONLY",
            "updated_at": datetime.now(KST).isoformat(),
            "updated_by": "emergency_stop_system",
            "reason": f"Emergency Stop activated: {data.reason}",
        }
        EXECUTION_GATE_FILE.write_text(
            json.dumps(gate_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.warning("Emergency Stop 활성화 - Gate를 MOCK_ONLY로 강제 전환")

    return {
        "result": "OK",
        "enabled": data.enabled,
        "updated_at": stop_data["updated_at"],
    }


@router.post("/api/approvals/real_enable/request", summary="REAL 모드 승인 요청")
def request_real_approval(data: ApprovalRequest):
    """REAL_ENABLED 승인 요청 생성 (PENDING 상태, keys=[])"""
    logger.info(f"REAL 승인 요청: by={data.requested_by}")

    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)

    approval = {
        "schema": "REAL_ENABLE_APPROVAL_V1",
        "approval_id": str(uuid.uuid4()),
        "requested_at": datetime.now(KST).isoformat(),
        "requested_by": data.requested_by,
        "mode_target": "REAL_ENABLED",
        "reason": data.reason,
        "expires_at": (datetime.now(KST) + timedelta(hours=24)).isoformat(),
        "keys_required": 2,
        "keys": [],
        "status": "PENDING",
    }

    with open(APPROVALS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(approval, ensure_ascii=False) + "\n")

    return {
        "result": "OK",
        "approval_id": approval["approval_id"],
        "status": "PENDING",
    }


@router.post("/api/approvals/real_enable/approve", summary="REAL 모드 Key 제공")
def approve_real_key(data: KeyApproval):
    """승인에 Key 추가 (2개 충족 시 APPROVED)"""
    logger.info(f"Key 제공: approval={data.approval_id}, key={data.key_id}")

    if not APPROVALS_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"result": "FAIL", "message": "No approvals found"},
        )

    approvals = read_jsonl(APPROVALS_FILE)

    # 같은 approval_id의 모든 버전 중 최신 것 찾기 (JSONL은 append-only)
    matching = [a for a in approvals if a.get("approval_id") == data.approval_id]
    if not matching:
        return JSONResponse(
            status_code=404,
            content={"result": "FAIL", "message": "Approval not found"},
        )

    # 최신 버전 (마지막에 추가된 것)
    target = matching[-1]

    # 만료 체크
    if datetime.fromisoformat(target["expires_at"]) < datetime.now(KST):
        return JSONResponse(
            status_code=409,
            content={"result": "EXPIRED", "message": "Approval has expired"},
        )

    # 이미 승인/취소됨
    if target["status"] in ["APPROVED", "REVOKED"]:
        return JSONResponse(
            status_code=409,
            content={
                "result": "CONFLICT",
                "message": f"Status is already {target['status']}",
            },
        )

    # 중복 Key 체크
    existing_keys = [k["key_id"] for k in target.get("keys", [])]
    if data.key_id in existing_keys:
        return JSONResponse(
            status_code=409,
            content={"result": "DUPLICATE", "message": "Key already provided"},
        )

    # 같은 approver가 이미 키 제공했는지 체크
    existing_approvers = [k["provided_by"] for k in target.get("keys", [])]
    if data.approver_id in existing_approvers:
        return JSONResponse(
            status_code=409,
            content={
                "result": "DUPLICATE",
                "message": "Approver already provided a key",
            },
        )

    # Key 추가
    new_key = {
        "key_id": data.key_id,
        "provided_by": data.approver_id,
        "provided_at": datetime.now(KST).isoformat(),
    }
    target["keys"].append(new_key)

    # 2개 충족 시 APPROVED
    if len(target["keys"]) >= target["keys_required"]:
        target["status"] = "APPROVED"
        logger.info(f"Approval APPROVED: {data.approval_id}")

    # 새 로그 Append (Append-only)
    with open(APPROVALS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(target, ensure_ascii=False) + "\n")

    return {
        "result": "OK",
        "approval_id": data.approval_id,
        "status": target["status"],
        "keys_count": len(target["keys"]),
    }


@router.get("/api/approvals/real_enable/latest", summary="최신 REAL 승인 상태 조회")
def get_latest_real_approval():
    """최신 REAL 승인 상태 반환"""
    approval = get_latest_approval()

    if not approval:
        return {
            "status": "not_ready",
            "schema": "REAL_ENABLE_APPROVAL_V1",
            "data": None,
        }

    # 만료 체크
    if approval["status"] == "PENDING" and datetime.fromisoformat(
        approval["expires_at"]
    ) < datetime.now(KST):
        approval["status"] = "EXPIRED"

    return {
        "status": "ready",
        "schema": "REAL_ENABLE_APPROVAL_V1",
        "asof": datetime.now(KST).isoformat(),
        "data": approval,
        "error": None,
    }


@router.get(
    "/api/execution_allowlist",
    summary="Execution Allowlist 조회 (Read-Only)",
)
def get_execution_allowlist():
    """불변 Allowlist 반환 (docs/contracts/ 경로에서 읽기 전용)"""
    if not ALLOWLIST_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "Allowlist not found"},
        )

    try:
        data = json.loads(ALLOWLIST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": data.get("schema", "REAL_EXECUTION_ALLOWLIST_V1"),
            "asof": datetime.now(KST).isoformat(),
            "data": data,
            "immutable_path": "docs/contracts/execution_allowlist_v1.json",
            "error": None,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


@router.post(
    "/api/real_enable_window/request",
    summary="REAL Enable Window 생성",
)
def create_real_window(data: WindowRequest):
    """REAL 실행 창 생성 (C-P.9: REQUEST_REPORTS만, 1회만)"""
    logger.info(f"Window 요청: reason={data.reason}, ttl={data.ttl_seconds}")

    WINDOWS_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(KST)
    window = {
        "schema": "REAL_ENABLE_WINDOW_V1",
        "event": "CREATE",
        "window_id": str(uuid.uuid4()),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=data.ttl_seconds)).isoformat(),
        "created_by": "api",
        "reason": data.reason,
        "allowed_request_types": [
            "REQUEST_RECONCILE",
            "REQUEST_REPORTS",
        ],  # C-P.12
        "max_real_executions": 1,  # C-P.9 고정
        "real_executions_used": 0,
        "status": "ACTIVE",
    }

    with open(WINDOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(window, ensure_ascii=False) + "\n")

    logger.info(f"Window 생성: {window['window_id']}")
    return {
        "result": "OK",
        "schema": "REAL_ENABLE_WINDOW_V1",
        "data": window,
    }


@router.get(
    "/api/real_enable_window/latest",
    summary="현재 REAL Enable Window 조회",
)
def get_real_window_latest():
    """현재 ACTIVE Window 반환 (없으면 빈 rows)"""
    window = get_active_window()

    return {
        "status": "ready",
        "schema": "REAL_ENABLE_WINDOW_V1",
        "asof": datetime.now(KST).isoformat(),
        "row_count": 1 if window else 0,
        "rows": [window] if window else [],
        "error": None,
    }


@router.post(
    "/api/real_enable_window/revoke",
    summary="REAL Enable Window 폐기",
)
def revoke_real_window(data: WindowRevoke):
    """Window 즉시 폐기"""
    logger.info(f"Window 폐기: {data.window_id}")

    if not WINDOWS_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={"result": "FAIL", "message": "No windows"},
        )

    revoke_event = {
        "schema": "REAL_ENABLE_WINDOW_V1",
        "event": "REVOKE",
        "window_id": data.window_id,
        "revoked_at": datetime.now(KST).isoformat(),
        "revoked_by": "api",
        "reason": data.reason,
    }

    with open(WINDOWS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(revoke_event, ensure_ascii=False) + "\n")

    return {
        "result": "OK",
        "window_id": data.window_id,
        "status": "REVOKED",
    }


@router.post(
    "/api/deps/reconcile/check",
    summary="Reconcile Deep Preflight 수행",
)
def run_reconcile_preflight(data: PreflightRequest):
    """Deep Preflight 체크 수행 및 Artifact 저장"""
    logger.info(f"Preflight 체크: {data.request_id} ({data.request_type})")

    PREFLIGHT_DIR.mkdir(parents=True, exist_ok=True)

    checks: Dict[str, Dict] = {}
    fail_reasons: List[str] = []

    # 1. Import Check
    deps = check_reconcile_deps()
    if deps["all_deps_ok"]:
        checks["import_check"] = {
            "status": "PASS",
            "detail": (
                f"pandas={deps.get('pandas_version')},"
                f" pyarrow={deps.get('pyarrow_version')}"
            ),
        }
    else:
        checks["import_check"] = {
            "status": "FAIL",
            "detail": f"Missing: {deps['required_missing']}",
        }
        fail_reasons.append(f"import_check: {deps['required_missing']}")

    # 2. Input Ready Check (minimal - check if config exists)
    config_path = BASE_DIR / "config" / "production_config_v2.py"
    if config_path.exists():
        checks["input_ready_check"] = {
            "status": "PASS",
            "detail": "config exists",
        }
    else:
        checks["input_ready_check"] = {
            "status": "FAIL",
            "detail": "config not found",
        }
        fail_reasons.append("input_ready_check: config not found")

    # 3. Output Writable Check
    output_dir = BASE_DIR / "reports" / "phase_c" / "latest"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test_file = output_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
        checks["output_writable_check"] = {
            "status": "PASS",
            "detail": str(output_dir),
        }
    except Exception as e:
        checks["output_writable_check"] = {
            "status": "FAIL",
            "detail": str(e),
        }
        fail_reasons.append(f"output_writable_check: {e}")

    # 4. Allowlist Check
    allowlist_file = BASE_DIR / "docs" / "contracts" / "execution_allowlist_v1.json"
    if allowlist_file.exists():
        allowlist = json.loads(allowlist_file.read_text(encoding="utf-8"))
        if data.request_type in allowlist.get("allowed_request_types", []):
            checks["allowlist_check"] = {
                "status": "PASS",
                "detail": f"{data.request_type} allowed",
            }
        else:
            checks["allowlist_check"] = {
                "status": "FAIL",
                "detail": f"{data.request_type} not in allowlist",
            }
            fail_reasons.append(f"allowlist_check: {data.request_type} not allowed")
    else:
        checks["allowlist_check"] = {
            "status": "FAIL",
            "detail": "allowlist not found",
        }
        fail_reasons.append("allowlist_check: file not found")

    # 5. Gate Check
    gate_ok = False
    try:
        gate_data = (
            json.loads(EXECUTION_GATE_FILE.read_text(encoding="utf-8"))
            if EXECUTION_GATE_FILE.exists()
            else {}
        )
        estop_data = (
            json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
            if EMERGENCY_STOP_FILE.exists()
            else {}
        )
        window = get_active_window()

        gate_mode = gate_data.get("mode", "MOCK_ONLY")
        estop_enabled = estop_data.get("enabled", False)
        window_active = window is not None and data.request_type in window.get(
            "allowed_request_types", []
        )

        if gate_mode == "REAL_ENABLED" and not estop_enabled and window_active:
            checks["gate_check"] = {
                "status": "PASS",
                "detail": (f"gate={gate_mode}, estop=OFF, window=ACTIVE"),
            }
            gate_ok = True
        else:
            checks["gate_check"] = {
                "status": "FAIL",
                "detail": (
                    f"gate={gate_mode}, estop={estop_enabled},"
                    f" window={window_active}"
                ),
            }
            fail_reasons.append("gate_check: conditions not met")
    except Exception as e:
        checks["gate_check"] = {"status": "FAIL", "detail": str(e)}
        fail_reasons.append(f"gate_check: {e}")

    # Decision
    all_pass = all(c["status"] == "PASS" for c in checks.values())
    decision = "PREFLIGHT_PASS" if all_pass else "PREFLIGHT_FAIL"

    # Save Artifact
    artifact = {
        "schema": "RECONCILE_PREFLIGHT_V1",
        "asof": datetime.now(KST).isoformat(),
        "request_id": data.request_id,
        "request_type": data.request_type,
        "checks": checks,
        "effective_plan": ["python", "-m", "app.reconcile"],
        "decision": decision,
        "fail_reasons": fail_reasons,
    }

    artifact_path = PREFLIGHT_DIR / f"{data.request_id}.json"
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"Preflight 결과: {decision}")
    return {
        "result": "OK",
        "request_id": data.request_id,
        "decision": decision,
        "artifact_path": str(artifact_path.relative_to(BASE_DIR)),
    }
