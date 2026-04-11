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

    R5v2 fallback 정책:
    - REQUIRED (raise on missing): allocation_mode, allocation_fallback_used,
      _allocation_rebalance_trace (BacktestRunner.run 항상 설정)
    - OPTIONAL (None 허용): allocation_params (non-dynamic 모드에서 None)
    - OPTIONAL 하위 (allocation_params 가 dict 일 때):
      * mode: REQUIRED — allocation_params 가 dict 이면 반드시 존재 (raise)
      * weight_floor, weight_cap: optional (equal_weight / inverse_vol
        mode 에서 legitimate 하게 없음 → explicit None)
    - 파생 (experiment_name): weight_floor/cap 이 None 이면 빈 문자열로
      표시 (기존 display format 유지). `.get(k, "")` 의 빈 문자열 default 를
      제거하고 `None → ""` 명시 변환으로 대체.
    """
    # REQUIRED: BacktestRunner.run 이 항상 설정
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

    # OPTIONAL: allocation_params 는 non-dynamic 모드에서 legitimate 하게 None
    alloc_params = result.get("allocation_params")

    if alloc_params is None:
        experiment_name = None
        weight_floor = None
        weight_cap = None
    else:
        # allocation_params 가 dict 이면 'mode' 는 REQUIRED (param_loader 검증)
        if "mode" not in alloc_params:
            raise KeyError(
                "build_allocation_meta: allocation_params 에 'mode' 누락"
                " (param_loader._validate_experiments 가 검증했어야 함)"
            )
        mode = alloc_params["mode"]
        # OPTIONAL: weight_floor/cap 은 mode 별로 있을 수도/없을 수도
        # (equal_weight 는 없음, risk_aware 는 있음). explicit None.
        weight_floor = alloc_params.get("weight_floor")
        weight_cap = alloc_params.get("weight_cap")
        # 파생 experiment_name: None → "" 명시 변환 (기존 display 포맷 유지)
        fl_str = "" if weight_floor is None else str(weight_floor)
        cap_str = "" if weight_cap is None else str(weight_cap)
        experiment_name = f"{mode}_{fl_str}_{cap_str}"

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
