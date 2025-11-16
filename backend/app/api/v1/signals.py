#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/signals.py
신호 & 히스토리 API 엔드포인트
"""
from datetime import datetime, timedelta
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Signal(BaseModel):
    """매매 신호 스키마"""
    date: str
    code: str
    name: str
    signal_type: str  # buy, sell
    price: float
    reason: str


class AlertHistory(BaseModel):
    """알림 히스토리 스키마"""
    timestamp: str
    alert_type: str  # stop_loss, daily_report, weekly_report
    message: str
    level: str  # info, warning, error


@router.get("/", response_model=list[Signal])
async def get_signals(days: int = 7):
    """
    매매 신호 조회
    
    Args:
        days: 조회 기간 (일)
    
    Returns:
        매매 신호 리스트
    """
    # TODO: DB에서 신호 조회
    signals = [
        Signal(
            date="2025-11-16",
            code="069500",
            name="KODEX 200",
            signal_type="buy",
            price=35000,
            reason="MAPS 점수 상위 10위"
        ),
        Signal(
            date="2025-11-15",
            code="102110",
            name="TIGER 200",
            signal_type="sell",
            price=34500,
            reason="손절 기준 도달"
        )
    ]
    
    return signals


@router.get("/history")
async def get_signal_history(skip: int = 0, limit: int = 100):
    """
    신호 히스토리 조회
    
    Args:
        skip: 건너뛸 개수
        limit: 조회 개수
    
    Returns:
        신호 히스토리
    """
    # TODO: DB에서 히스토리 조회
    return {
        "total": 1436,
        "signals": [
            {
                "date": "2025-11-16",
                "buy_count": 5,
                "sell_count": 3
            },
            {
                "date": "2025-11-15",
                "buy_count": 4,
                "sell_count": 2
            }
        ]
    }


@router.get("/alerts", response_model=list[AlertHistory])
async def get_alert_history(days: int = 7):
    """
    알림 히스토리 조회
    
    Args:
        days: 조회 기간 (일)
    
    Returns:
        알림 히스토리
    """
    # TODO: 로그 파일 또는 DB에서 알림 조회
    alerts = [
        AlertHistory(
            timestamp="2025-11-16 15:30:00",
            alert_type="stop_loss",
            message="손절 대상 6개 종목 발견",
            level="warning"
        ),
        AlertHistory(
            timestamp="2025-11-16 10:00:00",
            alert_type="daily_report",
            message="주간 리포트 전송 완료",
            level="info"
        )
    ]
    
    return alerts
