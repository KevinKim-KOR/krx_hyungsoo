# -*- coding: utf-8 -*-
"""
extensions/tuning/gates.py
튜닝/검증 체계 v2.1 - Live 승격 게이트

문서 참조: docs/tuning/02_objective_gates.md 7절
"""
import logging
import os
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Any

from extensions.tuning.types import (
    BacktestRunResult,
    CostConfig,
    DataConfig,
    SplitConfig,
)
from extensions.tuning.guardrails import (
    check_guardrails,
    check_mdd_consistency,
    check_logic_rsi,
    check_anomalies,
    has_critical_anomaly,
)
from extensions.tuning.runner import run_backtest_for_final

# 테스트 모드 플래그: 환경변수 또는 명시적 설정으로만 활성화
# 실전 경로에서 skip_logic_check/skip_mdd_check 사용 방지
_TEST_MODE = os.environ.get("TUNING_TEST_MODE", "").lower() in ("1", "true", "yes")

# 운영 허용 stage (analysis는 제외)
PRODUCTION_ALLOWED_STAGES = {"tuning", "gate1_passed", "gate2_passed", "final"}


def set_test_mode(enabled: bool) -> None:
    """테스트 모드 설정 (테스트 코드에서만 호출)"""
    global _TEST_MODE
    _TEST_MODE = enabled


def is_test_mode() -> bool:
    """현재 테스트 모드 여부"""
    return _TEST_MODE


def validate_manifest_stage_for_production(stage: str) -> bool:
    """
    manifest stage가 운영 파이프라인에서 사용 가능한지 검증

    Args:
        stage: manifest의 stage 값

    Returns:
        True면 운영 가능, False면 분석용

    Raises:
        ValueError: analysis stage를 운영에 사용하려 할 때
    """
    if stage == "analysis":
        raise ValueError(
            "analysis stage manifest는 운영 파이프라인에서 사용할 수 없습니다. "
            "분석용 결과가 Live 후보로 섞이는 것을 방지합니다."
        )
    return stage in PRODUCTION_ALLOWED_STAGES


logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """게이트 통과 결과"""

    passed: bool
    gate_name: str
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrialCandidate:
    """Live 승격 후보 Trial"""

    trial_number: int
    params: Dict[str, Any]
    result: BacktestRunResult
    val_sharpe: float
    gate1_result: Optional[GateResult] = None
    gate2_result: Optional[GateResult] = None
    gate3_result: Optional[GateResult] = None

    @property
    def status(self) -> str:
        """현재 상태"""
        if self.gate3_result and self.gate3_result.passed:
            return "gate3_passed"
        elif self.gate2_result and self.gate2_result.passed:
            return "gate2_passed"
        elif self.gate1_result and self.gate1_result.passed:
            return "gate1_passed"
        elif self.gate1_result and not self.gate1_result.passed:
            return "gate1_failed"
        return "pending"


