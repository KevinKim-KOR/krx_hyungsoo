"""
Market Data Provider (D-P.65)

Provides Realtime Market Data via Naver Finance (Poller).
Features:
- File-based Caching (TTL 60s) to prevent naive rate limiting issues.
- Batch fetching support.
- Fail-safe (returns partial data on error).
"""
import requests
import json
import random
import os
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

# Naver Polling URL (Reverse Engineered commonly used endpoint)
# mobile.financial.naver.com structure is often stable
NAVER_POLLING_URL = "https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker}"

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = BASE_DIR / "state" / "cache"
CACHE_FILE = CACHE_DIR / "market_data_cache.json"

# Config
CACHE_TTL_SECONDS = 60

class MarketDataProvider:
    def __init__(self, provider_type: str = "naver"):
        self.provider_type = provider_type
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        })
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> Dict:
        if not CACHE_FILE.exists():
            return {}
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except:
            return {}

    def _save_cache(self, data: Dict):
        try:
            CACHE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[MarketData] Cache save failed: {e}")

    def fetch_realtime(self, tickers: List[str]) -> Dict[str, Dict]:
        """
        Fetch realtime data with caching.
        """
        if not tickers:
            return {}
            
        if self.provider_type == "mock":
            return self._fetch_mock(tickers)
            
        # 1. Load Cache
        cache = self._load_cache()
        now_ts = time.time()
        
        results = {}
        to_fetch = []
        
        # 2. Check Cache
        for t in tickers:
            cached_item = cache.get(t)
            if cached_item and (now_ts - cached_item.get("_ts", 0) < CACHE_TTL_SECONDS):
                results[t] = cached_item["data"]
            else:
                to_fetch.append(t)
                
        # 3. Fetch Misses
        if to_fetch:
            print(f"[MarketData] Fetching {len(to_fetch)} items from {self.provider_type}...")
            fetched = self._fetch_naver_batch(to_fetch)
            
            # Update Cache
            for t, data in fetched.items():
                results[t] = data
                cache[t] = {
                    "_ts": now_ts,
                    "data": data
                }
            
            # Save Cache (even if partial)
            self._save_cache(cache)
            
        return results

    def _fetch_naver_batch(self, tickers: List[str]) -> Dict[str, Dict]:
        results = {}
        # Chunking if too many (Naver might limit query length)
        # Let's chunk by 20
        chunk_size = 20
        for i in range(0, len(tickers), chunk_size):
            chunk = tickers[i:i+chunk_size]
            query_str = ",".join([f"SERVICE_ITEM:{t}" for t in chunk])
            try:
                url = f"https://polling.finance.naver.com/api/realtime?query={query_str}"
                res = self.session.get(url, timeout=5)
                if res.ok:
                    data = res.json()
                    if "result" in data and "areas" in data["result"]:
                        for area in data["result"]["areas"]:
                            for item in area.get("datas", []):
                                t_code = item.get("cd")
                                if t_code:
                                    results[t_code] = {
                                        "provider": "naver",
                                        "price": item.get("nv"), 
                                        "change_pct": item.get("cr"), 
                                        "change_val": item.get("cv"),
                                        "volume": item.get("aq"),
                                        "value_krw": (item.get("aa") or 0) * 1000000,
                                        "nav": item.get("nav"), 
                                        "name": item.get("nm")
                                    }
            except Exception as e:
                print(f"[MarketData] Batch fetch error: {e}")
                # Partial failure is acceptable, we just don't return data for those.
                
        return results

    def _fetch_mock(self, tickers: List[str]) -> Dict[str, Dict]:
        results = {}
        for t in tickers:
            # Mock fluctuation
            change = random.uniform(-4.0, 4.0)
            price = 10000 * (1 + change/100)
            results[t] = {
                "provider": "mock",
                "price": int(price),
                "change_pct": round(change, 2),
                "volume": random.randint(1000, 100000),
                "value_krw": random.randint(100, 10000) * 1000000,
                "nav": int(price * (1 + random.uniform(-0.01, 0.01))) if "069500" in t else None,
                "name": f"Mock_{t}"
            }
        return results
