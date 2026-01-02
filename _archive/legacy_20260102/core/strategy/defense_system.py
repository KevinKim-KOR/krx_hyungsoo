# -*- coding: utf-8 -*-
"""
core/strategy/defense_system.py
방어 시스템 - 자동 손절 및 리스크 관리

목표: MDD -23.5% → -10~12% 감소
"""
from typing import Dict, Tuple, Optional
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """포지션 정보"""
    ticker: str
    entry_price: float
    entry_date: date
    quantity: int
    peak_price: float = 0.0
    trailing_stop_price: float = 0.0
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.peak_price == 0.0:
            self.peak_price = self.entry_price
        if self.trailing_stop_price == 0.0:
            self.trailing_stop_price = self.entry_price * 0.90


class CooldownManager:
    """
    쿨다운 관리자
    
    손절 후 재진입 금지 기간 관리
    """
    
    def __init__(self, cooldown_days: int = 3):
        """
        Args:
            cooldown_days: 쿨다운 기간 (일)
        """
        self.cooldown_days = cooldown_days
        self.stop_loss_history: Dict[str, date] = {}
    
    def record_stop_loss(self, ticker: str, stop_loss_date: date):
        """
        손절 기록
        
        Args:
            ticker: 종목 코드
            stop_loss_date: 손절 날짜
        """
        self.stop_loss_history[ticker] = stop_loss_date
        logger.info(f"손절 기록: {ticker} @ {stop_loss_date}")
    
    def can_reenter(self, ticker: str, current_date: date) -> bool:
        """
        재진입 가능 여부
        
        Args:
            ticker: 종목 코드
            current_date: 현재 날짜
        
        Returns:
            bool: True면 재진입 가능
        """
        if ticker not in self.stop_loss_history:
            return True
        
        stop_loss_date = self.stop_loss_history[ticker]
        days_passed = (current_date - stop_loss_date).days
        
        # 쿨다운 기간 경과 시 재진입 가능
        if days_passed >= self.cooldown_days:
            # 기록 삭제
            del self.stop_loss_history[ticker]
            logger.info(f"쿨다운 종료: {ticker} (경과 {days_passed}일)")
            return True
        
        logger.debug(f"쿨다운 중: {ticker} (경과 {days_passed}/{self.cooldown_days}일)")
        return False
    
    def get_cooldown_status(self) -> Dict[str, int]:
        """
        쿨다운 상태 조회
        
        Returns:
            dict: {ticker: days_remaining}
        """
        status = {}
        for ticker, stop_date in self.stop_loss_history.items():
            days_passed = (date.today() - stop_date).days
            days_remaining = max(0, self.cooldown_days - days_passed)
            status[ticker] = days_remaining
        return status


