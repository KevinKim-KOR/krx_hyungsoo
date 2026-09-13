"""POC3-OPS-02B-2 — KRX 무조정 가격 **별도 계열** 저장소.

설계자 최종 확정 (PLAN §M-1):

```text
PRICE_SUPPLY = KRX_DAILY_FULL_ETF_SNAPSHOT
PRICE_BASIS  = UNADJUSTED_TRADED_PRICE
STORAGE      = SEPARATE_SERIES
TABLE        = krx_etf_daily_price_unadjusted
```

**왜 별도 테이블인가** — 기존 `etf_daily_price` 는 배당조정 계열이고 KRX 는
무조정 실거래가다. 두 계열을 이어 붙이면 구간 경계에서 수익률이 깨진다
(`DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY`). 그래서 **join 하지 않고 분리**한다.

**이 테이블이 하는 일은 하나다** — `최근 강한 기초지수` 계산의 가격 공급.
UI·ML·보유 PUSH 로 확장하지 않는다.

**하지 않는 것**

- `etf_daily_price` 의 `open`·`close` 를 읽거나 수정하지 않는다
- 두 계열을 join 하지 않는다
- 조정/무조정을 구간 중간에서 연결하지 않는다
- 이 변경으로 `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 가 해결됐다고 기록하지 않는다
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from app.market_data_store import DEFAULT_DB_PATH

TABLE = "krx_etf_daily_price_unadjusted"
SOURCE = "KRX_OPEN_API"
PRICE_BASIS = "UNADJUSTED_TRADED_PRICE"

# 20거래일 수익률에는 최신일 포함 21개 완료 거래일이 필요하다 (PLAN §M-1).
REQUIRED_TRADING_DAYS = 21
LOOKBACK_5D = 5
LOOKBACK_20D = 20

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


class KrxSnapshotError(RuntimeError):
    """정상 적재로 처리하면 안 되는 snapshot. 호출자가 fail-closed 한다."""


@dataclass(frozen=True)
class SnapshotRow:
    date: str
    ticker: str
    close: float


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path or DEFAULT_DB_PATH))


def init_db(db_path: Optional[Path] = None) -> None:
    """테이블 생성. **기존 `etf_daily_price` 를 건드리지 않는다.**"""
    con = _connect(db_path)
    try:
        con.execute(_SCHEMA)
        con.commit()
    finally:
        con.close()


def validate_snapshot(
    rows: Sequence[dict[str, Any]], *, expected_date: str
) -> list[SnapshotRow]:
    """API 응답 1일치를 검사한다. 하나라도 어긋나면 **전체를 거부**한다.

    설계자 §M-1 fail-closed 목록 — 빈 응답 · ticker 중복 · 종가 결측 ·
    0 이하 가격 · **응답 기준일 불일치**.

    부분 저장을 허용하면 "일부만 최신" 인 계열이 생겨 그룹 `n` 판정이 흔들린다.
    """
    if not rows:
        raise KrxSnapshotError("empty_response")

    seen: set[str] = set()
    out: list[SnapshotRow] = []
    for r in rows:
        ticker = (r.get("ISU_CD") or "").strip()
        bas_dd = (r.get("BAS_DD") or "").strip()
        raw_close = (r.get("TDD_CLSPRC") or "").replace(",", "").strip()
        if not ticker:
            raise KrxSnapshotError("missing_ticker")
        if bas_dd != expected_date:
            raise KrxSnapshotError(f"date_mismatch:{bas_dd}!={expected_date}")
        if ticker in seen:
            raise KrxSnapshotError(f"duplicate_ticker:{ticker}")
        seen.add(ticker)
        if not raw_close:
            raise KrxSnapshotError(f"missing_close:{ticker}")
        try:
            close = float(raw_close)
        except ValueError as e:  # noqa: BLE001
            raise KrxSnapshotError(f"unparsable_close:{ticker}") from e
        if close <= 0:
            raise KrxSnapshotError(f"non_positive_close:{ticker}")
        out.append(SnapshotRow(date=_iso(bas_dd), ticker=ticker, close=close))
    return out


def _iso(bas_dd: str) -> str:
    return f"{bas_dd[:4]}-{bas_dd[4:6]}-{bas_dd[6:8]}" if len(bas_dd) == 8 else bas_dd


def upsert_snapshot(
    rows: Iterable[SnapshotRow], *, db_path: Optional[Path] = None
) -> int:
    """검사를 통과한 1일치를 저장한다. **idempotent** — 같은 `(date, ticker)` 는 덮어쓴다."""
    rows = list(rows)
    if not rows:
        return 0
    init_db(db_path)
    now = _utcnow()
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


def stored_trading_days(*, db_path: Optional[Path] = None) -> list[str]:
    """저장된 거래일 (오름차순). 이 계열 안에서만 본다."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        return [
            d
            for (d,) in con.execute(f"SELECT DISTINCT date FROM {TABLE} ORDER BY date")
        ]
    finally:
        con.close()


def closes_on(
    dates: Sequence[str], *, db_path: Optional[Path] = None
) -> dict[str, dict[str, float]]:
    """`{date: {ticker: close}}`. **`etf_daily_price` 를 읽지 않는다.**"""
    if not dates:
        return {}
    init_db(db_path)
    con = _connect(db_path)
    try:
        q = ",".join("?" * len(dates))
        out: dict[str, dict[str, float]] = {d: {} for d in dates}
        for d, t, c in con.execute(
            f"SELECT date, ticker, close FROM {TABLE} WHERE date IN ({q}) AND close > 0",
            list(dates),
        ):
            out[d][t] = c
        return out
    finally:
        con.close()


@dataclass(frozen=True)
class PriceWindow:
    """수익률 계산에 쓰는 세 기준일. 셋 다 있어야 유효하다."""

    latest: str
    d5: str
    d20: str

    @property
    def dates(self) -> tuple[str, str, str]:
        return (self.latest, self.d5, self.d20)


def resolve_window(*, db_path: Optional[Path] = None) -> Optional[PriceWindow]:
    """저장된 거래일로 세 기준일을 정한다.

    **최신일 포함 21개 완료 거래일이 없으면 `None`** — 20일 수익률을 내지 않는다
    (설계자 §M-1·§M-8-40).
    """
    days = stored_trading_days(db_path=db_path)
    if len(days) < REQUIRED_TRADING_DAYS:
        return None
    return PriceWindow(
        latest=days[-1], d5=days[-1 - LOOKBACK_5D], d20=days[-1 - LOOKBACK_20D]
    )


__all__ = [
    "LOOKBACK_20D",
    "LOOKBACK_5D",
    "PRICE_BASIS",
    "PriceWindow",
    "REQUIRED_TRADING_DAYS",
    "SOURCE",
    "TABLE",
    "KrxSnapshotError",
    "SnapshotRow",
    "closes_on",
    "init_db",
    "resolve_window",
    "stored_trading_days",
    "upsert_snapshot",
    "validate_snapshot",
]
