"""Holdings OCI 적용 API (POC3-07 §4.3 · 설계자 Q3·Q4·Q11).

제공 endpoint:
  POST /holdings/apply — 저장된 보유 종목을 OCI 에 명시적으로 적용(전송 → 검증 →
    원자 적용). 사용자 명시 클릭에서만 호출된다(자동 전송 없음). 저장(PUT /holdings)과
    분리된 별도 업무 동작.

frontend response 에 포함하지 않는 것(§6·§13):
  SSH target / remote path / raw subprocess 출력 / secret.
  → 사용자 중심 상태·시각·짧은 오류 요약·표시용 hash 만.

응답 후 일반 OCI 상태를 별도로 재조회하지 않는다(Q3). 이 응답은 이번 적용 동작의
결과만 담는다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app import holdings_oci_apply

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings-oci-apply"])

# apply 동작은 scp + ssh verify 를 포함하므로 기본 GET timeout 보다 길다.
# (프론트 client 에서 120s 허용과 대응.)


class HoldingsApplyResponse(BaseModel):
    status: str  # PC_SAVED / OCI_APPLIED / OUT_OF_SYNC / APPLY_FAILED / UNKNOWN
    applied_at: str | None
    content_sha256: str | None  # 표시용(전송 payload 해시)
    oci_verified: bool
    message: str


@router.post("/apply", response_model=HoldingsApplyResponse)
def post_apply_holdings_to_oci() -> HoldingsApplyResponse:
    """저장된 Holdings 를 OCI 에 적용(전송 → 검증 → 원자 적용). 실패 시 기존 보존."""
    result = holdings_oci_apply.apply_holdings_to_oci()
    return HoldingsApplyResponse(
        status=result.status,
        applied_at=result.applied_at,
        content_sha256=result.content_sha256,
        oci_verified=result.oci_verified,
        message=result.message,
    )
