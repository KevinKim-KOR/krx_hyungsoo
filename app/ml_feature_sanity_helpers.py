"""ML Feature Sanity — SQLite read helpers + 재계산 helper (POC2 2026-06-08).

지시문 §4.4 — sanity check 의 sample ticker 선택 / ML row fetch / primitives
재계산 / sample row 추출을 분리해 ml_feature_sanity.py 단일 책임 누적 회피
(KS-10 near 진입 회피).

본 모듈은 SQLite read-only + primitives 호출만. 외부 source 호출 X.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from app.market_regime import KODEX200_TICKER
from app.ml_feature_primitives import (
    WINDOW_5,
    WINDOW_10,
    WINDOW_20,
    PriceSeries,
    drawdown_20d,
    excess_vs_kodex200,
    return_pct,
    volatility_20d,
    volume_ratio_20d,
)


def pick_sample_tickers(db_path: Path, latest_asof: str, n: int) -> list[str]:
    """KODEX 200 + 거래량 top n-1 ticker 반환 (latest asof 기준)."""
    tickers: list[str] = [KODEX200_TICKER]
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT ticker FROM etf_ml_feature_daily "
            "WHERE asof = ? AND volume IS NOT NULL "
            "ORDER BY volume DESC LIMIT ?",
            (latest_asof, n * 2),
        )
        for r in cur.fetchall():
            tk = str(r[0])
            if tk not in tickers:
                tickers.append(tk)
                if len(tickers) >= n:
                    break
    return tickers[:n]


_ML_ROW_COLS = [
    "name",
    "close_price",
    "volume",
    "return_5d",
    "return_10d",
    "return_20d",
    "excess_return_5d_vs_kodex200",
    "excess_return_10d_vs_kodex200",
    "excess_return_20d_vs_kodex200",
    "volatility_20d",
    "drawdown_20d",
    "volume_ratio_20d",
    "nav",
    "nav_market_price",
    "nav_discount_rate_pct",
    "nav_status",
    "source_flags",
]


def fetch_ml_row(db_path: Path, ticker: str, asof: str) -> Optional[dict[str, Any]]:
    select_clause = ", ".join(_ML_ROW_COLS)
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            f"SELECT {select_clause} FROM etf_ml_feature_daily "
            "WHERE ticker = ? AND asof = ?",
            (ticker, asof),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(_ML_ROW_COLS, row))


def recompute_features_for_sample(
    series: PriceSeries,
    idx: int,
    kodex_returns: dict[str, Optional[float]],
) -> dict[str, Optional[float]]:
    """primitives 로 sample ticker × latest asof 1건의 feature 재계산."""
    r5 = return_pct(series, idx, WINDOW_5)
    r10 = return_pct(series, idx, WINDOW_10)
    r20 = return_pct(series, idx, WINDOW_20)
    return {
        "return_5d": r5,
        "return_10d": r10,
        "return_20d": r20,
        "excess_return_5d_vs_kodex200": excess_vs_kodex200(r5, kodex_returns.get("r5")),
        "excess_return_10d_vs_kodex200": excess_vs_kodex200(
            r10, kodex_returns.get("r10")
        ),
        "excess_return_20d_vs_kodex200": excess_vs_kodex200(
            r20, kodex_returns.get("r20")
        ),
        "volatility_20d": volatility_20d(series, idx),
        "drawdown_20d": drawdown_20d(series, idx),
        "volume_ratio_20d": volume_ratio_20d(series, idx),
    }


_SAMPLE_ROW_FIELDS = [
    "return_5d",
    "return_10d",
    "return_20d",
    "excess_return_5d_vs_kodex200",
    "excess_return_20d_vs_kodex200",
    "volatility_20d",
    "drawdown_20d",
    "volume_ratio_20d",
    "nav_discount_rate_pct",
    "nav_status",
]


def fetch_sample_rows(
    db_path: Path, tickers: list[str], asof: str
) -> list[dict[str, Any]]:
    """Data Status 표시용 sample row — name + asof + 주요 필드만."""
    out: list[dict[str, Any]] = []
    for tk in tickers:
        ml = fetch_ml_row(db_path, tk, asof)
        if ml is None:
            continue
        row: dict[str, Any] = {
            "ticker": tk,
            "name": ml.get("name"),
            "asof": asof,
        }
        for fld in _SAMPLE_ROW_FIELDS:
            row[fld] = ml.get(fld)
        out.append(row)
    return out
