# POC4-02A — KRX PIT universe 생존편향 측정 RESULT

```text
STATUS               = MEASURED (PIT · CONTROL 둘 다 preflight OK · 누수 L1/L2/L3 0 · N-1 통제 통과)
SURVIVORSHIP_EFFECT  = PIT − CONTROL (같은 봉인 계열·날짜·recipe · universe 만 다름 · 146 평가일 모두 짝)
                       IC 평균 −0.0029 (95% CI −0.0120 ~ +0.0048) · top-decile gross −0.00092/월 (CI −0.00295 ~ +0.00044)
                       top-decile net@25bp −0.00092/월 (CI −0.00297 ~ +0.00044) · 전략 CAGR −1.05%p · 상대 wealth −0.046
                       → 평균 기준으로는 생존자만 본 CONTROL 이 약간 좋게 나오는 방향 · 날짜별로는 일관되지 않고(§5-2)
                         크기는 작으며 CI 가 0 을 포함한다
MODEL (참고)          = 두 arm 모두 IC 음수(PIT −0.032 · CONTROL −0.029) · net@25bp 음수 — 모델 개선 단계가 아니다(설계 §1) ·
                       생존편향 측정과 별개 기록이며 02A 에서 모델 최종 판정은 내리지 않는다(설계자 RESULT 판정 §4)
DESIGNER_RESULT      = MEASURED_ACCEPTED · MANIFEST_SPLIT = APPROVED (설계자 RESULT 판정 2026-09-25)
DETERMINISM          = 처음부터 두 번 실행 canonical 동일 1e9a88af… (compare determinism_confirmed = true)
PRICE_BASIS          = KRX_BASEPRICE_CHAIN (관계 불일치 0행) · 주 성과 진입·청산 ACC_TRDVOL > 0
OFFICIAL_LABELS      = KRX_POINT_IN_TIME_UNIVERSE_V1 · REDUCED_NOT_ELIMINATED · RESEARCH_ONLY · UNBIASED_PERFORMANCE_CLAIM = NOT_YET
SEALED_SOURCE        = krx_etf_universe_v1 SEALED · content c1a87776… · 실행 전후 동일 · 라이브 5경로 전후 동일
OCI · PUSH = 0 · EXTERNAL_CALLS = 0 · DEPENDENCY_ADDED = 0 · COMMIT · PUSH = 0 (설계자 판정 §13)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자(02B 판정 뒤) · 검증자(Codex, 설계자 통과 범위)
- **입력**: 설계서 `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md` 끝 `# 설계자 PLAN 판정`(2026-09-25) ·
  PLAN `docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md`(§3~§8 확정 계약 · 구현 정의)
- **짝 결과서**: `docs/ai_result/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md` — 문서 동기화(§1-1)·공용 reader(§1-2 · §4-1)·
  전체 회귀는 그 문서에 적었다.
- **실행 폴더**(git 추적 밖): `state/ml/research/poc4_02a/run1` · `run2` · `run2/determinism_compare.json`
- **코드 상태**: 커밋 전 코드로 실행(판정 §13) · manifest `code_clean=false` · HEAD `94cec4e2` · 모듈 hash 기록 · 실행 뒤 코드 변경 0(§4-8).

---

