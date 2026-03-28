"""reporting 라우터 — contract5, diagnosis, gatekeeper, report, recon."""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.utils import (
    KST,
    REPORTS_DIR,
    logger,
    safe_read_json,
)

router = APIRouter()


@router.get("/api/contract5/latest", summary="최신 Daily Report 조회 (P103)")
def get_contract5_latest():
    """최신 Contract 5 Report (AI JSON) 반환"""
    path = REPORTS_DIR / "ops" / "contract5" / "latest" / "ai_report_latest.json"
    if not path.exists():
        return {
            "schema": "CONTRACT5_REPORT_V1",
            "decision": "BLOCKED",
            "reason": "FILE_NOT_FOUND",
        }
    return safe_read_json(path)


@router.post("/api/contract5/regenerate", summary="Daily Report 재생성 (P103)")
def regenerate_contract5(confirm: bool = Query(False)):
    """app/generate_contract5_report.py 실행"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "reason": "CONFIRM_REQUIRED"},
        )

    try:
        from app.generate_contract5_report import generate_contract5_report

        result = generate_contract5_report()
        return result
    except Exception as e:
        logger.error(f"Contract 5 API Error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"result": "ERROR", "message": str(e)},
        )


@router.get(
    "/api/diagnosis/v3",
    summary="진단 V3.1 데이터 (Schema V3.1 Strict)",
)
def get_diagnosis_v3():
    """Contact-1: PHASE_C0_DAILY_V3_1_EVIDENCE Serving"""
    path = REPORTS_DIR / "validation" / "phase_c0_daily_2024_2025_v3_1.json"
    if not path.exists():
        return {
            "status": "not_ready",
            "message": "Diagnosis V3.1 report not found",
        }
    return safe_read_json(path)


@router.get(
    "/api/gatekeeper/v3",
    summary="게이트키퍼 V3 데이터 (Schema Contract 2)",
)
def get_gatekeeper_v3():
    """Contract-2: GATEKEEPER_DECISION_V3 Serving (Latest)"""
    path = REPORTS_DIR / "tuning" / "gatekeeper_decision_latest.json"
    if not path.exists():
        return {
            "status": "not_ready",
            "message": "Gatekeeper V3 report (latest.json) not found",
        }
    return safe_read_json(path)


@router.get("/api/diagnosis", summary="진단 리포트 조회 (V3 Alias)")
def get_diagnosis_report():
    return get_diagnosis_v3()


@router.get("/api/gatekeeper", summary="Gatekeeper 심사 결과 조회 (V3 Alias)")
def get_gatekeeper_report():
    return get_gatekeeper_v3()


@router.get("/api/report/human", summary="Human Report (Contract 5)")
def get_report_human():
    path = REPORTS_DIR / "phase_c" / "latest" / "report_human.json"
    if not path.exists():
        return {"result": "FAIL", "message": "Human report not found"}
    return safe_read_json(path)


@router.get("/api/report/ai", summary="AI Report (Contract 5)")
def get_report_ai():
    path = REPORTS_DIR / "phase_c" / "latest" / "report_ai.json"
    if not path.exists():
        return {"result": "FAIL", "message": "AI report not found"}
    return safe_read_json(path)


@router.get(
    "/api/recon/summary",
    summary="Reconciliation Summary (Source of Truth)",
)
def get_recon_summary():
    summary_path = REPORTS_DIR / "phase_c" / "latest" / "recon_summary.json"
    daily_path = REPORTS_DIR / "phase_c" / "latest" / "recon_daily.jsonl"

    if daily_path.exists() and not summary_path.exists():
        return {
            "status": "error",
            "schema": "RECON_SUMMARY_V1",
            "error": "IC_SUMMARY_INCONSISTENT_WITH_DAILY",
            "message": (
                "Daily log exists but Summary is missing. "
                "Reconciler might have failed mid-process."
            ),
        }

    if not summary_path.exists():
        return {
            "status": "not_ready",
            "message": "Recon summary not found",
            "error": "A1_FILE_NOT_FOUND",
        }

    try:
        data = safe_read_json(summary_path)
        if not isinstance(data, dict):
            return {
                "status": "error",
                "message": "Invalid JSON format",
                "error": "A3_JSON_INVALID",
            }

        return {
            "status": "ready",
            "schema": "RECON_SUMMARY_V1",
            "asof": data.get("asof", datetime.now(KST).strftime("%Y-%m-%d")),
            **data,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "error": "A5_UNKNOWN_ERROR",
        }


@router.get(
    "/api/recon/daily",
    summary="Reconciliation Daily Events (Source of Truth)",
)
def get_recon_daily():
    path = REPORTS_DIR / "phase_c" / "latest" / "recon_daily.jsonl"
    if not path.exists():
        return {
            "status": "not_ready",
            "message": "Recon daily not found",
            "rows": [],
            "row_count": 0,
        }
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        rows = [json.loads(line) for line in lines if line.strip()]
        return {
            "status": "ready",
            "schema": "RECON_DAILY_V1",
            "asof": datetime.now(KST).strftime("%Y-%m-%d"),
            "row_count": len(rows),
            "rows": rows,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "rows": [],
            "row_count": 0,
            "error": str(e),
        }
