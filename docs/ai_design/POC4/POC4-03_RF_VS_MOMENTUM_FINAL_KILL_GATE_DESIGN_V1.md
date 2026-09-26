> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-09-25) · 기록: 개발자(VSCode Claude). 아래 `# POC4-03 설계 지시` 부터는 설계자 원문 그대로다.
> 같은 전달문 앞부분(POC3 문서 정리 판정)에 `POC4_03_PLAN_AUTHORIZED = YES` 가 있었다 — 문서 정리 판정 자체는 POC3 문서 커밋(`caacc42f` · `73be6948`)으로 처리했다.
> 선행 계약: `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md` Part D(§16 개방 조건 · §17 Kill Gate · §18 Track B 와 독립 판정).
> 개발 PLAN: `docs/ai_plan/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_PLAN_V1.md`
> **설계자 PLAN 판정(2026-09-25)** 원문은 이 문서 끝 `# 설계자 PLAN 판정` 절에 그대로 붙였다 — `PASS_WITH_MANDATORY_AMENDMENT`.
> 본문과 다른 곳은 판정이 우선한다(RF 선택 누수 제거 · 동률·결측 규칙 · CONTROL 조건부 실행 · 경계 동점 부분 가중 · Q1~Q17 확정 · 최종 kill gate).

# POC4-03 설계 지시

```text
STEP                      = POC4-03
NAME                      = RF_VS_MOMENTUM_FINAL_KILL_GATE
CURRENT_ACTION            = PLAN_ONLY
TRACK                     = A
POC4_04_05                = NOT_OPEN
OCI_PUSH_UI_API           = 0
NEW_DEPENDENCY            = 0
```

설계서 기록 경로:

```text
docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md
```

PLAN 제출 경로:

```text
docs/ai_plan/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_PLAN_V1.md
```

## 1. 목적

같은 데이터·feature·label·평가일·비용 조건에서 아래 세 가지를 공정하게 비교합니다.

1. 기존 선형 baseline
2. 단순 20일 모멘텀
3. RandomForest 최대 3설정

질문은 하나입니다.

> RandomForest가 단순 20일 모멘텀을 통계적·경제적으로 안정되게 이기는가?

기존 모델을 예쁘게 만드는 단계가 아닙니다. 못 이기면 Track A를 종료합니다.

## 2. 고정 입력

* 봉인 데이터: `krx_etf_universe_v1`
* reader: `app/krx_sealed_reader.py` 무수정
* 주 평가 universe: 날짜별 PIT
* 평가일: POC4-02A의 146일 그대로
* feature: 기존 7개 그대로
* 학습 label: `future_excess_return_20d`
* 평가 label: E2 `forward_excess`
* 분할: 날짜 기준, purge 20거래일
* 필터·가격 기준·제외 사유: POC4-02A 계약 그대로
* 현재 `etf_master`나 생존 DB로 결측 보충 금지
* 외부 네트워크·라이브 DB 연결 금지

POC4-02A 결과나 모듈을 바꾸지 않습니다. 새 비교 모듈과 러너로 분리합니다. 586줄인 02A 러너에는 코드를 추가하지 않습니다.

## 3. 비교 모델

### 선형 baseline

POC4-02A와 동일한 알고리즘·분할로 재현합니다. 지표가 POC4-02A와 맞지 않으면 RF 비교 전에 중단합니다.

### 단순 모멘텀

같은 평가일의 20일 수익률을 그대로 점수로 씁니다.

* 학습 없음
* 별도 threshold 없음
* 결과를 본 뒤 부호·정규화 방식 변경 금지

### RandomForest

* sklearn만 사용
* 최대 3개 설정
* XGBoost·LightGBM 금지
* 자동 탐색·grid search·Bayesian tuning 금지
* 공식 결과를 본 뒤 설정 추가·삭제·수정 금지
* exact 설정·seed·결측 처리·표준화 여부를 PLAN에서 먼저 동결

