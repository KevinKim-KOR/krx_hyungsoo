"""신호 주 · 운영 1개월 상위 30 복원 · 국내 주식형 후보 · 상승 확산 분모 · 결정 · 짝 — PLAN §1 · §2 · §3.

```text
신호    ISO 주 마지막 거래일 D · 다음 신호 D' · 즉시 매수 = D+1 · 보류 매수 = 평가 = D'+1(축 안에 있어야 함)
복원    1개월 = window_start ~ D · 두 끝에 행 · 같은 연결 구간 · 그날 이름 4종 제외 → (−수익률, 코드) 정렬 → 상위 30
후보    상위 30 가운데 변형별 국내 주식형(MAIN = 공식 + 추정 · OFFICIAL = 공식만) · 원래 순위 보존
확산    변형별 국내 주식형 · 같은 1개월 · 지수명에 '선물' 없음 → 지수명 하나 = 한 표(대표 = ETF 수익률 중앙값)
        B = (대표 > 0 인 지수) ÷ 지수 수 · B ≥ 0.5 → 즉시 · B < 0.5 → 보류 · 지수 < 30 → 즉시(규칙 없음)
        분모 갈래 = 공식 일치 · 명칭 추정 · 미확인(빼고 사유별로 셈)
짝      D+1 · D'+1 체결 가능 · 같은 연결 구간 — 아니면 사유를 남기고 뺀다(다음 날로 미루지 않음)
다음 주  D' 의 상위 30(원래 후보가 사라져도 비교에 남김 · 탈락 수를 세는 데만 씀)
```
D 뒤 가격은 짝의 체결 가능 여부와 시가 비율에만 쓰고, 그 비율은 study 가 쓴다(여기서는 계산만 · 판정 없음).
"""

from __future__ import annotations

import collections
import statistics
from typing import Any, Optional

import numpy as np

from app.entry_timing import classify as CL
from app.entry_timing.data import Panel, weekly_signals, window_start
from app.entry_timing.protocol import (
    BENCH,
    LOOKBACK_DAYS,
    MIN_VOTES,
    SHIFT_MAX,
    THRESHOLD,
    TOP_N,
    VARIANTS,
    Config,
)

IMMEDIATE, HOLD = "IMMEDIATE", "HOLD"
PAIR_REASONS = ("NOT_EXEC_E1", "NO_ROW_E2", "SEG_BREAK", "NOT_EXEC_E2")
BENCH_REASON = "BENCH_NOT_EXEC"


def name_excluded(name: Optional[str]) -> bool:
    """운영 `classify_etf_tags` 와 같은 낱말(인버스 · 레버리지 · 2X · 2배 · 합성 · 선물)."""
    if not name:
        return False
    upper = name.upper()
    return (
        "인버스" in name
        or "레버리지" in name
        or "2X" in upper
        or "2배" in name
        or "합성" in name
        or "선물" in name
    )


def span_of(date: str, spans: dict) -> Optional[str]:
    for key, (lo, hi) in spans.items():
        if lo <= date <= hi:
            return key
    return None


def sub_of(date: str, subs: tuple) -> Optional[int]:
    for k, (lo, hi) in enumerate(subs):
        if lo <= date <= hi:
            return k
    return None


def classification_table(panel: Panel, dictionary: dict) -> dict[str, list[str]]:
    """봉인 판 전체(모든 날짜)의 그날 지수명 가운데 기본정보에 없는 이름 → [갈래, 사유] (PLAN §2-1 ⑦)."""
    names = {x for x in panel.index_name.ravel().tolist() if x}
    return {
        n: list(CL.label(n, dictionary)) for n in sorted(names) if n not in dictionary
    }


def table_counts(table: dict[str, list[str]]) -> dict[str, int]:
    c = collections.Counter(lab for lab, _ in table.values())
    r = collections.Counter(why for lab, why in table.values() if lab == CL.UNKNOWN)
    return {
        "names_not_in_dictionary": len(table),
        CL.EST_DE: c[CL.EST_DE],
        CL.EST_NOT: c[CL.EST_NOT],
        CL.UNKNOWN: c[CL.UNKNOWN],
        "unknown_provider": r[CL.REASON["provider"]],
        "unknown_conflict": r[CL.REASON["conflict"]],
    }


def _population(
    panel: Panel, i: int, s: int, dictionary: dict, cache: dict
) -> list[tuple]:
    """(−수익률, 코드, 행, 지수명, 갈래, 수익률, 사유) — (−수익률, 코드) 정렬."""
    ok = (
        panel.has_row[:, i]
        & panel.has_row[:, s]
        & (panel.seg[:, i] == panel.seg[:, s])
        & np.isfinite(panel.I[:, i])
        & np.isfinite(panel.I[:, s])
    )
    pop = []
    for j in np.nonzero(ok)[0].tolist():
        if name_excluded(panel.name[j, i]):
            continue
        idx = panel.index_name[j, i]
        if idx not in cache:
            cache[idx] = CL.label(idx, dictionary)
        lab, why = cache[idx]
        ret = float(panel.I[j, i] / panel.I[j, s] - 1.0)
        pop.append((-ret, panel.codes[j], j, idx, lab, ret, why))
    pop.sort(key=lambda t: (t[0], t[1]))
    return pop


