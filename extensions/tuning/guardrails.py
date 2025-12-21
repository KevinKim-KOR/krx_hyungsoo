# -*- coding: utf-8 -*-
"""
extensions/tuning/guardrails.py
튜닝/검증 체계 v2.1 - 가드레일 및 이상치 감지

문서 참조: docs/tuning/01_metrics_guardrails.md
"""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from extensions.tuning.types import (
    BacktestRunResult,
    BacktestMetrics,
    GuardrailChecks,
    LogicChecks,
    ANOMALY_THRESHOLDS,
)

logger = logging.getLogger(__name__)


@dataclass
class AnomalyFlag:
    """이상치 경고 플래그"""

    code: str  # 경고 코드
    message: str  # 경고 메시지
    severity: str  # 'warning' (🟡) or 'critical' (🔴)
    value: float  # 실제 값
    threshold: float  # 임계값


def check_guardrails(result: BacktestRunResult) -> bool:
    """
    가드레일 통과 여부 확인

    문서 참조: docs/tuning/02_objective_gates.md 6.2절

    Args:
        result: 백테스트 결과

    Returns:
        통과 여부 (하나라도 실패하면 False)
    """
    if result.guardrail_checks is None:
        logger.warning("guardrail_checks가 None입니다")
        return False

    g = result.guardrail_checks
    passed = g.passed

    if not passed:
        logger.info(f"가드레일 실패: {g.failures}")

    return passed


def check_mdd_consistency(
    result: BacktestRunResult, min_tolerance: float = 0.10
) -> bool:
    """
    MDD 일관성 Gate (강화)

    문서 참조: docs/tuning/02_objective_gates.md 7.2.1절

    조건: abs(MDD_val) <= max(abs(MDD_train) * 1.2, MIN_TOLERANCE)

    Args:
        result: 백테스트 결과
        min_tolerance: 최소 허용 임계값 (기본 10%)

    Returns:
        통과 여부
    """
    train = result.metrics.get("train")
    val = result.metrics.get("val")

    if train is None or val is None:
        return False

    train_mdd = abs(train.mdd)
    val_mdd = abs(val.mdd)

    # Train MDD가 작아도 최소 10%까지는 허용
    threshold = max(train_mdd * 1.2, min_tolerance)

    passed = val_mdd <= threshold

    if not passed:
        logger.info(
            f"MDD 일관성 실패: Val MDD({val_mdd:.2%}) > threshold({threshold:.2%})"
        )

    return passed


def check_logic_rsi(result: BacktestRunResult, min_days: int = 10) -> bool:
    """
    RSI 실효성 Logic Check

    문서 참조: docs/tuning/02_objective_gates.md 7.2.2절

    Args:
        result: 백테스트 결과
        min_days: RSI가 영향을 준 최소 일수

    Returns:
        통과 여부
    """
    if result.logic_checks is None:
        return True  # logic_checks가 없으면 통과 (선택적 체크)

    return result.logic_checks.rsi_scale_days >= min_days


