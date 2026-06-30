"""시장 시계열 SQLite 기반 보강 — fixture 기반 자동 테스트 (2026-06-30).

본 테스트는 외부 네트워크 / 실제 KRX 자료 / 자격증명에 의존하지 않는다.
fake CSV 와 fake 가격 시계열을 입력으로 사용해 다음을 검증한다:

- 결측 분류 (상장 전 / 소스 미제공 / 상장 후 결측 / bad price)
- KODEX200 적재 후 ETF 결측 판정 기준 달력 사용
- 재개·중복 방지 (status=normal 인 종목 skip, ON CONFLICT 흡수)
- 충돌·bad price → missing_confirm 라벨
- 상태 카운트 / pending 리스트
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.market_data_store import fetch_price_history, init_db
from app.market_timeseries_ingestion_service import (
    BENCHMARK_KODEX200_TICKER,
    IngestionInput,
    ingest_benchmark_timeseries,
    ingest_etf_timeseries,
)
from app.market_timeseries_ingestion_store import (
    STATUS_FAILED,
    STATUS_LISTING_UNKNOWN,
    STATUS_MISSING_CONFIRM,
    STATUS_NORMAL,
    STATUS_PARTIAL,
    STATUS_SOURCE_MISSING,
    count_by_status,
    list_pending_tickers,
    list_states,
    read_state,
)


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _kodex200_three_day_calendar() -> list[tuple[str, float]]:
    return [
        ("2024-10-29", 100.0),
        ("2024-10-30", 101.0),
        ("2024-10-31", 102.0),
    ]


# ─── 벤치마크 적재 ───────────────────────────────────────────────────────


def test_kodex200_benchmark_ingestion_normal(fake_db: Path) -> None:
    """AC-2 / AC-3 — KODEX200 정상 적재 + etf_daily_price 에 저장."""
    rows = _kodex200_three_day_calendar()
    result = ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=rows,
        price_basis="raw_close",
        db_path=fake_db,
    )
    assert result.status == STATUS_NORMAL
    assert result.rows_written == 3
    assert result.observed_trading_day_count == 3
    assert result.series_start_date == "2024-10-29"
    assert result.series_end_date == "2024-10-31"
    # 실제 etf_daily_price 에 저장됐는지 확인.
    series = fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    assert len(series) == 3

    state = read_state(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    assert state is not None
    assert state.ingestion_status == STATUS_NORMAL
    assert state.price_basis == "raw_close"


def test_kodex200_bad_price_marks_missing_confirm(fake_db: Path) -> None:
    """AC-6 — 0 / NaN / 음수는 적재 제외 + missing_confirm 라벨."""
    rows = [
        ("2024-10-29", 100.0),
        ("2024-10-30", 0.0),  # bad
        ("2024-10-31", 101.0),
    ]
    result = ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=rows,
        price_basis="raw_close",
        db_path=fake_db,
    )
    assert result.status == STATUS_MISSING_CONFIRM
    assert result.rows_written == 2  # 0.0 은 제외


# ─── ETF 적재 + 결측 분류 ────────────────────────────────────────────────


def test_etf_post_listing_missing_classification(fake_db: Path) -> None:
    """AC-5 — 확인된 시계열 시작 이후 KODEX200 거래일에 없으면 partial 라벨."""
    # 먼저 KODEX200 적재 (벤치마크 달력 확보).
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    benchmark_calendar = [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    ]
    # ETF 는 10-29, 10-31 만 있음 → 10-30 은 post-listing missing.
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[("2024-10-29", 200.0), ("2024-10-31", 210.0)],
            confirmed_listing_date="2024-10-29",
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    assert result.status == STATUS_PARTIAL
    assert result.post_listing_missing_count == 1
    assert result.observed_trading_day_count == 2


def test_etf_pre_listing_dates_are_not_missing(fake_db: Path) -> None:
    """AC-5 — 확인된 시계열 시작 이전의 KODEX200 거래일은 정상 비존재 (count X)."""
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    benchmark_calendar = [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    ]
    # ETF 가 10-30 부터 거래 시작 — 10-29 는 상장 전.
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[("2024-10-30", 200.0), ("2024-10-31", 210.0)],
            confirmed_listing_date="2024-10-30",
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    assert result.status == STATUS_NORMAL  # 시계열 범위 안에 missing 없음
    assert result.post_listing_missing_count == 0


def test_etf_source_missing(fake_db: Path) -> None:
    """AC-5 — 소스에 데이터 자체가 없으면 source_missing."""
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="000001",
            rows=[],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
            source_missing=True,
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    assert result.status == STATUS_SOURCE_MISSING
    assert result.rows_written == 0


def test_etf_conflict_marks_missing_confirm(fake_db: Path) -> None:
    """AC-6 — 동일 (ticker, date) 가 충돌 가격으로 들어오면 missing_confirm."""
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="069500",
            rows=[("2024-10-29", 100.0), ("2024-10-29", 105.0)],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    assert result.status == STATUS_MISSING_CONFIRM


def test_etf_no_rows_listing_unknown(fake_db: Path) -> None:
    """행 자체가 없거나 모두 bad price 면 listing_unknown."""
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="999999",
            rows=[],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    assert result.status == STATUS_LISTING_UNKNOWN


# ─── 재개·중복 방지 ──────────────────────────────────────────────────────


def test_resume_skips_normal_tickers(fake_db: Path) -> None:
    """AC-7 / AC-8 — 이미 normal 적재된 종목은 pending 에서 제외."""
    # KODEX200 적재 — benchmark calendar 확보 후에야 ETF 가 normal 일 수 있다.
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    benchmark_calendar = [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    ]
    ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[
                ("2024-10-29", 200.0),
                ("2024-10-30", 201.0),
                ("2024-10-31", 202.0),
            ],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    pending = list_pending_tickers(
        universe_tickers=["069500", "379800", "111111"], db_path=fake_db
    )
    # 069500 / 379800 모두 normal → pending 에서 제외.
    assert pending == ["111111"]


def test_duplicate_dates_absorbed_by_pk(fake_db: Path) -> None:
    """AC-8 — 두 번 ingest 해도 (ticker, date) PK 로 ON CONFLICT 흡수."""
    rows = [("2024-10-29", 100.0), ("2024-10-30", 101.0)]
    ingest_etf_timeseries(
        IngestionInput(
            ticker="069500",
            rows=rows,
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    # 동일 데이터 재적재 — 충돌 X (값 동일).
    ingest_etf_timeseries(
        IngestionInput(
            ticker="069500",
            rows=rows,
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    series = fetch_price_history("069500", db_path=fake_db)
    assert len(series) == 2


# ─── 기존 SQLite 가격과의 충돌 검출 (FIX r1) ─────────────────────────────


def test_existing_price_conflict_blocks_overwrite(fake_db: Path) -> None:
    """A-1/A-3/A-4 보강 — 기존 (ticker, date, close) 와 충돌하는 새 가격은
    적재 X, status=missing_confirm.
    """
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    # 동일 date 에 다른 close (100 → 200) 로 재적재 시도.
    result = ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=[("2024-10-29", 200.0)],
        price_basis="raw_close",
        db_path=fake_db,
    )
    assert result.status == STATUS_MISSING_CONFIRM
    assert result.error_summary == "all_rows_conflict_with_existing"
    # 기존 가격 보존.
    series = dict(fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db))
    assert series["2024-10-29"] == 100.0


def test_etf_existing_price_conflict_blocks_overwrite(fake_db: Path) -> None:
    """ETF 적재도 동일 — 기존 가격 보존."""
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    benchmark_calendar = [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    ]
    ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[("2024-10-29", 200.0)],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    # 다른 가격으로 재적재 시도.
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[("2024-10-29", 300.0)],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    assert result.status == STATUS_MISSING_CONFIRM
    series = dict(fetch_price_history("379800", db_path=fake_db))
    assert series["2024-10-29"] == 200.0


def test_existing_same_price_is_idempotent(fake_db: Path) -> None:
    """동일 (date, close) 재적재는 충돌 아님 — ON CONFLICT 흡수."""
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    result = ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    assert result.status == STATUS_NORMAL


# ─── 벤치마크 달력 없음 → ETF 적재는 partial (FIX r1, B-1 보강) ─────────


def test_etf_without_benchmark_calendar_is_partial(fake_db: Path) -> None:
    """KODEX200 적재가 선행되지 않은 상태에서 ETF normal 부여 금지 (지시문 §5)."""
    result = ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[("2024-10-29", 100.0), ("2024-10-30", 101.0)],
            source="KRX_DATA_MARKET",
            price_basis="raw_close",
        ),
        benchmark_calendar=[],
        db_path=fake_db,
    )
    assert result.status == STATUS_PARTIAL
    assert result.error_summary == "benchmark_calendar_unavailable"


# ─── 상태 집계 ───────────────────────────────────────────────────────────


def test_count_by_status_enum_complete(fake_db: Path) -> None:
    """count_by_status 가 모든 enum 키를 0 으로 초기화하여 반환."""
    counts = count_by_status(db_path=fake_db)
    assert set(counts.keys()) == {
        STATUS_NORMAL,
        STATUS_PARTIAL,
        STATUS_MISSING_CONFIRM,
        STATUS_SOURCE_MISSING,
        STATUS_FAILED,
        STATUS_LISTING_UNKNOWN,
    }
    assert all(v == 0 for v in counts.values())


def test_list_states_after_mixed_ingestion(fake_db: Path) -> None:
    """다양한 상태 ingest 후 list_states 가 ticker 정렬로 반환."""
    ingest_benchmark_timeseries(
        benchmark_id=BENCHMARK_KODEX200_TICKER,
        benchmark_name="KODEX 200",
        rows=_kodex200_three_day_calendar(),
        price_basis="raw_close",
        db_path=fake_db,
    )
    benchmark_calendar = [
        dt for dt, _ in fetch_price_history(BENCHMARK_KODEX200_TICKER, db_path=fake_db)
    ]
    ingest_etf_timeseries(
        IngestionInput(
            ticker="379800",
            rows=[
                ("2024-10-29", 200.0),
                ("2024-10-30", 201.0),
                ("2024-10-31", 202.0),
            ],
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    ingest_etf_timeseries(
        IngestionInput(
            ticker="000001",
            rows=[],
            source_missing=True,
        ),
        benchmark_calendar=benchmark_calendar,
        db_path=fake_db,
    )
    states = list_states(db_path=fake_db)
    assert [s.ticker for s in states] == ["000001", "069500", "379800"]
    statuses = {s.ticker: s.ingestion_status for s in states}
    assert statuses["000001"] == STATUS_SOURCE_MISSING
    assert statuses["069500"] == STATUS_NORMAL
    assert statuses["379800"] == STATUS_NORMAL
