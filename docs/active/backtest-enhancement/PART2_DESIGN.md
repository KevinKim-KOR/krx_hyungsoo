# 백테스트 엔진 고도화 설계 - Part 2: 상세 설계 및 구현 계획

**작성일**: 2025-11-29  
**전제**: Part 1 분석 완료  
**목적**: 단계별 상세 설계 및 구현 가이드

---

## 📋 목차

1. [1단계: 거래비용 모델 고도화](#1단계-거래비용-모델-고도화)
2. [2단계: 레짐 노출 스케일링](#2단계-레짐-노출-스케일링)
3. [3단계: Train/Val/Test 파이프라인](#3단계-trainvaltest-파이프라인)
4. [4단계: Config 연결](#4단계-config-연결)
5. [5단계: 분석 로그 추가](#5단계-분석-로그-추가)
6. [테스트 전략](#테스트-전략)
7. [구현 체크리스트](#구현-체크리스트)

---

## 1단계: 거래비용 모델 고도화

**목표**: "이제부터는 무조건 Net 기준으로만 성과를 본다"  
**예상 기간**: 1~2일  
**우선순위**: 1순위

### 1.1 Config 구조

```yaml
# config/backtest.yaml
backtest:
  # 기본 설정
  initial_capital: 10000000
  max_positions: 10
  rebalance_frequency: 'daily'
  track_gross_metrics: false  # Gross 추적 (옵션)
  
  # 거래비용 (자산별)
  costs:
    # 한국 주식/ETF
    korea:
      commission_rate: 0.00015  # 0.015% (편도)
      tax_rate: 0.0023          # 0.23% (매도 시만)
      slippage_bps: 5           # 5bps = 0.05%
    
    # 미국 주식/ETF
    usa:
      commission_rate: 0.0      # 무료 (Robinhood 등)
      tax_rate: 0.0             # 없음
      slippage_bps: 3           # 3bps
    
    # 채권
    bond:
      commission_rate: 0.0001   # 0.01%
      tax_rate: 0.0015          # 0.15%
      slippage_bps: 2           # 2bps
```

### 1.2 Trade 클래스 확장

**파일**: `core/engine/backtest.py`

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class Trade:
    """거래 기록 (확장)"""
    date: date
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    price: float  # 슬리피지 적용된 가격
    commission: float = 0.0
    tax: float = 0.0         # ✅ 추가
    slippage: float = 0.0    # ✅ 추가 (price - original_price)
    
    @property
    def gross_amount(self) -> float:
        """Gross 거래 금액 (비용 제외)"""
        return self.quantity * self.price
    
    @property
    def net_amount(self) -> float:
        """Net 거래 금액 (비용 포함)"""
        if self.action == 'BUY':
            return self.gross_amount + self.commission
        else:  # SELL
            return self.gross_amount - self.commission - self.tax
    
    @property
    def total_cost(self) -> float:
        """총 비용"""
        return self.commission + self.tax
```

### 1.3 BacktestEngine 수정

**파일**: `core/engine/backtest.py`

```python
class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 10000000,
        commission_rate: float = 0.00015,
        tax_rate: float = 0.0023,        # ✅ 추가
        slippage_rate: float = 0.001,
        max_positions: int = 10,
        rebalance_frequency: str = 'daily',
        track_gross_metrics: bool = False  # ✅ 추가
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.tax_rate = tax_rate  # ✅ 추가
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.rebalance_frequency = rebalance_frequency
        self.track_gross_metrics = track_gross_metrics  # ✅ 추가
        
        # 포트폴리오
        self.portfolio = Portfolio(cash=initial_capital)
        
        # 성과 추적
        self.nav_history: List[Tuple[date, float]] = []
        self.daily_returns: List[float] = []
        
        # ✅ Gross 추적 (옵션)
        if track_gross_metrics:
            self.nav_history_gross: List[Tuple[date, float]] = []
            self.daily_returns_gross: List[float] = []
            self.total_costs: float = 0.0  # 누적 비용
        
        logger.info(f"BacktestEngine 초기화: "
                   f"자본={initial_capital:,.0f}, "
                   f"수수료={commission_rate*100:.3f}%, "
                   f"거래세={tax_rate*100:.2f}%, "
                   f"슬리피지={slippage_rate*100:.2f}%")
    
    def execute_sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        trade_date: date
    ) -> bool:
        """매도 실행 (거래세 추가)"""
        if symbol not in self.portfolio.positions:
            logger.warning(f"매도 불가 ({symbol}): 보유하지 않음")
            return False
        
        position = self.portfolio.positions[symbol]
        if position.quantity < quantity:
            logger.warning(f"매도 불가 ({symbol}): 보유 수량 부족")
            return False
        
        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, 'SELL')
        slippage_amount = adjusted_price - price  # 음수
        
        # 수수료 계산
        commission = self.calculate_commission(quantity * adjusted_price)
        
        # ✅ 거래세 계산 (매도 시만)
        tax = quantity * adjusted_price * self.tax_rate
        
        # ✅ 총 비용
        total_cost = commission + tax
        
        # 현금 증가 (비용 차감)
        self.portfolio.cash += (quantity * adjusted_price - total_cost)
        
        # 포지션 감소
        position.quantity -= quantity
        if position.quantity == 0:
            del self.portfolio.positions[symbol]
        
        # ✅ 거래 기록 (상세)
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action='SELL',
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=tax,  # ✅ 추가
            slippage=slippage_amount  # ✅ 추가
        )
        self.portfolio.trades.append(trade)
        
        # ✅ Gross 추적
        if self.track_gross_metrics:
            self.total_costs += total_cost
        
        logger.info(f"매도: {symbol} {quantity}주 @ {adjusted_price:,.0f} "
                   f"(수수료: {commission:,.0f}, 거래세: {tax:,.0f})")
        return True
    
    def execute_buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        trade_date: date
    ) -> bool:
        """매수 실행 (기존 + 상세 로그)"""
        # 슬리피지 적용
        adjusted_price = self.calculate_slippage(price, 'BUY')
        slippage_amount = adjusted_price - price  # 양수
        
        # 수수료 계산
        commission = self.calculate_commission(quantity * adjusted_price)
        
        # 총 비용
        total_cost = quantity * adjusted_price + commission
        
        # 현금 확인
        if self.portfolio.cash < total_cost:
            logger.warning(f"매수 불가 ({symbol}): 현금 부족")
            return False
        
        # 현금 차감
        self.portfolio.cash -= total_cost
        
        # 포지션 추가
        if symbol in self.portfolio.positions:
            position = self.portfolio.positions[symbol]
            position.quantity += quantity
            position.avg_price = (
                (position.avg_price * (position.quantity - quantity) + 
                 adjusted_price * quantity) / position.quantity
            )
        else:
            self.portfolio.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=adjusted_price
            )
        
        # ✅ 거래 기록 (상세)
        trade = Trade(
            date=trade_date,
            symbol=symbol,
            action='BUY',
            quantity=quantity,
            price=adjusted_price,
            commission=commission,
            tax=0.0,  # 매수 시 거래세 없음
            slippage=slippage_amount  # ✅ 추가
        )
        self.portfolio.trades.append(trade)
        
        # ✅ Gross 추적
        if self.track_gross_metrics:
            self.total_costs += commission
        
        logger.info(f"매수: {symbol} {quantity}주 @ {adjusted_price:,.0f} "
                   f"(수수료: {commission:,.0f})")
        return True
```

### 1.4 성과 지표 확장

```python
def get_performance_metrics(self) -> Dict[str, float]:
    """성과 지표 계산 (Gross/Net 구분)"""
    if not self.nav_history:
        return {}
    
    # NAV 시계열
    nav_series = pd.Series([nav for _, nav in self.nav_history])
    
    # ✅ Net 지표 (기본)
    metrics = {
        # 수익률
        'total_return_net': (nav_series.iloc[-1] / self.initial_capital - 1.0) * 100,
        'cagr_net': self._calculate_cagr(nav_series),
        
        # 위험
        'volatility_net': np.std(self.daily_returns) * np.sqrt(252) * 100,
        'max_drawdown_net': self._calculate_mdd(nav_series),
        
        # 위험 조정 수익률
        'sharpe_ratio_net': self._calculate_sharpe(self.daily_returns),
        'sortino_ratio_net': self._calculate_sortino(self.daily_returns),
        
        # ✅ 거래 요약
        'total_trades': len(self.portfolio.trades),
        'total_turnover': self._calculate_turnover(),
        'avg_holding_period': self._calculate_avg_holding_period(),
        
        # 최종 값
        'final_value': nav_series.iloc[-1]
    }
    
    # ✅ Gross 지표 (옵션)
    if self.track_gross_metrics:
        nav_series_gross = pd.Series([nav for _, nav in self.nav_history_gross])
        metrics.update({
            'total_return_gross': (nav_series_gross.iloc[-1] / self.initial_capital - 1.0) * 100,
            'cagr_gross': self._calculate_cagr(nav_series_gross),
            'sharpe_ratio_gross': self._calculate_sharpe(self.daily_returns_gross),
            'max_drawdown_gross': self._calculate_mdd(nav_series_gross),
            'volatility_gross': np.std(self.daily_returns_gross) * np.sqrt(252) * 100,
            
            # ✅ 비용 영향
            'total_costs': self.total_costs,
            'cost_impact_pct': (self.total_costs / self.initial_capital) * 100,
            'cost_drag_annual': (metrics['cagr_gross'] - metrics['cagr_net'])
        })
    
    return metrics

def _calculate_turnover(self) -> float:
    """총 회전율 계산 (연율화)"""
    if not self.portfolio.trades or not self.nav_history:
        return 0.0
    
    # 총 거래 금액 (매수 + 매도)
    total_trade_value = sum(
        trade.quantity * trade.price 
        for trade in self.portfolio.trades
    )
    
    # 평균 자산
    avg_nav = np.mean([nav for _, nav in self.nav_history])
    
    # 거래일 수
    days = len(self.nav_history)
    
    # 연율화 회전율
    turnover = (total_trade_value / avg_nav) * (252 / days)
    
    return turnover

def _calculate_avg_holding_period(self) -> float:
    """평균 보유 기간 계산 (일)"""
    if not self.portfolio.trades:
        return 0.0
    
    # 매수-매도 쌍 찾기 (FIFO)
    buy_queue = {}  # symbol -> [buy_date1, buy_date2, ...]
    holding_periods = []
    
    for trade in self.portfolio.trades:
        if trade.action == 'BUY':
            if trade.symbol not in buy_queue:
                buy_queue[trade.symbol] = []
            buy_queue[trade.symbol].append(trade.date)
        
        elif trade.action == 'SELL':
            if trade.symbol in buy_queue and buy_queue[trade.symbol]:
                buy_date = buy_queue[trade.symbol].pop(0)
                holding_period = (trade.date - buy_date).days
                holding_periods.append(holding_period)
    
    if not holding_periods:
        return 0.0
    
    return np.mean(holding_periods)
```

### 1.5 테스트 케이스

```python
# tests/test_backtest_costs.py

import pytest
from datetime import date
from core.engine.backtest import BacktestEngine

def test_tax_calculation():
    """거래세 계산 테스트"""
    engine = BacktestEngine(
        initial_capital=10000000,
        commission_rate=0.00015,
        tax_rate=0.0023,
        slippage_rate=0.0
    )
    
    # 매수
    engine.execute_buy('005930', 100, 70000, date(2024, 1, 1))
    
    # 매도
    engine.execute_sell('005930', 100, 75000, date(2024, 1, 2))
    
    # 거래 확인
    sell_trade = engine.portfolio.trades[1]
    assert sell_trade.action == 'SELL'
    assert sell_trade.tax == pytest.approx(75000 * 100 * 0.0023, rel=1e-6)
    assert sell_trade.commission == pytest.approx(75000 * 100 * 0.00015, rel=1e-6)

def test_gross_net_metrics():
    """Gross/Net 지표 테스트"""
    engine = BacktestEngine(
        initial_capital=10000000,
        commission_rate=0.00015,
        tax_rate=0.0023,
        slippage_rate=0.001,
        track_gross_metrics=True  # ✅ Gross 추적
    )
    
    # 백테스트 실행 (생략)
    # ...
    
    # 성과 지표
    metrics = engine.get_performance_metrics()
    
    # Gross > Net 확인
    assert metrics['cagr_gross'] > metrics['cagr_net']
    assert metrics['total_costs'] > 0
    assert metrics['cost_drag_annual'] > 0

def test_turnover_calculation():
    """회전율 계산 테스트"""
    engine = BacktestEngine(initial_capital=10000000)
    
    # 백테스트 실행 (생략)
    # ...
    
    metrics = engine.get_performance_metrics()
    
    # 회전율 확인
    assert metrics['total_turnover'] >= 0
    assert metrics['avg_holding_period'] >= 0
```

---

## 2단계: 레짐 노출 스케일링

**목표**: "레짐 점수에 따라 비중을 계단식으로 조절"  
**예상 기간**: 1~2일  
**우선순위**: 2순위

### 2.1 문제 진단

**현재 상황**:
```python
# extensions/backtest/runner.py
def run(self, ...):
    # ✅ 레짐 감지는 함
    regime, confidence = self.regime_detector.detect_regime(...)
    
    # ❌ 하지만 사용 안 함!
    target_weights = self._generate_target_weights(...)
    self.engine.rebalance(target_weights, ...)  # 항상 100% 포지션
```

### 2.2 해결 방법

**파일**: `extensions/backtest/runner.py`

```python
class BacktestRunner:
    def __init__(
        self,
        engine: BacktestEngine,
        signal_generator: SignalGenerator,
        risk_manager: RiskManager,
        regime_detector: Optional[MarketRegimeDetector] = None,  # ✅ 추가
        etf_filter: Optional[ETFFilter] = None
    ):
        self.engine = engine
        self.signal_generator = signal_generator
        self.risk_manager = risk_manager
        self.regime_detector = regime_detector  # ✅ 추가
        self.etf_filter = etf_filter
    
    def run(
        self,
        price_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        universe: List[str],
        rebalance_frequency: str = 'daily',
        market_index_code: str = '069500'  # ✅ KOSPI 대표 (KODEX 200)
    ) -> Dict:
        """백테스트 실행 (레짐 스케일링 포함)"""
        logger.info(f"백테스트 시작: {start_date} ~ {end_date}")
        
        # ✅ 시장 데이터 추출 (레짐 감지용)
        market_data = None
        if self.regime_detector and market_index_code in price_data.index.get_level_values('code'):
            market_data = price_data.xs(market_index_code, level='code')
            logger.info(f"시장 데이터 로드: {market_index_code} ({len(market_data)}일)")
        
        # 거래일 목록
        trading_dates = self._get_trading_dates(price_data, start_date, end_date)
        rebalance_dates = self._get_rebalance_dates(trading_dates, rebalance_frequency)
        
        # 일별 실행
        for current_date in trading_dates:
            # ✅ 레짐 감지
            regime = 'neutral'
            confidence = 0.5
            position_ratio = 1.0
            
            if self.regime_detector and market_data is not None:
                regime, confidence = self.regime_detector.detect_regime(
                    market_data, current_date
                )
                position_ratio = self.regime_detector.get_position_ratio(
                    regime, confidence
                )
                logger.debug(f"{current_date}: 레짐={regime}, "
                           f"신뢰도={confidence:.2f}, 비율={position_ratio:.2f}")
            
            # 리밸런싱
            if current_date in rebalance_dates:
                logger.info(f"=== 리밸런싱: {current_date} ===")
                
                # 목표 비중 계산
                target_weights = self._generate_target_weights(
                    price_data, current_date, universe
                )
                
                if target_weights:
                    # ✅ 레짐 비율 적용
                    adjusted_weights = self._apply_regime_scaling(
                        target_weights, position_ratio
                    )
                    
                    logger.info(f"레짐 조정: {regime} (비율={position_ratio:.2f})")
                    logger.info(f"조정 전 비중 합: {sum(target_weights.values()):.2f}")
                    logger.info(f"조정 후 비중 합: {sum(adjusted_weights.values()):.2f}")
                    
                    # 현재 가격
                    current_prices = self._get_prices_on_date(
                        price_data, current_date, universe
                    )
                    
                    # 리밸런싱 실행
                    self.engine.rebalance(adjusted_weights, current_prices, current_date)
            
            # NAV 업데이트
            current_prices = self._get_prices_on_date(price_data, current_date, universe)
            if current_prices:
                self.engine.update_nav(current_date, current_prices)
        
        # 성과 지표
        metrics = self.engine.get_performance_metrics()
        
        # ✅ 레짐 통계 추가
        if self.regime_detector:
            regime_stats = self.regime_detector.get_stats()
            metrics['regime_stats'] = regime_stats
        
        return {
            'metrics': metrics,
            'nav_history': self.engine.nav_history,
            'trades': self.engine.portfolio.trades,
            'final_positions': self.engine.portfolio.positions
        }
    
    def _apply_regime_scaling(
        self,
        target_weights: Dict[str, float],
        position_ratio: float
    ) -> Dict[str, float]:
        """
        레짐 비율 적용
        
        Args:
            target_weights: 원래 목표 비중 (합=1.0)
            position_ratio: 레짐 비율 (0.4~1.2)
        
        Returns:
            dict: 조정된 비중 (합=position_ratio)
        """
        # 비율 적용
        adjusted_weights = {
            symbol: weight * position_ratio
            for symbol, weight in target_weights.items()
        }
        
        # 정규화 (합이 position_ratio가 되도록)
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            adjusted_weights = {
                symbol: weight / total_weight * position_ratio
                for symbol, weight in adjusted_weights.items()
            }
        
        return adjusted_weights
```

### 2.3 계단식 vs 연속식 (선택)

**파일**: `core/strategy/market_regime_detector.py`

```python
class MarketRegimeDetector:
    def __init__(
        self,
        ...,
        position_scaling_mode: str = 'continuous'  # ✅ 추가: 'continuous' or 'discrete'
    ):
        self.position_scaling_mode = position_scaling_mode
        ...
    
    def get_position_ratio(
        self,
        regime: str,
        confidence: float
    ) -> float:
        """레짐에 따른 포지션 비율"""
        if self.position_scaling_mode == 'discrete':
            # 계단식
            return self._get_position_ratio_discrete(regime, confidence)
        else:
            # 연속식 (기존)
            return self._get_position_ratio_continuous(regime, confidence)
    
    def _get_position_ratio_continuous(
        self,
        regime: str,
        confidence: float
    ) -> float:
        """연속식 (기존)"""
        if regime == 'bull':
            return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
        elif regime == 'bear':
            return 0.6 - (confidence - 0.5) * 0.4  # 40~60%
        else:
            return 0.8  # 80%
    
    def _get_position_ratio_discrete(
        self,
        regime: str,
        confidence: float
    ) -> float:
        """계단식 (신규)"""
        if regime == 'bull':
            if confidence > 0.8:
                return 1.2  # 공격
            elif confidence > 0.6:
                return 1.0  # 중립
            else:
                return 0.8  # 방어
        
        elif regime == 'bear':
            if confidence > 0.8:
                return 0.4  # 강력 방어
            elif confidence > 0.6:
                return 0.5  # 방어
            else:
                return 0.6  # 약한 방어
        
        else:  # neutral
            return 0.8
```

### 2.4 테스트 케이스

```python
# tests/test_regime_scaling.py

def test_regime_scaling():
    """레짐 스케일링 테스트"""
    # 레짐 감지기
    detector = MarketRegimeDetector(
        position_scaling_mode='continuous'
    )
    
    # Bull 레짐 → 120% 포지션
    ratio = detector.get_position_ratio('bull', confidence=0.9)
    assert ratio == pytest.approx(1.16, rel=1e-2)
    
    # Bear 레짐 → 40% 포지션
    ratio = detector.get_position_ratio('bear', confidence=0.9)
    assert ratio == pytest.approx(0.44, rel=1e-2)

def test_backtest_with_regime_scaling():
    """레짐 스케일링 백테스트 테스트"""
    # 엔진
    engine = BacktestEngine(initial_capital=10000000)
    
    # 레짐 감지기
    detector = MarketRegimeDetector()
    
    # 러너
    runner = BacktestRunner(
        engine=engine,
        signal_generator=...,
        risk_manager=...,
        regime_detector=detector  # ✅ 레짐 감지기 연결
    )
    
    # 백테스트 실행
    results = runner.run(...)
    
    # 레짐 통계 확인
    assert 'regime_stats' in results['metrics']
    assert results['metrics']['regime_stats']['bull_days'] > 0
    assert results['metrics']['regime_stats']['bear_days'] > 0
```

---

## 3단계: Train/Val/Test 파이프라인

**목표**: "과최적화 방지 + 실전 성과 예측"  
**예상 기간**: 2~3일  
**우선순위**: 3순위

### 3.1 데이터 분할

**파일**: `extensions/backtest/train_val_test.py` (신규)

```python
from typing import Dict, List, Tuple
from datetime import date, timedelta
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TrainValTestSplitter:
    """Train/Validation/Test 데이터 분할"""
    
    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15
    ):
        """
        Args:
            train_ratio: Train 비율 (기본 70%)
            val_ratio: Validation 비율 (기본 15%)
            test_ratio: Test 비율 (기본 15%)
        """
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
            "비율 합이 1.0이어야 합니다"
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
    
    def split(
        self,
        start_date: date,
        end_date: date
    ) -> Tuple[Tuple[date, date], Tuple[date, date], Tuple[date, date]]:
        """
        시간순 분할
        
        Returns:
            tuple: ((train_start, train_end), (val_start, val_end), (test_start, test_end))
        """
        total_days = (end_date - start_date).days
        
        # Train 기간
        train_days = int(total_days * self.train_ratio)
        train_end = start_date + timedelta(days=train_days)
        
        # Validation 기간
        val_days = int(total_days * self.val_ratio)
        val_start = train_end + timedelta(days=1)
        val_end = val_start + timedelta(days=val_days)
        
        # Test 기간
        test_start = val_end + timedelta(days=1)
        test_end = end_date
        
        logger.info(f"데이터 분할:")
        logger.info(f"  Train: {start_date} ~ {train_end} ({train_days}일)")
        logger.info(f"  Val:   {val_start} ~ {val_end} ({val_days}일)")
        logger.info(f"  Test:  {test_start} ~ {test_end} ({(test_end - test_start).days}일)")
        
        return (
            (start_date, train_end),
            (val_start, val_end),
            (test_start, test_end)
        )
```

### 3.2 파라미터 그리드 서치

```python
# extensions/backtest/train_val_test.py

from itertools import product

class ParameterGridSearch:
    """파라미터 그리드 서치"""
    
    def __init__(
        self,
        param_grid: Dict[str, List],
        backtest_runner: BacktestRunner,
        metric: str = 'sharpe_ratio_net'
    ):
        """
        Args:
            param_grid: 파라미터 그리드
                예: {
                    'commission_rate': [0.00015, 0.0003],
                    'max_positions': [5, 10, 15],
                    'rebalance_frequency': ['daily', 'weekly']
                }
            backtest_runner: 백테스트 러너
            metric: 최적화 지표 (기본: sharpe_ratio_net)
        """
        self.param_grid = param_grid
        self.backtest_runner = backtest_runner
        self.metric = metric
        self.results = []
    
    def search(
        self,
        price_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        universe: List[str]
    ) -> Dict:
        """
        그리드 서치 실행
        
        Returns:
            dict: 최적 파라미터 및 결과
        """
        # 파라미터 조합 생성
        param_combinations = self._generate_combinations()
        
        logger.info(f"그리드 서치 시작: {len(param_combinations)}개 조합")
        
        best_score = -np.inf
        best_params = None
        best_metrics = None
        
        for i, params in enumerate(param_combinations, 1):
            logger.info(f"[{i}/{len(param_combinations)}] 테스트 중: {params}")
            
            try:
                # 파라미터 적용
                self._apply_params(params)
                
                # 백테스트 실행
                results = self.backtest_runner.run(
                    price_data=price_data,
                    start_date=start_date,
                    end_date=end_date,
                    universe=universe
                )
                
                # 성과 지표
                metrics = results['metrics']
                score = metrics.get(self.metric, -np.inf)
                
                # 결과 저장
                self.results.append({
                    'params': params.copy(),
                    'metrics': metrics,
                    'score': score
                })
                
                # 최적 파라미터 업데이트
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_metrics = metrics
                    logger.info(f"  ✅ 신규 최고 점수: {score:.4f}")
                else:
                    logger.info(f"  점수: {score:.4f}")
            
            except Exception as e:
                logger.error(f"  ❌ 실패: {e}")
                self.results.append({
                    'params': params.copy(),
                    'metrics': {},
                    'score': -np.inf,
                    'error': str(e)
                })
        
        logger.info(f"그리드 서치 완료!")
        logger.info(f"최적 파라미터: {best_params}")
        logger.info(f"최고 점수: {best_score:.4f}")
        
        return {
            'best_params': best_params,
            'best_metrics': best_metrics,
            'best_score': best_score,
            'all_results': self.results
        }
    
    def _generate_combinations(self) -> List[Dict]:
        """파라미터 조합 생성"""
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        
        combinations = []
        for combo in product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _apply_params(self, params: Dict):
        """파라미터 적용"""
        # BacktestEngine 파라미터
        if 'commission_rate' in params:
            self.backtest_runner.engine.commission_rate = params['commission_rate']
        if 'tax_rate' in params:
            self.backtest_runner.engine.tax_rate = params['tax_rate']
        if 'slippage_rate' in params:
            self.backtest_runner.engine.slippage_rate = params['slippage_rate']
        if 'max_positions' in params:
            self.backtest_runner.engine.max_positions = params['max_positions']
        
        # SignalGenerator 파라미터
        if 'ma_period' in params:
            self.backtest_runner.signal_generator.ma_period = params['ma_period']
        if 'rsi_period' in params:
            self.backtest_runner.signal_generator.rsi_period = params['rsi_period']
        
        # 기타 파라미터
        # ...
```

### 3.3 Train/Val/Test 실행

```python
# extensions/backtest/train_val_test.py

class TrainValTestPipeline:
    """Train/Validation/Test 파이프라인"""
    
    def __init__(
        self,
        backtest_runner: BacktestRunner,
        param_grid: Dict[str, List],
        metric: str = 'sharpe_ratio_net'
    ):
        self.backtest_runner = backtest_runner
        self.param_grid = param_grid
        self.metric = metric
        
        self.splitter = TrainValTestSplitter()
        self.grid_search = ParameterGridSearch(
            param_grid=param_grid,
            backtest_runner=backtest_runner,
            metric=metric
        )
    
    def run(
        self,
        price_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        universe: List[str]
    ) -> Dict:
        """
        Train/Val/Test 파이프라인 실행
        
        Returns:
            dict: {
                'train_results': {...},
                'val_results': {...},
                'test_results': {...},
                'best_params': {...}
            }
        """
        logger.info("=" * 80)
        logger.info("Train/Val/Test 파이프라인 시작")
        logger.info("=" * 80)
        
        # 1. 데이터 분할
        (train_start, train_end), (val_start, val_end), (test_start, test_end) = \
            self.splitter.split(start_date, end_date)
        
        # 2. Train: 파라미터 탐색
        logger.info("\n" + "=" * 80)
        logger.info("TRAIN: 파라미터 탐색")
        logger.info("=" * 80)
        
        train_results = self.grid_search.search(
            price_data=price_data,
            start_date=train_start,
            end_date=train_end,
            universe=universe
        )
        
        best_params = train_results['best_params']
        logger.info(f"\nTrain 최적 파라미터: {best_params}")
        logger.info(f"Train 최고 점수: {train_results['best_score']:.4f}")
        
        # 3. Validation: 최적 파라미터 검증
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION: 최적 파라미터 검증")
        logger.info("=" * 80)
        
        self.grid_search._apply_params(best_params)
        val_backtest_results = self.backtest_runner.run(
            price_data=price_data,
            start_date=val_start,
            end_date=val_end,
            universe=universe
        )
        
        val_metrics = val_backtest_results['metrics']
        val_score = val_metrics.get(self.metric, -np.inf)
        
        logger.info(f"Validation 점수: {val_score:.4f}")
        logger.info(f"Validation CAGR: {val_metrics.get('cagr_net', 0):.2f}%")
        logger.info(f"Validation Sharpe: {val_metrics.get('sharpe_ratio_net', 0):.2f}")
        logger.info(f"Validation MDD: {val_metrics.get('max_drawdown_net', 0):.2f}%")
        
        # 4. Test: 실전 성과 예측
        logger.info("\n" + "=" * 80)
        logger.info("TEST: 실전 성과 예측")
        logger.info("=" * 80)
        
        test_backtest_results = self.backtest_runner.run(
            price_data=price_data,
            start_date=test_start,
            end_date=test_end,
            universe=universe
        )
        
        test_metrics = test_backtest_results['metrics']
        test_score = test_metrics.get(self.metric, -np.inf)
        
        logger.info(f"Test 점수: {test_score:.4f}")
        logger.info(f"Test CAGR: {test_metrics.get('cagr_net', 0):.2f}%")
        logger.info(f"Test Sharpe: {test_metrics.get('sharpe_ratio_net', 0):.2f}")
        logger.info(f"Test MDD: {test_metrics.get('max_drawdown_net', 0):.2f}%")
        
        # 5. 결과 비교
        logger.info("\n" + "=" * 80)
        logger.info("결과 비교")
        logger.info("=" * 80)
        
        comparison = pd.DataFrame({
            'Train': [
                train_results['best_score'],
                train_results['best_metrics'].get('cagr_net', 0),
                train_results['best_metrics'].get('sharpe_ratio_net', 0),
                train_results['best_metrics'].get('max_drawdown_net', 0)
            ],
            'Validation': [
                val_score,
                val_metrics.get('cagr_net', 0),
                val_metrics.get('sharpe_ratio_net', 0),
                val_metrics.get('max_drawdown_net', 0)
            ],
            'Test': [
                test_score,
                test_metrics.get('cagr_net', 0),
                test_metrics.get('sharpe_ratio_net', 0),
                test_metrics.get('max_drawdown_net', 0)
            ]
        }, index=[self.metric, 'CAGR (%)', 'Sharpe', 'MDD (%)'])
        
        logger.info(f"\n{comparison}")
        
        return {
            'train_results': train_results,
            'val_results': {
                'metrics': val_metrics,
                'score': val_score
            },
            'test_results': {
                'metrics': test_metrics,
                'score': test_score
            },
            'best_params': best_params,
            'comparison': comparison
        }
```

---

## 4단계: Config 연결

**목표**: "함수 시그니처는 그대로, Config만 바꾸는 구조"  
**예상 기간**: 0.5일  
**우선순위**: 4순위

### 4.1 Config 로더

**파일**: `core/engine/backtest.py`

```python
import yaml
from pathlib import Path
from typing import Optional

def create_backtest_engine_from_config(
    config_path: Optional[str] = None,
    country_code: str = 'korea'
) -> BacktestEngine:
    """
    Config 파일에서 백테스트 엔진 생성
    
    Args:
        config_path: 설정 파일 경로 (None이면 기본 경로)
        country_code: 국가 코드 ('korea', 'usa', 'bond')
    
    Returns:
        BacktestEngine: 설정된 백테스트 엔진
    """
    # Config 로드
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "backtest.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 백테스트 설정
    backtest_config = config.get('backtest', {})
    costs = backtest_config.get('costs', {}).get(country_code, {})
    
    # 엔진 생성
    return BacktestEngine(
        initial_capital=backtest_config.get('initial_capital', 10000000),
        commission_rate=costs.get('commission_rate', 0.00015),
        tax_rate=costs.get('tax_rate', 0.0023),
        slippage_rate=costs.get('slippage_bps', 5) / 10000,  # bps → rate
        max_positions=backtest_config.get('max_positions', 10),
        rebalance_frequency=backtest_config.get('rebalance_frequency', 'daily'),
        track_gross_metrics=backtest_config.get('track_gross_metrics', False)
    )
```

---

## 5단계: 분석 로그 추가

**목표**: "일자별/트레이드별 상세 로그"  
**예상 기간**: 1일  
**우선순위**: 5순위

### 5.1 일자별 로그

**파일**: `core/engine/backtest.py`

```python
def update_nav(
    self,
    current_date: date,
    current_prices: Dict[str, float],
    regime: Optional[str] = None,  # ✅ 추가
    regime_confidence: Optional[float] = None  # ✅ 추가
) -> float:
    """
    NAV 업데이트 (로그 확장)
    
    Args:
        current_date: 현재 날짜
        current_prices: 현재 가격
        regime: 레짐 (옵션)
        regime_confidence: 레짐 신뢰도 (옵션)
    
    Returns:
        float: 현재 NAV
    """
    # 포지션 가치
    position_value = sum(
        pos.quantity * current_prices.get(pos.symbol, pos.avg_price)
        for pos in self.portfolio.positions.values()
    )
    
    # 총 자산
    total_value = self.portfolio.cash + position_value
    
    # NAV 기록
    self.nav_history.append((current_date, total_value))
    
    # ✅ 일자별 로그 (상세)
    if hasattr(self, 'daily_logs'):
        # 노출 비중 계산
        equity_exposure = position_value / total_value if total_value > 0 else 0
        cash_exposure = self.portfolio.cash / total_value if total_value > 0 else 0
        
        self.daily_logs.append({
            'date': current_date,
            'portfolio_value': total_value,
            'cash': self.portfolio.cash,
            'position_value': position_value,
            'equity_exposure': equity_exposure,
            'cash_exposure': cash_exposure,
            'regime': regime,
            'regime_confidence': regime_confidence,
            'num_positions': len(self.portfolio.positions)
        })
    
    # 일별 수익률
    if len(self.nav_history) > 1:
        prev_nav = self.nav_history[-2][1]
        daily_return = (total_value / prev_nav - 1.0)
        self.daily_returns.append(daily_return)
    
    return total_value
```

---

## 테스트 전략

### 단위 테스트
- 각 기능별 독립 테스트
- `pytest` 사용

### 통합 테스트
- 전체 백테스트 실행
- 기존 결과와 비교

### 검증 기준
```
✅ tax_rate=0 → 기존 결과와 동일
✅ tax_rate=0.0023 → CAGR 약 0.5~1% 감소
✅ Gross > Net (항상)
✅ 레짐 스케일링 → MDD 개선
✅ Train/Val/Test → 과최적화 방지
```

---

## 구현 체크리스트

### 1단계: 거래비용 모델
- [ ] Config 구조 정의
- [ ] Trade 클래스 확장
- [ ] execute_sell() 거래세 추가
- [ ] Gross/Net 지표 구분
- [ ] 거래 요약 통계 추가
- [ ] 단위 테스트 작성

### 2단계: 레짐 노출 스케일링
- [ ] BacktestRunner에 regime_detector 추가
- [ ] _apply_regime_scaling() 구현
- [ ] 계단식/연속식 옵션 추가
- [ ] 통합 테스트 작성

### 3단계: Train/Val/Test
- [ ] TrainValTestSplitter 구현
- [ ] ParameterGridSearch 구현
- [ ] TrainValTestPipeline 구현
- [ ] 실행 스크립트 작성

### 4단계: Config 연결
- [ ] create_backtest_engine_from_config() 구현
- [ ] backtest.yaml 작성
- [ ] 하위 호환성 테스트

### 5단계: 분석 로그
- [ ] daily_logs 추가
- [ ] update_nav() 확장
- [ ] 로그 DataFrame 변환
- [ ] 시각화 함수 작성

---

**다음 단계**: 구현 시작!
