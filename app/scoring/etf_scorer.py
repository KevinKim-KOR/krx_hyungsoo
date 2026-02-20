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
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

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


def _fetch_naver_daily_chart(tickers: List[str]) -> Tuple[Optional[Dict], str]:
    """
    P100-FIX1: Fetch daily OHLCV from Naver siseJson.naver API.
    Response is NOT valid JSON - needs special parsing.
    
    Returns:
        Tuple[data or None, data_source]
    """
    import requests
    from datetime import datetime, timedelta
    
    end_date = datetime.now(KST).strftime("%Y%m%d")
    start_date = (datetime.now(KST) - timedelta(days=30)).strftime("%Y%m%d")
    
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.naver.com"
    }
    
    for ticker in tickers:
        try:
            url = f"https://api.finance.naver.com/siseJson.naver?symbol={ticker}&requestType=1&startTime={start_date}&endTime={end_date}&timeframe=day"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.ok and len(resp.text) > 100:
                # Parse non-standard JSON response
                # Format: [["날짜","시가","고가","저가","종가","거래량","외국인소진율"],["20260201",72000,73000,71500,72500,1234567,28.04],...]
                text = resp.text.strip()
                # Replace single quotes with double quotes for JSON compatibility
                text = text.replace("'", '"')
                try:
                    import json
                    data = json.loads(text)
                    if isinstance(data, list) and len(data) > 1:
                        # First row is header, rest are data rows
                        # Format: [date, open, high, low, close, volume, foreign_ratio]
                        prices = []
                        for row in data[1:]:  # Skip header
                            if isinstance(row, list) and len(row) >= 5:
                                prices.append({
                                    "date": str(row[0]),
                                    "open": float(row[1]) if row[1] else 0,
                                    "high": float(row[2]) if row[2] else 0,
                                    "low": float(row[3]) if row[3] else 0,
                                    "close": float(row[4]) if row[4] else 0,
                                    "volume": int(row[5]) if len(row) > 5 and row[5] else 0
                                })
                        if prices:
                            # Calculate change_pct from latest close vs previous
                            latest_close = prices[-1]["close"] if prices else 0
                            prev_close = prices[-2]["close"] if len(prices) > 1 else latest_close
                            change_pct = ((latest_close / prev_close) - 1) * 100 if prev_close > 0 else 0
                            
                            results[ticker] = {
                                "prices": prices,
                                "price": latest_close,
                                "change_pct": round(change_pct, 2),
                                "data_source": "NAVER_DAILY"
                            }
                except Exception:
                    pass  # Skip this ticker on parse error
        except Exception:
            pass  # Skip this ticker on fetch error
    
    if results:
        # Save to etf_history_cache.json for future use
        try:
            cache_path = BASE_DIR / "state" / "cache" / "etf_history_cache.json"
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return results, "NAVER_DAILY"
    
    return None, "NAVER_DAILY_FAILED"


def _fetch_yahoo_chart(tickers: List[str]) -> Tuple[Optional[Dict], str]:
    """
    P100-FIX1: Fallback - Yahoo Finance v8/finance/chart (no yfinance dependency).
    
    Returns:
        Tuple[data or None, data_source]
    """
    import requests
    
    results = {}
    for ticker in tickers:
        try:
            # Yahoo uses .KS suffix for KRX stocks
            yahoo_ticker = f"{ticker}.KS"
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?range=1mo&interval=1d"
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.ok:
                data = resp.json()
                result = data.get("chart", {}).get("result", [])
                if result:
                    quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
                    timestamps = result[0].get("timestamp", [])
                    closes = quotes.get("close", [])
                    if closes and len(closes) >= 2:
                        valid_closes = [c for c in closes if c is not None]
                        if len(valid_closes) >= 2:
                            latest = valid_closes[-1]
                            prev = valid_closes[-2]
                            change_pct = ((latest / prev) - 1) * 100 if prev > 0 else 0
                            results[ticker] = {
                                "price": latest,
                                "change_pct": round(change_pct, 2),
                                "prices": [{"close": c} for c in valid_closes[-20:]],
                                "data_source": "YAHOO"
                            }
        except Exception:
            pass
    
    if results:
        return results, "YAHOO"
    return None, "YAHOO_FAILED"


