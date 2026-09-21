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

# OPS-03 — 조절 대상이 아닌 두 키.
#
# `dedup_window_minutes` 는 `cooldown_minutes` 의 **호환 별칭**이고,
# `max_sends_per_run` 은 조립이 회차당 본문을 하나만 만든다는 **구조에서 나온
# 고정값**이다. 둘 다 독립 정책처럼 표현하지 않는다(설계자 필수 보완).
FIXED_MAX_SENDS_PER_RUN = 1
DERIVED_POLICY_KEYS = ("dedup_window_minutes", "max_sends_per_run")

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
    # POC3-02C-OPS-02 — 사업군 대표 판정 (설계 §4-2). 코드 상수가 아니라
    # 승인 PARAM 이다. 이후 백테스트·ML 로 교체할 수 있어야 한다.
    "sector_entry_min_pct",
    "sector_chase_pct",
    "sector_avoid_drop_pct",
    "sector_rank_top_pct",
    "max_items_per_section",
    # 설계자 §14-4 — 상대순위 최소 커버리지. 조회에 성공한 사업군 안에서만
    # 상위 20% 를 매기면 27개 중 3개만 조회돼도 그중 하나가 후보가 된다.
    # 그건 실패 격리가 아니라 왜곡이다.
    "sector_min_coverage_pct",
)

# 설계 §4-2 초기 운영값. `enabled=true` 로 켤 때 채울 기준값이며, **여기서
# 자동으로 켜지지 않는다**(§10-3(6) 최초 번들 비활성 유지).
INITIAL_POLICY_VALUES = {
    "surge_threshold_pct": 5.0,
    "drop_threshold_pct": -5.0,
    "cooldown_minutes": 120,
    "dedup_window_minutes": 120,
    "max_sends_per_run": 1,
    "max_sends_per_day": 4,
    "sector_entry_min_pct": 1.5,
    "sector_chase_pct": 4.0,
    "sector_avoid_drop_pct": -1.5,
    "sector_rank_top_pct": 20.0,
    "max_items_per_section": 3,
    "sector_min_coverage_pct": 80.0,
}

# 설계자 §15-3 — `(키, 하한, 상한)`. 하한·상한 **포함**이다.
POLICY_RANGES = (
    ("sector_min_coverage_pct", 0.0, 100.0),
    ("sector_rank_top_pct", 0.0, 100.0),
    ("sector_entry_min_pct", -100.0, 100.0),
    ("sector_chase_pct", -100.0, 100.0),
    ("sector_avoid_drop_pct", -100.0, 100.0),
    ("surge_threshold_pct", 0.0, 100.0),
    ("drop_threshold_pct", -100.0, 0.0),
    ("cooldown_minutes", 0, 1440),
    ("dedup_window_minutes", 0, 1440),
    ("max_sends_per_run", 1, 10),
    ("max_sends_per_day", 1, 50),
    ("max_items_per_section", 1, 20),
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
        # 설계자 §15-3 — 키가 있는 것만으로는 부족하다. **비수치·범위 밖을
        # 거부**한다. 범위 밖 값이 통과하면 커버리지 Gate 가 무력화된다.
        for key, lo, hi in POLICY_RANGES:
            v = policy.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ConfigSchemaError(f"{key} 는 숫자여야 한다: {v!r}")
            if v != v or not (lo <= float(v) <= hi):
                raise ConfigSchemaError(f"{key} 범위 밖({lo}~{hi}): {v!r}")
        # OPS-03 설계자 필수 보완 — **선언만 된 설정값을 남기지 않는다.**
        #
        # 두 키는 이번 버전에서 독립 조절 대상이 아니다. 범위 검사만 두면
        # 실행 코드가 읽지 않는 장식용 값이 되어, 화면에 "조절 가능" 처럼
        # 보이면서 실제로는 아무 효과가 없다.
        if policy.get("dedup_window_minutes") != policy.get("cooldown_minutes"):
            raise ConfigSchemaError(
                "dedup_window_minutes 는 cooldown_minutes 의 호환 별칭이다 — "
                f"같아야 한다: {policy.get('dedup_window_minutes')!r} != "
                f"{policy.get('cooldown_minutes')!r}"
            )
        if policy.get("max_sends_per_run") != FIXED_MAX_SENDS_PER_RUN:
            raise ConfigSchemaError(
                "max_sends_per_run 은 회차당 본문 1개라는 구조에서 나온 고정값"
                f"({FIXED_MAX_SENDS_PER_RUN})이다: "
                f"{policy.get('max_sends_per_run')!r}"
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
    "DERIVED_POLICY_KEYS",
    "FIXED_MAX_SENDS_PER_RUN",
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
