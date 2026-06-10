"""GET /ml/feature-sanity/latest — read-only ML feature sanity snapshot 조회 (2026-06-08).

지시문 §4.8 — Data Status 화면에 sanity 요약 표시. 본 API 는:
- state/ml/ml_feature_sanity_latest.json 만 read.
- feature 재계산 X, 외부 source 호출 X, ML 학습 X, 매수·매도 판단 X.

snapshot 이 없으면 status=empty (정상 초기 상태).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

SANITY_SNAPSHOT_PATH = Path("state/ml/ml_feature_sanity_latest.json")

router = APIRouter()


class MlFeatureSanityResponse(BaseModel):
    status: str  # ok / empty / error
    snapshot_path: str
    snapshot: Optional[dict[str, Any]] = None
    message: Optional[str] = None


@router.get("/ml/feature-sanity/latest", response_model=MlFeatureSanityResponse)
def get_ml_feature_sanity_latest() -> MlFeatureSanityResponse:
    """저장된 sanity snapshot 만 반환 (재계산 X / 외부 호출 X).

    status:
      - empty: snapshot 파일이 아직 생성되지 않은 정상 초기 상태.
      - error: snapshot 파일이 존재하지만 손상되어 읽을 수 없음 (fail-loud).
      - ok: snapshot 정상 반환.
    """
    if not SANITY_SNAPSHOT_PATH.exists():
        return MlFeatureSanityResponse(
            status="empty",
            snapshot_path=str(SANITY_SNAPSHOT_PATH),
            snapshot=None,
            message=(
                "sanity snapshot 미생성. CLI 'python scripts/check_ml_feature_sanity.py' "
                "를 1회 실행하면 본 화면에 검산 결과가 표시됩니다."
            ),
        )
    try:
        with SANITY_SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        # 파일 손상은 fail-loud — empty 와 구분되는 error 상태로 보고.
        return MlFeatureSanityResponse(
            status="error",
            snapshot_path=str(SANITY_SNAPSHOT_PATH),
            snapshot=None,
            message=f"snapshot 파일이 손상되어 읽을 수 없습니다 (json_decode_failed): {e}",
        )
    return MlFeatureSanityResponse(
        status="ok",
        snapshot_path=str(SANITY_SNAPSHOT_PATH),
        snapshot=payload,
    )
