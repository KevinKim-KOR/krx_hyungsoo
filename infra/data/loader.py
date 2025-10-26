# -*- coding: utf-8 -*-
"""
infra/data/loader.py
데이터 로딩 인터페이스 및 구현
"""
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Union
import pandas as pd
import numpy as np

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
            return pd.read_parquet(path)
        except Exception as e:
            print(f"캐시 읽기 실패 ({symbol}): {e}")
            return None
    
    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """캐시 쓰기"""
        if df is None or df.empty:
            return
            
        try:
            path = self._get_cache_path(symbol)
            df.to_parquet(path)
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

def load_market_data(universe: str, end_date: pd.Timestamp, start_date: pd.Timestamp = None) -> pd.DataFrame:
    """
    특정 유니버스의 마켓 데이터 로드
    
    Args:
        universe: 유니버스 ID (예: KOR_ETF_CORE)
        end_date: 데이터 종료일
        start_date: 데이터 시작일 (기본값: end_date-126일)
        
    Returns:
        pd.DataFrame: 멀티인덱스(code, date) DataFrame with columns=['close']
    """
    # 임시: 테스트용 mock 데이터
    if start_date is None:
        start_date = end_date - pd.Timedelta(days=126)
    
    # Mock data for testing
    dates = pd.date_range(start=start_date, end=end_date, freq='B')
    codes = ['069500', '091170', '364980']  # KODEX 200, KODEX 자동차, KODEX 2차전지산업
    
    data = []
    for code in codes:
        for date in dates:
            data.append({
                'code': code,
                'date': date,
                'close': 100 * (1 + 0.001 * len(data))  # Dummy price
            })
    
    df = pd.DataFrame(data)
    df.set_index(['code', 'date'], inplace=True)
    df.sort_index(inplace=True)
    
    return df