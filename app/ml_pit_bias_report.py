"""POC4-02A — arm 집계 · preflight · 전략 성과 · PIT − CONTROL 비교 · 결과 payload (PLAN §4 · §6).

- arm 마다 N-1 셔플 통제 → `preflight_gate` (E2 와 같은 fail-closed). 통과면 `MEASURED`, 아니면 막힌
  사유(`BLOCKED_COVERAGE` 등) — 막힌 arm 은 집계 지표를 내지 않고 수만 남긴다 (구현 정의 7).
- 두 arm 이 모두 `MEASURED` 일 때만 `survivorship_effect`(PIT − CONTROL) 를 낸다.
- `build_strategy_performance` 는 옛 가격 라벨을 박으므로 `price_basis` 를 `KRX_BASEPRICE_CHAIN` 으로
  덮어 쓴다 (원본 수정 없음 · PLAN §2-13).
- `ml_score_validity_report.aggregate` 는 쓰지 않는다 (NEAR 파일 · 기능 추가 금지) — 순수 함수만 import.

결과 payload 에 실행 시각은 `generated_at` 하나뿐이다 (canonical hash 에서 제외).
"""

from __future__ import annotations

from typing import Optional, Sequence

from app import ml_pit_bias_eval as pit_eval
from app.krx_sealed_reader import PRICE_BASIS, RELATION_TOLERANCE_PCT, SEALED_VERSION
from app.ml_pit_universe import ARM_CONTROL, ARM_PIT, ARMS, REASON_CODES
from app.ml_relative_upside_features import FEATURE_COLUMNS
from app.ml_score_validity_eval import (
    BLOCKING_MIN_COVERAGE,
    COST_BPS_GRID,
    EXCLUDED_TAGS,
    PRIMARY_COST_BP,
    QUANTILE_BUCKETS,
    TOP_DECILE_FRACTION,
)
from app.ml_score_validity_metrics import (
    BOOTSTRAP_BLOCK_LEN,
    BOOTSTRAP_CI_HIGH_PCT,
    BOOTSTRAP_CI_LOW_PCT,
    BOOTSTRAP_ITERATIONS,
    BOOTSTRAP_SEED,
    SHUFFLE_SEED_END,
    SHUFFLE_SEED_START,
    circular_block_bootstrap_ci,
    cost_drag,
    mean,
    median,
    replaced_fraction,
    shuffle_control_verdict,
    shuffle_permutation_means,
    stdev,
    t_stat,
    win_rate,
)
from app.ml_score_validity_report import now_iso, preflight_gate
from app.ml_strategy_performance import (
    COMMISSION_BP,
    PRIMARY_SLIPPAGE_BP,
    build_strategy_performance,
)

