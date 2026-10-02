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

**이 테이블이 하는 일** — `최근 강한 기초지수` 계산의 가격 공급. 이전 Step 에서
승인돼 이미 읽는 곳이 더 있다 — 장중 사업군 5·20일 추세(`runtime_evidence.sector_signal`)
와 장중 설정 대표 선정 · 생성(`intraday_config.selector` · `generator` · 시장 갱신 뒤
후보 생성). 이번 개정(설계자 RESULT STEP 1)으로 더한 예외는 아래 보유 PUSH ETF 가격
증거뿐이다. UI 표시 · ML · 그 밖의 경로로 확장하지 않는다.

**보유 PUSH 는 ETF 가격 증거에 한해서만 허용한다** (설계자 RESULT STEP 1 ·
2026-09-30 개정). 보유 브리핑 · 장중 보유 위험의 ETF 20거래일 기준 종가 · 구간
종가를 현재가(Naver 무조정)와 같은 무조정 계열로 맞추기 위해서다
(`read_holdings_etf_prices`). 개별주 가격 · UI · ML 에는 쓰지 않는다.

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


# SQLite 변수 상한(옛 버전 999)과 무관하게 묻도록 나눠 묻는다.
_IN_CHUNK = 500


def first_loaded_dates(
    tickers: Iterable[str], *, db_path: Optional[Path] = None
) -> dict[str, str]:
    """`{ticker: 이 계열의 첫 적재일 MIN(date)}`. **값을 쓰지 않는다.**

    POC3-02D-OPS-01 C1 — pending gate 가 d20 종가 없는 신규 ETF 의 첫 적재일을
    기록할 때 쓴다(설계자 Q1 (c)). 적재 기록이 없는 ticker 는 담지 않는다.
    """
    wanted = sorted(set(tickers))
    if not wanted:
        return {}
    init_db(db_path)
    con = _connect(db_path)
    try:
        out: dict[str, str] = {}
        for start in range(0, len(wanted), _IN_CHUNK):
            end = start + _IN_CHUNK
            chunk = wanted[start:end]
            q = ",".join("?" * len(chunk))
            for t, d in con.execute(
                f"SELECT ticker, MIN(date) FROM {TABLE} "
                f"WHERE ticker IN ({q}) GROUP BY ticker",
                chunk,
            ):
                out[t] = d
        return out
    finally:
        con.close()


def stored_day_counts(
    tickers: Iterable[str], *, db_path: Optional[Path] = None
) -> dict[str, int]:
    """`{ticker: 이 계열에 저장된 거래일 수}`. **값을 쓰지 않는다.**

    POC3-02D-OPS-01 R2 Q23 — pending 이 d20 종가를 얻기까지 남은 거래일
    (`21 - 수`)을 셀 때 쓴다. 적재 기록이 없는 ticker 는 담지 않는다.
    """
    wanted = sorted(set(tickers))
    if not wanted:
        return {}
    init_db(db_path)
    con = _connect(db_path)
    try:
        out: dict[str, int] = {}
        for start in range(0, len(wanted), _IN_CHUNK):
            end = start + _IN_CHUNK
            chunk = wanted[start:end]
            q = ",".join("?" * len(chunk))
            for t, n in con.execute(
                f"SELECT ticker, COUNT(*) FROM {TABLE} "
                f"WHERE ticker IN ({q}) GROUP BY ticker",
                chunk,
            ):
                out[t] = int(n)
        return out
    finally:
        con.close()


