"""러너 record 진단 필드 전달 (KS-10 분리 · 2026-09-04).

`run_three_push_runtime_oci.py` 가 650줄 임계를 넘어 **기계적으로 분리**한 블록이다.
전달하는 키 목록과 조건은 그대로다 — 판정 로직 변경 0건.
"""

from __future__ import annotations

from typing import Any, Optional

# evidence.diagnostics 에서 record 로 그대로 옮기는 키.
# 개인정보 · Holdings JSON 원문 · raw ticker 는 Composer 계약상 이미 제외된다.
FORWARDED_DIAGNOSTIC_KEYS: tuple[str, ...] = (
    "holdings_snapshot_status",
    "holdings_snapshot_reason",
    "holdings_loaded_count",
    "holdings_evidence_item_count",
    "holdings_contentful_fact_count",
    "nav_contentful_fact_count",
    "holdings_selection_result_count",
    "rendered_holdings_fact_count",
    "private_fields_exposed",
    "raw_identifier_exposed",
    "universe_artifact_present",
    "universe_artifact_valid",
    "universe_artifact_status",
    "universe_artifact_asof",
    "universe_candidate_count",
    "universe_selected_count",
    "universe_contentful_fact_count",
    "universe_snapshot_status",
    "universe_snapshot_reason",
    "no_signal",
)


def forward_diagnostics(record: dict[str, Any], evidence: Optional[Any]) -> None:
    """evidence 진단을 record 로 전달. evidence 가 없으면(보유 브리핑) 아무것도 안 한다."""
    if evidence is None:
        return
    for key in FORWARDED_DIAGNOSTIC_KEYS:
        if key in evidence.diagnostics:
            record[key] = evidence.diagnostics[key]
