#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
레짐 감지기 디버깅 스크립트
"""
import sys
from pathlib import Path
from datetime import date
import pandas as pd

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.strategy.market_regime_detector import MarketRegimeDetector
from infra.data.loader import load_price_data

print("=" * 60)
print("레짐 감지기 디버깅")
print("=" * 60)

# 1. KOSPI 데이터 로드
print("\n1. KOSPI 데이터 로드")
tickers = ['069500']  # KODEX 200
start_date = date(2022, 1, 1)
end_date = date.today()

price_data = load_price_data(tickers, start_date, end_date)
print(f"데이터 로드 완료: {price_data.shape}")

# KODEX 200 데이터 추출
if '069500' in price_data.index.get_level_values(0):
    kospi_data = price_data.xs('069500', level=0)
    print(f"KODEX 200 데이터: {len(kospi_data)}일")
    print(f"컬럼: {kospi_data.columns.tolist()}")
    print(f"첫 5행:\n{kospi_data.head()}")
    
    # 컬럼명 정규화
    col_mapping = {}
    for col in kospi_data.columns:
        if col.lower() == 'close':
            col_mapping[col] = 'Close'
    
    if col_mapping:
        kospi_data = kospi_data.rename(columns=col_mapping)
        print(f"\n컬럼명 정규화 후: {kospi_data.columns.tolist()}")
    
    # 2. 레짐 감지기 초기화
    print("\n2. 레짐 감지기 초기화")
    detector = MarketRegimeDetector(
        short_ma_period=50,
        long_ma_period=200,
        bull_threshold=0.02,
        bear_threshold=-0.02,
        trend_strength_period=20
    )
    print("초기화 완료")
    
    # 3. 몇 가지 날짜에서 레짐 감지 테스트
    print("\n3. 레짐 감지 테스트")
    
    test_dates = [
        date(2022, 3, 1),   # 2022년 초반 (하락장 시작?)
        date(2022, 6, 1),   # 2022년 중반 (하락장?)
        date(2023, 1, 1),   # 2023년 초반 (회복?)
        date(2024, 1, 1),   # 2024년 초반 (상승장?)
        date(2024, 8, 5),   # 급락일
    ]
    
    for test_date in test_dates:
        if test_date in kospi_data.index:
            regime, confidence = detector.detect_regime(kospi_data, test_date)
            position_ratio = detector.get_position_ratio(regime, confidence)
            defense_mode = detector.should_enter_defense_mode(regime, confidence)
            
            print(f"\n날짜: {test_date}")
            print(f"  레짐: {regime}")
            print(f"  신뢰도: {confidence:.2f}")
            print(f"  포지션 비율: {position_ratio:.2f}")
            print(f"  방어 모드: {defense_mode}")
            
            # 이동평균 확인
            short_ma, long_ma = detector.calculate_moving_averages(kospi_data, test_date)
            if short_ma and long_ma:
                ma_diff_pct = (short_ma / long_ma - 1.0) * 100
                print(f"  단기MA: {short_ma:.2f}")
                print(f"  장기MA: {long_ma:.2f}")
                print(f"  MA 차이: {ma_diff_pct:.2f}%")
    
    # 4. 전체 기간 레짐 통계
    print("\n4. 전체 기간 레짐 통계")
    detector.reset_stats()
    
    for idx, row in kospi_data.iterrows():
        current_date = idx.date() if hasattr(idx, 'date') else idx
        regime, confidence = detector.detect_regime(kospi_data, current_date)
    
    stats = detector.get_stats()
    print(f"통계: {stats}")
    print(f"\n상승장: {stats['bull_days']}일 ({stats['bull_pct']:.1f}%)")
    print(f"하락장: {stats['bear_days']}일 ({stats['bear_pct']:.1f}%)")
    print(f"중립장: {stats['neutral_days']}일 ({stats['neutral_pct']:.1f}%)")
    print(f"레짐 변경: {stats['regime_changes']}회")
    
else:
    print("KODEX 200 데이터 없음!")

print("\n" + "=" * 60)
print("디버깅 완료")
print("=" * 60)
