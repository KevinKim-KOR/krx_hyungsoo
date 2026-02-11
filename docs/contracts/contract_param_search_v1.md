# Contract: Param Search V1 (P135)

## Overview
PC-based parameter recommendation engine.
- **Role**: Recommends `strategy_params` based on recent market data.
- **Constraint**: No external execution, no broker calls. Safe to run anytime.
- **Output**: `PARAM_SEARCH_V1` JSON.

## Schema: `PARAM_SEARCH_V1`

```json
{
  "schema": "PARAM_SEARCH_V1",
  "asof": "2026-02-08T15:00:00Z",
  "universe": ["069500", "229200", "114800", "122630"],
  "data_source_chain": ["LOCAL_CACHE", "NAVER_FETCH"],
  "search_space": {
    "lookback_days": [60, 90, 120],
    "momentum_window": [20, 40, 60],
    "vol_window": [14, 20, 30],
    "top_k": [4],
    "weights": [
       {"mom": 1.0, "vol": 0.0},
       {"mom": 0.7, "vol": 0.3},
       {"mom": 0.5, "vol": 0.5}
    ]
  },
  "results": [
    {
      "rank": 1,
      "params": {
        "lookbacks": { "momentum_period": 40, "volatility_period": 20 },
        "weights": { "momentum": 0.7, "volatility": 0.3 }
        // ... mapped to strategy_params structure
      },
      "metrics": {
        "avg_forward_return": 0.052,
        "hit_rate": 0.65,
        "sample_count": 12,
        "max_drawdown_proxy": -0.02
      },
      "score_0_100": 85
    }
  ],
  "winner": {
    "rank": 1,
    "params": { ... },
    "reason": "Highest risk-adjusted score"
  }
}
```

## Logic
1.  **Data Loading**:
    -   Load `state/cache/etf_history_cache.json`.
    -   If insufficient (< 150 days), fetch from Naver Finance (https://finance.naver.com).
    -   Update cache if fetched.
2.  **Simulation**:
    -   Rolling window sampling (Step: 5 days).
    -   For each window: Calculate hypothetical return of Top K picks.
3.  **Scoring**:
    -   Simple weighted score of Return, Hit Rate, Stability.
    -   Clamp 0-100.
4.  **Preservation**:
    -   Save to `reports/pc/param_search/latest/param_search_latest.json`.
    -   Save snapshot.
