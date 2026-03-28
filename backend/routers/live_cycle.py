# -*- coding: utf-8 -*-
"""live_cycle 라우터 — /api/live/cycle."""

import json
import re
import subprocess
import sys
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.utils import KST, BASE_DIR, logger

router = APIRouter()


# --- 라우트 ---
@router.get("/api/live/cycle/latest", summary="Live Cycle 최신 영수증 조회")
def get_live_cycle_latest():
    """
    Live Cycle Latest (D-P.50)

    최신 Live Cycle 영수증 조회
    Graceful: 영수증 없으면 NO_CYCLE_YET
    """
    try:
        from app.run_live_cycle import load_latest_cycle, list_cycle_snapshots

        receipt = load_latest_cycle()
        snapshots = list_cycle_snapshots()

        if receipt:
            return {
                "schema": "LIVE_CYCLE_RECEIPT_V1",
                "asof": datetime.now(KST).isoformat(),
                "status": "ready",
                "row_count": 1,
                "rows": [receipt],
                "snapshots": snapshots[:10],
                "error": None,
            }
        else:
            return {
                "schema": "LIVE_CYCLE_RECEIPT_V1",
                "asof": datetime.now(KST).isoformat(),
                "status": "no_cycle_yet",
                "row_count": 0,
                "rows": [],
                "snapshots": snapshots[:10],
                "error": {
                    "code": "NO_CYCLE_YET",
                    "message": "No live cycle receipt found",
                },
            }
    except ImportError as e:
        return {
            "schema": "LIVE_CYCLE_RECEIPT_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "error",
            "row_count": 0,
            "rows": [],
            "error": {"code": "IMPORT_ERROR", "message": str(e)},
        }
    except Exception as e:
        return {
            "schema": "LIVE_CYCLE_RECEIPT_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "error",
            "row_count": 0,
            "rows": [],
            "error": {"code": "UNKNOWN_ERROR", "message": str(e)},
        }


@router.post("/api/live/cycle/run", summary="Live Cycle 실행")
def run_live_cycle_api(confirm: bool = False, force: bool = Query(False)):
    """
    Live Cycle Run (P152 Subprocess Orchestration)

    Bundle->Reco->Plan->Export->Summary 단일 실행
    Confirm Guard: confirm=true 필수
    """
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
                "cycle_id": None,
            },
        )

    # [Fail-Closed] force=True는 REPLAY/DRY_RUN에서만 유효, LIVE에서는 무시
    _exec_mode = "LIVE"
    try:
        from app.utils.portfolio_normalize import load_asof_override

        override_data = load_asof_override()
        if override_data.get("enabled", False):
            _exec_mode = "DRY_RUN"
    except Exception:
        pass

    if force and _exec_mode == "LIVE":
        logger.warning("[P152] force=True rejected in LIVE mode. Forcing False.")
        force = False

    try:
        ops_run = {
            "schema": "OPS_RUN_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "RUNNING",
            "results": {},
        }

        def run_script(
            module: str, step_name: str, cascade_force: bool = False
        ) -> dict:
            cmd = [sys.executable, "-m", module]
            if force or cascade_force:
                cmd.append("--force")
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
            m = re.search(r"\[RESULT:\s*([^\]]+)\]", res.stdout)

            action = "UNKNOWN"
            reason = ""
            if res.returncode != 0:
                action = "FAIL"
                reason = "SCRIPT_ERROR"
            elif m:
                raw_res = m.group(1).strip()
                if raw_res.startswith("SKIP reason="):
                    action = "SKIP"
                    reason = raw_res.split("reason=")[1].strip()
                else:
                    action = raw_res
            else:
                if "REGEN" in res.stdout:
                    action = "REGEN"
                elif "SKIP" in res.stdout:
                    action = "SKIP"

            step_result = {
                "rc": res.returncode,
                "result": action,
                "reason": reason,
                "stdout_tail": res.stdout[-1000:] if res.stdout else "",
                "stderr_tail": res.stderr[-1000:] if res.stderr else "",
            }
            ops_run["results"][step_name] = step_result
            return step_result

        results = {}
        # 1. Reco
        reco_res = run_script("app.generate_reco_report", "reco")
        if reco_res["rc"] != 0:
            raise Exception("RECO Failed")

        results["reco"] = f"{reco_res['result']}" + (
            f" ({reco_res['reason']})" if reco_res["reason"] else ""
        )

        # P154: Force Cascade only in DRY_RUN / REPLAY
        cascade = False
        if _exec_mode != "LIVE" and reco_res["result"] == "REGEN":
            cascade = True

        # 2. Order Plan
        op_res = run_script(
            "app.generate_order_plan", "order_plan", cascade_force=cascade
        )
        if op_res["rc"] != 0:
            raise Exception("ORDER_PLAN Failed")

        results["order_plan"] = f"{op_res['result']}" + (
            f" ({op_res['reason']})" if op_res["reason"] else ""
        )

        if _exec_mode != "LIVE" and op_res["result"] == "REGEN":
            cascade = True

        # 3. Order Plan Export
        exp_res = run_script(
            "app.generate_order_plan_export",
            "order_plan_export",
            cascade_force=cascade,
        )
        if exp_res["rc"] != 0:
            raise Exception("EXPORT Failed")

        results["order_plan_export"] = f"{exp_res['result']}" + (
            f" ({exp_res['reason']})" if exp_res["reason"] else ""
        )

        # 4. Ops Summary (no [RESULT:] output natively, just runs)
        os_res = run_script(
            "app.generate_ops_summary",
            "ops_summary",
            cascade_force=cascade,
        )
        if os_res["rc"] != 0:
            raise Exception("OPS_SUMMARY Failed")

        ops_run["status"] = "SUCCESS"

        # Save ops_run
        run_file = (
            BASE_DIR
            / "state"
            / "reports"
            / "ops"
            / "run"
            / "latest"
            / "ops_run_latest.json"
        )
        run_file.parent.mkdir(parents=True, exist_ok=True)
        run_file.write_text(json.dumps(ops_run, indent=2, ensure_ascii=False))

        return {
            "result": "OK",
            "status": "success",
            "results": results,
        }
    except ImportError as e:
        detail = {"result": "FAILED", "reason": f"Import error: {e}"}
        try:
            if "ops_run" in locals():
                ops_run["status"] = "FAILED"
                run_file = (
                    BASE_DIR
                    / "state"
                    / "reports"
                    / "ops"
                    / "run"
                    / "latest"
                    / "ops_run_latest.json"
                )
                run_file.parent.mkdir(parents=True, exist_ok=True)
                run_file.write_text(json.dumps(ops_run, indent=2, ensure_ascii=False))
                detail["ops_run"] = ops_run
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=detail)
    except Exception as e:
        detail = {"result": "FAILED", "reason": str(e)}
        try:
            if "ops_run" in locals():
                ops_run["status"] = "FAILED"
                run_file = (
                    BASE_DIR
                    / "state"
                    / "reports"
                    / "ops"
                    / "run"
                    / "latest"
                    / "ops_run_latest.json"
                )
                run_file.parent.mkdir(parents=True, exist_ok=True)
                run_file.write_text(json.dumps(ops_run, indent=2, ensure_ascii=False))
                detail["ops_run"] = ops_run
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=detail)
