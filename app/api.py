"""POC 1단계 FastAPI (Step 3 OCI 실연결 구조).

엔드포인트:
- POST /runs/generate        : 새 run_id 로 초안 생성
- GET  /runs                 : 모든 run 조회
- GET  /runs/{run_id}        : 단일 run 조회 + DELIVERING 인 경우
                               OCI outbox 1회 reconciliation 시도
- POST /runs/{run_id}/reject : PENDING_APPROVAL -> REJECTED
- POST /runs/{run_id}/approve: PENDING_APPROVAL -> DELIVERING 즉시 진입 후
                               BackgroundTasks 가 SCP 로 OCI inbox 에 큐잉

상태 결정 책임 분리:
- _execute_delivery (BackgroundTasks):
  · SCP 성공 → status 그대로 DELIVERING 유지 (큐잉만 완료)
  · SCP 실패 / DeliveryConfigError → FAILED 즉시 종결
- _try_reconcile_with_oci_outbox (GET /runs/{run_id} 시점):
  · OCI consumer (poc1_consume_inbox.sh) 가 outbox 에 쓴 결과 파일을
    SSH cat 으로 1회 조회. status 가 COMPLETED / FAILED 이면 store 갱신
  · DeliveryConfigError → FAILED 마킹 (DELIVERING 영구 고정 차단)

즉 동기 응답으로 COMPLETED 까지 가지 않는다. 최종 상태는 OCI 측 처리 +
프론트의 느린 polling(12s) 또는 수동 새로고침을 통해 도달한다.
APPROVED 상태는 존재하지 않는다.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# `app.config` import 자체가 .env 자동 로드를 트리거한다.
# 환경변수에 의존하는 어떤 모듈보다 먼저 import 되어야 한다.
from app import config  # noqa: F401  # side-effect import (load_dotenv)
from app import delivery, draft, holdings as holdings_module, store
from app.holdings import HoldingsValidationError
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
    # 원 지시(POC1): GenerateDraft 실패 → FAILED 단일 규칙.
    # 빈 dict / 필수 키 누락 등 모든 draft 생성 실패는 draft.generate_draft
    # 내부에서 FAILED run 으로 저장되며 200 응답으로 돌려준다.
    # POC2 Step 1 부터 이 엔드포인트는 샘플 입력(개발/테스트용) 전용.
    # 운영 흐름은 POST /runs/generate-from-holdings 사용.
    run = draft.generate_draft(req.input_data)
    return RunResponse.from_run(run)


# ─── POC2 Step 1: holdings ─────────────────────────────────────────────


class HoldingItem(BaseModel):
    ticker: str
    quantity: float
    avg_buy_price: float
    name: Optional[str] = None


class HoldingsPayload(BaseModel):
    holdings: list[HoldingItem]


@app.get("/holdings", response_model=HoldingsPayload)
def get_holdings() -> HoldingsPayload:
    """저장된 holdings 조회. 파일 없으면 빈 리스트 반환."""
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        # 저장된 파일이 손상된 경우. 사용자에게 명시적으로 알림.
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    return HoldingsPayload(
        holdings=[
            HoldingItem(
                ticker=h.ticker,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                name=h.name,
            )
            for h in loaded
        ]
    )


@app.put("/holdings", response_model=HoldingsPayload)
def put_holdings(payload: HoldingsPayload) -> HoldingsPayload:
    """holdings 저장. 검증 실패 시 422 (run 생성 안 함).

    POC2 Step 1 E항: 단순 입력 오류로 run_id 를 만들거나 FAILED run 을
    저장하지 않는다. validation error 는 422 로 즉시 반환.
    """
    raw = [item.model_dump() for item in payload.holdings]
    try:
        validated = holdings_module.validate_holdings(raw)
    except HoldingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    holdings_module.save(validated)
    return HoldingsPayload(
        holdings=[
            HoldingItem(
                ticker=h.ticker,
                quantity=h.quantity,
                avg_buy_price=h.avg_buy_price,
                name=h.name,
            )
            for h in validated
        ]
    )


@app.post("/runs/generate-from-holdings", response_model=RunResponse)
def post_generate_from_holdings() -> RunResponse:
    """저장된 holdings 기반 draft 생성 (POC2 Step 1 운영 진입점).

    holdings 가 비어있거나 손상되면 422 — run 생성 차단 (FAILED run 만들지 않음).
    이후는 기존 승인 루프(PENDING_APPROVAL / Approve / Reject) 가 동일하게 처리.
    """
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")
    if not loaded:
        raise HTTPException(
            status_code=422,
            detail="holdings 가 비어 있습니다. 먼저 보유 종목을 입력 후 저장해 주세요.",
        )
    run = draft.generate_draft_from_holdings(loaded)
    return RunResponse.from_run(run)


@app.get("/runs", response_model=list[RunResponse])
def get_runs() -> list[RunResponse]:
    return [RunResponse.from_run(r) for r in store.list_runs()]


def _try_reconcile_with_oci_outbox(run: Run) -> Run:
    """DELIVERING 상태인 run 에 한해 OCI outbox 결과를 1회 조회하여 갱신.

    설계자 결정: 별도 worker/scheduler 를 만들지 않고, 프론트의 느린 polling
    이 GET /runs/{run_id} 를 호출할 때마다 동기적으로 SSH cat 1회 시도.
    outbox 파일이 있으면 store 갱신, 없으면 DELIVERING 유지.

    outbox 파일 규약(소비자 poc1_consume_inbox.sh 가 작성):
    {
      "run_id": "...",
      "status": "COMPLETED" | "FAILED",
      "processed_at": "ISO-8601",
      "telegram_message_id": "...optional..."
    }
    """
    if run.status != "DELIVERING":
        return run
    try:
        outbox = delivery.fetch_outbox_result(run.run_id)
    except delivery.DeliveryConfigError as e:
        # 환경변수 누락은 silent swallow 금지 (Codex B-1).
        # DELIVERING 영구 고정을 막기 위해 즉시 FAILED 로 종결한다.
        # 사용자가 .env 를 설정하지 않은 상태라면 동일한 누락으로 _execute_delivery
        # 단계에서도 FAILED 가 됐어야 정상이며, 여기 도달했다는 것은 SCP 시점에는
        # 환경변수가 있었으나 이후 사라진 비정상 상태이므로 명시적 실패 처리.
        logger.error(
            f"[reconcile] OCI 환경변수 누락으로 outbox 조회 불가 → FAILED "
            f"run_id={run.run_id}: {e}"
        )
        run.status = "FAILED"
        store.save(run)
        return run
    if not outbox:
        return run
    new_status = outbox.get("status")
    if new_status not in ("COMPLETED", "FAILED"):
        logger.warning(
            f"outbox status 가 비정상: run_id={run.run_id} status={new_status!r}. "
            "DELIVERING 유지."
        )
        return run
    try:
        validate_transition(run.status, new_status)
    except InvalidTransition as e:
        logger.warning(f"outbox 결과 무시 (전이 위반): {e}")
        return run
    run.status = new_status
    store.save(run)
    logger.info(f"[reconcile] OCI outbox 결과 반영 run_id={run.run_id} → {new_status}")
    return run


@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str) -> RunResponse:
    try:
        run = store.load(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    run = _try_reconcile_with_oci_outbox(run)
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
    """BackgroundTasks 에서 실행되는 전달 워커 (POC1 Step 3 OCI 연결 구조).

    deliver() 의 책임은 'OCI inbox 에 SCP 로 artifact 를 큐잉' 까지이며,
    그것만으로는 최종 COMPLETED 가 아니다. 실제 처리(Telegram 발송) 는 OCI
    측 daily_ops.sh → poc1_consume_inbox.sh 가 수행하고 그 결과를 outbox 에
    파일로 남긴다. 로컬 GET /runs/{run_id} 가 그 outbox 를 조회해
    COMPLETED 또는 FAILED 로 reconciliation 한다.

    따라서 이 함수의 분기는:
    - SCP 성공 → status 그대로(DELIVERING). store.save 만 (asof 는 변경 없음)
    - SCP 실패(또는 환경 설정 누락) → status FAILED 로 즉시 종결
    """
    try:
        run = store.load(run_id)
    except KeyError:
        logger.error(f"background delivery: run_id 조회 실패 {run_id}")
        return
    if run.status != "DELIVERING":
        logger.warning(
            f"background delivery: 상태가 DELIVERING 이 아님 "
            f"(run_id={run_id}, status={run.status}). 전달 건너뜀."
        )
        return
    try:
        delivery.deliver(run)
        # SCP 성공 = OCI inbox 에 큐잉 완료. 최종 결과는 outbox reconciliation 에서.
        logger.info(
            f"background delivery: SCP 큐잉 완료 (run_id={run_id}). DELIVERING 유지."
        )
    except delivery.DeliveryError as e:
        logger.error(f"delivery 실패 run_id={run.run_id}: {e}")
        run.status = "FAILED"
        store.save(run)
    except delivery.DeliveryConfigError as e:
        # 환경변수 미설정 — 검증 환경에서는 stub 으로 우회되지만,
        # 실 운영에서 누락되면 즉시 FAILED 로 마킹해야 사용자가 알 수 있음.
        logger.error(f"delivery 환경 설정 누락 run_id={run.run_id}: {e}")
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
