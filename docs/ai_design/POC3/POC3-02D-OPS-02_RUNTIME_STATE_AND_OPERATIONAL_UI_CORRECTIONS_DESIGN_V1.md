# POC3-02D-OPS-02 — RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS DESIGN V1

작성: 설계자(원문) · 기록: 개발자(VSCode Claude) · 기록일: 2026-09-27 · 갱신: 2026-09-28(판정 원문 · 3-4 문구 확정 원문 추가) · 전달: 사용자

```text
STEP_ID       = POC3-02D-OPS-02
STEP_NAME     = 장중 전달 상태·운영 UI 정합성 보완
PREDECESSOR   = POC3-02D-OPS-01
SUCCESSOR     = POC5-01A
PLAN          = docs/ai_plan/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_PLAN_V1.md
RESULT        = docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md
진행 방식      = 사실조사 · PLAN 기록 뒤, 중단 조건이 없으면 설계자 재판정 없이 구현까지(설계자 지시 STEP 3)
PLAN_Q1~Q6     = CONFIRMED (설계자 판정 2026-09-28 · 문서 끝 원문) — 3-2 필드명 `last_delivered_state` · 3-4 기존 응답 선택 필드 승인
3-4_WORDING    = CONFIRMED (2026-09-28 · 사용자 초안(목업) 승인 + 설계자 문구 규칙 · 문서 끝 원문) · 구현 화면 확인은 결과서 IMPLEMENTED_UI_CHECK
RESULT_DECISION = PASS_WITH_MANDATORY_AMENDMENT (설계자 2026-09-28 · 문서 끝 원문) — RESULT 판정 Q1~Q3(구파일 다음 정상 저장 · 회복 → 미전달 Y → X · KOSPI 최신성) APPROVED · 필수 보완 M1 · M2 반영
```

이 문서는 설계자 지시 원문을 그대로 옮긴 기록이다. 원문은 OPS-01 운영 확인(STEP 0~2)과 OPS-02(STEP 3~6)를 한 지시로 묶었다. OPS-01 부분의 처리 기록은 `docs/STATE_LATEST.md` 와 `docs/handoff/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_HANDOFF_2026-09-27.md` 에 있다.

> 개발자 기록(2026-09-27): §0 '첫 거래일 2026-09-28' 을 확인하다가, 저장소 거래일 캘린더(`state/market_meta/krx_trading_days_2026.csv`)가 09-28 을 '추석 대체공휴일'로 빼고 있음을 발견했다. 그대로면 09-28 08:00 시장 브리핑이 휴장일로 건너뛴다. 사용자 승인으로 같은 날 정정했다(커밋 `3e13fbec` · 캘린더 1줄 추가 · 전체 회귀 2,347 passed). OCI 반영은 09-28 07:15 전 재 pull.

---

# 설계자 지시 원문 (2026-09-27 · 사용자 전달)

아래 지시문 하나만 개발자에게 전달하시면 됩니다. 9월 28일 운영 확인과 OPS-02를 병행하도록 정리했습니다.

대상: 개발자

# POC3-02D 진행 통합 지시 — OPS-01 운영 확인 + OPS-02 착수

## 0. 일정 오류 정정

`2026-09-29 첫 거래일`은 잘못된 기록입니다.

```text
FIRST_TRADING_DAY_AFTER_DEPLOY = 2026-09-28
OPS01_RUNTIME_CHECK            = 2026-09-28 07:20 · 08:00
```

저장소에서 `2026-09-29`를 첫 거래일 또는 첫 운영 확인일로 쓴 곳을 찾아 **그 주장만** `2026-09-28`로 정정하십시오. 다른 의미의 9월 29일 기록은 건드리지 마십시오.

KRX CSV 출처는 사용자가 확인했습니다.

```text
SOURCE          = KRX Data Marketplace
MENU            = 증권상품 > ETF > 전종목 기본정보
DOWNLOADED_AT   = 2026-09-27
DATE_MEANING    = 다운로드·메타정보 스냅샷 날짜
TRADING_ASOF    = 해당 없음(추석 연휴 중 다운로드)
USER_CONFIRMED  = YES
```

결과서의 “파일명에서 읽음”을 사용자 확인 완료로 정정하십시오.

