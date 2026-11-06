"""POC6-23 판정 축 · 거래 분석 · Q4 노출 · report.md — 통합 설계 V1 개정 2 §5(H1 지표 · bootstrap 재사용).

```text
AC3 학습 목적   20bp CAGR(S) − CAGR(P) ≥ 0.01 그리고 보조 3구간 중 2구간 이상 기간 수익 S > P
                → DECISION_GAIN_OBSERVED / NOT_SHOWN(P 와 S 의 차이에만 학습 목적의 효용을 귀속)
AC4 사용자 목적 20bp CAGR(S) − CAGR(R) ≥ 0.01 그리고 CAGR(S) − CAGR(K) ≥ 0.01
AC5 위험 · 부담 20 · 40bp 각각 |MDD(S)| − |MDD(P)| ≤ 0.05 · |MDD(S)| − |MDD(K)| ≤ 0.05
                · 최장 고점 미회복(S) − (K) ≤ 126 거래일 · 연 회전율(S) ≤ 6
AC6 비용 스트레스 40bp CAGR(S) > P · R · K 각각(재학습 없음)
불확실성        20bp 주간 S − P · 13주 원형 블록 · 2,000회 · seed 20261026 · 하한 > 0 = 이번 연구 안 양의 근거
후보            AC3 ~ AC6 와 bootstrap 하한 > 0 모두 = FURTHER_REVIEW_CANDIDATE · 그 밖 NOT_CANDIDATE
무효            정상 완료 아님 = NOT_JUDGED · 어느 결과든 OPERATION_ADOPTION = NO · TOTAL_RETURN_VALIDATED = NO
```
"""

from __future__ import annotations

from typing import Any, Optional

from app.trend_switch import trades as TR
from app.weekly_selection import policy as PO
from app.weekly_selection import report as R

GAP_MIN = 0.01
SUB_WIN_MIN = 2
MDD_LIMIT = 0.05
UW_LIMIT = 126
TURNOVER_MAX = 6.0
BOOTSTRAP = {"block": R.BLOCK_WEEKS, "draws": R.BOOT_DRAWS, "seed": R.BOOT_SEED}
NAMES = ("P", "S", "R", "K")
ORDER = tuple(f"{k}_{c}" for c in ("20", "40") for k in NAMES)
NOTE = (
    "봉인 KRX 합성 가격지수와 POC6-19 연구 사본으로 만든 이미 본 기간의 탐색적 회고 모의 비교다. 새 독립 시험 · "
    "총수익 검증 · 실제 권고 채택이 아니다(TOTAL_RETURN_VALIDATED=NO · OPERATION_ADOPTION=NO)."
)
_NJ = "NOT_JUDGED"


def recipe() -> dict[str, Any]:
    return {
        "gap_min": GAP_MIN,
        "sub_win_min": SUB_WIN_MIN,
        "mdd_limit": MDD_LIMIT,
        "underwater_limit": UW_LIMIT,
        "turnover_max": TURNOVER_MAX,
        "bootstrap": {"pair": "S_20 − P_20 · 평가 구간 완결 주 전체", **BOOTSTRAP},
    }


# ── 거래 분석 · Q4 노출 ──────────────────────────────────────────────────────────


def q4(bk: dict) -> dict[str, Any]:
    """자격 밖 보유 보류 — 주 비율 · 금액 비중(평균 · 최대) · 종목 · 일(인과 해석 아님)."""
    plans = {pl["signal"]: pl for pl in bk["plans"]}
    status: dict[str, bool] = {}
    weights = []
    for r in bk["ledger"]:
        pl = plans.get(r["date"])
        if pl is not None:
            out_now = {t for t, _w in pl["held_not_eligible"]}
            status = {t: t in out_now for t in r["pos"]}
        held = sum(u * c for t, (u, c) in r["pos"].items() if status.get(t))
        weights.append(held / r["value"])
    weeks = sum(1 for pl in bk["plans"] if pl["held_not_eligible"])
    return {
        "plans": len(bk["plans"]),
        "weeks_with_held_out": weeks,
        "week_share": weeks / len(bk["plans"]) if bk["plans"] else None,
        "avg_weight": sum(weights) / len(weights) if weights else None,
        "max_weight": max(weights) if weights else None,
        **TR.held_out(bk),
    }


def decisions(bk: dict) -> dict[str, Any]:
    """P/S 계획 — 고른 행동 종류 · KEEP 만인 사유 · 정상 결측 대치 칸(D · ETF · 열 기준)."""
    chosen: dict[str, int] = {}
    keep_only: dict[str, int] = {}
    imputed = uses = 0
    for pl in bk["plans"]:
        if "chosen" not in pl:
            continue
        kind = pl["chosen"].split(":")[0]
        chosen[kind] = chosen.get(kind, 0) + 1
        if pl["keep_only"]:
            keep_only[pl["keep_only"]] = keep_only.get(pl["keep_only"], 0) + 1
        imputed += pl["imputed_cells"]
        uses += pl["imputed_action_uses"]
    return {
        "chosen": dict(sorted(chosen.items())),
        "keep_only": dict(sorted(keep_only.items())),
        "imputed_cells": imputed,
        "imputed_action_uses": uses,
    }


