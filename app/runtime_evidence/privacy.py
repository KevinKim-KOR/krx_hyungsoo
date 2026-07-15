"""privacy 하위 호환 facade (Cleanup / FIX r7 Round 3 이후).

실제 구현은 아래 두 모듈로 분리됐다:
- privacy_policy.py: 정책 상수 (RAW_IDENT_TOKENS · PRIVACY_CONTEXT_TOKENS 등).
- privacy_detector.py: 탐지 알고리즘 (detect_*, has_*).

이 파일은 기존 import 경로 (예: `from app.runtime_evidence.privacy import
detect_private_values_exposed`) 를 유지하기 위한 재-export 만 담는다. 새 코드는
정책은 `privacy_policy` 에서, detector 는 `privacy_detector` 에서 직접 import.
"""

from __future__ import annotations

from app.runtime_evidence.privacy_detector import (  # noqa: F401
    detect_private_values_exposed,
    detect_raw_identifier_exposed,
    has_numeric_word,
    has_string_word,
)
from app.runtime_evidence.privacy_policy import (  # noqa: F401
    ACCOUNT_GROUP_DEFAULT_LABEL,
    PRIVACY_CONTEXT_TOKENS,
    PRIVACY_CONTEXT_WINDOW,
    PRIVACY_NUMERIC_MIN_LEN,
    RAW_IDENT_TOKENS,
)

__all__ = [
    "ACCOUNT_GROUP_DEFAULT_LABEL",
    "PRIVACY_CONTEXT_TOKENS",
    "PRIVACY_CONTEXT_WINDOW",
    "PRIVACY_NUMERIC_MIN_LEN",
    "RAW_IDENT_TOKENS",
    "detect_private_values_exposed",
    "detect_raw_identifier_exposed",
    "has_numeric_word",
    "has_string_word",
]
