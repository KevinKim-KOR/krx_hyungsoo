# POC4-02A — KRX PIT universe 생존편향 측정 PLAN V1

```text
POC4_SEQUENCE_REVISION       = POC4_SEQUENCE_V2 반영 (설계서 docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md
                               · Master Plan §11 표 교체)
POC4_02A_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS (설계자 판정 2026-09-25 · 확정 11건 §6 · 계약 §3·§4)
POC4_02B_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS (docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md §8)
PLAN_RESUBMISSION_REQUIRED = NO · IMPLEMENTATION = AUTHORIZED_AFTER_DOCUMENT_SYNC (동기화 2026-09-25 완료) · COMMIT_PUSH = 0
PRIMARY_PRICE_BASIS        = KRX_BASEPRICE_CHAIN (판정 §2 — 아래 사실조사 수치는 무조정 종가 기준으로 잰 PLAN 시점 값)

02A:
  SEALED_SOURCE_VERIFIED       = YES  krx_etf_universe_v1 SEALED · content_sha256 재계산 일치 · payload hash 불일치 0 · quick_check ok
  FEATURE_7_FEASIBILITY        = YES  7개 모두 KRX_BASEPRICE_CHAIN(TDD_CLSPRC·CMPPREVDD_PRC · FLUC_RT 검증)과 같은 version 069500
                                    연결 계열만 쓴다 — NAV·etf_master 불필요 (거래량은 진입·청산 label 에만 · 판정 §2)
  LABEL_20D_FEASIBILITY        = YES  학습 target(t→t+20)·평가 label(E2 forward_excess) 모두 연결 계열로 계산 · 폐지 ETF 는 청산일 행 없음
                                    NO_FORWARD_EXIT_PRICE · 이어 붙인 거래량 0 마지막 행 ZERO_VOLUME_EXIT (§3)
  CONTROL_UNIVERSE             = 2026-09-21 KRX 상장 1,171개(벤치마크 제외 후보 1,170) · etf_master(1,183 · 폐지 12개 잔존) 아님
  PIT_UNIVERSE                 = 날짜별 KRX 실재 ETF · 기간 중 1,419개 · 최종일에 없는 248개가 표본에 들어간다
  COMMON_EVALUATION_DATES      = 기존 E2 146개(2014-06-30 ~ 2026-07-31) 고정 (확정 A6) — 두 arm 모두 146개 전부 평가 가능
  HISTORICAL_FILTER_FEASIBILITY = YES  현 필터는 이름 키워드만 쓴다 → 날짜별 ISU_NM 으로 재현 · HISTORICAL_FILTER_UNAVAILABLE = 0
  EXPECTED_STORAGE / RUNTIME   = 일부 추정 — 결과 약 2 MB/실행(추정) · 파생 DB 불필요(선택 시 41~136 MB 실측) · 1회 약 25~35분
                                 (유휴 기준 약 25분 · 기계 부하 시 더 걸림 · 재현 단계 실측 + 나머지 추정) · 결정성 2회 약 50~70분 ·
                                 최대 메모리 약 2.2 GB 실측 (§2-12)

COMMON:
  KS10_TRIGGER / NEAR          = TRIGGER 0 · NEAR 7 (§2-14) · 기능 추가 금지 파일 2개는 건드리지 않는다
  EXTERNAL_CALLS = 0 · NEW_DEPENDENCY = 0 · OCI_PUSH_CHANGE = 0 · IMPLEMENTATION = AUTHORIZED (문서 동기화 뒤 · 공용 reader 먼저)
  설계 §13 금지 범위           = 위 항목 외에 화면·API 추가 0 · PARAM 승격 0 · 자동 튜닝 0 · RF·XGBoost·LightGBM 0
                                 (E2 모델 클래스·lr·epoch·seed 그대로)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성일**: 2026-09-24
- **입력**: 설계서 `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md` Part A·C (§1~§6 · §12~§15 · §19~§21)
- **짝 PLAN**: `docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md` — 봉인 source 공통 사실(§1)은 이 문서에만 적고 02B 는 참조한다.
- **조사 방법**: 에이전트 4개가 항목별로 실측하고, 조사마다 다른 에이전트가 숫자를 처음부터 다시 쟀다. 틀린 값은 재측정값으로
  고쳐 적었다. 봉인 DB·스냅샷 DB 는 `file:<경로>?mode=ro&immutable=1`, 라이브 시장 DB 는 `mode=ro` 로만 열었다.
  조사 전후 sha256 동일: 봉인 `fe3022e9…` · 스냅샷 `6fbde434…` · 라이브 `db0b2e9c…`. 저장소·state 쓰기 0. 측정 스크립트·로그는
  로컬 임시 폴더 `/private/tmp/claude-501/poc4_02_survey/`·`poc4_02_factcheck/`(저장소 밖 · 보존 보장 없음)에 두었고 저장소에
  넣지 않았다(아래 수치는 그 실행 출력). 문서 완성 뒤 에이전트 6개가 숫자·코드 줄 번호·설계 항목 누락을 다시 대조했고,
  문제로 표시된 항목은 다른 에이전트가 처음부터 다시 재서 확인된 것만 고쳤다.

---

## 1. 공통 사실 — 봉인 source `krx_etf_universe_v1` (02B 도 이 절을 참조)

### 1-1. 테이블 · 컬럼 · PK (설계 §4-1)

```text
krx_download_batch   (batch_id PK)                              3 행
krx_download_plan    (batch_id, bas_dd) PK · state · response_id 3,338 행
krx_fetch_attempt    (attempt_id PK)                            3,339 행
krx_raw_response     (response_id PK) · bas_dd · payload(원문) · payload_sha256 · row_count · traded   3,338 행
krx_etf_daily_raw    (response_id, row_no) PK · bas_dd · isu_cd · row_json   1,729,129 행 · 색인 (bas_dd, isu_cd)
krx_dataset_version  (version_id PK) · status · content_sha256    2 행 (v1 SEALED · canary OPEN)
krx_dataset_member   (version_id, bas_dd) PK · response_id        3,138 행 (v1 3,122)
krx_refetch_conflict (version_id, bas_dd, new_response_id) PK     0 행
journal_mode = delete · -wal 없음
```

- 가격은 **타입 있는 컬럼이 없다** — `row_json`(KRX 응답 행 원문, 모든 값이 문자열)을 파싱해야 한다. 한 행의 키 19개:
  `ACC_TRDVAL ACC_TRDVOL BAS_DD CMPPREVDD_IDX CMPPREVDD_PRC FLUC_RT FLUC_RT_IDX IDX_IND_NM INVSTASST_NETASST_TOTAMT
  ISU_CD ISU_NM LIST_SHRS MKTCAP NAV OBJ_STKPRC_IDX TDD_CLSPRC TDD_HGPRC TDD_LWPRC TDD_OPNPRC` (v1 행 전부 같은 키 집합).
- `ISU_CD` 가 6자리 단축코드다(ISIN·`ISU_SRT_CD` 없음). 314개 코드는 `0000D0` 같은 영숫자 새 형식 — `etf_master` 와 같은 형식.
- **v1 행은 반드시 member 조인으로 고른다**: `krx_dataset_member m JOIN krx_etf_daily_raw d ON d.response_id = m.response_id
  WHERE m.version_id = 'krx_etf_universe_v1'` → 1,612,728 행. `bas_dd` 로만 고르면 1,622,473 행(+9,745 중복) — canary·재확인
  응답이 같은 날짜에 따로 있기 때문이다(여러 응답이 있는 날짜 전체 18개 중 v1 날짜 16개 · 추가 응답 17개 · payload hash 는 같음).

### 1-2. 봉인·무결성 (설계 §3 · §15)

- v1: `SEALED` · 2026-09-23 · member 3,122 날짜(20140102~20260921 · 전부 FULL-20260923 · TRADED) · `content_sha256
  c1a877762b9b1f296365801030641c86bc4508f4c2643f1a6793e39119f9bb4c` — member 로 다시 계산하면 일치 · payload hash 재검증
  불일치 0 · `row_count = len(OutBlock_1)` 전부 일치 · 재수집 충돌 0.
- 비용(실측): 파일 sha256 약 1초 · seal 재계산 약 1초 · `quick_check` 0.75초 · `integrity_check` 1.7초 → 실행 전후 각 약 4.4초.
- 주의: 기존 `app/ml_research_krx_universe.connect()` 는 폴더 생성·읽기쓰기 연결·`CREATE TABLE` 을 하므로 **봉인 DB 를 읽는 데 쓰면
  안 된다**. 읽기 전용 reader 가 새로 필요하다(§5).

### 1-3. 날짜 · 휴장

- v1 날짜 3,122개 = 069500 유효 종가 날짜(빠진 날 0). 스냅샷 069500 날짜는 전부 KRX 에 있고, 2014-04-09 이후 KRX 날짜도 전부 스냅샷에 있다.
- FULL 계획은 평일만(3,318개 = 계산한 평일 목록 그대로 · 주말 0). NON_TRADING 196일 = 전부 평일 휴장. 휴장일에도 KRX 는
  상장 ETF 전부에 행을 주지만 가격·거래량·NAV 가 모두 빈 문자열이다. 휴장 응답은 v1 member 가 아니다(계획 표·원응답에만 있다).
- 주말도 행을 준다(canary 20260919 토요일 1,171행) — `krx_sync.has_traded_prices` docstring 의 "주말은 행이 없다" 와 다르다(운영 코드 무변경).

### 1-4. 종가 품질

```text
v1 TRADED 행 1,612,728   TDD_CLSPRC 양수·숫자 100% (빈 값 0 · 0 · 비숫자 0)
거래량 0 인 행           34,883 (2.16% · 507개 ETF) — 종가는 있으나 체결가가 아니라 KRX 기준가
                         직전 종가와 같은 경우 31% · 나머지는 그날 NAV 근처(|종가/NAV−1| 중앙값 0.09%)
                         연도별 비중 2014 6.2% → 2026 0.5% · 50% 이상이 거래량 0 인 코드 12개 · 한 번도 없는 코드 912개
