# 친구 프로젝트(momentum-etf) 데이터 수집 방식 / 주기 분석

작성: 2026-06-07
대상: `ref/momentum-etf-main/` (사용자가 zip 으로 제공한 친구 프로젝트)
성격: 우리(krx_alertor_modular) 프로젝트의 NAV / 괴리율 / 구성종목 / 가격 시계열
source 진단 / 채택 결정에 사용하기 위한 외부 참조 분석.

> ⚠️ **본 문서는 친구 프로젝트의 데이터 source / 캐싱 / 주기 패턴을 정리한
> 참고 자료다.** 친구 프로젝트의 코드 / 구조 / 데이터 모델을 우리 프로젝트에
> 자동 차용하지 않는다 (`docs/CLAUDE.md` §7 — 친구 프로젝트를 뼈대로 삼지 않는다).

---

## 0. 핵심 결론 한 줄

친구 프로젝트는 **네이버 비공식 endpoint 5종 + pykrx + Yahoo (yfinance) + 토스 +
Investing.com + CNN + KIS master ZIP** 을 source 로 사용하며, **모든 외부 호출에
TTL 캐시 + 실패 시 stale 재사용 + 운영 배치(APScheduler) 단위 갱신** 패턴을 일관
적용한다. NAV / 괴리율 / 시장가는 **`finance.naver.com/api/sise/etfItemList.nhn`
1회 호출로 전체 ETF universe 를 30초 TTL 로 가져오는 구조** 가 핵심이다.

---

## 1. source 카탈로그 (한눈에)

| # | 도메인 | endpoint / 함수 | 제공 데이터 | 인증 |
| --- | --- | --- | --- | --- |
| 1 | **NAV / 시장가 / 괴리율 (전체 ETF)** | `finance.naver.com/api/sise/etfItemList.nhn` | nav / nowVal / changeRate / 3M / open/high/low/volume — universe 전체 | 없음 |
| 2 | ETF 메타 (기본) | `stock.naver.com/api/domestic/detail/{ticker}/ETFBase` | 보수 / 순자산총액 / 상장일 / 기초지수 | 없음 |
| 3 | ETF 메타 (배당) | `stock.naver.com/api/domestic/detail/{ticker}/ETFDividend` | TTM 배당수익률 / 전회 배당 / 기준일 | 없음 |
| 4 | ETF 구성종목 | `stock.naver.com/api/domestic/detail/{ticker}/ETFComponent` | 상위 비중 / componentItemCode / componentReutersCode / componentIsinCode / referenceDate | 없음 |
| 5 | 국내 개별 실시간 | `stock.naver.com/api/polling/domestic/stock?itemCodes=...` | 종가 / 변동률 / 프리/애프터 | 없음 |
| 6 | 국내 ETF 카테고리 | `stock.naver.com/api/stockSecurity/etfs/v1/domestic/themes`, `/domestic` | 분류 (주식/채권/투자국가/섹터/지수/혁신기술/배당/트렌드 등) | 없음 |
| 7 | 국내 벌크 marketValue | `m.stock.naver.com/api/stocks/marketValue/{market}` | KOSPI / KOSDAQ 시가총액 벌크 | 없음 |
| 8 | 해외 (worldstock) | `stock.naver.com/api/foreign/market/stock/global` | 미국 개별 — 업종 / 배당률 / 시가총액 | 없음 |
| 9 | 가격 시계열 (한국) | `pykrx` → `get_etf_ohlcv_by_date` → fallback `get_market_ohlcv_by_date` → `get_etn_ohlcv_by_date` | OHLCV | 없음 |
| 10 | 가격 시계열 (해외 + 환율) | `yfinance` (`yf.download` / `yf.Ticker` / `yf.Search` / `YfData.get` v7 quote) | OHLCV / 실시간 quote / 통화쌍 | 없음 |
| 11 | 미국 실시간 | 토스증권 `wts-info-api.tossinvest.com` | 미국 실시간 vs Yahoo 보조 | 없음 |
| 12 | 호주 실시간 | `quoteapi.com/api/v5/symbols` (marketindex.com.au) | 호주 실시간 (`APP_ID` 평문) | 평문 ID |
| 13 | VKOSPI | `kr.investing.com/indices/kospi-volatility` | HTML 정규식 파싱 — 코스피200 변동성 지수 | 없음 |
| 14 | 공포탐욕지수 | `production.dataviz.cnn.io/index/fearandgreed/graphdata` | score / rating / previous_close | 없음 |
| 15 | KIS ETF master | `new.real.download.dws.co.kr/common/master/kospi_code.mst.zip`, `kosdaq_code.mst.zip` | KOSPI / KOSDAQ 마스터 ZIP (정적) | 없음 |

