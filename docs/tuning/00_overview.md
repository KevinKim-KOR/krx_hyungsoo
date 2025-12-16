# 튜닝/검증 체계 설계 - 개요 (v2.1)

> **작성**: 2025-12-16  
> **최종 수정**: 2025-12-17  
> **Author**: 형수  
> **목적**: 튜닝 파라미터 스키마 표준화 및 검증 체계(Test 봉인, Walk-Forward, 목적함수) 설계

---

## 문서 구조

| 파일 | 내용 |
|------|------|
| **00_overview.md** | Changelog, 배경/문제 정의, 설계 원칙 |
| 01_metrics_guardrails.md | 지표 정의, 이상치 감지, 멀티 룩백 |
| 02_objective_gates.md | 목적함수, Live 승격 게이트 |
| 03_walkforward_manifest.md | Walk-Forward, run_manifest |
| 04_implementation.md | 누수 방지, 파라미터 스키마, UI/UX, 리스크, 다음 액션 |

---

## Changelog

| 버전 | 변경 내용 |
|--------|---------|
| v1 | 초기 설계 |
| v1.1 | Walk-Forward 윈도우 수정, 단위 통일, 멀티 룩백 결합, 누수 방지 체크리스트 |
| v1.2 | objective 흐름 정리, 지표 정의 명시, 거래일 스냅, 캐시 설계, Live 승격 게이트, 이상치 감지, 생존편향/배당 처리 |
| v1.3 | Split 충돌 규칙, Test 계산 시점, 룩백 정의(거래일), stop_loss 트리거 규칙, 캐시 키 강화 |
| v1.4 | 스냅 함수 분리(시작/종료), WF/Holdout 기간 구분, 이상치 규칙 적용 시점, 캐시 해시 안정화, split_config 필드 통일, entry_price 정의, 비용 예시 보완 |
| v2 | WF 윈도우 스냅 규칙 반영, Objective Test 봉인 강제, exposure_ratio 정의 명확화, stop_loss 비용 완전 적용, 룩백 end_date 스냅, manifest split_applied 추가 |
| **v2.1** | WF 윈도우 스냅 규칙 반영, Objective에서 Test 계산 봉인 강제, exposure_ratio 정의 확정, stop_loss 비용(수수료 포함) 정합, 룩백 end_date 스냅 추가, run_manifest split_applied + 단계별(Test null) 정합 |

---

## 1. 배경 / 문제 정의

### 1.1 현재 상황

| 항목 | 현재 상태 |
|------|----------|
| 활성 튜닝 변수 | ma_period, rsi_period, stop_loss (3개) |
| 비활성 후보 | volatility_filter, market_breadth, rsi_overbought, rsi_oversold, rebalance_threshold |
| 튜닝 방식 | Optuna 범위 탐색 (단일 백테스트 아님) |
| 검증 분할 | Train 70% / Val 15% / Test 15% |

### 1.2 핵심 문제

**반복되는 패턴:**
```
Train Sharpe: 높음 (2.0+)
Val Sharpe: 0 이하 / 부진
Test Sharpe: 비정상적으로 높음 (1.5+)
```

**원인 분석:**
1. **Test 데이터 누수**: 튜닝 선택 시 Test 성과를 참조하면 사실상 Test로 최적화한 것
2. **단일 분할의 한계**: 특정 기간에 운 좋게 맞는 파라미터가 선택됨
3. **Val 구간 짧음**: 15%는 약 2~3개월, 노이즈에 취약
4. **목적함수 단순**: Sharpe만 최대화 → 과적합 유도
5. **거래 부족 시 Sharpe 왜곡**: 거래가 적으면 비정상적으로 높은 Sharpe 발생

### 1.3 해결 방향

