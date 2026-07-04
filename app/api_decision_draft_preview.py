"""POST /decision-draft/preview — 선택 ETF 임시 판단 근거 미리보기.

지시문 §5 원칙:
- 저장 없는 preview 전용 endpoint (기존 PENDING draft 경로와 완전 분리).
- 요청은 target_kind + ticker 만. raw evidence / 초안 ID / LLM 문장 / 승인 상태
  를 클라이언트가 전달하지 않는다.
- 서버는 SQLite / 기존 비교·시장 참고 서비스에서 evidence 를 read → 결정적으로
  텍스트 조립 → 응답 반환.
- 어떤 DB 상태도 생성·수정·삭제하지 않는다.
- 외부 시세 호출·자동 조회·ML 실행 0건.
- 응답에 PENDING ID / 승인 상태 / 원본 예외 / 소스명 / 프롬프트 노출 X.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.decision_draft_preview_service import (
    ALLOWED_TARGET_KINDS,
    TARGET_KIND_CANDIDATE,
    TARGET_KIND_HOLDING,
    build_preview_text,
)
from app.market_data_store import DEFAULT_DB_PATH

router = APIRouter()

_FAILURE_MESSAGE = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."


class PreviewRequest(BaseModel):
    target_kind: str  # holding / candidate
    ticker: str


class PreviewEvidenceAsOf(BaseModel):
    target_as_of_date: Optional[str] = None
    kodex200_as_of_date: Optional[str] = None
    vix_as_of_date: Optional[str] = None


class PreviewResponse(BaseModel):
    status: str  # ok / error
    target_kind: Optional[str] = None
    ticker: Optional[str] = None
    preview_text: Optional[str] = None
    evidence_as_of: Optional[PreviewEvidenceAsOf] = None
    message: Optional[str] = None


def _load_holdings_evidence(ticker: str) -> Optional[dict[str, Any]]:
    """기존 build_holdings_market_evidence 재사용 (부작용 없음 — SQLite/store read only).

    예외는 catch 하여 None 반환 — 사용자 노출 정보 최소화.
    """
    try:
        from app.holdings import load_holdings_from_file
        from app.holdings_market_evidence import build_holdings_market_evidence
        from app.market_topn import compute_topn

        holdings = load_holdings_from_file()
        topn_payload = compute_topn()
        payload = build_holdings_market_evidence(
            holdings=holdings,
            topn_payload=topn_payload,
        )
        items = payload.get("holdings") or []
        for h in items:
            if str(h.get("ticker") or "") == ticker:
                return h
        return None
    except Exception:  # noqa: BLE001 — 사용자 노출 최소화, 실패 시 None.
        return None


def _load_candidate_evidence(ticker: str) -> Optional[dict[str, Any]]:
    try:
        from app.market_topn import compute_topn

        payload = compute_topn()
        for c in payload.get("candidates") or []:
            if str(c.get("ticker") or "") == ticker:
                return c
        return None
    except Exception:  # noqa: BLE001
        return None


@router.post("/decision-draft/preview", response_model=PreviewResponse)
def post_decision_draft_preview(req: PreviewRequest) -> PreviewResponse:
    """저장 없는 판단 근거 미리보기 생성.

    부작용 0건 — DB write / 외부 호출 / 자동 조회 / ML 실행 없음.
    """
    if req.target_kind not in ALLOWED_TARGET_KINDS:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)
    ticker = (req.ticker or "").strip()
    if not ticker:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    if req.target_kind == TARGET_KIND_HOLDING:
        target_evidence = _load_holdings_evidence(ticker)
    else:
        target_evidence = _load_candidate_evidence(ticker)

    if target_evidence is None:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    result = build_preview_text(
        target_kind=req.target_kind,
        ticker=ticker,
        target_evidence=target_evidence,
        db_path=DEFAULT_DB_PATH,
    )
    if result.status != "ok" or result.preview_text is None:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    return PreviewResponse(
        status="ok",
        target_kind=result.target_kind,
        ticker=result.ticker,
        preview_text=result.preview_text,
        evidence_as_of=PreviewEvidenceAsOf(
            target_as_of_date=(
                result.evidence_as_of.target_as_of_date
                if result.evidence_as_of
                else None
            ),
            kodex200_as_of_date=(
                result.evidence_as_of.kodex200_as_of_date
                if result.evidence_as_of
                else None
            ),
            vix_as_of_date=(
                result.evidence_as_of.vix_as_of_date if result.evidence_as_of else None
            ),
        ),
    )


# TARGET_KIND_CANDIDATE 는 import 되지만 조건 분기에서 else 처리 — flake8 F401 회피.
_ = TARGET_KIND_CANDIDATE
