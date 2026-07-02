"""Market timeseries ingestion state SSOT (2026-06-30 시장 시계열 SQLite 기반 보강).

종목별 적재·범위·결측 상태를 관리한다. 가격 시계열 자체는 기존
`etf_daily_price` / `market_benchmark_daily_price` 에 그대로 저장한다.
별도 가격 시계열 테이블 신설 금지.

본 모듈은 외부 네트워크 / 실제 KRX 자료 접근 / 자격증명을 사용하지 않는다.
실제 KRX 데이터마켓 자료를 PC 에서 CLI 로 읽은 결과를 SQLite 상태로
업서트하기 위한 read / write 함수만 제공한다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH

# 적재 상태 enum — DDL 주석과 동기.
STATUS_NORMAL = "normal"
STATUS_PARTIAL = "partial"
STATUS_MISSING_CONFIRM = "missing_confirm"
STATUS_SOURCE_MISSING = "source_missing"
STATUS_FAILED = "failed"
STATUS_LISTING_UNKNOWN = "listing_unknown"

ALL_STATUSES = (
    STATUS_NORMAL,
    STATUS_PARTIAL,
    STATUS_MISSING_CONFIRM,
    STATUS_SOURCE_MISSING,
    STATUS_FAILED,
    STATUS_LISTING_UNKNOWN,
)


@dataclass
class TimeseriesIngestionStateRow:
    ticker: str
    ingestion_status: str
    confirmed_listing_date: Optional[str] = None
    confirmed_series_start_date: Optional[str] = None
    confirmed_series_end_date: Optional[str] = None
    observed_trading_day_count: int = 0
    post_listing_missing_count: int = 0
    source: Optional[str] = None
    price_basis: Optional[str] = None
    error_summary: Optional[str] = None
    last_checked_at: Optional[str] = None


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_COLS = (
    "ticker",
    "confirmed_listing_date",
    "confirmed_series_start_date",
    "confirmed_series_end_date",
    "observed_trading_day_count",
    "post_listing_missing_count",
    "ingestion_status",
    "source",
    "price_basis",
    "last_checked_at",
    "error_summary",
)


def _ensure_table_only(db_path: Path) -> None:
    """DB 파일이 있을 때 테이블 보장. 부재 시 init_db 강제 호출하지 않는다."""
    if not db_path.exists():
        # DB 자체 부재 — read 는 None, write 는 init_db 후 진행.
        from app.market_data_store import init_db

        init_db(db_path)
        return
    from app.market_data_store import _ensure_initialized

    _ensure_initialized(db_path)


def read_state(
    ticker: str, db_path: Optional[Path] = None
) -> Optional[TimeseriesIngestionStateRow]:
    if db_path is None:
        from app import market_timeseries_ingestion_store as _self

        db_path = _self.DEFAULT_DB_PATH
    if not db_path.exists():
        return None
    _ensure_table_only(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            f"SELECT {', '.join(_COLS)} FROM market_timeseries_ingestion_state "
            "WHERE ticker = ?",
            (ticker,),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return TimeseriesIngestionStateRow(**dict(zip(_COLS, row)))


def list_states(
    db_path: Path = DEFAULT_DB_PATH,
) -> list[TimeseriesIngestionStateRow]:
    if not db_path.exists():
        return []
    _ensure_table_only(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            f"SELECT {', '.join(_COLS)} FROM market_timeseries_ingestion_state "
            "ORDER BY ticker"
        )
        rows = cur.fetchall()
    finally:
        con.close()
    return [TimeseriesIngestionStateRow(**dict(zip(_COLS, r))) for r in rows]


def upsert_state(
    state: TimeseriesIngestionStateRow,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    if state.ingestion_status not in ALL_STATUSES:
        raise ValueError(f"invalid ingestion_status: {state.ingestion_status}")
    _ensure_table_only(db_path)
    payload = (
        state.ticker,
        state.confirmed_listing_date,
        state.confirmed_series_start_date,
        state.confirmed_series_end_date,
        int(state.observed_trading_day_count),
        int(state.post_listing_missing_count),
        state.ingestion_status,
        state.source,
        state.price_basis,
        _utcnow_iso(),
        state.error_summary,
    )
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            """
            INSERT INTO market_timeseries_ingestion_state (
                ticker,
                confirmed_listing_date,
                confirmed_series_start_date,
                confirmed_series_end_date,
                observed_trading_day_count,
                post_listing_missing_count,
                ingestion_status,
                source,
                price_basis,
                last_checked_at,
                error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                confirmed_listing_date = excluded.confirmed_listing_date,
                confirmed_series_start_date = excluded.confirmed_series_start_date,
                confirmed_series_end_date = excluded.confirmed_series_end_date,
                observed_trading_day_count = excluded.observed_trading_day_count,
                post_listing_missing_count = excluded.post_listing_missing_count,
                ingestion_status = excluded.ingestion_status,
                source = excluded.source,
                price_basis = excluded.price_basis,
                last_checked_at = excluded.last_checked_at,
                error_summary = excluded.error_summary
            """,
            payload,
        )
        con.commit()
    finally:
        con.close()


def count_by_status(
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, int]:
    """ingestion_status 별 행 수. enum 전체 키를 0 으로 초기화하여 반환."""
    out: dict[str, int] = {status: 0 for status in ALL_STATUSES}
    if not db_path.exists():
        return out
    _ensure_table_only(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT ingestion_status, COUNT(*) "
            "FROM market_timeseries_ingestion_state "
            "GROUP BY ingestion_status"
        )
        for status, count in cur.fetchall():
            if status in out:
                out[status] = int(count)
    finally:
        con.close()
    return out


def list_pending_tickers(
    *,
    universe_tickers: list[str],
    db_path: Path = DEFAULT_DB_PATH,
) -> list[str]:
    """재개용 — 적재 상태 행이 없거나 status 가 normal 이 아닌 ticker.

    이미 정상 적재된 종목 (status=normal) 은 제외한다. AC-7 / AC-8 의 핵심.
    """
    if not db_path.exists():
        return list(universe_tickers)
    _ensure_table_only(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT ticker FROM market_timeseries_ingestion_state "
            "WHERE ingestion_status = ?",
            (STATUS_NORMAL,),
        )
        normal_set = {r[0] for r in cur.fetchall()}
    finally:
        con.close()
    return [tk for tk in universe_tickers if tk not in normal_set]


def clear_state(
    ticker: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """테스트 격리용. ticker 가 None 이면 전체 삭제."""
    if not db_path.exists():
        return
    con = sqlite3.connect(str(db_path))
    try:
        if ticker is None:
            con.execute("DELETE FROM market_timeseries_ingestion_state")
        else:
            con.execute(
                "DELETE FROM market_timeseries_ingestion_state WHERE ticker = ?",
                (ticker,),
            )
        con.commit()
    finally:
        con.close()
