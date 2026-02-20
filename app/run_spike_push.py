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
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
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
SPIKE_LOG_DIR = BASE_DIR / "reports" / "ops" / "push" / "spike_watch"
SPIKE_LATEST_FILE = SPIKE_LOG_DIR / "latest" / "spike_watch_latest.json"


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


# Portfolio
PORTFOLIO_FILE = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"

def get_portfolio_context() -> Dict:
    data = load_json(PORTFOLIO_FILE)
    if not data or "holdings" not in data:
        return {}
    return data["holdings"]


def check_cooldown(state: Dict, ticker: str, direction: str, cooldown_mins: int) -> bool:
    """쿨다운 체크 (종목+방향 키 사용)"""
    key = f"{ticker}_{direction}"
    last_sent_str = state.get("last_sent", {}).get(key)
    
    if not last_sent_str:
        return True
        
    last_sent = datetime.fromisoformat(last_sent_str)
    # Strict check: Must be greater than cooldown mins
    if datetime.now(KST) - last_sent > timedelta(minutes=cooldown_mins):
        return True
        
    return False


def format_money_kr(val):
    if val >= 100000000: # 1억
        return f"{val/100000000:.1f}억"
    if val >= 1000000: # 100만
        return f"{val/1000000:.0f}백만"
    return f"{val:,.0f}"


def update_cooldown(state: Dict, ticker: str, direction: str):
    """쿨다운 갱신"""
    key = f"{ticker}_{direction}"
    if "last_sent" not in state:
        state["last_sent"] = {}
    state["last_sent"][key] = datetime.now(KST).isoformat()


def is_in_session(session_config: Dict) -> bool:
    """장중 여부 체크"""
    now = datetime.now(KST)
    
    # 1. Day check
    if now.weekday() not in session_config.get("days", [0,1,2,3,4]):
        return False
        
    # 2. Time check
    current_time = now.strftime("%H:%M")
    start = session_config.get("start", "09:00")
    end = session_config.get("end", "15:30")
    
    return start <= current_time <= end


