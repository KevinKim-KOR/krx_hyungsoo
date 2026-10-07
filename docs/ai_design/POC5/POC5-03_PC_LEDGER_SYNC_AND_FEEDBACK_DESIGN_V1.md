# POC5-03 — PC 알림 기록·선택 평가 DESIGN V1 (개정 2)

개정: 2026-10-07 · 사용자 목업 결정 반영. 기존 파일 경로는 유지한다.

```text
STEP_ID          = POC5-03
PREDECESSOR      = POC5-02
SUCCESSOR        = POC5-04
PURPOSE          = 알림·당시 근거·이후 결과를 보존하고 필요할 때 사후 검토한다
REVISION         = 2
MENU             = 진단·상태 > 받은 알림 기록 (ML 실험 옆)
SYNC_POLICY      = USER_CLICK_ONLY
FEEDBACK_POLICY  = OPTIONAL_PC_LOCAL_APPEND_ONLY
OUTCOME_POLICY   = REVIEW_ON_DEMAND_WITHOUT_FEEDBACK_GATE
ML_SAMPLE_POLICY = INCLUDE_WITH_OR_WITHOUT_USER_FEEDBACK
```

## 1. 완료 모습

「진단·상태」의 `ML 실험` 옆에 별도 메뉴 `받은 알림 기록`을 둔다. 「오늘의 투자 점검」에는 넣지 않는다. 매일 모든 알림을 평가하는 작업이 아니라, 이후 ML 연구·사후 검토를 위한 기록이다.

- 실제 전달된 `sent`·`partial` 알림을 날짜와 종류별로 확인한다.
- 원문·당시 판단 근거를 확인하고, 필요할 때 +1/+5/+20 원시 가격 결과를 펼쳐 본다.
- `도움됨 / 보통 / 불필요·혼란` 평가는 선택이며 입력하지 않아도 조회·저장·향후 ML 사용을 막지 않는다.
- ML 사후평가 자체는 이번 단계에서 구현하지 않는다. 원장과 연결할 연구 계약은 §12에 둔다.
- OCI PUSH와 가격 배치에는 어떤 변화도 없다.

## 2. 포함·제외

### 포함

- 사용자 버튼 1회에 한한 OCI 읽기 전용 export와 PC 사본 반영
- 기존 PC `state/decision/decision_evidence.sqlite`의 원장 사본과 `user_feedback`
- 127.0.0.1 전용 조회·동기화·피드백 API
- 별도 메뉴 `받은 알림 기록` 1개와 접기 영역 `신호 결과 원장`
- PC 전용 `ledger_sync_attempt`(마지막 성공·실패 동기화 기록)
- 동기화·피드백 실패 시 기존 로컬 자료 보존

### 제외

- PC 기동·화면 진입·주기 실행에 의한 자동 원장 SSH(기존 POC3-07 상태 확인 SSH 1회는 유지)
- OCI DB 파일 자체 복사와 PC→OCI 쓰기
- 추가 메뉴 2개 이상·cron·daemon·상태 JSON·외부 시세 조회·신규 의존성
- 성공률·추천 적중률·유리한 방향·ML label
- suppressed·cut·not_selected 실행에 대한 사용자 피드백
- 보유 매수·매도 이력 및 holdings 스키마 변경

## 3. 동기화 계약

PC 로컬 사본을 즉시 보여 주고, `원장 새로고침` 버튼으로만 OCI export·검증·사본 반영을 한다.

- 버튼을 누르기 전에는 SSH를 실행하지 않는다.
- OCI 명령은 원장을 읽기 전용으로 열고 JSONL 또는 동등한 행 스트림만 stdout으로 내보낸다.
- V1은 전체 원장 export 후 키 기반 upsert를 기본으로 한다. 실제 크기로 문제가 확인되지 않으면 cursor·증분 토큰·동기화 큐를 만들지 않는다.
- 원격 `evaluation_run`의 종료 확정 상태는 같은 `event_id`에 반영한다. INSERT-only인 item·delivery·outcome은 확정 키로 중복 없이 반영한다.
- 원격 데이터 검증이나 저장 중 하나라도 실패하면 그 동기화 전체를 실패로 표시하고 기존 로컬 사본은 그대로 둔다.
- SSH 성공 여부와 마지막 성공 동기화 시각만 PC 화면에 표시한다. OCI에 동기화 상태를 쓰지 않는다.
- 결과 반영 수·원격 결과 표 유무를 동기화 응답과 시도 기록에서 제외한 기존 변경은 수용한다. 이번 개정으로 다시 넣을 필요는 없다.

