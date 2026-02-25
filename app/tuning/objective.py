# -*- coding: utf-8 -*-
"""
app/tuning/objective.py — P167-R Optuna 목적함수

trial마다:
  1. search_space에서 파라미터 제안
  2. runner.run_single_trial()로 직접 백테스트 실행
  3. 하드 제약 → prune
  4. compute_score → maximize

레거시 참조: _archive/legacy_20260102/extensions/tuning/objective.py
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set

import pandas as pd

try:
    import optuna
except ImportError:
    raise ImportError("optuna 패키지 미설치. pip install optuna 필요.")

from app.tuning.search_space import suggest_params
from app.tuning.scoring import compute_score, should_prune
from app.tuning.runner import run_single_trial
from app.tuning.cache_key import compute_params_hash
from app.tuning.telemetry import TuneLogger

logger = logging.getLogger(__name__)


class TuneObjective:
    """Optuna 목적함수 (maximize)"""

    def __init__(
        self,
        price_data: pd.DataFrame,
        universe: List[str],
        start: date,
        end: date,
        telemetry: Optional[TuneLogger] = None,
    ):
        self.price_data = price_data
        self.universe = universe
        self.start = start
        self.end = end
        self.telemetry = telemetry
        self._seen_hashes: Set[str] = set()

    def __call__(self, trial: optuna.Trial) -> float:
        # 1. Suggest params
        params = suggest_params(trial)

        # 2. Duplicate check
        p_hash = compute_params_hash(params)
        if p_hash in self._seen_hashes:
            logger.info(f"[TUNE] Trial {trial.number}: duplicate params → prune")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number, params, -999.0,
                    pruned=True, prune_reason="duplicate_params",
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
            )
        except Exception as e:
            logger.warning(f"[TUNE] Trial {trial.number}: backtest failed: {e}")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number, params, -999.0,
                    pruned=True, prune_reason=f"error: {e}",
                )
            raise optuna.TrialPruned(f"error: {e}")

        # 4. Hard constraint check
        prune_reason = should_prune(metrics["mdd_pct"], metrics["total_trades"])
        if prune_reason:
            logger.info(f"[TUNE] Trial {trial.number}: pruned — {prune_reason}")
            if self.telemetry:
                self.telemetry.emit_trial_end(
                    trial.number, params, -999.0,
                    pruned=True, prune_reason=prune_reason,
                    metrics=metrics,
                )
            raise optuna.TrialPruned(prune_reason)

        # 5. Compute score
        score = compute_score(
            metrics["sharpe"], metrics["mdd_pct"], metrics["total_trades"]
        )

        # 6. Log trial attrs for Optuna dashboard
        trial.set_user_attr("sharpe", metrics["sharpe"])
        trial.set_user_attr("mdd_pct", metrics["mdd_pct"])
        trial.set_user_attr("cagr", metrics["cagr"])
        trial.set_user_attr("total_return", metrics["total_return"])
        trial.set_user_attr("total_trades", metrics["total_trades"])
        trial.set_user_attr("params_hash", p_hash)

        logger.info(
            f"[TUNE] Trial {trial.number}: "
            f"score={score:.4f}  sharpe={metrics['sharpe']:.4f}  "
            f"mdd={metrics['mdd_pct']:.2f}%  trades={metrics['total_trades']}"
        )

        # 7. Telemetry
        if self.telemetry:
            self.telemetry.emit_trial_end(
                trial.number, params, score,
                metrics=metrics,
            )

        return score
