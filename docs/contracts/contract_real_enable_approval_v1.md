# Contract: Real Enable Approval V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Two-Key Approval은 **REAL_ENABLED 모드 진입을 위한 이중 승인 시스템**입니다.

> 🔐 **Two-Key Required**: 2개의 독립적인 Key가 모두 제공되어야 승인 완료됩니다.

---

## 2. 스키마 정의

### REAL_ENABLE_APPROVAL_V1

```json
{
  "schema": "REAL_ENABLE_APPROVAL_V1",
  "approval_id": "uuid",
  "requested_at": "2026-01-03T17:00:00+09:00",
  "requested_by": "operator_id",
  "mode_target": "REAL_ENABLED",
  "reason": "승인 요청 사유",
  "expires_at": "2026-01-04T17:00:00+09:00",
  "keys_required": 2,
  "keys": [
    {"key_id": "key1", "provided_by": "approver1", "provided_at": "..."},
    {"key_id": "key2", "provided_by": "approver2", "provided_at": "..."}
  ],
  "status": "PENDING | APPROVED | EXPIRED | REVOKED"
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `approval_id` | UUID | ✅ | **Server** | 승인 요청 고유 ID |
| `requested_at` | ISO8601 | ✅ | **Server** | 요청 시각 |
| `requested_by` | string | ✅ | Client | 요청자 ID |
| `mode_target` | string | ✅ | Fixed | "REAL_ENABLED" |
| `reason` | string | ✅ | Client | 승인 사유 |
| `expires_at` | ISO8601 | ✅ | **Server** | 만료 시각 (24시간 후) |
| `keys_required` | int | ✅ | Fixed | 2 (고정) |
| `keys` | array | ✅ | Mixed | 제공된 키 목록 |
| `status` | enum | ✅ | **Server** | 현재 상태 |

---

## 3. Status 정의

| Status | 설명 |
|--------|------|
| `PENDING` | 키 대기 중 (0-1개 제공됨) |
| `APPROVED` | 승인 완료 (2개 키 제공됨) |
| `EXPIRED` | 만료됨 (expires_at 경과) |
| `REVOKED` | 취소됨 |

---

## 4. 저장소 경로

| 경로 | 정책 |
|------|------|
| `state/approvals/real_enable_approvals.jsonl` | Append-only |

---

## 5. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/approvals/real_enable/request` | 승인 요청 생성 |
| POST | `/api/approvals/real_enable/approve` | 키 제공 |
| GET | `/api/approvals/real_enable/latest` | 최신 상태 조회 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.6) |