## 1) 처리한 요구사항

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| A1 | 학습 target `future_excess_return_20d` · 평가 E2 `forward_excess` | DONE | 고정 feature 함수 그대로 · label 은 같은 식을 연결 계열로(테스트로 `forward_excess` 와 같음 확인) |
| A2 | 날짜 기준 분할 + purge 20 · 기존 trainer 호출 (a)안 | DONE | 146일 모두 두 arm 분할 지문 같음 · trainer 학습 행 = |S| · 마지막 학습일 < 검증 시작(§4-4) |
| A3 | 거래량 0 계약(판정 §2) | DONE | feature 는 사용·기록 · 진입·청산 ACC_TRDVOL > 0 · 민감도 표 별도(§4-6) |
| A4 | 날짜별 `ISU_NM` 필터 | DONE | `classify_etf_tags(t 행 이름)` |
| A5 | CONTROL = KRX 최종일 1,171 (후보 1,170) | DONE | PIT 1,418 · CONTROL 1,170 종목 |
| A6 | E2 평가일 146개 고정 | DONE | 기준선 manifest(`dataset_manifest.json`, 파일 sha256 6b9c8938…)의 `e2_dates` 146개 · `assert_evaluation_window` |
| A7 | 실행 차단 coverage = arm 자기 universe · 교차 coverage 참고표 | DONE | 두 arm 최소 coverage 0.827 · 0.899 ≥ 0.70 · 교차는 최소 0.587(참고) |
| A8 | 공용 reader 하나 · 02B 는 수정 없이 사용 | DONE | 02B 결과서 §1-2 |
| A9 | `PROJECT_ORIGIN_INTENT §9.5` 예외 | DONE | 02B 결과서 §1-1 |
| A10 | `scripts/` = backend · `_live_guard.py` = test 기준 | DONE | 새 파일 최대 586줄(러너) < 600 |
| A11 | top-decile 기본 편도 25bp · 전략 성과 11.5bp 병기 | DONE | §4-5 |
| 판정 §2 | `KRX_BASEPRICE_CHAIN` · 관계 검증 · 불일치 행 제외 사유 | DONE | 불일치 0행 · `BASEPRICE_RELATION_MISMATCH` 0 |
| 판정 §2 | `OFFICIAL_REFERENCE_SENSITIVITY` (재학습 없음) | DONE | §4-6 |
| 판정 §12 | 02B 장시간 실행과 동시에 돌리지 않음 · 처음부터 두 번 | DONE | 02B 끝난 뒤 run1 → run2 · §4-7 |
| 설계 §5 | 제외 사유 따로 집계 · 마지막 가격을 청산가로 쓰지 않음 | DONE | §4-3 |
| 설계 §6 | 두 arm 같은 지표 · 공통 평가일 · coverage 표 | DONE | §4-5 · §4-2 |

## 2) 변경된 파일 목록

- `app/ml_pit_universe.py` (267) · `app/ml_pit_bias_eval.py` (389) · `app/ml_pit_bias_report.py` (535) ·
  `scripts/run_poc4_02a_pit_bias.py` (586): 신규
- `tests/test_poc4_02a_pit_bias.py` (408) · `tests/test_poc4_02a_pit_runner.py` (463): 신규
- `docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md`: 신규 (이 문서)
- 공용 reader · fixture · 문서 동기화 파일은 02B 결과서 §2.

전부 스테이징 상태(신규 `A`) · 커밋·push 없음(판정 §13) · git 상태 실측은 02B 결과서 §4-10. 운영 모듈·고정 모듈·기준선
(`relative_upside_v1_snap_20260921`) 수정 0.

## 3) 신규 추가된 의존성

없음 (stdlib + 기존 torch).

## 4) 지시문 외 변경

1. **사유 두 개 추가** — `NO_ENTRY_PRICE`(진입일 행 없음 · PLAN 구현 정의 2) · `NO_MODEL`(학습 행 부족 · 실제 0건).
2. **manifest 두 파일**(설계자 RESULT 판정 §5 승인) — 시작 `run_manifest.json`(재개 지문용 · 한 번만 씀) + 끝 `run_manifest_final.json`(날짜별 분할 경계 ·
   실제 학습 행 수 · 마지막 학습일 · 결과 canonical hash · 라이브 경로 전후). A2 "manifest 에 기록" 을 이 한 쌍으로 구현했다
   (검토 지적 반영).
3. **069500 이 t 에 없을 때** 는 universe 전부를 `BENCHMARK_UNAVAILABLE` 로 센다(실제 0건).
4. **turnover** 는 E2 코드와 같게 top-decile 이 없는 날 직전 바스켓을 빈 목록으로 둔다(실제 모든 날 표본 있음 → 영향 0).
5. 재개 안전장치 강화(검토 지적): 첫 시작 뒤 라이브 경로가 바뀌면 `guard_failed.json` 을 남기고 재개 거부 · 실행 폴더가 감시
   경로 아래면 거부 · compare 는 두 실행 모두 재개 없는 처음부터 실행일 때만 `determinism_confirmed`.

## 5) 알려진 한계 / 미완성

