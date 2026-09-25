> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-09-24) · 기록: 개발자(VSCode Claude). 아래는 설계자 원문 그대로다.
> 이 문서가 POC4-02 의 정본 설계서다. 이전에 말로 전달된 단일 `POC4-02 KRX PIT UNIVERSE RESEARCH BASELINE` 지시는
> 저장소에 설계서 파일로 기록된 적이 없어 `SUPERSEDED` 표시를 붙일 V1 파일이 없다.
> 개발 PLAN: `docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md` · `docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md`
> **설계자 PLAN 판정(2026-09-25)** 원문은 이 문서 끝 `# 설계자 PLAN 판정` 절에 그대로 붙였다 — V2 본문과 충돌하는 곳은 판정이 우선한다
> (가격 기준 `KRX_BASEPRICE_CHAIN` · 거래량 0 진입·청산 규칙 · 02B 사건·경보·판정 계약 등).
> **설계자 RESULT 판정(2026-09-25)** 원문은 문서 맨 끝 `# 설계자 RESULT 판정` 절 — 02B `REJECT` 수용·종결 · 02A `MEASURED` 수용 ·
> 검증 전 문서 정정 2곳 · 검증자 `VERIFIED` 뒤 커밋·push.

# POC4 설계 변경 및 POC4-02 통합 지시 V2

```text
DESIGN_REVISION          = POC4_SEQUENCE_V2
POC4_01                  = CLOSED · VERIFIED · REMOTE 94cec4e2
POC4_02A                 = KRX PIT UNIVERSE BIAS MEASUREMENT
POC4_02B                 = DOWNSIDE EARLY-WARNING BASELINE
POC4_03                  = TRACK_A KILL GATE
POC4_04 / POC4_05        = CONDITIONAL_NOT_OPEN
CURRENT_ACTION           = PLAN_ONLY
IMPLEMENTATION_AUTHORIZED = NO
```

## 0. 기존 설계 교체

이전에 전달한 단일 `POC4-02 KRX PIT UNIVERSE RESEARCH BASELINE` 지시는 이 문서로 교체한다.

이미 V1 설계서를 작성했다면 삭제하지 말고 다음을 머리말에 표시한다.

```text
STATUS = SUPERSEDED_BY_POC4_SEQUENCE_V2
```

새 정본 설계서는 다음 경로에 기록한다.

```text
docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md
```

POC4-00 Master Plan도 다음과 같이 정정한다.

| 단계         | 변경 후 역할                            |
| ---------- | ---------------------------------- |
| POC4-01    | 불변 기준선·테스트 격리·KRX 봉인 universe 완료   |
| POC4-02A   | 동일 KRX 가격에서 PIT와 최종 생존 universe 비교 |
| POC4-02B   | 위험 구간 조기감지 가능성 검증                  |
| POC4-03    | RF 대 단순 모멘텀 최종 Kill Gate           |
| POC4-04·05 | POC4-03 PASS 전에는 미개방               |

POC4-01에서 기존 baseline 재현까지 끝났으므로 이를 POC4-02에서 반복하지 않는다.

---

# Part A — POC4-02A

## 1. 목적

`POC4-02A`는 모델을 개선하는 단계가 아니다.

동일한 KRX 가격 데이터에서 universe만 바꿔 다음을 측정한다.

```text
SURVIVORSHIP_EFFECT = PIT_UNIVERSE - FINAL_SURVIVOR_CONTROL
```

목표는 생존편향의 방향과 크기를 분리하는 것이다. 성과가 좋아지거나 나빠지는 것은 구현 성공 기준이 아니다.

PLAN:

```text
docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md
```

## 2. 비교 설계

| 실험      | Universe              | 가격                    |
| ------- | --------------------- | --------------------- |
| CONTROL | 최종 기준일 생존 ETF를 과거에 투영 | `krx_etf_universe_v1` |
| PIT     | 각 날짜에 실제 존재한 ETF      | `krx_etf_universe_v1` |

두 실험은 다음을 완전히 같게 한다.

* feature 7개
* `future_excess_return_20d`
* 모델과 하이퍼파라미터
* seed
* walk-forward grid
* purge·embargo 20거래일
* 거래비용
* KODEX200 benchmark
* 주 비교 평가일

기존 `relative_upside_v1_snap_20260921`과 KRX 실험의 차이는 가격 source까지 다르므로 참고치로만 둔다.

## 3. 입력 계약

```text
SOURCE_VERSION = krx_etf_universe_v1
SOURCE_STATUS  = SEALED
SOURCE_DB      = state/ml/research/krx_etf_universe.sqlite
BENCHMARK      = 069500
PRICE_BASIS    = KRX_UNADJUSTED_TRADED_CLOSE
```

필수 규칙:

* 봉인 DB를 읽기 전용으로 연다.
* 실행 전후 hash·integrity를 확인한다.
* 현재 `etf_master`로 역사 universe를 다시 필터링하지 않는다.
* 운영 `etf_daily_price`로 결측을 보충하지 않는다.
* KODEX200도 동일 봉인 version에서 읽는다.
* 상장 전·폐지 후 가격을 만들지 않는다.
* 결측·0·휴장 응답을 보간하거나 이월하지 않는다.
* 봉인 DB를 수정하거나 새 데이터를 붙이지 않는다.
* 외부 호출을 하지 않는다.

