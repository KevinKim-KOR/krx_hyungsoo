"""ML Feature Sanity Check — 계산 정합성 / 데이터 품질 검산 (POC2 2026-06-08).

지시문 §3 — ML baseline v0 입력 직전에 etf_ml_feature_daily / market_risk_feature_daily
의 값이 사람이 납득할 수 있는 수준인지 검산. ML 학습 / 위험 threshold / 매수·매도
판단 / 외부 source 호출 0건.

본 모듈의 책임:
- coverage check: row 수 / asof 범위 / latest asof.
- calculation check: 샘플 ticker × 마지막 asof 1건의 return/excess/volatility/
  drawdown/volume_ratio 를 primitives 로 재계산 → ML row 값과 비교 (지시문 §4.4).
  허용 오차: abs_tol=1e-4 + rel_tol=1e-4 (사용자 결정 — (b) 옵션).
- NAV join check: future_nav_join_count=0 보장 (지시문 §4.5).
- risk proxy check: per-axis null 비율 + all-null per asof 만 (지시문 §4.6 — (f) 옵션).
- sample rows: Data Status 표시용 5~10건 (KODEX 200 / 거래량 top / NAV ok 다양).

본 모듈은 SQLite read-only. ML feature 재생성 X (orchestrator 책임은 별도).
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import (
    DEFAULT_DB_PATH,
    fetch_price_volume_history,
)
from app.market_regime import KODEX200_TICKER
from app.ml_feature_nav_lookup import NavLookup
from app.ml_feature_primitives import (
    WINDOW_5,
    WINDOW_10,
    WINDOW_20,
    build_series,
    return_pct,
)
from app.ml_feature_sanity_helpers import (
    fetch_ml_row,
    fetch_sample_rows,
    pick_sample_tickers,
    recompute_features_for_sample,
)

# 허용 오차 — 지시문 §4.4 사용자 결정 (b).
CALC_ABS_TOL = 1e-4
CALC_REL_TOL = 1e-4

DEFAULT_SAMPLE_TICKER_COUNT = 10
RISK_PROXY_NULL_WARN_RATIO = 0.5

# Coverage — 지시문 §4.3 ticker별 row 누락 / asof별 ticker count 급감 임계.
# trading_days 대비 95% 미만 row 적재되면 이상 (warn).
COVERAGE_TICKER_ROW_WARN_RATIO = 0.95
# asof별 ticker count 가 median 대비 70% 미만 으로 떨어지면 급감 의심 (warn).
COVERAGE_ASOF_TICKER_DROP_RATIO = 0.70


# ─── helpers ──────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_close(a: Optional[float], b: Optional[float]) -> bool:
    """abs_tol + rel_tol 결합 비교 (NumPy isclose 패턴).

    한쪽만 None 이면 False. 양쪽 None 이면 True (둘 다 누락이 일치하는 상태).
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= max(CALC_ABS_TOL, CALC_REL_TOL * max(abs(a), abs(b)))


# ─── coverage ────────────────────────────────────────────────────────


@dataclass
class CoverageChecks:
    status: str  # ok / warn / error
    feature_asof_start: Optional[str]
    feature_asof_end: Optional[str]
    trading_days: int
    etf_feature_row_count: int
    market_risk_row_count: int
    latest_asof_matches_readiness: bool
    # 지시문 §4.3 — ticker별 row 누락 / asof별 ticker count 급감.
    distinct_ticker_count: int = 0
    tickers_with_missing_rows: int = 0
    asof_ticker_count_median: int = 0
    asof_ticker_count_min: int = 0
    asof_with_ticker_drop: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _median_int(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) // 2