1. **생존편향은 줄였지 없앤 것이 아니다**(`REDUCED_NOT_ELIMINATED`) — 2014-01-02 이전에 폐지된 ETF 는 v1 에 없다.
2. **효과의 CI 가 0 을 포함한다** — IC · top-decile 모두. 평균 기준 지표(IC 평균 · top-decile gross/net · 승률 · 전략 CAGR · Sharpe ·
   상대 wealth)는 모두 CONTROL 이 좋게 나오는 방향이지만 날짜별로는 일관되지 않다 — PIT IC 가 낮은 날 68/146 · 높은 날 78/146 이고
   짝 IC 차이의 중앙값은 +0.0042(평균 −0.0029 와 반대 부호) · top-decile 은 PIT 가 낮은 날 75 · 높은 날 70 · 같은 날 1 · 연도별 IC
   차이는 13년 중 5년(2016·2017·2018·2024·2025)이 반대 방향이다. 크기는 통계적으로 구분되지 않는다.
3. **검증 구간 비율** — 날짜 기준 20% 를 검증으로 두면 최근 신규 상장이 많아 행 기준 검증 비율이 커진다(2026-07-31 38.5%).
   모델은 학습일 행(S)으로만 학습한다(A2 그대로).
4. **실행 비용** — 1회 약 24~27분(실행 기록 1,463~1,642초) · 최대 RSS 2.6~2.7 GB(PLAN §2-12 조사 실측 약 2.2 GB · ru_maxrss
   2.17 GB 보다 크다 · 16 GB 기기).
5. 기존 기준선(`relative_upside_v1_snap_20260921`)과의 차이는 가격 source · universe · 분할이 모두 달라 참고치다.
6. 결과·실행 폴더는 git 추적 밖이다. 결과서의 hash 로 대조한다.
7. **거래량 0 기록 범위** — 판정 §2 "feature 계산 … `zero_volume=true` 기록" 을 점수 쌍의 t 행이 거래량 0 인 수로만 기록했다
   (feature 창 t−20..t−1 의 거래량 0 행은 세지 않음 · PLAN §4 에 명시).

## 6) 다음 검증자(Codex)에게 알릴 점

- PLAN 조사 때(무조정 · 거래량 무관) 잰 사유 수와 확정 계약 수가 다르다: 청산 행 없음 247 → 206(필터 전) — 차이 41쌍(247쌍의 약
  17%)은 폐지 직전 쌍이 판정 순서상 앞의 `ZERO_VOLUME_ENTRY` 로 먼저 세어진 것이다(한 쌍 한 사유 · PLAN §3 순서 · 앞 순서의 다른
  사유는 warm-up 1,240 으로 PLAN 과 같고 나머지 0 · 이름 필터 뒤 193 → 166 도 같은 이유로 27쌍).
- 주 표와 민감도 표는 같은 점수·필터·분모를 쓰고 거래량 조건만 다르다 — 두 표의 효과(PIT − CONTROL) 방향은 같고 크기도 비슷하다(§4-6).
- 구현 뒤 두 관점 검토 지적 10건(겹침 포함 실제 5개: manifest 기록 · 재개로 라이브 가드 우회 · 폴더 위치 · compare 재개 여부 ·
  경계 테스트 누락)을 모두 고쳤다. 검토자가 봉인 DB 로 스모크 두 날짜를 독립 재계산해 사유 수·학습 행·label 이 일치했다.
- 러너 586줄 — KS-10 근접선(600) 아래지만 가깝다.

## 7) 사용자 확인이 필요한 항목

없음 — 아래 두 항목은 설계자 RESULT 판정(2026-09-25 · 설계서 끝 `# 설계자 RESULT 판정`)으로 결정됐다.

1. **manifest 두 파일(§4 지시문 외 변경 2)** — 승인(`MANIFEST_SPLIT = APPROVED`): `run_manifest.json` 은 시작 시점의 재개 지문과
   입력 계약, `run_manifest_final.json` 은 실제 분할·행 수·결과 hash·종료 시점 증거 — 역할이 달라 합치지 않는다.
2. **커밋 범위** — 검증자 `VERIFIED` 전에는 커밋·push 0. 통과 뒤 staged 29개를 함께 커밋·push 한다(사용자 소유 handoff · git 밖
   사후 진단 파일 제외).

---

## 4. 증거

### 4-1. 봉인 source · 달력 · universe

