# POC3-02D-OPS-01 — PRE_PRIMARY_OPERATIONAL_CORRECTIONS DESIGN V1

작성: 설계자(원문) · 기록: 개발자(VSCode Claude) · 기록일: 2026-09-26 (R2 · RESULT 판정 추가 2026-09-27) · 전달: 사용자

```text
STEP_ID            = POC3-02D-OPS-01
STEP_NAME          = PRE_PRIMARY_OPERATIONAL_CORRECTIONS
PREDECESSOR        = POC5-00
SUCCESSOR          = POC3-02D-OPS-02 (설계자 RESULT 판정 2026-09-27 · 그 뒤 POC5-01A)
PLAN               = docs/ai_plan/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md
RESULT             = docs/ai_result/POC3/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md
PLAN_DECISION      = PASS_WITH_MANDATORY_AMENDMENT_R2 (최종 · R2 원문)
RESULT_DECISION    = PASS_TO_VERIFIER (설계자 2026-09-27 · 문서 끝 원문) → 검증자 VERIFIED (2026-09-27)
FOLLOW_UP          = POC3-02D-OPS-02 — OCI 상세 링크 · Q8 인접 상태 저장 결함 · 낡은 역검증 ⑦ · 목업 ⑦ 제목 정리(설계자 결정 · PRIMARY 전) · 후보: KOSPI stale 화면 문구(Q19 · 2026-09-26 PLAN 판정 · 포함 여부는 OPS-02 PLAN 때 판정)
IMPLEMENTATION     = DONE (C1~C7 · 검증자 VERIFIED 2026-09-27)
Q23~Q27            = CONFIRMED
C3_CODE_CHANGE     = 사용자 원문 수신(2026-09-27) · `현재가 —` 확인 → 수정 완료
C7_CAUSE_FINAL     = UPSTREAM_2026_CSV_STALLED_AT_2026-09-17
C1_LOGIC           = UNBLOCKED
C1_LIVE_DATA       = 사용자가 KRX 에서 직접 다운로드한 원본 수신 · 설계자 원본 대조 완료(2026-09-27) · 반영 완료
COMMIT_PUSH_OCI    = 커밋(검증자 VERIFIED · STATE_LATEST 1차 갱신 뒤 · 이 문서 포함) · push 별도 승인 대기 · OCI pull 대기
PRIMARY_COHORT     = NOT_STARTED
SOURCE_SWITCH      = PROHIBITED
```

이 문서는 이 단계의 설계자 지시를 한곳에 모은 기록이다. 설계자 판정 원문(§3)과 최종 판정 R2(`# 설계자 최종 판정 R2`)가 PLAN 의 정본이다. 둘이 다르면 R2 를 따른다. 구현 뒤 설계자 RESULT 판정은 문서 끝(`# 설계자 RESULT 판정`)에 있다.

- §1 · §2 는 개발자가 원문을 찾기 쉽게 정리한 것이다. 원문과 다르면 원문을 따른다.
- 이 단계의 설계자 지시는 PLAN 전에 세 번 나왔다: 7건 분류(POC5-00 보완 판정) → 번호 지정 → PLAN 판정. 흩어 두지 않도록 부록 A · B 에 원문을 함께 옮겼다. 그 뒤 최종 판정 R2 와 구현 뒤 RESULT 판정이 나왔다(문서 뒤쪽).

---

## 1. C1~C7 범위 (원문 근거 정리)

