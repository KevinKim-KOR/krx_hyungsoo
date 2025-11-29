#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
backend/app/api/v1/portfolio.py
포트폴리오 최적화 API 엔드포인트
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 데이터 경로
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "output"
OPTIMIZATION_DIR = OUTPUT_DIR / "optimization"

router = APIRouter()


@router.post("/optimize")
async def run_portfolio_optimization(
    method: str = "max_sharpe",
    initial_capital: float = 10000000
) -> Dict[str, Any]:
    """
    포트폴리오 최적화 실행
    
    Args:
        method: 최적화 방법 (max_sharpe, min_volatility, efficient_risk)
        initial_capital: 초기 자본금
    
    Returns:
        최적화 결과
    """
    try:
        import subprocess
        import sys
        
        # PC 최적화 스크립트 실행
        script_path = OUTPUT_DIR.parent.parent / "pc" / "optimization" / "run_optimization.py"
        
        if not script_path.exists():
            raise HTTPException(
                status_code=404,
                detail="최적화 스크립트를 찾을 수 없습니다."
            )
        
        # 스크립트 실행
        result = subprocess.run(
            [sys.executable, str(script_path), "--method", method, "--capital", str(initial_capital)],
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"최적화 실행 실패: {result.stderr}"
            )
        
        logger.info(f"✅ 포트폴리오 최적화 완료: {method}")
        
        # 최신 결과 반환
        return await get_portfolio_optimization()
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="최적화 실행 시간 초과 (5분)"
        )
    except Exception as e:
        logger.error(f"최적화 실행 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"최적화 실행 중 오류 발생: {str(e)}"
        )


def find_latest_file(directory: Path, pattern: str = "optimal_portfolio_*.json") -> Optional[Path]:
    """최신 파일 찾기"""
    if not directory.exists():
        return None
    
    files = list(directory.glob(pattern))
    if not files:
        return None
    
    # 파일명에서 타임스탬프 추출하여 정렬
    return max(files, key=lambda f: f.stat().st_mtime)


def load_ticker_names() -> Dict[str, str]:
    """holdings.json에서 종목명 로드"""
    holdings_file = OUTPUT_DIR.parent / "portfolio" / "holdings.json"
    
    if not holdings_file.exists():
        return {}
    
    try:
        with open(holdings_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # code -> name 매핑
        return {h['code']: h['name'] for h in data.get('holdings', [])}
    except Exception as e:
        logger.error(f"종목명 로드 실패: {e}")
        return {}


@router.get("/optimization")
async def get_portfolio_optimization() -> Dict[str, Any]:
    """
    포트폴리오 최적화 결과 조회
    
    Returns:
        - timestamp: 분석 시각
        - method: 최적화 방법
        - expected_return: 기대 수익률
        - volatility: 변동성
        - sharpe_ratio: Sharpe Ratio
        - weights: 종목별 비중 (종목명 포함)
        - discrete_allocation: 이산 배분 (실제 매수 주식 수)
    """
    # 종목명 로드
    ticker_names = load_ticker_names()
    
    # 최신 최적화 결과 파일 찾기
    latest_file = find_latest_file(OPTIMIZATION_DIR)
    
    if not latest_file:
        raise HTTPException(
            status_code=404,
            detail="포트폴리오 최적화 결과를 찾을 수 없습니다."
        )
    
    try:
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"✅ 최적화 결과 로드: {latest_file.name}")
        
        # 리스트 형태인 경우 처리
        if isinstance(data, list):
            # max_sharpe 결과 찾기
            sharpe_data = next((item for item in data if item.get("method") == "max_sharpe"), data[0])
            # discrete_allocation 찾기
            discrete_data = next((item for item in data if item.get("method") == "discrete_allocation"), None)
            
            # weights에 종목명 추가
            weights = sharpe_data.get("weights", {})
            weights_with_names = {}
            for code, weight in weights.items():
                name = ticker_names.get(code, code)  # 종목명 없으면 코드 사용
                weights_with_names[f"{name} ({code})"] = weight
            
            # 응답 데이터 구성
            response = {
                "timestamp": latest_file.stem.replace("optimal_portfolio_", ""),
                "method": sharpe_data.get("method", "max_sharpe"),
                "expected_return": sharpe_data.get("expected_return", 0.0),
                "volatility": sharpe_data.get("volatility", 0.0),
                "sharpe_ratio": sharpe_data.get("sharpe_ratio", 0.0),
                "weights": weights_with_names,
            }
            
            # 이산 배분 정보 추가
            if discrete_data:
                response["discrete_allocation"] = {
                    "allocation": discrete_data.get("allocation", {}),
                    "leftover": discrete_data.get("leftover", 0.0),
                    "total_value": discrete_data.get("total_value", 0.0),
                }
        else:
            # weights에 종목명 추가
            weights = data.get("weights", {})
            weights_with_names = {}
            for code, weight in weights.items():
                name = ticker_names.get(code, code)
                weights_with_names[f"{name} ({code})"] = weight
            
            # 딕셔너리 형태인 경우 (기존 로직)
            response = {
                "timestamp": data.get("timestamp", ""),
                "method": data.get("method", "max_sharpe"),
                "expected_return": data.get("expected_return", 0.0),
                "volatility": data.get("volatility", 0.0),
                "sharpe_ratio": data.get("sharpe_ratio", 0.0),
                "weights": weights_with_names,
            }
            
            # 이산 배분 정보 추가
            if "discrete_allocation" in data:
                response["discrete_allocation"] = {
                    "allocation": data["discrete_allocation"].get("allocation", {}),
                    "leftover": data["discrete_allocation"].get("leftover", 0.0),
                    "total_value": data["discrete_allocation"].get("total_value", 0.0),
                }
        
        return response
        
    except Exception as e:
        logger.error(f"최적화 결과 로드 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"최적화 결과 로드 중 오류 발생: {str(e)}"
        )


@router.get("/history")
async def get_portfolio_history(limit: int = 10) -> list[Dict[str, Any]]:
    """
    포트폴리오 최적화 히스토리 조회
    
    Args:
        limit: 조회할 최대 개수
    
    Returns:
        최적화 결과 리스트 (최신순)
    """
    if not OPTIMIZATION_DIR.exists():
        return []
    
    try:
        # 모든 최적화 파일 찾기
        files = sorted(
            OPTIMIZATION_DIR.glob("optimal_portfolio_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )[:limit]
        
        results = []
        for file in files:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results.append({
                "timestamp": data.get("timestamp", ""),
                "method": data.get("method", ""),
                "sharpe_ratio": data.get("sharpe_ratio", 0.0),
                "expected_return": data.get("expected_return", 0.0),
                "volatility": data.get("volatility", 0.0),
            })
        
        logger.info(f"✅ 최적화 히스토리 {len(results)}개 로드")
        return results
        
    except Exception as e:
        logger.error(f"히스토리 로드 실패: {e}")
        return []
