# Data Directory (`data/`)

**Last Updated**: 2026-01-01
**Purpose**: 데이터 저장소 (시세, 캐시, DB)

---

## 📊 Folder Usage Summary

| Folder/File | Status | Description |
|-------------|--------|-------------|
| `data/cache/kr/` | ✅ **ACTIVE** | 한국 주식 OHLCV 캐시 |
| `data/cache/ohlcv/` | ✅ **ACTIVE** | 일반 OHLCV 캐시 |
| `data/evidence/` | ✅ **ACTIVE** | 백테스트 Evidence (Parquet) - **SSOT** |
| `data/ledgers/` | ✅ **ACTIVE** | 거래 원장 (Parquet) - **SSOT** |
| `krx_alertor.db` | ✅ **ACTIVE** | SQLite 데이터베이스 |

---

## 📁 주요 하위 폴더

| Folder | Status | Description |
|--------|--------|-------------|
| `cache/` | ✅ ACTIVE | OHLCV 캐시 (Pickle) |
| `cache/kr/` | ✅ ACTIVE | 한국 주식 캐시 |
| `cache/ohlcv/` | ✅ ACTIVE | 일반 OHLCV 캐시 |
| `evidence/` | ✅ ACTIVE | 백테스트 Evidence 데이터 |
| `ledgers/` | ✅ ACTIVE | 거래 원장 (Parquet) |

---

## 📄 Root Files

| File | Status | Description |
|------|--------|-------------|
| `krx_alertor.db` | ✅ ACTIVE | SQLite 데이터베이스 |

---

## ⚠️ 데이터 정책
- 원본 데이터는 **수정 금지**
- 캐시 파일은 자동 갱신됨
- `evidence/`, `ledgers/`는 Reconciler의 **SSOT (Source of Truth)**
