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
