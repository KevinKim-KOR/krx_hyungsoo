# -*- coding: utf-8 -*-
"""
app/generate_settings.py
Unified Settings Generator (Spike + Holding)
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, Any

# Root setup
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.utils.logger import setup_logger

logger = setup_logger("generate_settings")

SETTINGS_DIR = BASE_DIR / "state" / "settings" / "latest"
SETTINGS_FILE = SETTINGS_DIR / "settings_latest.json"

DEFAULT_SPIKE = {
    "enabled": False,
    "threshold_pct": 3.0,
    "cooldown_minutes": 15,
    "session_kst": {"start": "09:10", "end": "15:20"},
    "options": {
        "include_value_volume": True,
        "include_deviation": False,
        "include_portfolio_context": True
    }
}

DEFAULT_HOLDING = {
    "enabled": False,
    "pnl_up_pct": 5.0,
    "pnl_down_pct": 3.0,
    "use_trail_stop": False,
    "trail_stop_pct": 2.0,
    "cooldown_m": 15,
    "realert_delta_pp": 1.0,
    "session_kst": {"start": "09:10", "end": "15:20"},
    "weekdays": [0, 1, 2, 3, 4],
    "options": {
        "include_trade_value": True,
        "include_deviation": True,
        "include_pnl": True
    }
}

def load_settings() -> Dict[str, Any]:
    """Load existing settings or return default skeleton"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
    
    # Return Default
    return {
        "schema": "SETTINGS_V1",
        "updated_at": datetime.now(KST).isoformat(),
        "spike": DEFAULT_SPIKE.copy(),
        "holding": DEFAULT_HOLDING.copy()
    }

def upsert_settings(new_data: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
    """
    Upsert settings (Merge input with existing)
    new_data can contain 'spike', 'holding', or both.
    """
    if not confirm:
        return {"result": "BLOCKED", "message": "Confirm required"}

    current = load_settings()
    
    # Merge Spike
    if "spike" in new_data:
        current["spike"].update(new_data["spike"])
        
    # Merge Holding
    if "holding" in new_data:
        current["holding"].update(new_data["holding"])
        
    current["updated_at"] = datetime.now(KST).isoformat()
    current["schema"] = "SETTINGS_V1" # Enforce schema
    
    # Validation (Basic)
    if current["holding"]["pnl_down_pct"] < 0:
         current["holding"]["pnl_down_pct"] = abs(current["holding"]["pnl_down_pct"]) # Enforce positive value for logic usage (usually input as 3.0 for -3%)
         
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Settings saved: {SETTINGS_FILE}")
        return {"result": "OK", "path": str(SETTINGS_FILE), "data": current}
        
    except Exception as e:
        logger.error(f"Save failed: {e}")
        return {"result": "FAILED", "reason": str(e)}

if __name__ == "__main__":
    # CLI Util for testing
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Initialize default settings")
    args = parser.parse_args()
    
    if args.init:
        res = upsert_settings({}, confirm=True)
        print(json.dumps(res, indent=2))
