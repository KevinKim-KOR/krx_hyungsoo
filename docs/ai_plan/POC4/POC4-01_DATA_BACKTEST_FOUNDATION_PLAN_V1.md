# POC4-01 — 데이터·백테스트 기반 정비 PLAN V1

```text
STATUS            = 작업 1~6 · 테스트 격리 · 검증자 P1 · 설계자 3차 판정 교정 구현 · 설계자 확인 완료 ·
                    개발자 사전 점검 뒤 가드 보강(결과서 §4-13) → READY_FOR_LIMITED_REVERIFICATION
OCI · PUSH = 변경 0 · 테스트 격리 결함(전체 pytest 가 맥북 라이브 경로에 씀)은 수정 — 결과서 §4-8·§4-9
DEPENDENCY_ADDED  = 0
```

### 설계자 확인 (2026-09-24) — 3차 판정 개발자 정정(93 → 233 → 229) 수용

```text
DESIGNER_CONFIRMATION       = ACCEPTED
LIVE_DB_OPENERS_MEASURED    = 233
FIXED_INPUT_MIGRATED        = 4
LEGACY_READONLY_ALLOWLIST   = 229
MONITORING_READ_EXCEPTIONS  = 2 (READ-ONLY ONLY)
POC4_01_STATUS              = READY_FOR_LIMITED_REVERIFICATION
PUSH                        = HOLD_UNTIL_VERIFIED
HANDOFF                     = AFTER_VERIFIED_AND_PUSH
```

- 93 은 최초 가드의 read-write 실패만 센 과소 측정 — 233 전수 계측 · 정확값 의존 4건 고정 입력 전환 · 남은 229건은
  승인한 `READONLY_SESSION_COPY` 과도기 범위. 목록 밖 신규 테스트는 실패하므로 기술부채가 늘지 않는다.
- 감시 목적 직접 읽기 2건(세션 전후 hash · 테스트별 benchmark 조회)은 `mode=ro` 전용 · 보호 장치 자체의 관찰 경로라 예외 승인.
- 허용 목록 항목 교체를 런타임에서 완벽히 못 잡는 한계는 비차단 기술부채 — 목록은 정렬·중복 0 유지, 변경 diff 는 검증자 확인.
- NAV 격리본 보존·활성 경로 공백 수용 — 다음 정상 갱신이 재생성, 그전까지 UI·API·PUSH 영향 없음.
- 순서: 검증자 제한 재검증 → VERIFIED 뒤 로컬 commit 일괄 push → push 된 HEAD 확인 → POC4-01 최종 종료 인계 →
  POC4-02 착수 전 설계자에게 종료 보고. 사용자 화면 확인·OCI 적용은 필요 없음.
- (개발자 · 검증자 전달 전) 검증 항목 1~8 을 먼저 돌려 확정된 가드 우회 경로(ATTACH·VACUUM INTO · 사본 직접 쓰기 · 경로
  별칭 · 다른 진입점(`sqlite3.dbapi2.connect`·`_sqlite3.connect`·`_io.open`·`posix.*`) · 삼킨 가드 오류 · conftest 되돌려 쓰기)를 **테스트 코드만** 보강해 막았다(사용자 결정 2026-09-24 · 결과서 §4-13).
  설계 계약은 바꾸지 않았다 — 조건("쓰기 즉시 실패" · "감시는 읽기 전용")을 코드가 실제로 지키게 한 것이다.

### 설계자 판정 3차 (2026-09-24) — 검증자 2차 BLOCKED(설계자 계약 2건)에 대한 결정

```text
DESIGNER_DECISION           = APPROVED_WITH_REQUIRED_CORRECTIONS
LIVE_DB_TEST_ACCESS         = READONLY_SESSION_COPY
MARKET_REFRESH_NAV_JSON     = REQUIRED
KRX_ETF_UNIVERSE_V1         = APPROVED_AS_RESEARCH_BASELINE_INPUT
FORMULA_TEXT_CORRECTION     = REQUIRED
PUSH                        = HOLD
HANDOFF                     = AFTER_VERIFIED
```

