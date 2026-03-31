# -*- coding: utf-8 -*-
"""
app/tuning/objective.py - Optuna objective for tuning
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set

import pandas as pd

try:
    import optuna
except ImportError:
    raise ImportError("optuna package missing. Please install optuna.")

from app.tuning.search_space import suggest_params
from app.tuning.scoring import compute_score, should_prune
from app.tuning.runner import run_single_trial
from app.tuning.segment_eval import compute_segment_metrics
from app.tuning.cache_key import compute_params_hash
from app.tuning.telemetry import TuneLogger

logger = logging.getLogger(__name__)


class TuneObjective:
    """Optuna objective function (maximize)."""

    def __init__(
        self,
        price_data: pd.DataFrame,
        universe: List[str],
        start: date,
        end: date,
        telemetry: Optional[TuneLogger] = None,
        universe_resolver=None,
    ):
        self.price_data = price_data
        self.universe = universe
        self.start = start
        self.end = end
        self.telemetry = telemetry
        self.universe_resolver = universe_resolver
        self._seen_hashes: Set[str] = set()

    def __call__(self, trial: optuna.Trial) -> float:
        # 1. Suggest params
        params = suggest_params(trial)

        # 2. Duplicate check
        p_hash = compute_params_hash(params)
        if p_hash in self._seen_hashes:
            logger.info(f"[TUNE] Trial {trial.number}: duplicate params -> prune")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number,
                    params,
                    -10.0,
                    pruned=True,
                    prune_reason="duplicate_params",
                )
            raise optuna.TrialPruned("duplicate_params")
        self._seen_hashes.add(p_hash)

        # 3. Run backtest (direct call, no subprocess)
        try:
            metrics = run_single_trial(
                params=params,
                price_data=self.price_data,
                universe=self.universe,
                start=self.start,
                end=self.end,
                universe_resolver=self.universe_resolver,
                include_nav_history=True,
            )
        except Exception as error:
            logger.warning(f"[TUNE] Trial {trial.number}: backtest failed: {error}")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number,
                    params,
                    -10.0,
                    pruned=True,
                    prune_reason=f"error: {error}",
                )
            raise optuna.TrialPruned(f"error: {error}")

        metrics_core = {
            key: value for key, value in metrics.items() if key != "_nav_history"
        }

        # 4. Hard constraint check
        prune_reason = should_prune(
            metrics_core["mdd_pct"], metrics_core["total_trades"]
        )
        if prune_reason:
            logger.info(f"[TUNE] Trial {trial.number}: pruned - {prune_reason}")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number,
                    params,
                    -10.0,
                    pruned=True,
                    prune_reason=prune_reason,
                    metrics=metrics_core,
                )
            raise optuna.TrialPruned(prune_reason)

        # 5. Segment metrics + Step3 objective score
        segment_data = compute_segment_metrics(
            metrics.get("_nav_history", []), n_segments=3
        )
        score_payload = compute_score(metrics=metrics_core, segment_data=segment_data)
        score = float(score_payload["score"])

        # 6. Log trial attrs for downstream summary and UI
        trial.set_user_attr("sharpe", metrics_core["sharpe"])
        trial.set_user_attr("mdd_pct", metrics_core["mdd_pct"])
        trial.set_user_attr("cagr", metrics_core["cagr"])
        trial.set_user_attr("total_return", metrics_core["total_return"])
        trial.set_user_attr("total_trades", metrics_core["total_trades"])
        trial.set_user_attr("params_hash", p_hash)

        trial.set_user_attr("objective_version", score_payload["objective_version"])
        trial.set_user_attr("objective_formula", score_payload["objective_formula"])
        trial.set_user_attr("objective_weights", score_payload["objective_weights"])
        trial.set_user_attr("objective_breakdown", score_payload["objective_breakdown"])
        trial.set_user_attr("cagr_agg", score_payload["cagr_agg"])
        trial.set_user_attr("mdd_agg", score_payload["mdd_agg"])
        trial.set_user_attr("sharpe_agg", score_payload["sharpe_agg"])
        trial.set_user_attr("overfit_penalty", score_payload["overfit_penalty"])
        trial.set_user_attr(
            "hard_penalty_triggered", score_payload["hard_penalty_triggered"]
        )
        trial.set_user_attr("worst_segment", score_payload["worst_segment"])
        trial.set_user_attr(
            "metric_scale_normalized", score_payload["metric_scale_normalized"]
        )
        trial.set_user_attr("metric_scale_source", score_payload["metric_scale_source"])

        reason_code = score_payload.get("score_reason_code", "")
        if reason_code:
            trial.set_user_attr("score_reason_code", reason_code)

        logger.info(
            f"[TUNE] Trial {trial.number}: score={score:.4f} "
            f"cagr_agg={score_payload['cagr_agg']:.4f} "
            f"mdd_agg={score_payload['mdd_agg']:.4f} "
            f"sharpe_agg={score_payload['sharpe_agg']:.4f} "
            f"penalty={score_payload['overfit_penalty']:.4f}"
        )

        # 7. Telemetry
        if self.telemetry:
            telemetry_metrics: Dict[str, Any] = {
                **metrics_core,
                "objective_breakdown": score_payload.get("objective_breakdown", {}),
                "cagr_agg": score_payload.get("cagr_agg"),
                "mdd_agg": score_payload.get("mdd_agg"),
                "sharpe_agg": score_payload.get("sharpe_agg"),
                "overfit_penalty": score_payload.get("overfit_penalty"),
                "worst_segment": score_payload.get("worst_segment"),
                "metric_scale_normalized": score_payload.get("metric_scale_normalized"),
                "metric_scale_source": score_payload.get("metric_scale_source"),
            }
            self.telemetry.emit_trial_end(
                trial.number, params, score, metrics=telemetry_metrics
            )

        return score
