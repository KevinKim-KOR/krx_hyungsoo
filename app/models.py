"""POC 1단계 데이터 계약.

필드는 run_id / asof / status / draft_payload 4개만 사용.
status 는 5개 고정 enum. UI 와 백엔드가 동일 값을 사용한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Optional

Status = Literal[
    "PENDING_APPROVAL",
    "REJECTED",
    "DELIVERING",
    "FAILED",
    "COMPLETED",
]

ALL_STATES: tuple[Status, ...] = (
    "PENDING_APPROVAL",
    "REJECTED",
    "DELIVERING",
    "FAILED",
    "COMPLETED",
)

TERMINAL_STATES: frozenset[Status] = frozenset({"REJECTED", "FAILED", "COMPLETED"})


@dataclass
class Run:
    run_id: str
    asof: str
    status: Status
    draft_payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Run":
        required = ("run_id", "asof", "status", "draft_payload")
        missing = [k for k in required if k not in data]
        if missing:
            raise KeyError(
                f"Run 역직렬화 실패 — 필수 키 누락: {missing}. "
                f"저장 포맷이 계약을 어김 (기대 키: {list(required)})."
            )
        return cls(
            run_id=data["run_id"],
            asof=data["asof"],
            status=data["status"],
            draft_payload=data["draft_payload"],
        )
