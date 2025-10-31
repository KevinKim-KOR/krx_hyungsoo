#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""데이터 구조 확인"""

import pandas as pd
from pykrx import stock
from datetime import date

print("=" * 60)
print("PyKRX 데이터 구조 확인")
print("=" * 60)

# 1. PyKRX 직접 호출
print("\n1. PyKRX get_etf_ohlcv_by_date")
df = stock.get_etf_ohlcv_by_date("20241001", "20241030", "133690")
print(f"Shape: {df.shape}")
print(f"Columns: {df.columns.tolist()}")
print(f"Index: {df.index.name}")
print(f"\n샘플 데이터:")
print(df.head())

# 2. Parquet 캐시 확인
print("\n" + "=" * 60)
print("2. Parquet 캐시 파일")
print("=" * 60)

cache_file = "data/cache/133690.parquet"
df_cache = pd.read_parquet(cache_file, engine='pyarrow')
print(f"Shape: {df_cache.shape}")
print(f"Columns: {df_cache.columns.tolist()}")
print(f"Index: {df_cache.index.name}")
print(f"\n샘플 데이터:")
print(df_cache.head())
