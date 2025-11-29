#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extensions/automation/config_loader.py
설정 파일 로더 (YAML)
"""
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """설정 파일 로더"""
    
    def __init__(self, config_name: str = "config.nas.yaml"):
        """
        Args:
            config_name: 설정 파일 이름 (기본: config.nas.yaml)
        """
        self.config_name = config_name
        self.config_path = self._find_config_path()
        self._config_cache: Optional[Dict[str, Any]] = None
    
    def _find_config_path(self) -> Path:
        """설정 파일 경로 찾기"""
        # 현재 파일 기준 프로젝트 루트 찾기
        current = Path(__file__).resolve()
        
        # extensions/automation/config_loader.py -> 프로젝트 루트
        project_root = current.parent.parent.parent
        
        config_path = project_root / "config" / self.config_name
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"설정 파일을 찾을 수 없습니다: {config_path}\n"
                f"프로젝트 루트: {project_root}"
            )
        
        return config_path
    
    def load(self) -> Dict[str, Any]:
        """설정 파일 로드 (캐싱)"""
        if self._config_cache is not None:
            return self._config_cache
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            self._config_cache = config
            logger.info(f"설정 파일 로드 성공: {self.config_path}")
            
            return config
        
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            raise
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        중첩된 키로 설정 값 가져오기
        
        Args:
            key_path: 점(.)으로 구분된 키 경로 (예: "intraday_alert.thresholds.leverage")
            default: 기본값
        
        Returns:
            설정 값 또는 기본값
        
        Examples:
            >>> loader = ConfigLoader()
            >>> loader.get("intraday_alert.thresholds.leverage")
            3.0
            >>> loader.get("intraday_alert.min_trade_value")
            5000000000
        """
        config = self.load()
        
        keys = key_path.split('.')
        value = config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        설정 섹션 전체 가져오기
        
        Args:
            section: 섹션 이름 (예: "intraday_alert")
        
        Returns:
            섹션 딕셔너리
        """
        config = self.load()
        return config.get(section, {})


# 싱글톤 인스턴스 (NAS 전용)
_config_loader = None


def get_config_loader(config_name: str = "config.nas.yaml") -> ConfigLoader:
    """
    설정 로더 싱글톤 인스턴스 가져오기
    
    Args:
        config_name: 설정 파일 이름
    
    Returns:
        ConfigLoader 인스턴스
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader(config_name)
    
    return _config_loader
