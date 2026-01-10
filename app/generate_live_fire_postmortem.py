"""
Live Fire Postmortem Generator (C-P.25)
Live Fire 실행 결과 분석 및 Kill-Switch 상태 검증

주의:
- No External Send: 분석/기록 전용
- Robustness: 파일 없어도 크래시 없이 동작
- Atomic Write 필수
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

# C-P.32.1: Evidence refs utility
try:
    from app.utils.evidence_refs import build_postmortem_refs
except ImportError:
    def build_postmortem_refs():
        return []

STATE_DIR = BASE_DIR / "state"
REPORTS_PUSH_DIR = BASE_DIR / "reports" / "ops" / "push"
POSTMORTEM_DIR = REPORTS_PUSH_DIR / "postmortem"
POSTMORTEM_LATEST = POSTMORTEM_DIR / "postmortem_latest.json"
POSTMORTEM_SNAPSHOTS_DIR = POSTMORTEM_DIR / "snapshots"

# Source files
GATE_FILE = STATE_DIR / "execution_gate.json"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"
SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"
SELF_TEST_LATEST = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"
SEND_LATEST_FILE = REPORTS_PUSH_DIR / "send" / "send_latest.json"
SEND_RECEIPTS_FILE = STATE_DIR / "push" / "send_receipts.jsonl"
OUTBOX_LATEST_FILE = REPORTS_PUSH_DIR / "outbox" / "outbox_latest.json"
WINDOW_CONSUMED_FILE = STATE_DIR / "real_sender_window_consumed.json"


def safe_load_json(path: Path, default=None):
    """Safe JSON loading - 파일 없으면 default 반환"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_gate_mode() -> str:
    """Gate 모드 조회"""
    data = safe_load_json(GATE_FILE)
    if data is None:
        return "UNKNOWN"
    return data.get("mode", "UNKNOWN")


def is_sender_enabled() -> bool:
    """Sender Enable 상태 (Kill-Switch 확인)"""
    data = safe_load_json(SENDER_ENABLE_FILE)
    if data is None:
        return False  # 파일 없으면 disabled로 간주
    return data.get("enabled", False)


def is_emergency_stop_enabled() -> bool:
    """Emergency Stop 상태"""
    data = safe_load_json(EMERGENCY_STOP_FILE)
    if data is None:
        return False
    return data.get("enabled", data.get("active", False))


def get_self_test_decision() -> str:
    """Self-Test Decision"""
    data = safe_load_json(SELF_TEST_LATEST)
    if data is None:
        return "UNKNOWN"
    return data.get("decision", "UNKNOWN")


def is_window_consumed() -> bool:
    """Window 소진 여부"""
    data = safe_load_json(WINDOW_CONSUMED_FILE)
    if data is None:
        return False
    return data.get("consumed", False)


def get_send_attempt_info() -> dict:
    """Send 시도 정보"""
    data = safe_load_json(SEND_LATEST_FILE)
    if data is None:
        return {
            "attempted": False,
            "decision": None,
            "http_status": None,
            "ref": None
        }
    
    decision = data.get("decision")
    attempted = decision in ["SENT", "FAILED"]
    
    return {
        "attempted": attempted,
        "decision": decision,
        "http_status": data.get("http_status"),
        "ref": str(SEND_LATEST_FILE.relative_to(BASE_DIR)) if SEND_LATEST_FILE.exists() else None
    }


def calculate_overall_safety_status(sender_enabled: bool, emergency_stop: bool) -> str:
    """Overall Safety Status 계산"""
    if sender_enabled:
        return "UNSAFE"  # Kill-Switch가 아직 켜져있음 - CRITICAL
    if emergency_stop:
        return "SAFE"  # Emergency Stop 상태는 안전
    return "SAFE"


def generate_postmortem() -> dict:
    """Live Fire Postmortem 생성"""
    event_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    # 1. Gather Context
    gate_mode = get_gate_mode()
    sender_enabled = is_sender_enabled()
    emergency_stop_enabled = is_emergency_stop_enabled()
    self_test_decision = get_self_test_decision()
    
    # 2. Gather Evidence
    send_attempt = get_send_attempt_info()
    window_consumed = is_window_consumed()
    
    # 3. Verify Invariants (Kill-Switch Check)
    sender_is_disabled = not sender_enabled
    
    # CRITICAL WARNING if sender still enabled
    if sender_enabled:
        print("[CRITICAL WARNING] Kill-Switch (Sender Enable) is still ON!")
    
    # 4. Calculate overall safety
    overall_status = calculate_overall_safety_status(sender_enabled, emergency_stop_enabled)
    
    # 5. Construct Postmortem JSON
    postmortem = {
        "schema": "LIVE_FIRE_POSTMORTEM_V1",
        "event_id": event_id,
        "asof": asof,
        "overall_safety_status": overall_status,
        "context_observed": {
            "gate_mode": gate_mode,
            "sender_enabled": sender_enabled,
            "emergency_stop_enabled": emergency_stop_enabled,
            "self_test_decision": self_test_decision
        },
        "send_attempt_observed": send_attempt,
        "safety_invariants": {
            "sender_is_currently_disabled": sender_is_disabled,
            "window_was_consumed": window_consumed,
            "emergency_stop_is_off": not emergency_stop_enabled
        },
        "evidence_refs": build_postmortem_refs()
    }
    
    # 6. Atomic Save
    POSTMORTEM_DIR.mkdir(parents=True, exist_ok=True)
    POSTMORTEM_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Atomic write latest
    tmp_file = POSTMORTEM_DIR / "postmortem_latest.json.tmp"
    tmp_file.write_text(json.dumps(postmortem, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(POSTMORTEM_LATEST))
    
    # Snapshot
    snapshot_name = f"postmortem_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = POSTMORTEM_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(postmortem, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "result": "OK",
        "event_id": event_id,
        "overall_safety_status": overall_status,
        "kill_switch_verified": sender_is_disabled,
        "postmortem_latest_path": str(POSTMORTEM_LATEST.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = generate_postmortem()
    print(json.dumps(result, ensure_ascii=False, indent=2))
