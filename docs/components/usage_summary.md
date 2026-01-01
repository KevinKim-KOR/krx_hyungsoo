# 사용/미사용 함수 요약 (Usage Summary)

**Last Updated**: 2026-01-01
**Purpose**: 프로젝트 전체 파일/함수 사용 현황 종합

---

## 📊 Status Legend

| Icon | Status | 설명 |
|------|--------|------|
| ✅ | **ACTIVE** | 현재 적극 사용 중 |
| ⚠️ | **LOW/UNUSED** | 사용 빈도 낮음 또는 미사용 |
| 🔶 | **LEGACY** | 레거시 코드 (마이그레이션 권장) |
| ❌ | **DEPRECATED** | 삭제 검토 대상 |

---

## 📁 Core Module (`core/`)

### 파일 수준 Summary
| File | Status | 참조 수 |
|------|--------|---------|
| `data_loader.py` | ✅ ACTIVE | 12+ |
| `indicators.py` | ✅ ACTIVE | 6 |
| `fetchers.py` | ✅ ACTIVE | 4 |
| `calendar_kr.py` | ✅ ACTIVE | 4 |
| `db.py` | ✅ ACTIVE | 21+ |
| `cache_store.py` | ⚠️ UNUSED | 0 |
| `notifications.py` | 🔶 LEGACY | 2 |
| `adaptive.py` | ❌ DEPRECATED | 1 (_archive) |

### 정리 권장
- 삭제: `adaptive.py`
- 통합/삭제: `cache_store.py`
- 마이그레이션: `notifications.py` → `infra/notify/`

---

## 📁 Backend Module (`backend/`)

### API 수준 Summary
| Endpoint | Status | 사용처 |
|----------|--------|--------|
| `/api/status` | ✅ ACTIVE | dashboard |
| `/api/portfolio` | ✅ ACTIVE | dashboard |
| `/api/signals` | ✅ ACTIVE | dashboard |
| `/api/report/human` | ✅ ACTIVE | dashboard (Contract 5) |
| `/api/report/ai` | ✅ ACTIVE | AI Agent |
| `/api/recon/*` | ✅ ACTIVE | dashboard |
| `/api/raw` | ⚠️ DEBUG | 디버깅 전용 |

### 정리 권장
- 프로덕션에서 `/api/raw` 비활성화 검토

---

## 📁 Tools Module (`tools/`)

### 스크립트 수준 Summary
| Category | Active | Low/Unused | Deprecated |
|----------|--------|------------|------------|
| Reconciler & Reports | 3 | 0 | 0 |
| Gatekeeper | 1 | 0 | 0 |
| Phase Execution | 1 | 4 | 0 |
| Diagnosis | 3 | 2 | 1 |
| Verification | 3 | 1 | 0 |
| Utilities | 2 | 2 | 2 |

### 정리 권장
- 삭제: `diagnose_oos_reasons_draft.py`, `patch_dashboard.py`, `patch_evidence_2025.py`
- 이동: `run_phase*` 시리즈 → `scripts/`

---

## 📁 Extensions Module (`extensions/`)

### 서브폴더 수준 Summary
| Subdir | Status | 참조 수 |
|--------|--------|---------|
| `automation/` | ✅ ACTIVE | 50+ |
| `backtest/` | ✅ ACTIVE | 10+ |
| `optuna/` | ✅ ACTIVE | 10+ |
| `tuning/` | ✅ ACTIVE | 12+ |
| `monitoring/` | ⚠️ LOW | 수 개 |
| `notification/` | ⚠️ LOW | 수 개 |
| `realtime/` | ⚠️ LOW | 수 개 |
| `strategy/` | ⚠️ LOW | 수 개 |
| `ui_archive/` | ❌ DEPRECATED | 0 |

### 정리 권장
- 삭제: `ui_archive/` (14 files)
- 마이그레이션: `notification/` → `infra/notify/`

---

## 📁 App Module (`app/`)

### 컴포넌트 수준 Summary
| Component | Status | 참조 수 |
|-----------|--------|---------|
| `cli/alerts.py` | ✅ ACTIVE | 배포 스크립트 |
| `cli/runner.py` | ⚠️ LOW | 확인 필요 |
| `api/` | ⚠️ LOW | backend 사용 |
| `services/` | ⚠️ LOW | 확인 필요 |

### 정리 권장
- 통합: `app/api/` → `backend/`

---

## 🧹 전체 정리 권장 사항

### 즉시 삭제 검토 (❌ DEPRECATED)
1. `core/adaptive.py`
2. `tools/diagnose_oos_reasons_draft.py`
3. `tools/patch_dashboard.py`
4. `tools/patch_evidence_2025.py`
5. `extensions/ui_archive/` (전체 폴더)

### 통합/마이그레이션 검토 (🔶 LEGACY)
1. `core/notifications.py` → `infra/notify/telegram.py`
2. `core/cache_store.py` → `core/data_loader.py` 통합
3. `app/api/` → `backend/` 통합
4. `extensions/notification/` → `infra/notify/`

### 사용 빈도 확인 필요 (⚠️ LOW)
1. `core/indicators.py` 내 저빈도 함수들 (macd, bollinger, stochastic 등)
2. `core/fetchers.py` 내 realtime 관련 함수들
3. `extensions/monitoring/`, `extensions/realtime/`, `extensions/strategy/`

---

## 📋 다음 작업
1. 위 삭제/마이그레이션 수행
2. 파일명/함수명 정책 적용
