# Scripts Module (`scripts/`)

**Last Updated**: 2026-01-01
**Purpose**: 레거시 및 유틸리티 스크립트 모음 (약 170개 파일)

---

## 📊 Status Summary

| Category | Count | Status |
|----------|-------|--------|
| 전체 파일 | ~170 | ⚠️ 정리 필요 |
| 활성 사용 | ~20 | ✅ ACTIVE |
| 개발/테스트 | ~50 | ⚠️ DEV |
| 레거시/미사용 | ~100 | ❌ DEPRECATED |

---

## ⚠️ Status
이 폴더는 대량의 레거시 스크립트를 포함하고 있습니다.
대부분 개발 단계에서 사용된 스크립트이며, 프로덕션에서는 `tools/` 폴더를 사용합니다.

---

## 📁 주요 서브폴더

| Folder | Status | Description |
|--------|--------|-------------|
| `scripts/nas/` | ✅ ACTIVE | NAS 배포용 스크립트 |
| `scripts/dev/` | ⚠️ DEV | 개발 전용 스크립트 |
| `scripts/phase4/` | ⚠️ DEV | Phase 4 개발 스크립트 |
| `scripts/archive/` | ❌ DEPRECATED | 아카이브 |
| `scripts/tests/` | ⚠️ DEV | 테스트 스크립트 |
| 기타 | ❌ | 정리 대상 |

---

## 📋 권장 사항
1. ✅ `scripts/nas/` 활성 스크립트 → 유지
2. ⚠️ 개발 스크립트 → 필요 시 `tools/`로 승격
3. ❌ 미사용 스크립트 → `_archive/`로 이동 또는 삭제

---

## 🔗 참고
주요 운영 스크립트는 `tools/` 폴더를 참조하세요.
