#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/dashboard.py
대시보드 API 엔드포인트
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pathlib import Path
import json
import logging

from app.core.database import get_db
from app.schemas.asset import DashboardResponse, AssetResponse
from app.services.asset_service import AssetService

logger = logging.getLogger(__name__)

# 동기화 파일 경로
SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"

router = APIRouter()


@router.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    대시보드 요약 정보 조회
    
    동기화된 파일 우선 사용, 없으면 DB 조회
    
    Returns:
        - 총 자산
        - 현금
        - 주식 가치
        - 수익률 (일/주/월)
        - 보유 종목 수
    """
    # 1. 동기화 파일 확인
    snapshot_file = SYNC_DIR / "portfolio_snapshot.json"
    
    if snapshot_file.exists():
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {snapshot_file}")
            
            return DashboardResponse(
                total_assets=data.get("total_assets", 0),
                cash=data.get("cash", 0),
                stocks_value=data.get("stocks_value", 0),
                total_return_pct=data.get("total_return_pct", 0.0),
                daily_return_pct=data.get("daily_return_pct", 0.0),
                weekly_return_pct=0.0,  # TODO: 주간 수익률
                monthly_return_pct=0.0,  # TODO: 월간 수익률
                holdings_count=data.get("holdings_count", 0),
                last_updated=data.get("timestamp", "")
            )
        except Exception as e:
            logger.error(f"동기화 파일 읽기 실패: {e}")
    
    # 2. 동기화 파일 없으면 DB 조회
    logger.info("동기화 파일 없음, DB 조회")
    service = AssetService(db)
    return await service.get_dashboard_summary()


@router.get("/holdings", response_model=list[AssetResponse])
async def get_current_holdings(db: Session = Depends(get_db)):
    """
    현재 보유 종목 조회
    
    동기화된 파일 우선 사용, 없으면 DB 조회
    
    Returns:
        보유 종목 리스트 (수익률 포함)
    """
    # 1. 동기화 파일 확인
    snapshot_file = SYNC_DIR / "portfolio_snapshot.json"
    
    if snapshot_file.exists():
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {snapshot_file}")
            
            holdings = []
            for h in data.get("holdings", []):
                holdings.append(AssetResponse(
                    code=h.get("code", ""),
                    name=h.get("name", ""),
                    quantity=h.get("quantity", 0),
                    avg_price=h.get("avg_price", 0),
                    current_price=h.get("current_price", 0),
                    return_pct=h.get("return_pct", 0.0)
                ))
            
            return holdings
        except Exception as e:
            logger.error(f"동기화 파일 읽기 실패: {e}")
    
    # 2. 동기화 파일 없으면 DB 조회
    logger.info("동기화 파일 없음, DB 조회")
    service = AssetService(db)
    return await service.get_current_holdings()
