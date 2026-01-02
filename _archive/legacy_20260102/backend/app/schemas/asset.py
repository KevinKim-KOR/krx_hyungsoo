#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/schemas/asset.py
자산 관리 Pydantic 스키마
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# Asset 스키마
class AssetBase(BaseModel):
    """자산 기본 스키마"""
    name: str = Field(..., description="종목명")
    code: str = Field(..., description="종목코드")
    quantity: int = Field(..., description="수량", gt=0)
    avg_price: float = Field(..., description="평균 매수가", gt=0)
    purchase_date: datetime = Field(..., description="매수일")
    notes: Optional[str] = Field(None, description="메모")


class AssetCreate(AssetBase):
    """자산 생성 스키마"""
    pass


class AssetUpdate(BaseModel):
    """자산 수정 스키마"""
    name: Optional[str] = None
    quantity: Optional[int] = None
    avg_price: Optional[float] = None
    current_price: Optional[float] = None
    notes: Optional[str] = None


class AssetResponse(AssetBase):
    """자산 응답 스키마"""
    id: int
    current_price: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    
    # 계산 필드
    total_value: Optional[float] = Field(None, description="총 가치")
    return_pct: Optional[float] = Field(None, description="수익률 (%)")
    return_amount: Optional[float] = Field(None, description="수익금")
    
    class Config:
        from_attributes = True


# Trade 스키마
class TradeBase(BaseModel):
    """거래 기본 스키마"""
    asset_code: str = Field(..., description="종목코드")
    asset_name: str = Field(..., description="종목명")
    trade_type: str = Field(..., description="거래 유형 (buy/sell)")
    quantity: int = Field(..., description="수량", gt=0)
    price: float = Field(..., description="거래가", gt=0)
    trade_date: datetime = Field(..., description="거래일")
    notes: Optional[str] = Field(None, description="메모")


class TradeCreate(TradeBase):
    """거래 생성 스키마"""
    pass


class TradeResponse(TradeBase):
    """거래 응답 스키마"""
    id: int
    total_amount: float = Field(..., description="총 금액")
    created_at: datetime
    
    class Config:
        from_attributes = True


# Portfolio 스키마
class PortfolioSnapshot(BaseModel):
    """포트폴리오 스냅샷 스키마"""
    snapshot_date: datetime
    total_assets: float
    cash: float
    stocks_value: float
    total_return_pct: Optional[float] = None
    daily_return_pct: Optional[float] = None
    
    class Config:
        from_attributes = True


# Dashboard 응답 스키마
class DashboardResponse(BaseModel):
    """대시보드 응답 스키마 (프론트엔드 호환)"""
    portfolio_value: float = Field(..., description="총 포트폴리오 가치")
    portfolio_change: float = Field(..., description="포트폴리오 변동률 (소수)")
    sharpe_ratio: float = Field(..., description="Sharpe Ratio")
    volatility: float = Field(..., description="변동성 (소수)")
    expected_return: float = Field(..., description="기대 수익률 (소수)")
    last_updated: str = Field(..., description="마지막 업데이트")
