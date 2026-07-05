"""Market Flow ML v2 — Data Validity 진단 계산 (2026-07-05, FIX r1 분리).

책임:
- Target 분포 (target_end_date 연도별) 통계.
- Coverage 분포 (전체 · as_of_date 연도별) 통계.
- Coverage quartile 계산 (numpy quantile method="linear") + 각 row 배정.
- Coverage quartile 별 모델 metrics 집계.

분리 이유 (B-2 / B-3): 진단 계산을 예측 · runner · artifact writer 와 격리.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from app.market_flow_dataset import TARGET_COLUMN
from app.market_flow_walk_forward import _metrics

# ---------- target 분포 ----------


def target_distribution_by_year(
    labeled_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """§7.1: target_end_date 연도별 target 분포 통계."""
    buckets: dict[str, list[float]] = {}
    for r in labeled_rows:
        end = r.get("target_end_date")
        val = r.get(TARGET_COLUMN)
        if end is None or val is None:
            continue
        year = str(end)[:4]
        buckets.setdefault(year, []).append(float(val))
    out: list[dict[str, Any]] = []
    for year in sorted(buckets.keys()):
        arr = np.array(buckets[year], dtype=float)
        out.append(
            {
                "year": year,
                "row_count": int(arr.size),
                "mean": float(arr.mean()),
                "median": float(np.median(arr)),
                "standard_deviation": float(arr.std(ddof=0)),
                "min": float(arr.min()),
                "max": float(arr.max()),
                "percentile_10": float(np.quantile(arr, 0.10, method="linear")),
                "percentile_90": float(np.quantile(arr, 0.90, method="linear")),
                "positive_ratio": float((arr > 0).sum() / arr.size),
            }
        )
    return out


# ---------- coverage 분포 ----------


def coverage_overall_distribution(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    """§7.2: 전체 coverage 분포."""
    if not predictions:
        return {
            "min": None,
            "percentile_25": None,
            "median": None,
            "percentile_75": None,
            "max": None,
            "mean": None,
            "coverage_ratio_zero_or_unavailable_count": 0,
        }
    unavail = sum(
        1 for p in predictions if p.get("etf_coverage_ratio_20d") in (None, 0, 0.0)
    )
    values = np.array(
        [
            float(p["etf_coverage_ratio_20d"])
            for p in predictions
            if p.get("etf_coverage_ratio_20d") is not None
        ],
        dtype=float,
    )
    if values.size == 0:
        return {
            "min": None,
            "percentile_25": None,
            "median": None,
            "percentile_75": None,
            "max": None,
            "mean": None,
            "coverage_ratio_zero_or_unavailable_count": int(unavail),
        }
    return {
        "min": float(values.min()),
        "percentile_25": float(np.quantile(values, 0.25, method="linear")),
        "median": float(np.median(values)),
        "percentile_75": float(np.quantile(values, 0.75, method="linear")),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "coverage_ratio_zero_or_unavailable_count": int(unavail),
    }


def coverage_by_as_of_year(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """§7.2: as_of_date 연도별 coverage 통계."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for p in predictions:
        year = p["as_of_date"][:4]
        buckets.setdefault(year, []).append(p)
    out: list[dict[str, Any]] = []
    for year in sorted(buckets.keys()):
        rows = buckets[year]
        ratios = np.array(
            [
                float(r["etf_coverage_ratio_20d"])
                for r in rows
                if r.get("etf_coverage_ratio_20d") is not None
            ],
            dtype=float,
        )
        eligibles = np.array(
            [
                float(r["etf_eligible_count"])
                for r in rows
                if r.get("etf_eligible_count") is not None
            ],
            dtype=float,
        )
        coverages = np.array(
            [
                float(r["etf_coverage_count_20d"])
                for r in rows
                if r.get("etf_coverage_count_20d") is not None
            ],
            dtype=float,
        )
        out.append(
            {
                "year": year,
                "prediction_count": len(rows),
                "coverage_ratio_min": (float(ratios.min()) if ratios.size else None),
                "coverage_ratio_median": (
                    float(np.median(ratios)) if ratios.size else None
                ),
                "coverage_ratio_max": (float(ratios.max()) if ratios.size else None),
                "coverage_ratio_mean": (float(ratios.mean()) if ratios.size else None),
                "eligible_etf_count_mean": (
                    float(eligibles.mean()) if eligibles.size else None
                ),
                "coverage_etf_count_mean": (
                    float(coverages.mean()) if coverages.size else None
                ),
            }
        )
    return out


