#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OHLCV 캐시 확인"""

import pandas as pd
from pathlib import Path

ohlcv_dir = Path("data/cache/ohlcv")
cache_dir = Path("data/cache")

print("=" * 60)
print("1. data/cache/ohlcv/ 확인")
print("=" * 60)
ohlcv_file = ohlcv_dir / "133690.parquet"
if ohlcv_file.exists():
    df = pd.read_parquet(ohlcv_file, engine='pyarrow')
    print(f"Shape: {df.shape}")
    print(f"날짜 범위: {df.index.min()} ~ {df.index.max()}")
else:
    print("파일 없음")

print("\n" + "=" * 60)
print("2. data/cache/ 확인")
print("=" * 60)
cache_file = cache_dir / "133690.parquet"
if cache_file.exists():
    df = pd.read_parquet(cache_file, engine='pyarrow')
    print(f"Shape: {df.shape}")
    print(f"날짜 범위: {df.index.min()} ~ {df.index.max()}")
else:
    print("파일 없음")
