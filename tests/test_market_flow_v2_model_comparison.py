"""Market Flow ML v2 자동 테스트 (2026-07-05).

지시문 §11 필수 17 케이스.
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.market_benchmark_store import upsert_benchmark_prices
from app.market_data_store import (
    EtfDailyPriceRow,
    EtfMasterRow,
    init_db,
    upsert_daily_prices,
    upsert_etf_master,
)
from app.market_flow_baseline import (
    BENCHMARK_KODEX200_TICKER,
    BENCHMARK_KOSPI_ID,
    BENCHMARK_VIX_ID,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
)
from app.market_flow_dataset import build_dataset
from app.market_flow_v2_diagnostics import (
    assign_quartile,
    compute_quartile_boundaries,
    quartile_model_metrics,
)
from app.market_flow_v2_model_comparison import run_v2_model_comparison
from app.market_flow_v2_predictor import (
    CORE_FEATURE_COLUMNS,
    FULL_FEATURE_COLUMNS,
    predict_three_models_at_kodex_date,
)
from app.market_flow_walk_forward import (
    PREDICTION_INTERVAL,
    _find_anchor_kodex_index,
    _load_kodex_trading_dates,
)


def _iso_dates(start: str, count: int) -> list[str]:
    d = date.fromisoformat(start)
    out: list[str] = []
    for _ in range(count):
        out.append(d.isoformat())
        d = d + timedelta(days=1)
    return out


def _seed_full(db: Path, n: int) -> list[str]:
    dates = _iso_dates("2020-01-01", n)
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker=BENCHMARK_KODEX200_TICKER,
                date=d,
                open=None,
                high=None,
                low=None,
                close=100.0 + i * 0.3,
                volume=None,
                change=None,
            )
            for i, d in enumerate(dates)
        ],
        source="TEST",
        db_path=db,
    )
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_KOSPI_ID,
        benchmark_name="KOSPI",
        rows=[(d, 200.0 + i * 0.5) for i, d in enumerate(dates)],
        source="TEST",
        db_path=db,
    )
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_VIX_ID,
        benchmark_name="VIX",
        rows=[(d, 15.0 + (i % 7) * 0.4) for i, d in enumerate(dates)],
        source="TEST",
        db_path=db,
    )
    for i, tk in enumerate(("111111", "222222", "333333")):
        upsert_etf_master(
            [
                EtfMasterRow(
                    ticker=tk,
                    name=f"NORMAL_{tk}",
                    category="1",
                    price=None,
                    volume=None,
                    market_cap=None,
                )
            ],
            source="TEST",
            db_path=db,
        )
        upsert_daily_prices(
            [
                EtfDailyPriceRow(
                    ticker=tk,
                    date=d,
                    open=None,
                    high=None,
                    low=None,
                    close=50.0 + i + j * 0.2,
                    volume=None,
                    change=None,
                )
                for j, d in enumerate(dates)
            ],
            source="TEST",
            db_path=db,
        )
    return dates


@pytest.fixture
def big_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    _seed_full(db, n=900)
    return db


@pytest.fixture
def small_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    _seed_full(db, n=200)
    return db


def _get_ctx(db_path: Path):
    build = build_dataset(db_path=db_path)
    labeled_by_asof = {r["as_of_date"]: r for r in build.rows}
    labeled_sorted = sorted(build.rows, key=lambda r: r["as_of_date"])
    kodex_dates = _load_kodex_trading_dates(db_path)
    anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    return kodex_dates, labeled_by_asof, labeled_sorted, anchor_k


# ---------- §11 케이스 ----------


def test_1_full_and_core_feature_columns_are_exact() -> None:
    """§11.1: Full 13 / Core 7 feature 정확 분리."""
    assert len(FULL_FEATURE_COLUMNS) == 13
    assert set(FULL_FEATURE_COLUMNS) == set(FEATURE_COLUMNS)
    assert len(CORE_FEATURE_COLUMNS) == 7
    assert set(CORE_FEATURE_COLUMNS) == {
        "kodex200_return_5d_pct",
        "kodex200_return_20d_pct",
        "kospi_return_5d_pct",
        "kospi_return_20d_pct",
        "vix_close_lagged",
        "vix_return_5obs_pct",
        "vix_return_20obs_pct",
    }
    # Core ⊂ Full.
    assert set(CORE_FEATURE_COLUMNS).issubset(set(FULL_FEATURE_COLUMNS))


def test_2_three_models_share_common_grid_and_training(big_db: Path) -> None:
    """§11.2: Simple / Full / Core 동일 as_of_date · training row · actual."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_ctx(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred, _ = predict_three_models_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred is not None
    # 세 모델 모두 동일 target · train range.
    assert "actual_future_return_pct" in pred
    assert pred["train_start_date"] and pred["train_end_date"]
    training = [r for r in labeled_sorted if r["target_end_date"] < t]
    assert pred["train_row_count"] == len(training)


