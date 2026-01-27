# -*- coding: utf-8 -*-
"""
app/run_holding_watch.py
Holding Watch Runner (Phase D-P.66)
"""
import sys
import json
import time
import socket
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Root path setup
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.providers.market_data import MarketDataProvider
from app.providers.telegram_sender import send_telegram_message
from app.generate_incident_push import generate_incident_push
from app.utils.logger import setup_logger

logger = setup_logger("holding_watch")

# Paths
STATE_DIR = BASE_DIR / "state"
REPORTS_DIR = BASE_DIR / "reports"
SETTINGS_FILE = STATE_DIR / "settings" / "latest" / "settings_latest.json"
PORTFOLIO_FILE = STATE_DIR / "portfolio" / "latest" / "portfolio_latest.json"
HOLDING_STATE_FILE = STATE_DIR / "holding_watch" / "holding_state.json"
SNAPSHOT_DIR = REPORTS_DIR / "ops" / "push" / "holding_watch" / "snapshots"
LATEST_FILE = REPORTS_DIR / "ops" / "push" / "holding_watch" / "latest" / "holding_watch_latest.json"

# Constants
exit_code = 0

def safe_read_json(path: Path) -> Optional[Dict]:
    if not path.exists(): return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        return None

def is_in_session(session_cfg: Dict[str, str], weekdays: List[int]) -> bool:
    """Check if current time is within session (KST)"""
    now = datetime.now()
    if now.weekday() not in weekdays:
        return False
        
    start_str = session_cfg.get("start", "09:10")
    end_str = session_cfg.get("end", "15:20")
    
    current_hm = now.strftime("%H:%M")
    return start_str <= current_hm <= end_str

def save_snapshot(data: Dict, latest: bool = True) -> str:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"holding_watch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = SNAPSHOT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    if latest:
        LATEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LATEST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    return f"reports/ops/push/holding_watch/snapshots/{filename}"

