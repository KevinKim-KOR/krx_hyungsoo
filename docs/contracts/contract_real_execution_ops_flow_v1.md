# Contract: Real Execution Ops Flow V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

REAL 실행의 운영 플로우를 정의합니다. 모든 REAL 실행 시도는 이 흐름을 순서대로 거쳐야 하며, 어느 단계에서든 실패하면 즉시 차단됩니다.

---

## 2. Flow 정의 (순서 고정)

```
┌─────────────────────────────────────────────────────────────┐
│                    REAL EXECUTION FLOW                       │
├─────────────────────────────────────────────────────────────┤
│  1. Emergency Stop 확인                                      │
│     └─ ON → BLOCKED (EMERGENCY_STOP_ACTIVE)                 │
│                                                              │
│  2. Execution Gate 모드 확인                                 │
│     └─ != REAL_ENABLED → BLOCKED (GATE_MODE_NOT_REAL)       │
│                                                              │
│  3. Allowlist Exact Match 확인                               │
│     └─ FAIL → BLOCKED (ALLOWLIST_VIOLATION)                 │
│                                                              │
│  4. Approval (2-Key) 확인                                    │
│     └─ != APPROVED → BLOCKED (APPROVAL_NOT_APPROVED)        │
│                                                              │
│  5. Real Enable Window 확인                                  │
│     ├─ status != ACTIVE → BLOCKED (WINDOW_NOT_ACTIVE)       │
│     ├─ TTL 만료 → BLOCKED (WINDOW_EXPIRED)                  │
│     └─ 1회 소진 → BLOCKED (WINDOW_CONSUMED)                 │
│                                                              │
│  6. Preflight PASS 확인                                      │
│     ├─ 의존성 실패 → BLOCKED (PREFLIGHT_DEPS_FAIL)          │
│     └─ 입력 미준비 → BLOCKED (PREFLIGHT_INPUT_FAIL)         │
│                                                              │
│  7. 실행 시도 (subprocess)                                   │
│     ├─ exit_code != 0 → FAILED (EXECUTION_ERROR)            │
│     └─ 타임아웃 → FAILED (EXECUTION_TIMEOUT)                │
│                                                              │
│  8. Receipt V3 기록                                          │
│     └─ sha256/size/mtime triple proof + verified            │
│                                                              │
│  9. Ops Report 갱신                                          │
│     └─ last_done/last_failed/last_blocked 업데이트          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. BLOCKED vs FAILED 구분 규칙

| 구분 | 정의 | 발생 시점 |
|------|------|-----------|
| **BLOCKED** | 안전장치에 의해 **의도된** 차단 | Step 1-6 (실행 전) |
| **FAILED** | 실행 **시도 후** 실패 | Step 7 (실행 중) |

> 🔒 **원칙**: 실행이 시작되지 않았으면 BLOCKED, 시작 후 실패하면 FAILED

---

## 4. 사유 코드 매핑

| 코드 | 단계 | UI 메시지 (한글) | 분류 |
|------|------|------------------|------|
| `EMERGENCY_STOP_ACTIVE` | 1 | 비상 정지 활성화됨 | BLOCKED |
| `GATE_MODE_NOT_REAL` | 2 | 실행 게이트가 REAL 모드 아님 | BLOCKED |
| `ALLOWLIST_VIOLATION` | 3 | 허용 목록과 불일치 | BLOCKED |
| `APPROVAL_NOT_APPROVED` | 4 | 2-Key 승인 미완료 | BLOCKED |
| `WINDOW_NOT_ACTIVE` | 5 | REAL 윈도우 비활성 | BLOCKED |
| `WINDOW_EXPIRED` | 5 | REAL 윈도우 TTL 만료 | BLOCKED |
| `WINDOW_CONSUMED` | 5 | REAL 윈도우 1회 소진 | BLOCKED |
| `PREFLIGHT_DEPS_FAIL` | 6 | 필수 의존성 미설치 | BLOCKED |
| `PREFLIGHT_INPUT_FAIL` | 6 | 입력 파일 미준비 | BLOCKED |
| `EXECUTION_ERROR` | 7 | 실행 오류 (exit_code != 0) | FAILED |
| `EXECUTION_TIMEOUT` | 7 | 실행 타임아웃 | FAILED |
| `UNKNOWN_ERROR` | - | 알 수 없는 오류 | FAILED |

---

## 5. Receipt V3 Triple Proof

모든 REAL 실행 완료 후 아래를 기록:

```json
{
  "outputs_proof": {
    "targets": [
      {
        "path": "reports/phase_c/latest/...",
        "before": { "sha256": "...", "size_bytes": N, "mtime_iso": "..." },
        "after":  { "sha256": "...", "size_bytes": N, "mtime_iso": "..." },
        "changed": true|false,
        "verified": true
      }
    ]
  },
  "acceptance": {
    "pass": true,
    "reason": "CHANGED_VERIFIED | UNCHANGED_BUT_HASH_MATCH_VERIFIED"
  }
}
```

---

## 6. Safety Counters (Ops Report)

| 카운터 | 설명 |
|--------|------|
| `window_consumed_count` | 1회 소진으로 차단된 횟수 |
| `emergency_stop_hits` | Emergency Stop 발동 횟수 |
| `allowlist_violation_hits` | Allowlist 불일치 횟수 |
| `preflight_fail_hits` | Preflight 실패 횟수 |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.14) |
