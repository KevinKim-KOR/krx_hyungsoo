#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/bucket_risk.py — bucket/group 수준 위험 집계

P209-STEP9A drawdown 분석의 bucket 집계 단계. 종목별 기여도를 bucket
멤버십 기준으로 묶어 그룹 단위 위험 요약을 만든다.

단일 책임: ticker_contribs + buckets → bucket-level summary dict
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List


def compute_bucket_risk(
    ticker_contribs: List[Dict[str, Any]],
    buckets: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """종목별 기여를 bucket 멤버십 기준으로 집계.

    dynamic_etf_market 모드에서는 실제 거래 종목이 buckets universe에 없을 수
    있으므로, 매칭 안 되는 종목은 'dynamic_pool'로 분류한다.
    """
    tk_to_bucket: Dict[str, str] = {}
    for b in buckets or []:
        name = b.get("name", "unknown")
        for tk in b.get("universe", []) or []:
            tk_to_bucket[tk] = name

    agg: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "ticker_count": 0,
            "total_contribution_pct": 0.0,
            "avg_weight_sum": 0.0,
            "days_held_sum": 0,
        }
    )

    for row in ticker_contribs:
        code = row.get("ticker")
        bucket = tk_to_bucket.get(code, "dynamic_pool")
        a = agg[bucket]
        a["ticker_count"] += 1
        a["total_contribution_pct"] += float(row.get("contribution_to_nav_pct", 0.0))
        a["avg_weight_sum"] += float(row.get("avg_weight", 0.0))
        a["days_held_sum"] += int(row.get("days_in_portfolio", 0))

    out: Dict[str, Dict[str, Any]] = {}
    for bucket, a in agg.items():
        cnt = a["ticker_count"]
        out[bucket] = {
            "ticker_count": int(cnt),
            "total_contribution_pct": round(a["total_contribution_pct"], 4),
            "avg_weight": round(a["avg_weight_sum"] / cnt, 4) if cnt else 0.0,
            "avg_days_held": round(a["days_held_sum"] / cnt, 2) if cnt else 0.0,
        }
    return out
