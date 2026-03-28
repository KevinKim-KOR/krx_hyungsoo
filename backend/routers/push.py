# -*- coding: utf-8 -*-
"""backend/routers/push.py – Push 관련 API 라우터."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.utils import KST, BASE_DIR, REPORTS_DIR, logger, safe_read_json

router = APIRouter(prefix="/api/push", tags=["push"])

# --- Path constants ---
PUSH_DIR = REPORTS_DIR / "push" / "latest"
PUSH_DELIVERY_LATEST = (
    BASE_DIR / "reports" / "ops" / "push" / "push_delivery_latest.json"
)
PREVIEW_LATEST = (
    BASE_DIR / "reports" / "ops" / "push" / "preview" / "preview_latest.json"
)
SEND_LATEST_FILE = BASE_DIR / "reports" / "ops" / "push" / "send" / "send_latest.json"


# ============================================================================
# Push Messages (Phase C-P.1)
# ============================================================================


@router.get("/latest", summary="Push Messages (Latest)")
def get_push_latest():
    """최신 Push 메시지 목록 반환"""
    path = PUSH_DIR / "push_messages.json"
    if not path.exists():
        return {
            "status": "not_ready",
            "schema": "PUSH_MESSAGE_V1",
            "asof": datetime.now(KST).isoformat(),
            "row_count": 0,
            "rows": [],
            "error": "PUSH_FILE_NOT_FOUND",
        }
    try:
        data = safe_read_json(path)
        # Envelope 포맷 보장
        if "rows" not in data:
            data["rows"] = []
        if "status" not in data:
            data["status"] = "ready"
        if "schema" not in data:
            data["schema"] = "PUSH_MESSAGE_V1"
        if "row_count" not in data:
            data["row_count"] = len(data.get("rows", []))
        if "asof" not in data:
            data["asof"] = datetime.now(KST).isoformat()
        if "error" not in data:
            data["error"] = None
        return data
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "rows": [],
            "row_count": 0,
            "error": str(e),
        }


# ============================================================================
# Push Delivery (C-P.18)
# ============================================================================


@router.get("/delivery/latest", summary="푸시 발송 결정 최신 조회")
def get_push_delivery_latest():
    """Push Delivery Latest Receipt (C-P.18)"""
    if not PUSH_DELIVERY_LATEST.exists():
        return {
            "status": "empty",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "data": None,
            "error": "No delivery receipt yet",
        }

    try:
        data = json.loads(PUSH_DELIVERY_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "asof": data.get("asof"),
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/delivery/run", summary="푸시 발송 결정 사이클 실행")
def run_push_delivery_cycle_api():
    """Push Delivery Cycle Runner API (C-P.18)"""
    try:
        from app.run_push_delivery_cycle import run_push_delivery_cycle

        result = run_push_delivery_cycle()
        return {
            "status": "ready",
            "schema": "PUSH_DELIVERY_RECEIPT_V1",
            "data": result,
            "error": None,
        }
    except ImportError as e:
        logger.error(f"Import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": f"Import error: {e}"},
        )
    except Exception as e:
        logger.error(f"Push delivery error: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


# ============================================================================
# Push Preview (C-P.22)
# ============================================================================


@router.get("/preview/latest", summary="푸시 렌더 프리뷰 최신 조회")
def get_push_preview_latest():
    """Push Render Preview Latest (C-P.22)"""
    if not PREVIEW_LATEST.exists():
        return {
            "status": "empty",
            "schema": "PUSH_RENDER_PREVIEW_V1",
            "row_count": 0,
            "rows": [],
            "error": "No preview generated yet. Generate via push delivery cycle.",
        }

    try:
        data = json.loads(PREVIEW_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_RENDER_PREVIEW_V1",
            "asof": data.get("asof"),
            "row_count": len(data.get("rendered", [])),
            "rows": data.get("rendered", []),
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============================================================================
# Push Send (C-P.23)
# ============================================================================


@router.get("/send/latest", summary="최신 발송 결과 조회")
def get_push_send_latest():
    """Push Send Latest (C-P.23)"""
    if not SEND_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "PUSH_SEND_RECEIPT_V1",
            "data": None,
            "error": "No send receipt yet",
        }

    try:
        data = json.loads(SEND_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "PUSH_SEND_RECEIPT_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/send/run", summary="푸시 발송 실행 (One-Shot)")
def run_push_send():
    """Push Send Run (C-P.23) - One-Shot Telegram Only"""
    try:
        from app.run_push_send_cycle import run_push_send_cycle

        result = run_push_send_cycle()
        logger.info(f"Push send: {result.get('decision')} - {result.get('message')}")
        return result
    except ImportError as e:
        logger.error(f"Push send import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": f"Import error: {e}"},
        )
    except Exception as e:
        logger.error(f"Push send error: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


# ============================================================================
# Daily Status Push (D-P.55 + D-P.56)
# ============================================================================


@router.post("/daily_status/send")
async def push_daily_status_send(
    confirm: bool = Query(False),
    mode: str = Query("normal", description="normal=1일1회, test=idempotency우회"),
):
    """
    Daily Status Push - 오늘 운영 상태 1줄 요약 발송
    Confirm Guard: confirm=true 필수
    Idempotency: mode=normal이면 1일 1회, mode=test면 우회
    """
    # Confirm Guard
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
            },
        )

    # Validate mode
    if mode not in ("normal", "test"):
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": f"Invalid mode: {mode}. Use 'normal' or 'test'",
            },
        )

    try:
        from app.generate_daily_status_push import generate_daily_status_push

        result = generate_daily_status_push(mode=mode)

        logger.info(
            f"Daily status push: {result.get('idempotency_key')} mode={mode} "
            f"skipped={result.get('skipped')} delivery={result.get('delivery_actual')}"
        )

        return result

    except Exception as e:
        logger.error(f"Daily status push failed: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/daily_status/latest")
async def get_daily_status_latest():
    """Daily Status Push 최신 조회"""
    latest_path = Path("reports/ops/push/daily_status/latest/daily_status_latest.json")

    if not latest_path.exists():
        return {"result": "NOT_FOUND", "rows": [], "row_count": 0}

    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return {"result": "OK", "rows": [data], "row_count": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


# ============================================================================
# Incident Push (D-P.57)
# ============================================================================


@router.post("/incident/send")
async def push_incident_send(
    confirm: bool = Query(False),
    mode: str = Query("normal", description="normal=하루1회, test=우회"),
    kind: str = Query(
        ...,
        description="BACKEND_DOWN, OPS_BLOCKED, OPS_FAILED, LIVE_BLOCKED, LIVE_FAILED, PUSH_FAILED",
    ),
    step: str = Query("Unknown"),
    reason: str = Query("Unknown"),
):
    """
    Incident Push - 장애/차단 즉시 알림
    Confirm Guard: confirm=true 필수
    Idempotency: incident_<KIND>_YYYYMMDD (동일 타입 하루 1회)
    """
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
            },
        )

    if mode not in ("normal", "test"):
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": f"Invalid mode: {mode}"},
        )

    try:
        from app.generate_incident_push import generate_incident_push

        result = generate_incident_push(kind=kind, step=step, reason=reason, mode=mode)

        logger.info(
            f"Incident push: {kind} mode={mode} "
            f"skipped={result.get('skipped')} delivery={result.get('delivery_actual')}"
        )

        return result

    except Exception as e:
        logger.error(f"Incident push failed: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/incident/latest")
async def get_incident_latest():
    """Incident Push 최신 조회"""
    latest_path = Path("reports/ops/push/incident/latest/incident_latest.json")

    if not latest_path.exists():
        return {"result": "NOT_FOUND", "rows": [], "row_count": 0}

    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return {"result": "OK", "rows": [data], "row_count": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


# ============================================================================
# Spike Push (D-P.61)
# ============================================================================


@router.post("/spike/run")
async def run_spike_push_api(confirm: bool = Query(False)):
    """Spike Push 실행 (OCI Cron)"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    try:
        from app.run_spike_push import run_spike_push

        return run_spike_push()
    except Exception as e:
        logger.error(f"Spike run failed: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/spike/latest")
async def get_spike_latest_api():
    """Spike Push 최신 조회"""
    path = Path("reports/ops/push/spike_watch/latest/spike_watch_latest.json")
    if not path.exists():
        return {"result": "NOT_FOUND"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"result": "ERROR", "reason": str(e)}


# ============================================================================
# Holding Watch (D-P.66)
# ============================================================================


@router.post("/holding/run")
async def run_holding_watch_api(confirm: bool = Query(False)):
    """Holding Watch 실행 (OCI Cron / Monitor)"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    try:
        from app.run_holding_watch import run_holding_watch

        return run_holding_watch()
    except Exception as e:
        logger.error(f"Holding run failed: {e}")
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/holding/latest")
async def get_holding_latest_api():
    """Holding Watch 최신 조회"""
    path = Path("reports/ops/push/holding_watch/latest/holding_watch_latest.json")
    if not path.exists():
        return {"result": "NOT_FOUND"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"result": "ERROR", "reason": str(e)}
