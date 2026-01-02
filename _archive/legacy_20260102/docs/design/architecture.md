# System Architecture (v3)

**Last Update**: 2025-12-29

## 1. High-Level Overview

KRX Alertor Modular 시스템은 **Clean Architecture** 원칙을 지향하며, 핵심 비즈니스 로직(`core`)을 외부 인터페이스(`app`, `web`, `infra`)로부터 격리하는 구조입니다.

현재 시스템은 과도기적 단계로, 구형 진입점(`pc`, `web`)과 신형 아키텍처(`backend`)가 공존하고 있습니다.

---

## 2. Component Layers

### Layer 1: Application Entry Points
사용자와 시스템이 상호작용하는 진입점 계층입니다.

*   **`backend/` (Recommended)**: FastAPI 기반의 현대적인 REST API 서버. Router 패턴을 사용하여 확장성이 뛰어남. 향후 메인 서버로 통합 권장.
*   **`web/` (Legacy)**: 초기에 작성된 FastAPI/Jinja2 웹 대시보드 및 리포트 뷰어. 현재 운영 중이나 `backend`로 기능 이관 필요.
*   **`pc/` (Legacy CLI)**: App PC (Personal Client). 로컬 커맨드라인에서 데이터 수집, 백테스트 등을 실행하는 Fat Client.
*   **`app/cli/`**: 공용 CLI 도구 (`alerts`, `backtest` 등).

### Layer 2: Core Domain (`core/`)
시스템의 두뇌에 해당하며, 외부 디펜던시를 최소화한 순수 파이썬 로직입니다.

*   **`engine/`**: 백테스트 및 라이브 트레이딩 실행 엔진.
*   **`strategy/`**: 매매 전략 (Phase 9 등) 및 시그널 로직.
*   **`risk/`**: 자금 관리 및 포지션 사이징 규칙.
*   **`metrics/`**: 수익률, MDD 등 성과 지표 계산.

### Layer 3: Extensions & Automation (`extensions/`)
Core 기능을 확장하거나 장기 실행 작업을 처리하는 모듈입니다.

*   **`tuning/`**: Optuna 기반 하이퍼파라미터 최적화/튜닝 엔진.
*   **`automation/`**: 정기 리포트 발송, 데이터 업데이트 등 Cron Job 스크립트.

### Layer 4: Infrastructure & Adapters (`infra/`, `config/`)
외부 시스템과의 통신을 담당합니다.

*   **`config/`**: `production_config.py` 등 전략 및 환경 설정.
*   **`infra/data/`**: 주식 데이터 제공자 (PyKRX, FinanceDataReader 등).
*   **`infra/notify/`**: 메신저 어댑터 (Telegram, Slack).
*   **`infra/storage/`**: 데이터베이스(SQLite) 및 파일 시스템 핸들러.

---

## 3. Data Flow & Pipelines

### 3.1. Daily Operation Pipeline
1.  **Data Ingest**: 장 마감 후 `backend` 또는 `pc` 트리거로 데이터 수집 (`infra/data`).
2.  **Signal Gen**: `core/strategy`가 최신 데이터를 기반으로 추천 종목 선정.
3.  **Notification**: `infra/notify`를 통해 Telegram/Slack 전송.

### 3.2. Tuning Pipeline
1.  **Config**: `extensions/tuning`에서 검색 공간 정의.
2.  **Simulation**: `core/engine`을 병렬로 호출하여 시뮬레이션 수행.
3.  **Evaluation**: 결과 지표(`core/metrics`)를 Gate 로직으로 검증.
4.  **Selection**: 최적 파라미터를 선정하여 `config/`에 반영.

---

## 4. Current Architecture Issues (Cleanup Targets)

1.  **Web/Backend Separation**: `web/` 폴더와 `backend/` 폴더가 기능적으로 중복됨. `backend` 중심의 통합이 필요함.
2.  **NAS Support**: `nas/` 폴더는 과거 NAS 전용 배포를 위해 존재했으나, 현재는 컨테이너/클라우드 배포로 전환되는 추세임. Legacy로 분류.
3.  **Scripts Sprawl**: `tools/`와 `scripts/`에 다양한 유틸리티가 산재해 있음. `docs/design/components/05_tools.md` 참조하여 정리 필요.

---

## 5. Development Guidelines

*   **Core Logic**: 반드시 `core/` 내부에 작성하며, 웹 프레임워크나 DB 라이브러리에 직접 의존하지 않도록 함.
*   **New Features**: 새로운 기능은 `backend/`의 Router로 구현하거나 `extensions/` 모듈로 추가.
*   **Config**: 하드코딩을 피하고 `config/` 디렉토리의 설정 파일을 통해 주입받도록 설계.
