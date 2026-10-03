> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-10-02) · 기록: 개발자(VSCode Claude). 아래는 설계자 전달문 원문 그대로다.
> 앞부분(사용자에게 한 설명)도 단계 · 저장 경로 정정 근거라 함께 기록했다. 개발자가 받은 설계는 `# POC5 단계·저장 경로 설계 정정` 부터다.
> 계기: 개발자 세션 준비 보고(2026-10-02)의 충돌 2건 — 원장 DB 경로(POC5-00 Q5 확정 · 사용자 승인 `state/decision/decision_evidence.sqlite`
> 대 처음 POC5-01A 설계서 `state/decision_ledger/decision_ledger.sqlite`) · 단계 순서(POC5-00 확정 `01a 러너 분리 → 01 원장` 대 처음 POC5-01A = 원장).
> 원장 설계서는 `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` 로 옮겼다(STEP 3).
> 개발 PLAN: `docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md` — **PLAN 판정 전 구현 금지**.
> **설계자 PLAN 판정(2026-10-03 · `REVISE_AND_RESUBMIT`)** 원문은 이 문서 끝 `# 설계자 PLAN 판정` 절 — 필수 보정 4건 · Q1~Q6 (a) 승인(Q5 조건부) ·
> 구현 금지 유지. 보정은 같은 PLAN V1 에 반영해 재제출한다.

네. 개발자가 두 충돌을 정확히 잡았습니다. 둘 다 제가 최근 설계를 만들면서 상위 확정 계약을 덮어쓴 오류입니다.

* DB 경로는 기존 승인 경로로 복원합니다.
* 단계는 러너 분리를 먼저 수행합니다.
* 현재 원장 설계서는 버리지 않고 `POC5-01B`로 넘깁니다.
* OPS-04는 러너 분리 뒤, 실제 원장 수집 시작 전 처리합니다. 신호 계약이 바뀐 뒤 원장을 시작해야 표본이 섞이지 않습니다.

아래를 개발자에게 전달해 주세요.

대상: 개발자

# POC5 단계·저장 경로 설계 정정

개발자가 확인한 두 충돌 모두 사실입니다. 상위 확정 계약을 우선하여 다음처럼 바로잡습니다.

```text
DESIGNER_CORRECTION_REQUIRED = YES
USER_REAPPROVAL_REQUIRED     = NO
IMPLEMENTATION               = 아직 금지
```

## STEP 1. 원장 DB 경로

기존 사용자 승인 경로를 유지합니다.

```text
OCI = state/decision/decision_evidence.sqlite
PC  = state/decision/decision_evidence.sqlite
```

다음 경로는 폐기합니다.

```text
state/decision_ledger/decision_ledger.sqlite
```

이는 새 결정이 아니라 POC5-00 확정 계약 복원입니다. 사용자 재승인은 필요하지 않습니다.

* OCI에는 전용 DB로 새로 생성
* PC에는 같은 상대 경로의 기존 DB에 원장·피드백 테이블 추가
* `runtime_state.sqlite` 변경 0
* PC DB는 POC5-03 동기화 경로로만 채움
* PC 러너·dry-run·테스트 쓰기 금지

## STEP 2. 단계 번호 정정

파일 정렬과 선후관계를 명확히 하기 위해 다음으로 확정합니다.

```text
POC5-01A = 세 PUSH 러너 기계 분리
POC5-01B = 운영 판단 이벤트 원장
POC5-02  = 결과 성숙·원시 수익률
POC5-03  = PC 동기화·사용자 피드백
POC5-04  = R0·R1 기술 리포트
```

기존 POC5-00의 `POC5-01a → POC5-01` 의미를 `POC5-01A → POC5-01B`로 이름만 명확히 한 것입니다. 범위 변경은 아닙니다.

## STEP 3. 현재 staged 문서 정리

현재 신규 파일:

```text
docs/ai_design/POC5/POC5-01A_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md
```

