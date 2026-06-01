"""ETF 구성종목 API — Constituents & Overlap 1차 (POC2 — 2026-05-27).

엔드포인트 (지시문 §8):
- POST /market/constituents/refresh     : 후보 tickers 만 외부 수집 + 캐시.
- GET  /market/constituents/analysis    : 구성종목 + 집중도 + 중복률 + repeated.

본 router 는 매매 자동화 / Telegram / OCI PUSH / AI API 와 무관 — 외부 KRX
데이터 수집 (cap/cache/delay/budget 가드) + 로컬 SQLite 분석만.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import (
    etf_constituents_store,
)  # lookup-style attribute access (monkeypatch 친화).
from app.etf_constituents_analysis import (
    DEFAULT_TOP_K_FOR_OVERLAP,
    compute_analysis,
)
from app.etf_constituents_service import (
    DEFAULT_TOP_K,
    MAX_TICKERS_PER_REQUEST,
    MAX_TOP_K,
    refresh_constituents,
)
from app.etf_constituents_store import latest_constituent_asof

router = APIRouter()


class RefreshConstituentsRequest(BaseModel):
    asof: str = Field(..., min_length=1)
    tickers: list[str] = Field(..., min_length=1)
    top_k: int = DEFAULT_TOP_K
    force: bool = False


class RefreshConstituentsItem(BaseModel):
    ticker: str
    status: str
    source: Optional[str] = None
    constituent_count: int = 0
    from_cache: bool = False
    message: Optional[str] = None


class RefreshConstituentsResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    message: Optional[str] = None
    asof: Optional[str] = None
    requested_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    cached_count: int = 0
    fetched_count: int = 0
    skipped_count: int = 0
    source: Optional[str] = None
    items: list[RefreshConstituentsItem] = []


@router.post("/market/constituents/refresh", response_model=RefreshConstituentsResponse)
def post_constituents_refresh(
    req: RefreshConstituentsRequest,
) -> RefreshConstituentsResponse:
    if not req.tickers:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    if req.top_k is not None and req.top_k > MAX_TOP_K:
        raise HTTPException(
            status_code=422,
            detail=f"top_k must be <= {MAX_TOP_K}.",
        )
    # db_path 는 호출 시점 module attribute lookup — 테스트 monkeypatch 반영.
    result = refresh_constituents(
        asof=req.asof,
        tickers=list(req.tickers),
        top_k=req.top_k or DEFAULT_TOP_K,
        force=req.force,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
    )
    return RefreshConstituentsResponse(
        status=result.status,
        reason=result.reason,
        message=result.message,
        asof=result.asof,
        requested_count=result.requested_count,
        success_count=result.success_count,
        fail_count=result.fail_count,
        cached_count=result.cached_count,
        fetched_count=result.fetched_count,
        skipped_count=result.skipped_count,
        source=result.source,
        items=[
            RefreshConstituentsItem(
                ticker=i.ticker,
                status=i.status,
                source=i.source,
                constituent_count=i.constituent_count,
                from_cache=i.from_cache,
                message=i.message,
            )
            for i in result.items
        ],
    )


# ─── GET /market/constituents/analysis ────────────────────────────────


class TopHolding(BaseModel):
    rank: int
    ticker: Optional[str] = None
    name: Optional[str] = None
    weight_pct: Optional[float] = None
    # 2026-05-31 — Naver 통합. 해외형 종목은 ticker=null, 아래 식별자가 채워짐.
    constituent_isin: Optional[str] = None
    constituent_reuters_code: Optional[str] = None
    market_type: Optional[str] = None


class Concentration(BaseModel):
    top1_weight_pct: Optional[float] = None
    top3_weight_pct: Optional[float] = None
    top5_weight_pct: Optional[float] = None
    top10_weight_pct: Optional[float] = None


class ConstituentItem(BaseModel):
    etf_ticker: str
    etf_name: Optional[str] = None
    status: str
    source: Optional[str] = None
    asof: str
    top_holdings: list[TopHolding] = []
    concentration: Concentration = Concentration()


class OverlapCommonHolding(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    left_weight_pct: Optional[float] = None
    right_weight_pct: Optional[float] = None


class OverlapPair(BaseModel):
    left_ticker: str
    right_ticker: str
    common_count_top10: int = 0
    weighted_overlap_pct: Optional[float] = None
    common_holdings: list[OverlapCommonHolding] = []


class RepeatedCoreItem(BaseModel):
    etf_ticker: str
    weight_pct: Optional[float] = None


class RepeatedCoreHolding(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    appears_in_etf_count: int = 0
    items: list[RepeatedCoreItem] = []


class AnalysisCoverage(BaseModel):
    requested_count: int
    available_count: int
    unavailable_count: int


class ConstituentsAnalysisResponse(BaseModel):
    status: str
    asof: str
    top_k: int
    coverage: AnalysisCoverage
    constituents: list[ConstituentItem] = []
    overlap_matrix: list[OverlapPair] = []
    repeated_core_holdings: list[RepeatedCoreHolding] = []


def _parse_tickers_csv(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


@router.get(
    "/market/constituents/analysis", response_model=ConstituentsAnalysisResponse
)
def get_constituents_analysis(
    tickers: str = Query(..., description="콤마 구분 ETF tickers"),
    # 2026-05-27 FIX (검증자 B-6 NOTE 반영) — 지시문 §8.2 예시는 asof 없이 호출.
    # asof 누락 시 ticker 별 latest_constituent_asof 중 MAX 를 사용 (서버가
    # 가장 최근 수집 시점 자동 선택).
    asof: Optional[str] = Query(default=None),
    top_k: int = Query(default=DEFAULT_TOP_K_FOR_OVERLAP, ge=1, le=MAX_TOP_K),
) -> ConstituentsAnalysisResponse:
    ticker_list = _parse_tickers_csv(tickers)
    if not ticker_list:
        raise HTTPException(status_code=422, detail="tickers must not be empty.")
    if len(ticker_list) > MAX_TICKERS_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=(
                f"tickers count > {MAX_TICKERS_PER_REQUEST} — "
                "use POST /market/constituents/refresh first."
            ),
        )

    effective_asof = asof
    if not effective_asof:
        latest_dates: list[str] = []
        for tk in ticker_list:
            d = latest_constituent_asof(
                tk, db_path=etf_constituents_store.DEFAULT_DB_PATH
            )
            if d:
                latest_dates.append(d)
        # 데이터 1건도 없으면 today 로 fallback (compute_analysis 가 모두
        # unavailable 로 결과 반환).
        effective_asof = (
            max(latest_dates)
            if latest_dates
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )

    payload = compute_analysis(
        tickers=ticker_list,
        asof=effective_asof,
        top_k=top_k,
        db_path=etf_constituents_store.DEFAULT_DB_PATH,
    )
    return ConstituentsAnalysisResponse(**payload)
