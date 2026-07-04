"""Market Risk Reference v1 — KODEX200 + VIX 일별 맥락 evidence.

지시문 §6 계산 계약:
- KODEX200: etf_daily_price 의 069500 사용.
- VIX: market_benchmark_daily_price 의 VIX 사용.
- change_1d_pct: 최근 거래일 대비 직전 관측일 변화율.
- change_5d_pct (VIX 만): 최근 대비 5거래일 전 관측 변화율.
- 5거래일 전 값 부재 시 null (0/직전/보간 채움 금지).
- 상태: available / unavailable 만.

지시문 §9 ML 경계:
- VIX 는 ML feature / 판단 라벨에 사용하지 않는다.
- 본 모듈은 Market Discovery 시장 요약 응답 확장 전용.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.market_data_store import DEFAULT_DB_PATH

BENCHMARK_VIX_ID = "VIX"
BENCHMARK_KODEX200_TICKER = "069500"

RECENT_SERIES_LIMIT = 20  # 지시문 §8.2 상세: 최근 20거래일.


@dataclass
class RecentPoint:
    date: str
    close: float


@dataclass
class KodexRiskCard:
    availability: str  # available / unavailable
    as_of_date: Optional[str] = None
    close: Optional[float] = None
    change_1d_pct: Optional[float] = None
    recent_20d_series: Optional[list[RecentPoint]] = None
    # 지시문 §8.2 상세 — 각 시계열 최초·최종 관측일 (전체 저장 범위, 최근 20건 아님).
    series_first_date: Optional[str] = None
    series_last_date: Optional[str] = None


@dataclass
class VixRiskCard:
    availability: str
    as_of_date: Optional[str] = None
    close: Optional[float] = None
    change_1d_pct: Optional[float] = None
    change_5d_pct: Optional[float] = None
    recent_20d_series: Optional[list[RecentPoint]] = None
    series_first_date: Optional[str] = None
    series_last_date: Optional[str] = None


@dataclass
class MarketRiskReferenceEvidence:
    kodex200: KodexRiskCard
    vix: VixRiskCard


def _fetch_recent_closes_etf(
    ticker: str, *, limit: int, db_path: Path
) -> list[tuple[str, float]]:
    """etf_daily_price 의 (date, close) 를 최근순 limit 개. close>0 만."""
    if not db_path.exists():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT date, close FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date DESC LIMIT ?",
            (ticker, limit),
        )
        rows = cur.fetchall()
    finally:
        con.close()
    return [(str(r[0]), float(r[1])) for r in rows]


def _fetch_recent_closes_benchmark(
    benchmark_id: str, *, limit: int, db_path: Path
) -> list[tuple[str, float]]:
    """market_benchmark_daily_price 의 (date, close) 최근순 limit 개. close>0 만.

    market_benchmark_daily_price 는 market_benchmark_store.init_benchmark_db 로
    생성되며 init_db 에 포함되지 않는다. 없으면 빈 리스트 반환 (unavailable).
    """
    if not db_path.exists():
        return []
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = 'market_benchmark_daily_price'"
        )
        if cur.fetchone() is None:
            return []
        cur = con.execute(
            "SELECT date, close FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0 "
            "ORDER BY date DESC LIMIT ?",
            (benchmark_id, limit),
        )
        rows = cur.fetchall()
    finally:
        con.close()
    return [(str(r[0]), float(r[1])) for r in rows]


def _fetch_series_bounds_etf(
    ticker: str, *, db_path: Path
) -> tuple[Optional[str], Optional[str]]:
    """etf_daily_price 의 (min date, max date). close>0 만."""
    if not db_path.exists():
        return None, None
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT MIN(date), MAX(date) FROM etf_daily_price "
            "WHERE ticker = ? AND close IS NOT NULL AND close > 0",
            (ticker,),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if not row or row[0] is None:
        return None, None
    return str(row[0]), str(row[1])


def _fetch_series_bounds_benchmark(
    benchmark_id: str, *, db_path: Path
) -> tuple[Optional[str], Optional[str]]:
    """market_benchmark_daily_price 의 (min date, max date). 테이블 부재 시 (None, None)."""
    if not db_path.exists():
        return None, None
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = 'market_benchmark_daily_price'"
        )
        if cur.fetchone() is None:
            return None, None
        cur = con.execute(
            "SELECT MIN(date), MAX(date) FROM market_benchmark_daily_price "
            "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0",
            (benchmark_id,),
        )
        row = cur.fetchone()
    finally:
        con.close()
    if not row or row[0] is None:
        return None, None
    return str(row[0]), str(row[1])


def _pct_change(current: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior <= 0:
        return None
    return (current / prior - 1.0) * 100.0


def _build_kodex_card(
    db_path: Path = DEFAULT_DB_PATH,
) -> KodexRiskCard:
    rows_desc = _fetch_recent_closes_etf(
        BENCHMARK_KODEX200_TICKER, limit=RECENT_SERIES_LIMIT, db_path=db_path
    )
    first_date, last_date = _fetch_series_bounds_etf(
        BENCHMARK_KODEX200_TICKER, db_path=db_path
    )
    if not rows_desc:
        return KodexRiskCard(
            availability="unavailable",
            recent_20d_series=[],
            series_first_date=first_date,
            series_last_date=last_date,
        )
    latest_date, latest_close = rows_desc[0]
    prior_close = rows_desc[1][1] if len(rows_desc) >= 2 else None
    change_1d = _pct_change(latest_close, prior_close)
    series_asc = list(reversed(rows_desc))
    return KodexRiskCard(
        availability="available",
        as_of_date=latest_date,
        close=latest_close,
        change_1d_pct=change_1d,
        recent_20d_series=[RecentPoint(date=d, close=c) for d, c in series_asc],
        series_first_date=first_date,
        series_last_date=last_date,
    )


def _build_vix_card(
    db_path: Path = DEFAULT_DB_PATH,
) -> VixRiskCard:
    rows_desc = _fetch_recent_closes_benchmark(
        BENCHMARK_VIX_ID, limit=RECENT_SERIES_LIMIT, db_path=db_path
    )
    first_date, last_date = _fetch_series_bounds_benchmark(
        BENCHMARK_VIX_ID, db_path=db_path
    )
    if not rows_desc:
        return VixRiskCard(
            availability="unavailable",
            recent_20d_series=[],
            series_first_date=first_date,
            series_last_date=last_date,
        )
    latest_date, latest_close = rows_desc[0]
    prior_close = rows_desc[1][1] if len(rows_desc) >= 2 else None
    # change_5d_pct — 최근 대비 5거래일 전 (인덱스 5).
    five_close = rows_desc[5][1] if len(rows_desc) >= 6 else None
    change_1d = _pct_change(latest_close, prior_close)
    change_5d = _pct_change(latest_close, five_close)
    series_asc = list(reversed(rows_desc))
    return VixRiskCard(
        availability="available",
        as_of_date=latest_date,
        close=latest_close,
        change_1d_pct=change_1d,
        change_5d_pct=change_5d,
        recent_20d_series=[RecentPoint(date=d, close=c) for d, c in series_asc],
        series_first_date=first_date,
        series_last_date=last_date,
    )


def build_market_risk_reference(
    db_path: Path = DEFAULT_DB_PATH,
) -> MarketRiskReferenceEvidence:
    """SQLite 만 read 하여 KODEX200 + VIX evidence 생성. 외부 호출 X."""
    return MarketRiskReferenceEvidence(
        kodex200=_build_kodex_card(db_path=db_path),
        vix=_build_vix_card(db_path=db_path),
    )