폐지 248개의 마지막 행   248개 전부 거래량 0 · 222개는 마지막 체결 종가를 그대로 이어 붙인 값
최종 생존자 중 끝이 거래량 0   7개 — 265690 ACE 러시아MSCI(합성) 1,113행(2022-03-04 이후 체결 없음) · 0191M0 8 · 0191W0 5 ·
                         0052T0 2 · 0113P0 2 · 267450 2 · 472920 1
|일간 수익률| > 40%       35행(32개 코드) — 상장주식수 급변 없음(분할 흔적 없음) · 대부분 2026-07-31 레버리지·인버스
```

- **분배금**: KRX 종가는 무조정이라 분배락일에 가격이 떨어진다. 069500 은 `TDD_CLSPRC[t] − TDD_CLSPRC[t−1] ≠ CMPPREVDD_PRC`
  인 날이 42일 — KRX 가 그날 기준가를 분배금만큼 내렸다(4월 0.9~1.8%(2014~2025) · 2026년 4월 0.44% · 그 밖 분기
  0.02~0.40%(2026년 1·7월 포함)). 같은 source 의
  `CMPPREVDD_PRC` 로 분배 중립 연결 계열을 만들 수 있다(다른 source 불필요).
- 참고(비교용 스냅샷): 운영 `etf_daily_price` 는 분배 조정된 값이다(069500 스냅샷/KRX 비율 2014-04-09 0.7931 → 2026-01-29 부터
  1.0 · FinanceDataReader 구간도 분배 조정 — 2026-04-20~04-28 0.9936 · 04-29~07-29 0.9980 · 그 밖 1.0 · 전체 겹치는 1,405,329행 중
  76.1% 가 다름). 그런데 E2 의 `PRICE_BASIS_LABEL` 은 "분배금 미반영" 이라고 적혀 있다 — 설계자 참고용 관찰(§6 끝 '설계자 참고 관찰').

### 1-5. 069500 (설계 §4-6)

3,122일 전부 있음(2014-01-02 종가 25,910 ~ 2026-09-21 111,700) · 빠진 날 0 · 빈 종가 0 · 0 종가 0 · 거래량 0 인 날 0 ·
이름 항상 `KODEX 200` · 기초지수 항상 `코스피 200` · 상장주식수 급변 없음. 가장 큰 일간 변동 +24.17%(2026-07-31) ·
−12.46%(2026-03-04) — 종가 변동은 `FLUC_RT`·`CMPPREVDD_PRC` 와 맞지만 NAV(+19.97%)·지수(+19.98%)와는 다르다
(2026-07-31 NAV 대비 +3.48% 할증 마감). 값은 있는 그대로 쓴다.

### 1-6. ticker 재사용 흔적 (설계 §4-10)

- 코드 1,419개 모두 **첫 날부터 마지막 날까지 빠진 날이 없다**(내부 공백 0) — 사라졌다 다시 나타난 코드 0.
- 같은 이름이 다른 코드로 나온 경우 0.
- 이름 변경: 1,419개 중 539개가 이름이 1번 이상 바뀜(변경 724건 · 331건은 브랜드만 — KINDEX→ACE · KBSTAR→RISE ·
  ARIRANG→PLUS 등 · 2024년 253건 · 2025년 130건). 기초지수명이 바뀐 코드 38개.
- 빈 날 없이 같은 코드에 다른 상품이 들어왔는지(이름·기초지수 변경 760건): 변경일 NAV 가 20% 넘게 뛰거나 상장주식수가
  0.2배 미만·5배 초과로 바뀐 경우 0건(NAV 변화 최대 16.2% · 99% 4.7% · 주식수 비율 0.478~1.543).
- 변경과 무관하게 하루 NAV 비율이 [0.6, 1.6] 밖인 날 10번: 265690 3번(러시아 · 2022-03-10 NAV 가 전날의 1.4%) ·
  261220 2020-04-22(WTI 원유) · 2026-07-31 단일종목 레버리지·인버스 6개.
- 한계: 2014-01-02 이전에 쓰였던 코드의 재사용은 v1 만으로 알 수 없다.

---

## 2. 02A 독립 사실조사 (설계 §4 항목 번호)

### 2-2. feature 7개 (항목 2)

`app/ml_relative_upside_features.py` — `FEATURE_COLUMNS` = `return_5d · return_10d · return_20d · excess_return_5d ·
excess_return_10d · excess_return_20d · drawdown_20d`.

```text
return_k        close[i] / close[i−k] − 1          k 는 그 ETF 의 유효 종가 행 위치(달력일 아님)
excess_return_k return_k − (069500 종가[date i] / 069500 종가[date i−k] − 1)   날짜는 ETF 자기 행의 날짜
drawdown_20d    close[i] / max(close[i−19..i]) − 1
필요 입력       ETF 종가 · 날짜 · 같은 날짜의 069500 종가 — 거래량·NAV·시가총액·OHLC·etf_master 필드 없음
첫 행           i = 20 → 유효 종가 21개 필요
```

KRX 대응: 종가 → `TDD_CLSPRC` · 날짜 → `BAS_DD`(YYYYMMDD → YYYY-MM-DD 변환) · 종목 → `ISU_CD` · 벤치마크 → 같은 version 의
069500 행. ETF↔069500 날짜 조회(t−5/10/20 · t+20)는 항상 풀린다 → `BENCHMARK_UNAVAILABLE = 0`. **FEATURE_7_FEASIBILITY = YES**.

### 2-3. label (항목 3)

```text
(a) 학습 target future_excess_return_20d   진입 = t 행 종가 · 청산 = 20행 뒤 종가 − 같은 두 날짜 069500 수익률
                                          i+20 < n 일 때만 · 학습 이력은 t 로 잘려 모든 target 이 t 이전에 끝난다
