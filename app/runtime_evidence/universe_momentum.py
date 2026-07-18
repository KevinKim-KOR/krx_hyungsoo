"""universe_momentum_snapshot source composer (지시문 §21~§27).

기존 reader (`app/draft_three_push.py::_load_universe_artifact_for_spike`) 를
read-only 로 재사용. Runtime 은 producer/외부 API 호출 X · 후보 재계산 X ·
후보 재정렬 X · artifact write X (§22).

계약 (검증자 REJECTED r2 재정정):
- artifact validation 은 Publication 과 동일 shared validator 사용
  (`app.universe_bootstrap.artifact_validator.validate_artifact`).
  → refresh_status allowlist · candidate shape 단일 소스.
- Runtime 은 artifact.candidates **순서를 그대로 사용** (재정렬 금지, AC-20).
- reader 예외는 잡아서 unavailable 로 처리 (Runtime 실행까지 전파 금지).
- 사용자 문장에는 artifact 에 실제 존재하는 표시 값만 포함. 내부 reason code
  (exclusion_reason 등) 는 사용자 노출 금지 — 표시할 값 없으면 그 후보 skip.
- 정상 후보 0건 → no_signal=true (§25).
- 정상 후보 존재 (`candidate_count >= 1`) 시 selection/fact >= 1 필수 (§24 / AC-32).
  → 후보는 있지만 표시 가능 값이 없는 경우 (전부 미채점 등) 는 unavailable 로
    처리해 "후보 있음 · fact 없음" 계약 위반을 방지 (검증자 재정정).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.runtime_evidence.constants import fmt_pct
from app.universe_bootstrap.artifact_validator import validate_artifact

# 사용자 표시 최대 개수 (§26 신규 제한 금지 · 기존 spike alert 표시 계약과 동일).
_UNIVERSE_DISPLAY_LIMIT = 5


def _load_default_artifact() -> Optional[dict[str, Any]]:
    """기존 reader (`_load_universe_artifact_for_spike`) 재사용."""
    from app.draft_three_push import _load_universe_artifact_for_spike

    return _load_universe_artifact_for_spike()


def _build_candidate_notes(
    artifact: dict[str, Any],
) -> tuple[list[str], int, int]:
    """사용자용 evidence 문장 + selected_count + contentful_fact_count 반환.

    검증자 REJECTED r2 재정정:
    - artifact.candidates 순서 그대로 사용 (rank 재정렬 X · AC-20).
    - 미채점 후보는 exclusion_reason (내부 코드) 노출 대신 skip.
    - 표시 대상 후보 수는 기존 표시 제한 (_UNIVERSE_DISPLAY_LIMIT) 만큼만.
    """
    candidates = artifact.get("candidates") or []
    asof = artifact.get("asof")
    notes: list[str] = []
    selected_count = 0
    fact_count = 0

    for c in candidates:
        if not isinstance(c, dict):
            continue
        if selected_count >= _UNIVERSE_DISPLAY_LIMIT:
            break
        ticker = c.get("ticker")
        name = c.get("name") or ticker
        if not name:
            continue
        score_result = c.get("score_result") or {}
        parts: list[str] = []
        if score_result.get("is_scored") is True:
            score_value = score_result.get("score_value")
            score_pct = fmt_pct(score_value)
            if score_pct:
                parts.append(f"1개월 {score_pct}")
        # 미채점 후보 skip (내부 exclusion_reason 노출 X).
        if not parts:
            continue
        line = f"{name} ({asof} 기준): " + " · ".join(parts) + "."
        notes.append(line)
        selected_count += 1
        fact_count += 1
    return notes, selected_count, fact_count


def compose_universe_momentum(
    *,
    artifact_loader: Optional[Callable[[], Optional[dict[str, Any]]]] = None,
) -> tuple[str, list[str], dict[str, Any]]:
    """returns (status, extra_notes, diag).

    검증자 REJECTED r2 재정정: reader 자체 예외도 unavailable 로 캡처 (전파 금지).
    validator 는 Publication 과 shared (`validate_artifact`).
    후보 있으나 표시 가능 fact 0건 → unavailable + `universe_no_displayable_candidates`.
    """
    loader = artifact_loader or _load_default_artifact

    diag: dict[str, Any] = {
        "universe_artifact_present": False,
        "universe_artifact_valid": False,
        "universe_artifact_status": "",
        "universe_artifact_asof": "",
        "universe_candidate_count": 0,
        "universe_selected_count": 0,
        "universe_contentful_fact_count": 0,
        "universe_snapshot_status": "unavailable",
        "universe_snapshot_reason": "",
        "no_signal": False,
    }

    # reader 예외 → unavailable (전파 금지).
    try:
        artifact = loader()
    except Exception as e:  # noqa: BLE001
        diag["universe_snapshot_reason"] = f"artifact_loader_error:{type(e).__name__}"
        return "unavailable", [], diag

    if artifact is None:
        diag["universe_snapshot_reason"] = "artifact_missing_or_invalid_json"
        return "unavailable", [], diag

    diag["universe_artifact_present"] = True

    # shared validator 사용 (candidate shape 포함).
    valid, invalid_reason, meta = validate_artifact(artifact)
    if not valid:
        # 부분 meta (asof 등) 는 반영해도 안전.
        diag["universe_artifact_status"] = meta.get("status", "") or ""
        diag["universe_artifact_asof"] = meta.get("asof", "") or ""
        diag["universe_candidate_count"] = int(meta.get("candidate_count", 0) or 0)
        diag["universe_snapshot_reason"] = invalid_reason or "artifact_invalid"
        return "unavailable", [], diag

    diag["universe_artifact_valid"] = True
    diag["universe_artifact_status"] = meta["status"]
    diag["universe_artifact_asof"] = meta["asof"]
    diag["universe_candidate_count"] = meta["candidate_count"]
    total = meta["candidate_count"]

    if total == 0:
        # 정상 no-signal (§25).
        diag["universe_snapshot_status"] = "available"
        diag["no_signal"] = True
        return "available", [], diag

    notes, selected, fact_count = _build_candidate_notes(artifact)

    # 검증자 REJECTED r2 재정정: 후보 있음 + 표시 가능 fact 0건 → unavailable.
    # (§24 / AC-32: 후보 존재 시 selection/fact >= 1 필수. 계약 위반 방지.)
    if fact_count == 0:
        diag["universe_selected_count"] = 0
        diag["universe_contentful_fact_count"] = 0
        diag["universe_snapshot_reason"] = "universe_no_displayable_candidates"
        return "unavailable", [], diag

    diag["universe_selected_count"] = selected
    diag["universe_contentful_fact_count"] = fact_count
    diag["universe_snapshot_status"] = "available"
    diag["no_signal"] = False
    return "available", notes, diag
