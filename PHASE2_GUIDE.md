# Phase 2: 최적화 및 검증 가이드

## 📋 개요

Phase 2에서는 MAPS 전략의 파라미터 최적화 및 검증을 위한 3가지 핵심 도구를 구현했습니다:

1. **Optuna 파라미터 최적화**: 최적 파라미터 탐색
2. **워크포워드 분석**: 시간에 따른 전략 안정성 검증
3. **로버스트니스 테스트**: 다양한 조건에서의 전략 강건성 평가

---

## 🎯 1. Optuna 파라미터 최적화

### 목적
MAPS 전략의 최적 파라미터를 자동으로 탐색합니다.

### 최적화 파라미터

| 파라미터 | 범위 | 설명 |
|---------|------|------|
| `ma_period` | 20~120 (step 10) | 이동평균 기간 |
| `rsi_period` | 7~21 (step 2) | RSI 기간 |
| `rsi_overbought` | 65~80 (step 5) | RSI 과매수 임계값 |
| `maps_buy_threshold` | -2.0~5.0 (step 1.0) | MAPS 매수 임계값 |
| `maps_sell_threshold` | -10.0~-2.0 (step 1.0) | MAPS 매도 임계값 |
| `rebalance_frequency` | weekly/biweekly/monthly | 리밸런싱 주기 |
| `max_positions` | 5~20 (step 5) | 최대 보유 종목 수 |
| `min_confidence` | 0.0~0.3 (step 0.05) | 최소 신뢰도 |

### 목적 함수
```
목적함수 = 연율화 수익률 - λ × MDD
(기본 λ = 2.0)
```

### 사용법

#### 빠른 테스트 (20 trials, ~10분)
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --end 2024-06-30 \
  --trials 20 \
  --seed 42
```

#### 전체 최적화 (100 trials, ~1시간)
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --end 2024-12-30 \
  --trials 100 \
  --seed 42 \
  --output reports/optuna/full
```

### 출력
- `best_params.yaml`: 최적 파라미터
- `study_report.md`: 최적화 리포트
- `study.db`: Optuna study 데이터베이스
- `optimization_history.html`: 최적화 히스토리 (--plot 옵션)
- `param_importances.html`: 파라미터 중요도 (--plot 옵션)

---

## 🔄 2. 워크포워드 분석

### 목적
시간에 따른 전략의 안정성을 검증합니다. 과거 데이터로 최적화한 파라미터가 미래에도 유효한지 확인합니다.

### 윈도우 타입

#### 슬라이딩 윈도우 (Sliding Window)
```
[학습 12개월] → [검증 3개월]
         [학습 12개월] → [검증 3개월]
                  [학습 12개월] → [검증 3개월]
```
- 고정된 학습 기간 사용
- 최근 데이터에 더 민감

#### 확장 윈도우 (Expanding Window)
```
[학습 12개월] → [검증 3개월]
[학습 15개월] → [검증 3개월]
[학습 18개월] → [검증 3개월]
```
- 누적 학습 (모든 과거 데이터 사용)
- 장기 트렌드 포착

### 사용법

#### 슬라이딩 윈도우
```bash
python pc/cli.py walk-forward \
  --start 2023-01-01 \
  --end 2024-12-30 \
  --train-months 12 \
  --test-months 3 \
  --window-type sliding \
  --trials 30 \
  --output reports/walk_forward/sliding
```

#### 확장 윈도우
```bash
python pc/cli.py walk-forward \
  --start 2023-01-01 \
  --end 2024-12-30 \
  --train-months 12 \
  --test-months 3 \
  --window-type expanding \
  --trials 30 \
  --output reports/walk_forward/expanding
```

### 출력
- `walk_forward_results.csv`: 윈도우별 결과 요약
- `walk_forward_results.json`: 상세 결과 (파라미터 포함)

### 결과 해석
- **평균 검증 수익률**: 미래 성과 예측
- **평균 검증 샤프**: 위험 조정 수익률
- **승률**: 양의 수익률 비율
- **학습 vs 검증 차이**: 과적합 정도

---

## 🔬 3. 로버스트니스 테스트

### 목적
다양한 조건에서 전략의 강건성을 평가합니다.

### 테스트 항목

#### 1. 시드 변동 테스트
- 랜덤 시드를 변경하여 30회 반복
- 결과의 안정성 확인

