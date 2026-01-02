# Artifact Governance (Phase C-S.0)

**Version**: 1.0  
**Date**: 2026-01-03  
**Status**: LOCKED

---

## Active Surface 정의

Active Surface란 **운영 환경에서 실제로 소비/생성되는 파일 집합**을 말합니다.

- 운영 파일 목록: `docs/ops/active_surface.json`
- Active Surface에 없는 파일은 **"존재해도 없는 것"** 취급
- 변경 시 반드시 `active_surface.json` 업데이트 + lint PASS 필요

---

## Artifact Class 정의

| Class | 경로 | 용도 | 변경 빈도 |
|-------|------|------|-----------|
| **contracts** | `docs/contracts/` | 스키마/계약 정의 | Immutable (버전업만) |
| **ops** | `docs/ops/` | 운영 문서/레지스트리 | 낮음 |
| **reports** | `reports/phase_c/latest/` | 산출물 (UI 소비) | 매일 |
| **snapshots** | `reports/phase_c/snapshots/` | 증거/재현용 | 매일 |
| **archive** | `_archive/` | 레거시 격리 | 변경 금지 |

---

## Naming/Version 규칙

### 핵심 원칙
> **버전은 파일명이 아닌 스키마 내부(`schema.version`)로만 관리**

### 금지 사항
```
❌ reports/phase_c/latest/report_human_v1.json
❌ reports/phase_c/latest/recon_summary_V2.json
❌ reports/phase_c/latest/report_ai_v3_final.json
```

### 허용 사항
```
✅ reports/phase_c/latest/report_human.json  (내부에 schema: REPORT_HUMAN_V1)
✅ docs/contracts/contract_5_reports.md      (버전 변경 시 문서 업데이트)
```

---

## Reports 규칙

### `latest/` 폴더 (고정 파일명 4개만)

| 파일명 | 스키마 | 소비 주체 |
|--------|--------|-----------|
| `recon_summary.json` | RECON_SUMMARY_V1 | Backend, UI |
| `recon_daily.jsonl` | RECON_DAILY_V1 | Backend, UI |
| `report_human.json` | REPORT_HUMAN_V1 | UI (Dashboard) |
| `report_ai.json` | REPORT_AI_V1 | AI Agent |

### `snapshots/` 폴더 (시간별 스냅샷)

```
reports/phase_c/snapshots/YYYYMMDD_HHMM/
├── recon_summary.json
├── recon_daily.jsonl
├── report_human.json
├── report_ai.json
└── meta.json
```

---

## Deprecation/정리 정책

### Snapshots 유지 정책
- **기본 규칙**: 최근 30일 또는 30개 스냅샷 유지
- **삭제 실행**: 수동 검토 후에만 (자동 삭제 금지)

### Archive 정책
- `_archive/`는 참조 전용 (import/의존 금지)

---

## Change Control (Active Surface 변경 절차)

1. `docs/ops/active_surface.json` 업데이트
2. `app/lint_active_surface.py` 실행 → PASS
3. 변경 사유 커밋 메시지에 명시
