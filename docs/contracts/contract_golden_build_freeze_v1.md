# Contract: Golden Build Freeze V1

**Version**: 1.0
**Date**: 2026-01-11
**Status**: LOCKED

---

## 1. 개요

C-P.37.1 PASS 상태를 Golden Build로 동결하고, 이후 변경을 Manifest/Tag 기준으로 추적 가능하게 만드는 계약입니다.

> 🔒 **No Feature Add**: 동결 이후 기능 추가 금지
> 
> 🔒 **No New Runtime Paths**: 새 런타임 경로 추가 금지
> 
> 🔒 **No Secrets Commit**: .env 등 Git 포함 시 즉시 FAIL

---

## 2. Freeze 대상 (Immutable)

동결 대상은 변경 시 반드시 새 버전 릴리스가 필요합니다.

### 2-A. Contracts
| 경로 | 설명 |
|------|------|
| `docs/contracts/*.md` | 모든 계약 문서 |
| `docs/ops/active_surface.json` | Active Surface Registry |

### 2-B. Core Validators/Formatters
| 경로 | 설명 |
|------|------|
| `app/utils/ref_validator.py` | Evidence Ref Validator |
| `app/utils/formatter.py` | 메시지 포매터 (있을 경우) |

### 2-C. Ops 실행기
| 경로 | 설명 |
|------|------|
| `app/run_ops_cycle.py` | Ops Cycle Runner |
| `app/run_ops_drill.py` | Ops Drill Runner |
| `app/run_evidence_health_check.py` | Evidence Health Checker |
| `app/generate_ops_summary.py` | Ops Summary Generator |

### 2-D. Backend 보안 엔드포인트
| 엔드포인트 | 설명 |
|------------|------|
| `/api/evidence/resolve` | Evidence Resolver |
| `/api/ops/cycle/run` | Ops Cycle Trigger |
| `/api/ops/drill/run` | Ops Drill Trigger |

---

## 3. Safe Defaults

| 설정 | 기본값 | 위치 |
|------|--------|------|
| `sender_enable` | `false` | `state/real_sender_enable.json` |
| `emergency_stop.enabled` | `false` | `state/emergency_stop.json` |
| `execution_gate.mode` | `"MOCK_ONLY"` | `state/execution_gate.json` |

> ⚠️ **WARNING**: 실제 발송을 위해서는 명시적으로 `sender_enable=true` + `gate.mode="REAL"` 설정이 필요합니다.

---

## 4. Release 절차

### 4-A. Pre-Release Checklist
1. `python -m app.lint_active_surface` → PASS
2. `POST /api/ops/drill/run` → `overall_result: PASS`
3. `.env` Git 상태 확인 (포함 시 FAIL)

### 4-B. Release Steps
1. **Manifest 업데이트**: `docs/ops/release_manifest_golden_v1.json`
   - `active_surface.sha256` 계산 및 포함
   - `commit_sha` 현재 HEAD로 갱신
2. **Tag 생성**: `git tag -a v1.x.x-description -m "..."` 
3. **Runbook 이력**: `docs/ops/runbook.md`에 릴리스 기록
4. **Push**: `git push origin <branch> && git push origin <tag>`

---

## 5. 변경 추적

| 항목 | 방법 |
|------|------|
| active_surface 변조 탐지 | Manifest의 `sha256`과 현재 파일 해시 비교 |
| 버전 이력 | Git tags (`v1.0-golden`, etc.) |
| 변경 사유 | Commit message + Manifest 갱신 |

---

## 6. 버전 히스토리

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| 1.0 | 2026-01-11 | 초기 버전 (Phase C-P.38) |
