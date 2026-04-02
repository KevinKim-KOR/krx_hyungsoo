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


SEARCH_SPACE_VERSIONS = {
    "5axis_v1": "fixed/expanded 기본 탐색공간",
    "5axis_dynamic_risk_v1": "dynamic_etf_market 리스크 보정 전용",
}


def suggest_params(trial: optuna.Trial) -> Dict[str, Any]:
    """Optuna trial에서 하이퍼파라미터 제안 (fixed/expanded)"""
    return {
        "momentum_period": trial.suggest_int("momentum_period", 45, 65, step=1),
        "volatility_period": trial.suggest_int("volatility_period", 12, 24, step=1),
        "entry_threshold": trial.suggest_float(
            "entry_threshold", 0.01, 0.05, step=0.01
        ),
        "stop_loss": trial.suggest_float("stop_loss", -0.10, -0.03, step=0.01),
        "max_positions": trial.suggest_int("max_positions", 2, 5, step=1),
    }


def suggest_params_dynamic_risk(trial: optuna.Trial) -> Dict[str, Any]:
    """dynamic_etf_market 리스크 보정 전용 탐색공간

    - stop_loss: 타이트한 구간 (-0.07 ~ -0.03)
    - entry_threshold: 보수적 진입 (0.03 ~ 0.07)
    - max_positions: 분산 유지 (2 ~ 4)
    - momentum/volatility: 중간 범위
    """
    return {
        "momentum_period": trial.suggest_int("momentum_period", 40, 60, step=2),
        "volatility_period": trial.suggest_int("volatility_period", 14, 28, step=1),
        "entry_threshold": trial.suggest_float(
            "entry_threshold", 0.03, 0.07, step=0.01
        ),
        "stop_loss": trial.suggest_float("stop_loss", -0.07, -0.03, step=0.01),
        "max_positions": trial.suggest_int("max_positions", 2, 4, step=1),
    }
