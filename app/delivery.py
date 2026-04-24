"""외부 전달 어댑터.

POC 1단계에서는 stub 구현. 실제 Telegram/OCI 연동은 BACKLOG (Q2 OPEN).
향후 실 전달로 교체하기 쉽도록 이 모듈에만 접점을 둔다.

성공/실패가 반드시 run.status 에 반영되도록 호출측(api.py)과 계약한다.
"이벤트는 발송했지만 status 는 안 바뀜" 은 금지(KS-1 정책).
"""

from __future__ import annotations

import logging

from app.models import Run

logger = logging.getLogger(__name__)


class DeliveryError(Exception):
    pass


def deliver(run: Run) -> None:
    """DELIVERING 상태의 run 을 외부로 전달한다.

    성공 시 예외 없이 반환. 실패 시 DeliveryError 를 raise 한다.
    """
    if run.status != "DELIVERING":
        raise DeliveryError(f"DELIVERING 상태만 전달 가능: current={run.status}")
    if not run.draft_payload:
        raise DeliveryError(f"payload 없음: run_id={run.run_id}")
    if "title" not in run.draft_payload:
        # 명시적 키 접근. title 누락은 계약 위반이므로 fallback 없이 실패 처리.
        raise DeliveryError(f"payload 에 필수 키 'title' 누락: run_id={run.run_id}")

    # 테스트에서 실패를 재현해야 할 때는 이 함수를 monkeypatch 한다.
    # 운영 payload 에는 테스트 제어 플래그가 섞이지 않는다.
    logger.info(
        f"[delivery stub] run_id={run.run_id} 전달 완료 "
        f"(title={run.draft_payload['title']!r})"
    )
