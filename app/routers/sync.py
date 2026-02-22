from fastapi import APIRouter, HTTPException, Body, Query
from typing import Dict, Any
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

import json
from app.utils.portfolio_normalize import normalize_portfolio, load_asof_override
import datetime
from datetime import timezone, timedelta
import platform

router = APIRouter(prefix="/api/sync", tags=["Sync"])

# Base Directories (Relative to app root)
BASE_DIR = Path(__file__).parent.parent.parent
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
ASOF_OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
OPS_SUMMARY_PATH = BASE_DIR / "reports" / "ops" / "summary" / "latest" / "ops_summary_latest.json"

# Load Env
load_dotenv()
OCI_BACKEND_URL = os.getenv("OCI_BACKEND_URL", "http://localhost:8000") # Default to localhost for testing

@router.post("/pull")
async def pull_from_oci(timeout_seconds: int = Query(120, description="OCI Timeout")):
    """
    Pulls SSOT from OCI and applies it to Local PC.
    """
    try:
        # 1. Get Snapshot from OCI
        print(f"[DEBUG] Pulling from OCI: URL={OCI_BACKEND_URL}, Timeout={timeout_seconds}")
        try:
            resp = requests.get(f"{OCI_BACKEND_URL}/api/ssot/snapshot", timeout=timeout_seconds)
        except Exception as e:
            # Detect loopback error
            print(f"[ERROR] OCI Request Failed: {e}")
            raise HTTPException(status_code=502, detail=f"OCI Connect Failed: {e}")

        if resp.status_code != 200:
            print(f"[ERROR] OCI Response: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=502, detail=f"OCI Connect Failed: {resp.text}")
        
        snapshot = resp.json()
        
        # 2. Apply to Local via Direct Write (Avoids Loopback Deadlock)
        # We write directly to files.
        try:
             # Update Portfolio
            new_portfolio = snapshot.get("portfolio")
            if new_portfolio:
                normalized = normalize_portfolio(new_portfolio)
                PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
                PORTFOLIO_PATH.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")

            # Update Replay/Override
            new_override = snapshot.get("asof_override")
            if new_override:
                ASOF_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
                ASOF_OVERRIDE_PATH.write_text(json.dumps(new_override, indent=2, ensure_ascii=False), encoding="utf-8")

            # Update Ops Summary (P146 fix for PC Visibility)
            new_summary = snapshot.get("ops_summary")
            if new_summary and (new_summary.get("rows") or new_summary.get("schema")): # Basic validation
                OPS_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
                OPS_SUMMARY_PATH.write_text(json.dumps(new_summary, indent=2, ensure_ascii=False), encoding="utf-8")
         
        except Exception as e:
             raise HTTPException(status_code=500, detail=f"Local Write Failed: {e}")
             
        return {"status": "OK", "message": "Pulled from OCI", "snapshot": snapshot}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Exception in pull_from_oci: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/push")
async def push_to_oci(
    token: str = Body(..., embed=True),
    timeout_seconds: int = Query(120, description="OCI Timeout")
):
    """
    Pushes Local SSOT (Portfolio + Replay) to OCI.
    Requires Ops Token for security.
    """
    try:
        # 1. Get Local Snapshot (Direct Read to avoid Loopback Deadlock)
        # Load Portfolio
        portfolio = {}
        if PORTFOLIO_PATH.exists():
            try:
                portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
            except:
                pass

        # Load Override
        override = load_asof_override()

        # 4. Construct Snapshot (SSOT Only)
        # P146 Architectural Fix: OCI Generates Ops Summary. PC Pushes SSOT only.
        snapshot = {
            "env_info": {
                "hostname": platform.node(),
                "type": "PC",
                "url": "http://localhost:8000"
            },
            "portfolio": portfolio,
            "asof_override": override,
            "build_id": "PC_PUSH_SSOT",
            "synced_at": datetime.datetime.now(timezone(timedelta(hours=9))).isoformat()
        }
        
        # 2. Push to OCI
        # We pass token in query as checked in previous step.
        print(f"[DEBUG] Pushing to OCI: URL={OCI_BACKEND_URL}, Timeout={timeout_seconds}")
        
        try:
            oci_resp = requests.post(
                f"{OCI_BACKEND_URL}/api/ssot/snapshot?force=true&token={token}",
                json=snapshot,
                timeout=timeout_seconds
            )
            
            if oci_resp.status_code != 200:
                print(f"[ERROR] OCI Push Failed: {oci_resp.status_code} - {oci_resp.text}")
                raise HTTPException(status_code=502, detail=f"OCI Push Failed: {oci_resp.text}")
                
            return {"status": "OK", "message": "Pushed to OCI", "snapshot": snapshot}

        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail=f"OCI Timeout ({timeout_seconds}s)")
        except requests.exceptions.ConnectionError:
            raise HTTPException(status_code=502, detail="OCI Connection Failed")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Exception in push_to_oci: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/push_bundle")
async def push_bundle_to_oci(
    token: str = Body(..., embed=True),
    timeout_seconds: int = Query(120, description="OCI Timeout")
):
    """
    P150: 1-Click Sync (Bundle Push).
    Generates Strategy Bundle dynamically from Current Params, saves it locally,
    and pushes the new Strategy Bundle + Params to OCI.
    """
    try:
        # 1. Import dynamic bundle generator (PC side only script)
        try:
            from deploy.pc.generate_strategy_bundle import generate_bundle, save_bundle
        except ImportError as e:
            raise HTTPException(status_code=500, detail=f"Failed to load bundle generator: {e}")
            
        # 2. Generate and Save Bundle locally
        bundle_payload = generate_bundle()
        save_bundle(bundle_payload)
        
        # 3. Load Strategy Params
        PARAMS_PATH = BASE_DIR / "state" / "strategy_params" / "latest" / "strategy_params_latest.json"
        params_payload = None
        if PARAMS_PATH.exists():
            try:
                params_payload = json.loads(PARAMS_PATH.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[WARN] Could not parse strategy params: {e}")
                
        # 4. Construct SSOT partial snapshot payload
        import platform
        snapshot = {
            "env_info": {
                "hostname": platform.node(),
                "type": "PC",
                "url": "http://localhost:8000"
            },
            "strategy_bundle": bundle_payload,
            "strategy_params": params_payload,
            "build_id": "PC_PUSH_BUNDLE",
            "synced_at": datetime.datetime.now(timezone(timedelta(hours=9))).isoformat()
        }
        
        # 5. Push to OCI's SSOT Snapshot endpoint
        print(f"[DEBUG] Pushing Bundle to OCI: URL={OCI_BACKEND_URL}")
        try:
            oci_resp = requests.post(
                f"{OCI_BACKEND_URL}/api/ssot/snapshot?force=true&token={token}",
                json=snapshot,
                timeout=timeout_seconds
            )
            
            if oci_resp.status_code != 200:
                print(f"[ERROR] OCI Bundle Push Failed: {oci_resp.status_code} - {oci_resp.text}")
                raise HTTPException(status_code=502, detail=f"OCI Bundle Push Failed: {oci_resp.text}")
                
            return {
                "status": "OK", 
                "message": "Bundle Pushed to OCI", 
                "bundle_id": bundle_payload.get("bundle_id"),
                "created_at": bundle_payload.get("created_at")
            }

        except requests.exceptions.Timeout:
            raise HTTPException(status_code=504, detail=f"OCI Timeout ({timeout_seconds}s)")
        except requests.exceptions.ConnectionError:
            raise HTTPException(status_code=502, detail="OCI Connection Failed")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Exception in push_bundle_to_oci: {e}")
        raise HTTPException(status_code=500, detail=str(e))

