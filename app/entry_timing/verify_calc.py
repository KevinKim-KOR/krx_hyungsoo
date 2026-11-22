"""verify 독립 재계산 — weekly · study · data 를 쓰지 않고 reader 계열 + 원시 행에서 다시 만든다.

```text
뼈대   ISO 주 마지막 거래일 · 다음 신호 · D+1 · D'+1 · 간격 · 구간 · 하위 기간 · 평가 가능 주 목록
주     1개월 시작 · 모집단 · 상위 30 · 세 갈래(classify 사전 · 규칙 = 고정 규칙 자체) · 분모 갈래 · B · 결정 · 다음 주 상위 30
행     O* · 체결 조건 · 짝 사유 · 비율 · 경로 수익 · 차이(20 · 40bp · 옮김 민감도)
결과   summarize · ⑦ · 판정 · 사례를 같은 모양으로(파이썬 반복 · fsum · 같은 seed 블록 시작)
```
분류 규칙(classify)은 고정 규칙 그 자체라 함께 쓴다 — 결과 이름 목록은 잠금의 분류표와 따로 대조한다.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import math
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Optional

import numpy as np

from app import krx_sealed_reader as K
from app.entry_timing import classify as CL
from app.entry_timing import protocol as P

_TOKENS = ("인버스", "레버리지", "2배", "합성", "선물")
_KEYS = ("TDD_OPNPRC", "TDD_HGPRC", "TDD_LWPRC", "TDD_CLSPRC", "ACC_TRDVOL")


def _num(v: Any) -> Optional[float]:
    t = "" if v is None else str(v).replace(",", "").strip()
    try:
        return float(t) if t else None
    except ValueError:
        return None


def _mean(xs: list[float]) -> Optional[float]:
    return (math.fsum(xs) / len(xs)) if xs else None


def _excluded_name(name: str) -> bool:
    return bool(name) and (any(t in name for t in _TOKENS) or "2X" in name.upper())


def _sign(x: Optional[float]) -> Optional[int]:
    return None if x is None else (1 if x > 0 else (-1 if x < 0 else 0))


class Source:
    """reader 계열 + 원시 행(이 모듈이 따로 읽는다)."""

    def __init__(self, cfg: P.Config):
        self.p = K.load_panel(cfg.db, version_id=cfg.version)
        self.axis = self.p.dates
        self.pos = {d: i for i, d in enumerate(self.axis)}
        self.raw: dict[tuple[str, str], tuple] = {}
        con = sqlite3.connect(K.readonly_uri(Path(cfg.db)), uri=True)
        try:
            for bas_dd, code, text in con.execute(
                "SELECT m.bas_dd, d.isu_cd, d.row_json FROM krx_dataset_member m "
                "JOIN krx_etf_daily_raw d ON d.response_id = m.response_id "
                "WHERE m.version_id = ?",
                (cfg.version,),
            ):
                row = json.loads(text)
                d = f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:]}"
                self.raw[(code, d)] = tuple(_num(row.get(k)) for k in _KEYS) + (
                    (row.get("IDX_IND_NM") or "").strip(),
                )
        finally:
            con.close()
        self.last = {
            c
            for c, s in self.p.series.items()
            if s.index.get(self.axis[-1]) is not None
        }

    def row(self, code: str, d: str) -> Optional[int]:
        s = self.p.series.get(code)
        return None if s is None else s.index.get(d)

    def chain(self, code: str, d: str) -> Optional[float]:
        r = self.row(code, d)
        return None if r is None else self.p.series[code].chain[r]

    def seg(self, code: str, d: str) -> Optional[int]:
        r = self.row(code, d)
        return None if r is None else self.p.series[code].segment[r]

    def o_star_exec(self, code: str, d: str) -> tuple[Optional[float], bool]:
        r = self.row(code, d)
        if r is None:
            return None, False
        s = self.p.series[code]
        o, h, lo, c, v, _ = self.raw[(code, d)]
        ch = s.chain[r]
        if ch is None or s.close_status[r] != K.CLOSE_OK:
            return None, False
        ostar = None if o is None else o * (ch / c)
        ok = (
            v is not None
            and v > 0
            and o is not None
            and o > 0
            and h is not None
            and lo is not None
            and h >= max(o, c)
            and 0 < lo <= min(o, c)
            and s.relation_ok[r]
        )
        return ostar, bool(ok)

    def pair(self, code: str, d1: str, d2: str) -> tuple[str, Optional[float]]:
        o1, x1 = self.o_star_exec(code, d1)
        if not x1:
            return "NOT_EXEC_E1", None
        if self.row(code, d2) is None:
            return "NO_ROW_E2", None
        if self.seg(code, d2) != self.seg(code, d1):
            return "SEG_BREAK", None
        o2, x2 = self.o_star_exec(code, d2)
        return ("OK", o2 / o1) if x2 else ("NOT_EXEC_E2", None)

    def shifted(
        self, code: str, d1: str, d2: str
    ) -> tuple[Optional[str], Optional[float]]:
        i2 = self.pos[d2]
        for i in range(i2 + 1, min(i2 + P.SHIFT_MAX, len(self.axis) - 1) + 1):
            d = self.axis[i]
            if self.row(code, d) is None or self.seg(code, d) != self.seg(code, d1):
                return None, None
            o, x = self.o_star_exec(code, d)
            if x:
                return d, o / self.o_star_exec(code, d1)[0]
        return None, None

    def population(self, d: str, start: str, dictionary: dict) -> list[tuple]:
        pop = []
        for code, s in self.p.series.items():
            ri, rs = s.index.get(d), s.index.get(start)
            if ri is None or rs is None or s.chain[ri] is None or s.chain[rs] is None:
                continue
            if s.segment[ri] != s.segment[rs] or _excluded_name(s.name[ri]):
                continue
            idx = self.raw[(code, d)][5]
            lab, why = CL.label(idx, dictionary)
            ret = s.chain[ri] / s.chain[rs] - 1.0
            pop.append((-ret, code, idx, lab, why, ret))
        pop.sort(key=lambda t: (t[0], t[1]))
        return pop


def _start(axis: list[str], d: str) -> Optional[str]:
    target = (dt.date.fromisoformat(d) - dt.timedelta(days=P.LOOKBACK_DAYS)).isoformat()
    if target < axis[0]:
        return None
    return next(x for x in axis if x >= target)


def _in(d: str, ranges: dict) -> Optional[str]:
    return next((k for k, (lo, hi) in ranges.items() if lo <= d <= hi), None)


def skeleton(src: Source, cfg: P.Config) -> list[dict]:
    """평가 가능 주의 뼈대(기록과 따로 만든다)."""
    ax = src.axis

    def wk(d: str) -> tuple:
        return dt.date.fromisoformat(d).isocalendar()[:2]

    sig = [i for i in range(len(ax) - 1) if wk(ax[i]) != wk(ax[i + 1])]
    out = []
    for i, i2 in zip(sig, sig[1:]):
        if i2 + 1 >= len(ax):
            continue
        span = _in(ax[i], cfg.spans)
        start = _start(ax, ax[i])
        if span is None or start is None:
            continue
        sub = None
        if span == "main":
            sub = next(
                (k for k, (lo, hi) in enumerate(cfg.subs) if lo <= ax[i] <= hi), None
            )
        out.append(
            {
                "pos": i,
                "D": ax[i],
                "span": span,
                "sub": sub,
                "start": start,
                "next": ax[i2],
                "e1": ax[i + 1],
                "e2": ax[i2 + 1],
                "e1_pos": i + 1,
                "e2_pos": i2 + 1,
                "gap_days": i2 - i,
            }
        )
    return out


def week(src: Source, sk: dict, dictionary: dict, next_start: Optional[str]) -> dict:
    """한 주 기록 전체(weekly.build 와 같은 칸)."""
    d = sk["D"]
    pop = src.population(d, sk["start"], dictionary)
    top = pop[: P.TOP_N]
    den: dict[str, dict] = {CL.OFF_DE: {}, CL.EST_DE: {}, CL.UNKNOWN: {}}
    for t in pop:
        if t[3] in den and "선물" not in t[2]:
            den[t[3]][t[2]] = t[4]
    variants = {}
    for v in P.VARIANTS:
        groups: dict[str, list[float]] = {}
        for t in pop:
            if CL.is_domestic_equity(t[3], v) and "선물" not in t[2]:
                groups.setdefault(t[2], []).append(t[5])
        n = len(groups)
        up = sum(1 for g in groups.values() if statistics.median(g) > 0)
        b = (up / n) if n else None
        abstain = n < P.MIN_VOTES
        variants[v] = {
            "candidates": [
                [r + 1, t[1], t[3]]
                for r, t in enumerate(top)
                if CL.is_domestic_equity(t[3], v)
            ],
            "votes": n,
            "up": up,
            "B": b,
            "abstain": abstain,
            "decision": "IMMEDIATE" if (abstain or b >= P.THRESHOLD) else "HOLD",
        }
    nxt = (
        [] if next_start is None else src.population(sk["next"], next_start, dictionary)
    )
    return {
        **sk,
        "bench_ret_1m": src.chain(P.BENCH, d) / src.chain(P.BENCH, sk["start"]) - 1.0,
        "population": len(pop),
        "top": [[r + 1, t[1], t[3], t[4], t[2]] for r, t in enumerate(top)],
        "unknown_top": [
            [r + 1, t[1], t[1] not in src.last]
            for r, t in enumerate(top)
            if t[3] == CL.UNKNOWN
        ],
        "denominator": {
            "official": len(den[CL.OFF_DE]),
            "estimated": len(den[CL.EST_DE]),
            "unknown": len(den[CL.UNKNOWN]),
            "unknown_reasons": dict(
                sorted(collections.Counter(den[CL.UNKNOWN].values()).items())
            ),
        },
        "next_top": [t[1] for t in nxt[: P.TOP_N]],
        "variants": variants,
    }


def weeks(src: Source, cfg: P.Config, dictionary: dict) -> list[dict]:
    return [
        week(src, sk, dictionary, _start(src.axis, sk["next"]))
        for sk in skeleton(src, cfg)
    ]


def rows(
    src: Source, wks: list[dict], v: str, cost: float, shift: bool = False
) -> list[dict]:
    out = []
    for w in wks:
        x = w["variants"][v]
        r: dict[str, Any] = {
            "D": w["D"],
            "span": w["span"],
            "sub": w["sub"],
            "decision": x["decision"],
            "abstain": x["abstain"],
            "gap_days": w["gap_days"],
            "bench_ret_1m": w["bench_ret_1m"],
            "n_candidates": len(x["candidates"]),
            "excluded": {},
            "excluded_pairs": [],
            "pairs": [],
            "shifted": 0,
        }
        out.append(r)
        if not x["candidates"]:
            r["status"] = "NO_CANDIDATE"
            continue
        wb, rb = src.pair(P.BENCH, w["e1"], w["e2"])
        if wb != "OK":
            r["status"] = "BENCH_NOT_EXEC"
            r["excluded"] = {"BENCH_NOT_EXEC": len(x["candidates"])}
            continue
        nxt = set(w["next_top"])
        rel = []
        for rank, code, _lab in x["candidates"]:
            why, ratio = src.pair(code, w["e1"], w["e2"])
            if why == "NOT_EXEC_E2" and shift:
                d, q = src.shifted(code, w["e1"], w["e2"])
                if d is not None:
                    why, ratio = "OK", q
                    r["shifted"] += 1
            if why == "OK":
                rel.append(ratio)
                r["pairs"].append([rank, code, ratio, code in nxt])
            else:
                r["excluded"][why] = r["excluded"].get(why, 0) + 1
                r["excluded_pairs"].append([rank, code, why, code in nxt])
        if not rel:
            r["status"] = "ALL_PAIRS_EXCLUDED"
            continue
        imm = math.fsum(q / (1 + cost) - 1 for q in rel) / len(rel)
        hold = 1 / (1 + cost) - 1
        rule = hold if x["decision"] == "HOLD" else imm
        kk = rb / (1 + cost) - 1
        g = math.fsum(rel) / len(rel)
        r.update(
            status="OK",
            imm=imm,
            hold=hold,
            rule=rule,
            K=kk,
            g_imm=g,
            g_rule=1.0 if x["decision"] == "HOLD" else g,
            g_K=rb,
            d_rule=rule - imm,
            d_hold=hold - imm,
            d_rule_hold=rule - hold,
            d_rule_K=rule - kk,
            d_imm_K=imm - kk,
        )
    return out


def bootstrap(vals: list[Optional[float]], method: str) -> dict:
    n = len(vals)
    good = [x for x in vals if x is not None]
    base = {"n_slots": n, "n_valid": len(good), "method": method}
    if not good:
        return {**base, "mean": None, "lo": None, "hi": None, "draws_used": 0}
    nb = -(-n // P.BLOCK_WEEKS)
    starts = np.random.default_rng(P.SEED).integers(0, n, size=(P.DRAWS, nb))
    means = []
    for row in starts:
        picked = [vals[(int(b) + t) % n] for b in row for t in range(P.BLOCK_WEEKS)][:n]
        ok = [x for x in picked if x is not None]
        if ok:
            means.append(math.fsum(ok) / len(ok))
    lo, hi = np.percentile(np.array(means), [2.5, 97.5])
    return {
        **base,
        "mean": math.fsum(good) / len(good),
        "lo": float(lo),
        "hi": float(hi),
        "draws_used": len(means),
    }


def _mdd(gs: list[float]) -> float:
    v = p = 1.0
    w = 0.0
    for g in gs:
        v *= g
        p = v if v > p else p
        w = min(w, v / p - 1)
    return w


def summary(rs_all: list[dict], cfg: P.Config, span: str, method: str) -> dict:
    rs = [r for r in rs_all if r["span"] == span]
    ok = [r for r in rs if r["status"] == "OK"]
    hold = [r for r in ok if r["decision"] == "HOLD"]
    excluded: collections.Counter = collections.Counter()
    gap_pairs: collections.Counter = collections.Counter()
    for r in rs:
        excluded.update(r["excluded"])
    for r in ok:
        gap_pairs[r["gap_days"]] += len(r["pairs"])
    subs = []
    for k, rng in enumerate(cfg.subs):
        sel = [r for r in ok if r["sub"] == k]
        subs.append(
            {
                "range": list(rng),
                "evaluable_weeks": len(sel),
                "hold_weeks": sum(1 for r in sel if r["decision"] == "HOLD"),
                "delta": _mean([r["d_rule"] for r in sel]),
            }
        )
    split = {}
    for key, test in (("avoided", 1), ("missed", -1), ("zero", 0)):
        sel = [r for r in hold if _sign(r["d_rule"]) == test]
        top = sorted(sel, key=lambda r: (-abs(r["d_rule"]), r["D"]))[: P.TOP_EXCLUDE]
        split[key] = {
            "weeks": len(sel),
            "mean": _mean([r["d_rule"] for r in sel]),
            "top": [[r["D"], r["d_rule"]] for r in top],
        }
    ranked = sorted(ok, key=lambda r: (-r["d_rule"], r["D"]))
    n_top = P.TOP_EXCLUDE
    down = [r["d_rule"] for r in ok if r["bench_ret_1m"] < 0]
    pairs_ok = sum(len(r["pairs"]) for r in ok)
    return {
        "span": span,
        "counts": {
            "weeks": len(rs),
            "status": dict(collections.Counter(r["status"] for r in rs)),
            "cand_weeks": sum(1 for r in rs if r["n_candidates"]),
            "evaluable_weeks": len(ok),
            "pairs": sum(r["n_candidates"] for r in rs),
            "pairs_ok": pairs_ok,
            "excluded": dict(excluded),
            "shifted_pairs": sum(r["shifted"] for r in rs),
            "hold_weeks": len(hold),
            "buys": {"immediate": pairs_ok, "always_hold": pairs_ok, "rule": pairs_ok},
            "kodex200_buys": len(ok),
            "gap_days": dict(
                sorted(collections.Counter(r["gap_days"] for r in ok).items())
            ),
            "gap_pairs": dict(sorted(gap_pairs.items())),
            "next_week_dropout_pairs": sum(
                1 for r in ok for p in r["pairs"] if not p[3]
            ),
            "abstain_weeks": sum(1 for r in rs if r["abstain"]),
            "preopen_unavailable_weeks": 0,
        },
        "delta": bootstrap(
            [r["d_rule"] if r["status"] == "OK" else None for r in rs], method
        ),
        "rule_minus_hold": bootstrap(
            [r["d_rule_hold"] if r["status"] == "OK" else None for r in rs], method
        ),
        "hold_minus_immediate": _mean([r["d_hold"] for r in ok]),
        "rule_minus_kodex200": _mean([r["d_rule_K"] for r in ok]),
        "immediate_minus_kodex200": _mean([r["d_imm_K"] for r in ok]),
        "means": {k: _mean([r[k] for r in ok]) for k in ("imm", "hold", "rule", "K")},
        "hold_week_gain": _mean([r["d_rule"] for r in hold]),
        "subs": subs,
        "sub_wins": sum(1 for s in subs if s["delta"] is not None and s["delta"] > 0),
        "downturn": {"weeks": len(down), "delta": _mean(down)},
        "split": split,
        "mdd": {
            "immediate": _mdd([r["g_imm"] for r in ok]),
            "always_hold": _mdd([1.0] * len(ok)),
            "rule": _mdd([r["g_rule"] for r in ok]),
            "kodex200": _mdd([r["g_K"] for r in ok]),
        },
        "delta_without_top": _mean([r["d_rule"] for r in ranked[n_top:]]),
        "delta_sign": None,
    }


def judge(s: dict, c7: dict) -> dict:
    c = s["counts"]
    d_r = []
    if c["evaluable_weeks"] < P.EVAL_SHARE_MIN * c["cand_weeks"]:
        d_r.append("평가 가능 주 < 후보 있는 주의 80%")
    if c["pairs"] and (c["pairs"] - c["pairs_ok"]) > P.EXCLUDED_SHARE_MAX * c["pairs"]:
        d_r.append("체결 불가로 빠진 짝 > 후보 짝의 20%")
    mean = s["delta"]["mean"]
    if d_r or mean is None:
        return {"status": "D", "reasons": d_r or ["평가 가능 주 0"]}
    c_r = []
    if mean <= 0:
        c_r.append("Δ ≤ 0")
    if s["mdd"]["rule"] < s["mdd"]["immediate"]:
        c_r.append("규칙 경로 1주 노출 낙폭 > 즉시 경로(허용 위험 초과)")
    if c_r:
        return {"status": "C", "reasons": c_r}
    rh, hg, dn = s["rule_minus_hold"], s["hold_week_gain"], s["downturn"]["delta"]
    conds = {
        "1_ci_lower_gt_0": s["delta"]["lo"] > 0,
        "2_hold_week_gain": hg is not None and hg >= P.HOLD_GAIN_MIN,
        "3_rule_beats_always_hold": rh["mean"] is not None
        and rh["mean"] > 0
        and rh["lo"] > 0,
        "4_sub_wins": s["sub_wins"] >= P.SUB_WINS_MIN,
        "5_downturn_ge_0": dn is not None and dn >= 0,
        "6_hold_weeks": c["hold_weeks"] >= P.HOLD_WEEKS_MIN,
        "7_official_same_sign": c7["main"] is not None
        and c7["official"] is not None
        and _sign(c7["main"]) == _sign(c7["official"]),
    }
    failed = [k for k, v in conds.items() if not v]
    if not failed:
        return {"status": "A", "conditions": conds, "failed": []}
    note = (
        "보류 효과는 보이나 어느 주를 기다릴지 고른 효과는 미확인"
        if "3_rule_beats_always_hold" in failed
        else None
    )
    return {"status": "B", "conditions": conds, "failed": failed, "note": note}


def worked(src: Source, wks: list[dict], rs: list[dict]) -> Optional[dict]:
    ok = [r for r in rs if r["span"] == "main" and r["status"] == "OK"]
    pick = next((r for r in ok if r["decision"] == "HOLD"), None) or (
        ok[0] if ok else None
    )
    if pick is None:
        return None
    w = next(x for x in wks if x["D"] == pick["D"])
    cands = []
    for rank, code, ratio, in_next in pick["pairs"]:
        cands.append(
            {
                "rank": rank,
                "code": code,
                "index_name": src.raw[(code, w["D"])][5],
                "p_e": src.o_star_exec(code, w["e1"])[0],
                "p_t": src.o_star_exec(code, w["e2"])[0],
                "ratio": ratio,
                "immediate_value": 100.0 / (1.0 + P.BASE_COST) * ratio,
                "hold_value": 100.0 / (1.0 + P.BASE_COST),
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


def evaluate(
    src: Source, wks: list[dict], cfg: P.Config, method: str
) -> tuple[dict, dict]:
    m20 = rows(src, wks, "MAIN", P.BASE_COST)
    o20 = rows(src, wks, "OFFICIAL", P.BASE_COST)
    m40 = rows(src, wks, "MAIN", P.ALT_COST)
    sh = rows(src, wks, "MAIN", P.BASE_COST, shift=True)
    a = {r["D"]: r for r in m20 if r["span"] == "main" and r["status"] == "OK"}
    b = {r["D"]: r for r in o20 if r["span"] == "main" and r["status"] == "OK"}
    same = sorted(set(a) & set(b))
    c7 = {
        "weeks": len(same),
        "main": _mean([a[d]["d_rule"] for d in same]),
        "official": _mean([b[d]["d_rule"] for d in same]),
        "decisions_differ": sum(
            1 for d in same if a[d]["decision"] != b[d]["decision"]
        ),
    }
    res = {
        "primary": summary(m20, cfg, "main", method),
        "official_only": summary(o20, cfg, "main", method),
        "official_compare": c7,
        "alt_cost": summary(m40, cfg, "main", method),
        "aux": summary(m20, cfg, "aux", method),
        "shift_sensitivity": summary(sh, cfg, "main", method),
    }
    res["judgment"] = judge(res["primary"], c7)
    res["worked_case"] = worked(src, wks, m20)
    for k in ("primary", "alt_cost", "aux", "shift_sensitivity"):
        res[k]["delta_sign"] = _sign(res[k]["delta"]["mean"])
    res["official_only"].pop("delta_sign")
    return res, {"MAIN": m20, "OFFICIAL": o20, "SHIFT": sh}
