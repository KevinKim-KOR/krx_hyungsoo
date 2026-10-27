"""POC6-11 독립 손검산 — 정책 함수(policy)를 쓰지 않고 장부 · 의도 · 체결을 다시 따진다(판정 §6 · 검토 r1).

```text
장부     현금 · 수량 · 체결가 = 그날 O* · 거래 가능 · 5종목 · 예산 = min(20% 자산, 현금) · 명목 = 예산/(1+c) · 비용
체결     실행일 ≤ 오늘인 살아 있는 매도 = 거래 가능하면 오늘 체결 · 아니면 미체결(이연 · 재시도 누락 검출)
         같은 시가 매수 = 점수 순으로 기대 상태(자리 없음 · 보유 중 · 거래 불가 · 현금 없음 · 체결)와 대조
         처리되지 않은 의도(PLANNED) · 구간 안 UNEXECUTED · 끝의 DEFERRED 검출 · 멈춘 장부는 멈춘 날 시가까지
계획     상위 5 편입 · 추세(I > SMA60 · 가격에서 다시) · 주 편입 한도 · 10위 유지 · 통상 이탈 1개 · 4회 재진입 대기 ·
         중복 매도 의도 · 실행일 = 신호 + 2 · 보호 이탈 조건과 누락
K        첫 거래 가능 시가(잠금 실행일 이후) 전액 매수 · 수량 · 일별 평가
```
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from app.weekly_selection import data as D
from app.weekly_selection import policy as PO

TOL = 1e-9


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def _expected_buy(units: dict, t: str, ok: bool, budget: float) -> str:
    if len(units) >= PO.SLOTS:
        return "CANCELED_SLOT_FULL"
    if t in units:
        return "CANCELED_HELD"
    if not ok:
        return "CANCELED_NOT_TRADABLE"
    if not budget > 0:
        return "CANCELED_NO_CASH"
    return "FILLED"


def audit_book(
    p: D.Panel,
    bk: dict,
    scores: dict[str, dict[str, float]],
    reviews: list[int],
    start: int,
    end: int,
) -> list[str]:
    """L · B 장부 손검산. scores = 신호일 → {종목: 점수}(자격 집합 전체)."""
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    stop = bk["end"].get("stopped_at") if bk["status"] != "OK" else None
    if not bk["ledger"] and not stop:
        return out
    # 멈춘 장부는 멈춘 날 시가까지(평가 첫날 바로 멈춰 장부 행이 0개여도 그날 체결을 본다 · 재검토 r1)
    last_open = pos[stop] if stop else min(end, pos[bk["ledger"][-1]["date"]])
    cost, ci = bk["cost"], p.ci
    intents = {it["id"]: it for it in bk["intents"]}
    fill_of = {f["intent"]: f for f in bk["fills"]}
    if len(fill_of) != len(bk["fills"]) or not set(fill_of) <= set(intents):
        out.append("체결 · 의도 연결 이상(중복 · 의도 없는 체결)")
    for it in intents.values():
        if (it["status"] == "FILLED") != (it["id"] in fill_of):
            out.append(f"의도 {it['id']} 상태 {it['status']} ≠ 체결 기록")
    sells = sorted(
        (it for it in intents.values() if it["side"] == "SELL"), key=lambda it: it["id"]
    )
    buys_by: dict[str, list[dict]] = {}
    for it in intents.values():
        if it["side"] == "BUY" and it.get("exec_date"):
            buys_by.setdefault(it["exec_date"], []).append(it)
    led = {r["date"]: r for r in bk["ledger"]}
    cash, units, lastc = PO.START_VALUE, {}, {}
    for i in range(start, last_open + 1):
        d = p.axis[i]
        for it in sells:
            ed, fd = it.get("exec_date"), it.get("filled_date")
            if (
                it["status"] == "UNEXECUTED_AFTER_END"
                or ed is None
                or ed > d
                or (fd and fd < d)
            ):
                continue
            t = it["ticker"]
            if t not in units:
                out.append(f"{d} {t} 보유 없는 매도 의도 {it['id']}")
                continue
            j = ci[t]
            if bool(p.exec_ok[j, i]) != (fd == d):
                out.append(
                    f"{d} {t} 매도 의도 {it['id']} 체결 여부 ≠ 거래 가능({bool(p.exec_ok[j, i])})"
                )
            if fd != d or it["id"] not in fill_of:
                continue
            f = fill_of[it["id"]]
            if f["price"] != float(p.O[j, i]) or not _close(f["units"], units[t]):
                out.append(f"{d} {t} 매도 체결가 ≠ O* 또는 수량 ≠ 보유 전량")
            if not (
                _close(f["notional"], f["units"] * f["price"])
                and _close(f["cost"], f["notional"] * cost)
            ):
                out.append(f"{d} {t} 매도 명목 · 비용 불일치")
            cash += f["notional"] * (1.0 - cost)
            units.pop(t)
        equity = cash + sum(
            u * (float(p.O[ci[t], i]) if p.exec_ok[ci[t], i] else lastc[t])
            for t, u in units.items()
        )
        for it in sorted(buys_by.get(d, []), key=lambda it: it["priority"]):
            t = it["ticker"]
            j = ci[t]
            budget = min(PO.BUDGET_SHARE * equity, cash)
            exp = _expected_buy(units, t, bool(p.exec_ok[j, i]), budget)
            if it["status"] != exp:
                out.append(
                    f"{d} {t} 매수 의도 {it['id']} 상태 {it['status']} ≠ 기대 {exp}"
                )
            if exp != "FILLED" or it["id"] not in fill_of:
                continue
            f = fill_of[it["id"]]
            if f["date"] != d or f["price"] != float(p.O[j, i]):
                out.append(f"{d} {t} 매수 체결일 · 체결가 ≠ 실행일 O*")
            if not (
                _close(f["notional"], budget / (1.0 + cost))
                and _close(f["units"], f["notional"] / f["price"])
                and _close(f["cost"], f["notional"] * cost)
            ):
                out.append(f"{d} {t} 매수 예산 · 수량 · 비용 불일치")
            cash -= budget
            units[t] = f["units"]
            lastc[t] = f["price"]
        if stop and i == last_open:
            break  # 멈춘 날 = 시가 처리까지만(종가 평가 없음)
        value = cash
        for t, u in units.items():
            value += u * float(p.I[ci[t], i])
            lastc[t] = float(p.I[ci[t], i])
        r = led.get(d)
        if (
            r is None
            or not (_close(r["cash"], cash) and _close(r["value"], value))
            or sorted(r["pos"]) != sorted(units)
        ):
            out.append(f"{d} 장부 현금 · 평가 · 보유 불일치")
            break
    for it in intents.values():
        ed = it.get("exec_date")
        if it["status"] == "UNEXECUTED_AFTER_END" and ed is not None and pos[ed] <= end:
            out.append(f"의도 {it['id']} 구간 안 실행일인데 미실행")
        if it["status"] == "PLANNED" or (
            not stop and it["status"] in ("DEFERRED", "NOT_RUN_CHECK_REQUIRED")
        ):
            out.append(f"의도 {it['id']} 처리되지 않음({it['status']})")
        if it["status"] == "SKIPPED_NOT_HELD":
            out.append(f"의도 {it['id']} 보유 없는 매도")
    out += _audit_intents(p, bk, intents, scores, reviews, start, end)
    return out[:50]


def audit_k(p: D.Panel, bk: dict, k_idx: int, start: int, end: int) -> list[str]:
    """K 손검산 — 잠금 실행일 이후 첫 거래 가능 시가에 전액(비용 포함 예산) 매수 · 끝까지 보유."""
    out: list[str] = []
    j = p.ci[D.BENCH]
    cost = bk["cost"]
    day = next((i for i in range(k_idx, end + 1) if p.exec_ok[j, i]), None)
    fills = bk["fills"]
    if day is None:
        return out if not fills else ["K 거래 가능일이 없는데 체결"]
    if (
        len(fills) != 1
        or fills[0]["date"] != p.axis[day]
        or fills[0]["price"] != float(p.O[j, day])
    ):
        return [f"K 체결 ≠ {p.axis[day]} O*"]
    units = PO.START_VALUE / (1.0 + cost) / float(p.O[j, day])
    if not _close(fills[0]["units"], units):
        out.append("K 수량 ≠ 100/(1+c)/O*")
    if (day != k_idx) != any(e.get("type") == "K_DELAYED" for e in bk["events"]):
        out.append("K 지연 기록 이상")
    for r in bk["ledger"]:
        i = p.axis.index(r["date"])
        want = PO.START_VALUE if i < day else units * float(p.I[j, i])
        if not _close(r["value"], want):
            out.append(f"{r['date']} K 평가 ≠ 수량 × 종가")
            break
    return out


def _held_at(bk: dict, d: str) -> set[str]:
    r = next((r for r in bk["ledger"] if r["date"] == d), None)
    return set(r["pos"]) if r else set()


def _audit_intents(p, bk, intents, scores, reviews, start, end) -> list[str]:
    out: list[str] = []
    ci, pos = p.ci, {d: k for k, d in enumerate(p.axis)}
    rev = sorted(reviews)
    for it in intents.values():
        si = pos[it["signal"]]
        if it.get("exec_date") != (p.axis[si + 2] if si + 2 < len(p.axis) else None):
            out.append(f"의도 {it['id']} 실행일 ≠ 신호 + 2")
        if (
            it["status"] == "FILLED"
            and it["side"] == "SELL"
            and it["filled_date"] != it["exec_date"]
        ):
            j = ci[it["ticker"]]
            gap = range(pos[it["exec_date"]], pos[it["filled_date"]])
            if any(p.exec_ok[j, k] for k in gap):
                out.append(f"의도 {it['id']} 거래 가능일을 건너뛴 이연")
        if (
            it["status"] == "CANCELED_NOT_TRADABLE"
            and p.exec_ok[ci[it["ticker"]], pos[it["exec_date"]]]
        ):
            out.append(f"의도 {it['id']} 거래 가능한데 취소")
    live: dict[str, list[tuple[str, Optional[str]]]] = {}
    for it in intents.values():
        if it["side"] == "SELL":
            live.setdefault(it["ticker"], []).append(
                (it["signal"], it.get("filled_date"))
            )
    for t, spans in live.items():
        spans.sort()
        for (s1, f1), (s2, _f2) in zip(spans, spans[1:]):
            if f1 is None or f1 > s2:
                out.append(f"{t} 살아 있는 매도 의도 중복({s1} · {s2})")
    first = True
    for pl in bk["plans"]:
        d = pl["signal"]
        i = pos[d]
        sc = scores.get(d, {})
        held = _held_at(bk, d) if i >= start else set()
        selling = {
            t
            for t, spans in live.items()
            for s, f in spans
            if s <= d
            and (f is None or f > d)
            and not (s == d and _is_normal_exit(intents, t, d))
        }
        ranked = sorted(sc, key=lambda t: (-sc[t], 0 if t in held else 1, t))
        rank = {t: k + 1 for k, t in enumerate(ranked)}
        normal = [
            it
            for it in intents.values()
            if it["side"] == "SELL"
            and it["signal"] == d
            and it["reason"] in ("RANK_OUT", "NOT_ELIGIBLE")
        ]
        cands = [t for t in held - selling if t not in rank or rank[t] > PO.KEEP_RANK]
        cands.sort(key=lambda t: (0 if t not in rank else 1, -rank.get(t, 0), t))
        if [it["ticker"] for it in normal] != cands[:1]:
            out.append(
                f"{d} 통상 이탈 {[it['ticker'] for it in normal]} ≠ 기대 {cands[:1]}"
            )
        buys = [
            it for it in intents.values() if it["side"] == "BUY" and it["signal"] == d
        ]
        pending = {
            it["ticker"]
            for it in intents.values()
            if it["side"] == "BUY"
            and it["signal"] < d
            and pos[it["exec_date"] or p.axis[-1]] > i
            and it["status"] != "UNEXECUTED_AFTER_END"
        }
        cap = PO.SLOTS - len(held) - len(pending) + len(normal) + len(held & selling)
        limit = min(PO.SLOTS if first else 1, max(0, cap))
        expect = []
        for t in ranked[: PO.ENTRY_TOP]:
            if len(expect) >= limit:
                break
            if t in held or t in selling or t in pending or not _trend(p, ci[t], i):
                continue
            if _cooling(bk, t, i, pos, rev):
                continue
            expect.append(t)
        if [it["ticker"] for it in buys] != expect:
            out.append(f"{d} 편입 {[it['ticker'] for it in buys]} ≠ 기대 {expect}")
        first = False
    if bk["ledger"]:
        out += _audit_protect(
            p, bk, intents, start, min(end, pos[bk["ledger"][-1]["date"]])
        )
    return out


def _is_normal_exit(intents, t, d) -> bool:
    return any(
        it["ticker"] == t
        and it["signal"] == d
        and it["reason"] in ("RANK_OUT", "NOT_ELIGIBLE")
        for it in intents.values()
    )


def _trend(p: D.Panel, j: int, i: int) -> bool:
    """I > SMA60 — 30열 MA_GAP_60(= I/평균 − 1) > 0 과 같은 식(정책 함수 · 표를 쓰지 않음)."""
    if i < 59:
        return False
    win = p.I[j, i - 59 : i + 1]  # noqa: E203
    return bool(np.isfinite(win).all() and p.I[j, i] / win.mean() - 1.0 > 0)


def _cooling(bk: dict, t: str, i: int, pos: dict[str, int], rev: list[int]) -> bool:
    """실제 매도일(그날 종가 검토 포함) ~ 신호 i 의 정기 검토 수 ≤ 4 이면 재진입 대기."""
    sold = [
        pos[f["date"]]
        for f in bk["fills"]
        if f["ticker"] == t and f["side"] == "SELL" and pos[f["date"]] <= i
    ]
    if not sold:
        return False
    s = max(sold)
    return sum(1 for r in rev if s <= r <= i) <= PO.COOLDOWN_REVIEWS


def _audit_protect(p, bk, intents, start, end) -> list[str]:
    out: list[str] = []
    ci, pos = p.ci, {d: k for k, d in enumerate(p.axis)}
    prot = {
        (it["ticker"], it["signal"])
        for it in intents.values()
        if it["reason"] == "PROTECT"
    }
    spans = []
    buys = [f for f in bk["fills"] if f["side"] == "BUY"]
    for b in buys:
        s = next(
            (
                f
                for f in bk["fills"]
                if f["side"] == "SELL"
                and f["ticker"] == b["ticker"]
                and f["date"] > b["date"]
            ),
            None,
        )
        spans.append((b, s))
    for b, s in spans:
        j, a = ci[b["ticker"]], pos[b["date"]]
        z = pos[s["date"]] - 1 if s else end
        peak = b["price"]
        for k in range(a, z + 1):
            c = float(p.I[j, k])
            peak = max(peak, c)
            hit = c / peak - 1.0 <= PO.PROTECT
            d = p.axis[k]
            live = any(
                it["ticker"] == b["ticker"]
                and it["side"] == "SELL"
                and it["signal"] < d
                and (it.get("filled_date") is None or it["filled_date"] > d)
                for it in intents.values()
            )
            if hit and not live and (b["ticker"], d) not in prot:
                out.append(f"{d} {b['ticker']} 보호 이탈 누락")
            if (b["ticker"], d) in prot and not hit:
                out.append(f"{d} {b['ticker']} 조건 없는 보호 이탈")
    return out
