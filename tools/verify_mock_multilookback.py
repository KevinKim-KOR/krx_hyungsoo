# -*- coding: utf-8 -*-
"""
tools/verify_mock_multilookback.py
"""
import sys
import logging
from datetime import date, timedelta
from extensions.tuning.runner import run_backtest_for_tuning

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("Running verify_mock_multilookback...")

    # 1. 5년 기간 설정 (Val 기간 확보)
    start_date = date(2020, 1, 1)
    end_date = date(2024, 12, 31)

    # 2. Mock Calendar
    calendar = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() < 5:
            calendar.append(curr)
        curr += timedelta(days=1)
    
    universe = ["005930", "000660"]
    params = {
        "ma_period": 60, 
        "rsi_period": 14, 
        "stop_loss_pct": 0.05
    }

    results = {}
    lookbacks = [3, 6, 12]

    for lb in lookbacks:
        print(f"\n--- Running for LB={lb} ---")
        try:
            result = run_backtest_for_tuning(
                params=params,
                start_date=start_date,
                end_date=end_date,
                lookback_months=lb,
                trading_calendar=calendar,
                universe_codes=universe,
                use_cache=False
            )
            
            bars_used = result.debug.bars_used if result.debug else 0
            start_date_eval = result.debug.effective_eval_start if result.debug else None
            signal_days = result.debug.signal_days if result.debug else 0
            
            print(f"Result LB={lb}: bars_used={bars_used}, start={start_date_eval}, signal={signal_days}")
            results[lb] = bars_used
        except Exception as e:
            print(f"Error running LB={lb}: {e}")
            import traceback
            traceback.print_exc()

    # 검증
    print("\n--- Summary ---")
    print(f"LB=3: {results.get(3)}")
    print(f"LB=6: {results.get(6)}")
    print(f"LB=12: {results.get(12)}")

    if results[3] != results[6] and results[6] != results[12]:
        print("✅ SUCCESS: bars_used varies by lookback")
    else:
        print("❌ FAILURE: bars_used does not vary enough")
        # LB=12 might equal LB=6 if Val is short, but with 5 years it should differ.
        if results[3] == results[6]:
             print("  -> LB 3 == LB 6 !!")

if __name__ == "__main__":
    main()
