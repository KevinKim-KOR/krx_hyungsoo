import json
import uuid
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Setup Paths
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
LIVE_DIR = REPORTS_DIR / "live"

# Inputs
TICKET_DIR = LIVE_DIR / "manual_execution_ticket" / "latest"
PLAN_DIR = LIVE_DIR / "order_plan_export" / "latest"

# Outputs
OUTPUT_DIR = LIVE_DIR / "dry_run_record" / "latest"
OUTPUT_FILE = OUTPUT_DIR / "dry_run_record_latest.json"

def generate_dry_run_record(confirm: bool = False):
    if not confirm:
        print("ERROR: Confirmation required (confirm=True)")
        sys.exit(1)

    # 1. Load Inputs
    if not (TICKET_DIR / "manual_execution_ticket_latest.json").exists():
        print("ERROR: Ticket not found")
        sys.exit(1)
        
    ticket = json.loads((TICKET_DIR / "manual_execution_ticket_latest.json").read_text(encoding="utf-8"))
    
    # 2. Validate Linkage
    plan_id = ticket.get("linkage", {}).get("plan_id", "UNKNOWN")
    ticket_id = ticket.get("id", "UNKNOWN")
    
    # 3. Create Record
    record_id = f"dry_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    record = {
        "spec_version": "1.0",
        "id": record_id,
        "type": "DRY_RUN",
        "timestamp": datetime.now().isoformat(),
        "linkage": {
            "plan_id": plan_id,
            "ticket_id": ticket_id
        },
        "execution_result": "DRY_RUN",
        "decision": "COMPLETED",
        "items": [],  # No items executed in dry run
        "operator_confirm": True,
        "meta": {
            "generator": "app/generate_dry_run_record.py"
        }
    }
    
    # 4. Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(record, indent=2), encoding="utf-8")
    
    print(json.dumps({"result": "OK", "id": record_id, "path": str(OUTPUT_FILE)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Confirm dry run execution")
    args = parser.parse_args()
    
    generate_dry_run_record(confirm=args.confirm)
