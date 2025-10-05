#!/usr/bin/env python3
import sys, yaml
from pathlib import Path
import pandas as pd
from datetime import date

ROOT = Path(__file__).resolve().parents[2]

def _to_series(obj) -> pd.Series:
    """Datetime-like 객체를 Series로 표준화."""
    if isinstance(obj, pd.DatetimeIndex):
        return pd.Series(obj)
    if isinstance(obj, pd.Series):
        # dtype이 datetime이 아니라면 변환 시도
        return pd.to_datetime(obj, errors="coerce")
    if isinstance(obj, pd.Index):
        return pd.to_datetime(pd.Series(obj), errors="coerce")
    # DataFrame 등은 호출하는 쪽에서 컬럼 단위로 넘겨야 함
    return pd.to_datetime(pd.Series(obj), errors="coerce")

def _latest_trading_day_from_cache() -> date:
    """data/cache/kr/trading_days.pkl에서 오늘 이하 최대 거래일을 계산."""
    p = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
    if not p.exists():
        raise FileNotFoundError(f"trading_days cache missing: {p}")

    obj = pd.read_pickle(p)
    series_parts = []

    # 1) 인덱스가 DatetimeIndex인 경우
    idx = getattr(obj, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        series_parts.append(_to_series(idx))

    # 2) 컬럼 중 'date' 유사 컬럼 우선
    cols = getattr(obj, "columns", [])
    for c in cols:
        if "date" in str(c).lower():
            s = _to_series(obj[c])
            series_parts.append(s)

    # 3) 마지막 수단: 값 전체에서 날짜 추출
    if not series_parts:
        try:
            s = pd.to_datetime(obj.stack(dropna=False), errors="coerce")
            series_parts.append(s)
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

    # 인덱스 우선
    idx = getattr(df, "index", None)
    if isinstance(idx, pd.DatetimeIndex) and len(idx):
        return pd.to_datetime(idx).max().date()

    # 'date' 유사 컬럼
    for col in getattr(df, "columns", []):
        if "date" in str(col).lower():
            s = pd.to_datetime(df[col], errors="coerce")
            if s.notna().any():
                return s.max().date()

    # 전체 값에서 추출
    try:
        s = pd.to_datetime(df.stack(dropna=False), errors="coerce")
        if s.notna().any():
            return s.max().date()
    except Exception:
        pass

    raise ValueError(f"no datetime found in {p.name}")

def main():
    # 기대 거래일: trading_days 캐시에서 계산(외부/유틸 의존 제거)
    try:
        expected = _latest_trading_day_from_cache()
    except Exception as e:
        print(f"[STALE] cannot determine expected trading day: {e}", file=sys.stderr)
        return 2

    # 프로브 심볼
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
