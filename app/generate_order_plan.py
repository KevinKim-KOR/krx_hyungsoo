# -*- coding: utf-8 -*-
"""
app/generate_order_plan.py
P102: OCI Order Plan Generator V1 (Intent-Only)

Objective:
- Generate ORDER_PLAN_V1 from RECO_REPORT_V1 + PORTFOLIO_V1
- Read-Only (No Broker Calls)
- Fail-Closed (Block on Missing Inputs or Inconsistent Portfolio)
- Atomic Write

Contract: ORDER_PLAN_V1 (Intent-Only)
"""

import json
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
RECO_LATEST_FILE = BASE_DIR / "reports" / "live" / "reco" / "latest" / "reco_latest.json"
PORTFOLIO_LATEST_FILE = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"

OUTPUT_DIR = BASE_DIR / "reports" / "live" / "order_plan"
OUTPUT_LATEST = OUTPUT_DIR / "latest" / "order_plan_latest.json"
OUTPUT_SNAPSHOTS = OUTPUT_DIR / "snapshots"

# Ensure directories
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "latest").mkdir(parents=True, exist_ok=True)
OUTPUT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def sanitize_text(text: str) -> str:
    """Sanitize reason/detail (remove newlines, limit length)"""
    if not text:
        return ""
    # Remove newlines
    cleaned = text.replace("\n", " ").replace("\r", "")
    # Limit length
    if len(cleaned) > 240:
        cleaned = cleaned[:237] + "..."
    return cleaned

