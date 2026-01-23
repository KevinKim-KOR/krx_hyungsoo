# Contract: Evidence Ref V1

**Version**: 1.0
**Date**: 2026-01-10
**Status**: LOCKED

---

## 1. 개요

스냅샷/영수증의 `*_ref` 필드를 안전하게 해석하고 증거를 반환하는 Resolver 규칙을 정의합니다.

> 🔒 **Read-Only**: 상태 변경 금지
> 
> 🔒 **Allowlist Resolver**: 규칙 밖 ref는 400 INVALID_REF
> 
> 🔒 **이중 방어**: Regex 검증 + Path Normalization

---

## 2. Ref 타입 정의

### 2-A. JSONL Line Refs

| 타입 | 패턴 | 예시 |
|------|------|------|
| receipt_ref | `state/tickets/ticket_receipts.jsonl:line\d+` | `state/tickets/ticket_receipts.jsonl:line5` |
| results_ref | `state/tickets/ticket_results.jsonl:line\d+` | `state/tickets/ticket_results.jsonl:line54` |
| send_receipt_ref | `state/push/send_receipts.jsonl:line\d+` | `state/push/send_receipts.jsonl:line3` |

**정규식:**
```regex
^(state/tickets/ticket_receipts\.jsonl|state/tickets/ticket_results\.jsonl|state/push/send_receipts\.jsonl):line(\d+)$
```

**규칙:**
- `:lineN` 형식만 허용 (N >= 1, 정수만)
- 허용된 JSONL 파일 3개만 접근 가능

### 2-B. JSON Refs

| 타입 | 패턴 | 예시 |
|------|------|------|
| ops_run_snapshot_ref | `reports/ops/scheduler/snapshots/<id>.json` | `reports/ops/scheduler/snapshots/ops_run_20260110_090500.json` |
| postmortem_latest_ref | `reports/ops/push/postmortem/postmortem_latest.json` | - |
| self_test_latest_ref | `reports/ops/secrets/self_test_latest.json` | - |
| outbox_snapshot_ref | `reports/ops/push/outbox/snapshots/<id>.json` | - |
| live_fire_ref | `reports/ops/push/live_fire/live_fire_latest.json` | - |

**정규식:**
```regex
^reports/ops/(scheduler/snapshots/[a-zA-Z0-9_\-\.]+\.json|push/postmortem/postmortem_latest\.json|secrets/self_test_latest\.json|push/outbox/snapshots/[a-zA-Z0-9_\-\.]+\.json|push/live_fire/live_fire_latest\.json)$
```

---

## 3. Resolver 규칙

### 3-A. 1차 검증 (문자열 레벨)

> ⚠️ **위험 토큰 즉시 거부**

- `..` 포함 → 400
- `\` 포함 → 400
- `://` 포함 → 400
- `%2e`, `%2f` 등 URL 인코딩 → 400
- 정규식 미매칭 → 400

### 3-B. 2차 검증 (Path Normalization)

```python
abs_path = os.path.abspath(candidate_path)
allowed_root = os.path.abspath(BASE_DIR)
if not abs_path.startswith(allowed_root + os.sep):
    # 400 INVALID_REF
```

### 3-C. JSONL Line Reading

> 🔒 **전체 읽기 금지**

```python
import linecache
line_content = linecache.getline(str(path), line_no)
```

또는:
```python
with open(path) as f:
    for idx, line in enumerate(f, start=1):
        if idx == line_no:
            return json.loads(line)
```

---

## 4. API Specification

### GET /api/evidence/resolve

**Parameters:**
- `ref` (query): ref 문자열

**Response (Success):**
```json
{
  "status": "ready",
  "schema": "EVIDENCE_VIEW_V1",
  "asof": "2026-01-10T09:05:00",
  "row_count": 1,
  "rows": [{
    "ref": "state/tickets/ticket_receipts.jsonl:line5",
    "data": { ... },
    "source": {
      "kind": "JSONL_LINE",
      "path": "state/tickets/ticket_receipts.jsonl",
      "line": 5
    }
  }],
  "error": null
}
```

**Error Codes:**

| HTTP | Code | 설명 |
|------|------|------|
| 400 | INVALID_REF | ref 형식 오류, 위험 토큰, 경로 탈출 |
| 404 | NOT_FOUND | 파일/라인 없음 |
| 500 | PARSE_ERROR | JSON 파싱 실패 (UI 깨짐 방지) |

---

## 5. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-10 | 초기 버전 (Phase C-P.30) |
