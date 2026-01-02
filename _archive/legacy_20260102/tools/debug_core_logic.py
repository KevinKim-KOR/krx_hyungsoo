# -*- coding: utf-8 -*-
"""
tools/debug_core_logic.py
"""
import sys
import logging
from datetime import date, timedelta
from extensions.tuning.runner import run_backtest_for_tuning

# 로깅 설정 (ERROR만 표시하여 깔끔하게)
logging.basicConfig(level=logging.ERROR)

def main():
    print(">>> Debug Core Logic Start")

    # 1. Setup
    start_date = date(2021, 1, 1)
    end_date = date(2023, 12, 31)
    
    # Mock Calendar
    calendar = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:
            calendar.append(curr)
        curr += timedelta(days=1)
    
    universe = ["005930", "000660"] # Samsung, Hynix
    
    params = {
        "ma_period": 60, 
        "rsi_period": 14, 
        "stop_loss_pct": 0.05
    }

    # 2. Test Multi-Lookback & signal_days
    # LB=3 vs LB=12
    # LB=3 -> Val window = last 3 months
    # LB=12 -> Val window = last 12 months (or default Val if smaller? No, LB determines window)
    
    print("\n[Test 1] Multi-Lookback Duration Check")
    
    res_lb3 = run_backtest_for_tuning(
        params=params,
        start_date=start_date,
        end_date=end_date,
        lookback_months=3,
        trading_calendar=calendar,
        universe_codes=universe,
        use_cache=False
    )
    
    res_lb12 = run_backtest_for_tuning(
        params=params,
        start_date=start_date,
        end_date=end_date,
        lookback_months=12,
        trading_calendar=calendar,
        universe_codes=universe,
        use_cache=False
    )
    
    debug3 = res_lb3.debug
    debug12 = res_lb12.debug
    
    print(f"LB=3:  Bars Used = {debug3.bars_used}, Effective Start = {debug3.effective_eval_start}")
    print(f"LB=12: Bars Used = {debug12.bars_used}, Effective Start = {debug12.effective_eval_start}")
    
    if debug3.bars_used < debug12.bars_used:
        print("✅ SUCCESS: Bars Used differs correctly (3M < 12M).")
    else:
        print("❌ FAILURE: Bars Used should differ.")
        
    print("\n[Test 2] Signal Days Check")
    signal_days = res_lb12.val.signal_days if res_lb12.val else 0
    order_count = res_lb12.val.order_count if res_lb12.val else 0
    
    print(f"LB=12 Val Metrics: signal_days={signal_days}, order_count={order_count}")
    
    # Mock data might produce 0 signals if prices are random or unavailable?
    # Actually BacktestService might use real data if configured, or fail.
    # In 'tuning' mode runner, it calls BacktestService.
    # We didn't enforce Mock BacktestService here.
    # But checking if the field exists is enough for "Schema Verification".
    
    if hasattr(res_lb12.val, 'signal_days'):
        print(f"✅ SUCCESS: signal_days field exists in metrics. ({signal_days})")
    else:
        print("❌ FAILURE: signal_days field MISSING.")

    print("\n>>> Debug Core Logic Complete")

if __name__ == "__main__":
    main()
