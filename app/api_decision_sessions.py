"""Decision Evidence API — AI 투자세션 기록 1차 (POC2).

엔드포인트:
- POST /decision/sessions       : AI 질문 / 답변 / 메모 / 1차 판정 / 스냅샷 저장.
- GET  /decision/sessions       : 최근 기록 목록 (요약).
- GET  /decision/sessions/{id}  : 특정 기록 상세.

본 router 는 매매 자동화 / Telegram 전송 / OCI PUSH / AI API 직접 호출과는
완전히 분리된 read/write 경로이며, ml / 매수·매도 판단 / 매매 결과 추적도
하지 않는다. 책임은 사용자가 외부 AI 채널에서 받은 텍스트의 영속 저장과
조회까지다.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.decision_evidence_store import (
    ALLOWED_USER_VERDICTS,
    DEFAULT_DB_PATH,
    DEFAULT_USER_VERDICT,
    DecisionValidationError,
    get_record,
    insert_record,
    list_recent_records,
)

UserVerdictLiteral = Literal[
    "useful", "needs_constituents", "needs_market_compare", "hold"
]

router = APIRouter()


class DecisionFiltersModel(BaseModel):
    # 4 필드 모두 required (default 없음) — 저장 시점 snapshot 핵심 데이터이므로
    # 누락은 fail-loud 422 로 드러난다. default True 로 덮으면 실제 적용 필터와
    # 다른 값이 영속화될 수 있어 검증자 B-1 NOTE 로 차단된다.
    exclude_inverse: bool = Field(...)
    exclude_leveraged: bool = Field(...)
    exclude_synthetic: bool = Field(...)
    exclude_futures: bool = Field(...)


class DecisionCandidateSnapshot(BaseModel):
    """저장 시점 후보 1건. Market Discovery 응답 형태가 바뀌어도 기록은 불변이어야
    하므로 frontend 가 보낸 raw dict 를 그대로 저장한다 (느슨 모델)."""

    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    daily_return_pct: Optional[float] = None
    one_month_return_pct: Optional[float] = None
    three_month_return_pct: Optional[float] = None
    tags: list[str] = []


class CreateDecisionSessionRequest(BaseModel):
    asof: str = Field(..., min_length=1)
    source_screen: str = Field(..., min_length=1)
    filters: DecisionFiltersModel
    candidate_snapshot: list[DecisionCandidateSnapshot]
    question_text: str = Field(..., min_length=1)
    answer_text: str = Field(..., min_length=1)
    user_memo: str = ""
    user_verdict: UserVerdictLiteral = DEFAULT_USER_VERDICT  # type: ignore[assignment]
    next_checks: list[str] = []
    linked_market_refresh_id: Optional[str] = None


class CreateDecisionSessionResponse(BaseModel):
    status: str  # "ok"
    id: str
    created_at: str


class DecisionSessionSummary(BaseModel):
    id: str
    created_at: str
    asof: str
    source_screen: str
    user_verdict: str
    summary: str
    candidate_count: int


class ListDecisionSessionsResponse(BaseModel):
    status: str  # "ok"
    records: list[DecisionSessionSummary]


class DecisionSessionDetail(BaseModel):
    id: str
    created_at: str
    updated_at: str
    asof: str
    source_screen: str
    filters: DecisionFiltersModel
    candidate_snapshot: list[DecisionCandidateSnapshot]
    question_text: str
    answer_text: str
    user_memo: str
    user_verdict: str
    next_checks: list[str]
    linked_market_refresh_id: Optional[str] = None


class GetDecisionSessionResponse(BaseModel):
    # status 는 "ok" 또는 "not_found" — record 는 not_found 시 None.
    status: str
    record: Optional[DecisionSessionDetail] = None
    message: Optional[str] = None


@router.post("/decision/sessions", response_model=CreateDecisionSessionResponse)
def post_decision_session(
    req: CreateDecisionSessionRequest,
) -> CreateDecisionSessionResponse:
    try:
        saved = insert_record(
            asof=req.asof,
            source_screen=req.source_screen,
            filters=req.filters.model_dump(),
            candidate_snapshot=[c.model_dump() for c in req.candidate_snapshot],
            question_text=req.question_text,
            answer_text=req.answer_text,
            user_memo=req.user_memo,
            user_verdict=req.user_verdict,
            next_checks=list(req.next_checks),
            linked_market_refresh_id=req.linked_market_refresh_id,
            db_path=DEFAULT_DB_PATH,
        )
    except DecisionValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return CreateDecisionSessionResponse(
        status="ok", id=saved["id"], created_at=saved["created_at"]
    )


@router.get("/decision/sessions", response_model=ListDecisionSessionsResponse)
def get_decision_sessions(
    limit: int = Query(default=10, ge=1, le=200),
) -> ListDecisionSessionsResponse:
    rows = list_recent_records(limit=limit, db_path=DEFAULT_DB_PATH)
    return ListDecisionSessionsResponse(
        status="ok",
        records=[DecisionSessionSummary(**r) for r in rows],
    )


@router.get("/decision/sessions/{record_id}", response_model=GetDecisionSessionResponse)
def get_decision_session_detail(record_id: str) -> GetDecisionSessionResponse:
    record = get_record(record_id, db_path=DEFAULT_DB_PATH)
    if record is None:
        return GetDecisionSessionResponse(
            status="not_found",
            record=None,
            message="Decision session not found.",
        )
    return GetDecisionSessionResponse(
        status="ok",
        record=DecisionSessionDetail(
            id=record["id"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
            asof=record["asof"],
            source_screen=record["source_screen"],
            filters=DecisionFiltersModel(**record["filters"]),
            candidate_snapshot=[
                DecisionCandidateSnapshot(**c) for c in record["candidate_snapshot"]
            ],
            question_text=record["question_text"],
            answer_text=record["answer_text"],
            user_memo=record["user_memo"],
            user_verdict=record["user_verdict"],
            next_checks=list(record["next_checks"]),
            linked_market_refresh_id=record["linked_market_refresh_id"],
        ),
    )


# enum import re-export 가드 (모듈 외부에서 ALLOWED_USER_VERDICTS 참조 보장).
__all__ = [
    "router",
    "ALLOWED_USER_VERDICTS",
]
