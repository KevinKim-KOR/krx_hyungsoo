# 튜닝/검증 체계 설계 - 목적함수 및 승격 게이트 (v2.1)

> 관련 문서: [00_overview.md](./00_overview.md)

---

## 6. 목적함수(Objective) 설계

### 6.0 반환 자료구조 (BacktestRunResult)

```python
@dataclass
class BacktestRunResult:
    metrics: dict           # {'train': Metrics, 'val': Metrics, 'test': Metrics|None}
    guardrail_checks: dict  # {'num_trades': int, 'exposure_ratio': float, 'annual_turnover': float}
    logic_checks: dict      # {'rsi_scale_days': int, 'rsi_scale_events': int}  # v2.1 추가
```

```
⚠️ backtest()는 BacktestMetrics를 반환하고,
   run_backtest_for_tuning / run_backtest_for_final은 BacktestRunResult를 반환한다.
   - result.metrics['train'] / ['val'] / ['test']
   - result.guardrail_checks (num_trades, exposure_ratio, annual_turnover)
```

### 6.1 Objective 흐름

```
⚠️ trial은 Optuna 객체, params는 파라미터 dict.
   run_backtest_for_tuning()은 params를 받는다. trial을 직접 넘기지 않는다.

⚠️ for lb in lookbacks: 루프는 룩백별로 다른 데이터를 사용해야 합니다.
   lookback_months=lb를 인자로 전달하거나, period를 룩백별로 잘라서 넘겨야 합니다.
   그렇지 않으면 3회 반복되는 동일 백테스트가 실행됩니다 ("가짜 반복" 현상).

⚠️ lookback_months는 **백테스트 입력 데이터 슬라이스(룩백 절단)**에 직접 영향을 준다.
   즉, 같은 period로 3번 도는 게 아님.
```

**권장 구현 방식:**
```python
# run_backtest_for_tuning 내부에서 period를 룩백별로 계산
result = run_backtest_for_tuning(
    params=params,
    start_date=start_date,
    end_date=end_date,
    lookback_months=lb,    # 룩백 절단 → split 적용은 내부에서
    split_config=split_config,
    costs=DEFAULT_COSTS
)
```

**올바른 흐름 (v2.1: Test 봉인 강제):**
```python
def objective(trial, lookbacks=[3, 6, 12], start_date=None, end_date=None, split_config=None):
    """
    v2.1 절대 규칙:
    - objective에서는 Test를 계산하지 않는다.
    - 반드시 run_backtest_for_tuning()만 호출한다.
    - period는 run_backtest_for_tuning 내부에서 룩백별로 계산된다.
    """
    params = {
        'ma_period': trial.suggest_int('ma_period', 20, 200, step=10),
        'rsi_period': trial.suggest_int('rsi_period', 5, 30),
        'stop_loss': trial.suggest_float('stop_loss', -0.20, -0.05, step=0.01),
    }

    scores = []
    for lb in lookbacks:
        # ✅ period는 내부에서 룩백별로 계산됨
        result = run_backtest_for_tuning(
            params=params,
            start_date=start_date,
            end_date=end_date,
            lookback_months=lb,
            split_config=split_config,
            costs=DEFAULT_COSTS
        )

        if not check_guardrails(result):
            return -999

        score = calculate_score(result)
        scores.append(score)

    return min(scores)
```

### 6.2 가드레일 체크 함수

```python
def check_guardrails(result: BacktestRunResult):
    """
    가드레일 통과 여부 확인
    하나라도 실패하면 False
    """
    g = result.guardrail_checks
    return (
        g['num_trades'] >= 30 and
        g['exposure_ratio'] >= 0.30 and
        g['annual_turnover'] <= 24
    )
```

### 6.3 점수 계산 함수

```python
def calculate_score(result: BacktestRunResult):
    """
    Val 기반 점수 계산 (MDD 페널티 포함)
    """
    val = result.metrics['val']
    
    # MDD 페널티: 15% 초과 시
    mdd_threshold = 0.15
    mdd_penalty = max(0, abs(val.mdd) - mdd_threshold) * 10
    
    return val.sharpe - mdd_penalty
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
# 튜닝 단계:
result = run_backtest_for_tuning(
    params=params,
    start_date=start_date,
    end_date=end_date,
    lookback_months=lookback_months,
    split_config=split_config,
    costs=DEFAULT_COSTS
)

# Gate3 이후 최종 보고서:
result = run_backtest_for_final(
    params=params,
    start_date=start_date,
    end_date=end_date,
    lookback_months=lookback_months,
    split_config=split_config,
    costs=DEFAULT_COSTS
)
```

```
⚠️ 튜닝 단계에서는 반드시 run_backtest_for_tuning(),
   Gate3 이후 최종 보고서에서는 run_backtest_for_final()을 사용해야 합니다.
   (backtest()는 내부 구현 함수로만 사용)
```

---

## 7. Live 승격 게이트

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
| Gate 1 | **MDD 일관성** | `abs(MDD_val) <= max(abs(MDD_train) * 1.2, 0.10)` |
| Gate 1 | **Logic Check** | `rsi_scale_days >= 10` (RSI가 실제로 영향을 줬는지) |
| Gate 2 | 안정성 점수 | stability_score ≥ 1.0 |
| Gate 2 | 승률 | win_rate ≥ 60% |
| Gate 3 | 최종 확인 | 사용자 수동 선택 |

### 7.2.1 MDD 일관성 Gate (강화)

```
⚠️ MDD는 음수이므로 비교는 abs(MDD)로 한다.
   Train MDD가 너무 작으면(신내림) 상대 비교가 무력화되므로
   **최소 허용 임계값(MIN_TOLERANCE)**을 함께 적용한다.
```

```python
MIN_TOLERANCE = 0.10  # 10% 최소 허용 임계값 (하한선)

def check_mdd_consistency(result: BacktestRunResult) -> bool:
    """
    MDD 일관성 Gate: 상대 + 최소 허용 조건
    - Train MDD가 -3%여도 Val MDD가 -15%면 통과 안 됨
    - MIN_TOLERANCE는 Train MDD가 너무 작을 때 최소 허용 범위를 보장
    """
    train_mdd = abs(result.metrics['train'].mdd)
    val_mdd = abs(result.metrics['val'].mdd)
    
    # Train MDD가 작아도 최소 10%까지는 허용
    threshold = max(train_mdd * 1.2, MIN_TOLERANCE)
    return val_mdd <= threshold
```

### 7.2.2 Logic Check (RSI 실효성)

```
⚠️ rsi_period만 튜닝하고 cutoff가 고정이면,
   특정 rsi_period에서 "비중 조절이 거의 안 일어나는" 파라미터가 나올 수 있다.
```

```python
MIN_RSI_SCALE_DAYS = 10  # RSI가 실제로 영향을 준 최소 일수

def check_logic_rsi(result: BacktestRunResult) -> bool:
    """
    RSI가 실제로 전략에 영향을 줬는지 확인
    """
    logic = result.logic_checks
    return logic.get('rsi_scale_days', 0) >= MIN_RSI_SCALE_DAYS
```

**RSI cutoff 자동 조정 옵션 (탐색 공간 유지):**
```python
# rsi_period에 따라 cutoff 자동 조정
rsi_overbought = 70 + (20 - rsi_period) * 1  # 예시 식
rsi_oversold = 30 - (20 - rsi_period) * 1
```

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
