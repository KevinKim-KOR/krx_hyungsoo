from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

router = APIRouter(prefix="/api/sync", tags=["Sync"])

# Load Env
load_dotenv()
OCI_BACKEND_URL = os.getenv("OCI_BACKEND_URL", "http://localhost:8000") # Default to localhost for testing

@router.post("/pull")
async def pull_from_oci():
    """
    Pulls SSOT from OCI and applies it to Local PC.
    """
    try:
        # 1. Get Snapshot from OCI
        resp = requests.get(f"{OCI_BACKEND_URL}/api/ssot/snapshot", timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"OCI Connect Failed: {resp.text}")
        
        snapshot = resp.json()
        
        # 2. Apply to Local via Local API (Loopback)
        # We can call the local function directly or via localhost request. 
        # For simplicity/consistency, we call local API logic or just write files since we are on PC.
        # Calling local API is cleaner.
        local_resp = requests.post(
            "http://localhost:8000/api/ssot/snapshot?force=true",
            json=snapshot,
            timeout=5
        )
        
        if local_resp.status_code != 200:
             raise HTTPException(status_code=500, detail=f"Local Apply Failed: {local_resp.text}")
             
        return {"status": "OK", "message": "Pulled from OCI", "snapshot": snapshot}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/push")
async def push_to_oci(token: str = Body(..., embed=True)):
    """
    Pushes Local SSOT (Portfolio + Replay) to OCI.
    Requires Ops Token for security.
    """
    try:
        # 1. Get Local Snapshot
        local_resp = requests.get("http://localhost:8000/api/ssot/snapshot", timeout=2)
        if local_resp.status_code != 200:
             raise HTTPException(status_code=500, detail="Local Snapshot Failed")
        
        snapshot = local_resp.json()
        
        # 2. Push to OCI
        # OCI doesn't check token on /snapshot endpoint in MVP plan? 
        # Wait, plan said "Requires Token". But /api/ssot/snapshot definition didn't include it. 
        # We should probably pass it in header or query. 
        # For MVP, we'll assume endpoint is open or we rely on VPN, OR we add token param.
        # Let's add token to query for now to match other OCI patterns.
        
        oci_resp = requests.post(
            f"{OCI_BACKEND_URL}/api/ssot/snapshot?force=true&token={token}",
            json=snapshot,
            timeout=5
        )
        
        if oci_resp.status_code != 200:
             raise HTTPException(status_code=502, detail=f"OCI Push Failed: {oci_resp.text}")
             
        return {"status": "OK", "message": "Pushed to OCI", "snapshot": snapshot}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
