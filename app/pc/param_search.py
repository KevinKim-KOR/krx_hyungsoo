
import json
import requests
import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd
import numpy as np

# Config
BASE_DIR = Path(__file__).parent.parent.parent
OUTPUT_DIR = BASE_DIR / "reports" / "pc" / "param_search" / "latest"
SNAPSHOT_DIR = BASE_DIR / "reports" / "pc" / "param_search" / "snapshots"
CACHE_DIR = BASE_DIR / "state" / "cache"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Universe (Fixed for now, or load from strategy params)
UNIVERSE = ["069500", "229200", "114800", "122630"] 

# Search Space
SEARCH_SPACE = {
    "lookback_days": [60, 90, 120, 150],
    "momentum_window": [20, 40, 60],
    "vol_window": [14, 20, 30],
    "top_k": [4], # Fixed to 4 as per current strategy constraint
    "weights": [
       {"mom": 1.0, "vol": 0.0},
       {"mom": 0.7, "vol": 0.3},
       {"mom": 0.5, "vol": 0.5}
    ]
}

def fetch_history(ticker: str, days: int = 200) -> List[Dict]:
    """
    Fetch history from Naver Finance (Unofficial)
    Returns list of dict: {date, close, ...} sorted by date asc
    """
    url = f"https://api.finance.naver.com/siseJson.naver?symbol={ticker}&requestType=1&startTime=20200101&endTime=20991231&timeframe=day"
    
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        
        # Naver returns: [["Date", "Open", "High", "Low", "Close", "Volume", "Foreign"], ...]
        # We need to parse it. 
        # Note: The format is slightly cleaner in "siseJson.naver" endpoint usually.
        # Let's use a simpler known endpoint or just parse carefully.
        # Actually, let's use the XML/HTML scraping fallback if JSON fails, but this JSON endpoint is common.
        
        # Checking format...
        # It usually returns clean CSV-like list of lists.
        # Header is: Date, Open, High, Low, Close, Volume, Foreign
        
        data = r.text.strip()
        # Parse manually roughly or use cleaner regex
        # It's actually a valid CSV/JSON array of arrays usually.
        # Let's try eval or strict parsing if it is valid python list literal (Naver sometimes does this).
        # Actually, let's use the dataframe approach if possible, but requests is safer.
        
        import ast
        try:
            raw_rows = ast.literal_eval(data)
        except:
             # Fallback parsing
             raw_rows = []
             
        # Columns: 0=Date, 4=Close
        # Filter header if present
        if len(raw_rows) > 0:
            # Check if first row is header (e.g. '날짜' or 'Date')
            # If 4th element is not a number, it's a header
            try:
                float(raw_rows[0][4])
            except (ValueError, TypeError):
                # First row is header, skip it
                raw_rows = raw_rows[1:]
             
        rows = []
        for r in raw_rows:
            # Date format: '20251021'
            d_str = str(r[0]).replace("-", "")
            close = float(r[4])
            rows.append({"date": d_str, "close": close})
            
        return rows[-days:]
        
    except Exception as e:
        print(f"[WARN] Failed to fetch {ticker}: {e}")
        return []

def load_data(days=250):
    cache_path = CACHE_DIR / "etf_history_cache.json"
    data = {}
    
    # Try Cache first
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            # convert to simple list
            for t, v in cached.items():
                if "prices" in v:
                    # simplify
                    prices = [{"date": p["date"], "close": p["close"]} for p in v["prices"]]
                    data[t] = prices
        except:
            pass
            
    # Check completeness
    needs_update = False
    for t in UNIVERSE:
        if t not in data or len(data[t]) < 150: # arbitrary threshold
            print(f"[INFO] Fetching {t}...")
            fetched = fetch_history(t, days=300)
            if fetched:
                data[t] = fetched
                needs_update = True
    
    # Update cache if we fetched
    if needs_update:
        # Save back to cache in format compatible with other tools if needed
        # Or just use internal format for this tool? 
        # Contract says "Update cache if fetched". Let's try to match structure roughly or just overwrite.
        # Simplest: create a new structure for param search cache or reuse 'etf_history_cache.json'
        # 'etf_history_cache.json' is used by 'generate_watchlist_candidates.py'.
        # We should respect its schema if we overwrite.
        # Schema: { ticker: { prices: [...], price: ..., change_pct: ..., data_source: ... } }
        new_cache = {}
        for t, rows in data.items():
            if not rows: continue
            last = rows[-1]
            prev = rows[-2] if len(rows) > 1 else last
            change_pct = (last["close"] / prev["close"] - 1) * 100
            
            # Reconstruct prices list
            # We only kept date/close, ideally we keep OHLCV. 
            # But fetch_history as implemented above only extracted close.
            # Fix fetch_history to extract all if we want to be nice to other tools.
            # For now, let's NOT overwrite the shared cache to avoid breaking other tools with partial data.
            # We will use "param_search_cache.json" instead.
            pass
            
        # Write to separate cache for safety
        (CACHE_DIR / "param_search_data_cache.json").write_text(json.dumps(data), encoding="utf-8")
        
    return data

