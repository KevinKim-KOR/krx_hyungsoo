"""체결 · 평가 · 주 지표 · 판정 — PLAN §3 · §4 · 판정 §2 · Q5.

```text
자리       편입 OK  = e1 행 · 체결 가능(POC7-01 exec_ok) → 합성 시가 O*
           편입 현금 = e1 행 있음 · 거래량 ≤ 0(그날 거래 없음 확인) → 0% · 비용 없음
           편입 미확인 = e1 행 없음 · 행은 있으나 체결 판정 실패(가격 관계 · 시고저종)
           청산 OK  = e2 행 · 체결 가능 · 편입과 같은 구간 → O*  · 아니면 청산 미확인
기본       여섯 자리(두 기준 × 3) 중 미확인이 하나라도 있으면 그 주 두 묶음 함께 평가 불가
대안       편입 미확인 = 현금 · 청산 미확인 = 같은 구간 e2 까지 마지막 유효 연결 종가(참고 평가액 · 날짜 남김)
           그것도 없으면 그 주 평가 불가
수익률     자리 = X(1 − c) ÷ (O*(1 + c)) − 1 · 묶음 = 세 자리 평균 · d = B − A(같은 종목 집합이면 0)
낙폭       처음 수량 · 현금 유지 · 편입 시가 → 보유 중 종가(e1 ~ e2 전날) → 평가 값 · 비용 전 · 값 빠지면 미확인
교체       지난 신호 주 목록에서 빠진 종목 수(0 ~ 3)
KODEX 200  같은 날 · 같은 비용 · 값 빠지면 그 열만 미확인(주 평가는 그대로)
```
"""

from __future__ import annotations

import math
from typing import Any, Optional

import numpy as np

from app.candidate_compare import rules as RU
from app.candidate_compare.population import Data
from app.candidate_compare.protocol import (
    ALT_COST,
    BENCH,
    COST,
    DIFF_WEEKS_MIN,
    GAIN_MIN,
    MDD_WORSE_MAX,
    SUB_WINS_MIN,
    TOP_EXCLUDE,
    TURN_MORE_MAX,
    UNCONFIRMED_SHARE_MAX,
    Config,
)
from app.entry_timing.study import bootstrap

ENTRY_OK, ENTRY_CASH, ENTRY_UNKNOWN = "OK", "CASH", "UNKNOWN"
EXIT_OK, EXIT_UNKNOWN, EXIT_REF = "OK", "UNKNOWN", "REFERENCE"
VERDICTS = {
    "UNDECIDABLE": "판정 불가",
    "SHORT": "미달",
    "CANDIDATE": "연구 후보",
    "UNCONFIRMED": "효용 미확인",
}


def _fin(v: Any) -> bool:
    return v is not None and math.isfinite(float(v))


def slot(data: Data, code: str, e1: int, e2: int) -> dict[str, Any]:
    """한 자리의 편입 · 청산 판정(값은 아직 계산하지 않음 · prepare 가 잠금에 적는다)."""
    p = data.panel
    j = p.ci[code]
    if p.has_row[j, e1] and p.exec_ok[j, e1]:
        entry, why = ENTRY_OK, None
    elif p.has_row[j, e1] and _fin(data.vol[j, e1]) and data.vol[j, e1] <= 0:
        entry, why = ENTRY_CASH, "NO_TRADE_E1"
    else:
        entry = ENTRY_UNKNOWN
        why = "NO_ROW_E1" if not p.has_row[j, e1] else "NOT_EXEC_E1"
    out: dict[str, Any] = {"code": code, "entry": entry, "exit": None, "why": why}
    if entry != ENTRY_OK:
        return out
    seg = p.seg[j, e1]
    if not p.has_row[j, e2]:
        out.update(exit=EXIT_UNKNOWN, why="NO_ROW_E2")
    elif p.seg[j, e2] != seg:
        out.update(exit=EXIT_UNKNOWN, why="SEG_BREAK")
    elif not p.exec_ok[j, e2]:
        out.update(exit=EXIT_UNKNOWN, why="NOT_EXEC_E2")
    else:
        out["exit"] = EXIT_OK
    return out