은 내용이 원장 단계이므로 다음으로 rename하십시오.

```text
docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md
```

내부도 함께 고칩니다.

```text
STEP_ID     = POC5-01B
PREDECESSOR = POC5-01A + POC3-02D-OPS-04
SUCCESSOR   = POC5-02
DB_PATH     = state/decision/decision_evidence.sqlite
```

현재 원장 설계 내용은 버리지 않습니다. 단계명·경로·선행조건만 상위 계약에 맞춥니다.

다음 문서를 새로 기록하십시오.

```text
docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md
```

또한 다음 문서의 단계 표와 ‘다음’을 동기화하십시오.

* `docs/STATE_LATEST.md`
* `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md`
* `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`
* OPS-03 인계·종료 문서에서 POC5-01A의 단계명이 적힌 부분

기존 승인 내용이나 범위는 다시 작성하지 말고 단계명만 동기화합니다.

## STEP 4. 전체 진행 순서

```text
1. POC5-01A 러너 기계 분리
2. POC3-02D-OPS-04 운영 보완 5건
3. POC5-01B 운영 판단 이벤트 원장
4. POC5-02 결과 성숙
5. POC5-03 PC 동기화·피드백
6. POC5-04 R0·R1 리포트
```

OPS-04는 POC5-01A를 막지 않습니다. 다만 원장 PRIMARY 모집단이 시작된 뒤 PUSH 계약을 바꾸면 표본이 섞이므로, **POC5-01B 배포 전에는 완료**해야 합니다.

이 순서는 다시 사용자 결정 항목으로 올리지 않습니다.

# POC5-01A 설계 계약

## STEP 5. 목적

646줄인 `scripts/run_three_push_runtime_oci.py`에서 기존 책임을 기계적으로 분리하여, 후속 원장 기능을 러너 본체에 추가하지 않고 연결할 수 있는 구조를 만듭니다.

```text
BEHAVIOR_CHANGE        = 0
MESSAGE_CHANGE         = 0
SCHEDULE_CHANGE        = 0
DB_CHANGE              = 0
STATE_SCHEMA_CHANGE    = 0
EXTERNAL_CALL_CHANGE   = 0
TELEGRAM_SEND_CHANGE   = 0
```

## STEP 6. 분리 대상

사실조사 후 정확한 함수 경계를 PLAN에서 제안하되, 우선순위는 다음과 같습니다.

1. 실행 시작·종료 기록 조립
2. `_finish` 종료 상태 확정
3. JSONL·DB 상태 기록
4. 공통 예외 종료 처리
5. push kind별 dispatch 보조
6. 후속 원장 writer를 주입할 수 있는 경계

원장 `event_id`, 신규 DB 쓰기, signal payload 추가는 이번 단계에서 구현하지 않습니다.

## STEP 7. 파일·줄 수 계약

* 기존 `run()` 진입점과 CLI 계약 유지
* cron 명령 변경 없음
* 새 모듈은 `app/three_push_runtime/` 아래에 둠
* 순환 import 금지
* 러너 목표는 **570줄 이하**
* 후속 원장 연결은 추출된 모듈에 붙이고 러너 본체에는 신규 책임을 추가하지 않음
* 기존 646→648 동결선은 이번 기계 분리로 해소하되, 줄 수만 줄이고 책임이 그대로 남는 위장 분리는 금지

## STEP 8. 동작 불변 완료 조건

분리 전후 다음이 같아야 합니다.

* 세 push kind의 조립 순서
* flag·mode·중복·상한 판단
* Telegram 본문 byte
* 실행 status·reason
* JSONL 기록 내용과 순서
* DB 상태 기록
* 부분 전송·실패 처리
* state 파일 저장 여부
* exit code
* 기존 예외 전파·격리 범위

기존 테스트의 단언을 분리에 맞추기 위해 느슨하게 바꾸지 마십시오.

# 지금 작성할 PLAN

