"""POC4-03 — 신호일 평가: 02A 선형 기록 완전 일치 · S′ 제외 · 선택 경로 · 여섯 모델 단면 · NO_MODEL 날 (PLAN §2).

모두 tmp_path 의 KRX 스키마 고정 DB(`tests/_krx_fixture.py`)와 02A 테스트 fixture 만 쓴다. 봉인 DB·라이브 DB 는
열지 않는다.
"""

from __future__ import annotations

import json

import pytest

from app import ml_pit_bias_eval as pit_eval
from app import ml_rf_gate_eval as ev
from app import ml_rf_gate_models as rfm
from app import ml_pit_universe as uni
from app.krx_sealed_reader import load_panel
from app.ml_baseline_snapshot import SnapshotGuardError, guard_sqlite_paths
from app.ml_research_split import SplitContractError
from app.ml_score_validity_eval import build_calendar
from tests._krx_fixture import build_sealed_db
from tests.test_poc4_02a_pit_bias import T, reasons_rows
from tests.test_poc4_02a_pit_runner import clean_rows

GAP_CODE = "B00003"


def canon(obj) -> str:
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    )


def _ctx(path, rows):
    build_sealed_db(path, rows)
    panel = load_panel(path)
    return panel, pit_eval.build_context(panel)


@pytest.fixture(scope="module")
def reasons_ctx(tmp_path_factory):
    return _ctx(tmp_path_factory.mktemp("p403r") / "krx.sqlite", reasons_rows())


@pytest.fixture(scope="module")
def clean_ctx(tmp_path_factory):
    return _ctx(tmp_path_factory.mktemp("p403c") / "krx.sqlite", clean_rows())


def _gap_rows(panel_dates, t):
    """GAP_CODE 에서 purge 구간 날짜 2개를 뺀다 — 그 종목 S 행의 label 끝(20행 뒤)이 V 시작을 넘는다."""
    fold, _ = pit_eval.date_split(panel_dates, t)
    purge = list(fold.purged_dates)
    drop = {d.replace("-", "") for d in purge[-2:]}
    rows = clean_rows()
    return {
        d: [r for r in rs if not (r["ISU_CD"] == GAP_CODE and d in drop)]
        for d, rs in rows.items()
    }


@pytest.fixture(scope="module")
def gap_ctx(tmp_path_factory, clean_ctx):
    panel, _ = clean_ctx
    t = _points(panel)[-1].signal_date
    path = tmp_path_factory.mktemp("p403g") / "krx.sqlite"
    return (*_ctx(path, _gap_rows(panel.dates, t)), t)


def _points(panel):
    return [p for p in build_calendar(panel.dates, months_ahead=1)]


# --- 02A 선형 기록 완전 일치 ---------------------------------------------------------------


@pytest.mark.parametrize("which", ["reasons", "clean"])
def test_linear_record_equals_02a_evaluate_point_all_points_both_arms(
    which, reasons_ctx, clean_ctx
):
    panel, ctx = reasons_ctx if which == "reasons" else clean_ctx
    seen_model = seen_no_model = 0
    for arm in uni.ARMS:
        codes = uni.arm_codes(panel, arm)
        for point in _points(panel):
            ref = pit_eval.evaluate_point(ctx, arm, codes, point)
            rows = ev.collect_rows(ctx, codes, point.signal_date)
            run = ev.linear_run(rows)
            got, _parts = ev.assemble_record(ctx, arm, codes, point, run)
            assert canon(got) == canon(ref), (arm, point.signal_date)
            seen_model += run.has_model
            seen_no_model += not run.has_model
    assert seen_model and seen_no_model  # 모델 있는 날 · 없는 날 모두 대조했다