---

# STEP 1. PC 백엔드 재기동과 화면 확인 — 지금 수행

기존 표준 절차로 PC 백엔드만 재기동하십시오. 설정값과 자동발송 플래그는 변경하지 마십시오.

확인 항목:

1. 「OCI 운영 상태」가 새 필수 목록을 사용한다.
2. 운영 PUSH 3종이 정상으로 표시된다.

   * `market_briefing`
   * `holdings_briefing`
   * `holdings_risk_alert`
3. 폐지된 `spike_or_falling_alert`를 필수 스케줄로 요구하지 않는다.
4. PC 자동발송 플래그는 모두 `false`다.
5. 화면 결과와 재기동 시각을 기록한다.

이 확인은 OCI 변경이나 Telegram 발송을 수반하면 안 됩니다.

---

# STEP 2. OPS-01 첫 운영 실측 — 2026-09-28

## 2-1. 07:20 배치

정규 스케줄이 먼저 실행되게 두십시오. 예정 시각 전에 수동 실행하지 마십시오.

07:20 이후 읽기 전용으로 다음을 확인하십시오.

```text
BATCH_STATUS
BATCH_REASON
SELECTED_CSV
CSV_SHA256
CSV_ROWS
CSV_REJECTED_ROWS
API_ONLY_COUNT
CSV_ONLY_COUNT
META_CONSISTENCY_STATUS
KOSPI_AS_OF
KOSPI_STATUS
KOSPI_REASON
KOSPI_TRADING_DAY_LAG
REFRESH_DUE
```

기대값:

```text
SELECTED_CSV       = krx_etf_basic_20260927.csv
CSV_SHA256         = 0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314
CSV_ROWS           = 1175
CSV_REJECTED_ROWS  = 0
API_ONLY_COUNT     = 0
```

예상과 다르면 임의 재실행·DB 수정·파일 교체를 하지 말고 실제 값과 원인을 보고하십시오.

## 2-2. 08:00 시장 브리핑

스케줄 실행 뒤 다음을 확인하십시오.

```text
RUN_STATUS
RUN_REASON
TELEGRAM_ATTEMPTED
TELEGRAM_SENT
PARTIAL_DELIVERY
MESSAGE_COUNT
DOMESTIC_BASIS_DATE
INDEX_SECTION_PRESENT
INDEX_SECTION_OMISSION_REASON
```

완료 기준:

* CSV/API 불일치 8종 때문에 기초지수 구역이 빠지지 않는다.
* 기초지수 구역이 없다면 정확한 다른 Gate 사유가 기록된다.
* 동일 내용이라는 이유의 `no_change` 억제가 발생하지 않는다.
* 수동 재발송은 하지 않는다.
* OCI DB·flag·cron을 변경하지 않는다.

## 2-3. OPS-01 종료 기록

07:20·08:00이 정상이라면 `STATE_LATEST`를 실제 측정값으로 2차 갱신하십시오.

```text
POC3-02D-OPS-01 = IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED
```

문서만 별도 커밋·push해도 되며, 코드 재배포는 필요 없습니다. 실패가 있으면 위 상태로 닫지 말고 `OPERATION_CHECK_FAILED`와 실제 사유를 기록하십시오.

---

# STEP 3. POC3-02D-OPS-02 즉시 착수 — OPS-01 실측과 병행

```text
STEP_ID      = POC3-02D-OPS-02
STEP_NAME    = 장중 전달 상태·운영 UI 정합성 보완
PREDECESSOR  = POC3-02D-OPS-01
SUCCESSOR    = POC5-01A
```

파일명:

```text
docs/ai_design/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_DESIGN_V1.md
docs/ai_plan/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_PLAN_V1.md
docs/ai_result/POC3/POC3-02D-OPS-02_RUNTIME_STATE_AND_OPERATIONAL_UI_CORRECTIONS_RESULT.md
```

사실조사와 PLAN을 먼저 기록하되, 아래 중단 조건이 없으면 별도 설계자 재판정을 기다리지 말고 구현까지 진행하십시오.

## 3-1. OCI 상세 링크 수정

「오늘의 투자 점검」의 OCI 안내 링크를 실제 「OCI 운영 상태」 화면으로 연결하십시오.