## 4. PLAN 선행 사실조사

구현 전에 다음을 실측한다.

1. 봉인 DB의 실제 테이블·컬럼·PK
2. 7개 feature 생성 가능 여부
3. 20거래일 label 생성 가능 여부
4. 최종일 생존 ETF와 역사상 존재했던 ETF 수
5. 날짜별 universe 크기
6. `069500`의 범위·결측·0가격
7. 신규 상장 ETF의 warm-up 부족 규모
8. 폐지 직전 ETF의 미래가격 부족 규모
9. 당시 상품 유형을 KRX 필드만으로 구분할 수 있는지
10. ticker 재사용 흔적
11. CONTROL과 PIT의 공통 평가일
12. 파생 dataset 예상 크기와 실행시간
13. 재사용 모듈과 신규 모듈
14. 전체 KS-10 측정

당시 상품 유형을 구분하기 위해 현재 `etf_master`가 필요하다면 중단·보고한다.

## 5. 제외 사유

다음을 별도 집계한다.

```text
NON_TRADING_DATE
NOT_YET_LISTED
NO_VALID_CLOSE
NON_POSITIVE_CLOSE
INSUFFICIENT_WARMUP
NO_FORWARD_EXIT_PRICE
BENCHMARK_UNAVAILABLE
HISTORICAL_FILTER_UNAVAILABLE
```

폐지 직전 미래가격이 없다고 마지막 가격을 임의 청산가로 사용하지 않는다.

공식 표현은 다음으로 제한한다.

```text
universe_basis             = KRX_POINT_IN_TIME_UNIVERSE_V1
survivorship_status        = REDUCED_NOT_ELIMINATED
ceiling                    = RESEARCH_ONLY
UNBIASED_PERFORMANCE_CLAIM = NOT_YET
```

## 6. 산출 지표

CONTROL과 PIT에 대해 같은 지표를 낸다.

* IC와 신뢰구간
* top-decile gross/net
* turnover
* win rate
* CAGR
* MDD
* 변동성
* Sharpe
* 상대 wealth
* Information Ratio
* 월평균 active return
* 평가일·표본 수
* 제외 사유별 수
* 역사상 존재했지만 최종일에는 없는 ETF 포함 수

주 비교는 공통 평가일에서 수행한다. 평가일 차이는 coverage 표로 따로 기록한다.

---

# Part B — POC4-02B

## 7. 목적

Track B는 프로젝트의 원래 사용자 목적에 더 가깝다.

```text
최종 사용자 출력 = 위험 구간 / 정상 구간
금지              = 미래 하락률을 확정값처럼 예측
```

미래 구간의 하락은 모델 출력이 아니라 **과거 검증용 label**로만 쓴다.

산출물은 하나다.

> 현재 위험 신호가 과거 실제 하락 구간을 며칠 먼저 포착했는지, 얼마나 놓쳤고 얼마나 오탐했는지 보여주는 연구 리포트

PLAN:

```text
docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md
```

## 8. 출발점

새 모델부터 만들지 않는다. 기존 `risk_baseline`을 먼저 재현한다.

우선 조사 대상:

```text
app/ml_baseline_risk.py 또는 실제 risk_baseline 구현 경로
drawdown_capture_rate
high_minus_low_return
high/low_risk_group_future_down_ratio_5d
future_drawdown
```

PLAN에 다음을 정확히 밝힌다.

1. 분류 단위가 시장일인지 ETF-date인지
2. 현재 high/low risk를 가르는 factor
3. threshold
4. 미래 검증 horizon
5. 미래 하락 label
6. 실제 호출 경로와 현재 산출물
7. 현재 결과를 재현할 수 있는지
8. KRX 봉인 데이터만으로 다시 계산할 수 있는지

## 9. 위험 축의 비교 방식

POC4-02B에서는 최대 두 가지 factor 조합만 허용한다.

* 기존 `risk_baseline`
* 현재 하락이 이미 발생한 뒤 반응하는 단순 반응형 기준선

새 factor를 계속 추가하거나 threshold를 결과를 본 뒤 조정하지 않는다.

주 비교는 같은 경보 빈도에서 수행한다.

```text
EARLY_WARNING vs REACTIVE_BASELINE
```

필수 지표:

* 전체 하락 사건 수
* 사전 포착 사건 수
* 사건별 최초 경보 선행 거래일
* 선행일 중앙값·분포
* 사건 시작 후에만 잡은 수
* 완전 미포착 수
* alert day 수
* false alarm day 수
* precision
* recall/capture rate
* severe-event miss 목록
* 연도별 결과
* 최종 생존 universe와 PIT universe 결과 차이

하락 사건의 정확한 horizon·threshold는 기존 `risk_baseline` 계약을 먼저 사용한다. 기존 계약이 없거나 여러 값이라면 결과를 보기 전에 PLAN에서 후보와 선택 근거를 제출하고 설계자 확정을 받는다.

