"""POC6-23 허용 행동 · 예정 금액 · 70칸 입력 — 통합 설계 V1 개정 2 §2 · §4-1 · 판정 A-3 · A-4.

```text
행동   KEEP · SELL(i) · BUY(j) · SWITCH(i,j) — 통상 최대 1편입 · 1이탈 · KEEP 포함 최대 36
미결   매수 대기 또는 사유 EXIT 매도가 살아 있으면 KEEP 만(보호로 바뀐 이탈 = 보호 매도)
매도   보유 ∩ 그날 자격(34열 있음) ∩ 살아 있는 매도 없음 · 자격 밖 보유 = Q4 보류(매도 대상 아님)
편입   RET_120 상위 5 후보 중 미보유 · 매도/매수 대기 아님 · 예정 슬롯 ≥ 1 · h + (1−c)s > 1e-9
       예정 슬롯 = 5 − 보유 − 매수 대기 + 이번 매도 + 보유 중 살아 있는 보호 매도(보호 예정 대금은 예산에 없음)
순서   통상 거래 수 → KEEP · SELL · BUY · SWITCH → 종목코드(SWITCH = 매도 코드 → 매수 코드) · 학습 · 선택 공통
금액   v = NAV_D · h = 현금/v · s = 매도 보유의 D 평가/v · b = min(0.2, h + (1−c)s)/(1+c) · k = c(b + s)
입력   z = [b·[1, u_매수] (35칸) · s·[1, u_매도] (35칸)] · 없는 역할 · KEEP = 0
```

c 는 그 장부의 비용이다(40bp 장부는 예산 조건 · b · z · k 모두 0.004 · 판정 A-4). 미래 가격 · 체결 성공으로
행동을 미리 지우지 않는다 — 실제 수량 · 취소는 E 의 기존 체결 순서가 맡는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.weekly_selection import data as D
from app.weekly_selection import policy as PO

SLOTS = PO.SLOTS
SHARE = PO.BUDGET_SHARE
# 계산 잔차를 0 예산으로 구분하는 고정 경계(최저 금액 · 문턱 아님 · 판정 A-3)
EPS = 1e-9
NCOL = 34
WIDTH = NCOL + 1
KINDS = ("KEEP", "SELL", "BUY", "SWITCH")


@dataclass(frozen=True)
class Action:
    kind: str
    sell: Optional[int] = None
    buy: Optional[int] = None


KEEP = Action("KEEP")


@dataclass
class Snapshot:
    """판단일 D 의 상태(그날 체결 · 평가 · 보호를 마친 뒤 · 새 주간 의도 전)."""

    nav: float
    cash: float
    held: dict[int, float]  # 보유 → D 평가금액(수량 × D 종가)
    sell_live: dict[int, str]  # 살아 있는 매도 → 사유(EXIT · PROTECT)
    buy_live: set[int]


def snapshot(p: D.Panel, st: PO._State, i: int) -> Snapshot:
    held = {}
    for j, h in st.hold.items():
        if h["last_idx"] != i:
            raise D.CheckRequired(f"{p.axis[i]} 보유 {p.codes[j]} 의 그날 평가 없음")
        held[j] = h["units"] * h["last_close"]
    nav = st.cash + sum(held.values())
    if not (np.isfinite(nav) and nav > 0):
        raise D.CheckRequired(f"{p.axis[i]} 판단일 평가자산 이상: {nav!r}")
    return Snapshot(
        nav=nav,
        cash=st.cash,
        held=held,
        sell_live={j: it["reason"] for j, it in st.sell_live.items()},
        buy_live=set(st.buy_live),
    )


def trades(a: Action) -> int:
    return (a.sell is not None) + (a.buy is not None)


def order_key(a: Action, codes: list[str]) -> tuple:
    return (
        trades(a),
        KINDS.index(a.kind),
        "" if a.sell is None else codes[a.sell],
        "" if a.buy is None else codes[a.buy],
    )


def name(a: Action, codes: list[str]) -> str:
    if a.kind == "KEEP":
        return "KEEP"
    if a.kind == "SELL":
        return f"SELL:{codes[a.sell]}"
    if a.kind == "BUY":
        return f"BUY:{codes[a.buy]}"
    return f"SWITCH:{codes[a.sell]}>{codes[a.buy]}"


def parse(s: str, ci: dict[str, int]) -> Action:
    """저장 이름 → 행동(name 의 역)."""
    if s == "KEEP":
        return KEEP
    kind, rest = s.split(":", 1)
    if kind == "SWITCH":
        a, b = rest.split(">")
        return Action("SWITCH", sell=ci[a], buy=ci[b])
    if kind == "SELL":
        return Action("SELL", sell=ci[rest])
    if kind == "BUY":
        return Action("BUY", buy=ci[rest])
    raise ValueError(f"행동 이름 형식: {s}")


def allowed(
    sn: Snapshot, cands: list[int], eligible: set[int], cost: float, codes: list[str]
) -> tuple[list[Action], Optional[str]]:
    """(고정 순서 행동 목록 · KEEP 만인 사유). 첫째는 늘 KEEP."""
    if sn.buy_live or any(r == "EXIT" for r in sn.sell_live.values()):
        return [KEEP], "NORMAL_PENDING"
    sells = [j for j in sn.held if j not in sn.sell_live and j in eligible]
    buys = [
        j
        for j in cands
        if j not in sn.held and j not in sn.sell_live and j not in sn.buy_live
    ]
    protect = sum(1 for j in sn.held if j in sn.sell_live)
    free = SLOTS - len(sn.held) - len(sn.buy_live) + protect
    h = sn.cash / sn.nav
    acts = [KEEP] + [Action("SELL", sell=i) for i in sells]
    if free >= 1 and h > EPS:
        acts += [Action("BUY", buy=j) for j in buys]
    for i in sells:
        if free + 1 >= 1 and h + (1.0 - cost) * sn.held[i] / sn.nav > EPS:
            acts += [Action("SWITCH", sell=i, buy=j) for j in buys]
    acts.sort(key=lambda a: order_key(a, codes))
    return acts, (None if len(acts) > 1 else "NO_ACTION")


def amounts(sn: Snapshot, a: Action, cost: float) -> tuple[float, float, float]:
    """(b · s · k) — 판단용 근사(E 의 실제 수량 산식을 대체하지 않음)."""
    s = 0.0 if a.sell is None else sn.held[a.sell] / sn.nav
    b = (
        0.0
        if a.buy is None
        else min(SHARE, sn.cash / sn.nav + (1.0 - cost) * s) / (1.0 + cost)
    )
    return b, s, cost * (b + s)


def z_vector(a: Action, b: float, s: float, u: dict[int, np.ndarray]) -> np.ndarray:
    z = np.zeros(2 * WIDTH)
    if a.buy is not None:
        z[0] = b
        z[1:WIDTH] = b * u[a.buy]
    if a.sell is not None:
        z[WIDTH] = s
        z[WIDTH + 1 :] = s * u[a.sell]  # noqa: E203
    return z


def needed(acts: list[Action]) -> list[int]:
    """행동에 쓰이는 서로 다른 ETF(같은 D · ETF 는 통계에서 한 번만 · 판정 A-2)."""
    out: set[int] = set()
    for a in acts:
        out |= {j for j in (a.sell, a.buy) if j is not None}
    return sorted(out)
