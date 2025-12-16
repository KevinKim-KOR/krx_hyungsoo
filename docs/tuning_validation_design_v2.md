# 튜닝/검증 체계 설계 문서 (v2)

> **작성**: 2025-12-16  
> **최종 수정**: 2025-12-16  
> **Author**: 형수  
> **목적**: 튜닝 파라미터 스키마 표준화 및 검증 체계(Test 봉인, Walk-Forward, 목적함수) 설계

---

## Changelog

| 버전 | 변경 내용 |
|--------|---------|
| v1 | 초기 설계 |
| v1.1 | Walk-Forward 윈도우 수정, 단위 통일, 멀티 룩백 결합, 누수 방지 체크리스트 |
| v1.2 | objective 흐름 정리, 지표 정의 명시, 거래일 스냅, 캐시 설계, Live 승격 게이트, 이상치 감지, 생존편향/배당 처리 |
| v1.3 | Split 충돌 규칙, Test 계산 시점, 룩백 정의(거래일), stop_loss 트리거 규칙, 캐시 키 강화 |
| v1.4 | 스냅 함수 분리(시작/종료), WF/Holdout 기간 구분, 이상치 규칙 적용 시점, 캐시 해시 안정화, split_config 필드 통일, entry_price 정의, 비용 예시 보완 |
| **v2** | WF 윈도우 스냅 규칙 반영, Objective Test 봉인 강제, exposure_ratio 정의 명확화, stop_loss 비용 완전 적용, 룩백 end_date 스냅, manifest split_applied 추가 |

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

**Test 계산 시점 (Final+0.1 추가):**

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

**구현 (v2: 비용 적용):**
```python
def run_backtest_for_tuning(params, period, costs):
    """
    튜닝용 백테스트: Train/Val만 계산
    v2: 비용(costs) 반드시 전달
    """
    train_result = backtest(params, period['train'], costs=costs)  # ⭐ 비용 적용
    val_result = backtest(params, period['val'], costs=costs)      # ⭐ 비용 적용
    # ❌ Test는 계산하지 않음
    return {'train': train_result, 'val': val_result, 'test': None}

def run_backtest_for_final(params, period, costs):
    """
    최종 보고서용 백테스트: Test 포함 (Gate 2 통과 후에만 호출)
    v2: 비용(costs) 반드시 전달
    """
    train_result = backtest(params, period['train'], costs=costs)  # ⭐ 비용 적용
    val_result = backtest(params, period['val'], costs=costs)      # ⭐ 비용 적용
    test_result = backtest(params, period['test'], costs=costs)    # ⭐ 비용 적용
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

### 2.3 최소 기간 규칙 및 Split 충돌 해결 (v2 수정)

**Holdout Split vs Mini Walk-Forward 기간 구분 (v2):**

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

### 2.5 거래일 스냅 규칙 (v2 수정)

```
⚠️ 시작일은 다음 영업일로, 종료일은 이전 영업일로 스냅한다.
   (시작일을 이전 영업일로 스냅하면 기간 밖으로 튀는 사고 발생)
```

**스냅 함수 분리 (v2):**
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

---

## 3. 지표 정의 (Final 추가)

### 3.1 핵심 지표 정의

```
⚠️ 아래 정의는 구현 시 반드시 준수. 정의가 다르면 결과 비교 불가.
```

| 지표 | 정의 | 산식 |
|------|------|------|
| **num_trades** | 매수+매도 거래 횟수 합계 | `len(buy_orders) + len(sell_orders)` |
| **exposure_ratio** | 전체 거래일 중 포지션 보유일 비율 | `position_days / total_trading_days` |
| **annual_turnover** | 연간 매매 회전율 (리밸런싱 기준) | `(연간_매수금액 + 연간_매도금액) / (2 × 평균_포트폴리오_가치)` |
| **Sharpe** | 연환산 샤프 비율 (무위험 수익률 0% 가정) | `mean(daily_returns) / std(daily_returns) × sqrt(252)` |
| **CAGR** | 연복리 수익률 | `(최종가치 / 초기가치)^(1/연수) - 1` |
| **MDD** | 최대 낙폭 (고점 대비 최대 하락률) | `min((현재가치 - 고점) / 고점)` |

**exposure_ratio 정의 명확화 (v2):**

```
⚠️ exposure_ratio = position_days / total_trading_days
   - 분모: 전체 거래일 (현금 100%일 포함)
   - 분자: 포지션 보유일 (현금 100%일은 포함되지 않음)
   - 예: 252거래일 중 180일 포지션 보유 → 180/252 = 0.714
```

```python
def calculate_exposure_ratio(daily_positions, trading_days):
    """
    exposure_ratio 계산
    - position_days: 포지션 > 0인 날 수
    - total_trading_days: 전체 거래일 수 (현금일 포함)
    """
    position_days = sum(1 for pos in daily_positions if pos > 0)
    total_trading_days = len(trading_days)
    return position_days / total_trading_days
