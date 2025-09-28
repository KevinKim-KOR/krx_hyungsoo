# signals/queries.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Optional, Tuple
import json, os
from sqlalchemy import select, func
from db import SessionLocal, PriceDaily, Security

def latest_trading_date_kr() -> Optional[str]:
    with SessionLocal() as s:
        d0 = s.execute(
            select(func.max(PriceDaily.date)).where(PriceDaily.code.in_(("069500", "069500.KS")))
        ).scalar()
        return str(d0) if d0 else None

def previous_trading_date(d0: str) -> Optional[str]:
    with SessionLocal() as s:
        d1 = s.execute(select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)).scalar()
        return str(d1) if d1 else None

def recent_trading_dates_kr(limit: int = 200) -> List[str]:
    with SessionLocal() as s:
        rows = s.execute(
            select(PriceDaily.date)
            .where(PriceDaily.code.in_(("069500", "069500.KS")))
            .order_by(PriceDaily.date.desc())
            .limit(limit)
        ).all()
    dates = [str(r[0]) for r in rows]
    dates.reverse()
    return dates

def load_universe_from_json(path: str = "etf.json") -> List[str]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
            codes = []
            for it in items:
                if isinstance(it, dict):
                    if not it.get("is_active", True):
                        continue
                    code = str(it.get("code") or it.get("ticker") or "").strip()
                    if code:
                        codes.append(code)
            return sorted(set(codes))
        except Exception:
            pass
    with SessionLocal() as s:
        rows = s.execute(select(Security.code)).all()
    return sorted({r[0] for r in rows})

def load_names(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    with SessionLocal() as s:
        rows = s.execute(select(Security.code, Security.name).where(Security.code.in_(codes))).all()
    return dict(rows or [])

def load_prices_for_dates(codes: List[str], dates: List[str]) -> Dict[str, Dict[str, float]]:
    if not codes or not dates:
        return {}
    with SessionLocal() as s:
        rows = s.execute(
            select(PriceDaily.code, PriceDaily.date, PriceDaily.close)
            .where(PriceDaily.code.in_(codes))
            .where(PriceDaily.date.in_(dates))
        ).all()
    out: Dict[str, Dict[str, float]] = {}
    for code, d, px in rows:
        if px is None:
            continue
        out.setdefault(code, {})[str(d)] = float(px)
    return out
