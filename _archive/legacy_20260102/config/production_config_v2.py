# Production Strategy Config V2 (Phase 9 Upgrade)
# [IMMUTABLE POLICY]
# V1 (production_config.py) is the Frozen Baseline. DO NOT MODIFY V1.
# V2 extends V1 with RSI Thresholds required for Phase9Executor.

PROD_STRATEGY_CONFIG = {
    # --- V1 Parameters (Inherited) ---
    "ma_short_period": 60,
    "rsi_period": 40,
    "regime_ma_long": 120,
    "min_regime_hold_days": 30,
    "adx_period": 30,
    "adx_threshold": 17.5,
    "stop_loss_pct": 0.12,
    "initial_capital": 10000000,
    "max_positions": 5,
    "universe_codes": ["005930", "000660"],

    # --- V2 Parameters (New) ---
    "rsi_buy_threshold": 50,  # Dip Buy Criteria
    "rsi_sell_threshold": 70  # Overbought Criteria
}