## 10. Track B 판정 원칙

POC4-02B는 모델 개발 단계가 아니라 **선행 신호 존재 여부 확인 단계**다.

PASS 후보 조건:

* 반응형 기준선보다 실제 선행일이 존재
* 같은 경보 빈도에서 capture가 개선
* severe-event miss가 증가하지 않음
* 신호가 사건 발생 뒤에만 켜지는 단순 후행 지표가 아님
* 기간 일부에만 몰린 결과가 아님
* 두 번 실행 결과 동일

다음이면 REJECT한다.

* 중앙 선행일이 0 이하
* 개선이 특정 연도 또는 소수 사건에만 의존
* 오탐 증가만으로 capture를 올림
* 현재 drawdown을 다시 표현했을 뿐 조기 신호가 아님
* PIT 적용 후 효과가 사라짐
* 결과를 본 뒤 threshold를 바꿔야만 PASS함

PASS는 곧 PUSH 승인이 아니다. PASS이면 별도 설계로 운영 후보화를 검토한다.

```text
TRACK_B_PASS ≠ PUSH_ACTIVATION
```

## 11. Track B 데이터 규율

* POC4-02A와 같은 KRX 봉인 source를 사용한다.
* 평가 label은 미래 데이터를 사용해도 되지만 feature는 판정 시점 이전 데이터만 사용한다.
* label과 feature 사이에 horizon만큼 purge·embargo를 둔다.
* 운영 DB·현재 `etf_master`로 결측을 보충하지 않는다.
* 임계값·factor를 결과를 본 뒤 추가하지 않는다.
* RF·XGBoost·LightGBM은 사용하지 않는다.
* 신규 외부 source를 추가하지 않는다.

---

# Part C — 공통 계약

## 12. 병렬의 의미

`02A`와 `02B`는 서로 선행관계가 없다.

* 두 PLAN을 함께 제출할 수 있다.
* 같은 봉인 DB를 읽기 전용으로 사용할 수 있다.
* 산출물·모듈·테스트는 분리한다.
* 공유 파일을 동시에 수정하는 구조로 만들지 않는다.
* 하나의 결과가 다른 결과의 threshold나 universe를 바꾸면 안 된다.

판정 순서는 다음과 같다.

1. POC4-02A 결과
2. **POC4-02B 결과를 우선 판단**
3. 그 뒤에만 POC4-03 개방 여부 판단

## 13. 공통 금지 범위

두 Step 모두 다음을 하지 않는다.

* RF·XGBoost·LightGBM 구현
* 자동 튜닝
* feature 무제한 추가
* 화면·API 추가
* OCI 전달
* PARAM 승격
* PUSH 연결
* 운영 DB 변경
* 추가 KRX 다운로드
* 신규 패키지 설치
* 기존 기준선 덮어쓰기
* 라이브 state 수정

## 14. KS-10

다음 파일에는 기능을 추가하지 않는다.

```text
app/ml_score_validity_report.py           626줄
scripts/run_ml_score_validity_eval_v1.py  599줄
```

기존 러너와 보고서에 조건을 누적하지 말고 02A·02B 전용 모듈로 분리한다.

신규 파일은 해당 역할의 NEAR 기준 미만으로 설계한다.

## 15. 공통 테스트

최소한 다음을 검증한다.

* 미래 상장 ETF가 과거 universe에 없음
* 폐지 ETF가 실제 존재일 PIT universe에는 있음
* 현재 `etf_master`를 바꿔도 결과 불변
* 운영 `etf_daily_price` 접근 시 실패
* benchmark source가 다르면 실패
* 봉인 version·hash 불일치 시 실패
* 결측·0·휴장·warm-up·미래가격 부족 사유 분리
* 새 결과 폴더만 허용하고 덮어쓰기 실패
* 동일 입력 두 번 실행 결과 동일
* 전체 회귀 통과
* 라이브 5경로 전후 동일
* 외부 네트워크 0건
* 신규 테스트가 229건 세션 사본 허용 목록에 추가되지 않음

---

# Part D — POC4-03 Kill Gate

## 16. POC4-03 개방 조건

POC4-03은 POC4-02A·02B가 끝난 뒤 별도 설계로 연다.

비교 대상은 세 개뿐이다.

```text
1. 기존 선형 baseline
2. 단순 20일 모멘텀
3. RandomForest (sklearn · 사전 고정 설정 최대 3개)
```

자동 튜닝은 금지한다. XGBoost·LightGBM도 아직 열지 않는다.

## 17. Kill Gate

다음 중 하나면 Track A를 종료한다.

* RF의 IC가 단순 모멘텀 이하
* RF의 비용 반영 성과가 단순 모멘텀 이하
* RF−모멘텀 개선의 block-bootstrap 신뢰구간이 0을 넘지 못함
* PIT universe에서만 성능이 무너짐
* 결과가 특정 기간이나 단일 설정에 의존
* 결정성 재실행 실패

```text
IF MOMENTUM >= RF:
    TRACK_A = CLOSED_REJECT
    POC4_04 = NOT_OPENED
    POC4_05 = NOT_OPENED
```

