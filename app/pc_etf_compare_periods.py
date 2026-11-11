"""POC6-28 — 「ETF 비교하기」 기간 · 기준값 · 가격 시점(순수 계산 · 조회 없음).

PLAN `docs/ai_plan/POC6/POC6_28_ETF_COMPARISON_SECTOR_AND_HOLDINGS_PLAN_V1.md` §3-1 · §3-6 · §3-7.

- 기간 수익률의 시작 행 규칙은 기존 `market_topn_helpers._compute_period` 와 같다(1일 = 바로 앞 행 ·
  그 밖 = 끝일 − 기간 일수 이후 첫 행). 공통 기간과 시작 · 끝이 같을 때만 '비교 가능'이다.
- 가격 시점은 끝일 행의 저장 시각(`fetched_at` → KST)으로 나눈다. 저장 시각은 저장 사실이며 시세
  관측 시각이 아니다. 종가라고 단정하지 않는다(판정 §4).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from app.market_topn_helpers import (
    DAILY_LOOKBACK_DAYS,
    ONE_MONTH_LOOKBACK_DAYS,
    THREE_MONTH_LOOKBACK_DAYS,
)
from app.pc_stored_drawdown import WINDOW as DD_WINDOW
from app.pc_stored_drawdown import compute_stored_drawdown
from app.reentry_review.prices import PriceRow

BASIS_DAYS = {
    "daily": DAILY_LOOKBACK_DAYS,
    "one_month": ONE_MONTH_LOOKBACK_DAYS,
    "three_month": THREE_MONTH_LOOKBACK_DAYS,
}
KST = timezone(timedelta(hours=9))
SESSION_CLOSE = (
    15,
    30,
)  # 정규장 마감(KST) — 마감 시간이 바뀌는 날은 구분하지 못한다(PLAN §3-7 한계)

STATE_INTRADAY = "intraday"  # 장중 저장값 · 잠정
STATE_AFTER_CLOSE = "after_close"  # 마감 뒤 저장(종가 단정 아님)
STATE_UNKNOWN = "unknown"  # 마감값 확인 필요

CRIT_OK = "ok"
CRIT_PERIOD_DIFFERS = "period_differs"
CRIT_MISSING = "missing"


def price_state(price_date: Optional[str], fetched_at: Optional[str]) -> dict[str, Any]:
    """끝일 행 한 개의 저장 상태(PLAN §3-7). 저장 시각은 저장 사실일 뿐 시세 관측 시각이 아니다."""
    out: dict[str, Any] = {
        "date": price_date,
        "state": STATE_UNKNOWN,
        "fetched_at_kst": None,
    }
    if not price_date or not isinstance(fetched_at, str) or not fetched_at.strip():
        return out
    try:
        day = date.fromisoformat(price_date)
        stamp = datetime.fromisoformat(fetched_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return out
    if stamp.tzinfo is None:
        return out  # 시간대 없는 시각은 KST 로 바꿀 수 없다
    kst = stamp.astimezone(KST)
    out["fetched_at_kst"] = kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    day_start = datetime(day.year, day.month, day.day, tzinfo=KST)
    close_at = day_start.replace(hour=SESSION_CLOSE[0], minute=SESSION_CLOSE[1])
    if kst < day_start:
        return out  # 가격 날짜보다 앞선 저장 시각 — 확인 필요
    out["state"] = STATE_INTRADAY if kst < close_at else STATE_AFTER_CLOSE
    return out


def summarize_states(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """여러 종목 끝일 상태 → 요약(장중 저장값 포함이면 잠정)."""
    c = Counter(s["state"] for s in states)
    intraday = sorted(
        s["fetched_at_kst"]
        for s in states
        if s["state"] == STATE_INTRADAY and s["fetched_at_kst"]
    )
    after = sorted(
        s["fetched_at_kst"]
        for s in states
        if s["state"] == STATE_AFTER_CLOSE and s["fetched_at_kst"]
    )
    return {
        "intraday_count": c.get(STATE_INTRADAY, 0),
        "after_close_count": c.get(STATE_AFTER_CLOSE, 0),
        "unknown_count": c.get(STATE_UNKNOWN, 0),
        "provisional": c.get(STATE_INTRADAY, 0) > 0,
        "intraday_fetched_min": intraday[0] if intraday else None,
        "intraday_fetched_max": intraday[-1] if intraday else None,
        "after_close_fetched_min": after[0] if after else None,
        "after_close_fetched_max": after[-1] if after else None,
    }


def period_window(
    valid_rows: Sequence[tuple[str, float]], end: str, lookback_days: int
) -> Optional[tuple[int, int]]:
    """(시작 · 끝 행 번호). 끝 = `end` 이하 마지막 유효 행. 시작 = 1일이면 바로 앞 행, 아니면
    (공통 끝일 − 기간 일수) 이후 첫 행 — 기존 `_compute_period` 와 같다. 계산할 수 없으면 None."""
    idx = [i for i, (d, _) in enumerate(valid_rows) if d <= end]
    if len(idx) < 2:
        return None
    last = idx[-1]
    if lookback_days == DAILY_LOOKBACK_DAYS:
        return (last - 1, last)
    target = (date.fromisoformat(end) - timedelta(days=lookback_days)).isoformat()
    first = next((i for i in idx if valid_rows[i][0] >= target), None)
    if first is None or first == last:
        return None
    return (first, last)


def period_value(
    valid_rows: Sequence[tuple[str, float]], end: str, lookback: int
) -> Optional[dict[str, Any]]:
    w = period_window(valid_rows, end, lookback)
    if w is None:
        return None
    (sd, sc), (ed, ec) = valid_rows[w[0]], valid_rows[w[1]]
    return {
        "raw": (ec / sc - 1.0) * 100.0,
        "start": sd,
        "end": ed,
        "start_close": sc,
        "end_close": ec,
    }


def criterion_from_period(
    v: Optional[dict[str, Any]], common: Optional[tuple[str, str]]
) -> dict[str, Any]:
    if v is None:
        return {
            "status": CRIT_MISSING,
            "value": None,
            "start": None,
            "end": None,
            "reason": "no_period",
        }
    if common is None:
        # 비교 기준(069500) 구간을 못 정하면 '기간 다름'이 아니라 비교할 수 없다(독립 검토 LOW).
        return {
            "status": CRIT_MISSING,
            "value": None,
            "start": v["start"],
            "end": v["end"],
            "reason": "kodex_window_unknown",
        }
    ok = (v["start"], v["end"]) == common
    return {
        "status": CRIT_OK if ok else CRIT_PERIOD_DIFFERS,
        "value": round(v["raw"], 4),
        "start": v["start"],
        "end": v["end"],
        "start_close": v["start_close"],
        "end_close": v["end_close"],
        "reason": None if ok else "period_differs",
    }


def drawdown_of(rows: Sequence[PriceRow], end_date: Optional[str]) -> dict[str, Any]:
    window = [r for r in rows if end_date and r.date <= end_date][-DD_WINDOW:]
    return compute_stored_drawdown(list(window), end_date=end_date).model_dump()
