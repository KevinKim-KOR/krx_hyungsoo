# -*- coding: utf-8 -*-
"""strategy_bundle 라우터 — /api/strategy_bundle."""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils import KST, logger

router = APIRouter()


# --- 모델 ---
class StrategyBundleSnapshotRequest(BaseModel):
    confirm: bool = False


# --- 라우트 ---
@router.get("/api/strategy_bundle/latest", summary="Strategy Bundle 최신 조회")
def get_strategy_bundle_latest():
    """
    Strategy Bundle Latest (C-P.47)

    PC에서 생성된 전략 번들 조회 + 검증 결과 반환
    Fail-Closed: 검증 실패 시 번들 미반환
    """
    try:
        from app.load_strategy_bundle import (
            load_latest_bundle,
            get_bundle_status,
            list_snapshots,
        )

        bundle, validation = load_latest_bundle()
        status = get_bundle_status()
        snapshots = list_snapshots()

        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "ready" if bundle else "not_ready",
            "bundle": bundle,  # None if validation failed (Fail-Closed)
            "validation": {
                "decision": validation.decision,
                "valid": validation.valid,
                "bundle_id": validation.bundle_id,
                "created_at": validation.created_at,
                "strategy_name": validation.strategy_name,
                "strategy_version": validation.strategy_version,
                "issues": validation.issues,
                "warnings": validation.warnings,
            },
            "summary": status,
            "snapshots": snapshots[:5],  # 최근 5개
            "error": (
                None
                if bundle
                else {
                    "code": validation.decision,
                    "message": "; ".join(validation.issues),
                }
            ),
        }
    except ImportError as e:
        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "error",
            "bundle": None,
            "validation": None,
            "error": {"code": "IMPORT_ERROR", "message": str(e)},
        }
    except Exception as e:
        return {
            "schema": "STRATEGY_BUNDLE_V1",
            "asof": datetime.now(KST).isoformat(),
            "status": "error",
            "bundle": None,
            "validation": None,
            "error": {"code": "UNKNOWN_ERROR", "message": str(e)},
        }


@router.post(
    "/api/strategy_bundle/regenerate_snapshot",
    summary="Strategy Bundle Snapshot 생성",
)
def regenerate_strategy_bundle_snapshot(data: StrategyBundleSnapshotRequest):
    """
    Strategy Bundle Snapshot 생성 (C-P.47)

    latest를 snapshot으로 복제 (고정 경로만, 입력 경로 금지)
    Confirm Guard: confirm=true 필수
    """
    # Confirm Guard
    if not data.confirm:
        return JSONResponse(
            status_code=400,
            content={
                "result": "BLOCKED",
                "message": "Confirm guard: set confirm=true to proceed",
                "snapshot_ref": None,
            },
        )

    try:
        from app.load_strategy_bundle import regenerate_snapshot

        result = regenerate_snapshot()

        if result["success"]:
            logger.info(f"Strategy bundle snapshot created: {result['snapshot_ref']}")
            return {
                "result": "OK",
                "snapshot_ref": result["snapshot_ref"],
                "bundle_id": result.get("bundle_id"),
                "created_at": result.get("created_at"),
            }
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "result": "FAILED",
                    "message": result.get("error", "Unknown error"),
                    "snapshot_ref": None,
                },
            )
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": f"Import error: {e}"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"result": "FAILED", "reason": str(e)},
        )
