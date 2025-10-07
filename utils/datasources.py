#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
import yaml

ROOT = Path(__file__).resolve().parents[1]  # utils/ 기준 상위
CFG  = ROOT / "config" / "data_sources.yaml"

@lru_cache(maxsize=1)
def _load_yaml() -> dict:
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def benchmark_candidates() -> list[str]:
    y = _load_yaml()
    cand = (((y.get("defaults") or {}).get("benchmark_candidates")) or [])
    # 안전한 폴백(기존 동작 유지)
    return cand if cand else ["069500", "069500.KS"]

def regime_ticker() -> str:
    y = _load_yaml()
    tk = (((y.get("defaults") or {}).get("regime") or {}).get("ticker"))
    return tk or "069500.KS"

def calendar_symbol_priority() -> list[str]:
    y = _load_yaml()
    arr = (y.get("calendar") or {}).get("symbol_priority") or []
    return arr if arr else ["069500.KS","069500"]

def universe_symbols() -> list[str]:
    y = _load_yaml()
    arr = ((y.get("universe") or {}).get("symbols")) or []
    return arr if arr else ["069500.KS","133690.KS","091160.KS","305720.KS","373220.KS","005930.KS","000660.KS"]
