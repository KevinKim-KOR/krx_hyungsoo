"""NAV / 괴리율 수집 서비스 (POC2 — 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §9.

K6 방어 정책:
- 1회 최대 10개 ETF (hard cap).
- cache-first: 동일 asof + ticker + source 가 store 에 있으면 외부 호출 X.
- ticker 당 0.5초 delay.
- 전체 time budget 30초.
- 실패 격리: ETF 단위 실패가 Market Discovery refresh 전체 실패로 전파 X.

본 STEP 의 default fetcher 는 unavailable_nav_fetcher — 외부 호출 0건.
별도 진단 STEP 에서 실 fetcher 채택 시 인터페이스만 교체.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.etf_nav_fetcher import (
    NavFetcher,
    NavFetchResult,
    classify_discount_flag,
    compute_discount_rate_pct,
    default_nav_fetcher,
)
from app.etf_nav_store import (
    DEFAULT_DB_PATH,
    NavDailyRow,
    fetch_nav_rows,
    upsert_nav_rows,
)

MAX_TICKERS_PER_REQUEST = 10
PER_TICKER_DELAY_SECONDS = 0.5
TIME_BUDGET_SECONDS = 30.0


@dataclass
class NavItemResult:
    ticker: str
    status: str  # ok / unavailable / cached / skipped_timeout
    source: str
    asof: Optional[str]
    nav: Optional[float]
    market_price: Optional[float]
    discount_rate_pct: Optional[float]
    flag: Optional[str]
    from_cache: bool
    message: Optional[str] = None


@dataclass
class NavRefreshResult:
    status: str  # ok / partial / rejected
    reason: Optional[str]
    asof: Optional[str]
    requested_count: int
    success_count: int
    fail_count: int
    cached_count: int
    fetched_count: int
    skipped_count: int
    items: list[NavItemResult]


def _row_to_item(row: NavDailyRow, from_cache: bool) -> NavItemResult:
    flag = classify_discount_flag(row.discount_rate_pct)
    return NavItemResult(
        ticker=row.etf_ticker,
        status=row.status,
        source=row.source,
        asof=row.asof,
        nav=row.nav,
        market_price=row.market_price,
        discount_rate_pct=row.discount_rate_pct,
        flag=flag,
        from_cache=from_cache,
        message=row.message,
    )


def _result_to_row(
    *,
    ticker: str,
    asof: str,
    result: NavFetchResult,
) -> NavDailyRow:
    discount = result.discount_rate_pct
    if discount is None:
        discount = compute_discount_rate_pct(result.nav, result.market_price)
    return NavDailyRow(
        etf_ticker=ticker,
        asof=result.asof or asof,
        nav=result.nav,
        market_price=result.market_price,
        discount_rate_pct=discount,
        source=result.source,
        status=result.status,
        message=result.message,
    )


def refresh_nav(
    *,
    asof: str,
    tickers: list[str],
    fetcher: Optional[NavFetcher] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
    db_path: Path = DEFAULT_DB_PATH,
) -> NavRefreshResult:
    """후보 ETF 의 NAV / 괴리율 수집 (지시문 §9).

    Market Discovery refresh 후속 단계로 호출됨.
    cache check → external fetch (delay + budget) → upsert.
    실패 시에도 unavailable row 를 store 에 기록.
    """
    if not asof:
        return NavRefreshResult(
            status="rejected",
            reason="missing_asof",
            asof=None,
            requested_count=0,
            success_count=0,
            fail_count=0,
            cached_count=0,
            fetched_count=0,
            skipped_count=0,
            items=[],
        )
    if not tickers:
        return NavRefreshResult(
            status="ok",
            reason=None,
            asof=asof,
            requested_count=0,
            success_count=0,
            fail_count=0,
            cached_count=0,
            fetched_count=0,
            skipped_count=0,
            items=[],
        )
    if len(tickers) > MAX_TICKERS_PER_REQUEST:
        return NavRefreshResult(
            status="rejected",
            reason="too_many_tickers",
            asof=asof,
            requested_count=len(tickers),
            success_count=0,
            fail_count=0,
            cached_count=0,
            fetched_count=0,
            skipped_count=0,
            items=[],
        )

    fetcher_fn: NavFetcher = fetcher or default_nav_fetcher()
    items: list[NavItemResult] = []
    success_count = 0
    fail_count = 0
    cached_count = 0
    fetched_count = 0
    skipped_count = 0
    rows_to_upsert: list[NavDailyRow] = []
    deadline = now_fn() + TIME_BUDGET_SECONDS

    for index, ticker in enumerate(tickers):
        # cache check — 같은 asof 의 (어떤 source 라도) 이미 있으면 재사용.
        cached_rows = fetch_nav_rows(etf_ticker=ticker, asof=asof, db_path=db_path)
        usable = [r for r in cached_rows if r.status in ("ok", "partial")]
        if usable:
            items.append(_row_to_item(usable[0], from_cache=True))
            if usable[0].status == "ok":
                success_count += 1
            cached_count += 1
            continue

        if now_fn() > deadline:
            items.append(
                NavItemResult(
                    ticker=ticker,
                    status="skipped_timeout",
                    source="unavailable",
                    asof=asof,
                    nav=None,
                    market_price=None,
                    discount_rate_pct=None,
                    flag=None,
                    from_cache=False,
                    message="time budget exceeded",
                )
            )
            skipped_count += 1
            continue

        if index > 0:
            sleep_fn(PER_TICKER_DELAY_SECONDS)

        try:
            result = fetcher_fn(ticker)
        except Exception as e:  # noqa: BLE001
            result = NavFetchResult(
                status="unavailable",
                source="unavailable",
                message=f"fetcher exception: {type(e).__name__}: {e}",
            )

        row = _result_to_row(ticker=ticker, asof=asof, result=result)
        rows_to_upsert.append(row)
        items.append(_row_to_item(row, from_cache=False))
        fetched_count += 1
        if row.status == "ok":
            success_count += 1
        else:
            fail_count += 1

    if rows_to_upsert:
        upsert_nav_rows(rows_to_upsert, db_path=db_path)

    overall = "ok" if fail_count == 0 and skipped_count == 0 else "partial"
    return NavRefreshResult(
        status=overall,
        reason=None,
        asof=asof,
        requested_count=len(tickers),
        success_count=success_count,
        fail_count=fail_count,
        cached_count=cached_count,
        fetched_count=fetched_count,
        skipped_count=skipped_count,
        items=items,
    )