```

### 3.2 가드레일 임계값

| 가드레일 | 임계값 | 위반 시 처리 |
|----------|--------|-------------|
| 최소 거래수 | num_trades ≥ 30 | score = -999 (탈락) |
| 최소 노출 | exposure_ratio ≥ 0.30 | score = -999 (탈락) |
| 최대 회전율 | annual_turnover ≤ 24 | score = -999 (탈락) |

### 3.3 비용 모델 정의 (Final 추가)

```
⚠️ commission/slippage는 "편도" 기준. 왕복 시 2배 적용.
```

| 비용 항목 | 기본값 | 적용 방식 |
|----------|--------|----------|
| commission | 0.00015 (0.015%) | 매수/매도 각각 적용 (편도) |
| slippage | 0.001 (0.1%) | 매수/매도 각각 적용 (편도) |

**왕복 비용 계산:**
```python
round_trip_cost = 2 * (commission + slippage)
# 기본값: 2 * (0.00015 + 0.001) = 0.0023 (0.23%)
```

### 3.4 stop_loss 트리거/체결 규칙 (v2 수정)

```
⚠️ 절대 규칙: 손절 판단과 체결 시점을 명확히 분리한다.
   이 규칙 하나로 MDD/Sharpe가 크게 달라진다.
```

**entry_price 정의 (v2 추가):**

```
⚠️ entry_price = 포지션의 VWAP(가중평균 매수가)
   추가매수/리밸런싱이 있으면 평균단가로 갱신
```

| 상황 | entry_price 계산 |
|------|-----------------|
| 최초 매수 | 매수 체결가 |
| 추가 매수 | VWAP = (기존금액 + 추가금액) / (기존수량 + 추가수량) |
| 리밸런싱 | 리밸런싱 후 평균단가로 갱신 |

**권장 방식 (현실형):**

| 단계 | 시점 | 설명 |
|------|------|------|
| 손절 조건 판단 | T일 종가 | 종가 기준으로 stop_loss 도달 여부 확인 |
| 손절 체결 | T+1일 시가 | 다음 거래일 시가로 청산 |

**구현:**
```python
def check_stop_loss(position, current_close, stop_loss_pct):
    """
    T일 종가 기준 손절 조건 판단
    entry_price는 VWAP (가중평균 매수가)
    """
    entry_price = position['entry_price']  # VWAP
    return_pct = (current_close - entry_price) / entry_price
    
    # stop_loss_pct는 음수 (예: -0.10)
    return return_pct <= stop_loss_pct

def execute_stop_loss(position, next_open, costs):
    """
    T+1일 시가로 손절 체결 (v2: slippage + commission 모두 적용)
    """
    # 슬리피지 반영
    sell_price = next_open * (1 - costs['slippage_rate'])
    # 수수료 반영
    proceeds = sell_price * position['quantity'] * (1 - costs['commission_rate'])
    
    return {
        'action': 'SELL',
        'price': sell_price,
        'proceeds': proceeds,
        'reason': 'STOP_LOSS',
    }
```

**대안 방식:**

| 방식 | 판단 기준 | 체결 시점 | 특징 |
|------|----------|----------|------|
| **현실형 (권장)** | T일 종가 | T+1일 시가 | 실제 거래 가능, 보수적 |
| 보수형 | T일 종가 | T일 종가 | 슬리피지 없음 가정, 낙관적 |
| 공격형 | T일 저가 | T일 저가 | Intraday 가정, OHLC만 있으면 비현실적 |

```
⚠️ 공격형(저가 기준)은 실제로 그 가격에 체결 가능한지 알 수 없음.
   OHLC 데이터만 있으면 "가정"임을 명시해야 함.
```

---

## 4. 이상치 감지 레이더 (v2 수정)

### 4.1 자동 경고 규칙

```
⚠️ 아래 조건 충족 시 UI에 경고 배지 표시 + 자동 검토 대상
```

| 조건 | 경고 메시지 | 배지 | 적용 시점 |
|------|------------|------|----------|
| Sharpe > 5.0 | "산출/표본/누수 점검 필요" | 🔴 | 튜닝 중 |
| CAGR > 1.0 (100%) | "비현실적 수익률, 누수 의심" | 🔴 | 튜닝 중 |
| num_trades < 30 | "표본 부족, 통계적 신뢰도 낮음" | 🟡 | 튜닝 중 |
| exposure_ratio < 0.30 | "노출 부족, 대부분 현금 보유" | 🟡 | 튜닝 중 |
| Val↓ Test↑↑ (Val < 0, Test > 1.5) | "Val/Test 괴리, 과적합 의심" | 🔴 | **Gate 3 이후** |

```
⚠️ Val↓Test↑↑ 규칙은 Test 산출 이후(=Gate 3 시점)에만 평가한다.
   튜닝 중에는 Test를 계산하지 않으므로 이 규칙 적용 불가.
