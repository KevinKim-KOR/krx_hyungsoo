#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRX trading_days.pkl refresher
Priority:
  1) pandas_market_calendars 'XKRX'  (Py3.8: requires backports.zoneinfo)
  2) exchange_calendars 'XKRX'       (cap END to last_session)
  3) Fallback: weekdays-only (Mon~Fri)
Exit codes:
  0: success
  3: external-data-unavailable (no src)
  2: other failure
"""
from __future__ import annotations

import sys, pickle
from pathlib import Path
from datetime import datetime, timedelta, date

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "kr" / "trading_days.pkl"
CACHE.parent.mkdir(parents=True, exist_ok=True)

TODAY: date = datetime.now().date()
START: date = (TODAY.replace(day=1) - timedelta(days=370)).replace(day=1)  # ~12m+ cushion
END:   date = TODAY + timedelta(days=370)

def _to_date_list(idx) -> list[date]:
    """Convert a DatetimeIndex / iterable of timestamps to list[date]."""
    out = []
    try:
        import pandas as pd  # type: ignore
        if hasattr(idx, "to_pydatetime"):
            vals = idx.to_pydatetime()
        else:
            vals = list(idx)
        for x in vals:
            if isinstance(x, (datetime,)):
                out.append(x.date())
            else:
                # numpy datetime64 / pandas Timestamp / date
                try:
                    # pandas Timestamp has .date()
                    out.append(x.date())
                except Exception:
                    out.append(pd.to_datetime(x).date())
    except Exception:
        # very defensive; best-effort conversion
        for x in idx:
            if isinstance(x, datetime):
                out.append(x.date())
            elif hasattr(x, "date"):
                out.append(x.date())
            else:
                out.append(datetime.fromisoformat(str(x)).date())
    return out

def _try_pmc():
    """Try pandas_market_calendars 'XKRX'."""
    try:
        import pandas_market_calendars as mcal  # type: ignore
        krx = mcal.get_calendar("XKRX")
        # pmc는 schedule().index 가 DatetimeIndex
        sched = krx.schedule(start_date=START, end_date=END)
        days = _to_date_list(sched.index)
        print(f"[SRC] using=pandas_market_calendars days={len(days)} last={days[-1] if days else None}")
        return days
    except Exception as e:
        print(f"[SRC] pmc not available: {e}")
        return None

def _try_excals():
    """Try exchange_calendars 'XKRX' (cap END to last_session)."""
    try:
        import exchange_calendars as xcals  # type: ignore
        cal = xcals.get_calendar("XKRX")
        last_allowed = cal.last_session.date()
        end_capped: date = END if END <= last_allowed else last_allowed
        # sessions_in_range returns pandas.DatetimeIndex
        sessions = cal.sessions_in_range(START, end_capped)
        days = _to_date_list(sessions)
        print(f"[SRC] using=exchange_calendars days={len(days)} last={days[-1] if days else None}")
        return days
    except Exception as e:
        print(f"[SRC] exchange_calendars not available: {e}")
        return None

def _fallback_weekdays():
    days = []
    cur = START
    while cur <= END:
        if cur.weekday() < 5:  # Mon~Fri
            days.append(cur)
        cur += timedelta(days=1)
    print(f"[SRC] using=fallback_weekdays days={len(days)} last={days[-1] if days else None}")
    return days

def main():
    import sys as _sys
    days = None

    # Py<3.9에서는 pmc 건너뜀 (backports.zoneinfo 빌드 이슈 회피)
    if _sys.version_info >= (3, 9):
        days = _try_pmc()

    if not days:
        days = _try_excals()
    if not days:
        days = _fallback_weekdays()

    if not days:
        print("[ERROR] no calendar source available")
        return 3

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