(b) E2 평가 label forward_excess            진입 = 월말 t 다음 거래일 · 청산 = 다음 월말의 다음 거래일 (069500 유효일 기준)
                                          ETF·069500 둘 다 두 날짜에 양수 종가 · 보간 없음 · KRX 에서 보유 16~23 거래일
```

두 label 모두 KRX 종가만으로 계산된다. 폐지 ETF 는 청산일 가격이 없으면 None — 마지막 가격을 청산가로 쓰지 않는다.
**LABEL_20D_FEASIBILITY = YES**. 확정(A1): 학습 target 은 (a) · 평가 label 은 (b).

### 2-model. 모델 · 일정 · 비용 (현 E2 recipe)

- `nn.Linear(7,1)` · MSE · Adam lr 1e-3 · 전체 배치 200 epoch · float32 · `torch.manual_seed(42)` · 실행 기록 device = cpu.
- 분할: 완전한 행을 (날짜, 종목) 순으로 정렬해 앞 80% 학습 · 뒤 20% 는 test loss 에만. **별도 purge·embargo 없음** —
  purge·embargo 20일은 `app/ml_research_split.py` 에만 있고 E2 경로는 쓰지 않는다(테스트만 import).
- 신호일 = 매월 마지막 069500 유효일 · 각 신호일에 t 까지 잘린 이력으로 다시 학습 · 추론은 종목별 t 이하 마지막 완전 행.
- 비용: 현 E2 는 비용 틀이 두 개다(둘 다 월별 실측 교체비율 × 편도bp × 2). ① top-decile net·A2 판정: 편도 0/10/25/50bp · 판정
  기본 25bp(`app/ml_score_validity_eval.py:57-58` COST_BPS_GRID·PRIMARY_COST_BP). ② 전략 성과(`build_strategy_performance` —
  CAGR·MDD·변동성·Sharpe_0rf·상대 wealth·IR·월평균 active): 거래세 0 · 수수료 1.5bp · 슬리피지 5/10/25/50bp(기본 10 → 편도 11.5bp) ·
  legacy all-in 25bp 비교 시나리오(`app/ml_strategy_performance.py:37-42`).

### 2-4·5. universe 크기 (항목 4 · 5)

```text
기간 중 코드         1,419  · 최종일(2026-09-21) 상장 1,171 · 최종일에 없음(폐지) 248 · 첫날 146개 중 최종 생존 100
연도별 날짜 수·universe(min/median/max)
  2014 245 146/161/172   2017 243 256/283/325   2020 248 444/451/471   2023 245 666/733/812   2026 177 1058/1107/1171
  2015 248 166/176/201   2018 244 325/372/415   2021 248 467/484/533   2024 244 812/872/935
  2016 246 198/220/256   2019 246 413/431/450   2022 246 533/590/666   2025 242 935/991/1058
연말 PIT / CONTROL / 이후 폐지   2014-12-30 172/118/54 · 2016-12-29 256/208/48 · 2018-12-28 413/318/95 · 2020-12-30 468/391/77 ·
                                 2022-12-29 666/576/90 · 2024-12-30 935/867/68 · 2025-12-30 1058/1035/23 · 2026-09-21 1171/1171/0
행 수(코드×날짜)     PIT 1,612,728 · CONTROL 1,403,129
폐지 연도(마지막 날짜 기준) 2015 19 · 2016 8 · 2017 5 · 2018 7 · 2019 11 · 2020 29 · 2021 25 · 2022 6 · 2023 14 · 2024 51 · 2025 50 · 2026 23
```

**CONTROL 은 KRX 최종일 행으로 정의해야 한다** — 스냅샷 `etf_master`(1,183)에는 KRX 최종일 1,171개 전부 + 2026-06-24~09-14 에
KRX 에서 사라진 12개가 남아 있다(예: 301410 · 465780). 현 기준선 E2(run5 · 146 신호일)는 이 중 8개를 KRX 마지막 행 뒤 신호일에
옛 행으로 점수 매겼다 — 2026-06-30 3개(301410 · 422260 · 461270) · 2026-07-31 8개(+0021C0 · 0021D0 · 0021E0 · 424460 · 483420).
진입일 가격이 없어 평가 표본에는 들어가지 않았다. 나머지 4개(0036D0 · 397420 · 489010 · 465780)는 마지막 신호일 뒤에 사라졌다.

### 2-7·8. warm-up 부족 · 청산가 부족 (항목 7 · 8)

E2 146개 신호일 기준(069500 제외 · 후보 쌍 76,668):

```text
INSUFFICIENT_WARMUP (t 까지 유효 종가 21개 미만)   PIT 1,240쌍 · 1,215개 ETF · 전부 신규 상장 (CONTROL 1,036쌍 · 1,016개 ETF)
  연도별 2014 18 · 2015 43 · 2016 59 · 2017 73 · 2018 97 · 2019 51 · 2020 49 · 2021 94 · 2022 138 · 2023 157 · 2024 173 · 2025 172 · 2026 116
