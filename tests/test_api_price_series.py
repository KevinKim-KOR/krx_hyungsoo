"""POC3-02 REMEDIATION-1 — 가격 시계열 read API focused test.

계약 (지시문 §6·§12 AC-9~13):
- 저장값 일치 · date ASC · availability AVAILABLE/NO_DATA/UNAVAILABLE 구분.
- ticker 형식 오류 vs 저장 데이터 없음 vs 조회 실패 구분.
- 저장값 재계산 없음.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.market_benchmark_store import init_benchmark_db, upsert_benchmark_prices
from app.market_data_store import init_db, EtfDailyPriceRow, upsert_daily_prices


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "market_data.sqlite"
    init_db(db)
    init_benchmark_db(db)
    monkeypatch.setattr("app.api_price_series.MARKET_DB_PATH", db, raising=False)
    return db


def _seed(db: Path, ticker: str, rows: list[tuple[str, float]]) -> None:
    upsert_daily_prices(
        [
            EtfDailyPriceRow(
                ticker=ticker,
                date=d,
                open=None,
                high=None,
                low=None,
                close=c,
                volume=None,
                change=None,
            )
            for (d, c) in rows
        ],
        source="test",
        db_path=db,
    )


def test_available_returns_stored_series_date_ascending(tmp_db: Path):
    # 저장 순서를 뒤섞어도 응답은 date ASC (AC-10).
    _seed(
        tmp_db,
        "069500",
        [("2026-07-03", 34000.0), ("2026-07-01", 33000.0), ("2026-07-02", 33500.0)],
    )
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"ticker": "069500"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["availability"] == "AVAILABLE"
    assert body["available_from"] == "2026-07-01"
    assert body["available_to"] == "2026-07-03"
    dates = [p["date"] for p in body["series"]]
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]
    # 저장값 그대로 (재계산 없음 · AC-9).
    prices = {p["date"]: p["price"] for p in body["series"]}
    assert prices["2026-07-01"] == 33000.0
    assert prices["2026-07-03"] == 34000.0


def test_no_data_distinct_from_available(tmp_db: Path):
    # 정상 형식 ticker 인데 저장 데이터 없음 → NO_DATA (빈 정상 아님 · AC-11).
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"ticker": "999999"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["availability"] == "NO_DATA"
    assert body["series"] == []
    assert body["available_from"] is None


def test_invalid_ticker_distinct_from_no_data(tmp_db: Path):
    # ticker 형식 오류 → UNAVAILABLE (NO_DATA 와 구분 · AC-11).
    # 길이 미달/초과·특수문자만 형식 오류 (6자 영숫자는 유효).
    client = TestClient(app)
    for bad in ("", "abc", "12345", "1234567", "06-500"):
        resp = client.get("/market/price-series", params={"ticker": bad})
        assert resp.status_code == 200
        body = resp.json()
        assert body["availability"] == "UNAVAILABLE"
        assert body["reason"] == "invalid_ticker"


def test_alphanumeric_ticker_accepted(tmp_db: Path):
    # 실제 ETF 영숫자 ticker (예: 0000D0) 는 형식 유효 → 저장 데이터 반환.
    _seed(tmp_db, "0000D0", [("2026-07-01", 10000.0), ("2026-07-02", 10100.0)])
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"ticker": "0000D0"})
    body = resp.json()
    assert body["availability"] == "AVAILABLE"
    assert body["series"][0]["date"] == "2026-07-01"


def test_read_failure_distinct_and_no_raw_leak(tmp_path, monkeypatch):
    # 내부 조회 실패 → UNAVAILABLE(read_failure) · raw 예외/경로 미노출 (AC-11).
    def _boom(*a, **k):
        raise RuntimeError("SELECT ... /secret/path/market_data.sqlite")

    monkeypatch.setattr("app.api_price_series.fetch_price_history", _boom)
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"ticker": "069500"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["availability"] == "UNAVAILABLE"
    assert body["reason"] == "read_failure"
    # raw SQL/경로가 응답에 노출되지 않음.
    assert "/secret/path" not in resp.text
    assert "SELECT" not in resp.text


# ─── POC3-01 오늘의 투자 점검 — KOSPI benchmark 시계열 확장 (Q1-a) ────────


def _seed_benchmark(db: Path, benchmark_id: str, rows: list[tuple[str, float]]) -> None:
    upsert_benchmark_prices(
        benchmark_id=benchmark_id,
        benchmark_name=benchmark_id,
        rows=rows,
        source="test",
        db_path=db,
    )


def test_benchmark_kospi_returns_stored_series(tmp_db: Path):
    # ?benchmark=KOSPI → market_benchmark_daily_price 저장값 그대로 date ASC.
    _seed_benchmark(
        tmp_db,
        "KOSPI",
        [("2026-07-02", 2650.0), ("2026-07-01", 2600.0), ("2026-07-03", 2700.0)],
    )
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"benchmark": "KOSPI"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["availability"] == "AVAILABLE"
    assert body["ticker"] == "KOSPI"
    dates = [p["date"] for p in body["series"]]
    assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]
    prices = {p["date"]: p["price"] for p in body["series"]}
    assert prices["2026-07-01"] == 2600.0  # 저장값 그대로 (재계산 없음)
    assert body["available_from"] == "2026-07-01"
    assert body["available_to"] == "2026-07-03"


def test_benchmark_is_case_insensitive(tmp_db: Path):
    # 소문자 benchmark 도 정규화되어 조회 (kospi → KOSPI).
    _seed_benchmark(tmp_db, "KOSPI", [("2026-07-01", 2600.0)])
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"benchmark": "kospi"})
    body = resp.json()
    assert body["availability"] == "AVAILABLE"
    assert body["ticker"] == "KOSPI"


def test_benchmark_no_data_distinct(tmp_db: Path):
    # 허용 benchmark 이나 저장 데이터 없음 → NO_DATA (빈 정상 아님).
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"benchmark": "KOSPI"})
    body = resp.json()
    assert body["availability"] == "NO_DATA"
    assert body["series"] == []


def test_benchmark_not_allowed_rejected(tmp_db: Path):
    # 허용 목록 밖 benchmark → UNAVAILABLE(invalid_benchmark). 임의 조회 차단.
    client = TestClient(app)
    for bad in ("NASDAQ", "SP500", "KOSDAQ"):
        resp = client.get("/market/price-series", params={"benchmark": bad})
        body = resp.json()
        assert body["availability"] == "UNAVAILABLE"
        assert body["reason"] == "invalid_benchmark"


def test_benchmark_takes_precedence_over_ticker(tmp_db: Path):
    # benchmark 와 ticker 동시 → benchmark 우선 (KOSPI 반환).
    _seed(tmp_db, "069500", [("2026-07-01", 34000.0)])
    _seed_benchmark(tmp_db, "KOSPI", [("2026-07-01", 2600.0)])
    client = TestClient(app)
    resp = client.get(
        "/market/price-series", params={"ticker": "069500", "benchmark": "KOSPI"}
    )
    body = resp.json()
    assert body["ticker"] == "KOSPI"
    assert body["series"][0]["price"] == 2600.0


def test_benchmark_read_failure_no_raw_leak(tmp_db: Path, monkeypatch):
    # benchmark 조회 내부 실패 → UNAVAILABLE(read_failure) · raw 미노출.
    def _boom(*a, **k):
        raise RuntimeError("SELECT ... /secret/benchmark.sqlite")

    monkeypatch.setattr("app.api_price_series.fetch_benchmark_history", _boom)
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"benchmark": "KOSPI"})
    body = resp.json()
    assert body["availability"] == "UNAVAILABLE"
    assert body["reason"] == "read_failure"
    assert "/secret" not in resp.text
    assert "SELECT" not in resp.text


def test_close_le_zero_excluded(tmp_db: Path):
    # fetch_price_history 가 close<=0/null 제외 → 저장 계약 그대로 반영.
    _seed(tmp_db, "069500", [("2026-07-01", 33000.0), ("2026-07-02", 33500.0)])
    # close 0 인 행 직접 삽입.
    with sqlite3.connect(str(tmp_db)) as con:
        con.execute(
            "INSERT INTO etf_daily_price(ticker,date,close,source,fetched_at) "
            "VALUES('069500','2026-07-03',0,'test','t')"
        )
        con.commit()
    client = TestClient(app)
    resp = client.get("/market/price-series", params={"ticker": "069500"})
    body = resp.json()
    dates = [p["date"] for p in body["series"]]
    assert "2026-07-03" not in dates  # close 0 제외
    assert body["available_to"] == "2026-07-02"
