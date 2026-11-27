"""흐름 그래프 자료(V2 판정 2026-11-25 Q6 · §3) — 그림은 page_chart.

```text
기준   표의 첫 완료 주 마감 = 0% · 끝일까지 일정상 거래일마다 이 ETF · KODEX 200 누적 종가 변화
값     history.close_at(유효 종가 · '마감 뒤 저장')만 — 표 · 복사문의 '이번 주 지금까지'와 같은 종가
빠짐   값이 없는 날은 None 과 사유(no_price · intraday_close · unknown_close · no_base = 기준일 종가 없음 ·
       after_common = 두 종목 공통 마감 종가 마지막 날 뒤라 그리지 않음 · pair_no_base = 다른 종목의
       기준일 종가가 없어 비교선을 그리지 않음)
표식   표의 완료 주 마감마다 그때 복원(seen) · 그 뒤 거래 일정상 완료 주 마감(건너뛴 주 · 끝난 주 · 주말 끝일의
       그 주 마감)도 복원 · 진행 주면 끝일 = 지금 순위(now · progress 에 시작 · 예정 마감)
```
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import Any, Mapping, Optional

from app.candidate_compare import current as CU
from app.weekly_decision.history import Context, seen_at
from app.weekly_decision.observe import close_at, open_week


def flow(
    ctx: Context, ticker: str, rows: list[Mapping[str, Any]], item: Mapping[str, Any]
) -> dict[str, Any]:
    """흐름 그래프 자료 — 첫 완료 주 마감 = 0% · 끝일까지 일정상 거래일마다 두 종목 누적 변화.

    값은 close_at(마감 뒤 저장 유효 종가)만 · 빠진 날은 None 과 사유(no_base = 기준일 종가 없음).
    표식 = 표의 완료 주 마감마다 그때 복원(seen) · 진행 주면 끝일 지금 순위 · 끝난 주면 W0 복원."""
    if not rows:
        return {"state": "unavailable"}
    base = rows[0]["date"]
    days: list[str] = []
    day = dt.date.fromisoformat(base)
    last = dt.date.fromisoformat(ctx.end)
    while day <= last:
        if ctx.is_trading(day.isoformat()):
            days.append(day.isoformat())
        day += timedelta(days=1)

    def series(rs: list[Any]) -> list[tuple[Optional[float], Optional[str]]]:
        c0, _ = close_at(rs, base)
        out: list[tuple[Optional[float], Optional[str]]] = []
        for dd in days:
            c, why = close_at(rs, dd)
            if c0 is None:
                out.append((None, "no_base"))
            elif c is None:
                out.append((None, why))
            else:
                out.append(((c / c0 - 1.0) * 100.0, None))
        return out

    e = series(ctx.market["raw"].get(ticker, []))
    k = series(ctx.market["kodex_full"])
    points = [
        {
            "date": dd,
            "etf": e[i][0],
            "etf_why": e[i][1],
            "kodex": k[i][0],
            "kodex_why": k[i][1],
        }
        for i, dd in enumerate(days)
    ]
    marks = [{"date": r["date"], "kind": "week", "seen": r["seen"]} for r in rows]
    a = open_week(rows[-1])
    progress = None
    if a is not None:
        progress = {
            "from": a["from"],
            "to": a["to"],
            "intraday": bool(a.get("intraday")),
            "sofar_end": a["sofar"]["end"],
        }
    # 거래 일정상 이미 끝난 주의 마감일(진행 주의 예정 마감일은 뺌) — 그날 결측 = '완료 주 마감 종가 없음'
    open_to = progress["to"] if progress else None
    week_closes = [
        dd
        for dd in days
        if dd != open_to and CU._scheduled_last(CU._iso(dd), ctx.is_trading) == dd
    ]
    # 표 마지막 행 뒤의 완료 주 마감(주 마감 규칙이 건너뛴 주 · 끝난 주의 W0 · 주말 끝일의 그 주 마감)에도
    # 그때 순위 표식(복원) — 진행 주면 그 시작일까지만(반박 검토 F2 · 판정 §2-2 · §2-4)
    upto = progress["from"] if progress else ctx.end
    for dd in week_closes:
        if rows[-1]["date"] < dd <= upto:
            marks.append(
                {"date": dd, "kind": "week", "seen": seen_at(ctx.restore(dd), ticker)}
            )
    if progress is not None:
        now_seen = {
            "state": "ranked",
            "rank": item["rank"],
            "top30": item["top30"],
            "price_state": item["state"],
        }
        marks.append({"date": ctx.end, "kind": "now", "seen": now_seen})
    both = [
        p["date"] for p in points if p["etf"] is not None and p["kodex"] is not None
    ]
    # 그래프 관측 끝일 = 두 종목 공통 마감 종가 마지막 날(판정 2026-11-26 §2-1 · 검증 F15) — 그 뒤 한 종목 값은
    # 그리지 않는다(표 · 복사문 '이번 주 지금까지'와 같은 끝일) · 공통 날이 없으면 어느 선도 그리지 않음
    common_last = both[-1] if both else None
    # 한 종목의 기준일 종가가 없어 공통 날이 없으면 다른 종목 선도 '비교할 기준일 종가 없음'으로 그리지 않음
    no_base = any(
        all(p[k + "_why"] == "no_base" for p in points) for k in ("etf", "kodex")
    )
    cut_why = "pair_no_base" if common_last is None and no_base else "after_common"
    for p in points:
        if common_last is None or p["date"] > common_last:
            for key in ("etf", "kodex"):
                if p[key] is not None:
                    p[key], p[key + "_why"] = None, cut_why
    return {
        "state": "ok",
        "base": base,
        "end": ctx.end,
        "points": points,
        "marks": marks,
        "progress": progress,
        "last": common_last,
        "week_closes": week_closes,
    }
