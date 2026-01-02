# -*- coding: utf-8 -*-
"""
core/engine/config_loader.py
Phase 4: Config 연결

백테스트 설정을 YAML에서 로드하여 엔진을 생성하는 팩토리 함수

사용법:
    from core.engine.config_loader import (
        load_backtest_config,
        create_backtest_engine_from_config,
        create_maps_adapter_from_config
    )
    
    # Config 로드
    config = load_backtest_config()
    
    # 엔진 생성 (기존 방식과 호환)
    engine = create_backtest_engine_from_config()
    adapter = create_maps_adapter_from_config()
"""
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import logging

logger = logging.getLogger(__name__)

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_backtest_config(
    config_path: Optional[Path] = None,
    country: str = 'korea'
) -> Dict[str, Any]:
    """
    백테스트 설정 로드
    
    Args:
        config_path: 설정 파일 경로 (기본: config/backtest.yaml)
        country: 국가 코드 (korea, us)
        
    Returns:
        설정 딕셔너리
    """
    if config_path is None:
        config_path = PROJECT_ROOT / 'config' / 'backtest.yaml'
    
    if not config_path.exists():
        logger.warning(f"설정 파일 없음: {config_path}, 기본값 사용")
        return _get_default_config(country)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    backtest_config = raw_config.get('backtest', {})
    
    # 국가별 비용 설정 적용
    costs = backtest_config.get('costs', {}).get(country, {})
    
    config = {
        # 기본 설정
        'initial_capital': backtest_config.get('initial_capital', 10_000_000),
        'max_positions': backtest_config.get('max_positions', 10),
        
        # 거래비용
        'commission_rate': costs.get('commission_rate', 0.00015),
        'slippage_rate': costs.get('slippage_rate', 0.001),
        'tax_rates': costs.get('tax_rates', {'default': 0.0}),
        
        # 레짐 스케일링
        'regime_scaling': backtest_config.get('regime_scaling', {
            'enabled': True,
            'position_ratios': {'bull': 1.0, 'neutral': 0.8, 'bear': 0.5},
            'reduce_existing_positions': True,
            'exposure_buffer': 0.05
        }),
        
        # 방어 시스템
        'defense': backtest_config.get('defense', {
            'enabled': True,
            'portfolio_stop_loss': -0.15,
            'individual_stop_loss': -0.10,
            'cooldown_days': 5
        }),
        
        # 분할 설정
        'split': backtest_config.get('split', {
            'train_ratio': 0.70,
            'val_ratio': 0.15,
            'test_ratio': 0.15
        }),
        
        # 기간
        'default_start_date': backtest_config.get('default_start_date', '2022-01-01'),
        'default_end_date': backtest_config.get('default_end_date', '2025-11-30'),
        
        # 국가
        'country': country
    }
    
    logger.info(f"백테스트 설정 로드 완료: {config_path}")
    logger.debug(f"  초기 자본: {config['initial_capital']:,}원")
    logger.debug(f"  수수료율: {config['commission_rate']*100:.3f}%")
    logger.debug(f"  슬리피지: {config['slippage_rate']*100:.2f}%")
    
    return config


def _get_default_config(country: str = 'korea') -> Dict[str, Any]:
    """기본 설정 반환"""
    if country == 'korea':
        return {
            'initial_capital': 10_000_000,
            'max_positions': 10,
            'commission_rate': 0.00015,
            'slippage_rate': 0.001,
            'tax_rates': {
                'stock': 0.0023,
                'etf': 0.0,
                'leveraged_etf': 0.0,
                'reit': 0.0023,
                'default': 0.0
            },
            'regime_scaling': {
                'enabled': True,
                'position_ratios': {'bull': 1.0, 'neutral': 0.8, 'bear': 0.5},
                'reduce_existing_positions': True,
                'exposure_buffer': 0.05
            },
            'defense': {
                'enabled': True,
                'portfolio_stop_loss': -0.15,
                'individual_stop_loss': -0.10,
                'cooldown_days': 5
            },
            'split': {
                'train_ratio': 0.70,
                'val_ratio': 0.15,
                'test_ratio': 0.15
            },
            'country': 'korea'
        }
    else:
        return {
            'initial_capital': 10_000,  # USD
            'max_positions': 10,
            'commission_rate': 0.0,
            'slippage_rate': 0.001,
            'tax_rates': {'default': 0.0},
            'regime_scaling': {'enabled': False},
            'defense': {'enabled': False},
            'split': {'train_ratio': 0.70, 'val_ratio': 0.15, 'test_ratio': 0.15},
            'country': 'us'
        }


