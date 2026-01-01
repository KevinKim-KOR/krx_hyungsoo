# Core Module (`core/`)

**Last Updated**: 2026-01-01
**Purpose**: 핵심 비즈니스 로직 모듈 (데이터 로딩, 지표 계산, DB, 전략 엔진)

---

## 📁 Folder Structure
```
core/
├── data/           # 데이터 필터링
├── engine/         # 전략 엔진 (Phase9Executor, Scanner, Backtest)
├── metrics/        # 성과 지표
├── risk/           # 리스크 관리
├── strategy/       # 전략 로직 (Regime Detector, Signal Generator)
├── utils/          # 유틸리티
└── (Root Files)
```

---

## 📊 File Usage Summary

| File | Status | Used By |
|------|--------|---------|
| `data_loader.py` | ✅ **ACTIVE** | 12+ files (calendar_kr, fetchers, strategy, app) |
| `indicators.py` | ✅ **ACTIVE** | 6 files (tests, scanner, backtest, strategy) |
| `fetchers.py` | ✅ **ACTIVE** | 4 files (nas, app) |
| `calendar_kr.py` | ✅ **ACTIVE** | 4 files (fetchers, nas, app) |
| `db.py` | ✅ **ACTIVE** | 21+ files (전체 시스템) |
| `cache_store.py` | ⚠️ **UNUSED** | 0 files (직접 import 없음) |
| `notifications.py` | 🔶 **LEGACY** | 2 files (nas/app_nas.py, _archive) |
| `adaptive.py` | ❌ **DEPRECATED** | 1 file (_archive only) |

---

## 📄 Root Files

### `data_loader.py` (379 lines) - ✅ ACTIVE
**Purpose**: OHLCV 데이터 로딩 (yfinance, PyKRX, Naver Fallback)
| Function | Status | Description |
|----------|--------|-------------|
| `get_ohlcv(symbol, start, end)` | ✅ | 캐시 기반 OHLCV 로딩 |
| `get_ohlcv_safe(symbol, start, end)` | ✅ | 에러 시 빈 DataFrame 반환 래퍼 |
| `get_current_price_naver(code)` | ✅ | 네이버 금융 현재가 조회 |
| `get_kospi_index_naver()` | ⚠️ | 네이버 KOSPI 지수 조회 (사용 빈도 낮음) |
| `get_ohlcv_naver_fallback(symbol, start, end)` | ✅ | yfinance 실패 시 대체 로더 |
| `_read_cache`, `_write_cache` | ✅ | 내부 헬퍼 |
| `_normalize_df(df)` | ✅ | 내부 헬퍼 |

---

### `indicators.py` (301 lines) - ✅ ACTIVE
**Purpose**: 기술적 지표 계산 라이브러리
| Function | Status | Description |
|----------|--------|-------------|
| `sma(series, n)` | ✅ | 단순 이동평균 |
| `ema(series, n)` | ✅ | 지수 이동평균 |
| `rsi(close, n=14)` | ✅ | RSI (Phase9에서 사용) |
| `adx(high, low, close, n=14)` | ✅ | ADX (Phase9 Chop Filter) |
| `atr(high, low, close, n=14)` | ✅ | ATR (변동성) |
| `macd(close, fast, slow, signal)` | ⚠️ | MACD (사용 빈도 낮음) |
| `bollinger_bands(close, n, std_dev)` | ⚠️ | 볼린저 밴드 (사용 빈도 낮음) |
| `stochastic(high, low, close, n)` | ⚠️ | 스토캐스틱 (사용 빈도 낮음) |
| `williams_r(high, low, close, n)` | ⚠️ | 윌리엄스 %R (사용 빈도 낮음) |
| `cci(high, low, close, n)` | ⚠️ | CCI (사용 빈도 낮음) |
| `mfi(high, low, close, volume, n)` | ⚠️ | Money Flow Index (사용 빈도 낮음) |
| `zscore(series, n)` | ✅ | Z-Score |
| `slope(series, n)` | ✅ | 선형회귀 기울기 |
| `volatility(series, n)` | ✅ | 로그수익률 표준편차 |
| `rolling_max_drawdown(series)` | ✅ | MDD |
| `sector_score(prices_df, sectors_map)` | ⚠️ | 섹터별 모멘텀 (사용 빈도 낮음) |
| `turnover(close, volume)` | ⚠️ | 거래대금 (사용 빈도 낮음) |
| `turnover_stats(close, volume, n)` | ⚠️ | 거래대금 통계 (사용 빈도 낮음) |

---

### `fetchers.py` (248 lines) - ✅ ACTIVE
**Purpose**: EOD/실시간 데이터 수집 및 DB 적재
| Function | Status | Description |
|----------|--------|-------------|
| `fetch_eod_krx(code, start, end)` | ✅ | PyKRX 일별 OHLCV |
| `fetch_eod_yf(ticker, start, end)` | ✅ | yfinance 일별 OHLCV |
| `ingest_eod(date_str)` | ✅ | 캐시+증분 EOD 적재 (메인) |
| `ingest_eod_legacy(date)` | ❌ | 레거시 EOD 적재 (**DEPRECATED**) |
| `fetch_realtime_price(code)` | ⚠️ | 네이버 근실시간 호가 (사용 빈도 낮음) |
| `ingest_realtime_once(codes, ts)` | ⚠️ | 실시간 가격 DB 적재 (사용 빈도 낮음) |
| `ensure_yahoo_ticker(code, market)` | ✅ | Yahoo 티커 변환 |
| `_to_date(d)`, `_yyyymmdd(d)` | ✅ | 내부 헬퍼 |
| `_resolve_asof(date_str)` | ✅ | 휴장일 → 직전 거래일 변환 |

