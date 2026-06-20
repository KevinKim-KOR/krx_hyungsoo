"""ML 축1 — 상대상승 참고점수 v0 실행 UI 연결 endpoint (2026-06-21).

POST /market/relative-upside/run — 사용자가 CLI 없이 UI 에서 점수 계산.

원칙 (지시문):
  - 동기 처리 (subprocess 실행 대기 후 응답 — 사용자 결정).
  - 기존 ML 실행 로직 / snapshot 생성 로직 재사용. 새 모델 / 새 feature / 새
    학습 흐름 0건.
  - 실패 시 기존 정상 score snapshot 은 삭제 / 초기화 / 빈값 덮어쓰기 X.
    main() 안의 save_score_snapshot 호출은 모든 단계 통과 후 atomic write 만
    수행하므로, 도중에 raise 되면 기존 파일은 그대로 유지된다.
  - 응답에 모델 내부 식별자 (CUDA device name / loss / epoch / artifact path /
    raw traceback / feature vector) 노출 0건. 사용자 친화 메시지만.

구현:
  - scripts.run_ml_relative_upside_score_v0.main() 을 직접 import 호출
    (사용자 결정 — subprocess 가 아니라 같은 프로세스 내 함수 호출).
  - main() 완료 후 state/ml/relative_upside_score_run_latest.json 을 읽어
    asof_date / scored_candidate_count / gpu_execution_used / generated_at 추출.
  - 실패 시 기존 run meta 는 그대로 두고 사용자용 message 만 응답.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.ml_relative_upside_score import RUN_META_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market/relative-upside", tags=["ml-relative-upside"])


class RelativeUpsideRunResponse(BaseModel):
    status: str  # ok | failed | unavailable
    asof_date: Optional[str]
    generated_at: Optional[str]
    scored_candidate_count: Optional[int]
    gpu_execution_used: Optional[bool]
    message: str


def _read_run_meta() -> dict:
    """state/ml/relative_upside_score_run_latest.json read. 부재/손상 시 빈 dict."""
    if not RUN_META_PATH.exists():
        return {}
    try:
        data = json.loads(RUN_META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("run meta read 실패: %s", type(e).__name__)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


@router.post("/run", response_model=RelativeUpsideRunResponse)
def run_relative_upside_score() -> RelativeUpsideRunResponse:
    """상대상승 참고점수 계산 실행 (지시문 — 동기 처리).

    내부 순서:
      1. scripts.run_ml_relative_upside_score_v0.main() 호출 (CUDA 우선 학습).
      2. RUN_META_PATH read 로 결과 메타 (asof / scored count / gpu used) 추출.
      3. 사용자 친화 message 합성 후 응답.

    실패 (main() 이 예외 raise) 시:
      - 기존 score snapshot / run meta 파일 변경 0건 (atomic write 가 main() 의
        마지막 단계에서만 호출됨).
      - 응답: status=failed, message="새 점수를 계산하지 못했습니다. 기존 점수는
        유지됩니다."
      - 사용자에게 traceback / shell command / device name 노출 X (지시문).

    응답 필드는 5개 (지시문 — 사용자용 최소 정보만).
    """
    try:
        from scripts.run_ml_relative_upside_score_v0 import main as run_ml_main

        rc = run_ml_main()
    except Exception as e:  # noqa: BLE001
        logger.error("ML 점수 계산 실행 실패: %s", type(e).__name__)
        return RelativeUpsideRunResponse(
            status="failed",
            asof_date=None,
            generated_at=None,
            scored_candidate_count=None,
            gpu_execution_used=None,
            message=("새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다."),
        )

    if rc != 0:
        logger.warning("ML 점수 계산 비정상 종료: rc=%s", rc)
        return RelativeUpsideRunResponse(
            status="failed",
            asof_date=None,
            generated_at=None,
            scored_candidate_count=None,
            gpu_execution_used=None,
            message=("새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다."),
        )

    meta = _read_run_meta()
    meta_status = meta.get("status")
    asof_date = meta.get("asof_date") or None
    generated_at = meta.get("generated_at") or None
    scored_count = meta.get("scored_candidate_count")
    model_block = meta.get("model") or {}
    gpu_used = model_block.get("gpu_execution_used")

    # main() rc=0 이지만 status != "ok" (unavailable 등) 인 경우.
    if meta_status != "ok":
        return RelativeUpsideRunResponse(
            status="unavailable",
            asof_date=asof_date,
            generated_at=generated_at,
            scored_candidate_count=(
                scored_count if isinstance(scored_count, int) else None
            ),
            gpu_execution_used=(bool(gpu_used) if isinstance(gpu_used, bool) else None),
            message=(
                "계산은 시도했지만 점수를 생성하지 못했습니다. "
                "기존 점수는 유지됩니다."
            ),
        )

    # 성공 — 사용자 친화 message.
    if gpu_used is True:
        message = "상대상승 참고점수 계산이 완료되었습니다."
    else:
        message = "계산은 완료됐지만 GPU 실행은 확인되지 않았습니다."

    return RelativeUpsideRunResponse(
        status="ok",
        asof_date=asof_date,
        generated_at=generated_at,
        scored_candidate_count=(
            scored_count if isinstance(scored_count, int) else None
        ),
        gpu_execution_used=(bool(gpu_used) if isinstance(gpu_used, bool) else None),
        message=message,
    )
