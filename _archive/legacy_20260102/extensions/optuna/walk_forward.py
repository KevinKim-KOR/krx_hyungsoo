# -*- coding: utf-8 -*-
"""
extensions/optuna/walk_forward.py
워크포워드 분석 (Walk-Forward Analysis)
"""
import optuna
import pandas as pd
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
import logging

from extensions.optuna.objective import BacktestObjective
from extensions.backtest.runner import BacktestRunner
from core.engine.backtest import BacktestEngine
from core.strategy.signals import SignalGenerator
from infra.data.loader import load_price_data
from core.data.filtering import get_filtered_universe

logger = logging.getLogger(__name__)


class WalkForwardAnalyzer:
    """워크포워드 분석기"""
    
    def __init__(
        self,
        train_period_months: int = 12,
        test_period_months: int = 3,
        window_type: str = 'sliding',  # 'sliding' or 'expanding'
        n_trials: int = 50,
        seed: Optional[int] = 42
    ):
        """
        Args:
            train_period_months: 학습 기간 (개월)
            test_period_months: 검증 기간 (개월)
            window_type: 윈도우 타입 ('sliding': 슬라이딩, 'expanding': 확장)
            n_trials: Optuna 시행 횟수
            seed: 랜덤 시드
        """
        self.train_period_months = train_period_months
        self.test_period_months = test_period_months
        self.window_type = window_type
        self.n_trials = n_trials
        self.seed = seed
        
        self.results = []
    
    def _split_periods(
        self,
        start_date: date,
        end_date: date
    ) -> List[Tuple[date, date, date, date]]:
        """
        학습/검증 기간 분할
        
        Args:
            start_date: 전체 시작일
            end_date: 전체 종료일
            
        Returns:
            [(train_start, train_end, test_start, test_end), ...]
        """
        periods = []
        current_date = start_date
        
        while True:
            # 학습 기간
            if self.window_type == 'sliding':
                train_start = current_date
            else:  # expanding
                train_start = start_date
            
            train_end = current_date + timedelta(days=self.train_period_months * 30)
            
            # 검증 기간
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.test_period_months * 30)
            
            if test_end > end_date:
                break
            
            periods.append((train_start, train_end, test_start, test_end))
            
            # 다음 윈도우로 이동
            current_date = test_start
        
        return periods
    
    def run(
        self,
        start_date: date,
        end_date: date,
        output_dir: Optional[Path] = None
    ) -> pd.DataFrame:
        """
        워크포워드 분석 실행
        
        Args:
            start_date: 전체 시작일
            end_date: 전체 종료일
            output_dir: 결과 저장 디렉토리
            
        Returns:
            결과 DataFrame
        """
        logger.info("=" * 60)
        logger.info(f"워크포워드 분석 시작 ({self.window_type} 윈도우)")
        logger.info(f"학습: {self.train_period_months}개월, 검증: {self.test_period_months}개월")
        logger.info("=" * 60)
        
        # 기간 분할
        periods = self._split_periods(start_date, end_date)
        logger.info(f"총 {len(periods)}개 윈도우 생성")
        
        # 각 윈도우별 최적화 및 검증
        for i, (train_start, train_end, test_start, test_end) in enumerate(periods, 1):
            logger.info(f"\n[윈도우 {i}/{len(periods)}]")
            logger.info(f"학습: {train_start} ~ {train_end}")
            logger.info(f"검증: {test_start} ~ {test_end}")
            
            # 1. 학습 기간 최적화
            logger.info("파라미터 최적화 중...")
            study = optuna.create_study(
                direction='maximize',
                sampler=optuna.samplers.TPESampler(seed=self.seed)
            )
            
            objective = BacktestObjective(
                start_date=train_start,
                end_date=train_end,
                seed=self.seed
            )
            
            study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)
            
            best_params = study.best_params
            logger.info(f"최적 파라미터: {best_params}")
            logger.info(f"학습 성과: {study.best_value:.4f}")
            
            # 2. 검증 기간 테스트
            logger.info("검증 기간 테스트 중...")
            test_result = self._test_params(
                params=best_params,
                start_date=test_start,
                end_date=test_end
            )
            
            # 3. 결과 저장
            result = {
                'window': i,
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end,
                'best_params': best_params,
                'train_score': study.best_value,
                'test_return': test_result.get('total_return', 0.0),
                'test_sharpe': test_result.get('sharpe_ratio', 0.0),
                'test_mdd': test_result.get('max_drawdown', 0.0),
            }
            
            self.results.append(result)
            
            logger.info(f"검증 수익률: {test_result.get('total_return', 0.0):.2f}%")
            logger.info(f"검증 샤프: {test_result.get('sharpe_ratio', 0.0):.2f}")
        
        # 결과 DataFrame 생성
        df_results = pd.DataFrame(self.results)
        
        # 결과 저장
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # CSV 저장
            csv_path = output_dir / 'walk_forward_results.csv'
            df_results.to_csv(csv_path, index=False)
            logger.info(f"결과 저장: {csv_path}")
            
            # JSON 저장 (파라미터 포함)
            json_path = output_dir / 'walk_forward_results.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, default=str)
            logger.info(f"상세 결과 저장: {json_path}")
        
        # 요약 통계
        logger.info("\n" + "=" * 60)
        logger.info("워크포워드 분석 요약")
        logger.info("=" * 60)
        logger.info(f"평균 검증 수익률: {df_results['test_return'].mean():.2f}%")
        logger.info(f"평균 검증 샤프: {df_results['test_sharpe'].mean():.2f}")
        logger.info(f"평균 검증 MDD: {df_results['test_mdd'].mean():.2f}%")
        logger.info(f"승률: {(df_results['test_return'] > 0).sum() / len(df_results) * 100:.1f}%")
        
        return df_results
    
    def _test_params(
        self,
        params: Dict,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        파라미터로 백테스트 실행
        
        Args:
            params: 파라미터 딕셔너리
            start_date: 시작일
            end_date: 종료일
            
        Returns:
            성과 지표 딕셔너리
        """
        try:
            # 데이터 로드
            universe = get_filtered_universe()
            price_data = load_price_data(universe, start_date, end_date)
            
            # 백테스트 실행
            from core.risk.manager import RiskManager
            
            engine = BacktestEngine(initial_capital=10_000_000)
            signal_generator = SignalGenerator(
                ma_period=params.get('ma_period', 60),
                rsi_period=params.get('rsi_period', 14),
                rsi_overbought=params.get('rsi_overbought', 70)
            )
            
            risk_manager = RiskManager()
            
            runner = BacktestRunner(
                engine=engine,
                signal_generator=signal_generator,
                risk_manager=risk_manager
            )
            
            runner.run(
                price_data=price_data,
                start_date=start_date,
                end_date=end_date,
                universe=universe,
                rebalance_frequency=params.get('rebalance_frequency', 'monthly')
            )
            
            # 성과 계산
            return engine.get_performance_metrics()
        
        except Exception as e:
            logger.error(f"백테스트 실패: {e}")
            return {}


def run_walk_forward(
    start_date: date,
    end_date: date,
    train_months: int = 12,
    test_months: int = 3,
    window_type: str = 'sliding',
    n_trials: int = 50,
    output_dir: Optional[Path] = None,
    seed: int = 42
) -> pd.DataFrame:
    """
    워크포워드 분석 실행 헬퍼
    
    Args:
        start_date: 시작일
        end_date: 종료일
        train_months: 학습 기간 (개월)
        test_months: 검증 기간 (개월)
        window_type: 윈도우 타입
        n_trials: Optuna 시행 횟수
        output_dir: 결과 저장 디렉토리
        seed: 랜덤 시드
        
    Returns:
        결과 DataFrame
    """
    analyzer = WalkForwardAnalyzer(
        train_period_months=train_months,
        test_period_months=test_months,
        window_type=window_type,
        n_trials=n_trials,
        seed=seed
    )
    
    return analyzer.run(start_date, end_date, output_dir)
