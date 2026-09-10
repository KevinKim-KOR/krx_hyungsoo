# POC3-OPS-02B — 08:00 시장 브리핑 재개발 · 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude) · **수신**: 설계자
- **작성일**: 2026-09-08
- **대응 설계서**: `docs/ai_design/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_DESIGN_V1.md`
- **개정 이력**

  | 판 | 내용 |
  |---|---|
  | V1 (2026-09-08) | 최초 제출 — 모호점 6건 |
  | **V1.1** (2026-09-08) | 설계자 **`APPROVED_WITH_REQUIRED_EDITS`**. 모호점 6건 확정 · Step **2분할** · 필수 수정 3건 |
  | **V1.2** (2026-09-09) | **probe 3종 실행 결과 + 설계자 정정 반영.** `OPEN_GAP` 원천 **KRX Open API 무조정가** 확정 · USD/KRW **PIT 분리** · `SECTOR=NOT_EVALUATED` 확정 + **`INDEX_LEADERSHIP` 신설** · 신규 결함 등재 |
  | **V1.3** (2026-09-10) | `OPS-02B-1` Gate 실행 완료 · 계약 불일치 2건 질의 |
  | **V1.4** (2026-09-10) | 설계자 최종 판정 반영 — `SP500_SIGN_V1` · 공식 CSV snapshot · `n≥2` · 정합성 7건 |
  | **V1.5** (2026-09-10) | 검증자 r1 `REJECTED` 대응 — benchmark 실패 성공 위장 제거 · 테스트의 라이브 DB 쓰기 차단 · 재현 경로 확보(§17) |
  | **V1.6** (2026-09-10) | 검증자 `VERIFIED_WITH_NOTES` (커밋 `988b0494`) — fail-closed 계약을 코드에 연결 · 결과서 실측값 정정 · 계약 테스트 15건 |
  | **V1.7** (2026-09-11) | **설계자 최종 판정 — `OPS-02B-1` `CLOSED`.** 이월을 **`02B-2` 필수 2건 / BACKLOG 2건**으로 분리(§18). **정적 CSV 자동 다운로드는 범위 밖** |

- **상태**: **`OPS-02B-1` `CLOSED`** — 설계자 최종 Gate 확정 (2026-09-11).
  결론 **§14** · 이월 분리 **§18**. 다음은 **HANDOFF → `OPS-02B-2` DESIGN**. `OPS-02B-2` 는 `02B-1` 판정 이후
- **probe 3종 완료** (2026-09-09) — 읽기 전용. 적재·DB 쓰기 0건
- **조사 범위**: 로컬 저장소·로컬 DB·**OCI 읽기 전용**. 쓰기·발송·수집 실행 **0건**

---

## 0. 결론 요약 — probe 실측 후 (V1.2)

V1 조사 시점의 "데이터 3축이 모두 비어 있다"는 판단은 **probe 로 갱신됐습니다.**

| 축 | V1 판정 | **probe 실측 (V1.2)** |
|---|---|---|
| 예측 대상 `KODEX200_OPEN_GAP` | BLOCKED (`open` 126일) | **해소** — KRX Open API 가 **2015-09-02 이후 무조정 시가·종가** 제공 |
| 미국 입력 6종 | BLOCKED (VIX 1종) | **해소** — FDR 로 6종 전부 확보 (§2.1) |
| 섹터 분류 | BLOCKED | **`SECTOR=NOT_EVALUATED` 확정** — 구조화된 업종·테마 분류 필드가 CSV·API 모두에 없음 |
| — | — | **`INDEX_LEADERSHIP=AVAILABLE` 신설** — 공식 기초지수 흐름으로 대체 (§7) |

**현재 Gate 상태**

```text
implementation      = CONTINUE
outlook_gate        = RUNNABLE_AFTER_PIT_CORRECTION
sector              = NOT_EVALUATED
index_leadership    = AVAILABLE
krx_credentials     = AVAILABLE_AND_IN_USE
database_backfill   = DEFERRED
operating_rule      = SP500_SIGN_V1
```

> `krx_credentials` 는 V1.2 시점 `NOT_REQUIRED` 였으나, 사용자가 기존 발급분을
> `.env` `KRX_API_KEY` 로 제공해 **확보·사용 중**이다. 추가 발급 요청은 하지
> 않았다.

`SECTOR=NOT_EVALUATED` 는 **02B 전체를 막는 조건이 아닙니다.** 다만 기초지수
흐름을 **섹터 완료로 기록하지 않습니다.**

| Step | 범위 | 상태 |
|---|---|---|
| **`OPS-02B-1`** Market Input Readiness & Validity Gate | probe·평가·판정 · KOSPI/VIX 결함 수정 | **실행 중** |
| **`OPS-02B-2`** Market Briefing Message & Operation | 메시지·반복 억제·PUSH | Gate 판정 후 |

