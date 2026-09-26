> **기록 정보** — 작성: 설계자(웹 GPT) · 전달: 사용자(2026-09-26) · 기록: 개발자(VSCode Claude). 아래는 설계자 전달문 원문 그대로다.
> 앞부분(검증자 의견 수용 범위)도 설계 범위를 정하는 내용이라 함께 기록했다. 개발자가 받은 설계는 `# POC5-00 — 운영 신호·판단 결과 원장 MASTER DESIGN` 부터다.
> 선행 상태: POC4 종료 문서의 설계자 대기 표시 정정(§0)은 커밋 `8bf843e6`(2026-09-26 push)으로 끝났다.
> 개발 PLAN: `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`
> **설계자 PLAN 판정(2026-09-26)** 원문은 이 문서 끝 `# 설계자 PLAN 판정` 절에 그대로 붙였다 — `PASS_WITH_MANDATORY_AMENDMENT` · Q1~Q30 확정 ·
> 사용자 승인(OCI 전용 원장 SQLite 생성 · PC 기존 `decision_evidence.sqlite` 테이블 추가 · 2026-09-26). 본문과 다른 곳은 판정이 우선한다.

검증자 의견은 일부 수용하되, **2~3개월 개발 중단은 수용하지 않겠습니다.** 지금은 기다릴 단계가 아니라, 기다리는 동안 자동으로 쌓일 기반을 만드는 단계입니다.

먼저 사실관계는 검증자가 알고 있던 9월 7일 상태가 낡았습니다.

* `market_briefing`: 재구현·검증 후 9월 15일부터 운영
* `holdings_briefing`: 3슬롯 운영
* `holdings_risk_alert`: 9월 21일 장중 급등락 정책 활성화, 9월 22일 7/7틱·실발송 4건
* 폐지된 것은 `spike_or_falling_alert`

9월 7일의 KOSPI 3개월 `+48.40%` 메시지를 다시 켠 것이 아닙니다. 그 구 메시지 경로는 폐기됐고, 현재 08:00 브리핑은 S&P500 방향과 KRX 기초지수를 쓰는 새 계약입니다.

## 검증자 의견 수용 범위

| 의견                        | 판정  |
| ------------------------- | --- |
| 실제 발송 중인 신호부터 확정          | 수용  |
| 결과를 보기 전에 채점 기준 고정        | 수용  |
| POC5 성공을 ML과 분리           | 수용  |
| 객관적 성과와 사용자 도움 여부 분리      | 수용  |
| POC5 구현 후 바로 2~3개월 개발 중단  | 미수용 |
| POC5 끝을 자동으로 새 ML 진입로로 연결 | 미수용 |

POC5는 지금 개발합니다. 이후 결과가 쌓이는 동안에는 UI·운영 개선 등 다른 작업을 진행할 수 있습니다. 기다림은 **성과 판정에만 필요**하지, 개발 전체를 멈출 이유는 아닙니다.

## 개발자 전달용 설계

# POC5-00 — 운영 신호·판단 결과 원장 MASTER DESIGN

## 0. 선행 상태

```text
POC4_STATUS         = COMPLETED_RESEARCH_REJECT
TRACK_A / TRACK_B   = CLOSED_REJECT
POC4-04 / 05        = NOT_OPENED_BY_KILL_GATE
CURRENT_ML_MODEL    = NONE
POC5_IMPLEMENTATION = NOT_STARTED
```

POC4 종료 문서의 설계자 대기 표시를 정정한 뒤 POC5 PLAN으로 진입한다.

## 1. 목적

POC5의 목적은 ML 개발이 아니다.

현재 실제 발송되는 신호를 발생 당시 상태 그대로 보존하고, 이후 가격 결과와 사용자의 도움 여부를 연결하는 `Decision Outcome Ledger`를 만든다.

```text
운영 신호 발생
→ 당시 입력·판정·메시지·전송 결과 고정
→ 결과 성숙일까지 대기
→ 객관적 가격 결과 자동 결합
→ 사용자 도움 여부 선택 입력
→ PC 화면에서 신호별 결과 확인
```

POC5 자체의 성공은 다음으로 정의한다.

* 운영 신호를 누락 없이 기록
* 미래값 없이 당시 상태를 고정
* 결과 성숙 후 자동 채점
* 객관적 성과와 사용자 피드백을 분리
* 현재 PUSH의 동작·문구·시각에 영향 없음

