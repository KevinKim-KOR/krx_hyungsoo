#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/meta_builder.py — P207 meta 필드 빌더

P207-STEP7C allocation 관련 meta 필드를 backtest_result.json meta 에 주입하기
위한 순수 함수. format_result 에서 호출된다.

단일 책임: raw result dict → allocation meta dict (8개 필드)
R4 에서 run_backtest.py inline 블록에서 분리. R5 에서 fallback 정책 적용.

R5 정책 (fallback 제거):
- 필수 필드 (`allocation_mode`, `allocation_fallback_used`, `_allocation_rebalance_trace`):
  누락 시 KeyError raise. 이들은 BacktestRunner.run 이 반드시 설정하므로
  누락은 데이터 손상을 의미한다.
- 선택 필드 (`allocation_params`): non-dynamic 모드에서 None 이 legitimate.
  explicit None 반환 허용.
- 파생 필드 (`allocation_weight_floor/cap`, `allocation_experiment_name`):
  allocation_params 가 None 이면 None 전파. explicit None 처리.
"""

from __future__ import annotations

from typing import Any, Dict


def build_allocation_meta(result: Dict[str, Any]) -> Dict[str, Any]:
    """raw backtest result 에서 P207 allocation meta 필드를 추출/구성한다.

    반환 dict 는 format_result 의 meta dict 에 그대로 병합될 수 있는 형태.
    """
    # R5: 필수 필드 — BacktestRunner.run 이 항상 설정하므로 누락 = 데이터 손상
    if "allocation_mode" not in result:
        raise KeyError(
            "build_allocation_meta: result 에 'allocation_mode' 누락"
            " (BacktestRunner.run 이 반드시 설정해야 함)"
        )
    if "allocation_fallback_used" not in result:
        raise KeyError(
            "build_allocation_meta: result 에 'allocation_fallback_used' 누락"
        )
    if "_allocation_rebalance_trace" not in result:
        raise KeyError(
            "build_allocation_meta: result 에 '_allocation_rebalance_trace' 누락"
        )

    # R5: allocation_params 는 non-dynamic 모드에서 legitimate 하게 None
    alloc_params = result.get("allocation_params")

    # 파생 필드: allocation_params 가 None 이면 모두 explicit None
    if alloc_params is None:
        experiment_name = None
        weight_floor = None
        weight_cap = None
    else:
        experiment_name = (
            alloc_params.get("mode", "default")
            + "_"
            + str(alloc_params.get("weight_floor", ""))
            + "_"
            + str(alloc_params.get("weight_cap", ""))
        )
        weight_floor = alloc_params.get("weight_floor")
        weight_cap = alloc_params.get("weight_cap")

    return {
        "allocation_mode": result["allocation_mode"],
        "allocation_experiment_name": experiment_name,
        "allocation_fallback_used": result["allocation_fallback_used"],
        "allocation_params": alloc_params,
        "allocation_weight_floor": weight_floor,
        "allocation_weight_cap": weight_cap,
        "allocation_rebalance_trace_count": len(result["_allocation_rebalance_trace"]),
        "allocation_trace_by_rebalance_date": result["_allocation_rebalance_trace"],
    }
