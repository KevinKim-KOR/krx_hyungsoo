import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from utils.env import load_env_if_present

from .routes.backtest import router as backtest_router
from .routes.assets import router as assets_router
from .routes.dashboard import router as dashboard_router
from .routes.holdings import router as holdings_router
from .routes.market import router as market_router
from .routes.note import router as note_router
from .routes.rank import router as rank_router
from .routes.snapshots import router as snapshots_router
from .routes.stocks import router as stocks_router
from .routes.system import router as system_router
from .routes.ticker_detail import router as ticker_detail_router
from .routes.weekly import router as weekly_router

load_env_if_present()

logger = logging.getLogger(__name__)

app = FastAPI(title="Momentum ETF Internal API")


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """클라이언트 입력 오류 → 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(_request: Request, exc: RuntimeError) -> JSONResponse:
    """서버 내부 오류 → 500. 스택트레이스는 로그에만 남긴다."""
    logger.exception("RuntimeError in request handler")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(_request: Request, exc: FileNotFoundError) -> JSONResponse:
    """파일 누락 오류 → 500."""
    logger.exception("FileNotFoundError in request handler")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """처리되지 않은 예외 → 500. 상세 메시지를 클라이언트에 전달한다."""
    logger.exception("Unhandled exception in request handler")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.include_router(backtest_router)
app.include_router(assets_router)
app.include_router(holdings_router)
app.include_router(dashboard_router)
app.include_router(market_router)
app.include_router(note_router)
app.include_router(rank_router)
app.include_router(snapshots_router)
app.include_router(stocks_router)
from pymongo.errors import PyMongoError, NetworkTimeout
from fastapi import Request
from starlette.responses import JSONResponse

@app.middleware("http")
async def catch_mongodb_errors(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        is_db_timeout = False
        if isinstance(exc, NetworkTimeout):
            is_db_timeout = True
        elif isinstance(exc, PyMongoError) and "time out" in str(exc).lower():
            is_db_timeout = True
        elif "pymongo" in str(exc).lower() and "timeout" in str(exc).lower():
            is_db_timeout = True
            
        if is_db_timeout:
            global _LAST_DB_ERROR_TIME
            _LAST_DB_ERROR_TIME = time.time()
            return JSONResponse(status_code=503, content={"detail": "몽고디비 서버 연결 지연(타임아웃)이 발생했습니다."})
        raise exc

app.include_router(system_router)
app.include_router(ticker_detail_router)
app.include_router(weekly_router)
import time
_LAST_DB_ERROR_TIME = 0.0

@app.post("/internal/health/report_error")
def report_error() -> dict[str, str]:
    global _LAST_DB_ERROR_TIME
    _LAST_DB_ERROR_TIME = time.time()
    return {"status": "ok"}

@app.get("/internal/health")
def health() -> dict[str, str]:
    from utils.db_manager import get_db_connection

    db = get_db_connection()
    if db is None:
        return JSONResponse(status_code=503, content={"status": "error", "detail": "DB 연결 실패"})

    global _LAST_DB_ERROR_TIME
    if time.time() - _LAST_DB_ERROR_TIME < 60:
        return JSONResponse(status_code=503, content={"status": "error", "detail": "다른 API에서 최근 DB 통신 타임아웃이 보고되었습니다."})

    try:
        db.command("ping")
        # 실제 쿼리가 처리되는지만 점검하기 위해 timeLimit을 2초로 줍니다.
        db.stock_meta.find_one({}, max_time_ms=2000)
    except Exception as e:
        logger.warning(f"Health check DB query failed: {e}")
        return JSONResponse(status_code=503, content={"status": "error", "detail": f"DB 쿼리 시간 초과: {e}"})

    return {"status": "ok"}