def create_backtest_engine_from_config(
    config_path: Optional[Path] = None,
    country: str = 'korea',
    instrument_type: str = 'etf',
    **overrides
) -> 'BacktestEngine':
    """
    Config에서 BacktestEngine 생성
    
    Args:
        config_path: 설정 파일 경로
        country: 국가 코드
        instrument_type: 상품 유형 (etf, stock, etc.)
        **overrides: 설정 오버라이드
        
    Returns:
        BacktestEngine 인스턴스
    """
    from core.engine.backtest import BacktestEngine
    
    config = load_backtest_config(config_path, country)
    
    # 세율 결정
    tax_rates = config.get('tax_rates', {})
    tax_rate = tax_rates.get(instrument_type, tax_rates.get('default', 0.0))
    
    # 오버라이드 적용
    engine_params = {
        'initial_capital': config['initial_capital'],
        'commission_rate': config['commission_rate'],
        'slippage_rate': config['slippage_rate'],
        'tax_rate': tax_rate,
        **overrides
    }
    
    logger.info(f"BacktestEngine 생성: {instrument_type}, 세율 {tax_rate*100:.2f}%")
    
    return BacktestEngine(**engine_params)


def create_maps_adapter_from_config(
    config_path: Optional[Path] = None,
    country: str = 'korea',
    instrument_type: str = 'etf',
    **overrides
) -> 'KRXMAPSAdapter':
    """
    Config에서 KRXMAPSAdapter 생성
    
    Args:
        config_path: 설정 파일 경로
        country: 국가 코드
        instrument_type: 상품 유형
        **overrides: 설정 오버라이드
        
    Returns:
        KRXMAPSAdapter 인스턴스
    """
    from core.engine.krx_maps_adapter import KRXMAPSAdapter
    
    config = load_backtest_config(config_path, country)
    
    # 방어 시스템 활성화 여부
    defense_config = config.get('defense', {})
    enable_defense = defense_config.get('enabled', True)
    
    # 어댑터 파라미터
    adapter_params = {
        'initial_capital': config['initial_capital'],
        'max_positions': config['max_positions'],
        'commission_rate': config['commission_rate'],
        'slippage_rate': config['slippage_rate'],
        'instrument_type': instrument_type,
        'country_code': 'kor' if country == 'korea' else 'us',
        'enable_defense': enable_defense,
        **overrides
    }
    
    logger.info(f"KRXMAPSAdapter 생성: {instrument_type}, 방어={enable_defense}")
    
    return KRXMAPSAdapter(**adapter_params)


def get_split_config(config_path: Optional[Path] = None) -> Dict[str, float]:
    """
    Train/Val/Test 분할 설정 반환
    
    Returns:
        {'train_ratio': 0.70, 'val_ratio': 0.15, 'test_ratio': 0.15}
    """
    config = load_backtest_config(config_path)
    return config.get('split', {
        'train_ratio': 0.70,
        'val_ratio': 0.15,
        'test_ratio': 0.15
    })


def get_regime_scaling_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    레짐 스케일링 설정 반환
    """
    config = load_backtest_config(config_path)
    return config.get('regime_scaling', {
        'enabled': True,
        'position_ratios': {'bull': 1.0, 'neutral': 0.8, 'bear': 0.5}
    })


# 편의 함수
def quick_backtest_config(
    capital: int = 10_000_000,
    instrument: str = 'etf',
    defense: bool = True
) -> Dict[str, Any]:
    """
    빠른 백테스트 설정 생성
    
    Args:
        capital: 초기 자본금
        instrument: 상품 유형
        defense: 방어 시스템 활성화
        
    Returns:
        백테스트 설정 딕셔너리
    """
    config = load_backtest_config()
    
    return {
        'initial_capital': capital,
        'max_positions': config['max_positions'],
        'commission_rate': config['commission_rate'],
        'slippage_rate': config['slippage_rate'],
        'instrument_type': instrument,
        'country_code': 'kor',
        'enable_defense': defense
    }
