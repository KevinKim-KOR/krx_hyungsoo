"""Market Flow ML Dataset builder (2026-07-03).

SQLite 만 read 하여 날짜별 시장 학습 데이터셋을 조립.

지시문 §5 데이터 계약:
- KODEX200 / KOSPI / ETF universe: 기준일 t 까지 실제 관측값.
- VIX: t 보다 엄격히 이전 (strictly-prior) 가장 최근 관측일.
- ETF universe: 인버스 / 레버리지 / 합성 / 선물형 / missing_confirm 제외.
- target: t 이후 정확히 20 번째 KODEX200 거래일 단순 수익률 (%).

부작용 없음. 외부 API / FDR / Yahoo / pykrx / KRX CSV 호출 0건.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_timeseries_ingestion_store import STATUS_MISSING_CONFIRM
from app.market_topn_helpers import classify_etf_tags

BENCHMARK_KODEX200_TICKER = "069500"
BENCHMARK_VIX_ID = "VIX"
BENCHMARK_KOSPI_ID = "KOSPI"

TARGET_HORIZON_DAYS = 20
LOOKBACK_5D = 5
LOOKBACK_20D = 20
VIX_LOOKBACK_5OBS = 5
VIX_LOOKBACK_20OBS = 20

FEATURE_COLUMNS: tuple[str, ...] = (
    "kodex200_return_5d_pct",
    "kodex200_return_20d_pct",
    "kospi_return_5d_pct",
    "kospi_return_20d_pct",
    "etf_breadth_positive_ratio_20d",
    "etf_breadth_median_return_20d_pct",
    "etf_breadth_spread_p90_p10_20d_pct",
    "vix_close_lagged",
    "vix_return_5obs_pct",
    "vix_return_20obs_pct",
    "etf_eligible_count",
    "etf_coverage_count_20d",
    "etf_coverage_ratio_20d",
)

TARGET_COLUMN = "target_future_kodex200_return_20d_pct"
ID_COLUMNS: tuple[str, ...] = (
    "as_of_date",
    "target_end_date",
    "vix_source_date",
    "vix_lag_calendar_days",
)


@dataclass
class SourceSnapshot:
    kodex200_max_date: Optional[str] = None
    kospi_max_date: Optional[str] = None
    vix_max_date: Optional[str] = None
    etf_price_max_date: Optional[str] = None


@dataclass
class DatasetBuildResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    excluded_reason_counts: dict[str, int] = field(default_factory=dict)
    labeled_count: int = 0
    unlabeled_latest_row: Optional[dict[str, Any]] = None


# ---------- SQLite readers (pure) ----------


def _fetch_series(
    con: sqlite3.Connection, query: str, params: tuple
) -> list[tuple[str, float]]:
    cur = con.execute(query, params)
    return [(str(r[0]), float(r[1])) for r in cur.fetchall()]


def fetch_snapshot(db_path: Path = DEFAULT_DB_PATH) -> SourceSnapshot:
    snap = SourceSnapshot()
    if not db_path.exists():
        return snap
    con = sqlite3.connect(str(db_path))
    try:
        for attr, sql, params in (
            (
                "kodex200_max_date",
                "SELECT MAX(date) FROM etf_daily_price "
                "WHERE ticker = ? AND close IS NOT NULL AND close > 0",
                (BENCHMARK_KODEX200_TICKER,),
            ),
            (
                "kospi_max_date",
                "SELECT MAX(date) FROM market_benchmark_daily_price "
                "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0",
                (BENCHMARK_KOSPI_ID,),
            ),
            (
                "vix_max_date",
                "SELECT MAX(date) FROM market_benchmark_daily_price "
                "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0",
                (BENCHMARK_VIX_ID,),
            ),
            (
                "etf_price_max_date",
                "SELECT MAX(date) FROM etf_daily_price "
                "WHERE close IS NOT NULL AND close > 0",
                (),
            ),
        ):
            row = con.execute(sql, params).fetchone()
            setattr(snap, attr, row[0] if row and row[0] else None)
    finally:
        con.close()
    return snap


def _load_kodex200_series(con: sqlite3.Connection) -> list[tuple[str, float]]:
    return _fetch_series(
        con,
        "SELECT date, close FROM etf_daily_price "
        "WHERE ticker = ? AND close IS NOT NULL AND close > 0 ORDER BY date ASC",
        (BENCHMARK_KODEX200_TICKER,),
    )


def _load_benchmark_series(
    con: sqlite3.Connection, benchmark_id: str
) -> list[tuple[str, float]]:
    return _fetch_series(
        con,
        "SELECT date, close FROM market_benchmark_daily_price "
        "WHERE benchmark_id = ? AND close IS NOT NULL AND close > 0 "
        "ORDER BY date ASC",
        (benchmark_id,),
    )


def _load_eligible_etf_tickers(con: sqlite3.Connection) -> list[str]:
    """정상 ETF universe 필터 — 지시문 §5.3."""
    cur = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name = 'market_timeseries_ingestion_state'"
    )
    missing_confirm: set[str] = set()
    if cur.fetchone() is not None:
        cur = con.execute(
            "SELECT ticker FROM market_timeseries_ingestion_state "
            "WHERE ingestion_status = ?",
            (STATUS_MISSING_CONFIRM,),
        )
        missing_confirm = {str(r[0]) for r in cur.fetchall()}
    cur = con.execute("SELECT ticker, name FROM etf_master")
    result: list[str] = []
    for ticker, name in cur.fetchall():
        if ticker == BENCHMARK_KODEX200_TICKER:
            continue
        if ticker in missing_confirm:
            continue
        if classify_etf_tags(name):
            continue
        result.append(str(ticker))
    return sorted(result)


def _load_etf_close_map(
    con: sqlite3.Connection, tickers: list[str]
) -> dict[str, dict[str, float]]:
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    cur = con.execute(
        f"SELECT ticker, date, close FROM etf_daily_price "
        f"WHERE ticker IN ({placeholders}) "
        f"AND close IS NOT NULL AND close > 0",
        tickers,
    )
    out: dict[str, dict[str, float]] = {}
    for ticker, date, close in cur.fetchall():
        out.setdefault(str(ticker), {})[str(date)] = float(close)
    return out


# ---------- pure math helpers ----------


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def _median(values: list[float]) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    n = len(xs)
    mid = n // 2
    if n % 2:
        return xs[mid]
    return (xs[mid - 1] + xs[mid]) / 2.0


def _pct_return(current: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior <= 0:
        return None
    return (current / prior - 1.0) * 100.0


def _calendar_day_diff(a_iso: str, b_iso: str) -> int:
    a = datetime.strptime(a_iso, "%Y-%m-%d").date()
    b = datetime.strptime(b_iso, "%Y-%m-%d").date()
    return (a - b).days


def _find_strictly_prior_vix(vix_dates: list[str], as_of: str) -> Optional[int]:
    prior_idx: Optional[int] = None
    for i, d in enumerate(vix_dates):
        if d < as_of:
            prior_idx = i
        else:
            break
    return prior_idx


# ---------- ETF breadth (한 기준일) ----------


def _compute_etf_breadth(
    *,
    eligible_tickers: list[str],
    etf_close_map: dict[str, dict[str, float]],
    as_of: str,
    prior_kodex_date_20: str,
) -> Optional[dict[str, Any]]:
    """(eligible_count, coverage_count, coverage_ratio, positive_ratio, median, spread)."""
    eligible_count = len(eligible_tickers)
    if eligible_count == 0:
        return None
    etf_20d_returns: list[float] = []
    for ticker in eligible_tickers:
        closes = etf_close_map.get(ticker, {})
        now_c = closes.get(as_of)
        prior_c = closes.get(prior_kodex_date_20)
        if now_c is None or prior_c is None:
            continue
        r = _pct_return(now_c, prior_c)
        if r is None:
            continue
        etf_20d_returns.append(r)
    coverage_count = len(etf_20d_returns)
    if coverage_count == 0:
        return None
    positive_ratio = sum(1 for r in etf_20d_returns if r > 0) / coverage_count
    median_return = _median(etf_20d_returns)
    p90 = _percentile(etf_20d_returns, 90.0)
    p10 = _percentile(etf_20d_returns, 10.0)
    if median_return is None or p90 is None or p10 is None:
        return None
    return {
        "eligible_count": eligible_count,
        "coverage_count": coverage_count,
        "coverage_ratio": coverage_count / eligible_count,
        "positive_ratio": positive_ratio,
        "median_return": median_return,
        "spread": p90 - p10,
    }


# ---------- dataset builder ----------


def _build_row_for_asof(
    *,
    idx: int,
    as_of: str,
    kodex_dates: list[str],
    kodex_close: dict[str, float],
    kospi_close: dict[str, float],
    kospi_dates_asc: list[str],
    vix_dates: list[str],
    vix_close: dict[str, float],
    eligible_tickers: list[str],
    etf_close_map: dict[str, dict[str, float]],
    bump: Any,
) -> Optional[dict[str, Any]]:
    """한 기준일 dict row 생성 (excluded 는 bump 로 카운트 후 None 반환)."""
    if idx < LOOKBACK_20D:
        bump("kodex_lookback_insufficient")
        return None
    k_now = kodex_close[as_of]
    kodex_5d = _pct_return(k_now, kodex_close[kodex_dates[idx - LOOKBACK_5D]])
    kodex_20d = _pct_return(k_now, kodex_close[kodex_dates[idx - LOOKBACK_20D]])
    if kodex_5d is None or kodex_20d is None:
        bump("kodex_return_calc_failed")
        return None
    if as_of not in kospi_close:
        bump("kospi_missing_on_asof")
        return None
    try:
        kospi_idx = kospi_dates_asc.index(as_of)
    except ValueError:
        bump("kospi_missing_on_asof")
        return None
    if kospi_idx < LOOKBACK_20D:
        bump("kospi_lookback_insufficient")
        return None
    kospi_now = kospi_close[as_of]
    kospi_5d = _pct_return(
        kospi_now, kospi_close[kospi_dates_asc[kospi_idx - LOOKBACK_5D]]
    )
    kospi_20d = _pct_return(
        kospi_now, kospi_close[kospi_dates_asc[kospi_idx - LOOKBACK_20D]]
    )
    if kospi_5d is None or kospi_20d is None:
        bump("kospi_return_calc_failed")
        return None
    vix_prior_idx = _find_strictly_prior_vix(vix_dates, as_of)
    if vix_prior_idx is None:
        bump("vix_no_strictly_prior_observation")
        return None
    vix_source_date = vix_dates[vix_prior_idx]
    if vix_source_date >= as_of:
        bump("vix_alignment_violation")
        return None
    vix_lag_days = _calendar_day_diff(as_of, vix_source_date)
    vix_close_lagged = vix_close[vix_source_date]
    if vix_prior_idx < VIX_LOOKBACK_20OBS:
        bump("vix_lookback_insufficient")
        return None
    vix_5obs_return = _pct_return(
        vix_close_lagged, vix_close[vix_dates[vix_prior_idx - VIX_LOOKBACK_5OBS]]
    )
    vix_20obs_return = _pct_return(
        vix_close_lagged, vix_close[vix_dates[vix_prior_idx - VIX_LOOKBACK_20OBS]]
    )
    if vix_5obs_return is None or vix_20obs_return is None:
        bump("vix_return_calc_failed")
        return None
    breadth = _compute_etf_breadth(
        eligible_tickers=eligible_tickers,
        etf_close_map=etf_close_map,
        as_of=as_of,
        prior_kodex_date_20=kodex_dates[idx - LOOKBACK_20D],
    )
    if breadth is None:
        bump("etf_breadth_calc_failed")
        return None
    target_idx = idx + TARGET_HORIZON_DAYS
    has_target = target_idx < len(kodex_dates)
    target_end_date = kodex_dates[target_idx] if has_target else None
    target_value = (
        _pct_return(kodex_close[target_end_date], k_now)
        if has_target and target_end_date
        else None
    )
    return {
        "as_of_date": as_of,
        "target_end_date": target_end_date,
        "vix_source_date": vix_source_date,
        "vix_lag_calendar_days": vix_lag_days,
        "kodex200_return_5d_pct": kodex_5d,
        "kodex200_return_20d_pct": kodex_20d,
        "kospi_return_5d_pct": kospi_5d,
        "kospi_return_20d_pct": kospi_20d,
        "etf_breadth_positive_ratio_20d": breadth["positive_ratio"],
        "etf_breadth_median_return_20d_pct": breadth["median_return"],
        "etf_breadth_spread_p90_p10_20d_pct": breadth["spread"],
        "vix_close_lagged": vix_close_lagged,
        "vix_return_5obs_pct": vix_5obs_return,
        "vix_return_20obs_pct": vix_20obs_return,
        "etf_eligible_count": breadth["eligible_count"],
        "etf_coverage_count_20d": breadth["coverage_count"],
        "etf_coverage_ratio_20d": breadth["coverage_ratio"],
        TARGET_COLUMN: target_value,
        "_has_target": has_target,
    }


def build_dataset(db_path: Path = DEFAULT_DB_PATH) -> DatasetBuildResult:
    result = DatasetBuildResult()
    if not db_path.exists():
        result.excluded_reason_counts["db_missing"] = 1
        return result
    con = sqlite3.connect(str(db_path))
    try:
        kodex_series = _load_kodex200_series(con)
        kospi_series = _load_benchmark_series(con, BENCHMARK_KOSPI_ID)
        vix_series = _load_benchmark_series(con, BENCHMARK_VIX_ID)
        eligible_tickers = _load_eligible_etf_tickers(con)
        etf_close_map = _load_etf_close_map(con, eligible_tickers)
    finally:
        con.close()
    if not kodex_series or not vix_series:
        result.excluded_reason_counts["no_kodex_or_vix"] = 1
        return result
    kodex_dates = [d for d, _ in kodex_series]
    kodex_close = {d: c for d, c in kodex_series}
    kospi_close = {d: c for d, c in kospi_series}
    kospi_dates_asc = list(kospi_close.keys())
    vix_dates = [d for d, _ in vix_series]
    vix_close = {d: c for d, c in vix_series}
    exclude_reasons: dict[str, int] = {}

    def bump(reason: str) -> None:
        exclude_reasons[reason] = exclude_reasons.get(reason, 0) + 1

    rows: list[dict[str, Any]] = []
    latest_unlabeled: Optional[dict[str, Any]] = None
    for idx, as_of in enumerate(kodex_dates):
        row = _build_row_for_asof(
            idx=idx,
            as_of=as_of,
            kodex_dates=kodex_dates,
            kodex_close=kodex_close,
            kospi_close=kospi_close,
            kospi_dates_asc=kospi_dates_asc,
            vix_dates=vix_dates,
            vix_close=vix_close,
            eligible_tickers=eligible_tickers,
            etf_close_map=etf_close_map,
            bump=bump,
        )
        if row is None:
            continue
        has_target = row.pop("_has_target")
        if has_target and row[TARGET_COLUMN] is not None:
            rows.append(row)
        else:
            latest_unlabeled = row
            bump("target_horizon_unavailable")
    result.rows = rows
    result.excluded_reason_counts = exclude_reasons
    result.labeled_count = len(rows)
    result.unlabeled_latest_row = latest_unlabeled
    return result
