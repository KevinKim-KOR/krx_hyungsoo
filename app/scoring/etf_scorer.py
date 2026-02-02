# -*- coding: utf-8 -*-
"""
ETF Scorer (P100-2)

PC에서 ETF 스코어링 및 추천 리스트 생성.
- NO MOCK DATA IN APP CODE (RedTeam Hardening)
- Data Priority: CACHE → FETCH → SKIPPED
- Score: Rank-based 0~100 (clamped)
- ENUM-only reason, sanitized reason_detail

Usage:
    from app.scoring.etf_scorer import score_etfs
    result = score_etfs(universe, top_n=4)
"""

import json
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# Project Root
BASE_DIR = Path(__file__).parent.parent.parent

# ENUM-only validation
ENUM_ONLY_PATTERN = re.compile(r"^[A-Z0-9_]+$")

# Score Weights (configurable, not magic numbers causing scale explosion)
MOMENTUM_WEIGHT = 70  # 70%
VOLATILITY_WEIGHT = 30  # 30%


def sanitize_reason_detail(text: str, max_len: int = 240) -> str:
    """reason_detail sanitize: 개행 제거, 특수문자 escape, 길이 제한"""
    if not text:
        return ""
    clean = text.replace("\n", " ").replace("\r", "").replace("\t", " ")
    clean = clean.replace('"', "'")
    clean = " ".join(clean.split())
    return clean[:max_len]


def validate_enum_only(value: str) -> bool:
    """ENUM-only regex validation: ^[A-Z0-9_]+$"""
    return bool(ENUM_ONLY_PATTERN.match(value))


def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
    """Clamp value to range [min_val, max_val]"""
    return max(min_val, min(max_val, value))


def compute_input_fingerprint(data: Dict[str, Any]) -> str:
    """Compute fingerprint for determinism verification"""
    sorted_data = json.dumps(data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]


def _load_price_history_cache() -> Tuple[Optional[Dict], str]:
    """
    Load ETF price history from cache.
    
    Returns:
        Tuple[data or None, data_source]
    """
    # Try etf_history_cache.json (preferred for scoring - has daily prices)
    etf_history_path = BASE_DIR / "state" / "cache" / "etf_history_cache.json"
    if etf_history_path.exists():
        try:
            content = etf_history_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return data, "CACHE"
        except Exception:
            pass
    
    # Fallback: market_data_cache.json (realtime only, no history for momentum)
    market_cache_path = BASE_DIR / "state" / "cache" / "market_data_cache.json"
    if market_cache_path.exists():
        try:
            content = market_cache_path.read_text(encoding="utf-8")
            data = json.loads(content)
            # This cache only has realtime data, not sufficient for momentum calculation
            # But we can try to use change_pct as a proxy
            return data, "CACHE_REALTIME_ONLY"
        except Exception:
            pass
    
    return None, "NOT_FOUND"


def _fetch_price_history(tickers: List[str]) -> Tuple[Optional[Dict], str]:
    """
    Fetch price history via provider (NO MOCK DATA).
    
    Returns:
        Tuple[data or None, data_source]
    """
    try:
        from app.providers.market_data import MarketDataProvider
        provider = MarketDataProvider(provider_type="naver")  # NOT mock
        result = provider.fetch_realtime(tickers)
        if result:
            return result, "FETCH"
        return None, "FETCH_FAILED"
    except Exception as e:
        return None, f"FETCH_ERROR"


