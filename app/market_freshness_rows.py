"""POC6-27 — 시장 흐름 자료별 최신성(국내 직전 거래일 대비 · 「오늘의 투자 점검」 확인 창용 · 읽기 전용).

설계자 판정(2026-11-09 · PLAN 판정 §3 Q4 · §4):
- 외국인 수급 · 원/달러 = 국내 직전 거래일(T-1 · `trading_day_lag.expected_previous_trading_day`)과 비교한다.
  KOSPI 화면 판정과 같은 함수 · 같은 달력(없는 해는 평일 기본)이다. 마지막 자료일 ≥ 기대일이면 최신(국내 휴장
  중의 더 최근 원/달러 값도 최신), 이전이면 늦음(그 사이 거래일 수). 원/달러는 런던 날짜 관측이라 '국내 T-1
  대비'라는 기준을 화면이 따로 밝힌다. 원천의 공표 · 수집 지연 원인은 추론하지 않는다.
- WTI 는 판정하지 않는다(VIX 의 미국 마감 · 1평일 허용 규칙을 쓰지 않음) — 관측일만 싣는다(`observed`).
- 자료 없음 · 날짜 깨짐 · 기대일을 정하지 못함 = '기준 확인 필요'(`check`).
DB 를 열지 않는다(마지막 자료일은 호출부가 이미 읽은 값을 넘긴다). 달력 파일만 읽는다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.market_briefing.calendar import load_calendar, parse_date
from app.trading_day_lag import expected_previous_trading_day, trading_days_ending

KR_T1_ITEMS = (("flows", "외국인 수급"), ("usdkrw", "원/달러"))
KST = timezone(timedelta(hours=9))


def _expected_basis(
    expected: Optional[str], calendar_dir: Optional[Path]
) -> Optional[str]:
    if expected is None:
        return None
    try:
        cal = load_calendar(calendar_dir)
    except Exception:  # noqa: BLE001 — 달력을 못 읽으면 평일 기본과 같다
        cal = None
    return (
        "calendar"
        if cal is not None and cal.covers(int(expected[:4]))
        else "weekday_fallback"
    )


def _kr_item(
    key: str,
    label: str,
    last: Optional[str],
    expected: Optional[str],
    calendar_dir: Optional[Path],
) -> dict:
    item = {
        "key": key,
        "label": label,
        "last_date": last,
        "expected": expected,
        "basis": "kr_t1",
        "state": "check",
        "behind": None,
        "reason": None,
    }
    if not last:
        item["reason"] = "자료 없음"
        return item
    last_d = parse_date(last)
    if last_d is None:
        item["reason"] = "날짜 확인 불가"
        return item
    if expected is None:
        item["reason"] = "기대 기준일 확인 불가"
        return item
    if last >= expected:
        item["state"] = "fresh"
        return item
    span = (date.fromisoformat(expected) - last_d).days
    days = trading_days_ending(expected, span, calendar_dir=calendar_dir)
    behind = sum(1 for d in days if d > last)
    item.update(
        state="late",
        behind=behind,
        reason=f"국내 직전 거래일 {expected} 대비 {behind}거래일 늦음",
    )
    return item


def build_freshness(
    *,
    today_kst: str,
    last_dates: dict[str, Optional[str]],
    calendar_dir: Optional[Path] = None,
) -> dict:
    """`last_dates` = {"flows": E, "usdkrw": E, "wti": E}(없으면 None) → 응답 `freshness` 칸."""
    try:
        expected = expected_previous_trading_day(today_kst, calendar_dir=calendar_dir)
    except Exception:  # noqa: BLE001 — 기대일을 못 정하면 '기준 확인 필요'
        expected = None
    items = [
        _kr_item(k, label, last_dates.get(k), expected, calendar_dir)
        for k, label in KR_T1_ITEMS
    ]
    items.append(
        {
            "key": "wti",
            "label": "WTI",
            "last_date": last_dates.get("wti"),
            "expected": None,
            "basis": "observed_only",
            "state": "observed",
            "behind": None,
            "reason": None,
        }
    )
    return {
        "today_kst": today_kst,
        "expected_kr": expected,
        "expected_kr_basis": _expected_basis(expected, calendar_dir),
        "items": items,
    }


def freshness_from_series(
    now: datetime,
    flows_e: Optional[str],
    fx: list,
    oil: list,
    calendar_dir: Optional[Path] = None,
) -> dict:
    """시장 흐름 조립부가 이미 읽은 자료(수급 E · 원/달러 · WTI 점)로 `freshness` 를 만든다."""
    return build_freshness(
        today_kst=now.astimezone(KST).date().isoformat(),
        last_dates={
            "flows": flows_e,
            "usdkrw": fx[-1][0] if fx else None,
            "wti": oil[-1][0] if oil else None,
        },
        calendar_dir=calendar_dir,
    )
