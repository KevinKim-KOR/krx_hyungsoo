# Contract: Ops Runner V1

**Version**: 1.0
**Date**: 2026-01-04
**Status**: LOCKED

---

## 1. 개요

운영 관측 루프(Ops Runner)의 입출력 및 정책을 정의합니다.

---

## 2. Runner 입력 (SoT)

| 경로 | 설명 |
|------|------|
| `reports/ops/daily/ops_report_latest.json` | 최신 일일 운영 리포트 |
| `state/tickets/ticket_requests.jsonl` | 티켓 요청 로그 |
| `state/tickets/ticket_results.jsonl` | 티켓 처리 결과 |
| `state/tickets/ticket_receipts.jsonl` | 실행 영수증 |
| `state/execution_gate.json` | 실행 게이트 상태 |
| `state/emergency_stop.json` | 비상 정지 상태 |
| `state/real_enable_windows/real_enable_windows.jsonl` | REAL 윈도우 상태 |
| `state/approvals/real_enable_approvals.jsonl` | 2-Key 승인 상태 |

---

## 3. Runner 출력 (Artifacts)

| 경로 | 설명 |
|------|------|
| `reports/ops/daily/snapshots/ops_run_YYYYMMDD_HHMMSS.json` | 실행 스냅샷 |

---

## 4. Runner 정책

### 4-A. Emergency Stop

```
if emergency_stop.active == true:
    status = "STOPPED"
    snapshot 기록 후 즉시 종료
```

### 4-B. 중복 실행 방지

- Lock 파일: `state/ops_runner.lock`
- 최근 N분(기본 1분) 내 동일 lock이면 중복 실행 차단
- 차단 시 `status = "SKIPPED"` + snapshot 기록

### 4-C. 실패 시 재시도 정책

- 재시도 횟수: 0회 (즉시 실패 처리)
- 다음 스케줄에서만 재시도

---

## 5. 실행 순서 (고정)

```
1. Emergency Stop 확인
   └─ active → STOPPED
   
2. Lock 확보 (중복 실행 방지)
   └─ 이미 locked → SKIPPED
   
3. Ops Report regenerate
   └─ 최신 데이터 집계
   
4. Tickets 최신 상태 조회
   └─ /api/tickets/latest → snapshot에 저장
   
5. Push 최신 조회
   └─ /api/push/latest → snapshot에 저장
   
6. Snapshot 기록 및 종료
   └─ status: DONE / STOPPED / SKIPPED / FAILED
```

---

## 6. Snapshot 스키마

```json
{
  "schema": "OPS_RUN_SNAPSHOT_V1",
  "run_id": "uuid",
  "started_at": "ISO timestamp",
  "finished_at": "ISO timestamp",
  "status": "DONE | STOPPED | SKIPPED | FAILED",
  "reason": "...",
  "ops_summary": { ... },
  "tickets_summary": { "total": N, "open": N, "done": N },
  "push_summary": { "last_push_at": "...", "count": N }
}
```

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-04 | 초기 버전 (Phase C-P.15) |
