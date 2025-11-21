#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/holdings.py
보유 종목 관리 API
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from core.db import Holdings
from core.data_loader import get_ohlcv

router = APIRouter()


# Pydantic 모델
class HoldingCreate(BaseModel):
    code: str
    name: str
    quantity: int
    avg_price: float


class HoldingUpdate(BaseModel):
    quantity: int | None = None
    avg_price: float | None = None


class HoldingResponse(BaseModel):
    id: int
    code: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[HoldingResponse])
async def get_holdings(db: Session = Depends(get_db)):
    """보유 종목 목록 조회"""
    holdings = db.query(Holdings).filter(Holdings.quantity > 0).all()
    
    # 현재가 조회
    result = []
    for holding in holdings:
        try:
            # 최근 1년 데이터 조회
            df = get_ohlcv(holding.code, period='1y')
            if df is not None and len(df) > 0:
                current_price = float(df['close'].iloc[-1])
            else:
                current_price = holding.avg_price  # 데이터 없으면 평균가 사용
        except Exception as e:
            print(f"현재가 조회 실패 ({holding.code}): {e}")
            current_price = holding.avg_price
        
        result.append(HoldingResponse(
            id=holding.id,
            code=holding.code,
            name=holding.name,
            quantity=holding.quantity,
            avg_price=holding.avg_price,
            current_price=current_price,
            created_at=holding.created_at,
            updated_at=holding.updated_at
        ))
    
    return result


@router.post("", response_model=HoldingResponse)
async def create_holding(holding: HoldingCreate, db: Session = Depends(get_db)):
    """보유 종목 추가"""
    # 기존 종목 확인
    existing = db.query(Holdings).filter(Holdings.code == holding.code).first()
    
    if existing:
        # 기존 종목이 있으면 수량과 평균가 업데이트
        total_quantity = existing.quantity + holding.quantity
        total_cost = (existing.avg_price * existing.quantity) + (holding.avg_price * holding.quantity)
        new_avg_price = total_cost / total_quantity
        
        existing.quantity = total_quantity
        existing.avg_price = new_avg_price
        db.commit()
        db.refresh(existing)
        
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
            current_price=current_price,
            created_at=existing.created_at,
            updated_at=existing.updated_at
        )
    
    # 새 종목 추가
    db_holding = Holdings(
        code=holding.code,
        name=holding.name,
        quantity=holding.quantity,
        avg_price=holding.avg_price
    )
    db.add(db_holding)
    db.commit()
    db.refresh(db_holding)
    
    # 현재가 조회
    try:
        df = get_ohlcv(db_holding.code, period='1y')
        current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else db_holding.avg_price
    except:
        current_price = db_holding.avg_price
    
    return HoldingResponse(
        id=db_holding.id,
        code=db_holding.code,
        name=db_holding.name,
        quantity=db_holding.quantity,
        avg_price=db_holding.avg_price,
        current_price=current_price,
        created_at=db_holding.created_at,
        updated_at=db_holding.updated_at
    )


@router.put("/{holding_id}", response_model=HoldingResponse)
async def update_holding(holding_id: int, holding: HoldingUpdate, db: Session = Depends(get_db)):
    """보유 종목 수정"""
    db_holding = db.query(Holdings).filter(Holdings.id == holding_id).first()
    if not db_holding:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
    
    if holding.quantity is not None:
        db_holding.quantity = holding.quantity
    if holding.avg_price is not None:
        db_holding.avg_price = holding.avg_price
    
    db.commit()
    db.refresh(db_holding)
    
    # 현재가 조회
    try:
        df = get_ohlcv(db_holding.code, period='1y')
        current_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else db_holding.avg_price
    except:
        current_price = db_holding.avg_price
    
    return HoldingResponse(
        id=db_holding.id,
        code=db_holding.code,
        name=db_holding.name,
        quantity=db_holding.quantity,
        avg_price=db_holding.avg_price,
        current_price=current_price,
        created_at=db_holding.created_at,
        updated_at=db_holding.updated_at
    )


@router.delete("/{holding_id}")
async def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """보유 종목 삭제"""
    db_holding = db.query(Holdings).filter(Holdings.id == holding_id).first()
    if not db_holding:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
    
    db.delete(db_holding)
    db.commit()
    
    return {"message": "삭제되었습니다"}
