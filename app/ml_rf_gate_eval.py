"""POC4-03 — 신호일 하나 × arm 하나: 행 수집 · 선형 · 모멘텀 · RF A/B/C · RF_PRIMARY · 기록 조립 (PLAN §2-1~§2-3).

- 행 수집·선형 학습·기록 조립은 02A(`app/ml_pit_bias_eval.py` `train_and_score` · `evaluate_point`)와 같은 규칙이다.
  02A 모듈은 점수를 넣을 인자가 없고 행을 돌려주지 않아 여기서 같은 순서로 다시 조립한다 — 선형 기록이 02A 기록과
  canonical 텍스트까지 같은지 러너가 날짜마다 대조하고(§2-3), 테스트가 02A `evaluate_point` 와 대조한다.
- 선형이 모델을 만들지 못한 날은 여섯 모델 모두 점수를 가린다(NO_MODEL 날 규칙).
- RF 는 S′(= S − label 끝 ≥ V 시작) 로만 학습하고, 선택은 V 의 학습 target 만 본다 — 평가 label 은 선택 경로에 없다.
- 여섯 모델의 `rows_filter`·`rows_all`·`rows_sens` (종목, label) 순서열이 같지 않으면 멈춘다.

DB·파일에 접근하지 않는다. 고정 모듈·02A 모듈은 import 만 한다.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from app import ml_rf_gate_models as rfm
from app.ml_pit_bias_eval import (
    EPOCHS,
    LEARNING_RATE,
    SEED,
    SPLIT_HORIZON,
    PanelContext,
    ScoreRun,
    date_split,
)
from app.ml_pit_universe import (
    ARM_CONTROL,
    BENCHMARK_UNAVAILABLE,
    NOT_YET_LISTED,
    benchmark_pair,
    classify_pair,
    empty_reasons,
    has_volume,
    is_eligible,
    name_at,
    passes_name_filter,
)
from app.ml_relative_upside_features import (
    build_feature_rows_for_ticker,
    is_complete_for_inference,
    is_complete_for_training,
)
from app.ml_relative_upside_model import (
    normalize_to_display_scores,
    predict_raw_scores,
    train_walk_forward,
)
from app.ml_research_split import SelectionFold, SplitContractError
from app.ml_rf_gate_report import partial_top
from app.ml_score_validity_eval import (
    PHASE_EVALUATION,
    QUANTILE_BUCKETS,
    TOP_DECILE_FRACTION,
    RebalancePoint,
)
from app.ml_score_validity_metrics import (
    mean,
    median,
    quantile_means,
    spearman,
    top_fraction,
    win_rate,
)

LIN, MOM, RF_PRIMARY = "LIN", "MOM", "RF_PRIMARY"
MODELS = (LIN, MOM, *rfm.CONFIG_ORDER, RF_PRIMARY)
NO_MODEL_DAY = "선형 모델 없음 — 여섯 모델 모두 점수를 가린다"


@dataclass
class PointRows:
    """신호일 t 의 학습·검증·추론 행 (02A `train_and_score` 와 같은 수집)."""

    split: dict
    fold: Optional[SelectionFold]
    benchmark_ok: bool
    max_input: Optional[str]
    s_rows: list = field(default_factory=list)
    s_ends: list = field(default_factory=list)
    v_rows: list = field(default_factory=list)
    v_ends: list = field(default_factory=list)
    inference: list = field(default_factory=list)
    max_target_end: str = ""


def collect_rows(ctx: PanelContext, codes: tuple[str, ...], t: str) -> PointRows:
    panel = ctx.panel
    kodex = dict(ctx.bench.chain_history(upto=t))
    present = panel.present(t)
    max_input = max(kodex) if kodex else None
    if t not in kodex:
        split = {"status": "NO_MODEL", "reason": BENCHMARK_UNAVAILABLE}
        return PointRows(split, None, False, max_input)
    fold, split = date_split(panel.dates, t)
    if fold is None:
        return PointRows(split, None, True, max_input)
    out = PointRows(split, fold, True, max_input)
    train_set, val_set = set(fold.train_dates), set(fold.validation_dates)
    purged_set = set(fold.purged_dates)
    for code in codes:
        history = panel.series[code].chain_history(upto=t)
        if not history:
            continue
        if out.max_input is None or history[-1][0] > out.max_input:
            out.max_input = history[-1][0]
        rows = build_feature_rows_for_ticker(
            code, history, kodex, include_future_target=True
        )
        for r in rows:
            if not is_complete_for_training(r):
                continue
            end = None
            if r.asof_date in train_set:
                end = history[r.asof_index + SPLIT_HORIZON][0]
                out.s_rows.append(r)
                out.s_ends.append(end)
            elif r.asof_date in val_set:
                end = history[r.asof_index + SPLIT_HORIZON][0]
                out.v_rows.append(r)
                out.v_ends.append(end)
            elif r.asof_date in purged_set:
                continue
            else:
                raise SplitContractError(f"분할 밖 학습 행: {code} {r.asof_date}")
            if end > out.max_target_end:
                out.max_target_end = end
        last = rows[-1] if rows else None
        if (
            code in present
            and last is not None
            and last.asof_date == t
            and is_complete_for_inference(last)
        ):
            out.inference.append(last)
    return out


# --- 선형 (02A 호출 그대로) ------------------------------------------------------------


def _check_trainer(tr, s_rows: list, fold: SelectionFold) -> None:
    """고정 trainer 의 행 비율 분할이 날짜 경계와 정확히 같은지 (02A 와 같은 검사)."""
    last_train = max(r.asof_date for r in s_rows)
    problems = []
    if tr.train_row_count != len(s_rows):
        problems.append(f"train_row_count {tr.train_row_count} ≠ |S| {len(s_rows)}")
    if tr.train_date_range[1] != last_train:
        problems.append(f"마지막 학습일 {tr.train_date_range[1]} ≠ {last_train}")
    if not tr.train_date_range[1] < fold.validation_start:
        problems.append(f"마지막 학습일 {tr.train_date_range[1]} ≥ 검증 시작")
    if not tr.test_date_range[0] >= fold.validation_start:
        problems.append(f"첫 검증 행 {tr.test_date_range[0]} < 검증 시작")
    if problems:
        raise SplitContractError("trainer 경계 불일치: " + " · ".join(problems))


def linear_run(rows: PointRows) -> ScoreRun:
    if not rows.benchmark_ok:
        return ScoreRun({}, rows.split, False, False, 0, 0, rows.max_input, None)
    if rows.fold is None:
        return ScoreRun({}, rows.split, False, True, 0, 0, rows.max_input, None)
    s_rows, v_rows = rows.s_rows, rows.v_rows
    split = {**rows.split, "train_rows": len(s_rows), "validation_rows": len(v_rows)}
    end = rows.max_target_end or None
    if not s_rows or not v_rows:
        split = {**split, "status": "NO_MODEL", "reason": "학습 행 또는 검증 행 0"}
        return ScoreRun({}, split, False, True, 0, 0, rows.max_input, end)
    ratio = (len(s_rows) + 0.5) / (len(s_rows) + len(v_rows))
    model, tr = train_walk_forward(
        s_rows + v_rows,
        train_split_ratio=ratio,
        epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        seed=SEED,
    )
    _check_trainer(tr, s_rows, rows.fold)
    split = {
        **split,
        "train_split_ratio": ratio,
        "trainer_train_row_count": tr.train_row_count,
        "trainer_test_row_count": tr.test_row_count,
        "trainer_train_date_range": list(tr.train_date_range),
        "trainer_test_date_range": list(tr.test_date_range),
        "last_train_date": tr.train_date_range[1],
        "device": tr.device_name,
        "cuda_available": tr.cuda_available,
    }
    raw = predict_raw_scores(model, rows.inference) if model is not None else {}
    return ScoreRun(
        display_scores=normalize_to_display_scores(raw),
        split=split,
        has_model=model is not None,
        benchmark_ok=True,
        train_row_count=tr.train_row_count,
        test_row_count=tr.test_row_count,
        max_input_date=rows.max_input,
        max_target_end_date=end,
    )


# --- 모멘텀 · RF ---------------------------------------------------------------------


def _masked(lin: ScoreRun, basis: str) -> ScoreRun:
    """선형이 모델을 못 만든 날 — 같은 has_model·benchmark_ok 로 점수를 가린다."""
    split = {"status": "NO_MODEL", "reason": NO_MODEL_DAY, "basis": basis}
    return ScoreRun({}, split, False, lin.benchmark_ok, 0, 0, lin.max_input_date, None)


def momentum_run(rows: PointRows, lin: ScoreRun) -> ScoreRun:
    if not lin.has_model:
        return _masked(lin, "MOMENTUM")
    raw = rfm.momentum_raw_scores(rows.inference)
    split = {"status": "NO_TRAINING", "basis": "t 행 return_20d"}
    return ScoreRun(
        normalize_to_display_scores(raw), split, True, True, 0, 0, rows.max_input, None
    )


@functools.lru_cache(maxsize=None)
def _name_ok(name: str) -> bool:
    return passes_name_filter(name)


def _selection_rows(ctx: PanelContext, v_rows: list) -> list:
    """선택용 V — 그 V 날짜의 이름이 있고 이름 필터를 통과한 행 (7 feature · target 은 이미 있다)."""
    series = ctx.panel.series
    out = []
    for r in v_rows:
        name = name_at(series[r.ticker], r.asof_date)
        if name and _name_ok(
            name
        ):  # 빈 이름은 평가 쪽처럼 빼고(HISTORICAL_FILTER_UNAVAILABLE)
            out.append(r)
    return out


def _check_rf_inputs(rows: PointRows, s_prime, s_ends, t: str) -> None:
    fold = rows.fold
    v_start, val_dates = fold.validation_start, set(fold.validation_dates)
    problems = []
    if s_prime and max(r.asof_date for r in s_prime) >= v_start:
        problems.append("S′ 날짜 ≥ V 시작")
    if s_ends and max(s_ends) >= v_start:
        problems.append("S′ label 끝 ≥ V 시작")
    if any(r.asof_date not in val_dates for r in rows.v_rows):
        problems.append("V 날짜가 검증 구간 밖")
    ends = [*s_ends, *rows.v_ends]
    if ends and max(ends) > t:
        problems.append("label 끝 > t")
    if any(r.asof_date == t for r in (*s_prime, *rows.v_rows)):
        problems.append("t 행이 학습·검증에 있다")
    if problems:
        raise rfm.RfContractError("RF 입력 단언 위반: " + " · ".join(problems))


def rf_runs(
    ctx: PanelContext, rows: PointRows, lin: ScoreRun, t: str
) -> tuple[dict, dict]:
    """RF A·B·C → 선택 → RF_PRIMARY. 반환: ({모델: ScoreRun}, RF 메타)."""
    names = (*rfm.CONFIG_ORDER, RF_PRIMARY)
    if not lin.has_model:
        return {n: _masked(lin, n) for n in names}, {"status": "NO_MODEL"}
    v_start = rows.fold.validation_start
    kept = [(r, e) for r, e in zip(rows.s_rows, rows.s_ends) if e < v_start]
    excluded = len(rows.s_rows) - len(kept)
    kept.sort(key=lambda p: rfm.row_order_key(p[0]))
    s_prime, s_ends = [p[0] for p in kept], [p[1] for p in kept]
    if len(s_prime) < 2:
        raise rfm.RfContractError(f"S′ {len(s_prime)}행 — 모델을 만들 수 없다")
    _check_rf_inputs(rows, s_prime, s_ends, t)
    xs, ys = rfm.feature_matrix(s_prime), rfm.target_vector(s_prime)
    sel_rows = _selection_rows(ctx, rows.v_rows)
    xv, yv = rfm.feature_matrix(sel_rows), rfm.target_vector(sel_rows)
    xt = rfm.feature_matrix(rows.inference)
    tickers = [r.ticker for r in rows.inference]
    end = max([*s_ends, *rows.v_ends]) if (s_ends or rows.v_ends) else None
    val_ic, raw_t, forests = {}, {}, {}
    for name in rfm.CONFIG_ORDER:
        model = rfm.fit_forest(name, xs, ys)
        pv = rfm.ordered_predict(model, xv)
        val_ic[name] = rfm.validation_ic(
            pv.tolist(), yv.tolist(), [r.asof_date for r in sel_rows]
        )
        raw_t[name] = dict(zip(tickers, rfm.ordered_predict(model, xt).tolist()))
        forests[name] = rfm.forest_fingerprint(model)
        del model
    selection = rfm.select_config(val_ic)
    base_split = {
        "status": "OK",
        "basis": "RF · S′ = S − (label 끝 ≥ V 시작)",
        "split_fingerprint": rows.split.get("split_fingerprint"),
        "validation_start": v_start,
        "train_rows": len(s_prime),
        "excluded_overlap_rows": excluded,
        "validation_rows": len(rows.v_rows),
        "selection_rows": len(sel_rows),
    }
    runs = {}
    for name in rfm.CONFIG_ORDER:
        runs[name] = ScoreRun(
            normalize_to_display_scores(raw_t[name]),
            {**base_split, "config": name},
            True,
            True,
            len(s_prime),
            len(rows.v_rows),
            rows.max_input,
            end,
        )
    chosen = runs[selection.chosen]
    runs[RF_PRIMARY] = replace(
        chosen, split={**base_split, "config": RF_PRIMARY, "selected": selection.chosen}
    )
    meta = {
        "status": "OK",
        "val_ic": val_ic,
        "selected": selection.chosen,
        "selection_reason": selection.reason,
        "excluded_overlap_rows": excluded,
        "train_rows": len(s_prime),
        "selection_rows": len(sel_rows),
        "input_sha256": rfm.input_fingerprint(xs, ys),
        "forest_sha256": forests,
    }
    return runs, meta


# --- 기록 조립 (02A `evaluate_point` 와 같은 규칙 · 점수만 주입) --------------------------


def _top_block(rows: list[tuple[str, float, float]]) -> dict:
    top = top_fraction(rows, TOP_DECILE_FRACTION)
    values = [r[2] for r in top]
    return {"tickers": [r[0] for r in top], "values": values, "mean": mean(values)}


def assemble_record(
    ctx: PanelContext,
    arm: str,
    codes: tuple[str, ...],
    point: RebalancePoint,
    run: ScoreRun,
) -> tuple[dict, dict]:
    """(02A 스키마 기록, {filter·all·sens 행}) — 기록은 02A `evaluate_point` 와 같은 키·값."""
    panel, t = ctx.panel, point.signal_date
    if t not in ctx.day_index:
        raise ValueError(f"거래일이 아닌 신호일: {t}")
    universe = [c for c in codes if c in panel.present(t)]
    bench = benchmark_pair(
        ctx.bench, ctx.bench_facts, point.entry_date, point.exit_date
    )
    pre, post = empty_reasons(), empty_reasons()
    if arm == ARM_CONTROL:
        pre[NOT_YET_LISTED] = len(codes) - len(universe)
    denom = zero_volume = delisted_scored = delisted_eval = 0
    rows_filter: list[tuple[str, float, float]] = []
    rows_all: list[tuple[str, float, float]] = []
    rows_sens: list[tuple[str, float, float]] = []
    for code in universe:
        series, facts = panel.series[code], ctx.facts[code]
        score = run.display_scores.get(code)
        if not run.benchmark_ok:
            outcome_reason, label, sens = BENCHMARK_UNAVAILABLE, None, None
        else:
            outcome = classify_pair(
                series,
                facts,
                point,
                bench,
                has_model=run.has_model,
                scored=score is not None,
            )
            outcome_reason, label, sens = (
                outcome.reason,
                outcome.label,
                outcome.sensitivity_label,
            )
        in_filter = passes_name_filter(name_at(series, t))
        if outcome_reason is not None:
            pre[outcome_reason] += 1
            if in_filter:
                post[outcome_reason] += 1
        eligible = in_filter and is_eligible(facts, t, ctx.day_index)
        denom += eligible
        if score is None:
            continue
        zero_volume += not has_volume(series.volume[series.index[t]])
        delisted = code not in ctx.final_present
        delisted_scored += delisted
        if label is not None:
            rows_all.append((code, score, label))
            if eligible:
                rows_filter.append((code, score, label))
                delisted_eval += delisted
        if eligible and sens is not None:
            rows_sens.append((code, score, sens))

    top = top_fraction(rows_filter, TOP_DECILE_FRACTION)
    top_values = [r[2] for r in top]
    sens_top = _top_block(rows_sens)
    numer = len(rows_filter)
    record = {
        "arm": arm,
        "phase": PHASE_EVALUATION,
        "signal_date": t,
        "entry_date": point.entry_date,
        "exit_date": point.exit_date,
        "next_signal_date": point.next_signal_date,
        "universe_count": len(universe),
        "split": run.split,
        "train_row_count": run.train_row_count,
        "test_row_count": run.test_row_count,
        "scored_count": len(run.display_scores),
        "zero_volume_scored": zero_volume,
        "delisted_scored": delisted_scored,
        "coverage_denominator": denom,
        "coverage_numerator": numer,
        "coverage": (numer / denom) if denom else None,
        "reasons_prefilter": pre,
        "reasons_filtered": post,
        "ic_filter": spearman([r[1] for r in rows_filter], [r[2] for r in rows_filter]),
        "ic_all": spearman([r[1] for r in rows_all], [r[2] for r in rows_all]),
        "n_filter": numer,
        "n_all": len(rows_all),
        "quantile_means": {
            str(k): v for k, v in quantile_means(rows_filter, QUANTILE_BUCKETS).items()
        },
        "top_decile_tickers": [r[0] for r in top],
        "top_decile_values": top_values,
        "top_decile_mean": mean(top_values),
        "top_decile_median": median(top_values),
        "top_decile_win_rate": win_rate(top_values),
        "delisted_in_eval": delisted_eval,
        "sensitivity": {
            "label_basis": "OFFICIAL_REFERENCE_SENSITIVITY",
            "n": len(rows_sens),
            "ic": spearman([r[1] for r in rows_sens], [r[2] for r in rows_sens]),
            "top_decile_tickers": sens_top["tickers"],
            "top_decile_values": sens_top["values"],
            "top_decile_mean": sens_top["mean"],
        },
        "max_input_date": run.max_input_date,
        "max_target_end_date": run.max_target_end_date,
        "_scores": [r[1] for r in rows_filter],
        "_labels": [r[2] for r in rows_filter],
    }
    return record, {"filter": rows_filter, "all": rows_all, "sens": rows_sens}


def _cross_section(rows: dict) -> tuple:
    return tuple(
        tuple((c, lab) for c, _s, lab in rows[k]) for k in ("filter", "all", "sens")
    )


def evaluate_point_models(
    ctx: PanelContext,
    arm: str,
    codes: tuple[str, ...],
    point: RebalancePoint,
    *,
    check_linear: Optional[Callable[[dict], None]] = None,
) -> dict:
    """여섯 모델의 날짜 기록. `check_linear(선형 기록)` 은 모멘텀·RF 계산 **전에** 부른다(불일치면 예외)."""
    t = point.signal_date
    rows = collect_rows(ctx, codes, t)
    lin = linear_run(rows)
    lin_record, lin_rows = assemble_record(ctx, arm, codes, point, lin)
    if check_linear is not None:
        check_linear(lin_record)
    runs = {LIN: lin, MOM: momentum_run(rows, lin)}
    rf, rf_meta = rf_runs(ctx, rows, lin, t)
    runs.update(rf)
    reference = _cross_section(lin_rows)
    models: dict[str, dict] = {}
    for name in MODELS:
        record, parts = (
            (lin_record, lin_rows)
            if name == LIN
            else assemble_record(ctx, arm, codes, point, runs[name])
        )
        if set(runs[name].display_scores) != set(lin.display_scores):
            raise SplitContractError(f"{t} {name} 점수 대상이 선형과 다르다")
        if _cross_section(parts) != reference:
            raise SplitContractError(f"{t} {name} 평가 단면이 선형과 다르다")
        models[name] = {
            "record": record,
            "basket": partial_top(parts["filter"], TOP_DECILE_FRACTION),
            "sensitivity_basket": partial_top(parts["sens"], TOP_DECILE_FRACTION),
        }
    return {"models": models, "rf": rf_meta}
