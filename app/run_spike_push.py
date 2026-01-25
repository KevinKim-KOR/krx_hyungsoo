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
    """Mock Price Change"""
    val = random.uniform(-1.0, 1.0)
    # Occasional spike (5%)
    if random.random() < 0.05: 
        val = random.uniform(3.0, 5.0) * (1 if random.random() > 0.5 else -1)
        print(f"[DEBUG] Mock Spike for {ticker}: {val:.2f}%")
    return val


def check_cooldown(state: Dict, ticker: str, direction: str, cooldown_mins: int) -> bool:
    """쿨다운 체크"""
    key = f"{ticker}_{direction}"
    last_sent_str = state.get("last_sent", {}).get(key)
    
    if not last_sent_str:
        return True
        
    last_sent = datetime.fromisoformat(last_sent_str)
    if datetime.now() - last_sent > timedelta(minutes=cooldown_mins):
        return True
        
    return False


def update_cooldown(state: Dict, ticker: str, direction: str):
    """쿨다운 갱신"""
    key = f"{ticker}_{direction}"
    if "last_sent" not in state:
        state["last_sent"] = {}
    state["last_sent"][key] = datetime.now().isoformat()


def is_in_session(session_config: Dict) -> bool:
    """장중 여부 체크"""
    now = datetime.now()
    
    # 1. Day check
    if now.weekday() not in session_config.get("days", [0,1,2,3,4]):
        return False
        
    # 2. Time check
    current_time = now.strftime("%H:%M")
    start = session_config.get("start", "09:00")
    end = session_config.get("end", "15:30")
    
    return start <= current_time <= end


def run_spike_push() -> Dict:
    """Spike Push 실행"""
    ensure_dirs()
    
    # 1. Load Settings (Fail-Closed)
    from app.generate_spike_settings import load_spike_settings
    settings = load_spike_settings()
    
    if not settings:
        return {"result": "BLOCKED", "reason": "NO_SPIKE_SETTINGS"}
        
    if not settings.get("enabled", False):
        return {"result": "SKIPPED", "reason": "DISABLED_BY_SETTINGS"}
        
    # 2. Check Session
    if not is_in_session(settings.get("session_kst", {})):
        return {"result": "SKIPPED", "reason": "OUTSIDE_SESSION"}
        
    # 3. Load Watchlist
    watchlist_data = load_json(WATCHLIST_FILE)
    if not watchlist_data:
        return {"result": "BLOCKED", "reason": "NO_WATCHLIST"}
    
    items = watchlist_data.get("items", [])
    if not items:
        return {"result": "BLOCKED", "reason": "EMPTY_WATCHLIST"}
    
    # 4. Config values
    threshold_pct = settings.get("threshold_pct", 3.0)
    cooldown_minutes = settings.get("cooldown_minutes", 15)
    
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
        
        # Check triggers
        alert_type = None
        if change_pct >= threshold_pct:
            alert_type = "UP"
        elif change_pct <= -threshold_pct:
            alert_type = "DOWN"
            
        if alert_type:
            # Check cooldown
            if check_cooldown(state, ticker, alert_type, cooldown_minutes):
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
    
    # Send messages
    sent_count = 0
    if alerts:
        from app.providers.telegram_sender import send_telegram_message
        
        for alert in alerts:
            emoji = "🚀" if alert["type"] == "UP" else "📉"
            msg = f"{emoji} {alert['type']} {alert['name']}({alert['ticker']}) {alert['change_pct']:+.2f}%"
            
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
        "settings_used": {
            "threshold_pct": threshold_pct,
            "cooldown_minutes": cooldown_minutes
        },
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
