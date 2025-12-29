# Core Module Analysis

시스템의 핵심 비즈니스 로직, 데이터 처리, 전략 실행, 백테스트 엔진을 포함하는 `core` 디렉토리 분석 결과입니다.

## 1. Root Directory (`core/`)
시스템 전반에서 공통적으로 사용되는 유틸리티, 데이터 로더, 데이터베이스 스키마 등이 위치합니다.

### `adaptive.py`
*   **목적:** 레거시 코드 호환성을 위한 Import Shim. `scanner.py` 등에서 구버전 import 경로를 사용할 경우를 대비.
*   **주요 기능:**
    *   `core.utils.config` 모듈에서 `get_effective_cfg`를 import 하거나 실패 시 `load_cfg`를 alias로 제공.
*   **판단: [유지 / 아카이브 후보]** (점진적으로 모든 import 경로 수정 후 삭제 권장)

### `cache_store.py`
*   **목적:** 파일 기반의 간단한 OHLCV 데이터 캐싱 처리. 파라미터 튜닝이나 반복적 백테스트 시 속도 향상.
*   **주요 기능:**
    *   `load_cached`: 캐시된 파일 로드 및 인덱스 정규화.
    *   `save_cache`: DataFrame을 Pickle로 저장.
*   **판단: [유지]**

### `calendar_kr.py`
*   **목적:** KRX 거래일/휴장일 관리 및 캘린더 생성.
*   **주요 기능:**
    *   `build_trading_days`: 벤치마크(069500) 데이터를 기반으로 거래일 목록 생성.
    *   `load_trading_days`: 캐시된 거래일 목록 로드 또는 생성.
    *   `is_trading_day`, `next_trading_day`, `prev_trading_day`: 편의 함수.
*   **판단: [유지]**

### `data_loader.py`
*   **목적:** 다양한 소스(yfinance, PyKRX, Naver 금융)로부터 OHLCV 데이터를 로드하고 정규화.
*   **주요 기능:**
    *   `get_ohlcv`: 캐시 우선 로딩, 실패 시 다운로드.
    *   `get_ohlcv_naver_fallback`: yfinance 실패 시 PyKRX/Naver 금융으로 폴백 처리.
    *   `get_current_price_naver`: 실시간 현재가 조회.
*   **판단: [유지]**

### `db.py`
*   **목적:** SQLite 데이터베이스 연결 설정 및 SQLAlchemy ORM 모델 정의.
*   **주요 기능:**
    *   ORM 모델: `Security`, `PriceDaily`, `PriceRealtime`, `Position`, `Holdings`.
    *   `init_db`: 테이블 생성.
*   **이슈:** `DB_PATH`가 하드코딩 되어 있어(`data/krx_alertor.db`) 환경 변수나 설정 파일 기반으로 경로 유연화 필요 가능성 있음.
*   **판단: [유지]** (경로 수정 권장)

### `fetchers.py`
*   **목적:** 외부 API를 통한 데이터 수집 로직 집합 (PyKRX, yfinance, Naver).
*   **주요 기능:**
    *   `fetch_eod_krx`, `fetch_eod_yf`: 일별 데이터 수집.
    *   `ingest_eod`: 수집된 데이터를 DB 또는 캐시에 적재. (캐시 기반 로직이 주류가 됨)
    *   `fetch_realtime_price`: 실시간 가격 조회.
*   **판단: [유지]**

### `indicators.py`
*   **목적:** 기술적 지표 및 각종 스코어 계산 함수 모음. `ta-lib` 의존성 없이 `pandas`로 구현.
*   **주요 기능:**
    *   추세: SMA, EMA, MACD, ADX.
    *   모멘텀/오실레이터: RSI, MFI, Stochastic, Williams %R, CCI.
    *   변동성: Bollinger Bands, ATR.
    *   기타: Z-Score, Trend Slope, Sector Score.
*   **판단: [유지]**

### `notifications.py`
*   **목적:** 메시지 발송 유틸리티 (Slack, Telegram).
*   **주요 기능:**
    *   `send_telegram`, `send_slack`: 외부 API 호출.
    *   `send_notify`: 설정(`cfg`)에 따라 채널 자동 선택.
*   **판단: [유지]**

---

## 2. Engine Directory (`core/engine/`)
백테스트 및 전략 실행을 담당하는 코어 모듈입니다.

### `analysis_logger.py`
*   **목적:** 백테스트 실행 과정의 상세 로그(일별 성과, 트레이드 기록, 레짐 변경 등)를 기록하고 저장.
*   **주요 기능:**
    *   일자별 로그, 트레이드 로그, 레짐 변경 로그, 방어 이벤트 로그 관리.
    *   DataFrame 변환 및 파일 저장/로드.
*   **판단: [유지]**

