#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터 로딩 테스트 스크립트
"""
from datetime import date
from pathlib import Path
import pandas as pd
from infra.data.loader import load_price_data
from core.data.filtering import get_filtered_universe

print("=" * 60)
print("데이터 로딩 테스트")
print("=" * 60)

# 1. 유니버스 로드
print("\n1. 유니버스 로드...")
universe = get_filtered_universe()
print(f"   총 {len(universe)}개 종목")
print(f"   샘플: {universe[:5]}")

# 2. 소규모 데이터 로드 (10개 종목만)
print("\n2. 소규모 데이터 로드 (10개 종목)...")
small_universe = universe[:10]
start_date = date(2024, 1, 1)
end_date = date(2024, 1, 31)

try:
    price_data = load_price_data(small_universe, start_date, end_date)
    
    print(f"   로드 성공!")
    print(f"   Shape: {price_data.shape}")
    print(f"   Index: {price_data.index.names}")
    print(f"   Columns: {price_data.columns.tolist()}")
    print(f"\n   샘플 데이터:")
    print(price_data.head())
    
    # 3. MultiIndex 확인
    print("\n3. MultiIndex 검증...")
    if isinstance(price_data.index, pd.MultiIndex):
        print(f"   ✅ MultiIndex 확인")
        print(f"   Levels: {price_data.index.names}")
        
        # date 레벨 확인
        if 'date' in price_data.index.names:
            print(f"   ✅ 'date' 레벨 존재")
            dates = price_data.index.get_level_values('date').unique()
            print(f"   날짜 수: {len(dates)}")
        else:
            print(f"   ❌ 'date' 레벨 없음")
    else:
        print(f"   ❌ MultiIndex 아님: {type(price_data.index)}")

except Exception as e:
    print(f"   ❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()

# 4. 캐시 파일 상태 확인
print("\n4. 캐시 파일 상태 확인...")
cache_dir = Path('data/cache')
parquet_files = list(cache_dir.glob('*.parquet'))
print(f"   총 {len(parquet_files)}개 파일")

# 샘플 파일 검증
print("\n5. 샘플 파일 검증 (처음 3개)...")
import pandas as pd

for i, pf in enumerate(parquet_files[:3]):
    try:
        df = pd.read_parquet(pf)
        print(f"   ✅ {pf.name}: {df.shape}, Index: {df.index.name}")
    except Exception as e:
        print(f"   ❌ {pf.name}: {e}")

print("\n" + "=" * 60)
print("테스트 완료")
print("=" * 60)
