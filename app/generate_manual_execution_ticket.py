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
    if prep.get("decision") != "READY":
        ticket["decision"] = "PREP_NOT_READY"
        ticket["reason"] = f"PREP_STATUS_{prep.get('decision')}"
        ticket["reason_detail"] = prep.get("reason_detail", "")
        _save_and_return(ticket)
        return

    # 4. Generate Content
    ticket["decision"] = "GENERATED"
    ticket["reason"] = "READY_FOR_EXECUTION"
    
    raw_orders = prep.get("orders", [])
    processed_orders = []
    
    for o in raw_orders:
        new_o = o.copy()
        ticker = o.get("ticker", "UNKNOWN")
        side = o.get("side", "UNKNOWN")
        qty = o.get("qty", 0)
        price_ref = o.get("price_ref", 0)
        
        display_str = f"{side} {ticker}"
        if qty > 0:
            display_str += f" {qty} EA"
        else:
            notional = o.get("notional", 0)
            display_str += f" {notional:,.0f} KRW"
            
        new_o["display"] = display_str
        processed_orders.append(new_o)
        
    ticket["orders"] = processed_orders
    
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
        
    keys = ["ticker", "side", "qty", "price_ref", "notional", "reason", "display"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(orders)

def _write_md(path: Path, ticket: Dict):
    lines = [
        f"# Manual Execution Ticket",
        f"**Plan ID**: {ticket['source']['plan_id']}",
        f"**AsOf**: {ticket['asof']}",
        f"**Token**: `{ticket['source']['confirm_token']}`",
        "",
        "## Orders to Execute",
        "| Side | Ticker | Display | Reason |",
        "|---|---|---|---|"
    ]
    for o in ticket["orders"]:
        line = f"| {o.get('side')} | {o.get('ticker')} | **{o.get('display')}** | {o.get('reason')} |"
        lines.append(line)
        
    lines.append("")
    lines.append("> **Operator Instruction**: Execute exactly as shown. Record results via API.")
    
    path.write_text("\n".join(lines), encoding="utf-8")

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