def check_gate1(
    result: BacktestRunResult,
    top_n: int = 5,
    all_results: Optional[List[BacktestRunResult]] = None,
    skip_logic_check: bool = False,
    skip_mdd_check: bool = False,
) -> GateResult:
    """
    Gate 1: Val 기준 Top-N 선정

    문서 참조: docs/tuning/02_objective_gates.md 7.2절

    조건:
    - Val Sharpe 기준 상위 N개
    - 가드레일 통과 필수
    - 이상치 경고(🔴) 없어야 함
    - MDD 일관성 Gate 통과
    - Logic Check (RSI 실효성) 통과

    Args:
        result: 백테스트 결과
        top_n: 상위 N개 (기본 5)
        all_results: 전체 결과 리스트 (Top-N 판단용)
        skip_logic_check: Logic Check 건너뛰기 (TEST_MODE에서만 허용)
        skip_mdd_check: MDD 일관성 체크 건너뛰기 (TEST_MODE에서만 허용)

    Returns:
        GateResult

    Raises:
        RuntimeError: TEST_MODE가 아닌데 skip 플래그 사용 시
    """
    # 실전 경로 보호: TEST_MODE가 아니면 skip 플래그 사용 금지
    if (skip_logic_check or skip_mdd_check) and not _TEST_MODE:
        raise RuntimeError(
            "skip_logic_check/skip_mdd_check는 TEST_MODE에서만 사용 가능합니다. "
            "환경변수 TUNING_TEST_MODE=1 설정 또는 set_test_mode(True) 호출 필요."
        )

    failures = []
    warnings = []

    # 1. 가드레일 통과
    if not check_guardrails(result):
        failures.append("가드레일 미통과")
        if result.guardrail_checks:
            failures.extend(result.guardrail_checks.failures)

    # 2. 이상치 경고 확인
    anomalies = check_anomalies(result, stage="tuning")
    if has_critical_anomaly(anomalies):
        critical = [a for a in anomalies if a.severity == "critical"]
        failures.append(f"이상치 경고: {critical[0].code}")

    # 경고 수준 이상치는 warnings에 추가
    warning_anomalies = [a for a in anomalies if a.severity == "warning"]
    for a in warning_anomalies:
        warnings.append(f"{a.code}: {a.message}")

    # 3. MDD 일관성 Gate
    if not skip_mdd_check and not check_mdd_consistency(result):
        failures.append("MDD 일관성 미통과")

    # 4. Logic Check (RSI 실효성)
    if not skip_logic_check and not check_logic_rsi(result):
        failures.append("RSI 실효성 미통과")

    # 5. Top-N 판단 (all_results가 있는 경우)
    is_top_n = True
    if all_results:
        val_sharpes = sorted([r.val.sharpe for r in all_results if r.val], reverse=True)
        if result.val:
            current_sharpe = result.val.sharpe
            if len(val_sharpes) >= top_n:
                threshold = val_sharpes[top_n - 1]
                is_top_n = current_sharpe >= threshold

            if not is_top_n:
                failures.append(f"Val Sharpe Top-{top_n} 미달")

    passed = len(failures) == 0

    return GateResult(
        passed=passed,
        gate_name="Gate 1: Val Top-N",
        failures=failures,
        warnings=warnings,
        metadata={
            "val_sharpe": result.val.sharpe if result.val else 0.0,
            "is_top_n": is_top_n,
        },
    )


def deduplicate_top_n_candidates(
    candidates: List[Dict[str, Any]], top_n: int = 5
) -> List[Dict[str, Any]]:
    """
    Gate1 Top-N 후보에서 params_hash 중복 제거

    Args:
        candidates: 후보 리스트 [{'params_hash': str, 'val_sharpe': float, ...}, ...]
        top_n: 상위 N개

    Returns:
        중복 제거된 후보 리스트 (최대 top_n개)
    """
    seen_hashes = set()
    deduped = []
    duplicates = []

    # Val Sharpe 기준 정렬
    sorted_candidates = sorted(
        candidates, key=lambda x: x.get("val_sharpe", 0), reverse=True
    )

    for c in sorted_candidates:
        params_hash = c.get("params_hash", "")
        if params_hash and params_hash in seen_hashes:
            duplicates.append({**c, "dup_of": params_hash})
            continue

        if params_hash:
            seen_hashes.add(params_hash)
        deduped.append(c)

        if len(deduped) >= top_n:
            break

    logger.info(
        f"Gate1 Top-N 선정: candidates={len(candidates)}, "
        f"selected_top_n={len(deduped)}, dedup_removed={len(duplicates)}"
    )

    return deduped


