"""POC6-23 일별 루프 · P/S 주간 선택 장부 — 통합 설계 V1 개정 2 §2 · §4 · §5 · 판정 A-3 · A-4.

```text
루프     POC6-21 simulate 와 같은 순서: H1 `_open` → 보유 ≤ 5 · 현금 ≥ −1e-9 재확인 → 마지막 전량 매도 기록
         → H1 `_close`(평가 미확정 = CHECK_REQUIRED 장부) → `_protect_overlap` → 계획일이면 주간 의도
첫 계획  P/S/R 공통 = POC6-21 R0 최초 편입(강화 없음 · 최대 5) · 최초 편입은 학습 효용으로 세지 않음
이후     P/S = 허용 행동(actions)마다 q = βᵀz − k/s_g(KEEP = 0) · q 최대 하나(동점 = 고정 순서) · 새 문턱 없음
         · 분기 모형 = 잠금 배정(cutoff ≤ D) · u = 그 분기 μ · σ(평가 자료로 다시 맞추지 않음)
Q4       자격 밖 보유 = 통상 판단 보류 · 보호 계속 · 자격도 사유도 없는 보유 = CHECK_REQUIRED
의도     SELL = 사유 EXIT · 간격 = D − 진입 체결 · BUY = 사유 ENTRY · priority 1 · 간격 = D − 마지막 전량 매도
         · 최근 = 간격 0 ~ 10(POC6-21 거래 분석과 같은 분류 · 강화 없음)
```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.decision_learning import actions as A
from app.decision_learning import learn as LN
from app.trend_switch import policy as TP
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO

CheckRequired = D.CheckRequired
CASH_TOL = 1e-9


@dataclass
class DPlan:
    """한 공통 계획 신호의 고정 입력(P/S 공통 · 곡선마다 모형만 다름)."""

    signal: int
    r0: (
        TP.Plan
    )  # R0 점수 · 후보(RET_120 상위 5) · 자격 밖 사유 — 첫 계획 · R 장부 · 후보 순서
    rows: dict[int, list]  # 자격 종목 → 34열 원값(None = 정상 결측)
    quarter: str


def check_bounds(p: D.Panel, st: PO._State, i: int) -> None:
    """매수 직전 재확인의 결과 — 기존 체결 함수의 보장에 기대지 않는다(판정 A-3)."""
    if len(st.hold) > A.SLOTS or not st.cash >= -CASH_TOL:
        raise CheckRequired(
            f"{p.axis[i]} 보유 {len(st.hold)}종 · 현금 {st.cash!r} — 슬롯 · 현금 경계 위반"
        )


def walk(
    p: D.Panel,
    plans: dict,
    start: int,
    end: int,
    cost: float,
    curve: str,
    decide: Callable[[int, PO._State, dict], None],
) -> PO.Book:
    bk = PO.Book(curve=curve, cost=cost)
    st = PO._State(p, bk, end)
    last_sell: dict[int, int] = {}
    ci, seen = p.ci, 0
    for i in range(min([*plans, start]), end + 1):
        PO._open(p, st, i, st.due.pop(i, []), cost)
        check_bounds(p, st, i)
        for f in bk.fills[seen:]:
            if f["side"] == "SELL":
                last_sell[ci[f["ticker"]]] = i
        seen = len(bk.fills)
        if not PO._close(p, st, i, start):
            for its in st.due.values():
                for it in its:
                    it["status"] = "NOT_RUN_CHECK_REQUIRED"
            return bk
        TP._protect_overlap(p, st, i)
        if i in plans:
            decide(i, st, last_sell)
            st.first_plan_done = True
    for it in st.sell_live.values():
        if it["status"] == "DEFERRED":
            it["status"] = "OPEN_AT_END"
    bk.end = {
        "date": p.axis[end],
        "holdings": sorted(p.codes[j] for j in st.hold),
        "open_sells": sorted(
            p.codes[j]
            for j, it in st.sell_live.items()
            if it["status"] == "OPEN_AT_END"
        ),
        "unexecuted": sum(
            1 for it in bk.intents if it["status"] == "UNEXECUTED_AFTER_END"
        ),
    }
    return bk


def units(pl: DPlan, model: dict, js: list[int]) -> tuple[dict[int, np.ndarray], dict]:
    """(u · ETF 별 정상 결측 대치 칸 수)."""
    u, miss = {}, {}
    for j in js:
        u[j], miss[j] = LN.transform(
            pl.rows[j], model["mu"], model["sigma"], model["constant"]
        )
    return u, miss


def score(sn, a, u, beta: np.ndarray, sg: float, cost: float) -> float:
    if a.kind == "KEEP":
        return 0.0
    b, s, k = A.amounts(sn, a, cost)
    q = float(beta @ A.z_vector(a, b, s, u)) - k / sg
    if not np.isfinite(q):
        raise CheckRequired("행동 점수 비유한 값")
    return q


def choose(p, st, pl: DPlan, model: dict, mid: str, i: int, last_sell, cost) -> None:
    held, selling = set(st.hold), set(st.sell_live)
    held_out, exiting = [], []
    for j in sorted(held, key=lambda j: p.codes[j]):
        if j in selling:
            exiting.append([p.codes[j], st.sell_live[j]["reason"]])
        elif j in pl.rows:
            continue
        elif j in pl.r0.excluded:
            held_out.append([p.codes[j], pl.r0.excluded[j]])
        else:
            raise CheckRequired(f"{p.axis[i]} 보유 {p.codes[j]} 자격 · 제외 사유 없음")
    sn = A.snapshot(p, st, i)
    acts, why = A.allowed(sn, pl.r0.cands, set(pl.rows), cost, p.codes)
    u, miss = units(pl, model, A.needed(acts))
    # 행동 중복 사용 수(D · ETF · 열 기준 대치 칸 수와 따로 · 판정 A-2 6)
    uses = sum(miss[j] for a in acts[1:] for j in (a.sell, a.buy) if j is not None)
    beta = np.asarray(model["beta"], dtype=float)
    scored = [(a, score(sn, a, u, beta, model["s_g"], cost)) for a in acts]
    best, q = scored[0]
    for a, v in scored[1:]:  # 고정 순서 · 같은 값이면 앞
        if v > q:
            best, q = a, v
    common = dict(signal=p.axis[i], exec_idx=i + 2, score=q, model=mid)
    exits, entries = [], []
    if best.sell is not None:
        j = best.sell
        gap = i - st.hold[j]["entry_idx"]
        st.intent(
            side="SELL",
            reason="EXIT",
            ticker=p.codes[j],
            ticker_idx=j,
            gap=gap,
            recent=0 <= gap <= TP.RECENT_DAYS,
            action=A.name(best, p.codes),
            **common,
        )
        exits.append(p.codes[j])
    if best.buy is not None:
        j = best.buy
        gap = i - last_sell[j] if j in last_sell else None
        st.intent(
            side="BUY",
            reason="ENTRY",
            ticker=p.codes[j],
            ticker_idx=j,
            priority=1,
            cand_rank=pl.r0.cands.index(j) + 1,
            gap=gap,
            recent=gap is not None and 0 <= gap <= TP.RECENT_DAYS,
            action=A.name(best, p.codes),
            **common,
        )
        entries.append(p.codes[j])
    st.bk.plans.append(
        {
            "signal": p.axis[i],
            "model": mid,
            "first": False,
            "eligible": len(pl.rows),
            "cands": [p.codes[j] for j in pl.r0.cands],
            "held_not_eligible": held_out,
            "held_exiting": exiting,
            "keep_only": why,
            "nav": sn.nav,
            "cash": sn.cash,
            "actions": [[A.name(a, p.codes), v] for a, v in scored],
            "chosen": A.name(best, p.codes),
            "exits": exits,
            "entries": entries,
            "imputed_cells": sum(miss.values()),
            "imputed_action_uses": uses,
        }
    )


def simulate(
    p: D.Panel,
    plans: dict[int, DPlan],
    models: dict[str, dict],
    kind: str,
    start: int,
    end: int,
    cost: float,
    curve: str,
) -> PO.Book:
    """P 또는 S 장부 — models[분기] = {mu · sigma · constant · s_g · P · S(각 beta)}(20bp 학습값 그대로)."""

    def decide(i, st, last_sell):
        pl = plans[i]
        if not st.first_plan_done:
            TP._weekly(p, st, pl.r0, i, False, last_sell)
            return
        m = models[pl.quarter]
        model = {**m, "beta": m[kind]["beta"]}
        choose(p, st, pl, model, f"{pl.quarter}_{kind}", i, last_sell, cost)

    return walk(p, plans, start, end, cost, curve, decide)


def simulate_r(p, plans: dict[int, DPlan], start, end, cost, curve) -> PO.Book:
    """R = POC6-21 R0(강화 없음) 원본 정책 그대로."""
    return TP.simulate(
        p, {i: pl.r0 for i, pl in plans.items()}, start, end, cost, curve, False
    )
