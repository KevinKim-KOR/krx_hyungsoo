"""POC6-11 공통 운용 정책 · 모의 장부(L · B 공통 · K 예외) — 설계 §6 · §7 · PLAN §6(판정 §3).

```text
주간   신호 t(자격 ≥ 20) — 점수 내림차순(완전 동점 = 기존 보유 우선 → ticker 오름차순) · 순위는 추세 조건 전
       유지 = 순위 ≤ 10 · 통상 이탈 = 순위 > 10 또는 순위 없음(자격 밖) 중 가장 낮은 1종목(순위 없음이 가장 낮음)
       편입 = 상위 5 안 · I > SMA60 · 미보유 · 매도/매수 대기 아님 · 재진입 대기 아님 · 첫 유효 계획만 최대 5 · 이후 1
일별   큰 변화 = |I_t/I_t−1 − 1| ≥ 5%(기록만) · 보호 이탈 = I_t/P − 1 ≤ −15%(P = 편입 O* 와 이후 종가 최고)
체결   모든 계획 = t+2 합성 시가 · 매도 먼저(이연 먼저 · 거래 불가 = 이연) → 매수 전 자산 1회 확정 → 매수(점수 순)
       매수 예산(비용 포함) = min(자산 × 20%, 남은 현금) · 명목 = 예산/(1+c) · 거래 불가 · 자리 없음 = 취소
       매수 전 자산의 보유 평가 = 그날 체결 가능하면 O* · 아니면 직전 확인 종가(예산 계산 전용 · 장부 평가 아님)
재진입 실제 매도 뒤(매도일 종가 검토 포함) 정기 검토 4회 동안 신규 금지(5번째부터 가능)
미확정 보유 종목의 그날 공표 행 · 연결 종가 · 같은 연결 구간이 없으면 그 시점까지 기록하고 CHECK_REQUIRED 로 멈춤
       (마지막 종가 · NAV 정산 · 미래 마지막 행을 이용한 사전 매도 없음 · 판정 §3)
```
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

from app.weekly_selection.data import Panel

SLOTS = 5
KEEP_RANK = 10
ENTRY_TOP = 5
BUDGET_SHARE = 0.2
BIG_MOVE = 0.05
PROTECT = -0.15
COOLDOWN_REVIEWS = 4
START_VALUE = 100.0
LIVE_SELL = ("PLANNED", "DEFERRED", "UNEXECUTED_AFTER_END")


@dataclass
class Plan:
    """한 신호의 고정 점수 · 추세 조건(L · B 공통 입력)."""

    signal: int
    scores: dict[int, float]  # 자격 종목 위치 → 점수
    trend_ok: set[int]  # I > SMA60(MA_GAP_60 > 0)
    model_id: Optional[str] = None


@dataclass
class Book:
    curve: str
    cost: float
    status: str = "OK"
    ledger: list[dict] = field(default_factory=list)
    intents: list[dict] = field(default_factory=list)
    fills: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    plans: list[dict] = field(default_factory=list)
    unresolved: Optional[dict] = None
    end: dict = field(default_factory=dict)


def valid_close(p: Panel, j: int, i: int, seg: int) -> bool:
    return bool(
        p.has_row[j, i]
        and np.isfinite(p.I[j, i])
        and p.I[j, i] > 0
        and p.seg[j, i] == seg
    )


def ranking(scores: dict[int, float], held: set[int], codes: list[str]) -> list[int]:
    """점수 내림차순 · 완전 동점 = 기존 보유 우선 → ticker 오름차순(반올림 없음)."""
    return sorted(scores, key=lambda j: (-scores[j], 0 if j in held else 1, codes[j]))


class _State:
    def __init__(self, p: Panel, bk: Book, end: int):
        self.p, self.bk, self.end = p, bk, end
        self.cash = START_VALUE
        self.hold: dict[int, dict] = {}
        self.sell_live: dict[int, dict] = (
            {}
        )  # 종목 → 살아 있는 매도 의도(1개 · LIVE_SELL)
        self.buy_live: dict[int, dict] = {}  # 종목 → 실행 전 매수 의도
        self.due: dict[int, list[dict]] = {}
        self.reviews_after: dict[int, int] = {}  # 종목 → 실제 매도 뒤 지난 정기 검토 수
        self.first_plan_done = False

    def intent(self, **kw) -> dict:
        it = {"id": len(self.bk.intents) + 1, "status": "PLANNED"}
        it.update(kw)
        e = it["exec_idx"]
        it["exec_date"] = self.p.axis[e] if e < len(self.p.axis) else None
        self.bk.intents.append(it)
        if e > self.end:
            it["status"] = "UNEXECUTED_AFTER_END"
        else:
            self.due.setdefault(e, []).append(it)
        if it["side"] == "SELL":
            self.sell_live[it["ticker_idx"]] = it
        elif it["status"] == "PLANNED":
            self.buy_live[it["ticker_idx"]] = it
        return it

    def fill(
        self, it: dict, i: int, units: float, px: float, notional: float, cost: float
    ):
        it.update(status="FILLED", filled_idx=i, filled_date=self.p.axis[i])
        self.bk.fills.append(
            {
                "date": self.p.axis[i],
                "ticker": self.p.codes[it["ticker_idx"]],
                "side": it["side"],
                "units": units,
                "price": px,
                "notional": notional,
                "cost": notional * cost,
                "reason": it["reason"],
                "intent": it["id"],
            }
        )


def simulate(
    p: Panel,
    plans: dict[int, Plan],
    start: int,
    end: int,
    cost: float,
    curve: str,
    reviews: list[int],
    on_day: Optional[Callable[[int], None]] = None,
) -> Book:
    """start(평가 첫 거래일) ~ end(마지막 거래일) 장부.

    plans = 이 곡선의 정기 계획(실행이 end 뒤면 미실행) · reviews = 재진입 대기를 세는 정기 검토 위치.
    루프는 첫 계획 신호부터 돈다(시작일 전 신호의 실행이 시작일 이후인 경우 · 설계 §3-3).
    """
    bk = Book(curve=curve, cost=cost)
    st = _State(p, bk, end)
    first = min([*plans, start])
    review_set = set(reviews)
    for i in range(first, end + 1):
        if on_day is not None:
            on_day(i)
        today = st.due.pop(i, [])
        _open(p, st, i, today, cost)
        if not _close(p, st, i, start):
            for its in st.due.values():
                for it in its:
                    it["status"] = "NOT_RUN_CHECK_REQUIRED"
            return bk
        if i in review_set:
            for j in st.reviews_after:
                st.reviews_after[j] += 1
        if i in plans:
            _weekly(p, st, plans[i], i)
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


def _open(p: Panel, st: _State, i: int, today: list[dict], cost: float) -> None:
    sells = [it for it in st.sell_live.values() if it["status"] == "DEFERRED"]
    sells += [it for it in today if it["side"] == "SELL"]
    for it in sells:
        j = it["ticker_idx"]
        if j not in st.hold:  # 방어 — 계획 단계에서 보유만 매도하므로 생기지 않아야 함
            it["status"] = "SKIPPED_NOT_HELD"
            st.sell_live.pop(j, None)
            continue
        if p.exec_ok[j, i]:
            units = st.hold.pop(j)["units"]
            px = float(p.O[j, i])
            notional = units * px
            st.cash += notional * (1.0 - cost)
            st.fill(it, i, units, px, notional, cost)
            st.sell_live.pop(j, None)
            st.reviews_after[j] = 0
        else:
            it["status"] = "DEFERRED"
            it.setdefault("waited", []).append(p.axis[i])
    equity = st.cash
    for j, h in st.hold.items():
        equity += h["units"] * (
            float(p.O[j, i]) if p.exec_ok[j, i] else h["last_close"]
        )
    buys = sorted(
        (it for it in today if it["side"] == "BUY"), key=lambda it: it["priority"]
    )
    for it in buys:
        j = it["ticker_idx"]
        st.buy_live.pop(j, None)
        it["equity_at_open"] = equity
        if len(st.hold) >= SLOTS:
            it["status"] = "CANCELED_SLOT_FULL"
        elif j in st.hold:
            it["status"] = "CANCELED_HELD"
        elif not p.exec_ok[j, i]:
            it["status"] = "CANCELED_NOT_TRADABLE"
        else:
            budget = min(BUDGET_SHARE * equity, st.cash)
            if not budget > 0:
                it["status"] = "CANCELED_NO_CASH"
                continue
            px = float(p.O[j, i])
            notional = budget / (1.0 + cost)
            units = notional / px
            st.cash -= budget
            st.hold[j] = {
                "units": units,
                "entry_idx": i,
                "peak": px,
                "seg": int(p.seg[j, i]),
                "last_close": px,
                "last_idx": None,
            }
            st.fill(it, i, units, px, notional, cost)


def _close(p: Panel, st: _State, i: int, start: int) -> bool:
    bk = st.bk
    value = st.cash
    bad = [j for j in sorted(st.hold) if not valid_close(p, j, i, st.hold[j]["seg"])]
    if (
        bad
    ):  # 그날 평가를 확정할 수 없는 보유 전부(그 시점까지의 정보만 · 정산 · 소급 매도 없음)
        prev = bk.ledger[-1]["value"] if bk.ledger else None
        items = []
        for j in bad:
            h, sell = st.hold[j], st.sell_live.get(j)
            last_value = h["units"] * h["last_close"]
            items.append(
                {
                    "ticker": p.codes[j],
                    "last_valid": (
                        None if h["last_idx"] is None else p.axis[h["last_idx"]]
                    ),
                    "units": h["units"],
                    "last_value_diagnostic": last_value,
                    "last_weight_diagnostic": None if not prev else last_value / prev,
                    "pending_sell": (
                        None
                        if sell is None
                        else {"id": sell["id"], "status": sell["status"]}
                    ),
                    "cause": (
                        "NO_ROW"
                        if not p.has_row[j, i]
                        else (
                            "SEGMENT_CHANGED"
                            if p.seg[j, i] != h["seg"]
                            else "NO_VALID_CLOSE"
                        )
                    ),
                }
            )
        bk.unresolved = {"first_unresolved": p.axis[i], "items": items}
        bk.status = "CHECK_REQUIRED"
        bk.end = {"stopped_at": p.axis[i]}
        return False
    for j, h in sorted(st.hold.items()):
        close = float(p.I[j, i])
        prev_close = p.I[j, i - 1] if i > 0 else np.nan
        if np.isfinite(prev_close) and prev_close > 0:
            chg = close / float(prev_close) - 1.0
            if abs(chg) >= BIG_MOVE:
                bk.events.append(
                    {
                        "date": p.axis[i],
                        "ticker": p.codes[j],
                        "type": "BIG_MOVE",
                        "change": chg,
                    }
                )
        h["peak"] = max(h["peak"], close)
        h["last_close"], h["last_idx"] = close, i
        value += h["units"] * close
        if close / h["peak"] - 1.0 <= PROTECT and j not in st.sell_live:
            st.intent(
                side="SELL",
                reason="PROTECT",
                ticker=p.codes[j],
                ticker_idx=j,
                signal=p.axis[i],
                exec_idx=i + 2,
                peak=h["peak"],
                close=close,
            )
    if i >= start:
        if not (math.isfinite(value) and value > 0 and st.cash >= -1e-9):
            bk.status = "CHECK_REQUIRED"
            bk.unresolved = (
                {  # 비유한 값은 문자열로(엄격 JSON 저장이 실패 기록을 막지 않게)
                    "first_unresolved": p.axis[i],
                    "items": [
                        {
                            "cause": "INVALID_BOOK",
                            "value": value if math.isfinite(value) else repr(value),
                            "cash": (
                                st.cash if math.isfinite(st.cash) else repr(st.cash)
                            ),
                        }
                    ],
                }
            )
            bk.end = {"stopped_at": p.axis[i]}
            return False
        bk.ledger.append(
            {
                "date": p.axis[i],
                "cash": st.cash,
                "value": value,
                "pos": {
                    p.codes[j]: [h["units"], h["last_close"]]
                    for j, h in sorted(st.hold.items())
                },
            }
        )
    return True


def _weekly(p: Panel, st: _State, pl: Plan, i: int) -> None:
    held = set(st.hold)
    order = ranking(pl.scores, held, p.codes)
    rank = {j: r + 1 for r, j in enumerate(order)}
    selling = set(st.sell_live)
    cands = [
        j for j in held if j not in selling and (j not in rank or rank[j] > KEEP_RANK)
    ]
    exits: list[int] = []
    if cands:
        cands.sort(
            key=lambda j: (0 if j not in rank else 1, -rank.get(j, 0), p.codes[j])
        )
        j = cands[0]
        st.intent(
            side="SELL",
            reason="RANK_OUT" if j in rank else "NOT_ELIGIBLE",
            ticker=p.codes[j],
            ticker_idx=j,
            signal=p.axis[i],
            exec_idx=i + 2,
            rank=rank.get(j),
            model=pl.model_id,
        )
        exits.append(j)
    freeing = len(exits) + len(held & selling)
    capacity = SLOTS - len(held) - len(st.buy_live) + freeing
    limit = min(SLOTS if not st.first_plan_done else 1, max(0, capacity))
    entries: list[int] = []
    for j in order[:ENTRY_TOP]:
        if len(entries) >= limit:
            break
        if j in held or j in st.sell_live or j in st.buy_live or j not in pl.trend_ok:
            continue
        if j in st.reviews_after and st.reviews_after[j] <= COOLDOWN_REVIEWS:
            continue
        st.intent(
            side="BUY",
            reason="ENTRY",
            ticker=p.codes[j],
            ticker_idx=j,
            signal=p.axis[i],
            exec_idx=i + 2,
            rank=rank[j],
            score=pl.scores[j],
            priority=rank[j],
            model=pl.model_id,
        )
        entries.append(j)
    st.bk.plans.append(
        {
            "signal": p.axis[i],
            "model": pl.model_id,
            "eligible": len(order),
            "first": not st.first_plan_done,
            "held_rank": {p.codes[j]: rank.get(j) for j in sorted(held)},
            "exits": [p.codes[j] for j in exits],
            "entries": [p.codes[j] for j in entries],
            "capacity": capacity,
            "limit": limit,
        }
    )


def simulate_bench(
    p: Panel, j: int, k_idx: int, start: int, end: int, cost: float
) -> Book:
    """K — 잠금된 첫 정기 계획 실행일(L/B 와 무관)에 069500 전액(비용 포함 예산) 매수 · 끝까지 보유.

    예정일에 거래 불가이면 다음 거래 가능 시가로 미루고 사유를 남긴다(설계 §7).
    """
    bk = Book(curve="K", cost=cost)
    cash, units, seg, last, last_close = START_VALUE, 0.0, -1, None, 0.0
    bought = False
    for i in range(start, end + 1):
        if not bought and i >= k_idx and p.exec_ok[j, i]:
            px = float(p.O[j, i])
            notional = cash / (1.0 + cost)
            units, cash, seg, bought = notional / px, 0.0, int(p.seg[j, i]), True
            last_close = px  # 매수일 종가 전 마지막 확인 가격 = 체결가(진단용)
            bk.fills.append(
                {
                    "date": p.axis[i],
                    "ticker": p.codes[j],
                    "side": "BUY",
                    "units": units,
                    "price": px,
                    "notional": notional,
                    "cost": notional * cost,
                    "reason": "K_ENTRY",
                }
            )
            if i != k_idx:
                bk.events.append(
                    {"date": p.axis[i], "type": "K_DELAYED", "planned": p.axis[k_idx]}
                )
        value = cash
        if bought:
            if not valid_close(p, j, i, seg):
                bk.status = "CHECK_REQUIRED"
                bk.unresolved = {
                    "first_unresolved": p.axis[i],
                    "items": [
                        {
                            "ticker": p.codes[j],
                            "last_valid": last,
                            "units": units,
                            "last_value_diagnostic": units * last_close,
                            "last_weight_diagnostic": 1.0,
                            "pending_sell": None,
                            "cause": "BENCH_NO_VALID_CLOSE",
                        }
                    ],
                }
                bk.end = {"stopped_at": p.axis[i]}
                return bk
            last_close = float(p.I[j, i])
            value += units * last_close
            last = p.axis[i]
        bk.ledger.append(
            {
                "date": p.axis[i],
                "cash": cash,
                "value": value,
                "pos": {p.codes[j]: [units, float(p.I[j, i])]} if bought else {},
            }
        )
    bk.end = {"date": p.axis[end], "holdings": [p.codes[j]] if bought else []}
    return bk


def to_json(bk: Book) -> dict[str, Any]:
    drop = ("ticker_idx", "exec_idx", "filled_idx")
    return {
        "curve": bk.curve,
        "cost": bk.cost,
        "status": bk.status,
        "ledger": bk.ledger,
        "intents": [
            {k: v for k, v in it.items() if k not in drop} for it in bk.intents
        ],
        "fills": bk.fills,
        "events": bk.events,
        "plans": bk.plans,
        "unresolved": bk.unresolved,
        "end": bk.end,
    }
