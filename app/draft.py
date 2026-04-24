"""초안(draft) 생성.

성공: status=PENDING_APPROVAL, draft_payload=dict
실패: status=FAILED, draft_payload=None

같은 날 재시도도 허용되지만 반드시 새 run_id 를 발급한다.
draft_payload 는 화면에서도 보고 외부 전달 body 로도 사용되는 단일 본문이다.

테스트 시나리오(draft 생성 실패, 외부 전달 실패) 는 payload 내부 플래그로
표현하지 않는다. 테스트는 이 모듈의 함수를 monkeypatch 하여 실패를 주입한다.
운영 payload 에는 테스트 제어 메타데이터가 절대 섞이지 않는다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app import sample_draft, store
from app.models import Run

logger = logging.getLogger(__name__)


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"run_{stamp}_{uuid4().hex[:8]}"


def generate_draft(input_data: dict[str, Any]) -> Run:
    """초안 생성 엔트리.

    input_data 는 app.sample_draft.build_sample_payload 의 계약을 만족해야 한다.
    계약 불만족(빈 dict 포함, 필수 키 누락) 시 SampleDraftInputError 가
    발생하며 이 함수는 status=FAILED, draft_payload=None 인 Run 을 저장하고
    반환한다. 운영 지시상 "GenerateDraft 실패 → FAILED 단일 규칙" 을 따른다.
    """
    run_id = _new_run_id()
    asof = datetime.now(timezone.utc).isoformat()

    try:
        payload = sample_draft.build_sample_payload(input_data)
        run = Run(
            run_id=run_id,
            asof=asof,
            status="PENDING_APPROVAL",
            draft_payload=payload,
        )
    except sample_draft.SampleDraftInputError as e:
        logger.error(f"draft 생성 실패 run_id={run_id}: {e}")
        run = Run(
            run_id=run_id,
            asof=asof,
            status="FAILED",
            draft_payload=None,
        )

    store.save(run)
    return run
