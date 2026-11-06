"""POC6-23 P/S 장부 독립 손검산 — 행동 · 점수 · 선택을 정책 · 행동 함수 없이 장부 기록에서 다시 센다.

```text
장부     POC6-21 감사의 체결 재생 · 의도 처리 · 계획일 · 보호 검산 그대로(_replay · _intents · _plan_days · _protect)
첫 계획  POC6-21 R0 첫 계획 검산(_plans · 그 계획만)
상태     보유 · 현금 · 평가 = D 장부 행 · 매도 대기 = D 까지 체결 안 된 매도 의도(그날 종가 보호 포함 · 보호로 바뀐
         이탈은 protect_at ≤ D 이면 PROTECT) · 매수 대기 = 실행일이 D 뒤인 앞선 매수 의도
행동     미결(매수 대기 · 사유 EXIT 매도) = KEEP 만 · 매도 = 보유 − 매도 대기 ∩ 자격 · 편입 = 가격에서 다시 센
         RET_120 상위 5 · 예정 슬롯 · 예산 h + (1−c)s > 1e-9 · 순서 = 거래 수 → 종류 → 코드
점수     저장 모형(β · μ · σ · 상수 · s_g)으로 z · q 를 다시 · 기록 q 와 대조 · q 최대(동점 = 앞) = 고른 행동
의도     그날 통상 의도 = 고른 행동 · 칸(행동 이름 · 점수 · 간격 · 최근 · 모형) = 다시 센 값
```

고정값(5 · 0.2 · 1e-9 · 10)은 정책 상수를 가져다 쓰지 않는다(같은 오류 재현 방지 · POC6-21 판정 §5 방식).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.trend_switch import audit as AU
from app.weekly_selection import data as D

SLOTS, SHARE, EPS, RECENT, WIDTH = 5, 0.2, 1e-9, 10, 35
KIND_ORDER = ("KEEP", "SELL", "BUY", "SWITCH")
_Q_TOL = 1e-9


def _key(n: str) -> tuple:
    if n == "KEEP":
        return (0, 0, "", "")
    kind, rest = n.split(":", 1)
    sell, buy = (
        rest.split(">")
        if kind == "SWITCH"
        else ((rest, "") if kind == "SELL" else ("", rest))
    )
    return (2 if kind == "SWITCH" else 1, KIND_ORDER.index(kind), sell, buy)


def _reason_at(it: dict, d: str) -> str:
    if it.get("planned_reason") == "EXIT":
        pa = it.get("protect_at")
        return "PROTECT" if pa is not None and pa <= d else "EXIT"
    return it["reason"]


def _u(raw, m) -> np.ndarray:
    out = np.zeros(WIDTH - 1)
    for c, x in enumerate(raw):
        if x is None or m["constant"][c]:
            continue
        out[c] = (x - m["mu"][c]) / m["sigma"][c]
    return out


def _q(n: str, held, cash, nav, rows, m, beta, cost) -> float:
    if n == "KEEP":
        return 0.0
    kind, rest = n.split(":", 1)
    sell, buy = (
        rest.split(">")
        if kind == "SWITCH"
        else ((rest, None) if kind == "SELL" else (None, rest))
    )
    s = held[sell] / nav if sell else 0.0
    b = min(SHARE, cash / nav + (1.0 - cost) * s) / (1.0 + cost) if buy else 0.0
    z = np.zeros(2 * WIDTH)
    if buy:
        z[0], z[1:WIDTH] = b, b * _u(rows[buy], m)
    if sell:
        z[WIDTH], z[WIDTH + 1 :] = s, s * _u(rows[sell], m)  # noqa: E203
    return float(beta @ z) - cost * (b + s) / m["s_g"]


def _decisions(p, bk, intents, ctx, models, kind, cost) -> list[str]:
    out: list[str] = []
    pos = {d: k for k, d in enumerate(p.axis)}
    led = {r["date"]: r for r in bk["ledger"]}
    fills = bk["fills"]
    for pl in bk["plans"][1:]:
        d = pl["signal"]
        i = pos[d]
        row = led.get(d)
        if row is None:
            out.append(f"{d} 계획일 장부 행 없음")
            continue
        held = {t: u * c for t, (u, c) in row["pos"].items()}
        nav, cash = row["value"], row["cash"]
        selling = {
            it["ticker"]: _reason_at(it, d)
            for it in intents.values()
            if it["side"] == "SELL"
            and (it["signal"] < d or AU._created_at_close(it, d))
            and (it.get("filled_date") is None or it["filled_date"] > d)
        }
        pending = {
            it["ticker"]
            for it in intents.values()
            if it["side"] == "BUY"
            and it["signal"] < d
            and it["status"] != "UNEXECUTED_AFTER_END"
            and pos[it["exec_date"]] > i
        }
        elig = ctx["members"][d]
        outs = ctx["outs"][d]
        exp_out = [
            [t, outs.get(t)] for t in sorted(held) if t not in selling and t not in elig
        ]
        if pl["held_not_eligible"] != exp_out or any(w is None for _t, w in exp_out):
            out.append(
                f"{d} 자격 밖 보유 보류 {pl['held_not_eligible']} ≠ 기대 {exp_out}"
            )
        exp_exit = [[t, selling[t]] for t in sorted(held) if t in selling]
        if pl["held_exiting"] != exp_exit:
            out.append(f"{d} 매도 대기 보유 {pl['held_exiting']} ≠ 기대 {exp_exit}")
        cands = ctx["cands"][d]
        if pl["cands"] != cands:
            out.append(f"{d} 후보 {pl['cands']} ≠ 가격에서 다시 센 RET_120 상위 5")
        if pending or any(r == "EXIT" for r in selling.values()):
            acts, why = ["KEEP"], "NORMAL_PENDING"
        else:
            sells = sorted(t for t in held if t not in selling and t in elig)
            buys = [
                t
                for t in cands
                if t not in held and t not in selling and t not in pending
            ]
            free = (
                SLOTS - len(held) - len(pending) + sum(1 for t in held if t in selling)
            )
            h = cash / nav
            acts = ["KEEP"] + [f"SELL:{t}" for t in sells]
            if free >= 1 and h > EPS:
                acts += [f"BUY:{t}" for t in buys]
            for t in sells:
                if free + 1 >= 1 and h + (1.0 - cost) * held[t] / nav > EPS:
                    acts += [f"SWITCH:{t}>{b}" for b in buys]
            acts.sort(key=_key)
            why = None if len(acts) > 1 else "NO_ACTION"
        got = [n for n, _q0 in pl["actions"]]
        if got != acts or pl["keep_only"] != why:
            out.append(
                f"{d} 행동 집합 {got[:4]}… · {pl['keep_only']} ≠ 다시 센 {acts[:4]}… · {why}"
            )
            continue
        qid = ctx["assign"][d]
        m = models[qid]
        if pl["model"] != f"{qid}_{kind}":
            out.append(f"{d} 모형 {pl['model']} ≠ 배정 {qid}_{kind}")
        beta = np.asarray(m[kind]["beta"], dtype=float)
        rows = ctx["rows"][d]
        qs = [_q(n, held, cash, nav, rows, m, beta, cost) for n in acts]
        rec = [v for _n, v in pl["actions"]]
        if any(
            not math.isfinite(a) or abs(a - b) > _Q_TOL * max(1.0, abs(b))
            for a, b in zip(rec, qs)
        ):
            out.append(f"{d} 행동 점수 기록 ≠ 다시 센 점수")
        best = 0
        for k in range(1, len(qs)):
            if qs[k] > qs[best]:
                best = k
        chosen = acts[best]
        if pl["chosen"] != chosen:
            out.append(f"{d} 고른 행동 {pl['chosen']} ≠ 다시 센 {chosen}")
            continue
        out += _intents_of(p, d, i, chosen, qs[best], pl["model"], intents, fills, pos)
    return out


def _intents_of(p, d, i, chosen, q, mid, intents, fills, pos) -> list[str]:
    out = []
    normal = [
        it
        for it in intents.values()
        if it["signal"] == d
        and (
            it["side"] == "BUY"
            or it["reason"] == "EXIT"
            or it.get("planned_reason") == "EXIT"
        )
    ]
    sell = buy = None
    if chosen != "KEEP":
        kind, rest = chosen.split(":", 1)
        sell, buy = (
            rest.split(">")
            if kind == "SWITCH"
            else ((rest, None) if kind == "SELL" else (None, rest))
        )
    want = sorted(
        x
        for x in (f"SELL:{sell}" if sell else None, f"BUY:{buy}" if buy else None)
        if x
    )
    have = sorted(f"{it['side']}:{it['ticker']}" for it in normal)
    if have != want:
        return [f"{d} 그날 통상 의도 {have} ≠ 고른 행동 {chosen}"]
    last_buy, last_sell = {}, {}
    for f in fills:
        if f["date"] <= d:
            (last_buy if f["side"] == "BUY" else last_sell)[f["ticker"]] = pos[
                f["date"]
            ]
    for it in normal:
        t = it["ticker"]
        gap = (
            (i - last_buy[t])
            if it["side"] == "SELL"
            else (i - last_sell[t] if t in last_sell else None)
        )
        recent = gap is not None and 0 <= gap <= RECENT
        ok = (
            it.get("action") == chosen
            and it.get("model") == mid
            and it.get("gap") == gap
            and it.get("recent") == recent
            and abs(it.get("score", math.nan) - q) <= _Q_TOL * max(1.0, abs(q))
        )
        if not ok:
            out.append(
                f"{d} 의도 {it['id']} 칸(행동 · 모형 · 간격 · 최근 · 점수) ≠ 다시 센 값"
            )
    return out


def audit_book(
    p: D.Panel, bk: dict, ctx: dict[str, Any], models, kind, scores_r, start, end
) -> list[str]:
    """P 또는 S 장부. ctx = {cands · outs · members · rows · assign}(가격 · 자격 · 저장 입력에서 다시 만든 값)."""
    out = AU._replay(p, bk, start, end)
    intents = {it["id"]: it for it in bk["intents"]}
    out += AU._intents(p, bk, intents, end)
    out += AU._plan_days(bk, intents, ctx["cands"])
    first = {**bk, "plans": bk["plans"][:1]}
    out += AU._plans(
        p, first, intents, scores_r, ctx["cands"], ctx["outs"], False, start
    )
    out += _decisions(p, bk, intents, ctx, models, kind, bk["cost"])
    if bk["ledger"]:
        last = min(end, p.axis.index(bk["ledger"][-1]["date"]))
        out += AU._protect(p, bk, intents, last)
    return out[:50]
