# -*- coding: utf-8 -*-
"""
extensions/optuna/space.py
하이퍼파라미터 검색 공간 정의
"""
import optuna
from typing import Dict, Any


def suggest_strategy_params(trial: optuna.Trial) -> Dict[str, Any]:
    """
    전략 파라미터 검색 공간
    
    Args:
        trial: Optuna trial 객체
        
    Returns:
        파라미터 딕셔너리
    """
    params = {
        # 기술적 지표
        'ma_period': trial.suggest_int('ma_period', 10, 120),
        'rsi_period': trial.suggest_int('rsi_period', 7, 30),
        'adx_threshold': trial.suggest_float('adx_threshold', 10.0, 40.0),
        'bb_period': trial.suggest_int('bb_period', 10, 40),
        'bb_std': trial.suggest_float('bb_std', 1.5, 3.0),
        
        # 신호 생성
        'momentum_weight': trial.suggest_float('momentum_weight', 0.0, 1.0),
        'trend_weight': trial.suggest_float('trend_weight', 0.0, 1.0),
        'mean_reversion_weight': trial.suggest_float('mean_reversion_weight', 0.0, 1.0),
        
        # 리밸런싱
        'rebalance_frequency': trial.suggest_categorical(
            'rebalance_frequency', 
            ['daily', 'weekly', 'monthly']
        ),
        
        # 포지션 관리
        'max_positions': trial.suggest_int('max_positions', 5, 15),
        'position_cap': trial.suggest_float('position_cap', 0.15, 0.35),
    }
    
    # 가중치 정규화
    total_weight = (
        params['momentum_weight'] + 
        params['trend_weight'] + 
        params['mean_reversion_weight']
    )
    
    if total_weight > 0:
        params['momentum_weight'] /= total_weight
        params['trend_weight'] /= total_weight
        params['mean_reversion_weight'] /= total_weight
    
    return params


def suggest_risk_params(trial: optuna.Trial) -> Dict[str, Any]:
    """
    리스크 관리 파라미터 검색 공간
    
    Args:
        trial: Optuna trial 객체
        
    Returns:
        파라미터 딕셔너리
    """
    params = {
        'portfolio_vol_target': trial.suggest_float('portfolio_vol_target', 0.08, 0.20),
        'max_drawdown_threshold': trial.suggest_float('max_drawdown_threshold', -0.25, -0.10),
        'cooldown_days': trial.suggest_int('cooldown_days', 3, 10),
        'max_correlation': trial.suggest_float('max_correlation', 0.5, 0.85),
    }
    
    return params


def suggest_all_params(trial: optuna.Trial) -> Dict[str, Any]:
    """
    전체 파라미터 검색 공간
    
    Args:
        trial: Optuna trial 객체
        
    Returns:
        전체 파라미터 딕셔너리
    """
    params = {}
    params.update(suggest_strategy_params(trial))
    params.update(suggest_risk_params(trial))
    
    return params
