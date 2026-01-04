"""
Push Delivery Cycle Runner V2 (C-P.19)
푸시 메시지 발송 결정 라우터

주의:
- 실제 외부 발송 절대 금지 (Hard Rule)
- Console-First 정책
- delivery_actual은 항상 CONSOLE
- Candidate 판정은 Gate 무관, 기술적 가능성만 평가
"""

import json
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

# Setup
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = BASE_DIR / "state"
PUSH_STATE_DIR = STATE_DIR / "push"
REPORTS_PUSH_DIR = BASE_DIR / "reports" / "ops" / "push"

PUSH_MESSAGES_FILE = BASE_DIR / "reports" / "push" / "latest" / "push_messages.json"
GATE_FILE = STATE_DIR / "execution_gate.json"
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"

RECEIPTS_FILE = PUSH_STATE_DIR / "push_delivery_receipts.jsonl"
LATEST_RECEIPT_FILE = REPORTS_PUSH_DIR / "push_delivery_latest.json"
CONSOLE_OUT_FILE = REPORTS_PUSH_DIR / "console_out_latest.json"

logging.basicConfig(level=logging.INFO, format="[PUSH_DELIVERY_V2] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Channel Config from PUSH_CHANNELS_V1 Contract
CHANNEL_CONFIG = {
    "CONSOLE": {
        "required_secrets": [],
        "allowed_push_types": ["*"]
    },
    "TELEGRAM": {
        "required_secrets": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
        "allowed_push_types": ["ALERT", "DAILY_REPORT", "SIGNAL"]
    },
    "SLACK": {
        "required_secrets": ["SLACK_WEBHOOK_URL"],
        "allowed_push_types": ["ALERT", "DAILY_REPORT"]
    },
    "EMAIL": {
        "required_secrets": ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_TO"],
        "allowed_push_types": ["DAILY_REPORT"]
    }
}

SELF_TEST_LATEST_FILE = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"


def get_self_test_decision() -> str:
    """최근 Self-Test decision 조회 (값 노출 없음)"""
    if not SELF_TEST_LATEST_FILE.exists():
        return None
    try:
        data = json.loads(SELF_TEST_LATEST_FILE.read_text(encoding="utf-8"))
        return data.get("decision")  # SELF_TEST_PASS or SELF_TEST_FAIL
    except Exception:
        return None


def get_secrets_provider() -> str:
    """최근 Self-Test provider 조회"""
    if not SELF_TEST_LATEST_FILE.exists():
        return "ENV_ONLY"
    try:
        data = json.loads(SELF_TEST_LATEST_FILE.read_text(encoding="utf-8"))
        return data.get("provider", "ENV_ONLY")
    except Exception:
        return "ENV_ONLY"


def load_push_messages() -> list:
    """푸시 메시지 로드"""
    if not PUSH_MESSAGES_FILE.exists():
        return []
    try:
        data = json.loads(PUSH_MESSAGES_FILE.read_text(encoding="utf-8"))
        # Support both 'messages' and 'rows' fields
        return data.get("messages", data.get("rows", []))
    except Exception as e:
        logger.error(f"푸시 메시지 로드 실패: {e}")
        return []


def get_gate_mode() -> str:
    """Gate 모드 조회 (관측용)"""
    if not GATE_FILE.exists():
        return "MOCK_ONLY"
    try:
        data = json.loads(GATE_FILE.read_text(encoding="utf-8"))
        return data.get("mode", "MOCK_ONLY")
    except Exception:
        return "MOCK_ONLY"


def check_emergency_stop() -> bool:
    """비상 정지 상태 확인"""
    if not EMERGENCY_STOP_FILE.exists():
        return False
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data.get("enabled", data.get("active", False))
    except Exception:
        return False


def get_secrets_status() -> dict:
    """시크릿 존재 여부 확인 (값 노출 금지)"""
    # Optional: try to load .env
    try:
        from dotenv import load_dotenv
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except ImportError:
        pass

    all_secrets = set()
    for config in CHANNEL_CONFIG.values():
        all_secrets.update(config.get("required_secrets", []))
    
    secrets_map = {}
    for secret_name in all_secrets:
        # Only check presence, NEVER log or return values
        secrets_map[secret_name] = {"present": bool(os.environ.get(secret_name))}
    
    return secrets_map


def evaluate_candidate(push_type: str, secrets_status: dict) -> tuple:
    """
    Candidate 판정 (Gate 무관, 기술적 가능성만)
    
    Returns:
        (external_candidate: bool, candidate_channels: list, blocked_reason: str|None)
    """
    candidate_channels = []
    blocked_reasons = []
    
    for channel, config in CHANNEL_CONFIG.items():
        if channel == "CONSOLE":
            continue  # CONSOLE is always available
        
        required = config.get("required_secrets", [])
        allowed_types = config.get("allowed_push_types", [])
        
        # Check push_type allowed
        if "*" not in allowed_types and push_type not in allowed_types:
            blocked_reasons.append(f"{channel}:PUSH_TYPE_NOT_ALLOWED")
            continue
        
        # Check all required secrets present
        all_present = all(
            secrets_status.get(s, {}).get("present", False) 
            for s in required
        )
        
        if all_present:
            candidate_channels.append(channel)
        else:
            blocked_reasons.append(f"{channel}:NO_SECRETS")
    
    if candidate_channels:
        return (True, candidate_channels, None)
    else:
        # Determine primary blocked reason
        if all("PUSH_TYPE_NOT_ALLOWED" in r for r in blocked_reasons):
            return (False, [], "PUSH_TYPE_NOT_ALLOWED")
        else:
            return (False, [], "NO_SECRETS_FOR_ANY_CHANNEL")


def run_push_delivery_cycle() -> dict:
    """푸시 발송 결정 사이클 실행 (V2)"""
    delivery_run_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    # Context 로드
    messages = load_push_messages()
    gate_mode_observed = get_gate_mode()  # 관측용만
    emergency_stop = check_emergency_stop()
    secrets_status = get_secrets_status()
    
    # Check if any external secrets are available
    has_any_secrets = any(s.get("present", False) for s in secrets_status.values())
    
    logger.info(f"Gate Mode (observed): {gate_mode_observed}, Emergency Stop: {emergency_stop}")
    logger.info(f"Messages to process: {len(messages)}")
    
    # 결정 수행
    decisions = []
    console_output = []
    summary = {"total_messages": len(messages), "console": 0, "external": 0, "skipped": 0}
    
    # Candidate 판정 (전체 메시지에 대해 동일하게 적용)
    # 기본 push_type은 ALERT로 간주 (메시지에 타입이 있으면 사용)
    default_push_type = "ALERT"
    
    # 전체 Routing 결정 (V2)
    if messages:
        sample_push_type = messages[0].get("push_type", default_push_type)
        external_candidate, candidate_channels, blocked_reason = evaluate_candidate(
            sample_push_type, secrets_status
        )
    else:
        external_candidate = False
        candidate_channels = []
        blocked_reason = "NO_MESSAGES"
    
    for msg in messages:
        message_id = msg.get("id", str(uuid.uuid4()))
        push_type = msg.get("push_type", default_push_type)
        
        # 개별 메시지 candidate 판정
        msg_candidate, msg_channels, msg_blocked = evaluate_candidate(push_type, secrets_status)
        
        # 🛑 Hard Rule: delivery_actual은 항상 CONSOLE
        reason_code = msg_blocked if msg_blocked else "CONSOLE_ONLY_MODE"
        
        decisions.append({
            "message_id": message_id,
            "channel_decision": "CONSOLE",  # Always CONSOLE
            "channel_target": "console",
            "reason_code": reason_code,
            "candidate_info": {
                "external_candidate": msg_candidate,
                "candidate_channels": msg_channels
            }
        })
        
        summary["console"] += 1
        console_output.append({
            "message_id": message_id,
            "title": msg.get("title", ""),
            "content": msg.get("content", msg.get("body", "")),
            "push_type": push_type,
            "reason_code": reason_code
        })
    
    # Receipt V2 생성
    receipt = {
        "schema": "PUSH_DELIVERY_RECEIPT_V2",
        "delivery_run_id": delivery_run_id,
        "asof": asof,
        
        # V1 호환 필드
        "gate_mode": gate_mode_observed,
        "emergency_stop_enabled": emergency_stop,
        "secrets_available": has_any_secrets,
        "summary": summary,
        "decisions": decisions,
        
        # V2 신규 필드
        "routing": {
            "mode": "CONSOLE_ONLY",
            "external_candidate": external_candidate,
            "candidate_channels": candidate_channels,
            "blocked_reason": blocked_reason
        },
        "secrets_status_ref": "api:/api/secrets/status",
        "channel_matrix_version": "PUSH_CHANNELS_V1",
        "gate_mode_observed": gate_mode_observed,
        "delivery_actual": "CONSOLE",  # 🛑 Hard Rule: 항상 CONSOLE
        
        # V2.1 Self-Test 관측 필드 (C-P.20)
        "secrets_self_test_ref": "api:/api/secrets/self_test",
        "secrets_self_test_decision_observed": get_self_test_decision(),
        "secrets_provider_observed": get_secrets_provider()
    }
    
    # 저장
    PUSH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_PUSH_DIR.mkdir(parents=True, exist_ok=True)
    
    # Append-only 로그
    with open(RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    
    # Latest snapshot
    LATEST_RECEIPT_FILE.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Console output
    console_dump = {
        "schema": "CONSOLE_OUT_V2",
        "delivery_run_id": delivery_run_id,
        "asof": asof,
        "messages": console_output
    }
    CONSOLE_OUT_FILE.write_text(json.dumps(console_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Delivery cycle complete (V2): {summary}")
    logger.info(f"Candidate: {external_candidate}, Channels: {candidate_channels}")
    
    return {
        "result": "OK",
        "delivery_run_id": delivery_run_id,
        "summary": summary,
        "routing": receipt["routing"],
        "delivery_actual": "CONSOLE",
        "receipt_path": str(LATEST_RECEIPT_FILE.relative_to(BASE_DIR)),
        "console_out_path": str(CONSOLE_OUT_FILE.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = run_push_delivery_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
