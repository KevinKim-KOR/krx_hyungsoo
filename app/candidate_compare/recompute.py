"""독립 재계산 ② 분모 · 자리 수 · 요약 · 판정 · 손 계산 주 · 전체 재계산(PLAN §2-3 · §3-3 · §4 · 판정 §3).

주 기록 · 주 평가는 `recompute_weeks.py`(봉인 reader 계열 + 원시 행) · 판정 순서 함수는 실행과 같은
`study.judge`(판정 기준 자체를 다시 쓰지 않음) · 구간 추정은 POC7-01 `entry_timing.study.bootstrap`.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from app.candidate_compare import study as ST
from app.candidate_compare.protocol import ALT_COST, COST, TOP_EXCLUDE, Config
from app.candidate_compare.recompute_weeks import (
    Src,
    _evaluate_week,
    _slot,
    _week,
    _week_record,
)
from app.entry_timing.study import bootstrap

KEYS = (("base", COST, False), ("alt", COST, True), ("cost40", ALT_COST, False))


# ── 분모 · 자리 수 · 요약 · 판정 · 손 계산 주 ──────────────────────────────────


def _counts(weeks: list[dict], spans: dict) -> dict[str, dict[str, Any]]:
    out = {}
    for span in spans:
        ws = [w for w in weeks if w["span"] == span]
        pops = sorted(w["n_pop"] for w in ws)
        out[span] = {
            "weeks": len(ws),
            "ok_weeks": sum(1 for w in ws if w["status"] == "OK"),
            "few_weeks": sum(1 for w in ws if w["status"] == "FEW"),
            "immature_weeks": sum(1 for w in ws if w["status"] == "IMMATURE"),
            "common_missing": sum(len(w["dropped"]) for w in ws),
            "dropped_top3_weeks": sum(1 for w in ws if w["dropped_top3"]),
            "dropped_top30_weeks": sum(1 for w in ws if w["dropped_top30"]),
            "weekly_before_window": sum(1 for w in ws if w["weekly_before_window"]),
            "pop_median": float(np.median(pops)) if pops else None,
            "pop_min": pops[0] if pops else None,
            "pop_max": pops[-1] if pops else None,
            "same_weeks": sum(1 for w in ws if w["same"] is True),
            "first": ws[0]["signal"] if ws else None,
            "last": ws[-1]["signal"] if ws else None,
        }
    return out


def _slot_counts(src: Src, weeks: list[dict]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for w in weeks:
        c = out.setdefault(
            w["span"],
            {
                "assigned": 0,
                "entry_ok": 0,
                "cash": 0,
                "entry_unknown": 0,
                "exit_unknown": 0,
                "weeks_with_unknown": 0,
            },
        )
        if w["status"] != "OK":
            continue
        bad = False
        for code in w["a"] + w["b"]:
            s = _slot(src, code, w["entry"], w["exit"])
            c["assigned"] += 1
            c["entry_ok"] += int(s["entry"] == "OK")
            c["cash"] += int(s["entry"] == "CASH")
            c["entry_unknown"] += int(s["entry"] == "UNKNOWN")
            c["exit_unknown"] += int(s["exit"] == "UNKNOWN")
            bad = bad or s["entry"] == "UNKNOWN" or s["exit"] == "UNKNOWN"
        c["weeks_with_unknown"] += int(bad)
    return out


def _mean(xs: list[float]) -> Optional[float]:
    return float(sum(xs) / len(xs)) if xs else None


def summary(rows: list[dict], cfg: Config, span: str, key: str) -> dict[str, Any]:
    """실행의 study.summarize 와 같은 칸을 따로 계산."""
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
    alt = key == "alt"
    slots = [
        s for r in rs for s in r[key].get("slots_a", []) + r[key].get("slots_b", [])
    ]
    gone = [
        s
        for s in slots
        if (
            (s["entry"] == "OK" and s["exit"] == "UNKNOWN")
            if alt
            else (s["entry"] == "UNKNOWN" or s["exit"] == "UNKNOWN")
        )
    ]
    reasons: dict[str, int] = {}
    for s in gone:
        reasons[s["why"]] = reasons.get(s["why"], 0) + 1
    both = [
        r for r in ev if r[key]["mdd_a"] is not None and r[key]["mdd_b"] is not None
    ]
    ma = [r[key]["mdd_a"] for r in both]
    mb = [r[key]["mdd_b"] for r in both]
    ta = [r["turn_a"] for r in rs if r["turn_a"] is not None]
    tb = [r["turn_b"] for r in rs if r["turn_b"] is not None]
    kd = [r for r in ev if r[key]["kodex"] is not None]
    diff_w = [r for r in ev if r["same"] is False]
    subs = []
    for k in range(len(cfg.subs)):
        sd = [r[key]["d"] for r in ev if r["sub"] == k]
        subs.append({"weeks": len(sd), "delta": _mean(sd)})
    boot = None
    if span == "main":
        boot = bootstrap(
            [
                (
                    r[key]["d"]
                    if r[key]["status"] == "OK" and r[key]["d"] is not None
                    else None
                )
                for r in rs
            ]
        )
    out.update(
        unconfirmed_slots=len(gone),
        assigned_slots=len(slots),
        unconfirmed_share=len(gone) / len(slots) if slots else None,
        dropped_reasons=reasons,
        cash_slots=sum(1 for s in slots if s["entry"] == "CASH"),
        assumed_cash_slots=sum(1 for s in slots if alt and s["entry"] == "UNKNOWN"),
        reference_slots=sum(1 for s in slots if s.get("exit") == "REFERENCE"),
        bootstrap=boot,
        subs=subs,
        sub_wins=sum(1 for x in subs if x["delta"] is not None and x["delta"] > 0),
        diff_weeks=len(diff_w),
        diff_delta=_mean([r[key]["d"] for r in diff_w]),
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
        delta_without_top=_mean(sorted(ds, reverse=True)[TOP_EXCLUDE:]),
        mean_a=_mean([r[key]["ret_a"] for r in ev]),
        mean_b=_mean([r[key]["ret_b"] for r in ev]),
    )
    return out


def _worked_case(weeks: list[dict], rows: list[dict]) -> Optional[dict[str, Any]]:
    by = {w["signal"]: w for w in weeks}
    for r in rows:
        if r["span"] != "main" or r["same"] is not False or r["base"]["status"] != "OK":
            continue
        w = by[r["signal"]]
        keys = (
            "signal",
            "window",
            "weekly_dates",
            "entry",
            "exit",
            "n_common",
            "a",
            "b",
        )
        out = {k: w[k] for k in keys + ("a_order", "b_order", "picks")}
        out.update(
            {k: r["base"][k] for k in ("slots_a", "slots_b", "ret_a", "ret_b", "d")}
        )
        return out
    return None


def rebuild(cfg: Config) -> dict[str, Any]:
    """실행 산출물과 같은 모양 — 주 기록 · 주 평가 · 분모 · 자리 수 · 요약 · 판정 · 손 계산 주 · 봉인."""
    src = Src(cfg)
    axis = src.axis
    sig = [i for i in range(len(axis) - 1) if _week(axis[i]) != _week(axis[i + 1])]
    weeks = [
        w
        for w in (_week_record(src, k, sig, cfg) for k in range(len(sig)))
        if w is not None
    ]
    rows: list[dict] = []
    prev: dict[str, dict] = {}
    for w in weeks:
        last = prev.get(w["span"])
        turn_a = turn_b = None
        if w["status"] == "OK" and last is not None and last["status"] == "OK":
            turn_a = len(set(last["a"]) - set(w["a"]))
            turn_b = len(set(last["b"]) - set(w["b"]))
        prev[w["span"]] = w
        ev = {key: _evaluate_week(src, w, cost, alt) for key, cost, alt in KEYS}
        rows.append(
            {
                "signal": w["signal"],
                "span": w["span"],
                "sub": w["sub"],
                "same": w["same"],
                "turn_a": turn_a,
                "turn_b": turn_b,
                "base": ev["base"],
                "alt": ev["alt"],
                "cost40": {
                    k: ev["cost40"][k] for k in ("status", "ret_a", "ret_b", "d")
                },
            }
        )
    main, alt = summary(rows, cfg, "main", "base"), summary(rows, cfg, "main", "alt")
    return {
        "weeks": weeks,
        "rows": rows,
        "seal": src.seal,
        "counts": _counts(weeks, cfg.spans),
        "slot_counts": _slot_counts(src, weeks),
        "main": main,
        "alt": alt,
        "cost40": summary(rows, cfg, "main", "cost40"),
        "aux": summary(rows, cfg, "aux", "base"),
        "verdict": ST.judge(main, alt, cfg),
        "worked_case": _worked_case(weeks, rows),
    }
