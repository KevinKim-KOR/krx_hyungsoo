# -*- coding: utf-8 -*-
"""
core/risk/manager.py
리스크 관리 시스템 (친구 코드 참고)
"""
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """리스크 관리자"""
    
    def __init__(
        self,
        position_cap: float = 0.25,  # 종목당 최대 비중
        portfolio_vol_target: float = 0.12,  # 목표 변동성
        max_drawdown_threshold: float = -0.15,  # 최대 손실 한도
        cooldown_days: int = 5,  # 재진입 제한 기간
        max_correlation: float = 0.7,  # 최대 상관계수
        min_liquidity: float = 3e8  # 최소 거래대금
    ):
        """
        Args:
            position_cap: 종목당 최대 비중 (0~1)
            portfolio_vol_target: 목표 포트폴리오 변동성
            max_drawdown_threshold: 최대 손실 한도 (음수)
            cooldown_days: 매도 후 재진입 제한 기간
            max_correlation: 종목 간 최대 상관계수
            min_liquidity: 최소 일평균 거래대금
        """
        self.position_cap = position_cap
        self.portfolio_vol_target = portfolio_vol_target
        self.max_drawdown_threshold = max_drawdown_threshold
        self.cooldown_days = cooldown_days
        self.max_correlation = max_correlation
        self.min_liquidity = min_liquidity
        
        # 쿨다운 추적
        self.cooldown_tracker: Dict[str, date] = {}
    
    def check_position_size(
        self,
        symbol: str,
        current_weight: float,
        proposed_weight: float
    ) -> Tuple[bool, str]:
        """
        포지션 크기 검증
        
        Returns:
            (허용 여부, 메시지)
        """
        if proposed_weight > self.position_cap:
            return False, f"포지션 한도 초과: {proposed_weight:.2%} > {self.position_cap:.2%}"
        
        return True, "OK"
    
    def check_portfolio_volatility(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float]
    ) -> Tuple[bool, float]:
        """
        포트폴리오 변동성 검증
        
        Args:
            returns: 수익률 DataFrame (columns=symbols)
            weights: 종목별 비중 {symbol: weight}
            
        Returns:
            (허용 여부, 계산된 변동성)
        """
        if returns.empty:
            return True, 0.0
        
        # 공분산 행렬
        cov_matrix = returns.cov()
        
        # 포트폴리오 변동성 계산
        weight_vector = np.array([weights.get(col, 0.0) for col in returns.columns])
        portfolio_var = np.dot(weight_vector, np.dot(cov_matrix, weight_vector))
        portfolio_vol = np.sqrt(portfolio_var)
        
        # 연율화 (일간 → 연간)
        annual_vol = portfolio_vol * np.sqrt(252)
        
        if annual_vol > self.portfolio_vol_target:
            return False, annual_vol
        
        return True, annual_vol
    
    def check_drawdown(
        self,
        nav_series: pd.Series
    ) -> Tuple[bool, float]:
        """
        최대 낙폭 검증
        
        Args:
            nav_series: NAV 시계열
            
        Returns:
            (허용 여부, 현재 MDD)
        """
        if nav_series.empty:
            return True, 0.0
        
        # 누적 최고점
        cummax = nav_series.cummax()
        
        # 낙폭
        drawdown = (nav_series / cummax) - 1.0
        
        # 최대 낙폭
        max_dd = drawdown.min()
        
        if max_dd < self.max_drawdown_threshold:
            return False, max_dd
        
        return True, max_dd
    
    def check_cooldown(
        self,
        symbol: str,
        current_date: date
    ) -> Tuple[bool, Optional[int]]:
        """
        쿨다운 기간 검증
        
        Returns:
            (재진입 가능 여부, 남은 일수)
        """
        if symbol not in self.cooldown_tracker:
            return True, None
        
        last_sell_date = self.cooldown_tracker[symbol]
        days_passed = (current_date - last_sell_date).days
        
        if days_passed < self.cooldown_days:
            remaining = self.cooldown_days - days_passed
            return False, remaining
        
        # 쿨다운 완료
        del self.cooldown_tracker[symbol]
        return True, None
    
    def register_sell(
        self,
        symbol: str,
        sell_date: date
    ):
        """매도 등록 (쿨다운 시작)"""
        self.cooldown_tracker[symbol] = sell_date
        logger.info(f"쿨다운 등록: {symbol} (매도일: {sell_date})")
    
    def check_correlation(
        self,
        returns: pd.DataFrame,
        existing_symbols: List[str],
        new_symbol: str
    ) -> Tuple[bool, float]:
        """
        상관계수 검증
        
        Args:
            returns: 수익률 DataFrame
            existing_symbols: 기존 보유 종목
            new_symbol: 신규 종목
            
        Returns:
            (허용 여부, 최대 상관계수)
        """
        if not existing_symbols or new_symbol not in returns.columns:
            return True, 0.0
        
        # 신규 종목과 기존 종목들 간 상관계수
        correlations = []
        for symbol in existing_symbols:
            if symbol in returns.columns:
                corr = returns[new_symbol].corr(returns[symbol])
                if not np.isnan(corr):
                    correlations.append(abs(corr))
        
        if not correlations:
            return True, 0.0
        
        max_corr = max(correlations)
        
        if max_corr > self.max_correlation:
            return False, max_corr
        
        return True, max_corr
    
    def check_liquidity(
        self,
        symbol: str,
        avg_value: float
    ) -> Tuple[bool, str]:
        """
        유동성 검증
        
        Args:
            symbol: 종목 코드
            avg_value: 평균 거래대금
            
        Returns:
            (허용 여부, 메시지)
        """
        if avg_value < self.min_liquidity:
            return False, f"유동성 부족: {avg_value:,.0f} < {self.min_liquidity:,.0f}"
        
        return True, "OK"
    
    def calculate_position_size(
        self,
        symbol: str,
        signal_strength: float,
        volatility: float,
        available_cash: float,
        current_price: float
    ) -> int:
        """
        포지션 크기 계산 (변동성 기반)
        
        Args:
            symbol: 종목 코드
            signal_strength: 신호 강도 (0~1)
            volatility: 종목 변동성
            available_cash: 가용 현금
            current_price: 현재 가격
            
        Returns:
            매수 수량
        """
        # 1. 변동성 기반 목표 비중
        if volatility > 0:
            vol_adjusted_weight = self.portfolio_vol_target / (volatility * np.sqrt(252))
        else:
            vol_adjusted_weight = self.position_cap
        
        # 2. 신호 강도 반영
        target_weight = min(vol_adjusted_weight * signal_strength, self.position_cap)
        
        # 3. 금액 계산
        target_amount = available_cash * target_weight
        
        # 4. 수량 계산
        quantity = int(target_amount / current_price)
        
        return quantity
    
    def validate_trade(
        self,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        portfolio_value: float,
        current_holdings: Dict[str, int],
        returns: Optional[pd.DataFrame] = None,
        nav_series: Optional[pd.Series] = None,
        current_date: Optional[date] = None
    ) -> Tuple[bool, List[str]]:
        """
        거래 검증 (종합)
        
        Returns:
            (허용 여부, 경고 메시지 리스트)
        """
        warnings = []
        
        # 1. 포지션 크기
        if action == 'BUY':
            proposed_value = quantity * price
            proposed_weight = proposed_value / portfolio_value
            
            ok, msg = self.check_position_size(symbol, 0.0, proposed_weight)
            if not ok:
                warnings.append(msg)
                return False, warnings
        
        # 2. 쿨다운
        if action == 'BUY' and current_date:
            ok, remaining = self.check_cooldown(symbol, current_date)
            if not ok:
                warnings.append(f"쿨다운 기간: {remaining}일 남음")
                return False, warnings
        
        # 3. 포트폴리오 변동성
        if returns is not None and action == 'BUY':
            # 신규 포지션 추가 후 비중 계산
            new_holdings = current_holdings.copy()
            new_holdings[symbol] = new_holdings.get(symbol, 0) + quantity
            
            total_value = sum(
                qty * price for qty, price in 
                [(new_holdings.get(s, 0), price) for s in new_holdings]
            )
            
            weights = {
                s: (new_holdings.get(s, 0) * price) / total_value
                for s in new_holdings
            }
            
            ok, vol = self.check_portfolio_volatility(returns, weights)
            if not ok:
                warnings.append(f"변동성 초과: {vol:.2%} > {self.portfolio_vol_target:.2%}")
        
        # 4. 최대 낙폭
        if nav_series is not None:
            ok, mdd = self.check_drawdown(nav_series)
            if not ok:
                warnings.append(f"MDD 한도 초과: {mdd:.2%} < {self.max_drawdown_threshold:.2%}")
                return False, warnings
        
        # 5. 상관계수
        if returns is not None and action == 'BUY':
            existing = list(current_holdings.keys())
            ok, max_corr = self.check_correlation(returns, existing, symbol)
            if not ok:
                warnings.append(f"상관계수 높음: {max_corr:.2f} > {self.max_correlation:.2f}")
        
        if warnings:
            return False, warnings
        
        return True, []


def create_default_risk_manager() -> RiskManager:
    """기본 리스크 관리자 생성"""
    return RiskManager(
        position_cap=0.25,
        portfolio_vol_target=0.12,
        max_drawdown_threshold=-0.15,
        cooldown_days=5,
        max_correlation=0.7,
        min_liquidity=3e8
    )
