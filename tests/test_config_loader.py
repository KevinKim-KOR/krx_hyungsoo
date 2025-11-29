#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_config_loader.py
Config 로더 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from extensions.automation.config_loader import get_config_loader


def test_config_loader():
    """Config 로더 테스트"""
    print("=" * 60)
    print("Config 로더 테스트")
    print("=" * 60)
    
    # Config 로더 초기화
    config = get_config_loader()
    
    # 1. intraday_alert 섹션 전체 가져오기
    print("\n1. intraday_alert 섹션 전체:")
    intraday_config = config.get_section("intraday_alert")
    print(f"  섹션 키: {list(intraday_config.keys())}")
    
    # 2. thresholds 가져오기
    print("\n2. thresholds:")
    thresholds = config.get("intraday_alert.thresholds")
    for key, value in thresholds.items():
        print(f"  {key}: {value}%")
    
    # 3. min_trade_value 가져오기
    print("\n3. min_trade_value:")
    min_trade_value = config.get("intraday_alert.min_trade_value")
    print(f"  {min_trade_value:,}원 ({min_trade_value/1e8:.0f}억원)")
    
    # 4. exclude_keywords 가져오기
    print("\n4. exclude_keywords:")
    exclude_keywords = config.get("intraday_alert.exclude_keywords")
    print(f"  총 {len(exclude_keywords)}개:")
    for keyword in exclude_keywords:
        print(f"    - {keyword}")
    
    # 5. 기본값 테스트
    print("\n5. 기본값 테스트:")
    non_existent = config.get("non.existent.key", "DEFAULT_VALUE")
    print(f"  non.existent.key: {non_existent}")
    
    print("\n" + "=" * 60)
    print("✅ Config 로더 테스트 성공!")
    print("=" * 60)


if __name__ == "__main__":
    test_config_loader()
