
import sys
import os
import json
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from backend.main import app

# Redirect output to file for debugging
import logging
logging.basicConfig(level=logging.DEBUG)
# sys.stdout = open('debug_full.log', 'a', encoding='utf-8')
# sys.stderr = sys.stdout

client = TestClient(app)

# Paths
REPORTS_DIR = BASE_DIR / "reports"
LIVE_DIR = REPORTS_DIR / "live"
OPS_DIR = REPORTS_DIR / "ops"

PLAN_LATEST = LIVE_DIR / "order_plan" / "latest" / "order_plan_latest.json"
EXPORT_LATEST = LIVE_DIR / "order_plan_export" / "latest" / "order_plan_export_latest.json"
SUMMARY_LATEST = OPS_DIR / "summary" / "ops_summary_latest.json"
PREP_LATEST = LIVE_DIR / "execution_prep" / "latest" / "execution_prep_latest.json"
TICKET_LATEST = LIVE_DIR / "manual_execution_ticket" / "latest" / "manual_execution_ticket_latest.json"
RECORD_LATEST = LIVE_DIR / "manual_execution_record" / "latest" / "manual_execution_record_latest.json"
ASOF_OVERRIDE = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
ASOF_OVERRIDE_BACKUP = BASE_DIR / "state" / "runtime" / "asof_override_latest.json.bak"

def setup_mock_state():
    print(">>> Setting up MOCK state for UI Flow Test")
    
    # Disable Replay/Holiday Mode (prevents NO_ACTION_TODAY override)
    if ASOF_OVERRIDE.exists():
        shutil.copy(str(ASOF_OVERRIDE), str(ASOF_OVERRIDE_BACKUP))
        ASOF_OVERRIDE.unlink()
        print("   (Disabled replay mode for test)")
    
    # Ensure dirs
    PLAN_LATEST.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_LATEST.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_LATEST.parent.mkdir(parents=True, exist_ok=True)
    
    # 0. Clean Previous Record (Fix Duplicate Block)
    RECORD_LATEST = LIVE_DIR / "manual_execution_record" / "latest" / "manual_execution_record_latest.json"
    if RECORD_LATEST.exists():
        RECORD_LATEST.unlink()
    
    # 1. Order Plan
    plan_data = {
        "asof": "2026-02-13T00:00:00Z",
        "plan_id": "TEST_PLAN_001",
        "decision": "READY",
        "orders": [
            {"ticker": "069500", "side": "BUY", "qty": 10, "price_ref": 30000}
        ]
    }
    PLAN_LATEST.write_text(json.dumps(plan_data), encoding="utf-8")
    
    # 2. Export (Token)
    export_data = {
        "asof": "2026-02-13T00:00:00Z",
        "plan_id": "TEST_PLAN_001",
        "decision": "READY",
        "orders": plan_data["orders"],
        "human_confirm": {
            "required": True,
            "confirm_token": "TEST_TOKEN_123"
        }
    }
    EXPORT_LATEST.write_text(json.dumps(export_data), encoding="utf-8")
    
    # 3. Ops Summary Initial
    summary_data = {
        "asof": "2026-02-13T00:00:00Z",
        "rows": [
            {
                "manual_loop": {
                    "stage": "NEED_HUMAN_CONFIRM",
                    "plan_id": "TEST_PLAN_001"
                }
            }
        ]
    }
    SUMMARY_LATEST.write_text(json.dumps(summary_data), encoding="utf-8")
    
    # 4. Other Dependencies (Minimal)
    (LIVE_DIR / "reco" / "latest").mkdir(parents=True, exist_ok=True)
    (LIVE_DIR / "reco" / "latest" / "reco_latest.json").write_text(json.dumps({"decision": "READY", "asof": "2026-02-13T00:00:00Z"}), encoding="utf-8")
    
    (OPS_DIR / "evidence" / "health").mkdir(parents=True, exist_ok=True)
    (OPS_DIR / "evidence" / "health" / "health_latest.json").write_text(json.dumps({"status": "OK"}), encoding="utf-8")
    
    (OPS_DIR / "balance").mkdir(parents=True, exist_ok=True)
    (OPS_DIR / "balance" / "balance_latest.json").write_text(json.dumps({"total_equity": 1000000}), encoding="utf-8")
    
    (BASE_DIR / "state" / "portfolio" / "latest").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json").write_text(json.dumps({"total_value": 10000000, "cash": 5000000, "holdings": {}}), encoding="utf-8")