ML 재학습·모델 승격은 POC5 완료 조건이 아니다.

## 2. 현재 운영 신호 정본

문서만 믿지 말고 OCI의 cron·flag·history·state를 읽기 전용으로 대조한다.

```text
market_briefing
  08:00 · autosend=true · 2026-09-15 첫 발송
  현재 메시지는 미국장 방향으로 한국 개장 압력을 명시하므로 방향성 요소가 있음

holdings_briefing
  09:15 · 12:30 · 15:40 · autosend=true
  정기 상태 브리핑이며 모든 문장을 예측으로 취급하면 안 됨

holdings_risk_alert
  09:30~15:20 7틱 · autosend=true
  보유 급등락 + 사업군 진입 검토·회피 조건형
  일일 발송 상한 4건 · 지속 신호 억제 유지

spike_or_falling_alert
  폐지 · cron 0건 · 채점 대상 아님
```

9월 7일 구 시장 메시지와 현행 재구현 메시지는 서로 다른 `contract_version`으로 분리한다. 구 메시지의 KOSPI 3개월 값은 현행 채점 대상에 섞지 않는다.

## 3. 원장 구조

최소한 다음 다섯 개 개념을 분리한다.

1. `evaluation_run`

   * push kind, slot/tick, 실행시각, 계약 버전, 입력 기준일, 실행 결과
2. `signal_item`

   * ticker·사업군·보유 여부·상태·당시 수치·선정/억제 사유
3. `delivery`

   * sent/skipped/failed/partial, Telegram 성공 여부, 실제 본문 hash
4. `outcome`

   * 기준 가격, 평가 가격, 수익률, 최대 유리·불리 움직임, 성숙 상태
5. `user_feedback`

   * 도움 여부·사용자 행동·선택 메모. 객관적 outcome과 별도 저장

안정적인 `event_id`로 다섯 개를 연결한다. 본문 문자열이나 시각만으로 사후 추정해 연결하지 않는다.

기존 runtime history에서 정확한 연결키를 만들 수 없으면 임의로 복원하지 말고 `UNLINKABLE_LEGACY`로 기록한다.

## 4. 채점 계약

### 4.1 공통

* 결과가 아직 성숙하지 않았으면 `PENDING`; `0`으로 쓰지 않는다.
* 휴장일은 다음 실제 거래일 기준으로 계산한다.
* 가격 부재·상장폐지·거래정지는 별도 사유로 기록한다.
* 자연어 본문을 파싱하지 말고 구조화된 판정 필드를 우선한다.
* 구조화된 방향이 없는 문장에는 사후에 방향 label을 만들어 붙이지 않는다.
* suppressed·daily-cap·no-signal 회차도 분모 확인을 위해 기록하되 `sent`와 구분한다.

### 4.2 시장 브리핑

현행 문구가 말하는 대상이 다음 중 무엇인지 PLAN에서 코드로 확정한다.

* 한국 개장 갭 방향
* 장중 종가 방향
* 전일 종가 대비 당일 종가
* 단순 압력 정보로서 정확도 판정 불가

설계 문구만 보고 임의 선택하지 않는다. 생성기의 구조화된 방향·기준시각·대상 지수를 조사한다.

예측 대상이 명확할 때만 방향 적중률을 계산한다. 기초지수 목록은 별도로 1·5·20거래일 원시 성과를 기록하되 추천 적중률로 부르지 않는다.

### 4.3 보유 브리핑

정기 현황 설명을 전부 예측으로 채점하지 않는다.

* 명시적인 위험·관찰·선정 상태가 있는 항목만 상태별 결과를 집계
* 선택되지 않은 전체 보유 종목을 대조군으로 둘 수 있는지 조사
* 15:40 요약 줄은 운영 집계이며 투자 신호로 채점하지 않음

### 4.4 장중 급등락

상태별로 결과를 분리한다.

* 보유 급락·급등
* `ENTRY_REVIEW`
* `AVOID_DROP`
* `AVOID_SURGE`
* 관측됐지만 발송 상한에 잘린 신호
* 지속 신호로 억제된 항목

1·5·20거래일 수익률과 가능한 범위의 최대 유리·불리 움직임을 원시값으로 저장한다. “성공” 임계와 집계 규칙은 결과 분포를 보기 전에 설계자가 확정한다.