def test_rows_match_02a_trainer_boundaries(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    t = _points(panel)[-1].signal_date
    rows = ev.collect_rows(ctx, codes, t)
    ref = pit_eval.train_and_score(ctx, codes, t)
    assert (len(rows.s_rows), len(rows.v_rows)) == (
        ref.train_row_count,
        ref.test_row_count,
    )
    assert {r.ticker for r in rows.inference} == set(ref.display_scores)
    assert (rows.max_target_end or None) == ref.max_target_end_date <= t
    assert max(rows.s_ends) < rows.fold.validation_start


# --- RF 학습 행 S′ · 선택 경로 ------------------------------------------------------------


def test_s_prime_drops_rows_whose_label_ends_in_validation(gap_ctx):
    panel, ctx, t = gap_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    rows = ev.collect_rows(ctx, codes, t)
    v_start = rows.fold.validation_start
    overlap = [
        r for r, e in zip(rows.s_rows, rows.s_ends) if e >= v_start
    ]  # 달력 purge 로는 못 막은 행
    assert overlap and {r.ticker for r in overlap} == {GAP_CODE}
    point = next(p for p in _points(panel) if p.signal_date == t)
    out = ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, point)
    assert out["rf"]["excluded_overlap_rows"] == len(overlap)
    assert out["rf"]["train_rows"] == len(rows.s_rows) - len(overlap)
    rf_rec = out["models"]["RF_A"]["record"]
    assert rf_rec["split"]["excluded_overlap_rows"] == len(overlap)
    assert rf_rec["max_target_end_date"] <= t
    # 선형은 S 그대로 — 02A 와 같다
    ref = pit_eval.evaluate_point(ctx, uni.ARM_PIT, codes, point)
    assert canon(out["models"]["LIN"]["record"]) == canon(ref)


def test_selection_sees_only_training_targets_of_named_v_rows(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    point = _points(panel)[-1]
    rows = ev.collect_rows(ctx, codes, point.signal_date)
    calls = []
    real = rfm.validation_ic

    def spy(preds, targets, dates):
        calls.append((list(targets), list(dates)))
        return real(preds, targets, dates)

    monkeypatch.setattr(rfm, "validation_ic", spy)
    ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, point)
    named = [
        r
        for r in rows.v_rows
        if uni.passes_name_filter(uni.name_at(panel.series[r.ticker], r.asof_date))
    ]
    expected = (
        [r.future_excess_return_20d for r in named],
        [r.asof_date for r in named],
    )
    assert len(calls) == len(rfm.CONFIG_ORDER)
    assert all(c == expected for c in calls)
    assert max(expected[1]) < point.signal_date
    assert set(expected[1]) <= set(rows.fold.validation_dates)


