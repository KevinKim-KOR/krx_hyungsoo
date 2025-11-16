#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/dashboard.py
대시보드 API 엔드포인트
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.asset import DashboardResponse, AssetResponse
from app.services.asset_service import AssetService

router = APIRouter()


@router.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    대시보드 요약 정보 조회
    
    Returns:
        - 총 자산
        - 현금
        - 주식 가치
        - 수익률 (일/주/월)
        - 보유 종목 수
    """
    service = AssetService(db)
    return await service.get_dashboard_summary()


@router.get("/holdings", response_model=list[AssetResponse])
async def get_current_holdings(db: Session = Depends(get_db)):
    """
    현재 보유 종목 조회
    
    Returns:
        보유 종목 리스트 (수익률 포함)
    """
    service = AssetService(db)
    return await service.get_current_holdings()