각 평가일의 RF 설정 선택은 해당 평가일보다 앞선 validation 구간만 사용합니다. validation IC 최고 설정을 선택하고, 동률 우선순위는 PLAN에서 고정합니다. test 결과는 설정 선택에 사용할 수 없습니다.

고정 설정 3개의 개별 결과와 validation으로 선택한 `RF_PRIMARY`를 모두 냅니다.

## 4. 평가 지표

주요 지표:

* 일자별 Spearman IC
* IC 평균·중앙값
* RF−모멘텀 paired IC 차이
* top-decile gross
* top-decile net 25bp
* turnover·win rate
* CAGR·MDD·Sharpe·상대 wealth·IR

비용:

```text
PRIMARY              = 편도 25bp top-decile net
STRATEGY_REFERENCE   = 편도 11.5bp
SENSITIVITY          = 편도 10bp · 50bp
```

통계:

* 기존 circular block bootstrap 재사용
* 6개월 블록
* 95% CI
* 고정 seed
* 최소 10,000회
* RF−모멘텀의 날짜별 paired 차이로 계산

## 5. 강건성

반드시 함께 냅니다.

* PIT 주 평가
* 최종 생존 CONTROL은 진단용
* 연도별 결과
* 전체 기간 3구간 결과
* 가장 유리한 한 해 제외
* 2026년 제외
* RF 고정 설정 3개의 개별 결과
* validation 선택 설정의 사용 빈도

RF의 우위가 한 해 또는 설정 하나에서만 나오면 통과가 아닙니다.

## 6. 판정

### PASS

다음을 모두 충족해야 합니다.

* RF_PRIMARY IC > 모멘텀 IC
* IC 개선 95% CI 하한 > 0
* RF_PRIMARY net 25bp > 모멘텀 net 25bp
* net 개선 95% CI 하한 > 0
* 고정 RF 설정 중 최소 2개가 IC와 net 모두 모멘텀보다 양의 방향
* 가장 유리한 한 해를 빼도 IC와 net 개선 방향 유지
* 기간 3구간 중 최소 2구간에서 IC와 net 개선 방향 유지
* PIT에서 우위가 유지됨
* 두 공식 실행 결과 동일
* 누수·입력 변경·사후 설정 변경 0건

### REJECT_CLOSED

다음 중 하나면 Track A를 종료합니다.

* RF IC가 모멘텀 이하
* RF net 25bp가 모멘텀 이하
* RF가 PIT에서 무너짐
* 특정 기간 또는 설정 하나에만 의존
* 유효한 비교에서 명백히 열위

### INCONCLUSIVE_CLOSED

점추정치는 좋지만 CI가 0을 포함하거나 IC와 비용 성과가 엇갈리면 `PASS`가 아닙니다. 추가 튜닝 없이 Track A를 닫습니다.

### INVALID_STOP

다음은 모델 REJECT가 아니라 실행 무효입니다.

* 선형 baseline 재현 실패
* 데이터·봉인 hash 불일치
* 누수 발견
* 결정성 실패
* 라이브 경로 변경
* 자원 상한 초과

계약 결함만 고치고 같은 사전 등록 설정으로 다시 실행합니다. 모델 설정을 바꾸면 안 됩니다.

## 7. 자원·실행 안전선

PLAN에서 공식 실행 전 smoke로 시간과 메모리를 추정합니다. smoke는 test 성과 판정에 쓰지 않습니다.

```text
MAX_RSS_HARD_LIMIT       = 10 GB
EXPECTED_RUN_HARD_LIMIT  = 4시간 / 1회
OFFICIAL_RUNS            = 처음부터 2회
RESUME_RUN               = 결정성 증거로 불인정
OUTPUT                    = 새 폴더만 · 덮어쓰기 금지
```

상한을 넘을 것으로 예상되면 공식 실행하지 말고 설정 규모와 예상치를 보고합니다. test 결과를 본 뒤 모델을 가볍게 만드는 방식은 금지합니다.

