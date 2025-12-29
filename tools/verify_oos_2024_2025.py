import sys
import os
import json
import logging
from datetime import date
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.production_config import PROD_STRATEGY_CONFIG
from app.services.backtest_service import BacktestService, BacktestParams
from core.data.filtering import get_filtered_universe

# Configure logging (suppress info to keep stdout clean for JSON)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_verification():
    # 1. Load Universe
    logger.warning("Loading Universe...")
    universe = get_filtered_universe()
    if not universe:
        logger.warning("Cache empty. Falling back to Config Universe.")
        universe = PROD_STRATEGY_CONFIG.get("universe_codes", [])
    
    logger.warning(f"Universe Size: {len(universe)}")

    # [Added] Ensure Data is Up-to-Date
    from infra.data.loader import load_price_data
    from pykrx import stock
    import pandas as pd
    
    def ensure_data_uptodate(universe_codes):
        logger.warning(f"Checking data freshness for {len(universe_codes)} codes...")
        cache_dir = Path("data/cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        updated_count = 0
        
        for code in universe_codes:
            cache_path = cache_dir / f"{code}.parquet"
            need_update = False
            last_date = None
            
            if cache_path.exists():
                try:
                    df = pd.read_parquet(cache_path)
                    if not df.empty and hasattr(df.index, 'max'): # Check if index is date
                         # Check index type
                         if isinstance(df.index, pd.DatetimeIndex):
                             last_date = df.index.max().date()
                         elif 'date' in df.columns:
                             last_date = pd.to_datetime(df['date']).max().date()
                         else:
                             # Try reset index if "Date" or "날짜" in index names
                             if df.index.name in ['Date', 'date', '날짜']:
                                 last_date = df.index.max().date()
                except:
                    pass
            
            today = date.today()
            # If no data or older than 5 days, fetch
            if last_date is None or (today - last_date).days > 5:
                need_update = True
                
            if need_update:
                try:
                    start_str = "20200101" # Fetch enough history
                    end_str = today.strftime("%Y%m%d")
                    logger.info(f"Updating {code} -> {end_str}")
                    
                    df_new = stock.get_market_ohlcv_by_date(start_str, end_str, code)
                    if df_new is not None and not df_new.empty:
                        # Standardize columns
                        df_new = df_new.rename(columns={
                            "시가": "open", "고가": "high", "저가": "low", 
                            "종가": "close", "거래량": "volume", "거래대금": "value"
                        })
                        # Ensure nice column names (lowercase)
                        df_new.index.name = "date"
                        df_new = df_new.reset_index() # make date a column
                        
                        # Save
                        df_new.to_parquet(cache_path, engine='pyarrow')
                        updated_count += 1
                except Exception as e:
                    logger.warning(f"Failed to update {code}: {e}")
        
        logger.warning(f"Data Update Complete. Updated {updated_count} files.")

    ensure_data_uptodate(universe)

    service = BacktestService(save_history=False)
    
    periods = {
        "2024": (date(2024, 1, 1), date(2024, 12, 31)),
        "2025": (date(2025, 1, 1), date.today())
    }
    
    results = {}

    for label, (start_dt, end_dt) in periods.items():
        logger.warning(f"Running {label} ({start_dt} ~ {end_dt})...")
        
        # PROD Config Mapping
        # Stop Loss: 0.12 -> 12.0 (Service expects percentage int/float before division)
        # Note: Tuning Runner multiplied by 100. Service divides by 100. 
        # So we pass percentage value (e.g. 12.0 for 12%).
        stop_loss_val = PROD_STRATEGY_CONFIG["stop_loss_pct"] * 100 
        
        params = BacktestParams(
            start_date=start_dt,
            end_date=end_dt,
            ma_period=PROD_STRATEGY_CONFIG["ma_short_period"],
            rsi_period=PROD_STRATEGY_CONFIG["rsi_period"],
            stop_loss=stop_loss_val,
            initial_capital=PROD_STRATEGY_CONFIG["initial_capital"],
            max_positions=PROD_STRATEGY_CONFIG["max_positions"],
            enable_defense=True,
            regime_ma_long=PROD_STRATEGY_CONFIG["regime_ma_long"],
            min_regime_hold_days=PROD_STRATEGY_CONFIG["min_regime_hold_days"],
            adx_period=PROD_STRATEGY_CONFIG["adx_period"],
            adx_threshold=PROD_STRATEGY_CONFIG["adx_threshold"],
            universe_codes=universe
        )

        try:
            res = service.run(params)
            
            # Exposure calculation: days with market value > 0 / total trading days
            # BacktestResult has 'exposure_ratio' but let's double check or use it directly
            exposure = res.exposure_ratio
            
            results[label] = {
                "return": res.total_return,
                "mdd": res.max_drawdown,
                "sharpe": res.sharpe_ratio,
                "exposure": exposure,
                "trades": res.num_trades
            }
        except Exception as e:
            logger.error(f"Error in {label}: {e}")
            results[label] = {
                "return": 0.0,
                "mdd": 0.0,
                "sharpe": 0.0,
                "exposure": 0.0,
                "trades": 0,
                "error": str(e)
            }

    # Write JSON to file
    with open("oos_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Results saved to oos_results.json")

if __name__ == "__main__":
    run_verification()
