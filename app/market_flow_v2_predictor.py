"""Market Flow ML v2 — 세 모델 예측 계약 (2026-07-05, FIX r1 분리).

책임:
- Full Ridge (13 feature) / Core Ridge (7 feature) / Simple Baseline 3 모델의
  feature 컬럼 정의 상수 export.
- 단일 KODEX200 거래일 t 에서 세 모델을 **동일 training subset** 으로 fit + 예측.

분리 이유 (B-2 / B-3): 예측 계약을 진단 · runner · artifact writer 와 격리.
"""

from __future__ import annotations

from typing import Any, Optional

from app.market_flow_dataset import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    TARGET_HORIZON_DAYS,
)
from app.market_flow_walk_forward import MINIMUM_TRAIN_ROW_COUNT

RIDGE_ALPHA = 1.0

# §6.1 Full Ridge — 기존 13 feature 전체 (build_dataset 계약과 동일).
FULL_FEATURE_COLUMNS: tuple[str, ...] = tuple(FEATURE_COLUMNS)

# §6.2 Core Ridge — 시장 가격 흐름 + VIX 만 (breadth · coverage 제외).
CORE_FEATURE_COLUMNS: tuple[str, ...] = (
    "kodex200_return_5d_pct",
    "kodex200_return_20d_pct",
    "kospi_return_5d_pct",
    "kospi_return_20d_pct",
    "vix_close_lagged",
    "vix_return_5obs_pct",
    "vix_return_20obs_pct",
)


def predict_three_models_at_kodex_date(
    *,
    t: str,
    labeled_by_asof: dict[str, dict[str, Any]],
    labeled_sorted: list[dict[str, Any]],
    kodex_dates: list[str],
    k_idx: int,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """단일 KODEX 거래일 t 에서 Simple / Full Ridge / Core Ridge 예측.

    지시문 §5.2: 세 모델은 동일 as_of_date / training row / actual target /
    target_end_date 사용. Core Ridge 만 feature 수가 적다는 이유로 더 많은
    기준일을 사용하면 안 됨.

    반환: (prediction row dict, excluded reason). 실패 시 (None, reason).
    """
    training_rows = [r for r in labeled_sorted if r["target_end_date"] < t]
    if len(training_rows) < MINIMUM_TRAIN_ROW_COUNT:
        return None, "minimum_train_row_count_not_reached"

    t_row = labeled_by_asof.get(t)
    if t_row is None:
        return None, "feature_row_missing_on_kodex_date"

    if k_idx + TARGET_HORIZON_DAYS >= len(kodex_dates):
        return None, "actual_target_kodex_date_out_of_range"

    if t_row.get(TARGET_COLUMN) is None or t_row.get("target_end_date") is None:
        return None, "actual_target_missing"

    expected_target_end = kodex_dates[k_idx + TARGET_HORIZON_DAYS]
    if t_row["target_end_date"] != expected_target_end:
        return None, "target_end_date_kodex_index_mismatch"

    # Full / Core feature 벡터 준비. build_dataset 계약상 labeled row 존재 =
    # Full feature 확보 (Q2 (a)). 방어적 float() 은 유지.
    try:
        x_test_full = [float(t_row[c]) for c in FULL_FEATURE_COLUMNS]
        x_test_core = [float(t_row[c]) for c in CORE_FEATURE_COLUMNS]
    except (TypeError, ValueError, KeyError):
        return None, "feature_value_error"

    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    # 학습 matrix 준비 (Simple / Full / Core 동일 training row).
    y_train = [float(r[TARGET_COLUMN]) for r in training_rows]
    x_train_full = [[float(r[c]) for c in FULL_FEATURE_COLUMNS] for r in training_rows]
    x_train_core = [[float(r[c]) for c in CORE_FEATURE_COLUMNS] for r in training_rows]

    # Full Ridge — scaler + Ridge 새로 fit.
    full_scaler = StandardScaler()
    full_scaler_train = full_scaler.fit_transform(x_train_full)
    full_model = Ridge(alpha=RIDGE_ALPHA)
    full_model.fit(full_scaler_train, y_train)
    full_pred = float(full_model.predict(full_scaler.transform([x_test_full]))[0])

    # Core Ridge — scaler + Ridge 새로 fit (Full 과 독립).
    core_scaler = StandardScaler()
    core_scaler_train = core_scaler.fit_transform(x_train_core)
    core_model = Ridge(alpha=RIDGE_ALPHA)
    core_model.fit(core_scaler_train, y_train)
    core_pred = float(core_model.predict(core_scaler.transform([x_test_core]))[0])

    # Simple Baseline — 동일 training target 평균.
    simple_pred = sum(y_train) / len(y_train)

    actual = float(t_row[TARGET_COLUMN])

    def _err(p: float) -> float:
        return p - actual

    def _dir(p: float) -> bool:
        return (p > 0) == (actual > 0)

    return (
        {
            "as_of_date": t,
            "target_end_date": t_row["target_end_date"],
            "train_start_date": training_rows[0]["as_of_date"],
            "train_end_date": training_rows[-1]["as_of_date"],
            "train_row_count": len(training_rows),
            "actual_future_return_pct": actual,
            "simple_baseline_prediction_pct": simple_pred,
            "full_ridge_prediction_pct": full_pred,
            "core_ridge_prediction_pct": core_pred,
            "simple_baseline_error_pct": _err(simple_pred),
            "full_ridge_error_pct": _err(full_pred),
            "core_ridge_error_pct": _err(core_pred),
            "simple_baseline_direction_match": _dir(simple_pred),
            "full_ridge_direction_match": _dir(full_pred),
            "core_ridge_direction_match": _dir(core_pred),
            "vix_source_date": t_row.get("vix_source_date"),
            "etf_eligible_count": t_row.get("etf_eligible_count"),
            "etf_coverage_count_20d": t_row.get("etf_coverage_count_20d"),
            "etf_coverage_ratio_20d": t_row.get("etf_coverage_ratio_20d"),
        },
        None,
    )