`02B-1` 에서 **Telegram 본문·반복 억제·autosend 활성화는 구현하지 않습니다.**
`08:00 autosend 는 계속 `false`** 입니다.

---

## 1. 기존 코드·DB에서 재사용 가능한 데이터

### 1.1 재사용 가능 — 그대로 씀

| 자산 | 위치 | 실측 |
|---|---|---|
| KODEX200 일별 종가 | `etf_daily_price` (`069500`) | 3,045행 · 2014-04-09 ~ **2026-09-07**(OCI) |
| ETF 일별 종가 전체 | `etf_daily_price` | 1,392,746행 · OCI 최신 **2026-09-07** |
| **walk-forward 구조** | `app/market_flow_walk_forward.py` (499줄) | **구조만** — 날짜 정렬 · 기준일별 학습 · walk-forward · baseline 비교 · 결과 집계 |
| PIT 패턴 | `app/market_flow_dataset.py` (452줄) | VIX **strictly-prior** 처리 방식 (`vix_source_date`·`vix_lag_calendar_days`) |
| PUSH 파이프라인 | `market_briefing` kind · 08:00 cron · PARAM · registry · flag guard | **전부 살아 있음**. cron 유지, flag `false` |
| 반복 억제 골격 | `holdings_risk_state.py` (OPS-02A) | `worst_state` 패턴 → §9 fingerprint 에 재사용 |

> **재사용 범위 (설계자 확정 §12.7-1)** — `market_flow_*` 에서 재사용하는 것은
> **구조뿐**입니다. **기존 20일 target · feature · 학습 artifact · 3모델
> predictor 는 재사용 대상이 아닙니다.**
>
> ```
> 기존 target : t 이후 20번째 KODEX200 거래일 수익률  (TARGET_HORIZON_DAYS=20)
> 설계 target : 당일 KODEX200 시가 / 직전 거래일 종가 - 1  (overnight gap)
> ```
>
> `02B-1` 은 **투명한 단순 baseline 으로 시작**하며 **신규 ML 튜닝·앙상블을
> 하지 않습니다.** 기존 artifact 는 읽지도 쓰지도 않습니다.

### 1.2 있으나 쓸 수 없음

| 자산 | 실측 | 사유 |
|---|---|---|
| `market_benchmark_daily_price` KOSPI | OCI **2026-07-03** 정체 (로컬 2026-09-04) | §4 결함 대상 |
| 동 VIX | **2026-07-03** 정체 (3,079행) | 2개월 stale — 설계 §7 위반 |
| `etf_constituents` | OCI **24 / 1,146 ETF (2.1%)** · asof 2026-06-17~08-20 | 섹터 대체 불가 |
| `etf_master.category` | 결측 0% 이나 값이 **`"1"`~`"7"`** | 자산군 코드. 섹터 아님 |
| `market_risk_feature_daily` | 3,018행 · **2026-08-27** 까지 | 국내 지표만. 미국 입력 없음 |

---

## 2. [V1.2] probe 실측 — 미국 지표와 `OPEN_GAP` 원천

2026-09-09 실행. **읽기 전용 · 적재 0건.**

### 2.1 미국 지표 6종 — 전부 확보 (FDR)

| 지표 | symbol | 행수 | `Close` 결측 | 구간 |
|---|---|---|---|---|
| S&P500 | `US500` | 2,937 | 0 | 2014-12-31 ~ 2026-09-04 |
| Nasdaq | `IXIC` | 2,937 | 0 | 〃 |
| 반도체 | **`^SOX`** | 2,937 | 0 | 〃 |
| Russell 2000 | `RUT` | 2,937 | 0 | 〃 |
| VIX | `VIX` | 3,049 | 110 | 2014-12-31 ~ 2026-09-07 |
| USD/KRW | `USD/KRW` | 3,049 | 8 | 2014-12-31 ~ 2026-09-06 |

- **`SOX` 는 실패**(`KeyError: 'timestamp'`), **`^SOX` 로만 조회됩니다.**
- 재현성: 동일 구간 2회 호출 결과 **일치**.
- 미국 지수 최종일이 `2026-09-04` 인 것은 **2026-09-07 이 미국 휴장(Labor Day)**
  이기 때문입니다. VIX 가 09-07 값을 갖는 것은 **원천 이상 징후**로 기록합니다.

### 2.2 `OPEN_GAP` 원천 — **KRX Open API 무조정가** (설계자 정정 §1 확정)

```text
OPEN_GAP_t  = KRX t일 무조정 시가 / KRX 직전 거래일 무조정 종가 - 1
source      = KRX_OPEN_API
price_basis = UNADJUSTED_TRADED_PRICE
endpoint    = https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd
```

**왜 조정 계열이 아닌가** — `OPEN_GAP` 은 밤사이 갭을 재는 지표인데, **배당조정
계열은 배당락일의 갭을 인위적으로 지웁니다.** 측정 대상 자체가 훼손됩니다.

**확정 계약**

| # | 계약 |
|---|---|
| 1 | 시가·종가 **모두 KRX Open API 단일 원천** |
| 2 | FDR 시가와 DB 종가를 **혼합하지 않는다** |
| 3 | `etf_daily_price` 의 `open`·`close` 를 **수정·덮어쓰지 않는다** |
| 4 | 일별 응답 전체를 적재하지 않고 **`069500` 평가 행만** 추출 |
| 5 | 조회 구간·행 수·결측률·수집 시각·**snapshot hash** 기록 |
| 6 | 운영 적재 구조는 **Gate 결과 후 02B-2 에서** 결정 (`database_backfill = DEFERRED`) |

**한계 기록** — KRX 무조정가에는 **분배락에 따른 실제 가격 변화**가 포함됩니다.
공식 분배락 날짜를 확보하면 민감도 결과를 별도 보고하고, 확보하지 못하면
**임의 보정하지 않고 한계로 기록**합니다.

결과 표현은 **"미국시장과 개장 갭의 예측 관계"** 로 제한하고 **인과관계로
단정하지 않습니다.**

### 2.3 API 접근 실측

| 항목 | 결과 |
|---|---|
| 인증 | `.env` `KRX_API_KEY`(40자리 hex, gitignore 대상). 헤더 `AUTH_KEY` |
| host | `data-dbg.krx.co.kr` **만** 동작. `openapi.krx.co.kr`·`data.krx.co.kr` 은 404 |
| 응답 | 1일 1,167행(2026-09-04). 필드 19개 |
| 과거 범위 | **2015-09-02 확인** (그때 ETF 186종, `069500` 포함) |
| 비용 | 평균 **0.30초/호출** → 2,800 거래일 약 **14분** |
| pykrx | `KRX_ID`/`KRX_PW` 요구 → 사용 불가 |
| KRX 웹 JSON | 세션 쿠키 확보 후에도 `HTTP 400 LOGOUT` → 사용 불가 |

### 2.4 [신규 결함] `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY`

```text
status = INVESTIGATION_REQUIRED   (이번 Step 에서 수정하지 않음)
```

같은 날짜 종가를 세 원천에서 대조한 실측:

| 날짜 | KRX / DB | FDR / DB |
|---|---|---|
| 2020-09-02 | **+11.687%** | −0.645% |
| 2023-06-01 | **+5.237%** | −0.646% |
| 2026-03-06 | **+0.000%** | −0.644% |
| 2026-04-20 | +0.646% | **+0.000%** |

- KRX 와의 괴리가 과거로 갈수록 커지는 것(6년 11.7%, 3.3년 5.2% ≈ 연 1.8%)은
  KODEX200 분배금 수익률과 부합합니다 → **KRX = 무조정, DB·FDR = 조정 계열**
- 다만 **DB 자신이 구간마다 다른 기준**을 보입니다 — 2026-03-06 은 KRX 와 일치,
  2026-04-20 은 FDR 과 일치. **`NAVER_FDR` 이라는 source 표기만으로 실제 조정
  기준을 확정할 수 없습니다.**

**이번 Step 에서는 읽기 전용 기록만** 합니다 — 전체 기간 KRX/DB 비율 변화 ·
전환 후보일 · 영향 ticker 범위 · 수익률·ML·UI·PUSH 소비 경로 · 현재 운영 수치
실영향 여부. **KRX 단일 원천으로 수행하는 Gate 평가를 막지 않습니다.**

---

## 3. [V1.2] 섹터 판정 — **`SECTOR = NOT_EVALUATED` 확정**

### 3.1 probe 실측

| 원천 | 결과 |
|---|---|
| KRX **ETF 종목 기본정보 CSV** (사용자 제공, 1,168행 17컬럼) | 기초지수명·지수산출기관·추적배수·복제방법·기초시장분류·기초자산분류 **있음**. **업종/테마 분류 없음** |
| KRX **Open API** 필드 19개 | `IDX_IND_NM` 은 **기초지수명**(`코스피 200`·`S&P 500`·`NICE K반도체 TOP2 MAX+ 지수`). **업종·테마 분류 아님** |
| `pykrx` | 인증 요구 → 사용 불가. ETF→기초지수 매핑 함수 자체가 없음 |

`기초시장분류`(국내 645·해외 467·국내&해외 56)와 `기초자산분류`(주식 849·채권
162·혼합 81·기타 26·원자재 24·부동산 14·통화 12)는 **지역·자산군이지 섹터가
아닙니다.**

### 3.2 확정 (설계자 §4 · 정정 §3)

```text
SECTOR = NOT_EVALUATED
```

- 확보한 메타데이터에 **구조화된 업종·테마 분류가 없습니다.**
- **기초지수명 문자열을 해석해** 반도체·바이오·2차전지 등으로 임의 분류하지
  않습니다.
- **Naver 분류나 ETF 이름 추론으로 우회하지 않습니다.**
- **사용자에게 추가 계정 발급을 요청하지 않았습니다.** 기존 발급분을 제공받아
  `krx_credentials = AVAILABLE_AND_IN_USE` 다 (§0).
- **API Key 가 섹터 분류를 해결한 것으로 기록하지 않습니다.**

이 판정은 **시장 브리핑 전체를 막는 조건이 아닙니다.**

---

## 4. KOSPI/VIX 결함의 실제 원인과 수정 위치

`DEF-KOSPI-BENCHMARK-VALUE-ASOF-INTEGRITY` 는 **원인이 둘**입니다.

### 4.1 원인 ① 갱신이 멈춰 있다 (운영)

§2.4 참조. OCI 07:20 배치에 benchmark 갱신이 **없습니다.**

- 증거: OCI `KOSPI` max = `2026-07-03`, `VIX` max = `2026-07-03`,
  `etf_daily_price` max = `2026-09-07`
- **수정 위치**: `scripts/run_oci_market_data_batch.py` — ETF 가격 갱신 뒤
  benchmark 갱신 단계 추가. **확정 계약 (설계자 §12.7-3)**:

  | # | 계약 |
  |---|---|
  | 1 | ETF 가격 성공과 benchmark 성공을 **별도 상태로 기록** |
  | 2 | benchmark 실패를 **전체 배치 성공으로 숨기지 않는다** |
  | 3 | benchmark 실패 때문에 **정상 ETF 가격 적재까지 롤백하지 않는다** |
  | 4 | 각 benchmark **자기 `as_of_date`** 사용 |
  | 5 | **stale 이면 소비 문장 생성 금지** |
  | 6 | **위치 인덱스 대신 거래일 날짜 기준**으로 수익률 계산 |

### 4.2 원인 ② 값이 자기 기준일을 잃는다 (계산·표시)

```python
# app/market_regime.py:115
def compute_kospi_metrics(history):
    closes = [c for _, c in history if c is not None and c > 0]   # ← 날짜 폐기
    ...
    "return_1m_pct": _round_pct(_return_n_days_back(closes, LOOKBACK_1M)),
