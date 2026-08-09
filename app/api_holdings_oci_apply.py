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


class HoldingsApplyStatusResponse(BaseModel):
    """마지막 OCI 적용 상태(지속 기록). 한 번도 적용 안 했으면 has_record=false."""

    has_record: bool
    status: str | None = None
    applied_at: str | None = None
    oci_verified: bool | None = None
    message: str | None = None


@router.get("/apply/status", response_model=HoldingsApplyStatusResponse)
def get_holdings_apply_status() -> HoldingsApplyStatusResponse:
    """마지막 OCI 적용 시각·상태를 반환(요구 4). 화면 재진입해도 남는다.

    PC 로컬 status 파일을 읽는다. 실제 재적용은 하지 않는다(POST /apply 만 write).
    """
    rec = holdings_oci_apply.read_apply_status()
    if rec is None:
        return HoldingsApplyStatusResponse(has_record=False)
    return HoldingsApplyStatusResponse(
        has_record=True,
        status=rec.get("status"),
        applied_at=rec.get("applied_at"),
        oci_verified=rec.get("oci_verified"),
        message=rec.get("message"),
    )
