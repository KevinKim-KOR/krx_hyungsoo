# POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT — Cleanup 개발 결과서

작성일: 2026-09-13 · 작성자: 개발자(VSCode Claude) · 수신: 설계자 → 검증자

## 0. 설계자 지정 제출 항목

```text
CLEANUP_STATUS                 = CLOSED
VERIFIER_r3                    = VERIFIED (A·B 전 항목 통과)
USER_SCREEN_CONFIRMED          = YES (2026-09-13 · 「오늘의 투자 점검」 이상 없음)
TRIGGER_BEFORE                 = 2
TRIGGER_AFTER                  = 0
NEAR_BEFORE                    = 6
NEAR_AFTER                     = 6
ALL_SOURCE_FILES_MEASURED      = 454 (tracked 424 + untracked 30)
ORIGINAL_TEST_FILE             = DELETED (껍데기·빈 파일 미생성)
TEST_FUNCTIONS_BEFORE / AFTER  = 52 / 52
COLLECTED_CASES_BEFORE / AFTER = 52 / 52 (이름 단위 diff 0건)
AST_BASELINE                   = HEAD 74ec6dee (1545줄 · sha 398a2de9…)
AST_IDENTICAL                  = 65
APPROVED_PRIOR_CLEANUP_DELTA   = 2
UNEXPLAINED_AST_DIFFERENCE     = 0
PRE_SPLIT_BASELINE_REPRODUCIBLE = false
SPLIT_PRE_BASELINE_PRESERVED   = false
SPLIT_ZERO_BODY_CHANGE_INDEPENDENTLY_PROVEN = false
NO_ADDITIONAL_BODY_DIFF_BEYOND_APPROVED_DELTA = true
RISK_ACCEPTANCE                = 정확히 식별된 선행 변경 2건에 한정
PLAN_3_4_DEVIATION             = APPROVED_FOR_EXACT_2_PRIOR_DELTAS
STAGED_ENTRIES                 = 50
UNTRACKED_EXCLUDED             = 3 (§2.6)
DUPLICATE_COLLECTION           = 0
BACKEND_FOCUSED_TESTS          = 52 passed
BACKEND_FULL_REGRESSION        = 1533 passed / 0 failed / 0 errors (138.37s)
FRONTEND_TSC                   = PASS (exit 0)
FRONTEND_ESLINT                = PASS (exit 0)
FRONTEND_VITEST                = PASS (17 files / 191 tests)
TODAY_VIEW_TEST_FILE_CHANGED   = false (sha256 동일 · 35 tests 통과)
MAIN_PANEL_CHANGED             = false (sha256 동일)
LIVE_STATE_HASH_BEFORE / AFTER = 동일 (§6 표)
LIVE_DB_AND_SIDECAR_HASH_BEFORE / AFTER = 동일 (sidecar 부재)
EXTERNAL_NETWORK_CALLS         = 0
BUILD                          = PASS (exit 0 · 부록 A)
RUNNER_LINES                   = 648
ALLOWED_REMAINING_LINES        = 2
TRIGGER_STARTS_AT              = 651
CURRENT_POLICY                 = FREEZE_AT_648
COMMIT_PUSH_OCI_DEPLOY_SEND    = 0
AUTOSEND                       = false
```

**디렉터리 판정 종결** — 설계자가 `frontend/app/components/today/` 를 최종 승인했다
(`DIRECTORY_DECISION = ADOPT_EXISTING_TODAY` · `RENAME_OR_MOVE_REQUIRED = NO`). §4.1 참조.

---

## 1. 처리한 요구사항

| 요구사항 | 결과 |
|---|---|
| TRIGGER 2건 분리 | **DONE** |
| `tests/low_frequency_push/` 패키지 분리 | **DONE** |
| 프론트 컴포넌트 분리 | **DONE** — 디렉터리는 설계자 최종 승인 `today/` (`DIRECTORY_DECISION = ADOPT_EXISTING_TODAY` · CLOSED · §4.1) |
| 원본 테스트 파일 삭제 (조건 6개) | **DONE** — 조건 전부 충족 후 삭제 |
| 수집 동등성 검증 (이름·parametrize id 대조) | **DONE** — diff 0건 |
| PLAN §3.4 "test 본문 한 줄도 고치지 않음" | **DONE (편차 승인 완료)** — `HEAD` 기준 동일 65건 · 승인된 선행 Cleanup 이월 델타 2건 · 미설명 차이 0건. 설계자 확정 `PLAN_3_4_DEVIATION = APPROVED_FOR_EXACT_2_PRIOR_DELTAS` (§3.1 · §12-0) |
| 프론트 계약 무변경 (§4 10항목) | **DONE** |
| 전수 측정 (tracked + untracked) | **DONE** — 454개 |
| runner 648줄 동결 | **DONE** — 수정 0건 |
| 라이브 경계 역검증 (canary · 실경로 미노출) | **DONE** |
| `npm run build` (사용자 승인 후) | **PASS** — exit 0 · dev 재기동 완료 (부록 A) |

---

## 2. 변경된 파일 목록

### 2.1 신규 — `tests/low_frequency_push/` (11개)