def check_anomalies(
    result: BacktestRunResult, stage: str = "tuning"
) -> List[AnomalyFlag]:
    """
    이상치 감지 레이더

    문서 참조: docs/tuning/01_metrics_guardrails.md 4절

    Args:
        result: 백테스트 결과
        stage: 단계 ('tuning', 'gate1', 'gate2', 'gate3')

    Returns:
        이상치 경고 플래그 리스트
    """
    flags = []

    # Val 지표 기준 (튜닝 중에는 Val만 확인)
    val = result.metrics.get("val")
    train = result.metrics.get("train")

    if val is None:
        return flags

    # 1. Sharpe > 5.0 → 🔴
    if val.sharpe > ANOMALY_THRESHOLDS["sharpe_max"]:
        flags.append(
            AnomalyFlag(
                code="SHARPE_TOO_HIGH",
                message="산출/표본/누수 점검 필요",
                severity="critical",
                value=val.sharpe,
                threshold=ANOMALY_THRESHOLDS["sharpe_max"],
            )
        )

    # 2. CAGR > 100% → 🔴
    if val.cagr > ANOMALY_THRESHOLDS["cagr_max"]:
        flags.append(
            AnomalyFlag(
                code="CAGR_TOO_HIGH",
                message="비현실적 수익률, 누수 의심",
                severity="critical",
                value=val.cagr,
                threshold=ANOMALY_THRESHOLDS["cagr_max"],
            )
        )

    # 3. num_trades < 30 → 🟡
    if val.num_trades < ANOMALY_THRESHOLDS["min_trades"]:
        flags.append(
            AnomalyFlag(
                code="LOW_TRADES",
                message="표본 부족, 통계적 신뢰도 낮음",
                severity="warning",
                value=val.num_trades,
                threshold=ANOMALY_THRESHOLDS["min_trades"],
            )
        )

    # 4. exposure_ratio < 30% → 🟡
    if val.exposure_ratio < ANOMALY_THRESHOLDS["min_exposure"]:
        flags.append(
            AnomalyFlag(
                code="LOW_EXPOSURE",
                message="노출 부족, 대부분 현금 보유",
                severity="warning",
                value=val.exposure_ratio,
                threshold=ANOMALY_THRESHOLDS["min_exposure"],
            )
        )

    # 5. Val↓ Test↑↑ (Gate 3 이후에만)
    if stage == "gate3":
        test = result.metrics.get("test")
        if test is not None and val.sharpe < 0 and test.sharpe > 1.5:
            flags.append(
                AnomalyFlag(
                    code="VAL_TEST_DIVERGENCE",
                    message="Val/Test 괴리, 과적합 의심",
                    severity="critical",
                    value=test.sharpe,
                    threshold=1.5,
                )
            )

    # Train Sharpe 이상치 (참고용)
    if train is not None and train.sharpe > ANOMALY_THRESHOLDS["sharpe_max"]:
        flags.append(
            AnomalyFlag(
                code="TRAIN_SHARPE_TOO_HIGH",
                message="Train Sharpe 이상, 과적합 가능성",
                severity="warning",
                value=train.sharpe,
                threshold=ANOMALY_THRESHOLDS["sharpe_max"],
            )
        )

    return flags


def has_critical_anomaly(flags: List[AnomalyFlag]) -> bool:
    """🔴 경고가 있는지 확인"""
    return any(f.severity == "critical" for f in flags)


def format_anomaly_badge(flags: List[AnomalyFlag]) -> str:
    """이상치 배지 문자열 생성"""
    if not flags:
        return "✅ 정상"

    critical = [f for f in flags if f.severity == "critical"]
    warnings = [f for f in flags if f.severity == "warning"]

    if critical:
        return f"🔴 {critical[0].code}"
    elif warnings:
        return f"🟡 {warnings[0].code}"

    return "✅ 정상"


def calculate_guardrail_checks(
    metrics: BacktestMetrics,
    trading_days: int,
    total_buy_amount: float,
    total_sell_amount: float,
    avg_portfolio_value: float,
    position_days: int,
) -> GuardrailChecks:
    """
    가드레일 체크 값 계산

    문서 참조: docs/tuning/01_metrics_guardrails.md 3.1절

    Args:
        metrics: 백테스트 지표
        trading_days: 전체 거래일 수
        total_buy_amount: 연간 총 매수 금액
        total_sell_amount: 연간 총 매도 금액
        avg_portfolio_value: 평균 포트폴리오 가치
        position_days: 포지션 보유일 수

    Returns:
        GuardrailChecks 객체
    """
    # num_trades: 매수+매도 거래 횟수 합계
    num_trades = metrics.num_trades

    # exposure_ratio: 포지션 보유일 / 전체 거래일
    exposure_ratio = position_days / trading_days if trading_days > 0 else 0.0

    # annual_turnover: (연간 매수금액 + 연간 매도금액) / (2 × 평균 포트폴리오 가치)
    if avg_portfolio_value > 0:
        annual_turnover = (total_buy_amount + total_sell_amount) / (
            2 * avg_portfolio_value
        )
    else:
        annual_turnover = 0.0

    return GuardrailChecks(
        num_trades=num_trades,
        exposure_ratio=exposure_ratio,
        annual_turnover=annual_turnover,
    )


