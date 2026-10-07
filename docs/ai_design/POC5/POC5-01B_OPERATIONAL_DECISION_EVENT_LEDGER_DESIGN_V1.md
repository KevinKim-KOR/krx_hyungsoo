> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-10-06) · 기록: 개발자(VSCode Claude). 아래는 설계자가 새로 쓴 POC5-01B 설계서 원문이다.
> 같은 경로의 이전 판(2026-10-02 전달 · `# POC5-01B 설계 지시` STEP 1 ~ 13 · POC5-01A 에서 옮긴 판)은 이 판으로 **교체**했다 — 이전 판 원문은 커밋 `a0a2c514` 에 있다.
> 상위 설계: `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` · PLAN `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`(Q1 ~ Q30 확정 · 다시 묻지 않는다).
> 이 단계 PLAN: `docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md`.

# POC5-01B — 운영 의사결정 이벤트 원장 DESIGN V1

```text
STEP_ID          = POC5-01B
PREDECESSOR      = POC5-01A + POC3-02D-OPS-04
SUCCESSOR        = POC5-02
PURPOSE          = 운영 PUSH가 무엇을 판단·전달했는지 앞으로 발생하는 실행부터 보존
OUTCOME_POLICY   = RAW_ONLY
IMPLEMENTATION   = PLAN 판정 뒤 로컬 진행 가능
OCI_DEPLOY_GATE  = OPS-04 첫 거래일 확인·종료
```

## 1. 이번 단계의 완료 모습

OCI의 세 운영 PUSH가 실행되면 전용 SQLite에 다음이 남는다.

1. 실행 진입부터 종료까지의 상태
2. 판단 과정에서 이미 계산된 종목·사업군·시장 항목
3. 실제 전달 결과와 분할 전 메시지 전문·SHA-256
4. 기록이 끝나지 않은 실행을 찾을 수 있는 gap

이 단계는 수익률을 계산하거나 신호의 성공·실패를 판정하지 않는다.

## 2. 범위

### 포함

- OCI 전용 `state/decision/decision_evidence.sqlite`
- `market_briefing`, `holdings_briefing`, `holdings_risk_alert` 세 종류
- 실행 진입 `event_id`와 `STARTED` 기록
- 최외곽 종료 확정과 미포착 예외 기록
- flow 반환값의 additive 기록 payload
- 이미 계산된 비선정·억제·상한 잘림 항목
- kind별 계약 버전 상수
- 원장·기존 runtime 기록·gap 대조 기능
- 기존 문서의 낡은 Decision Outcome Ledger 선행조건 정정과 KS-11 변경 근거

### 제외

- 1·5·20거래일 결과 계산(POC5-02)
- PC 동기화·화면·사용자 피드백(POC5-03)
- R0/R1 통계(POC5-04)
- 과거 종목 신호 복원·성과 backfill
- PUSH 문구·시간·임계값·억제·상한 변경
- 신규 공개 API·cron·외부 호출·의존성
- `runtime_state.sqlite` 스키마 변경
- 폐지된 `spike_or_falling_alert`

미래 단계의 빈 테이블을 미리 만들지 않는다. 01B에는 run·item·delivery·meta만 둔다.

## 3. 바뀌면 안 되는 계약

- 기존 PUSH 본문 byte, 판정, 호출 순서, 발송 횟수, 상태 파일, DB·JSONL 기록을 유지한다.
- 원장 기록 실패는 PUSH 성공·실패를 바꾸지 않는다.
- 기존 예외의 종류·메시지·전파·exit code를 유지한다.
- 원장 쓰기는 기본 비활성이다. OCI 역할이 확인되고 `mode=send`일 때만 활성화한다.
- 기존 OCI 역할 표식이 있으면 재사용하고, 없을 때만 전용 환경 플래그 하나를 둔다. hostname 추정은 금지한다.
- PC 실행과 dry-run은 원장에 쓰지 않는다. 수동 send는 기록하되 `off_schedule=true`이며 PRIMARY 통계 대상이 아니다.
- 테스트는 임시 DB와 Telegram stub만 사용한다. live `state/`, `logs/`, 운영 DB, 외부 API를 열지 않는다.