PC 사본 키는 실제 POC5-02 스키마를 따른다.

```text
evaluation_run  event_id
signal_item     event_id + item_seq
delivery        event_id
price_outcome   event_id + item_seq + series_id + horizon
```

## 4. PC 저장 계약

- PC의 기존 `state/decision/decision_evidence.sqlite`만 사용한다. 새 DB를 만들지 않는다.
- OCI 원장 테이블은 원격 스키마와 의미를 바꾸지 않은 사본으로 둔다.
- `user_feedback`은 PC 전용이며 OCI export로 덮어쓰거나 삭제하지 않는다.
- 테스트는 임시 DB 경로를 명시적으로 주입한다. 함수 정의 시점에 고정된 기존 기본 경로를 그대로 사용하지 않는다.
- 동기화 쓰기는 짧은 단일 트랜잭션으로 수행한다. 일부 테이블만 갱신된 상태를 남기지 않는다.
- 기존 PC `ai_session_records`·파일 권한·저널 방식은 바꾸지 않는다. OCI 전용 `ledger_store.connect()` 대신 승인된 PC 연결 방식과 DDL 상수를 재사용한다.
- `ledger_sync_attempt`은 같은 DB의 PC 전용 append-only 표로 두며 본문·개인값을 기록하지 않는다.

`user_feedback`의 최소 계약은 다음과 같다.

```text
event_id · feedback_seq · helpfulness · action · memo · feedback_at
```

- `helpfulness`: `HELPFUL / NEUTRAL / UNHELPFUL_CONFUSING` 중 하나가 필수다.
- `action`: 선택값이며 `WATCH_ONLY / BUY_OR_ADD / SELL_OR_REDUCE / OTHER`만 허용한다.
- `memo`: 선택값이며 strip 뒤 500자까지 허용한다. 빈 문자열은 NULL이다.
- 첫 입력만이 아니라 재입력도 허용하되 UPDATE하지 않고 `feedback_seq + 1`로 추가한다.
- 화면의 현재 평가는 가장 최근 feedback을 보여 주고, 이전 행은 보존한다.
- 피드백을 입력하지 않은 event에는 행을 만들지 않는다.
- 무평가는 `평가 없음`이며 부정·중립·도움 안 됨으로 치환하지 않는다. ML 평가로 이 표를 자동 채우지 않는다.

## 5. 화면 계약

메뉴는 「진단·상태」의 `ML 실험` 옆 `받은 알림 기록`이다. 실제 MenuKey 12 → 13을 승인하며 사이드바·MainPanel·테스트를 함께 반영한다.

| 화면 위치 | 내용 |
|---|---|
| 상단 | 원장 새로고침 · 마지막 성공 동기화 시각 |
| 날짜 탐색 | 날짜 선택 · 이전/다음 날 · 종류 필터 |
| 알림 카드 | 시각 · 종류 · 전달 상태 · 핵심 item · 자세히 보기 |
| 카드 상세 | 생성 원문 · 당시 판단 근거 · 사용자 평가(선택) |
| 접기 영역 | 신호 결과 원장: +1/+5/+20 원시 결과 |

- 목록은 선택 날짜 하루의 `delivery_status=sent|partial`만 보여 준다. 최초 기본 날짜는 PC 사본에 받은 알림이 있는 가장 최근 날짜다(전체 종류 기준). 알림이 없으면 오늘 KST와 빈 상태를 표시한다.
- 사용자가 선택한 날짜는 동기화·종류 변경 뒤에도 유지한다. 강제로 오늘이나 최신 날짜로 이동시키지 않는다.
- 시장·보유·장중 종류 필터만 둔다. 점수·추천 순위는 만들지 않는다.
- 카드에는 실행 시각·알림 종류·전달 상태·핵심 item 수만 먼저 보여 주고, 원문과 item은 `자세히 보기`에서 확인한다.
- `partial`은 성공으로 위장하지 않고 `일부 전달`로 표시한다.
- `partial`의 전문 제목은 `생성된 원문 — 일부만 전달됨`, 안내는 `실제 수신된 범위는 확인할 수 없습니다`다. 분할 전 전문을 받은 전문으로 부르지 않는다.
- 평가 입력은 상세의 선택 영역으로 둔다. 미평가 수·평가 완료율·평가 독촉·매일 해야 할 목록은 만들지 않는다.
- 로컬 사본이 없으면 `원장 새로고침이 필요합니다`, 실패하면 `기존 기록을 표시 중입니다`와 실패 시각을 보여 준다.