def _check_coverage(db_path: Path) -> CoverageChecks:
    warnings: list[str] = []
    errors: list[str] = []
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT COUNT(*), MIN(asof), MAX(asof), COUNT(DISTINCT asof), "
            "COUNT(DISTINCT ticker) FROM etf_ml_feature_daily"
        )
        row = cur.fetchone()
        etf_count = int(row[0] or 0)
        asof_start = row[1]
        asof_end = row[2]
        trading_days = int(row[3] or 0)
        distinct_tickers = int(row[4] or 0)

        # ticker별 row 누락 — 지시문 §4.3.
        # trading_days 대비 row 수가 임계 비율 미만인 ticker 수 집계.
        tickers_missing = 0
        if trading_days > 0 and distinct_tickers > 0:
            min_required = int(trading_days * COVERAGE_TICKER_ROW_WARN_RATIO)
            cur = con.execute(
                "SELECT COUNT(*) FROM ("
                "  SELECT ticker, COUNT(*) AS c FROM etf_ml_feature_daily "
                "  GROUP BY ticker HAVING c < ?"
                ")",
                (min_required,),
            )
            tickers_missing = int(cur.fetchone()[0] or 0)

        # asof별 ticker count 급감 — 지시문 §4.3.
        asof_counts: list[tuple[str, int]] = []
        if trading_days > 0:
            cur = con.execute(
                "SELECT asof, COUNT(DISTINCT ticker) FROM etf_ml_feature_daily "
                "GROUP BY asof ORDER BY asof"
            )
            asof_counts = [(str(r[0]), int(r[1])) for r in cur.fetchall()]

        # Market risk
        cur = con.execute("SELECT COUNT(*), MAX(asof) FROM market_risk_feature_daily")
        row = cur.fetchone()
        mkt_count = int(row[0] or 0)
        mkt_latest_asof = row[1]

    counts_only = [c for _, c in asof_counts]
    median_c = _median_int(counts_only)
    min_c = min(counts_only) if counts_only else 0
    drop_threshold = (
        int(median_c * COVERAGE_ASOF_TICKER_DROP_RATIO) if median_c > 0 else 0
    )
    drop_asofs = [a for a, c in asof_counts if median_c > 0 and c < drop_threshold]

    if tickers_missing > 0:
        warnings.append(
            f"ticker별 row 누락: {tickers_missing}개 ticker 의 row 수가 "
            f"trading_days×{COVERAGE_TICKER_ROW_WARN_RATIO} 미만"
        )
    if drop_asofs:
        warnings.append(
            f"asof별 ticker count 급감: {len(drop_asofs)}건 "
            f"(median={median_c} 의 {COVERAGE_ASOF_TICKER_DROP_RATIO} 미만)"
        )

    latest_match = asof_end == mkt_latest_asof
    if not latest_match:
        warnings.append(
            f"latest asof 불일치: etf={asof_end} / market_risk={mkt_latest_asof}"
        )
    if etf_count == 0:
        errors.append("etf_ml_feature_daily row 0건")
    if mkt_count == 0:
        errors.append("market_risk_feature_daily row 0건")

    status = "error" if errors else ("warn" if warnings else "ok")
    return CoverageChecks(
        status=status,
        feature_asof_start=asof_start,
        feature_asof_end=asof_end,
        trading_days=trading_days,
        etf_feature_row_count=etf_count,
        market_risk_row_count=mkt_count,
        latest_asof_matches_readiness=latest_match,
        distinct_ticker_count=distinct_tickers,
        tickers_with_missing_rows=tickers_missing,
        asof_ticker_count_median=median_c,
        asof_ticker_count_min=min_c,
        asof_with_ticker_drop=drop_asofs[:20],  # snapshot 비대화 방지.
        warnings=warnings,
        errors=errors,
    )


# ─── calculation ─────────────────────────────────────────────────────


CHECKED_FIELDS = [
    "return_5d",
    "return_10d",
    "return_20d",
    "excess_return_5d_vs_kodex200",
    "excess_return_10d_vs_kodex200",
    "excess_return_20d_vs_kodex200",
    "volatility_20d",
    "drawdown_20d",
    "volume_ratio_20d",
]


@dataclass
class CalculationChecks:
    status: str
    checked_ticker_count: int
    checked_fields: list[str]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_calculations(
    db_path: Path,
    sample_tickers: list[str],
    latest_asof: str,
) -> CalculationChecks:
    warnings: list[str] = []
    errors: list[str] = []

    # KODEX200 시계열 + lookup map (재계산용).
    kodex_rows = fetch_price_volume_history(KODEX200_TICKER, db_path=db_path)
    if not kodex_rows:
        errors.append("KODEX200 시계열을 읽을 수 없음 — calculation check 불가")
        return CalculationChecks(
            status="error",
            checked_ticker_count=0,
            checked_fields=CHECKED_FIELDS,
            warnings=warnings,
            errors=errors,
        )
    kodex_series = build_series(KODEX200_TICKER, kodex_rows)
    kodex_idx = kodex_series.date_index.get(latest_asof)
    kodex_returns_for_asof: dict[str, Optional[float]] = {
        "r5": None,
        "r10": None,
        "r20": None,
    }
    if kodex_idx is not None:
        kodex_returns_for_asof = {
            "r5": return_pct(kodex_series, kodex_idx, WINDOW_5),
            "r10": return_pct(kodex_series, kodex_idx, WINDOW_10),
            "r20": return_pct(kodex_series, kodex_idx, WINDOW_20),
        }

    checked = 0
    for tk in sample_tickers:
        ml_row = fetch_ml_row(db_path, tk, latest_asof)
        if ml_row is None:
            warnings.append(f"ticker={tk} asof={latest_asof} ML row 부재")
            continue
        if tk == KODEX200_TICKER:
            series = kodex_series
        else:
            rows = fetch_price_volume_history(tk, db_path=db_path)
            if not rows:
                warnings.append(f"ticker={tk} 원천 가격 없음 — 검산 skip")
                continue
            series = build_series(tk, rows)
        idx = series.date_index.get(latest_asof)
        if idx is None:
            warnings.append(f"ticker={tk} asof={latest_asof} 거래일 없음")
            continue
        recomputed = recompute_features_for_sample(series, idx, kodex_returns_for_asof)
        for fld in CHECKED_FIELDS:
            if not _is_close(ml_row.get(fld), recomputed.get(fld)):
                errors.append(
                    f"calc mismatch ticker={tk} field={fld} "
                    f"ml={ml_row.get(fld)} recomputed={recomputed.get(fld)}"
                )
        checked += 1

    status = "error" if errors else ("warn" if warnings else "ok")
    return CalculationChecks(
        status=status,
        checked_ticker_count=checked,
        checked_fields=CHECKED_FIELDS,
        warnings=warnings,
        errors=errors,
    )


