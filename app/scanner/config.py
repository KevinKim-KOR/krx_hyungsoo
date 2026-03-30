# -*- coding: utf-8 -*-
"""
app/scanner/config.py — 스캐너 설정 (P205-STEP5B)

V1 확정 정책 및 Feature Registry 정의.
"""
from __future__ import annotations

from typing import Any, Dict, List

# ── V1 확정 정책 ──────────────────────────────────────────
SCANNER_VERSION = "v1"
SCANNER_MODE = "dynamic_etf_market"

# 불변조건 2: Churn 제어 설정값 (강제)
REFRESH_FREQUENCY = "weekly"
MIN_OVERLAP_RATIO = 0.60
MAX_NEW_ENTRIES_PER_REFRESH = 5

# 불변조건 3: 레버리지/인버스 정책 V1 확정
EXCLUDE_INVERSE = True
EXCLUDE_LEVERAGED = True
EXCLUDE_SYNTHETIC = True

# ── Candidate Pool 설정 ───────────────────────────────────
CANDIDATE_POOL_CONFIG: Dict[str, Any] = {
    "source": "krx_etf_list",
    "min_listing_days": 180,
    "min_avg_volume_20d": 50000,
    "min_price": 1000,
    "exclude_inverse": EXCLUDE_INVERSE,
    "exclude_leveraged": EXCLUDE_LEVERAGED,
    "exclude_synthetic": EXCLUDE_SYNTHETIC,
    "max_candidates": 200,
}

# ── V1 활성 Feature 정의 ──────────────────────────────────
V1_ACTIVE_FEATURES: List[Dict[str, Any]] = [
    {
        "key": "price_momentum_3m",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.30,
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "percentile_rank",
        "notes": "3개월 가격 모멘텀 (종가 기준 수익률)",
    },
    {
        "key": "price_momentum_6m",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.20,
        "lookback": 120,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "percentile_rank",
        "notes": "6개월 가격 모멘텀 (종가 기준 수익률)",
    },
    {
        "key": "volatility_20d",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.15,
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "z_score",
        "notes": "20일 변동성 (낮을수록 좋음, 역방향 적용)",
    },
    {
        "key": "liquidity_20d",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.15,
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "percentile_rank",
        "notes": "20일 평균 거래대금",
    },
    {
        "key": "turnover_rate",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.10,
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "fill_zero",
        "normalization": "percentile_rank",
        "notes": "회전율",
    },
    {
        "key": "drawdown_from_high",
        "source": "ohlcv",
        "enabled": True,
        "required": False,
        "weight": 0.10,
        "lookback": 60,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "exclude",
        "normalization": "min_max",
        "notes": "고점 대비 낙폭 (낮을수록 좋음, 역방향 적용)",
    },
]

# ── V2 비활성 슬롯 (구조만 존재, 계산 안 함) ─────────────
V2_DISABLED_SLOTS: List[Dict[str, Any]] = [
    {
        "key": "news_sentiment",
        "source": "external_api",
        "enabled": False,
        "required": False,
        "weight": 0.0,
        "lookback": 7,
        "lag_days": 1,
        "freshness_ttl": "1d",
        "missing_policy": "skip_scoring",
        "normalization": "z_score",
        "notes": "[V2] 뉴스 감성 점수. V1 비활성.",
    },
    {
        "key": "fear_index",
        "source": "external_api",
        "enabled": False,
        "required": False,
        "weight": 0.0,
        "lookback": 1,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "skip_scoring",
        "normalization": "min_max",
        "notes": "[V2] VIX/VKOSPI 공포지수. V1 비활성.",
    },
    {
        "key": "market_breadth",
        "source": "derived",
        "enabled": False,
        "required": False,
        "weight": 0.0,
        "lookback": 20,
        "lag_days": 0,
        "freshness_ttl": "1d",
        "missing_policy": "skip_scoring",
        "normalization": "percentile_rank",
        "notes": "[V2] 시장 폭 지표. V1 비활성.",
    },
    {
        "key": "macro_regime",
        "source": "external_api",
        "enabled": False,
        "required": False,
        "weight": 0.0,
        "lookback": 60,
        "lag_days": 1,
        "freshness_ttl": "7d",
        "missing_policy": "skip_scoring",
        "normalization": "none",
        "notes": "[V2] 매크로 레짐. V1 비활성.",
    },
]

ALL_FEATURES: List[Dict[str, Any]] = V1_ACTIVE_FEATURES + V2_DISABLED_SLOTS


def get_active_features() -> List[Dict[str, Any]]:
    """활성화된 feature 목록만 반환."""
    return [f for f in ALL_FEATURES if f["enabled"]]


def get_disabled_features() -> List[str]:
    """비활성 feature key 목록 반환."""
    return [f["key"] for f in ALL_FEATURES if not f["enabled"]]
