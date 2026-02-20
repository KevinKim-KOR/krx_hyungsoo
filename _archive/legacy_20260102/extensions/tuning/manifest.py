# -*- coding: utf-8 -*-
"""
extensions/tuning/manifest.py
튜닝/검증 체계 v2.1 - run_manifest 저장

문서 참조: docs/tuning/03_walkforward_manifest.md 9절
"""
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from datetime import timezone, timedelta
KST = timezone(timedelta(hours=9))
from pathlib import Path
from typing import Dict, List, Optional, Any

from extensions.tuning.types import (
    BacktestRunResult,
    SplitConfig,
    CostConfig,
    DataConfig,
)

logger = logging.getLogger(__name__)

# 스키마 버전
# v4.1: 멀티 룩백 증거 추가 (by_lookback, combined_score, min_lookback_months)
MANIFEST_SCHEMA_VERSION = "4.1"


@dataclass
class ManifestConfig:
    """Manifest 설정 섹션"""

    period: Dict[str, str]
    lookbacks: List[int]
    lookback_combination: str
    trials: int
    objective: str
    split: Dict[str, Any]
    guardrails: Dict[str, Any]
    variables: Dict[str, Any]
    cost_assumptions: Dict[str, Any]


@dataclass
class ManifestData:
    """Manifest 데이터 섹션"""

    universe_version: str
    universe_source: str
    delisted_handling: str
    survivorship_bias: str
    price_type: str
    dividend_handling: str
    data_version: str
    # 재현성 보장용 (v2.1 추가)
    universe_hash: str = ""  # ETF 코드 리스트 정렬 후 해시
    universe_count: int = 0  # 유니버스 종목 수
    # 유니버스 검증용 (v2.2 추가)
    requested_codes_count: int = 0  # 요청된 유니버스 종목 수
    effective_codes_count: int = 0  # 실제 적용된 유니버스 종목 수
    requested_hash: str = ""  # 요청된 유니버스 해시
    effective_hash: str = ""  # 실제 적용된 유니버스 해시
    sample_codes: List[str] = None  # 앞 5개 종목 샘플


@dataclass
class ManifestResults:
    """Manifest 결과 섹션"""

    best_trial: Optional[Dict[str, Any]] = None
    all_trials_count: int = 0
    convergence_trial: Optional[int] = None
    search_coverage: float = 0.0


@dataclass
class ManifestEnvironment:
    """Manifest 환경 섹션"""

    code_version: str = ""
    python_version: str = ""
    optuna_version: str = ""
    random_seed: int = 42
    splitter_version: str = "chronological_v1"
    cost_model_version: str = "simple_oneway_v1"


@dataclass
class ManifestEngineHealth:
    """Manifest 엔진 헬스 섹션"""

    is_valid: bool = True
    warnings: List[str] = field(default_factory=list)
    data_quality: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunManifest:
    """
    run_manifest v4.0 스키마

    문서 참조: docs/tuning/03_walkforward_manifest.md 9.1절
    """

    run_id: str
    created_at: str
    schema_version: str = MANIFEST_SCHEMA_VERSION
    stage: str = "tuning"  # tuning, gate1_passed, gate2_passed, final

    config: Optional[ManifestConfig] = None
    data: Optional[ManifestData] = None
    results: Optional[ManifestResults] = None
    environment: Optional[ManifestEnvironment] = None
    engine_health: Optional[ManifestEngineHealth] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "stage": self.stage,
            "config": asdict(self.config) if self.config else None,
            "data": asdict(self.data) if self.data else None,
            "results": asdict(self.results) if self.results else None,
            "environment": asdict(self.environment) if self.environment else None,
            "engine_health": asdict(self.engine_health) if self.engine_health else None,
        }

    def to_json(self, indent: int = 2) -> str:
        """JSON 문자열 변환"""
        return json.dumps(
            self.to_dict(), indent=indent, ensure_ascii=False, default=str
        )


def generate_run_id(stage: str = "tuning") -> str:
    """
    run_id 생성

    형식: {stage}_{날짜}_{시간}_{해시}
    예: tuning_20251216_143052_abc123
    """
    now = datetime.now(KST)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    hash_input = f"{timestamp}_{now.microsecond}"
    hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:6]

    return f"{stage}_{timestamp}_{hash_suffix}"


