"""POC4-03 — 경계 동점 부분 가중 바스켓 · 모델 지표(10,000회 CI) · paired 차이 · 강건성 (PLAN §2-4~§2-6).

- 바스켓(필수 보완 D): 점수 내림차순 k = max(1, round(n×0.1)) · 경계 점수 묶음 전부 포함 · 묶음 편입도
  (k − 위 행 수)/묶음 크기 — 가중치는 점수와 k 로만 정한다(label 미사용). 편입도가 0/1 이면 02A 값과 같다.
- 이 바스켓을 gross · net 비용 grid · turnover · win rate · 전략 성과 전체에 쓴다. 02A 코드 순서 값은
  `code_order_reference` 에 민감도 비교값으로만 둔다.
- 전략 성과는 `app/ml_strategy_performance.py` 의 공개 순수 함수로 같은 산식을 다시 조립한다(원본 수정 없음).
- bootstrap 은 기존 `circular_block_bootstrap_ci` 를 10,000회 · seed 42 · 블록 6 으로 직접 부른다.

DB·파일에 접근하지 않는다.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Optional, Sequence

from app.krx_sealed_reader import PRICE_BASIS
from app.ml_pit_bias_report import basket_series, strategy_block
from app.ml_score_validity_eval import COST_BPS_GRID, PRIMARY_COST_BP, QUANTILE_BUCKETS
from app.ml_score_validity_metrics import (
    circular_block_bootstrap_ci,
    cost_drag,
    mean,
    median,
    stdev,
    t_stat,
    win_rate,
)
from app.ml_strategy_performance import (
    COMMISSION_BP,
    LEGACY_ALL_IN_BP,
    PRIMARY_SLIPPAGE_BP,
    SLIPPAGE_BP_GRID,
    STRESS_SLIPPAGE_BP,
    TRANSACTION_TAX_BP,
    annualized_ratio,
    annualized_volatility,
    cagr,
    cost_scenarios,
    equity_curve,
    max_drawdown,
)

BOOTSTRAP_ITERATIONS = 10000
BOOTSTRAP_SEED = 42
BOOTSTRAP_BLOCK = 6
PERIOD_COUNT = 3
NET_KEY = str(int(PRIMARY_COST_BP))
STRATEGY_REFERENCE_SCENARIO = f"decomposed_slippage_{int(PRIMARY_SLIPPAGE_BP)}bp"


# --- 경계 동점 부분 가중 바스켓 --------------------------------------------------------


def partial_top(rows: Sequence[tuple[str, float, float]], fraction: float) -> dict:
    """(종목, 점수, label) → 편입도 · 평균 · 동점 진단. 편입도는 점수와 k 로만 정한다."""
    if not rows:
        return {
            "weights": {},
            "mean": None,
            "k": 0,
            "n": 0,
            "above": 0,
            "tie_group": 0,
            "boundary_tie": False,
            "unique_scores": 0,
        }
    ordered = sorted(rows, key=lambda x: x[1], reverse=True)
    n = len(ordered)
    k = max(1, int(round(n * fraction)))
    s_k = ordered[k - 1][1]
    above = [r for r in ordered if r[1] > s_k]
    group = [r for r in ordered if r[1] == s_k]
    share = 1.0 if len(group) == k - len(above) else (k - len(above)) / len(group)
    weights = {r[0]: 1.0 for r in above}
    weights.update({r[0]: share for r in group})
    total = sum(weights[code] * label for code, _score, label in above + group)
    return {
        "weights": weights,
        "mean": total / k,
        "k": k,
        "n": n,
        "above": len(above),
        "tie_group": len(group),
        "boundary_tie": len(above) + len(group) > k,
        "unique_scores": len({r[1] for r in ordered}),
    }


def weighted_replaced(prev: Optional[dict], cur: dict, k: int) -> Optional[float]:
    """Σ max(0, 편입도_t − 편입도_(t−1)) / k — 편입도 0/1 이면 |cur∖prev|/|cur| 와 같다."""
    if not cur or prev is None:
        return None
    return sum(max(0.0, w - prev.get(c, 0.0)) for c, w in cur.items()) / k


def weighted_basket_series(items: Sequence[tuple]) -> dict:
    """(신호일, 평균, 편입도, k) → gross · 교체비율 · 비용별 net (02A `basket_series` 와 같은 규칙)."""
    gross: list[float] = []
    turnovers: list[float] = []
    net = {str(int(c)): [] for c in COST_BPS_GRID}
    net_by_date: dict[str, dict[str, float]] = {}
    prev = None
    for day, value, weights, k in items:
        if value is None:
            prev = weights
            continue
        rep = weighted_replaced(prev, weights, k) if prev is not None else None
        if rep is not None:
            turnovers.append(rep)
        gross.append(value)
        net_by_date[day] = {}
        for c in COST_BPS_GRID:
            v = value - cost_drag(rep, c)
            net[str(int(c))].append(v)
            net_by_date[day][str(int(c))] = v
        prev = weights
    return {
        "gross": gross,
        "turnover": turnovers,
        "net": net,
        "net_by_date": net_by_date,
    }


def weighted_strategy(items: Sequence[dict], benchmark_closes: dict) -> dict:
    """items: {signal_date, entry_date, exit_date, mean, weights, k} — 기존 전략 산식(공개 순수 함수) 그대로."""
    periods, excluded, prev = [], [], None
    for it in items:
        if it["mean"] is None:
            prev = it["weights"]
            excluded.append(
                {"signal_date": it["signal_date"], "reason": "상위 10% 없음"}
            )
            continue
        rep = (
            weighted_replaced(prev, it["weights"], it["k"])
            if prev is not None
            else None
        )
        prev = it["weights"]
        k0 = benchmark_closes.get(it["entry_date"])
        k1 = benchmark_closes.get(it["exit_date"])
        if not k0 or not k1:
            excluded.append(
                {"signal_date": it["signal_date"], "reason": "KODEX200 종가 없음"}
            )
            continue
        bench = k1 / k0 - 1.0
        periods.append(
            {
                "entry_date": it["entry_date"],
                "exit_date": it["exit_date"],
                "benchmark_return": bench,
                "gross_return": it["mean"] + bench,
                "replaced_fraction": rep,
            }
        )
    base = {
        "basket": "경계 동점 부분 가중 (PLAN §2-4)",
        "price_basis": PRICE_BASIS,
        "cost_model": {
            "transaction_tax_bp": TRANSACTION_TAX_BP,
            "commission_bp": COMMISSION_BP,
            "slippage_bp_grid": list(SLIPPAGE_BP_GRID),
            "strategy_reference_one_way_bp": COMMISSION_BP + PRIMARY_SLIPPAGE_BP,
            "legacy_all_in_bp": LEGACY_ALL_IN_BP,
        },
        "periods": len(periods),
        "excluded_periods": excluded,
    }
    if not periods:
        return {**base, "status": "NO_PERIODS", "scenarios": {}}
    days = (
        date.fromisoformat(periods[-1]["exit_date"])
        - date.fromisoformat(periods[0]["entry_date"])
    ).days
    ppy = len(periods) / (days / 365.25) if days > 0 else 12.0
    scenarios, curves = {}, {}
    for sc in cost_scenarios():
        net = [
            p["gross_return"] - cost_drag(p["replaced_fraction"], sc["one_way_bp"])
            for p in periods
        ]
        bench = [p["benchmark_return"] for p in periods]
        active = [a - b for a, b in zip(net, bench)]
        eq, beq = equity_curve(net), equity_curve(bench)
        rel = [e / b for e, b in zip(eq, beq)]
        if sc["name"] == STRATEGY_REFERENCE_SCENARIO:
            curves = {
                "strategy_equity": eq,
                "benchmark_equity": beq,
                "relative_wealth": rel,
            }
        scenarios[sc["name"]] = {
            **sc,
            "role": _role(sc),
            "role_02a": sc["role"],
            "absolute": {
                "end_equity": eq[-1],
                "cagr": cagr(eq[-1], days),
                "mdd": max_drawdown(eq),
                "annualized_volatility": annualized_volatility(net, ppy),
                "sharpe_0rf": annualized_ratio(net, ppy),
            },
            "relative": {
                "benchmark_end_equity": beq[-1],
                "benchmark_cagr": cagr(beq[-1], days),
                "benchmark_mdd": max_drawdown(beq),
                "relative_wealth_end": rel[-1],
                "relative_mdd": max_drawdown(rel),
                "mean_active_return": statistics.fmean(active),
                "tracking_error": annualized_volatility(active, ppy),
                "information_ratio": annualized_ratio(active, ppy),
            },
        }
    return {
        **base,
        "status": "OK",
        "first_entry_date": periods[0]["entry_date"],
        "last_exit_date": periods[-1]["exit_date"],
        "calendar_days": days,
        "periods_per_year": ppy,
        "scenarios": scenarios,
        "strategy_reference_curves": {
            "exit_dates": [p["exit_date"] for p in periods],
            **curves,
        },
    }


def _role(sc: dict) -> str:
    """POC4-03 비용 역할 — 전략 11.5bp = STRATEGY_REFERENCE (판정 PRIMARY 는 top-decile net 25bp)."""
    if sc["name"] == STRATEGY_REFERENCE_SCENARIO:
        return "STRATEGY_REFERENCE"
    if sc["slippage_bp"] is None:
        return "LEGACY_COMPARISON"
    return "STRESS" if sc["slippage_bp"] == STRESS_SLIPPAGE_BP else "SENSITIVITY"


# --- 요약 · paired ------------------------------------------------------------------


def ci(series: Sequence[float]) -> Optional[dict]:
    got = circular_block_bootstrap_ci(
        list(series),
        block_len=BOOTSTRAP_BLOCK,
        iterations=BOOTSTRAP_ITERATIONS,
        seed=BOOTSTRAP_SEED,
    )
    return None if got is None else {"low": got[0], "high": got[1]}


def summary(series: Sequence[float], *, with_ci: bool = True) -> dict:
    out = {
        "n": len(series),
        "mean": mean(series),
        "median": median(series),
        "sd": stdev(series),
        "t_stat_reference_only": t_stat(series),
    }
    if with_ci:
        out["bootstrap_ci_95"] = ci(series)
    return out


def paired(
    a: dict, b: dict, why_a: Optional[dict] = None, why_b: Optional[dict] = None
) -> dict:
    """날짜별 a − b (둘 다 값이 있는 날) — 평균·중앙값·10,000회 CI · 빠진 날짜와 사유."""
    why_a, why_b = why_a or {}, why_b or {}
    dates = sorted(set(a) | set(b))
    both = [d for d in dates if a.get(d) is not None and b.get(d) is not None]
    diffs = [a[d] - b[d] for d in both]
    return {
        "n_paired": len(both),
        "mean_diff": mean(diffs),
        "median_diff": median(diffs),
        "bootstrap_ci_95": ci(diffs),
        "missing_dates": [
            {
                "date": d,
                "a_missing": a.get(d) is None,
                "b_missing": b.get(d) is None,
                "a_reason": why_a.get(d),
                "b_reason": why_b.get(d),
            }
            for d in dates
            if d not in both
        ],
    }


# --- 모델 블록 -----------------------------------------------------------------------


def _items(entries, key: str) -> list[tuple]:
    return [
        (
            e["record"]["signal_date"],
            e[key]["mean"],
            e[key]["weights"],
            e[key]["k"],
        )
        for e in entries
    ]


def _strategy_items(entries, key: str) -> list[dict]:
    return [
        {
            "signal_date": e["record"]["signal_date"],
            "entry_date": e["record"]["entry_date"],
            "exit_date": e["record"]["exit_date"],
            "mean": e[key]["mean"],
            "weights": e[key]["weights"],
            "k": e[key]["k"],
        }
        for e in entries
    ]


def _none_reason(record: dict, metric: str) -> str:
    if record["split"].get("status") == "NO_MODEL":
        return "NO_MODEL 날"
    if metric == "net25":
        return "top-decile 없음 (평가 단면 0)"
    if record["n_filter"] < 2:
        return "평가 단면 2개 미만"
    return "점수 또는 label 이 상수 (Spearman 정의 불가)"


def model_series(entries) -> dict:
    """날짜별 IC · net25(부분 가중) · 값이 없는 날의 사유 — paired·강건성·연도 표 입력."""
    main = weighted_basket_series(_items(entries, "basket"))
    out: dict = {"ic": {}, "net25": {}, "ic_why": {}, "net25_why": {}}
    for e in entries:
        rec = e["record"]
        day = rec["signal_date"]
        out["ic"][day] = rec["ic_filter"]
        out["net25"][day] = main["net_by_date"].get(day, {}).get(NET_KEY)
        for metric in ("ic", "net25"):
            if out[metric][day] is None:
                out[f"{metric}_why"][day] = _none_reason(rec, metric)
    return out


def yearly_table(series: dict, dates: Sequence[str]) -> dict:
    """모델 하나의 연도별 IC·net25 평균 — 전체 시계열의 날짜별 값을 잘라 쓴다 (§2-6)."""
    out = {}
    for y in sorted({d[:4] for d in dates}):
        days = [d for d in dates if d[:4] == y]
        ic = [series["ic"][d] for d in days if series["ic"].get(d) is not None]
        net = [series["net25"][d] for d in days if series["net25"].get(d) is not None]
        out[y] = {"dates": len(days), "ic_mean": mean(ic), "net25_mean": mean(net)}
    return out


def model_block(entries, benchmark_closes: dict) -> dict:
    """모델 하나의 집계 — entries = 날짜별 {record, basket, sensitivity_basket}."""
    records = [e["record"] for e in entries]
    ic = [r["ic_filter"] for r in records if r["ic_filter"] is not None]
    ic_all = [r["ic_all"] for r in records if r["ic_all"] is not None]
    spread = []
    for r in records:
        q = r["quantile_means"]
        hi, lo = q.get(str(QUANTILE_BUCKETS - 1)), q.get("0")
        if hi is not None and lo is not None:
            spread.append(hi - lo)
    main = weighted_basket_series(_items(entries, "basket"))
    sens = weighted_basket_series(_items(entries, "sensitivity_basket"))
    sens_ic = [
        r["sensitivity"]["ic"] for r in records if r["sensitivity"]["ic"] is not None
    ]
    code_order = basket_series(
        [
            (r["signal_date"], r["top_decile_mean"], r["top_decile_tickers"])
            for r in records
        ]
    )
    ties = [e["basket"] for e in entries]
    return {
        "ic_filter": summary(ic),
        "ic_all": summary(ic_all),
        "quantile_spread_q5_minus_q1": summary(spread),
        "quantile_spread_note": "5분위 경계 동점은 02A 규칙(코드 순서)으로 갈린다 · 판정 미사용",
        "top_decile_gross": summary(main["gross"]),
        "top_decile_net_by_cost_bp": {k: summary(v) for k, v in main["net"].items()},
        "turnover": summary(main["turnover"], with_ci=False),
        "top_decile_win_rate_by_date": win_rate(main["gross"]),
        "strategy_performance": weighted_strategy(
            _strategy_items(entries, "basket"), benchmark_closes
        ),
        "sensitivity_label": {
            "label_basis": "OFFICIAL_REFERENCE_SENSITIVITY",
            "ic": summary(sens_ic),
            "top_decile_gross": summary(sens["gross"]),
            "top_decile_net_25bp": summary(sens["net"][NET_KEY]),
            "strategy_performance": weighted_strategy(
                _strategy_items(entries, "sensitivity_basket"), benchmark_closes
            ),
        },
        "code_order_reference": {
            "role": "02A 종목코드 순서 바스켓 — 민감도 비교값 (판정에 쓰지 않는다)",
            "ci_note": "CI 는 10,000회 — 02A 공개값(2,000회)과 CI 를 직접 대조하지 않는다",
            "top_decile_gross": summary(code_order["gross"]),
            "top_decile_net_25bp": summary(code_order["net"][NET_KEY]),
            "turnover": summary(code_order["turnover"], with_ci=False),
            "strategy_performance": strategy_block(
                records, benchmark_closes, sensitivity=False
            ),
        },
        "ties": {
            "boundary_tie_dates": sum(1 for b in ties if b["boundary_tie"]),
            "max_boundary_group": max((b["tie_group"] for b in ties), default=0),
            "min_unique_share": min(
                (b["unique_scores"] / b["n"] for b in ties if b["n"]), default=None
            ),
        },
    }


# --- 강건성 ---------------------------------------------------------------------------


def _mean_over(diff: dict, days) -> Optional[float]:
    vals = [diff[d] for d in days if d in diff]
    return mean(vals)


def _diffs(a: dict, b: dict) -> dict:
    return {
        d: a[d] - b[d] for d in a if d in b and a[d] is not None and b[d] is not None
    }


def period_bounds(dates: Sequence[str], count: int = PERIOD_COUNT) -> list[list[str]]:
    """시간순으로 이어진 `count` 구간 — 앞 구간부터 한 개씩 더 (146 → 49 · 49 · 48)."""
    n = len(dates)
    sizes = [n // count + (1 if i < n % count else 0) for i in range(count)]
    out, start = [], 0
    for s in sizes:
        out.append(list(dates[start : start + s]))  # noqa: E203
        start += s
    return out


def robustness(a: dict, b: dict, dates: Sequence[str]) -> dict:
    """a·b = model_series. 연도별 · 3구간 · leave-one-year-out · 2026 제외 (방향만 판정 · §2-6)."""
    ic, net = _diffs(a["ic"], b["ic"]), _diffs(a["net25"], b["net25"])
    years = sorted({d[:4] for d in dates})
    yearly = {}
    for y in years:
        days = [d for d in dates if d[:4] == y]
        yearly[y] = {
            "dates": len(days),
            "ic_mean_diff": _mean_over(ic, days),
            "net25_mean_diff": _mean_over(net, days),
        }
    periods = []
    for block in period_bounds(dates):
        m_ic, m_net = _mean_over(ic, block), _mean_over(net, block)
        periods.append(
            {
                "first": block[0] if block else None,
                "last": block[-1] if block else None,
                "dates": len(block),
                "ic_mean_diff": m_ic,
                "net25_mean_diff": m_net,
                "both_positive": bool(
                    m_ic is not None and m_net is not None and m_ic > 0 and m_net > 0
                ),
            }
        )
    loyo = {}
    for key, diff in (("ic", ic), ("net25", net)):
        by_year = {y: _mean_over(diff, [d for d in dates if d[:4] != y]) for y in years}
        valid = {y: v for y, v in by_year.items() if v is not None}
        worst = min(valid, key=lambda y: (valid[y], y)) if valid else None
        loyo[key] = {
            "by_excluded_year": by_year,
            "min": valid[worst] if worst else None,
            "worst_excluded_year": worst,
            "complete": len(valid) == len(years),
        }
    no26 = [d for d in dates if d[:4] != "2026"]
    return {
        "yearly": yearly,
        "periods": periods,
        "leave_one_year_out": loyo,
        "excluding_2026": {
            "dates": len(no26),
            "ic_mean_diff": _mean_over(ic, no26),
            "net25_mean_diff": _mean_over(net, no26),
        },
    }