def run_spike_push() -> Dict:
    """Spike Push 실행 (Practical)"""
    ensure_dirs()
    
    # Init receipt fields
    receipt_status = "UNKNOWN"
    receipt_reason = ""
    alerts = []
    sent_count = 0
    skipped_cooldown = 0
    settings = {}
    
    try:
        # 1. Load Settings
        from app.generate_spike_settings import load_spike_settings
        settings = load_spike_settings() or {}
        if not settings:
            receipt_status = "BLOCKED"
            receipt_reason = "NO_SPIKE_SETTINGS"
            return {"result": receipt_status, "reason": receipt_reason}
            
        if not settings.get("enabled", False):
            receipt_status = "SKIPPED"
            receipt_reason = "DISABLED_BY_SETTINGS"
            return {"result": receipt_status, "reason": receipt_reason}
            
        # 2. Check Session
        if not is_in_session(settings.get("session_kst", {})):
            receipt_status = "SKIPPED"
            receipt_reason = "OUTSIDE_SESSION"
            return {"result": receipt_status, "reason": receipt_reason}
            
        # 3. Load Watchlist
        watchlist_data = load_json(WATCHLIST_FILE)
        if not watchlist_data:
            receipt_status = "BLOCKED"
            receipt_reason = "NO_WATCHLIST"
            return {"result": receipt_status, "reason": receipt_reason}
        
        items = watchlist_data.get("items", [])
        if not items:
            receipt_status = "BLOCKED"
            receipt_reason = "EMPTY_WATCHLIST"
            return {"result": receipt_status, "reason": receipt_reason}

        # 4. Filter Targets
        targets = [i["ticker"] for i in items if i.get("enabled", True)]
        if not targets:
            receipt_status = "SKIPPED"
            receipt_reason = "NO_ENABLED_TARGETS"
            return {"result": receipt_status, "reason": receipt_reason}
        
        # 5. Fetch Market Data & Portfolio
        provider_type = settings.get("market_data", {}).get("provider", "naver")
        from app.providers.market_data import MarketDataProvider
        provider = MarketDataProvider(provider_type)
        market_data = provider.fetch_realtime(targets)
        
        if not market_data:
            receipt_status = "BLOCKED"
            receipt_reason = "MARKET_DATA_FAILED"
            # Incident Push Logic (Simplified)
            try:
                 import requests
                 requests.post("http://localhost:8000/api/push/incident/run", 
                               json={"type": "MARKET_DATA_DOWN", "message": "Spike Watch: Market Data Fetch Failed"},
                               timeout=2)
            except: pass
            return {"result": receipt_status, "reason": receipt_reason}
            
        portfolio_holdings = {}
        if settings.get("display", {}).get("include_portfolio_context", True):
            portfolio_holdings = get_portfolio_context()
            
        # 6. Check Logic
        threshold_pct = settings.get("threshold_pct", 3.0)
        cooldown_minutes = settings.get("cooldown_minutes", 15)
        
        state = load_json(SPIKE_STATE_FILE) or {}
        
        for item in items:
            ticker = item["ticker"]
            if ticker not in targets or ticker not in market_data:
                continue
                
            md = market_data[ticker]
            try:
                current_pct = float(md.get("change_pct", 0))
            except:
                continue
                
            # Trigger Determination
            alert_type = None
            
            # 1. Base Spike Trigger
            if current_pct >= threshold_pct:
                alert_type = "UP"
            elif current_pct <= -threshold_pct:
                alert_type = "DOWN"
                
            if alert_type:
                # Check Cooldown & Ride
                key = f"{ticker}_{alert_type}"
                last_sent_str = state.get("last_sent", {}).get(key)
                last_pct = state.get("last_pct", {}).get(key, 0.0)
                
                should_alert = False
                is_ride = False
                
                if not last_sent_str:
                    # First time
                    should_alert = True
                else:
                    last_sent = datetime.fromisoformat(last_sent_str)
                    time_passed = datetime.now(KST) - last_sent
                    
                    if time_passed > timedelta(minutes=cooldown_minutes):
                        # Cooldown expired -> New Spike
                        should_alert = True
                    else:
                        # In Cooldown -> Check Ride (Significant Advance)
                        if alert_type == "UP":
                            if current_pct >= last_pct + 1.0:
                                should_alert = True
                                is_ride = True
                        elif alert_type == "DOWN":
                            if current_pct <= last_pct - 1.0:
                                should_alert = True
                                is_ride = True
                
                if should_alert:
                    # Enrich Message
                    name = md.get("name", item["name"])
                    price = md.get("price", 0)
                    vol = md.get("volume", 0)
                    val_krw = md.get("value_krw", 0)
                    
                    # Deviation (ETF)
                    nav_info = ""
                    if settings.get("display", {}).get("include_deviation", True) and md.get("nav"):
                        try:
                            nav = float(md["nav"])
                            if nav > 0:
                                diff = price - nav
                                diff_pct = (diff / nav) * 100
                                nav_info = f"\\n📊 괴리: {diff_pct:+.2f}% (NAV {nav:,.0f})"
                        except: pass

                    # Holding Context
                    holding_info = ""
                    if ticker in portfolio_holdings:
                        h = portfolio_holdings[ticker]
                        try:
                            qty = int(h.get("qty", 0))
                            avg = float(h.get("avg_price", 0))
                            pnl_pct = ((price - avg) / avg * 100) if avg > 0 else 0
                            holding_info = f"\\n💼 보유: {qty}주 ({pnl_pct:+.1f}%)"
                        except:
                            holding_info = "\\n💼 보유중"
                    
                    # Construct Message
                    title_emoji = "🚀" if not is_ride else "🏇"
                    if alert_type == "DOWN": title_emoji = "📉" if not is_ride else "⛷️"
                    type_str = f"{alert_type}" if not is_ride else f"RIDE {alert_type}"
                    
                    msg_lines = [
                        f"{title_emoji} {type_str} {name} {current_pct:+.2f}% ({price:,.0f})",
                    ]
                    
                    if settings.get("display", {}).get("include_value_volume", True):
                        val_str = format_money_kr(val_krw) if val_krw > 0 else f"{vol:,}주"
                        msg_lines.append(f"💰 {val_str}")
                        
                    if nav_info: msg_lines.append(nav_info)
                    if holding_info: msg_lines.append(holding_info)
                    
                    alerts.append({
                        "ticker": ticker,
                        "msg": " ".join(msg_lines), 
                        "full_msg": "\\n".join(msg_lines), 
                        "type": "RIDE" if is_ride else "SPIKE"
                    })
                    
                    update_cooldown(state, ticker, alert_type)
                    if "last_pct" not in state: state["last_pct"] = {}
                    state["last_pct"][key] = current_pct

                else:
                    skipped_cooldown += 1
                    
        # Save State
        save_json(SPIKE_STATE_FILE, state)

        # Send
        if alerts:
            from app.providers.telegram_sender import send_telegram_message
            for alert in alerts:
                res = send_telegram_message(alert["full_msg"])
                if res.get("success"):
                    sent_count += 1
                    print(f"[SPIKE] Sent: {alert['ticker']} {alert['type']}")
                else:
                    print(f"[SPIKE] Fail: {alert['ticker']}")
                    
        receipt_status = "OK"
        if not alerts:
            if skipped_cooldown > 0:
                receipt_reason = "COOLDOWN_ACTIVE"
            else:
                receipt_reason = "NO_ALERTS"
        else:
            receipt_reason = "ALERTS_GENERATED"

        return {
            "result": "OK", 
            "reason": receipt_reason,
            "alerts": len(alerts), 
            "sent": sent_count, 
            "skipped": skipped_cooldown
        }

    finally:
        # ALWAYS Save Receipt
        # Exception handling
        if not receipt_status or receipt_status == "UNKNOWN":
             receipt_status = "FAILED"
             receipt_reason = "EXCEPTION"

        receipt = {
            "schema": "SPIKE_PUSH_RECEIPT_V1_3",
            "asof": datetime.now(KST).isoformat(),
            "settings_used": settings.get("display", {}) if settings else {},
            "execution_result": receipt_status,
            "execution_reason": receipt_reason,
            "alerts_count": len(alerts),
            "sent_count": sent_count,
            "skipped_count": skipped_cooldown,
            "alerts_log": [a["msg"] for a in alerts],
            "delivery_actual": "TELEGRAM" if sent_count > 0 else ("NONE" if not alerts else "FAILED"),
            "send_receipt": {
                 "sent_at": datetime.now(KST).isoformat(),
                 "message_count": sent_count,
                 "provider": "TELEGRAM"
            }
        }
        save_json(SPIKE_LATEST_FILE, receipt)

if __name__ == "__main__":
    print(json.dumps(run_spike_push(), indent=2, ensure_ascii=False))
