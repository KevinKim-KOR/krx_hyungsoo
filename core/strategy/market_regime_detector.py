# -*- coding: utf-8 -*-
"""
core/strategy/market_regime_detector.py
시장 레짐 감지 시스템

목표: 시장 상황에 따른 동적 전략 전환

Week 3 최종 버전 (2025-11-08)
- MA 50/200일 기반 레짐 분류
- 포지션 비율: 상승장 100~120%, 중립장 80%, 하락장 40~60%
- 방어 모드: 신뢰도 85% 이상만 매수 스킵
- 성과: CAGR 27.05%, Sharpe 1.51, MDD -19.92%
"""
from typing import Dict, Optional, Tuple
from datetime import date
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    시장 레짐 감지기
    
    기능:
    1. 시장 추세 분석 (이동평균 기반)
    2. 레짐 분류 (상승장/하락장/중립장)
    3. 추세 강도 측정
    
    목표:
    - 상승장: 공격적 전략 (100% 포지션)
    - 하락장: 방어적 전략 (현금 보유)
    - 중립장: 혼합 전략 (50% 포지션)
    """
    
    def __init__(
        self,
        # 이동평균 파라미터
        short_ma_period: int = 50,  # 단기 이동평균
        long_ma_period: int = 200,  # 장기 이동평균
        
        # 레짐 분류 임계값
        bull_threshold: float = 0.02,  # 상승장: 단기MA > 장기MA + 2%
        bear_threshold: float = -0.02,  # 하락장: 단기MA < 장기MA - 2%
        
        # 추세 강도 파라미터
        trend_strength_period: int = 20,  # 추세 강도 계산 기간
        
        # 활성화 플래그
        enable_regime_detection: bool = True
    ):
        """
        Args:
            short_ma_period: 단기 이동평균 기간
            long_ma_period: 장기 이동평균 기간
            bull_threshold: 상승장 임계값 (%)
            bear_threshold: 하락장 임계값 (%)
            trend_strength_period: 추세 강도 계산 기간
            enable_regime_detection: 레짐 감지 활성화
        """
        self.short_ma_period = short_ma_period
        self.long_ma_period = long_ma_period
        self.bull_threshold = bull_threshold
        self.bear_threshold = bear_threshold
        self.trend_strength_period = trend_strength_period
        self.enable_regime_detection = enable_regime_detection
        
        # 현재 레짐
        self.current_regime: str = 'neutral'
        
        # 통계
        self.stats = {
            'bull_days': 0,
            'bear_days': 0,
            'neutral_days': 0,
            'regime_changes': 0
        }
        
        logger.info(f"MarketRegimeDetector 초기화: "
                   f"MA={short_ma_period}/{long_ma_period}일, "
                   f"임계값={bull_threshold*100}/{bear_threshold*100}%")
    
    def calculate_moving_averages(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        이동평균 계산
        
        Args:
            market_data: 시장 데이터 (Date 인덱스, Close 컬럼)
            current_date: 현재 날짜
        
        Returns:
            tuple: (단기MA, 장기MA)
        """
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < self.long_ma_period:
                return None, None
            
            # 단기 이동평균
            short_ma = hist_data['Close'].tail(self.short_ma_period).mean()
            
            # 장기 이동평균
            long_ma = hist_data['Close'].tail(self.long_ma_period).mean()
            
            return float(short_ma.iloc[0] if hasattr(short_ma, 'iloc') else short_ma), \
                   float(long_ma.iloc[0] if hasattr(long_ma, 'iloc') else long_ma)
            
        except Exception as e:
            logger.error(f"이동평균 계산 실패: {e}")
            return None, None
    
    def calculate_trend_strength(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Optional[float]:
        """
        추세 강도 계산
        
        방법: 최근 N일간 상승일 비율
        
        Args:
            market_data: 시장 데이터
            current_date: 현재 날짜
        
        Returns:
            float: 추세 강도 (0~1, 1이 가장 강한 상승)
        """
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < self.trend_strength_period:
                return None
            
            # 최근 N일 데이터
            recent_data = hist_data.tail(self.trend_strength_period)
            
            # 일별 수익률
            daily_returns = recent_data['Close'].pct_change()
            
            # 상승일 비율
            up_days = (daily_returns > 0).sum()
            total_days = len(daily_returns) - 1  # NaN 제외
            
            if total_days == 0:
                return None
            
            trend_strength = up_days / total_days
            
            return float(trend_strength.iloc[0] if hasattr(trend_strength, 'iloc') else trend_strength)
            
        except Exception as e:
            logger.error(f"추세 강도 계산 실패: {e}")
            return None
    
    def detect_regime(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Tuple[str, float]:
        """
        시장 레짐 감지
        
        Args:
            market_data: 시장 데이터 (KOSPI)
            current_date: 현재 날짜
        
        Returns:
            tuple: (레짐, 신뢰도)
        """
        if not self.enable_regime_detection:
            return 'neutral', 0.5
        
        try:
            # 이동평균 계산
            short_ma, long_ma = self.calculate_moving_averages(market_data, current_date)
            
            if short_ma is None or long_ma is None:
                return 'neutral', 0.5
            
            # MA 차이 비율
            ma_diff_pct = (short_ma / long_ma - 1.0)
            
            # 추세 강도 계산
            trend_strength = self.calculate_trend_strength(market_data, current_date)
            if trend_strength is None:
                trend_strength = 0.5
            
            # 레짐 분류
            prev_regime = self.current_regime
            
            if ma_diff_pct >= self.bull_threshold:
                # 상승장
                regime = 'bull'
                confidence = min(1.0, 0.5 + ma_diff_pct * 10)  # 차이가 클수록 신뢰도 증가
                self.stats['bull_days'] += 1
                
            elif ma_diff_pct <= self.bear_threshold:
                # 하락장
                regime = 'bear'
                confidence = min(1.0, 0.5 + abs(ma_diff_pct) * 10)
                self.stats['bear_days'] += 1
                
            else:
                # 중립장
                regime = 'neutral'
                confidence = 0.5
                self.stats['neutral_days'] += 1
            
            # 레짐 변경 감지
            if regime != prev_regime:
                self.stats['regime_changes'] += 1
                logger.info(f"레짐 변경! {current_date}: {prev_regime} → {regime} "
                          f"(MA차이={ma_diff_pct*100:.2f}%, 추세강도={trend_strength:.2f})")
            
            self.current_regime = regime
            
            return regime, confidence
            
        except Exception as e:
            logger.error(f"레짐 감지 실패: {e}")
            return 'neutral', 0.5
    
    def get_position_ratio(
        self,
        regime: str,
        confidence: float
    ) -> float:
        """
        레짐에 따른 포지션 비율 계산 (개선된 버전)
        
        Args:
            regime: 시장 레짐
            confidence: 신뢰도
        
        Returns:
            float: 포지션 비율 (0.4~1.2)
        """
        if regime == 'bull':
            # 상승장: 100~120% 포지션 (신뢰도에 따라)
            return 1.0 + (confidence - 0.5) * 0.4
            
        elif regime == 'bear':
            # 하락장: 40~60% 포지션 (신뢰도에 따라, 개선!)
            # 신뢰도 높을수록 포지션 감소
            return 0.6 - (confidence - 0.5) * 0.4
            
        else:
            # 중립장: 80% 포지션 (개선!)
            return 0.8
    
    def should_enter_defense_mode(
        self,
        regime: str,
        confidence: float
    ) -> bool:
        """
        방어 모드 진입 여부 (완화된 버전)
        
        Args:
            regime: 시장 레짐
            confidence: 신뢰도
        
        Returns:
            bool: True면 방어 모드 진입 (매수 스킵)
        """
        # 하락장이고 신뢰도가 매우 높을 때만 방어 모드 (완화!)
        # 0.7 → 0.85로 상향 조정하여 덜 방어적으로
        return regime == 'bear' and confidence >= 0.85
    
    def get_stats(self) -> Dict:
        """
        통계 조회
        
        Returns:
            dict: 레짐 감지 통계
        """
        total_days = sum([
            self.stats['bull_days'],
            self.stats['bear_days'],
            self.stats['neutral_days']
        ])
        
        return {
            **self.stats,
            'total_days': total_days,
            'bull_pct': (self.stats['bull_days'] / total_days * 100) if total_days > 0 else 0,
            'bear_pct': (self.stats['bear_days'] / total_days * 100) if total_days > 0 else 0,
            'neutral_pct': (self.stats['neutral_days'] / total_days * 100) if total_days > 0 else 0,
            'current_regime': self.current_regime
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'bull_days': 0,
            'bear_days': 0,
            'neutral_days': 0,
            'regime_changes': 0
        }
        self.current_regime = 'neutral'


__all__ = ['MarketRegimeDetector']
