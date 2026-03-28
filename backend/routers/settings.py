# -*- coding: utf-8 -*-
"""settings 라우터 — /api/settings, /api/spike_settings, /api/watchlist, etc."""

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.utils import KST, BASE_DIR, STATE_DIR, logger

router = APIRouter()


# --- 모델 ---
class SystemModeRequest(BaseModel):
    enabled: bool  # Replay Enabled
    mode: Optional[str] = "LIVE"
    asof_kst: Optional[str] = None
    simulate_trade_day: Optional[bool] = False
    token: Optional[str] = None


class WatchlistItem(BaseModel):
    ticker: str
    name: str = ""
    enabled: bool = True


class WatchlistUpsertRequest(BaseModel):
    items: List[WatchlistItem]


# --- 라우트: System Mode ---
@router.post("/api/settings/mode", summary="Set System Mode (Replay/Live)")
def set_system_mode(req: SystemModeRequest):
    """Update asof_override_latest.json from PC Cockpit."""
    try:
        path = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "enabled": req.enabled,
            "mode": req.mode or ("REPLAY" if req.enabled else "LIVE"),
            "asof_kst": req.asof_kst,
            "simulate_trade_day": req.simulate_trade_day,
            "updated_at": datetime.now(KST).isoformat(),
        }

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"System Mode Updated: {data}")
        return {"result": "OK", "data": data}

    except Exception as e:
        logger.error(f"Failed to set system mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings/mode", summary="Get System Mode")
def get_system_mode():
    """Read current asof_override_latest.json"""
    path = BASE_DIR / "state" / "runtime" / "asof_override_latest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enabled": False, "mode": "LIVE"}


# --- 라우트: Unified Settings ---
@router.get("/api/settings", summary="통합 설정 조회")
def get_unified_settings():
    """통합 설정(Spike + Holding) 최신 상태 반환"""
    from app.generate_settings import load_settings

    data = load_settings()
    return {"result": "OK", "data": data}


@router.post("/api/settings/upsert", summary="통합 설정 저장")
async def upsert_unified_settings(
    confirm: bool = Query(False), payload: dict = Body(...)
):
    """통합 설정 저장 (Spike/Holding 섹션 병합)"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    from app.generate_settings import upsert_settings

    res = upsert_settings(payload, confirm=confirm)
    if res.get("result") != "OK":
        return JSONResponse(status_code=500, content=res)
    return res


# --- 라우트: Spike Settings ---
@router.post("/api/spike_settings/upsert")
async def upsert_spike_settings_api(payload: dict, confirm: bool = Query(False)):
    """Spike 감시 설정 저장"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    try:
        from app.generate_spike_settings import upsert_spike_settings

        return upsert_spike_settings(payload)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/api/spike_settings/latest")
async def get_spike_settings_latest_api():
    """Spike 감시 설정 조회"""
    from app.generate_spike_settings import load_spike_settings

    data = load_spike_settings()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# --- 라우트: Watchlist ---
@router.post("/api/watchlist/upsert")
async def upsert_watchlist_api(
    payload: WatchlistUpsertRequest, confirm: bool = Query(False)
):
    """Watchlist 저장 (PC UI)"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    try:
        from app.generate_watchlist import upsert_watchlist

        items_dicts = [i.dict() for i in payload.items]
        return upsert_watchlist(items_dicts)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"result": "FAILED", "reason": str(e)}
        )


@router.get("/api/watchlist/latest")
async def get_watchlist_latest_api():
    """Watchlist 최신 조회"""
    from app.generate_watchlist import load_watchlist

    data = load_watchlist()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# --- 라우트: Watchlist Candidates ---
@router.post("/api/watchlist_candidates/regenerate")
async def regenerate_candidates_api(confirm: bool = Query(False)):
    """후보 리스트 생성 (Backtest/Reco 기반)"""
    if not confirm:
        return JSONResponse(
            status_code=400,
            content={"result": "BLOCKED", "message": "Confirm required"},
        )

    try:
        from app.generate_watchlist_candidates import generate_candidates

        return generate_candidates(confirm=True)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"result": "FAILED", "reason": str(e)},
        )


@router.get("/api/watchlist_candidates/latest")
async def get_candidates_latest_api():
    """후보 리스트 조회"""
    from app.generate_watchlist_candidates import get_latest_candidates

    data = get_latest_candidates()
    if not data:
        return {"result": "NOT_FOUND"}
    return {"result": "OK", "data": data}


# --- 라우트: Git Transport ---
@router.post("/api/transport/sync", summary="State 파일 OCI 동기화")
async def sync_state_to_remote_api(confirm: bool = Query(True)):
    """
    Git Transport: State 파일만 Commit & Push
    - Code 변경이 있으면 BLOCKED
    """
    try:
        from app.run_git_transport import sync_state_to_remote

        return sync_state_to_remote(confirm=confirm)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"result": "FAILED", "reason": str(e)},
        )
