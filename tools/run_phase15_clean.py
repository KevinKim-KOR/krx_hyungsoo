
# -*- coding: utf-8 -*-
import sys
import logging
import argparse
import random
import time
import json
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
import optuna

# Force UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

from extensions.tuning.runner import run_backtest_for_tuning, CostConfig
from extensions.tuning.types import BacktestRunResult, BacktestMetrics, DataConfig, DEFAULT_COSTS
from extensions.tuning.split import SplitConfig
from extensions.tuning.manifest import create_manifest
from extensions.tuning.evidence import ResultPackager, VerdictEngine, ReportGenerator, PreflightResult

# Mock & Configs
GUARDRAIL_PRESETS = {
    "default": {"min_trades": 30, "min_exposure": 0.30, "max_turnover": 24.0},
    "lax":     {"min_trades": 10, "min_exposure": 0.10, "max_turnover": 50.0},
    "strict":  {"min_trades": 50, "min_exposure": 0.50, "max_turnover": 12.0},
}
MOCK_UNIVERSE = {"tickers": ["005930"], "name": "MOCK"}
PERIODS = {"A": {"start": date(2021, 1, 1), "end": date(2023, 12, 31)}}
UNIVERSES = {"A": MOCK_UNIVERSE}

def run_clean_phase15(run_id: str, args: argparse.Namespace):
    packager = ResultPackager()
    logger = logging.getLogger()
    logger.info(f"=== CLEAN PHASE 1.5 START (RunID: {packager.run_id}) ===")
    
    period = PERIODS["A"]
    # Timestamps for compatibility
    period["start"] = pd.Timestamp(period["start"])
    period["end"] = pd.Timestamp(period["end"])

    # Loader Logic (Simplified)
    trading_calendar = []
    universe_codes = []
    if args.real:
        from core.data.filtering import get_filtered_universe
        from infra.data.loader import load_trading_calendar
        universe_codes = get_filtered_universe()
        trading_calendar = load_trading_calendar(period["start"], period["end"])
    else:
        universe_codes = MOCK_UNIVERSE["tickers"]
        trading_calendar = [period["start"] + timedelta(days=x) for x in range((period["end"] - period["start"]).days + 1)]

    # Optuna Setup
    run_dir = Path(f"data/tuning_runs/{packager.run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{run_dir}/optuna.db"
    
    study = optuna.create_study(
        study_name=f"study_{packager.run_id}",
        storage=db_url,
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=args.seed),
        load_if_exists=True
    )

    tuning_split_config = SplitConfig(min_val_months=14)
    lookbacks = [3, 6, 12]

    def objective(trial):
        params = {
            "ma_period": trial.suggest_int("ma_period", 40, 200, step=10),
            "rsi_period": trial.suggest_int("rsi_period", 10, 60),
            "stop_loss_pct": trial.suggest_float("stop_loss_pct", 0.05, 0.15, step=0.01),
            "regime_ma_period": trial.suggest_int("regime_ma_period", 60, 200, step=20),
        }
        
        by_lookback_evidence = {}
        scores = []
        result = None
        failed_result = None
        final_fail_reason = None
        final_score = -9999.0

        try:
            for lb in lookbacks:
                result = run_backtest_for_tuning(
                    params=params, start_date=period["start"], end_date=period["end"],
                    lookback_months=lb, trading_calendar=trading_calendar, universe_codes=universe_codes,
                    use_cache=True, guardrail_config=GUARDRAIL_PRESETS[args.guardrail_preset],
                    split_config=tuning_split_config
                )
                
                # Evidence Collection
                info = getattr(result, "debug", None)
                eff_lb_str = "N/A"
                if info and info.effective_eval_start:
                    eff_start = info.effective_eval_start.date() if hasattr(info.effective_eval_start, "date") else info.effective_eval_start
                    eff_end = period["end"].date() if hasattr(period["end"], "date") else period["end"]
                    delta_days = (eff_end - eff_start).days
                    eff_lb_str = f"{delta_days}d"
                
                score = float(result.val.sharpe) if result.val else -999.0
                if not result.is_valid and not args.analysis_mode:
                    score = -999.0
                    if failed_result is None:
                        failed_result = result
                    
                scores.append(score)
                by_lookback_evidence[lb] = {
                    "requested_lb": lb,
                    "effective_lb": eff_lb_str,
                    "val_effective_start_date": str(info.effective_eval_start) if info else "N/A",
                    "val_bars_used": info.bars_used if info else 0,
                    "score": score
                }

            # Monotonicity Check
            if all(k in by_lookback_evidence for k in [3, 6, 12]):
                d3 = by_lookback_evidence[3]["val_effective_start_date"]
                d6 = by_lookback_evidence[6]["val_effective_start_date"]
                d12 = by_lookback_evidence[12]["val_effective_start_date"]
                
                if d3 != "N/A" and d6 != "N/A" and d12 != "N/A":
                    if not (d12 <= d6 <= d3):
                        msg = f"[CRITICAL INTEGRITY] Date Monotonicity Failed! 12M({d12}) <= 6M({d6}) <= 3M({d3})"
                        logger.critical(msg)
                        raise ValueError(msg)

            final_score = min(scores) if scores else -999.0

        except Exception as e:
            logger.error(f"Objective Error: {e}")
            final_fail_reason = f"Exception: {str(e)}"
            final_score = -9999.0
            with open("last_trial_error.txt", "w", encoding="utf-8") as f:
                f.write(str(e))
                f.write("\n")
                f.write(traceback.format_exc())
        
        # Finally Logic (Manual Control)
        # Store Fail Reason
        if final_score <= -100:
            # Use failed_result if available, otherwise use last result
            target_result = failed_result if failed_result else result
            
            if not final_fail_reason:
                final_fail_reason = "Unknown Error"
                
                # Extraction
                if target_result is None: final_fail_reason = "Result None"
                elif not target_result.is_valid and target_result.guardrail_checks and getattr(target_result.guardrail_checks, 'failures', None):
                    final_fail_reason = target_result.guardrail_checks.failures[0]
                elif not target_result.is_valid and target_result.logic_checks and getattr(target_result.logic_checks, 'failures', None):
                    final_fail_reason = f"Logic: {target_result.logic_checks.failures[0]}"
                elif target_result.warnings:
                    final_fail_reason = f"Warning: {target_result.warnings[0]}"
                
                # Metrics / Logic fallback
                if final_fail_reason == "Unknown Error":
                     if not target_result.val: final_fail_reason = "Empty Metrics"
                
                # Fail Fast
                if final_fail_reason == "Unknown Error":
                    debug_ctx = {
                        "is_valid": target_result.is_valid if target_result else False,
                        "guardrail": getattr(target_result.guardrail_checks, 'failures', []) if target_result else [],
                        "logic": getattr(target_result.logic_checks, 'failures', []) if target_result else []
                    }
                    msg = f"[CRITICAL UNKNOWN ERROR] Context: {debug_ctx}"
                    logger.critical(msg)
                    # Dump to file
                    try:
                        with open("crash_dump_clean.json", "w", encoding="utf-8") as f:
                            json.dump(debug_ctx, f, indent=2, default=str)
                    except: pass
                    raise RuntimeError(msg)

            trial.set_user_attr("fail_reason", final_fail_reason)
        
        trial.set_user_attr("by_lookback", by_lookback_evidence)
        return final_score

    study.optimize(objective, n_trials=args.trials)
    
    # Simple Report
    valid_trials = [t for t in study.trials if t.value > -100]
    print(f"Total Trials: {len(study.trials)}")
    print(f"Valid Trials: {len(valid_trials)}")
    if valid_trials:
        best = max(valid_trials, key=lambda t: t.value)
        print(f"Best Score: {best.value}")
        print(f"Best Params: {best.params}")
        with open("top3_candidates_clean.md", "w", encoding="utf-8") as f:
            f.write(f"# Top Candidate\nScore: {best.value}\nParams: {best.params}\n")
            f.write(f"Evidence: {best.user_attrs.get('by_lookback')}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--guardrail-preset", type=str, default="default")
    parser.add_argument("--log-level", type=str, default="INFO")
    parser.add_argument("--analysis-mode", action="store_true")
    args = parser.parse_args()
    
    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler("manual_debug.log", encoding="utf-8", mode='w')]
    logging.basicConfig(level=getattr(logging, args.log_level), format='{asctime} [{levelname}] {message}', style='{', handlers=handlers)
    
    try:
        run_clean_phase15("A", args)
    except Exception as e:
        with open("fatal_error_clean.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
            # Also dump exception string
            f.write(f"\n{str(e)}")
        print(f"FATAL: {e}")
        sys.exit(1)
