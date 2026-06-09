"""ML 최소 데이터 레인 — SQLite 저장소 (POC2 2026-06-08).

지시문 §6.1 / §6.2 — etf_ml_feature_daily + market_risk_feature_daily 두
테이블만 관리. ML 모델 학습 / 라벨 / 예측 X — feature row 만 적재.

저장 위치: state/market/market_data.sqlite (기존 시장 데이터 DB 와 동일 파일).

본 store 는 schema + upsert + 간단한 조회만. feature 계산은 ml_feature_builder
가, CLI 실행은 scripts/generate_ml_features.py 가 담당.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from app.market_data_store import DEFAULT_DB_PATH

ETF_ML_FEATURE_DAILY_DDL = """
CREATE TABLE IF NOT EXISTS etf_ml_feature_daily (
    asof                              TEXT NOT NULL,
    ticker                            TEXT NOT NULL,
    name                              TEXT,
    close_price                       REAL,
    volume                            INTEGER,
    return_5d                         REAL,
    return_10d                        REAL,
    return_20d                        REAL,
    excess_return_5d_vs_kodex200      REAL,
    excess_return_10d_vs_kodex200     REAL,
    excess_return_20d_vs_kodex200     REAL,
    volatility_20d                    REAL,
    drawdown_20d                      REAL,
    volume_ratio_20d                  REAL,
    nav                               REAL,
    nav_market_price                  REAL,
    nav_discount_rate_pct             REAL,
    nav_status                        TEXT,
    source_flags                      TEXT,
    created_at                        TEXT NOT NULL,
    PRIMARY KEY (asof, ticker)
);
""".strip()


MARKET_RISK_FEATURE_DAILY_DDL = """
CREATE TABLE IF NOT EXISTS market_risk_feature_daily (
    asof                              TEXT PRIMARY KEY,
    kodex200_return_1d                REAL,
    kodex200_return_5d                REAL,
    kodex200_return_20d               REAL,
    kospi_return_1d                   REAL,
    kospi_return_5d                   REAL,
    kospi_return_20d                  REAL,
    etf_universe_up_count             INTEGER,
    etf_universe_down_count           INTEGER,
    etf_universe_flat_count           INTEGER,
    etf_universe_up_ratio             REAL,
    etf_universe_down_ratio           REAL,
    etf_universe_median_return_1d     REAL,
    etf_universe_median_return_5d     REAL,
    nav_discount_avg                  REAL,
    nav_discount_abs_avg              REAL,
    nav_discount_extreme_count        INTEGER,
    volatility_20d_market_proxy       REAL,
    drawdown_20d_market_proxy         REAL,
    distance_from_20d_high            REAL,
    volatility_expansion_20d          REAL,
    down_day_volume_ratio             REAL,
    large_negative_day_proxy          REAL,
    short_term_weakness_proxy         REAL,
    breadth_deterioration_proxy       REAL,
    created_at                        TEXT NOT NULL
);
""".strip()


# ─── init / connection ───────────────────────────────────────────────


_INITIALIZED_ML_DBS: set[str] = set()


def init_ml_feature_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as con:
        con.execute(ETF_ML_FEATURE_DAILY_DDL)
        con.execute(MARKET_RISK_FEATURE_DAILY_DDL)
        con.commit()


def _ensure_ml_initialized(db_path: Path) -> None:
    key = str(db_path.resolve())
    if key in _INITIALIZED_ML_DBS:
        return
    init_ml_feature_db(db_path)
    _INITIALIZED_ML_DBS.add(key)


@contextmanager
def _connection(db_path: Path):
    _ensure_ml_initialized(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── ETF feature row ─────────────────────────────────────────────────


@dataclass(frozen=True)
class EtfMlFeatureRow:
    asof: str
    ticker: str
    name: Optional[str]
    close_price: Optional[float]
    volume: Optional[int]
    return_5d: Optional[float]
    return_10d: Optional[float]
    return_20d: Optional[float]
    excess_return_5d_vs_kodex200: Optional[float]
    excess_return_10d_vs_kodex200: Optional[float]
    excess_return_20d_vs_kodex200: Optional[float]
    volatility_20d: Optional[float]
    drawdown_20d: Optional[float]
    volume_ratio_20d: Optional[float]
    nav: Optional[float]
    nav_market_price: Optional[float]
    nav_discount_rate_pct: Optional[float]
    nav_status: Optional[str]
    source_flags: Optional[str]


def upsert_etf_features(
    rows: Iterable[EtfMlFeatureRow],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    payload = list(rows)
    if not payload:
        return 0
    now = _utcnow_iso()
    items = [
        (
            r.asof,
            r.ticker,
            r.name,
            r.close_price,
            r.volume,
            r.return_5d,
            r.return_10d,
            r.return_20d,
            r.excess_return_5d_vs_kodex200,
            r.excess_return_10d_vs_kodex200,
            r.excess_return_20d_vs_kodex200,
            r.volatility_20d,
            r.drawdown_20d,
            r.volume_ratio_20d,
            r.nav,
            r.nav_market_price,
            r.nav_discount_rate_pct,
            r.nav_status,
            r.source_flags,
            now,
        )
        for r in payload
    ]
    sql = """
    INSERT INTO etf_ml_feature_daily (
        asof, ticker, name, close_price, volume,
        return_5d, return_10d, return_20d,
        excess_return_5d_vs_kodex200, excess_return_10d_vs_kodex200,
        excess_return_20d_vs_kodex200,
        volatility_20d, drawdown_20d, volume_ratio_20d,
        nav, nav_market_price, nav_discount_rate_pct, nav_status,
        source_flags, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(asof, ticker) DO UPDATE SET
        name=excluded.name,
        close_price=excluded.close_price,
        volume=excluded.volume,
        return_5d=excluded.return_5d,
        return_10d=excluded.return_10d,
        return_20d=excluded.return_20d,
        excess_return_5d_vs_kodex200=excluded.excess_return_5d_vs_kodex200,
        excess_return_10d_vs_kodex200=excluded.excess_return_10d_vs_kodex200,
        excess_return_20d_vs_kodex200=excluded.excess_return_20d_vs_kodex200,
        volatility_20d=excluded.volatility_20d,
        drawdown_20d=excluded.drawdown_20d,
        volume_ratio_20d=excluded.volume_ratio_20d,
        nav=excluded.nav,
        nav_market_price=excluded.nav_market_price,
        nav_discount_rate_pct=excluded.nav_discount_rate_pct,
        nav_status=excluded.nav_status,
        source_flags=excluded.source_flags,
        created_at=excluded.created_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, items)
    return len(items)


