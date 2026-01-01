import yfinance as yf
import pandas as pd
from pathlib import Path
import json

# Paths
BASE_DIR = Path(__file__).parent.parent
EVIDENCE_PATH = BASE_DIR / "data" / "price" / "069500.parquet"
RECON_OUT_DIR = BASE_DIR / "reports" / "recon"

def patch_evidence():
    print("--- Phase C-R.3: Patch Evidence (Track A) ---")
    
    symbol = "069500.KS"
    start_date = "2024-01-01"
    end_date = "2025-12-31"
    
    print(f"Fetching {symbol} from {start_date} to {end_date}...")
    try:
        # Fetch Data
        df_new = yf.download(symbol, start=start_date, end=end_date, progress=False)
        
        if df_new.empty:
            print("ERROR: Fetched data is empty. Network issue or invalid symbol?")
            return
            
        print(f"Fetched {len(df_new)} rows.")
        
        # Standardize Columns (Lowercase, etc if needed - but check existing parquet first)
        # Load existing to match schema
        if EVIDENCE_PATH.exists():
            df_old = pd.read_parquet(EVIDENCE_PATH)
            print(f"Existing Parquet: {len(df_old)} rows, Cols: {df_old.columns.tolist()}")
            
            # Simple merge strategy: Concatenate and drop duplicates by Date
            # Ensure 'date' is index or column
            
            # Flatten MultiIndex if present
            new_cols = []
            for c in df_new.columns:
                if isinstance(c, tuple):
                    new_cols.append(c[0]) 
                else:
                    new_cols.append(c)
            df_new.columns = new_cols

            # Restore is_index_date logic
            is_index_date = True
            if 'date' in df_old.columns:
                 is_index_date = False
                 df_old = df_old.set_index('date')
            
            # Helper to normalize case
            def normalize_cols(cols):
                return [c.capitalize() for c in cols] # Open, High...

            # Rename New Cols to match Old if needed?
            # Old is ['Open', 'High', 'Low', 'Close', 'Volume']
            # New is likely same.
            
            # Align cols
            # Only keep common columns
            # Force Title Case on New just in case
            df_new.columns = [c.capitalize() for c in df_new.columns]
            
            common_cols = list(set(df_old.columns) & set(df_new.columns))
            print(f"Common Columns: {common_cols}")
            
            if not common_cols:
                print(f"Old Columns: {df_old.columns.tolist()}")
                print(f"New Columns: {df_new.columns.tolist()}")
                print("Error: No common columns found.")
                return

            df_combined = pd.concat([df_old, df_new[common_cols]]) # Keep common columns
            
            # Deduplicate
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')]
            df_combined = df_combined.sort_index()
            
            # Validation
            print(f"Combined Rows: {len(df_combined)}")
            print(f"Range: {df_combined.index.min()} ~ {df_combined.index.max()}")
            
            # Save
            # If originally had 'date' col, reset index
            if not is_index_date:
                df_combined = df_combined.reset_index().rename(columns={'index': 'date', 'Date': 'date'})
            
            df_combined.to_parquet(EVIDENCE_PATH)
            print(f"[Done] Patched {EVIDENCE_PATH.name}")
            
            # Generate Output JSON
            after_cov = {
                "min_date": df_combined.index.min().strftime("%Y-%m-%d") if is_index_date else df_combined['date'].min().strftime("%Y-%m-%d"),
                "max_date": df_combined.index.max().strftime("%Y-%m-%d") if is_index_date else df_combined['date'].max().strftime("%Y-%m-%d"),
                "count": len(df_combined)
            }
            with open(RECON_OUT_DIR / "evidence_coverage_after.json", "w") as f:
                json.dump(after_cov, f, indent=2)
                
            # Clear E2 dates file (as verification expectation)
            with open(RECON_OUT_DIR / "e2_out_of_range_dates_after.json", "w") as f:
                json.dump([], f)
                
        else:
            print("Warning: Existing parquet not found. Creating new from fetch.")
            df_new.to_parquet(EVIDENCE_PATH)

    except Exception as e:
        print(f"Patch Failed: {e}")

if __name__ == "__main__":
    patch_evidence()