```

### 4.2 UI 표시 예시

```
┌────┬────┬────┬───────┬────────┬────────┬──────┬───────┬──────────────┐
│ #  │ MA │RSI │ SL(%) │ Train  │  Val   │ Test │ 거래수│ 상태         │
├────┼────┼────┼───────┼────────┼────────┼──────┼───────┼──────────────┤
│ 1  │ 60 │ 14 │ -10%  │  2.1   │  1.5   │  🔒  │  45   │ ✅ 정상      │
│ 2  │ 80 │ 12 │  -8%  │  1.9   │  1.3   │  🔒  │  38   │ ✅ 정상      │
│ 3  │ 40 │ 21 │ -15%  │  2.5   │  0.2   │  🔒  │  12   │ 🟡 표본↓     │
│ 4  │ 30 │  5 │  -5%  │  6.0   │ -0.5   │  🔒  │  52   │ 🔴 Sharpe↑↑  │
│ 5  │ 50 │ 10 │ -12%  │  2.0   │ -0.3   │  🔒  │  40   │ 🔴 Val↓Test↑ │
└────┴────┴────┴───────┴────────┴────────┴──────┴───────┴──────────────┘
```

### 4.3 표본 부족 시 Sharpe 표시

```python
def display_sharpe(sharpe, num_trades):
    if num_trades < 30:
        return f"<span class='text-gray-400'>{sharpe:.2f}*</span>"  # 회색 + 별표
    return f"{sharpe:.2f}"
```

---

## 5. 멀티 룩백 결합 설계

### 5.1 문제 정의

UI에서 3M/6M/12M 룩백을 동시에 선택할 수 있는데, 각 룩백별로 Val 점수가 다르게 나옴.
이를 **하나의 objective로 결합하는 규칙**이 필요.

### 5.2 결합 방식 비교

| 방식 | 공식 | 장점 | 단점 |
|------|------|------|------|
| **평균** | `mean(scores)` | 단순 | 하나가 나빠도 평균에 묻힘 → 과적합 |
| **최솟값 (min)** | `min(scores)` | 최악 케이스 방어 | 보수적, 최적 성과 낮음 |
| **평균-표준편차** | `mean - k*std` | 균형 (안정성 반영) | k 설정 주관적 |

### 5.3 권장 결합 규칙

**Option A: 최솟값 (강력한 안정성 지향) — 기본값**

```python
final_score = min(val_score_3m, val_score_6m, val_score_12m)
```

**Option B: 평균 - k*표준편차 (균형형)**

```python
scores = [val_score_3m, val_score_6m, val_score_12m]
final_score = np.mean(scores) - 1.0 * np.std(scores)
```

### 5.4 룩백 정의 (Final+0.1 추가)

```
⚠️ 절대 규칙: 룩백은 거래일 기준으로 정의한다.
   3M = 63거래일, 6M = 126거래일, 12M = 252거래일
   end_date 포함해서 정확히 63/126/252 거래일 (inclusive)
```

| 룩백 | 거래일 수 | 비고 |
|--------|----------|------|
| 3M | **63일** | 약 3달량 |
| 6M | **126일** | 약 6달량 |
| 12M | **252일** | 약 1년량 |

**룩백 계산 로직:**
```python
LOOKBACK_TRADING_DAYS = {
    3: 63,    # 3개월 = 63거래일
    6: 126,   # 6개월 = 126거래일
    12: 252,  # 12개월 = 252거래일
}

def get_lookback_start(end_date, lookback_months, trading_calendar):
    """
    거래일 기준 룩백 시작일 계산
    v2: end_date가 휴장일이면 먼저 스냅
    v2: end_date 포함해서 정확히 N 거래일 (inclusive)
    """
    # v2: end_date가 휴장일이면 이전 영업일로 스냅
    end_date = snap_end(end_date, trading_calendar)
    
    trading_days = LOOKBACK_TRADING_DAYS[lookback_months]
    
    # end_date 포함해서 역순으로 trading_days만큼 거슬러 올라감
    calendar_before_end = [d for d in trading_calendar if d <= end_date]
    if len(calendar_before_end) < trading_days:
        raise ValueError(f"데이터 부족: {trading_days}거래일 필요, {len(calendar_before_end)}일 존재")
    
    return calendar_before_end[-trading_days]
```

**달력월 대신 거래일을 쓰는 이유:**
- 달력월은 휴장일/공휴일에 따라 실제 거래일 수가 다름
- 3개월이 60일일 수도, 66일일 수도 있음
- 거래일 기준이면 항상 동일한 데이터 양으로 비교 가능

### 5.5 캐시 설계 (v2 수정)

멀티 룩백 실행 시 계산량이 3배로 증가. 캐시로 중복 계산 방지.

```
⚠️ 캐시 키에 data_version, universe_version 필수 포함.
   다른 데이터인데 캐시 재사용되는 사고 방지.
