# Contract: Real Sender Enable V1

**Version**: 1.0
**Date**: 2026-01-07
**Status**: LOCKED

---

## 1. 개요

실제 발송 기능의 활성화/비활성화 상태를 정의합니다.

> 🔒 **채널 제한**: TELEGRAM_ONLY
> 
> 🔒 **One-Shot**: 윈도우당 1건만 발송 허용

---

## 2. 스키마 정의

### REAL_SENDER_ENABLE_V1

```json
{
  "schema": "REAL_SENDER_ENABLE_V1",
  "enabled": false,
  "channel": "TELEGRAM_ONLY",
  "updated_at": "2026-01-07T23:00:00",
  "updated_by": "api",
  "reason": "Initial setup"
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `enabled` | boolean | 발송 활성화 여부 (default: false) |
| `channel` | enum | `TELEGRAM_ONLY` (고정) |
| `updated_at` | ISO8601 | 마지막 업데이트 시각 (서버 주입) |
| `updated_by` | string | 업데이트 주체 (서버 주입) |
| `reason` | string | 활성화/비활성화 사유 |

---

## 4. 정책

> 🚫 **파일 직접 수정 금지**
> 
> Enable/Disable은 반드시 Backend API를 통해서만 수행

| 동작 | 조건 |
|------|------|
| Enable (켜기) | `reason` 필수 |
| Disable (끄기) | 즉시 허용 |

---

## 5. Default 동작

- 파일 없음 → `enabled=false`
- 파일 손상 → `enabled=false`

---

## 6. 저장소 경로

| 경로 | 용도 |
|------|------|
| `state/real_sender_enable.json` | 현재 상태 |

---

## 7. API Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/real_sender_enable` | 현재 상태 조회 |
| POST | `/api/real_sender_enable` | 상태 변경 |

---

## 8. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-07 | 초기 버전 (Phase C-P.23) |
