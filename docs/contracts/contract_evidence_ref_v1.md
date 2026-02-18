# Contract: Evidence Ref V1

**Version**: 1.1 (Expanded Allowlist & Viewer Rules)
**Date**: 2026-02-18
**Status**: ACTIVE

---

## 1. 개요

증거(Evidence) 파일의 경로 검증 및 읽기 규칙을 정의합니다.
P146에서 `latest/` 디렉토리 지원 및 비-JSON 파일(MD/TXT) 처리가 강화되었습니다.

---

## 2. Ref 타입 및 패턴 (Allowlist)

### 2.1 JSONL Line Refs
- **Pattern**: `state/{kind}/{filename}.jsonl:line{N}`
- **Allowlist**:
  - `state/tickets/ticket_receipts.jsonl`
  - `state/tickets/ticket_results.jsonl`
  - `state/push/send_receipts.jsonl`

### 2.2 Artifact Latest Refs (JSON)
- **Pattern**: `reports/{category}/{module}/latest/{filename}_latest.json`
- **Allowlist**:
  - `reports/live/**/latest/*_latest.json` (Reco, OrderPlan, Export, Ticket)
  - `reports/ops/summary/latest/ops_summary_latest.json`
  - `reports/ops/evidence/**/latest/*_latest.json`
  - `reports/tuning/latest/*_latest.json`

### 2.3 Raw Text Refs (MD/KV/CSV)
- **Pattern**: `reports/**/latest/*.{md,txt,csv,kv}`
- **Allowlist**:
  - `reports/live/ticket/latest/ticket_latest.md` (Human Readable Ticket)
  - `reports/live/export/latest/export_latest.kv`

---

## 3. Viewer Rules (Resolver Logic)

파일 확장자에 따라 읽기 방식이 달라집니다.

| 확장자 | 처리 방식 | 에러 처리 (Fail-Soft) |
|---|---|---|
| `.json` | `json.loads()` 수행 | 파싱 실패 시 `raw_preview` (텍스트 앞부분) 반환. **500 에러 아님.** |
| `.jsonl` | 특정 라인만 `json.loads()` | 라인 없음(404) |
| `.md` / `.txt` | 전체 텍스트 읽기 (`read_text`) | - |
| `.csv` / `.kv` | 전체 텍스트 읽기 | - |

---

## 4. API Response (Unified)

### GET /api/evidence/resolve

```json
{
  "status": "ready",
  "ref": "reports/live/ticket/latest/ticket_latest.md",
  "mime_type": "text/markdown",
  "content": "# Ticket Target ...", 
  "error": null
}
```

**JSON Parse Error (Fail-Soft) 예시**:
```json
{
  "status": "partial_error",
  "mime_type": "application/json",
  "content": null,
  "raw_preview": "{ \"broken_json\": ... (truncated)",
  "error": "JSON_PARSE_ERROR"
}
```

---

## 5. Security (Path Traversal)

1. **Root Jail**: 모든 경로는 프로젝트 루트 내부여야 함.
2. **No Traversal**: `..` 포함 시 즉시 400.
3. **Canonical Path**: `os.path.abspath`로 정규화 후 검증.