# ─── Market risk row ─────────────────────────────────────────────────


@dataclass(frozen=True)
class MarketRiskFeatureRow:
    asof: str
    kodex200_return_1d: Optional[float]
    kodex200_return_5d: Optional[float]
    kodex200_return_20d: Optional[float]
    kospi_return_1d: Optional[float]
    kospi_return_5d: Optional[float]
    kospi_return_20d: Optional[float]
    etf_universe_up_count: Optional[int]
    etf_universe_down_count: Optional[int]
    etf_universe_flat_count: Optional[int]
    etf_universe_up_ratio: Optional[float]
    etf_universe_down_ratio: Optional[float]
    etf_universe_median_return_1d: Optional[float]
    etf_universe_median_return_5d: Optional[float]
    nav_discount_avg: Optional[float]
    nav_discount_abs_avg: Optional[float]
    nav_discount_extreme_count: Optional[int]
    volatility_20d_market_proxy: Optional[float]
    drawdown_20d_market_proxy: Optional[float]
    distance_from_20d_high: Optional[float]
    volatility_expansion_20d: Optional[float]
    down_day_volume_ratio: Optional[float]
    large_negative_day_proxy: Optional[float]
    short_term_weakness_proxy: Optional[float]
    breadth_deterioration_proxy: Optional[float]