**총 15 source. 모두 인증키 없음 (호주 QuoteAPI 의 `APP_ID` 만 평문 상수).**

---

## 2. NAV / 시장가 / 괴리율 (가장 중요)

### 2.1 단일 endpoint 로 전체 ETF universe 일괄 수집

```
GET https://finance.naver.com/api/sise/etfItemList.nhn
Headers: Mozilla UA, Referer: https://finance.naver.com/sise/etfList.nhn
Response: { result: { etfItemList: [ {itemcode, itemname, nav, nowVal, changeRate,
  threeMonthEarnRate, openVal, highVal, lowVal, quant, ...}, ... ] } }
```

- **소스 위치**: `utils/data_loader.py:_fetch_etf_inav_all` (라인 1485)
- **TTL**: **30 초** (모듈-전역 단일 캐시 `_ETF_INAV_GLOBAL_CACHE`)
- **호출 빈도**: 사용자 요청 시점 (실시간 화면 진입). 정기 batch 호출 X — 화면 진입 시
  단발 호출이 30 초 캐시 안에 들어오면 재호출 없음.
- **벌크 / 단일 구분**: 응답 자체가 universe 전체. `fetch_naver_etf_inav_snapshot(tickers)`
  는 단일 호출 결과에서 요청 ticker 만 filter (호출 비용은 동일).
- **괴리율 직접 제공 X — 자체 계산**: 응답 nav / nowVal 로 친구가 직접 계산.
  ```python
  deviation = ((price_value / nav_value) - 1.0) * 100.0
  ```
- **실패 정책**: `try/except` 로 빠지고 **stale 캐시 재사용** (TTL 지났어도 캐시 값
  retain). 운영 안정성 보장.
- **NAV asof**: API 응답 자체에는 명시적 asof 키 없음. 화면 진입 시각 = 응답 시각.

### 2.2 비교 — 우리 진단 1차 결과와의 일치점

우리는 `m.stock.naver.com/api/stock/{ticker}/integration` 에서 `etfKeyIndicator.nav`
+ `dealTrendInfos[0].closePrice` + `deviationRate` + `bizdate` 를 발견했다.

| 항목 | 우리 진단 1차 | 친구 프로젝트 |
| --- | --- | --- |
| Endpoint | `m.stock.naver.com/api/stock/{ticker}/integration` | `finance.naver.com/api/sise/etfItemList.nhn` |
| 호출 단위 | per-ticker (4 ticker = 4 호출) | universe 단일 호출 (≈1000+ ETF 1회) |
| NAV 키 | `etfKeyIndicator.nav` | `etfItemList[].nav` |
| 시장가 키 | `dealTrendInfos[0].closePrice` | `etfItemList[].nowVal` |
| 괴리율 | 응답 제공 (`deviationRate`) | 응답 X — 직접 계산 |
| TTL | 진단 시점 측정 X | 30 초 |
| asof | `bizdate` | 응답에 명시 없음 |
| 인증 | 없음 | 없음 |

**결론**: 친구 프로젝트의 endpoint 가 **호출 효율(universe 1회)** 측면에서 압도적
우위. 우리 진단 endpoint 는 **per-ticker 상세(괴리율 사전 계산, asof 명시)** 측면
에서 우위. 운영 채택 시 두 source 를 결합하는 패턴(universe 캐시 + 필요 시 per-
ticker 보강)이 가능.

