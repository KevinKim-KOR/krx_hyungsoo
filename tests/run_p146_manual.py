import sys
from pathlib import Path
import json
from unittest.mock import MagicMock, patch

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

# Mock environment before importing app
with patch("dotenv.load_dotenv"):
    # Mock admin_utils and ref_validator heavily to avoid FS dependency
    sys.modules["app.utils.admin_utils"] = MagicMock()
    sys.modules["app.utils.admin_utils"].normalize_portfolio = lambda x: x
    sys.modules["app.utils.admin_utils"].load_asof_override = lambda: {"enabled": True}
    
    sys.modules["app.utils.ref_validator"] = MagicMock()
    sys.modules["app.utils.ref_validator"].load_latest_artifact = lambda x: {}

    from app.routers.ssot import get_ssot_snapshot
    from app.routers.sync import pull_from_oci, push_to_oci
    from backend.main import app

def test_ssot_logic():
    print("Testing SSOT Logic...")
    # Mock dependencies by patching the module variables, not the Path object attributes
    with patch("app.routers.ssot.PORTFOLIO_PATH") as mock_port_path, \
         patch("app.routers.ssot.OPS_SUMMARY_PATH") as mock_ops_path, \
         patch("app.routers.ssot.load_asof_override", return_value={"enabled": True}):
         
        # Configure Mocks
        mock_port_path.exists.return_value = True
        mock_port_path.read_text.return_value = '{"total_value": 100}'
        
        mock_ops_path.exists.return_value = True
        mock_ops_path.read_text.return_value = '{"rows":[{"manual_loop":{"stage":"TEST_STAGE"}}],"updated_at":"2024-01-01"}'
         
        import asyncio
        data = asyncio.run(get_ssot_snapshot())
        
        assert data["portfolio"]["total_value"] == 100
        assert data["stage"] == "TEST_STAGE"
        print("✅ SSOT Snapshot Logic: OK")

def test_sync_logic():
    print("Testing Sync Logic...")
    # Mock Requests
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:
         
        # PULL Scenario
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"revision": "R1"}
        mock_post.return_value.status_code = 200
        
        import asyncio
        from app.routers import sync
        
        # Pull
        res = asyncio.run(sync.pull_from_oci())
        assert res["status"] == "OK"
        print("✅ Sync PULL Logic: OK")
        
        # PUSH Scenario
        # Local Get
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"revision": "R2"}
        # OCI Post
        mock_post.return_value.status_code = 200
        
        res = asyncio.run(sync.push_to_oci(token="test"))
        assert res["status"] == "OK"
        print("✅ Sync PUSH Logic: OK")

if __name__ == "__main__":
    try:
        test_ssot_logic()
        test_sync_logic()
        print("\n🎉 All Manual Tests Passed!")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
