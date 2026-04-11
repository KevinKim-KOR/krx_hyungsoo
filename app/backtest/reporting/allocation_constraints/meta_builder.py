#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/meta_builder.py — P207 meta 필드 빌더

P207-STEP7C allocation 관련 meta 필드를 backtest_result.json meta 에 주입하기
위한 순수 함수. format_result 에서 호출된다.

단일 책임: raw result dict → allocation meta dict (9개 필드)
R4 단계에서 run_backtest.py inline 블록에서 분리된 모듈.
"""

from __future__ import annotations

from typing import Any, Dict


def build_allocation_meta(result: Dict[str, Any]) -> Dict[str, Any]:
    """raw backtest result 에서 P207 allocation meta 필드를 추출/구성한다.

    반환 dict 는 format_result 의 meta dict 에 그대로 병합될 수 있는 형태.

    R4: byte-level 보존을 위해 기존 inline 패턴을 그대로 유지 (chained
    `.get(k, default)` 포함). R5 fallback 감사 STEP 에서 재검토 대상.
    """
    alloc_params = result.get("allocation_params")
    alloc_params_or_empty = alloc_params or {}

    if alloc_params:
        experiment_name = (
            alloc_params_or_empty.get("mode", "default")
            + "_"
            + str(alloc_params_or_empty.get("weight_floor", ""))
            + "_"
            + str(alloc_params_or_empty.get("weight_cap", ""))
        )
    else:
        experiment_name = None

    return {
        "allocation_mode": result.get("allocation_mode", "bucket_portfolio"),
        "allocation_experiment_name": experiment_name,
        "allocation_fallback_used": result.get("allocation_fallback_used", False),
        "allocation_params": alloc_params,
        "allocation_weight_floor": alloc_params_or_empty.get("weight_floor"),
        "allocation_weight_cap": alloc_params_or_empty.get("weight_cap"),
        "allocation_rebalance_trace_count": len(
            result.get("_allocation_rebalance_trace", [])
        ),
        "allocation_trace_by_rebalance_date": result.get(
            "_allocation_rebalance_trace", []
        ),
    }
