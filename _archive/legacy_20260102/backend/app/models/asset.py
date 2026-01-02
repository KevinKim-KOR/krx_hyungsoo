#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/models/asset.py
자산 관리 DB 모델
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base


class Asset(Base):
    """자산 테이블"""
    __tablename__ = "assets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="종목명")
    code = Column(String(20), nullable=False, index=True, comment="종목코드")
    quantity = Column(Integer, nullable=False, comment="수량")
    avg_price = Column(Float, nullable=False, comment="평균 매수가")
    current_price = Column(Float, nullable=True, comment="현재가")
    purchase_date = Column(DateTime, nullable=False, comment="매수일")
    created_at = Column(DateTime, server_default=func.now(), comment="생성일시")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="수정일시")
    notes = Column(Text, nullable=True, comment="메모")
    
    def __repr__(self):
        return f"<Asset(name={self.name}, code={self.code}, quantity={self.quantity})>"


class Trade(Base):
    """거래 기록 테이블"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_code = Column(String(20), nullable=False, index=True, comment="종목코드")
    asset_name = Column(String(100), nullable=False, comment="종목명")
    trade_type = Column(String(10), nullable=False, comment="거래 유형 (buy/sell)")
    quantity = Column(Integer, nullable=False, comment="수량")
    price = Column(Float, nullable=False, comment="거래가")
    total_amount = Column(Float, nullable=False, comment="총 금액")
    trade_date = Column(DateTime, nullable=False, comment="거래일")
    created_at = Column(DateTime, server_default=func.now(), comment="생성일시")
    notes = Column(Text, nullable=True, comment="메모")
    
    def __repr__(self):
        return f"<Trade(name={self.asset_name}, type={self.trade_type}, quantity={self.quantity})>"


class Portfolio(Base):
    """포트폴리오 스냅샷 테이블"""
    __tablename__ = "portfolio_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(DateTime, nullable=False, index=True, comment="스냅샷 날짜")
    total_assets = Column(Float, nullable=False, comment="총 자산")
    cash = Column(Float, nullable=False, comment="현금")
    stocks_value = Column(Float, nullable=False, comment="주식 가치")
    total_return_pct = Column(Float, nullable=True, comment="총 수익률 (%)")
    daily_return_pct = Column(Float, nullable=True, comment="일일 수익률 (%)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성일시")
    
    def __repr__(self):
        return f"<Portfolio(date={self.snapshot_date}, total={self.total_assets})>"
