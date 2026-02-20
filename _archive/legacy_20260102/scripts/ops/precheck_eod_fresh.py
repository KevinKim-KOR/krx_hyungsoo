#!/usr/bin/env python3
from __future__ import annotations
import argparse, glob, os, sys
from datetime import datetime, timedelta, date
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path

import pandas as pd

def _now_kr():
    # NAS는 Asia/Seoul이 기본일 가능성이 높지만, 안전하게 로컬 날짜 사용
    return pd.Timestamp(datetime.now(KST)).tz_localize(None)

def _load_trading_days_cache(cache_path: str) -> pd.DatetimeIndex | None:
    try:
        if os.path.isfile(cache_path):
            ser = pd.read_pickle(cache_path)
            # 캐시에 DatetimeIndex or Series 형태 저장돼 있을 수 있음
            if isinstance(ser, pd.DatetimeIndex):
                return ser
            if hasattr(ser, "index") and isinstance(ser.index, pd.DatetimeIndex):
                return ser.index
            # 리스트/Series를 DatetimeIndex로 시도
            return pd.DatetimeIndex(pd.to_datetime(ser))
    except Exception:
        pass
    return None

def _build_trading_days_fallback(start: date, end: date) -> pd.DatetimeIndex:
    # exchange_calendars 가용 시 사용, 없으면 영업일 가정(월~금)
    try:
        import exchange_calendars as xcals
        cal = xcals.get_calendar("XKRX")
        days = cal.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
        return pd.DatetimeIndex(days.tz_localize(None))
    except Exception:
        rng = pd.bdate_range(start=start, end=end, freq="C")  # 월~금
        return pd.DatetimeIndex(rng)

def _expected_trading_day(today: date, cache_path="data/cache/kr/trading_days.pkl") -> pd.Timestamp:
    td = _load_trading_days_cache(cache_path)
    if td is None or len(td) == 0:
        # 캐시가 없거나 오래되면 2년 범위로 재구성
        td = _build_trading_days_fallback(today - timedelta(days=730), today + timedelta(days=365))
    # today(현지) 기준, today 이하의 마지막 세션
    td = td.tz_localize(None)
    last = td[td <= pd.Timestamp(today)]
    if len(last) == 0:
        return pd.Timestamp(today)
    return pd.Timestamp(last.max().date())

def _cache_latest_parquet(glob_pat="data/cache/ohlcv/*.parquet") -> pd.Timestamp | None:
    paths = sorted(glob.glob(glob_pat))
    if not paths:
        return None
    latest = None
    # 빠르게 최대 인덱스만 구함 (pyarrow가 있으면 메모리 효율 ↑)
    try:
        import pyarrow.parquet as pq
        for p in paths:
            try:
                tbl = pq.read_table(p)
                # 파케를 바로 스캔하기 어렵다면 전체 로드 대신 판다스로 인덱스만 추정할 수도 있음
                df = tbl.to_pandas()
                if df.empty:
                    continue
                idx = pd.to_datetime(df.index)
                mx = idx.max().tz_localize(None)
                latest = mx if (latest is None or mx > latest) else latest
            except Exception:
                # 파케 로드 실패 시 판다스 parquet로 재시도
                try:
                    df = pd.read_parquet(p)
                    if df.empty:
                        continue
                    mx = pd.to_datetime(df.index).max().tz_localize(None)
                    latest = mx if (latest is None or mx > latest) else latest
                except Exception:
                    continue
    except Exception:
        # pyarrow 미가용이면 판다스 경로
        for p in paths:
            try:
                df = pd.read_parquet(p)
                if df.empty:
                    continue
                mx = pd.to_datetime(df.index).max().tz_localize(None)
                latest = mx if (latest is None or mx > latest) else latest
            except Exception:
                continue
    return latest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="report")
    args = ap.parse_args()

    now = _now_kr()
    today = now.date()

    expected = _expected_trading_day(today)
    cache_latest = _cache_latest_parquet()

    print(f"[RUN] report_precheck {now:%Y-%m-%d %H:%M:%S}")
    print(f"[INFO] expected={expected.date()}", flush=True)
    print(f"[INFO] cache_latest={None if cache_latest is None else cache_latest.date()}", flush=True)

    if cache_latest is None or cache_latest.date() < expected.date():
        print("[KRX EOD][RC:2] 지연 감지 (캐시 최신일 < 기대 최신일)")
        print(" - 조치: 인게스트(캐시) 더 수집 또는 잠시 후 재시도")
        sys.exit(2)

    print("[DONE] report_precheck OK (cache covers expected)")
    sys.exit(0)

if __name__ == "__main__":
    main()
