# Contract: Emergency Stop V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Emergency Stop은 **즉시 모든 실행을 중단**하는 비상 정지 시스템입니다.

> 🛑 **Priority Override**: Emergency Stop이 활성화되면 Gate는 무조건 MOCK_ONLY로 강제됩니다.

---

## 2. 스키마 정의

### EMERGENCY_STOP_V1

```json
{
  "schema": "EMERGENCY_STOP_V1",
  "enabled": true,
  "updated_at": "2026-01-03T17:00:00+09:00",
  "updated_by": "operator_id",
  "reason": "비상 정지 사유"
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `enabled` | boolean | ✅ | Client | 정지 상태 |
| `updated_at` | ISO8601 | ✅ | **Server** | 변경 시각 |
| `updated_by` | string | ✅ | Client | 변경자 ID |
| `reason` | string | ✅ | Client | 정지 사유 |

---

## 3. 동작 규칙

| 조건 | 결과 |
|------|------|
| `enabled = true` | Gate → MOCK_ONLY 강제 |
| `enabled = true` | Worker → SKIP (Receipt: SKIPPED) |
| `enabled = false` | 정상 동작 |

---

## 4. 저장소 경로

| 경로 | 용도 |
|------|------|
| `state/emergency_stop.json` | 현재 상태 |

---

## 5. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/emergency_stop` | 현재 상태 조회 |
| POST | `/api/emergency_stop` | 상태 변경 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.6) |
