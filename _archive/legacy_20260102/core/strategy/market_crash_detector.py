# -*- coding: utf-8 -*-
"""
core/strategy/market_crash_detector.py
시장 급락 감지 시스템

목표: 시장 전체 급락 시 방어 모드 전환
"""
from typing import Dict, Optional, Tuple
from datetime import date, datetime, timedelta
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class MarketCrashDetector:
    """
    시장 급락 감지기
    
    기능:
    1. KOSPI 급락 감지 (5일간 -10%)
    2. 보유 종목 동반 하락 감지 (80% 이상)
    3. 방어 모드 전환 관리
    
    목표:
    - 시장 급락 시 손실 최소화
    - 불필요한 청산 방지
    """
    
    def __init__(
        self,
        # KOSPI 급락 파라미터 (개선)
        single_day_crash_threshold: float = -5.0,  # 단일 급락
        short_term_crash_threshold: float = -7.0,  # 단기 급락
        short_term_crash_period: int = 3,  # 3일
        
        # 보유 종목 하락 파라미터 (완화)
        portfolio_decline_threshold: float = 0.6,  # 60% 이상
        portfolio_decline_pct: float = -5.0,  # -5% 이상 하락
        
        # 방어 모드 파라미터
        defense_mode_duration: int = 5,  # 5일간 방어 모드 유지
        
        # 활성화 플래그
        enable_market_crash: bool = True,
        enable_portfolio_decline: bool = True
    ):
        """
        Args:
            single_day_crash_threshold: 단일 급락 임계값 (%)
            short_term_crash_threshold: 단기 급락 임계값 (%)
            short_term_crash_period: 단기 급락 판단 기간 (일)
            portfolio_decline_threshold: 보유 종목 하락 비율 (0~1)
            portfolio_decline_pct: 하락 임계값 (%)
            defense_mode_duration: 방어 모드 유지 기간 (일)
            enable_market_crash: KOSPI 급락 감지 활성화
            enable_portfolio_decline: 보유 종목 하락 감지 활성화
        """
        self.single_day_crash_threshold = single_day_crash_threshold
        self.short_term_crash_threshold = short_term_crash_threshold
        self.short_term_crash_period = short_term_crash_period
        self.portfolio_decline_threshold = portfolio_decline_threshold
        self.portfolio_decline_pct = portfolio_decline_pct
        self.defense_mode_duration = defense_mode_duration
        
        self.enable_market_crash = enable_market_crash
        self.enable_portfolio_decline = enable_portfolio_decline
        
        # 방어 모드 상태
        self.defense_mode_start_date: Optional[date] = None
        self.is_defense_mode: bool = False
        
        # 통계
        self.stats = {
            'market_crash_count': 0,
            'portfolio_decline_count': 0,
            'defense_mode_days': 0
        }
        
        logger.info(f"MarketCrashDetector 초기화: "
                   f"single_day={single_day_crash_threshold}%, "
                   f"short_term={short_term_crash_threshold}%/{short_term_crash_period}일, "
                   f"portfolio_decline={portfolio_decline_threshold*100}%/{portfolio_decline_pct}%")
    
    def detect_market_crash(
        self,
        market_data: pd.DataFrame,
        current_date: date
    ) -> Tuple[bool, Optional[str]]:
        """
        KOSPI 급락 감지 (개선)
        
        조건:
        1. 단일 급락: 당일 Low가 전일 Close 대비 -5% 이상
        2. 단기 급락: 최근 3일 Low가 3일 전 Close 대비 -7% 이상
        3. 롤링 최저점 기준 계산
        
        Args:
            market_data: KOSPI 데이터 (Date 인덱스, Close/Low 컬럼)
            current_date: 현재 날짜
        
        Returns:
            tuple: (급락 여부, 이유)
        """
        if not self.enable_market_crash:
            return False, None
        
        try:
            # 현재 날짜까지의 데이터
            current_ts = pd.Timestamp(current_date)
            hist_data = market_data[market_data.index <= current_ts]
            
            if len(hist_data) < 2:
                return False, None
            
            # 1. 단일 급락 감지 (당일 Low vs 전일 Close)
            if len(hist_data) >= 2:
                prev_close = float(hist_data['Close'].iloc[-2])
                current_low = float(hist_data['Low'].iloc[-1]) if 'Low' in hist_data.columns else float(hist_data['Close'].iloc[-1])
                
                if prev_close > 0:
                    single_day_return = ((current_low / prev_close) - 1.0) * 100
                    
                    if single_day_return <= self.single_day_crash_threshold:
                        logger.warning(f"단일 급락 감지! {current_date}: "
                                     f"당일 Low {single_day_return:.2f}%")
                        self.stats['market_crash_count'] += 1
                        return True, f"single_day_crash_{single_day_return:.2f}%"
            
            # 2. 단기 급락 감지 (최근 N일 Low vs N일 전 Close)
            if len(hist_data) >= self.short_term_crash_period + 1:
                recent_data = hist_data.tail(self.short_term_crash_period + 1)
                
                # N일 전 Close
                start_close = float(recent_data['Close'].iloc[0])
                
                # 최근 N일 중 최저 Low
                recent_lows = recent_data['Low'].iloc[1:] if 'Low' in recent_data.columns else recent_data['Close'].iloc[1:]
                min_low = float(recent_lows.min())
                
                if start_close > 0:
                    short_term_return = ((min_low / start_close) - 1.0) * 100
                    
                    if short_term_return <= self.short_term_crash_threshold:
                        logger.warning(f"단기 급락 감지! {current_date}: "
                                     f"{self.short_term_crash_period}일간 최저 {short_term_return:.2f}%")
                        self.stats['market_crash_count'] += 1
                        return True, f"short_term_crash_{short_term_return:.2f}%"
            
            return False, None
            
        except Exception as e:
            logger.error(f"시장 급락 감지 실패: {e}")
            return False, None
    
    def detect_portfolio_decline(
        self,
        positions: Dict,
        current_prices: Dict[str, float],
        previous_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """
        보유 종목 동반 하락 감지
        
        조건: 80% 이상 종목이 -5% 이상 하락
        
        Args:
            positions: 보유 포지션 {ticker: Position}
            current_prices: 현재 가격 {ticker: price}
            previous_prices: 이전 가격 {ticker: price}
        
        Returns:
            tuple: (하락 여부, 이유)
        """
        if not self.enable_portfolio_decline:
            return False, None
        
        if not positions:
            return False, None
        
        try:
            declining_count = 0
            total_count = 0
            
            for ticker, position in positions.items():
                if ticker not in current_prices or ticker not in previous_prices:
                    continue
                
                current_price = current_prices[ticker]
                previous_price = previous_prices[ticker]
                
                if previous_price <= 0:
                    continue
                
                # 수익률 계산
                return_pct = ((current_price / previous_price) - 1.0) * 100
                
                total_count += 1
                
                # 하락 체크
                if return_pct <= self.portfolio_decline_pct:
                    declining_count += 1
            
            if total_count == 0:
                return False, None
            
            # 하락 비율 계산
            decline_ratio = declining_count / total_count
            
            # 동반 하락 체크
            if decline_ratio >= self.portfolio_decline_threshold:
                logger.warning(f"보유 종목 동반 하락 감지! "
                             f"{declining_count}/{total_count}개 종목 하락 ({decline_ratio*100:.1f}%)")
                self.stats['portfolio_decline_count'] += 1
                return True, f"portfolio_decline_{decline_ratio*100:.1f}%"
            
            return False, None
            
        except Exception as e:
            logger.error(f"보유 종목 하락 감지 실패: {e}")
            return False, None
    
    def check_crash(
        self,
        market_data: pd.DataFrame,
        current_date: date,
        positions: Dict,
        current_prices: Dict[str, float],
        previous_prices: Dict[str, float]
    ) -> Tuple[bool, Optional[str]]:
        """
        종합 급락 감지
        
        Args:
            market_data: KOSPI 데이터
            current_date: 현재 날짜
            positions: 보유 포지션
            current_prices: 현재 가격
            previous_prices: 이전 가격
        
        Returns:
            tuple: (급락 여부, 이유)
        """
        # 1. KOSPI 급락 감지
        market_crash, reason1 = self.detect_market_crash(market_data, current_date)
        if market_crash:
            return True, reason1
        
        # 2. 보유 종목 동반 하락 감지
        portfolio_decline, reason2 = self.detect_portfolio_decline(
            positions, current_prices, previous_prices
        )
        if portfolio_decline:
            return True, reason2
        
        return False, None
    
    def enter_defense_mode(self, current_date: date, reason: str):
        """
        방어 모드 진입
        
        Args:
            current_date: 현재 날짜
            reason: 진입 이유
        """
        self.is_defense_mode = True
        self.defense_mode_start_date = current_date
        logger.warning(f"방어 모드 진입! {current_date}: {reason}")
    
    def exit_defense_mode(self, current_date: date):
        """
        방어 모드 해제
        
        Args:
            current_date: 현재 날짜
        """
        self.is_defense_mode = False
        self.defense_mode_start_date = None
        logger.info(f"방어 모드 해제! {current_date}")
    
    def update_defense_mode(self, current_date: date):
        """
        방어 모드 상태 업데이트
        
        Args:
            current_date: 현재 날짜
        """
        if not self.is_defense_mode:
            return
        
        if self.defense_mode_start_date is None:
            return
        
        # 방어 모드 유지 기간 체크
        days_in_defense = (current_date - self.defense_mode_start_date).days
        
        if days_in_defense >= self.defense_mode_duration:
            self.exit_defense_mode(current_date)
        else:
            self.stats['defense_mode_days'] += 1
    
    def is_in_defense_mode(self) -> bool:
        """
        방어 모드 여부
        
        Returns:
            bool: True면 방어 모드
        """
        return self.is_defense_mode
    
    def get_stats(self) -> Dict:
        """
        통계 조회
        
        Returns:
            dict: 급락 감지 통계
        """
        return {
            **self.stats,
            'is_defense_mode': self.is_defense_mode,
            'defense_mode_start_date': str(self.defense_mode_start_date) if self.defense_mode_start_date else None
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'market_crash_count': 0,
            'portfolio_decline_count': 0,
            'defense_mode_days': 0
        }
        self.is_defense_mode = False
        self.defense_mode_start_date = None


__all__ = ['MarketCrashDetector']
