# Web Module Analysis

**분석 일자**: 2025-12-29
**분석 대상**: `web/` 디렉토리 및 모든 하위 파일 (전수 조사)

## 1. 개요 (Overview)
`web/` 디렉토리는 백엔드 API 서비스와 웹 기반 운영 도구를 포함합니다.
FastAPI 기반의 Application과 보고서 처리/데이터 갱신을 위한 유틸리티 스크립트로 구성됩니다.

## 2. 파일별 상세 분석 (Detailed Analysis)

### 2.1 Core Application (`web/*.py`)

#### `main.py`
*   **목적**: FastAPI 메인 애플리케이션 진입점.
*   **함수 목록 및 기능**:
    *   `_safe_include(path, attr)`: 모듈 임포트 실패 시 앱 구동을 멈추지 않고 스킵 처리하는 안전 장치. **(유지)**
    *   `home(request)`: `/` 엔드포인트. 간단한 시장 브리핑(Top 등락률)을 보여주는 대시보드 역할. **(유지 - Dashboard 완성 전까지)**
    *   `api_report_eod()`: `/api/report/eod`. EOD(End of Day) 리포트 생성을 트리거하는 API. **(유지)**
    *   `health()`: `/health`. 서버 상태 확인. **(유지)**
*   **판단**: **[유지]** (시스템의 진입점)

#### `bt_history.py`
*   **목적**: 백테스트 이력 비교 및 조회 (Router).
*   **함수 목록 및 기능**:
    *   `bt_history()`: `/bt/history`. 두 개의 백테스트 결과(NAV, 지표)를 시각적으로 비교하는 페이지 제공. **(유지 - 운영 필수 도구)**
    *   `bt_history_csv()`: 비교 데이터를 CSV로 다운로드. **(유지)**
    *   `_load_index`, `_get_pkg_by_key`: 백테스트 패키지 탐색 및 로딩 로직. **(유지)**
*   **판단**: **[유지]** (백테스트 결과 관리 및 디버깅에 필수적임)

#### `bt_inbox_service.py`
*   **목적**: 백테스트 결과 수신 및 처리를 위한 서비스/워커.
*   **함수 목록 및 기능**:
    *   `scan_inbox_once()`: `reports/backtests/inbox` 폴더를 스캔하여 신규 업로드된 결과물 처리. **(유지 - CI/CD 파이프라인)**
    *   `verify_sha256sums()`: 결과 패키지의 무결성 검증. **(유지)**
    *   `move_to_processed()`: 검증 완료된 파일을 `processed` 폴더로 이동 및 정리. **(유지)**
    *   `_telegram_notify()`: 처리 결과 텔레그램 알림. **(유지)**
*   **판단**: **[유지]** (자동화된 실험 파이프라인의 핵심 컴포넌트)

#### `signals.py`
*   **목적**: 일일 매매 신호 조회 및 관리 (Router).
*   **함수 목록 및 기능**:
    *   `signals_page()`: `/signals`. `signals.service`를 호출하여 매매 신호 리스트 표출. **(유지 - 레거시 UI 호환)**
    *   `signals_recalc()`: 신호 재계산 트리거 API. **(유지)**
    *   `signals_notify()`: 텔레그램 알림 발송 API. **(유지)**
*   **판단**: **[유지]** (Phase 9 `alerts.py`가 CLI를 담당하지만, 웹에서의 접근성을 위해 유지 필요)

#### `watchlist.py`
*   **목적**: 관심 종목 관리 (Router).
*   **함수 목록 및 기능**:
    *   `page_watchlist()`: 워치리스트 편집 페이지. **(유지)**
    *   `api_watchlist_save()`: 워치리스트 저장 API. **(유지)**
*   **판단**: **[유지]** (간단하지만 유용한 유틸리티)

---

### 2.2 Utilities (`web/*.py`)

#### `build_index.py`
*   **목적**: 백테스트 리포트 인덱스(`index.html/json`) 생성기.
*   **함수 목록 및 기능**:
    *   `gather_runs()`: 파일시스템에서 백테스트 결과들을 수집. **(유지)**
    *   `build_html()`: 수집된 데이터를 바탕으로 정렬/필터링 가능한 HTML 테이블 생성. **(유지)**
*   **판단**: **[유지]** (`bt_history.py`와 강하게 결합되어 있으며 리포트 가시성을 제공함)

#### `cal_refresh.py`
*   **목적**: 거래일 캘린더(`trading_days.pkl`) 갱신 유틸리티.
*   **함수 목록 및 기능**:
    *   `_try_pmc()`, `_try_excals()`: `pandas_market_calendars` 등 외부 라이브러리를 이용한 휴장일 데이터 확보. **(유지)**
    *   `main()`: 캘린더 피클 파일 생성 실행. **(유지)**
*   **판단**: **[유지]** (백테스트 및 라이브 시스템의 날짜 연산에 필수적인 데이터 생성기)

#### `enhance_index.py`
*   **목적**: 생성된 `index.html`에 클라이언트 사이드 기능 주입.
*   **함수 목록 및 기능**:
    *   HTML 내에 JS/CSS를 주입하여 Table Filtering, CSV Export 기능을 추가함.
*   **판단**: **[삭제 고려 / 아카이브]**
    *   이유: `dashboard` 프로젝트가 완성되면 정적 HTML 인덱싱 방식은 도태될 예정임.
    *   현재 상태: 당장은 `build_index.py` 결과물의 UX를 위해 사용 중이므로 **[보류/운영 중]**이나, 장기적으로는 제거 대상.

#### `universe_builder.py`
*   **목적**: 투자 유니버스(`universe.txt`) 자동 생성기.
*   **함수 목록 및 기능**:
    *   `build_universe()`: `config/data_sources.yaml` 설정에 따라 여러 소스(Static, CSV, Query)를 병합. **(유지)**
    *   `_apply_rules()`: 블랙리스트 필터링, 중복 제거, 티커 정규화 수행. **(유지)**
*   **판단**: **[유지]** (시스템 데이터 파이프라인의 시작점)

---

### 2.3 Frontend & Templates

#### `web/dashboard/` (Directory)
*   **목적**: React 기반의 차세대 대시보드 프론트엔드 프로젝트.
*   **판단**: **[유지]** (미래의 UI 표준)

#### `web/templates/` (Directory)
*   **목적**: Jinja2 템플릿 파일 (`base.html`, `signals.html`, `bt_history.html` 등)
*   **판단**: **[유지]** (현재 `signals.py`, `bt_history.py` 등에서 사용 중)

## 3. 종합 의견 (Summary)
`web/` 디렉토리는 현재 **운영에 필수적인** 파일들로 구성되어 있어 즉시 삭제할 파일은 없습니다.
다만, 향후 `web/dashboard` 프로젝트가 안정화되면 다음 순서로 레거시 제거가 가능합니다.
1.  **Phase 1**: `enhance_index.py` 및 `build_index.py` (동적 대시보드로 대체 시)
2.  **Phase 2**: `templates/` 및 관련 Router (`bt_history.py`의 HTML 서빙 부분)

현재 시점에서는 **모두 유지(Active)**하는 것을 권장합니다.
