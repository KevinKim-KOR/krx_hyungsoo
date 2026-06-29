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

from typing import Literal

from fastapi import APIRouter, Query

from app.api_market_topn_models import (  # noqa: F401 — MarketCandidate re-exported for tests
    MarketCandidate,
    MarketLatestRefresh,
    MarketRefreshResponse,
    MarketRefreshStatusResponse,
    MarketTopNFilters,
    MarketTopNResponse,
)
from app.api_market_topn_service import (
    candidate_to_model,
    enrich_candidates_with_evidence,
    entry_to_model,
    market_context_to_model,
    merge_relative_upside_score,
)
from app.market_data_store import DEFAULT_DB_PATH
from app.market_refresh_service import (
    DEFAULT_COOLDOWN_HOURS,
    get_state_snapshot,
    start_refresh_job,
)
from app.market_topn import DEFAULT_BASIS, DEFAULT_N, DEFAULT_ORDER, compute_topn

# 기존 테스트가 api_market_topn._merge_relative_upside_score /
# api_market_topn.MarketCandidate 를 직접 참조하므로 모듈 속성으로 노출.
_merge_relative_upside_score = merge_relative_upside_score

BasisLiteral = Literal["daily", "one_month", "three_month"]
OrderLiteral = Literal["desc", "asc"]

router = APIRouter()


# ─── /market/topn/latest ──────────────────────────────────────────────


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
    enriched_candidates = enrich_candidates_with_evidence(
        [candidate_to_model(c) for c in payload.get("candidates", [])],
        db_path=DEFAULT_DB_PATH,
    )
    # 2026-06-20 ML 축1 — 상대상승 참고점수 v0 머지 (지시문 §10). snapshot 부재
    # 시에도 후보 응답 자체는 유지 (지시문 §10 끝 — 실패·미생성 격리).
    merged_candidates, score_meta = merge_relative_upside_score(enriched_candidates)
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
        candidates=merged_candidates,
        daily_topn=[entry_to_model(r) for r in payload.get("daily_topn", [])],
        one_month_topn=[entry_to_model(r) for r in payload.get("one_month_topn", [])],
        three_month_topn=[
            entry_to_model(r) for r in payload.get("three_month_topn", [])
        ],
        period_exclusions=payload.get("period_exclusions", {}),
        filters=MarketTopNFilters(**filters_raw),
        filter_exclusions=payload.get("filter_exclusions", {}),
        candidate_filter_exclusions=payload.get("candidate_filter_exclusions", {}),
        topn_caveat=payload.get("topn_caveat"),
        market_context=market_context_to_model(payload.get("market_context")),
        relative_upside_score_status=score_meta.get("relative_upside_score_status"),
        relative_upside_score_asof_date=score_meta.get(
            "relative_upside_score_asof_date"
        ),
        relative_upside_score_generated_at=score_meta.get(
            "relative_upside_score_generated_at"
        ),
        relative_upside_score_user_notice=score_meta.get(
            "relative_upside_score_user_notice"
        ),
    )


# ─── /market/refresh ──────────────────────────────────────────────────


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
