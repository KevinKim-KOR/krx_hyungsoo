# -*- coding: utf-8 -*-
"""
app/backtest/strategy/risk_aware_allocator.py
P207-STEP7B/7C: Risk-Aware Allocation 엔진

risky sleeve 내부 종목 간 배분 방식을 결정한다.
regime(상위 레이어)은 건드리지 않고, risky sleeve 내부(하위 레이어)만 담당.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ALLOWED_MODES = {
    "dynamic_equal_weight",
    "risk_aware_equal_weight_v1",
    "inverse_volatility_v1",
}


@dataclass
class AllocationResult:
    """allocation 계산 결과. 중간 과정을 모두 보존."""

    mode: str
    codes: List[str]
    raw_vols: Dict[str, float]
    clamped_vols: Dict[str, float]
    pre_cap_weights: Dict[str, float]
    post_cap_weights: Dict[str, float]
    final_weights: Dict[str, float]
    fallback_used: bool = False
    fallback_reason: str = ""
    params_used: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "codes": self.codes,
            "raw_vols": self.raw_vols,
            "clamped_vols": self.clamped_vols,
            "pre_cap_weights": self.pre_cap_weights,
            "post_cap_weights": self.post_cap_weights,
            "final_weights": self.final_weights,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "params_used": self.params_used,
        }


def compute_base_weights(
    codes: List[str],
    volatilities: Dict[str, float],
    allocation_mode: str,
    allocation_params: Dict[str, Any],
) -> AllocationResult:
    """allocation_mode에 따라 risky sleeve 내부 base weight 계산.

    Raises:
        ValueError: 알 수 없는 allocation_mode
    """
    if not codes:
        return AllocationResult(
            mode=allocation_mode,
            codes=[],
            raw_vols={},
            clamped_vols={},
            pre_cap_weights={},
            post_cap_weights={},
            final_weights={},
            params_used=allocation_params,
        )

    if allocation_mode == "dynamic_equal_weight":
        return _equal_weight(codes, allocation_params)

    if allocation_mode == "risk_aware_equal_weight_v1":
        return _risk_aware_equal_weight(codes, volatilities, allocation_params)

    if allocation_mode == "inverse_volatility_v1":
        return _inverse_volatility(codes, volatilities, allocation_params)

    raise ValueError(
        f"알 수 없는 allocation_mode: {allocation_mode!r}. " f"허용: {ALLOWED_MODES}"
    )


def _equal_weight(
    codes: List[str],
    params: Dict[str, Any],
) -> AllocationResult:
    """동일 비중."""
    w = 1.0 / len(codes)
    weights = {c: w for c in codes}
    return AllocationResult(
        mode="dynamic_equal_weight",
        codes=list(codes),
        raw_vols={},
        clamped_vols={},
        pre_cap_weights=dict(weights),
        post_cap_weights=dict(weights),
        final_weights=dict(weights),
        params_used=params,
    )


def _clamp_vols(
    codes: List[str],
    volatilities: Dict[str, float],
    vol_floor: float,
    vol_cap: float,
) -> tuple:
    """vol clamp 공통 로직. (raw_vols, clamped_vols) 반환."""
    raw_vols = {}
    clamped = {}
    for c in codes:
        v = volatilities.get(c)
        if v is None or v != v:  # None or NaN
            v_raw = None
            v = vol_cap
        else:
            v_raw = v
        raw_vols[c] = v_raw
        clamped[c] = max(vol_floor, min(vol_cap, v))
    return raw_vols, clamped


def _normalize(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {c: w / total for c, w in weights.items()}


def _apply_cap_floor(
    weights: Dict[str, float],
    weight_floor: float,
    weight_cap: float,
) -> Dict[str, float]:
    """cap/floor 적용 후 재정규화."""
    capped = {c: max(weight_floor, min(weight_cap, w)) for c, w in weights.items()}
    return _normalize(capped)


def _risk_aware_equal_weight(
    codes: List[str],
    volatilities: Dict[str, float],
    params: Dict[str, Any],
) -> AllocationResult:
    """Equal weight + volatility penalty."""
    vol_floor = params.get("volatility_floor", 0.05)
    vol_cap = params.get("volatility_cap", 0.60)
    weight_floor = params.get("weight_floor", 0.35)
    weight_cap = params.get("weight_cap", 0.65)

    raw_vols, clamped = _clamp_vols(codes, volatilities, vol_floor, vol_cap)
    n = len(codes)
    base = 1.0 / n

    # penalty: vol 높을수록 감산
    penalty_strength = 0.5
    pre_cap = {}
    for c in codes:
        penalty = (clamped[c] / vol_cap) * penalty_strength
        pre_cap[c] = base * (1.0 - penalty)

    pre_cap_n = _normalize(pre_cap)
    if not pre_cap_n:
        # fallback to equal weight
        eq = _equal_weight(codes, params)
        eq.fallback_used = True
        eq.fallback_reason = "pre_cap weights sum <= 0"
        return eq

    post_cap = _apply_cap_floor(pre_cap_n, weight_floor, weight_cap)
    if not post_cap:
        eq = _equal_weight(codes, params)
        eq.fallback_used = True
        eq.fallback_reason = "post_cap weights sum <= 0"
        return eq

    return AllocationResult(
        mode="risk_aware_equal_weight_v1",
        codes=list(codes),
        raw_vols=raw_vols,
        clamped_vols=clamped,
        pre_cap_weights=pre_cap_n,
        post_cap_weights=post_cap,
        final_weights=post_cap,
        params_used=params,
    )


def _inverse_volatility(
    codes: List[str],
    volatilities: Dict[str, float],
    params: Dict[str, Any],
) -> AllocationResult:
    """Inverse volatility: w_i = (1/vol_i) / sum(1/vol_j)."""
    vol_floor = params.get("volatility_floor", 0.05)
    vol_cap = params.get("volatility_cap", 0.60)
    weight_floor = params.get("weight_floor", 0.00)
    weight_cap = params.get("weight_cap", 1.00)

    raw_vols, clamped = _clamp_vols(codes, volatilities, vol_floor, vol_cap)

    inv_vols = {c: 1.0 / clamped[c] for c in codes}
    pre_cap = _normalize(inv_vols)
    if not pre_cap:
        eq = _equal_weight(codes, params)
        eq.fallback_used = True
        eq.fallback_reason = "inverse vol sum <= 0"
        return eq

    post_cap = _apply_cap_floor(pre_cap, weight_floor, weight_cap)
    if not post_cap:
        eq = _equal_weight(codes, params)
        eq.fallback_used = True
        eq.fallback_reason = "post_cap weights sum <= 0"
        return eq

    return AllocationResult(
        mode="inverse_volatility_v1",
        codes=list(codes),
        raw_vols=raw_vols,
        clamped_vols=clamped,
        pre_cap_weights=pre_cap,
        post_cap_weights=post_cap,
        final_weights=post_cap,
        params_used=params,
    )
