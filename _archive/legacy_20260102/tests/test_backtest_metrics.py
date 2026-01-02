# -*- coding: utf-8 -*-
"""
tests/test_backtest_metrics.py
백테스트 성과 지표 계산 테스트
"""
from datetime import date, timedelta
import numpy as np
import sys
sys.path.insert(0, '.')

from core.engine.backtest import BacktestEngine


def test_metrics_calculation():
    """성과 지표 계산 테스트"""
    print("=== 백테스트 엔진 성과 지표 테스트 ===\n")
    
    # 테스트 케이스 1: 1년간 10% 수익
    print("--- 테스트 1: 1년간 10% 수익 시뮬레이션 ---")
    engine = BacktestEngine(initial_capital=10000000)
    
    np.random.seed(42)
    daily_returns = np.random.normal(0.0004, 0.01, 252)
    nav = 10000000
    
    start_date = date(2024, 1, 1)
    for i, ret in enumerate(daily_returns):
        d = start_date + timedelta(days=i)
        nav *= (1 + ret)
        engine.nav_history.append((d, nav))
        if i > 0:
            engine.daily_returns.append(ret)
    
    metrics = engine.get_performance_metrics()
    
    print(f"  Total Return: {metrics['total_return']:.2f}%")
    print(f"  CAGR: {metrics['cagr']:.2f}%")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"  MDD: {metrics['max_drawdown']:.2f}% (positive)")
    print(f"  Calmar Ratio: {metrics['calmar_ratio']:.2f}")
    print(f"  Volatility: {metrics['volatility']:.2f}%")
    print(f"  Calendar Days: {metrics['calendar_days']}")
    print(f"  Trading Days: {metrics['trading_days']}")
    print(f"  Years: {metrics['years']:.4f}")
    
    # 검증
    assert metrics['max_drawdown'] >= 0, "MDD should be positive"
    assert 'calmar_ratio' in metrics, "Calmar ratio should exist"
    assert metrics['years'] > 0, "Years should be positive"
    print("\n  [PASS] All assertions passed!\n")
    
    # 테스트 케이스 2: 3년간 100% 수익
    print("--- 테스트 2: 3년간 100% 수익 시뮬레이션 ---")
    engine2 = BacktestEngine(initial_capital=10000000)
    
    np.random.seed(123)
    daily_returns2 = np.random.normal(0.001, 0.015, 756)  # 3년
    nav2 = 10000000
    
    start_date2 = date(2022, 1, 1)
    for i, ret in enumerate(daily_returns2):
        d = start_date2 + timedelta(days=i)
        nav2 *= (1 + ret)
        engine2.nav_history.append((d, nav2))
        if i > 0:
            engine2.daily_returns.append(ret)
    
    metrics2 = engine2.get_performance_metrics()
    
    print(f"  Total Return: {metrics2['total_return']:.2f}%")
    print(f"  CAGR: {metrics2['cagr']:.2f}%")
    print(f"  Sharpe Ratio: {metrics2['sharpe_ratio']:.2f}")
    print(f"  MDD: {metrics2['max_drawdown']:.2f}% (positive)")
    print(f"  Calmar Ratio: {metrics2['calmar_ratio']:.2f}")
    print(f"  Years: {metrics2['years']:.4f}")
    
    # CAGR 수동 계산 검증
    final_value = engine2.nav_history[-1][1]
    initial_value = 10000000
    years = metrics2['years']
    expected_cagr = ((final_value / initial_value) ** (1 / years) - 1) * 100
    
    print(f"\n  Manual CAGR calculation: {expected_cagr:.2f}%")
    print(f"  Engine CAGR: {metrics2['cagr']:.2f}%")
    
    assert abs(metrics2['cagr'] - expected_cagr) < 0.01, "CAGR calculation mismatch"
    print("\n  [PASS] CAGR calculation verified!\n")
    
    print("=== All tests passed! ===")


if __name__ == "__main__":
    test_metrics_calculation()