파일:

```text
docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md
```

PLAN 앞부분에서 다음을 실제 코드로 조사하십시오.

1. 러너 전체 call graph
2. `run()`부터 `_finish`까지 모든 종료 경로
3. DB·JSONL·state 파일 쓰기 지점
4. push kind별 분기와 공통 분기
5. 전송 성공·실패·부분 전송의 순서
6. 예외가 잡히는 층과 빠지는 층
7. import 의존 방향과 순환 위험
8. 기존 테스트가 직접 import하는 러너 함수
9. 분리 후보별 줄 수
10. 분리 후 예상 러너 줄 수
11. OCI 전용 모듈 import 제약
12. POC5-01B가 사용할 수 있는 안전한 주입 지점

PLAN에는 파일별 이동표와 ‘이동 전 함수 → 이동 후 함수’를 명시하십시오.

## STEP 9. 중단 조건

다음 경우에만 구현 전에 중단 보고합니다.

* 메시지·판정·상태 저장 순서를 바꾸지 않고 분리할 수 없음
* 기존 테스트가 함수 위치 자체를 운영 계약으로 사용
* 순환 import를 피하려면 운영 동작 변경이 필요함
* 새 DB·API·cron·외부 호출이 필요함
* 러너를 570줄 이하로 만들려면 기능 삭제 또는 의미 변경이 필요함

그 외 질문은 추천안을 붙여 PLAN에 한 번에 제출하십시오.

## STEP 10. 현재 작업 지시

지금은 다음만 수행합니다.

1. staged 문서의 단계명·DB 경로 정정
2. POC5-01A 러너 분리 설계서 기록
3. POC5-01A PLAN 사실조사 및 작성
4. 사용자에게 PLAN 경로와 질문 요약 보고

PLAN 판정 전 코드 구현은 금지합니다. 현재 staged 4파일도 PLAN과 함께 커밋할 수 있지만, 커밋·push는 사용자 승인을 따릅니다.

OPS-04 구현이나 POC5-01B PLAN은 아직 시작하지 마십시오.

---

# 설계자 PLAN 판정 (2026-10-03 · 설계자 원문 · 사용자 전달)

> 기록 정보 — 작성: 설계자(INVESTMENT_MODEL_V2 총괄 설계자 인계 확인과 함께 전달) · 전달: 사용자(2026-10-03) · 기록: 개발자. 아래는 원문 그대로다.
> 개발자 기록(2026-10-03): 설계자가 '재확인 불가'로 둔 `7d507951` 의 OCI 반영은 개발자 읽기 전용 확인으로 반영됨이다 — OCI `git log -1` = `7d507951` ·
> `.git/FETCH_HEAD` 2026-10-02 17:56 KST · OCI 러너 blob `f256677020232600627d207c54baf5081c70c6e2`(저장소 HEAD 와 같음). PLAN §1-0.

[INVESTMENT_MODEL_V2 총괄 설계자 인계 확인]

READ_COMPLETE

* 완독한 필수 문서: `STATE_LATEST`, `PROGRAM_TRUTH`, `PROJECT_ORIGIN_INTENT`, `KILL_SWITCHES`, `ASSUMPTIONS`, `MASTER_PLAN`, `POC5-00 ... MASTER_PLAN`, `POC5-01A ... PLAN`.
* 경로가 달라 찾아 읽은 문서: 최신 `BACKLOG`, 구 총괄 핸드오프, `POC3-02D-OPS-01/02/03 RESULT`, `POC4-00 MASTER_PLAN`, `POC4-01/02/03 HANDOFF`.
* §4 전체 완독 판정: **미성립**. 아래 원문은 현재 제공 범위에서 직접 확인할 수 없었다.

  * `CLAUDE.md`
  * `POC3-02C_CLOSEOUT_2026-09-23.md`
  * OPS-01/02/03의 지정된 HANDOFF·DESIGN·PLAN 원문
  * POC5-00 MASTER DESIGN
  * POC5-01A MECHANICAL SPLIT DESIGN
  * POC5-01B EVENT LEDGER DESIGN