## 8. PLAN 필수 사실조사

PLAN 앞부분에 다음을 실측해 제출합니다.

1. 설치된 sklearn 실제 버전과 `requirements.txt` 일치 여부
2. 기존 선형 baseline 호출 경로와 고정 모듈 hash
3. 단순 20일 모멘텀의 정확한 입력 필드·부호·결측 처리
4. 02A의 146일·7 feature·label·분할을 그대로 재사용할 수 있는지
5. RF 3설정의 정확한 값과 선정 근거
6. validation 설정 선택 절차와 동률 규칙
7. 작은 train-only smoke의 시간·RSS
8. 공식 실행 예상 시간·RSS
9. 재사용 모듈과 신규 예상 파일·줄 수
10. 전체 `.py/.ts/.tsx` KS-10 측정
11. 라이브 5경로·봉인 DB 불변 검증 방법
12. focused test·전체 회귀·결정성 검증 범위

## 9. 금지 범위

* feature 추가·삭제
* label 변경
* 평가일 변경
* test 결과 기반 설정 선택
* XGBoost·LightGBM
* 신규 패키지 설치
* UI·API·OCI·PUSH 연결
* 기존 POC4-01·02 결과 덮어쓰기
* `app/krx_sealed_reader.py` 수정
* 커밋·push

PLAN이 승인되기 전에는 구현하지 않습니다. POC4-03이 PASS하더라도 POC4-04는 자동으로 열리지 않으며, 사용자 승인과 새 설계가 필요합니다.

---

# 설계자 PLAN 판정 (2026-09-25 · 설계자 원문 · 사용자 전달)

판정은 다음과 같습니다.

```text
POC3_DOCS_DECISION = ACCEPT
PUSH_ALLOWED       = caacc42f · 73be6948
VERIFIER_REQUIRED  = NO

POC4_03_PLAN_DECISION = PASS_WITH_MANDATORY_AMENDMENT
IMPLEMENTATION         = 아래 보완 반영 후 착수 가능
DESIGNER_RECHECK       = 보완이 불가능하거나 새 중단 조건이 생길 때만
```

## 1. POC3 문서

지정한 4건이 모두 의도대로 정정됐습니다. 코드 변경이 없으므로 별도 검증자 없이 다음 두 커밋을 push해도 됩니다.

```bash
git push origin main
```

대상은 `caacc42f`, `73be6948`입니다.

## 2. POC4-03 필수 보완

### A. RF 설정 선택의 누수 제거

* Q4: V의 모든 거래일별 IC 평균을 사용합니다.
* 검증 target은 `future_excess_return_20d`입니다.
* 모집단은 날짜별 이름 필터·7개 feature 완전성·검증 target 존재 조건으로 한정합니다.
* 공식 E2 `forward_excess`나 t 이후 정보가 설정 선택 경로로 들어가면 안 됩니다.
* Q17: RF 학습 S에서 `target_end_date >= V_start`인 행은 반드시 제외합니다.
* 제외 행 수를 날짜별로 기록합니다.
* 제외 때문에 모델 생성이 불가능하면 겹친 행을 되살리지 말고 `NO_MODEL` 또는 `INVALID_STOP`으로 처리합니다.

02A 선형 기록은 그대로 재현합니다. 누수 제거는 RF A/B/C에만 동일하게 적용합니다.

### B. 설정 동률·결측 규칙

Q5 추천안은 수정합니다.

```text
6자리 반올림 비교        = 사용하지 않음
비교                     = finite val_IC 원값
정확히 같을 때 우선순위   = A → B → C
일부 None                = 해당 설정 제외
전부 None                = A 선택 금지 · INVALID_STOP
```

검증 근거가 전혀 없는 날에 임의로 A를 선택하면 안 됩니다.

### C. CONTROL 실행은 PIT 통과 후보일 때만

불필요한 6~10시간 실행을 피합니다.

