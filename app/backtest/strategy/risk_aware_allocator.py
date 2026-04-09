# -*- coding: utf-8 -*-
"""
app/backtest/strategy/risk_aware_allocator.py
P207-STEP7B: Risk-Aware Allocation 엔진

risky sleeve 내부 종목 간 배분 방식을 결정한다.
regime(상위 레이어)은 건드리지 않고, risky sleeve 내부(하위 레이어)만 담당.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def compute_base_weights(
    codes: List[str],
    volatilities: Dict[str, float],
    allocation_mode: str,
    allocation_params: Dict[str, Any],
) -> Dict[str, float]:
    """allocation_mode에 따라 risky sleeve 내부 base weight를 계산한다.

    Args:
        codes: 선택된 종목 코드 리스트
        volatilities: 종목별 realized volatility (annualized)
        allocation_mode: 배분 모드
        allocation_params: 배분 파라미터 (strategy_params에서 추출)

    Returns:
        종목별 base weight (합 = 1.0)

    Raises:
        ValueError: 알 수 없는 allocation_mode
    """
    if not codes:
        return {}

    if allocation_mode == "dynamic_equal_weight":
        return _equal_weight(codes)

    if allocation_mode == "risk_aware_equal_weight_v1":
        return _risk_aware_equal_weight(codes, volatilities, allocation_params)

    if allocation_mode == "inverse_volatility_v1":
        return _inverse_volatility(codes, volatilities, allocation_params)

    raise ValueError(
        f"알 수 없는 allocation_mode: {allocation_mode!r}. "
        f"허용: dynamic_equal_weight, risk_aware_equal_weight_v1, "
        f"inverse_volatility_v1"
    )


def _equal_weight(codes: List[str]) -> Dict[str, float]:
    """동일 비중."""
    w = 1.0 / len(codes)
    return {c: w for c in codes}


def _risk_aware_equal_weight(
    codes: List[str],
    volatilities: Dict[str, float],
    params: Dict[str, Any],
) -> Dict[str, float]:
    """Equal weight + volatility penalty.

    1. equal base weight 생성
    2. vol이 높은 종목은 penalty (weight 감산)
    3. cap/floor 적용
    4. 재정규화 (합 = 1.0)
    """
    vol_floor = params.get("volatility_floor", 0.05)
    vol_cap = params.get("volatility_cap", 0.60)
    weight_floor = params.get("weight_floor", 0.35)
    weight_cap = params.get("weight_cap", 0.65)

    n = len(codes)
    base = 1.0 / n

    # 각 종목의 vol을 floor/cap으로 클램프
    clamped_vols = {}
    for c in codes:
        v = volatilities.get(c)
        if v is None or v != v:  # None or NaN
            v = vol_cap  # vol 없으면 보수적(고위험) 처리
        v = max(vol_floor, min(vol_cap, v))
        clamped_vols[c] = v

    # penalty: vol이 높을수록 weight 감산
    # penalty_factor = 1 - (clamped_vol / vol_cap) * penalty_strength
    # penalty_strength를 0.5로 고정 (base의 절반까지 깎을 수 있음)
    penalty_strength = 0.5
    raw_weights = {}
    for c in codes:
        penalty = (clamped_vols[c] / vol_cap) * penalty_strength
        raw_weights[c] = base * (1.0 - penalty)

    # cap/floor 적용
    for c in codes:
        raw_weights[c] = max(weight_floor / n, min(weight_cap / n * n, raw_weights[c]))

    # 재정규화
    total = sum(raw_weights.values())
    if total <= 0:
        return _equal_weight(codes)

    normalized = {c: w / total for c, w in raw_weights.items()}

    # 최종 cap/floor 재적용 (정규화 후)
    for c in codes:
        normalized[c] = max(weight_floor, min(weight_cap, normalized[c]))

    # 한 번 더 정규화
    total2 = sum(normalized.values())
    if total2 <= 0:
        return _equal_weight(codes)

    return {c: w / total2 for c, w in normalized.items()}


def _inverse_volatility(
    codes: List[str],
    volatilities: Dict[str, float],
    params: Dict[str, Any],
) -> Dict[str, float]:
    """Inverse volatility weighting: w_i = (1/vol_i) / sum(1/vol_j).

    변동성이 낮을수록 높은 비중.
    """
    vol_floor = params.get("volatility_floor", 0.05)
    vol_cap = params.get("volatility_cap", 0.60)
    weight_floor = params.get("weight_floor", 0.35)
    weight_cap = params.get("weight_cap", 0.65)

    inv_vols = {}
    for c in codes:
        v = volatilities.get(c)
        if v is None or v != v:  # None or NaN
            v = vol_cap
        v = max(vol_floor, min(vol_cap, v))
        inv_vols[c] = 1.0 / v

    total_inv = sum(inv_vols.values())
    if total_inv <= 0:
        return _equal_weight(codes)

    weights = {c: iv / total_inv for c, iv in inv_vols.items()}

    # cap/floor
    for c in codes:
        weights[c] = max(weight_floor, min(weight_cap, weights[c]))

    # 재정규화
    total2 = sum(weights.values())
    if total2 <= 0:
        return _equal_weight(codes)

    return {c: w / total2 for c, w in weights.items()}
