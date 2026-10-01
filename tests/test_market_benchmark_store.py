"""market_benchmark_store + KOSPI refresh fetcher 단위 테스트 (POC2 — 2026-05-22)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


from app.market_benchmark_store import (
    fetch_benchmark_history,
    init_benchmark_db,
    latest_benchmark_date,
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


# KOSPI 적재(`refresh_kospi_benchmark`) 테스트는 POC3-02D-OPS-03 자료원 전환(FDR `KS11` →
# KRX `idx/kospi_dd_trd` · 확정 계약 9)으로 `tests/test_poc3_02d_ops03_kospi.py` 로 옮겼다.
# 옛 FDR 경로 · C7 `lag ≤ 1` 판정은 폐기됐다(T-2 는 정상이 아니다).
