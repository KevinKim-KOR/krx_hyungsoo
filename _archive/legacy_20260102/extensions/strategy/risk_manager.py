# -*- coding: utf-8 -*-
"""
extensions/strategy/risk_manager.py
리스크 관리 및 포트폴리오 구성
"""
import logging
from datetime import date, timedelta
from typing import Dict, List
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RiskManager:
    """리스크 관리자"""
    
    def __init__(
        self,
        max_positions: int = 10,
        min_confidence: float = 0.1,
        portfolio_vol_target: float = 0.15,
        max_drawdown_threshold: float = -0.15,
        cooldown_days: int = 7,
        max_correlation: float = 0.7
    ):
        """
        Args:
            max_positions: 최대 포지션 수
            min_confidence: 최소 신뢰도
            portfolio_vol_target: 목표 변동성
            max_drawdown_threshold: 최대 낙폭 임계값
            cooldown_days: 쿨다운 기간
            max_correlation: 최대 상관계수
        """
        self.max_positions = max_positions
        self.min_confidence = min_confidence
        self.portfolio_vol_target = portfolio_vol_target
        self.max_drawdown_threshold = max_drawdown_threshold
        self.cooldown_days = cooldown_days
        self.max_correlation = max_correlation
        
        logger.info(f"RiskManager 초기화: max_pos={max_positions}, min_conf={min_confidence}")
    
    def filter_signals(
        self,
        signals: List[Dict],
        price_data: pd.DataFrame,
        target_date: date
    ) -> List[Dict]:
        """
        신호 필터링
        
        Args:
            signals: 원시 신호 리스트
            price_data: 가격 데이터
            target_date: 기준 날짜
            
        Returns:
            필터링된 신호 리스트
        """
        if not signals:
            return []
        
        # 1. 신뢰도 필터
        filtered = [s for s in signals if s.get('confidence', 0) >= self.min_confidence]
        logger.info(f"신뢰도 필터: {len(signals)} -> {len(filtered)}")
        
        # 2. 변동성 필터
        filtered = self._filter_by_volatility(filtered, price_data, target_date)
        logger.info(f"변동성 필터: -> {len(filtered)}")
        
        # 3. 상관계수 필터
        filtered = self._filter_by_correlation(filtered, price_data, target_date)
        logger.info(f"상관계수 필터: -> {len(filtered)}")
        
        return filtered
    
    def construct_portfolio(
        self,
        signals: List[Dict],
        price_data: pd.DataFrame,
        target_date: date
    ) -> Dict[str, float]:
        """
        포트폴리오 구성
        
        Args:
            signals: 필터링된 신호
            price_data: 가격 데이터
            target_date: 기준 날짜
            
        Returns:
            포트폴리오 (code -> weight)
        """
        if not signals:
            return {}
        
        # 신뢰도 기반 가중치
        total_confidence = sum(s.get('confidence', 0) for s in signals)
        
        if total_confidence == 0:
            # 동일 가중
            weight = 1.0 / min(len(signals), self.max_positions)
            return {s['code']: weight for s in signals[:self.max_positions]}
        
        # 신뢰도 비례 가중
        portfolio = {}
        sorted_signals = sorted(signals, key=lambda x: x.get('confidence', 0), reverse=True)
        
        for signal in sorted_signals[:self.max_positions]:
            weight = signal.get('confidence', 0) / total_confidence
            portfolio[signal['code']] = weight
        
        # 가중치 정규화
        total_weight = sum(portfolio.values())
        if total_weight > 0:
            portfolio = {k: v / total_weight for k, v in portfolio.items()}
        
        return portfolio
    
    def _filter_by_volatility(
        self,
        signals: List[Dict],
        price_data: pd.DataFrame,
        target_date: date
    ) -> List[Dict]:
        """변동성 필터"""
        filtered = []
        
        for signal in signals:
            code = signal['code']
            
            try:
                # 종목 데이터
                symbol_data = price_data.xs(code, level=0)
                
                if len(symbol_data) < 20:
                    continue
                
                # 20일 변동성
                returns = symbol_data['close'].pct_change()
                volatility = returns.std() * np.sqrt(252)
                
                # 변동성 임계값 (연 50% 이하)
                if volatility < 0.5:
                    filtered.append(signal)
            
            except Exception as e:
                logger.debug(f"[{code}] 변동성 계산 실패: {e}")
                continue
        
        return filtered
    
    def _filter_by_correlation(
        self,
        signals: List[Dict],
        price_data: pd.DataFrame,
        target_date: date
    ) -> List[Dict]:
        """상관계수 필터 (간단한 버전)"""
        if len(signals) <= 1:
            return signals
        
        # 상관계수 계산은 복잡하므로 일단 모두 통과
        # 실제로는 종목 간 상관계수를 계산하여 높은 상관관계 제거
        return signals
    
    def calculate_position_size(
        self,
        code: str,
        weight: float,
        total_capital: float,
        current_price: float
    ) -> int:
        """
        포지션 크기 계산
        
        Args:
            code: 종목 코드
            weight: 목표 가중치
            total_capital: 총 자본
            current_price: 현재 가격
            
        Returns:
            매수 수량
        """
        if current_price <= 0:
            return 0
        
        target_value = total_capital * weight
        shares = int(target_value / current_price)
        
        return shares
