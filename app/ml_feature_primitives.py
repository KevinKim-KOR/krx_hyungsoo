"""ML 최소 데이터 레인 — 시계열 primitives (POC2 2026-06-08 / FIX r2).

지시문 §6.1 — feature 계산용 순수 함수. builder 와 분리해 단일 책임 + KS-10
near 진입 회피 (검증자 B-3 / B-6 FIX).

본 모듈은:
- `_PriceSeries` dataclass + `_build_series()` factory.
- 기간 N 수익률 / 일간 수익률 시퀀스 / 변동성 / drawdown / volume_ratio /
  excess vs KODEX200 계산 함수.

외부 의존 0 — 표준 statistics 만 사용. SQLite 접근 0.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

WINDOW_5 = 5
WINDOW_10 = 10
WINDOW_20 = 20


@dataclass(frozen=True)
class PriceSeries:
    """ticker 의 (date, close, volume) ASC 시계열."""

    ticker: str
    dates: list[str] = field(default_factory=list)
    closes: list[float] = field(default_factory=list)
    volumes: list[Optional[int]] = field(default_factory=list)
    # date → index 매핑 (asof 기준일 lookup 용).
    date_index: dict[str, int] = field(default_factory=dict)


def build_series(
    ticker: str, rows: list[tuple[str, float, Optional[int]]]
) -> PriceSeries:
    dates: list[str] = []
    closes: list[float] = []
    volumes: list[Optional[int]] = []
    for d, c, v in rows:
        dates.append(d)
        closes.append(c)
        volumes.append(v)
    return PriceSeries(
        ticker=ticker,
        dates=dates,
        closes=closes,
        volumes=volumes,
        date_index={d: i for i, d in enumerate(dates)},
    )


def return_pct(series: PriceSeries, idx: int, window: int) -> Optional[float]:
    """기간 N 거래일 수익률 (%)."""
    if idx - window < 0:
        return None
    prev = series.closes[idx - window]
    cur = series.closes[idx]
    if prev <= 0:
        return None
    return (cur / prev - 1.0) * 100.0


def daily_returns(series: PriceSeries, idx: int, window: int) -> list[float]:
    """[idx-window+1, idx] 구간의 일간 수익률 리스트 (window 길이). 부족하면 빈 리스트."""
    if idx - window < 0:
        return []
    out: list[float] = []
    for i in range(idx - window + 1, idx + 1):
        prev = series.closes[i - 1]
        cur = series.closes[i]
        if prev <= 0:
            return []
        out.append((cur / prev - 1.0) * 100.0)
    return out


def volatility_20d(series: PriceSeries, idx: int) -> Optional[float]:
    rets = daily_returns(series, idx, WINDOW_20)
    if len(rets) < 2:
        return None
    return statistics.stdev(rets)


def drawdown_20d(series: PriceSeries, idx: int) -> Optional[float]:
    if idx - (WINDOW_20 - 1) < 0:
        return None
    window_closes = series.closes[idx - (WINDOW_20 - 1) : idx + 1]  # noqa: E203
    peak = max(window_closes)
    if peak <= 0:
        return None
    return (series.closes[idx] / peak - 1.0) * 100.0


def distance_from_20d_high(series: PriceSeries, idx: int) -> Optional[float]:
    # drawdown 과 동일 정의 — 가독성 위해 alias.
    return drawdown_20d(series, idx)


def volume_ratio_20d(series: PriceSeries, idx: int) -> Optional[float]:
    if idx - (WINDOW_20 - 1) < 0:
        return None
    window = series.volumes[idx - (WINDOW_20 - 1) : idx + 1]  # noqa: E203
    valid = [v for v in window if v is not None and v > 0]
    if len(valid) < 2:
        return None
    cur = series.volumes[idx]
    if cur is None or cur <= 0:
        return None
    mean_v = statistics.fmean(valid)
    if mean_v <= 0:
        return None
    return cur / mean_v


def excess_vs_kodex200(
    etf_ret: Optional[float], kodex_ret: Optional[float]
) -> Optional[float]:
    if etf_ret is None or kodex_ret is None:
        return None
    return etf_ret - kodex_ret
