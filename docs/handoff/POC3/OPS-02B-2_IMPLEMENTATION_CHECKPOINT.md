# POC3-OPS-02B-2 — 구현 체크포인트 (개발 세션 전환용)

- **작성일**: 2026-09-12
- **성격**: **프로젝트 전체 HANDOFF 가 아니다.** `OPS-02B-2` **개발 세션 전환용
  체크포인트**다.
- **판정**: 설계자 지시로 **여기서 구현을 중단**하고 다음 개발자 세션으로 인계

```text
CURRENT_STATUS            = PARTIAL_IMPLEMENTATION
ISOLATED_CONTRACT_TESTS   = 50 PASSED
FULL_REGRESSION           = 1511 PASSED / 0 FAILED
BATCH_INTEGRATION         = NOT_STARTED
RUNNER_INTEGRATION        = NOT_STARTED
READY_FOR_VERIFIER        = false
READY_FOR_MOCK            = false
```

> **테스트 통과를 구현 완료로 기록하지 않는다.** 지금 있는 것은 **배선 전
> 코드**다. 6개 모듈이 각각 독립적으로는 계약을 지키지만, **어디에서도
> 호출되지 않는다.**

---

## 1. 현재 Step 과 승인된 PLAN 판정

| 항목 | 값 |
|---|---|
| Step | **`POC3-OPS-02B-2`** — 08:00 시장 흐름 브리핑 메시지·억제·운영 |
| 설계서 | `docs/ai_design/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_DESIGN_V1.md` |
| PLAN | `docs/ai_plan/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_PLAN_V1.md` (**V1.2**) |
| PLAN 판정 | **`APPROVED_WITH_REQUIRED_EDITS`** |

```text
IMPLEMENTATION    = AUTHORIZED        (로컬 한정)
COMMIT_PUSH       = NOT_AUTHORIZED
OCI_DEPLOY        = NOT_AUTHORIZED
AUTOSEND          = false 유지
LIVE_SEND         = NOT_AUTHORIZED
ACTIVATION_BLOCK  = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

**선행 `OPS-02B-1` Gate 결론** (커밋 `988b0494` · `CLOSED`)

```text
OUTLOOK_RELATIONSHIP       = ADOPT
OPERATING_RULE             = SP500_SIGN_V1      (OLS = RESEARCH_REFERENCE)
SECTOR                     = NOT_EVALUATED
INDEX_LEADERSHIP_GATE      = AVAILABLE
INDEX_LEADERSHIP_OPERATION = CURRENTLY_UNAVAILABLE
KOSPI_VIX_INTEGRITY        = PASS
```

확정 계약 원문은 **PLAN §M** 에 전부 있다. 다음 세션은 **§M 을 먼저 읽는다.**

---

## 2. `git status --short` — 실측 원문

```text
 M docs/ai_plan/POC3/POC3-OPS-02B_MARKET_BRIEFING_REDEVELOPMENT_PLAN_V1.md
