"""POC6-21 독립 손검산 — 새 주간 정책 함수(policy)를 부르지 않고 장부 · 의도 · 체결 · 검토 기록을 다시 따진다.

판정 §5: 새 감사가 정책 함수를 그대로 불러 같은 오류를 재현하는 방식으로 독립 확인을 대신하지 않는다.

```text
장부     현금 · 수량 · 체결가 = 그날 O* · 거래 가능 · 5종목 · 예산 = min(20% 자산, 현금) · 명목 = 예산/(1+c) · 비용
체결     실행일 ≤ 오늘인 살아 있는 매도 = 거래 가능하면 오늘 체결 · 아니면 이연 · 매수 기대 상태 · 처리되지 않은 의도
계획     보유 = 장부 행 · 매도 대기 = 체결 전 매도 의도(그날 종가 보호 포함) · 자격 밖 보유 = 보류(사유 대조)
         이탈 = 점수 ≤ −문턱 중 가장 낮은 1개 · 편입 = 가격에서 다시 센 RET_120 상위 5 순서 · 점수 ≥ 문턱 · 한도
         문턱 = h · 강화 곡선 최근 10거래일 2h(간격 = 판단일 − 체결 기록) · 검토 기록(기회 분모)을 칸별로 대조
보호     보유 구간 매일 종가 · 최고 종가(편입 O* 포함) 대비 −15% → 새 보호 의도 또는 살아 있는 이탈의 보호 사유
R 점수   가격에서 log(I_t/I_{t−60}) 로 다시(표 · 정책 미사용) · M 점수 = 저장 예측
```
"""

from __future__ import annotations

import math
from typing import Optional

from app.weekly_selection import audit as AU
from app.weekly_selection import data as D
from app.weekly_selection import policy as PO

TOL = AU.TOL
_close = AU._close
RECENT, TOP = (
    10,
    5,
)  # 설계 §3 · §5 고정값(정책 상수를 가져다 쓰지 않는다 · 같은 오류 재현 방지)
H = math.log(1.002 / 0.998)


def r_scores(p: D.Panel, members: dict[int, list[int]], signals: list[int]) -> dict:
    """신호일 → {종목: log(I_t/I_{t−60})}(가격에서 직접)."""
    return {
        p.axis[i]: {
            p.codes[j]: math.log(float(p.I[j, i]) / float(p.I[j, i - 60]))
            for j in members[i]
        }
        for i in signals
    }


def candidates(p: D.Panel, members: dict[int, list[int]], signals: list[int]) -> dict:
    """신호일 → RET_120 상위 5(가격에서 직접 · 동점 = 종목코드)."""
    out = {}
    for i in signals:
        ret = {
            p.codes[j]: float(p.I[j, i]) / float(p.I[j, i - 120]) - 1.0
            for j in members[i]
        }
        out[p.axis[i]] = sorted(ret, key=lambda t: (-ret[t], t))[:TOP]
    return out


def excluded(p: D.Panel, el: D.Eligibility, signals: list[int]) -> dict:
    return {
        p.axis[i]: {p.codes[j]: why for why, js in el.excluded[i].items() for j in js}
        for i in signals
    }


def audit_book(
    p: D.Panel,
    bk: dict,
    scores: dict[str, dict[str, float]],
    cands: dict[str, list[str]],
    outs: dict[str, dict[str, str]],
    strengthen: bool,
    start: int,
    end: int,
) -> list[str]:
    out = _replay(p, bk, start, end)
    intents = {it["id"]: it for it in bk["intents"]}
    out += _intents(p, bk, intents, end)
    out += _plan_days(bk, intents, cands)
    out += _plans(p, bk, intents, scores, cands, outs, strengthen, start)
    if bk["ledger"]:
        last = min(end, p.axis.index(bk["ledger"][-1]["date"]))
        out += _protect(p, bk, intents, last)
    return out[:50]