| 줄 | 파일 |
|---:|---|
| 14 | `__init__.py` (원본 머리말의 **사용자 확정 계약 원문** 보존) |
| 306 | `_fixtures.py` (helper 14개 + `_MISSING` 상수) |
| 420 | `test_runner_fail_closed.py` (test 11) |
| 230 | `test_selection_state_isolation.py` (test 5) |
| 163 | `test_holdings_runtime_line.py` (test 5) |
| 157 | `test_reevaluator.py` (test 9) |
| 154 | `test_target_tickers.py` (test 11) |
| 107 | `test_spike_body.py` (test 6) |
| 62 | `test_kind_flag_guard.py` (test 2) |
| 38 | `test_market_quote.py` (test 1) |
| 33 | `test_registry_key.py` (test 2) |
| **1684** | 합계 · **test 52건** · 최대 단일 파일 **420줄** |

### 2.2 신규 — `frontend/app/components/today/` (8개)

| 줄 | 파일 |
|---:|---|
| 168 | `maintenanceQueue.ts` (`MaintenanceItem` · `collectMaintenance`) |
| 145 | `JudgmentQueueSection.tsx` |
| 139 | `KospiHeadline.tsx` |
| 128 | `MaintenanceQueueSection.tsx` (+ 내부 `MaintInfo`) |
| 84 | `KospiDetailSection.tsx` (+ 내부 `BlockedRow`·상수 2종) |
| 84 | `InDevelopmentSection.tsx` (+ 내부 `DevList`·상수 2종) |
| 66 | `OciStatusOneLine.tsx` |
| 43 | `useLightRefreshState.ts` |
| **857** | 합계 · 최대 단일 파일 **168줄** |

### 2.3 수정

| 파일 | 전 | 후 |
|---|---:|---:|
| `frontend/app/components/TodayInvestmentCheckView.tsx` | 907 | **141** |

### 2.4 삭제

| 버전 | 줄 | sha256 | 복구 |
|---|---:|---|---|
| `HEAD`(`74ec6dee`) 커밋본 | **1545** | `398a2de96ffef5644b9f8e3361cbe3cedb42b50bb77b67abed985956b8c50283` | **가능** — `git show HEAD:tests/test_low_frequency_push_operation.py` |
| 삭제 직전 working tree | 1548 | `6864e55a59ce18fa3f0b01a0486516867cb955b2022752acc2c745ce46287f78` | **불가능** — 커밋되지 않았다 |

**정정(검증자 r1 A-2)**: 앞선 기록은 `1548줄 / 6864e55a…` 만 적어 마치 그것이
git 에서 복구되는 원본인 것처럼 읽혔다. 사실은 다르다. git 이 돌려주는 것은
**1545줄 / `398a2de9…`** 이고, 1548 버전은 선행 Cleanup 의 uncommitted 변경 3줄을
포함한 working tree 상태로 **복원할 수 없다**(§3.1).

**껍데기·호환성 명목 빈 파일을 남기지 않았다.** 과거 역사 문서의 경로는 일괄
수정하지 않았다.

### 2.5 건드리지 않은 것

| 파일 | 확인 방법 |
|---|---|
| `frontend/app/components/MainPanel.tsx` | sha256 `9e95d4f3…b6684` 전후 동일 |
| `frontend/app/components/TodayInvestmentCheckView.test.tsx` | sha256 `8b0db836…87de9` 전후 동일 |
| `frontend/app/components/today/KospiChart.tsx` (101) | `git diff` 0건 |
| `frontend/app/components/today/todayHelpers.ts` (86) | `git diff` 0건 |
| `scripts/run_three_push_runtime_oci.py` (648) | 수정 0건 · 648줄 동결 |
| NEAR 6건 전부 | 수정 0건 |

### 2.6 git index 상태 (설계자 §7 — 실측)

```text
STAGED_ENTRIES     = 50
UNSTAGED           = 0
UNTRACKED_EXCLUDED = 3
```

측정: `git status --short --untracked-files=all | grep -c '^[MARD]'` → **50**.
`git diff --cached --name-status | wc -l` → **50**. 두 값이 일치한다.

**이전 "51건" 보고는 틀렸다. 삭제한다.** 검증자 실측 50건이 맞다.

제외한 untracked 3건 — 경로와 사유:

| 경로 | 제외 사유 |
|---|---|
| `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` | **사용자 소유 파일.** 개발자가 만든 것이 아니다. 읽기·이동·삭제·staging 모두 하지 않았다(§11 계약). |
| `state/three_push/market_briefing_state_latest.json` | 런타임 상태 산출물. `state/three_push/` 에서 tracked 인 것은 `previews/` 뿐이므로 추적 대상이 아니다. `LOCAL_ONLY_INCIDENT` 기록 대상이며(§6.3) 설계자 지시로 삭제·되돌림을 하지 않았다. |
| `state/three_push/market_briefing_meta_consistency_latest.json` | 위와 같다. |

`.gitignore` 에 등록된 항목은 아니므로(`git check-ignore` 미해당) **의도적 미staging**
임을 여기 명시한다. 숨기지 않는다.

---

## 3. 테스트 분리 — 의미 보존 증명

### 3.1 AST 기반 본문 동등성 — 검증자 지적 반영 정정 (r1 REJECTED)

**이전 기록("본문 불일치 0건")은 틀렸다. 삭제한다.** 검증자가 `git show HEAD:` 로
대조한 결과 **2건이 다르다**. 검증자 실측이 맞다.

#### 기준선을 명시한다 — 이것이 앞선 보고의 결함이었다