NO_FORWARD_EXIT_PRICE (E2 1M 규칙)                 층마다 수가 다르다 — 결과표는 층을 함께 적는다
  t 상장 · warm-up 통과 (필터 전)                 247쌍 · 247개 ETF · 전부 최종일에 없는 ETF · 폐지 ETF 마다 마지막 월말 1쌍
    연도별 2015 19 · 2016 8 · 2017 5 · 2018 7 · 2019 11 · 2020 29 · 2021 25 · 2022 6 · 2023 14 · 2024 55 · 2025 46 · 2026 22
  + 이름 필터(t 시점 이름)                       193쌍 · 193개 ETF (최종 이름으로 필터해도 193)
    연도별 2015 19 · 2016 6 · 2017 4 · 2018 6 · 2019 7 · 2020 21 · 2021 13 · 2022 4 · 2023 12 · 2024 46 · 2025 38 · 2026 17
  (학습 target 규칙 t→t+20 은 필터 전 247쌍 · 246개 ETF) · 최종 생존 ETF 는 0
  참고: 행 단위로 세면(모든 날짜 중 최종일−20 이전 행) 4,943행 · 248개 — 신호일 쌍 수가 아니다
최종일에 없는 ETF 가 PIT 표본에 들어오는 수          248개 전부 · 9,531쌍 (이름 필터 뒤 195개 · 7,202쌍)
평가 표본(warm-up·label 통과)                     PIT 75,181 · CONTROL 65,650 (+14.5%) · 이름 필터 뒤 55,133 · 47,931
날짜별 후보 수 (t 상장 · 069500 제외 · 필터 전)   PIT 160~1,154 (중앙 449.5) · CONTROL 110~1,150 (중앙 356.5)
날짜별 평가 표본 (warm-up·label·필터 통과)       최소 PIT 118 · CONTROL 79 (§2-11)
```

### 2-9. 상품 유형 — KRX 필드만으로 (항목 9)

- 현 파이프라인의 필터는 **이름 키워드뿐**이다 — `classify_etf_tags(etf_master.name)` 로 인버스·레버리지(2X·2배)·합성·선물을
  평가 분모·주 지표에서 뺀다(학습·추론은 전 종목). `etf_master` 의 다른 필드(category·시가총액·거래량·상장일)는 안 쓴다.
- KRX `ISU_NM` 이 모든 행에 날짜별로 있다(빈 값 0) → **날짜별 이름으로 같은 필터 재현 가능 · HISTORICAL_FILTER_UNAVAILABLE = 0**.
  최종 생존 1,171개는 KRX 최종일 이름 = 스냅샷 `etf_master` 이름(1,171/1,171 · 태그 집합도 같음). 폐지 248개 중
  `etf_master` 에 있는 것은 12개뿐이라 현 파이프라인은 나머지를 필터할 수 없었다 — KRX 로는 된다.
- 이름 변경으로 태그가 바뀌는 코드 6개 중 필터 판정(t 시점 이름 대 최종 이름)이 달라지는 것은 2개(310080 31쌍 · 253990 7쌍 = 38쌍 /
  E2 146일 후보 76,668쌍 · warm-up 통과 층에서는 36쌍).
- `IDX_IND_NM`(기초지수명)은 레버리지·인버스를 표시하지 않는다(예: 122630 KODEX 레버리지 → 코스피 200). 유형 전용 필드 없음.
- **"현재 etf_master 가 필요하면 중단" 조건: 해당 없음.**

### 2-11. CONTROL·PIT 공통 평가일 (항목 11)

- 현 E2 달력: 069500 유효일에서 월말 t · 진입 t+1 · 다음 월말 · 청산. 끝에서 진입·청산일이 없으면 빠진다. 표본이 작다고 날짜를
  빼는 규칙은 없다(coverage 0.70 미만이면 날짜를 빼는 대신 실행 전체를 `BLOCKED_COVERAGE`).
- KRX 달력은 151개(2014-01-29 ~ 2026-07-31). **기준선 146개가 전부 들어 있고 (t · 진입 · 다음 월말 · 청산)이 146/146 같다.**
  KRX 에만 있는 앞쪽 5개 중 2014-04-30·05-30 은 warm-up 상수, 2014-01-29·02-28·03-31 은 현 코드가 EVALUATION 으로 분류해
  `assert_evaluation_window` 가 실패한다 → 146개 고정(확정 A6).
- 146개 날짜 모두 두 arm 에 평가 표본이 있다(이름 필터 후 최소 PIT 118 · CONTROL 79 — CONTROL 79 는 기준선 run5 2014-06-30
  분모와 같다). 최소 학습 행(PLAN 조사 · 행 80% 분할 기준) PIT 9,496 · CONTROL 6,515 — 확정 A2 날짜 분할의 실제 값은 결과서
  §4-4(PIT 6,405 · CONTROL 4,381). → **COMMON_EVALUATION_DATES = 146 전부**.
- 주의: 2014-06-30 ~ 2015-01-30 의 8개 날짜는 CONTROL/PIT 후보 비율이 0.70 미만이다. CONTROL coverage 를 PIT 분모로 재면 기존
  preflight 가 CONTROL 실행 전체를 막는다 → arm 마다 자기 분모(확정 A7).

### 2-12. 파생 dataset · 실행시간 (항목 12)

```text
파싱          v1 전체 payload 파싱 7.2초 · row_json 파싱 8.0초 (1,612,728행)
파생 DB(선택) 좁은 sqlite(종목·날짜·종가) 40.9 MB · 13.5초 / 넓은 것(OHLC·거래량·NAV·이름) 136.4 MB · 17.6초
              parquet 불가(pyarrow 등 없음 · 신규 의존성 금지) · 전체 feature 패널을 미리 만들 필요 없음(E2 는 날짜마다 다시 계산)
E2 루프 실측   기존 reproduce 단계 146일: PIT 755초 · CONTROL 609초 · 스냅샷 611초(run5 날짜별 학습 행·점수 수 146/146 일치)
              비용은 잘린 이력 행 수에 비례(행당 약 9µs · 누적 PIT 82.3M · CONTROL 67.1M · 스냅샷 66.4M)
              15개 날짜 표본으로 다시 재면 PIT 약 798초 · CONTROL 약 647초(외삽)
              다른 작업과 CPU 를 나눠 쓴 상태(load 1.6~3.4)에서 다시 재면 PIT 1,002초 · CONTROL 803초 · 스냅샷 637초 —
              같은 루프가 기계 부하에 따라 25~33% 달라진다
예상(추정)    1회 약 25~35분(유휴 기준 PIT 약 13 + CONTROL 약 10.5 + 읽기·검증·집계 · 부하 시 두 arm 루프만 약 30분) ·
              결정성 2회 약 50~70분
