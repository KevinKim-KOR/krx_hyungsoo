# scripts/ops/universe.py
from __future__ import annotations
from utils.datasources import load_universe as _load

def load_universe():
    """YAML 기반 유니버스 로더(역호환 엔트리)."""
    return _load()
