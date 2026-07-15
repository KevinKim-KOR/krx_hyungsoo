"""Runtime Evidence Composer — 얇은 facade (Cleanup / FIX r7 Round 2 이후).

실제 구현은 `app/runtime_evidence/` 패키지로 분리됐다:
- constants.py: source key · reason code · RuntimeEvidenceResult
- privacy.py: privacy detector 정책 · 함수
- market_discovery.py: market_discovery_snapshot composer
- holdings_evidence.py: Holdings evidence 판정 · 문장 생성
- nav_evidence.py: NAV row 해석 · 문장 생성
- diagnostics.py: diagnostics 필드 집계
- composer.py: orchestrator (compose_runtime_evidence)

이 파일은 기존 import 경로 (`from app.runtime_evidence_composer import ...`)
을 유지하기 위한 재-export 만 담는다. 새 코드는 `app.runtime_evidence` 를
직접 import 하는 것을 권장.
"""

from __future__ import annotations

from app.runtime_evidence import (  # noqa: F401
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
    compose_runtime_evidence,
)

# 하위 호환: 기존 test 가 `monkeypatch.setattr(runtime_evidence_composer, "HOLDINGS_FILE", ...)`
# 로 default override 를 시도한다. 원본 파일이 상단에서 `from app.holdings import HOLDINGS_FILE`
# 로 import 해서 모듈 attribute 로 노출했던 계약을 유지.
from app.holdings import HOLDINGS_FILE  # noqa: F401

# 기존 test 가 참조하는 내부 helper 경로 유지 (하위 호환).
from app.runtime_evidence.privacy import (  # noqa: F401
    detect_private_values_exposed as _detect_private_values_exposed,
    detect_raw_identifier_exposed as _detect_raw_identifier_exposed,
    has_numeric_word as _has_numeric_word,
    has_string_word as _has_string_word,
    PRIVACY_CONTEXT_TOKENS as _PRIVACY_CONTEXT_TOKENS,
    RAW_IDENT_TOKENS as _RAW_IDENT_TOKENS,
)

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
