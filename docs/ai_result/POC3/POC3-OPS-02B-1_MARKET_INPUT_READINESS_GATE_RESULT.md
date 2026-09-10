# POC3-OPS-02B-1 — Market Input Readiness & Validity Gate · 개발 결과서

- **입력 문서**: `docs/ai_plan/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_PLAN_V1.md` (V1.5)
- **설계서**: `docs/ai_design/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_DESIGN_V1.md` (V1.2)
- **작성일**: 2026-09-10 · **독자**: 검증자(Codex)
- **커밋**: `48babf04`(코드·산출물) · `40f1dabd`(결과서) · **r3 보완분**
- **라운드**: r2 (검증자 r1 `REJECTED` → 재제출)

## 0) 현재 상태

| 항목 | 값 |
|---|---|
| `OUTLOOK_RELATIONSHIP` | `ADOPT` |
| `OPERATING_RULE` | `SP500_SIGN_V1` |
| `OLS` | `RESEARCH_REFERENCE` |
| `SECTOR` | `NOT_EVALUATED` |
| `INDEX_LEADERSHIP` | `AVAILABLE` |
| `KOSPI_VIX_INTEGRITY` | `PASS` |
| `implementation` | `DONE` |
| `verification` | **검증 대기** |
| `deployment` | `NOT_DEPLOYED` |
| `autosend (08:00)` | **`false`** |
| `step_status` | `GATE_COMPLETE_PENDING_VERIFICATION` |

> **`ADOPT` 는 미국시장–한국 개장 갭의 방향 관계가 유효하다는 판정이지 OLS 의
> 운영 채택 판정이 아니다.** 운영 규칙은 `SP500_SIGN_V1` 이다.

**본 Step 에서 하지 않은 것** — Telegram 본문·반복 억제·autosend 활성화 구현 ·
OCI 배포 · 실제 발송 · `etf_daily_price` 변경 · ML 재학습.

---

## 1) 처리한 요구사항

| # | 요구사항 (설계자 판정) | 상태 | 근거 |
|---|---|---|---|
| 1 | `OPEN_GAP` 을 **KRX 무조정 단일 원천**으로 평가 | DONE | §3.1 |
| 2 | 미국 지표 **symbol probe 선행** 후 사용 | DONE | §3.2 |
| 3 | **USD/KRW PIT 분리** 후 표본·커버리지 재산출 | DONE | §3.3 |
| 4 | 운영 규칙 **`SP500_SIGN_V1`** 수치 산출 | DONE | §3.4 |
| 5 | `SECTOR = NOT_EVALUATED` 확정 | DONE | §3.5 |
| 6 | `INDEX_LEADERSHIP` **`n ≥ 2`** 적용 | DONE | §3.6 |
| 7 | KOSPI/VIX 결함 **계약 7개** | DONE | §4 |
| 8 | 배치 계약 3개 (분리 기록·은폐 금지·롤백 금지) | DONE | §4.2 |
| 9 | `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` **읽기 전용 기록** | DONE | §5 |
| 10 | VIX stale 소비 영향 **읽기 전용 확인** | DONE | §6 |
| 11 | 정적 메타데이터 **공식 CSV versioned snapshot** 계약 | DONE | §7 |
| 12 | Gate 근거 **독립 재현 경로** | DONE | §7 |

---

## 2) 변경된 파일 목록 (커밋 `48babf04`)

### 신규

| 파일 | 줄 | 역할 |
|---|---:|---|
| `app/market_benchmark_freshness.py` | 122 | 거래일 **날짜 기준** 수익률 · 자기 `as_of_date` · freshness |
| `app/market_benchmark_batch.py` | 149 | 운영 배치용 KOSPI·VIX 갱신 (개별 상태 반환) |
| `scripts/ops02b1_gate/reproduce.py` | 454 | Gate 재현 단일 진입점 (읽기 전용) |
| `scripts/ops02b1_gate/fetch_snapshot.py` | 116 | KRX snapshot 재수집 (`KRX_API_KEY`) |
| `tests/test_market_benchmark_freshness.py` | 448 | 계약 test **24건** |
| `state/ops02b1_gate/*` (7종) | — | Gate 입력 snapshot + `MANIFEST.json` |
| `state/market_meta/krx_etf_basic_20260909.csv` | 1,168행 | 공식 KRX ETF 기본정보 (cp949) |

