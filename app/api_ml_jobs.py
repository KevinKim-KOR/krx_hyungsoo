"""GET /ml/jobs/latest + POST /ml/jobs/evidence-refresh (POC2 UI 안전실행, 2026-06-11).

Data Status 화면이 본 API 2개로 ML evidence 갱신을 안전하게 운영한다:

- GET /ml/jobs/latest               — 저장된 job status 만 read (실행 X / AC-7).
- POST /ml/jobs/evidence-refresh    — background job 시작 + 즉시 반환 (AC-2 / AC-8).
                                      중복 요청은 현재 running 상태 반환 (AC-4).

본 router 는 ML 모델 학습 / 산식 변경 / 외부 source 호출 / Telegram / OCI / PUSH
와 분리된 read/write 경로다 (지시문 §8).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.market_timeseries_ingestion_store import STATUS_NORMAL as INGEST_STATUS_NORMAL
from app.market_timeseries_ingestion_store import read_state as read_ingest_state
from app.market_timeseries_ingestion_service import BENCHMARK_KODEX200_TICKER
from app.market_timeseries_refresh_state_store import (
    STATUS_OK as REFRESH_STATUS_OK,
)
from app.market_timeseries_refresh_state_store import (
    normalize_running_to_failed as _normalize_refresh_running,
)
from app.market_timeseries_refresh_state_store import (
    read_state as read_refresh_state,
)
from app.ml_job_runner import (
    JOB_STATUS_PATH,
    JobAlreadyRunningError,
    JobStatusCorruptedError,
    get_latest_status,
    start_evidence_refresh_job,
)

_ML_GATE_MESSAGE = (
    "시계열 최신화가 완료되지 않았습니다. "
    "PC에서 시계열 최신화 배치를 실행한 뒤 다시 시도하세요."
)


def _timeseries_ready_for_ml() -> tuple[bool, str]:
    """SQLite 만 read 하여 시계열 최신화 준비 여부 판정 (지시문 §9.1).

    조건 (모두 만족해야 준비 완료):
      - market_timeseries_refresh_state.last_attempt_status == 'ok'
      - benchmark_asof_date 존재
      - KODEX200 (069500) 의 market_timeseries_ingestion_state.status == 'normal'
      - eligible_ticker_count > 0

    return: (ready, gate_message). ready=False 이면 사용자용 짧은 안내.
    """
    _normalize_refresh_running()
    refresh = read_refresh_state()
    if refresh is None or refresh.last_attempt_status != REFRESH_STATUS_OK:
        return False, _ML_GATE_MESSAGE
    if not refresh.benchmark_asof_date:
        return False, _ML_GATE_MESSAGE
    if refresh.eligible_ticker_count <= 0:
        return False, _ML_GATE_MESSAGE
    bm_state = read_ingest_state(BENCHMARK_KODEX200_TICKER)
    if bm_state is None or bm_state.ingestion_status != INGEST_STATUS_NORMAL:
        return False, _ML_GATE_MESSAGE
    return True, ""


router = APIRouter()


class MlJobLatestResponse(BaseModel):
    status: (
        str  # "ok" / "empty" / "error" — endpoint 응답 상태 (job 자체 status 와 다름).
    )
    job_status_path: str
    job: Optional[dict[str, Any]] = None
    message: Optional[str] = None


class MlJobStartResponse(BaseModel):
    """job 시작 응답.

    - accepted: 새 job 이 시작됨.
    - already_running: 기존 running job 이 있어 새 job 을 만들지 않음 (AC-4).
    """

    status: str  # "accepted" / "already_running" / "error"
    job_status_path: str
    job: Optional[dict[str, Any]] = None
    message: Optional[str] = None


@router.get("/ml/jobs/latest", response_model=MlJobLatestResponse)
def get_ml_jobs_latest() -> MlJobLatestResponse:
    """저장된 job status 만 반환. 본 API 는 job 을 실행하지 않는다 (AC-7).

    FIX r2: 손상 시 status="error" 로 fail-loud (B-1 — 손상과 미실행 구분).
    """
    snap, read_err = get_latest_status()
    if read_err is not None:
        return MlJobLatestResponse(
            status="error",
            job_status_path=str(JOB_STATUS_PATH),
            job=None,
            message=(
                f"ml_job_status 파일이 손상되어 읽을 수 없습니다: {read_err}. "
                f"파일을 삭제하거나 직접 확인 후 재시도하세요."
            ),
        )
    if snap is None:
        return MlJobLatestResponse(
            status="empty",
            job_status_path=str(JOB_STATUS_PATH),
            job=None,
            message=(
                "ML evidence 갱신 job 이 아직 한 번도 실행되지 않았습니다. "
                "'ML evidence 갱신 실행' 버튼을 누르면 background 로 시작됩니다."
            ),
        )
    return MlJobLatestResponse(
        status="ok",
        job_status_path=str(JOB_STATUS_PATH),
        job=snap,
    )


@router.post("/ml/jobs/evidence-refresh", response_model=MlJobStartResponse)
def post_ml_jobs_evidence_refresh(
    background_tasks: BackgroundTasks,
) -> MlJobStartResponse:
    """ML evidence 갱신 background job 을 시작하고 즉시 반환 (AC-2 / AC-8).

    HTTP 응답은 job 완료를 기다리지 않는다. job 진행 상태는 GET /ml/jobs/latest
    로 polling 한다. 중복 요청은 새 job 을 만들지 않고 현재 running job 의
    snapshot 을 그대로 반환한다 (AC-4).

    FastAPI BackgroundTasks 가 응답 송신 직후 runner 를 실행한다 — HTTP 응답
    송신 자체는 즉시 일어난다.

    2026-06-30 Closeout: 시계열 최신화 게이트 (지시문 §9). SQLite 만 read
    하여 준비 여부 확인 후 진입. 외부 시세 호출 없음. 새 endpoint / 새 응답
    필드 추가 없음 — 기존 status="error" + message 만 사용.
    """
    ready, gate_message = _timeseries_ready_for_ml()
    if not ready:
        return MlJobStartResponse(
            status="error",
            job_status_path=str(JOB_STATUS_PATH),
            job=None,
            message=gate_message,
        )
    try:
        state = start_evidence_refresh_job(
            requested_by="ui",
            schedule=background_tasks.add_task,
        )
    except JobAlreadyRunningError as e:
        return MlJobStartResponse(
            status="already_running",
            job_status_path=str(JOB_STATUS_PATH),
            job=e.state,
            message=str(e),
        )
    except JobStatusCorruptedError as e:
        # FIX r2 (B-1): 손상 시 새 job 자동 생성 금지 — 사용자에게 명시.
        return MlJobStartResponse(
            status="error",
            job_status_path=str(JOB_STATUS_PATH),
            job=None,
            message=str(e),
        )
    return MlJobStartResponse(
        status="accepted",
        job_status_path=str(JOB_STATUS_PATH),
        job=state,
        message="ML evidence refresh job 이 background 로 시작되었습니다.",
    )