`신호 결과 원장`은 같은 구역 안의 접기 영역이다.

- 평가 가능한 item의 당시 상태·t0·disposition과 원시 +1/+5/+20 결과를 보여 준다.
- 피드백 유무와 무관하게 접기 영역을 펼치면 저장된 결과를 조회한다. `피드백 후 결과 확인` 조건과 backend feedback gate를 폐기한다.
- POC5-02 대상 event·item에 아직 결과 행이 없으면 `집계 중`, 상태 행이면 `가격 자료 없음 / 매도 뒤 추적 중단 / 지원 계열 없음 / 기준 가격 없음`처럼 사실만 표시한다.
- `LEGACY_DIAGNOSTIC`·예정 외 event, `evaluable=0`, subject가 ticker/sector/market/index_group 이외인 item은 `결과 대상 아님`이다. 무평가는 대상 제외 조건이 아니다.
- 결과 수익률은 원시 데이터의 화면 표현일 뿐 성공·실패 색이나 적중 배지를 붙이지 않는다.

## 6. API 경계

정확한 path와 payload는 PLAN에서 기존 라우팅 구조를 확인해 정하되 기능은 세 종류로 제한한다.

1. 로컬 사본 조회
2. 사용자 클릭에 의한 OCI 동기화
3. append-only 피드백 추가

- 모두 PC의 127.0.0.1 backend 전용이다.
- 동기화 API만 기존 SSH 설정을 사용한다. 시장 API·Telegram·OCI 쓰기는 호출하지 않는다.
- 피드백 요청은 `sent|partial` delivery가 로컬에 있는 event만 허용한다.
- outcome 응답은 feedback 0행이어도 조회를 허용한다. 접기·지연 조회는 화면 가독성을 위한 것이며 권한·평가 조건이 아니다.

## 7. 실패·보안 경계

- SSH 인증 실패·timeout·원격 export 오류: 기존 사본 유지, 피드백 가능, 동기화 실패 표시
- 잘못된 JSONL·필수 키 누락·중복 충돌: 전체 반영 취소
- 로컬 DB 쓰기 실패: 화면 오류만 반환하며 OCI와 운영 PUSH에 영향 0
- feedback 실패: 성공한 것처럼 버튼 상태를 바꾸지 않는다.
- 원격 명령은 고정된 읽기 전용 명령만 허용하고 사용자 입력을 shell 문자열에 붙이지 않는다.
- 전문·메모·사용자 행동은 PC 로컬에만 표시·저장하며 로그에 본문을 남기지 않는다.

## 8. 수용 기준

1. PC 기동과 화면 진입만으로 원장 export SSH 호출이 0건이다(기존 상태 확인 SSH는 예외).
2. 버튼 1회가 OCI 읽기 전용 export 1회만 실행하고 원격 파일을 바꾸지 않는다.
3. 같은 export를 반복 반영해도 원장 사본 행이 중복되지 않고 PC feedback이 보존된다.
4. 중간 실패를 주입하면 모든 원격 테이블 반영이 취소되고 기존 화면 자료가 남는다.
5. sent·partial만 목록과 feedback 대상이며 나머지는 거부된다.
6. 미입력 feedback 행이 없고 재입력은 새 sequence로 누적된다.
7. feedback 0행이어도 API·화면에서 결과를 조회할 수 있고, 조회가 feedback 행을 만들지 않는다.
8. MATURED·PENDING·결측·결과 대상 아님이 feedback 유무와 무관하게 정확히 표시된다. 무평가는 부정 라벨이 아니다.
9. 승인된 별도 메뉴 1개만 추가하며 오늘의 투자 점검 삽입·cron·외부 시세 호출·OCI 쓰기·실 Telegram 발송은 0건이다.
10. API 임시 DB 테스트·frontend 테스트·사용자 실화면·전체 회귀·라이브 파일 불변·KS-10을 통과한다.

## 9. 개발 PLAN에서 확인할 것

1. 기존 PC decision DB 테이블·기본 경로 고정 문제와 안전한 경로 주입 방법
2. 기존 SSH 실행 wrapper·OCI python 경로·읽기 전용 export 위치
3. POC5-02 실제 5개 원격 테이블 DDL과 PC upsert/update 허용 경계
4. 「진단·상태」 메뉴·MainPanel·캐시·API 라우팅의 정확한 삽입 지점
5. feedback action·memo 검증에 재사용할 기존 입력 제한
6. 기존 feedback gate를 제거할 응답 조립 위치와 무평가 결과조회 테스트
7. 변경 파일·테스트·실화면 확인 방법·KS-10 실측