### 수정

| 파일 | 변경 |
|---|---|
| `app/market_regime.py` | `compute_kospi_metrics` 날짜 기준 재작성 · `compute_market_context` 에 `asof_source` |
| `app/market_summary_composer.py` | stale KOSPI 값 차단 · `freshness` 노출 |
| `app/three_push_runtime/market_data_batch.py` | `write_batch_state` 스키마 확장 (benchmark 5필드) |
| `scripts/run_oci_market_data_batch.py` | §2-b benchmark 갱신 · 종료 status 분기 |
| `tests/conftest.py` | 라이브 DB 갱신 **차단 가드 2종** |
| `.gitattributes` | Gate CSV **byte 보존** (sha256 계약) |
| `docs/ai_plan/.../PLAN_V1.md` | V1.5 |

**삭제** — `state/tmp_krx_etf_basic.csv` (사용자 승인. 정본과 sha256 동일
`bf07e52b…bc576` 확인 후, 정본 stage → 삭제 → 무결성 재확인 순서)

**git 상태 (커밋 후 실측)** — `git status --short --untracked-files=all` **출력 없음** (clean).

---

## 3) Gate 결과

### 3.1 `OPEN_GAP` 원천

```text
OPEN_GAP_t  = KRX t일 무조정 시가 / KRX 직전 거래일 무조정 종가 - 1
source      = KRX_OPEN_API   price_basis = UNADJUSTED_TRADED_PRICE
```

배당조정 계열은 **배당락일의 갭을 지워** 측정 대상을 훼손하므로 무조정가를 쓴다.
`069500` 평가 행만 추출했고 **`etf_daily_price` 는 읽지도 쓰지도 않았다.**

| 항목 | 값 |
|---|---|
| 행 수 | **2,867일** (`20150102` ~ `20260907`) |
| 결측 | 1일 (`20260908` KRX 미제공) |
| sha256 | `ca94dffbc37aa338ea6e4e98196c6a4793a741aa4cbe10954c3d3d7304e6d361` |

**한계** — 무조정가에는 분배락 실제 가격 변화가 포함된다. 공식 분배락 날짜를
확보하지 못해 **임의 보정하지 않고 한계로 기록**한다.

### 3.2 미국 지표 symbol probe

| 지표 | symbol | 행수 | `Close` 결측 |
|---|---|---:|---:|
| S&P500 | `US500` | 2,937 | 0 |
| Nasdaq | `IXIC` | 2,937 | 0 |
| 반도체 | **`^SOX`** | 2,937 | 0 |
| Russell 2000 | `RUT` | 2,937 | 0 |
| VIX | `VIX` | 3,049 | 110 |
| USD/KRW | `USD/KRW` | 3,049 | 8 |

`SOX` 는 `KeyError: 'timestamp'` 로 실패하고 **`^SOX` 로만** 조회된다. 동일 구간
2회 호출 결과 일치.

### 3.3 PIT 정렬 — USD/KRW 분리

| 그룹 | 규칙 |
|---|---|
| S&P500·Nasdaq·`^SOX`·Russell·VIX | 미국 세션 종료(16:00 ET) < 한국 개장(09:00 KST). DST 는 `zoneinfo` |
| **USD/KRW** | 일별 종가만 제공되고 **제공 완료 시각 증명 불가 → primary 제외** |

**재산출 결과**

