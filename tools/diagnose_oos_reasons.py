import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sys

# --- CONFIG & PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
VALIDATION_DIR = REPORTS_DIR / "validation"
# SoT 1: Ledger (Execution Status)
LEDGER_PATH = VALIDATION_DIR / "phase_c0_daily_ledger_2024_2025.jsonl"
# SoT 2: Market Data (Evidence Source)
MARKET_DATA_PATH = BASE_DIR / "data" / "price" / "069500.parquet"
OUTPUT_PATH = VALIDATION_DIR / "phase_c0_daily_2024_2025_v3.json"

sys.path.append(str(BASE_DIR))
try:
    from config.production_config import PROD_STRATEGY_CONFIG
except ImportError:
    PROD_STRATEGY_CONFIG = {
        "ma_short_period": 60, 
        "regime_ma_long": 120, 
        "adx_period": 30, 
        "adx_threshold": 17.5
    }

# --- INDICATOR LIBRARY ---
def calculate_adx(df, period=30):
    """Calculate ADX for evidence"""
    # Lowercase columns normalisation
    df.columns = [c.lower() for c in df.columns]
    
    if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
        return pd.Series(0, index=df.index)
        
    # ... logic continues ...
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = pd.DataFrame(df['high'] - df['low'])
    tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
    tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    atr = tr.rolling(period).mean()
    
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (abs(minus_dm).rolling(period).mean() / atr)
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    return adx

