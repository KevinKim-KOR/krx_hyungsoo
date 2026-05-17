"""SQLite 직접 계산 기반 일간 / 1개월 / 3개월 TOP N 산출.

2026-05-18 변경 (Market Discovery SQLite Direct Refresh):
- JSON artifact 출력/저장 폐기 (state/market/ 하위 어떤 .json 파일도 생성하지 않는다).
- 시장 데이터 SSOT 는 state/market/market_data.sqlite 단일.
- API (`GET /market/topn/latest`) 는 본 모듈의 `compute_topn()` 만 호출한다.

응답 status:
- "ok"      : 정상 — universe + 가격 데이터로 TOP N 산출 가능 (빈 결과여도 ok)
- "missing" : SQLite DB 파일 자체 없음
- "empty"   : DB 존재하나 가격 데이터 부족 (etf_daily_price 의 date 없음)
- "invalid" : DB 파일 깨짐 / 필수 테이블 부재 등 구조 이상

결측 처리 (지시문 §6):
- 결측 ETF 를 0% 수익률로 보정하지 않는다.
- period_exclusions 로 기간별 제외 사유를 집계해 반환.
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
    latest_refresh_log,
    list_etf_tickers,
)

REQUIRED_TABLES = ("etf_master", "etf_daily_price", "market_refresh_log")


def _missing_required_tables(db_path: Path) -> list[str]:
    """raw sqlite3 로 필수 테이블 존재 여부 확인 — init_db 자동 호출 회피.

    init_db 를 거치면 모든 테이블이 자동 생성되어 invalid 분기를 진입할 수 없다.
    본 함수는 sqlite_master 만 조회한다 (sqlite3.connect 는 빈 파일을 만들 수 있지만
    compute_topn 진입 직전에 path.exists() 가 이미 통과한 상태라 안전).
    """
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN (?, ?, ?)",
            REQUIRED_TABLES,
        )
        present = {row[0] for row in cur.fetchall()}
    return [t for t in REQUIRED_TABLES if t not in present]


DEFAULT_N = 10
DAILY_LOOKBACK_DAYS = 1
ONE_MONTH_LOOKBACK_DAYS = 30
THREE_MONTH_LOOKBACK_DAYS = 90

EXCLUSION_REASONS = (
    "missing_latest_price",
    "missing_base_price",
    "insufficient_history",
    "invalid_price",
    "stale_price",
)


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


@dataclass
class _PeriodResult:
    return_pct: Optional[float]
    base_date: Optional[str]
    exclusion_reason: Optional[str]  # None if success


def _compute_period(
    history: list[tuple[str, float]],
    asof_iso: str,
    lookback_days: int,
) -> _PeriodResult:
    """단일 ticker 의 시계열에서 한 기간 수익률 산출.

    결측은 0% 로 보정하지 않고 exclusion_reason 으로 분류한다.
    """
    if not history:
        return _PeriodResult(None, None, "missing_latest_price")
    if len(history) < 2:
        return _PeriodResult(None, None, "insufficient_history")

    latest_idx = len(history) - 1
    _latest_date, latest_close = history[latest_idx]
    if latest_close <= 0:
        return _PeriodResult(None, None, "invalid_price")

    if lookback_days == DAILY_LOOKBACK_DAYS:
        base_idx: Optional[int] = latest_idx - 1
    else:
        try:
            asof_d = date.fromisoformat(asof_iso)
        except ValueError:
            return _PeriodResult(None, None, "invalid_price")
        target = asof_d - timedelta(days=lookback_days)
        target_iso = target.isoformat()
        base_idx = None
        for i, (d_iso, _close) in enumerate(history):
            if d_iso >= target_iso:
                base_idx = i
                break
        if base_idx is None:
            return _PeriodResult(None, None, "missing_base_price")
        if base_idx == latest_idx:
            return _PeriodResult(None, None, "insufficient_history")

    base_date, base_close = history[base_idx]
    if base_close <= 0:
        return _PeriodResult(None, None, "invalid_price")
    ret_pct = (latest_close / base_close - 1.0) * 100.0
    return _PeriodResult(return_pct=ret_pct, base_date=base_date, exclusion_reason=None)


def _latest_date_in_db(db_path: Path) -> Optional[str]:
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute("SELECT MAX(date) FROM etf_daily_price")
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def _empty_exclusion_buckets() -> dict[str, dict[str, int]]:
    return {
        "daily": {k: 0 for k in EXCLUSION_REASONS},
        "one_month": {k: 0 for k in EXCLUSION_REASONS},
        "three_month": {k: 0 for k in EXCLUSION_REASONS},
    }


def _latest_refresh_payload(db_path: Path) -> Optional[dict]:
    log = latest_refresh_log(db_path=db_path)
    if not log:
        return None
    return {
        "refresh_id": log["run_id"],
        "source": log["source"],
        "asof": log["asof"],
        "attempted_count": log["attempted_count"],
        "success_count": log["success_count"],
        "fail_count": log["fail_count"],
        "runtime_seconds": log["runtime_seconds"],
        "error_summary": log["error_summary"],
        "created_at": log["created_at"],
    }


def _build_empty_payload(
    *,
    status: str,
    n: int,
    elapsed: float,
    error: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> dict:
    latest_refresh = None
    if db_path is not None and status in ("ok", "empty"):
        try:
            latest_refresh = _latest_refresh_payload(db_path)
        except sqlite3.Error:
            latest_refresh = None
    return {
        "status": status,
        "error": error,
        "asof": None,
        "source": "SQLite (FinanceDataReader 수집)",
        "n": n,
        "universe_count": 0,
        "price_success_count": 0,
        "price_fail_count": 0,
        "latest_refresh": latest_refresh,
        "runtime_seconds": round(elapsed, 3),
        "daily_topn": [],
        "one_month_topn": [],
        "three_month_topn": [],
        "period_exclusions": _empty_exclusion_buckets(),
        "topn_caveat": (
            "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능 (query parameter `n`)."
        ),
    }


def compute_topn(
    *,
    n: int = DEFAULT_N,
    db_path: Path = DEFAULT_DB_PATH,
    asof: Optional[str] = None,
) -> dict:
    """SQLite etf_daily_price 기준 일간 / 1개월 / 3개월 TOP N 산출.

    DB 부재 시 status="missing". DB 가 있어도 가격 데이터 없음/필수 테이블 부재면
    각각 status="empty"/"invalid". 본 함수는 외부 fetch / write 없음 — SQLite read only.
    """
    t0 = time.perf_counter()

    if not db_path.exists():
        return _build_empty_payload(
            status="missing",
            n=n,
            elapsed=time.perf_counter() - t0,
            error="SQLite DB 파일이 없습니다. 먼저 시장 데이터 갱신을 실행하세요.",
        )

    try:
        missing = _missing_required_tables(db_path)
    except sqlite3.Error as e:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            error=f"SQLite 구조 확인 실패: {type(e).__name__}: {e}",
        )
    if missing:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            error=f"SQLite 의 필수 테이블이 누락되었습니다: {missing}",
        )

    try:
        asof_iso = asof or _latest_date_in_db(db_path)
    except sqlite3.Error as e:
        return _build_empty_payload(
            status="invalid",
            n=n,
            elapsed=time.perf_counter() - t0,
            error=f"SQLite 조회 실패: {type(e).__name__}: {e}",
        )

    tickers = list_etf_tickers(db_path)
    universe_count = len(tickers)

    if not asof_iso:
        payload = _build_empty_payload(
            status="empty",
            n=n,
            elapsed=time.perf_counter() - t0,
            error="가격 데이터가 SQLite 에 아직 없습니다. 최신 시장 데이터 갱신을 실행하세요.",
            db_path=db_path,
        )
        payload["universe_count"] = universe_count
        return payload

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
    exclusions = _empty_exclusion_buckets()

    for tk in tickers:
        history = fetch_price_history(tk, db_path=db_path)
        if not history:
            price_fail += 1
            for label, _ in period_specs:
                exclusions[label]["missing_latest_price"] += 1
            continue
        price_success += 1
        for label, lookback in period_specs:
            r = _compute_period(history, asof_iso, lookback)
            if r.exclusion_reason is not None:
                exclusions[label][r.exclusion_reason] = (
                    exclusions[label].get(r.exclusion_reason, 0) + 1
                )
                continue
            assert r.return_pct is not None and r.base_date is not None
            buckets[label].append((tk, r.return_pct, r.base_date))

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
        "status": "ok",
        "error": None,
        "asof": asof_iso,
        "source": "SQLite (FinanceDataReader 수집)",
        "n": n,
        "universe_count": universe_count,
        "price_success_count": price_success,
        "price_fail_count": price_fail,
        "latest_refresh": _latest_refresh_payload(db_path),
        "runtime_seconds": round(elapsed, 3),
        "daily_topn": _topn(buckets["daily"]),
        "one_month_topn": _topn(buckets["one_month"]),
        "three_month_topn": _topn(buckets["three_month"]),
        "period_exclusions": exclusions,
        "topn_caveat": (
            "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능 (query parameter `n`)."
        ),
    }
