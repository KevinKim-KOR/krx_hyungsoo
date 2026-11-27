"""그 뒤 관측 · 이번 주 지금까지(PLAN §3 · V2 판정 2026-11-25 Q6 · PLAN V2 판정 2026-11-26 §2) — history 에서 나눔.

```text
종가      close_at = 그날 유효 종가이고 '마감 뒤 저장'일 때만(장중 저장 · 저장 시각 불명은 사유)
그 뒤     그 마감 종가 → 다음 주 마감 종가(ETF · KODEX 200) — 그때 판단의 근거가 아님
          다음 주 마감이 끝일 뒤이거나 끝일인데 아직 장중 저장값이면 기간 미경과 · 지났는데 값이 없으면 자료 없음
이번 주   진행 주(그 주 일정상 마감 > 끝일 · 또는 = 끝일인데 장중) = 거래 일정상 직전 완료 주 마감 → 끝일까지 두 종목에
지금까지  공통으로 마감 뒤 저장 종가가 있는 마지막 거래일 · 시작일에 두 종목 마감 종가가 다 있지 않으면 비교 불가
          (no_prev_close) · 표 · 복사문 · 그래프(flow)가 같은 종가
```
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional

from app.candidate_compare import current as CU
from app.pc_etf_compare_periods import STATE_AFTER_CLOSE, STATE_INTRADAY, price_state
from app.same_period_kodex200 import valid_close

if (
    TYPE_CHECKING
):  # 형 표시만 — history 가 이 모듈을 불러 쓰므로 실행 때는 가져오지 않음
    from app.weekly_decision.history import Context


def close_at(rows: list[Any], d: str) -> tuple[Optional[float], Optional[str]]:
    """그날 장마감 종가 — 유효 종가이고 '마감 뒤 저장'일 때만(아니면 None · 사유)."""
    r = next((x for x in rows if x.date == d), None)
    if r is None or not valid_close(r.close):
        return None, "no_price"
    st = price_state(d, r.fetched_at)["state"]
    if st != STATE_AFTER_CLOSE:
        return None, ("intraday_close" if st == STATE_INTRADAY else "unknown_close")
    return float(r.close), None


def change(rows: list[Any], a: str, b: str) -> dict[str, Any]:
    ca, wa = close_at(rows, a)
    cb, wb = close_at(rows, b)
    if ca is None or cb is None:
        return {"value": None, "why": wa or wb}
    return {"value": (cb / ca - 1.0) * 100.0, "why": None}


def next_week_end(
    d: str, weekly_dates: Optional[list[str]], is_trading: Callable[[str], bool]
) -> Optional[str]:
    """다음 주 마감일 — 주 마감 목록에 있으면 그다음 · 아니면 다음 ISO 주의 일정상 마지막 거래일."""
    if weekly_dates and d in weekly_dates:
        j = weekly_dates.index(d)
        if j + 1 < len(weekly_dates):
            return weekly_dates[j + 1]
    day = dt.date.fromisoformat(d)
    monday = day - timedelta(days=day.weekday()) + timedelta(days=7)
    return CU._scheduled_last(CU._iso(monday.isoformat()), is_trading)


def _closed_days(
    rows: list[Any], a: str, end: str, is_trading: Callable[[str], bool]
) -> set[str]:
    """a 뒤 ~ end 의 일정상 거래일 중 '마감 뒤 저장' 유효 종가가 있는 날."""
    return {
        r.date
        for r in rows
        if a < r.date <= end
        and is_trading(r.date)
        and close_at(rows, r.date)[0] is not None
    }


def week_so_far(ctx: Context, ticker: str, d: str) -> dict[str, Any]:
    """이번 주 지금까지 — 그 완료 주 마감 → 끝일까지 두 종목에 공통으로 마감 종가가 있는 마지막 날.

    없으면 end=None · why = no_prev_close(시작 = 직전 주 마감에 두 종목 마감 종가가 다 있지 않음 → 비교 불가 ·
    판정 2026-11-26 §2-3) · no_new_day(그 마감 뒤 저장한 거래일 자료 없음) · no_common_close(두 종목 모두
    마감 뒤 저장한 종가가 있는 날 없음 — 장중 저장값뿐이거나 한쪽만 있음)."""
    etf_rows = ctx.market["raw"].get(ticker, [])
    kdx_rows = ctx.market["kodex_full"]
    if close_at(etf_rows, d)[0] is None or close_at(kdx_rows, d)[0] is None:
        return {"end": None, "why": "no_prev_close"}
    common = _closed_days(etf_rows, d, ctx.end, ctx.is_trading) & _closed_days(
        kdx_rows, d, ctx.end, ctx.is_trading
    )
    if not common:
        newer = any(
            d < r.date <= ctx.end and ctx.is_trading(r.date)
            for r in (*etf_rows, *kdx_rows)
        )
        return {"end": None, "why": "no_common_close" if newer else "no_new_day"}
    e = max(common)
    return {
        "end": e,
        "etf": change(etf_rows, d, e),
        "kodex": change(kdx_rows, d, e),
        "why": None,
    }


def prev_week_close(d: str, is_trading: Callable[[str], bool]) -> Optional[str]:
    """d 가 속한 주 바로 앞 주의 일정상 마지막 거래일(거래일 없는 주는 건너뜀 · 다섯 주까지)."""
    day = dt.date.fromisoformat(d)
    monday = day - timedelta(days=day.weekday())
    for k in range(1, 6):
        last = CU._scheduled_last(
            CU._iso((monday - timedelta(days=7 * k)).isoformat()), is_trading
        )
        if last:
            return last
    return None


def this_week(ctx: Context, ticker: str) -> Optional[dict[str, Any]]:
    """끝일이 속한 주가 진행 중이면 그 주 관측(기간 미경과 행과 같은 모양) · 아니면 None.

    진행 중 = 그 주 일정상 마지막 거래일 > 끝일 · 또는 = 끝일인데 두 종목 중 하나가 장중 저장값.
    시작 = 거래 일정상 직전 완료 주 마감(판정 2026-11-26 §2-3) · 끝 = week_so_far."""
    sched = CU._scheduled_last(CU._iso(ctx.end), ctx.is_trading)
    if sched is None or sched < ctx.end:
        return None
    out: dict[str, Any] = {"state": "not_yet", "from": None, "to": sched}
    if sched == ctx.end:
        whys = (
            close_at(ctx.market["raw"].get(ticker, []), ctx.end)[1],
            close_at(ctx.market["kodex_full"], ctx.end)[1],
        )
        if "intraday_close" not in whys:
            return None
        out["intraday"] = True
    start = prev_week_close(ctx.end, ctx.is_trading)
    if start is None:
        return None
    out["from"] = start
    out["sofar"] = week_so_far(ctx, ticker, start)
    return out


def after_move(ctx: Context, ticker: str, d: str) -> dict[str, Any]:
    """그 뒤 관측 — 그 마감 → 다음 주 마감(ETF · KODEX 200 각각) · 기간 미경과면 이번 주 지금까지(sofar)."""
    nxt = next_week_end(d, (ctx.build.get("weekly") or {}).get("dates"), ctx.is_trading)
    if nxt is None:
        return {"state": "no_schedule", "from": d, "to": None}
    if nxt > ctx.end:
        return {
            "state": "not_yet",
            "from": d,
            "to": nxt,
            "sofar": week_so_far(ctx, ticker, d),
        }
    etf_rows, kdx_rows = ctx.market["raw"].get(ticker, []), ctx.market["kodex_full"]
    etf = change(etf_rows, d, nxt)
    kodex = change(kdx_rows, d, nxt)
    ends = (close_at(etf_rows, nxt)[1], close_at(kdx_rows, nxt)[1])
    if nxt == ctx.end and "intraday_close" in ends:
        # 끝일이 다음 주 마감일인데 그날 값이 장중 저장 — 마감이 아직 오지 않음(자료 없음 아님)
        # · 그날 종가로 직접 본다(change 의 사유는 시작일 사유가 먼저라 쓰지 않음 · 반박 검토 F1)
        return {
            "state": "not_yet",
            "from": d,
            "to": nxt,
            "intraday": True,
            "sofar": week_so_far(ctx, ticker, d),
        }
    return {"state": "ok", "from": d, "to": nxt, "etf": etf, "kodex": kodex}


def open_week(row: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """표 마지막 행의 진행 주(이번 주 지금까지) — 기간 미경과 행 자체 또는 덧붙인 then · 없으면 None."""
    a = row["after"]
    if a["state"] == "not_yet":
        return a
    return a.get("then")
