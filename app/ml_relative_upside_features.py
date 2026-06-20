"""ML 축1 (후보 ETF 상대상승 참고점수 v0) — feature 계산.

본 모듈은 SQLite `etf_daily_price` 시계열을 read-only 로 읽어 다음 feature 를
계산한다:
  - 5/10/20거래일 수익률 (compute_topn 의 selected_return_pct 와 별도 계산)
  - 5/10/20거래일 KODEX200 대비 초과수익 (percentage point)
  - 20거래일 고점 대비 하락폭 (drawdown_20d) — **본 STEP 의 첫 추가 factor**

drawdown_20d 정의:
    close / rolling_20d_high - 1  (음수)
    - 현재가 90, 직전 20거래일 고점 100 → -10.0% (-0.10)
    - 0.0% : 최근 20일 고점 부근
    - 값이 더 작을수록 (음수 절대값 큼) 고점 대비 더 많이 하락.

학습용 target (build_targets):
    이후 20거래일 KODEX200 대비 상대수익
    = (future_close_+20d / current_close - 1) - (kodex_+20d / kodex_now - 1)

본 모듈은 ML 모델을 호출하지 않는다. feature/target 만 생성한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

KODEX200_TICKER = "069500"

# 거래일 lookback 상수 (지시문 §5.1).
RETURN_LOOKBACK_5D = 5
RETURN_LOOKBACK_10D = 10
RETURN_LOOKBACK_20D = 20

# 추가 factor (지시문 §5.2).
DRAWDOWN_LOOKBACK_20D = 20

# 학습 target horizon (지시문 §6.2).
FUTURE_HORIZON_20D = 20


@dataclass
class CandidateFeatureRow:
    """기준일 (asof_index) 의 단일 ETF feature row.

    asof_index 는 ticker 시계열에서 종가 위치 index. 학습/추론 모두 동일 정의.
    None 인 field 는 missing 으로 처리되어 학습/추론에서 제외된다.
    """

    ticker: str
    asof_index: int
    asof_date: str
    close: float
    return_5d: Optional[float]
    return_10d: Optional[float]
    return_20d: Optional[float]
    excess_return_5d: Optional[float]
    excess_return_10d: Optional[float]
    excess_return_20d: Optional[float]
    drawdown_20d: Optional[float]
    # 학습용 future target — 추론 시점에는 None (아직 미래 데이터 없음).
    future_excess_return_20d: Optional[float] = None


def _pct_return(close_now: float, close_base: float) -> Optional[float]:
    """단순 수익률 (소수 표현 — 0.05 = +5%). 입력 invalid 면 None."""
    if close_base is None or close_now is None:
        return None
    if close_base <= 0 or close_now <= 0:
        return None
    return float(close_now) / float(close_base) - 1.0


def _drawdown_from_peak(close_now: float, rolling_high: float) -> Optional[float]:
    """drawdown = close / peak - 1 (음수). peak <= 0 이면 None."""
    if rolling_high is None or close_now is None:
        return None
    if rolling_high <= 0 or close_now <= 0:
        return None
    return float(close_now) / float(rolling_high) - 1.0


def build_kodex200_series(
    prices_by_ticker: dict[str, list[tuple[str, float]]],
) -> dict[str, float]:
    """KODEX200 (069500) 시계열을 date → close map 으로 변환.

    prices_by_ticker 에 KODEX200 가 없으면 빈 dict (호출자가 excess_return 을
    None 으로 처리).
    """
    series = prices_by_ticker.get(KODEX200_TICKER)
    if not series:
        return {}
    return {date: close for date, close in series}


def build_feature_rows_for_ticker(
    ticker: str,
    history: list[tuple[str, float]],
    kodex_map: dict[str, float],
    *,
    include_future_target: bool,
) -> list[CandidateFeatureRow]:
    """단일 ticker 의 시계열 → 모든 가능한 asof_index 의 feature row 목록.

    history 는 (date, close) 튜플의 date ASC 정렬 리스트. drawdown 은 최근
    20거래일 window 의 high 사용 (history index i 시점에 i-19~i 까지 max).

    include_future_target=True 면 future_excess_return_20d 도 채운다 (학습용).
    False 면 None 유지 (추론용 — 현재 시점에서는 미래 데이터 차단).

    학습 데이터 누수 방지 (지시문 AC-3): future target 은 history index +20 이
    존재할 때만 계산. 모든 feature 는 asof_index 시점까지의 데이터만 사용.
    """
    rows: list[CandidateFeatureRow] = []
    n = len(history)
    # 최소 lookback 20일 필요.
    for i in range(RETURN_LOOKBACK_20D, n):
        date_i, close_i = history[i]
        if close_i is None or close_i <= 0:
            continue

        # 수익률 (5/10/20일).
        ret_5d = _pct_return(close_i, history[i - RETURN_LOOKBACK_5D][1])
        ret_10d = _pct_return(close_i, history[i - RETURN_LOOKBACK_10D][1])
        ret_20d = _pct_return(close_i, history[i - RETURN_LOOKBACK_20D][1])

        # KODEX200 동일 시점 수익률.
        kodex_now = kodex_map.get(date_i)
        kodex_5d_base = kodex_map.get(history[i - RETURN_LOOKBACK_5D][0])
        kodex_10d_base = kodex_map.get(history[i - RETURN_LOOKBACK_10D][0])
        kodex_20d_base = kodex_map.get(history[i - RETURN_LOOKBACK_20D][0])
        kodex_ret_5d = _pct_return(kodex_now, kodex_5d_base) if kodex_now else None
        kodex_ret_10d = _pct_return(kodex_now, kodex_10d_base) if kodex_now else None
        kodex_ret_20d = _pct_return(kodex_now, kodex_20d_base) if kodex_now else None

        # 초과수익 (percentage point — 비율 차이).
        excess_5d = (
            ret_5d - kodex_ret_5d
            if (ret_5d is not None and kodex_ret_5d is not None)
            else None
        )
        excess_10d = (
            ret_10d - kodex_ret_10d
            if (ret_10d is not None and kodex_ret_10d is not None)
            else None
        )
        excess_20d = (
            ret_20d - kodex_ret_20d
            if (ret_20d is not None and kodex_ret_20d is not None)
            else None
        )

        # drawdown_20d — 직전 20거래일 (i-19 ~ i) high 대비 현재 종가.
        # 정의: close_i / rolling_high - 1 (음수).
        window_start = max(0, i - DRAWDOWN_LOOKBACK_20D + 1)
        window = history[window_start : i + 1]  # noqa: E203
        rolling_high = max(
            (c for _, c in window if c is not None and c > 0), default=None
        )
        drawdown_20d = (
            _drawdown_from_peak(close_i, rolling_high)
            if rolling_high is not None
            else None
        )

        # 학습용 future target — 지시문 §6.2.
        future_target: Optional[float] = None
        if include_future_target and i + FUTURE_HORIZON_20D < n:
            close_future = history[i + FUTURE_HORIZON_20D][1]
            date_future = history[i + FUTURE_HORIZON_20D][0]
            future_ret = _pct_return(close_future, close_i)
            kodex_future = kodex_map.get(date_future)
            kodex_future_ret = (
                _pct_return(kodex_future, kodex_now)
                if (kodex_now and kodex_future)
                else None
            )
            if future_ret is not None and kodex_future_ret is not None:
                future_target = future_ret - kodex_future_ret

        rows.append(
            CandidateFeatureRow(
                ticker=ticker,
                asof_index=i,
                asof_date=date_i,
                close=float(close_i),
                return_5d=ret_5d,
                return_10d=ret_10d,
                return_20d=ret_20d,
                excess_return_5d=excess_5d,
                excess_return_10d=excess_10d,
                excess_return_20d=excess_20d,
                drawdown_20d=drawdown_20d,
                future_excess_return_20d=future_target,
            )
        )
    return rows


def is_complete_for_training(row: CandidateFeatureRow) -> bool:
    """학습용 row 가 모든 feature + target 을 가지고 있는가."""
    return all(
        v is not None
        for v in (
            row.return_5d,
            row.return_10d,
            row.return_20d,
            row.excess_return_5d,
            row.excess_return_10d,
            row.excess_return_20d,
            row.drawdown_20d,
            row.future_excess_return_20d,
        )
    )


def is_complete_for_inference(row: CandidateFeatureRow) -> bool:
    """추론용 row 가 모든 feature 를 가지고 있는가. future target 은 무시."""
    return all(
        v is not None
        for v in (
            row.return_5d,
            row.return_10d,
            row.return_20d,
            row.excess_return_5d,
            row.excess_return_10d,
            row.excess_return_20d,
            row.drawdown_20d,
        )
    )


FEATURE_COLUMNS = (
    "return_5d",
    "return_10d",
    "return_20d",
    "excess_return_5d",
    "excess_return_10d",
    "excess_return_20d",
    "drawdown_20d",
)
