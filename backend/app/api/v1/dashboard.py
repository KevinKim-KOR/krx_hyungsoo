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
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.database import get_db
from app.schemas.asset import DashboardResponse, AssetResponse
from app.services.asset_service import AssetService

logger = logging.getLogger(__name__)

# 동기화 파일 경로
SYNC_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sync"
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "output"

router = APIRouter()


def find_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    """최신 파일 찾기"""
    if not directory.exists():
        return None
    
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    return max(files, key=lambda f: f.stat().st_mtime)


@router.get("/summary", response_model=DashboardResponse)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    대시보드 요약 정보 조회
    
    동기화된 파일 우선 사용, 없으면 DB 조회
    
    Returns:
        - 포트폴리오 가치
        - 변동률
        - Sharpe Ratio
        - 변동성
        - 기대 수익률
    """
    # 1. 동기화 파일 확인
    snapshot_file = SYNC_DIR / "portfolio_snapshot.json"
    
    if snapshot_file.exists():
        try:
            with open(snapshot_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"✅ 동기화 파일 사용: {snapshot_file}")
            
            # 프론트엔드 스키마에 맞게 변환
            return DashboardResponse(
                portfolio_value=data.get("total_assets", 0),
                portfolio_change=data.get("total_return_pct", 0.0) / 100.0,  # % -> 소수
                sharpe_ratio=0.0,  # TODO: Sharpe Ratio 계산
                volatility=0.0,    # TODO: 변동성 계산
                expected_return=0.0,  # TODO: 기대 수익률 계산
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


@router.get("/recent")
async def get_recent_analyses(limit: int = 5) -> list[Dict[str, Any]]:
    """
    최근 분석 결과 조회
    
    Args:
        limit: 조회할 최대 개수
    
    Returns:
        최근 분석 결과 리스트 (포트폴리오, 백테스트, ML, 룩백)
    """
    analyses = []
    
    # 1. 포트폴리오 최적화
    opt_file = find_latest_file(OUTPUT_DIR / "optimization", "optimal_portfolio_*.json")
    if opt_file:
        try:
            with open(opt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 리스트 형태인 경우 max_sharpe 찾기
            if isinstance(data, list):
                sharpe_data = next((item for item in data if item.get("method") == "max_sharpe"), data[0] if data else {})
            else:
                sharpe_data = data
            
            analyses.append({
                "type": "portfolio",
                "title": "포트폴리오 최적화",
                "timestamp": opt_file.stem.replace("optimal_portfolio_", ""),
                "summary": f"Sharpe {sharpe_data.get('sharpe_ratio', 0):.2f}, 수익률 {sharpe_data.get('expected_return', 0)*100:.1f}%"
            })
        except Exception as e:
            logger.error(f"포트폴리오 최적화 로드 실패: {e}")
    
    # 2. 백테스트
    bt_file = find_latest_file(OUTPUT_DIR / "phase2", "backtest_hybrid_summary.json")
    if bt_file:
        try:
            with open(bt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            analyses.append({
                "type": "backtest",
                "title": "하이브리드 전략 백테스트",
                "timestamp": data.get("timestamp", ""),
                "summary": f"CAGR {data.get('cagr', 0)*100:.1f}%, Sharpe {data.get('sharpe_ratio', 0):.2f}"
            })
        except Exception as e:
            logger.error(f"백테스트 로드 실패: {e}")
    
    # 3. ML 모델
    ml_file = find_latest_file(OUTPUT_DIR / "ml", "meta_*.json")
    if ml_file:
        try:
            with open(ml_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            analyses.append({
                "type": "ml",
                "title": "ML 모델 학습",
                "timestamp": data.get("timestamp", ""),
                "summary": f"Test R² {data.get('test_score', 0):.3f}, {len(data.get('feature_importance', {}))}개 특징"
            })
        except Exception as e:
            logger.error(f"ML 모델 로드 실패: {e}")
    
    # 4. 룩백 분석
    lookback_file = find_latest_file(OUTPUT_DIR / "analysis", "lookback_analysis_*.json")
    if lookback_file:
        try:
            with open(lookback_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            summary = data.get("summary", {})
            analyses.append({
                "type": "lookback",
                "title": "룩백 분석",
                "timestamp": data.get("timestamp", ""),
                "summary": f"{summary.get('total_rebalances', 0)}회 리밸런싱, 평균 Sharpe {summary.get('avg_sharpe', 0):.2f}"
            })
        except Exception as e:
            logger.error(f"룩백 분석 로드 실패: {e}")
    
    # 타임스탬프 기준 정렬 (최신순)
    analyses.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return analyses[:limit]
