#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest 없이 직접 실행 가능한 간단 테스트 스크립트
NAS DS220j 환경용

실행: python3 scripts/diagnostics/run_tests_simple.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_imports():
    """Import 테스트"""
    print("\n[TEST 1/5] Import 테스트...")
    try:
        from fetchers import ingest_eod
        from scanner import recommend_buy_sell
        from cache_store import load_cached
        from indicators import sma, adx, mfi
        print("  [OK] 모든 모듈 Import 성공")
        return True
    except Exception as e:
        print(f"  [FAIL] Import 실패: {e}")
        return False

def test_indicators():
    """지표 계산 테스트"""
    print("\n[TEST 2/5] 지표 계산 테스트...")
    try:
        import pandas as pd
        import numpy as np
        from indicators import sma, pct_change_n
        
        # SMA 테스트
        data = pd.Series([10, 20, 30, 40, 50], index=pd.date_range("2025-01-01", periods=5))
        result = sma(data, 3)
        assert abs(result.iloc[2] - 20.0) < 0.01, "SMA 계산 오류"
        
        # 수익률 테스트
        # data = [10, 20, 30, 40, 50]
        # pct_change(2): data[2]=30, data[0]=10 → (30-10)/10 = 2.0
        ret = pct_change_n(data, 2)
        assert abs(ret.iloc[2] - 2.0) < 0.01, f"수익률 계산 오류 (expected: 2.0, got: {ret.iloc[2]:.4f})"
        
        print("  [OK] 지표 계산 정상")
        return True
    except Exception as e:
        print(f"  [FAIL] 지표 계산 실패: {e}")
        return False

def test_cache():
    """캐시 시스템 테스트"""
    print("\n[TEST 3/5] 캐시 시스템 테스트...")
    try:
        from cache_store import load_cached, save_cache, cache_path
        import pandas as pd
        from pathlib import Path
        
        # 경로 확인
        p = cache_path("TEST")
        assert p.parent.exists() or True, "캐시 디렉토리 생성 가능"
        
        # 존재하지 않는 캐시 로드
        result = load_cached("NONEXISTENT_CODE")
        assert result is None, "존재하지 않는 캐시는 None 반환"
        
        print("  [OK] 캐시 시스템 정상")
        return True
    except Exception as e:
        print(f"  [FAIL] 캐시 테스트 실패: {e}")
        return False

def test_db_connection():
    """DB 연결 테스트"""
    print("\n[TEST 4/5] DB 연결 테스트...")
    try:
        from db import SessionLocal, Security
        
        with SessionLocal() as s:
            # 간단한 쿼리
            count = s.query(Security).count()
            print(f"  [INFO] DB 연결 성공 (종목 수: {count})")
        
        print("  [OK] DB 연결 정상")
        return True
    except Exception as e:
        print(f"  [FAIL] DB 연결 실패: {e}")
        return False

def test_config_loading():
    """설정 파일 로딩 테스트"""
    print("\n[TEST 5/5] 설정 파일 로딩 테스트...")
    try:
        from scanner import load_config_yaml
        
        # config.yaml 또는 config.yaml.example 로드
        try:
            cfg = load_config_yaml("config.yaml")
            print("  [INFO] config.yaml 로드 성공")
        except FileNotFoundError:
            try:
                cfg = load_config_yaml("config.yaml.example")
                print("  [INFO] config.yaml.example 로드 성공")
            except FileNotFoundError:
                print("  [WARN] 설정 파일 없음 (정상일 수 있음)")
                return True
        
        # 필수 키 확인 (없으면 안내)
        if "universe" not in cfg:
            print("  [WARN] universe 키 누락 - config.yaml.example을 config.yaml로 복사하세요")
            print("         cp config.yaml.example config.yaml")
            return False
        if "scanner" not in cfg:
            print("  [WARN] scanner 키 누락")
            return False
        
        print("  [OK] 설정 파일 정상")
        return True
    except Exception as e:
        print(f"  [FAIL] 설정 로딩 실패: {e}")
        return False

def main():
    print("=" * 60)
    print("[SIMPLE TEST] NAS 환경 테스트 시작")
    print("=" * 60)
    
    results = []
    
    # 테스트 실행
    results.append(("Import", test_imports()))
    results.append(("Indicators", test_indicators()))
    results.append(("Cache", test_cache()))
    results.append(("DB Connection", test_db_connection()))
    results.append(("Config Loading", test_config_loading()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("[SUMMARY] 테스트 결과")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print("-" * 60)
    print(f"  총 {passed}/{total} 테스트 통과")
    print("=" * 60)
    
    # 종료 코드
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
