# backend/app/api/v1/ai.py
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class BacktestAnalysisRequest(BaseModel):
    metrics: Dict[str, Any]
    trades: List[Dict[str, Any]]
    user_question: Optional[str] = None

class PortfolioAnalysisRequest(BaseModel):
    holdings: List[Dict[str, Any]]
    market_status: Dict[str, Any]
    user_question: Optional[str] = None

@router.post("/analyze/backtest")
async def analyze_backtest(request: BacktestAnalysisRequest):
    """
    백테스트 결과 분석을 위한 프롬프트 생성
    """
    try:
        # 1. 성과 지표 요약
        metrics_str = "\n".join([f"- {k}: {v}" for k, v in request.metrics.items()])
        
        # 2. 거래 내역 요약 (최근 5개만)
        recent_trades = request.trades[-5:] if request.trades else []
        trades_str = "\n".join([str(t) for t in recent_trades])
        
        # 3. 프롬프트 구성
        system_message = "당신은 전문 퀀트 투자자이자 데이터 분석가입니다. 백테스트 결과를 분석하고 개선점을 제안해주세요."
        
        prompt = f"""
[백테스트 결과 분석 요청]

1. 주요 성과 지표:
{metrics_str}

2. 최근 거래 내역:
{trades_str}

3. 사용자 질문:
{request.user_question or "이 전략의 장단점과 개선 방안을 분석해주세요."}

위 데이터를 바탕으로 다음 내용을 포함하여 답변해주세요:
- 수익률과 리스크(MDD) 평가
- 거래 패턴의 특징
- 구체적인 파라미터 튜닝 제안
"""
        return {
            "system_message": system_message,
            "prompt": prompt.strip()
        }
        
    except Exception as e:
        logger.error(f"백테스트 분석 프롬프트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/portfolio")
async def analyze_portfolio(request: PortfolioAnalysisRequest):
    """
    포트폴리오 분석을 위한 프롬프트 생성
    """
    try:
        # 1. 보유 종목 요약
        holdings_str = "\n".join([f"- {h.get('name', 'Unknown')} ({h.get('code')}): {h.get('weight', 0)*100:.1f}%" for h in request.holdings])
        
        # 2. 시장 상황
        market_str = f"Regime: {request.market_status.get('regime', 'Unknown')}, Trend: {request.market_status.get('trend', 'Unknown')}"
        
        # 3. 프롬프트 구성
        system_message = "당신은 포트폴리오 매니저입니다. 현재 시장 상황과 포트폴리오 구성을 분석하여 리밸런싱 조언을 제공해주세요."
        
        prompt = f"""
[포트폴리오 진단 요청]

1. 현재 시장 상황:
{market_str}

2. 보유 종목 구성:
{holdings_str}

3. 사용자 질문:
{request.user_question or "현재 포트폴리오의 리스크와 리밸런싱 필요성을 진단해주세요."}

위 데이터를 바탕으로 다음 내용을 포함하여 답변해주세요:
- 섹터/자산 배분의 적절성
- 현재 시장 레짐에 따른 대응 전략
- 추천 리밸런싱 방향
"""
        return {
            "system_message": system_message,
            "prompt": prompt.strip()
        }
        
    except Exception as e:
        logger.error(f"포트폴리오 분석 프롬프트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class MLModelAnalysisRequest(BaseModel):
    model_info: Dict[str, Any]
    user_question: Optional[str] = None

class LookbackAnalysisRequest(BaseModel):
    summary: Dict[str, Any]
    results: List[Dict[str, Any]]
    user_question: Optional[str] = None

@router.post("/analyze/ml-model")
async def analyze_ml_model(request: MLModelAnalysisRequest):
    """
    ML 모델 학습 결과 분석을 위한 프롬프트 생성
    """
    try:
        info = request.model_info
        
        # 1. 모델 성능 요약
        performance_str = f"Train R2: {info.get('train_score', 0):.4f}, Test R2: {info.get('test_score', 0):.4f}"
        
        # 2. 주요 특징 (Feature Importance)
        features = info.get('feature_importance', [])[:5]  # Top 5
        features_str = "\n".join([f"- {f.get('feature')}: {f.get('importance', 0):.4f}" for f in features])
        
        # 3. 프롬프트 구성
        system_message = "당신은 머신러닝 엔지니어입니다. 모델의 학습 결과와 특성 중요도를 분석하여 모델 개선 방안을 제시해주세요."
        
        prompt = f"""
[ML 모델 성능 분석 요청]

1. 모델 성능:
{performance_str}

2. 주요 영향 변수 (Feature Importance):
{features_str}

3. 사용자 질문:
{request.user_question or "모델의 과적합 여부와 성능 개선을 위한 피처 엔지니어링 아이디어를 제안해주세요."}

위 데이터를 바탕으로 다음 내용을 포함하여 답변해주세요:
- 과적합/과소적합 여부 진단
- 주요 변수들의 경제적/통계적 의미 해석
- 모델 성능 향상을 위한 구체적인 조언
"""
        return {
            "system_message": system_message,
            "prompt": prompt.strip()
        }
        
    except Exception as e:
        logger.error(f"ML 모델 분석 프롬프트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze/lookback")
async def analyze_lookback(request: LookbackAnalysisRequest):
    """
    룩백 분석 결과 분석을 위한 프롬프트 생성
    """
    try:
        # 1. 요약 통계
        summary_str = "\n".join([f"- {k}: {v}" for k, v in request.summary.items()])
        
        # 2. 리밸런싱 이력 (최근 5회)
        recent_results = request.results[-5:] if request.results else []
        history_str = "\n".join([f"{r.get('rebalance_date')}: Return {r.get('return', 0)*100:.2f}%, Sharpe {r.get('sharpe_ratio', 0):.2f}" for r in recent_results])
        
        # 3. 프롬프트 구성
        system_message = "당신은 퀀트 전략가입니다. 과거 데이터를 기반으로 한 룩백 분석 결과를 평가하고 전략의 유효성을 진단해주세요."
        
        prompt = f"""
[룩백 분석 결과 진단 요청]

1. 전체 요약 통계:
{summary_str}

2. 최근 리밸런싱 성과:
{history_str}

3. 사용자 질문:
{request.user_question or "이 전략의 안정성과 시계열적 성과 변화를 분석해주세요."}

위 데이터를 바탕으로 다음 내용을 포함하여 답변해주세요:
- 전략의 일관성 및 안정성 평가
- 시장 국면 변화에 따른 성과 특성
- 리밸런싱 주기 및 파라미터 최적화 제안
"""
        return {
            "system_message": system_message,
            "prompt": prompt.strip()
        }
        
    except Exception as e:
        logger.error(f"룩백 분석 프롬프트 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