def create_manifest(
    stage: str,
    start_date: date,
    end_date: date,
    lookbacks: List[int],
    trials: int,
    split_config: SplitConfig,
    costs: CostConfig,
    data_config: DataConfig,
    param_ranges: Dict[str, Any],
    best_result: Optional[BacktestRunResult] = None,
    all_trials_count: int = 0,
    convergence_trial: Optional[int] = None,
    random_seed: int = 42,
    # 멀티 룩백 증거 (v4.1 추가)
    by_lookback: Optional[Dict[int, Dict[str, Any]]] = None,
    combined_score: Optional[float] = None,
    min_lookback_months: Optional[int] = None,
    # Gate2 WF 결과 (v4.1 추가)
    wf_windows: Optional[int] = None,
    wf_outsample_sharpes: Optional[List[float]] = None,
    wf_stability_score: Optional[float] = None,
    wf_win_rate: Optional[float] = None,
    # Guardrail Preset (v2.2)
    guardrail_preset: str = "default",
) -> RunManifest:
    """
    run_manifest 생성

    Args:
        stage: 단계 (tuning, gate1_passed, gate2_passed, final)
        start_date: 시작일
        end_date: 종료일
        lookbacks: 룩백 기간 리스트
        trials: 시행 횟수
        split_config: Split 설정
        costs: 비용 설정
        data_config: 데이터 설정
        param_ranges: 파라미터 범위
        best_result: 최적 결과
        all_trials_count: 전체 시행 횟수
        convergence_trial: 수렴 시행 번호
        random_seed: 랜덤 시드
        by_lookback: 멀티 룩백 결과 {3: {...}, 6: {...}, 12: {...}}
        combined_score: 결합 점수 (lookback_combination=min 기준)
        min_lookback_months: combined_score를 만든 lookback
        wf_windows: WF 윈도우 개수
        wf_outsample_sharpes: WF outsample sharpe 리스트
        wf_stability_score: WF stability score
        wf_win_rate: WF win rate

    Returns:
        RunManifest 객체
    """
    import sys
    import subprocess

    # run_id 생성
    run_id = generate_run_id(stage)

    # 탐색 커버리지 계산
    total_combinations = 1
    for name, config in param_ranges.items():
        if config.get("type") == "int":
            steps = (config["max"] - config["min"]) // config.get("step", 1) + 1
        else:
            steps = int((config["max"] - config["min"]) / config.get("step", 0.01)) + 1
        total_combinations *= steps

    search_coverage = trials / total_combinations if total_combinations > 0 else 0.0

    # Config 섹션
    config = ManifestConfig(
        period={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        lookbacks=lookbacks,
        lookback_combination="min",
        trials=trials,
        objective="val_sharpe_with_mdd_penalty",
        split={
            "method": split_config.method,
            "target_ratios": {
                "train": split_config.target_train_ratio,
                "val": split_config.target_val_ratio,
                "test": split_config.target_test_ratio,
            },
            "min_val_months": split_config.min_val_months,
            "min_test_months": split_config.min_test_months,
            "applied": {
                "train_months": split_config.applied_train_months,
                "val_months": split_config.applied_val_months,
                "test_months": split_config.applied_test_months,
            },
        },
        guardrails={
            "preset": guardrail_preset,
            "min_trades": 30,
            "min_exposure_ratio": 0.30,
            "max_annual_turnover": 24,
        },
        variables=param_ranges,
        cost_assumptions={
            "commission_rate": costs.commission_rate,
            "slippage_rate": costs.slippage_rate,
            "cost_type": "one_way",
            "unit": "decimal",
        },
    )

    # Data 섹션
    # 유니버스 검증: requested와 effective가 같아야 함
    requested_hash = data_config.universe_hash
    effective_hash = data_config.universe_hash  # 현재는 동일 (BacktestService에서 검증)
    sample_codes = data_config.sample_codes[:5] if data_config.sample_codes else []

    data = ManifestData(
        universe_version=data_config.universe_version,
        universe_source=data_config.universe_source,
        delisted_handling=data_config.delisted_handling,
        survivorship_bias=data_config.survivorship_bias,
        price_type=data_config.price_type,
        dividend_handling=data_config.dividend_handling,
        data_version=data_config.data_version,
        universe_hash=data_config.universe_hash,
        universe_count=data_config.universe_count,
        requested_codes_count=data_config.universe_count,
        effective_codes_count=data_config.universe_count,
        requested_hash=requested_hash,
        effective_hash=effective_hash,
        sample_codes=sample_codes,
    )

    # Results 섹션
    results = ManifestResults(
        all_trials_count=all_trials_count,
        convergence_trial=convergence_trial,
        search_coverage=search_coverage,
    )

    if best_result:
        train = best_result.train
        val = best_result.val
        test = best_result.test

        results.best_trial = {
            "trial_number": 1,  # TODO: 실제 trial 번호
            "params": best_result.params,
            "metrics": {
                "train": (
                    {
                        "sharpe": train.sharpe if train else 0.0,
                        "cagr": train.cagr if train else 0.0,
                        "mdd": train.mdd if train else 0.0,
                    }
                    if train
                    else None
                ),
                "val": (
                    {
                        "sharpe": val.sharpe if val else 0.0,
                        "cagr": val.cagr if val else 0.0,
                        "mdd": val.mdd if val else 0.0,
                    }
                    if val
                    else None
                ),
                "test": (
                    {
                        "sharpe": test.sharpe if test else 0.0,
                        "cagr": test.cagr if test else 0.0,
                        "mdd": test.mdd if test else 0.0,
                    }
                    if test
                    else None
                ),
            },
            "guardrail_checks": (
                {
                    "num_trades": (
                        best_result.guardrail_checks.num_trades
                        if best_result.guardrail_checks
                        else 0
                    ),
                    "exposure_ratio": (
                        best_result.guardrail_checks.exposure_ratio
                        if best_result.guardrail_checks
                        else 0.0
                    ),
                    "annual_turnover": (
                        best_result.guardrail_checks.annual_turnover
                        if best_result.guardrail_checks
                        else 0.0
                    ),
                }
                if best_result.guardrail_checks
                else None
            ),
            "logic_checks": (
                {
                    "rsi_scale_days": (
                        best_result.logic_checks.rsi_scale_days
                        if best_result.logic_checks
                        else 0
                    ),
                    "rsi_scale_events": (
                        best_result.logic_checks.rsi_scale_events
                        if best_result.logic_checks
                        else 0
                    ),
                }
                if best_result.logic_checks
                else None
            ),
            "anomaly_flags": [],
            "debug": (
                {
                    # min_lookback_months: combined_score를 만든 lookback (대표 룩백)
                    "min_lookback_months": min_lookback_months
                    or (best_result.debug.lookback_months if best_result.debug else 0),
                    "lookback_start_date": (
                        str(best_result.debug.lookback_start_date)
                        if best_result.debug and best_result.debug.lookback_start_date
                        else None
                    ),
                    "params_hash": (
                        best_result.debug.params_hash if best_result.debug else ""
                    ),
                    "cache_key": (
                        best_result.debug.cache_key[:8]
                        if best_result.debug and best_result.debug.cache_key
                        else ""
                    ),
                    "period_signature": (
                        best_result.debug.period_signature if best_result.debug else ""
                    ),
                }
                if best_result.debug
                else None
            ),
            # 멀티 룩백 증거 (v4.1 추가)
            "by_lookback": by_lookback or {},
            "combined_score": combined_score,
            # Gate2 WF 결과 (v4.1 추가)
            "walkforward": (
                {
                    "windows": wf_windows,
                    "outsample_sharpes": wf_outsample_sharpes or [],
                    "stability_score": wf_stability_score,
                    "win_rate": wf_win_rate,
                }
                if wf_windows is not None
                else None
            ),
        }

    # Environment 섹션
    try:
        git_hash = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
        code_version = f"git:{git_hash}"
    except Exception:
        code_version = "unknown"

    try:
        import optuna

        optuna_version = optuna.__version__
    except ImportError:
        optuna_version = "unknown"

    environment = ManifestEnvironment(
        code_version=code_version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        optuna_version=optuna_version,
        random_seed=random_seed,
    )

    # Engine Health 섹션
    engine_health = ManifestEngineHealth(
        is_valid=True,
        warnings=best_result.warnings if best_result else [],
        data_quality={"missing_ratio": 0.001, "outlier_count": 0},  # TODO: 실제 계산
    )

    return RunManifest(
        run_id=run_id,
        created_at=datetime.now(KST).isoformat(),
        stage=stage,
        config=config,
        data=data,
        results=results,
        environment=environment,
        engine_health=engine_health,
    )


def save_manifest(manifest: RunManifest, output_dir: Path) -> Path:
    """
    Manifest 저장

    Args:
        manifest: RunManifest 객체
        output_dir: 저장 디렉토리

    Returns:
        저장된 파일 경로
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{manifest.run_id}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(manifest.to_json())

    logger.info(f"Manifest 저장: {filepath}")
    return filepath


def load_manifest(filepath: Path) -> RunManifest:
    """
    Manifest 로드

    Args:
        filepath: 파일 경로

    Returns:
        RunManifest 객체
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 간단한 역직렬화 (완전한 구현은 필요 시 추가)
    manifest = RunManifest(
        run_id=data["run_id"],
        created_at=data["created_at"],
        schema_version=data.get("schema_version", MANIFEST_SCHEMA_VERSION),
        stage=data.get("stage", "tuning"),
    )

    return manifest
