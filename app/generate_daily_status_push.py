"""
Daily Status Push Generator (D-P.55 + D-P.56 Telegram)

OCI 크론 실행 후 당일 운영 상태를 1줄 요약으로 PUSH 발송
- Idempotency: 1일 1회만 발송 (mode=test로 우회 가능)
- No Secret Leak: 요약만 발송
- Fail-Closed: enabled=false 또는 토큰 누락 시 외부 전송 금지
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent.parent

# Input paths
OPS_SUMMARY_LATEST = BASE_DIR / "reports" / "ops" / "summary" / "ops_summary_latest.json"
LIVE_CYCLE_LATEST = BASE_DIR / "reports" / "live" / "cycle" / "latest" / "live_cycle_latest.json"
SENDER_ENABLE_FILE = BASE_DIR / "state" / "real_sender_enable.json"

# Output paths
DAILY_STATUS_DIR = BASE_DIR / "reports" / "ops" / "push" / "daily_status"
DAILY_STATUS_LATEST = DAILY_STATUS_DIR / "latest" / "daily_status_latest.json"
DAILY_STATUS_SNAPSHOTS = DAILY_STATUS_DIR / "snapshots"


def safe_load_json(path: Path) -> Optional[Dict]:
    """JSON 파일 안전 로드"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_idempotency_key(mode: str = "normal") -> str:
    """
    Idempotency key 생성
    - mode=normal: daily_status_YYYYMMDD (1일 1회)
    - mode=test: test_daily_status_YYYYMMDD_HHMMSS (매번 새로)
    """
    now = datetime.now()
    if mode == "test":
        return f"test_daily_status_{now.strftime('%Y%m%d_%H%M%S')}"
    return f"daily_status_{now.strftime('%Y%m%d')}"


def check_already_sent(idempotency_key: str) -> bool:
    """해당 idempotency_key로 이미 발송되었는지 확인"""
    if not DAILY_STATUS_LATEST.exists():
        return False
    try:
        data = json.loads(DAILY_STATUS_LATEST.read_text(encoding="utf-8"))
        stored_key = data.get("idempotency_key", "")
        return stored_key == idempotency_key
    except Exception:
        return False


def generate_daily_status_message(
    ops_status: str,
    live_result: str,
    live_decision: str,
    bundle_decision: str,
    bundle_stale: bool,
    reco_decision: str,
    delivery: str,
    top_risks: list
) -> str:
    """1줄 요약 메시지 생성"""
    risks_str = ",".join(top_risks) if top_risks else "NONE"
    stale_str = "true" if bundle_stale else "false"
    
    return (
        f"📊 KRX OPS: {ops_status}\n"
        f"🔄 LIVE: {live_result} {live_decision}\n"
        f"📦 bundle={bundle_decision} stale={stale_str}\n"
        f"📝 reco={reco_decision}\n"
        f"⚠️ risks=[{risks_str}]"
    )


