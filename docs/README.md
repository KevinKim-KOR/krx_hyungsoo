# 📚 KRX Alertor Modular - Documentation

**System Version**: 9.0 (Crisis Alpha Strategy)  
**Last Update**: 2025-12-29

---

## 🧭 Introduction

KRX Alertor Modular System은 한국 주식 시장(KRX)을 대상으로 한 퀀트 트레이딩/알림 시스템입니다.
본 문서는 시스템의 설계, 운영, 유지보수, 그리고 확장을 위한 포괄적인 가이드를 제공합니다.

### 🚀 Quick Links
*   **[System Architecture](design/architecture.md)**: 시스템의 전체적인 구조와 흐름.
*   **[Component Detail](design/components/01_core.md)**: 각 모듈별 상세 분석.
*   **[Backtest Guide](guides/backtest.md)**: 백테스트 실행 및 검증 방법.
*   **[Cleanup Guide](guides/maintainer_cleanup_guide.md)**: **(New)** 프로젝트 정리 및 유지보수 가이드.

---

## 📂 Documentation Structure

문서는 다음과 같이 구성되어 있습니다.

### 1. 🎨 Design & Architecture (`docs/design/`)
시스템의 설계 철학과 세부 구현 명세입니다.

*   **[Architecture](design/architecture.md)**: High-level 아키텍처 및 데이터 흐름.
*   **Components Analysis** (현재 코드베이스 상태를 반영한 상세 분석):
    *   [`01_core.md`](design/components/01_core.md): 핵심 비즈니스 로직 (Engine, Strategy, Risk).
    *   [`02_web.md`](design/components/02_web.md): (Legacy) Web Dashboard & API.
    *   [`03_app_api.md`](design/components/03_app_api.md): Application & Services.
    *   [`04_apps_extensions.md`](design/components/04_apps_extensions.md): PC CLI, Backend, Automation Extensions.
    *   [`05_tools.md`](design/components/05_tools.md): 운영 및 유틸리티 스크립트.
    *   [`06_infra_config.md`](design/components/06_infra_config.md): 설정 및 인프라 어댑터.

### 2. 📖 User & Operator Guides (`docs/guides/`)
사용자 및 운영자를 위한 매뉴얼입니다.

*   **Simulation**: [`backtest.md`](guides/backtest.md), [`optuna.md`](guides/optuna.md)
*   **Operation**: [`alert-system.md`](guides/alert-system.md), [`portfolio-manager.md`](guides/portfolio-manager.md)
*   **Maintenance**: [`maintainer_cleanup_guide.md`](guides/maintainer_cleanup_guide.md) **(Maintenance Priority)**

### 3. 🔧 Tuning System (`docs/tuning/`)
Phase 9 전략 최적화를 위한 튜닝 시스템 전용 문서입니다.

*   [`00_overview.md`](tuning/00_overview.md) ~ [`05_development_history.md`](tuning/05_development_history.md)

### 4. 🚀 Deployment (`docs/deployment/`)
배포 환경별 가이드입니다.

*   [`oracle_cloud_guide.md`](deployment/oracle_cloud_guide.md): Oracle Cloud 배포.
*   [`nas.md`](deployment/nas.md): Synology NAS 배포 (Legacy support).

### 5. 📋 Plans & Archive (`docs/plans/`, `docs/archive/`)
*   `plans/`: 향후 개발 계획 (`future_work.md`).
*   `archive/`: 과거 문서 및 로그.

---

## 🛠 Project Status (as of 2025-12-29)

### ✅ Active Phaes
*   **Phase 9 (Crisis Alpha)**: 시장 하락 시 방어 및 알림 기능 (운영 중).
*   **Tuning System**: Optuna 연동 파라미터 최적화 (완료).

### 🚧 Maintenance Required
*   **Backend Consolidation**: `web/` (Legacy FastAPI)와 `backend/` (Modern FastAPI)의 통합 필요.
*   **Code Cleanup**: `tools/` 및 `scripts/` 내 미사용 파일/폴더 정리 필요 (Ref: [`maintainer_cleanup_guide.md`](guides/maintainer_cleanup_guide.md)).
*   **DB Consistency**: Hardcoded DB paths in `core/db.py` need refactoring.

---

## 📞 Support
시스템 관련 문의나 버그 제보는 GitHub Issue Tracker를 이용해주세요.
개발에 참여시 `AI_CONTEXT_PACK.md`를 반드시 먼저 숙지하시기 바랍니다.
