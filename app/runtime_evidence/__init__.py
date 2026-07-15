"""Runtime Evidence 패키지 — OCI PARAM Runtime + Diagnosis 공통 evidence 조립.

책임 분리 (Cleanup / FIX r7 Round 2):
- constants.py: source key · reason code · RuntimeEvidenceResult 계약.
- privacy.py: 개인정보 · raw identifier 노출 탐지 정책·detector.
- market_discovery.py: market_discovery_snapshot source composer.
- holdings_evidence.py: Holdings evidence 판정 + 사용자 문장 생성.
- nav_evidence.py: NAV row 해석 + 사용자 문장 생성.
- diagnostics.py: diagnostics 필드 집계.
- composer.py: orchestrator (compose_runtime_evidence).

외부 계약 유지:
- app.runtime_evidence_composer 는 이 패키지의 얇은 facade 로 남는다.
- 기존 import 경로 (`from app.runtime_evidence_composer import ...`) 전부 그대로 동작.
"""

from __future__ import annotations

from app.runtime_evidence.constants import (
    REASON_EXTERNAL_FETCH_REQUIRED,
    REASON_MARKET_DB_MISSING,
    REASON_NAV_UNAVAILABLE,
    REASON_NO_CONTENTFUL_FACT,
    REASON_NOT_IMPLEMENTED,
    REASON_SOURCE_MISSING_HOLDINGS,
    RuntimeEvidenceResult,
    SRC_HOLDINGS,
    SRC_KR_REALTIME,
    SRC_MARKET_DISCOVERY,
    SRC_ML_BASELINE,
    SRC_NAV_DISCOUNT,
    SRC_NEWS,
    SRC_OVERNIGHT_US,
    SRC_UNIVERSE_MOMENTUM,
)
from app.runtime_evidence.composer import compose_runtime_evidence

__all__ = [
    "REASON_EXTERNAL_FETCH_REQUIRED",
    "REASON_MARKET_DB_MISSING",
    "REASON_NAV_UNAVAILABLE",
    "REASON_NO_CONTENTFUL_FACT",
    "REASON_NOT_IMPLEMENTED",
    "REASON_SOURCE_MISSING_HOLDINGS",
    "RuntimeEvidenceResult",
    "SRC_HOLDINGS",
    "SRC_KR_REALTIME",
    "SRC_MARKET_DISCOVERY",
    "SRC_ML_BASELINE",
    "SRC_NAV_DISCOUNT",
    "SRC_NEWS",
    "SRC_OVERNIGHT_US",
    "SRC_UNIVERSE_MOMENTUM",
    "compose_runtime_evidence",
]
