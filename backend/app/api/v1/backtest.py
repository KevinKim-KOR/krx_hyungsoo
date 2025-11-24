#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/backtest.py
백테스트 API 엔드포인트
"""
import json
import logging
from pathlib import Path
from typing import Optional, Any, Union
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

# 동기화 파일 경로
SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "output"

router = APIRouter()


def find_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    """최신 파일 찾기"""
    if not directory.exists():
        return None
    
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    return max(files, key=lambda f: f.stat().st_mtime)


class BacktestResult(BaseModel):
    """백테스트 결과 스키마"""
    strategy: str
    start_date: str
    end_date: str
    cagr: float
    sharpe_ratio: float
    max_drawdown: float
    total_return: float
    total_trades: int


class ParameterComparison(BaseModel):
    """파라미터 비교 스키마"""
    parameter: str
    optimal_value: Union[str, int, float]
    current_value: Union[str, int, float]
    optimal_performance: float
    current_performance: float
    difference: float


@router.get("/results", response_model=list[BacktestResult])
async def get_backtest_results():
    """
    백테스트 결과 조회
    
    동기화된 파일 우선 사용, 없으면 로컬 파일 조회
    
    Returns:
        백테스트 결과 리스트 (Jason, Hybrid 전략)
    """
    # 1. 동기화 파일 확인
    sync_file = SYNC_DIR / "backtest_results.json"
    
    if sync_file.exists():
        try:
            with open(sync_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {sync_file}")
            
            results = []
            
            # Jason 전략
            jason = data.get("jason_strategy", {})
            if jason:
                results.append(BacktestResult(
                    strategy="Jason",
                    start_date="2022-01-01",
                    end_date="2025-11-08",
                    cagr=jason.get("cagr", 0),
                    sharpe_ratio=jason.get("sharpe", 0),
                    max_drawdown=jason.get("mdd", 0),
                    total_return=jason.get("total_return", 0),
                    total_trades=1436
                ))
            
            # Hybrid 전략
            hybrid = data.get("hybrid_strategy", {})
            if hybrid:
                results.append(BacktestResult(
                    strategy="Hybrid",
                    start_date="2022-01-01",
                    end_date="2025-11-08",
                    cagr=hybrid.get("cagr", 0),
                    sharpe_ratio=hybrid.get("sharpe", 0),
                    max_drawdown=hybrid.get("mdd", 0),
                    total_return=hybrid.get("total_return", 0),
                    total_trades=1406
                ))
            
            return results
        except Exception as e:
            logger.error(f"동기화 파일 읽기 실패: {e}")
    
    # 2. 동기화 파일 없으면 로컬 파일 조회
    logger.info("동기화 파일 없음, 로컬 파일 조회")
    results = []
    backtest_dir = Path(settings.BACKTEST_DIR)
    
    # Jason 전략 결과
    jason_file = backtest_dir / "jason_backtest_results.json"
    if jason_file.exists():
        try:
            with open(jason_file, 'r', encoding='utf-8') as f:
                jason_data = json.load(f)
                results.append(BacktestResult(
                    strategy="Jason",
                    start_date=jason_data.get('start_date', '2022-01-01'),
                    end_date=jason_data.get('end_date', '2025-11-08'),
                    cagr=jason_data.get('cagr', 0.3902) * 100,
                    sharpe_ratio=jason_data.get('sharpe', 1.71),
                    max_drawdown=jason_data.get('max_drawdown', -0.2351) * 100,
                    total_return=jason_data.get('total_return', 1.5388) * 100,
                    total_trades=jason_data.get('total_trades', 1436)
                ))
        except Exception as e:
            print(f"Error loading Jason backtest: {e}")
    
    # Hybrid 전략 결과
    hybrid_file = backtest_dir / "hybrid_backtest_results.json"
    if hybrid_file.exists():
        try:
            with open(hybrid_file, 'r', encoding='utf-8') as f:
                hybrid_data = json.load(f)
                results.append(BacktestResult(
                    strategy="Hybrid",
                    start_date=hybrid_data.get('start_date', '2022-01-01'),
                    end_date=hybrid_data.get('end_date', '2025-11-08'),
                    cagr=hybrid_data.get('cagr', 0.2705) * 100,
                    sharpe_ratio=hybrid_data.get('sharpe', 1.51),
                    max_drawdown=hybrid_data.get('max_drawdown', -0.1992) * 100,
                    total_return=hybrid_data.get('total_return', 0.9680) * 100,
                    total_trades=hybrid_data.get('total_trades', 1406)
                ))
        except Exception as e:
            print(f"Error loading Hybrid backtest: {e}")
    
    # 3. 파일이 없으면 더미 데이터 반환
    if not results:
        logger.info("백테스트 파일 없음, 더미 데이터 반환")
        results = [
            BacktestResult(
                strategy="하이브리드 레짐 전략",
                start_date="2022-01-01",
                end_date="2025-11-08",
                cagr=27.05,
                sharpe_ratio=1.51,
                max_drawdown=-19.92,
                total_return=96.80,
                total_trades=1406
            )
        ]
    
    return results


@router.post("/run")
async def run_backtest():
    """
    백테스트 실행
    
    파라미터는 config/backtest_params.json에서 로드
    
    Returns:
        백테스트 실행 상태
    
    Raises:
        HTTPException: 클라우드 환경에서 실행 시
    """
    if not settings.IS_LOCAL:
        raise HTTPException(
            status_code=403,
            detail="백테스트는 로컬 환경에서만 실행 가능합니다"
        )
    
    import subprocess
    import sys
    
    # 백테스트 스크립트 경로
    script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "dev" / "phase2" / "run_backtest_hybrid.py"
    
    if not script_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"백테스트 스크립트를 찾을 수 없습니다: {script_path}"
        )
    
    try:
        # 백그라운드에서 백테스트 실행
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"백테스트 실행 시작 (PID: {process.pid})")
        
        return {
            "message": "백테스트 실행 시작",
            "status": "running",
            "pid": process.pid,
            "script": str(script_path)
        }
    except Exception as e:
        logger.error(f"백테스트 실행 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_backtest_history():
    """
    백테스트 히스토리 조회
    
    Returns:
        과거 백테스트 실행 기록
    """
    # TODO: DB에서 백테스트 히스토리 조회
    return {
        "message": "백테스트 히스토리",
        "history": [
            {
                "date": "2025-11-08",
                "strategy": "Hybrid",
                "cagr": 27.05,
                "sharpe": 1.51
            },
            {
                "date": "2025-11-07",
                "strategy": "Jason",
                "cagr": 39.02,
                "sharpe": 1.71
            }
        ]
    }


@router.get("/compare", response_model=list[ParameterComparison])
async def compare_parameters():
    """
    최적 조건 vs 현재 조건 비교
    
    Returns:
        파라미터별 비교 결과
    """
    comparisons = [
        ParameterComparison(
            parameter="Top N",
            optimal_value=10,
            current_value=15,
            optimal_performance=39.02,
            current_performance=27.05,
            difference=-11.97
        ),
        ParameterComparison(
            parameter="Rebalancing",
            optimal_value="daily",
            current_value="daily",
            optimal_performance=39.02,
            current_performance=27.05,
            difference=0.0
        ),
        ParameterComparison(
            parameter="MA Period",
            optimal_value="50/200",
            current_value="50/200",
            optimal_performance=27.05,
            current_performance=27.05,
            difference=0.0
        )
    ]
    
    return comparisons
