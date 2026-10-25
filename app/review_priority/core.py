"""POC6-09 — 경계 동점 비중 · 날짜별 P/R · 균등 기대 · 날짜 평균 · 표본 · 판정(설계 §4 ~ §6 · PLAN §4).

```text
순서   날짜 · 범위마다 점수가 낮은 종목부터 k = min(3, n) · 경계값 q 와 같은 종목은 (k - m) / b(정확한 동등)
Y      실제 D20 ≤ -0.08(포함) · M = ΣY · TP = Σ w·Y · FP = k - TP · FN = M - TP
P · R  P = TP / k(모든 날짜) · R = TP / M(M > 0 날짜만 · 아니면 null) · 균등 기대 P = M / n · R = k / n
평균   날짜마다 같은 비중(전체 · 구간 1 · 2 · 3) · R 은 정의된 날짜 수를 함께
판정   범위 × 모델(RIDGE_P · HGB_P) × 기준(PRICE20_RULE · MEDIAN_P · UNIFORM_EXPECTATION)
       표본 부족 = DATA_SHORT · ① 전체 P 차 ≥ 0.05 ② 구간 P 차 양수 ≥ 2구간 ③ 구간 P 차 ≥ -0.05
       ④ 전체 R ≥ 기준 → 모두 = PRIORITY_RESEARCH_SIGNAL · 아니면 PRIORITY_GAIN_NOT_SHOWN
수      비중 · TP · P · R · 평균 · 차이 · 판정 = 정확한 분수(Fraction) — 같은 값이 부동소수 오차로 경계를
       넘지 않게(검토 L1) · 저장 · 보고만 float(`to_json`)
```
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from typing import Any, Optional

K = 3
TAIL = -0.08
FOLDS = 3
METHODS = ("PRICE20_RULE", "MEDIAN_P", "RIDGE_P", "HGB_P")
UNIFORM = "UNIFORM_EXPECTATION"
MODELS = ("RIDGE_P", "HGB_P")
BASELINES = ("PRICE20_RULE", "MEDIAN_P", UNIFORM)
P_MARGIN = Fraction(1, 20)  # 전체 P 절대 차이 0.05(%p 로 5)
FOLD_WINS = 2
FOLD_WORSE = Fraction(1, 20)
MIN_DATES, MIN_TICKERS = 20, 3
MIN_FOLD_DATES, MIN_FOLD_TICKERS = 5, 2

SIGNAL = "PRIORITY_RESEARCH_SIGNAL"
NOT_SHOWN = "PRIORITY_GAIN_NOT_SHOWN"
DATA_SHORT = "DATA_SHORT"


def conditions() -> dict[str, Any]:
    """고정 계약(설계 §4 ~ §6) — protocol 에 적고 verify 가 코드 값과 대조한다."""
    return {
        "k": K,
        "tail": TAIL,
        "tail_rule": "Y = 1[실제 D20 ≤ -0.08](경계 포함)",
        "order": "점수 낮은 순(PRICE20 = 저장 P chg20 · 세 구성 = [-1, 0] 제한 예측)",
        "tie": "경계값 q 와 같은 종목 = (k - m) / b · 저장 숫자 정확 동등(반올림 · epsilon 없음)",
        "methods": list(METHODS),
        "uniform": "P = M / n · R = k / n(M > 0)",
        "models": list(MODELS),
        "baselines": list(BASELINES),
        "averaging": "날짜 같은 비중 · P = 모든 날짜 · R = M > 0 날짜만",
        "arithmetic": "비중 · P · R · 평균 · 차이 · 판정 = 정확한 분수 · 저장 · 보고 = float",
        "sample": {
            "min_dates": MIN_DATES,
            "min_tickers": MIN_TICKERS,
            "min_fold_dates": MIN_FOLD_DATES,
            "min_fold_tickers": MIN_FOLD_TICKERS,
        },
        "judge": {
            "p_margin": float(P_MARGIN),
            "fold_wins": FOLD_WINS,
            "fold_worse": float(FOLD_WORSE),
            "r_rule": "전체 R ≥ 기준 전체 R",
        },
    }


def boundary_weights(scores: dict[str, float], k: int = K) -> dict[str, Any]:
    """낮은 점수 우선 k 개의 선택 비중(분수) — 경계 동점은 균등 선택의 평균(종목 코드 순서 없음)."""
    n = len(scores)
    if n == 0:
        raise ValueError("빈 날짜")
    k = min(k, n)
    q = sorted(scores.values())[k - 1]
    m = sum(1 for v in scores.values() if v < q)
    b = sum(1 for v in scores.values() if v == q)
    share = Fraction(k - m, b)
    weights = {
        t: (Fraction(1) if v < q else share if v == q else Fraction(0))
        for t, v in scores.items()
    }
    return {"weights": weights, "k": k, "q": q, "below": m, "tie": b}


def day(rows: list[dict[str, Any]], k: int = K) -> dict[str, Any]:
    """한 범위 · 한 날짜(rows = [{ticker, truth, scores{method}}]) — 방법별 비중 · TP · P · R + 균등 기대."""
    n = len(rows)
    y = {r["ticker"]: 1 if r["truth"] <= TAIL else 0 for r in rows}
    M = sum(y.values())
    kk = min(k, n)
    out: dict[str, Any] = {"n": n, "k": kk, "M": M, "y": y, "methods": {}}
    for method in METHODS:
        bw = boundary_weights({r["ticker"]: r["scores"][method] for r in rows}, k)
        tp = sum((w * y[t] for t, w in bw["weights"].items()), Fraction(0))
        out["methods"][method] = {
            "weights": bw["weights"],
            "q": bw["q"],
            "below": bw["below"],
            "tie": bw["tie"],
            "boundary_tie": bw["below"] + bw["tie"] > bw["k"],
            **_counts(tp, kk, M),
        }
    out["methods"][UNIFORM] = {
        **_counts(Fraction(kk * M, n), kk, M),
        "P": Fraction(M, n),
        "R": Fraction(kk, n) if M > 0 else None,
    }
    return out


def _counts(tp: Fraction, k: int, M: int) -> dict[str, Any]:
    return {
        "TP": tp,
        "FP": k - tp,
        "FN": M - tp,
        "P": tp / k,
        "R": tp / M if M > 0 else None,
    }


def _mean(xs: list[Fraction]) -> Optional[Fraction]:
    return sum(xs, Fraction(0)) / len(xs) if xs else None


def summarize(days: list[dict[str, Any]]) -> dict[str, Any]:
    """days = [{date, fold, day}] 한 범위 — 방법별 전체 · 구간 날짜 평균 · 분모 · 미포착 · 동점 · 반복 선택."""
    out: dict[str, Any] = {}
    for method in METHODS + (UNIFORM,):
        parts: dict[str, Any] = {}
        for part in ("all", 0, 1, 2):
            sel = [d for d in days if part == "all" or d["fold"] == part]
            ms = [d["day"]["methods"][method] for d in sel]
            rs = [m["R"] for m in ms if m["R"] is not None]
            parts[str(part)] = {
                "P": _mean([m["P"] for m in ms]),
                "R": _mean(rs),
                "dates": len(ms),
                "r_dates": len(rs),
                "miss": _mean([1 - r for r in rs]),  # 큰 하락 미포착 비중(1 - R)
                "not_hit": _mean(
                    [1 - m["P"] for m in ms]
                ),  # 선택 중 큰 하락 미해당(1 - P)
                "TP": sum((m["TP"] for m in ms), Fraction(0)),
                "FP": sum((m["FP"] for m in ms), Fraction(0)),
                "FN": sum((m["FN"] for m in ms), Fraction(0)),
            }
        out[method] = parts
        if method != UNIFORM:
            out[method]["ties"] = _ties(days, method)
            out[method]["selection"] = _selection(days, method)
    return out


def _ties(days, method) -> dict[str, Any]:
    t = [d["day"]["methods"][method] for d in days]
    bt = [m for m in t if m["boundary_tie"]]
    return {
        "boundary_tie_dates": len(bt),
        "max_boundary_tie": max((m["tie"] for m in bt), default=0),
    }


def _selection(days, method) -> dict[str, Any]:
    """반복 선택 집중 — 종목별 비중 합 ÷ (k × 날짜)."""
    total: dict[str, Fraction] = defaultdict(Fraction)
    slots = 0
    for d in days:
        m = d["day"]["methods"][method]
        slots += d["day"]["k"]
        for t, w in m["weights"].items():
            total[t] += w
    share = {t: v / slots for t, v in sorted(total.items()) if v > 0}
    top3 = sorted(share.values(), reverse=True)[:3]
    return {
        "share": share,
        "tickers_selected": len(share),
        "top3_share": sum(top3, Fraction(0)),
    }


def per_ticker(days: list[dict[str, Any]]) -> dict[str, Any]:
    """종목별 내역(설계 §7) — 행 · 큰 하락 행 · 방법별 선택 비중 합 · 적중(w × Y) 합."""
    out: dict[str, Any] = {}
    for d in days:
        dd = d["day"]
        for t, yv in dd["y"].items():
            e = out.setdefault(
                t,
                {
                    "rows": 0,
                    "tail": 0,
                    "methods": {
                        m: {"selected": Fraction(0), "hit": Fraction(0)}
                        for m in METHODS
                    },
                },
            )
            e["rows"] += 1
            e["tail"] += yv
            for m in METHODS:
                w = dd["methods"][m]["weights"][t]
                e["methods"][m]["selected"] += w
                e["methods"][m]["hit"] += w * yv
    return dict(sorted(out.items()))


def sample(days: list[dict[str, Any]]) -> dict[str, Any]:
    """표본 충족 — 큰 하락 날짜 · 종목(전체 20 · 3 · 구간마다 5 · 2)."""

    def count(sel):
        dates = [d for d in sel if d["day"]["M"] > 0]
        tickers = {t for d in sel for t, v in d["day"]["y"].items() if v}
        return {"tail_dates": len(dates), "tail_tickers": len(tickers)}

    overall = count(days)
    folds = [count([d for d in days if d["fold"] == k]) for k in range(FOLDS)]
    enough = (
        overall["tail_dates"] >= MIN_DATES
        and overall["tail_tickers"] >= MIN_TICKERS
        and all(
            f["tail_dates"] >= MIN_FOLD_DATES and f["tail_tickers"] >= MIN_FOLD_TICKERS
            for f in folds
        )
    )
    return {
        "enough": enough,
        **overall,
        "folds": folds,
        "dates": len(days),
        "rows": sum(d["day"]["n"] for d in days),
        "tail_rows": sum(d["day"]["M"] for d in days),
        "dates_m_over_k": sum(1 for d in days if d["day"]["M"] > d["day"]["k"]),
    }


def judge(summary: dict[str, Any], samp: dict[str, Any], model: str) -> dict[str, Any]:
    """한 범위 · 한 모델 — 세 기준 각각과 네 조건(정확한 분수 · 차이 = 소수 · %p 로는 ×100)."""
    per: dict[str, Any] = {}
    me = summary[model]
    for base in BASELINES:
        bs = summary[base]
        overall = me["all"]["P"] - bs["all"]["P"]
        folds = [me[str(k)]["P"] - bs[str(k)]["P"] for k in range(FOLDS)]
        r_m, r_b = me["all"]["R"], bs["all"]["R"]
        c = {
            "p_margin": overall >= P_MARGIN,
            "fold_wins": sum(1 for d in folds if d > 0) >= FOLD_WINS,
            "no_fold_worse": all(d >= -FOLD_WORSE for d in folds),
            "r_not_lower": r_m is not None and r_b is not None and r_m >= r_b,
        }
        per[base] = {
            "p_diff": overall,
            "fold_p_diff": folds,
            "r_diff": (r_m - r_b) if r_m is not None and r_b is not None else None,
            "conditions": c,
            "pass": all(c.values()),
        }
    best = max(BASELINES, key=lambda b: summary[b]["all"]["P"])
    if not samp["enough"]:
        status = DATA_SHORT
    else:
        status = SIGNAL if all(v["pass"] for v in per.values()) else NOT_SHOWN
    return {
        "status": status,
        "against": per,
        "best_baseline": best,
        "p_diff_vs_best": me["all"]["P"] - summary[best]["all"]["P"],
    }


def to_json(obj: Any) -> Any:
    """분수 → float(저장 · 보고 · 비교 대조용) — dict · list 를 따라 내려간다."""
    if isinstance(obj, Fraction):
        return float(obj)
    if isinstance(obj, dict):
        return {k: to_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_json(v) for v in obj]
    return obj