def simulate(params, history_data):
    # params: {lookback, mom_win, vol_win, w_mom, w_vol}
    # return: {avg_return, hit_rate, ...}
    
    # 1. Align data
    # Create DF: index=date, columns=tickers
    df = pd.DataFrame()
    for t in UNIVERSE:
        if t not in history_data: continue
        rows = history_data[t]
        s = pd.Series({r["date"]: r["close"] for r in rows})
        df[t] = s
        
    df.sort_index(inplace=True)
    df.ffill(inplace=True)
    df.dropna(inplace=True)
    
    if len(df) < params["lookback_days"] + 20:
        return None
        
    # 2. Simulation Loop
    # Step: 5 days
    returns = []
    
    # We need at least lookback_days for first calculation
    # And then we look 'forward' N days (e.g. 5 days) for return
    forward_days = 5
    start_idx = params["lookback_days"]
    
    for i in range(start_idx, len(df) - forward_days, 5):
        # Slice for calculation
        # window: df.iloc[i-lookback : i]
        # target_date = df.index[i]
        
        # Calculate Scores
        sub = df.iloc[i-params["lookback_days"]:i]
        
        # Momentum: Return over mom_window
        mom_ret = sub.pct_change(params["momentum_window"]).iloc[-1]
        
        # Volatility: StdDev of daily returns over vol_window
        daily_ret = sub.pct_change()
        vol = daily_ret.tail(params["vol_window"]).std() * np.sqrt(252)
        
        # Scoring
        # Normalized? Simple rank?
        # Let's use simple z-score proxy or just raw weighted?
        # Config says simple weights.
        # mom_score = returns
        # vol_score = 1/vol (inverse)
        
        # To combine properly, rank them.
        mom_rank = mom_ret.rank(ascending=False)
        vol_rank = vol.rank(ascending=True) # Low vol = #1
        
        # Combined Rank (Lower is better)
        # score = w_mom * mom_rank + w_vol * vol_rank
        # This implementation interprets weights as importance.
        # But 'weights' in search space map to actual logic.
        # contract says {mom: 1.0, vol: 0.0}
        
        final_scores = {}
        for t in df.columns:
            m_r = mom_rank[t]
            v_r = vol_rank[t]
            score = params["weights"]["mom"] * m_r + params["weights"]["vol"] * v_r
            final_scores[t] = score
            
        # Pick Top K (lowest score)
        sorted_tickers = sorted(final_scores, key=final_scores.get)[:params["top_k"]]
        
        # Calculate Forward Return
        # Buy at close of i, sell at close of i+5
        # Equally weighted
        port_ret = 0
        for t in sorted_tickers:
            p_buy = df[t].iloc[i]
            p_sell = df[t].iloc[i+forward_days]
            r = (p_sell / p_buy) - 1.0
            port_ret += r
            
        port_ret /= len(sorted_tickers)
        returns.append(port_ret)
        
    if not returns:
        return None
        
    avg_ret = np.mean(returns)
    hit_rate = sum(1 for r in returns if r > 0) / len(returns)
    
    # Score 0-100 logic
    # Base score: annualized return * hit_rate bias?
    # Simple heuristic to clamp 0-100:
    # 5-day return avg -> annualized * 2 is roughly reasonable?
    # Let's say 1% per 5 days (~50% annual) => Score 80
    # 0% => Score 50
    # -1% => Score 20
    
    raw_score = 50 + (avg_ret * 100 * 20) # 0.5% return -> 50 + 10 = 60
    # Add Hit Rate Bonus
    raw_score += (hit_rate - 0.5) * 20 # 60% hit -> +2
    
    final_score = max(0, min(100, int(raw_score)))
    
    return {
        "avg_forward_return": float(avg_ret),
        "hit_rate": float(hit_rate),
        "sample_count": len(returns),
        "score_0_100": final_score
    }

def main():
    print("Starting PC Param Search V1...")
    
    # 1. Load Data
    history_data = load_data()
    if not history_data:
        print("[ERROR] No data available.")
        return
        
    print(f"Data Loaded: {len(history_data)} tickers")
    
    # 2. Iterate Search Space
    import itertools
    keys = list(SEARCH_SPACE.keys())
    values = list(SEARCH_SPACE.values())
    combinations = list(itertools.product(*values))
    
    results = []
    
    print(f"Simulating {len(combinations)} combinations...")
    
    for combo in combinations:
        # Create params dict
        p = dict(zip(keys, combo))
        
        # Prepare for simulation input
        # Flatten weights for display? 
        # Simulation requires direct access
        
        sim_res = simulate(p, history_data)
        if sim_res:
            res_entry = {
                "params": p,
                "metrics": sim_res,
                "score_0_100": sim_res["score_0_100"]
            }
            results.append(res_entry)
            
    # 3. Sort & Rank
    # Sort by score desc
    results.sort(key=lambda x: x["score_0_100"], reverse=True)
    
    # Assign Rank
    for i, r in enumerate(results):
        r["rank"] = i + 1
        
    best = results[0] if results else None
    
    # 4. Save
    output_data = {
        "schema": "PARAM_SEARCH_V1",
        "asof": datetime.datetime.now(KST).isoformat(),
        "universe": UNIVERSE,
        "data_source_chain": ["CACHE", "NAVER_FETCH"],
        "search_space": SEARCH_SPACE,
        "results": results[:20], # Top 20 only
        "winner": {
            "rank": 1,
            "params": best["params"] if best else {},
            "reason": f"Highest Score: {best['score_0_100']}" if best else "N/A"
        }
    }
    
    json_str = json.dumps(output_data, indent=2)
    
    # Latest
    (OUTPUT_DIR / "param_search_latest.json").write_text(json_str, encoding="utf-8")
    
    # Snapshot
    ts = datetime.datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    (SNAPSHOT_DIR / f"param_search_{ts}.json").write_text(json_str, encoding="utf-8")
    
    print(f"Search Complete. Best Score: {best['score_0_100'] if best else 0}")
    print(f"Saved to {OUTPUT_DIR / 'param_search_latest.json'}")

if __name__ == "__main__":
    main()
