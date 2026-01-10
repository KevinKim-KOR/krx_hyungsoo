"""
Live Fire Ops Runner (C-P.26)
주간 Live Fire 운영 사이클 - 윈도우 기반 발송 + 자동 Lockdown

규칙:
- No Surprise Sender: 유효한 윈도우 없으면 발송 금지
- One-Shot: 1회 시도 = 윈도우 소진
- Post-Fire Lockdown: 발송 후 sender_enable → false
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import sys

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

STATE_DIR = BASE_DIR / "state"
REPORTS_PUSH_DIR = BASE_DIR / "reports" / "ops" / "push"
LIVE_FIRE_DIR = REPORTS_PUSH_DIR / "live_fire"
LIVE_FIRE_LATEST = LIVE_FIRE_DIR / "live_fire_latest.json"
LIVE_FIRE_SNAPSHOTS_DIR = LIVE_FIRE_DIR / "snapshots"

# State files
GATE_FILE = STATE_DIR / "execution_gate.json"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"
SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"
SELF_TEST_LATEST = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"
OUTBOX_LATEST = REPORTS_PUSH_DIR / "outbox" / "outbox_latest.json"
WINDOW_CONSUMED_FILE = STATE_DIR / "real_sender_window_consumed.json"
SEND_LATEST_FILE = REPORTS_PUSH_DIR / "send" / "send_latest.json"
POSTMORTEM_LATEST = REPORTS_PUSH_DIR / "postmortem" / "postmortem_latest.json"


def safe_load_json(path: Path, default=None):
    """Safe JSON 로드"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_gate_mode() -> str:
    data = safe_load_json(GATE_FILE)
    return data.get("mode", "MOCK_ONLY") if data else "MOCK_ONLY"


def is_emergency_stop() -> bool:
    data = safe_load_json(EMERGENCY_STOP_FILE)
    return data.get("enabled", data.get("active", False)) if data else False


def is_sender_enabled() -> bool:
    data = safe_load_json(SENDER_ENABLE_FILE)
    return data.get("enabled", False) if data else False


def get_self_test() -> str:
    data = safe_load_json(SELF_TEST_LATEST)
    return data.get("decision", "UNKNOWN") if data else "UNKNOWN"


def is_window_active() -> bool:
    """윈도우 활성 여부 (consumed=false면 active)"""
    data = safe_load_json(WINDOW_CONSUMED_FILE)
    if data is None:
        return True  # 파일 없으면 아직 소진 안 됨
    return not data.get("consumed", False)


def get_outbox_row_count() -> int:
    data = safe_load_json(OUTBOX_LATEST)
    if data is None:
        return 0
    messages = data.get("messages", data.get("rows", []))
    return len(messages) if messages else 0


