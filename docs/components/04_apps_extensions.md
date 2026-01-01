# Applications, Extensions & Scripts Analysis

시스템의 실행 가능한 애플리케이션(`pc`, `backend`)과 확장 기능(`extensions`), 그리고 운영 스크립트(`scripts`)에 대한 분석입니다.

## 1. Application Layer

### `pc/` (Operator CLI)
로컬 환경 또는 운영자가 직접 실행하는 CLI 도구 모음입니다. "Personal Computer" 또는 "Private Client"의 약자로 추정됩니다.
*   **`app_pc.py`**
    *   **목적:** 시스템의 주요 기능을 커맨드라인에서 실행하는 진입점.
    *   **기능:**
        *   `init`: DB 초기화.
        *   `ingest_eod`, `ingest_realtime`: 데이터 수집.
        *   `scanner`: 매수/매도 시그널 생성 및 Slack 알림.
        *   `report`: 성과 리포트 생성.
    *   **특징:** `core` 모듈을 직접 import하여 사용하는 "Fat Client" 구조.

### `backend/` (Modern API Server)
FastAPI 기반의 최신 백엔드 서버입니다.
*   **`app/main.py`**
    *   **목적:** API 서비스 제공.
    *   **구조:** RESTful API (`v1`), Router 기반 모듈화 (`dashboard`, `backtest`, `signals` 등).
    *   **비고:** 루트 디렉토리의 `web/main.py`와 역할이 유사하나, 구조가 더 체계적이고 확장에 용이한 형태. **시스템의 차세대 백엔드로 보임.**

## 2. Extensions Directory (`extensions/`)
시스템의 코어 기능 이외의 부가 기능 및 자동화 로직입니다.

### `automation/`
*   **`daily_report.py`**
    *   **목적:** 일일 리포트 자동 생성 및 발송 (Cron Job용).
    *   **기능:** `live_signal_generator`를 사용해 신호를 생성하고, 포트폴리오 현황과 함께 텔레그램으로 전송.
*   **`data_updater.py`**
    *   **목적:** 정기 데이터 업데이트 스크립트.

### `tuning/`
*   Optuna 등을 이용한 하이퍼파라미터 튜닝 관련 확장 기능들이 위치했을 것으로 추정.

## 3. Scripts Directory (`scripts/`)
다양한 운영, 유지보수, 배치 작업을 위한 스크립트 모음입니다.

### `daily/`
*   **`daily_recommend.py`**
    *   **목적:** 일일 매매 추천 엔진.
    *   **이슈:** `extensions/automation/daily_report.py`와 기능적으로 매우 유사함 (신호 생성 + 텔레그램 발송).
    *   **비고:** `recommend`는 "추천 행위"에, `report`는 "현황 보고"에 초점을 맞춘 것으로 보이나, 로직 통합이 가능해 보임.

### `ops/` (Operations)
*   **`notify.py`**: 간단한 알림 발송 테스트/유틸.
*   **`sync_cache_to_db.py`**: 파일 캐시 데이터를 DB로 동기화하는 유틸리티.

### `dev/`, `nas/`, `maintenance/`
*   개발 테스트, NAS 백업 설정, 유지보수용 일회성 스크립트들이 다수 존재.

## 요약 및 제언

### 1. 백엔드 통합 (`web` vs `backend`)
*   현재 루트의 `web/`과 `backend/`가 공존하고 있습니다. `backend/`가 더 현대적인 구조(Router, V1 API)를 갖추고 있으므로, `web/`의 기능을 `backend/`로 완전히 이관하고 **`web/`을 제거(또는 `backend`로 대체)**하는 것이 좋습니다.

### 2. 자동화 스크립트 정리
*   `daily_recommend.py`와 `daily_report.py`의 역할이 중복됩니다. `extensions/automation/` 폴더를 "정식 배치 작업" 공간으로 정의하고, `scripts/daily/`의 내용을 이곳으로 통합하거나 정리하는 것을 권장합니다.

### 3. 진입점 단순화
*   현재 실행 방법이 `app_pc.py`, `scripts/...`, `backend/...` 등으로 파편화되어 있습니다. 운영 가이드를 통해 "CLI 작업은 `pc/`, 서버 작업은 `backend/`, 배치는 `extensions/automation/`"과 같이 명확히 정의할 필요가 있습니다.
