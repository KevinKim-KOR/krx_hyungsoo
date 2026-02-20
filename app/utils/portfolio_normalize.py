
import json
import os
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
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
        normalized["asof"] = normalized.get("updated_at") or (datetime.now(KST).isoformat())
        
    # 2. Holdings & Total Value
    cash = float(normalized.get("cash", 0))
    positions = normalized.get("positions", [])
    
    positions_value = 0.0
    clean_positions = []
    
    if isinstance(positions, list):
        for p in positions:
            t = p.get("ticker")
            if t:
                qty = int(p.get("quantity", 0))
                # Price Hierarchy: current_price > average_price > 0
                price = float(p.get("current_price", p.get("average_price", 0)))
                val = qty * price
                positions_value += val
                
                # Weight Pct Recalc (Approximate until total is final)
                # We will set 0 for now, or calc later? 
                # Better to calc only if total > 0.
                clean_positions.append(p)

    # Recalculate Total
    total_val = cash + positions_value
    
    # Update Weights
    for p in clean_positions:
        t = p.get("ticker")
        qty = int(p.get("quantity", 0))
        price = float(p.get("current_price", p.get("average_price", 0)))
        val = qty * price
        if total_val > 0:
            p["weight_pct"] = round(val / total_val, 4)
        else:
            p["weight_pct"] = 0.0
            
    normalized["positions"] = clean_positions
    normalized["total_value"] = int(total_val)
    normalized["positions_cnt"] = len(clean_positions)
    
    return normalized

def is_holiday_today(override_date_str: str = None, simulate_trade_day: bool = False) -> bool:
    """
    Check if today (or override date) is a weekend.
    Returns True if Saturday(5) or Sunday(6).
    
    P145: If simulate_trade_day=True, always returns False
    (= forces "trade day" mode, allowing full Daily Loop even on weekends).
    """
    if simulate_trade_day:
        return False
    
    dt = datetime.now(KST)
    if dt.weekday() >= 5: # Sat, Sun
        return True
    return False

