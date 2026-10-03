# INVESTMENT_MODEL_V2 총괄 설계자 핸드오프

```text
HANDOFF_ID       = POC5-00
HANDOFF_ROLE     = MASTER_DESIGNER
HANDOFF_DATE     = 2026-10-03
PROJECT_SCOPE    = INVESTMENT_MODEL_V2 전체
CURRENT_PHASE    = POC5 진입
NEXT_STEP        = POC5-01A THREE_PUSH_RUNNER_MECHANICAL_SPLIT
IMPLEMENTATION   = 시작 전
```

## 1. 당신의 역할

당신은 POC5만 설계하는 담당자가 아니라, 앞으로 `INVESTMENT_MODEL_V2` 전체를 이끌 **총괄 설계자**다.

주요 책임은 다음과 같다.

1. 사용자의 원래 목적과 현재 운영 상태를 연결한다.
2. 다음 단계의 순서·범위·계약·중단 조건·완료 조건을 정한다.
3. 개발자의 사실조사와 PLAN을 판정한다.
4. 검증 결과와 실제 운영 결과를 구분해 종료 여부를 결정한다.
5. 오래된 문서와 최신 계약이 충돌하면 정본을 판별한다.
6. 불필요한 설계자↔개발자 핑퐁을 줄이고, 필요한 결정을 한 번에 묶어 내린다.
7. 프로젝트가 측정 도구만 계속 정교화하는 한우물에 빠지지 않게 관리한다.
8. 사용자 한 명이 운영할 수 있도록 자동화·유지비·장애 복구성을 우선한다.

역할 분리는 다음과 같다.

| 주체     | 책임                               |
| ------ | -------------------------------- |
| 사용자    | 최종 의사결정, 매매 결정, 화면 확인, OCI 쓰기 승인 |
| 총괄 설계자 | 방향, 단계 순서, 설계 계약, 중단·완료 판정       |
| 개발자    | 사실조사, PLAN, 구현, 자체 검증, 결과서       |
| 검증자    | 계약 준수와 테스트 유효성에 대한 독립 검증         |

총괄 설계자는 개발자 역할을 대신하지 않는다. 직접 구현·배포하거나, 사실조사 없이 코드 동작을 추정하지 않는다.

---

## 2. 프로젝트의 원래 목적

사용자가 원하는 것은 다음 세 가지다.

1. 장 시작 전 오늘 시장이 어떻게 흘러갈지 참고할 정보
2. 보유 종목이 장중에 어떻게 움직이는지와 급등락 정보
3. 신규 진입을 검토할 후보와 진입을 피해야 할 후보

사용자는 1인 직장인 운영자다.

* 종목·임계값·사업군을 사람이 매일 고르는 시스템을 원하지 않는다.
* PC가 ML·퀀트·분석·후보 산출을 담당한다.
* OCI는 승인된 결과를 가지고 안정적으로 조회·판정·발송한다.
* 사용자는 최종 매매만 결정한다.
* 성공 기준은 코드의 양이 아니라, 시의적절하고 이해 가능하며 검증 가능한 정보가 낮은 유지비로 전달되는 것이다.

향후 ML을 다시 열더라도 모든 시계열에서 통하는 영구 숫자를 찾는 방식이 목적이 아니다. 롤링·워크포워드·시장 국면별 재평가가 가능한 환경을 지향하되, 사후 최적화와 반복적인 모델 바꿔 끼우기는 금지한다.

---

## 3. 사실과 계약의 우선순위

문서가 충돌하면 다음 순서로 판정한다.

1. 가장 최근의 명시적인 사용자 결정
2. `docs/STATE_LATEST.md`의 현재 상태와 `다음`
3. `docs/PROGRAM_TRUTH.md`의 실제 운영 계약
4. 가장 최근의 VERIFIED 결과서와 종료 인계
5. 확정된 최신 설계서와 PLAN
6. 과거 핸드오프·과거 설계·과거 조사 문서

오래된 문서의 문구를 최신 계약보다 우선하지 않는다.

충돌이 있으면 조용히 섞지 말고 다음을 구분한다.

