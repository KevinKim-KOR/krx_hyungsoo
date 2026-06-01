"""ETF 구성종목 SQLite 저장소 (POC2 — ETF Constituents & Overlap 1차).

본 모듈은 2개 신규 테이블만 관리한다:
- etf_constituents: ETF 별 (asof, ticker, source) → 상위 N 구성종목 + 비중.
- etf_constituent_refresh_log: 수집 결과 로그 (성공/실패/타임아웃).

저장 위치는 시장 데이터 DB (`state/market/market_data.sqlite`) 와 동일 파일이다.
Decision Evidence DB 와는 분리.

본 모듈은 외부 fetch 하지 않는다 — write/read 책임만. 외부 fetch 는
`etf_constituents_fetcher.py`, 흐름 제어 (cache / cap / delay / budget) 는
`etf_constituents_service.py` 가 담당한다.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH

ETF_CONSTITUENTS_DDL = """
CREATE TABLE IF NOT EXISTS etf_constituents (
    etf_ticker               TEXT NOT NULL,
    asof                     TEXT NOT NULL,
    source                   TEXT NOT NULL,
    rank                     INTEGER NOT NULL,
    constituent_ticker       TEXT,
    constituent_name         TEXT,
    weight_pct               REAL,
    etf_name                 TEXT,
    constituent_key          TEXT,
    constituent_isin         TEXT,
    constituent_reuters_code TEXT,
    market_type              TEXT,
    created_at               TEXT NOT NULL,
    PRIMARY KEY (etf_ticker, asof, source, rank)
);
""".strip()

ETF_CONSTITUENT_REFRESH_LOG_DDL = """
CREATE TABLE IF NOT EXISTS etf_constituent_refresh_log (
    etf_ticker  TEXT NOT NULL,
    asof        TEXT NOT NULL,
    status      TEXT NOT NULL,
    source      TEXT,
    message     TEXT,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (etf_ticker, asof, created_at)
);
""".strip()


@dataclass
class ConstituentRow:
    etf_ticker: str
    asof: str
    source: str
    rank: int
    constituent_ticker: Optional[str]
    constituent_name: Optional[str]
    weight_pct: Optional[float]
    etf_name: Optional[str] = None
    # 2026-05-31 — Naver Stock ETFComponent 통합 (지시문 §7).
    # constituent_key: 매칭 1차 키 (국내 ticker / 해외 reuters / ISIN /
    # normalized name 중 최우선 존재값). analysis._match_key 의 입력.
    constituent_key: Optional[str] = None
    constituent_isin: Optional[str] = None
    constituent_reuters_code: Optional[str] = None
    market_type: Optional[str] = None


def _utcnow_iso() -> str:
    # 마이크로초 포함 — etf_constituent_refresh_log PK 의 created_at 정렬/유일성
    # 보장 (같은 초 안 연속 log 가능). decision_evidence_store 와 동일 패턴.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _migrate_add_naver_columns(con: sqlite3.Connection) -> None:
    """2026-05-31 — Naver Stock ETFComponent 통합으로 4 컬럼 추가.

    이전 STEP 의 DB (constituent_key 등 없음) 에 대해 init_constituents_db
    호출 시점에 자동 ALTER TABLE ADD COLUMN. 각 컬럼 누락 시에만 추가.
    """
    cur = con.execute("PRAGMA table_info(etf_constituents)")
    cols = {row[1] for row in cur.fetchall()}
    if not cols:
        return
    for new_col in (
        ("constituent_key", "TEXT"),
        ("constituent_isin", "TEXT"),
        ("constituent_reuters_code", "TEXT"),
        ("market_type", "TEXT"),
    ):
        if new_col[0] not in cols:
            con.execute(
                f"ALTER TABLE etf_constituents ADD COLUMN {new_col[0]} {new_col[1]}"
            )


def init_constituents_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """2개 신규 테이블 보장 + Naver source 통합 마이그레이션.

    마이그레이션 순서:
    1. CREATE TABLE IF NOT EXISTS (신규 4 컬럼 포함) — 신규 DB.
    2. _migrate_add_naver_columns — 기존 DB 자동 컬럼 추가 (POC2 2026-05-31).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(ETF_CONSTITUENTS_DDL)
        con.execute(ETF_CONSTITUENT_REFRESH_LOG_DDL)
        _migrate_add_naver_columns(con)
        con.commit()


