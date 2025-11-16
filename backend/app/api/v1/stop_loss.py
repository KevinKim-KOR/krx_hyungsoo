#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/stop_loss.py
손절 전략 API 엔드포인트
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/strategies")
async def get_stop_loss_strategies():
    """손절 전략 목록 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Stop loss strategies endpoint"}


@router.get("/comparison")
async def compare_strategies():
    """전략 비교 (최적 vs 현재)"""
    # TODO: Day 2-3에서 구현
    return {"message": "Strategy comparison endpoint"}


@router.get("/targets")
async def get_stop_loss_targets():
    """손절 대상 종목 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Stop loss targets endpoint"}
