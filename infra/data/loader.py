# -*- coding: utf-8 -*-
"""
infra/data/loader.py
데이터 로딩 인터페이스 및 구현
"""
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import pandas as pd
import numpy as np
from pykrx import stock

class DataProvider(ABC):
    """데이터 제공자 인터페이스"""
    
    @abstractmethod
    def get_daily_prices(
        self,
        symbol: str,
        start_date: Union[str, date, datetime],
        end_date: Optional[Union[str, date, datetime]] = None
    ) -> pd.DataFrame:
        """일별 가격 데이터 조회"""
        pass

class CachedDataProvider(DataProvider):
    """캐시 지원 데이터 제공자"""
    
    def __init__(self, cache_dir: Union[str, Path] = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, symbol: str) -> Path:
        """캐시 파일 경로"""
        return self.cache_dir / f"{symbol}.parquet"
    
    def _read_cache(self, symbol: str) -> Optional[pd.DataFrame]:
        """캐시 읽기"""
        path = self._get_cache_path(symbol)
        if not path.exists():
            return None
            
        try:
            return pd.read_parquet(path, engine='pyarrow')
        except Exception as e:
            print(f"가격 데이터 로드 실패 ({symbol}): {e}")
            return None
    
    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """캐시 쓰기"""
        if df is None or df.empty:
            return
            
        try:
            path = self._get_cache_path(symbol)
            df.to_parquet(path, engine='pyarrow')
        except Exception as e:
            print(f"캐시 쓰기 실패 ({symbol}): {e}")

def load_prices(
    target_date: Union[str, date, datetime],
    lookback_days: int = 126
) -> pd.DataFrame:
    """
    가격 데이터 로드
    - target_date까지의 lookback_days만큼의 데이터
    - code/date를 인덱스로 하는 멀티인덱스 DataFrame 반환
    """
    from core.utils.trading_day import get_previous_trading_day
    from core.utils.datasources import get_universe_codes
    
    # 1. 날짜 처리
    end_date = pd.to_datetime(target_date).date()
    start_date = get_previous_trading_day(end_date, lookback_days)
    
    # 2. 종목 코드 로드
    codes = get_universe_codes()
    
    # 3. 가격 데이터 로드
    frames = []
    provider = CachedDataProvider()
    
    for code in codes:
        try:
            df = provider.get_daily_prices(code, start_date, end_date)
            if df is not None and not df.empty:
                df['code'] = code
                frames.append(df)
        except Exception as e:
            print(f"가격 로드 실패 ({code}): {e}")
    
    if not frames:
        return pd.DataFrame()
    
    # 4. 데이터 결합 및 정리
    result = pd.concat(frames, axis=0)
    result.set_index(['code', 'date'], inplace=True)
    result.sort_index(inplace=True)
    
    return result

def _load_etf_universe() -> List[Dict[str, Any]]:
    """ETF 유니버스 로드"""
    tickers = stock.get_etf_ticker_list()
    result = []
    
    for ticker in tickers:
        try:
            name = stock.get_etf_ticker_name(ticker)
            result.append({
                'code': ticker,
                'name': name,
                'cat': '',  # 상세 카테고리는 현재 API에서 제공하지 않음
                'size': 0.0  # 시가총액은 별도로 조회 필요
            })
        except Exception as e:
            print(f"ETF 정보 로드 실패 ({ticker}): {e}")
    
    return result