| 항목 | 값 |
|---|---|
| primary 5종 완비 | **2,758 / 2,866 = 96.2%** |
| 750일 요구 | **충족** |
| 95% 커버리지 | **충족** |
| Gate 사용 feature | `sp500_ret_1d_pct` · `nasdaq_ret_1d_pct` · `sox_ret_1d_pct` · `russell_ret_1d_pct` · `vix_ret_1d_pct` |

USD/KRW 는 `usdkrw_ret_1d_pct`(엄격히 앞선 날짜)로 데이터셋에 남겼고 **평가에
쓰지 않았다.**

### 3.4 `OPERATING_RULE = SP500_SIGN_V1`

같은 표본, 같은 예측 구간(2018-03-15 ~ 2026-09-07).

| 항목 | `SP500_SIGN_V1` | (참고) OLS |
|---|---|---|
| 방향 적중률 | **74.25%** · 95%CI **[72.26, 76.13]** | 76.39% |
| 다수방향 baseline | 57.32% | 57.32% |
| 개선폭 | **+16.93%p** | +19.07%p |
| S&P 상승일 갭 평균 | **+0.5058%** (n=1,086) | — |
| S&P 하락일 갭 평균 | **−0.4191%** (n=916) | — |
| 상승·하락일 차이 | **+0.9249%** · 95%CI **[+0.8338, +1.0174]** | — |

| 사전 기준 | 판정 |
|---|---|
| 적중 CI 하한 > 50% | **PASS** |
| baseline 대비 +5%p 이상 | **PASS** |
| 상승·하락일 갭 차이 CI > 0 | **PASS** |

전체 표본(2,758일): 74.63% · CI [72.95, 76.27] · +17.47%p · 차이 +0.7966% ·
CI [+0.7260, +0.8684] — **같은 결론.**

**운영 표현 제약** — 방향 압력까지만. **한국 개장 예상 등락률 숫자 미표시**
(calibration 검증 없음). Nasdaq·`^SOX`·Russell·VIX 는 설명 evidence 로만 쓰고
**임의 가중 규칙을 추가하지 않는다.**

**OLS 누수 검사 6종 — 전부 통과**

| 검사 | 결과 |
|---|---|
| target 셔플 ×3 | **52.97 / 55.39 / 56.10%** |
| feature 1세션 지연 | **53.75%** |
| feature 2세션 지연 | 53.54% |
| target +1일 이동 | 53.75% |
| 단변량 `sign(VIX)` | 29.32% (역방향 = 위험회피) |
| `OPEN_GAP` 분포 | 평균 +0.071% · 표준편차 1.024% · 상승 55.6% |

### 3.5 `SECTOR = NOT_EVALUATED`

| 원천 | 결과 |
|---|---|
| KRX 공식 CSV (17컬럼) | 기초지수명·지수산출기관·추적배수·복제방법·기초시장분류·기초자산분류 **있음**. **업종/테마 분류 없음** |
| KRX Open API (19필드) | `IDX_IND_NM` 은 **기초지수명**. 업종·테마 분류 아님 |
| `pykrx` | `KRX_ID`/`KRX_PW` 요구 → 사용 불가 |
| KRX 웹 JSON | 세션 쿠키 확보 후에도 `HTTP 400 LOGOUT` |

`기초시장분류`(국내 645·해외 467·국내&해외 56)와 `기초자산분류`(주식 849·채권
162·혼합 81·기타 26·원자재 24·부동산 14·통화 12)는 **지역·자산군이지 섹터가
아니다.** 기초지수명 문자열 해석·Naver 분류 자동 채택·ETF명 추론 **하지 않았다.**

### 3.6 `INDEX_LEADERSHIP = AVAILABLE`

| 항목 | 값 |
|---|---|
| 메타데이터 | 1,168종 |
| 필터 후 (주식 · 일반 · 실물) | **726종** |
| 기초지수 그룹 (`지수산출기관 + 기초지수명` 완전일치) | **573개** |
| **`n ≥ 2` 풀** | **43개** |
| join coverage | **100%** (≥95% 충족) |
| API `IDX_IND_NM` ↔ CSV 기초지수명 | **1,167 / 1,167 = 100% 완전일치** |

