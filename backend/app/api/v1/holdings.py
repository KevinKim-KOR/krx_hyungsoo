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
import requests
from bs4 import BeautifulSoup

router = APIRouter()


def get_current_price(code: str, avg_price: float) -> float:
    """현재가 조회 (네이버 금융 사용)"""
    try:
        # 네이버 금융 URL
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=3)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 현재가 추출
        price_element = soup.select_one('.no_today .blind')
        if price_element:
            price_text = price_element.text.strip().replace(',', '')
            return float(price_text)
        
        # 대체 방법: p11 클래스
        price_element = soup.select_one('.p11 .blind')
        if price_element:
            price_text = price_element.text.strip().replace(',', '')
            return float(price_text)
            
    except Exception as e:
        print(f"현재가 조회 실패 ({code}): {e}")
    
    # 실패 시 평균가 반환
    return avg_price


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
            current_price = get_current_price(h.code, h.avg_price)
            
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
            current_price = get_current_price(existing.code, existing.avg_price)
            
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
            current_price = get_current_price(new_holding.code, new_holding.avg_price)
            
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
        current_price = get_current_price(holding.code, holding.avg_price)
        
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
