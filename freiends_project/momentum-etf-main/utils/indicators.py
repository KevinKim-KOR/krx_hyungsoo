"""
기술적 지표 계산 함수 모음
- 이동평균 기반 점수 계산을 위한 공통 함수들
"""

import pandas as pd


def calculate_moving_average_signals(
    close_prices: pd.Series, moving_average_period: int
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    이동평균 기반 지표를 계산합니다.

    Args:
        close_prices: 종가 시리즈
        moving_average_period: 이동평균 기간

    Returns:
        tuple: (moving_average, buy_signal_active, consecutive_buy_days)
            - moving_average: 이동평균선
            - buy_signal_active: 이동평균 상회 여부 (close > ma)
            - consecutive_buy_days: 이동평균 상회 상태가 연속으로 유지된 일수
    """
    if close_prices is None:
        return pd.Series(dtype=float), pd.Series(dtype=bool), pd.Series(dtype=int)

    if len(close_prices) < moving_average_period:
        return pd.Series(dtype=float), pd.Series(dtype=bool), pd.Series(dtype=int)

    # MultiIndex 컬럼 처리 (성능 최적화)
    if isinstance(close_prices, pd.DataFrame):
        close_prices = close_prices.iloc[:, 0]

    # 이동평균 계산
    moving_average = close_prices.rolling(window=moving_average_period).mean()

    # 이동평균 상회 여부 (종가 > 이동평균)
    buy_signal_active = close_prices > moving_average

    # 이동평균 상회 상태가 연속으로 유지된 일수 계산
    consecutive_buy_days = (
        buy_signal_active.groupby((buy_signal_active != buy_signal_active.shift()).cumsum())
        .cumsum()
        .fillna(0)
        .astype(int)
    )

    return moving_average, buy_signal_active, consecutive_buy_days


def calculate_ma_score(
    close_prices: pd.Series,
    moving_average: pd.Series,
) -> pd.Series:
    """
    RANK(Moving Average Position Score) 점수를 계산합니다.

    Args:
        close_prices: 종가 시리즈
        moving_average: 이동평균 시리즈

    """
    from core.strategy.scoring import calculate_maps_score

    return calculate_maps_score(close_prices, moving_average)
