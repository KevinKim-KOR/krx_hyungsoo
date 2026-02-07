import json
import os
import sys
from pathlib import Path

# Goal: Print "STAGE : [VALUE]" or just "VALUE"
# Robustly find the file relative to this script

try:
    # deploy/oci/get_stage.py -> ../.. -> Base Dir
    BASE_DIR = Path(__file__).parent.parent.parent.resolve()
    SUMMARY_FILE = BASE_DIR / "reports" / "ops" / "summary" / "ops_summary_latest.json"

    if not SUMMARY_FILE.exists():
        print(f"ERROR: Summary file not found at {SUMMARY_FILE}")
        sys.exit(1)

    with open(SUMMARY_FILE, 'r') as f:
        data = json.load(f)
        # Ops Summary V1 structure:
        # { "manual_loop": { "stage": "..." }, ... }
        # Note: older verify steps used 'rows' list, but generate_ops_summary.py produces direct dict.
        # Let's handle both just in case, or stick to V1 schema.
        # V1 Schema in generate_ops_summary.py: root is dict, manual_loop is key.
        
        stage = data.get("manual_loop", {}).get("stage", "UNKNOWN")
        print(f"STAGE_VALUE:{stage}")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
