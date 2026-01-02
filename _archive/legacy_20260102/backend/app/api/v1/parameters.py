#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/parameters.py
백테스트 파라미터 설정 API
"""
import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 파라미터 저장 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
PARAMS_FILE = PROJECT_ROOT / "config" / "backtest_params.json"

router = APIRouter()


class BacktestParameters(BaseModel):
    """백테스트 파라미터 스키마"""
    # 기본 설정
    start_date: str = Field(default="2022-01-01", description="백테스트 시작일")
    end_date: str = Field(default="2025-11-08", description="백테스트 종료일")
    initial_capital: float = Field(default=10000000, description="초기 자본금")
    
    # 전략 파라미터
    ma_period: int = Field(default=60, description="이동평균 기간")
    rsi_period: int = Field(default=14, description="RSI 기간")
    rsi_overbought: int = Field(default=70, description="RSI 과매수 기준")
    rsi_oversold: int = Field(default=30, description="RSI 과매도 기준")
    
    # MAPS 파라미터
    maps_buy_threshold: float = Field(default=0.0, description="MAPS 매수 임계값")
    maps_sell_threshold: float = Field(default=-5.0, description="MAPS 매도 임계값")
    
    # 레짐 감지 파라미터
    short_ma_period: int = Field(default=50, description="단기 이동평균 기간")
    long_ma_period: int = Field(default=200, description="장기 이동평균 기간")
    bull_threshold: float = Field(default=0.02, description="상승장 임계값 (2%)")
    bear_threshold: float = Field(default=-0.02, description="하락장 임계값 (-2%)")
    
    # 포지션 관리
    max_position_size: float = Field(default=0.2, description="최대 포지션 크기 (20%)")
    top_n: int = Field(default=10, description="상위 N개 종목 선택")
    rebalancing: str = Field(default="daily", description="리밸런싱 주기 (daily/weekly/monthly)")
    
    # 리스크 관리
    stop_loss: float = Field(default=-0.05, description="손절 기준 (-5%)")
    take_profit: float = Field(default=0.20, description="익절 기준 (20%)")


class ParameterPreset(BaseModel):
    """파라미터 프리셋"""
    name: str
    description: str
    parameters: BacktestParameters


# 기본 프리셋
DEFAULT_PRESETS = {
    "conservative": ParameterPreset(
        name="보수적",
        description="안정적인 수익을 추구하는 전략",
        parameters=BacktestParameters(
            top_n=15,
            max_position_size=0.15,
            stop_loss=-0.03,
            take_profit=0.15,
            bull_threshold=0.03,
            bear_threshold=-0.03
        )
    ),
    "balanced": ParameterPreset(
        name="균형",
        description="수익과 리스크의 균형을 맞춘 전략",
        parameters=BacktestParameters(
            top_n=10,
            max_position_size=0.2,
            stop_loss=-0.05,
            take_profit=0.20,
            bull_threshold=0.02,
            bear_threshold=-0.02
        )
    ),
    "aggressive": ParameterPreset(
        name="공격적",
        description="높은 수익을 추구하는 전략",
        parameters=BacktestParameters(
            top_n=5,
            max_position_size=0.3,
            stop_loss=-0.07,
            take_profit=0.30,
            bull_threshold=0.01,
            bear_threshold=-0.01
        )
    )
}


def load_parameters() -> BacktestParameters:
    """저장된 파라미터 로드"""
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"파라미터 로드: {PARAMS_FILE}")
            return BacktestParameters(**data)
        except Exception as e:
            logger.error(f"파라미터 로드 실패: {e}")
    
    # 기본값 반환
    logger.info("기본 파라미터 사용")
    return BacktestParameters()


def save_parameters(params: BacktestParameters) -> None:
    """파라미터 저장"""
    PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params.model_dump(), f, ensure_ascii=False, indent=2)
    
    logger.info(f"파라미터 저장: {PARAMS_FILE}")


@router.get("/current", response_model=BacktestParameters)
async def get_current_parameters():
    """
    현재 파라미터 조회
    
    Returns:
        현재 설정된 백테스트 파라미터
    """
    return load_parameters()


@router.post("/update", response_model=BacktestParameters)
async def update_parameters(params: BacktestParameters):
    """
    파라미터 업데이트
    
    Args:
        params: 새로운 파라미터
    
    Returns:
        업데이트된 파라미터
    """
    try:
        save_parameters(params)
        logger.info("파라미터 업데이트 성공")
        return params
    except Exception as e:
        logger.error(f"파라미터 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets", response_model=dict[str, ParameterPreset])
async def get_presets():
    """
    파라미터 프리셋 조회
    
    Returns:
        사용 가능한 프리셋 목록
    """
    return DEFAULT_PRESETS


@router.post("/preset/{preset_name}", response_model=BacktestParameters)
async def apply_preset(preset_name: str):
    """
    프리셋 적용
    
    Args:
        preset_name: 프리셋 이름 (conservative/balanced/aggressive)
    
    Returns:
        적용된 파라미터
    """
    if preset_name not in DEFAULT_PRESETS:
        raise HTTPException(
            status_code=404,
            detail=f"프리셋을 찾을 수 없습니다: {preset_name}"
        )
    
    preset = DEFAULT_PRESETS[preset_name]
    save_parameters(preset.parameters)
    
    logger.info(f"프리셋 적용: {preset.name}")
    return preset.parameters


@router.post("/reset", response_model=BacktestParameters)
async def reset_parameters():
    """
    파라미터 초기화
    
    Returns:
        기본 파라미터
    """
    default_params = BacktestParameters()
    save_parameters(default_params)
    
    logger.info("파라미터 초기화")
    return default_params