한 지표만 이기고 다른 지표가 불리하면 PASS가 아니라 `INCONCLUSIVE → CLOSED`로 판정한다.

RF가 실제로 Gate를 통과한 경우에만 사용자 승인 후 POC4-04를 새로 설계한다. 번호가 있다는 이유로 자동 진행하지 않는다.

## 18. Track B와 독립 판정

Track A가 REJECT여도 Track B가 PASS할 수 있다.

| Track A | Track B | 다음                          |
| ------- | ------- | --------------------------- |
| FAIL    | FAIL    | POC4 연구 종료                  |
| FAIL    | PASS    | 상승후보 ML 종료, 위험 축 운영후보 별도 설계 |
| PASS    | FAIL    | Track A의 POC4-04 개방 여부 판단   |
| PASS    | PASS    | 두 축을 섞지 않고 각각 별도 다음 설계      |

Track B가 PASS해도 기존 PUSH에 즉시 연결하지 않는다. 사용자 확인·운영 비용·오탐 상한·fail-closed 계약을 별도 설계한다.

---

# Part E — 개발자 제출물

## 19. 이번에 제출할 것

코드는 수정하지 않는다.

다음 세 문서만 제출한다.

```text
docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md
docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md
docs/ai_plan/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md
```

각 PLAN 앞부분에 독립 사실조사를 넣고, 공통 사실은 복사하지 말고 동일 증거 경로를 참조한다.

제출 형식:

```text
POC4_SEQUENCE_REVISION
POC4_02A_PLAN_STATUS
POC4_02B_PLAN_STATUS

02A:
  SEALED_SOURCE_VERIFIED
  FEATURE_7_FEASIBILITY
  LABEL_20D_FEASIBILITY
  CONTROL_UNIVERSE
  PIT_UNIVERSE
  COMMON_EVALUATION_DATES
  HISTORICAL_FILTER_FEASIBILITY
  EXPECTED_STORAGE / RUNTIME

02B:
  EXISTING_RISK_BASELINE_PATH
  CLASSIFICATION_UNIT
  EXISTING_FACTORS
  EVENT_LABEL
  HORIZON / THRESHOLD
  EVENT_COUNT
  REACTIVE_BASELINE
  LEAD_TIME_MEASUREMENT
  FALSE_ALARM_MEASUREMENT
  EXPECTED_STORAGE / RUNTIME

COMMON:
  KS10_TRIGGER / NEAR
  EXTERNAL_CALLS = 0
  NEW_DEPENDENCY = 0
  OCI_PUSH_CHANGE = 0
  IMPLEMENTATION = NOT_STARTED
```

## 20. 중단 조건

다음이면 구현하지 않고 보고한다.

* 봉인 KRX 데이터만으로 필요한 가격·label 생성 불가
* 현재 `etf_master` 또는 운영 가격 DB가 필요
* KODEX200을 다른 source에서 가져와야 함
* risk baseline의 factor·threshold·label을 재현할 수 없음
* 결과를 보기 전에 Track B 성공 기준을 고정할 수 없음
* 추가 네트워크·신규 의존성 필요
* 기존 기준선 수정 필요
* KS-10 trigger 발생
* 라이브 DB·상태 파일 변경 필요
* 두 PLAN이 같은 운영 모듈을 동시에 수정해야 함

## 21. 작업 리듬

```text
DEADLINE                  = NONE
PRODUCTION_URGENCY        = NONE
POC3_PUSH_OPERATION       = 정상 운영 중
NIGHTLY_COMPLETION_TARGET = 없음
```

두 PLAN을 병렬로 열되 하루 안에 끝내기 위한 폭주 작업으로 취급하지 않는다. 1.86GB 봉인 DB 작업은 읽기 전용·재개 가능 구조로 설계하고, 라이브 DB를 건드리는 편법을 쓰지 않는다.

---

이 변경으로 POC4는 더 이상 “REJECT 모델을 위해 5단계를 끝까지 수행하는 계획”이 아닙니다.

* 02A는 생존편향을 수치화하는 짧은 측정
* 02B는 사용자 목적에 직접 닿는 위험 조기감지 검증
* 03은 진짜 중단 Gate
* 04·05는 PASS가 나와야만 존재하는 단계

개발자는 지금 코딩하지 않고 두 PLAN을 함께 제출하면 됩니다.


---

# 설계자 PLAN 판정 (2026-09-25 · 설계자 원문 · 사용자 전달)

판정은 두 PLAN 모두 **필수 보완조건부 승인**입니다. 사실조사는 충분하며 PLAN 재제출은 필요 없습니다. 아래 결정대로 문서를 동기화한 뒤 02A·02B 구현을 시작해도 됩니다.

```text
POC4_02A_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS
POC4_02B_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS
PLAN_RESUBMISSION_REQUIRED = NO
IMPLEMENTATION_AUTHORIZED  = YES_AFTER_DOCUMENT_SYNC
EXTERNAL_CALLS             = 0
OCI_PUSH_CHANGE            = 0
NEW_DEPENDENCY             = 0
COMMIT_PUSH                = 0
```