| 기준선 | 줄 | sha256 | 독립 재현 |
|---|---:|---|---|
| `HEAD`(=`74ec6dee`) 커밋본 | **1545** | `398a2de96ffef5644b9f8e3361cbe3cedb42b50bb77b67abed985956b8c50283` | **가능** (`git show HEAD:…`) |
| 분리 직전 working tree | 1548 | `6864e55a59ce18fa3f0b01a0486516867cb955b2022752acc2c745ce46287f78` | **불가능** |

앞선 §3.1 은 **1548 기준**으로 대조해 "0건" 이라고 적었다. 그 기준선은 커밋되지
않았고 지금 복원할 수 없다. `HEAD` 에 선행 Cleanup 의 변경을 다시 적용해
재구성해도 **1547줄 / `244581afa82441a8ab303d7faf273facb80c01d55ce088655e046cc6df01fd94`**
가 나와 `6864e55a` 와 일치하지 않는다(1줄 미설명). 따라서

```text
PRE_SPLIT_BASELINE_REPRODUCIBLE = false
```

**검증자 B-6 지적을 수용한다.** 재현 불가능한 기준선 위의 "0건" 주장은 증빙으로
성립하지 않는다.

#### 재현 가능한 기준선(`HEAD`)으로 다시 측정한 결과

```text
HEAD 정의: 67   분리본: 67
누락: 0건   추가: 0건   중복: 0건
불일치: 2건
  - test_runner_spike_mixed_signals_body_excludes_already_sent
  - test_runner_reeval_exception_forces_failed_no_send
동일: 65건
```

**단위 정정(설계자 §6)**: 67개 정의는 **함수 66개 + 모듈 상수 1개(`_MISSING`)** 다.
그래서 `67 − 2 = 65`(정의 기준)와 `66 − 2 = 64`(함수 기준)가 둘 다 성립한다.
앞선 §3.1 은 두 단위를 섞어 적었다. **정본은 정의 기준 `AST_IDENTICAL = 65`** 이며,
내부 구성은 동일 함수 64개 + 동일 상수 1개다. AST 증명 스크립트가 `FunctionDef`
만 비교하므로 그 출력은 64 로 나오는 것이 정상이다.

#### 2건의 차이는 **한 줄 배선 교체로 완전히 설명된다** (기계 증명)

`HEAD` 의 해당 함수에 아래 치환 하나만 적용하면 분리본과 **정확히 일치**한다.

```text
- monkeypatch.setattr(runner, "compose_runtime_evidence", lambda pk, **kw: fake)
+ patch_compose_runtime_evidence(monkeypatch, fake)
```

```text
test_runner_spike_mixed_signals_body_excludes_already_sent
  HEAD 에 치환 대상 출현: 1 · 교체 후 분리본과 동일: True
test_runner_reeval_exception_forces_failed_no_send
  HEAD 에 치환 대상 출현: 1 · 교체 후 분리본과 동일: True
두 건의 차이가 배선 교체로 완전히 설명되는가 = True
나머지 64개 **함수** 전부 동일: True
```

재현 명령은 §3.1-R 에 있다.

#### 이 변경이 발생한 단위 — 이번 분리 단위가 아니다

이 2건은 **선행 Cleanup `POC3-OPS-02B-2-KS10-RUNNER-EVIDENCE-EXTRACTION`** 에서
발생했다. 러너 §4 를 `runner_evidence.assemble_legacy_evidence()` 로 옮기면서
`compose_runtime_evidence` import 가 helper 안으로 이동했고, 러너 모듈 속성을
`monkeypatch` 하던 두 테스트가 `AttributeError` 로 깨져 **원천 모듈을 갈아끼우는
helper 호출로 바꿨다.** 설계자는 그 단위를
`RUNNER_EVIDENCE_EXTRACTION = PASS` · `TEST_ISOLATION_FIXES = ACCEPTED_PENDING_VERIFIER`
로 수용했다.

#### 주장의 범위를 정확히 제한한다 (설계자 §5)

두 문장을 구분한다.

| 문장 | 성립 |
|---|---|
| "이번 분리에서 테스트 본문을 바꾸지 않았다" | **독립 증명 불가** — 분리 직전 기준선이 보존되지 않았다. **이 문장은 사용하지 않는다.** |
| "`HEAD` 대비 확인되는 본문 차이는 승인된 선행 Cleanup 의 정확한 2건뿐이며, 그 밖의 차이는 0건이다" | **재현 가능하게 증명됨** (§3.1-R) |

완료 근거로 쓰는 것은 **후자뿐**이다.

```text
SPLIT_PRE_BASELINE_PRESERVED                  = false
SPLIT_ZERO_BODY_CHANGE_INDEPENDENTLY_PROVEN   = false
NO_ADDITIONAL_BODY_DIFF_BEYOND_APPROVED_DELTA = true
RISK_ACCEPTANCE = 정확히 식별된 선행 변경 2건에 한정
```

기준선은 **재현 가능한 `HEAD 74ec6dee` 로 유지한다.** 재현 불가능한 "분리 직전
working tree" 를 새 기준선으로 확정하자는 앞선 제안은 **설계자가 기각했고
삭제한다.**

PLAN §3.4 와의 관계는 설계자가 확정했다 —
`PLAN_3_4_DEVIATION = APPROVED_FOR_EXACT_2_PRIOR_DELTAS`. 상세는 §12-0.

### 3.1-R 재현 명령 (검증자용)

