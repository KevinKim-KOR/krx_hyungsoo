"""etf_constituents + refresh_log store 단위 테스트 (POC2 — 2026-05-27)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.etf_constituents_store import (
    ConstituentRow,
    fetch_constituents,
    init_constituents_db,
    latest_constituent_asof,
    log_constituent_refresh,
    upsert_constituents,
)


def test_init_constituents_db_creates_two_tables(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    init_constituents_db(db)
    with sqlite3.connect(str(db)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('etf_constituents', 'etf_constituent_refresh_log')"
        )
        names = {row[0] for row in cur.fetchall()}
    assert names == {"etf_constituents", "etf_constituent_refresh_log"}


def test_upsert_and_fetch_constituents_round_trip(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    rows = [
        ConstituentRow(
            etf_ticker="139260",
            asof="2026-05-26",
            source="pykrx/get_etf_portfolio_deposit_file",
            rank=1,
            constituent_ticker="005930",
            constituent_name="삼성전자",
            weight_pct=25.1,
            etf_name="TIGER 200 IT",
        ),
        ConstituentRow(
            etf_ticker="139260",
            asof="2026-05-26",
            source="pykrx/get_etf_portfolio_deposit_file",
            rank=2,
            constituent_ticker="000660",
            constituent_name="SK하이닉스",
            weight_pct=15.2,
            etf_name="TIGER 200 IT",
        ),
    ]
    written = upsert_constituents(rows, db_path=db)
    assert written == 2

    fetched = fetch_constituents(etf_ticker="139260", asof="2026-05-26", db_path=db)
    assert [r.rank for r in fetched] == [1, 2]
    assert fetched[0].constituent_name == "삼성전자"
    assert fetched[1].weight_pct == 15.2


def test_upsert_conflict_updates_existing(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    base = ConstituentRow(
        etf_ticker="139260",
        asof="2026-05-26",
        source="pykrx",
        rank=1,
        constituent_ticker="005930",
        constituent_name="삼성전자",
        weight_pct=25.1,
    )
    upsert_constituents([base], db_path=db)
    # 같은 PK 로 비중 변경.
    updated = ConstituentRow(
        etf_ticker="139260",
        asof="2026-05-26",
        source="pykrx",
        rank=1,
        constituent_ticker="005930",
        constituent_name="삼성전자",
        weight_pct=26.5,
    )
    upsert_constituents([updated], db_path=db)
    fetched = fetch_constituents(etf_ticker="139260", asof="2026-05-26", db_path=db)
    assert len(fetched) == 1
    assert fetched[0].weight_pct == 26.5


def test_log_constituent_refresh_records_history(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    log_constituent_refresh(
        etf_ticker="139260",
        asof="2026-05-26",
        status="ok",
        source="pykrx",
        message=None,
        db_path=db,
    )
    log_constituent_refresh(
        etf_ticker="0167A0",
        asof="2026-05-26",
        status="unavailable",
        source="pykrx",
        message="no_data",
        db_path=db,
    )
    with sqlite3.connect(str(db)) as con:
        rows = con.execute(
            "SELECT etf_ticker, status FROM etf_constituent_refresh_log "
            "ORDER BY etf_ticker"
        ).fetchall()
    assert ("0167A0", "unavailable") in rows
    assert ("139260", "ok") in rows


def test_latest_constituent_asof_returns_max(tmp_path: Path):
    db = tmp_path / "market_data.sqlite"
    for asof in ("2026-05-20", "2026-05-26", "2026-05-22"):
        upsert_constituents(
            [
                ConstituentRow(
                    etf_ticker="139260",
                    asof=asof,
                    source="pykrx",
                    rank=1,
                    constituent_ticker="005930",
                    constituent_name="삼성전자",
                    weight_pct=25.0,
                )
            ],
            db_path=db,
        )
    assert latest_constituent_asof("139260", db_path=db) == "2026-05-26"
    assert latest_constituent_asof("UNKNOWN", db_path=db) is None
