"""Market Flow ML Walk-forward Lookback v1 (2026-07-05).

지시문 §5 계약:

- build_dataset() 은 전체 SQLite snapshot 에서 1회 생성 (기존 계약 미변경).
- 각 예측 기준일 t 마다 target_end_date < t 인 labeled row 로만 학습.
- StandardScaler / Ridge(alpha=1.0) 는 기준일별 새로 fit — 전체 fit 재사용 금지.
- Ridge 예측과 simple baseline (training target 평균) 을 동일 학습 범위에서 비교.
- 최초 anchor t0: target_end_date < t0 인 labeled row 가 756 개 이상 확보되는
  가장 이른 KODEX200 거래일. 이후 후보는 KODEX200 거래일 index 기준 20 간격
  고정 grid (skip 이 grid 를 밀지 않음).

부작용: SQLite read only. 외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건.
기존 baseline artifact (`state/ml/market_flow_baseline_latest.json` /
`state/ml/market_flow_training_dataset_latest.csv`) 미변경.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_flow_baseline import _sklearn_available, _sklearn_version
from app.market_flow_dataset import (
    BENCHMARK_KODEX200_TICKER,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    TARGET_HORIZON_DAYS,
    build_dataset,
    fetch_snapshot,
)

WALK_FORWARD_PREDICTIONS_CSV_PATH = Path(
    "state/ml/market_flow_walk_forward_predictions_latest.csv"
)
WALK_FORWARD_SUMMARY_JSON_PATH = Path("state/ml/market_flow_walk_forward_latest.json")

SCHEMA_VERSION = "market_flow_walk_forward_v1"
MINIMUM_TRAIN_ROW_COUNT = 756
PREDICTION_INTERVAL = 20

RIDGE_ALPHA = 1.0

PREDICTION_CSV_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "train_start_date",
    "train_end_date",
    "train_row_count",
    "target_end_date",
    "ridge_prediction_pct",
    "simple_baseline_prediction_pct",
    "actual_future_return_pct",
    "ridge_error_pct",
    "simple_baseline_error_pct",
    "ridge_direction_match",
    "simple_baseline_direction_match",
    "vix_source_date",
    "etf_eligible_count",
    "etf_coverage_count_20d",
    "etf_coverage_ratio_20d",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- KODEX200 거래일 시퀀스 로드 ----------


def _load_kodex_trading_dates(db_path: Path) -> list[str]:
    """SQLite 에서 KODEX200 거래일 시퀀스 (오름차순) 를 read.

    FIX r1 (검증자 A-1): 지시문 Q2 (a) 확정 — grid 기준은 labeled row 가
    아니라 KODEX200 거래일 index. build_dataset 결과에는 excluded 된 KODEX
    거래일 (kodex/kospi lookback insufficient / target horizon unavailable)
    이 빠져있으므로, anchor 이후 excluded 가 있으면 labeled row index 로
    20 간격을 계산하면 실제 KODEX 거래일 간격과 어긋난다.
    """
    if not db_path.exists():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT date FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date ASC",
            (BENCHMARK_KODEX200_TICKER,),
        )
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        con.close()


# ---------- anchor / grid selection (KODEX200 거래일 index 기준) ----------


def _find_anchor_kodex_index(
    kodex_dates: list[str],
    labeled_by_asof: dict[str, dict[str, Any]],
) -> Optional[int]:
    """최초 예측 기준일 t0 의 KODEX200 거래일 index.

    조건 (모두 만족하는 가장 이른 KODEX 거래일):
      - target_end_date < t0 인 labeled row 가 756 개 이상
      - t0 feature 계산 가능 (labeled_by_asof 에 존재)
      - t0 이후 정확히 20 번째 KODEX 거래일 actual target 존재
        (labeled_by_asof[t0][TARGET_COLUMN] is not None)
    """
    labeled_sorted = sorted(labeled_by_asof.values(), key=lambda r: r["as_of_date"])
    for k_idx, t in enumerate(kodex_dates):
        if k_idx + TARGET_HORIZON_DAYS >= len(kodex_dates):
            break
        row = labeled_by_asof.get(t)
        if row is None:
            continue
        if row.get(TARGET_COLUMN) is None:
            continue
        count = 0
        for r in labeled_sorted:
            if r["as_of_date"] >= t:
                break
            if r["target_end_date"] < t:
                count += 1
                if count >= MINIMUM_TRAIN_ROW_COUNT:
                    break
        if count >= MINIMUM_TRAIN_ROW_COUNT:
            return k_idx
    return None


def _build_prediction_grid_kodex(
    kodex_dates: list[str], anchor_kodex_idx: int
) -> list[int]:
    """anchor_kodex_idx 부터 KODEX200 거래일 index 기준 20 간격 고정 grid.

    skip 시에도 grid 는 밀지 않는다 (Q2 (a) 확정).
    grid 는 t0, t0+20, t0+40 ... 형태의 KODEX 거래일 index 리스트.
    """
    grid: list[int] = []
    i = anchor_kodex_idx
    while i < len(kodex_dates):
        grid.append(i)
        i += PREDICTION_INTERVAL
    return grid


# ---------- per-anchor training & prediction ----------


def _rows_to_matrix(
    rows: list[dict[str, Any]],
) -> tuple[list[list[float]], list[float]]:
    xs: list[list[float]] = []
    ys: list[float] = []
    for r in rows:
        xs.append([float(r[c]) for c in FEATURE_COLUMNS])
        ys.append(float(r[TARGET_COLUMN]))
    return xs, ys


def _predict_at_kodex_date(
    *,
    t: str,
    labeled_by_asof: dict[str, dict[str, Any]],
    labeled_sorted: list[dict[str, Any]],
    kodex_dates: list[str],
    k_idx: int,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """단일 KODEX 거래일 t 에서 학습 + 예측.

    반환: (prediction row dict, excluded reason). 성공 시 (dict, None).
    실패 시 (None, "<reason>").
    """
    # (1) target_end_date < t 인 labeled row 로만 학습 subset 구성.
    training_rows = [r for r in labeled_sorted if r["target_end_date"] < t]
    if len(training_rows) < MINIMUM_TRAIN_ROW_COUNT:
        return None, "minimum_train_row_count_not_reached"

    # (2) t 시점 feature 확보 여부 (labeled_by_asof 에 존재해야 함).
    t_row = labeled_by_asof.get(t)
    if t_row is None:
        return None, "feature_row_missing_on_kodex_date"

    # (3) t 이후 정확히 20 번째 KODEX 거래일 actual target 확보.
    if k_idx + TARGET_HORIZON_DAYS >= len(kodex_dates):
        return None, "actual_target_kodex_date_out_of_range"
    if t_row.get(TARGET_COLUMN) is None or t_row.get("target_end_date") is None:
        return None, "actual_target_missing"
    expected_target_end = kodex_dates[k_idx + TARGET_HORIZON_DAYS]
    if t_row["target_end_date"] != expected_target_end:
        # dataset builder 와 kodex_dates 시퀀스 불일치 — 방어적 skip.
        return None, "target_end_date_kodex_index_mismatch"

    try:
        x_test = [float(t_row[c]) for c in FEATURE_COLUMNS]
    except (TypeError, ValueError, KeyError):
        return None, "feature_value_error"

    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    x_train, y_train = _rows_to_matrix(training_rows)
    scaler = StandardScaler()
    x_train_s = scaler.fit_transform(x_train)
    model = Ridge(alpha=RIDGE_ALPHA)
    model.fit(x_train_s, y_train)
    x_test_s = scaler.transform([x_test])
    ridge_pred = float(model.predict(x_test_s)[0])

    simple_pred = sum(y_train) / len(y_train)

    actual = float(t_row[TARGET_COLUMN])
    ridge_err = ridge_pred - actual
    simple_err = simple_pred - actual
    ridge_dir_match = (ridge_pred > 0) == (actual > 0)
    simple_dir_match = (simple_pred > 0) == (actual > 0)

    return (
        {
            "as_of_date": t,
            "train_start_date": training_rows[0]["as_of_date"],
            "train_end_date": training_rows[-1]["as_of_date"],
            "train_row_count": len(training_rows),
            "target_end_date": t_row["target_end_date"],
            "ridge_prediction_pct": ridge_pred,
            "simple_baseline_prediction_pct": simple_pred,
            "actual_future_return_pct": actual,
            "ridge_error_pct": ridge_err,
            "simple_baseline_error_pct": simple_err,
            "ridge_direction_match": ridge_dir_match,
            "simple_baseline_direction_match": simple_dir_match,
            "vix_source_date": t_row.get("vix_source_date"),
            "etf_eligible_count": t_row.get("etf_eligible_count"),
            "etf_coverage_count_20d": t_row.get("etf_coverage_count_20d"),
            "etf_coverage_ratio_20d": t_row.get("etf_coverage_ratio_20d"),
        },
        None,
    )


# ---------- metrics ----------


def _metrics(errors: list[float], preds: list[float], actuals: list[float]) -> dict:
    n = len(errors)
    if n == 0:
        return {"mae": None, "rmse": None, "directional_accuracy": None}
    mae = sum(abs(e) for e in errors) / n
    rmse = (sum(e * e for e in errors) / n) ** 0.5
    dir_acc = sum(1 for p, a in zip(preds, actuals) if (p > 0) == (a > 0)) / n
    return {"mae": mae, "rmse": rmse, "directional_accuracy": dir_acc}


def _diff_metrics(a: dict, b: dict) -> dict:
    out: dict[str, Optional[float]] = {}
    for k in ("mae", "rmse", "directional_accuracy"):
        av, bv = a.get(k), b.get(k)
        out[k] = (av - bv) if (av is not None and bv is not None) else None
    return out


def _yearly_metrics(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """target_end_date 연도별 성능 요약."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for p in predictions:
        year = p["target_end_date"][:4]
        buckets.setdefault(year, []).append(p)
    out: list[dict[str, Any]] = []
    for year in sorted(buckets.keys()):
        rows = buckets[year]
        actuals = [r["actual_future_return_pct"] for r in rows]
        ridge_preds = [r["ridge_prediction_pct"] for r in rows]
        ridge_errs = [r["ridge_error_pct"] for r in rows]
        simple_preds = [r["simple_baseline_prediction_pct"] for r in rows]
        simple_errs = [r["simple_baseline_error_pct"] for r in rows]
        out.append(
            {
                "year": year,
                "prediction_count": len(rows),
                "ridge": _metrics(ridge_errs, ridge_preds, actuals),
                "simple_baseline": _metrics(simple_errs, simple_preds, actuals),
            }
        )
    return out


