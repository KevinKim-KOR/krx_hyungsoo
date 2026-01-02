# scripts/dev/benchmark_backtest.py
import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import date

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from extensions.backtest.runner import BacktestRunner

def create_mock_data(start_date, end_date):
    """테스트용 데이터 생성"""
    dates = pd.date_range(start_date, end_date, freq='B')
    
    # 1. 종목 데이터 (10개 종목)
    dfs = []
    for i in range(10):
        code = f'TEST{i:03d}'
        prices = []
        price = 10000
        for _ in range(len(dates)):
            price *= (1 + np.random.normal(0.001, 0.02))
            prices.append(price)
            
        df = pd.DataFrame({
            'close': prices,
            'code': code
        }, index=dates)
        dfs.append(df)
        
    result = pd.concat(dfs)
    result.index.name = 'date'
    result = result.reset_index().set_index(['code', 'date'])
    
    return result

def run_benchmark():
    print("=== Backtest Parallel Processing Benchmark ===")
    
    start_date = date(2023, 1, 1)
    end_date = date(2023, 12, 31)
    
    print("1. Generating Mock Data...")
    price_data = create_mock_data(start_date, end_date)
    print(f"   Price Data: {len(price_data)} rows")
    
    # 2. 시나리오 생성 (50개)
    print("\n2. Generating 50 Scenarios...")
    params_list = []
    for i in range(50):
        # 랜덤 비중 생성
        weights = {}
        for j in range(5):
            code = f'TEST{j:03d}'
            weights[code] = 0.2
        
        params_list.append({
            'label': f'Scenario_{i}',
            'target_weights': weights
        })
    
    runner = BacktestRunner()
    
    # 3. 순차 실행 (n_jobs=1)
    print("\n3. Running Sequential (n_jobs=1)...")
    start_time = time.time()
    runner.run_batch(
        price_data=price_data,
        params_list=params_list,
        start_date=start_date,
        end_date=end_date,
        n_jobs=1
    )
    seq_time = time.time() - start_time
    print(f"   Sequential Time: {seq_time:.2f} seconds")
    
    # 4. 병렬 실행 (n_jobs=-1)
    print("\n4. Running Parallel (n_jobs=-1)...")
    start_time = time.time()
    runner.run_batch(
        price_data=price_data,
        params_list=params_list,
        start_date=start_date,
        end_date=end_date,
        n_jobs=-1
    )
    par_time = time.time() - start_time
    print(f"   Parallel Time: {par_time:.2f} seconds")
    
    # 5. 결과 비교
    print("\n5. Benchmark Results")
    speedup = seq_time / par_time
    print(f"   Speedup: {speedup:.2f}x")
    
    if speedup > 1.2:
        print("   ✅ Parallel processing is effective.")
    else:
        print("   ⚠️ Speedup is low (overhead might be high for small tasks).")

if __name__ == "__main__":
    run_benchmark()
