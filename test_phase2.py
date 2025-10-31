#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 테스트 스크립트
Optuna 최적화, 워크포워드 분석, 로버스트니스 테스트
"""
from datetime import date, datetime
from pathlib import Path
import json

# 1. Optuna 최적화 테스트
print("=" * 60)
print("1. Optuna 파라미터 최적화 테스트")
print("=" * 60)
print("""
# 소규모 최적화 (빠른 테스트)
python pc/cli.py optimize --start 2024-01-01 --end 2024-06-30 --trials 20 --seed 42

# 전체 최적화
python pc/cli.py optimize --start 2024-01-01 --end 2024-12-30 --trials 100 --seed 42 --output reports/optuna/test1
""")

# 2. 워크포워드 분석 테스트
print("\n" + "=" * 60)
print("2. 워크포워드 분석 테스트")
print("=" * 60)
print("""
# 슬라이딩 윈도우 (12개월 학습, 3개월 검증)
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --train-months 12 --test-months 3 --window-type sliding --trials 30 --output reports/walk_forward/sliding

# 확장 윈도우
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --train-months 12 --test-months 3 --window-type expanding --trials 30 --output reports/walk_forward/expanding
""")

# 3. 로버스트니스 테스트
print("\n" + "=" * 60)
print("3. 로버스트니스 테스트")
print("=" * 60)
print("""
# 먼저 최적 파라미터를 JSON으로 저장
cat > best_params.json << EOF
{
  "ma_period": 60,
  "rsi_period": 14,
  "rsi_overbought": 70,
  "maps_buy_threshold": 0.0,
  "maps_sell_threshold": -5.0,
  "rebalance_frequency": "monthly",
  "max_positions": 10,
  "min_confidence": 0.1
}
EOF

# 로버스트니스 테스트 실행
python pc/cli.py robustness --start 2024-01-01 --end 2024-12-30 --params best_params.json --iterations 30 --output reports/robustness/test1
""")

# 4. 기본 파라미터 JSON 생성
print("\n" + "=" * 60)
print("4. 기본 파라미터 파일 생성")
print("=" * 60)

best_params = {
    "ma_period": 60,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "maps_buy_threshold": 0.0,
    "maps_sell_threshold": -5.0,
    "rebalance_frequency": "monthly",
    "max_positions": 10,
    "min_confidence": 0.1
}

params_file = Path("best_params.json")
with open(params_file, 'w', encoding='utf-8') as f:
    json.dump(best_params, f, indent=2, ensure_ascii=False)

print(f"✅ 생성 완료: {params_file}")
print(f"내용:\n{json.dumps(best_params, indent=2, ensure_ascii=False)}")

print("\n" + "=" * 60)
print("Phase 2 테스트 준비 완료!")
print("=" * 60)
print("\n위 명령어들을 순서대로 실행하세요.")
print("각 단계는 독립적으로 실행 가능합니다.")
