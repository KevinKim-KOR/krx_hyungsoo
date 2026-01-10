"""
Push Send Cycle (C-P.23)
실제 Telegram 발송 (One-Shot, Formatter 강제)

주의:
- TELEGRAM 1채널만 허용
- One-Shot: 윈도우당 1건만
- Formatter 강제
- Secret Leak Zero
- Emergency Stop 최우선
"""

import json
import os
import uuid
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
import sys

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.utils.push_formatter import format_telegram, check_secret_injection, format_test_message

STATE_DIR = BASE_DIR / "state"
PUSH_STATE_DIR = STATE_DIR / "push"
REPORTS_PUSH_DIR = BASE_DIR / "reports" / "ops" / "push"
SEND_DIR = REPORTS_PUSH_DIR / "send"

# File paths
EMERGENCY_STOP_FILE = STATE_DIR / "emergency_stop.json"
GATE_FILE = STATE_DIR / "execution_gate.json"
SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"
SELF_TEST_LATEST = BASE_DIR / "reports" / "ops" / "secrets" / "self_test_latest.json"
OUTBOX_LATEST = REPORTS_PUSH_DIR / "outbox" / "outbox_latest.json"
WINDOW_CONSUMED_FILE = STATE_DIR / "real_sender_window_consumed.json"

SEND_RECEIPTS_FILE = PUSH_STATE_DIR / "send_receipts.jsonl"
SEND_LATEST_FILE = SEND_DIR / "send_latest.json"
SEND_SNAPSHOTS_DIR = SEND_DIR / "snapshots"


def is_emergency_stop() -> bool:
    """Emergency Stop 확인"""
    if not EMERGENCY_STOP_FILE.exists():
        return False
    try:
        data = json.loads(EMERGENCY_STOP_FILE.read_text(encoding="utf-8"))
        return data.get("enabled", data.get("active", False))
    except Exception:
        return False


def get_gate_mode() -> str:
    """Gate 모드 조회"""
    if not GATE_FILE.exists():
        return "MOCK_ONLY"
    try:
        data = json.loads(GATE_FILE.read_text(encoding="utf-8"))
        return data.get("mode", "MOCK_ONLY")
    except Exception:
        return "MOCK_ONLY"


def is_sender_enabled() -> bool:
    """Real Sender 활성화 확인"""
    if not SENDER_ENABLE_FILE.exists():
        return False
    try:
        data = json.loads(SENDER_ENABLE_FILE.read_text(encoding="utf-8"))
        return data.get("enabled", False)
    except Exception:
        return False


def get_self_test_decision() -> str:
    """Self-Test Decision 조회"""
    if not SELF_TEST_LATEST.exists():
        return "SELF_TEST_FAIL"
    try:
        data = json.loads(SELF_TEST_LATEST.read_text(encoding="utf-8"))
        return data.get("decision", "SELF_TEST_FAIL")
    except Exception:
        return "SELF_TEST_FAIL"


