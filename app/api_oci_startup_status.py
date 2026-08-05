"""OCI 기동 시 상태 스냅샷 조회 API (읽기 전용).

POC3-07 (PLAN V2 §4.2 · 설계자 Q2):
  - 이 엔드포인트는 **기동 시 1회 읽은 프로세스 로컬 스냅샷을 반환**한다.
  - 요청마다 OCI 를 다시 조회하지 않는다(SSH 재실행 없음). 화면 새로고침 =
    기동 시 캐시 반환.
  - 첫 화면(오늘의 투자 점검)은 summary_line·checked_at 만 사용해 한 줄 표시.
  - 상세(jobs·note)는 진단·상태 화면에서만 사용.

민감정보는 스냅샷 자체에 없다(app.oci_startup_status 가 담지 않음).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import oci_startup_status

router = APIRouter(prefix="/oci", tags=["oci-status"])


class OciJobStatusModel(BaseModel):
    job: str
    status: str
    detail: str = ""


class OciStartupStatusResponse(BaseModel):
    checked_at: str | None
    reachable: bool
    overall: str
    summary_line: str
    crontab_active: bool | None
    jobs: list[OciJobStatusModel]
    note: str


@router.get("/startup-status", response_model=OciStartupStatusResponse)
def get_oci_startup_status() -> OciStartupStatusResponse:
    """기동 시 1회 읽은 OCI 상태 스냅샷 반환(재조회 없음)."""
    snap = oci_startup_status.get_snapshot()
    return OciStartupStatusResponse(
        checked_at=snap.checked_at,
        reachable=snap.reachable,
        overall=snap.overall,
        summary_line=snap.summary_line,
        crontab_active=snap.crontab_active,
        jobs=[
            OciJobStatusModel(job=j.job, status=j.status, detail=j.detail)
            for j in snap.jobs
        ],
        note=snap.note,
    )