## 5. 사전등록과 과거 자료 구분

POC5 채점 계약 확정 이전의 이벤트는 성과 판정의 정본으로 사용하지 않는다.

```text
LEGACY_DIAGNOSTIC_COHORT
  계약 동결 전 기존 history
  정확히 연결 가능한 이벤트만 진단용 backfill
  POC5 성공·신호 유효성 판정에는 사용하지 않음

PRIMARY_LIVE_COHORT
  계약 동결 다음 거래일부터 생성
  이후 공식 평가에 사용
```

PLAN 단계에서는 기존 이벤트 수와 연결 가능 비율만 조사한다. 성공 임계값을 정하기 전에 과거 수익률 분포를 열어 보지 않는다.

## 6. 사용자 피드백

객관적 성과와 주관적 도움 여부를 합쳐 하나의 점수로 만들지 않는다.

최소 선택지는 다음과 같다.

```text
도움됨
보통
불필요하거나 혼란스러움
```

선택적으로 다음 행동을 기록할 수 있다.

```text
매매 없음
추가 검토
매수
매도
보유 유지
```

자유 메모는 선택 사항이다. 피드백 미입력은 부정 평가가 아니다.

Telegram 상호작용을 새로 만들지는 않는다. 기존 PC 화면에서 최근 수신 메시지에 1~2번 클릭으로 남길 수 있는 위치를 먼저 조사한다. 별도 Telegram callback이 필요하면 중단하고 설계자에게 보고한다.

## 7. PC와 OCI 책임

```text
OCI
  운영 실행·신호·전송 사실 기록
  이미 적재된 가격으로 성숙한 raw outcome 계산 가능 여부 조사
  ML 학습·모델 선택 금지

PC
  원장 조회·결과 집계·사용자 피드백
  신호 종류별 비교 화면
  향후 연구 가설 작성
```

PC가 꺼져 있어도 이벤트가 누락되면 안 된다. 다만 신규 cron이나 운영 DB 테이블이 필요한지는 PLAN에서 조사하고 설계자 승인 전 변경하지 않는다.

## 8. 단계

```text
POC5-00  MASTER PLAN·사실조사
POC5-01  불변 event ledger + 운영 실행 연결
POC5-02  결과 성숙·자동 채점 + legacy 진단 backfill
POC5-03  PC 결과 조회·사용자 피드백 UI
POC5-04  운영 신호 리뷰 리포트
```

POC5-01~03은 결과가 20일 쌓이기 전에도 구현·검증할 수 있다.

POC5-04의 신호 유효성 결론만 표본 성숙을 기다린다. 기다리는 동안 다른 UI·운영 개선 작업 진행을 막지 않는다.

## 9. 금지 범위

* 현행 PUSH 문구·시간·임계·억제·상한 변경
* 새로운 매수·매도 추천
* ML 학습·RF/XGBoost/LightGBM 재개
* outcome을 보고 성공 기준 변경
* 누락된 과거 신호를 가격 데이터로 역생성
* 테스트의 라이브 DB·상태 파일 쓰기
* 실제 Telegram 발송
* OCI write·cron 변경·배포
* 사용자 피드백을 모델 label로 즉시 사용

## 10. POC5-00 PLAN 필수 사실조사

1. 세 운영 push kind의 실제 cron·flag·최근 이력
2. 메시지와 runtime record를 잇는 기존 ID
3. signal item의 구조화 필드와 contract version
4. sent·suppressed·no-signal·daily-cap 기록 위치
5. 기존 history의 기간·건수·정확한 연결 가능 비율
6. 1·5·20일 outcome 계산에 쓸 가격 source
7. 시장 브리핑의 정확한 예측 대상
8. 보유 브리핑에서 실제 예측으로 볼 수 있는 필드
9. 장중 상태별 outcome 정의 가능성
10. PC·OCI DB 위치와 신규 테이블 필요 여부
11. 기존 화면에서 피드백 카드를 놓을 자연스러운 위치
12. PC 미가동 중 자동 outcome 생성 방법
13. 계약 동결 시각과 `PRIMARY_LIVE_COHORT` 시작일
14. 최초 리뷰에 필요한 표본 수·거래일 제안과 근거
15. KS-10·라이브 경계·외부 호출 위험