⚠️ hash() 대신 hashlib.md5() 사용 (프로세스 간 일관성 보장)
```

**split_config 필드 통일 (v2):**

```python
# ✅ 통일된 split_config 구조
split_config = {
    'train_months': 12,      # 실제 적용값 (개월)
    'val_months': 6,
    'test_months': 6,
    'method': 'chronological',
    'target_ratios': {       # 참고값 (비율)
        'train': 0.70,
        'val': 0.15,
        'test': 0.15,
    }
}
```

**캐시 키 설계 (v2):**
```python
def make_cache_key(params, lookback, period, costs, split_config, data_config):
    """
    동일한 조건의 백테스트 결과를 캐싱
    
    v2: hash() 대신 hashlib.md5() 사용 (프로세스 간 일관성)
    v2: split_config 필드명 통일
    """
    # ⭐ v2: 안정 해시 사용 (hash()는 프로세스마다 다를 수 있음)
    params_sig = json.dumps(params, sort_keys=True)
    params_hash = hashlib.md5(params_sig.encode()).hexdigest()
    
    key_dict = {
        # 파라미터
        'params_hash': params_hash,  # ⭐ v2: 안정 해시
        'lookback': lookback,
        
        # 기간
        'start_date': period['start_date'],
        'end_date': period['end_date'],
        
        # 비용
        'commission': costs['commission_rate'],
        'slippage': costs['slippage_rate'],
        
        # Split (v2: 통일된 필드명)
        'train_months': split_config['train_months'],
        'val_months': split_config['val_months'],
        'test_months': split_config['test_months'],
        'split_method': split_config['method'],
        
        # 데이터/유니버스 버전
        'data_version': data_config['data_version'],
        'universe_version': data_config['universe_version'],
        'price_type': data_config.get('price_type', 'adj_close'),
        'dividend_handling': data_config.get('dividend_handling', 'total_return'),
    }
    return hashlib.md5(json.dumps(key_dict, sort_keys=True).encode()).hexdigest()

# 캐시 사용
split_config = {
    'train_months': 12,
    'val_months': 6,
    'test_months': 6,
    'method': 'chronological',
}
data_config = {
    'data_version': 'ohlcv_20251216',
    'universe_version': 'krx_etf_20251216',
    'price_type': 'adj_close',
    'dividend_handling': 'total_return',
}
cache_key = make_cache_key(params, lookback, period, costs, split_config, data_config)
if cache_key in run_cache:
    return run_cache[cache_key]
result = run_backtest(params, lookback, costs=costs)  # ⭐ v2: 비용 전달
run_cache[cache_key] = result
```

---

## 6. 목적함수(Objective) 설계

### 6.1 Objective 흐름 (Final 수정)

```
⚠️ trial은 Optuna 객체, params는 파라미터 dict.
   run_backtest()는 params를 받는다. trial을 직접 넘기지 않는다.
```

**올바른 흐름 (v2: Test 봉인 강제):**
```python
def objective(trial, lookbacks=[3, 6, 12]):
    """
    1. trial에서 params 추출
    2. params로 백테스트 실행 (튜닝용 함수 사용!)
    3. 결과로 점수 계산
    
    v2: run_backtest_for_tuning() 사용으로 Test 봉인 강제
    """
    # Step 1: 파라미터 추출
    params = {
        'ma_period': trial.suggest_int('ma_period', 20, 200, step=10),
        'rsi_period': trial.suggest_int('rsi_period', 5, 30),
        'stop_loss': trial.suggest_float('stop_loss', -0.20, -0.05, step=0.01),
    }
    
    scores = []
    for lb in lookbacks:
        # Step 2: 튜닝용 함수로 백테스트 실행 (Test 계산 안 함!)
        result = run_backtest_for_tuning(
            params=params,
            period=get_period_for_lookback(lb),
            costs=DEFAULT_COSTS
        )
        
        # Step 3: 가드레일 체크
        if not check_guardrails(result):
            return -999
        
        # Step 4: 점수 계산 (Val 기반)
        score = calculate_score(result)
        scores.append(score)
    
    # Step 5: 멀티 룩백 결합
    return min(scores)
```

### 6.2 가드레일 체크 함수

```python
def check_guardrails(result):
    """
    가드레일 통과 여부 확인
    하나라도 실패하면 False
    """
    if result.num_trades < 30:
        return False
    if result.exposure_ratio < 0.30:
        return False
    if result.annual_turnover > 24:
        return False
    return True
```

### 6.3 점수 계산 함수

```python
def calculate_score(result):
    """
    Val 기반 점수 계산 (MDD 페널티 포함)
    """
    val_sharpe = result.val_sharpe
    val_mdd = result.val_mdd  # 소수 (예: -0.12)
    
    # MDD 페널티: 15% 초과 시
    mdd_threshold = 0.15
    mdd_penalty = max(0, abs(val_mdd) - mdd_threshold) * 10
    
    return val_sharpe - mdd_penalty
```

### 6.4 거래비용 기본 적용

```
⚠️ 절대 규칙: 거래비용은 "옵션"이 아니라 "기본값"으로 항상 적용.
   비용 없이 튜닝하면 Test에서 성과가 급락하는 "신내림" 현상 발생.
```

```python
DEFAULT_COSTS = {
    'commission_rate': 0.00015,  # 0.015% (편도)
    'slippage_rate': 0.001,      # 0.1% (편도)
}