```

`_return_n_days_back(closes, n)` 은 `closes[-1]` 과 `closes[-(n+1)]` 의 비율로,
**위치 인덱스**입니다(`market_regime.py:58-62`). 결과 dict 에 **자기 `as_of_date`
가 없습니다.**

그리고 `compute_market_context(asof=..., kodex200_history, kospi_history)` 는
**최상위 `asof` 하나**만 두고 그 아래에 `kospi` 를 넣습니다
(`market_regime.py:320-`). KODEX200 은 2026-09-07 인데 KOSPI 는 2026-07-03 인
상황에서 **KOSPI 값이 2026-09-07 로 표시**됩니다. 이것이 결함의 표시 층위입니다.

부수 문제: 위치 인덱스라 KOSPI 에 결측일이 있으면 "20거래일 전"이 실제 20거래일
전이 아닙니다.

**수정 위치 (4층위)**

| 층위 | 파일 | 조치 |
|---|---|---|
| 계산 | `app/market_regime.py` | `compute_kospi_metrics` 가 **자기 `as_of_date` + `freshness`** 반환. 날짜 기준 조회로 교체(위치 인덱스 폐기) |
| 조립 | 동 `compute_market_context` | benchmark 별 `as_of_date` 분리. 전역 `asof` 로 덮지 않음 |
| 소비 | `app/market_summary_composer.py` (`summarize_market_position`·`build_data_status`) | 각 benchmark 자기 날짜 사용. stale 이면 **문장 미생성** |
| 소비 | OCI PUSH · API · Mac UI | 전수 grep 후 일괄 (착수 시 열거) |

### 4.3 [V1.2] 최소 계약 7개 (설계자 §6)

| # | 계약 |
|---|---|
| 1 | OCI 운영 배치에서 **KOSPI·VIX 갱신 경로 확보** |
| 2 | 각 benchmark 가 **자신의 `as_of_date` 유지** |
| 3 | 날짜를 버린 위치 인덱스가 아니라 **실제 거래일 기준** 수익률 계산 |
| 4 | **최신성 1거래일을 벗어나면 수익률 미산출** |
| 5 | stale benchmark 를 **다른 최신 `market_context.asof` 로 표시하지 않음** |
| 6 | KOSPI·VIX 중 **일부만 실패하면 실패한 블록만 제외** |
| 7 | 기존 stale VIX 의 과거 ML·시장 evidence 영향은 **읽기 전용 확인**. **ML 재학습으로 확대하지 않음** |

수정 후에도 **08:00 autosend 는 계속 `false`** 입니다. 실제 발송은 `02B-2`
목업과 사용자 확인 이후입니다.

### 4.4 판정 원칙

KODEX200 과 KOSPI 수익률 차이가 크다는 사실만으로 어느 쪽을 정답으로 두지
않습니다. **원천 행을 직접 읽어 독립 재계산**한 값과 대조해 판정합니다.
`market_discovery.extra_notes` 의 KOSPI 문장은 검증 종료 전까지 새 브리핑에서
재사용하지 않습니다(설계 §6).

---

## 5. [V1.2] 미국–한국 PIT 정렬 — **USD/KRW 분리**

### 5.1 두 갈래로 나눕니다 (설계자 §3)

V1.1 의 "6종 모두 16:00 ET 종료 기준" 판정은 **그대로 인정되지 않습니다.**

| 그룹 | 규칙 |
|---|---|
| **S&P500 · Nasdaq · `^SOX` · Russell 2000 · VIX** | **미국 세션 종료(16:00 ET) < 한국 개장(09:00 KST)** 인 가장 최근 미국 세션일 |
| **USD/KRW** | 해당 **일별 종가의 실제 제공 완료 시각**이 한국 개장 전임을 **확인해야** 사용 |

**USD/KRW 처리**

- 제공 완료 시각을 **증명할 수 없으면 primary feature 에서 제외**합니다.
- 필요하면 **한국 개장일보다 날짜가 엄격히 앞선 행만** 쓰는 **보조 민감도
  평가**로 제한합니다.
- **`07:50 현재 환율` 등의 표현은 금지**합니다.

### 5.2 구현 규칙

- ET→KST 오프셋은 서머타임에 따라 달라지므로 **표준 `zoneinfo`** 로 처리하고
  **상수로 두지 않습니다.**
- 한국 연휴 뒤에는 여러 미국 세션이 누적되므로 **가장 최근 1개만** 쓰고 누적
  개수를 진단에 남깁니다.
- benchmark 별 **timezone·통상 종료시각은 코드의 정적 catalog**.

### 5.3 재산출 의무

**이 규칙을 적용한 뒤 정렬 표본 수와 커버리지를 다시 산출하고, 실제 Gate 에
사용한 feature 집합을 명시합니다.** (V1.1 의 `2,755일 / 96.1%` 는 USD/KRW 를
16:00 ET 기준으로 포함한 수치라 **그대로 쓰지 않습니다.**)

---

## 6. 사전 평가 실행 방법과 판정

### 6.1 [V1 당시 조사 — 현행 아님] 데이터 확보 전에는 실행할 수 없었다

> **아래는 V1(2026-09-08) 조사 시점의 값이다.** probe 로 전부 해소됐다 —
> 현행은 **§2 · §14** 다. 이력 보존용으로 남긴다.

설계 §4 최소 검증 계약은 **정렬 표본 750일 이상**을 요구합니다. 예측 대상
`KODEX200_OPEN_GAP` 의 분자인 `open` 은 **126일**뿐입니다(§2.4). 미국 입력 5종은
**0일**입니다.

> **현재 상태로 평가를 돌리면 `REJECT` 가 아니라 "표본 부족으로 평가 불가"** 가
> 나옵니다. 이것을 `REJECT` 로 기록하면 "관계가 없다"는 잘못된 결론이 남습니다.
> 그래서 설계자가 **`NOT_EVALUATED` 를 신설**했습니다(§12.4).

### 6.2 데이터 확보 후 실행 절차

1. **KRX Open API snapshot** 구축(`069500` 행만) → 실측 표본 일수 보고
2. **USD/KRW 분리 규칙 적용 후** 정렬 표본·커버리지 **재산출** (§5.3)
3. `market_flow_walk_forward` 의 **구조만** 참조해 anchor 구성 — 날짜 정렬 ·
   기준일별 학습 · walk-forward · baseline 비교 · 결과 집계. **기존 target ·
   feature · artifact · 3모델 predictor 는 쓰지 않습니다.** 모델은 **투명한
   단순 baseline** 으로 시작하고 ML 튜닝·앙상블을 하지 않습니다
4. 방향 적중률 + 95% CI(정규근사 아닌 **bootstrap**), 다수 방향 baseline 대비
   개선폭, 상·하위군 개장 수익률 차이 bootstrap CI
5. 판정

| 조건 | 판정 |
|---|---|
| 표본·커버리지·적중 CI 하한 >50% · baseline +5%p 이상 · 군간 차이 CI >0 **전부 충족** | `ADOPT_OUTLOOK` |
| 표본·커버리지는 되나 통계 기준 미달 | `FACT_ONLY` |
| 표본·커버리지 자체 미달 (`open` 750일 미만 포함) | **`NOT_EVALUATED`** |
| **충분한 데이터로 평가**했으나 사전 기준 미달 | `REJECT` |

`NOT_EVALUATED` 를 `REJECT` 에 포함하지 않습니다(설계자 §12.4). 문구를 약하게
바꿔 통과시키지 않고, **소표본으로 임계값을 완화하지 않습니다**.

미국시장 **사실**과 상승 **섹터**는 **각각 독립적으로** 사용 가능성을
판정합니다 — 전망이 `NOT_EVALUATED` 여도 섹터는 `AVAILABLE` 일 수 있습니다.

---

## 7. [V1.2] `INDEX_LEADERSHIP` — 최근 강한 기초지수

```text
INDEX_LEADERSHIP = AVAILABLE
화면·메시지 명칭 = 최근 강한 기초지수
```

**이것을 `상승 섹터` 라고 부르지 않습니다.** 08:00 메시지에서도 표시하지
않습니다. 공식 지수 분류에 따른 **가격 흐름**이지 섹터 상승을 검증한 결과가
아니며, 그 사실을 결과서에 명시합니다.

### 7.1 산출 계약 (설계자 §5)

| # | 계약 |
|---|---|
| 1 | 식별키 = **`지수산출기관 + 기초지수명` 완전일치** |
| 2 | **fuzzy matching·의미 추론 금지** |
| 3 | 기초자산이 **주식인 상품만** 대상 |
| 4 | **레버리지·인버스 제외** (`추적배수` ≠ `일반` 제외) |
| 5 | **합성 상품 제외** (`복제방법` 에 `합성` 포함 시 제외) |
| 6 | 같은 기초지수 추종 ETF 는 **하나의 그룹**으로 중복 제거 |
| 6-b | **`minimum_distinct_tickers_per_index = 2`** — 필터 적용 후 서로 다른 ETF 코드가 **2개 이상**인 기초지수만 후보. `n=1` 은 **진단에는 남기되 PUSH 후보에서 제외**하고 **fallback 으로 부활시키지 않는다**. 운용사 상이 조건은 구조화된 운용사 필드가 없어 **추가하지 않는다** |
| 7 | 그룹 수익률 = 추종 ETF 들의 **중앙값** |
| 8 | **5거래일·20거래일 수익률이 모두 양수**인 기초지수만 후보 |
| 9 | **20거래일 수익률 기준 상위 2개**까지만 표시. 상위 2개가 없으면 **실제 존재하는 개수만** 표시 |
| 10 | **추종 ETF 수와 가격 기준일**을 evidence 에 기록 |

### 7.2 [V1.4] 메타데이터 운영 계약 — 원천 2분리

> V1.2 의 "수동 CSV 는 운영 정본으로 쓰지 않는다" 는 **설계자가 수정**했다.
> API 에 정적 필드가 없다는 실측(§15-1)이 확인됐기 때문이다.

| 역할 | 원천 | 주기 |
|---|---|---|
| ticker · **최신 기초지수명** | **KRX Open API 일별 응답** | 매일 |
| `지수산출기관` · `추적배수` · `복제방법` · `기초자산분류` | **공식 KRX 기본정보 CSV 의 versioned snapshot** | 저빈도 |

**CSV 사용 계약**

| # | 계약 |
|---|---|
| 1 | `source = KRX_OFFICIAL_CSV` |
| 2 | **기준일 · 파일 hash · 행 수** 기록 |
| 3 | API ticker 와 **정확히 join** |
| 4 | API `IDX_IND_NM` 과 CSV `기초지수명` 이 **일치하는 종목만** 사용 |
| 5 | 신규 ticker·지수명 불일치는 **임의 보완하지 않고 제외** |
| 6 | join coverage **95% 미만이면 기초지수 블록 전체 미산출** |
| 7 | API 와 불일치 발생 시 **공식 CSV 교체 필요 상태로 기록** |

CSV 는 **일별 시세 정본이 아니라 저빈도 정적 속성 reference** 다. **수동 편집본·
개발자가 가공한 분류표는 허용하지 않는다.**

**과거 2,800일 메타데이터 전체 backfill 은 하지 않는다.**

### 7.3 join coverage 게이트

현재 ETF universe 와의 join coverage 를 측정합니다.

| coverage | 처리 |
|---|---|
| **≥ 95%** | 기초지수 블록 **사용 가능** |
| **< 95%** | 해당 블록 **미산출** |
| 미매칭 상품 | **임의 추론하지 않고 제외** |

### 7.4 메시지 표현

```text
오늘 볼 기초지수
• ○○지수: 5일 +x.x% · 20일 +x.x% (추종 ETF n개 기준)
```

---

## 8. [V1.2] 목업 — **Gate 판정 후 작성**

설계자 정정 §4: **본문을 지금 확정하지 않고 OUTLOOK Gate 를 먼저 실행합니다.**
목업은 `02B-2` 산출물이며, 판정에 따라 구성이 달라집니다.

| OUTLOOK 판정 | 목업 구성 |
|---|---|
| `ADOPT_OUTLOOK` | 한국 개장 압력 전망 + **최근 강한 기초지수** |
| `FACT_ONLY` | 예측 표현 없이 미국시장 **관측 사실** + 최근 강한 기초지수 |
| `REJECT` | 미국→한국 예측 **제외**, 기초지수 중심 |
| `NOT_EVALUATED` | **원인 명시** 후 기초지수 중심 |

**`REJECT` 또는 `NOT_EVALUATED` 가 나와도 세 번째 PUSH 를 폐기하지 않습니다.**
최소 본문 목업을 사용자에게 보여준 뒤 운영 가치 여부를 판정합니다.

모든 evidence 가 불가능한 경우에만 `REMAIN_BLOCKED` 입니다.

---

## 9. 상태 fingerprint 와 반복 억제

> **본 절도 `OPS-02B-2` 범위입니다.** `02B-1` 에서 구현하지 않습니다.

OPS-02A 의 상태 파일 패턴을 재사용합니다(신규 발명 없음).

```
state_fingerprint = f"{outlook_state}#{index_leadership_state}"
  outlook_state          = UP | MIXED | DOWN | NONE   (SP500_SIGN_V1 방향 압력)
  index_leadership_state = 상위 기초지수명을 정렬해 '|' 로 결합 (없으면 NONE)
