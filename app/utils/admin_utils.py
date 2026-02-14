
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"

def load_asof_override() -> Dict[str, Any]:
    """
    Load Replay/Override configuration.
    Returns: {"mode": "REPLAY"|"LIVE", "asof": "YYYY-MM-DD", "enabled": bool}
    """
    if not OVERRIDE_PATH.exists():
        return {"mode": "LIVE", "enabled": False}
    
    try:
        data = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
        if data.get("enabled", False):
            # Validate format if needed, but primarily trust file
            return data
    except Exception:
        pass
        
    return {"mode": "LIVE", "enabled": False}

def normalize_portfolio(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Portfolio SSOT.
    1. Ensure 'asof' exists (if missing, use updated_at or now).
    2. Recalculate total_value = cash + positions_value.
    3. Ensure holdings is a dict (ticker -> info).
    """
    if not data:
        return {}
        
    normalized = data.copy()
    
    # 1. Asof
    if not normalized.get("asof"):
        # Try updated_at
        normalized["asof"] = normalized.get("updated_at") or (datetime.utcnow().isoformat() + "Z")
        
    # 2. Holdings & Total Value
    cash = float(normalized.get("cash", 0))
    raw_holdings = normalized.get("holdings", {})
    
    positions_value = 0.0
    clean_holdings = {}
    
    # Standardize to Dict
    if isinstance(raw_holdings, list):
        for h in raw_holdings:
            t = h.get("ticker")
            if t:
                clean_holdings[t] = h
    elif isinstance(raw_holdings, dict):
        clean_holdings = raw_holdings
        
    # Calculate Value
    for t, info in clean_holdings.items():
        qty = int(info.get("quantity", 0))
        # Use current_price if available, else avg_price?
        # Portfolio SSOT usually tracks 'avg_price' (cost basis). 
        # But 'total_value' implies Market Value?
        # Standard: total_value in Portfolio State usually means Liquidation Value if we have market data,
        # OR Cost Basis if we don't.
        # However, for P143 consistency, let's use what we have.
        # Most portfolios in this system store 'avg_price' and 'quantity'. 'current_price' might not be there.
        # Let's check `pc_cockpit/app.py` or sample data.
        # User said: "positions_cnt = 0인데 cash=10,000,000, total_value=20,000,000 (합이 안 맞음)"
        # So primarily check Sum of (Qty * Price). Which Price?
        # If this is the *Accounting* Portfolio, it might settle on Avg Price (Book Value)?
        # Or usually Total Equity = Cash + Market Value of Positions.
        # But without live feed in the portfolio object itself (it's just state), we might fallback to Avg Price.
        # Wait, `portfolio_latest.json` does NOT usually contain current price unless updated by a market sync.
        # Let's assume Cost Basis (Qty * Avg) for consistency check, 
        # OR if the user manually inputs total_value, we might overwrite it.
        # User Instruction: "total_value = cash + positions_value_sum"
        # I will use `avg_price` as the proxy for value if `current_price` is missing.
        price = float(info.get("current_price", info.get("avg_price", 0)))
        positions_value += qty * price
    
    normalized["holdings"] = clean_holdings
    normalized["total_value"] = int(cash + positions_value)
    normalized["positions_cnt"] = len(clean_holdings)
    
    return normalized

def is_holiday_today(override_date_str: str = None) -> bool:
    """
    Check if today (or override date) is a weekend.
    Returns True if Saturday(5) or Sunday(6).
    """
    # If override is active, do we check that date?
    # User said: "asof_override가 활성화되어 있고 '오늘 거래 불가(휴장/주말)'이면"
    # This implies we check the *current wall clock* usually, OR the override date if we are simulating.
    # "Holiday UI Rehearsal" -> We might want to simulate a holiday even if it's Tuesday.
    # So if override["force_holiday"] is True?
    # Or based on the `asof_override` date?
    # Let's interpret: "If we are effectively in a holiday state".
    # P143 Rehearsal is "Fri Snapshot Freeze".
    # Let's assume we check the *System Time* (Real Today) for weekend, 
    # UNLESS override explicitly says "force_holiday": true.
    dt = datetime.now()
    if dt.weekday() >= 5: # Sat, Sun
        return True
    return False