## 4. 최소 저장 계약

정확한 SQLite 테이블·컬럼명은 PLAN에서 확정하되 논리 구조는 아래 네 가지로 고정한다.

| 기록 | 필수 내용 |
|---|---|
| run | `event_id`, `STARTED/FINALIZED`, push kind, contract version, slot/tick, KST 실행일시, 입력 기준일, status/reason/error, started/finished, runtime `run_id`, PARAM/config ID, off-schedule, cohort, 시장 태그 |
| item | `(event_id, item_seq)`, subject 종류·ID, held 여부, state·이전 state, disposition, event type, PRIMARY/SECONDARY, 당시 계산값, 실제 사용 현재가와 시각(있는 경우) |
| delivery | `event_id`, sent/skipped/failed/partial, Telegram 전달 여부, chunk 수, 분할 전 본문, SHA-256 |
| meta | schema version, PRIMARY 시작일, 배포 근거 커밋, kind별 contract version |

- run·item·delivery는 당시 스냅샷이다. POC5-02가 이를 수정하지 않는다.
- run은 `STARTED` 생성 후 종료 확정 1회만 허용한다.
- item·delivery는 한 번의 짧은 트랜잭션으로 넣고 run을 종료 확정한다.
- WAL·busy timeout을 사용하되 재시도 큐·daemon·별도 서비스는 만들지 않는다.
- DB와 디렉터리 접근 권한은 OCI 로컬 운영 사용자로 제한한다.

## 5. 실행 흐름

1. 원장 활성 조건을 확인한다. 비활성이면 현재 경로를 그대로 실행한다.
2. 실행 진입 시 `event_id`를 만들고 run `STARTED`를 best-effort로 INSERT한다.
3. 기존 조립·가드·발송·상태 저장을 순서 변경 없이 실행한다.
4. `KindAssembly`와 각 flow 결과에 기록 payload만 추가한다. 추가 조회·재계산은 금지한다.
5. 가장 바깥 경계에서 item·delivery를 기록하고 run 종료를 확정한다.
6. 기존 미포착 예외도 원장에는 `failed`로 확정 시도한 뒤 같은 예외를 다시 올린다.

초기 INSERT 실패는 구조화 오류 로그를 남기고 PUSH를 계속한다. 종료 기록 실패로 `STARTED`가 남으면 그것이 gap이다. 별도 복구 작업을 자동 실행하지 않는다.

## 6. 항목 분류

`disposition`은 최소한 다음을 구분한다.

```text
sent / suppressed / cut_by_section_cap / cut_by_daily_cap /
not_selected / data_unavailable
```

- 보유 브리핑: 이번 실행에서 이미 평가한 전 보유 종목을 기록한다.
- 장중 알림: 이미 평가한 전 보유 종목과 27개 사업군을 기록한다.
- 시장 브리핑: S&P500 상태·태그와 실제 선택된 기초지수 그룹·ticker를 기록한다.
- 실제 전달된 항목만 전달 효과 표본이다. 억제·잘림·비선정은 관측 모집단에는 남긴다.
- 추가 조회나 사후 재계산으로 빈 필드를 채우지 않는다.

상태 전이는 같은 `(push_kind, subject)`의 직전 평가와 비교한다.

- 첫 활성 상태: `new_entry / PRIMARY`
- 같은 활성 상태 반복: `repeat_exposure / SECONDARY`
- 같은 방향 계열에서 더 강한 구간: `worsened / PRIMARY`
- 비활성 관측 뒤 다시 활성: `reentry_after_recovery / PRIMARY`
- 비교 불가능한 상태 변경: 새 상태의 `new_entry / PRIMARY`
- 비선정·자료없음·시장 관찰처럼 전이가 적용되지 않으면 event type과 exposure는 비워 둔다.