PLAN 조사에서는 코드·DB·cron·flag·OCI·Telegram을 변경하지 않는다.

## 11. 완료 기준

POC5 구현 완료와 신호 성과 판정을 분리한다.

```text
IMPLEMENTATION_STATUS = DONE
COLLECTION_STATUS     = COLLECTING
SIGNAL_EFFECTIVENESS  = NOT_YET_MEASURED
ML_REENTRY            = NOT_DECIDED
```

다음 조건이면 POC5 구현은 완료다.

* 운영 대상 3종과 폐지 1종이 정확히 구분됨
* 신규 이벤트 100%가 안정적인 ID로 원장에 연결됨
* 미래 결과가 이벤트 당시 snapshot을 변경하지 않음
* outcome 성숙·결측·휴장 처리가 재현 가능
* objective outcome과 user feedback이 분리됨
* 현행 PUSH 회귀 0
* 테스트 중 라이브 DB·외부 호출·실발송 0
* 전체 회귀·KS-10 통과
* 사용자 실화면 확인 완료

POC5 완료가 새 ML 개발을 자동 승인하지 않는다. 새 ML 연구는 운영 결과에서 독립적인 가설이 생긴 뒤 별도 설계자·사용자 결정으로만 연다.

## 12. 즉시 중단 조건

* 현행 메시지 생성이나 발송 순서를 변경해야 함
* 기존 이벤트에 안정적인 연결키를 만들 수 없음
* 운영 DB를 테스트가 직접 변경
* outcome 계산에 신규 외부 API가 필요
* 과거 결과를 본 뒤 성공 기준을 정해야 함
* Telegram callback·신규 공개 API·신규 cron이 필요
* 사용자 피드백 입력이 기존 발송 성공 여부에 영향
* POC5 안에서 ML 모델을 다시 열어야 함

먼저 `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md`에 본 설계를 기록하고, 사실조사를 포함한 `docs/ai_plan/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md`을 제출한다. PLAN 판정 전 구현하지 않는다.

이 설계라면 개발은 지금 계속됩니다. 다만 “모델을 하나 더 붙이는 개발”이 아니라, 앞으로 무엇을 개선해야 하는지 실제로 알려 주는 기반을 만드는 개발입니다. POC5 결과가 쌓이는 동안 다른 UI·운영 개선을 병행할 수 있으므로 프로젝트가 멈추는 구조도 아닙니다.

---

# 설계자 PLAN 판정 (2026-09-26 · 설계자 원문 · 사용자 전달)

> 사용자 승인(2026-09-26 · 사용자 원문 "두 항목 모두 승인합니다."): 아래 `USER_APPROVAL_REQUIRED` 두 항목 — OCI 전용 SQLite 생성 · PC 기존 `decision_evidence.sqlite` 신규 테이블 추가.

[PLAN](sandbox:/workspace/scratch/0f5b1f431bc1/upload/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_PLAN_V1.md)을 전부 확인했습니다.

결론은 `PASS_WITH_MANDATORY_AMENDMENT`입니다. POC5는 ML을 다시 시도하는 단계가 아니라, 현재 운영 신호·결과·사용자 판단을 자동으로 축적하는 기반입니다. 데이터가 쌓이기를 기다리는 동안에도 POC5-01~03 개발은 계속합니다.

## 핵심 확정

1. 기존 메시지·시간·임계값은 바꾸지 않습니다.
2. 과거 종목별 신호는 복원하지 않고 `UNLINKABLE_LEGACY`로 둡니다.
3. POC5에서는 신호를 성공/실패로 재단하지 않습니다. 1·5·20일 원시 결과와 사용자 피드백을 별도로 기록합니다.
4. 08:00 브리핑에는 한국 시장의 명확한 예측 대상이 없으므로 방향 적중률을 만들지 않습니다.
5. 현재가를 보고 판단하는 신호의 공식 기준가격은 장 마감 종가가 아니라 메시지 생성 당시 가격입니다. 종가는 비교용 보조값으로 저장합니다.
6. 운영 DB와 섞지 않고 전용 판단 원장을 사용합니다.
7. 신규 이벤트 100% 기록의 모집단을 “이미 DB에 남은 실행”으로 축소하는 안은 승인하지 않습니다. 실행 진입부터 추적하고 누락은 명시적인 gap으로 남겨야 합니다.

