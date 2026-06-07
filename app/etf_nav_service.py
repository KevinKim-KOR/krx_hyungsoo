"""NAV / 괴리율 수집 서비스 (POC2 — 2026-06-01 / 2026-06-08).

Market Discovery Evidence Closeout 1차 — 지시문 §9 — per-ticker fetcher.

K6 방어 정책 (per-ticker):
- 1회 최대 10개 ETF (hard cap).
- cache-first: 동일 asof + ticker + source 가 store 에 있으면 외부 호출 X.
- ticker 당 0.5초 delay.
- 전체 time budget 30초.
- 실패 격리: ETF 단위 실패가 Market Discovery refresh 전체 실패로 전파 X.

2026-06-08 Naver Universe Integration (지시문 §5):
- refresh_nav_universe() 신규 — Naver `etfItemList.nhn` 1회 호출로 전체 ETF
  universe NAV / 시장가격 / 괴리율을 upsert.
- per-ticker 1,000회 호출 패턴이 아니므로 MAX cap 적용 X.
- TTL 30s + stale 재사용은 naver_etf_universe_fetcher 모듈 책임.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
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
from app.naver_etf_universe_fetcher import (
    NaverUniverseSnapshot,
    SOURCE_LABEL as NAVER_UNIVERSE_SOURCE,
    fetch_universe_snapshot,
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


# ─── Universe refresh (2026-06-08 — 지시문 §5) ────────────────────────


@dataclass
class NavUniverseRefreshSummary:
    """Naver universe refresh 결과 요약 (지시문 §5.5)."""

    source: str
    status: str  # ok / partial / unavailable
    asof: str
    fetched_at: Optional[str]
    started_at: str
    finished_at: str
    elapsed_seconds: float
    total_count: int
    success_count: int
    unavailable_count: int
    failed_count: int
    ignored_count: int
    cache_hit: bool
    stale_cache_used: bool
    message: Optional[str] = None
    upserted_count: int = 0
    sample_tickers: list[str] = field(default_factory=list)


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def refresh_nav_universe(
    *,
    asof: str,
    force: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    fetcher: Optional[Callable[..., NaverUniverseSnapshot]] = None,
    universe_filter: Optional[list[str]] = None,
) -> NavUniverseRefreshSummary:
    """Naver ETF universe 1회 호출로 전체 NAV / 시장가격 / 괴리율 수집·저장.

    지시문 §5 — per-ticker N회 호출 X. Naver `etfItemList.nhn` 1회 호출 + 일괄 upsert.

    Args:
        asof: 기준일 (YYYY-MM-DD). 일반적으로 직전 market refresh end_date 사용.
              (a) 결정에 따라 호출자(market_refresh_service) 가 결정 — 본 함수는 받는다.
        force: True 이면 TTL 무시 후 외부 호출 강제.
        db_path: etf_nav_daily SQLite 경로.
        fetcher: 테스트 주입용.
        universe_filter: 지정 시 해당 ticker 만 저장 (디버그 용도).

    Returns:
        NavUniverseRefreshSummary — 화면 / 운영 로그 / artifact 용.
    """
    started_at = _utcnow_iso()
    t0 = time.perf_counter()

    if not asof:
        finished_at = _utcnow_iso()
        return NavUniverseRefreshSummary(
            source=NAVER_UNIVERSE_SOURCE,
            status="unavailable",
            asof="",
            fetched_at=None,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(time.perf_counter() - t0, 3),
            total_count=0,
            success_count=0,
            unavailable_count=0,
            failed_count=0,
            ignored_count=0,
            cache_hit=False,
            stale_cache_used=False,
            message="missing_asof",
        )

    fetch_fn = fetcher or fetch_universe_snapshot
    snap: NaverUniverseSnapshot = fetch_fn(force=force)

    if snap.status == "unavailable" or not snap.items:
        finished_at = _utcnow_iso()
        return NavUniverseRefreshSummary(
            source=NAVER_UNIVERSE_SOURCE,
            status="unavailable",
            asof=asof,
            fetched_at=snap.fetched_at,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=round(time.perf_counter() - t0, 3),
            total_count=0,
            success_count=0,
            unavailable_count=0,
            failed_count=0,
            ignored_count=0,
            cache_hit=snap.cache_hit,
            stale_cache_used=snap.stale_cache_used,
            message=snap.message or "no items",
        )

    # universe_filter 적용 (디버그 용도).
    items_iter = snap.items.values()
    if universe_filter:
        keep = {t.upper() for t in universe_filter}
        items_iter = [it for it in items_iter if it.ticker in keep]
        ignored = len(snap.items) - len(items_iter)
    else:
        items_iter = list(items_iter)
        ignored = 0

    total = len(items_iter)
    success = 0
    unavailable = 0
    rows: list[NavDailyRow] = []
    sample: list[str] = []

    for it in items_iter:
        if (
            it.status != "ok"
            or it.nav is None
            or it.market_price is None
            or it.discount_rate_pct is None
        ):
            rows.append(
                NavDailyRow(
                    etf_ticker=it.ticker,
                    asof=asof,
                    nav=it.nav,
                    market_price=it.market_price,
                    discount_rate_pct=it.discount_rate_pct,
                    source=NAVER_UNIVERSE_SOURCE,
                    status="unavailable",
                    message=it.message or "nav or market_price missing",
                )
            )
            unavailable += 1
            continue

        # source 가 stale 인 경우 status=partial 표시 + 동일 row 저장 (asof 기준 최신값).
        row_status = "partial" if snap.stale_cache_used else "ok"
        row_message = "stale cache reused" if snap.stale_cache_used else None
        rows.append(
            NavDailyRow(
                etf_ticker=it.ticker,
                asof=asof,
                nav=it.nav,
                market_price=it.market_price,
                discount_rate_pct=it.discount_rate_pct,
                source=NAVER_UNIVERSE_SOURCE,
                status=row_status,
                message=row_message,
            )
        )
        success += 1
        if len(sample) < 5:
            sample.append(it.ticker)

    upserted = upsert_nav_rows(rows, db_path=db_path) if rows else 0

    finished_at = _utcnow_iso()
    overall = "ok"
    if snap.stale_cache_used:
        overall = "partial"
    if success == 0:
        overall = "unavailable"

    return NavUniverseRefreshSummary(
        source=NAVER_UNIVERSE_SOURCE,
        status=overall,
        asof=asof,
        fetched_at=snap.fetched_at,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=round(time.perf_counter() - t0, 3),
        total_count=total,
        success_count=success,
        unavailable_count=unavailable,
        failed_count=0,
        ignored_count=ignored,
        cache_hit=snap.cache_hit,
        stale_cache_used=snap.stale_cache_used,
        upserted_count=upserted,
        sample_tickers=sample,
        message=snap.message,
    )
