# signals/queries.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Optional, Tuple
import json, os
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily, Security

def latest_trading_date_kr() -> Optional[str]:
    with SessionLocal() as s:
        d0 = s.execute(select(func.max(PriceDaily.date)).where(
            PriceDaily.code.in_(("069500","069500.KS")))).scalar()
        return str(d0) if d0 else None

def recent_trading_dates_kr(limit: int = 260) -> List[str]:
    with SessionLocal() as s:
        rows = s.execute(select(PriceDaily.date)
            .where(PriceDaily.code.in_(("069500","069500.KS")))
            .order_by(PriceDaily.date.desc()).limit(limit)).all()
    dates = [str(r[0]) for r in rows][::-1]
    return dates

def load_universe_from_json(path: str = "etf.json") -> List[str]:
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                items = json.load(f)
            codes=[]
            for it in items:
                if isinstance(it,dict):
                    if not it.get("is_active",True): continue
                    c = str(it.get("code") or it.get("ticker") or "").strip()
                    if c: codes.append(c)
            return sorted(set(codes))
        except Exception:
            pass
    with SessionLocal() as s:
        rows = s.execute(select(Security.code)).all()
    return sorted({r[0] for r in rows})

def load_names(codes: List[str]) -> Dict[str,str]:
    if not codes: return {}
    with SessionLocal() as s:
        rows = s.execute(select(Security.code, Security.name)
            .where(Security.code.in_(codes))).all()
    return dict(rows or [])

def load_prices_for_dates(codes: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
    if not codes or not dates: return {}
    with SessionLocal() as s:
        rows = s.execute(select(PriceDaily.code, PriceDaily.date, PriceDaily.close)
            .where(PriceDaily.code.in_(codes))
            .where(PriceDaily.date.in_(dates))).all()
    out: Dict[str, Dict[str, float]] = {}
    for c, d, px in rows:
        if px is None: continue
        out.setdefault(c,{})[str(d)] = float(px)
    return out

def load_turnover_for_dates(codes: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
    """
    거래대금(원) 추정: 우선순위
      1) PriceDaily.value(거래대금) 칼럼이 있으면 그대로
      2) 있지 않다면 close * volume이 가능하면 계산
      3) 둘 다 불가면 해당 날짜는 결측
    """
    if not codes or not dates: return {}
    with SessionLocal() as s:
        # 칼럼 존재 유무를 런타임에서 안전하게 접근
        has_value  = hasattr(PriceDaily, "value")
        has_volume = hasattr(PriceDaily, "volume")
        cols = [PriceDaily.code, PriceDaily.date]
        if has_value:  cols.append(getattr(PriceDaily,"value"))
        if has_volume: cols.append(getattr(PriceDaily,"volume"))
        cols.append(PriceDaily.close)
        rows = s.execute(select(*cols)
                .where(PriceDaily.code.in_(codes))
                .where(PriceDaily.date.in_(dates))).all()
    out: Dict[str, Dict[str, float]] = {}
    for row in rows:
        code, d = row[0], str(row[1])
        val = None
        if has_value and row[2] is not None:
            val = float(row[2])
        else:
            # close * volume 조합 시도
            vol = None; close = None
            if has_value and has_volume:
                vol, close = row[3], row[4]
            elif has_volume:
                vol, close = row[2], row[3]
            if vol is not None and close is not None:
                try: val = float(vol) * float(close)
                except: pass
        if val is not None:
            out.setdefault(code,{})[d] = val
    return out