?? app/market_briefing/
?? docs/ai_design/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_DESIGN_V1.md
?? docs/ai_plan/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_PLAN_V1.md
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
?? tests/test_market_briefing_contracts.py
```

> **worktree 는 깨끗하지 않다.** "테스트가 안정적" 인 것과 다르다.
> **임의로 정리하지 않았다** — `git stash`·`reset`·`checkout` 0건.

| 항목 | 내용 |
|---|---|
| ` M` 1건 | `02B` PLAN — **OCI 자동 pull 오기 정정** (실측: 수동 배포) |
| `??` 4건 | 이번 Step 산출물 (모듈 디렉터리 · 설계서 · PLAN · 테스트) |
| `??` 1건 | **`INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` — 사용자 소유. 건드리지 않았다** (§11) |

---

## 3. 완성된 6개 모듈

`app/market_briefing/` — **1,293줄** (`__init__.py` 11줄 포함)

| 파일 | 줄 | 책임 |
|---|---:|---|
| `krx_store.py` | **232** | 신규 무조정 가격 계열 저장소 · snapshot 검증 · idempotent upsert · 21거래일 창 |
| `flow.py` | **262** | 조립 흐름 · fingerprint · 반복 억제 · 상태 저장 |
| `meta_gate.py` | **229** | API↔CSV 정합성(순수 함수) · **07:20 결과 소비 경계** |
| `evidence.py` | **226** | `SP500_SIGN_V1` 방향 + 기초지수 산출 |
| `render.py` | **172** | 본문 · 부분 산출 6분기 · 안내 문구 4종 |
| `calendar.py` | **161** | 거래일 snapshot 로더 · Gate · fail-closed |
| `__init__.py` | 11 | 패키지 |

**KS-10** — 단일 파일 최대 262줄. 설계자 판정: **현 시점 Cleanup 대상 아님.**

### 구현된 핵심 계약 (테스트로 고정)

| 계약 | 구현 위치 |
|---|---|
| `MIXED` 없음 · 0은 `FLAT` | `evidence.decide_outlook` — **S&P500 인자만 받는다** |
| Nasdaq·반도체 방향 미개입 | 〃 (함수 시그니처로 차단) |
| API-only/지수명 불일치 1건 → `CSV_REFRESH_REQUIRED` | `meta_gate.evaluate_consistency` — **coverage 와 무관** |
| coverage 분모 = `max(api, csv)` | 〃 — API 부분 응답 차단 |
| 세 기준 가격 모두 있어야 `n` 포함 | `evidence.compute_index_leadership` |
| 21거래일 미만이면 창 미생성 | `krx_store.resolve_window` |
| 연도 미포함 캘린더 → `KRX_CALENDAR_REFRESH_REQUIRED` | `calendar.check_trading_day` |
| **fingerprint 는 본문이 만들어진 뒤에만 비교** | `flow.assemble_market_briefing` |
| 정상 0개는 **안내 없이 문단 생략** | `render.render_market_briefing` |

---

## 4. 테스트 결과

| 항목 | 결과 |
|---|---|
| `tests/test_market_briefing_contracts.py` | **50 passed** |
| **전체 회귀** `pytest tests/` | **1,511 passed / 0 failed** (141.09s) |
| 직전 회귀 | 1,461 → **+50** |
| `black --check app scripts tests` | `321 files would be left unchanged` |
| `flake8 app scripts tests` | exit 0 |

**격리** — 합성 fixture · 임시 DB(`tmp_path`) 만 사용. 외부 조회 0건 · 라이브
DB·state 미접근 · 발송 0건.

> 테스트 작성 중 제 검사 2건이 **docstring 설명 문구**와 **신규 테이블명 자체**를
> 금지어로 오탐했다. AST 로 docstring 을 제거하고 단어 경계 정규식으로 고쳤다.
> 계약 위반이 아니라 **검사 방식 문제**였다.

---

## 5. 아직 연결되지 않은 경로

**6개 모듈은 어디에서도 호출되지 않는다.**

| 경로 | 상태 |
|---|---|
| 07:20 배치 → KRX 전종목 수집 | **미연결** |
| 07:20 배치 → 무조정 가격 적재 | **미연결** |
| 07:20 배치 → API·CSV 정합성 판정·저장 | **미연결** |
| 07:20 배치 → 미국 지수 3종 갱신 | **미연결** |
| 08:00 runner → `flow.assemble_market_briefing` | **미연결** |
| runner §6-c → 판정 분기 | **미연결** |
| runner §8 → 상태 저장 | **미연결** |
| `market_briefing` 구 조립기 우회 | **미적용** (`SKIP_EVIDENCE_KINDS` 미수정) |

기존 `market_briefing` 은 **여전히 구 경로**(`compose_market_discovery` →
`build_runtime_message`)를 탄다. flag 가 `false` 라 발송되지 않는다.

---

## 6. 남은 작업 — **순서 고정**

```text
1.  현재 diff 와 checkpoint 대조
2.  07:20 KRX 전종목 수집·가격 적재·정합성 연결
3.  미국 지수 3종 benchmark 배치 연결
4.  배치 focused test 와 기존 배치 회귀
5.  market_briefing 전용 runner helper 연결
6.  runner 최종 줄 수 측정
7.  flow-through 테스트
8.  보호 로직 역검증
9.  전체 회귀
10. 목업 7종 생성
11. 구현 결과 보고
```

### runner 배선 규칙 (설계자 확정)

| # | 규칙 |
|---|---|
| 1 | 보유 브리핑(§3-c)·급락 알림(§3-d) 분기 **변경 금지** |
| 2 | 공통 `record_send_success` 계약 **변경 금지** |
| 3 | 줄 수를 맞추기 위한 **압축 코딩 금지** |
| 4 | 최종 **650줄 이하** |
| 5 | 650 이하로 연결 불가하면 **즉시 중단하고 KS-10 Cleanup 필요성 보고** |
| 6 | 연결 전후 기존 PUSH **flow-through 회귀 필수** |

---

## 7. 신규 KRX 무조정 가격계열 계약

```text
TABLE        = krx_etf_daily_price_unadjusted
SOURCE       = KRX_OPEN_API
PRICE_BASIS  = UNADJUSTED_TRADED_PRICE
PRIMARY KEY  = (date, ticker)
```

| 필드 | 내용 |
|---|---|
| `date` | KRX 응답의 **실제 기준일** (ISO) |
| `ticker` · `close` | 종목코드 · 무조정 종가 |
| `source` · `price_basis` · `collected_at` | 출처 · 기준 · 수집 시각 |

**격리 계약 — 반드시 유지**

- `etf_daily_price` 와 **join 금지** · `open`/`close` **수정 금지**
- 5일·20일 수익률의 **분자·분모 모두 신규 계열**에서
- 조정/무조정을 **구간 중간에서 연결 금지**
- **다른 UI·ML·보유 PUSH 의 가격 source 로 확장 금지**
- **이 변경으로 `DEF-ETF-DAILY-PRICE-BASIS-CONSISTENCY` 가 해결됐다고 기록하지
  않는다.** 분배락 민감도는 BACKLOG 유지

**적재 계약** — 20일 수익률에 **최신일 포함 21개 완료 거래일** 필요 · 최초 적재는
그 범위만(**전체 backfill 금지**) · 초기 역탐색 **40달력일** · 일별 **7달력일** ·
하루 응답의 **전체 ETF 저장**(196종만 저장하지 않는다) · **idempotent** ·
빈 응답·ticker 중복·종가 결측·0 이하·기준일 불일치는 **fail-closed**.

> **OCI 초기 적재는 별도 승인 대상이며 수행하지 않았다.**

---

## 8. autosend 활성화 차단 상태

```text
ACTIVATION_BLOCKED = true
BLOCK_REASON       = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