# ---------- artifact writers ----------


def _write_predictions_csv(predictions: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(PREDICTION_CSV_COLUMNS))
        writer.writeheader()
        for p in predictions:
            row = {k: p.get(k) for k in PREDICTION_CSV_COLUMNS}
            # bool → csv 표기 안정화.
            row["ridge_direction_match"] = bool(row["ridge_direction_match"])
            row["simple_baseline_direction_match"] = bool(
                row["simple_baseline_direction_match"]
            )
            writer.writerow(row)
    tmp.replace(path)


def _write_summary_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(path)


# ---------- main runner ----------


def run_walk_forward(
    db_path: Path = DEFAULT_DB_PATH,
    predictions_path: Path = WALK_FORWARD_PREDICTIONS_CSV_PATH,
    summary_path: Path = WALK_FORWARD_SUMMARY_JSON_PATH,
) -> dict[str, Any]:
    """Walk-forward Lookback v1 실행.

    SQLite → build_dataset (1회) → anchor 탐색 → grid 순회 → per-anchor 재학습
    · 예측 → CSV · JSON artifact.
    """
    snapshot = fetch_snapshot(db_path)
    build = build_dataset(db_path=db_path)
    rows = build.rows

    excluded_reason_counts: dict[str, int] = {}
    predictions: list[dict[str, Any]] = []
    status = "ok"
    limitations: list[str] = []

    if not _sklearn_available():
        status = "unavailable"
        limitations.append("scikit-learn not available")
        payload = _build_summary_payload(
            status=status,
            snapshot=snapshot,
            predictions=predictions,
            excluded_reason_counts=excluded_reason_counts,
            limitations=limitations,
            predictions_path=predictions_path,
            summary_path=summary_path,
        )
        _write_predictions_csv(predictions, predictions_path)
        _write_summary_json(payload, summary_path)
        return payload

    if not rows:
        status = "unavailable"
        excluded_reason_counts["no_labeled_rows"] = 1
        limitations.append("build_dataset returned 0 labeled rows")
        payload = _build_summary_payload(
            status=status,
            snapshot=snapshot,
            predictions=predictions,
            excluded_reason_counts=excluded_reason_counts,
            limitations=limitations,
            predictions_path=predictions_path,
            summary_path=summary_path,
        )
        _write_predictions_csv(predictions, predictions_path)
        _write_summary_json(payload, summary_path)
        return payload

    kodex_dates = _load_kodex_trading_dates(db_path)
    labeled_by_asof: dict[str, dict[str, Any]] = {r["as_of_date"]: r for r in rows}
    labeled_sorted = sorted(rows, key=lambda r: r["as_of_date"])

    anchor_kodex_idx = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    if anchor_kodex_idx is None:
        status = "unavailable"
        excluded_reason_counts["minimum_train_row_count_not_reached"] = 1
        limitations.append(
            f"KODEX200 거래일 중 target_end_date < t 인 학습 행이 "
            f"{MINIMUM_TRAIN_ROW_COUNT} 개 이상 + feature/target 확보 조건을 "
            f"만족하는 기준일이 없다."
        )
        payload = _build_summary_payload(
            status=status,
            snapshot=snapshot,
            predictions=predictions,
            excluded_reason_counts=excluded_reason_counts,
            limitations=limitations,
            predictions_path=predictions_path,
            summary_path=summary_path,
        )
        _write_predictions_csv(predictions, predictions_path)
        _write_summary_json(payload, summary_path)
        return payload

    grid = _build_prediction_grid_kodex(kodex_dates, anchor_kodex_idx)
    for k_idx in grid:
        t = kodex_dates[k_idx]
        pred, reason = _predict_at_kodex_date(
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

    payload = _build_summary_payload(
        status=status,
        snapshot=snapshot,
        predictions=predictions,
        excluded_reason_counts=excluded_reason_counts,
        limitations=limitations,
        predictions_path=predictions_path,
        summary_path=summary_path,
    )
    _write_predictions_csv(predictions, predictions_path)
    _write_summary_json(payload, summary_path)
    return payload


def _build_summary_payload(
    *,
    status: str,
    snapshot,
    predictions: list[dict[str, Any]],
    excluded_reason_counts: dict[str, int],
    limitations: list[str],
    predictions_path: Path,
    summary_path: Path,
) -> dict[str, Any]:
    actuals = [p["actual_future_return_pct"] for p in predictions]
    ridge_preds = [p["ridge_prediction_pct"] for p in predictions]
    ridge_errs = [p["ridge_error_pct"] for p in predictions]
    simple_preds = [p["simple_baseline_prediction_pct"] for p in predictions]
    simple_errs = [p["simple_baseline_error_pct"] for p in predictions]

    ridge_metrics = _metrics(ridge_errs, ridge_preds, actuals)
    simple_metrics = _metrics(simple_errs, simple_preds, actuals)
    diff_metrics = _diff_metrics(ridge_metrics, simple_metrics)

    start_date = predictions[0]["as_of_date"] if predictions else None
    end_date = predictions[-1]["as_of_date"] if predictions else None

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "generated_at": _utcnow_iso(),
        "source_snapshot": {
            "kodex200_max_date": snapshot.kodex200_max_date,
            "kospi_max_date": snapshot.kospi_max_date,
            "vix_max_date": snapshot.vix_max_date,
            "etf_price_max_date": snapshot.etf_price_max_date,
        },
        "model": {
            "name": "standard_scaler_ridge",
            "ridge_alpha": RIDGE_ALPHA,
            "scikit_learn_version": _sklearn_version() or "",
        },
        "feature_columns": list(FEATURE_COLUMNS),
        "target_definition": (
            f"future {TARGET_HORIZON_DAYS} trading-day KODEX200 simple return (%)"
        ),
        "walk_forward_rule": {
            "minimum_train_row_count": MINIMUM_TRAIN_ROW_COUNT,
            "prediction_interval_kodex200_trading_days": PREDICTION_INTERVAL,
            "training_target_end_before_as_of": True,
        },
        "evaluation": {
            "start_date": start_date,
            "end_date": end_date,
            "prediction_count": len(predictions),
            "excluded_prediction_count": sum(excluded_reason_counts.values()),
            "excluded_reason_counts": excluded_reason_counts,
        },
        "metrics": {
            "ridge": ridge_metrics,
            "simple_baseline": simple_metrics,
            "ridge_minus_simple": diff_metrics,
        },
        "yearly_metrics": _yearly_metrics(predictions),
        "artifacts": {
            "predictions_csv": str(predictions_path),
            "summary_json": str(summary_path),
        },
        "limitations": limitations,
    }
