#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""데이터 로딩 테스트"""

from datetime import date, timedelta
from pathlib import Path
import sys

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infra.data.loader import load_price_data

# 테스트 파라미터
universe = ['133690', '305720']
start_date = date(2024, 10, 1)
end_date = date(2024, 12, 31)

print("=" * 60)
print("1. 백테스트 기간만 로드")
print("=" * 60)
price_data = load_price_data(universe, start_date, end_date)
print(f"Shape: {price_data.shape}")
print(f"Index levels: {price_data.index.names}")
print(f"\n133690 데이터:")
if '133690' in price_data.index.get_level_values('code'):
    data_133690 = price_data.loc['133690']
    print(f"  행 수: {len(data_133690)}")
    print(f"  날짜 범위: {data_133690.index.min()} ~ {data_133690.index.max()}")

print("\n" + "=" * 60)
print("2. Lookback 포함하여 로드")
print("=" * 60)
lookback_days = 120
data_start_date = start_date - timedelta(days=lookback_days)
price_data2 = load_price_data(universe, data_start_date, end_date)
print(f"Shape: {price_data2.shape}")
print(f"\n133690 데이터:")
if '133690' in price_data2.index.get_level_values('code'):
    data_133690_2 = price_data2.loc['133690']
    print(f"  행 수: {len(data_133690_2)}")
    print(f"  날짜 범위: {data_133690_2.index.min()} ~ {data_133690_2.index.max()}")

print("\n" + "=" * 60)
print("3. 2023년부터 로드")
print("=" * 60)
data_start_date3 = date(2023, 1, 1)
price_data3 = load_price_data(universe, data_start_date3, end_date)
print(f"Shape: {price_data3.shape}")
print(f"\n133690 데이터:")
if '133690' in price_data3.index.get_level_values('code'):
    data_133690_3 = price_data3.loc['133690']
    print(f"  행 수: {len(data_133690_3)}")
    print(f"  날짜 범위: {data_133690_3.index.min()} ~ {data_133690_3.index.max()}")