### 2.3 추정 iNAV (PoC 단계)

별도로 `scripts/verify_realtime_inav.py` 가 존재 — **etfnow.co.kr 의 "추정 iNAV"**
계산 패턴을 모방. 공식 NAV(=`meta_cache.nav`) × (1 + 포트폴리오 변동% × 환율 변동%)
로 추정.

- 입력: `holdings_cache.items[i].weight`, Yahoo `regularMarketChangePercent` /
  `preMarketChangePercent` / `postMarketChangePercent`, 환율 변동률
- 시장 상태 분기: PRE / REGULAR / POST / CLOSED 각각 다른 변동률 사용 (POST 는
  reg + post compound)
- **본 함수는 PoC 단계** — 운영 가격으로 사용하지는 않음. etfnow.co.kr 의 값을
  추적 검증 용도.

---

## 3. ETF 메타 / 구성종목

### 3.1 ETF 기본 / 배당 메타

- **2 endpoint**:
  - `stock.naver.com/api/domestic/detail/{ticker}/ETFBase`
  - `stock.naver.com/api/domestic/detail/{ticker}/ETFDividend`
- **추출 필드**: 보수(`fundPay`) / 순자산총액 / 상장일 / 기초지수 / TTM 배당수익률 /
  전회 배당 / 기준일
- **호출 패턴**: per-ticker. `fetch_korean_etf_info_map(tickers)` 는 ticker 마다 2회
  호출 — 100 ticker = 200 호출.
- **TTL**: **300 초** (모듈 전역 dict).
- **소스 위치**: `services/etf_meta_service.py`

### 3.2 ETF 구성종목 (Holdings)

- **Endpoint**: `stock.naver.com/api/domestic/detail/{ticker}/ETFComponent`
- **응답 단위**: 단일 ETF 의 구성종목 리스트.
- **TTL**: **300 초** (별도 module-level dict `_NAVER_ETF_COMPONENT_CACHE`).
- **저장**: Mongo `stock_cache_meta.holdings_cache` (저빈도 메타 캐시).
- **갱신 주기**: cron `45 9-17 * * 1-5` — 평일 9~17시 매시 45분 (시간당 1회).
- **소스 위치**: `services/etf_holdings_service.py:fetch_korean_etf_holdings_from_naver`

#### 3.2.1 해외 구성종목 가격 보강 (Yahoo)

- 한국 ETF 의 해외 구성종목은 응답 시점에 Yahoo (`yfinance`) 로 가격 보강 — `services/component_price_service.py`.
- ISIN → Yahoo symbol 매핑 로직:
  - reuters_code (`{base}.{suffix}`) suffix 를 Yahoo 거래소 화이트리스트 (≈50개)
    와 매칭 (`T`/`HK`/`SS`/`SZ`/`KS`/`AX`/`L`/`PA`/`DE`/`TO` 등)
  - componentItemCode 6자리 + raw_code `CNE` 접두사 → 중국 본토 거래소 매핑
    (시작 `6`→`.SS`, `0`/`3`→`.SZ`, `4`/`8`→`.BJ`)
  - 일본 ISIN `JP` + 4자리 코드 → `.T`
  - 호주 ISIN `AU______XXX` → `XXX.AX`
  - 마지막 fallback: `yf.Search(query)` 결과의 첫 매치 (TTL 1시간 캐시)
- **TTL (Yahoo symbol resolution)**: 3600 초
- **TTL (foreign price)**: 300 초

### 3.3 ETF universe master

- **Source**: KIS 다운로드 (`KIS_KOSPI_MASTER_URL`, `KIS_KOSDAQ_MASTER_URL`)
- **포맷**: `.mst.zip` (정적 ZIP)
- **갱신 주기**: 미명시 — KIS 가 매일 정해진 시각에 갱신 (보통 EOD 18:00 부근).
  친구는 `load_cached_kis_domestic_etf_master()` 로 캐시 우선 사용.
