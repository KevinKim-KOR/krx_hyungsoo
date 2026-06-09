"""ML 최소 데이터 레인 — NAV join helper (POC2 2026-06-08 / FIX r2).

지시문 §6.4 — etf_nav_daily 에서 ticker × asof ≤ 기준일 인 가장 최근 row 1건
검색. 미래 NAV 가 join 되면 안 된다.

builder 와 분리해 단일 책임 + KS-10 near 진입 회피 (검증자 B-3 / B-6 FIX).

본 모듈은:
- `NavRow` dataclass (ticker 무관 최소 필드).
- `NavLookup` 클래스 — etf_nav_daily 를 1쿼리로 메모리에 인덱싱.

외부 source 호출 0건. 오직 SQLite read.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class NavRow:
    asof: str
    nav: Optional[float]
    market_price: Optional[float]
    discount_rate_pct: Optional[float]
    status: str


class NavLookup:
    """latest available ≤ asof NAV row 검색 (지시문 §6.4).

    1쿼리로 전체 etf_nav_daily 의 (ticker, asof, ...) 를 메모리에 적재 + ticker 별
    asof DESC 정렬. lookup 시 first asof ≤ 기준일 row 반환.

    DB 가 없거나 테이블이 없으면 빈 상태로 초기화 (정상 — 초기 적재 / 테스트).
    """

    def __init__(self, db_path: Path):
        self.by_ticker: dict[str, list[NavRow]] = {}
        if not db_path.exists():
            return
        with sqlite3.connect(str(db_path)) as con:
            cur = con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='etf_nav_daily'"
            )
            if cur.fetchone() is None:
                return
            cur = con.execute(
                "SELECT etf_ticker, asof, nav, market_price, "
                "discount_rate_pct, status "
                "FROM etf_nav_daily "
                "ORDER BY etf_ticker ASC, asof DESC, created_at DESC"
            )
            for tk, asof, nav, mp, dr, st in cur.fetchall():
                key = str(tk)
                self.by_ticker.setdefault(key, []).append(
                    NavRow(
                        asof=str(asof),
                        nav=(float(nav) if nav is not None else None),
                        market_price=(float(mp) if mp is not None else None),
                        discount_rate_pct=(float(dr) if dr is not None else None),
                        status=str(st),
                    )
                )

    def lookup(self, ticker: str, asof: str) -> Optional[NavRow]:
        rows = self.by_ticker.get(ticker)
        if not rows:
            return None
        # 이미 asof DESC 정렬 — 첫 row.asof ≤ asof.
        for r in rows:
            if r.asof <= asof:
                return r
        return None
