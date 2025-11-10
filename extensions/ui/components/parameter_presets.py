#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파라미터 프리셋 - 미리 정의된 전략 설정
"""

def get_presets():
    """미리 정의된 파라미터 프리셋"""
    return {
        "균형 (기본)": {
            "name": "균형 (기본)",
            "description": "안정적이고 균형잡힌 전략 - 권장 설정",
            "params": {
                'maps_threshold': 5.0,
                'regime_ma_short': 50,
                'regime_ma_long': 200,
                'regime_threshold': 2.0,
                'position_bull': 120,
                'position_sideways': 80,
                'position_bear': 50,
                'defense_confidence': 85,
                'max_position_size': 20,
                'stop_loss': -5.0
            },
            "expected": {
                "cagr": "25~30%",
                "sharpe": "1.4~1.6",
                "mdd": "-15~-20%"
            }
        },
        "공격적": {
            "name": "공격적",
            "description": "높은 수익률 추구 - 변동성 큼",
            "params": {
                'maps_threshold': 3.0,
                'regime_ma_short': 20,
                'regime_ma_long': 100,
                'regime_threshold': 1.5,
                'position_bull': 150,
                'position_sideways': 100,
                'position_bear': 60,
                'defense_confidence': 90,
                'max_position_size': 30,
                'stop_loss': -7.0
            },
            "expected": {
                "cagr": "35~45%",
                "sharpe": "1.2~1.4",
                "mdd": "-25~-35%"
            }
        },
        "보수적": {
            "name": "보수적",
            "description": "안정성 우선 - 낮은 변동성",
            "params": {
                'maps_threshold': 7.0,
                'regime_ma_short': 100,
                'regime_ma_long': 300,
                'regime_threshold': 2.5,
                'position_bull': 100,
                'position_sideways': 60,
                'position_bear': 30,
                'defense_confidence': 80,
                'max_position_size': 15,
                'stop_loss': -3.0
            },
            "expected": {
                "cagr": "15~20%",
                "sharpe": "1.6~1.8",
                "mdd": "-8~-12%"
            }
        },
        "Week 3 최적": {
            "name": "Week 3 최적",
            "description": "Week 3에서 검증된 최적 파라미터",
            "params": {
                'maps_threshold': 5.0,
                'regime_ma_short': 50,
                'regime_ma_long': 200,
                'regime_threshold': 2.0,
                'position_bull': 120,
                'position_sideways': 80,
                'position_bear': 50,
                'defense_confidence': 85,
                'max_position_size': 20,
                'stop_loss': -5.0
            },
            "expected": {
                "cagr": "27.05%",
                "sharpe": "1.51",
                "mdd": "-19.92%"
            }
        }
    }
