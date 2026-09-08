# POC3-OPS-02B — 08:00 시장 브리핑 재개발 · 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude) · **수신**: 설계자
- **작성일**: 2026-09-08
- **대응 설계서**: `docs/ai_design/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_DESIGN_V1.md`
- **개정 이력**

  | 판 | 내용 |
  |---|---|
  | V1 (2026-09-08) | 최초 제출 — 모호점 6건 |
  | **V1.1** (2026-09-08) | 설계자 **`APPROVED_WITH_REQUIRED_EDITS`**. 모호점 6건 **전부 확정**(§12) · Step **2분할** · 필수 수정 3건 반영. **재검토 없이 `OPS-02B-1` 착수** |

- **상태**: **`OPS-02B-1` 착수 승인됨.** `OPS-02B-2` 는 `02B-1` 판정 이후
- **조사 범위**: 로컬 저장소·로컬 DB·**OCI 읽기 전용**. 쓰기·발송·수집 실행 **0건**

---

## 0. 결론 요약 — 데이터 3축이 비어 Step 을 2분할한다

조사 결과 **설계서가 전제한 데이터 중 상당수가 없습니다.** 그대로 착수하면
§4 사전판정이 `REJECT` 로 끝나는 것이 아니라 **평가 자체를 실행할 수 없습니다.**

| 축 | 설계서 요구 | 실측 | 판정 |
|---|---|---|---|
| **예측 대상** `KODEX200_OPEN_GAP` | 정렬 표본 **750일 이상** | `open` 컬럼이 **2026-03-06부터 126일**뿐 | **BLOCKED** — backfill 선행 필요 |
| **미국 입력** 6종 | S&P500·Nasdaq·반도체·Russell·VIX·USD/KRW | DB에 **VIX 1종만**, 그마저 **2026-07-03 정체** | **BLOCKED** — 5종 신규 수집 |
| **섹터 분류** | 공식·구조화 원천 | **없음** (`category` 는 자산군 코드 7종) | **BLOCKED** — 원천 결정 필요 |
| **KOSPI 결함** | 이번 Step 해소 | 원인 2개 확정 (§4) | **해소 가능** |
| **파이프라인 재사용** | 기존 유지 | `market_flow_*` walk-forward 재사용 가능 | **가능** |

**따라서 Step 을 2분할합니다** (설계자 확정 · §12.1).

| Step | 범위 | 상태 |
|---|---|---|
| **`OPS-02B-1`** Market Input Readiness & Validity Gate | probe·backfill · 결함 수정 · 평가 · 판정 | **착수 승인** |
| **`OPS-02B-2`** Market Briefing Message & Operation | 메시지·반복 억제·PUSH | `02B-1` 판정 후 |

`02B-1` 에서 **Telegram 본문·반복 억제·autosend 활성화는 구현하지 않습니다.**
전망과 섹터가 **모두** 사용 불가면 `02B-2` 를 억지로 만들지 않고 POC3 을 계속
열린 상태로 둡니다.

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

## 2. 부족한 미국 지표 — 최소 수집 방법과 backfill 범위

### 2.1 미국 지표 6종 현황

| 지표 | DB 존재 | FDR 심볼(후보) | 필요 조치 |
|---|---|---|---|
| S&P500 | **없음** | `US500` 또는 `^GSPC` | 신규 수집 + backfill |
| Nasdaq | **없음** | `IXIC` | 신규 수집 + backfill |
| 반도체(SOX) | **없음** | `SOX` | 신규 수집 + backfill · **심볼 검증 필요** |
| Russell 2000 | **없음** | `RUT` | 신규 수집 + backfill |
| VIX | 있음(3,079행) | `VIX` (기존 `vix_ingest.py`) | **정체 해소만** |
| USD/KRW | **없음** | `USD/KRW` | 신규 수집 + backfill · **심볼 검증 필요** |

### 2.2 **symbol probe 선행** — 적재 전 필수 (설계자 확정 §12.7-2)

5종을 **바로 적재하지 않습니다.** 각 후보 symbol 에 대해 먼저 확인합니다.

