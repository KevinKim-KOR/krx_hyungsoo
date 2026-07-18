"""Diagnostics 필드 집계 (지시문 §9 · 설계자 확정본 Q7).

Cleanup / FIX r7 Round 2 에서 `app/runtime_evidence_composer.py` 로부터 분리.
사용자 메시지 원문 · Holdings 세부정보 (수량/평단/account_group 등) 를
diagnostics 에 저장하지 않는다.
"""

from __future__ import annotations

from typing import Any

from app.runtime_evidence.constants import (
    SRC_HOLDINGS,
    SRC_NAV_DISCOUNT,
)


def build_base_diagnostics(
    push_kind: str,
    available_sources: dict[str, str],
    diag_sources: dict[str, dict[str, Any]],
    contentful_fact_count: int,
    selection_result_count: int,
) -> dict[str, Any]:
    """공통 diagnostics 구성 (모든 push_kind 공용)."""

    def _status_for(src_key: str) -> str:
        if src_key in diag_sources:
            return diag_sources[src_key].get("status") or "unavailable"
        return "unavailable"

    unavailable_reasons = {
        src: st for src, st in available_sources.items() if st != "available"
    }

    return {
        "push_kind": push_kind,
        "source_statuses": {src: _status_for(src) for src in available_sources},
        "source_asof": {
            src: diag_sources.get(src, {}).get("asof")
            for src in diag_sources
            if diag_sources.get(src, {}).get("asof") is not None
        },
        "contentful_fact_count": contentful_fact_count,
        "selection_result_count": selection_result_count,
        "unavailable_reasons": unavailable_reasons,
        "holdings_source_present": diag_sources.get(SRC_HOLDINGS, {}).get(
            "source_present", False
        ),
    }


def add_holdings_briefing_diagnostics(
    diagnostics: dict[str, Any],
    diag_sources: dict[str, dict[str, Any]],
) -> None:
    """holdings_briefing 전용 fact attribution 필드 (설계자 확정본 Q7).

    diagnostics 딕셔너리에 in-place 로 필드 추가:
    - holdings_loaded_count / holdings_evidence_item_count /
      holdings_contentful_fact_count / nav_contentful_fact_count /
      holdings_selection_result_count / rendered_holdings_fact_count /
      holdings_snapshot_status / holdings_snapshot_reason /
      private_fields_exposed (bool) / raw_identifier_exposed (bool).
    - selection_result_count 를 holdings 전용 값으로 재정의.
    """
    h = diag_sources.get(SRC_HOLDINGS, {})
    nav = diag_sources.get(SRC_NAV_DISCOUNT, {})
    diagnostics.update(
        {
            "holdings_loaded_count": h.get("holdings_loaded_count", 0),
            "holdings_evidence_item_count": h.get("holdings_evidence_item_count", 0),
            "holdings_contentful_fact_count": h.get(
                "holdings_contentful_fact_count", 0
            ),
            "nav_contentful_fact_count": nav.get("nav_contentful_fact_count", 0),
            "holdings_selection_result_count": h.get(
                "holdings_selection_result_count", 0
            ),
            "rendered_holdings_fact_count": h.get("rendered_holdings_fact_count", 0),
            "holdings_snapshot_status": h.get("status", "unavailable"),
            "holdings_snapshot_reason": h.get("reason") or "",
            "private_fields_exposed": bool(h.get("private_fields_exposed", False)),
            "raw_identifier_exposed": bool(h.get("raw_identifier_exposed", False)),
        }
    )
    # 설계자 확정본 Q3: selection_result_count 를 holdings 전용 값으로 재정의.
    diagnostics["selection_result_count"] = h.get("holdings_selection_result_count", 0)


def add_spike_alert_diagnostics(
    diagnostics: dict[str, Any],
    diag_sources: dict[str, dict[str, Any]],
    extra_notes: list[str],
) -> None:
    """spike_or_falling_alert 전용 universe diagnostics 필드 (지시문 §27).

    검증자 REJECTED r2 재정정:
    - private_fields_exposed / raw_identifier_exposed 는 하드코드 False 금지.
      기존 privacy detector 를 재사용하여 실제 extra_notes 스캔 결과 반환.
    - Universe artifact 는 개인정보가 없더라도 template 이 실수로 노출할 수 있으므로
      실측 결과가 계약.

    boolean 계약: universe_artifact_present · universe_artifact_valid · no_signal ·
    private_fields_exposed · raw_identifier_exposed. 0/1/None/문자열 반환 금지.
    """
    from app.runtime_evidence.constants import SRC_UNIVERSE_MOMENTUM
    from app.runtime_evidence.privacy_detector import (
        detect_private_values_exposed,
        detect_raw_identifier_exposed,
    )

    u = diag_sources.get(SRC_UNIVERSE_MOMENTUM, {})
    # spike 는 holdings list 를 참조하지 않지만 privacy detector 는 빈 리스트에서도
    # 안전. raw identifier 검사는 항상 실측.
    raw_exposed = detect_raw_identifier_exposed(extra_notes)
    private_exposed = detect_private_values_exposed([], extra_notes)
    diagnostics.update(
        {
            "universe_artifact_present": bool(
                u.get("universe_artifact_present", False)
            ),
            "universe_artifact_valid": bool(u.get("universe_artifact_valid", False)),
            "universe_artifact_status": u.get("universe_artifact_status", "") or "",
            "universe_artifact_asof": u.get("universe_artifact_asof", "") or "",
            "universe_candidate_count": int(u.get("universe_candidate_count", 0) or 0),
            "universe_selected_count": int(u.get("universe_selected_count", 0) or 0),
            "universe_contentful_fact_count": int(
                u.get("universe_contentful_fact_count", 0) or 0
            ),
            "universe_snapshot_status": u.get(
                "universe_snapshot_status", "unavailable"
            ),
            "universe_snapshot_reason": u.get("universe_snapshot_reason", "") or "",
            "no_signal": bool(u.get("no_signal", False)),
            "private_fields_exposed": bool(private_exposed),
            "raw_identifier_exposed": bool(raw_exposed),
        }
    )