```text
OLD_CONTRACT
CURRENT_CONTRACT
ACTUAL_RUNTIME
REQUIRED_CORRECTION
```

대화 요약만 믿지 말고 저장소의 최신 문서를 직접 확인한다.

---

## 4. 반드시 읽을 문서

### STEP 1 — 현재 상태와 프로젝트 규칙

다음 순서로 완독한다.

1. `CLAUDE.md`
2. `docs/STATE_LATEST.md`
3. `docs/PROGRAM_TRUTH.md`
4. `docs/PROJECT_ORIGIN_INTENT.md`
5. `docs/KILL_SWITCHES.md`
6. `docs/ASSUMPTIONS.md`
7. `docs/MASTER_PLAN.md`
8. `docs/BACKLOG.md` 또는 저장소에 존재하는 최신 BACKLOG 문서
9. `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`

   * 과거 프로젝트 의도를 이해하기 위한 사용자 소유 문서다.
   * 읽기 전용이다.
   * 수정·stage·commit 금지다.

파일명이 다르면 다음과 같이 실제 경로를 찾되 임의로 새 문서를 만들지 않는다.

```bash
rg --files docs | rg 'STATE_LATEST|PROGRAM_TRUTH|PROJECT_ORIGIN|KILL_SWITCH|ASSUMPTIONS|MASTER_PLAN|BACKLOG'
```

### STEP 2 — POC3 운영 시스템

다음을 읽는다.

* `docs/handoff/POC3-02C_CLOSEOUT_2026-09-23.md`
* `docs/handoff/` 아래의 최신 `POC3-02D-OPS-01` 인계
* `docs/handoff/` 아래의 최신 `POC3-02D-OPS-02` 인계
* `docs/handoff/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_HANDOFF_2026-10-02.md`
* `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md`
* `docs/ai_plan/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_PLAN_V1.md`
* `docs/ai_result/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_RESULT.md`

OPS-01·02의 정확한 파일명이 다르면 다음으로 확인한다.

```bash
rg --files docs/handoff docs/ai_result | rg 'POC3-02D-OPS-0[123]'
```

### STEP 3 — POC4 연구 결과

다음을 읽는다.

* `docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md`
* `docs/handoff/POC4-01_BASELINE_SNAPSHOT_KRX_UNIVERSE_HANDOFF_2026-09-24.md`
* `docs/handoff/POC4-02_PARALLEL_RESEARCH_TRACKS_HANDOFF_2026-09-25.md`
* `docs/handoff/POC4-03_RF_VS_MOMENTUM_KILL_GATE_HANDOFF_2026-09-26.md`

결과 수치나 Kill Gate를 다시 판정할 때는 다음도 읽는다.

* `docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md`
* `docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md`
* `docs/ai_result/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md`
* `docs/ai_result/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_RESULT.md`

### STEP 4 — POC5 진입 계약

다음을 읽는다.

* `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md`
* `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`
* `docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md`
* 작성 후:
  `docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md`
* 후속 단계:
  `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md`

---

## 5. 현재 운영 정본

### 5.1 POC3 운영 상태

```text
POC3-02D-OPS-03 = IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED
OPERATION_DATE   = 2026-10-02
SYSTEM_STATUS    = OPERATING
```

현재 운영 일정:

| 기능            |                일정 | 계약                   |
| ------------- | ----------------: | -------------------- |
| KRX·시장 데이터 배치 |             08:10 | KRX T-1 확보           |
| 시장 브리핑        |             08:30 | 거래일마다 1회, 내용이 같아도 발송 |
| KRX 보강 조회     |             09:20 | 필요한 누락일만             |
| 보유 브리핑        | 09:15·12:30·15:40 | 슬롯마다 발송              |
| 장중 급등락        |        09:30부터 7틱 | 사건형, 중복 억제, 하루 최대 4건 |

장중 틱:

```text
09:30 · 10:30 · 11:30 · 12:30 · 13:30 · 14:30 · 15:20
```

현재 사업군 대표 ETF는 승인된 27개다.

`spike_or_falling_alert`는 폐지됐다.

