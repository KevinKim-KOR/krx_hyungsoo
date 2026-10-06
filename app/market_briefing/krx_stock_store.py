"""POC3-02D-OPS-04 항목 1 — 보유 코스피 개별주 KRX 공식 일별 종가 **별도 계열** 저장소.

설계자 Q1 (a) 확정 · 사용자 승인(2026-10-04):

```text
DB        기존 state/market/market_data.sqlite (새 DB 파일 0)
TABLE     krx_stock_daily_price_unadjusted (6열 · PK (date, ticker))
SOURCE    KRX_OPEN_API/stk_bydd_trd (기존 KRX 키)
BASIS     UNADJUSTED_TRADED_PRICE (정규장 종가 · 무조정)
범위       현재 보유 코스피 개별주 행만 저장 — 전 종목 적재 · 코스닥 · 전체 과거 백필 0
```

**ETF 무조정 표(`krx_etf_daily_price_unadjusted`)와 섞지 않는다** — 그 표에 행이 있으면
보유 가격 기준이 ETF 로 분류하고(`holdings_price_basis.classify_assets`) 적재 행 수 판정
(`krx_store.baseline_row_count`)과 대표 선정도 그 표 전체를 ETF 로 본다. `etf_daily_price`
(FDR)도 읽거나 쓰지 않는다. 표 생성은 이 모듈 `init_db` 가 한다
(`market_data_store.init_db` 의 표 목록은 그대로).

응답 필드(2026-10-06 실측 · `basDd=20261001` · 942행 · HTTP 200): `BAS_DD` · `ISU_CD`(6자리
단축코드) · `ISU_NM` · `MKT_NM`(`KOSPI`) · `TDD_CLSPRC` · `TDD_OPNPRC` · `TDD_HGPRC` ·
`TDD_LWPRC` 등. ETF 는 응답에 없다. 공개 전 날짜는 0행이다.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from app.market_data_store import DEFAULT_DB_PATH

TABLE = "krx_stock_daily_price_unadjusted"
SOURCE = "KRX_OPEN_API/stk_bydd_trd"
PRICE_BASIS = "UNADJUSTED_TRADED_PRICE"

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    date          TEXT NOT NULL,
    ticker        TEXT NOT NULL,
    close         REAL NOT NULL,
    source        TEXT NOT NULL,
    price_basis   TEXT NOT NULL,
    collected_at  TEXT NOT NULL,
    PRIMARY KEY (date, ticker)
);
"""


@dataclass(frozen=True)
class StockRow:
    date: str  # YYYY-MM-DD
    ticker: str
    close: float


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path or DEFAULT_DB_PATH))


def init_db(db_path: Optional[Path] = None) -> None:
    """이 표만 만든다. 다른 표를 건드리지 않는다."""
    con = _connect(db_path)
    try:
        con.execute(_SCHEMA)
        con.commit()
    finally:
        con.close()


def iso(bas_dd: str) -> str:
    return f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:8]}" if len(bas_dd) == 8 else bas_dd


def _close(raw: Any) -> Optional[float]:
    try:
        v = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def held_rows(
    rows: Sequence[dict[str, Any]], *, bas_dd: str, tickers: Iterable[str]
) -> list[StockRow]:
    """응답 1일치에서 **보유 종목 행만** 고른다. 종가가 없거나 0 이하인 행은 버린다.

    기준일(`BAS_DD`) 확인은 호출자가 응답 전체로 먼저 한다. 같은 종목이 두 번 오면
    그 종목을 저장하지 않는다(어느 값이 맞는지 모른다).
    """
    wanted = set(tickers)
    seen: dict[str, list[float]] = {}
    for r in rows:
        t = (r.get("ISU_CD") or "").strip()
        if t not in wanted or (r.get("BAS_DD") or "").strip() != bas_dd:
            continue
        c = _close(r.get("TDD_CLSPRC"))
        if c is not None:
            seen.setdefault(t, []).append(c)
    day = iso(bas_dd)
    return [
        StockRow(date=day, ticker=t, close=v[0])
        for t, v in sorted(seen.items())
        if len(v) == 1
    ]