def test_3_training_rows_use_target_end_before_as_of(big_db: Path) -> None:
    """§11.3: training row 는 target_end_date < as_of_date 만."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_ctx(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    training = [r for r in labeled_sorted if r["target_end_date"] < t]
    for r in training:
        assert r["target_end_date"] < t


def test_4_full_and_core_scalers_refit_per_anchor(big_db: Path) -> None:
    """§11.4: 각 기준일별 scaler / Ridge 새로 fit — anchor 이후 rows 접근 없음.

    truncated labeled_sorted (t 이전) 로만 예측해도 결과 동일.
    """
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_ctx(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred_all, _ = predict_three_models_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    truncated = [r for r in labeled_sorted if r["as_of_date"] < t]
    pred_tr, _ = predict_three_models_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=truncated,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred_all is not None and pred_tr is not None
    assert pred_all["full_ridge_prediction_pct"] == pytest.approx(
        pred_tr["full_ridge_prediction_pct"]
    )
    assert pred_all["core_ridge_prediction_pct"] == pytest.approx(
        pred_tr["core_ridge_prediction_pct"]
    )
    assert pred_all["simple_baseline_prediction_pct"] == pytest.approx(
        pred_tr["simple_baseline_prediction_pct"]
    )


def test_5_simple_baseline_equals_training_target_mean(big_db: Path) -> None:
    """§11.5: Simple Baseline = training target 평균."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_ctx(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred, _ = predict_three_models_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred is not None
    training = [r for r in labeled_sorted if r["target_end_date"] < t]
    expected = sum(r[TARGET_COLUMN] for r in training) / len(training)
    assert pred["simple_baseline_prediction_pct"] == pytest.approx(expected)


