# -*- coding: utf-8 -*-
"""
tests/integration/test_backtest_pipeline.py
백테스트 파이프라인 통합 테스트
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, timedelta
from pathlib import Path
import tempfile
import shutil

from core.engine.backtest import BacktestEngine, create_default_backtest_engine
from extensions.backtest.runner import BacktestRunner, create_momentum_runner
from extensions.backtest.report import create_report
from core.strategy.signals import create_default_signal_generator
from core.risk.manager import create_default_risk_manager


class TestBacktestPipeline:
    """백테스트 파이프라인 통합 테스트"""
    
    @pytest.fixture
    def sample_price_data(self):
        """샘플 가격 데이터 생성"""
        # 3개 종목, 100일 데이터
        symbols = ['069500', '091160', '133690']
        dates = pd.date_range(end=date.today(), periods=100, freq='D')
        
        data = []
        for symbol in symbols:
            # 상승 추세 + 랜덤 노이즈
            base_price = 10000 + np.random.randint(-1000, 1000)
            prices = base_price + np.cumsum(np.random.randn(100) * 100 + 10)
            
            for i, d in enumerate(dates):
                data.append({
                    'code': symbol,
                    'date': d,
                    'open': prices[i] * 0.99,
                    'high': prices[i] * 1.02,
                    'low': prices[i] * 0.98,
                    'close': prices[i],
                    'volume': np.random.randint(100000, 500000)
                })
        
        df = pd.DataFrame(data)
        df = df.set_index(['code', 'date'])
        
        return df
    
    @pytest.mark.integration
    def test_backtest_engine_basic(self):
        """백테스트 엔진 기본 테스트"""
        engine = create_default_backtest_engine()
        
        # 초기 상태
        assert engine.portfolio.cash == 10000000
        assert len(engine.portfolio.positions) == 0
        
        # 매수
        success = engine.execute_buy('TEST', 100, 10000, date.today())
        assert success
        assert 'TEST' in engine.portfolio.positions
        assert engine.portfolio.cash < 10000000
        
        # 매도
        success = engine.execute_sell('TEST', 50, 11000, date.today())
        assert success
        assert engine.portfolio.positions['TEST'].quantity == 50
        
        print("Engine basic test: PASSED")
    
    @pytest.mark.integration
    def test_backtest_engine_rebalance(self):
        """백테스트 엔진 리밸런싱 테스트"""
        engine = create_default_backtest_engine()
        
        # 목표 비중
        target_weights = {
            'A': 0.5,
            'B': 0.3,
            'C': 0.2
        }
        
        current_prices = {
            'A': 10000,
            'B': 20000,
            'C': 30000
        }
        
        # 리밸런싱
        engine.rebalance(target_weights, current_prices, date.today())
        
        # 검증
        assert len(engine.portfolio.positions) == 3
        
        total_value = engine.portfolio.total_value
        for symbol, target_weight in target_weights.items():
            if symbol in engine.portfolio.positions:
                position = engine.portfolio.positions[symbol]
                actual_weight = position.market_value / total_value
                # 오차 허용 (거래 단위로 인한)
                assert abs(actual_weight - target_weight) < 0.05
        
        print("Engine rebalance test: PASSED")
    
    @pytest.mark.integration
    def test_backtest_runner(self, sample_price_data):
        """백테스트 실행기 테스트"""
        # 러너 생성
        runner = create_momentum_runner(
            initial_capital=10000000,
            max_positions=3
        )
        
        # 백테스트 실행
        universe = ['069500', '091160', '133690']
        start_date = sample_price_data.index.get_level_values('date').min()
        end_date = sample_price_data.index.get_level_values('date').max()
        
        result = runner.run(
            price_data=sample_price_data,
            start_date=start_date,
            end_date=end_date,
            universe=universe,
            rebalance_frequency='weekly'
        )
        
        # 검증
        assert 'metrics' in result
        assert 'nav_history' in result
        assert 'trades' in result
        
        metrics = result['metrics']
        assert 'total_return' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        
        print(f"Total return: {metrics['total_return']:.2f}%")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"MDD: {metrics['max_drawdown']:.2f}%")
        print(f"Total trades: {metrics['total_trades']}")
        
        print("Runner test: PASSED")
    
    @pytest.mark.integration
    def test_backtest_report(self, sample_price_data):
        """백테스트 리포트 테스트"""
        # 백테스트 실행
        runner = create_momentum_runner(initial_capital=10000000, max_positions=3)
        
        universe = ['069500', '091160', '133690']
        start_date = sample_price_data.index.get_level_values('date').min()
        end_date = sample_price_data.index.get_level_values('date').max()
        
        result = runner.run(
            price_data=sample_price_data,
            start_date=start_date,
            end_date=end_date,
            universe=universe,
            rebalance_frequency='monthly'
        )
        
        # 리포트 생성
        report = create_report(result)
        
        # 요약 리포트
        summary = report.generate_summary()
        assert len(summary) > 0
        assert '백테스트 성과 요약' in summary
        
        # NAV 시계열
        nav_series = report.generate_nav_series()
        assert not nav_series.empty
        assert len(nav_series) > 0
        
        # 거래 로그
        trade_log = report.generate_trade_log()
        if not trade_log.empty:
            assert 'symbol' in trade_log.columns
            assert 'action' in trade_log.columns
        
        print("Report test: PASSED")
    
    @pytest.mark.integration
    def test_full_backtest_pipeline(self, sample_price_data):
        """전체 백테스트 파이프라인 테스트"""
        # Step 1: 백테스트 실행
        runner = create_momentum_runner(
            initial_capital=10000000,
            max_positions=5
        )
        
        universe = ['069500', '091160', '133690']
        start_date = sample_price_data.index.get_level_values('date').min()
        end_date = sample_price_data.index.get_level_values('date').max()
        
        result = runner.run(
            price_data=sample_price_data,
            start_date=start_date,
            end_date=end_date,
            universe=universe,
            rebalance_frequency='weekly'
        )
        
        # Step 2: 리포트 생성
        report = create_report(result)
        
        # Step 3: 파일 저장
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / 'backtest_results'
            report.save_to_file(output_dir)
            
            # 파일 확인
            assert (output_dir / 'summary.txt').exists()
            assert (output_dir / 'nav.csv').exists()
            
            # 요약 출력
            with open(output_dir / 'summary.txt', 'r', encoding='utf-8') as f:
                summary = f.read()
                print("\n" + summary)
        
        print("Full pipeline test: PASSED")
    
    @pytest.mark.integration
    def test_performance_metrics_calculation(self):
        """성과 지표 계산 테스트"""
        engine = create_default_backtest_engine()
        
        # 가상 NAV 히스토리 생성
        base_date = date.today() - timedelta(days=100)
        for i in range(100):
            current_date = base_date + timedelta(days=i)
            nav = 10000000 * (1 + i * 0.001)  # 0.1% 일간 수익
            engine.nav_history.append((current_date, nav))
            
            if i > 0:
                prev_nav = engine.nav_history[i-1][1]
                daily_return = (nav / prev_nav - 1.0)
                engine.daily_returns.append(daily_return)
        
        # 성과 지표 계산
        metrics = engine.get_performance_metrics()
        
        # 검증
        assert metrics['total_return'] > 0
        assert metrics['annual_return'] > 0
        assert metrics['volatility'] >= 0
        assert metrics['max_drawdown'] <= 0
        assert 0 <= metrics['win_rate'] <= 100
        
        print(f"Total return: {metrics['total_return']:.2f}%")
        print(f"Annual return: {metrics['annual_return']:.2f}%")
        print(f"Volatility: {metrics['volatility']:.2f}%")
        print(f"Sharpe ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"MDD: {metrics['max_drawdown']:.2f}%")
        
        print("Metrics calculation test: PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
