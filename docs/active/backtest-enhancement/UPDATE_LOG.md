# 백테스트 엔진 고도화 설계 - 업데이트 로그

**업데이트 일시**: 2025-11-30  
**작업 내용**: 비판적 검토 반영 및 문서 수정

---

## 📝 업데이트 요약

### 작업 완료 항목
1. ✅ 비판적 검토 문서 작성 (`BACKTEST_ENHANCEMENT_CRITICAL_REVIEW.md`)
2. ✅ Part 1 문서 업데이트 (현황 분석)
3. ✅ Summary 문서 업데이트 (실행 계획)
4. ✅ 업데이트 로그 작성 (본 문서)

### 주요 변경사항

#### 1. Phase 0 추가 (검증 프레임워크 우선)
**변경 전**:
```
1순위: 거래비용 모델
2순위: 레짐 스케일링
3순위: Train/Val/Test
```

**변경 후**:
```
0순위: 간단한 Train/Test 분리 (검증 프레임워크)
1순위: 거래비용 모델
2순위: 레짐 스케일링
3순위: Train/Val/Test 고도화
```

**이유**: 모든 변경사항을 Train/Test 양쪽에서 검증해야 과적합 방지 가능

---

#### 2. 상품별 세율 차별화
**변경 전**:
```yaml
costs:
  korea:
    tax_rate: 0.0023  # 일괄 0.23%
```

**변경 후**:
```yaml
costs:
  korea:
    stock:
      tax_rate: 0.0023  # 주식: 0.23%
    etf:
      tax_rate: 0.0      # ETF: 0% (면제)
    leveraged_etf:
      tax_rate: 0.0      # 레버리지 ETF: 0% (면제)
```

**이유**: 
- ETF는 대부분 거래세 면제
- 일괄 0.23% 적용 시 ETF 성과를 과도하게 깎음
- 현실적인 성과 예측 필요

---

#### 3. 레짐 엔진 표현 명확화
**변경 전**:
```markdown
**레짐 엔진**: ✅ 이미 구현됨 - Week 3에서 검증
```

**변경 후**:
```markdown
**레짐 엔진**:
- ✅ 레짐 감지 로직: 구현 및 테스트 완료
- ✅ 포지션 비율 계산: 구현 완료
- ❌ **포트폴리오 적용: 미구현** (가장 심각!)

**Week 3 성과의 진실**:
- 레짐 감지는 했지만 포지션 조절은 안 함
- Week 3 성과는 레짐 엔진 덕이 아님
```

**이유**: 
- "검증됨"이라는 표현이 오해 소지
- 실제로는 레짐 감지만 하고 포지션 조절은 안 함
- Week 3 성과가 레짐 덕이라고 착각할 여지 제거

---

#### 4. 레버리지 처리 명확화
**변경 전**:
```python
if regime == 'bull':
    return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
```

**변경 후**:
```python
class MarketRegimeDetector:
    def __init__(self, ..., enable_leverage: bool = False):
        self.enable_leverage = enable_leverage
    
    def get_position_ratio(self, regime, confidence):
        if regime == 'bull':
            if self.enable_leverage:
                return 1.0 + (confidence - 0.5) * 0.4  # 100~120%
            else:
                return 0.8 + (confidence - 0.5) * 0.4  # 80~100%
```

**이유**:
- 120% 포지션은 레버리지 필요
- 엔진이 레버리지를 지원하는지 불명확
- 현금 음수 발생 가능성
- 기본값은 레버리지 비활성화 (안전)

---

#### 5. 최소 데이터 길이 검증 추가
**변경 전**:
```python
train_ratio = 0.7  # 70%
val_ratio = 0.15   # 15%
test_ratio = 0.15  # 15%
```

**변경 후**:
```python
class TrainValTestSplitter:
    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        min_train_days: int = 504,  # 최소 2년
        min_val_days: int = 126,    # 최소 6개월
        min_test_days: int = 126    # 최소 6개월
    ):
        ...
    
    def split(self, start_date, end_date):
        # 최소 길이 검증
        if train_days < self.min_train_days:
            raise ValueError("Train 기간 부족")
        ...
```

**이유**:
- 현재 데이터 3~4년은 매크로 사이클 기준 부족
- Train 1.8년은 너무 짧음
- 구간별 레짐 편향 가능성

---

#### 6. 파라미터 튜닝 단계화
**변경 전**:
```python
param_grid = {
    'commission_rate': [0.00015, 0.0003],
    'max_positions': [5, 10, 15],
    'rebalance_frequency': ['daily', 'weekly'],
    'ma_period': [20, 50, 100],
    'rsi_period': [7, 14, 21],
    ...  # 조합 폭발!
}
```

**변경 후**:
```python
# Phase 1: 핵심 파라미터 (2~3개)
param_grid_phase1 = {
    'max_positions': [5, 10, 15],
    'rebalance_frequency': ['daily', 'weekly']
}

# Phase 2: 전략 파라미터 (2~3개)
param_grid_phase2 = {
    'ma_period': [20, 50, 100],
    'rsi_period': [7, 14, 21]
}

# 총 조합: 6 + 9 = 15개 (안전)
# vs 전체 한 번에: 6 × 9 = 54개 (과적합 위험)
```

**이유**:
- 파라미터 수가 많으면 Validation도 과적합
- 한 번에 2~3개만 튜닝
- 단계적 접근으로 안정성 확보

---

#### 7. Gross/Net 구현 난이도 재평가
**변경 전**:
```markdown
- 난이도: ⭐⭐ (쉬움)
- 작업량: 지표 계산 함수 두 번 호출
```

