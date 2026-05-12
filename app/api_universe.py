"""POC2 Step 6 — universe momentum FastAPI 라우터.

분리 목적: app/api.py KS-10 근접 (>=600) 해소. FastAPI APIRouter 패턴.

설계자 결정 (Step 6 §6 / §7 / §12 + Step6 Fix 라운드 2026-05-11):
- POST /universe/momentum/refresh : 수동 sync refresh (pykrx 1개월 수익률).
  GenerateDraft / Approve / Telegram 자동 호출 금지. seed >20 hard fail.
  candidate 단위 실패는 partial / failed 결과로 저장 (HTTP 200).
- **신규 endpoint 추가 금지** (Fix 라운드 결정) — GET /universe/momentum/latest 제거.
  UI 의 마지막 갱신 결과 표시는 POST refresh 응답을 frontend state 로 보관해서 처리하며,
  페이지 reload 시 안내 문구로 비워진다 (다음 refresh 클릭 전까지).
- POST 응답에 top_candidate / summary_reason_text 를 함께 실어 UI 가 페이지 reload
  전까지 상태 패널을 그릴 수 있게 한다 (응답 필드 확장은 신규 endpoint 가 아니다).

draft_payload 노출 정책:
- 본 라우터 응답에는 candidates 배열 전체 / 점수 전체를 싣지 않는다 (Step6 §13 / AC-28).
- summary 와 top_candidate (rank=1 1건) 만 노출. UI 도 이 한 건만 표시.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.momentum import (
    build_universe_momentum_result_scored,
    save_latest_artifact as save_universe_latest_artifact,
)
from app.universe_refresh import (
    FALLING_THRESHOLD_PCT,
    UniverseRefreshError,
    build_failure_summary_reason,
    run_universe_refresh,
    validate_seed_for_refresh,
)
from app.universe_seed import (
    UniverseSeedError,
    ensure_seed_file_exists,
    load_universe_seed,
)

router = APIRouter()


class UniverseMomentumRefreshSummary(BaseModel):
    total_candidates: int
    scored_candidates: int
    excluded_candidates: int
    source_freshness: str
    refresh_status: str
    # Step6 Fix: UI 가 GET /latest 없이 POST 응답만으로 상태 패널을 그리도록 필드 확장.
    summary_reason_text: Optional[str] = None
    top_candidate: Optional[dict[str, Any]] = None
    # Step7A: seed source — "starter_seed" 면 UI 가 "기본 후보군 사용" 안내 표시.
    # universe_mode._build_summary 가 seed.source 를 그대로 summary 에 실어주므로
    # 본 필드는 노출만 한다 (데이터 계약 신설 아님).
    source: Optional[str] = None
    # Step7C: 급락 ETF 주의 신호 (PUSH 3) — universe_mode 가 summary 에 실어주는
    # falling_candidate / falling_threshold_pct 를 노출. 후보 없으면 falling_candidate=None.
    falling_candidate: Optional[dict[str, Any]] = None
    falling_threshold_pct: Optional[float] = None


class UniverseMomentumRefreshResultBrief(BaseModel):
    mode: str
    asof: str
    summary: UniverseMomentumRefreshSummary


class UniverseMomentumRefreshResponse(BaseModel):
    status: str
    artifact_path: str
    momentum_result: UniverseMomentumRefreshResultBrief


@router.post(
    "/universe/momentum/refresh", response_model=UniverseMomentumRefreshResponse
)
def post_universe_momentum_refresh() -> UniverseMomentumRefreshResponse:
    """수동 universe seed → pykrx 1개월 수익률 scoring → latest artifact 저장.

    Step 7A — seed 파일이 없을 때만 starter seed 생성 후 기존 흐름 진행.
    기존 사용자 seed 가 있으면 절대 덮어쓰지 않는다.

    실패 처리:
    - seed 파일 부재 / asof 누락·형식 오류·미래 날짜 / items 비정상: 422 (universe seed 검증 실패)
    - items 20개 초과: 422 (UniverseRefreshError) — 조용히 자르지 않는다.
    - candidate 단위 pykrx 실패는 partial / failed 결과로 저장 (HTTP 200 OK).
    """
    # Step 7A: seed 파일 부재 시 starter seed 생성 (기존 사용자 seed 보호).
    ensure_seed_file_exists()

    try:
        seed = load_universe_seed()
    except UniverseSeedError as e:
        raise HTTPException(status_code=422, detail=f"universe seed 검증 실패: {e}")
    try:
        validate_seed_for_refresh(seed)
    except UniverseRefreshError as e:
        raise HTTPException(status_code=422, detail=str(e))

    scores, refresh_status = run_universe_refresh(seed)
    failure_reason = (
        build_failure_summary_reason(seed, scores)
        if refresh_status == "failed"
        else None
    )
    momentum_result = build_universe_momentum_result_scored(
        seed=seed,
        scores=scores,
        refresh_status=refresh_status,
        failure_summary_reason=failure_reason,
        falling_threshold_pct=FALLING_THRESHOLD_PCT,
    )
    artifact_path = save_universe_latest_artifact(momentum_result)
    summary = momentum_result["summary"]
    return UniverseMomentumRefreshResponse(
        status=refresh_status,
        artifact_path=str(artifact_path),
        momentum_result=UniverseMomentumRefreshResultBrief(
            mode=momentum_result["mode"],
            asof=momentum_result["asof"],
            summary=UniverseMomentumRefreshSummary(
                total_candidates=summary["total_candidates"],
                scored_candidates=summary["scored_candidates"],
                excluded_candidates=summary["excluded_candidates"],
                source_freshness=summary["source_freshness"],
                refresh_status=summary["refresh_status"],
                summary_reason_text=summary.get("summary_reason_text"),
                top_candidate=summary.get("top_candidate"),
                source=summary.get("source"),
                falling_candidate=summary.get("falling_candidate"),
                falling_threshold_pct=summary.get("falling_threshold_pct"),
            ),
        ),
    )
