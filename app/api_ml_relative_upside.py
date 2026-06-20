"""ML 축1 — 상대상승 참고점수 v0 실행 UI 연결 endpoint (2026-06-21).

POST /market/relative-upside/run — 사용자가 CLI 없이 UI 에서 점수 계산.

원칙 (지시문):
  - 동기 처리 — 같은 프로세스 내 함수 호출 대기 후 응답 (사용자 결정 2026-06-21).
    subprocess 가 아니라 `scripts.run_ml_relative_upside_score_v0.main()` 을
    직접 import 해서 호출한다.
  - 기존 ML 실행 로직 / snapshot 생성 로직 재사용. 새 모델 / 새 feature / 새
    학습 흐름 0건.
  - 실패 시 기존 정상 score snapshot 은 삭제 / 초기화 / 빈값 덮어쓰기 X.
    2층 보호: (a) main() 예외 raise 시 atomic write 가 호출되지 않아 파일 변경
    0건. (b) FIX r1 — main() 의 model is None / inference_rows 빈 분기에서
    save_score_snapshot() 호출 자체를 제거 → SCORE_SNAPSHOT_PATH 그대로 유지.
    이 경우 RUN_META_PATH 는 이력 추적용으로 snapshot_path="" 로 갱신된다.
  - 응답에 모델 내부 식별자 (CUDA device name / loss / epoch / artifact path /
    raw traceback / feature vector) 노출 0건. 사용자 친화 메시지만.

구현:
  - scripts.run_ml_relative_upside_score_v0.main() 을 직접 import 호출
    (사용자 결정 — subprocess 가 아니라 같은 프로세스 내 함수 호출).
  - main() 완료 후 state/ml/relative_upside_score_run_latest.json 을 읽어
    asof_date / scored_candidate_count / gpu_execution_used / generated_at 추출.
  - 실패 분기에서 score snapshot 은 유지된다. run meta 는 이력 추적을 위해
    main() 의 unavailable/failed 분기에서도 갱신될 수 있다 (snapshot_path="").
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


# run meta 파일 상태 — 부재 / 손상 / 정상 3분리.
META_STATE_MISSING = "missing"
META_STATE_CORRUPTED = "corrupted"
META_STATE_OK = "ok"


def _read_run_meta() -> tuple[str, dict]:
    """state/ml/relative_upside_score_run_latest.json 의 (상태, payload).

    상태:
      - META_STATE_MISSING — 파일 부재 (한 번도 실행 안 됨)
      - META_STATE_CORRUPTED — JSON parse 실패 또는 dict 가 아님 (운영 상태 손상)
      - META_STATE_OK — 정상 read

    raw error / device name / artifact path 는 응답에 노출하지 않고 호출자가
    사용자 친화 dict 로 변환한다 (지시문 — 일반 UI 노출 금지).
    """
    if not RUN_META_PATH.exists():
        return META_STATE_MISSING, {}
    try:
        data = json.loads(RUN_META_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("run meta read 실패: %s", type(e).__name__)
        return META_STATE_CORRUPTED, {}
    if not isinstance(data, dict):
        logger.warning(
            "run meta 형식 오류: 최상위가 dict 아님 (%s)", type(data).__name__
        )
        return META_STATE_CORRUPTED, {}
    return META_STATE_OK, data


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

    응답 필드는 6개 (지시문 — 사용자용 최소 정보만).
    status / asof_date / generated_at / scored_candidate_count / gpu_execution_used / message.
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

    meta_state, meta = _read_run_meta()
    # 손상은 응답에 별도로 노출하지 않고 unavailable 로 묶되 로그에는 남긴다
    # (B-1 — 손상과 데이터 부족 구분, 사용자에게는 동일 사용자 친화 메시지).
    if meta_state == META_STATE_CORRUPTED:
        return RelativeUpsideRunResponse(
            status="unavailable",
            asof_date=None,
            generated_at=None,
            scored_candidate_count=None,
            gpu_execution_used=None,
            message=("운영 상태 파일을 읽지 못했습니다. 기존 점수는 유지됩니다."),
        )
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