def denominator(pop: list[tuple]) -> dict[str, Any]:
    """분모 갈래(선물 지수 제외 · 지수명 하나 = 한 표) — 공식 일치 · 명칭 추정 · 미확인(사유별)."""
    names: dict[str, dict] = {CL.OFF_DE: {}, CL.EST_DE: {}, CL.UNKNOWN: {}}
    for t in pop:
        if t[4] in names and "선물" not in t[3]:
            names[t[4]][t[3]] = t[6]
    return {
        "official": len(names[CL.OFF_DE]),
        "estimated": len(names[CL.EST_DE]),
        "unknown": len(names[CL.UNKNOWN]),
        "unknown_reasons": dict(
            sorted(collections.Counter(names[CL.UNKNOWN].values()).items())
        ),
    }


def _votes(pop: list[tuple], variant: str) -> dict[str, Any]:
    groups: dict[str, list[float]] = {}
    for t in pop:
        idx, lab, ret = t[3], t[4], t[5]
        if CL.is_domestic_equity(lab, variant) and "선물" not in idx:
            groups.setdefault(idx, []).append(ret)
    n = len(groups)
    up = sum(1 for v in groups.values() if statistics.median(v) > 0)
    b = (up / n) if n else None
    abstain = n < MIN_VOTES
    decision = IMMEDIATE if (abstain or b >= THRESHOLD) else HOLD
    return {"votes": n, "up": up, "B": b, "abstain": abstain, "decision": decision}


def build(panel: Panel, dictionary: dict, cfg: Config) -> list[dict[str, Any]]:
    """평가 가능한 신호 주 기록(날짜 순). 성과 · 판정 없음."""
    axis, m = panel.axis, len(panel.axis)
    sig = weekly_signals(axis)
    bj = panel.ci[BENCH]
    last_codes = set(np.nonzero(panel.has_row[:, m - 1])[0].tolist())
    cache: dict[str, tuple[str, str]] = {}
    pops: dict[int, Optional[tuple]] = {}

    def get(i: int) -> Optional[tuple]:
        if i not in pops:
            s = window_start(axis, i, LOOKBACK_DAYS)
            pops[i] = (
                None if s is None else (s, _population(panel, i, s, dictionary, cache))
            )
        return pops[i]

    out: list[dict[str, Any]] = []
    for k, i in enumerate(sig[:-1]):
        i2 = sig[k + 1]
        if i2 + 1 >= m:
            continue
        d = axis[i]
        span = span_of(d, cfg.spans)
        got = get(i) if span is not None else None
        if got is None:
            pops.pop(i, None)
            continue
        s, pop = got
        nxt = get(i2)
        top = pop[:TOP_N]
        variants = {}
        for v in VARIANTS:
            cand = [
                [r + 1, t[1], t[4]]
                for r, t in enumerate(top)
                if CL.is_domestic_equity(t[4], v)
            ]
            variants[v] = {"candidates": cand, **_votes(pop, v)}
        out.append(
            {
                "pos": i,
                "D": d,
                "span": span,
                "sub": sub_of(d, cfg.subs) if span == "main" else None,
                "start": axis[s],
                "next": axis[i2],
                "e1": axis[i + 1],
                "e2": axis[i2 + 1],
                "e1_pos": i + 1,
                "e2_pos": i2 + 1,
                "gap_days": i2 - i,
                "bench_ret_1m": float(panel.I[bj, i] / panel.I[bj, s] - 1.0),
                "population": len(pop),
                "top": [[r + 1, t[1], t[4], t[6], t[3]] for r, t in enumerate(top)],
                "unknown_top": [
                    [r + 1, t[1], t[2] not in last_codes]
                    for r, t in enumerate(top)
                    if t[4] == CL.UNKNOWN
                ],
                "denominator": denominator(pop),
                "next_top": [] if nxt is None else [t[1] for t in nxt[1][:TOP_N]],
                "variants": variants,
            }
        )
        pops.pop(i, None)
    return out


