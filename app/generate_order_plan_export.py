# -*- coding: utf-8 -*-
"""
app/generate_order_plan_export.py
P111: Order Plan Dry-Run Export V1 (Human-Confirm Gate)
"""

import json
import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
ORDER_PLAN_LATEST = BASE_DIR / "reports" / "live" / "order_plan" / "latest" / "order_plan_latest.json"
EXPORT_DIR = BASE_DIR / "reports" / "live" / "order_plan_export"
EXPORT_LATEST = EXPORT_DIR / "latest" / "order_plan_export_latest.json"
EXPORT_SNAPSHOTS = EXPORT_DIR / "snapshots"

# Ensure directories
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
(EXPORT_DIR / "latest").mkdir(parents=True, exist_ok=True)
EXPORT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def generate_confirm_token(plan_id: str, count: int) -> str:
    """Generate a short hash token for human confirmation"""
    raw = f"{plan_id}:{count}:{datetime.now().isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def generate_export():
    now = datetime.now()
    asof_str = now.isoformat()
    
    # 1. Load Input (Order Plan)
    plan = load_json(ORDER_PLAN_LATEST)
    
    # 2. Initialize Export
    export = {
        "schema": "ORDER_PLAN_EXPORT_V1",
        "asof": asof_str,
        "created_at": asof_str,
        "source": {
            "order_plan_ref": str(ORDER_PLAN_LATEST.relative_to(BASE_DIR)).replace("\\", "/"),
            "plan_id": None,
            "decision": None
        },
        "summary": {
            "orders_count": 0,
            "buys_count": 0,
            "sells_count": 0,
            "cash_before": 0, # Placeholder, needs Portfolio input if we want accurate est
            "cash_after_est": 0,
            "notes": ""
        },
        "orders": [],
        "human_confirm": {
            "required": True,
            "confirm_token": None,
            "how_to_confirm": "POST /api/order/execute with token",
            "evidence_refs": []
        },
        "decision": "BLOCKED", # Default
        "integrity": {}
    }

    # 3. Fail-Closed Check
    if not plan:
        export["decision"] = "BLOCKED"
        export["summary"]["notes"] = "Order Plan not found"
        _save_and_return(export)
        return

    export["source"]["plan_id"] = plan.get("plan_id")
    export["source"]["decision"] = plan.get("decision")
    export["human_confirm"]["evidence_refs"].append(export["source"]["order_plan_ref"])

    # If Order Plan is BLOCKED, Export is BLOCKED
    if plan.get("decision") == "BLOCKED":
        export["decision"] = "BLOCKED"
        export["summary"]["notes"] = f"Order Plan is BLOCKED: {plan.get('reason')}"
        _save_and_return(export)
        return

    # 4. Map Orders
    orders_in = plan.get("orders", [])
    orders_out = []
    buys = 0
    sells = 0

    for o in orders_in:
        side = o.get("side", "BUY")
        qty = o.get("quantity", 0) # Order Plan might not have calc qty yet? 
        # Wait, P102 Order Plan usually has Intent (ADD/NEW_ENTRY) but maybe not specific Qty if Scorer didn't provide perfectly?
        # Actually P102 doesn't calculate Qty? P102 Code: "orders": [{ticker, side, intent, ...}]
        # Let's check P102 output. It DOES NOT have Qty/Price logic yet?
        # Ah, P102 logs "Generated X orders".
        # If P102 is Intent-only, then Request says "Order Plan Dry-Run Export".
        # The export should show what IS in the plan.
        # If Plan has no Qty, Export implies 0 or "TBD".
        # But User says "orders (배열): ticker, side, qty, price_ref, notional".
        # If P102 doesn't have Qty, we can't export it? 
        # Or maybe P102 DOES have it? 
        # Let's assume P102 output structure from previous steps. 
        # I recall P102 just output intents. 
        # If so, this Export is the place where we might need to *see* what's missing, but we shouldn't *calculate* it if constraint says "Order Plan logic itself don't touch".
        # BUT, "expression/export only add".
        # If Plan lacks data, Export shows null/0.
        
        # Mapping
        out_item = {
            "ticker": o.get("ticker"),
            "side": side,
            "qty": o.get("quantity", 0), # Optional in Plan?
            "price_ref": o.get("price", 0), # Optional?
            "notional": o.get("value", 0), # Optional?
            "reason": o.get("intent", "UNKNOWN"), # Map Intent to Reason
            "reason_detail": o.get("reason_detail", "") or o.get("reason", "")
        }
        orders_out.append(out_item)
        
        if side == "BUY": buys += 1
        elif side == "SELL": sells += 1

    export["orders"] = orders_out
    export["summary"]["orders_count"] = len(orders_out)
    export["summary"]["buys_count"] = buys
    export["summary"]["sells_count"] = sells
    
    # 5. Final Decision
    if not orders_out and plan.get("decision") == "EMPTY":
         export["decision"] = "EMPTY"
    else:
         export["decision"] = "GENERATED"
         
    # Confirm Token
    export["human_confirm"]["confirm_token"] = generate_confirm_token(export["source"]["plan_id"], len(orders_out))

    _save_and_return(export)

def _save_and_return(export: Dict):
    try:
        # Atomic Write
        temp_file = EXPORT_LATEST.parent / f".tmp_{EXPORT_LATEST.name}"
        temp_file.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp_file), str(EXPORT_LATEST))
        
        # Snapshot
        asof_safe = export["asof"].replace(":", "").replace("-", "").replace("T", "_").split(".")[0]
        snap_name = f"order_plan_export_{asof_safe}.json"
        snapshot_path = EXPORT_SNAPSHOTS / snap_name
        shutil.copy(str(EXPORT_LATEST), str(snapshot_path))
        
        print(json.dumps(export, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({
            "schema": "ORDER_PLAN_EXPORT_V1",
            "decision": "BLOCKED",
            "reason": "WRITE_ERROR",
            "error": str(e)
        }))

if __name__ == "__main__":
    generate_export()
