# -*- coding: utf-8 -*-
"""
infra/data/updater.py
실시간 데이터 업데이트 메커니즘
"""
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import pandas as pd
import logging
from pykrx import stock

logger = logging.getLogger(__name__)


class DataUpdater:
    """데이터 업데이트 관리자"""
    
    def __init__(self, cache_dir: Union[str, Path] = "data/cache"):
        """
        Args:
            cache_dir: 캐시 디렉토리 경로
        """
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
            df = pd.read_parquet(path)
            if df.empty:
                return None
            return df
        except Exception as e:
            logger.warning(f"캐시 읽기 실패 ({symbol}): {e}")
            return None
    
    def _write_cache(self, symbol: str, df: pd.DataFrame) -> None:
        """캐시 쓰기"""
        if df is None or df.empty:
            return
        
        try:
            path = self._get_cache_path(symbol)
            df.to_parquet(path)
            logger.debug(f"캐시 저장 완료: {symbol} ({len(df)} rows)")
        except Exception as e:
            logger.error(f"캐시 쓰기 실패 ({symbol}): {e}")
    
    def get_last_cached_date(self, symbol: str) -> Optional[date]:
        """
        캐시된 데이터의 마지막 날짜 조회
        
        Args:
            symbol: 종목 코드
            
        Returns:
            마지막 날짜 또는 None
        """
        cached = self._read_cache(symbol)
        if cached is None or cached.empty:
            return None
        
        try:
            # 인덱스가 날짜인 경우
            if isinstance(cached.index, pd.DatetimeIndex):
                return cached.index.max().date()
            # date 컬럼이 있는 경우
            elif 'date' in cached.columns:
                return pd.to_datetime(cached['date']).max().date()
            else:
                return None
        except Exception as e:
            logger.warning(f"마지막 날짜 조회 실패 ({symbol}): {e}")
            return None
    
    def needs_update(
        self,
        symbol: str,
        target_date: Optional[date] = None
    ) -> bool:
        """
        업데이트 필요 여부 확인
        
        Args:
            symbol: 종목 코드
            target_date: 목표 날짜 (기본값: 오늘)
            
        Returns:
            업데이트 필요 여부
        """
        if target_date is None:
            target_date = date.today()
        
        last_date = self.get_last_cached_date(symbol)
        
        # 캐시 없음
        if last_date is None:
            return True
        
        # 캐시가 오래됨
        if last_date < target_date:
            return True
        
        return False
    
    def update_symbol(
        self,
        symbol: str,
        end_date: Optional[date] = None,
        force: bool = False
    ) -> bool:
        """
        특정 종목 데이터 업데이트 (증분 업데이트)
        
        Args:
            symbol: 종목 코드
            end_date: 종료 날짜 (기본값: 오늘)
            force: 강제 업데이트 (전체 재다운로드)
            
        Returns:
            업데이트 성공 여부
        """
        if end_date is None:
            end_date = date.today()
        
        try:
            # 1. 기존 캐시 확인
            cached = self._read_cache(symbol)
            
            if force or cached is None or cached.empty:
                # 전체 다운로드 (최근 2년)
                start_date = end_date - timedelta(days=730)
                logger.info(f"전체 다운로드: {symbol} ({start_date} ~ {end_date})")
                
                df = stock.get_etf_ohlcv_by_date(
                    fromdate=start_date.strftime("%Y%m%d"),
                    todate=end_date.strftime("%Y%m%d"),
                    ticker=symbol
                )
                
                if df is None or df.empty:
                    logger.warning(f"데이터 없음: {symbol}")
                    return False
                
                # 데이터 정규화
                df = self._normalize_data(df)
                self._write_cache(symbol, df)
                return True
            
            else:
                # 증분 업데이트
                last_date = self.get_last_cached_date(symbol)
                
                if last_date >= end_date:
                    logger.debug(f"업데이트 불필요: {symbol} (최신: {last_date})")
                    return True
                
                # 마지막 날짜 다음날부터 다운로드
                start_date = last_date + timedelta(days=1)
                logger.info(f"증분 업데이트: {symbol} ({start_date} ~ {end_date})")
                
                df_new = stock.get_etf_ohlcv_by_date(
                    fromdate=start_date.strftime("%Y%m%d"),
                    todate=end_date.strftime("%Y%m%d"),
                    ticker=symbol
                )
                
                if df_new is None or df_new.empty:
                    logger.debug(f"신규 데이터 없음: {symbol}")
                    return True
                
                # 데이터 정규화 및 병합
                df_new = self._normalize_data(df_new)
                df_merged = pd.concat([cached, df_new]).sort_index()
                df_merged = df_merged[~df_merged.index.duplicated(keep='last')]
                
                self._write_cache(symbol, df_merged)
                logger.info(f"업데이트 완료: {symbol} (+{len(df_new)} rows)")
                return True
                
        except Exception as e:
            logger.error(f"업데이트 실패 ({symbol}): {e}")
            return False
    
    def update_universe(
        self,
        symbols: List[str],
        end_date: Optional[date] = None,
        force: bool = False
    ) -> Dict[str, bool]:
        """
        유니버스 전체 업데이트
        
        Args:
            symbols: 종목 코드 리스트
            end_date: 종료 날짜
            force: 강제 업데이트
            
        Returns:
            {symbol: success} 딕셔너리
        """
        results = {}
        
        logger.info(f"유니버스 업데이트 시작: {len(symbols)}개 종목")
        
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"[{i}/{len(symbols)}] {symbol} 업데이트 중...")
            results[symbol] = self.update_symbol(symbol, end_date, force)
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"유니버스 업데이트 완료: "
            f"{success_count}/{len(symbols)} 성공"
        )
        
        return results
    
    def _normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        데이터 정규화
        
        Args:
            df: 원본 데이터
            
        Returns:
            정규화된 데이터
        """
        # 1. 컬럼명 변경
        df = df.rename(columns={
            '날짜': 'date',
            '시가': 'open',
            '고가': 'high',
            '저가': 'low',
            '종가': 'close',
            '거래량': 'volume',
            '거래대금': 'value'
        })
        
        # 2. 인덱스 처리
        if 'date' not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
            df.reset_index(inplace=True)
        
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
        
        # 3. 데이터 타입 변환
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'value']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 4. 정렬 및 중복 제거
        df.sort_index(inplace=True)
        df = df[~df.index.duplicated(keep='last')]
        
        return df
    
    def get_update_status(self, symbols: List[str]) -> pd.DataFrame:
        """
        업데이트 상태 조회
        
        Args:
            symbols: 종목 코드 리스트
            
        Returns:
            상태 DataFrame
        """
        status_list = []
        
        for symbol in symbols:
            last_date = self.get_last_cached_date(symbol)
            needs_update = self.needs_update(symbol)
            
            status_list.append({
                'symbol': symbol,
                'last_date': last_date,
                'needs_update': needs_update,
                'days_old': (date.today() - last_date).days if last_date else None
            })
        
        return pd.DataFrame(status_list)


def create_updater(cache_dir: Union[str, Path] = "data/cache") -> DataUpdater:
    """업데이터 생성"""
    return DataUpdater(cache_dir)
