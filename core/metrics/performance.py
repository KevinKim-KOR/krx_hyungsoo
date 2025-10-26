# -*- coding: utf-8 -*-
"""
core/metrics/performance.py
성과 지표 계산 모듈
"""
from typing import Union
import pandas as pd
import numpy as np

def calc_returns(
    prices: Union[pd.Series, pd.DataFrame],
    lookback: int = 1,
    min_periods: int = None
) -> Union[float, pd.Series]:
    """
    수익률 계산
    - lookback: 룩백 기간
    - min_periods: 최소 필요 기간 (기본: lookback)
    """
    if min_periods is None:
        min_periods = lookback
        
    if isinstance(prices, pd.Series):
        if len(prices) < min_periods:
            return 0.0
        return (prices / prices.shift(lookback)) - 1.0
        
    else:  # DataFrame
        return prices.pct_change(periods=lookback, min_periods=min_periods)

def calc_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02,  # 연율화 2%
    periods_per_year: int = 252
) -> float:
    """
    샤프 비율 계산
    - returns: 일간 수익률
    - risk_free_rate: 무위험 수익률 (연율화)
    - periods_per_year: 연간 기간 수 (일간=252, 주간=52, 월간=12)
    """
    if len(returns) < 2:
        return 0.0
        
    # 연율화 계수
    annualization = np.sqrt(periods_per_year)
    
    excess_returns = returns - risk_free_rate / periods_per_year
    if excess_returns.std() == 0:
        return 0.0
        
    return excess_returns.mean() / excess_returns.std() * annualization

def calc_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    소티노 비율 계산 (하방 위험 기준)
    """
    if len(returns) < 2:
        return 0.0
        
    excess_returns = returns - risk_free_rate / periods_per_year
    down_std = np.sqrt(np.mean(np.minimum(excess_returns, 0) ** 2))
    
    if down_std == 0:
        return 0.0
        
    return excess_returns.mean() / down_std * np.sqrt(periods_per_year)

def calc_max_drawdown(prices: pd.Series) -> float:
    """
    최대 낙폭 계산
    """
    if len(prices) < 2:
        return 0.0
        
    cummax = prices.cummax()
    drawdown = prices / cummax - 1.0
    return float(drawdown.min())

def calc_cagr(
    prices: pd.Series,
    periods_per_year: int = 252
) -> float:
    """
    연평균 성장률 계산
    """
    if len(prices) < 2:
        return 0.0
        
    years = len(prices) / periods_per_year
    if years == 0:
        return 0.0
        
    total_return = prices.iloc[-1] / prices.iloc[0] - 1
    return (1 + total_return) ** (1 / years) - 1