# -*- coding: utf-8 -*-
"""
app/generate_manual_execution_ticket.py
P113-A: Manual Execution Ticket V1
"""

import json
import shutil
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
PREP_LATEST = BASE_DIR / "reports" / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"

TICKET_DIR = BASE_DIR / "reports" / "live" / "manual_execution_ticket"
TICKET_LATEST = TICKET_DIR / "latest" / "manual_execution_ticket_latest.json"
TICKET_SNAPSHOTS = TICKET_DIR / "snapshots"

# Ensure directories
TICKET_DIR.mkdir(parents=True, exist_ok=True)
(TICKET_DIR / "latest").mkdir(parents=True, exist_ok=True)
TICKET_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def generate_ticket():
    now = datetime.now(timezone.utc)
    asof_str = now.isoformat().replace("+00:00", "Z")
    
    # 1. Initialize Ticket
    ticket = {
        "schema": "MANUAL_EXECUTION_TICKET_V1",
        "asof": asof_str,
        "source": {
            "prep_ref": None,
            "prep_asof": None,
            "confirm_token": None,
            "plan_id": None
        },
        "decision": "BLOCKED",
        "reason": "UNKNOWN",
        "reason_detail": "",
        "orders": [],
        "output_files": {
            "csv_path": None,
            "md_path": None
        },
        "evidence_refs": []
    }
    
    # 2. Load Prep
    prep = load_json(PREP_LATEST)
    if not prep:
        ticket["decision"] = "NO_PREP"
        ticket["reason"] = "EXECUTION_PREP_MISSING"
        _save_and_return(ticket)
        return
        
    ticket["source"]["prep_ref"] = str(PREP_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    ticket["source"]["prep_asof"] = prep.get("asof")
    ticket["source"]["plan_id"] = prep.get("source", {}).get("plan_id")
    ticket["source"]["confirm_token"] = prep.get("source", {}).get("confirm_token")
    ticket["evidence_refs"].append(ticket["source"]["prep_ref"])
    
    # 3. Validation
    if prep.get("decision") not in ["READY", "WARN"]:
        # If BLOCKED (from P120), we still generate the Ticket Artifact but marked as BLOCKED
        # so the operator sees "BLOCKED" in the Ticket View instead of "File Not Found".
        ticket["decision"] = "BLOCKED"
        ticket["reason"] = f"PREP_{prep.get('decision')}"
        ticket["reason_detail"] = prep.get("reason_detail", "")
        # Include guardrail info even if blocked
        ticket["guardrails"] = {
            "decision": prep.get("decision"),
            "violated": [prep.get("reason")] if prep.get("decision") == "BLOCKED" else []
        }
        # P140: Force Overwrite Artifacts even if BLOCKED (To prevent stale files)
        # We need to render a "BLOCKED TICKET" so the operator sees the error.
        _generate_blocked_ticket_content(ticket)
        _save_and_return(ticket)
        return

    # 4. Generate Content
    ticket["decision"] = "GENERATED"
    ticket["reason"] = "READY_FOR_EXECUTION"
    
    # Guardrails from Prep
    prep_safety = prep.get("safety", {})
    ticket["guardrails"] = {
        "decision": prep.get("verdict", "UNKNOWN"), # P120 uses 'verdict' or 'decision'? P120 script uses 'decision' for READY/WARN/BLOCKED.
        "violated": [] 
    }
    # Note: P120 script sets prep['decision'] to READY/WARN/BLOCKED.
    # prep['safety'] has details.
    
    ticket["guardrails"]["decision"] = prep.get("decision", "READY")
    if prep.get("decision") == "WARN":
         ticket["guardrails"]["violated"] = ["WARNING_TRIGGERED"] # Placeholder, real codes in safety
         ticket["reason"] = "EXECUTABLE_WITH_WARNING"

    raw_orders = prep.get("orders", [])
    processed_orders = []
    
    total_buy = 0
    total_sell = 0
    
    copy_paste_lines = []
    
    for o in raw_orders:
        new_o = o.copy()
        ticker = o.get("ticker", "UNKNOWN")
        side = o.get("side", "UNKNOWN")
        qty = o.get("qty", 0)
        price_ref = o.get("price_ref", 0) or 0
        
        notional = qty * price_ref
        new_o["notional_est"] = notional
        new_o["limit_price"] = price_ref # Assuming Limit = Ref for manual simple
        
        if side == "BUY": total_buy += notional
        elif side == "SELL": total_sell += notional
        
        # Per Order Checks
        checks = {
            "qty_ok": qty > 0,
            "round_lot_ok": True, # KRW usually 1 share. Exceptions (ETF/futures/etc). Assuming 1 is OK.
            "price_ok": price_ref > 0
        }
        new_o["checks"] = checks
        
        display_str = f"{side} {ticker} {qty:,}주 ({price_ref:,}원)"
        new_o["display"] = display_str
        
        copy_paste_lines.append(f"{side} {ticker} {qty}") # Minimal for HTS: "BUY 005930 10"
        
        processed_orders.append(new_o)
        
    ticket["orders"] = processed_orders
    
    # Summaries
    portfolio_val = prep_safety.get("portfolio_value", 0)
    # We might need to load portfolio here if prep didn't store cash?
    # P120 Prep stored portfolio_value but maybe not raw cash. 
    # Let's assume we load portfolio for accurate Cash Before.
    # Actually P120 Prep doesn't fully expose cash in top level.
    # Let's load Portfolio again? Or just use what we have. Contract says "cash_before".
    # Loading Portfolio is safer.
    portfolio_path = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
    cash_before = 0
    if portfolio_path.exists():
         try:
             p_data = json.loads(portfolio_path.read_text(encoding='utf-8'))
             cash_before = p_data.get("cash", 0)
         except: pass
         
    cash_after = cash_before - total_buy + total_sell
    
    ticket["summary"] = {
        "total_orders": len(processed_orders),
        "total_notional": total_buy + total_sell,
        "cash_before": cash_before,
        "cash_after_est": cash_after
    }
    
    ticket["copy_paste"] = " / ".join(copy_paste_lines)
    
    # 5. Generate Output Files (CSV/MD)
    base_name = f"manual_execution_ticket_latest"
    csv_path = TICKET_DIR / "latest" / f"{base_name}.csv"
    md_path = TICKET_DIR / "latest" / f"{base_name}.md"
    
    _write_csv(csv_path, processed_orders)
    _write_md(md_path, ticket)
    
    ticket["output_files"]["csv_path"] = str(csv_path.relative_to(BASE_DIR)).replace("\\", "/")
    ticket["output_files"]["md_path"] = str(md_path.relative_to(BASE_DIR)).replace("\\", "/")
    
    _save_and_return(ticket)

def _write_csv(path: Path, orders: List[Dict]):
    if not orders:
        path.write_text("", encoding="utf-8")
        return
        
    keys = ["side", "ticker", "qty", "limit_price", "notional_est", "display"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(orders)

def _write_md(path: Path, ticket: Dict):
    summ = ticket.get("summary", {})
    gr = ticket.get("guardrails", {})
    
    lines = [
        f"# Manual Execution Ticket",
        f"**Plan ID**: {ticket['source']['plan_id']}",
        f"**AsOf**: {ticket['asof']}",
        f"**Token**: `{ticket['source']['confirm_token']}`",
        "",
        "## Summary",
        f"- **Status**: {gr.get('decision')} {gr.get('violated')}",
        f"- **Orders**: {summ.get('total_orders')} (Notional: {summ.get('total_notional'):,.0f} KRW)",
        f"- **Cash**: {summ.get('cash_before'):,.0f} -> ~{summ.get('cash_after_est'):,.0f} KRW",
        "",
        "## Copy-Paste (HTS/MTS)",
        f"```text",
        f"{ticket.get('copy_paste')}",
        f"```",
        "",
        "## Orders to Execute",
        "| Side | Ticker | Qty | Limit | Check |",
        "|---|---|---|---|---|"
    ]
    for o in ticket["orders"]:
        line = f"| {o.get('side')} | {o.get('ticker')} | {o.get('qty'):,} | {o.get('limit_price'):,} | [ ] |"
        lines.append(line)
        
    lines.append("")
    lines.append("> **Operator Instruction**: Copy input string, paste to HTS. Check each order as executed.")
    
    path.write_text("\n".join(lines), encoding="utf-8")

def _generate_blocked_ticket_content(ticket: Dict):
    # P140: Generate minimal artifacts even if blocked
    ticket["decision"] = "BLOCKED" # Reinforced
    
    # Minimal Summary
    ticket["summary"] = {
        "total_orders": 0,
        "total_notional": 0,
        "cash_before": 0,
        "cash_after_est": 0
    }
    ticket["copy_paste"] = "BLOCKED: See Reason"
    
    base_name = f"manual_execution_ticket_latest"
    csv_path = TICKET_DIR / "latest" / f"{base_name}.csv"
    md_path = TICKET_DIR / "latest" / f"{base_name}.md"
    
    # Clear CSV
    csv_path.write_text("", encoding="utf-8")
    
    # MD with Error
    lines = [
        f"# Manual Execution Ticket (BLOCKED)",
        f"**Plan ID**: {ticket['source'].get('plan_id', 'UNKNOWN')}",
        f"**AsOf**: {ticket['asof']}",
        f"**Status**: ❌ BLOCKED",
        f"**Reason**: {ticket.get('reason')}",
        f"**Detail**: {ticket.get('reason_detail')}",
        "",
        "> Please resolve the blocking issue in Execution Prep."
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    
    ticket["output_files"]["csv_path"] = str(csv_path.relative_to(BASE_DIR)).replace("\\", "/")
    ticket["output_files"]["md_path"] = str(md_path.relative_to(BASE_DIR)).replace("\\", "/")

def _save_and_return(ticket: Dict):
    try:
        # Atomic Write
        temp_file = TICKET_LATEST.parent / f".tmp_{TICKET_LATEST.name}"
        temp_file.write_text(json.dumps(ticket, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp_file), str(TICKET_LATEST))
        
        # Snapshot
        asof_safe = ticket["asof"].replace(":", "").replace("-", "").replace("T", "_").replace("Z", "").split(".")[0]
        snap_name = f"manual_execution_ticket_{asof_safe}.json"
        
        # Also snapshot CSV/MD if they exist
        if ticket["decision"] == "GENERATED":
             csv_snap = TICKET_SNAPSHOTS / f"manual_execution_ticket_{asof_safe}.csv"
             md_snap = TICKET_SNAPSHOTS / f"manual_execution_ticket_{asof_safe}.md"
             shutil.copy(str(TICKET_DIR / "latest" / "manual_execution_ticket_latest.csv"), str(csv_snap))
             shutil.copy(str(TICKET_DIR / "latest" / "manual_execution_ticket_latest.md"), str(md_snap))

        snapshot_path = TICKET_SNAPSHOTS / snap_name
        shutil.copy(str(TICKET_LATEST), str(snapshot_path))
        
        print(json.dumps(ticket, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({
            "schema": "MANUAL_EXECUTION_TICKET_V1",
            "decision": "BLOCKED",
            "reason": "WRITE_ERROR",
            "error": str(e)
        }))

if __name__ == "__main__":
    generate_ticket()