| 확인 항목 | 왜 |
|---|---|
| 실제 지표 identity | `US500` 이 S&P500 현물인지 선물인지, `SOX` 가 PHLX 반도체지수인지 |
| 최초·최종일 | 750일 표본 가능 여부 |
| `close` 결측률 | 커버리지 95% 기준 |
| source date | session date 인지 적재일인지 |
| 동일 요청 재현성 | 같은 구간 재호출 시 동일 값 |
| **한국 개장 전 확정 여부** | PIT 위반 방지 |

**`SOX` · `USD/KRW` 처럼 symbol 의미가 불명확하면 확인 전 적재 금지입니다.**

### 2.3 최소 수집 방법 — 신규 의존성 0

`finance-datareader>=0.9.202` 가 **이미 선언돼 있고**(`requirements.txt:15`) VIX
수집이 `fdr.DataReader("VIX", start, end)` 로 이미 동작합니다
(`scripts/_market_refresh/vix_ingest.py:54`). 같은 방식으로 5종을 추가합니다.

- 저장처: **기존 `market_benchmark_daily_price` 유지**, `benchmark_id` 만 추가.
  **신규 테이블·대규모 컬럼 migration 없음**(설계자 확정 §12.2).
  `date` = session date · `created_at` = 적재 시각 · `source` = 원천.
  **timezone·통상 종료시각·freshness 규칙은 코드의 정적 catalog** 로 관리하고,
  반환 evidence 에 각 benchmark 의 `as_of_date` 와 계산된 freshness 를 담습니다.
  **기존 행에 알 수 없는 timestamp 를 소급 생성하지 않습니다.**
- 진입점: 기존 `scripts/refresh_market_timeseries.py` 에 서브커맨드 추가.
  **신규 cron 은 만들지 않습니다** — §2.3 참조.

### 2.4 backfill 범위 예상

| 대상 | 기간 | 예상 행수 |
|---|---|---|
| 미국 지수 4종 + 환율 1종 | 2014-04 ~ 현재 (KODEX200 축과 정렬) | 약 **3,100행 × 5 = 15,500행** |
| KODEX200 `open` **재적재** | 2014-04-09 ~ 2026-03-05 | 약 **2,919행** |

> **KODEX200 `open` 이 이번 설계의 최대 병목입니다.** 예측 대상이 시가 기반인데
> `open` 은 **2026-03-06부터 126일**만 있습니다(로컬·OCI 동일). 2026-03-05
> 이전은 전부 `NAVER_FDR` 출처이고 `open`=NULL 입니다. FDR 어댑터는 `Open` 을
> 읽도록 이미 구현돼 있습니다(`market_data_fdr.py:219`).
>
> **확정 절차 (설계자 §12.5)** — ① FDR 반환값을 **1개 짧은 구간에서 probe** →
> ② 성공하면 **기존 `close` 를 보존**하면서 `open` 만 backfill → ③ **정렬 표본
> 750일 이상일 때만** 평가 실행 → ④ 750일 미만이면 **`NOT_EVALUATED`**.
> **126일 소표본으로 임계값을 완화하지 않고, 당일 종가 수익률로 target 을
> 바꾸지 않습니다.**

### 2.5 OCI 배치가 benchmark 를 갱신하지 않습니다 — §4 결함의 절반

OCI cron 실측(2026-09-08): 러너 11건 + `run_oci_market_data_batch.py` 1건.
그 배치는 `refresh_approved_prices`(ETF 가격)만 호출하고 **KOSPI·VIX 갱신을
호출하지 않습니다.**

- `refresh_kospi_benchmark` → `app/market_refresh_service.py:318` (**`POST
  /market/refresh` 경로 = Mac 수동**)
- VIX → `scripts/refresh_market_timeseries.py vix` (**독립 스크립트, cron 미등록**)

그래서 ETF 가격은 2026-09-07 로 최신인데 KOSPI·VIX 만 **2026-07-03** 에 멈춰
있습니다. 미국 지표를 새로 수집해도 **같은 자리에 놓으면 같은 이유로 멈춥니다.**

