"""경로별 주 수익 · 차이 · 블록 부트스트랩 · 1주 노출 낙폭 · 판정 — PLAN §3 · §4(판정 2026-11-22 우선).

```text
짝      즉시 값 = 100/(1+c) × P_T/P_E · 보류 값 = 100/(1+c) · 규칙 = 그 주 결정 쪽 · K = 069500 같은 방식
주      평가 가능 주(짝 ≥ 1 · 069500 체결 가능)의 같은 가중 평균 = 한 관측 · 빠진 주는 모든 비교에서 같이 뺌
차이    Δ = 주별 (규칙 − 즉시) 평균(즉시를 고른 주 = 0) · 피함/놓침 = 보류 주의 (보류 − 즉시) 부호
불확실  본 구간 신호 주 달력 자리(빠진 주 = 빈 자리) · 13주 순환 블록 · 2,000회 · seed 고정 · 평균 = 유효 주
낙폭    비용을 뺀 가격 비율의 1주 노출 경로(보류 주 = 1) · D+1 → D'+1 주 간격
판정    D(자료 손실) → C(Δ ≤ 0 · 규칙 낙폭 > 즉시) → A(① ~ ⑦ 모두) → B(나머지) · 반올림 전 값
```
"""

from __future__ import annotations

import collections
from typing import Any, Optional

import numpy as np

from app.entry_timing import weekly as W
from app.entry_timing.data import Panel
from app.entry_timing.protocol import (
    ALT_COST,
    BASE_COST,
    BENCH,
    BLOCK_WEEKS,
    DRAWS,
    EVAL_SHARE_MIN,
    EXCLUDED_SHARE_MAX,
    HOLD_GAIN_MIN,
    HOLD_WEEKS_MIN,
    SEED,
    SUB_WINS_MIN,
    TOP_EXCLUDE,
    Config,
)

METHOD = (
    f"circular block · {BLOCK_WEEKS}주 · {DRAWS:,}회 · seed {SEED} · numpy default_rng · "
    "달력 자리 유지(빠진 주 = 빈 자리) · 재표본 평균 = 유효 주 평균 · 2.5/97.5 백분위"
)


def _mean(xs: list[float]) -> Optional[float]:
    return (sum(xs) / len(xs)) if xs else None


def week_rows(
    panel: Panel, weeks: list[dict], variant: str, cost: float, *, shift: bool = False
) -> list[dict[str, Any]]:
    """주마다 경로 수익 · 차이(PLAN §3). shift = D'+1 체결 불가 짝 민감도(판정 외)."""
    ci = panel.ci
    bj = ci[BENCH]
    rows: list[dict[str, Any]] = []
    for w in weeks:
        v = w["variants"][variant]
        e1, e2 = w["e1_pos"], w["e2_pos"]
        row: dict[str, Any] = {
            "D": w["D"],
            "span": w["span"],
            "sub": w["sub"],
            "decision": v["decision"],
            "abstain": v["abstain"],
            "gap_days": w["gap_days"],
            "bench_ret_1m": w["bench_ret_1m"],
            "n_candidates": len(v["candidates"]),
            "excluded": {},
            "excluded_pairs": [],
            "pairs": [],
            "shifted": 0,
        }
        rows.append(row)
        if not v["candidates"]:
            row["status"] = "NO_CANDIDATE"
            continue
        nxt = set(w["next_top"])
        why_b, rb = W.pair(panel, bj, e1, e2)
        if why_b != "OK":
            row["status"] = "BENCH_NOT_EXEC"
            row["excluded"] = {W.BENCH_REASON: len(v["candidates"])}
            continue
        rel: list[float] = []
        for rank, code, _lab in v["candidates"]:
            why, r = W.pair(panel, ci[code], e1, e2)
            if why == "NOT_EXEC_E2" and shift:
                e, r2 = W.shifted_pair(panel, ci[code], e1, e2)
                if e is not None:
                    why, r = "OK", r2
                    row["shifted"] += 1
            if why == "OK":
                rel.append(r)
                row["pairs"].append([rank, code, r, code in nxt])
            else:
                row["excluded"][why] = row["excluded"].get(why, 0) + 1
                row["excluded_pairs"].append([rank, code, why, code in nxt])
        if not rel:
            row["status"] = "ALL_PAIRS_EXCLUDED"
            continue
        g_imm = sum(rel) / len(rel)
        imm = sum(r / (1.0 + cost) - 1.0 for r in rel) / len(rel)
        hold = 1.0 / (1.0 + cost) - 1.0
        is_hold = v["decision"] == W.HOLD
        rule = hold if is_hold else imm
        k = rb / (1.0 + cost) - 1.0
        row.update(
            status="OK",
            imm=imm,
            hold=hold,
            rule=rule,
            K=k,
            g_imm=g_imm,
            g_rule=1.0 if is_hold else g_imm,
            g_K=rb,
            d_rule=rule - imm,
            d_hold=hold - imm,
            d_rule_hold=rule - hold,
            d_rule_K=rule - k,
            d_imm_K=imm - k,
        )
    return rows


