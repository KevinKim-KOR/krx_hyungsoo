"""POC2 Step 6 — universe momentum FastAPI 라우터 분리.

분리 목적: app/api.py KS-10 근접 (>=600) 해소. FastAPI APIRouter 패턴.

설계자 결정 (Step 6 §6 / §7 / §10 / §12):
- POST /universe/momentum/refresh : 수동 sync refresh (pykrx 1개월 수익률).
- GET  /universe/momentum/latest   : UI 상태 패널용 latest artifact 조회.
- 두 endpoint 모두 본 모듈에 모으고, app/api.py 는 본 라우터를 include 한다.
- 응답 스키마 / 경로 / 동작 모두 분리 전과 동일 — 위치만 이동.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# universe_mode 모듈 자체를 import — LATEST_ARTIFACT_FILE 은 호출 시점에 lookup 하여
# 테스트에서 monkeypatch.setattr(universe_mode, "LATEST_ARTIFACT_FILE", ...) 가
# 본 endpoint 에도 반영되도록 한다 (정적 binding 회피).
from app.momentum import universe_mode
from app.momentum import (
    build_universe_momentum_result_scored,
    save_latest_artifact as save_universe_latest_artifact,
)
from app.universe_refresh import (
    UniverseRefreshError,
    build_failure_summary_reason,
    run_universe_refresh,
    validate_seed_for_refresh,
)
from app.universe_seed import UniverseSeedError, load_universe_seed

router = APIRouter()


class UniverseMomentumRefreshSummary(BaseModel):
    total_candidates: int
    scored_candidates: int
    excluded_candidates: int
    source_freshness: str
    refresh_status: str


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

    실패 처리:
    - seed 파일 부재 / asof 누락·형식 오류·미래 날짜 / items 비정상: 422 (universe seed 검증 실패)
    - items 20개 초과: 422 (UniverseRefreshError) — 조용히 자르지 않는다.
    - candidate 단위 pykrx 실패는 partial / failed 결과로 저장 (HTTP 200 OK).
    """
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
            ),
        ),
    )


class UniverseMomentumLatestResponse(BaseModel):
    """GET /universe/momentum/latest — UI 상태 패널용 latest artifact 조회.

    artifact 가 없으면 status="absent" 반환 (404 가 아닌 200). 프론트가 안내 문구만 표시.
    """

    status: str  # 'present' | 'absent'
    artifact_path: str
    momentum_result: Optional[dict[str, Any]] = None


@router.get(
    "/universe/momentum/latest",
    response_model=UniverseMomentumLatestResponse,
)
def get_universe_momentum_latest() -> UniverseMomentumLatestResponse:
    """latest artifact 를 그대로 반환. UI status panel 이 직접 렌더링.

    artifact 가 없거나 JSON 파싱 실패면 status="absent" 로 응답 (refresh 안 된 신규 환경).
    """
    # universe_mode 모듈에서 호출 시점에 lookup — 테스트가 monkeypatch 한 경로 반영.
    path = universe_mode.LATEST_ARTIFACT_FILE
    if not path.exists():
        return UniverseMomentumLatestResponse(
            status="absent",
            artifact_path=str(path),
            momentum_result=None,
        )
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return UniverseMomentumLatestResponse(
            status="absent",
            artifact_path=str(path),
            momentum_result=None,
        )
    return UniverseMomentumLatestResponse(
        status="present",
        artifact_path=str(path),
        momentum_result=data,
    )
