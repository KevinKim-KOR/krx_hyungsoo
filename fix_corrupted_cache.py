#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
손상된 캐시 파일 자동 정리 스크립트
"""
import pandas as pd
from pathlib import Path

print("=" * 60)
print("손상된 캐시 파일 검사 및 정리")
print("=" * 60)

cache_dir = Path('data/cache')
total = 0
corrupted = []
valid = 0

print("\n캐시 파일 검사 중...")

for pf in cache_dir.glob('*.parquet'):
    total += 1
    try:
        df = pd.read_parquet(pf, engine='pyarrow')
        if df.empty:
            print(f"  ⚠️  빈 파일: {pf.name}")
            corrupted.append(pf)
        else:
            valid += 1
    except Exception as e:
        print(f"  ❌ 손상: {pf.name} - {str(e)[:50]}")
        corrupted.append(pf)

print("\n" + "=" * 60)
print("검사 결과")
print("=" * 60)
print(f"총 파일 수: {total}")
print(f"정상 파일: {valid} ({valid/total*100:.1f}%)")
print(f"손상 파일: {len(corrupted)} ({len(corrupted)/total*100:.1f}%)")

if len(corrupted) > 0:
    print("\n손상된 파일 삭제 여부를 선택하세요:")
    print(f"  - 삭제할 파일: {len(corrupted)}개")
    print(f"  - 손상률: {len(corrupted)/total*100:.1f}%")
    
    response = input("\n삭제하시겠습니까? (y/N): ").strip().lower()
    
    if response == 'y':
        print("\n삭제 중...")
        deleted = 0
        for pf in corrupted:
            try:
                pf.unlink()
                deleted += 1
                print(f"  ✅ 삭제: {pf.name}")
            except Exception as e:
                print(f"  ❌ 삭제 실패: {pf.name} - {e}")
        
        print(f"\n총 {deleted}개 파일 삭제 완료")
        print("\n다음 명령어로 재다운로드하세요:")
        print("  python pc/cli.py update --date 2024-12-30")
    else:
        print("\n취소되었습니다.")
else:
    print("\n✅ 모든 캐시 파일이 정상입니다!")

print("\n" + "=" * 60)
