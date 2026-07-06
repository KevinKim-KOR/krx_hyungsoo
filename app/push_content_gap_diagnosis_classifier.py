"""PUSH Content Gap Diagnosis v1 — root cause classifier (2026-07-05, FIX r2 분리).

책임:
- readiness signal 요약.
- primary_root_cause 분류 규칙 (§11 원인 6종 실제 분기).

§11 원인 6종:
- RUNTIME_CONFIGURATION_GAP: PARAM/코드/available_sources 등 구성 문제.
- OBSERVATION_HISTORY_GAP: SQLite 관측 이력 자체 부족.
- OCI_EVIDENCE_GAP: environment=oci + 필수 artifact 부재.
- CONTENT_SELECTION_GAP: 데이터·이력 충족, 기존 필터 결과 empty.
- MIXED: 둘 이상의 독립 원인이 실제로 같은 PUSH 내용을 동시에 막음.
- UNRESOLVED: 재현됐지만 단일 원인 확정 불가.
"""

from __future__ import annotations

from typing import Any, Optional


def readiness_signals(
    sqlite_deps: list[dict[str, Any]],
    artifact_statuses: list[dict[str, Any]],
    required_sqlite: list[dict[str, Any]],
) -> dict[str, bool]:
    """readiness 신호 요약 — §11 분류 규칙에 필요한 primitives.

    - sqlite_lookback_insufficient: 필수 lookback 대비 실제 row_count 부족.
    - required_artifact_missing: 필수 artifact 하나라도 exists=False.
    """
    lookback_bad = False
    for actual, required in zip(sqlite_deps, required_sqlite):
        min_days = int(required.get("minimum_lookback_days") or 1)
        if not actual.get("exists") or actual.get("row_count", 0) < min_days:
            lookback_bad = True
            break
    artifact_bad = any(not a.get("exists") for a in artifact_statuses)
    return {
        "sqlite_lookback_insufficient": lookback_bad,
        "required_artifact_missing": artifact_bad,
    }


def _count_independent_causes(
    param_runtime: dict[str, Any],
    sqlite_bad: bool,
    artifact_bad: bool,
    environment: str,
) -> list[str]:
    """MIXED 판정용 — 서로 독립인 원인 후보를 열거.

    (Q1 특수 규칙 케이스는 상위에서 우선 처리되므로 여기서는 다루지 않는다.)
    """
    independent: list[str] = []
    if sqlite_bad:
        independent.append("OBSERVATION_HISTORY_GAP")
    if environment == "oci" and artifact_bad:
        independent.append("OCI_EVIDENCE_GAP")
    if not param_runtime.get("param_available") or (
        param_runtime.get("push_kind_enabled_in_param") is False
    ):
        independent.append("RUNTIME_CONFIGURATION_GAP")
    if (
        param_runtime.get("message_generated")
        and param_runtime.get("selection_result_count", 0) == 0
        and not sqlite_bad
        and not artifact_bad
        and param_runtime.get("exact_reason_code") is None
    ):
        independent.append("CONTENT_SELECTION_GAP")
    return independent


def decide_primary_root_cause(
    param_runtime: dict[str, Any],
    package_fallback: dict[str, Any],
    *,
    environment: str = "pc",
    readiness: Optional[dict[str, bool]] = None,
) -> tuple[str, list[str], str]:
    """§11 원인 분류 규칙 + Q1 특수 규칙.

    반환: (primary_root_cause, contributing_causes, recommended_next_step_type).
    """
    contributing: list[str] = []
    readiness = readiness or {}
    sqlite_bad = bool(readiness.get("sqlite_lookback_insufficient"))
    artifact_bad = bool(readiness.get("required_artifact_missing"))

    # Q1 특수 규칙 우선.
    if (
        package_fallback.get("content_generation_status") == "content_ready"
        and param_runtime.get("exact_reason_code")
        == "runtime_available_sources_not_supplied"
    ):
        return (
            "RUNTIME_CONFIGURATION_GAP",
            ["package_evidence_ready_but_runtime_not_supplied"],
            "OCI_RUNTIME_CONFIGURATION_CLOSEOUT",
        )

    # MIXED — 서로 독립인 원인이 둘 이상 (FIX r2 신규 분기).
    independent = _count_independent_causes(
        param_runtime, sqlite_bad, artifact_bad, environment
    )
    if len(independent) >= 2:
        return (
            "MIXED",
            independent,
            "NARROWED_FOLLOWUP_DIAGNOSIS",
        )

    # OBSERVATION_HISTORY_GAP — SQLite 관측 이력 자체가 최소 lookback 미달.
    if sqlite_bad:
        return (
            "OBSERVATION_HISTORY_GAP",
            ["sqlite_lookback_insufficient"],
            "MINIMUM_OBSERVATION_HISTORY_BACKFILL",
        )

    # OCI_EVIDENCE_GAP — environment=oci + 필수 artifact 부재.
    if environment == "oci" and artifact_bad:
        return (
            "OCI_EVIDENCE_GAP",
            ["required_artifact_missing_on_oci"],
            "OCI_RUNTIME_EVIDENCE_SYNC",
        )

    # PARAM 미준비 = runtime configuration.
    if not param_runtime.get("param_available"):
        return (
            "RUNTIME_CONFIGURATION_GAP",
            ["missing_latest_param"],
            "OCI_RUNTIME_CONFIGURATION_CLOSEOUT",
        )

    if param_runtime.get("push_kind_enabled_in_param") is False:
        return (
            "RUNTIME_CONFIGURATION_GAP",
            ["push_kind_not_in_param"],
            "OCI_RUNTIME_CONFIGURATION_CLOSEOUT",
        )

    # runtime 메시지가 축약형 (available_sources=None 하드코딩).
    if (
        param_runtime.get("exact_reason_code")
        == "runtime_available_sources_not_supplied"
    ):
        if package_fallback.get("content_generation_status") != "content_ready":
            contributing.append("package_fallback_also_not_ready")
        return (
            "RUNTIME_CONFIGURATION_GAP",
            contributing,
            "OCI_RUNTIME_CONFIGURATION_CLOSEOUT",
        )

    # CONTENT_SELECTION_GAP — 데이터·lookback·PARAM 정상, 메시지 생성, 선택 empty.
    if (
        param_runtime.get("message_generated")
        and param_runtime.get("selection_result_count", 0) == 0
        and not sqlite_bad
        and not artifact_bad
        and param_runtime.get("exact_reason_code") is None
    ):
        return (
            "CONTENT_SELECTION_GAP",
            ["selection_empty_after_existing_filter"],
            "PUSH_CONTENT_SELECTION_CLOSEOUT",
        )

    return ("UNRESOLVED", contributing, "NARROWED_FOLLOWUP_DIAGNOSIS")
