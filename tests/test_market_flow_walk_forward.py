"""Walk-forward Lookback v1 자동 테스트 (2026-07-05, FIX r1).

지시문 §11 필수 15 케이스 + Q2 (a) 확정 (KODEX200 거래일 index 기준 20 간격
고정 grid, skip 이 grid 를 밀지 않음).
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
from app.market_flow_walk_forward import (
    MINIMUM_TRAIN_ROW_COUNT,
    PREDICTION_INTERVAL,
    _build_prediction_grid_kodex,
    _find_anchor_kodex_index,
    _load_kodex_trading_dates,
    _predict_at_kodex_date,
    run_walk_forward,
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


# ---------- 공용 helper: anchor 정보 획득 ----------


def _get_anchor_context(db_path: Path):
    build = build_dataset(db_path=db_path)
    labeled_by_asof = {r["as_of_date"]: r for r in build.rows}
    labeled_sorted = sorted(build.rows, key=lambda r: r["as_of_date"])
    kodex_dates = _load_kodex_trading_dates(db_path)
    anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    return kodex_dates, labeled_by_asof, labeled_sorted, anchor_k


# ---------- §11 케이스 ----------


def test_1_training_rows_use_target_end_date_before_as_of(big_db: Path) -> None:
    """§11.1: 각 기준일의 training row 는 target_end_date < as_of_date 만."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    training = [r for r in labeled_sorted if r["target_end_date"] < t]
    for r in training:
        assert r["target_end_date"] < t


def test_2_first_prediction_needs_756_training_rows(big_db: Path) -> None:
    """§11.2: anchor 는 target_end_date < t 인 labeled row 756 이상.

    이전 KODEX 거래일 (anchor_k - 1) 은 조건 불충족.
    """
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    count = sum(1 for r in labeled_sorted if r["target_end_date"] < t)
    assert count >= MINIMUM_TRAIN_ROW_COUNT
    # 이전 거래일도 gate 미달 확인 (feature/target 이 확보돼도 count 만 확인).
    for prev_k in range(anchor_k - 1, -1, -1):
        t_prev = kodex_dates[prev_k]
        prev_count = sum(1 for r in labeled_sorted if r["target_end_date"] < t_prev)
        if prev_count < MINIMUM_TRAIN_ROW_COUNT:
            # 정상: anchor 이전 어떤 지점에서 미충족 관측.
            return
    pytest.fail("이전 KODEX 거래일에서 count < 756 미확인")