def read_holdings_etf_prices(
    tickers: Iterable[str],
    dates: Sequence[str] = (),
    *,
    db_path: Optional[Path] = None,
) -> tuple[set[str], dict[str, dict[str, float]]]:
    """보유 PUSH ETF 가격 증거 전용 읽기 (설계자 RESULT STEP 1 · 2026-09-30).

    반환 `(이 계열에 적재 기록이 있는 ticker, {ticker: {date: close}})`. 종가는
    `dates` 에 든 날짜만 담는다. **읽기 전용으로 연다** — 테이블을 만들지 않는다.
    DB · 테이블이 없으면 `sqlite3.Error` 를 그대로 올린다. 호출자가 '읽을 수
    없음' 으로 fail-closed 한다(없는 표를 '적재 기록 없음' 으로 읽지 않는다).
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
        for start in range(0, len(wanted), _IN_CHUNK):
            end = start + _IN_CHUNK
            chunk = wanted[start:end]
            q = ",".join("?" * len(chunk))
            for (t,) in con.execute(
                f"SELECT DISTINCT ticker FROM {TABLE} WHERE ticker IN ({q})", chunk
            ):
                present.add(t)
            if not days:
                continue
            dq = ",".join("?" * len(days))
            for t, d, c in con.execute(
                f"SELECT ticker, date, close FROM {TABLE} WHERE ticker IN ({q}) "
                f"AND date IN ({dq}) AND close > 0",
                [*chunk, *days],
            ):
                closes.setdefault(t, {})[d] = float(c)
        return present, closes
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


# ── POC3-02D-OPS-03 — 목표일 적재 보조 · 거래일 날짜 창 ────────────────────────


def row_count_on(date: str, *, db_path: Optional[Path] = None) -> int:
    """`date` 에 저장된 행 수. 적재 뒤 read-back(확정 계약 3 ⑤)에 쓴다."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        (n,) = con.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE date=?", (date,)
        ).fetchone()
        return int(n)
    finally:
        con.close()


