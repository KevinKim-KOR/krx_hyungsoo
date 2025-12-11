#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
api_backtest.py
Backtest & Tuning API - PC 전용 (Port 8001)
단일 책임: API 엔드포인트만 담당
"""
import logging
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from app.services.backtest_service import (  # noqa: E402
    BacktestParams as BacktestParamsInternal,
    BacktestService,
)
from app.services.tuning_service import (  # noqa: E402
    TuningParams as TuningParamsInternal,
    TuningService,
)
from app.services.optimal_params_service import OptimalParamsService  # noqa: E402

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="Backtest & Tuning API",
    description="PC 전용 - 실제 백테스트, Optuna 튜닝 API",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서비스 인스턴스 (싱글톤)
_backtest_service = None
_tuning_service = None
_optimal_params_service = OptimalParamsService()


def get_backtest_service() -> BacktestService:
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service


def get_tuning_service() -> TuningService:
    global _tuning_service
    if _tuning_service is None:
        _tuning_service = TuningService()
    return _tuning_service


# ============================================
# Request/Response 모델 (API용)
# ============================================
class BacktestRequest(BaseModel):
    """백테스트 요청"""

    start_date: str
    end_date: str
    ma_period: int
    rsi_period: int
    stop_loss: float
    initial_capital: int = 10000000
    max_positions: int = 5
    enable_defense: bool = True

    @validator("start_date", "end_date")
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("날짜 형식은 YYYY-MM-DD 이어야 합니다")
        return v

    @validator("ma_period")
    def validate_ma_period(cls, v):
        if v < 5 or v > 200:
            raise ValueError("ma_period는 5~200 범위여야 합니다")
        return v

    @validator("rsi_period")
    def validate_rsi_period(cls, v):
        if v < 2 or v > 50:
            raise ValueError("rsi_period는 2~50 범위여야 합니다")
        return v

    @validator("stop_loss")
    def validate_stop_loss(cls, v):
        if v > 0 or v < -50:
            raise ValueError("stop_loss는 -50~0 범위여야 합니다")
        return v

    @validator("initial_capital")
    def validate_capital(cls, v):
        if v < 1000000:
            raise ValueError("initial_capital은 최소 1,000,000 이상이어야 합니다")
        return v

    @validator("max_positions")
    def validate_positions(cls, v):
        if v < 1 or v > 50:
            raise ValueError("max_positions는 1~50 범위여야 합니다")
        return v


class BacktestResponse(BaseModel):
    """백테스트 응답"""

    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    num_trades: int
    win_rate: float
    volatility: float
    calmar_ratio: float


class TuningRequest(BaseModel):
    """튜닝 요청"""

    trials: int
    start_date: str
    end_date: str
    lookback_months: List[int] = [3, 6, 12]  # 기본값: 3, 6, 12개월
    optimization_metric: str = "sharpe"  # 기본값: sharpe

    @validator("trials")
    def validate_trials(cls, v):
        if v < 10 or v > 1000:
            raise ValueError("trials는 10~1000 범위여야 합니다")
        return v

    @validator("lookback_months")
    def validate_lookback(cls, v):
        if not v:
            raise ValueError("lookback_months는 최소 1개 이상이어야 합니다")
        for m in v:
            if m < 1 or m > 36:
                raise ValueError("lookback_months 각 값은 1~36 범위여야 합니다")
        return v

    @validator("optimization_metric")
    def validate_metric(cls, v):
        if v not in ["sharpe", "cagr", "calmar"]:
            raise ValueError("optimization_metric은 sharpe, cagr, calmar 중 하나여야 합니다")
        return v


class TuningStatusResponse(BaseModel):
    """튜닝 상태 응답"""

    is_running: bool
    current_trial: int
    total_trials: int
    best_sharpe: float
    best_params: dict | None
    trials: list
    lookback_results: dict


# ============================================
# API 엔드포인트
# ============================================
@app.post("/api/v1/backtest/run", response_model=BacktestResponse)
def run_backtest(request: BacktestRequest):
    """백테스트 실행"""
    try:
        service = get_backtest_service()

        params = BacktestParamsInternal(
            start_date=datetime.strptime(request.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.end_date, "%Y-%m-%d").date(),
            ma_period=request.ma_period,
            rsi_period=request.rsi_period,
            stop_loss=request.stop_loss,
            initial_capital=request.initial_capital,
            max_positions=request.max_positions,
            enable_defense=request.enable_defense,
        )

        result = service.run(params)

        logger.info(f"백테스트 완료: CAGR={result.cagr:.2f}%, Sharpe={result.sharpe_ratio:.2f}")

        return BacktestResponse(
            cagr=result.cagr,
            sharpe_ratio=result.sharpe_ratio,
            max_drawdown=result.max_drawdown,
            total_return=result.total_return,
            num_trades=result.num_trades,
            win_rate=result.win_rate,
            volatility=result.volatility,
            calmar_ratio=result.calmar_ratio,
        )

    except ValueError as e:
        logger.error(f"백테스트 실패: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"백테스트 오류: {e}")
        raise HTTPException(status_code=500, detail=f"백테스트 실행 오류: {e}")


class SplitMetricsResponse(BaseModel):
    """분할 구간 성과 응답"""

    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    num_trades: int


class EngineHealthResponse(BaseModel):
    """엔진 헬스체크 응답"""

    is_valid: bool
    warnings: List[str]


class ExtendedBacktestResponse(BaseModel):
    """확장된 백테스트 응답 (Train/Val/Test + engine_health)"""

    # 전체 성과
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    num_trades: int
    win_rate: float
    volatility: float
    calmar_ratio: float
    # Train/Val/Test
    train: SplitMetricsResponse | None = None
    val: SplitMetricsResponse | None = None
    test: SplitMetricsResponse | None = None
    # 엔진 헬스체크
    engine_health: EngineHealthResponse | None = None
    # 일별 로그 (최근 N개)
    daily_logs: list | None = None
    # 경고
    warnings: List[str] | None = None


@app.post("/api/v1/backtest/run-split", response_model=ExtendedBacktestResponse)
def run_backtest_with_split(request: BacktestRequest):
    """Train/Val/Test 분할 백테스트 실행"""
    try:
        service = get_backtest_service()

        params = BacktestParamsInternal(
            start_date=datetime.strptime(request.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.end_date, "%Y-%m-%d").date(),
            ma_period=request.ma_period,
            rsi_period=request.rsi_period,
            stop_loss=request.stop_loss,
            initial_capital=request.initial_capital,
            max_positions=request.max_positions,
            enable_defense=request.enable_defense,
        )

        result = service.run_with_split(params)

        logger.info(
            f"분할 백테스트 완료: CAGR={result.metrics.cagr:.2f}%, "
            f"Train Sharpe={result.train_metrics.sharpe_ratio if result.train_metrics else 'N/A'}, "
            f"Test Sharpe={result.test_metrics.sharpe_ratio if result.test_metrics else 'N/A'}"
        )

        return ExtendedBacktestResponse(
            cagr=result.metrics.cagr,
            sharpe_ratio=result.metrics.sharpe_ratio,
            max_drawdown=result.metrics.max_drawdown,
            total_return=result.metrics.total_return,
            num_trades=result.metrics.num_trades,
            win_rate=result.metrics.win_rate,
            volatility=result.metrics.volatility,
            calmar_ratio=result.metrics.calmar_ratio,
            train=(
                SplitMetricsResponse(
                    cagr=result.train_metrics.cagr,
                    sharpe_ratio=result.train_metrics.sharpe_ratio,
                    max_drawdown=result.train_metrics.max_drawdown,
                    num_trades=result.train_metrics.num_trades,
                )
                if result.train_metrics
                else None
            ),
            val=(
                SplitMetricsResponse(
                    cagr=result.val_metrics.cagr,
                    sharpe_ratio=result.val_metrics.sharpe_ratio,
                    max_drawdown=result.val_metrics.max_drawdown,
                    num_trades=result.val_metrics.num_trades,
                )
                if result.val_metrics
                else None
            ),
            test=(
                SplitMetricsResponse(
                    cagr=result.test_metrics.cagr,
                    sharpe_ratio=result.test_metrics.sharpe_ratio,
                    max_drawdown=result.test_metrics.max_drawdown,
                    num_trades=result.test_metrics.num_trades,
                )
                if result.test_metrics
                else None
            ),
            engine_health=(
                EngineHealthResponse(
                    is_valid=result.engine_health.get("is_valid", False),
                    warnings=result.engine_health.get("warnings", []),
                )
                if result.engine_health
                else None
            ),
            daily_logs=result.daily_logs,
            warnings=result.warnings,
        )

    except ValueError as e:
        logger.error(f"분할 백테스트 실패: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"분할 백테스트 오류: {e}")
        raise HTTPException(status_code=500, detail=f"분할 백테스트 실행 오류: {e}")


@app.post("/api/v1/tuning/start")
def start_tuning(request: TuningRequest):
    """튜닝 시작"""
    try:
        service = get_tuning_service()

        params = TuningParamsInternal(
            trials=request.trials,
            start_date=datetime.strptime(request.start_date, "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.end_date, "%Y-%m-%d").date(),
            lookback_months=request.lookback_months,
            optimization_metric=request.optimization_metric,
        )

        service.start(params)

        return {"message": "튜닝 시작됨", "trials": request.trials}

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"튜닝 시작 오류: {e}")
        raise HTTPException(status_code=500, detail=f"튜닝 시작 오류: {e}")


@app.post("/api/v1/tuning/stop")
def stop_tuning():
    """튜닝 중지"""
    service = get_tuning_service()
    service.stop()
    return {"message": "튜닝 중지 요청됨"}


@app.get("/api/v1/tuning/status", response_model=TuningStatusResponse)
def get_tuning_status():
    """튜닝 상태 조회"""
    service = get_tuning_service()
    state = service.state

    return TuningStatusResponse(
        is_running=state.is_running,
        current_trial=state.current_trial,
        total_trials=state.total_trials,
        best_sharpe=state.best_sharpe,
        best_params=state.best_params,
        trials=state.trials[:10],
        lookback_results=state.lookback_results,
    )


# ============================================
# AI 분석 API
# ============================================


class TuningTrialPayload(BaseModel):
    """AI 분석용 튜닝 Trial 페이로드"""

    lookback: str  # "3M", "6M", "12M"
    trial_id: int
    strategy: str = "Momentum ETF"
    params: dict  # ma_period, rsi_period, stop_loss
    metrics: dict  # train/val/test → sharpe, cagr, mdd
    engine_health: dict  # is_valid, warnings


class AnalysisResponse(BaseModel):
    """AI 분석 응답"""

    trial_id: int
    lookback: str
    sections: dict  # 7개 섹션


@app.post("/api/v1/tuning/analysis", response_model=AnalysisResponse)
def analyze_tuning_trial(payload: TuningTrialPayload):
    """
    튜닝 Trial AI 분석

    선택된 Trial 데이터를 Claude API로 분석하여 7개 섹션 리포트 반환
    """
    try:
        from app.services.tuning_analysis_service import (
            TuningTrialPayload as ServicePayload,
            get_analysis_service,
        )

        # 엔진 헬스체크
        if not payload.engine_health.get("is_valid", True):
            warnings = payload.engine_health.get("warnings", [])
            raise HTTPException(status_code=400, detail=f"엔진 비정상: {', '.join(warnings)}")

        # 서비스 페이로드 생성
        service_payload = ServicePayload(
            lookback=payload.lookback,
            trial_id=payload.trial_id,
            strategy=payload.strategy,
            params=payload.params,
            metrics=payload.metrics,
            engine_health=payload.engine_health,
        )

        # AI 분석 실행
        service = get_analysis_service()
        result = service.analyze(service_payload)

        return AnalysisResponse(
            trial_id=result["trial_id"],
            lookback=result["lookback"],
            sections=result["sections"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"AI 분석 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI 분석 실패: {str(e)}")


# ============================================
# 히스토리 API
# ============================================
_history_service = None


def get_history_service():
    global _history_service
    if _history_service is None:
        from app.services.history_service import HistoryService

        _history_service = HistoryService()
    return _history_service


@app.get("/api/v1/history/backtests")
def get_backtest_history(
    limit: int = 100,
    run_type: str = None,
    order_by: str = "created_at",
):
    """백테스트 히스토리 조회"""
    service = get_history_service()
    history = service.get_backtest_history(
        limit=limit,
        run_type=run_type,
        order_by=order_by,
    )
    return {"history": history, "count": len(history)}


@app.get("/api/v1/history/tuning-sessions")
def get_tuning_sessions(limit: int = 20, status: str = None):
    """튜닝 세션 목록 조회"""
    service = get_history_service()
    sessions = service.get_tuning_sessions(limit=limit, status=status)
    return {"sessions": sessions, "count": len(sessions)}


@app.get("/api/v1/history/tuning-sessions/{session_id}")
def get_tuning_session(session_id: str):
    """튜닝 세션 상세 조회"""
    service = get_history_service()
    session = service.get_tuning_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
    return session


@app.get("/api/v1/history/tuning-sessions/{session_id}/trials")
def get_session_trials(session_id: str):
    """튜닝 세션의 모든 trial 조회"""
    service = get_history_service()
    trials = service.get_session_trials(session_id)
    return {"trials": trials, "count": len(trials)}


@app.get("/api/v1/history/best")
def get_best_backtest(metric: str = "sharpe_ratio"):
    """최고 성과 백테스트 조회"""
    service = get_history_service()
    try:
        best = service.get_best_backtest(metric=metric)
        if not best:
            raise HTTPException(status_code=404, detail="히스토리가 없습니다")
        return best
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/history/statistics")
def get_statistics():
    """전체 통계 조회"""
    service = get_history_service()
    return service.get_statistics()


# ========== 캐시 관리 ==========

# 캐시 업데이트 상태
cache_update_state = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "updated": 0,
    "skipped": 0,  # 이미 최신
    "failed": 0,  # 실제 오류
    "errors": [],  # 오류 상세
    "message": "",
    "last_update": None,
}


@app.get("/api/v1/cache/status")
def get_cache_status():
    """캐시 상태 조회"""
    from pathlib import Path
    import pandas as pd

    cache_dir = Path("data/cache")
    sample_file = cache_dir / "069500.parquet"

    cache_info = {
        "exists": cache_dir.exists(),
        "file_count": len(list(cache_dir.glob("*.parquet"))) if cache_dir.exists() else 0,
        "last_date": None,
    }

    if sample_file.exists():
        try:
            df = pd.read_parquet(sample_file)
            cache_info["last_date"] = df.index.max().strftime("%Y-%m-%d")
        except Exception:
            pass

    return {**cache_info, **cache_update_state}


@app.post("/api/v1/cache/update")
def start_cache_update():
    """캐시 업데이트 시작"""
    global cache_update_state

    if cache_update_state["is_running"]:
        raise HTTPException(status_code=400, detail="이미 업데이트 중입니다")

    def run_update():
        global cache_update_state
        from datetime import date, timedelta
        from pathlib import Path
        import pandas as pd
        from pykrx import stock
        from core.data.filtering import get_filtered_universe

        cache_update_state = {
            "is_running": True,
            "progress": 0,
            "total": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
            "message": "유니버스 로드 중...",
            "last_update": None,
        }

        try:
            cache_dir = Path("data/cache")
            cache_dir.mkdir(parents=True, exist_ok=True)

            tickers = get_filtered_universe()
            cache_update_state["total"] = len(tickers)
            cache_update_state["message"] = f"{len(tickers)}개 ETF 업데이트 시작"

            end_date = date.today()

            for i, ticker in enumerate(tickers):
                try:
                    cache_file = cache_dir / f"{ticker}.parquet"

                    if cache_file.exists():
                        existing = pd.read_parquet(cache_file)
                        last_idx = existing.index.max()

                        # 인덱스 타입에 따라 date로 통일
                        if isinstance(last_idx, pd.Timestamp):
                            last_date = last_idx.date()
                        elif isinstance(last_idx, date):
                            last_date = last_idx
                        else:
                            last_date = pd.to_datetime(last_idx).date()

                        # 이미 최신인 경우 (date끼리 비교)
                        if last_date >= end_date:
                            cache_update_state["skipped"] += 1
                            cache_update_state["progress"] = i + 1
                            continue

                        fetch_start = last_date + timedelta(days=1)
                    else:
                        existing = None
                        fetch_start = end_date - timedelta(days=365)

                    new_data = stock.get_etf_ohlcv_by_date(
                        fetch_start.strftime("%Y%m%d"),
                        end_date.strftime("%Y%m%d"),
                        ticker,
                    )

                    # 데이터 없음 (상장폐지, 거래정지 등)
                    if new_data.empty:
                        cache_update_state["skipped"] += 1
                        cache_update_state["progress"] = i + 1
                        continue

                    new_data.index = pd.to_datetime(new_data.index)
                    new_data.index.name = "날짜"

                    column_map = {
                        "시가": "open",
                        "고가": "high",
                        "저가": "low",
                        "종가": "close",
                        "거래량": "volume",
                        "거래대금": "value",
                        "NAV": "NAV",
                    }
                    new_data = new_data.rename(columns=column_map)

                    if existing is not None:
                        # 기존 인덱스를 Timestamp로 통일 (sort_index 오류 방지)
                        if existing.index.dtype == "object":
                            existing.index = pd.to_datetime(existing.index)

                        for col in existing.columns:
                            if col not in new_data.columns:
                                new_data[col] = 0
                        combined = pd.concat([existing, new_data])
                        combined = combined[~combined.index.duplicated(keep="last")]
                        combined = combined.sort_index()
                    else:
                        combined = new_data

                    combined.to_parquet(cache_file)
                    cache_update_state["updated"] += 1

                except Exception as e:
                    cache_update_state["failed"] += 1
                    # 오류 상세 기록 (최대 10개)
                    if len(cache_update_state["errors"]) < 10:
                        cache_update_state["errors"].append(f"{ticker}: {str(e)[:50]}")

                cache_update_state["progress"] = i + 1
                cache_update_state["message"] = f"진행 중: {i + 1}/{len(tickers)}"

            cache_update_state["message"] = (
                f"완료: {cache_update_state['updated']}개 업데이트, "
                f"{cache_update_state['skipped']}개 스킵, "
                f"{cache_update_state['failed']}개 실패"
            )
            cache_update_state["last_update"] = date.today().isoformat()

        except Exception as e:
            cache_update_state["message"] = f"오류: {str(e)}"
        finally:
            cache_update_state["is_running"] = False

    thread = threading.Thread(target=run_update, daemon=True)
    thread.start()

    return {"message": "캐시 업데이트 시작됨"}


# ============================================================
# 최적 파라미터 저장/로드 API
# ============================================================


class SaveOptimalParamsRequest(BaseModel):
    """최적 파라미터 저장 요청 (Research)"""

    params: dict
    result: dict
    source: str = "manual"
    lookback: str = None  # "3M", "6M", "12M"
    notes: str = ""


class PromoteToLiveRequest(BaseModel):
    """실전 파라미터 승격 요청"""

    params: dict
    result: dict
    trial_id: int = None
    lookback: str = None  # "3M", "6M", "12M"
    notes: str = ""


@app.post("/api/v1/optimal-params/save")
def save_optimal_params(request: SaveOptimalParamsRequest):
    """Research 파라미터 저장 (튜닝 결과)"""
    success = _optimal_params_service.save(
        params=request.params,
        result=request.result,
        source=request.source,
        lookback=request.lookback,
        notes=request.notes,
    )
    if success:
        return {"status": "success", "message": "Research 파라미터 저장 완료"}
    raise HTTPException(status_code=500, detail="저장 실패")


@app.post("/api/v1/optimal-params/promote-to-live")
def promote_to_live(request: PromoteToLiveRequest):
    """
    실전 파라미터로 승격

    튜닝 UI에서 선택한 Trial을 Live로 승격합니다.
    기존 Live는 live_history로 이동됩니다.
    """
    success = _optimal_params_service.promote_to_live(
        params=request.params,
        result=request.result,
        source_trial_id=request.trial_id,
        lookback=request.lookback,
        notes=request.notes,
    )
    if success:
        return {
            "status": "success",
            "message": "Live 파라미터 승격 완료",
            "live": _optimal_params_service.load_live(),
        }
    raise HTTPException(status_code=500, detail="Live 승격 실패")


class SetLiveParamsRequest(BaseModel):
    """Live 파라미터 수동 설정 요청"""

    lookback: str = "3M"  # "3M", "6M", "12M"
    ma_period: int = 60
    rsi_period: int = 14
    stop_loss: float = -10
    max_positions: int = 10
    notes: str = "수동 설정"


@app.get("/api/v1/optimal-params/live")
def get_live_params():
    """현재 Live 파라미터 조회"""
    live = _optimal_params_service.load_live()
    return {"live": live}


@app.post("/api/v1/optimal-params/set-live")
def set_live_params(request: SetLiveParamsRequest):
    """
    Live 파라미터 수동 설정 (튜닝 없이)

    UI에서 직접 파라미터를 입력하여 Live로 설정합니다.
    기존 Live는 live_history로 이동됩니다.
    """
    params = {
        "lookback": request.lookback,
        "ma_period": request.ma_period,
        "rsi_period": request.rsi_period,
        "stop_loss": request.stop_loss,
        "max_positions": request.max_positions,
    }

    # 수동 설정은 result 없이 promote
    success = _optimal_params_service.promote_to_live(
        params=params,
        result={"source": "manual_setting"},
        source_trial_id=None,
        lookback=request.lookback,
        notes=request.notes,
    )

    if success:
        return {
            "status": "success",
            "message": "Live 파라미터 수동 설정 완료",
            "live": _optimal_params_service.load_live(),
        }
    raise HTTPException(status_code=500, detail="Live 설정 실패")


@app.get("/api/v1/optimal-params/live-history")
def get_live_history(limit: int = 10):
    """Live 파라미터 히스토리 조회"""
    history = _optimal_params_service.get_live_history(limit=limit)
    return {"live_history": history, "count": len(history)}


@app.post("/api/v1/optimal-params/rollback-live")
def rollback_live(history_index: int = 0):
    """
    이전 Live 파라미터로 롤백

    Args:
        history_index: live_history 인덱스 (0 = 가장 최근)
    """
    success = _optimal_params_service.rollback_live(history_index)
    if success:
        return {
            "status": "success",
            "message": "Live 롤백 완료",
            "live": _optimal_params_service.load_live(),
        }
    raise HTTPException(status_code=400, detail="롤백할 히스토리가 없습니다")


# ========== 하위 호환성 API (deprecated) ==========


@app.get("/api/v1/optimal-params/current")
def get_current_optimal_params():
    """현재 활성 최적 파라미터 조회 (deprecated: /live 사용)"""
    current = _optimal_params_service.load_current()
    return {"current": current}


@app.get("/api/v1/optimal-params/history")
def get_optimal_params_history(limit: int = 10):
    """최적 파라미터 히스토리 조회 (deprecated: /research 사용)"""
    history = _optimal_params_service.load_history(limit=limit)
    return {"history": history}


@app.get("/api/v1/optimal-params/research")
def get_research_params(limit: int = 20):
    """Research 파라미터 히스토리 조회"""
    research = _optimal_params_service.load_research(limit=limit)
    return {"research": research, "count": len(research)}


@app.post("/api/v1/optimal-params/activate/{entry_id}")
def activate_optimal_params(entry_id: int):
    """특정 파라미터 활성화 (deprecated: /promote-to-live 사용)"""
    success = _optimal_params_service.activate(entry_id)
    if success:
        return {"status": "success", "message": f"파라미터 #{entry_id} Live로 승격"}
    raise HTTPException(status_code=404, detail="파라미터를 찾을 수 없음")


# ============================================================
# 튜닝 변수 관리 API
# ============================================================


@app.get("/api/v1/tuning-variables")
def get_tuning_variables():
    """모든 튜닝 변수 조회"""
    from app.services.backtest_service import ConfigLoader

    all_vars = ConfigLoader.get_all_tuning_variables()
    enabled_vars = ConfigLoader.get_tuning_variables()

    return {
        "all_variables": all_vars,
        "enabled_variables": list(enabled_vars.keys()),
        "enabled_count": len(enabled_vars),
        "total_count": len(all_vars),
    }


class VariableUpdateRequest(BaseModel):
    """변수 업데이트 요청"""

    enabled: bool = None
    range_min: float = None
    range_max: float = None
    default: float = None
    step: float = None


@app.put("/api/v1/tuning-variables/{variable_name}")
def update_tuning_variable(variable_name: str, request: VariableUpdateRequest):
    """튜닝 변수 설정 업데이트"""
    import yaml

    config_path = Path(__file__).parent / "config" / "backtest.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "tuning_variables" not in config:
        raise HTTPException(status_code=404, detail="tuning_variables 섹션 없음")

    if variable_name not in config["tuning_variables"]:
        raise HTTPException(status_code=404, detail=f"변수 '{variable_name}' 없음")

    var_config = config["tuning_variables"][variable_name]

    # 업데이트
    if request.enabled is not None:
        var_config["enabled"] = request.enabled
    if request.range_min is not None and request.range_max is not None:
        var_config["range"] = [request.range_min, request.range_max]
    if request.default is not None:
        var_config["default"] = request.default
    if request.step is not None:
        var_config["step"] = request.step

    # 저장
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # ConfigLoader 캐시 초기화
    from app.services.backtest_service import ConfigLoader

    ConfigLoader._backtest_config = None

    return {
        "message": f"변수 '{variable_name}' 업데이트 완료",
        "variable": var_config,
    }


@app.get("/")
def root():
    """API 정보"""
    return {
        "name": "Backtest & Tuning API",
        "version": "2.3.0",
        "features": {
            "backtest": "실제 백테스트 실행",
            "tuning": "Optuna 기반 파라미터 최적화",
            "optimal_params": "최적 파라미터 영구 저장",
            "live_params": "Live 파라미터 관리 (promote/rollback)",
            "tuning_variables": "튜닝 변수 관리",
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Backtest & Tuning API 시작 (PC 전용)")
    print("=" * 60)
    print("URL: http://localhost:8001")
    print("")
    print("백테스트: POST /api/v1/backtest/run")
    print("튜닝: POST /api/v1/tuning/start")
    print("상태: GET /api/v1/tuning/status")
    print("=" * 60)

    # reload=True: 코드 수정 시 자동 재시작 (개발 모드)
    uvicorn.run("api_backtest:app", host="0.0.0.0", port=8001, reload=True)
