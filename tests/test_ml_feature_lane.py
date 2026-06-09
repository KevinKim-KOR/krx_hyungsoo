"""ML 최소 데이터 레인 — store + builder + readiness API 테스트 (2026-06-08).

지시문 §11 (AC) — 외부 네트워크 의존 0. 모든 fixture 는 tmp_path SQLite.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.market_benchmark_store import (
    MARKET_BENCHMARK_DAILY_PRICE_DDL,
    upsert_benchmark_prices,
)
from app.market_data_store import (
    ETF_DAILY_PRICE_DDL,
    ETF_MASTER_DDL,
    MARKET_REFRESH_LOG_DDL,
)
from app.market_regime import KODEX200_TICKER, KOSPI_ID
from app.ml_feature_builder import build_features
from app.ml_feature_store import (
    ETF_ML_FEATURE_DAILY_DDL,
    MARKET_RISK_FEATURE_DAILY_DDL,
    fetch_readiness,
    upsert_etf_features,
    upsert_market_risk_features,
)

# ─── fixture: tmp DB with synthetic data ─────────────────────────────


def _create_schema(db: Path) -> None:
    with sqlite3.connect(str(db)) as con:
        con.execute(ETF_MASTER_DDL)
        con.execute(ETF_DAILY_PRICE_DDL)
        con.execute(MARKET_REFRESH_LOG_DDL)
        con.execute(MARKET_BENCHMARK_DAILY_PRICE_DDL)
        con.execute(ETF_ML_FEATURE_DAILY_DDL)
        con.execute(MARKET_RISK_FEATURE_DAILY_DDL)
        con.commit()


def _insert_master(db: Path, ticker: str, name: str) -> None:
    with sqlite3.connect(str(db)) as con:
        con.execute(
            "INSERT OR REPLACE INTO etf_master(ticker, name, source, last_seen_at) "
            "VALUES (?, ?, 'test', '2026-06-08T00:00:00Z')",
            (ticker, name),
        )
        con.commit()


def _insert_price_series(
    db: Path,
    ticker: str,
    dates_closes_volumes: list[tuple[str, float, int]],
) -> None:
    with sqlite3.connect(str(db)) as con:
        for d, c, v in dates_closes_volumes:
            con.execute(
                "INSERT OR REPLACE INTO etf_daily_price"
                "(ticker, date, close, volume, source, fetched_at) "
                "VALUES (?, ?, ?, ?, 'test', '2026-06-08T00:00:00Z')",
                (ticker, d, c, v),
            )
        con.commit()


def _make_25_day_series(
    base_close: float = 100.0, daily_change_pct: float = 1.0
) -> list[tuple[str, float, int]]:
    """25 거래일 시계열 — KODEX 영업일 simulator. 영업일은 2026-04-13 ~ 2026-05-18 평일.

    실제 캘린더와 무관. 거래 가능한 25 일을 단순 평일 시퀀스로 만든다.
    """
    from datetime import date, timedelta

    out: list[tuple[str, float, int]] = []
    cur = date(2026, 4, 13)  # Monday
    close = base_close
    for _ in range(25):
        # skip weekends (Sat=5, Sun=6)
        while cur.weekday() >= 5:
            cur += timedelta(days=1)
        out.append((cur.isoformat(), round(close, 4), 10000))
        close *= 1.0 + (daily_change_pct / 100.0)
        cur += timedelta(days=1)
    return out


@pytest.fixture
def tmp_db_with_data(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    _create_schema(db)

    # ETF master + price series — KODEX200 + 1 ticker.
    _insert_master(db, KODEX200_TICKER, "KODEX 200")
    _insert_master(db, "360750", "TIGER 미국S&P500")

    # KODEX200: +1%/day, TIGER: +0.5%/day
    _insert_price_series(db, KODEX200_TICKER, _make_25_day_series(100.0, 1.0))
    _insert_price_series(db, "360750", _make_25_day_series(50.0, 0.5))

    # KOSPI benchmark (별도 테이블) — 동일 영업일 시퀀스.
    kospi_rows = [(d, c) for d, c, _ in _make_25_day_series(2500.0, 0.5)]
    upsert_benchmark_prices(
        benchmark_id=KOSPI_ID,
        benchmark_name="KOSPI",
        rows=kospi_rows,
        source="test",
        db_path=db,
    )

    # api_ml_readiness 와 api_nav_discount 의 DEFAULT_DB_PATH 를 tmp 로 교체.
    monkeypatch.setattr("app.api_ml_readiness.DEFAULT_DB_PATH", db, raising=False)

    return db


# ─── builder tests ────────────────────────────────────────────────────


def test_build_features_returns_etf_and_market_rows(tmp_db_with_data: Path):
    result = build_features(
        db_path=tmp_db_with_data,
        start_date=None,
        end_date=None,
        default_lookback_days=10,
    )
    assert len(result.asofs) > 0
    assert len(result.etf_rows) > 0
    assert len(result.market_rows) == len(result.asofs)
    # universe 2 종목 × asof 수 만큼 (일부는 lookback 미달로 0 일 수 있음).
    # ETF row 의 ticker 분포 검증.
    tickers = {r.ticker for r in result.etf_rows}
    assert KODEX200_TICKER in tickers
    assert "360750" in tickers


def test_build_features_excess_return_uses_kodex200(tmp_db_with_data: Path):
    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    # 마지막 asof 의 360750 (TIGER) 의 excess return 은 -방향 (느린 +0.5/day vs +1.0/day).
    last_asof = result.asofs[-1]
    tiger_row = next(
        r for r in result.etf_rows if r.ticker == "360750" and r.asof == last_asof
    )
    assert tiger_row.return_5d is not None
    # KODEX200 는 더 빠르게 상승 → 초과수익 음수.
    assert tiger_row.excess_return_5d_vs_kodex200 is not None
    assert tiger_row.excess_return_5d_vs_kodex200 < 0


def test_build_features_nav_join_uses_latest_available_past(
    tmp_db_with_data: Path,
):
    """NAV asof < ETF asof 인 row 도 latest available 로 join 되어야 한다."""
    from app.etf_nav_store import NavDailyRow, upsert_nav_rows

    # ETF 의 첫 거래일보다 더 이전 NAV 1건 + 중간 1건.
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker=KODEX200_TICKER,
                asof="2026-04-10",
                nav=99.0,
                market_price=99.5,
                discount_rate_pct=0.5,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
        ],
        db_path=tmp_db_with_data,
    )

    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    kodex_rows = [r for r in result.etf_rows if r.ticker == KODEX200_TICKER]
    assert kodex_rows
    # 모든 KODEX row 가 NAV ok status (latest available = 2026-04-10) 로 join.
    assert all(r.nav_status == "ok" for r in kodex_rows)
    # 미래 NAV 가 없는데 latest available 이 과거이므로 source_flags 에 nav_asof 명시.
    assert all(
        r.source_flags is not None and "nav_asof=2026-04-10" in r.source_flags
        for r in kodex_rows
    )


def test_build_features_no_future_nav_join(tmp_db_with_data: Path):
    """미래 NAV 가 ETF asof 이전 row 에 join 되면 안 된다 (지시문 §6.4 #5)."""
    from app.etf_nav_store import NavDailyRow, upsert_nav_rows

    # 마지막 영업일보다 더 미래 NAV.
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker=KODEX200_TICKER,
                asof="2099-01-01",
                nav=999.0,
                market_price=999.0,
                discount_rate_pct=0.0,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
        ],
        db_path=tmp_db_with_data,
    )
    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    # 어떤 row 도 nav=999.0 으로 join 되지 않아야 한다.
    for r in result.etf_rows:
        if r.ticker == KODEX200_TICKER:
            assert r.nav != 999.0


