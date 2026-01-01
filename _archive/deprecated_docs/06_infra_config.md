# Infrastructure & Configuration Analysis

시스템의 기반이 되는 설정(`config`)과 인프라(`infra`) 레이어에 대한 분석입니다.

## 1. Config Directory (`config/`)
시스템 전반의 환경 설정, 전략 파라미터, 데이터 소스 정의 파일들이 위치합니다.

### 주요 파일
*   **`production_config.py` (중요)**
    *   **목적:** 실제 운영(Live)에 적용되는 최종 전략 파라미터 ("Phase 9: Crisis Alpha").
    *   **내용:** MA 기간(60/120), RSI 기간(40), 손절비율(12%), 유니버스 정의 등. 백테스트를 통해 검증된 **Best Practice** 설정값.

*   **`config.yaml` / `common.yaml`**
    *   **목적:** 일반적인 애플리케이션 설정 (로깅 레벨, 경로 등).
    *   **비고:** `secret/config.yaml`이 존재할 경우 오버라이드 되는 구조.

*   **`data_sources.yaml`**
    *   **목적:** 데이터 수집 대상 및 벤치마크 정의.
    *   **내용:** 벤치마크(KODEX 200, S&P 500 등), 투자 유니버스 구성 종목 리스트 관리. 하드코딩을 피하기 위한 설정 파일.

*   **`us_market_indicators.yaml`**
    *   **목적:** 미국 시장 모니터링을 위한 지표 정의.
    *   **내용:** S&P500 200일선, VIX, CNN Fear & Greed 등 주요 체크 포인트 설정.

*   **`backtest.yaml`**
    *   **목적:** 백테스트 실행 시 사용되는 기본 파라미터 세트.
    *   **활용:** `production_config.py`가 Live 용이라면, 이 파일은 실험/개발용 기본값.

### `strategies/` Sub-directory
*   전략별 세부 파라미터(JSON/YAML)가 저장되는 곳으로 추정되나 현재는 파일이 적음.

---

## 2. Infra Directory (`infra/`)
외부 시스템(DB, 메신저, 데이터 프로바이더)과의 저수준 통신을 담당하는 어댑터 레이어입니다.

### `notify/` (Notification)
*   **`telegram.py`**
    *   **목적:** 텔레그램 봇 API 연동.
    *   **기능:** `.env` 또는 `secret/config.yaml`에서 토큰을 로드하여 메시지 발송. HTML/Markdown 모드 지원.
*   **`slack.py`**
    *   **목적:** 슬랙 웹훅 연동.
    *   **기능:** 간단한 텍스트 메시지 전송.

### `data/` (Data Access)
*   **`loader.py`**
    *   **목적:** 데이터 로딩 추상화.
    *   **기능:** `DataProvider` 인터페이스 및 `CachedDataProvider` 구현. 로컬 캐시(Pickle/Parquet) 또는 외부 소스에서 OHLCV 데이터 로드.
*   **`updater.py`**
    *   **목적:** 데이터 최신화.
    *   **기능:** 장 마감 후 새로운 데이터를 fetch하여 저장소(DB/Cache)를 갱신하는 로직.

### `storage/` (Persistence)
*   **`sqlite.py`**
    *   **목적:** SQLite 데이터베이스 연결 및 세션 관리.
    *   **기능:** DB 커넥션 풀링 및 세션 생성기.

### `logging/`
*   로깅 설정 관련 유틸리티가 위치할 것으로 예상. (현재 상세 분석 생략)

## 요약 및 제언
*   **구조적 완성도**: `config`와 `infra` 레이어는 역할이 명확하게 분리되어 있으며, 환경 변수와 Secret 관리도 체계적임.
*   **유지 보수**: `production_config.py`는 전략의 핵심이므로 최우선 관리 대상. `data_sources.yaml`을 통해 코드 수정 없이 유니버스 변경이 가능한 점은 우수함.
*   **통합 제안**: 현재 `core/utils/config.py`와 `config/` 디렉토리 간에 역할 중복(설정 로딩 로직)이 일부 존재할 수 있음. 장기적으로 `core.config`가 `config/` 파일을 읽어오는 표준 인터페이스로 통일되어야 함.
