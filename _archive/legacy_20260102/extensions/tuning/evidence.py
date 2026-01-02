# -*- coding: utf-8 -*-
"""
extensions/tuning/evidence.py
Phase 1 Evidence-Based Completion Infrastructure (v2.2.1)

Core Components:
1. ResultPackager: 3-layer safety net for Artifact saving.
2. PreflightCheck: Loader-authoritative validation.
3. VerdictEngine: Strict automated verification logic.
4. ReportGenerator: Fixed-template reporting.
"""
import sys
import os
import json
import logging
import traceback
import atexit
import subprocess
import platform
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)

# --- 1. Result Packager ---
class ResultPackager:
    def __init__(self, output_root: Path = Path("data/tuning_runs")):
        self.run_id = self._generate_run_id()
        self.run_dir = output_root / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.run_dir / "run.log"
        self._setup_file_logging()
        
        self._saved = False
        
        # Context recording
        self.context = {
            "run_id": self.run_id,
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "platform": platform.platform(),
            "command_line": " ".join(sys.argv),
            "git_hash": self._get_git_hash(),
        }
        
    def _generate_run_id(self) -> str:
        import hashlib
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        h = hashlib.md5(f"{ts}_{now.microsecond}".encode()).hexdigest()[:6]
        return f"real_{ts}_{h}" # Prefix 'real_' helps identification, though strictly run mode matters
        
    def _get_git_hash(self) -> str:
        try:
            return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
        except:
            return "unknown"
            
    def _setup_file_logging(self):
        # Force FileHandler to root logger
        root = logging.getLogger()
        fh = logging.FileHandler(self.log_file, mode='w', encoding='utf-8')
        fmt = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        fh.setFormatter(fmt)
        root.addHandler(fh)
        
        # Print location
        print(f"[ResultPackager] RunID: {self.run_id}")
        print(f"[ResultPackager] Logging to: {self.log_file}")
        
    def register_safety_nets(self, manifest_getter, report_getter, verdict_getter):
        """
        Register callbacks to retrieve latest state for saving.
        We use getters because the objects might be updated until the very end.
        """
        self._manifest_getter = manifest_getter
        self._report_getter = report_getter
        self._verdict_getter = verdict_getter
        
        # 2. sys.excepthook
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._excepthook_handler
        
        # 3. atexit
        atexit.register(self.save_if_not_saved)
        
    def _excepthook_handler(self, exc_type, exc_value, exc_traceback):
        logger.critical("Uncaught Exception:", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Save crash dump
        crash_data = {
            "error_type": str(exc_type.__name__),
            "error_msg": str(exc_value),
            "traceback": "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        }
        try:
            with open(self.run_dir / "crash.json", "w", encoding="utf-8") as f:
                json.dump(crash_data, f, indent=2, ensure_ascii=False)
        except:
            print("Failed to save crash.json")
            
        self.save_if_not_saved()
        
        if self._original_excepthook:
            self._original_excepthook(exc_type, exc_value, exc_traceback)
            
    def save_if_not_saved(self):
        if self._saved:
            return
        
        try:
            logger.info("ResultPackager: Saving Artifacts...")
            
            # Get latest data (allowing for crash state)
            manifest = self._manifest_getter()
            verdict = self._verdict_getter() # Should include context
            report = self._report_getter()
            
            # Save Manifest
            if manifest:
                with open(self.run_dir / "manifest.json", "w", encoding="utf-8") as f:
                    # Handle object if it has to_dict/json, else dump
                    if hasattr(manifest, "to_dict"):
                        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False, default=str)
                    else:
                        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
            
            # Save Verdict
            if verdict:
                # Inject context and artifacts paths if missing
                if "meta" not in verdict: verdict["meta"] = self.context
                if "artifacts" not in verdict:
                    verdict["artifacts"] = {
                        "run_log": "run.log",
                        "manifest": "manifest.json",
                        "verdict": "verdict.json",
                        "report": "report.md",
                        "crash": "crash.json" if (self.run_dir / "crash.json").exists() else None
                    }
                
                with open(self.run_dir / "verdict.json", "w", encoding="utf-8") as f:
                    json.dump(verdict, f, indent=2, ensure_ascii=False)
            
            # Save Report
            if report:
                with open(self.run_dir / "report.md", "w", encoding="utf-8") as f:
                    f.write(report)
                    
            print(f"\n[ResultPackager] RUN COMPLETE. Artifacts saved to: {self.run_dir}")
            
        except Exception as e:
            print(f"CRITICAL: Failed to save result pack: {e}")
            traceback.print_exc()
        finally:
            self._saved = True


# --- 2. Preflight Check ---
@dataclass
class PreflightResult:
    data_source: str
    data_digest: str
    sample_metadata: Dict[str, Any]
    universe_count: int
    is_valid: bool
    fail_reason: Optional[str] = None

class PreflightCheck:
    @staticmethod
    def run(loader_pkg, universe_codes: List[str], sample_code_hint: str = None) -> PreflightResult:
        """
        Loader Authoritative Check.
        loader_pkg: infra.data.loader module (mocked or real)
        """
        # 1. Universe Check
        eff_count = len(universe_codes)
        if eff_count == 0:
            return PreflightResult("unknown", "", {}, 0, False, "Effective universe is empty")

        # 2. Sample Load (Deterministic)
        sorted_codes = sorted(universe_codes)
        sample_code = sample_code_hint if sample_code_hint else sorted_codes[0]
        
        try:
            # Inspection Prohibited: Must use loader return
            # Assuming loader HAS a way to tell us source? 
            # If not, we deduce from data? 
            # User requirement: "Loader Authority... loader MUST return source"
            # We might need to wrap loader call or inspect the returned object metadata if the loader doesn't provide explicit source API yet.
            # But the plan says "Update Loader to return Source". So we assume strict contract or we fix loader.
            # For now, we will perform load and check attributes if possible, or assume based on import path used? 
            # No, 'data_version' in config is a hint, but we need proof. 
            pass 
        except:
            pass
            
        # Mock implementation for now as we haven't modified loader yet.
        # But we need to support the check.
        # We will implement logic in the script to call loader and wrap it.
        return PreflightResult(
            data_source="pending_check_in_script", 
            data_digest="pending", 
            sample_metadata={"code": sample_code}, 
            universe_count=eff_count, 
            is_valid=True
        )


# --- 3. Verdict Engine ---
class VerdictEngine:
    @staticmethod
    def evaluate(
        run_mode: str, 
        preflight: PreflightResult, 
        manifest_data: Dict,
        min_wf_windows: int = 3,
        max_zero_trade_windows_tolerance: int = 1
    ) -> Dict:
        checks = {}
        verdict = "PASS"
        grade = "PASS"
        top_reasons = []

        # 1. Real Data Evidence
        check_real = {"status": "PASS", "evidence": f"Source: {preflight.data_source}"}
        if run_mode == "today" or run_mode == "real": # '--real' maps to appropriate mode string
            if preflight.data_source != "parquet":
                check_real["status"] = "FAIL"
                check_real["reason"] = f"Real mode requires 'parquet' source, got '{preflight.data_source}'"
                verdict = "FAIL"
                grade = "FAIL"
                top_reasons.append(check_real["reason"])
            if not preflight.is_valid:
                 check_real["status"] = "FAIL"
                 check_real["reason"] = preflight.fail_reason
                 verdict = "FAIL"
                 grade = "FAIL"
                 top_reasons.append(preflight.fail_reason)
        checks["real_data"] = check_real

        # 2. Universe
        check_uni = {"status": "PASS", "evidence": f"Count: {preflight.universe_count}"}
        if preflight.universe_count < 5:
            check_uni["status"] = "FAIL"
            check_uni["reason"] = f"Universe count {preflight.universe_count} < 5"
            verdict = "FAIL" # Strict? User said effective>=5
            top_reasons.append(check_uni["reason"])
        checks["universe"] = check_uni

        # 3. Multi-Lookback Monotonicity & Evidence
        # Evidence must exist even if trial failed.
        # Check 'best_trial' OR 'best_attempt'
        best_data = manifest_data.get("results", {}).get("best_trial")
        # Failover to best_attempt if best_trial missing OR missing evidence (while attempt has it)
        attempt_data = manifest_data.get("results", {}).get("best_attempt")
        if not best_data or (not best_data.get("by_lookback") and attempt_data and attempt_data.get("by_lookback")):
            best_data = attempt_data
        
        check_lb = {"status": "PASS", "evidence": ""}
        results_found = False
        
        if not best_data:
             check_lb["status"] = "FAIL"
             check_lb["reason"] = "No trial/attempt evidence found"
             verdict = "FAIL"
             top_reasons.append(check_lb["reason"])
        else:
            by_lookback = best_data.get("by_lookback", {})
            required_lbs = [3, 6, 12]
            bl_norm = {int(k): v for k, v in by_lookback.items()}
            
            missing_lbs = [lb for lb in required_lbs if lb not in bl_norm]
            
            if missing_lbs:
                check_lb["status"] = "FAIL"
                check_lb["reason"] = f"Missing lookbacks: {missing_lbs}"
                verdict = "FAIL"
                top_reasons.append(check_lb["reason"])
            else:
                # Validate Fields & Monotonicity
                try:
                    # 12M <= 6M <= 3M
                    d12 = bl_norm[12].get("val_effective_start_date", "9999-99-99")
                    d6 = bl_norm[6].get("val_effective_start_date", "9999-99-99")
                    d3 = bl_norm[3].get("val_effective_start_date", "9999-99-99")
                    
                    c12 = bl_norm[12].get("val_is_capped", False)
                    c6 = bl_norm[6].get("val_is_capped", False)
                    
                    check_lb["evidence"] = f"Dates: 12M({d12}{'(C)' if c12 else ''}) <= 6M({d6}{'(C)' if c6 else ''}) <= 3M({d3})"
                    
                    # Sort check: d12 <= d6 <= d3
                    # If Capped, Equality is expected. If not capped, d12 < d6 preferred but <= is safe Hard constraint.
                    if not (d12 <= d6 <= d3):
                        check_lb["status"] = "FAIL"
                        check_lb["reason"] = f"Monotonicity violation: {check_lb['evidence']}"
                        verdict = "FAIL"
                        top_reasons.append(check_lb["reason"])
                        
                    # Check for Evidence Fields
                    for lb in required_lbs:
                        ev = bl_norm[lb]
                        if "val_bars_used" not in ev or "val_trades" not in ev:
                             check_lb["status"] = "FAIL"
                             check_lb["reason"] = f"Incomplete evidence fields for LB={lb}"
                             verdict = "FAIL"
                             top_reasons.append(check_lb["reason"])
                             break

                except Exception as e:
                    check_lb["status"] = "FAIL"
                    check_lb["reason"] = f"Data error: {e}"
                    verdict = "FAIL"
                    
        checks["multi_lookback"] = check_lb

        # 4. Walk-Forward Presence
        check_wf_p = {"status": "PASS", "evidence": "Results Found"}
        wf_data = best_data.get("walkforward") if best_data else None
        
        if not wf_data:
             check_wf_p["status"] = "FAIL"
             check_wf_p["reason"] = "WF not executed (No data)"
             verdict = "FAIL"
             top_reasons.append(check_wf_p["reason"])
             checks["walkforward_presence"] = check_wf_p
             checks["walkforward_validity"] = {"status": "FAIL", "evidence": "", "reason": "Skipped (No WF data)"}
        else:
            # Strict Presence Check: Must have list AND meet min_windows
            windows = wf_data.get("windows_detail", [])
            if len(windows) < min_wf_windows:
                 check_wf_p["status"] = "FAIL"
                 check_wf_p["reason"] = f"WF executed but windows {len(windows)} < {min_wf_windows}"
                 verdict = "FAIL"
                 top_reasons.append(check_wf_p["reason"])
                 checks["walkforward_presence"] = check_wf_p
                 checks["walkforward_validity"] = {"status": "FAIL", "evidence": "", "reason": "Skipped (Low windows)"}
            else:
                 checks["walkforward_presence"] = check_wf_p
                 
                 # 5. Walk-Forward Validity
                 check_wf_v = {"status": "PASS", "evidence": ""}
                 # Check Bars > 0
                 zero_bars = [i for i, w in enumerate(windows) if w.get("outsample_bars", 0) <= 0]
                 if zero_bars:
                    check_wf_v["status"] = "FAIL"
                    check_wf_v["reason"] = f"Windows {zero_bars} have 0 bars"
                    verdict = "FAIL"
                    top_reasons.append(check_wf_v["reason"])
                 else:
                    # Check Trades
                    zero_trades_count = sum(1 for w in windows if w.get("outsample_trades", 0) == 0)
                    global_trades = sum(w.get("outsample_trades", 0) for w in windows)
                    
                    check_wf_v["evidence"] = f"Windows:{len(windows)}, ZeroTradeWins:{zero_trades_count}, GlobalTrades:{global_trades}"

                    if global_trades == 0:
                        check_wf_v["status"] = "FAIL"
                        check_wf_v["reason"] = "Global Outsample Trades = 0"
                        verdict = "FAIL"
                        top_reasons.append(check_wf_v["reason"])
                    elif zero_trades_count > max_zero_trade_windows_tolerance:
                        check_wf_v["status"] = "FAIL"
                        check_wf_v["reason"] = f"Zero trade windows {zero_trades_count} > tolerance {max_zero_trade_windows_tolerance}"
                        verdict = "FAIL"
                        top_reasons.append(check_wf_v["reason"])
                    elif zero_trades_count > 0:
                         check_wf_v["reason"] = f"Zero trade windows {zero_trades_count} within tolerance"
                         grade = "WARN"
                         verdict = "FAIL" 
                         top_reasons.append(f"WF Warning: {check_wf_v['reason']}")
            
            checks["walkforward_validity"] = check_wf_v

        if verdict == "PASS":
            grade = "PASS" # Reinforced
        
        # Populate Meta from Manifest if available
        meta = {}
        if manifest_data:
             meta = manifest_data.get("meta", {})
             # Flatten from manifest root if needed
             if "run_id" not in meta:
                 meta["run_id"] = manifest_data.get("run_id", "Unknown")
        
        # Diagnostics Extraction (Phase 2)
        diagnostics = {}
        if wf_data:
            # Aggregate counters from windows
            # manifest.walkforward.windows_detail is a list of dicts
            windows = wf_data.get("windows_detail", [])
            raw = sum(w.get("raw_signal_count", 0) for w in windows)
            filt = sum(w.get("filtered_signal_count", 0) for w in windows)
            exec_t = sum(w.get("outsample_trades", 0) for w in windows)
            
            diagnostics = {
                "raw_signal_count": raw,
                "filtered_signal_count": filt,
                "executed_trades": exec_t
            }
        
        return {
            "verdict": verdict,
            "grade": grade,
            "checks": checks,
            "top_reasons": top_reasons,
            "meta": meta,
            "diagnostics": diagnostics,
            "artifacts": {
                "run_log": "run.log",
                "manifest": "manifest.json",
                "verdict": "verdict.json",
                "report": "report.md",
                "crash": None
            }
        }

# --- 4. Report Generator ---
class ReportGenerator:
    @staticmethod
    def render(verdict: Dict) -> str:
        v = verdict
        meta = v.get("meta", {})
        checks = v.get("checks", {})
        
        # Header
        icon = "✅" if v["verdict"] == "PASS" else ("⚠️" if v["grade"]=="WARN" else "❌")
        report = f"# Tuning Engine Phase 1 Verification Report\n\n"
        report += f"## Verdict: {icon} {v['verdict']} (Grade: {v['grade']})\n"
        
        if v.get("top_reasons"):
            report += "### Top Failure Reasons\n"
            for r in v["top_reasons"]:
                report += f"- {r}\n"
        report += "\n"
        
        # Run Info
        report += "## Run Context\n"
        report += f"- **Run ID**: `{meta.get('run_id')}`\n"
        report += f"- **Mode**: `{meta.get('command_line')}`\n"
        report += f"- **Git**: `{meta.get('git_hash')}`\n\n"
        
        # Evidence Summary
        report += "## Evidence Checklist\n"
        report += "| Check | Status | Evidence/Reason |\n"
        report += "| :--- | :--- | :--- |\n"
        for key, res in checks.items():
            icon_c = "✅" if res["status"] == "PASS" else ("⚠️" if res["status"]=="WARN" else "❌")
            reason = res.get("reason", res.get("evidence", "-"))
            report += f"| {key} | {icon_c} {res['status']} | {reason} |\n"
            
        # Zero Trade Autopsy (Phase 2 Diagnostic)
        if v.get("diagnostics"):
            report += "\n---\n"
            report += "## Zero Trade Autopsy (Funnel)\n"
            report += "| Metric | Count | Interpretation |\n"
            report += "| :--- | :--- | :--- |\n"
            diag = v["diagnostics"]
            report += f"| 1. Raw Signals | {diag.get('raw_signal_count', 'N/A')} | MA/RSI 조건 만족 횟수 |\n"
            report += f"| 2. Filtered Signals | {diag.get('filtered_signal_count', 'N/A')} | Liquidity/TopN 필터 통과 |\n"
            report += f"| 3. Executed Trades | {diag.get('executed_trades', 'N/A')} | 실제 체결 횟수 |\n"
            
        # Freeze Declaration
        if v["verdict"] == "PASS":
            report += "\n---\n"
            report += "### ❄️ Phase 1 Freeze Declaration\n"
            report += "> Phase 1 Freeze: 본 run에서 verdict=PASS 달성 시, Phase 1 엔진/증거 스키마는 동결하며 이후 변경은 (A) 재현성 붕괴 또는 (B) WF 결과-로직 불일치가 발생할 때만 허용한다.\n"
            
        return report
