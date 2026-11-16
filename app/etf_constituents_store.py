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

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from app.market_data_store import DEFAULT_DB_PATH

# ── POC6-31 원천일 확인 표시(내용 지문) — 쓰는 쪽(저장)과 읽는 쪽(상태 · 분석)이 같은 정의를 쓰게 이 아래층에 둔다 ──
# 'ok' 기록 문구 머리 + ':' + 저장한 행(DB 에서 다시 읽은 표현)의 내용 지문.
SOURCE_CONFIRMED = "source_date_confirmed"
CONFIRM_PREFIX = SOURCE_CONFIRMED + ":"
# POC6-31 STEP 4(검토 지적 backend#0) — 확인 기록 끝 표시: 저장 행이 원천이 준 전체(요청 깊이보다 적게 받았고 버린 항목
# 없음). 없는 기록(이 표시 전 기록 · 30행 · 버린 항목 있음)은 원천 전체인지 모름 — 읽는 쪽은 지문 부분만 대조한다.
COMPLETE_SUFFIX = ";source_complete"
# 지문 칸 순서(저장 행 · 읽은 행 공통)
ROW_SQL = (
    "rank, constituent_ticker, constituent_name, weight_pct, etf_name, "
    "constituent_key, constituent_isin, constituent_reuters_code, market_type"
)


def _norm_cell(v: Any) -> Any:
    # 검증자 r3 F7 — 부동소수 -0.0 은 SQLite REAL 을 거치면 0.0 으로 읽힌다. 같은 값으로 맞춘다.
    if isinstance(v, float) and v == 0.0:
        return 0.0
    return v


def fingerprint(rows: Iterable[Sequence[Any]]) -> str:
    """구성 행 내용 지문(순위순 · 칸 순서 `ROW_SQL`) — 같은 내용이면 같은 값."""
    norm = sorted(([_norm_cell(v) for v in r] for r in rows), key=lambda r: r[0])
    raw = json.dumps(norm, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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

    2026-06-01 FIX — FastAPI threadpool 동시 init race 보호. PRAGMA 확인
    시점과 ALTER 실행 시점 사이에 다른 스레드가 같은 컬럼을 추가하면
    SQLite 가 "duplicate column name" OperationalError 를 던진다.
    이 경우는 정상 race (다른 스레드가 이미 완료) 이므로 무시.
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
            try:
                con.execute(
                    f"ALTER TABLE etf_constituents ADD COLUMN {new_col[0]} {new_col[1]}"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise


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


def replace_constituents_snapshot(
    rows: Iterable[ConstituentRow],
    *,
    log_status: str,
    log_message: Optional[str] = None,
    confirm: bool = False,
    complete: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """(etf_ticker, asof, source) 구성 한 벌을 통째로 바꾸고 확인 기록 한 줄을 **같은 트랜잭션**에 쓴다.

    POC6-31 검증자 r1 F1 — 같은 날짜에 다시 받은 응답이 더 적어도 예전 순위 행이 남지 않게(행 단위 upsert 와 다름).
    행과 기록이 함께 들어가거나 함께 실패한다(잠김이면 아무것도 바뀌지 않음). 행 · 기록의 `created_at` 은 같은 시각이다.
    기존 `upsert_constituents`(수동 수집 경로 · 얕은 재수집이 깊은 구성을 줄이지 않는 계약)는 그대로 둔다.

    confirm=True — 확인 기록 문구 = `source_date_confirmed:<지문>` 이고, 지문은 **같은 트랜잭션에서 방금 저장한 행을
    DB 에서 다시 읽어** 계산한다(검증자 r3 F7 — 저장 전 값과 DB 표현이 달라도 읽는 쪽과 같은 지문).
    """
    rows = list(rows)
    if not rows:
        raise ValueError("replace_constituents_snapshot: rows must not be empty")
    keys = {(r.etf_ticker, r.asof, r.source) for r in rows}
    if len(keys) != 1:
        raise ValueError("replace_constituents_snapshot: rows must share one snapshot")
    etf_ticker, asof, source = next(iter(keys))
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
    with _connection(db_path) as con:
        con.execute(
            "DELETE FROM etf_constituents WHERE etf_ticker = ? AND asof = ? AND source = ?",
            (etf_ticker, asof, source),
        )
        con.executemany(
            "INSERT INTO etf_constituents "
            "(etf_ticker, asof, source, rank, constituent_ticker, constituent_name, "
            "weight_pct, etf_name, constituent_key, constituent_isin, "
            "constituent_reuters_code, market_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            payload,
        )
        if confirm:
            back = con.execute(
                f"SELECT {ROW_SQL} FROM etf_constituents "
                "WHERE etf_ticker = ? AND asof = ? AND source = ? ORDER BY rank ASC",
                (etf_ticker, asof, source),
            ).fetchall()
            log_message = (
                CONFIRM_PREFIX
                + fingerprint(back)
                + (COMPLETE_SUFFIX if complete else "")
            )
        con.execute(
            "INSERT INTO etf_constituent_refresh_log "
            "(etf_ticker, asof, status, source, message, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (etf_ticker, asof, log_status, source, log_message, now),
        )
    return len(payload)


_FETCH_COLUMNS = (
    "etf_ticker, asof, source, rank, constituent_ticker, constituent_name, "
    "weight_pct, etf_name, constituent_key, constituent_isin, "
    "constituent_reuters_code, market_type"
)


def read_rows(
    con: sqlite3.Connection,
    *,
    etf_ticker: str,
    asof: str,
    source: Optional[str] = None,
) -> list[ConstituentRow]:
    """주어진 연결로 (ticker, asof) 구성 행 — rank ASC · source None 이면 모든 source.

    `fetch_constituents` 와 같은 결과(한 읽기 트랜잭션 안에서 쓰게 연결을 받음).
    """
    if source is None:
        cur = con.execute(
            f"SELECT {_FETCH_COLUMNS} FROM etf_constituents "
            "WHERE etf_ticker = ? AND asof = ? ORDER BY rank ASC",
            (etf_ticker, asof),
        )
    else:
        cur = con.execute(
            f"SELECT {_FETCH_COLUMNS} FROM etf_constituents "
            "WHERE etf_ticker = ? AND asof = ? AND source = ? ORDER BY rank ASC",
            (etf_ticker, asof, source),
        )
    return [ConstituentRow(*r) for r in cur.fetchall()]


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
