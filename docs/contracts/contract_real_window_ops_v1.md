# Contract: Real Window Ops V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

REAL Enable Window의 운영 정책을 정의합니다.

---

## 2. Window 정책

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `ttl_minutes` | 10 | 윈도우 유효 시간 |
| `cooldown_minutes` | 60 | 재발급 대기 시간 (선택적 강제) |
| `max_real_per_window` | 1 | 윈도우당 최대 REAL 실행 횟수 |
| `allowed_request_types` | `["REQUEST_RECONCILE", "REQUEST_REPORTS"]` | 허용된 요청 타입 |

---

## 3. 우선순위 체크 순서 (Fail-Fast)

```
1. emergency_stop == ON → 강제 MOCK_ONLY
2. gate.mode != REAL_ENABLED → 차단 (BLOCKED)
3. approval.status != APPROVED → 차단 (BLOCKED)
4. window.status != ACTIVE → 차단 (BLOCKED)
5. window.real_executions_used >= max_real_per_window → 차단 (CONSUMED)
6. allowlist mismatch → 차단 (BLOCKED)
7. preflight != PASS → 차단 (PREFLIGHT_FAIL)
```

> 🔒 **Fail-Closed**: 어느 단계든 실패하면 REAL 실행 금지

---

## 4. Window 생명주기

```
CREATE → ACTIVE → (CONSUME or REVOKE or EXPIRE)
         ↓
       CONSUMED (max_real 도달)
       REVOKED (수동 취소)
       EXPIRED (TTL 초과)
```

---

## 5. Revoke 우선순위

- Emergency Stop이 켜지면 모든 ACTIVE 윈도우는 자동으로 무효화됨 (REVOKE 대신 Gate 차단)
- 수동 Revoke는 즉시 ACTIVE → REVOKED

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.13) |