메모리(실측)  PIT 146일 → CONTROL 146일을 한 프로세스로 돌리면 최대 RSS 약 2.2 GB(ru_maxrss 2.17 GB · 날짜가 뒤로 갈수록
              커지고 CONTROL 에서는 더 늘지 않음) · 날짜 사이 RSS 중앙 약 0.9 GB · 기기 메모리 16 GB
결과(추정)    arm 당 약 1 MB JSON + 제외 사유 표 → 약 2 MB/실행
측정 안 한 것 run5 의 나머지 약 330초(읽기·E1·U2·집계)는 나눠 재지 않았다 · 날짜 기준 분할 + purge(A2)의
              실행시간은 재지 않았다 · KRX 에서 두 번 실행한 점수가 같은지(결정성)는 아직 증거가 없다 — 구현 뒤 확인한다
```

### 2-13. 재사용 · 신규 모듈 (항목 13)

**그대로 재사용(수정 없음)** — DB·파일 접근 없는 함수라 입력만 KRX 로 바꾸면 된다:
`app/ml_relative_upside_features.py` · `app/ml_score_validity_eval.py` 의
`trading_days · build_calendar · truncate_history · build_close_maps · forward_excess · is_filter_universe ·
classify_phase · assert_evaluation_window` · `app/ml_score_validity_metrics.py`(spearman · 블록 부트스트랩 CI 계약: 6개월 블록 ·
2,000회 · seed 42 · 2.5/97.5% · win_rate · replaced_fraction · cost_drag) · `app/ml_strategy_performance.build_strategy_performance`
(069500 종가 맵만 KRX 로) · `app/market_topn_helpers.classify_etf_tags` · `app/ml_baseline_provenance`(code_provenance · git_state ·
environment · file_hashes) · `app/ml_baseline_snapshot.guard_sqlite_paths · new_run_dir`(새 실행에만 — 재개 경로는 러너의 별도 검사 · §8).

**파일은 고치지 않지만 부르는 방식이 정해져야 하는 것** — `app/ml_relative_upside_model.py`(고정 모듈)의 `train_walk_forward` 는
날짜 인자가 없다. 받은 행을 (날짜, 종목) 순으로 정렬한 뒤 **행 수 비율**로 다시 나눈다(:156-161 · split_idx = max(1, int(n×ratio)),
최대 n−1). 날짜 기준 분할(A2)을 이 함수로 통과시키려면 02A 루프가 ① 학습일 행 + 검증일 행만 넘기고(purge 된 날 제외)
② `train_split_ratio = (학습 행 수 + 0.5) / 넘긴 행 수` 를 arm·신호일마다 계산해 넘기며 ③ 매 호출 `train_row_count == 학습 행 수` ·
학습 마지막 날 < 검증 시작일을 assert 해야 한다(비율을 k/n 으로 주면 부동소수 오차로 약 4% 에서 1행 어긋난다). 이는 기준선 고정값
`train_split_ratio = 0.8`(`app/ml_baseline_provenance.py:205` 에 기록)을 바꾸는 것이다. 검증 구간 뒤 표본을 학습에 쓰는 embargo
(blocked) 분할은 이 함수로 표현할 수 없다. 이 함수는 torch 전역 seed 를 설정하고 환경변수·CUDA 로 device 를 고른다.

**그대로는 못 쓰는 것**

```text
load_prices(ml_score_validity_eval) → list_etf_tickers · fetch_price_history(market_data_store)
                                                      읽기쓰기 연결 + CREATE TABLE — 봉인 DB 에 쓰게 된다
ml_research_krx_universe.connect                      같은 이유
build_tag_map                                         현재 etf_master 이름을 읽는다
reproduce_scores_at                                   t 에 행이 없는 폐지 ETF 도 마지막 완전 행으로 점수 매긴다(PIT 2026-07-31 244개)
is_pit_eligible                                       코드는 수정 없이 부르되, t 상장 여부를 보지 않아(21개 관측 + 첫 종가 후
                                                      20거래일만 확인) 폐지 ETF 가 분모에 들어간다 → 02A 루프에서 t 행 존재
                                                      확인으로 감싼다(KRX 2026-07-31: True 1,382 중 244 가 t 행 없음)
build_frozen_descriptor · write_run_manifest          etf_daily_price·스냅샷 번들 전제
snapshot_session                                      1.86 GB 를 작업 폴더로 복사하는 구조 — KRX 에는 맞지 않는다
run_e1_gate · U2(compute_topn)                        운영 점수·etf_master 스키마 전제 — KRX arm 에 해당 없음
ml_score_validity_report.aggregate · verdict           626줄(NEAR · 기능 추가 금지) · A4(U2) 판정 포함
```

재사용할 때 반드시 막을 것 두 가지:

- `build_strategy_performance`(`app/ml_strategy_performance.py:207`)와 `app/ml_score_validity_report.py:485` 는
  `price_basis` 에 `PRICE_BASIS_LABEL = "price return (분배금 미반영, SOURCE_CLOSE)"`(`app/ml_score_validity_eval.py:59`)를
  박는다. 02A 결과에 그대로 두면 가격 기준이 잘못 적힌다 → 02A 보고 모듈이 `KRX_BASEPRICE_CHAIN` 으로 덮어 쓴다(원본 수정 없음).
- 위 표의 `reproduce_scores_at`·`is_pit_eligible` 문제(폐지 ETF 가 점수·분모에 들어감)는 t 상장 확인을
  `app/ml_score_validity_eval.py`(589줄 · NEAR 까지 11줄)에 넣지 않고 02A 새 모듈에서 감싸서 막는다.

**신규**(§5) — 봉인 reader · CONTROL/PIT universe + 제외 사유 · 02A 평가 루프 · 02A 지표·비교 · KRX run manifest · 러너.
어떤 운영 모듈도 고치지 않는다.

### 2-14. KS-10 전체 측정 (항목 14)

추적 중인 `.py/.ts/.tsx` 497개를 `wc -l` 로 쟀다(기준 `docs/KILL_SWITCHES.md` — 백엔드 650 · 근접 600 · 프론트 근접 850).
분류 기준: `app/`·`scripts/`·`legacy/` 를 백엔드로 셌다(NEAR 6개 중 2개가 scripts). `tests/_live_guard.py`(684)는 테스트
도우미로 보고 백엔드에 넣지 않았다 — 백엔드로 세면 650 을 넘는다. 확정(A10): 이 분류 그대로.

```text
TRIGGER   0
NEAR      7  frontend/app/components/JudgmentWorkbenchView.tsx 855 · scripts/run_three_push_runtime_oci.py 646 · app/api.py 641 ·
             scripts/ops02c/reverse_verify_guards.py 638 · app/ml_score_validity_report.py 626 · app/holdings_market_evidence.py 616 ·
             app/draft.py 602
바로 아래  scripts/run_ml_score_validity_eval_v1.py 599 · scripts/diagnose_nav_discount_source.py 594 · app/ml_score_validity_eval.py 589 ·
          scripts/refresh_market_timeseries.py 585
