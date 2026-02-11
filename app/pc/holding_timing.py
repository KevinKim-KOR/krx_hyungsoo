
import json
import datetime
from pathlib import Path
import pandas as pd
import numpy as np
import sys

# Add project root to path to import param_search logic
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(BASE_DIR))

from app.pc.param_search import load_data, fetch_history

# Config
OUTPUT_DIR = BASE_DIR / "reports" / "pc" / "holding_timing" / "latest"
SNAPSHOT_DIR = BASE_DIR / "reports" / "pc" / "holding_timing" / "snapshots"
PORTFOLIO_PATH = BASE_DIR / "state" / "portfolio" / "latest" / "portfolio_latest.json"
PARAMS_PATH = BASE_DIR / "state" / "strategy_params" / "latest" / "strategy_params_latest.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None

def calculate_signal(ticker, history_rows, params):
    """
    Calculate signal based on strategy params.
    Returns: (signal, reason, lookback_events, metrics)
    """
    # Strategy Logic (Simplified from P100/P135)
    # 1. Momentum: Return > 0 (or some threshold) / Rank (relative)
    # 2. Volatility: Low is better
    # 3. MA rules? Params have 'lookbacks'.
    
    # Params structure:
    # "lookbacks": { "momentum_period": 20, "volatility_period": 14 }
    # "decision_params": { "entry_threshold": 0.02, "exit_threshold": -0.03 }
    
    lookbacks = params.get("lookbacks", {})
    mom_period = lookbacks.get("momentum_period", 20)
    vol_period = lookbacks.get("volatility_period", 14)
    
    decisions = params.get("decision_params", {})
    entry_th = decisions.get("entry_threshold", 0.02)
    exit_th = decisions.get("exit_threshold", -0.03)
    
    # Create DF
    df = pd.DataFrame(history_rows)
    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    
    if len(df) < mom_period + 10:
        return "UNKNOWN", "Insufficient Data", [], {}
        
    # Calculate Indicators
    # Momentum: Simple Return or MA distance? 
    # Param Search used pct_change(mom_period).
    df['mom'] = df['close'].pct_change(mom_period)
    
    # Volatility
    df['daily_ret'] = df['close'].pct_change()
    df['vol'] = df['daily_ret'].rolling(vol_period).std() * np.sqrt(252)
    
    # MA (Moving Average) - Standard Trend Follow
    # Let's assume MA20 if not specified, or use mom_period as MA window?
    # Usually "Momentum Strategy" uses MA filter (e.g. Price > MA).
    ma_window = mom_period 
    df['ma'] = df['close'].rolling(ma_window).mean()
    
    # Current Signal
    last = df.iloc[-1]
    
    metrics = {
        "momentum_val": float(last['mom']) if not pd.isna(last['mom']) else 0.0,
        "volatility_val": float(last['vol']) if not pd.isna(last['vol']) else 0.0,
        "price": float(last['close']),
        "ma": float(last['ma']) if not pd.isna(last['ma']) else 0.0
    }
    
    # Signal Logic
    # this is a "Visual Analysis", so we show what the system *would* think.
    # BUY if Mom > Entry AND Price > MA
    # SELL if Mom < Exit OR Price < MA (Stop loss?)
    
    signal = "HOLD"
    reason = "Neutral"
    
    # Score? 
    # If Mom > Entry: Positive
    # If Mom < Exit: Negative
    
    if metrics['momentum_val'] > entry_th and metrics['price'] > metrics['ma']:
        signal = "BUY"
        # Friendly Reason
        mom_pct = metrics['momentum_val'] * 100
        reason = f"Strong Momentum (+{mom_pct:.1f}%) & Price above MA"
    elif metrics['momentum_val'] < exit_th:
        signal = "SELL"
        mom_pct = metrics['momentum_val'] * 100
        reason = f"Momentum Weakened ({mom_pct:.1f}%)"
    elif metrics['price'] < metrics['ma']:
        # Optional: Trend filter exit
        # signal = "SELL" # strict
        # reason = "Price fell below trend (MA)"
        pass
        
    # Lookback Events (Last 60 days)
    events = []
    lb_start = df.index[-min(len(df), 60)]
    sub = df.loc[lb_start:]
    
    # Detect signal changes
    prev_sig = "UNKNOWN"
    
    for dt, row in sub.iterrows():
        m = row['mom']
        p = row['close']
        ma = row['ma']
        
        s = "HOLD"
        r = ""
        
        if pd.isna(m) or pd.isna(ma):
            continue
            
        if m > entry_th and p > ma:
            s = "BUY"
            r = "Entry Signal"
        elif m < exit_th:
            s = "SELL"
            r = "Exit Signal (Mom)"
        elif p < ma:
            # s = "SELL" 
            # r = "Trend Broken"
            pass
            
        if s != prev_sig and s != "HOLD":
            events.append({
                "date": dt.strftime('%Y-%m-%d'),
                "signal": s,
                "reason": r,
                "price": float(p)
            })
            prev_sig = s
            
    # Next Trigger Hint
    # Calculate price/mom needed to flip signal
    hint = "N/A"
    if signal == "HOLD" or signal == "SELL":
        # What is needed for BUY?
        # Need Mom > entry_th. 
        # Approx price needed: Close = Old_Close * (1+Entry)
        # Using mom calculation: (P_now / P_old) - 1 > Entry
        # P_now > P_old * (1+Entry)
        p_old = df['close'].iloc[-(mom_period+1)] if len(df) > mom_period else 0
        if p_old > 0:
            target = p_old * (1 + entry_th)
            hint = f"Buy if Price > {target:.0f} (Mom > {entry_th:.1%})"
    elif signal == "BUY":
        # What is needed for SELL?
        # Mom < exit_th
        p_old = df['close'].iloc[-(mom_period+1)]
        if p_old > 0:
            target = p_old * (1 + exit_th)
            hint = f"Sell if Price < {target:.0f} (Mom < {exit_th:.1%})"

    return signal, reason, events, metrics, hint