**공식 KRX 거래일 snapshot 이 없다.** 조사 결과(PLAN §F-Q1):

| 후보 | 결과 |
|---|---|
| KRX Open API 휴장일 서비스 | **404** (`gen/hldy`·`gen/holiday`·`cal/hldy`) |
| KRX 지수 일별시세로 당일 판정 | **불가** — 거래일에도 08시엔 `rows=0` |
| KRX 웹 휴장일 화면 | **로그인 필요** |
| 저장소 내 캘린더 | **없음** |

`calendar.check_trading_day` 는 **파일이 없으면 `KRX_CALENDAR_REFRESH_REQUIRED`
로 fail-closed** 한다. 따라서 **autosend 를 켜도 발송이 0건**이다.

**실제 snapshot 은 사용자 승인·제공 후 별도 반영**한다. 형식은 `date` 컬럼 1개
CSV (`state/market_meta/krx_trading_days_YYYY.csv`). **추정값·빈 placeholder 로
만들지 않는다.**

---

## 9. runner 줄 수와 KS-10

| 항목 | 값 |
|---|---:|
| `scripts/run_three_push_runtime_oci.py` **현재** | **637줄** (미변경) |
| KS-10 임계 | 650 |
| **여유** | **13줄** |

PLAN §I-1 의 예상 순증가는 **+15 내외**다. **여유를 넘는다.** 설계자가 다음을
금지했으므로 다른 방법을 찾아야 한다.

- ❌ 보유 PUSH(§3-c·§3-d) 분리로 여유 만들기
- ❌ `record_send_success` 인자 변경
- ❌ 압축 코딩

**가능한 방향** — `market_briefing` 전용 **판정 helper 1함수**로 §6-c 분기를
2줄로 묶고, §4 분기를 **교체**(추가가 아니라)해 순증가를 줄인다. 그래도 650을
넘으면 **즉시 중단하고 보고**한다.

---

## 10. 이번 세션 실적 — 쓰기 0건