- 세션 사본 조건: 라이브 DB 는 사본을 만들 때만 읽음 · 테스트 sqlite 연결은 모두 임시 사본을 mode=ro 로 · 쓰기 즉시
  실패 · 라이브 DB·5곳 hash 전후 동일 · 운영 코드 기본 경로 계약은 이번 Step 에서 바꾸지 않음 · 새 테스트는 자체
  임시 DB·고정 fixture · 호환 경로는 기존 테스트에만(판정문: "기존 93건에만") · 사본 생성 전후 라이브 hash 가 다르면 실패 · 사본 SQLite
  integrity 검사 · 정확한 데이터값을 계약으로 단언하는 테스트에는 세션 사본 금지 · 기존 테스트의 고정 fixture 전환은
  비차단 기술부채(POC4-01 인계에 기록).
  - **개발자 정정 (설계자 확인 완료 — 위 ACCEPTED)**: 판정문의 "기존 93건" 은 개발자가 보고한 수치였고 **과소 집계**였다. 실측으로
    세션 사본을 여는 기존 테스트는 233건이었고, 그중 199건은 사본이 없으면 실패했다(29839c75 전 가드 기준 — 나머지 34건은
    가드 오류가 삼켜져 통과했다. 지금은 삼킨 가드 오류도 테스트를 실패시켜 목록을 비우면 229건 모두 실패한다, 결과서 §4-13). 판정의 뜻(기존 테스트에만 · 새 테스트
    금지)대로 이 목록을 고정하고, 라이브 커버리지 단언 4건을 고정 입력으로 바꿔 229건으로 줄였다. 결과서 §4-9 · §6-3.
- AC-8: `LEGACY_MARKET_JSON_ARTIFACTS = 0` · `NAV_SUMMARY_JSON = 지정 경로 1개` · `OTHER_MARKET_JSON_ARTIFACTS = 0`.
  운영 코드의 NAV JSON 쓰기는 제거하지 않는다.
- 현재 NAV 요약: 증거 기록 → 활성 경로 밖 이름으로 격리 보존 → 다음 정상 NAV 갱신이 다시 만듦 · 수동 편집·합성
  금지 · 실행 기록 156개·공유 로그 2개는 유지.
- 산식 문구: `strategy_performance.formulas.active_return` 에 월평균 active return · tracking error · information ratio
  명시 → 기준선 두 번 재실행(run 결과 동일 · E2 핵심 hash 동일 · 산식·설명 외 전략 결과 변화 0).
- `krx_etf_universe_v1`: POC4-02 연구 기준선 입력으로 승인(`PURPOSE=RESEARCH_BASELINE` · `OPERATION_PROMOTION=NO` ·
  `OCI_DEPLOY=0` · `PUSH_USE=0`). POC4-02 규칙 — 각 날짜의 KRX universe 사용 · 현재 `etf_master` 로 재필터 금지 ·
  폐지 ETF 가격은 같은 KRX 봉인 version 에서, KODEX200(069500)도 같은 계열에서 · 결측을 생존 DB 로 채우지 않음 ·
  결측·0·휴장 응답은 사유와 함께 제외 · dataset version·payload hash·날짜 범위 고정 ·
  `UNBIASED_PERFORMANCE_CLAIM=YES` 아님(POC4-02 검증 전까지 `RESEARCH_ONLY`).
- 순서: 계약 2건 반영 → NAV 오염 산출물 격리 → 산식 문구 → 기준선 2회 → 전체 회귀(1,997건 이상)·라이브 5곳 불변 →
  결과서 → 검증자 제한 재검증 → VERIFIED 뒤 로컬 commit 전부 push → POC4-01 최종 인계.
- 현재 중간 인계와 `02a0f7c5` 는 사용자 직접 지시로 생성됐다는 기록을 유지한다(별도 문제로 취급하지 않음).

### 설계자 판정 2차 (2026-09-24)

```text
POC4_01_WORK_1_TO_5       = ACCEPTED_PENDING_VERIFIER
WORK_6                    = AUTHORIZED
TEST_ISOLATION_DEFECT     = BLOCKING
CODE_PUSH                 = HOLD        (VERIFIED 뒤 한꺼번에 push)
HANDOFF                   = NOT_YET     (AFTER_WORK6_AND_VERIFIER)
UNBIASED_PERFORMANCE      = NOT_YET
```

