# App Module Analysis

**분석 일자**: 2025-12-29
**분석 대상**: `app/` 디렉토리 (API, CLI, Services)

## 1. 개요 (Overview)
`app/` 디렉토리는 시스템의 **애플리케이션 레이어**입니다.
외부 요청을 처리하는 **API**, 커맨드라인 작업을 수행하는 **CLI**, 그리고 비즈니스 로직을 캡슐화한 **Services**로 구성됩니다.

## 2. 파일 및 디렉토리별 기능 (Breakdown)

### 2.1 API (`app/api/`)
FastAPI 기반의 웹 서버 엔드포인트입니다.

| 파일명 | 상태 | 분류 | 설명 |
|---|---|---|---|
| **`api_backtest.py`** | **[Active]** | API | **Backtest & Tuning Server (Port 8001)**. 백테스트 실행, 튜닝 요청, 헬스체크, AI 분석 요청 등을 처리. |
| **`api_holdings.py`** | **[Active]** | API | **Holdings & Regime Server (Port 8000)**. 현재 보유 종목, 시장 레짐(Bull/Bear), 오늘의 추천주 등 운영 데이터 서빙. |

### 2.2 CLI (`app/cli/`)
터미널에서 직접 실행되는 유틸리티 커맨드입니다.

| 파일명 | 상태 | 분류 | 설명 |
|---|---|---|---|
| **`alerts.py`** | **[Active]** | CLI | **전략 스캐너 & 알림**. `scan` 명령으로 매매 신호를 생성하고 `notify` 명령으로 텔레그램 알림 발송. Phase 9 및 Legacy 전략 모두 지원. |
| **`backtest.py`** | **[Active]** | CLI | **Inbox Backtest Adapter**. `reports/pending/*.json` 요청 파일을 읽어 백테스트를 트리거하는 파이프라인 어댑터. |
| **`log_utils.py`** | **[Active]** | Util | 로깅 헬퍼. 슬랙/텔레그램 전송 연동 래퍼. |

### 2.3 Services (`app/services/`)
핵심 비즈니스 로직이 구현된 도메인 서비스입니다.

| 파일명 | 상태 | 분류 | 설명 |
|---|---|---|---|
| **`backtest_service.py`** | **[Active]** | Core | **백테스트 실행 엔진**. `BacktestRunner`를 래핑하여 파라미터 유효성 검사, 데이터 로딩, Train/Val/Test 분할 실행 등을 담당. |
| **`tuning_service.py`** | **[Active]** | Core | **Optuna 튜닝 오케스트레이터**. 튜닝 세션 관리, 최적 파라미터 탐색(앙상블), 백그라운드 작업 처리. |
| **`tuning_analysis_service.py`** | **[Active]** | AI | **AI 분석**. Claude API를 호출하여 튜닝 결과(지표, 파라미터)에 대한 해석과 개선 제안 리포트 생성. |
| **`optimal_params_service.py`** | **[Active]** | Mgmt | **파라미터 관리**. 튜닝된 파라미터의 이력 관리(Research) 및 운영 적용(Live Promote) 기능 제공. JSON 기반 저장소. |
| **`history_service.py`** | **[Active]** | Data | **이력 저장소**. SQLite(`backtest_history.db`)를 통해 백테스트 및 튜닝 결과를 영구 저장하고 통계 조회 기능 제공. |
| **`data_preflight.py`** | **[Active]** | Data | **데이터 무결성 검증**. 튜닝 전 데이터 파일(Parquet) 존재 여부, 날짜 커버리지 등을 사전 검사하는 Gatekeeper. |
| **`data_locator.py`** | **[Active]** | Data | **데이터 경로 해석**. 다양한 티커 포맷(069500, A069500 등)과 파일 경로 패턴을 표준화하여 Resolve. |

## 3. 구조적 특징 및 결론 (Conclusion)

1.  **높은 모듈화 (High Modularity)**: `app/` 내의 파일들은 단일 책임 원칙(SRP)을 잘 따르고 있습니다.
    *   `API`는 요청/응답 처리만 담당.
    *   `Services`는 비즈니스 로직만 담당.
    *   `Data Locator/Preflight`는 데이터 접근 로직을 추상화.
2.  **삭제 대상 없음**: 모든 파일이 현재 CI/CD 파이프라인, 운영 서버, 혹은 전략 실행에 필수적으로 사용되고 있습니다.
3.  **개선 포인트**: `api_backtest.py`와 `api_holdings.py`가 서로 다른 포트(8001, 8000)를 사용 중인데, 향후 `main.py` 등을 통해 통합하거나 Gateway 패턴을 고려해볼 수 있습니다(현재는 분리가 명확하여 유지 무방).

**결론**: `app/` 디렉토리는 시스템의 핵심이므로 **전체 파일 유지(Keep)**를 권장합니다.
