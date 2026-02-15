import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from backend.main import app

client = TestClient(app)

def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/operator"

def test_ssot_snapshot_get():
    # Mock file reads
    with patch("app.routers.ssot.PORTFOLIO_PATH.exists", return_value=True), \
         patch("app.routers.ssot.PORTFOLIO_PATH.read_text", return_value='{"total_value": 100}'), \
         patch("app.routers.ssot.load_asof_override", return_value={"enabled": True}):
        
        response = client.get("/api/ssot/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["portfolio"]["total_value"] == 100
        assert data["asof_override"]["enabled"] is True
        assert "stage" in data

def test_sync_pull_mock():
    # Mock OCI response and Local Apply
    mock_snapshot = {"portfolio": {"gross": 200}, "revision": "REV1"}
    
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:
        
        # OCI Call
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_snapshot
        
        # Local Apply Call
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "OK"}
        
        # Trigger Pull via Router (needs importing router if not in main app, but main app includes it)
        # We test the endpoint
        response = client.post("/api/sync/pull")
        assert response.status_code == 200
        assert response.json()["message"] == "Pulled from OCI"

def test_sync_push_mock():
    # Mock Local Get and OCI Post
    mock_local_snap = {"portfolio": {"gross": 300}, "revision": "REV2"}
    
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:
         
        # Local Snapshot Call
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_local_snap
        
        # OCI Push Call
        mock_post.return_value.status_code = 200
        
        response = client.post("/api/sync/push", json={"token": "test-token"})
        assert response.status_code == 200
        assert response.json()["message"] == "Pushed to OCI"
