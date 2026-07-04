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
    """canonical 보유 evidence 조립 — 화면과 동일 원천·동일 계산 (FIX r5).

    화면 (HoldingsCompareView) 이 사용하는 두 데이터 원천을 그대로 결합한다:
      - GET /holdings/enriched  → enrich_holdings 로 market_weight_pct /
        pnl_rate_pct 계산 (market_cache.get_all() quotes 기준)
      - GET /holdings/market-evidence/latest → build_holdings_market_evidence
        로 short_term_momentum / data_quality / overlap 계산 (동일 quotes 사용)

    화면과 preview 가 서로 다른 계산 경로를 쓰지 않도록 두 결과를 **동일 시점·
    동일 quotes** 로 조립한 뒤 ticker 별 dict 반환.

    FIX r3 예외 정책 그대로:
    - 데이터 오류 (파일 부재 / JSON 파싱 / holdings 검증 / SQLite) 만 catch.
    - 프로그래머 오류 (ImportError / AttributeError / TypeError) 는 propagate.
    """
    import json
    import logging
    import sqlite3
    import traceback

    from app import market_cache
    from app.holdings import HoldingsValidationError, load as load_holdings
    from app.holdings_enrich import enrich_holdings
    from app.holdings_market_evidence import build_holdings_market_evidence
    from app.market_topn import compute_topn

    logger = logging.getLogger(__name__)
    try:
        holdings = load_holdings()
        # 화면과 동일하게 market_cache.get_all() 사용 (외부 fetch 0건, cache read).
        all_quotes = market_cache.get_all()
        relevant_quotes = {
            h.ticker: all_quotes[h.ticker] for h in holdings if h.ticker in all_quotes
        }
        enriched = enrich_holdings(holdings, relevant_quotes)
        topn_payload = compute_topn()
        evidence_payload = build_holdings_market_evidence(
            holdings=holdings,
            topn_payload=topn_payload,
            market_quotes=relevant_quotes,
        )
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        HoldingsValidationError,
        sqlite3.Error,
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
    # 중복 ticker 보유 케이스에서 raw row 를 그대로 선택하면 화면 집계와 값이
    # 갈라진다. 화면 helpers.ts::aggregateHoldingsByTicker 로직을 그대로 이식.
    aggregated = _aggregate_enriched_by_ticker(enriched)
    aggregated_by_ticker = {a["ticker"]: a for a in aggregated}
    evidence_by_ticker = {
        str(h.get("ticker") or ""): h for h in (evidence_payload.get("holdings") or [])
    }
    aggregated_row = aggregated_by_ticker.get(ticker)
    evidence_row = evidence_by_ticker.get(ticker)
    if aggregated_row is None and evidence_row is None:
        return None

    canonical: dict[str, Any] = {"ticker": ticker}
    if aggregated_row is not None:
        canonical["name"] = aggregated_row.get("name")
        canonical["market_weight_pct"] = aggregated_row.get("market_weight_pct")
        canonical["pnl_rate_pct"] = aggregated_row.get("pnl_rate_pct")
    else:
        canonical["name"] = evidence_row.get("name") if evidence_row else None
        canonical["market_weight_pct"] = None
        canonical["pnl_rate_pct"] = None
    if evidence_row is not None:
        canonical["short_term_momentum"] = evidence_row.get("short_term_momentum")
        canonical["data_quality"] = evidence_row.get("data_quality")
        canonical["overlap"] = evidence_row.get("overlap")
    return canonical


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


def _load_candidate_evidence(ticker: str) -> Optional[dict[str, Any]]:
    """FIX r3 (2026-07-03): 프로그래머 오류 propagate, 데이터 오류만 catch."""
    import logging
    import sqlite3
    import traceback

    from app.market_topn import compute_topn

    logger = logging.getLogger(__name__)
    try:
        payload = compute_topn()
    except sqlite3.Error as exc:
        logger.warning(
            "decision-draft/preview: candidate evidence load data error "
            "(ticker=%s): %s\n%s",
            ticker,
            type(exc).__name__,
            traceback.format_exc(),
        )
        return None

    for c in payload.get("candidates") or []:
        if str(c.get("ticker") or "") == ticker:
            return c
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

    # FIX r3 (2026-07-03): loader 는 프로그래머 오류 (import 오타 등) 를 삼키지
    # 않고 propagate. endpoint 경계에서 catch 하여 사용자 친화 실패 응답을 유지.
    # 서버 로그에는 traceback 이 loader / 여기 두 곳 모두에서 기록되므로 개발자
    # 파악 가능하되, 응답 body 는 계약 그대로 짧은 문구만 노출.
    import logging
    import traceback

    _preview_logger = logging.getLogger(__name__)
    try:
        if req.target_kind == TARGET_KIND_HOLDING:
            target_evidence = _load_holdings_evidence(ticker)
        else:
            target_evidence = _load_candidate_evidence(ticker)
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
