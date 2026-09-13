# POC3-OPS-02B-2 — KS-10 Cleanup 2건 종료 · 부모 Step 재개 인계

작성일: 2026-09-13 · 성격: **챕터 종료 + 다음 챕터 진입 문서**

```text
CLEANUP_KS10_RUNNER_EVIDENCE_EXTRACTION = CLOSED
CLEANUP_KS10_TRIGGER_FILE_SPLIT         = CLOSED
PARENT_STEP  = POC3-OPS-02B-2 (PAUSED → 재개 가능)
NEXT_ACTION  = 부모 Step 남은 작업 5건 (§4)
AUTOSEND     = false · PUSH = 2_OF_3
```

---

## 1. 이 챕터에서 무슨 일이 있었나

부모 Step `OPS-02B-2`(08:00 시장 흐름 브리핑) 구현 중 **러너가 KS-10 임계(650줄)를
넘었다**(656줄). 설계자가 부모 Step 을 `PAUSED_BY_KS10` 으로 멈추고 Cleanup 2건을
분기했다. 둘 다 종료됐다.

### 1-1. `POC3-OPS-02B-2-KS10-RUNNER-EVIDENCE-EXTRACTION`

러너 §4(runtime evidence 조립) 블록을 `app/three_push_runtime/runner_evidence.py` 의
`assemble_legacy_evidence()` 로 옮겼다. **656 → 648줄.**

부수로 **라이브 자원 침범 2건**이 드러나 고쳤다.

1. 테스트가 라이브 시장 브리핑 상태 파일에 썼다 — 경로가 `runner_market_briefing`
   안에서 `STATE_DIR` 로 풀려 기존 격리 fixture 밖이었다.
2. 배치 테스트가 **라이브 KRX Open API 를 실제 호출**했다 — `.env` 의
   `KRX_API_KEY` 로 외부 호출이 나갔다.

`tests/conftest.py` 에 격리·차단을 추가했다. 설계자 `PASS`.

### 1-2. `POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT`

저장소 전수 측정에서 TRIGGER 2건이 더 나와 분리했다.

| 대상 | 전 | 후 |
|---|---:|---|
| `tests/test_low_frequency_push_operation.py` | 1548 | **삭제** → `tests/low_frequency_push/` 11파일 (최대 420) |
| `frontend/app/components/TodayInvestmentCheckView.tsx` | 907 | **141** + `today/` 신규 8파일 (최대 168) |

```text
TRIGGER_BEFORE = 2 → TRIGGER_AFTER = 0
NEAR = 6 (변동 없음)
BUILD = PASS (사용자 승인으로 dev 종료 → build → 재기동)
```

검증자 **r1·r2 REJECTED → r3 VERIFIED**. 사용자 실화면 확인 완료.

---

## 2. 반려 3라운드에서 배운 것 — 다음 세션이 반복하지 말 것

**구현 코드는 r1 이후 한 줄도 바뀌지 않았다.** 반려 사유는 전부 **증빙 방식과 보고
정확성**이었다. 같은 실수를 반복하지 않으려면:

### 2-1. 동등성 증명의 기준선을 먼저 커밋하거나 명시하라

AST 대조로 "본문 불일치 0건" 을 보고했는데, 기준선이 **커밋되지 않은 working
tree(1548줄)** 였다. 검증자는 `git show HEAD:`(1545줄)로 대조해 **2건 불일치**를
찾았다. 둘 다 사실이지만 **재현 불가능한 기준선 위의 주장은 증빙이 아니다.**

- 리팩토링 전 기준선은 **먼저 커밋하거나**, 최소한 결과서에 "기준선 = `HEAD <sha>`"
  를 명시하고 그 기준으로 측정하라.
- 삭제할 파일의 sha256 을 적을 때 **git 에서 복구되는 버전인지** 확인하라.

### 2-2. stale 정정은 반드시 grep 전수 후 일괄

r2 는 §1 표 한 줄(`PARTIAL · 설계자 판단 대기`)을 지적했다. 같은 모순이 **5곳**에
있었다. 한 줄만 고치면 다음 라운드에 나머지가 다시 나온다.

```bash
grep -rn "<stale 표현>" docs/
```

### 2-3. 측정 없는 수치 금지

staged 를 "51건" 으로 보고했는데 실측 **50건**이었다. `git status` 를 그 자리에서
찍고 출력을 인용하라.

### 2-4. 설계자 승인 명칭과 기존 코드가 충돌하면 멈춰라

설계자가 `today_investment_check/` 를 승인했으나 **이미 `today/` 가 존재**했고 이
화면 전용 부품(`KospiChart.tsx`·`todayHelpers.ts`)을 담고 있었다. PLAN 에 그 사실을
적지 않은 것이 개발자 누락이다. 자체 해석하지 않고 사용자에게 물어 결정을 받았고
설계자가 최종 승인했다(`ADOPT_EXISTING_TODAY`). **충돌 시 "지시문 외 변경" 이 아니라
"사용자 확인 필요" 로 올려야 한다.**

---

## 3. 현재 코드 상태 — 다음 세션이 먼저 볼 것

### 3-1. git

```text
staged = 50 · unstaged = 0 · untracked 제외 3
```

제외 3건(의도적):

| 경로 | 사유 |
|---|---|
| `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` | 사용자 소유. 읽기·이동·삭제·staging 전부 금지 |
| `state/three_push/market_briefing_state_latest.json` | 런타임 상태. `LOCAL_ONLY_INCIDENT` · 삭제·되돌림 금지 |
| `state/three_push/market_briefing_meta_consistency_latest.json` | 위와 같다 |