| 정정 | 내용 | 설계자 분류(부록 A) | 사실 성격 | 이번 단계 범위(§3) |
|---|---|---|---|---|
| C1 | 08:00 기초지수 구역 복구 | PRIMARY 시작 전 필수 | 실제 발생 | (c) pending gate + 최신 유효 CSV 자동 선택 resolver(07:20 · 08:00 공유) · `refresh_due` 발생 시 사용자에게 갱신 요청 · 장중 설정 · 02B-1 재현은 `20260909` 고정 · 실제 CSV 반영은 사용자 원본 전달 뒤 |
| C2 | 폐지 spike 필수 판정 | 화면 정정 | 발생 추정 | 운영 3종 목록 교체만 · 주석 필터 · 틱 수 검사 제외 · `PROGRAM_TRUTH` + 옛 crontab 문서 SUPERSEDED |
| C3 | 장중 본문 `현재가 —` | 실제 문구 확인 후 수정 | 발생 추정 | 실행 시각 사용 · **사용자 원문이 정말 `현재가 —` 일 때만** 수정 |
| C4 | 잘린 보유 급락의 잘못된 억제 | PRIMARY 시작 전 필수 | 잠재(발생 0건) | 저장 대상 재계산 · 상세 ticker JSONL 추가 없음 · 정렬 유지 · 인접 결함 2개는 tmp 재현 · 결과서 보고만 |
| C5 | Telegram 실패 집계 | 운영 집계 · 증거 정정 | 잠재(실패 0건) | `send_failed` + 사용자 문구 `발송 실패 N회` · 조립 뒤 failed 출구 4개 · 성공 경로도 최종 status 기준 |
| C6 | `message_text_length=0` | 운영 집계 · 증거 정정 | 실제 발생 | flow 에서 조립된 본문 길이 기록 |
| C7 | KOSPI 09-17 정지 | 원인 조사 후 판정 | 실제 발생 | 감지 정정 A(`failed + source_stale:` · 공용 거래일-lag helper 추출 · 시장 브리핑 동작 동일 테스트) · source 교체 금지 · 화면 문구는 후속 `POC3-02D-OPS-02` 후보 |

- PRIMARY 와의 관계(Q20 · Q21): C1~C7 모두 PRIMARY 전에 반영한다. C7 은 감지 정정까지이고, source 복구는 선행조건이 아니다.
- 배포(Q21): 한 단계 · 한 결과서 · 한 pull 이다. CSV 가 늦으면 C1 만 분리할 수 있지만, PRIMARY 는 C1 까지 기다린다.

## 2. 사용자 입력 대기

| 항목 | 필요한 것 | 막히는 것 |
|---|---|---|
| C3 | Telegram 「[장중 급등락]」 메시지의 `기준` 바로 다음 줄 원문 | **원문 수신**(2026-09-27): 사용자 입력 그대로 `현재가 ㅡ. 직전 종가 2026-09-22` — 시각 없이 줄표만 찍힘 → R2 조건('실제로 `현재가 —` 이면 수정') 충족 |
| C7 | `data/index/year_ks11/2026.csv`(master) 마지막 행 날짜 | **해소**(R2 · 설계자 직접 확인: 마지막 행 2026-09-17 · 파일 최신 커밋 2026-09-17 12:22 KST) |
| C1 | 최신 KRX ETF 전종목 기본정보 CSV 원본(재저장 금지) · 다운로드 날짜 · 메뉴 경로 | **원본 수신 · 확인 완료**(2026-09-27) — 사용자가 KRX 에서 직접 다운로드한 파일이다(사용자 확인 · 아래 개발자 기록). 설계자는 원본 내용(크기 · SHA · CP949 · 17열 · 1,175행 · 신규 8종)을 대조했다(RESULT 판정 원문): 출처 KRX Data Marketplace `증권상품 > ETF > 전종목 기본정보` · 다운로드일 2026-09-27. 추석 연휴 중 받은 파일이라 `2026-09-27` 은 **다운로드 · 스냅샷 날짜**이고 거래 기준일이 아니다 |

받은 사용자 증거: `UPSTREAM_MASTER_LAST_COMMIT = 2026-09-26 04:46`(사용자 브라우저 확인).

---

## 3. 설계자 PLAN 판정 원문 (2026-09-26 · 사용자 전달)

판정은 **`PASS_WITH_MANDATORY_AMENDMENT`**입니다. 방향과 사실조사는 충분합니다. 아래 확정사항을 PLAN과 전용 설계서에 반영하면 구현에 들어가도 됩니다.

