"""POC3-02C-OPS-01 — `INTRADAY_ALERT_CONFIG` 번들 스키마·검증·해시.

설계자 §10-3 확정 계약을 코드로 고정한다.

## 두 해시를 분리한다 (§10-3(1))

| 해시 | 무엇을 감지하나 | 쓰임 |
|---|---|---|
| `evaluation_input_hash` | 데이터·기준일·규칙 변경 | **계산 이력에만** |
| `effective_config_hash` | 대표·대체·사전·정책이 **실제로** 달라졌는지 | **새 버전 생성 기준** |

가격 기준일만 바뀌면 `evaluation_input_hash` 는 달라지지만
`effective_config_hash` 는 같다 → **새 승인 버전을 만들지 않는다.** 이게 없으면
거래일마다 승인 요청이 쌓인다.

**보유 여부는 선정 입력이 아니다** — 장중 메시지에서 판정할 정보다.

## checksum 범위 (§10-3(5))

`source_hash_sha256` 은 **가변값을 제외한** 정규화 payload 로 계산한다.
제외: `created_at` · `approved_at` · `approved_by` · sync 상태 · hash 필드 자체.
승인 시각이 바뀌었다고 설정 내용의 checksum 이 바뀌면 안 된다.

## 최초 번들은 비활성 (§10-3(6))

```text
enabled = false · policy_status = NOT_CONFIGURED
```

`enabled=true` 면 급등·급락 임계 · cooldown · 중복 억제 · 발송 상한이 **모두**
있어야 검증을 통과한다.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

SCHEMA_VERSION = "intraday_alert_config.v1"
DEFAULT_ACTIVE_SCOPE = "intraday_alert"

POLICY_NOT_CONFIGURED = "NOT_CONFIGURED"
POLICY_CONFIGURED = "CONFIGURED"

# `enabled=true` 일 때 반드시 있어야 하는 정책 키 (§10-3(6)).
REQUIRED_POLICY_KEYS = (
    "surge_threshold_pct",
    "drop_threshold_pct",
    "cooldown_minutes",
    "dedup_window_minutes",
    "max_sends_per_run",
    "max_sends_per_day",
)

# source_hash 계산에서 빼는 가변 필드 (§10-3(5)).
VOLATILE_KEYS = frozenset(
    {
        "created_at",
        "approved_at",
        "approved_by",
        "rejected_at",
        "rejected_by",
        "reject_reason",
        "sync",
        "source_hash_sha256",
        "evaluation_input_hash",
        "effective_config_hash",
        "config_version_id",
    }
)


class ConfigSchemaError(ValueError):
    """번들이 계약을 어겼다. **fail-closed** — 추정으로 채우지 않는다."""


def _canonical(obj: Any) -> str:
    """정렬·공백 고정 JSON. 키 순서가 달라도 같은 해시가 나오게 한다."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strip_volatile(obj: Any) -> Any:
    """가변 필드를 재귀적으로 제거한다."""
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(x) for x in obj]
    return obj


def source_hash(payload: dict[str, Any]) -> str:
    """설정 내용만의 sha256. 승인·시각이 바뀌어도 값이 그대로다."""
    return hashlib.sha256(_canonical(_strip_volatile(payload)).encode()).hexdigest()


def effective_config_hash(payload: dict[str, Any]) -> str:
    """**실제 운영에 영향을 주는 부분**만의 해시 (§10-3(1)).

    universe 의 대표·대체 ticker 와 사업군 키, 분류 사전, 정책이 대상이다.
    `data_asof` · 시총 같은 산출 근거는 **뺀다** — 값이 흔들려도 결과가 같으면
    새 버전을 만들지 않는다.
    """
    uni = payload.get("sector_representative_universe") or {}
    sectors = []
    for s in uni.get("sectors") or []:
        rep = s.get("representative") or {}
        alt = s.get("alternate") or {}
        sectors.append(
            {
                "sector_key": s.get("sector_key"),
                "representative": rep.get("ticker"),
                "alternate": alt.get("ticker"),
            }
        )
    sectors.sort(key=lambda x: str(x.get("sector_key")))
    core = {
        "sectors": sectors,
        "token_dictionary": uni.get("token_dictionary"),
        "policy": payload.get("intraday_alert_policy"),
        "rule_version": payload.get("rule_version"),
    }
    return hashlib.sha256(_canonical(core).encode()).hexdigest()


