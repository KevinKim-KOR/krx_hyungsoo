# -*- coding: utf-8 -*-
"""
extensions/tuning/cache.py
튜닝/검증 체계 v2.1 - 캐시 시스템

문서 참조: docs/tuning/01_metrics_guardrails.md 5.5절
"""
import hashlib
import json
import logging
from collections import OrderedDict
from datetime import date
from typing import Any, Dict, Optional

from extensions.tuning.types import (
    BacktestRunResult,
    Period,
    CostConfig,
    DataConfig,
)

logger = logging.getLogger(__name__)


def make_cache_key(
    params: Dict[str, Any],
    lookback_months: int,
    period: Period,
    costs: CostConfig,
    data_config: DataConfig
) -> str:
    """
    캐시 키 생성 (v2.1 표준)
    
    문서 참조: docs/tuning/01_metrics_guardrails.md 5.5절
    
    ⚠️ hash() 대신 hashlib.md5() 사용 (프로세스 간 일관성 보장)
    ⚠️ period 구조에 train/val/test range 포함 (룩백·기간 충돌 방지)
    
    Args:
        params: 튜닝 파라미터
        lookback_months: 룩백 기간
        period: 기간 구조
        costs: 비용 설정
        data_config: 데이터 설정
        
    Returns:
        MD5 해시 문자열
    """
    # 파라미터 해시
    params_sig = json.dumps(params, sort_keys=True)
    params_hash = hashlib.md5(params_sig.encode()).hexdigest()
    
    # 키 딕셔너리 구성
    key_dict = {
        # 파라미터
        'params_hash': params_hash,
        'lookback_months': lookback_months,
        
        # 기간 (v2.1: 실제 적용 범위 포함)
        'start_date': period.start_date.isoformat(),
        'end_date': period.end_date.isoformat(),
        'train_range': {
            'start': period.train['start'].isoformat(),
            'end': period.train['end'].isoformat()
        } if period.train else None,
        'val_range': {
            'start': period.val['start'].isoformat(),
            'end': period.val['end'].isoformat()
        } if period.val else None,
        'test_range': {
            'start': period.test['start'].isoformat(),
            'end': period.test['end'].isoformat()
        } if period.test else None,
        
        # 비용
        'commission': costs.commission_rate,
        'slippage': costs.slippage_rate,
        
        # 데이터/유니버스 버전
        'data_version': data_config.data_version,
        'universe_version': data_config.universe_version,
        'price_type': data_config.price_type,
        'dividend_handling': data_config.dividend_handling,
    }
    
    # MD5 해시 생성
    # [Audit Item 2] Cache Key Logging
    key_json = json.dumps(key_dict, sort_keys=True)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[CACHE] Generating key with: {key_json}")
        
    return hashlib.md5(key_json.encode()).hexdigest()


class TuningCache:
    """
    튜닝 결과 캐시 (LRU 방식)
    
    멀티 룩백 실행 시 계산량이 3배로 증가하므로 캐시로 중복 계산 방지
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Args:
            max_size: 최대 캐시 크기
        """
        self._cache: OrderedDict[str, BacktestRunResult] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[BacktestRunResult]:
        """
        캐시에서 결과 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            캐시된 결과 또는 None
        """
        if key in self._cache:
            # LRU: 최근 사용된 항목을 끝으로 이동
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, result: BacktestRunResult) -> None:
        """
        캐시에 결과 저장
        
        Args:
            key: 캐시 키
            result: 백테스트 결과
        """
        if key in self._cache:
            # 이미 존재하면 업데이트 후 끝으로 이동
            self._cache[key] = result
            self._cache.move_to_end(key)
        else:
            # 새 항목 추가
            self._cache[key] = result
            
            # 최대 크기 초과 시 가장 오래된 항목 제거
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def clear(self) -> None:
        """캐시 초기화"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    @property
    def size(self) -> int:
        """현재 캐시 크기"""
        return len(self._cache)
    
    @property
    def hit_rate(self) -> float:
        """캐시 적중률"""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0
    
    def stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        return {
            'size': self.size,
            'max_size': self._max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{self.hit_rate:.1%}"
        }


# 전역 캐시 인스턴스
_global_cache: Optional[TuningCache] = None


def get_global_cache() -> TuningCache:
    """전역 캐시 인스턴스 반환"""
    global _global_cache
    if _global_cache is None:
        _global_cache = TuningCache()
    return _global_cache


def clear_global_cache() -> None:
    """전역 캐시 초기화 (인스턴스 완전 리셋)"""
    global _global_cache
    _global_cache = TuningCache()