### C7 확인 결과

사용자가 확인한 사실은 다음처럼 기록합니다.

```text
UPSTREAM_MASTER_LAST_COMMIT = 2026-09-26 04:46 (사용자 브라우저 확인)
```

다만 이것은 저장소 전체가 살아 있다는 증거일 뿐, `2026.csv`가 갱신됐다는 증거는 아닙니다. **파일 마지막 행 날짜가 여전히 필요합니다.**

따라서 현재 판정은 다음입니다.

```text
REPOSITORY_DEAD = false
KS11_FILE_CURRENT = UNCONFIRMED
SOURCE_SWITCH = PROHIBITED
STALE_DETECTION_FIX = APPROVED
```

마지막 행이 09-17이면 해당 파일만 멈춘 상태이고, 09-18 이후이면 다음 07:20 적재에서 자동 복구될 가능성이 있습니다. 어느 쪽이든 stale을 `ok`로 보고한 구조 결함은 남으므로 C7-A는 구현합니다.

### Q1~Q22 확정

| Q   | 판정                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Q1  | **(c) 채택 + 최신 유효 CSV 자동 선택.** `d20` 없는 `api_only`는 pending으로 기록하고 차단하지 않음. 고정 월 1회가 아니라 `refresh_due` 발생 시 사용자에게 갱신 요청.                |
| Q2  | 07:20·08:00은 하나의 CSV resolver를 공유.                                                                                                     |
| Q3  | 장중 설정과 02B-1 재현은 `20260909`에 고정. 운영 resolver와 섞지 않음.                                                                                   |
| Q4  | `07:15~08:05 pull 금지` 운영 규칙만 적용. 코드 시간 가드는 추가하지 않음.                                                                                    |
| Q5  | 기존 최신성 임계 유지. 드러나는 결과를 먼저 관찰.                                                                                                          |
| Q6  | C4 상세 ticker를 JSONL에 추가하지 않음. POC5-01이 맡음.                                                                                             |
| Q7  | 보유 급락 정렬 순서 유지.                                                                                                                        |
| Q8  | 두 인접 결함을 tmp로 재현하고 결과서에 보고. 이번 단계에서 함께 고치지 않음.                                                                                         |
| Q9  | **(a)** 실행 시각 사용. 단, 사용자 원문이 정말 `현재가 —`인 경우에만 수정.                                                                                      |
| Q10 | 범위 밖으로 기록.                                                                                                                             |
| Q11 | **(b)** `send_failed` + 사용자 문구 **`발송 실패 N회`** 확정.                                                                                      |
| Q12 | 조립 뒤 failed 출구 4개 모두 적용.                                                                                                               |
| Q13 | 성공 경로도 최종 status 기준으로 확정.                                                                                                              |
| Q14 | C2는 운영 3종 목록 교체만. 주석 필터·틱 수 검사는 제외.                                                                                                    |
| Q15 | `PROGRAM_TRUTH` 갱신 + 옛 crontab 문서 `SUPERSEDED` 표시.                                                                                     |
| Q16 | 사용자 브라우저 증거 사용. master 커밋 시각과 CSV 마지막 행을 따로 기록.                                                                                        |
| Q17 | C7-A 채택. `failed + source_stale:` 사용. 다만 flow의 private helper를 store가 import하는 방식은 금지. 공용 거래일-lag helper로 추출하고 기존 시장 브리핑 동작이 동일함을 테스트. |
| Q18 | upstream이 재개되면 그대로 사용. 계속 멈추면 source 교체를 별도 설계로 판단.                                                                                    |
| Q19 | KOSPI stale 화면 문구는 이번 단계에서 제외. 후속 `POC3-02D-OPS-02` 후보로 기록.                                                                            |
| Q20 | **C1~C7 모두 PRIMARY 전 반영.** C7은 감지 정정까지만이며 source 복구는 선행조건 아님.                                                                          |
| Q21 | 한 단계·한 결과서·한 pull. CSV가 늦으면 C1만 분리할 수 있지만 PRIMARY는 C1까지 기다림.                                                                           |
| Q22 | 새 테스트 파일 생성 승인.                                                                                                                        |

