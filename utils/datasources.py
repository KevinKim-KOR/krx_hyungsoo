#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Tuple, Any
import yaml

# 프로젝트 루트 (utils/ 기준 상위)
ROOT = Path(__file__).resolve().parents[1]
CFG  = ROOT / "config" / "data_sources.yaml"

@lru_cache(maxsize=1)
def _load_yaml() -> Dict[str, Any]:
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data
    except Exception:
        return {}

# ---------------------------
# 신규/일반화된 API (신·구 스키마 모두 지원)
# ---------------------------

def get_benchmark_map() -> Dict[str, Any]:
    """YAML benchmarks 섹션 전체 반환(없으면 {})."""
    y = _load_yaml()
    b = y.get("benchmarks") or {}
    return b if isinstance(b, dict) else {}

def local_keys_for_benchmark(name: str) -> Tuple[str, ...]:
    """
    벤치마크 이름('KOSPI','KOSDAQ','S&P500' 등)에 대한 로컬키 묶음.
    신스키마: benchmarks.<name>.symbols.local_keys
    구스키마(폴백): defaults.benchmark_candidates (KOSPI 전용 취급)
    """
    bmap = get_benchmark_map()
    if name in bmap:
        syms = ((bmap[name] or {}).get("symbols") or {}).get("local_keys") or []
        return tuple(str(x) for x in syms)

    # 구스키마 폴백(주로 KOSPI 용도)
    if name.upper() == "KOSPI":
        return tuple(benchmark_candidates())
    return tuple()

def label_for_benchmark(name: str) -> str:
    """표시용 라벨(간단히 이름 그대로 리턴)."""
    return name

def probes_eod_fresh() -> List[str]:
    """
    EOD 신선도 확인용 프로브 파일 목록.
    신스키마: probes.eod_fresh
    구스키마 폴백: ["069500.KS.pkl","069500.pkl"]
    """
    y = _load_yaml()
    p = y.get("probes") or {}
    arr = p.get("eod_fresh") or []
    if arr:
        return [str(x) for x in arr]
    return ["069500.KS.pkl", "069500.pkl"]

def calendar_symbol_priority() -> List[str]:
    """
    캘린더 생성 시 우선순위 심볼.
    신스키마: probes.calendar_symbols_priority
    구스키마: calendar.symbol_priority
    기본값: ["069500.KS","069500"]
    """
    y = _load_yaml()
    # 신스키마 우선
    p = y.get("probes") or {}
    arr = p.get("calendar_symbols_priority")
    if isinstance(arr, list) and arr:
        return [str(x) for x in arr]
    # 구스키마 폴백
    arr = (y.get("calendar") or {}).get("symbol_priority") or []
    if arr:
        return [str(x) for x in arr]
    # 기본
    return ["069500.KS","069500"]

def regime_ticker_priority() -> List[str]:
    """
    레짐 판단용 티커 우선순위.
    신스키마: regime.ticker_priority (예: ["^GSPC","SPY","069500.KS"])
    구스키마: defaults.regime.ticker (단일), 있으면 [그 값]으로 구성
    기본: ["^GSPC","SPY","069500.KS"]
    """
    y = _load_yaml()
    r = y.get("regime") or {}
    arr = r.get("ticker_priority")
    if isinstance(arr, list) and arr:
        return [str(x) for x in arr]

    # 구스키마 단일
    tk = (((y.get("defaults") or {}).get("regime") or {}).get("ticker"))
    if tk:
        return [str(tk)]

    return ["^GSPC","SPY","069500.KS"]

def regime_ticker() -> str:
    """우선순위의 첫 번째 티커(단일 값 필요할 때 사용)."""
    pri = regime_ticker_priority()
    return str(pri[0]) if pri else "069500.KS"

def load_universe() -> List[str]:
    """
    유니버스 전체(ETF/주식 등) 평탄화된 리스트.
    신스키마: universe.etfs / universe.equities / universe.others
    구스키마: universe.symbols
    기본: KR 대표 바스켓
    """
    y = _load_yaml()
    u = (y.get("universe") or {})

    out: List[str] = []
    for key in ("etfs", "equities", "others"):
        lst = u.get(key) or []
        for v in lst:
            if isinstance(v, dict):
                if v.get("is_active", True) and v.get("code"):
                    out.append(str(v["code"]))
            else:
                out.append(str(v))

    if not out:
        # 구스키마
        arr = u.get("symbols") or []
        out = [str(x) for x in arr]

    if not out:
        out = ["069500.KS","133690.KS","091160.KS","305720.KS","373220.KS","005930.KS","000660.KS"]

    # 중복 제거(순서 보존)
    out = [x for x in dict.fromkeys(out) if x]
    return out

def default_market_code(country: str = "kr") -> str:
    """국가별 대표 벤치마크 코드(로컬키 첫 번째 우선)."""
    if country.lower() == "kr":
        keys = local_keys_for_benchmark("KOSPI")
        return keys[0] if keys else "069500"
    if country.lower() == "us":
        keys = local_keys_for_benchmark("S&P500")
        return keys[0] if keys else "SPY"
    return "SPY"

# ---------------------------
# (레거시) 기존 함수 시그니처 유지: 내부에서 신규 API로 위임
# ---------------------------

def benchmark_candidates() -> List[str]:
    """
    (레거시) 구스키마: defaults.benchmark_candidates
    없을 때는 신스키마 KOSPI의 local_keys → 기본값
    """
    y = _load_yaml()
    cand = (((y.get("defaults") or {}).get("benchmark_candidates")) or [])
    if cand:
        return [str(x) for x in cand]
    keys = local_keys_for_benchmark("KOSPI")
    if keys:
        return list(keys)
    return ["069500","069500.KS"]

# regime_ticker()는 위 신규 API와 동일 이름/동작을 그대로 제공

# calendar_symbol_priority()는 위 신규 API와 동일 이름/동작을 그대로 제공

def universe_symbols() -> List[str]:
    """(레거시) 기존 호출 호환: load_universe() 결과를 그대로 반환."""
    return load_universe()
