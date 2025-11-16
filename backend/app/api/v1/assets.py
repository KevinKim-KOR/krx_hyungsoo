#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/assets.py
자산 관리 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.asset import (
    AssetCreate, AssetUpdate, AssetResponse,
    TradeCreate, TradeResponse
)
from app.services.asset_service import AssetService

router = APIRouter()


# 자산 관리
@router.get("/", response_model=list[AssetResponse])
async def get_assets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """자산 목록 조회"""
    service = AssetService(db)
    return await service.get_assets(skip=skip, limit=limit)


@router.post("/", response_model=AssetResponse)
async def create_asset(
    asset: AssetCreate,
    db: Session = Depends(get_db)
):
    """자산 추가"""
    service = AssetService(db)
    return await service.create_asset(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """자산 상세 조회"""
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    asset: AssetUpdate,
    db: Session = Depends(get_db)
):
    """자산 수정"""
    service = AssetService(db)
    updated = await service.update_asset(asset_id, asset)
    if not updated:
        raise HTTPException(status_code=404, detail="Asset not found")
    return updated


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db)
):
    """자산 삭제"""
    service = AssetService(db)
    success = await service.delete_asset(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted successfully"}


# 거래 기록
@router.get("/trades/", response_model=list[TradeResponse])
async def get_trades(
    skip: int = 0,
    limit: int = 100,
    trade_type: str = None,
    db: Session = Depends(get_db)
):
    """거래 기록 조회"""
    service = AssetService(db)
    return await service.get_trades(skip=skip, limit=limit, trade_type=trade_type)


@router.post("/trades/", response_model=TradeResponse)
async def create_trade(
    trade: TradeCreate,
    db: Session = Depends(get_db)
):
    """거래 기록 추가"""
    service = AssetService(db)
    return await service.create_trade(trade)