### C1 필수 보완

매번 코드 상수를 바꾸는 방식은 1인 운영에 맞지 않습니다. 다음 구조로 바꿉니다.

```text
운영 07:20·08:00
  → krx_etf_basic_YYYYMMDD.csv 중
     파일명 날짜가 가장 늦고 검증을 통과한 파일을 결정적으로 선택

02B-1 재현·장중 설정
  → 승인된 20260909 파일에 계속 고정
```

resolver는 다음을 fail-loud로 검사해야 합니다.

* 파일명 날짜 파싱
* 동일 날짜 파일 중복
* CP949 디코딩
* 17개 컬럼
* ticker 중복·빈 기초지수명
* 선택 파일명·SHA·`csv_asof` 기록

향후 CSV 교체는 **데이터 파일만 추가**하는 작업으로 만듭니다. 검증 스크립트와 집중 테스트가 통과하면, 코드 변경이 없는 데이터 갱신마다 전체 검증자를 다시 거치지 않아도 됩니다. commit·push·OCI pull 승인은 계속 유지합니다.

### 전용 설계서

만들어야 합니다. POC5-00 끝에 흩어 두지 않습니다.

```text
docs/ai_design/POC3/
POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md
```

이 답변의 판정 원문, C1~C7 범위, Q1~Q22 확정, 사용자 입력 대기 항목을 기록하십시오.

### 구현 착수 조건

다음은 지금 바로 진행할 수 있습니다.

```text
C2 · C4 · C5 · C6
C7 stale 감지
C1 resolver·pending gate·테스트
```

다음 두 가지는 사용자 증거를 받은 뒤에만 마무리합니다.

1. C3: Telegram 메시지의 `기준` 바로 다음 줄 원문
2. C7: `2026.csv`의 마지막 행 날짜

C1 실제 CSV 반영은 PLAN 반영 뒤 사용자가 최신 원본을 전달하면 진행합니다.

```text
PLAN_DECISION      = PASS_WITH_MANDATORY_AMENDMENT
IMPLEMENTATION     = ALLOWED_AFTER_DOCUMENT_SYNC
C3_CODE_CHANGE     = BLOCKED_BY_USER_MESSAGE_TEXT
C7_CAUSE_FINAL     = BLOCKED_BY_LAST_ROW_DATE
PRIMARY_COHORT     = NOT_STARTED
SOURCE_SWITCH      = PROHIBITED
```

---

## 부록 A. 7건 분류 원문 (설계자 보완 판정 2026-09-26 중 이 단계 해당 부분)

전문은 `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md` 끝 `# 설계자 보완 판정` 에 있다.

> 운영 정정 PLAN에는 7건을 한꺼번에 고치는 코드부터 작성하지 말고, 각각을 아래처럼 분류해야 합니다.
>
> * PRIMARY 시작 전 필수: 기초지수 구역 복구, 잘린 보유 급락의 잘못된 억제
> * 실제 문구 확인 후 수정: `현재가 —`
> * 운영 집계·증거 정정: Telegram 실패 집계, `message_text_length=0`
> * 화면 정정: 폐지 spike 필수 판정
> * 원인 조사 후 판정: KOSPI 09-17 정지
>
> KOSPI는 원인을 확인하기 전 임의 source 교체나 날짜 밀어 넣기를 금지합니다. PC의 의심 기록 12행도 계속 보존합니다.

## 부록 B. 번호 지정 원문 (설계자 2026-09-26 · 사용자 전달)