| 문제 | 해결책 |
|------|--------|
| Test 누수 | **Test 봉인** — 선택/정렬에 사용 금지 |
| 단일 분할 한계 | **미니 Walk-Forward** — 롤링 검증 |
| Val 짧음 | **최소 개월수 규칙** (Val ≥ 6M, Test ≥ 6M) |
| 과적합 | **복합 목적함수** — Val 기반 + 안정성 페널티 + 가드레일 |
| 재현성 | **run_manifest** — 모든 실행 조건 저장 (seed 포함) |
| 누수 | **체크리스트** — 신호/체결 시점, 결측 처리 등 |
| 이상치 | **이상치 감지 레이더** — Sharpe/CAGR/표본수 기반 경고 |

---

## 2. 설계 원칙

### 2.1 검증 봉인 원칙

```
┌─────────────────────────────────────────────────────────────┐
│  Train (70%)  │  Val (15%)  │  Test (15%)                  │
│               │             │                              │
│  학습/탐색    │  선택 기준  │  최종 보고서에서만 열람      │
│               │             │  (선택/정렬/최적화 금지)     │
└─────────────────────────────────────────────────────────────┘
```

**강제 규칙:**
- Optuna objective = Val 성과만 사용
- UI 결과 테이블 정렬 = Val Sharpe 기준
- Test 컬럼은 "최종 리포트" 탭에서만 표시

**Test 계산 시점:**

```
⚠️ 절대 규칙: 튜닝 중에는 Test 자체를 계산하지 않는다.
   Gate 2 통과 후에만 Test 백테스트를 실행한다.
   (UI에서 숨기는 것만으로는 누수를 못 막음 - 로그로 볼 수 있음)
```

| 단계 | Test 계산 | 이유 |
|------|----------|------|
| 튜닝 중 (Optuna) | ❌ 계산 안 함 | 로그로도 누수 방지 |
| Gate 1 (Val Top-N) | ❌ 계산 안 함 | 선택 기준에 영향 방지 |
| Gate 2 (WF 안정성) | ❌ 계산 안 함 | 안정성 평가에 영향 방지 |
| Gate 2 통과 후 | ✅ 계산 | 최종 보고서용 |

**구현:**
```python
def run_backtest_for_tuning(params, period, costs):
    """
    튜닝용 백테스트: Train/Val만 계산
    """
    train_result = backtest(params, period['train'], costs=costs)
    val_result = backtest(params, period['val'], costs=costs)
    # ❌ Test는 계산하지 않음
    return {'train': train_result, 'val': val_result, 'test': None}

def run_backtest_for_final(params, period, costs):
    """
    최종 보고서용 백테스트: Test 포함 (Gate 2 통과 후에만 호출)
    """
    train_result = backtest(params, period['train'], costs=costs)
    val_result = backtest(params, period['val'], costs=costs)
    test_result = backtest(params, period['test'], costs=costs)
    return {'train': train_result, 'val': val_result, 'test': test_result}
```

### 2.2 Chronological Split 강제

```
⚠️ 절대 규칙: Split은 반드시 시간 순서(과거→미래)로 수행한다.
   랜덤 분할은 금지. 미래 데이터가 Train에 섞이면 누수 발생.
```

**Split 규칙:**
```python
# ✅ 올바른 분할 (Chronological)
data = data.sort_values('date')
train = data[:int(len(data) * 0.70)]
val   = data[int(len(data) * 0.70):int(len(data) * 0.85)]
test  = data[int(len(data) * 0.85):]

# ❌ 금지 (Random)
train, val, test = random_split(data, [0.70, 0.15, 0.15])
```

### 2.3 최소 기간 규칙 및 Split 충돌 해결

**Holdout Split vs Mini Walk-Forward 기간 구분:**

```
⚠️ Holdout Split(Train/Val/Test)은 Val/Test 기본 6M
   Mini Walk-Forward의 val/test는 3M (빠른 안정성 체크용)
```

| 용도 | Val 기간 | Test 기간 | 비고 |
|------|----------|----------|------|
| **Holdout Split** | 6개월 | 6개월 | 최종 평가용 |
| **Mini Walk-Forward** | 3개월 | 3개월 | 빠른 안정성 체크 |

