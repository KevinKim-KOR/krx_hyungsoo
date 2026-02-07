# -*- coding: utf-8 -*-
"""
app/generate_manual_execution_record.py
P113-A: Manual Execution Record V1
"""

import json
import shutil
from datetime import datetime, timezone
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

def generate_record(confirm_token: str, items: List[Dict]):
    now = datetime.now(timezone.utc)
    asof_str = now.isoformat().replace("+00:00", "Z")
    
    # 1. Initialize Record
    record = {
        "schema": "MANUAL_EXECUTION_RECORD_V1",
        "asof": asof_str,
        "source": {
            "prep_ref": None,
            "ticket_ref": None,
            "confirm_token": confirm_token,
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
    
    if not prep or not ticket:
        record["decision"] = "BLOCKED"
        record["reason"] = "DEPENDENCY_MISSING"
        _save_and_return(record)
        return
        
    record["source"]["prep_ref"] = str(PREP_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    record["source"]["ticket_ref"] = str(TICKET_LATEST.relative_to(BASE_DIR)).replace("\\", "/")
    record["source"]["plan_id"] = prep.get("source", {}).get("plan_id")
    record["evidence_refs"] = [record["source"]["prep_ref"], record["source"]["ticket_ref"]]
    
    # 3. Validate Context
    if prep.get("decision") != "READY":
        record["decision"] = "BLOCKED"
        record["reason"] = "PREP_NOT_READY"
        _save_and_return(record)
        return
        
    required_token = prep.get("source", {}).get("confirm_token")
    if confirm_token != required_token:
        record["decision"] = "BLOCKED"
        record["reason"] = "TOKEN_MISMATCH"
        _save_and_return(record)
        return
        
    # 4. Process Items
    # We trust user input items but should match against Ticket orders if we want strictness.
    # User instruction says "submit -> decision=EXECUTED or PARTIAL".
    # We just record what user sent, assuming UI/Operator is responsible for mapping.
    # But we can calculate summary.
    
    executed = 0
    skipped = 0
    
    processed_items = []
    for item in items:
        status = item.get("status", "SKIPPED")
        if status == "EXECUTED":
            executed += 1
        else:
            skipped += 1
        processed_items.append(item)
        
    record["items"] = processed_items
    record["summary"]["orders_total"] = len(items)
    record["summary"]["executed_count"] = executed
    record["summary"]["skipped_count"] = skipped
    
    if executed > 0:
        if skipped > 0:
            record["decision"] = "PARTIAL"
        else:
            record["decision"] = "EXECUTED"
    else:
        if skipped > 0:
            record["decision"] = "SKIPPED" # All skipped
        else:
            record["decision"] = "EXECUTED" # Empty list? or NO_OP
            if len(items) == 0:
                record["decision"] = "NO_ITEMS"

    record["reason"] = "SUBMITTED"
    
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
    # For testing, CLI usage might be complex due to JSON arg.
    # Rely on API invocation mainly.
    pass 
