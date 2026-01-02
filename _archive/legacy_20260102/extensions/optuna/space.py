# -*- coding: utf-8 -*-
"""
extensions/optuna/space.py
하이퍼파라미터 검색 공간 정의
"""
import optuna
from typing import Dict, Any


def suggest_strategy_params(trial: optuna.Trial) -> Dict[str, Any]:
    """
    MAPS 전략 파라미터 검색 공간
    
    Args:
        trial: Optuna trial 객체
        
    Returns:
        파라미터 딕셔너리
    """
    params = {
        # MAPS 전략 핵심 파라미터
        'ma_period': trial.suggest_int('ma_period', 20, 120, step=10),  # 이동평균 기간
        'rsi_period': trial.suggest_int('rsi_period', 7, 21, step=2),   # RSI 기간
        'rsi_overbought': trial.suggest_int('rsi_overbought', 65, 80, step=5),  # RSI 과매수 임계값
        
        # 신호 임계값
        'maps_buy_threshold': trial.suggest_float('maps_buy_threshold', -2.0, 5.0, step=1.0),  # MAPS 매수 임계값
        'maps_sell_threshold': trial.suggest_float('maps_sell_threshold', -10.0, -2.0, step=1.0),  # MAPS 매도 임계값
        
        # 리밸런싱
        'rebalance_frequency': trial.suggest_categorical(
            'rebalance_frequency', 
            ['weekly', 'biweekly', 'monthly']
        ),
        
        # 포지션 관리
        'max_positions': trial.suggest_int('max_positions', 5, 20, step=5),
        'min_confidence': trial.suggest_float('min_confidence', 0.0, 0.3, step=0.05),  # 최소 신뢰도
    }
    
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
