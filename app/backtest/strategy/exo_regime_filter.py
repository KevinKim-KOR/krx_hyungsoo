# -*- coding: utf-8 -*-
"""
app/backtest/strategy/exo_regime_filter.py
P206-STEP6D: Exogenous Regime Filter (VIX fear index)

dynamic_etf_market 전용 외생 레짐 필터.
- 주력: fear_index_regime (미국 VIX, 선행 공포 센서)
- MA/Breadth: enabled=false (비교군/백업 슬롯)
- 정렬: 미국 T종가 → 한국 T+1 개장 입력
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Provider Registry ──────────────────────────────────────

PROVIDER_REGISTRY: List[Dict[str, Any]] = [
    {
        "key": "fear_index_regime",
        "enabled": True,
        "source": "US CBOE VIX via yfinance",
        "lookback": 250,
        "lag_days": 1,
        "freshness_ttl": 5,
        "thresholds": {
            "risk_on_max": 20.0,
            "risk_off_min": 26.0,
            "spike_threshold": 0.05,
            "spike_window": 5,
        },
        "missing_policy": "neutral_fallback",
        "regime_map": {
            "low_fear": "risk_on",
            "mid_fear_no_spike": "neutral",
            "mid_fear_spike": "risk_off",
            "high_fear": "risk_off",
        },
        "required_symbols": ["^VIX"],
        "notes": "혼합: 절대 임계치(20/26) + trailing 5DMA 급등률(5%)",
    },
    {
        "key": "market_trend_ma_regime",
        "enabled": False,
        "source": "OHLCV proxy symbol MA crossover",
        "lookback": 200,
        "lag_days": 0,
        "freshness_ttl": 5,
        "thresholds": {"ma_period": 200},
        "missing_policy": "risk_off",
        "regime_map": {"above_ma": "risk_on", "below_ma": "risk_off"},
        "required_symbols": ["069500"],
        "notes": "비활성 — 비교군/백업",
    },
    {
        "key": "market_breadth_regime",
        "enabled": False,
        "source": "후보 universe 중기 모멘텀 양수 비율",
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": 5,
        "thresholds": {"risk_on_pct": 0.60, "risk_off_pct": 0.30},
        "missing_policy": "risk_off",
        "regime_map": {},
        "required_symbols": [],
        "notes": "비활성 — 비교군/백업",
    },
    {
        "key": "news_sentiment_regime",
        "enabled": False,
        "source": "뉴스 감성 지표",
        "lookback": 7,
        "lag_days": 1,
        "freshness_ttl": 5,
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
        "freshness_ttl": 5,
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
        "freshness_ttl": 5,
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
        "freshness_ttl": 5,
        "thresholds": {},
        "missing_policy": "neutral",
        "regime_map": {},
        "required_symbols": [],
        "notes": "비활성",
    },
]

FRESHNESS_TTL_DAYS = 5  # 캘린더 일수 기준

_VIX_CACHE_DIR = "data/cache/ohlcv/vix"


def fetch_vix_cached(start: date, end: date) -> Optional[pd.DataFrame]:
    """VIX 데이터를 캐시 우선으로 fetch. 기존 OHLCV 캐시 패턴 재사용."""
    from pathlib import Path

    cache_dir = Path(_VIX_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"VIX_{start}_{end}"
    cache_path = cache_dir / f"{cache_key}.parquet"

    if cache_path.exists():
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"[VIX] cache hit: {cache_path}")
            return df
        except Exception:
            pass

    try:
        import yfinance as yf

        fetch_start = start - pd.Timedelta(days=400)
        ticker = yf.Ticker("^VIX")
        df = ticker.history(
            start=str(fetch_start),
            end=str(end + pd.Timedelta(days=1)),
        )
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            if hasattr(df.index, "tz") and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            df.to_parquet(cache_path)
            logger.info(f"[VIX] fetched {len(df)} rows → {cache_path}")
            return df
    except Exception as exc:
        logger.warning(f"[VIX] fetch 실패: {exc}")
    return None


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


# ── VIX Fear Regime Provider ───────────────────────────────


def _align_vix_to_kr_date(
    vix_close_series: pd.Series,
    kr_date: date,
) -> Dict[str, Any]:
    """한국 리밸런스일에 대해 미국 VIX 직전 유효 종가를 매핑.

    규칙: kr_date - 1 이하인 미국 거래일 중 최신 종가.
    미국 T종가 → 한국 T+1 입력. same-day 사용 금지.
    """
    cutoff = pd.Timestamp(kr_date - timedelta(days=1))
    valid = vix_close_series[vix_close_series.index <= cutoff]

    if valid.empty:
        return {
            "vix_close": None,
            "source_date_us": None,
            "staleness_days": None,
            "error": "no_valid_vix_before_kr_date",
        }

    last_valid_idx = valid.index[-1]
    vix_val = float(valid.iloc[-1])

    if pd.isna(vix_val):
        return {
            "vix_close": None,
            "source_date_us": str(last_valid_idx.date()),
            "staleness_days": None,
            "error": "vix_value_nan",
        }

    staleness = (kr_date - last_valid_idx.date()).days
    return {
        "vix_close": round(vix_val, 2),
        "source_date_us": str(last_valid_idx.date()),
        "staleness_days": staleness,
        "error": None,
    }


def _compute_5dma(
    vix_close_series: pd.Series,
    source_date_us: str,
) -> Optional[float]:
    """source_date_us 직전 5거래일 종가의 산술평균 (trailing, 당일 미포함)."""
    ts = pd.Timestamp(source_date_us)
    before = vix_close_series[vix_close_series.index < ts]
    if len(before) < 5:
        return None
    vals = before.tail(5).astype(float)
    if vals.isna().any():
        return None
    return round(float(vals.mean()), 4)


def _compute_fear_state(
    vix_close: float,
    vix_5dma: Optional[float],
    risk_on_max: float = 20.0,
    risk_off_min: float = 30.0,
    spike_threshold: float = 0.20,
) -> str:
    """VIX 기반 fear state 판별.

    vix_close < risk_on_max → risk_on
    risk_on_max <= vix_close < risk_off_min and spike < spike_threshold → neutral
    risk_on_max <= vix_close < risk_off_min and spike >= spike_threshold → risk_off
    vix_close >= risk_off_min → risk_off
    """
    if vix_close < risk_on_max:
        return "risk_on"
    if vix_close >= risk_off_min:
        return "risk_off"
    if vix_5dma is not None and vix_5dma > 0:
        spike = vix_close / vix_5dma - 1.0
        if spike >= spike_threshold:
            return "risk_off"
    return "neutral"


# ── Fear Regime Schedule Builder ───────────────────────────


def build_fear_regime_schedule(
    vix_ohlcv: Optional[pd.DataFrame],
    rebalance_dates: List[date],
    risk_on_max: float = 20.0,
    risk_off_min: float = 30.0,
    spike_threshold: float = 0.20,
) -> Dict[str, Any]:
    """한국 리밸런스 날짜별 VIX fear regime schedule 생성."""
    result: Dict[str, Any] = {
        "schedule": {},
        "provider_values": {},
        "provider": "fear_index_regime",
        "fear_index_symbol": "^VIX",
        "alignment_mode": "us_close_to_kr_next_open",
        "freshness_ttl": FRESHNESS_TTL_DAYS,
        "regime_valid": False,
        "regime_error_code": None,
        "risk_on_count": 0,
        "neutral_count": 0,
        "risk_off_count": 0,
    }

    # VIX close series 추출
    vix_close = None
    if vix_ohlcv is not None and not vix_ohlcv.empty:
        _vix_df = vix_ohlcv.copy()
        # tz-aware index → tz-naive (yfinance VIX는 America/Chicago)
        if hasattr(_vix_df.index, "tz") and _vix_df.index.tz is not None:
            _vix_df.index = _vix_df.index.tz_localize(None)
        for col in ["close", "Close"]:
            if col in _vix_df.columns:
                vix_close = _vix_df[col].dropna().astype(float)
                break

    if vix_close is None or vix_close.empty:
        result["regime_error_code"] = "vix_fetch_failed"
        logger.warning("[FEAR-REGIME] VIX 데이터 없음 → fail-closed")
        for d in rebalance_dates:
            result["schedule"][str(d)] = "risk_off"
            result["provider_values"][str(d)] = {
                "fear_value": None,
                "error_code": "vix_fetch_failed",
            }
        result["risk_off_count"] = len(rebalance_dates)
        return result

    risk_on = 0
    neutral = 0
    risk_off = 0

    for d in rebalance_dates:
        aligned = _align_vix_to_kr_date(vix_close, d)

        if aligned["error"] is not None:
            # fail-closed: neutral fallback
            state = "neutral"
            pv = {
                "fear_value": None,
                "vix_5dma": None,
                "vix_spike": None,
                "source_trade_date_us": aligned["source_date_us"],
                "applied_trade_date_kr": str(d),
                "staleness_days": aligned["staleness_days"],
                "error_code": aligned["error"],
            }
        elif (
            aligned["staleness_days"] is not None
            and aligned["staleness_days"] > FRESHNESS_TTL_DAYS
        ):
            # stale → neutral fallback
            state = "neutral"
            pv = {
                "fear_value": aligned["vix_close"],
                "vix_5dma": None,
                "vix_spike": None,
                "source_trade_date_us": aligned["source_date_us"],
                "applied_trade_date_kr": str(d),
                "staleness_days": aligned["staleness_days"],
                "error_code": "staleness_exceeded",
            }
        else:
            vix_val = aligned["vix_close"]
            src_date = aligned["source_date_us"]
            dma = _compute_5dma(vix_close, src_date)
            spike = (
                round(vix_val / dma - 1.0, 4) if dma is not None and dma > 0 else None
            )
            state = _compute_fear_state(
                vix_val, dma, risk_on_max, risk_off_min, spike_threshold
            )
            pv = {
                "fear_value": vix_val,
                "vix_5dma": dma,
                "vix_spike": spike,
                "source_trade_date_us": src_date,
                "applied_trade_date_kr": str(d),
                "staleness_days": aligned["staleness_days"],
                "error_code": None,
            }

        result["schedule"][str(d)] = state
        result["provider_values"][str(d)] = pv

        if state == "risk_on":
            risk_on += 1
        elif state == "risk_off":
            risk_off += 1
        else:
            neutral += 1

    result["regime_valid"] = True
    result["risk_on_count"] = risk_on
    result["neutral_count"] = neutral
    result["risk_off_count"] = risk_off
    logger.info(
        f"[FEAR-REGIME] schedule 완료:"
        f" risk_on={risk_on}, neutral={neutral},"
        f" risk_off={risk_off}"
    )
    return result


# ── Domestic Shock Regime ──────────────────────────────────

DOMESTIC_CARRY_FORWARD_MAX = 3  # 캘린더 일수
DOMESTIC_FRESHNESS_TTL = 5  # 캘린더 일수


def _compute_domestic_state(
    preopen_return: float,
    risk_on_max: float = -0.01,
    risk_off_min: float = -0.03,
) -> str:
    """069500 전일 수익률 기반 국내 쇼크 판정."""
    if preopen_return >= risk_on_max:
        return "risk_on"
    if preopen_return <= risk_off_min:
        return "risk_off"
    return "neutral"


def compute_hybrid_aggregate(global_state: str, domestic_state: str) -> str:
    """PATCH 반영 진리표.

    - 둘 중 하나라도 risk_off → risk_off
    - 한쪽만 neutral → neutral
    - neutral + neutral → neutral (NOT risk_off)
    - 둘 다 risk_on → risk_on
    """
    if global_state == "risk_off" or domestic_state == "risk_off":
        return "risk_off"
    if global_state == "neutral" or domestic_state == "neutral":
        return "neutral"
    return "risk_on"


def build_hybrid_regime_schedule(
    fear_schedule: Dict[str, Any],
    domestic_ohlcv: Optional[pd.DataFrame],
    rebalance_dates: List[date],
) -> Dict[str, Any]:
    """VIX + 국내 하이브리드 regime schedule 생성."""
    result: Dict[str, Any] = {
        "schedule": {},
        "provider_states": {},
        "provider_values": {},
        "confirmation_mode": "hybrid_global_domestic",
        "regime_valid": False,
        "regime_error_code": None,
        "risk_on_count": 0,
        "neutral_count": 0,
        "risk_off_count": 0,
    }

    fear_sched = fear_schedule.get("schedule", {})
    fear_vals = fear_schedule.get("provider_values", {})

    # 국내 close series
    dom_close = None
    if domestic_ohlcv is not None and not domestic_ohlcv.empty:
        for col in ["close", "Close"]:
            if col in domestic_ohlcv.columns:
                dom_close = domestic_ohlcv[col].dropna().astype(float)
                break

    risk_on = 0
    neutral = 0
    risk_off = 0

    for d in rebalance_dates:
        d_str = str(d)

        # Global state (from fear schedule)
        g_state = fear_sched.get(d_str, "neutral")
        g_vals = fear_vals.get(d_str, {})

        # Domestic state
        dom_state = "neutral"  # default fallback
        preopen_ret = None
        intraday_ret = None
        dom_src_date = None

        if dom_close is not None:
            # preopen: kr_date 전일까지만 사용 (lookahead 방지)
            ts = pd.Timestamp(d)
            hist = dom_close[dom_close.index < ts]
            if len(hist) >= 2:
                latest = float(hist.iloc[-1])  # 최근 확정 종가
                prev = float(hist.iloc[-2])  # 직전 확정 종가
                dom_src_date = str(hist.index[-1].date())
                stale = (d - hist.index[-1].date()).days

                if stale > DOMESTIC_FRESHNESS_TTL:
                    dom_state = "risk_off"
                    preopen_ret = None
                elif stale > DOMESTIC_CARRY_FORWARD_MAX:
                    dom_state = "neutral"
                    preopen_ret = None
                elif prev > 0:
                    preopen_ret = round(latest / prev - 1.0, 6)
                    dom_state = _compute_domestic_state(preopen_ret)

                    # 백테스트 근사: 당일 종가로 intraday 재판정
                    _today = dom_close.get(ts)
                    if _today is not None and not pd.isna(_today):
                        intraday_ret = round(float(_today) / prev - 1.0, 6)
                        _intra_state = _compute_domestic_state(
                            intraday_ret,
                            risk_on_max=-0.015,
                            risk_off_min=-0.03,
                        )
                        # 격상만 허용
                        _rank = {
                            "risk_on": 0,
                            "neutral": 1,
                            "risk_off": 2,
                        }
                        if _rank.get(_intra_state, 0) > _rank.get(dom_state, 0):
                            dom_state = _intra_state
        else:
            dom_state = "risk_off"  # fail-closed

        # Hybrid aggregate
        agg = compute_hybrid_aggregate(g_state, dom_state)
        result["schedule"][d_str] = agg
        result["provider_states"][d_str] = {
            "global": g_state,
            "domestic": dom_state,
        }
        # domestic_eval_mode 결정
        if intraday_ret is not None:
            _eval_mode = "daily_close_proxy"
        elif preopen_ret is not None:
            _eval_mode = "preopen_only"
        else:
            _eval_mode = "fallback"

        result["provider_values"][d_str] = {
            "vix_value": g_vals.get("fear_value"),
            "vix_5dma": g_vals.get("vix_5dma"),
            "preopen_return": preopen_ret,
            "intraday_return": intraday_ret,
            "domestic_eval_mode": _eval_mode,
            "domestic_source_date": dom_src_date,
            "global_source_date": g_vals.get("source_trade_date_us"),
        }

        if agg == "risk_on":
            risk_on += 1
        elif agg == "risk_off":
            risk_off += 1
        else:
            neutral += 1

    result["regime_valid"] = fear_schedule.get("regime_valid", False)
    result["regime_error_code"] = fear_schedule.get("regime_error_code")
    result["risk_on_count"] = risk_on
    result["neutral_count"] = neutral
    result["risk_off_count"] = risk_off
    logger.info(
        f"[HYBRID-REGIME] schedule:"
        f" risk_on={risk_on}, neutral={neutral},"
        f" risk_off={risk_off}"
    )
    return result
