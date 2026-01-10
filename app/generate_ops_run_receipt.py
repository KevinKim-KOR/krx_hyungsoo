"""
Ops Run Receipt Generator (C-P.27)
통합 운영 영수증 생성 - 하루 운영 사이클 한눈에 파악

규칙:
- 이 영수증 하나로 오늘 시스템이 뭘 했는지 확인 가능
- External Send Count = 0 보장 (DRY_RUN/CONSOLE_ONLY 시)
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "reports"
SCHEDULER_DIR = REPORTS_DIR / "ops" / "scheduler"
SCHEDULER_LATEST_DIR = SCHEDULER_DIR / "latest"
SCHEDULER_SNAPSHOTS_DIR = SCHEDULER_DIR / "snapshots"

# State files
GATE_FILE = STATE_DIR / "execution_gate.json"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"
SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"
WINDOW_CONSUMED_FILE = STATE_DIR / "real_sender_window_consumed.json"

# Result files
OUTBOX_LATEST = REPORTS_DIR / "ops" / "push" / "outbox" / "outbox_latest.json"
LIVE_FIRE_LATEST = REPORTS_DIR / "ops" / "push" / "live_fire" / "live_fire_latest.json"
DELIVERY_LATEST = REPORTS_DIR / "ops" / "push" / "delivery_latest.json"


def safe_load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_observed_modes() -> dict:
    """현재 관측 모드"""
    gate_data = safe_load_json(GATE_FILE)
    gate_mode = gate_data.get("mode", "DRY_RUN") if gate_data else "DRY_RUN"
    
    emergency_data = safe_load_json(EMERGENCY_STOP_FILE)
    emergency_stop = emergency_data.get("enabled", False) if emergency_data else False
    
    sender_data = safe_load_json(SENDER_ENABLE_FILE)
    sender_enable = sender_data.get("enabled", False) if sender_data else False
    
    window_data = safe_load_json(WINDOW_CONSUMED_FILE)
    window_active = not window_data.get("consumed", False) if window_data else True
    
    return {
        "gate_mode": gate_mode,
        "delivery_mode": "CONSOLE_ONLY",  # 기본 정책
        "sender_enable": sender_enable,
        "window_active": window_active,
        "emergency_stop": emergency_stop
    }


def determine_live_fire_decision(observed_modes: dict, outbox_count: int) -> tuple:
    """Live Fire 결정 및 사유"""
    if observed_modes["emergency_stop"]:
        return "BLOCKED", "EMERGENCY_STOP"
    
    if observed_modes["gate_mode"] != "REAL_ENABLED":
        return "SKIPPED", "NOT_REAL_GATE"
    
    if outbox_count < 1:
        return "SKIPPED", "NO_MESSAGES"
    
    if not observed_modes["sender_enable"]:
        return "SKIPPED", "SENDER_DISABLED"
    
    if not observed_modes["window_active"]:
        return "BLOCKED", "WINDOW_INACTIVE"
    
    # 모든 조건 만족 시 실행 대상
    return "PENDING", "CONDITIONS_MET"


def generate_ops_run_receipt(
    ticket_result: dict = None,
    push_delivery_result: dict = None,
    live_fire_result: dict = None,
    caller: str = "api"
) -> dict:
    """OPS_RUN_RECEIPT_V1 생성"""
    run_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    observed_modes = get_observed_modes()
    
    # Outbox 카운트
    outbox_data = safe_load_json(OUTBOX_LATEST)
    outbox_count = 0
    if outbox_data:
        messages = outbox_data.get("messages", outbox_data.get("rows", []))
        outbox_count = len(messages) if messages else 0
    
    # Ticket Step
    ticket_step = {
        "decision": "SKIPPED",
        "reason": "No ticket result",
        "receipt_ref": None
    }
    if ticket_result:
        ticket_step["decision"] = ticket_result.get("status", "DONE")
        ticket_step["reason"] = ticket_result.get("reason", "Ticket processed")
        ticket_step["receipt_ref"] = ticket_result.get("snapshot_path")
    
    # Push Delivery Step
    push_delivery_step = {
        "decision": "SKIPPED",
        "outbox_ref": None
    }
    if push_delivery_result:
        push_delivery_step["decision"] = "DONE"
        push_delivery_step["outbox_ref"] = str(OUTBOX_LATEST.relative_to(BASE_DIR)) if OUTBOX_LATEST.exists() else None
    
    # Live Fire Step
    live_fire_decision, live_fire_reason = determine_live_fire_decision(observed_modes, outbox_count)
    live_fire_step = {
        "decision": live_fire_decision,
        "reason": live_fire_reason,
        "live_fire_receipt_ref": None
    }
    
    if live_fire_result:
        live_fire_step["decision"] = live_fire_result.get("blocked_reason") and "BLOCKED" or (live_fire_result.get("attempted") and "DONE" or "SKIPPED")
        live_fire_step["reason"] = live_fire_result.get("blocked_reason", live_fire_reason)
        if LIVE_FIRE_LATEST.exists():
            live_fire_step["live_fire_receipt_ref"] = str(LIVE_FIRE_LATEST.relative_to(BASE_DIR))
    
    # External Send Count (DRY_RUN/CONSOLE_ONLY = 0)
    external_send_count = 0
    if live_fire_result and live_fire_result.get("attempted") and live_fire_result.get("send_http_status"):
        external_send_count = 1
    
    # Snapshot path
    snapshot_name = f"ops_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = SCHEDULER_SNAPSHOTS_DIR / snapshot_name
    
    receipt = {
        "schema": "OPS_RUN_RECEIPT_V1",
        "run_id": run_id,
        "asof": asof,
        "invocation": {
            "type": "API",
            "path": "/api/ops/cycle/run",
            "caller": caller
        },
        "observed_modes": observed_modes,
        "ticket_step": ticket_step,
        "push_delivery_step": push_delivery_step,
        "live_fire_step": live_fire_step,
        "external_send_count": external_send_count,
        "refs": {
            "ops_run_snapshot": str(snapshot_path.relative_to(BASE_DIR))
        }
    }
    
    # Save
    SCHEDULER_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULER_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write latest
    latest_path = SCHEDULER_LATEST_DIR / "ops_run_latest.json"
    tmp_file = SCHEDULER_LATEST_DIR / "ops_run_latest.json.tmp"
    tmp_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(latest_path))
    
    # Snapshot
    snapshot_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "result": "OK",
        "run_id": run_id,
        "overall_status": observe_overall_status(receipt),
        "ops_run_latest_path": str(latest_path.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


def observe_overall_status(receipt: dict) -> str:
    """전체 상태 계산"""
    if receipt["observed_modes"]["emergency_stop"]:
        return "STOPPED"
    
    live_fire_decision = receipt["live_fire_step"]["decision"]
    if live_fire_decision == "BLOCKED":
        return "BLOCKED"
    
    return "DONE"


if __name__ == "__main__":
    result = generate_ops_run_receipt(caller="cli")
    print(json.dumps(result, ensure_ascii=False, indent=2))
