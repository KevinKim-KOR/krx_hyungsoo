# Phase C-P.8: Allowlist Contract & Enforcement

**Date**: 2026-01-03
**Status**: ✅ 완료

---

## 📋 목표

- **Immutable Allowlist**: `docs/contracts/`에 고정 저장, 런타임 수정 금지
- **Exact Match**: 명령어/출력 경로 완전 일치만 허용
- **SHADOW_BLOCKED**: 위반 시 차단 기록

---

## 📁 생성된 문서/파일

| 타입 | 경로 |
|------|------|
| Contract | `docs/contracts/contract_real_execution_allowlist_v1.md` |
| JSON SoT | `docs/contracts/execution_allowlist_v1.json` |

---

## 📄 Allowlist 구조

```json
{
  "allowed_request_types": ["REQUEST_RECONCILE", "REQUEST_REPORTS"],
  "rules": {
    "REQUEST_RECONCILE": {
      "real_command_allowlist": [["python", "-m", "app.reconcile"]],
      "expected_outputs_allowlist": ["reports/phase_c/latest/recon_summary.json"]
    }
  }
}
```

---

## ✅ 검증 결과

| 케이스 | Ticket Type | Decision | Violations |
|--------|-------------|----------|------------|
| OK | REQUEST_RECONCILE | ✅ SHADOW_OK | None |
| BLOCKED | ACKNOWLEDGE | ❌ SHADOW_BLOCKED | "not in allowed_request_types" |

---

## 🚀 다음 단계

**C-P.9**: REAL_ENABLED 부분 오픈 (REQUEST_REPORTS부터)