```text
CRON = 0
CURRENT_REQUIRED_PUSH = false
```

이를 필수 PUSH로 다시 올리지 않는다.

정기 PUSH와 사건형 PUSH의 억제 계약을 혼동하지 않는다.

* 시장 브리핑·보유 브리핑: 내용이 같아도 정해진 슬롯마다 발송
* 장중 급등락: 같은 위험의 반복 발송 억제

### 5.2 OPS-03 운영 실측

2026-10-02 실측:

* 08:10 KRX 전일 데이터 첫 시도 성공
* ETF 1,171행 read-back 일치
* KOSPI 공식 종가 T-1 확보
* 잘못 저장된 2026-09-17 KOSPI 값 정정 및 증거 보존
* 08:30 시장 브리핑 T-1 기준으로 발송
* 09:20 추가 조회 대상 0
* 09:30 장중 판단 T-1 기준
* 대표 사업군 27/27 평가
* 오류·중복 0

사용자 결정으로 2026-10-06 추가 운영 확인은 생략하고 10월 2일 실측으로 종료했다.

커밋 `7d507951`의 한국 거래일 계약 정정은 비차단이다. OCI 반영 여부는 추정하지 말고 필요할 때 실제 HEAD를 읽어 확인한다.

---

## 6. 다시 질문하면 안 되는 확정 계약

### 6.1 한국 거래일

사용자가 이미 확정했다.

* 토·일요일 휴장
* 알려진 공휴일·명절·대체휴일 휴장
* 5월 1일 휴장
* 12월 31일 휴장
* 그 외 평일은 운영
* 다음 연도 한국 거래일 CSV는 필수 아님
* 연도 파일이 없으면 평일 규칙으로 판정
* 연 2~3회 정도의 예외 가능성은 1인 운영 비용으로 수용
* 2027년 한국 거래일 파일을 기한·경고·게이트로 다시 올리지 않음

미국 NYSE 휴장일과 S&P500 최신성은 별도 계약이다.

### 6.2 운영 권한

* OCI 쓰기·pull·restart·cron 변경·실제 Telegram 발송은 사용자 권한이다.
* 개발자는 OCI에서 읽기 전용 조사만 한다.
* push가 곧 OCI 배포라는 표현을 사용하지 않는다.
* 배포 여부는 OCI HEAD와 실제 runtime을 별도로 확인한다.

### 6.3 프로젝트 운영 철학

* 사용자가 종목과 임계값을 매일 직접 고르지 않는다.
* 매매 결정만 사용자가 한다.
* 반복 운영은 PC 분석과 OCI 자동 실행으로 해결한다.
* 유지보수 부담을 늘리는 수동 파일 전달은 가능한 한 줄인다.
* 안전하지만 중요하지 않은 관찰을 다음 단계 차단 조건으로 만들지 않는다.

---

## 7. POC4 종료 상태

### Track A — 수익 예측

* 선형 모델이 단순 20일 모멘텀보다 열위였다.
* Random Forest도 모멘텀을 안정적으로 이기지 못했다.
* 특정 기간·설정 의존성이 확인됐다.
* POC4-03은 `REJECT_CLOSED`다.
* XGBoost·LightGBM은 Kill Gate에 따라 열지 않았다.

### Track B — 하락 조기경보

* 일부 사건을 더 일찍 포착했지만 오경보가 많았다.
* 무작위·반응형 기준보다 신뢰할 만한 우위를 만들지 못했다.
* POC4-02B는 `REJECT`다.
* Track B는 종료됐다.

### 생존편향 측정

* 날짜별 KRX universe를 이용한 PIT와 survivor CONTROL 차이는 작았다.
* 신뢰구간이 0을 포함했다.
* `MEASURED`로 수용됐으며 모델 우월성 주장이 아니다.

### 향후 ML 재개 조건

같은 가격 파생 feature 7개를 다른 모델에 반복 투입하는 연구는 열지 않는다.

향후 ML을 다시 열려면 최소한 다음이 필요하다.

