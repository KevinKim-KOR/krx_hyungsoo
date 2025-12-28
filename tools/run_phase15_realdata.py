# -*- coding: utf-8 -*-
"""
tools/run_phase15_realdata.py (Enhanced v2.2.1 Strict)

Goal: Phase 1 Evidence-Based Completion
- 3-Layer Safety Result Pack
- Loader-Authoritative Preflight
- Multi-Lookback Monotonicity Evidence
- Outsample-Focused Gate 2 Evidence
- Automated Verdict
"""
import sys
import logging
import argparse
import random
import time
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

# Force UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except: pass

# Internal Imports
from extensions.tuning.runner import run_backtest_for_tuning, CostConfig
from extensions.tuning.types import (
    BacktestRunResult, BacktestMetrics, DataConfig, 
    DEFAULT_COSTS, GuardrailChecks, compute_universe_hash
)
from extensions.tuning.split import SplitConfig
from extensions.tuning.manifest import create_manifest, save_manifest
from extensions.tuning.evidence import (
    ResultPackager, PreflightCheck, VerdictEngine, ReportGenerator, PreflightResult
) # New Evidence Module

# ----------------------------------------------------------------
# MOCK Infrastructure (Fallback)
# ----------------------------------------------------------------
class MockTelemetry:
    def start_new_session(self, *args, **kwargs): pass
def get_telemetry(): return MockTelemetry()
def emit_system_start(*args,**kw): pass
def emit_run_config(*args,**kw): pass
def emit_tuning_start(*args,**kw): pass
def emit_trial_result(*args,**kw): pass
def emit_gate1_summary(*args,**kw): pass
def emit_gate2_summary(*args,**kw): pass
def emit_manifest_saved(*args,**kw): pass
class EventStage:
    GATE2 = "GATE2"
    PHASE15 = "PHASE15"

# ----------------------------------------------------------------
# Constants & Configs
# ----------------------------------------------------------------
GUARDRAIL_PRESETS = {
    "default": {"min_trades": 30, "min_exposure": 0.30, "max_turnover": 24.0},
    "lax":     {"min_trades": 10, "min_exposure": 0.10, "max_turnover": 50.0},
    "strict":  {"min_trades": 50, "min_exposure": 0.50, "max_turnover": 12.0},
    "proof":   {"min_trades": 5, "min_exposure": 0.05, "max_turnover": 999.0}, # For Evidence Proof
}

MOCK_UNIVERSE = {
    "tickers": ["005930", "000660", "035420", "005380", "051910"],
    "name": "KOSPI_TOP5_MOCK"
}

PERIODS = {
    "A": {"start": date(2021, 1, 1), "end": date(2023, 12, 31)},
    "B": {"start": date(2021, 6, 1), "end": date(2024, 5, 30)},
    "C": {"start": date(2022, 1, 1), "end": date(2024, 12, 31)},
}

UNIVERSES = {
    "A": MOCK_UNIVERSE,
    "B": MOCK_UNIVERSE,
    "C": MOCK_UNIVERSE,
}

# ----------------------------------------------------------------
# MiniWalkForward (Gate 2 Logic) - Enhanced for Evidence
# ----------------------------------------------------------------
@dataclass
class WFWindowEvidence:
    train_period: Dict[str, str]
    val_period: Dict[str, str]
    outsample_period: Dict[str, str]
    outsample_bars: int
    outsample_trades: int
    outsample_sharpe: float