테스트    최대 tests/test_intraday_config_integration.py 1,423 (근접 1,450 미만) · tests/_live_guard.py 684(테스트 도우미)
관련      ml_research_krx_universe 532 · ml_baseline_snapshot 417 · ml_baseline_risk 390 · ml_baseline_provenance 277 ·
          ml_strategy_performance 257 · ml_research_split 149
```

설계 §14 의 두 파일(626 · 599)과 `app/ml_score_validity_eval.py`(589)에는 손대지 않는다.

---

## 3. 제외 사유 (확정 계약 · 설계 §5 + 설계자 판정 §2)

```text
사유                           판정 기준 (쌍 = 신호일 t × 종목)
NON_TRADING_DATE               달력 = v1 member 날짜(= 069500 유효일) — 구조상 0
NOT_YET_LISTED                 CONTROL 의 최종 생존자가 t 에 아직 행이 없음 (PIT 는 정의상 0)
NO_VALID_CLOSE                 TDD_CLSPRC 빈 값·비숫자 (조사 0)
NON_POSITIVE_CLOSE             TDD_CLSPRC ≤ 0 (조사 0)
BASEPRICE_RELATION_MISMATCH    previous_reference ≤ 0 이거나 |daily_return×100 − FLUC_RT| > 0.005%p 인 행이 feature 창(t−20..t)
                               또는 보유 구간(진입..청산)에 들어가는 쌍 — 보정하지 않고 제외 (조사: 불일치 0행 · 아래 §4)
INSUFFICIENT_WARMUP            t 까지 유효 행 21개 미만 (v1 은 종목 안에 빈 날이 없어 "첫 행 뒤 20거래일" 과 같다)
NO_ENTRY_PRICE                 진입일(t 다음 거래일)에 종목 행 없음 — 판정 목록에 없는 경우라 별도 사유로 센다
ZERO_VOLUME_ENTRY              진입일 행 ACC_TRDVOL = 0
NO_FORWARD_EXIT_PRICE          청산일(다음 월말의 다음 거래일)에 종목 행 없음
ZERO_VOLUME_EXIT               청산일 행 ACC_TRDVOL = 0 (폐지 ETF 의 이어 붙인 마지막 행이 여기에 걸린다)
BENCHMARK_UNAVAILABLE          069500 진입·청산일 행 없음 (조사 0)
HISTORICAL_FILTER_UNAVAILABLE  t 행 ISU_NM 빈 값 (조사 0)
```

- 판정 순서(코드와 같음): 상장(t 행) → t 행 이름(HISTORICAL_FILTER_UNAVAILABLE) → t 행 종가(NO_VALID_CLOSE · NON_POSITIVE_CLOSE) →
  warm-up → feature 창 관계 검증 → 모델 없음(NO_MODEL) · 점수 없음(BENCHMARK_UNAVAILABLE) → 진입 행 → 진입 거래량 → 청산 행 →
  청산 거래량 → 보유 구간 관계 검증 → 069500 진입·청산(BENCHMARK_UNAVAILABLE). 069500 이 t 에 없으면 universe 전부 BENCHMARK_UNAVAILABLE.
  한 쌍은 첫 사유 하나로만 센다. 다음 거래일로 미루거나 마지막 체결가를 청산가로 대체하지 않는다.
- 사유별 수는 arm · 필터 전/후로 따로 적는다. PLAN 조사 때의 수(§2-7·8)는 무조정 종가·거래량 무관 기준이라 확정 계약의 수는
  결과서에 새로 적는다.
- 공식 표현은 설계 §5 그대로 결과에 박는다: `universe_basis = KRX_POINT_IN_TIME_UNIVERSE_V1` · `survivorship_status =
  REDUCED_NOT_ELIMINATED` · `ceiling = RESEARCH_ONLY` · `UNBIASED_PERFORMANCE_CLAIM = NOT_YET`.

---

## 4. 확정 실험 계약 (설계자 판정 2026-09-25 A1~A11 · §2 · §3)

```text
SURVIVORSHIP_EFFECT = PIT − CONTROL   (같은 봉인 계열 · 같은 날짜 · 같은 recipe · universe 만 다르다)
PRIMARY_PRICE_BASIS = KRX_BASEPRICE_CHAIN
```

| 항목 | 두 arm 공통 (확정) |
|---|---|
| 가격 (판정 §2) | 종목마다 v1 행을 날짜 순으로 놓고 `r_i = CMPPREVDD_PRC / (TDD_CLSPRC − CMPPREVDD_PRC)` · 연결 계열 `C_0 = 첫 행 TDD_CLSPRC` · `C_i = C_{i−1} × (1 + r_i)`. 069500 도 같은 방식. feature · 학습 target · 평가 label · 벤치마크 모두 이 계열 (비율만 쓰므로 시작값은 결과에 영향 없음) |
| 관계 검증 | 모든 v1 행에서 `|r_i × 100 − FLUC_RT| ≤ 0.005%p (+부동소수 1e-9)` — `FLUC_RT` 가 소수 둘째 자리 반올림이라 그 절반 폭. 판정 뒤 조사: 1,612,728행 최대 차이 0.005000000000000782 → 불일치 0행. 넘는 행·무효 종가 행은 보정하지 않고 그 행의 `TDD_CLSPRC` 로 연결 계열의 새 구간을 시작한다 — 구간을 넘는 feature 창·보유 기간은 `BASEPRICE_RELATION_MISMATCH` (§3), 학습 이력은 마지막 구간만 쓴다 |
| 거래량 0 (판정 §2) | feature 계산: 그 행 사용 · `zero_volume=true` 기록 — 구현은 점수 쌍의 t 행이 거래량 0 인 수만 센다(feature 창 t−20..t−1 의 거래량 0 행은 세지 않는다 · 판정 문구보다 좁은 기록) / 주 성과 진입·청산: `ACC_TRDVOL > 0` 필수 |
| 민감도 | `OFFICIAL_REFERENCE_SENSITIVITY` — 같은 점수(재학습 없음)로 진입·청산에 거래량 0 행을 허용(행은 있어야 함). 주 판정·preflight 에 쓰지 않는 표 |
| feature · target (A1) | 7개 · `future_excess_return_20d` — 고정 모듈 `build_feature_rows_for_ticker` 에 (날짜, 연결값) 이력을 넣어 호출 |
| 모델 | 고정 trainer `train_walk_forward` · `nn.Linear(7,1)` · lr 1e-3 · 200 epoch · seed 42 · 이 기기는 CUDA 없음 → CPU |
| 분할 (A2 · (a)안) | 신호일 t 마다 달력 = v1 거래일 ≤ t · 표본일 = 달력 index ≥ 20 · `make_selection_folds(n_folds=1, validation_days = N − int(0.8N), horizon=20, walk-forward)` (N = label 완성 표본일 수) → 학습일·검증일·purge 일. 두 arm 이 같은 달력을 쓰므로 경계가 같다. trainer 에는 학습일 행 S + 검증일 행 V 만 넘기고 `train_split_ratio = (|S|+0.5)/(|S|+|V|)` · 매 호출 `train_row_count == |S|` · `train_date_range[1] < 검증 시작일` assert. 날짜별 경계·실제 학습 행 수·마지막 학습일을 결과·manifest 에 기록. 사후 embargo 는 walk-forward 라 구조적으로 해당 없음 |
| 평가일 (A6) | KRX 달력 `build_calendar(months_ahead=1)` 중 기준선 manifest(`state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json`, sha256 기록) 의 `e2_dates` 146개 · `assert_evaluation_window` |
| universe (A5) | PIT = t 에 v1 행이 있는 ETF(069500 제외) / CONTROL = PIT 중 2026-09-21 에도 v1 행이 있는 ETF |
| 학습 행 | arm 의 전 종목(PIT 1,418 · CONTROL 1,170) 이력을 t 로 자른 것 — E2 와 같이 학습은 필터 전 전 종목 |
| 점수 | t 에 행이 있고 **t 행**의 feature 가 완전한 종목만 (폐지 ETF 의 옛 행으로 점수 매기지 않는다 · 추론 asof = t) |
| 필터 (A4) | `classify_etf_tags(t 행 ISU_NM)` 의 inverse · leveraged · synthetic · futures 제외 — 평가 분모·주 지표에만 |
| 평가 label (A1) | `forward_excess` 와 같은 식(진입 t+1 → 다음 월말+1)을 연결 계열로 · ETF 진입·청산 행 `ACC_TRDVOL > 0` |
| coverage (A7) | 분모 = arm universe ∩ 필터 ∩ `is_pit_eligible` · 분자 = 분모 중 점수·주 label 이 있는 쌍. 0.70 미만 날짜가 있으면 그 arm `BLOCKED_COVERAGE`. 교차 coverage(CONTROL 분자 / PIT 분모)는 참고표 |
| 비용 (A11) | top-decile net: 편도 0/10/25/50bp · 기본 25bp / 전략 성과: 편도 11.5bp 기본(수수료 1.5 + 슬리피지 10) · 슬리피지 5/10/25/50 · legacy 25bp |
| 누수·통제 | L1(학습·추론 입력 > t) · L2(진입 ≤ t) · L3(target 끝 > t) 0건 · N-1 셔플 통제 — E2 와 같은 preflight. 막히면 그 arm 의 최종 지표를 내지 않는다 |
| 벤치마크 | 069500 같은 version 연결 계열 |

**산출** (설계 §6 · 두 arm 같은 지표 · 146일 공통 평가일): IC(필터 universe)와 블록 부트스트랩 95% CI · 분위 스프레드 ·
top-decile gross/net(0/10/25/50) · turnover · win rate · 연도별 IC · 전략 성과(CAGR · MDD · 변동성 · Sharpe_0rf · 상대 wealth ·
IR · 월평균 active — `price_basis` 는 `KRX_BASEPRICE_CHAIN` 으로 덮어 적는다) · 평가일·표본 수 · 제외 사유별 수 · 최종일에 없는
ETF 포함 수(점수·평가 쌍) · 점수 쌍 중 t 행 거래량 0 수 · 민감도 표.
**비교표**: 지표마다 `PIT − CONTROL`. 날짜별 값이 있는 IC · top-decile gross · net(25bp) 는 같은 날짜 쌍 차이의 평균과 블록
부트스트랩 95% CI. 전략 성과 지표는 차이만. coverage 표는 따로. 기존 `relative_upside_v1_snap_20260921` 과의 차이는 가격 source
도 달라 참고치로만 적는다.

**실행 규율**: 봉인 DB 는 `file:…?mode=ro&immutable=1` 로만 연다 · 실행 전후 파일 sha256 · seal 재계산 · payload hash ·
`quick_check` · `integrity_check` 가 같아야 결과를 쓴다 · 실행 중 `sqlite3.connect` 는 봉인 DB 경로만 허용(`guard_sqlite_paths`) ·
결과는 새 실행 폴더에만(재개 규칙은 §8 한 곳에만 적는다) · run manifest 에 source version · content hash · 날짜 범위 · 모듈
sha256 · git 상태(커밋 전 실행이면 `code_committed=false`) · 환경 · 인자 · 결과 canonical hash · 외부 호출 0.

---

## 5. 파일 계획 · 테스트

**신규 모듈**(각각 백엔드 600줄 미만 · 운영 모듈·고정 모듈·기준선 파일 수정 0)

```text
app/krx_sealed_reader.py         공용 봉인 reader (판정 §3) — 읽기 전용 연결 · 파일 sha256 · seal 재계산 · payload hash ·
                                 quick/integrity check · member 조인 · 종목별 행(날짜·종가·CMPPREVDD·FLUC_RT·거래량·NAV·이름)
                                 · 관계 검증 · 연결 계열. 02A·02B 는 수정 없이 import 만
