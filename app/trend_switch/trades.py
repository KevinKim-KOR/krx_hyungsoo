"""POC6-21 거래 · 묶음 · 회복 · 검토 기회 · 보류 분모 — 통합 설계 §5(직전 손익) · §7 AC3 · AC4 · 판정 §A-4.

```text
거래     같은 종목의 매수 체결 → 다음 전량 매도 체결 · 손익 = 매도 순대금 − 매수 예산(비용 포함) · 장부 현금흐름 그대로
         진입 구분 = 첫 진입 · 재진입(직전 완료 거래 있음) · 단기 재진입(판단일 − 마지막 매도 ≤ 10거래일)
         이탈 구분 = 보호(PROTECT) · 단기 재이탈(판단일 − 진입 체결 ≤ 10거래일) · 통상 · 끝까지 보유(열림)
         재이탈 = 판단일 종가 평가손익(미확정)과 실제 청산 순손익을 나란히 · 보유 중 최고 평가이익 · 반납
직전     재진입의 직전 완료 거래 순손익 = 이익 · 손실 · 0 · 이력 없음 — 거래 수 · 날짜 수 · 순손익 · 비용
묶음     같은 종목에서 직전 이탈 체결 → 다음 진입 체결 ≤ 10거래일이면 연결 · 순손익 = 현금흐름 합(열린 끝 = 평가 · 표시)
회복     직전 최고 평가자산(시작 100 포함)을 밑도는 연속 거래일의 최장 · 끝에서 미회복이면 따로 표시
검토     강화 기회 = 강화 곡선에서 2h 를 대입한 문턱 판정 직전의 검토(편입 · 이탈별 건수 · 날짜 수 · 통과)
보류     자격 밖 보유의 통상 판단 보류(종목 · 주 · 일 · 사유) — ML 유지 권고가 아님
```

체결되지 않은 의도 · 취소는 거래로 세지 않는다. 개별 거래 승률과 장부 성과를 구분한다(설명 · 판정 입력 아님).
"""

from __future__ import annotations

from typing import Any, Optional

from app.trend_switch import policy as TP
from app.weekly_selection.data import Panel

KINDS_IN = ("ENTRY", "REENTRY", "SHORT_REENTRY")
KINDS_OUT = ("EXIT", "SHORT_REEXIT", "PROTECT", "OPEN")
PRIOR = ("GAIN", "LOSS", "ZERO", "NONE")


def _cls(pnl: Optional[float]) -> str:
    if pnl is None:
        return "NONE"
    return "GAIN" if pnl > 0 else ("LOSS" if pnl < 0 else "ZERO")


def trade_list(p: Panel, bk: dict) -> list[dict]:
    pos = {d: k for k, d in enumerate(p.axis)}
    ci = p.ci
    intents = {it["id"]: it for it in bk["intents"]}
    open_: dict[str, dict] = {}
    prev: dict[str, dict] = {}
    out: list[dict] = []
    for f in bk["fills"]:
        t = f["ticker"]
        if f["side"] == "BUY":
            open_[t] = _entry(f, intents[f["intent"]], prev.get(t), pos)
            out.append(open_[t])
            continue
        tr = open_.pop(t)
        it = intents[f["intent"]]
        j, a, z = ci[t], pos[tr["entry_date"]], pos[f["date"]]
        sell_cash = f["notional"] - f["cost"]
        peak = (
            max(float(p.I[j, k]) for k in range(a, z)) if z > a else tr["entry_price"]
        )
        sig_close = float(p.I[j, pos[it["signal"]]])
        pnl = sell_cash - tr["buy_cash"]
        kind = (
            "PROTECT"
            if it["reason"] == "PROTECT"
            else ("SHORT_REEXIT" if it.get("recent") else "EXIT")
        )
        tr.update(
            exit_kind=kind,
            exit_date=f["date"],
            exit_signal=it["signal"],
            exit_price=f["price"],
            exit_reason=it["reason"],
            exit_planned_reason=it.get("planned_reason"),
            exit_score=it.get("score"),
            exit_gap=it.get("gap"),
            exit_strengthened=it.get("strengthened", False),
            sell_cash=sell_cash,
            pnl=pnl,
            ret=pnl / tr["buy_cash"],
            costs=tr["costs"] + f["cost"],
            market_days=z - a,
            unrealized_at_signal=tr["units"] * sig_close - tr["buy_cash"],
            peak_unrealized=tr["units"] * peak - tr["buy_cash"],
            giveback=tr["units"] * peak - tr["buy_cash"] - pnl,
        )
        prev[t] = tr
    last = bk["ledger"][-1] if bk["ledger"] else None
    for t, tr in open_.items():
        c = (last["pos"].get(t) or [None, None])[1] if last else None
        tr.update(
            exit_kind="OPEN",
            end_date=last["date"] if last else None,
            unrealized_at_end=None if c is None else tr["units"] * c - tr["buy_cash"],
        )
    return out


