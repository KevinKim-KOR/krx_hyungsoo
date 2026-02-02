# Contract: Contract 5 Report V1

**Version**: 1.0 (P103)  
**Date**: 2026-02-02  
**Status**: ACTIVE

---

## 1. 개요

Daily Operations의 최종 산출물로, Ops Summary, Reco, Order Plan을 종합하여 운영자(Human)와 AI Agent에게 상황을 보고합니다.
대시보드 "Contract 5 Status"의 소스가 됩니다.

> 🔒 **Fail-Closed**: 입력 데이터 결함 시 생성은 하되 decision은 `BLOCKED`

---

## 2. Schema: CONTRACT5_REPORT_V1

```json
{
  "schema": "CONTRACT5_REPORT_V1",
  "asof": "2026-02-02T10:00:00",
  "report_id": "c5-20260202-100000",
  "decision": "OK", 
  "reason": "SUCCESS",
  "reason_detail": "All systems green",
  "inputs": {
    "ops_summary_ref": "http://localhost:8000/api/ops/summary/latest",
    "ops_asof": "2026-02-02T10:00:00",
    "reco_ref": "reports/live/reco/latest/reco_latest.json",
    "reco_asof": "2026-02-02T09:55:00",
    "reco_decision": "GENERATED",
    "order_plan_ref": "reports/live/order_plan/latest/order_plan_latest.json",
    "order_plan_asof": "2026-02-02T09:57:00",
    "order_plan_decision": "COMPLETED",
    "bundle_id": "uuid-bundle",
    "bundle_created_at": "2026-02-02T09:00:00",
    "payload_sha256": "sha256"
  },
  "content": {
    "human": "Markdown text summary...",
    "ai": {
       "summary": "Short summary",
       "key_metrics": {"...":"..."},
       "alerts": []
    }
  },
  "evidence_refs": [
    "reports/live/reco/latest/reco_latest.json",
    "reports/live/order_plan/latest/order_plan_latest.json"
  ],
  "error_summary": null
}
```

---

## 3. 필드 정의

| 필드 | 타입 | 설명 |
|------|------|------|
| `schema` | string | `CONTRACT5_REPORT_V1` |
| `decision` | enum | `OK` / `WARN` / `BLOCKED` / `EMPTY` |
| `reason` | enum | `SUCCESS`, `INPUT_MISSING`, `INPUT_BLOCKED`, `GEN_FAIL` |
| `inputs` | object | 입력 소스 메타데이터 |
| `content` | object | human(md), ai(json) |

### inputs
- Ops Summary, Reco, Order Plan의 Ref 및 주요 상태

### content
- `human`: Markdown 포맷의 가독성 높은 요약. (10~30줄)
- `ai`: AI Agent가 파싱하기 쉬운 구조화된 데이터.

---

## 4. API & 저장소

### API
- `GET /api/contract5/latest`
- `POST /api/contract5/regenerate?confirm=true`

### 저장 경로 (SSOT)
- Human JSON (Dashboard용): `reports/phase_c/latest/report_human.json` (Overwrite)
- AI JSON: `reports/ops/contract5/latest/ai_report_latest.json`
- Human Markdown: `reports/ops/contract5/latest/human_report_latest.md`

---

## 5. Decision 규칙

| 상황 | Decision | Reason |
|------|----------|--------|
| 모든 입력 정상, Order Plan 등 생성 완료 | `OK` | `SUCCESS` |
| 입력 중 하나라도 Missing | `BLOCKED` | `INPUT_MISSING` |
| 입력 중 하나라도 WARN/BLOCKED | `WARN` / `BLOCKED` | `INPUT_BLOCKED` |
| Reco Empty 등 정상적 Empty | `EMPTY` | `SUCCESS_EMPTY` |