```

| 상황 | 발송 |
|---|---|
| fingerprint 변경 | **발송** |
| 동일 | `no_change` **미발송** |
| 전 데이터 stale | 미발송 · 이력만 |
| 문장 생성 실패 | 미발송 · 이력만 |
| 다음 거래일 | 상태 유지(일 단위 비교) |

- 저장 경로: `state/three_push/market_briefing_state_latest.json`
- **발송 성공 뒤에만 저장** (OPS-01A/02A 와 동일 계약)
- 근거 수치(−1.2% 등)는 **fingerprint 에 넣지 않습니다** — 넣으면 매일 바뀌어
  억제가 무력화됩니다. OPS-02A 에서 확정한 원칙입니다.
- registry 중복키 슬롯: **일 단위**(08:00 1회이므로 `HH:MM` 불필요)

---

## 10. 테스트·역검증 계약

**Step 별로 나눕니다.** `02B-1` 은 데이터·판정만, `02B-2` 는 본문·억제.

### 10.1 `OPS-02B-1` (이번 착수 범위)

| # | 무력화 | 기대 |
|---|---|---|
| R-1 | 미국 관측일을 한국 날짜와 **같은 문자열로 연결** | 탐지 |
| R-2 | ET→KST 오프셋을 **상수로 고정**(DST 무시) | 탐지 |
| R-2b | **USD/KRW 를 미국 지수와 같은 16:00 ET 기준**으로 처리 | 탐지 |
| R-3 | **당일 미국 종가**(한국 개장 후 확정)를 입력에 포함 | 탐지 |
| R-4 | walk-forward 를 전체 fit 재사용으로 | 탐지 |
| R-5 | **표본 부족인데 `REJECT`** 로 기록 | 탐지 |
| R-6 | 통계 미달인데 `ADOPT_OUTLOOK` | 탐지 |
| R-7 | 750일 미만에서 **임계값 완화**해 평가 실행 | 탐지 |
| R-8 | Gate 가 **`etf_daily_price` 를 수정**(open/close backfill) | 탐지 |
| R-8b | KRX 시가와 **DB·FDR 종가를 혼합**해 `OPEN_GAP` 계산 | 탐지 |
| R-8c | **조정 계열**(FDR)로 `OPEN_GAP` 계산 | 탐지 |
| R-9 | 기초지수명 **문자열을 해석**해 섹터로 묶음 | 탐지 |
| R-10 | 구조화 분류 필드가 없는데 **Naver 분류 자동 채택** | 탐지 |
| R-11 | 동일 기초지수 복제 상품을 개별 계수 | 탐지 |
| R-12 | 기초지수 그룹 수익률을 중앙값 아닌 **최대값**으로 | 탐지 |
| R-12b | 레버리지·인버스·합성 상품을 **포함** | 탐지 |
| R-12c | join coverage **95% 미만인데 블록 산출** | 탐지 |
| R-12d | 기초지수 흐름을 **`상승 섹터`로 표기** | 탐지 |
| R-13 | KOSPI 값을 **전역 `asof`** 로 표시 | 탐지 |
| R-14 | 위치 인덱스 수익률 복원(날짜 무시) | 탐지 |
| R-15 | benchmark **실패를 배치 성공으로** 기록 | 탐지 |
| R-16 | benchmark 실패로 **ETF 가격 적재까지 롤백** | 탐지 |
| R-17 | stale benchmark 로 문장 생성 | 탐지 |
| R-18 | 기존 행에 **timestamp 소급 생성** | 탐지 |
| R-19 | probe 없이 symbol 적재 | 탐지 |

### 10.2 `OPS-02B-2` (다음 Step)

`fingerprint 에 근거 수치 포함` · `동일 상태인데 발송` · `미발송인데 상태 저장` ·
`'별도 확인 필요' 목록 부활` · `flag guard 앞에서 skip·fail 결정` · `상위 2개
제한 제거` · **`충족 기초지수 0인데 빈 문단 출력`** · `정확한 등락률을 예측값으로 표시`.

### 10.3 운영 규칙

`atexit` + SIGTERM/SIGINT/SIGHUP 원본 복원 · 적용·복원 양쪽 `__pycache__` 삭제 +
`PYTHONDONTWRITEBYTECODE=1` · 대상 문자열 없으면 **오류로 중단**(조용한 SKIP
금지) · **발송 0건**(sender mock) · 라이브 state·DB 미접근(`tmp_path` 주입 +
conftest 감지). OPS-01A·02A 에서 실제 사고가 났던 항목들입니다.

**흐름 통과 테스트 필수** — 단위만으로는 배선 유실을 못 잡습니다(OPS-01A
`avg_buy_prices`, OPS-02A `unavailable` 이 실제로 미탐지였습니다).

## 11. 변경 예상 파일과 OCI 배포 영향

### 11.1 예상 변경 — `OPS-02B-1` 범위

| 파일 | 성격 |
|---|---|
| `app/market_regime.py` | **수정** — benchmark 별 `as_of_date`·freshness, **날짜 기준** 수익률 |
| `app/market_summary_composer.py` | 수정 — 자기 날짜 사용, stale 시 문장 미생성 |
| `scripts/run_oci_market_data_batch.py` | 수정 — benchmark 갱신 단계 + **상태 분리 기록** |
| `scripts/refresh_market_timeseries.py` | 수정 — 미국 지표 서브커맨드 (probe 통과분만) |
| `app/market_benchmark_store.py` | 수정 — benchmark **정적 catalog**(timezone·종료시각·freshness 규칙) |
| 신규 `app/market_input_probe.py` 등 | probe·backfill·평가·판정 |
| `app/market_flow_*` | **미변경.** 구조만 참조하고 import 하지 않음 |
| `docs/PROGRAM_TRUTH.md` | 갱신 |

**`OPS-02B-2` 로 미룸**: `app/message_market_briefing.py` · 신규 본문·억제 모듈 ·
`scripts/run_three_push_runtime_oci.py` · PROGRAM_TRUTH C-1/C-2.

### 11.2 KS-10 주의

`scripts/run_three_push_runtime_oci.py` 는 **현재 637줄**(임계 650). 시장
브리핑 조립을 러너에 인라인하면 즉시 위반합니다. **조립은 전부 helper 모듈**에
두고 러너는 호출만 합니다 — OPS-02A 에서 709줄까지 갔다가 4곳 분리한 경험을
그대로 적용합니다.

### 11.3 OCI 배포 영향

| 항목 | 영향 |
|---|---|
| cron | **변경 없음** (08:00 기존 유지). 단 §4.1 조치로 07:20 배치 **동작이 바뀜** |
| PARAM | 변경 없음 (`market_briefing` 이미 `enabled_push_kinds` 에 있음) |
| flag | `PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED` **`false` 유지**. `02B-1` 에서 **활성화하지 않습니다** |
| DB | `market_benchmark_daily_price` — 미국 지표 적재 여부는 `02B-2` 에서 결정 |
| `etf_daily_price` | **변경 없음.** `open`·`close` 를 수정·덮어쓰지 않는다. `OPEN_GAP` 은 KRX 평가 snapshot 안에서만 계산한다 |
| 배포 | OCI 자동 pull 확인됨(2026-09-08 `5d2614d6` 즉시 반영) |

---

## 12. [V1.1] 확정 사항 — 2026-09-08 설계자 판정

V1 의 모호점 6건은 **전부 확정**됐습니다. 아래가 정본이며, 앞 절과 충돌하면
이 절이 우선합니다.

| V1 질의 | 확정 |
|---|---|
| Q1 범위 분할 | **(b) 2분할** — `02B-1` Gate / `02B-2` 메시지 (§12.1) |
| Q2 benchmark 스키마 | **(d) 최소 변경** — 테이블 유지 + 정적 catalog (§12.2) |
| Q3 섹터 원천 | **KRX 읽기 전용 probe 승인**, 수집기는 조건부 (§12.3) |
| Q4 판정 상태 | **`NOT_EVALUATED` 신설** (§12.4) |
| Q5 `open` backfill 실패 | ~~(b) 제한~~ → **V1.2 에서 폐기.** KRX 단일 원천으로 대체 (§2.2 · §12.5) |
| Q6 VIX 영향 | **읽기 전용 확인까지만** (§12.6) |

**미확정 항목 없음 → 재검토 없이 `OPS-02B-1` 착수.**

### 12.1 Step 2분할

| Step | 범위 |
|---|---|
| **`OPS-02B-1`** Market Input Readiness & Validity Gate | **KRX 평가 snapshot 구축**(`069500` 행만, 운영 DB 미변경) · 미국 지표 source/symbol 검증 · KOSPI/VIX 갱신·값·as-of 결함 수정 · 기초지수 메타데이터 원천 검증 · 미국→한국 개장 walk-forward 평가 · **`INDEX_LEADERSHIP` 산출 가능성 판정** |
| **`OPS-02B-2`** Market Briefing Message & Operation | `02B-1` 판정을 입력으로 메시지·반복 억제·PUSH |

`02B-1` 에서 **Telegram 본문·반복 억제·autosend 활성화를 구현하지 않습니다.**
전망과 섹터가 **모두** 사용 불가면 `02B-2` 를 억지로 만들지 않고 POC3 을 계속
열린 상태로 둡니다.

### 12.2 benchmark 스키마 — 최소 변경

기존 `market_benchmark_daily_price` **유지**. `date` = session date ·
`created_at` = 적재 시각 · `source` = 원천. benchmark 별 **timezone · 통상
종료시각 · freshness 규칙은 코드의 정적 catalog**. 반환 evidence 에 각
benchmark 의 **`as_of_date` 와 계산된 freshness** 포함. **기존 행에 알 수 없는
timestamp 소급 생성 금지. 신규 테이블·대규모 컬럼 migration 금지.**

미국 일별 지수는 session date + `America/New_York` 규칙으로 한국 개장 전 이용
가능성을 계산하고, **DST 는 표준 `zoneinfo`** 로 처리합니다.

USD/KRW 가 일별 값만 제공되면 **`07:50 현재` 라고 표현하지 않습니다.** source 가
실제로 제공하는 날짜·시각만 쓰고, **PIT 시점이 불명확하면 예측 입력에서
제외**합니다.

### 12.3 섹터 원천 — KRX 읽기 전용 probe

상세는 **§3.3**. 요약: probe 로 필드·커버리지 확인 → 구조화된 섹터/테마 필드가
없으면 **`SECTOR_NOT_EVALUATED`** · Naver 자동 채택·ETF명 추론 우회 금지 ·
확인된 경우에만 **이번 Step 전용 수집기 1개** 허용.

### 12.4 판정 4상태

| 상태 | 의미 |
|---|---|
| `ADOPT_OUTLOOK` | 한국 개장 압력 문구 사용 가능 |
| `FACT_ONLY` | 예측 문구는 불가하나 **미국시장 사실 입력은 사용 가능** |
| `REJECT` | **충분한 데이터로 평가**했으나 사전 기준 미달 |
| `NOT_EVALUATED` | **표본·입력 부족으로 평가 자체를 못 함** |

`NOT_EVALUATED` 를 `REJECT` 에 포함하지 않습니다.

### 12.5 `open` backfill — **V1.2 에서 폐기됨**

V1.1 의 "FDR 로 `open` 만 backfill · 750일 미만이면 `NOT_EVALUATED`" 지시는
**probe 결과로 폐기**됐습니다. KRX Open API 가 시가·종가를 **같은 무조정
기준**으로 제공하므로 혼합 문제가 발생하지 않습니다. 현행은 **§2.2**.

`database_backfill = DEFERRED` — 운영 DB 적재는 Gate 판정 후 `02B-2` 에서
결정합니다.

### 12.6 VIX 영향 — 읽기 전용 확인까지만

확인: 2026-07-03 이후 기존 market-flow 산출물이 사용한 VIX source date · stale
VIX 가 실제 artifact·API·UI·PUSH 에 소비됐는지 · 영향 기준일과 소비처.

하지 않음: 기존 ML 재학습 · artifact 전면 재생성 · 상대상승 모델 재개 ·
**영향이 확인되지 않은 산출물 수정.**

운영 소비가 확인되면 해당 경로를 **fail-closed 로 차단**하고 **별도 결함으로
기록**합니다.

### 12.7 추가 필수 수정

1. **기존 모델 재사용 범위** — `market_flow_walk_forward.py` 는 **구조만**
   (날짜 정렬·기준일별 학습·walk-forward·baseline 비교·결과 집계). 기존 20일
   target·feature·학습 artifact·3모델 predictor 는 **재사용 대상 아님**.
   `02B-1` 은 **투명한 단순 baseline** 으로 시작, ML 튜닝·앙상블 없음. (§1.1 반영)
2. **미국 symbol probe 선행** — identity·최초/최종일·`close` 결측률·source
   date·재현성·**개장 전 확정 여부** 확인. `SOX`·`USD/KRW` 처럼 의미 불명확하면
   **확인 전 적재 금지**. (§2.2 반영)
3. **KOSPI/VIX 갱신** — 상태 분리 기록 · 실패 은폐 금지 · ETF 가격 롤백 금지 ·
   자기 `as_of_date` · stale 시 문장 생성 금지 · 날짜 기준 계산. (§4.1 반영)

### 12.8 [V1.2] probe 후 설계자 정정 (2026-09-09)

| # | 정정 | 반영 |
|---|---|---|
| 1 | **`OPEN_GAP` 원천을 KRX Open API 무조정가로 교체.** V1.1 의 "FDR 자체 계열" 지시는 **폐기** | §2.2 |
| 2 | USD/KRW **PIT 분리** — 제공 완료 시각 증명 못하면 primary feature 제외 · 표본 **재산출** | §5 |
| 3 | `SECTOR = NOT_EVALUATED` 확정. **API Key 가 섹터를 해결한 것으로 기록 금지** | §3 |
| 4 | **`INDEX_LEADERSHIP` 신설** — `최근 강한 기초지수`. **`상승 섹터` 로 표기 금지** | §7 |
| 5 | 신규 결함 **`DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY`** 등재 (`INVESTIGATION_REQUIRED`, 이번 Step 미수정) | §2.4 |
| 6 | 본문 확정 전에 **Gate 먼저 실행**. `REJECT`·`NOT_EVALUATED` 여도 3번째 PUSH 폐기 금지 | §8 |
| 7 | 메타데이터는 **운영용 최신만** 수집. 수동 CSV 는 정본 아님. 2,800일 backfill 금지 | §7.2 |

---

## 13. [V1.2] `OPS-02B-1` 종료 산출물

| # | 산출물 |
|---|---|
| 1 | 데이터별 **probe 결과** (§2) |
| 2 | **USD/KRW 분리 적용 후** 실제 정렬 표본 수와 커버리지 · **Gate 에 쓴 feature 집합** |
| 3 | KOSPI/VIX **독립 재계산 결과** |
| 4 | **VIX stale 소비 영향** (읽기 전용) |
| 5 | 섹터 메타데이터 **필드·커버리지** + `INDEX_LEADERSHIP` join coverage |
| 6 | `OPEN_GAP` snapshot **재현 근거** — symbol · 조회 구간 · 행 수 · 최초/최종일 · 수집 시각 · **snapshot hash** · 결측률 · 가격 기준 불일치 관찰 |
| 7 | **전망 판정** |
| 8 | `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 읽기 전용 기록 |

