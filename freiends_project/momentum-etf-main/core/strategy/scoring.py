"""RANK 전략 점수 계산 및 정규화 함수."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_maps_score(
    close_prices: pd.Series,
    moving_average: pd.Series,
) -> pd.Series:
    """
    RANK(Moving Average Position Score) 점수를 계산합니다.

    Args:
        close_prices: 종가 시리즈
        moving_average: 이동평균 시리즈

    Returns:
        pd.Series: 이동평균 대비 수익률 (%)

    Examples:
        >>> close = pd.Series([110, 115, 120])
        >>> ma = pd.Series([100, 100, 100])
        >>> calculate_maps_score(close, ma)
        0    10.0
        1    15.0
        2    20.0
        dtype: float64
    """
    # 0으로 나누기 방지
    safe_moving_average = moving_average.replace(0, np.nan)
    ma_score = ((close_prices / safe_moving_average) - 1.0) * 100
    # 무한대 값 처리
    ma_score = ma_score.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return ma_score


__all__ = [
    "calculate_maps_score",
]