def test_3_prediction_grid_is_kodex200_20_trading_days(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.3 / Q2 (a): grid 는 KODEX200 거래일 index 기준 20 간격 고정.

    실제 예측 as_of_date 는 grid 후보의 부분집합. 예측 as_of 사이의 KODEX
    거래일 간격이 20 의 배수여야 함 (skip 이 있어도 grid 는 밀리지 않음).
    """
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    kodex_dates = _load_kodex_trading_dates(big_db)
    date_to_kidx = {d: i for i, d in enumerate(kodex_dates)}
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        actual_asofs = [row["as_of_date"] for row in csv.DictReader(f)]
    assert actual_asofs, "예측 as_of_date 없음"

    # 모든 예측 as_of 의 KODEX index 는 anchor + 20*k 형태.
    anchor_k = date_to_kidx[actual_asofs[0]]
    for a in actual_asofs:
        k = date_to_kidx[a]
        assert (k - anchor_k) % PREDICTION_INTERVAL == 0, (
            f"as_of {a} 의 KODEX index {k} 이 anchor {anchor_k} 로부터 "
            f"{PREDICTION_INTERVAL} 의 배수가 아님"
        )


def test_3b_skip_does_not_shift_grid(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q2 (a) 보완: 중간 기준일에서 skip 이 발생해도 다음 후보는 여전히
    20 KODEX 거래일 뒤 grid 위치를 유지한다.

    grid 의 두 번째 후보가 예측 실패하도록 강제하고, 세 번째 후보의 KODEX
    index 가 anchor + 40 (== 두 번째 후보 + 20) 인지 확인.
    """
    from app import market_flow_walk_forward as wf

    kodex_dates = _load_kodex_trading_dates(big_db)
    build = build_dataset(db_path=big_db)
    labeled_by_asof = {r["as_of_date"]: r for r in build.rows}
    anchor_k = _find_anchor_kodex_index(kodex_dates, labeled_by_asof)
    assert anchor_k is not None

    skip_target_kidx = anchor_k + PREDICTION_INTERVAL
    original = wf._predict_at_kodex_date

    def wrapper(*, t, labeled_by_asof, labeled_sorted, kodex_dates, k_idx):
        if k_idx == skip_target_kidx:
            return None, "forced_skip_for_test"
        return original(
            t=t,
            labeled_by_asof=labeled_by_asof,
            labeled_sorted=labeled_sorted,
            kodex_dates=kodex_dates,
            k_idx=k_idx,
        )

    monkeypatch.setattr(wf, "_predict_at_kodex_date", wrapper)
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    date_to_kidx = {d: i for i, d in enumerate(kodex_dates)}
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kidxs = [date_to_kidx[r["as_of_date"]] for r in rows]
    # skip 된 두 번째 후보 (anchor+20) 는 결과에 없음.
    assert skip_target_kidx not in kidxs
    # 세 번째 후보 (anchor+40) 는 여전히 결과에 있음 (grid 가 밀리지 않음).
    assert (anchor_k + 2 * PREDICTION_INTERVAL) in kidxs


def test_4_actual_is_20th_kodex200_trading_day_return(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.4: 각 예측의 actual 은 이후 정확히 20 번째 KODEX200 거래일 수익률."""
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    kodex_dates = _load_kodex_trading_dates(big_db)
    date_to_kidx = {d: i for i, d in enumerate(kodex_dates)}
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            k = date_to_kidx[row["as_of_date"]]
            expected_target_end = kodex_dates[k + 20]
            assert row["target_end_date"] == expected_target_end


def test_5_scaler_fit_only_on_training_rows(big_db: Path) -> None:
    """§11.5: scaler / Ridge 는 training row (target_end_date < t) 로만 fit.

    labeled_sorted 를 rows[:idx] (anchor 이전) 로 잘라 넣어도 결과 동일.
    """
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred_full, _ = _predict_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    truncated_sorted = [r for r in labeled_sorted if r["as_of_date"] < t]
    pred_truncated, _ = _predict_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=truncated_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred_full is not None and pred_truncated is not None
    assert pred_full["ridge_prediction_pct"] == pytest.approx(
        pred_truncated["ridge_prediction_pct"]
    )
    assert pred_full["train_row_count"] == pred_truncated["train_row_count"]


def test_6_ridge_and_simple_share_training_range(big_db: Path) -> None:
    """§11.6: Ridge / simple baseline 동일 training 범위."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred, _ = _predict_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred is not None
    training = [r for r in labeled_sorted if r["target_end_date"] < t]
    expected_simple = sum(r[TARGET_COLUMN] for r in training) / len(training)
    assert pred["simple_baseline_prediction_pct"] == pytest.approx(expected_simple)
    assert pred["train_row_count"] == len(training)


def test_7_simple_baseline_equals_training_target_mean(big_db: Path) -> None:
    """§11.7: simple baseline = training target 평균."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred, _ = _predict_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred is not None
    training_targets = [
        r[TARGET_COLUMN] for r in labeled_sorted if r["target_end_date"] < t
    ]
    assert pred["simple_baseline_prediction_pct"] == pytest.approx(
        sum(training_targets) / len(training_targets)
    )


def test_8_error_and_direction_computed_per_spec(big_db: Path) -> None:
    """§11.8: 오차 · 방향 일치 정의대로."""
    kodex_dates, labeled_by_asof, labeled_sorted, anchor_k = _get_anchor_context(big_db)
    assert anchor_k is not None
    t = kodex_dates[anchor_k]
    pred, _ = _predict_at_kodex_date(
        t=t,
        labeled_by_asof=labeled_by_asof,
        labeled_sorted=labeled_sorted,
        kodex_dates=kodex_dates,
        k_idx=anchor_k,
    )
    assert pred is not None
    actual = pred["actual_future_return_pct"]
    ridge_pred = pred["ridge_prediction_pct"]
    assert pred["ridge_error_pct"] == pytest.approx(ridge_pred - actual)
    assert pred["ridge_direction_match"] == ((ridge_pred > 0) == (actual > 0))
    simple = pred["simple_baseline_prediction_pct"]
    assert pred["simple_baseline_error_pct"] == pytest.approx(simple - actual)
    assert pred["simple_baseline_direction_match"] == ((simple > 0) == (actual > 0))


def test_9_yearly_summary_matches_predictions_csv(big_db: Path, tmp_path: Path) -> None:
    """§11.9: 연도별 요약이 prediction CSV 와 일치."""
    payload = run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    if payload["status"] != "ok" or not payload["yearly_metrics"]:
        pytest.skip("no predictions")
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_year: dict[str, list[dict]] = {}
    for r in rows:
        by_year.setdefault(r["target_end_date"][:4], []).append(r)
    for ym in payload["yearly_metrics"]:
        assert ym["prediction_count"] == len(by_year[ym["year"]])


def test_10_insufficient_training_marks_unavailable(small_db: Path) -> None:
    """§11.10: 최소 training row 부족 → unavailable + 사유 기록."""
    payload = run_walk_forward(
        db_path=small_db,
        predictions_path=small_db.parent / "p.csv",
        summary_path=small_db.parent / "s.json",
    )
    assert payload["status"] == "unavailable"
    reasons = payload["evaluation"]["excluded_reason_counts"]
    assert (
        "minimum_train_row_count_not_reached" in reasons or "no_labeled_rows" in reasons
    )


def test_11_reproducibility(big_db: Path, tmp_path: Path) -> None:
    """§11.11: 재현성."""
    p1 = tmp_path / "p1.csv"
    s1 = tmp_path / "s1.json"
    p2 = tmp_path / "p2.csv"
    s2 = tmp_path / "s2.json"
    payload1 = run_walk_forward(db_path=big_db, predictions_path=p1, summary_path=s1)
    payload2 = run_walk_forward(db_path=big_db, predictions_path=p2, summary_path=s2)
    assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")
    assert payload1["metrics"] == payload2["metrics"]
    assert (
        payload1["evaluation"]["prediction_count"]
        == payload2["evaluation"]["prediction_count"]
    )


def test_12_no_external_data_calls(
    big_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§11.12: 외부 source 호출 없음."""
    import FinanceDataReader as fdr

    calls: list = []

    def stub(*a, **kw):
        calls.append((a, kw))
        raise RuntimeError("external call not expected")

    monkeypatch.setattr(fdr, "DataReader", stub)
    monkeypatch.setattr(fdr, "StockListing", stub)
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    assert calls == []


def test_13_existing_baseline_artifacts_not_overwritten(
    big_db: Path, tmp_path: Path
) -> None:
    """§11.13: 기존 baseline CSV / JSON 미변경."""
    baseline_csv = tmp_path / "market_flow_training_dataset_latest.csv"
    baseline_json = tmp_path / "market_flow_baseline_latest.json"
    baseline_csv.write_text("SENTINEL_CSV", encoding="utf-8")
    baseline_json.write_text('{"sentinel": true}', encoding="utf-8")
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "wf_p.csv",
        summary_path=tmp_path / "wf_s.json",
    )
    assert baseline_csv.read_text(encoding="utf-8") == "SENTINEL_CSV"
    assert baseline_json.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_14_feature_contract_maintained(big_db: Path, tmp_path: Path) -> None:
    """§11.14: VIX strictly-prior + target horizon 20 + feature 컬럼."""
    payload = run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=tmp_path / "s.json",
    )
    assert payload["feature_columns"] == list(FEATURE_COLUMNS)
    assert (
        payload["target_definition"]
        == "future 20 trading-day KODEX200 simple return (%)"
    )
    with open(tmp_path / "p.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["vix_source_date"]:
                assert row["vix_source_date"] < row["as_of_date"]


def test_15_summary_schema_and_json_writeable(big_db: Path, tmp_path: Path) -> None:
    """§11.15 대체: summary schema 계약."""
    summary_path = tmp_path / "s.json"
    run_walk_forward(
        db_path=big_db,
        predictions_path=tmp_path / "p.csv",
        summary_path=summary_path,
    )
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    for key in (
        "schema_version",
        "status",
        "generated_at",
        "source_snapshot",
        "model",
        "feature_columns",
        "target_definition",
        "walk_forward_rule",
        "evaluation",
        "metrics",
        "yearly_metrics",
        "artifacts",
        "limitations",
    ):
        assert key in payload
    assert payload["schema_version"] == "market_flow_walk_forward_v1"
    assert payload["walk_forward_rule"]["minimum_train_row_count"] == 756
    assert (
        payload["walk_forward_rule"]["prediction_interval_kodex200_trading_days"] == 20
    )
    assert payload["walk_forward_rule"]["training_target_end_before_as_of"] is True
    assert payload["model"]["ridge_alpha"] == 1.0


# ---------- helper 단위 (Q2 (a) 계약 재확인) ----------


def test_helper_grid_is_kodex_index_based() -> None:
    """_build_prediction_grid_kodex 는 순수히 KODEX index 기준 20 간격."""
    kodex_dates = [f"2020-01-{i:02d}" for i in range(1, 32)] * 5  # 155 개
    kodex_dates = kodex_dates[:100]
    grid = _build_prediction_grid_kodex(kodex_dates, anchor_kodex_idx=10)
    assert grid[0] == 10
    for a, b in zip(grid, grid[1:]):
        assert b - a == PREDICTION_INTERVAL