**날짜별 후보 수** (최근 21거래일)

| 지표 | 값 |
|---|---|
| 중앙값 | **11개** |
| 범위 | 0 ~ 31개 |
| 2개 이상인 날 | **18 / 21** |
| 0개인 날 | 3 / 21 → **문단 생략** |

> **설계자 판정문의 "현재 43개 그룹이 남으므로" 는 두 조건의 교집합이 아니다.**
> 43 은 `n ≥ 2` **풀**이고, 특정일 후보 수는 그날 수익률에 따라 달라진다.
> 2026-09-04 기준으로는 1개(`KRX 은행`)였다. **`AVAILABLE` 판정은 유지된다.**

---

## 4) KOSPI/VIX 결함 — `PASS`

### 4.1 계약 7개

| # | 계약 | 구현 |
|---|---|---|
| ① | 배치에서 갱신 경로 확보 | `app/market_benchmark_batch.py` → `run_oci_market_data_batch.py` §2-b |
| ② | 각 benchmark 자기 `as_of_date` | `compute_kospi_metrics` 가 `as_of_date`·`freshness` 반환 |
| ③ | **실제 거래일 날짜 기준** 수익률 | `return_by_trading_days` — 위치 인덱스 폐기 |
| ④ | 최신성 1거래일 초과 시 **미산출** | `status="stale"` + 수익률 키 자체 미포함 |
| ⑤ | stale 을 최신 `asof` 로 표시 금지 | `asof_source="KODEX200"` · composer 차단 |
| ⑥ | 일부 실패 시 **실패 블록만 제외** | KOSPI stale 이어도 KODEX200 국면 유지 |
| ⑦ | stale VIX 영향 읽기 전용 확인 | §6 |

**원인 2개** (V1.3 조사)

1. **운영** — OCI 07:20 배치가 benchmark 갱신을 호출하지 않았다.
   `refresh_kospi_benchmark` 는 `POST /market/refresh`(Mac 수동) 경로에만, VIX 는
   cron 미등록 스크립트에만 있었다. → ETF 가격 2026-09-07 vs KOSPI·VIX 2026-07-03
2. **계산·표시** — `compute_kospi_metrics` 가 날짜를 버리고 `closes[-1]` /
   `closes[-(n+1)]` 위치 인덱스로 계산했고, 결과에 자기 기준일이 없어
   `compute_market_context` 의 상위 `asof` 로 표시됐다.

### 4.2 배치 계약 3개

| # | 계약 | 구현 |
|---|---|---|
| 1 | ETF 가격 성공과 benchmark 성공 **별도 기록** | `record`·`write_batch_state` 에 `price_pipeline_status` / `benchmark_status` / `benchmark_failed` / `kospi_as_of` / `vix_as_of` |
| 2 | benchmark 실패를 **전체 성공으로 숨기지 않음** | 종료 status **`success_with_benchmark_failure`** |
| 3 | benchmark 실패로 **ETF 가격 롤백 안 함** | `price_pipeline_status="success"` 유지 |

`refresh_benchmarks` 는 **`Exception` 만** catch 한다 — `BaseException`(종료
신호)을 삼키면 배치가 죽는 중에도 정상 종료로 보인다.

**부수 영향 1건** — `spike_freshness` 는 `status == "success"` 만 통과시키므로
benchmark 실패 시 spike 가 **fail-closed** 된다. `spike_or_falling_alert` 는 cron
이 교체돼 실행되지 않으므로 **운영 영향 없음.**

---

## 5) `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` (읽기 전용)

`status = INVESTIGATION_REQUIRED` · **수정 0건.**

