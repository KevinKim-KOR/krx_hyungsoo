"""market_benchmark_store + KOSPI refresh fetcher 단위 테스트 (POC2 — 2026-05-22)."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path


from app.market_benchmark_store import (
    fetch_benchmark_history,
    init_benchmark_db,
    latest_benchmark_date,
    refresh_kospi_benchmark,
    upsert_benchmark_prices,
)


def test_init_benchmark_db_creates_table(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    init_benchmark_db(db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='market_benchmark_daily_price'"
        )
        assert cur.fetchone() is not None


def test_upsert_and_fetch_benchmark_history(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    rows = [
        ("2026-05-20", 2700.0),
        ("2026-05-21", 2710.0),
        ("2026-05-22", 2725.0),
    ]
    written = upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=rows,
        source="test_source",
        db_path=db,
    )
    assert written == 3
    history = fetch_benchmark_history("KOSPI", db_path=db)
    assert history == [(d, c) for d, c in rows]
    assert latest_benchmark_date("KOSPI", db_path=db) == "2026-05-22"


def test_upsert_benchmark_prices_skips_null_and_nonpositive(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    upsert_benchmark_prices(
        benchmark_id="KOSPI",
        benchmark_name="KOSPI",
        rows=[
            ("2026-05-20", None),
            ("2026-05-21", 0.0),
            ("2026-05-22", 2725.0),
        ],
        source="test",
        db_path=db,
    )
    history = fetch_benchmark_history("KOSPI", db_path=db)
    # null + 0 은 fetch 단계에서 제외 (close > 0 가드).
    assert history == [("2026-05-22", 2725.0)]


def test_refresh_kospi_benchmark_with_stub_fetcher_ok(tmp_path: Path):
    """fetcher stub 으로 외부 FDR 의존 없이 흐름 검증."""
    db = tmp_path / "market_data.sqlite"

    class FakeDF:
        columns = ["Open", "High", "Low", "Close", "Volume"]

        def __init__(self):
            self._rows = [
                ("2026-05-20", 2700.0),
                ("2026-05-21", 2710.0),
                ("2026-05-22", 2725.0),
            ]

        def __len__(self):
            return len(self._rows)

        def iterrows(self):
            class _Idx:
                def __init__(self, s):
                    self._s = s

                def strftime(self, fmt):  # noqa: ARG002
                    return self._s

            for dt, close in self._rows:
                yield _Idx(dt), {"Close": close}

    def fake_fetcher(ticker, start, end):
        assert ticker == "KS11"
        return FakeDF()

    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=fake_fetcher,
        db_path=db,
    )
    assert result["status"] == "ok"
    assert result["rows_written"] == 3
    assert latest_benchmark_date("KOSPI", db_path=db) == "2026-05-22"


def test_refresh_kospi_benchmark_returns_failed_on_exception(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"

    def boom_fetcher(ticker, start, end):  # noqa: ARG001
        raise RuntimeError("network timeout")

    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=boom_fetcher,
        db_path=db,
    )
    assert result["status"] == "failed"
    assert "RuntimeError" in result["error"]
    assert result["rows_written"] == 0
    # DB 는 생성됐지만 KOSPI rows 는 0.
    assert fetch_benchmark_history("KOSPI", db_path=db) == []


def test_refresh_kospi_benchmark_returns_failed_on_empty_df(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"

    class EmptyDF:
        columns = ["Close"]

        def __len__(self):
            return 0

        def iterrows(self):
            return iter(())

    def empty_fetcher(ticker, start, end):  # noqa: ARG001
        return EmptyDF()

    result = refresh_kospi_benchmark(
        end_date=date(2026, 5, 22),
        price_fetcher=empty_fetcher,
        db_path=db,
    )
    assert result["status"] == "failed"
    assert result["error"] == "no_data"
