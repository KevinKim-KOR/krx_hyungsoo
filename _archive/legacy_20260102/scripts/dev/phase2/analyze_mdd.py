#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MDD 발생 시점 분석
"""
import sys
from pathlib import Path
import pandas as pd
import json

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 결과 로드
output_dir = PROJECT_ROOT / 'data' / 'output' / 'phase2'

# 방어 없음 결과
crash_comparison_file = output_dir / 'crash_detection_comparison.json'
with open(crash_comparison_file, 'r') as f:
    comparison_data = json.load(f)

# daily_values는 백테스트를 다시 실행해야 함
# 간단히 MDD 시점만 추정
print("MDD 분석을 위해 백테스트 재실행 필요")
print("대신 급락 감지 시점 분석:")
print("  2024-08-05: 단일 급락 -11.40%")
print("  2025-04-07: 단일 급락 -6.14%")
print("\nMDD: -23.51%")
print("이 MDD가 언제 발생했는지 확인 필요")

sys.exit(0)

# Daily values 분석
daily_values = no_defense_results['results']['daily_values']

# DataFrame 생성
df = pd.DataFrame(daily_values, columns=['date', 'value'])
df['date'] = pd.to_datetime(df['date'])
df = df.set_index('date')

# 누적 최고값 계산
df['peak'] = df['value'].cummax()

# Drawdown 계산
df['drawdown'] = (df['value'] / df['peak'] - 1) * 100

# MDD 찾기
mdd_value = df['drawdown'].min()
mdd_date = df['drawdown'].idxmin()

print("=" * 60)
print("MDD 분석")
print("=" * 60)
print(f"MDD: {mdd_value:.2f}%")
print(f"MDD 발생일: {mdd_date.date()}")
print(f"Peak 가치: {df.loc[mdd_date, 'peak']:,.0f}")
print(f"MDD 시점 가치: {df.loc[mdd_date, 'value']:,.0f}")

# MDD 전후 10일 분석
mdd_idx = df.index.get_loc(mdd_date)
start_idx = max(0, mdd_idx - 10)
end_idx = min(len(df), mdd_idx + 10)

print("\nMDD 전후 10일:")
print(df.iloc[start_idx:end_idx][['value', 'peak', 'drawdown']])

# KOSPI 데이터 로드
print("\n" + "=" * 60)
print("KOSPI (KODEX 200) 동기화 분석")
print("=" * 60)

from infra.data.loader import load_price_data
from datetime import date

kospi_data = load_price_data(['069500'], date(2022, 1, 1), date.today())
kospi_df = kospi_data.xs('069500', level=0)

# MDD 전후 KOSPI 변화
mdd_period = kospi_df.loc[mdd_date - pd.Timedelta(days=10):mdd_date + pd.Timedelta(days=10)]

if len(mdd_period) > 0:
    print(f"\nMDD 전후 KOSPI 변화:")
    mdd_period['daily_return'] = mdd_period['close'].pct_change() * 100
    print(mdd_period[['close', 'low', 'daily_return']])
    
    # MDD 당일 KOSPI 변화
    if mdd_date in mdd_period.index:
        mdd_day_data = mdd_period.loc[mdd_date]
        print(f"\nMDD 당일 KOSPI:")
        print(f"  Close: {mdd_day_data['close']:.2f}")
        print(f"  Low: {mdd_day_data['low']:.2f}")
        print(f"  Daily Return: {mdd_day_data['daily_return']:.2f}%")
        
        # 전일 대비 Low 하락률
        if mdd_idx > 0:
            prev_date = df.index[mdd_idx - 1]
            if prev_date in mdd_period.index:
                prev_close = mdd_period.loc[prev_date, 'close']
                low_drop = (mdd_day_data['low'] / prev_close - 1) * 100
                print(f"  전일 Close 대비 Low 하락: {low_drop:.2f}%")

# 급락 감지 시점과 비교
print("\n" + "=" * 60)
print("급락 감지 vs MDD 발생")
print("=" * 60)
print("급락 감지: 2024-08-05, 2025-04-07")
print(f"MDD 발생: {mdd_date.date()}")

if mdd_date.date() == date(2024, 8, 5):
    print("✅ MDD 발생일에 급락 감지됨!")
elif mdd_date.date() == date(2025, 4, 7):
    print("✅ MDD 발생일에 급락 감지됨!")
else:
    print("❌ MDD 발생일에 급락 감지 안됨!")
    print(f"   MDD는 {mdd_date.date()}에 발생했지만 급락 감지는 다른 날짜")