def test_build_features_market_breadth_counts_match_universe(
    tmp_db_with_data: Path,
):
    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    # universe 가 2 종목 — up + down + flat <= 2.
    for m in result.market_rows:
        if m.etf_universe_up_count is None:
            continue
        total = (
            (m.etf_universe_up_count or 0)
            + (m.etf_universe_down_count or 0)
            + (m.etf_universe_flat_count or 0)
        )
        assert total <= 2


def test_build_features_no_data_returns_empty(tmp_path: Path):
    db = tmp_path / "empty.sqlite"
    _create_schema(db)
    result = build_features(db_path=db, default_lookback_days=10)
    assert result.etf_rows == []
    assert result.market_rows == []


# ─── store + readiness API tests ────────────────────────────────────


def test_upsert_then_readiness_returns_counts(tmp_db_with_data: Path):
    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    upsert_etf_features(result.etf_rows, db_path=tmp_db_with_data)
    upsert_market_risk_features(result.market_rows, db_path=tmp_db_with_data)

    readiness = fetch_readiness(db_path=tmp_db_with_data)
    assert readiness.etf_row_count > 0
    assert readiness.market_risk_row_count > 0
    assert readiness.etf_latest_asof is not None
    assert readiness.market_risk_latest_asof is not None


def test_readiness_api_returns_axes(tmp_db_with_data: Path):
    # 적재 후 API 호출.
    result = build_features(
        db_path=tmp_db_with_data,
        default_lookback_days=10,
    )
    upsert_etf_features(result.etf_rows, db_path=tmp_db_with_data)
    upsert_market_risk_features(result.market_rows, db_path=tmp_db_with_data)

    client = TestClient(app)
    resp = client.get("/ml/readiness/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["etf_feature_row_count"] > 0
    assert body["market_risk_row_count"] > 0
    assert len(body["axes"]) == 7
    # 모든 axis 가 available 상태여야 한다 (universe 2 ETF + KOSPI 적재).
    statuses = [a["status"] for a in body["axes"]]
    assert all(s == "available" for s in statuses)


def test_readiness_api_empty_db_returns_zero_counts(tmp_path: Path, monkeypatch):
    db = tmp_path / "empty.sqlite"
    # DB 파일 자체가 없어도 안전.
    monkeypatch.setattr("app.api_ml_readiness.DEFAULT_DB_PATH", db, raising=False)
    client = TestClient(app)
    resp = client.get("/ml/readiness/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["etf_feature_row_count"] == 0
    assert body["market_risk_row_count"] == 0
    assert all(a["status"] == "empty" for a in body["axes"])


def test_readiness_api_does_not_trigger_feature_build(
    tmp_db_with_data: Path, monkeypatch
):
    """readiness API 는 build_features 를 호출하지 않는다 (지시문 §4 / AC-1)."""

    def _boom(*args, **kwargs):
        raise AssertionError("build_features called from screen / API")

    monkeypatch.setattr("app.ml_feature_builder.build_features", _boom, raising=False)
    client = TestClient(app)
    resp = client.get("/ml/readiness/latest")
    assert resp.status_code == 200
