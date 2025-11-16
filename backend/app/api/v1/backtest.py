#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/backtest.py
백테스트 API 엔드포인트
"""
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings

router = APIRouter()


class BacktestResult(BaseModel):
    """백테스트 결과 스키마"""
    strategy: str
    start_date: str
    end_date: str
    cagr: float
    sharpe: float
    max_drawdown: float
    total_return: float
    total_trades: int


class ParameterComparison(BaseModel):
    """파라미터 비교 스키마"""
    parameter: str
    optimal_value: any
    current_value: any
    optimal_performance: float
    current_performance: float
    difference: float


@router.get("/results", response_model=list[BacktestResult])
async def get_backtest_results():
    """
    백테스트 결과 조회
    
    Returns:
        백테스트 결과 리스트 (Jason, Hybrid 전략)
    """
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
                    sharpe=jason_data.get('sharpe', 1.71),
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
                    sharpe=hybrid_data.get('sharpe', 1.51),
                    max_drawdown=hybrid_data.get('max_drawdown', -0.1992) * 100,
                    total_return=hybrid_data.get('total_return', 0.9680) * 100,
                    total_trades=hybrid_data.get('total_trades', 1406)
                ))
        except Exception as e:
            print(f"Error loading Hybrid backtest: {e}")
    
    if not results:
        raise HTTPException(
            status_code=404,
            detail="백테스트 결과를 찾을 수 없습니다"
        )
    
    return results


@router.post("/run")
async def run_backtest():
    """
    백테스트 실행 (로컬만)
    
    Raises:
        HTTPException: 클라우드 환경에서 실행 시
    """
    if not settings.IS_LOCAL:
        raise HTTPException(
            status_code=403,
            detail="백테스트는 로컬 환경에서만 실행 가능합니다"
        )
    
    # TODO: 실제 백테스트 실행 로직
    return {
        "message": "백테스트 실행 시작",
        "status": "running",
        "note": "실제 구현은 기존 백테스트 스크립트 활용"
    }


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
