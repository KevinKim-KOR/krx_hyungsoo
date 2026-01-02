import json
import pandas as pd
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
RECON_DAILY = BASE_DIR / "reports" / "phase_c" / "recon_daily.jsonl"
EVIDENCE_PATH = BASE_DIR / "data" / "price" / "069500.parquet"
LEDGER_PATH = BASE_DIR / "reports" / "validation" / "phase_c0_daily_ledger_2024_2025.jsonl"
RECON_OUT_DIR = BASE_DIR / "reports" / "recon"

RECON_OUT_DIR.mkdir(parents=True, exist_ok=True)

def analyze():
    print("--- Phase C-R.3: Coverage Gap Analysis ---")
    
    # 1. Identify E2 Dates
    e2_dates = []
    with open(RECON_DAILY, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            row = json.loads(line)
            integrity = row.get("integrity", {})
            if integrity.get("severity") == "CRITICAL":
                # Check root cause E2 (we inferred it as E2_DATE_OUT_OF_RANGE)
                # Or check if pointer matches 069500.parquet and date logic
                # Since we haven't officially tagged E2 in file yet (we only did analysis JSON output), 
                # we rely on IC_DATA_MISSING_WITH_EXECUTION check.
                if "IC_DATA_MISSING_WITH_EXECUTION" in integrity.get("codes", []):
                     e2_dates.append(row["trade_date"])
    
    e2_dates.sort()
    e2_out_file = RECON_OUT_DIR / "e2_out_of_range_dates.json"
    with open(e2_out_file, "w", encoding="utf-8") as f:
        json.dump(e2_dates, f, indent=2)
    print(f"[Done] E2 Dates ({len(e2_dates)}) saved to {e2_out_file.name}")
    
    # 2. Measure Evidence Coverage
    df_ev = pd.read_parquet(EVIDENCE_PATH)
    # Handle index or 'date' column
    if 'date' in df_ev.columns:
        dates = pd.to_datetime(df_ev['date'])
    else:
        dates = pd.to_datetime(df_ev.index)
        
    ev_cov = {
        "min_date": dates.min().strftime("%Y-%m-%d"),
        "max_date": dates.max().strftime("%Y-%m-%d"),
        "count": len(dates)
    }
    ev_out_file = RECON_OUT_DIR / "evidence_coverage.json"
    with open(ev_out_file, "w", encoding="utf-8") as f:
        json.dump(ev_cov, f, indent=2)
    print(f"[Done] Evidence Coverage saved to {ev_out_file.name}: {ev_cov}")
    
    # 3. Measure Ledger Execution Coverage
    exec_dates = []
    with open(LEDGER_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            row = json.loads(line)
            if row.get("actual_trades", 0) > 0:
                exec_dates.append(row["date"])
                
    exec_dates.sort()
    led_cov = {
        "min_date": min(exec_dates) if exec_dates else None,
        "max_date": max(exec_dates) if exec_dates else None,
        "count": len(exec_dates)
    }
    led_out_file = RECON_OUT_DIR / "ledger_execution_coverage.json"
    with open(led_out_file, "w", encoding="utf-8") as f:
        json.dump(led_cov, f, indent=2)
    print(f"[Done] Ledger Coverage saved to {led_out_file.name}: {led_cov}")

if __name__ == "__main__":
    analyze()
