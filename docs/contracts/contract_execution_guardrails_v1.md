# Contract: Execution Guardrails V1

## Schema: `EXECUTION_GUARDRAILS_V1`

### Purpose
Enforce safety limits on manual execution to prevent operator errors (fat-finger, excessive trading, risk disregard).

### Logic
The `Execution Prep` generator validates the `Order Plan Export` against these guardrails.

### Fields

#### `limits`
- `max_orders_per_day` (int): Maximum number of orders allowed in a single day (e.g., 50).
- `max_total_notional_ratio` (float): Max ratio of Total Order Value / Portfolio Value (e.g., 0.3 for 30%).
- `max_single_order_ratio` (float): Max ratio of Single Order Value / Portfolio Value (e.g., 0.1 for 10%).
- `min_cash_reserve_ratio` (float): Minimum Cash / Portfolio Value to maintain (e.g., 0.05 for 5%).
- `allow_buy` (bool): If false, only SELL orders are allowed (e.g., in Bear Market or Risk Off).

#### `market_checks`
- `market_session` (enum): `OPEN`, `CLOSED`, `UNKNOWN`.
- `price_data_fresh` (bool): True if market data is up-to-date (within last 24h).

### Decisions (in `execution_prep`)
- **READY**: All checks passed.
- **WARN**: Minor limits approached or non-critical checks failed (e.g., price data slightly stale).
- **BLOCKED**: Critical limits exceeded (Notional, Cash Reserve) or Market Closed.

### Example JSON Fragment (inside Execution Prep)
```json
"guardrails": {
  "decision": "READY",
  "checks": {
    "total_notional_ratio": 0.15,
    "limit_total_notional_ratio": 0.3,
    "passed": true
  },
  "market": {
    "session": "OPEN",
    "fresh": true
  }
}
```