| 요구 기록 | 실측 |
|---|---|
| 전체 기간 KRX/DB 비율 | 2015Q2 **+23.92%** → 2026Q1 **+0.03%** (단조 감소) |
| 전환 후보일 | **39건.** 2025-01-24 · 04-29 · 07-30 · 10-30 · 2026-01-29 · 04-29 · 07-30 — **분기 배당락 패턴** |
| 영향 ticker 범위 | `NAVER_FDR` 1,063종(~2026-03-05) · `FinanceDataReader` 1,181종(2026-02-19~). **2026-02-19~03-05 중첩** |
| 소비 경로 | 수익률(`market_regime`·`market_topn`) · ML(`market_flow_dataset`·`ml_feature_builder`) · UI/API(`api_market_topn_service`·`api_price_series`) · PUSH(보유 브리핑·급락 알림) |
| **현재 운영 수치 실영향** | **없음** — PUSH·수익률은 **DB 단일 계열 안에서** 상대 계산하므로 균일 배수가 상쇄된다. KRX snapshot 은 Gate 평가 전용. **계열 혼합 0건** |

누적 괴리(11년 +23.9% ≈ 연 1.9%)가 KODEX200 분배금 수익률과 부합하고 전환일이
분기 배당락일과 겹친다 → **DB = 배당조정 계열, KRX = 무조정 실거래가**로 설명된다.
**미해명 1건** — 2026-04-17 `+0.000%` → 04-20 `+0.646%` 는 유일한 역방향 계단이다.

---

## 6) VIX stale 소비 영향 (읽기 전용)

| 확인 | 결과 |
|---|---|
| OCI benchmark 최신성 | KOSPI·VIX **2026-07-03** / ETF 가격 2026-09-07 |
| OCI ML artifact | **없음** — ML 은 OCI 에서 돌지 않는다 |
| PUSH 본문 VIX·변동성 문구 | **0건** |
| 결론 | **운영 발송 경로에 stale VIX 소비 없음** |

ML 재학습·artifact 재생성·상대상승 모델 재개 **하지 않았다.**

---

## 7) 재현 경로

```bash
python scripts/ops02b1_gate/reproduce.py            # 전체
python scripts/ops02b1_gate/reproduce.py operating  # 일부
```

**운영 DB 를 읽지 않는다** — `sqlite3` import 자체가 없다. 커밋된 snapshot 만
쓰고 **tracked 산출물도 덮지 않는다**(결과 JSON 갱신은 `--write` 를 준 실행만).
무결성 불일치·표본 미달·coverage 미달·스크립트 부재 시 **exit code 1**.

| 입력 | 경로 | 행 수 | sha256 |
|---|---|---:|---|
| 공식 KRX ETF 기본정보 | `state/market_meta/krx_etf_basic_20260909.csv` | 1,168 | `bf07e52bea461b23c2402e61b5224fc1e89078e8f320f6f0742948a09e0bc576` |
| KRX `069500` 무조정 | `state/ops02b1_gate/krx_069500_snapshot.csv` | 2,867 | `ca94dffbc37aa338ea6e4e98196c6a4793a741aa4cbe10954c3d3d7304e6d361` |
| PIT 정렬 데이터셋 | `state/ops02b1_gate/gate_dataset.csv` | 2,866 | `a8e36743ffa42f95e51dbc892b5eca1b927631e05cef81663e681655ab631435` |
| KRX API 기초지수명 | `state/ops02b1_gate/krx_api_idxname_20260904.csv` | 1,167 | `e5627965e6eaf5e84ecf23bc8b8b59f9f7c27fe416cddd809b1e68c05e5e3428` |
| ETF 종가(41거래일) | `state/ops02b1_gate/etf_close_snapshot.csv` | 7,984 | `4caa9d9c90d37c1c8b75c70cd4ec4f9d9bd8e113cd9d7f06bf469a870f4a961c` |
| `etf_master` ticker | `state/ops02b1_gate/etf_master_tickers.csv` | 1,178 | `4c186184953a1f52613f33ce0a8d521699f8d865fbde43fd9db369c480eba493` |
| DB `069500` 종가 | `state/ops02b1_gate/db_069500_close_snapshot.csv` | 3,044 | `caaae26e94451ddcb79944777cc8da05810658662d0ed1631152b301a177231b` |