def validate(payload: dict[str, Any]) -> None:
    """번들 계약 검증. 위반이면 `ConfigSchemaError`."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ConfigSchemaError(
            f"schema_version != {SCHEMA_VERSION}: {payload.get('schema_version')!r}"
        )
    if not str(payload.get("rule_version") or "").strip():
        raise ConfigSchemaError("rule_version 없음")

    uni = payload.get("sector_representative_universe")
    if not isinstance(uni, dict):
        raise ConfigSchemaError("sector_representative_universe 없음")
    if not str(uni.get("data_asof") or "").strip():
        raise ConfigSchemaError("data_asof 없음 — 기준일 없는 산출물은 쓰지 않는다")

    sectors = uni.get("sectors")
    if not isinstance(sectors, list) or not sectors:
        raise ConfigSchemaError("sectors 가 비었다")

    seen_sector: set[str] = set()
    seen_ticker: set[str] = set()
    for s in sectors:
        key = str(s.get("sector_key") or "").strip()
        if not key:
            raise ConfigSchemaError("sector_key 없음")
        if key in seen_sector:
            raise ConfigSchemaError(f"sector_key 중복: {key}")
        seen_sector.add(key)

        rep = s.get("representative")
        if not isinstance(rep, dict) or not str(rep.get("ticker") or "").strip():
            raise ConfigSchemaError(f"{key}: representative.ticker 없음")
        t = str(rep["ticker"]).strip()
        # 한 ticker 가 두 사업군의 대표가 되면 같은 종목을 두 번 조회한다.
        if t in seen_ticker:
            raise ConfigSchemaError(f"대표 ticker 중복: {t}")
        seen_ticker.add(t)

        alt = s.get("alternate")
        if alt is not None:
            if not isinstance(alt, dict) or not str(alt.get("ticker") or "").strip():
                raise ConfigSchemaError(f"{key}: alternate 형식 오류")
            if str(alt["ticker"]).strip() == t:
                raise ConfigSchemaError(f"{key}: 대표와 대체가 같다")

    policy = payload.get("intraday_alert_policy")
    if not isinstance(policy, dict):
        raise ConfigSchemaError("intraday_alert_policy 없음")

    enabled = policy.get("enabled")
    if not isinstance(enabled, bool):
        raise ConfigSchemaError("policy.enabled 는 bool 이어야 한다")

    status = policy.get("policy_status")
    if enabled:
        # §10-3(6) — 켜려면 전부 있어야 한다. 하나라도 없으면 거부.
        missing = [k for k in REQUIRED_POLICY_KEYS if policy.get(k) is None]
        if missing:
            raise ConfigSchemaError(f"enabled=true 인데 정책 값 누락: {missing}")
        if status != POLICY_CONFIGURED:
            raise ConfigSchemaError(
                f"enabled=true 면 policy_status={POLICY_CONFIGURED} 여야 한다"
            )
    else:
        if status != POLICY_NOT_CONFIGURED:
            raise ConfigSchemaError(
                f"enabled=false 면 policy_status={POLICY_NOT_CONFIGURED} 여야 한다"
            )


def build_payload(
    *,
    rule_version: str,
    sectors: list[dict[str, Any]],
    token_dictionary: dict[str, list[str]],
    data_asof: str,
    excluded: Optional[list[dict[str, Any]]] = None,
    policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """번들 payload 를 만든다. 정책 기본값은 **비활성**이다 (§10-3(6))."""
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": rule_version,
        "sector_representative_universe": {
            "data_asof": data_asof,
            "token_dictionary": token_dictionary,
            "sectors": sectors,
            # 분류 안 된 것을 조용히 버리지 않는다 (§10-2).
            "excluded": excluded or [],
        },
        "intraday_alert_policy": policy
        or {"enabled": False, "policy_status": POLICY_NOT_CONFIGURED},
    }
    validate(body)
    return body


__all__ = [
    "DEFAULT_ACTIVE_SCOPE",
    "POLICY_CONFIGURED",
    "POLICY_NOT_CONFIGURED",
    "REQUIRED_POLICY_KEYS",
    "SCHEMA_VERSION",
    "ConfigSchemaError",
    "build_payload",
    "effective_config_hash",
    "source_hash",
    "validate",
]
