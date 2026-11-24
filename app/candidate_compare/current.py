"""이번 주 한 장의 자료 — PC 시세 DB(읽기 전용)를 운영 규칙 그대로 읽어 전체 후보를 만든다(PLAN §5).

```text
끝일     운영과 같음 = ETF 목록 종목 가격의 저장 최신일
         1 · 3개월 공통 기간 = 069500 유효 행(운영 `_assemble`)
전체     운영 모집단 고리와 같은 순서 · 같은 사유
         (no_price · filter_excluded · no_return · end_differs · start_differs)
         순위 = 1개월(반올림 전) 내림차순 · 같으면 종목코드 — 상위 30 = 「주간 ETF 점검」 상위 30
주별 끝일 W0 = 거래 일정(calendar.check_trading_day · 연도 파일 · 없으면 평일 계약)상 그 주 마지막 거래일을
         끝일까지 마쳤고 그날이 069500 축에 있으며 069500 가격이 '마감 뒤 저장'인 가장 최근 주의 마지막 거래일
         · 1개월 끝일과 다르면 '주중 참고'(판정 Q6) · 건너뛴 주와 사유를 남긴다
주 마감  W-4 ~ W0 = 069500 축의 연속 ISO 주 마지막 거래일 5번 · 다섯 주 모두 일정상 마지막 거래일과 같아야 함
         (아니면 날짜 없음 · 모든 후보 오른 주 미확인) · 후보 값은 그날 유효 종가이고 '마감 뒤 저장'일 때만
         (없음 · 장중 저장 · 저장 시각 불명 = 미확인 · 사유를 남김)
두 기준  rules.pick_a · rules.pick_b(과거 비교와 같은 함수)
상세     가격 근거 = 이 모듈 계산(모든 후보) · 구성 · 겹침 = 「주간 ETF 점검」 ③ 과 같은 읽기
         (weekly_candidate_reads.read_candidate → weekly_review.overlap_of · 읽기 전용 · 외부 조회 0)
```
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from app import index_family as IF
from app import pc_etf_compare_summary as PS
from app import weekly_review as WR
from app.candidate_compare import rules as RU
from app.candidate_compare.protocol import BENCH, LOOKBACK_1M, LOOKBACK_3M, N_INTERVALS
from app.constituents_pair_exposure import condition_of
from app.market_topn_helpers import classify_etf_tags
from app.pc_etf_compare_groups import classify_etf
from app.pc_etf_compare_periods import (
    STATE_AFTER_CLOSE,
    STATE_INTRADAY,
    period_value,
    period_window,
    price_state,
)
from app.same_period_kodex200 import valid_close

KST = timezone(timedelta(hours=9))
SCREEN = "poc7_03_research"
TOP_N = 30
FILTER_TAGS = PS.FILTER_TAGS
Reader = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def _windows(
    kodex_valid: list[tuple[str, float]], end: str
) -> dict[str, Optional[tuple[str, str]]]:
    out: dict[str, Optional[tuple[str, str]]] = {}
    for key, days in (("one_month", LOOKBACK_1M), ("three_month", LOOKBACK_3M)):
        w = period_window(kodex_valid, end, days)
        out[key] = (
            None
            if w is None or kodex_valid[w[1]][0] != end
            else (kodex_valid[w[0]][0], kodex_valid[w[1]][0])
        )
    return out


def _iso(d: str) -> tuple[int, int]:
    y, w, _ = dt.date.fromisoformat(d).isocalendar()
    return (y, w)


def default_is_trading(d: str) -> bool:
    """프로젝트 거래일 계약(연도 파일 · 없으면 평일 + 5/1 · 12/31 휴장) — `calendar.check_trading_day`."""
    from app.market_briefing.calendar import check_trading_day

    return bool(check_trading_day(d).ok)


def _scheduled_last(
    week: tuple[int, int], is_trading: Callable[[str], bool]
) -> Optional[str]:
    """그 ISO 주의 일정상 마지막 거래일(월 ~ 금 중 거래일인 마지막 날) · 없으면 None."""
    monday = dt.date.fromisocalendar(week[0], week[1], 1)
    days = [(monday + timedelta(days=k)).isoformat() for k in range(5)]
    sched = [d for d in days if is_trading(d)]
    return sched[-1] if sched else None


def weekly_dates(
    axis: list[str],
    end: str,
    bench_states: Mapping[str, str],
    is_trading: Callable[[str], bool],
) -> dict[str, Any]:
    """주별 끝일 W0 과 주 마감 5번(판정 Q6 · 검증자 r1 F3).

    W0 = 끝일까지 거래 일정상 마지막 거래를 마쳤고(그 주 일정상 마지막 거래일 ≤ 끝일 · 그날이 축에 있음)
    그날 069500 가격이 '마감 뒤 저장'인 가장 최근 주의 마지막 거래일. 아니면 한 주씩 앞으로(skipped 에 사유).
    축은 일정상 거래일만 본다(일정 밖 날짜 행은 off_schedule 에 남김).
    W-1 ~ W-4 = W0 앞 네 주의 축 마지막 거래일 — 각각 일정상 마지막 거래일과 같고, 사이에 일정상 거래일이
    있는데 축에 없는 주가 없어야 한다. 아니면 날짜 없음(gap 에 사유 · 모든 후보 오른 주 미확인).
    """
    # 일정 밖 날짜(주말 등)의 행은 주 마감 날짜로 쓰지 않는다 — 그런 행 때문에 끝난 주를 건너뛰지 않게(반박 재현 c)
    days = [d for d in axis if d <= end and is_trading(d)]
    off = [d for d in axis if d <= end and not is_trading(d)]
    weeks: dict[tuple[int, int], str] = {}
    for d in days:
        weeks[_iso(d)] = d  # 그 주 축 마지막 거래일
    order = sorted(weeks)
    skipped: list[dict[str, Any]] = []
    w0 = None
    for wk in reversed(order):
        last = weeks[wk]
        sched = _scheduled_last(wk, is_trading)
        if sched is None or sched > end:
            skipped.append({"week_last": last, "why": "week_unfinished"})
            continue
        if last != sched:
            skipped.append(
                {"week_last": last, "why": "schedule_gap", "scheduled": sched}
            )
            continue
        if bench_states.get(last) != STATE_AFTER_CLOSE:
            skipped.append({"week_last": last, "why": "bench_not_after_close"})
            continue
        w0 = wk
        break
    base = {"finished": _iso(end) == w0, "skipped": skipped, "off_schedule": off[-10:]}
    none = {"dates": None, "w0": None, "mid_week": None, **base}
    if w0 is None:
        return {**none, "gap": {"why": "no_finished_week"}}
    keep = N_INTERVALS + 1
    upto = [w for w in order if w <= w0][-keep:]
    if len(upto) < keep:
        return {**none, "gap": {"why": "too_few_weeks"}}
    # W-4 ~ W-1 도 일정과 맞춤(반박 m3) — 그 주 축 마지막 날 = 일정상 마지막 거래일 · 사이에 빠진 주 없음
    for w in upto[:-1]:
        sched = _scheduled_last(w, is_trading)
        if weeks[w] != sched:
            gap = {"why": "schedule_gap", "week_last": weeks[w], "scheduled": sched}
            return {**none, "gap": gap}
    day = dt.date.fromisocalendar(upto[0][0], upto[0][1], 1)
    while day < dt.date.fromisocalendar(w0[0], w0[1], 1):
        iso = _iso(day.isoformat())
        sched = _scheduled_last(iso, is_trading)
        if iso not in weeks and sched is not None:
            return {**none, "gap": {"why": "missing_week", "scheduled": sched}}
        day += timedelta(days=7)
    picked = [weeks[w] for w in upto]
    return {
        "dates": picked,
        "w0": picked[-1],
        "mid_week": picked[-1] != end,
        "gap": None,
        **base,
    }


def fingerprint(market: Mapping[str, Any]) -> str:
    """같은 시점 확인용 자료 지문 — 끝일 · 이름 · 모든 가격 행(날짜 · 종가 · 저장 시각) · KODEX 200 행."""
    h = hashlib.sha256()
    h.update(str(market["end"]).encode())
    for tk in sorted(market["names"]):
        h.update(f"|{tk}:{market['names'][tk]}".encode())
    for tk in sorted(market["raw"]):
        for r in market["raw"][tk]:
            h.update(f"|{tk},{r.date},{r.close},{r.fetched_at}".encode())
    for r in market["kodex_full"]:
        h.update(f"|K,{r.date},{r.close},{r.fetched_at}".encode())
    return h.hexdigest()


GAP_OF_STATE = {STATE_INTRADAY: "intraday_close"}


def _week_closes(
    rows: list[Any], dates: list[str]
) -> tuple[list[Optional[float]], Optional[str]]:
    """주 마감 5번 — 그날 유효 종가이고 '마감 뒤 저장'일 때만 값 · 아니면 None 과 첫 사유(F3)."""
    by = {r.date: r for r in rows}
    out: list[Optional[float]] = []
    gap = None
    for d in dates:
        r = by.get(d)
        if r is None or not valid_close(r.close):
            out.append(None)
            gap = gap or "no_price"
            continue
        st = price_state(d, r.fetched_at)["state"]
        if st != STATE_AFTER_CLOSE:
            out.append(None)
            gap = gap or GAP_OF_STATE.get(st, "unknown_close")
            continue
        out.append(float(r.close))
    return out, gap


def _state(rows: list[Any], end: str) -> str:
    last = next((r for r in reversed(rows) if r.date == end), None)
    return (
        price_state(end, last.fetched_at if last else None)["state"]
        if last
        else "unknown"
    )


def read_market(db_path: Path, end: Optional[str] = None) -> dict[str, Any]:
    """PC 시세 DB 를 운영과 같은 질의로 읽는다(읽기 전용 · `end` = 과거 대조용 끝일 지정)."""
    with closing(PS._ro(db_path)) as con:
        if end is None:
            end = con.execute(
                "SELECT MAX(p.date) FROM etf_daily_price p JOIN etf_master m ON m.ticker = p.ticker"
            ).fetchone()[0]
        if not end:
            raise ValueError("저장된 가격이 없음")
        start_from = (
            dt.date.fromisoformat(end) - timedelta(days=LOOKBACK_3M)
        ).isoformat()
        raw, names = PS._read(con, end, start_from)
        kodex_full = [
            PS.PriceRow(d, c, s, fa, ch)
            for d, c, s, fa, ch in con.execute(
                "SELECT date, close, source, fetched_at, change FROM etf_daily_price "
                "WHERE ticker = ? AND date <= ? ORDER BY date",
                (BENCH, end),
            )
        ]
    return {"end": end, "raw": raw, "names": names, "kodex_full": kodex_full}


def build(
    market: Mapping[str, Any],
    *,
    filters: Mapping[str, bool],
    official: Mapping[str, Mapping[str, str]],
    dictionary: Optional[Mapping[str, list[str]]],
    reader: Optional[Reader] = None,
    is_trading: Optional[Callable[[str], bool]] = None,
) -> dict[str, Any]:
    """전체 후보 · 사유 개수 · 주 마감 · 두 기준 · 후보별 상세(reader 가 있으면 구성 · 겹침까지)."""
    end, raw, names = market["end"], market["raw"], market["names"]
    kodex_valid = [
        (r.date, float(r.close)) for r in market["kodex_full"] if valid_close(r.close)
    ]
    win = _windows(kodex_valid, end)
    common = win["one_month"]
    out: dict[str, Any] = {"end": end, "filters": dict(filters), "windows": win}
    if common is None:
        return {**out, "status": "no_common_period"}
    bench_state = _state(list(market["kodex_full"]), end)
    bench_states = {
        r.date: price_state(r.date, r.fetched_at)["state"]
        for r in market["kodex_full"]
        if valid_close(r.close)
    }
    wk = weekly_dates(
        [d for d, _ in kodex_valid], end, bench_states, is_trading or default_is_trading
    )
    out.update(bench_state=bench_state, weekly=wk)
    exclude = {t for t in FILTER_TAGS if filters.get(f"exclude_{t}")}
    counts: Counter = Counter(
        {
            k: 0
            for k in (
                "universe",
                "no_price",
                "filter_excluded",
                "no_return",
                "end_differs",
                "start_differs",
            )
        }
    )  # 운영 응답처럼 0 인 사유도 칸으로 남긴다(AC1 대조)
    pop: list[dict[str, Any]] = []
    for tk in sorted(names):
        rows = raw.get(tk, [])
        valid = [(r.date, float(r.close)) for r in rows if valid_close(r.close)]
        counts["universe"] += 1
        if not valid:
            counts["no_price"] += 1
            continue
        tags = classify_etf_tags(names.get(tk))
        if exclude & set(tags):
            counts["filter_excluded"] += 1
            continue
        v = period_value(valid, end, LOOKBACK_1M)
        if v is None:
            counts["no_return"] += 1
            continue
        if v["end"] != common[1]:
            counts["end_differs"] += 1
            continue
        if v["start"] != common[0]:
            counts["start_differs"] += 1
            continue
        pop.append(
            {"ticker": tk, "name": names.get(tk), "v1": v, "valid": valid, "rows": rows}
        )
    counts["population"] = len(pop)
    pop.sort(key=lambda p: (-p["v1"]["raw"], p["ticker"]))
    k1 = period_value(kodex_valid, end, LOOKBACK_1M)
    k3 = period_value(kodex_valid, end, LOOKBACK_3M) if win["three_month"] else None
    fam = Counter()
    for r, p in enumerate(pop, 1):
        p["rank"] = r
        state = _state(p["rows"], end)
        closes: list[Optional[float]] = [None] * (N_INTERVALS + 1)
        # 오른 주 미확인 사유(첫 문제 · no_price · intraday_close · unknown_close · weekly_unavailable)
        week_gap = "weekly_unavailable"
        if wk["dates"]:
            closes, week_gap = _week_closes(p["rows"], wk["dates"])
        v3 = period_value(p["valid"], end, LOOKBACK_3M)
        three = None
        if v3 is not None:
            if win["three_month"] is None:
                st3 = "kodex_window_unknown"  # 운영과 같음 — KODEX 200 3개월 기간을 정할 수 없음
            elif (v3["start"], v3["end"]) == win["three_month"]:
                st3 = "ok"
            else:
                st3 = "period_differs"
            three = {
                "value": v3["raw"],
                "start": v3["start"],
                "end": v3["end"],
                "status": st3,
            }
        cls = classify_etf(p["ticker"], p["name"], official, dictionary)
        family = IF.family_of(cls.get("index_name"))
        fam[family] += int(family is not None)
        p.update(
            state=state,
            closes=closes,
            changes=RU.interval_changes(closes),
            up=RU.up_weeks(closes),
            week_gap=week_gap,
            three=three,
            index_name=cls.get("index_name"),
            family=family,
        )
    common_list = [p for p in pop if p["up"] is not None]
    for r, p in enumerate(common_list, 1):
        p["common_rank"] = r
    cands = [RU.Cand(p["ticker"], p["v1"]["raw"], p["up"]) for p in common_list]
    picks_a = RU.pick_a(cands) if len(cands) >= 3 else []
    picks_b = RU.pick_b(cands) if len(cands) >= 3 else []
    items = []
    for p in pop:
        item = {
            "rank": p["rank"],
            "common_rank": p.get("common_rank"),
            "ticker": p["ticker"],
            "name": p["name"],
            "one_month": {
                "value": p["v1"]["raw"],
                "start": p["v1"]["start"],
                "end": p["v1"]["end"],
            },
            "three_month": p["three"],
            "state": p["state"],
            "closes": p["closes"],
            "moves": [RU.move_of(c) for c in p["changes"]],
            "changes": p["changes"],
            "up": p["up"],
            "week_gap": p["week_gap"],
            "top30": p["rank"] <= TOP_N,
            "index_name": p["index_name"],
            "family_size": fam[p["family"]] if p["family"] is not None else None,
        }
        if reader is not None:
            item["detail"] = _detail(reader, item, filters)
        items.append(item)
    dist = Counter(p["up"] for p in pop)
    out.update(
        status="ok",
        counts=dict(counts),
        kodex={
            "one_month": (
                None
                if k1 is None
                else {"value": k1["raw"], "start": k1["start"], "end": k1["end"]}
            ),
            "three_month": (
                None
                if k3 is None
                else {"value": k3["raw"], "start": k3["start"], "end": k3["end"]}
            ),
        },
        items=items,
        n_common=len(common_list),
        up_distribution={str(k): dist.get(k, 0) for k in range(N_INTERVALS + 1)}
        | {"none": dist.get(None, 0)},
        picks_a=picks_a,
        picks_b=picks_b,
        price_states=dict(Counter(p["state"] for p in pop)),
    )
    return out


def _detail(
    reader: Reader, item: Mapping[str, Any], filters: Mapping[str, bool]
) -> dict[str, Any]:
    """구성 · 겹침 — 「주간 ETF 점검」 ③ 과 같은 읽기와 글(조건만 이 연구 화면)."""
    cond = condition_of(
        screen=SCREEN,
        basis="one_month",
        side=None,
        rank=item["rank"],
        start_date=item["one_month"]["start"],
        end_date=item["one_month"]["end"],
        filters=dict(filters),
    )
    try:
        got = reader(item["ticker"], cond)
    except (sqlite3.Error, OSError, ValueError, KeyError):
        return {"constituents": None, "overlap": None, "error": True}
    cons = got.get("constituents") or {}
    sel = {"ticker": item["ticker"], "name": item["name"], "rank": item["rank"]}
    ov = WR.overlap_of(sel, got.get("exposure"), bool(got.get("exposure_error")))
    scope = (got.get("exposure") or {}).get("scope") or {}
    return {
        "constituents": {
            k: cons.get(k)
            for k in ("state", "state_label", "asof", "stored_rows", "line")
        },
        "overlap": {
            k: ov.get(k)
            for k in ("state", "warn_lines", "lines", "date_line", "numbers")
        },
        # 시세가 없어 비중을 모르는 보유 수(분모 밖) — 복사문 '모두 확인' 과장 막기(글에는 숫자를 쓰지 않음)
        "no_weight": (scope.get("no_weight") or {}).get("count"),
        "error": False,
    }


def latest_end(db_path: Path) -> Optional[str]:
    """지금 저장 최신일(운영 끝일과 같은 질의) — 한 장을 다 만든 뒤 끝날짜가 바뀌었는지 다시 본다."""
    with closing(PS._ro(db_path)) as con:
        return con.execute(
            "SELECT MAX(p.date) FROM etf_daily_price p JOIN etf_master m ON m.ticker = p.ticker"
        ).fetchone()[0]


def default_reader(db_path: Path) -> Reader:
    from app import weekly_candidate_reads as WCR

    def read(ticker: str, cond: Mapping[str, Any]) -> Mapping[str, Any]:
        return WCR.read_candidate(ticker, db_path=db_path, condition=cond)

    return read


def now_kst() -> datetime:
    return datetime.now(KST)


__all__ = ["build", "read_market", "weekly_dates", "default_reader", "STATE_INTRADAY"]
