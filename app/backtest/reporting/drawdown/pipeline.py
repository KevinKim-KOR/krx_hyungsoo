#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/backtest/reporting/drawdown/pipeline.py — drawdown 분석 파이프라인

P209-STEP9A drawdown 분석의 오케스트레이션 단계. 단일 variant 분석
(`analyze_variant`) 과 A/B 2-variant 파이프라인 (`run_analysis_pipeline`)
을 포함한다. 각 계산 단계(window/positions/attribution/selection_quality/
bucket_risk) 는 이 모듈에서 조합 호출된다.

단일 책임: analysis orchestration (계산 모듈 호출 + 결과 조합 + 리포트 생성 호출)
R2 단계에서 drawdown_contribution.py god module 에서 분리된 모듈.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.backtest.reporting.drawdown.attribution import compute_ticker_contributions
from app.backtest.reporting.drawdown.bucket_risk import compute_bucket_risk
from app.backtest.reporting.drawdown.positions import (
    _build_close_series,
    reconstruct_daily_positions,
)
from app.backtest.reporting.drawdown.report_writer import (
    write_drawdown_contribution_report,
)
from app.backtest.reporting.drawdown.selection_quality import (
    _selection_quality_verdict,
    _summarize_selection_quality,
    compute_selection_quality,
)
from app.backtest.reporting.drawdown.window import find_mdd_window

logger = logging.getLogger(__name__)


