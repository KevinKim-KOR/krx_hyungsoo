"""three_push_runtime_param.v1 — PARAM snapshot 계약.

목적:
  - PC에서 사용자가 승인한 PARAM snapshot을 정의/로드/검증한다.
  - OCI runtime runner가 이 snapshot을 고정 사용해 3-PUSH 메시지를 생성한다.

PARAM snapshot이 포함하는 것:
  - 발송 정책 (어떤 push_kind를 켤지)
  - runtime 정책 (unavailable 동작 방식)
  - evidence 정책 (runtime timestamp 사용 / 누락 추정 금지)
  - safety 정책 (매수/매도/조정장 확정 등 차단 flag)

PARAM snapshot이 포함하지 않는 것 (금지):
  - 완성된 Telegram message_text
  - ETF 순위 결과
  - 매수/매도/비중 조절 지시
  - 조정장 / 위험 threshold 확정
  - 확정되지 않은 factor/label/threshold 값
  - token / chat_id 등 secret

저장 위치:
  PC:  state/three_push/params/latest_runtime_param.json
  OCI: state/three_push/params/latest_runtime_param.json  (동일 경로)
  history (선택): state/three_push/params/history/<param_id>.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = "three_push_runtime_param.v1"

ALLOWED_PUSH_KINDS = (
    "market_briefing",
    "holdings_briefing",
    "spike_or_falling_alert",
)

ALLOWED_PARAM_SOURCES = (
    "manual_seed",
    "baseline_static",
    "future_ml_placeholder",
    "ml_export",
)

# 금지: PARAM이 들고 있으면 안 되는 키 (완성 메시지 / 매매 판단 등)
FORBIDDEN_PARAM_TOP_LEVEL_KEYS = frozenset(
    {
        "message_text",
        "telegram_text",
        "buy_candidates",
        "sell_candidates",
        "cash_allocation",
        "regime_confirmation",
        "risk_threshold_confirmation",
        "etf_ranking",
        "token",
        "chat_id",
        "bot_token",
        "telegram_token",
        "telegram_chat_id",
    }
)


@dataclass
class RuntimeParam:
    """three_push_runtime_param.v1 in-memory 표현."""

    param_id: str
    created_at: str
    approved_at: str
    approved_by: str
    param_source: str
    enabled_push_kinds: list[str]
    runtime_policy: dict[str, Any]
    evidence_policy: dict[str, Any]
    safety_policy: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "param_id": self.param_id,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "approved_by": self.approved_by,
            "param_source": self.param_source,
            "enabled_push_kinds": list(self.enabled_push_kinds),
            "runtime_policy": dict(self.runtime_policy),
            "evidence_policy": dict(self.evidence_policy),
            "safety_policy": dict(self.safety_policy),
        }
        # extra metadata (param_description / source_note 등) 는 허용
        for k, v in self.extra.items():
            if k in out:
                continue
            if k in FORBIDDEN_PARAM_TOP_LEVEL_KEYS:
                continue
            out[k] = v
        return out

    def is_push_kind_enabled(self, push_kind: str) -> bool:
        return push_kind in self.enabled_push_kinds


# ── 기본 정책 ─────────────────────────────────────────────────────────────────


def default_runtime_policy() -> dict[str, Any]:
    return {
        "data_unavailable_behavior": "mark_unavailable",
        "allow_partial_message": True,
    }


def default_evidence_policy() -> dict[str, Any]:
    return {
        "use_runtime_timestamp": True,
        "include_data_availability": True,
        "do_not_infer_missing_sources": True,
    }


def default_safety_policy() -> dict[str, Any]:
    return {
        "block_buy_sell_wording": True,
        "block_cash_allocation_instruction": True,
        "block_regime_confirmation": True,
        "block_risk_threshold_confirmation": True,
        "block_secret_exposure": True,
    }


# ── 생성 / 직렬화 ─────────────────────────────────────────────────────────────


def new_param_id(prefix: str = "param") -> str:
    """KST 일자 + UTC HHMMSS 기반 param_id 생성."""
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%S')}-{now.microsecond:06d}"


def build_manual_seed_param(
    *,
    approved_by: str = "user",
    enabled_push_kinds: Optional[list[str]] = None,
    param_description: Optional[str] = None,
    source_note: Optional[str] = None,
) -> RuntimeParam:
    """ML 없이 manual_seed 정책으로 default PARAM 생성."""
    now_iso = datetime.now(timezone.utc).isoformat()
    extra: dict[str, Any] = {}
    if param_description:
        extra["param_description"] = param_description
    if source_note:
        extra["source_note"] = source_note
    return RuntimeParam(
        param_id=new_param_id(),
        created_at=now_iso,
        approved_at=now_iso,
        approved_by=approved_by,
        param_source="manual_seed",
        enabled_push_kinds=list(enabled_push_kinds or list(ALLOWED_PUSH_KINDS)),
        runtime_policy=default_runtime_policy(),
        evidence_policy=default_evidence_policy(),
        safety_policy=default_safety_policy(),
        extra=extra,
    )


# ── 검증 ──────────────────────────────────────────────────────────────────────


def validate_param_dict(data: dict[str, Any]) -> list[str]:
    """PARAM dict 검증. 오류 목록을 반환 (빈 리스트면 valid).

    검증 항목:
      - schema_version 일치
      - 필수 필드 존재
      - param_source 허용값
      - enabled_push_kinds 허용값
      - 금지 key (완성 메시지 / 매매 판단 / secret) 부재
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return [f"PARAM은 dict 이어야 함: got {type(data).__name__}"]

    sv = data.get("schema_version")
    if sv != SCHEMA_VERSION:
        errors.append(f"schema_version 불일치: expected={SCHEMA_VERSION!r}, got={sv!r}")

    for field_name in (
        "param_id",
        "created_at",
        "approved_at",
        "approved_by",
        "param_source",
        "enabled_push_kinds",
        "runtime_policy",
        "evidence_policy",
        "safety_policy",
    ):
        if field_name not in data:
            errors.append(f"필수 필드 누락: {field_name}")

    ps = data.get("param_source")
    if ps is not None and ps not in ALLOWED_PARAM_SOURCES:
        errors.append(
            f"param_source 허용값 위반: got={ps!r} (허용={list(ALLOWED_PARAM_SOURCES)})"
        )

    epk = data.get("enabled_push_kinds")
    if isinstance(epk, list):
        for k in epk:
            if k not in ALLOWED_PUSH_KINDS:
                errors.append(
                    f"enabled_push_kinds 허용값 위반: got={k!r} (허용={list(ALLOWED_PUSH_KINDS)})"
                )
    elif epk is not None:
        errors.append(f"enabled_push_kinds 는 list 이어야 함: got {type(epk).__name__}")

    for key in FORBIDDEN_PARAM_TOP_LEVEL_KEYS:
        if key in data:
            errors.append(
                f"금지 키 포함: {key!r} (완성 메시지 / 매매 판단 / secret 은 PARAM에 저장 금지)"
            )

    return errors