def bootstrap(slots: list[Optional[float]]) -> dict[str, Any]:
    """달력 자리(빈 자리 = None)를 유지한 순환 블록 · 재표본 평균 = 그 안 유효 주 평균."""
    x = np.array([np.nan if v is None else float(v) for v in slots], dtype=float)
    valid = np.isfinite(x)
    n, nv = len(x), int(valid.sum())
    out: dict[str, Any] = {"n_slots": n, "n_valid": nv, "method": METHOD}
    if nv == 0:
        return {**out, "mean": None, "lo": None, "hi": None, "draws_used": 0}
    rng = np.random.default_rng(SEED)
    nb = -(-n // BLOCK_WEEKS)
    starts = rng.integers(0, n, size=(DRAWS, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK_WEEKS)[None, None, :]) % n
    samp = x[idx.reshape(DRAWS, -1)[:, :n]]
    fin = np.isfinite(samp)
    cnt = fin.sum(axis=1)
    sums = np.where(fin, samp, 0.0).sum(axis=1)
    keep = cnt > 0
    means = sums[keep] / cnt[keep]
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        **out,
        "mean": float(x[valid].mean()),
        "lo": float(lo),
        "hi": float(hi),
        "draws_used": int(keep.sum()),
    }


def mdd(gross: list[float]) -> float:
    """1주 노출 경로(시작 1 = 첫 고점)의 최대낙폭(≤ 0)."""
    value = peak = 1.0
    worst = 0.0
    for g in gross:
        value *= g
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def _split(hold_ok: list[dict]) -> dict[str, Any]:
    """피한 손실 · 놓친 상승 = 보류 주 (보류 − 즉시) 부호(판정 §4 설계자 의견)."""
    out: dict[str, Any] = {}
    for key, test in (
        ("avoided", lambda d: d > 0),
        ("missed", lambda d: d < 0),
        ("zero", lambda d: d == 0),
    ):
        sel = [r for r in hold_ok if test(r["d_rule"])]
        top = sorted(sel, key=lambda r: (-abs(r["d_rule"]), r["D"]))[:TOP_EXCLUDE]
        out[key] = {
            "weeks": len(sel),
            "mean": _mean([r["d_rule"] for r in sel]),
            "top": [[r["D"], r["d_rule"]] for r in top],
        }
    return out


