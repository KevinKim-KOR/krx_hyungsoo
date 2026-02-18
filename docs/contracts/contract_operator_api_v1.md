# Contract: Operator API V1

**Version**: 1.1 (Replaces Dashboard API V1)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

OCI Execution Plane(`:8000`)에서 제공하는 Operator Dashboard(`:8000/operator`) 전용 API입니다.
Operator는 이 API를 통해 보안 토큰을 제출하고, 매매 Draft를 검증/승인합니다.

---

## 2. Draft Management (매매 승인)

### 2.1 Generate Draft (Preview)
- **Method**: `POST /api/operator/draft`
- **Description**: 현재 `Ticket`과 `Ops Summary`를 기반으로 실행될 매매 내용을 미리보기(Preview) 합니다.
- **Response**:
  ```json
  {
    "pretty_json": "...(Human Readable JSON)...",
    "raw_json": { "ticket_ref": "...", "plan_id": "...", "action": "BUY" }
  }
  ```

### 2.2 Submit Draft (Final Approval)
- **Method**: `POST /api/operator/draft/submit`
- **Description**: 검토된 Draft를 최종 승인하여 `Execution Record`를 생성하고 매매를 진행합니다.
- **Rules**:
  - **LIVE Mode**: `token` 필수. (`EXPORT_CONFIRM_TOKEN`과 일치해야 함)
  - **DRY_RUN Mode**: Server-Side Mock Token 자동 주입.
- **Parameters**:
  - `token` (Body, str): 운영자 승인 토큰.
  - `draft` (Body, json): 2.1에서 받은 raw_json.

---

## 3. Ops Management (상태 제어)

### 3.1 Regenerate Ops Summary
- **Method**: `POST /api/ops/summary/regenerate`
- **Query**: `confirm=true`
- **Description**: `ops_summary_latest.json`을 현재 Artifact 상태 기반으로 재작성합니다. (Stage 복구용)

### 3.2 Regenerate Ticket MD
- **Method**: `POST /api/operator/ticket/regenerate/{ticket_date}`
- **Description**: `ticket_{date}.md` 파일을 DB/Export 기반으로 재생성합니다.
- **Constraint**: `plan_id`와 `token` 정보를 최신 `Export` 아티팩트와 동기화합니다.

---

## 4. UI Required Actions Logic

Operator Dashboard는 `ops_summary.manual_loop.required_actions` 필드를 보고 UI를 렌더링합니다.

| Action Code | UI Behavior | Token Requirement |
|---|---|---|
| `REVIEW_TICKET` | **Draft Manager** 표시 | - |
| `SUBMIT_TICKET` | **Submit Button** 활성화 | **LIVE**: 필수 (Input Show)<br>**DRY**: 숨김 (Auto-Fill) |
| `WAIT` | "대기 중" 표시 | - |

---

## 5. Token Source of Truth

- **Primary Source**: `reports/live/order_plan_export/latest/order_plan_export_latest.json` -> `confirm_token`
- **Validation**:
  - API는 요청받은 `token`을 위 파일의 `confirm_token`과 대조합니다.
  - 불일치 시 `403 Forbidden`을 반환하며, `plan_id` 불일치로 간주하여 차단합니다.