@contextmanager
def _connection(db_path: Path):
    init_constituents_db(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def has_constituents(
    *,
    etf_ticker: str,
    asof: str,
    source: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """캐시 체크 — (ticker, asof, source) 키로 구성종목 1건 이상 있는지."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT 1 FROM etf_constituents "
            "WHERE etf_ticker = ? AND asof = ? AND source = ? LIMIT 1",
            (etf_ticker, asof, source),
        )
        return cur.fetchone() is not None


def upsert_constituents(
    rows: Iterable[ConstituentRow],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """ConstituentRow 들을 (etf_ticker, asof, source, rank) PK 기준 upsert.

    2026-05-31 — constituent_key / isin / reuters_code / market_type 4 컬럼
    추가 영속화 (Naver Stock ETFComponent 통합).
    """
    now = _utcnow_iso()
    payload = [
        (
            r.etf_ticker,
            r.asof,
            r.source,
            int(r.rank),
            r.constituent_ticker,
            r.constituent_name,
            r.weight_pct,
            r.etf_name,
            r.constituent_key,
            r.constituent_isin,
            r.constituent_reuters_code,
            r.market_type,
            now,
        )
        for r in rows
    ]
    if not payload:
        return 0
    sql = """
    INSERT INTO etf_constituents
        (etf_ticker, asof, source, rank, constituent_ticker, constituent_name,
         weight_pct, etf_name, constituent_key, constituent_isin,
         constituent_reuters_code, market_type, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(etf_ticker, asof, source, rank) DO UPDATE SET
        constituent_ticker = excluded.constituent_ticker,
        constituent_name = excluded.constituent_name,
        weight_pct = excluded.weight_pct,
        etf_name = excluded.etf_name,
        constituent_key = excluded.constituent_key,
        constituent_isin = excluded.constituent_isin,
        constituent_reuters_code = excluded.constituent_reuters_code,
        market_type = excluded.market_type,
        created_at = excluded.created_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, payload)
    return len(payload)


_FETCH_COLUMNS = (
    "etf_ticker, asof, source, rank, constituent_ticker, constituent_name, "
    "weight_pct, etf_name, constituent_key, constituent_isin, "
    "constituent_reuters_code, market_type"
)


def fetch_constituents(
    *,
    etf_ticker: str,
    asof: str,
    source: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> list[ConstituentRow]:
    """(ticker, asof) 의 구성종목 — rank ASC. source 가 None 이면 모든 source."""
    with _connection(db_path) as con:
        if source is None:
            cur = con.execute(
                f"SELECT {_FETCH_COLUMNS} "
                "FROM etf_constituents WHERE etf_ticker = ? AND asof = ? "
                "ORDER BY rank ASC",
                (etf_ticker, asof),
            )
        else:
            cur = con.execute(
                f"SELECT {_FETCH_COLUMNS} "
                "FROM etf_constituents WHERE etf_ticker = ? AND asof = ? "
                "AND source = ? ORDER BY rank ASC",
                (etf_ticker, asof, source),
            )
        return [
            ConstituentRow(
                etf_ticker=r[0],
                asof=r[1],
                source=r[2],
                rank=r[3],
                constituent_ticker=r[4],
                constituent_name=r[5],
                weight_pct=r[6],
                etf_name=r[7],
                constituent_key=r[8],
                constituent_isin=r[9],
                constituent_reuters_code=r[10],
                market_type=r[11],
            )
            for r in cur.fetchall()
        ]


def log_constituent_refresh(
    *,
    etf_ticker: str,
    asof: str,
    status: str,
    source: Optional[str],
    message: Optional[str],
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """수집 결과 1건 기록 (status: ok / unavailable / skipped_timeout / cached)."""
    now = _utcnow_iso()
    with _connection(db_path) as con:
        con.execute(
            "INSERT INTO etf_constituent_refresh_log "
            "(etf_ticker, asof, status, source, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (etf_ticker, asof, status, source, message, now),
        )


def latest_constituent_asof(
    etf_ticker: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[str]:
    """ticker 의 가장 최근 asof — 캐시 우선 결정 시 사용."""
    with _connection(db_path) as con:
        cur = con.execute(
            "SELECT MAX(asof) FROM etf_constituents WHERE etf_ticker = ?",
            (etf_ticker,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None