# 비용은 항상 적용
result = run_backtest(params, costs=DEFAULT_COSTS)
```

---

## 7. Live 승격 게이트 (Final 추가)

### 7.1 승격 프로세스

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Live 승격 게이트                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Gate 1: Val 기준 Top-N 선정                                           │
│  ────────────────────────────────────────────────────────────────────  │
│  - Val Sharpe 기준 상위 N개 (기본 N=5)                                 │
│  - 가드레일 통과 필수                                                   │
│  - 이상치 경고(🔴) 없어야 함                                           │
│                                                                         │
│                              ↓                                          │
│                                                                         │
│  Gate 2: Walk-Forward 안정성 통과                                      │
│  ────────────────────────────────────────────────────────────────────  │
│  - 미니 Walk-Forward 실행 (3~5개 윈도우)                               │
│  - stability_score ≥ 1.0                                               │
│  - win_rate ≥ 60% (Sharpe > 0인 윈도우 비율)                           │
│                                                                         │
│                              ↓                                          │
│                                                                         │
│  Gate 3: Test 공개 + Live 후보 등록                                    │
│  ────────────────────────────────────────────────────────────────────  │
│  - Gate 1, 2 통과한 Trial만 Test 성과 공개                             │
│  - Live 적용 후보로 등록                                                │
│  - 최종 선택은 사용자가 수동으로                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 게이트 통과 조건

| 게이트 | 조건 | 통과 기준 |
|--------|------|----------|
| Gate 1 | Val Top-N | Val Sharpe 상위 5개 |
| Gate 1 | 가드레일 | num_trades ≥ 30, exposure ≥ 30%, turnover ≤ 24 |
| Gate 1 | 이상치 | 🔴 경고 없음 |
| Gate 2 | 안정성 점수 | stability_score ≥ 1.0 |
| Gate 2 | 승률 | win_rate ≥ 60% |
| Gate 3 | 최종 확인 | 사용자 수동 선택 |

### 7.3 UI 표시

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Live 승격 후보                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✅ Trial #1 — Gate 1, 2 통과                                          │
│     Val Sharpe: 1.5 | 안정성: 1.8 | 승률: 80%                          │
│     [Test 확인] [Live 적용]                                            │
│                                                                         │
│  ✅ Trial #5 — Gate 1, 2 통과                                          │
│     Val Sharpe: 1.3 | 안정성: 1.2 | 승률: 60%                          │
│     [Test 확인] [Live 적용]                                            │
│                                                                         │
│  ⏸️ Trial #2 — Gate 2 대기 (안정성 검증 필요)                          │
│     Val Sharpe: 1.4 | [안정성 검증 실행]                               │
│                                                                         │
│  ❌ Trial #3 — Gate 1 탈락 (이상치 경고)                               │
│     Val Sharpe: 2.0 | 🔴 Sharpe↑↑                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 미니 Walk-Forward 설계

### 8.1 윈도우 생성 규칙

```
⚠️ 절대 규칙: 모든 윈도우는 전체 기간(start_date ~ end_date) 내에서만 생성.
   end_date를 초과하는 윈도우는 생성하지 않는다.
   윈도우 경계일이 휴장일이면 이전 영업일로 스냅한다.
```

**윈도우 생성 알고리즘 (v2 수정):**
```python
def generate_windows(start_date, end_date, train_months, val_months, test_months, 
                     stride_months, trading_calendar):
    """
    전체 기간 내에서만 윈도우 생성.
    v2: 시작일은 snap_start(), 종료일은 snap_end() 사용
    """
    windows = []
    
    current_start = start_date
    while True:
        train_end = current_start + relativedelta(months=train_months)
        val_start = train_end
        val_end = val_start + relativedelta(months=val_months)
        test_start = val_end
        test_end = test_start + relativedelta(months=test_months)
        
        # end_date 초과 시 중단
        if test_end > end_date:
            break
        
        # v2: 시작일은 snap_start, 종료일은 snap_end
        windows.append({
            'train': (
                snap_start(current_start, trading_calendar),
                snap_end(train_end - timedelta(days=1), trading_calendar)
            ),
            'val': (
                snap_start(val_start, trading_calendar),
                snap_end(val_end - timedelta(days=1), trading_calendar)
            ),
            'test': (
                snap_start(test_start, trading_calendar),
                snap_end(test_end - timedelta(days=1), trading_calendar)
            ),
        })
        
        current_start += relativedelta(months=stride_months)
    
    return windows
```

### 8.2 정확한 윈도우 예시

**설정:**
- 전체 기간: 2024-01-01 ~ 2025-12-31 (24개월)
- Train: 12개월, Val: 3개월, Test: 3개월
- Stride: 3개월

**생성된 윈도우:**

| Window | Train | Val | Test |
|--------|-------|-----|------|
| W1 | 2024-01-02 ~ 2024-12-31 | 2025-01-02 ~ 2025-03-31 | 2025-04-01 ~ 2025-06-30 |
| W2 | 2024-04-01 ~ 2025-03-31 | 2025-04-01 ~ 2025-06-30 | 2025-07-01 ~ 2025-09-30 |
| W3 | 2024-07-01 ~ 2025-06-30 | 2025-07-01 ~ 2025-09-30 | 2025-10-01 ~ 2025-12-30 |

**W4는 생성되지 않음** (Test가 2026-01~03으로 end_date 초과)

### 8.3 안정성 점수 계산

```python
def calculate_stability_score(sharpe_list):
    """
    안정성 점수 = 평균 / (표준편차 + epsilon)
    높을수록 안정적
    """
    mean = np.mean(sharpe_list)
    std = np.std(sharpe_list)
    epsilon = 0.1
    return mean / (std + epsilon)

def calculate_win_rate(sharpe_list):
    """
    승률 = Sharpe > 0인 윈도우 비율
    """
    wins = sum(1 for s in sharpe_list if s > 0)
    return wins / len(sharpe_list)