**최종 결론 형식**

```text
OUTLOOK             = ADOPT_OUTLOOK | FACT_ONLY | REJECT | NOT_EVALUATED
SECTOR              = NOT_EVALUATED
INDEX_LEADERSHIP    = AVAILABLE | NOT_EVALUATED
KOSPI_VIX_INTEGRITY = PASS | FAIL
NEXT                = START_02B_2 | REMAIN_BLOCKED
```

> 구현 중 **외부 source 의 identity·필드가 PLAN 과 다르거나 새로운 PIT 문제가
> 발견되는 경우에만** 다시 질의합니다. 그 밖에는 임의 대체하지 않고 사실만
> 반환합니다.

---

## 14. [V1.3] `OPS-02B-1` Gate 결론

실행일 2026-09-10. **운영 DB 쓰기 0건 · 발송 0건 · 08:00 autosend `false` 유지.**

```text
OUTLOOK_RELATIONSHIP = ADOPT
OPERATING_RULE       = SP500_SIGN_V1
OLS                  = RESEARCH_REFERENCE
SECTOR               = NOT_EVALUATED
INDEX_LEADERSHIP     = AVAILABLE
KOSPI_VIX_INTEGRITY  = PASS
OPS-02B-1            = 검증 대기
NEXT                 = 검증자 VERIFIED 후 설계자 최종 Gate 확정 → HANDOFF → 02B-2
```

