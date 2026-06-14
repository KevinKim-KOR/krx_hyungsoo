"""POC2 Cleanup — market_topn 보조 helper 분리 (2026-06-14).

`app/market_topn.py` 의 KS-10 near 해소를 위해 다음 helper 들을 본 모듈로 이관.
산식 / 문구 / 데이터 계약 변경 0건. 함수 시그니처와 동작 그대로.

본 모듈은 다음을 제공한다:

- 상수: `REQUIRED_TABLES`, `EXCLUSION_REASONS`, `PRODUCT_TAG_TYPES`,
  `DAILY_LOOKBACK_DAYS`, `ONE_MONTH_LOOKBACK_DAYS`, `THREE_MONTH_LOOKBACK_DAYS`,
  `SIX_MONTH_LOOKBACK_DAYS`, `TWELVE_MONTH_LOOKBACK_DAYS`,
  `THREE_YEAR_LOOKBACK_DAYS`, `ALLOWED_BASIS`, `DEFAULT_BASIS`, `ALLOWED_ORDER`,
  `DEFAULT_ORDER`, `DEFAULT_N`.
- dataclass: `TopNEntry`, `_PeriodResult`.
- helper: `_missing_required_tables`, `classify_etf_tags`, `_compute_period`,
  `_latest_date_in_db`, `_latest_refresh_payload`, `_empty_exclusion_buckets`,
  `_empty_filter_exclusion_buckets`, `_build_filters_dict`, `_build_empty_payload`.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.market_data_store import latest_refresh_log

REQUIRED_TABLES = ("etf_master", "etf_daily_price", "market_refresh_log")

DEFAULT_N = 10
DAILY_LOOKBACK_DAYS = 1
ONE_MONTH_LOOKBACK_DAYS = 30
THREE_MONTH_LOOKBACK_DAYS = 90
# 2026-06-08 — UI 요청 (6m/12m/1y/3y 컬럼 추가). 시계열이 없으면 None 으로
# 정직 표시. 1m=30 패턴 유지 (영업일 기준 아니라 캘린더 일수).
SIX_MONTH_LOOKBACK_DAYS = 180
TWELVE_MONTH_LOOKBACK_DAYS = 365
THREE_YEAR_LOOKBACK_DAYS = 365 * 3

# 2026-05-18 통합 후보 테이블 1차 — 조회 기준 (basis).
ALLOWED_BASIS = ("daily", "one_month", "three_month")
DEFAULT_BASIS = "one_month"

# 2026-05-19 Grid 사용성 FIX — 정렬 방향 (order).
ALLOWED_ORDER = ("desc", "asc")
DEFAULT_ORDER = "desc"

EXCLUSION_REASONS = (
    "missing_latest_price",
    "missing_base_price",
    "insufficient_history",
    "invalid_price",
    "stale_price",
)

# 2026-05-18 Market Discovery 후보 정제 1차:
# ETF 이름 기반 1차 태깅 — 인버스 / 레버리지 / 합성 / 선물형.
PRODUCT_TAG_TYPES = ("inverse", "leveraged", "synthetic", "futures")


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


def _missing_required_tables(db_path: Path) -> list[str]:
    """raw sqlite3 로 필수 테이블 존재 여부 확인 — init_db 자동 호출 회피.

    init_db 를 거치면 모든 테이블이 자동 생성되어 invalid 분기를 진입할 수 없다.
    본 함수는 sqlite_master 만 조회한다.
    """
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN (?, ?, ?)",
            REQUIRED_TABLES,
        )
        present = {row[0] for row in cur.fetchall()}
    return [t for t in REQUIRED_TABLES if t not in present]


def classify_etf_tags(name: Optional[str]) -> list[str]:
    """ETF 이름에서 1차 상품 태그를 추출.

    - "인버스" → inverse
    - "레버리지" / "2X" / "2배" → leveraged
    - "합성" → synthetic
    - "선물" → futures
    """
    if not name:
        return []
    tags: list[str] = []
    if "인버스" in name:
        tags.append("inverse")
    # leveraged: "레버리지" 또는 "2X" (대/소문자 무시) 또는 "2배"
    name_upper = name.upper()
    if ("레버리지" in name) or ("2X" in name_upper) or ("2배" in name):
        tags.append("leveraged")
    if "합성" in name:
        tags.append("synthetic")
    if "선물" in name:
        tags.append("futures")
    return tags


def _empty_filter_exclusion_buckets() -> dict[str, dict[str, int]]:
    return {
        "daily": {k: 0 for k in PRODUCT_TAG_TYPES},
        "one_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "three_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "six_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "twelve_month": {k: 0 for k in PRODUCT_TAG_TYPES},
        "three_year": {k: 0 for k in PRODUCT_TAG_TYPES},
    }


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
        "six_month": {k: 0 for k in EXCLUSION_REASONS},
        "twelve_month": {k: 0 for k in EXCLUSION_REASONS},
        "three_year": {k: 0 for k in EXCLUSION_REASONS},
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


def _build_filters_dict(
    exclude_inverse: bool,
    exclude_leveraged: bool,
    exclude_synthetic: bool,
    exclude_futures: bool,
) -> dict[str, bool]:
    return {
        "exclude_inverse": exclude_inverse,
        "exclude_leveraged": exclude_leveraged,
        "exclude_synthetic": exclude_synthetic,
        "exclude_futures": exclude_futures,
    }


def _build_empty_payload(
    *,
    status: str,
    n: int,
    elapsed: float,
    basis: str = DEFAULT_BASIS,
    order: str = DEFAULT_ORDER,
    error: Optional[str] = None,
    db_path: Optional[Path] = None,
    filters: Optional[dict[str, bool]] = None,
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
        "basis": basis,
        "order": order,
        "universe_count": 0,
        "price_success_count": 0,
        "price_fail_count": 0,
        "latest_refresh": latest_refresh,
        "runtime_seconds": round(elapsed, 3),
        "candidates": [],
        "daily_topn": [],
        "one_month_topn": [],
        "three_month_topn": [],
        "period_exclusions": _empty_exclusion_buckets(),
        "filter_exclusions": _empty_filter_exclusion_buckets(),
        "filters": filters or _build_filters_dict(True, True, True, True),
        "topn_caveat": (
            "TOP N 의 N 값은 고정값이 아니며 운영/테스트 중 변경 가능 (query parameter `n`)."
        ),
        "market_context": None,
    }
