# Contract: Dashboard API V1

**Version**: 1.0
**Date**: 2026-02-17
**Status**: ACTIVE

---

## 1. 개요

Operator Dashboard(`http://localhost:8000/dashboard`)에서 사용되는 Backend API 정의.
P146.8에서 Token 검증 및 Ticket Regeneration 로직이 강화되었습니다.

---

## 2. Draft Management

### 2.1 Generate Draft
- **Method**: `POST /api/operator/dashboard/draft`
- **Description**: 현재 Ops Summary 및 Ticket 상태를 기반으로 Draft(JSON)를 생성합니다.
- **Response**: `{"pretty_json": "...", "raw_json": {...}}`

### 2.2 Submit Draft
- **Method**: `POST /api/operator/dashboard/draft/submit`
- **Description**: 검토 완료된 Draft를 티켓 시스템에 제출합니다.
- **Parameters**:
  - `token` (Body, str, required if LIVE): 운영 토큰. DRY_RUN 모드에서는 선택 사항.
  - `draft` (Body, json): 제출할 Draft 내용.

---

## 3. Ops Management

### 3.1 Regenerate Ops Summary
- **Method**: `POST /api/ops/summary/regenerate`
- **Query Params**:
  - `confirm` (bool): `true` 필수.
- **Description**: `reports/ops/summary/ops_summary_latest.json`을 강제 재생성.

### 3.2 Regenerate Ticket MD
- **Method**: `POST /api/operator/ticket/regenerate/{ticket_date}`
- **Description**: 특정 날짜의 `ticket_{date}.md` 파일을 DB(JSONL) 기반으로 재생성.
- **Changes (P146.8)**: 재생성 시 `execution_plan` ID와 `token` 정보를 최신 상태로 동기화.

---

## 4. Token Policy (P146.8)

- **LIVE Mode**: `token` 필드 필수. `EXPORT` 아티팩트의 `confirm_token`과 일치해야 함.
- **DRY_RUN Mode**: Server-Side에서 `mock_token` 자동 주입 (Client 생략 가능).
