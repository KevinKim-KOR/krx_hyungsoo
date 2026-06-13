"""Run 데이터 계약.

핵심 필드:
- run_id / asof / status / draft_payload — POC1 단계부터의 4개 기본 필드.
- message_text (POC2 Step 2D, 2026-05-XX) — 백엔드가 generate 시점에 빌드한
  Telegram / preview 본문 (단일 소스). 과거 run 은 None 허용 (하위호환).
- push_kind (POC2 3-PUSH Message Contract, 2026-06-12) — 하루 3종 PUSH 메시지
  구분 식별자 ("holdings_briefing" / "market_briefing" / "spike_or_falling_alert").
  과거 run 은 None 허용. delivery / OCI consumer 는 본 필드를 읽지 않으며
  Telegram 본문은 message_text 단일 소스 그대로 사용한다.

status 는 5개 고정 enum (PENDING_APPROVAL / REJECTED / DELIVERING / FAILED /
COMPLETED). UI 와 백엔드가 동일 값을 사용한다.
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


PushKind = Literal[
    "holdings_briefing",  # PUSH-2 — 기존 holdings draft 재정의 (2026-06-11).
    "market_briefing",  # PUSH-1 — 시장 흐름 브리핑.
    "spike_or_falling_alert",  # PUSH-3 — 급등락 관찰 신호.
]


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
    # POC2 3-PUSH Message Contract 정렬 (2026-06-11) — 하루 3종 PUSH 메시지
    # 구분용 식별자. 과거 run 은 None 허용 (저장 시점에 본 필드 없던 시기).
    # delivery / OCI consumer 는 본 필드를 읽지 않는다 — Telegram 본문은
    # message_text 단일 소스 그대로.
    push_kind: Optional[str] = None

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
        push_kind = data.get("push_kind")
        return cls(
            run_id=data["run_id"],
            asof=data["asof"],
            status=data["status"],
            draft_payload=data["draft_payload"],
            message_text=msg if isinstance(msg, str) else None,
            push_kind=push_kind if isinstance(push_kind, str) else None,
        )