app/ml_pit_universe.py           arm universe · t 상장 · 이름 필터 · warm-up · 진입·청산 판정 · 제외 사유
app/ml_pit_bias_eval.py          신호일 하나의 평가 — 절단 · feature(고정 모듈) · 날짜 분할(ml_research_split) · 고정 trainer 호출 ·
                                 점수 · 주 label · 민감도 label · 날짜별 기록
app/ml_pit_bias_report.py        arm 집계 · preflight · 전략 성과(가격 기준 덮어쓰기) · PIT − CONTROL 비교 · canonical hash
scripts/run_poc4_02a_pit_bias.py 러너 — 새 폴더 · 전후 검증 · progress/ · --resume · run manifest
```

**테스트**(설계 §15 · 모두 `tmp_path` 의 KRX 스키마 고정 DB — 봉인 DB 는 테스트 가드가 연결을 거부한다 · 새 테스트는 229건
허용 목록에 넣지 않는다)

```text
reader     읽기 전용 · 봉인 version·content hash·payload hash 불일치 시 실패 · OPEN version 거부 · member 조인만 · 쓰기 0 ·
           관계 검증 경계(0.005%p) · 연결 계열 = 공식 변동률 누적
universe   미래 상장 ETF 가 과거 universe 에 없음 · 폐지 ETF 가 실재일 PIT universe 에 있음 · CONTROL = 최종일 행
           · 날짜별 이름 필터 · 현재 etf_master 를 바꿔도 결과 불변(etf_master 를 읽지 않음)
사유       warm-up · 진입 행 없음 · 진입 거래량 0 · 청산 행 없음 · 청산 거래량 0 · 관계 불일치가 따로 세어짐 ·
           마지막 가격을 청산가로 쓰지 않음 · 폐지 ETF 의 옛 행으로 점수 매기지 않음 · 민감도는 거래량 0 허용