```bash
git show HEAD:tests/test_low_frequency_push_operation.py > /tmp/head_orig.py
python3 - <<'EOF'
import ast, io, pathlib
def top(p):
    t = ast.parse(io.open(p, encoding="utf-8").read())
    return {n.name: ast.unparse(n) for n in t.body if isinstance(n, ast.FunctionDef)}
head = top("/tmp/head_orig.py")
split = {}
for f in sorted(pathlib.Path("tests/low_frequency_push").glob("*.py")):
    split.update(top(f))
OLD = "monkeypatch.setattr(runner, 'compose_runtime_evidence', lambda pk, **kw: fake)"
NEW = "patch_compose_runtime_evidence(monkeypatch, fake)"
diff = [k for k in head if head[k] != split[k]]
print("불일치:", diff)
print("배선 교체로 설명됨:",
      all(head[k].replace(OLD, NEW) == split[k] for k in diff))
print("나머지 동일:",
      all(head[k] == split[k] for k in head if k not in diff))
EOF
```

`ast.unparse` 정규화 기준이므로 결과는 **정규화된 AST 구조 동등**이다 — 바이트
동등이라고 표현하지 않는다(공백·줄바꿈·따옴표 형태는 정규화에 흡수된다).

허용한 변경은 **파일 배치와 import 경로**다. assertion·docstring·fixture 본문은
고치지 않았다 — 위 2건의 배선 한 줄은 선행 단위 소관이다.

### 3.2 수집 동등성 (설계자 §3 계약)

`wc -l` 에 의존하지 않았다. 분리 **전** 원본에서 수집되는 사례의 **이름과
parametrize 식별자**를 기준선으로 저장하고, 분리 **후** 패키지의 수집 결과를
경로를 제외해 정렬 대조했다.

```bash
pytest <대상> --collect-only -q | grep '::' | sed 's/^.*:://' | sort
```

| 항목 | 값 |
|---|---|
| before / after 사례 수 | 52 / 52 |
| `diff` 결과 | **차이 0건** |
| 중복 수집 (`uniq -d`) | **0건** |
| `pytest.mark.skip` · `xfail` · `pytest.skip()` | 원본 0건 → 분해본 **0건** |
| `skip`/`xfail` 문자열 출현 | 13 → 13 (전부 `status="skipped"` 등 assertion 문자열) |

### 3.3 원본 삭제 조건 (설계자 §2) 충족 근거

| 조건 | 결과 |
|---|---|
| 1. 다른 코드·테스트의 참조 없음 | import 구문 **0건** (정규식 `^\s*(from\|import)\s.*test_low_frequency_push_operation`) |
| 2. 외부 참조가 있으면 fixture 경로만 변경 | 해당 없음 (참조 0건) |
| 3. 제품 코드 참조 | `app/`·`scripts/` 내 **0건** → 중단 사유 미발생 |
| 4. 신규 패키지 focused test | **52 passed** |
| 5. 분리 전후 수집 사례 수 동일 | 52 = 52 |
| 6. 중복 수집 0건 | 0건 |

잔존 문자열 11건은 신규 파일의 **출처 표기 docstring**(`원본 tests/test_low_frequency_push_operation.py …`)이며 import 가 아니다.

### 3.4 as-of 섹션 9건 재배치 — PLAN §3.3 그대로 수행

PLAN 에 제출한 1:1 매핑표대로 옮겼다. 변경 없음.

---

## 4. 프론트 분리 — 계약 무변경 증명

### 4.1 디렉터리명 — 설계자 최종 승인 완료

설계자는 `today_investment_check/` 를 승인했다. 그러나 착수 직전
**`frontend/app/components/today/` 가 이미 존재**하고 이 화면 전용 부품
(`KospiChart.tsx` 101줄 · `todayHelpers.ts` 86줄)을 담고 있음을 발견했다.
원본 L45·L51 이 `./today/KospiChart`·`./today/todayHelpers` 를 import 한다.

PLAN V1 에 이 사실을 적지 않은 것은 **개발자 누락**이다. 설계자는 그 누락된
정보 위에서 명칭을 승인했다.

승인 명칭대로 `today_investment_check/` 를 새로 만들면 **같은 화면의 부품이 두
디렉터리로 쪼개진다.** 자체 해석하지 않고 사용자에게 선택지를 제시해 결정을
받았다.

```text
사용자 결정 (2026-09-13) = 기존 `today/` 에 합친다
```

| 항목 | 값 |
|---|---|
| 승인 명칭 | `frontend/app/components/today_investment_check/` |
| 실제 사용 | `frontend/app/components/today/` |
| 사유 | 같은 화면 부품이 이미 `today/` 에 있음 (실측) |
| 기존 2개 파일 | 수정 0건 (`git diff` 0건) |

```text
DIRECTORY               = frontend/app/components/today/
DECISION                = ADOPT
RENAME_OR_MOVE_REQUIRED = NO
```

설계자가 최종 승인했다 — 같은 화면의 부품이 이미 `today/` 에 있으므로 기존
디렉터리에 합치는 것이 구조적으로 맞다는 판정이다. 기존 두 파일은 수정하지
않는다. 이 항목은 **종결**이다.

### 4.2 외부 계약 무변경 (설계자 §4 10항목)