def load_market_data(universe: str, end_date: pd.Timestamp, start_date: pd.Timestamp = None, cache_dir: Path = None) -> pd.DataFrame:
    """
    특정 유니버스의 마켓 데이터 로드
    
    Args:
        universe: 유니버스 ID (예: KOR_ETF_CORE)
        end_date: 데이터 종료일
        start_date: 데이터 시작일 (기본값: end_date-126일)
        cache_dir: 캐시 디렉토리 경로 (기본값: data/cache/ohlcv)
        
    Returns:
        pd.DataFrame: 멀티인덱스(code, date) DataFrame with columns=['close']
    """
    if start_date is None:
        start_date = end_date - pd.Timedelta(days=126)
    
    # 1. 캐시 파일 확인
    if isinstance(cache_dir, Path):
        cache_file = cache_dir / f"{end_date:%Y%m%d}.parquet"
    else:
        default_cache_dir = Path("data/cache/ohlcv")
        default_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = default_cache_dir / f"{end_date:%Y%m%d}.parquet"
    
    if cache_file.exists():
        df = pd.read_parquet(cache_file)
        if len(df) > 0:
            return df
    
    # 2. ETF 유니버스 로드
    etfs = _load_etf_universe()
    exclude_keywords = ["레버리지", "인버스", "선물", "채권", "커버드콜"]
    
    # 3. 필터링
    filtered_etfs = [
        etf for etf in etfs
        if not any(kw in etf['name'] for kw in exclude_keywords)
    ]
    
    # 4. OHLCV 데이터 수집
    dfs = []
    for etf in filtered_etfs:
        try:
            code = etf['code']
            df = stock.get_etf_ohlcv_by_date(
                fromdate=start_date.strftime("%Y%m%d"),
                todate=end_date.strftime("%Y%m%d"),
                ticker=code
            )
            if df is not None and len(df) > 0:
                # 데이터 타입 변환을 먼저 수행
                numeric_columns = ['종가', '시가', '고가', '저가', '거래량', '거래대금']
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # 컬럼명 변경
                df = df.rename(columns={'종가': 'close'})
                df['code'] = code
                dfs.append(df)
        except Exception as e:
            print(f"가격 데이터 로드 실패 ({code}): {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    # 5. 데이터 정리
    if not dfs:
        return pd.DataFrame()
        
    result = pd.concat(dfs)
    result.reset_index(inplace=True)
    
    # 컬럼 이름 변경
    result.rename(columns={
        'index': 'date',
        '날짜': 'date',
        '종가': 'close',
        '거래량': 'volume',
        '거래대금': 'value'
    }, inplace=True)
    
    # 데이터 타입 변환
    numeric_columns = ['close', 'volume', 'value']
    for col in numeric_columns:
        if col in result.columns:
            result[col] = result[col].astype('float64')
    
    # 불필요한 컬럼 제거
    keep_columns = ['code', 'date', 'close', 'volume', 'value']
    result = result[[col for col in keep_columns if col in result.columns]]
    
    # 인덱스 설정
    result.set_index(['code', 'date'], inplace=True)
    result.sort_index(inplace=True)
    
    # 인덱스 설정 후 데이터 타입 확인
    print(f"Data types after set_index: {result.dtypes}")
    
    # 6. 캐시 저장
    result.to_parquet(cache_file)
    
    return result


def load_price_data(
    universe: List[str],
    start_date: date,
    end_date: date,
    cache_dir: Path = None
) -> pd.DataFrame:
    """
    가격 데이터 로드 (백테스트/스캔용)
    
    Args:
        universe: 종목 코드 리스트
        start_date: 시작일
        end_date: 종료일
        cache_dir: 캐시 디렉토리
        
    Returns:
        MultiIndex DataFrame (code, date)
    """
    if cache_dir is None:
        cache_dir = Path('data/cache/ohlcv')
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    dfs = []
    
    for code in universe:
        try:
            # 캐시 파일 확인
            cache_file = cache_dir / f"{code}.parquet"
            
            if cache_file.exists():
                df = pd.read_parquet(cache_file)
                
                # 날짜 필터링
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)]
                elif df.index.name == 'date':
                    df = df[(df.index.date >= start_date) & (df.index.date <= end_date)]
                
                if not df.empty:
                    df['code'] = code
                    dfs.append(df)
        
        except Exception as e:
            print(f"가격 데이터 로드 실패 ({code}): {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    # 데이터 결합
    result = pd.concat(dfs, axis=0)
    
    # 인덱스 설정
    if 'code' in result.columns and 'date' in result.columns:
        result.set_index(['code', 'date'], inplace=True)
    elif result.index.name != 'date':
        result.reset_index(inplace=True)
        result.set_index(['code', 'date'], inplace=True)
    
    result.sort_index(inplace=True)
    
    return result