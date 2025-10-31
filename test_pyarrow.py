#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pyarrow 설치 확인 및 테스트"""

print("=" * 60)
print("1. pyarrow 설치 확인")
print("=" * 60)

try:
    import pyarrow
    print(f"✅ pyarrow 설치됨: {pyarrow.__version__}")
except ImportError as e:
    print(f"❌ pyarrow 미설치: {e}")
    print("\n해결 방법:")
    print("  pip install pyarrow")
    exit(1)

print("\n" + "=" * 60)
print("2. pandas parquet 지원 확인")
print("=" * 60)

try:
    import pandas as pd
    print(f"✅ pandas 버전: {pd.__version__}")
    
    # 테스트 데이터 생성
    df = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=10),
        'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
    })
    
    # Parquet 쓰기 테스트
    test_file = 'data/cache/test_pyarrow.parquet'
    df.to_parquet(test_file, engine='pyarrow')
    print(f"✅ Parquet 쓰기 성공: {test_file}")
    
    # Parquet 읽기 테스트
    df_read = pd.read_parquet(test_file, engine='pyarrow')
    print(f"✅ Parquet 읽기 성공: {len(df_read)} rows")
    
    # 파일 삭제
    import os
    os.remove(test_file)
    print(f"✅ 테스트 파일 삭제")
    
except Exception as e:
    print(f"❌ pandas parquet 지원 실패: {e}")
    print("\n해결 방법:")
    print("  pip uninstall pyarrow -y")
    print("  pip install pyarrow")
    exit(1)

print("\n" + "=" * 60)
print("3. 환경 정보")
print("=" * 60)

import sys
print(f"Python: {sys.version}")
print(f"실행 경로: {sys.executable}")

print("\n" + "=" * 60)
print("✅ 모든 테스트 통과!")
print("=" * 60)
