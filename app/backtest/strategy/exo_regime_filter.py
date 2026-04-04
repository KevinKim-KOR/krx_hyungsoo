# -*- coding: utf-8 -*-
"""
app/backtest/strategy/exo_regime_filter.py
P206-STEP6B: Exogenous Regime Filter V1

dynamic_etf_market 전용 외생 레짐 필터.
risk_off 시 해당 리밸런스에서 위험자산 목표 0%, 현금 100%.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Provider Registry ──────────────────────────────────────

PROVIDER_REGISTRY: List[Dict[str, Any]] = [
    {
        "key": "market_trend_ma_regime",
        "enabled": True,
        "source": "OHLCV proxy symbol MA crossover",
        "lookback": 200,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {"ma_period": 200},
        "missing_policy": "risk_off",
        "regime_map": {
            "above_ma": "risk_on",
            "below_ma": "risk_off",
        },
        "required_symbols": ["069500"],
        "notes": "KODEX 200 종가 vs 200일 이평선",
    },
    {
        "key": "market_breadth_regime",
        "enabled": False,
        "source": "시장 breadth 지표 (V2 예정)",
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "risk_off",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
    {
        "key": "news_sentiment_regime",
        "enabled": False,
        "source": "뉴스 감성 지표",
        "lookback": 7,
        "lag_days": 1,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "risk_off",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
    {
        "key": "fear_index_regime",
        "enabled": False,
        "source": "공포지수 (VIX 등)",
        "lookback": 14,
        "lag_days": 1,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "risk_off",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
    {
        "key": "fx_regime",
        "enabled": False,
        "source": "환율 레짐",
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "neutral",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
    {
        "key": "rate_regime",
        "enabled": False,
        "source": "금리 레짐",
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "neutral",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
    {
        "key": "macro_composite_regime",
        "enabled": False,
        "source": "매크로 복합 지표",
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "neutral",
        "regime_map": {},
        "required_symbols": [],
        "notes": "V1에서는 비활성",
    },
]


def get_active_providers() -> List[Dict[str, Any]]:
    """활성화된 provider 목록 반환."""
    return [p for p in PROVIDER_REGISTRY if p["enabled"]]


def get_required_proxy_symbols() -> List[str]:
    """모든 활성 provider가 요구하는 proxy symbol 목록."""
    symbols: List[str] = []
    for p in get_active_providers():
        for s in p.get("required_symbols", []):
            if s not in symbols:
                symbols.append(s)
    return symbols


# ── V1 Provider: market_trend_ma_regime ────────────────────


def _compute_ma_regime_for_date(
    close_series: pd.Series,
    target_date: date,
    ma_period: int = 200,
) -> str:
    """주어진 날짜의 MA regime 판정.

    Returns: "risk_on" | "risk_off"
    """
    ts = pd.Timestamp(target_date)
    hist = close_series[close_series.index <= ts]
    if len(hist) < ma_period:
        return "risk_off"  # fail-closed

    ma_val = float(hist.tail(ma_period).mean())
    current = float(hist.iloc[-1])

    if pd.isna(ma_val) or pd.isna(current):
        return "risk_off"  # fail-closed

    return "risk_on" if current >= ma_val else "risk_off"


# ── Schedule Builder ───────────────────────────────────────


def build_exo_regime_schedule(
    proxy_ohlcv: Optional[pd.DataFrame],
    rebalance_dates: List[date],
    ma_period: int = 200,
) -> Dict[str, Any]:
    """리밸런스 날짜별 exogenous regime schedule 생성.

    Returns:
        {
            "schedule": {date_str: regime_state, ...},
            "provider": "market_trend_ma_regime",
            "proxy_symbol": "069500",
            "ma_period": 200,
            "regime_valid": bool,
            "regime_error_code": str or None,
            "risk_off_count": int,
            "risk_on_count": int,
        }
    """
    result: Dict[str, Any] = {
        "schedule": {},
        "provider": "market_trend_ma_regime",
        "proxy_symbol": "069500",
        "ma_period": ma_period,
        "regime_valid": False,
        "regime_error_code": None,
        "risk_off_count": 0,
        "risk_on_count": 0,
    }

    if proxy_ohlcv is None or proxy_ohlcv.empty:
        result["regime_error_code"] = "proxy_data_missing"
        logger.warning("[EXO-REGIME] proxy OHLCV 없음 → fail-closed")
        # fail-closed: 모든 날짜를 risk_off
        for d in rebalance_dates:
            result["schedule"][str(d)] = "risk_off"
        result["risk_off_count"] = len(rebalance_dates)
        return result

    # close 시리즈 추출
    if "close" in proxy_ohlcv.columns:
        close = proxy_ohlcv["close"].astype(float)
    elif "Close" in proxy_ohlcv.columns:
        close = proxy_ohlcv["Close"].astype(float)
    else:
        result["regime_error_code"] = "no_close_column"
        for d in rebalance_dates:
            result["schedule"][str(d)] = "risk_off"
        result["risk_off_count"] = len(rebalance_dates)
        return result

    risk_on = 0
    risk_off = 0
    for d in rebalance_dates:
        state = _compute_ma_regime_for_date(close, d, ma_period)
        result["schedule"][str(d)] = state
        if state == "risk_on":
            risk_on += 1
        else:
            risk_off += 1

    result["regime_valid"] = True
    result["risk_on_count"] = risk_on
    result["risk_off_count"] = risk_off
    logger.info(
        f"[EXO-REGIME] schedule 완료:" f" risk_on={risk_on}, risk_off={risk_off}"
    )
    return result