```

---

## 9. run_manifest 설계

### 9.1 스키마 (v2 수정)

```json
{
  "run_id": "tuning_20251216_143052_abc123",
  "created_at": "2025-12-16T14:30:52+09:00",
  "schema_version": "4.0",
  "stage": "tuning",
  
  "config": {
    "period": {
      "start_date": "2024-01-01",
      "end_date": "2025-12-31"
    },
    "lookbacks": [3, 6, 12],
    "lookback_combination": "min",
    "trials": 50,
    "objective": "val_sharpe_with_mdd_penalty",
    
    "split_target": {
      "train_ratio": 0.70,
      "val_ratio": 0.15,
      "test_ratio": 0.15
    },
    
    "split_applied": {
      "train_months": 12,
      "val_months": 6,
      "test_months": 6,
      "train_range": ["2024-01-02", "2024-12-31"],
      "val_range": ["2025-01-02", "2025-06-30"],
      "test_range": ["2025-07-01", "2025-12-30"]
    },
    
    "guardrails": {
      "min_trades": 30,
      "min_exposure_ratio": 0.30,
      "max_annual_turnover": 24
    },
    
    "variables": {
      "ma_period": {
        "enabled": true,
        "range": [20, 200],
        "step": 10,
        "type": "int"
      },
      "rsi_period": {
        "enabled": true,
        "range": [5, 30],
        "step": 1,
        "type": "int"
      },
      "stop_loss": {
        "enabled": true,
        "range": [-0.20, -0.05],
        "step": 0.01,
        "type": "float",
        "unit": "decimal"
      }
    },
    
    "cost_assumptions": {
      "commission_rate": 0.00015,
      "slippage_rate": 0.001,
      "cost_type": "one_way",
      "unit": "decimal"
    }
  },
  
  "data": {
    "universe_version": "krx_etf_20251216",
    "universe_source": "KRX",
    "delisted_handling": "exclude_from_start",
    "survivorship_bias": "point_in_time",
    "price_type": "adj_close",
    "dividend_handling": "total_return",
    "data_version": "ohlcv_20251216"
  },
  
  "results": {
    "best_trial": {
      "trial_number": 1,
      "params": {
        "ma_period": 60,
        "rsi_period": 14,
        "stop_loss": -0.10
      },
      "metrics": {
        "train": { "sharpe": 2.1, "cagr": 0.25, "mdd": -0.08 },
        "val": { "sharpe": 1.5, "cagr": 0.18, "mdd": -0.12 },
        "test": null
      },
      "guardrail_checks": {
        "num_trades": 45,
        "exposure_ratio": 0.65,
        "annual_turnover": 12
      },
      "anomaly_flags": []
    },
    "all_trials_count": 50,
    "convergence_trial": 35,
    "search_coverage": 0.007
  },
  
  "environment": {
    "code_version": "git:abc123def",
    "python_version": "3.11.5",
    "optuna_version": "3.4.0",
    "random_seed": 42,
    "splitter_version": "chronological_v1",
    "cost_model_version": "simple_oneway_v1"
  },
  
  "engine_health": {
    "is_valid": true,
    "warnings": [],
    "data_quality": {
      "missing_ratio": 0.001,
      "outlier_count": 3
    }
  }
}
```

### 9.2 단계별 manifest (v2 추가)

```
⚠️ Test 봉인 원칙에 따라 단계별로 manifest가 다름
```

| 단계 | stage | metrics.test | 설명 |
|------|-------|--------------|------|
| 튜닝 중 | `tuning` | `null` | Test 미계산 |
| Gate 1 통과 | `gate1_passed` | `null` | Test 미계산 |
| Gate 2 통과 | `gate2_passed` | `null` | Test 미계산 |
| Gate 3 (최종) | `final` | `{sharpe, cagr, mdd}` | Test 계산됨 |

### 9.3 생존편향/배당 처리

| 항목 | 필드 | 설명 |
|------|------|------|
| 유니버스 버전 | `universe_version` | ETF 목록 스냅샷 날짜 |
| 유니버스 소스 | `universe_source` | KRX, Yahoo 등 |
| 상장폐지 처리 | `delisted_handling` | `exclude_from_start`: 처음부터 제외, `include_until_delist`: 상폐 전까지 포함 |
| 생존편향 | `survivorship_bias` | `point_in_time`: 해당 시점 존재 ETF만 사용 |
| 가격 유형 | `price_type` | `adj_close`: 수정 종가 (배당/분할 반영) |
| 배당 처리 | `dividend_handling` | `total_return`: 배당 재투자 가정 |

---

## 10. 누수 방지 체크리스트

### 10.1 신호 계산 vs 체결 시점

| 항목 | 올바른 처리 | 잘못된 처리 (누수) |
|------|------------|-------------------|
| 신호 계산 | T일 종가 기준 | T일 장중 데이터 사용 |
| 체결 시점 | T+1일 시가 또는 종가 | T일 종가 (신호와 동시) |
| 가격 참조 | 체결 시점 가격 | 신호 시점 가격 |

### 10.2 결측치 처리

| 항목 | 올바른 처리 | 잘못된 처리 (누수) |
|------|------------|-------------------|
| Forward Fill | 과거 값으로 채움 | 미래 값으로 채움 |
| 결측 구간 | 거래 중단 또는 제외 | 보간으로 미래 정보 사용 |

### 10.3 체크리스트 (구현 시 확인)

```markdown
## 누수 방지 체크리스트