> `ADOPT` 는 **미국시장–한국 개장 갭의 방향 관계가 유효**하다는 판정이다.
> **OLS 자체의 운영 채택 판정이 아니다** — 운영 규칙은 `SP500_SIGN_V1` 이다
> (§14.1-b).

### 14.1 OUTLOOK — `ADOPT_OUTLOOK`

| 사전 기준 | 실측 | 판정 |
|---|---|---|
| 정렬 표본 750일 이상 | **2,758일** (2015-01-05 ~ 2026-09-07) | PASS |
| 입력 커버리지 95% | **96.2%** | PASS |
| 방향 적중 95% CI 하한 > 50% | 76.39% · CI **[74.50, 78.28]** | PASS |
| 다수방향 baseline 대비 +5%p | 57.32% → **+19.07%p** | PASS |
| 강한 상승·하락군 차이 CI > 0 | +1.9238% · CI **[+1.7458, +2.1183]** | PASS |

- 예측 구간 2018-03-15 ~ 2026-09-07 (2,002일) · 방향 판정 1,961일
- 모델: **확장창 walk-forward OLS**, 기준일마다 이전 데이터로만 재적합(20거래일
  간격), 비교 baseline 은 같은 학습 구간의 다수 방향. **ML 튜닝·앙상블 없음.**
- **Gate 에 사용한 feature 집합** (5종, 각 1일 수익률):
  `sp500_ret_1d_pct` · `nasdaq_ret_1d_pct` · `sox_ret_1d_pct` ·
  `russell_ret_1d_pct` · `vix_ret_1d_pct`
- **USD/KRW 는 primary 제외** — 일별 종가만 제공되고 제공 완료 시각을 증명할 수
  없다. 보조 민감도용으로 `usdkrw_ret_1d_pct`(엄격히 앞선 날짜)만 데이터셋에
  남겨 두었고 **평가에는 쓰지 않았다.**

**모델 기여는 작다** — `sign(S&P500)` 단독 규칙이 이미 **74.63%** 이고 OLS 는
**+1.76%p** 만 더한다. `02B-2` 에서는 **단변량 규칙**이 더 정직할 수 있다.

**누수 검사 6종 — 전부 통과**

| 검사 | 결과 | 해석 |
|---|---|---|
| target 셔플 ×3 | 54.3 ~ 55.8% | 관계 파괴 시 baseline 으로 붕괴 |
| feature 1세션 지연 | **53.75%** | 동일일 데이터 누수 아님 |
| feature 2세션 지연 | 53.54% | 〃 |
| target +1일 이동 | 53.75% | 미래 참조 아님 |
| 단변량 `sign(VIX)` | 29.32% | 역방향 = 위험회피, 부호 정상 |
| `OPEN_GAP` 분포 | 평균 +0.071% · 표준편차 1.024% · 상승 55.6% | 실제 갭 분포 |

표현은 **"미국시장과 개장 갭의 예측 관계"** 로 제한하고 인과로 단정하지 않는다.

### 14.1-b [V1.4] 운영 규칙 — `SP500_SIGN_V1`

설계자 §2 확정: **`ADOPT` 는 미국시장–한국 개장 갭의 방향 관계가 유효하다는
판정이지, OLS 자체의 운영 채택 판정이 아니다.**

```text
OPERATING_RULE = SP500_SIGN_V1     (규칙: 직전 미국 세션 S&P500 1일 수익률의 부호)
OLS            = RESEARCH_REFERENCE
```

**같은 표본 실측** (OLS Gate 와 동일 예측 구간 2018-03-15 ~ 2026-09-07)

| 항목 | `SP500_SIGN_V1` | (참고) OLS |
|---|---|---|
| 방향 적중률 | **74.25%** · 95%CI **[72.26, 76.13]** | 76.39% |
| 다수방향 baseline | 57.32% | 57.32% |
| 개선폭 | **+16.93%p** | +19.07%p |
| S&P 상승일 갭 평균 | **+0.5058%** (n=1,086) | — |
| S&P 하락일 갭 평균 | **−0.4191%** (n=916) | — |
| 상승·하락일 갭 차이 | **+0.9249%** · bootstrap 95%CI **[+0.8338, +1.0174]** | — |

| 기존 Gate 기준 | 판정 |
|---|---|
| 적중 CI 하한 > 50% | **PASS** |
| baseline 대비 +5%p 이상 | **PASS** |
| 상승·하락일 갭 차이 CI > 0 | **PASS** |

전체 표본(2,758일) robustness: 적중 74.63% · CI [72.95, 76.27] ·
개선 +17.47%p · 갭 차이 +0.7966% · CI [+0.7260, +0.8684] — **같은 결론.**

> 모든 CI 는 `scripts/ops02b1_gate/reproduce.py operating` 출력이다. 통계 항목마다
> **독립 RNG**(seed 를 항목 tag 로 파생)를 쓰므로 스크립트 구성이 바뀌어도 같은
> 값이 나온다. r1 문서의 CI 는 공유 RNG 를 순서대로 소비해 재현되지 않았다
> (검증자 r2 A-2) — **위 값이 정본**이다.

**운영 표현 제약**

