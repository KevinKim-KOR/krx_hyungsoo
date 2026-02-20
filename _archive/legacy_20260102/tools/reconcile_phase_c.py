import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
import hashlib
from pathlib import Path
import hashlib
from pathlib import Path
from datetime import datetime
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))

# --- CONFIGURATION (Contract C-R) ---
BASE_DIR = Path(__file__).parent.parent
VALIDATION_DIR = BASE_DIR / "reports" / "validation"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "reports" / "phase_c"

# Input Sources (Read-Only)
LEDGER_PATH = VALIDATION_DIR / "phase_c0_daily_ledger_2024_2025.jsonl"
VALIDATION_REPORT_PATH = VALIDATION_DIR / "oos_2024_2025_monthly.json"
EVIDENCE_PRICE_PATH = DATA_DIR / "price" / "069500.parquet"

# Output Targets (The Truth)
RECON_DAILY_PATH = OUTPUT_DIR / "recon_daily.jsonl"
RECON_SUMMARY_PATH = OUTPUT_DIR / "recon_summary.json"

# Ensure output dir exists
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Integrity Policy V1
INTEGRITY_POLICY = {
    "IC_DATA_MISSING_WITH_EXECUTION": "CRITICAL",
    "IC_L1_L2_MISMATCH": "INFO",
    "IC_EXECUTED_BUT_FINAL_BLOCK": "CRITICAL"
}

# Strategy Params (Baseline for Evidence)
PARAMS = {
    "ma_short": 60,
    "ma_long": 120,
    "adx_period": 30,
    "adx_threshold": 17.5
}

def calculate_technical_indicators(df):
    """Calculate ADX and MA for Evidence"""
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    
    # MA
    df['ma_short'] = df['close'].rolling(PARAMS['ma_short']).mean()
    df['ma_long'] = df['close'].rolling(PARAMS['ma_long']).mean()
    
    # ADX
    high = df['high']
    low = df['low']
    close = df['close']
    
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(PARAMS['adx_period']).mean()
    
    plus_di = 100 * (plus_dm.rolling(PARAMS['adx_period']).mean() / atr)
    minus_di = 100 * (minus_dm.abs().rolling(PARAMS['adx_period']).mean() / atr)
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    df['adx'] = dx.rolling(PARAMS['adx_period']).mean()
    
    return df

def calculate_file_hash(path):
    """Calculate SHA256 of a file"""
    if not path.exists():
        return None
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_file_info(path, name):
    """Gather file metadata for provenance"""
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "error": "File Not Found"
        }
    stat = path.stat()
    return {
        "name": name,
        "path": str(path),
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size_bytes": stat.st_size,
        "sha256": calculate_file_hash(path)
    }

def load_l1_ledger():
    if not LEDGER_PATH.exists():
        return {}, 0
    df = pd.read_json(LEDGER_PATH, lines=True)
    df['date'] = pd.to_datetime(df['date'])
    # Event Normalization: Map Date -> Action Count
    ledger_map = df.set_index('date')['actual_trades'].to_dict()
    total_actions = df['actual_trades'].sum()
    return ledger_map, int(total_actions)

