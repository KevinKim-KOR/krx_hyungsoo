"""evidence 라우터 — evidence resolve, index, health."""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.utils import (
    KST,
    BASE_DIR,
    logger,
)

router = APIRouter()

# Evidence path constants
EVIDENCE_INDEX_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "index"
EVIDENCE_INDEX_LATEST = EVIDENCE_INDEX_DIR / "evidence_index_latest.json"
HEALTH_DIR = BASE_DIR / "reports" / "ops" / "evidence" / "health"
HEALTH_LATEST_FILE = HEALTH_DIR / "health_latest.json"


@router.get("/api/evidence/resolve", summary="Evidence Ref Resolver")
def resolve_evidence_ref(ref: str):
    """Evidence Ref Resolver (C-P.30/33) - Uses shared ref_validator"""
    from app.utils.ref_validator import validate_and_resolve_ref

    asof = datetime.now(KST).isoformat()

    result = validate_and_resolve_ref(ref)

    if result.http_status_equivalent == 400:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "schema": "EVIDENCE_VIEW_V1",
                "asof": asof,
                "error": {
                    "code": result.decision,
                    "message": result.reason,
                },
            },
        )

    if result.http_status_equivalent == 404:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "schema": "EVIDENCE_VIEW_V1",
                "asof": asof,
                "error": {
                    "code": result.decision,
                    "message": result.reason,
                },
            },
        )

    if result.decision == "PARSE_ERROR":
        return {
            "status": "error",
            "schema": "EVIDENCE_VIEW_V1",
            "asof": asof,
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "PARSE_ERROR",
                "message": result.reason,
            },
            "raw_preview": result.raw_content,
            "guidance": (
                "이 파일은 유효한 JSON이 아닙니다. "
                "Draft라면 Draft Manager에서 재생성해주세요."
            ),
        }

    return {
        "status": "ready",
        "schema": "EVIDENCE_VIEW_V1",
        "asof": asof,
        "row_count": 1,
        "rows": [
            {
                "ref": ref,
                "data": result.data,
                "source": {
                    "kind": result.source_kind,
                    "path": result.resolved_path,
                    "line": result.source_line,
                },
            }
        ],
        "error": None,
    }


@router.get("/api/evidence/index/latest", summary="Evidence Index 최신 조회")
def get_evidence_index_latest():
    """Evidence Index Latest (C-P.31) - Graceful Empty State"""
    if not EVIDENCE_INDEX_LATEST.exists():
        return {
            "status": "ready",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": None,
            "row_count": 0,
            "rows": [],
            "error": {
                "code": "NO_INDEX_YET",
                "message": "Evidence index not generated yet.",
            },
        }

    try:
        data = json.loads(EVIDENCE_INDEX_LATEST.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": data.get("asof"),
            "row_count": data.get("row_count", 0),
            "rows": data.get("rows", []),
            "error": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "schema": "EVIDENCE_INDEX_V1",
            "asof": datetime.now(KST).isoformat(),
            "row_count": 0,
            "rows": [],
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.post("/api/evidence/index/regenerate", summary="Evidence Index 재생성")
def regenerate_evidence_index():
    """Evidence Index Regenerate (C-P.31)"""
    try:
        from app.generate_evidence_index import regenerate_index

        result = regenerate_index()
        return result
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


@router.get("/api/evidence/health/latest", summary="Evidence Health 최신 조회")
def get_evidence_health_latest():
    """Evidence Health Latest (C-P.33) - Graceful Empty State"""
    if not HEALTH_LATEST_FILE.exists():
        return {
            "status": "ready",
            "schema": "EVIDENCE_HEALTH_REPORT_V1",
            "asof": None,
            "summary": {
                "total": 0,
                "pass": 0,
                "warn": 0,
                "fail": 0,
                "decision": "UNKNOWN",
            },
            "checks": [],
            "top_fail_reasons": [],
            "error": {
                "code": "NO_REPORT_YET",
                "message": "Health report not generated yet.",
            },
        }

    try:
        data = json.loads(HEALTH_LATEST_FILE.read_text(encoding="utf-8"))
        return {"status": "ready", **data, "error": None}
    except Exception as e:
        return {
            "status": "error",
            "schema": "EVIDENCE_HEALTH_REPORT_V1",
            "asof": datetime.now(KST).isoformat(),
            "summary": {
                "total": 0,
                "pass": 0,
                "warn": 0,
                "fail": 0,
                "decision": "UNKNOWN",
            },
            "checks": [],
            "top_fail_reasons": [],
            "error": {"code": "READ_ERROR", "message": str(e)},
        }


@router.post("/api/evidence/health/regenerate", summary="Evidence Health 재생성")
def regenerate_evidence_health():
    """Evidence Health Regenerate (C-P.33)"""
    try:
        from app.run_evidence_health_check import regenerate_health_report

        result = regenerate_health_report()
        return result
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