- 테스트 사고: (a) 시장 DB 1행 그대로 · (b) 테스트 단독 생성 파일만 증거 기록 후 삭제(공유 로그는 삭제 금지) ·
  (c) 격리 수정 필수 — tmp 격리 · 라이브 경로 즉시 실패 guard · 5곳 전후 hash · 역검증 · 전체 회귀 후 불변 확인.
- 작업 6 결정은 §5 에 반영했다.
- 순서: checkpoint 커밋 → 사고 증거 → 가짜 파일 정리 → 격리·역검증 → 작업 6 → 전체 회귀·KS-10·5곳 불변 →
  결과서 → 검증자 → VERIFIED 후 push → handoff. OCI·운영 PUSH·운영 DB 변경 없음.

### 설계자 판정 1차 (2026-09-23)

```text
STOP_CONDITION_COMPLIED       = YES
LEGACY_BASELINE               = NON_REPRODUCIBLE
ROOT_CAUSE                    = MUTABLE_INPUT_DATA
NEW_IMMUTABLE_BASELINE        = APPROVED
KRX_HISTORICAL_SOURCE         = APPROVED_WITH_GATES
UNBIASED_PERFORMANCE_CLAIM    = NOT_YET
POC4_01_CONTINUE              = YES
```

- 결정 1 — 새 기준선: 기존 결과 덮어쓰지 않음 · 145 를 146 으로 단순 수정 금지 ·
  라이브 DB 직접 baseline 실행 금지 · 입력 스냅샷·hash·cutoff·테이블 통계·schema hash·
  코드 commit·고정 모듈 raw/정규화 AST hash·환경·인자·결과 hash·평가일 목록을 한 세트로
  고정 · snapshot hash 불일치 시 fail-closed · 검증 기준 4개(두 번 실행 동일 / 라이브
  새 날짜 무관 / 라이브 과거 행 변경 무관 / 누락·불일치 시 실패).
- 결정 2 — KRX universe: PC 전용 별도 연구 DB · OCI 쓰기 0 · 운영 DB 변경 금지 · 가격
  혼합 금지 · 2014년 이후 전체 기간 · 원응답 raw · 폐지 종목을 현재 etf_master 로
  거르지 않음 · batch·조회일·source·payload hash 기록 · 덮어쓰기 금지 · 재수집이 다르면
  별도 version · Gate 1~6(공식 한도 조사 → 재시작 가능 downloader → canary ≤20 →
  중복·누락·재시도·backoff 검증 → 한도 확인 시 전체 적재 / 미확인 시 일괄 호출 금지).
- 결정 3 — 고정 모듈 주석: 새 기준선을 만드는 커밋에서 정정하고 그 hash 를 고정 ·
  기존 hash 갱신·위조 금지 · raw hash 는 바뀌고 정규화 AST hash 는 같음을 기록 ·
  requirements.txt 변경도 provenance 에 포함.
- 132MB 임시 DB: 4가지 확인 후, 불완전하면 새 스냅샷 생성·검증 뒤 **그 파일 1개만** 삭제.
- 순서: legacy 표시 → 스냅샷·manifest·fail-closed → 결정성 검증 → KRX 연구 DB·canary →
  한도 확인 전 전체 적재 금지 → 그다음 embargo·성과지표·비용 분해. 완료 후 검증자.

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자
- **입력**: 설계자 POC4-00 판정·POC4-01 착수 지시·POC4-01 판정 1차(2026-09-23)·2차·3차(2026-09-24)·검증자 1차 판정 REJECTED(P1 산출물 보호)·2차 BLOCKED(설계자 계약 2건)
- 구현 증거·수치는 결과서 `docs/ai_result/POC4/POC4-01_DATA_BACKTEST_FOUNDATION_RESULT.md`.

---

## 0. 결론

| | 결과 |
|---|---|
| **기존 baseline** | **재현 불가 확정**(`LEGACY_BASELINE_NON_REPRODUCIBLE`). 원본 결과는 덮어쓰지 않고 역사 자료로 보존했다(§1) |
| **새 기준선** | 라이브 DB 를 한 번 동결한 **불변 스냅샷**으로만 평가한다. 평가기는 스냅샷 없이는 돌지 않는다(§4) |
| **universe 복원** | 공식 한도(키당 10,000회/일)를 약관 원문으로 확인했다. canary 게이트 통과 후 전체 기간 적재(§2) |
| **작업 6** | 설계자 결정(§5)대로 구현 — 20거래일 purge·embargo 는 모델·설정 선택 분할에(E2 무변경), 비용 분해(편도 11.5bp 기본 · legacy 25bp 유지), 절대·상대 성과지표 |
| **테스트 격리** | 전체 pytest 가 맥북 라이브 경로에 쓰던 기존 결함을 막았다 — 쓰는 순간 실패하는 가드 · 라이브 DB 는 읽기 전용 세션 사본으로(기존 테스트 목록 229건만 · 사본 hash·integrity 검사) · 세션 전후 비교 |

