"""Market Risk Reference v1 evidence service — SQLite read + change 계산."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.market_benchmark_store import upsert_benchmark_prices
from app.market_data_store import (
    EtfDailyPriceRow,
    init_db,
    upsert_daily_prices,
)
from app.market_risk_reference_service import (
    BENCHMARK_KODEX200_TICKER,
    BENCHMARK_VIX_ID,
    build_market_risk_reference,
)


@pytest.fixture
def fake_db(tmp_path: Path) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    return db


def _seed_kodex(db: Path, series: list[tuple[str, float]]) -> None:
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker=BENCHMARK_KODEX200_TICKER,
                date=dt,
                open=None,
                high=None,
                low=None,
                close=c,
                volume=None,
                change=None,
            )
            for dt, c in series
        ],
        source="TEST",
        db_path=db,
    )


def _seed_vix(db: Path, series: list[tuple[str, float]]) -> None:
    upsert_benchmark_prices(
        benchmark_id=BENCHMARK_VIX_ID,
        benchmark_name="VIX",
        rows=[(dt, c) for dt, c in series],
        source="TEST",
        db_path=db,
    )


def test_unavailable_when_no_data(fake_db: Path) -> None:
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.kodex200.availability == "unavailable"
    assert ev.kodex200.recent_20d_series == []
    assert ev.vix.availability == "unavailable"
    assert ev.vix.recent_20d_series == []


def test_kodex_available_with_change_1d(fake_db: Path) -> None:
    _seed_kodex(
        fake_db,
        [("2026-06-30", 34000.0), ("2026-07-01", 34500.0), ("2026-07-02", 34845.0)],
    )
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.kodex200.availability == "available"
    assert ev.kodex200.as_of_date == "2026-07-02"
    assert ev.kodex200.close == 34845.0
    # (34845/34500 - 1) * 100 = 1.0
    assert ev.kodex200.change_1d_pct == pytest.approx(1.0, abs=1e-6)
    # series 는 오름차순.
    dates = [p.date for p in ev.kodex200.recent_20d_series]
    assert dates == ["2026-06-30", "2026-07-01", "2026-07-02"]


def test_vix_available_with_change_5d(fake_db: Path) -> None:
    _seed_vix(
        fake_db,
        [
            ("2026-06-24", 10.0),  # 5d prior for latest
            ("2026-06-25", 10.5),
            ("2026-06-26", 11.0),
            ("2026-06-27", 11.5),
            ("2026-06-28", 12.0),  # 1d prior for latest
            ("2026-06-29", 15.0),  # latest
        ],
    )
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.vix.availability == "available"
    assert ev.vix.as_of_date == "2026-06-29"
    assert ev.vix.close == 15.0
    # 1d: (15/12 - 1) * 100 = 25.0
    assert ev.vix.change_1d_pct == pytest.approx(25.0, abs=1e-6)
    # 5d: (15/10 - 1) * 100 = 50.0
    assert ev.vix.change_5d_pct == pytest.approx(50.0, abs=1e-6)


def test_vix_change_5d_null_when_lt_6_obs(fake_db: Path) -> None:
    _seed_vix(
        fake_db,
        [
            ("2026-06-28", 12.0),
            ("2026-06-29", 15.0),
        ],
    )
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.vix.availability == "available"
    assert ev.vix.change_1d_pct == pytest.approx(25.0, abs=1e-6)
    # 6개 미만 → 5d null.
    assert ev.vix.change_5d_pct is None


def test_series_capped_at_20(fake_db: Path) -> None:
    _seed_kodex(fake_db, [(f"2026-06-{i:02d}", 100.0 + i) for i in range(1, 26)])
    ev = build_market_risk_reference(db_path=fake_db)
    assert len(ev.kodex200.recent_20d_series) == 20


def test_kodex_and_vix_asof_dates_can_differ(fake_db: Path) -> None:
    """지시문 §3 — 두 기준일이 다르면 숨기지 않고 각자 표시."""
    _seed_kodex(fake_db, [("2026-07-01", 34000.0), ("2026-07-02", 34500.0)])
    _seed_vix(fake_db, [("2026-06-29", 15.0), ("2026-06-30", 14.0)])
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.kodex200.as_of_date == "2026-07-02"
    assert ev.vix.as_of_date == "2026-06-30"
    assert ev.kodex200.as_of_date != ev.vix.as_of_date


def test_series_first_last_date_reflects_full_range(fake_db: Path) -> None:
    """FIX r1 — 상세 노출용 series_first_date / series_last_date 는 전체 저장
    범위 (최근 20건이 아니라 저장된 모든 close>0 행) 를 반영해야 한다.
    """
    # 25 rows: recent_20d_series 는 20건 cap 되지만 first/last 는 전체 범위.
    _seed_kodex(fake_db, [(f"2026-06-{i:02d}", 100.0 + i) for i in range(1, 26)])
    _seed_vix(fake_db, [(f"2020-01-{i:02d}", 10.0 + i) for i in range(1, 26)])
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.kodex200.series_first_date == "2026-06-01"
    assert ev.kodex200.series_last_date == "2026-06-25"
    assert ev.vix.series_first_date == "2020-01-01"
    assert ev.vix.series_last_date == "2020-01-25"


def test_series_bounds_none_when_unavailable(fake_db: Path) -> None:
    ev = build_market_risk_reference(db_path=fake_db)
    assert ev.kodex200.series_first_date is None
    assert ev.kodex200.series_last_date is None
    assert ev.vix.series_first_date is None
    assert ev.vix.series_last_date is None
