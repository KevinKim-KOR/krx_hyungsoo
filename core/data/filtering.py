# -*- coding: utf-8 -*-
"""
core/data/filtering.py
ETF 필터링 로직 (친구 코드 참고)
"""
from typing import List, Dict, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ETFFilter:
    """ETF 필터링 클래스"""
    
    def __init__(
        self,
        min_liquidity: float = 3e8,  # 최소 거래대금 (3억)
        min_price: float = 1000,  # 최소 가격 (1,000원)
        exclude_keywords: Optional[List[str]] = None,
        exclude_categories: Optional[List[str]] = None
    ):
        """
        Args:
            min_liquidity: 최소 일평균 거래대금 (원)
            min_price: 최소 가격 (원)
            exclude_keywords: 제외할 키워드 리스트
            exclude_categories: 제외할 카테고리 리스트
        """
        self.min_liquidity = min_liquidity
        self.min_price = min_price
        self.exclude_keywords = exclude_keywords or [
            "레버리지", "인버스", "선물", "채권", "커버드콜", "곱버스"
        ]
        self.exclude_categories = exclude_categories or []
    
    def filter_by_name(self, etfs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        ETF 이름 기반 필터링
        
        Args:
            etfs: ETF 정보 리스트 [{'code': str, 'name': str, ...}, ...]
            
        Returns:
            필터링된 ETF 리스트
        """
        filtered = []
        for etf in etfs:
            name = etf.get('name', '')
            if not any(kw in name for kw in self.exclude_keywords):
                filtered.append(etf)
            else:
                logger.debug(f"제외 (키워드): {etf['code']} {name}")
        
        logger.info(f"이름 필터링: {len(etfs)} → {len(filtered)}")
        return filtered
    
    def filter_by_liquidity(
        self,
        etfs: List[Dict[str, Any]],
        price_data: pd.DataFrame,
        lookback_days: int = 20
    ) -> List[Dict[str, Any]]:
        """
        거래대금 기반 필터링
        
        Args:
            etfs: ETF 정보 리스트
            price_data: 가격 데이터 (멀티인덱스: code, date)
            lookback_days: 평균 계산 기간
            
        Returns:
            필터링된 ETF 리스트
        """
        filtered = []
        
        for etf in etfs:
            code = etf['code']
            
            try:
                # 해당 종목 데이터 추출
                if code not in price_data.index.get_level_values('code'):
                    logger.debug(f"데이터 없음: {code}")
                    continue
                
                etf_data = price_data.loc[code]
                
                # 최근 lookback_days 데이터
                recent_data = etf_data.tail(lookback_days)
                
                # 거래대금 확인
                if 'value' in recent_data.columns:
                    avg_value = recent_data['value'].mean()
                    
                    if avg_value >= self.min_liquidity:
                        etf['avg_liquidity'] = float(avg_value)
                        filtered.append(etf)
                    else:
                        logger.debug(
                            f"제외 (거래대금): {code} "
                            f"평균={avg_value:,.0f} < {self.min_liquidity:,.0f}"
                        )
                else:
                    # 거래대금 데이터 없으면 거래량*종가로 추정
                    if 'volume' in recent_data.columns and 'close' in recent_data.columns:
                        avg_value = (recent_data['volume'] * recent_data['close']).mean()
                        
                        if avg_value >= self.min_liquidity:
                            etf['avg_liquidity'] = float(avg_value)
                            filtered.append(etf)
                        else:
                            logger.debug(
                                f"제외 (거래대금 추정): {code} "
                                f"평균={avg_value:,.0f} < {self.min_liquidity:,.0f}"
                            )
                    else:
                        logger.debug(f"거래대금 계산 불가: {code}")
                        
            except Exception as e:
                logger.warning(f"거래대금 필터링 실패 ({code}): {e}")
        
        logger.info(f"거래대금 필터링: {len(etfs)} → {len(filtered)}")
        return filtered
    
    def filter_by_price(
        self,
        etfs: List[Dict[str, Any]],
        price_data: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        가격 기반 필터링
        
        Args:
            etfs: ETF 정보 리스트
            price_data: 가격 데이터 (멀티인덱스: code, date)
            
        Returns:
            필터링된 ETF 리스트
        """
        filtered = []
        
        for etf in etfs:
            code = etf['code']
            
            try:
                # 해당 종목 데이터 추출
                if code not in price_data.index.get_level_values('code'):
                    continue
                
                etf_data = price_data.loc[code]
                
                # 최근 종가
                if 'close' in etf_data.columns:
                    latest_price = etf_data['close'].iloc[-1]
                    
                    if latest_price >= self.min_price:
                        etf['latest_price'] = float(latest_price)
                        filtered.append(etf)
                    else:
                        logger.debug(
                            f"제외 (가격): {code} "
                            f"가격={latest_price:,.0f} < {self.min_price:,.0f}"
                        )
                        
            except Exception as e:
                logger.warning(f"가격 필터링 실패 ({code}): {e}")
        
        logger.info(f"가격 필터링: {len(etfs)} → {len(filtered)}")
        return filtered
    
    def filter_by_category_duplicate(
        self,
        etfs: List[Dict[str, Any]],
        max_per_category: int = 2
    ) -> List[Dict[str, Any]]:
        """
        카테고리 중복 방지 필터링 (친구 코드 참고)
        
        Args:
            etfs: ETF 정보 리스트 (이미 점수순 정렬되어 있어야 함)
            max_per_category: 카테고리당 최대 종목 수
            
        Returns:
            필터링된 ETF 리스트
        """
        category_count: Dict[str, int] = {}
        filtered = []
        
        for etf in etfs:
            cat = etf.get('cat', 'UNKNOWN')
            
            # 카테고리 카운트 확인
            current_count = category_count.get(cat, 0)
            
            if current_count < max_per_category:
                filtered.append(etf)
                category_count[cat] = current_count + 1
            else:
                logger.debug(
                    f"제외 (카테고리 중복): {etf['code']} "
                    f"카테고리={cat} (이미 {current_count}개)"
                )
        
        logger.info(f"카테고리 중복 필터링: {len(etfs)} → {len(filtered)}")
        return filtered
    
    def apply_all_filters(
        self,
        etfs: List[Dict[str, Any]],
        price_data: pd.DataFrame,
        lookback_days: int = 20,
        max_per_category: int = 2
    ) -> List[Dict[str, Any]]:
        """
        모든 필터 적용
        
        Args:
            etfs: ETF 정보 리스트
            price_data: 가격 데이터
            lookback_days: 거래대금 평균 계산 기간
            max_per_category: 카테고리당 최대 종목 수
            
        Returns:
            필터링된 ETF 리스트
        """
        logger.info(f"필터링 시작: 총 {len(etfs)}개 ETF")
        
        # 1. 이름 기반 필터링
        filtered = self.filter_by_name(etfs)
        
        # 2. 거래대금 필터링
        filtered = self.filter_by_liquidity(filtered, price_data, lookback_days)
        
        # 3. 가격 필터링
        filtered = self.filter_by_price(filtered, price_data)
        
        # 4. 카테고리 중복 필터링 (점수순 정렬 후)
        # 주의: 이 필터는 점수 계산 후에 적용해야 함
        # filtered = self.filter_by_category_duplicate(filtered, max_per_category)
        
        logger.info(f"필터링 완료: {len(filtered)}개 ETF")
        return filtered


def create_default_filter() -> ETFFilter:
    """기본 필터 생성"""
    return ETFFilter(
        min_liquidity=3e8,  # 3억
        min_price=1000,  # 1,000원
        exclude_keywords=["레버리지", "인버스", "선물", "채권", "커버드콜", "곱버스"]
    )
