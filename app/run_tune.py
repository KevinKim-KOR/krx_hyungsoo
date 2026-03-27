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
  reports/tuning/tuning_results.json
  reports/tuning/snapshots/tuning_results_YYYYMMDD_HHMMSS.json
  reports/tuning/tuning_summary.md
  reports/tuning/promotion_verdict.json
"""

from __future__ import annotations
import argparse
import json
import logging
import sys
import time
import traceback
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.run_tune")

# ─── Paths ────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_PATH = (
    PROJECT_ROOT
    / "state"
    / "strategy_bundle"
    / "latest"
    / "strategy_bundle_latest.json"
)
PARAMS_SSOT_PATH = (
    PROJECT_ROOT / "state" / "params" / "latest" / "strategy_params_latest.json"
)
BACKTEST_RESULT_LATEST = (
    PROJECT_ROOT / "reports" / "backtest" / "latest" / "backtest_result.json"
)
RESULT_LATEST = PROJECT_ROOT / "reports" / "tuning" / "tuning_results.json"
RESULT_SNAPSHOTS = PROJECT_ROOT / "reports" / "tuning" / "snapshots"
TRIALS_TOP20_CSV = PROJECT_ROOT / "reports" / "tuning" / "trials_top20.csv"
BEST_TRIAL_SEGMENTS_CSV = (
    PROJECT_ROOT / "reports" / "tuning" / "best_trial_segments.csv"
)
TUNING_SUMMARY_MD = PROJECT_ROOT / "reports" / "tuning" / "tuning_summary.md"
PROMOTION_VERDICT_JSON = PROJECT_ROOT / "reports" / "tuning" / "promotion_verdict.json"
PROMOTION_VERDICT_MD = PROJECT_ROOT / "reports" / "tuning" / "promotion_verdict.md"

from app.utils.param_loader import load_params_strict
from app.tuning.results_io import atomic_write_result, atomic_write_text
from app.tuning.exports import (
    _to_float,
    _build_top_trial_rows,
    _rows_to_csv,
    _build_best_segment_rows,
    _build_validation_pack_metadata,
)
from app.tuning.summary_render import _build_validation_summary_md
from app.tuning.promotion_gate import (
    _load_json_or_none,
    refresh_promotion_verdict,
)

KST = timezone(timedelta(hours=9))


# ─── 1. Strategy Bundle ──────────────────────────────────────────────────
def load_strategy_bundle() -> Dict[str, Any]:
    if not BUNDLE_PATH.exists():
        raise FileNotFoundError(f"Strategy bundle not found: {BUNDLE_PATH}")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_tune_config(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """번들에서 튜닝에 필요한 설정 추출 (레거시 호환용, 직접 사용 금지)"""
    raise NotImplementedError(
        "extract_tune_config()은 폐기되었습니다. "
        "app.utils.param_loader.load_params_strict()를 사용하세요."
    )


# ─── 3. Main ─────────────────────────────────────────────────────────────
def run_cli_tune(
    mode: str = "full", n_trials: int = 50, seed: int = 42, timeout_sec: int = None
) -> bool:
    """Run Optuna tuning programmatically. Returns True if successful."""
    logger.info("=" * 60)
    logger.info("P167-R Optuna Tuning Engine — CLI")
    logger.info("=" * 60)

    # ── 0. Cleanup stale tmp files from previous runs ──
    tuning_dir = PROJECT_ROOT / "reports" / "tuning"
    tuning_dir.mkdir(parents=True, exist_ok=True)
    for tmp_file in tuning_dir.glob("*.tmp"):
        try:
            tmp_file.unlink()
            logger.info(f"[CLEANUP] Removed stale tmp: {tmp_file.name}")
        except Exception:
            pass

    # ── 1. Load config ──
    try:
        params, param_source = load_params_strict()
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

        price_data = prefetch_ohlcv(
            universe, start, end, data_source=params["data_source"]
        )
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
    from app.tuning.scoring import OBJECTIVE_VERSION, compute_score
    from app.tuning.telemetry import TuneLogger

    run_id = (
        f"tune_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    telemetry = TuneLogger(run_id)

    telemetry.emit_tune_start(
        {
            "run_id": run_id,
            "mode": mode,
            "n_trials": n_trials,
            "seed": seed,
            "universe": universe,
            "start_date": str(start),
            "end_date": str(end),
            "timeout_sec": timeout_sec,
        }
    )

    sampler = optuna.samplers.TPESampler(seed=seed)
    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    storage_path = PROJECT_ROOT / "reports" / "tuning" / "study.sqlite3"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    study_name = f"tune_{mode}_{universe[0] if universe else 'ALL'}_{OBJECTIVE_VERSION}"

    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        storage=f"sqlite:///{storage_path}",
        load_if_exists=True,
        study_name=study_name,
    )

    objective = TuneObjective(
        price_data=price_data,
        universe=universe,
        start=start,
        end=end,
        telemetry=telemetry,
    )

    def _checkpoint_callback(study_obj, trial_obj):
        base_dir = storage_path.parent
        now_str = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

        def _atomic_write_custom(filepath: Path, data: dict) -> None:
            import os, json

            tmp_path = filepath.parent / f"{filepath.name}.tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                os.replace(str(tmp_path), str(filepath))
            except Exception:
                if tmp_path.exists():
                    tmp_path.unlink()

        # 1. best_params / best_score
        try:
            best_t = study_obj.best_trial
            best_params_data = {
                "best_trial_number": best_t.number,
                "best_score": best_t.value,
                "params": best_t.params,
                "asof": now_str,
            }
            best_score_data = {
                "best_score": best_t.value,
                "best_trial_number": best_t.number,
                "asof": now_str,
            }
            _atomic_write_custom(base_dir / "best_params_latest.json", best_params_data)
            _atomic_write_custom(base_dir / "best_score_latest.json", best_score_data)
        except ValueError:
            pass  # No completed trials yet

        # 2. last_completed_trial
        status_str = (
            "COMPLETE"
            if trial_obj.state == optuna.trial.TrialState.COMPLETE
            else "FAIL"
        )
        reason = None
        if trial_obj.state == optuna.trial.TrialState.FAIL:
            reason = "EXCEPTION"
        elif trial_obj.state == optuna.trial.TrialState.PRUNED:
            status_str = "FAIL"
            reason = "NO_RESULT"
        elif (
            trial_obj.state == optuna.trial.TrialState.WAITING
            or trial_obj.state == optuna.trial.TrialState.RUNNING
        ):
            status_str = "FAIL"
            reason = "INTERRUPTED"

        last_comp_data = {
            "trial_number": trial_obj.number,
            "status": status_str,
            "reason": reason,
            "asof": now_str,
        }
        _atomic_write_custom(base_dir / "last_completed_trial.json", last_comp_data)

    t0 = time.time()
    started_at_str = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout_sec,
        callbacks=[_checkpoint_callback],
        catch=(Exception,),
    )
    runtime_sec = time.time() - t0

    # ── 5. Collect results ──
    completed_trials = [
        t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE
    ]

    if not completed_trials:
        logger.error("[TUNE] No completed trials! All pruned or failed.")
        telemetry.emit_tune_end({"status": "FAIL", "reason": "no_completed_trials"})
        return False

    completed_v2_trials = [
        t
        for t in completed_trials
        if t.user_attrs.get("objective_version") == OBJECTIVE_VERSION
    ]
    scored_trials = completed_v2_trials if completed_v2_trials else completed_trials

    best = max(scored_trials, key=lambda t: t.value)
    best_params = best.params
    best_score = best.value
    best_attrs = best.user_attrs

    # Top trials for export/UI
    sorted_trials = sorted(scored_trials, key=lambda t: t.value, reverse=True)
    trials_top20 = _build_top_trial_rows(sorted_trials, top_n=20)
    trials_top10 = []
    for t in sorted_trials[:10]:
        trials_top10.append(
            {
                "trial": t.number,
                "score": round(t.value, 4),
                "params": t.params,
                "sharpe": t.user_attrs.get("sharpe", 0),
                "mdd_pct": t.user_attrs.get("mdd_pct", 0),
                "cagr": t.user_attrs.get("cagr", 0),
                "total_trades": t.user_attrs.get("total_trades", 0),
            }
        )

    now_kst = datetime.now(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")

    try:
        from app.backtest.infra.data_loader import get_telemetry

        telemetry_data = get_telemetry()
    except ImportError:
        telemetry_data = {}

    # 5b. Segment evaluation (P204-STEP2)
    from app.tuning.segment_eval import compute_segment_metrics
    from app.tuning.runner import run_single_trial

    segment_data = {"segment_evaluation_enabled": False, "segment_status": "SKIPPED"}
    best_with_nav = {}
    try:
        logger.info("[SEGMENT] Re-running best params to extract nav_history...")
        best_with_nav = run_single_trial(
            params=best_params,
            price_data=price_data,
            universe=universe,
            start=start,
            end=end,
            include_nav_history=True,
        )
        raw_nav = best_with_nav.get("_nav_history", [])
        segment_data = compute_segment_metrics(raw_nav, n_segments=3)
        logger.info(
            f"[SEGMENT] {segment_data.get('segment_status', '?')} - "
            f"segments={segment_data.get('segment_count', 0)}, "
            f"ready={segment_data.get('segment_eval_ready', False)}"
        )
    except Exception as e:
        logger.warning(f"[SEGMENT] Segment evaluation failed: {e}")
        segment_data = {
            "segment_evaluation_enabled": True,
            "segment_scheme": "equal_3way",
            "segment_count": 3,
            "segment_eval_ready": False,
            "segment_status": f"ERROR: {e}",
            "full_period_metrics": {},
            "segment_metrics": {},
            "segment_lengths": [],
        }

    objective_payload = {
        "objective_version": best_attrs.get("objective_version", OBJECTIVE_VERSION),
        "objective_formula": best_attrs.get("objective_formula", ""),
        "objective_weights": best_attrs.get("objective_weights", {}),
        "objective_breakdown": best_attrs.get("objective_breakdown", {}),
        "cagr_agg": best_attrs.get("cagr_agg", 0.0),
        "mdd_agg": best_attrs.get("mdd_agg", 0.0),
        "sharpe_agg": best_attrs.get("sharpe_agg", 0.0),
        "overfit_penalty": best_attrs.get("overfit_penalty", 0.0),
        "hard_penalty_triggered": best_attrs.get("hard_penalty_triggered", False),
        "worst_segment": best_attrs.get("worst_segment", "N/A"),
        "metric_scale_normalized": best_attrs.get("metric_scale_normalized", "decimal"),
        "metric_scale_source": best_attrs.get(
            "metric_scale_source", "percent_to_decimal"
        ),
    }

    if not objective_payload.get("objective_breakdown") and best_with_nav:
        fallback_metrics = {
            key: value for key, value in best_with_nav.items() if key != "_nav_history"
        }
        objective_payload = compute_score(
            metrics=fallback_metrics, segment_data=segment_data
        )

    best_segment_rows = _build_best_segment_rows(segment_data)
    summary_markdown = _build_validation_summary_md(
        asof=now_kst,
        study_name=study_name,
        mode=mode,
        start_date=str(start),
        end_date=str(end),
        best_trial_number=best.number,
        best_params=best_params,
        full_metrics=segment_data.get("full_period_metrics", {}),
        worst_segment=objective_payload.get("worst_segment", "N/A"),
        overfit_penalty=_to_float(objective_payload.get("overfit_penalty")),
        top_rows=trials_top20,
    )

    validation_paths = {
        "trials_top20.csv": TRIALS_TOP20_CSV,
        "best_trial_segments.csv": BEST_TRIAL_SEGMENTS_CSV,
        "tuning_summary.md": TUNING_SUMMARY_MD,
    }
    atomic_write_text(
        TRIALS_TOP20_CSV,
        _rows_to_csv(
            [
                "rank",
                "trial",
                "score",
                "momentum_period",
                "volatility_period",
                "entry_threshold",
                "stop_loss",
                "max_positions",
                "cagr_full",
                "mdd_full",
                "sharpe_full",
                "cagr_agg",
                "mdd_agg",
                "sharpe_agg",
                "overfit_penalty",
                "worst_segment",
                "hard_penalty_triggered",
            ],
            trials_top20,
        ),
    )
    atomic_write_text(
        BEST_TRIAL_SEGMENTS_CSV,
        _rows_to_csv(
            ["segment", "cagr", "mdd", "sharpe", "days"],
            best_segment_rows,
        ),
    )
    atomic_write_text(TUNING_SUMMARY_MD, summary_markdown)
    validation_pack = {
        "generated_at": now_kst,
        "files": _build_validation_pack_metadata(
            {
                **validation_paths,
                "promotion_verdict.json": PROMOTION_VERDICT_JSON,
                "promotion_verdict.md": PROMOTION_VERDICT_MD,
            }
        ),
        "top5_comparison": trials_top20[:5],
    }

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
        "trials_top20": trials_top20,
        "validation_pack": validation_pack,
        "objective_version": objective_payload.get(
            "objective_version", OBJECTIVE_VERSION
        ),
        "objective_formula": objective_payload.get("objective_formula", ""),
        "objective_weights": objective_payload.get("objective_weights", {}),
        "objective_breakdown": objective_payload.get("objective_breakdown", {}),
        "cagr_agg": objective_payload.get("cagr_agg", 0.0),
        "mdd_agg": objective_payload.get("mdd_agg", 0.0),
        "sharpe_agg": objective_payload.get("sharpe_agg", 0.0),
        "overfit_penalty": objective_payload.get("overfit_penalty", 0.0),
        "hard_penalty_triggered": objective_payload.get(
            "hard_penalty_triggered", False
        ),
        "worst_segment": objective_payload.get("worst_segment", "N/A"),
        "metric_scale_normalized": objective_payload.get(
            "metric_scale_normalized", "decimal"
        ),
        "metric_scale_source": objective_payload.get(
            "metric_scale_source", "percent_to_decimal"
        ),
        **segment_data,
        "meta": {
            "asof": now_kst,
            "run_id": run_id,
            "study_name": study_name,
            "storage_path": str(storage_path),
            "resume_enabled": True,
            "n_trials_total": len(study.trials),
            "n_trials_complete": len(completed_trials),
            "n_trials_complete_v2": len(completed_v2_trials),
            "n_trials_failed": len(
                [t for t in study.trials if t.state == optuna.trial.TrialState.FAIL]
            ),
            "best_trial_number": best.number,
            "best_score": round(best_score, 4),
            "checkpoint_files": [
                "best_params_latest.json",
                "best_score_latest.json",
                "last_completed_trial.json",
            ],
            "started_at": started_at_str,
            "finished_at": now_kst,
            "mode": mode,
            "start_date": str(start),
            "end_date": str(end),
            "universe": universe,
            "n_trials_session": n_trials,
            "completed_trials_session": len(completed_trials),
            "pruned_trials_session": len(study.trials) - len(completed_trials),
            "seed": seed,
            "runtime_sec": round(runtime_sec, 1),
            "param_source": param_source,
            "data_source_used": params["data_source"],
            "download_count": telemetry_data.get("download_count", 0),
            "cache_hit_count": telemetry_data.get("cache_hit_count", 0),
            "fallback_count": telemetry_data.get("fallback_count", 0),
            "objective_version": objective_payload.get(
                "objective_version", OBJECTIVE_VERSION
            ),
            "metric_scale_normalized": objective_payload.get(
                "metric_scale_normalized", "decimal"
            ),
            "metric_scale_source": objective_payload.get(
                "metric_scale_source", "percent_to_decimal"
            ),
        },
    }
    promotion_verdict = refresh_promotion_verdict(
        tune_data_override=tune_result,
        backtest_data_override=_load_json_or_none(BACKTEST_RESULT_LATEST),
        params_data_override=_load_json_or_none(PARAMS_SSOT_PATH),
    )
    tune_result["validation_pack"]["files"] = _build_validation_pack_metadata(
        {
            **validation_paths,
            "promotion_verdict.json": PROMOTION_VERDICT_JSON,
            "promotion_verdict.md": PROMOTION_VERDICT_MD,
        }
    )
    tune_result["promotion_verdict"] = promotion_verdict
    try:
        atomic_write_result(tune_result)
    except Exception as e:
        logger.error(f"Result write failed: {e}")
        return False

    telemetry.emit_tune_end(
        {
            "status": "OK",
            "best_score": round(best_score, 4),
            "best_params": best_params,
            "completed_trials": len(completed_trials),
            "runtime_sec": round(runtime_sec, 1),
        }
    )

    # ── 7. Summary ──
    logger.info("=" * 60)
    logger.info(f"[RESULT: OK] best_score={best_score:.4f}")
    logger.info(f"  best_params: {best_params}")
    logger.info(
        f"  sharpe={best_attrs.get('sharpe', 0):.4f}  "
        f"mdd={best_attrs.get('mdd_pct', 0):.2f}%  "
        f"cagr={best_attrs.get('cagr', 0):.4f}"
    )
    logger.info(
        f"  completed={len(completed_trials)}/{len(study.trials)}  "
        f"runtime={runtime_sec:.1f}s"
    )
    logger.info(f"  telemetry: {telemetry.filepath}")
    logger.info("=" * 60)
    print(f"[RESULT: OK] tuning completed → {RESULT_LATEST}")
    return True


def main():
    parser = argparse.ArgumentParser(description="P167-R Optuna Tuning CLI")
    parser.add_argument(
        "--mode", choices=["quick", "full"], default="full", help="quick: 6M, full: 3Y"
    )
    parser.add_argument("--n-trials", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--timeout-sec", type=int, default=None, help="Optuna timeout (seconds)"
    )
    args = parser.parse_args()

    success = run_cli_tune(
        mode=args.mode,
        n_trials=args.n_trials,
        seed=args.seed,
        timeout_sec=args.timeout_sec,
    )
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
