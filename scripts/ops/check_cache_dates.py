#!/usr/bin/env python3
"""캐시 데이터의 날짜 범위를 확인하는 스크립트"""
import pandas as pd
import glob
from pathlib import Path
from datetime import datetime

def check_cache_dates():
    """캐시 파일들의 날짜 범위를 확인"""
    
    # 캐시 디렉토리 확인
    cache_dirs = [
        "data/cache/*.parquet",
        "data/cache/ohlcv/*.parquet",
        "data/cache/kr/*.pkl"
    ]
    
    all_min_date = None
    all_max_date = None
    file_count = 0
    error_count = 0
    
    print("=" * 80)
    print("캐시 데이터 날짜 범위 분석")
    print("=" * 80)
    
    for pattern in cache_dirs:
        files = glob.glob(pattern)
        if not files:
            continue
            
        print(f"\n📁 패턴: {pattern}")
        print(f"   파일 수: {len(files)}개")
        
        pattern_min = None
        pattern_max = None
        
        for file_path in files[:10]:  # 각 패턴에서 처음 10개만 샘플링
            try:
                if file_path.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                elif file_path.endswith('.pkl'):
                    df = pd.read_pickle(file_path)
                else:
                    continue
                
                if df.empty:
                    continue
                
                df.index = pd.to_datetime(df.index)
                min_date = df.index.min()
                max_date = df.index.max()
                
                # 패턴별 범위 업데이트
                if pattern_min is None or min_date < pattern_min:
                    pattern_min = min_date
                if pattern_max is None or max_date > pattern_max:
                    pattern_max = max_date
                
                # 전체 범위 업데이트
                if all_min_date is None or min_date < all_min_date:
                    all_min_date = min_date
                if all_max_date is None or max_date > all_max_date:
                    all_max_date = max_date
                
                file_count += 1
                
            except Exception as e:
                error_count += 1
                continue
        
        if pattern_min and pattern_max:
            print(f"   📅 날짜 범위: {pattern_min.date()} ~ {pattern_max.date()}")
            days = (pattern_max - pattern_min).days
            print(f"   📊 기간: {days}일")
    
    print("\n" + "=" * 80)
    print("전체 요약")
    print("=" * 80)
    
    if all_min_date and all_max_date:
        print(f"✅ 캐시 시작일: {all_min_date.date()}")
        print(f"✅ 캐시 종료일: {all_max_date.date()}")
        total_days = (all_max_date - all_min_date).days
        print(f"✅ 총 기간: {total_days}일 ({total_days / 365.25:.1f}년)")
        print(f"✅ 분석된 파일: {file_count}개")
        
        # 현재 날짜와 비교
        now = pd.Timestamp.now()
        days_old = (now - all_max_date).days
        print(f"⏰ 최신 데이터로부터: {days_old}일 경과")
        
        if error_count > 0:
            print(f"⚠️  오류 파일: {error_count}개")
    else:
        print("❌ 캐시 데이터를 찾을 수 없습니다.")
    
    print("=" * 80)

if __name__ == "__main__":
    check_cache_dates()
