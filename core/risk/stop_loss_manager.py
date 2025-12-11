# -*- coding: utf-8 -*-
"""
core/risk/stop_loss_manager.py
손절 합성 로직 공용 함수

기능:
- Live 파라미터의 stop_loss와 하이브리드 손절 매트릭스 합성
- 모든 알림 스크립트에서 공유
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# 하이브리드 손절 매트릭스 (레짐 × 변동성)
# 레짐: bull, neutral, bear
# 변동성: low (<15%), mid (15-25%), high (>25%)
HYBRID_STOP_LOSS_MATRIX = {
    "bull": {"low": -8, "mid": -10, "high": -12},
    "neutral": {"low": -7, "mid": -8, "high": -10},
    "bear": {"low": -5, "mid": -6, "high": -8},
}


def get_volatility_level(volatility: float) -> str:
    """
    변동성 수준 분류

    Args:
        volatility: 연율화 변동성 (0~1)

    Returns:
        str: 'low', 'mid', 'high'
    """
    vol_pct = volatility * 100 if volatility < 1 else volatility

    if vol_pct < 15:
        return "low"
    elif vol_pct < 25:
        return "mid"
    else:
        return "high"


def get_hybrid_stop_loss(regime: str, volatility: float) -> float:
    """
    하이브리드 손절 기준 조회

    Args:
        regime: 시장 레짐 ('bull', 'neutral', 'bear')
        volatility: 연율화 변동성

    Returns:
        float: 손절 기준 (음수, 예: -8)
    """
    regime = regime.lower() if regime else "neutral"
    if regime not in HYBRID_STOP_LOSS_MATRIX:
        regime = "neutral"

    vol_level = get_volatility_level(volatility)
    return HYBRID_STOP_LOSS_MATRIX[regime][vol_level]


def get_stop_loss(
    ticker: str,
    live_params: Dict,
    regime: str = "neutral",
    volatility: float = 0.2,
    hybrid_matrix: Optional[Dict] = None,
) -> float:
    """
    손절 합성 로직 - 전략 손절과 하이브리드 손절 중 더 타이트한 값 사용

    Args:
        ticker: 종목 코드 (로깅용)
        live_params: Live 파라미터 dict (params.stop_loss 포함)
        regime: 시장 레짐 ('bull', 'neutral', 'bear')
        volatility: 종목 연율화 변동성 (기본 0.2 = 20%)
        hybrid_matrix: 커스텀 하이브리드 매트릭스 (None이면 기본값 사용)

    Returns:
        float: 최종 손절 기준 (음수, 예: -8)

    사용 예:
        stop_loss = get_stop_loss(
            ticker="069500",
            live_params={"params": {"stop_loss": -10}},
            regime="bull",
            volatility=0.18
        )
    """
    # 1. Live 파라미터에서 전략 손절 추출
    params = live_params.get("params", {}) if live_params else {}
    strategy_stop_loss = params.get("stop_loss", -10)

    # 2. 하이브리드 손절 계산
    if hybrid_matrix:
        # 커스텀 매트릭스 사용
        regime_key = regime.lower() if regime else "neutral"
        vol_level = get_volatility_level(volatility)
        hybrid_stop_loss = hybrid_matrix.get(regime_key, {}).get(vol_level, -8)
    else:
        hybrid_stop_loss = get_hybrid_stop_loss(regime, volatility)

    # 3. 합성: 더 타이트한(절대값이 작은) 손절 사용
    # 예: 전략 -10%, 하이브리드 -8% → 최종 -8%
    final_stop_loss = max(strategy_stop_loss, hybrid_stop_loss)

    logger.debug(
        f"[{ticker}] 손절 합성: 전략={strategy_stop_loss}%, "
        f"하이브리드={hybrid_stop_loss}% (레짐={regime}, 변동성={volatility:.1%}) "
        f"→ 최종={final_stop_loss}%"
    )

    return final_stop_loss


def check_stop_loss_triggered(
    ticker: str,
    return_pct: float,
    live_params: Dict,
    regime: str = "neutral",
    volatility: float = 0.2,
) -> tuple:
    """
    손절 트리거 여부 확인

    Args:
        ticker: 종목 코드
        return_pct: 현재 수익률 (%, 예: -8.5)
        live_params: Live 파라미터
        regime: 시장 레짐
        volatility: 종목 변동성

    Returns:
        tuple: (트리거 여부, 손절 기준, 초과량)
    """
    stop_loss = get_stop_loss(ticker, live_params, regime, volatility)

    if return_pct <= stop_loss:
        excess = stop_loss - return_pct  # 초과량 (양수)
        return True, stop_loss, excess

    return False, stop_loss, 0


def get_stop_loss_summary(
    holdings: list,
    live_params: Dict,
    regime: str = "neutral",
) -> Dict:
    """
    보유 종목 손절 요약

    Args:
        holdings: 보유 종목 리스트 [{'code': ..., 'return_pct': ..., 'volatility': ...}, ...]
        live_params: Live 파라미터
        regime: 시장 레짐

    Returns:
        Dict: {
            'stop_loss_targets': [...],  # 손절 대상
            'near_stop_loss': [...],     # 손절 근접
            'safe': [...]                # 안전
        }
    """
    result = {"stop_loss_targets": [], "near_stop_loss": [], "safe": []}

    for holding in holdings:
        code = holding.get("code", "")
        name = holding.get("name", code)
        return_pct = holding.get("return_pct", 0)
        volatility = holding.get("volatility", 0.2)

        stop_loss = get_stop_loss(code, live_params, regime, volatility)

        item = {
            "code": code,
            "name": name,
            "return_pct": return_pct,
            "stop_loss": stop_loss,
            "gap": return_pct - stop_loss,  # 손절까지 여유 (양수면 안전)
        }

        if return_pct <= stop_loss:
            result["stop_loss_targets"].append(item)
        elif return_pct <= stop_loss + 2:  # 손절 기준 + 2% 이내
            result["near_stop_loss"].append(item)
        else:
            result["safe"].append(item)

    return result
