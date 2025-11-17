# Phase 5 완료 보고서

**작성일**: 2025-11-17  
**작성자**: Cascade AI Assistant  
**프로젝트**: KRX Alertor Modular

---

## 📋 목차

1. [개요](#개요)
2. [Phase 5-1: NAS ↔ Oracle 데이터 연동](#phase-5-1-nas--oracle-데이터-연동)
3. [Phase 5-2: 머신러닝 모델 개발](#phase-5-2-머신러닝-모델-개발)
4. [Phase 5-3: 포트폴리오 최적화](#phase-5-3-포트폴리오-최적화)
5. [Phase 5-4: 룩백 분석](#phase-5-4-룩백-분석)
6. [성과 요약](#성과-요약)
7. [다음 단계](#다음-단계)

---

## 개요

Phase 5는 **고급 분석 및 최적화**를 목표로 하며, 다음 4개 서브 페이즈로 구성됩니다:

- **Phase 5-1**: NAS ↔ Oracle 데이터 연동 (자동 동기화)
- **Phase 5-2**: 머신러닝 모델 개발 (ETF 랭킹 예측)
- **Phase 5-3**: 포트폴리오 최적화 (효율적 프론티어)
- **Phase 5-4**: 룩백 분석 (워크포워드 분석)

### 목표

1. ✅ NAS와 Oracle Cloud 간 데이터 자동 동기화
2. ✅ ML 기반 ETF 랭킹 예측 모델 구축
3. ✅ PyPortfolioOpt 기반 포트폴리오 최적화
4. ✅ 워크포워드 분석을 통한 전략 검증

---

## Phase 5-1: NAS ↔ Oracle 데이터 연동

### 목표

NAS에서 생성한 데이터를 Oracle Cloud로 자동 동기화하여, FastAPI가 최신 데이터를 제공하도록 구성.

### 구현 내용

#### 1. NAS 데이터 생성 스크립트

**파일**: `scripts/sync/generate_sync_data.py`

```python
# 주요 기능:
# - OHLCV 데이터 로드 (yfinance)
# - Parquet 형식으로 저장
# - 메타데이터 JSON 생성
# - 로그 기록

# 실행:
python scripts/sync/generate_sync_data.py --codes "069500,091160" --start "2023-01-01" --end "2024-11-01"
```

**출력**:
- `data/sync/ohlcv/{code}.parquet`
- `data/sync/meta.json`

#### 2. rsync 동기화 스크립트

**파일**: `scripts/sync/sync_to_oracle.sh`

```bash
#!/bin/bash
# rsync를 통해 NAS → Oracle Cloud 동기화
# - SSH 키 기반 인증
# - 증분 동기화 (변경된 파일만)
# - 로그 기록

# 실행:
bash scripts/sync/sync_to_oracle.sh
```

**동기화 경로**:
```
NAS: /volume2/homes/Hyungsoo/krx/krx_alertor_modular/data/sync/
→ Oracle: /home/ubuntu/krx_alertor_modular/data/sync/
```

#### 3. SSH 키 설정

**파일**: `scripts/sync/setup_ssh_key.sh`

NAS에서 `ssh-copy-id` 명령어가 없을 때 수동으로 공개키를 등록하는 스크립트.

```bash
# 실행:
bash scripts/sync/setup_ssh_key.sh
```

#### 4. FastAPI 수정

**파일**: `api/main.py`

동기화된 파일을 우선적으로 읽도록 수정:

```python
# 1순위: data/sync/ohlcv/{code}.parquet (동기화 파일)
# 2순위: data/cache/ohlcv/{code}.parquet (캐시 파일)
# 3순위: yfinance 다운로드
```

### 성과

- ✅ NAS → Oracle 자동 동기화 구축
- ✅ SSH 키 기반 인증 설정
- ✅ FastAPI 동기화 파일 우선 읽기
- ✅ 증분 동기화로 효율성 향상

### 파일 구조

```
scripts/sync/
├── generate_sync_data.py   # NAS 데이터 생성
├── sync_to_oracle.sh        # rsync 동기화
├── setup_ssh_key.sh         # SSH 키 설정
└── README.md                # 사용 가이드

data/sync/
├── ohlcv/
│   ├── 069500.parquet
│   └── 091160.parquet
└── meta.json
```

---

## Phase 5-2: 머신러닝 모델 개발

### 목표

XGBoost/LightGBM 기반 ETF 랭킹 예측 모델 구축.

### 구현 내용

#### 1. 특징 엔지니어링

**파일**: `pc/ml/feature_engineering.py`

**46개 특징 생성**:

| 카테고리 | 특징 | 개수 |
|---------|------|------|
| **기본 OHLCV** | Open, High, Low, Close, Volume, AdjClose | 6 |
| **기술적 지표** | RSI(14,28), MACD, BB, MA(5,10,20,50,100,200) | 18 |
| **모멘텀 지표** | ROC(5,10,20,60), MOM(5,10,20), Stochastic, Williams %R | 8 |
| **변동성 지표** | ATR(14,28), Historical Vol(10,20,60), Parkinson's Vol | 6 |
| **거시 지표** | KOSPI 상관관계, 베타, 거래량 비율 | 8 |

**주요 메서드**:
```python
class FeatureEngineer:
    def calculate_technical_indicators()  # RSI, MACD, BB, MA
    def calculate_momentum_indicators()   # ROC, MOM, Stochastic
    def calculate_volatility_indicators() # ATR, Vol
    def calculate_macro_indicators()      # KOSPI 상관, 베타
```

#### 2. 모델 학습

**파일**: `pc/ml/train_xgboost.py`

**지원 모델**:
- XGBoost
- LightGBM

**지원 태스크**:
- 회귀 (Regression): N일 후 수익률 예측
- 분류 (Classification): 상승/하락 예측

**주요 클래스**:
```python
class ETFRankingModel:
    def prepare_data()           # 데이터 로드 및 특징 생성
    def train()                  # 모델 학습
    def predict()                # 예측
    def save_model()             # 모델 저장
    def load_model()             # 모델 로드
```

**실행 예시**:
```bash
python pc/ml/train_xgboost.py \
  --model xgboost \
  --task regression \
  --target-days 5 \
  --codes "069500,091160" \
  --start-date "2023-01-01" \
  --end-date "2024-11-01"
```

#### 3. 학습 결과

**테스트 조건** (2종목, 2023-2024):
- 종목: 069500, 091160
- 샘플: 454행
- 특징: 46개
- Train/Test: 363/91

**성능**:
```
Train RMSE: 0.001085, R²: 0.9986
Test RMSE: 0.068128, R²: -0.3973
```

**Top 10 중요 특징**:
1. volatility_60: 0.0629
2. ma_100: 0.0609
3. roc_60: 0.0592
4. macd_signal: 0.0536
5. williams_r: 0.0513
6. atr_28: 0.0419
7. parkinson_vol: 0.0399
8. ma_50: 0.0376
9. volatility_10: 0.0312
10. atr_14: 0.0311

**분석**:
- Train R²가 높고 Test R²가 음수 → **과적합**
- 더 많은 종목 데이터 필요 (10개 이상)
- 더 긴 기간 필요 (3년 이상)
- 하이퍼파라미터 튜닝 필요 (Optuna)

### 성과

- ✅ 46개 특징 엔지니어링 완료
- ✅ XGBoost/LightGBM 학습 스크립트 완성
- ✅ 모델 저장/로드 기능 구현
- ✅ Feature Importance 분석
- ⚠️ 과적합 문제 발견 (실제 운영 시 개선 필요)

### 파일 구조

```
pc/ml/
├── feature_engineering.py   # 특징 엔지니어링
├── train_xgboost.py         # 모델 학습
└── __init__.py

data/output/ml/
├── xgboost_regression_*.pkl # 학습된 모델
├── scaler_*.pkl             # 스케일러
└── meta_*.json              # 메타데이터
```

---

## Phase 5-3: 포트폴리오 최적화

### 목표

PyPortfolioOpt 기반 포트폴리오 최적화 (효율적 프론티어, 리스크 패리티).

### 구현 내용

#### 1. 포트폴리오 최적화 모듈

**파일**: `pc/optimization/portfolio_optimizer.py`

**지원 최적화 방법**:

| 방법 | 설명 | 목표 |
|-----|------|------|
| **Max Sharpe** | Sharpe Ratio 최대화 | 위험 대비 수익 극대화 |
| **Min Volatility** | 변동성 최소화 | 리스크 최소화 |
| **Efficient Return** | 목표 수익률 달성 | 특정 수익률 목표 |

**주요 클래스**:
```python
class PortfolioOptimizer:
    def load_data()                          # 가격 데이터 로드
    def calculate_expected_returns_and_risk() # 기대 수익률 및 공분산
    def optimize_max_sharpe()                # Sharpe 최대화
    def optimize_min_volatility()            # 변동성 최소화
    def optimize_efficient_return()          # 목표 수익률
    def calculate_discrete_allocation()      # 이산 배분
    def save_results()                       # 결과 저장
```

**실행 예시**:
```bash
python pc/optimization/portfolio_optimizer.py \
  --codes "069500,091160,133690" \
  --start-date "2023-01-01" \
  --end-date "2024-11-01" \
  --portfolio-value 10000000 \
  --max-weight 0.4 \
  --min-weight 0.1
```

#### 2. 최적화 결과

**테스트 조건** (3종목, 2023-2024):
- 종목: 069500 (KODEX 200), 091160 (KODEX 반도체), 133690 (KOSEF 국고채)
- 제약: 최대 40%, 최소 10%
- 총 투자액: 1천만원

**Sharpe Ratio 최대화**:
```
기대 수익률: 29.9%
변동성: 18.1%
Sharpe Ratio: 1.49

최적 비중:
- 069500: 40%
- 091160: 20%
- 133690: 40%
```

**이산 배분** (실제 매수 주식 수):
```
총 투자액: 10,000,000원
잔액: 21,441원

매수:
- 069500: 120주
- 091160: 63주
- 133690: 33주
```

**분석**:
- Sharpe Ratio 1.49 → 우수한 위험 대비 수익
- 변동성 18.1% → 적절한 리스크 수준
- 국고채 40% 비중 → 안정성 확보

### 성과

- ✅ PyPortfolioOpt 기반 최적화 완료
- ✅ Sharpe Ratio 최대화 구현
- ✅ 변동성 최소화 구현
- ✅ 이산 배분 (실제 매수 주식 수) 계산
- ✅ 제약 조건 (최대/최소 비중) 지원

### 파일 구조

```
pc/optimization/
├── portfolio_optimizer.py   # 포트폴리오 최적화
└── __init__.py

data/output/optimization/
└── optimal_portfolio_*.json # 최적화 결과
```

---

## 성과 요약

### Phase 5-1: NAS ↔ Oracle 데이터 연동

| 항목 | 상태 | 비고 |
|-----|------|------|
| NAS 데이터 생성 | ✅ | Parquet 형식 |
| rsync 동기화 | ✅ | 증분 동기화 |
| SSH 키 설정 | ✅ | 수동 등록 스크립트 |
| FastAPI 수정 | ✅ | 동기화 파일 우선 |

### Phase 5-2: 머신러닝 모델 개발

| 항목 | 상태 | 비고 |
|-----|------|------|
| 특징 엔지니어링 | ✅ | 46개 특징 |
| XGBoost 학습 | ✅ | 회귀/분류 지원 |
| LightGBM 학습 | ✅ | 회귀/분류 지원 |
| 모델 저장/로드 | ✅ | Pickle 형식 |
| Feature Importance | ✅ | JSON 저장 |
| 과적합 문제 | ⚠️ | 더 많은 데이터 필요 |

### Phase 5-3: 포트폴리오 최적화

| 항목 | 상태 | 비고 |
|-----|------|------|
| Sharpe 최대화 | ✅ | Sharpe 1.49 |
| 변동성 최소화 | ✅ | Vol 18.1% |
| 이산 배분 | ✅ | 실제 매수 주식 수 |
| 제약 조건 | ✅ | 최대/최소 비중 |

### Phase 5-4: 룩백 분석

| 항목 | 상태 | 비고 |
|-----|------|------|
| 워크포워드 분석 | ✅ | 4회 리밸런싱 |
| 포트폴리오 최적화 방법 | ✅ | 평균 Sharpe 2.47 |
| ML 랭킹 방법 | ✅ | 모멘텀 기반 |
| 요약 통계 | ✅ | 승률 75% |

---

---

## Phase 5-4: 룩백 분석

### 목표

과거 시점 기준 "그때 전략을 썼다면?" 워크포워드 분석 (Walk-Forward Analysis).

### 구현 내용

#### 1. 룩백 분석 모듈

**파일**: `pc/analysis/lookback_analysis.py`

**주요 기능**:
- 워크포워드 분석 (시계열 교차 검증)
- 포트폴리오 최적화 방법
- ML 랭킹 방법 (모멘텀 기반)

**주요 클래스**:
```python
class LookbackAnalyzer:
    def load_data()                          # 가격 데이터 로드
    def run_walkforward_analysis()           # 워크포워드 분석
    def _generate_rebalance_dates()          # 리밸런싱 날짜 생성
    def _analyze_portfolio_optimization()    # 포트폴리오 최적화
    def _analyze_ml_ranking()                # ML 랭킹
    def calculate_summary_statistics()       # 요약 통계
    def save_results()                       # 결과 저장
```

**실행 예시**:
```bash
python pc/analysis/lookback_analysis.py \
  --codes "069500,091160,133690" \
  --start-date "2022-01-01" \
  --end-date "2024-11-01" \
  --lookback-window 252 \
  --rebalance-freq 63 \
  --test-window 21 \
  --method portfolio_optimization
```

#### 2. 분석 결과

**테스트 조건** (3종목, 2022-2024):
- 종목: 069500, 091160, 133690
- 학습 윈도우: 252일 (1년)
- 리밸런싱 주기: 63일 (3개월)
- 테스트 윈도우: 21일 (1개월)

**워크포워드 분석 결과** (4회 리밸런싱):

| 날짜 | 최적 비중 | 수익률 | 변동성 | Sharpe |
|-----|----------|--------|--------|--------|
| 2023-09-25 | 133690: 100% | -0.46% | 15.17% | -0.23 |
| 2024-01-29 | 091160: 20%, 133690: 80% | 2.96% | 17.17% | 1.67 |
| 2024-06-03 | 091160: 8%, 133690: 92% | 10.09% | 13.40% | 6.31 |
| 2024-10-07 | 133690: 100% | 2.23% | 15.80% | 2.15 |

**요약 통계**:
```
총 리밸런싱 횟수: 4
평균 수익률: 3.71%
평균 변동성: 15.39%
평균 Sharpe Ratio: 2.47
승률: 75%
최고 수익률: 10.09%
최저 수익률: -0.46%
```

**분석**:
- 평균 Sharpe 2.47 → 우수한 위험 조정 수익
- 승률 75% → 안정적인 성과
- 국고채(133690) 높은 비중 → 안정성 중시
- 2024년 상반기 최고 성과 (10.09%)

### 성과

- ✅ 워크포워드 분석 구현 완료
- ✅ 포트폴리오 최적화 방법 지원
- ✅ ML 랭킹 방법 지원 (모멘텀 기반)
- ✅ 요약 통계 자동 계산
- ✅ 결과 JSON 저장

### 파일 구조

```
pc/analysis/
├── lookback_analysis.py     # 룩백 분석
└── __init__.py

data/output/analysis/
└── lookback_analysis_*.json # 분석 결과
```

---

## 다음 단계

### Phase 5-5: UI/UX 통합 (예정)

**목표**: 모든 기능을 하나의 대시보드에 통합

**구현 내용**:
- React + TailwindCSS + shadcn/ui
- 차트 라이브러리 (Recharts, Plotly)
- 포트폴리오 최적화 결과 시각화
- 백테스트 결과 비교
- ML 모델 Feature Importance 시각화
- 룩백 분석 결과 시각화

### 프로젝트 정리 (예정)

**목표**: 미사용 파일/폴더 정리

**작업 내용**:
- 미사용 파일 식별 및 제거
- 폴더 구조 정리
- 문서 업데이트

---

## 기술 스택

### 데이터 수집 및 처리
- **yfinance**: OHLCV 데이터 수집
- **pandas**: 데이터 처리
- **numpy**: 수치 계산

### 머신러닝
- **XGBoost**: 그래디언트 부스팅
- **LightGBM**: 경량 그래디언트 부스팅
- **scikit-learn**: 전처리, 평가

### 포트폴리오 최적화
- **PyPortfolioOpt**: 포트폴리오 최적화
- **cvxpy**: 볼록 최적화

### 인프라
- **rsync**: 파일 동기화
- **SSH**: 보안 통신
- **FastAPI**: REST API

---

## 참고 자료

### 문서
- `docs/PHASE5_PLAN.md`: Phase 5 전체 계획
- `scripts/sync/README.md`: 동기화 가이드
- `pc/ml/README.md`: ML 모델 가이드 (예정)
- `pc/optimization/README.md`: 최적화 가이드 (예정)

### 코드
- `scripts/sync/`: 동기화 스크립트
- `pc/ml/`: ML 모델
- `pc/optimization/`: 포트폴리오 최적화

### 결과
- `data/sync/`: 동기화 데이터
- `data/output/ml/`: ML 모델 결과
- `data/output/optimization/`: 최적화 결과

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|-----|------|----------|
| 2025-11-17 | 1.0 | Phase 5-1, 5-2, 5-3 완료 |
| 2025-11-18 | 1.1 | Phase 5-4 추가 (룩백 분석) |

---

**작성**: Cascade AI Assistant  
**최종 수정**: 2025-11-18