def get_secrets_status() -> dict:
    """시크릿 존재 여부 (값 아님, C-P.24 present 규칙)"""
    # present 판정: None 또는 '' = false
    def is_present(key: str) -> bool:
        value = os.environ.get(key)
        return value is not None and value != ""
    
    return {
        "TELEGRAM_BOT_TOKEN": is_present("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": is_present("TELEGRAM_CHAT_ID")
    }


def is_window_consumed() -> bool:
    """One-Shot 윈도우 소진 확인"""
    if not WINDOW_CONSUMED_FILE.exists():
        return False
    try:
        data = json.loads(WINDOW_CONSUMED_FILE.read_text(encoding="utf-8"))
        return data.get("consumed", False)
    except Exception:
        return False


def consume_window():
    """One-Shot 윈도우 소진 처리"""
    data = {
        "consumed": True,
        "consumed_at": datetime.now().isoformat(),
        "schema": "WINDOW_CONSUMED_V1"
    }
    WINDOW_CONSUMED_FILE.parent.mkdir(parents=True, exist_ok=True)
    WINDOW_CONSUMED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sanitize_error(error_msg: str) -> str:
    """에러 메시지 Sanitize (시크릿 마스킹)"""
    if not error_msg:
        return None
    # Mask any potential token/secret patterns
    sanitized = error_msg
    # Mask long strings that might be tokens
    if len(sanitized) > 100:
        sanitized = sanitized[:50] + "...[SANITIZED]..." + sanitized[-20:]
    # Mask bot token patterns
    if "bot" in sanitized.lower() and ":" in sanitized:
        sanitized = "[SANITIZED: API error]"
    return sanitized


def send_telegram_message(text: str) -> tuple:
    """
    Telegram 메시지 발송 (실제 HTTP 호출)
    
    Returns:
        (success: bool, http_status: int?, error_class: str?, error_msg: str?)
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        return (False, None, "ConfigError", "Missing credentials")
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return (True, resp.status, None, None)
    except urllib.error.HTTPError as e:
        return (False, e.code, "HTTPError", sanitize_error(str(e)))
    except urllib.error.URLError as e:
        return (False, None, "URLError", sanitize_error(str(e)))
    except Exception as e:
        return (False, None, type(e).__name__, sanitize_error(str(e)))


def run_push_send_cycle() -> dict:
    """
    Push 발송 사이클 실행
    
    조건 검사 순서:
    1. Emergency Stop
    2. Gate Mode (REAL_ENABLED)
    3. Sender Enabled
    4. Self-Test Decision
    5. Outbox Messages
    6. Window Consumed
    7. Secret Injection Check
    8. Telegram 발송
    """
    send_id = str(uuid.uuid4())
    asof = datetime.now().isoformat()
    
    # Load .env if available (override=False: SYSTEM_ENV > DOTENV)
    try:
        from dotenv import load_dotenv
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=False)  # C-P.24: SYSTEM_ENV > DOTENV
    except ImportError:
        pass
    
    # C-P.32.1: Evidence refs
    try:
        from app.utils.evidence_refs import build_push_refs
        evidence_refs = build_push_refs()
    except Exception:
        evidence_refs = []
    
    # Default receipt structure
    receipt = {
        "schema": "PUSH_SEND_RECEIPT_V1",
        "send_id": send_id,
        "asof": asof,
        "channel": "TELEGRAM",
        "message_id": None,
        "request_type": None,
        "decision": None,
        "blocked_reason": None,
        "formatter_ref": "app/utils/push_formatter.py",
        "preview_ref": "api:/api/push/preview/latest",
        "secrets_status_observed": get_secrets_status(),
        "http_status": None,
        "error_class": None,
        "error_message_sanitized": None,
        "evidence_refs": evidence_refs
    }
    
    # 1. Emergency Stop
    if is_emergency_stop():
        receipt["decision"] = "BLOCKED"
        receipt["blocked_reason"] = "EMERGENCY_STOP"
        return save_receipt(receipt, "BLOCKED by Emergency Stop")
    
    # 2. Gate Mode
    gate_mode = get_gate_mode()
    if gate_mode != "REAL_ENABLED":
        receipt["decision"] = "SKIPPED"
        receipt["blocked_reason"] = "NOT_REAL_GATE"
        return save_receipt(receipt, f"SKIPPED: Gate is {gate_mode}")
    
    # 3. Sender Enabled
    if not is_sender_enabled():
        receipt["decision"] = "SKIPPED"
        receipt["blocked_reason"] = "SENDER_DISABLED"
        return save_receipt(receipt, "SKIPPED: Sender not enabled")
    
    # 4. Self-Test Decision
    self_test = get_self_test_decision()
    if self_test != "SELF_TEST_PASS":
        receipt["decision"] = "BLOCKED"
        receipt["blocked_reason"] = "SELF_TEST_FAIL"
        return save_receipt(receipt, "BLOCKED: Self-test failed")
    
    # 5. Outbox Messages
    if not OUTBOX_LATEST.exists():
        receipt["decision"] = "SKIPPED"
        receipt["blocked_reason"] = "NO_MESSAGES"
        return save_receipt(receipt, "SKIPPED: No outbox")
    
    try:
        outbox = json.loads(OUTBOX_LATEST.read_text(encoding="utf-8"))
        messages = outbox.get("messages", [])
    except Exception:
        receipt["decision"] = "SKIPPED"
        receipt["blocked_reason"] = "NO_MESSAGES"
        return save_receipt(receipt, "SKIPPED: Outbox read error")
    
    if not messages:
        receipt["decision"] = "SKIPPED"
        receipt["blocked_reason"] = "NO_MESSAGES"
        return save_receipt(receipt, "SKIPPED: No messages in outbox")
    
    # 6. Window Consumed
    if is_window_consumed():
        receipt["decision"] = "BLOCKED"
        receipt["blocked_reason"] = "WINDOW_CONSUMED"
        return save_receipt(receipt, "BLOCKED: One-shot window consumed")
    
    # Get first message (우선순위 1개)
    msg = messages[0]
    receipt["message_id"] = msg.get("message_id", msg.get("id", "unknown"))
    receipt["request_type"] = msg.get("push_type", "ALERT")
    
    # 7. Format with Formatter + Secret Injection Check
    # C-P.24: 테스트 메시지 포맷 사용
    kst_timestamp = datetime.now().isoformat()
    text = format_test_message(kst_timestamp)
    
    is_safe, reason = check_secret_injection(text)
    if not is_safe:
        receipt["decision"] = "BLOCKED"
        receipt["blocked_reason"] = "SECRET_INJECTION_SUSPECTED"
        return save_receipt(receipt, f"BLOCKED: {reason}")
    
    # 8. Send Telegram (One-Shot)
    success, http_status, error_class, error_msg = send_telegram_message(text)
    
    # Consume window regardless of success/failure
    consume_window()
    
    receipt["http_status"] = http_status
    receipt["error_class"] = error_class
    receipt["error_message_sanitized"] = error_msg
    
    if success:
        receipt["decision"] = "SENT"
        return save_receipt(receipt, "SENT: Telegram message delivered")
    else:
        receipt["decision"] = "FAILED"
        return save_receipt(receipt, f"FAILED: {error_class}")


def save_receipt(receipt: dict, log_msg: str) -> dict:
    """Receipt 저장 (Atomic Write)"""
    # Ensure directories
    PUSH_STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEND_DIR.mkdir(parents=True, exist_ok=True)
    SEND_SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Append-only log
    with open(SEND_RECEIPTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    
    # Atomic write latest
    tmp_file = SEND_DIR / "send_latest.json.tmp"
    tmp_file.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(SEND_LATEST_FILE))
    
    # Snapshot
    snapshot_name = f"send_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_path = SEND_SNAPSHOTS_DIR / snapshot_name
    snapshot_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "result": receipt["decision"],
        "send_id": receipt["send_id"],
        "decision": receipt["decision"],
        "blocked_reason": receipt["blocked_reason"],
        "message": log_msg,
        "send_latest_path": str(SEND_LATEST_FILE.relative_to(BASE_DIR)),
        "snapshot_path": str(snapshot_path.relative_to(BASE_DIR))
    }


if __name__ == "__main__":
    result = run_push_send_cycle()
    print(json.dumps(result, ensure_ascii=False, indent=2))
