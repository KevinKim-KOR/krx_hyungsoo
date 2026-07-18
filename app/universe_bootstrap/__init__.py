"""Universe Seed Bootstrap — Holdings 평가금액 + Market Discovery 후보를
사용자에게 제안하기 위한 read-only 후보 조립.

사용자 승인 이후에만 materialize 로 seed 저장 (지시문 §5 / §11 / §12).

새 threshold · 신규 factor · 후보 재정렬 · 예제 seed 사용 금지 (§7~§9 / §38).
"""

from __future__ import annotations

from app.universe_bootstrap.proposal import (
    ProposedCandidate,
    ProposalResult,
    build_bootstrap_proposal,
)

__all__ = [
    "ProposedCandidate",
    "ProposalResult",
    "build_bootstrap_proposal",
]