# ---------- coverage quartile ----------


def compute_quartile_boundaries(
    predictions: list[dict[str, Any]],
) -> dict[str, Optional[float]]:
    """§7.3: numpy quantile method="linear" q25/q50/q75."""
    values = np.array(
        [
            float(p["etf_coverage_ratio_20d"])
            for p in predictions
            if p.get("etf_coverage_ratio_20d") is not None
        ],
        dtype=float,
    )
    if values.size == 0:
        return {"q25": None, "q50": None, "q75": None}
    return {
        "q25": float(np.quantile(values, 0.25, method="linear")),
        "q50": float(np.quantile(values, 0.50, method="linear")),
        "q75": float(np.quantile(values, 0.75, method="linear")),
    }


def assign_quartile(
    ratio: Optional[float], boundaries: dict[str, Optional[float]]
) -> Optional[str]:
    """§7.3 구간 배정."""
    q25 = boundaries["q25"]
    q50 = boundaries["q50"]
    q75 = boundaries["q75"]
    if ratio is None or q25 is None or q50 is None or q75 is None:
        return None
    if ratio <= q25:
        return "Q1"
    if ratio <= q50:
        return "Q2"
    if ratio <= q75:
        return "Q3"
    return "Q4"


# ---------- metrics 집계 helper ----------


def model_metrics(
    predictions: list[dict[str, Any]], model_key: str
) -> dict[str, Optional[float]]:
    """model_key ∈ {simple_baseline, full_ridge, core_ridge}."""
    if not predictions:
        return {"mae": None, "rmse": None, "directional_accuracy": None}
    errs = [p[f"{model_key}_error_pct"] for p in predictions]
    preds = [p[f"{model_key}_prediction_pct"] for p in predictions]
    actuals = [p["actual_future_return_pct"] for p in predictions]
    return _metrics(errs, preds, actuals)


def diff_metrics(a: dict, b: dict) -> dict:
    out: dict[str, Optional[float]] = {}
    for k in ("mae", "rmse", "directional_accuracy"):
        av, bv = a.get(k), b.get(k)
        out[k] = (av - bv) if (av is not None and bv is not None) else None
    return out


def yearly_model_metrics(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """target_end_date 연도별 세 모델 metrics."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for p in predictions:
        year = p["target_end_date"][:4]
        buckets.setdefault(year, []).append(p)
    out: list[dict[str, Any]] = []
    for year in sorted(buckets.keys()):
        rows = buckets[year]
        out.append(
            {
                "year": year,
                "prediction_count": len(rows),
                "simple_baseline": model_metrics(rows, "simple_baseline"),
                "full_ridge": model_metrics(rows, "full_ridge"),
                "core_ridge": model_metrics(rows, "core_ridge"),
            }
        )
    return out


def quartile_model_metrics(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """coverage 분위별 세 모델 metrics. 동점으로 빈 분위는 unavailable."""
    buckets: dict[str, list[dict[str, Any]]] = {
        "Q1": [],
        "Q2": [],
        "Q3": [],
        "Q4": [],
    }
    for p in predictions:
        q = p.get("coverage_quartile")
        if q in buckets:
            buckets[q].append(p)
    out: list[dict[str, Any]] = []
    for q in ("Q1", "Q2", "Q3", "Q4"):
        rows = buckets[q]
        if not rows:
            out.append(
                {
                    "quartile": q,
                    "prediction_count": 0,
                    "simple_baseline": {
                        "mae": None,
                        "rmse": None,
                        "directional_accuracy": None,
                    },
                    "full_ridge": {
                        "mae": None,
                        "rmse": None,
                        "directional_accuracy": None,
                    },
                    "core_ridge": {
                        "mae": None,
                        "rmse": None,
                        "directional_accuracy": None,
                    },
                    "unavailable_reason": "quartile_empty_due_to_tie_boundaries",
                }
            )
            continue
        out.append(
            {
                "quartile": q,
                "prediction_count": len(rows),
                "simple_baseline": model_metrics(rows, "simple_baseline"),
                "full_ridge": model_metrics(rows, "full_ridge"),
                "core_ridge": model_metrics(rows, "core_ridge"),
            }
        )
    return out
