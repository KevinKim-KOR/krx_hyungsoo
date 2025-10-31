# -*- coding: utf-8 -*-
"""
extensions/backtest/runner.py
백테스트 실행기 (친구 코드 참고)
"""
from typing import Dict, List, Optional, Callable
from datetime import date, timedelta
import pandas as pd
import numpy as np
import logging

from core.engine.backtest import BacktestEngine
from core.strategy.signals import SignalGenerator
from core.risk.manager import RiskManager
from core.data.filtering import ETFFilter

logger = logging.getLogger(__name__)


class BacktestRunner:
    """백테스트 실행기"""
    
    def __init__(
        self,
        engine: BacktestEngine,
        signal_generator: SignalGenerator,
        risk_manager: RiskManager,
        etf_filter: Optional[ETFFilter] = None
    ):
        """
        Args:
            engine: 백테스트 엔진
            signal_generator: 신호 생성기
            risk_manager: 리스크 관리자
            etf_filter: ETF 필터 (선택)
        """
        self.engine = engine
        self.signal_generator = signal_generator
        self.risk_manager = risk_manager
        self.etf_filter = etf_filter
        
    def run(
        self,
        price_data: pd.DataFrame,
        start_date: date,
        end_date: date,
        universe: List[str],
        rebalance_frequency: str = 'daily'
    ) -> Dict:
        """
        백테스트 실행
        
        Args:
            price_data: 가격 데이터 (MultiIndex: code, date)
            start_date: 시작일
            end_date: 종료일
            universe: 투자 유니버스 (종목 코드 리스트)
            rebalance_frequency: 리밸런싱 주기
            
        Returns:
            백테스트 결과
        """
        logger.info(f"백테스트 시작: {start_date} ~ {end_date}")
        logger.info(f"유니버스: {len(universe)}개 종목")
        
        # 거래일 목록
        all_dates = sorted(price_data.index.get_level_values('date').unique())
        # Timestamp를 date로 변환하여 비교
        trading_dates = [d for d in all_dates if start_date <= d.date() <= end_date]
        
        logger.info(f"거래일 수: {len(trading_dates)}일")
        
        # 리밸런싱 날짜 계산
        rebalance_dates = self._get_rebalance_dates(trading_dates, rebalance_frequency)
        logger.info(f"리밸런싱 횟수: {len(rebalance_dates)}회")
        
        # 일별 실행
        for i, current_date in enumerate(trading_dates):
            # 진행률 출력
            if (i + 1) % 20 == 0 or i == len(trading_dates) - 1:
                logger.info(f"진행: {i+1}/{len(trading_dates)} ({(i+1)/len(trading_dates)*100:.1f}%)")
            
            # 리밸런싱 날짜인 경우
            logger.debug(f"날짜 체크: {current_date}, 리밸런싱: {current_date in rebalance_dates}")
            if current_date in rebalance_dates:
                logger.info(f"=== 리밸런싱 실행: {current_date} ===")
                # 현재 가격 데이터
                current_prices = {}
                for symbol in universe:
                    try:
                        price = price_data.loc[(symbol, current_date), 'close']
                        current_prices[symbol] = price
                    except KeyError:
                        pass
                
                # 목표 비중 계산 (MAPS 전략 기반)
                logger.info(f"목표 비중 계산 시작: {len(universe)}개 종목")
                try:
                    target_weights = self._generate_target_weights(
                        price_data,
                        current_date,
                        universe,
                        lookback_days=60
                    )
                    
                    logger.info(f"목표 비중 계산 완료: {len(target_weights)}개 종목")
                    if target_weights:
                        logger.info(f"리밸런싱 실행: {target_weights}")
                        self.engine.rebalance(target_weights, current_prices, current_date)
                    else:
                        logger.warning("목표 비중 없음 - 리밸런싱 건너뜀")
                except Exception as e:
                    logger.error(f"목표 비중 계산 실패: {e}", exc_info=True)
                    target_weights = {}
            
            # 현재 가격 추출
            current_prices = self._get_prices_on_date(price_data, current_date, universe)
            
            if not current_prices:
                continue
            
            # NAV 업데이트
            self.engine.update_nav(current_date, current_prices)
        
        # 성과 지표 출력
        logger.info("백테스트 완료")
        metrics = self.engine.get_performance_metrics()
        logger.info(f"총 수익률: {metrics.get('total_return', 0):.2f}%")
        logger.info(f"연율화 수익률: {metrics.get('annual_return', 0):.2f}%")
        logger.info(f"최대 낙폭: {metrics.get('max_drawdown', 0):.2f}%")
        logger.info(f"샤프 비율: {metrics.get('sharpe_ratio', 0):.2f}")
        
        return {
            'metrics': metrics,
            'nav_history': self.engine.nav_history,
            'trades': self.engine.portfolio.trades,
            'final_positions': self.engine.portfolio.positions
        }
    
    def _get_rebalance_dates(
        self,
        trading_dates: List[date],
        frequency: str
    ) -> List[date]:
        """리밸런싱 날짜 계산"""
        if frequency == 'daily':
            return trading_dates
        elif frequency == 'weekly':
            # 매주 월요일
            return [d for d in trading_dates if d.weekday() == 0]
        elif frequency == 'monthly':
            # 매월 첫 거래일
            rebalance = []
            current_month = None
            for d in trading_dates:
                if current_month != d.month:
                    rebalance.append(d)
                    current_month = d.month
            return rebalance
        else:
            return trading_dates
    
    def _get_prices_on_date(
        self,
        price_data: pd.DataFrame,
        target_date: date,
        universe: List[str]
    ) -> Dict[str, float]:
        """특정 날짜의 가격 추출"""
        prices = {}
        
        for symbol in universe:
            try:
                if symbol in price_data.index.get_level_values('code'):
                    symbol_data = price_data.loc[symbol]
                    
                    if target_date in symbol_data.index:
                        prices[symbol] = float(symbol_data.loc[target_date, 'close'])
            except Exception as e:
                logger.debug(f"가격 추출 실패 ({symbol}, {target_date}): {e}")
        
        return prices
    
    def _generate_target_weights(
        self,
        price_data: pd.DataFrame,
        current_date: date,
        universe: List[str],
        lookback_days: int = 60
    ) -> Dict[str, float]:
        """목표 비중 생성"""
        logger.info(f"[_generate_target_weights] 시작: current_date={current_date}, universe={universe}, lookback={lookback_days}")
        logger.info(f"[_generate_target_weights] price_data shape: {price_data.shape}")
        logger.info(f"[_generate_target_weights] price_data index levels: {price_data.index.names}")
        
        # 룩백 기간
        start_date = current_date - timedelta(days=lookback_days * 2)  # 여유있게
        
        # 신호 생성
        signals = {}
        
        for symbol in universe:
            try:
                logger.info(f"[{symbol}] 처리 시작")
                if symbol not in price_data.index.get_level_values('code'):
                    logger.warning(f"[{symbol}] 데이터 없음")
                    continue
                
                # 종목 데이터 추출
                symbol_data = price_data.loc[symbol]
                logger.info(f"[{symbol}] 전체 데이터: {len(symbol_data)}행")
                symbol_data = symbol_data[symbol_data.index <= current_date]
                logger.info(f"[{symbol}] 필터 후 데이터: {len(symbol_data)}행 (current_date={current_date})")
                
                if len(symbol_data) < lookback_days:
                    logger.warning(f"[{symbol}] 데이터 부족 ({len(symbol_data)} < {lookback_days})")
                    continue
                
                # 최근 데이터
                recent_data = symbol_data.tail(lookback_days)
                
                # 신호 생성
                signal_result = self.signal_generator.generate_combined_signal(
                    close=recent_data['close'],
                    high=recent_data.get('high'),
                    low=recent_data.get('low'),
                    volume=recent_data.get('volume')
                )
                
                logger.info(f"{symbol}: {signal_result['signal']} (신뢰도: {signal_result.get('confidence', 0):.2f}, 점수: {signal_result.get('score', 0):.2f})")
                
                # 매수 신호만
                if signal_result['signal'] == 'BUY':
                    signals[symbol] = signal_result['confidence']
                    
            except Exception as e:
                logger.warning(f"신호 생성 실패 ({symbol}): {e}")
        
        if not signals:
            logger.info("매수 신호 없음")
            return {}
        
        # 상위 N개 선택
        top_n = min(self.engine.max_positions, len(signals))
        sorted_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)
        top_signals = dict(sorted_signals[:top_n])
        
        # 균등 비중
        equal_weight = 1.0 / len(top_signals)
        target_weights = {symbol: equal_weight for symbol in top_signals}
        
        logger.debug(f"목표 비중: {len(target_weights)}개 종목")
        
        return target_weights