---

## 1. baseline 재현 — 실패

### 1-1. 무엇을 했나

설계자 지시 순서 그대로다 — **코드 변경 전에** 재현했다.

```text
1  원본 artifact 고정     state/ml/validity/poc4_01_frozen_original/  (sha256 보존)
2  같은 인자로 재실행      limit_dates=None · skip_e1=False  (원본 run_arguments 와 동일)
3  출력을 별도 폴더로      --out-dir state/ml/validity/poc4_01_repro  (원본 덮어쓰기 0)
4  라이브 DB 보호          가격·이름 조회(load_prices·build_tag_map)는 운영 조회 함수(_connection)로
                          라이브 DB 를 읽기쓰기 연결로 열었다(처음 열 때 CREATE TABLE IF NOT EXISTS ·
                          기존 테이블이라 변경 없음). mode=ro 는 U2 재현 원본과 가격 hash 계산뿐 ·
                          산출 JSON 과 U2 임시 DB 는 출력 폴더로만
```

실행 후 라이브 `market_data.sqlite` sha256 이 **실행 전과 같다**.

### 1-2. 결과

```text
RuntimeError: E2 평가일 수 계약 위반: 기대 145, 실제 146
```

재현 당시 코드(`d43db726`)에서는 `app/ml_score_validity_eval.py:73` 이 평가일 수를
`E2_EXPECTED_POINT_COUNT = 145` 로 고정했고, `assert_evaluation_window`(:529)가 개수가
다르면 멈췄다. **계약 가드가 제대로 작동한 것이다** — 입력이 바뀌었다는 것을 잡았다.
(`be579619` 에서 이 상수를 뺐다 — 지금은 스냅샷 manifest 의 평가일 목록과 비교한다. §4-2)

### 1-3. 코드는 바뀌지 않았다

원본 산출물에 **고정 모듈 해시**(`frozen_descriptor.module_sha256`)가 남아 있다.

```text
app/ml_relative_upside_features.py   원본 실행과 같음
app/ml_relative_upside_model.py      원본 실행과 같음
app/ml_relative_upside_score.py      원본 실행과 같음
```

계산도 재현된다 — **겹치는 145개 평가일 중 142개는 IC 가 원본과 정확히 같고,
종목 수(n)는 145개 전부 같다.**

### 1-4. 원인 — 입력 데이터가 두 가지로 바뀌었다

원본 산출물의 **가격 입력 해시**(`price_projection_sha256_full`)가 지금 DB 로 다시
계산하면 **다르다.** 무엇이 바뀌었는지 둘로 나뉜다.

**원인 1 · 평가 창이 늘었다 (146 ≠ 145)**

```text
원본 실행 때 가격 최신일   2026-08-27
지금 가격 최신일          2026-09-21
```

`2026-07-31` 신호의 1개월 청산일은 "다음 월말 + 1 거래일" = 2026-09-01 이다.
원본 실행 때는 그 가격이 없어 평가점에서 빠졌고, 지금은 있어서 **완전한 평가점이
됐다.** 재현에만 있는 평가일이 정확히 이것 하나다(2014-04·05 는 시작일 계약
2014-06-30 이전이라 원래 제외된다).

**원인 2 · 과거 가격이 다시 적재됐다 (최근 3개 IC 변동)**

`etf_daily_price.fetched_at` 이 원본 실행(2026-08-29 13:04 UTC) **이후**인 과거 행:

```text
2014-01-01 ~ 2025-12-31          0 / 1,209,017
2026-01-01 ~ 2026-03-31          0 /    62,546
2026-04-01 ~ 2026-06-30     41,660 /    67,954   ← 61%
2026-07-01 ~ 2026-08-27     46,145 /    46,235   ← 거의 전부
재적재 시각 범위           2026-09-04 ~ 2026-09-21
```

