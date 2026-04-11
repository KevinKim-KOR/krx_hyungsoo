#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/toxic_summary.py — 공통 toxic ticker 집계

P209-STEP9A realignment FIX: drawdown_contribution_report.md 와
dynamic_evidence_latest.md 가 서로 다른 기준으로 공통 toxic ticker 를
계산하여 Step9B 근거가 불일치하던 문제를 해결한다.

단일 책임: "정식 baseline (A, B) 의 top-N toxic ticker 교집합" 계산.
"""

from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_COMMON_TOXIC_TOP_N = 3


def compute_common_toxic_primary(
    analyses: List[Dict[str, Any]],
    top_n: int = DEFAULT_COMMON_TOXIC_TOP_N,
) -> List[str]:
    """정식 baseline (role != shadow_reference) 의 top-N toxic 교집합을 반환.

    - shadow_reference 는 정식 baseline 이 아니므로 교집합 계산에서 제외한다.
    - 각 variant 의 `top_ticker_contributors_to_mdd` 에서 top_n 개 ticker 를
      취한 뒤 모든 variant 의 교집합을 반환.
    - 결과는 정렬된 list.

    report_writer.py 와 evidence_writer.py 양쪽에서 이 함수를 호출하여
    동일한 "A ∩ B 공통 Toxic Tickers" 결과를 쓰도록 한다.
    """
    if top_n <= 0:
        raise ValueError(f"top_n 은 양의 정수여야 합니다: {top_n}")
    if not analyses:
        return []

    primary_sets: List[set] = []
    for a in analyses:
        if a.get("role") == "shadow_reference":
            continue
        top = a.get("top_ticker_contributors_to_mdd") or []
        primary_sets.append({r["ticker"] for r in top[:top_n] if "ticker" in r})

    if not primary_sets:
        return []

    return sorted(set.intersection(*primary_sets))
