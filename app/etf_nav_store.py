"""ETF NAV / 괴리율 저장소 (POC2 — 2026-06-01).

Market Discovery Evidence Closeout 1차 — 지시문 §8.

테이블: etf_nav_daily (state/market/market_data.sqlite).
PK: (etf_ticker, asof, source).

본 store 는 fetch / upsert 만 담당. fetcher / service / 응답 계약과 분리.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path("state/market/market_data.sqlite")


ETF_NAV_DAILY_DDL = """
CREATE TABLE IF NOT EXISTS etf_nav_daily (
    etf_ticker         TEXT NOT NULL,
    asof               TEXT NOT NULL,
    nav                REAL,
    market_price       REAL,
    discount_rate_pct  REAL,
    source             TEXT NOT NULL,
    status             TEXT NOT NULL,
    message            TEXT,
    created_at         TEXT NOT NULL,
    PRIMARY KEY (etf_ticker, asof, source)
)
""".strip()


@dataclass(frozen=True)
class NavDailyRow:
    etf_ticker: str
    asof: str
    nav: Optional[float]
    market_price: Optional[float]
    discount_rate_pct: Optional[float]
    source: str
    status: str
    message: Optional[str]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def init_nav_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """테이블 보장. 신규 컬럼이 생길 경우 _safe_add_column 패턴 활용 (현재 없음)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(ETF_NAV_DAILY_DDL)
        con.commit()


@contextmanager
def _connection(db_path: Path):
    init_nav_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert_nav_rows(
    rows: list[NavDailyRow],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    if not rows:
        return 0
    now = _utcnow_iso()
    payload = [
        (
            r.etf_ticker,
            r.asof,
            r.nav,
            r.market_price,
            r.discount_rate_pct,
            r.source,
            r.status,
            r.message,
            now,
        )
        for r in rows
    ]
    sql = """
    INSERT INTO etf_nav_daily (
        etf_ticker, asof, nav, market_price, discount_rate_pct,
        source, status, message, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(etf_ticker, asof, source) DO UPDATE SET
        nav = excluded.nav,
        market_price = excluded.market_price,
        discount_rate_pct = excluded.discount_rate_pct,
        status = excluded.status,
        message = excluded.message,
        created_at = excluded.created_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, payload)
    return len(payload)


def fetch_latest_nav(
    *,
    etf_ticker: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[NavDailyRow]:
    """최신 asof 의 NAV row (source 무관) 1건. 없으면 None."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT etf_ticker, asof, nav, market_price, discount_rate_pct, "
            "source, status, message "
            "FROM etf_nav_daily WHERE etf_ticker = ? "
            "ORDER BY asof DESC, created_at DESC LIMIT 1",
            (etf_ticker,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return NavDailyRow(
            etf_ticker=row[0],
            asof=row[1],
            nav=row[2],
            market_price=row[3],
            discount_rate_pct=row[4],
            source=row[5],
            status=row[6],
            message=row[7],
        )


def fetch_all_latest_nav(
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[NavDailyRow]:
    """모든 ticker 의 최신 asof NAV row 1건씩 반환 (지시문 §4.5 read-only API 용도).

    PK 가 (ticker, asof, source) 이므로 한 ticker 에 여러 row 가 있을 수 있다.
    본 함수는 ticker 별로 (asof DESC, created_at DESC) 기준 최신 row 1건만 반환.
    DB 파일이 없으면 [] 반환.
    """
    if not db_path.exists():
        return []
    with _connection(db_path) as con:
        cur = con.execute("""
            SELECT t.etf_ticker, t.asof, t.nav, t.market_price, t.discount_rate_pct,
                   t.source, t.status, t.message
            FROM etf_nav_daily t
            INNER JOIN (
                SELECT etf_ticker,
                       MAX(asof) AS max_asof,
                       MAX(created_at) AS max_created_at
                FROM etf_nav_daily
                GROUP BY etf_ticker
            ) latest ON t.etf_ticker = latest.etf_ticker
                    AND t.asof = latest.max_asof
                    AND t.created_at = latest.max_created_at
            ORDER BY t.etf_ticker
            """)
        return [
            NavDailyRow(
                etf_ticker=row[0],
                asof=row[1],
                nav=row[2],
                market_price=row[3],
                discount_rate_pct=row[4],
                source=row[5],
                status=row[6],
                message=row[7],
            )
            for row in cur.fetchall()
        ]


def fetch_nav_rows(
    *,
    etf_ticker: str,
    asof: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[NavDailyRow]:
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT etf_ticker, asof, nav, market_price, discount_rate_pct, "
            "source, status, message "
            "FROM etf_nav_daily WHERE etf_ticker = ? AND asof = ? "
            "ORDER BY source ASC",
            (etf_ticker, asof),
        )
        return [
            NavDailyRow(
                etf_ticker=row[0],
                asof=row[1],
                nav=row[2],
                market_price=row[3],
                discount_rate_pct=row[4],
                source=row[5],
                status=row[6],
                message=row[7],
            )
            for row in cur.fetchall()
        ]
