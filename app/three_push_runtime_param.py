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

# 금지: PARAM이 들고 있으면 안 되는 키 (완성 메시지 / 매매 판단 / secret 등).
# top-level만 검사하면 `{"nested": {"message_text": ...}}` 같은 우회를 막지 못하므로
# validate_param_dict 가 재귀적으로 dict/list 전체를 순회한다.
# 이름은 호환을 위해 유지하지만 의미는 "PARAM 전체에서 금지" 다.
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

# 명시적 별칭 — validator 내부에서 사용. 두 이름 모두 동일 set 을 가리킨다.
FORBIDDEN_PARAM_KEYS_ANYWHERE = FORBIDDEN_PARAM_TOP_LEVEL_KEYS


def _collect_forbidden_keys_recursive(obj: Any, path: str = "") -> list[str]:
    """PARAM dict/list 전체를 순회해 금지 key가 어디든 등장하면 경로를 모은다.

    key 매칭은 대소문자 무관 (lower 비교) — 'Token' / 'BOT_TOKEN' 등 변형도 차단.
    """
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else k
            if isinstance(k, str) and k.lower() in FORBIDDEN_PARAM_KEYS_ANYWHERE:
                hits.append(child_path)
            hits.extend(_collect_forbidden_keys_recursive(v, path=child_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_path = f"{path}[{i}]"
            hits.extend(_collect_forbidden_keys_recursive(item, path=child_path))
    return hits


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

    # 금지 키 — top-level 뿐 아니라 중첩된 dict/list 안의 키도 모두 거부 (fail-closed).
    # 대소문자 무관 매칭.
    forbidden_hits = _collect_forbidden_keys_recursive(data)
    for path in forbidden_hits:
        errors.append(
            f"금지 키 포함: {path!r} (완성 메시지 / 매매 판단 / secret 은 PARAM에 저장 금지 — 중첩 포함)"
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


# ── DB IO — Cutover v1 (Q7 (b): 신규 함수, legacy JSON 함수는 seed source/reference) ──


def read_active_param_from_db(db_path: Optional[Path] = None) -> RuntimeParam:
    """runtime_state.sqlite 의 active pointer 를 통해 active PARAM 을 재구성.

    fail-closed:
      - DB 파일 부재 → RuntimeError.
      - active pointer 부재 → RuntimeError.
      - version row 부재 → RuntimeError.
      - 재구성 결과가 validate_param_dict 통과 못 하면 RuntimeError.
    JSON fallback 없음.
    """
    from app import runtime_state_store as store

    p = db_path or store.DEFAULT_DB_PATH
    if not Path(p).exists():
        raise RuntimeError(
            f"runtime_state DB 부재 — JSON fallback 없음 (fail closed): {p}"
        )
    ptr = store.get_active_pointer(Path(p))
    if not ptr:
        raise RuntimeError(
            "runtime_param_active pointer 부재 — JSON fallback 없음 (fail closed)"
        )
    version = store.read_param_version(Path(p), ptr["active_param_version_id"])
    if not version:
        raise RuntimeError(
            f"runtime_param_version 부재: {ptr['active_param_version_id']}"
        )
    data = store.reconstruct_param_dict(version)
    return from_dict(data)


def create_param_version_in_db(
    param: RuntimeParam,
    *,
    db_path: Optional[Path] = None,
) -> tuple[str, str, bool]:
    """PARAM 을 runtime_state DB 에 등록. 이미 동일 hash version 이 있으면 재사용.

    반환: (param_version_id, source_hash_sha256, created_new).
    """
    from app import runtime_state_store as store

    p = Path(db_path or store.DEFAULT_DB_PATH)
    data = param.to_dict()
    errors = validate_param_dict(data)
    if errors:
        raise RuntimeError("PARAM 검증 실패: " + "; ".join(errors))
    source_hash = store.canonical_json_sha256(data)
    existing = store.find_param_version_by_hash(p, source_hash)
    if existing:
        return existing["param_version_id"], source_hash, False
    values = store.flatten_param_dict(data)
    store.insert_param_version(
        p,
        param_version_id=param.param_id,
        schema_version=param.schema_version,
        created_at=param.created_at,
        approved_at=param.approved_at,
        approved_by=param.approved_by,
        param_source=param.param_source,
        source_hash_sha256=source_hash,
        param_description=param.extra.get("param_description"),
        source_note=param.extra.get("source_note"),
        values=values,
    )
    return param.param_id, source_hash, True


def activate_param_version(
    param_version_id: str,
    *,
    activated_at: str,
    activated_by: str,
    db_path: Optional[Path] = None,
) -> None:
    """runtime_param_active pointer 를 지정 version 으로 갱신 (upsert)."""
    from app import runtime_state_store as store

    p = Path(db_path or store.DEFAULT_DB_PATH)
    store.set_active_pointer(
        p,
        active_param_version_id=param_version_id,
        activated_at=activated_at,
        activated_by=activated_by,
    )
