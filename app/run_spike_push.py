"""
Spike Push Runner (D-P.61)

Watchlist에 있는 종목들의 현재가를 체크하여 급등/급락 발생 시 텔레그램을 발송합니다.
- OCI에서 5~10분 주기로 실행 (Cron)
- 중복 발송 방지 (Cooldown: 15분)
- Fail-Closed: 시세 조회 실패 시 발송 안 함 (로그만)
"""

import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import hashlib

BASE_DIR = Path(__file__).parent.parent

# Input paths
WATCHLIST_FILE = BASE_DIR / "state" / "watchlist" / "latest" / "watchlist_latest.json"

# State paths
STATE_DIR = BASE_DIR / "state" / "spike"
SPIKE_STATE_FILE = STATE_DIR / "spike_state.json"  # Cooldown tracking

# Output logs
SPIKE_LOG_DIR = BASE_DIR / "reports" / "ops" / "push" / "spike"
SPIKE_LATEST_FILE = SPIKE_LOG_DIR / "latest" / "spike_latest.json"

# Config
COOLDOWN_MINUTES = 15
THRESHOLD_PCT = 3.0  # ±3%


def ensure_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SPIKE_LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except:
        return None


def save_json(path: Path, data: Dict):
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def get_mock_price_change(ticker: str) -> float:
    """
    시세 변동률 조회 (Mock)
    실제 환경에서는 pykrx 또는 API 사용
    여기서는 테스트를 위해 랜덤 값 반환 (가끔 급등락 발생)
    """
    # Deterministic randomness based on time roughly
    # But for demo, let's just random
    val = random.uniform(-1.0, 1.0) # Normal range
    
    # Occasional spike
    if random.random() < 0.05: # 5% chance
        val = random.uniform(3.0, 5.0) * (1 if random.random() > 0.5 else -1)
        print(f"[DEBUG] Mock Spike for {ticker}: {val:.2f}%")
    
    return val


def check_cooldown(state: Dict, ticker: str, direction: str) -> bool:
    """쿨다운 체크 (True면 발송 가능)"""
    key = f"{ticker}_{direction}"
    last_sent_str = state.get("last_sent", {}).get(key)
    
    if not last_sent_str:
        return True
        
    last_sent = datetime.fromisoformat(last_sent_str)
    if datetime.now() - last_sent > timedelta(minutes=COOLDOWN_MINUTES):
        return True
        
    return False


def update_cooldown(state: Dict, ticker: str, direction: str):
    """쿨다운 갱신"""
    key = f"{ticker}_{direction}"
    if "last_sent" not in state:
        state["last_sent"] = {}
    state["last_sent"][key] = datetime.now().isoformat()
    # Save is done by caller


def run_spike_push() -> Dict:
    """Spike Push 실행"""
    ensure_dirs()
    
    watchlist_data = load_json(WATCHLIST_FILE)
    if not watchlist_data:
        return {"result": "BLOCKED", "reason": "NO_WATCHLIST"}
    
    items = watchlist_data.get("items", [])
    if not items:
        return {"result": "BLOCKED", "reason": "EMPTY_WATCHLIST"}
    
    state = load_json(SPIKE_STATE_FILE) or {}
    
    alerts = []
    skipped = 0
    
    for item in items:
        if not item.get("enabled", True):
            continue
            
        ticker = item.get("ticker", "")
        name = item.get("name", "")
        
        # Check price (Mock)
        change_pct = get_mock_price_change(ticker)
        
        # Check specific triggers
        alert_type = None
        if change_pct >= THRESHOLD_PCT:
            alert_type = "UP"
        elif change_pct <= -THRESHOLD_PCT:
            alert_type = "DOWN"
            
        if alert_type:
            # Check cooldown
            if check_cooldown(state, ticker, alert_type):
                alerts.append({
                    "ticker": ticker,
                    "name": name,
                    "change_pct": round(change_pct, 2),
                    "type": alert_type
                })
                update_cooldown(state, ticker, alert_type)
            else:
                skipped += 1
                
    # Save state
    save_json(SPIKE_STATE_FILE, state)
    
    # Send messages (Telegram)
    sent_count = 0
    if alerts:
        from app.providers.telegram_sender import send_telegram_message
        
        for alert in alerts:
            emoji = "🚀" if alert["type"] == "UP" else "📉"
            msg = f"{emoji} {alert['type']} {alert['name']}({alert['ticker']}) {alert['change_pct']:+.2f}%"
            
            # Send (Individual messages for spikes to grab attention)
            res = send_telegram_message(msg)
            if res.get("success"):
                sent_count += 1
                print(f"[SPIKE] Sent: {msg}")
            else:
                print(f"[SPIKE] Failed: {msg} - {res.get('error')}")

    # Receipt
    receipt = {
        "schema": "SPIKE_PUSH_RECEIPT_V1",
        "asof": datetime.now().isoformat(),
        "alerts_count": len(alerts),
        "sent_count": sent_count,
        "skipped_count": skipped,
        "alerts": alerts
    }
    
    save_json(SPIKE_LATEST_FILE, receipt)
    
    return {
        "result": "OK",
        "alerts": len(alerts),
        "sent": sent_count,
        "skipped": skipped
    }

if __name__ == "__main__":
    print(json.dumps(run_spike_push(), indent=2, ensure_ascii=False))
