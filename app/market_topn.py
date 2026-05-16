"""SQLite 가격 데이터 기준 일간 / 1개월 / 3개월 TOP N 산출.

artifact 출력: state/market/etf_universe_topn_latest.json

N 값은 기본 10 — 파라미터로 변경 가능.
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_history,
    get_etf_name,
    init_db,
    list_etf_tickers,
    write_artifact_json,
)

DEFAULT_TOPN_PATH = Path("state/market/etf_universe_topn_latest.json")
DEFAULT_N = 10
DAILY_LOOKBACK_DAYS = 1
ONE_MONTH_LOOKBACK_DAYS = 30
THREE_MONTH_LOOKBACK_DAYS = 90


@dataclass
class TopNEntry:
    rank: int
    ticker: str
    name: Optional[str]
    return_pct: float
    basis_start_date: str
    basis_end_date: str

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "name": self.name,
            "return_pct": round(self.return_pct, 4),
            "basis_start_date": self.basis_start_date,
            "basis_end_date": self.basis_end_date,
        }


def _select_base_index(
    history: list[tuple[str, float]], asof_iso: str, lookback_days: int
) -> Optional[int]:
    """asof - lookback_days 이후 첫 거래일 인덱스. daily 는 직전 인덱스."""
    if len(history) < 2:
        return None
    if lookback_days == DAILY_LOOKBACK_DAYS:
        return len(history) - 2
    asof_d = date.fromisoformat(asof_iso)
    target = asof_d - timedelta(days=lookback_days)
    target_iso = target.isoformat()
    last_idx = len(history) - 1
    for i, (d, _close) in enumerate(history):
        if d >= target_iso:
            if i == last_idx:
                return None
            return i
    return None


def _compute_return_pct(
    history: list[tuple[str, float]],
    asof_iso: str,
    lookback_days: int,
) -> Optional[tuple[float, str]]:
    """(return_pct, base_date) 또는 None (계산 불가)."""
    base_idx = _select_base_index(history, asof_iso, lookback_days)
    if base_idx is None:
        return None
    base_date, base_close = history[base_idx]
    _latest_date, latest_close = history[-1]
    if base_close <= 0 or latest_close <= 0:
        return None
    return ((latest_close / base_close) - 1.0) * 100.0, base_date


def _latest_date_in_db(db_path: Path) -> Optional[str]:
    init_db(db_path)
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute("SELECT MAX(date) FROM etf_daily_price")
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def compute_topn(
    *,
    n: int = DEFAULT_N,
    db_path: Path = DEFAULT_DB_PATH,
    asof: Optional[str] = None,
) -> dict:
    """SQLite etf_daily_price 기준 일간 / 1개월 / 3개월 TOP N 산출.

    asof 미지정 시 etf_daily_price 의 가장 최근 date 사용.
    각 ticker 의 시계열에서 직전/30일 이전/90일 이전 base close 와 비교.
    """
    t0 = time.perf_counter()
    asof_iso = asof or _latest_date_in_db(db_path)
    if not asof_iso:
        return {
            "asof": None,
            "source": "FinanceDataReader",
            "n": n,
            "universe_count": 0,
            "price_success_count": 0,
            "price_fail_count": 0,
            "runtime_seconds": round(time.perf_counter() - t0, 3),
            "daily_topn": [],
            "one_month_topn": [],
            "three_month_topn": [],
            "topn_caveat": (
                "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능. "
                "asof 결정에 필요한 가격 데이터가 SQLite 에 없어 빈 결과."
            ),
        }

    tickers = list_etf_tickers(db_path)
    universe_count = len(tickers)
    price_success = 0
    price_fail = 0

    period_specs = [
        ("daily", DAILY_LOOKBACK_DAYS),
        ("one_month", ONE_MONTH_LOOKBACK_DAYS),
        ("three_month", THREE_MONTH_LOOKBACK_DAYS),
    ]
    buckets: dict[str, list[tuple[str, float, str]]] = {
        label: [] for label, _ in period_specs
    }

    for tk in tickers:
        history = fetch_price_history(tk, db_path=db_path)
        if not history:
            price_fail += 1
            continue
        price_success += 1
        for label, lookback in period_specs:
            r = _compute_return_pct(history, asof_iso, lookback)
            if r is None:
                continue
            ret_pct, base_date = r
            buckets[label].append((tk, ret_pct, base_date))

    def _topn(items: list[tuple[str, float, str]]) -> list[dict]:
        items.sort(key=lambda x: x[1], reverse=True)
        out: list[dict] = []
        for rank, (tk, ret_pct, base_date) in enumerate(items[:n], start=1):
            out.append(
                TopNEntry(
                    rank=rank,
                    ticker=tk,
                    name=get_etf_name(tk, db_path=db_path),
                    return_pct=ret_pct,
                    basis_start_date=base_date,
                    basis_end_date=asof_iso,
                ).to_dict()
            )
        return out

    elapsed = time.perf_counter() - t0
    return {
        "asof": asof_iso,
        "source": "FinanceDataReader",
        "n": n,
        "universe_count": universe_count,
        "price_success_count": price_success,
        "price_fail_count": price_fail,
        "runtime_seconds": round(elapsed, 3),
        "daily_topn": _topn(buckets["daily"]),
        "one_month_topn": _topn(buckets["one_month"]),
        "three_month_topn": _topn(buckets["three_month"]),
        "topn_caveat": ("TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능."),
    }


def save_topn_artifact(
    payload: dict,
    *,
    path: Path = DEFAULT_TOPN_PATH,
) -> Path:
    """compute_topn 결과를 atomic JSON 저장."""
    write_artifact_json(payload, path=path)
    return path


def compute_and_save_topn(
    *,
    n: int = DEFAULT_N,
    db_path: Path = DEFAULT_DB_PATH,
    artifact_path: Path = DEFAULT_TOPN_PATH,
    asof: Optional[str] = None,
) -> tuple[dict, Path]:
    payload = compute_topn(n=n, db_path=db_path, asof=asof)
    out = save_topn_artifact(payload, path=artifact_path)
    return payload, out
