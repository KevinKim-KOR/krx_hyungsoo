"""POC3-ML-02 — U2 화면 슬레이트 PIT 재현 (PLAN §4.12).

화면의 Top 10 은 ML 점수 상위 10개가 아니다. 인버스·레버리지·합성·선물을 제외한
뒤 `one_month desc` 로 뽑은 10개에 점수를 나중에 붙여 순서만 바꾼다.

**C-4 (PLAN §1.10)**: `compute_topn(asof=t)` 만으로는 과거가 재현되지 않는다.
`_compute_period` 가 최신가를 `history[-1]` 에서 가져오는데
`fetch_price_history` 는 날짜 제한 없이 전체를 읽기 때문이다.

따라서 본 모듈은 **`date <= t` 로 절단한 임시 SQLite** 를 만들어
`compute_topn(asof=t, db_path=<임시>)` 를 호출한다. 운영 함수는 **무수정**이며
선정 규칙을 재구현하지 않는다 — 입력만 point-in-time 으로 만든다.

임시 DB 는 리밸런싱 날짜 순서대로 **증분 적재**한다 (전체 복사 145회 금지).
라이브 DB 는 read-only 로만 연다.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_topn import compute_topn
from app.market_topn_helpers import REQUIRED_TABLES

logger = logging.getLogger(__name__)

SCREEN_N = 10
SCREEN_BASIS = "one_month"
SCREEN_ORDER = "desc"

_PRICE_COLUMNS = (
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "change",
    "source",
    "fetched_at",
)


def _read_only_connect(db_path: Path) -> sqlite3.Connection:
    """라이브 DB 는 반드시 read-only 로 연다 (쓰기 사고 차단)."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _copy_schema_and_master(src: sqlite3.Connection, dst: sqlite3.Connection) -> None:
    """필수 테이블 DDL + etf_master / market_refresh_log 내용을 임시 DB 로 복사.

    `etf_daily_price` 는 **DDL 만** 복사한다 (내용은 증분 적재).
    """
    for table in REQUIRED_TABLES:
        row = src.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not row or not row[0]:
            raise RuntimeError(f"라이브 DB 에 필수 테이블이 없습니다: {table}")
        dst.execute(row[0])

    for table in ("etf_master", "market_refresh_log"):
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})").fetchall()]
        placeholders = ",".join("?" for _ in cols)
        rows = src.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall()
        if rows:
            dst.executemany(
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})",
                rows,
            )
    dst.commit()


def replay_screen_slates(
    rebalance_dates: list[str],
    *,
    live_db_path: Path = DEFAULT_DB_PATH,
    temp_db_path: Path,
    n: int = SCREEN_N,
    progress: Optional[Iterable] = None,
) -> dict[str, list[dict]]:
    """각 기준일의 화면 후보 슬레이트를 PIT 로 재현.

    반환: `{기준일: [{"rank":1,"ticker":...,"name":...,"one_month_return_pct":...}, ...]}`

    가격은 라이브 DB 를 date ASC 로 **1회 스캔**하며 임시 DB 에 증분 적재한다.
    기준일을 지날 때마다 그 시점의 임시 DB 로 `compute_topn` 을 호출한다.
    """
    ordered = sorted(set(rebalance_dates))
    if not ordered:
        return {}

    if temp_db_path.exists():
        temp_db_path.unlink()
    temp_db_path.parent.mkdir(parents=True, exist_ok=True)

    src = _read_only_connect(live_db_path)
    dst = sqlite3.connect(str(temp_db_path))
    result: dict[str, list[dict]] = {}
    try:
        _copy_schema_and_master(src, dst)

        cursor = src.execute(
            f"SELECT {','.join(_PRICE_COLUMNS)} FROM etf_daily_price "
            f"WHERE date <= ? ORDER BY date ASC",
            (ordered[-1],),
        )
        placeholders = ",".join("?" for _ in _PRICE_COLUMNS)
        insert_sql = (
            f"INSERT OR REPLACE INTO etf_daily_price "
            f"({','.join(_PRICE_COLUMNS)}) VALUES ({placeholders})"
        )

        pending: list[tuple] = []
        cut_idx = 0
        for row in cursor:
            row_date = row[1]
            # 현재 기준일을 넘어서는 행을 만나면, 그 전까지 적재하고 슬레이트 산출.
            while cut_idx < len(ordered) and row_date > ordered[cut_idx]:
                if pending:
                    dst.executemany(insert_sql, pending)
                    pending = []
                dst.commit()
                t = ordered[cut_idx]
                result[t] = _slate_at(t, temp_db_path, n)
                cut_idx += 1
            if cut_idx >= len(ordered):
                break
            pending.append(row)
            if len(pending) >= 20000:
                dst.executemany(insert_sql, pending)
                pending = []

        if pending:
            dst.executemany(insert_sql, pending)
        dst.commit()
        while cut_idx < len(ordered):
            t = ordered[cut_idx]
            result[t] = _slate_at(t, temp_db_path, n)
            cut_idx += 1
    finally:
        dst.close()
        src.close()
    return result


def _slate_at(t: str, db_path: Path, n: int) -> list[dict]:
    """단일 기준일의 슬레이트. `compute_topn` 을 **무수정 호출**한다."""
    payload = compute_topn(
        n=n,
        db_path=db_path,
        asof=t,
        basis=SCREEN_BASIS,
        order=SCREEN_ORDER,
        exclude_inverse=True,
        exclude_leveraged=True,
        exclude_synthetic=True,
        exclude_futures=True,
    )
    if payload.get("status") != "ok":
        logger.warning("slate %s status=%s", t, payload.get("status"))
        return []
    out: list[dict] = []
    for c in payload.get("candidates") or []:
        out.append(
            {
                "rank": c.get("rank"),
                "ticker": c.get("ticker"),
                "name": c.get("name"),
                "one_month_return_pct": c.get("selected_return_pct"),
                "basis_start_date": c.get("selected_basis_start_date"),
                "basis_end_date": c.get("selected_basis_end_date"),
            }
        )
    return out
