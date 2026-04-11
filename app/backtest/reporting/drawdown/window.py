#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/window.py — MDD window 식별

P209-STEP9A drawdown 분석의 첫 단계. nav_history 에서 최대낙폭 구간
(peak_date, trough_date) 과 관련 지표를 추출한다.

단일 책임: cummax 기반으로 최대 drawdown 구간을 찾는다.
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def find_mdd_window(nav_history: List[Tuple[Any, float]]) -> Optional[Dict[str, Any]]:
    """nav_history에서 최대낙폭 구간(peak/trough)을 찾는다.

    nav_history: [(date_like, nav_float), ...]
    """
    if not nav_history or len(nav_history) < 2:
        return None

    peak_idx = 0
    trough_idx = 0
    cur_peak_nav = float(nav_history[0][1])
    cur_peak_idx = 0
    max_dd = 0.0

    for i, (_d, nav) in enumerate(nav_history):
        nv = float(nav)
        if nv > cur_peak_nav:
            cur_peak_nav = nv
            cur_peak_idx = i
        if cur_peak_nav > 0:
            dd = (nv - cur_peak_nav) / cur_peak_nav
            if dd < max_dd:
                max_dd = dd
                peak_idx = cur_peak_idx
                trough_idx = i

    return {
        "peak_date": str(nav_history[peak_idx][0]),
        "peak_nav": round(float(nav_history[peak_idx][1]), 2),
        "trough_date": str(nav_history[trough_idx][0]),
        "trough_nav": round(float(nav_history[trough_idx][1]), 2),
        "mdd_pct": round(abs(max_dd) * 100, 4),
        "window_length_days": int(trough_idx - peak_idx),
    }
