"""비-spike 중복 가드 (KS-10 분리 · 2026-09-07).

`run_three_push_runtime_oci.py` 가 650줄 임계를 넘어 **기계적으로 분리**한 블록.
판정 로직 변경 0건 — 실패 사유를 튜플로 돌려주고 러너가 `_finish(*fail)` 한다.
"""

from __future__ import annotations

from typing import Any, Optional


def resolve_duplicate_slot(
    push_kind: str, *, slot_id: Optional[str], runtime_kst: Optional[str]
) -> Optional[str]:
    """registry 중복키의 슬롯 접미.

    - `holdings_briefing` : `OPEN`/`MIDDAY`/`CLOSE`
    - `holdings_risk_alert` : **실행 시각 `HH:MM`**
      하루 7틱을 돌고 **악화 시 재발송**이 계약이라, 일 단위 키를 쓰면 그날 두
      번째 발송이 `duplicate_runtime` 으로 막혀 계약이 깨진다. 같은 틱의 중복
      실행만 막는다. (신규·악화 억제는 registry 가 아니라 `worst_state` 담당.)
    - 그 밖 : 접미 없음(일 단위)
    """
    if push_kind == "holdings_briefing":
        return slot_id
    if push_kind == "holdings_risk_alert":
        from app.runtime_evidence.holdings_risk_flow import slot_label_from_runtime

        return slot_label_from_runtime(runtime_kst) or None
    return None


def check_plain_duplicate(
    record: dict[str, Any],
    *,
    push_kind: str,
    param: Any,
    runtime_date_kst: str,
    runtime_kst: Optional[str],
    slot_id: Optional[str],
    resolve_registry_date_field: Any,
    registry_key: Any,
    is_already_sent: Any,
    logger: Any,
) -> tuple[Optional[tuple[str, str, Optional[str]]], str]:
    """Market / Holdings / Risk 중복 판정.

    반환 `(실패 튜플|None, registry_date_field)`. 두 번째 값은 러너 §8 이 발송
    성공 뒤 `mark_sent` 에 쓰는 **같은 키**다 — 여기서 조회한 키와 기록하는 키가
    갈라지면 중복 가드가 영영 성립하지 않으므로 계산을 한 곳에 둔다.
    """
    dup_slot = resolve_duplicate_slot(
        push_kind, slot_id=slot_id, runtime_kst=runtime_kst
    )
    date_field = resolve_registry_date_field(runtime_date_kst, slot_id=dup_slot)
    dup_key = registry_key(
        push_kind, param.param_id, runtime_date_kst, slot_id=dup_slot
    )
    record["duplicate_key"] = dup_key
    try:
        already = is_already_sent(push_kind, param.param_id, date_field)
    except Exception as e:  # noqa: BLE001
        logger.error("registry DB 접근 실패: %s", e)
        return ("failed", "registry_corrupted", str(e)[:400]), date_field
    if already:
        logger.info("중복 발송 차단: %s", dup_key)
        return ("skipped", "duplicate_runtime", None), date_field
    return None, date_field