구간 강도와 비활성 판정의 실제 코드 매핑은 PLAN에 표로 제시한다. 새 투자 의미를 만들면 안 된다.

## 7. 기록 실패와 대조

- writer의 시작·item·delivery·종료 각 실패는 기존 로거에 `event_id`, 단계, kind, 예외 종류만 남긴다. 본문·비밀값은 로그에 쓰지 않는다.
- 읽기 전용 대조는 원장 run, 기존 `runtime_execution_status`, 원장의 `STARTED` 잔류를 비교한다.
- 대조 결과는 누락·gap·고아 행의 ID와 건수만 보여 준다. 자동 수정·재발송·backfill은 하지 않는다.
- 최초 쓰기 자체가 실패한 실행은 기존 runtime 행과 구조화 오류 로그로 식별한다.

## 8. 수용 기준

1. 원장 비활성 시 현행 동작과 기록이 완전히 같다.
2. 원장 활성 시에도 본문 byte·판정·발송 순서·기존 DB/JSONL 내용이 같다.
3. 세 운영 kind만 기록되고 spike·dry-run·PC 실행은 0건이다.
4. 정상·skip·no-signal·중복·부분 전송·발송 실패가 각각 정확히 종료된다.
5. 조립 예외, 발송 뒤 `mark_sent` 예외, 기존 `insert_status` 예외도 원장 failed 또는 명시적 gap으로 보인다.
6. 원장 INSERT·UPDATE 실패를 각각 주입해도 기존 PUSH 결과와 예외 전파가 같다.
7. 비선정·억제·잘림을 추가 조회 없이 기록한다.
8. 분할 전 본문과 SHA-256이 일치하고 비밀값이 없다.
9. 대조 기능이 누락·STARTED gap·정상 실행을 구분한다.
10. 임시 DB 계약 테스트, 기존 러너 회귀, 마지막 전체 회귀, KS-10 검사를 통과한다.

## 9. 개발 PLAN에 필요한 조사

PLAN은 새 설계를 만들지 말고 아래 사실과 구현 위치만 짧게 제시한다.

1. `a308353c` 기준 `new_run_record`, `KindAssembly`, `finish_run`, 최외곽 예외 경계
2. OCI 역할 표식 재사용 가능 여부와 기본 비활성 방식
3. kind별 기존 계산 결과에서 바로 꺼낼 수 있는 item 필드·disposition 매핑
4. 상태 구간 강도·회복 관측 매핑
5. Telegram chunk·partial과 분할 전 본문이 확정되는 위치
6. 실제 테이블·인덱스·짧은 트랜잭션 경계
7. PRIMARY 첫날·배포 커밋을 meta에 한 번 기록하는 최소 방법
8. 변경 파일·테스트·현재 전 파일 KS-10 실측

POC5-00의 Q1~Q30을 다시 질문하지 않는다. 실제 코드와 충돌하는 항목만 추천안과 함께 설계자에게 올린다.

## 10. 진행·중단 기준

- OPS-04 운영 확인을 기다리지 않고 DESIGN·PLAN·로컬 구현·검증을 진행할 수 있다.
- OCI 배포는 OPS-04가 첫 거래일 확인으로 종료된 뒤에만 한다.
- 추가 외부 조회가 필요하거나, 원장 때문에 PUSH 순서·본문·판정이 달라지거나, 승인 경로와 다른 DB가 필요하면 구현 전에 중단 보고한다.
- 이 단계 완료는 검증자 VERIFIED와 설계자 RESULT 판정 뒤 OCI 배포, 첫 거래일 원장·기존 실행 기록 대조까지다.

---

## 설계자 전달문 (2026-10-06 · 사용자 전달 원문)

```text
POC5-01B 개발 PLAN 작성 요청

설계서:
docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md

- 기준 커밋: a308353c
- 설계서 §9의 8개 항목을 실제 코드에서 조사해 짧은 PLAN 작성
- POC5-00 Q1~Q30 재질문 금지
- PLAN 판정 전 구현 금지
- OPS-04 운영 확인을 기다릴 필요는 없음
- 단, POC5-01B OCI 배포는 OPS-04 종료 뒤
- PLAN 작성 후 경로와 실제 충돌 질문만 보고
```

