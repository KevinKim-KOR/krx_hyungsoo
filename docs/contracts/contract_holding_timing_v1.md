# Contract: Holding Timing V1 (P136)

## Overview
PC-based holding analysis engine.
- **Role**: Analyzes current holdings against market data to determine signals and timing.
- **Constraint**: No execution. Only analysis.
- **Output**: `HOLDING_TIMING_V1` JSON.

## Schema: `HOLDING_TIMING_V1`

```json
{
  "schema": "HOLDING_TIMING_V1",
  "asof": "2026-02-08T17:00:00Z",
  "portfolio_ref": "portfolio_latest.json",
  "params_ref": "strategy_params_latest.json",
  "holdings": [
    {
      "ticker": "069500",
      "qty": 10,
      "avg_price": 35000,
      "current_price": 36000,
      "data_source": "NAVER_FETCH",
      "current_signal": "HOLD",
      "signal_reason": "Momentum Rank 1, Volatility Low",
      "next_trigger_hint": "Sell if drops below 34000 (Exit Threshold)",
      "lookback_events": [
        {"date": "2026-01-15", "signal": "BUY", "reason": "Golden Cross"},
        {"date": "2026-02-01", "signal": "HOLD", "reason": "Trend continued"}
      ],
      "metrics": {
          "momentum_score": 0.8,
          "volatility_score": 0.2
      }
    }
  ]
}
```

## Logic
1.  **Load State**:
    -   `state/portfolio/latest/portfolio_latest.json` (Source of Truth for Holdings).
    -   `state/strategy_params/latest/strategy_params_latest.json` (Logic).
2.  **Data Fetch**:
    -   Cache/Naver (Same chain as P135).
3.  **Calculation**:
    -   Apply strategy indicators (Momentum, Volatility) over lookback period.
    -   Re-evaluate BUY/SELL logic at each time step (simplified).
4.  **Output**:
    -   `reports/pc/holding_timing/latest/holding_timing_latest.json`
