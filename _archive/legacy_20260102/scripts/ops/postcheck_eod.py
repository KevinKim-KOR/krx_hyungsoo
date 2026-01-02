#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import pandas as pd
from datetime import date

ROOT = Path(__file__).resolve().parents[2]

def _to_series(obj) -> pd.Series:
    if isinstance(obj, pd.DatetimeIndex):
        return pd.Series(obj)
    if isinstance(obj, pd.Series):
        return pd.to_datetime(obj, errors="coerce")
    if isinstance(obj, pd.Index):
        return pd.to_datetime(pd.Series(obj), errors="coerce")
    return pd.to_datetime(pd.Series(obj), errors="coerce")

def _latest_trading_day_from_cache() -> date:
    p = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
    if not p.exists():
        raise FileNotFoundError(f"trading_days cache missing: {p}")
    obj = pd.read_pickle(p)

    series_parts = []
    idx = getattr(obj, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        series_parts.append(_to_series(idx))
    cols = getattr(obj, "columns", [])
    for c in cols:
        if "date" in str(c).lower():
            series_parts.append(_to_series(obj[c]))
    if not series_parts:
        try:
            series_parts.append(pd.to_datetime(obj.stack(dropna=False), errors="coerce"))
        except Exception:
            pass
    if not series_parts:
        raise ValueError("no datetime found in trading_days cache")

    today = pd.Timestamp.today().normalize()
    cat = pd.concat(series_parts, axis=0).dropna()
    cat = cat[cat <= today]
    if cat.empty:
        raise ValueError("no trading day <= today in cache")
    return cat.max().date()

def _max_dt_from_pickle(p: Path) -> date:
    df = pd.read_pickle(p)
    idx = getattr(df, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        return pd.to_datetime(idx).max().date()
    for col in getattr(df, "columns", []):
        if "date" in str(col).lower():
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().any():
                return s.max().date()
    try:
        s = pd.to_datetime(df.stack(dropna=False), errors="coerce")
        if s.notna().any():
            return s.max().date()
    except Exception:
        pass
    raise ValueError(f"no datetime found in {p.name}")

def main():
    # 1) 프로브 목록
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

    # 2) 각 프로브의 최신 날짜 수집
    found_dates = []
    for name in probes:
        p = base / name
        if not p.exists():
            print(f"[STALE] probe missing: {p}", file=sys.stderr)
            continue
        try:
            found_dates.append((_max_dt_from_pickle(p), name))
        except Exception as e:
            print(f"[STALE] {name}: read error: {e}", file=sys.stderr)

    if not found_dates:
        print("[STALE] no probes readable", file=sys.stderr)
        return 2

    # 3) 기대 거래일 계산: trading_days.pkl vs 프로브 최신 중 더 최신으로 결정
    expected_from_cache = None
    try:
        expected_from_cache = _latest_trading_day_from_cache()
    except Exception as e:
        print(f"[WARN] trading_days cache unusable: {e}", file=sys.stderr)

    latest_found = max(d for d, _ in found_dates)
    if expected_from_cache and expected_from_cache >= latest_found:
        expected = expected_from_cache
        src = "calendar"
    else:
        expected = latest_found
        src = "probes"

    print(f"[INFO] expected trading day = {expected} (source={src})")

    # 4) 통과 기준: 기대일과 같은 프로브가 1개 이상이어야 OK
    ok = sum(1 for d, _ in found_dates if d == expected)
    for d, name in sorted(found_dates, reverse=True):
        if d != expected:
            print(f"[STALE] {name}: expected {expected}, found {d}", file=sys.stderr)

    return 0 if ok > 0 else 2

if __name__ == "__main__":
    sys.exit(main())