def disable_sender():
    """Sender Enable → false (Post-Fire Lockdown)"""
    data = {
        "schema": "REAL_SENDER_ENABLE_V1",
        "enabled": False,
        "channel": "TELEGRAM_ONLY",
        "updated_at": datetime.now().isoformat(),
        "updated_by": "live_fire_ops_runner",
        "reason": "Post-Fire Lockdown"
    }
    SENDER_ENABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENDER_ENABLE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def consume_window():
    """윈도우 소진 처리"""
    data = {
        "consumed": True,
        "consumed_at": datetime.now().isoformat(),
        "schema": "WINDOW_CONSUMED_V1"
    }
    WINDOW_CONSUMED_FILE.parent.mkdir(parents=True, exist_ok=True)
    WINDOW_CONSUMED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_live_fire_ops() -> dict:
    """Live Fire Ops 실행"""
    run_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    # 1. Precheck 정보 수집
    gate_mode = get_gate_mode()
    emergency_stop = is_emergency_stop()
    sender_enabled = is_sender_enabled()
    self_test = get_self_test()
    window_active = is_window_active()
    outbox_count = get_outbox_row_count()
    
    precheck_summary = {
        "gate_mode": gate_mode,
        "self_test": self_test,
        "emergency_stop": emergency_stop,
        "sender_enabled": sender_enabled,
        "window_active": window_active,
        "outbox_row_count": outbox_count
    }
    
    # 2. 기본 Receipt 구조
    receipt = {
        "schema": "LIVE_FIRE_OPS_RECEIPT_V1",
        "run_id": run_id,
        "asof": asof,
        "precheck_summary": precheck_summary,
        "attempted": False,
        "blocked_reason": None,
        "send_http_status": None,
        "channel": "TELEGRAM",
        "message_id": None,
        "window_consumed": False,
        "sender_disabled_after": False,
        "refs": {
            "outbox_snapshot_path": None,
            "send_latest_path": None,
            "postmortem_latest_path": None
        }
    }
    
    # 3. Preconditions 체크
    if outbox_count < 1:
        receipt["blocked_reason"] = "NO_MESSAGES"
        return save_receipt(receipt, "SKIPPED: No messages in outbox")
    
    if emergency_stop:
        receipt["blocked_reason"] = "EMERGENCY_STOP"
        return save_receipt(receipt, "BLOCKED: Emergency stop active")
    
    if gate_mode != "REAL_ENABLED":
        receipt["blocked_reason"] = "NOT_REAL_GATE"
        return save_receipt(receipt, f"SKIPPED: Gate is {gate_mode}")
    
    if self_test != "SELF_TEST_PASS":
        receipt["blocked_reason"] = "SELF_TEST_FAIL"
        return save_receipt(receipt, "BLOCKED: Self-test failed")
    
    if not sender_enabled:
        receipt["blocked_reason"] = "SENDER_DISABLED"
        return save_receipt(receipt, "SKIPPED: Sender not enabled")
    
    if not window_active:
        receipt["blocked_reason"] = "WINDOW_INACTIVE"
        return save_receipt(receipt, "BLOCKED: Window already consumed")
    
    # 4. All preconditions passed - 발송 시도
    try:
        from app.run_push_send_cycle import run_push_send_cycle
        send_result = run_push_send_cycle()
        
        receipt["attempted"] = True
        receipt["send_http_status"] = send_result.get("http_status")
        receipt["message_id"] = send_result.get("message_id")
        
    except Exception as e:
        receipt["attempted"] = True
        receipt["blocked_reason"] = f"SEND_ERROR: {type(e).__name__}"
    
    # 5. Post-Fire Lockdown (성공/실패 무관)
    consume_window()
    receipt["window_consumed"] = True
    
    disable_sender()
    receipt["sender_disabled_after"] = True
    
    # 6. Evidence refs 업데이트
    if SEND_LATEST_FILE.exists():
        receipt["refs"]["send_latest_path"] = str(SEND_LATEST_FILE.relative_to(BASE_DIR))
    if POSTMORTEM_LATEST.exists():
        receipt["refs"]["postmortem_latest_path"] = str(POSTMORTEM_LATEST.relative_to(BASE_DIR))
    
    return save_receipt(receipt, f"COMPLETED: attempted={receipt['attempted']}, http={receipt['send_http_status']}")


def save_receipt(receipt: dict, log_msg: str) -> dict:
    """Receipt 저장 (Atomic Write)"""
    LIVE_FIRE_DIR.mkdir(parents=True, exist_ok=True)
    LIVE_FIRE_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write latest
    tmp_file = LIVE_FIRE_DIR / "live_fire_latest.json.tmp"
    tmp_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(LIVE_FIRE_LATEST))
    
    # Snapshot
    snapshot_name = f"live_fire_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = LIVE_FIRE_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "result": "OK",
        "run_id": receipt["run_id"],
        "attempted": receipt["attempted"],
        "blocked_reason": receipt["blocked_reason"],
        "window_consumed": receipt["window_consumed"],
        "sender_disabled_after": receipt["sender_disabled_after"],
        "message": log_msg,
        "live_fire_latest_path": str(LIVE_FIRE_LATEST.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = run_live_fire_ops()
    print(json.dumps(result, ensure_ascii=False, indent=2))
