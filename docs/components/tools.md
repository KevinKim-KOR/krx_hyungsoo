# Tools Module (`tools/`)

**Last Updated**: 2026-01-01
**Purpose**: 운영/분석/검증용 CLI 스크립트 모음

---

## 📊 Script Usage Summary

| File | Status | Used By |
|------|--------|---------|
| `reconcile_phase_c.py` | ✅ **ACTIVE** | run_reconciler_pipeline, generate_contract5_reports |
| `run_reconciler_pipeline.py` | ✅ **ACTIVE** | 수동 실행 |
| `generate_contract5_reports.py` | ✅ **ACTIVE** | 수동 실행 |
| `gatekeeper.py` | ✅ **ACTIVE** | 문서 참조, 수동 실행 |
| `paper_trade_phase9.py` | ✅ **ACTIVE** | deploy/run_daily.sh, deploy/run_daily.ps1 |
| `verify_contract5_api.py` | ✅ **ACTIVE** | 검증용 |
| `diagnose_oos_reasons.py` | ✅ **ACTIVE** | 분석용 |
| `run_phase15_realdata.py` | ⚠️ **LOW** | 개발 단계 사용 |
| `run_phase20_real_gate2.py` | ⚠️ **LOW** | 개발 단계 사용 |
| `run_phase30_final.py` | ⚠️ **LOW** | 개발 단계 사용 |
| `run_phase9_diag.py` | ⚠️ **LOW** | 진단용 |
| 기타 | ⚠️ | 개별 확인 필요 |

---

## 📁 스크립트 분류

### 🔄 Reconciler & Reports - ✅ ACTIVE
| File | Status | Description |
|------|--------|-------------|
| `reconcile_phase_c.py` | ✅ | Phase C Reconciler (recon_daily.jsonl, recon_summary.json) |
| `run_reconciler_pipeline.py` | ✅ | Determinism 검증 및 Report 생성 파이프라인 |
| `generate_contract5_reports.py` | ✅ | Contract 5 Human/AI 레포트 생성기 |

### 🚦 Gatekeeper - ✅ ACTIVE
| File | Status | Description |
|------|--------|-------------|
| `gatekeeper.py` | ✅ | Gatekeeper Decision V3 생성 (Production Approval) |

### 📊 Phase Execution - ⚠️ DEVELOPMENT
| File | Status | Description |
|------|--------|-------------|
| `run_phase15_realdata.py` | ⚠️ | Phase 15 실제 데이터 백테스트 (개발용) |
| `run_phase20_real_gate2.py` | ⚠️ | Phase 20 Gate 2 검증 (개발용) |
| `run_phase30_final.py` | ⚠️ | Phase 30 최종 실행기 (개발용) |
| `run_phase9_diag.py` | ⚠️ | Phase 9 진단 스크립트 |
| `paper_trade_phase9.py` | ✅ | Phase 9 모의 거래 실행기 (**배포 스크립트에서 사용**) |

### 🔍 Diagnosis & Analysis - ✅ ACTIVE
| File | Status | Description |
|------|--------|-------------|
| `diagnose_market.py` | ⚠️ | 시장 상태 진단 |
| `diagnose_oos_reasons.py` | ✅ | OOS 검증 실패 원인 분석 |
| `diagnose_oos_reasons_draft.py` | ❌ | 초안 (**삭제 검토**) |
| `debug_alpha_autopsy.py` | ⚠️ | 알파 부검 (성과 분석) |
| `debug_core_logic.py` | ⚠️ | 코어 로직 디버깅 |
| `analyze_coverage_gap.py` | ✅ | 커버리지 갭 분석 |
| `analyze_missing_data.py` | ✅ | 누락 데이터 분석 |

### ✅ Verification - ✅ ACTIVE
| File | Status | Description |
|------|--------|-------------|
| `verify_contract5_api.py` | ✅ | Contract 5 API 검증 |
| `verify_oos_2024_2025.py` | ✅ | 2024-2025 OOS 검증 |
| `verify_paper_logic.py` | ✅ | Paper Trading 로직 검증 |
| `verify_mock_multilookback.py` | ⚠️ | Multi-Lookback Mock 검증 |

### 🛠️ Utilities - ⚠️ MIXED
| File | Status | Description |
|------|--------|-------------|
| `cat_log.py` | ⚠️ | 로그 파일 출력 (간단) |
| `convert_docs_encoding.py` | ⚠️ | 문서 인코딩 변환 (일회성) |
| `export_trials.py` | ⚠️ | Optuna Trial 내보내기 |
| `patch_dashboard.py` | ❌ | Dashboard 패치 (**완료됨, 삭제 검토**) |
| `patch_evidence_2025.py` | ❌ | 2025 Evidence 패치 (**완료됨, 삭제 검토**) |
| `replay_manifest.py` | ⚠️ | Manifest 리플레이 |

---

## 🚀 주요 실행 예시

### Reconciler 파이프라인 - ✅ ACTIVE
```bash
python tools/run_reconciler_pipeline.py
```

### Contract 5 레포트 생성 - ✅ ACTIVE
```bash
python tools/generate_contract5_reports.py
```

### Phase 9 Paper Trade - ✅ ACTIVE
```bash
python tools/paper_trade_phase9.py --date auto
```

### API 검증 - ✅ ACTIVE
```bash
python tools/verify_contract5_api.py
```

---

## 📋 Output Locations
- `reports/phase_c/recon_summary.json`
- `reports/phase_c/recon_daily.jsonl`
- `reports/phase_c/report_human_v1.json`
- `reports/phase_c/report_ai_v1.json`
- `state/live/gatekeeper_decision_v3.json`

---

## 🧹 정리 권장 사항
1. ❌ `diagnose_oos_reasons_draft.py`: 삭제 검토 (초안)
2. ❌ `patch_dashboard.py`: 삭제 검토 (일회성 완료)
3. ❌ `patch_evidence_2025.py`: 삭제 검토 (일회성 완료)
4. ⚠️ `run_phase*` 시리즈: 개발용으로 `scripts/` 이동 검토
