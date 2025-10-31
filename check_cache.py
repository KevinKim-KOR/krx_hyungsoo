#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""캐시 데이터 확인"""

import pandas as pd

cache_file = "data/cache/133690.parquet"
df = pd.read_parquet(cache_file, engine='pyarrow')

print(f"Shape: {df.shape}")
print(f"Index: {df.index.name}")
print(f"Columns: {df.columns.tolist()}")
print(f"\n날짜 범위:")
print(f"  시작: {df.index.min()}")
print(f"  종료: {df.index.max()}")
print(f"\n샘플 데이터:")
print(df.head())
print(df.tail())
