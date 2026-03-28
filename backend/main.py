# -*- coding: utf-8 -*-
"""
backend/main.py
KRX Alertor Modular - 읽기 전용 옵저버 백엔드

S5-6A: 모든 라우트를 backend/routers/ 로 이전 완료.
이 파일은 앱 팩토리 + 라우터 등록만 담당.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.utils import DASHBOARD_DIR

# --- .env 로딩 (시작 시 1회) ---
try:
    from dotenv import load_dotenv

    _possible_paths = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
        Path(".env"),
    ]
    for _env_file in _possible_paths:
        if _env_file.exists():
            load_dotenv(_env_file, override=False)
            break
except ImportError:
    pass

# --- FastAPI 앱 설정 ---
app = FastAPI(
    title="KRX Alertor Modular Backend",
    description="Read-only Observer Backend + Operator Dashboard",
    version="1.0.0",
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response

    return Response(status_code=204)


# CORS (P99)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 기존 라우터 (변경 없음) ---
from backend import operator_dashboard

app.include_router(operator_dashboard.router)

from backend import dry_run

app.include_router(dry_run.router)

from app.routers import ssot

app.include_router(ssot.router)

try:
    from app.routers import sync

    app.include_router(sync.router)
except ImportError:
    pass

# --- S5 신규 라우터 (등록 순서 = 기존 본문 라우트 순서 보존) ---
from backend.routers import core as _core_router
from backend.routers import portfolio as _portfolio_router
from backend.routers import reporting as _reporting_router
from backend.routers import push as _push_router
from backend.routers import tickets as _tickets_router
from backend.routers import execution_gate as _execution_gate_router
from backend.routers import deps as _deps_router
from backend.routers import ops as _ops_router
from backend.routers import secrets as _secrets_router
from backend.routers import real_sender as _real_sender_router
from backend.routers import manual_execution as _manual_execution_router
from backend.routers import settings as _settings_router
from backend.routers import operator as _operator_router
from backend.routers import evidence as _evidence_router
from backend.routers import strategy_bundle as _strategy_bundle_router
from backend.routers import live_cycle as _live_cycle_router

# 등록 순서: 기존 main.py 본문의 @app 데코레이터 등장 순서와 동일
app.include_router(_core_router.router)  # /, status, signals, history, raw
app.include_router(_portfolio_router.router)  # portfolio, reco, order_plan, export
app.include_router(
    _reporting_router.router
)  # contract5, diagnosis, gatekeeper, report, recon
app.include_router(_push_router.router)  # push/*
app.include_router(_tickets_router.router)  # tickets/*
app.include_router(
    _execution_gate_router.router
)  # gate, emergency, approvals, window, allowlist, preflight
app.include_router(_deps_router.router)  # deps/*
app.include_router(
    _ops_router.router
)  # ops/daily, health, cycle, scheduler, summary, drill, postmortem, live_fire
app.include_router(_secrets_router.router)  # secrets/*
app.include_router(_real_sender_router.router)  # real_sender_enable
app.include_router(_manual_execution_router.router)  # execution_prep, ticket, record
app.include_router(
    _settings_router.router
)  # settings/mode, settings, spike, watchlist, transport
app.include_router(_operator_router.router)  # operator/sync_cycle
app.include_router(_evidence_router.router)  # evidence/*
app.include_router(_strategy_bundle_router.router)  # strategy_bundle/*
app.include_router(_live_cycle_router.router)  # live/cycle/*

# Static Files (Dashboard)
if DASHBOARD_DIR.exists():
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(DASHBOARD_DIR)),
        name="dashboard",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
