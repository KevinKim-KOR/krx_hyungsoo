# -*- coding: utf-8 -*-
"""
core/engine/backtest.py
백테스트 엔진 (친구 코드 참고)
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import date, datetime
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """포지션 정보"""
    symbol: str
    quantity: int
    entry_price: float
    entry_date: date
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        """시장 가치"""
        return self.quantity * self.current_price
    
    @property
    def pnl(self) -> float:
        """손익"""
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """손익률"""
        if self.entry_price == 0:
            return 0.0
        return (self.current_price / self.entry_price - 1.0) * 100


@dataclass
class Trade:
    """거래 기록"""
    date: date
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    price: float
    commission: float = 0.0
    tax: float = 0.0  # 거래세 (매도 시만)
    slippage: float = 0.0  # 슬리피지 비용
    
    @property
    def amount(self) -> float:
        """거래 금액 (수수료 포함)"""
        return self.quantity * self.price + self.commission
    
    @property
    def total_cost(self) -> float:
        """총 거래비용 (수수료 + 세금 + 슬리피지)"""
        return self.commission + self.tax + self.slippage


@dataclass
class Portfolio:
    """포트폴리오 상태"""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    trades: List[Trade] = field(default_factory=list)
    
    @property
    def market_value(self) -> float:
        """포지션 시장 가치"""
        return sum(pos.market_value for pos in self.positions.values())
    
    @property
    def total_value(self) -> float:
        """총 자산"""
        return self.cash + self.market_value
    
    @property
    def pnl(self) -> float:
        """총 손익"""
        return sum(pos.pnl for pos in self.positions.values())
    
    def update_prices(self, prices: Dict[str, float]):
        """포지션 가격 업데이트"""
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.current_price = prices[symbol]


# 상품별 거래세율 (한국 시장)
TAX_RATES = {
    'stock': 0.0023,       # 주식: 0.23% (증권거래세 0.18% + 농특세 0.05%)
    'etf': 0.0,            # ETF: 면제
    'leveraged_etf': 0.0,  # 레버리지 ETF: 면제
    'reit': 0.0023,        # 리츠: 0.23%
    'default': 0.0         # 기본값: 면제 (ETF 위주 전략)
}


class BacktestEngine:
    """백테스트 엔진"""
    
    def __init__(
        self,
        initial_capital: float = 10000000,  # 초기 자본 (1천만원)
        commission_rate: float = 0.00015,  # 수수료율 (0.015%)
        slippage_rate: float = 0.001,  # 슬리피지 (0.1%)
        max_positions: int = 10,  # 최대 보유 종목 수
        rebalance_frequency: str = 'daily',  # 리밸런싱 주기
        instrument_type: str = 'etf'  # 상품 유형 (etf, stock, leveraged_etf, reit)
    ):
        """
        Args:
            initial_capital: 초기 자본
            commission_rate: 거래 수수료율
            slippage_rate: 슬리피지율
            max_positions: 최대 보유 종목 수
            rebalance_frequency: 리밸런싱 주기 (daily, weekly, monthly)
            instrument_type: 상품 유형 (거래세 결정)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.rebalance_frequency = rebalance_frequency
        self.instrument_type = instrument_type
        self.tax_rate = TAX_RATES.get(instrument_type, TAX_RATES['default'])
        
        # 포트폴리오 초기화
        self.portfolio = Portfolio(cash=initial_capital)
        
        # 성과 추적
        self.nav_history: List[Tuple[date, float]] = []
        self.daily_returns: List[float] = []
        
        # 거래비용 추적
        self.total_commission: float = 0.0
        self.total_tax: float = 0.0
        self.total_slippage: float = 0.0
        
        logger.info(f"BacktestEngine 초기화: instrument_type={instrument_type}, tax_rate={self.tax_rate*100:.2f}%")
        
    def calculate_commission(self, amount: float) -> float:
        """수수료 계산"""
        return amount * self.commission_rate
    
    def calculate_slippage(self, price: float, action: str) -> float:
        """슬리피지 적용"""
        if action == 'BUY':
            return price * (1 + self.slippage_rate)
        else:  # SELL
            return price * (1 - self.slippage_rate)
    
    def can_buy(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:
        """매수 가능 여부 확인"""
        # 최대 보유 종목 수 확인
        if symbol not in self.portfolio.positions and len(self.portfolio.positions) >= self.max_positions:
            return False, f"최대 보유 종목 수 초과 ({self.max_positions})"
        
        # 자금 확인
        adjusted_price = self.calculate_slippage(price, 'BUY')
        commission = self.calculate_commission(quantity * adjusted_price)
        required_cash = quantity * adjusted_price + commission
        
        if self.portfolio.cash < required_cash:
            return False, f"자금 부족: {required_cash:,.0f} > {self.portfolio.cash:,.0f}"
        
        return True, "OK"
    
    def execute_buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        trade_date: date
    ) -> bool:
        """매수 실행"""
        # 매수 가능 확인
        can_buy, msg = self.can_buy(symbol, quantity, price)
        if not can_buy:
            logger.warning(f"매수 불가 ({symbol}): {msg}")
            return False
        
        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, 'BUY')
        slippage_cost = abs(adjusted_price - price) * quantity
        
        # 수수료 계산
        commission = self.calculate_commission(quantity * adjusted_price)
        
        # 포지션 생성 또는 추가
        if symbol in self.portfolio.positions:
            # 기존 포지션 추가
            existing = self.portfolio.positions[symbol]
            total_qty = existing.quantity + quantity
            avg_price = (existing.entry_price * existing.quantity + adjusted_price * quantity) / total_qty
            existing.quantity = total_qty
            existing.entry_price = avg_price
            existing.current_price = adjusted_price
        else:
            # 신규 포지션
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=adjusted_price,
                entry_date=trade_date,
                current_price=adjusted_price
            )
        
        # 현금 차감
        self.portfolio.cash -= (quantity * adjusted_price + commission)
        
        # 비용 추적
        self.total_commission += commission
        self.total_slippage += slippage_cost
        
        # 거래 기록
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action='BUY',
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=0.0,  # 매수 시 세금 없음
            slippage=slippage_cost
        )
        self.portfolio.trades.append(trade)
        
        logger.debug(f"매수 실행: {symbol} {quantity}주 @ {adjusted_price:,.0f} (수수료: {commission:,.0f})")
        return True
    
    def execute_sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        trade_date: date
    ) -> bool:
        """매도 실행"""
        # 포지션 확인
        if symbol not in self.portfolio.positions:
            logger.warning(f"매도 불가 ({symbol}): 보유하지 않음")
            return False
        
        position = self.portfolio.positions[symbol]
        
        # 수량 확인
        if position.quantity < quantity:
            logger.warning(f"매도 불가 ({symbol}): 보유 수량 부족 ({position.quantity} < {quantity})")
            return False
        
        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, 'SELL')
        slippage_cost = abs(price - adjusted_price) * quantity
        
        # 거래 금액
        trade_amount = quantity * adjusted_price
        
        # 수수료 계산
        commission = self.calculate_commission(trade_amount)
        
        # 거래세 계산 (매도 시에만 부과)
        tax = trade_amount * self.tax_rate
        
        # 현금 증가 (수수료 + 세금 차감)
        self.portfolio.cash += (trade_amount - commission - tax)
        
        # 포지션 감소
        position.quantity -= quantity
        
        # 포지션 제거 (수량 0)
        if position.quantity == 0:
            del self.portfolio.positions[symbol]
        
        # 비용 추적
        self.total_commission += commission
        self.total_tax += tax
        self.total_slippage += slippage_cost
        
        # 거래 기록
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action='SELL',
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=tax,
            slippage=slippage_cost
        )
        self.portfolio.trades.append(trade)
        
        logger.debug(f"매도 실행: {symbol} {quantity}주 @ {adjusted_price:,.0f} (수수료: {commission:,.0f}, 세금: {tax:,.0f})")
        return True
    
    def rebalance(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        trade_date: date
    ):
        """포트폴리오 리밸런싱"""
        total_value = self.portfolio.total_value
        
        # 현재 비중 계산
        current_weights = {}
        for symbol, position in self.portfolio.positions.items():
            if symbol in current_prices:
                position.current_price = current_prices[symbol]
                current_weights[symbol] = position.market_value / total_value
        
        # 목표 비중과 현재 비중 비교
        for symbol, target_weight in target_weights.items():
            if symbol not in current_prices:
                continue
            
            current_weight = current_weights.get(symbol, 0.0)
            weight_diff = target_weight - current_weight
            
            # 비중 차이가 1% 이상이면 리밸런싱
            if abs(weight_diff) > 0.01:
                target_value = total_value * target_weight
                current_value = self.portfolio.positions.get(symbol, Position(symbol, 0, 0.0, trade_date)).market_value
                value_diff = target_value - current_value
                
                price = current_prices[symbol]
                quantity = int(abs(value_diff) / price)
                
                if quantity > 0:
                    if value_diff > 0:
                        # 매수
                        self.execute_buy(symbol, quantity, price, trade_date)
                    else:
                        # 매도
                        self.execute_sell(symbol, quantity, price, trade_date)
        
        # 목표 비중에 없는 종목 청산
        for symbol in list(self.portfolio.positions.keys()):
            if symbol not in target_weights:
                position = self.portfolio.positions[symbol]
                if symbol in current_prices:
                    self.execute_sell(symbol, position.quantity, current_prices[symbol], trade_date)
    
    def update_nav(self, current_date: date, current_prices: Dict[str, float]):
        """NAV 업데이트"""
        # 포지션 가격 업데이트
        self.portfolio.update_prices(current_prices)
        
        # NAV 기록
        nav = self.portfolio.total_value
        self.nav_history.append((current_date, nav))
        
        # 일간 수익률 계산
        if len(self.nav_history) > 1:
            prev_nav = self.nav_history[-2][1]
            daily_return = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
            self.daily_returns.append(daily_return)
    
    def get_performance_metrics(self) -> Dict[str, float]:
        """성과 지표 계산"""
        if not self.nav_history:
            return {}
        
        # NAV 시계열
        nav_series = pd.Series([nav for _, nav in self.nav_history])
        
        # 총 수익률
        total_return = (nav_series.iloc[-1] / self.initial_capital - 1.0) * 100
        
        # 연율화 수익률
        days = len(nav_series)
        annual_return = ((nav_series.iloc[-1] / self.initial_capital) ** (252 / days) - 1.0) * 100 if days > 0 else 0.0
        
        # 변동성
        if len(self.daily_returns) > 1:
            volatility = np.std(self.daily_returns) * np.sqrt(252) * 100
        else:
            volatility = 0.0
        
        # 샤프 비율 (무위험 수익률 0% 가정)
        sharpe_ratio = (annual_return / volatility) if volatility > 0 else 0.0
        
        # MDD
        cummax = nav_series.cummax()
        drawdown = (nav_series / cummax - 1.0) * 100
        max_drawdown = drawdown.min()
        
        # 승률
        if len(self.daily_returns) > 0:
            win_rate = (np.array(self.daily_returns) > 0).sum() / len(self.daily_returns) * 100
        else:
            win_rate = 0.0
        
        # 총 거래비용
        total_costs = self.total_commission + self.total_tax + self.total_slippage
        cost_ratio = (total_costs / self.initial_capital) * 100 if self.initial_capital > 0 else 0.0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(self.portfolio.trades),
            'final_value': nav_series.iloc[-1],
            # 거래비용 상세
            'total_commission': self.total_commission,
            'total_tax': self.total_tax,
            'total_slippage': self.total_slippage,
            'total_costs': total_costs,
            'cost_ratio': cost_ratio,  # 초기 자본 대비 비용 비율
            'instrument_type': self.instrument_type,
            'tax_rate': self.tax_rate * 100  # %로 표시
        }


def create_default_backtest_engine() -> BacktestEngine:
    """기본 백테스트 엔진 생성"""
    return BacktestEngine(
        initial_capital=10000000,
        commission_rate=0.00015,
        slippage_rate=0.001,
        max_positions=10,
        rebalance_frequency='daily'
    )
