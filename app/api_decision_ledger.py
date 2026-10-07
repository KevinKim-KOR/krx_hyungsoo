"""POC5-03 — 받은 알림 기록 API(PC 원장 사본 조회 · 원장 새로고침 · 피드백 추가).

PLAN `docs/ai_plan/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_PLAN_V1.md` §2-4 · §8.

엔드포인트(PC backend · uvicorn --host 127.0.0.1 바인딩 · 기존 API 와 같음):
- GET  /decision-ledger/alerts                      : 선택 날짜(없으면 최근 알림 날짜) · 종류의 sent · partial
                                                      알림 + 동기화 상태
- GET  /decision-ledger/alerts/{event_id}           : 원문 · item · feedback 이력 · 가격 결과(평가와 무관)
- POST /decision-ledger/sync                        : 사용자 버튼 — OCI 읽기 전용 export 1회 → 사본 반영
- POST /decision-ledger/alerts/{event_id}/feedback  : append-only 피드백 1행

동기화 API 만 SSH 를 쓴다. 조회 · 피드백은 PC 사본만 읽고 쓴다. 시장 API · Telegram · OCI 쓰기 0.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.ledger_copy import store, sync, views

KindLiteral = Literal["all", "market", "holdings", "intraday"]
HelpfulnessLiteral = Literal["HELPFUL", "NEUTRAL", "UNHELPFUL_CONFUSING"]
ActionLiteral = Literal["WATCH_ONLY", "BUY_OR_ADD", "SELL_OR_REDUCE", "OTHER"]

_FEEDBACK_HTTP = {"invalid": 422, "not_found": 404, "not_target": 409}

router = APIRouter(prefix="/decision-ledger", tags=["decision-ledger"])


class SyncStatus(BaseModel):
    has_copy: bool
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_failure_kind: Optional[str] = None


class KeyItem(BaseModel):
    subject_kind: str
    subject_id: str
    name: Optional[str] = None


class FeedbackRow(BaseModel):
    feedback_seq: int
    helpfulness: str
    action: Optional[str] = None
    memo: Optional[str] = None
    feedback_at: str


class AlertCard(BaseModel):
    event_id: str
    push_kind: str
    time_kst: Optional[str] = None
    schedule_expected: Optional[str] = None
    off_schedule: bool
    delivery_status: str
    key_items: list[KeyItem]
    latest_feedback: Optional[FeedbackRow] = None
    feedback_count: int


class AlertListResponse(BaseModel):
    date: str
    kind: str
    sync: SyncStatus
    alerts: list[AlertCard]


class ItemRow(BaseModel):
    item_seq: int
    subject_kind: str
    subject_id: str
    name: Optional[str] = None
    held: Optional[int] = None
    state: Optional[str] = None
    prev_state: Optional[str] = None
    state_label: Optional[str] = None
    prev_state_label: Optional[str] = None
    disposition: str
    event_type: Optional[str] = None
    t0_price: Optional[float] = None
    t0_price_asof: Optional[str] = None
    evaluable: bool
    outcome_target: bool


class OutcomeRow(BaseModel):
    item_seq: int
    series_id: str
    series_name: str
    horizon: int
    status: str
    t0_price: Optional[float] = None
    t0_price_asof: Optional[str] = None
    eval_date: Optional[str] = None
    eval_price: Optional[float] = None
    return_raw: Optional[float] = None
    max_up_raw: Optional[float] = None
    max_down_raw: Optional[float] = None
    path_points: Optional[int] = None


class AlertDetailResponse(BaseModel):
    event_id: str
    push_kind: str
    time_kst: Optional[str] = None
    runtime_date_kst: Optional[str] = None
    schedule_expected: Optional[str] = None
    off_schedule: bool
    outcome_event_target: bool
    delivery_status: Optional[str] = None
    body_text: Optional[str] = None
    body_withheld: bool
    body_partial_delivery: bool
    items: list[ItemRow]
    feedback: list[FeedbackRow]
    outcomes: list[OutcomeRow]


class TableCounts(BaseModel):
    inserted: int
    updated: int
    unchanged: int


class SyncResponse(BaseModel):
    ok: bool
    failure_kind: Optional[str] = None
    attempted_at: str
    counts: Optional[dict[str, TableCounts]] = None


class FeedbackRequest(BaseModel):
    helpfulness: HelpfulnessLiteral
    action: Optional[ActionLiteral] = None
    memo: Optional[str] = None


class FeedbackResponse(FeedbackRow):
    event_id: str


@router.get("/alerts", response_model=AlertListResponse)
def get_alerts(
    date: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    kind: KindLiteral = "all",
) -> AlertListResponse:
    return AlertListResponse(**views.list_alerts(date, kind))


@router.get("/alerts/{event_id}", response_model=AlertDetailResponse)
def get_alert_detail(event_id: str) -> AlertDetailResponse:
    detail = views.alert_detail(event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="로컬 사본에 없는 알림입니다.")
    return AlertDetailResponse(**detail)


@router.post("/sync", response_model=SyncResponse)
def post_sync() -> SyncResponse:
    result = sync.sync_once()
    if result["failure_kind"] == sync.BUSY:
        raise HTTPException(
            status_code=409, detail="원장 새로고침이 이미 진행 중입니다."
        )
    return SyncResponse(**result)


@router.post("/alerts/{event_id}/feedback", response_model=FeedbackResponse)
def post_feedback(event_id: str, req: FeedbackRequest) -> FeedbackResponse:
    try:
        saved = store.add_feedback(
            event_id, helpfulness=req.helpfulness, action=req.action, memo=req.memo
        )
    except store.FeedbackError as e:
        raise HTTPException(status_code=_FEEDBACK_HTTP[e.code], detail=str(e))
    return FeedbackResponse(**saved)