| 구간 | 기본값 (Holdout) | 예외 (전체 기간 짧을 때) |
|------|-----------------|-------------------------|
| Val | **6개월 이상** | 최소 4개월 (경고 표시) |
| Test | **6개월 이상** | 최소 4개월 (경고 표시) |
| Train | **나머지** | 최소 8개월 (경고 표시) |

**Split 비율 vs 최소개월 충돌 해결 규칙:**

```
⚠️ 절대 규칙: 최소개월 우선, 비율은 목표치
   Val = 6개월, Test = 6개월, Train = 나머지
   기간이 짧으면 예외 + 경고 표시
```

**예시 (24개월 기간):**
- 70/15/15 비율 적용 시: Val=3.6개월, Test=3.6개월 → 최소개월 미달
- **실제 적용**: Val=6개월, Test=6개월, Train=12개월 (나머지)

**Split 계산 로직:**
```python
def calculate_split(total_months, min_val=6, min_test=6, min_train=8):
    """
    최소개월 우선 Split 계산
    """
    # 1. 최소 기간 확보 가능 여부 확인
    required = min_val + min_test + min_train
    if total_months < required:
        # 예외 모드: 4/4/8 최소값
        if total_months < 16:
            raise ValueError(f"전체 기간이 16개월 미만입니다: {total_months}개월")
        val_months = 4
        test_months = 4
        train_months = total_months - val_months - test_months
        warnings.append("⚠️ Val/Test가 최소값(4개월)으로 설정되었습니다.")
    else:
        # 정상 모드: 6/6/나머지
        val_months = min_val
        test_months = min_test
        train_months = total_months - val_months - test_months
    
    return train_months, val_months, test_months
```

### 2.4 단위 통일 원칙

```
⚠️ 절대 규칙: 엔진/manifest 내부는 소수(0~1), UI 표시만 %
```

| 지표 | 내부 저장 (소수) | UI 표시 (%) |
|------|-----------------|-------------|
| CAGR | 0.25 | 25% |
| MDD | -0.12 | -12% |
| stop_loss | -0.10 | -10% |
| commission | 0.00015 | 0.015% |
| slippage | 0.001 | 0.1% |
| Sharpe | 1.5 (무단위) | 1.5 |

### 2.5 거래일 스냅 규칙

```
⚠️ 시작일은 다음 영업일로, 종료일은 이전 영업일로 스냅한다.
   (시작일을 이전 영업일로 스냅하면 기간 밖으로 튀는 사고 발생)
```

**스냅 함수 분리:**
```python
def snap_start(date, trading_calendar):
    """시작일: 휴장일이면 다음 영업일로 스냅"""
    while date not in trading_calendar:
        date = date + timedelta(days=1)  # 다음 영업일
    return date

def snap_end(date, trading_calendar):
    """종료일: 휴장일이면 이전 영업일로 스냅"""
    while date not in trading_calendar:
        date = date - timedelta(days=1)  # 이전 영업일
    return date

# 예시:
# 2024-01-01(휴장) 시작일 → 2024-01-02로 스냅 (다음 영업일)
# 2025-06-30(휴장) 종료일 → 2025-06-27로 스냅 (이전 영업일)
```

**잘못된 예시 (기간 밖으로 튀는 사고):**
```python
# ❌ 시작일을 이전 영업일로 스냅하면:
# 2024-01-01(휴장) → 2023-12-29로 스냅 → 기간 밖!
```

### 2.6 탐색 공간 제어 원칙

```
활성 변수 수 × 각 변수 step 수 = 탐색 공간
```

**예시:**
- ma_period: (200-20)/10 = 18개
- rsi_period: (30-5)/1 = 25개
- stop_loss: (20-5)/1 = 15개
- **총 조합: 18 × 25 × 15 = 6,750개**

**탐색 커버리지:**
```
Trials = 50일 때, 커버리지 ≈ 50 / 6,750 = 0.7%
→ "전수조사가 아닌 샘플링 탐색"임을 UI에 명시
```