- **저장**: 로컬 캐시.

### 3.4 ETF 카테고리 (테마/투자국가/섹터/지수)

- **Endpoint**: `stock.naver.com/api/stockSecurity/etfs/v1/domestic/themes`,
  `/v1/domestic`
- **카테고리 코드 18개**: 주식 / 채권 / 부동산 / 멀티에셋 / 원자재 / 통화 / 단기자금 /
  투자국가 / 배율 / 섹터 / 지수 / 혁신기술 / 투자전략 / ESG / 배당 / 단일종목 /
  트렌드 / 국내운용사
- **운영 사용**: `use=True` 인 9개 카테고리만 대표 분류로 사용.

---

## 4. 가격 시계열 (OHLCV)

### 4.1 한국 — pykrx 3-tier fallback

```python
df = stock.get_etf_ohlcv_by_date(start, end, ticker)
if df is None or df.empty:
    df = stock.get_market_ohlcv_by_date(start, end, ticker)
if df is None or df.empty:
    df = stock.get_etn_ohlcv_by_date(start, end, ticker)  # 있으면
```

- **이유**: pykrx ETF endpoint 가 신규 상장 / 6자리 신형 ticker (`0015B0` 등) /
  날짜 특정 조합에서 종종 `empty` 응답 → market 으로 보강.
- **장 시작 전 16시 이전**에는 당일분이 아직 나오지 않아 호출 skip.
- **수집 단위**: 1년 chunk (시계열 5년 이상도 1년씩 잘라서 호출).

### 4.2 해외 — yfinance

- `yf.download(ticker, period=..., progress=False, auto_adjust=True)` 로 시계열.
- 인덱스 (`^`) / 호주 종목 (`.AX`) 는 yfinance 로 직접 호출.
- 미국은 보통 yfinance + 토스 (실시간) 결합.

### 4.3 캐시 저장 — Apache Parquet on MongoDB

- **포맷**: Pickle → **Apache Parquet** 로 전환 (Numpy 버전 충돌 회피).
- **저장소**: MongoDB (Parquet 바이트를 Mongo doc 으로 저장).
- **갱신 주기**: cron `0 * * * 1-6` — 평일+토 매시 정시 (시간당 1회).
- **소스 위치**: `utils/cache_utils.py` (1045 라인), `scripts/stock_price_cache_updater.py`

### 4.4 실시간 환율

- Yahoo `KRW=X` / `AUDKRW=X` / `JPYKRW=X` / `CNYKRW=X` / `TWDKRW=X` / `HKDKRW=X` /
  `GBPKRW=X` / `EUR/GBP`
- **TTL**: 3600 초 (1시간).

---

## 5. 시장 지표 (위험 감지 후보)

### 5.1 VKOSPI (코스피200 변동성지수)

- **Source**: `kr.investing.com/indices/kospi-volatility` (HTML)
- **파싱**: 정규식 (`instrument-price-last`, `instrument-price-change-percent`)
- **TTL**: 300 초
- **인증**: 없음 (User-Agent 만)
- **위험**: HTML 구조 변경 시 파싱 실패 가능 (정규식 의존).

### 5.2 CNN Fear & Greed Index

- **Source**: `production.dataviz.cnn.io/index/fearandgreed/graphdata` (JSON)
- **추출**: `fear_and_greed.score` / `rating` / `timestamp` / `historical.previous_close`
- **TTL**: 300 초
- **인증**: 없음 (Origin / Referer 헤더 필수)

### 5.3 그 외 — 친구 프로젝트에 적재된 시장 지표

- 외국인 / 기관 수급: `scripts/collect_investor_trend.py` (520 라인) 별도 수집
  스크립트 존재 (본 분석 시점에 내부 소스 미상세 확인).

---

## 6. 자동 배치 (cron / APScheduler)

타임존 Asia/Seoul. **2026-05 이후 VM cron 폐기 → 로컬 노트북의 `run_local_scheduler.py`
가 단일 진실 소스**.