* OPS 결과서는 읽었지만, 지정된 HANDOFF/DESIGN/PLAN을 읽은 것으로 대체 선언하지 않는다.

CURRENT_TRUTH

* POC3 운영 상태: OPS-03까지 `IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED`. 2026-10-02 첫 거래일 운영 증거가 확인됐다.
* POC4 종료 상태: Track A/B 모두 기각·종료. POC4-04/05, XGB/LGBM, 배포 가능한 ML 단계는 열리지 않았다.
* POC5 현재 단계: `POC5-01A runner mechanical split`의 PLAN 심사 단계다. 아직 구현 단계가 아니다.
* 현재 배포와 미배포 차이:

  * OPS-03 운영 배포는 확인됐다.
  * 한국 거래일 계약 보정 커밋 `7d507951`의 실제 OCI 반영 여부는 현재 저장소/OCI HEAD가 없어 재확인할 수 없다.
  * POC5-01A, POC5-01B 및 OPS-04는 미구현·미배포 상태다.

CONTRACT_CORRECTIONS

* POC5-01A = runner mechanical split.
* POC5-01B = event ledger.
* 승인 DB = `state/decision/decision_evidence.sqlite`.
* `state/decision_ledger/decision_ledger.sqlite`는 기각된 경로다.
* 한국 거래일 계약은 재질의하지 않는다.
* `runtime_state.sqlite` 스키마는 변경하지 않는다.
* ledger 계약은 `RAW_ONLY`, 실제 발송 표본만 기록, primary `t0`는 메시지에 실제 사용된 quote이며, ledger 실패가 push를 막아서는 안 된다.

NEXT_ACTION

* POC5-01A PLAN을 수정 후 재심한다.
* PLAN이 PASS되기 전에는 구현하지 않는다.
* OPS-04는 POC5-01A 이후의 별도 단계로 유지한다.

OPEN_BLOCKERS

* 위 §4 필수 원문 부재로 완전한 인계 완료 및 DESIGN 대비 정합성 검증이 불가능하다.
* 현재 작업공간에 실제 Git 저장소와 소스가 없어 HEAD, working tree, runner 646줄, 27개 종료 경로, monkeypatch 13개, 테스트 305개의 사실성을 독립 검증할 수 없다.

## POC5-01A PLAN 판정

**PLAN_DECISION = REVISE_AND_RESUBMIT**
**IMPLEMENTATION = HOLD / 금지 유지**

현재 PLAN은 방향과 단계 경계는 타당하지만, 다음 필수 보정 없이는 PASS할 수 없다.

1. **KS-10 전체 저장소 인벤토리 누락**

   * Cleanup 시작 시점의 전체 `.py`, `.ts`, `.tsx` 파일 줄 수와 모든 `NEAR/TRIGGER` 파일을 다시 제시해야 한다.
   * 과거 POC5-00 인벤토리나 runner 단일 파일 측정으로 대체할 수 없다.

2. **변경 파일 목록 불일치**

   * PLAN은 `scripts/poc5_01a/runner_split_equivalence.py` 신설을 제안하면서 변경 목록은 “새 모듈 3개 + runner”로만 적었다.
   * 검증 스크립트를 정식 변경 범위와 파일 수에 포함해야 한다.

3. **동등성 기준점 고정 부족**

   * 단순히 `git show <분리 직전 커밋>`이라고 하지 말고 구현 직전 HEAD와 runner blob SHA를 고정해야 한다.
   * 비교 시작 전 현재 runner가 해당 blob과 동일함을 확인하는 절차가 필요하다.

