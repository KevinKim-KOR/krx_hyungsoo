#!/usr/bin/env python3
import sys
from pathlib import Path
import pandas as pd
from datetime import date

# 기대: utils.trading_day 가 제공됨
try:
    from utils.trading_day import last_trading_day
except Exception as e:
    print(f"[STALE] utils.trading_day import failed: {e}", file=sys.stderr)
    sys.exit(2)

def main():
    # 1) 오늘 기준 '기대되는 마지막 거래일'
    try:
        expected = last_trading_day().date()
    except Exception as e:
        print(f"[STALE] cannot compute last_trading_day: {e}", file=sys.stderr)
        sys.exit(2)

    # 2) 캐시의 최신 거래일 확인(있으면 비교)
    cache = Path("data/cache/kr/trading_days.pkl")
    if not cache.exists():
        print(f"[STALE] cache missing: {cache}", file=sys.stderr)
        sys.exit(2)

    try:
        df = pd.read_pickle(cache)
        # df 가 시리즈/데이터프레임 형태 모두 허용
        if hasattr(df, "index") and len(df.index) > 0:
            # 인덱스/컬럼 어디든 날짜가 있을 수 있으므로 가장 최신 날짜 추정
            if isinstance(df.index, pd.DatetimeIndex):
                found = df.index.max().date()
            else:
                # 컬럼 안에서 datetime 찾기 (fallback)
                dtcols = [c for c in getattr(df, "columns", []) if "date" in str(c).lower()]
                if dtcols:
                    found = pd.to_datetime(df[dtcols[0]]).max().date()
                else:
                    # 마지막 수단: 전체 값을 datetime으로 시도
                    found = pd.to_datetime(df.stack(dropna=False), errors="coerce").max().date()
        else:
            # 단순 리스트/시리즈일 수도 있음
            s = pd.to_datetime(pd.Series(df), errors="coerce")
            found = s.max().date()
    except Exception as e:
        print(f"[STALE] cannot read {cache}: {e}", file=sys.stderr)
        sys.exit(2)

    if found != expected:
        print(f"[STALE] trading_days cache not fresh "
              f"(expected {expected}, found {found})", file=sys.stderr)
        sys.exit(2)

    print(f"[FRESH] trading_days cache OK ({found})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
