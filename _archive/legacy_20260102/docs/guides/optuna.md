# Optuna 파라미터 최적화 가이드

## 개요

Optuna를 사용한 전략 파라미터 자동 최적화 시스템입니다.

**목적 함수**: 연율화 수익률 - λ × MDD (기본 λ=2.0)

---

## 사용 방법

### 기본 실행
```bash
# PC에서 실행
python pc/cli.py optimize --start 2024-01-01 --trials 100
```

### 상세 옵션
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --capital 10000000 \
  --trials 100 \
  --timeout 3600 \
  --mdd-lambda 2.0 \
  --seed 42 \
  --output reports/optuna/my_study \
  --plot
```

---

## 파라미터 설명

### 필수 파라미터
- `--start`: 백테스트 시작일 (YYYY-MM-DD)

### 선택 파라미터
- `--end`: 백테스트 종료일 (기본: today)
- `--capital`: 초기 자본 (기본: 10,000,000원)
- `--trials`: Trial 수 (기본: 100)
- `--timeout`: 타임아웃 (초, 미지정시 무제한)
- `--mdd-lambda`: MDD 패널티 계수 (기본: 2.0)
- `--seed`: 랜덤 시드 (재현성 보장)
- `--output`: 결과 저장 경로 (기본: reports/optuna/study_<timestamp>)
- `--plot`: 시각화 생성 (HTML)

---

## 최적화 대상 파라미터

### 기술적 지표
- `ma_period`: 이동평균 기간 [10, 120]
- `rsi_period`: RSI 기간 [7, 30]
- `adx_threshold`: ADX 임계값 [10.0, 40.0]
- `bb_period`: 볼린저 밴드 기간 [10, 40]
- `bb_std`: 볼린저 밴드 표준편차 [1.5, 3.0]

### 신호 생성
- `momentum_weight`: 모멘텀 가중치 [0.0, 1.0]
- `trend_weight`: 추세 가중치 [0.0, 1.0]
- `mean_reversion_weight`: 평균회귀 가중치 [0.0, 1.0]
- ※ 가중치는 자동으로 정규화됨

### 리밸런싱
- `rebalance_frequency`: {daily, weekly, monthly}

### 포지션 관리
- `max_positions`: 최대 보유 종목 수 [5, 15]
- `position_cap`: 종목당 최대 비중 [0.15, 0.35]

### 리스크 관리
- `portfolio_vol_target`: 목표 변동성 [0.08, 0.20]
- `max_drawdown_threshold`: 최대 낙폭 임계값 [-0.25, -0.10]
- `cooldown_days`: 쿨다운 기간 [3, 10]
- `max_correlation`: 최대 상관계수 [0.5, 0.85]

---

## 출력 파일

### 1. best_params.yaml
최적 파라미터 (YAML 형식)

```yaml
ma_period: 45
rsi_period: 14
adx_threshold: 25.3
rebalance_frequency: monthly
max_positions: 10
...
```

### 2. study_report.md
최적화 리포트 (Markdown)

- 설정 정보
- 최적 결과 (목적함수 값, 메트릭)
- 최적 파라미터

### 3. study.db
Optuna Study 데이터베이스 (SQLite)

- 모든 trial 기록
- 재개 가능 (load_if_exists=True)

### 4. 시각화 (--plot 옵션)
- `optimization_history.html`: 최적화 히스토리
- `param_importances.html`: 파라미터 중요도

---

## 사용 예시

### 예시 1: 빠른 테스트 (10 trials)
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --trials 10 \
  --seed 42
```

### 예시 2: 본격 최적화 (100 trials, 1시간 제한)
```bash
python pc/cli.py optimize \
  --start 2023-01-01 \
  --trials 100 \
  --timeout 3600 \
  --mdd-lambda 2.0 \
  --plot
```

### 예시 3: MDD 패널티 강화 (λ=3.0)
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --trials 50 \
  --mdd-lambda 3.0
```

### 예시 4: 재현성 보장 (고정 시드)
```bash
python pc/cli.py optimize \
  --start 2024-01-01 \
  --trials 100 \
  --seed 42 \
  --output reports/optuna/reproducible_study
```

---

## 최적 파라미터 적용

### 1. best_params.yaml 확인
```bash
cat reports/optuna/study_<timestamp>/best_params.yaml
```

### 2. config.yaml에 반영
```yaml
# config/config.yaml
strategy:
  signals:
    ma_period: 45  # Optuna 최적값
    rsi_period: 14
    adx_threshold: 25.3
  ...
```

### 3. 백테스트로 검증
```bash
python pc/cli.py backtest \
  --start 2024-01-01 \
  --output reports/backtest_optimized
```

---

## 고급 사용법

### Study 재개
동일한 output 경로로 재실행하면 이전 trial부터 이어서 실행됩니다.

```bash
# 첫 실행 (50 trials)
python pc/cli.py optimize \
  --start 2024-01-01 \
  --trials 50 \
  --output reports/optuna/my_study

# 재개 (추가 50 trials)
python pc/cli.py optimize \
  --start 2024-01-01 \
  --trials 100 \
  --output reports/optuna/my_study
```

### Study DB 직접 조회
```python
import optuna

study = optuna.load_study(
    study_name='krx_alertor_20241031_083900',
    storage='sqlite:///reports/optuna/study_20241031_083900/study.db'
)

print(f"Best value: {study.best_value}")
print(f"Best params: {study.best_params}")

# 모든 trial 조회
df = study.trials_dataframe()
print(df.head())
```

---

## 트러블슈팅

### 1. 메모리 부족
- `--trials` 수 줄이기
- 백테스트 기간 단축
- 유니버스 크기 축소

### 2. 너무 느림
- `--timeout` 설정
- `--trials` 수 줄이기
- 병렬 실행 (향후 지원 예정)

### 3. 최적화 결과가 이상함
- 백테스트 기간 확인 (너무 짧지 않은지)
- 목적 함수 확인 (MDD 패널티 조정)
- 검색 공간 확인 (extensions/optuna/space.py)

---

## 다음 단계

1. **워크포워드 분석**: 최적 파라미터의 안정성 검증
2. **로버스트니스 테스트**: 시드 변동, 수수료 민감도 테스트
3. **앙상블**: 여러 최적 파라미터 조합

---

## 참고

- Optuna 공식 문서: https://optuna.readthedocs.io/
- 프로젝트 문서: `docs/NEW/README.md`