class DefenseSystem:
    """
    통합 방어 시스템
    
    기능:
    1. 개별 종목 손절 (고정 + 트레일링)
    2. 포트폴리오 손절
    3. 재진입 관리
    
    목표:
    - MDD -23.5% → -10~12% 감소
    - CAGR 30% 이상 유지
    - Sharpe 1.5 이상 유지
    """
    
    def __init__(
        self,
        # 개별 손절 파라미터
        fixed_stop_loss_pct: float = -7.0,
        trailing_stop_pct: float = -10.0,
        
        # 포트폴리오 손절 파라미터
        portfolio_stop_loss_pct: float = -15.0,
        
        # 재진입 파라미터
        cooldown_days: int = 3,
        
        # 활성화 플래그
        enable_fixed_stop: bool = True,
        enable_trailing_stop: bool = True,
        enable_portfolio_stop: bool = True
    ):
        """
        Args:
            fixed_stop_loss_pct: 고정 손절 비율 (%)
            trailing_stop_pct: 트레일링 스톱 비율 (%)
            portfolio_stop_loss_pct: 포트폴리오 손절 비율 (%)
            cooldown_days: 쿨다운 기간 (일)
            enable_fixed_stop: 고정 손절 활성화
            enable_trailing_stop: 트레일링 스톱 활성화
            enable_portfolio_stop: 포트폴리오 손절 활성화
        """
        self.fixed_stop_loss_pct = fixed_stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.portfolio_stop_loss_pct = portfolio_stop_loss_pct
        self.cooldown_days = cooldown_days
        
        self.enable_fixed_stop = enable_fixed_stop
        self.enable_trailing_stop = enable_trailing_stop
        self.enable_portfolio_stop = enable_portfolio_stop
        
        # 쿨다운 관리자
        self.cooldown_manager = CooldownManager(cooldown_days)
        
        # 통계
        self.stats = {
            'fixed_stop_count': 0,
            'trailing_stop_count': 0,
            'portfolio_stop_count': 0,
            'total_stop_loss': 0.0
        }
        
        logger.info(f"DefenseSystem 초기화: fixed={fixed_stop_loss_pct}%, "
                   f"trailing={trailing_stop_pct}%, portfolio={portfolio_stop_loss_pct}%")
    
    def check_fixed_stop_loss(
        self,
        position: Position,
        current_price: float
    ) -> bool:
        """
        고정 손절 체크
        
        진입가 대비 -7% 하락 시 손절
        
        Args:
            position: 포지션 정보
            current_price: 현재 가격
        
        Returns:
            bool: True면 손절 발동
        """
        if not self.enable_fixed_stop:
            return False
        
        entry_price = position.entry_price
        if entry_price <= 0:
            return False
        
        # 손실률 계산
        loss_pct = ((current_price / entry_price) - 1.0) * 100
        
        # 손절 체크
        if loss_pct <= self.fixed_stop_loss_pct:
            logger.info(f"고정 손절 발동: {position.ticker} "
                       f"진입가={entry_price:,.0f} 현재가={current_price:,.0f} "
                       f"손실={loss_pct:.2f}%")
            return True
        
        return False
    
    def check_trailing_stop(
        self,
        position: Position,
        current_price: float
    ) -> bool:
        """
        트레일링 스톱 체크
        
        최고가 대비 -10% 하락 시 손절
        
        Args:
            position: 포지션 정보
            current_price: 현재 가격
        
        Returns:
            bool: True면 손절 발동
        """
        if not self.enable_trailing_stop:
            return False
        
        trailing_stop_price = position.trailing_stop_price
        
        # 트레일링 스톱 가격 이하로 하락 시 손절
        if current_price <= trailing_stop_price:
            peak_price = position.peak_price
            loss_from_peak = ((current_price / peak_price) - 1.0) * 100
            
            logger.info(f"트레일링 스톱 발동: {position.ticker} "
                       f"최고가={peak_price:,.0f} 현재가={current_price:,.0f} "
                       f"손절선={trailing_stop_price:,.0f} "
                       f"최고가 대비={loss_from_peak:.2f}%")
            return True
        
        return False
    
    def check_individual_stop_loss(
        self,
        position: Position,
        current_price: float
    ) -> Tuple[bool, Optional[str]]:
        """
        개별 종목 손절 체크 (고정 + 트레일링)
        
        Args:
            position: 포지션 정보
            current_price: 현재 가격
        
        Returns:
            tuple: (손절 여부, 손절 유형)
        """
        # 1. 고정 손절 체크
        if self.check_fixed_stop_loss(position, current_price):
            self.stats['fixed_stop_count'] += 1
            return True, 'fixed_stop_loss'
        
        # 2. 트레일링 스톱 체크
        if self.check_trailing_stop(position, current_price):
            self.stats['trailing_stop_count'] += 1
            return True, 'trailing_stop'
        
        return False, None
    
    def update_trailing_stop(
        self,
        position: Position,
        current_price: float
    ):
        """
        트레일링 스톱 업데이트
        
        현재가가 최고가를 갱신하면 손절선도 상승
        
        Args:
            position: 포지션 정보
            current_price: 현재 가격
        """
        if not self.enable_trailing_stop:
            return
        
        # 최고가 업데이트
        if current_price > position.peak_price:
            old_peak = position.peak_price
            old_stop = position.trailing_stop_price
            
            position.peak_price = current_price
            # 손절선 업데이트 (최고가의 90%)
            position.trailing_stop_price = current_price * (1 + self.trailing_stop_pct / 100)
            
            logger.debug(f"트레일링 스톱 업데이트: {position.ticker} "
                        f"최고가 {old_peak:,.0f}→{current_price:,.0f} "
                        f"손절선 {old_stop:,.0f}→{position.trailing_stop_price:,.0f}")
    
    def check_portfolio_stop_loss(
        self,
        current_portfolio_value: float,
        peak_portfolio_value: float
    ) -> bool:
        """
        포트폴리오 손절 체크
        
        전체 포트폴리오 가치 -15% 하락 시 전체 청산
        
        Args:
            current_portfolio_value: 현재 포트폴리오 가치
            peak_portfolio_value: 최고 포트폴리오 가치
        
        Returns:
            bool: True면 손절 발동
        """
        if not self.enable_portfolio_stop:
            return False
        
        if peak_portfolio_value <= 0:
            return False
        
        # 손실률 계산
        loss_pct = ((current_portfolio_value / peak_portfolio_value) - 1.0) * 100
        
        # 손절 체크
        if loss_pct <= self.portfolio_stop_loss_pct:
            logger.warning(f"포트폴리오 손절 발동! "
                          f"최고가치={peak_portfolio_value:,.0f} "
                          f"현재가치={current_portfolio_value:,.0f} "
                          f"손실={loss_pct:.2f}%")
            self.stats['portfolio_stop_count'] += 1
            return True
        
        return False
    
    def can_reenter(self, ticker: str, current_date: date) -> bool:
        """
        재진입 가능 여부
        
        Args:
            ticker: 종목 코드
            current_date: 현재 날짜
        
        Returns:
            bool: True면 재진입 가능
        """
        return self.cooldown_manager.can_reenter(ticker, current_date)
    
    def record_stop_loss(self, ticker: str, stop_loss_date: date):
        """
        손절 기록
        
        Args:
            ticker: 종목 코드
            stop_loss_date: 손절 날짜
        """
        self.cooldown_manager.record_stop_loss(ticker, stop_loss_date)
    
    def get_stats(self) -> Dict:
        """
        통계 조회
        
        Returns:
            dict: 손절 통계
        """
        cooldown_status = self.cooldown_manager.get_cooldown_status()
        
        return {
            **self.stats,
            'cooldown_count': len(cooldown_status),
            'cooldown_tickers': list(cooldown_status.keys())
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.stats = {
            'fixed_stop_count': 0,
            'trailing_stop_count': 0,
            'portfolio_stop_count': 0,
            'total_stop_loss': 0.0
        }


__all__ = ['DefenseSystem', 'Position', 'CooldownManager']