## 1. 02A 확정 11건

| #   | 확정                                                                   |
| --- | -------------------------------------------------------------------- |
| A1  | 학습 target은 `future_excess_return_20d`, 평가는 기존 E2 `forward_excess` 유지 |
| A2  | 날짜 기준 분할 + purge 20거래일 채택. 기존 trainer에 호출별 비율을 계산해 넘기는 (a)안          |
| A3  | 거래량 0 기준은 아래 별도 계약 적용                                                |
| A4  | 날짜별 `ISU_NM` 사용                                                      |
| A5  | CONTROL은 KRX 최종일 1,171개 기준                                           |
| A6  | 기존 E2 평가일 146개 고정                                                    |
| A7  | 실행 차단용 coverage는 arm별 자기 universe, 교차 coverage는 참고표                  |
| A8  | 봉인 reader 하나를 공용으로 만들고 02B가 수정 없이 사용                                 |
| A9  | V2 병렬 연구를 승인하고 `PROJECT_ORIGIN_INTENT §9.5`에 날짜가 붙은 예외 추가            |
| A10 | `scripts/`는 backend 기준, `tests/_live_guard.py`는 test 기준 적용           |
| A11 | top-decile 기본 비용은 기존 A2와 같은 편도 25bp 유지. 전략 성과는 11.5bp도 병기            |

### A2 분할 해석

이번 결과는 기존 불변 기준선을 수정하는 것이 아니라 새로운 `POC4-02A` 연구 recipe다.

* 동일 날짜 경계를 두 arm에 적용
* 학습 마지막 label이 검증 구간에 걸치지 않도록 20거래일 purge
* 검증 이후 자료를 학습에 쓰지 않으므로 사후 embargo는 구조적으로 적용 완료
* 실제 학습 행 수와 마지막 학습일을 manifest에 기록
* 기존 `relative_upside_v1_snap_20260921`은 변경하지 않음

별도 학습 루프를 복제하지 말고 기존 trainer를 호출하는 (a)를 사용합니다.

## 2. 02A 가격·거래량 계약 변경

사실조사에서 분배 조정 차이가 확인됐으므로 이전 설계의 `KRX_UNADJUSTED_TRADED_CLOSE`를 주 성과 기준으로 쓰지 않습니다.

```text
PRIMARY_PRICE_BASIS = KRX_BASEPRICE_CHAIN
```

계산은 같은 봉인 source의 공식 일간 변동률을 사용합니다.

```text
previous_reference = TDD_CLSPRC - CMPPREVDD_PRC
daily_return        = CMPPREVDD_PRC / previous_reference
                    = FLUC_RT / 100
```

전체 유효 행에서 위 관계를 허용 오차 내 검증하고, 맞지 않는 행은 임의 보정하지 않고 제외 사유로 기록합니다.

거래량 0은 다음처럼 나눕니다.

* feature 계산: KRX 공식 기준가격으로 사용 가능하되 `zero_volume=true` 기록
* 주 성과의 진입·청산: `ACC_TRDVOL > 0` 필수
* 거래량 0 진입: `ZERO_VOLUME_ENTRY`
* 거래량 0 청산: `ZERO_VOLUME_EXIT`
* 청산일 행 없음: `NO_FORWARD_EXIT_PRICE`
* 다음 거래일로 미루거나 마지막 체결가를 청산가로 대체하지 않음
* 폐지 ETF의 이어 붙인 마지막 가격은 주 성과 청산가로 사용하지 않음

같은 점수로 거래량 0도 공식 기준가격으로 인정한 결과를 `OFFICIAL_REFERENCE_SENSITIVITY`로 추가할 수 있습니다. 이는 민감도 표일 뿐 주 판정에는 쓰지 않습니다. 모델을 다시 학습할 필요는 없습니다.

## 3. 02A 공용 reader

`app/krx_sealed_reader.py`를 두 트랙의 공용 기반으로 승인합니다.

이는 분석 선행관계가 아니라 코드 기반 순서입니다.

1. 공용 reader 구현·고정 fixture 테스트
2. 이후 02A·02B가 수정 없이 import
3. 한쪽에서 변경이 필요하면 임의 수정하지 않고 공통 계약 변경으로 보고

중복 reader 두 벌은 만들지 않습니다.

---

## 4. 02B 확정 13건

| #   | 확정                                                |
| --- | ------------------------------------------------- |
| B1  | 주 사건 label은 분배 중립 계열의 `dd10 ≤ −5%`                |
| B2  | 조기감지 평가는 반드시 시점 기준 점수 사용                          |
| B3  | 알려진 기존 합성 결함은 그대로 두지 않고 아래처럼 교정                   |
| B4  | KRX `FLUC_RT` 기반 분배 중립 계열 사용                      |
| B5  | 사건 시작은 실현 고점일 `P`                                 |
| B6  | 사전 창 `W=10`, label 구간은 간격 `≤ h−1`일 때만 하나의 사건으로 병합 |
| B7  | severe는 완결 사건 중 실현 깊이 하위 25%                      |
| B8  | 연도·사건 제외 안정성 검사 유지                                |
| B9  | 시점 기준 누적 분위가 주 비교. 전체 기간 exact-k는 참고만             |
| B10 | universe 축은 날짜별 이름으로 인버스·레버리지·합성·선물 제외            |
| B11 | 운영 표 재현은 읽기 전용 동결 사본을 이용한 진단 단계로만 승인              |
| B12 | 오른쪽이 잘린 사건은 주 판정에서 제외                             |
| B13 | 학습이 없는 시점 기준 규칙에는 purge·embargo 비적용               |