#### 2. 샘플 드롭 테스트
- 데이터 누락 시뮬레이션 (5%, 10%, 15%, 20%)
- 데이터 품질 저하 시 성능 확인

#### 3. 부트스트랩 테스트
- 복원 추출로 30회 반복
- 95% 신뢰구간 계산

#### 4. 수수료 민감도
- 수수료율 변화에 따른 성과 변화
- 0%, 0.005%, 0.015%, 0.03%, 0.05%

#### 5. 슬리피지 민감도
- 슬리피지율 변화에 따른 성과 변화
- 0%, 0.05%, 0.1%, 0.2%, 0.5%

### 사용법

#### 1. 파라미터 파일 준비
```json
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
```

#### 2. 테스트 실행
```bash
python pc/cli.py robustness \
  --start 2024-01-01 \
  --end 2024-12-30 \
  --params best_params.json \
  --iterations 30 \
  --output reports/robustness/test1
```

### 출력
- `seed_variation.csv`: 시드 변동 결과
- `sample_drop.csv`: 샘플 드롭 결과
- `bootstrap.csv`: 부트스트랩 결과
- `commission_sensitivity.csv`: 수수료 민감도
- `slippage_sensitivity.csv`: 슬리피지 민감도

### 결과 해석
- **시드 변동**: 표준편차가 작을수록 안정적
- **샘플 드롭**: 누락률 증가에도 성과 유지 시 강건
- **부트스트랩**: 95% 신뢰구간이 좁을수록 신뢰도 높음
- **수수료/슬리피지**: 민감도가 낮을수록 실전 적용 유리

---

## 📊 권장 워크플로우

### Step 1: 파라미터 최적화
```bash
# 소규모 테스트
python pc/cli.py optimize --start 2024-01-01 --end 2024-06-30 --trials 20

# 결과 확인 후 전체 최적화
python pc/cli.py optimize --start 2024-01-01 --end 2024-12-30 --trials 100 --output reports/optuna/full
```

### Step 2: 워크포워드 검증
```bash
# 슬라이딩 윈도우
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --window-type sliding --trials 30

# 확장 윈도우
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --window-type expanding --trials 30
```

### Step 3: 로버스트니스 확인
```bash
# 최적 파라미터로 로버스트니스 테스트
python pc/cli.py robustness --start 2024-01-01 --end 2024-12-30 --params reports/optuna/full/best_params.yaml --iterations 30
```

### Step 4: 최종 백테스트
```bash
# 최적 파라미터로 전체 기간 백테스트
python pc/cli.py backtest --start 2023-01-01 --end 2024-12-30 --max-positions 10
```

---

## 🎯 성공 기준

### Optuna 최적화
- ✅ 목적함수 값 > 10.0 (연율화 수익률 - 2×MDD)
- ✅ 샤프 비율 > 1.0
- ✅ MDD < -15%

### 워크포워드 분석
- ✅ 평균 검증 수익률 > 5%
- ✅ 승률 > 50%
- ✅ 학습-검증 차이 < 10%p

### 로버스트니스 테스트
- ✅ 시드 변동 표준편차 < 5%
- ✅ 20% 샘플 드롭 시 수익률 > 0%
- ✅ 부트스트랩 95% 신뢰구간 양수
- ✅ 0.03% 수수료 시 수익률 > 0%

---

## 🔧 트러블슈팅

### 문제: 최적화가 너무 느림
**해결**: trials 수를 줄이거나 기간을 단축
```bash
python pc/cli.py optimize --start 2024-01-01 --end 2024-06-30 --trials 20
```

### 문제: 워크포워드 윈도우가 생성되지 않음
**해결**: 학습+검증 기간이 전체 기간보다 짧은지 확인
```bash
# 전체 2년 기간에 학습 12개월 + 검증 3개월 = 최소 15개월 필요
python pc/cli.py walk-forward --start 2023-01-01 --end 2024-12-30 --train-months 12 --test-months 3
```

### 문제: 로버스트니스 테스트 실패
**해결**: 파라미터 파일 경로 및 형식 확인
```bash
# JSON 형식 확인
cat best_params.json
```

---

## 📝 다음 단계

Phase 2 완료 후:
- ✅ 최적 파라미터 확보
- ✅ 전략 안정성 검증
- ✅ 강건성 확인

**Phase 3로 진행**: 실시간 운영
- 일중 매매 신호 구현
- 포지션 변경 알림
- 레짐 변경 감지
- 웹 대시보드
