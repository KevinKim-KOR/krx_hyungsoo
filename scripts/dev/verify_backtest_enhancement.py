# scripts/dev/verify_backtest_enhancement.py
import sys
import os
import pandas as pd
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from core.engine.backtest import BacktestEngine

def run_verification():
    print("=== Backtest Engine Enhancement Verification ===")
    
    # 1. Test ETF (Tax 0%)
    print("\n[Test 1] ETF Backtest (Tax should be 0)")
    engine_etf = BacktestEngine(
        initial_capital=10000000,
        instrument_type='etf',
        commission_rate=0.00015, # 0.015%
        slippage_rate=0.001      # 0.1%
    )
    
    # Buy
    engine_etf.execute_buy('ETF001', 100, 10000, date(2024, 1, 1))
    engine_etf.update_nav(date(2024, 1, 1), {'ETF001': 10000})
    
    # Sell
    engine_etf.execute_sell('ETF001', 100, 11000, date(2024, 1, 2))
    engine_etf.update_nav(date(2024, 1, 2), {'ETF001': 11000})
    
    metrics_etf = engine_etf.get_performance_metrics()
    print(f"Total Tax: {metrics_etf.get('total_tax', -1):.2f}")
    print(f"Cost Drag: {metrics_etf.get('cost_drag', 0):.4f}%")
    
    if metrics_etf.get('total_tax', -1) == 0:
        print("✅ ETF Tax is 0 (Pass)")
    else:
        print(f"❌ ETF Tax is {metrics_etf.get('total_tax')} (Fail)")
        
    # 2. Test Stock (Tax 0.23%)
    print("\n[Test 2] Stock Backtest (Tax should be applied)")
    engine_stock = BacktestEngine(
        initial_capital=10000000,
        instrument_type='stock',
        commission_rate=0.00015,
        slippage_rate=0.001
    )
    
    # Buy
    engine_stock.execute_buy('STOCK001', 100, 10000, date(2024, 1, 1))
    engine_stock.update_nav(date(2024, 1, 1), {'STOCK001': 10000})
    
    # Sell (Amount: 100 * 11000 = 1,100,000)
    # Tax: 1,100,000 * 0.0023 = 2,530
    engine_stock.execute_sell('STOCK001', 100, 11000, date(2024, 1, 2))
    engine_stock.update_nav(date(2024, 1, 2), {'STOCK001': 11000})
    
    metrics_stock = engine_stock.get_performance_metrics()
    print(f"Total Tax: {metrics_stock.get('total_tax', -1):.2f}")
    print(f"Cost Drag: {metrics_stock.get('cost_drag', 0):.4f}%")
    
    adjusted_price = 11000 * (1 - 0.001) # 10989
    trade_amount = 100 * adjusted_price # 1,098,900
    expected_tax_val = trade_amount * 0.0023 # 2527.47
    
    print(f"Expected Tax: {expected_tax_val:.2f}")
    
    if abs(metrics_stock.get('total_tax', 0) - expected_tax_val) < 1.0:
        print("✅ Stock Tax is correct (Pass)")
    else:
        print(f"❌ Stock Tax mismatch (Fail)")

    # 3. Gross vs Net
    print("\n[Test 3] Gross vs Net Logic")
    # Gross return should be higher than Net return (Cost Drag > 0)
    if metrics_stock.get('total_return_gross', 0) > metrics_stock.get('total_return', 0):
        print(f"✅ Gross Return ({metrics_stock.get('total_return_gross'):.2f}%) > Net Return ({metrics_stock.get('total_return'):.2f}%)")
        print(f"✅ Cost Drag: {metrics_stock.get('cost_drag'):.4f}%")
    else:
        print("❌ Gross Return <= Net Return (Fail)")

if __name__ == "__main__":
    run_verification()
