"""GET /market/nav-discount/latest read-only API 테스트 (2026-06-08).

지시문 §4.5 / §5 / AC-4 / AC-5.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.etf_nav_store import NavDailyRow, upsert_nav_rows
from app.market_data_store import ETF_MASTER_DDL


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch) -> Path:
    """동일 tmp DB 를 market_data + etf_nav_daily 양쪽으로 사용.

    api_nav_discount 는 NAV_DB_PATH 와 MARKET_DB_PATH 가 같은 SQLite 파일이라고
    가정한다. monkeypatch 로 양쪽 default 를 같은 경로로 교체.
    """
    db = tmp_path / "market_data.sqlite"
    monkeypatch.setattr("app.api_nav_discount.NAV_DB_PATH", db, raising=False)
    monkeypatch.setattr("app.api_nav_discount.MARKET_DB_PATH", db, raising=False)
    # etf_master + etf_nav_daily 테이블 사전 생성.
    with sqlite3.connect(str(db)) as con:
        con.execute(ETF_MASTER_DDL)
        con.commit()
    return db


def _insert_master(db: Path, ticker: str, name: str) -> None:
    with sqlite3.connect(str(db)) as con:
        con.execute(
            "INSERT OR REPLACE INTO etf_master(ticker, name, source, last_seen_at) "
            "VALUES (?, ?, 'test', '2026-06-08T00:00:00Z')",
            (ticker, name),
        )
        con.commit()


def test_get_nav_discount_latest_empty_returns_empty_summary(tmp_db: Path):
    client = TestClient(app)
    resp = client.get("/market/nav-discount/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "empty"
    assert body["summary"]["total_count"] == 0
    assert body["items"] == []


def test_get_nav_discount_latest_returns_stored_rows_with_names(tmp_db: Path):
    _insert_master(tmp_db, "069500", "KODEX 200")
    _insert_master(tmp_db, "360750", "TIGER 미국S&P500")
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-06-08",
                nav=130551.0,
                market_price=131030.0,
                discount_rate_pct=0.367,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
            NavDailyRow(
                etf_ticker="360750",
                asof="2026-06-08",
                nav=28663.0,
                market_price=28845.0,
                discount_rate_pct=0.635,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
            NavDailyRow(
                etf_ticker="BAD",
                asof="2026-06-08",
                nav=None,
                market_price=None,
                discount_rate_pct=None,
                source="naver_etf_item_list",
                status="unavailable",
                message="missing",
            ),
        ],
        db_path=tmp_db,
    )

    client = TestClient(app)
    resp = client.get("/market/nav-discount/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["asof"] == "2026-06-08"
    assert body["source"] == "naver_etf_item_list"
    assert body["summary"]["total_count"] == 3
    assert body["summary"]["ok_count"] == 2
    assert body["summary"]["unavailable_count"] == 1
    # ticker 기준 정렬 — KODEX 200 / TIGER / BAD.
    tickers = [it["ticker"] for it in body["items"]]
    assert tickers == ["069500", "360750", "BAD"]
    k200 = next(it for it in body["items"] if it["ticker"] == "069500")
    assert k200["name"] == "KODEX 200"
    assert k200["nav"] == 130551.0
    assert k200["market_price"] == 131030.0
    assert k200["discount_rate_pct"] == 0.367
    assert k200["asof"] == "2026-06-08"
    assert k200["source"] == "naver_etf_item_list"
    assert k200["status"] == "ok"


def test_get_nav_discount_latest_returns_only_latest_per_ticker(tmp_db: Path):
    _insert_master(tmp_db, "069500", "KODEX 200")
    upsert_nav_rows(
        [
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-06-05",
                nav=130000.0,
                market_price=130500.0,
                discount_rate_pct=0.385,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
            NavDailyRow(
                etf_ticker="069500",
                asof="2026-06-08",
                nav=130551.0,
                market_price=131030.0,
                discount_rate_pct=0.367,
                source="naver_etf_item_list",
                status="ok",
                message=None,
            ),
        ],
        db_path=tmp_db,
    )
    client = TestClient(app)
    resp = client.get("/market/nav-discount/latest")
    body = resp.json()
    items = [it for it in body["items"] if it["ticker"] == "069500"]
    assert len(items) == 1
    assert items[0]["asof"] == "2026-06-08"
    assert items[0]["nav"] == 130551.0


def test_get_nav_discount_latest_does_not_call_external_source(
    tmp_db: Path, monkeypatch
):
    """본 API 는 etf_nav_daily 만 읽고 Naver 등 외부 source 를 호출하지 않는다 (지시문 §4.5)."""

    def _boom(*args, **kwargs):
        raise AssertionError("external source called by read-only API")

    monkeypatch.setattr(
        "app.naver_etf_universe_fetcher.fetch_universe_snapshot",
        _boom,
        raising=False,
    )
    monkeypatch.setattr(
        "app.etf_nav_service.refresh_nav_universe", _boom, raising=False
    )

    client = TestClient(app)
    resp = client.get("/market/nav-discount/latest")
    assert resp.status_code == 200
