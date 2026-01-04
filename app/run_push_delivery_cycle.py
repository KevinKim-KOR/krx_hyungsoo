"""
Push Delivery Cycle Runner (C-P.18)
푸시 메시지 발송 결정 라우터

주의:
- 실제 외부 발송 절대 금지
- Console-First 정책
- Secrets Fallback
"""

import json
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
SECRETS_FILE = BASE_DIR / "config" / "secrets.json"

RECEIPTS_FILE = PUSH_STATE_DIR / "push_delivery_receipts.jsonl"
LATEST_RECEIPT_FILE = REPORTS_PUSH_DIR / "push_delivery_latest.json"
CONSOLE_OUT_FILE = REPORTS_PUSH_DIR / "console_out_latest.json"

logging.basicConfig(level=logging.INFO, format="[PUSH_DELIVERY] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_push_messages() -> list:
    """푸시 메시지 로드"""
    if not PUSH_MESSAGES_FILE.exists():
        return []
    try:
        data = json.loads(PUSH_MESSAGES_FILE.read_text(encoding="utf-8"))
        return data.get("messages", [])
    except Exception as e:
        logger.error(f"푸시 메시지 로드 실패: {e}")
        return []


def get_gate_mode() -> str:
    """Gate 모드 조회"""
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


def check_secrets_available() -> bool:
    """외부 발송 시크릿 존재 확인"""
    if not SECRETS_FILE.exists():
        return False
    try:
        data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        # Telegram 봇 토큰과 채팅 ID 확인
        telegram = data.get("telegram", {})
        return bool(telegram.get("bot_token") and telegram.get("chat_id"))
    except Exception:
        return False


def determine_channel_decision(gate_mode: str, emergency_stop: bool, secrets_available: bool) -> tuple:
    """
    채널 결정 정책 적용 (Console-First)
    
    Returns:
        (channel_decision, channel_target, reason_code)
    """
    # 1. Emergency Stop 최우선
    if emergency_stop:
        return ("CONSOLE", "console", "EMERGENCY_STOP_FORCED_CONSOLE")
    
    # 2. Gate 모드 확인
    if gate_mode == "MOCK_ONLY":
        return ("CONSOLE", "console", "GATE_MOCK_ONLY_CONSOLE")
    
    if gate_mode == "DRY_RUN":
        return ("CONSOLE", "console", "GATE_DRY_RUN_CONSOLE_ONLY")
    
    # 3. REAL_ENABLED + Secrets 확인
    if gate_mode == "REAL_ENABLED":
        if secrets_available:
            return ("EXTERNAL", "telegram", "EXTERNAL_ALLOWED")
        else:
            return ("CONSOLE", "console", "NO_SECRET_FALLBACK_CONSOLE")
    
    # 기본: CONSOLE
    return ("CONSOLE", "console", "UNKNOWN_GATE_FALLBACK_CONSOLE")


def run_push_delivery_cycle() -> dict:
    """푸시 발송 결정 사이클 실행"""
    delivery_run_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    # 컨텍스트 로드
    messages = load_push_messages()
    gate_mode = get_gate_mode()
    emergency_stop = check_emergency_stop()
    secrets_available = check_secrets_available()
    
    logger.info(f"Gate Mode: {gate_mode}, Emergency Stop: {emergency_stop}, Secrets: {secrets_available}")
    logger.info(f"Messages to process: {len(messages)}")
    
    # 결정 수행
    decisions = []
    console_output = []
    summary = {"total_messages": len(messages), "console": 0, "external": 0, "skipped": 0}
    
    for msg in messages:
        message_id = msg.get("id", str(uuid.uuid4()))
        channel_decision, channel_target, reason_code = determine_channel_decision(
            gate_mode, emergency_stop, secrets_available
        )
        
        decisions.append({
            "message_id": message_id,
            "channel_decision": channel_decision,
            "channel_target": channel_target,
            "reason_code": reason_code
        })
        
        if channel_decision == "CONSOLE":
            summary["console"] += 1
            console_output.append({
                "message_id": message_id,
                "title": msg.get("title", ""),
                "content": msg.get("content", msg.get("body", "")),
                "reason_code": reason_code
            })
        elif channel_decision == "EXTERNAL":
            summary["external"] += 1
            # 실제 발송은 하지 않음 (시뮬레이션만)
            logger.info(f"[SIMULATION] External delivery allowed for {message_id}")
    
    # Receipt 생성
    receipt = {
        "schema": "PUSH_DELIVERY_RECEIPT_V1",
        "delivery_run_id": delivery_run_id,
        "asof": asof,
        "gate_mode": gate_mode,
        "emergency_stop_enabled": emergency_stop,
        "secrets_available": secrets_available,
        "summary": summary,
        "decisions": decisions
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
        "schema": "CONSOLE_OUT_V1",
        "delivery_run_id": delivery_run_id,
        "asof": asof,
        "messages": console_output
    }
    CONSOLE_OUT_FILE.write_text(json.dumps(console_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    
    logger.info(f"Delivery cycle complete: {summary}")
    
    return {
        "result": "OK",
        "delivery_run_id": delivery_run_id,
        "summary": summary,
        "receipt_path": str(LATEST_RECEIPT_FILE.relative_to(BASE_DIR)),
        "console_out_path": str(CONSOLE_OUT_FILE.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = run_push_delivery_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
