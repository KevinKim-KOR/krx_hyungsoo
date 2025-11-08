# -*- coding: utf-8 -*-
"""
extensions/automation/data_updater.py
데이터 수집 자동화

기능:
- 일별 가격 데이터 자동 수집
- KOSPI 지수 데이터 수집
- 데이터베이스 자동 업데이트
"""

from datetime import date, datetime, timedelta
from typing import Optional, List
import pandas as pd
import logging
from pathlib import Path

from infra.data.loader import load_price_data

logger = logging.getLogger(__name__)


class DataUpdater:
    """
    데이터 수집 자동화 클래스
    
    기능:
    1. 일별 가격 데이터 수집
    2. KOSPI 지수 데이터 수집
    3. 데이터 검증 및 저장
    """
    
    def __init__(self, universe_file: Optional[str] = None):
        """
        Args:
            universe_file: 유니버스 파일 경로
        """
        self.universe_file = universe_file or "data/universe/etf_universe.csv"
        self.kospi_code = "069500"  # KODEX 200
        
    def load_universe(self) -> List[str]:
        """
        유니버스 로드
        
        Returns:
            List[str]: 종목 코드 리스트
        """
        try:
            universe_path = Path(self.universe_file)
            if not universe_path.exists():
                logger.warning(f"유니버스 파일 없음: {self.universe_file}")
                return []
                
            df = pd.read_csv(universe_path)
            # 'code' 또는 'ticker' 컬럼 사용
            code_col = 'code' if 'code' in df.columns else 'ticker'
            codes = df[code_col].astype(str).str.zfill(6).tolist()
            logger.info(f"유니버스 로드: {len(codes)}개 종목")
            return codes
            
        except Exception as e:
            logger.error(f"유니버스 로드 실패: {e}")
            return []
    
    def update_daily_prices(
        self,
        target_date: Optional[date] = None,
        codes: Optional[List[str]] = None
    ) -> bool:
        """
        일별 가격 데이터 업데이트
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
            codes: 종목 코드 리스트 (None이면 유니버스 전체)
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 날짜 설정
            if target_date is None:
                target_date = date.today()
            
            # 주말이면 금요일로 조정
            if target_date.weekday() >= 5:  # 토요일(5), 일요일(6)
                days_back = target_date.weekday() - 4
                target_date = target_date - timedelta(days=days_back)
            
            logger.info(f"데이터 업데이트 시작: {target_date}")
            
            # 종목 코드 로드
            if codes is None:
                codes = self.load_universe()
                if not codes:
                    logger.error("종목 코드가 없습니다")
                    return False
            
            # KOSPI 지수 추가
            if self.kospi_code not in codes:
                codes.append(self.kospi_code)
            
            # 데이터 수집
            start_date = target_date - timedelta(days=7)  # 최근 1주일
            end_date = target_date
            
            logger.info(f"데이터 수집: {start_date} ~ {end_date}")
            
            price_data = load_price_data(
                universe=codes,
                start_date=start_date,
                end_date=end_date
            )
            
            if price_data.empty:
                logger.warning("수집된 데이터가 없습니다")
                return False
            
            # 데이터 검증
            target_data = price_data[
                price_data.index.get_level_values('date') == pd.Timestamp(target_date)
            ]
            
            if target_data.empty:
                logger.warning(f"{target_date}의 데이터가 없습니다 (휴장일일 수 있음)")
                return False
            
            logger.info(f"✅ 데이터 업데이트 완료: {len(target_data)}개 종목")
            return True
            
        except Exception as e:
            logger.error(f"데이터 업데이트 실패: {e}")
            return False
    
    def update_kospi_index(
        self,
        target_date: Optional[date] = None
    ) -> Optional[pd.DataFrame]:
        """
        KOSPI 지수 데이터 업데이트
        
        Args:
            target_date: 대상 날짜 (None이면 오늘)
        
        Returns:
            Optional[pd.DataFrame]: KOSPI 데이터 (실패 시 None)
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            logger.info(f"KOSPI 지수 업데이트: {target_date}")
            
            # 최근 1년 데이터 수집 (레짐 감지용)
            start_date = target_date - timedelta(days=365)
            end_date = target_date
            
            price_data = load_price_data(
                universe=[self.kospi_code],
                start_date=start_date,
                end_date=end_date
            )
            
            if price_data.empty:
                logger.warning("KOSPI 데이터가 없습니다")
                return None
            
            # KODEX 200 데이터 추출
            kospi_data = price_data.xs(
                self.kospi_code,
                level='code'
            ).copy()
            
            # 컬럼명 정규화
            kospi_data.columns = [col.capitalize() for col in kospi_data.columns]
            
            logger.info(f"✅ KOSPI 데이터 업데이트 완료: {len(kospi_data)}일")
            return kospi_data
            
        except Exception as e:
            logger.error(f"KOSPI 업데이트 실패: {e}")
            return None
    
    def get_latest_date(self) -> Optional[date]:
        """
        최신 데이터 날짜 조회
        
        Returns:
            Optional[date]: 최신 날짜 (데이터 없으면 None)
        """
        try:
            # 최근 1주일 데이터 조회
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            
            price_data = load_price_data(
                universe=[self.kospi_code],
                start_date=start_date,
                end_date=end_date
            )
            
            if price_data.empty:
                return None
            
            # 최신 날짜 추출
            latest_date = price_data.index.get_level_values('date').max()
            return latest_date.date()
            
        except Exception as e:
            logger.error(f"최신 날짜 조회 실패: {e}")
            return None
