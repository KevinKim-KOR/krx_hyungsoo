#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/services/asset_service.py
자산 관리 서비스
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.asset import Asset, Trade, Portfolio
from app.schemas.asset import (
    AssetCreate, AssetUpdate, AssetResponse,
    TradeCreate, TradeResponse,
    DashboardResponse
)


class AssetService:
    """자산 관리 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def get_dashboard_summary(self) -> DashboardResponse:
        """대시보드 요약 정보 조회"""
        # 현재 자산 조회
        assets = self.db.query(Asset).all()
        
        # 총 자산 계산
        total_stocks_value = sum(
            asset.quantity * (asset.current_price or asset.avg_price)
            for asset in assets
        )
        
        # 현금 (임시: 포트폴리오 스냅샷에서 가져와야 함)
        cash = 10000000.0  # TODO: 실제 현금 조회
        
        total_assets = cash + total_stocks_value
        
        # 수익률 계산
        total_cost = sum(asset.quantity * asset.avg_price for asset in assets)
        total_return_pct = ((total_stocks_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
        
        # 일/주/월 수익 (임시)
        daily_return = 0.0  # TODO: 실제 계산
        daily_return_pct = 0.0
        weekly_return = 0.0
        weekly_return_pct = 0.0
        monthly_return = 0.0
        monthly_return_pct = 0.0
        
        return DashboardResponse(
            total_assets=total_assets,
            cash=cash,
            stocks_value=total_stocks_value,
            total_return_pct=total_return_pct,
            daily_return=daily_return,
            daily_return_pct=daily_return_pct,
            weekly_return=weekly_return,
            weekly_return_pct=weekly_return_pct,
            monthly_return=monthly_return,
            monthly_return_pct=monthly_return_pct,
            holdings_count=len(assets)
        )
    
    async def get_current_holdings(self) -> list[AssetResponse]:
        """현재 보유 종목 조회"""
        assets = self.db.query(Asset).all()
        
        result = []
        for asset in assets:
            current_price = asset.current_price or asset.avg_price
            total_value = asset.quantity * current_price
            total_cost = asset.quantity * asset.avg_price
            return_pct = ((current_price - asset.avg_price) / asset.avg_price * 100) if asset.avg_price > 0 else 0
            return_amount = total_value - total_cost
            
            asset_response = AssetResponse(
                id=asset.id,
                name=asset.name,
                code=asset.code,
                quantity=asset.quantity,
                avg_price=asset.avg_price,
                current_price=current_price,
                purchase_date=asset.purchase_date,
                notes=asset.notes,
                created_at=asset.created_at,
                updated_at=asset.updated_at,
                total_value=total_value,
                return_pct=return_pct,
                return_amount=return_amount
            )
            result.append(asset_response)
        
        return result
    
    async def get_assets(self, skip: int = 0, limit: int = 100) -> list[Asset]:
        """자산 목록 조회"""
        return self.db.query(Asset).offset(skip).limit(limit).all()
    
    async def get_asset(self, asset_id: int) -> Asset:
        """자산 상세 조회"""
        return self.db.query(Asset).filter(Asset.id == asset_id).first()
    
    async def create_asset(self, asset: AssetCreate) -> Asset:
        """자산 추가"""
        db_asset = Asset(**asset.dict())
        self.db.add(db_asset)
        self.db.commit()
        self.db.refresh(db_asset)
        return db_asset
    
    async def update_asset(self, asset_id: int, asset: AssetUpdate) -> Asset:
        """자산 수정"""
        db_asset = await self.get_asset(asset_id)
        if not db_asset:
            return None
        
        update_data = asset.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_asset, field, value)
        
        self.db.commit()
        self.db.refresh(db_asset)
        return db_asset
    
    async def delete_asset(self, asset_id: int) -> bool:
        """자산 삭제"""
        db_asset = await self.get_asset(asset_id)
        if not db_asset:
            return False
        
        self.db.delete(db_asset)
        self.db.commit()
        return True
    
    async def get_trades(
        self,
        skip: int = 0,
        limit: int = 100,
        trade_type: str = None
    ) -> list[Trade]:
        """거래 기록 조회"""
        query = self.db.query(Trade)
        
        if trade_type:
            query = query.filter(Trade.trade_type == trade_type)
        
        return query.order_by(Trade.trade_date.desc()).offset(skip).limit(limit).all()
    
    async def create_trade(self, trade: TradeCreate) -> Trade:
        """거래 기록 추가"""
        total_amount = trade.quantity * trade.price
        
        db_trade = Trade(
            **trade.dict(),
            total_amount=total_amount
        )
        
        self.db.add(db_trade)
        self.db.commit()
        self.db.refresh(db_trade)
        
        return db_trade
