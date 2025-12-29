import os
import sys
import logging
import pandas as pd
from datetime import date

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extensions.backtest.runner import BacktestRunner
from app.services.backtest_service import BacktestParams

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def run_diagnostic():
    # Load Universe
    try:
        from core.data.filtering import get_filtered_universe
        universe_codes = get_filtered_universe()
        logger.info(f"Loaded {len(universe_codes)} codes.")
    except Exception as e:
        logger.warning(f"Failed to load universe, using Mock: {e}")
        universe_codes = ["005930"]

    # Load Data (Need Market & Price Data)
    from infra.data.loader import load_price_data # Functional import as seen in Service
    # loader = DataLoader() # Removed
    
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
        market_df.index = pd.to_datetime(market_df.index)
        # Rename columns to standardized names
        market_df.rename(columns={
            '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'
        }, inplace=True)
        # Ensure lowercase
        market_df.columns = [c.lower() for c in market_df.columns]
    except Exception as e:
        logger.error(f"Failed to load market data: {e}")
        return

    # Runner Setup
    runner = BacktestRunner(
        initial_capital=10_000_000,
        max_positions=5,
        enable_defense=True,
    )
    
    # Params (Phase 7.3 Aggressive Winner)
    ma = 90
    rsi = 20
    sl = 0.06
    regime = 100
    hold = 19
    
    logger.info(f"Running Backtest: MA={ma}, RSI={rsi}, SL={sl}, Regime={regime}, Hold={hold}")
    
    # Target Weights (Simple equal weight for universe initially? No, Runner calculates weights)
    # Runner needs target_weights dict? No, Runner.run logic:
    # "target_weights: Dict[str, float] # 초기 비중 (필수)"
    # But usually Momentum Strategy *calculates* weights dynamically.
    # Ah, the Runner logic iterates dates and calls `_calculate_momentum_scores` and creates target weights.
    # But `target_weights` input to `run` is essentially the "Universe Definition" in current design?
    # Let's check `BacktestRunner.run` signature.
    # It takes `target_weights`.
    # In `BacktestService`, it passes `target_weights={code: 0.0 for code in universe}` as initialization.
    init_weights = {code: 0.0 for code in universe_codes}
    
    result = runner.run(
        price_data=price_data,
        target_weights=init_weights,
        start_date=start_date,
        end_date=end_date,
        market_index_data=market_df,
        ma_period=ma,
        rsi_period=rsi,
        stop_loss=sl, # 0.15 treated as -15% inside runner usually, wait. Runner default is -0.10.
        # If I pass 0.15, and Runner uses it as drawdown threshold (e.g. if drawdown <= stop_loss).
        # Drawdown is usually negative (e.g. -0.05).
        # So I should pass -0.15? Or does Runner negate it?
        # Runner: `if drawdown <= stop_loss:`
        # So stop_loss must be negative.
        # `BacktestService` passed `metrics.stop_loss / 100.0` (positive) -> wait
        # Service: `stop_loss=params.stop_loss / 100.0`. If params.sl is 15 -> 0.15.
        # Runner Default: `-0.10`.
        # Code in Runner: `stop_loss: float = -0.10`.
        # If I pass positive 0.15, `drawdown` (negative) <= 0.15 is ALWAYS TRUE.
        # So it triggers SL immediately! 
        # THIS MIGHT BE THE BUG.
        # User said Top 1 Param has `stop_loss_pct: 0.15`.
        # If Optuna optimizes `0.05 ~ 0.15` (positive), and it's passed as positive...
        # Then SL triggers every day?
        # BUT `BacktestService` might negate it?
        # Let's check `app/services/backtest_service.py` -> `create_backtest`.
        # No negation seen in snippet.
        # Let's check if Optuna suggests NEGATIVE values? No `0.05, 0.15`.
        # CHECK `extensions/tuning/runner.py`:
        # `stop_loss=params.stop_loss / 100.0`
        # Wait, if `params.stop_loss` is in %, e.g. 10.
        # Then passed is 0.1.
        # If Runner expects negative...
        # Let's check `Runner.run`: `if drawdown <= stop_loss`.
        # If drawdown is -0.01, and stop_loss is 0.1. -0.01 <= 0.1 is True. SOLD.
        # So SL triggers on ANY small loss (or even profit if logic is `<`).
        # This explains why Sharpe is low!
        # I MUST PASS NEGATIVE STOP LOSS.
        # `-0.15` for 15%.
        # Diagnostic should use correct value.
        
        regime_ma_period=regime,
        min_regime_hold_days=hold,
    )
    
    metrics = result.get("metrics", {})
    yearly = metrics.get("yearly_stats", {})
    
    report_lines = []
    report_lines.append("\n" + "="*50)
    report_lines.append("PHASE 7.2 DIAGNOSTIC REPORT (Runner Direct)")
    report_lines.append("="*50)
    
    report_lines.append(f"[Run Configuration]")
    report_lines.append(f"MA: {ma}, RSI: {rsi}, Regime: {regime}, Hold: {hold}")
    report_lines.append(f"StopLoss (Effective): {-sl}") 
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
    with open("phase7_2_final_report.txt", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    run_diagnostic()