def main():
    print("Starting Holding Timing Analysis...")
    
    # 1. Load State
    portfolio = load_json(PORTFOLIO_PATH)
    params = load_json(PARAMS_PATH)
    
    if not portfolio:
        print("No portfolio found. Skipping.")
        return
    
    if not params:
        print("No strategy params found. Using defaults/empty.")
        # fallback is tricky without params.
        return

    # 2. Fetch Data
    # Parse Holdings (Support Dict or List structure for robustness)
    raw_holdings = portfolio.get("holdings", {})
    # If it's under 'balance', try that (legacy/standard support)
    if not raw_holdings and "balance" in portfolio:
        raw_holdings = portfolio["balance"].get("holdings", {})

    target_holdings = []
    if isinstance(raw_holdings, dict):
        # Convert dict {ticker: info} to list [{ticker, ...}]
        for t, info in raw_holdings.items():
            entry = info.copy()
            entry["ticker"] = t
            target_holdings.append(entry)
    elif isinstance(raw_holdings, list):
        target_holdings = raw_holdings
    
    tickers = [h["ticker"] for h in target_holdings]
    
    # Force fetch for these tickers to ensure freshness
    print(f"Fetching data for {len(tickers)} holdings...")
    
    data_map = load_data() # Loads P135 universe + cache
    
    for t in tickers:
        if t not in data_map:
            print(f"Fetching extra: {t}")
            hist = fetch_history(t, days=300)
            if hist:
                data_map[t] = hist
                
    # 3. Analyze
    results = []
    p_params = params.get("params", {})
    
    for h in target_holdings:
        t = h["ticker"]
        qty = h.get("quantity", 0) # Note: file uses 'quantity', not 'qty'
        avg_price = h.get("avg_price", 0)
        
        entry = {
            "ticker": t,
            "qty": qty,
            "avg_price": avg_price,
            "data_source": "CACHE" if t in data_map else "MISSING"
        }
        
        if t in data_map:
            rows = data_map[t]
            if rows:
                current_price = rows[-1]["close"]
                entry["current_price"] = current_price
                
                sig, reason, events, metrics, hint = calculate_signal(t, rows, p_params)
                entry["current_signal"] = sig
                entry["signal_reason"] = reason
                entry["lookback_events"] = events
                entry["metrics"] = metrics
                entry["next_trigger_hint"] = hint
            else:
                entry["current_signal"] = "UNKNOWN"
                entry["signal_reason"] = "Empty Data"
        else:
            entry["current_signal"] = "UNKNOWN"
            entry["signal_reason"] = "Data Missing"
            
        results.append(entry)
        
    # 4. Save
    output_data = {
        "schema": "HOLDING_TIMING_V1",
        "asof": datetime.datetime.utcnow().isoformat() + "Z",
        "portfolio_ref": "portfolio_latest.json",
        "params_ref": "strategy_params_latest.json",
        "holdings": results
    }
    
    json_str = json.dumps(output_data, indent=2, ensure_ascii=False)
    (OUTPUT_DIR / "holding_timing_latest.json").write_text(json_str, encoding="utf-8")
    
    # Snapshot
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (SNAPSHOT_DIR / f"holding_timing_{ts}.json").write_text(json_str, encoding="utf-8")
    
    print(f"Analysis saved. {len(results)} holdings processed.")

if __name__ == "__main__":
    main()