---

## 3. 섹터 분류 원천 — 후보와 확정 절차

### 3.1 현재 없는 것

- ETF별 **추종지수·기초지수 식별자 없음** (`etf_master` 8컬럼에 해당 없음)
- 섹터·테마 분류 없음 (`category` = `"1"`~`"7"` 자산군: 381/339/174/124/99/38/23)
- `etf_constituents` **OCI 24 / 1,146 = 2.1%** — 구성종목 기반 클러스터링 불가

### 3.2 후보

| # | 원천 | 얻는 것 | 비용 | 위험 |
|---|---|---|---|---|
| A | **KRX 정보데이터시스템** ETF 기초지수 | 공식 기초지수명·지수코드 → **중복 제거의 정본** | 신규 수집기 1개 | 비공식 endpoint 아님 · 규격 안정 |
| B | Naver ETF 목록 API 분류 탭 | 테마/업종 분류 | 기존 Naver 어댑터 확장 | **비공식** · 분류 기준 불투명 |
| C | `etf_constituents` 확대 후 구성종목 유사도 | 중복·섹터 동시 해결 | 1,146종목 수집 + 주기 갱신 | 비용 최대 · 2.1%→100% 는 별도 Step 규모 |
| D | ETF명 문자열 파싱 | — | — | **설계서 §5 가 명시적으로 금지** |

### 3.3 확정 — **KRX 읽기 전용 probe 승인** (설계자 §12.3)

**수집기를 바로 만들지 않습니다.** 먼저 읽기 전용 probe 로 확인합니다.

| probe 확인 항목 |
|---|
| ETF ticker |
| 기초지수 **코드** |
| 기초지수명 |
| **구조화된 기초시장·국가·자산·업종·테마 분류 필드** |
| 전체 ETF 커버리지 |
| 응답 안정성 및 인증 필요 여부 |

**핵심 구분**

- 기초지수 코드는 **동일지수 ETF 중복 제거만** 해결합니다.
- 서로 다른 기초지수를 **같은 섹터로 묶으려면 구조화된 분류 필드가 별도로**
  있어야 합니다.
- **기초지수명 문자열을 개발자가 해석해 임의 섹터로 묶지 않습니다.**
- 공식 원천에 구조화된 섹터/테마 필드가 **없으면 `SECTOR_NOT_EVALUATED`** 로
  반환합니다. 그 경우 **후보 B(Naver 분류)를 자동 채택하거나 D(ETF명 추론)로
  우회하지 않습니다.**
- 필드·커버리지가 확인된 **경우에만** 이번 Step 전용 KRX 메타데이터 수집기
  **1개**를 만듭니다. 범용 KRX 플랫폼·구성종목 100% 수집으로 확대하지 않습니다.

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

### 4.3 판정 원칙

KODEX200 과 KOSPI 수익률 차이가 크다는 사실만으로 어느 쪽을 정답으로 두지
않습니다. **원천 행을 직접 읽어 독립 재계산**한 값과 대조해 판정합니다.
`market_discovery.extra_notes` 의 KOSPI 문장은 검증 종료 전까지 새 브리핑에서
재사용하지 않습니다(설계 §6).

---

## 5. 미국–한국 거래일 PIT 정렬 방법

### 5.1 정렬 규칙

한국 거래일 `t_kr` (KODEX200 거래일 축, OPS-01A/02A 와 동일 축 재사용)에 대해:

```
사용 가능한 미국 관측일 u = max{ u : u 의 미국 세션 종료시각 < t_kr 개장시각 }
```

- 미국 세션 종료 16:00 ET, 한국 개장 09:00 KST
- ET→KST 는 서머타임에 따라 **+13h / +14h** 로 달라집니다. **날짜 문자열을
  같은 날로 잇지 않습니다**(설계 §7). **DST 는 표준 `zoneinfo` 로 처리**하고
  오프셋을 상수로 두지 않습니다(설계자 §12.2).
