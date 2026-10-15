"""POC2 — Holdings × Market Discovery Evidence 1차 read-only API (2026-06-03).

지시문 §5.1 — `GET /holdings/market-evidence/latest`.

본 라우터는:
- 기존 데이터만 read 한다 (holdings store / SQLite market data / etf_constituents
  cache / etf_nav cache).
- 외부 source 를 호출하지 않는다.
- 데이터를 저장하지 않는다.
- Draft 를 생성하지 않는다.
- 매수 / 매도 / 교체 판단을 반환하지 않는다.

evidence 조립 로직은 `app/holdings_market_evidence.build_holdings_market_evidence()`
가 담당하며, GenerateDraft 흐름이 같은 builder 를 재사용한다 (지시문 §5.10).
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import holdings as holdings_module
from app import market_cache
from app.holdings import HoldingsValidationError, HOLDINGS_FILE
from app.holdings_market_evidence import (
    build_holdings_market_evidence,
    get_holdings_file_mtime_iso,
)
from app.market_data_store import DEFAULT_DB_PATH as MARKET_DB_PATH
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn
from app.pc_price_basis import apply_pc_price_basis, load_recent_price_rows
from app.stored_volume_evidence import (
    StoredVolumeEvidence,
    compute_stored_volume_evidence,
)

router = APIRouter()


# ─── Response models — 지시문 §5.2 의미 보존 ────────────────────────────


class HoldingSnapshot(BaseModel):
    quantity: float
    avg_buy_price: float
    evaluation_amount: Optional[float] = None
    pnl_rate_pct: Optional[float] = None


class TopnMatch(BaseModel):
    # matched_topn_candidate / not_in_current_topn / unavailable
    status: str
    rank: Optional[int] = None
    basis: Optional[str] = None
    candidate_name: Optional[str] = None


class ReturnsPayload(BaseModel):
    # ok / unavailable / partial
    status: str
    one_month_return_pct: Optional[float] = None
    three_month_return_pct: Optional[float] = None
    # 2026-08-16 추가 — 보유↔후보를 같은 기간으로 비교하기 위해. status 판정은
    #   기존대로 1m/3m 기준이며 이 두 필드는 표시 전용이다.
    six_month_return_pct: Optional[float] = None
    twelve_month_return_pct: Optional[float] = None


class ExcessReturnPayload(BaseModel):
    status: str
    vs_kodex200_1m_pctp: Optional[float] = None
    vs_kodex200_3m_pctp: Optional[float] = None


class ShortTermMomentumPayload(BaseModel):
    status: str
    return_5d_pct: Optional[float] = None
    return_10d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    excess_vs_kodex200_5d_pctp: Optional[float] = None
    excess_vs_kodex200_10d_pctp: Optional[float] = None
    excess_vs_kodex200_20d_pctp: Optional[float] = None


class ConstituentsOverlapItem(BaseModel):
    ticker: Optional[str] = None
    name: Optional[str] = None
    weight_pct: Optional[float] = None
    market_core_count: Optional[int] = None


class ConstituentsOverlapPayload(BaseModel):
    # ok / constituents_unavailable / market_core_unavailable / unavailable
    status: str
    overlap_with_market_core: list[ConstituentsOverlapItem] = []


class NavDiscountPayload(BaseModel):
    # ok / warning / partial / unavailable
    status: str
    source: Optional[str] = None
    asof: Optional[str] = None
    nav: Optional[float] = None
    market_price: Optional[float] = None
    discount_rate_pct: Optional[float] = None
    flag: Optional[str] = None
    message: Optional[str] = None


class PriceDates(BaseModel):
    # 실제 계산 이력의 기준일 · 비교 기간 시작일(pc_price_basis).
    end_date: Optional[str] = None
    start_date_5d: Optional[str] = None
    start_date_20d: Optional[str] = None
    # ok / date_mismatch / window_mismatch / unavailable
    comparison: str


class DeclineBand(BaseModel):
    # POC5-13 — 20저장일 하락 구간(pc_price_basis · 경계 = OCI classify_decline).
    judgeable: bool
    # D10_PLUS / D8_10 / D5_8 · 구간 밖이거나 판정 안 함이면 None
    state: Optional[str] = None
    label: Optional[str] = None
    return_20d_pct_1dp: Optional[float] = None
    # date_mismatch / insufficient_history / invalid_value · 판정했으면 None
    unjudged_reason: Optional[str] = None


class HoldingEvidenceItem(BaseModel):
    ticker: str
    name: str
    account_group: str = "일반"
    holding: HoldingSnapshot
    topn_match: TopnMatch
    returns: ReturnsPayload
    excess_return: ExcessReturnPayload
    short_term_momentum: ShortTermMomentumPayload
    constituents_overlap: ConstituentsOverlapPayload
    nav_discount: NavDiscountPayload
    evidence_notes: list[str] = []
    # POC5-09 — PC 화면용 선택 필드(이 응답 사본에만 · 공유 builder 결과에는 없음).
    price_dates: Optional[PriceDates] = None
    stored_volume: Optional[StoredVolumeEvidence] = None
    # POC5-13 — PC 화면용 선택 필드(이 응답 사본에만).
    decline_band: Optional[DeclineBand] = None


class PriceBasisMismatch(BaseModel):
    ticker: str
    name: Optional[str] = None
    end_date: Optional[str] = None


class PriceBasis(BaseModel):
    # PC 비교 기준일 = KODEX200 최신 저장 가격 날짜(단기 흐름 비교 계열).
    reference_date: Optional[str] = None
    reference_ticker: str
    kodex200_start_date_5d: Optional[str] = None
    kodex200_start_date_20d: Optional[str] = None
    date_mismatch: list[PriceBasisMismatch] = []


class EvidenceSummary(BaseModel):
    total_holdings_count: int
    matched_topn_count: int
    not_in_current_topn_count: int
    evidence_unavailable_count: int
    constituents_available_count: int
    constituents_unavailable_count: int
    nav_discount_unavailable_count: int


class MarketContextResponse(BaseModel):
    status: str
    asof: Optional[str] = None
    regime_label: str = "판정불가"
    regime_code: str = "unavailable"


class HoldingsMarketEvidenceResponse(BaseModel):
    status: (
        str  # ok (read-only API 는 항상 ok 로 응답, market 데이터 부재는 warnings 로)
    )
    asof: str
    holdings_asof: Optional[str] = None
    market_asof: Optional[str] = None
    market_context: Optional[MarketContextResponse] = None
    summary: EvidenceSummary
    holdings: list[HoldingEvidenceItem] = []
    # 2026-08-04 POC3-06 §6.1 — 공통 판단 요약(backend 단일 계산 결과). Dashboard·PUSH
    # 가 이 동일 객체를 표시한다. composer 가 만든 dict 를 그대로 통과(중첩 구조 보존).
    judgment_summary: Optional[dict[str, Any]] = None
    # POC5-09 — PC 비교 기준일 · 기준일이 달라 현재 비교에서 뺀 종목(선택 필드).
    price_basis: Optional[PriceBasis] = None
    warnings: list[str] = []


def _to_market_context_response(
    raw: Optional[dict[str, Any]],
) -> Optional[MarketContextResponse]:
    if not raw:
        return None
    return MarketContextResponse(
        status=raw.get("status") or "unavailable",
        asof=raw.get("asof"),
        regime_label=raw.get("regime_label") or "판정불가",
        regime_code=raw.get("regime_code") or "unavailable",
    )


@router.get(
    "/holdings/market-evidence/latest",
    response_model=HoldingsMarketEvidenceResponse,
)
def get_holdings_market_evidence_latest() -> HoldingsMarketEvidenceResponse:
    """보유 ETF × Market Discovery evidence 비교 (지시문 §5.1 / AC-1~2).

    응답 status:
    - 항상 "ok" — read-only API 가 일관되게 응답.
    - market 데이터 부재 / cache 미존재는 holdings 내부 status (unavailable / constituents_unavailable
      / nav_discount.unavailable) + 최상위 warnings 로 표시 (지시문 §5.3 분기 보존).

    holdings 가 비어있어도 200 + 빈 응답 — 기존 GET /holdings 와 동일 정책
    (지시문 §4.1 "기존 빈 상태 처리를 깨뜨리면 안 된다").
    """
    try:
        loaded = holdings_module.load()
    except HoldingsValidationError as e:
        raise HTTPException(status_code=500, detail=f"holdings 저장 파일 손상: {e}")

    holdings_asof = get_holdings_file_mtime_iso(HOLDINGS_FILE)

    # 시세 enrichment 는 캐시에서만 추출 (외부 fetch X — 지시문 §5.1 금지 목록).
    all_quotes = market_cache.get_all()
    relevant_quotes = {
        h.ticker: all_quotes[h.ticker] for h in loaded if h.ticker in all_quotes
    }

    # Market Discovery TOP N 결과 — SQLite read-only (외부 fetch X).
    topn_payload = compute_topn(
        n=DEFAULT_N,
        db_path=MARKET_DB_PATH,
        basis=DEFAULT_BASIS,
        order=DEFAULT_ORDER,
    )

    shared = build_holdings_market_evidence(
        holdings=loaded,
        topn_payload=topn_payload,
        market_quotes=relevant_quotes,
        db_path=MARKET_DB_PATH,
        holdings_asof=holdings_asof,
    )

    # POC5-09 — PC 화면용 사본: 가격 흐름 기준일 정정 · 최대 3개 재선정(공유 builder
    # 결과는 PUSH · 초안이 쓰므로 그대로) + 저장 거래량. 같은 최근 행 읽기를 둘이 쓴다.
    rows_by_ticker = load_recent_price_rows(
        [h["ticker"] for h in shared.get("holdings", [])], db_path=MARKET_DB_PATH
    )
    evidence = apply_pc_price_basis(shared, rows_by_ticker)

    return HoldingsMarketEvidenceResponse(
        status=evidence["status"],
        asof=evidence["asof"],
        holdings_asof=evidence.get("holdings_asof"),
        market_asof=evidence.get("market_asof"),
        market_context=_to_market_context_response(evidence.get("market_context")),
        summary=EvidenceSummary(**evidence["summary"]),
        holdings=[
            HoldingEvidenceItem(
                **h,
                stored_volume=compute_stored_volume_evidence(
                    h["ticker"], rows_by_ticker[h["ticker"]]
                ),
            )
            for h in evidence.get("holdings", [])
        ],
        judgment_summary=evidence.get("judgment_summary"),
        price_basis=PriceBasis(**evidence["price_basis"]),
        warnings=list(evidence.get("warnings") or []),
    )