일일 배치가 **최근 몇 달의 과거 가격을 다시 받아 덮어쓴다.** 그래서 IC 가 달라진
3개 평가일이 정확히 그 기간이다.

```text
2026-04-30   원본 -0.4840   재현 -0.4857
2026-05-29   원본 -0.2962   재현 -0.2968
2026-06-30   원본 -0.3194   재현 -0.3193
```

2026-03 이전은 재적재가 0행이고, 그 기간 IC 는 전부 일치한다.

### 1-5. 근본 원인

**백테스트가 고정된 데이터 스냅샷 없이, 계속 바뀌는 라이브 DB 를 읽는다.**
원본은 가격 해시를 남겨 변동을 **감지**할 수는 있지만, 원본 입력을 **재구성**할
수는 없다. 따라서 **원본 artifact 를 지금 코드로 똑같이 다시 만드는 것은 불가능**
하다 — 코드가 같아도.

### 1-6. 재현 중 개발자 절차 오류 1건

설계자 지시대로 `app/ml_relative_upside_model.py` 의 docstring(모델 비교 금지
문구)을 정정했는데, 이 파일이 **baseline 의 고정 모듈**이다. 주석만 고쳐도 바이트
해시가 바뀌어 "코드는 그대로" 를 증명할 수 없게 된다. 실행 코드(AST)는 같았지만
**재현 기준을 흐리게 만들었다.**

→ **그 파일의 docstring 은 되돌렸다.** 고정 모듈 3개가 다시 원본과 일치한다.
설계자 결정 3 에 따라 **새 기준선을 만드는 커밋에서 다시 정정**했다(§4-4).

### 1-7. 처리 — `LEGACY_BASELINE_NON_REPRODUCIBLE`

원본 두 파일은 그대로 두고(sha256 `a55e7292…` · `8d186239…`), 옆에 표시 파일
`state/ml/validity/LEGACY_BASELINE_NON_REPRODUCIBLE.json` 을 둔다. 145 라는 평가일 수는
이 표시 파일에만 역사 값으로 남고, 코드 상수에서는 뺐다 — 새 기준선의 평가일 수는
스냅샷 manifest 가 정한다.

---

## 2. universe 복원 가능성 — **공식 출처로 가능**

### 2-1. 출처

저장소가 **이미 쓰는** KRX OpenAPI 다. 신규 API 가 아니다.

```text
data-dbg.krx.co.kr/svc/apis/etp/etf_bydd_trd   (ETF 일별매매정보)
호출처   app/market_briefing/krx_sync.py:42 · scripts/ops02b1_gate/fetch_snapshot.py:23
인증     .env KRX_API_KEY (값 미출력)
```

`basDd`(기준일)를 주면 **그날 상장돼 있던 ETF 전체**를 돌려준다(그날 거래량 0 인 종목 포함 ·
휴장일·토요일에도 행은 오고 가격 필드는 빈 문자열). 과거 날짜를 주면 **그
시점의 universe** 가 나오고, 이후 폐지된 ETF 도 들어 있다. 응답에 종가
(`TDD_CLSPRC`)도 있다.

### 2-2. 탐침 결과 — 저장 0 · DB 적재 0

외부 호출은 **7회**다(과거 3시점 × 2회 + 최근 1회). 결과는 화면 출력만 했다.

| 기준일 | KRX universe | 우리 DB 그날 | 우리 DB 에 **전혀 없는** 종목 | 그중 지금 폐지 | **누락 비율** |
|---|---:|---:|---:|---:|---:|
| 2015-01-05 | 172 | 118 | 54 | **54** | **31.4%** |
| 2018-06-01 | 367 | 289 | 78 | **78** | **21.3%** |
| 2021-06-04 | 480 | 417 | 63 | **63** | **13.1%** |

- **우리 DB 가 가진 종목은 전부 KRX 목록 안에 있다**(118 → 118 일치 등).
- **빠진 종목은 100% 상장폐지 종목**이다 — 지금도 상장 중인데 우리가 못 받은 것은
  0건이다. 최근(2026-09-18) KRX 상장 1,171 과 대조했다.