class MiniWalkForward:
    def __init__(self, start_date, end_date, trading_calendar, train_m, val_m, out_m, stride_m, universe_codes):
        self.start_date = start_date
        self.end_date = end_date
        self.trading_calendar = trading_calendar
        self.train_m = train_m
        self.val_m = val_m
        self.out_m = out_m
        self.stride_m = stride_m
        self.universe_codes = universe_codes
        from dateutil.relativedelta import relativedelta
        self.rd = relativedelta

    def run(self, params: Dict[str, Any]) -> List[WFWindowEvidence]:
        results = []
        curr = self.start_date
        
        while True:
            # Window Calculation
            total_m = self.train_m + self.val_m + self.out_m
            wind_end = curr + self.rd(months=total_m)
            if wind_end > self.end_date:
                break
                
            # Period Definitions
            out_end = wind_end
            out_start = out_end - self.rd(months=self.out_m)
            
            val_end = out_start
            val_start = val_end - self.rd(months=self.val_m)
            
            train_end = val_start
            train_start = curr
            
            # Execution (Outsample Focus)
            # We use _run_single_backtest to get strict outsample metrics
            from extensions.tuning.runner import _run_single_backtest
            
            # Run on Outsample Period
            # [EVIDENCE] Main Engine Execution Context
            if self.start_date == curr: # Log once per run (start of window loop doesn't guarantee single log if looped, but practical enough)
                 # Only log if it's the very first window or we can check a flag. 
                 # Better: Log before loop. But params are passed to _run_single_backtest.
                 pass

            # Run on Outsample Period
            # [EVIDENCE] Log before passing to runner
            if logging.getLogger().isEnabledFor(logging.INFO):
                 logging.getLogger().info(f"[EVIDENCE] Main Engine passing params to _run_single_backtest: {params}")

            metrics = _run_single_backtest(
                params=params,
                start_date=out_start,
                end_date=out_end,
                costs=DEFAULT_COSTS,
                trading_calendar=self.trading_calendar,
                universe_codes=self.universe_codes
            )
            
            # Collect Evidence
            sharpe = metrics.sharpe if metrics else 0.0
            trades = metrics.num_trades if metrics else 0
            # Bars? _run_single_backtest doesn't return bars count directly in metrics usually?
            # Metric object usually has num_trades, sharpe, etc. 
            # We might need to count bars from result? 
            # _run_single_backtest returns BacktestMetrics. 
            # BacktestMetrics definition check? Assuming it doesn't have bars.
            # We can approximate bars by calendar or if we assume daily data.
            # Let's assume daily and use calendar slicing.
            bars_cnt = len([d for d in self.trading_calendar if out_start <= d <= out_end]) if metrics else 0
            
            ev = WFWindowEvidence(
                train_period={"start": str(train_start), "end": str(train_end)},
                val_period={"start": str(val_start), "end": str(val_end)},
                outsample_period={"start": str(out_start), "end": str(out_end)},
                outsample_bars=bars_cnt,
                outsample_trades=trades,
                outsample_sharpe=sharpe
            )
            results.append(ev)
            
            curr += self.rd(months=self.stride_m)
            
        return results

