"""AC1 대조(판정 §3) — 같은 시점의 실제 목록 세 곳 · 보관 응답 · 봉인 안 한 주.

```text
① 이번 주  PC 연구 목록 ↔ 「주간 ETF 점검」(GET /weekly/etf-check) ↔ 「후보리스트」(GET /market/etf-compare/summary)
           기준일 · 가격 기간 · 제외 조건 · 상위 30 코드와 순위 · 가격 상태(상위 30) · 전체 후보 수와 제외 사유
           조회 → 연구 계산 → 다시 조회 · 기준일이 바뀌면 한 번 더(그래도 바뀌면 멈춤)
② 보관 응답 POC7-02 보관 `response.json`(11/23) 상위 30 ↔ 같은 끝일 연구 계산(PC DB 는 갱신 때 덮어쓰므로 차이 기록)
③ 봉인 안   2026-09-18 운영 규칙(PC DB · 지금 이름) ↔ 봉인 복원(그날 이름) — 전체 후보 · 순위 · 1개월 · 오른 주
읽기 전용   로컬 서버 GET · PC 시세 DB 읽기 전용 · 봉인 DB 읽기 전용
```
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from app.candidate_compare import current as CU
from app.candidate_compare import population as PO
from app.candidate_compare.protocol import (
    LOOKBACK_1M,
    N_INTERVALS,
    CheckRequired,
    Config,
)
from app.entry_timing import data as DA

BASE_URL = "http://127.0.0.1:8000"
SUMMARY_Q = (
    "/market/etf-compare/summary?basis=one_month&exclude_inverse=true&exclude_leveraged=true"
    "&exclude_synthetic=true&exclude_futures=true"
)
COUNT_KEYS = (
    "universe",
    "no_price",
    "filter_excluded",
    "no_return",
    "end_differs",
    "start_differs",
    "population",
)
Fetch = Callable[[str], dict]


def http_fetch(path: str) -> dict:
    """로컬 서버 GET(프록시 끔 · 127.0.0.1 만)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(BASE_URL + path, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


STATE_KEYS = ("intraday", "after_close", "unknown")


def _obj(x: Any) -> Mapping[str, Any]:
    return x if isinstance(x, Mapping) else {}


def _list(x: Any) -> list:
    return x if isinstance(x, list) else []


def weekly_top(resp: Any) -> list[list]:
    rows = [
        [_obj(m).get("rank"), _obj(m).get("ticker")]
        for f in _list(_obj(resp).get("flows"))
        for m in _list(_obj(f).get("members"))
    ]
    # 순위 숫자 순(원래와 같음) · 형식이 틀린 순위는 뒤로(대조가 다름으로 잡음)
    return sorted(
        rows,
        key=lambda r: (0, r[0], str(r[1])) if type(r[0]) is int else (1, 0, str(r)),
    )


def research_top(data: Mapping[str, Any]) -> list[list]:
    return [
        [it["rank"], it["ticker"]] for it in data["items"] if it["rank"] <= CU.TOP_N
    ]


def weekly_fields(resp: Any) -> dict[str, Any]:
    """「주간 ETF 점검」 응답에서 대조에 쓰는 칸 전부 — 같은 시점 지문도 이 dict 그대로(r2 F7 · 대조 칸 = 지문 칸)."""
    r = _obj(resp)
    cond = _obj(r.get("condition"))
    ps = _obj(_obj(r.get("data_quality_snapshot")).get("price_states"))
    return {
        "end_date": r.get("end_date"),
        "period": [cond.get("start"), cond.get("end")],
        "filters": cond.get("filters"),
        "top": weekly_top(r),
        "states": {
            str(t): _obj(v).get("state") for t, v in _obj(ps.get("rows")).items()
        },
        "kodex_state": _obj(ps.get("kodex200")).get("state"),
    }


def summary_fields(resp: Any) -> dict[str, Any]:
    """「후보리스트」 응답에서 대조에 쓰는 칸 전부 — 같은 시점 지문도 이 dict 그대로(r2 F7)."""
    r = _obj(resp)
    period = _obj(r.get("period"))
    return {
        "end_date": r.get("end_date"),
        "period": [period.get("start"), period.get("end")],
        "filters": r.get("filters"),
        "top": [
            [_obj(x).get("rank"), _obj(x).get("ticker")] for x in _list(r.get("top"))
        ],
        "counts": {k: _obj(r.get("counts")).get(k) for k in COUNT_KEYS},
        "state_counts": {
            k: _obj(r.get("price_state")).get(f"{k}_count") for k in STATE_KEYS
        },
        "kodex_state": _obj(_obj(r.get("regime")).get("price")).get("state"),
    }


def _canon(x: Any) -> str:
    """형까지 보는 비교용 글 — 1 · True · 1.0 을 다르게 본다(파이썬 == 는 같게 봄 · r2 반박 5)."""
    return json.dumps(
        x, sort_keys=True, ensure_ascii=True, allow_nan=True, default=repr
    )


def _eq(*xs: Any) -> bool:
    return len({_canon(x) for x in xs}) == 1


def current_week(fetch: Fetch, research: Callable[[], dict]) -> dict[str, Any]:
    """① 같은 시점 세 곳 대조 — 필드별 같음 / 다름(형까지).

    같은 시점 = 연구 계산 앞뒤 두 번 조회한 두 응답에서 **대조에 쓰는 칸 전부**(`weekly_fields` · `summary_fields`)가
    형까지 같고 끝일이 세 곳 모두 같을 때(r1 F4 · r2 F7). 두 번 해도 아니면 DATA_CHANGED. 대조는 그 칸들로만 한다.
    """
    changed: list[str] = []
    for _attempt in range(2):
        w1 = weekly_fields(fetch("/weekly/etf-check"))
        s1 = summary_fields(fetch(SUMMARY_Q))
        data = research()
        w2 = weekly_fields(fetch("/weekly/etf-check"))
        s2 = summary_fields(fetch(SUMMARY_Q))
        changed = [
            n for n, a, b in (("weekly", w1, w2), ("summary", s1, s2)) if not _eq(a, b)
        ]
        if not _eq(w1["end_date"], s1["end_date"], data.get("end")):
            changed.append("end_date")
        if not changed:
            break
    else:
        return {"status": "DATA_CHANGED", "changed": changed}
    return compare_current(w1, s1, data)


def compare_current(
    w: Mapping[str, Any], s: Mapping[str, Any], data: Mapping[str, Any]
) -> dict[str, Any]:
    """세 곳 대조 — 응답 쪽은 `weekly_fields` · `summary_fields` 가 만든 칸만 쓴다 · 모든 비교는 형까지(_eq)."""
    by = {it["ticker"]: it for it in data["items"]}
    top = research_top(data)
    top_codes = {t for _r, t in top}
    checks: dict[str, Any] = {
        "end_date": [w["end_date"], s["end_date"], data["end"]],
        "period_1m": [w["period"], s["period"], list(data["windows"]["one_month"])],
        "filters": [w["filters"], s["filters"], data["filters"]],
        "top30_weekly_vs_research": _eq(w["top"], top),
        "top30_summary_vs_research": _eq(s["top"], top),
        "counts": {k: [s["counts"][k], data["counts"].get(k)] for k in COUNT_KEYS},
        # 가격 상태는 연구 상위 30 과 같은 종목 집합이어야(일부만 오면 다름 · 반박 5)
        "price_states_rows_same_codes": set(w["states"]) == top_codes,
        "price_states_top30": {
            t: [st, by[t]["state"] if t in by else None]
            for t, st in w["states"].items()
        },
        # 「후보리스트」 모집단 끝일 가격 상태 개수 ↔ 연구 목록(같은 기준 · 검토 m8)
        "price_state_counts": {
            k: [s["state_counts"][k], data["price_states"].get(k, 0)]
            for k in STATE_KEYS
        },
        # KODEX 200 끝일 상태 — 주별 끝일 규칙의 입력(주간 점검 · 후보리스트 · 연구)
        "kodex_end_state": [w["kodex_state"], s["kodex_state"], data["bench_state"]],
    }
    same = {
        "end_date": _eq(*checks["end_date"]),
        "period_1m": _eq(*checks["period_1m"]),
        "filters": _eq(*checks["filters"]),
        "top30_weekly": checks["top30_weekly_vs_research"],
        "top30_summary": checks["top30_summary_vs_research"],
        "counts": all(_eq(a, b) for a, b in checks["counts"].values()),
        "price_states": checks["price_states_rows_same_codes"]
        and bool(top_codes)
        and all(_eq(a, b) for a, b in checks["price_states_top30"].values()),
        "price_state_counts": all(
            _eq(a, b) for a, b in checks["price_state_counts"].values()
        ),
        "kodex_end_state": _eq(*checks["kodex_end_state"]),
    }
    return {
        "status": "SAME" if all(same.values()) else "DIFFERENT",
        "same": same,
        "checks": checks,
        "beyond_top30": data["counts"]["population"]
        - min(CU.TOP_N, data["counts"]["population"]),
        "weekly_unconfirmed": data["up_distribution"]["none"],
        "weekly": data["weekly"],
    }


def _finite(x: Any) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


def stored_response(path: Path, research_at: Callable[[str], dict]) -> dict[str, Any]:
    """② 보관 응답 상위 30 ↔ 같은 끝일 연구 계산 — SAME = 행 있음 · 중복 없음 · 종목 집합 = 연구 상위 목록 · 순위(정수) ·
    1개월(유한 수 · 1e-3 안) 모두 같음."""
    resp = _obj(json.loads(Path(path).read_text(encoding="utf-8")))
    end = resp.get("end_date")
    # 끝일 칸이 빠지면 '최신일'로 읽지 않는다(r3 F9 같은 종류)
    if not isinstance(end, str):
        return {
            "end_date": end,
            "status": "DIFFERENT",
            "why": "보관 응답에 끝일이 없음",
        }
    data = research_at(end)
    rows = [_obj(r) for r in _list(resp.get("candidate_snapshot"))]
    # 종목 칸이 글이 아닌 행은 비교할 수 없음(사전 키로 쓰지 않는다 · r3 F8 같은 종류)
    odd = [r for r in rows if not isinstance(r.get("ticker"), str)]
    snap = {r["ticker"]: r for r in rows if isinstance(r.get("ticker"), str)}
    by = {it["ticker"]: it for it in data["items"]}
    diffs = []
    for t, r in snap.items():
        it = by.get(t)
        if it is None:
            diffs.append({"ticker": t, "stored_rank": r.get("rank"), "now": None})
            continue
        stored = r.get("one_month_return_pct")
        if (
            type(r.get("rank")) is not int
            or r.get("rank") != it["rank"]
            or not _finite(stored)
            or abs(it["one_month"]["value"] - stored) > 1e-3
        ):
            diffs.append(
                {
                    "ticker": t,
                    "stored_rank": r.get("rank"),
                    "now_rank": it["rank"],
                    "stored_1m": stored,
                    "now_1m": it["one_month"]["value"],
                }
            )
    same_codes = set(snap) == {
        it["ticker"] for it in data["items"] if it["rank"] <= CU.TOP_N
    }
    # 빈 목록 · 같은 종목 두 번 = 온전하지 않음
    whole = bool(rows) and not odd and len(snap) == len(rows) and isinstance(end, str)
    return {
        "end_date": end,
        "stored_top": len(rows),
        "same_codes": same_codes,
        "stored_rows_whole": whole,
        "differences": diffs,
        "status": "SAME" if not diffs and same_codes and whole else "DIFFERENT",
    }


def _picks_same(sealed: Mapping[str, dict], pc: Mapping[str, Any]) -> dict[str, Any]:
    """두 출처의 두 기준 선정이 같은가(같은 함수 · 같은 주)."""
    from app.candidate_compare import rules as RU

    cands = [
        RU.Cand(c, p["ret"], p["up"]) for c, p in sealed.items() if p["up"] is not None
    ]
    a, b = (RU.pick_a(cands), RU.pick_b(cands)) if len(cands) >= 3 else ([], [])
    return {
        "a": [a, pc["picks_a"]],
        "b": [b, pc["picks_b"]],
        "same": a == pc["picks_a"] and b == pc["picks_b"],
    }


def sealed_week(
    cfg: Config,
    signal: str,
    research_at: Callable[[str], dict],
    data: Optional[PO.Data] = None,
) -> dict[str, Any]:
    """③ 봉인 안 한 주 — 운영 규칙(PC DB) ↔ 봉인 복원 전체 후보 · 순위 · 1개월 · 오른 주."""
    data = data or PO.load(cfg)
    panel = data.panel
    sig = DA.weekly_signals(panel.axis)
    k = next((k for k, i in enumerate(sig) if panel.axis[i] == signal), None)
    if k is None or k < N_INTERVALS:
        raise CheckRequired(f"봉인 축의 주 신호일이 아님: {signal}")
    i = sig[k]
    s = DA.window_start(panel.axis, i, LOOKBACK_1M)
    wk = [sig[k - N_INTERVALS + m] for m in range(N_INTERVALS + 1)]
    sealed = {p["code"]: p for p in PO.population(panel, i, s, wk)}
    pc = research_at(signal)
    pcs = {it["ticker"]: it for it in pc["items"]}
    only_sealed = sorted(set(sealed) - set(pcs))
    only_pc = sorted(set(pcs) - set(sealed))
    both = sorted(set(sealed) & set(pcs))
    rank_diff = [t for t in both if sealed[t]["orig_rank"] != pcs[t]["rank"]]
    up_diff = [t for t in both if sealed[t]["up"] != pcs[t]["up"]]
    ret_gap = max(
        (abs(sealed[t]["ret"] * 100 - pcs[t]["one_month"]["value"]) for t in both),
        default=None,
    )
    top30_s = [t for t, p in sorted(sealed.items(), key=lambda x: x[1]["orig_rank"])][
        : CU.TOP_N
    ]
    top30_p = [it["ticker"] for it in pc["items"] if it["rank"] <= CU.TOP_N]
    return {
        "signal": signal,
        "weekly_dates_sealed": [panel.axis[w] for w in wk],
        "weekly_dates_pc": pc["weekly"]["dates"],
        "sealed_pop": len(sealed),
        "pc_pop": len(pcs),
        "only_sealed": only_sealed[:50],
        "only_pc": only_pc[:50],
        "rank_differs": len(rank_diff),
        "first_rank_differs": min(
            (sealed[t]["orig_rank"] for t in rank_diff), default=None
        ),
        "max_rank_shift": max(
            (abs(sealed[t]["orig_rank"] - pcs[t]["rank"]) for t in rank_diff), default=0
        ),
        "picks_same": _picks_same(sealed, pc),
        "up_differs": len(up_diff),
        "up_differs_codes": up_diff[:50],
        "max_1m_gap_pctp": ret_gap,
        "top30_same": top30_s == top30_p,
    }