def check_gate2(
    result: BacktestRunResult,
    wf_results: List[Dict[str, float]],
    min_stability_score: float = 1.0,
    min_win_rate: float = 0.60,
) -> GateResult:
    """
    Gate 2: Walk-Forward 안정성 통과

    문서 참조: docs/tuning/02_objective_gates.md 7.2절

    조건:
    - 미니 Walk-Forward 실행 (3~5개 윈도우)
    - stability_score ≥ 1.0
    - win_rate ≥ 60% (Sharpe > 0인 윈도우 비율)

    Args:
        result: 백테스트 결과
        wf_results: Walk-Forward 결과 리스트 [{'sharpe': float}, ...]
        min_stability_score: 최소 안정성 점수
        min_win_rate: 최소 승률

    Returns:
        GateResult
    """
    import numpy as np

    failures = []
    warnings = []

    if not wf_results:
        failures.append("Walk-Forward 결과 없음")
        return GateResult(
            passed=False,
            gate_name="Gate 2: WF 안정성",
            failures=failures,
            warnings=warnings,
        )

    # Sharpe 리스트 추출
    sharpe_list = [r.get("sharpe", 0.0) for r in wf_results]

    # 안정성 점수 계산
    mean_sharpe = np.mean(sharpe_list)
    std_sharpe = np.std(sharpe_list)
    epsilon = 0.1
    stability_score = mean_sharpe / (std_sharpe + epsilon)

    # 승률 계산
    wins = sum(1 for s in sharpe_list if s > 0)
    win_rate = wins / len(sharpe_list)

    # 조건 체크
    if stability_score < min_stability_score:
        failures.append(
            f"안정성 점수 미달: {stability_score:.2f} < {min_stability_score}"
        )

    if win_rate < min_win_rate:
        failures.append(f"승률 미달: {win_rate:.1%} < {min_win_rate:.0%}")

    passed = len(failures) == 0

    return GateResult(
        passed=passed,
        gate_name="Gate 2: WF 안정성",
        failures=failures,
        warnings=warnings,
        metadata={
            "stability_score": stability_score,
            "win_rate": win_rate,
            "mean_sharpe": mean_sharpe,
            "std_sharpe": std_sharpe,
            "n_windows": len(sharpe_list),
        },
    )


def check_gate3(
    result: BacktestRunResult,
    params: Dict[str, Any],
    start_date: date,
    end_date: date,
    lookback_months: int,
    trading_calendar: List[date],
    split_config: Optional[SplitConfig] = None,
    costs: Optional[CostConfig] = None,
    data_config: Optional[DataConfig] = None,
) -> GateResult:
    """
    Gate 3: Test 공개 + Live 후보 등록

    문서 참조: docs/tuning/02_objective_gates.md 7.2절

    조건:
    - Gate 1, 2 통과한 Trial만 Test 성과 공개
    - Live 적용 후보로 등록
    - 최종 선택은 사용자가 수동으로

    Args:
        result: 기존 백테스트 결과 (Train/Val만 있음)
        params: 전략 파라미터
        start_date: 시작일
        end_date: 종료일
        lookback_months: 룩백 기간
        trading_calendar: 거래일 리스트
        split_config: Split 설정
        costs: 비용 설정
        data_config: 데이터 설정

    Returns:
        GateResult (Test 결과 포함)
    """
    failures = []
    warnings = []

    # Test 백테스트 실행 (Gate 2 통과 후에만)
    final_result = run_backtest_for_final(
        params=params,
        start_date=start_date,
        end_date=end_date,
        lookback_months=lookback_months,
        trading_calendar=trading_calendar,
        split_config=split_config,
        costs=costs,
        data_config=data_config,
    )

    test = final_result.test
    val = final_result.val

    if test is None:
        failures.append("Test 백테스트 실패")
        return GateResult(
            passed=False,
            gate_name="Gate 3: Test 공개",
            failures=failures,
            warnings=warnings,
        )

    # Val↓ Test↑↑ 이상치 체크 (Gate 3에서만)
    anomalies = check_anomalies(final_result, stage="gate3")
    if has_critical_anomaly(anomalies):
        critical = [a for a in anomalies if a.severity == "critical"]
        for a in critical:
            warnings.append(f"⚠️ {a.code}: {a.message}")

    # Test 결과 메타데이터
    metadata = {
        "test_sharpe": test.sharpe,
        "test_cagr": test.cagr,
        "test_mdd": test.mdd,
        "val_sharpe": val.sharpe if val else 0.0,
        "val_test_ratio": test.sharpe / val.sharpe if val and val.sharpe != 0 else 0.0,
    }

    # Gate 3는 항상 통과 (정보 제공 목적)
    # 최종 선택은 사용자가 수동으로
    passed = True

    return GateResult(
        passed=passed,
        gate_name="Gate 3: Test 공개",
        failures=failures,
        warnings=warnings,
        metadata=metadata,
    )


