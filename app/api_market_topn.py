"""PC Market Discovery — SQLite 직접 계산 + refresh background job + status API.

2026-05-18 변경 (Market Discovery SQLite Direct Refresh):
- GET  /market/topn/latest      는 SQLite 에서 직접 TOP N 을 계산한다 (artifact 폐기).
- POST /market/refresh          신규 — FDR 수집을 background job 으로 실행.
  · single-flight + 6h cooldown 가드.
- GET  /market/refresh/status   신규 — 현재/마지막 refresh 상태.

namespace 결정 (2026-05-18, 설계자 직접 확인 후 환원):
- 지시문 §5.2 는 `/market/refresh` / `/market/refresh/status` 그대로 사용.
- 기존 `app/api.py` 의 holdings naver 시세 갱신 endpoint 는 `/holdings/market/refresh`
  로 이동하여 충돌 해소. backward compatibility alias 미제공.

JSON artifact 파일은 생성/저장하지 않는다 (state/market/ 하위 어떤 .json 도 미사용).
SQLite 만이 시장 데이터의 단일 SSOT.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.etf_nav_fetcher import classify_discount_flag
from app.etf_nav_store import fetch_latest_nav
from app.market_data_store import DEFAULT_DB_PATH
from app.market_refresh_service import (
    DEFAULT_COOLDOWN_HOURS,
    get_state_snapshot,
    start_refresh_job,
)
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn
from app.short_term_momentum import (
    compute_daily_return_check,
    compute_short_term_momentum_batch,
)

BasisLiteral = Literal["daily", "one_month", "three_month"]
OrderLiteral = Literal["desc", "asc"]

router = APIRouter()


# ─── /market/topn/latest ──────────────────────────────────────────────


class MarketTopNEntry(BaseModel):
    # 결측은 None 통과, 강제 변환 / 0·"" / 0.0 fallback 절대 금지 — Frontend 가 "-" 표시.
    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    return_pct: Optional[float] = None
    basis_start_date: Optional[str] = None
    basis_end_date: Optional[str] = None
    # 2026-05-18 후보 정제 1차 — ETF 이름 기반 상품 태그 (inverse / leveraged / synthetic / futures).
    tags: list[str] = []


class MarketTopNFilters(BaseModel):
    exclude_inverse: bool = True
    exclude_leveraged: bool = True
    exclude_synthetic: bool = True
    exclude_futures: bool = True


class MarketLatestRefresh(BaseModel):
    refresh_id: Optional[str] = None
    source: Optional[str] = None
    asof: Optional[str] = None
    attempted_count: Optional[int] = None
    success_count: Optional[int] = None
    fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    error_summary: Optional[str] = None
    created_at: Optional[str] = None


class MarketPeriodReturn(BaseModel):
    return_pct: Optional[float] = None
    basis_start_date: Optional[str] = None
    basis_end_date: Optional[str] = None


class MarketReturns(BaseModel):
    daily: Optional[MarketPeriodReturn] = None
    one_month: Optional[MarketPeriodReturn] = None
    three_month: Optional[MarketPeriodReturn] = None
    # 2026-06-08 — 표시 전용 신규 기간 (UI 요청). 정렬 X.
    six_month: Optional[MarketPeriodReturn] = None
    twelve_month: Optional[MarketPeriodReturn] = None
    three_year: Optional[MarketPeriodReturn] = None


class ShortTermMomentumStartDates(BaseModel):
    five_d: Optional[str] = None
    ten_d: Optional[str] = None
    twenty_d: Optional[str] = None


class ShortTermMomentumPayload(BaseModel):
    status: str  # ok / unavailable
    return_5d_pct: Optional[float] = None
    return_10d_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    excess_vs_kodex200_5d_pctp: Optional[float] = None
    excess_vs_kodex200_10d_pctp: Optional[float] = None
    excess_vs_kodex200_20d_pctp: Optional[float] = None
    start_dates: Optional[ShortTermMomentumStartDates] = None
    end_date: Optional[str] = None
    message: Optional[str] = None


class DailyReturnCheckPayload(BaseModel):
    status: str  # ok / warning / unavailable
    daily_return_pct: Optional[float] = None
    flag: Optional[str] = None
    threshold_pct: Optional[float] = None
    message: Optional[str] = None


class NavDiscountPayload(BaseModel):
    status: str  # ok / unavailable / partial
    asof: Optional[str] = None
    nav: Optional[float] = None
    market_price: Optional[float] = None
    discount_rate_pct: Optional[float] = None
    flag: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None


class DataQualityPayload(BaseModel):
    status: str  # ok / warning / unavailable
    daily_return_check: DailyReturnCheckPayload
    nav_discount: NavDiscountPayload
    warnings: list[str] = []


class MarketCandidate(BaseModel):
    """통합 후보 테이블 entry — 3 기간 수익률 + 선택된 basis 의 요약 필드."""

    rank: Optional[int] = None
    ticker: Optional[str] = None
    name: Optional[str] = None
    tags: list[str] = []
    selected_return_pct: Optional[float] = None
    selected_basis_start_date: Optional[str] = None
    selected_basis_end_date: Optional[str] = None
    returns: MarketReturns = MarketReturns()
    # 2026-05-22 Market Regime & Benchmark Context 1차 — KODEX200/KOSPI 대비
    # 1m/3m 초과수익 (percentage point). KOSPI 데이터 없으면 vs_kospi_* 는 null.
    excess_return: Optional["MarketCandidateExcessReturn"] = None
    # 2026-06-01 Market Discovery Evidence Closeout 1차 — 단기 흐름 + 데이터 품질.
    short_term_momentum: Optional[ShortTermMomentumPayload] = None
    data_quality: Optional[DataQualityPayload] = None


class MarketCandidateExcessReturn(BaseModel):
    vs_kodex200_1m_pctp: Optional[float] = None
    vs_kodex200_3m_pctp: Optional[float] = None
    vs_kospi_1m_pctp: Optional[float] = None
    vs_kospi_3m_pctp: Optional[float] = None


MarketCandidate.model_rebuild()


# ─── Market Regime & Benchmark Context (지시문 §9.1) ──────────────────


class MarketContextKodex200(BaseModel):
    status: str  # ok / unavailable
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None
    return_1m_pct: Optional[float] = None
    return_3m_pct: Optional[float] = None
    close: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    ma20_position: Optional[str] = None  # above / below
    ma60_position: Optional[str] = None


class MarketContextKospi(BaseModel):
    status: str  # ok / unavailable
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None
    return_1m_pct: Optional[float] = None
    return_3m_pct: Optional[float] = None


class MarketContextResponse(BaseModel):
    status: str  # ok / partial / unavailable
    asof: Optional[str] = None
    primary_benchmark: str = "KODEX200"
    regime_label: str  # 상승장 / 보합장 / 하락장 / 판정불가
    regime_code: str  # bull / neutral / bear / unavailable
    regime_score: Optional[int] = None
    regime_reasons: list[str] = []
    kodex200: MarketContextKodex200
    kospi: MarketContextKospi
    warnings: list[str] = []


class MarketTopNResponse(BaseModel):
    status: str  # ok / missing / empty / invalid
    error: Optional[str] = None
    asof: Optional[str] = None
    source: Optional[str] = None
    n: Optional[int] = None
    # 2026-05-18 통합 후보 테이블 1차 — basis: daily / one_month / three_month.
    basis: Optional[str] = None
    # 2026-05-19 Grid 사용성 FIX — 정렬 방향: desc / asc.
    order: Optional[str] = None
    universe_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    latest_refresh: Optional[MarketLatestRefresh] = None
    runtime_seconds: Optional[float] = None
    # 통합 후보 테이블 (frontend 기본 렌더 소스).
    candidates: list[MarketCandidate] = []
    # 호환용 — 기존 분리 테이블도 유지 (frontend 사용 안 함).
    daily_topn: list[MarketTopNEntry] = []
    one_month_topn: list[MarketTopNEntry] = []
    three_month_topn: list[MarketTopNEntry] = []
    period_exclusions: dict[str, dict[str, int]] = {}
    # 2026-05-18 후보 정제 1차 — 활성 필터 / 기간별 필터 제외 집계.
    filters: MarketTopNFilters = MarketTopNFilters()
    filter_exclusions: dict[str, dict[str, int]] = {}
    candidate_filter_exclusions: dict[str, int] = {}
    topn_caveat: Optional[str] = None
    # 2026-05-22 — Market Regime & Benchmark Context (지시문 §9.1).
    # ok/partial/unavailable + KODEX200 (필수) + KOSPI (보조). status=missing/
    # empty/invalid 인 경우 null 로 노출.
    market_context: Optional[MarketContextResponse] = None


def _entry_to_model(raw: dict) -> MarketTopNEntry:
    return MarketTopNEntry(
        rank=raw.get("rank"),
        ticker=raw.get("ticker"),
        name=raw.get("name"),
        return_pct=raw.get("return_pct"),
        basis_start_date=raw.get("basis_start_date"),
        basis_end_date=raw.get("basis_end_date"),
        tags=list(raw.get("tags") or []),
    )


def _period_to_model(raw: Optional[dict]) -> Optional[MarketPeriodReturn]:
    if raw is None:
        return None
    return MarketPeriodReturn(
        return_pct=raw.get("return_pct"),
        basis_start_date=raw.get("basis_start_date"),
        basis_end_date=raw.get("basis_end_date"),
    )


def _candidate_to_model(raw: dict) -> MarketCandidate:
    returns_raw = raw.get("returns") or {}
    excess_raw = raw.get("excess_return") or None
    return MarketCandidate(
        rank=raw.get("rank"),
        ticker=raw.get("ticker"),
        name=raw.get("name"),
        tags=list(raw.get("tags") or []),
        selected_return_pct=raw.get("selected_return_pct"),
        selected_basis_start_date=raw.get("selected_basis_start_date"),
        selected_basis_end_date=raw.get("selected_basis_end_date"),
        returns=MarketReturns(
            daily=_period_to_model(returns_raw.get("daily")),
            one_month=_period_to_model(returns_raw.get("one_month")),
            three_month=_period_to_model(returns_raw.get("three_month")),
            # 2026-06-08 — 표시 전용 신규 기간.
            six_month=_period_to_model(returns_raw.get("six_month")),
            twelve_month=_period_to_model(returns_raw.get("twelve_month")),
            three_year=_period_to_model(returns_raw.get("three_year")),
        ),
        excess_return=(
            MarketCandidateExcessReturn(**excess_raw) if excess_raw else None
        ),
    )


def _build_nav_discount_payload(ticker: str) -> NavDiscountPayload:
    """store 에서 최신 NAV row 를 읽어 응답 payload 생성 (지시문 §10.2).

    store 에 row 없으면 status=unavailable + message.
    """
    row = fetch_latest_nav(etf_ticker=ticker, db_path=DEFAULT_DB_PATH)
    if row is None:
        return NavDiscountPayload(
            status="unavailable",
            message="NAV / discount source unavailable",
        )
    return NavDiscountPayload(
        status=row.status,
        asof=row.asof,
        nav=row.nav,
        market_price=row.market_price,
        discount_rate_pct=row.discount_rate_pct,
        flag=classify_discount_flag(row.discount_rate_pct),
        source=row.source,
        message=row.message,
    )


def _enrich_candidates_with_evidence(
    candidates: list[MarketCandidate],
) -> list[MarketCandidate]:
    """단기 흐름 + data_quality 채우기 (지시문 §10).

    KODEX200 시계열은 1회만 fetch. NAV 는 store read only.
    """
    tickers = [c.ticker for c in candidates if c.ticker]
    momentum_map = compute_short_term_momentum_batch(tickers, db_path=DEFAULT_DB_PATH)
    enriched: list[MarketCandidate] = []
    for c in candidates:
        if not c.ticker:
            enriched.append(c)
            continue
        m = momentum_map.get(c.ticker)
        momentum_payload = (
            ShortTermMomentumPayload(
                status=m.status,
                return_5d_pct=m.return_5d_pct,
                return_10d_pct=m.return_10d_pct,
                return_20d_pct=m.return_20d_pct,
                excess_vs_kodex200_5d_pctp=m.excess_vs_kodex200_5d_pctp,
                excess_vs_kodex200_10d_pctp=m.excess_vs_kodex200_10d_pctp,
                excess_vs_kodex200_20d_pctp=m.excess_vs_kodex200_20d_pctp,
                start_dates=(
                    ShortTermMomentumStartDates(
                        five_d=m.start_date_5d,
                        ten_d=m.start_date_10d,
                        twenty_d=m.start_date_20d,
                    )
                    if m.status == "ok"
                    else None
                ),
                end_date=m.end_date,
                message=m.message,
            )
            if m is not None
            else None
        )

        d = compute_daily_return_check(c.ticker, db_path=DEFAULT_DB_PATH)
        daily_payload = DailyReturnCheckPayload(
            status=d.status,
            daily_return_pct=d.daily_return_pct,
            flag=d.flag,
            threshold_pct=d.threshold_pct,
            message=d.message,
        )
        nav_payload = _build_nav_discount_payload(c.ticker)

        warnings: list[str] = []
        if daily_payload.flag:
            warnings.append(daily_payload.flag)
        if nav_payload.flag:
            warnings.append(nav_payload.flag)

        # data_quality 전체 status — daily 또는 nav 중 warning 이 있으면 warning.
        if daily_payload.status == "warning" or nav_payload.flag is not None:
            overall_status = "warning"
        elif (
            daily_payload.status == "unavailable"
            and nav_payload.status == "unavailable"
        ):
            overall_status = "unavailable"
        else:
            overall_status = "ok"

        dq_payload = DataQualityPayload(
            status=overall_status,
            daily_return_check=daily_payload,
            nav_discount=nav_payload,
            warnings=warnings,
        )
        enriched.append(
            c.model_copy(
                update={
                    "short_term_momentum": momentum_payload,
                    "data_quality": dq_payload,
                }
            )
        )
    return enriched


def _market_context_to_model(raw: Optional[dict]) -> Optional[MarketContextResponse]:
    if not raw:
        return None
    kodex_raw = raw.get("kodex200") or {"status": "unavailable"}
    kospi_raw = raw.get("kospi") or {"status": "unavailable"}
    return MarketContextResponse(
        status=raw.get("status") or "unavailable",
        asof=raw.get("asof"),
        primary_benchmark=raw.get("primary_benchmark") or "KODEX200",
        regime_label=raw.get("regime_label") or "판정불가",
        regime_code=raw.get("regime_code") or "unavailable",
        regime_score=raw.get("regime_score"),
        regime_reasons=list(raw.get("regime_reasons") or []),
        kodex200=MarketContextKodex200(**kodex_raw),
        kospi=MarketContextKospi(**kospi_raw),
        warnings=list(raw.get("warnings") or []),
    )


@router.get("/market/topn/latest", response_model=MarketTopNResponse)
def get_market_topn_latest(
    n: int = Query(default=DEFAULT_N, ge=1, le=200),
    basis: BasisLiteral = Query(default=DEFAULT_BASIS),
    order: OrderLiteral = Query(default=DEFAULT_ORDER),
    exclude_inverse: bool = Query(default=True),
    exclude_leveraged: bool = Query(default=True),
    exclude_synthetic: bool = Query(default=True),
    exclude_futures: bool = Query(default=True),
) -> MarketTopNResponse:
    """SQLite 에서 직접 일간 / 1개월 / 3개월 TOP N 산출.

    artifact 파일을 읽지 않는다. FDR 호출 / refresh 트리거 없음 (read-only).

    2026-05-18 후보 정제 1차 — 4개 exclude 옵션 (모두 default true).
    2026-05-18 통합 후보 테이블 1차 — basis 파라미터 (default one_month).
    2026-05-19 Grid 사용성 FIX — order 파라미터 (default desc).
      · desc 는 전체 후보 기준 TOP N, asc 는 전체 후보 기준 BOTTOM N.
      · 프론트 로컬 reverse 가 아니다.
    invalid basis / order 는 FastAPI Literal 가 422 응답으로 차단.
    필터링은 TOP N limit 이전에 적용된다 (지시문 §3.1).
    """
    payload = compute_topn(
        n=n,
        db_path=DEFAULT_DB_PATH,
        basis=basis,
        order=order,
        exclude_inverse=exclude_inverse,
        exclude_leveraged=exclude_leveraged,
        exclude_synthetic=exclude_synthetic,
        exclude_futures=exclude_futures,
    )
    latest_refresh = payload.get("latest_refresh")
    filters_raw = payload.get("filters") or {}
    return MarketTopNResponse(
        status=payload["status"],
        error=payload.get("error"),
        asof=payload.get("asof"),
        source=payload.get("source"),
        n=payload.get("n"),
        basis=payload.get("basis"),
        order=payload.get("order"),
        universe_count=payload.get("universe_count"),
        price_success_count=payload.get("price_success_count"),
        price_fail_count=payload.get("price_fail_count"),
        latest_refresh=(
            MarketLatestRefresh(**latest_refresh) if latest_refresh else None
        ),
        runtime_seconds=payload.get("runtime_seconds"),
        candidates=_enrich_candidates_with_evidence(
            [_candidate_to_model(c) for c in payload.get("candidates", [])]
        ),
        daily_topn=[_entry_to_model(r) for r in payload.get("daily_topn", [])],
        one_month_topn=[_entry_to_model(r) for r in payload.get("one_month_topn", [])],
        three_month_topn=[
            _entry_to_model(r) for r in payload.get("three_month_topn", [])
        ],
        period_exclusions=payload.get("period_exclusions", {}),
        filters=MarketTopNFilters(**filters_raw),
        filter_exclusions=payload.get("filter_exclusions", {}),
        candidate_filter_exclusions=payload.get("candidate_filter_exclusions", {}),
        topn_caveat=payload.get("topn_caveat"),
        market_context=_market_context_to_model(payload.get("market_context")),
    )


# ─── /market/refresh ──────────────────────────────────────────────────


class MarketRefreshResponse(BaseModel):
    status: str  # accepted / running / skipped_cooldown / failed_to_start
    refresh_id: Optional[str] = None
    message: str
    cooldown_remaining_seconds: int = 0


@router.post("/market/refresh", response_model=MarketRefreshResponse)
def post_market_refresh() -> MarketRefreshResponse:
    """FDR 수집을 background job 으로 시작. 동시 1건 + 6h cooldown 가드."""
    result = start_refresh_job(
        db_path=DEFAULT_DB_PATH,
        cooldown_hours=DEFAULT_COOLDOWN_HOURS,
    )
    return MarketRefreshResponse(
        status=result.status,
        refresh_id=result.refresh_id,
        message=result.message,
        cooldown_remaining_seconds=result.cooldown_remaining_seconds,
    )


# ─── /market/refresh/status ───────────────────────────────────────────


class MarketRefreshStatusResponse(BaseModel):
    status: str  # idle / running / completed / failed / skipped_cooldown
    refresh_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    asof: Optional[str] = None
    universe_count: Optional[int] = None
    price_attempted_count: Optional[int] = None
    price_success_count: Optional[int] = None
    price_fail_count: Optional[int] = None
    runtime_seconds: Optional[float] = None
    error_summary: Optional[str] = None
    cooldown_remaining_seconds: int = 0


@router.get("/market/refresh/status", response_model=MarketRefreshStatusResponse)
def get_market_refresh_status() -> MarketRefreshStatusResponse:
    snap = get_state_snapshot(cooldown_hours=DEFAULT_COOLDOWN_HOURS)
    return MarketRefreshStatusResponse(
        status=snap.status,
        refresh_id=snap.refresh_id,
        started_at=snap.started_at,
        finished_at=snap.finished_at,
        asof=snap.asof,
        universe_count=snap.universe_count,
        price_attempted_count=snap.price_attempted_count,
        price_success_count=snap.price_success_count,
        price_fail_count=snap.price_fail_count,
        runtime_seconds=snap.runtime_seconds,
        error_summary=snap.error_summary,
        cooldown_remaining_seconds=snap.cooldown_remaining_seconds,
    )