def get_stage_from_summary(summary):
    if "rows" in summary and summary["rows"]:
        return summary["rows"][0].get("manual_loop", {}).get("stage")
    return summary.get("manual_loop", {}).get("stage")

def test_p144_api_flow():
    setup_mock_state()
    
    print("\n1. [OCI UI] Running Prep with Token...")
    res = client.post("/api/execution_prep/prepare?confirm=true", json={"confirm_token": "TEST_TOKEN_123"})
    assert res.status_code == 200
    data = res.json()
    print(f"   Prep Result: {data.get('decision')}")
    if data["decision"] == "BLOCKED":
        print(f"   BLOCK REASON: {data.get('reason')} - {data.get('reason_detail')}")
    assert data["decision"] in ["READY", "WARN"]
    
    # Verify Prep File
    assert PREP_LATEST.exists()
    prep = json.loads(PREP_LATEST.read_text(encoding="utf-8"))
    assert prep["source"]["confirm_token"] == "TEST_TOKEN_123"
    
    print("\n2. [OCI UI] Generating Ticket...")
    res = client.post("/api/manual_execution_ticket/regenerate?confirm=true")
    assert res.status_code == 200
    
    # Verify Ticket File
    assert TICKET_LATEST.exists()
    
    print("\n3. [Auto] Updating Summary...")
    res = client.post("/api/ops/summary/regenerate?confirm=true")
    assert res.status_code == 200
    
    summary = client.get("/api/ops/summary/latest").json()
    stage = get_stage_from_summary(summary)
    print(f"   Stage after Ticket: {stage}")
    
    # Needs to be AWAITING_HUMAN_EXECUTION
    # Or PREP_READY if Ticket failed? But we asserted 200 OK.
    
    print("\n4. [OCI UI] Submitting Record...")
    
    # DEBUG: Inspect Prep Content
    print(f"DEBUG: Reading PREP_LATEST from {PREP_LATEST}")
    if PREP_LATEST.exists():
        content = PREP_LATEST.read_text(encoding="utf-8")
        print(f"DEBUG: PREP Content: {content[:500]}...") # Print first 500 chars
        try:
             parsed = json.loads(content)
             print(f"DEBUG: PREP Parsed Type: {type(parsed)}")
             if isinstance(parsed, dict):
                 print(f"DEBUG: PREP Source: {parsed.get('source')}")
             else:
                 print("DEBUG: PREP IS NOT DICT!")
        except Exception as e:
             print(f"DEBUG: PREP JSON Parse Error: {e}")
    else:
        print("DEBUG: PREP_LATEST DOES NOT EXIST!")

    payload = {
        "confirm_token": "TEST_TOKEN_123",
        "items": [
           {"ticker": "069500", "side": "BUY", "executed_qty": 10, "avg_price": 30000, "status": "EXECUTED"}
        ],
        "filled_at": "2026-02-13T12:00:00Z"
    }
    
    res = client.post("/api/manual_execution_record/submit?confirm=true", json=payload)
    assert res.status_code == 200
    data = res.json()
    print(f"   Submit Result: {data.get('decision')}")
    assert data["decision"] == "EXECUTED"
    
    print("\n5. [Auto] Final Summary Update...")
    res = client.post("/api/ops/summary/regenerate?confirm=true")
    if res.status_code != 200:
        print(f"FAILED: Summary Regenerate failed: {res.status_code} {res.text}")
    assert res.status_code == 200
    summary = client.get("/api/ops/summary/latest").json()
    stage = get_stage_from_summary(summary)
    print(f"   Final Stage: {stage}")
    
    # Should be DONE_TODAY
    print(f"DEBUG: Summary JSON: {json.dumps(summary, indent=2)}")
    
    # Check Record File
    if RECORD_LATEST.exists():
        print(f"DEBUG: RECORD_LATEST Content: {RECORD_LATEST.read_text(encoding='utf-8')[:500]}")
    else:
        print("DEBUG: RECORD_LATEST Missing!")

    assert stage == "DONE_TODAY"
    
    print("\n>>> SUCCESS: P144 API Flow Verified (Mocked) <<<")

if __name__ == "__main__":
    try:
        test_p144_api_flow()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Restore Replay Mode
        if ASOF_OVERRIDE_BACKUP.exists():
            shutil.copy(str(ASOF_OVERRIDE_BACKUP), str(ASOF_OVERRIDE))
            ASOF_OVERRIDE_BACKUP.unlink()
            print("   (Restored replay mode)")