def upsert(rows: Iterable[StockRow], *, db_path: Optional[Path] = None) -> int:
    """idempotent — 같은 `(date, ticker)` 는 덮어쓴다."""
    rows = list(rows)
    if not rows:
        return 0
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    con = _connect(db_path)
    try:
        con.executemany(
            f"INSERT INTO {TABLE} (date, ticker, close, source, price_basis, "
            f"collected_at) VALUES (?, ?, ?, ?, ?, ?) "
            f"ON CONFLICT(date, ticker) DO UPDATE SET "
            f"close=excluded.close, source=excluded.source, "
            f"price_basis=excluded.price_basis, collected_at=excluded.collected_at",
            [(r.date, r.ticker, r.close, SOURCE, PRICE_BASIS, now) for r in rows],
        )
        con.commit()
    finally:
        con.close()
    return len(rows)


def stored_dates(*, db_path: Optional[Path] = None) -> set[str]:
    """행이 하나라도 있는 날짜(이 계열 안에서만)."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        return {d for (d,) in con.execute(f"SELECT DISTINCT date FROM {TABLE}")}
    finally:
        con.close()


def closes_on_date(date: str, *, db_path: Optional[Path] = None) -> dict[str, float]:
    """`{ticker: close}` — 저장 뒤 read-back 용."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        return {
            t: float(c)
            for t, c in con.execute(
                f"SELECT ticker, close FROM {TABLE} WHERE date=? AND close > 0", (date,)
            )
        }
    finally:
        con.close()


def delete_date(date: str, *, db_path: Optional[Path] = None) -> int:
    """read-back 이 어긋난 날짜를 지운다(그 값으로 파생값을 내지 않게)."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(f"DELETE FROM {TABLE} WHERE date=?", (date,))
        con.commit()
        return cur.rowcount
    finally:
        con.close()


def read_holdings_stock_prices(
    tickers: Iterable[str],
    dates: Sequence[str] = (),
    *,
    db_path: Optional[Path] = None,
) -> tuple[set[str], dict[str, dict[str, float]]]:
    """보유 PUSH 개별주 가격 증거 전용 읽기.

    반환 `(이 계열에 적재 기록이 있는 ticker, {ticker: {date: close}})`. **읽기 전용으로
    연다** — 표를 만들지 않는다. DB · 표가 없으면 `sqlite3.Error` 를 그대로 올린다(호출자가
    '읽을 수 없음' 으로 그 종목 파생값만 닫는다). 종목이 없으면 연결하지 않는다.
    """
    wanted = sorted(set(tickers))
    days = sorted(set(dates))
    present: set[str] = set()
    closes: dict[str, dict[str, float]] = {}
    if not wanted:
        return present, closes
    uri = Path(db_path or DEFAULT_DB_PATH).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        q = ",".join("?" * len(wanted))
        for (t,) in con.execute(
            f"SELECT DISTINCT ticker FROM {TABLE} WHERE ticker IN ({q})", wanted
        ):
            present.add(t)
        if days:
            dq = ",".join("?" * len(days))
            for t, d, c in con.execute(
                f"SELECT ticker, date, close FROM {TABLE} WHERE ticker IN ({q}) "
                f"AND date IN ({dq}) AND close > 0",
                [*wanted, *days],
            ):
                closes.setdefault(t, {})[d] = float(c)
        return present, closes
    finally:
        con.close()


__all__ = [
    "PRICE_BASIS",
    "SOURCE",
    "TABLE",
    "StockRow",
    "closes_on_date",
    "delete_date",
    "held_rows",
    "init_db",
    "iso",
    "read_holdings_stock_prices",
    "stored_dates",
    "upsert",
]
