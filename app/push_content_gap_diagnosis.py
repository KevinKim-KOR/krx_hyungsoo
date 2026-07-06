"""PUSH Content Gap Diagnosis v1 — main runner (2026-07-05, FIX r2 얇게 재구성).

책임 (얇게 유지, B-2 / B-3):
- 3 PUSH 순회 + 하위 모듈 orchestration.
- artifact JSON 저장.

분리 모듈 (FIX r2):
- `push_content_gap_diagnosis_requirements` — PUSH_REQUIREMENTS 상수 + readiness helper.
- `push_content_gap_diagnosis_reproducers` — PARAM runtime / package fallback 재현.
- `push_content_gap_diagnosis_classifier` — 원인 분류 (§11 6종 + Q1 특수 규칙 + MIXED).

절대 유지 사항 (§4, §9):
- SQLite 변경 금지 / 기존 state artifact 덮어쓰기 금지 / Telegram 발송 금지 /
  외부 API 호출 금지 / 기존 PUSH 실행 이력 변경 금지.
- 기존 PUSH 코드에서 발송 이전의 pure helper 만 재사용.
- available_sources 는 실운영과 동일하게 None 을 전달 (Q1 확정).

Q3 (c) 확정: OCI 실측 대기 = PARTIAL. artifact 최상위 observation_status 로
잠정 상태 명시.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.market_data_store import DEFAULT_DB_PATH
from app.push_content_gap_diagnosis_classifier import (
    decide_primary_root_cause,
    readiness_signals,
)
from app.push_content_gap_diagnosis_reproducers import (
    PARAM_PATH,
    reproduce_package_fallback,
    reproduce_param_runtime,
)
from app.push_content_gap_diagnosis_requirements import (
    PUSH_REQUIREMENTS,
    artifact_status,
    check_sqlite_integrity,
    sqlite_table_ready,
)

DIAGNOSIS_ARTIFACT_PATH = Path(
    "state/diagnostics/push_content_gap_diagnosis_latest.json"
)
SCHEMA_VERSION = "push_content_gap_diagnosis_v1"
VALID_ENVIRONMENTS = ("pc", "oci")

# 기존 테스트 · 진단 CLI 가 참조하는 이름은 유지 (하위 호환 재-export).
_decide_primary_root_cause = decide_primary_root_cause


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_commit(project_root: Path) -> str:
    """현재 commit hash. 실패 시 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _diagnose_push(push_kind: str, db_path: Path, environment: str) -> dict[str, Any]:
    req = PUSH_REQUIREMENTS[push_kind]
    sqlite_deps = [
        sqlite_table_ready(db_path, dep["table"]) for dep in req["sqlite_dependencies"]
    ]
    artifact_statuses: list[dict[str, Any]] = []
    for dep in req["artifact_dependencies"]:
        art = artifact_status(dep["path"])
        art["logical"] = dep["logical"]
        artifact_statuses.append(art)

    readiness = readiness_signals(
        sqlite_deps, artifact_statuses, req["sqlite_dependencies"]
    )

    param_runtime = reproduce_param_runtime(push_kind)
    package_fallback = reproduce_package_fallback(push_kind)

    primary, contributing, next_step = decide_primary_root_cause(
        param_runtime,
        package_fallback,
        environment=environment,
        readiness=readiness,
    )

    return {
        "push_id": push_kind,
        "purpose": req["purpose"],
        "requirements": {
            "sqlite_dependencies": req["sqlite_dependencies"],
            "artifact_dependencies": [
                {"logical": d["logical"], "path": d["path"]}
                for d in req["artifact_dependencies"]
            ],
            "minimum_observation_requirements": [
                f"{d['table']} lookback >= {d.get('minimum_lookback_days', 1)}"
                for d in req["sqlite_dependencies"]
            ],
            "expected_sources": req["expected_sources"],
        },
        "actual_readiness": {
            "sqlite": sqlite_deps,
            "artifacts": artifact_statuses,
            "param_runtime_path": param_runtime,
            "package_fallback_path": package_fallback,
        },
        "content_generation": {
            "status": param_runtime.get("content_generation_status")
            or "runtime_unavailable",
            "selection_result_count": param_runtime.get("selection_result_count", 0),
            "exact_reason_code": param_runtime.get("exact_reason_code"),
        },
        "primary_root_cause": primary,
        "contributing_causes": contributing,
        "recommended_next_step_type": next_step,
    }


def run_push_content_gap_diagnosis(
    *,
    environment: str,
    db_path: Path = DEFAULT_DB_PATH,
    artifact_path: Path = DIAGNOSIS_ARTIFACT_PATH,
    project_root: Optional[Path] = None,
) -> dict[str, Any]:
    """진단 실행. environment ∈ {'pc', 'oci'}. 읽기 전용.

    artifact 는 로컬에 생성 (§8.2). PC · OCI 는 각자 자기 artifact 만.
    """
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"environment must be one of {VALID_ENVIRONMENTS}, got {environment!r}"
        )

    root = project_root or Path(__file__).resolve().parent.parent
    commit = _git_commit(root)
    sqlite_integrity = check_sqlite_integrity(db_path)

    pushes = [
        _diagnose_push(pk, db_path, environment)
        for pk in ("market_briefing", "holdings_briefing", "spike_or_falling_alert")
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "environment": environment,
        # FIX r1: 진단 자체는 environment 한쪽만 담으며, 최종 root cause 는
        # PC · OCI 비교 후에 확정. artifact 각 push 의 primary_root_cause 는
        # 이 환경 시점의 "잠정" 관측치임을 명시.
        "observation_status": "single_environment_pending_cross_comparison",
        "generated_at": _utcnow_iso(),
        "code_version": {
            "commit": commit,
            "version_match_checkable": commit != "unknown",
        },
        "runtime_readiness": {
            "sqlite_integrity": sqlite_integrity,
            "required_logical_paths_ready": all(
                any(a["exists"] for a in p["actual_readiness"]["artifacts"])
                for p in pushes
            ),
        },
        "pushes": pushes,
        "limitations": [
            "OCI 실측은 사용자가 동일 commit 을 OCI 에 반영한 뒤 별도 실행. "
            "본 artifact 는 environment 인자로 지정된 환경 한쪽만 담고 있다.",
            "각 push 의 primary_root_cause / recommended_next_step_type 은 이 "
            "환경 시점의 잠정 관측치이며, PC·OCI 비교 후 최종 확정한다.",
        ],
    }

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = artifact_path.with_suffix(artifact_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    tmp.replace(artifact_path)
    return payload


# 하위 호환: 이전 테스트가 참조하던 이름들.
__all__ = [
    "DIAGNOSIS_ARTIFACT_PATH",
    "PARAM_PATH",
    "PUSH_REQUIREMENTS",
    "SCHEMA_VERSION",
    "VALID_ENVIRONMENTS",
    "_decide_primary_root_cause",
    "_diagnose_push",
    "run_push_content_gap_diagnosis",
]