**커밋된 blob 7종이 위 sha256 과 일치함을 `git cat-file` 로 확인**했다.
`.gitattributes` 에 `state/ops02b1_gate/*.csv -text` · `state/market_meta/*.csv
-text` 를 넣어 줄바꿈 정규화로 hash 가 깨지지 않게 했다(공식 CSV 는 **cp949**).

**공식 CSV 계약 이행** — `source=KRX_OFFICIAL_CSV` · `asof_date=2026-09-09` ·
`rows=1168` · sha256 · API ticker 완전일치 join · 지수명 불일치 제외 · coverage
95% 게이트 · **수동 편집본·가공 분류표 없음**(다운로드 원본 그대로).

---

## 7.1) fail-closed 실증 (r3 신규)

계약 이하 입력이 **성공으로 끝나지 않는지**를 코드로 고정했다. 이전 라운드에는
계약이 문서에만 있었다.

| 강제 입력 | 결과 |
|---|---|
| coverage **0%** | `evaluate_coverage → ok=False` |
| coverage **94%** | `ok=False` |
| 표본 **700일**(비율 100%) | `ok=False` |
| 지수명 불일치 1종 | **제외됨** (`name_mismatch`) |
| API 부재 1종 | **제외됨** (`not_in_api`) |
| join coverage < 95% | **블록 전체 미산출** + `return False` |
| 섹션 실패 | `main() → exit 1` |

현재 snapshot 실행에서 **API 부재 1종(`0238P0`)이 실제로 제외**된다. 그 종목은
혼합자산이라 상품 필터에서도 걸러지므로 **`INDEX_LEADERSHIP` 수치에는 영향이
없다**(검증자 확인과 일치).

---

## 8) 알려진 한계 / 미완성