> 알겠습니다. 앞으로 **설계서·PLAN·RESULT 파일명과 본문에 모두 숫자 단계**를 명시하겠습니다. `PRE_PRIMARY` 같은 설명만으로 단계를 대신하지 않습니다.
>
> 이번 작업 번호는 기존 `POC3-02C` 다음으로 잡아 다음처럼 정리하는 것이 맞습니다.
>
> ```text
> STEP_ID     = POC3-02D-OPS-01
> STEP_NAME   = PRE_PRIMARY_OPERATIONAL_CORRECTIONS
> PREDECESSOR = POC5-00
> SUCCESSOR   = POC5-01A
> ```
>
> 현재 초안도 최종 제출 전에 다음 이름으로 바꿔 주세요.
>
> ```text
> docs/ai_plan/POC3/
> POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md
> ```
>
> 연관 문서도 같은 번호를 유지합니다.
>
> ```text
> POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_DESIGN_V1.md
> POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_PLAN_V1.md
> POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md
> ```
>
> 본문에는 다음 두 축을 모두 숫자로 표시해야 합니다.
>
> * 전체 작업 단계: `STEP 1 → STEP 2 → …`
> * 정정 대상: `C1 → C7`
>
> 예를 들면:
>
> ```text
> STEP 1  사실 기준선 고정
> STEP 2  C1~C7 구현
> STEP 3  집중·전체 회귀
> STEP 4  운영 상태 불변 확인
> STEP 5  검증자 판정
> STEP 6  commit·push
> STEP 7  OCI 적용 및 사후 실측
> ```
>
> 추가로 최종 PLAN에서는 사실의 성격을 구분해 주세요.
>
> * KOSPI 정지 및 배치 `ok`: **실제 발생한 운영 결함**
> * 잘린 보유 급락 억제: 발생 0건인 **잠재 결함**
> * Telegram 실패 집계: 실패 0건인 **잠재 결함**
>
> 이 셋을 모두 "운영에서 발생했다"고 묶으면 보고가 부풀려집니다. 독립 검토가 끝난 최종본이 오면 `POC3-02D-OPS-01` 기준으로 판정하겠습니다.

---

# 설계자 최종 판정 R2 (2026-09-27 · 설계자 원문 · 사용자 전달 · §3 판정 뒤 Q23~Q27 확정)

설계자 머리말: "PLAN 662줄 전체를 다시 읽었습니다. 앞선 답변은 사용하지 마시고, 아래 판정을 정본으로 개발자에게 전달해 주세요."

## POC3-02D-OPS-01 설계자 최종 판정

```text
PLAN_DECISION          = PASS_WITH_MANDATORY_AMENDMENT_R2
IMPLEMENTATION         = CONTINUE
Q23~Q27                = CONFIRMED
C3_CODE_CHANGE         = USER_TELEGRAM_LINE 대기
C7_CAUSE_FINAL         = UPSTREAM_2026_CSV_STALLED_AT_2026-09-17
C1_LOGIC               = UNBLOCKED
C1_LIVE_DATA           = KRX CSV 원본 대기
COMMIT_PUSH_OCI        = HOLD
PRIMARY_COHORT         = NOT_STARTED
```

현재 구현된 C2·C4·C5·C6·C7 감지와 C1 pending gate 방향은 승인합니다.

### Q23~Q27 확정

| 질문  | 판정           | 확정 내용                                                                                            |
| --- | ------------ | ------------------------------------------------------------------------------------------------ |
| Q23 | **(a), N=5** | 가장 오래된 pending ETF가 21번째 저장 거래일을 얻기까지 5거래일 이하이거나, 이미 `CSV_REFRESH_REQUIRED`이면 `refresh_due=true` |
| Q24 | **(b)**      | 08:00 본문 끝에 조건부 1줄을 붙임                                                                           |
| Q25 | **(a)**      | 최신 파일이 검증 실패하면 직전의 최신 유효 파일을 사용하고 거부 파일·SHA·사유 기록                                                |
| Q26 | **(b)**      | `as_of`는 **유효 종가가 있는 마지막 날짜**로 정의                                                                |
| Q27 | **(b)**      | 전날 판정 재사용을 허용하지 않고 08:00에서 판정 창 일치 여부를 확인해 fail-closed                                           |

세부 계약은 다음과 같습니다.

#### Q23 — `refresh_due`

