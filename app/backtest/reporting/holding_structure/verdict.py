#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/holding_structure/verdict.py — G1~G8 실험군 verdict

P208-STEP8A holding structure 비교 실험군 각각에 대한 PROMOTE/REJECT 판정.
기준: CAGR > 15 AND MDD < 10 (P206 verdict 기준 유지)

단일 책임: (cagr, mdd) → "PROMOTE" | "REJECT"
R3 단계에서 holding_structure_compare.py god module 에서 분리된 모듈.
"""

from __future__ import annotations


def _verdict(cagr: float, mdd: float) -> str:
    """CAGR>15 & MDD<10 기준 (P206 verdict 기준 유지)."""
    if cagr is None or mdd is None:
        return "REJECT"
    return "PROMOTE" if (cagr > 15 and mdd < 10) else "REJECT"
