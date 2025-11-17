#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/stop_loss.py
손절 전략 API 엔드포인트
"""
import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.config import settings

logger = logging.getLogger(__name__)

# 동기화 파일 경로
SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"

router = APIRouter()


class StopLossStrategy(BaseModel):
    """손절 전략 스키마"""
    name: str
    description: str
    threshold_range: str
    stop_loss_count: int
    safe_count: int
    current_return_pct: float
    after_stop_loss_return_pct: float
    improvement: float


class StrategyComparison(BaseModel):
    """전략 비교 스키마"""
    strategy_name: str
    is_optimal: bool
    is_current: bool
    performance: float
    stop_loss_count: int
    improvement: float


class StopLossTarget(BaseModel):
    """손절 대상 스키마"""
    name: str
    code: str
    return_pct: float
    threshold: float
    current_value: float
    loss_amount: float


@router.get("/strategies", response_model=list[StopLossStrategy])
async def get_stop_loss_strategies():
    """
    손절 전략 목록 조회
    
    Returns:
        4가지 손절 전략 정보
    """
    comparison_file = Path(settings.BACKTEST_DIR) / "stop_loss_strategy_comparison.json"
    
    if not comparison_file.exists():
        raise HTTPException(
            status_code=404,
            detail="손절 전략 비교 결과를 찾을 수 없습니다"
        )
    
    try:
        with open(comparison_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        strategies = []
        for key, strategy_data in data.get('strategies', {}).items():
            strategy_info = strategy_data.get('strategy_info', {})
            strategies.append(StopLossStrategy(
                name=strategy_info.get('name', key),
                description=strategy_info.get('description', ''),
                threshold_range=strategy_info.get('threshold_range', ''),
                stop_loss_count=strategy_data.get('stop_loss_count', 0),
                safe_count=strategy_data.get('safe_count', 0),
                current_return_pct=strategy_data.get('total_return_pct', 0),
                after_stop_loss_return_pct=strategy_data.get('after_stop_loss_return_pct', 0),
                improvement=strategy_data.get('improvement', 0)
            ))
        
        return strategies
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"손절 전략 데이터 로드 실패: {str(e)}"
        )


@router.get("/comparison", response_model=list[StrategyComparison])
async def compare_strategies():
    """
    전략 비교 (최적 vs 현재)
    
    Returns:
        전략별 성과 비교 (최적 전략 표시)
    """
    comparison_file = Path(settings.BACKTEST_DIR) / "stop_loss_strategy_comparison.json"
    
    if not comparison_file.exists():
        raise HTTPException(
            status_code=404,
            detail="손절 전략 비교 결과를 찾을 수 없습니다"
        )
    
    try:
        with open(comparison_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        best_strategy_name = data.get('best_strategy', {}).get('name', 'hybrid')
        current_strategy = "fixed"  # TODO: 실제 현재 전략 조회
        
        comparisons = []
        for key, strategy_data in data.get('strategies', {}).items():
            strategy_info = strategy_data.get('strategy_info', {})
            comparisons.append(StrategyComparison(
                strategy_name=strategy_info.get('name', key),
                is_optimal=(key == best_strategy_name),
                is_current=(key == current_strategy),
                performance=strategy_data.get('after_stop_loss_return_pct', 0),
                stop_loss_count=strategy_data.get('stop_loss_count', 0),
                improvement=strategy_data.get('improvement', 0)
            ))
        
        # 성과순 정렬
        comparisons.sort(key=lambda x: x.performance, reverse=True)
        
        return comparisons
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"전략 비교 데이터 로드 실패: {str(e)}"
        )


@router.get("/targets", response_model=list[StopLossTarget])
async def get_stop_loss_targets(strategy: str = "hybrid"):
    """
    손절 대상 종목 조회
    
    동기화된 파일 우선 사용, 없으면 로컬 파일 조회
    
    Args:
        strategy: 손절 전략 (fixed, regime, dynamic, hybrid)
    
    Returns:
        손절 대상 종목 리스트
    """
    # 1. 동기화 파일 확인
    sync_file = SYNC_DIR / "stop_loss_targets.json"
    
    if sync_file.exists():
        try:
            with open(sync_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {sync_file}")
            
            targets = []
            for target in data.get('targets', []):
                targets.append(StopLossTarget(
                    name=target.get('name', ''),
                    code=target.get('code', ''),
                    return_pct=target.get('return_pct', 0),
                    threshold=target.get('threshold', 0),
                    current_value=target.get('current_value', 0),
                    loss_amount=target.get('loss_amount', 0)
                ))
            
            return targets
        except Exception as e:
            logger.error(f"동기화 파일 읽기 실패: {e}")
    
    # 2. 동기화 파일 없으면 로컬 파일 조회
    logger.info("동기화 파일 없음, 로컬 파일 조회")
    comparison_file = Path(settings.BACKTEST_DIR) / "stop_loss_strategy_comparison.json"
    
    if not comparison_file.exists():
        raise HTTPException(
            status_code=404,
            detail="손절 전략 비교 결과를 찾을 수 없습니다"
        )
    
    try:
        with open(comparison_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        strategy_data = data.get('strategies', {}).get(strategy, {})
        targets_data = strategy_data.get('stop_loss_targets', [])
        
        targets = []
        for target in targets_data:
            targets.append(StopLossTarget(
                name=target.get('name', ''),
                code=target.get('code', ''),
                return_pct=target.get('return_pct', 0),
                threshold=target.get('threshold', 0),
                current_value=target.get('current_value', 0),
                loss_amount=target.get('loss_amount', 0)
            ))
        
        return targets
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"손절 대상 데이터 로드 실패: {str(e)}"
        )
