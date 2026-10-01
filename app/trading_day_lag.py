"""POC3-02D-OPS-01 C7 — 공용 거래일-lag helper.

적재된 최신일이 **기준일 직전 거래일보다 몇 거래일 뒤처졌나**를 잰다. 두 곳이
**같은 축**을 쓴다.

| 호출부 | 무엇을 재나 |
|---|---|
| `app/market_briefing/flow.py` | 08:00 기초지수 창 최신성 관문 |
| `app/market_benchmark_store.refresh_kospi_benchmark` | KOSPI 적재 source 정지 감지 |
| `app/api_market_topn_service.with_kospi_display` | KOSPI 화면 상태의 거래일 지연 (OPS-02 3-4) |

본체는 `flow._weekday_axis_before` · `_window_lag_trading_days` 에서 **그대로**
옮겼다(설계자 Q17 — store 가 flow 의 private helper 를 import 하지 않는다).
`flow.py` 는 옛 이름을 이 함수들에 묶어 둔다 — 역검증 스크립트 monkeypatch 와
기존 테스트가 그대로 동작한다.

**기준일 당일은 축에서 뺀다.** 당일 행을 lag 0 으로 볼지는 호출부가 정한다.

POC3-02D-OPS-03 — 기대 기준일(`expected_previous_trading_day`)과 거래일 날짜 창
(`trading_days_back` · `trading_window_dates`)을 여기에 둔다. 배치 · API · 화면이
**같은 함수**로 최신성을 판정한다(확정 계약 6 · 9).
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Collection, Optional, Sequence

from app.market_briefing.calendar import load_calendar, parse_date


def weekday_axis_before(today_kst: str, *, span_days: int) -> list[str]:
    """`today_kst` 직전 `span_days` 달력일 중 **평일만** 오름차순.

    snapshot 이 없는 연도에서 지연을 재기 위한 축이다. 공휴일을 모르므로 실제
    거래일보다 조금 많게 잡힐 수 있다 — 그만큼 지연 판정이 **보수적**이 된다
    (실제보다 더 오래된 것처럼 보여 stale 로 막힐 뿐, 오래된 값을 최신으로
    착각하지 않는다).
    """
    try:
        base = _date.fromisoformat(today_kst[:10])
    except ValueError:
        return []
    out = [base - timedelta(days=i) for i in range(span_days, 0, -1)]
    return [d.isoformat() for d in out if d.weekday() < 5]


def trading_axis_before(today_kst: str, *, calendar_dir: Optional[Path]) -> list[str]:
    """`today_kst` **미만** 거래일 축(오름차순).

    축은 거래일 Gate 와 **같은 우선순위**로 고른다(2026-09-13 사용자 정책).

    | 상황 | 축 |
    |---|---|
    | 캘린더가 그 연도를 덮음 | snapshot 거래일 |
    | 없음·손상·연도 미지원 | **평일 fallback** |
    """
    try:
        cal = load_calendar(calendar_dir)
    except Exception:  # noqa: BLE001
        cal = None

    if cal is not None and cal.covers(int(today_kst[:4])):
        return sorted(d for d in cal.days if d < today_kst)
    # 거래일 Gate 와 **같은 평일 fallback 축**을 쓴다(2026-09-13 사용자 정책).
    # 여기서만 캘린더를 요구하면 캘린더 없는 연도에 기초지수가 늘 stale 이
    # 되어 "평일이면 나머지 Gate 를 계속 평가한다" 는 정책이 깨진다.
    return weekday_axis_before(today_kst, span_days=90)


def lag_on_axis(latest: str, days: Sequence[str]) -> Optional[int]:
    """축의 마지막 날에서 `latest` 까지 거래일 수. 축에 없으면 `None`."""
    if not days or latest not in days:
        # 적재된 최신일이 축에 없다 — 지연을 못 재므로 쓰지 않는다.
        return None
    return len(days) - 1 - days.index(latest)


def window_lag_trading_days(
    latest: str, *, today_kst: str, calendar_dir: Optional[Path]
) -> Optional[int]:
    """적재된 최신 거래일이 **직전 거래일보다 몇 거래일 뒤처졌나**.

    축에서 최신일을 못 찾으면 `None` — 지연을 모르므로 쓰지 않는다(호출부가
    `stale` 로 막는다).
    """
    return lag_on_axis(
        latest, trading_axis_before(today_kst, calendar_dir=calendar_dir)
    )


def benchmark_lag_trading_days(
    as_of: Optional[str], *, today_kst: str, calendar_dir: Optional[Path]
) -> tuple[Optional[int], Optional[str]]:
    """유효 종가 마지막 날짜(`as_of`)의 거래일 lag 와 축의 마지막 날(`ref`).

    POC3-02D-OPS-01 C7 KOSPI 적재 감지(`market_benchmark_store`)의 계산을 **본문 그대로**
    옮겼다(POC3-02D-OPS-02 3-4 · 설계자 Q6 — 화면도 같은 값을 쓴다).

    축은 08:00 기초지수 최신성 관문과 같다(`today_kst` **미만** 거래일 · snapshot,
    없으면 평일 fallback). KODEX200 DB 축은 DB 가 같이 멈추면 lag 가 0 이 되는
    순환 결함이 있어 쓰지 않는다.

    - 축의 마지막 날 **이상**이면 lag 0 — 축이 기준일 당일을 빼므로, PC 수동
      갱신(`end_date=date.today()`)에서 당일 행이 오면 정상 자료가 stale 로
      오판된다.
    - lag 를 못 재면 `None`(호출부가 stale 로 본다) — 유효 종가 행 없음
      (`as_of=None`) · 파싱 불가 · 축보다 오래됨 · 축 안에 없는 과거 날짜(휴장일 등).
    """
    days = trading_axis_before(today_kst, calendar_dir=calendar_dir)
    ref = days[-1] if days else None
    # **먼저 형식을 본다.** `20260923` 같은 값은 문자열 비교로 축 끝보다 커
    # 보여 lag 0 으로 통과한다.
    if as_of is None or parse_date(as_of) is None:
        return None, ref
    if ref is not None and as_of >= ref:
        return 0, ref
    return lag_on_axis(as_of, days), ref


# ── POC3-02D-OPS-03 — 기대 기준일 · 거래일 날짜 창 ─────────────────────────────
#
# 확정 계약 6 — 국내 최신성은 lag 숫자가 아니라
# `actual_basis_date == expected_previous_trading_day` 로 판정한다.
# 확정 계약 5 — 5일 · 20일은 저장 행 위치가 아니라 **거래일 날짜**로 정한다.
#
# 날짜마다 그 **연도**를 캘린더가 덮으면 캘린더, 아니면 평일로 거래일을 가린다.
# 연말 · 연초 창이 두 해에 걸쳐도 해마다 맞는 축을 쓴다(위 `trading_axis_before`
# 는 기준일 연도 하나로 축 전체를 고른다 — 그 함수는 바꾸지 않는다).

# 거슬러 올라가는 달력일 상한. 설 · 추석 연휴를 넉넉히 넘는다.
_WALK_LIMIT_DAYS = 60


def _trading_day_test(calendar_dir: Optional[Path]):
    """`date` → 거래일 여부. 캘린더는 한 번만 읽는다."""
    try:
        cal = load_calendar(calendar_dir)
    except Exception:  # noqa: BLE001
        cal = None

    def _is_trading(d: _date) -> bool:
        if cal is not None and cal.covers(d.year):
            return d.isoformat() in cal.days
        return d.weekday() < 5

    return _is_trading


def is_trading_day(date_kst: str, *, calendar_dir: Optional[Path]) -> bool:
    """`date_kst` 가 거래일인가. 읽을 수 없는 날짜는 `False`."""
    d = parse_date(date_kst)
    return d is not None and _trading_day_test(calendar_dir)(d)


def expected_previous_trading_day(
    today_kst: str, *, calendar_dir: Optional[Path]
) -> Optional[str]:
    """`today_kst` **직전** 거래일(T-1). 오늘은 넣지 않는다.

    그해 캘린더가 있으면 캘린더, 없으면 평일 fallback — 평일 휴장 다음 날에는
    휴장일이 T-1 로 잡혀 국내 구역이 생략된다(보수적 · 오래된 값을 최신으로 보지
    않는다). 읽을 수 없는 날짜 · 상한 안에 거래일이 없으면 `None`.
    """
    base = parse_date(today_kst)
    if base is None:
        return None
    is_trading = _trading_day_test(calendar_dir)
    for i in range(1, _WALK_LIMIT_DAYS + 1):
        d = base - timedelta(days=i)
        if is_trading(d):
            return d.isoformat()
    return None


def trading_days_ending(
    anchor_date: str, count: int, *, calendar_dir: Optional[Path]
) -> list[str]:
    """`anchor_date` **이하** 거래일 `count` 개(오름차순 · anchor 가 거래일이면 포함).

    상한 안에서 `count` 개를 못 모으면 모은 만큼만 돌려준다 — 호출부가 길이로
    판정한다. 읽을 수 없는 날짜면 `[]`.
    """
    base = parse_date(anchor_date)
    if base is None or count <= 0:
        return []
    is_trading = _trading_day_test(calendar_dir)
    out: list[str] = []
    limit = _WALK_LIMIT_DAYS + count * 3
    for i in range(0, limit + 1):
        d = base - timedelta(days=i)
        if is_trading(d):
            out.append(d.isoformat())
            if len(out) == count:
                break
    return sorted(out)


def trading_days_back(
    anchor_date: str, n: int, *, calendar_dir: Optional[Path]
) -> Optional[str]:
    """`anchor_date` 에서 **거래일 `n` 개 전** 날짜. `n=0` 이면 anchor 자신.

    anchor 가 거래일이 아니면 `None` — 휴장일에서 센 '5거래일 전' 은 계약의
    5거래일이 아니다. 거래일을 다 못 모아도 `None`(더 오래된 날로 밀지 않는다).
    """
    if n < 0 or not is_trading_day(anchor_date, calendar_dir=calendar_dir):
        return None
    days = trading_days_ending(anchor_date, n + 1, calendar_dir=calendar_dir)
    if len(days) != n + 1 or days[-1] != anchor_date:
        return None
    return days[0]


def unconfirmed_days(
    days: Sequence[str], stored: Collection[str], *, calendar_dir: Optional[Path]
) -> tuple[str, ...]:
    """캘린더가 그 **연도**를 덮지 않아 평일로 거래일로 친 날 가운데 저장되지 않은 날.

    그런 날은 휴장일인지 적재 누락인지 모른다 — 휴장일이면 그 창의 5 · 20거래일
    셈이 하루 틀어진다(4 · 19일을 5 · 20일로 보고). 호출부가 창을 fail-closed
    한다(확정 계약 5). 캘린더가 덮는 해의 날짜는 여기서 보지 않는다.
    """
    try:
        cal = load_calendar(calendar_dir)
    except Exception:  # noqa: BLE001
        cal = None
    out: list[str] = []
    for day in days:
        d = parse_date(day)
        if d is None or (cal is not None and cal.covers(d.year)):
            continue
        if day not in stored:
            out.append(day)
    return tuple(out)


def trading_window_dates(
    latest: str, *, calendar_dir: Optional[Path], lookbacks: Sequence[int] = (5, 20)
) -> Optional[tuple[str, ...]]:
    """`(latest, latest 의 5거래일 전, 20거래일 전)` — **거래일 날짜 기준**.

    저장 행 순서를 보지 않는다(확정 계약 5). 하나라도 못 정하면 `None`.
    """
    out: list[str] = [latest]
    for n in lookbacks:
        d = trading_days_back(latest, n, calendar_dir=calendar_dir)
        if d is None:
            return None
        out.append(d)
    return tuple(out)


__all__ = [
    "benchmark_lag_trading_days",
    "expected_previous_trading_day",
    "is_trading_day",
    "lag_on_axis",
    "trading_axis_before",
    "trading_days_back",
    "trading_days_ending",
    "trading_window_dates",
    "unconfirmed_days",
    "weekday_axis_before",
    "window_lag_trading_days",
]
