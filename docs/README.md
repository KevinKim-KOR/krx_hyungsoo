# 📚 KRX Alertor Modular - Documentation

**System Version**: 10.1 (P204-STEP1-INFRA-V1)
**Last Update**: 2026-03-22

---

## 📂 폴더 네비게이션

| 폴더 | 내용 |
|------|------|
| [contracts/](contracts/) | 스키마/계약 정의 (Immutable) |
| [ops/](ops/) | 운영 문서, 거버넌스, 체크리스트 |
| [archive/](archive/) | 프로젝트 히스토리, 완료 리포트 |

---

## 🔗 주요 문서

### 📋 운영 (ops/ & runbooks/)
| 문서 | 설명 |
|------|------|
| [artifact_governance.md](ops/artifact_governance.md) | 파일/버전 거버넌스 규칙 |
| [active_surface.json](ops/active_surface.json) | 운영 파일 화이트리스트 |
| [smoke_test.md](ops/smoke_test.md) | 시스템 검증 체크리스트 |
| [OCI_EVIDENCE_RESOLVER_GUIDE_V1.md](OCI_EVIDENCE_RESOLVER_GUIDE_V1.md) | OCI 운영자 대시보드(Evidence Resolver) 공식 가이드 |
| [runbook_ui_daily_ops_v1.md](runbooks/runbook_ui_daily_ops_v1.md) | PC Cockpit UI V1.7 (5-Step) 데일리 운영 가이드 |

### 📝 계약 (contracts/)
| 문서 | 설명 |
|------|------|
| [contracts_index.md](contracts/contracts_index.md) | Contract 목록 인덱스 |
| [contract_5_reports.md](contracts/contract_5_reports.md) | Human/AI Report 스키마 |

### 📊 히스토리 (archive/)
| 문서 | 설명 |
|------|------|
| [phase_c_s0_artifact_governance.md](archive/phase_c_s0_artifact_governance.md) | Phase C-S.0 성과 요약 |

---

## 🎯 Quick Start

### 1. 거버넌스 확인
```bash
python app/lint_active_surface.py
```

### 2. Backend 실행
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. API 확인
- `/api/recon/summary` - Reconciliation 요약
- `/api/recon/daily` - 일별 상세
- `/api/report/human` - Human Report
- `/api/report/ai` - AI Report

---

## 📜 규칙

1. **Active Surface 변경 시**: `active_surface.json` 업데이트 + lint PASS 필수
2. **버전 관리**: 파일명에 버전 금지, `docs/contracts/`에서만 관리
3. **Archive 참조 금지**: `_archive/`에서 import/의존 금지
