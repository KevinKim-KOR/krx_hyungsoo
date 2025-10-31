# -*- coding: utf-8 -*-
"""
extensions/optuna/robustness.py
로버스트니스 테스트 (민감도 분석, 부트스트랩 등)
"""
import numpy as np
import pandas as pd
from datetime import date
from typing import Dict, List, Optional
from pathlib import Path
import logging

from extensions.backtest.runner import BacktestRunner
from core.engine.backtest import BacktestEngine
from core.strategy.signals import SignalGenerator
from infra.data.loader import load_price_data
from core.data.filtering import get_filtered_universe

logger = logging.getLogger(__name__)


class RobustnessAnalyzer:
    """로버스트니스 분석기"""
    
    def __init__(
        self,
        base_params: Dict,
        start_date: date,
        end_date: date,
        n_iterations: int = 30,
        seed: int = 42
    ):
        """
        Args:
            base_params: 기본 파라미터
            start_date: 시작일
            end_date: 종료일
            n_iterations: 반복 횟수
            seed: 랜덤 시드
        """
        self.base_params = base_params
        self.start_date = start_date
        self.end_date = end_date
        self.n_iterations = n_iterations
        self.seed = seed
        
        # 데이터 로드
        self.universe = get_filtered_universe()
        self.price_data = load_price_data(self.universe, start_date, end_date)
        
        self.results = {
            'seed_variation': [],
            'sample_drop': [],
            'bootstrap': [],
            'commission_sensitivity': [],
            'slippage_sensitivity': []
        }
    
    def run_all_tests(self, output_dir: Optional[Path] = None) -> Dict[str, pd.DataFrame]:
        """
        모든 로버스트니스 테스트 실행
        
        Args:
            output_dir: 결과 저장 디렉토리
            
        Returns:
            테스트별 결과 DataFrame 딕셔너리
        """
        logger.info("=" * 60)
        logger.info("로버스트니스 테스트 시작")
        logger.info("=" * 60)
        
        # 1. 시드 변동 테스트
        logger.info("\n1. 시드 변동 테스트")
        self.test_seed_variation()
        
        # 2. 샘플 드롭 테스트
        logger.info("\n2. 샘플 드롭 테스트 (데이터 누락 시뮬레이션)")
        self.test_sample_drop()
        
        # 3. 부트스트랩 테스트
        logger.info("\n3. 부트스트랩 테스트")
        self.test_bootstrap()
        
        # 4. 수수료 민감도
        logger.info("\n4. 수수료 민감도 분석")
        self.test_commission_sensitivity()
        
        # 5. 슬리피지 민감도
        logger.info("\n5. 슬리피지 민감도 분석")
        self.test_slippage_sensitivity()
        
        # 결과 DataFrame 변환
        results_df = {
            'seed_variation': pd.DataFrame(self.results['seed_variation']),
            'sample_drop': pd.DataFrame(self.results['sample_drop']),
            'bootstrap': pd.DataFrame(self.results['bootstrap']),
            'commission_sensitivity': pd.DataFrame(self.results['commission_sensitivity']),
            'slippage_sensitivity': pd.DataFrame(self.results['slippage_sensitivity'])
        }
        
        # 결과 저장
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for test_name, df in results_df.items():
                csv_path = output_dir / f'{test_name}.csv'
                df.to_csv(csv_path, index=False)
                logger.info(f"저장: {csv_path}")
        
        # 요약 출력
        self._print_summary(results_df)
        
        return results_df
    
    def test_seed_variation(self):
        """시드 변동 테스트"""
        for i in range(self.n_iterations):
            seed = self.seed + i
            result = self._run_backtest(
                params=self.base_params,
                seed=seed
            )
            
            self.results['seed_variation'].append({
                'iteration': i,
                'seed': seed,
                'total_return': result.get('total_return', 0.0),
                'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                'max_drawdown': result.get('max_drawdown', 0.0),
                'win_rate': result.get('win_rate', 0.0)
            })
    
    def test_sample_drop(self):
        """샘플 드롭 테스트 (데이터 누락 시뮬레이션)"""
        drop_rates = [0.05, 0.10, 0.15, 0.20]  # 5%, 10%, 15%, 20% 누락
        
        for drop_rate in drop_rates:
            for i in range(10):  # 각 비율당 10회 반복
                result = self._run_backtest(
                    params=self.base_params,
                    drop_rate=drop_rate,
                    seed=self.seed + i
                )
                
                self.results['sample_drop'].append({
                    'drop_rate': drop_rate,
                    'iteration': i,
                    'total_return': result.get('total_return', 0.0),
                    'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                    'max_drawdown': result.get('max_drawdown', 0.0)
                })
    
    def test_bootstrap(self):
        """부트스트랩 테스트"""
        for i in range(self.n_iterations):
            result = self._run_backtest(
                params=self.base_params,
                bootstrap=True,
                seed=self.seed + i
            )
            
            self.results['bootstrap'].append({
                'iteration': i,
                'total_return': result.get('total_return', 0.0),
                'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                'max_drawdown': result.get('max_drawdown', 0.0)
            })
    
    def test_commission_sensitivity(self):
        """수수료 민감도 분석"""
        commission_rates = [0.0, 0.00005, 0.00015, 0.0003, 0.0005]  # 0%, 0.005%, 0.015%, 0.03%, 0.05%
        
        for rate in commission_rates:
            result = self._run_backtest(
                params=self.base_params,
                commission_rate=rate
            )
            
            self.results['commission_sensitivity'].append({
                'commission_rate': rate,
                'commission_pct': rate * 100,
                'total_return': result.get('total_return', 0.0),
                'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                'max_drawdown': result.get('max_drawdown', 0.0)
            })
    
    def test_slippage_sensitivity(self):
        """슬리피지 민감도 분석"""
        slippage_rates = [0.0, 0.0005, 0.001, 0.002, 0.005]  # 0%, 0.05%, 0.1%, 0.2%, 0.5%
        
        for rate in slippage_rates:
            result = self._run_backtest(
                params=self.base_params,
                slippage_rate=rate
            )
            
            self.results['slippage_sensitivity'].append({
                'slippage_rate': rate,
                'slippage_pct': rate * 100,
                'total_return': result.get('total_return', 0.0),
                'sharpe_ratio': result.get('sharpe_ratio', 0.0),
                'max_drawdown': result.get('max_drawdown', 0.0)
            })
    
    def _run_backtest(
        self,
        params: Dict,
        seed: Optional[int] = None,
        drop_rate: float = 0.0,
        bootstrap: bool = False,
        commission_rate: float = 0.00015,
        slippage_rate: float = 0.001
    ) -> Dict:
        """
        백테스트 실행
        
        Args:
            params: 파라미터
            seed: 랜덤 시드
            drop_rate: 데이터 누락 비율
            bootstrap: 부트스트랩 여부
            commission_rate: 수수료율
            slippage_rate: 슬리피지율
            
        Returns:
            성과 지표
        """
        try:
            # 데이터 처리
            price_data = self.price_data.copy()
            
            if drop_rate > 0:
                # 랜덤하게 데이터 제거
                np.random.seed(seed or self.seed)
                mask = np.random.random(len(price_data)) > drop_rate
                price_data = price_data[mask]
            
            if bootstrap:
                # 부트스트랩 샘플링 (복원 추출)
                np.random.seed(seed or self.seed)
                indices = np.random.choice(len(price_data), size=len(price_data), replace=True)
                price_data = price_data.iloc[indices].sort_index()
            
            # 백테스트 실행
            engine = BacktestEngine(
                initial_capital=10_000_000,
                commission_rate=commission_rate,
                slippage_rate=slippage_rate
            )
            
            signal_generator = SignalGenerator(
                ma_period=params.get('ma_period', 60),
                rsi_period=params.get('rsi_period', 14),
                rsi_overbought=params.get('rsi_overbought', 70)
            )
            
            runner = BacktestRunner(
                engine=engine,
                signal_generator=signal_generator,
                max_positions=params.get('max_positions', 10)
            )
            
            runner.run(
                price_data=price_data,
                start_date=self.start_date,
                end_date=self.end_date,
                universe=self.universe,
                rebalance_frequency=params.get('rebalance_frequency', 'monthly')
            )
            
            return engine.calculate_performance_metrics()
        
        except Exception as e:
            logger.error(f"백테스트 실패: {e}")
            return {}
    
    def _print_summary(self, results_df: Dict[str, pd.DataFrame]):
        """결과 요약 출력"""
        logger.info("\n" + "=" * 60)
        logger.info("로버스트니스 테스트 요약")
        logger.info("=" * 60)
        
        # 1. 시드 변동
        if len(results_df['seed_variation']) > 0:
            df = results_df['seed_variation']
            logger.info("\n1. 시드 변동 테스트")
            logger.info(f"   평균 수익률: {df['total_return'].mean():.2f}% (±{df['total_return'].std():.2f}%)")
            logger.info(f"   평균 샤프: {df['sharpe_ratio'].mean():.2f} (±{df['sharpe_ratio'].std():.2f})")
            logger.info(f"   평균 MDD: {df['max_drawdown'].mean():.2f}% (±{df['max_drawdown'].std():.2f}%)")
        
        # 2. 샘플 드롭
        if len(results_df['sample_drop']) > 0:
            df = results_df['sample_drop']
            logger.info("\n2. 샘플 드롭 테스트")
            for rate in df['drop_rate'].unique():
                subset = df[df['drop_rate'] == rate]
                logger.info(f"   누락률 {rate*100:.0f}%: 수익률 {subset['total_return'].mean():.2f}% (±{subset['total_return'].std():.2f}%)")
        
        # 3. 부트스트랩
        if len(results_df['bootstrap']) > 0:
            df = results_df['bootstrap']
            logger.info("\n3. 부트스트랩 테스트 (95% 신뢰구간)")
            logger.info(f"   수익률: {df['total_return'].quantile(0.025):.2f}% ~ {df['total_return'].quantile(0.975):.2f}%")
            logger.info(f"   샤프: {df['sharpe_ratio'].quantile(0.025):.2f} ~ {df['sharpe_ratio'].quantile(0.975):.2f}")
        
        # 4. 수수료 민감도
        if len(results_df['commission_sensitivity']) > 0:
            df = results_df['commission_sensitivity']
            logger.info("\n4. 수수료 민감도")
            for _, row in df.iterrows():
                logger.info(f"   {row['commission_pct']:.3f}%: 수익률 {row['total_return']:.2f}%")
        
        # 5. 슬리피지 민감도
        if len(results_df['slippage_sensitivity']) > 0:
            df = results_df['slippage_sensitivity']
            logger.info("\n5. 슬리피지 민감도")
            for _, row in df.iterrows():
                logger.info(f"   {row['slippage_pct']:.2f}%: 수익률 {row['total_return']:.2f}%")


def run_robustness_tests(
    base_params: Dict,
    start_date: date,
    end_date: date,
    n_iterations: int = 30,
    output_dir: Optional[Path] = None,
    seed: int = 42
) -> Dict[str, pd.DataFrame]:
    """
    로버스트니스 테스트 실행 헬퍼
    
    Args:
        base_params: 기본 파라미터
        start_date: 시작일
        end_date: 종료일
        n_iterations: 반복 횟수
        output_dir: 결과 저장 디렉토리
        seed: 랜덤 시드
        
    Returns:
        테스트별 결과 DataFrame 딕셔너리
    """
    analyzer = RobustnessAnalyzer(
        base_params=base_params,
        start_date=start_date,
        end_date=end_date,
        n_iterations=n_iterations,
        seed=seed
    )
    
    return analyzer.run_all_tests(output_dir)
