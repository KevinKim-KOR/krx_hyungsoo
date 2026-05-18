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

from app.market_data_store import DEFAULT_DB_PATH
from app.market_refresh_service import (
    DEFAULT_COOLDOWN_HOURS,
    get_state_snapshot,
    start_refresh_job,
)
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, compute_topn

BasisLiteral = Literal["daily", "one_month", "three_month"]

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


class MarketTopNResponse(BaseModel):
    status: str  # ok / missing / empty / invalid
    error: Optional[str] = None
    asof: Optional[str] = None
    source: Optional[str] = None
    n: Optional[int] = None
    # 2026-05-18 통합 후보 테이블 1차 — basis: daily / one_month / three_month.
    basis: Optional[str] = None
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
        ),
    )


@router.get("/market/topn/latest", response_model=MarketTopNResponse)
def get_market_topn_latest(
    n: int = Query(default=DEFAULT_N, ge=1, le=200),
    basis: BasisLiteral = Query(default=DEFAULT_BASIS),
    exclude_inverse: bool = Query(default=True),
    exclude_leveraged: bool = Query(default=True),
    exclude_synthetic: bool = Query(default=True),
    exclude_futures: bool = Query(default=True),
) -> MarketTopNResponse:
    """SQLite 에서 직접 일간 / 1개월 / 3개월 TOP N 산출.

    artifact 파일을 읽지 않는다. FDR 호출 / refresh 트리거 없음 (read-only).

    2026-05-18 후보 정제 1차 — 4개 exclude 옵션 (모두 default true).
    2026-05-18 통합 후보 테이블 1차 — basis 파라미터 (default one_month).
    invalid basis 는 FastAPI Literal 가 422 응답으로 차단.
    필터링은 TOP N limit 이전에 적용된다 (지시문 §3.1).
    """
    payload = compute_topn(
        n=n,
        db_path=DEFAULT_DB_PATH,
        basis=basis,
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
        universe_count=payload.get("universe_count"),
        price_success_count=payload.get("price_success_count"),
        price_fail_count=payload.get("price_fail_count"),
        latest_refresh=(
            MarketLatestRefresh(**latest_refresh) if latest_refresh else None
        ),
        runtime_seconds=payload.get("runtime_seconds"),
        candidates=[_candidate_to_model(c) for c in payload.get("candidates", [])],
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
