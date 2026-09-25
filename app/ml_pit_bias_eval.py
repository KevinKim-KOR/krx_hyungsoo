"""POC4-02A — 신호일 하나 × arm 하나 평가 (PLAN §4 · §6 구현 정의 · 설계자 판정 A1·A2).

순서: t 절단 이력(연결 계열) → 고정 feature 함수 → 날짜 기준 분할(`make_selection_folds`, purge 20)
→ 고정 trainer `train_walk_forward` 에 학습일 행 S + 검증일 행 V 만 넘기고 호출별 비율
`(|S|+0.5)/(|S|+|V|)` → t 행 추론 점수 → 제외 사유 · 주 label · 민감도 label → 날짜별 기록.

- 학습·추론 입력은 t 이하 · 학습 target 끝은 t 이하 (`max_input_date` · `max_target_end_date` 로 기록).
- 점수는 t 에 행이 있고 t 행 feature 가 완전한 종목만 — 폐지 ETF 의 옛 행으로 점수 매기지 않는다.
- fold 는 달력(`panel.dates` ≤ t)에만 의존한다 → 두 arm 의 날짜 경계·purge 가 같다.
- 고정 모듈(`ml_relative_upside_features` · `ml_relative_upside_model`)은 import 만 한다.

DB·파일에 접근하지 않는다.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Optional

from app.krx_sealed_reader import CodeSeries, SealedPanel
from app.ml_pit_universe import (
    ARM_CONTROL,
    BENCHMARK_UNAVAILABLE,
    NOT_YET_LISTED,
    SeriesFacts,
    benchmark_pair,
    build_facts,
    classify_pair,
    empty_reasons,
    has_volume,
    is_eligible,
    name_at,
    passes_name_filter,
)
from app.ml_relative_upside_features import (
    FUTURE_HORIZON_20D,
    RETURN_LOOKBACK_20D,
    CandidateFeatureRow,
    build_feature_rows_for_ticker,
    is_complete_for_inference,
    is_complete_for_training,
)
from app.ml_relative_upside_model import (
    DEFAULT_EPOCHS,
    DEFAULT_LEARNING_RATE,
    DEFAULT_RANDOM_SEED,
    normalize_to_display_scores,
    predict_raw_scores,
    train_walk_forward,
)
from app.ml_research_split import (
    SelectionFold,
    SplitContractError,
    make_selection_folds,
    split_fingerprint,
)
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

# --- 연구 recipe 상수 (E2 모델 클래스·lr·epoch·seed 그대로 · 분할만 A2) ------------------
EPOCHS = DEFAULT_EPOCHS
LEARNING_RATE = DEFAULT_LEARNING_RATE
SEED = DEFAULT_RANDOM_SEED
TRAIN_SHARE = 0.8  # 검증일 수 = N − int(0.8N) (구현 정의 3)
SPLIT_HORIZON = FUTURE_HORIZON_20D  # purge = label 20거래일
FEATURE_WARMUP_DAYS = RETURN_LOOKBACK_20D  # 표본일 = 달력 index ≥ 20
MIN_SAMPLE_DAYS = 2


@dataclass
class PanelContext:
    """panel 한 번 읽은 뒤 날짜마다 다시 쓰는 색인."""

    panel: SealedPanel
    day_index: dict[str, int]
    facts: dict[str, SeriesFacts]
    final_present: frozenset
    bench: CodeSeries = field(repr=False)
    bench_facts: SeriesFacts = field(repr=False)


def build_context(panel: SealedPanel) -> PanelContext:
    bench = panel.benchmark()
    return PanelContext(
        panel=panel,
        day_index={d: i for i, d in enumerate(panel.dates)},
        facts={code: build_facts(s) for code, s in panel.series.items()},
        final_present=panel.present(panel.final_date),
        bench=bench,
        bench_facts=build_facts(bench),
    )


# --- 날짜 기준 분할 (A2 · (a)안) ---------------------------------------------------


def date_split(
    dates: list[str], signal_date: str
) -> tuple[Optional[SelectionFold], dict]:
    """달력 = v1 거래일 ≤ t · 표본일 = index ≥ 20 · walk-forward 1 fold · purge 20."""
    cal = dates[: bisect.bisect_right(dates, signal_date)]
    sample = cal[FEATURE_WARMUP_DAYS:]
    n = max(0, len(cal) - FEATURE_WARMUP_DAYS - SPLIT_HORIZON)
    info: dict = {
        "calendar_days": len(cal),
        "label_complete_sample_days": n,
        "validation_days": None,
    }
    if n < MIN_SAMPLE_DAYS:
        return None, {
            **info,
            "status": "NO_MODEL",
            "reason": "label 완성 표본일 2개 미만",
        }
    validation_days = n - int(TRAIN_SHARE * n)
    fold = make_selection_folds(
        cal,
        sample,
        n_folds=1,
        validation_days=validation_days,
        horizon=SPLIT_HORIZON,
    )[0]
    return fold, {
        **info,
        "status": "OK",
        "reason": None,
        "validation_days": validation_days,
        "train_days": len(fold.train_dates),
        "train_first_date": fold.train_dates[0] if fold.train_dates else None,
        "train_last_date": fold.train_dates[-1] if fold.train_dates else None,
        "purged_days": len(fold.purged_dates),
        "purged_first_date": fold.purged_dates[0] if fold.purged_dates else None,
        "purged_last_date": fold.purged_dates[-1] if fold.purged_dates else None,
        "validation_start": fold.validation_start,
        "validation_end": fold.validation_end,
        "split_fingerprint": split_fingerprint([fold]),
    }


# --- 학습 · 점수 ----------------------------------------------------------------


@dataclass
class ScoreRun:
    display_scores: dict[str, float]
    split: dict
    has_model: bool
    benchmark_ok: bool
    train_row_count: int
    test_row_count: int
    max_input_date: Optional[str]
    max_target_end_date: Optional[str]


def _check_trainer(tr, s_rows: list, fold: SelectionFold) -> None:
    """고정 trainer 의 행 비율 분할이 날짜 경계와 정확히 같은지 (PLAN §2-13 ③)."""
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


def train_and_score(
    ctx: PanelContext, codes: tuple[str, ...], signal_date: str
) -> ScoreRun:
    """arm 종목 전부의 t 절단 이력으로 학습 → t 에 행이 있는 종목의 t 행 점수."""
    panel = ctx.panel
    kodex = dict(ctx.bench.chain_history(upto=signal_date))
    present = panel.present(signal_date)
    max_input = max(kodex) if kodex else None
    if signal_date not in kodex:
        split = {"status": "NO_MODEL", "reason": BENCHMARK_UNAVAILABLE}
        return ScoreRun({}, split, False, False, 0, 0, max_input, None)
    fold, split = date_split(panel.dates, signal_date)
    if fold is None:
        return ScoreRun({}, split, False, True, 0, 0, max_input, None)

    train_set, val_set = set(fold.train_dates), set(fold.validation_dates)
    purged_set = set(fold.purged_dates)
    s_rows: list[CandidateFeatureRow] = []
    v_rows: list[CandidateFeatureRow] = []
    inference: list[CandidateFeatureRow] = []
    max_target_end = ""
    for code in codes:
        history = panel.series[code].chain_history(upto=signal_date)
        if not history:
            continue
        if max_input is None or history[-1][0] > max_input:
            max_input = history[-1][0]
        rows = build_feature_rows_for_ticker(
            code, history, kodex, include_future_target=True
        )
        for r in rows:
            if not is_complete_for_training(r):
                continue
            if r.asof_date in train_set:
                s_rows.append(r)
            elif r.asof_date in val_set:
                v_rows.append(r)
            elif r.asof_date in purged_set:
                continue
            else:
                raise SplitContractError(f"분할 밖 학습 행: {code} {r.asof_date}")
            end = history[r.asof_index + SPLIT_HORIZON][0]
            if end > max_target_end:
                max_target_end = end
        last = rows[-1] if rows else None
        if (
            code in present
            and last is not None
            and last.asof_date == signal_date
            and is_complete_for_inference(last)
        ):
            inference.append(last)

    split = {**split, "train_rows": len(s_rows), "validation_rows": len(v_rows)}
    if not s_rows or not v_rows:
        split = {**split, "status": "NO_MODEL", "reason": "학습 행 또는 검증 행 0"}
        return ScoreRun({}, split, False, True, 0, 0, max_input, max_target_end or None)
    ratio = (len(s_rows) + 0.5) / (len(s_rows) + len(v_rows))
    model, tr = train_walk_forward(
        s_rows + v_rows,
        train_split_ratio=ratio,
        epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        seed=SEED,
    )
    _check_trainer(tr, s_rows, fold)
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
    raw = predict_raw_scores(model, inference) if model is not None else {}
    return ScoreRun(
        display_scores=normalize_to_display_scores(raw),
        split=split,
        has_model=model is not None,
        benchmark_ok=True,
        train_row_count=tr.train_row_count,
        test_row_count=tr.test_row_count,
        max_input_date=max_input,
        max_target_end_date=max_target_end or None,
    )


# --- 날짜별 기록 --------------------------------------------------------------------


def _top_block(rows: list[tuple[str, float, float]]) -> dict:
    top = top_fraction(rows, TOP_DECILE_FRACTION)
    values = [r[2] for r in top]
    return {"tickers": [r[0] for r in top], "values": values, "mean": mean(values)}


def evaluate_point(
    ctx: PanelContext, arm: str, codes: tuple[str, ...], point: RebalancePoint
) -> dict:
    """신호일 하나 × arm 하나 → JSON 직렬화 가능한 기록 (`_scores`/`_labels` 는 N-1 용 비공개)."""
    panel, t = ctx.panel, point.signal_date
    if t not in ctx.day_index:
        raise ValueError(f"거래일이 아닌 신호일: {t}")  # NON_TRADING_DATE 는 구조상 0
    run = train_and_score(ctx, codes, t)
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
    return {
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