## Q1~Q30 판정

| 질문  | 확정                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | 과거 실행 단위 연결은 허용. 과거 종목 단위는 `UNLINKABLE_LEGACY`.                                                                                                                  |
| Q2  | 승인된 POC5 구현·수동 배포는 §9 금지 대상이 아님. cron 추가는 금지.                                                                                                                    |
| Q3  | `127.0.0.1` 전용 API는 공개 API가 아님.                                                                                                                                  |
| Q4  | 실제 코드 값 `AVOID_CHASE`를 정본으로 사용. 이름 변경 없음.                                                                                                                        |
| Q5  | OCI에 전용 `state/decision/decision_evidence.sqlite` 생성. `runtime_state.sqlite`와 분리. 짧은 트랜잭션·WAL·busy timeout 적용.                                                   |
| Q6  | POC5-01a에서 러너를 먼저 분리. 이후 실행 진입 시 `event_id`와 초기 행을 만들고 최외곽에서 종료 상태를 확정. 기록 실패는 PUSH를 막지 않되 명시적인 오류·대조 보고를 남김.                                                    |
| Q7  | flow 반환값에 기록용 payload를 additive로 추가. 본문 byte·판정·순서 동일 테스트 필수.                                                                                                    |
| Q8  | 이미 계산된 보유·27개 사업군의 비선정 결과도 기록. 추가 조회·재계산은 금지.                                                                                                                    |
| Q9  | 분할 전 전문과 SHA-256을 모두 보존. 파일 권한과 DB 접근은 로컬 사용자 한정.                                                                                                                |
| Q10 | 실행 진입 시 고유 `event_id` 발급. `run_id`·`started_at`은 보조키.                                                                                                            |
| Q11 | `mode=send`만 원장 대상. 수동 send는 `off_schedule=true`로 기록하고 PRIMARY 통계에서 제외.                                                                                          |
| Q12 | kind별 계약 버전을 코드 상수로 관리. legacy 버전은 진단 전용.                                                                                                                        |
| Q13 | **(d)** 방향 적중률을 계산하지 않음. S&P500 상태와 한국 시장 원시 결과만 병기.                                                                                                             |
| Q14 | FLAT/NONE·동일 미국 세션·연휴 직후·입력 지연을 별도 태그로 기록.                                                                                                                       |
| Q15 | ETF는 KRX 무조정 종가, 비ETF 보유는 기존 FDR 계열. source와 분배락 포함 여부를 반드시 기록.                                                                                                  |
| Q16 | 장중·보유 신호의 PRIMARY t0는 메시지 생성에 실제 사용한 현재가. 신호일 종가와 전일 종가는 보조 비교값. 현재가 누락 시 종가로 대체하지 않음.                                                                           |
| Q17 | 실제 가격 적재일 순서로 +1/+5/+20을 계산. 2027 CSV를 선행조건으로 만들지 않고 기존 snapshot 우선·평일 fallback 정책 유지.                                                                           |
| Q18 | 가격 대체 금지. `PRICE_MISSING`·`UNTRACKED_AFTER_EXIT` 등으로 기록. 거래량 필드 추가는 이번 단계에서 하지 않음.                                                                               |
| Q19 | 같은 상태의 반복 노출은 보조 기록. 신규 진입·구간 악화·회복 후 재진입을 PRIMARY 전이 이벤트로 셈.                                                                                                    |
| Q20 | 원시 결과만 저장. 상태별 “유리한 방향”과 단일 성공 라벨은 만들지 않음.                                                                                                                       |
| Q21 | 원장 화면을 열 때 1회 동기화 + 수동 새로고침. PC 전체 기동 시 자동 SSH 조회는 하지 않음.                                                                                                        |
| Q22 | PC는 이미 존재하는 `state/decision/decision_evidence.sqlite`에 원장·피드백 테이블을 추가. `runtime_state.sqlite` 사용 및 새 PC DB 생성 모두 불필요.                                            |
| Q23 | 우선 「오늘의 투자 점검」 안에 새 구역으로 배치. 메뉴를 14개로 늘리지 않음. 이름은 `받은 알림 기록`, 상세 접기 영역은 `신호 결과 원장`.                                                                              |
| Q24 | `sent`와 실제 일부가 전달된 `partial`만 피드백 대상. append-only, 미입력 행 없음, 가격 결과는 피드백 전에 노출하지 않음.                                                                              |
| Q25 | 07:20 배치 후 격리된 단계로 성숙 결과 계산. 실패해도 배치 status·가격 적재·08:00 실행에 영향 없음.                                                                                               |
| Q26 | POC5-01a·01·02·03마다 짧은 PLAN 제출. MASTER 질문을 다시 반복하지 않음.                                                                                                           |
| Q27 | POC5가 기존 `Decision Outcome Ledger` 미결 항목을 이어받아 완성. 별도 중복 원장을 만들지 않음.                                                                                             |
| Q28 | 운영 계약 정정·코드 pull 후 첫 거래일부터 PRIMARY. 10거래일 뒤 R0 수집 점검. R1은 정기 기술통계로 내고, 겹치는 날짜는 날짜 블록 bootstrap 사용. 다음 개발을 기다리게 하지 않음.                                            |
| Q29 | 성공 임계 없음. kind·state·contract_version·horizon별 원시 분포를 보고. 같은 종목·같은 상태·같은 날은 첫 노출을 PRIMARY, 반복은 secondary, 악화·회복 후 재진입은 새 사건. 잘림·억제는 관측 모수에는 포함하되 전달 효과 모수에서는 제외. |
| Q30 | 운영 3종만 허용하고 spike는 legacy에서도 제외. 낡은 OCI 상태 화면은 POC5와 분리된 작은 수정으로 먼저 처리.                                                                                          |