def unknown(s: dict[str, Any]) -> bool:
    return s["entry"] == ENTRY_UNKNOWN or s["exit"] == EXIT_UNKNOWN


def _ref_close(
    data: Data, j: int, e1: int, e2: int
) -> tuple[Optional[int], Optional[float]]:
    """대안 참고 평가액 — 같은 구간 · e2 까지 마지막 유효 연결 종가(위치, 값)."""
    p = data.panel
    seg = p.seg[j, e1]
    for t in range(e2, e1 - 1, -1):
        if p.has_row[j, t] and p.seg[j, t] == seg and _fin(p.I[j, t]) and p.I[j, t] > 0:
            return t, float(p.I[j, t])
    return None, None


def _path(data: Data, j: int, e1: int, e2: int, final: float) -> Optional[list[float]]:
    """편입 시가 1 → 보유 중 종가(e1 ~ e2 전날) → 평가 값 · 값이 빠지면 None."""
    p = data.panel
    o1 = float(p.O[j, e1])
    seg = p.seg[j, e1]
    out = [1.0]
    for t in range(e1, e2):
        if not (p.has_row[j, t] and p.seg[j, t] == seg and _fin(p.I[j, t])):
            return None
        out.append(float(p.I[j, t]) / o1)
    out.append(final / o1)
    return out


def mdd_size(path: list[float]) -> float:
    """경로의 최대 낙폭 크기(≥ 0)."""
    peak = path[0]
    worst = 0.0
    for v in path:
        peak = max(peak, v)
        worst = max(worst, 1.0 - v / peak)
    return worst


def basket(
    data: Data, codes: list[str], e1: int, e2: int, cost: float, alt: bool
) -> dict[str, Any]:
    """한 기준의 세 자리 — 수익률(비용 후) · 낙폭(비용 전) · 자리 기록. 값을 못 내면 ret = None."""
    p = data.panel
    slots, rets, paths = [], [], []
    ok = True
    for code in codes:
        s = slot(data, code, e1, e2)
        j = p.ci[code]
        rec = dict(s)
        if s["entry"] == ENTRY_CASH or (alt and s["entry"] == ENTRY_UNKNOWN):
            rec["value"] = "CASH"
            rets.append(0.0)
            paths.append(None)  # 현금 = 1 유지
        elif s["entry"] == ENTRY_UNKNOWN:
            ok = False
        else:
            o1 = float(p.O[j, e1])
            if s["exit"] == EXIT_OK:
                x = float(p.O[j, e2])
            elif alt:
                t, x = _ref_close(data, j, e1, e2)
                if t is None:
                    ok = False
                    slots.append(rec)
                    continue
                rec.update(exit=EXIT_REF, ref_date=p.axis[t])
            else:
                ok = False
                slots.append(rec)
                continue
            rets.append(x * (1.0 - cost) / (o1 * (1.0 + cost)) - 1.0)
            paths.append(_path(data, j, e1, e2, x))
            rec.update(entry_px=o1, exit_px=x)
        slots.append(rec)
    out: dict[str, Any] = {"slots": slots, "ret": None, "mdd": None}
    if not ok or len(rets) != len(codes):
        return out
    out["ret"] = sum(rets) / len(rets)
    cash = [sl.get("value") == "CASH" for sl in slots]
    if all(c or pt is not None for c, pt in zip(cash, paths)):
        n = e2 - e1 + 2  # 편입 시가 + 종가(e1 ~ e2 전날) + 평가 값
        agg = [
            sum(1.0 if c else pt[t] for c, pt in zip(cash, paths)) / len(paths)
            for t in range(n)
        ]
        out["mdd"] = mdd_size(agg)
    return out


