"""portfolio 라우터 — portfolio CRUD + order_plan + reco + export.

중복 라우트 포함: 1차 정의(실동작) + 2차 정의(shadowed) 모두 이동.
삭제 판단은 S5-6에서 수행.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils import (
    KST,
    BASE_DIR,
    STATE_DIR,
    REPORTS_DIR,
    logger,
    safe_read_json,
)

router = APIRouter()

EXPORT_LATEST_FILE = (
    BASE_DIR
    / "reports"
    / "live"
    / "order_plan_export"
    / "latest"
    / "order_plan_export_latest.json"
)


# --- Models ---


class PortfolioHolding(BaseModel):
    ticker: str
    name: str = ""
    quantity: float
    avg_price: float = 0
    current_price: Optional[float] = None


class PortfolioUpsertRequest(BaseModel):
    cash: float
    holdings: List[PortfolioHolding]


# ══════════════════════════════════════════════
# 1차 정의 (실동작 — 먼저 등록, 매칭됨)
# ══════════════════════════════════════════════


@router.get("/api/portfolio", summary="포트폴리오 조회")
def get_portfolio():
    """현재 포트폴리오 상태 반환"""
    logger.info("포트폴리오 조회 요청 (GET /api/portfolio)")

    path_latest = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
    if path_latest.exists():
        return safe_read_json(path_latest)

    path_legacy = STATE_DIR / "paper_portfolio.json"
    if path_legacy.exists():
        return safe_read_json(path_legacy)

    return {
        "error": "포트폴리오 파일이 없습니다.",
        "cash": 0,
        "holdings": {},
        "total_equity": 0,
    }


@router.post("/api/portfolio/upsert")
async def upsert_portfolio_api_v1(
    confirm: bool = Query(False), payload: Dict = Body(...)
):
    """포트폴리오 저장 (D-P.58) — 1차 정의"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm required",
            },
        )

    try:
        path_latest = (
            BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
        )
        path_latest.parent.mkdir(parents=True, exist_ok=True)

        if "updated_at" not in payload:
            payload["updated_at"] = datetime.now(KST).isoformat()

        with open(path_latest, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2, ensure_ascii=False))

        logger.info(f"포트폴리오 저장 완료: {path_latest}")
        return {"result": "OK", "path": str(path_latest), "data": payload}

    except Exception as e:
        logger.error(f"포트폴리오 저장 실패: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"result": "FAILED", "reason": str(e)},
        )


@router.get("/api/reco/latest", summary="최신 추천 리포트 조회 (P101)")
def get_reco_latest_v1():
    """최신 Reco Report V1 — 1차 정의"""
    path = REPORTS_DIR / "live" / "reco" / "latest" / "reco_latest.json"
    if not path.exists():
        return {
            "schema": "RECO_REPORT_V1",
            "decision": "NO_RECO_YET",
            "reason": "FILE_NOT_FOUND",
            "message": "아직 추천 리포트가 생성되지 않았습니다.",
            "created_at": None,
            "source_bundle": None,
        }
    return safe_read_json(path)


@router.post("/api/reco/regenerate", summary="추천 리포트 최신화 (P101)")
def regenerate_reco_v1(force: bool = Query(False)):
    """Reco regenerate — 1차 정의"""
    try:
        from app.generate_reco_report import generate_reco_report

        return generate_reco_report(force=force)
    except Exception as e:
        logger.error(f"Reco API Error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"result": "ERROR", "message": str(e)},
        )


@router.post("/api/order_plan/regenerate", summary="주문안 최신화 (P102)")
def regenerate_order_plan_v1(force: bool = Query(False)):
    """Order plan regenerate — 1차 정의"""
    try:
        from app.generate_order_plan import generate_order_plan

        return generate_order_plan(force=force)
    except Exception as e:
        logger.error(f"Order Plan API Error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"result": "ERROR", "message": str(e)},
        )


@router.get("/api/order_plan/latest", summary="최신 주문안 조회 (P102)")
def get_order_plan_latest_v1():
    """Order Plan 최신 조회 — 1차 정의"""
    path = REPORTS_DIR / "live" / "order_plan" / "latest" / "order_plan_latest.json"
    if not path.exists():
        return {
            "schema": "ORDER_PLAN_V1",
            "decision": "BLOCKED",
            "reason": "FILE_NOT_FOUND",
            "message": "아직 주문안이 생성되지 않았습니다.",
        }
    return safe_read_json(path)


@router.get(
    "/api/order_plan_export/latest",
    summary="Order Plan Export 최신 조회",
)
def get_order_plan_export_latest():
    """Order Plan Export Latest (P111)"""
    if not EXPORT_LATEST_FILE.exists():
        return {
            "status": "empty",
            "schema": "ORDER_PLAN_EXPORT_V1",
            "data": None,
            "error": "No export generated yet.",
        }

    try:
        data = json.loads(EXPORT_LATEST_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "ORDER_PLAN_EXPORT_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post(
    "/api/order_plan_export/regenerate",
    summary="Order Plan Export 재생성",
)
def regenerate_order_plan_export(
    confirm: bool = Query(False), force: bool = Query(False)
):
    """Regenerate Order Plan Export (P111)"""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "result": "BLOCKED",
                "reason": "CONFIRM_REQUIRED",
            },
        )

    try:
        from app.generate_order_plan_export import generate_export

        generate_export(force=force)

        if EXPORT_LATEST_FILE.exists():
            data = json.loads(EXPORT_LATEST_FILE.read_text(encoding="utf-8"))
            return data
        else:
            return {
                "result": "FAIL",
                "reason": "Generation failed (No file)",
            }

    except ImportError as e:
        logger.error(f"Export import error: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "result": "FAILED",
                "reason": f"Import error: {e}",
            },
        )
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )


# --- /api/portfolio/latest (유일한 정의) ---


@router.get("/api/portfolio/latest")
async def get_portfolio_latest_api():
    """Portfolio 최신 조회"""
    from app.generate_portfolio_snapshot import get_portfolio_latest

    data = get_portfolio_latest()
    if not data:
        return {"result": "NOT_FOUND", "rows": [], "row_count": 0}

    return {"result": "OK", "rows": [data], "row_count": 1}
