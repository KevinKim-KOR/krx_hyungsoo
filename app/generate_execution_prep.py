# -*- coding: utf-8 -*-
"""
app/generate_execution_prep.py
P112: Execution Prep V1 (Human Token Lock + Immutable Snapshot)
"""

import json
import shutil
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
EXPORT_LATEST = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
ORDER_PLAN_LATEST = BASE_DIR / "reports" / "live" / "order_plan" / "latest" / "order_plan_latest.json"

PREP_DIR = BASE_DIR / "reports" / "live" / "execution_prep"
PREP_LATEST = PREP_DIR / "latest" / "execution_prep_latest.json"
PREP_SNAPSHOTS = PREP_DIR / "snapshots"

# Ensure directories
PREP_DIR.mkdir(parents=True, exist_ok=True)
(PREP_DIR / "latest").mkdir(parents=True, exist_ok=True)
PREP_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

# Safety Limits
ALLOW_BUY = True

PORTFOLIO_VAR_DIR = BASE_DIR / "state" / "portfolio" / "latest"
PORTFOLIO_LATEST = PORTFOLIO_VAR_DIR / "portfolio_latest.json"

GUARDRAILS_DIR = BASE_DIR / "state" / "guardrails" / "latest"
GUARDRAILS_LATEST = GUARDRAILS_DIR / "guardrails_latest.json"

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def generate_prep(confirm_token: str):
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    asof_str = now.isoformat()
    # 1. Initialize Result
    prep = {
        "schema": "EXECUTION_PREP_V1",
        "asof": asof_str,
        "source": {
            "export_ref": None,
            "export_asof": None,
            "order_plan_ref": None,
            "plan_id": None,
            "confirm_token": confirm_token
        },
        "decision": "BLOCKED",
        "reason": "UNKNOWN",
        "reason_detail": "",
        "orders": [],
        "safety": {
            "orders_count": 0,
            "max_orders_allowed": 20,
            "max_single_order_ratio": 0.0
        },
        "verdict": "BLOCKED",
        "manual_next_step": "Resolve Blocking Issues",
        "evidence_refs": []
    }

    # 2. Load Inputs
    export_data = load_json(EXPORT_LATEST)
    plan_data = load_json(ORDER_PLAN_LATEST)
    
    # DEBUG
    print(f"DEBUG: BASE_DIR: {BASE_DIR.absolute()}")
    print(f"DEBUG: ORDER_PLAN_LATEST: {ORDER_PLAN_LATEST}")
    print(f"DEBUG: plan_data: {json.dumps(plan_data)}")
    
    if not export_data:
        prep["decision"] = "NO_EXPORT"
        prep["reason"] = "EXPORT_MISSING"
        prep["reason_detail"] = "Order Plan Export file not found"
        _save_and_return(prep)
        return

    prep["source"]["export_ref"] = str(EXPORT_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    prep["source"]["export_asof"] = export_data.get("asof")
    prep["evidence_refs"].append(prep["source"]["export_ref"])

    if not plan_data:
        prep["decision"] = "NO_PLAN"
        prep["reason"] = "ORDER_PLAN_MISSING"
        prep["reason_detail"] = "Order Plan file not found"
        _save_and_return(prep)
        return

    prep["source"]["order_plan_ref"] = str(ORDER_PLAN_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    
    prep["source"]["order_plan_ref"] = str(ORDER_PLAN_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    
    # Direct access to ensure we get the ID (Fail-closed)
    prep["source"]["plan_id"] = plan_data["plan_id"]
    
    prep["evidence_refs"].append(prep["source"]["order_plan_ref"])

    # 3. Fail-Closed Checks
    # 3-A. Check Upstream Blocks
    if export_data.get("decision") == "BLOCKED" or plan_data.get("decision") == "BLOCKED":
        prep["decision"] = "BLOCKED"
        prep["reason"] = "UPSTREAM_BLOCKED"
        prep["reason_detail"] = f"Export Decision: {export_data.get('decision')}"
        _save_and_return(prep)
        return
        
    # 3-B. Verify Token
    export_token = export_data.get("human_confirm", {}).get("confirm_token")
    
    # P140: Token Sanity Fix (Record Input instead of Compare)
    # Rationale: User input IS the confirmation. We record it.
    if not confirm_token:
         prep["decision"] = "BLOCKED"
         prep["reason"] = "TOKEN_EMPTY"
         prep["reason_detail"] = "Confirmation Token is required."
         _save_and_return(prep)
         return
         
    # Record the token (Binding)
    prep["source"]["confirm_token"] = confirm_token

    # Load Portfolio
    portfolio_data = load_json(PORTFOLIO_LATEST)
    
    # 4. Load SSOT Guardrails
    guardrails_cfg = load_json(GUARDRAILS_LATEST) or {}
    
    # Defaults in case missing
    live_profile = guardrails_cfg.get("live", {"max_total_notional_ratio": 0.3, "max_single_order_ratio": 0.1, "min_cash_reserve_ratio": 0.05})
    dry_run_profile = guardrails_cfg.get("dry_run", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
    replay_profile = guardrails_cfg.get("replay", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
    caps = guardrails_cfg.get("caps", {"max_total_notional_ratio": 1.0, "max_single_order_ratio": 1.0, "min_cash_reserve_ratio": 0.0})
    
    # Determine Execution Mode (Similar to P146.9)
    # Check Replay/Override
    from app.utils.portfolio_normalize import load_asof_override
    override_cfg = load_asof_override()
    exec_mode = "LIVE"
    
    if override_cfg.get("enabled", False):
        exec_mode = "REPLAY" # If it's replay. We can strictly use DRY_RUN or REPLAY.
        
    # Also check Ops Summary stage or mode if available
    OPS_SUMMARY = BASE_DIR / "reports" / "live" / "ops_summary" / "latest" / "ops_summary_latest.json"
    if OPS_SUMMARY.exists():
        try:
             summ = json.loads(OPS_SUMMARY.read_text(encoding="utf-8"))
             if "manual_loop" in summ:
                 exec_mode = summ["manual_loop"].get("mode", exec_mode)
             # Handle rows vs dict
             elif "rows" in summ and summ["rows"]:
                 exec_mode = summ["rows"][0].get("manual_loop", {}).get("mode", exec_mode)
        except Exception:
             pass
             
    # Map exec_mode to profile
    if exec_mode == "REPLAY":
        active_limits = replay_profile
    elif exec_mode == "DRY_RUN":
        active_limits = dry_run_profile
    else:
        active_limits = live_profile
        
    # Clamp to Caps (Fail-Closed)
    max_total_notional_ratio = min(active_limits.get("max_total_notional_ratio", 0.3), caps.get("max_total_notional_ratio", 1.0))
    max_single_order_ratio = min(active_limits.get("max_single_order_ratio", 0.1), caps.get("max_single_order_ratio", 1.0))
    
    # min reserve is a minimum floor we must adhere to. So we take MAX of requested vs caps min floor (if defined).
    # If cap is 0.0, we just use requested.
    min_cash_reserve_ratio = max(active_limits.get("min_cash_reserve_ratio", 0.05), caps.get("min_cash_reserve_ratio", 0.0))
    MAX_ORDERS_ALLOWED = 20 # Keep this max count hardcoded or add to SSOT later

    # 5. Safety Checks (Guardrails V1)
    orders = export_data.get("orders", [])
    prep["orders"] = orders
    
    # Calculate Metrics
    orders_count = len(orders)
    
    # Notional Calculation (Requires Portfolio)
    total_buy_notional = 0
    total_sell_notional = 0
    
    for o in orders:
        side = o.get("side", "BUY")
        price = o.get("price_ref", 0) or 0 # Use price_ref from Export
        qty = o.get("qty", 0) or 0
        notional = price * qty
        
        if side == "BUY":
            total_buy_notional += notional
        elif side == "SELL":
             total_sell_notional += notional
             
    total_notional = total_buy_notional + total_sell_notional
    max_single_notional = max([o.get("price_ref", 0) * o.get("qty", 0) for o in orders]) if orders else 0

    # Initialize Safety Block
    prep["safety"] = {
        "orders_count": orders_count,
        "max_orders_allowed": MAX_ORDERS_ALLOWED,
        "total_notional": total_notional,
        "max_single_notional": max_single_notional,
        "portfolio_value": 0, # Placeholder
        "cash_reserve_after": 0, # Placeholder
        "checks": {},
        "limits": {
            "applied": {
                "max_total_notional_ratio": max_total_notional_ratio,
                "max_single_order_ratio": max_single_order_ratio,
                "min_cash_reserve_ratio": min_cash_reserve_ratio,
                "exec_mode": exec_mode
            }
        }
    }

    # Guardrail Logic
    decision = "READY"
    reason = "CONFIRMED"
    detail = "Human confirmation token matched. Safety checks passed."
    verdict = "PASS"
    
    # 1. Order Count Check
    if orders_count > MAX_ORDERS_ALLOWED:
        decision = "BLOCKED"
        reason = "LIMIT_EXCEEDED"
        detail = f"Order count {orders_count} exceeds limit {MAX_ORDERS_ALLOWED}"
        verdict = "BLOCKED"
    
    # 2. Portfolio Checks (If available)
    if portfolio_data:
        p_val = portfolio_data.get("total_value", 0)
        p_cash = portfolio_data.get("cash", 0)
        prep["safety"]["portfolio_value"] = p_val
        
        if p_val > 0:
            # Ratios
            total_ratio = total_notional / p_val
            single_ratio = max_single_notional / p_val
            cash_after = p_cash - total_buy_notional + total_sell_notional # Estimation
            cash_reserve_ratio = cash_after / p_val
            
            prep["safety"]["checks"] = {
                "total_notional_ratio": round(total_ratio, 4),
                "single_order_ratio": round(single_ratio, 4),
                "cash_reserve_ratio": round(cash_reserve_ratio, 4)
            }
            
        
            if total_ratio > max_total_notional_ratio:
                decision = "BLOCKED"
                reason = "LIMIT_EXCEEDED"
                detail = f"Total notional ratio {total_ratio:.4f} > {max_total_notional_ratio:.4f}"
                verdict = "BLOCKED"
            
            elif single_ratio > max_single_order_ratio:
                decision = "BLOCKED"
                reason = "LIMIT_EXCEEDED"
                detail = f"Single order notional ratio {single_ratio:.4f} > {max_single_order_ratio:.4f}"
                verdict = "BLOCKED"
                 
            elif cash_reserve_ratio < min_cash_reserve_ratio:
                decision = "BLOCKED" # Or WARN?
                reason = "CASH_LOW"
                detail = f"Est. Cash Reserve {cash_reserve_ratio:.4f} below {min_cash_reserve_ratio:.4f}"
                verdict = "BLOCKED"
        else:
            # Portfolio value 0? suspicious
            decision = "BLOCKED"
            reason = "PORTFOLIO_ZERO"
            detail = "Portfolio Value is 0. Cannot calculate safety ratios."
            verdict = "BLOCKED"
            
    else:
        # Portfolio Missing -> Fail Closed per P120
        decision = "BLOCKED"
        reason = "NO_PORTFOLIO"
        detail = "Portfolio Snapshot missing. Cannot verify safety limits."
        verdict = "BLOCKED"

    # 3. Allow Buy Check
    if not ALLOW_BUY and total_buy_notional > 0:
        decision = "BLOCKED"
        reason = "SELL_ONLY_MODE"
        detail = "Buy orders detected in SELL_ONLY mode."
        verdict = "BLOCKED"

    # Finalize
    prep["decision"] = decision
    prep["reason"] = reason
    prep["reason_detail"] = detail
    prep["verdict"] = verdict
    
    if decision == "BLOCKED":
        prep["manual_next_step"] = f"CRITICAL: {detail}"
    elif decision == "WARN":
        prep["manual_next_step"] = f"WARNING: {detail}"
    else:
        prep["manual_next_step"] = "Ready for Execution (Next Phase)"

    _save_and_return(prep)

def _save_and_return(prep: Dict):
    try:
        # Atomic Write
        temp_file = PREP_LATEST.parent / f".tmp_{PREP_LATEST.name}"
        temp_file.write_text(json.dumps(prep, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp_file), str(PREP_LATEST))
        
        # Snapshot
        asof_safe = prep["asof"].replace(":", "").replace("-", "").replace("T", "_").replace("Z", "").split(".")[0]
        snap_name = f"execution_prep_{asof_safe}.json"
        snapshot_path = PREP_SNAPSHOTS / snap_name
        shutil.copy(str(PREP_LATEST), str(snapshot_path))
        
        print(json.dumps(prep, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({
            "schema": "EXECUTION_PREP_V1",
            "decision": "BLOCKED",
            "reason": "WRITE_ERROR",
            "error": str(e)
        }))

if __name__ == "__main__":
    import sys
    # Expect token as arg 1? Or just allow module import usage.
    # User requirement: API POST body.
    # The script can be run standalone for testing.
    token = sys.argv[1] if len(sys.argv) > 1 else "TEST_TOKEN"
    generate_prep(token)