def kodex(data: Data, e1: int, e2: int, cost: float) -> Optional[float]:
    p = data.panel
    j = p.ci[BENCH]
    if (
        p.has_row[j, e1]
        and p.exec_ok[j, e1]
        and p.has_row[j, e2]
        and p.exec_ok[j, e2]
        and p.seg[j, e2] == p.seg[j, e1]
    ):
        return (
            float(p.O[j, e2]) * (1.0 - cost) / (float(p.O[j, e1]) * (1.0 + cost)) - 1.0
        )
    return None


def evaluate_week(
    data: Data, w: dict[str, Any], cost: float, alt: bool
) -> dict[str, Any]:
    """한 주 — 두 기준 묶음 · d · KODEX 200 · 사유."""
    out: dict[str, Any] = {
        "status": w["status"],
        "ret_a": None,
        "ret_b": None,
        "d": None,
    }
    if w["status"] != "OK":
        return out
    pos = {d: i for i, d in enumerate(data.axis)}
    e1, e2 = pos[w["entry"]], pos[w["exit"]]
    a = basket(data, w["a"], e1, e2, cost, alt)
    b = basket(data, w["b"], e1, e2, cost, alt)
    reasons = [
        [rule, s["code"], s["why"]]
        for rule, bk in (("A", a), ("B", b))
        for s in bk["slots"]
        if s["why"] is not None
    ]
    out.update(slots_a=a["slots"], slots_b=b["slots"], reasons=reasons)
    if a["ret"] is None or b["ret"] is None:
        out["status"] = "INVALID"
        return out
    out.update(
        ret_a=a["ret"],
        ret_b=b["ret"],
        d=0.0 if w["same"] else b["ret"] - a["ret"],
        mdd_a=a["mdd"],
        mdd_b=b["mdd"],
        kodex=kodex(data, e1, e2, cost),
    )
    return out


def unconfirmed_slots(rows: list[dict[str, Any]], alt: bool) -> tuple[int, int]:
    """(미확인 자리, 실제 배정 자리) — 기본 = 편입 · 청산 미확인 · 대안 = 값을 끝내 못 낸 자리."""
    bad = total = 0
    for r in rows:
        if r["status"] not in ("OK", "INVALID"):
            continue
        for s in r.get("slots_a", []) + r.get("slots_b", []):
            total += 1
            if alt:
                bad += int(s["entry"] == ENTRY_OK and s["exit"] == EXIT_UNKNOWN)
            else:
                bad += int(unknown(s))
    return bad, total


def evaluate(data: Data, weeks: list[dict[str, Any]], cfg: Config) -> dict[str, Any]:
    """모든 주 · 기본 / 대안 / 참고 40bp."""
    prev: dict[str, Optional[dict]] = {}
    rows = []
    for w in weeks:
        base = evaluate_week(data, w, COST, alt=False)
        alt = evaluate_week(data, w, COST, alt=True)
        c40 = evaluate_week(data, w, ALT_COST, alt=False)
        last = prev.get(w["span"])
        turn_a = turn_b = None
        if w["status"] == "OK" and last is not None and last["status"] == "OK":
            turn_a = RU.changed_count(w["a"], last["a"])
            turn_b = RU.changed_count(w["b"], last["b"])
        prev[w["span"]] = w
        rows.append(
            {
                "signal": w["signal"],
                "span": w["span"],
                "sub": w["sub"],
                "same": w["same"],
                "turn_a": turn_a,
                "turn_b": turn_b,
                "base": base,
                "alt": alt,
                "cost40": {k: c40[k] for k in ("status", "ret_a", "ret_b", "d")},
            }
        )
    return {
        "rows": rows,
        "main": summarize(rows, cfg, "main", "base"),
        "alt": summarize(rows, cfg, "main", "alt"),
        "cost40": summarize(rows, cfg, "main", "cost40"),
        "aux": summarize(rows, cfg, "aux", "base"),
    }


