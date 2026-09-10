"""POC3-OPS-02B-1 — benchmark 자기 기준일·최신성·날짜 기준 수익률.

`DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY` 대응. 설계자 확정 최소 계약 중
계산·표시 층위(②~⑥)를 담당한다. 운영 갱신(①)은 OCI 배치가 맡는다.

| # | 계약 |
|---|---|
| ② | 각 benchmark 가 **자신의 `as_of_date`** 를 유지 |
| ③ | 날짜를 버린 **위치 인덱스가 아니라 실제 거래일 기준** 수익률 |
| ④ | **최신성 1거래일을 벗어나면 수익률 미산출** |
| ⑤ | stale benchmark 를 다른 최신 `market_context.asof` 로 표시하지 않음 |
| ⑥ | 일부만 실패하면 **실패한 블록만 제외** |

기존 `market_regime._return_n_days_back` 는 `closes[-1]` 과 `closes[-(n+1)]` 의
비율이라 **날짜를 보지 않는다.** 계열에 결측일이 있으면 "20거래일 전" 이 실제
20거래일 전이 아니고, 결과 dict 에 자기 기준일이 없어 상위 `asof` 로 표시된다.
이 모듈은 **거래일 축 위의 날짜로** 기준일을 찾고 그 날짜의 값만 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

# 최신성 허용 폭 — 축의 마지막 거래일로부터 몇 거래일까지 허용하는가.
MAX_STALE_TRADING_DAYS = 1


@dataclass(frozen=True)
class BenchmarkFreshness:
    """benchmark 한 종류의 기준일·지연·판정."""

    as_of_date: Optional[str]
    reference_date: Optional[str]
    lag_trading_days: Optional[int]
    is_fresh: bool
    reason: Optional[str]

    def to_dict(self) -> dict:
        return {
            "as_of_date": self.as_of_date,
            "reference_date": self.reference_date,
            "lag_trading_days": self.lag_trading_days,
            "is_fresh": self.is_fresh,
            "reason": self.reason,
        }


def _date_only(value: str) -> str:
    return (value or "")[:10]


def evaluate_freshness(
    history: Sequence[tuple[str, float]],
    *,
    trading_days: Sequence[str],
    max_stale: int = MAX_STALE_TRADING_DAYS,
) -> BenchmarkFreshness:
    """benchmark 자기 기준일과 거래일 축 대비 지연을 판정한다.

    `trading_days` 는 오름차순 거래일 축(KODEX200 기준). 축이 없으면 판정 불가로
    두고 **`is_fresh=False`** 를 돌려준다 — 모르면 쓰지 않는다.
    """
    axis = [_date_only(d) for d in trading_days if d]
    ref = axis[-1] if axis else None
    dates = sorted({_date_only(d) for d, c in history if d and c and c > 0})
    as_of = dates[-1] if dates else None

    if as_of is None:
        return BenchmarkFreshness(None, ref, None, False, "no_data")
    if ref is None:
        return BenchmarkFreshness(as_of, None, None, False, "no_trading_day_axis")
    if as_of not in axis:
        # 축에 없는 날짜 — 거래일이 아니거나 축보다 미래다. 지연을 셀 수 없다.
        return BenchmarkFreshness(as_of, ref, None, False, "as_of_not_on_axis")

    lag = (len(axis) - 1) - axis.index(as_of)
    if lag > max_stale:
        return BenchmarkFreshness(as_of, ref, lag, False, "stale")
    return BenchmarkFreshness(as_of, ref, lag, True, None)


def return_by_trading_days(
    history: Sequence[tuple[str, float]],
    *,
    trading_days: Sequence[str],
    lookback: int,
    as_of_date: Optional[str] = None,
) -> Optional[float]:
    """`as_of_date` 에서 **거래일 축으로 `lookback` 만큼 뒤** 날짜와의 % 변화.

    기준일·비교일 **둘 다 그 날짜의 실제 값**이 있어야 한다. 하나라도 없으면
    `None` — 더 오래된 값으로 대체하지 않는다(OPS-02A §4.7 과 같은 원칙).
    """
    if lookback <= 0:
        return None
    axis = [_date_only(d) for d in trading_days if d]
    by_date = {_date_only(d): c for d, c in history if d and c and c > 0}
    anchor = _date_only(as_of_date) if as_of_date else None
    if anchor is None:
        known = [d for d in axis if d in by_date]
        anchor = known[-1] if known else None
    if anchor is None or anchor not in axis or anchor not in by_date:
        return None
    i = axis.index(anchor)
    j = i - lookback
    if j < 0:
        return None
    base_date = axis[j]
    base = by_date.get(base_date)
    latest = by_date.get(anchor)
    if not base or base <= 0 or not latest or latest <= 0:
        return None
    return (latest / base - 1.0) * 100.0


__all__ = [
    "MAX_STALE_TRADING_DAYS",
    "BenchmarkFreshness",
    "evaluate_freshness",
    "return_by_trading_days",
]