- 상승·하락 **방향 압력까지만** 허용한다.
- **한국 개장 예상 등락률 숫자는 표시하지 않는다** — calibration 검증이 없다.
- Nasdaq·`^SOX`·Russell·VIX 는 **설명 evidence 로만** 쓰고 **임의 가중 규칙을
  추가하지 않는다.**

단순 규칙이 기준을 통과했으므로 **OLS 운영 여부는 재질의하지 않는다.**

### 14.2 `OPEN_GAP` snapshot 재현 근거

| 항목 | 값 |
|---|---|
| source | `KRX_OPEN_API` (`https://data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd`) |
| price_basis | `UNADJUSTED_TRADED_PRICE` |
| symbol | `069500` (평가 행만 추출 · 일별 응답 전체 미적재) |
| 조회 구간 | `20150102` ~ `20260908` (거래일 축 = FDR `069500`) |
| 행 수 | **2,867일** |
| 최초·최종일 | `2015-01-02` ~ `2026-09-07` |
| 결측 | **1일** — `20260908` (KRX 미제공). `20230519` 는 일시 오류 후 재조회 복구 |
| 수집 시각 | 2026-09-09 KST |
| snapshot sha256 | `ca94dffbc37aa338ea6e4e98196c6a4793a741aa4cbe10954c3d3d7304e6d361` |
| dataset sha256 | `a8e36743ffa42f95e51dbc892b5eca1b927631e05cef81663e681655ab631435` |
| 비용 | 평균 0.30초/호출 · 총 약 27분 |

**한계** — KRX 무조정가에는 **분배락에 따른 실제 가격 변화**가 포함된다. 공식
분배락 날짜를 별도로 확보하지 못했으므로 **임의 보정하지 않고 한계로 기록**한다.
분기 배당락 추정일은 §14.4 의 전환 후보일과 겹친다.

### 14.3 KOSPI/VIX 결함 — `KOSPI_VIX_INTEGRITY = PASS`

계약 7개 전부 구현. 신규 테스트 **17건** · 전체 회귀 **1,439 passed / 0 failed**.

| # | 계약 | 구현 위치 |
|---|---|---|
| ① | 배치에서 갱신 경로 확보 | `app/market_benchmark_batch.py` → `scripts/run_oci_market_data_batch.py` §2-b |
| ② | 각 benchmark 자기 `as_of_date` | `market_regime.compute_kospi_metrics` |
| ③ | 실제 거래일 날짜 기준 수익률 | `app/market_benchmark_freshness.return_by_trading_days` |
| ④ | 최신성 1거래일 초과 시 미산출 | `status="stale"` + 수익률 키 자체 미포함 |
| ⑤ | stale 을 최신 `asof` 로 표시 금지 | `asof_source="KODEX200"` · composer 차단 |
| ⑥ | 일부 실패 시 실패 블록만 제외 | KOSPI stale 이어도 KODEX200 국면 유지 |
| ⑦ | stale VIX 영향 읽기 전용 확인 | §14.5 |

배치 계약 3건도 반영 — ETF 가격 성공과 benchmark 성공 **별도 기록** · benchmark
실패를 **전체 성공으로 숨기지 않음** · benchmark 실패로 **ETF 가격 적재 롤백
안 함**(경계에 `BaseException` 가드).

> 테스트가 실제 결함 1건을 잡았다. `refresh_benchmarks` 에 예외 가드가 없어
> 개별 함수 밖 예외가 배치 전체를 실패시킬 수 있었다.

### 14.4 `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` — 읽기 전용 기록

`status = INVESTIGATION_REQUIRED` · **이번 Step 수정 0건.**

| 요구 기록 | 실측 |
|---|---|
| 전체 기간 KRX/DB 비율 | 2015Q2 **+23.92%** → 2026Q1 **+0.03%** (단조 감소) |
| 전환 후보일 | **39건.** 2025-01-24 · 04-29 · 07-30 · 10-30 · 2026-01-29 · 04-29 · 07-30 — **분기 배당락 패턴** |
| 영향 ticker 범위 | `NAVER_FDR` 1,063종 (~2026-03-05) · `FinanceDataReader` 1,181종 (2026-02-19~). **2026-02-19~03-05 중첩** |
| 소비 경로 | 수익률(`market_regime`·`market_topn`) · ML(`market_flow_dataset`·`ml_feature_builder`) · UI/API(`api_market_topn_service`·`api_price_series`) · PUSH(보유 브리핑 20거래일·급락 알림 고점 대비) |
| 현재 운영 수치 실영향 | **없음** — PUSH·수익률은 **DB 단일 계열 안에서** 상대 계산하므로 균일 배수가 상쇄된다. KRX snapshot 은 Gate 평가 전용이며 운영 경로에 들어가지 않는다. **계열 혼합 0건** |

**해석** — 누적 괴리(11년 +23.9% ≈ 연 1.9%)가 KODEX200 분배금 수익률과 부합하고
전환일이 분기 배당락일과 겹친다. 즉 **DB = 배당조정(총수익) 계열, KRX = 무조정
실거래가**로 설명된다. 다만 **2026-04-17 `+0.000%` → 04-20 `+0.646%`** 는 유일한
역방향 계단이라 설명되지 않는다. `source` 중첩 구간과 함께 남은 조사 대상이다.

### 14.5 VIX stale 소비 영향 (읽기 전용)

| 확인 | 결과 |
|---|---|
| OCI benchmark 최신성 | KOSPI·VIX **2026-07-03** / ETF 가격 2026-09-07 |
| OCI ML artifact | **없음** — ML 은 OCI 에서 돌지 않는다 |
| PUSH 본문 VIX·변동성 문구 | **0건** |
| 결론 | **운영 발송 경로에 stale VIX 소비 없음** |

ML 재학습·artifact 재생성·상대상승 모델 재개 **하지 않았다**(설계자 §6-7).

### 14.6 `INDEX_LEADERSHIP` 산출 실측

| 항목 | 값 |
|---|---|
| 메타데이터 | 1,168종 |
| 필터 후 (기초자산=주식 · 추적배수=일반 · 복제방법 실물) | **726종** |
| 기초지수 그룹 (`지수산출기관 + 기초지수명` 완전일치) | **573개** |
| 추종 ETF **2개 이상** 그룹 (`n≥2` 풀) | **43개** |
| join coverage (필터 후 ↔ `etf_master`) | **100%** (≥95% 충족) |
| 2026-09-04 기준 5일·20일 모두 양수 **+ `n≥2`** | **1개** (`KRX 은행`) |
| 최근 20거래일 후보 수 | 중앙 **11개** · 범위 0~31 · 2개 이상인 날 **17/20** |

> `n≥2` 상세와 판정 근거는 **§15.1**.

---

## 15. [V1.4] V1.3 질의 2건 — **해소**

| 질의 | 확정 |
|---|---|
| **15-1** KRX API 에 정적 속성 필드 없음 | **원천 2분리** — ticker·최신 기초지수명은 API 일별, 정적 속성은 **공식 KRX CSV versioned snapshot**. "수동 CSV 정본 불가" 계약을 설계자가 **수정**했다. 계약 7개는 **§7.2** |
| **15-2** 상위 기초지수가 추종 ETF 1개 | **`minimum_distinct_tickers_per_index = 2`** 확정. `n=1` 은 진단에만 남기고 PUSH 후보 제외 · fallback 부활 금지. 계약은 **§7.1-6b** |

### 15.1 `n ≥ 2` 적용 후 실측 — 판정 유지, 다만 수치 정정

설계자 판정문은 "현재 43개 그룹이 남으므로"라고 했는데, **43 은 두 조건의
교집합이 아니다.**

| 구분 | 개수 |
|---|---|
| 필터 후 기초지수 그룹 | **573** |
| 그중 `n ≥ 2` 그룹 | **43** |
| 그중 2026-09-04 기준 5일·20일 모두 양수 | **1** (`KRX 은행`, 추종 ETF 2개) |

즉 `n ≥ 2` **풀**이 43개이고, **특정일의 후보 수**는 그날 수익률에 따라 달라진다.

**최근 20거래일 후보 수 분포**

| 지표 | 값 |
|---|---|
| 중앙값 | **11개** |
| 최소 ~ 최대 | **0 ~ 31개** |
| 후보 **2개 이상**인 날 | **17 / 20** |
| 후보 **0개**인 날 | **2 / 20** (→ 기초지수 문단 생략) |

2026-09-04(1개)은 약한 날이었다. **`INDEX_LEADERSHIP = AVAILABLE` 판정은
유지된다.** 후보 0개인 날은 §7.1 계약대로 **문단 자체를 생략**한다.

---

## 16. [V1.5] 검증자 r1 `REJECTED` — 처리 내역

