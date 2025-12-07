#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest & Tuning API - PC 전용 (Port 8001)
백테스트, 튜닝 등 무거운 연산 작업용 API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

# FastAPI 앱
app = FastAPI(title="Backtest & Tuning API", description="PC 전용 - 백테스트, 튜닝 API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# 백테스트 API
# ============================================
class BacktestParams(BaseModel):
    start_date: str
    end_date: str
    ma_period: int = 60
    rsi_period: int = 14
    stop_loss: float = -8
    initial_capital: int = 10000000


class BacktestResult(BaseModel):
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    num_trades: int
    win_rate: float


@app.post("/api/v1/backtest/run", response_model=BacktestResult)
def run_backtest(params: BacktestParams):
    """백테스트 실행"""
    import random
    import time
    
    # 시뮬레이션 (실제 백테스트 로직 연결 필요)
    time.sleep(1)  # 실제 백테스트 시간 시뮬레이션
    
    # 파라미터 기반 결과 생성 (데모용)
    base_sharpe = 1.0 + (params.ma_period - 50) * 0.01 + random.uniform(-0.3, 0.3)
    base_cagr = 0.15 + (params.ma_period - 50) * 0.002 + random.uniform(-0.05, 0.05)
    
    return BacktestResult(
        cagr=max(0, base_cagr),
        sharpe_ratio=max(0, base_sharpe),
        max_drawdown=-abs(random.uniform(0.1, 0.25)),
        total_return=base_cagr * 2,
        num_trades=random.randint(50, 200),
        win_rate=random.uniform(0.45, 0.65)
    )


# ============================================
# 튜닝 API (Optuna)
# ============================================

# 튜닝 상태 저장
tuning_state = {
    "is_running": False,
    "current_trial": 0,
    "total_trials": 0,
    "best_sharpe": 0,
    "best_params": None,
    "trials": [],
    "stop_requested": False
}
tuning_lock = threading.Lock()


class TuningStartParams(BaseModel):
    trials: int = 50
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-07"


def run_tuning_background(params: TuningStartParams):
    """백그라운드에서 튜닝 실행"""
    import random
    import time
    
    global tuning_state
    
    with tuning_lock:
        tuning_state["is_running"] = True
        tuning_state["current_trial"] = 0
        tuning_state["total_trials"] = params.trials
        tuning_state["best_sharpe"] = 0
        tuning_state["best_params"] = None
        tuning_state["trials"] = []
        tuning_state["stop_requested"] = False
    
    for i in range(params.trials):
        # 중지 요청 확인
        with tuning_lock:
            if tuning_state["stop_requested"]:
                break
        
        # 랜덤 파라미터 생성
        trial_params = {
            "start_date": params.start_date,
            "end_date": params.end_date,
            "ma_period": random.randint(20, 100),
            "rsi_period": random.randint(7, 21),
            "stop_loss": random.randint(-15, -5),
            "initial_capital": 10000000
        }
        
        # 백테스트 실행 (시뮬레이션)
        time.sleep(0.5)  # 실제 백테스트 시간
        
        # 결과 생성
        sharpe = 0.8 + (trial_params["ma_period"] - 50) * 0.015 + random.uniform(-0.4, 0.4)
        cagr = 0.12 + (trial_params["ma_period"] - 50) * 0.003 + random.uniform(-0.08, 0.08)
        mdd = -abs(random.uniform(0.08, 0.22))
        
        result = {
            "cagr": max(0, cagr),
            "sharpe_ratio": max(0, sharpe),
            "max_drawdown": mdd,
            "total_return": cagr * 2,
            "num_trades": random.randint(50, 200),
            "win_rate": random.uniform(0.45, 0.65)
        }
        
        trial_data = {
            "trial_number": i + 1,
            "params": trial_params,
            "result": result,
            "timestamp": ""
        }
        
        with tuning_lock:
            tuning_state["current_trial"] = i + 1
            tuning_state["trials"].append(trial_data)
            
            # 최적 결과 업데이트
            if sharpe > tuning_state["best_sharpe"]:
                tuning_state["best_sharpe"] = sharpe
                tuning_state["best_params"] = trial_params
            
            # Sharpe 기준 정렬
            tuning_state["trials"].sort(key=lambda x: x["result"]["sharpe_ratio"], reverse=True)
    
    with tuning_lock:
        tuning_state["is_running"] = False


@app.post("/api/v1/tuning/start")
def start_tuning(params: TuningStartParams):
    """튜닝 시작"""
    global tuning_state
    
    with tuning_lock:
        if tuning_state["is_running"]:
            raise HTTPException(status_code=400, detail="튜닝이 이미 실행 중입니다")
    
    # 백그라운드 스레드에서 실행
    thread = threading.Thread(target=run_tuning_background, args=(params,))
    thread.daemon = True
    thread.start()
    
    return {"message": "튜닝 시작됨", "trials": params.trials}


@app.post("/api/v1/tuning/stop")
def stop_tuning():
    """튜닝 중지"""
    global tuning_state
    
    with tuning_lock:
        tuning_state["stop_requested"] = True
    
    return {"message": "튜닝 중지 요청됨"}


@app.get("/api/v1/tuning/status")
def get_tuning_status():
    """튜닝 상태 조회"""
    global tuning_state
    
    with tuning_lock:
        return {
            "is_running": tuning_state["is_running"],
            "current_trial": tuning_state["current_trial"],
            "total_trials": tuning_state["total_trials"],
            "best_sharpe": tuning_state["best_sharpe"],
            "best_params": tuning_state["best_params"],
            "trials": tuning_state["trials"][:10]  # 상위 10개만
        }


@app.get("/")
def root():
    return {
        "message": "Backtest & Tuning API (PC 전용)",
        "port": 8001,
        "endpoints": {
            "backtest": "POST /api/v1/backtest/run",
            "tuning_start": "POST /api/v1/tuning/start",
            "tuning_stop": "POST /api/v1/tuning/stop",
            "tuning_status": "GET /api/v1/tuning/status"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Backtest & Tuning API 시작 (PC 전용)...")
    print("📍 URL: http://localhost:8001")
    print("🧪 Backtest: POST http://localhost:8001/api/v1/backtest/run")
    print("🎯 Tuning: POST http://localhost:8001/api/v1/tuning/start")
    print("📊 Status: GET http://localhost:8001/api/v1/tuning/status\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001)
