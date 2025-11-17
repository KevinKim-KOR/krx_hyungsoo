#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/market.py
시장 분석 API 엔드포인트
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 동기화 파일 경로
SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"

router = APIRouter()


class MarketRegime(BaseModel):
    """시장 레짐 스키마"""
    current_regime: str  # bull, neutral, bear
    ma50: float
    ma200: float
    trend_strength: float
    volatility: str  # low, medium, high
    confidence: float
    criteria: dict


class VolatilityAnalysis(BaseModel):
    """변동성 분석 스키마"""
    atr: float
    atr_period: int
    volatility_level: str  # low, medium, high
    bollinger_width: float


class SectorAnalysis(BaseModel):
    """섹터 분석 스키마"""
    sector: str
    return_pct: float
    trend: str  # strong, weak, neutral


@router.get("/regime", response_model=MarketRegime)
async def get_market_regime():
    """
    시장 레짐 조회
    
    동기화된 파일 우선 사용, 없으면 더미 데이터 반환
    
    Returns:
        - 현재 레짐 (bull/neutral/bear)
        - 레짐 기준 (MA50, MA200, 추세 강도, 변동성)
        - 신뢰도
    """
    # 1. 동기화 파일 확인
    sync_file = SYNC_DIR / "market_regime.json"
    
    if sync_file.exists():
        try:
            with open(sync_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {sync_file}")
            
            return MarketRegime(
                current_regime=data.get("current_regime", "neutral"),
                ma50=data.get("ma50", 0),
                ma200=data.get("ma200", 0),
                trend_strength=data.get("trend_strength", 0),
                volatility=data.get("volatility", "unknown"),
                confidence=data.get("confidence", 0),
                criteria={
                    "ma50_above_ma200": data.get("ma50", 0) > data.get("ma200", 0),
                    "trend_strength_threshold": 80.0,
                    "volatility_threshold": data.get("volatility", "unknown")
                }
            )
        except Exception as e:
            logger.error(f"동기화 파일 읽기 실패: {e}")
    
    # 2. 동기화 파일 없으면 더미 데이터
    logger.info("동기화 파일 없음, 더미 데이터 반환")
    return MarketRegime(
        current_regime="bull",
        ma50=35000.0,
        ma200=33000.0,
        trend_strength=85.0,
        volatility="low",
        confidence=92.0,
        criteria={
            "ma50_above_ma200": True,
            "trend_strength_threshold": 80.0,
            "volatility_threshold": "low"
        }
    )


@router.get("/volatility", response_model=VolatilityAnalysis)
async def get_volatility_analysis():
    """
    변동성 분석
    
    Returns:
        ATR, 변동성 수준, 볼린저 밴드 폭
    """
    # TODO: 실제 시장 데이터에서 변동성 계산
    return VolatilityAnalysis(
        atr=500.0,
        atr_period=14,
        volatility_level="low",
        bollinger_width=1.5
    )


@router.get("/sectors", response_model=list[SectorAnalysis])
async def get_sector_analysis():
    """
    섹터 분석
    
    Returns:
        섹터별 수익률 및 추세
    """
    # TODO: 실제 섹터 데이터 분석
    sectors = [
        SectorAnalysis(
            sector="IT",
            return_pct=15.5,
            trend="strong"
        ),
        SectorAnalysis(
            sector="금융",
            return_pct=8.2,
            trend="neutral"
        ),
        SectorAnalysis(
            sector="제조",
            return_pct=-2.3,
            trend="weak"
        )
    ]
    
    return sectors