# ─── NAV join ────────────────────────────────────────────────────────


@dataclass
class NavJoinChecks:
    status: str
    future_nav_join_count: int
    unavailable_ratio: float
    same_asof_count: int
    past_latest_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_nav_join(db_path: Path) -> NavJoinChecks:
    """미래 NAV join 0건 보장. unavailable 비율 / same-asof / past latest 카운트."""
    warnings: list[str] = []
    errors: list[str] = []
    nav_lookup = NavLookup(db_path=db_path)

    total = 0
    unavailable = 0
    same_asof = 0
    past_latest = 0
    future_join_violations = 0

    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT ticker, asof, nav, nav_status, source_flags "
            "FROM etf_ml_feature_daily"
        )
        for ticker, asof, nav, status, flags in cur.fetchall():
            total += 1
            if status == "unavailable":
                unavailable += 1
                continue
            # nav_lookup 으로 검산 — 실제 join 된 row 의 asof 가 ETF asof 와
            # 일치하거나 그 이전이어야 한다.
            nav_row = nav_lookup.lookup(str(ticker), str(asof))
            if nav_row is None:
                # ML row 는 ok 인데 lookup 이 None 이면 변형 — 경고.
                warnings.append(
                    f"ticker={ticker} asof={asof} nav_status={status} 인데 "
                    "재검색 시 lookup 결과 None"
                )
                continue
            if nav_row.asof > asof:
                future_join_violations += 1
                errors.append(
                    f"FUTURE NAV ticker={ticker} feature_asof={asof} "
                    f"nav_asof={nav_row.asof}"
                )
                continue
            if nav_row.asof == asof:
                same_asof += 1
            else:
                past_latest += 1
                # source_flags 에 nav_asof 명시되어야 한다.
                if not flags or f"nav_asof={nav_row.asof}" not in (flags or ""):
                    warnings.append(
                        f"source_flags 누락 ticker={ticker} feature_asof={asof} "
                        f"nav_asof={nav_row.asof}"
                    )

    ratio = (unavailable / total) if total > 0 else 0.0
    status = "error" if errors else ("warn" if warnings else "ok")
    return NavJoinChecks(
        status=status,
        future_nav_join_count=future_join_violations,
        unavailable_ratio=round(ratio, 6),
        same_asof_count=same_asof,
        past_latest_count=past_latest,
        warnings=warnings,
        errors=errors,
    )


# ─── risk proxy ──────────────────────────────────────────────────────


RISK_PROXY_FIELDS = [
    "distance_from_20d_high",
    "drawdown_20d_market_proxy",
    "volatility_expansion_20d",
    "down_day_volume_ratio",
    "large_negative_day_proxy",
    "short_term_weakness_proxy",
    "breadth_deterioration_proxy",
]


