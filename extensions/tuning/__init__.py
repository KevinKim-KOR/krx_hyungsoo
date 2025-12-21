# -*- coding: utf-8 -*-
"""
extensions/tuning/__init__.py
튜닝/검증 체계 v2.1 구현

문서 참조: docs/tuning/00_overview.md ~ 04_implementation.md
"""
from extensions.tuning.types import (
    BacktestMetrics,
    BacktestRunResult,
    GuardrailChecks,
    LogicChecks,
    DebugInfo,
    Period,
    SplitConfig,
    CostConfig,
    DataConfig,
    DEFAULT_COSTS,
    DEFAULT_GUARDRAILS,
    LOOKBACK_TRADING_DAYS,
    ANOMALY_THRESHOLDS,
    compute_params_hash,
    compute_universe_hash,
)
from extensions.tuning.guardrails import (
    check_guardrails,
    check_anomalies,
    check_mdd_consistency,
    check_logic_rsi,
    has_critical_anomaly,
    AnomalyFlag,
    aggregate_failure_reasons,
    format_failure_summary,
    GUARDRAIL_FAILURE_CODES,
    ANOMALY_FAILURE_CODES,
)
from extensions.tuning.objective import TuningObjective, calculate_score, create_tuning_objective
from extensions.tuning.split import (
    calculate_split,
    create_period,
    create_period_for_lookback,
    snap_start,
    snap_end,
    get_lookback_start,
)
from extensions.tuning.runner import (
    run_backtest_for_tuning,
    run_backtest_for_final,
)
from extensions.tuning.cache import TuningCache, make_cache_key, get_global_cache, clear_global_cache
from extensions.tuning.gates import (
    LivePromotionGate,
    TrialCandidate,
    GateResult,
    set_test_mode,
    is_test_mode,
    deduplicate_top_n_candidates,
    check_gate1,
    check_gate2,
    check_gate3,
)
from extensions.tuning.walkforward import (
    MiniWalkForward,
    WFWindow,
    WFResult,
    generate_windows,
    calculate_stability_score,
    calculate_win_rate,
)
from extensions.tuning.manifest import (
    RunManifest,
    create_manifest,
    save_manifest,
    load_manifest,
    generate_run_id,
    MANIFEST_SCHEMA_VERSION,
)

__all__ = [
    # Types
    "BacktestMetrics",
    "BacktestRunResult",
    "GuardrailChecks",
    "LogicChecks",
    "DebugInfo",
    "Period",
    "SplitConfig",
    "CostConfig",
    "DataConfig",
    "DEFAULT_COSTS",
    "DEFAULT_GUARDRAILS",
    "LOOKBACK_TRADING_DAYS",
    "ANOMALY_THRESHOLDS",
    "compute_params_hash",
    "compute_universe_hash",
    # Guardrails
    "check_guardrails",
    "check_anomalies",
    "check_mdd_consistency",
    "check_logic_rsi",
    "has_critical_anomaly",
    "AnomalyFlag",
    # Objective
    "TuningObjective",
    "calculate_score",
    "create_tuning_objective",
    # Split
    "calculate_split",
    "create_period",
    "create_period_for_lookback",
    "snap_start",
    "snap_end",
    "get_lookback_start",
    # Runner
    "run_backtest_for_tuning",
    "run_backtest_for_final",
    # Cache
    "TuningCache",
    "make_cache_key",
    "get_global_cache",
    "clear_global_cache",
    # Gates
    "LivePromotionGate",
    "TrialCandidate",
    "set_test_mode",
    "is_test_mode",
    "deduplicate_top_n_candidates",
    "GateResult",
    "check_gate1",
    "check_gate2",
    "check_gate3",
    # Walk-Forward
    "MiniWalkForward",
    "WFWindow",
    "WFResult",
    "generate_windows",
    "calculate_stability_score",
    "calculate_win_rate",
    # Manifest
    "RunManifest",
    "create_manifest",
    "save_manifest",
    "load_manifest",
    "generate_run_id",
    "MANIFEST_SCHEMA_VERSION",
]