### 3-2. KS-10 현황 (tracked + untracked 454개 전수)

```text
TRIGGER = 0
NEAR    = 6
```

| # | 줄 | 파일 | 임계까지 |
|---:|---:|---|---:|
| 1 | 648 | `scripts/run_three_push_runtime_oci.py` | **2** (`TRIGGER_STARTS_AT = 651`) |
| 2 | 632 | `app/api.py` | 18 |
| 3 | 626 | `app/ml_score_validity_report.py` | 24 |
| 4 | 616 | `app/holdings_market_evidence.py` | 34 |
| 5 | 855 | `frontend/app/components/JudgmentWorkbenchView.tsx` | 45 |
| 6 | 602 | `app/draft.py` | 48 |

**러너 정책 `FREEZE_AT_648`.** 부모 Step 재개 시 러너에 줄이 늘면 **설계자 판단을
받아야 한다.** 650까지는 허용이고 651부터 TRIGGER 다.

### 3-3. 테스트 가드 (절대 약화시키지 말 것)

`tests/conftest.py` autouse fixture:

| 가드 | 막는 것 |
|---|---|
| `_isolated_holdings_selection_state` | 보유 선정 · 급락 · **시장 브리핑 상태 2종** + `_mb.STATE_DIR` + `three_push_runner_common.STATE_DIR` |
| `_block_live_krx_api` | `krx_sync._default_fetcher` — 라이브 KRX Open API |
| `_block_live_benchmark_refresh` | `upsert_benchmark_prices` 저장 계층 |
| `_stub_oci_calls` | deliver · fetch_outbox_result |

역검증 방법(실경로 노출 0건):

```bash
.venv/bin/python -c "
from _pytest.monkeypatch import MonkeyPatch
import tests.conftest as C
from app.market_briefing import krx_sync
mp = MonkeyPatch(); C._block_live_krx_api.__wrapped__(mp)
krx_sync._default_fetcher('20260911','DUMMY')"
# → AssertionError: 테스트가 라이브 KRX Open API 를 호출했다.
```

### 3-4. 검증 기준선 (회귀 깨짐 판단용)

```text
backend 전체        = 1533 passed / 0 failed / 0 errors (~140초 · run_in_background 필수)
low_frequency_push  = 52 passed
frontend vitest     = 17 files / 191 tests
TodayInvestmentCheck = 35 tests
black               = 334 files unchanged
flake8              = 0건
```

---

## 4. 부모 Step `OPS-02B-2` 재개 — 남은 작업

설계자가 고정한 순서다. **1~6번은 이미 끝났다**(체크포인트 §6 기준).

| # | 작업 | 상태 |
|---:|---|---|
| 1~6 | 배치 연결 · 러너 연결 · 줄 수 측정 | **완료** |
| 7 | flow-through 테스트 | **남음** |
| 8 | 보호 로직 역검증 | **남음** |
| 9 | 전체 회귀 | **남음** |
| 10 | 목업 7종 생성 | **남음** |
| 11 | 구현 결과 보고 | **남음** |

### 4-1. 재개 전 첫 행동

1. `docs/ai_plan/POC3/POC3-OPS-02B-2_MARKET_BRIEFING_MESSAGE_PLAN_V1.md` **§M 완독** —
   설계자 확정 계약이 전부 거기 있다.
2. `docs/handoff/POC3/OPS-02B-2_IMPLEMENTATION_CHECKPOINT.md` — 부모 Step 의 모듈·계약·
   차단 상태. 부록 A 는 선행 Cleanup 기록.
3. `git status --short --untracked-files=all` 로 §3-1 과 대조. 불일치면 임의 정리
   금지 · 차이를 먼저 보고.

### 4-2. 활성화 차단 (해소 안 됨)

```text
ACTIVATION_BLOCKED = true
BLOCK_REASON       = KRX_TRADING_CALENDAR_NOT_PROVIDED
```

공식 KRX 거래일 snapshot 이 없다. `app/market_briefing/calendar.py` 가 파일 부재 시
`KRX_CALENDAR_REFRESH_REQUIRED` 로 fail-closed 하므로 **autosend 를 켜도 발송 0건**
이다. 형식은 `date` 컬럼 1개 CSV
(`state/market_meta/krx_trading_days_YYYY.csv`). **추정값·빈 placeholder 로 만들지
말 것** — 사용자 승인·제공 후 별도 반영.

### 4-3. 하지 말 것

- 테스트 통과를 구현 완료로 보고
- 목업·검증자 제출 (부모 Step 은 아직 `READY_FOR_VERIFIER = false`)
- PUSH `3_OF_3` 기록
- OCI write · 배포 · autosend 활성화 · 실발송
- 러너 줄 수 증가 (설계자 판단 없이)

---

## 5. 승인 상태 요약

| 항목 | 상태 |
|---|---|
| 로컬 구현 | **승인됨** |
| commit | 사용자 요청 시 |
| push | **항상 별도 승인** |
| OCI write · 배포 | **미승인** |
| autosend | `false` 유지 |
| Telegram 실발송 | **미승인** |
| `git stash · reset · checkout` | **미승인** |
| 로컬 DB 30행 · `LOCAL_ONLY_INCIDENT` 2건 | 삭제·되돌림 **미승인** |
