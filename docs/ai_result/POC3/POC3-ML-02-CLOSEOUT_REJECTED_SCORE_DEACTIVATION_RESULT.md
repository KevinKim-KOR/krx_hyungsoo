# POC3-ML-02 REJECT Closeout — 개발 결과서

- **작성**: 개발자 (VSCode Claude)
- **수신**: 검증자 (Codex)
- **작성일**: 2026-08-29
- **상태**: **`CLOSED`** — 검증자 **`VERIFIED`** + 사용자 실화면 확인 **완료** (2026-08-31)
- **개정**
  | 라운드 | 내용 |
  |---|---|
  | r1 (2026-08-29) | 구현 + 실화면 확인 → 검증자 **`REJECTED`** (C-3/C-4·C-7 미완성) |
  | r2 (2026-08-29) | C-3/C-4 3변형 · C-7 실동작 보강 + 보고 4건 정정 + `act` 해소 → 검증자 **`REJECTED`** (`보유 노출` 1건) |
  | **r3** (2026-08-31) | **`보유 노출` 정렬 실동작 고정** → 검증자 **`VERIFIED`**. **같은 파일 개정**(V2 미생성) |
- **설계서**: `docs/ai_design/POC3/POC3-ML-02-CLOSEOUT_REJECTED_SCORE_DEACTIVATION_DESIGN_V1.md`
- **PLAN**: `docs/ai_plan/POC3/POC3-ML-02-CLOSEOUT_REJECTED_SCORE_DEACTIVATION_PLAN_V1.md`
  (설계자 `CONDITIONAL_PASS` → V1.1 반영 → PASS)
- **선행 판정**: `relative_upside_v0` **`REJECT` 확정** ·
  `ui_action = DEACTIVATE_AND_HIDE` · 커밋 `ad42bb88`
  (근거 수치는 `POC3-ML-02_..._RESULT.md` 참조 — **본 문서에 복제하지 않는다**)

> **본 Step 은 UI closeout 이다.** 모델 재평가·재학습·삭제가 아니다.

---

## 1. 처리한 요구사항

| 확정 계약 | 상태 |
|---|---|
| API 필드·스키마·백엔드 무변경 | **DONE** — `git status -- app/ scripts/ state/ .env` **0건** |
| 후보 표·판단 워크벤치에서 점수·사유 미표시 | **DONE** |
| 참고점수 재정렬 완전 제거 | **DONE** (5곳) |
| 정렬 드롭다운에서 `참고점수` 선택지 제거 | **DONE** — 비활성 선택지로 남기지 않음 |
| 비활성 선택지·`0`·`사용 불가`·경고 배지로 대체 금지 | **DONE** |
| API 후보 순서 보존 | **DONE** |
| 점수의 존재·부재·크기가 순서에 영향 없음 | **DONE** (C-3 테스트) |
| ML 화면 수동 실행 유지 + `relative_upside_v0`·`REJECT`·연구용 표기 | **DONE** |
| 자동 실행·스케줄러·후보 화면 연결 추가 없음 | **DONE** — 기존 이동 링크도 제거 |
| 다른 운영 화면에 상태 문구·점수 미노출 | **DONE** |
| M-1 5곳 적용 / M-2 링크 제거 / M-3 1개월 수익률 / M-4 양쪽 검증 | **DONE** |
| CompareCards 주석 정정 | **DONE** |

---

## 2. 변경된 파일 목록

