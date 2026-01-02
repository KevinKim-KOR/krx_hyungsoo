# Production Strategy Config (Freeze Phase 10)
# This file contains the "Gatekeeper Approved" parameters.
# Any change here requires Gatekeeper promotion.

PROD_STRATEGY_CONFIG = {
    "ma_short_period": 60,
    "rsi_period": 40,
    "regime_ma_long": 120,
    "min_regime_hold_days": 30,
    "adx_period": 30,
    "adx_threshold": 17.5,
    "stop_loss_pct": 0.12, # Unit: Ratio or PCT? Gatekeeper check HC1 says 3.0abs diff. V3 JSON says 0.12. BacktestRunner used /100.
                           # The tool diagnoser uses it as is?
                           # Let's match what was in the file before. It was 0.12.
    "initial_capital": 10000000,
    "max_positions": 5,
    "universe_codes": ["005930", "000660"]
}