class LivePromotionGate:
    """
    Live 승격 게이트 관리자

    문서 참조: docs/tuning/02_objective_gates.md 7.1절

    프로세스:
    Gate 1: Val 기준 Top-N 선정
    Gate 2: Walk-Forward 안정성 통과
    Gate 3: Test 공개 + Live 후보 등록
    """

    def __init__(
        self,
        start_date: date,
        end_date: date,
        trading_calendar: List[date],
        lookback_months: int = 12,
        top_n: int = 5,
        split_config: Optional[SplitConfig] = None,
        costs: Optional[CostConfig] = None,
        data_config: Optional[DataConfig] = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.trading_calendar = trading_calendar
        self.lookback_months = lookback_months
        self.top_n = top_n
        self.split_config = split_config
        self.costs = costs
        self.data_config = data_config

        self.candidates: List[TrialCandidate] = []

    def add_candidate(
        self, trial_number: int, params: Dict[str, Any], result: BacktestRunResult
    ) -> TrialCandidate:
        """후보 추가"""
        val_sharpe = result.val.sharpe if result.val else 0.0

        candidate = TrialCandidate(
            trial_number=trial_number,
            params=params,
            result=result,
            val_sharpe=val_sharpe,
        )

        self.candidates.append(candidate)
        return candidate

    def run_gate1(self) -> List[TrialCandidate]:
        """Gate 1 실행: Val Top-N 선정"""
        all_results = [c.result for c in self.candidates]

        for candidate in self.candidates:
            candidate.gate1_result = check_gate1(
                result=candidate.result, top_n=self.top_n, all_results=all_results
            )

        # Gate 1 통과 후보 반환
        return [c for c in self.candidates if c.gate1_result and c.gate1_result.passed]

    def run_gate2(
        self, candidate: TrialCandidate, wf_results: List[Dict[str, float]]
    ) -> GateResult:
        """Gate 2 실행: WF 안정성"""
        candidate.gate2_result = check_gate2(
            result=candidate.result, wf_results=wf_results
        )
        return candidate.gate2_result

    def run_gate3(self, candidate: TrialCandidate) -> GateResult:
        """Gate 3 실행: Test 공개"""
        if not (candidate.gate1_result and candidate.gate1_result.passed):
            return GateResult(
                passed=False, gate_name="Gate 3: Test 공개", failures=["Gate 1 미통과"]
            )

        if not (candidate.gate2_result and candidate.gate2_result.passed):
            return GateResult(
                passed=False, gate_name="Gate 3: Test 공개", failures=["Gate 2 미통과"]
            )

        candidate.gate3_result = check_gate3(
            result=candidate.result,
            params=candidate.params,
            start_date=self.start_date,
            end_date=self.end_date,
            lookback_months=self.lookback_months,
            trading_calendar=self.trading_calendar,
            split_config=self.split_config,
            costs=self.costs,
            data_config=self.data_config,
        )

        return candidate.gate3_result

    def get_live_candidates(self) -> List[TrialCandidate]:
        """Live 승격 후보 반환 (Gate 1, 2 통과)"""
        return [
            c
            for c in self.candidates
            if c.gate1_result
            and c.gate1_result.passed
            and c.gate2_result
            and c.gate2_result.passed
        ]

    def get_final_candidates(self) -> List[TrialCandidate]:
        """최종 후보 반환 (Gate 3 통과)"""
        return [c for c in self.candidates if c.gate3_result and c.gate3_result.passed]