## PRIMARY 시작 전에 바로 고칠 운영 항목

현재 메시지 계약이 중간에 바뀌면 원장 데이터가 섞이므로 아래는 PRIMARY 시작 전에 정리해야 합니다.

* 08:00 기초지수 구역 복구: 공식 CSV 갱신 및 정합성 검증
* 폐지된 spike를 요구하는 OCI 상태 화면 수정
* 장중 본문의 `현재가 —`가 실제로 발생하는지 확인 후 결함이면 수정
* 상한에 잘려 발송되지 않은 보유 급락이 당일 억제되는 문제 수정
* Telegram 실패가 `no_signal`로 집계되는 문제 수정
* `holdings_risk_alert.message_text_length=0` 기록 수정
* KOSPI 09-17 정지는 원인 조사 후 복구 또는 명시적 stale 처리

PC DB의 의심 기록 12행은 출처가 확정되지 않았으므로 삭제하지 않습니다. 전용 원장을 사용하면 새 데이터에도 섞이지 않습니다.

## 개발자에게 전달할 판정

```text
POC5-00 PLAN_DECISION = PASS_WITH_MANDATORY_AMENDMENT

IMPLEMENTATION_ORDER
  1. POC3 운영 정정 소형 PLAN
  2. POC5-01a 러너 기계 분리
  3. POC5-01 운영 원장
  4. POC5-02 outcome 성숙
  5. POC5-03 PC 동기화·피드백
  6. POC5-04 R0/R1 리포트

POC5_PURPOSE
  운영 신호·원시 결과·사용자 피드백 축적
  ML 재개 아님
  성공/실패 label 생성 아님
  기다림은 성과 해석에만 필요하며 개발을 차단하지 않음

MARKET_DIRECTION_ACCURACY = NOT_DEFINED
OUTCOME_POLICY            = RAW_ONLY
PRIMARY_T0                = RUNTIME_QUOTE_USED_IN_MESSAGE
LEGACY_ITEM_LINKAGE       = UNLINKABLE_LEGACY

OCI_LEDGER_DB = state/decision/decision_evidence.sqlite (신규)
PC_LEDGER_DB  = state/decision/decision_evidence.sqlite (기존 파일 확장)
RUNTIME_STATE_DB_CHANGE = 0

USER_APPROVAL_REQUIRED
  OCI 전용 SQLite 생성
  PC 기존 decision_evidence.sqlite 신규 테이블 추가

PLAN 문서에는 Q1~Q30 확정과 위 필수 보완을 반영한 뒤 커밋한다.
운영 결과·과거 수익률은 계속 열지 않는다.
```

사용자님께서는 마지막으로 **OCI 전용 원장 DB 생성과 PC 기존 판단 DB의 테이블 추가**만 승인해 주시면 됩니다. 저는 두 항목 모두 승인하는 것을 권합니다.
