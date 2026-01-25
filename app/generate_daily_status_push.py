"""
Daily Status Push Generator (D-P.55 + D-P.56 + D-P.57)

OCI 크론 실행 후 당일 운영 상태 + 추천 상세를 PUSH 발송
- Idempotency: 1일 1회만 발송 (mode=test로 우회 가능)
- No Secret Leak: 요약만 발송
- Fail-Closed: enabled=false 또는 토큰 누락 시 외부 전송 금지
- D-P.57: reco_items 상세 포함 (최대 5개)
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).parent.parent

# Input paths
OPS_SUMMARY_LATEST = BASE_DIR / "reports" / "ops" / "summary" / "ops_summary_latest.json"
LIVE_CYCLE_LATEST = BASE_DIR / "reports" / "live" / "cycle" / "latest" / "live_cycle_latest.json"
RECO_LATEST = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"
SENDER_ENABLE_FILE = BASE_DIR / "state" / "real_sender_enable.json"

# Output paths
DAILY_STATUS_DIR = BASE_DIR / "reports" / "ops" / "push" / "daily_status"
DAILY_STATUS_LATEST = DAILY_STATUS_DIR / "latest" / "daily_status_latest.json"
DAILY_STATUS_SNAPSHOTS = DAILY_STATUS_DIR / "snapshots"

# Config
MAX_RECO_ITEMS = 5  # 메시지 길이 제한


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


def get_reco_items() -> tuple[List[Dict], str, str, int]:
    """
    Reco 상세 정보 추출
    
    Returns:
        (reco_items, decision, reason, items_count)
    """
    reco = safe_load_json(RECO_LATEST)
    
    if not reco:
        return [], "UNKNOWN", "NO_RECO_FILE", 0
    
    decision = reco.get("decision", "UNKNOWN")
    reason = reco.get("reason", "")
    recommendations = reco.get("recommendations", [])
    
    # 추천 상세 추출 (최대 N개)
    reco_items = []
    for r in recommendations[:MAX_RECO_ITEMS]:
        item = {
            "action": r.get("action", "HOLD"),
            "ticker": r.get("ticker", ""),
            "name": r.get("name", ""),
            "weight_pct": round(r.get("weight_pct", 0), 1),
            "signal_score": round(r.get("signal_score", 0), 4)
        }
        reco_items.append(item)
    
    return reco_items, decision, reason, len(recommendations)


def generate_daily_status_message(
    ops_status: str,
    live_result: str,
    live_decision: str,
    bundle_decision: str,
    bundle_stale: bool,
    reco_decision: str,
    reco_reason: str,
    reco_items: List[Dict],
    top_risks: list
) -> str:
    """운영 상태 + 추천 상세 메시지 생성 (D-P.57)"""
    risks_str = ",".join(top_risks) if top_risks else "NONE"
    stale_str = "true" if bundle_stale else "false"
    
    # 기본 상태
    lines = [
        f"📊 KRX OPS: {ops_status}",
        f"🔄 LIVE: {live_result} {live_decision}",
        f"📦 bundle={bundle_decision} stale={stale_str}",
        f"📝 reco={reco_decision}",
    ]
    
    # 추천이 비어있는 경우 reason 표시
    if reco_decision in ("EMPTY_RECO", "BLOCKED") or not reco_items:
        if reco_reason:
            lines.append(f"   └─ reason: {reco_reason}")
    
    # 추천 상세 (있는 경우)
    if reco_items:
        lines.append("")
        lines.append("📈 추천:")
        for item in reco_items:
            action = item.get("action", "HOLD")
            ticker = item.get("ticker", "")
            name = item.get("name", "")[:12]  # 종목명 길이 제한
            weight = item.get("weight_pct", 0)
            score = item.get("signal_score", 0)
            
            # 이모지로 action 구분
            emoji = "🟢" if action == "BUY" else ("🔴" if action == "SELL" else "⚪")
            lines.append(f"  {emoji} {action} {ticker} {name} {weight}% ({score:+.2f})")
    
    # 리스크
    lines.append("")
    lines.append(f"⚠️ risks=[{risks_str}]")
    
    return "\n".join(lines)


def generate_daily_status_push(mode: str = "normal") -> Dict[str, Any]:
    """
    Daily Status Push 생성 (D-P.57 Enhanced)
    
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
    
    # D-P.57: Load reco details
    reco_items, reco_decision, reco_reason, items_count = get_reco_items()
    
    # Check sender enabled
    sender_config = safe_load_json(SENDER_ENABLE_FILE) or {}
    sender_enabled = sender_config.get("enabled", False)
    sender_provider = sender_config.get("provider", "").lower()
    
    # Generate message with reco details
    message = generate_daily_status_message(
        ops_status=ops_status,
        live_result=live_result,
        live_decision=live_decision,
        bundle_decision=bundle_decision,
        bundle_stale=bundle_stale,
        reco_decision=reco_decision,
        reco_reason=reco_reason,
        reco_items=reco_items,
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
            "decision": reco_decision,
            "reason": reco_reason if reco_reason else None,
            "items_count": items_count
        },
        "reco_items": reco_items,
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
        "provider_message_id": provider_message_id,
        "reco_items_count": len(reco_items)
    }


if __name__ == "__main__":
    import sys
    mode = "test" if "--test" in sys.argv else "normal"
    result = generate_daily_status_push(mode=mode)
    print(json.dumps(result, indent=2, ensure_ascii=False))