| cron 표현식 | job | 스크립트 | 의미 |
| --- | --- | --- | --- |
| `0 * * * 1-6` | `cache_refresh` | `scripts/stock_price_cache_updater.py` | 평일 + 토, 매시 정시 — 가격 시계열 캐시 갱신 |
| `45 9-17 * * 1-5` | `metadata_updater` | `scripts/stock_meta_cache_updater.py` | 평일 9~17시 매시 45분 — ETF 메타 / 구성종목 갱신 (시간당 1회) |
| `15 9-16 * * 1-5` | `data_aggregate` | `scripts/collect_data.py` | 평일 9~16시 매시 15분 — 일별 원장 / 주별 / 월별 재집계 |
| `40 9,16 * * 1-5` | `asset_summary` | `scripts/slack_asset_summary.py` | 평일 09:40, 16:40 — Slack 자산 요약 발송 |
| `0 7 * * 1-5` | `market_hours_analysis` | `scripts/analyze_market_hours.py` | 평일 07:00 — 시장시간 분석 |
| `0 8 * * 1-5` | `us_market_stocks` | `scripts/update_us_market_stocks.py` | 평일 08:00 — 미국 종목 갱신 |

### 운영 제약

- VM (OCI 1 OCPU ARM) 의 CPU 100% 다운 이슈 → cron 제거.
- 로컬 노트북 꺼져 있던 시간의 누락은 따라잡지 않음 (다음 예약 시각부터 동작).
- 모든 job 은 `infra/cron/run_batch.py` 를 통해 `batch_locks` Mongo 컬렉션의 락 사용 — 자동 / 수동 실행 충돌 방지.
- 수동 1회 실행은 `/system` 화면 버튼.

---

## 7. 캐싱 정책 통합

| 캐시 종류 | TTL | 위치 |
| --- | --- | --- |
| Naver iNAV (universe) | 30 s | 모듈 전역 dict |
| Naver ETF meta (Base/Dividend) | 300 s | 모듈 전역 dict |
| Naver ETF holdings (per-ticker) | 300 s | 모듈 전역 dict + Mongo `stock_cache_meta.holdings_cache` |
| Naver stock realtime polling | 60 s | `_TICKER_PRICE_CACHE` |
| Yahoo foreign price | 300 s | 서비스 dict |
| Yahoo symbol resolution | 3600 s | 서비스 dict |
| Toss US realtime | 60 s | `_TICKER_PRICE_CACHE` |
| AU QuoteAPI | 60 s | `_TICKER_PRICE_CACHE` |
| 환율 (Yahoo) | 3600 s | `_FX_CACHE` |
| VKOSPI / Fear&Greed | 300 s | 모듈 dict |
| 가격 시계열 (OHLCV) | persistent | MongoDB Parquet |

### 캐시 원칙 (친구 프로젝트의 4 원칙)

1. **실시간 가격 외 모든 값은 종목 캐시(`stock_cache_meta`) 에 저장.**
2. **화면 진입 시 외부 원천을 다시 호출하지 않는다** — 캐시된 메타 / 구성종목 한꺼번
   에 읽기.
3. **실패 시 stale 캐시 재사용** (TTL 지난 값이라도 retain).
4. **Next API 라우트는 응답 헤더에 `Cache-Control: no-store`** 명시 — 브라우저 /
   중간 계층 캐시 차단 (서버 캐시는 유지, 클라이언트 캐시는 0).

---

## 8. 인증키 / 헤더 정책

- **인증키**: 사용 X. 호주 QuoteAPI `APP_ID=af5f4d73c1a54a33` 평문 상수만 존재 (사실상
  공개 키).
- **User-Agent**: 모든 외부 호출에 Mozilla 가짜 UA 설정. 일부 endpoint 는 Referer +
  Origin 도 요구 (CNN / Toss 등).
- **timeout**: 일관 5~15 초. Naver 5초, Toss / KIS / VKOSPI 10~15초.

---

## 9. 우리(krx_alertor_modular) 적용 시 시사점