| # | 지적 | 처리 |
|---|---|---|
| A-1 | benchmark 가 `partial/failed` 여도 배치가 **무조건 `success`** 로 끝나고, 영구 상태에 benchmark 결과가 없다 | **수정.** 종료 status 를 **`success_with_benchmark_failure`** 로 분기하고, `write_batch_state` 에 `price_pipeline_status`·`benchmark_status`·`benchmark_failed`·`kospi_as_of`·`vix_as_of` 를 **영구 기록**한다. ETF 가격 적재는 그대로 유지(`price_pipeline_status="success"` 가 증명) |
| A-2 | 보고에서 **untracked 1건 누락** | **정정.** `state/tmp_krx_etf_basic.csv` 를 보고에 포함하고, 정본은 **§17** 의 versioned snapshot 으로 이동 |
| A-2·A-4 | 배치 테스트가 **라이브 로컬 DB 에 KOSPI 120행·VIX 48행 기록** | **수정.** `tests/conftest.py` 에 가드 2종 — `db_path` 미주입(=라이브) 갱신 **차단** + benchmark 테이블 **변경 감지 실패**. 개별 테스트를 고치지 않고 **일괄**로 막았다 |
| A-3 | Gate 근거가 `tmp` untracked 파일이라 **독립 재현 불가** | **수정.** snapshot·dataset·공식 CSV 를 **저장소로 이동**하고 `MANIFEST.json`(sha256·행 수·기준일)과 **단일 재현 스크립트**를 추가했다 (§17) |
| B-5 | 핵심 메타데이터 원본이 untracked | **수정.** `state/market_meta/krx_etf_basic_20260909.csv` 로 versioned 화 |
| B-6 | 테스트가 **helper 반환만** 보고 배치 종료·영구 상태를 안 본다 | **보강.** `test_batch_state_records_benchmark_status_separately` 추가 |
| B-6 | `BaseException` 까지 삼켜 **종료 신호를 benchmark 실패로 변환** | **수정.** `Exception` 만 catch. `test_guard_does_not_swallow_base_exception` 으로 고정 |

> **라이브 DB 에 실제로 쓰인 내용** — 로컬 Mac `market_data.sqlite` 에 KOSPI 120행
> (2026-03-16~09-07) · VIX 48행(2026-07-06~09-09) 이 `created_at=2026-09-10T12:26:12Z`
> 로 기록됐다. 값 자체는 **실제 시장 데이터**이고(KOSPI 2026-09-07 = 6,995.39)
> **OCI 는 무관**하다. 되돌리지 않았다 — 시세 데이터 임의 복원이 더 위험하다.
> 경로만 막았다.

**부수 영향 1건** — `spike_freshness` 는 `status == "success"` 만 통과시키므로,
benchmark 실패 시 spike 는 **fail-closed** 가 된다. `spike_or_falling_alert` 는
cron 이 교체돼 **실행되지 않으므로 운영 영향은 없다.**

---

## 17. [V1.5] Gate 재현 경로

검증자가 **독립 재검증**할 수 있도록 저장소 안에 둔다.

| 산출물 | 경로 | 행 수 | sha256 |
|---|---|---:|---|
| 공식 KRX ETF 기본정보 | `state/market_meta/krx_etf_basic_20260909.csv` | 1,168 | `bf07e52b…` |
| KRX `069500` 무조정 시가/종가 | `state/ops02b1_gate/krx_069500_snapshot.csv` | 2,867 | `ca94dffb…` |
| PIT 정렬 데이터셋 | `state/ops02b1_gate/gate_dataset.csv` | 2,866 | `a8e36743…` |
| KRX API 기초지수명(1일치) | `state/ops02b1_gate/krx_api_idxname_20260904.csv` | 1,167 | `e5627965…` |
| ETF 종가(41거래일 · `n≥2` 대상) | `state/ops02b1_gate/etf_close_snapshot.csv` | 7,984 | `4caa9d9c…` |
| `etf_master` ticker 목록 | `state/ops02b1_gate/etf_master_tickers.csv` | 1,178 | `4c186184…` |
| DB `069500` 종가(조정 계열) | `state/ops02b1_gate/db_069500_close_snapshot.csv` | 3,044 | `caaae26e…` |
| 무결성 기준 | `state/ops02b1_gate/MANIFEST.json` | — | — |

**`reproduce.py` 는 운영 DB 를 읽지 않는다** — 위 snapshot 만 쓴다(검증자 r2
A-3). `sqlite3` import 자체가 없다. 무결성·스크립트 존재가 하나라도 어긋나면
**exit code 1** 로 끝난다.

**CSV 사용 계약 (설계자 §3) 이행**

| 계약 | 이행 |
|---|---|
| `source = KRX_OFFICIAL_CSV` | `MANIFEST.json` 에 명시 |
| 기준일·파일 hash·행 수 기록 | `asof_date=2026-09-09` · `sha256` · `rows=1168` |
| API ticker 와 정확히 join | `reproduce.py` §6 — 완전일치만 |
| 지수명 불일치 종목 제외 | API `IDX_IND_NM` 과 **1,167종 100% 일치** 확인 |
| coverage 95% 미만이면 미산출 | `reproduce.py` 가 coverage 를 출력하고 게이트한다 |
| 수동 편집본·가공 분류표 금지 | 다운로드 원본 그대로. `tmp` 사본은 정본이 아니다 |

**재현 방법**

```bash
python scripts/ops02b1_gate/reproduce.py          # 전체 (읽기 전용)
python scripts/ops02b1_gate/reproduce.py operating index
```

`reproduce.py` 는 **운영 DB 를 쓰지 않고 외부 조회도 하지 않는다.** snapshot 을
처음부터 받으려면 `scripts/ops02b1_gate/fetch_snapshot.py` 를 쓴다
(`KRX_API_KEY` 필요, 운영 DB 는 여전히 미변경).

---

## 18. [V1.7] 이월 분리 — 설계자 최종 판정

> 이월을 그대로 넘기면 `02B-2` 범위가 다시 불어난다. **필수와 BACKLOG 를
> 분리**한다 (설계자 2026-09-11).

### 18.1 `02B-2` **필수** 2건

| # | 항목 | 내용 |
|---|---|---|
| 1 | **API 에만 있는 신규 ticker 감지** | `select_index_universe` 가 CSV 를 순회해 API 쪽 신규 종목을 보지 못한다. 일별 API 가 CSV 보다 최신이 되는 운영 단계에서 잡아야 한다 |
| 2 | **API·CSV 불일치 감지와 `CSV_REFRESH_REQUIRED` 상태** | 매일 API 대조 → **불일치 종목 제외** → **공식 CSV 교체 필요 상태 기록**까지 |

**정적 CSV 자동 다운로드는 이번 범위가 아니다** (설계자 확정). API 가 제공하지
않는 필드를 억지로 자동화하지 않는다. 위 2건까지만 하면 **운영 안전성은
확보된다.**

### 18.2 BACKLOG · **비차단** 2건

| # | 항목 | 상태 |
|---|---|---|
| 1 | `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` **DB 가격계열 본조사** | `INVESTIGATION_REQUIRED`. 운영 실영향 없음(계열 혼합 0건) |
| 2 | **분배락 민감도 평가** | 공식 분배락 날짜 확보 시. 미확보 상태는 §2.2 에 한계로 기록됨 |

**`02B-2` 를 막지 않는다.**

---

## 19. 진행 상태와 다음 순서

**`OPS-02B-1` `CLOSED`** (설계자 최종 Gate 확정 2026-09-11).

| # | 단계 | 상태 |
|---|---|---|
| 1 | 계약 + `SP500_SIGN_V1` 수치 반영 | **완료** |
| 2 | PLAN 같은 파일 개정 | **완료** (V1.4) |
| 3 | 커밋·푸시 | **완료** — `988b0494`(코드) · `d76a9fc1`(종료 문서) |
| 4 | `OPS-02B-1` 결과를 **검증자에게 제출** | **완료** — `VERIFIED_WITH_NOTES` |
| 5 | 검증자 `VERIFIED` 전 **`02B-2` 구현 착수 금지** | **해제** |
| 6 | `VERIFIED` 후 설계자 최종 Gate 확정 · HANDOFF | **완료** — 2026-09-11 `CLOSED` |
| 7 | 새 설계자 세션에서 `02B-2` 메시지·억제·목업 설계 | **다음** |

수행 범위: 로컬 DB 읽기 · OCI 읽기 전용 SSH · 소스 grep · 읽기 전용 외부
probe(FDR · KRX Open API · pykrx) · KOSPI/VIX 결함 수정 코드.

**운영 DB 쓰기 0건 · 발송 0건 · `etf_daily_price` 미변경 · 08:00 autosend
`false` 유지 · OCI 배포 미수행.**
