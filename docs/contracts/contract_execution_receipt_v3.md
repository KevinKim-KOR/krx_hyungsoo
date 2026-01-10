# Contract: Execution Receipt V3

**Version**: 1.0
**Date**: 2026-01-03
**Status**: LOCKED

---

## 1. 개요

REAL 실행 완료 판정을 **mtime 기반(changed)**에서 **sha256 해시 기반(verified)**으로 전환합니다.

> 🔒 **핵심 원칙**: "바뀌었냐?"가 아니라 **"일치/검증됐냐?"**로 판정

---

## 2. 스키마 정의

### EXECUTION_RECEIPT_V3

```json
{
  "schema": "EXECUTION_RECEIPT_V3",
  "asof": "ISO datetime",
  "request_id": "uuid",
  "request_type": "REQUEST_RECONCILE | REQUEST_REPORTS",
  "mode": "MOCK_ONLY | DRY_RUN | REAL",
  "decision": "EXECUTED | FAILED | BLOCKED",
  "exit_code": 0,
  "outputs_proof": {
    "latest_dir": "reports/phase_c/latest/",
    "targets": [
      {
        "path": "reports/phase_c/latest/recon_summary.json",
        "before": {"exists": true, "mtime_iso": "...", "size_bytes": 123, "sha256": "abc..."},
        "after": {"exists": true, "mtime_iso": "...", "size_bytes": 123, "sha256": "abc..."},
        "changed": false,
        "verified": true
      }
    ]
  },
  "acceptance": {
    "pass": true,
    "reason": "CHANGED_VERIFIED | UNCHANGED_BUT_HASH_MATCH_VERIFIED | FAILED_EXIT_CODE | MISSING_OUTPUTS"
  },
  "evidence_refs": [
    "reports/ops/evidence/index/evidence_index_latest.json",
    "reports/phase_c/latest/recon_summary.json"
  ]
}
```

> 🔒 **evidence_refs 규칙**
> - Raw Path Only (접두어 금지: `json:`, `file://` 등)
> - `reports/ops/evidence/index/evidence_index_latest.json`는 항상 포함 (존재 시)
> - 해당 실행과 직접 관련된 ref 1개 이상 포함 (존재 시)

---

## 3. 필수 Targets (고정, 순서 고정)

| # | Path |
|---|------|
| 1 | `reports/phase_c/latest/recon_summary.json` |
| 2 | `reports/phase_c/latest/recon_daily.jsonl` |
| 3 | `reports/phase_c/latest/report_human.json` |
| 4 | `reports/phase_c/latest/report_ai.json` |

---

## 4. 스냅샷 구조

```json
{
  "exists": true,
  "mtime_iso": "2026-01-03T21:00:00",
  "size_bytes": 1234,
  "sha256": "a1b2c3d4e5..."
}
```

- **exists=false**: 파일 없음 → mtime/size/sha256 모두 null

---

## 5. 판정 규칙

### 5-A. changed 계산

```
changed = (before.mtime != after.mtime) OR 
          (before.size_bytes != after.size_bytes) OR 
          (before.sha256 != after.sha256)
```

### 5-B. verified 계산 (핵심)

```
IF after.exists == false OR after.sha256 == null:
    verified = false

ELSE IF changed == true:
    verified = true  # 실행으로 산출물 갱신이 증명됨

ELSE:  # changed == false
    verified = (before.sha256 == after.sha256 AND before.sha256 != null)
    # 안 바뀌었지만 동일 해시로 재검증됨
```

### 5-C. acceptance 계산

```
acceptance.pass = (exit_code == 0) AND (all 4 targets verified == true)

acceptance.reason:
- CHANGED_VERIFIED: 4개 중 1개 이상 changed=true, 모두 verified
- UNCHANGED_BUT_HASH_MATCH_VERIFIED: 4개 모두 changed=false, 모두 verified  
- FAILED_EXIT_CODE: exit_code != 0
- MISSING_OUTPUTS: 4개 중 1개 이상 verified=false
```

---

## 6. 스냅샷 순서 (불변)

```
1. BEFORE 스냅샷: REAL 실행 직전
2. REAL 실행 수행
3. AFTER 스냅샷: REAL 실행 직후
4. changed/verified/acceptance 계산
```

---

## 7. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-03 | 초기 버전 (Phase C-P.10.1) |
