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

POC5-27 판정 §3: [현재 기준 OCI 적용] 요청 **안에서** 읽은 값이 있으면 그 값 · 시각으로 비교한다
(명시 적용 결과 반영 — 이 엔드포인트가 OCI 를 다시 읽지는 않는다). 행이 200 으로 오는 것과
'값 확인 성공 · 일치'는 다르다(상태 SUCCESS 만 일치).

POC6-34 Q4: 그 OCI 활성값을 읽은 시각 · 경로를 `param_read_at` · `param_source` 로 싣는다(메모리의
값 그대로 · 확인되지 않았으면 null · 기본값 null 이라 옛 소비자는 그대로).

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


class OciScheduleRowModel(BaseModel):
    kind: str
    label: str
    state: str  # registered · missing · unknown (POC6-27)


class OciStartupStatusResponse(BaseModel):
    checked_at: str | None
    reachable: bool
    overall: str
    summary_line: str
    crontab_active: bool | None
    jobs: list[OciJobStatusModel]
    note: str
    # POC6-27 — 필수 3종 예약 상태(기동 스냅샷에서 · OCI 재조회 없음)
    schedule: list[OciScheduleRowModel] = []
    # POC6-34 Q4 · I-7 — '운영 기준 활성' 행의 OCI 활성값을 실제로 읽은 시각(UTC ISO 원문)과
    # 경로(startup = 기동 점검 · apply = [현재 기준 OCI 적용] 요청 안). 메모리에 이미 있는 값을
    # 싣기만 한다(새 OCI 읽기 · 새 계산 없음). 확인되지 않았으면 둘 다 null.
    param_read_at: str | None = None
    param_source: str | None = None


_PARAM_SOURCES = ("startup", "apply")


def _param_read(
    snap: oci_startup_status.OciStartupSnapshot, show: bool
) -> tuple[str | None, str | None]:
    """POC6-34 I-7 — OCI 활성값을 실제로 읽어 갖고 있을 때만 (읽은 시각, 경로).

    행이 빠지는 조건(show)은 그대로 따른다. 확인 불가(unconfirmed)일 때 저장된 시각은 적용
    요청이 끝난 시각이라 '읽은 시각'으로 내보내지 않는다. 그 밖은 (None, None).
    """
    if (
        show
        and snap.oci_param_values
        and not snap.oci_param_unconfirmed
        and snap.oci_param_read_at
        and snap.oci_param_source in _PARAM_SOURCES
    ):
        return snap.oci_param_read_at, snap.oci_param_source
    return None, None


def _param_active_row(
    snap: oci_startup_status.OciStartupSnapshot,
) -> oci_startup_status.OciJobStatus:
    try:
        from app import api_three_push_param as param_api

        return oci_startup_status.param_active_job(
            snap.oci_param_values,
            param_api.latest_param_path(),
            read_at=snap.oci_param_read_at,
            source=snap.oci_param_source,
            unconfirmed=snap.oci_param_unconfirmed,
        )
    except Exception:  # noqa: BLE001 - 이 행만 확인 불가 · 응답은 그대로
        return oci_startup_status.OciJobStatus(
            "param_active", "UNKNOWN", "지금 PC 기준과 비교하지 못함"
        )


@router.get("/startup-status", response_model=OciStartupStatusResponse)
def get_oci_startup_status() -> OciStartupStatusResponse:
    """기동 시 1회 읽은 OCI 상태 스냅샷 반환(OCI 재조회 없음 · 운영 기준 활성 행만 요청 때 비교)."""
    snap = oci_startup_status.get_snapshot()
    # POC5-27 — 기동 읽기가 실패했어도 적용 요청에서 읽은(또는 확인 못 한) 결과는 행으로 보인다.
    show = snap.reachable or snap.oci_param_source == "apply"
    jobs = [*snap.jobs, _param_active_row(snap)] if show else list(snap.jobs)
    param_read_at, param_source = _param_read(snap, show)
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
        schedule=[
            OciScheduleRowModel(**r) for r in oci_startup_status.schedule_rows(snap)
        ],
        param_read_at=param_read_at,
        param_source=param_source,
    )
