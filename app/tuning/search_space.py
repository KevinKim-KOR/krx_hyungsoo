# -*- coding: utf-8 -*-
"""
app/tuning/search_space.py — P167-R 하이퍼파라미터 검색 공간

레거시 참조: _archive/legacy_20260102/extensions/optuna/space.py
"""
from __future__ import annotations
from typing import Any, Dict

try:
    import optuna
except ImportError:
    raise ImportError("optuna 패키지 미설치. pip install optuna 필요.")


def suggest_params(trial: optuna.Trial) -> Dict[str, Any]:
    """Optuna trial에서 하이퍼파라미터 제안"""
    return {
        "momentum_period": trial.suggest_int("momentum_period", 8, 60),
        "stop_loss": trial.suggest_float("stop_loss", -0.10, -0.01, step=0.01),
        "max_positions": trial.suggest_int("max_positions", 2, 6),
    }