### `backtest.py`
*   **목적:** 백테스트 엔진 로직. 포트폴리오 상태 관리 및 매매 실행 시뮬레이션.
*   **주요 기능:**
    *   클래스: `Position`, `Trade`, `Portfolio`, `BacktestEngine`.
    *   `execute_buy`, `execute_sell`: 수수료/세금/슬리피지를 고려한 체결 시뮬레이션.
    *   `rebalance`: 목표 비중에 따른 리밸런싱.
    *   `get_performance_metrics`: CAGR, MDD, Sharpe 등 성과 분석.
*   **판단: [유지]**

### `config_loader.py`
*   **목적:** YAML 설정 파일을 읽어 백테스트 엔진 객체를 생성하는 팩토리.
*   **주요 기능:**
    *   `load_backtest_config`: 설정 로드 및 기본값 처리.
    *   `create_backtest_engine_from_config`: 설정기반 엔진 인스턴스화.
    *   `create_maps_adapter_from_config`: MAPS 어댑터 생성.
*   **판단: [유지]**

### `krx_maps_adapter.py`
*   **목적:** MAPS(Moving Average Position Score) 전략을 실행하기 위한 어댑터. Jason의 전략 코드를 이식.
*   **주요 기능:**
    *   데이터 구조 변환 (Core 포맷 ↔ MAPS 전략 포맷).
    *   `run`: 백테스트 실행 및 로깅.
    *   `_simple_maps_backtest`: 자체 구현된 간이 MAPS 로직.
*   **판단: [유지]**

### `phase9_executor.py`
*   **목적:** Phase 9 (Crisis Alpha) 전략을 실제 운영 환경(Live)에서 실행하기 위한 실행기.
*   **주요 기능:**
    *   `execute`: 일별 시그널 생성 (Dual Timeframe Regime + ADX Filter + RSI Logic).
    *   시장 데이터 로드 및 레짐 판단 통합.
*   **판단: [유지]** (현재 주력 전략 실행 파일)

### `scanner.py`
*   **목적:** 시장 전체를 스캔하여 전략 규칙에 부합하는 매매 후보를 발굴.
*   **주요 기능:**
    *   `_calc_momentum_scores`: 전 종목 모멘텀 스코어링.
    *   `generate_signals`: 매수/매도/홀드 신호 생성 (HOLD_CORE 로직 포함).
*   **판단: [유지]**

---

## 3. Risk Directory (`core/risk/`)
포트폴리오 리스크 및 개별 종목 리스크 관리 모듈입니다.

### `manager.py`
*   **목적:** 포트폴리오 수준의 리스크 매니저. 진입 전 사전 검증(Pre-trade validation).
*   **주요 기능:**
    *   `check_position_size`, `check_portfolio_volatility`, `check_correlation`: 각종 리스크 한도 체크.
    *   `validate_trade`: 거래 허용 여부 종합 판단.
    *   `calculate_position_size`: 변동성 역가중 기반 사이즈 계산.
*   **판단: [유지]**

### `position.py`
*   **목적:** 개별 포지션 객체 정의 및 상태 관리.
*   **주요 기능:**
    *   `Position` 데이터 클래스: 평단가, 수량, 손절/익절가 관리.
    *   `PositionManager`: 포트폴리오 내 포지션 집합 관리 CRUD.
*   **판단: [유지]**

### `stop_loss_manager.py`
*   **목적:** 다양한 조건(레짐, 변동성)을 결합한 하이브리드 손절 로직.
*   **주요 기능:**
    *   `get_stop_loss`: 전략상 손절과 하이브리드 매트릭스상 손절 중 타이트한 값 선택.
    *   `check_stop_loss_triggered`: 손절가 도달 여부 판단.
*   **판단: [유지]**

---

## 4. Strategy Directory (`core/strategy/`)
구체적인 투자 전략 로직과 시장 판단 모듈들이 위치합니다.

### `defense_system.py`
*   **목적:** 하락장 방어를 위한 자동 손절 및 재진입 제한 시스템.
*   **주요 기능:**
    *   `check_individual_stop_loss`: 고정 손절 + 트레일링 스톱.
    *   `check_portfolio_stop_loss`: 포트폴리오 전체 가치 기반 청산.
    *   `CooldownManager`: 손절 후 일정 기간 재진입 금지.
*   **판단: [유지]**

### `live_signal_generator.py`
*   **목적:** 운영 환경(Live) 파라미터를 기반으로 매일의 추천 신호를 생성.
*   **주요 기능:**
    *   `load_live_params`: 설정 파일 및 RSI 프로파일 로드.
    *   `generate_recommendation`: 레짐, RSI 등을 고려하여 최종 매매 추천 생성.
    *   텔레그램 메시지 포맷팅 기능 포함.
*   **판단: [유지]**

