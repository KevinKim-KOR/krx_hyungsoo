# Contract: Ops Scheduler API V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

Ops Scheduler 관련 API Envelope 및 Empty State 규칙을 정의합니다.

> 🔒 **Graceful Empty State**: 파일 없어도 500/크래시 금지
> 
> 🔒 **No Path Traversal**: 클라이언트 입력으로 경로 지정 금지

---

## 2. GET /api/ops/scheduler/latest

### 요청
- Method: `GET`
- Path: `/api/ops/scheduler/latest`
- 파라미터: 없음

### 응답 Envelope

```json
{
  "status": "ready" | "not_ready" | "error",
  "schema": "OPS_RUN_RECEIPT_V1",
  "asof": "2026-01-10T09:05:00",
  "row_count": 1,
  "rows": [{ ... receipt ... }],
  "error": null | { "code": "...", "message": "..." }
}
```

### Empty State 규칙

| 상황 | status | error.code | 설명 |
|------|--------|------------|------|
| 파일 없음 | `not_ready` | `NO_RUN_HISTORY` | 아직 실행 이력 없음 |
| 파일 있음 | `ready` | `null` | 정상 |
| 읽기 오류 | `error` | `READ_ERROR` | 파일 파싱 실패 |

---

## 3. GET /api/ops/scheduler/snapshots

### 요청
- Method: `GET`
- Path: `/api/ops/scheduler/snapshots`
- 파라미터: **없음** (Path Traversal 방지)

### 응답 Envelope

```json
{
  "status": "ready",
  "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
  "asof": "2026-01-10T09:05:00",
  "directory": "reports/ops/scheduler/snapshots",
  "row_count": 5,
  "rows": [
    { "filename": "ops_run_20260110_090500.json", "mtime": "...", "size_bytes": 1234 }
  ],
  "error": null
}
```

### 보안 규칙

> 🔒 **서버에서 하드코딩된 경로만 조회**
> 
> - 디렉토리: `reports/ops/scheduler/snapshots/`
> - 클라이언트 파라미터로 경로 지정 금지
> - 최신 20개 파일만 반환 (DoS 방지)

---

## 4. POST /api/ops/cycle/run

기존 엔드포인트 재사용 (신규 생성 금지).

### UI 호출 시 주의사항

> ⚠️ **Clumsy Finger Protection**
> 
> UI에서 호출 전 `confirm()` 필수

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.28) |
