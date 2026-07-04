"""Market Flow ML Baseline v1 (2026-07-03).

- 시간 순서 split (train 60% / validation 20% / test 20%) + target overlap 방지.
- 단일 baseline: StandardScaler + Ridge(alpha=1.0).
- 신규 의존성 X. sklearn 미선언 환경에서는 status=unavailable.
- 산출물: CSV 데이터셋 + JSON baseline artifact.

dataset 조립 로직은 `app.market_flow_dataset` 로 분리 (2026-07-03, B-3 파일 책임
과다 해소). 본 파일은 split / train / artifact writer / 실행 파이프라인만 담당.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_dataset import (  # noqa: F401 — helper re-exports for tests
    _find_strictly_prior_vix,
    _median,
    _percentile,
)
from app.market_flow_dataset import (
    BENCHMARK_KODEX200_TICKER,
    BENCHMARK_KOSPI_ID,
    BENCHMARK_VIX_ID,
    DatasetBuildResult,
    FEATURE_COLUMNS,
    ID_COLUMNS,
    TARGET_COLUMN,
    build_dataset,
    fetch_snapshot,
)

DATASET_PATH = Path("state/ml/market_flow_training_dataset_latest.csv")
BASELINE_ARTIFACT_PATH = Path("state/ml/market_flow_baseline_latest.json")

RIDGE_ALPHA = 1.0
SCHEMA_VERSION = "market_flow_baseline_v1"

# 재-export (기존 import 경로 유지 목적, backend near-threshold 회귀 방지).
__all__ = [
    "FEATURE_COLUMNS",
    "ID_COLUMNS",
    "TARGET_COLUMN",
    "BENCHMARK_KODEX200_TICKER",
    "BENCHMARK_KOSPI_ID",
    "BENCHMARK_VIX_ID",
    "DATASET_PATH",
    "BASELINE_ARTIFACT_PATH",
    "RIDGE_ALPHA",
    "SCHEMA_VERSION",
    "DatasetBuildResult",
    "build_dataset",
    "run_baseline",
    "write_dataset_csv",
]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_dataset_csv(result: DatasetBuildResult, path: Path = DATASET_PATH) -> None:
    """CSV artifact 저장. 오름차순 정렬 + 컬럼 순서 고정."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = list(ID_COLUMNS) + list(FEATURE_COLUMNS) + [TARGET_COLUMN]
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in result.rows:
            w.writerow({k: row.get(k) for k in header})
    tmp.replace(path)


