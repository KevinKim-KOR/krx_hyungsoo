#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Holdings API - 간단한 FastAPI 서버
기존 core.db.Holdings 사용
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from core.db import SessionLocal, Holdings, init_db
from core.data_loader import get_ohlcv

# FastAPI 앱
app = FastAPI(title="Holdings API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic 모델
class HoldingResponse(BaseModel):
    id: int
    code: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    
    class Config:
        from_attributes = True


class RegimeResponse(BaseModel):
    regime: str
    confidence: float
    date: str
    us_market_regime: str | None = None


# API 엔드포인트
@app.get("/api/v1/holdings", response_model=List[HoldingResponse])
def get_holdings():
    """보유 종목 목록 조회"""
    session = SessionLocal()
    try:
        holdings = session.query(Holdings).filter(Holdings.quantity > 0).all()
        
        result = []
        for h in holdings:
            # 현재가 조회
            try:
                df = get_ohlcv(h.code, period='1y')
                current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else h.avg_price
            except:
                current_price = h.avg_price
            
            result.append(HoldingResponse(
                id=h.id,
                code=h.code,
                name=h.name,
                quantity=h.quantity,
                avg_price=h.avg_price,
                current_price=current_price
            ))
        
        return result
    finally:
        session.close()


@app.get("/api/v1/regime/current", response_model=RegimeResponse)
def get_current_regime():
    """현재 시장 레짐 조회"""
    import json
    from datetime import datetime
    
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


@app.get("/")
def root():
    return {
        "message": "Holdings API",
        "endpoints": {
            "holdings": "/api/v1/holdings",
            "regime": "/api/v1/regime/current"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    # DB 초기화
    init_db()
    print("✅ DB 초기화 완료\n")
    
    print("🚀 Holdings API 시작...")
    print("📍 URL: http://localhost:8000")
    print("💰 Holdings: http://localhost:8000/api/v1/holdings")
    print("📊 Regime: http://localhost:8000/api/v1/regime/current\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