| 항목 | 결과 | 근거 |
|---|---|---|
| `MainPanel.tsx` import | 무변경 | 파일 sha256 동일 |
| default export · 외부 경로 | 유지 | `export default function TodayInvestmentCheckView` 가 같은 경로에 그대로 |
| JSX 문구·표시 순서 | 무변경 | 블록을 그대로 이동 · 컨테이너의 렌더 순서 원문 유지 |
| className · DOM 의미 | 무변경 | 편집 0건 |
| 버튼·핸들러 | 무변경 | 편집 0건 |
| API 호출 10개의 조건·횟수·순서 | 무변경 | `useSharedQuery` 4건·`refreshMarket`·`reloadAsync` 3건은 컨테이너에, `fetchOciStartupStatus` 는 `OciStatusOneLine` 에 **같은 컴포넌트 안에서** 이동 |
| `useState`·`useEffect` 동작·의존성 | 무변경 | hook 을 컴포넌트 경계를 가로질러 옮기지 않았다 |
| 로딩·성공·실패 상태 전이 | 무변경 | `useLightRefreshState` 를 통째로 이동 |
| 기존 테스트 fixture·mock·assertion | 무변경 | 테스트 파일 sha256 동일 |

추가한 것은 **파일 머리말 주석 · import 줄 · `export` 키워드**뿐이다.

### 4.3 내부 함수의 export 전환

옮긴 뒤 컨테이너가 쓰려면 export 가 필요하다. 기존 `today/KospiChart.tsx` 가
`export default function` 을 쓰므로 같은 관행을 따랐다.

| 대상 | 형태 |
|---|---|
| 컴포넌트 6종 | `export default function` |
| `MaintenanceItem` · `collectMaintenance` | named export (`maintenanceQueue.ts`) |
| `useLightRefreshState` | named export |
| `BlockedRow` · `MaintInfo` · `DevList` · 상수 4종 | **export 하지 않음** (각 파일 내부 유지) |

### 4.4 검증 결과

| 단계 | 결과 |
|---|---|
| `npx tsc --noEmit` | exit 0 |
| `npm run lint` (eslint) | exit 0 |
| `npx vitest run` | 17 files / **191 tests** passed |
| `TodayInvestmentCheckView.test.tsx` | **35 tests passed** · 파일 무수정 |

---

## 5. KS-10 전수 측정 (설계자 §5 계약 — untracked 포함)

`git ls-files` 만으로는 commit 전 신규 분리 파일이 빠진다. tracked 424 +
untracked 30 = **454개**를 측정했다. 삭제된 파일은 제외했다.

```text
TRIGGER = 0
NEAR = 6
NEW_SPLIT_FILES_NEAR_OR_TRIGGER = 0
```

### 5.1 NEAR 6건 — 전부 변동 없음 (설계자 지정 감시 순서)

| # | 줄 | 파일 | 임계까지 |
|---:|---:|---|---:|
| 1 | 648 | `scripts/run_three_push_runtime_oci.py` | **2** (`TRIGGER_STARTS_AT = 651`) |
| 2 | 632 | `app/api.py` | 18 |
| 3 | 626 | `app/ml_score_validity_report.py` | 24 |
| 4 | 616 | `app/holdings_market_evidence.py` | 34 |
| 5 | 855 | `frontend/app/components/JudgmentWorkbenchView.tsx` | 45 |
| 6 | 602 | `app/draft.py` | 48 |

### 5.2 신규 분리 파일 — NEAR 초과 0건

| 디렉터리 | 최대 | NEAR 기준 | 초과 |
|---|---:|---:|---:|
| `tests/low_frequency_push/` | 420 (`test_runner_fail_closed.py`) | 1450 | 0건 |
| `frontend/app/components/today/` | 168 (`maintenanceQueue.ts`) | 850 | 0건 |

---

## 6. 라이브 경계 — 불변 확인과 역검증 (설계자 §6 계약)

### 6.1 실경로 해시 대조 (wildcard 미사용 · 경로 명시)

| 경로 | before | after |
|---|---|---|
| `state/three_push/market_briefing_meta_consistency_latest.json` | `82a10517…fe4f2` | 동일 |
| `state/three_push/market_briefing_state_latest.json` | `8fcde0e4…9e46d` | 동일 |
| `state/market/market_data.sqlite` | `08cbf4e4…0adfa` | 동일 |
| `state/market/market_data.sqlite-wal` | **ABSENT** | ABSENT |
| `state/market/market_data.sqlite-shm` | **ABSENT** | ABSENT |

백엔드 전체 회귀 전후로도 따로 대조해 동일함을 확인했다.

### 6.2 역검증 — canary 방식 (실경로 노출 0건)

PLAN §7.2 의 "상태 격리를 해제하고 러너 테스트 실행" 은 **실행하지 않았다**
(설계자 §6 지시). 대신 fixture 를 직접 호출해 임시 디렉터리 경계로만 확인했다.

```text
KRX 차단 OK: 테스트가 라이브 KRX Open API 를 호출했다. `fetcher=` 로 stub 을 넘겨라.
state 격리 OK: _mb.STATE_DIR = /var/folders/1y/.../tmpxau0aph_/three_push
실경로와 다름 = True
```

| 요구 | 결과 |
|---|---|
| 실제 `state/` 를 쓰기 대상으로 노출 | **0건** (tmp 디렉터리만) |
| 실제 KRX API 호출 | **0건** (stub 인자로 차단 확인) |
| 실제 Telegram 발송 경계 호출 | **0건** |
| 가드 무력화 시 임시 canary 검사에서 실패 | 확인 (`AssertionError` 발생) |
| 가드 활성 시 임시 경로만 사용 | 확인 (`_mb.STATE_DIR` ≠ 실경로) |
| 역검증 전후 실제 파일·DB 동일 | 확인 (§6.1) |