def _calculate_momentum_and_volatility(
    ticker: str,
    data: Dict,
    data_source: str
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Calculate momentum (20d return) and volatility (14d stdev) for a ticker.
    
    Returns:
        Tuple[momentum_pct, volatility_pct, status_detail]
    """
    # If we have full history cache
    if data_source == "CACHE":
        ticker_data = data.get(ticker, {})
        prices = ticker_data.get("prices", [])
        if len(prices) >= 20:
            closes = [p.get("close", 0) for p in prices[-20:]]
            if closes[0] > 0 and closes[-1] > 0:
                momentum = ((closes[-1] / closes[0]) - 1.0) * 100
                # Volatility: stdev of daily returns
                returns = []
                for i in range(1, len(closes)):
                    if closes[i-1] > 0:
                        returns.append((closes[i] / closes[i-1] - 1.0) * 100)
                volatility = (sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns)) ** 0.5 if returns else 0
                return momentum, volatility, "OK"
        return None, None, "INSUFFICIENT_HISTORY"
    
    # If only realtime cache, use change_pct as proxy
    if data_source == "CACHE_REALTIME_ONLY":
        ticker_data = data.get(ticker, {})
        if isinstance(ticker_data, dict) and "data" in ticker_data:
            ticker_data = ticker_data["data"]
        change_pct = ticker_data.get("change_pct")
        if change_pct is not None:
            # Use daily change as momentum proxy (not ideal but deterministic)
            return float(change_pct), abs(float(change_pct)) * 0.5, "PROXY_CHANGE_PCT"
        return None, None, "NO_CHANGE_PCT"
    
    # FETCH data
    if data_source == "FETCH":
        ticker_data = data.get(ticker, {})
        change_pct = ticker_data.get("change_pct")
        if change_pct is not None:
            return float(change_pct), abs(float(change_pct)) * 0.5, "PROXY_CHANGE_PCT"
        return None, None, "NO_CHANGE_PCT"
    
    return None, None, "UNKNOWN_SOURCE"


def score_etfs(
    universe: List[str],
    top_n: int = 4,
    skip_fetch: bool = False
) -> Dict:
    """
    Score ETFs and return top N picks.
    
    Args:
        universe: List of ETF tickers to score
        top_n: Number of top picks to return
        skip_fetch: If True, skip network fetch (use cache only)
    
    Returns:
        Dict with status, reason, top_picks, etc.
    """
    result = {
        "status": "SKIPPED",
        "reason": "UNKNOWN_ERROR",
        "reason_detail": "",
        "data_source": "NONE",
        "valid_count": 0,
        "top_picks": [],
        "input_fingerprint": ""
    }
    
    if not universe:
        result["reason"] = "EMPTY_UNIVERSE"
        result["reason_detail"] = sanitize_reason_detail("No ETF tickers provided")
        return result
    
    # 1. Try to load cache
    cache_data, data_source = _load_price_history_cache()
    
    # 2. If no cache, try fetch (unless skip_fetch)
    if cache_data is None and not skip_fetch:
        cache_data, data_source = _fetch_price_history(universe)
    
    # 3. Still no data → SKIPPED
    if cache_data is None:
        result["reason"] = "DATA_MISSING"
        result["data_source"] = data_source
        result["reason_detail"] = sanitize_reason_detail(f"No price data available, source={data_source}")
        result["input_fingerprint"] = compute_input_fingerprint({"universe": universe, "source": data_source})
        return result
    
    # 4. Calculate momentum and volatility for each ticker
    scored_items = []
    for ticker in universe:
        momentum, volatility, calc_status = _calculate_momentum_and_volatility(ticker, cache_data, data_source)
        if momentum is not None and volatility is not None:
            scored_items.append({
                "ticker": ticker,
                "momentum": momentum,
                "volatility": volatility,
                "calc_status": calc_status
            })
    
    valid_count = len(scored_items)
    result["valid_count"] = valid_count
    result["data_source"] = data_source
    
    # 5. If not enough valid data → SKIPPED
    if valid_count == 0:
        result["reason"] = "DATA_MISSING"
        result["reason_detail"] = sanitize_reason_detail(f"No valid ETF data in cache, tried {len(universe)} tickers")
        result["input_fingerprint"] = compute_input_fingerprint({"universe": universe, "source": data_source})
        return result
    
    # 6. Rank-based scoring (deterministic: sort by value then ticker for ties)
    # Sort by momentum descending, then by ticker ascending for ties
    scored_items.sort(key=lambda x: (-x["momentum"], x["ticker"]))
    for i, item in enumerate(scored_items):
        item["mom_rank"] = i + 1
        item["mom_rank_pct"] = 1.0 - (i / valid_count) if valid_count > 1 else 1.0
    
    # Sort by volatility ascending (lower is better), then by ticker ascending
    scored_items.sort(key=lambda x: (x["volatility"], x["ticker"]))
    for i, item in enumerate(scored_items):
        item["vol_rank"] = i + 1
        item["vol_rank_pct"] = 1.0 - (i / valid_count) if valid_count > 1 else 1.0
    
    # 7. Calculate final score (clamped 0-100)
    for item in scored_items:
        raw_score = (
            MOMENTUM_WEIGHT * item["mom_rank_pct"] +
            VOLATILITY_WEIGHT * item["vol_rank_pct"]
        )
        item["score"] = clamp(raw_score, 0, 100)
    
    # 8. Sort by score descending, then ticker for determinism
    scored_items.sort(key=lambda x: (-x["score"], x["ticker"]))
    
    # 9. Build top_picks
    top_picks = []
    for item in scored_items[:top_n]:
        pick = {
            "ticker": item["ticker"],
            "score": round(item["score"], 1),
            "reason": "RANK_SCORE",
            "reason_detail": sanitize_reason_detail(
                f"mom_rank={item['mom_rank']}/{valid_count} vol_rank={item['vol_rank']}/{valid_count}"
            )
        }
        # Validate reason is ENUM-only
        if not validate_enum_only(pick["reason"]):
            pick["reason"] = "SCORE_COMPUTED"
        top_picks.append(pick)
    
    # 10. Success result
    result["status"] = "OK"
    result["reason"] = "SUCCESS"
    result["reason_detail"] = sanitize_reason_detail(
        f"data_source={data_source}, valid={valid_count}, top_n={len(top_picks)}"
    )
    result["top_picks"] = top_picks
    result["input_fingerprint"] = compute_input_fingerprint({
        "universe": sorted(universe),
        "source": data_source,
        "valid": valid_count
    })
    
    return result


# For testing only - NOT for production use
if __name__ == "__main__":
    # Default universe from strategy bundle
    test_universe = ["069500", "229200", "114800", "122630"]
    result = score_etfs(test_universe, top_n=4)
    print(json.dumps(result, indent=2, ensure_ascii=False))
