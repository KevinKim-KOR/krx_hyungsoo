# -*- coding: utf-8 -*-
"""
core/engine/backtest.py
백테스트 엔진 (친구 코드 참고)
"""
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import date
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
    entry_price: float = 0.0  # 매수 시 진입가 (매도 시 사용)
    realized_pnl: float = 0.0  # 실현 손익 (매도 시만)

    @property
    def amount(self) -> float:
        """거래 금액 (수수료 포함)"""
        return self.quantity * self.price + self.commission

    @property
    def total_cost(self) -> float:
        """총 거래비용 (수수료 + 세금 + 슬리피지)"""
        return self.commission + self.tax + self.slippage

    @property
    def is_winning_trade(self) -> bool:
        """수익 거래 여부 (매도 시만 유효)"""
        return self.action == "SELL" and self.realized_pnl > 0


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
    "stock": 0.0023,  # 주식: 0.23% (증권거래세 0.18% + 농특세 0.05%)
    "etf": 0.0,  # ETF: 면제
    "leveraged_etf": 0.0,  # 레버리지 ETF: 면제
    "reit": 0.0023,  # 리츠: 0.23%
    "default": 0.0,  # 기본값: 면제 (ETF 위주 전략)
}


class BacktestEngine:
    """백테스트 엔진"""

    def __init__(
        self,
        initial_capital: float = 10000000,  # 초기 자본 (1천만원)
        commission_rate: float = 0.00015,  # 수수료율 (0.015%)
        slippage_rate: float = 0.001,  # 슬리피지 (0.1%)
        max_positions: int = 10,  # 최대 보유 종목 수
        rebalance_frequency: str = "daily",  # 리밸런싱 주기
        rebalance_threshold: float = 0.01,  # 리밸런싱 임계값 (1%)
        instrument_type: str = "etf",  # 상품 유형 (etf, stock, leveraged_etf, reit)
    ):
        """
        Args:
            initial_capital: 초기 자본
            commission_rate: 거래 수수료율
            slippage_rate: 슬리피지율
            max_positions: 최대 보유 종목 수
            rebalance_frequency: 리밸런싱 주기 (daily, weekly, monthly)
            rebalance_threshold: 리밸런싱 임계값 (비중 차이가 이 값 이상이면 리밸런싱)
            instrument_type: 상품 유형 (거래세 결정)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.rebalance_frequency = rebalance_frequency
        self.rebalance_threshold = rebalance_threshold
        self.instrument_type = instrument_type
        self.tax_rate = TAX_RATES.get(instrument_type, TAX_RATES["default"])

        # 포트폴리오 초기화
        self.portfolio = Portfolio(cash=initial_capital)

        # 성과 추적
        self.nav_history: List[Tuple[date, float]] = []
        self.daily_returns: List[float] = []

        # Gross 성과 추적 (비용 미반영)
        self.track_gross_metrics = True  # 항상 추적하도록 설정 (분석용)
        self.portfolio_gross = Portfolio(cash=initial_capital)
        self.nav_history_gross: List[Tuple[date, float]] = []
        self.daily_returns_gross: List[float] = []

        # 거래비용 추적
        self.total_commission: float = 0.0
        self.total_tax: float = 0.0
        self.total_slippage: float = 0.0

        logger.info(
            f"BacktestEngine 초기화: instrument_type={instrument_type}, tax_rate={self.tax_rate*100:.2f}%"
        )

    def calculate_commission(self, amount: float) -> float:
        """수수료 계산"""
        return amount * self.commission_rate

    def calculate_slippage(self, price: float, action: str) -> float:
        """슬리피지 적용"""
        if action == "BUY":
            return price * (1 + self.slippage_rate)
        else:  # SELL
            return price * (1 - self.slippage_rate)

    def can_buy(self, symbol: str, quantity: int, price: float) -> Tuple[bool, str]:
        """매수 가능 여부 확인"""
        # 최대 보유 종목 수 확인
        if (
            symbol not in self.portfolio.positions
            and len(self.portfolio.positions) >= self.max_positions
        ):
            return False, f"최대 보유 종목 수 초과 ({self.max_positions})"

        # 자금 확인
        adjusted_price = self.calculate_slippage(price, "BUY")
        commission = self.calculate_commission(quantity * adjusted_price)
        required_cash = quantity * adjusted_price + commission

        if self.portfolio.cash < required_cash:
            return (
                False,
                f"자금 부족: {required_cash:,.0f} > {self.portfolio.cash:,.0f}",
            )

        return True, "OK"

    def execute_buy(
        self, symbol: str, quantity: int, price: float, trade_date: date
    ) -> bool:
        """매수 실행"""
        # 매수 가능 확인
        can_buy, msg = self.can_buy(symbol, quantity, price)
        if not can_buy:
            logger.warning(f"매수 불가 ({symbol}): {msg}")
            return False

        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, "BUY")
        slippage_cost = abs(adjusted_price - price) * quantity

        # 수수료 계산
        commission = self.calculate_commission(quantity * adjusted_price)

        # 1. Net 포트폴리오 업데이트 (비용 차감)
        if symbol in self.portfolio.positions:
            existing = self.portfolio.positions[symbol]
            total_qty = existing.quantity + quantity
            avg_price = (
                existing.entry_price * existing.quantity + adjusted_price * quantity
            ) / total_qty
            existing.quantity = total_qty
            existing.entry_price = avg_price
            existing.current_price = adjusted_price
        else:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                entry_price=adjusted_price,
                entry_date=trade_date,
                current_price=adjusted_price,
            )
        self.portfolio.cash -= quantity * adjusted_price + commission

        # 2. Gross 포트폴리오 업데이트 (비용 미차감, 슬리피지 미적용 가격 사용)
        if self.track_gross_metrics:
            if symbol in self.portfolio_gross.positions:
                existing_gross = self.portfolio_gross.positions[symbol]
                total_qty_gross = existing_gross.quantity + quantity
                # Gross는 원래 가격(price) 사용
                avg_price_gross = (
                    existing_gross.entry_price * existing_gross.quantity
                    + price * quantity
                ) / total_qty_gross
                existing_gross.quantity = total_qty_gross
                existing_gross.entry_price = avg_price_gross
                existing_gross.current_price = price
            else:
                self.portfolio_gross.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    entry_price=price,
                    entry_date=trade_date,
                    current_price=price,
                )
            # 수수료/슬리피지 없이 순수 가격만큼만 차감
            self.portfolio_gross.cash -= quantity * price

        # 비용 추적
        self.total_commission += commission
        self.total_slippage += slippage_cost

        # 거래 기록
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action="BUY",
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=0.0,  # 매수 시 세금 없음
            slippage=slippage_cost,
        )
        self.portfolio.trades.append(trade)

        logger.debug(
            f"매수 실행: {symbol} {quantity}주 @ {adjusted_price:,.0f} (수수료: {commission:,.0f})"
        )
        return True

    def execute_sell(
        self, symbol: str, quantity: int, price: float, trade_date: date
    ) -> bool:
        """매도 실행"""
        # 포지션 확인
        if symbol not in self.portfolio.positions:
            logger.warning(f"매도 불가 ({symbol}): 보유하지 않음")
            return False

        position = self.portfolio.positions[symbol]

        # 수량 확인
        if position.quantity < quantity:
            logger.warning(
                f"매도 불가 ({symbol}): 보유 수량 부족 ({position.quantity} < {quantity})"
            )
            return False

        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, "SELL")
        slippage_cost = abs(price - adjusted_price) * quantity

        # 거래 금액
        trade_amount = quantity * adjusted_price

        # 수수료 계산
        commission = self.calculate_commission(trade_amount)

        # 거래세 계산 (매도 시에만 부과)
        tax = trade_amount * self.tax_rate

        # 1. Net 포트폴리오 업데이트
        self.portfolio.cash += trade_amount - commission - tax
        position.quantity -= quantity
        if position.quantity == 0:
            del self.portfolio.positions[symbol]

        # 2. Gross 포트폴리오 업데이트
        if self.track_gross_metrics and symbol in self.portfolio_gross.positions:
            pos_gross = self.portfolio_gross.positions[symbol]
            # 비용 없이 순수 가격으로 현금 증가
            self.portfolio_gross.cash += quantity * price
            pos_gross.quantity -= quantity
            if pos_gross.quantity == 0:
                del self.portfolio_gross.positions[symbol]

        # 비용 추적
        self.total_commission += commission
        self.total_tax += tax
        self.total_slippage += slippage_cost

        # 실현 손익 계산 (매도가 - 매수가) * 수량 - 비용
        entry_price = position.entry_price
        realized_pnl = (adjusted_price - entry_price) * quantity - commission - tax

        # 거래 기록
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action="SELL",
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=tax,
            slippage=slippage_cost,
            entry_price=entry_price,
            realized_pnl=realized_pnl,
        )
        self.portfolio.trades.append(trade)

        logger.debug(
            f"매도 실행: {symbol} {quantity}주 @ {adjusted_price:,.0f} (수수료: {commission:,.0f}, 세금: {tax:,.0f})"
        )
        return True

    def rebalance(
        self,
        target_weights: Dict[str, float],
        current_prices: Dict[str, float],
        trade_date: date,
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

            # 비중 차이가 임계값 이상이면 리밸런싱
            if abs(weight_diff) > self.rebalance_threshold:
                target_value = total_value * target_weight
                current_value = self.portfolio.positions.get(
                    symbol, Position(symbol, 0, 0.0, trade_date)
                ).market_value
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
                    self.execute_sell(
                        symbol, position.quantity, current_prices[symbol], trade_date
                    )

    def update_nav(self, current_date: date, current_prices: Dict[str, float]):
        """NAV 업데이트"""
        # 1. Net 포트폴리오
        self.portfolio.update_prices(current_prices)
        nav = self.portfolio.total_value
        self.nav_history.append((current_date, nav))

        if len(self.nav_history) > 1:
            prev_nav = self.nav_history[-2][1]
            daily_return = (nav / prev_nav - 1.0) if prev_nav > 0 else 0.0
            self.daily_returns.append(daily_return)

        # 2. Gross 포트폴리오
        if self.track_gross_metrics:
            self.portfolio_gross.update_prices(current_prices)
            nav_gross = self.portfolio_gross.total_value
            self.nav_history_gross.append((current_date, nav_gross))

            if len(self.nav_history_gross) > 1:
                prev_nav_gross = self.nav_history_gross[-2][1]
                daily_return_gross = (
                    (nav_gross / prev_nav_gross - 1.0) if prev_nav_gross > 0 else 0.0
                )
                self.daily_returns_gross.append(daily_return_gross)

    def get_performance_metrics(self) -> Dict[str, float]:
        """
        성과 지표 계산 (표준 금융 공식 적용)

        - CAGR: 달력일 기준 (365.25일)
        - Sharpe: 일간 수익률 기반 연율화
        - MDD: 양수로 반환 (업계 관례)
        - Calmar: CAGR / MDD
        """
        if not self.nav_history:
            return {}

        # 기본 데이터 준비
        dates = [d for d, _ in self.nav_history]
        nav_series = pd.Series([nav for _, nav in self.nav_history])

        start_date = dates[0]
        end_date = dates[-1]
        final_value = nav_series.iloc[-1]

        # 1. 총 수익률 (%)
        total_return = (final_value / self.initial_capital - 1.0) * 100

        # 2. CAGR 계산 (표준 공식: 달력일 기준)
        if isinstance(start_date, date) and isinstance(end_date, date):
            calendar_days = (end_date - start_date).days
        else:
            calendar_days = len(nav_series)

        years = calendar_days / 365.25
        if years > 0 and self.initial_capital > 0:
            cagr = ((final_value / self.initial_capital) ** (1 / years) - 1.0) * 100
        else:
            cagr = 0.0

        # 3. 변동성 계산 (일간 수익률 표준편차의 연율화)
        if len(self.daily_returns) > 1:
            daily_std = np.std(self.daily_returns, ddof=1)  # 표본 표준편차
            volatility = daily_std * np.sqrt(252) * 100
        else:
            volatility = 0.0

        # 4. Sharpe Ratio 계산 (표준 공식: 일간 수익률 기반)
        if len(self.daily_returns) > 1:
            mean_daily_return = np.mean(self.daily_returns)
            std_daily_return = np.std(self.daily_returns, ddof=1)
            if std_daily_return > 0:
                sharpe_ratio = (mean_daily_return / std_daily_return) * np.sqrt(252)
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # 5. MDD 계산 (양수로 반환)
        cummax = nav_series.cummax()
        drawdown = (nav_series / cummax - 1.0) * 100  # 음수
        max_drawdown = abs(drawdown.min())  # 양수로 변환

        # 6. Calmar Ratio 계산
        if max_drawdown > 0:
            calmar_ratio = cagr / max_drawdown
        else:
            calmar_ratio = 0.0

        # 7. 승률 계산 (일별 수익률 기준 - 명시적으로 표기)
        if len(self.daily_returns) > 0:
            daily_win_rate = (
                (np.array(self.daily_returns) > 0).sum() / len(self.daily_returns) * 100
            )
        else:
            daily_win_rate = 0.0

        # 8. 거래 승률 계산 (실제 매도 거래 기준)
        trades = self.portfolio.trades
        sell_trades = [t for t in trades if t.action == "SELL"]
        if sell_trades:
            winning_trades = [t for t in sell_trades if t.realized_pnl > 0]
            trade_win_rate = len(winning_trades) / len(sell_trades) * 100
            total_realized_pnl = sum(t.realized_pnl for t in sell_trades)
            avg_win = (
                np.mean([t.realized_pnl for t in winning_trades])
                if winning_trades
                else 0.0
            )
            losing_trades = [t for t in sell_trades if t.realized_pnl <= 0]
            avg_loss = (
                np.mean([t.realized_pnl for t in losing_trades])
                if losing_trades
                else 0.0
            )
        else:
            trade_win_rate = 0.0
            total_realized_pnl = 0.0
            avg_win = 0.0
            avg_loss = 0.0

        # 비용 통계
        total_costs = self.total_commission + self.total_tax + self.total_slippage
        cost_ratio = (
            (total_costs / self.initial_capital) * 100
            if self.initial_capital > 0
            else 0.0
        )

        metrics = {
            "total_return": total_return,
            "annual_return": cagr,  # CAGR로 변경
            "cagr": cagr,  # 명시적 CAGR 필드 추가
            "volatility": volatility,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": max_drawdown,  # 양수
            "calmar_ratio": calmar_ratio,  # 추가
            "win_rate": daily_win_rate,  # 일별 승률
            "trade_win_rate": trade_win_rate,  # 거래 승률 (실제 매도 기준)
            "total_trades": len(trades),
            "sell_trades": len(sell_trades),
            "total_realized_pnl": total_realized_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "final_value": final_value,
            "total_commission": self.total_commission,
            "total_tax": self.total_tax,
            "total_slippage": self.total_slippage,
            "total_costs": total_costs,
            "cost_ratio": cost_ratio,
            "instrument_type": self.instrument_type,
            "tax_rate": self.tax_rate * 100,
            "calendar_days": calendar_days,
            "trading_days": len(nav_series),
            "years": years,
        }

        # Gross 성과 추가
        if self.track_gross_metrics and self.nav_history_gross:
            nav_series_gross = pd.Series([nav for _, nav in self.nav_history_gross])
            final_value_gross = nav_series_gross.iloc[-1]
            total_return_gross = (final_value_gross / self.initial_capital - 1.0) * 100

            if years > 0:
                cagr_gross = (
                    (final_value_gross / self.initial_capital) ** (1 / years) - 1.0
                ) * 100
            else:
                cagr_gross = 0.0

            metrics.update(
                {
                    "total_return_gross": total_return_gross,
                    "annual_return_gross": cagr_gross,
                    "cagr_gross": cagr_gross,
                    "cost_drag": total_return_gross - total_return,
                }
            )

        return metrics


def create_default_backtest_engine() -> BacktestEngine:
    """기본 백테스트 엔진 생성"""
    return BacktestEngine(
        initial_capital=10000000,
        commission_rate=0.00015,
        slippage_rate=0.001,
        max_positions=10,
        rebalance_frequency="daily",
    )