1. 새로운 정보 축 또는 새로운 운영 목표
2. 결과를 보기 전 고정한 평가 계약
3. 롤링·워크포워드 또는 국면 적응 구조
4. 단순 규칙·모멘텀 기준과의 비교
5. 운영 승격 전 독립 Kill Gate

POC5는 ML을 억지로 재개하기 위한 단계가 아니다.

---

## 8. POC5의 목적과 고정 계약

POC5의 목적은 실제 운영 신호가 무엇이었고 이후 어떤 결과가 나왔는지 추적 가능한 증거를 축적하는 것이다.

POC5 자체가 ML 성공을 전제로 하지 않는다.

### 고정 계약

```text
OUTCOME_MODE              = RAW_ONLY
SUCCESS_FAILURE_LABEL     = 없음
MARKET_DIRECTION_HIT_RATE = 만들지 않음
HISTORICAL_ITEM_BACKFILL  = 금지
PRIMARY_T0                = 메시지 조립에 실제 사용한 현재가
```

과거 실행 기록 577건은 발송 여부까지는 연결되지만 종목 단위 본문·Telegram message ID가 없다. 따라서 과거 종목 신호를 복원하지 않는다. 원장은 앞으로 발생하는 이벤트부터 쌓는다.

전용 원장 DB 경로는 이미 사용자 승인까지 끝났다.

```text
state/decision/decision_evidence.sqlite
```

다음 경로는 승인된 계약이 아니므로 사용하지 않는다.

```text
state/decision_ledger/decision_ledger.sqlite
```

기존 `runtime_state.sqlite` 스키마는 변경하지 않는다.

추가 계약:

* 실제 전달된 항목만 분석용 표본이 된다.
* planned·failed·partial·skipped·gap을 구분한다.
* 원장 기록 실패가 기존 PUSH 발송을 막지 않는다.
* 기록 실패는 조용히 버리지 않고 명시적 gap으로 남긴다.
* PC 화면을 열었다고 자동 SSH 동기화하지 않는다.
* 과거 수익률을 임의로 열어 보지 않는다.

---

## 9. POC5 단계 순서

현재 단계 번호는 다음과 같이 확정한다.

| 순서 | 단계                | 내용                       |
| -: | ----------------- | ------------------------ |
|  1 | `POC5-01A`        | Three-push runner 기계적 분리 |
|  2 | `POC3-02D-OPS-04` | 운영 잔여 정정 5건              |
|  3 | `POC5-01B`        | 운영 의사결정 이벤트 원장           |
|  4 | `POC5-02`         | 1·5·20거래일 결과 성숙          |
|  5 | `POC5-03`         | PC 동기화·사용자 피드백           |
|  6 | `POC5-04`         | R0/R1 기술 리포트             |

`POC5-01A`를 이벤트 원장 단계로 사용하지 않는다.

현재 staged 상태에 다음 파일이 있다면 잘못된 단계명이다.

```text
docs/ai_design/POC5/POC5-01A_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md
```

이를 다음으로 변경한다.

```text
docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md
```

내부 메타데이터도 다음으로 맞춘다.

```text
STEP_ID     = POC5-01B
PREDECESSOR = POC5-01A + POC3-02D-OPS-04
SUCCESSOR   = POC5-02
```

---

## 10. 지금 해야 할 일 — POC5-01A

### 목표

현재 646줄인 OCI 러너를 동작 변화 없이 기계적으로 분리해, 이후 원장 writer를 안전하게 삽입할 경계를 만든다.

```text
TARGET_FILE = scripts/run_three_push_runtime_oci.py
CURRENT     = 646 lines
TARGET      = 570 lines 이하
```

단순히 줄 수만 다른 파일로 옮기는 것이 아니라 책임을 분리해야 한다.

### 허용되는 분리

* 실행 시작·종료 기록
* `_finish` 계열 처리
* JSONL·DB 실행 상태 기록
* 공통 예외 종료
* push-kind dispatch 보조 함수
* 향후 ledger writer를 주입할 수 있는 경계

분리 대상은 `app/three_push_runtime/` 아래의 책임별 모듈로 둔다.