@dataclass
class RiskProxyChecks:
    status: str
    per_axis_null_ratio: dict[str, float]
    all_null_asof_count: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _check_risk_proxy(db_path: Path) -> RiskProxyChecks:
    """per-axis null 비율 + all-null per asof 만 검산.

    위험 threshold / 라벨 / 매수·매도 판단 0건 (지시문 §4.6).
    """
    warnings: list[str] = []
    errors: list[str] = []
    field_sql = ", ".join(RISK_PROXY_FIELDS)
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(f"SELECT asof, {field_sql} FROM market_risk_feature_daily")
        rows = cur.fetchall()

    total = len(rows)
    if total == 0:
        errors.append("market_risk_feature_daily row 0건 — risk proxy 검산 불가")
        return RiskProxyChecks(
            status="error",
            per_axis_null_ratio={f: 1.0 for f in RISK_PROXY_FIELDS},
            all_null_asof_count=0,
            warnings=warnings,
            errors=errors,
        )

    null_counts: dict[str, int] = {f: 0 for f in RISK_PROXY_FIELDS}
    all_null_asof = 0
    for row in rows:
        asof = row[0]
        axis_values = row[1:]
        if all(v is None for v in axis_values):
            all_null_asof += 1
            errors.append(f"all-null risk proxy asof={asof}")
        for i, fld in enumerate(RISK_PROXY_FIELDS):
            if axis_values[i] is None:
                null_counts[fld] += 1

    ratios = {f: round(null_counts[f] / total, 6) for f in RISK_PROXY_FIELDS}
    for f, r in ratios.items():
        if r > RISK_PROXY_NULL_WARN_RATIO:
            warnings.append(f"null ratio > {RISK_PROXY_NULL_WARN_RATIO}: {f} = {r}")

    status = "error" if errors else ("warn" if warnings else "ok")
    return RiskProxyChecks(
        status=status,
        per_axis_null_ratio=ratios,
        all_null_asof_count=all_null_asof,
        warnings=warnings,
        errors=errors,
    )


# ─── public API ──────────────────────────────────────────────────────


@dataclass
class SanityReport:
    generated_at: str
    feature_asof_range: dict[str, Any]
    etf_feature_row_count: int
    market_risk_row_count: int
    checked_ticker_count: int
    sampled_tickers: list[str]
    sanity_status: str  # ok / warn / error
    coverage_checks: dict[str, Any]
    calculation_checks: dict[str, Any]
    nav_join_checks: dict[str, Any]
    risk_proxy_checks: dict[str, Any]
    sample_rows: list[dict[str, Any]]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "feature_asof_range": self.feature_asof_range,
            "etf_feature_row_count": self.etf_feature_row_count,
            "market_risk_row_count": self.market_risk_row_count,
            "checked_ticker_count": self.checked_ticker_count,
            "sampled_tickers": self.sampled_tickers,
            "sanity_status": self.sanity_status,
            "coverage_checks": self.coverage_checks,
            "calculation_checks": self.calculation_checks,
            "nav_join_checks": self.nav_join_checks,
            "outlier_checks": self.risk_proxy_checks,
            "risk_proxy_checks": self.risk_proxy_checks,
            "sample_rows": self.sample_rows,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _aggregate_status(*statuses: str) -> str:
    if any(s == "error" for s in statuses):
        return "error"
    if any(s == "warn" for s in statuses):
        return "warn"
    return "ok"


def build_sanity_report(
    db_path: Path = DEFAULT_DB_PATH,
    sample_count: int = DEFAULT_SAMPLE_TICKER_COUNT,
) -> SanityReport:
    """ML feature dataset 의 sanity report 생성 — 외부 source 호출 0건."""
    coverage = _check_coverage(db_path)
    latest_asof = coverage.feature_asof_end
    sampled: list[str] = []
    calc = CalculationChecks(
        status="ok",
        checked_ticker_count=0,
        checked_fields=CHECKED_FIELDS,
    )
    if latest_asof is not None and coverage.etf_feature_row_count > 0:
        sampled = pick_sample_tickers(db_path, latest_asof, n=sample_count)
        calc = _check_calculations(db_path, sampled, latest_asof)

    nav_check = _check_nav_join(db_path)
    risk_check = _check_risk_proxy(db_path)

    sample_rows: list[dict[str, Any]] = []
    if latest_asof is not None and sampled:
        sample_rows = fetch_sample_rows(db_path, sampled, latest_asof)

    overall = _aggregate_status(
        coverage.status, calc.status, nav_check.status, risk_check.status
    )

    all_warnings: list[str] = []
    all_errors: list[str] = []
    for sub in (coverage, calc, nav_check, risk_check):
        all_warnings.extend(sub.warnings)
        all_errors.extend(sub.errors)

    return SanityReport(
        generated_at=_utcnow_iso(),
        feature_asof_range={
            "start": coverage.feature_asof_start,
            "end": coverage.feature_asof_end,
            "trading_days": coverage.trading_days,
        },
        etf_feature_row_count=coverage.etf_feature_row_count,
        market_risk_row_count=coverage.market_risk_row_count,
        checked_ticker_count=calc.checked_ticker_count,
        sampled_tickers=sampled,
        sanity_status=overall,
        coverage_checks=asdict(coverage),
        calculation_checks=asdict(calc),
        nav_join_checks=asdict(nav_check),
        risk_proxy_checks=asdict(risk_check),
        sample_rows=sample_rows,
        warnings=all_warnings,
        errors=all_errors,
    )


__all__ = [
    "CALC_ABS_TOL",
    "CALC_REL_TOL",
    "CHECKED_FIELDS",
    "RISK_PROXY_FIELDS",
    "SanityReport",
    "build_sanity_report",
]