def _replay(p, bk, start, end) -> list[str]:
    """H1 감사와 같은 체결 규칙을 장부 기록에서 다시 돌린다(정책 상태 미사용)."""
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    stop = bk["end"].get("stopped_at") if bk["status"] != "OK" else None
    if not bk["ledger"] and not stop:
        return out
    last_open = pos[stop] if stop else min(end, pos[bk["ledger"][-1]["date"]])
    cost, ci = bk["cost"], p.ci
    intents = {it["id"]: it for it in bk["intents"]}
    fill_of = {f["intent"]: f for f in bk["fills"]}
    if len(fill_of) != len(bk["fills"]) or not set(fill_of) <= set(intents):
        out.append("체결 · 의도 연결 이상(중복 · 의도 없는 체결)")
    for it in intents.values():
        if (it["status"] == "FILLED") != (it["id"] in fill_of):
            out.append(f"의도 {it['id']} 상태 {it['status']} ≠ 체결 기록")
    sells = [it for it in intents.values() if it["side"] == "SELL"]
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
                out.append(f"{d} {t} 매도 의도 {it['id']} 체결 여부 ≠ 거래 가능")
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
            t, j = it["ticker"], ci[it["ticker"]]
            budget = min(PO.BUDGET_SHARE * equity, cash)
            exp = AU._expected_buy(units, t, bool(p.exec_ok[j, i]), budget)
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
            units[t], lastc[t] = f["units"], f["price"]
        if stop and i == last_open:
            break  # 멈춘 날 = 시가 처리까지만(종가 평가 없음)
        value = cash
        for t, u in units.items():
            lastc[t] = float(p.I[ci[t], i])
            value += u * lastc[t]
        r = led.get(d)
        if (
            r is None
            or not (_close(r["cash"], cash) and _close(r["value"], value))
            or sorted(r["pos"]) != sorted(units)
        ):
            out.append(f"{d} 장부 현금 · 평가 · 보유 불일치")
            break
    return out


def _intents(p, bk, intents, end) -> list[str]:
    out: list[str] = []
    ci, pos = p.ci, {d: k for k, d in enumerate(p.axis)}
    stop = bk["status"] != "OK"
    for it in intents.values():
        si = pos[it["signal"]]
        if it.get("exec_date") != (p.axis[si + 2] if si + 2 < len(p.axis) else None):
            out.append(f"의도 {it['id']} 실행일 ≠ 신호 + 2")
        ed = it.get("exec_date")
        if (
            it["status"] == "FILLED"
            and it["side"] == "SELL"
            and it["filled_date"] != ed
        ):
            if any(
                p.exec_ok[ci[it["ticker"]], k]
                for k in range(pos[ed], pos[it["filled_date"]])
            ):
                out.append(f"의도 {it['id']} 거래 가능일을 건너뛴 이연")
        if (
            it["status"] == "CANCELED_NOT_TRADABLE"
            and p.exec_ok[ci[it["ticker"]], pos[ed]]
        ):
            out.append(f"의도 {it['id']} 거래 가능한데 취소")
        if it["status"] == "UNEXECUTED_AFTER_END" and ed is not None and pos[ed] <= end:
            out.append(f"의도 {it['id']} 구간 안 실행일인데 미실행")
        if it["status"] == "PLANNED" or (
            not stop and it["status"] in ("DEFERRED", "NOT_RUN_CHECK_REQUIRED")
        ):
            out.append(f"의도 {it['id']} 처리되지 않음({it['status']})")
        if it["status"] == "SKIPPED_NOT_HELD":
            out.append(f"의도 {it['id']} 보유 없는 매도")
    spans: dict[str, list[tuple]] = {}
    for it in intents.values():
        if it["side"] == "SELL":
            spans.setdefault(it["ticker"], []).append(
                (it["signal"], it.get("filled_date"))
            )
    for t, sp in spans.items():
        sp.sort()
        for (s1, f1), (s2, _f2) in zip(sp, sp[1:]):
            if f1 is None or f1 > s2:
                out.append(f"{t} 살아 있는 매도 의도 중복({s1} · {s2})")
    return out


def _plan_days(bk: dict, intents: dict, cands: dict) -> list[str]:
    """계획 기록 = 공통 계획 신호 전부(멈춘 장부는 멈춘 날 전까지) · 편입 · 통상 이탈 의도는 계획일에만."""
    out = []
    stop = bk["end"].get("stopped_at") if bk["status"] != "OK" else None
    want = sorted(d for d in cands if stop is None or d < stop)
    got = [pl["signal"] for pl in bk["plans"]]
    if got != want:
        miss, extra = sorted(set(want) - set(got)), sorted(set(got) - set(want))
        out.append(
            f"계획 기록 {len(got)}개 ≠ 공통 계획 신호 {len(want)}개(빠짐 {miss[:3]} · 남음 {extra[:3]})"
        )
    days = set(got)
    odd = [
        it["id"]
        for it in intents.values()
        if (it["side"] == "BUY" or "EXIT" in (it["reason"], it.get("planned_reason")))
        and it["signal"] not in days
    ]
    if odd:
        out.append(f"계획일이 아닌 날의 편입 · 통상 이탈 의도 {odd[:3]}")
    return out


