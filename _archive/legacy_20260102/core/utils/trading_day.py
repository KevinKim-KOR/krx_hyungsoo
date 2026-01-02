# utils/trading_day.py
# -*- coding: utf-8 -*-
import datetime as dt

KST = dt.timezone(dt.timedelta(hours=9))

def is_trading_day(d: dt.date = None) -> bool:
    """한국거래소 영업일 여부. 우선 pykrx로 판정, 실패 시 평일이면 True."""
    today = d or dt.datetime.now(KST).date()
    # 주말은 무조건 휴장
    if today.weekday() >= 5:
        return False
    # pykrx가 있으면 실제 영업일로 판정
    try:
        from pykrx.stock import get_open_market_days
        s = today.strftime("%Y%m%d")
        return len(get_open_market_days(s, s)) == 1
    except Exception:
        # fallback: 평일은 거래일 간주(이전 규칙 유지)
        return True

def in_trading_hours(t: dt.time = None) -> bool:
    """장중(대략 08:50~16:00 KST) 여부. 매 5분 배치용."""
    nowt = t or dt.datetime.now(KST).time()
    return dt.time(8, 50) <= nowt <= dt.time(16, 0)

