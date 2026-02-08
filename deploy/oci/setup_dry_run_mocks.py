
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_LIVE = BASE_DIR / "reports" / "live"

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    print(f"Wrote {path}")

def setup():
    # 1. Prep
    prep = {
        "id": "prep_mock",
        "decision": "READY",
        "reason_detail": "MOCK_DRY_RUN",
        "timestamp": "2026-01-01T00:00:00"
    }
    write_json(REPORTS_LIVE / "execution_prep" / "latest" / "execution_prep_latest.json", prep)

    # 2. Plan Export
    plan = {
        "id": "plan_mock",
        "decision": "GENERATED",
        "timestamp": "2026-01-01T00:00:00"
    }
    write_json(REPORTS_LIVE / "order_plan_export" / "latest" / "order_plan_export_latest.json", plan)

    # 3. Ticket
    ticket = {
        "id": "ticket_mock",
        "decision": "GENERATED",
        "linkage": {
            "plan_id": "plan_mock"
        },
        "timestamp": "2026-01-01T00:00:00"
    }
    write_json(REPORTS_LIVE / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json", ticket)
    
    # 4. Remove existing Dry Run Record if any
    dry_run = REPORTS_LIVE / "dry_run_record" / "latest" / "dry_run_record_latest.json"
    if dry_run.exists():
        dry_run.unlink()
        print("Removed existing dry run record")

    # 5. Remove existing Manual Record if any (so we aren't DONE_TODAY)
    manual_rec = REPORTS_LIVE / "manual_execution_record" / "latest" / "manual_execution_record_latest.json"
    if manual_rec.exists():
        manual_rec.unlink()
        print("Removed existing manual record")

if __name__ == "__main__":
    setup()
