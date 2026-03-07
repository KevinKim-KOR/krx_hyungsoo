from typing import Protocol, Optional
import pandas as pd
from datetime import date

class DataProvider(Protocol):
    """데이터 제공자 프로토콜"""
    
    @property
    def name(self) -> str:
        """Provider 식별자 (캐시 키 등에 사용)"""
        ...
        
    def fetch_ohlcv(self, ticker: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """
        특정 종목의 지정된 기간 OHLCV 데이터를 가져옵니다.
        
        Args:
            ticker: 종목 코드 (예: '069500')
            start: 시작일
            end: 종료일
            
        Returns:
            pd.DataFrame: OHLCV 데이터 (인덱스는 DatetimeIndex), 실패 시 None
        """
        ...