def _entry(f: dict, it: dict, prior: Optional[dict], pos: dict[str, int]) -> dict:
    kind = (
        "ENTRY"
        if prior is None
        else ("SHORT_REENTRY" if it.get("recent") else "REENTRY")
    )
    return {
        "ticker": f["ticker"],
        "entry_kind": kind,
        "entry_signal": it["signal"],
        "entry_date": f["date"],
        "entry_price": f["price"],
        "units": f["units"],
        "buy_cash": f["notional"] + f["cost"],
        "costs": f["cost"],
        "entry_score": it.get("score"),
        "entry_gap": it.get("gap"),
        "entry_strengthened": it.get("strengthened", False),
        "cand_rank": it.get("cand_rank"),
        "prior": _cls(None if prior is None else prior["pnl"]),
        "prior_exit_kind": None if prior is None else prior["exit_kind"],
        "reentry_vs_prior_exit": (
            None if prior is None else f["price"] / prior["exit_price"] - 1.0
        ),
        "fill_gap_from_prior_exit": (
            None if prior is None else pos[f["date"]] - pos[prior["exit_date"]]
        ),
    }


def _sum(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows if r.get(key) is not None)


def _group(rows: list[dict], key: str = "entry_date") -> dict[str, Any]:
    """key = 발생 날짜(진입 · 직전 손익 묶음 = 진입 체결일 · 이탈 구분 = 이탈 체결일 · 열림은 이탈 날짜 없음)."""
    closed = [r for r in rows if r["exit_kind"] != "OPEN"]
    return {
        "trades": len(rows),
        "closed": len(closed),
        "open": len(rows) - len(closed),
        "dates": len({r[key] for r in rows if r.get(key)}),
        "pnl_closed": _sum(closed, "pnl"),
        "costs_closed": _sum(closed, "costs"),
        "wins_closed": sum(1 for r in closed if r["pnl"] > 0),
    }


def bundles(rows: list[dict], pos: dict[str, int]) -> dict[str, Any]:
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["ticker"], []).append(r)
    items = []
    for t, trs in sorted(by.items()):
        cur = [trs[0]]
        for a, b in zip(trs, trs[1:]):
            linked = (
                a["exit_kind"] != "OPEN"
                and pos[b["entry_date"]] - pos[a["exit_date"]] <= TP.RECENT_DAYS
            )
            if linked:
                cur.append(b)
                continue
            items.append(cur)
            cur = [b]
        items.append(cur)
    multi = [c for c in items if len(c) > 1]
    out = []
    for c in multi:
        closed = [r for r in c if r["exit_kind"] != "OPEN"]
        tail = c[-1] if c[-1]["exit_kind"] == "OPEN" else None
        out.append(
            {
                "ticker": c[0]["ticker"],
                "trades": len(c),
                "first_entry": c[0]["entry_date"],
                "last_exit": None if tail else c[-1]["exit_date"],
                "pnl_closed": _sum(closed, "pnl"),
                "costs": _sum(c, "costs"),
                "open_tail_unrealized": (
                    None if tail is None else tail["unrealized_at_end"]
                ),
            }
        )
    return {
        "bundles": len(out),
        "trades_in_bundles": sum(b["trades"] for b in out),
        "pnl_closed": sum(b["pnl_closed"] for b in out),
        "costs": sum(b["costs"] for b in out),
        "open_tail": sum(1 for b in out if b["open_tail_unrealized"] is not None),
        "items": out,
    }


def underwater(ledger: list[dict], base: float) -> dict[str, Any]:
    peak, run, best, span, start = base, 0, 0, (None, None), None
    for r in ledger:
        if r["value"] >= peak:
            peak, run = r["value"], 0
            continue
        run += 1
        start = r["date"] if run == 1 else start
        if (
            run >= best
        ):  # 같은 길이면 나중 구간(끝에서 열린 구간이면 그 구간을 가리킨다)
            best, span = run, (start, r["date"])
    return {
        "longest_days": best,
        "longest_start": span[0],
        "longest_end": span[1],
        "underwater_at_end": run > 0,
        "days_at_end": run,
        "longest_open_at_end": run > 0 and run == best,
    }