### `market_crash_detector.py`
*   **목적:** 시장 급락(Crash) 감지 및 방어 모드 발동.
*   **주요 기능:**
    *   `detect_market_crash`: KOSPI 지수 급락 감지.
    *   `detect_portfolio_decline`: 보유 종목 다수 동반 하락 감지.
    *   방어 모드 진입/해제 관리.
*   **판단: [유지]**

### `market_regime_detector.py`
*   **목적:** 시장의 국면(Regime)을 Bull/Bear/Neutral로 판단.
*   **주요 기능:**
    *   이동평균(MA), ADX, 추세 강도 등을 종합하여 레짐 판별.
    *   `detect_regime_adx`: ADX 필터가 적용된 레짐 감지 로직 (주력 모델).
*   **판단: [유지]**

### `rules.py`
*   **목적:** 전략 실행 규칙 정의 및 공통 데이터 구조.
*   **주요 기능:**
    *   `SignalType` Enum, `Signal` dataclass.
    *   `StrategyRules`: 핵심 보유 종목(HOLD_CORE) 처리 및 매수 후보 선정 우선순위 로직.
*   **판단: [유지]**

### `signals.py`
*   **목적:** 다양한 기술적 분석 기반의 매매 신호 생성기.
*   **주요 기능:**
    *   모멘텀, 평균회귀, 추세추종 신호 생성.
    *   MAPS 전략 신호 생성 로직 포함.
*   **판단: [유지]**

### `us_market_monitor.py`
*   **목적:** 미국 시장 주요 지표(S&P500, Nasdaq, VIX 등) 모니터링 및 리포트.
*   **주요 기능:**
    *   설정된 지표 계산 및 상태(Bull/Bear) 판단.
    *   ChatGPT 프롬프트 생성을 통한 AI 분석 연동 기능.
*   **판단: [유지]**

### `volatility_manager.py`
*   **목적:** 변동성(ATR) 기반의 포지션 크기 조절 시스템.
*   **주요 기능:**
    *    ATR 계산 및 변동성 레벨(High/Low) 분류.
    *   변동성 국면에 따른 포지션 비중 축소/확대 가이드 제공.
*   **판단: [유지]**

### `weight_scaler.py`
*   **목적:** 최종 포트폴리오 비중 산출 (동적 자산 배분).
*   **주요 기능:**
    *   스케일링 파이프라인: Base Weight -> RSI Scaling -> Soft Normalize -> Regime Scaling.
    *   시장 상황에 따라 주식 비중을 줄이고 현금을 확보하는 로직.
*   **판단: [유지]**

---

## 5. Utils Directory (`core/utils/`)

### `cfg_loader.py`
*   **목적:** 간단한 YAML 설정 로더.
*   **주요 기능:**
    *   여러 경로의 설정 파일을 순차적으로 탐색하여 로드.
*   **판단: [유지]** (기능 단순하지만 명확함)

### `config.py`
*   **목적:** 시스템 전반의 설정을 관리하는 메인 config 모듈.
*   **주요 기능:**
    *   `load_cfg`: 통합 설정 로딩.
    *   `load_watchlist`, `write_watchlist_codes`: 관심 종목 파일 관리(CRUD).
    *   각종 기본값(Default) 제공.
*   **판단: [유지]**

### `datasources.py`
*   **목적:** 데이터 소스 관련 설정(벤치마크 심볼, 유니버스 등)을 코드 내 하드코딩 대신 YAML/함수로 관리.
*   **주요 기능:**
    *   `benchmark_candidates`, `universe_symbols` 등의 리스트 제공.
    *   `config/data_sources.yaml` 연동.
*   **판단: [유지]**

### `trading.py`
*   **목적:** 거래 시간 및 최신 거래일 관련 헬퍼.
*   **주요 기능:**
    *   DB 조회하여 특정 마켓의 최신 거래 데이터 날짜 확인.
*   **판단: [유지]**

### `trading_day.py`
*   **목적:** 거래일 판별 로직 (PyKRX 의존).
*   **주요 기능:**
    *   `is_trading_day`: 오늘이 휴장일인지 확인.
    *   `in_trading_hours`: 현재 시간이 장중인지 확인.
*   **판단: [유지]**

### `valuation.py`
*   **목적:** 자산 가치 보정 로직.
*   **주요 기능:**
    *   `corrected_valuation`: 기록된 가치와 실제 보유 가치 간의 불일치 시 보수적 관점(또는 특정 룰)에서 보정.
*   **판단: [유지]**

---

## 6. Metrics Directory (`core/metrics/`)

### `performance.py`
*   **목적:** 금융 성과 지표 계산.
*   **주요 기능:**
    *   CAGR, Sharpe Ratio, Sortino Ratio, MDD, Returns 계산.
*   **판단: [유지]**
