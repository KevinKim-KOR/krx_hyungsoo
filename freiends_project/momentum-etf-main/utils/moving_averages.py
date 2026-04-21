"""
이동평균 계산 유틸리티 함수
- SMA, EMA, WMA, DEMA, TEMA, HMA, ALMA 지원
"""

import numpy as np
import pandas as pd

ALMA_OFFSET = 0.85
ALMA_SIGMA = 6.0


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Simple Moving Average (단순 이동평균)

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        SMA 시리즈
    """
    return prices.rolling(window=period, min_periods=1).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """
    Exponential Moving Average (지수 이동평균)

    최근 데이터에 지수적으로 더 높은 가중치를 부여합니다.

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        EMA 시리즈
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_wma(prices: pd.Series, period: int) -> pd.Series:
    """
    Weighted Moving Average (가중 이동평균)

    선형적으로 가중치를 부여합니다 (최근일=N, 전일=N-1, ..., N일전=1)

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        WMA 시리즈
    """
    weights = np.arange(1, period + 1)

    def weighted_mean(x):
        n = len(x)
        w = weights[-n:]  # 데이터 길이에 맞춰 가중치 뒤쪽(최근)부터 사용
        return np.dot(x, w) / w.sum()

    return prices.rolling(window=period, min_periods=1).apply(weighted_mean, raw=True)


def calculate_tema(prices: pd.Series, period: int) -> pd.Series:
    """
    Triple Exponential Moving Average (삼중 지수 이동평균)

    EMA를 3번 적용하여 더욱 빠른 반응을 제공합니다.
    TEMA = 3 * EMA - 3 * EMA(EMA) + EMA(EMA(EMA))

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        TEMA 시리즈
    """
    ema1 = prices.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    return 3 * ema1 - 3 * ema2 + ema3


def calculate_dema(prices: pd.Series, period: int) -> pd.Series:
    """
    Double Exponential Moving Average (이중 지수 이동평균)

    EMA의 EMA를 사용하여 지연(lag)을 감소시킵니다.
    DEMA = 2 * EMA - EMA(EMA)

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        DEMA 시리즈
    """
    ema1 = prices.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    return 2 * ema1 - ema2


def calculate_hma(prices: pd.Series, period: int) -> pd.Series:
    """
    Hull Moving Average (헐 이동평균)

    WMA를 활용하여 부드러우면서도 빠른 반응을 제공합니다.
    HMA = WMA(2 * WMA(n/2) - WMA(n), sqrt(n))

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간

    Returns:
        HMA 시리즈
    """
    half_period = period // 2
    sqrt_period = int(np.sqrt(period))

    wma_half = calculate_wma(prices, half_period)
    wma_full = calculate_wma(prices, period)
    raw_hma = 2 * wma_half - wma_full

    return calculate_wma(raw_hma, sqrt_period)


def calculate_alma(
    prices: pd.Series,
    period: int,
) -> pd.Series:
    """
    Arnaud Legoux Moving Average (아르노 르구 이동평균)

    가우시안 가중치를 사용해 노이즈를 줄이면서도 반응성을 유지합니다.

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간
        offset: 가중치 중심 위치
        sigma: 가우시안 분포 폭 제어값

    Returns:
        ALMA 시리즈
    """

    if period <= 0:
        raise ValueError(f"이동평균 기간은 1 이상이어야 합니다: {period}")

    m = ALMA_OFFSET * (period - 1)
    s = period / ALMA_SIGMA
    weights = np.exp(-((np.arange(period) - m) ** 2) / (2 * s * s))
    weights = weights / weights.sum()
    values = prices.to_numpy(dtype=float, copy=False)
    result = np.empty(len(values), dtype=float)

    # 초반 구간은 현재 min_periods=1 동작을 유지하기 위해 짧은 커널로 다시 정규화합니다.
    prefix_length = min(period - 1, len(values))
    for idx in range(prefix_length):
        window_weights = weights[-(idx + 1) :]
        normalized_weights = window_weights / window_weights.sum()
        result[idx] = np.dot(values[: idx + 1], normalized_weights)

    if len(values) >= period:
        valid_result = np.convolve(values, weights[::-1], mode="valid")
        result[period - 1 :] = valid_result

    return pd.Series(result, index=prices.index, dtype=float)


def calculate_moving_average(
    prices: pd.Series,
    period: int,
    ma_type: str = "SMA",
) -> pd.Series:
    """
    지정된 타입의 이동평균을 계산합니다.

    Args:
        prices: 가격 시리즈
        period: 이동평균 기간
        ma_type: 이동평균 타입 (SMA, EMA, WMA, DEMA, TEMA, HMA, ALMA)

    Returns:
        계산된 이동평균 시리즈

    Raises:
        ValueError: 지원하지 않는 MA 타입인 경우

    Examples:
        >>> prices = pd.Series([100, 102, 104, 103, 105])
        >>> calculate_moving_average(prices, 3, "SMA")
        >>> calculate_moving_average(prices, 3, "EMA")
    """
    ma_type_upper = ma_type.upper()

    if ma_type_upper == "SMA":
        return calculate_sma(prices, period)
    elif ma_type_upper == "EMA":
        return calculate_ema(prices, period)
    elif ma_type_upper == "WMA":
        return calculate_wma(prices, period)
    elif ma_type_upper == "DEMA":
        return calculate_dema(prices, period)
    elif ma_type_upper == "TEMA":
        return calculate_tema(prices, period)
    elif ma_type_upper == "HMA":
        return calculate_hma(prices, period)
    elif ma_type_upper == "ALMA":
        return calculate_alma(prices, period)
    else:
        raise ValueError(f"지원하지 않는 MA 타입입니다: {ma_type}. 지원 타입: SMA, EMA, WMA, DEMA, TEMA, HMA, ALMA")


__all__ = [
    "calculate_moving_average",
    "calculate_sma",
    "calculate_ema",
    "calculate_wma",
    "calculate_dema",
    "calculate_tema",
    "calculate_hma",
    "calculate_alma",
]