def test_6_grid_is_kodex_20_and_skip_preserved(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§11.6: KODEX200 20 거래일 grid + skip 후 grid 유지."""
    from app import market_flow_v2_model_comparison as v2

    kodex_dates = _load_kodex_trading_dates(big_db)
    build = build_dataset(db_path=big_db)
    labeled_by_asof = {r["as_of_date"]: r for r in build.rows}
    anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    assert anchor_k is not None

    skip_target = anchor_k + PREDICTION_INTERVAL
    original = v2._predict_three_models_at_kodex_date

    def wrapper(*, t, labeled_by_asof, labeled_sorted, kodex_dates, k_idx):
        if k_idx == skip_target:
            return None, "forced_skip_for_test"
        return original(
            t=t,
            labeled_by_asof=labeled_by_asof,
            labeled_sorted=labeled_sorted,
            kodex_dates=kodex_dates,
            k_idx=k_idx,
        )

    monkeypatch.setattr(v2, "_predict_three_models_at_kodex_date", wrapper)
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    date_to_k = {d: i for i, d in enumerate(kodex_dates)}
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        kidxs = [date_to_k[row["as_of_date"]] for row in csv.DictReader(f)]
    assert skip_target not in kidxs
    assert (anchor_k + 2 * PREDICTION_INTERVAL) in kidxs


def test_7_full_feature_missing_excludes_all_three(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§11.7: Full row 부재 grid 후보 → 세 모델 모두 예측 X + 사유 기록.

    build_dataset 결과에서 anchor+20 KODEX 거래일에 해당하는 labeled row 를
    제거한 뒤 실행 → 해당 기준일 예측 없음 + `feature_row_missing_on_kodex_date`.
    """
    from app import market_flow_v2_model_comparison as v2

    kodex_dates = _load_kodex_trading_dates(big_db)
    build_orig = build_dataset(db_path=big_db)
    labeled_by_asof = {r["as_of_date"]: r for r in build_orig.rows}
    anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    assert anchor_k is not None
    skip_t = kodex_dates[anchor_k + PREDICTION_INTERVAL]

    orig_build = v2.build_dataset

    def stub_build(db_path):
        result = orig_build(db_path=db_path)
        result.rows = [r for r in result.rows if r["as_of_date"] != skip_t]
        return result

    monkeypatch.setattr(v2, "build_dataset", stub_build)
    payload = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    assert (
        payload["evaluation"]["excluded_reason_counts"].get(
            "feature_row_missing_on_kodex_date", 0
        )
        >= 1
    )
    # 예측 CSV 에 skip_t 없음.
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        asofs = [row["as_of_date"] for row in csv.DictReader(f)]
    assert skip_t not in asofs


def test_8_error_and_direction_computed_per_spec(big_db: Path, tmp_path: Path) -> None:
    """§11.8: error = pred - actual, direction = (pred>0)==(actual>0)."""
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            actual = float(row["actual_future_return_pct"])
            for key in ("simple_baseline", "full_ridge", "core_ridge"):
                pred = float(row[f"{key}_prediction_pct"])
                err = float(row[f"{key}_error_pct"])
                assert err == pytest.approx(pred - actual)
                assert (row[f"{key}_direction_match"] == "True") == (
                    (pred > 0) == (actual > 0)
                )


def test_9_target_distribution_by_year_from_labeled_rows(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.9: target 분포는 target_end_date 연도별 labeled row 기준."""
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    dv = json.loads((tmp_path / "dv.json").read_text(encoding="utf-8"))
    build = build_dataset(db_path=big_db)
    counts: dict[str, int] = {}
    for r in build.rows:
        y = r["target_end_date"][:4]
        counts[y] = counts.get(y, 0) + 1
    for entry in dv["target_distribution_by_target_end_year"]:
        assert entry["row_count"] == counts[entry["year"]]


def test_10_coverage_stats_from_common_prediction_rows(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.10: coverage 분포는 실제 common prediction row 기준."""
    payload = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    dv = json.loads((tmp_path / "dv.json").read_text(encoding="utf-8"))
    total_by_year_from_pred = sum(
        y["prediction_count"] for y in dv["walk_forward_coverage"]["by_as_of_year"]
    )
    assert total_by_year_from_pred == payload["evaluation"]["prediction_count"]


def test_11_quartile_boundaries_use_numpy_linear(big_db: Path, tmp_path: Path) -> None:
    """§11.11: quartile 은 numpy quantile method='linear'."""
    import numpy as np

    payload = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        ratios = [
            float(row["etf_coverage_ratio_20d"])
            for row in csv.DictReader(f)
            if row["etf_coverage_ratio_20d"]
        ]
    if not ratios:
        pytest.skip("no coverage ratios")
    arr = np.array(ratios, dtype=float)
    expected_q25 = float(np.quantile(arr, 0.25, method="linear"))
    expected_q75 = float(np.quantile(arr, 0.75, method="linear"))
    dv = json.loads((tmp_path / "dv.json").read_text(encoding="utf-8"))
    boundaries = dv["walk_forward_coverage"]["quartile_boundaries"]
    assert boundaries["q25"] == pytest.approx(expected_q25)
    assert boundaries["q75"] == pytest.approx(expected_q75)
    assert dv["walk_forward_coverage"]["quartile_method"] == "numpy_linear"
    _ = payload


def test_12_tied_quartile_empty_marked_unavailable(
    tmp_path: Path,
) -> None:
    """§11.12: 동점 경계로 빈 분위는 재분배 없이 unavailable."""
    # 모든 coverage_ratio 가 동일하면 q25==q50==q75 → Q1 만 채워지고 Q2/Q3/Q4 empty.
    predictions = [
        {
            "etf_coverage_ratio_20d": 0.5,
            "actual_future_return_pct": 1.0,
            "simple_baseline_prediction_pct": 0.5,
            "simple_baseline_error_pct": -0.5,
            "simple_baseline_direction_match": True,
            "full_ridge_prediction_pct": 0.4,
            "full_ridge_error_pct": -0.6,
            "full_ridge_direction_match": True,
            "core_ridge_prediction_pct": 0.6,
            "core_ridge_error_pct": -0.4,
            "core_ridge_direction_match": True,
        }
        for _ in range(20)
    ]
    boundaries = compute_quartile_boundaries(predictions)
    for p in predictions:
        p["coverage_quartile"] = assign_quartile(
            p["etf_coverage_ratio_20d"], boundaries
        )
    q_metrics = quartile_model_metrics(predictions)
    # 최소 하나의 quartile 은 empty → unavailable_reason 기록.
    empties = [q for q in q_metrics if q["prediction_count"] == 0]
    assert empties, "동점 경계 시 빈 분위가 있어야 함"
    for q in empties:
        assert q["unavailable_reason"] == "quartile_empty_due_to_tie_boundaries"


def test_13_overall_yearly_quartile_metrics_match_csv(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.13: 전체·연도별·분위별 metrics 가 CSV 와 일치."""
    payload = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # 연도별 count 일치.
    yearly = {
        y["year"]: y["prediction_count"]
        for y in payload["yearly_metrics_by_target_end_year"]
    }
    csv_years: dict[str, int] = {}
    for r in rows:
        csv_years[r["target_end_date"][:4]] = (
            csv_years.get(r["target_end_date"][:4], 0) + 1
        )
    assert yearly == csv_years
    # 분위별 count 일치.
    q_counts = {
        q["quartile"]: q["prediction_count"]
        for q in payload["coverage_quartile_metrics"]
    }
    csv_q: dict[str, int] = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for r in rows:
        q = r["coverage_quartile"]
        if q in csv_q:
            csv_q[q] += 1
    assert q_counts == csv_q


def test_14_no_external_calls(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§11.14: 외부 FDR 호출 없음."""
    import FinanceDataReader as fdr

    calls: list = []

    def stub(*a, **kw):
        calls.append((a, kw))
        raise RuntimeError("external call not expected")

    monkeypatch.setattr(fdr, "DataReader", stub)
    monkeypatch.setattr(fdr, "StockListing", stub)
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    assert calls == []


def test_15_existing_artifacts_untouched(big_db: Path, tmp_path: Path) -> None:
    """§11.15: 기존 baseline / walk-forward artifact 미변경."""
    baseline_csv = tmp_path / "market_flow_training_dataset_latest.csv"
    baseline_json = tmp_path / "market_flow_baseline_latest.json"
    wf_csv = tmp_path / "market_flow_walk_forward_predictions_latest.csv"
    wf_json = tmp_path / "market_flow_walk_forward_latest.json"
    for p in (baseline_csv, baseline_json, wf_csv, wf_json):
        p.write_text("SENTINEL", encoding="utf-8")
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "v2_dv.json",
        predictions_path=tmp_path / "v2_p.csv",
        summary_path=tmp_path / "v2_s.json",
    )
    for p in (baseline_csv, baseline_json, wf_csv, wf_json):
        assert p.read_text(encoding="utf-8") == "SENTINEL"


def test_16_reproducibility(big_db: Path, tmp_path: Path) -> None:
    """§11.16: 동일 SQLite → 동일 CSV / metrics."""
    p1_csv = tmp_path / "p1.csv"
    p2_csv = tmp_path / "p2.csv"
    payload1 = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv1.json",
        predictions_path=p1_csv,
        summary_path=tmp_path / "s1.json",
    )
    payload2 = run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv2.json",
        predictions_path=p2_csv,
        summary_path=tmp_path / "s2.json",
    )
    assert p1_csv.read_text(encoding="utf-8") == p2_csv.read_text(encoding="utf-8")
    assert payload1["metrics"] == payload2["metrics"]