### B1·B6 사건 정의

```text
EVENT_LABEL     = future_market_drawdown_10d <= -5%
PRICE_BASIS     = KRX_BASEPRICE_CHAIN
EVENT_GROUPING  = label 날짜 간격 <= 9거래일일 때 병합
EVENT_START     = 실현 고점일 P
PRE_WINDOW      = P 이전 10거래일
```

간격이 정확히 10거래일인 두 label은 미래 창이 겹치지 않으므로 서로 다른 사건입니다. 사건 수는 이 확정 계약으로 다시 계산해 결과서에 기록합니다. 숫자가 36에서 달라져도 설계 변경이 아니라 정의 정정입니다.

## 5. 기존 risk baseline 결함 처리

기존 보고서의 수치는 먼저 정확히 재현하되, 그것을 주 조기감지 신호로 쓰면 안 됩니다.

```text
LEGACY_REPRODUCTION = 감사용 · 기존 결함 그대로
EARLY_WARNING       = 시점 기준 교정본 · 주 평가 대상
REACTIVE_BASELINE   = drawdown_20d_market_proxy
```

주 평가용 `EARLY_WARNING`은 새 factor를 추가하지 않고 다음 세 결함만 고칩니다.

1. 동일한 낙폭 축 2개는 하나로 축소
2. 방향이 반대인 `short_term_weakness_proxy`의 위험 방향 교정
3. 축별 값의 개수가 달라도 같은 0~1 과거 percentile로 정규화한 뒤 평균

모든 순위·정규화는 날짜 `t` 이전 값만 사용합니다. 결측 축은 빼고 평균하되 최소 3개 축 조건을 유지합니다.

이는 세 번째 factor 조합이 아니라 **알려진 계산 결함을 제거한 동일 factor 집합**입니다. 결함이 있는 legacy 결과와 교정 결과를 나란히 기록합니다.

## 6. 경보 기준과 무작위 기준

전체 기간 상위 `k`를 주 비교로 사용하면 미래 정보를 사용하게 됩니다. 개발자 제안 (a)는 기각하고 (b)를 채택합니다.

주 경보:

```text
현재 점수 >= 이전 날짜들 점수의 66.67 percentile
```

* 최소 과거 이력은 기존 60일 lookback을 따른다.
* 경계 동점은 전부 경보로 포함한다.
* 실제 경보 수와 비율을 보고한다.
* 전체 기간 exact-k 결과는 `LOOKAHEAD_DIAGNOSTIC_ONLY`로만 기록하고 PASS/REJECT에 사용하지 않는다.

무작위 기준은 단순 날짜 추출이 아니라 다음으로 고정합니다.

```text
RANDOM_NULL = 연도별 경보 run 수·각 run 길이를 보존한 circular shift
REPEATS     = 1,000
SEED        = 고정
```

이렇게 해야 연속 경보가 많은 신호와 무작위 하루 경보를 잘못 비교하지 않습니다.

## 7. 02B PASS/REJECT 계약 수정

기존 PLAN의 `EARLY capture > REACTIVE`는 무작위도 대부분 사건을 잡는 구조라 변별력이 부족합니다. 다음 조건을 모두 만족해야 PASS입니다.

```text
1. EARLY의 전체 포착 선행일 중앙값 > REACTIVE
2. EARLY의 사전 capture >= REACTIVE
3. EARLY의 severe 완전 미포착 수 <= REACTIVE
4. 포착 사건 중 사전 포착 비율 > REACTIVE
5. 경보 run precision > REACTIVE
6. 경보 100건당 false-alarm run < REACTIVE
7. 경보 run precision이 RANDOM_NULL 95% 분위보다 높음
8. PIT universe에서도 1~7의 방향 유지
9. 2026년을 제외해도 핵심 방향 유지
10. 사건 하나 또는 사건이 있는 연도 하나를 빼도 핵심 우위의 부호 유지
11. 두 번 실행 canonical 동일
```

하나라도 실패하면 `REJECT` 또는 `INCONCLUSIVE → CLOSED`입니다. 결과를 보고 threshold를 바꾸는 재시도는 허용하지 않습니다.

## 8. 잘린 사건·동점·purge

* `2026-04-29~09-07`처럼 끝과 저점을 모르는 사건은 `RIGHT_CENSORED_EVENT`로 기록
* 주 capture·precision·severe·PASS 판정에서 전부 제외
* 현재까지 관찰된 부분은 설명용 표에만 포함
* 시점 기준 percentile 경계의 동점은 모두 포함
* 학습이나 threshold fit이 없으므로 purge·embargo는 `NOT_APPLICABLE_TO_NO_FIT_RULE`
* 전체 기간 exact-k 진단에는 `LOOKAHEAD=true`를 명시하고 판정에서 제외

