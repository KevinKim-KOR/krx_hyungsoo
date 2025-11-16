#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/backtest.py
백테스트 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from app.core.config import settings

router = APIRouter()


@router.get("/results")
async def get_backtest_results():
    """백테스트 결과 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Backtest results endpoint"}


@router.post("/run")
async def run_backtest():
    """
    백테스트 실행 (로컬만)
    
    Raises:
        HTTPException: 클라우드 환경에서 실행 시
    """
    if not settings.IS_LOCAL:
        raise HTTPException(
            status_code=403,
            detail="백테스트는 로컬 환경에서만 실행 가능합니다"
        )
    
    # TODO: Day 2-3에서 구현
    return {"message": "Backtest execution endpoint (local only)"}


@router.get("/history")
async def get_backtest_history():
    """백테스트 히스토리 조회"""
    # TODO: Day 2-3에서 구현
    return {"message": "Backtest history endpoint"}


@router.get("/compare")
async def compare_parameters():
    """최적 조건 vs 현재 조건 비교"""
    # TODO: Day 2-3에서 구현
    return {"message": "Parameter comparison endpoint"}