def load_l2_validation():
    if not VALIDATION_REPORT_PATH.exists():
        return 0
    try:
        with open(VALIDATION_REPORT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            total = 0
            if "years" in data:
                for y in data["years"].values():
                     if "summary" in y:
                         total += y["summary"].get("trades", 0)
            return int(total)
    except:
        return 0

def load_market_evidence():
    if not EVIDENCE_PRICE_PATH.exists():
        return pd.DataFrame()
    df = pd.read_parquet(EVIDENCE_PRICE_PATH)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    df = df.sort_index()
    # Normalize with Indicators
    return calculate_technical_indicators(df)

def main():
    print(">>> Starting Reconciliation Phase C-R...")
    
    # 1. Load Sources
    l1_map, l1_total = load_l1_ledger()
    l2_total = load_l2_validation()
    evidence_df = load_market_evidence()
    
    print(f"Loaded L1 Actions: {l1_total}")
    print(f"Loaded L2 Trades: {l2_total}")
    print(f"Loaded Market Evidence: {len(evidence_df)} rows")
    
    # 1.1 Load Baseline (Contract R-4)
    BASELINE_PATH = OUTPUT_DIR.parent / "recon" / "coverage_baseline.json"
    baseline = {}
    if BASELINE_PATH.exists():
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            baseline = json.load(f)
            
    # 1.2 Gate CR4-1: Evidence Coverage Regression
    if baseline:
        b_min = baseline["evidence"]["min_date"]
        b_max = baseline["evidence"]["max_date"]
        
        # Current Evidence Range
        if evidence_df.empty:
             cur_min = "N/A"
             cur_max = "N/A"
        else:
             cur_min = evidence_df.index.min().strftime("%Y-%m-%d")
             cur_max = evidence_df.index.max().strftime("%Y-%m-%d")
             
        print(f"Coverage Check: Baseline[{b_min}~{b_max}] vs Current[{cur_min}~{cur_max}]")
        
        # Logic: Current must cover Baseline (Current Min <= Baseline Min AND Current Max >= Baseline Max)
        # Or EXACT MATCH? User said "Current.max < Baseline.max" is FAIL.
        # "shorter than baseline" -> FAIL.
        
        is_regression = False
        if evidence_df.empty:
            is_regression = True
        else:
            if cur_min > b_min or cur_max < b_max:
                is_regression = True
                
        if is_regression:
            error_summary = {
                "status": "error",
                "schema": "RECON_SUMMARY_V1",
                "generated_at": datetime.now(KST).isoformat(),
                "error": {
                    "code": "EVIDENCE_COVERAGE_REGRESSION",
                    "message_ko": f"심각: 증거 데이터 범위가 축소되었습니다. (기준: {b_min}~{b_max}, 현재: {cur_min}~{cur_max})"
                },
                "coverage": {
                    "baseline": baseline["evidence"],
                    "current": { "min_date": cur_min, "max_date": cur_max },
                    "regression": True,
                    "exec_within_evidence": False 
                }
            }
            print("!!! GATE CR4-1 FAILED: EVIDENCE REGRESSION !!!")
            with open(RECON_SUMMARY_PATH, "w", encoding="utf-8") as f:
                json.dump(error_summary, f, indent=2)
            sys.exit(1) # Hard Fail

    # 1.3 Gate CR4-2: Execution Within Evidence
    # Get Execution subset from L1 Map
    exec_dates = [d for d, trades in l1_map.items() if trades > 0]
    if exec_dates:
        exec_min = min(exec_dates).strftime("%Y-%m-%d")
        exec_max = max(exec_dates).strftime("%Y-%m-%d")
        
        if evidence_df.empty:
            ev_min = "9999-99-99"
            ev_max = "0000-00-00"
        else:
            ev_min = evidence_df.index.min().strftime("%Y-%m-%d")
            ev_max = evidence_df.index.max().strftime("%Y-%m-%d")
            
        # Fail if Exec Min < Ev Min OR Exec Max > Ev Max
        if exec_min < ev_min or exec_max > ev_max:
            error_summary = {
                "status": "error",
                "schema": "RECON_SUMMARY_V1",
                "generated_at": datetime.now(KST).isoformat(),
                "error": {
                    "code": "EXECUTION_OUTSIDE_EVIDENCE_COVERAGE",
                    "message_ko": f"심각: 거래 발생일이 시장 데이터 범위를 벗어났습니다. (거래: {exec_min}~{exec_max}, 시장: {ev_min}~{ev_max})"
                },
                "coverage": {
                    "baseline": baseline.get("evidence", {}),
                    "current": { "min_date": ev_min, "max_date": ev_max },
                    "regression": False,
                    "exec_within_evidence": False,
                    "execution_range": { "min_date": exec_min, "max_date": exec_max }
                }
            }
            print("!!! GATE CR4-2 FAILED: EXECUTION OUTSIDE COVERAGE !!!")
            with open(RECON_SUMMARY_PATH, "w", encoding="utf-8") as f:
                json.dump(error_summary, f, indent=2)
            sys.exit(1) # Hard Fail
    
    # 2. Iterate Daily (Business Days 2024-2025)
    all_dates = pd.date_range("2024-01-01", "2025-12-31", freq="B")
    
    recon_daily_rows = []
    
    integrity_stats = {
        "critical_days": 0,
        "warning_days": 0,
        "info_days": 0,
        "code_counts": {}
    }
    
    kpi_stats = {
        "gate_open": 0, "chop_block": 0, "bear_block": 0,
        "executed": 0, "no_data": 0
    }
    
    for date in all_dates:
        d_str = date.strftime("%Y-%m-%d")
        
        # --- Join Inputs ---
        l1_actions = l1_map.get(date, 0)
        executed = l1_actions > 0
        
        row = evidence_df.loc[date] if date in evidence_df.index else None
        has_data = row is not None
        
        # --- Logic & Evidence ---
        data_status = "OK" if has_data else "NO_DATA"
        adx_val = 0.0
        ma_s = 0.0
        ma_l = 0.0
        regime = "unknown"
        
        # Precheck
        pre_gate = "BLOCK"
        pre_reason = "NO_DATA"
        
        if has_data:
            if pd.isna(row['adx']) or pd.isna(row['ma_short']):
                data_status = "DATA_MISSING"
                pre_reason = "DATA_MISSING"
            else:
                adx_val = float(row['adx'])
                ma_s = float(row['ma_short'])
                ma_l = float(row['ma_long'])
                
                if adx_val < PARAMS['adx_threshold']:
                    regime = "neutral"
                    pre_reason = "CHOP_BLOCK"
                elif ma_s < ma_l:
                    regime = "bear"
                    pre_reason = "BEAR_BLOCK"
                else:
                    regime = "bull"
                    pre_gate = "PASS"
                    pre_reason = "NONE"
        
        # Override (Final Decision)
        final_gate = pre_gate
        final_reason = pre_reason
        
        if executed:
            final_gate = "PASS"
            final_reason = "EXECUTED_SOT_OVERRIDE"
            
        # --- Integrity Check (Mechanical Rule) ---
        integrity_codes = []
        severity = "NONE"
        
        # Rule 1: Data Missing with Execution
        if (data_status in ["NO_DATA", "DATA_MISSING"]) and executed:
            integrity_codes.append("IC_DATA_MISSING_WITH_EXECUTION")
            severity = "CRITICAL"
            
        # Rule 2: Executed but Blocked (Logic Bug) - Should handle above, but double check
        if executed and final_gate == "BLOCK":
            integrity_codes.append("IC_EXECUTED_BUT_FINAL_BLOCK")
            severity = "CRITICAL"
            
        # Update Integrity Stats
        if severity == "CRITICAL":
            integrity_stats["critical_days"] += 1
        elif severity == "WARNING":
            integrity_stats["warning_days"] += 1
        elif severity == "INFO":
            integrity_stats["info_days"] += 1
            
        for code in integrity_codes:
            integrity_stats["code_counts"][code] = integrity_stats["code_counts"].get(code, 0) + 1

        # Update KPI Stats
        if executed: kpi_stats["executed"] += 1
        if data_status != "OK": kpi_stats["no_data"] += 1
        if pre_gate == "PASS": kpi_stats["gate_open"] += 1
        if pre_reason == "CHOP_BLOCK": kpi_stats["chop_block"] += 1
        if pre_reason == "BEAR_BLOCK": kpi_stats["bear_block"] += 1

        # --- Construct Recon Row ---
        recon_row = {
            "schema": "RECON_DAILY_V1",
            "trade_date": d_str,
            "l1": {
                "actions": int(l1_actions)
            },
            "evidence": {
                "status": data_status,
                "regime": regime,
                "adx": round(adx_val, 2),
                "ma_short": round(ma_s, 2),
                "ma_long": round(ma_l, 2)
            },
            "precheck": {
                "gate_decision": pre_gate,
                "reason": pre_reason
            },
            "final": {
                "gate_decision": final_gate,
                "reason": final_reason
            },
            "execution": {
                "executed": bool(executed)
            },
            "integrity": {
                "severity": severity,
                "codes": integrity_codes
            },
            "pointers": {
                "l1_source": "phase_c0_daily_ledger_2024_2025.jsonl" if executed else None,
                "evidence_source": "069500.parquet" if has_data else None
            }
        }
        recon_daily_rows.append(recon_row)

    # 3. Output Generation
    
    # 3.1 Daily JSONL
    print(f"Writing {len(recon_daily_rows)} daily rows to {RECON_DAILY_PATH}")
    with open(RECON_DAILY_PATH, "w", encoding="utf-8") as f:
        for row in recon_daily_rows:
            f.write(json.dumps(row) + "\n")
            
    # 3.2 Summary JSON
    top_codes = [{"code": k, "days": v} for k, v in integrity_stats["code_counts"].items()]
    top_codes.sort(key=lambda x: x["days"], reverse=True)
    
    summary = {
        "schema": "RECON_SUMMARY_V1",
        "generated_at": datetime.now(KST).isoformat(),
        "period": { "from": "2024-01-01", "to": "2025-12-31" },
        "trade_count_policy_id": "TRADE_COUNT_POLICY_V1",
        "counts": {
            "L1_actions": l1_total,
            "L2_trades": l2_total,
            "L1_L2_delta": l1_total - l2_total
        },
        "kpis": kpi_stats,
        "integrity": {
            "critical_days": integrity_stats["critical_days"],
            "warning_days": integrity_stats["warning_days"],
            "info_days": integrity_stats["info_days"],
            "top_codes": top_codes
        },
        "coverage": {
            "evidence_no_data_days": kpi_stats["no_data"],
            "regression": False,
            "exec_within_evidence": True,
            "baseline": baseline.get("evidence", {}),
            "current": {
                "min_date": evidence_df.index.min().strftime("%Y-%m-%d") if not evidence_df.empty else "N/A",
                "max_date": evidence_df.index.max().strftime("%Y-%m-%d") if not evidence_df.empty else "N/A"
            },
            "execution_range": {
                 # Calculated again for safety or assume from Gate logic?
                 # L1 Map keys > 0
                 "min_date": min([d for d,c in l1_map.items() if c>0]).strftime("%Y-%m-%d") if any(l1_map.values()) else "N/A",
                 "max_date": max([d for d,c in l1_map.items() if c>0]).strftime("%Y-%m-%d") if any(l1_map.values()) else "N/A"
            }
        },
        "provenance": {
            "generated_at": datetime.now(KST).isoformat(),
            "reconciler_version": "C-R.5",
            "policy_ids": ["TRADE_COUNT_POLICY_V1", "COVERAGE_BASELINE_V1", "INTEGRITY_POLICY_V1"],
            "sources": [
                get_file_info(LEDGER_PATH, "LEDGER"),
                get_file_info(EVIDENCE_PRICE_PATH, "EVIDENCE"),
                get_file_info(VALIDATION_REPORT_PATH, "VALIDATION"),
                get_file_info(BASELINE_PATH, "BASELINE")
            ]
        },
        "provenance": {
            "generated_at": datetime.now(KST).isoformat(),
            "reconciler_version": "C-R.5",
            "policy_ids": ["TRADE_COUNT_POLICY_V1", "COVERAGE_BASELINE_V1", "INTEGRITY_POLICY_V1"],
            "sources": [
                get_file_info(LEDGER_PATH, "LEDGER"),
                get_file_info(EVIDENCE_PRICE_PATH, "EVIDENCE"),
                get_file_info(VALIDATION_REPORT_PATH, "VALIDATION"),
                get_file_info(BASELINE_PATH, "BASELINE")
            ]
        }
    }
    
    print(f"Writing summary to {RECON_SUMMARY_PATH}")
    with open(RECON_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print(">>> Reconciliation Complete.")

if __name__ == "__main__":
    main()