class MomentumBacktestRunner(BacktestRunner):
    """모멘텀 전략 백테스트 실행기"""
    
    def _generate_target_weights(
        self,
        price_data: pd.DataFrame,
        current_date: date,
        universe: List[str],
        lookback_days: int = 60
    ) -> Dict[str, float]:
        """모멘텀 기반 목표 비중 생성"""
        # 룩백 기간
        start_date = current_date - timedelta(days=lookback_days * 2)
        
        # 모멘텀 계산
        momentum_scores = {}
        
        for symbol in universe:
            try:
                if symbol not in price_data.index.get_level_values('code'):
                    continue
                
                symbol_data = price_data.loc[symbol]
                symbol_data = symbol_data[symbol_data.index <= current_date]
                
                if len(symbol_data) < lookback_days:
                    continue
                
                # 모멘텀 = (현재가 / N일전 가격) - 1
                current_price = symbol_data['close'].iloc[-1]
                past_price = symbol_data['close'].iloc[-lookback_days]
                
                momentum = (current_price / past_price - 1.0) * 100
                
                # 양수 모멘텀만
                if momentum > 0:
                    momentum_scores[symbol] = momentum
                    
            except Exception as e:
                logger.debug(f"모멘텀 계산 실패 ({symbol}): {e}")
        
        if not momentum_scores:
            return {}
        
        # 상위 N개 선택
        top_n = min(self.engine.max_positions, len(momentum_scores))
        sorted_momentum = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
        top_momentum = dict(sorted_momentum[:top_n])
        
        # 균등 비중
        equal_weight = 1.0 / len(top_momentum)
        target_weights = {symbol: equal_weight for symbol in top_momentum}
        
        logger.debug(f"모멘텀 상위 {len(target_weights)}개 종목 선택")
        
        return target_weights


def create_default_runner(
    initial_capital: float = 10000000,
    max_positions: int = 10
) -> BacktestRunner:
    """기본 백테스트 실행기 생성"""
    from core.engine.backtest import BacktestEngine
    from core.strategy.signals import create_default_signal_generator
    from core.risk.manager import create_default_risk_manager
    
    engine = BacktestEngine(
        initial_capital=initial_capital,
        max_positions=max_positions
    )
    
    signal_generator = create_default_signal_generator()
    risk_manager = create_default_risk_manager()
    
    return BacktestRunner(engine, signal_generator, risk_manager)


def create_momentum_runner(
    initial_capital: float = 10000000,
    max_positions: int = 10
) -> MomentumBacktestRunner:
    """모멘텀 백테스트 실행기 생성"""
    from core.engine.backtest import BacktestEngine
    from core.strategy.signals import create_default_signal_generator
    from core.risk.manager import create_default_risk_manager
    
    engine = BacktestEngine(
        initial_capital=initial_capital,
        max_positions=max_positions
    )
    
    signal_generator = create_default_signal_generator()
    risk_manager = create_default_risk_manager()
    
    return MomentumBacktestRunner(engine, signal_generator, risk_manager)