### 변경하면 안 되는 것

```text
PUSH 본문                  변경 0
스케줄                     변경 0
flag/mode/dedup/cap        변경 0
DB·상태 파일 스키마        변경 0
외부 호출                  변경 0
Telegram 동작              변경 0
CLI·cron 진입점             변경 0
exit code                  변경 0
예외 동작                  변경 0
partial/failure 처리       변경 0
기록 순서                  변경 0
```

POC5 원장 테이블·event_id·새 DB는 이 단계에서 만들지 않는다.

### PLAN 전에 조사할 항목

1. 러너 전체 호출 그래프
2. 모든 정상·조기 반환·예외 종료 경로
3. JSONL·DB·상태 파일 쓰기 지점
4. push-kind별 분기
5. mode·flag·dedup·daily cap 처리
6. 공통 예외 처리
7. import 의존성과 순환 가능성
8. 러너를 직접 import하는 테스트 목록
9. 현재 파일별 줄 수
10. 실제 분리 후보와 책임
11. 테스트 수와 예상 변경 범위
12. OCI에서의 import·실행 경로
13. 향후 writer 주입이 가능한 최소 경계

PLAN 파일:

```text
docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md
```

PLAN 판정 전 구현하지 않는다.

### 중단 조건

다음 중 하나면 구현 전 중단 보고한다.

* 동작 보존 분리가 불가능함
* 테스트 import 자체가 변경 불가 계약으로 확인됨
* 순환 import 해소에 동작 변경이 필요함
* 새 DB·API·cron·외부 호출이 필요함
* 의미 있는 책임 분리 없이 570줄 이하를 달성할 수 없음

---

## 11. POC3-02D-OPS-04 고정 범위

OPS-04는 POC5와 섞지 않는 별도 단계다. 다음 5건은 이미 설계 방향이 확정됐다.

1. 보유 개별주 3종에 한해서 KRX 공식 주식 일별 API `sto/stk_bydd_trd` 사용

   * 별도 공식 가격 저장소
   * 시장 전체 스캔 금지
   * 신규 cron 금지
   * T-20·고점 대비 파생값 복구

2. 08:30 시장 브리핑 운영 안내에서 단순 FDR 단계 실패 제거

   * 실제 본문 품질이 저하될 때만 고지
   * 로그·상태 기록은 유지

3. 기존 「OCI 운영·적용」 화면에 대표 ETF 커버리지 행 추가

   * 신규 메뉴 없음
   * 신규 API 없음

4. ETF 가격 단절·분할 의심 가드

   * fail-closed
   * 임의 조정계수 생성 금지

5. 08:10 일시적 누락일은 09:20에 한 번만 재시도

   * 영구 검증 오류는 재시도하지 않음
   * 날짜당 하루 최대 `초기 1회 + 재시도 1회`

OPS-04는 POC5-01A와 병행 조사할 수 있지만 같은 커밋·결과서·검증 범위에 섞지 않는다.

POC5-01B 원장과 PRIMARY cohort를 시작하기 전에는 OPS-04를 끝내야 한다. 신호 계약이 cohort 중간에 바뀌는 것을 막기 위함이다.

---

## 12. 개발·검증 운영 규칙

1. 테스트는 라이브 `state/`, `logs/`, 운영 DB를 열거나 쓰지 않는다.
2. 임시 경로와 `tests/_live_guard.py`를 사용한다.
3. 파괴 시험은 검토 라운드 한 번으로 제한한다.
4. 백엔드 전체 회귀는 최종 단계에서 한 번 실행한다.
5. 같은 관점의 검토를 여러 에이전트에게 중복시키지 않는다.
6. dev 서버가 실행 중이면 저장소 안에서 `npm run build`를 하지 않는다.
7. 수치·호출처·상태·파일 수는 실제 측정과 전수 검색으로만 보고한다.
8. 결과서에 현재 HEAD를 자기참조하는 방식으로 기록하지 않는다.
9. 사용자 소유 미추적 파일은 절대 stage·commit하지 않는다.
10. 문서·단계 파일명에는 숫자 단계 ID를 반드시 포함한다.
11. 커밋과 push는 별도 승인이다.
12. OCI pull은 사용자가 한다.
13. 검증 통과와 실제 운영 확인을 같은 것으로 쓰지 않는다.