def _same_intent(it: dict, r: Optional[dict]) -> bool:
    """의도 칸(점수 · 문턱 · 간격 · 최근 · 강화) = 다시 센 검토(거래 구분 · 단기 재진입/재이탈 분모의 근거)."""
    if r is None or any(it.get(k) != r[k] for k in ("gap", "recent", "strengthened")):
        return False
    return _close(it.get("score", math.nan), r["score"]) and _close(
        it.get("threshold", math.nan), r["threshold"]
    )


def _created_at_close(it: dict, d: str) -> bool:
    """그날 종가 처리에서 만든 보호 의도(주간 판단보다 먼저 생김)."""
    return (
        it["signal"] == d and it["reason"] == "PROTECT" and "planned_reason" not in it
    )


def _review(t, s, gap, strengthen, side) -> dict:
    recent = gap is not None and 0 <= gap <= RECENT
    strong = strengthen and recent
    thr = 2 * H if strong else H
    return {
        "ticker": t,
        "score": s,
        "gap": gap,
        "recent": recent,
        "strengthened": strong,
        "threshold": thr,
        "passed": s <= -thr if side == "SELL" else s >= thr,
    }


def _same_reviews(a: list[dict], b: list[dict]) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if any(
            x[k] != y[k] for k in ("ticker", "gap", "recent", "strengthened", "passed")
        ):
            return False
        if not (
            _close(x["score"], y["score"]) and _close(x["threshold"], y["threshold"])
        ):
            return False
    return True


def _plans(p, bk, intents, scores, cands, outs, strengthen, start) -> list[str]:
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    led = {r["date"]: r for r in bk["ledger"]}
    fills = bk["fills"]
    first = True
    for pl in bk["plans"]:
        d = pl["signal"]
        i = pos[d]
        sc = scores.get(d, {})
        held = set(led[d]["pos"]) if d in led else set()
        if i >= start and d not in led:
            out.append(f"{d} 계획일 장부 행 없음")
        selling = {
            it["ticker"]
            for it in intents.values()
            if it["side"] == "SELL"
            and (it["signal"] < d or _created_at_close(it, d))
            and (it.get("filled_date") is None or it["filled_date"] > d)
        }
        entry_fill = {}
        last_sell = {}
        for f in fills:
            if f["date"] > d:
                continue
            (entry_fill if f["side"] == "BUY" else last_sell)[f["ticker"]] = pos[
                f["date"]
            ]
        exit_rev, held_out, hits = [], [], []
        for t in sorted(held - selling):
            if t in sc:
                exit_rev.append(
                    _review(t, sc[t], i - entry_fill[t], strengthen, "SELL")
                )
                if exit_rev[-1]["passed"]:
                    hits.append((sc[t], t))
            else:
                held_out.append([t, outs.get(d, {}).get(t)])
        exp_exit = [min(hits)[1]] if hits else []
        normal_its = [
            it
            for it in intents.values()
            if it["side"] == "SELL"
            and it["signal"] == d
            and (it["reason"] == "EXIT" or it.get("planned_reason") == "EXIT")
        ]
        normal = [it["ticker"] for it in normal_its]
        if normal != exp_exit:
            out.append(f"{d} 통상 이탈 {normal} ≠ 기대 {exp_exit}")
        rev_of = {r["ticker"]: r for r in exit_rev}
        if any(not _same_intent(it, rev_of.get(it["ticker"])) for it in normal_its):
            out.append(f"{d} 통상 이탈 의도 칸 ≠ 다시 센 검토")
        if not _same_reviews(pl["exit_reviews"], exit_rev):
            out.append(f"{d} 이탈 검토 기록 ≠ 다시 센 검토")
        if pl["held_not_eligible"] != held_out or any(w is None for _t, w in held_out):
            out.append(
                f"{d} 자격 밖 보유 보류 {pl['held_not_eligible']} ≠ 기대 {held_out}"
            )
        pending = {
            it["ticker"]
            for it in intents.values()
            if it["side"] == "BUY"
            and it["signal"] < d
            and it["status"] != "UNEXECUTED_AFTER_END"
            and pos[it["exec_date"]] > i
        }
        cap = PO.SLOTS - len(held) - len(pending) + len(exp_exit) + len(held & selling)
        limit = min(PO.SLOTS if first else 1, max(0, cap))
        entry_rev, expect = [], []
        if pl["cands"] != cands.get(d):
            out.append(f"{d} 후보 순서 {pl['cands']} ≠ 가격에서 다시 센 RET_120 상위 5")
        for t in cands.get(d, []):
            if len(expect) >= limit:
                break
            if t in held or t in selling or t in pending:
                continue
            gap = i - last_sell[t] if t in last_sell else None
            entry_rev.append(_review(t, sc[t], gap, strengthen, "BUY"))
            if entry_rev[-1]["passed"]:
                expect.append(t)
        buy_its = [
            it for it in intents.values() if it["side"] == "BUY" and it["signal"] == d
        ]
        buys = [it["ticker"] for it in buy_its]
        if buys != expect:
            out.append(f"{d} 편입 {buys} ≠ 기대 {expect}")
        rev_of = {r["ticker"]: r for r in entry_rev}
        order = cands.get(d, [])
        for it in buy_its:
            rank = order.index(it["ticker"]) + 1 if it["ticker"] in order else None
            if not _same_intent(it, rev_of.get(it["ticker"])) or not (
                it.get("cand_rank") == it.get("priority") == rank
            ):
                out.append(f"{d} 편입 의도 {it['id']} 칸 ≠ 다시 센 검토 · 후보 순위")
                break
        if not _same_reviews(pl["entry_reviews"], entry_rev):
            out.append(f"{d} 편입 검토 기록 ≠ 다시 센 검토")
        if pl["first"] != first or pl["limit"] != limit:
            out.append(f"{d} 첫 계획 · 한도 기록 ≠ 기대({first} · {limit})")
        first = False
    return out


