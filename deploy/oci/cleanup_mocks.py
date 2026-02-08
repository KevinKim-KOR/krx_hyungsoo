
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_LIVE = BASE_DIR / "reports" / "live"

def cleanup():
    files = [
        REPORTS_LIVE / "execution_prep" / "latest" / "execution_prep_latest.json",
        REPORTS_LIVE / "order_plan_export" / "latest" / "order_plan_export_latest.json",
        REPORTS_LIVE / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json",
        REPORTS_LIVE / "dry_run_record" / "latest" / "dry_run_record_latest.json"
    ]
    
    for f in files:
        if f.exists():
            f.unlink()
            print(f"Removed {f}")
        else:
            print(f"Skipped {f} (not found)")

if __name__ == "__main__":
    cleanup()
