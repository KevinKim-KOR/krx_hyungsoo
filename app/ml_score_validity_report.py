"""POC3-ML-02 — 평가 결과 집계 + 사전 판정 기준 대조 (PLAN §4 / §5).

본 모듈은 기준일별 레코드를 받아 지표를 집계하고 **구현 전 고정된** 판정 기준과
대조한다. 임계값은 결과를 본 뒤 바꾸지 않는다 (설계서 §4.6).

판정 상한: 생존편향의 크기·방향을 정량화할 수 없으므로 최대 `RESEARCH_ONLY`
(PLAN §2.6 · P-1). `REJECT` 는 상한과 무관하게 가능하다.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from app.ml_score_validity_eval import (
    BLOCKING_MIN_COVERAGE,
    COST_BPS_GRID,
    PRICE_BASIS_LABEL,
    PRIMARY_COST_BP,
    QUANTILE_BUCKETS,
    SCORE_TOP_N,
    month_end_days,
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
    newey_west_t,
    replaced_fraction,
    shuffle_control_verdict,
    shuffle_permutation_means,
    stdev,
    t_stat,
    win_rate,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "relative_upside_validity.v1"

# --- 사전 판정 임계값 (PLAN §5 — 구현 전 고정) ------------------------------
A1_MIN_IC = 0.03
A2_MIN_NET_MONTHLY = 0.003
A3_MIN_POSITIVE_YEARS = 9
A4_MIN_WIN_RATIO = 0.5
A5_MIN_COVERAGE = 0.90
R2_NOISE_IC = 0.01
R4_BEAR_IC = -0.02
R4_MIN_BEAR_SAMPLES = 12

REGIME_LABELS = ("bull", "neutral", "bear")

# L-4 전체 결정성 대조에서 제외하는 **승인된** 비결정 메타데이터 (설계자 보완 §5).
# 이 목록 밖의 어떤 필드도 제외하지 않는다.
NON_DETERMINISTIC_FIELDS = (
    "generated_at",
    "e1.elapsed_seconds",
)
# 위 목록과 별개로, 해시 자신을 담는 `determinism.canonical_sha256` 은 계산 시
# None 으로 정규화한다 (해시가 자기 자신을 포함할 수 없다).
SELF_REFERENTIAL_FIELD = "determinism.canonical_sha256"


def _strip_path(payload: dict, dotted: str) -> None:
    """`a.b.c` 경로의 키를 제자리에서 제거. 없으면 무시."""
    parts = dotted.split(".")
    node = payload
    for key in parts[:-1]:
        if not isinstance(node, dict) or key not in node:
            return
        node = node[key]
    if isinstance(node, dict):
        node.pop(parts[-1], None)


def canonical_sha256(
    payload: dict, *, exclude: tuple[str, ...] = NON_DETERMINISTIC_FIELDS
) -> str:
    """결과 객체 전체의 canonical sha256 (설계자 보완 §5).

    승인된 비결정 메타데이터만 제외하고 **나머지 JSON 전체**를 정렬 직렬화해
    해시한다. 일부 지표만 비교하는 방식으로 L-4 를 통과시키지 않는다.
    """
    import copy
    import json as _json

    clone = copy.deepcopy(payload)
    for path in exclude:
        _strip_path(clone, path)
    # 자기참조 필드는 제거가 아니라 **None 으로 되돌린다**. 기록 시점에는 None
    # 이었으므로, 저장된 파일에서 다시 계산해도 같은 값이 나온다 (검증자 재현 가능).
    if isinstance(clone.get("determinism"), dict):
        clone["determinism"]["canonical_sha256"] = None
    blob = _json.dumps(clone, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def preflight_gate(evaluation_records: list[dict], n1: dict) -> dict:
    """집계·판정 **전에** 실행을 막는 fail-closed 게이트 (설계자 보완 §1 · §7).

    막히면 `validity_latest` 를 정상 결과로 발행하지 않는다. 사후 보고가 아니라
    실행 코드가 멈춘다.

    - E2 평가일 중 coverage < 70% 가 하나라도 있으면 `BLOCKED_COVERAGE`
    - L-1~L-3 위반이 하나라도 있으면 `BLOCKED_LEAKAGE`
    - N-1 negative control 실패면 `BLOCKED_METRIC_CONTROL`
    """
    blocked: list[str] = []
    details: dict = {}

    low = [
        {"signal_date": r["signal_date"], "coverage": r["coverage"]}
        for r in evaluation_records
        if r.get("coverage") is None or r["coverage"] < BLOCKING_MIN_COVERAGE
    ]
    if low:
        blocked.append("BLOCKED_COVERAGE")
        details["BLOCKED_COVERAGE"] = {
            "threshold": BLOCKING_MIN_COVERAGE,
            "dates": low,
        }

    l1 = [
        r["signal_date"]
        for r in evaluation_records
        if r.get("max_input_date") and r["max_input_date"] > r["signal_date"]
    ]
    l2 = [
        r["signal_date"]
        for r in evaluation_records
        if r["entry_date"] <= r["signal_date"]
    ]
    l3 = [
        r["signal_date"]
        for r in evaluation_records
        if r.get("max_target_end_date") and r["max_target_end_date"] > r["signal_date"]
    ]
    if l1 or l2 or l3:
        blocked.append("BLOCKED_LEAKAGE")
        details["BLOCKED_LEAKAGE"] = {"L1": l1, "L2": l2, "L3": l3}

    if not n1.get("passed"):
        blocked.append("BLOCKED_METRIC_CONTROL")
        details["BLOCKED_METRIC_CONTROL"] = n1

    return {
        "status": "OK" if not blocked else blocked[0],
        "blocked": blocked,
        "details": details,
        "evaluated_dates": len(evaluation_records),
        "leakage": {"L1": len(l1), "L2": len(l2), "L3": len(l3)},
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ci(series: list[float]) -> Optional[dict]:
    got = circular_block_bootstrap_ci(series)
    if got is None:
        return None
    return {"low": got[0], "high": got[1]}


def _summary(series: list[float], *, with_ci: bool = True) -> dict:
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


def _basket_series(records, values_key, tickers_key):
    """바스켓의 (gross 시계열, 월별 교체비율, 비용별 net 시계열) 산출.

    비용은 **월별 실측 교체비율**에 적용한다 (PLAN §4.9).
    """
    gross: list[float] = []
    turnovers: list[float] = []
    net: dict[str, list[float]] = {str(int(c)): [] for c in COST_BPS_GRID}
    prev = None
    for r in records:
        values = r.get(values_key) or []
        tickers = r.get(tickers_key) or []
        if not values:
            prev = tickers or prev
            continue
        rep_frac = replaced_fraction(prev, tickers) if prev is not None else None
        if rep_frac is not None:
            turnovers.append(rep_frac)
        m = mean(values)
        gross.append(m)
        for c in COST_BPS_GRID:
            net[str(int(c))].append(m - cost_drag(rep_frac, c))
        prev = tickers
    return gross, turnovers, net


def aggregate(
    per_date, e1, days, frozen_descriptor, calendar_extra, warmup_records=None
) -> dict:
    """지표 집계 + 판정 (PLAN §4 / §5)."""
    ic_filter = [r["ic_filter"] for r in per_date if r["ic_filter"] is not None]
    ic_all = [r["ic_all"] for r in per_date if r["ic_all"] is not None]
    ic_simple = [
        r["ic_simple_momentum"] for r in per_date if r["ic_simple_momentum"] is not None
    ]
    ic_3m_series = [r["ic_3m"] for r in per_date if r["ic_3m"] is not None]

    # 분위 스프레드
    spread = []
    for r in per_date:
        q = r["quantile_means"]
        hi, lo = q.get(str(QUANTILE_BUCKETS - 1)), q.get("0")
        if hi is not None and lo is not None:
            spread.append(hi - lo)

    # turnover / 비용 (상위 10% 바스켓 · 월별 실측)
    gross, turnovers, net_by_cost = [], [], {str(int(c)): [] for c in COST_BPS_GRID}
    prev = None
    for r in per_date:
        if r["top_decile_mean"] is None:
            prev = r["top_decile_tickers"]
            continue
        rep = (
            replaced_fraction(prev, r["top_decile_tickers"])
            if prev is not None
            else None
        )
        if rep is not None:
            turnovers.append(rep)
        gross.append(r["top_decile_mean"])
        for c in COST_BPS_GRID:
            net_by_cost[str(int(c))].append(r["top_decile_mean"] - cost_drag(rep, c))
        r["replaced_fraction"] = rep
        prev = r["top_decile_tickers"]

    net_primary = net_by_cost[str(int(PRIMARY_COST_BP))]

    # 연도별 / 시장 상태별
    yearly, by_regime = {}, {}
    for r in per_date:
        if r["ic_filter"] is None:
            continue
        yearly.setdefault(r["signal_date"][:4], []).append(r["ic_filter"])
        by_regime.setdefault(r["regime"] or "unknown", []).append(r["ic_filter"])

    yearly_summary = {
        y: {"n": len(v), "mean_ic": mean(v), "positive": (mean(v) or 0) > 0}
        for y, v in sorted(yearly.items())
    }
    regime_summary = {
        g: {
            "n": len(v),
            "mean_ic": mean(v),
            "bootstrap_ci_95": _ci(v),
            "positive": (mean(v) or 0) > 0,
        }
        for g, v in sorted(by_regime.items())
    }

    # 커버리지
    cov = [r["coverage"] for r in per_date if r["coverage"] is not None]
    missing_total: dict[str, int] = {}
    for r in per_date:
        for k, v in r["missing_reasons"].items():
            missing_total[k] = missing_total.get(k, 0) + v

    # --- 3M 비중첩 (분기말) 부분집합 — 설계자 보완 §3 --------------------
    q_records = [r for r in per_date if r.get("is_quarter_end")]
    q_used = [r for r in q_records if r.get("ic_3m") is not None]
    q_ic = [r["ic_3m"] for r in q_used]
    q_spread = []
    for r in q_used:
        q3 = r.get("quantile_means_3m") or {}
        hi, lo = q3.get(str(QUANTILE_BUCKETS - 1)), q3.get("0")
        if hi is not None and lo is not None:
            q_spread.append(hi - lo)
    q_gross, q_turn, q_net = _basket_series(
        q_used, "top_decile_3m_values", "top_decile_3m_tickers"
    )
    q_exclusions: dict[str, int] = {}
    for r in q_records:
        reason = r.get("exclusion_3m")
        if reason:
            q_exclusions[reason] = q_exclusions.get(reason, 0) + 1
    non_overlapping_3m = {
        "definition": "분기말 기준일만 사용한 3M 비중첩 표본",
        "quarter_end_dates": len(q_records),
        "dates_used": len(q_used),
        "exclusion_reasons": q_exclusions,
        "ic": _summary(q_ic),
        "quantile_spread_q5_minus_q1": _summary(q_spread),
        "top_decile_gross": _summary(q_gross),
        "top_decile_net_by_cost_bp": {k: _summary(v) for k, v in q_net.items()},
        "turnover": _summary(q_turn, with_ci=False),
        "win_rate_by_date": win_rate(q_gross),
    }

    # --- 점수 기준 top-N 바스켓 — 설계자 보완 §4 ---------------------------
    st_records = [r for r in per_date if r.get("score_top10_mean") is not None]
    st_gross, st_turn, st_net = _basket_series(
        st_records, "score_top10_values", "score_top10_tickers"
    )
    st_missing: dict[str, int] = {}
    for r in per_date:
        reason = r.get("score_top10_missing_reason")
        if reason:
            st_missing[reason] = st_missing.get(reason, 0) + 1
    pooled_st = [v for r in st_records for v in (r.get("score_top10_values") or [])]
    score_top_basket = {
        "definition": (
            f"필터 universe 에서 참고점수 상위 {SCORE_TOP_N}개 "
            "(화면 슬레이트 screen_slate_u2 와 별개)"
        ),
        "dates_used": len(st_records),
        "missing_reasons": st_missing,
        "gross": _summary(st_gross),
        "pooled_median": median(pooled_st),
        "net_by_cost_bp": {k: _summary(v) for k, v in st_net.items()},
        "turnover": _summary(st_turn, with_ci=False),
        "win_rate_by_date": win_rate(st_gross),
        "note": "본 지표는 R-3 판정 기준을 사후 변경하지 않는다 (참고 지표).",
    }

    # 화면 슬레이트
    screen_diffs = [
        r["screen_diff"] for r in per_date if r.get("screen_diff") is not None
    ]

    # N-1 negative control
    logger.info(
        "N-1 negative control (%d회 permutation)",
        SHUFFLE_SEED_END - SHUFFLE_SEED_START + 1,
    )
    pairs = [(r["_scores"], r["_labels"]) for r in per_date if len(r["_scores"]) >= 2]
    perm_means = shuffle_permutation_means(
        pairs, seed_start=SHUFFLE_SEED_START, seed_end=SHUFFLE_SEED_END
    )
    n1 = shuffle_control_verdict(perm_means)

    for r in per_date:
        r.pop("_scores", None)
        r.pop("_labels", None)

    ic_sum = _summary(ic_filter)
    net_sum = _summary(net_primary)
    spread_sum = _summary(spread)
    ic3_sum = _summary(ic_3m_series)
    screen_sum = _summary(screen_diffs)

    # --- 판정 (PLAN §5) ---
    mean_ic = ic_sum["mean"]
    ic_ci = ic_sum["bootstrap_ci_95"]
    net_ci = net_sum["bootstrap_ci_95"]
    pooled_top = [v for r in per_date for v in r.get("top_decile_values", [])]
    top_med = median(pooled_top)
    coverage_mean = mean(cov)
    pos_years = len([1 for v in yearly_summary.values() if v["positive"]])
    all_regimes = [g for g in ("bull", "neutral", "bear")]
    regimes_positive = all(
        regime_summary.get(g, {}).get("positive", False) for g in all_regimes
    )
    screen_mean = screen_sum["mean"]
    screen_win = win_rate(screen_diffs)
    l1 = sum(
        1
        for r in per_date
        if r["max_input_date"] and r["max_input_date"] > r["signal_date"]
    )
    l2 = sum(1 for r in per_date if r["entry_date"] <= r["signal_date"])
    l3 = sum(
        1
        for r in per_date
        if r["max_target_end_date"] and r["max_target_end_date"] > r["signal_date"]
    )
    leak_ok = l1 == 0 and l2 == 0 and l3 == 0

    e1_ics = [r["e1_ic"] for r in per_date if r.get("e1_ic") is not None]
    e1_screen = [
        r["e1_screen_diff"] for r in per_date if r.get("e1_screen_diff") is not None
    ]
    e1_ic_mean, e1_screen_mean = mean(e1_ics), mean(e1_screen)

    a1 = (
        mean_ic is not None
        and mean_ic >= A1_MIN_IC
        and ic_ci is not None
        and ic_ci["low"] > 0
    )
    a2 = (
        net_sum["mean"] is not None
        and net_sum["mean"] >= A2_MIN_NET_MONTHLY
        and top_med is not None
        and top_med > 0
        and net_ci is not None
        and net_ci["low"] > 0
    )
    a3 = pos_years >= A3_MIN_POSITIVE_YEARS and regimes_positive
    a4 = (
        screen_mean is not None
        and screen_mean > 0
        and screen_win is not None
        and screen_win > A4_MIN_WIN_RATIO
    )
    a5 = (
        coverage_mean is not None
        and coverage_mean >= A5_MIN_COVERAGE
        and n1["passed"]
        and leak_ok
    )
    if (
        e1["status"] != "E1_RECONSTRUCTED"
        or e1_ic_mean is None
        or e1_screen_mean is None
    ):
        # 설계자 보완 §6 — NOT_EVALUABLE 을 true 로 바꾸는 fallback 을 두지 않는다.
        a6_block = {
            "status": "NOT_EVALUABLE",
            "passed": None,
            "reason": e1.get("status", "E1_UNAVAILABLE"),
            "e1_mean_ic": e1_ic_mean,
            "e1_mean_screen_diff": e1_screen_mean,
            "e1_dates": len(e1_ics),
        }
    else:
        contradicted = e1_ic_mean < 0 and e1_screen_mean < 0
        a6_block = {
            "status": "CONTRADICTED" if contradicted else "NOT_CONTRADICTED",
            "passed": (not contradicted),
            "reason": None,
            "e1_mean_ic": e1_ic_mean,
            "e1_mean_screen_diff": e1_screen_mean,
            "e1_dates": len(e1_ics),
        }
    a6 = a6_block["passed"]

    bear = regime_summary.get("bear", {})
    r1 = mean_ic is not None and mean_ic < 0 and ic_ci is not None and ic_ci["high"] < 0
    r2 = (
        mean_ic is not None
        and abs(mean_ic) < R2_NOISE_IC
        and ic_ci is not None
        and ic_ci["low"] <= 0 <= ic_ci["high"]
    )
    r3 = net_sum["mean"] is not None and net_sum["mean"] <= 0
    bear_ci = bear.get("bootstrap_ci_95")
    r4 = (
        bear.get("n", 0) >= R4_MIN_BEAR_SAMPLES
        and bear.get("mean_ic") is not None
        and bear["mean_ic"] < R4_BEAR_IC
        and bear_ci is not None
        and bear_ci["high"] < 0
    )

    reject = bool(r1 or r2 or r3 or r4)
    flags = [a1, a2, a3, a4, a5, a6]
    if any(f is False for f in flags):
        passed_all = False
    elif any(f is None for f in flags):
        passed_all = None  # 판정 불가 항목이 남아 있으면 "전부 충족" 이라 못 한다.
    else:
        passed_all = True
    final = "REJECT" if reject else "RESEARCH_ONLY"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso(),
        "price_basis": PRICE_BASIS_LABEL,
        "frozen_descriptor": frozen_descriptor,
        "calendar": {
            "trading_days": len(days),
            "first_trading_day": days[0],
            "last_trading_day": days[-1],
            "month_end_days": len(month_end_days(days)),
            "e2_evaluation_points": len(per_date),
            "e2_first_signal_date": min(r["signal_date"] for r in per_date),
            "signal_entry_rule": "판단일 t / 진입 e(t)=t 다음 거래일 / 청산 e(t')",
            **(calendar_extra or {}),
        },
        "pre_evaluation_warmup": {
            "definition": (
                "v0 레시피가 아직 모델을 만들 수 없어 애초에 E2 평가 대상이 아닌 "
                "기준일. 결과를 보고 제외한 것이 아니라 PLAN 의 E2 시작일을 복원한 것."
            ),
            "dates": [
                {
                    "signal_date": r["signal_date"],
                    "train_row_count": r.get("train_row_count"),
                    "scored_count": r.get("scored_count"),
                    "reason": "train_rows=0 — 학습 가능 행 부재",
                }
                for r in (warmup_records or [])
            ],
            "excluded_from": [
                "coverage",
                "ic",
                "yearly",
                "by_regime",
                "top_decile",
                "score_top10_basket",
                "three_month",
                "screen_slate_u2",
            ],
            "note": (
                "이후 발생하는 train_rows=0 을 임의로 warmup 으로 재분류하지 않는다. "
                "warmup 집합은 사전 고정이다."
            ),
        },
        "e1": e1,
        "e2": {
            "definition": "현재 v0 실행 레시피의 point-in-time 재현 (신규 학습 정책 아님)",
            "ic_filter_universe": ic_sum,
            "ic_all_universe_diagnostic": _summary(ic_all),
            "ic_simple_momentum_diagnostic": _summary(ic_simple),
            "ic_3m_overlapping": ic3_sum,
            "three_month_non_overlapping": non_overlapping_3m,
            "score_top10_basket": score_top_basket,
            "ic_3m_newey_west_t": newey_west_t(ic_3m_series, lag=2),
            "quantile_spread_q5_minus_q1": spread_sum,
            "top_decile_gross": _summary(gross),
            "top_decile_net_by_cost_bp": {
                k: _summary(v) for k, v in net_by_cost.items()
            },
            "turnover": _summary(turnovers, with_ci=False),
            "top_decile_win_rate_by_date": win_rate(gross),
            "yearly": yearly_summary,
            "by_regime": regime_summary,
            "coverage": {
                "mean": coverage_mean,
                "min": min(cov) if cov else None,
                "missing_reason_totals": missing_total,
                "denominator_definition": "PIT 편입 가능 필터 universe",
            },
            "screen_slate_u2": {
                "definition": "필터 → one_month desc Top10 → 점수 결합 → 점수 재정렬",
                "diff_top_half_minus_bottom_half": screen_sum,
                "win_month_ratio": screen_win,
                "dates_evaluated": len(screen_diffs),
            },
        },
        "leakage_checks": {
            "L1_future_input_violations": l1,
            "L2_label_before_entry_violations": l2,
            "L3_target_end_violations": l3,
            "L4_determinism": "동일 seed 재실행 테스트로 검증 (T-14)",
            "all_passed": leak_ok,
            "note": "L-1~L-3 이 누수 판정. N-1 은 metric 구현 negative control 이다.",
        },
        "n1_negative_control": n1,
        "bootstrap_contract": {
            "method": "circular moving-block bootstrap",
            "block_length_months": BOOTSTRAP_BLOCK_LEN,
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": BOOTSTRAP_SEED,
            "ci_percentiles": [BOOTSTRAP_CI_LOW_PCT, BOOTSTRAP_CI_HIGH_PCT],
        },
        "verdict": {
            "final": final,
            "ceiling": "RESEARCH_ONLY",
            "ceiling_reason": (
                "상장폐지 생존편향의 크기와 방향을 정량화할 수 없으므로 "
                "ADOPT 의 충분한 근거로 사용할 수 없다 (PLAN §2.6 · P-1)"
            ),
            "numeric_criteria": {
                "A1_ic": {
                    "passed": a1,
                    "mean_ic": mean_ic,
                    "threshold": A1_MIN_IC,
                    "ci": ic_ci,
                },
                "A2_top_decile_net": {
                    "passed": a2,
                    "mean_net": net_sum["mean"],
                    "threshold": A2_MIN_NET_MONTHLY,
                    "median": top_med,
                    "ci": net_ci,
                    "cost_bp": PRIMARY_COST_BP,
                },
                "A3_stability": {
                    "passed": a3,
                    "positive_years": pos_years,
                    "total_years": len(yearly_summary),
                    "threshold": A3_MIN_POSITIVE_YEARS,
                    "all_regimes_positive": regimes_positive,
                },
                "A4_screen_slate": {
                    "passed": a4,
                    "mean_diff": screen_mean,
                    "win_ratio": screen_win,
                },
                "A5_integrity": {
                    "passed": a5,
                    "coverage_mean": coverage_mean,
                    "threshold": A5_MIN_COVERAGE,
                    "n1_passed": n1["passed"],
                },
                "A6_e1_contradiction": a6_block,
            },
            "reject_criteria": {
                "R1_negative_predictive_power": r1,
                "R2_noise": r2,
                "R3_net_non_positive": r3,
                "R4_bear_reversal": r4,
            },
            "all_numeric_passed": passed_all,
            "leakage_ok": leak_ok,
        },
        "per_date": per_date,
    }