```text
봉인      02B 결과서 §4-1 과 같은 검증 · 이 실행 전후 동일 (file fe3022e9… · content c1a87776… · integrity ok)
달력      거래일 3,122 · 평가일 146 (2014-06-30 ~ 2026-07-31) · 기준선 manifest 파일 sha256 6b9c8938…(e2_dates 출처)
          평가 시점(signal·entry·next_signal·exit) 목록 sha256 e5f1be57… (재개 지문)
universe  PIT 1,418종목 (봉인 panel 전 종목 · 069500 제외 · 날짜 t 의 universe 는 이 중 t 에 v1 행이 있는 종목)
          CONTROL 1,170종목 (최종일 2026-09-21 에 행 · 069500 제외)
          146일 합계 후보 PIT 76,668 · CONTROL 66,686 · 점수 PIT 75,428 · CONTROL 65,650
          평가 표본(필터 · 주 label) PIT 53,658 · CONTROL 47,045 — 날짜별 PIT 102~914 · CONTROL 71~914
최종일에 없는 ETF   점수 9,778쌍 · 평가 6,613쌍 (PIT 만)
```

### 4-2. coverage (A7)

```text
             평균     최소     분모 정의
PIT          0.9551   0.8268   arm universe(t 행) ∩ 이름 필터 ∩ is_pit_eligible
CONTROL      0.9725   0.8987
교차(참고)   CONTROL 분자 / PIT 분모 — 최소 0.587 · 최대 0.988 · 0.70 미만 18일 (판정에 쓰지 않음)
```

### 4-3. 제외 사유 (146일 합계 · 한 쌍 한 사유)

```text
                              PIT 필터 전   PIT 필터 후   CONTROL 필터 전   CONTROL 필터 후
NOT_YET_LISTED                0             0             104,134           0
INSUFFICIENT_WARMUP           1,240         1,006         1,036             852
ZERO_VOLUME_ENTRY             1,365         967           750               565
NO_FORWARD_EXIT_PRICE         206           166           0                 0
ZERO_VOLUME_EXIT              720           535           405               321
NO_ENTRY_PRICE · NO_MODEL · BASEPRICE_RELATION_MISMATCH · NO_VALID_CLOSE · NON_POSITIVE_CLOSE ·
BENCHMARK_UNAVAILABLE · HISTORICAL_FILTER_UNAVAILABLE · NON_TRADING_DATE        모두 0 (두 arm)
점수 쌍 중 t 행 거래량 0      PIT 1,367 · CONTROL 769
```

마지막 가격을 청산가로 쓰지 않는다: 청산일 행 없음 → `NO_FORWARD_EXIT_PRICE` · 폐지 ETF 의 이어 붙인 거래량 0 마지막 행 →
`ZERO_VOLUME_EXIT`.

### 4-4. 분할 (A2)

```text
146일 모두 모델 있음 · purge 20일 · 두 arm 분할 지문(split_fingerprint) 146/146 같음
2014-06-30   학습일 44 (2014-02-03~04-03) · purge 04-04~05-02 · 검증 17일 (05-07~05-29) · PIT 학습 행 6,405 · 비율 0.7180
2026-07-31   학습일 2,417 (2014-02-03~2023-11-27) · purge 11-28~12-26 · 검증 610일 (2023-12-27~2026-07-02)
             PIT 학습 행 921,424 = trainer 921,424 · 검증 행 576,443 · 비율 0.6152 · CONTROL 학습 행 757,891
학습 행 범위  PIT 6,405 ~ 921,424 · CONTROL 4,381 ~ 757,891 · device cpu
```

### 4-5. 두 arm 지표 (주 표 · 146일)

```text
                                  PIT                          CONTROL                      PIT − CONTROL
IC 평균 (95% CI)                  −0.0322 (−0.0752 ~ +0.0100)  −0.0294 (−0.0726 ~ +0.0139)  −0.0029 (−0.0120 ~ +0.0048)
IC 중앙값                          −0.0216                      −0.0160                      −0.0056 (중앙값끼리 차이 · 짝 차이 중앙값 +0.0042)
IC 전 종목(필터 없음)              −0.0399                      −0.0381                      −0.0018
분위 스프레드 Q5−Q1                −0.00581                     −0.00522                     −0.00059
top-decile gross /월 (CI)          −0.00640 (−0.0201 ~ +0.0037) −0.00548 (−0.0191 ~ +0.0050) −0.00092 (−0.00295 ~ +0.00044)
top-decile net 10bp                −0.00804                     −0.00712                     −0.00092
top-decile net 25bp (기본 · CI)    −0.01050 (−0.0242 ~ −0.0004) −0.00958 (−0.0232 ~ +0.0010) −0.00092 (−0.00297 ~ +0.00044)
top-decile net 50bp                −0.01461                     −0.01367                     −0.00093
turnover (교체 비율)               0.826                        0.825                        +0.002
win rate (날짜)                    0.459                        0.479                        −0.021
전략 성과 (편도 11.5bp · 146기간 · 2014-07-01 ~ 2026-09-01 · price_basis KRX_BASEPRICE_CHAIN)
  CAGR                             5.19%                        6.24%                        −1.05%p
  MDD                              −35.81%                      −34.85%                      −0.96%p
  연 변동성                        18.15%                       18.76%                       −0.61%p
  Sharpe_0rf                       0.370                        0.417                        −0.047
  상대 wealth (끝)                 0.354                        0.400                        −0.046
  IR                               −0.505                       −0.437                       −0.068
  월평균 active                    −0.83%                       −0.74%                       −0.09%p
  KODEX200 (같은 기간)             CAGR 14.56% · MDD −32.19% · 끝 equity 5.229
전략 legacy all-in 25bp            CAGR 2.44% · 상대 wealth 0.256 CAGR 3.47% · 상대 wealth 0.290
```