def _mean(xs: list[float]) -> Optional[float]:
    return float(sum(xs) / len(xs)) if xs else None


def summarize(rows: list[dict], cfg: Config, span: str, key: str) -> dict[str, Any]:
    rs = [r for r in rows if r["span"] == span]
    ev = [r for r in rs if r[key]["status"] == "OK" and r[key]["d"] is not None]
    ds = [r[key]["d"] for r in ev]
    out: dict[str, Any] = {
        "weeks": len(rs),
        "ok_weeks": sum(1 for r in rs if r[key]["status"] in ("OK", "INVALID")),
        "valid_weeks": len(ev),
        "invalid_weeks": sum(1 for r in rs if r[key]["status"] == "INVALID"),
        "delta": _mean(ds),
    }
    if key == "cost40":
        return out
    bad, total = unconfirmed_slots([r[key] for r in rs], alt=(key == "alt"))
    alt = key == "alt"
    dropped: dict[str, int] = {}
    cash = assumed_cash = reference = 0
    for r in rs:
        for sl in r[key].get("slots_a", []) + r[key].get("slots_b", []):
            if sl["entry"] == ENTRY_CASH:
                cash += 1
            elif alt and sl["entry"] == ENTRY_UNKNOWN:
                assumed_cash += 1  # 대안 가정 — 빠진 자리가 아님
            if sl.get("exit") == EXIT_REF:
                reference += 1  # 대안 참고 평가액 — 빠진 자리가 아님
            gone = (
                (sl["entry"] == ENTRY_OK and sl["exit"] == EXIT_UNKNOWN)
                if alt
                else unknown(sl)
            )
            if gone:
                dropped[sl["why"]] = dropped.get(sl["why"], 0) + 1
    slots = [
        r[key]["d"] if r[key]["status"] == "OK" and r[key]["d"] is not None else None
        for r in rs
    ]
    subs = []
    for k in range(len(cfg.subs)):
        sd = [r[key]["d"] for r in ev if r["sub"] == k]
        subs.append({"weeks": len(sd), "delta": _mean(sd)})
    diff = [r for r in ev if r["same"] is False]
    both = [
        r
        for r in ev
        if r[key].get("mdd_a") is not None and r[key].get("mdd_b") is not None
    ]
    ma = [r[key]["mdd_a"] for r in both]
    mb = [r[key]["mdd_b"] for r in both]
    ta = [r["turn_a"] for r in rs if r["turn_a"] is not None]
    tb = [r["turn_b"] for r in rs if r["turn_b"] is not None]
    kd = [r for r in ev if r[key].get("kodex") is not None]
    top = sorted(ds, reverse=True)[TOP_EXCLUDE:]
    out.update(
        unconfirmed_slots=bad,
        assigned_slots=total,
        unconfirmed_share=(bad / total) if total else None,
        dropped_reasons=dropped,
        cash_slots=cash,
        assumed_cash_slots=assumed_cash,
        reference_slots=reference,
        bootstrap=bootstrap(slots) if span == "main" else None,
        subs=subs,
        sub_wins=sum(1 for s in subs if s["delta"] is not None and s["delta"] > 0),
        diff_weeks=len(diff),
        diff_delta=_mean([r[key]["d"] for r in diff]),
        mdd={
            "weeks": len(both),
            "a_mean": _mean(ma),
            "b_mean": _mean(mb),
            "a_p95": float(np.percentile(ma, 95)) if ma else None,
            "b_p95": float(np.percentile(mb, 95)) if mb else None,
            "b_minus_a": (_mean(mb) - _mean(ma)) if both else None,
        },
        turnover={
            "weeks": len(ta),
            "a_mean": _mean(ta),
            "b_mean": _mean(tb),
            "b_minus_a": (_mean(tb) - _mean(ta)) if ta and tb else None,
        },
        kodex={
            "weeks": len(kd),
            "a_minus_k": _mean([r[key]["ret_a"] - r[key]["kodex"] for r in kd]),
            "b_minus_k": _mean([r[key]["ret_b"] - r[key]["kodex"] for r in kd]),
        },
        delta_without_top=_mean(top),
        mean_a=_mean([r[key]["ret_a"] for r in ev]),
        mean_b=_mean([r[key]["ret_b"] for r in ev]),
    )
    return out