def summarize(rows: list[dict], cfg: Config, span: str) -> dict[str, Any]:
    rs = [r for r in rows if r["span"] == span]
    ok = [r for r in rs if r["status"] == "OK"]
    hold_ok = [r for r in ok if r["decision"] == W.HOLD]
    status = collections.Counter(r["status"] for r in rs)
    excluded: dict[str, int] = collections.Counter()
    for r in rs:
        excluded.update(r["excluded"])
    pairs = sum(r["n_candidates"] for r in rs)  # 본 구간 후보 짝 전체(PLAN §4 D 분모)
    pairs_ok = sum(len(r["pairs"]) for r in ok)
    subs = []
    for k in range(len(cfg.subs)):
        sel = [r for r in ok if r["sub"] == k]
        subs.append(
            {
                "range": list(cfg.subs[k]),
                "evaluable_weeks": len(sel),
                "hold_weeks": sum(1 for r in sel if r["decision"] == W.HOLD),
                "delta": _mean([r["d_rule"] for r in sel]),
            }
        )
    gap_pairs: collections.Counter = collections.Counter()
    for r in ok:
        gap_pairs[r["gap_days"]] += len(r["pairs"])
    down = [r for r in ok if r["bench_ret_1m"] < 0]
    ranked = sorted(ok, key=lambda r: (-r["d_rule"], r["D"]))
    paths = {
        "immediate": mdd([r["g_imm"] for r in ok]),
        "always_hold": mdd([1.0 for _ in ok]),
        "rule": mdd([r["g_rule"] for r in ok]),
        "kodex200": mdd([r["g_K"] for r in ok]),
    }

    def slots(key: str) -> list[Optional[float]]:
        return [r[key] if r["status"] == "OK" else None for r in rs]

    return {
        "span": span,
        "counts": {
            "weeks": len(rs),
            "status": dict(status),
            "cand_weeks": sum(1 for r in rs if r["n_candidates"]),
            "evaluable_weeks": len(ok),
            "pairs": pairs,
            "pairs_ok": pairs_ok,
            "excluded": dict(excluded),
            "shifted_pairs": sum(r["shifted"] for r in rs),
            "hold_weeks": len(hold_ok),
            "buys": {"immediate": pairs_ok, "always_hold": pairs_ok, "rule": pairs_ok},
            "kodex200_buys": len(ok),
            "gap_days": dict(
                sorted(collections.Counter(r["gap_days"] for r in ok).items())
            ),
            "gap_pairs": dict(sorted(gap_pairs.items())),
            "next_week_dropout_pairs": sum(
                1 for r in ok for p in r["pairs"] if not p[3]
            ),
            "abstain_weeks": sum(1 for r in rs if r.get("abstain")),
            "preopen_unavailable_weeks": 0,
        },
        "delta": bootstrap(slots("d_rule")),
        "rule_minus_hold": bootstrap(slots("d_rule_hold")),
        "hold_minus_immediate": _mean([r["d_hold"] for r in ok]),
        "rule_minus_kodex200": _mean([r["d_rule_K"] for r in ok]),
        "immediate_minus_kodex200": _mean([r["d_imm_K"] for r in ok]),
        "means": {k: _mean([r[k] for r in ok]) for k in ("imm", "hold", "rule", "K")},
        "hold_week_gain": _mean([r["d_rule"] for r in hold_ok]),
        "subs": subs,
        "sub_wins": sum(1 for s in subs if s["delta"] is not None and s["delta"] > 0),
        "downturn": {
            "weeks": len(down),
            "delta": _mean([r["d_rule"] for r in down]),
        },
        "split": _split(hold_ok),
        "mdd": paths,
        "delta_without_top": _mean([r["d_rule"] for r in ranked[TOP_EXCLUDE:]]),
    }


def common_delta(main_rows: list[dict], off_rows: list[dict], span: str) -> dict:
    """§4 ⑦ — 두 분류에서 모두 평가 가능한 같은 주의 Δ."""
    a = {r["D"]: r for r in main_rows if r["span"] == span and r["status"] == "OK"}
    b = {r["D"]: r for r in off_rows if r["span"] == span and r["status"] == "OK"}
    same = sorted(set(a) & set(b))
    return {
        "weeks": len(same),
        "main": _mean([a[d]["d_rule"] for d in same]),
        "official": _mean([b[d]["d_rule"] for d in same]),
        "decisions_differ": sum(
            1 for d in same if a[d]["decision"] != b[d]["decision"]
        ),
    }


def judge(s: dict, cmp7: dict) -> dict[str, Any]:
    """판정 순서 D → C → A → B(PLAN §4 · 위에서 처음 맞는 것 하나)."""
    c = s["counts"]
    pairs_out = c["pairs"] - c["pairs_ok"]
    d_reasons = []
    if c["evaluable_weeks"] < EVAL_SHARE_MIN * c["cand_weeks"]:
        d_reasons.append("평가 가능 주 < 후보 있는 주의 80%")
    if c["pairs"] and pairs_out > EXCLUDED_SHARE_MAX * c["pairs"]:
        d_reasons.append("체결 불가로 빠진 짝 > 후보 짝의 20%")
    delta = s["delta"]["mean"]
    if d_reasons or delta is None:
        return {"status": "D", "reasons": d_reasons or ["평가 가능 주 0"]}
    c_reasons = []
    if not delta > 0:
        c_reasons.append("Δ ≤ 0")
    if s["mdd"]["rule"] < s["mdd"]["immediate"]:
        c_reasons.append("규칙 경로 1주 노출 낙폭 > 즉시 경로(허용 위험 초과)")
    if c_reasons:
        return {"status": "C", "reasons": c_reasons}
    rh = s["rule_minus_hold"]
    hg = s["hold_week_gain"]
    dn = s["downturn"]["delta"]
    conds = {
        "1_ci_lower_gt_0": s["delta"]["lo"] > 0,
        "2_hold_week_gain": hg is not None and hg >= HOLD_GAIN_MIN,
        "3_rule_beats_always_hold": rh["mean"] is not None
        and rh["mean"] > 0
        and rh["lo"] > 0,
        "4_sub_wins": s["sub_wins"] >= SUB_WINS_MIN,
        "5_downturn_ge_0": dn is not None and dn >= 0,
        "6_hold_weeks": c["hold_weeks"] >= HOLD_WEEKS_MIN,
        "7_official_same_sign": cmp7["main"] is not None
        and cmp7["official"] is not None
        and sign(cmp7["main"]) == sign(cmp7["official"]),
    }
    failed = [k for k, ok in conds.items() if not ok]
    if not failed:
        return {"status": "A", "conditions": conds, "failed": []}
    note = None
    if "3_rule_beats_always_hold" in failed:
        note = "보류 효과는 보이나 어느 주를 기다릴지 고른 효과는 미확인"
    return {"status": "B", "conditions": conds, "failed": failed, "note": note}