## 9. universe 필터

기존 builder의 전 종목 포함은 주 평가에서 유지하지 않습니다.

날짜별 `ISU_NM`으로 다음을 제외합니다.

* 인버스
* 레버리지·2X·2배
* 합성
* 선물

기존 전 종목 방식은 legacy 재현에만 사용합니다. 이는 프로젝트의 일관된 ETF 필터 계약과도 맞습니다.

## 10. 운영 DB 재현

기존 보고서 재현을 위한 운영 표 2개 읽기는 중단 조건으로 보지 않습니다. 다만 다음 조건입니다.

* POC4-01에서 승인된 방식으로 읽기 전용 세션 사본 생성
* 사본 hash·integrity 기록
* 라이브 DB 직접 연결 금지
* 재현 단계가 끝나면 이후 KRX 평가에는 사용하지 않음
* 기존 `ml_baseline_v0_report_latest.json` 및 feature 표 쓰기 0
* 실행 전후 라이브 5경로 동일

운영 DB 재현은 “옛 숫자를 제대로 이해했다”는 감사 증거일 뿐, 02B 결과 입력은 아닙니다.

---

## 11. 문서 동기화

구현 전에 다음을 반영합니다.

### `PROJECT_ORIGIN_INTENT §9.5`

기존 문장을 삭제하지 말고 날짜가 붙은 예외를 추가합니다.

```text
2026-09-25 정정:
축 1·축 2의 운영 승격을 동시에 진행하지 않는 원칙은 유지한다.
다만 동일한 봉인 연구 데이터를 사용하는 독립 연구 02A·02B는 병렬 개방한다.
두 트랙은 결과·threshold·산출물을 공유하지 않으며 각각 독립 판정한다.
```

### `ASSUMPTIONS Q6`

```text
RESEARCH_CONTRACT = FIXED_FOR_POC4_02B
OPERATIONAL_CONTRACT = OPEN
```

연구 label과 판정 기준을 고정했을 뿐 운영 임계·PUSH 계약은 아직 확정하지 않았음을 남깁니다.

### 중복 문구 정리

* 02A의 “옛 행으로 점수 매겼다” 중복
* 02A 실행 규율의 `progress/` 문단 중복
* 02B의 `## 8. 설계자 확인 필요` 중복

## 12. 구현·검증 순서

```text
1. 설계서·PLAN·Master Plan·PROJECT_ORIGIN_INTENT·ASSUMPTIONS 동기화
2. 공용 krx_sealed_reader 구현 및 고정 fixture 검증
3. 02A·02B 독립 구현
4. 장시간 02A와 02B 실행은 동시에 돌리지 않음
5. 각각 처음부터 두 번 실행해 결정성 확인
6. 결과서 2개를 별도로 제출
7. 설계자는 02B 결과를 먼저 판정
8. 설계자 통과 범위만 검증자에게 전달
```

결과서 경로:

```text
docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md
docs/ai_result/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md
```

## 13. 범위와 상태

```text
PLAN_RESUBMISSION       = NOT_REQUIRED
IMPLEMENTATION          = AUTHORIZED_AFTER_DOCUMENT_SYNC
COMMIT                  = 0
PUSH                    = 0
OCI_WRITE               = 0
EXTERNAL_CALLS          = 0
NEW_DEPENDENCY          = 0
RF_XGB_LGBM             = 0
PUSH_INTEGRATION        = 0
USER_SCREEN_CHECK       = NOT_REQUIRED
```

문서 네 건은 지금 별도 커밋하지 않습니다. 위 확정 내용을 반영한 뒤 구현과 결과서까지 진행하고, 설계자 판정과 검증을 거쳐 커밋 범위를 정합니다.

이제 추가 질문 없이 02A·02B 구현으로 넘어가면 됩니다.

---

# 설계자 RESULT 판정 (2026-09-25 · 설계자 원문 · 사용자 전달)

판정은 **02B REJECT 수용·종결, 02A MEASURED 수용**입니다. 사건 정의를 고쳐 02B를 다시 돌리지 않습니다. 문서 2곳만 정정한 뒤 검증자로 넘기면 됩니다.

개발자에게 아래 내용을 전달해 주세요.

```text
POC4-02A / 02B — 설계자 RESULT 판정

DESIGNER_DECISION          = PASS_TO_VERIFIER_WITH_DOC_FIXES
POC4_02B                   = REJECT_ACCEPTED
POC4_02B_RERUN             = NO
POC4_02A                   = MEASURED_ACCEPTED
MANIFEST_SPLIT             = APPROVED
READY_FOR_VERIFIER         = AFTER_DOC_FIXES
COMMIT_PUSH                = 0 UNTIL VERIFIER_VERIFIED
OCI_PUSH_EXTERNAL_CALLS    = 0
```

### 1. POC4-02B 판정

`REJECT`를 수용한다.

