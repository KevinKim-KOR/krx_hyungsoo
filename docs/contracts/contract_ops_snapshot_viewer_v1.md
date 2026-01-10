# Contract: Ops Snapshot Viewer V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

운영 스냅샷 읽기 전용 조회 API 및 보안 정책을 정의합니다.

> 🔒 **Read-Only**: 어떤 경우에도 서버 상태/파일 수정 금지
> 
> 🔒 **Path Traversal Block**: snapshot_id 화이트리스트 검증 필수

---

## 2. API Specifications

### 2-A. 목록 조회

```
GET /api/ops/scheduler/snapshots
```

**Response:**
```json
{
  "status": "ready",
  "schema": "OPS_SCHEDULER_SNAPSHOTS_V1",
  "row_count": 5,
  "rows": [
    { "snapshot_id": "ops_run_20260110_090500.json", "mtime": "...", "size_bytes": 1234 }
  ]
}
```

### 2-B. 단건 조회

```
GET /api/ops/scheduler/snapshots/{snapshot_id}
```

**Parameters:**
- `snapshot_id`: 파일명 (예: `ops_run_20260110_090500.json`)

**Response (Success):**
```json
{
  "status": "ready",
  "schema": "OPS_RUN_RECEIPT_V1",
  "snapshot_id": "ops_run_20260110_090500.json",
  "data": { ... original receipt ... }
}
```

**Response (Error):**
```json
{
  "status": "error",
  "schema": "OPS_SNAPSHOT_VIEWER_V1",
  "error": {
    "code": "INVALID_ID" | "NOT_FOUND",
    "message": "..."
  }
}
```

---

## 3. Security Policy

### 3-A. snapshot_id Validation

> ⚠️ **정규식 검증 필수**

```regex
^[a-zA-Z0-9_\-\.]+\.json$
```

- 경로 구분자 (`/`, `\`, `..`) 포함 시 → **400 Bad Request**
- 영숫자, 밑줄, 하이픈, 점만 허용

### 3-B. Directory Restriction

```
reports/ops/scheduler/snapshots/
```

- 하드코딩된 경로만 사용
- 클라이언트 입력으로 상위 디렉토리 탈출 불가

---

## 4. Error Codes

| HTTP | Code | 설명 |
|------|------|------|
| 400 | `INVALID_ID` | snapshot_id 형식 오류 (Path Traversal 시도 포함) |
| 404 | `NOT_FOUND` | 파일 없음 |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.29) |