def run_diagnosis_v3():
    # 1. LOAD DATA
    if not LEDGER_PATH.exists() or not MARKET_DATA_PATH.exists():
        print(f"CRITICAL: Missing Ledger {LEDGER_PATH} or Market Data {MARKET_DATA_PATH}")
        return

    ledger_df = pd.read_json(LEDGER_PATH, lines=True)
    ledger_df['date'] = pd.to_datetime(ledger_df['date'])
    ledger_df = ledger_df.sort_values('date').set_index('date')

    market_df = pd.read_parquet(MARKET_DATA_PATH)
    # Ensure index is datetime
    if not isinstance(market_df.index, pd.DatetimeIndex):
        if 'date' in market_df.columns:
            market_df['date'] = pd.to_datetime(market_df['date'])
            market_df = market_df.set_index('date')
    
    market_df = market_df.sort_index()
    market_df.columns = [c.lower() for c in market_df.columns]

    # 2. COMPUTE EVIDENCE (SoT for Market State)
    short_p = PROD_STRATEGY_CONFIG.get("ma_short_period", 60)
    long_p = PROD_STRATEGY_CONFIG.get("regime_ma_long", 120)
    adx_p = PROD_STRATEGY_CONFIG.get("adx_period", 30)
    adx_th = PROD_STRATEGY_CONFIG.get("adx_threshold", 17.5)

    market_df['ma_short'] = market_df['close'].rolling(window=short_p).mean()
    market_df['ma_long'] = market_df['close'].rolling(window=long_p).mean()
    market_df['adx'] = calculate_adx(market_df, period=adx_p)
    # Golden Cross: Short > Long (today) vs Short < Long (yesterday)? 
    # Or just current state? Schema says 'golden_cross.is_golden_cross'.
    # Usually means the event. But maybe just 'relation' is covered by 'ma.relation'.
    # Let's interpret 'golden_cross.is_golden_cross' as 'Short > Long' state or 'Cross Event'.
    # Given 'ma.relation' exists, 'golden_cross' likely implies the CROSS EVENT happened today.
    # But for simplicity and robustness, let's map it to 'Short > Long' boolean or check crossover logic.
    # Let's use 'is_golden_cross' as 'Today Cross Up'.
    market_df['prev_short'] = market_df['ma_short'].shift(1)
    market_df['prev_long'] = market_df['ma_long'].shift(1)
    market_df['is_gc'] = (market_df['ma_short'] > market_df['ma_long']) & (market_df['prev_short'] <= market_df['prev_long'])

    # 3. BUILD JSON STRUCTURE
    daily_items = []
    
    # KPI Aggregators
    kpi_map = {y: {"trading_days": 0, "gate_open_days":0, "chop_blocked_days":0, "bear_blocked_days":0, "executed_days":0, "integrity_anomaly_days":0} for y in [2024, 2025]}
    breakdown_map = {y: {"CHOP_BLOCK":0, "BEAR_BLOCK":0, "NO_SIGNAL":0, "EXECUTED":0, "EXECUTION_ANOMALY":0, "DATA_MISSING":0, "NONE":0} for y in [2024, 2025]}

    for dt, l_row in ledger_df.iterrows():
        year = dt.year
        if year not in [2024, 2025]: continue
        
        # Merge Market Evidence
        m_row = market_df.loc[dt] if dt in market_df.index else None
        
        # --- FIELDS ---
        # Execution
        executed = bool(l_row.get('actual_trades',0) > 0)
        actual_trades = int(l_row.get('actual_trades',0))
        
        # Market / Gate
        # Ledger 'primary_reason' dominates logic unless we want to re-evaluate?
        # Diagnosis usually explains WHY it happened. So we trust Ledger's decision flow results.
        block_reason = l_row.get('primary_reason', 'NONE')
        gate_decision = "BLOCK" if block_reason != 'NONE' else "PASS"
        regime = l_row.get('regime', 'BULL') # Ledger should have this
        
        # Signal
        # Ledger might have 'potential_signals' (bool or count).
        has_signal = bool(l_row.get('potential_signals', 0) > 0) or bool(l_row.get('signal', False))
        
        # Evidence (Calculated)
        adx_val = float(m_row['adx']) if m_row is not None and not pd.isna(m_row['adx']) else 0.0
        is_chop = adx_val < adx_th
        ma_short = float(m_row['ma_short']) if m_row is not None else 0
        ma_long = float(m_row['ma_long']) if m_row is not None else 0
        ma_relation = "SHORT_ABOVE_LONG" if ma_short > ma_long else "SHORT_BELOW_LONG"
        is_gc = bool(m_row['is_gc']) if m_row is not None else False
        
        # Integrity Logic (Contract 1)
        # "If execution.executed==true then market.block_reason must be 'NONE' OR integrity.anomaly==true"
        anomaly = False
        anomaly_codes = []
        
        if executed:
            if block_reason != 'NONE':
                anomaly = True
                anomaly_codes.append("EXECUTED_BUT_BLOCKED")
        
        if not executed and block_reason == 'NONE':
             # Passed gate but no trade? Maybe NO_SIGNAL but reason says NONE?
             # Usually 'NONE' means "No Block". If 'has_signal' is False, reason should be 'NO_SIGNAL'.
             # If Ledger says reason='NONE' logic implies it passed checks.
             # If no trade, maybe signal was False?
             # If signal was False, reason should have been NO_SIGNAL.
             # So (Reason=NONE + Executed=False) -> suspicious if Signal wasn't processed.
             pass 

        # --- KPI UPDATE ---
        kp = kpi_map[year]
        bd = breakdown_map[year]
        
        kp['trading_days'] += 1
        if block_reason not in ['CHOP_BLOCK', 'BEAR_BLOCK']:
            kp['gate_open_days'] += 1
        if block_reason == 'CHOP_BLOCK': kp['chop_blocked_days'] += 1
        if block_reason == 'BEAR_BLOCK': kp['bear_blocked_days'] += 1
        if executed: kp['executed_days'] += 1
        if anomaly: kp['integrity_anomaly_days'] += 1
        
        bd[block_reason] = bd.get(block_reason, 0) + 1
        if executed: bd['EXECUTED'] += 1 # Note: This overlaps with NONE usually
        if anomaly: bd['EXECUTION_ANOMALY'] += 1

        # --- ITEM CONSTRUCTION ---
        item = {
            "date": dt.strftime("%Y-%m-%d"),
            "year": year,
            "execution": {
                "executed": executed,
                "actual_trades": actual_trades,
                "source_of_truth": "OOS_LEDGER"
            },
            "signal": {
                "has_signal": has_signal,
                "signal_type": "BUY" if has_signal else "NONE", # Placeholder simplifying
                "signal_reason_short": "Signal Logic"
            },
            "market": {
                "regime": regime,
                "gate_decision": gate_decision,
                "block_reason": block_reason
            },
            "evidence": {
                "adx": { "value": round(adx_val, 2), "threshold": adx_th, "is_chop": is_chop },
                "ma": { "short_period": short_p, "long_period": long_p, "relation": ma_relation },
                "golden_cross": { "is_golden_cross": is_gc },
                "confidence": { "value": 0.0, "band": "MID", "explain": "Not Implemented" }
            },
            "integrity": {
                "anomaly": anomaly,
                "anomaly_codes": anomaly_codes
            }
        }
        daily_items.append(item)

    # 4. FINAL JSON
    final_json = {
        "schema": "PHASE_C0_DAILY_V3_EVIDENCE",
        "generated_at": datetime.now().isoformat(),
        "range": { "from": "2024-01-01", "to": "2025-12-31" },
        "kpi_definition": {
             "kpi_1_gate_open_days": "CHOP_BLOCK, BEAR_BLOCK가 아닌 거래일 수",
             "kpi_2_chop_blocked_days": "block_reason=CHOP_BLOCK 거래일 수",
             "kpi_3_bear_blocked_days": "block_reason=BEAR_BLOCK 거래일 수",
             "kpi_4_executed_days": "actual_trades>0 거래일 수 (SoT 기반)",
             "kpi_5_integrity_anomaly_days": "정책상 BLOCK인데 executed=true 등 모순/불일치 일수"
        },
        "years": {
            y: { "kpis": kpi_map[y], "reason_breakdown": breakdown_map[y] } for y in [2024, 2025]
        },
        "days": daily_items
    }
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False)
    
    print(f"Success: {OUTPUT_PATH}")

if __name__ == "__main__":
    run_diagnosis_v3()
