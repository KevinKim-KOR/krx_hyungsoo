"""Registry key/date-field 계산 helper (Low-Frequency Telegram Push Operation v1 A+).

DB PRIMARY KEY (push_kind, param_id, runtime_date_kst) 미변경 · runtime_date_kst
문자열 확장으로 slot_id/signal_fingerprint 별 UNIQUE 달성.
"""

from __future__ import annotations

from typing import Optional

HOLDINGS_SLOT_IDS = ("OPEN", "MIDDAY", "CLOSE")


def registry_key(
    push_kind: str,
    param_id: str,
    runtime_date_kst: str,
    slot_id: Optional[str] = None,
    signal_fingerprint: Optional[str] = None,
) -> str:
    """중복 차단 key 문자열.

    - Market: 3튜플 그대로.
    - Holdings: runtime_date_kst 에 `#{slot_id}` 접미.
    - Spike: runtime_date_kst 에 `#{signal_fingerprint}` 접미
             (fingerprint = ticker#trigger#direction; 날짜는 여기서 1회만 접미).
    """
    date_field = resolve_registry_date_field(
        runtime_date_kst, slot_id=slot_id, signal_fingerprint=signal_fingerprint
    )
    return f"{push_kind}::{param_id}::{date_field}"


def resolve_registry_date_field(
    runtime_date_kst: str,
    slot_id: Optional[str] = None,
    signal_fingerprint: Optional[str] = None,
) -> str:
    """registry `runtime_date_kst` 컬럼에 저장할 문자열."""
    if slot_id is not None:
        return f"{runtime_date_kst}#{slot_id}"
    if signal_fingerprint is not None:
        return f"{runtime_date_kst}#{signal_fingerprint}"
    return runtime_date_kst
