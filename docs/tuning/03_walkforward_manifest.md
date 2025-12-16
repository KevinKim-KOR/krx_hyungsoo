# 튜닝/검증 체계 설계 - Walk-Forward 및 Manifest (v2.1)

> 관련 문서: [00_overview.md](./00_overview.md)

---

## 8. 미니 Walk-Forward 설계

### 8.1 윈도우 생성 규칙

```
⚠️ 절대 규칙: 모든 윈도우는 전체 기간(start_date ~ end_date) 내에서만 생성.
   end_date를 초과하는 윈도우는 생성하지 않는다.

⚠️ 절대 규칙: 윈도우 경계 스냅은 start/end 규칙을 분리한다.
   - start 경계(구간 시작일): 휴장일이면 다음 영업일로 스냅(snap_start)
   - end 경계(구간 종료일): 휴장일이면 이전 영업일로 스냅(snap_end)
```

**윈도우 생성 알고리즘 (v2.1 수정):**
```python
def generate_windows(start_date, end_date, train_months, val_months, test_months,
                     stride_months, trading_calendar):
    """
    전체 기간 내에서만 윈도우 생성.
    v2.1: start는 snap_start(다음 영업일), end는 snap_end(이전 영업일)로 분리 적용.
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
        
        # v2.1: 시작일은 snap_start, 종료일은 snap_end
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

### 9.1 스키마 (v2.1 수정)

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
    
    "split": {
      "method": "chronological",
      "target_ratios": { "train": 0.70, "val": 0.15, "test": 0.15 },
      "min_val_months": 6,
      "min_test_months": 6,

      "applied": {
        "train_months": 12,
        "val_months": 6,
        "test_months": 6,
        "train_range": ["2024-01-02", "2024-12-31"],
        "val_range":   ["2025-01-02", "2025-06-30"],
        "test_range":  ["2025-07-01", "2025-12-30"]
      }
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

### 9.2 단계별 manifest (v2.1 수정)

```
⚠️ Test 봉인 원칙에 따라 단계별로 manifest가 다름
   튜닝(run_id가 tuning_… 인 경우)에는 test를 기록하지 않는다.
   Gate 3 통과 후 "final_…" run_id에서만 test가 들어간다.
```

| 단계 | stage | metrics.test | 설명 |
|------|-------|--------------|------|
| 튜닝 중 | `tuning` | `null` | Test 미계산 |
| Gate 1 통과 | `gate1_passed` | `null` | Test 미계산 |
| Gate 2 통과 | `gate2_passed` | `null` | Test 미계산 |
| Gate 3 (최종) | `final` | `{sharpe, cagr, mdd}` | Test 계산됨 |

**튜닝 manifest 예시:**
```json
"metrics": {
  "train": { "sharpe": 2.1, "cagr": 0.25, "mdd": -0.08 },
  "val":   { "sharpe": 1.5, "cagr": 0.18, "mdd": -0.12 },
  "test":  null
}
```

**Gate 3 이후 final manifest에서만:**
```json
"metrics": {
  "train": { "sharpe": 2.1, "cagr": 0.25, "mdd": -0.08 },
  "val":   { "sharpe": 1.5, "cagr": 0.18, "mdd": -0.12 },
  "test":  { "sharpe": 1.8, "cagr": 0.20, "mdd": -0.10 }
}
```

### 9.3 생존편향/배당 처리

| 항목 | 필드 | 설명 |
|------|------|------|
| 유니버스 버전 | `universe_version` | ETF 목록 스냅샷 날짜 |
| 유니버스 소스 | `universe_source` | KRX, Yahoo 등 |
| 상장폐지 처리 | `delisted_handling` | `exclude_from_start`: 처음부터 제외, `include_until_delist`: 상폐 전까지 포함 |
| 생존편향 | `survivorship_bias` | `point_in_time`: 해당 시점 존재 ETF만 사용 |
| 가격 유형 | `price_type` | `adj_close`: 수정 종가 (배당/분할 반영) |
| 배당 처리 | `dividend_handling` | `total_return`: 배당 재투자 가정 |
