#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app/run_tune.py — P167-R Optuna 튜닝 CLI 진입점

실행:
  python -m app.run_tune --mode quick --n-trials 50 --seed 42
  python -m app.run_tune --mode full --n-trials 100 --timeout-sec 3600

입력:
  state/strategy_bundle/latest/strategy_bundle_latest.json → universe, 기간

출력:
  reports/tune/latest/tune_result.json
  reports/tune/snapshots/tune_result_YYYYMMDD_HHMMSS.json
  reports/tune/telemetry/tune_YYYYMMDD_HHMMSS.jsonl
"""
from __future__ import annotations
import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
import traceback
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.run_tune")

# ─── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_PATH = PROJECT_ROOT / "state" / "strategy_bundle" / "latest" / "strategy_bundle_latest.json"
RESULT_LATEST = PROJECT_ROOT / "reports" / "tune" / "latest" / "tune_result.json"
RESULT_SNAPSHOTS = PROJECT_ROOT / "reports" / "tune" / "snapshots"

from app.run_backtest import load_params_with_fallback

KST = timezone(timedelta(hours=9))


# ─── 1. Strategy Bundle ──────────────────────────────────────────────────
def load_strategy_bundle() -> Dict[str, Any]:
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Strategy bundle not found: {BUNDLE_PATH}")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_tune_config(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """번들에서 튜닝에 필요한 설정 추출"""
    strategy = bundle.get("strategy", {})
    return {
        "universe": strategy.get("universe", []),
        "momentum_period": strategy.get("lookbacks", {}).get("momentum_period", 20),
        "stop_loss": strategy.get("decision_params", {}).get("exit_threshold", -0.05),
        "max_positions": strategy.get("position_limits", {}).get("max_positions", 4),
    }


# ─── 2. Atomic Write ─────────────────────────────────────────────────────
def atomic_write_result(data: Dict[str, Any]) -> None:
    """Atomic write: tmp → rename → snapshot copy"""
    RESULT_LATEST.parent.mkdir(parents=True, exist_ok=True)
    RESULT_SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    content = json.dumps(data, indent=2, ensure_ascii=False)

    tmp_fd = tempfile.NamedTemporaryFile(
        mode="w", dir=RESULT_LATEST.parent,
        suffix=".tmp", delete=False, encoding="utf-8",
    )
    try:
        tmp_fd.write(content)
        tmp_fd.close()
        tmp_path = Path(tmp_fd.name)
        if RESULT_LATEST.exists():
            RESULT_LATEST.unlink()
        tmp_path.rename(RESULT_LATEST)
        logger.info(f"[WRITE] latest → {RESULT_LATEST}")
    except Exception:
        Path(tmp_fd.name).unlink(missing_ok=True)
        raise

    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    snap_path = RESULT_SNAPSHOTS / f"tune_result_{ts}.json"
    shutil.copy2(RESULT_LATEST, snap_path)
    logger.info(f"[WRITE] snapshot → {snap_path}")


# ─── 3. Main ─────────────────────────────────────────────────────────────
def run_cli_tune(mode: str = "full", n_trials: int = 50, seed: int = 42, timeout_sec: int = None) -> bool:
    """Run Optuna tuning programmatically. Returns True if successful."""
    logger.info("=" * 60)
    logger.info("P167-R Optuna Tuning Engine — CLI")
    logger.info("=" * 60)

    # ── 1. Load config ──
    try:
        params, param_source = load_params_with_fallback()
    except Exception as e:
        logger.error(f"Strategy params load failed: {e}")
        return False

    universe = params["universe"]
    if not universe:
        logger.error("Universe is empty!")
        return False

    # ── 2. Date range ──
    today = date.today()
    if mode == "quick":
        start = today - timedelta(days=180)
    else:
        start = today - timedelta(days=365 * 3)
    end = today - timedelta(days=1)

    logger.info(f"[CONFIG] universe={universe}, mode={mode}")
    logger.info(f"[CONFIG] period={start} → {end}, trials={n_trials}, seed={seed}")

    # ── 3. Prefetch OHLCV (1회) ──
    logger.info("=" * 60)
    logger.info("[PREFETCH] Downloading OHLCV data (this is the ONLY download phase)")
    logger.info("=" * 60)

    try:
        from app.backtest.infra.data_loader import prefetch_ohlcv
        price_data = prefetch_ohlcv(universe, start, end)
    except Exception as e:
        logger.error(f"Prefetch failed: {e}")
        traceback.print_exc()
        return False

    logger.info(f"[PREFETCH] Complete: {len(price_data)} rows")
    logger.info("=" * 60)
    logger.info("[TUNING] Starting Optuna optimization (NO more downloads)")
    logger.info("=" * 60)

    # ── 4. Optuna study ──
    try:
        import optuna
    except ImportError:
        logger.error("optuna 패키지 미설치. pip install optuna")
        sys.exit(1)

    from app.tuning.objective import TuneObjective
    from app.tuning.telemetry import TuneLogger

    run_id = f"tune_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    telemetry = TuneLogger(run_id)

    telemetry.emit_tune_start({
        "run_id": run_id,
        "mode": mode,
        "n_trials": n_trials,
        "seed": seed,
        "universe": universe,
        "start_date": str(start),
        "end_date": str(end),
        "timeout_sec": timeout_sec,
    })

    sampler = optuna.samplers.TPESampler(seed=seed)
    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        study_name=run_id,
    )

    objective = TuneObjective(
        price_data=price_data,
        universe=universe,
        start=start,
        end=end,
        telemetry=telemetry,
    )

    t0 = time.time()
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_sec,
        catch=(Exception,),
    )
    runtime_sec = time.time() - t0

    # ── 5. Collect results ──
    completed_trials = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]

    if not completed_trials:
        logger.error("[TUNE] No completed trials! All pruned or failed.")
        telemetry.emit_tune_end({"status": "FAIL", "reason": "no_completed_trials"})
        return False

    best = study.best_trial
    best_params = best.params
    best_score = best.value
    best_attrs = best.user_attrs

    # Top 10
    sorted_trials = sorted(completed_trials, key=lambda t: t.value, reverse=True)
    trials_top10 = []
    for t in sorted_trials[:10]:
        trials_top10.append({
            "trial": t.number,
            "score": round(t.value, 4),
            "params": t.params,
            "sharpe": t.user_attrs.get("sharpe", 0),
            "mdd_pct": t.user_attrs.get("mdd_pct", 0),
            "cagr": t.user_attrs.get("cagr", 0),
            "total_trades": t.user_attrs.get("total_trades", 0),
        })

    now_kst = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    tune_result = {
        "best_params": best_params,
        "best_score": round(best_score, 4),
        "best_summary": {
            "sharpe": best_attrs.get("sharpe", 0),
            "mdd_pct": best_attrs.get("mdd_pct", 0),
            "cagr": best_attrs.get("cagr", 0),
            "total_return": best_attrs.get("total_return", 0),
        },
        "best_total_trades": best_attrs.get("total_trades", 0),
        "trials_top10": trials_top10,
        "meta": {
            "asof": now_kst,
            "run_id": run_id,
            "mode": mode,
            "start_date": str(start),
            "end_date": str(end),
            "universe": universe,
            "n_trials": n_trials,
            "completed_trials": len(completed_trials),
            "pruned_trials": len(study.trials) - len(completed_trials),
            "seed": seed,
            "runtime_sec": round(runtime_sec, 1),
            "param_source": param_source,
        },
    }

    # ── 6. Write results ──
    try:
        atomic_write_result(tune_result)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        return False

    telemetry.emit_tune_end({
        "status": "OK",
        "best_score": round(best_score, 4),
        "best_params": best_params,
        "completed_trials": len(completed_trials),
        "runtime_sec": round(runtime_sec, 1),
    })

    # ── 7. Summary ──
    logger.info("=" * 60)
    logger.info(f"[RESULT: OK] best_score={best_score:.4f}")
    logger.info(f"  best_params: {best_params}")
    logger.info(f"  sharpe={best_attrs.get('sharpe', 0):.4f}  "
                f"mdd={best_attrs.get('mdd_pct', 0):.2f}%  "
                f"cagr={best_attrs.get('cagr', 0):.4f}")
    logger.info(f"  completed={len(completed_trials)}/{len(study.trials)}  "
                f"runtime={runtime_sec:.1f}s")
    logger.info(f"  telemetry: {telemetry.filepath}")
    logger.info("=" * 60)
    print(f"[RESULT: OK] tuning completed → {RESULT_LATEST}")
    return True

def main():
    parser = argparse.ArgumentParser(description="P167-R Optuna Tuning CLI")
    parser.add_argument("--mode", choices=["quick", "full"], default="full",
                        help="quick: 6M, full: 3Y")
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout-sec", type=int, default=None,
                        help="Optuna timeout (seconds)")
    args = parser.parse_args()

    success = run_cli_tune(mode=args.mode, n_trials=args.n_trials, seed=args.seed, timeout_sec=args.timeout_sec)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