SCHEMA_VERSION = "poc4_02a_pit_bias.v1"
TRACK = "POC4-02A"
MEASURED = "MEASURED"
CANONICAL_EXCLUDED = ("generated_at",)
PRIMARY_STRATEGY_SCENARIO = f"decomposed_slippage_{int(PRIMARY_SLIPPAGE_BP)}bp"
OFFICIAL_LABELS = {
    "universe_basis": "KRX_POINT_IN_TIME_UNIVERSE_V1",
    "survivorship_status": "REDUCED_NOT_ELIMINATED",
    "ceiling": "RESEARCH_ONLY",
    "UNBIASED_PERFORMANCE_CLAIM": "NOT_YET",
}
PRICE_BASIS_NOTE = (
    "build_strategy_performance 가 박는 기존 라벨(E2 PRICE_BASIS_LABEL)을 02A 보고 모듈이 "
    "KRX_BASEPRICE_CHAIN 으로 덮어 썼다 (원본 모듈 수정 없음 · PLAN §2-13)"
)
REFERENCE_NOTE = (
    "기존 relative_upside_v1_snap_20260921 기준선과의 차이는 참고치다 — 가격 source 가 다르고(스냅샷 "
    "etf_daily_price 는 분배 조정값인데 E2 PRICE_BASIS_LABEL 은 '분배금 미반영' 으로 적혀 있다 · "
    "02A 는 KRX_BASEPRICE_CHAIN), universe·분할도 다르다. 이 결과는 기준선을 바꾸지 않는다."
)
# 막힌 arm 의 날짜별 기록에 남기는 필드 — 수·경계만 (날짜별 지표 제외).
COUNT_FIELDS = tuple(
    "arm phase signal_date entry_date exit_date next_signal_date universe_count split "
    "train_row_count test_row_count scored_count zero_volume_scored delisted_scored "
    "coverage_denominator coverage_numerator coverage reasons_prefilter reasons_filtered "
    "n_filter n_all delisted_in_eval max_input_date max_target_end_date".split()
)
# PIT − CONTROL 을 내는 단일 값 지표 (arm 블록 안 경로).
SCALAR_METRICS = (
    "metrics.ic_filter.mean",
    "metrics.ic_filter.median",
    "metrics.ic_all.mean",
    "metrics.quantile_spread_q5_minus_q1.mean",
    "metrics.top_decile_gross.mean",
    *(f"metrics.top_decile_net_by_cost_bp.{int(c)}.mean" for c in COST_BPS_GRID),
    "metrics.turnover.mean",
    "metrics.top_decile_win_rate_by_date",
    "metrics.sensitivity.ic.mean",
    "metrics.sensitivity.top_decile_gross.mean",
    "metrics.sensitivity.top_decile_net_25bp.mean",
    "counts.coverage.mean",
    "counts.coverage.min",
    "counts.totals.scored",
    "counts.totals.evaluated_filter",
    "counts.totals.delisted_scored",
    "counts.totals.delisted_in_eval",
    "counts.totals.zero_volume_scored",
)


def recipe_block() -> dict:
    """연구 recipe — 결과·run manifest·재개 지문(설정 hash)에 같은 값이 들어간다."""
    return {
        "recipe_id": "POC4-02A_KRX_PIT_BIAS_V1",
        "sealed_version": SEALED_VERSION,
        "price_basis": PRICE_BASIS,
        "relation_tolerance_pct": RELATION_TOLERANCE_PCT,
        "features": list(FEATURE_COLUMNS),
        "training_target": "future_excess_return_20d — t 행 → 20행 뒤 · 069500 연결 계열 대비 (A1)",
        "evaluation_label": "forward_excess 식 — 진입 t 다음 거래일 → 다음 월말 다음 거래일 · "
        "연결 계열 · ETF 진입·청산 ACC_TRDVOL > 0 (A1 · 판정 §2)",
        "sensitivity_label": "OFFICIAL_REFERENCE_SENSITIVITY — 같은 점수·필터·분모 · 거래량 조건만 뺀다",
        "model": "nn.Linear(7,1) · MSE · Adam · 전체 배치 · float32 (고정 trainer)",
        "epochs": pit_eval.EPOCHS,
        "learning_rate": pit_eval.LEARNING_RATE,
        "seed": pit_eval.SEED,
        "split_rule": (
            "신호일 t 마다 달력 = v1 거래일 ≤ t · 표본일 = 달력 index ≥ 20 · N = label 완성 표본일 수 · "
            "make_selection_folds(n_folds=1, validation_days=N − int(0.8N), horizon=20, "
            "walk-forward) · trainer 에 학습일 행 S + 검증일 행 V · "
            "train_split_ratio = (|S|+0.5)/(|S|+|V|) (A2)"
        ),
        "feature_warmup_days": pit_eval.FEATURE_WARMUP_DAYS,
        "label_horizon_days": pit_eval.SPLIT_HORIZON,
        "train_share": pit_eval.TRAIN_SHARE,
        "filter": f"classify_etf_tags(t 행 ISU_NM) 제외 태그 {list(EXCLUDED_TAGS)} (A4)",
        "scoring": "t 에 행이 있고 t 행 feature 가 완전한 종목만 · display = 후보군 내 순위 0~100",
        "quantile_buckets": QUANTILE_BUCKETS,
        "top_decile_fraction": TOP_DECILE_FRACTION,
        "top_decile_cost_bps_grid": list(COST_BPS_GRID),
        "top_decile_primary_cost_bp": PRIMARY_COST_BP,
        "strategy_primary_one_way_bp": COMMISSION_BP + PRIMARY_SLIPPAGE_BP,
        "min_coverage": BLOCKING_MIN_COVERAGE,
        "bootstrap": {
            "method": "circular moving-block bootstrap",
            "block_length": BOOTSTRAP_BLOCK_LEN,
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": BOOTSTRAP_SEED,
            "ci_percentiles": [BOOTSTRAP_CI_LOW_PCT, BOOTSTRAP_CI_HIGH_PCT],
        },
        "n1_shuffle_seeds": [SHUFFLE_SEED_START, SHUFFLE_SEED_END],
    }