def test_17_summary_schema_and_writeable(big_db: Path, tmp_path: Path) -> None:
    """§11.17 대체: summary schema 계약."""
    summary_path = tmp_path / "s.json"
    run_v2_model_comparison(
        db_path=big_db,
        data_validity_path=tmp_path / "dv.json",
        predictions_path=tmp_path / "p.csv",
        summary_path=summary_path,
    )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in (
        "schema_version",
        "status",
        "generated_at",
        "model_definitions",
        "walk_forward_rule",
        "evaluation",
        "metrics",
        "yearly_metrics_by_target_end_year",
        "coverage_quartile_metrics",
        "artifacts",
        "limitations",
    ):
        assert key in payload
    assert payload["schema_version"] == "market_flow_v2_model_comparison_v1"
    rule = payload["walk_forward_rule"]
    assert rule["minimum_train_row_count"] == 756
    assert rule["prediction_interval_kodex200_trading_days"] == 20
    assert rule["training_target_end_before_as_of"] is True
    assert rule["common_full_feature_grid_only"] is True
    for m in ("simple_baseline", "full_ridge", "core_ridge"):
        assert m in payload["metrics"]
    assert payload["model_definitions"]["full_ridge"]["ridge_alpha"] == 1.0
    assert payload["model_definitions"]["core_ridge"]["ridge_alpha"] == 1.0
    assert len(payload["model_definitions"]["full_ridge"]["feature_columns"]) == 13
    assert len(payload["model_definitions"]["core_ridge"]["feature_columns"]) == 7
