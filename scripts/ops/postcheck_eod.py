#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import pandas as pd
from datetime import date

ROOT = Path(__file__).resolve().parents[2]

def _latest_trading_day_from_cache() -> date:
    """data/cache/kr/trading_days.pkl 에서 오늘 이하의 가장 최근 거래일을 계산."""
    p = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
    if not p.exists():
        raise FileNotFoundError(f"trading_days cache missing: {p}")
    obj = pd.read_pickle(p)

    # 인덱스/컬럼/값 어디에 있든 최대한 날짜를 추출
    candidates = []
    if isinstance(getattr(obj, "index", None), pd.DatetimeIndex) and len(obj.index):
        candidates.append(pd.to_datetime(obj.index))
    if hasattr(obj, "columns"):
        for c in obj.columns:
            if "date" in str(c).lower():
                s = pd.to_datetime(obj[c], errors="coerce")
                candidates.append(s)
    if not candidates:
        try:
            s = pd.to_datetime(obj.stack(dropna=False), errors="coerce")
            candidates.append(s)
        except Exception:
            pass

    if not candidates:
        raise ValueError("no datetime found in trading_days cache")

    today = pd.Timestamp.today().normalize()
    latest = pd.concat(candidates, axis=0).dropna()
    latest = latest[latest <= today]
    if latest.empty:
        raise ValueError("no trading day <= today in cache")
    return latest.max().date()

def _max_dt_from_pickle(p: Path) -> date:
    df = pd.read_pickle(p)
    # DatetimeIndex 우선
    if isinstance(getattr(df, "index", None), pd.DatetimeIndex) and len(df.index):
        return pd.to_datetime(df.index).max().date()
    # 'date' 컬럼 추정
    if hasattr(df, "columns"):
        for col in df.columns:
            if "date" in str(col).lower():
                s = pd.to_datetime(df[col], errors="coerce")
                if s.notna().any():
                    return s.max().date()
    # 최후 수단: 전체 값에서 날짜 추출
    try:
        s = pd.to_datetime(df.stack(dropna=False), errors="coerce")
        if s.notna().any():
            return s.max().date()
    except Exception:
        pass
    raise ValueError(f"no datetime found in {p.name}")

def main():
    # 0) 기대 거래일: trading_days 캐시 기반 (utils 의존 제거)
    try:
        expected = _latest_trading_day_from_cache()
    except Exception as e:
        print(f"[STALE] cannot determine expected trading day: {e}", file=sys.stderr)
        return 2

    # 1) 프로브 심볼 목록
    probes = ["069500.KS.pkl", "069500.pkl"]
    cfg = ROOT / "config" / "data_sources.yaml"
    if cfg.exists():
        try:
            y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            probes = y.get("postcheck_probes", probes)
        except Exception:
            pass

    base = ROOT / "data" / "cache" / "kr"
    if not base.exists():
        print(f"[STALE] cache dir missing: {base}", file=sys.stderr)
        return 2

    ok = 0
    for name in probes:
        p = base / name
        if not p.exists():
            print(f"[STALE] probe missing: {p}", file=sys.stderr)
            continue
        try:
            found = _max_dt_from_pickle(p)
            if found != expected:
                print(f"[STALE] {name}: expected {expected}, found {found}", file=sys.stderr)
            else:
                print(f"[OK] {name} up-to-date ({found})")
                ok += 1
        except Exception as e:
            print(f"[STALE] {name}: read error: {e}", file=sys.stderr)

    return 0 if ok > 0 else 2

if __name__ == "__main__":
    sys.exit(main())