### 신호/체결
- [ ] 신호는 T일 종가 기준으로 계산하는가?
- [ ] 체결은 T+1일 시가(또는 종가)로 하는가?
- [ ] 체결 가격이 신호 시점 가격과 분리되어 있는가?

### 데이터 처리
- [ ] 결측치는 ffill(과거 값)로만 채우는가?
- [ ] 보간(interpolate)을 사용하지 않는가?
- [ ] 표준화/정규화는 Train 기간 통계만 사용하는가?

### Split
- [ ] Split이 시간 순서(chronological)인가?
- [ ] 랜덤 분할을 사용하지 않는가?
- [ ] Val/Test 기간이 최소 6개월 이상인가?

### 지표
- [ ] 이동평균/RSI 등이 미래 데이터를 참조하지 않는가?
- [ ] 순위 계산이 해당 시점까지만 사용하는가?

### 리밸런싱
- [ ] 리밸런싱 결정과 실행이 분리되어 있는가?
- [ ] 실행은 결정 익영업일인가?

### 유니버스
- [ ] Point-in-time 유니버스를 사용하는가?
- [ ] 상장폐지 ETF가 미래 정보로 제외되지 않는가?
```

---

## 11. 파라미터 스키마 설계

### 11.1 스키마 표준 필드

```yaml
variable_schema:
  key: string                    # 고유 식별자 (예: ma_period)
  label_ko: string               # 한글 라벨 (예: 이동평균 기간)
  category: enum                 # trend | momentum | risk | market | execution
  enabled_default: boolean       # 기본 활성화 여부
  
  type: enum                     # int | float | bool | enum
  range:
    min: number
    max: number
  step: number
  distribution: enum             # uniform | loguniform | categorical
  unit: enum                     # days | decimal | none
  
  dependency:                    # 의존성 (선택)
    requires: string[]           # 이 변수가 켜져 있어야 의미 있음
    condition: string            # 조건식 (예: "rsi_period > 0")
  
  constraints:                   # 제약 조건 (선택)
    - expression: string         # 예: "rsi_oversold < rsi_overbought"
      message: string
  
  recommended_by_lookback:       # 룩백별 추천 범위
    3M: { min: number, max: number }
    6M: { min: number, max: number }
    12M: { min: number, max: number }
  
  notes:
    strategic_meaning: string    # 전략적 의미
    risk_warning: string         # 리스크/부작용
    interaction: string[]        # 상호작용 변수
```

### 11.2 활성 변수 (3개)

```yaml
ma_period:
  key: ma_period
  label_ko: 이동평균 기간
  category: trend
  enabled_default: true
  type: int
  range: { min: 20, max: 200 }
  step: 10
  unit: days
  recommended_by_lookback:
    3M: { min: 20, max: 60 }
    6M: { min: 40, max: 120 }
    12M: { min: 60, max: 200 }
  notes:
    strategic_meaning: 추세 판단 기준. 짧으면 민감(휩쏘↑), 길면 둔감(지연↑)
    risk_warning: 3M 룩백에서 MA=200은 데이터 부족으로 무의미
    interaction: [stop_loss]

rsi_period:
  key: rsi_period
  label_ko: RSI 기간
  category: momentum
  enabled_default: true
  type: int
  range: { min: 5, max: 30 }
  step: 1
  unit: days
  recommended_by_lookback:
    3M: { min: 5, max: 14 }
    6M: { min: 7, max: 21 }
    12M: { min: 10, max: 30 }
  notes:
    strategic_meaning: 모멘텀 강도 측정. 짧으면 과민, 길면 둔감
    risk_warning: RSI 5는 노이즈에 취약, 30은 신호 지연
    interaction: [rsi_overbought, rsi_oversold]

stop_loss:
  key: stop_loss
  label_ko: 손절 비율
  category: risk
  enabled_default: true
  type: float
  range: { min: -0.20, max: -0.05 }
  step: 0.01
  unit: decimal
  recommended_by_lookback:
    3M: { min: -0.10, max: -0.05 }
    6M: { min: -0.15, max: -0.07 }
    12M: { min: -0.20, max: -0.10 }
  notes:
    strategic_meaning: 손실 제한. 타이트하면 휩쏘 손절↑, 넓으면 큰 손실 허용
    risk_warning: -5%는 변동성 높은 ETF에서 빈번한 손절 유발
    interaction: [volatility_filter, ma_period]