> 이번 설계에는 결과 계산·PC 화면·사용자 피드백을 넣지 않았습니다. 재시도 서비스나 별도 daemon도 만들지 않습니다. **실행·판단 항목·전달 사실을 SQLite에 남기는 데까지만** 범위를 잘랐습니다.

---

## 설계자 PLAN 판정 (2026-10-06 · 사용자 전달 원문)

판정은 **조건부 통과**입니다. 재제출 없이 아래 보정만 반영하고 구현을 시작하면 됩니다.

```text
PLAN_DECISION     = PASS_WITH_MANDATORY_AMENDMENTS
IMPLEMENTATION    = AUTHORIZED
PLAN_RESUBMISSION = NOT_REQUIRED
OPS-04_WAIT       = 구현에는 불필요
OCI_DEPLOYMENT    = OPS-04 종료 뒤
```

### Q-A~Q-H 판정

| 질문 | 판정 |
|---|---|
| Q-A | 추천안 승인. 예정 시각 기준으로 판정하되, cron이 1분 이상 지연되면 off-schedule로 잡힐 수 있다는 한계만 기록 |
| Q-B | 승인. 이미 계산된 값을 기본값 있는 필드로 운반하는 것은 추가 조회·재계산이 아님 |
| Q-C | 승인. 원장 자기 행 조회는 금지한 외부 추가 조회가 아님. 첫날 `new_entry/PRIMARY` 허용 |
| Q-D | 추천안 승인. `event_type`은 실제 전이, `exposure`는 같은 날 중복 방지 규칙을 각각 적용 |
| Q-E | 조건부 승인. 실제 발송 chunk 수가 아니므로 컬럼명을 `planned_chunk_count`로 변경 |
| Q-F | 조건부 승인. 거래일 배포는 **15:45 이후**로 변경. `git rev-parse` 실패 시 `unknown`을 영구 저장하지 말고 키를 비워 다음 실행에서 다시 시도 |
| Q-G | 승인. `KILL_SWITCHES`와 `ASSUMPTIONS`에 변경 근거 기록 |
| Q-H | 한국 시장 휴장 기준으로 확정. 태그명은 의미가 분명한 `after_kr_market_closure` 사용. 미국 휴장 영향은 `same_us_session`이 담당 |

### 필수 보정

1. 권한을 0700/0600으로 만들거나 확인하지 못하면 그 실행의 원장 쓰기를 중단하고 오류만 기록합니다. 민감한 본문을 느슨한 권한으로 저장하면 안 됩니다. PUSH는 계속합니다.
2. `chunk_count`는 `planned_chunk_count`로 바꿉니다. 실제 전달 chunk 수는 알 수 없다고 명시합니다.
3. 배포 가능 시각을 거래일 **15:45 이후** 또는 비거래일로 고칩니다.
4. 과거 POC2 인계 문서 두 개는 수정하지 않습니다. 현재 정본인 `MASTER_PLAN`, POC3 지도, `STATE_LATEST`, `PROGRAM_TRUTH`, `KILL_SWITCHES`, `ASSUMPTIONS`만 정정합니다.
5. 줄 수 598과 600을 맞추려고 코드를 비틀지 않습니다. 구현 후 600~649면 `NEAR` 기록만 하고 계속하며, 650 이상일 때만 중단합니다.

271줄은 이번에는 허용합니다. 대부분 실제 코드 조사와 검증표이며, 불필요한 것은 과거 인계 문서 수정과 줄 수 맞추기 정도였습니다.

개발자에게는 이 답변을 그대로 전달하면 됩니다. **OPS-04 확인을 기다리지 말고 로컬 구현·검증까지 진행할 수 있습니다.** 다만 OCI 환경 플래그 추가와 배포는 OPS-04 종료 후 사용자 승인으로 진행합니다.