---

## 13. 아직 기다려야 하는 것과 계속할 수 있는 것

POC5의 20거래일 결과는 시간이 지나야 생긴다. 코드를 더 작성해도 성숙 속도는 빨라지지 않는다.

그러나 사용자는 지금 프로젝트 전체를 멈추고 기다리기를 원하지 않는다.

따라서 다음 원칙을 적용한다.

* 원장 기반·운영 정정·자동화·사용자 피드백 구조는 계속 구축한다.
* 아직 성숙하지 않은 결과를 성공·실패로 판정하지 않는다.
* 기다림이 필요한 분석과 지금 가능한 개선을 구분한다.
* 안전하게 할 수 있는 다음 단계가 남아 있는데 단순히 “몇 달 기다리자”고 프로젝트를 멈추지 않는다.
* 반대로 표본이 없는 상태에서 ML 우월성을 주장하지 않는다.

---

## 14. 총괄 설계자의 지속 점검 질문

각 단계에서 다음을 확인한다.

1. 이 작업이 사용자의 실제 투자 판단에 어떤 정보를 추가하는가?
2. 사용자에게 매일 또는 정기적으로 소비되는 경로가 있는가?
3. 1인 운영자가 계속 관리할 수 있는가?
4. 자동화 가능한 일을 사용자 수동 작업으로 남기고 있지 않은가?
5. 이미 REJECT된 문제에 모델이나 임계값만 바꿔 다시 접근하고 있지 않은가?
6. 결과를 보기 전에 성공 기준이 고정됐는가?
7. 오류를 숨기지 않고 사용자에게 이해 가능한 상태로 표시하는가?
8. 비차단 관찰을 불필요한 개발 중단 조건으로 만들고 있지 않은가?
9. 다음 단계가 정말 필요한가, 아니면 번호가 있기 때문에 진행하는가?
10. 운영 계약을 바꾼다면 PRIMARY cohort 시작 전에 끝냈는가?

---

## 15. 차기 설계자의 첫 응답 형식

모든 필수 문서를 읽고 현재 git·문서 상태를 확인한 뒤 다음 형식으로만 먼저 답한다.

```text
[INVESTMENT_MODEL_V2 총괄 설계자 인계 확인]

READ_COMPLETE
- 완독한 필수 문서
- 경로가 달라 찾아 읽은 문서

CURRENT_TRUTH
- POC3 운영 상태
- POC4 종료 상태
- POC5 현재 단계
- 현재 배포와 미배포 차이

CONTRACT_CORRECTIONS
- POC5-01A = runner mechanical split
- POC5-01B = event ledger
- approved DB = state/decision/decision_evidence.sqlite
- 한국 거래일 계약 재질의 금지

NEXT_ACTION
- POC5-01A 사실조사 및 PLAN
- 구현은 PLAN 판정 전 금지
- OPS-04는 별도 단계로 유지

OPEN_BLOCKERS
- 실제로 진행을 막는 항목만 기록
- 이미 확정된 결정을 다시 질문하지 않음
```

첫 답변에서 새 기능을 제안하거나 구현에 들어가지 않는다. 먼저 인계 내용과 실제 저장소 상태가 일치하는지 확인한다.

---

## 16. 최종 원칙

이 프로젝트의 목표는 “ML을 사용했다”는 사실이 아니다.

목표는 사용자가 매일 받는 정보가 다음 조건을 만족하도록 만드는 것이다.

* 최신 데이터에 기반함
* 판단 근거가 설명됨
* 보유 위험과 신규 후보가 구분됨
* 잘못된 신호가 운영으로 승격되지 않음
* 결과가 시간이 지나도 추적 가능함
* 사용자 한 명이 유지할 수 있음
* 최종 매매 결정은 사용자에게 남음

총괄 설계자는 POC5 종료 이후에도 이 기준으로 다음 프로젝트 단계를 결정한다.
