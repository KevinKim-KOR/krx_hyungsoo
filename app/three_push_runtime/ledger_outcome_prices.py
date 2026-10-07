"""POC5-02 — 가격 결과 성숙의 읽기 전용 입력: 가격 표 3 · 운영 거래일 캘린더 · 보유 목록.

PLAN `docs/ai_plan/POC5/POC5-02_PRICE_OUTCOME_MATURITY_PLAN_V1.md` §1-2 · §2-3 · §8.

```text
계열        krx_etf   = krx_etf_daily_price_unadjusted   (ETF · 사업군 대표 · 기초지수 ticker)
            krx_stock = krx_stock_daily_price_unadjusted (KRX 코스피 보유 개별주 · OPS-04)
            benchmark = market_benchmark_daily_price · benchmark_id='KOSPI'
읽기        시장 DB 를 `mode=ro` 로만 연다(표를 만들지 않는다 · FDR 표를 읽지 않는다 · 외부 조회 0)
날짜        +n 은 운영 거래일 캘린더만(연도 CSV · 없으면 평일 fallback) — 가격표 행으로 휴장을
            추론하지 않는다(설계자 Q-C 정정 · 적재 상태가 바뀌어도 평가일 불변)
채우기 창    ETF 21 · 개별주 31 거래일(T-1 로 끝남) — 그 안의 빠진 날은 아직 채워질 수 있다
```
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

from app import market_data_store, trading_day_lag
from app.market_benchmark_store import KOSPI_ID
from app.market_briefing.krx_stock_sync import WINDOW_TRADING_DAYS as STOCK_WINDOW
from app.market_briefing.krx_store import REQUIRED_TRADING_DAYS as ETF_WINDOW

SERIES_ETF = "krx_etf"
SERIES_STOCK = "krx_stock"
SERIES_KOSPI = "benchmark"

_TABLE = {
    SERIES_ETF: "krx_etf_daily_price_unadjusted",
    SERIES_STOCK: "krx_stock_daily_price_unadjusted",
}
PRICE_BASIS = {
    SERIES_ETF: "KRX_ETF_UNADJUSTED",
    SERIES_STOCK: "KRX_STOCK_UNADJUSTED",
    SERIES_KOSPI: "KRX_KOSPI_INDEX",
}
FILL_WINDOW = {SERIES_ETF: ETF_WINDOW, SERIES_STOCK: STOCK_WINDOW}
_WALK_LIMIT_DAYS = 120  # 20거래일 + 긴 연휴를 넉넉히 넘는다


def market_db_path() -> Path:
    """운영 시장 DB(호출 때 읽는다 · 테스트는 tmp 로 바꾼다)."""
    return Path(market_data_store.DEFAULT_DB_PATH)


def open_ro(path: Optional[Path] = None) -> sqlite3.Connection:
    p = Path(path) if path is not None else market_db_path()
    if not p.exists():
        raise FileNotFoundError(p.name)
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5.0)


class PriceReader:
    """한 성숙 실행 동안 쓰는 읽기 전용 조회. 같은 질의는 한 번만 읽는다."""

    def __init__(self, con: sqlite3.Connection) -> None:
        self.con = con
        self._latest: dict[tuple[str, Optional[str]], Optional[str]] = {}

    def _where(self, series: str, ident: str) -> tuple[str, str, tuple[Any, ...]]:
        if series == SERIES_KOSPI:
            return (
                "market_benchmark_daily_price",
                "benchmark_id = ? AND close IS NOT NULL",
                (KOSPI_ID,),
            )
        return _TABLE[series], "ticker = ?", (ident,)

    def _stamp_col(self, series: str) -> str:
        return "created_at" if series == SERIES_KOSPI else "collected_at"

    def closes(
        self, series: str, ident: str, dates: Sequence[str]
    ) -> dict[str, tuple[float, Optional[str]]]:
        """`{date: (종가, 수집 시각)}` — 저장된 날만."""
        if not dates:
            return {}
        table, cond, args = self._where(series, ident)
        marks = ", ".join("?" for _ in dates)
        rows = self.con.execute(
            f"SELECT date, close, {self._stamp_col(series)} FROM {table}"
            f" WHERE {cond} AND date IN ({marks})",
            (*args, *dates),
        ).fetchall()
        return {r[0]: (float(r[1]), r[2]) for r in rows if r[1] is not None}

    def last_before(
        self, series: str, ident: str, day: str
    ) -> Optional[tuple[str, float]]:
        """`day` **이전** 마지막 저장 종가(날짜 · 종가)."""
        table, cond, args = self._where(series, ident)
        row = self.con.execute(
            f"SELECT date, close FROM {table} WHERE {cond} AND date < ?"
            " ORDER BY date DESC LIMIT 1",
            (*args, day),
        ).fetchone()
        return (row[0], float(row[1])) if row and row[1] is not None else None

    def latest_date(self, series: str, ident: Optional[str] = None) -> Optional[str]:
        """그 계열(또는 그 종목)의 마지막 저장 날짜."""
        key = (series, ident)
        if key not in self._latest:
            if series == SERIES_KOSPI or ident is not None:
                table, cond, args = self._where(series, ident or "")
                row = self.con.execute(
                    f"SELECT MAX(date) FROM {table} WHERE {cond}", args
                ).fetchone()
            else:
                row = self.con.execute(
                    f"SELECT MAX(date) FROM {_TABLE[series]}"
                ).fetchone()
            self._latest[key] = row[0] if row else None
        return self._latest[key]


# ── 운영 거래일 캘린더(가격표를 보지 않는다) ────────────────────────────────────


class Calendar:
    """한 성숙 실행의 거래일 판정 — 캘린더 파일을 **한 번만** 읽는다(대상마다 다시 읽지 않음).

    규칙은 운영과 같다(`trading_day_lag._trading_day_test` · 연도 CSV · 없으면 평일 fallback ·
    저장 자료로 휴장을 추론하지 않음 · 설계자 Q-C 정정).
    """

    def __init__(self, calendar_dir: Optional[Path]) -> None:
        self._test = trading_day_lag._trading_day_test(calendar_dir)
        self._memo: dict[str, bool] = {}
        self._fill: dict[tuple[str, str], Optional[str]] = {}

    def is_trading(self, day: str) -> bool:
        if day not in self._memo:
            try:
                self._memo[day] = bool(self._test(date.fromisoformat(day)))
            except ValueError:
                self._memo[day] = False
        return self._memo[day]

    def days_from(self, start: str, count: int) -> list[str]:
        """`start` **이상** 거래일 `count` 개(오름차순)."""
        try:
            d = date.fromisoformat(start)
        except ValueError:
            return []
        out: list[str] = []
        for _ in range(_WALK_LIMIT_DAYS):
            if self.is_trading(d.isoformat()):
                out.append(d.isoformat())
                if len(out) == count:
                    break
            d += timedelta(days=1)
        return out

    def _walk_back(self, day: str, count: int) -> list[str]:
        """`day` **미만** 거래일 `count` 개(내림차순)."""
        try:
            d = date.fromisoformat(day)
        except ValueError:
            return []
        out: list[str] = []
        for _ in range(_WALK_LIMIT_DAYS):
            d -= timedelta(days=1)
            if self.is_trading(d.isoformat()):
                out.append(d.isoformat())
                if len(out) == count:
                    break
        return out

    def next_after(self, day: str) -> Optional[str]:
        try:
            nxt = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        except ValueError:
            return None
        got = self.days_from(nxt, 1)
        return got[0] if got else None

    def previous(self, day: str) -> Optional[str]:
        got = self._walk_back(day, 1)
        return got[0] if got else None

    def fill_start(self, series: str, today_kst: str) -> Optional[str]:
        """오늘 배치의 채우기 창 첫날(T-1 로 끝나는 창) — 이보다 앞선 빠진 날은 다시 채워지지 않는다."""
        key = (series, today_kst)
        if key not in self._fill:
            back = self._walk_back(today_kst, FILL_WINDOW[series])
            self._fill[key] = back[-1] if len(back) == FILL_WINDOW[series] else None
        return self._fill[key]


# ── 보유 · 자산 구분(바꿔 끼울 수 있게 모듈 이름으로 둔다) ───────────────────────


def load_holdings() -> list[Any]:
    """보유 ticker — 파일 없음 · 손상이면 예외(모름) · 보유 0 이면 [](개별주 곁 작업과 같은 구분)."""
    from app.market_briefing.krx_stock_sync import STATUS_NO_HOLDINGS, holdings_tickers

    tickers, reason = holdings_tickers()
    if tickers is None and reason != STATUS_NO_HOLDINGS:
        raise LookupError(reason or "holdings_unknown")
    return [{"ticker": t} for t in tickers or []]


def current_holdings(
    loader: Optional[Callable[[], Iterable[Any]]] = None,
) -> Optional[set[str]]:
    """지금 보유 ticker. 못 읽으면 None — 매도 여부를 정하지 않는다."""
    try:
        rows = (loader or load_holdings)()
    except Exception:  # noqa: BLE001 - 보유를 모르면 미추적 판정을 미룬다
        return None
    out: set[str] = set()
    for h in rows:
        t = getattr(h, "ticker", None)
        if t is None and isinstance(h, dict):
            t = h.get("ticker")
        if t:
            out.add(str(t))
    return out


def classify(
    tickers: Sequence[str], *, db_path: Optional[Path] = None
) -> dict[str, tuple[str, Optional[str]]]:
    """기존 `holdings_price_basis.classify_assets`(로컬 CSV · KRX ETF 표만 · 외부 0)."""
    from app.runtime_evidence import holdings_price_basis as hpb

    kinds, _ = hpb.classify_assets(
        list(tickers), hpb.default_source(db_path=db_path or market_db_path())
    )
    return kinds


__all__ = [
    "Calendar",
    "FILL_WINDOW",
    "PRICE_BASIS",
    "PriceReader",
    "SERIES_ETF",
    "SERIES_KOSPI",
    "SERIES_STOCK",
    "classify",
    "current_holdings",
    "load_holdings",
    "market_db_path",
    "open_ro",
]
