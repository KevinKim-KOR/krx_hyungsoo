#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List
import yaml

ROOT = Path(__file__).resolve().parents[1]  # .../utils/ 기준 상위(프로젝트 루트)
CFG  = ROOT / "config" / "data_sources.yaml"

@lru_cache(maxsize=1)
def _load_yaml() -> Dict[str, Any]:
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            y = yaml.safe_load(f)
            return y if isinstance(y, dict) else {}
    except Exception:
        return {}

def _as_list(v, *, fallback: List[str] = None) -> List[str]:
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    if v is None:
        return list(fallback or [])
    return [str(v)]

def benchmark_candidates() -> List[str]:
    y = _load_yaml()
    cand = (((y.get("defaults") or {}).get("benchmark_candidates")) or
            y.get("benchmark_candidates"))
    return _as_list(cand, fallback=["069500", "069500.KS"])

def calendar_symbol_priority() -> List[str]:
    y = _load_yaml()
    # 기본: calendar.symbol_priority
    cal = y.get("calendar") or {}
    arr = cal.get("symbol_priority")
    # 레거시 alias도 지원
    if not arr:
        arr = y.get("calendar_symbols_priority") or y.get("calendar_symbol_priority")
    return _as_list(arr, fallback=["069500.KS","069500"])

def regime_ticker_priority() -> List[str]:
    y = _load_yaml()
    reg = (y.get("defaults") or {}).get("regime") or {}
    pri = reg.get("ticker_priority")
    if not pri:
        # 레거시: 단일 ticker
        t = reg.get("ticker")
        pri = [t] if t else None
    return _as_list(pri, fallback=["^GSPC","SPY","069500.KS"])

def regime_ticker() -> str:
    pri = regime_ticker_priority()
    return pri[0] if pri else "069500.KS"

def universe_symbols() -> List[str]:
    y = _load_yaml()
    uni = (y.get("universe") or {}).get("symbols")
    return _as_list(uni, fallback=[
        "069500.KS","133690.KS","091160.KS","305720.KS","373220.KS","005930.KS","000660.KS"
    ])

def local_keys_for_benchmark(label: str) -> List[str]:
    y = _load_yaml()
    bm = (y.get("benchmarks") or {}).get(label, {})
    keys = bm.get("local_keys")
    defaults = {
        "KOSPI":  ["069500.KS","069500","KOSPI","KOSPI_ETF"],
        "KOSDAQ": ["229200.KS","229200","KOSDAQ"],
        "S&P500": ["SPY","^GSPC","S&P500"],
    }
    return _as_list(keys, fallback=defaults.get(label, []))

def label_for_benchmark(label: str) -> str:
    y = _load_yaml()
    bm = (y.get("benchmarks") or {}).get(label, {})
    return str(bm.get("label") or label)