| 파일 | 구분 | 내용 |
|---|---|---|
| `frontend/app/components/CandidateTable.tsx` | 수정 | 점수 열·근거 열·정렬 토글·고지 배너·prop 2개 제거 |
| `frontend/app/components/MarketDiscoveryView.tsx` | 수정 | prop 전달 제거 |
| `frontend/app/components/CandidateCards.tsx` | 수정 | 점수 배지 → **1개월 수익률** · 점수 근거 제거 |
| `frontend/app/components/JudgmentWorkbenchView.tsx` | 수정 | 정렬 키 `score`·버튼·행 표시 자리·선택 상세 제거 |
| `frontend/app/components/HoldingsCompareView.tsx` | 수정 | 타입에서 `"score"` 삭제·정렬 키·버튼 제거 |
| `frontend/app/components/holdings_compare/SelectedDetail.tsx` | 수정 | 점수·사유 제거 + 미사용 import 정리 |
| `frontend/app/components/holdings_compare/CompareCards.tsx` | 수정 | 주석 1줄 정정 (동작 변화 0) |
| `frontend/app/components/RelativeUpsideRunCard.tsx` | 수정 | `relative_upside_v0`·`REJECT`·연구용 표기 추가 |
| `frontend/app/components/MLView.tsx` | 수정 | 후보 화면 이동 링크 제거 · `onNavigate` prop 삭제 |
| `frontend/app/components/MainPanel.tsx` | 수정 | 위 prop 전달 제거 |
| `frontend/app/components/workbench/helpers.ts` | 수정 | 미사용이 된 `fmtScore` 제거 |
| `frontend/app/components/CandidateCards.test.tsx` | 수정 | 계약 반영 |
| `frontend/app/components/JudgmentWorkbenchView.test.tsx` | 수정 | Closeout 계약 **4건** 추가 — C-1·C-2·**C-3/C-4 3변형**·**C-7 5종 실동작**. 픽스처의 점수는 **유지**(값이 와도 안 나오는 것을 증명) |
| `frontend/app/components/RejectedScoreCloseout.test.tsx` | **신규** | 계약 test **13건** (421줄) |
| `docs/ai_design/...CLOSEOUT..._DESIGN_V1.md` | 신규 | 설계자 원문 |
| `docs/ai_plan/...CLOSEOUT..._PLAN_V1.md` | 신규 | PLAN V1.1 |
| `docs/ai_result/...CLOSEOUT..._RESULT.md` | 신규 | 본 문서 |
| `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md` | 수정 | 화면 계약 갱신 |

**백엔드 파일 변경 0건.** `app/` · `scripts/` · `state/` · `.env` · cron · OCI 무변경.

---

## 3. 신규 추가된 의존성

**없음.**

---

## 4. 지시문 외 변경

**3건. 전부 확정 계약의 직접 귀결이다.**

1. **`MainPanel.tsx` 수정** — `MLView` 의 `onNavigate` prop 을 없앴으므로 호출부도
   함께 정리했다. 이 prop 은 제거 대상 링크에만 쓰였다.
2. **`workbench/helpers.ts` 의 `fmtScore` 제거** — 참고점수 표시가 사라져 유일한
   호출자가 없어졌다. 남기면 dead code + eslint 경고.
3. **`SelectedDetail.tsx` 의 `STATE_NO_DATA` import 제거** — 점수 줄 삭제로
   미사용이 됐다(eslint 경고 해소).

---

## 5. 알려진 한계 / 미완성

- **후보 카드에 같은 값이 두 번 나온다.** 큰 숫자 자리(`+6.01% / 1개월`)와 지표 행의
  `1개월` 셀이 동일하다. 설계자가 M-3 에서 **1개월 수익률**을 확정했기에 임의로
  바꾸지 않았다. 지표 행에서 `1개월` 셀을 빼면 3칸 그리드(`wb-hm3`)가 2칸이 되어
  레이아웃 영향이 있다. **사용자 실화면 확인 완료** — 현 상태로 승인됨.
- API 응답에는 점수·사유가 계속 실려 온다(계약 보존). 화면이 소비하지 않을 뿐이다.
- `frontend/lib/api/market.ts` 의 타입 6개는 그대로다.

---

## 6. 다음 검증자에게 알릴 점

1. **핵심은 C-3 이다.** 표시만 지우고 정렬이 남으면 화면엔 안 보이는데 순서는
   여전히 REJECT 점수가 정한다. **세 화면 각각** (a)원본 (b)점수 역순 (c)점수 전부
   `null` 3변형의 ticker 순서가 같은지 본다 — 후보 표·후보 카드는
   `RejectedScoreCloseout.test.tsx`, 판단 워크벤치는 `JudgmentWorkbenchView.test.tsx`
   의 `C-3 / C-4 원본·점수 역순·점수 전부 null 세 변형...` 이 담당한다.
   **[r2 정정]** r1 은 워크벤치를 점수 역순 1회만 검사하면서 "세 화면 모두 3변형" 이라
   적었다. 과장이었고 r2 에서 실제로 3변형을 돌린다.
