#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import pandas as pd
from datetime import date, datetime

ROOT = Path(__file__).resolve().parents[2]

def _to_series(obj) -> pd.Series:
    if isinstance(obj, pd.DatetimeIndex): return pd.Series(obj)
    if isinstance(obj, pd.Series):        return pd.to_datetime(obj, errors="coerce")
    if isinstance(obj, pd.Index):         return pd.to_datetime(pd.Series(obj), errors="coerce")
    return pd.to_datetime(pd.Series(obj), errors="coerce")

def _latest_trading_day_from_cache():
    p = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
    if not p.exists():
        raise FileNotFoundError(f"missing: {p}")
    obj = pd.read_pickle(p)
    parts = []
    idx = getattr(obj, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx): parts.append(_to_series(idx))
    for c in getattr(obj, "columns", []):
        if "date" in str(c).lower(): parts.append(_to_series(obj[c]))
    if not parts:
        try: parts.append(pd.to_datetime(obj.stack(dropna=False), errors="coerce"))
        except Exception: pass
    cat = pd.concat(parts, axis=0).dropna().sort_values()
    today = pd.Timestamp.today().normalize()
    # 오늘이 영업일이면 “전일 영업일”, 아니면 “오늘 이전 마지막 영업일”
    prev = cat[cat < today]
    if prev.empty: raise ValueError("no trading day < today")
    prev_day = prev.max().date()
    is_today_trading = (cat.max().normalize().date() == today.date()) or (today.date() in set(d.date() for d in cat))
    return prev_day, is_today_trading

def _max_dt_from_pickle(p: Path):
    df = pd.read_pickle(p)
    idx = getattr(df, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        return pd.to_datetime(idx).max().date()
    for col in getattr(df, "columns", []):
        if "date" in str(col).lower():
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().any(): return s.max().date()
    try:
        s = pd.to_datetime(df.stack(dropna=False), errors="coerce")
        if s.notna().any(): return s.max().date()
    except Exception:
        pass
    raise ValueError(f"no datetime in {p.name}")

def latest_probe_date():
    """config/data_sources.yaml 의 probes(신규) 또는 postcheck_probes(구키) 사용."""
    base = ROOT / "data" / "cache" / "kr"
    cfg  = ROOT / "config" / "data_sources.yaml"
    probes = ["069500.KS.pkl", "069500.pkl"]
    if cfg.exists():
        try:
            import yaml
            y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            probes = y.get("probes") or y.get("postcheck_probes") or probes
        except Exception:
            pass
    dates = []
    for name in probes:
        p = base / name
        if not p.exists():
            continue
        try:
            dates.append(_max_dt_from_pickle(p))
        except Exception:
            pass
    return max(dates) if dates else None

def main():
    try:
        prev_day, is_today_trading = _latest_trading_day_from_cache()
    except Exception as e:
        print(f"[PRECHECK] calendar unavailable: {e}", file=sys.stderr)
        # 달력이 없으면 일단 재시도 유도
        return 2

    # 오늘이 영업일이 아니면 스캐너도 어차피 스킵 → 통과
    if not is_today_trading:
        print("[PRECHECK] non-trading day → OK")
        return 0

    lp = latest_probe_date()
    if not lp:
        print(f"[PRECHECK] probe missing → expected {prev_day}, found None", file=sys.stderr)
        return 2

    print(f"[PRECHECK] expected(prev trading day)={prev_day}, probes_latest={lp}")
    # 전일 영업일보다 프로브가 과거면 스테일 → 재시도 유도(RC=2)
    if lp < prev_day:
        print(f"[STALE] EOD stale (probes {lp} < expected {prev_day})", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
