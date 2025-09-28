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
        d1 = s.execute(
            select(func.max(PriceDaily.date)).where(PriceDaily.date < d0)
        ).scalar()
        return str(d1) if d1 else None

def load_universe_from_json(path: str = "etf.json") -> List[str]:
    """etf.json 기반 우선, 없으면 Security 테이블 모든 코드 사용."""
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
    # fallback: DB Security
    with SessionLocal() as s:
        rows = s.execute(select(Security.code)).all()
    return sorted({r[0] for r in rows})

def load_last_two_closes(codes: List[str], d0: str, d1: str) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """각 코드의 (d0 종가, d1 종가)"""
    out: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    if not codes:
        return out
    with SessionLocal() as s:
        rows0 = s.execute(
            select(PriceDaily.code, PriceDaily.close).where(PriceDaily.code.in_(codes)).where(PriceDaily.date == d0)
        ).all()
        rows1 = s.execute(
            select(PriceDaily.code, PriceDaily.close).where(PriceDaily.code.in_(codes)).where(PriceDaily.date == d1)
        ).all()
    px0 = {c: (float(x) if x is not None else None) for c, x in rows0}
    px1 = {c: (float(x) if x is not None else None) for c, x in rows1}
    for c in codes:
        out[c] = (px0.get(c), px1.get(c))
    return out

def load_names(codes: List[str]) -> Dict[str, str]:
    if not codes:
        return {}
    with SessionLocal() as s:
        rows = s.execute(select(Security.code, Security.name).where(Security.code.in_(codes))).all()
    return dict(rows or [])