기존 PLAN 조사는 재실행하지 않는다. 개정으로 바뀐 위치·조회 조건·테스트만 PLAN에 반영하고 별도 재제출 없이 진행한다.

## 10. 진행·배포 기준

- DESIGN·PLAN·로컬 구현·검증은 POC5-02 OCI 배포나 첫 outcome 성숙을 기다리지 않는다.
- PC 사본의 스키마 fixture로 개발하고, 실제 원장 자료를 보려는 OCI 동기화 확인만 POC5-02 배포 뒤 진행한다.
- 새 메뉴·선택 평가·결과 접기 기준으로 목업을 한 번 갱신해 사용자에게 보여 준다. 기존 backend 전체 재작성은 하지 않는다.
- POC5-03은 PC 기능이므로 OCI pull·cron 변경이 없다. PC backend/frontend 반영과 사용자 실화면 확인으로 종료한다.
- 변경된 gate·메뉴·날짜·무평가 상태 테스트를 추가·교체한다. 기존 55개 통과는 변경 전 기준이며 수정 후 검증 결과로 갱신한다.

## 11. 보유 이력 요청의 위치

사용자가 요청한 매수·매도 시점·금액 기록은 필요성을 인정한다. 다만 원장 사본·피드백과 저장 주체·입력 화면·개인값 경계가 달라 POC5-03에 넣지 않는다.

- BACKLOG의 holdings 스키마 확장 트리거는 충족된 것으로 유지한다.
- 별도 소형 설계에서 현재 holdings 저장·OCI 적용·재매수 의미를 먼저 정한다.
- POC5-02 기존 outcome을 다시 계산하거나 수정하지 않는다.
- 이 항목은 POC5-03과 POC5-04 진행을 막는 gate가 아니다.

## 12. 사후평가·향후 ML 연결 계약

기본 흐름은 `알림 당시 snapshot 저장 → 가격 결과 성숙 → 연구 실행 시 사후평가`다. PC 미기동·사용자 무평가여도 OCI 01B·02 저장은 계속된다.

| 정보 | 의미와 사용 |
|---|---|
| 당시 item·t0·계약 버전 | 알림 시점 조건과 판단을 재현하는 근거 |
| +1/+5/+20 원시 가격 결과 | 사용자 평가 없이도 분석·학습할 수 있는 결과 자료 |
| user_feedback(있는 경우만) | 사용자가 느낀 도움·혼란·행동의 명시적 평가 |
| ML 사후평가(향후) | 당시 근거와 성숙 결과를 정해진 연구 기준으로 검토한 별도 평가 |

- POC5-04 리포트와 이후 ML의 기본 모수는 feedback 있는 행만이 아니다. 무평가도 포함하며 데이터·cohort·시간·전달 상태 기준은 기존대로 적용한다.
- 사용자 평가가 있으면 사용자에게 도움이 됐는지의 명시적 기준으로 사용한다. 없다면 ML 사후평가로 검토하되 사용자 의견을 생성·대입하지 않는다. 둘 다 있으면 출처를 나눠 보존한다.
- 도움이 됐다는 평가와 가격이 올랐다는 결과는 다른 대상이다. 급락 경고 후 계속 하락했다고 알림 실패로 단정하지 않는다.
- '적절한 알림'의 목표·기간·평가 기준과 학습/평가 날짜 분리는 향후 ML 실험 PLAN에서 먼저 정한다. POC5-03·04에는 새 성공 라벨을 넣지 않는다.
- 이후 수익률·사후 feedback은 결과/평가에만 쓰며 당시 예측 입력인 것처럼 쓰지 않는다. 새 모델의 시험 구간은 그 모델의 학습 구간과 분리한다.
- POC5-04는 RAW_ONLY 수집 점검·기술통계를 유지한다. ML 모델 실행·정기 재학습·새 평가 표는 이번 변경에 추가하지 않는다.

## 13. 계약 변경 기록·개발자 지시

```text
CHANGE_DECISION = ACCEPTED_USER_DIRECTED_DESIGN_CHANGE
PLAN_RESUBMISSION = NOT_REQUIRED
A_RESULT_HIDE = SUPERSEDED; 사용자 평가 없이 원시 결과 조회 허용
B_DEFAULT_DATE = LATEST_LOCAL_SENT_OR_PARTIAL_DATE
C_ML_FEEDBACK = OPTIONAL; 무평가로 제외·부정 라벨 생성 금지
BACKEND_REWRITE = NONE; 조회 feedback gate만 국소 수정
```