def worked_case(panel: Panel, weeks: list[dict], rows: list[dict]) -> Optional[dict]:
    """AC1 · AC2 사례(미리 정한 선택: 본 구간 첫 평가 가능 보류 주 · 없으면 첫 평가 가능 주).

    체결된 짝(가격 · 값 · 다음 주 상위 30 잔류)과 빠진 짝(사유 · 다음 주 잔류)을 함께 싣는다.
    """
    by_d = {w["D"]: w for w in weeks}
    main_ok = [r for r in rows if r["span"] == "main" and r["status"] == "OK"]
    pick = next((r for r in main_ok if r["decision"] == W.HOLD), None) or next(
        iter(main_ok), None
    )
    if pick is None:
        return None
    w = by_d[pick["D"]]
    ci = panel.ci
    e1, e2 = w["e1_pos"], w["e2_pos"]
    cands = []
    for rank, code, r, in_next in pick["pairs"]:
        j = ci[code]
        cands.append(
            {
                "rank": rank,
                "code": code,
                "index_name": panel.index_name[j, w["pos"]],
                "p_e": float(panel.O[j, e1]),
                "p_t": float(panel.O[j, e2]),
                "ratio": r,
                "immediate_value": 100.0 / (1.0 + BASE_COST) * r,
                "hold_value": 100.0 / (1.0 + BASE_COST),
                "in_next_top": in_next,
            }
        )
    return {
        "D": w["D"],
        "next": w["next"],
        "window": [w["start"], w["D"]],
        "fills": [w["e1"], w["e2"]],
        "decision": pick["decision"],
        "votes": {k: w["variants"]["MAIN"][k] for k in ("votes", "up", "B")},
        "denominator": w["denominator"],
        "top": w["top"],
        "candidates": cands,
        "excluded": [
            {"rank": a, "code": b, "reason": c, "in_next_top": d}
            for a, b, c, d in pick["excluded_pairs"]
        ],
        "d_rule": pick["d_rule"],
    }


def evaluate(panel: Panel, weeks: list[dict], cfg: Config) -> dict[str, Any]:
    """공식 실행의 모든 계산(쓰기 전). 반환 = report 본문 + 주별 행."""
    main20 = week_rows(panel, weeks, "MAIN", BASE_COST)
    off20 = week_rows(panel, weeks, "OFFICIAL", BASE_COST)
    main40 = week_rows(panel, weeks, "MAIN", ALT_COST)
    shift20 = week_rows(panel, weeks, "MAIN", BASE_COST, shift=True)
    primary = summarize(main20, cfg, "main")
    cmp7 = common_delta(main20, off20, "main")
    result = {
        "primary": primary,
        "official_only": summarize(off20, cfg, "main"),
        "official_compare": cmp7,
        "alt_cost": summarize(main40, cfg, "main"),
        "aux": summarize(main20, cfg, "aux"),
        "shift_sensitivity": summarize(shift20, cfg, "main"),
        "judgment": judge(primary, cmp7),
        "worked_case": worked_case(panel, weeks, main20),
    }
    for key in ("primary", "alt_cost", "aux", "shift_sensitivity"):
        result[key]["delta_sign"] = sign(result[key]["delta"]["mean"])
    return {"result": result, "rows": {"MAIN": main20, "OFFICIAL": off20}}


def sign(x: Optional[float]) -> Optional[int]:
    if x is None:
        return None
    return 1 if x > 0 else (-1 if x < 0 else 0)
