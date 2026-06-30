"""Market timeseries ingestion service (2026-06-30 시장 시계열 SQLite 기반 보강).

KRX 데이터마켓 공식 자료를 PC 에서 CLI 로 import 한 결과를 받아
SQLite (`etf_daily_price` / `market_benchmark_daily_price` / 상태 테이블) 에
영속화한다. 본 모듈 자체는 외부 네트워크·자격증명을 사용하지 않는다.

호출자 (CLI) 가 다음을 책임진다:
- KRX 데이터마켓 ZIP/CSV 다운로드
- 컬럼 매핑 (ticker / date / close / price_basis)
- 본 모듈 함수에 정규화된 시계열 전달

결측 분류 규칙 (지시문 §7):
- 상장 전 날짜             → 정상 비존재 (count 제외)
- 소스 제공 시작일 이전    → source_missing 범위 (count 제외)
- 확인 범위 이후 KODEX200 거래일에 없는 가격 → post_listing_missing (count)
- 중복 날짜·충돌 가격      → 자동 선택 X, status=missing_confirm
- 0 이하·NaN              → 적재 제외, status=missing_confirm
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from app.market_benchmark_store import (
    fetch_existing_benchmark_close_map,
    upsert_benchmark_prices,
)
from app.market_data_store import (
    DEFAULT_DB_PATH,
    EtfDailyPriceRow,
    fetch_existing_close_map,
    upsert_daily_prices,
)
from app.market_timeseries_ingestion_store import (
    STATUS_LISTING_UNKNOWN,
    STATUS_MISSING_CONFIRM,
    STATUS_NORMAL,
    STATUS_PARTIAL,
    STATUS_SOURCE_MISSING,
    TimeseriesIngestionStateRow,
    upsert_state,
)

BENCHMARK_KODEX200_TICKER = "069500"


@dataclass
class IngestionInput:
    """단일 종목 import 입력 (정규화 완료된 상태)."""

    ticker: str
    rows: list[tuple[str, Optional[float]]]  # (date_iso, close)
    confirmed_listing_date: Optional[str] = None
    source: Optional[str] = None
    price_basis: Optional[str] = None
    # 가격 시계열이 비어 있고 그 사유가 "KRX 자료에 해당 ticker 없음" 이면
    # source_missing 으로 기록. 호출자가 명시.
    source_missing: bool = False
    # 행 자체는 있으나 일부 날짜에 동일 ticker 가 충돌 (가격 불일치 등) 이면 True.
    has_conflict: bool = False


@dataclass
class IngestionResult:
    ticker: str
    status: str
    rows_written: int
    observed_trading_day_count: int
    post_listing_missing_count: int
    series_start_date: Optional[str]
    series_end_date: Optional[str]
    error_summary: Optional[str] = None


def _classify_rows(
    rows: list[tuple[str, Optional[float]]],
) -> tuple[list[tuple[str, float]], int, bool]:
    """가격 행을 (적재용 valid rows, 결측 후보 수, has_bad_price) 로 분류.

    - close 가 None / NaN / 0 이하: 적재 제외, missing 후보 X (post-listing missing
      판정은 호출 측 KODEX200 달력 기반으로 별도 계산).
    - 중복 (date, close 차이) 은 호출 측에서 detect (`has_conflict`).
    """
    valid: list[tuple[str, float]] = []
    bad = 0
    for dt, close in rows:
        if close is None:
            bad += 1
            continue
        try:
            f = float(close)
        except (TypeError, ValueError):
            bad += 1
            continue
        if f != f:  # NaN
            bad += 1
            continue
        if f <= 0:
            bad += 1
            continue
        valid.append((dt, f))
    return valid, bad, bad > 0


def _detect_duplicate_conflict(rows: list[tuple[str, float]]) -> bool:
    """동일 date 가 서로 다른 close 로 들어오면 True."""
    by_date: dict[str, float] = {}
    for dt, close in rows:
        if dt in by_date and by_date[dt] != close:
            return True
        by_date[dt] = close
    return False


_PRICE_EQ_EPS = 1e-9


def _split_by_existing_conflict(
    rows: list[tuple[str, float]],
    existing: dict[str, Optional[float]],
) -> tuple[list[tuple[str, float]], list[str]]:
    """기존 SQLite 가격과 비교해 (적재 가능 rows, 충돌 dates) 로 분리.

    동일 date 가 기존에 있고 close 값이 다르면 충돌 — 호출자가 자동 덮어쓰기를
    하지 않도록 적재 대상에서 제외한다 (지시문 §6.1).

    - 기존 close 가 None / 0 이하 → 충돌로 보지 않음 (보강 적재 허용).
    - 기존 close 와 동일 (eps) → 적재 OK (ON CONFLICT 가 흡수해도 값 변화 없음).
    - 기존 close 와 다른 값 → conflict 로 분류, 적재 X.
    """
    ok: list[tuple[str, float]] = []
    conflict_dates: list[str] = []
    for dt, close in rows:
        prior = existing.get(dt)
        if prior is None or prior <= 0:
            ok.append((dt, close))
            continue
        if abs(prior - close) <= _PRICE_EQ_EPS:
            ok.append((dt, close))
            continue
        conflict_dates.append(dt)
    return ok, conflict_dates


def _count_post_listing_missing(
    *,
    valid_dates: set[str],
    benchmark_calendar: set[str],
    series_start: Optional[str],
    series_end: Optional[str],
) -> int:
    """확인된 시계열 범위 [series_start, series_end] 안의 벤치마크 거래일 중
    valid_dates 에 없는 날짜 수.

    벤치마크 달력이 비어 있으면 0 반환 (KODEX200 적재 전이거나 벤치마크 모드).
    """
    if not benchmark_calendar:
        return 0
    if not series_start or not series_end:
        return 0
    missing = 0
    for dt in benchmark_calendar:
        if dt < series_start or dt > series_end:
            continue
        if dt not in valid_dates:
            missing += 1
    return missing


def ingest_etf_timeseries(
    payload: IngestionInput,
    *,
    benchmark_calendar: Optional[Iterable[str]] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> IngestionResult:
    """ETF 단일 종목 시계열을 etf_daily_price 에 적재 + 상태 테이블 갱신.

    benchmark_calendar: KODEX200 (또는 동등 기준) 의 거래일 집합. 미제공 시
    post_listing_missing_count=0 으로 처리.
    """
    if payload.source_missing:
        upsert_state(
            TimeseriesIngestionStateRow(
                ticker=payload.ticker,
                ingestion_status=STATUS_SOURCE_MISSING,
                confirmed_listing_date=payload.confirmed_listing_date,
                source=payload.source,
                price_basis=payload.price_basis,
                error_summary="krx_source_unavailable",
            ),
            db_path=db_path,
        )
        return IngestionResult(
            ticker=payload.ticker,
            status=STATUS_SOURCE_MISSING,
            rows_written=0,
            observed_trading_day_count=0,
            post_listing_missing_count=0,
            series_start_date=None,
            series_end_date=None,
            error_summary="krx_source_unavailable",
        )

    valid, bad, has_bad = _classify_rows(payload.rows)
    has_conflict = payload.has_conflict or _detect_duplicate_conflict(valid)

    if not valid:
        # 가격 행이 없거나 모두 bad — 상장일 추정도 불가.
        upsert_state(
            TimeseriesIngestionStateRow(
                ticker=payload.ticker,
                ingestion_status=STATUS_LISTING_UNKNOWN,
                confirmed_listing_date=payload.confirmed_listing_date,
                source=payload.source,
                price_basis=payload.price_basis,
                error_summary=(
                    "no_valid_rows_with_bad_prices" if has_bad else "no_rows"
                ),
            ),
            db_path=db_path,
        )
        return IngestionResult(
            ticker=payload.ticker,
            status=STATUS_LISTING_UNKNOWN,
            rows_written=0,
            observed_trading_day_count=0,
            post_listing_missing_count=0,
            series_start_date=None,
            series_end_date=None,
            error_summary=("no_valid_rows_with_bad_prices" if has_bad else "no_rows"),
        )

    # 기존 SQLite 가격과 비교 — 충돌하는 date 는 적재 대상에서 제외
    # (지시문 §6.1: "임의로 덮어쓰지 않는다, 확인 필요 상태").
    existing = fetch_existing_close_map(payload.ticker, db_path=db_path)
    appendable, existing_conflict_dates = _split_by_existing_conflict(valid, existing)
    has_existing_conflict = len(existing_conflict_dates) > 0

    if not appendable:
        # 모든 row 가 기존과 충돌 — 적재 0건 + missing_confirm.
        upsert_state(
            TimeseriesIngestionStateRow(
                ticker=payload.ticker,
                ingestion_status=STATUS_MISSING_CONFIRM,
                confirmed_listing_date=payload.confirmed_listing_date,
                source=payload.source,
                price_basis=payload.price_basis,
                error_summary="all_rows_conflict_with_existing",
            ),
            db_path=db_path,
        )
        return IngestionResult(
            ticker=payload.ticker,
            status=STATUS_MISSING_CONFIRM,
            rows_written=0,
            observed_trading_day_count=0,
            post_listing_missing_count=0,
            series_start_date=None,
            series_end_date=None,
            error_summary="all_rows_conflict_with_existing",
        )

    appendable_sorted = sorted(appendable, key=lambda x: x[0])
    series_start = appendable_sorted[0][0]
    series_end = appendable_sorted[-1][0]
    valid_dates = {dt for dt, _ in appendable_sorted}

    cal_set: set[str] = set(benchmark_calendar) if benchmark_calendar else set()
    benchmark_calendar_available = len(cal_set) > 0
    post_missing = _count_post_listing_missing(
        valid_dates=valid_dates,
        benchmark_calendar=cal_set,
        series_start=series_start,
        series_end=series_end,
    )

    # 적재 — 충돌 제외된 row 만. (ticker, date) PK ON CONFLICT 는 동일 값에만 발생.
    rows_for_db = [
        EtfDailyPriceRow(
            ticker=payload.ticker,
            date=dt,
            open=None,
            high=None,
            low=None,
            close=close,
            volume=None,
            change=None,
        )
        for dt, close in appendable_sorted
    ]
    written = upsert_daily_prices(
        rows_for_db,
        source=payload.source or "KRX_DATA_MARKET",
        db_path=db_path,
    )

    # status 결정 우선순위:
    # 1. 입력 자체 충돌 (동일 batch 안에서 동일 date 다른 값) / bad price / 기존 충돌
    #    → missing_confirm (사용자 확인 필요)
    # 2. 벤치마크 달력 없음 → 결측 검증 기준 부재. KODEX200 적재가 선행되지 않은
    #    상태에서 ETF 를 normal 로 표시하지 않는다 (지시문 §5 / B-1 보강).
    # 3. post_listing_missing > 0 → partial
    # 4. 그 외 → normal
    if has_conflict or has_bad or has_existing_conflict:
        status = STATUS_MISSING_CONFIRM
        if has_existing_conflict:
            sample = ",".join(existing_conflict_dates[:3])
            err = f"existing_price_conflict: dates={sample}"
        else:
            err = "conflict_or_bad_price"
    elif not benchmark_calendar_available:
        status = STATUS_PARTIAL
        err = "benchmark_calendar_unavailable"
    elif post_missing > 0:
        status = STATUS_PARTIAL
        err = None
    else:
        status = STATUS_NORMAL
        err = None

    upsert_state(
        TimeseriesIngestionStateRow(
            ticker=payload.ticker,
            ingestion_status=status,
            confirmed_listing_date=payload.confirmed_listing_date,
            confirmed_series_start_date=series_start,
            confirmed_series_end_date=series_end,
            observed_trading_day_count=len(appendable_sorted),
            post_listing_missing_count=post_missing,
            source=payload.source,
            price_basis=payload.price_basis,
            error_summary=err,
        ),
        db_path=db_path,
    )
    return IngestionResult(
        ticker=payload.ticker,
        status=status,
        rows_written=written,
        observed_trading_day_count=len(appendable_sorted),
        post_listing_missing_count=post_missing,
        series_start_date=series_start,
        series_end_date=series_end,
        error_summary=err,
    )


def ingest_benchmark_timeseries(
    *,
    benchmark_id: str,
    benchmark_name: str,
    rows: list[tuple[str, Optional[float]]],
    source: Optional[str] = "KRX_DATA_MARKET",
    price_basis: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> IngestionResult:
    """벤치마크 (KODEX200 등) 시계열 적재.

    KODEX200 은 ETF 이므로 기존 `etf_daily_price` 에 저장한다 (지시문 Q4 답).
    KOSPI 같은 지수형 벤치마크는 `market_benchmark_daily_price` 에 저장.
    """
    valid, bad, has_bad = _classify_rows(rows)
    has_conflict = _detect_duplicate_conflict(valid)

    if not valid:
        upsert_state(
            TimeseriesIngestionStateRow(
                ticker=benchmark_id,
                ingestion_status=STATUS_LISTING_UNKNOWN,
                source=source,
                price_basis=price_basis,
                error_summary="no_valid_rows",
            ),
            db_path=db_path,
        )
        return IngestionResult(
            ticker=benchmark_id,
            status=STATUS_LISTING_UNKNOWN,
            rows_written=0,
            observed_trading_day_count=0,
            post_listing_missing_count=0,
            series_start_date=None,
            series_end_date=None,
            error_summary="no_valid_rows",
        )

    # 기존 가격과 충돌 검출 — 저장 위치별로 다른 read 함수 사용.
    if benchmark_id == BENCHMARK_KODEX200_TICKER:
        existing = fetch_existing_close_map(benchmark_id, db_path=db_path)
    else:
        existing = fetch_existing_benchmark_close_map(benchmark_id, db_path=db_path)
    appendable, existing_conflict_dates = _split_by_existing_conflict(valid, existing)
    has_existing_conflict = len(existing_conflict_dates) > 0

    if not appendable:
        upsert_state(
            TimeseriesIngestionStateRow(
                ticker=benchmark_id,
                ingestion_status=STATUS_MISSING_CONFIRM,
                source=source,
                price_basis=price_basis,
                error_summary="all_rows_conflict_with_existing",
            ),
            db_path=db_path,
        )
        return IngestionResult(
            ticker=benchmark_id,
            status=STATUS_MISSING_CONFIRM,
            rows_written=0,
            observed_trading_day_count=0,
            post_listing_missing_count=0,
            series_start_date=None,
            series_end_date=None,
            error_summary="all_rows_conflict_with_existing",
        )

    appendable_sorted = sorted(appendable, key=lambda x: x[0])
    series_start = appendable_sorted[0][0]
    series_end = appendable_sorted[-1][0]

    if benchmark_id == BENCHMARK_KODEX200_TICKER:
        rows_for_db = [
            EtfDailyPriceRow(
                ticker=benchmark_id,
                date=dt,
                open=None,
                high=None,
                low=None,
                close=close,
                volume=None,
                change=None,
            )
            for dt, close in appendable_sorted
        ]
        written = upsert_daily_prices(
            rows_for_db, source=source or "KRX_DATA_MARKET", db_path=db_path
        )
    else:
        written = upsert_benchmark_prices(
            benchmark_id=benchmark_id,
            benchmark_name=benchmark_name,
            rows=[(dt, close) for dt, close in appendable_sorted],
            source=source or "KRX_DATA_MARKET",
            db_path=db_path,
        )

    if has_conflict or has_bad or has_existing_conflict:
        status = STATUS_MISSING_CONFIRM
        if has_existing_conflict:
            sample = ",".join(existing_conflict_dates[:3])
            err = f"existing_price_conflict: dates={sample}"
        else:
            err = "conflict_or_bad_price"
    else:
        status = STATUS_NORMAL
        err = None

    upsert_state(
        TimeseriesIngestionStateRow(
            ticker=benchmark_id,
            ingestion_status=status,
            confirmed_series_start_date=series_start,
            confirmed_series_end_date=series_end,
            observed_trading_day_count=len(appendable_sorted),
            post_listing_missing_count=0,
            source=source,
            price_basis=price_basis,
            error_summary=err,
        ),
        db_path=db_path,
    )
    return IngestionResult(
        ticker=benchmark_id,
        status=status,
        rows_written=written,
        observed_trading_day_count=len(appendable_sorted),
        post_listing_missing_count=0,
        series_start_date=series_start,
        series_end_date=series_end,
        error_summary=err,
    )
