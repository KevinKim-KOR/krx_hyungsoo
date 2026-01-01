# Dashboard Module (`dashboard/`)

**Last Updated**: 2026-01-01
**Purpose**: 웹 대시보드 UI (React SPA)

---

## 📊 File Usage Summary

| File | Status | Used By |
|------|--------|---------|
| `index.html` | ✅ **ACTIVE** | Backend 서버에서 서빙 |

---

## 📄 Files

| File | Status | Description |
|------|--------|-------------|
| `index.html` | ✅ ACTIVE | 메인 대시보드 HTML (React 앱 포함) |

---

## 🖥️ 기능
- **Status View**: 시스템 상태 모니터링 - ✅ ACTIVE
- **Portfolio View**: 포트폴리오 현황 - ✅ ACTIVE
- **Diagnosis View**: Reconciliation 결과 및 KPI - ✅ ACTIVE
- **Signals View**: 매매 신호 - ✅ ACTIVE
- **Logs View**: 로그 뷰어 - ✅ ACTIVE

---

## 📋 Contract 5 지원
- `/api/report/human`에서 Header/KPI 렌더링 - ✅ ACTIVE
- `/api/recon/daily`에서 상세 테이블 렌더링 - ✅ ACTIVE
- Stop Screen: `status != ready` 시 차단 - ✅ ACTIVE

---

## 🚀 실행
Backend 서버 실행 후 `http://localhost:8000` 접속
