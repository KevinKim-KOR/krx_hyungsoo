# -*- coding: utf-8 -*-
"""
extensions/optuna/objective.py
Optuna 목적 함수 (백테스트 기반)
"""
import optuna
from datetime import date, datetime
from typing import Dict, Any, Optional
import numpy as np

from extensions.backtest.runner import BacktestRunner
from extensions.optuna.space import suggest_all_params
from core.data.filtering import ETFFilter
from infra.data.loader import load_price_data


class BacktestObjective:
    """백테스트 기반 목적 함수"""
    
    def __init__(
        self,
        start_date: date,
        end_date: date,
        initial_capital: float = 10_000_000,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001,
        mdd_penalty_lambda: float = 2.0,
        seed: Optional[int] = None
    ):
        """
        Args:
            start_date: 백테스트 시작일
            end_date: 백테스트 종료일
            initial_capital: 초기 자본
            commission_rate: 수수료율
            slippage_rate: 슬리피지율
            mdd_penalty_lambda: MDD 패널티 계수 (기본 2.0)
            seed: 랜덤 시드 (재현성)
        """
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.mdd_penalty_lambda = mdd_penalty_lambda
        self.seed = seed
        
        # 유니버스 및 데이터 로드 (한 번만)
        etf_filter = ETFFilter()
        self.universe = etf_filter.get_filtered_universe()
        self.price_data = load_price_data(
            self.universe,
            self.start_date,
            self.end_date
        )
    
    def __call__(self, trial: optuna.Trial) -> float:
        """
        목적 함수 실행
        
        Args:
            trial: Optuna trial
            
        Returns:
            목적 함수 값 (연율화 수익률 - λ·MDD)
        """
        # 파라미터 샘플링
        params = suggest_all_params(trial)
        
        try:
            # 백테스트 실행
            runner = BacktestRunner(
                universe=self.universe,
                start_date=self.start_date,
                end_date=self.end_date,
                initial_capital=self.initial_capital,
                commission_rate=self.commission_rate,
                slippage_rate=self.slippage_rate,
                rebalance_frequency=params['rebalance_frequency'],
                max_positions=params['max_positions']
            )
            
            # 가격 데이터 설정
            runner.price_data = self.price_data
            
            # 실행
            result = runner.run()
            
            if result is None or result.empty:
                return -999.0
            
            # 성과 지표 계산
            metrics = runner.engine.calculate_performance_metrics()
            
            # 목적 함수: 연율화 수익률 - λ·MDD
            annual_return = metrics.get('annual_return', 0.0)
            mdd = abs(metrics.get('max_drawdown', 0.0))
            
            objective_value = annual_return - self.mdd_penalty_lambda * mdd
            
            # 추가 메트릭 로깅
            trial.set_user_attr('annual_return', annual_return)
            trial.set_user_attr('mdd', -mdd)
            trial.set_user_attr('sharpe', metrics.get('sharpe_ratio', 0.0))
            trial.set_user_attr('total_return', metrics.get('total_return', 0.0))
            trial.set_user_attr('volatility', metrics.get('volatility', 0.0))
            trial.set_user_attr('win_rate', metrics.get('win_rate', 0.0))
            
            return objective_value
        
        except Exception as e:
            print(f"Trial {trial.number} failed: {e}")
            return -999.0


def create_objective(
    start_date: date,
    end_date: date,
    initial_capital: float = 10_000_000,
    mdd_penalty_lambda: float = 2.0,
    seed: Optional[int] = None
) -> BacktestObjective:
    """
    목적 함수 생성 헬퍼
    
    Args:
        start_date: 백테스트 시작일
        end_date: 백테스트 종료일
        initial_capital: 초기 자본
        mdd_penalty_lambda: MDD 패널티 계수
        seed: 랜덤 시드
        
    Returns:
        BacktestObjective 인스턴스
    """
    return BacktestObjective(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        mdd_penalty_lambda=mdd_penalty_lambda,
        seed=seed
    )
