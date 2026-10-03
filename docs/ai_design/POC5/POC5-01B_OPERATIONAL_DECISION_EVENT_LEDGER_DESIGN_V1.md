> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-10-02) · 기록: 개발자(VSCode Claude). 아래는 설계자 전달문 중 `# POC5-01A 설계 지시` 부분 원문이다.
> 같은 전달문의 앞부분(`POC3-02D-OPS-03` 종료 판정 · 잔여 판단 5건 → `POC3-02D-OPS-04` · `POC5-01A = OPEN`)은
> `docs/ai_design/POC3/POC3-02D-OPS-03_OPERATIONAL_DATA_FRESHNESS_AND_SOURCE_RECOVERY_DESIGN_V1.md` 끝 절에 원문 그대로 있다.
> 상위 설계: `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` · PLAN `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`.
> **설계자 정정(2026-10-02 · 원문 = `docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md` STEP 1 ~ 3)**: 이 원장 설계는
> `POC5-01A` → **`POC5-01B`** 로 옮겼다(파일 이름 변경 · 처음 기록 이름 `POC5-01A_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md`).
> 설계자 지시대로 본문에서 고친 곳은 단계명 · 저장 경로 · 선행조건뿐이다 — 머리 code block(`STEP_ID` · `PREDECESSOR` · `SUCCESSOR`) ·
> 문서 경로 2줄 · STEP 3 · STEP 10 · 끝 줄의 단계명 · STEP 4 DB 경로(원래 `state/decision_ledger/decision_ledger.sqlite` · 폐기 →
> POC5-00 확정 경로 복원 · 사용자 재승인 불필요). 나머지 내용은 원문 그대로다.
> 순서: `POC5-01A` 러너 기계 분리 → `POC3-02D-OPS-04` → **`POC5-01B`(이 문서)** → `POC5-02`. 이 단계 PLAN 은 아직 쓰지 않는다(설계자 지시).

# POC5-01B 설계 지시

```text
STEP_ID     = POC5-01B
STEP_NAME   = 운영 판단 이벤트 원장 수집 기반
PREDECESSOR = POC5-01A + POC3-02D-OPS-04
SUCCESSOR   = POC5-02
```

문서:

```text
docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md
docs/ai_plan/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_PLAN_V1.md
```

이번 단계는 먼저 설계서를 기록하고 사실조사가 포함된 PLAN을 제출합니다. PLAN 판정 전 구현하지 마십시오.

## STEP 2. 목표

2026-10-02 이후 실제로 사용자에게 전달된 운영 판단을 구조화된 이벤트로 남깁니다.

대상:

* `market_briefing`
* `holdings_briefing`
* `holdings_risk_alert`

  * 보유 급등락
  * 신규 진입 검토
  * 급락 회피
  * 추격 주의

목표는 “맞았다·틀렸다”를 판정하는 것이 아니라 **무엇을 어떤 근거와 가격으로 실제 전달했는지** 보존하는 것입니다.

## STEP 3. 이번 단계에서 하지 않는 것

* 성공·실패 판정
* 시장 방향 적중률
* 점수·등급·랭킹
* ML 학습·재학습
* 매수·매도 추천
* 과거 메시지 종목 단위 복원
* 과거 수익률 열람·역산
* Telegram 메시지 변경
* 사용자 피드백 UI
* 자동 PC SSH 동기화

POC5-01B 자체가 ML로 가는 통로가 되어서는 안 됩니다.

## STEP 4. 저장 계약

OCI에 전용 DB를 사용합니다.

```text
state/decision/decision_evidence.sqlite
```

기존 `runtime_state.sqlite`는 변경하지 않습니다.

최소 구조:

1. 실행 단위
2. 메시지 단위
3. 구조화된 종목·신호 이벤트
4. 전달 결과
5. 기록 누락 gap
6. schema/version 정보

실제 테이블 구조는 PLAN에서 기존 전송 경로를 조사한 뒤 제안하십시오.

## STEP 5. 기록 시점과 전달 사실

원장은 다음 상태를 구분해야 합니다.

```text
PLANNED
DELIVERED
FAILED
PARTIAL
SKIPPED
GAP
```

분석 표본은 `DELIVERED`만 사용합니다.

* Telegram 성공 확인 후 전달 완료로 기록
* 부분 전송이면 실제 전달된 메시지·종목만 `DELIVERED`
* 전달되지 않은 항목은 `PARTIAL` 또는 `FAILED`
* 같은 실행 재시도에서 중복 행 금지
* 전송 성공 뒤 원장 기록이 실패하면 명시적 `GAP`
* 원장 장애가 기존 운영 PUSH를 막아서는 안 됨

## STEP 6. 이벤트에 보존할 값

종목 이벤트에는 최소한 다음을 보존합니다.