# --- 요약 · 바스켓 ----------------------------------------------------------------


def _ci(series: Sequence[float]) -> Optional[dict]:
    got = circular_block_bootstrap_ci(series)
    return None if got is None else {"low": got[0], "high": got[1]}


def _summary(series: Sequence[float], *, with_ci: bool = True) -> dict:
    out = {
        "n": len(series),
        "mean": mean(series),
        "median": median(series),
        "sd": stdev(series),
        "t_stat_reference_only": t_stat(series),
    }
    if with_ci:
        out["bootstrap_ci_95"] = _ci(series)
    return out


def basket_series(items: Sequence[tuple[str, Optional[float], list]]) -> dict:
    """(신호일, 상위 10% 평균, 종목) → gross · 교체비율 · 비용별 net (E2 aggregate 와 같은 규칙).

    첫 날(직전 바스켓 없음)은 교체비율 None → 비용 0. 상위 10% 가 없는 날은 그날 종목(빈 목록)을
    직전 바스켓으로 둔다(E2 `aggregate` 의 top-decile 규칙 그대로).
    """
    gross: list[float] = []
    turnovers: list[float] = []
    net = {str(int(c)): [] for c in COST_BPS_GRID}
    net_by_date: dict[str, dict[str, float]] = {}
    prev = None
    for date, value, tickers in items:
        if value is None:
            prev = tickers
            continue
        rep = replaced_fraction(prev, tickers) if prev is not None else None
        if rep is not None:
            turnovers.append(rep)
        gross.append(value)
        net_by_date[date] = {}
        for c in COST_BPS_GRID:
            v = value - cost_drag(rep, c)
            net[str(int(c))].append(v)
            net_by_date[date][str(int(c))] = v
        prev = tickers
    return {
        "gross": gross,
        "turnover": turnovers,
        "net": net,
        "net_by_date": net_by_date,
    }


def _main_items(records):
    return [
        (r["signal_date"], r["top_decile_mean"], r["top_decile_tickers"])
        for r in records
    ]


def _sens_items(records):
    return [
        (
            r["signal_date"],
            r["sensitivity"]["top_decile_mean"],
            r["sensitivity"]["top_decile_tickers"],
        )
        for r in records
    ]


def strategy_block(
    records, benchmark_closes: dict[str, float], *, sensitivity: bool
) -> dict:
    """전략 성과 — 민감도는 top_decile_* 를 민감도 블록 값으로 바꾼 기록을 넘긴다."""
    if sensitivity:
        records = [
            {
                "signal_date": r["signal_date"],
                "entry_date": r["entry_date"],
                "exit_date": r["exit_date"],
                "top_decile_mean": r["sensitivity"]["top_decile_mean"],
                "top_decile_tickers": r["sensitivity"]["top_decile_tickers"],
            }
            for r in records
        ]
    out = build_strategy_performance(records, benchmark_closes)
    out["price_basis"] = PRICE_BASIS
    out["price_basis_note"] = PRICE_BASIS_NOTE
    out["label_basis"] = "OFFICIAL_REFERENCE_SENSITIVITY" if sensitivity else "MAIN"
    return out