def _fetch_price_history(tickers: List[str]) -> Tuple[Optional[Dict], str]:
    """
    P100-FIX1: Fetch price history with priority chain:
    1. Naver Daily Chart (siseJson.naver) - primary
    2. Yahoo Finance Chart - fallback
    
    Returns:
        Tuple[data or None, data_source]
    """
    # Try Naver first
    result, source = _fetch_naver_daily_chart(tickers)
    if result and len(result) >= len(tickers) * 0.5:  # At least 50% success
        return result, source
    
    # Fallback to Yahoo
    yahoo_result, yahoo_source = _fetch_yahoo_chart(tickers)
    if yahoo_result:
        if result:
            # Merge: Naver data + Yahoo for missing tickers
            for ticker, data in yahoo_result.items():
                if ticker not in result:
                    result[ticker] = data
            return result, f"{source}_THEN_YAHOO"
        return yahoo_result, yahoo_source
    
    # Return whatever we got from Naver (even if partial)
    if result:
        return result, source
    
    return None, "FETCH_FAILED"


def _calculate_momentum_and_volatility(
    ticker: str,
    data: Dict,
    data_source: str
) -> Tuple[Optional[float], Optional[float], str]:
    """
    Calculate momentum (20d return) and volatility (14d stdev) for a ticker.
    P100-FIX1: Updated to handle NAVER_DAILY and YAHOO sources with full price history.
    
    Returns:
        Tuple[momentum_pct, volatility_pct, status_detail]
    """
    ticker_data = data.get(ticker, {})
    
    # P100-FIX1: Handle NAVER_DAILY and YAHOO sources (have prices array)
    if "NAVER_DAILY" in data_source or "YAHOO" in data_source or data_source == "CACHE":
        prices = ticker_data.get("prices", [])
        if prices and len(prices) >= 2:
            # Extract closes - handle both {"close": x} and {"close": x, "open": y, ...} formats
            closes = []
            for p in prices[-20:]:  # Use last 20 days
                if isinstance(p, dict):
                    close = p.get("close")
                    if close and close > 0:
                        closes.append(float(close))
            
            if len(closes) >= 2:
                # Momentum: return over period
                momentum = ((closes[-1] / closes[0]) - 1.0) * 100
                
                # Volatility: stdev of daily returns
                returns = []
                for i in range(1, len(closes)):
                    if closes[i-1] > 0:
                        returns.append((closes[i] / closes[i-1] - 1.0) * 100)
                
                if returns:
                    mean_return = sum(returns) / len(returns)
                    volatility = (sum((r - mean_return)**2 for r in returns) / len(returns)) ** 0.5
                else:
                    volatility = 0
                
                return momentum, volatility, "FULL_HISTORY"
        
        # Fallback: if prices array is empty but has change_pct
        change_pct = ticker_data.get("change_pct")
        if change_pct is not None:
            mom = float(change_pct)
            vol = abs(mom) * 0.5
            return mom, vol, "PROXY_CHANGE_PCT"
        
        return None, None, "INSUFFICIENT_HISTORY"
    
    # Handle realtime-only cache (legacy)
    if data_source in ("CACHE_REALTIME_ONLY", "FETCH_NAVER") or "CACHE_THEN" in data_source:
        if isinstance(ticker_data, dict) and "data" in ticker_data:
            ticker_data = ticker_data["data"]
        change_pct = ticker_data.get("change_pct")
        if change_pct is not None:
            mom = float(change_pct)
            vol = abs(mom) * 0.5
            return mom, vol, "PROXY_CHANGE_PCT"
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
    
    # P100-FIX1: Enhanced data source priority
    # 1. Try to load cache
    cache_data, data_source = _load_price_history_cache()
    
    # 2. Check if cache has enough universe coverage
    cached_universe_count = 0
    if cache_data:
        for ticker in universe:
            ticker_data = cache_data.get(ticker) or cache_data.get(ticker, {}).get("data")
            if ticker_data:
                cached_universe_count += 1
    
    # 3. If cache doesn't cover universe sufficiently, try fetch
    if cached_universe_count < len(universe) and not skip_fetch:
        fetch_data, fetch_source = _fetch_price_history(universe)
        if fetch_data:
            # Merge fetch data with cache data (or use fetch if cache empty)
            if cache_data:
                # Merge: prefer fresh fetch data
                for ticker, ticker_data in fetch_data.items():
                    cache_data[ticker] = ticker_data
                data_source = f"CACHE_THEN_{fetch_source}"
            else:
                cache_data = fetch_data
                data_source = fetch_source
    
    # 4. Still no data → SKIPPED
    if cache_data is None:
        result["reason"] = "DATA_MISSING"
        result["data_source"] = data_source
        result["reason_detail"] = sanitize_reason_detail(f"No price data available, source={data_source}")
        result["input_fingerprint"] = compute_input_fingerprint({"universe": universe, "source": data_source})
        return result
    
    # 5. Calculate momentum and volatility for each ticker
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
    
    # 6. If not enough valid data → SKIPPED
    if valid_count == 0:
        result["reason"] = "DATA_MISSING"
        result["reason_detail"] = sanitize_reason_detail(f"No valid ETF data, tried {len(universe)} tickers, source={data_source}")
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