| 항목 | 실적 |
|---|---|
| commit | **0건** |
| push | **0건** |
| `git stash`·`reset`·`checkout` | **0건** |
| OCI write · 배포 | **0건** |
| 운영 DB write | **0건** |
| state write | **0건** |
| Telegram 발송 | **0건** |
| autosend | **`false` 유지** |
| `STATE_LATEST`·`PROGRAM_TRUTH` 에 완료·운영 기록 | **없음** |

읽기 전용으로 수행한 것 — 저장소·로컬 DB 읽기 · OCI 읽기 전용 SSH(cron·flag·
HEAD·ticker 별 freshness) · 소스 grep · KRX Open API 읽기 전용 probe.

---

## 11. 사용자 소유 파일

```text
docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md   (untracked)
```

**개발자가 만든 파일이 아니며, 읽지도 옮기지도 지우지도 않았다.** 사용자가
적절한 위치로 옮겨 커밋 관리한다.

---

## 12. 다음 세션의 첫 행동

1. **PLAN §M 을 읽는다** — 설계자 확정 계약이 전부 거기 있다
   (`docs/ai_plan/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_PLAN_V1.md`)
2. `git status --short` 를 찍어 **§2 목록과 대조**한다 (남은 작업 1번)
3. 일치하면 **남은 작업 2번(07:20 배치 연결)** 부터 시작한다
4. 불일치하면 **임의로 정리하지 말고** 차이를 먼저 보고한다

**하지 말 것** — 테스트가 통과한다고 구현 완료로 보고 · 검증자에게 제출
(`READY_FOR_VERIFIER = false`) · 목업 생성 (`READY_FOR_MOCK = false`) ·
`PUSH 3_OF_3` 기록 · commit·push·배포·발송.

**설계자에게 갈 시점** — 러너가 **650줄을 넘을 때**, 또는 새로운 source
identity·schema 충돌이 발견될 때. 그 외에는 구현을 계속한다.

---

## 부록 A. KS-10 Cleanup 단위 결과 (2026-09-12)

단위명 `POC3-OPS-02B-2-KS10-RUNNER-EVIDENCE-EXTRACTION` · 부모 Step `PAUSED_BY_KS10`.

### A-1. 무엇을 했나

러너 §4(runtime evidence 조립) 블록을 `app/three_push_runtime/runner_evidence.py`
의 `assemble_legacy_evidence()` 로 **통째로 옮겼다**. 판정·입출력·예외 동작을
바꾸지 않았다. 실패 경로에서 `evidence` 는 갱신되고 `message_text` 는 보존되는
이전 순서까지 같다. 러너 §4 는 14줄 호출 하나로 줄었고,
`compose_runtime_evidence`·`availability_summary` import 는 helper 안으로 옮겼다.

설계자 승인 범위 밖 삭제는 하지 않았다 — `spike_or_falling_alert` 경로 30행
포함 **삭제 0건**.

### A-2. 줄 수 (실측)

| 파일 | Cleanup 전 | 후 |
|---|---:|---:|
| `scripts/run_three_push_runtime_oci.py` | 656 | **648** |
| `app/three_push_runtime/runner_evidence.py` | 129 | 184 |

`656` 은 부모 Step 배선 직후 값이다. `git show HEAD:` 기준(=부모 Step 착수 전)은
`637` 이다. KS-10 백엔드 임계 초과 **0건**.

### A-3. 부수로 드러난 결함 2건 — 둘 다 라이브 자원 침범

Cleanup 자체가 만든 결함은 아니지만, 옮기면서 테스트를 돌리자 드러났고
**고치지 않으면 회귀가 라이브를 계속 건드린다**.

1. **테스트가 라이브 시장 브리핑 상태 파일에 썼다.**
   경로가 러너 상수가 아니라 `runner_market_briefing` 안에서 `STATE_DIR` 로
   풀려 기존 격리 fixture 밖이었다. `conftest` 의 상태 격리 fixture에 시장
   브리핑 상태 2종을 추가하고, 모듈의 `STATE_DIR` 와 원본 상수를 함께 격리했다.

2. **배치 테스트가 라이브 KRX Open API 를 실제로 호출했다.**
   `refresh_benchmarks` 만 stub 돼 있었고 `sync_krx_daily` 는 그대로였다. 맥
   `.env` 에 `KRX_API_KEY` 가 있어 외부 호출이 나갔다. 네트워크 경계
   (`krx_sync._default_fetcher`)에 차단 fixture 를 추가했다.

