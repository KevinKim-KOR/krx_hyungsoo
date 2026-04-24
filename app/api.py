"""POC 1단계 FastAPI.

엔드포인트:
- POST /runs/generate        : 새 run_id 로 초안 생성
- GET  /runs                 : 모든 run 조회
- GET  /runs/{run_id}        : 단일 run 조회
- POST /runs/{run_id}/reject : PENDING_APPROVAL -> REJECTED
- POST /runs/{run_id}/approve: PENDING_APPROVAL -> DELIVERING 즉시 진입 후
                               실제 외부 전달은 BackgroundTasks 로 위임.
                               최종 상태(COMPLETED / FAILED) 는 후속
                               GET /runs/{run_id} 에서 확인한다.

APPROVED 상태는 없다. Approve 응답은 DELIVERING 스냅샷을 반환하며,
백그라운드 워커(_execute_delivery) 가 delivery.deliver() 를 실행한 뒤
결과에 따라 run.status 를 COMPLETED 또는 FAILED 로 저장한다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import delivery, draft, store
from app.models import Run
from app.state import InvalidTransition, validate_transition

logger = logging.getLogger(__name__)

app = FastAPI(title="POC 1단계 승인 루프")

# Next.js dev(3000) 프론트에서 직접 호출 허용.
# Next.js API Routes/Proxy 를 거치지 않고 프론트 ↔ FastAPI 분리 연결이
# 이번 단계의 확정 설계. 운영 배포 시 origin 화이트리스트 재정의 대상.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class GenerateDraftRequest(BaseModel):
    # input_data 는 필수 dict. 빈 dict 또는 sample_draft 필수 키 누락은
    # draft 레이어에서 SampleDraftInputError → FAILED run 으로 귀결된다.
    # 즉 "실패 → FAILED 단일 규칙" 이며 이 단계에서 400 으로 거절하지 않는다.
    input_data: dict[str, Any] = Field(
        ...,
        description=(
            "draft 생성 입력. 필수 dict. 빈 dict / 필수 키 누락 시 FAILED run 으로 저장"
        ),
    )


class RunResponse(BaseModel):
    run_id: str
    asof: str
    status: str
    draft_payload: Optional[dict[str, Any]] = None

    @classmethod
    def from_run(cls, run: Run) -> "RunResponse":
        return cls(
            run_id=run.run_id,
            asof=run.asof,
            status=run.status,
            draft_payload=run.draft_payload,
        )


@app.post("/runs/generate", response_model=RunResponse)
def post_generate(req: GenerateDraftRequest) -> RunResponse:
    # 원 지시: GenerateDraft 실패 → FAILED 단일 규칙.
    # 빈 dict / 필수 키 누락 등 모든 draft 생성 실패는 draft.generate_draft
    # 내부에서 FAILED run 으로 저장되며 200 응답으로 돌려준다.
    run = draft.generate_draft(req.input_data)
    return RunResponse.from_run(run)


@app.get("/runs", response_model=list[RunResponse])
def get_runs() -> list[RunResponse]:
    return [RunResponse.from_run(r) for r in store.list_runs()]


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return RunResponse.from_run(run)


@app.post("/runs/{run_id}/reject", response_model=RunResponse)
def post_reject(run_id: str) -> RunResponse:
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    try:
        validate_transition(run.status, "REJECTED")
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    run.status = "REJECTED"
    store.save(run)
    return RunResponse.from_run(run)


def _execute_delivery(run_id: str) -> None:
    """BackgroundTasks 에서 실행되는 전달 워커.

    응답은 이미 클라이언트에 전송된 뒤이므로 이 함수는 반환값을 쓰지 않는다.
    실패/성공은 store 에 기록해 다음 GET /runs/{run_id} 에서 노출된다.
    """
    try:
        run = store.load(run_id)
    except KeyError:
        logger.error(f"background delivery: run_id 조회 실패 {run_id}")
        return
    if run.status != "DELIVERING":
        # 외부 개입이나 드리프트로 DELIVERING 이 아닌 경우 안전하게 종료
        logger.warning(
            f"background delivery: 상태가 DELIVERING 이 아님 "
            f"(run_id={run_id}, status={run.status}). 전달 건너뜀."
        )
        return
    try:
        delivery.deliver(run)
        run.status = "COMPLETED"
    except delivery.DeliveryError as e:
        logger.error(f"delivery 실패 run_id={run.run_id}: {e}")
        run.status = "FAILED"
    store.save(run)


@app.post("/runs/{run_id}/approve", response_model=RunResponse)
def post_approve(run_id: str, background_tasks: BackgroundTasks) -> RunResponse:
    """Approve 요청.

    - PENDING_APPROVAL → DELIVERING 상태 저장 후 '즉시' DELIVERING 응답을 반환
    - 실제 외부 전달은 BackgroundTasks 로 위임 (별도 태스크)
    - 클라이언트는 polling 또는 수동 새로고침으로 COMPLETED / FAILED 최종 상태를 확인
    """
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    try:
        validate_transition(run.status, "DELIVERING")
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))

    run.status = "DELIVERING"
    store.save(run)

    # 현 시점 스냅샷을 응답으로 고정 (background 가 언제 실행되든 상관 없음)
    snapshot = RunResponse.from_run(run)

    # 외부 전달은 비동기로 진행. 결과는 store 업데이트.
    background_tasks.add_task(_execute_delivery, run_id)

    return snapshot