def analyze(p, bk: dict) -> dict[str, Any]:
    """POC6-21 거래 분석(재진입 · 재이탈 · 직전 손익 · 묶음 · 회복 · 현금 · 보류) — 강화 검토 칸은 없음."""
    view = {
        **bk,
        "plans": [
            {"entry_reviews": [], "exit_reviews": [], **pl} for pl in bk["plans"]
        ],
    }
    out = TR.analyze(p, view, PO.START_VALUE)
    out.pop("reviews")
    out["q4"] = q4(bk)
    out["decisions"] = decisions(bk)
    return out


def extra(p, books: dict[str, dict], bounds=None) -> dict[str, dict]:
    pos = {d: k for k, d in enumerate(p.axis)}
    out = {}
    for n, b in books.items():
        if b["status"] != "OK":
            continue
        led = b["ledger"]
        if n.startswith("K_"):
            buy = b["fills"][0] if b["fills"] else None
            out[n] = {
                "underwater": TR.underwater(led, PO.START_VALUE),
                "cash": TR.cash(led),
                "costs_total": sum(f["cost"] for f in b["fills"]),
                "holding": {
                    "entry": buy and buy["date"],
                    "market_days_to_end": buy
                    and pos[led[-1]["date"]] - pos[buy["date"]],
                },
            }
        else:
            out[n] = analyze(p, b)
        out[n]["underwater_sub"] = TR.underwater_sub(led, bounds, PO.START_VALUE)
    return out


# ── 판정 ────────────────────────────────────────────────────────────────────────


def _cagr(c: dict) -> float:
    return c["total"]["cagr"]


def _dd(c: dict) -> float:
    return abs(c["total"]["mdd"])


def _to(c: dict) -> float:
    return c["turnover"]["annual"]


def _uw(ex: dict) -> int:
    return ex["underwater"]["longest_days"]


def judge(
    validity: str, test: Optional[dict], ex: Optional[dict], boot: Optional[dict]
) -> dict[str, Any]:
    base = {
        "validity": validity,
        "OPERATION_ADOPTION": "NO",
        "TOTAL_RETURN_VALIDATED": "NO",
    }
    if validity != "OK" or test is None or ex is None or boot is None:
        return {
            **base,
            "decision_gain": _NJ,
            "purpose": _NJ,
            "risk_burden": _NJ,
            "cost_stress": _NJ,
            "uncertainty": None,
            "candidate": _NJ,
            "reasons": [],
        }
    P, S, Rr, K = (test[f"{k}_20"] for k in NAMES)
    P4, S4, R4, K4 = (test[f"{k}_40"] for k in NAMES)
    reasons = []
    gap = _cagr(S) - _cagr(P)
    sub_diff = [
        a["return"] - b["return"] for a, b in zip(S["subperiods"], P["subperiods"])
    ]
    wins = sum(1 for x in sub_diff if x > 0)
    gain = gap >= GAP_MIN and wins >= SUB_WIN_MIN
    if not gain:
        reasons.append("DECISION_GAIN_NOT_SHOWN")
    gap_r, gap_k = _cagr(S) - _cagr(Rr), _cagr(S) - _cagr(K)
    purpose = gap_r >= GAP_MIN and gap_k >= GAP_MIN
    for bad, why in (
        (not gap_r >= GAP_MIN, "S_NOT_1PP_ABOVE_R"),
        (not gap_k >= GAP_MIN, "S_NOT_1PP_ABOVE_K"),
    ):
        if bad:
            reasons.append(why)
    risk_vals = {}
    risk = True
    for c, (s, p_, k) in (("20", (S, P, K)), ("40", (S4, P4, K4))):
        vals = {
            "mdd_S_minus_P": _dd(s) - _dd(p_),
            "mdd_S_minus_K": _dd(s) - _dd(k),
            "underwater_S_minus_K": _uw(ex[f"S_{c}"]) - _uw(ex[f"K_{c}"]),
            "turnover_S": _to(s),
        }
        risk_vals[c] = vals
        for bad, why in (
            (not vals["mdd_S_minus_P"] <= MDD_LIMIT, f"MDD_WORSE_THAN_P_{c}"),
            (not vals["mdd_S_minus_K"] <= MDD_LIMIT, f"MDD_WORSE_THAN_K_{c}"),
            (not vals["underwater_S_minus_K"] <= UW_LIMIT, f"UNDERWATER_LONGER_{c}"),
            (not vals["turnover_S"] <= TURNOVER_MAX, f"TURNOVER_ABOVE_6_{c}"),
        ):
            if bad:
                risk = False
                reasons.append(why)
    c40 = {
        "P": _cagr(S4) - _cagr(P4),
        "R": _cagr(S4) - _cagr(R4),
        "K": _cagr(S4) - _cagr(K4),
    }
    cost = all(v > 0 for v in c40.values())
    reasons += [f"COST_40BP_NOT_ABOVE_{k}" for k, v in c40.items() if not v > 0]
    lo, hi = boot["ci95"]
    unc = (
        "POSITIVE_IN_STUDY"
        if lo > 0
        else ("NEGATIVE_IN_STUDY" if hi < 0 else "UNCERTAIN")
    )
    candidate = gain and purpose and risk and cost and lo > 0
    if not lo > 0:
        reasons.append("BOOTSTRAP_LOWER_NOT_ABOVE_0")
    return {
        **base,
        "decision_gain": "DECISION_GAIN_OBSERVED" if gain else "NOT_SHOWN",
        "purpose": "PURPOSE_MET" if purpose else "PURPOSE_NOT_MET",
        "risk_burden": "RISK_BURDEN_MET" if risk else "RISK_BURDEN_NOT_MET",
        "cost_stress": "COST_STRESS_MET" if cost else "COST_STRESS_NOT_MET",
        "uncertainty": unc,
        "candidate": "FURTHER_REVIEW_CANDIDATE" if candidate else "NOT_CANDIDATE",
        "values": {
            "cagr_gap_S_P_20": gap,
            "sub_return_diff_S_P": sub_diff,
            "sub_wins": wins,
            "cagr_gap_S_R_20": gap_r,
            "cagr_gap_S_K_20": gap_k,
            "risk": risk_vals,
            "cagr_gap_S_40": c40,
            "bootstrap_ci95": [lo, hi],
        },
        "reasons": reasons,
    }


