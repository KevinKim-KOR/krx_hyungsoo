# -*- coding: utf-8 -*-
from typing import Optional
from datetime import datetime, date, time, timedelta, timezone
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily
from utils.datasources import benchmark_candidates, default_market_code

KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    return datetime.now(KST)

#def latest_trading_date_by_market(code: str = "069500") -> Optional[str]:
def latest_trading_date_by_market(code: str | None = None) -> Optional[str]:
    if not code:
        code = default_market_code("kr")  # 없으면 "069500" 폴백
    with SessionLocal() as s:
        d0 = s.execute(select(func.max(PriceDaily.date)).where(PriceDaily.code.in_((code, f"{code}.KS")))).scalar()
        return str(d0) if d0 else None

def price_date_for_signals(country: str = "kr") -> Optional[str]:
    """
    개발룰:
      - 휴장일에는 마지막 거래일
      - KR은 개장 후에는 당일 가격 사용(일봉이 아니라 실시간은 별도 fetch 단계에서 처리)
    """
    # 현재는 '일봉 기준 신호'에 맞춰 최신 거래일만 반환 (실시간은 별도 단계에서 확장)
    return latest_trading_date_by_market("069500" if country == "kr" else "SPY")
