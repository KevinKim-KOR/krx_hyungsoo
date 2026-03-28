# -*- coding: utf-8 -*-
"""real_sender 라우터 — /api/real_sender_enable."""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.utils import KST, STATE_DIR, logger

router = APIRouter()

# --- 상수 ---
SENDER_ENABLE_FILE = STATE_DIR / "real_sender_enable.json"


# --- 모델 ---
class SenderEnableRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None


# --- 라우트 ---
@router.get("/api/real_sender_enable", summary="Real Sender 활성화 상태 조회")
def get_real_sender_enable():
    """Real Sender Enable Status (C-P.23)"""
    if not SENDER_ENABLE_FILE.exists():
        return {
            "status": "ready",
            "schema": "REAL_SENDER_ENABLE_V1",
            "data": {
                "enabled": False,
                "channel": "TELEGRAM_ONLY",
                "updated_at": None,
                "updated_by": None,
                "reason": "Not configured",
            },
            "error": None,
        }

    try:
        data = json.loads(SENDER_ENABLE_FILE.read_text(encoding="utf-8"))
        return {
            "status": "ready",
            "schema": "REAL_SENDER_ENABLE_V1",
            "data": data,
            "error": None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/api/real_sender_enable", summary="Real Sender 활성화/비활성화")
def set_real_sender_enable(request: SenderEnableRequest):
    """Real Sender Enable/Disable (C-P.23)"""
    # Enable requires reason
    if request.enabled and not request.reason:
        raise HTTPException(
            status_code=400,
            detail={"error": "reason is required when enabling"},
        )

    data = {
        "schema": "REAL_SENDER_ENABLE_V1",
        "enabled": request.enabled,
        "channel": "TELEGRAM_ONLY",
        "updated_at": datetime.now(KST).isoformat(),
        "updated_by": "api",
        "reason": request.reason or "Disabled",
    }

    SENDER_ENABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SENDER_ENABLE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(
        f"Real sender {'enabled' if request.enabled else 'disabled'}: {request.reason}"
    )

    return {
        "result": "OK",
        "enabled": request.enabled,
        "channel": "TELEGRAM_ONLY",
    }