### 9.1 NAV / 괴리율 source 채택 후보 — 친구 프로젝트의 결정적 우위

- **현재 우리 진단**: `m.stock.naver.com/api/stock/{ticker}/integration` per-ticker (4 ticker = 4 호출 / 1 universe = 1000+ 호출 추정)
- **친구 채택**: `finance.naver.com/api/sise/etfItemList.nhn` universe 1 호출
- **권장**: `etfItemList.nhn` 을 1차 source 로 채택 검토.
  - 장점: 1 호출 = universe 전체 / 30s TTL / 인증 없음 / 단순 schema
  - 단점: 괴리율 직접 제공 X — 우리는 기존 `compute_discount_rate_pct(nav, market_price)` 그대로 재사용 가능
  - 단점: 응답에 asof (영업일) 키 없음 — 화면 진입 시각 = 응답 시각으로 처리하거나
    별도 영업일 cache 와 결합 필요
  - per-ticker 정확도가 필요한 경우만 `integration` 으로 보강

### 9.2 운영 안정성 패턴 차용 가능 항목

- **TTL + stale 재사용 패턴** — Naver 등 비공식 endpoint 일시 차단 / 5xx 발생 시
  운영 fail-stop 회피.
- **`Cache-Control: no-store`** — Next API 라우트 단일 패턴 (이미 우리도 일부 적용).
- **batch 락(`batch_locks`)** — 자동 / 수동 실행 충돌 방지 (우리는 아직 미적용).

### 9.3 위험 감지 축 시계열 후보 (우리 NEXT_ACTIONS §0-1 빈자리)

- VKOSPI (`investing.com` HTML 파싱) — 위험 감지 후보 1순위. HTML 구조 변경 위험 있음.
- CNN Fear&Greed — 한국 시장 직접 매칭 X 이나 미국 비교 지표로 참고 가능.
- 외국인 / 기관 수급 — `scripts/collect_investor_trend.py` 패턴 참고 (520 라인, 별도
  분석 필요).
- pykrx `get_market_ohlcv_by_date` — 시장 폭 / 거래량 시계열 source 후보.

### 9.4 친구 프로젝트의 운영 제약 — 우리도 동일 검토 필요

- VM (OCI 1 OCPU ARM) 의 CPU 100% 다운 이슈 → 친구는 로컬 노트북 cron 으로 전환.
  우리는 OCI push 가 아직 BACKLOG 인데, OCI 자원 한계는 동일하게 적용될 가능성.

### 9.5 친구 프로젝트와의 차별점 (보존 원칙)

우리 프로젝트의 다음 원칙은 친구 프로젝트의 패턴을 도입하더라도 **그대로 유지** 한다.

- **MongoDB 도입 X** — 우리는 SQLite (시장 데이터) + JSON (holdings / Run / 승인)
  SSOT 분리. 친구의 Mongo `stock_cache_meta` 패턴을 우리 SQLite `etf_nav_daily`
  + `etf_constituents_*` 로 직접 매핑.
- **자동 매매 X / Telegram 3-PUSH 보조 알림 유지** — 친구의 `slack_asset_summary`
  는 정기 발송이지만, 우리는 사용자 수동 승인 게이트 유지.
- **친구의 7개 cron job 을 그대로 도입 X** — 우리는 현재 사용자 PC 수동 실행
  (주 2회) 정책. cron 도입은 별도 결정 영역.

---

## 10. source 별 위험 / 안정성 자체 평가