```

---

## 12. UI/UX 변경안

### 12.1 튜닝 설정 패널

```
┌─────────────────────────────────────────────────────────────────────────┐
│  튜닝 설정                                      [범위 기반 자동 탐색]   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                         │
│  📅 백테스트 기간                                                       │
│  ┌──────────────┐    ┌──────────────┐                                   │
│  │ 2024-01-01   │ ~  │ 2025-12-31   │  (24개월)                         │
│  └──────────────┘    └──────────────┘                                   │
│                                                                         │
│  📊 룩백 기간 (멀티 선택 시 min() 결합)                                │
│  [3개월 ✓] [6개월 ✓] [12개월 ✓]                                        │
│                                                                         │
│  ⚙️ Split 설정                                                          │
│  Train: 70% │ Val: 15% (최소 6개월) │ Test: 15% (최소 6개월)           │
│  ⚠️ Chronological 분할 (시간 순서 강제)                                │
│                                                                         │
│  💰 거래비용 (기본 적용, 편도 기준)                                     │
│  수수료: 0.015% │ 슬리피지: 0.1%                                        │
│                                                                         │
│  🛡️ 가드레일                                                            │
│  최소 거래: 30회 │ 최소 노출: 30% │ 최대 회전율: 연 24회               │
│                                                                         │
│  📊 탐색 커버리지: 0.7% (50 trials / 6,750 조합)                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 결과 테이블 (이상치 감지 포함)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  튜닝 결과 (Val 기준 정렬)                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                                         │
│  ⚠️ 선택 기준은 Val 성과입니다. Test는 Gate 통과 후 공개.              │
│                                                                         │
│  ┌────┬────┬────┬───────┬────────┬────────┬──────┬───────┬──────────┐  │
│  │ #  │ MA │RSI │ SL(%) │ Train  │  Val   │ Test │ 거래수│ 상태     │  │
│  ├────┼────┼────┼───────┼────────┼────────┼──────┼───────┼──────────┤  │
│  │ 1  │ 60 │ 14 │ -10%  │  2.1   │  1.5   │  🔒  │  45   │ ✅ 정상  │  │
│  │ 2  │ 80 │ 12 │  -8%  │  1.9   │  1.3   │  🔒  │  38   │ ✅ 정상  │  │
│  │ 3  │ 40 │ 21 │ -15%  │  2.5   │  0.2   │  🔒  │  12   │ 🟡 표본↓ │  │
│  │ 4  │ 30 │  5 │  -5%  │  6.0   │ -0.5   │  🔒  │  52   │ 🔴 Sharpe│  │
│  └────┴────┴────┴───────┴────────┴────────┴──────┴───────┴──────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 13. 리스크 / 트레이드오프

| 설계 결정 | 장점 | 단점/리스크 | 완화 방안 |
|-----------|------|-------------|----------|
| **Test 봉인** | 과적합 방지 | 사용자 불편 | Live 승격 게이트 |
| **Val 기준 선택** | 일반화 성능 중시 | Val 노이즈 | 미니 Walk-Forward |
| **최소 6개월 규칙** | 노이즈 감소 | 짧은 데이터 사용 불가 | 4개월 예외 (경고) |
| **min() 결합** | 안정성 극대화 | 보수적 성과 | mean-k*std 옵션 |
| **가드레일** | 비정상 결과 제거 | 일부 유효 결과 탈락 | 임계값 조정 가능 |
| **비용 기본 적용** | 현실적 평가 | 비용 없는 비교 불가 | 비용 0 옵션 (비권장) |
| **캐시** | 계산 시간 절약 | 메모리 사용 증가 | LRU 캐시 |
| **Live 게이트** | 신뢰도 높은 후보만 | 복잡한 프로세스 | UI 자동화 |

---

## 14. 다음 액션 (구현 우선순위)

### Phase 0: 즉시 적용 (1~2일)

1. **단위 통일 적용**
   - 엔진 내부: 소수로 통일
   - UI: % 표시 변환 함수 적용

2. **Test 봉인 UI 적용**
   - 결과 테이블에서 Test 컬럼 🔒 표시

3. **Objective 함수 변경**
   - suggest_params → run_backtest(params) 흐름
   - 가드레일 추가
   - 비용 기본 적용

### Phase 1: 단기 (1주)

4. **지표 정의 코드 적용**
   - num_trades, exposure_ratio, annual_turnover 산식 통일

5. **이상치 감지 레이더**
   - Sharpe/CAGR/표본수 기반 경고 배지

6. **캐시 구현**
   - run_cache_key 기반 캐싱

### Phase 2: 중기 (2~3주)

7. **Live 승격 게이트 구현**
   - Gate 1: Val Top-N
   - Gate 2: Walk-Forward 안정성
   - Gate 3: Test 공개

8. **미니 Walk-Forward 구현**
   - 윈도우 생성기 (거래일 스냅 포함)
   - 안정성 점수 계산

9. **run_manifest v3 저장**
   - 생존편향/배당 처리 항목 포함

---

## 부록: 용어 정리

| 용어 | 설명 |
|------|------|
| **Chronological Split** | 시간 순서대로 분할 (과거→미래) |
| **Guardrail** | 비정상 결과를 걸러내는 최소/최대 조건 |
| **Exposure Ratio** | 전체 기간 중 포지션 보유일 비율 |
| **Annual Turnover** | 연간 매매 회전율 |
| **min() 결합** | 멀티 룩백 점수 중 최솟값 사용 |
| **Live 승격 게이트** | Val → WF → Test 순차 검증 프로세스 |
| **이상치 레이더** | 비정상 결과 자동 감지 시스템 |
| **Point-in-time** | 해당 시점에 존재하던 데이터만 사용 |
| **Total Return** | 배당 재투자 가정 수익률 |
