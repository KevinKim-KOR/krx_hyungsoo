# -*- coding: utf-8 -*-
"""
app/backtest/strategy/exo_regime_filter.py
P206-STEP6B-PATCH1: Exogenous Regime Filter (dual-confirm)

dynamic_etf_market 전용 외생 레짐 필터.
- market_trend_ma_regime + market_breadth_regime 2개 활성
- risk_off = 이중확인(둘 다 risk_off)일 때만 100% cash
- neutral = soft gate (50% cash)
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
        "regime_map": {"above_ma": "risk_on", "below_ma": "risk_off"},
        "required_symbols": ["069500"],
        "notes": "KODEX 200 종가 vs 200일 이평선",
    },
    {
        "key": "market_breadth_regime",
        "enabled": True,
        "source": "후보 universe 중기 모멘텀 양수 비율",
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": 1,
        "thresholds": {
            "risk_on_pct": 0.60,
            "risk_off_pct": 0.30,
        },
        "missing_policy": "risk_off",
        "regime_map": {
            "breadth_high": "risk_on",
            "breadth_mid": "neutral",
            "breadth_low": "risk_off",
        },
        "required_symbols": [],
        "notes": "universe 중 60일 모멘텀 양수 비율",
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
        "notes": "비활성",
    },
    {
        "key": "fear_index_regime",
        "enabled": False,
        "source": "공포지수",
        "lookback": 14,
        "lag_days": 1,
        "freshness_ttl": 1,
        "thresholds": {},
        "missing_policy": "risk_off",
        "regime_map": {},
        "required_symbols": [],
        "notes": "비활성",
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
        "notes": "비활성",
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
        "notes": "비활성",
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
        "notes": "비활성",
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


# ── Aggregate Truth Table ──────────────────────────────────


def compute_aggregate_regime(ma_state: str, breadth_state: str) -> str:
    """A4 진리표: 둘 다 risk_on→risk_on, 둘 다 risk_off→risk_off,
    그 외→neutral."""
    if ma_state == "risk_on" and breadth_state == "risk_on":
        return "risk_on"
    if ma_state == "risk_off" and breadth_state == "risk_off":
        return "risk_off"
    return "neutral"


# ── Provider 1: market_trend_ma_regime ─────────────────────


def _compute_ma_regime_for_date(
    close_series: pd.Series,
    target_date: date,
    ma_period: int = 200,
) -> Dict[str, Any]:
    """MA regime 판정."""
    ts = pd.Timestamp(target_date)
    hist = close_series[close_series.index <= ts]
    if len(hist) < ma_period:
        return {"state": "risk_off", "close": None, "ma": None}

    ma_val = float(hist.tail(ma_period).mean())
    current = float(hist.iloc[-1])

    if pd.isna(ma_val) or pd.isna(current):
        return {"state": "risk_off", "close": None, "ma": None}

    state = "risk_on" if current >= ma_val else "risk_off"
    return {
        "state": state,
        "close": round(current, 2),
        "ma": round(ma_val, 2),
    }


# ── Provider 2: market_breadth_regime ──────────────────────


def _compute_breadth_for_date(
    price_data: pd.DataFrame,
    universe: List[str],
    target_date: date,
    momentum_period: int = 60,
    risk_on_pct: float = 0.60,
    risk_off_pct: float = 0.30,
) -> Dict[str, Any]:
    """후보 universe 중 momentum_period일 모멘텀 양수 비율로 breadth 판정.

    - >= risk_on_pct → risk_on
    - <= risk_off_pct → risk_off
    - 그 사이 → neutral
    """
    ts = pd.Timestamp(target_date)
    positive = 0
    total = 0

    if not isinstance(price_data.index, pd.MultiIndex):
        return {
            "state": "risk_off",
            "breadth_pct": None,
            "positive": 0,
            "total": 0,
        }

    for code in universe:
        try:
            code_data = price_data.xs(code, level="code")
            hist = code_data[code_data.index <= ts]
            if len(hist) < momentum_period + 1:
                continue
            close = hist["close"].astype(float)
            mom = float(close.iloc[-1]) / float(close.iloc[-momentum_period]) - 1.0
            if pd.isna(mom):
                continue
            total += 1
            if mom > 0:
                positive += 1
        except (KeyError, IndexError):
            continue

    if total == 0:
        return {
            "state": "risk_off",
            "breadth_pct": None,
            "positive": 0,
            "total": 0,
        }

    pct = positive / total
    if pct >= risk_on_pct:
        state = "risk_on"
    elif pct <= risk_off_pct:
        state = "risk_off"
    else:
        state = "neutral"

    return {
        "state": state,
        "breadth_pct": round(pct, 4),
        "positive": positive,
        "total": total,
    }


# ── Schedule Builder (PATCH1: dual-confirm) ────────────────


def build_exo_regime_schedule(
    proxy_ohlcv: Optional[pd.DataFrame],
    rebalance_dates: List[date],
    ma_period: int = 200,
    price_data: Optional[pd.DataFrame] = None,
    universe: Optional[List[str]] = None,
    universe_resolver: Optional[Any] = None,
) -> Dict[str, Any]:
    """리밸런스 날짜별 dual-confirm regime schedule 생성.

    universe_resolver가 있으면 rebalance date별 동적 후보군을
    breadth 계산에 사용. 없으면 고정 universe 사용.
    """
    result: Dict[str, Any] = {
        "schedule": {},
        "provider_states": {},
        "provider_values": {},
        "confirmation_mode": "dual_confirm",
        "proxy_symbol": "069500",
        "ma_period": ma_period,
        "regime_valid": False,
        "regime_error_code": None,
        "risk_on_count": 0,
        "neutral_count": 0,
        "risk_off_count": 0,
    }

    # MA close series
    ma_close = None
    if proxy_ohlcv is not None and not proxy_ohlcv.empty:
        if "close" in proxy_ohlcv.columns:
            ma_close = proxy_ohlcv["close"].astype(float)
        elif "Close" in proxy_ohlcv.columns:
            ma_close = proxy_ohlcv["Close"].astype(float)

    if ma_close is None:
        result["regime_error_code"] = "proxy_data_missing"
        logger.warning("[EXO-REGIME] proxy OHLCV 없음 → fail-closed")
        for d in rebalance_dates:
            result["schedule"][str(d)] = "risk_off"
            result["provider_states"][str(d)] = {
                "ma": "risk_off",
                "breadth": "risk_off",
            }
        result["risk_off_count"] = len(rebalance_dates)
        return result

    _fallback_univ = universe or []
    risk_on = 0
    neutral = 0
    risk_off = 0

    for d in rebalance_dates:
        # Provider 1: MA
        ma_v = _compute_ma_regime_for_date(ma_close, d, ma_period)
        ma_state = ma_v["state"]

        # Provider 2: Breadth (dynamic universe 우선)
        _date_univ = _fallback_univ
        if universe_resolver is not None:
            _resolved = universe_resolver(d)
            if _resolved:
                _date_univ = _resolved
        if price_data is not None and _date_univ:
            br_v = _compute_breadth_for_date(price_data, _date_univ, d)
        else:
            br_v = {
                "state": "risk_off",
                "breadth_pct": None,
                "positive": 0,
                "total": 0,
            }
        breadth_state = br_v["state"]

        # Aggregate (A4 truth table)
        agg = compute_aggregate_regime(ma_state, breadth_state)
        result["schedule"][str(d)] = agg
        result["provider_states"][str(d)] = {
            "ma": ma_state,
            "breadth": breadth_state,
        }
        result["provider_values"][str(d)] = {
            "proxy_close": ma_v["close"],
            "proxy_ma200": ma_v["ma"],
            "breadth_pct": br_v["breadth_pct"],
            "breadth_positive": br_v["positive"],
            "breadth_total": br_v["total"],
        }

        if agg == "risk_on":
            risk_on += 1
        elif agg == "risk_off":
            risk_off += 1
        else:
            neutral += 1

    result["regime_valid"] = True
    result["risk_on_count"] = risk_on
    result["neutral_count"] = neutral
    result["risk_off_count"] = risk_off
    logger.info(
        f"[EXO-REGIME] dual-confirm schedule:"
        f" risk_on={risk_on}, neutral={neutral},"
        f" risk_off={risk_off}"
    )
    return result