```text
remaining_trading_days = max(0, 21 - stored_trading_day_count)

refresh_due =
  earliest_pending.remaining_trading_days <= 5
  OR consistency_status == CSV_REFRESH_REQUIRED
```

거의 매주 CSV 갱신을 요구하지 않으면서 실제 차단 약 1주 전에 알리는 방식입니다.

#### Q24 — 사용자 안내

확정 문구:

```text
※ 운영 안내: KRX ETF 전종목 기본정보 CSV를 갱신해 주세요.
```

* `refresh_due: false → true`가 된 주기마다 한 번만 알립니다.
* 해당일 08:00 발송이 없으면 다음 실제 08:00 발송까지 안내를 보류합니다.
* 정합성 JSON과 배치 로그에는 매회 상태를 기록합니다.
* 이 안내 때문에 시장 브리핑 자체를 차단하지 않습니다.

#### Q25 — 잘못된 최신 CSV

* 가장 최신 날짜 파일이 실패하면 그 이전의 최신 유효 파일을 선택합니다.
* 실패 파일명·원본 SHA-256·실패 사유를 JSON과 로그에 남깁니다.
* 동일 날짜 파일이 둘 이상이면 그 날짜 묶음은 무효로 보고 이전 유효 날짜로 내려갑니다.
* 유효 파일이 하나도 없을 때만 `CSV_REFRESH_REQUIRED + resolver error`로 fail-closed 합니다.

#### Q26 — KOSPI `as_of`

* `Close > 0`인 행 중 마지막 날짜를 `as_of`로 사용합니다.
* 더 최신 날짜에 `NaN`, 0, 음수 행이 있어도 신선한 자료로 인정하지 않습니다.
* 유효 종가 행이 하나도 없으면:

```text
failed
source_stale:as_of=unknown
```

#### Q27 — 전날 `ok` 재사용 방지

개발자 제안 (a)는 승인하지 않습니다. 07:20 실패 후 전날의 `ok`를 그대로 쓰는 것은 조용한 fail-open이며, 1인 자동 운영에서 배치 로그를 사람이 매일 확인해야만 발견할 수 있습니다.

정합성 JSON에 최소한 다음을 기록합니다.

```text
evaluated_api_basis_date
evaluated_window_d20_date
evaluated_at_kst
```

08:00 실행 시 현재 창과 비교합니다.

* 일치: 저장된 판정 사용
* 누락·불일치: 기초지수 구역만 fail-closed
* 진단 상태: `META_GATE_STALE`
* 이를 `CSV_REFRESH_REQUIRED`로 표시하지 않음 — 불필요한 CSV 다운로드 요청을 막기 위함
* 미국 전망 한 줄 등 나머지 브리핑은 정상 진행

이는 정합성을 08:00에 다시 계산하는 것이 아니라, 저장된 판정이 오늘 창의 것인지 확인하는 안전 검사입니다.

## 사용자 확인 항목 정리

### 1. Telegram 한 줄 — 여전히 필요합니다

C3는 설계자 확정 Q9에서 사용자 실수신 원문 확인을 전제로 했으므로 생략할 수 없습니다.

Telegram의 `[장중 급등락]` 메시지에서 `기준` 바로 다음 줄만 보내 주세요.

예상:

```text
현재가 — · 직전 종가 2026-09-19
```

실제로 `현재가 —`이면 계획대로 `format_quote_asof(runtime_kst)`로 수정합니다. 이미 시각이 표시돼 있다면 C3 코드는 수정하지 않습니다.

### 2. `2026.csv` 날짜 — 제가 확인했으므로 안 보셔도 됩니다

GitHub 현재 파일을 직접 확인했습니다.

* 마지막 행: **2026-09-17**
* 해당 파일의 최신 커밋: **2026-09-17 12:22 KST**
* 저장소 전체의 9월 26일 커밋과는 별개로, KS11의 `2026.csv`만 멈춰 있습니다.