- 예: `091200 KOSEF IT` · `091210 TIGER KRX100` · `098560 TIGER 방송통신` ·
  `139310 TIGER 금속선물(H)`

**생존편향이 처음으로 정량화됐다.** 과거로 갈수록 누락이 크다 — 백테스트 초기
구간일수록 수익률이 더 부풀려진다.

### 2-3. 공식 호출 한도 — 확인됨 (Gate 1)

KRX OPEN API 이용약관(2025-12-26 시행) 원문과 공식 FAQ 를 인용으로 확인하고, 인용마다
페이지를 다시 열어 문장이 실제로 있는지 독립 검증했다(12건 모두 원문 일치).

```text
일일 한도     인증키당 1일(0시~24시) 10,000회 — 약관 제8조④ · FAQ "429 에러"
초당·분당     별도 제한 없음 — FAQ
초과 시       HTTP 429 · "서비스가 중지될 수 있다"
제공 기간     2010-01-04 데이터부터 (서비스 목록 · API 상세 · 개발 명세서)
이용 조건     비상업 목적 · 제3자 제공 금지(제11조②) · 화면 표출 시 출처 표시(제10조③)
폐지 종목     "기준일 당시 상장되어 있었다면 이후 상장폐지된 종목도 포함" — FAQ
```

필요 호출(2014-01-02 ~ 2026-09-21 평일)은 **3,318회**로 한도 안이다. 운영 07:20 수집과
같은 키일 수 있어, 한 KST 일 5,000회(한도의 절반)를 코드로 막는다.

### 2-4. 저장 방식 (결정 2 그대로)

```text
위치       state/ml/research/krx_etf_universe.sqlite  (PC 전용 · gitignore · 운영 DB 경로면 거부)
원응답     krx_raw_response  — 본문 그대로 append-only · payload sha256
호출 기록  krx_fetch_attempt — batch · 조회 시각(UTC·KST일) · HTTP 상태 · 오류
행         krx_etf_daily_raw — 원응답 행 dict 그대로 · etf_master 로 거르지 않음
checkpoint krx_download_plan — 날짜별 상태 · 중단 후 이어받기
version    krx_dataset_version / member — 거래일 → 응답 1개 · 봉인 후 변경 불가
충돌       krx_refetch_conflict — 같은 OPEN version 에 이미 붙은 거래일을 재수집해 TRADED 로 왔고
          payload hash 가 다르면 기존 member 유지 + 기록 (재수집이 NON_TRADING·NO_ROWS 면
          비교·기록 없음 — raw 는 남는다)
          → 새 version 은 derive_version 으로만
```

거래일 달력 API 가 없어(FAQ) 평일 전부를 계획하고 응답으로 판정한다. 휴장 평일·토요일은
**행은 오지만 가격이 빈 문자열**이다(canary 실측 · `NON_TRADING`).

### 2-5. POC4-00 기록 정정

POC4-00 §19-3 은 "**저장소 데이터만으로는** 복원 불가" 라고 적었다. 그 문장은
맞다(상장일 필드 0/1,145). 다만 **저장소 밖 공식 출처로는 복원 가능**하다는 것이
이번에 확인됐다. `SURVIVORSHIP_BIAS = RESOLVED_OR_ACCEPTABLY_BOUNDED` 로 가는
길이 생겼다.

---

## 3. 확정된 설계자 사항

```text
RF_COMPARISON            APPROVED   (사전 고정 설정 최대 3개 · test 보고 추가 금지)
AUTO_TUNING              NOT_APPROVED
XGBOOST_LIGHTGBM         NOT_APPROVED · INSTALL 0
POC4-05_EVIDENCE_SCOPE   PC_UI_ONLY
PUSH_ML_INTEGRATION      NOT_APPROVED
OCI_ML_PROMOTION         GATED  (POC4-00 §24-3 의 8개 조건)
TRACK_A                  future_excess_return_20d 회귀 — 모델 비교용
TRACK_B                  위험 구간 분류 — 사용자 출력용
NEW_IMMUTABLE_BASELINE   APPROVED   (결정 1)
KRX_HISTORICAL_SOURCE    APPROVED_WITH_GATES (결정 2)
UNBIASED_PERFORMANCE_CLAIM NOT_YET
```

---

## 4. 재개 계획 — 작업 1~5 (PLAN 재제출 없음 · 설계자 지시 순서)