### 6.3 과거 사건 기록 — `LOCAL_ONLY_INCIDENT` 유지

```text
INCIDENT_CLASS     = LOCAL_ONLY_INCIDENT
RESTORE_PROVEN     = false
DELETE_OR_ROLLBACK = NOT_PERFORMED
```

두 상태 파일은 untracked 이고 `git log --all` 출력이 0건이다. 덮어쓰기 **전**
바이트 해시를 남기지 않아 원본 동일성을 증명할 수 없다. **"삭제·복원 완료"
라고 쓰지 않는다.** 상세는
`docs/handoff/POC3/OPS-02B-2_IMPLEMENTATION_CHECKPOINT.md` 부록 A-3-1.

---

## 7. `BUILD = PASS`

최초 구현 보고 시점에는 개발 서버가 포트 3000 에서 실행 중이어서 build 를
`DEFERRED_BY_ACTIVE_DEV_SERVER` 로 두었다. dev 가동 중 `next build` 는 `.next`
캐시가 겹쳐 dev 500 오류를 만들기 때문이다(사용자 확정 규칙). 그 시점에
**개발 서버를 임의 종료하지 않았다.**

이후 설계자 `BUILD_AUTHORIZATION = GRANTED` 와 사용자 승인(개발 서버 일시 종료 →
build → 재기동)을 받아 수행했고 **exit 0 으로 통과**했다. 상세·출력 원문·소스
무변경 증거는 **부록 A** 에 있다.

build 는 `BUILD = PASS` 로 종결됐다. 이후 검증자 r3 `VERIFIED` 와 사용자 실화면
확인을 거쳐 **`CLEANUP_STATUS = CLOSED`** 가 됐다(§0 · 부록 B). 종료를 개발자가
선언한 것이 아니라 **검증자 PASS + 사용자 확인**으로 성립했다.

---

## 8. 신규 추가된 의존성

없음.

---

## 9. 지시문 외 변경

1. **프론트 분리 디렉터리명** — 승인 명칭 `today_investment_check/` 대신 기존
   `today/` 를 사용했다. 자체 판단이 아니라 **사용자 결정**이었고, 이후 설계자가
   **최종 승인**했다 (`DIRECTORY_DECISION = ADOPT_EXISTING_TODAY` ·
   `RENAME_OR_MOVE_REQUIRED = NO`). **종결 항목이며 미결·확인 대기가 아니다.**
   §4.1 참조.
2. 원본 머리말의 사용자 확정 계약 6줄을 `tests/low_frequency_push/__init__.py`
   docstring 으로 **보존**했다. 파일이 나뉘면서 계약 문구가 사라지는 것을 막기
   위한 것이고 내용은 원문 그대로다.

---

## 10. 알려진 한계 / 미완성

1. 없음 — 검증자 r3 `VERIFIED` · 사용자 실화면 확인 완료로 이 Cleanup 은 `CLOSED` 다.
2. NEAR 6건 미처리. 러너는 648줄이고 **650줄까지 허용**되며 **651줄부터** TRIGGER
   다(남은 여유 2줄). 설계자 정정 — "한 줄만 늘어도 즉시 trigger" 는 틀린 표현이다.
   다만 이번 Cleanup 의 운영 정책은 `FREEZE_AT_648` 이므로 부모 Step 복귀 시
   러너 증가분은 설계자 판단을 받는다.
3. 사용자 실화면 확인 미수행 — 설계자 §8 순서에 따라 검증자·build 이후다.
4. `LOCAL_ONLY_INCIDENT` 2건의 원본 동일성은 앞으로도 증명 불가다.

---

## 11. 다음 검증자에게 알릴 점

0. **이번 라운드(r3)에서 바꾼 것은 문서 상태 표기 5곳뿐이다.** 코드·테스트·build
   재실행 0건이며 소스 454개 sha256 이 build 직후와 동일하다. r2 가 지적한 §1
   표의 `PARTIAL · 설계자 판단 대기` 를 비롯해, 같은 유형의 stale 을 **grep 으로
   전수 검색해 일괄 정정**했다 — §1 PLAN §3.4 행 · §1 프론트 행 · §7 의
   `IMPLEMENTED_BUILD_PASS` 단정 · §9-1 의 "사용자 확인 필요" 분류 · §12 제목.
   한 줄만 고치지 않은 이유는 같은 모순이 5곳에 있었기 때문이다.

1. **분리가 "의미 보존" 인지** — §3.1 을 **r1 REJECTED 반영해 전면 교체했다.**
   기준선은 `HEAD 74ec6dee`(1545줄 · `398a2de9…`)이고 결과는 **65건 동일 / 2건
   불일치**다. 2건은 `HEAD` 함수에 배선 한 줄만 치환하면 분리본과 정확히 일치함을
   기계 증명했다. 재현 명령은 §3.1-R 에 있다. **이전의 "불일치 0건" 주장은
   삭제했다** — 근거로 쓴 1548줄 기준선이 재현 불가였다.
2. **프론트 디렉터리명** — 설계자 최종 승인 완료(§4.1). 재확인 대상이 아니다.
3. **`today/` 기존 2개 파일** — `git diff` 0건이지만 같은 디렉터리에 신규 8개가
   들어갔으므로 함께 확인할 가치가 있다.
