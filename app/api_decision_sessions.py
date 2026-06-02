"""Decision Evidence API — AI Sessions / Context Bridge (POC2).

엔드포인트:
- POST /decision/sessions       : AI 질문 / GPT·Gemini·Claude 3개 답변 / 메모 /
  1차 판정 / 스냅샷 저장.
- GET  /decision/sessions       : 최근 기록 목록 (요약 + has_* 플래그).
- GET  /decision/sessions/{id}  : 특정 기록 상세 (3 답변 분리).

2026-05-21 변경: 단일 answer_text → gpt_answer_text / gemini_answer_text /
claude_answer_text 3 분리. 본 router 는 매매 자동화 / Telegram 전송 / OCI
PUSH / AI API 직접 호출과 완전히 분리된 read/write 경로다.
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
    # 4 필드 모두 required (default 없음) — snapshot 핵심 데이터 fail-loud.
    exclude_inverse: bool = Field(...)
    exclude_leveraged: bool = Field(...)
    exclude_synthetic: bool = Field(...)
    exclude_futures: bool = Field(...)


class DecisionCandidateSnapshot(BaseModel):
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
    # 3 답변 모두 default "" — 최소 1개 이상 채워야 한다는 정책은 store 가
    # DecisionValidationError 로 검증한다 (단일 필드의 empty 와 그룹 필수의 구분).
    gpt_answer_text: str = ""
    gemini_answer_text: str = ""
    claude_answer_text: str = ""
    user_memo: str = ""
    user_verdict: UserVerdictLiteral = DEFAULT_USER_VERDICT  # type: ignore[assignment]
    next_checks: list[str] = []
    linked_market_refresh_id: Optional[str] = None
    # 2026-05-22 Market Regime & Benchmark Context — 저장 시점 시장 문맥 스냅샷.
    # 자유 schema dict (frontend 가 보낸 그대로 저장). None / 빈 dict 모두 허용.
    market_context_snapshot: Optional[dict] = None
    # 2026-05-27 ETF Constituents & Overlap 1차 — 저장 시점 구성종목 / 중복률.
    constituent_snapshot: Optional[dict] = None
    overlap_snapshot: Optional[dict] = None
    # 2026-06-01 Market Discovery Evidence Closeout 1차 — 단기 흐름 + 데이터 품질.
    short_term_momentum_snapshot: Optional[dict] = None
    data_quality_snapshot: Optional[dict] = None


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
    has_gpt_answer: bool
    has_gemini_answer: bool
    has_claude_answer: bool


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
    gpt_answer_text: str
    gemini_answer_text: str
    claude_answer_text: str
    user_memo: str
    user_verdict: str
    next_checks: list[str]
    linked_market_refresh_id: Optional[str] = None
    # 2026-05-22 — 저장 시점 시장 문맥 (free dict, frontend 가 보낸 그대로).
    market_context_snapshot: dict = {}
    # 2026-05-27 — 저장 시점 구성종목 / 중복률 스냅샷 (free dict).
    constituent_snapshot: dict = {}
    overlap_snapshot: dict = {}
    # 2026-06-01 — 저장 시점 단기 흐름 / 데이터 품질 스냅샷.
    short_term_momentum_snapshot: dict = {}
    data_quality_snapshot: dict = {}


class GetDecisionSessionResponse(BaseModel):
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
            gpt_answer_text=req.gpt_answer_text,
            gemini_answer_text=req.gemini_answer_text,
            claude_answer_text=req.claude_answer_text,
            user_memo=req.user_memo,
            user_verdict=req.user_verdict,
            next_checks=list(req.next_checks),
            linked_market_refresh_id=req.linked_market_refresh_id,
            market_context_snapshot=req.market_context_snapshot,
            constituent_snapshot=req.constituent_snapshot,
            overlap_snapshot=req.overlap_snapshot,
            short_term_momentum_snapshot=req.short_term_momentum_snapshot,
            data_quality_snapshot=req.data_quality_snapshot,
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
            gpt_answer_text=record["gpt_answer_text"],
            gemini_answer_text=record["gemini_answer_text"],
            claude_answer_text=record["claude_answer_text"],
            user_memo=record["user_memo"],
            user_verdict=record["user_verdict"],
            next_checks=list(record["next_checks"]),
            linked_market_refresh_id=record["linked_market_refresh_id"],
            market_context_snapshot=record.get("market_context_snapshot") or {},
            constituent_snapshot=record.get("constituent_snapshot") or {},
            overlap_snapshot=record.get("overlap_snapshot") or {},
            short_term_momentum_snapshot=(
                record.get("short_term_momentum_snapshot") or {}
            ),
            data_quality_snapshot=record.get("data_quality_snapshot") or {},
        ),
    )


__all__ = [
    "router",
    "ALLOWED_USER_VERDICTS",
]
