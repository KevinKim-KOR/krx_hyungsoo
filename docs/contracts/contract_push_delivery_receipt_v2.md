# Contract: Push Delivery Receipt V2

**Version**: 2.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

Push Delivery Receipt의 V2 스키마입니다.

> 🔒 **V1 Superset**: V2는 V1의 완전 상위호환입니다. 기존 V1 필드를 모두 포함합니다.

---

## 2. V1과의 관계

| 항목 | 설명 |
|------|------|
| 호환성 | V2 ⊃ V1 (완전 상위호환) |
| V1 상태 | DEPRECATED (contract_push_delivery_v1.md 참조) |
| 마이그레이션 | V1 필드 그대로 유지 + V2 필드 추가 |

---

## 3. 스키마 정의

### PUSH_DELIVERY_RECEIPT_V2

```json
{
  "schema": "PUSH_DELIVERY_RECEIPT_V2",
  "delivery_run_id": "uuid",
  "asof": "2026-01-04T17:00:00",
  
  "gate_mode": "MOCK_ONLY",
  "emergency_stop_enabled": false,
  "secrets_available": false,
  
  "summary": {
    "total_messages": 5,
    "console": 5,
    "external": 0,
    "skipped": 0
  },
  
  "decisions": [
    {
      "message_id": "msg-uuid",
      "channel_decision": "CONSOLE",
      "channel_target": "console",
      "reason_code": "NO_SECRETS_FOR_ANY_CHANNEL"
    }
  ],
  
  "routing": {
    "mode": "CONSOLE_ONLY",
    "external_candidate": false,
    "candidate_channels": [],
    "blocked_reason": "NO_SECRETS_FOR_ANY_CHANNEL"
  },
  
  "secrets_status_ref": "api:/api/secrets/status",
  "channel_matrix_version": "PUSH_CHANNELS_V1",
  "gate_mode_observed": "MOCK_ONLY",
  "delivery_actual": "CONSOLE"
}
```

---

## 4. V2 신규 필드

| 필드 | 타입 | 설명 |
|------|------|------|
| `routing` | object | 라우팅 결정 상세 |
| `routing.mode` | string | 항상 `CONSOLE_ONLY` |
| `routing.external_candidate` | boolean | 외부 발송 후보 여부 |
| `routing.candidate_channels` | array | 후보 채널 목록 |
| `routing.blocked_reason` | string? | 차단 사유 (null 가능) |
| `secrets_status_ref` | string | 시크릿 상태 API 참조 |
| `channel_matrix_version` | string | 채널 매트릭스 버전 |
| `gate_mode_observed` | string? | 관측된 Gate 모드 (참고용) |
| `delivery_actual` | string | **항상 CONSOLE** |

---

## 5. Candidate 판정 규칙

> ⚠️ **Gate 미반영**: 후보 판정은 Gate mode와 무관하게 "기술적 가능성"만 평가

### external_candidate=true 조건 (채널별)

1. `push_type` ∈ `allowed_push_types`
2. `required_secrets`가 전부 `present=true`

### blocked_reason 값

| 값 | 설명 |
|----|------|
| `NO_SECRETS_FOR_ANY_CHANNEL` | 모든 채널의 시크릿 미충족 |
| `PUSH_TYPE_NOT_ALLOWED` | 허용되지 않은 push_type |
| `null` | 정상 (candidate=true) |

---

## 6. 핵심 규칙

> 🛑 **delivery_actual = CONSOLE (고정)**
> 
> 어떤 상황에서도 실제 발송(`delivery_actual`)은 항상 `CONSOLE`입니다.
> 외부 발송은 절대 금지입니다.

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 2.0 | 2026-01-04 | 초기 버전 (Phase C-P.19) - V1 Superset |
