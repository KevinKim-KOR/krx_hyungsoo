import sys
from pathlib import Path
import json
from unittest.mock import MagicMock, patch
import platform
import os

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Mock app.utils.admin_utils and others to allow import
sys.modules["app.utils.admin_utils"] = MagicMock()
sys.modules["app.utils.admin_utils"].normalize_portfolio = lambda x: x
sys.modules["app.utils.admin_utils"].load_asof_override = lambda: {"enabled": True, "asof_kst": "2099-01-01"}

# Mock app.utils.ref_validator
sys.modules["app.utils.ref_validator"] = MagicMock()

# Mock imports
with patch("dotenv.load_dotenv"):
    from app.routers.ssot import get_ssot_snapshot
    from backend.main import app
    from fastapi.testclient import TestClient

client = TestClient(app)

def test_ssot_identity_and_env():
    print("\n🧪 Testing SSOT Identity & Env Info...")
    
    with patch("app.routers.ssot.PORTFOLIO_PATH") as mock_port_path, \
         patch("app.routers.ssot.OPS_SUMMARY_PATH") as mock_ops_path, \
         patch("app.routers.ssot.load_asof_override", return_value={"enabled": True, "asof_kst": "2099-01-01"}):
         
        # Configure Mocks
        mock_port_path.exists.return_value = True
        mock_port_path.read_text.return_value = '{"total_value": 100}'
        mock_ops_path.exists.return_value = True
        mock_ops_path.read_text.return_value = '{"rows":[{"manual_loop":{"stage":"TEST_STAGE"}}],"updated_at":"2024-01-01"}'
        
        # Test Function Logic
        import asyncio
        data = asyncio.run(get_ssot_snapshot())
        
        # Verify env_info key
        assert "env_info" in data, "env_info missing"
        assert "hostname" in data["env_info"], "hostname missing"
        assert "type" in data["env_info"], "type missing"
        
        print(f"✅ SSOT Env Info: {data['env_info']}")
        
        # Verify Stage & Replay
        assert data["stage"] == "TEST_STAGE"
        assert data["asof_override"]["enabled"] is True
        print("✅ SSOT Stage & Replay Data OK")

def test_root_redirect():
    print("\n🧪 Testing Root Redirect...")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/operator"
    print("✅ Root Redirects to /operator")

if __name__ == "__main__":
    try:
        test_ssot_identity_and_env()
        test_root_redirect()
        print("\n🎉 All P146.1 Tests Passed!")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