4. **삭제된 원본** — git 이력으로 복구 가능하다. 삭제 전 sha256 을 §2.4 에 적었다.
5. **컨테이너 141줄** — 원본 L791–872 를 그대로 옮겼다. L873–907(경량 갱신 훅)은
   `useLightRefreshState.ts` 로 갔고, 훅 앞의 설명 주석 2줄도 함께 옮겼다.
6. **`BUILD`** — 사용자 승인으로 수행해 PASS 다(부록 A). build 전후 소스 454개
   해시가 동일하므로 build 가 코드를 바꾸지 않았다.

---

## 12. 설계자 확정 결정 / 사용자가 알아야 할 항목

설계자 판단 대기 항목은 **0건**이다. §12-0 은 확정된 결정의 기록이다.

### 12-0. 설계자 결정 — 확정됨 (r1 REJECTED 해소)

```text
DESIGNER_DECISION                = APPROVE_EXACT_PRIOR_CLEANUP_DELTA
OPTION_A                         = PARTIAL_ACCEPT_WITH_REFRAMING
OPTION_B                         = REJECT
PLAN_3_4_DEVIATION               = APPROVED_FOR_EXACT_2_PRIOR_DELTAS
CODE_CHANGE_REQUIRED             = false
DOCUMENT_CORRECTION_REQUIRED     = true   → 완료
REVERIFICATION_REQUIRED          = true   → 동일 검증자에게 재제출
```

설계자가 확정했다. **개발자 판단 대기 항목이 아니다.**

1. **코드 수정 없음.** 이 라운드에서 `.py`/`.ts`/`.tsx` 변경 0건이다.
2. **기준선은 `HEAD 74ec6dee` 로 유지한다.** 재현 불가능한 "분리 직전 working
   tree" 를 새 기준선으로 확정하자는 개발자 제안은 **기각됐다.**
3. `HEAD` 대비 AST 결과는 §0·§3.1 의 키로 확정한다 — `AST_IDENTICAL = 65`,
   `APPROVED_PRIOR_CLEANUP_DELTA = 2`, `UNEXPLAINED_AST_DIFFERENCE = 0`.
4. 두 차이는 아래 두 함수의 **정확히 한 줄 배선 변경**으로 한정한다.
   - `test_runner_spike_mixed_signals_body_excludes_already_sent`
   - `test_runner_reeval_exception_forces_failed_no_send`

   선행 `RUNNER-EVIDENCE-EXTRACTION` Cleanup 의 구조 변경에 따라 patch 대상을
   **실제 lookup 위치로 이동**한 이월 변경으로 **승인**한다.
5. **"이번 분리 단위가 본문을 0건 변경했음을 증명했다" 는 문장은 사용하지
   않는다.** §3.1 의 범위 제한 표와 4개 키로 대체했다.
6. (b) `HEAD` 본문 복원은 **기각**이다. 오래된 patch 경로를 되살려 현재 구조에서
   테스트를 깨뜨린다(러너 §4 추출로 `AttributeError`). 되돌리려면 선행 단위까지
   뒤집어 `runner 656줄`·KS-10 재TRIGGER 가 된다.
7. 코드·테스트·build **재실행은 요구되지 않았다.** 문서만 정정했다. 다만 문서
   정정 뒤 focused test 1회를 확인용으로 돌렸다 — **52 passed**.
8. **재검증 PASS 전까지 Cleanup 을 종료하지 않고, 부모 `OPS-02B-2` 도 재개하지
   않는다.** → **충족됨.** r3 `VERIFIED` + 사용자 실화면 확인으로 `CLOSED` 가
   됐고, 부모 Step 재개는 그 다음이다(부록 B).

### 12-1. 그 밖에 사용자가 알아야 할 항목

1. **프론트 분리 디렉터리명** (§4.1) — **종결**. 설계자가 `today/` 를 최종
   승인했다(`RENAME_OR_MOVE_REQUIRED = NO`).
2. **원본 테스트 파일 삭제 완료** — 설계자가 승인한 작업이다. git 이력에 남아
   복구 가능하다. 삭제 자체를 사용자도 알고 있어야 한다.
3. **`npm run build`** — 사용자 승인으로 개발 서버 일시 종료 → build → 재기동을
   수행했다. 결과는 부록 A 참조.

---

## 부록 A. Build 결과 (사용자 승인 범위 내 로컬 검증)

설계자 `BUILD_AUTHORIZATION = GRANTED` · 사용자 승인(개발 서버 일시 종료 → build
→ 재기동)에 따라 수행했다.

```text
BUILD                       = PASS
BUILD_EXIT_CODE             = 0
DEV_SERVER_RESTARTED        = YES
PORT_3000                   = LISTEN
SOURCE_CHANGED_DURING_BUILD = 0
COMMIT_PUSH_OCI_DEPLOY_SEND = 0
AUTOSEND                    = false
```

### A-1. 수행 순서 (설계자 §4 그대로)

| # | 작업 | 결과 |
|---:|---|---|
| 1 | 개발 서버 일시 종료 | `npm run dev` PID 17693 에 SIGTERM · 포트 3000 해제 · `next` 프로세스 0건 |
| 2 | `npm run build` | **exit 0** |
| 3 | 개발 서버 재기동 | `npm run dev` 재실행 (동일 명령) · PID 62593 / next-server 62594 |
| 4 | 포트·화면 확인 | 포트 3000 **LISTEN** · `GET /` **HTTP 200** (22,017 bytes, 0.179s) · 본문에 「오늘의 투자 점검」 포함 |

