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

    R5v2 fallback 정책:
    - buckets: None 이거나 빈 리스트 가능 (legitimate, dynamic_etf_market 모드)
    - bucket dict 의 name/universe: param_loader 에서 검증된 SSOT → 직접 subscript
    - ticker_contribs row 의 필드: compute_ticker_contributions 가 항상 설정
      → 직접 subscript
    - tk_to_bucket.get(code, "dynamic_pool"): 매칭 없으면 'dynamic_pool' 로
      분류 (R5 whitelist: 의도된 기본 분류 bucket, silent bug 아님)
    """
    # buckets 는 None 이나 빈 리스트일 수 있음 (명시적 None check)
    tk_to_bucket: Dict[str, str] = {}
    if buckets is not None:
        for b in buckets:
            # bucket 스키마는 param_loader 가 검증 → name/universe 필수
            if "name" not in b:
                raise KeyError(
                    "compute_bucket_risk: bucket 에 'name' 누락"
                    " (param_loader 가 검증했어야 함)"
                )
            if "universe" not in b:
                raise KeyError("compute_bucket_risk: bucket 에 'universe' 누락")
            name = b["name"]
            for tk in b["universe"]:
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
        # ticker_contribs 는 compute_ticker_contributions 의 산출물
        # → ticker/contribution_to_nav_pct/avg_weight/days_in_portfolio 항상 설정
        code = row["ticker"]
        # R5 whitelist: dynamic_pool 은 "bucket 매칭 없음" 의 의도된 기본 분류
        bucket = tk_to_bucket.get(code, "dynamic_pool")
        a = agg[bucket]
        a["ticker_count"] += 1
        a["total_contribution_pct"] += float(row["contribution_to_nav_pct"])
        a["avg_weight_sum"] += float(row["avg_weight"])
        a["days_held_sum"] += int(row["days_in_portfolio"])

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
