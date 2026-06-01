"""ETF 구성종목 수집 흐름 서비스 (POC2 — 2026-05-27).

POST /market/constituents/refresh 의 백엔드 service. 외부 fetch 의존성을
강하게 가두기 위한 K6 방어 정책 (지시문 §4):

- 1회 최대 10개 ticker (`MAX_TICKERS_PER_REQUEST`).
- 캐시 우선: (etf_ticker, asof, source) 키로 이미 있으면 외부 호출 안 함.
- `force=true` 인 경우에만 캐시를 무시하고 재수집.
- 외부 fetch 사이 ticker 당 0.5초 delay.
- 전체 refresh time budget 30초. 초과 시 남은 ETF 는 skipped_timeout.
- 부분 실패 격리: ETF 단위 실패가 전체 실패로 번지지 않는다.
- source 불명 데이터는 ok 처리하지 않는다 (fetcher 가 source 명시).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

from app.etf_constituents_fetcher import (
    FetcherFn,
    FetchResult,
    NAVER_STOCK_SOURCE,
    default_fetcher,
)
from app.etf_constituents_store import (
    ConstituentRow,
    DEFAULT_DB_PATH,
    fetch_constituents,
    log_constituent_refresh,
    upsert_constituents,
)

MAX_TICKERS_PER_REQUEST = 10
DEFAULT_TOP_K = 10
MAX_TOP_K = 10
PER_TICKER_DELAY_SECONDS = 0.5
TIME_BUDGET_SECONDS = 30.0


@dataclass
class RefreshItemResult:
    ticker: str
    status: str  # "ok" / "unavailable" / "skipped_timeout" / "cached"
    source: Optional[str]
    constituent_count: int
    from_cache: bool
    message: Optional[str] = None


@dataclass
class RefreshResult:
    status: str  # "ok" / "partial" / "rejected"
    reason: Optional[str]  # rejected 시 사유
    message: Optional[str]
    asof: Optional[str]
    requested_count: int
    success_count: int
    fail_count: int
    cached_count: int
    fetched_count: int
    skipped_count: int
    source: Optional[str]
    items: list[RefreshItemResult]


def _cap_top_k(top_k: int) -> int:
    if top_k is None or top_k <= 0:
        return DEFAULT_TOP_K
    return min(int(top_k), MAX_TOP_K)


def refresh_constituents(
    *,
    asof: str,
    tickers: list[str],
    top_k: int = DEFAULT_TOP_K,
    force: bool = False,
    fetcher: Optional[FetcherFn] = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
    db_path=DEFAULT_DB_PATH,
) -> RefreshResult:
    """후보 ETF 구성종목 수집. service-level 흐름 제어.

    cache check → external fetch (delay + budget) → upsert → log.

    rejected 시 (10개 초과) status='rejected' + items 비어있음.
    """
    if not asof:
        return RefreshResult(
            status="rejected",
            reason="missing_asof",
            message="asof is required.",
            asof=None,
            requested_count=0,
            success_count=0,
            fail_count=0,
            cached_count=0,
            fetched_count=0,
            skipped_count=0,
            source=None,
            items=[],
        )
    if len(tickers) > MAX_TICKERS_PER_REQUEST:
        return RefreshResult(
            status="rejected",
            reason="too_many_tickers",
            message=(
                "ETF 구성종목 수집은 1회 최대 "
                f"{MAX_TICKERS_PER_REQUEST}개 후보만 허용합니다."
            ),
            asof=asof,
            requested_count=len(tickers),
            success_count=0,
            fail_count=0,
            cached_count=0,
            fetched_count=0,
            skipped_count=0,
            source=None,
            items=[],
        )

    fetch = fetcher or default_fetcher()
    capped_top_k = _cap_top_k(top_k)
    t_start = now_fn()
    items: list[RefreshItemResult] = []
    success_count = 0
    fail_count = 0
    cached_count = 0
    fetched_count = 0
    skipped_count = 0
    source_seen: Optional[str] = None
    is_first_external = True

    # 2026-05-31 — Naver Stock ETFComponent 1차 채택 (직전 PYKRX_SOURCE 교체).
    # cache key 일치성 (지시문 §4.3 ticker+asof+source) — 본 service 는 단일
    # fetcher 기준으로 expected_source 를 NAVER_STOCK_SOURCE 로 명시 매칭.
    expected_source = NAVER_STOCK_SOURCE

    for tk in tickers:
        if not force:
            existing = fetch_constituents(
                etf_ticker=tk,
                asof=asof,
                source=expected_source,
                db_path=db_path,
            )
            if existing:
                items.append(
                    RefreshItemResult(
                        ticker=tk,
                        status="ok",
                        source=expected_source,
                        constituent_count=len(existing),
                        from_cache=True,
                    )
                )
                success_count += 1
                cached_count += 1
                if source_seen is None:
                    source_seen = expected_source
                continue

        # external fetch — 시간 예산 체크.
        elapsed = now_fn() - t_start
        if elapsed >= TIME_BUDGET_SECONDS:
            items.append(
                RefreshItemResult(
                    ticker=tk,
                    status="skipped_timeout",
                    source=None,
                    constituent_count=0,
                    from_cache=False,
                    message="constituent refresh time budget exceeded",
                )
            )
            log_constituent_refresh(
                etf_ticker=tk,
                asof=asof,
                status="skipped_timeout",
                source=None,
                message="time_budget_exceeded",
                db_path=db_path,
            )
            skipped_count += 1
            continue

        # ticker 간 delay (첫 외부 호출 제외).
        if not is_first_external:
            sleep_fn(PER_TICKER_DELAY_SECONDS)
        is_first_external = False

        # fetch.
        try:
            result: FetchResult = fetch(tk, asof, capped_top_k)
        except Exception as e:  # noqa: BLE001 — service 안에서 흡수.
            result = FetchResult(
                status="unavailable",
                source="unknown",
                constituents=[],
                message=f"fetch_unexpected: {type(e).__name__}: {e}",
            )

        if result.status != "ok" or not result.constituents:
            items.append(
                RefreshItemResult(
                    ticker=tk,
                    status="unavailable",
                    source=result.source,
                    constituent_count=0,
                    from_cache=False,
                    message=result.message or "constituent source unavailable",
                )
            )
            log_constituent_refresh(
                etf_ticker=tk,
                asof=asof,
                status="unavailable",
                source=result.source,
                message=result.message,
                db_path=db_path,
            )
            fail_count += 1
            fetched_count += 1
            continue

        # source 불명 ('unknown' 또는 빈 문자열) 은 ok 처리 금지 (지시문 §4.6).
        if (
            not result.source
            or result.source.strip() == ""
            or result.source == "unknown"
        ):
            items.append(
                RefreshItemResult(
                    ticker=tk,
                    status="unavailable",
                    source=result.source,
                    constituent_count=0,
                    from_cache=False,
                    message="source unclear — not stored",
                )
            )
            log_constituent_refresh(
                etf_ticker=tk,
                asof=asof,
                status="unavailable",
                source=result.source,
                message="source_unclear",
                db_path=db_path,
            )
            fail_count += 1
            fetched_count += 1
            continue

        # 2026-05-31 — Naver 의 referenceDate 가 우선. 입력 asof 가 단순
        # "오늘 기준 가져와줘" 의미였다면 응답의 referenceDate 를 신뢰한다
        # (지시문 §6.1 — referenceDate → asof).
        save_asof = result.effective_asof or asof

        # constituent_key 빌드 (지시문 §6.3).
        from app.etf_constituents_fetcher import _build_constituent_key

        rows = [
            ConstituentRow(
                etf_ticker=tk,
                asof=save_asof,
                source=result.source,
                rank=c.rank,
                constituent_ticker=c.constituent_ticker,
                constituent_name=c.constituent_name,
                weight_pct=c.weight_pct,
                etf_name=result.etf_name,
                constituent_key=_build_constituent_key(
                    c.constituent_ticker,
                    c.constituent_reuters_code,
                    c.constituent_isin,
                    c.constituent_name,
                ),
                constituent_isin=c.constituent_isin,
                constituent_reuters_code=c.constituent_reuters_code,
                market_type=c.market_type,
            )
            for c in result.constituents
        ]
        upsert_constituents(rows, db_path=db_path)
        log_constituent_refresh(
            etf_ticker=tk,
            asof=save_asof,
            status="ok",
            source=result.source,
            message=None,
            db_path=db_path,
        )
        items.append(
            RefreshItemResult(
                ticker=tk,
                status="ok",
                source=result.source,
                constituent_count=len(rows),
                from_cache=False,
            )
        )
        success_count += 1
        fetched_count += 1
        if source_seen is None:
            source_seen = result.source

    overall = "ok" if fail_count == 0 and skipped_count == 0 else "partial"
    if success_count == 0 and (fail_count + skipped_count) > 0:
        overall = "partial"  # 전체 실패라도 partial 로 노출 (지시문 §4.6 정신).
    return RefreshResult(
        status=overall,
        reason=None,
        message=None,
        asof=asof,
        requested_count=len(tickers),
        success_count=success_count,
        fail_count=fail_count,
        cached_count=cached_count,
        fetched_count=fetched_count,
        skipped_count=skipped_count,
        source=source_seen,
        items=items,
    )
