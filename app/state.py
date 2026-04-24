"""POC 1단계 상태 전이 규칙.

APPROVED 상태는 존재하지 않는다. Approve 이벤트가 발생하면
PENDING_APPROVAL -> DELIVERING 으로 직행한다.

terminal_state(REJECTED/FAILED/COMPLETED) 에서는 어떤 전이도 금지한다.
"""

from __future__ import annotations

from app.models import ALL_STATES, TERMINAL_STATES, Status

ALLOWED_TRANSITIONS: dict[Status, frozenset[Status]] = {
    "PENDING_APPROVAL": frozenset({"REJECTED", "DELIVERING", "FAILED"}),
    "DELIVERING": frozenset({"COMPLETED", "FAILED"}),
    "REJECTED": frozenset(),
    "FAILED": frozenset(),
    "COMPLETED": frozenset(),
}


class InvalidTransition(Exception):
    pass


def validate_transition(current: Status, target: Status) -> None:
    if current not in ALL_STATES:
        raise InvalidTransition(f"알 수 없는 current status: {current!r}")
    if target not in ALL_STATES:
        raise InvalidTransition(f"알 수 없는 target status: {target!r}")
    if current in TERMINAL_STATES:
        raise InvalidTransition(
            f"terminal state({current}) 에서는 어떤 전이도 불가 (target={target})"
        )
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"허용되지 않은 전이: {current} -> {target}")