def pair(panel: Panel, j: int, e1: int, e2: int) -> tuple[str, Optional[float]]:
    """(사유, P_T ÷ P_E). 사유 순서 고정 — 체결 가능 · 같은 구간일 때만 비율."""
    if not (panel.has_row[j, e1] and panel.exec_ok[j, e1]):
        return "NOT_EXEC_E1", None
    if not panel.has_row[j, e2]:
        return "NO_ROW_E2", None
    if panel.seg[j, e2] != panel.seg[j, e1]:
        return "SEG_BREAK", None
    if not panel.exec_ok[j, e2]:
        return "NOT_EXEC_E2", None
    return "OK", float(panel.O[j, e2] / panel.O[j, e1])


def shifted_pair(
    panel: Panel, j: int, e1: int, e2: int
) -> tuple[Optional[int], Optional[float]]:
    """민감도(PLAN §3): D'+1 체결 불가 짝만 — 그다음 첫 체결 가능 시가(최대 5거래일 뒤 · 같은 구간)."""
    last = min(e2 + SHIFT_MAX, len(panel.axis) - 1)
    for e in range(e2 + 1, last + 1):
        if not panel.has_row[j, e] or panel.seg[j, e] != panel.seg[j, e1]:
            return None, None
        if panel.exec_ok[j, e]:
            return e, float(panel.O[j, e] / panel.O[j, e1])
    return None, None


def counts(panel: Panel, weeks: list[dict], spans: dict) -> dict[str, dict]:
    """잠금 분모(PLAN §1-4 칸 + 분모 갈래 + 체결 가능 짝 · 평가 가능 주). 수익률 · 판정 없음."""
    ci = panel.ci
    out: dict[str, dict] = {}
    for span in spans:
        ws = [w for w in weeks if w["span"] == span]
        if not ws:
            out[span] = {"weeks": 0}
            continue
        main = [w["variants"]["MAIN"] for w in ws]
        off = [w["variants"]["OFFICIAL"] for w in ws]
        den = [w["denominator"] for w in ws]
        reasons_weeks: collections.Counter = collections.Counter()
        for x in den:
            reasons_weeks.update(x["unknown_reasons"])
        c: dict[str, Any] = {
            "weeks": len(ws),
            "first": ws[0]["D"],
            "last": ws[-1]["D"],
            "cand_weeks": sum(1 for v in main if v["candidates"]),
            "cand_weeks_official": sum(1 for v in off if v["candidates"]),
            "est_cand_weeks": sum(
                1 for v in main if any(x[2] == CL.EST_DE for x in v["candidates"])
            ),
            "pairs_official": sum(
                1 for v in main for x in v["candidates"] if x[2] == CL.OFF_DE
            ),
            "pairs_estimated": sum(
                1 for v in main for x in v["candidates"] if x[2] == CL.EST_DE
            ),
            "unknown_rows": sum(len(w["unknown_top"]) for w in ws),
            "unknown_rows_delisted": sum(
                1 for w in ws for x in w["unknown_top"] if x[2]
            ),
            "votes_min": min(v["votes"] for v in main),
            "votes_official_min": min(v["votes"] for v in off),
            "votes_median": statistics.median(v["votes"] for v in main),
            "votes_official_median": statistics.median(x["official"] for x in den),
            "votes_estimated_median": statistics.median(x["estimated"] for x in den),
            "votes_estimated_max": max(x["estimated"] for x in den),
            "votes_unknown_median": statistics.median(x["unknown"] for x in den),
            "votes_unknown_max": max(x["unknown"] for x in den),
            "unknown_reason_name_weeks": dict(sorted(reasons_weeks.items())),
            "preopen_unavailable_weeks": 0,  # 과거 실제 수신 시각 기록 없음(판정 §2) — 확인된 날 0
        }
        for var in VARIANTS:
            reasons = {r: 0 for r in (*PAIR_REASONS, BENCH_REASON)}
            ok_pairs = evaluable = bench_out = dropouts = 0
            for w in ws:
                cand = w["variants"][var]["candidates"]
                if not cand:
                    continue
                dropouts += sum(1 for x in cand if x[1] not in set(w["next_top"]))
                if pair(panel, ci[BENCH], w["e1_pos"], w["e2_pos"])[0] != "OK":
                    bench_out += 1
                    reasons[BENCH_REASON] += len(cand)
                    continue
                n_ok = 0
                for _rank, code, _lab in cand:
                    why, _ = pair(panel, ci[code], w["e1_pos"], w["e2_pos"])
                    if why == "OK":
                        n_ok += 1
                    else:
                        reasons[why] += 1
                ok_pairs += n_ok
                evaluable += 1 if n_ok else 0
            c[var] = {
                "pairs": sum(len(w["variants"][var]["candidates"]) for w in ws),
                "pairs_ok": ok_pairs,
                "excluded": reasons,
                "bench_excluded_weeks": bench_out,
                "evaluable_weeks": evaluable,
                "abstain_weeks": sum(1 for w in ws if w["variants"][var]["abstain"]),
                "next_week_dropout_pairs": dropouts,
            }
        out[span] = c
    return out
