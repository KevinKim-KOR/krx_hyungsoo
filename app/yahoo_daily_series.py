"""POC6-01 — Yahoo 차트 일봉(원/달러 `KRW=X` · WTI `CL=F`)의 좁은 읽기 어댑터.

FDR 이 쓰는 것과 같은 주소(`query2.finance.yahoo.com/v8/finance/chart`)를 읽되, FDR 처럼 UTC 날짜로
자르지 않고 **원시 timestamp 를 공급자 시간대(`meta.exchangeTimezoneName`)로 바꾼 현지 날짜**를 쓴다
(과거 각 시점의 서머타임은 `zoneinfo` 가 적용 · 일괄 +1 · 요일 맞추기 보정 없음 · PLAN 판정 §2).

완료된 일봉만 돌려준다(PLAN §9-1 · 판정 §3):
- 공급자의 '오늘 구간'(`meta.currentTradingPeriod.regular.start` 의 현지 날짜) 이상인 봉 = 진행 중 → 제외.
- 현지 자정이 아닌 줄(현재가 줄) · 종가 없는 줄 → 제외(같은 날짜를 정상 종가로 중복 저장하지 않음).
- 시간대 · 오늘 구간이 없으면 날짜 의미를 확정할 수 없으므로 실패(다른 자료원으로 대체하지 않음).

값은 한국 15:30 값이 아니다(같은 날짜 라벨이어도 관측 시각이 다르다).
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import requests

CHART_URL = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_TIMEOUT_S = 20  # 기존 FDR 요청 대기 상한과 같다
_UA = {"user-agent": "Mozilla/5.0 AppleWebKit/537.36"}
_default_get = requests.get  # 시험은 이 속성을 막는다(실제 Yahoo 호출 금지)


class YahooSeriesError(Exception):
    """날짜 의미 · 응답 형식을 확정할 수 없음(저장하지 않는다)."""


def fetch_completed_daily(
    symbol: str,
    start: date,
    *,
    now_utc: datetime,
    http_get: Optional[Callable] = None,
) -> list[tuple[str, float]]:
    """`start` 이후 완료된 일봉 [(현지 날짜 YYYY-MM-DD, 종가)] — 날짜순 · 같은 날짜 1개."""
    get = http_get or _default_get
    p1 = int(
        datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp()
    )
    p2 = int(now_utc.timestamp())
    r = get(
        CHART_URL.format(symbol=symbol),
        params={"period1": p1, "period2": p2, "interval": "1d"},
        headers=_UA,
        timeout=REQUEST_TIMEOUT_S,
    )
    r.raise_for_status()
    try:
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        tz = ZoneInfo(meta["exchangeTimezoneName"])
        today_start = (
            datetime.fromtimestamp(
                meta["currentTradingPeriod"]["regular"]["start"], timezone.utc
            )
            .astimezone(tz)
            .date()
        )
        stamps = res.get("timestamp") or []
        closes = res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise YahooSeriesError(
            f"{symbol} 응답 형식 · 시간대 확인 불가: {type(e).__name__}"
        ) from e
    if len(stamps) != len(closes):
        raise YahooSeriesError(f"{symbol} 시각 · 값 개수 다름")
    out: dict[str, float] = {}
    for ts, c in zip(stamps, closes):
        loc = datetime.fromtimestamp(ts, timezone.utc).astimezone(tz)
        if c is None or (loc.hour, loc.minute, loc.second) != (0, 0, 0):
            continue  # 종가 없음 · 현재가 줄
        if loc.date() >= today_start or loc.date() < start:
            continue  # 진행 중 · 요청 범위 밖
        if loc.weekday() >= 5:
            continue  # 주말 날짜 봉 = 완료 일봉 아님(두 계열 저장 이력 0건 · 일요일 저녁 선물 잠정 봉 방지)
        v = float(c)
        if not math.isfinite(v):
            raise YahooSeriesError(f"{symbol} {loc.date()} 값이 수가 아님")
        key = loc.date().isoformat()
        if key in out:
            raise YahooSeriesError(f"{symbol} {key} 같은 날짜 봉이 둘")
        out[key] = v
    return sorted(out.items())