### 4-1. 불변 스냅샷 (결정 1)

```text
만들기    scripts/ml_baseline_tool.py build --cutoff <날짜> --baseline-id <id>
          라이브 DB 를 mode=ro 로 ATTACH → 한 읽기 트랜잭션 안에서 평가 입력 3개 테이블
          (etf_master · etf_daily_price(cutoff 이하) · market_refresh_log) + E1 비교용 점수
          JSON 을 새 bundle 로 복사 → 파일 0444 봉인. 이미 있는 bundle 은 덮어쓰지 않는다.
manifest  dataset sha256 · 테이블별 행 수·종목 수·최소일·최대일·내용 hash · schema hash ·
          cutoff · 라이브 DB 당시 통계 · E1 JSON sha256·asof · **평가일 목록과 개수**
평가      scripts/run_ml_score_validity_eval_v1.py --snapshot-manifest · --cutoff · --out-dir
          세 인자 모두 필수 — 라이브 DB 로 평가하는 경로는 없앴다.
fail-closed  manifest·파일 누락 / sha256 불일치 / cutoff 불일치 / 실행 중 원본 변경 /
          평가일 목록 불일치 / 코드가 commit 과 다름 → 결과·meta·run_manifest 를 쓰지 않고 실패
          (예외: 코드가 commit 과 다를 때 개발·테스트용 --allow-dirty-code 를 주면 실행해서
          결과를 쓰고 run_manifest 에 official=false 로 기록한다)
라이브 차단  평가 중 sqlite 접속은 hash 를 확인한 작업 사본과 임시 재현 DB 로만 허용.
          E1 JSON 도 hash 를 확인한 사본만 읽는다.
기존 결과  out-dir 는 **새 폴더**여야 한다 — state/ml/validity/ 와 그 하위, 이미 있는 폴더는 거부
          (검증자 P1 수정 · 덮어쓰기와 실패 시 이전 결과 잔존을 구조로 막는다)
```

작업 사본을 쓰는 이유 — 운영 조회 함수(`market_data_store._connection`)가 처음 여는 DB 에
`CREATE TABLE IF NOT EXISTS` 를 쓴다. 봉인 파일을 직접 열면 그 쓰기가 봉인을 깬다.

### 4-2. 평가일 수 계약

`E2_EXPECTED_POINT_COUNT = 145` 상수를 코드에서 뺐다. 전체 실행은 **2014-06-30 시작 +
manifest 평가일 목록과 완전 일치**를 요구한다(수만 맞고 날짜가 달라도 실패). `--limit-dates`
스모크는 manifest 목록의 부분집합이어야 한다. 145 는 LEGACY 표시 파일에만 남는다.

### 4-3. provenance (run_manifest.json)

```text
입력     baseline_id · manifest 파일 hash · manifest 내용 hash · dataset·E1 sha256 · schema hash · cutoff
코드     git HEAD · app/·scripts/·requirements.txt 미커밋 변경 게이트(폴더 단위) ·
         고정 모듈 3개 + 실제로 import 된 app/·scripts/ 모듈 전부의 raw sha256·정규화 AST hash
환경     Python · torch/numpy/pandas/scipy/scikit-learn 버전 · SQLite · requirements.txt sha256
실행     인자 전부 · official(= commit 과 같은 코드 · 전체 기간 · E1 포함)
결과     결과 파일 sha256 · canonical sha256 · 평가일 목록·개수 · warmup 목록
```

### 4-4. 고정 모듈 docstring (결정 3)

새 기준선을 만드는 커밋 `be579619` 에서 정정했다.

```text
app/ml_relative_upside_model.py   raw sha256        8cb88f9e… → b41b2a9a…
                                   정규화 AST hash   1ba8f5cb… = 1ba8f5cb…  (동일)
```

### 4-5. 결정성 검증 (검증 기준 1~4)

```text
기준 1  같은 스냅샷으로 전체 실행 2회 → canonical sha256 · 평가일 목록 비교 (실제 데이터)
기준 2  합성 DB 테스트 — 라이브에 새 날짜 추가 뒤 같은 스냅샷 재실행 결과 동일
        대조군: 새 날짜를 담은 새 스냅샷이면 평가일 자체가 달라진다
기준 3  합성 DB 테스트 — 라이브 과거 행 변경 뒤 같은 스냅샷 재실행 결과 동일
        대조군: 변경을 담은 새 스냅샷이면 같은 평가일의 IC 가 달라진다
기준 4  manifest·dataset·E1 누락 / hash 불일치 / 실행 중 변경 → 실패 · 아무것도 안 씀
```

