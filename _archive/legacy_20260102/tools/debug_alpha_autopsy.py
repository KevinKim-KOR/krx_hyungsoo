import argparse
import sys
import logging
import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from typing import Dict, Any, List

# Setup Utils
sys.path.append(os.getcwd())
try:
    from infra.data.loader import load_daily_price, load_trading_calendar
except ImportError:
    # Fallback for direct execution if needed
    pass

# Config Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("AlphaAutopsy")

class AlphaAutopsy:
    def __init__(self, run_id: str):
        self.stats = {
            "rows_loaded": 0,
            "rows_after_date_filter": 0,
            "rows_after_nan_drop": 0,
            "cond_maps_buy": 0,
            "cond_rsi_filter": 0,
            "cond_entry_signal": 0,
            "first_date": None,
            "last_date": None,
            "debug_trace": [] # First 5 rows details
        }
        self.run_dir = os.path.join("data", "debugging", run_id)
        os.makedirs(self.run_dir, exist_ok=True)

    def calculate_indicators(self, df: pd.DataFrame, params: Dict[str, Any]):
        ma_period = params.get('ma_period', 60)
        rsi_period = params.get('rsi_period', 14)
        
        close = df['close']
        
        # MA
        ma = close.rolling(window=ma_period).mean()
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Momentum
        momentum = close.pct_change(20)
        
        # MAPS Score
        ma_score = ((close - ma) / ma * 100).fillna(0)
        rsi_score = (50 - rsi) / 10
        momentum_score = momentum * 100
        
        maps = ma_score + rsi_score + momentum_score
        
        df = df.copy()
        df['ma'] = ma
        df['rsi'] = rsi
        df['maps'] = maps
        return df

    def run(self, code: str, start: datetime, end: datetime, params: Dict[str, Any]):
        logger.info(f"Target: {code}, {start.date()} ~ {end.date()}")
        logger.info(f"Params: {params}")
        
        # 1. Load Data
        df = load_daily_price(code, start, end)
        self.stats["rows_loaded"] = len(df)
        if df.empty:
            logger.error("No data loaded.")
            self.save_report()
            return
            
        # Column Normalization (Audit Fix)
        # Loader might typically use KR columns if coming from pykrx directly or simple cache
        # We ensure 'close' exists
        rename_map = {
            '종가': 'close',
            '시가': 'open',
            '고가': 'high',
            '저가': 'low',
            '거래량': 'volume'
        }
        df = df.rename(columns=rename_map)
        
        # Lowercase all columns
        df.columns = [c.lower() for c in df.columns]
        
        if 'close' not in df.columns:
            logger.error(f"Missing 'close' column. Available: {list(df.columns)}")
            self.stats["error"] = "Missing close column"
            self.save_report()
            return

        self.stats["first_date"] = str(df.index.min())
        self.stats["last_date"] = str(df.index.max())
        self.stats["rows_after_date_filter"] = len(df)

        # 2. Indicators
        df = self.calculate_indicators(df, params)
        valid_df = df.dropna()
        self.stats["rows_after_nan_drop"] = len(valid_df)
        
        if valid_df.empty:
            logger.error("All rows dropped after indicator calculation (Warmup issue?)")
            self.save_report()
            return

        # 3. Signal Check
        maps_buy_threshold = params.get('maps_buy_threshold', 1.0)
        rsi_overbought = params.get('rsi_overbought', 70)
        
        count_maps = 0
        count_rsi = 0
        count_entry = 0
        
        trace = []
        
        for idx, row in valid_df.iterrows():
            maps_val = row['maps']
            rsi_val = row['rsi']
            
            is_maps_buy = maps_val >= maps_buy_threshold
            is_rsi_ok = rsi_val < rsi_overbought
            
            if is_maps_buy: count_maps += 1
            if is_rsi_ok: count_rsi += 1 # This is filter, so if True it passes
            
            if is_maps_buy and is_rsi_ok:
                count_entry += 1
            
            if len(trace) < 5:
                trace.append({
                    "date": str(idx),
                    "close": row['close'],
                    "maps": round(maps_val, 2),
                    "rsi": round(rsi_val, 2),
                    "is_maps_buy": bool(is_maps_buy),
                    "is_rsi_ok": bool(is_rsi_ok)
                })
        
        self.stats["cond_maps_buy"] = count_maps
        self.stats["cond_rsi_filter"] = count_rsi 
        self.stats["cond_entry_signal"] = count_entry
        self.stats["debug_trace"] = trace
        
        self.save_report()
        
        # Save CSV sample
        valid_df.to_csv(os.path.join(self.run_dir, "autopsy_sample.csv"))

    def save_report(self):
        report_path = os.path.join(self.run_dir, "alpha_debug.json")
        with open(report_path, "w") as f:
            json.dump(self.stats, f, indent=4)
        print(f"REPORT_SAVED: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", type=str, required=True)
    parser.add_argument("--start", type=str, required=True)
    parser.add_argument("--end", type=str, required=True)
    parser.add_argument("--params-preset", type=str, default="lax")
    args = parser.parse_args()
    
    # Simple preset mapping for debugging
    params = {
        "ma_period": 20, 
        "rsi_period": 14, 
        "maps_buy_threshold": -5.0, # Very Lax
        "rsi_overbought": 80
    }
    
    if args.params_preset == "lax":
        # Ensure these match what we used in trials
        pass
        
    start_dt = datetime.strptime(args.start, "%Y-%m-%d")
    end_dt = datetime.strptime(args.end, "%Y-%m-%d")
    
    autopsy = AlphaAutopsy(f"debug_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}")
    autopsy.run(args.code, start_dt, end_dt, params)