def main():
    global exit_code
    logger.info("Starting Holding Watch...")
    
    # 1. Load Resources (Settings, Portfolio)
    settings_all = safe_read_json(SETTINGS_FILE)
    if not settings_all:
        logger.error("No Settings found")
        print("BLOCKED: NO_SETTINGS")
        sys.exit(2)
        
    settings = settings_all.get("holding", {})
    if not settings.get("enabled", False):
        logger.info("Holding Watch Disabled")
        print("SKIP: DISABLED")
        sys.exit(0)
        
    # Session Check
    if not is_in_session(settings.get("session_kst", {}), settings.get("weekdays", [0,1,2,3,4])):
        # Force run capability? Maybe via arg. For now, strict session.
        logger.info("Outside Session")
        print("SKIP: OUTSIDE_SESSION")
        sys.exit(0)

    portfolio = safe_read_json(PORTFOLIO_FILE)
    if not portfolio or not portfolio.get("holdings"):
        logger.warning("No Portfolio found or empty")
        print("BLOCKED: NO_PORTFOLIO")
        # Fail-Closed Rule: BLOCKED is Exit 2
        sys.exit(2)

    # Load Previous State
    HOLDING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    holding_state = safe_read_json(HOLDING_STATE_FILE) or {}
    
    # 2. Market Data
    holdings = portfolio.get("holdings", [])
    # Normalize holdings list (in case it's dict)
    if isinstance(holdings, dict):
        holdings = list(holdings.values())
        
    tickers = [h["ticker"] for h in holdings if h.get("ticker")]
    if not tickers:
        print("SKIP: NO_TICKERS")
        sys.exit(0)
        
    provider = MarketDataProvider()
    market_map = provider.fetch_realtime(tickers)
    
    # Check Data Integrity
    if not market_map:
        logger.error("Market Data Fetch Failed (Empty)")
        generate_incident_push("MARKET_DATA_DOWN", "Run Holding Watch", "Empty response from provider")
        sys.exit(3)
        
    # 3. Watch Logic
    alerts = []
    
    pnl_up_limit = settings.get("pnl_up_pct", 5.0)
    pnl_down_limit = settings.get("pnl_down_pct", 3.0) # Assume positive input (e.g. 3.0 means -3%)
    trail_stop_limit = settings.get("trail_stop_pct", 2.0)
    use_trail_stop = settings.get("use_trail_stop", False)
    cooldown_sec = settings.get("cooldown_m", 15) * 60
    realert_delta = settings.get("realert_delta_pp", 1.0)
    
    now_ts = time.time()
    now_iso = datetime.now().isoformat()
    
    for h in holdings:
        ticker = h["ticker"]
        name = h["name"]
        avg_price = float(h.get("avg_price", 0))
        qty = float(h.get("quantity", 0))
        
        if avg_price <= 0 or qty <= 0:
            continue
            
        m_data = market_map.get(ticker)
        if not m_data: continue
        
        curr_price = float(m_data.get("price", 0))
        if curr_price <= 0: continue
        
        # Calc PnL
        pnl_pct = ((curr_price - avg_price) / avg_price) * 100
        pnl_val = (curr_price - avg_price) * qty
        market_val = curr_price * qty
        
        # State Tracking
        h_state = holding_state.get(ticker, {})
        max_pnl = float(h_state.get("max_pnl_seen", -999.0))
        
        # Update High Watermark (if trail enabled)
        if use_trail_stop:
            if pnl_pct > max_pnl:
                max_pnl = pnl_pct
                h_state["max_pnl_seen"] = max_pnl
        
        # Check Alert Conditions
        alert_type = None
        trigger_val = 0.0
        
        # 1. PNL UP
        if pnl_pct >= pnl_up_limit:
            alert_type = "PNL_UP"
            trigger_val = pnl_pct
            
        # 2. PNL DOWN (Note: pnl_down_limit is positive, so check <= -limit)
        elif pnl_pct <= -abs(pnl_down_limit):
            alert_type = "PNL_DOWN"
            trigger_val = pnl_pct
            
        # 3. TRAIL STOP
        elif use_trail_stop and (max_pnl - pnl_pct >= trail_stop_limit) and max_pnl > 0:
             # Ensure we are profitable or came from high point? Usually trail stop implies locking profit or limiting loss from peak.
             # Strict logic: Peak - Current >= Limit
             alert_type = "TRAIL_STOP"
             trigger_val = pnl_pct
             
        if not alert_type:
            # Update state just for heartbeat/values? No, only on alert or significant move?
            # Actually we should update max_pnl even if no alert
            holding_state[ticker] = h_state
            continue
            
        # Anti-Spam Logic
        last_alert_at = float(h_state.get("last_alert_ts", 0))
        last_alert_pnl = float(h_state.get("last_alert_pnl", 0))
        last_alert_type = h_state.get("last_alert_type", "")
        
        should_alert = False
        reason = ""
        
        # Fresh Alert OR Direction Change
        if (now_ts - last_alert_at > cooldown_sec) or (last_alert_type != alert_type):
            should_alert = True
            reason = "Fresh/Cooldown/TypeChange"
        else:
            # Re-alert Exception: Additional 1.0%p Move
            # Compare current pnl vs last alert pnl
            # Logic: If direction is UP, and pnl increased by delta
            # Logic: If direction is DOWN, and pnl decreased by delta
            
            delta = abs(pnl_pct - last_alert_pnl)
            if delta >= realert_delta:
                should_alert = True
                reason = f"Delta {delta:.2f}%p >= {realert_delta}%p"
                
        if should_alert:
            # Prepare Alert Data
            alerts.append({
                "ticker": ticker,
                "name": name,
                "type": alert_type,
                "pnl_pct": pnl_pct,
                "price": curr_price,
                "avg_price": avg_price,
                "qty": qty,
                "market_value_krw": market_val,
                "reason": reason,
                "last_alert_pnl": last_alert_pnl if last_alert_at > 0 else None,
                "formatted_msg": f"💼 {alert_type} {ticker} {name} {pnl_pct:+.2f}% (평단 {int(avg_price):,} / 현재 {int(curr_price):,})"
            })
            
            # Update State
            h_state["last_alert_ts"] = now_ts
            h_state["last_alert_pnl"] = pnl_pct
            h_state["last_alert_type"] = alert_type
            h_state["last_alert_iso"] = now_iso
            
        holding_state[ticker] = h_state

    # 4. Save State Logic
    try:
        with open(HOLDING_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(holding_state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"State save failed: {e}")

    # 5. Send Alerts
    execution_result = "OK"
    execution_reason = "ALERTS_GENERATED" if alerts else "NO_ALERTS"
    
    snapshot_data = {
        "asof": now_iso,
        "execution_result": execution_result,
        "execution_reason": execution_reason,
        "checked_count": len(holdings),
        "alerts_generated": len(alerts),
        "alerts": alerts,
        "evidence_refs": [
            "state/portfolio/latest/portfolio_latest.json",
            "state/settings/latest/settings_latest.json"
        ]
    }
    
    # 1) Save Snapshot First (for ref)
    snapshot_ref = save_snapshot(snapshot_data)
    
    if alerts:
        # Send Telegram
        msgs = []
        for a in alerts:
            # Ops Format
            # 💼 HOLDING ALERT: PNL_UP
            # 005930 삼성전자 +5.2%
            # (평단 60,000 / 현재 63,120) | 보유 10주
            # Cond: PNL_UP(5.0%)
            # Re-alert: +4.1% -> +5.2% (Δ1.1%p)
            
            re_alert_str = ""
            if a["last_alert_pnl"] is not None:
                delta = abs(a["pnl_pct"] - a["last_alert_pnl"])
                re_alert_str = f"\n🔄 Re-alert: {a['last_alert_pnl']:+.2f}% → {a['pnl_pct']:+.2f}% (Δ{delta:.1f}%p)"
                
            msg = (
                f"💼 HOLDING ALERT: {a['type']}\n"
                f"{a['ticker']} {a['name']} {a['pnl_pct']:+.2f}%\n"
                f"(평단 {int(a['avg_price']):,} / 현재 {int(a['price']):,}) | 보유 {int(a['qty']):,}주\n"
                f"Value: {int(a['market_value_krw']/10000):,}만원\n"
                f"{re_alert_str}"
            )
            msgs.append(msg)
            
        # Combine short messages or send individually
        # Let's send individually to avoid monster messages, but maybe batch 2-3?
        # User said "한 메시지로 묶어" in future D-P.68. For now individually is safer for clarity.
        
        full_msg = "\n\n".join(msgs)
        full_msg += f"\n\n🔍 Evidence: {snapshot_ref}"
        
        # Send and Capture Receipt
        res = send_telegram_message(full_msg)
        
        # Update Snapshot with Receipt
        if res.get("success"):
            snapshot_data["delivery_actual"] = "TELEGRAM"
            snapshot_data["send_receipt"] = {
                "message_id": res.get("message_id"),
                "sent_at": datetime.now().isoformat(),
                "provider": "TELEGRAM"
            }
        else:
            snapshot_data["delivery_actual"] = "FAILED"
            snapshot_data["send_receipt"] = {
                "error": res.get("error"),
                "sent_at": datetime.now().isoformat()
            }
            logger.error(f"Telegram Failed: {res.get('error')}")

        # Re-save snapshot with receipt
        save_snapshot(snapshot_data, latest=True)

        logger.info(f"Sent {len(alerts)} alerts (Success={res.get('success')})")
        print(f"OK: Alerts={len(alerts)} Reason=ALERTS_GENERATED")
    else:
        logger.info("No alerts triggered")
        print("OK: Alerts=0 Reason=NO_ALERTS")

if __name__ == "__main__":
    main()
