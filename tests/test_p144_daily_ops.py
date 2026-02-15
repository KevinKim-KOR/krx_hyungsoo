
import sys
import os
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from backend.main import app

client = TestClient(app)

def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def test_p144_ui_driven_ops_loop():
    print("\n>>> P144 Verification: UI-Driven Daily Ops Loop")
    
    # 1. PC: Auto Ops Flow
    # 1-A. Reco (Mock Data should be ready or we assume it works)
    # We might fail if no market data, but let's try.
    print("1. [Auto Ops] Generating Reco...")
    res = client.post("/api/reco/regenerate?confirm=true")
    # If this fails (e.g. no market data), we might need to mock or skip
    if res.status_code != 200:
        print(f"WARN: Reco failed ({res.status_code}), but proceeding if possible. Msg: {res.text}")
    
    # 1-B. Order Plan (Crucial)
    # This generates the Export with the Token.
    print("2. [Auto Ops] Generating Order Plan...")
    res = client.post("/api/order_plan/regenerate?confirm=true")
    assert res.status_code == 200, f"Order Plan Failed: {res.text}"
    
    # 1-C. Ops Summary
    print("3. [Auto Ops] Updating Summary...")
    res = client.post("/api/ops/summary/regenerate?confirm=true")
    assert res.status_code == 200, f"Summary Failed: {res.text}"
    
    # Verify Stage: Should be NEED_HUMAN_CONFIRM
    summary = client.get("/api/ops/summary/latest").json()
    stage = summary.get("rows", [{}])[0].get("manual_loop", {}).get("stage")
    print(f"   Current Stage: {stage}")
    assert stage == "NEED_HUMAN_CONFIRM" or stage == "PREP_READY", f"Stage mismatch: {stage}"
    
    # 2. OCI: Prepare (Requires Token)
    # Read Token from Export
    export_path = BASE_DIR / "reports" / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
    export_data = load_json(export_path)
    assert export_data, "Export file missing!"
    
    confirm_token = export_data.get("human_confirm", {}).get("confirm_token")
    print(f"   Token Found: {confirm_token}")
    
    print("4. [OCI UI] Running Prep...")
    res = client.post("/api/execution_prep/prepare?confirm=true", json={"confirm_token": confirm_token})
    assert res.status_code == 200, f"Prep Failed: {res.text}"
    data = res.json()
    assert data["decision"] in ["READY", "WARN"], f"Prep Decision Blocked: {data}"
    
    # 3. OCI: Ticket
    print("5. [OCI UI] Generating Ticket...")
    res = client.post("/api/manual_execution_ticket/regenerate?confirm=true")
    assert res.status_code == 200, f"Ticket Gen Failed: {res.text}"
    
    # Update Summary
    client.post("/api/ops/summary/regenerate?confirm=true")
    summary = client.get("/api/ops/summary/latest").json()
    stage = summary.get("rows", [{}])[0].get("manual_loop", {}).get("stage")
    print(f"   Current Stage: {stage}")
    assert stage == "AWAITING_HUMAN_EXECUTION", f"Stage mismatch: {stage}"
    
    # 4. PC: "Execute" (Simulated by creating a draft record or just submitting directly from UI logic)
    # The UI `submitRecord` sends a JSON payload.
    # We construct a mock payload.
    # We need to read the ticket to get valid properties? Or just minimal payload.
    # Minimally we need `confirm_token` and `items`.
    
    print("6. [OCI UI] Submitting Record...")
    payload = {
        "confirm_token": confirm_token,
        "items": [], # Empty execution -> Skipped
        "filled_at": "2024-01-01T12:00:00Z",
        "method": "TEST_UI_SUBMIT",
        "evidence_note": "Automated Verification"
    }
    
    res = client.post("/api/manual_execution_record/submit?confirm=true", json=payload)
    assert res.status_code == 200, f"Submit Failed: {res.text}"
    data = res.json()
    assert data["decision"] in ["EXECUTED", "SKIPPED", "PARTIAL"], f"Submit Decision Blocked: {data}"
    
    # Final Summary Update
    client.post("/api/ops/summary/regenerate?confirm=true")
    summary = client.get("/api/ops/summary/latest").json()
    stage = summary.get("rows", [{}])[0].get("manual_loop", {}).get("stage")
    print(f"   Final Stage: {stage}")
    assert stage == "DONE_TODAY", f"Stage mismatch: {stage}"
    
    print("\nSUCCESS: UI-First Daily Ops Flow Verified!")

if __name__ == "__main__":
    # Setup needed? Mocks?
    # We probably need to ensure minimal state exists.
    # For now, let's run and assume dev env state.
    try:
        test_p144_ui_driven_ops_loop()
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