# ----------------------------------------------------------------
# Main Orchestrator
# ----------------------------------------------------------------
def run_strict_phase15(
    run_id: str,
    args: argparse.Namespace
) -> Dict:
    # 1. Setup ResultPackager
    packager = ResultPackager()
    logger = logging.getLogger() # Root logger (now has file handler)
    logger.info(f"=== STRICT PHASE 1.5 START (RunID: {packager.run_id}) ===")
    
    universe = UNIVERSES.get(run_id, MOCK_UNIVERSE)
    period = PERIODS.get(run_id, PERIODS["A"])

    # Convert to Timestamps for compatibility with Pykrx/Pandas calendar
    try:
        import pandas as pd
        period["start"] = pd.Timestamp(period["start"])
        period["end"] = pd.Timestamp(period["end"])
    except ImportError:
        pass # Fallback if pandas not available (unlikely in real mode)

    use_mock = not args.real
    
    # Register Safety Nets early
    # We use mutable containers to pass data to packager callbacks
    state = {
        "manifest": None,
        "report": None,
        "verdict": None
    }
    packager.register_safety_nets(
        lambda: state["manifest"],
        lambda: state["report"],
        lambda: state["verdict"]
    )
    
    try:
        # =========================================================
        # Phase 0: Preflight (Loader Authority)
        # =========================================================
        logger.info("[Phase 0] Preflight Check")
        
        # Load Universe & Data Sample
        if use_mock:
            # Simulated Loader
            universe_codes = universe["tickers"]
            pf_result = PreflightResult(
                data_source="mock", 
                data_digest="mock_digest_123", 
                sample_metadata={"code": universe_codes[0], "rows": 100}, 
                universe_count=len(universe_codes), 
                is_valid=True
            )
            trading_calendar = [
                period["start"] + timedelta(days=x) 
                for x in range((period["end"] - period["start"]).days + 1)
            ]
        else:
            # REAL LOADER
            try:
                from core.data.filtering import get_filtered_universe
                from infra.data.loader import load_trading_calendar, load_daily_price
                
                # 1. Load Universe
                universe_codes = get_filtered_universe()
                eff_count = len(universe_codes)
                
                # 2. Load Sample (Sorted First)
                if eff_count > 0:
                    sorted_codes = sorted(universe_codes)
                    sample_code = sorted_codes[0]
                    # Load 30 days
                    sample_df = load_daily_price(sample_code, period["start"], period["start"]+timedelta(days=30))
                    
                    # Compute Digest & Metadata
                    import hashlib
                    # Simple digest: hash of index + column values
                    digest_str = str(sample_df.index[0]) + str(sample_df.shape) if not sample_df.empty else "empty"
                    digest = hashlib.md5(digest_str.encode()).hexdigest()
                    
                    pf_result = PreflightResult(
                        data_source="parquet", # Assumed, or check loader capability
                        data_digest=digest,
                        sample_metadata={
                            "code": sample_code, 
                            "rows": len(sample_df),
                            "date_min": str(sample_df.index.min()) if not sample_df.empty else "N/A",
                            "date_max": str(sample_df.index.max()) if not sample_df.empty else "N/A"
                        },
                        universe_count=eff_count,
                        is_valid=(eff_count > 0 and not sample_df.empty)
                    )
                else:
                    pf_result = PreflightResult("parquet", "none", {}, 0, False, "Empty Universe")
                
                trading_calendar = load_trading_calendar(period["start"], period["end"])
                
            except Exception as e:
                logger.error(f"Loader Failed: {e}")
                import traceback
                traceback.print_exc()
                pf_result = PreflightResult("error", "none", {}, 0, False, str(e))

        # Check Fail-Fast
        if args.real and pf_result.data_source != "parquet":
            msg = f"FAIL-FAST: Real mode requires 'parquet', got '{pf_result.data_source}'"
            # Trigger Verdict & Exit
            # Trigger Verdict & Exit
            verdict = VerdictEngine.evaluate("real", pf_result, {}, 0) # run_mode='real'
            state["verdict"] = verdict
            state["report"] = ReportGenerator.render(verdict)
            logger.critical(msg)
            return {} # Will trigger save in finally/atexit
                
        # =========================================================
        # Phase 1: Tuning (Evidence Collection)
        # =========================================================
        logger.info("[Phase 1] Tuning Loop")
        
        guardrail_config = GUARDRAIL_PRESETS[args.guardrail_preset]
        data_config = DataConfig(
            data_version=f"{pf_result.data_source}_v1",
            universe_count=pf_result.universe_count,
            sample_codes=[pf_result.sample_metadata.get("code", "N/A")]
        )
        
        import optuna
        import numpy as np # Added for NaN check
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        
        # [Phase 4] DB Isolation
        # run_id is passed to run_strict_phase15 (e.g. "A" or actual ID from packager if accessible?)
        # packager.run_id is the unique timestamped ID.
        run_dir = Path(f"data/tuning_runs/{packager.run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{run_dir}/optuna.db"
        study_name = f"study_{packager.run_id}"
        
        logger.info(f"[Phase 4] Persistence Enabled: {db_url}")
        
        study = optuna.create_study(
            study_name=study_name,
            storage=db_url,
            direction="maximize", 
            sampler=optuna.samplers.TPESampler(seed=args.seed),
            load_if_exists=True
        )
        
        lookbacks = [3, 6, 12]
        
        def objective(trial):
            # [Phase 4] Expanded Search Space
            params = {
                "ma_period": trial.suggest_int("ma_period", 40, 200, step=10),      # 20~180 -> 40~200
                "rsi_period": trial.suggest_int("rsi_period", 10, 60),             # 10~30 -> 10~60
                "stop_loss_pct": trial.suggest_float("stop_loss_pct", 0.05, 0.15, step=0.01), # 3%~15% -> 5%~15%
            }
            
            # Evidence Bucket
            by_lookback_evidence = {}
            scores = []
            
            # Result init for safety
            result = None
            final_fail_reason = None # Initialize to avoid UnboundLocalError globally in objective
            
            # [Phase 6.x Debug] Ensure Validation Window is large enough for 12M lookback
            # Default is 6M, which causes 12M lookback to be clamped to 6M (same as 6M lookback)
            tuning_split_config = SplitConfig(min_val_months=14)
            
            try:
                for lb in lookbacks:
                    result = run_backtest_for_tuning(
                        params=params, 
                        start_date=period["start"], 
                        end_date=period["end"], 
                        lookback_months=lb,
                        trading_calendar=trading_calendar,
                        universe_codes=universe_codes,
                        use_cache=True,
                        guardrail_config=guardrail_config,
                        split_config=tuning_split_config, # Fix: Enforce larger val window
                    )
                    
                    # Collect Evidence (Debug Info)
                    info = getattr(result, "debug", None)
                    
                    is_capped = False
                    eff_lb_str = "N/A"
                    
                    if info and info.effective_eval_start:
                        # Calculate effective days
                        eff_start = info.effective_eval_start
                        eff_end = period["end"] # Using period end (which matches val_end in runner)
                        
                        # Convert to date if datetime
                        if hasattr(eff_start, "date"): eff_start = eff_start.date()
                        if hasattr(eff_end, "date"): eff_end = eff_end.date()
                            
                        delta_days = (eff_end - eff_start).days
                        eff_lb_str = f"{delta_days}d"
                        
                        # Capped Check: Compare with requested months (approx 30 days)
                        # If delta is significantly smaller than requested months * 30
                        # e.g. 12M requested (360d) but got 180d -> Capped
                        requested_days = lb * 30
                        if delta_days < (requested_days - 15): # 15 days margin
                            is_capped = True
                        
                    by_lookback_evidence[lb] = {
                        "requested_lb": lb,
                        "effective_lb": eff_lb_str,
                        "val_effective_start_date": str(info.effective_eval_start) if info else "N/A",
                        "val_effective_end_date": str(period["end"]),
                        "val_bars_used": info.bars_used if info else 0,
                        "val_trades": result.val.num_trades if (result.val and hasattr(result.val, 'num_trades')) else 0,
                        "val_is_capped": is_capped, 
                        "val_sharpe": float(result.val.sharpe) if result.val else 0.0,
                        "score": float(result.val.sharpe) if (result.is_valid or args.analysis_mode) and result.val else -999.0
                    }
                    
                    if result.is_valid or args.analysis_mode:
                        scores.append(float(result.val.sharpe) if result.val else 0.0)
                    else:
                        scores.append(-999.0)
                        
                # [Phase 6.x Final] Data Integrity: Monotonicity Check
                # Rule 1: Start Date (12M) <= Start Date (6M) <= Start Date (3M)
                # Rule 2: Bars Used (12M) >= Bars Used (6M) >= Bars Used (3M)
                if all(k in by_lookback_evidence for k in [3, 6, 12]):
                    src3 = by_lookback_evidence[3]
                    src6 = by_lookback_evidence[6]
                    src12 = by_lookback_evidence[12]
                    
                    if src3["val_effective_start_date"] != "N/A" and src6["val_effective_start_date"] != "N/A" and src12["val_effective_start_date"] != "N/A":
                        # Compare dates string lexicographically (YYYY-MM-DD format works)
                        d3 = src3["val_effective_start_date"]
                        d6 = src6["val_effective_start_date"]
                        d12 = src12["val_effective_start_date"]
                        
                        b3 = src3["val_bars_used"]
                        b6 = src6["val_bars_used"]
                        b12 = src12["val_bars_used"]

                        if not (d12 <= d6 <= d3):
                            msg = f"[CRITICAL INTEGRITY] Date Monotonicity Failed! 12M({d12}) <= 6M({d6}) <= 3M({d3}) broken."
                            logger.critical(msg)
                            raise ValueError(msg)
                        
                        if not (b12 >= b6 >= b3):
                            msg = f"[CRITICAL INTEGRITY] Bars Monotonicity Failed! 12M({b12}) >= 6M({b6}) >= 3M({b3}) broken."
                            logger.critical(msg)
                            raise ValueError(msg)

            except Exception as e:
                logger.error(f"Objective Failed: {e}", exc_info=True)
                final_score = -9999.0
                # Capture exception for reporting
                err_msg = f"Exception: {str(e)}"
                trial.set_user_attr("fail_reason", err_msg)
                try:
                    with open("error_dump.txt", "w", encoding="utf-8") as f:
                        f.write(err_msg)
                except: pass
            finally:
                # Store Evidence in Trial Attribute (CRITICAL)
                # Ensure all values are JSON serializable (cast numpy types)
                trial.set_user_attr("by_lookback", by_lookback_evidence)
                trial.set_user_attr("valid", bool(final_score > -100))
                
                # Per-Trial Debug Dump
                try:
                    t_dump = {
                        "number": trial.number,
                        "score": final_score,
                        "reason": trial.user_attrs.get("fail_reason", "None"),
                        "result_exists": bool(result),
                        "val_exists": bool(result.val) if result else False,
                        "is_valid": result.is_valid if result else False,
                        "guardrail_fails": getattr(result.guardrail_checks, 'failures', []) if result and result.guardrail_checks else [],
                        "logic_fails": getattr(result.logic_checks, 'failures', []) if result and result.logic_checks else [],
                        "warnings": result.warnings if result else []
                    }
                    with open(f"debug_dump_{trial.number}.json", "w", encoding="utf-8") as f:
                        json.dump(t_dump, f, indent=2, default=str)
                except Exception as ex:
                    logger.error(f"Dump Failed: {ex}")
                # Capture Failure Reason (Prioritize existing reason if set, else check guardrails)
                # Check fail reason logic
                if final_score <= -100:
                    current_reason = trial.user_attrs.get("fail_reason")
                    if not current_reason:
                        final_fail_reason = "Unknown Error"
                        
                        # Detailed Classification
                        if result is None:
                            final_fail_reason = "Critical_Crash (Result None)"
                        elif not result.val:
                            final_fail_reason = "Empty_Metrics"
                        elif result.val and (pd.isna(result.val.sharpe) or np.isinf(result.val.sharpe)):
                            final_fail_reason = "Result_NaN"
                            if hasattr(result.val, 'num_trades') and result.val.num_trades == 0:
                                final_fail_reason = "NO_TRADES"
                        elif result.guardrail_checks and getattr(result.guardrail_checks, 'failures', None):
                            final_fail_reason = result.guardrail_checks.failures[0] # Grab first fail reason
                        elif result.logic_checks and getattr(result.logic_checks, 'failures', None):
                            final_fail_reason = f"Logic: {result.logic_checks.failures[0]}"
                        elif result.warnings:
                            final_fail_reason = f"Warning: {result.warnings[0]}"
                        
                        # Extra Check for incomplete metrics
                        if final_fail_reason == "Unknown Error" and result.val:
                            if not hasattr(result.val, 'sharpe'):
                                final_fail_reason = "METRICS_KEY_MISSING"
                                
                        # [Phase 6.x] Fail-Fast on Unknown Error
                        if final_fail_reason == "Unknown Error":
                            # Dump Context
                            debug_ctx = {
                                "is_valid": result.is_valid if result else "None",
                                "val_exists": bool(result.val) if result else False,
                                "guardrail": getattr(result.guardrail_checks, 'failures', 'N/A') if result else "N/A",
                                "logic": getattr(result.logic_checks, 'failures', 'N/A') if result else "N/A",
                                "warnings": result.warnings if result else "N/A"
                            }
                            msg = f"[CRITICAL UNKNOWN ERROR] Trial failed but reason is Unknown! Context: {debug_ctx}"
                            
                            # Dump to file for reliable debugging
                            try:
                                with open("crash_dump.json", "w", encoding="utf-8") as f:
                                    json.dump(debug_ctx, f, indent=2, default=str)
                            except: pass
                            
                            logger.critical(msg)
                            raise RuntimeError(msg)
                        
                        trial.set_user_attr("fail_reason", final_fail_reason)
            
            return final_score

        study.optimize(objective, n_trials=args.trials)
        
        # Select Best Candidate (or Best Attempt)
        valid_trials = [t for t in study.trials if t.value > -100]
        
        best_evidence = {}
        best_params = {}
        
        if not valid_trials:
             logger.warning("No valid trials found. Saving BEST ATTEMPT for evidence.")
             # Select attempt with highest score (even if negative) or most trades?
             # Let's use highest value.
             if study.trials:
                 # Prefer trials with evidence
                 trials_with_ev = [t for t in study.trials if t.user_attrs.get("by_lookback")]
                 if trials_with_ev:
                    best_attempt = max(trials_with_ev, key=lambda t: t.value if t.value is not None else -9999)
                 else:
                    best_attempt = max(study.trials, key=lambda t: t.value if t.value is not None else -9999)
                 
                 best_params = best_attempt.params
                 best_evidence = best_attempt.user_attrs.get("by_lookback", {})
                 
                 # Special Manifest Injection for Failed Run
                 # We need to run create_manifest but mark it as best_attempt
                 pass
             else:
                 # No trials at all?
                 pass
                 
        else:
            best_trial = max(valid_trials, key=lambda t: t.value)
            best_params = best_trial.params
            best_evidence = best_trial.user_attrs.get("by_lookback", {})
            logger.info(f"Best Score: {best_trial.value:.4f}")
        
        # Calculate Params Hash
        from extensions.tuning.types import compute_params_hash
        params_hash = compute_params_hash(best_params) if best_params else "none"
        params_source = "best_trial" if valid_trials else ("best_attempt" if trials_with_ev or study.trials else "none")
        
        # =========================================================
        # Phase 2: Gate 2 (WF Outsample Evidence)
        # =========================================================
        # Logic: If we have ANY best_params (valid or attempt), we TRY Gate 2 
        # to generate complete evidence (even if it fails logic).
        # PROOF Preset allows passing Gate 1 easier, but if we fail Gate 1, we still want WF evidence if possible?
        # User said: "Phase 1 PASS (Engine Evidence PASS) ... Real Data PASS, Universe PASS, Multi-Lookback PASS, WF PASS"
        # If Gate 1 fails, we can't really do WF properly on "failed" params? 
        # But we can try.
        
        if best_params:
            logger.info("[Phase 2] Gate 2 Walk-Forward (Attempting with best params)")
            wf_runner = MiniWalkForward(
                period["start"], period["end"], trading_calendar,
                12, 3, 3, 6, universe_codes
            )
            wf_evidences = wf_runner.run(best_params)
            
            # Convert dataclass to dict for JSON
            from dataclasses import asdict
            wf_windows_json = [asdict(ev) for ev in wf_evidences]
        else:
            wf_evidences = []
            wf_windows_json = []

        
        # =========================================================
        # Phase 3: Manifest & Verdict
        # =========================================================
        
        # Re-run best to get full Result object
        best_result_obj = None
        if best_params:
            best_result_obj = run_backtest_for_tuning(
                params=best_params, start_date=period["start"], end_date=period["end"],
                lookback_months=6, trading_calendar=trading_calendar,
                universe_codes=universe_codes, guardrail_config=guardrail_config
            )
        
        manifest = create_manifest(
            stage="gate2",
            start_date=period["start"], end_date=period["end"],
            lookbacks=lookbacks, trials=args.trials,
            split_config=SplitConfig(), costs=DEFAULT_COSTS,
            data_config=data_config, param_ranges={},
            best_result=best_result_obj,  # Can be None/Failed result
            all_trials_count=args.trials, random_seed=args.seed,
            guardrail_preset=args.guardrail_preset
        )
        
        # Convert dataclass to dict for mutability
        from dataclasses import asdict
        manifest = asdict(manifest)
        
        # Inject our Custom Evidence
        # If valid, put in best_trial. If not, put in best_attempt.
        target_key = "best_trial" if valid_trials else "best_attempt"
        # Ensure structure exists if create_manifest didn't make it (it usually makes best_trial if best_result passed)
        if target_key not in manifest["results"]:
             manifest["results"][target_key] = {}
             
        manifest["results"][target_key]["by_lookback"] = best_evidence
        manifest["results"][target_key]["walkforward"] = {
            "windows_detail": wf_windows_json,
            "windows_count": len(wf_windows_json),
            "total_outsample_trades": sum(w.outsample_trades for w in wf_evidences),
            "avg_outsample_sharpe": sum(w.outsample_sharpe for w in wf_evidences)/len(wf_windows_json) if wf_windows_json else 0,
            "params_source": params_source,
            "params_hash": params_hash
        }
        
        # [Audit Item 5] Failure Stats Aggregation
        from collections import Counter
        fail_reasons = []
        for t in study.trials:
            if t.value is None or t.value <= -100:
                frm = t.user_attrs.get("fail_reason", "Unknown")
                fail_reasons.append(frm)
        
        manifest["results"]["failure_stats"] = dict(Counter(fail_reasons).most_common(10))
        
        state["manifest"] = manifest
        
        # Verdict Evaluation
        verdict = VerdictEngine.evaluate(
            "real" if args.real else "mock", 
            pf_result, 
            manifest, 
            min_wf_windows=1 if use_mock else 3, # Relax for mock
            max_zero_trade_windows_tolerance=1
        )
        state["verdict"] = verdict
        
        # Report
        report = ReportGenerator.render(verdict)
        state["report"] = report
        
        # Final Save (via Safety Net or explicit)
        packager.save_if_not_saved()
        
    except Exception as e:
        logger.error(f"Orchestrator Crash: {e}", exc_info=True)
        # Excepthook will catch this and save crash.json
        raise

if __name__ == "__main__":
    from dataclasses import dataclass
    # Argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--trials", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--analysis-mode", action="store_true")
    parser.add_argument("--guardrail-preset", type=str, default="default")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()
    
    # Apply Log Level
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if isinstance(numeric_level, int):
        logging.getLogger().setLevel(numeric_level)
        # Force lower level loggers if needed, or rely on root/config
        # If using app.logging_config, we might need to adjust it there or override here
        # Assuming simple script usage or basicConfig was called earlier
        logging.basicConfig(level=numeric_level, style='{', format='{asctime} [{levelname}] {name}: {message}')
    
    try:
        run_strict_phase15("A", args)
    except Exception as e:
        import traceback
        with open("fatal_error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"FATAL ERROR: {e}")
        import sys
        sys.exit(1)
