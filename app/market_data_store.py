"""SQLite 시장 데이터 저장소 (POC2 — B 방향 PC 작업 1~2단계).

본 모듈은 다음 3개 테이블만 관리한다:
- etf_master: ETF universe 1회 listing 결과
- etf_daily_price: ETF 가격 시계열 (upsert)
- market_refresh_log: 수집 결과 로그

본 모듈은 운영 상태 / 승인 / Telegram / Run 상태를 저장하지 않는다.
decision_evidence 테이블 신설 금지 (BACKLOG — 별도 STEP).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

DEFAULT_DB_PATH = Path("state/market/market_data.sqlite")

ETF_MASTER_DDL = """
CREATE TABLE IF NOT EXISTS etf_master (
    ticker        TEXT PRIMARY KEY,
    name          TEXT,
    category      TEXT,
    price         REAL,
    volume        INTEGER,
    market_cap    REAL,
    source        TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL
);
""".strip()

ETF_DAILY_PRICE_DDL = """
CREATE TABLE IF NOT EXISTS etf_daily_price (
    ticker     TEXT NOT NULL,
    date       TEXT NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    volume     INTEGER,
    change     REAL,
    source     TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ticker, date)
);
""".strip()

MARKET_REFRESH_LOG_DDL = """
CREATE TABLE IF NOT EXISTS market_refresh_log (
    run_id           TEXT PRIMARY KEY,
    source           TEXT NOT NULL,
    asof             TEXT NOT NULL,
    attempted_count  INTEGER NOT NULL DEFAULT 0,
    success_count    INTEGER NOT NULL DEFAULT 0,
    fail_count       INTEGER NOT NULL DEFAULT 0,
    runtime_seconds  REAL NOT NULL DEFAULT 0,
    error_summary    TEXT,
    created_at       TEXT NOT NULL
);
""".strip()


@dataclass
class EtfMasterRow:
    ticker: str
    name: Optional[str]
    category: Optional[str]
    price: Optional[float]
    volume: Optional[int]
    market_cap: Optional[float]


@dataclass
class EtfDailyPriceRow:
    ticker: str
    date: str  # 'YYYY-MM-DD'
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    change: Optional[float]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create database file + tables if missing.

    Decision evidence 테이블은 생성하지 않는다 (BACKLOG).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(ETF_MASTER_DDL)
        con.execute(ETF_DAILY_PRICE_DDL)
        con.execute(MARKET_REFRESH_LOG_DDL)
        con.commit()


@contextmanager
def _connection(db_path: Path):
    init_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert_etf_master(
    rows: Iterable[EtfMasterRow],
    *,
    source: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """ETF universe 1회 listing 결과를 etf_master 에 upsert.

    rows 는 단일 universe listing 호출 결과여야 한다 — ticker 별 N+1 호출 금지.
    같은 ticker 가 다시 들어오면 마지막 last_seen_at 으로 갱신.
    """
    now = _utcnow_iso()
    payload = [
        (
            r.ticker,
            r.name,
            r.category,
            r.price,
            r.volume,
            r.market_cap,
            source,
            now,
        )
        for r in rows
    ]
    sql = """
    INSERT INTO etf_master
        (ticker, name, category, price, volume, market_cap, source, last_seen_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ticker) DO UPDATE SET
        name = excluded.name,
        category = excluded.category,
        price = excluded.price,
        volume = excluded.volume,
        market_cap = excluded.market_cap,
        source = excluded.source,
        last_seen_at = excluded.last_seen_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, payload)
    return len(payload)


def upsert_daily_prices(
    rows: Iterable[EtfDailyPriceRow],
    *,
    source: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """가격 시계열을 etf_daily_price 에 upsert. (ticker, date) PK 기준 중복 제거."""
    now = _utcnow_iso()
    payload = [
        (
            r.ticker,
            r.date,
            r.open,
            r.high,
            r.low,
            r.close,
            r.volume,
            r.change,
            source,
            now,
        )
        for r in rows
    ]
    sql = """
    INSERT INTO etf_daily_price
        (ticker, date, open, high, low, close, volume, change, source, fetched_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ticker, date) DO UPDATE SET
        open = excluded.open,
        high = excluded.high,
        low = excluded.low,
        close = excluded.close,
        volume = excluded.volume,
        change = excluded.change,
        source = excluded.source,
        fetched_at = excluded.fetched_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, payload)
    return len(payload)


def log_refresh(
    *,
    run_id: str,
    source: str,
    asof: str,
    attempted: int,
    success: int,
    fail: int,
    runtime_seconds: float,
    error_summary: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """market_refresh_log 1건 기록 (성공/실패/runtime/오류 요약)."""
    now = _utcnow_iso()
    with _connection(db_path) as con:
        con.execute(
            "INSERT OR REPLACE INTO market_refresh_log "
            "(run_id, source, asof, attempted_count, success_count, fail_count, "
            "runtime_seconds, error_summary, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                source,
                asof,
                int(attempted),
                int(success),
                int(fail),
                float(runtime_seconds),
                error_summary,
                now,
            ),
        )


def list_etf_tickers(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    with _connection(db_path) as con:
        cur = con.execute("SELECT ticker FROM etf_master ORDER BY ticker")
        return [row[0] for row in cur.fetchall()]


def get_etf_name(ticker: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[str]:
    with _connection(db_path) as con:
        cur = con.execute("SELECT name FROM etf_master WHERE ticker = ?", (ticker,))
        row = cur.fetchone()
        return row[0] if row else None


def fetch_price_history(
    ticker: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[tuple[str, float]]:
    """(date, close) 시계열 (date ASC). close 가 null/0 이하인 행은 제외."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT date, close FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date ASC",
            (ticker,),
        )
        return [(r[0], float(r[1])) for r in cur.fetchall()]


def table_exists(table: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        )
        return cur.fetchone() is not None


def latest_refresh_log(
    source: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[dict]:
    with _connection(db_path) as con:
        if source:
            cur = con.execute(
                "SELECT run_id, source, asof, attempted_count, success_count, "
                "fail_count, runtime_seconds, error_summary, created_at "
                "FROM market_refresh_log WHERE source = ? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (source,),
            )
        else:
            cur = con.execute(
                "SELECT run_id, source, asof, attempted_count, success_count, "
                "fail_count, runtime_seconds, error_summary, created_at "
                "FROM market_refresh_log ORDER BY created_at DESC, rowid DESC LIMIT 1"
            )
        row = cur.fetchone()
        if not row:
            return None
        cols = [
            "run_id",
            "source",
            "asof",
            "attempted_count",
            "success_count",
            "fail_count",
            "runtime_seconds",
            "error_summary",
            "created_at",
        ]
        return dict(zip(cols, row))


def write_artifact_json(payload: dict, *, path: Path) -> None:
    """TOP N artifact 저장 — atomic write (.tmp → rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)


def normalize_ticker_list(values: Sequence) -> list[str]:
    """문자열 ticker 시퀀스를 6자리 zero-pad — universe 정규화 공용 유틸."""
    out: list[str] = []
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        out.append(s.zfill(6) if len(s) <= 6 else s)
    return out
