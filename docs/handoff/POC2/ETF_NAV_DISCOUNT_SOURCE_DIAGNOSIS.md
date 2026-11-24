# ETF NAV / Discount Source Diagnosis 1차

작성: 2026-06-06T15:18:32Z
성격: 진단 전용 — 운영 fetcher 교체 / source integration 없음.

## 1. 진단 대상 sample ticker

| ticker | name | category | reason |
| --- | --- | --- | --- |
| `069500` | KODEX 200 | domestic_representative | 국내 대표 ETF — 가장 거래량이 많고 NAV 공시가 안정적이라 추정 |
| `360750` | TIGER 미국S&P500 | overseas | 해외형 ETF — NAV 산정 / 기준시각이 국내와 다를 수 있음 |
| `411420` | Market Discovery 후보 (테마/해외형) | market_discovery_candidate | 직전 STEP Constituents Source Diagnosis 와 동일 ticker 재사용 |
| `0015B0` | KoAct 미국나스닥성장기업액티브 | user_holding | 사용자 보유 ETF — 6자리 신형 ticker (액티브) |

## 2. source별 판정

| source_id | category | judgment | 핵심 사유 |
| --- | --- | --- | --- |
| `pykrx_etf_ohlcv` | pykrx | **unusable** | 모든 ticker × 날짜 조합에서 ok 응답 0건 (empty / call_failed). |
| `pykrx_etf_price_deviation` | pykrx | **unusable** | 모든 ticker × 날짜 조합 empty / call_failed. |
| `finance_data_reader` | fdr | **hold_unstable** | FDR 은 시장 종가만 제공 — NAV 직접 제공 안 함. NAV source 와 결합 시 괴리율 계산 후보. 단독 adopt_candidate 아님. |
| `naver_mobile_stock_integration` | naver_mobile | **hold_unstable** | NAV / 시장가격 / 괴리율 모두 4/4 제공 (asof=4/4). 비공식 endpoint — schema 변경 / 차단 위험 + 운영 안정성 별도 검증 권장. 안정성 진단 후 adopt 승격 가능. |
| `naver_mobile_etf_detail` | naver_mobile | **unusable** | ETF dedicated endpoint 후보 모두 HTTP 200 응답 0건. |

## 3. source별 상세

### pykrx_etf_ohlcv

- judgment: **unusable**
- reason: 모든 ticker × 날짜 조합에서 ok 응답 0건 (empty / call_failed).

샘플 결과 (ticker × 최초 ok / 최후 시도):

  - `069500` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260530: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260529: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260528: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260417: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260331: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260530: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260529: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260528: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260417: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260331: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260530: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260529: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260528: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260417: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260331: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260530: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260529: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260528: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260417: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260331: status=empty has_nav=None has_price=None has_dev=None

### pykrx_etf_price_deviation

- judgment: **unusable**
- reason: 모든 ticker × 날짜 조합 empty / call_failed.

샘플 결과 (ticker × 최초 ok / 최후 시도):

  - `069500` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `069500` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `360750` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `411420` @ 20260603: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260605: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260604: status=empty has_nav=None has_price=None has_dev=None
  - `0015B0` @ 20260603: status=empty has_nav=None has_price=None has_dev=None

### finance_data_reader

- judgment: **hold_unstable**
- reason: FDR 은 시장 종가만 제공 — NAV 직접 제공 안 함. NAV source 와 결합 시 괴리율 계산 후보. 단독 adopt_candidate 아님.

샘플 결과 (ticker × 최초 ok / 최후 시도):

  - `069500`: status=ok has_nav=False has_price=True has_dev=False
  - `360750`: status=ok has_nav=False has_price=True has_dev=False
  - `411420`: status=ok has_nav=False has_price=True has_dev=False
  - `0015B0`: status=ok has_nav=False has_price=True has_dev=False

### naver_mobile_stock_integration

- judgment: **hold_unstable**
- reason: NAV / 시장가격 / 괴리율 모두 4/4 제공 (asof=4/4). 비공식 endpoint — schema 변경 / 차단 위험 + 운영 안정성 별도 검증 권장. 안정성 진단 후 adopt 승격 가능.

샘플 결과 (ticker × 최초 ok / 최후 시도):

  - `069500`: status=ok has_nav=True has_price=True has_dev=True
  - `360750`: status=ok has_nav=True has_price=True has_dev=True
  - `411420`: status=ok has_nav=True has_price=True has_dev=True
  - `0015B0`: status=ok has_nav=True has_price=True has_dev=True

### naver_mobile_etf_detail

- judgment: **unusable**
- reason: ETF dedicated endpoint 후보 모두 HTTP 200 응답 0건.

샘플 결과 (ticker × 최초 ok / 최후 시도):

  - `069500`: status=ok has_nav=None has_price=None has_dev=None
  - `360750`: status=ok has_nav=None has_price=None has_dev=None
  - `411420`: status=ok has_nav=None has_price=None has_dev=None
  - `0015B0`: status=ok has_nav=None has_price=None has_dev=None

## 4. 기존 schema fit

- `etf_nav_daily` 컬럼: etf_ticker / asof / nav / market_price / discount_rate_pct / source / status / message.
- pykrx 후보가 `adopt_candidate` 일 경우 시장가격은 ohlcv 종가, NAV 는 NAV 컬럼, source 라벨은 `pykrx/etf_ohlcv` 권장.
- 괴리율은 source 가 직접 제공하면 그 값을 우선 사용, 그렇지 않으면 기존 `compute_discount_rate_pct(nav, market_price)` 재사용.

## 5. K6 / EOD 방어 가능성

- pykrx 후보: 단일 호출 1초 내외 / 1ticker = 1API call. 10개 후보 + delay 적용 가능, 30초 budget 안에 들어옴. cache-first / 실패 격리 패턴 적용 가능.
- Naver mobile 후보: 비공식 — 차단 / schema 변경 위험. K6 적용은 채택 결정 후 별도 운영 안정성 STEP 에서 검증.

## 6. 결론 / 다음 STEP 추천

- adopt_candidate 0건. 다음 STEP 후보: 사용자 결정 — 다른 빈자리 (구성종목 가격 시계열 / 위험 감지 지표 시계열) 로 이동하거나 KRX OPEN API (auth_required) 확보 검토.

## 7. 본 STEP 에서 하지 않은 것

- 운영 NAV fetcher 교체.
- NAV / 괴리율 source integration.
- 전체 universe NAV 수집 / 정기 job 추가.
- 신규 API / 괴리율 threshold 변경 / Telegram 변경.
