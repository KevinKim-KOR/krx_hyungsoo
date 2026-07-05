"""Market Flow ML v2 — main runner + artifact writer (2026-07-05, FIX r1).

책임 (얇게 유지, B-2 / B-3):
- SQLite → build_dataset → walk-forward grid 순회 → 세 모델 예측 위임
  (`market_flow_v2_predictor`) → coverage 진단 위임
  (`market_flow_v2_diagnostics`) → CSV / JSON artifact 저장.

절대 유지 사항 (§4):
- SQLite read only. 외부 API 호출 0건.
- StandardScaler + Ridge(alpha=1.0) 유지 (predictor).
- KODEX200 20 거래일 grid 유지 (walk-forward v1 helper 재사용).
- 최소 training row 756 유지.
- target_end_date < as_of_date 누수 방지 (predictor).
- 기존 build_dataset / baseline / walk-forward artifact 미변경.

계약 확정:
- Q1 (b): numpy 는 requirements 에 명시 (numpy==2.4.6).
- Q2 (a): build_dataset labeled row 존재 = Full feature 확보.
- Q3: coverage quartile 은 실제 공통 prediction row 로만 계산 후 배정.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_baseline import _sklearn_available, _sklearn_version
from app.market_flow_dataset import (
    TARGET_HORIZON_DAYS,
    build_dataset,
    fetch_snapshot,
)
from app.market_flow_v2_diagnostics import (
    assign_quartile,
    compute_quartile_boundaries,
    coverage_by_as_of_year,
    coverage_overall_distribution,
    diff_metrics,
    model_metrics,
    quartile_model_metrics,
    target_distribution_by_year,
    yearly_model_metrics,
)
from app.market_flow_v2_predictor import (
    CORE_FEATURE_COLUMNS,
    FULL_FEATURE_COLUMNS,
    RIDGE_ALPHA,
    predict_three_models_at_kodex_date,
)
from app.market_flow_walk_forward import (
    MINIMUM_TRAIN_ROW_COUNT,
    PREDICTION_INTERVAL,
    _build_prediction_grid_kodex,
    _find_anchor_kodex_index,
    _load_kodex_trading_dates,
)

DATA_VALIDITY_ARTIFACT_PATH = Path("state/ml/market_flow_v2_data_validity_latest.json")
PREDICTIONS_CSV_PATH = Path(
    "state/ml/market_flow_v2_model_comparison_predictions_latest.csv"
)
SUMMARY_JSON_PATH = Path("state/ml/market_flow_v2_model_comparison_latest.json")

DATA_VALIDITY_SCHEMA_VERSION = "market_flow_v2_data_validity_v1"
MODEL_COMPARISON_SCHEMA_VERSION = "market_flow_v2_model_comparison_v1"

PREDICTION_CSV_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "target_end_date",
    "train_start_date",
    "train_end_date",
    "train_row_count",
    "actual_future_return_pct",
    "simple_baseline_prediction_pct",
    "full_ridge_prediction_pct",
    "core_ridge_prediction_pct",
    "simple_baseline_error_pct",
    "full_ridge_error_pct",
    "core_ridge_error_pct",
    "simple_baseline_direction_match",
    "full_ridge_direction_match",
    "core_ridge_direction_match",
    "vix_source_date",
    "etf_eligible_count",
    "etf_coverage_count_20d",
    "etf_coverage_ratio_20d",
    "coverage_quartile",
)


# ---------- 재-export (기존 import 경로 유지, 테스트 안정성 목적) ----------
# `_predict_three_models_at_kodex_date` 는 v2_predictor 로 이동됐지만 monkeypatch
# 시나리오를 위해 본 모듈 이름공간에서도 접근 가능하도록 유지.
_predict_three_models_at_kodex_date = predict_three_models_at_kodex_date
_compute_quartile_boundaries = compute_quartile_boundaries


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- artifact writers ----------


def _write_predictions_csv(predictions: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(PREDICTION_CSV_COLUMNS))
        writer.writeheader()
        for p in predictions:
            row = {k: p.get(k) for k in PREDICTION_CSV_COLUMNS}
            for k in (
                "simple_baseline_direction_match",
                "full_ridge_direction_match",
                "core_ridge_direction_match",
            ):
                row[k] = bool(row[k])
            writer.writerow(row)
    tmp.replace(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


# ---------- main runner ----------


def run_v2_model_comparison(
    db_path: Path = DEFAULT_DB_PATH,
    data_validity_path: Path = DATA_VALIDITY_ARTIFACT_PATH,
    predictions_path: Path = PREDICTIONS_CSV_PATH,
    summary_path: Path = SUMMARY_JSON_PATH,
) -> dict[str, Any]:
    """v2 Data Validity + Model Comparison 실행. artifact 3개 생성."""
    snapshot = fetch_snapshot(db_path)
    build = build_dataset(db_path=db_path)
    labeled_rows = build.rows
    labeled_by_asof = {r["as_of_date"]: r for r in labeled_rows}
    labeled_sorted = sorted(labeled_rows, key=lambda r: r["as_of_date"])
    kodex_dates = _load_kodex_trading_dates(db_path)

    excluded_reason_counts: dict[str, int] = {}
    predictions: list[dict[str, Any]] = []
    limitations: list[str] = []

    status = "ok"
    if not _sklearn_available():
        status = "unavailable"
        limitations.append("scikit-learn not available")

    anchor_k = None
    if status == "ok":
        if not labeled_rows:
            status = "unavailable"
            excluded_reason_counts["no_labeled_rows"] = 1
            limitations.append("build_dataset returned 0 labeled rows")
        else:
            anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
            if anchor_k is None:
                status = "unavailable"
                excluded_reason_counts["minimum_train_row_count_not_reached"] = 1
                limitations.append(
                    f"KODEX200 거래일 중 target_end_date < t 인 학습 행이 "
                    f"{MINIMUM_TRAIN_ROW_COUNT} 이상 확보되고 t 시점 Full "
                    f"feature + 20-KODEX 뒤 target 을 만족하는 기준일이 없다."
                )

    if status == "ok" and anchor_k is not None:
        # v2 monkeypatch 지점 — 본 모듈의 이름공간을 통해 dispatch (테스트가
        # `market_flow_v2_model_comparison._predict_three_models_at_kodex_date`
        # 를 patch 하는 관행 유지).
        import sys

        module_ns = sys.modules[__name__]
        grid = _build_prediction_grid_kodex(kodex_dates, anchor_k)
        for k_idx in grid:
            t = kodex_dates[k_idx]
            pred, reason = module_ns._predict_three_models_at_kodex_date(
                t=t,
                labeled_by_asof=labeled_by_asof,
                labeled_sorted=labeled_sorted,
                kodex_dates=kodex_dates,
                k_idx=k_idx,
            )
            if pred is None:
                key = reason or "prediction_row_unavailable"
                excluded_reason_counts[key] = excluded_reason_counts.get(key, 0) + 1
                continue
            predictions.append(pred)

    # Q3: coverage quartile 은 실제 공통 prediction row 로만 산출 후 각 row 배정.
    quartile_boundaries = compute_quartile_boundaries(predictions)
    for p in predictions:
        p["coverage_quartile"] = assign_quartile(
            p.get("etf_coverage_ratio_20d"), quartile_boundaries
        )

    # data validity artifact.
    data_validity = {
        "schema_version": DATA_VALIDITY_SCHEMA_VERSION,
        "status": status,
        "generated_at": _utcnow_iso(),
        "source_snapshot": {
            "kodex200_max_date": snapshot.kodex200_max_date,
            "kospi_max_date": snapshot.kospi_max_date,
            "vix_max_date": snapshot.vix_max_date,
            "etf_price_max_date": snapshot.etf_price_max_date,
        },
        "target_definition": (
            f"future {TARGET_HORIZON_DAYS} trading-day KODEX200 simple return (%)"
        ),
        "target_distribution_by_target_end_year": target_distribution_by_year(
            labeled_rows
        ),
        "walk_forward_coverage": {
            "prediction_count": len(predictions),
            "overall": coverage_overall_distribution(predictions),
            "by_as_of_year": coverage_by_as_of_year(predictions),
            "quartile_method": "numpy_linear",
            "quartile_boundaries": quartile_boundaries,
        },
        "excluded_reason_counts": excluded_reason_counts,
        "limitations": limitations,
    }
    _write_json(data_validity_path, data_validity)

    # model comparison artifact.
    simple = model_metrics(predictions, "simple_baseline")
    full = model_metrics(predictions, "full_ridge")
    core = model_metrics(predictions, "core_ridge")

    summary = {
        "schema_version": MODEL_COMPARISON_SCHEMA_VERSION,
        "status": status,
        "generated_at": _utcnow_iso(),
        "model_definitions": {
            "simple_baseline": {"definition": "mean(training target)"},
            "full_ridge": {
                "name": "standard_scaler_ridge",
                "ridge_alpha": RIDGE_ALPHA,
                "feature_columns": list(FULL_FEATURE_COLUMNS),
            },
            "core_ridge": {
                "name": "standard_scaler_ridge",
                "ridge_alpha": RIDGE_ALPHA,
                "feature_columns": list(CORE_FEATURE_COLUMNS),
            },
        },
        "walk_forward_rule": {
            "minimum_train_row_count": MINIMUM_TRAIN_ROW_COUNT,
            "prediction_interval_kodex200_trading_days": PREDICTION_INTERVAL,
            "training_target_end_before_as_of": True,
            "common_full_feature_grid_only": True,
        },
        "evaluation": {
            "start_date": predictions[0]["as_of_date"] if predictions else None,
            "end_date": predictions[-1]["as_of_date"] if predictions else None,
            "prediction_count": len(predictions),
            "excluded_prediction_count": sum(excluded_reason_counts.values()),
            "excluded_reason_counts": excluded_reason_counts,
        },
        "metrics": {
            "simple_baseline": simple,
            "full_ridge": full,
            "core_ridge": core,
            "full_ridge_minus_simple": diff_metrics(full, simple),
            "core_ridge_minus_simple": diff_metrics(core, simple),
            "full_ridge_minus_core": diff_metrics(full, core),
        },
        "yearly_metrics_by_target_end_year": yearly_model_metrics(predictions),
        "coverage_quartile_metrics": quartile_model_metrics(predictions),
        "artifacts": {
            "data_validity_json": str(data_validity_path),
            "predictions_csv": str(predictions_path),
            "summary_json": str(summary_path),
        },
        "limitations": limitations,
        "sklearn_version": _sklearn_version() or "",
        "numpy_version": str(np.__version__),
    }

    _write_predictions_csv(predictions, predictions_path)
    _write_json(summary_path, summary)
    return summary