**변경 후**:
```markdown
- 난이도: ⭐⭐⭐ (중간)
- 작업량:
  1. Gross 포트폴리오 병렬 추적 (복잡)
  2. 모든 거래 함수에서 Gross 업데이트
  3. 메모리 사용량 약 2배
  
- 대안: 간소화 구현
  - 거래 로그에서 비용 합산
  - Net NAV + 총 비용 = Gross NAV (근사)
```

**이유**:
- 현재 엔진은 NAV 자체가 이미 Net
- Gross를 알려면 가상 포트폴리오 병렬 실행 필요
- 단순히 함수 두 번 호출로는 해결 안 됨

---

#### 8. 성과 지표 Single Source of Truth
**변경 전**:
```python
# core/engine/backtest.py
class BacktestEngine:
    def get_performance_metrics(self):
        cagr = self._calculate_cagr(...)  # 여기서 계산

# core/metrics/performance.py
def calc_cagr(...):
    ...  # 여기서도 계산
```

**변경 후**:
```python
# core/engine/backtest.py
class BacktestEngine:
    def get_performance_metrics(self):
        from core.metrics.performance import calc_cagr
        cagr = calc_cagr(...)  # 위임만

# core/metrics/performance.py
def calc_cagr(...):
    ...  # 유일한 계산 위치
```

**이유**:
- 중복 코드 제거
- 수정 시 한 곳만 변경
- 일관성 보장

---

## 📊 예상 성과 변화 (수정)

### 거래비용 모델 (ETF 전략 기준)
**변경 전 예상**:
```
현재: CAGR 27.05%
거래세 반영 후: CAGR 26.0~26.5% (약 0.5~1% 감소)
```

**변경 후 예상**:
```
현재: CAGR 27.05%
거래세 반영 후 (ETF): CAGR 27.0% (거의 변화 없음, 면제)
거래세 반영 후 (주식): CAGR 26.0~26.5% (약 0.5~1% 감소)
```

### 레짐 노출 스케일링
**변경 전 예상**:
```
레짐 반영 후:
- Bull: 120% 포지션
- Bear: 40% 포지션
- MDD: -15%
```

**변경 후 예상 (레버리지 비활성화)**:
```
레짐 반영 후:
- Bull: 100% 포지션 (안전)
- Bear: 40% 포지션
- MDD: -15%
- 현금 음수 발생 안 함
```

---

## 🎯 수정된 우선순위

| 순위 | 단계 | 예상 기간 | 핵심 변경 |
|------|------|----------|----------|
| **0** | 간단한 Train/Test 분리 | 0.5일 | **검증 프레임워크 우선** |
| **1** | 거래비용 모델 (상품별) | 1~2일 | ETF/주식 구분 |
| **2** | 레짐 노출 스케일링 | 1~2일 | 레버리지 비활성화 |
| **3** | Train/Val/Test 고도화 | 2~3일 | 단계적 튜닝 |
| **4** | Config 연결 | 0.5일 | - |
| **5** | 분석 로그 | 1일 | - |

**총 예상 기간**: 6~9일 (기존 5.5~8.5일에서 증가)

---

## ✅ 수용한 비판 (8개)

1. ✅ 상품별 세율 차별화 (`instrument_type` 추가)
2. ✅ 레짐 "검증됨" 표현 수정 (명확화)
3. ✅ 120% 포지션 레버리지 처리 (`enable_leverage` 플래그)
4. ✅ 최소 데이터 길이 검증 (Train 2년, Val/Test 6개월)
5. ✅ 파라미터 튜닝 단계화 (한 번에 2~3개)
6. ✅ Gross/Net 구현 난이도 재평가 (간소화 대안)
7. ✅ 성과 지표 Single Source of Truth
8. ✅ 작업 순서 재조정 (Phase 0 추가)

---

## 📚 업데이트된 문서

1. **BACKTEST_ENHANCEMENT_CRITICAL_REVIEW.md** (신규)
   - 비판적 검토 및 수정안
   - 항목별 수용/반박
   - 상세 설계 변경

2. **BACKTEST_ENHANCEMENT_PART1_ANALYSIS.md** (수정)
   - 레짐 엔진 표현 명확화
   - 상품별 세율 추가
   - 우선순위 재조정 (Phase 0 추가)

3. **BACKTEST_ENHANCEMENT_SUMMARY.md** (수정)
   - Phase 0 추가
   - 상품별 세율 반영
   - 레버리지 처리 명확화
   - 검증 프레임워크 강조

4. **BACKTEST_ENHANCEMENT_UPDATE_LOG.md** (신규, 본 문서)
   - 업데이트 요약
   - 변경사항 상세
   - 수정된 예상 성과

---

## 🚀 내일부터 구현 시작

### Phase 0: 검증 프레임워크 (0.5일)
- `simple_train_test_split()` 함수
- `run_backtest_with_split()` 함수
- 기존 백테스트를 Train/Test로 분리 실행

### Phase 1: 거래비용 모델 (1~2일)
- `instrument_type` 파라미터 추가
- 상품별 거래세 분기
- Gross/Net 구분 (간소화 버전)

### Phase 2: 레짐 노출 스케일링 (1~2일)
- `enable_leverage` 플래그 (기본 False)
- 레짐 비율 적용
- 현금 음수 방지

### Phase 3: Train/Val/Test 고도화 (2~3일)
- 최소 길이 검증
- 단계적 파라미터 튜닝
- 레짐 균형 검증

---

**작성자**: Cascade AI  
**검토 완료**: 2025-11-30  
**구현 시작**: 2025-12-01 (예정)
