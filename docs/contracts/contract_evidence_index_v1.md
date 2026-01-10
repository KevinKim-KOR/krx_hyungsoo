# Contract: Evidence Index V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

시스템 전반의 증거(Evidence)를 인덱싱하여 UI에 표시하는 규격을 정의합니다.

> 🔒 **Read-Only**: 엔진 실행 금지, 읽기/집계/인덱싱만
> 
> 🔒 **Atomic Write**: `.tmp` → `os.replace()` 원자적 교체

---

## 2. Schema: EVIDENCE_INDEX_V1

```json
{
  "schema": "EVIDENCE_INDEX_V1",
  "asof": "2026-01-10T21:00:00+09:00",
  "row_count": 5,
  "rows": [
    { /* EVIDENCE_ITEM_V1 */ }
  ]
}
```

---

## 3. Schema: EVIDENCE_ITEM_V1

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| evidence_id | string | ✅ | sha256(ref)[:12] |
| created_at | string | ✅ | ISO datetime |
| title | string | ✅ | UI 표시용 |
| kind | enum | ✅ | 증거 유형 |
| severity | enum | ✅ | INFO/WARN/ERROR/CRITICAL |
| ref | string | ✅ | evidence_ref_v1 포맷 |
| tags | string[] | ❌ | 태그 |
| links | object | ❌ | 관련 링크 |
| request_id | string | ❌ | 요청 ID |
| ticket_line_ref | string | ❌ | Human hint |

### 3-A. kind enum

| 값 | 설명 |
|----|------|
| TICKET_RECEIPT | 티켓 영수증 |
| OPS_RUN | Ops 실행 영수증 |
| PUSH_SEND | Push 발송 영수증 |
| PUSH_POSTMORTEM | Postmortem 리포트 |
| SECRETS_SELF_TEST | Secrets 자가진단 |
| PHASE_C_LATEST | Phase C 최신 리포트 |
| OTHER | 기타 |

### 3-B. severity enum

| 값 | 설명 |
|----|------|
| INFO | 정상 |
| WARN | 경고 |
| ERROR | 오류 |
| CRITICAL | 심각 |

---

## 4. Artifact 경로

| 타입 | 경로 |
|------|------|
| Latest | `reports/ops/evidence/index/evidence_index_latest.json` |
| Snapshots | `reports/ops/evidence/index/snapshots/evidence_index_YYYYMMDD_HHMMSS.json` |

---

## 5. API Specification

### 5-A. GET /api/evidence/index/latest

**Response (Normal):**
```json
{
  "status": "ready",
  "schema": "EVIDENCE_INDEX_V1",
  "asof": "...",
  "row_count": 5,
  "rows": [...]
}
```

**Response (Empty):**
```json
{
  "status": "ready",
  "schema": "EVIDENCE_INDEX_V1",
  "asof": null,
  "row_count": 0,
  "rows": [],
  "error": { "code": "NO_INDEX_YET" }
}
```

### 5-B. POST /api/evidence/index/regenerate

- 경로/입력값 받지 않음
- 서버 고정 경로만 사용
- `confirm()` 필수 (UI)

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.31) |