- POC5-00 Q23(기본 화면 내 구역·메뉴 수 고정)과 Q24 중 '피드백 전 결과 비노출'은 이 사용자 결정으로 대체한다. append-only·sent/partial feedback 규칙은 유지한다.
- 개발자는 마스터·PLAN·STATE·PROGRAM_TRUTH의 해당 문장만 같은 구현 범위에서 정합화하고, 원 판정은 결정 이력으로 보존한다. 전체 재조사·PLAN 재판정은 하지 않는다.
- 01B·02 코드·가격 계산·outcome INSERT-once·OCI 배포 게이트는 바꾸지 않는다. 피드백과 무관하게 보존된 자료를 향후 연구에 사용한다.

---

# 결정 이력 (원문 보존 · 개정 2 의 §13 에 따라)

아래 두 원문은 개정 전(DESIGN V1 최초판 · 2026-10-07) 기준이다. 개정 2 가 '피드백 전 결과 비노출(Q24 일부)' · '기본 화면 내 구역(Q23)' 을 대체했다. Q-A · Q-B · Q-C 확장 · partial 본문 표기는 개정 2 본문에 흡수됐다.

## 설계자 전달문 — 2026-10-07 (사용자 전달 원문 · POC5-02 RESULT 판정과 함께)

```text
POC5-03 PLAN 작성도 바로 진행하십시오.

설계서:
docs/ai_design/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_DESIGN_V1.md

주요 경계:
- 원장 새로고침 버튼을 누를 때만 SSH
- PC 기동·화면 진입 자동 SSH 금지
- OCI 읽기 전용, PC→OCI 쓰기 금지
- 새 메뉴 없이 오늘의 투자 점검 안에 추가
- feedback 전에는 backend와 frontend 모두 가격 결과 비노출
- feedback은 PC 전용 append-only
- 보유 매수·매도 이력은 POC5-03 제외
- §9의 7개 코드 사실을 조사해 PLAN 제출
- 실제 OCI 동기화 확인만 POC5-02 배포 뒤 수행
- PLAN·로컬 구현·검증은 지금 진행 가능

frontend 구현 전 설계서 §5 구성을 실제 화면 목업으로 사용자에게 보여주십시오.
```

---

## 설계자 PLAN 판정 — 2026-10-07 (사용자 전달 원문)

```text
PLAN_DECISION = PASS_TO_IMPLEMENT_WITH_CORRECTIONS
RESUBMISSION = NOT_REQUIRED

Q-A = ACCEPTED
Q-B = ACCEPTED
Q-C = ACCEPTED_AND_EXPANDED
```

> 판정 내용:
>
> - Q-A: 수용 기준의 SSH 0건은 **원장 동기화 SSH**에만 적용합니다. 기존 POC3-07 기동 상태 확인 SSH 1회는 유지합니다.
> - Q-B: PC DB의 `ledger_sync_attempt` 표 추가를 승인합니다. 마지막 성공·실패 시각을 재기동 후에도 보여주는 데 필요한 최소 기록입니다.
> - Q-C: `결과 대상 아님` 문구를 승인합니다.
>
> 다만 구현 시 두 가지를 추가로 반영해야 합니다.
>
> 1. `결과 대상 아님` 판정을 event뿐 아니라 item에도 적용합니다.
>
> ```text
> event:
> PRIMARY_LIVE AND off_schedule=0
>
> item:
> evaluable=1 AND
> subject ∈ {ticker, sector, market, index_group}
> ```
>
> `index_block`, `sector_block`, `evaluable=0`처럼 POC5-02가 가격 결과를 만들지 않는 item에도 `집계 중`이라고 표시하면 안 됩니다.
>
> 2. `partial` 알림의 전문 표시를 명확히 합니다.
>
> 01B의 `body_text`는 실제 전달된 부분만이 아니라 분할 전 전체 본문입니다. 따라서 `partial` 상세에서는 다음처럼 표시해야 합니다.
>
> ```text
> 생성된 원문 — 일부만 전달됨
> 실제 수신된 범위는 확인할 수 없습니다.
> ```
>
> `받은 전문`, `전달된 원문`처럼 전체가 수신된 것으로 오해할 표현은 사용하지 않습니다.