def generate_order_plan() -> Dict[str, Any]:
    now = datetime.now()
    asof_str = now.isoformat()
    
    # 1. Load Inputs
    reco = load_json(RECO_LATEST_FILE)
    portfolio = load_json(PORTFOLIO_LATEST_FILE)
    
    # 2. Initialize Report
    report = {
        "schema": "ORDER_PLAN_V1",
        "asof": asof_str,
        "plan_id": f"plan-{now.strftime('%Y%m%d-%H%M%S')}",
        "decision": "BLOCKED",
        "reason": "UNKNOWN",
        "reason_detail": "",
        "source": {
            "reco_ref": str(RECO_LATEST_FILE.relative_to(BASE_DIR)).replace("\\", "/"),
            "reco_asof": None,
            "reco_decision": None,
            "bundle_id": None,
            "bundle_created_at": None,
            "portfolio_ref": str(PORTFOLIO_LATEST_FILE.relative_to(BASE_DIR)).replace("\\", "/"),
            "portfolio_updated_at": None
        },
        "orders": [],
        "evidence_refs": [],
        "error_summary": None
    }
    
    # 3. Fail-Closed Checks
    
    # Check Reco Existence
    if not reco:
        report["decision"] = "BLOCKED"
        report["reason"] = "NO_RECO"
        report["reason_detail"] = "Reco report not found"
        _save_and_return(report)
        return report

    # Populate Reco Meta
    report["source"]["reco_asof"] = reco.get("asof")
    report["source"]["reco_decision"] = reco.get("decision")
    if "source_bundle" in reco and reco["source_bundle"]:
        report["source"]["bundle_id"] = reco["source_bundle"].get("bundle_id")
        report["source"]["bundle_created_at"] = reco["source_bundle"].get("created_at")
        if "integrity" in reco["source_bundle"]:
             report["source"]["payload_sha256"] = reco["source_bundle"]["integrity"].get("payload_sha256")
             
    report["evidence_refs"].append(report["source"]["reco_ref"])

    # Check Reco Validity (Must be GENERATED or OK)
    reco_decision = reco.get("decision")
    if reco_decision not in ["GENERATED", "OK", "SUCCESS"]:
        # If Reco is EMPTY/BLOCKED, Order Plan is EMPTY (No Orders)
        # But wait, logic says: "reco decision이 BLOCKED|EMPTY_RECO -> decision=EMPTY, reason=NO_ORDERS_FROM_RECO"
        report["decision"] = "EMPTY"
        report["reason"] = "NO_ORDERS_FROM_RECO"
        report["reason_detail"] = f"Reco decision was {reco_decision}"
        _save_and_return(report)
        return report

    # Check Portfolio Existence
    if not portfolio:
        report["decision"] = "BLOCKED"
        report["reason"] = "NO_PORTFOLIO"
        report["reason_detail"] = "Portfolio file not found"
        _save_and_return(report)
        return report

    report["source"]["portfolio_updated_at"] = portfolio.get("updated_at")
    # Portfolio Ref is technically state, so usually not in evidence_refs, but helpful for trace
    # report["evidence_refs"].append(report["source"]["portfolio_ref"]) 

    # Check Portfolio Integrity (Anti-Red Team)
    holdings = portfolio.get("holdings", {})
    total_value = portfolio.get("total_value", 0)
    
    # Rule: holdings > 0 && total_value <= 0 -> BLOCKED
    has_holdings = len(holdings) > 0
    if has_holdings and total_value <= 0:
        report["decision"] = "BLOCKED"
        report["reason"] = "PORTFOLIO_INCONSISTENT"
        report["reason_detail"] = f"Holdings exist ({len(holdings)}) but Total Value is {total_value}"
        _save_and_return(report)
        return report

    # 4. Generate Orders (Intent Mapping)
    # Reco: holding_actions
    holding_actions = reco.get("holding_actions", [])
    # Also check top_picks for NEW_ENTRY if P103 handles logic? 
    # Wait, Reco generator puts ALL actions into holding_actions?
    # No, P100 says: top_picks (Buy list), holding_actions (Sell/Hold list).
    # So we need to merge logic.
    
    # But wait, P102 instructions:
    # "reco의 holding_actions를 order intent로 변환"
    # What about 'top_picks'?
    # Usually:
    # - Top Picks -> Potential BUY (New Entry or Add)
    # - Holding Actions -> SELL/HOLD/BUY (if rebalancing)
    
    # Reco V1 schema:
    # holding_actions: [{ticker, action, ...}] where action is SELL, HOLD, BUY
    # top_picks: [{ticker, score, ...}]
    
    # Contract says: "orders: [{ticker, intent: ADD/REDUCE/NEW_ENTRY/EXIT}]"
    
    # Logic:
    # Iterate holding_actions:
    #   SELL -> EXIT (if all?) or REDUCE?
    #   Usually SELL in holding_actions means Exit or Reduce.
    #   Let's check Reco's Action field. "SELL" usually maps to EXIT/REDUCE.
    #   "BUY" maps to ADD.
    #   "HOLD" -> Ignore.
    
    # Iterate top_picks:
    #   If not in holdings -> NEW_ENTRY
    #   If in holdings -> ADD
    
    orders = []
    
    # 4.1 Process Holding Actions (Priority: Sell first?)
    for action_item in holding_actions:
        ticker = action_item.get("ticker")
        act = action_item.get("action", "HOLD")
        confidence = action_item.get("confidence", "MEDIUM")
        reason = sanitize_text(action_item.get("reason", ""))
        
        if act == "SELL":
            # Determine if EXIT or REDUCE. Without quantity, we assume EXIT for now or check confidence?
            # Or P102 just maps to SELL/EXIT?
            # Strategy Bundle usually outputs "SELL" for removal.
            intent = "EXIT" 
            orders.append({
                "ticker": ticker,
                "side": "SELL",
                "intent": intent,
                "confidence": confidence,
                "reason": "RECO_SELL",
                "reason_detail": reason
            })
        elif act == "BUY":
            # Rebalancing Buy
            orders.append({
                "ticker": ticker,
                "side": "BUY",
                "intent": "ADD",
                "confidence": confidence,
                "reason": "RECO_BUY",
                "reason_detail": reason
            })
            
    # 4.2 Process Top Picks
    top_picks = reco.get("top_picks", [])
    current_tickers = holdings.keys()
    
    for pick in top_picks:
        ticker = pick.get("ticker")
        score = pick.get("score", 0)
        # Check if already processed in holding_actions (avoid duplicate ADD)
        # If in top_picks AND in holding_actions as BUY -> Duplication possible?
        # Usually they are distinct sets or consistent.
        # If ticker is in holdings, it might be in holding_action as HOLD or BUY.
        
        # Check if we already have an order for this ticker
        existing_order = next((o for o in orders if o["ticker"] == ticker), None)
        if existing_order:
            continue # Already handled (e.g. by holding action)
            
        # Determine Intent
        intent = "ADD" if ticker in current_tickers else "NEW_ENTRY"
        
        orders.append({
            "ticker": ticker,
            "side": "BUY",
            "intent": intent,
            "confidence": "HIGH", # Top picks match HIGH?
            "reason": "TOP_PICK",
            "reason_detail": f"Score: {score}"
        })

    report["orders"] = orders
    
    if not orders:
        report["decision"] = "EMPTY"
        report["reason"] = "NO_ORDERS"
        report["reason_detail"] = "No actionable signals from Reco"
    else:
        report["decision"] = "COMPLETED"
        report["reason"] = "SUCCESS"
        report["reason_detail"] = f"Generated {len(orders)} orders"

    _save_and_return(report)
    return report

def _save_and_return(report: Dict):
    """Save latest and snapshot (Atomic)"""
    try:
        # Atomic Write
        temp_file = OUTPUT_LATEST.parent / f".tmp_{OUTPUT_LATEST.name}"
        temp_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(temp_file, OUTPUT_LATEST)
        
        # Snapshot
        asof_safe = report["asof"].replace(":", "").replace("-", "").replace("T", "_").split(".")[0]
        snap_name = f"order_plan_{asof_safe}.json"
        snapshot_path = OUTPUT_SNAPSHOTS / snap_name
        
        # Add snapshot ref to report? (Circular)
        # We can't add it into the file we just wrote without rewriting.
        # But Ops Summary needs it. Ops Summary will find it.
        
        shutil.copy(OUTPUT_LATEST, snapshot_path)
        
        # Print for API capture
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({
            "schema": "ORDER_PLAN_V1",
            "decision": "BLOCKED", 
            "reason": "WRITE_ERROR",
            "error_summary": str(e)
        }))

if __name__ == "__main__":
    generate_order_plan()