# --- arm 블록 -------------------------------------------------------------------------


def n1_control(records) -> dict:
    pairs = [(r["_scores"], r["_labels"]) for r in records if len(r["_scores"]) >= 2]
    return shuffle_control_verdict(
        shuffle_permutation_means(
            pairs, seed_start=SHUFFLE_SEED_START, seed_end=SHUFFLE_SEED_END
        )
    )


def _sum_reasons(records, key: str) -> dict[str, int]:
    out = {code: 0 for code in REASON_CODES}
    for r in records:
        for k, v in r[key].items():
            out[k] = out.get(k, 0) + v
    return out


def arm_counts(records) -> dict:
    """막혀도 남기는 수 — 사유 · 점수·평가·폐지·거래량 0 · 분할 · coverage."""
    cov = [r["coverage"] for r in records if r["coverage"] is not None]
    splits = [r["split"] for r in records]
    model = [s for s in splits if s.get("status") == "OK"]
    trains = [r["train_row_count"] for r in records if r["split"].get("status") == "OK"]
    tests = [r["test_row_count"] for r in records if r["split"].get("status") == "OK"]
    purged = [s["purged_days"] for s in model]
    return {
        "dates": len(records),
        "reasons_prefilter": _sum_reasons(records, "reasons_prefilter"),
        "reasons_filtered": _sum_reasons(records, "reasons_filtered"),
        "totals": {
            "universe": sum(r["universe_count"] for r in records),
            "scored": sum(r["scored_count"] for r in records),
            "evaluated_filter": sum(r["n_filter"] for r in records),
            "evaluated_all": sum(r["n_all"] for r in records),
            "delisted_scored": sum(r["delisted_scored"] for r in records),
            "delisted_in_eval": sum(r["delisted_in_eval"] for r in records),
            "zero_volume_scored": sum(r["zero_volume_scored"] for r in records),
        },
        "split": {
            "dates_with_model": len(model),
            "dates_without_model": len(records) - len(model),
            "train_rows_min": min(trains) if trains else None,
            "train_rows_max": max(trains) if trains else None,
            "test_rows_min": min(tests) if tests else None,
            "test_rows_max": max(tests) if tests else None,
            "purged_days_min": min(purged) if purged else None,
            "purged_days_max": max(purged) if purged else None,
            "embargo": "walk-forward — 검증 뒤 자료를 학습에 쓰지 않아 구조적으로 해당 없음",
        },
        "coverage": {
            "mean": mean(cov),
            "min": min(cov) if cov else None,
            "denominator_definition": "arm universe(t 행) ∩ 이름 필터(t 행 ISU_NM) ∩ is_pit_eligible",
        },
    }


def arm_metrics(records, benchmark_closes: dict[str, float]) -> dict:
    """MEASURED arm 의 집계 지표 (설계 §6 · PLAN §4 산출)."""
    ic = [r["ic_filter"] for r in records if r["ic_filter"] is not None]
    ic_all = [r["ic_all"] for r in records if r["ic_all"] is not None]
    spread = []
    for r in records:
        q = r["quantile_means"]
        hi, lo = q.get(str(QUANTILE_BUCKETS - 1)), q.get("0")
        if hi is not None and lo is not None:
            spread.append(hi - lo)
    main = basket_series(_main_items(records))
    sens = basket_series(_sens_items(records))
    yearly: dict[str, list[float]] = {}
    for r in records:
        if r["ic_filter"] is not None:
            yearly.setdefault(r["signal_date"][:4], []).append(r["ic_filter"])
    sens_ic = [
        r["sensitivity"]["ic"] for r in records if r["sensitivity"]["ic"] is not None
    ]
    return {
        "ic_filter": _summary(ic),
        "ic_all": _summary(ic_all),
        "quantile_spread_q5_minus_q1": _summary(spread),
        "top_decile_gross": _summary(main["gross"]),
        "top_decile_net_by_cost_bp": {k: _summary(v) for k, v in main["net"].items()},
        "turnover": _summary(main["turnover"], with_ci=False),
        "top_decile_win_rate_by_date": win_rate(main["gross"]),
        "yearly_ic": {
            y: {"n": len(v), "mean_ic": mean(v), "positive": (mean(v) or 0) > 0}
            for y, v in sorted(yearly.items())
        },
        "strategy_performance": strategy_block(
            records, benchmark_closes, sensitivity=False
        ),
        "sensitivity": {
            "label_basis": "OFFICIAL_REFERENCE_SENSITIVITY",
            "role": "민감도 표 — 주 판정·preflight 에 쓰지 않는다 (판정 §2)",
            "ic": _summary(sens_ic),
            "top_decile_gross": _summary(sens["gross"]),
            "top_decile_net_25bp": _summary(sens["net"][str(int(PRIMARY_COST_BP))]),
            "strategy_performance": strategy_block(
                records, benchmark_closes, sensitivity=True
            ),
        },
    }


