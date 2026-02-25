# -*- coding: utf-8 -*-
"""
app/tuning/scoring.py — P167-R 스코어 계산 + 하드 제약

score = sharpe - 2.0 * (mdd_pct / 100) - 0.0002 * total_trades

레거시 참조: _archive/legacy_20260102/extensions/tuning/objective.py
"""
from __future__ import annotations

# ─── 하드 제약 임계값 ──────────────────────────────────────────────────
MAX_MDD_PCT = 20.0        # MDD > 20% → prune
MAX_TOTAL_TRADES = 900    # total_trades > 900 → prune

# ─── 스코어 가중치 ─────────────────────────────────────────────────────
MDD_PENALTY_WEIGHT = 2.0
TRADE_PENALTY_WEIGHT = 0.0002


def compute_score(sharpe: float, mdd_pct: float, total_trades: int) -> float:
    """
    균형형 스코어 계산.

    Args:
        sharpe: Sharpe Ratio (연환산)
        mdd_pct: Maximum Drawdown (%, 양수값. 예: 15.0 = 15%)
        total_trades: 총 거래 횟수

    Returns:
        score (높을수록 좋음)
    """
    return (
        sharpe
        - MDD_PENALTY_WEIGHT * (mdd_pct / 100.0)
        - TRADE_PENALTY_WEIGHT * total_trades
    )


def should_prune(mdd_pct: float, total_trades: int) -> str | None:
    """
    하드 제약 위반 시 prune 사유 반환, 통과 시 None.

    Args:
        mdd_pct: MDD (%, 양수)
        total_trades: 총 거래 횟수

    Returns:
        prune 사유 문자열 또는 None
    """
    if mdd_pct > MAX_MDD_PCT:
        return f"MDD {mdd_pct:.1f}% > {MAX_MDD_PCT}%"
    if total_trades > MAX_TOTAL_TRADES:
        return f"trades {total_trades} > {MAX_TOTAL_TRADES}"
    return None
