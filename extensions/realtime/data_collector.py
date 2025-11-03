# -*- coding: utf-8 -*-
"""
extensions/realtime/data_collector.py
실시간 데이터 수집 및 캐시 업데이트
"""
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional
import pandas as pd
from pykrx import stock

logger = logging.getLogger(__name__)


class RealtimeDataCollector:
    """실시간 데이터 수집기"""
    
    def __init__(self, cache_dir: Path = None):
        """
        Args:
            cache_dir: 캐시 디렉토리 경로
        """
        self.cache_dir = cache_dir or Path('data/cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def update_latest(self, target_date: date = None) -> bool:
        """
        최신 데이터 수집 및 캐시 업데이트
        
        Args:
            target_date: 수집할 날짜 (None이면 오늘)
            
        Returns:
            성공 여부
        """
        if target_date is None:
            target_date = datetime.now().date()
        
        logger.info(f"데이터 수집 시작: {target_date}")
        
        try:
            # 1. 유니버스 로드
            universe = self._get_universe()
            logger.info(f"유니버스: {len(universe)}개 종목")
            
            # 2. 각 종목 데이터 업데이트
            success_count = 0
            fail_count = 0
            
            for i, code in enumerate(universe, 1):
                try:
                    if self._update_symbol(code, target_date):
                        success_count += 1
                    else:
                        fail_count += 1
                    
                    if i % 50 == 0:
                        logger.info(f"진행: {i}/{len(universe)} ({success_count} 성공, {fail_count} 실패)")
                
                except Exception as e:
                    logger.error(f"[{code}] 업데이트 실패: {e}")
                    fail_count += 1
            
            logger.info(f"데이터 수집 완료: {success_count}/{len(universe)} 성공")
            
            # 3. 성공률 검증
            success_rate = success_count / len(universe) if universe else 0
            if success_rate < 0.8:
                logger.warning(f"성공률 낮음: {success_rate:.1%}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"데이터 수집 실패: {e}")
            return False
    
    def _get_universe(self) -> List[str]:
        """유니버스 로드 (캐시 기반)"""
        # 캐시 파일 목록에서 종목 코드 추출
        codes = [f.stem for f in self.cache_dir.glob('*.parquet')]
        return sorted([c for c in codes if len(c) == 6])
    
    def _update_symbol(self, code: str, target_date: date) -> bool:
        """
        개별 종목 데이터 업데이트
        
        Args:
            code: 종목 코드
            target_date: 수집 날짜
            
        Returns:
            성공 여부
        """
        cache_file = self.cache_dir / f"{code}.parquet"
        
        try:
            # 1. 기존 캐시 로드
            if cache_file.exists():
                existing_df = pd.read_parquet(cache_file, engine='pyarrow')
                
                # 인덱스를 date 컬럼으로 변환
                if existing_df.index.name in ['날짜', 'date']:
                    existing_df = existing_df.reset_index()
                    existing_df = existing_df.rename(columns={'날짜': 'date'})
                
                # 날짜 타입 확인
                if 'date' in existing_df.columns:
                    existing_df['date'] = pd.to_datetime(existing_df['date']).dt.date
                    
                    # 이미 최신 데이터가 있는지 확인
                    if target_date in existing_df['date'].values:
                        return True
                    
                    # 마지막 날짜 확인
                    last_date = existing_df['date'].max()
                else:
                    existing_df = pd.DataFrame()
                    last_date = target_date - timedelta(days=365)
            else:
                existing_df = pd.DataFrame()
                last_date = target_date - timedelta(days=365)
            
            # 2. 신규 데이터 수집
            from_date = last_date + timedelta(days=1)
            to_date = target_date
            
            if from_date > to_date:
                return True  # 이미 최신
            
            new_df = stock.get_etf_ohlcv_by_date(
                fromdate=from_date.strftime("%Y%m%d"),
                todate=to_date.strftime("%Y%m%d"),
                ticker=code
            )
            
            if new_df is None or len(new_df) == 0:
                return False
            
            # 3. 데이터 정리
            new_df = new_df.reset_index()
            new_df = new_df.rename(columns={
                'index': 'date',
                '날짜': 'date',
                '종가': 'close',
                '시가': 'open',
                '고가': 'high',
                '저가': 'low',
                '거래량': 'volume',
                '거래대금': 'value'
            })
            
            # 날짜 타입 변환
            if 'date' in new_df.columns:
                new_df['date'] = pd.to_datetime(new_df['date']).dt.date
            
            # 숫자 컬럼 변환
            numeric_columns = ['close', 'open', 'high', 'low', 'volume', 'value']
            for col in numeric_columns:
                if col in new_df.columns:
                    new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
            
            # 4. 기존 데이터와 병합
            if not existing_df.empty:
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['date'], keep='last')
                combined_df = combined_df.sort_values('date')
            else:
                combined_df = new_df
            
            # 5. 캐시 저장
            combined_df.set_index('date', inplace=True)
            combined_df.to_parquet(cache_file, engine='pyarrow')
            
            return True
        
        except Exception as e:
            logger.error(f"[{code}] 업데이트 실패: {e}")
            return False
    
    def validate_data(self, target_date: date = None) -> dict:
        """
        데이터 품질 검증
        
        Args:
            target_date: 검증 날짜
            
        Returns:
            검증 결과 딕셔너리
        """
        if target_date is None:
            target_date = datetime.now().date()
        
        universe = self._get_universe()
        
        results = {
            'total': len(universe),
            'valid': 0,
            'missing': 0,
            'outdated': 0,
            'corrupted': 0
        }
        
        for code in universe:
            cache_file = self.cache_dir / f"{code}.parquet"
            
            if not cache_file.exists():
                results['missing'] += 1
                continue
            
            try:
                df = pd.read_parquet(cache_file, engine='pyarrow')
                
                if df.empty:
                    results['corrupted'] += 1
                    continue
                
                # 날짜 확인
                if df.index.name in ['날짜', 'date']:
                    last_date = pd.to_datetime(df.index.max()).date()
                elif 'date' in df.columns:
                    last_date = pd.to_datetime(df['date'].max()).date()
                else:
                    results['corrupted'] += 1
                    continue
                
                # 최신 여부 확인
                if last_date < target_date:
                    results['outdated'] += 1
                else:
                    results['valid'] += 1
            
            except Exception as e:
                logger.error(f"[{code}] 검증 실패: {e}")
                results['corrupted'] += 1
        
        return results