| source | 안정성 | 위험 | 운영 도입 권장도 |
| --- | --- | --- | --- |
| Naver `etfItemList.nhn` | 높음 (단순 schema, 5년 이상 운영) | schema 변경 / 차단 | ★★★★ |
| Naver `ETFBase` / `Dividend` / `ETFComponent` | 높음 (안정 운영) | schema 변경 | ★★★★ |
| Naver `polling/domestic/stock` | 중 (실시간) | 차단 / 빠른 schema 변경 | ★★★ |
| Naver `stock/{ticker}/integration` (우리 진단) | 중 (비공식, 응답 풍부) | schema 변경 | ★★★ |
| pykrx ETF | 중 (1.0.51 ETF endpoint empty 잦음) | KRX 정책 변경 | ★★ (시계열 적재용으로만) |
| pykrx market_ohlcv | 높음 (pykrx 의 안정 endpoint) | KRX 정책 변경 | ★★★★ |
| yfinance | 높음 (해외 표준) | rate limit / Yahoo 정책 | ★★★★ |
| 토스 wts-info-api | 중 (사용자 미공개 API) | 차단 / 인증 도입 | ★★ |
| 호주 QuoteAPI | 중 (앱키 평문) | APP_ID 폐기 / 차단 | ★★ |
| Investing.com (VKOSPI) | 중 (HTML 파싱) | DOM 변경 | ★★ |
| CNN Fear&Greed | 중 (JSON 안정) | API 정책 변경 | ★★★ |
| KIS master ZIP | 높음 (정적 ZIP) | URL 변경 | ★★★★ |

---

## 11. 참고 파일 위치 (ref 기준)

- `ref/momentum-etf-main/docs/developer_guide.md` — 핵심 원칙 / 캐싱 / 서비스 계층
- `ref/momentum-etf-main/docs/project_overview.md` — 전체 구조
- `ref/momentum-etf-main/services/price_service.py` — 국가별 실시간 가격 오케스트레이션
- `ref/momentum-etf-main/services/etf_meta_service.py` — ETF Base / Dividend 메타
- `ref/momentum-etf-main/services/etf_holdings_service.py` — ETF Component 구성종목
- `ref/momentum-etf-main/services/component_price_service.py` — 해외 구성종목 Yahoo 보강
- `ref/momentum-etf-main/services/vkospi_service.py` — VKOSPI
- `ref/momentum-etf-main/services/fear_greed_service.py` — CNN Fear&Greed
- `ref/momentum-etf-main/utils/data_loader.py` — pykrx / yfinance / Naver 직접 호출 모음
  (2573 라인 — 가장 크고 핵심)
- `ref/momentum-etf-main/utils/cache_utils.py` — Parquet on Mongo 캐시
- `ref/momentum-etf-main/scripts/stock_price_cache_updater.py` — 가격 시계열 갱신
- `ref/momentum-etf-main/scripts/stock_meta_cache_updater.py` — 메타 / 구성종목 갱신
- `ref/momentum-etf-main/scripts/verify_realtime_inav.py` — 추정 iNAV PoC
- `ref/momentum-etf-main/scripts/collect_investor_trend.py` — 외국인/기관 수급 (520라인)
- `ref/momentum-etf-main/config.py` — 모든 외부 URL / 헤더 상수
- `ref/momentum-etf-main/infra/cron/crontab` — APScheduler 가 파싱하는 단일 진실 소스

---

## 12. 결론 — 우리 다음 STEP 후보 (사용자 결정 대기)

본 분석을 NAV / Discount Source Diagnosis 1차 결과와 결합하면, 가장 유력한 다음
STEP 후보는 다음 둘 중 하나다:

1. **NAV / Discount Source Adoption 1차 (Naver universe API 채택)** —
   `finance.naver.com/api/sise/etfItemList.nhn` 을 우리 `etf_nav_fetcher` 의 실
   구현으로 채택. 친구 프로젝트의 30초 TTL + stale 재사용 패턴 차용. universe
   1 호출 / 인증 없음 / pyloft 와 schema 직접 매핑.
2. **위험 감지 지표 시계열 적재 1차 (VKOSPI / Fear&Greed)** — `services/vkospi_service.py`
   + `services/fear_greed_service.py` 패턴 참고하여 우리 SQLite 에 시계열 적재. ML
   2축 중 축 2 (위험 구간 분류) 의 선행 조건.

어느 쪽을 먼저 채울지는 **사용자 결정 영역**. 두 후보 모두 우리 NEXT_ACTIONS §0-1
빈자리 후속 원칙에 부합한다.