# ── report.md ───────────────────────────────────────────────────────────────────


def _pct(x: Optional[float], d: int = 2) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def _ordered(d: dict) -> list:
    return [(k, d[k]) for k in ORDER if k in d] + sorted(
        (k, v) for k, v in d.items() if k not in ORDER
    )


def _curves(part: dict, ex: dict, title: str) -> list[str]:
    lines = [
        title,
        "",
        "| 장부 | 상태 | 기간 수익 | CAGR | MDD | 회전율 | 최장 고점 미회복(거래일) | 끝 미회복 | 평균 현금 비중 | 총비용 |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for k, c in _ordered(part):
        if c["status"] != "OK":
            lines.append(f"| {k} | {c['status']} | — | — | — | — | — | — | — | — |")
            continue
        t, e = c["total"], ex.get(k) or {}
        uw, cash = e.get("underwater") or {}, e.get("cash") or {}
        end = f"예 · {uw['days_at_end']}일" if uw.get("underwater_at_end") else "아니오"
        cost = e.get("costs_total")
        lines.append(
            f"| {k} | OK | {_pct(t['return'])} | {_pct(t['cagr'])} | {_pct(t['mdd'])} | "
            f"{c['turnover']['annual']:.2f} | {uw.get('longest_days', '—')} | {end} | "
            f"{_pct(cash.get('avg_cash_weight'))} | {'—' if cost is None else f'{cost:.4f}'} |"
        )
    return lines + [""]


def _trades(ex: dict, title: str) -> list[str]:
    lines = [
        title,
        "",
        "| 장부 | 진입 · 재진입 · 단기 재진입 | 통상 · 단기 재이탈 · 보호 · 열림 | 묶음(거래 · 순손익) | "
        "Q4 보류(주 · 평균/최대 금액 비중) | 고른 행동 | KEEP 만 | 결측 대치 칸 |",
        "|---|---|---|---|---|---|---|---:|",
    ]
    for k, a in _ordered(ex):
        if "by_entry_kind" not in a:
            continue
        ein = "/".join(
            str(a["by_entry_kind"][x]["trades"])
            for x in ("ENTRY", "REENTRY", "SHORT_REENTRY")
        )
        eout = "/".join(
            str(a["by_exit_kind"][x]["trades"])
            for x in ("EXIT", "SHORT_REEXIT", "PROTECT", "OPEN")
        )
        b, q, dc = a["bundles"], a["q4"], a["decisions"]
        lines.append(
            f"| {k} | {ein} | {eout} | "
            f"{b['bundles']}({b['trades_in_bundles']} · {b['pnl_closed']:.2f}) | "
            f"{q['weeks_with_held_out']}/{q['plans']} · "
            f"{_pct(q['avg_weight'])}/{_pct(q['max_weight'])} | "
            f"{dc['chosen'] or '—'} | {dc['keep_only'] or '—'} | {dc['imputed_cells']} |"
        )
    return lines + [""]


def _learning(rows: list[dict]) -> list[str]:
    lines = [
        "## 분기 학습(정답 · 수치 조건)",
        "",
        "| 분기 | 창 상한 | 유효 D | 행 | 제외(사유) | s_g | P 상태 · 절대 차이 | S 상태 · 절대 차이 · 상계 여유 |",
        "|---|---:|---:|---:|---|---:|---|---|",
    ]
    for r in rows:
        fp, fs = r.get("P") or {}, r.get("S") or {}
        sg = "—" if r.get("s_g") is None else f"{r['s_g']:.6f}"
        lines.append(
            f"| {r['id']} | {r['upper']} | {r['valid']} | {r.get('rows', '—')} | "
            f"{r['excluded'] or '—'} | "
            f"{sg} | "
            f"{fp.get('status', '—')} · {fp.get('abs_diff', '—')} | "
            f"{fs.get('status', '—')} · {fs.get('abs_diff', '—')} · {fs.get('upper_margin', '—')} |"
        )
    return lines + [""]


def markdown(rep: dict) -> str:
    j = rep.get("judgment") or {}
    lines = [
        "# POC6-23 비용을 반영한 주간 의사결정 학습 — 실행 보고",
        "",
        f"- 잠금 `{rep.get('lock_id')}` · 실행 `{rep.get('run_id')}`",
        f"- {rep.get('note')}",
        f"- {rep.get('price_note')}",
        "",
    ]
    if rep.get("stop"):
        lines += [f"**정지**: {rep['stop']}", ""]
    lines += [
        "## 판정",
        "",
        f"- 유효성 {j.get('validity')} · 학습 목적(AC3) {j.get('decision_gain')} · 사용자 목적(AC4) "
        f"{j.get('purpose')} · 위험 · 부담(AC5) {j.get('risk_burden')} · 비용 스트레스(AC6) "
        f"{j.get('cost_stress')}",
        f"- 불확실성 {j.get('uncertainty')} · 후보 {j.get('candidate')} · OPERATION_ADOPTION="
        f"{j.get('OPERATION_ADOPTION')} · TOTAL_RETURN_VALIDATED={j.get('TOTAL_RETURN_VALIDATED')}",
        f"- 사유 {', '.join(j.get('reasons') or []) or '—'}",
        "",
    ]
    if j.get("values"):
        v = j["values"]
        lines += [
            f"- CAGR S − P(20bp) {_pct(v['cagr_gap_S_P_20'])} · 보조 구간 S − P "
            f"{[_pct(x) for x in v['sub_return_diff_S_P']]} · S − R {_pct(v['cagr_gap_S_R_20'])} · "
            f"S − K {_pct(v['cagr_gap_S_K_20'])}",
            f"- 40bp CAGR S − (P · R · K) "
            f"{[_pct(v['cagr_gap_S_40'][k]) for k in ('P', 'R', 'K')]} · "
            f"bootstrap(주간 S − P) 95% {[f'{x:.6f}' for x in v['bootstrap_ci95']]}",
            "",
        ]
    if rep.get("reference"):
        r = rep["reference"]
        lines += [
            "## R0 참조 경로",
            "",
            f"- 상태 {r.get('status')} · POC6-21 simulate 와 같음 {r.get('same_as_poc6_21')} · "
            f"{r.get('start')} ~ {r.get('end')} · 판단일 {r.get('states')} · 체결 {r.get('fills')}",
            f"- 정답 제외 사유 {r.get('excluded') or '—'}",
            "",
        ]
    if rep.get("learning"):
        lines += _learning(rep["learning"])
    for key, title in (
        ("validation", "선행 재생 2018 ~ 2020"),
        ("test", "주 평가 2021 ~ 2026-09-21"),
    ):
        if rep.get(key):
            lines += _curves(rep[key], rep.get(f"{key}_trades") or {}, f"## {title}")
            lines += _trades(
                rep.get(f"{key}_trades") or {}, f"### {title} — 거래 · Q4 · 행동"
            )
    if rep.get("bootstrap"):
        b = rep["bootstrap"]
        lines += [
            "## 불확실성",
            "",
            f"- 주간 S_20 − P_20 · {b['weeks']}주 · 평균 {b['mean_diff']:.6f} · 95% "
            f"[{b['ci95'][0]:.6f}, {b['ci95'][1]:.6f}] · 끝 불완전 주 제외 "
            f"{rep.get('bootstrap_tail_excluded')}",
            "",
        ]
    return "\n".join(lines) + "\n"
