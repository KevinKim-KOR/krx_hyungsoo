# Dynamic Risk Calibration Summary

- asof: 2026-04-02T23:33:29+09:00
- universe_mode: dynamic_etf_market
- study: tune_quick_dynamic_etf_market_5axis_dynamic_risk_v1
- search_space: 5axis_dynamic_risk_v1
- seed: 42

## Best Params
```json
{
  "momentum_period": 44,
  "volatility_period": 19,
  "entry_threshold": 0.04,
  "stop_loss": -0.04000000000000001,
  "max_positions": 2
}
```

## Performance
| Metric | Value |
|---|---|
| CAGR | 144.30% |
| MDD | 6.25% |
| Sharpe | 3.8215 |

## Targets
- MDD < 10%: 예
- CAGR > 15%: 예

## Conclusion: **PROMOTION_READY**