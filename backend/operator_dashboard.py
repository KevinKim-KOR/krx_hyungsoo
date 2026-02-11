from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json
from datetime import datetime

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent
SUMMARY_FILE = BASE_DIR / "reports" / "ops" / "summary" / "ops_summary_latest.json"

@router.get("/operator")
async def get_operator_ui():
    template_path = BASE_DIR / "templates" / "operator.html"
    if not template_path.exists():
        return JSONResponse(status_code=404, content={"error": "UI Template not found"})
    return FileResponse(template_path)

@router.get("/api/operator/dashboard")
async def get_operator_dashboard():
    # 1. Read Ops Summary (SSOT)
    if not SUMMARY_FILE.exists():
        return JSONResponse(status_code=503, content={
            "stage": "check_backend",
            "next_action": {"title": "Backend Error", "command": "bash deploy/oci/flight_status.sh"}
        })
    
    try:
        with open(SUMMARY_FILE, 'r') as f:
            summary = json.load(f)
            # Handle both V1 schema (direct dict) and older row-based schema if any
            if "rows" in summary:
                 # Legacy workaround if needed, though strictly we use V1 now
                 row = summary["rows"][0]
                 manual_loop = row.get("manual_loop", {})
            else:
                 manual_loop = summary.get("manual_loop", {})
            
            stage = manual_loop.get("stage", "UNKNOWN")
            asof = summary.get("asof", "UNKNOWN")
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Failed to parse summary: {str(e)}"})

    # 2. Determine Next Action (Logic from P126)
    next_action = {"title": "Unknown", "command": "echo 'Check Admin'", "notes": ""}
    
    if stage == "NEED_HUMAN_CONFIRM":
        next_action = {
            "title": "Run Prep", 
            "command": "deploy/pc/daily_manual_loop.ps1 -DoPrep",
            "notes": "Requires Token on OCI"
        }
    elif stage == "PREP_READY":
        next_action = {
            "title": "Generate Ticket", 
            "command": "deploy/pc/daily_manual_loop.ps1 -DoTicket",
            "notes": "Auto-ticket usually done by Prep"
        }
    elif stage == "AWAITING_HUMAN_EXECUTION":
        next_action = {
            "title": "Generate Record Draft", 
            "command": "deploy/pc/daily_manual_loop.ps1 -DoDraft",
            "notes": "Review Ticket First"
        }
    elif stage == "AWAITING_RECORD_SUBMIT":
        next_action = {
            "title": "Push & Submit Record", 
            "command": "deploy/pc/daily_manual_loop.ps1 -DoPushDraft -DoSubmit",
            "notes": "Will prompt for token on OCI"
        }
    elif stage in ["DONE_TODAY", "DONE_TODAY_PARTIAL"]:
        next_action = {
            "title": "No Action (Done)", 
            "command": "",
            "notes": "Cycle Complete"
        }
    elif stage == "AWAITING_RETRY_EXECUTION":
        next_action = {
            "title": "Retry Execution", 
            "command": "deploy/pc/daily_manual_loop.ps1 -DoDraft", # Retry logic might restart from draft or just submit? Assuming draft regen.
            "notes": "Check previous reasons"
        }

    # 3. Artifacts Refs
    # We construct these based on known latest paths which are standard.
    # Ref Validator needs to allow these.
    artifacts = {
        "summary": "reports/ops/summary/ops_summary_latest.json",
        "order_plan": "reports/live/order_plan/latest/order_plan_latest.json",
        "export": "reports/live/order_plan_export/latest/order_plan_export_latest.json",
        "prep": "reports/live/execution_prep/latest/execution_prep_latest.json",
        "ticket": "reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.json",
        "ticket_md": "reports/live/manual_execution_ticket/latest/manual_execution_ticket_latest.md",
        "record": "reports/live/manual_execution_record/latest/manual_execution_record_latest.json",
        "reco": "reports/live/reco/latest/reco_latest.json",
        "health": "reports/ops/evidence/health/health_latest.json"
    }

    # 4. P139: Portfolio & Timing Data
    portfolio_path = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
    timing_path = BASE_DIR / "reports" / "oci" / "holding_timing" / "latest" / "holding_timing_latest.json"
    
    portfolio_view = []
    
    # Ticker Map (Simple Fallback) - Ideally this should be shared or loaded from params
    TICKER_MAP = {
        "069500": "KODEX 200",
        "229200": "KODEX KONEX",
        "114800": "KODEX INVERSE",
        "122630": "KODEX LEVERAGE"
    }
    
    if portfolio_path.exists():
        try:
            pf_data = json.loads(portfolio_path.read_text(encoding="utf-8"))
            holdings = pf_data.get("holdings", {})
            
            # Load timing for signals/prices
            timing_map = {}
            if timing_path.exists():
                try:
                    t_data = json.loads(timing_path.read_text(encoding="utf-8"))
                    for h in t_data.get("holdings", []):
                        timing_map[h["ticker"]] = h
                except: pass
            
            # Normalize holdings (Handle list vs dict)
            if isinstance(holdings, list):
                iter_holdings = holdings
            else:
                iter_holdings = [{"ticker": k, **v} for k, v in holdings.items()]
                
            for h in iter_holdings:
                t = h.get("ticker", "UNKNOWN")
                qty = h.get("quantity", 0)
                avg = h.get("avg_price", 0)
                
                # Get Market Data from Timing (Best effort)
                t_info = timing_map.get(t, {})
                curr = t_info.get("current_price", 0) # Could be 0 if unknown
                
                # Calculate PnL
                pnl_pct = 0.0
                if avg > 0 and curr > 0:
                    pnl_pct = ((curr / avg) - 1) * 100
                elif avg > 0:
                    # If current price unknown, PnL is unknown (or 0)
                    pnl_pct = 0.0
                    
                # Signal
                sig = t_info.get("current_signal", "WAIT")
                reason = t_info.get("signal_reason", "-")
                
                portfolio_view.append({
                    "ticker": t,
                    "name": TICKER_MAP.get(t, t),
                    "qty": qty,
                    "avg_price": avg,
                    "current_price": curr,
                    "pnl_pct": pnl_pct,
                    "signal": sig,
                    "reason": reason
                })
                
        except Exception as e:
            # Fallback if port parse fails
            portfolio_view = [{"ticker": "ERROR", "name": str(e)}]
            
    return {
        "asof": asof,
        "stage": stage,
        "next_action": next_action,
        "artifacts": artifacts,
        "portfolio": portfolio_view
    }
