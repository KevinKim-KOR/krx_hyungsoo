"""
Incident Push Generator (D-P.57)

운영 장애/차단 발생 시 즉시 텔레그램으로 알림 발송
- Idempotency: incident_<KIND>_YYYYMMDD (동일 타입 하루 1회)
- Fail-Closed: 백엔드 다운 시 스크립트 직발송 fallback
"""

import json
import os
import shutil
from datetime import datetime
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent

# Input paths
SENDER_ENABLE_FILE = BASE_DIR / "state" / "real_sender_enable.json"

# Output paths
INCIDENT_DIR = BASE_DIR / "reports" / "ops" / "push" / "incident"
INCIDENT_LATEST = INCIDENT_DIR / "latest" / "incident_latest.json"
INCIDENT_SNAPSHOTS = INCIDENT_DIR / "snapshots"

# Incident 종류
INCIDENT_KINDS = {
    "BACKEND_DOWN": {"severity": "CRITICAL", "message": "🚨 서버가 응답하지 않습니다"},
    "OPS_BLOCKED": {"severity": "HIGH", "message": "⛔ Ops Summary BLOCKED"},
    "OPS_FAILED": {"severity": "HIGH", "message": "❌ Ops Summary 생성 실패"},
    "LIVE_BLOCKED": {"severity": "HIGH", "message": "⛔ Live Cycle BLOCKED"},
    "LIVE_FAILED": {"severity": "HIGH", "message": "❌ Live Cycle 실행 실패"},
    "PUSH_FAILED": {"severity": "MEDIUM", "message": "⚠️ PUSH 발송 실패"},
    "MARKET_DATA_DOWN": {"severity": "HIGH", "message": "⚠️ Market Data Fetch Failed"},
}


def safe_load_json(path: Path) -> Optional[Dict]:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_idempotency_key(kind: str, mode: str = "normal") -> str:
    """
    Idempotency key 생성
    - mode=normal: incident_<KIND>_YYYYMMDD (동일 타입 하루 1회)
    - mode=test: test_incident_<KIND>_YYYYMMDD_HHMMSS (우회)
    """
    now = datetime.now(KST)
    if mode == "test":
        return f"test_incident_{kind}_{now.strftime('%Y%m%d_%H%M%S')}"
    return f"incident_{kind}_{now.strftime('%Y%m%d')}"


