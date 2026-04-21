"""이동평균 기반 점수 지표 계산 모듈."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from config import MIN_TRADING_DAYS
from utils.indicators import calculate_ma_score
from utils.moving_averages import calculate_moving_average


def _consecutive_counter(flags: np.ndarray) -> np.ndarray:
    """연속 True 일수를 계산합니다."""
    result = np.zeros(flags.shape[0], dtype=np.int32)
    streak = 0
    for idx in range(flags.shape[0]):
        if flags[idx]:
            streak += 1
        else:
            streak = 0
        result[idx] = streak
    return result


def calculate_consecutive_days(scores: pd.Series) -> pd.Series:
    """점수 시계열에서 양수 지속 일수를 계산합니다."""
    if scores is None or scores.empty:
        return pd.Series([], dtype=int)

    positive_flags = (scores > 0).to_numpy(dtype=bool, copy=False)
    streak_values = _consecutive_counter(positive_flags)
    return pd.Series(streak_values, index=scores.index, dtype=int)


def _calculate_score(
    close_prices: pd.Series,
    moving_average: pd.Series,
) -> pd.Series:
    return calculate_ma_score(close_prices, moving_average)


def process_ticker_data(
    ticker: str,
    df: pd.DataFrame,
    ma_days: int,
    precomputed_entry: Mapping[str, Any] | None = None,
    ma_type: str = "SMA",
    enable_data_sufficiency_check: bool = False,
) -> dict | None:
    """
    개별 종목의 데이터를 처리하고 지표를 계산합니다.

    Args:
        ticker: 종목 티커
        df: 가격 데이터프레임
        ma_days: 이동평균 기간
        precomputed_entry: 미리 계산된 캐시 데이터 (옵션)
        ma_type: 이동평균 타입 (SMA, EMA, WMA, DEMA, TEMA, HMA, ALMA)
        enable_data_sufficiency_check: 데이터 충분성 검사 활성화 여부
    Returns:
        Dict: 계산된 지표들 또는 None (처리 실패 시)
    """
    if df is None and precomputed_entry is None:
        return None
    if df is not None and df.empty and not precomputed_entry:
        return None

    working_df = df
    if working_df is None and precomputed_entry:
        # Dummy frame to keep downstream logic consistent
        working_df = pd.DataFrame()

    if working_df is not None and isinstance(working_df.columns, pd.MultiIndex):
        working_df = working_df.copy()
        working_df.columns = working_df.columns.get_level_values(0)
        working_df = working_df.loc[:, ~working_df.columns.duplicated()]

    # 티커 유형에 따른 이동평균 기간 결정 (단일 기간 사용)
    current_ma_days = ma_days

    close_prices = None
    open_prices = None
    if isinstance(precomputed_entry, Mapping):
        close_prices = precomputed_entry.get("close")
        open_prices = precomputed_entry.get("open")

    if close_prices is None:
        if working_df is None:
            return None

        price_series = None
        if isinstance(working_df.columns, pd.MultiIndex):
            cols = working_df.columns.get_level_values(0)
            working_df = working_df.copy()
            working_df.columns = cols
            working_df = working_df.loc[:, ~working_df.columns.duplicated()]

        if "unadjusted_close" in working_df.columns:
            price_series = working_df["unadjusted_close"]
        else:
            price_series = working_df["Close"]

        if isinstance(price_series, pd.DataFrame):
            price_series = price_series.iloc[:, 0]
        close_prices = price_series.astype(float)

    if open_prices is None:
        if working_df is not None and "Open" in working_df.columns:
            open_series = working_df["Open"]
            if isinstance(open_series, pd.DataFrame):
                open_series = open_series.iloc[:, 0]
            open_prices = open_series.astype(float)
        else:
            open_prices = close_prices.copy()

    # 데이터 충분성 검증: MA 타입별 이상적인 데이터 요구량
    if enable_data_sufficiency_check:
        ma_type_upper = (ma_type or "SMA").upper()
        if ma_type_upper in {"EMA", "DEMA", "TEMA"}:
            ideal_multiplier = 2.0
        elif ma_type_upper == "HMA":
            ideal_multiplier = 1.5
        else:  # SMA, WMA 등
            ideal_multiplier = 1.0
        ideal_data_required = int(current_ma_days * ideal_multiplier)

        # 데이터가 이상적인 양보다 적으면 완화된 기준 적용
        if len(close_prices) < ideal_data_required:
            # 완화된 기준: multiplier의 절반 (최소 1배)
            relaxed_multiplier = max(ideal_multiplier / 2.0, 1.0)
            min_required_data = int(current_ma_days * relaxed_multiplier)
        else:
            # 충분한 데이터가 있으면 이상적인 기준 적용
            min_required_data = ideal_data_required

        if len(close_prices) < min_required_data:
            return None

    # 절대 최소 거래일 기준 (ENABLE_DATA_SUFFICIENCY_CHECK와 무관, 항상 적용)
    if len(close_prices) < MIN_TRADING_DAYS:
        return None

    # 이동평균 기반 점수 계산
    ma_type_key = (ma_type or "SMA").upper()
    ma_key = f"{ma_type_key}_{int(current_ma_days)}"
    moving_average = None
    ma_score = None
    if isinstance(precomputed_entry, Mapping):
        ma_cache = precomputed_entry.get("ma") or {}
        ma_score_cache = precomputed_entry.get("ma_score") or {}
        moving_average = ma_cache.get(ma_key)
        ma_score = ma_score_cache.get(ma_key)

    if moving_average is None:
        moving_average = calculate_moving_average(close_prices, current_ma_days, ma_type)
    if ma_score is None:
        ma_score = _calculate_score(close_prices, moving_average)

    # consecutive_buy_days = calculate_consecutive_days(ma_score)
    consecutive_buy_days = calculate_consecutive_days(ma_score)

    return {
        "df": working_df if working_df is not None else df,
        "close": close_prices,
        "open": open_prices,
        "ma": moving_average,
        "ma_score": ma_score,
        "buy_signal_days": consecutive_buy_days,
        "ma_days": current_ma_days,
    }