### A-3-1. 사고 기록 — `LOCAL_ONLY_INCIDENT` (설계자 §4 지시)

INCIDENT_CLASS = LOCAL_ONLY_INCIDENT
RESTORE_PROVEN = false
DELETE_OR_ROLLBACK = NOT_PERFORMED

| 항목 | 값 |
|---|---|
| 파일 1 | `/Users/hyungsookim/projects/krx_hyungsoo/state/three_push/market_briefing_state_latest.json` |
| 파일 2 | `/Users/hyungsookim/projects/krx_hyungsoo/state/three_push/market_briefing_meta_consistency_latest.json` |
| git 추적 | 둘 다 **untracked** (`git log --all -- <경로>` 출력 0건) |
| 현재 sha256 (파일 1) | `8fcde0e47fa038a024dcfee88ae76eddd2bffc3845b045d2659f4996bc69e46d` (162 bytes) |
| 현재 sha256 (파일 2) | `82a105170c70431195185bf4adbaa61aedb1f1f63dc2aa9ec6be90ccff5fe4f2` (485 bytes) |
| 범위 | 맥 로컬 전용. OCI·운영 경로 동일 파일 **미접근** |

**"복원했다" 고 쓰지 않는다.** 두 파일은 2026-09-12 개발자의 수동 검증 실행이
처음 만든 것이고 git 이력에 없다. 테스트가 덮어쓰기 **전**의 바이트를 해시로
남겨두지 않았으므로 원본 동일성을 증명할 수 없다. 따라서 `LOCAL_ONLY_INCIDENT`
로만 기록한다. 설계자 지시에 따라 **삭제·되돌림은 하지 않았다.**

가드 적용 **후** 전체 회귀 1회를 돌려 두 파일의 sha256 이 전후 동일함을
확인했다 — 지금은 회귀가 라이브를 건드리지 않는다.

### A-3-2. 가드 역검증 (무력화 시 실제로 실패하는가)

두 가드를 직접 호출해 확인했다. 출력 원문:

```text
[가드 전] _default_fetcher = _default_fetcher
[가드 후] _default_fetcher = _blocked
차단 확인 AssertionError: 테스트가 라이브 KRX Open API 를 호출했다. `fetcher=` 로 stub 을 넘겨라.
LIVE STATE_DIR      = /Users/hyungsookim/projects/krx_hyungsoo/state/three_push
격리 후 _mb.STATE_DIR = /var/folders/1y/7hrg9b3s3xb5dn_2gf12vkw00000gn/T/tmp4ub436ty/three_push
격리 동작 = True
```

상태 격리를 **일시 해제**하고 `tests/test_runtime_runner_partial_delivery.py` 를
돌렸을 때의 결과도 기록한다 — 라이브 경로 접근이 실제로 검사에 걸렸다.

```text
ERROR tests/test_runtime_runner_partial_delivery.py::test_runner_all_chunks_success_partial_false_and_registry_write
3 passed, 1 warning, 1 error in 0.74s
```

KRX 차단 가드를 넣기 **전** 전체 회귀에서는 라이브 정합성 파일 변경이 검사에
걸려 4건이 ERROR 였다(`test_market_benchmark_freshness.py` 3건 ·
`test_oci_market_data_refresh.py` 1건). 가드 적용 후 0건이다.

### A-4. 되돌린 것 1건

부모 Step 에서 `_MD_PUSH_KINDS` 를 비웠으나, 러너는 `SKIP_EVIDENCE_KINDS` 에서
이미 끊기므로 **이중 차단**이었고 legacy market discovery 계약 테스트 2건만
검사 불가가 됐다. 라우팅을 원복했다. 러너가 `market_briefing` 으로 이 경로에
들어가지 않는 것은 그대로다.

### A-5. 검증 결과

- `black --check` 324 files unchanged · `flake8` 0건 · `py_compile` OK
- 전체 회귀 **1533 passed, 0 failed, 0 errors** (137.59s)
- 회귀 전후 라이브 상태 파일 sha256 동일 — 침범 없음
- commit · push · 배포 · 실발송 **0건**
