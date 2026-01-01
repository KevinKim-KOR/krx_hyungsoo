# 사용/미사용 함수 요약 (Usage Summary)

**Last Updated**: 2026-01-02
**Purpose**: 프로젝트 전체 파일/함수 사용 현황 종합

---

## 📊 Status Legend

| Icon | Status | 설명 |
|------|--------|------|
| ✅ | **ACTIVE** | 현재 적극 사용 중 |
| ⚠️ | **LOW** | 사용 빈도 낮음 |
| 📦 | **ARCHIVED** | `_archive/`로 이동됨 |

---

## ✅ 정리 완료 (2026-01-02)

### 📦 `_archive/deprecated_code/`로 이동됨
- `core/adaptive.py`
- `core/cache_store.py`
- `core/notifications.py`
- `tools/diagnose_oos_reasons_draft.py`
- `tools/patch_dashboard.py`
- `tools/patch_evidence_2025.py`
- `extensions/ui_archive/` (14 files)

### 🗑️ 삭제됨
- `docs/archive/` (레거시 문서 135개)
- `logs/archive/` (이전 로그)
- Root level: `error.log`, `error_log.txt`, `diag_log.txt`

---

## 📁 Core Module (`core/`) - ✅ Active Only

| File | Status | 참조 수 |
|------|--------|---------|
| `data_loader.py` | ✅ ACTIVE | 12+ |
| `indicators.py` | ✅ ACTIVE | 6 |
| `fetchers.py` | ✅ ACTIVE | 4 |
| `calendar_kr.py` | ✅ ACTIVE | 4 |
| `db.py` | ✅ ACTIVE | 21+ |

---

## 📁 Backend Module (`backend/`) - ✅ Active

| Endpoint | Status |
|----------|--------|
| `/api/status` | ✅ |
| `/api/portfolio` | ✅ |
| `/api/signals` | ✅ |
| `/api/report/human` | ✅ |
| `/api/report/ai` | ✅ |
| `/api/recon/*` | ✅ |

---

## 📁 Tools Module (`tools/`) - ✅ Cleaned

| Category | Active |
|----------|--------|
| Reconciler & Reports | 3 |
| Gatekeeper | 1 |
| Phase Execution | 5 |
| Diagnosis | 4 |
| Verification | 4 |

---

## 📁 Extensions Module (`extensions/`) - ✅ Cleaned

| Subdir | Status |
|--------|--------|
| `automation/` | ✅ ACTIVE |
| `backtest/` | ✅ ACTIVE |
| `optuna/` | ✅ ACTIVE |
| `tuning/` | ✅ ACTIVE |
| `monitoring/` | ⚠️ LOW |
| `notification/` | ⚠️ LOW |
| `realtime/` | ⚠️ LOW |
| `strategy/` | ⚠️ LOW |

---

## 📋 남은 작업
1. ⚠️ LOW 사용 extensions 정리 검토
2. 파일명/함수명 정책 적용
