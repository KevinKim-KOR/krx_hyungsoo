"""GET /market/nav-discount/latest — read-only NAV / 괴리율 universe 조회 (2026-06-08).

지시문 §4.5 — read-only API. 저장된 etf_nav_daily 값만 읽고:
- Naver 직접 호출 X
- refresh 수행 X
- 매수/매도 판단 반환 X
- 새 source 추가 X

본 API 의 책임:
- etf_nav_store.fetch_all_latest_nav() 호출 → 모든 ETF 의 최신 asof NAV row.
- etf_master 의 name 으로 join (성능: 1회 dict build).
- summary count + items 리스트 + 응답 시점 asof / source 요약.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.etf_nav_fetcher import classify_discount_flag
from app.etf_nav_store import (
    DEFAULT_DB_PATH as NAV_DB_PATH,
    NavDailyRow,
    fetch_all_latest_nav,
)
from app.market_data_store import DEFAULT_DB_PATH as MARKET_DB_PATH

router = APIRouter()


# ─── Response models ───────────────────────────────────────────────────


class NavDiscountSummary(BaseModel):
    total_count: int
    ok_count: int
    unavailable_count: int
    failed_count: int


class NavDiscountItem(BaseModel):
    ticker: str
    name: Optional[str] = None
    nav: Optional[float] = None
    market_price: Optional[float] = None
    discount_rate_pct: Optional[float] = None
    flag: Optional[str] = None
    asof: str
    source: str
    status: str
    message: Optional[str] = None


class NavDiscountResponse(BaseModel):
    status: str  # ok / empty
    asof: Optional[str] = None
    source: Optional[str] = None
    summary: NavDiscountSummary
    items: list[NavDiscountItem] = []


# ─── helpers ───────────────────────────────────────────────────────────


def _build_name_map(db_path) -> dict:
    """etf_master 의 ticker→name 매핑.

    DB 가 없거나 etf_master 테이블이 없으면 빈 dict (정상 상태 — etf_nav_daily 만
    있고 universe master 가 아직 적재 안 된 경우 발생 가능).

    그 외 SQL 오류는 silent fallback 하지 않고 그대로 raise — broad fallback 은
    데이터 품질을 가린다 (검증자 B-1 FIX, 2026-06-08 라운드 2).
    """
    import sqlite3

    if not db_path.exists():
        return {}
    out: dict[str, str] = {}
    with sqlite3.connect(str(db_path)) as con:
        # etf_master 테이블 없으면 빈 dict (정상). DB 자체 손상은 raise.
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='etf_master'"
        )
        if cur.fetchone() is None:
            return {}
        cur = con.execute("SELECT ticker, name FROM etf_master")
        for ticker, name in cur:
            if name:
                out[str(ticker)] = str(name)
    return out


def _row_to_item(row: NavDailyRow, name: Optional[str]) -> NavDiscountItem:
    return NavDiscountItem(
        ticker=row.etf_ticker,
        name=name,
        nav=row.nav,
        market_price=row.market_price,
        discount_rate_pct=row.discount_rate_pct,
        flag=classify_discount_flag(row.discount_rate_pct),
        asof=row.asof,
        source=row.source,
        status=row.status,
        message=row.message,
    )


# ─── route ─────────────────────────────────────────────────────────────


@router.get("/market/nav-discount/latest", response_model=NavDiscountResponse)
def get_nav_discount_latest() -> NavDiscountResponse:
    """저장된 etf_nav_daily 최신 NAV/괴리율을 read-only 로 반환.

    - 외부 source 호출 X / refresh X.
    - 모든 ETF (asof DESC, created_at DESC) 기준 최신 row 1건씩.
    - 매수/매도 판단 X.
    """
    rows = fetch_all_latest_nav(db_path=NAV_DB_PATH)
    if not rows:
        return NavDiscountResponse(
            status="empty",
            summary=NavDiscountSummary(
                total_count=0,
                ok_count=0,
                unavailable_count=0,
                failed_count=0,
            ),
            items=[],
        )

    name_map = _build_name_map(MARKET_DB_PATH)
    items = [_row_to_item(r, name_map.get(r.etf_ticker)) for r in rows]

    ok_count = sum(1 for it in items if it.status == "ok")
    unavailable_count = sum(1 for it in items if it.status == "unavailable")
    failed_count = sum(
        1 for it in items if it.status not in ("ok", "partial", "unavailable")
    )

    # 응답 시점 asof / source 요약 — 가장 흔한 값 사용.
    asof_values = [it.asof for it in items if it.asof]
    response_asof = max(asof_values) if asof_values else None
    sources = {it.source for it in items if it.source}
    response_source = next(iter(sources)) if len(sources) == 1 else None

    return NavDiscountResponse(
        status="ok",
        asof=response_asof,
        source=response_source,
        summary=NavDiscountSummary(
            total_count=len(items),
            ok_count=ok_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        items=items,
    )
