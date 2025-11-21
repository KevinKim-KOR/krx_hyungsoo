#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/regime.py
시장 레짐 정보 API
"""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()


class RegimeResponse(BaseModel):
    regime: str
    confidence: float
    date: str
    us_market_regime: str | None = None
    ma_short: float | None = None
    ma_long: float | None = None
    current_price: float | None = None


@router.get("/current", response_model=RegimeResponse)
async def get_current_regime():
    """현재 시장 레짐 조회"""
    # 상태 파일 경로
    state_file = Path("data/state/current_regime.json")
    
    if not state_file.exists():
        # 파일이 없으면 기본값 반환
        return RegimeResponse(
            regime="중립장",
            confidence=0.5,
            date=datetime.now().strftime("%Y-%m-%d"),
            us_market_regime="neutral"
        )
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return RegimeResponse(
            regime=data.get("regime", "중립장"),
            confidence=data.get("confidence", 0.5),
            date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
            us_market_regime=data.get("us_market_regime"),
            ma_short=data.get("ma_short"),
            ma_long=data.get("ma_long"),
            current_price=data.get("current_price")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"레짐 정보 조회 실패: {str(e)}")
