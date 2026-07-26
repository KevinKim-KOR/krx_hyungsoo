"""SQLite 기반 1개월 수익률 basis fetcher (OCI Operational Market Data Refresh v1).

`app.price_history_pykrx.fetch_one_month_basis` 와 **동일 계약** (같은 시그니처 ·
같은 PriceHistoryResult 반환) 을 SQLite `etf_daily_price` 시계열로 구현한다.

목적: Universe Builder (score_candidates) 의 fetcher DI 에 그대로 꽂아, OCI 운영
경로에서 pykrx 외부 호출 없이 저장된 일별 시세로 base/latest close 를 계산한다.

- pykrx 기본 경로는 PC·진단용으로 보존 (본 모듈은 그 경로를 대체하지 않고 병존).
- base_target 선정 알고리즘은 pykrx 버전과 동일 (asof - lookback_days 이후 첫 거래일).
- 신규 factor·threshold·산식 없음. 데이터 소스만 pykrx → SQLite.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Callable

from app.market_data_store import DEFAULT_DB_PATH, fetch_price_history
from app.price_history_pykrx import (
    DEFAULT_FETCH_WINDOW_DAYS,
    DEFAULT_LOOKBACK_DAYS,
    PriceHistoryBasis,
    PriceHistoryFailure,
    PriceHistoryResult,
    _parse_asof,
)


def make_sqlite_price_fetcher(
    db_path: Path = DEFAULT_DB_PATH,
    fetch_history: Callable[..., list] = None,
) -> Callable[[str, str], PriceHistoryResult]:
    """score_candidates 에 주입할 fetcher 를 만든다.

    반환 fetcher 시그니처: (ticker, asof) -> PriceHistoryResult.
    (score_candidates._default_fetcher 와 동일 — fetch_window/lookback 은 여기서
    기본값을 쓴다. builder 가 fetcher 를 (ticker, asof) 로만 호출하기 때문.)
    """
    _fetch = fetch_history or fetch_price_history

    def _sqlite_fetcher(ticker: str, asof: str) -> PriceHistoryResult:
        return fetch_one_month_basis_sqlite(
            ticker=ticker,
            asof=asof,
            db_path=db_path,
            fetch_history=_fetch,
        )

    return _sqlite_fetcher


def fetch_one_month_basis_sqlite(
    ticker: str,
    asof: str,
    *,
    fetch_window_days: int = DEFAULT_FETCH_WINDOW_DAYS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    db_path: Path = DEFAULT_DB_PATH,
    fetch_history: Callable[..., list] = None,
) -> PriceHistoryResult:
    """asof 기준 1개월 수익률 basis 를 SQLite etf_daily_price 로 계산.

    pykrx 버전(fetch_one_month_basis)과 동일 절차:
    1. asof 검증 · fromdate = asof - fetch_window_days.
    2. SQLite (date, close) 시계열 조회 (date ASC) · fromdate~asof 범위 필터.
    3. 비어 있으면 no_data.
    4. latest = 마지막 거래일 종가.
    5. base_target = asof - lookback_days · 그 날짜 또는 이후 첫 거래일을 base.
    6. base 없음/단일 거래일 → no_base_close.
    """
    _fetch = fetch_history or fetch_price_history
    try:
        asof_date = _parse_asof(asof)
    except (TypeError, ValueError) as e:
        return PriceHistoryFailure(reason="asof_invalid", detail=str(e))

    fromdate = asof_date - timedelta(days=fetch_window_days)

    try:
        series = _fetch(ticker, db_path=db_path)
    except Exception as e:  # noqa: BLE001 — 저장소 접근 예외 격리
        return PriceHistoryFailure(reason="fetch_error", detail=f"sqlite: {e}")

    # (date_str, close) · date ASC. fromdate ~ asof 범위만.
    rows = [
        (d, c)
        for (d, c) in series
        if fromdate.isoformat() <= d <= asof_date.isoformat() and c > 0
    ]
    if not rows:
        return PriceHistoryFailure(reason="no_data")

    latest_date_str, latest_close = rows[-1]
    if not (latest_close > 0):
        return PriceHistoryFailure(reason="no_data", detail="latest_close <= 0")

    base_target = (asof_date - timedelta(days=lookback_days)).isoformat()
    base = None
    for d, c in rows:
        if d >= base_target:
            base = (d, c)
            break
    if base is None or base[0] == latest_date_str:
        return PriceHistoryFailure(
            reason="no_base_close",
            detail=f"no trading day on or after {base_target}",
        )

    base_date_str, base_close = base
    if not (base_close > 0):
        return PriceHistoryFailure(reason="no_base_close", detail="base_close <= 0")

    return PriceHistoryBasis(
        base_date=base_date_str,
        base_close=base_close,
        latest_date=latest_date_str,
        latest_close=latest_close,
    )
