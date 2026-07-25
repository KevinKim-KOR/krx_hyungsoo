"""Spike message body helper (Low-Frequency Telegram Push Operation v1 A+ · B).

혼합 Spike 신호 정책: 기발송 신호는 body 에서도 제외하고 신규 신호만으로 message
extra_notes 를 재조립한다. Runner 가 build_runtime_message 를 재호출하기 전에 이
함수로 evidence.extra_notes 를 교체한다.
"""

from __future__ import annotations

from typing import Any


def filter_extra_notes_to_new_signals(
    all_notes: list[str],
    all_fingerprints: list[str],
    new_fingerprints: list[str],
) -> list[str]:
    """all_notes 를 new_fingerprints 대응 항목만 남기고 필터.

    all_notes[i] 는 all_fingerprints[i] 와 순서 대응 (composer 계약).
    new_fingerprints 는 all_fingerprints 부분집합.
    """
    if not all_fingerprints and not all_notes:
        return []
    # A+ 재정정: length mismatch 는 composer 계약 위반이며 Fail-Closed 로 즉시 raise.
    # 조용히 빈 리스트를 반환하면 Runner 가 정상 skip 처럼 오인할 위험.
    if len(all_notes) != len(all_fingerprints):
        raise ValueError(
            f"notes/fingerprints length mismatch: "
            f"notes={len(all_notes)} fingerprints={len(all_fingerprints)}"
        )
    new_set = set(new_fingerprints)
    return [note for note, fp in zip(all_notes, all_fingerprints) if fp in new_set]


def diag_summary(diag_source: dict[str, Any]) -> dict[str, Any]:
    """Runner record 에 forward 할 진단 subset (테스트 편의)."""
    keys = (
        "reevaluate_status",
        "reevaluate_missing_fields",
        "reevaluate_quote_missing_tickers",
        "reevaluate_candidate_missing_fields",
        "reevaluate_scored_candidate_count",
        "reevaluate_exception",
    )
    return {k: diag_source[k] for k in keys if k in diag_source}
