# -*- coding: utf-8 -*-
"""
app/scanner/feature_provider.py — Feature Provider Registry (P205-STEP5B)

Registry 기반 feature 계산 엔진.
features[] 설정을 읽어 해당 provider를 dispatch 하는 구조.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Feature 계산 함수 Registry ──────────────────────────
_FEATURE_REGISTRY: Dict[str, Callable] = {}


def register_feature(key: str):
    """Feature 계산 함수를 registry에 등록하는 데코레이터."""

    def decorator(func: Callable):
        _FEATURE_REGISTRY[key] = func
        return func

    return decorator


# ── V1 Active Feature 계산 함수들 ───────────────────────


@register_feature("price_momentum_3m")
def _calc_price_momentum_3m(ohlcv: pd.DataFrame, lookback: int = 60) -> Optional[float]:
    """3개월 가격 모멘텀 (종가 기준 수익률)."""
    if ohlcv is None or len(ohlcv) < lookback:
        return None
    closes = ohlcv["close"].dropna()
    if len(closes) < lookback:
        return None
    start = closes.iloc[-lookback]
    if start <= 0:
        return None
    return float((closes.iloc[-1] / start - 1.0) * 100)


@register_feature("price_momentum_6m")
def _calc_price_momentum_6m(
    ohlcv: pd.DataFrame, lookback: int = 120
) -> Optional[float]:
    """6개월 가격 모멘텀 (종가 기준 수익률)."""
    if ohlcv is None or len(ohlcv) < lookback:
        return None
    closes = ohlcv["close"].dropna()
    if len(closes) < lookback:
        return None
    start = closes.iloc[-lookback]
    if start <= 0:
        return None
    return float((closes.iloc[-1] / start - 1.0) * 100)


@register_feature("volatility_20d")
def _calc_volatility_20d(ohlcv: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    """20일 변동성 (일간 수익률 표준편차 * sqrt(252))."""
    if ohlcv is None or len(ohlcv) < lookback + 1:
        return None
    closes = ohlcv["close"].dropna()
    if len(closes) < lookback + 1:
        return None
    rets = closes.pct_change().dropna().tail(lookback)
    if len(rets) < 5:
        return None
    return float(rets.std() * np.sqrt(252) * 100)


@register_feature("liquidity_20d")
def _calc_liquidity_20d(ohlcv: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    """20일 평균 거래대금 (close * volume)."""
    if ohlcv is None or len(ohlcv) < lookback:
        return None
    tail = ohlcv.tail(lookback)
    if "volume" not in tail.columns:
        return None
    if "close" not in tail.columns:
        return None
    turnover = tail["close"] * tail["volume"]
    valid = turnover.dropna()
    if len(valid) < 5:
        return None
    return float(valid.mean())


@register_feature("turnover_rate")
def _calc_turnover_rate(ohlcv: pd.DataFrame, lookback: int = 20) -> Optional[float]:
    """회전율 (최근 거래량 / 전체 평균 거래량)."""
    if ohlcv is None or "volume" not in ohlcv.columns:
        return None
    vols = ohlcv["volume"].dropna()
    if len(vols) < lookback:
        return None
    recent_avg = vols.tail(lookback).mean()
    total_avg = vols.mean()
    if total_avg <= 0:
        return None
    return float(recent_avg / total_avg)


@register_feature("drawdown_from_high")
def _calc_drawdown_from_high(
    ohlcv: pd.DataFrame, lookback: int = 60
) -> Optional[float]:
    """고점 대비 낙폭 (%)."""
    if ohlcv is None or len(ohlcv) < lookback:
        return None
    closes = ohlcv["close"].dropna().tail(lookback)
    if len(closes) < 5:
        return None
    peak = closes.max()
    if peak <= 0:
        return None
    current = closes.iloc[-1]
    return float((current / peak - 1.0) * 100)


# ── Missing Policy 적용 ────────────────────────────────


def apply_missing_policy(value: Optional[float], policy: str) -> Optional[float]:
    """missing_policy에 따라 결측값 처리."""
    if value is not None and np.isfinite(value):
        return value

    if policy == "fill_zero":
        return 0.0
    # exclude, skip_scoring, 기타 → None
    return None


# ── Normalization ───────────────────────────────────────


def normalize_series(
    series: pd.Series,
    method: str,
    invert: bool = False,
) -> pd.Series:
    """시리즈 정규화. invert=True면 역방향."""
    if series.empty or series.dropna().empty:
        return series

    valid = series.dropna()

    if method == "percentile_rank":
        ranked = valid.rank(pct=True)
        result = series.copy()
        result.loc[ranked.index] = ranked
        if invert:
            result.loc[ranked.index] = 1.0 - ranked
        return result

    elif method == "z_score":
        mean_val = valid.mean()
        std_val = valid.std()
        if std_val == 0:
            result = series.copy()
            result.loc[valid.index] = 0.5
            return result
        z = (valid - mean_val) / std_val
        z_clipped = z.clip(-3, 3)
        normalized = (z_clipped + 3) / 6.0
        result = series.copy()
        result.loc[normalized.index] = normalized
        if invert:
            result.loc[normalized.index] = 1.0 - normalized
        return result

    elif method == "min_max":
        vmin = valid.min()
        vmax = valid.max()
        if vmax == vmin:
            result = series.copy()
            result.loc[valid.index] = 0.5
            return result
        normed = (valid - vmin) / (vmax - vmin)
        result = series.copy()
        result.loc[normed.index] = normed
        if invert:
            result.loc[normed.index] = 1.0 - normed
        return result

    return series


# 역방향 정규화가 필요한 feature 키
_INVERT_FEATURES = {"volatility_20d", "drawdown_from_high"}


# ── Feature Matrix 계산 ────────────────────────────────


def compute_feature_matrix(
    tickers: List[str],
    ohlcv_cache: Dict[str, pd.DataFrame],
    features: List[Dict[str, Any]],
    ticker_name_map: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    주어진 ticker들에 대해 feature matrix를 계산.

    Args:
        tickers: 계산 대상 ticker 리스트
        ohlcv_cache: {ticker: ohlcv_df} 캐시
        features: 활성 feature 설정 리스트
        ticker_name_map: {ticker: name} (CSV name 컬럼용)

    Returns:
        DataFrame [ticker x feature columns]
    """
    if ticker_name_map is None:
        ticker_name_map = {}

    active = [f for f in features if f["enabled"]]

    rows: List[Dict[str, Any]] = []
    for ticker in tickers:
        ohlcv = ohlcv_cache.get(ticker)
        row: Dict[str, Any] = {
            "ticker": ticker,
            "name": ticker_name_map.get(ticker, ""),
        }
        row["feature_complete"] = True
        row["exclusion_reason"] = ""

        missing_reasons: List[str] = []

        for feat in active:
            key = feat["key"]
            lookback = feat.get("lookback", 20)
            policy = feat.get("missing_policy", "exclude")

            calc_fn = _FEATURE_REGISTRY.get(key)
            if calc_fn is None:
                logger.warning("[FEATURE] No registered calculator " f"for '{key}'")
                row[key] = None
                row["feature_complete"] = False
                missing_reasons.append(f"{key}: no_calculator")
                continue

            try:
                raw_value = calc_fn(ohlcv, lookback=lookback)
            except Exception as e:
                logger.warning(f"[FEATURE] {ticker}/{key} 계산 실패: {e}")
                raw_value = None

            final = apply_missing_policy(raw_value, policy)

            if final is None and policy == "exclude":
                row["feature_complete"] = False
                missing_reasons.append(f"{key}: missing_excluded")

            row[key] = final

        if missing_reasons:
            row["exclusion_reason"] = "; ".join(missing_reasons)

        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # 정규화 적용
    for feat in active:
        key = feat["key"]
        norm_method = feat.get("normalization", "none")
        if key not in df.columns:
            continue

        invert = key in _INVERT_FEATURES
        col = df[key].copy()
        df[f"{key}_norm"] = normalize_series(col, norm_method, invert=invert)

    return df
