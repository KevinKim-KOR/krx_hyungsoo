#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/allocation_constraints/sweep.py — P207 allocation sweep

P207-STEP7C allocation_experiments 실행 로직. 각 실험군에 대해 backtest 를
실행하고, 결과를 수집해 정렬된 rows 를 생성한 뒤 비교 산출물을 만든다.

단일 책임: experiments list → rows (verdict 포함) + 산출물 생성 호출
R4 단계에서 run_backtest.py inline 블록에서 분리된 모듈. P207 cleanup 핵심.

주의:
- allocation mode / verdict 기준 수정 금지
- 실험군별 변경 허용값은 allocation 블록 (mode/floor/cap 등)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.backtest.reporting.allocation_constraints.diagnostic import (
    allocation_experiment_verdict,
)
from app.backtest.reporting.allocation_constraints.report_writer import (
    write_allocation_constraint_compare,
)

logger = logging.getLogger(__name__)


def run_allocation_constraint_sweep(
    experiments: List[Dict[str, Any]],
    base_params: Dict[str, Any],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    format_result_fn: Callable,
    project_root: Path,
) -> List[Dict[str, Any]]:
    """allocation_experiments sweep 실행 + 비교 산출물 생성.

    각 실험군당 allocation 블록만 override 되며 나머지 파라미터는 그대로 공유.

    Args:
        experiments: strategy_params_latest.json 의 allocation_experiments 리스트
            (각 항목: experiment_id, allocation={mode, weight_floor, weight_cap, ...})
        base_params: run_backtest 에 전달할 base 파라미터
        price_data: 공통 price data
        start, end: 백테스트 기간
        run_backtest_fn: run_backtest 함수 참조 (순환 import 방지)
        format_result_fn: format_result 함수 참조
        project_root: 프로젝트 루트 (reports/tuning 경로 해석용)

    Returns:
        실험군 결과 dict 리스트 (Sharpe 기준 내림차순 정렬, rank 부여됨)
    """
    logger.info(f"[P207-SWEEP] 실험군 {len(experiments)}개 실행")

    exp_results: List[Dict[str, Any]] = []
    for exp in experiments:
        # R5: experiment_id 는 param_loader._validate_experiments 에서 필수로
        # 검증되므로 여기서 silent 'unknown' fallback 금지.
        if "experiment_id" not in exp:
            raise KeyError(
                "run_allocation_constraint_sweep: 실험군에 experiment_id 누락"
                f" (exp={exp!r})"
            )
        eid = exp["experiment_id"]
        ea = exp.get("allocation")
        if not ea:
            # R5: allocation 블록이 없으면 param_loader 가 이미 reject 했어야
            # 한다. 여기 도달하면 스키마 불일치이므로 raise.
            raise KeyError(
                f"run_allocation_constraint_sweep: experiment_id={eid}"
                f" 에 'allocation' 블록 누락"
            )
        try:
            ep = dict(base_params)
            ep["allocation"] = ea
            er = run_backtest_fn(
                price_data,
                ep,
                start,
                end,
                enable_regime=True,
                skip_baselines=True,
            )
            ef = format_result_fn(
                er,
                ep,
                start,
                end,
                price_data=price_data,
                run_mode="experiment",
            )
            es = ef["summary"]
            ec = es.get("cagr")
            em = es.get("mdd")
            exp_results.append(
                {
                    "experiment_id": eid,
                    "mode": ea.get("mode"),
                    "weight_floor": ea.get("weight_floor"),
                    "weight_cap": ea.get("weight_cap"),
                    "CAGR": round(ec, 4) if ec else None,
                    "MDD": round(em, 4) if em else None,
                    "Sharpe": round(es.get("sharpe", 0), 4),
                    "trades": ef["meta"].get("total_trades", 0),
                    "fallback_used": er.get("allocation_fallback_used", False),
                    "verdict": allocation_experiment_verdict(ec, em),
                }
            )
            logger.info(f"[P207-SWEEP] {eid}:" f" CAGR={ec:.2f} MDD={em:.2f}")
        except Exception as eexc:
            logger.warning(f"[P207-SWEEP] {eid} 실패: {eexc}")
            exp_results.append(
                {
                    "experiment_id": eid,
                    "mode": ea.get("mode") if ea else "?",
                    "error": str(eexc),
                }
            )

    if not exp_results:
        return exp_results

    # 정렬 + rank 부여 (원본 inline 과 동일 로직)
    sorted_valid = [r for r in exp_results if "error" not in r]
    sorted_valid.sort(key=lambda x: x.get("Sharpe") or -999, reverse=True)
    for i, r in enumerate(sorted_valid):
        r["rank"] = i + 1
    errors = [r for r in exp_results if "error" in r]

    # 산출물 생성 (sorted_valid 순서대로 CSV/MD 기록 — rank 와 파일 순서 일치)
    out_dir = project_root / "reports" / "tuning"
    write_allocation_constraint_compare(
        sorted_valid=sorted_valid,
        errors=errors,
        total_experiments=len(exp_results),
        out_dir=out_dir,
    )

    return exp_results
