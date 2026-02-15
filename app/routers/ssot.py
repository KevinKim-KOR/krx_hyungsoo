from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Dict, Any, Optional
from datetime import datetime
import json
from pathlib import Path

from app.utils.portfolio_normalize import normalize_portfolio, load_asof_override
# from app.utils.ref_validator import load_latest_artifact # Not found, removing dependency

router = APIRouter(prefix="/api/ssot", tags=["SSOT"])

# Base Directories (Relative to app root)
BASE_DIR = Path(__file__).parent.parent.parent
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
ASOF_OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
OPS_SUMMARY_PATH = BASE_DIR / "reports" / "ops" / "summary" / "ops_summary_latest.json"

def get_build_id():
    """Returns simple build identifier (e.g. git sha or timestamp)"""
    # Simplified for MVP: Use ops_summary timestamp or internal marker
    try:
        summary = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
        return summary.get("updated_at", "UNKNOWN_BUILD")
    except:
        return "UNKNOWN_BUILD"

@router.get("/snapshot")
async def get_ssot_snapshot():
    """
    Returns the current SSOT state (Portfolio + Replay + Stage).
    Used by PC to pull from OCI, or OCI to verify PC state.
    """
    # 1. Load Portfolio
    portfolio = {}
    if PORTFOLIO_PATH.exists():
        try:
            portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
        except:
            pass

    # 2. Load Replay/Override
    override = load_asof_override()

    # 3. Load Stage (from Ops Summary)
    stage = "UNKNOWN"
    updated_at = datetime.utcnow().isoformat()
    if OPS_SUMMARY_PATH.exists():
        try:
            summary = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
            # Handle V1 schema (rows vs direct)
            row = summary["rows"][0] if "rows" in summary and summary["rows"] else summary
            stage = row.get("manual_loop", {}).get("stage", "UNKNOWN")
            updated_at = summary.get("updated_at", updated_at)
        except:
            pass

    import platform
    import os
    
    # 4. Construct Snapshot
    snapshot = {
        "env_info": {
            "hostname": platform.node(),
            "type": "OCI" if "oracle" in platform.node().lower() or "instance" in platform.node().lower() else "PC",
            "url": "http://localhost:8000" # Self URL (approx)
        },
        "stage": stage,
        "portfolio": portfolio,
        "asof_override": override,
        "revision": updated_at, # Use updated_at as revision for now
        "build_id": get_build_id(),
        "synced_at": datetime.utcnow().isoformat()
    }
    
    return snapshot

@router.post("/snapshot")
async def update_ssot_snapshot(
    snapshot: Dict[str, Any] = Body(...), 
    force: bool = Query(False)
):
    """
    Updates the local SSOT state from a snapshot.
    Protected by token check in main dependency (if applied) or internal network restrictions.
    """
    # 1. Update Portfolio (If provided and different)
    new_portfolio = snapshot.get("portfolio")
    if new_portfolio:
        # Normalize first
        normalized = normalize_portfolio(new_portfolio)
        # Save
        PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
        PORTFOLIO_PATH.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Update Replay/Override (If provided)
    new_override = snapshot.get("asof_override")
    if new_override:
        ASOF_OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ASOF_OVERRIDE_PATH.write_text(json.dumps(new_override, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"status": "OK", "message": "SSOT updated successfully", "revision": snapshot.get("revision")}