확인 페이지: [FinanceData 2026.csv](https://github.com/FinanceData/fdr_krx_data_cache/blob/master/data/index/year_ks11/2026.csv)

따라서 C7 원인은 다음으로 확정합니다.

```text
REPOSITORY_DEAD     = false
KS11_FILE_CURRENT   = false
KS11_LAST_ROW       = 2026-09-17
C7_CAUSE_FINAL      = upstream KS11 2026.csv stopped
SOURCE_SWITCH       = PROHIBITED
```

C7 감지 정정은 계속 진행하고, 원본 source 교체는 이번 단계에서 하지 않습니다.

### 3. KRX CSV 원본 — 구현을 막지는 않지만 PRIMARY 전에는 필요합니다

resolver·pending gate·테스트는 지금 마무리할 수 있습니다. 다만 C1 데이터 반영과 `POC3-02D-OPS-01` 최종 종료, PRIMARY 시작 전에는 최신 원본 CSV가 필요합니다.

Excel로 다시 저장하지 않은 원본과 다음 두 정보만 전달하면 됩니다.

* 다운로드 날짜
* 실제 메뉴 경로

## 개발자 진행 순서

기존 `STEP 1~7` 번호를 유지합니다.

1. **STEP 1** — C7 증거를 위 날짜로 확정하고, C3 원문·C1 CSV만 사용자 대기로 남김
2. **STEP 2** — Q23~Q27에 따라 C1 resolver·`refresh_due`·Q27 안전검사·C7을 완료. C3는 원문 도착 뒤 처리
3. **STEP 3** — 남은 변경 후 전체 회귀를 다시 실행. 현재의 `2303 passed`는 중간 실적
4. **STEP 4** — PC 라이브 파일 221개·DB·플래그·OCI 불변 재확인
5. **STEP 5** — 결과서 작성 → 설계자 → 검증자
6. **STEP 6** — 검증 통과 뒤 commit, 별도 승인 후 push
7. **STEP 7** — `07:15~08:05`를 피해서 OCI pull 및 사후 실측

PRIMARY는 이 STEP 7만으로 시작하지 않습니다. `POC5-01` 코드 pull까지 완료한 뒤 첫 KRX 거래일부터 시작한다는 기존 계약을 유지합니다.

---

> 개발자 기록(2026-09-27): 사용자가 같은 메시지로 KRX CSV 원본을 전달했다. 파일 `~/Downloads/KRX_증권상품_ETF_전종목기본정보_20260927.csv` · 373,228 byte · SHA-256 `0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314` · 파일 수정 시각 2026-09-27 13:27. 다운로드 날짜와 메뉴 경로는 파일명(`증권상품 · ETF · 전종목기본정보` · `20260927`)에서 읽은 값이었다. 그 뒤 사용자가 대화에서 'KRX 에서 다운로드한 파일'이라고 확인했다(2026-09-27). 설계자 RESULT 판정 표의 출처 · 다운로드일도 같은 값이고, 설계자는 원본 내용을 대조했다.

> 개발자 기록(2026-09-27): 사용자가 C3 원문을 전달했다. 사용자 입력 그대로 `현재가 ㅡ. 직전 종가 2026-09-22`. 사용자가 손으로 옮긴 것이라 줄표(`—`)와 가운뎃점(`·`)이 `ㅡ` · `.` 으로 적혔다. 현재가 자리에 시각이 없고 줄표만 있으므로 코드상 추정(`현재가 — · 직전 종가 <날짜>`)과 같은 결함이 실수신 메시지에서 확인됐다.

---

# 설계자 RESULT 판정 (2026-09-27 · 설계자 원문 · 사용자 전달)

판정은 **`PASS_TO_VERIFIER`**입니다. C1~C7 구현을 다시 열 사유는 없습니다.

첨부 원본도 결과서와 직접 대조했습니다.

| 항목      | 확인값                                                                |
| ------- | ------------------------------------------------------------------ |
| 출처      | KRX Data Marketplace의 `증권상품 > ETF > 전종목 기본정보`                      |
| 다운로드일   | 2026-09-27                                                         |
| 파일 크기   | 373,228 bytes                                                      |
| SHA-256 | `0f0c074240e66c6d7a3406861c287dc63b8137c7aa497e5db509fae9f8722314` |
| 인코딩     | CP949                                                              |
| 구조      | 17개 열 · 데이터 1,175행                                                 |
| 신규 ETF  | 결과서의 8종 모두 존재                                                      |
| 누락      | 0종                                                                 |

추석 연휴 중 받은 파일이므로 `2026-09-27`은 **거래 기준일이 아니라 다운로드·스냅샷 날짜**로 기록하면 됩니다. ETF 기본정보는 종가 데이터가 아니므로 휴장일 다운로드도 문제없습니다.

[첨부 CSV](sandbox:/workspace/scratch/0f5b1f431bc1/upload/KRX_증권상품_ETF_전종목기본정보_20260927.csv) · [결과서](sandbox:/workspace/scratch/0f5b1f431bc1/upload/POC3-02D-OPS-01_PRE_PRIMARY_OPERATIONAL_CORRECTIONS_RESULT.md)

그리고 이 CSV는 API 키가 있는데도 매번 수동으로 가격을 갱신하기 위한 파일이 아닙니다. 일별 가격은 API가 자동 수집하고, 이 파일은 ETF 이름·기초지수·분류 등 **공식 메타정보를 독립적으로 검증하는 스냅샷**입니다. 이번 C1의 `pending/refresh_due`가 들어가면 필요할 때만 갱신 안내가 나옵니다.

결정 사항은 다음과 같습니다.

1. **`META_GATE_STALE` 문구 승인**

   `기초지수 정보는 최신 기준을 확인하지 못해 제외했습니다.`

   이 문구를 그대로 사용해도 됩니다. 단, `evaluated_window_missing` 등 현재 판정 창을 확인하지 못한 경우에만 사용하고, 단순히 후보가 0개인 경우에는 사용하지 않습니다.

2. **잘못된 OCI 상세 링크는 고칩니다**

   다만 검증이 끝난 C1~C7에 지금 섞지 않습니다. 다음 번호 단계인 `POC3-02D-OPS-02`에서 「오늘의 투자 점검」 링크를 실제 「OCI 운영 상태」 화면으로 연결합니다.

3. **결과서 §8의 인접 상태 저장 결함도 후속 처리합니다**

   전송 실패·부분 전송·구역 상한·조립 예외 때 실제로 전달되지 않은 신호가 발송 완료처럼 억제되는 문제는 운영 정확성에 영향을 줍니다. 이것도 `OPS-02`에 포함하고 **POC5-01A PRIMARY 시작 전에** 끝내는 편이 맞습니다.

4. **역검증 ⑦은 현 계약에서 폐기 대상입니다**

   2026-09-18 이후 정기 PUSH는 내용이 같아도 발송하도록 바뀌었으므로, 기존 `fingerprint 반복 억제` 역검증과 “동일 fingerprint 미발송” 목업 제목은 현재 계약 검증으로 사용하면 안 됩니다. 이것도 `OPS-02`에서 정리합니다.

진행 순서는 다음으로 확정합니다.

1. 결과서에 CSV 출처를 `사용자 확인 완료`로 바꾸고, 연휴라 다운로드일이지 거래 기준일이 아니라는 주석 추가
2. 현재 C1~C7을 검증자에게 전달
3. `VERIFIED` 후 `STATE_LATEST` 갱신 → 커밋·push
4. OCI pull은 `07:15~08:05`를 피해서 실행
5. 연휴 뒤 첫 거래일에 07:20·08:00 운영 확인
6. `POC3-02D-OPS-02`에서 링크·상태 저장·낡은 역검증 정리
7. 그 뒤 `POC5-01A PRIMARY` 시작

즉, **현재 구현은 검증자로 넘기고, 발견된 별도 결함은 번호가 있는 다음 소형 단계에서 처리합니다.**
