"""POC6-11 성과 지표 · 회전율 · 보유기간 · bootstrap · 상태 축 · 판정 · report.md — 설계 §5 · §8.

```text
기준     전체 = 시작일 자산 100(전액 현금) → 마지막 종가 평가 · 보조 구간 = 직전 평가값을 기준으로 포함(재시작 없음)
CAGR     (끝/기준)^(365.25/경과 달력일) − 1 · MDD = 기준값을 첫 고점으로 둔 최대 낙폭(음수)
회전율   (전체 매수 명목 + 전체 매도 명목) / (2 × 일별 자산 평균 × 경과 연수) · 첫 계획 편입을 뺀 값도 공개
bootstrap 완결 주의 L−B 주간 수익 차이 · 13주 원형 블록 · 2,000회 · seed 20261026 · 평균 차이 95% 구간
판정     H1 = CAGR(L)−CAGR(B) ≥ 0.01 그리고 보조 3구간 중 2구간 이상 기간 수익 차이 > 0
         목적 = CAGR(L) > CAGR(K) · 위험 = MDD(L)−MDD(B) ≥ −0.05 · MDD(L)−MDD(K) ≥ −0.05 · 회전율(L) ≤ 6
         비용 = 40bp CAGR(L)−CAGR(B) > 0 · 넷 모두 = FURTHER_REVIEW_CANDIDATE
         CHECK_REQUIRED · DATA_SHORT · BUDGET_STOP = NOT_JUDGED · 어느 결과든 OPERATION_ADOPTION = NO
```
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any, Optional, Sequence

import numpy as np

from app.ml_strategy_performance import cagr as _cagr
from app.ml_strategy_performance import max_drawdown

GAP_MIN = 0.01
MDD_LIMIT = 0.05
TURNOVER_MAX = 6.0
SUB_WIN_MIN = 2
SELECT_TIE = 1e-12
START = 100.0
BLOCK_WEEKS = 13
BOOT_DRAWS = 2000
BOOT_SEED = 20261026
VALIDITY = ("OK", "CHECK_REQUIRED", "DATA_SHORT", "BUDGET_STOP")
PRICE_NOTE = (
    "봉인 KRX `KRX_BASEPRICE_CHAIN` 합성 가격지수의 모의 성과다. 분배금 포함 총수익 · 실제 계좌 · "
    "추천 채택이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO)."
)
# 유형 의존도 표시용(설명 전용 · 자격 · 판정에 쓰지 않음) — 종목의 마지막 저장 이름 키워드, 앞에서부터 처음 맞는 것.
TYPE_RULES = (
    ("CASH_LIKE", ("머니마켓", "CD금리", "KOFR", "SOFR", "단기자금", "MMF", "초단기")),
    (
        "BOND",
        (
            "채권",
            "국고채",
            "국채",
            "회사채",
            "단기채",
            "통안",
            "금융채",
            "크레딧",
            "물가채",
        ),
    ),
    (
        "OVERSEAS",
        (
            "미국",
            "나스닥",
            "S&P",
            "다우",
            "필라델피아",
            "중국",
            "차이나",
            "China",
            "CSI",
            "항셍",
            "홍콩",
            "일본",
            "니케이",
            "TOPIX",
            "유로",
            "유럽",
            "독일",
            "인도",
            "베트남",
            "대만",
            "글로벌",
            "선진국",
            "신흥국",
            "MSCI",
            "러시아",
            "브라질",
            "라틴",
            "아시아",
            "호주",
        ),
    ),
)


def asset_type(name: str) -> str:
    for label, keys in TYPE_RULES:
        if any(k in name for k in keys):
            return label
    return "UNMATCHED"


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def period(rows: Sequence[dict], base_date: str, base_value: float) -> dict[str, Any]:
    """기준(날짜 · 값) 뒤 rows 의 기간 수익 · CAGR · MDD · 회복."""
    vals = [r["value"] for r in rows]
    end = rows[-1]
    days = _days(base_date, end["date"])
    ret = end["value"] / base_value - 1.0
    eq = [v / base_value for v in vals]
    peak_v, peak_d, worst, wpeak, wpeak_v, wtrough = (
        base_value,
        base_date,
        0.0,
        None,
        None,
        None,
    )
    for r in rows:
        if r["value"] > peak_v:
            peak_v, peak_d = r["value"], r["date"]
        dd = r["value"] / peak_v - 1.0
        if dd < worst:
            worst, wpeak, wpeak_v, wtrough = dd, peak_d, peak_v, r["date"]
    recovered = None
    if worst < 0:
        recovered = next(
            (r["date"] for r in rows if r["date"] > wtrough and r["value"] >= wpeak_v),
            None,
        )
    return {
        "base_date": base_date,
        "base_value": base_value,
        "end_date": end["date"],
        "end_value": end["value"],
        "days": days,
        "return": ret,
        "cagr": _cagr(end["value"] / base_value, days),
        "mdd": max_drawdown(eq),
        "mdd_peak": wpeak,
        "mdd_trough": wtrough,
        "recovered": recovered,
        "recovery_days": None if recovered is None else _days(wtrough, recovered),
        "not_recovered": worst < 0 and recovered is None,
    }


def subperiods(ledger: Sequence[dict], start: str, base: float, bounds) -> list[dict]:
    out = []
    for lo, hi in bounds:
        rows = [r for r in ledger if lo <= r["date"] <= hi]
        before = [r for r in ledger if r["date"] < lo]
        bd, bv = (before[-1]["date"], before[-1]["value"]) if before else (start, base)
        out.append({"bounds": [lo, hi], **period(rows, bd, bv)})
    return out


def turnover(book: dict, ledger: Sequence[dict], start: str) -> dict[str, Any]:
    fills = book["fills"]
    days = _days(start, ledger[-1]["date"])
    years = days / 365.25
    avg = float(np.mean([r["value"] for r in ledger]))
    buy = sum(f["notional"] for f in fills if f["side"] == "BUY")
    sell = sum(f["notional"] for f in fills if f["side"] == "SELL")
    first_ids = {
        it["id"]
        for it in book["intents"]
        if it["side"] == "BUY"
        and book["plans"]
        and it.get("signal") == book["plans"][0]["signal"]
    }
    first_buy = sum(f["notional"] for f in fills if f.get("intent") in first_ids)
    denom = 2.0 * avg * years
    return {
        "buy_notional": buy,
        "sell_notional": sell,
        "first_plan_buy_notional": first_buy,
        "avg_value": avg,
        "years": years,
        "annual": (buy + sell) / denom if denom > 0 else None,
        "annual_ex_first_plan": (buy + sell - first_buy) / denom if denom > 0 else None,
    }


def holding_periods(book: dict, pos: dict[str, int], end: str) -> dict[str, Any]:
    open_: dict[str, dict] = {}
    closed, censored = [], []
    for f in book["fills"]:
        if f["side"] == "BUY":
            open_[f["ticker"]] = f
        else:
            b = open_.pop(f["ticker"])
            closed.append(
                {
                    "ticker": f["ticker"],
                    "entry": b["date"],
                    "exit": f["date"],
                    "market_days": pos[f["date"]] - pos[b["date"]],
                    "reason": f["reason"],
                }
            )
    for t, b in sorted(open_.items()):
        censored.append(
            {
                "ticker": t,
                "entry": b["date"],
                "market_days_to_end": pos[end] - pos[b["date"]],
            }
        )
    md = [c["market_days"] for c in closed]
    q = np.percentile(md, [10, 25, 50, 75, 90]).tolist() if md else None
    return {
        "closed": len(closed),
        "open_at_end": censored,
        "quantiles_10_25_50_75_90": q,
        "min": min(md) if md else None,
        "max": max(md) if md else None,
        "median": q[2] if q else None,
    }


def exposure(ledger: Sequence[dict]) -> dict[str, Any]:
    max_w, max_cash, counts = 0.0, 0.0, []
    for r in ledger:
        counts.append(len(r["pos"]))
        max_cash = max(max_cash, r["cash"] / r["value"])
        for u, c in r["pos"].values():
            max_w = max(max_w, u * c / r["value"])
    return {
        "max_single_weight": max_w,
        "max_cash_weight": max_cash,
        "avg_holdings": float(np.mean(counts)),
    }


def dependency(book: dict, names: dict[str, str], top: int = 5) -> dict[str, Any]:
    """종목별 손익 기여 = 매도 순대금 − 매수 예산(비용 포함) + 끝 평가 · 합 = 끝 자산 − 100."""
    contrib: dict[str, float] = {}
    for f in book["fills"]:
        sign = 1.0 if f["side"] == "SELL" else -1.0
        cash = (
            f["notional"] - f["cost"]
            if f["side"] == "SELL"
            else f["notional"] + f["cost"]
        )
        contrib[f["ticker"]] = contrib.get(f["ticker"], 0.0) + sign * cash
    last = book["ledger"][-1]
    for t, (u, c) in last["pos"].items():
        contrib[t] = contrib.get(t, 0.0) + u * c
    total = last["value"] - START
    ranked = sorted(contrib.items(), key=lambda kv: (-kv[1], kv[0]))
    by_type: dict[str, float] = {}
    for t, v in contrib.items():
        k = asset_type(names.get(t, ""))
        by_type[k] = by_type.get(k, 0.0) + v
    return {
        "total_pnl": total,
        "sum_check": sum(contrib.values()) - total,
        "top": [{"ticker": t, "name": names.get(t), "pnl": v} for t, v in ranked[:top]],
        "bottom": [
            {"ticker": t, "name": names.get(t), "pnl": v} for t, v in ranked[-top:]
        ],
        "by_type_pnl": dict(sorted(by_type.items())),
        "tickers": len(contrib),
        "type_rule": "마지막 저장 이름 키워드(설명 전용 · 판정 미사용)",
    }


def counts(book: dict) -> dict[str, Any]:
    fills: dict[str, int] = {}
    for f in book["fills"]:
        k = f"{f['side']}_{f['reason']}"
        fills[k] = fills.get(k, 0) + 1
    status: dict[str, int] = {}
    deferred = 0
    for it in book["intents"]:
        status[it["status"]] = status.get(it["status"], 0) + 1
        deferred += 1 if it.get("waited") else 0
    big = sum(1 for e in book["events"] if e["type"] == "BIG_MOVE")
    return {
        "fills": dict(sorted(fills.items())),
        "intent_status": dict(sorted(status.items())),
        "sells_ever_deferred": deferred,
        "big_move_records": big,
    }


def sharpe_0rf(ledger: Sequence[dict], base: float) -> Optional[float]:
    v = np.array([base] + [r["value"] for r in ledger])
    r = v[1:] / v[:-1] - 1.0
    s = float(np.std(r, ddof=1)) if len(r) > 1 else 0.0
    return float(np.mean(r)) / s * math.sqrt(252) if s > 0 else None


def curve(
    book: dict, start: str, bounds, pos: dict[str, int], names: dict[str, str]
) -> dict[str, Any]:
    if book["status"] != "OK":
        return {
            "status": book["status"],
            "unresolved": book["unresolved"],
            "end": book["end"],
        }
    led = book["ledger"]
    base = START
    out = {
        "status": "OK",
        "total": period(led, start, base),
        "subperiods": subperiods(led, start, base, bounds) if bounds else [],
        "turnover": turnover(book, led, start),
        "counts": counts(book),
        "end": book["end"],
        "sharpe_0rf_explain": sharpe_0rf(led, base),
    }
    if book["curve"] != "K":
        out["holding"] = holding_periods(book, pos, led[-1]["date"])
        out["exposure"] = exposure(led)
        out["dependency"] = dependency(book, names)
    return out


def weekly_returns(
    ledger: Sequence[dict], week_ends: set[str], base: float
) -> tuple[list, int]:
    """완결 주(주 마지막 거래일 = 정기 신호일)의 종가 평가 수익. 끝의 불완전 주 수를 함께 돌려준다."""
    out, prev = [], base
    for r in ledger:
        if r["date"] in week_ends:
            out.append((r["date"], r["value"] / prev - 1.0))
            prev = r["value"]
    tail = 1 if ledger and ledger[-1]["date"] not in week_ends else 0
    return out, tail


def bootstrap(diffs: Sequence[float]) -> dict[str, Any]:
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    rng = np.random.default_rng(BOOT_SEED)
    nb = -(-n // BLOCK_WEEKS)
    starts = rng.integers(0, n, size=(BOOT_DRAWS, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK_WEEKS)[None, None, :]) % n
    means = d[idx.reshape(BOOT_DRAWS, -1)[:, :n]].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "weeks": n,
        "mean_diff": float(d.mean()),
        "ci95": [float(lo), float(hi)],
        "uncertain": bool(lo <= 0.0 <= hi),
        "method": "circular block · 13주 · 2,000회 · seed 20261026 · numpy default_rng · "
        "percentile 2.5/97.5",
    }


def _avg_rank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x))
    ranks[order] = np.arange(1, len(x) + 1)
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    return np.bincount(inv, weights=ranks)[inv] / cnt[inv]


def rank_ic(pairs: dict[str, list]) -> dict[str, Any]:
    """신호별 (점수, z) 순위 상관의 평균 — 설명용(판정 미사용 · 설계 §8-1)."""
    vals = []
    for _d, ps in sorted(pairs.items()):
        if len(ps) < 3:
            continue
        rs = _avg_rank(np.array([a for a, _ in ps], dtype=float))
        rz = _avg_rank(np.array([b for _, b in ps], dtype=float))
        if rs.std() == 0 or rz.std() == 0:
            continue
        vals.append(float(np.corrcoef(rs, rz)[0, 1]))
    return {
        "dates": len(vals),
        "mean": float(np.mean(vals)) if vals else None,
        "note": "설명용 · 판정 미사용",
    }


def select(val: dict[str, dict]) -> dict[str, Any]:
    """검증 기본 비용 CAGR 이 높은 것(차이 ≤ 1e-12 = ML_A · MOM20 우선)."""

    def pick(a: str, b: str) -> str:
        ca, cb = val[a]["total"]["cagr"], val[b]["total"]["cagr"]
        return b if cb - ca > SELECT_TIE else a

    ml, mom = pick("ML_A", "ML_B"), pick("MOM20", "MOM120")
    return {
        "L": ml,
        "B": mom,
        "cagr": {
            k: val[k]["total"]["cagr"] for k in ("ML_A", "ML_B", "MOM20", "MOM120")
        },
        "rule": "검증 20bp CAGR 최대 · 차이 ≤ 1e-12 이면 ML_A · MOM20",
    }


def judge(validity: str, test: Optional[dict], boot: Optional[dict]) -> dict[str, Any]:
    base = {
        "validity": validity,
        "OPERATION_ADOPTION": "NO",
        "TOTAL_RETURN_VALIDATED": "NO",
    }
    if validity != "OK" or test is None:
        return {
            **base,
            "h1": "NOT_JUDGED",
            "candidate": "NOT_JUDGED",
            "uncertainty": None,
            "reasons": [],
        }
    L, B, K = test["L_20"], test["B_20"], test["K_20"]
    L4, B4 = test["L_40"], test["B_40"]
    gap = L["total"]["cagr"] - B["total"]["cagr"]
    sub_diff = [
        a["return"] - b["return"] for a, b in zip(L["subperiods"], B["subperiods"])
    ]
    wins = sum(1 for x in sub_diff if x > 0)
    h1 = gap >= GAP_MIN and wins >= SUB_WIN_MIN
    purpose = L["total"]["cagr"] > K["total"]["cagr"]
    mdd_b = L["total"]["mdd"] - B["total"]["mdd"]
    mdd_k = L["total"]["mdd"] - K["total"]["mdd"]
    to = L["turnover"]["annual"]
    risk = mdd_b >= -MDD_LIMIT and mdd_k >= -MDD_LIMIT and to <= TURNOVER_MAX
    gap40 = L4["total"]["cagr"] - B4["total"]["cagr"]
    cost = gap40 > 0
    reasons = []
    if not h1:
        reasons.append("H1_NOT_SHOWN")
    if not purpose:
        reasons.append("L_NOT_ABOVE_K")
    if not mdd_b >= -MDD_LIMIT:
        reasons.append("MDD_WORSE_THAN_B")
    if not mdd_k >= -MDD_LIMIT:
        reasons.append("MDD_WORSE_THAN_K")
    if not to <= TURNOVER_MAX:
        reasons.append("TURNOVER_ABOVE_6")
    if not cost:
        reasons.append("COST_SENSITIVE_40BP")
    return {
        **base,
        "h1": "PRICE_GAIN_OBSERVED" if h1 else "PRICE_GAIN_NOT_SHOWN",
        "candidate": (
            "FURTHER_REVIEW_CANDIDATE"
            if h1 and purpose and risk and cost
            else "NOT_CANDIDATE"
        ),
        "uncertainty": (
            None
            if boot is None
            else ("UNCERTAIN" if boot["uncertain"] else "CI_EXCLUDES_ZERO")
        ),
        "values": {
            "cagr_gap_L_B": gap,
            "sub_return_diff_L_B": sub_diff,
            "sub_wins": wins,
            "cagr_L_minus_K": L["total"]["cagr"] - K["total"]["cagr"],
            "mdd_L_minus_B": mdd_b,
            "mdd_L_minus_K": mdd_k,
            "turnover_L": to,
            "cagr_gap_L_B_40bp": gap40,
        },
        "reasons": reasons,
    }


ORDER = (
    "ML_A",
    "ML_B",
    "MOM20",
    "MOM120",
    "K",
    "L_20",
    "B_20",
    "K_20",
    "L_40",
    "B_40",
    "K_40",
)


def _ordered(d: dict) -> list:
    """표 순서 고정(저장 JSON 은 키를 정렬하므로 dict 순서에 기대지 않음)."""
    return [(k, d[k]) for k in ORDER if k in d] + sorted(
        (k, v) for k, v in d.items() if k not in ORDER
    )


def _pct(x: Optional[float], d: int = 2) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def markdown(rep: dict) -> str:
    j = rep["judgment"]
    lines = [
        "# POC6-11 H1 주간 ETF 상대성과 선별 — 공식 실행 보고",
        "",
        PRICE_NOTE,
        "",
        "```text",
        f"VALIDITY   = {j['validity']}",
        f"H1         = {j['h1']}",
        f"CANDIDATE  = {j['candidate']}",
        f"UNCERTAIN  = {j.get('uncertainty')}",
        "OPERATION_ADOPTION = NO · TOTAL_RETURN_VALIDATED = NO",
        "```",
        "",
    ]
    if rep.get("stop"):
        lines += ["## 멈춘 이유", "", f"- {rep['stop']}"]
        for part in ("validation", "test"):
            for k, c in _ordered(rep.get(part) or {}):
                for x in (
                    ((c.get("unresolved") or {}).get("items") or [])
                    if c["status"] != "OK"
                    else []
                ):
                    first = c["unresolved"].get("first_unresolved")
                    lines.append(
                        f"- 미확정 {part} {k}: {x.get('ticker', '—')} · 최초 {first} · "
                        f"마지막 유효 {x.get('last_valid', '—')} · 원인 {x.get('cause')} · "
                        f"진단용 마지막 평가 {x.get('last_value_diagnostic', '—')}"
                    )
        lines.append("")
    sel = rep.get("selection")
    val = rep.get("validation") or {}
    if val:
        lines += [
            "## 검증 구간(설정 선택 · 20bp)",
            "",
            "| 곡선 | 상태 | CAGR | MDD | 회전율 |",
            "|---|---|---:|---:|---:|",
        ]
        for k, c in _ordered(val):
            if c["status"] == "OK":
                lines.append(
                    f"| {k} | OK | {_pct(c['total']['cagr'])} | {_pct(c['total']['mdd'])} | "
                    f"{c['turnover']['annual']:.2f} |"
                )
            else:
                lines.append(f"| {k} | {c['status']} | — | — | — |")
        lines.append("")
    if sel:
        lines += [f"선택: L = **{sel['L']}** · B = **{sel['B']}** ({sel['rule']})", ""]
    test = rep.get("test") or {}
    if test:
        lines += [
            "## 시험 구간",
            "",
            "| 곡선 | 상태 | 기간 수익 | CAGR | MDD | 회전율 | 회복 |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for k, c in _ordered(test):
            if c["status"] == "OK":
                t = c["total"]
                rec = "미회복" if t["not_recovered"] else (t["recovered"] or "—")
                lines.append(
                    f"| {k} | OK | {_pct(t['return'])} | {_pct(t['cagr'])} | {_pct(t['mdd'])} | "
                    f"{c['turnover']['annual']:.2f} | {rec} |"
                )
            else:
                lines.append(f"| {k} | {c['status']} | — | — | — | — | — |")
        lines.append("")
        if all(test.get(k, {}).get("status") == "OK" for k in ("L_20", "B_20", "K_20")):
            lines += [
                "보조 구간(20bp · 기간 수익)",
                "",
                "| 구간 | L | B | K |",
                "|---|---:|---:|---:|",
            ]
            for n, sub in enumerate(test["L_20"]["subperiods"]):
                lo, hi = sub["bounds"]
                vals = [
                    test[k]["subperiods"][n]["return"] for k in ("L_20", "B_20", "K_20")
                ]
                lines.append(
                    f"| {lo} ~ {hi} | " + " | ".join(_pct(v) for v in vals) + " |"
                )
            lines.append("")
    if j.get("values"):
        v = j["values"]
        lines += [
            "## 판정 값(반올림 전 값으로 비교)",
            "",
            f"- CAGR(L) − CAGR(B) = {v['cagr_gap_L_B']:.6f} (기준 ≥ 0.01) · "
            f"보조 구간 우위 {v['sub_wins']}/3",
            f"- CAGR(L) − CAGR(K) = {v['cagr_L_minus_K']:.6f} (기준 > 0)",
            f"- MDD(L) − MDD(B) = {v['mdd_L_minus_B']:.6f} · "
            f"MDD(L) − MDD(K) = {v['mdd_L_minus_K']:.6f} "
            f"(기준 ≥ −0.05) · 회전율(L) = {v['turnover_L']:.4f} (기준 ≤ 6)",
            f"- 40bp CAGR(L) − CAGR(B) = {v['cagr_gap_L_B_40bp']:.6f} (기준 > 0)",
            f"- 사유: {', '.join(j['reasons']) or '없음'}",
            "",
        ]
    boot = rep.get("bootstrap")
    if boot:
        lines += [
            "## 주간 L−B 차이 bootstrap",
            "",
            f"- 완결 주 {boot['weeks']} · 끝 불완전 주 제외 {rep.get('bootstrap_tail_excluded', 0)}",
            f"- 평균 차이 {boot['mean_diff']:.6f} · "
            f"95% 구간 [{boot['ci95'][0]:.6f}, {boot['ci95'][1]:.6f}]",
            "- 이미 관측한 경로에 관한 한정 추정이다. 미래 우위를 증명하지 않는다.",
            "",
        ]
    hold = ((rep.get("test") or {}).get("L_20") or {}).get("holding") or {}
    lines += [
        "## 네 기간(설계 §3-2 · 서로 다름)",
        "",
        "- 과거 관측: 입력 창 5 · 20 · 60 · 120 거래일(신호일 t 종가까지)",
        "- 예측 목표: t+2 합성 시가 ~ 그날을 첫날로 센 60번째 거래일 종가의 KODEX200 대비 순위"
        "(60일째 자동 청산 없음)",
        f"- 실제 보유: 운용 규칙(10위 유지 · 보호 이탈 · 이연)으로 정해짐 · 시험 L 중앙 "
        f"{hold.get('median', '—')} 거래일(청산 {hold.get('closed', '—')}건)",
        "- 재학습: 분기 1회 · cutoff 에서 5달력년 · 정답 끝이 cutoff 보다 5거래일 이상 앞선 사례",
        "",
    ]
    lines += [
        "## 한정",
        "",
        "- 시험 기간은 과거 연구에서 이미 본 시기와 겹친다(처음 보는 독립 표본 · 전향 입증 아님).",
        "- 비용 20bp · 40bp 는 연구 가정이다(실측 계좌 요금 · 세금 아님).",
        "- 유형 표시는 종목의 마지막 저장 이름 키워드로 나눈 설명용 구분이다(판정 미사용).",
        "",
    ]
    return "\n".join(lines)
