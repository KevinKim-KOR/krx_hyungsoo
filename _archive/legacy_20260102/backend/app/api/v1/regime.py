#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/regime.py
시장 레짐 API
"""
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import json

router = APIRouter()


class RegimeResponse(BaseModel):
    regime: str
    confidence: float
    date: str
    us_market_regime: str | None = None


@router.get("/current", response_model=RegimeResponse)
def get_current_regime():
    """현재 시장 레짐 조회"""
    state_file = Path("data/state/current_regime.json")
    
    if not state_file.exists():
        return RegimeResponse(
            regime="중립장",
            confidence=0.5,
            date=datetime.now().strftime("%Y-%m-%d"),
            us_market_regime="neutral"
        )
    
    with open(state_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return RegimeResponse(
        regime=data.get("regime", "중립장"),
        confidence=data.get("confidence", 0.5),
        date=data.get("date", datetime.now().strftime("%Y-%m-%d")),
        us_market_regime=data.get("us_market_regime")
    )
