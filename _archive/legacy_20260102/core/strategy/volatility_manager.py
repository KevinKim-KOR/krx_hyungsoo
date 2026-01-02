# -*- coding: utf-8 -*-
"""
core/strategy/volatility_manager.py
변동성 관리 시스템

목표: 변동성 기반 포지션 조정으로 MDD 개선
"""
from typing import Dict, Optional, Tuple
from datetime import date
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class VolatilityManager:
    """
    변동성 관리자
    
    기능:
    1. ATR (Average True Range) 계산
    2. 변동성 레벨 분류 (낮음/중간/높음)
    3. 포지션 크기 동적 조정
    
    목표:
    - 고변동성 시 포지션 축소 → MDD 감소
    - 저변동성 시 포지션 확대 → 수익률 증대
    """
    
    def __init__(
        self,
        # ATR 파라미터
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        
        # 변동성 레벨 임계값
        low_volatility_threshold: float = 0.5,  # ATR 평균 대비
        high_volatility_threshold: float = 1.5,
        
        # 포지션 조정 비율
        low_volatility_position_ratio: float = 1.2,  # 120%
        normal_volatility_position_ratio: float = 1.0,  # 100%
        high_volatility_position_ratio: float = 0.6,  # 60%
        
        # 활성화 플래그
        enable_volatility_adjustment: bool = True
    ):
        """
        Args:
            atr_period: ATR 계산 기간 (일)
            atr_multiplier: ATR 배수 (변동성 판단)
            low_volatility_threshold: 저변동성 임계값
            high_volatility_threshold: 고변동성 임계값
            low_volatility_position_ratio: 저변동성 시 포지션 비율
            normal_volatility_position_ratio: 정상 변동성 시 포지션 비율
            high_volatility_position_ratio: 고변동성 시 포지션 비율
            enable_volatility_adjustment: 변동성 조정 활성화
        """
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.low_volatility_threshold = low_volatility_threshold
        self.high_volatility_threshold = high_volatility_threshold
        
        self.low_volatility_position_ratio = low_volatility_position_ratio
        self.normal_volatility_position_ratio = normal_volatility_position_ratio
        self.high_volatility_position_ratio = high_volatility_position_ratio
        
        self.enable_volatility_adjustment = enable_volatility_adjustment
        
        # 통계
        self.stats = {
            'low_volatility_days': 0,
            'normal_volatility_days': 0,
            'high_volatility_days': 0,
            'total_adjustments': 0
        }
        
        logger.info(f"VolatilityManager 초기화: "
                   f"ATR={atr_period}일, "
                   f"임계값={low_volatility_threshold}/{high_volatility_threshold}, "
                   f"비율={low_volatility_position_ratio}/{normal_volatility_position_ratio}/{high_volatility_position_ratio}")
    
    def calculate_atr(
        self,
        price_data: pd.DataFrame,
        current_date: date
    ) -> Optional[float]:
        """
        ATR (Average True Range) 계산
        
        ATR = MA(True Range, period)
        True Range = max(high - low, |high - prev_close|, |low - prev_close|)
        
        Args:
            price_data: 가격 데이터 (Date 인덱스, High/Low/Close 컬럼)
            current_date: 현재 날짜
        
        Returns:
            float: ATR 값 (None이면 계산 불가)
        """
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = price_data[price_data.index <= current_ts]
            
            if len(hist_data) < self.atr_period + 1:
                return None
            
            # 최근 N+1일 데이터 (이전 종가 필요)
            recent_data = hist_data.tail(self.atr_period + 1).copy()
            
            # 컬럼명 정규화 (소문자 → 대문자)
            col_mapping = {}
            for col in recent_data.columns:
                if col.lower() == 'high':
                    col_mapping[col] = 'High'
                elif col.lower() == 'low':
                    col_mapping[col] = 'Low'
                elif col.lower() == 'close':
                    col_mapping[col] = 'Close'
            
            if col_mapping:
                recent_data = recent_data.rename(columns=col_mapping)
            
            # True Range 계산
            recent_data['prev_close'] = recent_data['Close'].shift(1)
            
            recent_data['tr1'] = recent_data['High'] - recent_data['Low']
            recent_data['tr2'] = abs(recent_data['High'] - recent_data['prev_close'])
            recent_data['tr3'] = abs(recent_data['Low'] - recent_data['prev_close'])
            
            recent_data['true_range'] = recent_data[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # ATR = True Range의 이동평균
            atr = recent_data['true_range'].iloc[1:].mean()  # 첫 행 제외 (prev_close NaN)
            
            return float(atr)
            
        except Exception as e:
            logger.error(f"ATR 계산 실패: {e}")
            return None
    
    def classify_volatility(
        self,
        current_atr: float,
        avg_atr: float
    ) -> Tuple[str, float]:
        """
        변동성 레벨 분류
        
        Args:
            current_atr: 현재 ATR
            avg_atr: 평균 ATR (기준)
        
        Returns:
            tuple: (변동성 레벨, 포지션 비율)
        """
        if avg_atr <= 0:
            return 'normal', self.normal_volatility_position_ratio
        
        # ATR 비율 계산
        atr_ratio = current_atr / avg_atr
        
        # 변동성 레벨 분류
        if atr_ratio <= self.low_volatility_threshold:
            self.stats['low_volatility_days'] += 1
            return 'low', self.low_volatility_position_ratio
        elif atr_ratio >= self.high_volatility_threshold:
            self.stats['high_volatility_days'] += 1
            return 'high', self.high_volatility_position_ratio
        else:
            self.stats['normal_volatility_days'] += 1
            return 'normal', self.normal_volatility_position_ratio
    
    def calculate_position_size(
        self,
        base_position_size: float,
        market_data: pd.DataFrame,
        current_date: date,
        historical_atr: Optional[float] = None
    ) -> Tuple[float, str]:
        """
        변동성 기반 포지션 크기 계산
        
        Args:
            base_position_size: 기본 포지션 크기
            market_data: 시장 데이터 (KOSPI)
            current_date: 현재 날짜
            historical_atr: 과거 평균 ATR (None이면 자동 계산)
        
        Returns:
            tuple: (조정된 포지션 크기, 변동성 레벨)
        """
        if not self.enable_volatility_adjustment:
            return base_position_size, 'normal'
        
        try:
            # 현재 ATR 계산
            current_atr = self.calculate_atr(market_data, current_date)
            
            if current_atr is None:
                return base_position_size, 'normal'
            
            # 평균 ATR 계산 (과거 60일)
            if historical_atr is None:
                current_ts = pd.Timestamp(current_date)
                hist_data = market_data[market_data.index <= current_ts]
                
                if len(hist_data) < 60:
                    return base_position_size, 'normal'
                
                # 과거 60일 ATR 평균
                atr_values = []
                for i in range(60):
                    date_i = hist_data.index[-60 + i]
                    atr_i = self.calculate_atr(market_data, date_i.date())
                    if atr_i is not None:
                        atr_values.append(atr_i)
                
                if not atr_values:
                    return base_position_size, 'normal'
                
                historical_atr = np.mean(atr_values)
            
            # 변동성 레벨 분류
            volatility_level, position_ratio = self.classify_volatility(
                current_atr, historical_atr
            )
            
            # 포지션 크기 조정
            adjusted_position_size = base_position_size * position_ratio
            
            self.stats['total_adjustments'] += 1
            
            if volatility_level != 'normal':
                logger.info(f"{current_date}: {volatility_level} 변동성 감지 "
                          f"(ATR={current_atr:.4f}, 평균={historical_atr:.4f}, "
                          f"비율={position_ratio:.2f})")
            
            return adjusted_position_size, volatility_level
            
        except Exception as e:
            logger.error(f"포지션 크기 계산 실패: {e}")
            return base_position_size, 'normal'
    
    def calculate_portfolio_volatility(
        self,
        positions: Dict,
        price_data: Dict[str, pd.DataFrame],
        current_date: date
    ) -> Optional[float]:
        """
        포트폴리오 전체 변동성 계산
        
        Args:
            positions: 보유 포지션
            price_data: 가격 데이터
            current_date: 현재 날짜
        
        Returns:
            float: 포트폴리오 변동성 (None이면 계산 불가)
        """
        try:
            if not positions:
                return None
            
            atr_values = []
            
            for ticker, position in positions.items():
                if ticker not in price_data:
                    continue
                
                ticker_data = price_data[ticker]
                atr = self.calculate_atr(ticker_data, current_date)
                
                if atr is not None:
                    # 가격 대비 ATR 비율
                    current_ts = pd.Timestamp(current_date)
                    current_price = ticker_data[ticker_data.index <= current_ts]['Close'].iloc[-1]
                    
                    if current_price > 0:
                        atr_pct = (atr / current_price) * 100
                        atr_values.append(atr_pct)
            
            if not atr_values:
                return None
            
            # 평균 ATR 비율
            portfolio_volatility = np.mean(atr_values)
            
            return float(portfolio_volatility)
            
        except Exception as e:
            logger.error(f"포트폴리오 변동성 계산 실패: {e}")
            return None
    
    def get_stats(self) -> Dict:
        """
        통계 조회
        
        Returns:
            dict: 변동성 관리 통계
        """
        total_days = sum([
            self.stats['low_volatility_days'],
            self.stats['normal_volatility_days'],
            self.stats['high_volatility_days']
        ])
        
        return {
            **self.stats,
            'total_days': total_days,
            'low_volatility_pct': (self.stats['low_volatility_days'] / total_days * 100) if total_days > 0 else 0,
            'high_volatility_pct': (self.stats['high_volatility_days'] / total_days * 100) if total_days > 0 else 0
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'low_volatility_days': 0,
            'normal_volatility_days': 0,
            'high_volatility_days': 0,
            'total_adjustments': 0
        }


__all__ = ['VolatilityManager']
