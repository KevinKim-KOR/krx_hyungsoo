import argparse
import os
import sys
import glob
import pandas as pd
from typing import List, Tuple

def find_cache_files(base: str, country: str):
    path = os.path.join(base, country.lower())
    return sorted(glob.glob(os.path.join(path, '*.pkl')))

def read_df(path: str) -> pd.DataFrame:
    df = pd.read_pickle(path)
    if 'date' in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError('Index must be DatetimeIndex or have a parsable "date" column')
    return df.sort_index()

def check_integrity(df: pd.DataFrame) -> Tuple[bool, list]:
    errors = []
    if df.index.has_duplicates:
        errors.append('duplicate_index')
    if df.index.isnull().any():
        errors.append('null_index')
    if 'close' in df.columns:
        if df['close'].isnull().any():
            errors.append('null_close')
        if (df['close'] < 0).any():
            errors.append('negative_close')
    return (len(errors) == 0), errors

def check_chronology(df: pd.DataFrame) -> Tuple[bool, list]:
    errors = []
    if not df.index.is_monotonic_increasing:
        errors.append('not_monotonic_increasing')
    return (len(errors) == 0), errors

def diagnose(base: str, country: str) -> int:
    files = find_cache_files(base, country)
    if not files:
        print(f"[WARN] No cache files under {base}/{country.lower()} (*.pkl)")
        return 0

    total = len(files)
    ok_cnt, warn_cnt, err_cnt = 0, 0, 0

    for fp in files:
        try:
            df = read_df(fp)
            ok_i, errs_i = check_integrity(df)
            ok_c, errs_c = check_chronology(df)
            errs = errs_i + errs_c
            if ok_i and ok_c:
                print(f"[OK] {os.path.basename(fp)} rows={len(df)}")
                ok_cnt += 1
            else:
                print(f"[WARN] {os.path.basename(fp)} issues={errs}")
                warn_cnt += 1
        except Exception as e:
            print(f"[ERROR] {os.path.basename(fp)}: {e}")
            err_cnt += 1

    print(f"\nSummary: total={total}, ok={ok_cnt}, warn={warn_cnt}, error={err_cnt}")
    return 0 if err_cnt == 0 else 1

def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description='Diagnose cache integrity/index/chronology')
    ap.add_argument('--base', default=os.path.join('data', 'cache'), help='cache base dir (default: data/cache)')
    ap.add_argument('--country', default='kr', help='country code, e.g., kr/us (default: kr)')
    args = ap.parse_args(argv)
    return diagnose(args.base, args.country)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
