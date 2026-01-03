# Contract: Ticket Worker V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

티켓 워커는 **OPEN 상태의 티켓을 자동으로 처리**하는 백그라운드 프로세스입니다.

> 🚫 **No Execution 원칙**: 이 버전은 Mock Worker입니다. 실제 엔진(Reconcile, Report)을 실행하지 않고 상태 전이만 수행합니다.

---

## 2. Worker 위치

| 경로 | 설명 |
|------|------|
| `app/run_ticket_worker.py` | Core Application Logic으로 격상 |

> ⚠️ **Path Governance**: `tools/`가 아닌 `app/`에 위치해야 합니다.

---

## 3. Worker Responsibilities

### 3.1 Polling Strategy

1. `state/tickets/ticket_requests.jsonl` 읽기
2. `state/tickets/ticket_results.jsonl` 읽기
3. 두 파일을 Join하여 현재 상태 계산
4. `current_status == "OPEN"` 인 티켓 필터링

### 3.2 Locking Strategy

| 파일 | 용도 |
|------|------|
| `state/worker.lock` | 중복 실행 방지 |

**Lock 파일 포맷:**
```json
{
  "pid": 12345,
  "acquired_at": "2026-01-03T15:30:00+09:00"
}
```

**Stale Lock Recovery:**
- Lock 파일 존재 AND (현재시간 - acquired_at < 10분) → **종료** (Locked)
- Lock 파일 존재 AND (현재시간 - acquired_at ≥ 10분) → **경고 후 덮어쓰기** (Force Acquire)
- Lock 파일 없음 → **생성** (Acquired)

**Cleanup:**
- `try...finally` 블록으로 종료 시 Lock 파일 삭제 보장

---

## 4. Processing Flow

```
1. Acquire Lock
   │
   ├─ Locked? → Exit
   │
2. Scan OPEN Tickets
   │
3. For each ticket:
   │
   ├─ POST /api/tickets/consume
   │   └─ 409? → Continue (다른 워커 선점)
   │
   ├─ Mock Execute (sleep 1s)
   │
   └─ POST /api/tickets/complete
       ├─ status: DONE
       └─ message: "SUCCESS [MOCK_ONLY]: ..."
   │
4. Release Lock (finally)
```

---

## 5. Message Policy

Mock Execution 완료 시 `message` 필드 형식:

```
SUCCESS [MOCK_ONLY]: Simulated execution for {request_type}
```

| Tag | 의미 |
|-----|------|
| `SUCCESS` | 성공적으로 처리됨 |
| `[MOCK_ONLY]` | 실제 엔진 실행 없음 (시뮬레이션) |

> ⚠️ **필수**: Mock Worker는 반드시 `[MOCK_ONLY]` 태그를 포함해야 합니다.

---

## 6. 409 Conflict Handling

| 상황 | 처리 |
|------|------|
| consume 시 409 | 다른 워커가 선점 → **Continue** (다음 티켓) |
| complete 시 409 | 상태 불일치 → **Log + Continue** |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.3) |
