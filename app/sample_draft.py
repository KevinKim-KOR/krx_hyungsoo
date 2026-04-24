"""POC 전용 stub — 샘플 draft payload 빌더.

이 파일은 POC 단계 검증 전용이다. 운영 시 실제 ML/샘플링 로직으로 교체 대상.
파일명에 "sample" 을 명시하여 운영 payload 생성 로직이 아니라는 점을 드러낸다.

계약:
- build_sample_payload(input_data) -> dict
- input_data 는 필수. 필수 키 누락 시 SampleDraftInputError 로 즉시 실패
  (암묵 fallback 금지).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

REQUIRED_INPUT_KEYS: tuple[str, ...] = (
    "title",
    "recommendations",
    "note",
)


class SampleDraftInputError(Exception):
    pass


def build_sample_payload(input_data: dict[str, Any]) -> dict[str, Any]:
    """POC 용 draft payload 빌드.

    input_data 는 다음 키를 모두 포함해야 한다:
    - title: str
    - recommendations: list[dict]
    - note: str

    누락 시 SampleDraftInputError 를 raise 한다.
    asof 는 호출 시점의 UTC 시각으로 서버가 결정한다.
    """
    missing = [k for k in REQUIRED_INPUT_KEYS if k not in input_data]
    if missing:
        raise SampleDraftInputError(
            f"input_data 에 필수 키 누락: {missing}. "
            f"요구 키: {list(REQUIRED_INPUT_KEYS)}"
        )

    return {
        "title": input_data["title"],
        "asof": datetime.now(timezone.utc).isoformat(),
        "recommendations": input_data["recommendations"],
        "note": input_data["note"],
    }
