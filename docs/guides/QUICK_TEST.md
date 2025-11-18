# Phase 2 빠른 테스트 가이드

## 🚀 즉시 실행 가능한 테스트 명령어

### 1. Optuna 최적화 (소규모, ~10분)
```bash
python pc/cli.py optimize --start 2024-01-01 --end 2024-06-30 --trials 20 --seed 42
```

**예상 결과**:
- 20개 trial 실행
- 최적 파라미터 출력
- `reports/optuna/study_YYYYMMDD_HHMMSS/` 디렉토리 생성
  - `best_params.yaml`: 최적 파라미터
  - `study_report.md`: 리포트
  - `study.db`: Optuna 데이터베이스

---

### 2. 워크포워드 분석 (슬라이딩, ~20분)
```bash
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --train-months 12 --test-months 3 --window-type sliding --trials 30 --seed 42
```

**예상 결과**:
- 여러 윈도우 생성 (학습 12개월 → 검증 3개월)
- 각 윈도우별 최적화 및 검증
- `reports/walk_forward/sliding_YYYYMMDD_HHMMSS/` 디렉토리 생성
  - `walk_forward_results.csv`: 요약 결과
  - `walk_forward_results.json`: 상세 결과

---

### 3. 로버스트니스 테스트 (~15분)

#### Step 1: 파라미터 파일 확인
```bash
# best_params.json이 이미 생성되어 있음
cat best_params.json
```

#### Step 2: 테스트 실행
```bash
python pc/cli.py robustness --start 2024-01-01 --end 2024-12-30 --params best_params.json --iterations 30 --seed 42
```

**예상 결과**:
- 5가지 테스트 실행:
  1. 시드 변동 (30회)
  2. 샘플 드롭 (4개 비율 × 10회)
  3. 부트스트랩 (30회)
  4. 수수료 민감도 (5개 비율)
  5. 슬리피지 민감도 (5개 비율)
- `reports/robustness/YYYYMMDD_HHMMSS/` 디렉토리 생성
  - 각 테스트별 CSV 파일

---

## 📊 결과 확인 방법

### Optuna 최적화 결과
```bash
# 최적 파라미터 확인
cat reports/optuna/study_*/best_params.yaml

# 리포트 확인
cat reports/optuna/study_*/study_report.md
```

### 워크포워드 결과
```bash
# CSV로 확인
cat reports/walk_forward/sliding_*/walk_forward_results.csv

# 또는 Python으로 분석
python -c "
import pandas as pd
df = pd.read_csv('reports/walk_forward/sliding_*/walk_forward_results.csv')
print(df[['window', 'test_return', 'test_sharpe', 'test_mdd']])
print(f'\n평균 검증 수익률: {df[\"test_return\"].mean():.2f}%')
print(f'평균 샤프: {df[\"test_sharpe\"].mean():.2f}')
"
```

### 로버스트니스 결과
```bash
# 시드 변동 결과
python -c "
import pandas as pd
df = pd.read_csv('reports/robustness/*/seed_variation.csv')
print(f'평균 수익률: {df[\"total_return\"].mean():.2f}% (±{df[\"total_return\"].std():.2f}%)')
print(f'평균 샤프: {df[\"sharpe_ratio\"].mean():.2f} (±{df[\"sharpe_ratio\"].std():.2f})')
"

# 수수료 민감도
python -c "
import pandas as pd
df = pd.read_csv('reports/robustness/*/commission_sensitivity.csv')
print(df[['commission_pct', 'total_return', 'sharpe_ratio']])
"
```

---

## ⚡ 초고속 테스트 (디버깅용)

### 최소 설정으로 빠른 검증
```bash
# 1. 최적화 (5 trials, ~2분)
python pc/cli.py optimize --start 2024-01-01 --end 2024-03-31 --trials 5 --seed 42

# 2. 워크포워드 (10 trials, ~5분)
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-06-30 --train-months 6 --test-months 2 --trials 10 --seed 42

# 3. 로버스트니스 (10 iterations, ~5분)
python pc/cli.py robustness --start 2024-01-01 --end 2024-06-30 --params best_params.json --iterations 10 --seed 42
```

---

## 🎯 성공 확인 체크리스트

### Optuna 최적화
- [ ] `best_params.yaml` 파일 생성됨
- [ ] 목적함수 값이 출력됨
- [ ] 파라미터가 합리적 범위 내에 있음

### 워크포워드 분석
- [ ] `walk_forward_results.csv` 생성됨
- [ ] 여러 윈도우 결과가 있음
- [ ] 평균 검증 수익률이 출력됨

### 로버스트니스 테스트
- [ ] 5개 CSV 파일 생성됨
- [ ] 각 테스트 요약 통계 출력됨
- [ ] 95% 신뢰구간 계산됨

---

## 🔧 문제 해결

### "데이터 없음" 오류
```bash
# 데이터 업데이트
python pc/cli.py update --date 2024-12-30
```

### "파라미터 파일 없음" 오류
```bash
# best_params.json 재생성
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
```

### 메모리 부족
```bash
# trials/iterations 수 줄이기
python pc/cli.py optimize --trials 10
python pc/cli.py robustness --iterations 10
```

---

## 📝 다음 단계

모든 테스트 완료 후:
1. 결과 분석 및 최적 파라미터 선택
2. 전체 기간 백테스트 실행
3. Phase 3 (실시간 운영) 준비