* 신규 메뉴를 만들지 않는다.
* 기존 「개발·실험용」 화면으로 보내지 않는다.
* 링크 문구도 실제 도착 화면과 일치시킨다.
* 라우팅 관통 테스트를 추가한다.

## 3-2. 전달 상태 저장 계약 수정

모든 장중 신호에 다음 계약을 동일하게 적용하십시오.

1. 관측 상태와 발송 완료 상태를 구분한다.
2. 발송 후보 판단은 **마지막으로 성공 전달된 상태**를 기준으로 한다.
3. 관측만 됐다는 이유로 발송 완료 상태를 전진시키지 않는다.
4. 구역 상한에 잘려 본문에 포함되지 않은 신호는 다음 틱의 후보로 남긴다.
5. Telegram 전송 실패 시 본문에 포함됐던 신호도 발송 완료로 저장하지 않는다.
6. 부분 전송이면 전체 신호의 발송 완료 상태를 저장하지 않는다.
7. 장중 본문 조립 뒤 진단·집계 예외가 발생해 구 본문만 발송됐다면 장중 신호를 발송 완료로 저장하지 않는다.
8. 전체 전송 성공 시에만 실제 본문에 포함된 신호의 발송 완료 표식을 저장한다.
9. 관측 상태는 기존 회복·지속 판단 계약을 유지하되, 미전달 신호를 억제하는 근거로 사용하지 않는다.
10. cooldown·일일 상한·회차당 상한·임계값은 변경하지 않는다.

최소 재현 항목:

* 구역 상한으로 잘림
* `telegram_send_error`
* `partial_delivery`
* 장중 조립 후 diagnostics 예외
* 장중 조립 후 tally/summary 예외
* 다음 틱에서 미전달 상태 변화가 다시 후보가 됨
* 성공 전달 뒤에는 정상적으로 억제됨

## 3-3. 낡은 fingerprint 역검증 정리

2026-09-18 이후 정기 PUSH는 내용이 같아도 거래일·슬롯마다 발송하는 것이 현재 계약입니다.

따라서 다음을 정정하십시오.

* `reverse_verify_guards.py`의 옛 “동일 fingerprint 반복 억제” 검증
* 목업 ⑦의 “동일 fingerprint 미발송” 제목과 설명
* 현재 계약을 설명하는 결과서·주석·테스트 문구

새 검증 계약:

* 다음 거래일의 동일 fingerprint 시장 브리핑은 발송한다.
* 보유 브리핑도 각 고정 슬롯에서 내용이 같아도 발송한다.
* 같은 실행이나 같은 슬롯의 중복 실행을 막는 기존 실행 중복 보호는 약화하지 않는다.
* 사건형 `holdings_risk_alert`의 동일 위험 억제는 유지한다.
* 과거 계약 기록은 삭제하지 말고 적용 기간을 명시한다.

## 3-4. KOSPI stale 화면 표현

PC 화면에서 다음 상태를 구분하십시오.

* 정상 최신
* source stale
* provider/fetch 실패
* 아직 평가되지 않음
* 휴장 또는 거래일 아님

`source_stale`을 성공으로 표시하거나 단순 “데이터 없음”으로 뭉개지 마십시오. 가능한 경우 다음을 함께 표시하십시오.

```text
KOSPI_AS_OF
TRADING_DAY_LAG
STATUS
REASON
```

운영 판정 로직과 임계값은 변경하지 않고 표시만 실제 상태와 맞춥니다.

---

# STEP 4. 변경 제한

다음은 금지합니다.

```text
NEW_API              = 0
NEW_EXTERNAL_SOURCE  = 0
NEW_DEPENDENCY       = 0
NEW_DB_TABLE         = 0
NEW_PUSH_KIND        = 0
CRON_CHANGE          = 0
FLAG_CHANGE          = 0
LIVE_SEND            = 0
OCI_WRITE            = 0
```

추가 제한:

* 알림 임계값·cooldown·일일 상한·스케줄 변경 금지
* 사용자 소유 `INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 변경 금지
* 운영 러너는 현재 646줄을 기준으로 한다.
* 648줄을 넘기지 말고, 증가가 필요하면 모듈로 분리한다.
* 운영 파일과 상태 파일의 전후 hash를 기록한다.

다음 중 하나라도 필요하면 구현을 중단하고 보고하십시오.

* 신규 DB 또는 스키마 변경
* 신규 API·외부 데이터·의존성
* cron 또는 운영 flag 변경
* 기존 임계값·발송 상한 변경
* 현재 관측 상태와 발송 상태를 분리할 수 없는 구조적 충돌
* KS-10 트리거 발생

---

# STEP 5. 검증 기준

최소 검증:

1. 관련 계약 테스트
2. 실제 `run()` 경로 관통 테스트
3. 위 5개 실패·잘림 시나리오 무력화 검증
4. 프론트 라우팅·상태 표시 테스트
5. 백엔드 전체 회귀
6. 프론트 전체 회귀·타입 검사·lint
7. black·flake8
8. KS-10 전수 검사
9. PC 라이브 상태·운영 DB 전후 hash 동일
10. OCI 쓰기·Telegram 발송 0건

결과서에는 다음을 분리해 보고하십시오.

```text
OBSERVATION_STATE
DELIVERY_STATE
ACTUALLY_INCLUDED_SIGNALS
SUCCESSFULLY_DELIVERED_SIGNALS
PENDING_FOR_NEXT_TICK
```

---

# STEP 6. 종료 순서

1. 2026-09-28 OPS-01 운영 확인 및 `STATE_LATEST` 2차 갱신
2. OPS-02 구현·전체 검증
3. 설계자 RESULT 판정
4. 검증자 독립 검증
5. VERIFIED 뒤 커밋·push 승인 요청
6. OCI pull 및 운영 확인
7. `POC5-01A PRIMARY` 시작

OPS-01 운영 확인은 OPS-02 개발의 선행조건이 아닙니다. 두 작업을 병행하십시오. 다만 `POC5-01A` 운영 시작은 OPS-02 검증·배포가 끝난 뒤로 둡니다.

---

# 설계자 판정 — OPS-01 종료 · OPS-02 Q1~Q6 (2026-09-28 · 설계자 원문 · 사용자 전달)

## 설계자 판정

```text
POC3-02D-OPS-01 = CLOSED
STATUS           = IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED
DOC_PUSH         = APPROVED
POC3-02D-OPS-02  = CONTINUE
```

9월 28일 정상 개장 판정도 공식 월력요항과 일치합니다. 추석 연휴는 9월 24~27일입니다. ([www.kasi.re.kr][1])

`1489896d`는 문서만 바뀐 커밋이므로 **push해도 됩니다.** OCI pull은 필요 없습니다.

## OPS-02 Q1~Q6 판정

### Q1 — 상태 파일 필드 추가

**승인합니다. 중단 조건에 해당하지 않습니다.**

* DB 변경이 아니라 기존 JSON 상태 파일의 하위 호환 필드 추가입니다.
* 필드명은 `last_delivered_state`로 고정합니다.
* `schema_version=1`을 유지해도 됩니다.
* `fingerprint`를 저장하는 것은 아닙니다.
* 설계 §15-2는 이번 계약으로 명시적으로 개정합니다.

구파일 호환 규칙:

```text
last_delivered_state 존재      → 그대로 사용
필드 없음 + last_sent_at 있음  → 기존 state를 마지막 전달 상태로 추정
필드 없음 + last_sent_at 없음  → null
```

읽기만으로 파일을 일괄 변환하지 말고, 다음 정상 저장 때 필드를 추가하십시오.

### Q2 — 조립 뒤 예외

**제안대로 승인합니다.**

장중 조립 뒤 예외가 발생해 구 본문만 발송됐다면:

* 장중 관측 상태 전진 안 함
* 장중 집계 안 함
* 장중 `sent_today` 증가 안 함
* 장중 발송 완료 상태 저장 안 함
* 오류는 실행 이력에 남김
* 구 본문에 실제 포함된 기존 보유 급락 D*만 전송 성공 계약에 따라 저장

전송 실패·부분 전송이면 D*도 발송 완료로 저장하지 않습니다.

### Q3 — X → 미전달 Y → X

**억제가 맞습니다.**

마지막 성공 전달 상태가 X이고 현재 다시 X라면 새 정보가 아니므로 억제합니다. 이후 Y가 다시 나타나면 마지막 전달 상태 X와 다르므로 다시 후보가 됩니다.

### Q4 — 기존 API 응답 확장

**`NEW_API=0` 위반이 아닙니다. 승인합니다.**

단, 다음 조건을 지켜야 합니다.

* 신규 엔드포인트 생성 금지
* 기존 필드 의미 변경 금지
* 추가 필드는 선택 필드로 제공
* 외부 호출 추가 금지
* 응답 생성 시 이미 보유한 DB·상태만 사용
* Dashboard에서 `/market/topn/latest` 자동 호출을 부활시키지 않음
* 해당 API를 이미 호출하는 화면에서만 표시

KS-1을 우회해 첫 화면 자동 조회를 다시 붙이면 안 됩니다.

### Q5 — 아직 평가되지 않음

두 상태를 합치지 마십시오.

| 실제 상태           | 화면 문구        |
| --------------- | ------------ |
| 화면 요청 진행 중      | `확인 중`       |
| 실행·수집 이력이 전혀 없음 | `아직 평가되지 않음` |
| 수집은 했지만 값이 없음   | `수집 결과 없음`   |
| 데이터가 오래됨        | `기준일 지연`     |
| 호출 실패           | `자료원 확인 실패`  |

### Q6 — lag 기준

화면이 직접 계산하지 말고 **백엔드가 C7 공용 거래일 계산으로 산출한 lag를 우선 사용**하십시오.

부득이하게 KODEX200 적재일을 대체 축으로 사용할 경우에만:

```text
KODEX200 거래일 기준 4일 지연
```

처럼 명시하십시오. 이 값은 `KOSPI_TRADING_DAY_LAG`와 같은 값인 것처럼 취급하면 안 됩니다.

## 다음 순서

1. `1489896d` push
2. Q1~Q6을 설계서·PLAN에 반영
3. OPS-02의 3-2·3-4 구현
4. 전체 회귀·무력화·프론트 검증
5. 결과서 제출
6. 설계자 판정 → 검증자
7. VERIFIED 후 커밋·push·OCI 적용
8. `POC5-01A` 시작

Telegram은 가능하면 오늘 메시지 한 건만 확인해 주세요. `기준` 다음 줄이 `현재가 2026-09-28 HH:MM` 형태라면 C3도 운영 확인 완료로 기록하면 됩니다. 다르게 보이면 그 한 줄만 그대로 전달하면 됩니다. 이는 `1489896d` push를 막는 조건은 아닙니다.

[1]: https://www.kasi.re.kr/publication/post/newsMaterial/32031?utm_source=chatgpt.com "한국천문연구원 | 고객참여|보도자료"

---

# 3-4 화면 문구 확정 (2026-09-28 · 사용자 초안(목업) 승인 + 설계자 문구 규칙 · 사용자 전달)

개발자가 화면 초안(두 화면 공용 · 상태별 배지 · 기준 줄 · 사유 줄)을 사용자에게 보였고, 사용자가 설계자 답을 붙여 '이대로 구현'으로 확정했다. 영문 KOSPI 경고 줄은 사용자가 '화면에서만 숨김'을 골랐다. 아래는 사용자 전달 원문이다.

> 이대로 구현인데 추가 설명이 있어서 Other를 선택했습니다.
>
> 네, 이전 답변은 개발자에게 넘기는 것이 맞습니다. 개발자가 지시를 제대로 읽고 화면 표현의 빈칸을 질문한 것입니다.
>
> 선택은 **1번 '이대로 구현'**입니다. 다만 휴장일과 문구 규칙을 아래처럼 확정해서 보내세요.
>
> 3-4 KOSPI 상태 표시는 **1번 '이대로 구현'**으로 확정합니다.
>
> 두 화면은 같은 상태 판정·문구 생성기를 공유하십시오.
>
> 1. 정상일
>
> * `정상` 배지는 표시하지 않는다.
> * 사유 줄도 표시하지 않는다.
> * 현재 수치와 함께 `KOSPI 기준일 2026-09-28`처럼 기준일만 표시한다.
>
> 2. 기준일 지연
>
> * 배지: `기준일 지연`
> * 기준 줄: `KOSPI 기준일 2026-09-17 · 4거래일 지연`
> * 사유 줄을 한 줄 표시한다.
> * 내부 코드인 `source_stale` 등을 그대로 노출하지 말고 사용자 문장으로 바꾼다.
>   예: `KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.`
>
> 3. 자료원 호출 실패
>
> * 배지: `자료원 확인 실패`
> * 마지막 정상 기준일이 있으면 함께 표시한다.
> * 사유: `KOSPI 원자료를 불러오지 못했습니다.`
>
> 4. 수집 이력 없음
>
> * 배지: `수집 결과 없음`
> * 사유: `저장된 KOSPI 자료가 없습니다.`
>
> 5. 평가 이력 없음
>
> * 배지: `아직 평가되지 않음`
> * 사유: `KOSPI 최신성 판정이 아직 실행되지 않았습니다.`
>
> 6. 화면 요청 진행 중
>
> * 배지가 아니라 로딩 상태 `확인 중`으로 표시한다.
> * 이를 `아직 평가되지 않음`과 합치지 않는다.
>
> 7. 휴장일
>
> * 중립 배지 `휴장일`을 표시한다.
> * 최근 KOSPI 기준일은 보여 준다.
> * 사유: `오늘은 국내 증시 휴장일입니다.`
> * 정상적인 직전 거래일 자료를 `기준일 지연`으로 경고하지 않는다.
>
> 8. 거래일 지연 계산
>
> * 백엔드가 C7 공용 계산으로 제공한 값을 우선 사용한다.
> * 화면이 KODEX200 날짜 축으로 대신 계산한 경우에는 반드시
>   `KODEX200 거래일 기준 N일 지연`으로 표시한다.
> * 두 값을 같은 `KOSPI_TRADING_DAY_LAG`인 것처럼 섞지 않는다.
>
> 사유 줄은 정상일에는 숨기고, 지연·실패·미평가·휴장 상태에서만 한 줄 표시하십시오. 기술 토큰이나 예외 원문은 화면에 노출하지 마십시오.

영문 경고 질문(「요즘 잘 오르는 ETF」 시장 배경 카드의 'KOSPI benchmark is stale … lag=2' — KODEX200 적재일 축이라 새 줄의 캘린더 축 지연과 숫자가 다르다) 사용자 선택: **KOSPI 경고만 숨김** — 화면에서만 숨기고 서버 응답은 바꾸지 않는다 · KODEX200 경고는 그대로 둔다.

---

# 설계자 RESULT 판정 — PASS_WITH_MANDATORY_AMENDMENT (2026-09-28 · 설계자 원문 · 사용자 전달)

판정은 **`PASS_WITH_MANDATORY_AMENDMENT`**입니다. 핵심 구현은 통과입니다. 재설계는 없고, 화면 문구 1건과 결과서 표현 1건만 바로잡은 뒤 사용자 화면 확인 → 검증자로 넘기면 됩니다.

POC3-02D-OPS-02 설계자 RESULT 판정

```text
RESULT                  = PASS_WITH_MANDATORY_AMENDMENT
CORE_IMPLEMENTATION     = PASS
Q1 / Q2 / Q3            = APPROVED
COMMIT_PUSH_OCI         = HOLD
NEXT                    = 필수 보완 2건 → 사용자 화면 확인 → 검증자
```

## 1. 판정 요청 3건

### Q1 — 구파일의 다음 정상 저장

개발자 해석을 승인합니다.

관측 저장도 정상 저장에 포함합니다. 구파일 entry의 `state`를 새 관측값으로 덮기 전에 추정한 기존 전달 상태를 `last_delivered_state`로 옮기는 것이 맞습니다.

* 읽기만으로 파일을 변환하지 않음
* 다음 실제 저장 시 변환
* 추정값을 그대로 옮길 뿐 전달 상태를 새 관측값으로 전진시키지 않음
* `schema_version=1` 유지
* DB 변경 아님

전송 성공 저장 때까지 기다려 배포 당일 결함을 한 번 허용하는 것보다 현재 구현이 계약 취지에 맞습니다.

### Q2 — 회복 → 미전달 Y → X 재진입

현재 구현을 승인합니다.

마지막 성공 전달 상태가 X이고, 회복 뒤 Y는 전달되지 않았으며, 다시 X가 cooldown 안에 들어오면 억제합니다. 사용자에게 마지막으로 전달한 상태와 같기 때문입니다.

```text
cooldown 이내 X 재진입 = 억제
cooldown 경과 후 X 재진입 = 발송
Y가 다시 나타남 = 마지막 전달 X와 다르므로 후보
```

미전달 Y가 회복 기록을 지워 즉시 재발송을 만들면 관측 상태가 다시 억제 근거가 되므로 현재 구현이 맞습니다.

### Q3 — KOSPI 최신성 판정

승인합니다.

```text
최신 = 운영 판정이 stale 아님
       AND C7 공용 캘린더 lag <= 1