```text
1. PIT run1
2. PIT run2
3. 결정성 대조
4. PIT가 PASS 후보가 아니면 Track A 종료 — CONTROL 실행하지 않음
5. PIT가 PASS 후보이면 CONTROL run1·run2 실행
6. CONTROL은 진단만 하고 PIT 판정을 뒤집지 않음
```

CONTROL을 실행할 때는 축소하지 않고 선형·모멘텀·RF A/B/C·RF PRIMARY를 모두 같은 절차로 돌립니다.

### D. RF 점수 동점 처리

Q13의 가중 방식은 승인하지만 판정 지표에만 제한하지 않습니다.

* 경계 동점 종목을 모두 포함하고 필요한 비율만큼 동일한 부분 가중치를 줍니다.
* 이 가중 바스켓을 gross·net·비용 grid·turnover·CAGR·MDD 등 전략 성과 전체에 일관되게 사용합니다.
* 종목코드 순서로 자르는 기존 02A 값은 민감도 비교값으로만 병기합니다.
* 가중치는 점수와 목표 종목 수만으로 정하며 label을 사용하면 안 됩니다.
* RF_A 설정 자체는 바꾸지 않습니다.

## 3. Q1~Q17 확정

| 질문  | 확정                                                                       |
| --- | ------------------------------------------------------------------------ |
| Q1  | `return_20d`                                                             |
| Q2  | 여섯 모델 모두 `normalize_to_display_scores`                                   |
| Q3  | RF는 S로만 학습, S+V 재학습 금지                                                   |
| Q4  | 모든 V 거래일 평균. 위 필수 보완 A의 모집단 적용                                           |
| Q5  | 반올림 없음·원값 비교·전부 None이면 `INVALID_STOP`                                    |
| Q6  | CONTROL은 PIT PASS 후보일 때만 여섯 모델 전체 실행                                     |
| Q7  | 한 지표만 열위면 `INCONCLUSIVE_CLOSED`; C5~C7 실패는 `REJECT_CLOSED`; CONTROL은 진단만 |
| Q8  | 지표별 leave-one-year-out 최솟값 `> 0`                                         |
| Q9  | top-decile net 10·50bp, 기존 전략 시나리오는 유지                                   |
| Q10 | arm별 실행 승인. PIT 우선·CONTROL 조건부 실행                                        |
| Q11 | `perf_counter` 기반 4시간 강제 중단, UTC 시각 병기. 같은 설정으로 재시도 1회만 허용               |
| Q12 | `app/research_run_guard.py` 신규 작성, POC4-03에만 적용                          |
| Q13 | 경계 동점 부분 가중치를 모든 성과 산식에 일관 적용                                            |
| Q14 | 두 arm 292건 canonical 전체 일치                                               |
| Q15 | bootstrap 10,000회·seed 42·블록 6                                           |
| Q16 | RF_C 비율 그대로 유지. 결과 확인 후 변경 금지                                            |
| Q17 | 겹치는 S행 보고만 하지 말고 RF 학습에서 제외                                              |

4시간 초과 시 `INVALID_STOP(RESOURCE_LIMIT)`으로 멈추고 시스템 부하만 제거한 뒤 같은 설정으로 한 번 재실행합니다. 두 번째도 초과하면 설정을 가볍게 바꾸지 말고 중단 보고합니다.

## 4. 최종 kill gate

```text
PIT PASS             → CONTROL 진단 후 POC4-04 개방 판단
PIT REJECT           → POC4-04·05 미개방 · Track A 종료
PIT INCONCLUSIVE     → POC4-04·05 미개방 · Track A 종료
결정성/자원 INVALID  → 결과 판정 금지 · 지정된 1회 재실행만 허용
```

위 내용을 PLAN과 설계서 기록에 반영한 뒤 구현에 착수하십시오. 이 반영만으로는 설계자에게 다시 돌아올 필요가 없습니다. 새 데이터 소스·RF 설정 변경·성과 확인 후 기준 변경·4시간 재초과가 발생할 때만 중단 보고하면 됩니다.
