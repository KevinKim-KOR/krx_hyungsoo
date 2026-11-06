"""POC6-23 R0 참조 경로 · 행동별 20거래일 분기 정답 g — 통합 설계 V1 개정 2 §3 · 판정 A-6.

```text
참조     20bp R0(POC6-21 강화 없음 원본 정책) 하나 · 최초 공통 신호부터 현금 100 · 공통 신호일마다 `_weekly`
         직전 상태를 복제(판단일 상태 = 그날 체결 · 평가 · 보호 뒤) · 같은 시작의 POC6-21 simulate 와 장부 대조
분기     복제 상태 · end = T(E 를 1일로 센 20번째 한국 거래일 = D + 21) · 행동 의도 실행일 E = D + 2
         · D+1 ~ T 체결 · 평가 · 보호만(새 통상 계획 없음) · 매수 직전 슬롯 · 현금 재확인
정답     g(D, a) = [NAV_T(a) − NAV_T(KEEP)] / NAV_D · KEEP = 0 · T 의 열린 보유는 평가(가상 청산 없음)
제외     행동 집합을 먼저 고정 → KEEP 만(NORMAL_PENDING · NO_ACTION) · 한 행동이라도 평가 미확정(BRANCH_UNRESOLVED)
         이면 그 D 학습 상태 전체 제외(행동을 지워 최선 행동을 바꾸지 않음)
```
"""

from __future__ import annotations

import copy
from typing import Any

from app.decision_learning import actions as A
from app.decision_learning import policy as P
from app.trend_switch import policy as TP
from app.weekly_selection import data as D
from app.weekly_selection import features as F
from app.weekly_selection import policy as PO

CheckRequired = D.CheckRequired
HORIZON = 20
T_LAG = F.EXEC_LAG + HORIZON - 1  # T = D + 21
CURVE = "R0_REF"
_FIELDS = ("hold", "sell_live", "buy_live", "due", "reviews_after")


def _payload(st: PO._State) -> dict[str, Any]:
    """한 번의 deepcopy — 같은 의도 객체가 due · sell_live · buy_live 에 함께 있는 관계를 보존한다."""
    return copy.deepcopy(
        {
            **{k: getattr(st, k) for k in _FIELDS},
            "cash": st.cash,
            "first_plan_done": st.first_plan_done,
        }
    )


def _restore(p: D.Panel, payload: dict, end: int, cost: float) -> PO._State:
    st = PO._State(p, PO.Book(curve="BRANCH", cost=cost), end)
    pl = copy.deepcopy(payload)
    for k in _FIELDS:
        setattr(st, k, pl[k])
    st.cash, st.first_plan_done = pl["cash"], pl["first_plan_done"]
    return st


def reference(p: D.Panel, plans: dict[int, P.DPlan], start: int, end: int, cost):
    """(R0 참조 장부 · {D: (Snapshot · 복제 상태)})."""
    states: dict[int, tuple] = {}

    def decide(i, st, last_sell):
        states[i] = (A.snapshot(p, st, i), _payload(st))
        TP._weekly(p, st, plans[i].r0, i, False, last_sell)

    bk = P.walk(p, plans, start, end, cost, CURVE, decide)
    return bk, states


def reference_same(p, plans, start, end, cost, bk: PO.Book) -> bool:
    """참조 루프 장부 = 같은 시작 · 계획의 POC6-21 simulate(R0) 장부."""
    base = TP.simulate(
        p, {i: pl.r0 for i, pl in plans.items()}, start, end, cost, CURVE, False
    )
    return PO.to_json(base) == PO.to_json(bk)


def branch(p: D.Panel, payload: dict, i: int, a: A.Action, cost: float):
    """행동 a 를 D = i 에서 고른 20거래일 경로의 NAV_T(평가 미확정이면 None)."""
    t = i + T_LAG
    st = _restore(p, payload, t, cost)
    if a.sell is not None:
        st.intent(
            side="SELL",
            reason="EXIT",
            ticker=p.codes[a.sell],
            ticker_idx=a.sell,
            signal=p.axis[i],
            exec_idx=i + 2,
        )
    if a.buy is not None:
        st.intent(
            side="BUY",
            reason="ENTRY",
            ticker=p.codes[a.buy],
            ticker_idx=a.buy,
            signal=p.axis[i],
            exec_idx=i + 2,
            priority=1,
        )
    for k in range(i + 1, t + 1):
        PO._open(p, st, k, st.due.pop(k, []), cost)
        P.check_bounds(p, st, k)
        if not PO._close(p, st, k, i + 1):
            return None
        TP._protect_overlap(p, st, k)
    last = st.bk.ledger[-1]
    if last["date"] != p.axis[t]:
        raise CheckRequired(f"{p.axis[i]} 분기 마지막 평가일 {last['date']} ≠ T")
    return last["value"]


def label(p: D.Panel, pl: P.DPlan, snap, payload, i: int, cost: float) -> dict:
    """한 판단일의 행동 · g · 제외 사유(행동 집합을 먼저 고정)."""
    acts, why = A.allowed(snap, pl.r0.cands, set(pl.rows), cost, p.codes)
    rec: dict[str, Any] = {
        "nav": snap.nav,
        "cash": snap.cash,
        "held": {p.codes[j]: v for j, v in sorted(snap.held.items())},
        "sell_live": {p.codes[j]: r for j, r in sorted(snap.sell_live.items())},
        "actions": [A.name(a, p.codes) for a in acts],
        "g": None,
        "excluded": why,
    }
    if why is not None:
        return rec
    navs = [branch(p, payload, i, a, cost) for a in acts]
    bad = [A.name(a, p.codes) for a, v in zip(acts, navs) if v is None]
    if bad:
        rec.update(excluded="BRANCH_UNRESOLVED", unresolved=bad)
        return rec
    rec["nav_t"] = navs
    rec["g"] = [(v - navs[0]) / snap.nav for v in navs]
    return rec


def labels(p, plans, states, cost) -> dict[str, dict]:
    out = {}
    for i in sorted(states):
        snap, payload = states[i]
        if i + T_LAG >= len(p.axis):
            raise CheckRequired(f"{p.axis[i]} 정답 끝 T 가 날짜 축 밖")
        out[p.axis[i]] = label(p, plans[i], snap, payload, i, cost)
    return out