def build_arm_block(records, benchmark_closes: dict[str, float]) -> dict:
    n1 = n1_control(records)
    gate = preflight_gate(records, n1)
    status = MEASURED if gate["status"] == "OK" else gate["status"]
    return {
        "status": status,
        "preflight_gate": gate,
        "n1_negative_control": n1,
        "counts": arm_counts(records),
        "metrics": (
            arm_metrics(records, benchmark_closes) if status == MEASURED else None
        ),
    }


def public_record(record: dict, *, measured: bool) -> dict:
    """결과 per_date 용 — `_scores`/`_labels` 제거 · 막힌 arm 은 수 필드만."""
    if measured:
        return {k: v for k, v in record.items() if not k.startswith("_")}
    return {k: record[k] for k in COUNT_FIELDS if k in record}


# --- PIT − CONTROL ---------------------------------------------------------------------


def _get(block: dict, dotted: str):
    node = block
    for key in dotted.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _diff(a, b):
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
        return None
    return a - b


def _paired(pit: dict[str, Optional[float]], ctl: dict[str, Optional[float]]) -> dict:
    dates = sorted(set(pit) | set(ctl))
    both = [d for d in dates if pit.get(d) is not None and ctl.get(d) is not None]
    diffs = [pit[d] - ctl[d] for d in both]
    return {
        "n_paired": len(both),
        "mean_diff": mean(diffs),
        "median_diff": median(diffs),
        "bootstrap_ci_95": _ci(diffs),
        "unpaired_dates": len(dates) - len(both),
        "pit_only_dates": sum(
            1 for d in dates if pit.get(d) is not None and ctl.get(d) is None
        ),
        "control_only_dates": sum(
            1 for d in dates if ctl.get(d) is not None and pit.get(d) is None
        ),
    }


def _net_primary_by_date(records) -> dict[str, Optional[float]]:
    by_date = basket_series(_main_items(records))["net_by_date"]
    key = str(int(PRIMARY_COST_BP))
    return {
        r["signal_date"]: by_date.get(r["signal_date"], {}).get(key) for r in records
    }