```

* 적재 감지와 화면이 `benchmark_lag_trading_days`를 공유하는 방식 승인
* KODEX200 날짜 축으로 별도 계산하지 않는 방식 승인
* 화면 요청 실패를 `자료원 확인 실패`로 표시하는 방식 승인
* 공용 함수 이동 전후 본문과 기존 C7 판정 불변 조건 유지

## 2. 필수 보완 M1 — `수집 결과 없음` 사유 분리

결과서 §5에 적힌 알려진 한계를 그대로 두면 화면이 사실과 다른 설명을 할 수 있습니다.

같은 배지 `수집 결과 없음`을 유지하되 사유를 나누십시오.

```text
저장된 KOSPI 행 자체가 없음
→ 저장된 KOSPI 자료가 없습니다.

KOSPI 기준일은 있으나 수익률 산출값이 없음
→ KOSPI 수익률을 계산할 자료가 충분하지 않습니다.
```

새 상태나 새 API 필드는 만들 필요 없습니다. 현재 응답의 기준일·값 존재 여부로 구분하고 두 경우의 프론트 테스트를 추가하십시오.

프론트만 바뀌면 다음을 다시 확인합니다.

```text
vitest 전체
tsc
eslint
```

백엔드도 바꾸면 관련 계약 테스트와 백엔드 전체 회귀를 다시 실행하십시오.

## 3. 필수 보완 M2 — 결과서의 화면 확인 표현

결과서 머리말의 다음 표현은 실제 상태와 다릅니다.

```text
3-4 화면 문구 CONFIRMED
(사용자 화면 확인 + 설계자 문구 규칙)
```

현재 사용자는 문구 계약을 승인했지만 실제 구현 화면은 아직 확인하지 않았습니다. 다음처럼 분리하십시오.

```text
USER_UI_CONTRACT_APPROVED = YES
IMPLEMENTED_UI_CHECK      = PENDING
```

사용자가 두 화면을 확인한 뒤에만 다음으로 바꿉니다.

```text
IMPLEMENTED_UI_CHECK = PASSED
```

## 4. 사용자 화면 확인 항목

보완 반영 뒤 브라우저 새로고침으로 확인받으십시오.

1. 「오늘의 투자 점검」

```text
코스피 수익률·위치 [기준일 지연]
KOSPI 기준일 2026-09-17 · 4거래일 지연
KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.
```

2. 「요즘 잘 오르는 ETF」 → 시장 배경

* `(KS11) KOSPI (보조)`에 같은 상태·기준일·사유 표시
* 영문 KOSPI 경고 줄 없음
* KODEX200 관련 다른 경고는 그대로 유지

화면이 맞으면 결과서에 사용자 확인 시각과 `IMPLEMENTED_UI_CHECK=PASSED`만 기록하십시오.

Telegram C3 확인은 선택 사항이며 OPS-02 검증자 전달을 막지 않습니다.

## 5. 다음 순서

1. M1·M2 반영
2. 필요한 테스트 재실행
3. 사용자 실화면 확인
4. 결과서 최종 갱신
5. 검증자에게 전달
6. 검증자 VERIFIED 뒤 커밋
7. push 승인 요청
8. OCI pull 및 운영 확인
9. POC5-01A 시작

현재 staged 35파일은 유지하고, 검증자 통과 전 커밋하지 마십시오.