분할       두 arm 의 날짜 경계·purge 가 같음 · trainer 의 실제 학습 행 수·마지막 학습일이 경계와 같음 · 학습 target 끝 ≤ t
러너       새 결과 폴더만 · 이미 있는 폴더는 --resume 없이 실패 · --resume 은 지문이 같을 때만 남은 날짜를 잇고 기존 progress/
           레코드를 바꾸지 않음 · 지문이 다르면 멈춤 · 끊은 뒤 재개한 결과 = 끊지 않은 결과 · 같은 입력 두 번 실행 결과 동일
경계       운영 DB·etf_daily_price 접속 시 실패 · 벤치마크가 다른 source 면 실패 · 외부 네트워크 0 · 전체 회귀 통과 · 라이브 5경로 동일
```

---

## 6. 설계자 확정 11건 (2026-09-25) · 구현 정의

| # | 확정 | 이 PLAN 의 반영 위치 |
|---|---|---|
| A1 | 학습 target `future_excess_return_20d` · 평가 E2 `forward_excess` | §4 feature·평가 label |
| A2 | 날짜 기준 분할 + purge 20 · 기존 trainer 에 호출별 비율 (a)안 · 기준선 수정이 아닌 새 `POC4-02A` 연구 recipe | §4 분할 · §2-13 |
| A3 | 거래량 0 은 판정 §2 별도 계약 | §3 · §4 거래량 0 · 민감도 |
| A4 | 날짜별 `ISU_NM` | §4 필터 |
| A5 | CONTROL = KRX 최종일 1,171개 | §4 universe |
| A6 | 기존 E2 평가일 146개 고정 | §4 평가일 |
| A7 | 실행 차단 coverage 는 arm 별 자기 universe · 교차 coverage 는 참고표 | §4 coverage |
| A8 | 공용 봉인 reader 하나 · 02B 는 수정 없이 사용 · 변경 필요 시 공통 계약 변경으로 보고 | §5 · 구현 순서: reader + 고정 fixture 테스트 먼저 |
| A9 | V2 병렬 승인 · `PROJECT_ORIGIN_INTENT §9.5` 에 2026-09-25 예외 추가 | 반영 완료 |
| A10 | `scripts/` = backend 기준 · `tests/_live_guard.py` = test 기준 | §2-14 분류 그대로 |
| A11 | top-decile 기본 비용 편도 25bp 유지 · 전략 성과는 11.5bp 병기 | §4 비용 |

**구현 정의** — 설계자 판정이 정하지 않은 세부를 결과를 보기 전에 여기서 고정한다(결과를 본 뒤 바꾸지 않는다).

1. 관계 검증 허용 오차 0.005%p (+1e-9) — `FLUC_RT` 표기 정밀도의 절반. 첫 행(상장일)도 같은 규칙.
2. 진입일 행이 없는 쌍은 `NO_ENTRY_PRICE` 로 따로 센다(판정 목록에 없는 경우).
3. 분할의 검증일 수 = `N − int(0.8N)` (기존 80/20 비율을 날짜 수로 옮긴 값). 학습 행 또는 검증 행이 0 이면 그 날은 모델 없음으로
   기록하고 점수를 내지 않는다(146일 모두 학습 행이 있다 — §2-11).
4. 점수는 t 행 기준(추론 asof = t). t 행 feature 가 불완전하면 그 종목은 점수 없음.
5. 민감도 표는 주 표와 같은 점수·같은 필터·같은 분모를 쓰고, 진입·청산 거래량 조건만 뺀다.
6. 비교 CI 는 두 arm 모두 값이 있는 날짜만 쓴다(짝이 없는 날짜 수는 따로 적는다).
7. 판정: 02A 는 측정 단계다. arm 마다 preflight 통과 시 `MEASURED`, 아니면 막힌 사유(`BLOCKED_COVERAGE` 등). 두 arm 이 모두
   `MEASURED` 일 때만 `SURVIVORSHIP_EFFECT` 표를 낸다. 성과의 좋고 나쁨은 구현 성공 기준이 아니다(설계 §1).

설계자 참고 관찰(기록): 기준선 스냅샷 가격은 분배 조정값인데 E2 `PRICE_BASIS_LABEL` 은 "분배금 미반영" 이다 — 기준선과 참고
비교할 때 이 차이를 적는다.

---

## 7. 중단 조건 점검 (설계 §20 · 판정 반영 후)

```text
봉인 KRX 만으로 가격·label 생성 불가            아니다 — 연결 계열·label 전부 봉인 version 으로 계산
현재 etf_master·운영 가격 DB 필요                아니다
KODEX200 을 다른 source 에서                    아니다 — 3,122일 전부
추가 네트워크·신규 의존성                        아니다 — stdlib + 기존 torch·numpy
기존 기준선 수정                                아니다 — 판정 A2: 기존 불변 기준선이 아닌 새 POC4-02A 연구 recipe ·
                                               relative_upside_v1_snap_20260921 · 고정 모듈 파일 변경 0
KS-10 trigger                                  아니다 — 0 (신규 모듈은 각각 600줄 미만)
라이브 DB·상태 파일 변경                        아니다 — 봉인 DB 읽기 전용 · 결과는 새 폴더 · 라이브 5경로 전후 동일 확인
두 PLAN 이 같은 운영 모듈을 동시에 수정          아니다 — 운영 모듈 수정 0 · 공용 reader 는 판정 A8·§3 순서
```

## 8. 작업 리듬 · 재개 (설계 §21 · 판정 §12)

순서: 문서 동기화 → 공용 reader + 고정 fixture 테스트 → 02A 구현 · 테스트 → 전체 회귀 → 실행 1(처음부터) → 실행 2(처음부터 ·
결정성) → 결과서 `docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md`. 02B 장시간 실행과 동시에 돌리지 않는다.

**재개 가능 구조**: 새 실행은 `new_run_dir` 로 새 폴더를 만든다(이미 있으면 거부). 러너는 arm·신호일마다 결과 레코드를 실행 폴더
안 `progress/` 에 한 번씩만 쓴다(덮어쓰기 없음). 각 레코드와 run manifest 에 입력 지문(봉인 content·파일 hash · 모듈 정규화 AST
sha256 · 설정 hash · 평가일 목록 hash · 기준선 manifest hash)을 넣는다. 중간에 멈추면 `--resume <같은 폴더>` 로 다시 연다 — `new_run_dir` 를 거치지 않고, 지문이 전부
같을 때만 끝난 날짜를 건너뛰고 없는 날짜의 레코드만 새로 쓴다. 지문이 하나라도 다르면 이어 돌지 않고 멈춘다(새 폴더로 처음부터).
기존 레코드와 최종 결과 파일은 덮어쓰지 않는다. 최종 결과 파일은 146일 × 2 arm 이 모두 끝난 뒤 한 번 만든다. 결정성 확인은
재개 없이 처음부터 두 번 돈 결과로 한다.
