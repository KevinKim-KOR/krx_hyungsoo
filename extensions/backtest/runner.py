# -*- coding: utf-8 -*-
"""
extensions/backtest/runner.py
백테스트 실행기 (친구 코드 참고)
"""
from typing import Dict, List, Optional, Any
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
        initial_capital: float = 10000000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
        max_positions: int = 10,
        rebalance_frequency: str = 'daily',
        instrument_type: str = 'etf',
        enable_defense: bool = True
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.max_positions = max_positions
        self.rebalance_frequency = rebalance_frequency
        self.instrument_type = instrument_type
        self.enable_defense = enable_defense
        
        # 레짐 감지기 초기화
        from core.strategy.market_regime_detector import MarketRegimeDetector
        self.regime_detector = MarketRegimeDetector(enable_regime_detection=enable_defense)
        
    def run(
        self,
        price_data: pd.DataFrame,
        target_weights: Dict[str, float],
        start_date: date,
        end_date: date,
        market_index_data: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        백테스트 실행
        
        Args:
            price_data: 종목별 가격 데이터 (MultiIndex: code, date)
            target_weights: 목표 비중 (종목 코드: 비중)
            start_date: 시작일
            end_date: 종료일
            market_index_data: 시장 지수 데이터 (레짐 감지용)
            
        Returns:
            성과 지표
        """
        # 엔진 생성 (각 실행마다 독립적)
        engine = BacktestEngine(
            initial_capital=self.initial_capital,
            commission_rate=self.commission_rate,
            slippage_rate=self.slippage_rate,
            max_positions=self.max_positions,
            rebalance_frequency=self.rebalance_frequency,
            instrument_type=self.instrument_type
        )
        
        # 날짜 범위 생성
        dates = pd.date_range(start_date, end_date, freq='B')
        
        current_regime = 'neutral'
        position_ratio = 1.0
        
        for current_date in dates:
            d = current_date.date()
            
            # 1. 레짐 감지 및 비중 조절
            if self.enable_defense and market_index_data is not None:
                regime, confidence = self.regime_detector.detect_regime(market_index_data, d)
                
                if regime != current_regime:
                    current_regime = regime
                
                position_ratio = self.regime_detector.get_position_ratio(regime, confidence)
            
            # 2. 현재 가격 조회
            current_prices = {}
            if isinstance(price_data.index, pd.MultiIndex):
                try:
                    daily_data = price_data.xs(d, level='date')
                    current_prices = daily_data['close'].to_dict()
                except KeyError:
                    pass
            
            if not current_prices:
                continue
                
            # NAV 업데이트
            engine.update_nav(d, current_prices)
            
            # 3. 리밸런싱
            # 레짐 반영된 목표 비중 계산
            adjusted_weights = {k: v * position_ratio for k, v in target_weights.items()}
            
            try:
                if adjusted_weights:
                    engine.rebalance(adjusted_weights, current_prices, d)
                else:
                    # logger.warning("목표 비중 없음 - 리밸런싱 건너뜀")
                    pass
            except Exception as e:
                logger.error(f"목표 비중 계산 실패: {e}", exc_info=True)
                adjusted_weights = {}
            
        # 성과 지표 출력
        # logger.info("백테스트 완료")
        metrics = engine.get_performance_metrics()
        
        return {
            'metrics': metrics,
            'nav_history': engine.nav_history,
            'trades': engine.portfolio.trades,
            'final_positions': engine.portfolio.positions
        }


    def run_batch(
        self,
        price_data: pd.DataFrame,
        params_list: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        market_index_data: Optional[pd.DataFrame] = None,
        n_jobs: int = -1
    ) -> List[Dict[str, Any]]:
        """
        배치 백테스트 실행 (병렬 처리)
        
        Args:
            price_data: 가격 데이터
            params_list: 파라미터 리스트 (각 항목은 target_weights 생성 등에 사용될 수 있음)
                         현재 구조에서는 target_weights가 필수이므로, 
                         params_list의 각 항목이 {'target_weights': ..., 'label': ...} 형태라고 가정
            start_date: 시작일
            end_date: 종료일
            market_index_data: 시장 지수 데이터
            n_jobs: 병렬 작업 수 (-1: 모든 코어 사용)
            
        Returns:
            결과 리스트
        """
        from joblib import Parallel, delayed
        import copy
        
        logger.info(f"배치 백테스트 시작: {len(params_list)}개 시나리오, n_jobs={n_jobs}")
        
        def _run_single(params):
            # 엔진 별도 생성 (스레드 안전성 확보)
            runner = BacktestRunner(
                initial_capital=self.initial_capital,
                commission_rate=self.commission_rate,
                slippage_rate=self.slippage_rate,
                max_positions=self.max_positions,
                rebalance_frequency=self.rebalance_frequency,
                instrument_type=self.instrument_type,
                enable_defense=self.enable_defense
            )
            
            # 파라미터 추출
            weights = params.get('target_weights', {})
            label = params.get('label', 'unknown')
            
            try:
                result = runner.run(
                    price_data=price_data,
                    target_weights=weights,
                    start_date=start_date,
                    end_date=end_date,
                    market_index_data=market_index_data
                )
                result['label'] = label
                result['params'] = params
                return result
            except Exception as e:
                logger.error(f"시나리오 실패 ({label}): {e}")
                return {'label': label, 'error': str(e)}

        # 병렬 실행
        results = Parallel(n_jobs=n_jobs)(
            delayed(_run_single)(params) for params in params_list
        )
        
        logger.info("배치 백테스트 완료")
        return results


class MomentumBacktestRunner(BacktestRunner):
    """모멘텀 전략 백테스트 실행기"""
    
    # 기존 로직 유지 (필요 시 오버라이드)
    pass


def create_default_runner(
    initial_capital: float = 10000000,
    max_positions: int = 10
) -> BacktestRunner:
    """기본 백테스트 실행기 생성"""
    return BacktestRunner(
        initial_capital=initial_capital,
        max_positions=max_positions
    )


def create_momentum_runner(
    initial_capital: float = 10000000,
    max_positions: int = 10
) -> MomentumBacktestRunner:
    """모멘텀 백테스트 실행기 생성"""
    return MomentumBacktestRunner(
        initial_capital=initial_capital,
        max_positions=max_positions
    )