def upsert_market_risk_features(
    rows: Iterable[MarketRiskFeatureRow],
    *,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    payload = list(rows)
    if not payload:
        return 0
    now = _utcnow_iso()
    items = [
        (
            r.asof,
            r.kodex200_return_1d,
            r.kodex200_return_5d,
            r.kodex200_return_20d,
            r.kospi_return_1d,
            r.kospi_return_5d,
            r.kospi_return_20d,
            r.etf_universe_up_count,
            r.etf_universe_down_count,
            r.etf_universe_flat_count,
            r.etf_universe_up_ratio,
            r.etf_universe_down_ratio,
            r.etf_universe_median_return_1d,
            r.etf_universe_median_return_5d,
            r.nav_discount_avg,
            r.nav_discount_abs_avg,
            r.nav_discount_extreme_count,
            r.volatility_20d_market_proxy,
            r.drawdown_20d_market_proxy,
            r.distance_from_20d_high,
            r.volatility_expansion_20d,
            r.down_day_volume_ratio,
            r.large_negative_day_proxy,
            r.short_term_weakness_proxy,
            r.breadth_deterioration_proxy,
            now,
        )
        for r in payload
    ]
    sql = """
    INSERT INTO market_risk_feature_daily (
        asof,
        kodex200_return_1d, kodex200_return_5d, kodex200_return_20d,
        kospi_return_1d, kospi_return_5d, kospi_return_20d,
        etf_universe_up_count, etf_universe_down_count, etf_universe_flat_count,
        etf_universe_up_ratio, etf_universe_down_ratio,
        etf_universe_median_return_1d, etf_universe_median_return_5d,
        nav_discount_avg, nav_discount_abs_avg, nav_discount_extreme_count,
        volatility_20d_market_proxy, drawdown_20d_market_proxy,
        distance_from_20d_high, volatility_expansion_20d,
        down_day_volume_ratio, large_negative_day_proxy,
        short_term_weakness_proxy, breadth_deterioration_proxy,
        created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(asof) DO UPDATE SET
        kodex200_return_1d=excluded.kodex200_return_1d,
        kodex200_return_5d=excluded.kodex200_return_5d,
        kodex200_return_20d=excluded.kodex200_return_20d,
        kospi_return_1d=excluded.kospi_return_1d,
        kospi_return_5d=excluded.kospi_return_5d,
        kospi_return_20d=excluded.kospi_return_20d,
        etf_universe_up_count=excluded.etf_universe_up_count,
        etf_universe_down_count=excluded.etf_universe_down_count,
        etf_universe_flat_count=excluded.etf_universe_flat_count,
        etf_universe_up_ratio=excluded.etf_universe_up_ratio,
        etf_universe_down_ratio=excluded.etf_universe_down_ratio,
        etf_universe_median_return_1d=excluded.etf_universe_median_return_1d,
        etf_universe_median_return_5d=excluded.etf_universe_median_return_5d,
        nav_discount_avg=excluded.nav_discount_avg,
        nav_discount_abs_avg=excluded.nav_discount_abs_avg,
        nav_discount_extreme_count=excluded.nav_discount_extreme_count,
        volatility_20d_market_proxy=excluded.volatility_20d_market_proxy,
        drawdown_20d_market_proxy=excluded.drawdown_20d_market_proxy,
        distance_from_20d_high=excluded.distance_from_20d_high,
        volatility_expansion_20d=excluded.volatility_expansion_20d,
        down_day_volume_ratio=excluded.down_day_volume_ratio,
        large_negative_day_proxy=excluded.large_negative_day_proxy,
        short_term_weakness_proxy=excluded.short_term_weakness_proxy,
        breadth_deterioration_proxy=excluded.breadth_deterioration_proxy,
        created_at=excluded.created_at
    """
    with _connection(db_path) as con:
        con.executemany(sql, items)
    return len(items)


# ─── Readiness 조회 (read-only API 용) ───────────────────────────────


@dataclass(frozen=True)
class MlFeatureReadiness:
    etf_row_count: int
    etf_distinct_asof_count: int
    etf_latest_asof: Optional[str]
    market_risk_row_count: int
    market_risk_latest_asof: Optional[str]


def fetch_readiness(db_path: Path = DEFAULT_DB_PATH) -> MlFeatureReadiness:
    """API / 화면 readiness 표시용 — read-only.

    DB 가 없거나 테이블이 없으면 0 / None 반환 (silent fallback 아님 — 정상 초기 상태).
    """
    if not db_path.exists():
        return MlFeatureReadiness(0, 0, None, 0, None)
    with _connection(db_path) as con:
        cur = con.execute("SELECT COUNT(*) FROM etf_ml_feature_daily")
        etf_count = int(cur.fetchone()[0])
        cur = con.execute(
            "SELECT COUNT(DISTINCT asof), MAX(asof) FROM etf_ml_feature_daily"
        )
        row = cur.fetchone()
        etf_distinct_asof = int(row[0] or 0)
        etf_latest_asof = row[1]
        cur = con.execute("SELECT COUNT(*), MAX(asof) FROM market_risk_feature_daily")
        row = cur.fetchone()
        mkt_count = int(row[0] or 0)
        mkt_latest_asof = row[1]
    return MlFeatureReadiness(
        etf_row_count=etf_count,
        etf_distinct_asof_count=etf_distinct_asof,
        etf_latest_asof=etf_latest_asof,
        market_risk_row_count=mkt_count,
        market_risk_latest_asof=mkt_latest_asof,
    )


def reset_initialized_cache_for_tests() -> None:
    """테스트 전용 — process-level init 캐시 초기화."""
    _INITIALIZED_ML_DBS.clear()
