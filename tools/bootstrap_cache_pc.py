# KR 캐시 부트스트랩(증분 저장). 의존: pandas, pyyaml, pykrx (requirements-nas.txt에 포함 가정)
import argparse
import os
import sys
import time
import json
from typing import List, Optional

import pandas as pd

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

try:
    from pykrx import stock
except Exception:  # pragma: no cover
    stock = None

CACHE_BASE = os.path.join('data', 'cache', 'kr')
ETF_JSON = os.path.join('etf.json')  # 존재 시 is_active 필터 사용

def load_watchlist(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    if path.endswith('.yaml') or path.endswith('.yml'):
        if yaml is None:
            return []
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            for k in ('codes', 'tickers', 'symbols'):
                if k in data and isinstance(data[k], list):
                    return [str(x) for x in data[k]]
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith('#')]

def load_active_from_etf_json(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        out = []
        for row in data:
            if isinstance(row, dict) and row.get('is_active', True):
                code = str(row.get('code') or row.get('ticker') or '').strip()
                if code:
                    out.append(code)
        return out
    except Exception:
        return []

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def fetch_ohlcv_kr(code: str, start: str, end: str) -> pd.DataFrame:
    """
    pykrx를 활용해 [date, open, high, low, close, volume] 일봉을 반환.
    start/end: YYYY-MM-DD
    """
    if stock is None:
        raise RuntimeError('pykrx is not installed. Install via requirements-nas.txt')
    s = start.replace('-', '')
    e = end.replace('-', '')
    df = stock.get_market_ohlcv_by_date(s, e, code)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns=str.lower)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    cols = ['open', 'high', 'low', 'close', 'volume']
    df = df[cols]
    df.index.name = 'date'
    return df

def load_existing_cache(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_pickle(path)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
            df.index = pd.to_datetime(df.index)
            return df.sort_index()
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def incremental_merge(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if old is None or old.empty:
        return new
    if new is None or new.empty:
        return old
    merged = pd.concat([old, new])
    merged = merged[~merged.index.duplicated(keep='last')].sort_index()
    return merged

def bootstrap(tickers: List[str], since: str, until: str, sleep_sec: float = 0.7) -> None:
    ensure_dir(CACHE_BASE)
    total = len(tickers)
    for i, code in enumerate(tickers, 1):
        cache_path = os.path.join(CACHE_BASE, f"{code}.pkl")
        old = load_existing_cache(cache_path)
        last_dt = None if old.empty else old.index.max().strftime('%Y-%m-%d')
        start = last_dt or since
        print(f"[{i}/{total}] {code} from {start} → {until}")
        try:
            new_df = fetch_ohlcv_kr(code, start, until)
            if new_df.empty and not old.empty:
                print(f"  [SKIP] no new data")
                continue
            merged = incremental_merge(old, new_df)
            merged.to_pickle(cache_path)
            print(f"  [OK] rows={len(merged)} saved: {cache_path}")
            time.sleep(sleep_sec)
        except Exception as e:
            print(f"  [ERROR] {code}: {e}")

def parse_tickers(arg: str, watchlist_path: Optional[str]) -> List[str]:
    if arg.upper() == 'KRALL':
        lst = load_active_from_etf_json(ETF_JSON)
        if lst:
            return lst
        if watchlist_path:
            lst = load_watchlist(watchlist_path)
            if lst:
                return lst
        print('[WARN] KRALL fallback: no etf.json/watchlist, please provide --tickers explicitly')
        return []
    if os.path.exists(arg):
        return load_watchlist(arg)
    return [x.strip() for x in arg.split(',') if x.strip()]

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description='Bootstrap KR cache incrementally (PC)')
    ap.add_argument('--tickers', required=True, help='e.g., "069500,329200" or path or KRALL')
    ap.add_argument('--since', default='2018-01-01')
    ap.add_argument('--until', default=pd.Timestamp.today().strftime('%Y-%m-%d'))
    ap.add_argument('--watchlist', default=os.environ.get('KRX_WATCHLIST', 'secret/watchlist.yaml'))
    ap.add_argument('--sleep', type=float, default=0.7)
    args = ap.parse_args(argv)

    tks = parse_tickers(args.tickers, args.watchlist)
    if not tks:
        print('[ERROR] No tickers resolved. Use --tickers or prepare etf.json/watchlist')
        return 2

    bootstrap(tks, args.since, args.until, args.sleep)
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
