# POC3-OPS-02B — 08:00 시장 브리핑 재개발 · 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude) · **수신**: 설계자
- **작성일**: 2026-09-08
- **대응 설계서**: `docs/ai_design/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_DESIGN_V1.md`
- **개정 이력**

  | 판 | 내용 |
  |---|---|
  | V1 (2026-09-08) | 최초 제출 — 모호점 6건 |
  | **V1.1** (2026-09-08) | 설계자 **`APPROVED_WITH_REQUIRED_EDITS`**. 모호점 6건 확정 · Step **2분할** · 필수 수정 3건 |
  | **V1.2** (2026-09-09) | **probe 3종 실행 결과 + 설계자 정정 반영.** `OPEN_GAP` 원천 **KRX Open API 무조정가** 확정 · USD/KRW **PIT 분리** · `SECTOR=NOT_EVALUATED` 확정 + **`INDEX_LEADERSHIP` 신설** · 신규 결함 `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 등재. **추가 질의 없이 Gate 실행** |

- **상태**: **`OPS-02B-1` Gate 실행 중.** `OPS-02B-2` 는 `02B-1` 판정 이후
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
krx_credentials     = NOT_REQUIRED
database_backfill   = DEFERRED
```

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
- **사용자에게 추가 계정 발급을 요청하지 않습니다** (`krx_credentials =
  NOT_REQUIRED`).
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

### 6.1 데이터 확보 전에는 실행할 수 없습니다

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
| 7 | 그룹 수익률 = 추종 ETF 들의 **중앙값** |
| 8 | **5거래일·20거래일 수익률이 모두 양수**인 기초지수만 후보 |
| 9 | **20거래일 수익률 기준 상위 2개**까지만 표시 |
| 10 | **추종 ETF 수와 가격 기준일**을 evidence 에 기록 |

### 7.2 메타데이터 운영 계약 (설계자 정정 §3)

- KRX API 로 **기초지수명·추적배수·복제방법을 매일 갱신**
- **수동 CSV 는 운영 정본으로 쓰지 않습니다** (V1.2 판정 근거로만 사용)
- **과거 2,800일 메타데이터 전체 backfill 하지 않습니다.** 운영용 **최신
  메타데이터만** 수집
- `source`·`as-of`·`hash` 를 가진 **versioned snapshot** 으로 보존

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
state_fingerprint = f"{outlook_state}#{sector_state}"
  outlook_state = ADOPT_OUTLOOK:UP|MIXED|DOWN  또는 FACT_ONLY:...  또는 NONE
  sector_state  = 상위 섹터명을 정렬해 '|' 로 결합 (없으면 NONE)
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
제한 제거` · `충족 섹터 0인데 빈 문단 출력` · `정확한 등락률을 예측값으로 표시`.

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
| DB | `market_benchmark_daily_price` **행 대량 증가**(약 15,500) + 컬럼 확장 시 마이그레이션 |
| `etf_daily_price` | `open` backfill 시 **약 2,919행 UPDATE** — 기존 `close` 를 덮지 않도록 주의 |
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
| **`OPS-02B-1`** Market Input Readiness & Validity Gate | KODEX200 `open` probe·backfill · 미국 지표 source/symbol 검증·backfill · KOSPI/VIX 갱신·값·as-of 결함 수정 · 섹터/기초지수 메타데이터 원천 검증·최소 적재 · 미국→한국 개장 walk-forward 평가 · 상승 섹터 산출 가능성 판정 |
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

## 14. 착수

설계자 판정 + 정정을 **V1.2 에 전부 반영**했으므로 **추가 질의 없이 `OPS-02B-1`
Gate 를 실행**합니다.

수행 범위: 로컬 DB 읽기 · OCI 읽기 전용 SSH · 소스 grep · **읽기 전용 외부
probe**(FDR · KRX Open API · pykrx). **운영 DB 쓰기·발송 0건 · 08:00 autosend
`false` 유지.**