def calculate_logic_checks(rsi_scale_days: int, rsi_scale_events: int) -> LogicChecks:
    """
    Logic Checks 계산

    Args:
        rsi_scale_days: RSI가 비중 조절에 영향을 준 일수
        rsi_scale_events: RSI 기반 비중 조절 횟수

    Returns:
        LogicChecks 객체
    """
    return LogicChecks(rsi_scale_days=rsi_scale_days, rsi_scale_events=rsi_scale_events)


# 가드레일 실패 사유 코드 정의
GUARDRAIL_FAILURE_CODES = {
    "num_trades": "LOW_TRADES",
    "exposure_ratio": "LOW_EXPOSURE",
    "annual_turnover": "HIGH_TURNOVER",
}

ANOMALY_FAILURE_CODES = {
    "SHARPE_TOO_HIGH": "ANOMALY_SHARPE",
    "CAGR_TOO_HIGH": "ANOMALY_CAGR",
    "MDD_TOO_LOW": "ANOMALY_MDD",
}


def aggregate_failure_reasons(
    results: List[BacktestRunResult],
    anomalies_list: Optional[List[List[AnomalyFlag]]] = None,
) -> Dict[str, int]:
    """
    가드레일/이상치 실패 사유 집계

    Args:
        results: 백테스트 결과 리스트
        anomalies_list: 각 결과에 대한 이상치 플래그 리스트 (옵션)

    Returns:
        실패 사유별 카운트 딕셔너리
    """
    from collections import Counter

    failure_counts: Counter = Counter()

    for i, result in enumerate(results):
        # 가드레일 실패 집계
        if result.guardrail_checks and not result.guardrail_checks.passed:
            g = result.guardrail_checks
            if g.num_trades < g.min_trades:
                failure_counts["LOW_TRADES"] += 1
            if g.exposure_ratio < g.min_exposure:
                failure_counts["LOW_EXPOSURE"] += 1
            if g.annual_turnover > g.max_turnover:
                failure_counts["HIGH_TURNOVER"] += 1

        # 이상치 실패 집계
        if anomalies_list and i < len(anomalies_list):
            for anomaly in anomalies_list[i]:
                if anomaly.severity == "critical":
                    code = ANOMALY_FAILURE_CODES.get(anomaly.code, anomaly.code)
                    failure_counts[code] += 1

    return dict(failure_counts)


def format_failure_summary(
    failure_counts: Dict[str, int], total_trials: int, top_n: int = 3
) -> str:
    """
    실패 사유 요약 문자열 생성

    Args:
        failure_counts: 실패 사유별 카운트
        total_trials: 전체 시행 수
        top_n: 상위 N개 사유만 출력

    Returns:
        요약 문자열
    """
    if not failure_counts:
        return "  실패 사유 없음"

    total_failures = sum(failure_counts.values())
    failure_rate = total_failures / total_trials if total_trials > 0 else 0

    lines = [f"  전체 실패율: {failure_rate:.1%} ({total_failures}/{total_trials})"]
    lines.append(f"  실패 사유 Top{top_n}:")

    sorted_failures = sorted(failure_counts.items(), key=lambda x: x[1], reverse=True)
    for i, (code, count) in enumerate(sorted_failures[:top_n]):
        pct = count / total_failures * 100 if total_failures > 0 else 0
        lines.append(f"    {i + 1}. {code}: {count}건 ({pct:.0f}%)")

    return "\n".join(lines)