- benchmark 별 **timezone·통상 종료시각은 코드의 정적 catalog** 로 관리합니다.
- 통상 `u = t_kr 의 전일(미국 거래일)`. 한국 연휴 뒤에는 **여러 미국 세션이
  누적**되므로 `u` 는 가장 최근 1개만 쓰고, 누적 개수를 진단에 남깁니다.
- **USD/KRW 는 원천이 실제로 주는 것만 씁니다** (설계자 §12.2). 일별 값만
  제공되면 **`07:50 현재` 라고 표현하지 않습니다.** PIT 시점이 불명확하면
  **예측 입력에서 제외**합니다. 설계서 §2 예시의 `환율 09-08 07:50` 은 원천이
  그 시각 값을 실제로 줄 때만 유효합니다 — probe 로 확인합니다(§2.2).

### 5.2 기존 계약 재사용

`market_flow_dataset.py` 가 VIX 에 대해 이미 **strictly-prior** 를 쓰고
`vix_source_date` · `vix_lag_calendar_days` 를 ID 컬럼으로 남깁니다. 같은 패턴을
미국 지표 5종에 확장합니다 — **신규 발명 없음.**

### 5.3 검증

정렬이 미래를 보지 않는지는 **역검증**으로 고정합니다(§10 R-3·R-4).

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

1. `open` backfill → **실측 표본 일수 보고** (750 미달이면 여기서 중단·보고)
2. 미국 5종 backfill → **입력 커버리지 산출** (95% 미달이면 중단·보고)
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

## 7. 상승 섹터 산출식과 중복 제거 계약

**§3 probe 에서 구조화된 분류 필드가 확인된 경우에만** 적용합니다. 없으면
`SECTOR_NOT_EVALUATED` 로 반환하고 아래 산출식을 쓰지 않습니다.

```
섹터 그룹핑 : 기초지수 코드 기준 (ETF명 문자열 금지)
중복 제거   : 동일 기초지수 → 1개로 축약 (거래대금 최대 1종목 대표)
섹터 수익률 : 중복 제거 후 그룹 구성원의 5d·20d 수익률 **중앙값**
상승 비율   : 중복 제거 후 그룹 내 20d 수익률 > 0 인 비율
```

**후보 조건 (설계 §5 그대로)**

| 조건 | 값 |
|---|---|
| 서로 다른 추종지수·독립 상품 | **2개 이상** |
| 5거래일 대표수익률 | **> 0** |
| 20거래일 대표수익률 | **> 0** |
| 그룹 내 상승 비율 | **> 50%** |
| 본문 노출 | **상위 2개까지** |
| 충족 섹터 0개 | **섹터 문단 생략** |

중앙값을 쓰므로 개별 최고 ETF 가 그룹을 끌어올리지 못합니다.

---

## 8. 목업 3종

> **본 절은 `OPS-02B-2` 범위입니다.** `02B-1` 에서는 본문·억제·발송을 구현하지
> 않습니다(설계자 §12.1). 아래는 형식 참고용이며 수치는 합성입니다.
> 실제 데이터로 생성한 것이 아닙니다(수집 미실행).

### 8-A. `ADOPT_OUTLOOK`

```text
[시장 흐름 브리핑] 08:00

오늘 한 문장
미국 기술주와 반도체가 함께 약세이고 원/달러도 상승해,
한국 성장주 개장에는 하락 압력이 우세합니다.

오늘 볼 섹터
바이오헬스케어 — 최근 5일·20일 흐름이 모두 상승하고
같은 섹터의 여러 ETF가 함께 움직이고 있습니다.

근거
Nasdaq −1.2% · 반도체 −2.1% · 원/달러 +0.4%

기준
미국 09-07 종가 · 국내 09-07 종가 · 환율 09-08 07:50
```

> 환율 시각 표기는 **원천이 실제로 그 시각 값을 줄 때만** 씁니다(§5.1).

### 8-B. `FACT_ONLY`

