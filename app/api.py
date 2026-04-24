"""POC 1단계 FastAPI.

엔드포인트:
- POST /runs/generate        : 새 run_id 로 초안 생성
- GET  /runs                 : 모든 run 조회
- GET  /runs/{run_id}        : 단일 run 조회
- POST /runs/{run_id}/reject : PENDING_APPROVAL -> REJECTED
- POST /runs/{run_id}/approve: PENDING_APPROVAL -> DELIVERING 즉시 진입 후
                               전달 결과에 따라 COMPLETED 또는 FAILED 로 종료

APPROVED 상태는 없다. Approve 는 즉시 DELIVERING 으로 전이하며 동일 요청
안에서 외부 전달을 시도하고 그 결과를 run 에 저장한다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import delivery, draft, store
from app.models import Run
from app.state import InvalidTransition, validate_transition

logger = logging.getLogger(__name__)

app = FastAPI(title="POC 1단계 승인 루프")


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


@app.post("/runs/{run_id}/approve", response_model=RunResponse)
def post_approve(run_id: str) -> RunResponse:
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

    try:
        delivery.deliver(run)
        run.status = "COMPLETED"
    except delivery.DeliveryError as e:
        logger.error(f"delivery 실패 run_id={run.run_id}: {e}")
        run.status = "FAILED"

    store.save(run)
    return RunResponse.from_run(run)
