# Contract: Execution Gate V1

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

Execution Gate는 **워커의 실행 모드를 제어**하는 게이트웨이입니다.

> 🚫 **C-P.4 Restriction**: `REAL_ENABLED` 모드로의 진입은 API 레벨에서 차단됩니다.

---

## 2. 스키마 정의

### EXECUTION_GATE_V1

```json
{
  "schema": "EXECUTION_GATE_V1",
  "mode": "MOCK_ONLY | DRY_RUN | REAL_ENABLED",
  "updated_at": "2026-01-03T16:00:00+09:00",
  "updated_by": "local_api",
  "reason": "Gate 변경 사유"
}
```

| Key | Type | 필수 | 생성 주체 | 설명 |
|-----|------|------|-----------|------|
| `mode` | enum | ✅ | Client | 실행 모드 |
| `updated_at` | ISO8601 | ✅ | **Server** | 변경 시각 |
| `updated_by` | string | ✅ | **Server** | 변경 주체 (고정: "local_api") |
| `reason` | string | ✅ | Client | 변경 사유 |

---

## 3. Mode 정의

| Mode | 설명 | 동작 |
|------|------|------|
| `MOCK_ONLY` | 모의 실행 (Default) | `time.sleep` + `[MOCK_ONLY]` 메시지 |
| `DRY_RUN` | 검증 실행 | Payload 검증 + `[DRY_RUN]` 메시지 |
| `REAL_ENABLED` | 실제 실행 | **C-P.4에서 금지됨** |

---

## 4. 저장소 경로

| 경로 | 용도 |
|------|------|
| `state/execution_gate.json` | Gate 상태 저장 |

**Default Policy**: 파일 부재 시 `MOCK_ONLY`로 간주

---

## 5. Transition Rules

| From | To | 허용 |
|------|----|------|
| `MOCK_ONLY` | `DRY_RUN` | ✅ |
| `DRY_RUN` | `MOCK_ONLY` | ✅ |
| Any | `MOCK_ONLY` | ✅ (Emergency Stop) |
| Any | `REAL_ENABLED` | ❌ **400 Bad Request** |

---

## 6. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/execution_gate` | 현재 Gate 상태 조회 |
| POST | `/api/execution_gate` | Gate 모드 변경 |

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.4) |
