#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/holding_structure/sweep.py — G1~G8 실험군 sweep

P208-STEP8A holding structure 비교 실험(G1~G8) 실행 로직.
max_positions × allocation_mode 조합을 동일 dynamic universe / hybrid B+D /
safe asset 정책 하에서 실행하고, 각 실험군의 결과를 수집해 정렬된 rows 를
반환한다.

단일 책임: experiments list → rows (format_result + verdict) + 산출물 생성 호출
R3 단계에서 holding_structure_compare.py god module 에서 분리된 모듈.

주의:
- dynamic scanner / hybrid regime / safe asset / verdict 기준 수정 금지
- 실험군별 변경 허용값은 오직 max_positions, allocation_mode
- inverse_volatility_v1 재도입 금지
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.backtest.reporting.holding_structure.report_writer import _write_outputs
from app.backtest.reporting.holding_structure.verdict import _verdict

logger = logging.getLogger(__name__)

_RAEW_DEFAULTS = {
    "mode": "risk_aware_equal_weight_v1",
    "volatility_lookback": 20,
    "volatility_floor": 0.05,
    "volatility_cap": 0.6,
    "weight_floor": 0.35,
    "weight_cap": 0.65,
    "fallback_mode": "dynamic_equal_weight",
}

_EQW_DEFAULTS = {
    "mode": "dynamic_equal_weight",
    "fallback_mode": "dynamic_equal_weight",
}


def _build_allocation_block(allocation_mode: str) -> Dict[str, Any]:
    """실험군 allocation_mode에 맞는 allocation 블록 반환.

    P208-STEP8A는 대표 2개 모드만 허용:
    - dynamic_equal_weight
    - risk_aware_equal_weight_v1 (P207 기본 floor/cap=0.35/0.65 유지)
    """
    if allocation_mode == "dynamic_equal_weight":
        return dict(_EQW_DEFAULTS)
    if allocation_mode == "risk_aware_equal_weight_v1":
        return dict(_RAEW_DEFAULTS)
    raise ValueError(f"P208-STEP8A 허용되지 않은 allocation_mode: {allocation_mode!r}")


def run_holding_structure_sweep(
    experiments: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    format_result_fn: Callable,
    project_root: Path,
) -> List[Dict[str, Any]]:
    """G1~G8 실험군을 동일 dynamic universe/hybrid regime/safe asset 하에서 실행.

    각 실험군당 max_positions와 allocation_mode만 변경되며 나머지 정책/시나리오는
    base_params 그대로 공유된다.
    """
    logger.info(f"[P208-SWEEP] holding_structure 실험군 {len(experiments)}개 실행")

    out_dir = project_root / "reports" / "tuning"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for exp in experiments:
        name = exp["name"]
        max_pos = exp["max_positions"]
        mode = exp["allocation_mode"]

        try:
            exp_params = dict(base_params)
            exp_params["max_positions"] = max_pos
            exp_params["allocation"] = _build_allocation_block(mode)
            exp_params["holding_structure_experiment_name"] = name
            # 하위 sweep 중첩 방지
            exp_params["holding_structure_experiments"] = None
            exp_params["allocation_experiments"] = None

            raw = run_backtest_fn(
                price_data,
                exp_params,
                start,
                end,
                enable_regime=True,
                skip_baselines=True,
            )
            formatted = format_result_fn(
                raw,
                exp_params,
                start,
                end,
                price_data=price_data,
                run_mode="holding_structure_experiment",
            )
            summary = formatted["summary"]
            meta = formatted["meta"]

            cagr = summary.get("cagr")
            mdd = summary.get("mdd")
            sharpe = summary.get("sharpe")
            blocked_totals = meta.get("blocked_reason_totals") or {}
            blocked_max_pos = int(blocked_totals.get("BLOCKED_MAX_POSITIONS", 0))

            rows.append(
                {
                    "variant": name,
                    "max_positions": max_pos,
                    "allocation_mode": mode,
                    "cagr": round(cagr, 4) if cagr is not None else None,
                    "mdd": round(mdd, 4) if mdd is not None else None,
                    "sharpe": round(sharpe, 4) if sharpe is not None else None,
                    "total_trades": meta.get("total_trades", 0),
                    "avg_held_positions": meta.get("avg_held_positions", 0.0),
                    "max_held_positions_observed": meta.get(
                        "max_held_positions_observed", 0
                    ),
                    "rebalances_with_more_than_2_candidates": meta.get(
                        "rebalances_with_more_than_2_candidates", 0
                    ),
                    "blocked_max_positions": blocked_max_pos,
                    "blocked_reason_totals": blocked_totals,
                    "turnover_proxy": meta.get("turnover_proxy", 0.0),
                    "verdict": _verdict(cagr, mdd),
                }
            )
            logger.info(
                f"[P208-SWEEP] {name}: pos={max_pos} mode={mode}"
                f" CAGR={cagr} MDD={mdd} blocked_max_pos={blocked_max_pos}"
            )
        except Exception as exc:
            logger.warning(f"[P208-SWEEP] {name} 실패: {exc}")
            errors.append(
                {
                    "variant": name,
                    "max_positions": max_pos,
                    "allocation_mode": mode,
                    "error": str(exc),
                }
            )

    # 정렬: 1차 MDD 오름차순, 2차 CAGR 내림차순
    def _sort_key(r: Dict[str, Any]):
        mdd = r.get("mdd")
        cagr = r.get("cagr")
        return (
            mdd if mdd is not None else 9999.0,
            -(cagr if cagr is not None else -9999.0),
        )

    rows.sort(key=_sort_key)
    for i, r in enumerate(rows, start=1):
        r["rank"] = i

    _write_outputs(rows, errors, out_dir)
    return rows
