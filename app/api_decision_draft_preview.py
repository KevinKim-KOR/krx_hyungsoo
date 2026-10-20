"""POST /decision-draft/preview — 선택 ETF 임시 판단 근거 미리보기.

지시문 §5 원칙:
- 저장 없는 preview 전용 endpoint (기존 PENDING draft 경로와 완전 분리).
- 요청은 target_kind + ticker (+ POC5-23 후보만 화면 목록 조건 선택 필드). raw evidence / 초안 ID /
  LLM 문장 / 승인 상태를 클라이언트가 전달하지 않는다.
- 서버는 SQLite / 기존 비교·시장 참고 서비스에서 evidence 를 read → 결정적으로
  텍스트 조립 → 응답 반환.
- 어떤 DB 상태도 생성·수정·삭제하지 않는다.
- 외부 시세 호출·자동 조회·ML 실행 0건.
- 응답에 PENDING ID / 승인 상태 / 원본 예외 / 소스명 / 프롬프트 노출 X.

POC5-23(2026-10-18) — 자료는 화면이 쓰는 두 PC API 응답에서 꺼낸다(`app/decision_preview_sources.py`).
후보 요청은 화면 목록 조건을 선택 필드로 받는다(판정 Q1 (a) · 없으면 기존 기본 조건).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.decision_draft_preview_service import (
    ALLOWED_TARGET_KINDS,
    TARGET_KIND_CANDIDATE,
    TARGET_KIND_HOLDING,
    build_preview_text,
)
from app.decision_preview_sources import (
    CandidateListQuery,
    CandidateListUnavailable,
    load_candidate_bundle,
    load_holding_bundle,
)
from app.market_data_store import DEFAULT_DB_PATH

router = APIRouter()

_FAILURE_MESSAGE = "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요."
# POC5-23 §4 — 현재 조건으로 다시 계산한 목록에 그 종목이 없을 때(다른 조건 값으로 채우지 않음).
_NOT_IN_LIST_MESSAGE = (
    "현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요."
)


class PreviewRequest(BaseModel):
    target_kind: str  # holding / candidate
    ticker: str
    # POC5-23 판정 Q1 (a) — 후보만 · 화면 목록 조건(없으면 기존 기본 조건).
    n: Optional[int] = None
    basis: Optional[str] = None
    order: Optional[str] = None
    exclude_inverse: Optional[bool] = None
    exclude_leveraged: Optional[bool] = None
    exclude_synthetic: Optional[bool] = None
    exclude_futures: Optional[bool] = None
    # POC6-01 — 시장 흐름 묶음 기간(화면 선택 · 없으면 6개월). 허용 밖 = 실패 응답.
    flow_period: Optional[str] = None


FLOW_PERIODS = ("1M", "3M", "6M", "YTD")


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
    # POC5-23 — 생성 시각(KST · 선택 필드).
    generated_at: Optional[str] = None
    message: Optional[str] = None


def _load_holdings_evidence(ticker: str) -> Optional[dict[str, Any]]:
    """보유 종목 하나 — 평가 비중 · 손익(기존 종목 합산 정책) + 화면 근거 묶음(POC5-23).

    - 평가 비중 · 손익률: 화면과 같은 `enrich_holdings` + `_aggregate_enriched_by_ticker`(FIX r5 · r7).
    - 근거: 「보유와 비교」 · 「확인 근거」가 쓰는 `get_holdings_market_evidence_latest()` 응답의 그 종목
      (`load_holding_bundle` · PC 기준일 정정 사본 · 같은 계산).

    FIX r3 예외 정책 그대로 — 데이터 오류(파일 부재 / JSON 파싱 / holdings 검증 / SQLite · 보유 근거
    API 의 손상 응답)만 catch. 프로그래머 오류는 propagate.
    """
    import json
    import logging
    import sqlite3
    import traceback

    from app import market_cache
    from app.holdings import HoldingsValidationError, load as load_holdings
    from app.holdings_enrich import enrich_holdings

    logger = logging.getLogger(__name__)
    try:
        holdings = load_holdings()
        # 화면과 동일하게 market_cache.get_all() 사용 (외부 fetch 0건, cache read).
        all_quotes = market_cache.get_all()
        relevant_quotes = {
            h.ticker: all_quotes[h.ticker] for h in holdings if h.ticker in all_quotes
        }
        enriched = enrich_holdings(holdings, relevant_quotes)
        bundle = load_holding_bundle(ticker, db_path=DEFAULT_DB_PATH)
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        HoldingsValidationError,
        sqlite3.Error,
        HTTPException,
    ) as exc:
        logger.warning(
            "decision-draft/preview: holdings evidence load data error "
            "(ticker=%s): %s\n%s",
            ticker,
            type(exc).__name__,
            traceback.format_exc(),
        )
        return None

    # FIX r7 — 화면의 aggregateHoldingsByTicker 와 동일한 ticker 단위 집계.
    aggregated_row = {
        a["ticker"]: a for a in _aggregate_enriched_by_ticker(enriched)
    }.get(ticker)
    if aggregated_row is None and bundle is None:
        return None

    item = (bundle or {}).get("item") or {}
    return {
        "ticker": ticker,
        "name": (aggregated_row or {}).get("name") or item.get("name"),
        "market_weight_pct": (aggregated_row or {}).get("market_weight_pct"),
        "pnl_rate_pct": (aggregated_row or {}).get("pnl_rate_pct"),
        "bundle": bundle,
    }


def _aggregate_enriched_by_ticker(enriched: list) -> list[dict[str, Any]]:
    """화면 helpers.ts::aggregateHoldingsByTicker 와 동일한 집계 로직 (Python).

    - invested_amount: ticker 그룹 합계
    - eval_amount: ticker 그룹 합계 (한 row 라도 None 이면 그룹 전체 None)
    - pnl_rate_pct: evalSum != null && invested > 0 → (eval - invested)/invested * 100
    - market_weight_pct: evalSum != null && totalEval > 0 → eval / totalEval * 100

    rounding 은 화면과 동일하게 2자리 (helpers.ts 는 round 안 함 — Python 도 그대로).
    단, 화면 표시 시 `fmtPct` 가 `.toFixed(2)` 를 쓰므로 preview 도 fmtPct(_fmt_pct)
    가 동일하게 `.2f` 로 처리. 여기서는 raw float 유지.
    """
    if not enriched:
        return []
    total_eval = sum(
        (row.eval_amount or 0) for row in enriched if row.eval_amount is not None
    )
    # 화면과 정확히 동일하게: totalEval = rows.reduce(acc + (r.eval_amount ?? 0), 0)
    total_eval = sum((row.eval_amount or 0) for row in enriched)

    by_ticker: dict[str, list] = {}
    for row in enriched:
        by_ticker.setdefault(row.ticker, []).append(row)

    result: list[dict[str, Any]] = []
    for ticker, group in by_ticker.items():
        invested = sum(row.invested_amount for row in group)
        eval_sum: Optional[float] = 0.0
        eval_partial = False
        data_missing = False
        for row in group:
            if row.price_missing or row.calc_missing:
                data_missing = True
            if row.eval_amount is None:
                eval_partial = True
            elif eval_sum is not None:
                eval_sum += row.eval_amount
        if eval_partial:
            eval_sum = None

        pnl_rate = (
            ((eval_sum - invested) / invested) * 100.0
            if eval_sum is not None and invested > 0
            else None
        )
        market_weight = (
            (eval_sum / total_eval) * 100.0
            if eval_sum is not None and total_eval > 0
            else None
        )

        result.append(
            {
                "ticker": ticker,
                "name": group[0].name,
                "invested_amount": invested,
                "eval_amount": eval_sum,
                "eval_partial_unavail": eval_partial,
                "pnl_rate_pct": pnl_rate,
                "market_weight_pct": market_weight,
                "data_missing": data_missing,
            }
        )
    return result


def _load_candidate_evidence(
    ticker: str, query: CandidateListQuery
) -> Optional[dict[str, Any]]:
    """후보 하나 — 화면과 같은 목록 조건의 PC 시장 응답 + 선택 1종목 추가 읽기(POC5-23).

    그 조건의 목록에 없으면 None(호출자가 '목록에 없음' 사유로 응답). 예외는 잡지 않는다 — endpoint 경계가
    짧은 실패 응답으로 바꾸고 traceback 을 남긴다(FIX r3 경계 그대로).
    """
    return load_candidate_bundle(ticker, query, db_path=DEFAULT_DB_PATH)


def _list_query(req: PreviewRequest) -> CandidateListQuery:
    base = CandidateListQuery()
    return CandidateListQuery(
        n=req.n if req.n is not None else base.n,
        basis=req.basis if req.basis is not None else base.basis,
        order=req.order if req.order is not None else base.order,
        exclude_inverse=(
            req.exclude_inverse
            if req.exclude_inverse is not None
            else base.exclude_inverse
        ),
        exclude_leveraged=(
            req.exclude_leveraged
            if req.exclude_leveraged is not None
            else base.exclude_leveraged
        ),
        exclude_synthetic=(
            req.exclude_synthetic
            if req.exclude_synthetic is not None
            else base.exclude_synthetic
        ),
        exclude_futures=(
            req.exclude_futures
            if req.exclude_futures is not None
            else base.exclude_futures
        ),
    )


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

    # FIX r3 (2026-07-03): loader 는 프로그래머 오류 (import 오타 등) 를 삼키지
    # 않고 propagate. endpoint 경계에서 catch 하여 사용자 친화 실패 응답을 유지.
    # 서버 로그에는 traceback 이 loader / 여기 두 곳 모두에서 기록되므로 개발자
    # 파악 가능하되, 응답 body 는 계약 그대로 짧은 문구만 노출.
    import logging
    import traceback

    _preview_logger = logging.getLogger(__name__)
    query = _list_query(req)
    if req.target_kind != TARGET_KIND_HOLDING and not query.is_valid():
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)
    flow_period = req.flow_period or "6M"
    if flow_period not in FLOW_PERIODS:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)
    try:
        if req.target_kind == TARGET_KIND_HOLDING:
            target_evidence = _load_holdings_evidence(ticker)
        else:
            target_evidence = _load_candidate_evidence(ticker, query)
            if target_evidence is None:
                return PreviewResponse(status="error", message=_NOT_IN_LIST_MESSAGE)
    except CandidateListUnavailable as exc:
        # 시장 목록 자료 자체가 없음 · 손상 — '목록에 없음'으로 바꾸지 않고 일반 실패.
        _preview_logger.warning(
            "decision-draft/preview: market list unavailable (status=%s)", exc
        )
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)
    except Exception as exc:  # noqa: BLE001 — endpoint 경계 응답 계약 유지
        _preview_logger.error(
            "decision-draft/preview: unexpected loader error "
            "(target_kind=%s, ticker=%s): %s\n%s",
            req.target_kind,
            ticker,
            type(exc).__name__,
            traceback.format_exc(),
        )
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    if target_evidence is None:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    # POC5-23 검증자 r2 — 글 조립(숫자 글 포함)의 예상 밖 예외도 HTTP 500 대신 로더와 같은 짧은 실패 응답
    # (traceback 은 서버 로그에만).
    try:
        result = build_preview_text(
            target_kind=req.target_kind,
            ticker=ticker,
            target_evidence=target_evidence,
            db_path=DEFAULT_DB_PATH,
            flow_period=flow_period,
        )
    except Exception as exc:  # noqa: BLE001 — endpoint 경계 응답 계약 유지
        _preview_logger.error(
            "decision-draft/preview: unexpected text build error "
            "(target_kind=%s, ticker=%s): %s\n%s",
            req.target_kind,
            ticker,
            type(exc).__name__,
            traceback.format_exc(),
        )
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)
    if result.status != "ok" or result.preview_text is None:
        return PreviewResponse(status="error", message=_FAILURE_MESSAGE)

    return PreviewResponse(
        status="ok",
        target_kind=result.target_kind,
        ticker=result.ticker,
        preview_text=result.preview_text,
        generated_at=result.generated_at,
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