4. **monkeypatch 경계 증거 부족**

   * 기존 13개 monkeypatch 대상 각각에 대해:

     * runner에 잔류,
     * 새 모듈에 호출 시 전달,
     * 이동하지 않음

     중 어느 처리인지 명시해야 한다.
   * 특히 시간 함수, 상태 경로, `insert_status_from_record`, `mark_sent`, `build_runtime_message`의 결합 시점이 드러나야 한다.

PLAN의 선택지는 다음과 같이 판정한다.

* Q1: **(a) 승인**
* Q2: **(a) 승인**
* Q3: **(a) 승인** — outer exception conversion은 POC5-01B로 유지
* Q4: **(a) 승인** — injection boundary 식별까지만
* Q5: **(a) 조건부 승인** — 위 기준점 고정과 변경 파일 목록 보정 필요
* Q6: **(a) 승인** — POC5-01A 단독 배포·첫 거래일 관찰 후 OPS-04

이는 새 기능 요구가 아니라, 현재 PLAN의 검증 가능성과 계약 준수를 위한 필수 수정이다. 원문 DESIGN과 실제 저장소가 제공되고 위 네 항목이 반영되기 전에는 구현 승인을 내리지 않는다.

---

# 설계자 PLAN 재판정 (2026-10-03 · 설계자 원문 · 사용자 전달)

> 기록 정보 — 아래 code block 은 설계자가 '설계서에 기록할 판정 원문'으로 지정한 부분 그대로다. 같은 전달문의 나머지 지시는 다음과 같다.
> - 판정 표: 보정 4건 모두 `CLOSED` · `OPEN_BLOCKERS = NONE` · `COMMIT / PUSH / OCI = 별도 사용자 승인 유지` · 구현 직전 §3-1 기준점 검사 4개 중 하나라도 실패하면 즉시 중단.
> - 낡은 문구 17곳: `STATE_LATEST` · `PROGRAM_TRUTH` 는 최신 사실로 직접 정정한다. OPS-03 RESULT · HANDOFF 는 기존 문장을 두고 `2026-10-03 후속 배포 확인` 항목을 추가한다(설계자 정본 문구). POC5-01A 구현과 섞지 않는 **선행 문서 정정**이다.
> - 경로: `docs/BACKLOG.md` 는 잘못된 경로다(정본 `docs/backlog/BACKLOG.md`). Git 비관리 `INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 향후 인계서에 `외부 첨부 필수` 로 적는다. 사용자가 staged 한 `POC5-00_INVESTMENT_MODEL_V2_MASTER_DESIGNER_HANDOFF_2026-10-03.md` 는 사용자 소유 선행 변경이다 — 개발자는 수정 · unstage 하지 않고, 코드 변경 수에 넣지 않으며, 결과서에 `구현 전부터 존재한 사용자 소유 staged 문서` 로 기록한다.
> - PLAN §4 롤백 문구 비차단 정정: "분리 전용 스키마·데이터 변경이 없어 되돌릴 데이터가 없다"(재제출 불필요).

```text
# 설계자 PLAN 재판정 — 2026-10-03

PLAN_DECISION = PASS

1차 REVISE_AND_RESUBMIT에서 요구한 필수 보정 4건은 모두 충족됐다.

- KS-10 전체 저장소 인벤토리와 NEAR/TRIGGER가 다시 측정됐다.
- 검증 스크립트를 포함한 코드 변경 파일 5개가 확정됐다.
- 분리 전 runner blob과 기존 모듈 blob이 고정됐고 구현 전 중단 검사가 마련됐다.
- monkeypatch 대상 13개의 잔류·전달 경계와 검증 방법이 이름별로 확정됐다.

Q1~Q6의 기존 확정을 유지한다.
POC5-01A 범위는 A·B·D·E의 기계적 분리뿐이다.
동작·본문 byte·판정·상태 저장 순서·예외 전파·CLI·cron·DB·스키마는 바꾸지 않는다.

로컬 구현 착수를 승인한다.
커밋·push·OCI pull은 이 판정에 포함되지 않으며 기존 별도 승인 절차를 유지한다.
```