EARLY는 사전 포착 수는 늘렸지만 다음 핵심 기준에서 명확히 실패했다.

* 선행일 중앙값 우위 없음: 8.0 대 8.0
* run precision 열위: 0.2820 대 0.4459
* 오경보 run 열위: 23.59 대 8.06/100
* 무작위 기준에도 미달: 0.2820 < p95 0.3256
* 2026 제외·사건 하나 제외·연도 하나 제외에서도 결론 유지 실패

따라서 이 방식은 운영 후보나 추가 모델 입력으로 승격하지 않는다.

사건 정의 결함은 인정하지만 재실행하지 않는다. 사전 정의·ALT_A·ALT_B 모두 조건 5·6·7에서 실패했으므로, 정의 변경으로 결론이 바뀔 가능성이 실증상 없다. 재실행은 같은 REJECT를 정밀화하는 작업이 된다.

다만 현재 사건 정의는 향후 연구에 재사용하지 않는다.

```text
CURRENT_OFFICIAL_RESULT = 사전 등록 정의에 따른 REJECT
EVENT_DEFINITION_STATUS = RETIRED_AFTER_THIS_STUDY
FUTURE_TRACK_B_RETRY    = 새 PLAN·새 사전 등록이 있는 별도 연구만 가능
```

사후 민감도 결과는 공식 판정을 대체하지 않는 진단으로만 남긴다.

### 2. 잘린 사건 제외 창

`[F−10, 관측 종료일]` 적용을 승인한다.

이는 “잘린 사건을 precision에서 전부 제외한다”는 확정 계약에 더 정확히 맞는다. 변경 전후 조건 1~7의 참·거짓도 같으므로 공식 실행을 다시 돌릴 필요가 없다.

### 3. 조건 8 해석

현재 결론을 승인한다.

주 평가 자체가 PIT이므로 조건 8은 독립적인 추가 증거가 아니라 조건 1~7의 반복이다. 결과서에는 다음처럼 해석을 명확히 남긴다.

```text
CRITERION_8_PRIMARY = PIT가 주 평가이므로 독립 조건이 아님
FS_SENSITIVITY      = 기록용 보조검사
FS_RESULT           = 조건 5·6·7 실패, REJECT 방향 동일
```

### 4. POC4-02A 판정

`MEASURED`를 수용한다.

정확한 결론은 다음 범위까지만이다.

* 이 모델·146개 평가일·확정 가격 규칙에서 PIT−CONTROL 효과는 작고 음수
* IC와 top-decile 효과의 신뢰구간은 0을 포함
* 날짜별 방향도 일관되지 않음
* 생존편향을 줄였지만 제거하지는 못함
* 편향이 없다는 일반 결론이나 성과 우월성 주장은 불가

따라서 다음 토큰을 유지한다.

```text
KRX_POINT_IN_TIME_UNIVERSE_V1
REDUCED_NOT_ELIMINATED
RESEARCH_ONLY
UNBIASED_PERFORMANCE_CLAIM = NOT_YET
```

모델 자체가 PIT와 CONTROL 모두 음의 IC라는 사실은 생존편향 측정과 별개로 기록하되, 02A에서 모델 최종 판정을 내리지는 않는다.

### 5. manifest 두 파일

승인한다.

* `run_manifest.json`: 시작 시점의 재개 지문과 입력 계약
* `run_manifest_final.json`: 실제 분할·행 수·결과 hash·종료 시점 증거

역할이 다르므로 한 파일로 합칠 필요가 없다.

### 6. 검증 전 필수 문서 정정

코드나 연구 실행은 다시 돌리지 말고 문서만 고친다.

1. 02B 결과서 머리말:

```text
현재: 거짓 5·6·7 외
정정: 거짓 1·5·6·7·8·9·10
```

2. 02A 결과서 §5 번호가 `1·2·3·4·7·5·6` 순서이므로 `1~7` 순서로 정렬한다. 내용은 바꾸지 않는다.

### 7. 검증·커밋 범위

문서 정정 후 29개 staged 파일 전체를 한 검증 단위로 넘긴다.

검증자는 특히 다음을 확인한다.

* 봉인 reader의 관계식 불일치 0
* 운영 DB 직접 연결·쓰기 0
* 02A 두 공식 실행의 결정성 및 누수 통제
* 02B 조건표와 원시 결과의 일치
* legacy 재현 65개 값 `EXACT_MATCH`
* 잘린 사건 제외 전후 판정 불변
* 전체 회귀 2,134건
* 라이브 경로 전후 불변
* 신규 의존성·OCI·PUSH 변경 0

검증자 `VERIFIED` 전에는 커밋·push하지 않는다. 통과 후에는 현재 staged 29개를 함께 커밋·push한다. 사용자 소유 handoff와 git 밖의 사후 진단 파일은 포함하지 않는다.

그다음은 `POC4-03` 하나만 Track A의 최종 kill gate로 진행합니다. RF가 단순 모멘텀을 이기지 못하면 `POC4-04·05`는 열지 않고 Track A를 종료합니다. Track B는 이번 `REJECT`로 닫습니다.
