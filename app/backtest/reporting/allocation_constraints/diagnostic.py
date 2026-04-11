#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/diagnostic.py — P207 verdict 판정

P207-STEP7C allocation experiment verdict (CAGR>15 & MDD<10) 기준.

단일 책임: (cagr, mdd) → "PROMOTE" | "REJECT"
R4 단계에서 run_backtest.py inline 블록에서 분리된 모듈.
"""

from __future__ import annotations

from typing import Optional


def allocation_experiment_verdict(cagr: Optional[float], mdd: Optional[float]) -> str:
    """CAGR > 15 AND MDD < 10 판정 (P206 verdict 기준 유지).

    R4: inline 로직 그대로 이전. cagr/mdd 가 None 또는 0 이면 REJECT.
    (기존 inline 은 `if _ec and _ec > 15 and _em and _em < 10` 형태로
     `0.0` 도 False 로 처리하므로 동일하게 유지)
    """
    if cagr and cagr > 15 and mdd and mdd < 10:
        return "PROMOTE"
    return "REJECT"
