# 백테스트 엔진 비교 분석

**작성일**: 2025-12-08  
**목적**: Jason(친구) 백테스트 엔진과 현재 시스템의 차이점 분석 및 개선 계획 수립

---

## 1. Jason 백테스트 엔진 분석

### 1.1 GitHub 저장소
- **URL**: https://github.com/jasonisdoing/momentum-etf
- **전략**: MAPS (Moving Average Position Score) 기반 추세 추종

### 1.2 성과 지표 (2024.12.03 기준)
| 지표 | 값 |
|------|-----|
| CAGR | 72.37% |
| MDD | -11.24% |
| Sharpe Ratio | 2.82 |

### 1.3 핵심 로직 분석

#### 성과 계산 (`account_runner.py`)

```python
# CAGR 계산
years = max((end_date - start_date).days / 365.25, 0.0)
cagr = (final_value / initial_capital) ** (1 / years) - 1

# MDD 계산
running_max = pv_series.cummax()
drawdown_series = (running_max - pv_series) / running_max
max_drawdown = float(drawdown_series.max())

# Sharpe Ratio 계산
daily_returns = pv_series.pct_change().dropna()
mean_ret = daily_returns.mean()
std_ret = daily_returns.std()
sharpe_ratio = (mean_ret / std_ret) * (252**0.5)
```

#### 특징
1. **연율화**: `365.25`일 기준 (윤년 고려)
2. **MDD**: 비율로 계산 후 최대값 (양수)
3. **Sharpe**: 일간 수익률 기반, `sqrt(252)` 연율화
4. **데이터 타입**: `pd.Timestamp` 일관 사용

---

## 2. 현재 시스템 분석

### 2.1 성과 계산 (`core/engine/backtest.py`)

```python
# CAGR 계산 (현재)
days = len(nav_series)
if days >= 126:
    annual_return = ((nav_series.iloc[-1] / initial_capital) ** (252 / days) - 1.0) * 100
elif days > 0:
    annual_return = total_return * (252 / days)
    annual_return = max(-100, min(200, annual_return))  # 제한

# MDD 계산
cummax = nav_series.cummax()
drawdown = (nav_series / cummax - 1.0) * 100
max_drawdown = drawdown.min()  # 음수

# Sharpe Ratio 계산
volatility = np.std(daily_returns) * np.sqrt(252) * 100
sharpe_ratio = annual_return / volatility
```

### 2.2 문제점

| 항목 | Jason | 현재 시스템 | 문제 |
|------|-------|-------------|------|
| **CAGR 연율화** | `365.25`일 기준 | `252`일 기준 | 거래일 vs 달력일 혼용 |
| **CAGR 제한** | 없음 | `-100% ~ 200%` | 인위적 제한으로 왜곡 |
| **MDD 부호** | 양수 (11.24%) | 음수 (-11.24%) | 표시 불일치 |
| **Sharpe 계산** | 일간 수익률 직접 사용 | 연율화된 값 사용 | 계산 방식 차이 |
| **데이터 타입** | `pd.Timestamp` 일관 | `date`/`Timestamp` 혼용 | 비교 오류 발생 |

---

## 3. 데이터 타입 불일치 문제

### 3.1 발생한 오류들

1. **`Cannot compare Timestamp with datetime.date`**
   - 원인: 캐시 파일 인덱스가 `datetime.date`, 새 데이터는 `pd.Timestamp`
   - 해결: 병합 전 인덱스를 `pd.Timestamp`로 통일

2. **`sort_index()` 오류**
   - 원인: 혼합된 인덱스 타입으로 정렬 불가
   - 해결: `pd.to_datetime()` 변환 후 정렬

### 3.2 권장 표준

| 항목 | 권장 타입 | 이유 |
|------|----------|------|
| 날짜 인덱스 | `pd.Timestamp` | pandas 연산 호환성 |
| 날짜 파라미터 | `datetime.date` | 사용자 입력 편의성 |
| 내부 처리 | `pd.Timestamp` | 일관성 |

---

## 4. 개선 계획

### Phase 1: 데이터 타입 표준화 (우선순위: 높음)

#### 4.1 캐시 데이터 마이그레이션
- 모든 캐시 파일의 인덱스를 `pd.Timestamp`로 통일
- 기존 `datetime.date` 인덱스 자동 변환

#### 4.2 백테스트 엔진 수정
- 입력 날짜를 `pd.Timestamp`로 변환
- 내부 처리 시 타입 일관성 유지

### Phase 2: 성과 계산 로직 개선 (우선순위: 높음)

#### 4.3 CAGR 계산 수정
```python
# 수정 전
annual_return = ((final / initial) ** (252 / days) - 1.0) * 100

# 수정 후 (Jason 방식)
years = (end_date - start_date).days / 365.25
cagr = ((final / initial) ** (1 / years) - 1.0) * 100
```

#### 4.4 MDD 표시 통일
```python
# 수정 전
max_drawdown = drawdown.min()  # 음수 (-11.24%)

# 수정 후 (Jason 방식)
max_drawdown = abs(drawdown.min())  # 양수 (11.24%)
```

#### 4.5 Sharpe Ratio 수정
```python
# 수정 전
sharpe = annual_return / volatility

# 수정 후 (Jason 방식)
daily_returns = pv_series.pct_change().dropna()
sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
```

### Phase 3: CAGR 제한 제거 (우선순위: 중간)

#### 4.6 인위적 제한 제거
- 현재: `-100% ~ 200%` 제한
- 수정: 제한 없이 실제 값 표시
- 대안: 짧은 기간(3개월 미만)은 "기간 수익률"로 표시

### Phase 4: 테스트 및 검증 (우선순위: 높음)

#### 4.7 동일 조건 비교 테스트
- 동일 기간, 동일 파라미터로 양쪽 엔진 실행
- 결과 비교 및 차이 분석

---

## 5. 작업 일정

| 단계 | 작업 | 예상 시간 | 우선순위 |
|------|------|----------|----------|
| 1 | 캐시 인덱스 타입 통일 | 1시간 | 높음 |
| 2 | CAGR 계산 로직 수정 | 30분 | 높음 |
| 3 | MDD 부호 통일 | 15분 | 높음 |
| 4 | Sharpe 계산 수정 | 30분 | 높음 |
| 5 | CAGR 제한 제거 | 15분 | 중간 |
| 6 | 테스트 및 검증 | 1시간 | 높음 |

**총 예상 시간**: 3시간 30분

---

## 6. 참고 자료

- Jason GitHub: https://github.com/jasonisdoing/momentum-etf
- 전략 로직 문서: https://github.com/jasonisdoing/momentum-etf/blob/main/docs/strategy_logic.md
- 현재 백테스트 엔진: `core/engine/backtest.py`
- 현재 튜닝 서비스: `app/services/tuning_service.py`
