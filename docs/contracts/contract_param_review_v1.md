# Contract: Param Review V1

## Goal
Provide a human-readable, decision-support report for selecting strategy parameters.
It compares the CURRENT strategy parameters against the TOP CANDIDATES from the latest Param Search (P135).

## Schema: `PARAM_REVIEW_V1`

### File Path
- **Latest**: `reports/pc/param_review/latest/param_review_latest.json`
- **Snapshot**: `reports/pc/param_review/snapshots/param_review_YYYYMMDD_HHMMSS.json`

### JSON Structure
```json
{
  "schema": "PARAM_REVIEW_V1",
  "asof": "2025-02-08T14:30:00Z",
  "baseline": {
    "params": { ... }, // Current Strategy Params
    "fingerprint": "a1b2c3d4...",
    "metrics": { ... } // If available (e.g. from recent backtest or unknown)
  },
  "candidates": [
    {
      "rank": 1,
      "score": 85,
      "params": { ... },
      "metrics": {
        "cagr": 0.15,
        "mdd": -0.10,
        "sharpe": 1.2
      },
      "analysis": {
        "why_good": "Stable returns in low volatility.",
        "risk_factor": "May underperform in strong bull market due to high volatility weight.",
        "regime_hint": "DEFENSIVE"
      },
      "tags": ["STABLE", "LOW_DRAWDOWN"]
    },
    ...
  ],
  "recommendation": {
    "candidate_rank": 1,
    "level": "SOFT", // SOFT, NEUTRAL, STRONG
    "reason": "Top score with significantly lower MDD than baseline."
  },
  "questions": [
    "Q: Why is Candidate 1 better than Baseline?",
    "Q: What happens if volatility spikes?"
  ]
}
```

## Constraints
- **Read-Only Generation**: Generating the report does NOT change any state.
- **Human Decision**: The "Apply" action is separate and manual.
- **No Auto-Publish**: Applying a candidate only updates `strategy_params_latest.json`.

## Versioning
- **V1**: Initial version.