def _protect(p, bk, intents, last: int) -> list[str]:
    """보유 구간 매일 종가로 보호 조건을 다시 · 새 보호 의도 또는 살아 있는 이탈의 보호 사유 변경과 대조."""
    out: list[str] = []
    ci, pos = p.ci, {d: k for k, d in enumerate(p.axis)}
    sells = [it for it in intents.values() if it["side"] == "SELL"]
    created = {
        (it["ticker"], it["signal"])
        for it in sells
        if "planned_reason" not in it and it["reason"] == "PROTECT"
    }
    relabel = {it["id"]: it for it in sells if it.get("planned_reason") == "EXIT"}
    for b in [f for f in bk["fills"] if f["side"] == "BUY"]:
        t = b["ticker"]
        s = next(
            (
                f
                for f in bk["fills"]
                if f["side"] == "SELL" and f["ticker"] == t and f["date"] > b["date"]
            ),
            None,
        )
        j, a = ci[t], pos[b["date"]]
        z = pos[s["date"]] - 1 if s else last
        peak = b["price"]
        for k in range(a, z + 1):
            c = float(p.I[j, k])
            peak = max(peak, c)
            hit = c / peak - 1.0 <= PO.PROTECT
            d = p.axis[k]
            live: Optional[dict] = next(
                (
                    it
                    for it in sells
                    if it["ticker"] == t
                    and it["signal"] < d
                    and (it.get("filled_date") is None or it["filled_date"] > d)
                ),
                None,
            )
            if hit and live is None and (t, d) not in created:
                out.append(f"{d} {t} 보호 이탈 누락")
            if (t, d) in created and not hit:
                out.append(f"{d} {t} 조건 없는 보호 이탈")
            if (
                hit
                and live is not None
                and live.get("planned_reason") is None
                and live["reason"] == "EXIT"
            ):
                out.append(f"{d} {t} 보호 조건인데 살아 있는 이탈 사유가 EXIT 그대로")
            if (
                live is not None
                and live["id"] in relabel
                and live.get("protect_at") == d
                and not hit
            ):
                out.append(f"{d} {t} 조건 없는 보호 사유 변경")
            if (
                hit
                and live is not None
                and live["id"] in relabel
                and live.get("protect_at") > d
            ):
                out.append(f"{d} {t} 보호 사유 변경이 첫 조건일보다 늦음")
    return out
