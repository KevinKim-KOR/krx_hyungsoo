# -*- coding: utf-8 -*-
"""
tools/export_trials.py

Exports Optuna trials from a SQLite DB to CSV and generates a Top 3 summary.
Usage: python -m tools.export_trials --run-id <RUN_ID>
"""
import argparse
import pandas as pd
import optuna
import logging
from pathlib import Path
import sys

# Force UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

logging.basicConfig(level=logging.INFO, format='{asctime} [{levelname}] {message}', style='{')
logger = logging.getLogger(__name__)

def export_trials(run_id: str):
    # Locate DB
    # Check if run_id is a full path or just an ID
    if Path(run_id).exists():
         run_dir = Path(run_id)
         # Extract clean ID from path if possible, or just use folder name
         clean_id = run_dir.name
    else:
         # Assume inside data/tuning_runs
         run_dir = Path(f"data/tuning_runs/{run_id}")
         clean_id = run_id
    
    db_path = run_dir / "optuna.db"
    if not db_path.exists():
        logger.error(f"DB not found at {db_path}")
        return

    db_url = f"sqlite:///{db_path}"
    study_name = f"study_{clean_id}" # Assuming naming convention matches run_phase15

    logger.info(f"Loading study '{study_name}' from {db_url}...")
    try:
        study = optuna.load_study(study_name=study_name, storage=db_url)
    except Exception as e:
        # Fallback: try getting the first study if name mismatch
        try:
             logger.warning(f"Could not load '{study_name}'. Listing all studies...")
             all_studies = optuna.get_all_study_summaries(storage=db_url)
             if not all_studies:
                 logger.error("No studies found in DB.")
                 return
             study = optuna.load_study(study_name=all_studies[0].study_name, storage=db_url)
             logger.info(f"Loaded study '{study.study_name}' instead.")
        except Exception as e2:
             logger.error(f"Failed to load study: {e2}")
             return

    # Convert to DataFrame
    df = study.trials_dataframe()
    
    # Clean Column Names
    # e.g., user_attrs_by_lookback -> by_lookback (too complex), but params_ma_period -> ma_period is good.
    df.rename(columns=lambda x: x.replace("params_", "").replace("user_attrs_", ""), inplace=True)
    
    # Sort by Value (Sharpe) Descending
    if "value" in df.columns:
        df.sort_values("value", ascending=False, inplace=True)
    
    # Save CSV
    csv_path = run_dir / "trials.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved trials to {csv_path}")
    
    # Generate Top 3 Summary
    if "value" not in df.columns:
        logger.warning("No value column found (all trials failed?). Skipping summary.")
        return

    top3 = df.head(3)
    
    md_path = run_dir / "top3_candidates.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Top 3 Candidates for Run {clean_id}\n\n")
        f.write(top3.to_markdown(index=False))
        f.write("\n\n## Summary\n")
        f.write(f"- Total Trials: {len(df)}\n")
        completed = df[df.state == "COMPLETE"]
        f.write(f"- Completed: {len(completed)}\n")
        f.write(f"- Best Score: {study.best_value:.4f} (Trial {study.best_trial.number})\n")
    
    logger.info(f"Saved Top 3 summary to {md_path}")
    
    # Print Top 3 for console
    print("\n[Top 3 Candidates]")
    cols_to_show = [c for c in ["number", "value", "ma_period", "rsi_period", "stop_loss_pct", "state", "fail_reason"] if c in df.columns]
    print(top3[cols_to_show].to_markdown(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="Run ID or path to run directory")
    args = parser.parse_args()
    
    export_trials(args.run_id)