2. **"API 순서 강제" 는 최초 진입 기본 상태 한정이다.** 사용자가 `1M`·`3M` 등을
   직접 고른 뒤까지 강제하면 기존 기능이 깨진다.
   **[r2 정정]** r1 의 C-7 은 **버튼 존재만** 검사했다 — 정렬 함수가 무력화돼도
   통과했다. r2 는 워크벤치 **5종**(`순위`·`1M`·`3M`·`KODEX초과`·`고점대비`)과
   보유와비교 **3종**(`20일 초과`·`고점 대비`·`보유 노출`)이 **실제로 순서를 바꾸는지**
   확인한다. 각 정렬 키가 서로 다른 순서를 만들도록 3종목 픽스처를 설계했다.
   **[r3 정정]** r2 의 `보유 노출` 은 **맨 앞 종목을 보유**하게 해 기본 순서와 결과가
   같았다 — 분기를 지워도 통과했다. r3 는 **맨 뒤 종목(CCC)** 을 보유하게 바꿔
   결과가 기본 순서와 달라지고, 전체 순서를 단언한다(§7.2 역검증 2종으로 확인).
3. **테스트 픽스처에는 점수를 일부러 넣었다.** 값이 들어와도 화면에 안 나오는 것을
   증명해야 하기 때문이다. 픽스처의 `72.3` 을 근거로 "점수가 남아 있다" 고 보면 안 된다.
4. **grep 은 보조 검사다.** 허용 위치는 **4종**이다 — ① API 타입(`market.ts`)
   ② ML 연구 경로 3파일 ③ 테스트 픽스처 ④ **`CompareCards.tsx` 주석**(제거 이유
   기록 · 설계자 수용). §7.1 표가 정본이다.
   **[r2 정정]** r1 은 §6 에서 ①②③ 만 적어 §7.1 과 경계가 어긋났다.
5. **PLAN 과 달라진 것 1건** — 판단 워크벤치 행의 빈 자리를 처음엔 후보 카드처럼
   1개월 수익률로 채웠다가, 아래 facts 줄의 `1M` 과 중복돼 기존 테스트가 깨졌다.
   PLAN §2.3 이 원래 "열 자체 제거"였으므로 그대로 되돌렸다.
6. **역검증 중 무효한 시도 1건이 있었다** — `보유와 비교` 사보타주가 후보 정렬바가
   아니라 **보유 정렬바**에 들어가 탐지되지 않았다(보유 데이터가 없어 렌더 안 됨).
   후보 정렬바로 바로잡아 재검증했고 2건이 실패했다(§7).

---

## 7. 검수 실측

| 항목 | 결과 |
|---|---|
| 신규 계약 test `RejectedScoreCloseout.test.tsx` | **13 passed** |
| `JudgmentWorkbenchView.test.tsx` (Closeout 4건 포함) | **30 passed** |
| 프론트 전체 `npx vitest run` | **191 passed** (17 파일) |
| `npx tsc --noEmit` | **0건** |
| `npm run lint` | **0건** (경고 포함 0) |
| **백엔드 전체 `pytest tests/`** | **1,268 passed** (C-6 — 운영 무변경 확인) |
| `git status -- app/ scripts/ state/ .env` | **0건** |
| grep 가드 | 허용 위치 외 **0건** |
| `act(...)` 경고 | **0건** (r2 — ML 형제 카드 4개 stub) |
| 사용자 실화면 확인 | **완료** (시장 발굴 표·카드 / 판단 워크벤치 / 보유와 비교 / ML 연구 화면) |

### 7.1 grep 가드 결과 (보조 검사)

`relative_upside_score` · `relative_upside_reasons` · `relativeUpside` 를
snake·camel 양쪽으로 훑은 결과 남은 파일은 아래뿐이다.

| 파일 | 허용 근거 |
|---|---|
| `frontend/lib/api/market.ts` | **API 타입 정의** — 계약 보존 |
| `frontend/lib/api/mlRelativeUpside.ts` | **ML 연구 경로** |
| `frontend/app/components/MLView.tsx` | **ML 연구 경로** |
| `frontend/app/components/RelativeUpsideRunCard.tsx` | **ML 연구 경로** |
| `frontend/app/components/holdings_compare/CompareCards.tsx` | **주석만** (제거 이유 기록) |
| `CandidateCards.test.tsx` · `JudgmentWorkbenchView.test.tsx` · `RejectedScoreCloseout.test.tsx` | **테스트 픽스처** — 점수가 와도 안 나오는 것을 증명하는 데 필요 |

### 7.2 역검증 (테스트 유의미성)