def check_already_sent(idempotency_key: str) -> bool:
    """해당 idempotency_key로 이미 발송되었는지 확인"""
    # 스냅샷 디렉토리에서 해당 키가 있는지 확인
    if not INCIDENT_SNAPSHOTS.exists():
        return False

    # 오늘 날짜의 스냅샷들 확인
    today = datetime.now(KST).strftime("%Y%m%d")
    for f in INCIDENT_SNAPSHOTS.glob(f"incident_*_{today}_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("idempotency_key") == idempotency_key:
                return True
        except Exception:
            continue
    return False


def generate_incident_message(kind: str, step: str, reason: str) -> str:
    """Incident 메시지 생성"""
    info = INCIDENT_KINDS.get(kind, {"message": f"🚨 INCIDENT: {kind}"})
    base_msg = info["message"]

    lines = [
        f"🚨 INCIDENT: {kind}",
        "",
        base_msg,
        f"Step: {step}",
        f"Reason: {reason}",
        "",
        "조치: OCI 접속하여 상태 확인",
    ]

    return "\n".join(lines)


def generate_incident_push(
    kind: str, step: str = "Unknown", reason: str = "Unknown", mode: str = "normal"
) -> Dict[str, Any]:
    """
    Incident Push 생성

    Args:
        kind: BACKEND_DOWN, OPS_BLOCKED, OPS_FAILED, LIVE_BLOCKED, LIVE_FAILED, PUSH_FAILED
        step: 발생 단계 (Step1~6)
        reason: 상세 사유
        mode: "normal" (하루 1회) 또는 "test" (우회)
    """
    now = datetime.now(KST)
    asof = now.isoformat()
    idempotency_key = get_idempotency_key(kind, mode)

    # Validate kind
    if kind not in INCIDENT_KINDS:
        return {"result": "ERROR", "message": f"Unknown incident kind: {kind}"}

    # Check idempotency (normal mode only)
    if mode != "test" and check_already_sent(idempotency_key):
        return {
            "result": "OK",
            "skipped": True,
            "kind": kind,
            "idempotency_key": idempotency_key,
            "message": f"Already sent {kind} today",
        }

    severity = INCIDENT_KINDS[kind]["severity"]

    # Generate message
    message = generate_incident_message(kind, step, reason)

    # Check sender enabled
    sender_config = safe_load_json(SENDER_ENABLE_FILE) or {}
    sender_enabled = sender_config.get("enabled", False)
    sender_provider = sender_config.get("provider", "").lower()

    # Determine actual delivery method
    final_delivery = "CONSOLE_SIMULATED"
    send_receipt = None
    provider_message_id = None

    if sender_enabled and sender_provider == "telegram":
        try:
            from app.providers.telegram_sender import send_telegram_message

            telegram_result = send_telegram_message(message)

            if telegram_result.get("success"):
                final_delivery = "TELEGRAM"
                provider_message_id = telegram_result.get("message_id")
                send_receipt = {
                    "provider": "TELEGRAM",
                    "message_id": provider_message_id,
                    "sent_at": asof,
                }
                print(
                    f"[INCIDENT_PUSH] Telegram sent: {kind} message_id={provider_message_id}"
                )
            else:
                error_msg = telegram_result.get("error", "Unknown error")
                final_delivery = "TELEGRAM_FAILED"
                send_receipt = {
                    "provider": "TELEGRAM",
                    "error": error_msg,
                    "sent_at": asof,
                }
                print(f"[INCIDENT_PUSH] Telegram failed: {error_msg}")
        except Exception as e:
            final_delivery = "TELEGRAM_ERROR"
            send_receipt = {"provider": "TELEGRAM", "error": str(e), "sent_at": asof}
            print(f"[INCIDENT_PUSH] Telegram error: {e}")
    else:
        print(f"[INCIDENT_PUSH] {message}")

    # Build incident record
    snapshot_filename = f"incident_{kind}_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_ref = f"reports/ops/push/incident/snapshots/{snapshot_filename}"

    incident_record = {
        "schema": "INCIDENT_PUSH_V1",
        "asof": asof,
        "idempotency_key": idempotency_key,
        "mode": mode,
        "kind": kind,
        "severity": severity,
        "step": step,
        "reason": reason,
        "message": message,
        "delivery_actual": final_delivery,
        "send_receipt": send_receipt,
        "snapshot_ref": snapshot_ref,
        "evidence_refs": ["reports/ops/push/incident/latest/incident_latest.json"],
    }

    # Save to latest
    INCIDENT_LATEST.parent.mkdir(parents=True, exist_ok=True)
    INCIDENT_LATEST.write_text(
        json.dumps(incident_record, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Save to snapshot
    INCIDENT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot_path = INCIDENT_SNAPSHOTS / snapshot_filename
    shutil.copy(INCIDENT_LATEST, snapshot_path)

    return {
        "result": "OK",
        "skipped": False,
        "mode": mode,
        "kind": kind,
        "severity": severity,
        "idempotency_key": idempotency_key,
        "delivery_actual": final_delivery,
        "message": message,
        "snapshot_ref": snapshot_ref,
        "provider_message_id": provider_message_id,
    }


if __name__ == "__main__":
    import sys

    mode = "test" if "--test" in sys.argv else "normal"
    kind = "BACKEND_DOWN"
    for arg in sys.argv:
        if arg.startswith("--kind="):
            kind = arg.split("=")[1]

    result = generate_incident_push(
        kind=kind, step="Step2", reason="Test incident", mode=mode
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
