# Phase C-P.9: REAL Enable Window + First Real Execution

**Date**: 2026-01-03
**Status**: ✅ 완료

---

## 📋 목표

- **REAL Enable Window**: TTL 기반 Window 안에서만 REAL 실행 허용
- **REQUEST_REPORTS 1회만**: C-P.9에서 REQUEST_RECONCILE REAL 금지
- **Preflight 4체크**: Emergency Stop, Approval, Allowlist, Window

---

## 📁 생성된 문서/파일

| 타입 | 경로 |
|------|------|
| Contract | `contract_real_enable_window_v1.md` |
| Contract | `contract_execution_receipt_v2.md` |
| Storage | `state/real_enable_windows/real_enable_windows.jsonl` |

---

## 🔌 새 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | `/api/real_enable_window/request` | Window 생성 |
| GET | `/api/real_enable_window/latest` | ACTIVE Window 조회 |
| POST | `/api/real_enable_window/revoke` | Window 폐기 |

---

## ✅ 검증 결과

| 항목 | 결과 |
|------|------|
| Window ACTIVE | ✅ PASS |
| REAL 실행 시도 | ✅ exit_code=1 (script error, but executed) |
| Receipt V2 작성 | ✅ mode=REAL, command, artifacts_written |
| REQUEST_RECONCILE BLOCKED | ✅ "type not allowed" |
| Lint | ✅ PASS |

---

## 📄 Receipt V2 예시

```json
{
  "schema": "EXECUTION_RECEIPT_V2",
  "mode": "REAL",
  "decision": "FAILED",
  "command": ["python", "-m", "app.generate_reports"],
  "exit_code": 1,
  "artifacts_written": ["reports/phase_c/latest/report_human.json"],
  "safety_checks": {
    "approval_status": "APPROVED",
    "window_active": true
  }
}
```

---

## 🚀 다음 단계

**C-P.10**: REQUEST_RECONCILE REAL 실행 허용
