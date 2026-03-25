# -*- coding: utf-8 -*-
"""
app/tuning/scoring.py - P204 Step3 objective and safe-math scoring
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, Tuple

# Hard constraints
MAX_MDD_PCT = 20.0
MAX_TOTAL_TRADES = 900

# Step3 objective constants
OBJECTIVE_VERSION = "P204_STEP3_V2"
OBJECTIVE_FORMULA = "Score=(0.45*CAGR_agg)-(0.35*MDD_agg)+(0.20*Sharpe_agg)-(1.00*OverfitPenalty)"
OBJECTIVE_WEIGHTS = {
    "w1": 0.45,
    "w2": 0.35,
    "w3": 0.20,
    "w4": 1.00,
}

# Safe score fallback
INVALID_SCORE_FLOOR = -10.0


def _clip(value: float, lower: float, upper: float) -> Tuple[float, bool]:
    clipped = min(max(value, lower), upper)
    return clipped, clipped != value


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _infer_scale_source(cagr_values: Iterable[float], mdd_values: Iterable[float]) -> str:
    # MDD decimal should be <= 1.0 in normal cases.
    if any(abs(value) > 1.0 for value in mdd_values):
        return "percent_to_decimal"
    if any(abs(value) > 1.0 for value in cagr_values):
        return "percent_to_decimal"
    return "decimal_native"


def _safe_exp(clipped_input: float) -> float:
    try:
        value = math.exp(clipped_input)
    except OverflowError:
        return math.exp(4.0)
    if not math.isfinite(value):
        return math.exp(4.0)
    return value


def _invalid_result(metric_scale_source: str) -> Dict[str, Any]:
    return {
        "score": INVALID_SCORE_FLOOR,
        "objective_version": OBJECTIVE_VERSION,
        "objective_formula": OBJECTIVE_FORMULA,
        "objective_weights": dict(OBJECTIVE_WEIGHTS),
        "objective_breakdown": {
            "cagr_full": 0.0,
            "cagr_seg_mean": 0.0,
            "mdd_full": 0.0,
            "mdd_seg_mean": 0.0,
            "sharpe_full": 0.0,
            "sharpe_seg_mean": 0.0,
            "penalty_var": 0.0,
            "penalty_tail": 0.0,
            "final_score": INVALID_SCORE_FLOOR,
        },
        "cagr_agg": 0.0,
        "mdd_agg": 0.0,
        "sharpe_agg": 0.0,
        "overfit_penalty": 0.0,
        "hard_penalty_triggered": False,
        "worst_segment": "N/A",
        "metric_scale_normalized": "decimal",
        "metric_scale_source": metric_scale_source,
        "score_reason_code": "INVALID_METRIC_NORMALIZED",
    }


def compute_score(
    *,
    metrics: Dict[str, Any],
    segment_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Step3 objective score with safe-math, metric normalization, and hard caps.
    """
    full_metrics = segment_data.get("full_period_metrics", {}) if isinstance(segment_data, dict) else {}
    seg_metrics = segment_data.get("segment_metrics", {}) if isinstance(segment_data, dict) else {}

    seg_keys = ["SEG_1", "SEG_2", "SEG_3"]
    raw_seg_cagr = [_safe_float(seg_metrics.get(key, {}).get("cagr")) for key in seg_keys]
    raw_seg_mdd = [_safe_float(seg_metrics.get(key, {}).get("mdd")) for key in seg_keys]
    raw_seg_sharpe = [_safe_float(seg_metrics.get(key, {}).get("sharpe")) for key in seg_keys]

    full_cagr = _safe_float(full_metrics.get("cagr"))
    full_mdd = _safe_float(full_metrics.get("mdd"))
    full_sharpe = _safe_float(full_metrics.get("sharpe"))

    # Fallback to trial metrics if full-period metrics are missing.
    if full_cagr is None:
        full_cagr = _safe_float(metrics.get("cagr"))
    if full_mdd is None:
        full_mdd = _safe_float(metrics.get("mdd_pct"))
    if full_sharpe is None:
        full_sharpe = _safe_float(metrics.get("sharpe"))

    required_values = [full_cagr, full_mdd, full_sharpe, *raw_seg_cagr, *raw_seg_mdd, *raw_seg_sharpe]
    if any(value is None for value in required_values):
        return _invalid_result(metric_scale_source="decimal_native")

    raw_cagr_values = [full_cagr, *raw_seg_cagr]  # type: ignore[list-item]
    raw_mdd_values = [full_mdd, *raw_seg_mdd]  # type: ignore[list-item]
    metric_scale_source = _infer_scale_source(raw_cagr_values, raw_mdd_values)
    scale_factor = 0.01 if metric_scale_source == "percent_to_decimal" else 1.0

    cagr_full = full_cagr * scale_factor  # type: ignore[operator]
    mdd_full = full_mdd * scale_factor  # type: ignore[operator]
    cagr_seg = [value * scale_factor for value in raw_seg_cagr]  # type: ignore[operator]
    mdd_seg = [value * scale_factor for value in raw_seg_mdd]  # type: ignore[operator]
    sharpe_seg = [float(value) for value in raw_seg_sharpe]  # type: ignore[arg-type]
    sharpe_full = float(full_sharpe)  # type: ignore[arg-type]

    cagr_seg_mean = mean(cagr_seg)
    mdd_seg_mean = mean(mdd_seg)
    sharpe_seg_mean = mean(sharpe_seg)

    cagr_agg = 0.40 * cagr_full + 0.60 * cagr_seg_mean
    mdd_agg = 0.50 * mdd_full + 0.50 * mdd_seg_mean
    sharpe_agg = 0.40 * sharpe_full + 0.60 * sharpe_seg_mean

    safe_math_clipped = False

    # Dispersion penalty
    dispersion = 1.5 * pstdev(cagr_seg) + 1.2 * pstdev(mdd_seg) + 1.0 * pstdev(sharpe_seg)
    exp_input_var, was_clipped = _clip(3.0 * dispersion, 0.0, 4.0)
    safe_math_clipped = safe_math_clipped or was_clipped
    penalty_var_raw = _safe_exp(exp_input_var) - 1.0
    penalty_var, was_clipped = _clip(penalty_var_raw, 0.0, 5.0)
    safe_math_clipped = safe_math_clipped or was_clipped

    # Tail penalty
    penalty_tail = 0.0
    hard_penalty_triggered = False
    worst_segment = "SEG_1"
    worst_segment_quality = float("inf")

    for idx, key in enumerate(seg_keys):
        cagr_value = cagr_seg[idx]
        mdd_value = mdd_seg[idx]
        sharpe_value = sharpe_seg[idx]

        quality = cagr_value - mdd_value + (0.2 * sharpe_value)
        if quality < worst_segment_quality:
            worst_segment_quality = quality
            worst_segment = key

        if mdd_value > 0.18:
            hard_penalty_triggered = True
            exp_input, was_clipped = _clip(25.0 * (mdd_value - 0.18), 0.0, 4.0)
            safe_math_clipped = safe_math_clipped or was_clipped
            penalty_tail += _safe_exp(exp_input)

        if cagr_value < 0.0:
            hard_penalty_triggered = True
            exp_input, was_clipped = _clip(6.0 * abs(cagr_value), 0.0, 4.0)
            safe_math_clipped = safe_math_clipped or was_clipped
            penalty_tail += _safe_exp(exp_input) - 1.0

        if sharpe_value < 0.0:
            hard_penalty_triggered = True
            exp_input, was_clipped = _clip(2.0 * abs(sharpe_value), 0.0, 4.0)
            safe_math_clipped = safe_math_clipped or was_clipped
            penalty_tail += 0.5 * (_safe_exp(exp_input) - 1.0)

    penalty_tail, was_clipped = _clip(penalty_tail, 0.0, 5.0)
    safe_math_clipped = safe_math_clipped or was_clipped

    overfit_penalty, was_clipped = _clip(penalty_var + penalty_tail, 0.0, 10.0)
    safe_math_clipped = safe_math_clipped or was_clipped

    score = (
        OBJECTIVE_WEIGHTS["w1"] * cagr_agg
        - OBJECTIVE_WEIGHTS["w2"] * mdd_agg
        + OBJECTIVE_WEIGHTS["w3"] * sharpe_agg
        - OBJECTIVE_WEIGHTS["w4"] * overfit_penalty
    )

    if not math.isfinite(score):
        return _invalid_result(metric_scale_source=metric_scale_source)

    reason_code = "SAFE_MATH_CLIPPED" if safe_math_clipped else ""
    final_score = max(score, INVALID_SCORE_FLOOR)

    return {
        "score": round(final_score, 6),
        "objective_version": OBJECTIVE_VERSION,
        "objective_formula": OBJECTIVE_FORMULA,
        "objective_weights": dict(OBJECTIVE_WEIGHTS),
        "objective_breakdown": {
            "cagr_full": round(cagr_full, 6),
            "cagr_seg_mean": round(cagr_seg_mean, 6),
            "mdd_full": round(mdd_full, 6),
            "mdd_seg_mean": round(mdd_seg_mean, 6),
            "sharpe_full": round(sharpe_full, 6),
            "sharpe_seg_mean": round(sharpe_seg_mean, 6),
            "penalty_var": round(penalty_var, 6),
            "penalty_tail": round(penalty_tail, 6),
            "final_score": round(final_score, 6),
        },
        "cagr_agg": round(cagr_agg, 6),
        "mdd_agg": round(mdd_agg, 6),
        "sharpe_agg": round(sharpe_agg, 6),
        "overfit_penalty": round(overfit_penalty, 6),
        "hard_penalty_triggered": hard_penalty_triggered,
        "worst_segment": worst_segment,
        "metric_scale_normalized": "decimal",
        "metric_scale_source": metric_scale_source,
        "score_reason_code": reason_code,
    }


def should_prune(mdd_pct: float, total_trades: int) -> str | None:
    """
    Return prune reason if hard constraints are violated, otherwise None.
    """
    if mdd_pct > MAX_MDD_PCT:
        return f"MDD {mdd_pct:.1f}% > {MAX_MDD_PCT}%"
    if total_trades > MAX_TOTAL_TRADES:
        return f"trades {total_trades} > {MAX_TOTAL_TRADES}"
    return None
