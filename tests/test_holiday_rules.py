import os
import sys
import glob
import pandas as pd

CACHE_BASE = os.path.join('data', 'cache', 'kr')

def assert_no_weekend_rows(df: pd.DataFrame, code: str) -> None:
    # 주말(토:5, 일:6) 인덱스가 존재하면 실패
    wdays = df.index.weekday
    if ((wdays == 5) | (wdays == 6)).any():
        raise AssertionError(f"Weekend rows found in cache for {code}")

def main() -> int:
    files = sorted(glob.glob(os.path.join(CACHE_BASE, '*.pkl')))
    if not files:
        print('[WARN] No cache files to test')
        return 0
    fail = 0
    for fp in files:
        try:
            df = pd.read_pickle(fp)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            code = os.path.basename(fp).replace('.pkl', '')
            assert_no_weekend_rows(df, code)
            print(f"[OK] {code} weekend-free rows={len(df)}")
        except Exception as e:
            print(f"[FAIL] {os.path.basename(fp)}: {e}")
            fail += 1
    print(f"Summary: total={len(files)}, fail={fail}")
    return 0 if fail == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
