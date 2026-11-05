"""POC6-21 주간 보유/현금 전환 · 최근 거래 후 강화 — 통합 설계 §3 · §5 · 판정 §A-3 · §A-4 · §A-6.

```text
주간   공통 계획 신호(자격 20종 이상 · 시장 4열 정의)만 판단 · 그 밖의 주 = 통상 판단 없음(보유 평가 · 일별 보호 계속)
이탈   보유(살아 있는 매도 없음 · 자격 있음)마다 점수 ≤ −문턱 이면 후보 → 가장 낮은 점수 1개(동점 = 종목코드)
       자격 밖 보유 = 통상 판단 보류(자동 매도 · 0점 없음 · 사유 기록) · 살아 있는 매도(보호 · 이연) = 다시 계획 안 함
편입   RET_120 상위 5(동점 = 종목코드 · R/M 공통) 순서로 미보유 · 매수/매도 대기 아님 · 점수 ≥ +문턱 → 한도까지
       한도 = 첫 공통 계획만 5 · 이후 1(자리 = 5 − 보유 − 매수 대기 + 이번 이탈 + 살아 있는 매도)
문턱   h = log(1.002/0.998) · 강화 곡선(R1 · M1)에서 최근 10거래일이면 2h — 재진입 = D 까지 체결된 같은 종목의
       마지막 전량 매도 · 재이탈 = 지금 보유의 진입 체결 · 간격 = 축 위치 D − 체결일(당일 0 · 이연 = 실제 체결일)
보호   H1 −15% 보호 이탈(_close) 그대로 · 강화보다 우선 · 통상 이탈이 살아 있는 동안 보호 조건이 되면 한 건으로
       두고 사유를 PROTECT 로 남긴다(planned_reason = EXIT) · 보호가 살아 있으면 통상 이탈을 만들지 않는다
체결   H1 `_open` · `_close`(시가 체결 · 매도 먼저 · 이연 · 예산 = min(자산 × 20%, 현금) · 미확정 = CHECK_REQUIRED)
```
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

from app.weekly_selection import data as D
from app.weekly_selection import policy as PO
from app.weekly_selection.data import Panel

H = math.log((1 + 0.002) / (1 - 0.002))
STRONG = 2 * H
RECENT_DAYS = 10
CAND_TOP = PO.ENTRY_TOP


@dataclass
class Plan:
    """한 신호의 고정 판단 입력(곡선마다 점수만 다르고 후보 순서 · 자격 밖 사유는 같다)."""

    signal: int
    scores: dict[int, float]  # 자격 종목 위치 → 판단 점수(R = log(1+RET_60) · M = 예측)
    cands: list[int]  # RET_120 상위 5(동점 = 종목코드)
    excluded: dict[
        int, str
    ]  # 신호일 자격 밖 종목 → 사유(name · run126 · liquidity · vol0)
    model_id: Optional[str] = None


def threshold(strengthen: bool, gap: Optional[int]) -> tuple[float, bool, bool]:
    """(문턱, 최근 10거래일 안인가, 강화 적용인가)."""
    recent = gap is not None and 0 <= gap <= RECENT_DAYS
    strong = strengthen and recent
    return (STRONG if strong else H), recent, strong


def simulate(
    p: Panel,
    plans: dict[int, Plan],
    start: int,
    end: int,
    cost: float,
    curve: str,
    strengthen: bool,
    on_day: Optional[Callable[[int], None]] = None,
) -> PO.Book:
    """start(평가 첫 거래일) ~ end(마지막 거래일) 장부 — 루프는 첫 계획 신호부터(시작일 전 신호의 실행 포함)."""
    bk = PO.Book(curve=curve, cost=cost)
    st = PO._State(p, bk, end)
    last_sell: dict[int, int] = {}  # 종목 → 마지막 전량 매도 체결 위치
    ci, seen = p.ci, 0
    first = min([*plans, start])
    for i in range(first, end + 1):
        if on_day is not None:
            on_day(i)
        PO._open(p, st, i, st.due.pop(i, []), cost)
        for f in bk.fills[seen:]:
            if f["side"] == "SELL":
                last_sell[ci[f["ticker"]]] = i
        seen = len(bk.fills)
        if not PO._close(p, st, i, start):
            for its in st.due.values():
                for it in its:
                    it["status"] = "NOT_RUN_CHECK_REQUIRED"
            return bk
        _protect_overlap(p, st, i)
        if i in plans:
            _weekly(p, st, plans[i], i, strengthen, last_sell)
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


def _protect_overlap(p: Panel, st: PO._State, i: int) -> None:
    """살아 있는 통상 이탈이 있는 보유가 오늘 종가에 보호 조건이면 그 의도를 보호 사유로(한 건 · 새 계획 없음)."""
    for j, it in st.sell_live.items():
        h = st.hold.get(j)
        if it["reason"] != "EXIT" or h is None or h["last_idx"] != i:
            continue
        if h["last_close"] / h["peak"] - 1.0 <= PO.PROTECT:
            it.update(
                reason="PROTECT",
                planned_reason="EXIT",
                protect_at=p.axis[i],
                peak=h["peak"],
                close=h["last_close"],
            )


def _review(p, j, s, gap, strengthen, side) -> dict:
    thr, recent, strong = threshold(strengthen, gap)
    return {
        "ticker": p.codes[j],
        "score": s,
        "gap": gap,
        "recent": recent,
        "strengthened": strong,
        "threshold": thr,
        "passed": s <= -thr if side == "SELL" else s >= thr,
    }


def _weekly(
    p: Panel,
    st: PO._State,
    pl: Plan,
    i: int,
    strengthen: bool,
    last_sell: dict[int, int],
) -> None:
    held, selling = set(st.hold), set(st.sell_live)
    exit_rev, held_out, exiting, hits = [], [], [], []
    for j in sorted(held, key=lambda j: p.codes[j]):
        if j in selling:
            exiting.append([p.codes[j], st.sell_live[j]["reason"]])
        elif j in pl.scores:
            gap = i - st.hold[j]["entry_idx"]
            exit_rev.append(_review(p, j, pl.scores[j], gap, strengthen, "SELL"))
            if exit_rev[-1]["passed"]:
                hits.append((pl.scores[j], p.codes[j], j, exit_rev[-1]))
        elif j in pl.excluded:
            held_out.append([p.codes[j], pl.excluded[j]])
        else:  # 그날 행이 있는 보유는 자격 또는 자격 밖 사유 중 하나 — 둘 다 없으면 자료 손상
            raise D.CheckRequired(
                f"{p.axis[i]} 보유 {p.codes[j]} 자격 · 제외 사유 없음"
            )
    exits: list[int] = []
    if hits:
        _s, _c, j, r = min(hits, key=lambda x: (x[0], x[1]))
        st.intent(
            side="SELL",
            reason="EXIT",
            ticker=r["ticker"],
            ticker_idx=j,
            signal=p.axis[i],
            exec_idx=i + 2,
            **{
                k: r[k] for k in ("score", "threshold", "gap", "recent", "strengthened")
            },
            model=pl.model_id,
        )
        exits.append(j)
    freeing = len(exits) + len(held & selling)
    capacity = PO.SLOTS - len(held) - len(st.buy_live) + freeing
    limit = min(PO.SLOTS if not st.first_plan_done else 1, max(0, capacity))
    entry_rev: list[dict] = []
    entries: list[int] = []
    for k, j in enumerate(pl.cands):
        if len(entries) >= limit:
            break
        if j in held or j in st.sell_live or j in st.buy_live:
            continue
        gap = i - last_sell[j] if j in last_sell else None
        r = _review(p, j, pl.scores[j], gap, strengthen, "BUY")
        entry_rev.append(r)
        if not r["passed"]:
            continue
        st.intent(
            side="BUY",
            reason="ENTRY",
            ticker=r["ticker"],
            ticker_idx=j,
            signal=p.axis[i],
            exec_idx=i + 2,
            priority=k + 1,
            cand_rank=k + 1,
            **{
                k2: r[k2]
                for k2 in ("score", "threshold", "gap", "recent", "strengthened")
            },
            model=pl.model_id,
        )
        entries.append(j)
    st.bk.plans.append(
        {
            "signal": p.axis[i],
            "model": pl.model_id,
            "eligible": len(pl.scores),
            "first": not st.first_plan_done,
            "cands": [p.codes[j] for j in pl.cands],
            "exit_reviews": exit_rev,
            "held_not_eligible": held_out,
            "held_exiting": exiting,
            "exits": [p.codes[j] for j in exits],
            "entry_reviews": entry_rev,
            "entries": [p.codes[j] for j in entries],
            "capacity": capacity,
            "limit": limit,
        }
    )
