# scripts/dev/verify_regime_backtest.py
import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from extensions.backtest.runner import BacktestRunner
from core.strategy.market_regime_detector import MarketRegimeDetector

def create_mock_data(start_date, end_date):
    """테스트용 데이터 생성"""
    dates = pd.date_range(start_date, end_date, freq='B')
    
    # 1. 종목 데이터 (상승 추세)
    prices = []
    price = 10000
    for _ in range(len(dates)):
        price *= (1 + np.random.normal(0.001, 0.02))
        prices.append(price)
        
    df = pd.DataFrame({
        'close': prices,
        'code': 'TEST001'
    }, index=dates)
    df.index.name = 'date'
    df = df.reset_index().set_index(['code', 'date'])
    
    # 2. 시장 지수 데이터 (하락장 시뮬레이션)
    # 전반부: 상승, 후반부: 급락 (하락장 유도)
    market_prices = []
    m_price = 2000
    mid_point = len(dates) // 2
    
    for i in range(len(dates)):
        if i < mid_point:
            ret = 0.001 # 상승
        else:
            ret = -0.005 # 하락
            
        m_price *= (1 + ret + np.random.normal(0, 0.01))
        market_prices.append(m_price)
        
    market_df = pd.DataFrame({
        'Close': market_prices
    }, index=dates)
    
    return df, market_df

def run_verification():
    print("=== Regime-based Backtest Verification ===")
    
    start_date = date(2022, 1, 1)
    end_date = date(2024, 6, 30)
    
    print("1. Generating Mock Data...")
    price_data, market_data = create_mock_data(start_date, end_date)
    print(f"   Price Data: {len(price_data)} rows")
    print(f"   Market Data: {len(market_data)} rows")
    
    # 2. Runner 초기화
    print("\n2. Initializing BacktestRunner...")
    runner = BacktestRunner(
        initial_capital=10000000,
        enable_defense=True
    )
    
    # 3. 백테스트 실행 (레짐 감지 포함)
    print("\n3. Running Backtest with Regime Detection...")
    target_weights = {'TEST001': 1.0} # 100% 비중
    
    result = runner.run(
        price_data=price_data,
        target_weights=target_weights,
        start_date=start_date,
        end_date=end_date,
        market_index_data=market_data
    )
    
    # 4. 결과 검증
    print("\n4. Verification Results")
    metrics = result['metrics']
    print(f"   Total Return: {metrics.get('total_return', 0):.2f}%")
    print(f"   MDD: {metrics.get('max_drawdown', 0):.2f}%")
    
    # 레짐 감지 확인
    detector = runner.regime_detector
    stats = detector.get_stats()
    print("\n   [Regime Stats]")
    print(f"   Bull Days: {stats.get('bull_days', 0)}")
    print(f"   Bear Days: {stats.get('bear_days', 0)}")
    print(f"   Neutral Days: {stats.get('neutral_days', 0)}")
    
    if stats.get('bear_days', 0) > 0:
        print("   ✅ Bear regime detected successfully.")
    else:
        print("   ❌ No bear regime detected (Check logic or data).")
        
    # 포지션 비중 변화 확인 (로그 대신 간접 확인)
    # 하락장에서 현금 비중이 늘어났는지 확인하려면 상세 로그나 history를 봐야 함
    # 여기서는 실행 자체의 성공 여부와 레짐 감지 여부를 중점으로 확인
    
if __name__ == "__main__":
    run_verification()
