"""POC3-02D-OPS-01 C7 — 공용 거래일-lag helper.

적재된 최신일이 **기준일 직전 거래일보다 몇 거래일 뒤처졌나**를 잰다. 두 곳이
**같은 축**을 쓴다.

| 호출부 | 무엇을 재나 |
|---|---|
| `app/market_briefing/flow.py` | 08:00 기초지수 창 최신성 관문 |
| `app/market_benchmark_store.refresh_kospi_benchmark` | KOSPI 적재 source 정지 감지 |

본체는 `flow._weekday_axis_before` · `_window_lag_trading_days` 에서 **그대로**
옮겼다(설계자 Q17 — store 가 flow 의 private helper 를 import 하지 않는다).
`flow.py` 는 옛 이름을 이 함수들에 묶어 둔다 — 역검증 스크립트 monkeypatch 와
기존 테스트가 그대로 동작한다.

**기준일 당일은 축에서 뺀다.** 당일 행을 lag 0 으로 볼지는 호출부가 정한다.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from pathlib import Path
from typing import Optional, Sequence

from app.market_briefing.calendar import load_calendar


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


__all__ = [
    "lag_on_axis",
    "trading_axis_before",
    "weekday_axis_before",
    "window_lag_trading_days",
]