def baseline_row_count(
    date: str, *, db_path: Optional[Path] = None
) -> tuple[Optional[str], Optional[int]]:
    """`date` 의 **직전 정상 적재**(앞선 최신 저장일)와 그 행 수(확정 계약 3 ③).

    저장된 날은 모두 검사를 통과한 전종목 snapshot 이다. 앞선 날이 없으면(빠진
    날 채우기에서 창 맨 앞) 뒤로 가장 가까운 저장일을 쓴다. 둘 다 없으면
    `(None, None)` — 비교 대상이 없다.
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        row = con.execute(
            f"SELECT date, COUNT(*) FROM {TABLE} WHERE date < ? "
            f"GROUP BY date ORDER BY date DESC LIMIT 1",
            (date,),
        ).fetchone()
        if row is None:
            row = con.execute(
                f"SELECT date, COUNT(*) FROM {TABLE} WHERE date > ? "
                f"GROUP BY date ORDER BY date ASC LIMIT 1",
                (date,),
            ).fetchone()
        return (row[0], int(row[1])) if row else (None, None)
    finally:
        con.close()


def rows_on(date: str, *, db_path: Optional[Path] = None) -> dict[str, float]:
    """`date` 에 저장된 `{ticker: close}`. 적재 뒤 read-back(확정 계약 3 ⑤)에 쓴다."""
    init_db(db_path)
    con = _connect(db_path)
    try:
        return {
            t: float(c)
            for t, c in con.execute(
                f"SELECT ticker, close FROM {TABLE} WHERE date=?", (date,)
            )
        }
    finally:
        con.close()


def replace_date(rows: Iterable[SnapshotRow], *, db_path: Optional[Path] = None) -> int:
    """같은 날짜 저장분을 **한 트랜잭션에서** 지우고 검사를 통과한 `rows` 로 다시 쓴다.

    판정 전 중단 등으로 남은 부분 · 다른 저장분을 이번 snapshot 과 같게 맞출 때만 쓴다
    (검증자 r1 A-1). 판정까지 끝난 T-1 은 호출자가 다시 받지 않는다(already_loaded).
    """
    rows = list(rows)
    if not rows:
        return 0
    init_db(db_path)
    now = _utcnow()
    con = _connect(db_path)
    try:
        with con:
            con.execute(f"DELETE FROM {TABLE} WHERE date=?", (rows[0].date,))
            con.executemany(
                f"INSERT INTO {TABLE} (date, ticker, close, source, price_basis, "
                f"collected_at) VALUES (?, ?, ?, ?, ?, ?)",
                [(r.date, r.ticker, r.close, SOURCE, PRICE_BASIS, now) for r in rows],
            )
    finally:
        con.close()
    return len(rows)


def delete_date(date: str, *, db_path: Optional[Path] = None) -> int:
    """`date` 행을 지운다. 이 날짜를 쓴(또는 바꿔 쓴) 호출의 read-back 이 어긋났을 때만
    쓴다 — 부분 snapshot 을 남기지 않기 위해서다(fail-closed · 그 날짜는 비어 실패로 남는다).
    """
    init_db(db_path)
    con = _connect(db_path)
    try:
        cur = con.execute(f"DELETE FROM {TABLE} WHERE date=?", (date,))
        con.commit()
        return int(cur.rowcount or 0)
    finally:
        con.close()


@dataclass(frozen=True)
class CalendarWindow:
    """거래일 날짜로 정한 창(확정 계약 5). 저장 행 위치로 밀리지 않는다.

    `missing_days` — 창(21거래일) 안에서 저장되지 않은 날. 계산에 쓰는 세 날짜
    (`latest` · `d5` · `d20`) 가운데 하나라도 없으면 `usable=False` — 호출부가
    fail-closed 한다(6 · 21거래일 전 값으로 대신하지 않는다).

    연도 파일이 없는 해는 저장 자료가 없는 평일을 휴장으로 건너뛰어 날짜를 정한다
    (`trading_day_lag` `stored` · 한국 거래일 계약 2026-09-11 · 창을 닫지 않는다).
    """

    latest: str
    d5: Optional[str]
    d20: Optional[str]
    window_days: tuple[str, ...]
    missing_days: tuple[str, ...]

    @property
    def missing_required(self) -> tuple[str, ...]:
        need = (self.latest, self.d5, self.d20)
        return tuple(d for d in need if d is None or d in self.missing_days)

    @property
    def usable(self) -> bool:
        return (
            self.d5 is not None and self.d20 is not None and not self.missing_required
        )

    def price_window(self) -> Optional[PriceWindow]:
        """세 날짜가 정해졌으면 `PriceWindow`. 저장 여부는 보지 않는다."""
        if self.d5 is None or self.d20 is None:
            return None
        return PriceWindow(latest=self.latest, d5=self.d5, d20=self.d20)

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest": self.latest,
            "d5": self.d5,
            "d20": self.d20,
            "window_day_count": len(self.window_days),
            "missing_days": list(self.missing_days),
            "missing_required": [d for d in self.missing_required if d],
            "usable": self.usable,
        }


def resolve_calendar_window(
    latest: str,
    *,
    calendar_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> CalendarWindow:
    """`latest`(보통 기대 T-1)에서 거래일 캘린더로 d5 · d20 과 21거래일 창을 정한다.

    `resolve_window` 는 저장 행 순서로 날짜를 고른다 — 하루가 빠지면 5 · 20일이
    6 · 21일이 된다. 이 함수는 날짜를 캘린더로 정하고 **저장 여부만** 본다.
    """
    from app import trading_day_lag

    stored = set(stored_trading_days(db_path=db_path))
    dates = trading_day_lag.trading_window_dates(
        latest,
        calendar_dir=calendar_dir,
        lookbacks=(LOOKBACK_5D, LOOKBACK_20D),
        stored=stored,
    )
    d5, d20 = (dates[1], dates[2]) if dates else (None, None)
    days = tuple(
        trading_day_lag.trading_days_ending(
            latest, REQUIRED_TRADING_DAYS, calendar_dir=calendar_dir, stored=stored
        )
    )
    return CalendarWindow(
        latest=latest,
        d5=d5,
        d20=d20,
        window_days=days,
        missing_days=tuple(d for d in days if d not in stored),
    )


__all__ = [
    "LOOKBACK_20D",
    "LOOKBACK_5D",
    "PRICE_BASIS",
    "CalendarWindow",
    "PriceWindow",
    "REQUIRED_TRADING_DAYS",
    "SOURCE",
    "TABLE",
    "KrxSnapshotError",
    "SnapshotRow",
    "baseline_row_count",
    "closes_on",
    "delete_date",
    "first_loaded_dates",
    "init_db",
    "read_holdings_etf_prices",
    "replace_date",
    "resolve_calendar_window",
    "resolve_window",
    "row_count_on",
    "rows_on",
    "stored_day_counts",
    "stored_trading_days",
    "upsert_snapshot",
    "validate_snapshot",
]
