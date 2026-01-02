# Reports Directory (`reports/`)

**Last Updated**: 2026-01-01
**Purpose**: 시스템 산출물 저장소 (레포트, 신호, 검증 결과)

---

## 📊 Folder Usage Summary

| Folder | Status | Description |
|--------|--------|-------------|
| `phase_c/` | ✅ **ACTIVE** | Phase C Reconciler 산출물 (**SSOT**) |
| `paper/` | ✅ **ACTIVE** | Paper Trading 결과 |
| `validation/` | ✅ **ACTIVE** | OOS 검증 리포트 |
| `recon/` | ✅ **ACTIVE** | Reconciliation 베이스라인 |
| `archive/` | ⚠️ **ARCHIVE** | 아카이브된 레포트 |
| `tuning/` | ⚠️ **LOW** | 튜닝 결과 |

---

## 📁 주요 하위 폴더

### `reports/phase_c/` - ✅ ACTIVE (Contract 5)
| File | Status | Description |
|------|--------|-------------|
| `recon_summary.json` | ✅ | Reconciler 요약 |
| `recon_daily.jsonl` | ✅ | Reconciler 일별 상세 |
| `report_human_v1.json` | ✅ | Human Report (Dashboard) |
| `report_ai_v1.json` | ✅ | AI Report (Agent Context) |

### `reports/paper/` - ✅ ACTIVE
Paper Trading 결과 JSON 파일

### `reports/validation/` - ✅ ACTIVE
OOS 검증 리포트

---

## 📄 Root Files
| File | Status | Description |
|------|--------|-------------|
| `signals_YYYYMMDD.yaml` | ✅ ACTIVE | 일별 매매 신호 |

---

## ⚠️ Contract 5 산출물
`reports/phase_c/` 폴더에는 Sealed 레포트가 저장됩니다:
- `report_human_v1.json` (Dashboard UI용)
- `report_ai_v1.json` (AI Agent용)

**스키마가 고정되어 있으며 직접 수정하지 마세요.**
