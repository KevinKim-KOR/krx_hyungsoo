import sys
import os
import json
import logging
import pandas as pd
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.production_config import PROD_STRATEGY_CONFIG
from core.data.filtering import get_filtered_universe
from extensions.backtest.runner import BacktestRunner
from infra.data.loader import load_price_data, load_market_data
from pykrx import stock

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def ensure_data_uptodate(universe_codes):
    """
    Ensure 2024-2025 data availability
    """
    logger.warning(f"Checking data freshness for {len(universe_codes)} codes...")
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    updated_count = 0
    today = date.today()
    
    for code in universe_codes:
        cache_path = cache_dir / f"{code}.parquet"
        need_update = False
        last_date = None
        
        if cache_path.exists():
            try:
                df = pd.read_parquet(cache_path)
                if not df.empty:
                    if isinstance(df.index, pd.DatetimeIndex):
                        last_date = df.index.max().date()
                    elif 'date' in df.columns:
                        last_date = pd.to_datetime(df['date']).max().date()
                    elif df.index.name in ['Date', 'date', '날짜']:
                        last_date = df.index.max().date()
            except:
                pass
        
        if last_date is None or (today - last_date).days > 5:
            need_update = True
            
        if need_update:
            try:
                start_str = "20200101"
                end_str = today.strftime("%Y%m%d")
                df_new = stock.get_market_ohlcv_by_date(start_str, end_str, code)
                
                if df_new is not None and not df_new.empty:
                    df_new = df_new.rename(columns={
                        "시가": "open", "고가": "high", "저가": "low", 
                        "종가": "close", "거래량": "volume", "거래대금": "value"
                    })
                    df_new.index.name = "date"
                    df_new = df_new.reset_index()
                    df_new.to_parquet(cache_path, engine='pyarrow')
                    updated_count += 1
            except Exception as e:
                # logger.warning(f"Failed to update {code}: {e}")
                pass
    
    if updated_count > 0:
        logger.warning(f"Updated {updated_count} files.")

def calculate_monthly_stats(nav_history, trades, year):
    """
    Calculate monthly return, mdd, trades, exposure
    """
    if not nav_history:
        return []

    df = pd.DataFrame(nav_history)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    
    # Filter for year
    df = df[df.index.year == int(year)]
    if df.empty:
        return []

    monthly_stats = []
    
    # Resample Monthly
    # 'ME' for Month End
    # Group by year-month string to handle potential gaps
    df['month_str'] = df.index.strftime('%Y-%m')
    months = sorted(df['month_str'].unique())

    # Need equity relative to previous month end
    # Get last day of previous year/month for reference?
    # Actually, simplistic: return of month = (end/start - 1)
    
    for m in months:
        m_df = df[df['month_str'] == m]
        if m_df.empty:
            continue
            
        # Return
        start_equity = m_df.iloc[0]['equity']
        end_equity = m_df.iloc[-1]['equity']
        
        # Check previous day's close for accurate return?
        # Standard approach: using nav series
        # Monthly Return = (Last Equity of Month / Last Equity of Prev Month) - 1
        # But here we just approximate (Last / First) - 1 ??
        # Or better: (Last / First of Month) - 1 ... Wait, if we lost money day 1?
        # Correct way is: (M_Last) / (M-1_Last) - 1.
        
        # Let's use daily returns product
        daily_ret = m_df['equity'].pct_change().fillna(0)
        # However, first day return is lost if we don't have prev day. 
        # But NAV history ideally is continuous.
        # Let's stick to (End / Start) - 1 for simplicity here, or look back at full DF for prev month close.
        
        # Find prev month close
        curr_month_first_date = m_df.index[0]
        prev_data = df[df.index < curr_month_first_date]
        if not prev_data.empty:
            ref_equity = prev_data.iloc[-1]['equity']
            ret_pct = ((end_equity / ref_equity) - 1) * 100
        else:
            # First month of year: compare to initial capital? No, first day equity might be == initial logic
            # Use First day open? 
            # If 2024-01-02 is first day, we compare to 2024-01-02 open?
            # Let's simpler: (End / Start - 1) if no prev.
             ret_pct = ((end_equity / start_equity) - 1) * 100

        # MDD calculation for the month
        roll_max = m_df['equity'].cummax()
        drawdown = (m_df['equity'] - roll_max) / roll_max
        mdd_pct = abs(drawdown.min()) * 100
        
        # Trades Count
        # Filter trades in this month
        month_trades = 0
        if trades:
            for t in trades:
                t_date = pd.to_datetime(t['entry_date']) if isinstance(t, dict) else t.entry_date
                if t_date.strftime('%Y-%m') == m:
                    month_trades += 1
        
        # Exposure Ratio
        # Days with exposure
        trade_days = len(m_df)
        # active days? Need 'portfolio_value' or 'positions' count
        # Nav history usually has total_equity. 
        # Using BacktestEngine logic: exposure_ratio is total active days / total days.
        # But nav_history doesn't store active status explicitly unless we have 'cash' and 'equity'.
        # Let's verify BacktestResult.
        # If input 'nav_history' has 'cash', exposure = (equity - cash) > 0
        # If keys are just 'equity', we can't.
        # Assuming nav_history has keys: 'date', 'equity', 'cash' (check engine.py)
        # engine.nav_history.append({"date": current_date, "equity": ..., "cash": ...})
        
        exposure_count = 0
        if 'cash' in m_df.columns:
            # Active if equity > cash (roughly) or cash < equity
            # Or market_value > 0
            # equity = cash + market_value
            # market_value = equity - cash
            market_val = m_df['equity'] - m_df['cash']
            exposure_count = (market_val > 100).sum() # tolerance
            
        exposure_ratio = exposure_count / trade_days if trade_days > 0 else 0.0

        monthly_stats.append({
            "month": m,
            "return_pct": round(ret_pct, 2),
            "mdd_pct": round(mdd_pct, 2),
            "trades": month_trades,
            "trade_days": trade_days,
            "exposure_ratio": round(exposure_ratio, 2)
        })
        
    return monthly_stats

