
import sys
import os
import json
import logging
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

# Redirect output
logging.basicConfig(level=logging.DEBUG)

def run_test():
    try:
        from backend.main import app
        client = TestClient(app)
        
        payload = {
            "confirm_token": "TEST_TOKEN_123",
            "items": [
               {"ticker": "069500", "side": "BUY", "executed_qty": 10, "avg_price": 30000, "status": "EXECUTED"}
            ],
            "filled_at": "2026-02-13T12:00:00Z"
        }
        
        print("Submitting via Client...")
        response = client.post("/api/manual_execution_record/submit?confirm=true", json=payload)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.json()}")

    except Exception:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
