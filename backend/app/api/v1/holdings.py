#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/holdings.py
보유 종목 API - core.db.Holdings 사용
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
import sys
from pathlib import Path

# core 모듈 접근을 위한 경로 추가
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.db import SessionLocal, Holdings
from core.data_loader import get_ohlcv

router = APIRouter()


class HoldingResponse(BaseModel):
    id: int
    code: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    
    class Config:
        from_attributes = True


class HoldingCreate(BaseModel):
    code: str
    name: str
    quantity: int
    price: float


class HoldingUpdate(BaseModel):
    quantity: int
    price: float
    action: str  # "buy" 또는 "sell"


@router.get("", response_model=List[HoldingResponse])
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


@router.post("", response_model=HoldingResponse)
def add_holding(data: HoldingCreate):
    """종목 추가 또는 추가 매수"""
    session = SessionLocal()
    try:
        # 기존 종목 확인
        existing = session.query(Holdings).filter(Holdings.code == data.code).first()
        
        if existing:
            # 추가 매수: 평균가 재계산
            total_cost = (existing.avg_price * existing.quantity) + (data.price * data.quantity)
            total_quantity = existing.quantity + data.quantity
            new_avg_price = total_cost / total_quantity
            
            existing.quantity = total_quantity
            existing.avg_price = new_avg_price
            session.commit()
            session.refresh(existing)
            
            # 현재가 조회
            try:
                df = get_ohlcv(existing.code, period='1y')
                current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else existing.avg_price
            except:
                current_price = existing.avg_price
            
            return HoldingResponse(
                id=existing.id,
                code=existing.code,
                name=existing.name,
                quantity=existing.quantity,
                avg_price=existing.avg_price,
                current_price=current_price
            )
        else:
            # 신규 종목 추가
            new_holding = Holdings(
                code=data.code,
                name=data.name,
                quantity=data.quantity,
                avg_price=data.price
            )
            session.add(new_holding)
            session.commit()
            session.refresh(new_holding)
            
            # 현재가 조회
            try:
                df = get_ohlcv(new_holding.code, period='1y')
                current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else new_holding.avg_price
            except:
                current_price = new_holding.avg_price
            
            return HoldingResponse(
                id=new_holding.id,
                code=new_holding.code,
                name=new_holding.name,
                quantity=new_holding.quantity,
                avg_price=new_holding.avg_price,
                current_price=current_price
            )
    finally:
        session.close()


@router.put("/{holding_id}", response_model=HoldingResponse)
def update_holding(holding_id: int, data: HoldingUpdate):
    """종목 수정 (추가 매수 또는 부분 매도)"""
    session = SessionLocal()
    try:
        holding = session.query(Holdings).filter(Holdings.id == holding_id).first()
        if not holding:
            raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
        
        if data.action == "buy":
            # 추가 매수
            total_cost = (holding.avg_price * holding.quantity) + (data.price * data.quantity)
            total_quantity = holding.quantity + data.quantity
            holding.avg_price = total_cost / total_quantity
            holding.quantity = total_quantity
        elif data.action == "sell":
            # 부분 매도
            if data.quantity > holding.quantity:
                raise HTTPException(status_code=400, detail="보유 수량보다 많이 매도할 수 없습니다")
            holding.quantity -= data.quantity
        else:
            raise HTTPException(status_code=400, detail="action은 'buy' 또는 'sell'이어야 합니다")
        
        session.commit()
        session.refresh(holding)
        
        # 현재가 조회
        try:
            df = get_ohlcv(holding.code, period='1y')
            current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else holding.avg_price
        except:
            current_price = holding.avg_price
        
        return HoldingResponse(
            id=holding.id,
            code=holding.code,
            name=holding.name,
            quantity=holding.quantity,
            avg_price=holding.avg_price,
            current_price=current_price
        )
    finally:
        session.close()


@router.delete("/{holding_id}")
def delete_holding(holding_id: int):
    """종목 삭제 (전체 매도)"""
    session = SessionLocal()
    try:
        holding = session.query(Holdings).filter(Holdings.id == holding_id).first()
        if not holding:
            raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
        
        session.delete(holding)
        session.commit()
        
        return {"message": f"{holding.name} 종목이 삭제되었습니다"}
    finally:
        session.close()
