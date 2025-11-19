#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/analysis.py
분석 결과 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# 데이터 경로
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "output"
ANALYSIS_DIR = OUTPUT_DIR / "analysis"

router = APIRouter()


def find_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    """최신 파일 찾기"""
    if not directory.exists():
        return None
    
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    return max(files, key=lambda f: f.stat().st_mtime)


@router.get("/lookback")
async def get_lookback_analysis() -> Dict[str, Any]:
    """
    룩백 분석 결과 조회
    
    Returns:
        - timestamp: 분석 시각
        - method: 분석 방법
        - results: 리밸런싱 결과 리스트
        - summary: 요약 통계
    """
    # 최신 룩백 분석 파일 찾기
    lookback_file = find_latest_file(ANALYSIS_DIR, "lookback_analysis_*.json")
    
    if not lookback_file:
        raise HTTPException(
            status_code=404,
            detail="룩백 분석 결과를 찾을 수 없습니다."
        )
    
    try:
        with open(lookback_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ 룩백 분석 로드: {lookback_file.name}")
        
        # 결과 데이터 구성
        results = []
        for r in data.get("results", []):
            results.append({
                "rebalance_date": r.get("rebalance_date", ""),
                "holding_period_days": r.get("holding_period_days", 0),
                "return": r.get("return", 0.0),
                "volatility": r.get("volatility", 0.0),
                "sharpe_ratio": r.get("sharpe_ratio", 0.0),
                "weights": r.get("weights", {}),
            })
        
        # 요약 통계
        summary_data = data.get("summary", {})
        summary = {
            "total_rebalances": summary_data.get("total_rebalances", 0),
            "avg_return": summary_data.get("avg_return", 0.0),
            "avg_sharpe": summary_data.get("avg_sharpe", 0.0),
            "win_rate": summary_data.get("win_rate", 0.0),
        }
        
        response = {
            "timestamp": data.get("timestamp", ""),
            "method": data.get("method", "portfolio_optimization"),
            "results": results,
            "summary": summary,
        }
        
        return response
        
    except Exception as e:
        logger.error(f"룩백 분석 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"룩백 분석 로드 중 오류 발생: {str(e)}"
        )


@router.get("/regime")
async def get_regime_history() -> Dict[str, Any]:
    """
    시장 레짐 히스토리 조회
    
    Returns:
        레짐 변경 히스토리
    """
    regime_file = OUTPUT_DIR / "regime_history.json"
    
    if not regime_file.exists():
        raise HTTPException(
            status_code=404,
            detail="레짐 히스토리를 찾을 수 없습니다."
        )
    
    try:
        with open(regime_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ 레짐 히스토리 로드")
        return data
        
    except Exception as e:
        logger.error(f"레짐 히스토리 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"레짐 히스토리 로드 중 오류 발생: {str(e)}"
        )
