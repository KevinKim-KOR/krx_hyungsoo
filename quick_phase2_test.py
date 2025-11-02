#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 빠른 검증 스크립트
10개 종목, 3 trials, 6개월 데이터
"""
from datetime import date
from extensions.optuna.objective import BacktestObjective
import optuna

print("=" * 60)
print("Phase 2 빠른 검증 테스트")
print("=" * 60)

# 1. Objective 생성
print("\n1. Objective 생성 중...")
obj = BacktestObjective(
    start_date=date(2023, 7, 1),
    end_date=date(2023, 12, 31),
    seed=42
)

print(f"   전체 유니버스: {len(obj.universe)}개 종목")

# 2. 유니버스 축소 (10개만)
print("\n2. 유니버스 축소 (10개)...")
obj.universe = obj.universe[:10]
print(f"   테스트 유니버스: {obj.universe}")

# 3. 데이터 재로드
print("\n3. 데이터 로드 중...")
from infra.data.loader import load_price_data
obj.price_data = load_price_data(obj.universe, obj.start_date, obj.end_date)
print(f"   데이터 shape: {obj.price_data.shape}")
print(f"   Index: {obj.price_data.index.names}")

# 4. 최적화 실행
print("\n4. Optuna 최적화 실행 (3 trials)...")
study = optuna.create_study(direction='maximize')

try:
    study.optimize(obj, n_trials=3, show_progress_bar=True)
    
    print("\n" + "=" * 60)
    print("✅ 최적화 성공!")
    print("=" * 60)
    print(f"최적 목적함수 값: {study.best_value:.2f}")
    print(f"최적 파라미터:")
    for key, value in study.best_params.items():
        print(f"  - {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Phase 2 기능 검증 완료!")
    print("=" * 60)
    
except Exception as e:
    print("\n" + "=" * 60)
    print("❌ 최적화 실패")
    print("=" * 60)
    print(f"오류: {e}")
    import traceback
    traceback.print_exc()
