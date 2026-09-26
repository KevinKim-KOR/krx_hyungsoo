"""POC4-03 — RF 동결 설정 · 입력 규칙 · 순서 고정 예측 · 설정 선택 · 모멘텀 (PLAN §1-5 · §1-6).

DB·파일을 열지 않는다(합성 행·배열만).
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

from app import ml_rf_gate_models as rfm
from app.ml_relative_upside_features import FEATURE_COLUMNS, CandidateFeatureRow

PLAN_CONFIG_JSON = (
    '{"RF_A":{"bootstrap":true,"criterion":"squared_error","max_depth":4,"max_features":1.0,'
    '"max_samples":0.25,"min_samples_leaf":0.005,"n_estimators":200,"random_state":42},'
    '"RF_B":{"bootstrap":true,"criterion":"squared_error","max_depth":8,"max_features":0.5,'
    '"max_samples":0.25,"min_samples_leaf":0.001,"n_estimators":200,"random_state":42},'
    '"RF_C":{"bootstrap":true,"criterion":"squared_error","max_depth":16,"max_features":0.5,'
    '"max_samples":0.25,"min_samples_leaf":0.0002,"n_estimators":200,"random_state":42}}'
)


def row(ticker="A", date="2014-01-02", *, base=0.01, target=0.0, **over):
    values = {c: base * (k + 1) for k, c in enumerate(FEATURE_COLUMNS)}
    values.update(over)
    return CandidateFeatureRow(
        ticker=ticker,
        asof_index=20,
        asof_date=date,
        close=100.0,
        future_excess_return_20d=target,
        **values,
    )


def synthetic(n=3000, seed=7):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, len(FEATURE_COLUMNS))).astype(np.float32)
    y = (0.3 * x[:, 0] - 0.2 * x[:, 3] + rng.normal(scale=1.0, size=n)).astype(
        np.float64
    )
    return x, y


# --- 동결 설정 ----------------------------------------------------------------------


def test_config_json_and_sha_equal_plan():
    assert rfm.config_json() == PLAN_CONFIG_JSON
    assert rfm.config_sha256() == rfm.FROZEN_CONFIG_SHA256
    rfm.assert_frozen_config()


def test_changed_config_is_refused(monkeypatch):
    monkeypatch.setitem(
        rfm.RF_CONFIGS, "RF_C", {**rfm.RF_CONFIGS["RF_C"], "max_depth": 12}
    )
    with pytest.raises(rfm.RfContractError, match="동결값"):
        rfm.assert_frozen_config()


def test_recipe_block_names_the_frozen_rules():
    rb = rfm.recipe_block()
    assert rb["feature_columns"] == list(FEATURE_COLUMNS)
    assert "(asof_date, ticker)" in rb["row_order"]
    assert "전부 None → INVALID_STOP" in rb["selection"]


# --- 입력 규칙 ----------------------------------------------------------------------


def test_row_order_key_sorts_by_date_then_ticker():
    rows = [row("B", "2014-01-03"), row("A", "2014-01-03"), row("C", "2014-01-02")]
    assert [(r.asof_date, r.ticker) for r in sorted(rows, key=rfm.row_order_key)] == [
        ("2014-01-02", "C"),
        ("2014-01-03", "A"),
        ("2014-01-03", "B"),
    ]


def test_feature_matrix_is_float32_in_feature_column_order():
    x = rfm.feature_matrix([row(base=0.01), row(base=0.02)])
    assert x.dtype == np.float32 and x.shape == (2, 7) and x.flags["C_CONTIGUOUS"]
    assert np.allclose(x[1], [0.02 * (k + 1) for k in range(7)])
    assert rfm.feature_matrix([]).shape == (0, 7)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1e40])
def test_non_finite_inputs_are_refused(bad):
    with pytest.raises(rfm.RfContractError):
        rfm.feature_matrix([row(return_5d=bad)])
    if bad != 1e40:  # float64 target 은 1e40 을 담는다
        with pytest.raises(rfm.RfContractError):
            rfm.target_vector([row(target=bad)])


def test_fit_refuses_fewer_than_two_rows():
    x, y = synthetic(n=1)
    with pytest.raises(rfm.RfContractError, match="2개 미만"):
        rfm.fit_forest("RF_A", x, y)


# --- 결정성 ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", rfm.CONFIG_ORDER)
def test_ordered_predict_is_bit_identical_across_n_jobs(monkeypatch, name):
    x, y = synthetic()
    got = {}
    for n_jobs in (1, 4, 8):
        monkeypatch.setattr(rfm, "N_JOBS", n_jobs)
        model = rfm.fit_forest(name, x, y)
        got[n_jobs] = (
            rfm.ordered_predict(model, x[:500]).tobytes(),
            rfm.forest_fingerprint(model),
        )
    assert got[1] == got[4] == got[8]


def test_ordered_predict_equals_mean_of_trees_and_handles_empty():
    x, y = synthetic(n=800)
    model = rfm.fit_forest("RF_B", x, y)
    manual = np.mean([t.predict(x[:50]) for t in model.estimators_], axis=0)
    assert np.allclose(rfm.ordered_predict(model, x[:50]), manual, rtol=0, atol=1e-15)
    assert rfm.ordered_predict(model, x[:0]).shape == (0,)


def test_input_fingerprint_changes_with_row_order():
    x, y = synthetic(n=50)
    assert rfm.input_fingerprint(x, y) == rfm.input_fingerprint(x.copy(), y.copy())
    assert rfm.input_fingerprint(
        x[::-1].copy(), y[::-1].copy()
    ) != rfm.input_fingerprint(x, y)


# --- 검증 IC · 설정 선택 ----------------------------------------------------------------


def test_validation_ic_is_mean_of_daily_spearman_skipping_undefined_days():
    preds = [1, 2, 3, 3, 2, 1, 5, 5, 5]
    targets = [1, 2, 3, 1, 2, 3, 1, 2, 3]
    dates = ["d1"] * 3 + ["d2"] * 3 + ["d3"] * 3  # d3 예측 상수 → 제외
    assert rfm.validation_ic(preds, targets, dates) == pytest.approx(0.0)
    assert rfm.validation_ic([1, 2], [1, 2], ["d1", "d1"]) == pytest.approx(1.0)
    assert rfm.validation_ic([1, 1], [1, 2], ["d1", "d1"]) is None
    assert rfm.validation_ic([], [], []) is None
    with pytest.raises(ValueError):
        rfm.validation_ic([1], [1, 2], ["d1"])


def test_select_config_uses_raw_values_without_rounding():
    sel = rfm.select_config({"RF_A": 0.1, "RF_B": 0.1 + 1e-12, "RF_C": 0.05})
    assert (sel.chosen, sel.reason) == ("RF_B", rfm.REASON_MAX)


def test_select_config_exact_tie_prefers_a_then_b():
    sel = rfm.select_config({"RF_A": 0.2, "RF_B": 0.2, "RF_C": 0.2})
    assert (sel.chosen, sel.reason) == ("RF_A", rfm.REASON_EXACT_TIE)
    sel = rfm.select_config({"RF_A": 0.1, "RF_B": 0.3, "RF_C": 0.3})
    assert (sel.chosen, sel.reason) == ("RF_B", rfm.REASON_EXACT_TIE)


def test_select_config_drops_none_and_nan():
    sel = rfm.select_config({"RF_A": None, "RF_B": math.nan, "RF_C": -0.01})
    assert (sel.chosen, sel.reason, sel.candidates) == (
        "RF_C",
        rfm.REASON_PARTIAL_NONE,
        ("RF_C",),
    )


def test_select_config_refuses_when_all_none():
    with pytest.raises(rfm.RfContractError, match="고르지 않는다"):
        rfm.select_config({"RF_A": None, "RF_B": None, "RF_C": math.nan})
    with pytest.raises(rfm.RfContractError):
        rfm.select_config({})


def test_selection_functions_take_no_evaluation_label():
    assert list(inspect.signature(rfm.select_config).parameters) == ["val_ic"]
    assert list(inspect.signature(rfm.validation_ic).parameters) == [
        "predictions",
        "targets",
        "dates",
    ]


# --- 모멘텀 ---------------------------------------------------------------------------


def test_momentum_is_raw_return_20d_higher_is_better():
    rows = [row("A", return_20d=0.05), row("B", return_20d=-0.02), row("C")]
    rows[2].return_20d = None
    got = rfm.momentum_raw_scores(rows)
    assert got == {"A": 0.05, "B": -0.02}
    assert max(got, key=got.get) == "A"


def test_forest_parallelism_uses_threads(monkeypatch):
    """RF 병렬은 스레드 — 하위 프로세스가 없어 in-process sqlite 가드 · ru_maxrss 가 유효하다."""
    import joblib
    from sklearn.ensemble import _forest

    seen = []
    real = _forest.Parallel

    def spy(*args, **kwargs):
        seen.append(kwargs)
        par = real(*args, **kwargs)
        seen.append(type(par._backend).__name__)
        return par

    monkeypatch.setattr(_forest, "Parallel", spy)
    x, y = synthetic(n=300)
    rfm.fit_forest("RF_B", x, y)
    assert seen[0].get("prefer") == "threads" and "backend" not in seen[0]
    assert seen[1] == "ThreadingBackend"
    assert type(joblib.parallel.get_active_backend()[0]).__name__ != "ThreadingBackend"
