#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/lookback_parameters.py
Lookback 분석 파라미터 설정 API
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
PARAMS_FILE = PROJECT_ROOT / "config" / "lookback_params.json"
HISTORY_FILE = PROJECT_ROOT / "data" / "output" / "lookback_history.json"

router = APIRouter()


class LookbackParameters(BaseModel):
    """Lookback 파라미터 스키마"""
    method: str = Field(default="portfolio_optimization", description="분석 방법")
    lookback_days: int = Field(default=120, description="룩백 기간 (일)")
    rebalance_frequency: int = Field(default=30, description="리밸런싱 주기 (일)")
    min_weight: float = Field(default=0.05, description="최소 비중")
    max_weight: float = Field(default=0.30, description="최대 비중")
    risk_free_rate: float = Field(default=0.02, description="무위험 수익률")


class LookbackHistory(BaseModel):
    """Lookback 히스토리 스키마"""
    id: str
    timestamp: str
    parameters: dict
    metrics: dict
    status: str


@router.get("/current")
async def get_lookback_parameters():
    """현재 Lookback 파라미터 조회"""
    if PARAMS_FILE.exists():
        try:
            with open(PARAMS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return LookbackParameters(**data)
        except Exception as e:
            logger.error(f"파라미터 로드 실패: {e}")
    
    return LookbackParameters()


@router.post("/update")
async def update_lookback_parameters(params: LookbackParameters):
    """Lookback 파라미터 업데이트"""
    try:
        PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(params.model_dump(), f, ensure_ascii=False, indent=2)
        return params
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_lookback_history():
    """Lookback 히스토리 조회"""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"히스토리 로드 실패: {e}")
    
    return [
        LookbackHistory(
            id="1",
            timestamp="2025-11-24T10:00:00",
            parameters={"lookback_days": 120, "rebalance_frequency": 30},
            metrics={"total_return": 15.5, "sharpe_ratio": 1.2, "max_drawdown": -8.5},
            status="success"
        ).model_dump()
    ]


@router.post("/history/save")
async def save_lookback_history(history: LookbackHistory):
    """Lookback 히스토리 저장"""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    existing = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except:
            pass
    
    existing.insert(0, history.model_dump())
    existing = existing[:50]
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return {"message": "저장 완료", "id": history.id}
