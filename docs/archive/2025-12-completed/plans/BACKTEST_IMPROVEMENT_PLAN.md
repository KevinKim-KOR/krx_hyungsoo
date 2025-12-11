# 백테스트 엔진 개선 계획

**작성일**: 2025-12-08  
**상태**: ✅ 완료 (2025-12-08)  
**관련 문서**: [비교 분석](../analysis/BACKTEST_COMPARISON_ANALYSIS.md)

---

## 1. 배경

### 1.1 해결된 문제
- ~~튜닝 결과가 비현실적 (CAGR 12000%, MDD -400%)~~ → 정상 범위로 수정됨
- ~~데이터 타입 불일치로 인한 오류 빈발~~ → 캐시 인덱스 타입 통일 완료
- ~~Jason 엔진과 성과 계산 방식 차이~~ → 동일한 방식 적용

### 1.2 달성된 목표
- ✅ Jason 엔진과 동일한 성과 계산 로직 적용
- ✅ 데이터 타입 표준화로 오류 방지
- ✅ 신뢰할 수 있는 백테스트 결과 제공

---

## 2. 개선 항목

### 2.1 Phase 1: 데이터 타입 표준화

#### 작업 1.1: 캐시 인덱스 마이그레이션 스크립트
**파일**: `scripts/migrate_cache_index.py`

```python
# 의사 코드
for each parquet file in data/cache/:
    df = read_parquet(file)
    if df.index.dtype == 'object':
        df.index = pd.to_datetime(df.index)
        df.to_parquet(file)
```

**검증**:
- 마이그레이션 전후 데이터 무결성 확인
- 인덱스 타입이 `datetime64[ns]`인지 확인

#### 작업 1.2: 캐시 업데이트 로직 수정
**파일**: `api_backtest.py`

- 새 데이터 저장 시 항상 `pd.Timestamp` 인덱스 사용
- 기존 데이터 로드 시 인덱스 타입 확인 및 변환

---

### 2.2 Phase 2: 성과 계산 로직 수정

#### 작업 2.1: CAGR 계산 수정
**파일**: `core/engine/backtest.py`

**현재**:
```python
annual_return = ((final / initial) ** (252 / days) - 1.0) * 100
```

**수정**:
```python
years = (end_date - start_date).days / 365.25
if years > 0:
    cagr = ((final / initial) ** (1 / years) - 1.0) * 100
else:
    cagr = 0.0
```

**이유**: 
- 거래일(252) 대신 달력일(365.25) 사용
- Jason 엔진과 동일한 방식

#### 작업 2.2: MDD 부호 통일
**파일**: `core/engine/backtest.py`

**현재**:
```python
max_drawdown = drawdown.min()  # 음수 반환
```

**수정**:
```python
max_drawdown = abs(drawdown.min())  # 양수 반환
```

**이유**:
- MDD는 일반적으로 양수로 표시
- Jason 엔진과 동일한 방식

#### 작업 2.3: Sharpe Ratio 수정
**파일**: `core/engine/backtest.py`

**현재**:
```python
volatility = np.std(daily_returns) * np.sqrt(252) * 100
sharpe_ratio = annual_return / volatility
```

**수정**:
```python
daily_returns = pv_series.pct_change().dropna()
if len(daily_returns) > 1:
    mean_ret = daily_returns.mean()
    std_ret = daily_returns.std()
    if std_ret > 0:
        sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0
else:
    sharpe_ratio = 0.0
```

**이유**:
- 일간 수익률 직접 사용
- Jason 엔진과 동일한 방식

---

### 2.3 Phase 3: CAGR 제한 제거

#### 작업 3.1: 인위적 제한 제거
**파일**: `core/engine/backtest.py`

**현재**:
```python
annual_return = max(-100, min(200, annual_return))
```

**수정**:
```python
# 제한 제거, 실제 값 사용
# 단, UI에서 짧은 기간은 "기간 수익률"로 표시
```

---

### 2.4 Phase 4: UI 수정

#### 작업 4.1: MDD 표시 수정
**파일**: `web/dashboard/src/pages/Strategy.tsx`

**현재**:
```tsx
<span className="text-red-500">-{mdd}%</span>
```

**수정**:
```tsx
<span className="text-red-500">-{Math.abs(mdd)}%</span>
```

---

## 3. 테스트 계획

### 3.1 단위 테스트
- CAGR 계산 함수 테스트
- MDD 계산 함수 테스트
- Sharpe 계산 함수 테스트

### 3.2 통합 테스트
- 동일 조건으로 백테스트 실행
- Jason 결과와 비교

### 3.3 검증 데이터
| 기간 | 예상 CAGR | 예상 MDD | 예상 Sharpe |
|------|----------|---------|-------------|
| 2024-01-01 ~ 2024-12-31 | 10~30% | 5~15% | 0.5~2.0 |

---

## 4. 롤백 계획

### 4.1 백업
- 수정 전 `core/engine/backtest.py` 백업
- 캐시 마이그레이션 전 `data/cache/` 백업

### 4.2 롤백 절차
1. Git revert로 코드 복원
2. 백업된 캐시 파일 복원

---

## 5. 완료 체크리스트

- [x] 분석 문서 검토 완료
- [x] 개선 계획 검토 완료
- [x] 작업 시작 승인
- [x] Phase 1: 캐시 인덱스 타입 통일 완료
- [x] Phase 2: 성과 계산 로직 수정 완료
- [x] Phase 3: CAGR 제한 제거 완료
- [x] Phase 4: UI 수정 완료
- [x] 리밸런싱 임계값 설정화 (1% 하드코딩 제거)
- [x] 거래 승률 계산 개선 (실제 거래 기준)
- [x] 최적 파라미터 저장 API 구현
- [x] 최적 파라미터 저장 UI 연결

---

## 6. 추가 개선 사항 (완료)

### 6.1 AI 분석 연동
- [x] AI 분석용 프롬프트 생성 함수 (`promptGenerator.ts`)
- [x] 튜닝 결과에 "최적 결과 AI 분석" 버튼 추가
- [x] 손실 구간 분석 프롬프트 템플릿
- [x] 새 변수 제안 프롬프트 템플릿

### 6.2 UI 개선
- [x] "빠른 백테스트" 섹션 제거 (튜닝으로 통합)
- [x] "최적 파라미터 저장" 버튼 API 연결

---

## 7. 관련 문서

- `docs/plans/AI_ANALYSIS_INTEGRATION_PLAN.md` - AI 분석 연동 계획
- `docs/plans/VARIABLE_SYSTEM_PLAN.md` - 변수 관리 시스템 계획 (다음 단계)