def underwater_sub(ledger: list[dict], bounds, base: float) -> list[dict]:
    """보조 구간별 최장 고점 미회복 — 기준 = 구간 전 마지막 평가(없으면 시작 100 · H1 subperiods 와 같은 기준)."""
    out = []
    for lo, hi in bounds or ():
        rows = [r for r in ledger if lo <= r["date"] <= hi]
        before = [r for r in ledger if r["date"] < lo]
        out.append(
            {
                "bounds": [lo, hi],
                **underwater(rows, before[-1]["value"] if before else base),
            }
        )
    return out


def cash(ledger: list[dict]) -> dict[str, Any]:
    """현금 비중(현금/평가) — 평균 · 끝 · 보유 0종목 날 수(시작일은 늘 현금이라 최대값은 쓰지 않는다)."""
    w = [r["cash"] / r["value"] for r in ledger]
    return {
        "days": len(ledger),
        "avg_cash_weight": sum(w) / len(w) if w else None,
        "end_cash_weight": w[-1] if w else None,
        "full_cash_days": sum(1 for r in ledger if not r["pos"]),
    }


def reviews(bk: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for side, key in (("entry", "entry_reviews"), ("exit", "exit_reviews")):
        rs = [(pl["signal"], r) for pl in bk["plans"] for r in pl[key]]
        strong = [(d, r) for d, r in rs if r["strengthened"]]
        out[side] = {
            "reviews": len(rs),
            "recent": sum(1 for _d, r in rs if r["recent"]),
            "strengthened": len(strong),
            "strengthened_dates": len({d for d, _r in strong}),
            "strengthened_passed": sum(1 for _d, r in strong if r["passed"]),
        }
    return out


def held_out(bk: dict) -> dict[str, Any]:
    """자격 밖 보유의 통상 판단 보류 — (계획 · 종목) 쌍 · 날짜 · 종목 · 사유 · 그 상태로 보유한 장부 일수."""
    pairs = [
        (pl["signal"], t, why)
        for pl in bk["plans"]
        for t, why in pl["held_not_eligible"]
    ]
    status: dict[str, bool] = {}
    plans = {pl["signal"]: pl for pl in bk["plans"]}
    days = 0
    for r in bk["ledger"]:
        pl = plans.get(r["date"])
        if pl is not None:
            out_now = {t for t, _w in pl["held_not_eligible"]}
            status = {t: t in out_now for t in r["pos"]}
        days += sum(1 for t in r["pos"] if status.get(t))
    reasons: dict[str, int] = {}
    for _d, _t, why in pairs:
        reasons[why] = reasons.get(why, 0) + 1
    return {
        "pairs": len(pairs),
        "dates": len({d for d, _t, _w in pairs}),
        "tickers": sorted({t for _d, t, _w in pairs}),
        "reasons": dict(sorted(reasons.items())),
        "held_days": days,
    }


def analyze(p: Panel, bk: dict, base: float) -> dict[str, Any]:
    pos = {d: k for k, d in enumerate(p.axis)}
    rows = trade_list(p, bk)
    reexit = [r for r in rows if r["exit_kind"] == "SHORT_REEXIT"]
    return {
        "by_entry_kind": {
            k: _group([r for r in rows if r["entry_kind"] == k]) for k in KINDS_IN
        },
        "by_exit_kind": {
            k: _group([r for r in rows if r["exit_kind"] == k], "exit_date")
            for k in KINDS_OUT
        },
        "reentry_by_prior": {
            k: _group(
                [r for r in rows if r["entry_kind"] != "ENTRY" and r["prior"] == k]
            )
            for k in PRIOR
        },
        "short_reentry_by_prior": {
            k: _group(
                [
                    r
                    for r in rows
                    if r["entry_kind"] == "SHORT_REENTRY" and r["prior"] == k
                ]
            )
            for k in PRIOR
        },
        "short_reexit": {
            "trades": len(reexit),
            "unrealized_at_signal": _sum(reexit, "unrealized_at_signal"),
            "pnl": _sum(reexit, "pnl"),
        },
        "bundles": bundles(rows, pos),
        "underwater": underwater(bk["ledger"], base),
        "cash": cash(bk["ledger"]),
        "reviews": reviews(bk),
        "held_not_eligible": held_out(bk),
        "costs_total": sum(f["cost"] for f in bk["fills"]),
        "trades": rows,
    }