```text
(개발자 전달문)
POC5-03 PLAN 판정

PLAN_DECISION = PASS_TO_IMPLEMENT_WITH_CORRECTIONS
RESUBMISSION = NOT_REQUIRED

Q-A ACCEPTED
- '기동·화면 진입 SSH 0건'은 원장 export SSH에 한정
- 기존 POC3-07 기동 상태 확인 SSH 1회 유지

Q-B ACCEPTED
- PC DB에 append-only ledger_sync_attempt 추가 승인

Q-C ACCEPTED_AND_EXPANDED
- 결과 대상이 아닌 event는 '결과 대상 아님'
- 다음 item도 '결과 대상 아님':
  evaluable=0 또는 subject가
  ticker/sector/market/index_group 이외인 경우
- 이러한 item을 '집계 중'으로 표시하지 않음

추가 구현 조건:
- partial 상세의 body_text는 전체 수신 본문으로 표현하지 않는다.
- '생성된 원문 — 일부만 전달됨 /
   실제 수신된 범위는 확인할 수 없습니다'로 표시한다.

위 조건을 테스트에 포함해 구현 진행.
PLAN 재제출은 하지 않는다.

backend 구현과 화면 목업 작성을 병행하고,
사용자 목업 확인 뒤 frontend를 구현한다.
POC5-02 OCI 배포는 기존대로 10-08 01B 운영 확인 뒤 진행한다.
```

---

## 설계자 개정 전달문 — 2026-10-07 (사용자 전달 원문 · 사용자 목업 결정 뒤 · 개정 2)

```text
POC5-03 사용자 결정 반영 — 구현 계속 승인

- 별도 메뉴·선택 평가·무평가 ML 활용으로 설계 개정
- backend의 feedback 유무에 따른 결과 조회 제한 제거
- 저장·동기화 backend 전체 재작성 불필요
- 기존 숨김 테스트를 무평가 결과조회 테스트로 교체
- 새 메뉴 기준 목업 갱신 후 frontend 진행
- PLAN 변경점만 기록하고 재제출하지 않음
- 향후 ML은 사용자 평가 없는 데이터도 사용
- POC5-01B·02 운영 및 배포 계약은 그대로 유지
```

---

## 설계자 RESULT 판정 — 2026-10-07 (사용자 전달 원문 · 검증자 r2 VERIFIED 뒤)

```text
RESULT_DECISION = PASS_TO_USER_CHECK
EXTRA_CHANGES = ACCEPTED 5/5
SYNC_CONFLICT_POLICY = ACCEPTED
FUNCTIONAL_REWORK = NONE
PLAN_RESULT_RESUBMISSION = NOT_REQUIRED
STEP_CLOSED = NO
```

> 지시문 외 변경 5건은 모두 수용합니다. 처리 문구만 앞서 정한 아래 표현으로 반영하면 됩니다.
>
> | 코드 | 확정 문구 |
> |---|---|
> | `sent` | 알림 본문에 포함 |
> | `suppressed` | 반복 알림 생략 |
> | `cut_by_section_cap` | 구역별 항목 수 제한으로 제외 |
> | `cut_by_daily_cap` | 하루 알림 횟수 제한으로 제외 |
> | `not_selected` | 이번 알림에 포함 안 됨 |
> | `data_unavailable` | 자료 문제로 판단 보류 |
>
> WAL 보조 파일 생성 가능성도 수용합니다. 문서의 '원격 파일 변경 0'은 **'애플리케이션의 원장 쓰기 0·원장 행 불변, SQLite 보조 파일 생성 가능'**으로 정확히 적으면 됩니다. 코드 재작업 사항은 아닙니다.
>
> 남은 것은 실제 사용 확인입니다.
>
> - 오늘: 문구 반영, 메뉴·빈 화면·실패 표시 확인, 커밋·push 준비
> - 내일 09:35 이후: POC5-01B 운영 확인과 실제 알림 동기화 확인
> - POC5-02 배포·첫 성숙 실행 뒤: 실제 가격 결과 조회 확인
>
> 문구 변경 때문에 전체 검증을 다시 돌리거나 RESULT를 재제출할 필요는 없습니다. 관련 화면 테스트만 확인하면 됩니다. 커밋·push는 개발자가 판정을 기록한 뒤 사용자 승인으로 진행하십시오.
>
> **사용자 평가가 없는 알림도 보존·조회·향후 ML에 사용하는 방향은 제대로 반영됐습니다.** 매일 평가를 입력해야 하는 작업은 없습니다.
