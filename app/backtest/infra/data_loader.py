"""
data_loader.py
OHLCV 데이터 로딩 모듈 - DataProvider 추상화 적용 (P180)
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
from datetime import date
import requests
from bs4 import BeautifulSoup

from app.backtest.infra.providers.naver_fdr import FDRProvider
from app.backtest.infra.providers.yfinance_provider import YFinanceProvider

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache/ohlcv")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# P180 Telemetry
CACHE_TELEMETRY = {
    "download_count": 0,
    "cache_hit_count": 0,
    "fallback_count": 0
}

def get_telemetry() -> Dict[str, Any]:
    return CACHE_TELEMETRY.copy()

def _get_provider(data_source: str):
    if data_source == "fdr":
        return FDRProvider()
    elif data_source == "yfinance":
        return YFinanceProvider()
    else:
        log.warning(f"Unknown data_source '{data_source}', falling back to fdr")
        return FDRProvider()

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame 정규화 (MultiIndex 지원을 위해 소문자 + 인덱스 설정)"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 컬럼 소문자화 (run_backtest.py 호환)
    df.columns = [str(c).lower() for c in df.columns]
    
    if "close" not in df.columns:
        if "종가" in df.columns:
            df["close"] = df["종가"]
            
    # 인덱스를 DatetimeIndex로
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except:
            pass
            
    if hasattr(df.index, 'tz') and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
        
    df.index.name = "date"
    return df

def load_ohlcv_cached(
    ticker: str, start: date, end: date, data_source: str = "fdr"
) -> Optional[pd.DataFrame]:
    """
    OHLCV 로드 (캐시 우선, Provider 선택)
    반환: MultiIndex(code, date) DataFrame
    """
    if hasattr(start, 'date'):
        start = start.date()
    if hasattr(end, 'date'):
        end = end.date()
        
    provider = _get_provider(data_source)
    provider_name = provider.name
    
    # 1. 캐시 확인
    provider_cache_dir = CACHE_DIR / provider_name
    provider_cache_dir.mkdir(parents=True, exist_ok=True)
    
    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')
    
    def _check(src: str) -> Optional[pd.DataFrame]:
        cfile = CACHE_DIR / src / f"{ticker}_{start_str}_{end_str}.parquet"
        if cfile.exists():
            try:
                df = pd.read_parquet(cfile)
                if not df.empty:
                    CACHE_TELEMETRY["cache_hit_count"] += 1
                    log.info(f"[CACHE HIT] {src} : {ticker}")
                    return df
            except Exception as e:
                log.warning(f"[CACHE ROOT] Failed to read {cfile}: {e}")
        return None
        
    df_cache = _check(provider_name)
    if df_cache is not None:
        return df_cache
        
    if provider_name != "yfinance":
        df_cache = _check("yfinance")
        if df_cache is not None:
            return df_cache
            
    # 2. 다운로드 (Provider)
    log.info(f"[DOWNLOAD] {provider_name} : {ticker} ({start} ~ {end})")
    raw_df = provider.fetch_ohlcv(ticker, start, end)
    
    if raw_df is None or raw_df.empty:
        # 3. Fallback to yfinance if not already
        if data_source != "yfinance":
            log.info(f"[FALLBACK] trying yfinance for {ticker}")
            fallback_provider = YFinanceProvider()
            raw_df = fallback_provider.fetch_ohlcv(ticker, start, end)
            provider_name = fallback_provider.name
            CACHE_TELEMETRY["fallback_count"] += 1
            
    if raw_df is None or raw_df.empty:
        log.error(f"[FAIL] Could not fetch data for {ticker}")
        return None
        
    CACHE_TELEMETRY["download_count"] += 1
    
    # 4. 정규화 & MultiIndex 생성 (BacktestRunner 포맷)
    norm_df = _normalize_df(raw_df)
    if "close" not in norm_df.columns:
        log.warning(f"[NORMALIZE] 'close' missing for {ticker}")
        return None
        
    norm_df["code"] = ticker
    result = norm_df.reset_index().set_index(["code", "date"]).sort_index()
    
    # 5. 캐시 저장
    try:
        # Update cache target in case we fell back
        provider_cache_dir = CACHE_DIR / provider_name
        provider_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = provider_cache_dir / f"{ticker}_{start_str}_{end_str}.parquet"
        result.to_parquet(cache_file)
        log.info(f"[CACHE WRITE] Saved {ticker} to {cache_file}")
    except Exception as e:
        log.warning(f"[CACHE WRITE] Failed for {ticker}: {e}")
        
    return result

def prefetch_ohlcv(
    tickers: list[str], start: date, end: date, data_source: str = "fdr"
) -> pd.DataFrame:
    """
    전체 유니버스 OHLCV 다운로드 및 병합
    """
    log.info(f"[PREFETCH] Starting for {len(tickers)} tickers via {data_source}...")
    frames = []
    
    for i, ticker in enumerate(tickers, 1):
        df = load_ohlcv_cached(ticker, start, end, data_source)
        if df is not None and not df.empty:
            frames.append(df)
            log.info(f"[PREFETCH] ({i}/{len(tickers)}) {ticker}: OK ({len(df)} rows)")
        else:
            log.warning(f"[PREFETCH] ({i}/{len(tickers)}) {ticker}: FAILED")
            
    if not frames:
        raise RuntimeError(f"Prefetch failed for all tickers. {tickers}")
        
    combined = pd.concat(frames).sort_index()
    return combined

def get_ohlcv(symbol: str, start, end, use_cache: bool = True) -> pd.DataFrame:
    """Legacy Wrapper"""
    df = load_ohlcv_cached(symbol, start, end, data_source="fdr")
    return df if df is not None else pd.DataFrame()

def get_ohlcv_safe(symbol: str, start, end) -> pd.DataFrame:
    """Legacy Wrapper"""
    return get_ohlcv(symbol, start, end)

def get_current_price_naver(code: str) -> Optional[float]:
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        price_el = soup.select_one('.no_today .blind') or soup.select_one('.p11 .blind')
        if price_el:
            return float(price_el.text.strip().replace(',', ''))
        return None
    except Exception:
        return None

def get_kospi_index_naver() -> Optional[float]:
    try:
        url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        el = soup.select_one('#now_value')
        if el:
            return float(el.text.strip().replace(',', ''))
        return None
    except Exception:
        return None