| 라운드 | 제거한 보호 | 결과 |
|---|---|---|
| r1 | 후보 표에 점수 정렬 복원 | C-3/C-4 **1건 실패** |
| r1 | `보유와 비교` **후보** 정렬바에 `참고점수` 복원 | C-1·C-2 **2건 실패** |
| r1 | (무효 시도) `보유와 비교` **보유** 정렬바에 삽입 | 탐지 실패 — 보유 데이터 없어 미렌더. 대상을 바로잡아 재검증 |
| **r2** | **워크벤치 `rows.sort` 무력화** | **2건 실패** (신규 C-7 + 기존 정렬 test) |
| **r2** | **보유와비교 후보 정렬 무력화** | **1건 실패** (신규 C-7) |
| **r3** | **`exposure` 분기만 제거**(`case "exposure": return null`) | **1건 실패** — `['AAA','BBB','CCC']` ≠ `['CCC','AAA','BBB']` |
| **r3** | **`exposureSortRank` 를 상수 `1` 로 대체**(순위 구분만 제거) | **1건 실패** — 같은 단언 |

전부 원복 후 프론트 **191 passed** 재확인.

---

## 7.3 [r2] 검증자 지적 대응

| 지적 | 대응 |
|---|---|
| **P1-1** C-7 이 선택지 존재만 검사 | 워크벤치 5종·보유와비교 3종이 **실제로 순서를 바꾸는지** 확인. 각 키가 서로 다른 순서를 내도록 3종목 픽스처 설계. 역검증으로 정렬 무력화 시 실패 확인 |
| **P1-2** 워크벤치 3변형 누락 | (a)원본 (b)점수 역순 (c)점수 전부 `null` 3변형을 렌더해 세 결과의 **직접 동등성** + API 순서 일치 확인 |
| **[r3] P1** `보유 노출` 정렬 무력화를 못 잡음 | r2 는 **AAA(맨 앞)** 를 보유하게 해 정렬 후에도 `order()[0] === "AAA"` 만 봤다 — 기본 순서와 결과가 같아 분기를 지워도 통과했다. r3 는 **CCC(맨 뒤)** 를 보유하게 바꿔 결과가 `["CCC","AAA","BBB"]` 로 **기본 순서와 달라지게** 하고 **전체 ticker 순서**를 단언한다. `not.toEqual(기본 순서)` 도 함께 건다 |
| A-2 §6 "세 화면 3변형" 과장 | §6-1 에 `[r2 정정]` 명시 후 실제 구현 |
| A-2 C-7 주장 과장 | §6-2 에 `[r2 정정]` 명시 후 실제 구현 |
| A-2 백엔드 1,268 누락 | §7 검수표에 추가 |
| A-2 grep 경계 불일치 | §6-4 를 §7.1 표(4종)와 일치시킴 |
| **B-6** `act(...)` 경고 | `MLView` 형제 카드 4개(`MLEvidenceRefreshCard`·`MLTimeseriesReadinessCard`·`MLFeatureSanityCard`·`MLBaselineV0Card`)를 stub 으로 대체. `RelativeUpsideRunCard` 는 mount fetch 가 없어 **실물 유지**. `보유와 비교` 는 `@/lib/api/holdings` mock + `waitFor` 로 로드 완료 후 단언. **경고 0건** |

---

## 8. 사용자 확인이 필요한 항목

1. **커밋·푸시** — 검증자 `VERIFIED` 후 사용자 지시로 수행했다.
2. 후보 카드의 `1개월` 중복 표시(§5). 실화면 확인에서 승인됐으나, 이후 정리를
   원하면 별건으로 처리한다.


---

## 9. Closeout 종료 상태

```text
step_status            = CLOSED
verification           = VERIFIED
user_screen_check      = DONE (시장 발굴 표·카드 / 판단 워크벤치 / 보유와 비교 / ML 연구 화면)
model_verdict          = REJECT (relative_upside_v0)
ui_action              = DEACTIVATE_AND_HIDE  → 적용 완료
api_contract           = UNCHANGED
oci_push_cron_impact   = NONE
```

`verification` 이력: r1 `REJECTED` → r2 `REJECTED` → r3 **`VERIFIED`**.
**세 라운드 반려 이력은 지우지 않는다** — 무엇이 덜 고정돼 있었는지가 이 Step 의
실질이다(정렬 계약은 "버튼이 있다" 가 아니라 "순서가 실제로 바뀐다" 로만 고정된다).

**남은 관찰 1건**(후보 카드의 `1개월` 중복 표시)은 §5 에 그대로 둔다 — 실화면
확인에서 승인됐고, 정리하려면 별건 Step 이 필요하다.
