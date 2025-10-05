#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import pandas as pd
from datetime import date

# 기대되는 "마지막 거래일"
try:
    from utils.trading_day import last_trading_day
except Exception as e:
    print(f"[POSTCHECK] import utils.trading_day failed: {e}", file=sys.stderr)
    sys.exit(2)

def _max_dt_from_pickle(p: Path):
    df = pd.read_pickle(p)
    # DatetimeIndex 우선
    if isinstance(getattr(df, "index", None), pd.DatetimeIndex) and len(df.index):
        return pd.to_datetime(df.index).max().date()
    # date 컬럼/첫 컬럼 탐색
    for col in (c for c in getattr(df, "columns", []) if "date" in str(c).lower()):
        s = pd.to_datetime(df[col], errors="coerce")
        if s.notna().any():
            return s.max().date()
    # 최후 수단: 전 값에서 날짜 추출
    s = pd.to_datetime(getattr(df, "stack", lambda *a, **k: pd.Series([]))(), errors="coerce")
    if s.notna().any():
        return s.max().date()
    raise ValueError("no datetime found")

def main():
    expected = last_trading_day().date()

    # 프로브 심볼(환경/설정이 있으면 그것 사용)
    probes = ["069500.KS.pkl", "069500.pkl"]
    cfg = Path("config/data_sources.yaml")
    if cfg.exists():
        try:
            y = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            probes = y.get("postcheck_probes", probes)
        except Exception:
            pass

    base = Path("data/cache/kr")
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

    if ok == 0:
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