연도별 IC 차이(PIT − CONTROL): 2014 −0.004 · 2015 −0.030 · 2016 +0.008 · 2017 +0.001 · 2018 +0.010 · 2019 −0.003 · 2020 −0.008 ·
2021 −0.001 · 2022 −0.010 · 2023 −0.011 · 2024 +0.005 · 2025 +0.008 · 2026 −0.001.

### 4-6. 민감도 `OFFICIAL_REFERENCE_SENSITIVITY` (판정 미사용 · 거래량 0 진입·청산 허용)

```text
                        PIT         CONTROL     PIT − CONTROL
IC 평균                 −0.0321     −0.0297     −0.0024
top-decile gross        −0.00653    −0.00554    −0.00098
top-decile net 25bp     −0.01061    −0.00962    −0.00099
전략 CAGR (11.5bp)      5.07%       6.22%       −1.15%p
```

주 표와 효과(PIT − CONTROL) 방향이 같고 크기도 비슷하다(IC −0.0029 대 −0.0024 · top-decile gross −0.00092 대 −0.00098 · net 25bp
−0.00092 대 −0.00099 · 전략 CAGR −1.05 대 −1.15%p) → 거래량 0 규칙이 효과를 만든 것은 아니다.

### 4-7. 실행 · 결정성

```text
run1   1,642.5초 (27.4분) · 최대 RSS 2.60 GB · resumed=false · progress 292 계산 · 0 재사용
       canonical 1e9a88afff4e2dc5ed49d9df3abe57b58f78ddbca1fafc29278efc4ba5881da6 · result.json sha256 edb1b0f6…
       라이브 5경로 시작·전·후 동일 · 봉인 전후 동일
run2   실행 기록 1,463.3초 · 최대 RSS 2.69 GB · resumed=false · progress 292 계산 · 0 재사용 · canonical 같음
       result.json sha256 2c1ed996… (generated_at 만 다름 — canonical 제외 필드)
       벽시계는 2,085초 — 02:44:47 부터 623초 시스템 잠자기(pmset 기록 'Maintenance Sleep') · 결과 영향 없음
       라이브 5경로 시작·전·후 동일 · 봉인 전후 동일
compare identical = true · determinism_eligible = true(두 폴더 모두 재개 없음) · both_official = true · determinism_confirmed = true
누수    L1 0 · L2 0 · L3 0 (두 arm) · N-1 셔플 통제 통과 (평균 PIT +0.0002 · CONTROL −0.0003)
```

### 4-8. 코드 hash · 자체 검수

```text
실행 당시 = 지금 (run1·run2 manifest 의 불러온 모듈 20개 raw sha256 전부 일치)
  app/ml_pit_universe.py  fa160229…   app/ml_pit_bias_eval.py  fb125d55…   app/ml_pit_bias_report.py  3e3e3051…
  scripts/run_poc4_02a_pit_bias.py  a49af9ce…   app/krx_sealed_reader.py  e43275ff…
  고정 모듈 features 11910654… · model b41b2a9a… · score 8d53aa56… — git HEAD 와 같음(수정 0)
black --check · flake8 · py_compile   새 파일 21개 통과 (02B 결과서 §4-10)
02A 테스트                            35건 — tmp 고정 DB · 봉인·라이브 DB 미접속 · 허용 목록 미추가
전체 회귀                             2,134 passed (0:04:13)
```
