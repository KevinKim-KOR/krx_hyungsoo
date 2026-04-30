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
    # POC2 Step 2D: top-level optional metadata.
    # 신규 run 은 generate 시점에 백엔드가 빌드해 저장하고, OCI handoff/Telegram 도
    # 동일한 이 값을 사용한다 (preview ↔ 실제 발송문 단일 소스).
    # 과거 state/runs/*.json 에 키가 없을 수 있으므로 from_dict 가 누락을 None 으로 허용.
    message_text: Optional[str] = None

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
        # message_text 는 옵션. 과거 run 파일에 없으면 None.
        msg = data.get("message_text")
        return cls(
            run_id=data["run_id"],
            asof=data["asof"],
            status=data["status"],
            draft_payload=data["draft_payload"],
            message_text=msg if isinstance(msg, str) else None,
        )
