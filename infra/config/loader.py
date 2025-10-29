# -*- coding: utf-8 -*-
"""
infra/config/loader.py
설정 파일 로더
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import os


class Config:
    """설정 관리자"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 설정 파일 경로 (기본: config/config.yaml)
        """
        if config_path is None:
            config_path = Path('config/config.yaml')
        
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """설정 파일 로드"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # 환경 변수로 덮어쓰기
        self._override_from_env()
    
    def _override_from_env(self):
        """환경 변수로 설정 덮어쓰기"""
        # 예: KRX_DATA_CACHE_DIR -> data.cache_dir
        env_mappings = {
            'KRX_DATA_CACHE_DIR': ('data', 'cache_dir'),
            'KRX_DB_PATH': ('data', 'db_path'),
            'KRX_INITIAL_CAPITAL': ('backtest', 'initial_capital'),
            'KRX_LOG_LEVEL': ('logging', 'level'),
            'KRX_TELEGRAM_TOKEN': ('notification', 'telegram', 'bot_token'),
            'KRX_TELEGRAM_CHAT_ID': ('notification', 'telegram', 'chat_id'),
        }
        
        for env_key, config_keys in env_mappings.items():
            value = os.getenv(env_key)
            if value is not None:
                self._set_nested(config_keys, value)
    
    def _set_nested(self, keys: tuple, value: Any):
        """중첩된 딕셔너리에 값 설정"""
        d = self._config
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        
        # 타입 변환
        last_key = keys[-1]
        if isinstance(d.get(last_key), int):
            value = int(value)
        elif isinstance(d.get(last_key), float):
            value = float(value)
        elif isinstance(d.get(last_key), bool):
            value = value.lower() in ('true', '1', 'yes')
        
        d[last_key] = value
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """설정 값 가져오기"""
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def get_data_config(self) -> Dict[str, Any]:
        """데이터 설정"""
        return self.get('data', default={})
    
    def get_filtering_config(self) -> Dict[str, Any]:
        """필터링 설정"""
        return self.get('filtering', default={})
    
    def get_backtest_config(self) -> Dict[str, Any]:
        """백테스트 설정"""
        return self.get('backtest', default={})
    
    def get_strategy_config(self) -> Dict[str, Any]:
        """전략 설정"""
        return self.get('strategy', default={})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """리스크 설정"""
        return self.get('strategy', 'risk', default={})
    
    def get_scan_config(self) -> Dict[str, Any]:
        """스캔 설정"""
        return self.get('scan', default={})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """로깅 설정"""
        return self.get('logging', default={})
    
    def get_notification_config(self) -> Dict[str, Any]:
        """알림 설정"""
        return self.get('notification', default={})


# 전역 설정 인스턴스
_config: Optional[Config] = None


def get_config() -> Config:
    """전역 설정 인스턴스 가져오기"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config():
    """설정 다시 로드"""
    global _config
    _config = None
    return get_config()
