"""verify 독립 재계산(2) — 잠금 분모 · 주별 기록을 weekly.counts · report.week_records 를 쓰지 않고 다시 만든다.

검증자 r1 F1(잠금 분모 · 기록이 재계산과 이어지지 않음) · F2(주별 분모 갈래 누락)를 막는다. 바탕 = verify_calc 의
Source(reader 계열 + 원시 행)와 다시 만든 주 기록 · 경로 행. 칸 이름 · 모양은 잠금 · 저장 파일과 같다.
"""

from __future__ import annotations

import collections
import statistics
from typing import Any

from app.entry_timing import classify as CL
from app.entry_timing import protocol as P
from app.entry_timing.verify_calc import Source

_REASONS = ("NOT_EXEC_E1", "NO_ROW_E2", "SEG_BREAK", "NOT_EXEC_E2", "BENCH_NOT_EXEC")
_RESULT_KEYS = (
    "status",
    "excluded",
    "pairs",
    "shifted",
    "imm",
    "hold",
    "rule",
    "K",
    "d_rule",
    "d_hold",
    "d_rule_hold",
)
RECORD_KIND = "뒤에 복원한 목록(봉인 KRX · 그날 이름 · 그날 지수명)"


def _variant_counts(src: Source, ws: list[dict], v: str) -> dict[str, Any]:
    reasons = {r: 0 for r in _REASONS}
    ok_pairs = evaluable = bench_out = dropouts = 0
    for w in ws:
        cand = w["variants"][v]["candidates"]
        if not cand:
            continue
        nxt = set(w["next_top"])
        dropouts += sum(1 for _r, code, _l in cand if code not in nxt)
        if src.pair(P.BENCH, w["e1"], w["e2"])[0] != "OK":
            bench_out += 1
            reasons["BENCH_NOT_EXEC"] += len(cand)
            continue
        n_ok = 0
        for _r, code, _l in cand:
            why = src.pair(code, w["e1"], w["e2"])[0]
            if why == "OK":
                n_ok += 1
            else:
                reasons[why] += 1
        ok_pairs += n_ok
        if n_ok:
            evaluable += 1
    return {
        "pairs": sum(len(w["variants"][v]["candidates"]) for w in ws),
        "pairs_ok": ok_pairs,
        "excluded": reasons,
        "bench_excluded_weeks": bench_out,
        "evaluable_weeks": evaluable,
        "abstain_weeks": sum(1 for w in ws if w["variants"][v]["abstain"]),
        "next_week_dropout_pairs": dropouts,
    }


def counts(src: Source, wks: list[dict], spans: dict, table_counts: dict) -> dict:
    """잠금 분모 전체(PLAN §1-4 칸 · 분모 갈래 · 체결 가능 짝 · 분류표 수)."""
    out: dict[str, Any] = {}
    for span in spans:
        ws = [w for w in wks if w["span"] == span]
        if not ws:
            out[span] = {"weeks": 0}
            continue
        mv = [w["variants"]["MAIN"] for w in ws]
        ov = [w["variants"]["OFFICIAL"] for w in ws]
        den = [w["denominator"] for w in ws]
        reason_weeks: collections.Counter = collections.Counter()
        for x in den:
            for k, n in x["unknown_reasons"].items():
                reason_weeks[k] += n
        c: dict[str, Any] = {
            "weeks": len(ws),
            "first": ws[0]["D"],
            "last": ws[-1]["D"],
            "cand_weeks": sum(1 for x in mv if x["candidates"]),
            "cand_weeks_official": sum(1 for x in ov if x["candidates"]),
            "est_cand_weeks": sum(
                1 for x in mv if any(c[2] == CL.EST_DE for c in x["candidates"])
            ),
            "pairs_official": sum(
                1 for x in mv for c in x["candidates"] if c[2] == CL.OFF_DE
            ),
            "pairs_estimated": sum(
                1 for x in mv for c in x["candidates"] if c[2] == CL.EST_DE
            ),
            "unknown_rows": sum(len(w["unknown_top"]) for w in ws),
            "unknown_rows_delisted": sum(
                1 for w in ws for u in w["unknown_top"] if u[2]
            ),
            "votes_min": min(x["votes"] for x in mv),
            "votes_official_min": min(x["votes"] for x in ov),
            "votes_median": statistics.median([x["votes"] for x in mv]),
            "votes_official_median": statistics.median([x["official"] for x in den]),
            "votes_estimated_median": statistics.median([x["estimated"] for x in den]),
            "votes_estimated_max": max(x["estimated"] for x in den),
            "votes_unknown_median": statistics.median([x["unknown"] for x in den]),
            "votes_unknown_max": max(x["unknown"] for x in den),
            "unknown_reason_name_weeks": dict(sorted(reason_weeks.items())),
            "preopen_unavailable_weeks": 0,
        }
        for v in P.VARIANTS:
            c[v] = _variant_counts(src, ws, v)
        out[span] = c
    out["classification"] = table_counts
    return out


def records(wks: list[dict], rows: dict[str, list[dict]]) -> list[dict]:
    """주별 기록 전체(설계 §4-3 · 판정 §2 · 분모 갈래 포함) — 저장 weeks.json 과 같은 모양."""
    by = {v: {r["D"]: r for r in rows[v]} for v in P.VARIANTS}
    out = []
    for w in wks:
        variants = {}
        for v in P.VARIANTS:
            row = by[v][w["D"]]
            variants[v] = {
                **w["variants"][v],
                "result_20bp": {k: row[k] for k in _RESULT_KEYS if k in row},
            }
        out.append(
            {
                "D": w["D"],
                "span": w["span"],
                "sub": w["sub"],
                "record_kind": RECORD_KIND,
                "price_window": [w["start"], w["D"]],
                "price_state": "종가",
                "availability": P.AVAILABILITY,
                "fills": {
                    "immediate": f"{w['e1']} 시가",
                    "hold_and_evaluation": f"{w['e2']} 시가",
                    "note": P.FILL_NOTE,
                },
                "gap_days": w["gap_days"],
                "bench_ret_1m": w["bench_ret_1m"],
                "population": w["population"],
                "top": w["top"],
                "unknown_top": w["unknown_top"],
                "denominator": w["denominator"],
                "next_top": w["next_top"],
                "variants": variants,
            }
        )
    return out
