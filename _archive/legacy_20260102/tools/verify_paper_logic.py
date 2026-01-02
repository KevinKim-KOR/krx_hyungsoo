import sys
import os
import logging
from datetime import date, datetime, timedelta
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.production_config import PROD_STRATEGY_CONFIG
from core.strategy.market_regime_detector import MarketRegimeDetector
from extensions.backtest.runner import BacktestRunner
from infra.data.loader import load_price_data 

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_logic():
    logger.info("="*50)
    logger.info("PHASE 10: LOGIC VERIFICATION (PAPER TRADING PREP)")
    logger.info("="*50)
    
    # 1. Load Config
    cfg = PROD_STRATEGY_CONFIG
    logger.info(f"Loaded Config: {cfg}")
    
    # 2. Setup Date (Today)
    today = date.today()
    start_date = today - timedelta(days=365*2) # 2 Years history for MA/ADX
    logger.info(f"Date Range: {start_date} ~ {today}")
    
    # 3. Load Data
    universe = cfg['universe_codes']
    logger.info(f"Loading Price Data for {universe}...")
    price_data = load_price_data(universe, start_date, today)
    
    logger.info("Loading Market Data (069500)...")
    try:
        from pykrx import stock
        market_df = stock.get_market_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            today.strftime("%Y%m%d"),
            "069500"
        )
        market_df = market_df.rename(columns={
            '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'
        })
        market_df.index.name = 'date'
        market_df.columns = [c.lower() for c in market_df.columns]
        
        # Latest Data Check
        last_dt = market_df.index[-1].date()
        logger.info(f"Market Data Loaded. Latest Date: {last_dt}")
        
    except Exception as e:
        logger.error(f"Failed to load market data: {e}")
        return

    # 4. Initialize Detector
    detector = MarketRegimeDetector(
        enable_regime_detection=True
    )
    
    # 5. Execute Detection (Simulation)
    # Use the logic directly from detector to verify state
    # detect_regime_adx(market_data, current_date, long_ma, short_ma, adx_p, adx_t)
    
    logger.info("-" * 30)
    logger.info("[REGIME DETECTION Logic Check]")
    
    regime, confidence, is_golden, is_chop = detector.detect_regime_adx(
        market_df, 
        today,
        long_ma_period=cfg['regime_ma_long'],
        short_ma_period=cfg['ma_short_period'],
        adx_period=cfg['adx_period'],
        adx_threshold=cfg['adx_threshold']
    )
    
    logger.info(f"Date: {today}")
    logger.info(f"Raw Regime: {regime}")
    logger.info(f"Confidence: {confidence}")
    logger.info(f"Golden Cross: {is_golden}")
    logger.info(f"Is Chop (ADX < {cfg['adx_threshold']}): {is_chop}")
    
    # 6. Apply Priority (Runner Logic Simulation)
    final_regime = regime
    if is_chop:
        final_regime = 'bear' # Force Cash
        logger.warning(">> CHOP DETECTED! Force Risk-Off (Cash)")
    else:
        logger.info(f">> Normal Regime Logic applied: {final_regime}")
        
    logger.info("-" * 30)
    
    # 7. ADX Value Check (Internal Debug)
    # Re-calc manually to see value
    adx_val = detector._calculate_adx(market_df.tail(cfg['adx_period']*5), cfg['adx_period'])
    logger.info(f"Calculated ADX Value: {adx_val:.2f}")

    logger.info("="*50)
    logger.info("Verification Complete.")

if __name__ == "__main__":
    verify_logic()
