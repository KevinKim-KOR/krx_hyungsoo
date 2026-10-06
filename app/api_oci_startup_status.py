"""OCI 기동 시 상태 스냅샷 조회 API (읽기 전용).

POC3-07 (PLAN V2 §4.2 · 설계자 Q2):
  - 이 엔드포인트는 **기동 시 1회 읽은 프로세스 로컬 스냅샷을 반환**한다.
  - 요청마다 OCI 를 다시 조회하지 않는다(SSH 재실행 없음). 화면 새로고침 =
    기동 시 캐시 반환.
  - 첫 화면(오늘의 투자 점검)은 summary_line·checked_at 만 사용해 한 줄 표시.
  - 상세(jobs·note)는 「OCI 운영·적용」 ① 표에서 사용.

POC3-02D-OPS-04 항목 6(설계자 Q7 b): '운영 기준 활성' 행은 요청 때 만든다 — 기동 때 읽어
둔 OCI 활성값과 **지금** PC 운영 기준 JSON 을 비교한다(OCI 는 다시 읽지 않는다). 캐시된
행 목록은 고치지 않고 새 목록을 만든다. 비교가 어떤 이유로 실패해도 이 행만 '확인 불가'다
(응답은 늘 200 — 첫 화면 한 줄도 같은 응답을 쓴다).

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


def _param_active_row(
    snap: oci_startup_status.OciStartupSnapshot,
) -> oci_startup_status.OciJobStatus:
    try:
        from app import api_three_push_param as param_api

        return oci_startup_status.param_active_job(
            snap.oci_param_values,
            param_api.latest_param_path(),
            param_api.last_sync_succeeded(),
        )
    except Exception:  # noqa: BLE001 - 이 행만 확인 불가 · 응답은 그대로
        return oci_startup_status.OciJobStatus(
            "param_active", "UNKNOWN", "전달한 운영 기준과 비교하지 못함"
        )


@router.get("/startup-status", response_model=OciStartupStatusResponse)
def get_oci_startup_status() -> OciStartupStatusResponse:
    """기동 시 1회 읽은 OCI 상태 스냅샷 반환(OCI 재조회 없음 · 운영 기준 활성 행만 요청 때 비교)."""
    snap = oci_startup_status.get_snapshot()
    jobs = [*snap.jobs, _param_active_row(snap)] if snap.reachable else list(snap.jobs)
    return OciStartupStatusResponse(
        checked_at=snap.checked_at,
        reachable=snap.reachable,
        overall=snap.overall,
        summary_line=snap.summary_line,
        crontab_active=snap.crontab_active,
        jobs=[
            OciJobStatusModel(job=j.job, status=j.status, detail=j.detail) for j in jobs
        ],
        note=snap.note,
    )
