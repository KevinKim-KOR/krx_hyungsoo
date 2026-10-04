"""PARAM 로드 · 비밀값 · slot_id · push_kind 활성 사전 검사 (POC5-01A 러너 기계 분리 · 2026-10-03).

`run_three_push_runtime_oci.py` §1 · §1-b · §2 를 **문장 순서 그대로** 옮겼다. 판정 ·
로그 · record 기록 변경 0건. `return _finish(...)` 대신 실패 튜플을 돌려주고 러너가
`_finish(*fail)` 한다(기존 helper 와 같은 규약 · 튜플 모양도 원래 인자 그대로).

테스트가 러너 모듈에서 바꿔 끼우는 `read_active_param_dict` · `param_from_dict` 는 러너가
**호출 때** 인자로 넘긴다(여기서 import 하면 바꿔 끼우기가 먹지 않는다 · PLAN 1-8).
logger 는 러너 것을 받는다.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.three_push_runner_common import assert_no_sensitive_keys
from app.three_push_runtime.registry_key import HOLDINGS_SLOT_IDS


def load_param_and_check_slot(
    record: dict[str, Any],
    *,
    push_kind: str,
    slot_id: Optional[str],
    logger: Any,
    read_active_param_dict: Callable[[], dict[str, Any]],
    param_from_dict: Callable[[dict[str, Any]], Any],
) -> tuple[Any, Optional[tuple]]:
    """반환 `(param | None, 실패 튜플 | None)`. 실패면 러너가 그대로 `_finish(*fail)`."""
    # ── 1. active PARAM 로드 (runtime_state.sqlite 기준) ─────────────────────
    try:
        param_dict = read_active_param_dict()
        param = param_from_dict(param_dict)
    except Exception as e:
        logger.error("active PARAM 로드/검증 실패: %s", e)
        return None, ("failed", "param_load_error", str(e)[:400])

    record["param_id"] = param.param_id
    record["param_source"] = param.param_source

    # PARAM 자체에 secret 포함 여부 점검 (정책상 금지지만 방어적)
    try:
        assert_no_sensitive_keys(param.to_dict(), path="param")
    except RuntimeError as e:
        logger.error("PARAM secret 노출: %s", e)
        return None, ("failed", "param_secret_exposed", str(e)[:400])

    # ── 1-b. slot_id 계약 검증 (holdings_briefing 만) ────────────────────────
    # Low-Frequency Telegram Push Operation v1: holdings_briefing 은 OPEN/MIDDAY/CLOSE
    # 세 슬롯으로 나뉜다. slot_id 는 registry key 문자열에 삽입되어 슬롯별 중복 차단.
    if push_kind == "holdings_briefing":
        if slot_id is None:
            logger.error("holdings_briefing 은 --slot-id 필수 (OPEN/MIDDAY/CLOSE)")
            return None, ("failed", "slot_id_required")
        if slot_id not in HOLDINGS_SLOT_IDS:
            logger.error("잘못된 slot_id=%s (허용값 %s)", slot_id, HOLDINGS_SLOT_IDS)
            return None, ("failed", "slot_id_invalid")
        record["slot_id"] = slot_id
    else:
        if slot_id is not None:
            logger.info(
                "slot_id=%s 는 push_kind=%s 에서 무시됨 (holdings_briefing 만 유효)",
                slot_id,
                push_kind,
            )

    # ── 2. PARAM에서 push_kind 활성화 확인 ────────────────────────────────────
    if not param.is_push_kind_enabled(push_kind):
        logger.info(
            "PARAM enabled_push_kinds 미포함: push_kind=%s param_id=%s",
            push_kind,
            param.param_id,
        )
        return None, ("skipped", "push_kind_not_in_param")
    return param, None
