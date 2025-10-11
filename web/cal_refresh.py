#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX trading_days.pkl refresher
Priority:
  1) pandas_market_calendars 'XKRX'
  2) exchange_calendars 'XKRX'
  3) Fallback: weekdays-only (Mon~Fri)
Exit codes:
  0: success
  3: external-data-unavailable (no src)
  2: other failure
"""
from __future__ import annotations
import sys, pickle, os
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
CACHE.parent.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now().date()
START = (TODAY.replace(day=1) - timedelta(days=370)).replace(day=1)  # ~12m+ cushion
END   = TODAY + timedelta(days=370)

def _try_pmc():
    try:
        import pandas as pd  # noqa
        import pandas_market_calendars as mcal  # type: ignore
        krx = mcal.get_calendar("XKRX")
        sched = krx.schedule(start_date=START, end_date=END)
        days = list(pd.to_datetime(sched.index).date)
        print(f"[SRC] using=pandas_market_calendars days={len(days)} last={days[-1] if days else None}")
        return days
    except Exception as e:
        print(f"[SRC] pmc not available: {e}")
        return None

def _try_excals():
    try:
        import exchange_calendars as xcals  # type: ignore
        cal = xcals.get_calendar("XKRX")
        days = [d.date for d in cal.sessions_in_range(START, END)]
        print(f"[SRC] using=exchange_calendars days={len(days)} last={days[-1] if days else None}")
        return days
    except Exception as e:
        print(f"[SRC] exchange_calendars not available: {e}")
        return None

def _fallback_weekdays():
    days = []
    cur = START
    while cur <= END:
        if cur.weekday() < 5:  # 0~4: Mon-Fri
            days.append(cur)
        cur += timedelta(days=1)
    print(f"[SRC] using=fallback_weekdays days={len(days)} last={days[-1] if days else None}")
    return days

def main():
    # choose source
    days = _try_pmc()
    if not days:
        days = _try_excals()
    if not days:
        # fallback always available
        days = _fallback_weekdays()

    if not days:
        # realistically unreachable; if both libs missing fallback exists
        print("[ERROR] no calendar source available")
        return 3

    # write cache (as pickle list of datetime.date)
    with open(CACHE, "wb") as f:
        pickle.dump(days, f)
    print(f"[DONE] wrote {CACHE} last={days[-1] if days else None} count={len(days)}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"[ERROR] cal_refresh failed: {e}")
        sys.exit(2)