def _temporal_split(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """train 60% / val 20% / test 20% + target overlap 방지.

    지시문 §8.2:
      "위 조건을 만족하지 않는 경계 인접 행은 이전 구간에서 제외한다."
    → train / val 에서 target_end_date 가 다음 구간 시작일을 침범하는 행을
    제외. val / test 자체 구간을 변경하지 않는다.
    """
    n = len(rows)
    if n < 3:
        return rows, [], []
    train_end = int(n * 0.6)
    val_end = int(n * 0.8)
    train = rows[:train_end]
    val = rows[train_end:val_end]
    test = rows[val_end:]
    if val:
        val_start = val[0]["as_of_date"]
        train = [
            r
            for r in train
            if r.get("target_end_date") is not None and r["target_end_date"] < val_start
        ]
    if test:
        test_start = test[0]["as_of_date"]
        val = [
            r
            for r in val
            if r.get("target_end_date") is not None
            and r["target_end_date"] < test_start
        ]
    return train, val, test


def _sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
        from sklearn.linear_model import Ridge  # noqa: F401
        from sklearn.preprocessing import StandardScaler  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _rows_to_xy(
    rows: list[dict[str, Any]],
) -> tuple[list[list[float]], list[float]]:
    xs: list[list[float]] = []
    ys: list[float] = []
    for r in rows:
        xs.append([float(r[c]) for c in FEATURE_COLUMNS])
        ys.append(float(r[TARGET_COLUMN]))
    return xs, ys


def _compute_metrics(
    y_true: list[float], y_pred: list[float]
) -> dict[str, Optional[float]]:
    n = len(y_true)
    if n == 0:
        return {"mae": None, "rmse": None, "directional_accuracy": None}
    errs = [p - a for p, a in zip(y_pred, y_true)]
    mae = sum(abs(e) for e in errs) / n
    rmse = (sum(e * e for e in errs) / n) ** 0.5
    dir_acc = sum(1 for p, a in zip(y_pred, y_true) if (p > 0) == (a > 0)) / n
    return {"mae": mae, "rmse": rmse, "directional_accuracy": dir_acc}


def _train_and_evaluate(
    train: list[dict[str, Any]],
    val: list[dict[str, Any]],
    test: list[dict[str, Any]],
    unlabeled_latest: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if not _sklearn_available():
        return {
            "status": "unavailable",
            "unavailable_reason": "sklearn_not_installed",
        }
    if not train or not val or not test:
        return {"status": "unavailable", "unavailable_reason": "split_insufficient"}
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    x_train, y_train = _rows_to_xy(train)
    x_val, y_val = _rows_to_xy(val)
    x_test, y_test = _rows_to_xy(test)
    scaler = StandardScaler()
    x_train_s = scaler.fit_transform(x_train)
    x_val_s = scaler.transform(x_val)
    x_test_s = scaler.transform(x_test)
    model = Ridge(alpha=RIDGE_ALPHA)
    model.fit(x_train_s, y_train)
    y_val_pred = list(model.predict(x_val_s))
    y_test_pred = list(model.predict(x_test_s))
    val_metrics = _compute_metrics(y_val, y_val_pred)
    test_metrics = _compute_metrics(y_test, y_test_pred)
    # 재학습 + 최신 무라벨 추론.
    all_x, all_y = _rows_to_xy(train + val + test)
    scaler2 = StandardScaler()
    all_x_s = scaler2.fit_transform(all_x)
    model2 = Ridge(alpha=RIDGE_ALPHA)
    model2.fit(all_x_s, all_y)
    latest_pred = None
    latest_asof = None
    latest_status = "unavailable"
    latest_reason: Optional[str] = "no_unlabeled_latest_row"
    if unlabeled_latest is not None:
        try:
            x_latest = [[float(unlabeled_latest[c]) for c in FEATURE_COLUMNS]]
        except (TypeError, KeyError, ValueError):
            latest_reason = "latest_feature_missing"
        else:
            x_latest_s = scaler2.transform(x_latest)
            latest_pred = float(model2.predict(x_latest_s)[0])
            latest_asof = unlabeled_latest["as_of_date"]
            latest_status = "ok"
            latest_reason = None
    return {
        "status": "ok",
        "unavailable_reason": None,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "latest_status": latest_status,
        "latest_asof": latest_asof,
        "latest_pred": latest_pred,
        "latest_reason": latest_reason,
    }


def _build_limitations(
    eval_result: dict[str, Any],
    rows: list[dict[str, Any]],
    val_count: int,
) -> list[str]:
    limitations: list[str] = []
    if not _sklearn_available():
        limitations.append(
            "sklearn 이 requirements.txt 에 선언되어 있지 않아 baseline 학습·평가·"
            "추론을 실행할 수 없다. 신규 의존성 추가 없이 PARTIAL 상태로 종료 "
            "(지시문 §7.1)."
        )
    if not rows:
        limitations.append("labeled 행이 0건이라 split·학습이 실행되지 않는다.")
    if val_count == 0 and rows:
        limitations.append(
            "temporal split 결과 validation row_count=0 — target overlap 방지 "
            "필터가 val 구간을 모두 제거. KOSPI 시계열이 짧아 labeled 행 밀도가 "
            "낮은 것이 원인. sklearn 을 설치해도 이 상태에서는 validation "
            "metrics 를 산출할 수 없다. KOSPI 시계열 보강이 함께 필요하다."
        )
    if eval_result.get("unavailable_reason") == "split_insufficient":
        limitations.append(
            "train / validation / test 중 하나 이상이 비어 있어 baseline 학습·평가를 "
            "실행할 수 없다."
        )
    return limitations


def run_baseline(
    db_path: Path = DEFAULT_DB_PATH,
    dataset_path: Path = DATASET_PATH,
    artifact_path: Path = BASELINE_ARTIFACT_PATH,
) -> dict[str, Any]:
    """전체 파이프라인: dataset build → CSV 저장 → split → train/eval → JSON 저장."""
    snapshot = fetch_snapshot(db_path)
    build = build_dataset(db_path=db_path)
    write_dataset_csv(build, path=dataset_path)
    rows = build.rows
    train, val, test = _temporal_split(rows)
    eval_result = _train_and_evaluate(train, val, test, build.unlabeled_latest_row)
    limitations = _build_limitations(eval_result, rows, len(val))
    if eval_result.get("status") == "ok":
        status = "ok"
    else:
        status = "unavailable"
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": _utcnow_iso(),
        "source_snapshot": {
            "kodex200_max_date": snapshot.kodex200_max_date,
            "kospi_max_date": snapshot.kospi_max_date,
            "vix_max_date": snapshot.vix_max_date,
            "etf_price_max_date": snapshot.etf_price_max_date,
        },
        "dataset": {
            "path": str(dataset_path),
            "as_of_start_date": rows[0]["as_of_date"] if rows else None,
            "as_of_end_date": rows[-1]["as_of_date"] if rows else None,
            "latest_labeled_date": rows[-1]["as_of_date"] if rows else None,
            "row_count": len(rows),
            "excluded_row_count": sum(build.excluded_reason_counts.values()),
            "excluded_reason_counts": build.excluded_reason_counts,
        },
        "feature_columns": list(FEATURE_COLUMNS),
        "target_definition": "future 20 trading-day KODEX200 simple return (%)",
        "vix_alignment": "strictly_prior_observation",
        "splits": {
            "train": {
                "start_date": train[0]["as_of_date"] if train else None,
                "end_date": train[-1]["as_of_date"] if train else None,
                "row_count": len(train),
            },
            "validation": {
                "start_date": val[0]["as_of_date"] if val else None,
                "end_date": val[-1]["as_of_date"] if val else None,
                "row_count": len(val),
            },
            "test": {
                "start_date": test[0]["as_of_date"] if test else None,
                "end_date": test[-1]["as_of_date"] if test else None,
                "row_count": len(test),
            },
        },
        "model": {
            "name": "standard_scaler_ridge",
            "ridge_alpha": RIDGE_ALPHA,
            "dependency_reused": _sklearn_available(),
        },
        "metrics": {
            "validation": eval_result.get("val_metrics")
            or {"mae": None, "rmse": None, "directional_accuracy": None},
            "test": eval_result.get("test_metrics")
            or {"mae": None, "rmse": None, "directional_accuracy": None},
        },
        "latest_inference": {
            "status": eval_result.get("latest_status") or "unavailable",
            "as_of_date": eval_result.get("latest_asof"),
            "predicted_future_kodex200_return_20d_pct": eval_result.get("latest_pred"),
            "unavailable_reason": (
                eval_result.get("unavailable_reason")
                or eval_result.get("latest_reason")
            ),
        },
        "limitations": limitations,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(artifact_path)
    return artifact