def data_ok(s: dict[str, Any], cfg: Config) -> bool:
    share = s.get("unconfirmed_share")
    return (
        s["valid_weeks"] > 0
        and s["valid_weeks"] >= cfg.valid_weeks_min
        and share is not None
        and share <= UNCONFIRMED_SHARE_MAX
    )


def conditions(s: dict[str, Any]) -> dict[str, bool]:
    """연구 후보 조건 ① ~ ⑥(PLAN §4)."""
    bs = s.get("bootstrap") or {}
    mdd, turn = s["mdd"], s["turnover"]
    return {
        "1_lower_bound": bs.get("lo") is not None and bs["lo"] > 0,
        "2_gain": s["delta"] is not None and s["delta"] >= GAIN_MIN,
        "3_subs": s["sub_wins"] >= SUB_WINS_MIN,
        "4_mdd": mdd["weeks"] > 0
        and mdd["b_minus_a"] is not None
        and mdd["b_minus_a"] <= MDD_WORSE_MAX,
        "5_turnover": turn["b_minus_a"] is not None
        and turn["b_minus_a"] <= TURN_MORE_MAX,
        "6_diff_weeks": s["diff_weeks"] >= DIFF_WEEKS_MIN,
    }


def judge(base: dict[str, Any], alt: dict[str, Any], cfg: Config) -> dict[str, Any]:
    """판정 순서: 판정 불가 → 미달 → 연구 후보(① ~ ⑦) → 효용 미확인."""
    out: dict[str, Any] = {"data_ok": data_ok(base, cfg)}
    if not out["data_ok"]:
        return {**out, "code": "UNDECIDABLE", "label": VERDICTS["UNDECIDABLE"]}
    if base["delta"] is None or base["delta"] <= 0:
        return {**out, "code": "SHORT", "label": VERDICTS["SHORT"]}
    cond = conditions(base)
    alt_cond = conditions(alt)
    alt_ok = data_ok(alt, cfg) and all(alt_cond.values())
    out.update(conditions=cond, alt_data_ok=data_ok(alt, cfg), alt_conditions=alt_cond)
    cond["7_alternative"] = alt_ok
    code = "CANDIDATE" if all(cond.values()) else "UNCONFIRMED"
    return {**out, "code": code, "label": VERDICTS[code]}


def worked_case(
    data: Data, weeks: list[dict], rows: list[dict]
) -> Optional[dict[str, Any]]:
    """AC2 손 계산용 — 선택이 갈리고 평가가 가능한 첫 주(본 구간) · 없으면 None."""
    by = {w["signal"]: w for w in weeks}
    for r in rows:
        if r["span"] != "main" or r["same"] is not False or r["base"]["status"] != "OK":
            continue
        w = by[r["signal"]]
        return {
            "signal": w["signal"],
            "window": w["window"],
            "weekly_dates": w["weekly_dates"],
            "entry": w["entry"],
            "exit": w["exit"],
            "n_common": w["n_common"],
            "a": w["a"],
            "b": w["b"],
            "a_order": w["a_order"],
            "b_order": w["b_order"],
            "picks": w["picks"],
            "slots_a": r["base"]["slots_a"],
            "slots_b": r["base"]["slots_b"],
            "ret_a": r["base"]["ret_a"],
            "ret_b": r["base"]["ret_b"],
            "d": r["base"]["d"],
        }
    return None
