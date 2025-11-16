#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/signals.py
신호 & 히스토리 API 엔드포인트
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def get_signals():
    """매매 신호 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Signals endpoint"}


@router.get("/history")
async def get_signal_history():
    """신호 히스토리 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Signal history endpoint"}


@router.get("/alerts")
async def get_alert_history():
    """알림 히스토리 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Alert history endpoint"}
