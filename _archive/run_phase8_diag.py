import sys
import os
import logging
from datetime import date
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from extensions.backtest.runner import BacktestRunner
from app.services.backtest_service import BacktestParams
from core.data.filtering import get_filtered_universe  # Ensure this matches actual usage
from infra.data.loader import load_price_data # Functional import as seen in Service

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_diagnostic(ma, rsi, sl, regime_long, regime_short, hold):
    logger.info(f"Setting up Diagnostic Run (Phase 8)...")
    logger.info(f"Params: MA={ma}, RSI={rsi}, SL={sl}, RegimeLong={regime_long}, RegimeShort={regime_short}, Hold={hold}")

    # 1. Setup Universe
    universe_codes = ["005930"] # Samsung Electronics as Proxy
    
    # 2. Load Data
    start_date = date(2022, 1, 1)
    end_date = date(2023, 12, 31)
    
    logger.info("Loading Price Data...")
    price_data = load_price_data(universe_codes, start_date, end_date)
    
    logger.info("Loading Market Data (069500)...")
    try:
        from pykrx import stock
        market_df = stock.get_market_ohlcv_by_date(
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
            "069500"
        )
        # Normalize Market Data
        market_df = market_df.rename(columns={
            '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'
        })
        market_df.index.name = 'date'
        # Ensure lowercase columns
        market_df.columns = [c.lower() for c in market_df.columns]
    except Exception as e:
        logger.error(f"Failed to load market data: {e}")
        return

    # 3. Setup Runner
    runner = BacktestRunner(
        initial_capital=10_000_000,
        max_positions=5,
        enable_defense=True,
    )

    init_weights = {code: 0.0 for code in universe_codes}

    # 4. Execute
    # Phase 8 Params: regime_ma_long, short_ma_period(=ma_period)
    result = runner.run(
        price_data=price_data,
        target_weights=init_weights,
        start_date=start_date,
        end_date=end_date,
        market_index_data=market_df,
        ma_period=regime_short, # Used as Short MA for both Strategy & Regime Cross
        rsi_period=rsi,
        stop_loss=-sl, # Pass as negative
        regime_ma_period=200, # Legacy/Unused
        min_regime_hold_days=hold,
        regime_ma_long=regime_long, # Phase 8 Param
    )

    metrics = result.get("metrics", {})
    yearly = metrics.get("yearly_stats", {})
    
    report_lines = []
    report_lines.append("\n" + "="*50)
    report_lines.append("PHASE 8 DIAGNOSTIC REPORT")
    report_lines.append("="*50)
    
    report_lines.append(f"[Run Configuration]")
    report_lines.append(f"MA(Short): {regime_short}, RSI: {rsi}, Hold: {hold}")
    report_lines.append(f"Regime(Long): {regime_long}, SL: {-sl}") 
    report_lines.append("-" * 30)
    
    report_lines.append(f"[Overall Metrics]")
    report_lines.append(f"Total Return: {metrics.get('total_return', 0.0):.2f}%")
    report_lines.append(f"CAGR: {metrics.get('cagr', 0.0):.2f}%")
    report_lines.append(f"MDD: {metrics.get('max_drawdown', 0.0):.2f}%")
    report_lines.append(f"Sharpe: {metrics.get('sharpe_ratio', 0.0):.2f}")
    report_lines.append(f"Exposure Ratio: {metrics.get('exposure_ratio', 0.0):.2f}")
    report_lines.append("-" * 30)
    
    report_lines.append(f"[Regime Diagnostics]")
    report_lines.append(f"Total Switches: {metrics.get('regime_switch_count', 'N/A')}")
    report_lines.append(f"Total Locked: {metrics.get('regime_locked_count', 'N/A')}")
    report_lines.append("-" * 30)
    
    report_lines.append(f"[Yearly Breakdown]")
    for year in sorted(yearly.keys()):
        stats = yearly[year]
        report_lines.append(f"Year {year}: Return {stats['return']:.2f}%, MDD {stats['mdd']:.2f}%")
    report_lines.append("="*50 + "\n")
    
    content = "\n".join(report_lines)
    print(content)
    # Append to report file
    with open("phase8_report.txt", "a", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    # Top 1 from Phase 8 Tuning
    # Params: {'ma_period': 50, 'rsi_period': 17, 'stop_loss_pct': 0.08, 'regime_ma_long': 140, 'min_regime_hold_days': 15}
    run_diagnostic(ma=50, rsi=17, sl=0.08, regime_long=140, regime_short=50, hold=15)
