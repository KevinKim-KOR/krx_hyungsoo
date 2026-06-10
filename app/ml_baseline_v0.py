"""ML Baseline v0 — orchestrator (2026-06-11).

지시문 §3 — 현재 feature dataset 이 과거 구간에서 (1) 상승 후보 발굴 baseline
및 (2) 위험 구간 감지 baseline 으로 의미가 있었는지 룩백 검증.

본 모듈은 4 sub-step:
- targets 생성 (candidate / risk) — `app/ml_baseline_targets.py`.
- candidate baseline 평가 — `app/ml_baseline_candidate.py`.
- risk baseline 평가 — `app/ml_baseline_risk.py`.
- leakage / coverage check 통합.

CLI/API 가 호출하는 단일 entry: `build_baseline_report`.
ML 학습 / 외부 source / 매수·매도 판단 / 위험 threshold 0건.
"""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.market_regime import KODEX200_TICKER
from app.ml_baseline_candidate import (
    CandidateBaselineResult,
    evaluate_candidate_baseline,
)
from app.ml_baseline_risk import RiskBaselineResult, evaluate_risk_baseline
from app.ml_baseline_targets import (
    MAX_HORIZON,
    LeakageReport,
    build_candidate_targets,
    build_risk_targets,
    evaluate_leakage,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CoverageSummary:
    feature_asof_start: Optional[str]
    feature_asof_end: Optional[str]
    trading_days: int
    etf_feature_row_count: int
    market_risk_row_count: int


def _load_coverage(db_path: Path) -> CoverageSummary:
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT COUNT(*), MIN(asof), MAX(asof), COUNT(DISTINCT asof) "
            "FROM etf_ml_feature_daily"
        )
        row = cur.fetchone()
        etf_count = int(row[0] or 0)
        asof_start = row[1]
        asof_end = row[2]
        trading_days = int(row[3] or 0)
        cur = con.execute("SELECT COUNT(*) FROM market_risk_feature_daily")
        mkt_count = int(cur.fetchone()[0] or 0)
    return CoverageSummary(
        feature_asof_start=asof_start,
        feature_asof_end=asof_end,
        trading_days=trading_days,
        etf_feature_row_count=etf_count,
        market_risk_row_count=mkt_count,
    )


def _evaluated_range(
    db_path: Path,
    candidate: CandidateBaselineResult,
    risk: RiskBaselineResult,
    coverage: CoverageSummary,
) -> dict[str, Any]:
    """평가 가능 구간 = feature_asof_range 의 앞쪽 (전체 - MAX_HORIZON).

    end 는 평가에 사용된 마지막 asof (= feature_asof DESC 정렬에서 MAX_HORIZON
    번째 이전). evaluated_days 는 candidate / risk 평가 거래일 중 큰 쪽.
    """
    if coverage.trading_days <= MAX_HORIZON:
        return {"start": None, "end": None, "evaluated_days": 0}
    # 평가 마지막 asof 는 SQL 에서 직접 계산.
    with sqlite3.connect(str(db_path)) as con:
        cur = con.execute(
            "SELECT asof FROM ("
            "  SELECT DISTINCT asof FROM etf_ml_feature_daily ORDER BY asof DESC "
            "  LIMIT ? OFFSET ?"
            ") ORDER BY asof DESC LIMIT 1",
            (1, MAX_HORIZON),
        )
        row = cur.fetchone()
        evaluated_end = row[0] if row else None
    evaluated_days = max(candidate.evaluated_days, risk.evaluated_days)
    return {
        "start": coverage.feature_asof_start,
        "end": evaluated_end,
        "evaluated_days": evaluated_days,
    }


@dataclass
class BaselineReport:
    status: str  # ok / warn / insufficient_history / error
    generated_at: str
    feature_asof_range: dict[str, Any]
    evaluated_asof_range: dict[str, Any]
    coverage_checks: dict[str, Any]
    candidate_baseline: dict[str, Any]
    risk_baseline: dict[str, Any]
    leakage_checks: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _aggregate_status(
    coverage: CoverageSummary,
    candidate: CandidateBaselineResult,
    risk: RiskBaselineResult,
    leakage: LeakageReport,
) -> str:
    if leakage.feature_future_data_leakage_detected:
        return "error"
    statuses = {candidate.status, risk.status}
    if "error" in statuses:
        return "error"
    if coverage.trading_days <= MAX_HORIZON:
        return "insufficient_history"
    if "insufficient_history" in statuses:
        return "insufficient_history"
    if "warn" in statuses:
        return "warn"
    return "ok"


def build_baseline_report(
    db_path: Path = DEFAULT_DB_PATH,
    kodex_ticker: str = KODEX200_TICKER,
) -> BaselineReport:
    """ML Baseline v0 룩백 검증 단일 entry."""
    warnings: list[str] = []
    errors: list[str] = []

    coverage = _load_coverage(db_path)
    if coverage.etf_feature_row_count == 0:
        errors.append(
            "etf_ml_feature_daily 가 비어있음 — feature 생성 CLI 먼저 실행 필요"
        )
    if coverage.market_risk_row_count == 0:
        errors.append(
            "market_risk_feature_daily 가 비어있음 — feature 생성 CLI 먼저 실행 필요"
        )

    candidate_rows, c_errs = build_candidate_targets(db_path, kodex_ticker)
    errors.extend(c_errs)
    risk_rows, r_errs = build_risk_targets(db_path, kodex_ticker)
    errors.extend(r_errs)

    candidate_result = evaluate_candidate_baseline(db_path, candidate_rows)
    risk_result = evaluate_risk_baseline(db_path, risk_rows)
    leakage = evaluate_leakage(db_path, candidate_rows, risk_rows)

    warnings.extend(candidate_result.warnings)
    warnings.extend(risk_result.warnings)
    errors.extend(candidate_result.errors)
    errors.extend(risk_result.errors)

    status = _aggregate_status(coverage, candidate_result, risk_result, leakage)
    if errors and status == "ok":
        status = "warn"

    return BaselineReport(
        status=status,
        generated_at=_utcnow_iso(),
        feature_asof_range={
            "start": coverage.feature_asof_start,
            "end": coverage.feature_asof_end,
            "trading_days": coverage.trading_days,
        },
        evaluated_asof_range=_evaluated_range(
            db_path, candidate_result, risk_result, coverage
        ),
        coverage_checks={
            "etf_feature_row_count": coverage.etf_feature_row_count,
            "market_risk_row_count": coverage.market_risk_row_count,
            "trading_days": coverage.trading_days,
            "max_horizon_tail_excluded": MAX_HORIZON,
        },
        candidate_baseline=asdict(candidate_result),
        risk_baseline=asdict(risk_result),
        leakage_checks=asdict(leakage),
        warnings=warnings,
        errors=errors,
    )