### A-2. build 출력 원문 (발췌)

```text
> next build

   ▲ Next.js 15.5.15
   - Environments: .env.local

   Creating an optimized production build ...
 ✓ Compiled successfully in 2.7s
   Linting and checking validity of types ...
   Collecting page data ...
 ✓ Generating static pages (4/4)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                 Size  First Load JS
┌ ○ /                                    71.7 kB         174 kB
└ ○ /_not-found                            995 B         103 kB
+ First Load JS shared by all             102 kB
```

분리한 8개 파일이 production build 의 **타입 검사·정적 생성**을 모두 통과했다.

### A-3. build 가 소스를 바꾸지 않았다 (실측)

build **전** 소스 파일 454개(`tracked` + `untracked` `.py`/`.ts`/`.tsx`)의 sha256
목록을 저장하고, 재기동 **후** 다시 측정해 대조했다.

```text
diff src_before.txt src_after.txt → 차이 0건
SOURCE_CHANGED_DURING_BUILD = 0
```

build 전에 소스를 수정하지 않았고, build 자체도 소스를 바꾸지 않았다.

### A-4. 라이브 자원 불변 (build 전후)

| 경로 | 결과 |
|---|---|
| `state/three_push/market_briefing_meta_consistency_latest.json` | 불변 |
| `state/three_push/market_briefing_state_latest.json` | 불변 |
| `state/market/market_data.sqlite` | 불변 |
| `state/market/market_data.sqlite-wal` · `-shm` | 부재 (0개) |

### A-5. 재기동 시 `.next` 정리

dev 재기동 전에 `frontend/.next` 를 제거했다. production build 산출물이 남은
상태로 dev 를 올리면 캐시가 겹쳐 dev 가 500 을 내는 기존 사고 패턴을 막기
위한 것이다. `.next` 는 gitignore 대상 **빌드 산출물**이며 소스가 아니다
(§A-3 해시 대조가 소스 무변경을 증명한다). 재기동 로그:

```text
 ✓ Starting...
 ✓ Ready in 1093ms
 ✓ Compiled / in 1996ms (730 modules)
 GET / 200 in 2267ms
```

### A-6. 승인 범위를 넘지 않았다

| 항목 | 실적 |
|---|---|
| commit · push | 0건 |
| OCI write · 배포 | 0건 |
| autosend 활성화 | 0건 (`false` 유지) |
| Telegram 실발송 | 0건 |
| 외부 API 호출 | 0건 |
| 검증자 역할 대행 | 없음 |
| 사용자 실화면 확인 요청 | 하지 않았다 (설계자 §8 순서 준수) |
| 부모 Step `OPS-02B-2` 재개 | 없음 (`PAUSED` 유지) |
| 목업 작성 | 0건 |

---

## 부록 B. 종결 (2026-09-13)

```text
VERIFIER_r1 = REJECTED  → AST 기준선·삭제 원본·staged 수 정정
VERIFIER_r2 = REJECTED  → 결과서 활성 상태 모순 5곳 일괄 정정
VERIFIER_r3 = VERIFIED  → A-1·A-2·A-3·A-4 · B-1~B-6 전 항목 통과
USER_SCREEN_CONFIRMED = YES
CLEANUP_STATUS = CLOSED
PARENT_STEP = OPS-02B-2 재개 가능
```

### B-1. 사용자 실화면 확인 (설계자 §8 5단계)

좌측 메뉴 **「오늘의 투자 점검」** 을 사용자가 직접 확인해 **이상 없음**을 회신했다
(2026-09-13). 907줄 → 9개 파일 분리 후 화면·문구·동작이 이전과 같다.

개발자 측 보조 확인(자동 테스트로 잡히지 않는 레이아웃은 사용자 확인이 정본):

| 항목 | 결과 |
|---|---|
| 한글 UI 문구 보존 | `HEAD` 322개 전부 존재 · **누락 0건** (정규식 전수 대조) |
| 구역 렌더 순서 | `HEAD` 와 동일 — OCI 한 줄 → 코스피 대표 → 코스피 상세 → (판단 큐 ∥ 자료 최신화) → 개발 중 기능 |
| 초기 HTML 실렌더 | `GET /` HTTP 200 · 6개 구역 문구 전부 확인 |

### B-2. 3라운드에서 고친 것 / 고치지 않은 것

| 라운드 | 코드 | 문서 |
|---|---|---|
| r1 → r2 | **0건** | §3.1 전면 교체 · §2.4 · staged 수 · §12-0 신설 |
| r2 → r3 | **0건** | 활성 상태 모순 5곳 + §10·§11 |

**구현 코드는 r1 이후 한 줄도 바뀌지 않았다.** 소스 454개 sha256 이 build 직후와
동일함을 매 라운드 대조했다. 반려 사유는 전부 **증빙 방식과 보고 정확성**이었다.

### B-3. 남는 것 (부모 Step 으로 이월)

| 항목 | 내용 |
|---|---|
| NEAR 6건 | 별도 Cleanup 단위. 러너는 `FREEZE_AT_648` · `TRIGGER_STARTS_AT = 651` |
| `LOCAL_ONLY_INCIDENT` 2건 | 원본 동일성 증명 불가. 삭제·되돌림 금지 유지 |
| 부모 `OPS-02B-2` | flow-through 테스트 · 보호 로직 역검증 · 전체 회귀 · 목업 7종 · 구현 결과 보고 |