| # | 한계 |
|---|---|
| 1 | 분배락 날짜 미확보 — 무조정가 민감도 분석을 하지 못했다(§3.1) |
| 2 | `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 는 **미수정**. 2026-04-17→04-20 역방향 계단과 source 중첩 구간이 미해명 |
| 3 | `INDEX_LEADERSHIP` 후보가 **0개인 날이 21일 중 3일** — 그날은 문단이 생략된다 |
| 4 | 정적 메타데이터가 **수동 다운로드**다. 자동 갱신 경로는 `02B-2` 결정 |
| 5 | `2026-09-08` KRX snapshot 결측 1일 (KRX 미제공) |
| 6 | 로컬 Mac DB 에 테스트가 쓴 KOSPI 120행·VIX 48행이 남아 있다 (§9) |

---

## 9) 검증자에게 알릴 점

### 9.1 우선 볼 곳

| # | 항목 |
|---|---|
| 1 | **배치 종료 분기** — `run_oci_market_data_batch.py` 가 benchmark 실패 시 `success_with_benchmark_failure` 로 끝나고 영구 상태에 5필드를 남기는지. 흐름 테스트 3건으로 고정 |
| 2 | **stale 차단** — `compute_kospi_metrics` 가 stale 이면 수익률 키를 **아예 넣지 않는지**, composer 가 값을 막는지 |
| 3 | **날짜 기준 계산** — `return_by_trading_days` 가 결측일에 더 오래된 값으로 대체하지 않는지 |
| 4 | **재현성** — `reproduce.py` 를 직접 실행해 §3 수치가 나오는지. **exit code** 확인 |
| 5 | **conftest 가드** — 라이브 DB 갱신 차단이 우회 가능한 경로가 남았는지 |

### 9.2 이전 라운드에서 제가 틀렸던 것

| # | 내용 |
|---|---|
| 1 | **bootstrap CI 재현 불가** — 공유 RNG 를 순서대로 소비해 스크립트 구성이 바뀌면 값이 달라졌다. 항목별 독립 RNG 로 고쳤고 **CI 4개를 정정**했다. 점추정·판정은 불변 |
| 2 | **테스트가 라이브 DB 를 변경** — 배치에 benchmark 갱신을 붙이면서 기존 테스트를 격리하지 않았다. 로컬 Mac DB 에 KOSPI 120행·VIX 48행이 실제로 기록됐다(`created_at=2026-09-10T12:26:12Z`). 값은 실제 시장 데이터이고 **OCI 는 무관**하다. 사용자·검증자 판단으로 **되돌리지 않고 유지**했다 — 정확한 백업이 없어 임의 복원이 더 위험하다 |
| 3 | **`BaseException` 삼킴** — 테스트를 통과시키려다 종료 신호까지 benchmark 실패로 바꿨다 |
| 4 | **MANIFEST 에 없는 스크립트 8개 기재** — 실제 2개로 교체하고 존재 여부를 검사에 넣었다 |
| 5 | **보고에서 untracked 1건 누락** |
| 6 | **fail-closed 가 코드에 연결되지 않음** — `check_coverage()` 가 판정값을 반환하지 않아 coverage 0% 에도 exit 0 이었고, API–CSV 지수명 불일치를 **출력만** 하고 그룹은 CSV 전체로 만들었다. 계약이 문서에만 있고 실행되지 않았다 |
| 7 | **결과서 sha256 오기** — snapshot hash 를 **손으로 옮겨 적어** 실제와 달랐다. 이제 MANIFEST 에서 **생성**한다 |
| 8 | **shuffle 범위 오기** — 구 스크래치 실행값(54.3~55.8%)을 적었다. 실제 재현값은 **52.97 / 55.39 / 56.10%** |
| 9 | **`reproduce.py` 가 tracked JSON 을 덮음** — "읽기 전용" 주장과 어긋났다. `--write` 옵션으로 분리했다 |

### 9.3 개발자 판단 (설계자 확정 아님)

| # | 항목 |
|---|---|
| 1 | **`spike_freshness` fail-closed 부수 영향** — benchmark 실패 시 spike 가 막힌다. cron 미연결이라 운영 영향이 없다고 판단했다 |
| 2 | **라이브 DB 행 유지** — 되돌리지 않는 쪽을 택했다 |
| 3 | **snapshot 범위** — `INDEX_LEADERSHIP` 재현용 ETF 종가를 `n≥2` 대상 196 ticker × 41 거래일로 한정했다. 전체를 넣으면 저장소가 과도해진다 |

---

## 10) 사용자 확인이 필요한 항목

| # | 항목 |
|---|---|
| 1 | 로컬 Mac DB 의 KOSPI 120행·VIX 48행 — **유지로 결정**됨. 재확인만 |
| 2 | 08:00 autosend 는 **`false` 유지**. 활성화는 `02B-2` 목업·사용자 확인 이후 |
| 3 | OCI 배포 **미수행**. 배포 시점은 `02B-2` 이후 |

---

## 11) 검증 실행 결과 (실측)

| 항목 | 결과 |
|---|---|
| `black --check app scripts tests` | `313 files would be left unchanged` |
| `flake8 app scripts tests` | exit 0 |
| `pytest tests/test_market_benchmark_freshness.py` | **24 passed** |
| `pytest tests/test_ops02b1_gate_reproduce.py` | **15 passed** (Gate 계약 test, r3 신규) |
| **전체 회귀** `pytest tests/` | **1,461 passed / 0 failed** (140.10s) |
| `reproduce.py` | exit 0 · 입력 7종 sha256 일치 · 스크립트 2개 존재 |
| 커밋 | `48babf04` · 22 files · +22,269 / −44 |
| `git status --short --untracked-files=all` | **출력 없음** (clean) |
| 실제 Telegram 발송 | **0건** |
| OCI 변경 | **0건** |