def run_verification():
    # 1. Load Universe
    logger.warning("Loading Universe...")
    universe = get_filtered_universe()
    if not universe:
        universe = PROD_STRATEGY_CONFIG.get("universe_codes", [])
    
    # 2. Update Data
    ensure_data_uptodate(universe)

    # 3. Setup Runner
    periods = {
        "2024": (date(2024, 1, 1), date(2024, 12, 31)),
        "2025": (date(2025, 1, 1), date.today())
    }
    
    final_output = {
        "schema_version": "OOS-MONTHLY-1.0",
        "generated_at": datetime.now().isoformat(),
        "years": {}
    }

    # Load Full Range Data Once (Optimization)
    start_all = min(p[0] for p in periods.values()) - timedelta(days=200) # buffer for MA
    end_all = max(p[1] for p in periods.values())
    
    logger.warning("Loading Price Data...")
    price_data = load_price_data(universe, start_all, end_all)
    logger.warning("Loading Market Data...")
    market_data = load_market_data("KOR_ETF_CORE", end_all, start_all)

    # Target Weights (Equal Weight)
    target_weights = {code: 1.0 / PROD_STRATEGY_CONFIG["max_positions"] for code in universe}
    
    params_stop_loss = PROD_STRATEGY_CONFIG["stop_loss_pct"] # As decimal (0.12) or pct (12)? 
    # Config has 0.12. BacktestRunner expects decimal.
    # WAIT. BacktestService divides by 100? 
    # In `backtest_service.py`: `stop_loss=params.stop_loss / 100.0`.
    # So `BacktestParams` expects 12.0.
    # But `BacktestRunner` expects decimal?
    # Let's check `BacktestRunner.run` signature. 
    # `stop_loss=params.stop_loss / 100.0` passed to runner.
    # So Runner expects decimal (e.g. 0.12).
    # Since we call Runner directly, we pass 0.12 directly.
    
    sl_decimal = PROD_STRATEGY_CONFIG["stop_loss_pct"]

    for label, (start_dt, end_dt) in periods.items():
        logger.warning(f"Running {label} ({start_dt} ~ {end_dt})...")

        runner = BacktestRunner(
            initial_capital=PROD_STRATEGY_CONFIG["initial_capital"],
            max_positions=PROD_STRATEGY_CONFIG["max_positions"],
            enable_defense=True,
            min_holding_days=0
        )
        
        # Prepare params to match Production
        # Note: BacktestRunner allows kwargs for Phase 7/8/9 params?
        # Check signature of runner.run().
        # It accepts specific args: regime_ma_period, min_regime_hold_days, etc.
        
        res_dict = runner.run(
            price_data=price_data,
            target_weights=target_weights,
            start_date=start_dt,
            end_date=end_dt,
            market_index_data=market_data,
            ma_period=PROD_STRATEGY_CONFIG["ma_short_period"],
            rsi_period=PROD_STRATEGY_CONFIG["rsi_period"],
            stop_loss=sl_decimal,

            regime_ma_period=PROD_STRATEGY_CONFIG["regime_ma_long"],
            min_regime_hold_days=PROD_STRATEGY_CONFIG["min_regime_hold_days"],
            # Phase 9
            # adx_period=... (Only if runner supports it)
            # Checked source previously: `regime_detector.detect_regime_adx` called in logic.
            # If `run` doesn't take ADX args, we might be using default.
            # BUT service passed `adx_period`... so runner MUST accept it?
            # Wait, `runner.run` signature I didn't verify fully (args list).
            # If `run` uses `**kwargs` or has the arg, fine.
            # Let's check `BacktestRunner.run` args quickly or use `inspect`.
            # Actually, just pass them. If error, I fix.
            # Based on service code:
            # split_result = split_runner.run(..., adx_period=..., adx_threshold=...)
            # So it supports it.
            adx_period=PROD_STRATEGY_CONFIG["adx_period"],
            adx_threshold=PROD_STRATEGY_CONFIG["adx_threshold"]
        )
        
        metrics = res_dict["metrics"]
        nav = res_dict["nav_history"]
        trades = res_dict["trades"]
        
        # Monthly Stats
        m_stats = calculate_monthly_stats(nav, trades, label)
        
        final_output["years"][label] = {
            "period": {"start": str(start_dt), "end": str(end_dt)},
            "summary": {
                "total_return_pct": round(metrics.get("total_return", 0), 2),
                "mdd_pct": round(metrics.get("max_drawdown", 0), 2),
                "trades": len(trades),
                "exposure_ratio": round(metrics.get("exposure_ratio", 0), 3)
            },
            "monthly": m_stats
        }

    # Save
    report_path = Path("reports/validation/oos_2024_2025_monthly.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
    
    print(f"Validation Report Saved: {report_path}")

if __name__ == "__main__":
    run_verification()