def from_dict(data: dict[str, Any]) -> RuntimeParam:
    """dict → RuntimeParam. 검증 실패 시 RuntimeError."""
    errors = validate_param_dict(data)
    if errors:
        raise RuntimeError("PARAM 검증 실패: " + "; ".join(errors))
    known = {
        "schema_version",
        "param_id",
        "created_at",
        "approved_at",
        "approved_by",
        "param_source",
        "enabled_push_kinds",
        "runtime_policy",
        "evidence_policy",
        "safety_policy",
    }
    extra = {k: v for k, v in data.items() if k not in known}
    return RuntimeParam(
        param_id=data["param_id"],
        created_at=data["created_at"],
        approved_at=data["approved_at"],
        approved_by=data["approved_by"],
        param_source=data["param_source"],
        enabled_push_kinds=list(data["enabled_push_kinds"]),
        runtime_policy=dict(data["runtime_policy"]),
        evidence_policy=dict(data["evidence_policy"]),
        safety_policy=dict(data["safety_policy"]),
        extra=extra,
    )


# ── 파일 IO ──────────────────────────────────────────────────────────────────


def write_param_file(path: Path, param: RuntimeParam) -> None:
    """atomic write — *.tmp → rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(param.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(path)


def read_param_file(path: Path) -> RuntimeParam:
    if not path.exists():
        raise FileNotFoundError(f"PARAM 파일 없음: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"PARAM JSON 파싱 실패: {path} — {e}") from e
    return from_dict(data)
