# -*- coding: utf-8 -*-
"""
app/tuning/segment_eval.py — P204-STEP2 구간 평가 유틸리티

1-Run Multi-Slice: nav_history를 사후 균등 3분할하여
각 구간의 CAGR/MDD/Sharpe를 계산한다.
코어 백테스트 엔진은 건드리지 않는다.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List, Tuple


def compute_segment_metrics(
    nav_history: List[Tuple[str, float]],
    n_segments: int = 3,
) -> Dict[str, Any]:
    """
    nav_history를 균등 분할하여 구간별 CAGR/MDD/Sharpe를 계산한다.

    Args:
        nav_history: [(date_str, nav_value), ...] 시계열
        n_segments: 분할 수 (기본 3)

    Returns:
        {
          "segment_evaluation_enabled": True,
          "segment_scheme": "equal_3way",
          "segment_count": 3,
          "segment_eval_ready": True/False,
          "segment_status": "OK" / "INSUFFICIENT_DATA" / "MISSING_NAV_HISTORY",
          "full_period_metrics": { cagr, mdd, sharpe, days },
          "segment_metrics": { "SEG_1": {...}, "SEG_2": {...}, "SEG_3": {...} },
          "segment_lengths": [n1, n2, n3],
        }
    """
    base = {
        "segment_evaluation_enabled": True,
        "segment_scheme": "equal_3way",
        "segment_count": n_segments,
    }

    if not nav_history or len(nav_history) < 2:
        base["segment_eval_ready"] = False
        base["segment_status"] = "MISSING_NAV_HISTORY"
        base["full_period_metrics"] = {}
        base["segment_metrics"] = {}
        base["segment_lengths"] = []
        return base

    total_days = len(nav_history)
    min_days_per_seg = 5
    if total_days < min_days_per_seg * n_segments:
        base["segment_eval_ready"] = False
        base["segment_status"] = "INSUFFICIENT_DATA"
        base["full_period_metrics"] = _calc_metrics(nav_history)
        base["segment_metrics"] = {}
        base["segment_lengths"] = []
        return base

    # Full period
    full_metrics = _calc_metrics(nav_history)

    # Equal split
    seg_size = total_days // n_segments
    segments = []
    for i in range(n_segments):
        start_idx = i * seg_size
        end_idx = start_idx + seg_size if i < n_segments - 1 else total_days
        segments.append(nav_history[start_idx:end_idx])

    seg_metrics = {}
    seg_lengths = []
    for i, seg in enumerate(segments):
        key = f"SEG_{i + 1}"
        seg_metrics[key] = _calc_metrics(seg)
        seg_lengths.append(len(seg))

    base["segment_eval_ready"] = True
    base["segment_status"] = "OK"
    base["full_period_metrics"] = full_metrics
    base["segment_metrics"] = seg_metrics
    base["segment_lengths"] = seg_lengths
    return base


def _calc_metrics(nav_history: List[Tuple[str, float]]) -> Dict[str, Any]:
    """단일 구간의 CAGR / MDD / Sharpe를 계산한다."""
    if len(nav_history) < 2:
        return {"cagr": 0.0, "mdd": 0.0, "sharpe": 0.0, "days": len(nav_history)}

    navs = [v for _, v in nav_history]
    days = len(navs)
    start_nav = navs[0]
    end_nav = navs[-1]

    # CAGR
    if start_nav > 0 and days > 1:
        total_return = end_nav / start_nav
        years = days / 252.0
        if years > 0 and total_return > 0:
            cagr = (total_return ** (1.0 / years) - 1.0) * 100.0
        else:
            cagr = 0.0
    else:
        cagr = 0.0

    # MDD
    peak = navs[0]
    max_dd = 0.0
    for v in navs:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    mdd = max_dd * 100.0

    # Sharpe
    sharpe = 0.0
    if days >= 3:
        rets = [(navs[i] / navs[i - 1]) - 1.0 for i in range(1, days) if navs[i - 1] > 0]
        if len(rets) > 1:
            mean_r = sum(rets) / len(rets)
            var_r = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
            std_r = math.sqrt(var_r) if var_r > 0 else 0.0
            if std_r > 0:
                sharpe = (mean_r / std_r) * math.sqrt(252)

    return {
        "cagr": round(cagr, 4),
        "mdd": round(mdd, 4),
        "sharpe": round(sharpe, 4),
        "days": days,
    }