```text
[시장 흐름 브리핑] 08:00

오늘 한 문장
밤사이 미국시장은 혼조여서 한국 개장 방향을 정할 근거가 약합니다.

오늘 볼 섹터
바이오헬스케어 — 최근 5일·20일 상승 흐름이 이어지고
같은 섹터의 여러 ETF가 동행하고 있습니다.

근거
S&P500 +0.3% · Nasdaq −0.4% · 반도체 −0.8%

기준
미국 09-07 종가 · 국내 09-07 종가
```

### 8-C. `no_change` / no-send

**발송하지 않습니다.** 실행 이력에만 남습니다.

```json
{
  "push_kind": "market_briefing",
  "status": "skipped",
  "reason": "no_change",
  "outlook_state": "FACT_ONLY:MIXED",
  "sector_state": "바이오헬스케어|2차전지",
  "state_fingerprint": "FACT_ONLY:MIXED#바이오헬스케어|2차전지",
  "previous_fingerprint": "FACT_ONLY:MIXED#바이오헬스케어|2차전지",
  "us_asof": "2026-09-07",
  "kr_asof": "2026-09-07",
  "telegram_attempted": false
}
```

stale·문장 미생성 시 `reason` 은 `all_data_stale` / `no_publishable_sentence` 로
구분합니다.

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
| R-3 | **당일 미국 종가**(한국 개장 후 확정)를 입력에 포함 | 탐지 |
| R-4 | walk-forward 를 전체 fit 재사용으로 | 탐지 |
| R-5 | **표본 부족인데 `REJECT`** 로 기록 | 탐지 |
| R-6 | 통계 미달인데 `ADOPT_OUTLOOK` | 탐지 |
| R-7 | 750일 미만에서 **임계값 완화**해 평가 실행 | 탐지 |
| R-8 | `open` backfill 이 기존 **`close` 를 덮어씀** | 탐지 |
| R-9 | 섹터를 **ETF명 문자열**로 분류 | 탐지 |
| R-10 | 구조화 분류 필드가 없는데 **Naver 분류 자동 채택** | 탐지 |
| R-11 | 동일 기초지수 복제 상품을 개별 계수 | 탐지 |
| R-12 | 섹터 수익률을 중앙값 아닌 **최대값**으로 | 탐지 |
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
| Q5 `open` backfill 실패 | **(b) 제한** — probe → 750일 미만이면 `NOT_EVALUATED` (§12.5) |
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

### 12.5 `open` backfill

probe → `close` 보존 backfill → **750일 이상일 때만 평가** → 미달이면
`NOT_EVALUATED`. **임계값 완화 금지 · target 변경 금지 · 개장 전망 문구 미사용.**
미국시장 사실과 상승 섹터는 **각각 독립 판정**합니다.

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

---

## 13. `OPS-02B-1` 종료 산출물

| # | 산출물 |
|---|---|
| 1 | 데이터별 **probe·backfill 결과** |
| 2 | **실제 정렬 표본 수와 커버리지** |
| 3 | KOSPI/VIX **독립 재계산 결과** |
| 4 | **VIX stale 소비 영향** |
| 5 | 섹터 메타데이터 **필드·커버리지** |
| 6 | **전망 판정** |
| 7 | **섹터 판정** |
| 8 | 최종 결론 |

```text
OUTLOOK=ADOPT_OUTLOOK|FACT_ONLY|REJECT|NOT_EVALUATED
SECTOR=AVAILABLE|NOT_EVALUATED
NEXT=START_02B_2|REMAIN_BLOCKED
```

> 구현 중 **외부 source 의 identity·필드가 PLAN 과 다르거나 `open` 750일 확보가
> 실패하면 임의 대체하지 말고 그 사실만 반환**합니다.

---

## 14. 착수

설계자 **`APPROVED_WITH_REQUIRED_EDITS`** — 필수 수정 3건을 V1.1 에 반영했으므로
**재검토 없이 `OPS-02B-1` 구현에 착수**합니다.

조사 단계에서 수행한 것: 로컬 DB 읽기 · OCI 읽기 전용 SSH · 소스 grep.
**쓰기·발송·수집 실행 0건.**