---

### `calendar_kr.py` (142 lines) - ✅ ACTIVE
**Purpose**: KRX 거래일 캘린더 관리
| Function | Status | Description |
|----------|--------|-------------|
| `load_trading_days(asof, start, end)` | ✅ | 거래일 DatetimeIndex 로드 |
| `build_trading_days(start, end)` | ✅ | 거래일 빌드 후 캐시 저장 |
| `is_trading_day(d)` | ✅ | 거래일 여부 확인 |
| `next_trading_day(d)` | ✅ | 다음 거래일 반환 |
| `prev_trading_day(d)` | ✅ | 이전 거래일 반환 |
| `_first_available_ohlcv(start, end)` | ✅ | 내부 헬퍼 |

---

### `db.py` (71 lines) - ✅ ACTIVE
**Purpose**: SQLAlchemy ORM 모델 및 DB 연결
| Class/Function | Status | Description |
|----------------|--------|-------------|
| `Security` | ✅ | 종목 마스터 테이블 |
| `PriceDaily` | ✅ | 일별 OHLCV 테이블 |
| `PriceRealtime` | ⚠️ | 실시간 가격 테이블 (사용 빈도 낮음) |
| `Position` | ⚠️ | 포지션 테이블 (사용 빈도 낮음) |
| `Holdings` | ✅ | 보유 종목 테이블 |
| `init_db()` | ✅ | 테이블 생성 |
| `get_db_connection()` | 🔶 | SQLite 연결 (레거시 호환) |

---

### `cache_store.py` (50 lines) - ⚠️ UNUSED
**Purpose**: 간단한 OHLCV 파일 캐시 (Pickle)
> ⚠️ **주의**: 이 파일은 현재 직접 import되지 않습니다. `data_loader.py`가 자체 캐시 로직을 사용합니다.

| Function | Status | Description |
|----------|--------|-------------|
| `load_cached(code)` | ⚠️ | 미사용 |
| `save_cache(code, df)` | ⚠️ | 미사용 |
| `cache_path(code)` | ⚠️ | 미사용 |
| `ensure_dir()` | ⚠️ | 미사용 |

---

### `notifications.py` - 🔶 LEGACY
**Purpose**: 알림 관련 유틸
> 🔶 **레거시**: `nas/app_nas.py`에서만 사용됩니다. `infra/notify/telegram.py`로 대체 권장.

---

### `adaptive.py` - ❌ DEPRECATED
**Purpose**: 적응형 파라미터 유틸
> ❌ **미사용**: `_archive` 폴더에서만 참조됩니다. 삭제 검토 대상.

---

## 📁 Subdirectories

### `core/engine/` - ✅ ACTIVE
전략 엔진 모듈

| File | Status | Description |
|------|--------|-------------|
| `phase9_executor.py` | ✅ | Phase 9 전략 실행기 (CLI에서 사용) |
| `scanner.py` | ✅ | 종목 스캐너 |
| `backtest.py` | ✅ | 백테스트 엔진 (12+ files에서 사용) |
| `config_loader.py` | ✅ | 설정 로더 |
| `krx_maps_adapter.py` | ✅ | KRX 어댑터 |

### `core/strategy/` - ✅ ACTIVE
전략 로직 모듈

| File | Status | Description |
|------|--------|-------------|
| `market_regime_detector.py` | ✅ | 시장 국면 감지 (12+ files에서 사용) |
| `live_signal_generator.py` | ✅ | 실시간 신호 생성 (4 files에서 사용) |
| `signals.py` | ✅ | 신호 처리 |
| `us_market_monitor.py` | ✅ | 미국 시장 모니터링 |

### `core/risk/` - ✅ ACTIVE
리스크 관리 모듈

### `core/utils/` - ✅ ACTIVE
공통 유틸리티 (Datasource Config, Formatting 등)

### `core/data/` - ✅ ACTIVE
데이터 필터링 로직

### `core/metrics/` - ⚠️ LOW USAGE
성과 지표 계산 (사용 빈도 확인 필요)

---

## 🔗 Dependencies
- `pandas`, `numpy`, `yfinance`, `pykrx`, `sqlalchemy`
- 내부: `core.utils.datasources`, `infra.data.loader`

---

## 🧹 정리 권장 사항
1. ❌ `adaptive.py`: 삭제 검토
2. ⚠️ `cache_store.py`: `data_loader.py`와 통합 또는 삭제 검토
3. 🔶 `notifications.py`: `infra/notify/` 사용으로 마이그레이션
4. ⚠️ `indicators.py` 내 저빈도 함수들: 사용 여부 재검토
