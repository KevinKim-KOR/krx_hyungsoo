"""
data_loader.py
단순한 데이터 로딩 - yfinance 중심
친구 코드 구조 참고
"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache/ohlcv")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_cache(symbol: str) -> Optional[pd.DataFrame]:
    """캐시에서 데이터 읽기"""
    cache_file = CACHE_DIR / f"{symbol}.parquet"
    if not cache_file.exists():
        return None
    try:
        df = pd.read_parquet(cache_file)
        if df.empty:
            return None
        return df
    except Exception as e:
        log.warning(f"Cache read failed for {symbol}: {e}")
        return None


def _write_cache(symbol: str, df: pd.DataFrame):
    """캐시에 데이터 저장"""
    if df is None or df.empty:
        return
    try:
        cache_file = CACHE_DIR / f"{symbol}.parquet"
        df.to_parquet(cache_file)
    except Exception as e:
        log.warning(f"Cache write failed for {symbol}: {e}")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame 정규화"""
    if df is None or df.empty:
        return pd.DataFrame()
    
    # 인덱스를 DatetimeIndex로 변환
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    
    # 타임존 제거
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    
    # 정렬 및 중복 제거
    df = df.sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
    # 컬럼명 정규화
    df = df.rename(columns={
        'Adj Close': 'AdjClose',
        'adj_close': 'AdjClose',
    })
    
    return df


def get_ohlcv(symbol: str, start, end, use_cache: bool = True) -> pd.DataFrame:
    """
    OHLCV 데이터 로딩 - 단순 버전
    
    Args:
        symbol: 종목 코드 (예: '005930.KS', 'AAPL')
        start: 시작일
        end: 종료일
        use_cache: 캐시 사용 여부
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume, AdjClose
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    
    # 1. 캐시 확인
    if use_cache:
        cached = _read_cache(symbol)
        if cached is not None and not cached.empty:
            # 캐시에 필요한 데이터가 모두 있으면 반환
            if start >= cached.index.min() and end <= cached.index.max():
                result = cached.loc[start:end]
                if not result.empty:
                    return result
    
    # 2. yfinance로 다운로드
    try:
        log.info(f"Downloading {symbol} from {start.date()} to {end.date()}")
        df = yf.download(
            symbol,
            start=start,
            end=end + pd.Timedelta(days=1),  # end는 inclusive하게
            progress=False,
            auto_adjust=False
        )
        
        if df.empty:
            log.warning(f"No data for {symbol}")
            return pd.DataFrame()
        
        # 정규화
        df = _normalize_df(df)
        
        # 3. 캐시 업데이트
        if use_cache:
            # 기존 캐시와 병합
            if cached is not None and not cached.empty:
                df = pd.concat([cached, df]).sort_index()
                df = df[~df.index.duplicated(keep='last')]
            _write_cache(symbol, df)
        
        # 요청 범위만 반환
        return df.loc[start:end]
        
    except Exception as e:
        log.error(f"Failed to download {symbol}: {e}")
        return pd.DataFrame()


def get_ohlcv_safe(symbol: str, start, end) -> pd.DataFrame:
    """
    안전한 OHLCV 로딩 - 에러 시 빈 DataFrame 반환
    하위 호환성을 위한 래퍼
    """
    try:
        return get_ohlcv(symbol, start, end)
    except Exception as e:
        log.warning(f"get_ohlcv_safe failed for {symbol}: {e}")
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
