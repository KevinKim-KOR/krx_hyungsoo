# Contract: Real Enable Window V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Real Enable Window는 **REAL 실행을 제한된 시간창 안에서만 허용**합니다.

> ⏱️ **Time-Boxed Execution**: TTL 만료 또는 max 소진 시 자동 비활성화

---

## 2. 스키마 정의

### REAL_ENABLE_WINDOW_V1

```json
{
  "schema": "REAL_ENABLE_WINDOW_V1",
  "event": "CREATE | REVOKE | CONSUME",
  "window_id": "uuid",
  "created_at": "ISO datetime (server)",
  "expires_at": "ISO datetime (server)",
  "created_by": "api",
  "reason": "string",
  "allowed_request_types": ["REQUEST_REPORTS"],
  "max_real_executions": 1,
  "real_executions_used": 0,
  "status": "ACTIVE | EXPIRED | REVOKED | CONSUMED"
}
```

| Key | Type | 생성 주체 | 설명 |
|-----|------|-----------|------|
| `window_id` | UUID | **Server** | 창 고유 ID |
| `created_at` | ISO8601 | **Server** | 생성 시각 |
| `expires_at` | ISO8601 | **Server** | 만료 시각 (TTL) |
| `allowed_request_types` | array | Forced | C-P.9에서 `["REQUEST_REPORTS"]` 고정 |
| `max_real_executions` | int | Forced | C-P.9에서 `1` 고정 |
| `status` | enum | Computed | 현재 상태 |

---

## 3. Status 계산 규칙

| 조건 | Status |
|------|--------|
| expires_at 경과 | EXPIRED |
| REVOKE 이벤트 존재 | REVOKED |
| real_executions_used >= max | CONSUMED |
| 그 외 | ACTIVE |

---

## 4. 저장소 경로

| 경로 | 정책 |
|------|------|
| `state/real_enable_windows/real_enable_windows.jsonl` | Append-only |

---

## 5. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/real_enable_window/request` | Window 생성 |
| GET | `/api/real_enable_window/latest` | 현재 Window 조회 |
| POST | `/api/real_enable_window/revoke` | Window 폐기 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.9) |
