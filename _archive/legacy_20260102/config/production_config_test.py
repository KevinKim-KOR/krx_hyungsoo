# PROD_STRATEGY_CONFIG in config/production_config.py
# Simulating missing key error
PROD_STRATEGY_CONFIG = {
    # "ma_short_period": 60,  <-- COMMENTED OUT TO TRIGGER KEYERROR
    "rsi_period": 40,
    "regime_ma_long": 120,
    "min_regime_hold_days": 30,
    "adx_period": 30,
    "adx_threshold": 17.5,
    "stop_loss_pct": 20.0, # Using % as default? No, previous was 0.12?
    "initial_capital": 10000000,
    "max_positions": 5,
    "universe_codes": ["005930", "000660"]
}
