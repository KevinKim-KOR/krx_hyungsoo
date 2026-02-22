from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import JSONResponse
import os
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

from app.utils.portfolio_normalize import normalize_portfolio, load_asof_override
# from app.utils.ref_validator import load_latest_artifact # Not found, removing dependency

router = APIRouter(prefix="/api/ssot", tags=["SSOT"])

# Base Directories (Relative to app root)
BASE_DIR = Path(__file__).parent.parent.parent
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
ASOF_OVERRIDE_PATH = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
OPS_SUMMARY_PATH = BASE_DIR / "reports" / "ops" / "summary" / "latest" / "ops_summary_latest.json"

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
    KST = timezone(timedelta(hours=9))
    updated_at = datetime.now(KST).isoformat()
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
        "ops_summary": summary if "summary" in locals() else {}, # P146 Only: Full Ops Summary Sync
        "build_id": get_build_id(),
        "synced_at": datetime.now(KST).isoformat()
    }
    
    return snapshot

@router.post("/snapshot")
async def update_ssot_snapshot(
    snapshot: Dict[str, Any] = Body(...), 
    force: bool = Query(False),
    token: str = Query("")
):
    """
    Updates the local SSOT state from a snapshot.
    Protected by strict token validation (P151 Token Unification).
    """
    # 0. Token Validation (P151)
    _exec_mode = "LIVE"
    if OPS_SUMMARY_PATH.exists():
        try:
            _summ = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
            _exec_mode = _summ.get("manual_loop", {}).get("mode", "LIVE")
        except:
            pass
            
    override_payload = snapshot.get("asof_override", {})
    if override_payload and override_payload.get("enabled", False):
        _exec_mode = "DRY_RUN"
        
    allow_tokenless_replay = os.getenv("ALLOW_TOKENLESS_PUSH_IN_REPLAY", "true").lower() == "true"
    
    if _exec_mode == "DRY_RUN":
        if not token and not allow_tokenless_replay:
            return JSONResponse(status_code=403, content={
                "result": "BLOCKED",
                "reason": "REPLAY_TOKENLESS_DISABLED",
                "message": "REPLAY 모드라도 환경변수(ALLOW_TOKENLESS_PUSH_IN_REPLAY)가 활성화되어 있지 않으면 토큰이 필요합니다."
            })
    else:
        # LIVE Mode
        if not token:
            return JSONResponse(status_code=403, content={
                "result": "BLOCKED",
                "reason": "TOKEN_MISSING",
                "message": "LIVE 모드에서는 SSOT 덮어쓰기 권한(Token)이 필수입니다."
            })
        
        try:
            REPORTS_DIR = BASE_DIR / "reports"
            _exp_path = REPORTS_DIR / "live" / "order_plan_export" / "latest" / "order_plan_export_latest.json"
            if _exp_path.exists():
                _exp = json.loads(_exp_path.read_text(encoding="utf-8"))
                _expected = _exp.get("human_confirm", {}).get("confirm_token") or _exp.get("source", {}).get("confirm_token")
                if _expected and token != _expected:
                    return JSONResponse(status_code=403, content={
                        "result": "BLOCKED",
                        "reason": "TOKEN_INVALID",
                        "message": "제공된 토큰이 현재 LIVE Export의 confirm_token과 일치하지 않습니다."
                    })
        except Exception:
            pass

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

    # 3. Update Ops Summary (Stage) - P146.9 Fix
    # This allows OCI Dash to reflect PC Stage (e.g. AWAITING_RECORD_SUBMIT)
    new_stage = snapshot.get("stage")
    new_revision = snapshot.get("revision")
    
    if new_stage and OPS_SUMMARY_PATH.exists():
        try:
            summary = json.loads(OPS_SUMMARY_PATH.read_text(encoding="utf-8"))
            # Handle V1 schema (rows vs direct dict)
            is_rows = "rows" in summary
            row = summary["rows"][0] if is_rows else summary
            
            # Update Stage
            if "manual_loop" not in row:
                row["manual_loop"] = {}
            row["manual_loop"]["stage"] = new_stage
            
            # Update Revision
            if new_revision:
                summary["updated_at"] = new_revision
                
            # Save
            OPS_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[WARN] Failed to update Ops Summary Stage: {e}")
            pass

    # 4. Update Strategy Bundle (P150 1-Click Sync)
    new_bundle = snapshot.get("strategy_bundle")
    if new_bundle:
        BUNDLE_PATH = BASE_DIR / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
        BUNDLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BUNDLE_PATH.write_text(json.dumps(new_bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        
    # 5. Update Strategy Params (P150 Optional Payload)
    new_params = snapshot.get("strategy_params")
    if new_params:
        PARAMS_PATH = BASE_DIR / "state" / "strategy_params" / "latest" / "strategy_params_latest.json"
        PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PARAMS_PATH.write_text(json.dumps(new_params, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"status": "OK", "message": "SSOT updated successfully", "revision": snapshot.get("revision")}