# ─── 단일 variant 분석 orchestrator ─────────────────────────────────────
def analyze_variant(
    *,
    label: str,
    role: str,
    max_positions: int,
    allocation_mode: str,
    raw_result: Dict[str, Any],
    price_data,
    buckets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """단일 백테스트 결과에 대한 전체 drawdown 기여 분석.

    R5v3 (fallback 전수 제거): raw_result 는 BacktestRunner.run 반환값이어야
    하며 nav_history / trades / _rebalance_trace 가 반드시 존재하고 값이 None
    이 아니어야 한다. 키 누락 또는 값 None 시 raise.

    - 키 누락 → KeyError (데이터 손상)
    - 값이 None → ValueError (BacktestRunner 가 반드시 list 를 설정해야 함)
    - 빈 list → 정상 (backtest 가 실행됐지만 trade 가 없는 케이스 등 legitimate)

    이전 `raw_result["nav_history"] or []` 패턴은 None 을 silent 하게 빈
    리스트로 fallback 하여 NO_DATA 경로로 흘려보냈음. R5v3 에서 제거.
    """
    # R5v3: 키 존재 + 값 None 아님 이중 검증
    for key in ("nav_history", "trades", "_rebalance_trace"):
        if key not in raw_result:
            raise KeyError(
                f"analyze_variant: raw_result 에 {key!r} 누락 (label={label})"
            )
        if raw_result[key] is None:
            raise ValueError(
                f"analyze_variant: raw_result[{key!r}] 값이 None"
                f" (label={label}) — BacktestRunner.run 은 반드시 list 를 설정"
            )
    nav_history = raw_result["nav_history"]
    trades = raw_result["trades"]
    rebalance_trace = raw_result["_rebalance_trace"]

    close_by_code = _build_close_series(price_data)
    window = find_mdd_window(nav_history)

    if window is None:
        # 드로우다운 미발생 or nav_history 부족 — 명시적 NO_DATA 경로
        # _summarize_selection_quality([]) 를 호출하지 않고 직접 구성
        return {
            "label": label,
            "role": role,
            "max_positions": max_positions,
            "allocation_mode": allocation_mode,
            "mdd_window": None,
            "top_ticker_contributors_to_mdd": [],
            "all_ticker_contributions": [],
            "selection_quality_summary": None,
            "selection_quality_verdict": "NO_DATA",
            "worst_selection_events": [],
            "bucket_risk_summary": {},
        }

    daily_pos = reconstruct_daily_positions(trades, nav_history, close_by_code)
    contribs = compute_ticker_contributions(
        daily_pos, nav_history, window["peak_date"], window["trough_date"]
    )
    sel_events = compute_selection_quality(trades, rebalance_trace, close_by_code)
    bucket_risk = compute_bucket_risk(contribs, buckets)
    # R5: _summarize_selection_quality 가 빈 events 에서 None 을 반환하면
    # verdict 는 "NO_EVENTS" 로 명시 분기됨. 0.0 silent fallback 금지.
    summary = _summarize_selection_quality(sel_events)
    verdict = _selection_quality_verdict(summary)

    # 상위 toxic = 기여도가 가장 음수인 5개
    top_toxic = [c for c in contribs if c["contribution_to_nav_pct"] < 0][:5]
    # 최악 선택 이벤트 top 5 (worst ticker 기준 가장 큰 손실)
    # R5v2: compute_selection_quality 는 worst_return_pct 를 항상 설정
    worst_events = sorted(sel_events, key=lambda e: e["worst_return_pct"])[:5]

    return {
        "label": label,
        "role": role,
        "max_positions": max_positions,
        "allocation_mode": allocation_mode,
        "mdd_window": window,
        "top_ticker_contributors_to_mdd": top_toxic,
        "all_ticker_contributions": contribs,
        "selection_quality_summary": summary,
        "selection_quality_verdict": verdict,
        "worst_selection_events": worst_events,
        "bucket_risk_summary": bucket_risk,
    }


# ─── 2-variant pipeline (A + B) ─────────────────────────────────────────
_RAEW_DEFAULTS = {
    "mode": "risk_aware_equal_weight_v1",
    "risky_sleeve_only": True,
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


def _build_allocation_block(mode: str) -> Dict[str, Any]:
    if mode == "dynamic_equal_weight":
        return dict(_EQW_DEFAULTS)
    if mode == "risk_aware_equal_weight_v1":
        return dict(_RAEW_DEFAULTS)
    raise ValueError(f"P209-STEP9A 지원 mode 아님: {mode!r}")


def _matches_main(
    main_params: Dict[str, Any], max_positions: int, allocation_mode: str
) -> bool:
    """main_params 가 주어진 (max_positions, allocation_mode) 조합과 일치하는지 판단.

    R5v3 fallback 정책:
    - `main_params["max_positions"]` 는 REQUIRED (param_loader 에서 검증).
      누락 시 KeyError.
    - `main_params["allocation"]` 는 OPTIONAL (non-dynamic 모드에선 None).
      None 이면 allocation_mode 매칭 불가 → False 반환 (explicit 분기).
    - `alloc["mode"]` 는 allocation 블록이 존재하면 param_loader 가 검증.
      누락 시 KeyError.
    """
    if "max_positions" not in main_params:
        raise KeyError("_matches_main: main_params 에 'max_positions' 누락")
    if main_params["max_positions"] != max_positions:
        return False

    alloc = main_params.get("allocation")
    if alloc is None:
        # non-dynamic 모드: allocation 블록 자체가 없음 → 매칭 불가
        return False
    if "mode" not in alloc:
        raise KeyError(
            "_matches_main: allocation 블록에 'mode' 누락"
            " (param_loader 가 검증했어야 함)"
        )
    return alloc["mode"] == allocation_mode


def run_analysis_pipeline(
    *,
    main_params: Dict[str, Any],
    main_raw_result: Dict[str, Any],
    price_data,
    start,
    end,
    run_backtest_fn: Callable,
    project_root: Path,
    a_spec: Tuple[str, int, str],
    b_spec: Tuple[str, int, str],
    c_spec: Optional[Tuple[str, int, str]] = None,
) -> Dict[str, Any]:
    """A (operational) + B (research) + C (shadow, optional) 분석 파이프라인.

    P209-STEP9A baseline realignment FIX (2026-04-11):
    - a_spec / b_spec 는 REQUIRED. 하드코딩된 기본값 없음 (rule 6/7).
    - 호출자 (run_backtest.py) 가 SSOT 의 drawdown_analysis_baselines 블록을
      읽어 (label, max_positions, allocation_mode) tuple 로 변환 후 전달해야 함.
    - c_spec 는 optional — SSOT 에 shadow 라벨이 있을 때만 활성화.

    - A가 현재 main SSOT와 일치하면 main_raw_result를 재사용
    - 그렇지 않으면 A를 별도 실행
    - B/C는 spec 이 main 과 일치하지 않으면 별도 실행
    - 결과를 joint report로 저장하고 A 요약 dict을 main meta에 주입할 수 있게 반환
    """
    a_label, a_pos, a_mode = a_spec
    b_label, b_pos, b_mode = b_spec
    # R5v3: buckets 는 OPTIONAL (dynamic_etf_market 모드에서 빈 리스트가
    # legitimate). None 은 param_loader 스키마 위반 → raise.
    buckets_raw = main_params.get("buckets")
    if buckets_raw is None:
        raise KeyError(
            "run_analysis_pipeline: main_params 에 'buckets' 누락"
            " (param_loader 가 빈 리스트라도 설정해야 함)"
        )
    buckets: List[Dict[str, Any]] = buckets_raw

    logger.info(
        f"[P209-STEP9A] drawdown 기여 분석 파이프라인 시작"
        f" A={a_label}(pos{a_pos},{a_mode})"
        f" B={b_label}(pos{b_pos},{b_mode})"
    )

    # ── A 결과 확보 ──
    if _matches_main(main_params, a_pos, a_mode):
        a_raw = main_raw_result
        logger.info(f"[P209-STEP9A] A={a_label} main 결과 재사용")
    else:
        a_params = dict(main_params)
        a_params["max_positions"] = a_pos
        a_params["allocation"] = _build_allocation_block(a_mode)
        a_params["holding_structure_experiments"] = None
        a_params["allocation_experiments"] = None
        a_params["holding_structure_experiment_name"] = a_label
        a_raw = run_backtest_fn(
            price_data,
            a_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
        )

    # ── B 결과 확보 ──
    if _matches_main(main_params, b_pos, b_mode):
        b_raw = main_raw_result
        logger.info(f"[P209-STEP9A] B={b_label} main 결과 재사용")
    else:
        b_params = dict(main_params)
        b_params["max_positions"] = b_pos
        b_params["allocation"] = _build_allocation_block(b_mode)
        b_params["holding_structure_experiments"] = None
        b_params["allocation_experiments"] = None
        b_params["holding_structure_experiment_name"] = b_label
        b_raw = run_backtest_fn(
            price_data,
            b_params,
            start,
            end,
            enable_regime=True,
            skip_baselines=True,
        )

    # ── C (shadow) 결과 확보 — optional ──
    c_analysis: Optional[Dict[str, Any]] = None
    if c_spec is not None:
        c_label, c_pos, c_mode = c_spec
        if _matches_main(main_params, c_pos, c_mode):
            c_raw = main_raw_result
            logger.info(f"[P209-STEP9A] C={c_label} main 결과 재사용 (shadow)")
        else:
            c_params = dict(main_params)
            c_params["max_positions"] = c_pos
            c_params["allocation"] = _build_allocation_block(c_mode)
            c_params["holding_structure_experiments"] = None
            c_params["allocation_experiments"] = None
            c_params["holding_structure_experiment_name"] = c_label
            c_raw = run_backtest_fn(
                price_data,
                c_params,
                start,
                end,
                enable_regime=True,
                skip_baselines=True,
            )
        c_analysis = analyze_variant(
            label=c_label,
            role="shadow_reference",
            max_positions=c_pos,
            allocation_mode=c_mode,
            raw_result=c_raw,
            price_data=price_data,
            buckets=buckets,
        )

    a_analysis = analyze_variant(
        label=a_label,
        role="operational_baseline",
        max_positions=a_pos,
        allocation_mode=a_mode,
        raw_result=a_raw,
        price_data=price_data,
        buckets=buckets,
    )
    b_analysis = analyze_variant(
        label=b_label,
        role="research_baseline",
        max_positions=b_pos,
        allocation_mode=b_mode,
        raw_result=b_raw,
        price_data=price_data,
        buckets=buckets,
    )

    analyses = [a_analysis, b_analysis]
    if c_analysis is not None:
        analyses.append(c_analysis)
    out_dir = project_root / "reports" / "tuning"
    paths = write_drawdown_contribution_report(analyses, out_dir)

    main_inject = _build_main_meta_injection(a_analysis, b_analysis, c_analysis)
    return {
        "analyses": analyses,
        "report_paths": {k: str(v) for k, v in paths.items()},
        "main_meta_injection": main_inject,
    }


# ─── main meta 주입용 요약 dict 구성 ────────────────────────────────────
def _build_main_meta_injection(
    a_analysis: Dict[str, Any],
    b_analysis: Dict[str, Any],
    c_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """A 분석의 핵심 필드 + A/B 비교 요약을 main result meta에 주입할 형태로 반환.

    R5v2 fallback 정책:
    - `mdd_window` 와 `selection_quality_summary` 는 analyze_variant 가
      NO_DATA 경로 (window 없음 / events 없음) 에서 None 으로 설정한다.
    - 여기서는 하위 `.get(k)` 호출이 AttributeError 를 일으키지 않도록
      명시적 if-else 로 `None → {}` 변환 (R5 whitelist: display meta).
    - `or {}` 패턴 대신 명시 분기로 "None 이 legitimate NO_DATA 시그널" 임을
      독자가 즉시 알 수 있게 한다.
    """
    # R5v2: 명시적 None 분기 (or {} 금지)
    a_mdd_window = a_analysis["mdd_window"]  # Optional[Dict]
    b_mdd_window = b_analysis["mdd_window"]
    a_w: Dict[str, Any] = a_mdd_window if a_mdd_window is not None else {}
    b_w: Dict[str, Any] = b_mdd_window if b_mdd_window is not None else {}

    a_sqs = a_analysis["selection_quality_summary"]  # Optional[Dict]
    b_sqs = b_analysis["selection_quality_summary"]
    a_qs: Dict[str, Any] = a_sqs if a_sqs is not None else {}
    b_qs: Dict[str, Any] = b_sqs if b_sqs is not None else {}
    comparison: Dict[str, Any] = {
        "operational_baseline_label": a_analysis["label"],
        "operational_baseline_verdict": a_analysis["selection_quality_verdict"],
        # R5 whitelist: a_qs 가 {} 인 NO_EVENTS 경로에서 None 반환 (display)
        "operational_avg_selection_gap_pct": a_qs.get("avg_selection_gap_pct"),
        "operational_mdd_pct": a_w.get("mdd_pct"),
        "operational_positive_forward_ratio": a_qs.get("positive_forward_ratio"),
        "operational_avg_forward_return_pct": a_qs.get("avg_forward_return_pct"),
        "operational_events_with_better_unselected": a_qs.get(
            "events_with_better_unselected"
        ),
        "research_baseline_label": b_analysis["label"],
        "research_baseline_verdict": b_analysis["selection_quality_verdict"],
        "research_avg_selection_gap_pct": b_qs.get("avg_selection_gap_pct"),
        "research_mdd_pct": b_w.get("mdd_pct"),
        "research_positive_forward_ratio": b_qs.get("positive_forward_ratio"),
        "research_avg_forward_return_pct": b_qs.get("avg_forward_return_pct"),
        "research_events_with_better_unselected": b_qs.get(
            "events_with_better_unselected"
        ),
        # B군 요약 — UI side-by-side 표시용 (analyze_variant 항상 설정)
        "research_top_toxic_tickers": b_analysis["top_ticker_contributors_to_mdd"],
        "research_worst_selection_events": b_analysis["worst_selection_events"],
        "research_bucket_risk_summary": b_analysis["bucket_risk_summary"],
    }

    if c_analysis is not None:
        c_mdd_window = c_analysis["mdd_window"]
        c_w: Dict[str, Any] = c_mdd_window if c_mdd_window is not None else {}
        c_sqs = c_analysis["selection_quality_summary"]
        c_qs: Dict[str, Any] = c_sqs if c_sqs is not None else {}
        comparison.update(
            {
                "shadow_baseline_label": c_analysis["label"],
                "shadow_baseline_verdict": c_analysis["selection_quality_verdict"],
                "shadow_mdd_pct": c_w.get("mdd_pct"),
                "shadow_avg_selection_gap_pct": c_qs.get("avg_selection_gap_pct"),
                "shadow_positive_forward_ratio": c_qs.get("positive_forward_ratio"),
                "shadow_avg_forward_return_pct": c_qs.get("avg_forward_return_pct"),
                "shadow_events_with_better_unselected": c_qs.get(
                    "events_with_better_unselected"
                ),
                "shadow_top_toxic_tickers": c_analysis[
                    "top_ticker_contributors_to_mdd"
                ],
                "shadow_worst_selection_events": c_analysis["worst_selection_events"],
                "shadow_bucket_risk_summary": c_analysis["bucket_risk_summary"],
            }
        )

    return {
        "drawdown_peak_date": a_w.get("peak_date"),
        "drawdown_trough_date": a_w.get("trough_date"),
        # analyze_variant 는 이들 필드를 항상 설정한다 (빈 list/dict 포함).
        # 따라서 직접 subscript. 누락 시 KeyError = 데이터 손상.
        "mdd_window_length": a_w.get(
            "window_length_days"
        ),  # R5 whitelist: a_w 가 {} 인 NO_DATA 경로에서 None
        "top_ticker_contributors_to_mdd": a_analysis["top_ticker_contributors_to_mdd"],
        "selection_quality_summary": a_qs,
        "selection_quality_verdict": a_analysis["selection_quality_verdict"],
        "worst_selection_events": a_analysis["worst_selection_events"],
        "bucket_risk_summary": a_analysis["bucket_risk_summary"],
        "drawdown_analysis_comparison": comparison,
    }