### 4-6. KRX universe (결정 2 Gate 1~6)

```text
Gate 1  공식 한도 확인 — §2-3
Gate 2  재시작 가능한 downloader — checkpoint · 날짜마다 commit
Gate 3  canary 19개 기준일 + 같은 날짜 재수집 1회 = 호출 20회
Gate 4  중복·누락·hash·재시도·backoff — canary 검증 + 가짜 fetcher 테스트
        (5xx·네트워크 지수 backoff 재시도 · 429 즉시 중단 · 그 밖 4xx 즉시 중단 ·
         연속 실패 3회 중단 · 하루 상한)
Gate 5  한도 확인됨 → 2014-01-02 ~ 2026-09-21 평일 전체 적재
Gate 6  (해당 없음 — 한도가 공식 확인됨)
```

---

## 5. 작업 6 — 설계자 결정 (2026-09-24)

개발자가 올린 질문 3개(embargo 위치 · 비용 수치 · 지표 기준)에 대한 결정이다. 구현과 결과는 결과서 §4-10.

### 5-1. purge·embargo — 개발자 제안 (a) 승인

```text
TRAIN_VALIDATION_PURGE = 20 trading days
E2_EVALUATION_CHANGE   = 0
FROZEN_BASELINE_CHANGE = 0
```

근거(코드로 재확인) — 기준일 t 의 학습 행은 절단 이력(≤ t)에서 target 이 있는 행이라 label 종료일 ≤ t 이고
(스냅샷으로 t=2020-06-30·2026-07-31 재계산: 학습 행 target 종료일 최대 = t · asof 최대 = t−20거래일), E2 label 은
진입 t+1 부터다. 모델 80/20 split 의 뒤 20% 는 test loss 에만 쓴다. 그래서 20거래일 차단은 E2 가 아니라
**모델·설정을 고르는 train/validation 분할**에 건다.

- 계약은 날짜로 검사 — 학습 sample 의 label 종료일 < validation 시작일
- validation 뒤 데이터를 학습에 쓰는 fold 면 validation 종료 뒤 20거래일 embargo
- 경계를 한 줄이라도 겹치게 만들면 테스트 실패
- RF 설정 최대 3개 모두 같은 분할

### 5-2. 거래비용

```text
TRANSACTION_TAX_BP = 0          국내 상장 ETF 매매 증권거래세 비징수 (공시 확인 · 설계자)
COMMISSION_BP       = 1.5 per side   ASSUMPTION — 증권사 수수료 가정
SLIPPAGE_BP_GRID    = 5 / 10 / 25 / 50 per side   (50 = 저유동성 스트레스)
PRIMARY_SLIPPAGE    = 10 bp  → 편도 11.5bp
LEGACY_COMPARISON   = all-in 25 bp per side (기존 결과와 비교용으로 유지)
제외               배당소득세 · 매매차익 과세 (거래 시점 비용과 성격이 다르다)
```

### 5-3. 성과지표 — (c) 절대·상대 둘 다

```text
절대   net strategy equity curve · CAGR · MDD · annualized volatility · Sharpe_0rf
상대   KODEX200 benchmark equity curve · active return · tracking error · information ratio ·
       relative wealth · relative MDD
산식   절대 equity = Π(1 + 비용 차감 후 전략수익률) · benchmark = Π(1 + KODEX200 수익률) ·
       relative = 전략 equity / benchmark equity  (차감 수익률 복리 누적 금지 — 차감은 IC·IR 에만)
```

무위험수익률 source 가 없어 `Sharpe` 가 아니라 `Sharpe_0rf` 로 표시한다. 승격 판단의 1차 축은 상대성과다.

---

## 6. 산출물 · 상태

결과서 §4 에 실측값으로 정리한다(스냅샷 hash · 두 실행 비교 · KRX 적재 결과 · 132MB 임시 DB
처리).

---

## 7. 이번 단계에서 한 변경

결과서 §2 "변경된 파일 목록" 이 정본이다.
