# -*- coding: utf-8 -*-
"""
app/tuning/cache_key.py — P167-R 파라미터 해시 (중복 trial 감지)

레거시 참조: _archive/legacy_20260102/extensions/tuning/types.py compute_params_hash
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict


def compute_params_hash(params: Dict[str, Any]) -> str:
    """
    파라미터 딕셔너리 → 16자리 SHA-256 해시.

    float 값을 고정 소수점으로 정규화하여 부동소수점 오차로 인한
    불일치를 방지.
    """
    normalized = {}
    for k, v in sorted(params.items()):
        if isinstance(v, float):
            normalized[k] = round(v, 6)
        else:
            normalized[k] = v
    params_str = json.dumps(normalized, sort_keys=True)
    return hashlib.sha256(params_str.encode()).hexdigest()[:16]