* push kind
* 실행 ID·슬롯·전달시각
* Telegram 메시지 식별자 또는 회신 가능한 전달 식별자
* ticker·name
* event kind·state
* 보유/비보유 구분
* 메시지 생성에 실제 사용한 현재가
* 현재가 기준시각·source
* 직전 종가·추세 기준일
* 당시 5일·20일 등 실제 표시된 원시 수치
* 정책 버전·대표 ETF pool 버전
* message hash
* 반복·연속 상태
* 같은 날 노출 순번

현재가 기준은 나중에 다시 조회한 가격이 아니라 **메시지 생성에 실제 사용한 가격**입니다.

시장 브리핑은 종목 예측으로 만들지 말고 실행 이벤트와 사용 evidence만 기록합니다.

## STEP 7. 반복 노출 계약

데이터를 버리지 않습니다.

* 실제 전달된 반복 노출도 모두 원장에 기록
* 같은 날짜·ticker·event kind의 첫 전달을 `same_day_primary=true`
* 이후 같은 날 전달은 보조 노출
* 전날부터 이어진 상태는 `repeat_exposure=true`
* 향후 평가 표본 규칙은 파생 view에서 정함
* 원시 이벤트 행을 수정·삭제해 표본을 만들지 않음

## STEP 8. 과거 자료

과거 실행 577건은 실행 사실만 남아 있고 종목 단위 본문이 없으므로 종목 이벤트를 추정하지 않습니다.

```text
HISTORICAL_ITEM_BACKFILL = PROHIBITED
PROSPECTIVE_START_ONLY   = true
```

원장 가동일부터 새로 쌓습니다.

## STEP 9. OCI 전용 쓰기

원장 쓰기는 다음 조건에서만 허용합니다.

* OCI 운영 러너
* `mode=send`
* 실제 전송 경로
* 운영 push kind

다음은 쓰기 금지입니다.

* PC 실행
* dry-run
* compose-only
* 테스트
* 목업 생성
* 과거 재생
* 승인 화면 조회

hostname 추측만으로 판단하지 말고, 운영 러너에서 writer를 명시적으로 주입하는 구조를 우선 검토하십시오.

## STEP 10. PC 동기화

PC 화면 진입 시 자동 SSH는 금지합니다.

POC5-01B에서는 OCI 기록과 검증 가능한 export 계약까지만 만듭니다. PC 동기화 버튼과 화면은 후속 단계에서 구현합니다.

기존 `Decision Outcome Ledger`의 `First Real Decision Cycle` 선행 조건은 이번 POC5-00·01A 계약으로 대체합니다.

## STEP 11. PLAN 사실조사

PLAN 앞부분에서 다음을 확인하십시오.

1. 세 PUSH의 실제 조립→전송→저장 경로
2. Telegram 성공을 메시지별로 식별할 수 있는지
3. partial delivery에서 전달 항목을 구분할 수 있는지
4. 현재가·기준일·source가 사라지기 전 위치
5. 전송 성공과 원장 저장 사이 crash window
6. 기존 run ID·message ID·registry 재사용 가능성
7. 같은 실행 재시도 시 idempotency key
8. 전용 SQLite 생성·백업·export 방법
9. OCI와 PC 쓰기 권한 격리 방법
10. 러너 646줄 동결 유지 방법
11. 하루 예상 이벤트 수·1년 DB 크기
12. 기존 테스트 라이브 상태 보호 규칙
13. 신규 API·cron·외부 호출 필요 여부

## STEP 12. 중단 조건

다음 중 하나가 확인될 때만 구현 전에 중단 보고하십시오.

* 실제 전달 항목을 메시지·종목 단위로 식별할 수 없음
* 전용 DB가 아니라 기존 운영 DB 변경이 필요함
* 원장 기록 실패가 Telegram 전송을 막는 구조만 가능함
* PC·dry-run 쓰기를 구조적으로 차단할 수 없음
* 러너 동결선을 넘기지 않고 배선할 수 없음
* 신규 외부 API·cron이 필요함

그 외 질문은 추천안을 포함해 PLAN에서 한 번에 제출하십시오.

## STEP 13. 완료 조건

* 실제 성공 전달 이벤트 100% 기록
* failed·skipped를 성공 표본에 포함하지 않음
* 부분 전송 정확히 분리
* retry 중복 0
* 기록 실패 gap 명시
* PC·dry-run·테스트 쓰기 0
* 기존 PUSH 본문·시간·발송량 변화 0
* 신규 외부 호출·cron 0
* 전체 회귀 통과
* 라이브 운영 파일 불변 검증
* 전용 DB 생성·복구·export 검증

먼저 POC5-01B 설계서 기록과 PLAN을 제출하십시오. 코드 구현은 PLAN 판정 뒤입니다.
