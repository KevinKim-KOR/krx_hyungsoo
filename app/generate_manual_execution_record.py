# -*- coding: utf-8 -*-
"""
app/generate_manual_execution_record.py
P113-A: Manual Execution Record V1
"""

import json
import shutil

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# --- Configuration ---
BASE_DIR = Path(__file__).parent.parent
PREP_LATEST = BASE_DIR / "reports" / "live" / "execution_prep" / "latest" / "execution_prep_latest.json"
TICKET_LATEST = BASE_DIR / "reports" / "live" / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"

RECORD_DIR = BASE_DIR / "reports" / "live" / "manual_execution_record"
RECORD_LATEST = RECORD_DIR / "latest" / "manual_execution_record_latest.json"
RECORD_SNAPSHOTS = RECORD_DIR / "snapshots"

# Ensure directories
RECORD_DIR.mkdir(parents=True, exist_ok=True)
(RECORD_DIR / "latest").mkdir(parents=True, exist_ok=True)
RECORD_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

def load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def generate_record(input_token: str, items_data: Dict):
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    asof_str = now.isoformat()
    
    # 1. Initialize Record
    record = {
        "schema": "MANUAL_EXECUTION_RECORD_V1",
        "asof": asof_str,
        "source": {
            "prep_ref": None,
            "ticket_ref": None,
            "confirm_token": input_token,
            "plan_id": None
        },
        "decision": "BLOCKED",
        "summary": {
            "orders_total": 0,
            "executed_count": 0,
            "skipped_count": 0
        },
        "items": [],
        "reason": "UNKNOWN",
        "reason_detail": "",
        "evidence_refs": []
    }
    
    # 2. Load Dependencies
    prep = load_json(PREP_LATEST)
    ticket = load_json(TICKET_LATEST)
    
    # DEBUG
    print(f"DEBUG: PREP_LATEST={PREP_LATEST}, Exists={PREP_LATEST.exists()}")
    print(f"DEBUG: TICKET_LATEST={TICKET_LATEST}, Exists={TICKET_LATEST.exists()}")
    print(f"DEBUG: prep type: {type(prep)}")
    print(f"DEBUG: ticket type: {type(ticket)}")
    
    if not prep or not ticket:
        record["decision"] = "BLOCKED"
        record["reason"] = "DEPENDENCY_MISSING"
        print("DEBUG: Dependencies missing. Returning BLOCKED.")
        _save_and_return(record)
        return
        

    
    # Sanitize prep["source"] which might be a list in some contexts
    source = prep.get("source", {})
    if isinstance(source, list):
        source = source[0] if source else {}
    if not isinstance(source, dict):
        source = {}
    
    try:
        record["source"]["prep_ref"] = str(PREP_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
        record["source"]["ticket_ref"] = str(TICKET_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
        record["source"]["plan_id"] = source.get("plan_id")
        record["evidence_refs"] = [record["source"]["prep_ref"], record["source"]["ticket_ref"]]
    except Exception as e:
        print(f"DEBUG: Error in linkage construction: {e}")
        raise e
    
    
    # 3. Validate Context (Fail-Closed)
    # source is already sanitized above

    # 3-A. Token Check
    required_token = source.get("confirm_token")
    if input_token != required_token:
        record["decision"] = "BLOCKED"
        record["reason"] = "TOKEN_MISMATCH"
        _save_and_return(record)
        return

    # 3-B. Prep Status Check
    if prep.get("decision") not in ["READY", "WARN"]:
        record["decision"] = "BLOCKED"
        record["reason"] = "PREP_NOT_READY"
        record["reason_detail"] = f"Prep decision is {prep.get('decision')}"
        _save_and_return(record)
        return

    # 3-C. Linkage Check (Plan ID match)
    prep_plan_id = prep.get("source", {}).get("plan_id")
    ticket_plan_id = ticket.get("source", {}).get("plan_id")
    input_plan_id = items_data.get("source", {}).get("plan_id") # Input should have source headers

    if prep_plan_id != ticket_plan_id:
        record["decision"] = "BLOCKED"
        record["reason"] = "LINKAGE_MISMATCH"
        record["reason_detail"] = "Prep and Ticket Plan IDs do not match"
        _save_and_return(record)
        return
        
    if input_plan_id and input_plan_id != prep_plan_id:
        record["decision"] = "BLOCKED"
        record["reason"] = "LINKAGE_MISMATCH"
        record["reason_detail"] = f"Input Plan ID {input_plan_id} != Prep Plan ID {prep_plan_id}"
        _save_and_return(record)
        return

    # 3-D. Dedupe & Versioning
    # Check LATEST first.
    current_record = load_json(RECORD_LATEST)
    record_version = 1
    
    # Idempotency Key Generation (if not provided in input, though contract says it's in 'dedupe' object usually?)
    # Contract says dedupe.idempotency_key. Let's assume input has it or we form it.
    # We formed it from ticket_id + filled_at + plan_id usually.
    # Here we check if input `dedupe` exists.
    input_dedupe = items_data.get("dedupe", {})
    input_idem_key = input_dedupe.get("idempotency_key")
    if not input_idem_key:
        # Fallback gen
        input_idem_key = f"{prep_plan_id}_{items_data.get('filled_at')}"
    
    if current_record and current_record.get("linkage", {}).get("plan_id") == prep_plan_id:
        # Same Plan ID exists.
        last_idem_key = current_record.get("dedupe", {}).get("idempotency_key")
        last_decision = current_record.get("decision")
        
        if last_idem_key == input_idem_key:
             # Exact Duplicate
            if last_decision != "BLOCKED":
                record["decision"] = "BLOCKED"
                record["reason"] = "DUPLICATE_SUBMIT_BLOCKED"
                record["reason_detail"] = "Identical payload already processed."
                _save_and_return(record)
                return
        else:
            # Different Content -> New Version
            record_version = current_record.get("record_version", 1) + 1
            print(f"DEBUG: New Version Detected: v{record_version}")

    record["record_version"] = record_version
    record["dedupe"] = {
        "idempotency_key": input_idem_key
    }

    # 4. Populate Record Fields
    record["source_refs"] = {
        "execution_prep_ref": str(PREP_LATEST.relative_to(BASE_DIR)).replace("\\", "/"),
        "ticket_ref": str(TICKET_LATEST.relative_to(BASE_DIR)).replace("\\", "/"),
        "order_plan_export_ref": prep.get("source", {}).get("export_ref")
    }
    
    record["linkage"] = {
        "bundle_id": "UNKNOWN", 
        "plan_id": prep_plan_id,
        "export_id": prep.get("source", {}).get("export_ref"), 
        "ticket_id": "TICKET_LATEST" 
    }
    
    # 5. Process Items & Calculate Result
    input_items = items_data.get("items", [])
    
    executed = 0
    skipped = 0
    partial = 0
    canceled = 0
    
    processed_items = []
    fills = []
    
    for item in input_items:
        status = item.get("status", "SKIPPED")
        processed_items.append(item)
        
        if status == "EXECUTED":
            executed += 1
            fills.append({
                "ticker": item.get("ticker"),
                "side": item.get("side"),
                "qty_filled": item.get("executed_qty"),
                "avg_price": item.get("avg_price", 0),
                "note": item.get("note", "")
            })
        elif status == "PARTIAL":
            partial += 1
            fills.append({
                "ticker": item.get("ticker"),
                "side": item.get("side"),
                "qty_filled": item.get("executed_qty"),
                "avg_price": item.get("avg_price", 0),
                "note": item.get("note", "")
            })
        elif status == "CANCELED":
            canceled += 1
        else:
            skipped += 1
            
    record["items"] = processed_items
    record["fills"] = fills
    
    record["summary"]["orders_total"] = len(input_items)
    record["summary"]["executed_count"] = executed
    record["summary"]["skipped_count"] = skipped
    
    # Reconciliation Logic
    # Compare with Prep Orders? 
    # For now, just simplistic summaries.
    record["reconciliation"] = {
        "missing_orders_count": 0, # TODO: Implement if needed to compare with Prep
        "diff_summary": f"Exec:{executed}, Part:{partial}, Skip:{skipped}, Cncl:{canceled}"
    }

    # Determine Execution Result
    if executed == len(input_items) and len(input_items) > 0:
        record["execution_result"] = "EXECUTED"
        record["decision"] = "EXECUTED"
    elif executed == 0 and partial == 0:
        record["execution_result"] = "NOT_EXECUTED"
        record["decision"] = "SKIPPED" # Legacy mapping
    else:
        record["execution_result"] = "PARTIAL"
        record["decision"] = "PARTIAL"
        
    record["reason"] = "SUBMITTED"
    record["operator_proof"] = {
        "filled_at": items_data.get("filled_at", asof_str),
        "method": items_data.get("method", "UNKNOWN"),
        "evidence_note": items_data.get("evidence_note", "")
    }
    
    _save_and_return(record)

def _save_and_return(record: Dict):
    try:
        # Atomic Write
        temp_file = RECORD_LATEST.parent / f".tmp_{RECORD_LATEST.name}"
        temp_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp_file), str(RECORD_LATEST))
        
        # Snapshot
        asof_safe = record["asof"].replace(":", "").replace("-", "").replace("T", "_").replace("Z", "").split(".")[0]
        snap_name = f"manual_execution_record_{asof_safe}.json"
        
        snapshot_path = RECORD_SNAPSHOTS / snap_name
        shutil.copy(str(RECORD_LATEST), str(snapshot_path))
        
        print(json.dumps(record, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(json.dumps({
            "schema": "MANUAL_EXECUTION_RECORD_V1",
            "decision": "BLOCKED",
            "reason": "WRITE_ERROR",
            "error": str(e)
        }))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({"decision": "BLOCKED", "reason": "NO_INPUT_FILE"}))
        sys.exit(1)
        
    input_file = Path(sys.argv[1])
    try:
        if not input_file.exists():
             # maybe passed as stdin content? No, argument is file path usually.
             # Check if argument is token (legacy usage)?
             # New usage: python generate... record_input.json < token.txt (via stdin for token) OR
             # P122 says "submit input JSON". 
             # Let's assume input_file contains everything including token?
             # OR token is passed via pipe?
             # Safe pattern: Token via pipe (safe), Content via file.
             pass
             
        # Read Token from Stdin
        token = sys.stdin.read().strip()
        
        items_data = json.loads(input_file.read_text(encoding='utf-8'))
        generate_record(token, items_data)
        
    except Exception as e:
        print(json.dumps({"decision": "BLOCKED", "reason": "INPUT_ERROR", "error": str(e)}))
        sys.exit(1)