def generate_daily_status_push(mode: str = "normal") -> Dict[str, Any]:
    """
    Daily Status Push 생성
    
    Args:
        mode: "normal" (1일 1회 idempotency) 또는 "test" (우회)
    """
    now = datetime.now()
    asof = now.isoformat()
    idempotency_key = get_idempotency_key(mode)
    
    # Check idempotency (normal mode only)
    if mode != "test" and check_already_sent(idempotency_key):
        return {
            "result": "OK",
            "skipped": True,
            "idempotency_key": idempotency_key,
            "message": "Already sent today"
        }
    
    # Load ops summary
    ops_summary = safe_load_json(OPS_SUMMARY_LATEST) or {}
    ops_status = ops_summary.get("overall_status", "UNKNOWN")
    ops_risks = ops_summary.get("top_risks", [])
    top_risk_codes = [r.get("code", "") for r in ops_risks if r.get("code")]
    
    # Load live cycle
    live_cycle = safe_load_json(LIVE_CYCLE_LATEST) or {}
    live_result = live_cycle.get("result", "UNKNOWN")
    live_decision = live_cycle.get("decision", "UNKNOWN")
    
    # Bundle info from live cycle
    bundle_info = live_cycle.get("bundle", {}) or {}
    bundle_decision = bundle_info.get("decision", "UNKNOWN")
    bundle_stale = bundle_info.get("stale", False)
    
    # Reco info from live cycle
    reco_info = live_cycle.get("reco", {}) or {}
    reco_decision = reco_info.get("decision", "UNKNOWN")
    
    # Push info (from live cycle)
    push_info = live_cycle.get("push", {}) or {}
    live_delivery = push_info.get("delivery_actual", "CONSOLE_SIMULATED")
    
    # Check sender enabled
    sender_config = safe_load_json(SENDER_ENABLE_FILE) or {}
    sender_enabled = sender_config.get("enabled", False)
    sender_provider = sender_config.get("provider", "").lower()
    
    # Generate message
    message = generate_daily_status_message(
        ops_status=ops_status,
        live_result=live_result,
        live_decision=live_decision,
        bundle_decision=bundle_decision,
        bundle_stale=bundle_stale,
        reco_decision=reco_decision,
        delivery=live_delivery,
        top_risks=top_risk_codes
    )
    
    # Determine actual delivery method
    final_delivery = "CONSOLE_SIMULATED"
    send_receipt = None
    provider_message_id = None
    
    if sender_enabled and sender_provider == "telegram":
        # D-P.56: Telegram real send
        try:
            from app.providers.telegram_sender import send_telegram_message
            
            telegram_result = send_telegram_message(message)
            
            if telegram_result.get("success"):
                final_delivery = "TELEGRAM"
                provider_message_id = telegram_result.get("message_id")
                send_receipt = {
                    "provider": "TELEGRAM",
                    "message_id": provider_message_id,
                    "sent_at": asof
                }
                print(f"[DAILY_STATUS_PUSH] Telegram sent: message_id={provider_message_id}")
            else:
                # Telegram failed - Fail-Closed: 외부 전송 실패 기록
                error_msg = telegram_result.get("error", "Unknown error")
                final_delivery = "TELEGRAM_FAILED"
                send_receipt = {
                    "provider": "TELEGRAM",
                    "error": error_msg,
                    "sent_at": asof
                }
                print(f"[DAILY_STATUS_PUSH] Telegram failed: {error_msg}")
        except Exception as e:
            final_delivery = "TELEGRAM_ERROR"
            send_receipt = {
                "provider": "TELEGRAM",
                "error": str(e),
                "sent_at": asof
            }
            print(f"[DAILY_STATUS_PUSH] Telegram error: {e}")
    else:
        # Fail-Closed: enabled=false or provider not telegram
        print(f"[DAILY_STATUS_PUSH] {message}")
    
    # Build push record
    snapshot_filename = f"daily_status_{now.strftime('%Y%m%d_%H%M%S')}.json"
    snapshot_ref = f"reports/ops/push/daily_status/snapshots/{snapshot_filename}"
    
    push_record = {
        "schema": "DAILY_STATUS_PUSH_V1",
        "asof": asof,
        "idempotency_key": idempotency_key,
        "mode": mode,
        "ops_status": ops_status,
        "live_status": {
            "result": live_result,
            "decision": live_decision
        },
        "bundle": {
            "decision": bundle_decision,
            "stale": bundle_stale
        },
        "reco": {
            "decision": reco_decision
        },
        "top_risks": top_risk_codes,
        "message": message,
        "delivery_actual": final_delivery,
        "send_receipt": send_receipt,
        "snapshot_ref": snapshot_ref,
        "evidence_refs": [
            "reports/ops/push/daily_status/latest/daily_status_latest.json"
        ]
    }
    
    # Save to latest
    DAILY_STATUS_LATEST.parent.mkdir(parents=True, exist_ok=True)
    DAILY_STATUS_LATEST.write_text(json.dumps(push_record, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Save to snapshot
    DAILY_STATUS_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot_path = DAILY_STATUS_SNAPSHOTS / snapshot_filename
    shutil.copy(DAILY_STATUS_LATEST, snapshot_path)
    
    return {
        "result": "OK",
        "skipped": False,
        "mode": mode,
        "idempotency_key": idempotency_key,
        "delivery_actual": final_delivery,
        "message": message,
        "snapshot_ref": snapshot_ref,
        "provider_message_id": provider_message_id
    }


if __name__ == "__main__":
    import sys
    mode = "test" if "--test" in sys.argv else "normal"
    result = generate_daily_status_push(mode=mode)
    print(json.dumps(result, indent=2))