def survivorship_effect(blocks: dict, records: dict) -> dict:
    """두 arm 모두 MEASURED 일 때만 — 지표마다 PIT − CONTROL · 날짜별 짝 차이 평균과 블록 부트스트랩 CI."""
    statuses = {arm: blocks[arm]["status"] for arm in ARMS}
    if any(s != MEASURED for s in statuses.values()):
        return {
            "status": "NOT_PRODUCED",
            "reason": "두 arm 이 모두 MEASURED 일 때만 낸다 (구현 정의 7)",
            "arm_status": statuses,
        }
    pit, ctl = blocks[ARM_PIT], blocks[ARM_CONTROL]
    scalar = {}
    for path in SCALAR_METRICS:
        a, b = _get(pit, path), _get(ctl, path)
        scalar[path] = {"pit": a, "control": b, "pit_minus_control": _diff(a, b)}
    yearly_p = pit["metrics"]["yearly_ic"]
    yearly_c = ctl["metrics"]["yearly_ic"]
    yearly = {
        y: _diff(yearly_p.get(y, {}).get("mean_ic"), yearly_c.get(y, {}).get("mean_ic"))
        for y in sorted(set(yearly_p) | set(yearly_c))
    }
    per_date = {
        "ic_filter": _paired(
            {r["signal_date"]: r["ic_filter"] for r in records[ARM_PIT]},
            {r["signal_date"]: r["ic_filter"] for r in records[ARM_CONTROL]},
        ),
        "top_decile_gross": _paired(
            {r["signal_date"]: r["top_decile_mean"] for r in records[ARM_PIT]},
            {r["signal_date"]: r["top_decile_mean"] for r in records[ARM_CONTROL]},
        ),
        f"top_decile_net_{int(PRIMARY_COST_BP)}bp": _paired(
            _net_primary_by_date(records[ARM_PIT]),
            _net_primary_by_date(records[ARM_CONTROL]),
        ),
    }
    strategy = {}
    sp_p = pit["metrics"]["strategy_performance"].get("scenarios", {})
    sp_c = ctl["metrics"]["strategy_performance"].get("scenarios", {})
    sc_p = sp_p.get(PRIMARY_STRATEGY_SCENARIO)
    sc_c = sp_c.get(PRIMARY_STRATEGY_SCENARIO)
    if sc_p and sc_c:
        for part in ("absolute", "relative"):
            strategy[part] = {
                k: _diff(sc_p[part].get(k), sc_c[part].get(k))
                for k in sorted(sc_p[part])
            }
    return {
        "status": "PRODUCED",
        "definition": "SURVIVORSHIP_EFFECT = PIT − CONTROL (같은 봉인 계열·날짜·recipe · universe 만 다름)",
        "scalar": scalar,
        "yearly_mean_ic": yearly,
        "per_date_paired": per_date,
        "strategy_primary_scenario": PRIMARY_STRATEGY_SCENARIO,
        "strategy_primary_diff": strategy,
    }


def cross_coverage(records: dict) -> list[dict]:
    """참고표 — 날짜별 CONTROL 분자 / PIT 분모 (A7 · 실행 차단에 쓰지 않는다)."""
    ctl = {r["signal_date"]: r for r in records[ARM_CONTROL]}
    out = []
    for p in records[ARM_PIT]:
        c = ctl.get(p["signal_date"])
        if c is None:
            continue
        denom = p["coverage_denominator"]
        out.append(
            {
                "signal_date": p["signal_date"],
                "control_numerator": c["coverage_numerator"],
                "pit_denominator": denom,
                "cross_coverage": (c["coverage_numerator"] / denom) if denom else None,
                "pit_coverage": p["coverage"],
                "control_coverage": c["coverage"],
            }
        )
    return out


# --- 결과 payload -------------------------------------------------------------------


def build_result(
    *,
    official: bool,
    source: dict,
    calendar: dict,
    universe: dict,
    records: dict,
    benchmark_closes: dict[str, float],
) -> dict:
    """결과 payload (`poc4_02a_pit_bias.v1`). `determinism.canonical_sha256` 은 호출자가 채운다."""
    blocks = {arm: build_arm_block(records[arm], benchmark_closes) for arm in ARMS}
    return {
        "schema_version": SCHEMA_VERSION,
        "track": TRACK,
        "generated_at": now_iso(),
        "official": official,
        "official_labels": dict(OFFICIAL_LABELS),
        "price_basis": PRICE_BASIS,
        "source": source,
        "calendar": calendar,
        "recipe": recipe_block(),
        "universe": universe,
        "arms": blocks,
        "survivorship_effect": survivorship_effect(blocks, records),
        "cross_coverage": cross_coverage(records),
        "reference_note": REFERENCE_NOTE,
        "per_date": {
            arm: [
                public_record(r, measured=blocks[arm]["status"] == MEASURED)
                for r in records[arm]
            ]
            for arm in ARMS
        },
        "determinism": {
            "excluded_fields": list(CANONICAL_EXCLUDED),
            "canonical_sha256": None,
        },
    }