def test_selection_rows_apply_the_name_filter_of_that_day(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    rows = ev.collect_rows(ctx, codes, _points(panel)[-1].signal_date)
    banned = rows.v_rows[0].ticker
    monkeypatch.setattr(ev, "_name_ok", lambda name: banned not in name)
    kept = ev._selection_rows(ctx, rows.v_rows)
    assert kept and all(r.ticker != banned for r in kept)


def test_all_none_validation_ic_is_invalid(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    monkeypatch.setattr(rfm, "validation_ic", lambda *a: None)
    with pytest.raises(rfm.RfContractError, match="고르지 않는다"):
        ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, _points(panel)[-1])


def test_rf_input_assertion_catches_label_past_t(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    t = _points(panel)[-1].signal_date
    rows = ev.collect_rows(ctx, codes, t)
    rows.v_ends[0] = "2099-01-01"
    with pytest.raises(rfm.RfContractError, match="label 끝 > t"):
        ev._check_rf_inputs(rows, rows.s_rows[:1], rows.s_ends[:1], t)


# --- 여섯 모델 · 선형 대조 순서 · NO_MODEL 날 ---------------------------------------------


def test_six_models_share_cross_section_and_primary_equals_selected(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_CONTROL)
    out = ev.evaluate_point_models(ctx, uni.ARM_CONTROL, codes, _points(panel)[-1])
    assert set(out["models"]) == set(ev.MODELS)
    recs = {m: out["models"][m]["record"] for m in ev.MODELS}
    assert len({r["n_filter"] for r in recs.values()}) == 1
    assert len({tuple(r["_labels"]) for r in recs.values()}) == 1
    chosen = out["rf"]["selected"]
    assert recs["RF_PRIMARY"]["_scores"] == recs[chosen]["_scores"]
    assert recs["RF_PRIMARY"]["split"]["selected"] == chosen
    assert recs["MOM"]["split"]["status"] == "NO_TRAINING"
    assert recs["MOM"]["max_target_end_date"] is None


def test_scored_set_mismatch_stops(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    real = ev.momentum_run

    def drop_one(rows, lin):
        run = real(rows, lin)
        run.display_scores.pop(next(iter(run.display_scores)))
        return run

    monkeypatch.setattr(ev, "momentum_run", drop_one)
    with pytest.raises(SplitContractError, match="점수 대상"):
        ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, _points(panel)[-1])


def test_linear_check_runs_before_momentum_and_rf(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)

    def boom(*_a, **_k):
        raise AssertionError("선형 대조 전에 RF·모멘텀을 계산했다")

    monkeypatch.setattr(ev, "rf_runs", boom)
    monkeypatch.setattr(ev, "momentum_run", boom)

    class Stop(Exception):
        pass

    def check(_record):
        raise Stop

    with pytest.raises(Stop):
        ev.evaluate_point_models(
            ctx, uni.ARM_PIT, codes, _points(panel)[-1], check_linear=check
        )


def test_no_model_day_masks_all_six_models(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    point = _points(panel)[0]  # 달력이 짧아 선형 모델이 없는 날
    out = ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, point)
    assert out["rf"] == {"status": "NO_MODEL"}
    for m in ev.MODELS:
        rec = out["models"][m]["record"]
        assert rec["scored_count"] == 0 and rec["n_filter"] == 0, m
        assert out["models"][m]["basket"]["mean"] is None
    lin_reasons = out["models"]["LIN"]["record"]["reasons_prefilter"]
    for m in ev.MODELS:
        assert out["models"][m]["record"]["reasons_prefilter"] == lin_reasons


def test_evaluation_opens_no_database(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    with guard_sqlite_paths([]):
        ev.evaluate_point_models(ctx, uni.ARM_PIT, codes, _points(panel)[-1])
    with guard_sqlite_paths([]), pytest.raises(SnapshotGuardError):
        import sqlite3

        sqlite3.connect(":memory:")


def test_reasons_fixture_signal_day_runs_all_models(reasons_ctx):
    panel, ctx = reasons_ctx
    point = next(p for p in _points(panel) if p.signal_date == T)
    for arm in uni.ARMS:
        out = ev.evaluate_point_models(ctx, arm, uni.arm_codes(panel, arm), point)
        assert out["rf"]["status"] == "OK"
        assert out["rf"]["selected"] in rfm.CONFIG_ORDER


def test_s_prime_impossible_is_invalid_without_reviving_rows(clean_ctx):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    t = _points(panel)[-1].signal_date
    rows = ev.collect_rows(ctx, codes, t)
    lin = ev.linear_run(rows)
    rows.s_ends = [rows.fold.validation_start] * len(rows.s_ends)
    with pytest.raises(rfm.RfContractError, match="모델을 만들 수 없다"):
        ev.rf_runs(ctx, rows, lin, t)


def test_selection_rows_drop_empty_names(clean_ctx, monkeypatch):
    panel, ctx = clean_ctx
    codes = uni.arm_codes(panel, uni.ARM_PIT)
    rows = ev.collect_rows(ctx, codes, _points(panel)[-1].signal_date)
    blank = rows.v_rows[0].ticker
    real = ev.name_at
    monkeypatch.setattr(
        ev, "name_at", lambda series, d: "" if series.code == blank else real(series, d)
    )
    kept = ev._selection_rows(ctx, rows.v_rows)
    assert kept and all(r.ticker != blank for r in kept)
