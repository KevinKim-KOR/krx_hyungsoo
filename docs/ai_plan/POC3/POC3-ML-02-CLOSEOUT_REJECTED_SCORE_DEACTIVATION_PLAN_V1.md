# POC3-ML-02 REJECT Closeout — 개발 PLAN V1

- **작성**: 개발자 (VSCode Claude)
- **수신**: 설계자 · 레드팀
- **작성일**: 2026-08-29
- **성격**: 개발 PLAN (모호점 포함). **구현 전 회신 문서** — 코드 변경 0건.
- **대응 설계서**: `docs/ai_design/POC3/POC3-ML-02-CLOSEOUT_REJECTED_SCORE_DEACTIVATION_DESIGN_V1.md`
- **개정**: **V1.1** (2026-08-29) — 설계자 판정 **`CONDITIONAL_PASS`** 수용.
  모호점 M-1~M-4 + CompareCards 확정 반영 · 필수 보완 4건 반영.
  **V2 파일을 만들지 않고 같은 파일을 개정**했다. 변경 절에 `[V1.1]` 표시.
- **상태**: `PLAN_V1.1_SUBMITTED — 레드팀 검토 대기`
- **다음 절차**: 레드팀 검토 → PASS → 최종 개발 지시 → 구현 → 검증자 검증 +
  사용자 실화면 확인(4개 화면) → Closeout 종료

---

## 0. 한 줄 요약과 **가장 중요한 발견**

확정 계약은 `CandidateTable` 과 `JudgmentWorkbench` **2곳**을 지목했다.
그런데 실제로 참고점수를 화면에 **표시하거나 정렬에 쓰는 곳은 5곳**이다.

> **`보유와 비교` 화면에도 `참고점수` 정렬 버튼이 살아 있고, `시장 발굴` 카드와
> `보유와 비교` 선택 상세도 점수·사유를 그대로 보여준다.**

2곳만 고치면 "점수 값이 화면 순서에 영향을 주지 않는다"(검증 계약 3·4)가
**`보유와 비교` 화면에서 깨진다.**

**[V1.1] 설계자 판정 — 5곳 모두 적용 확정.**
> 원 설계에서 2곳만 지목한 것은 소비처 전수 기준으로 불완전했습니다.
> ③④⑤를 포함하는 것은 범위 확장이 아니라 **REJECT 판정의 완결**입니다.

---

## 1. 현재 참고점수를 소비하는 프론트엔드 위치 **전체** (실측)

`grep -rn "relative_upside\|relativeUpside" frontend/app frontend/lib` 전수 결과.

### 1.1 표시 / 정렬에 쓰는 곳 — **5곳**

| # | 파일 | 소비 형태 | 화면 (한국어 메뉴명) |
|---|---|---|---|
| **①** | `CandidateTable.tsx` | 점수 열(`:285-287`) · 사유 열(`:305-310`) · **점수 정렬**(`:86-99`) · 고지 배너(`:324-341`) | 시장 발굴 — 후보 표 |
| **②** | `JudgmentWorkbenchView.tsx` | **정렬 키 `score`**(`:447-448`) · 정렬 버튼 `참고점수`(`:486`) · 행 표시(`:546-547`) · 선택 상세 `참고점수`(`:800`) | 판단 워크벤치 |
| **③** | `CandidateCards.tsx` | 점수 배지(`:124-129`) · **점수 근거 목록**(`:204-213`, 없으면 "점수 근거 없음") | 시장 발굴 — 후보 카드 |
| **④** | `HoldingsCompareView.tsx` | **정렬 키 `score`**(`:169`) · 정렬 버튼 `참고점수`(`:379`) | 보유와 비교 |
| **⑤** | `holdings_compare/SelectedDetail.tsx` | `참고점수:` 값(`:104-108`) · 사유 목록(`:109-116`) | 보유와 비교 — 선택 상세 |

**③④⑤ 는 설계서 확정 계약에 이름이 없다.**

### 1.2 전달만 하는 곳 (표시 아님)

| 파일 | 내용 |
|---|---|
| `MarketDiscoveryView.tsx:623-626` | `relative_upside_score_status` · `..._user_notice` 를 `CandidateTable` 로 prop 전달 |

### 1.3 유지 대상 — ML 연구 경로

| 파일 | 내용 |
|---|---|
| `MLView.tsx` | 좌측 **ML** 화면. 실행 상태 state + `RelativeUpsideRunCard` 마운트 |
| `RelativeUpsideRunCard.tsx` | **수동 실행 버튼**. 실행 → `relative_upside_score_v0` |
| `frontend/lib/api/mlRelativeUpside.ts` | 실행 API 클라이언트 |

`MLView.tsx:62` 에 **실행 성공 시 후보 화면으로 이동하는 링크**(`onNavigate`)가 있다.
**[V1.1] 설계자 확정 — 해당 기존 링크를 제거한다.**

### 1.4 타입 정의 (변경 없음)

`frontend/lib/api/market.ts:81-83,162-165` — `relative_upside_score` ·
`relative_upside_reasons` · `..._status` · `..._asof_date` · `..._generated_at` ·
`..._user_notice`. **API 계약 보존이므로 그대로 둔다.**

### 1.5 주석만 있는 곳 (변경 없음)

`holdings_compare/CompareCards.tsx:14-17` — "참고점수는 카드에서 뺐다" 는 기존 주석.
실제 표시 코드 없음. 다만 사유가 "맥에서 항상 null 이라서" 로 적혀 있어 현재
판정과 어긋난다 → 주석 1줄만 사실에 맞게 고칠 것을 제안(§6).

---

## 2. 제거되는 표시 · 정렬 로직

### 2.1 정렬 (검증 계약 2·3·4의 핵심)

| 위치 | 제거 내용 | 제거 후 |
|---|---|---|
| `CandidateTable.tsx:76-100,126-136` | `ScoreSort` 타입 · `sortByRelativeUpside()` · 헤더 클릭 토글 | **API 반환 순서 그대로 렌더** |
| `JudgmentWorkbenchView.tsx:447-448` | 정렬 키 `"score"` case | 키 목록에서 삭제 |
| `JudgmentWorkbenchView.tsx:486` | 정렬 버튼 `참고점수` | **선택지 자체 제거** |
| `HoldingsCompareView.tsx:41` | `CandidateSortKey` 의 `"score"` 리터럴 | 타입에서 삭제 |
| `HoldingsCompareView.tsx:169` | 정렬 키 `"score"` case | 키 목록에서 삭제 |
| `HoldingsCompareView.tsx:379` | 정렬 버튼 `참고점수` | **선택지 자체 제거** |

`CandidateSortKey` 타입에서 `"score"` 리터럴을 제거해 **타입 수준에서 재도입을
막는다**. 잔존 참조는 `tsc` 가 잡는다.

**비활성 선택지·`0`·`사용 불가`·경고 배지로 대체하지 않는다.**

### 2.1.1 [V1.1] 기본 정렬 상태 — 실측 확인

세 화면 모두 **기본 상태가 이미 API 순서**다. 점수 정렬은 사용자가 눌러야 켜진다.

| 화면 | 기본값 | 기본 상태 동작 |
|---|---|---|
| 후보 표 (`CandidateTable`) | `scoreSort = "off"` (`:120`) | `candidates` 를 **그대로** 렌더 |
| 판단 워크벤치 | `useSort("rank")` (`:408`) | `c.rank ?? 9999` = **API 순서** |
| 보유와 비교 | `candSortKey = "default"` (`:72`) | `if (candSortKey === "default") return list` (`:164`) |

→ 점수 정렬 제거는 **기본 화면 순서를 바꾸지 않는다.** 없어지는 것은
"사용자가 점수로 정렬할 수 있는 선택지" 뿐이다.

### 2.1.2 [V1.1] **정상 정렬은 보존한다** — 과잉 제거 금지

설계자 확정:

> "API 순서와 일치"는 **최초 진입 기본 상태**에 적용합니다. 사용자가 1개월·3개월 등
> 정상 정렬을 직접 선택한 뒤까지 API 순서를 강제하면 기존 기능을 망가뜨립니다.

**보존해야 하는 정렬 선택지 (실측 전수)**

| 화면 | 보존 |
|---|---|
| 판단 워크벤치 | `순위`(rank·기본) · `1M` · `3M` · `KODEX초과` · `고점대비` |
| 보유와 비교 | `default`(기본) · `20일 초과` · `고점 대비` · `보유 노출` |
| 후보 표 | 기존 열 정렬 동작 (점수 열 외) |

**`참고점수` 하나만 사라진다.** 이를 §5 테스트 C-7 로 고정한다.

### 2.2 표시

| 위치 | 제거 |
|---|---|
| `CandidateTable.tsx:280-312` | 점수 열 + 사유 열 (헤더 셀 포함) |
| `CandidateTable.tsx:324-341` | 참고점수 고지 배너 + `status !== "ok"` 안내 |
| `CandidateTable.tsx:107-116` | `relativeUpsideScoreStatus` · `...UserNotice` prop |
| `MarketDiscoveryView.tsx:623-626` | 위 prop 전달 |
| `JudgmentWorkbenchView.tsx:546-547` | 행의 `참고점수` 값 |
| `JudgmentWorkbenchView.tsx:800` | 선택 상세 `참고점수` DetailCell |
| `CandidateCards.tsx:124-129` | 점수 배지 |
| `CandidateCards.tsx:204-214` | 점수 근거 목록 + "점수 근거 없음" |
| `SelectedDetail.tsx:102-116` | `참고점수` 값 + 사유 목록 |

**빈 열·`—`·placeholder 를 남기지 않는다.** 열 자체를 없앤다.

### 2.3 삭제로 생기는 빈 자리 처리

- **[V1.1 확정]** `CandidateCards` 의 큰 숫자 자리(`wb-hrow-pnl`)는
  **1개월 수익률**(`c.returns.one_month.return_pct`)로 채운다. 라벨은 `1개월`.
  이미 카드가 계산해 두는 값(`:71 oneRet`)이고 `compute_topn` 기본 정렬 기준
  (`one_month desc`)과 같아 "왜 이 순서인지"를 그대로 설명한다.
  **순위 표기는 채택하지 않는다** — 설계자 근거: 순위는 필터 universe 에 따라
  달라지는 2차 가공값이라 실제 수익률이 더 직접적이다.
  **값이 없으면 `0` 으로 대체하지 않고 기존 unavailable 계약을 따른다** —
  `fmtPct(null)` 이 `DASH` 를 반환하는 현행 동작 그대로다(`CandidateCards.tsx:25-28`).
- `JudgmentWorkbenchView` 행의 `참고점수` 자리는 **열 자체 제거**(폭 재배분).
- `SelectedDetail` 의 `후보 흐름` 섹션은 점수만 빠지고 나머지 항목은 유지.

---

## 3. 유지되는 경로

| 대상 | 처리 |
|---|---|
| `GET /market/topn/latest` 응답 필드 6개 | **무변경** — 계약 보존 |
| `app/api_market_topn_service.py:merge_relative_upside_score()` | **무변경** |
| `app/ml_relative_upside_*.py` · `scripts/run_ml_relative_upside_score_v0.py` | **무변경** |
| `state/ml/relative_upside_score_latest.json` 등 artifact | **무변경·미삭제** |
| `app/ml_score_validity_*.py` · 평가 테스트 105건 | **무변경·미삭제** |
| `frontend/lib/api/market.ts` 타입 | **무변경** |
| ML 화면 수동 실행 (`MLView` · `RelativeUpsideRunCard`) | **유지 + 상태 표기 추가** |
| OCI · PUSH · cron | **무변경** |

### 3.1 ML 화면 상태 표기 (신규 추가 유일 항목)

**[V1.1]** `MLView.tsx:62` 의 후보 화면 이동 링크는 **제거**한다(M-2 확정).


`RelativeUpsideRunCard` 상단에 아래 3요소를 명시한다.

- 모델 식별자 **`relative_upside_v0`**
- 판정 **`REJECT`**
- **`연구용 baseline이며 투자 판단에 사용하지 않음`**

**이 문구와 점수는 ML 화면 밖 어디에도 노출하지 않는다.**
자동 실행·스케줄러·후보 화면 연결은 **추가하지 않는다**.

---

## 4. 변경 예상 파일

| 파일 | 구분 |
|---|---|
| `frontend/app/components/CandidateTable.tsx` | 수정 (표시·정렬·prop 제거) |
| `frontend/app/components/MarketDiscoveryView.tsx` | 수정 (prop 전달 제거) |
| `frontend/app/components/CandidateCards.tsx` | 수정 (배지·사유 제거, 빈 자리 대체) |
| `frontend/app/components/JudgmentWorkbenchView.tsx` | 수정 (정렬 키·버튼·표시·상세 제거) |
| `frontend/app/components/HoldingsCompareView.tsx` | 수정 (정렬 키·버튼 제거) |
| `frontend/app/components/holdings_compare/SelectedDetail.tsx` | 수정 (점수·사유 제거) |
| `frontend/app/components/holdings_compare/CompareCards.tsx` | 주석 1줄 정정 (§6) |
| `frontend/app/components/RelativeUpsideRunCard.tsx` | 수정 (REJECT·연구용 표기 추가) |
| `frontend/app/components/MLView.tsx` | **[V1.1]** 수정 — 후보 화면 이동 링크 제거 |
| `frontend/app/components/CandidateCards.test.tsx` | 수정 (계약 반영) |
| `frontend/app/components/JudgmentWorkbenchView.test.tsx` | 수정 (계약 반영) |
| `frontend/app/components/RejectedScoreCloseout.test.tsx` | **신규** (§5) |
| `docs/PROGRAM_TRUTH.md` | 수정 — 화면·표시 계약이 바뀌므로 갱신 대상 |
| `docs/STATE_LATEST.md` | 수정 |
| `docs/ai_result/POC3/POC3-ML-02-CLOSEOUT_..._RESULT.md` | **신규 (짧게)** |

**백엔드 파일 변경 0건.** `app/` · `scripts/` · `state/` · `.env` · cron · OCI 무변경.

---

## 5. 계약을 고정하는 테스트 [V1.1 개정]

설계서 검증 계약 6개 + 설계자 필수 보완을 1:1로 고정한다. 신규 파일
`frontend/app/components/RejectedScoreCloseout.test.tsx` 에 모은다 —
"REJECT 점수가 판단 화면에 되살아나지 않는다" 는 **하나의 책임**이라 한 파일로 둔다.

| # | 계약 | 테스트 |
|---|---|---|
| **C-1** | 점수·사유 미표시 | 점수 `72.3` · 사유 2건이 든 응답으로 **5개 화면 전부** 렌더 → `72.3` · 사유 문자열 · `참고점수` · `점수 근거` **미출현** |
| **C-2** | `참고점수` 정렬 선택지 부재 | 판단 워크벤치 · 보유와 비교 정렬 버튼 목록에 `참고점수` **없음** |
| **C-3** | **점수를 바꿔도 기본 순서 불변** | §5.1 |
| **C-4** | 기본 상태 순서 = API 순서 | §5.1 |
| **C-5** | ML 연구 화면 유지 + 표기 | `RelativeUpsideRunCard` 에 실행 버튼 존재 · `relative_upside_v0` · `REJECT` · `연구용 baseline이며 투자 판단에 사용하지 않음` 출현. **후보 화면 이동 링크 부재** |
| **C-6** | API·운영 무변경 | 백엔드 회귀 **1,268건** 재실행 + `git diff --stat` 에 `app/` · `scripts/` · `state/` · cron 변경 **0건** (기계 검사) |
| **C-7** | **[V1.1] 정상 정렬 보존** | §5.2 |
| **C-8** | **[V1.1] 카드 빈 자리 = 1개월 수익률** | 큰 숫자 자리에 `oneRet` 표시 · 라벨 `1개월` · `null` 이면 `0` 이 아니라 `DASH` |

### 5.1 [V1.1] 주문 불변 — **3개 화면 각각** 검증

설계자 필수 보완 1. 아래 **세 화면 각각**에서 같은 검사를 돌린다.

- `CandidateTable` (후보 표)
- `JudgmentWorkbenchView` (판단 워크벤치)
- `HoldingsCompareView` (보유와 비교)

각 화면마다 **동일한 후보 배열**을 3가지 변형으로 렌더한다.

| 변형 | 내용 |
|---|---|
| (a) 원본 | 응답 그대로 |
| (b) 점수 역순 | `relative_upside_score` 값만 뒤집음 (다른 필드 불변) |
| (c) 점수 제거 | `relative_upside_score` 전부 `null` |

**단언**
1. (a)·(b)·(c) 의 **렌더된 ticker 순서가 3개 모두 동일** → C-3
2. 그 순서가 응답 `candidates` 의 ticker 배열과 **동일** → C-4

**적용 범위는 최초 진입 기본 상태다.** 사용자가 정렬을 누른 뒤 상태는 대상이 아니다.

### 5.2 [V1.1] 정상 정렬 보존 — 과잉 제거 가드

점수 정렬만 없애려다 다른 정렬까지 망가뜨리는 것을 막는다.

| 화면 | 검사 |
|---|---|
| 판단 워크벤치 | `1M` 클릭 → 1개월 수익률 내림차순으로 **순서가 실제로 바뀐다**. `3M` · `KODEX초과` · `고점대비` · `순위` 도 각각 동작 |
| 보유와 비교 | `20일 초과` · `고점 대비` · `보유 노출` 각각 동작 |

정렬 선택지 목록 자체도 단언한다 — 판단 워크벤치는 **5개**(`순위`·`1M`·`3M`·
`KODEX초과`·`고점대비`), 보유와 비교는 **3개**(`20일 초과`·`고점 대비`·`보유 노출`).
`참고점수` 만 빠졌고 나머지는 그대로임을 고정한다.

### 5.3 [V1.1] grep 가드 — **보조 검사** (테스트 대체 불가)

설계자 필수 보완 3. **테스트가 계약을 고정하고, grep 은 잔존물을 훑는 보조 수단이다.**

- **패턴**: snake case 와 camel case 를 모두 검사한다 —
  `relative_upside_score` · `relative_upside_reasons` · `relative_upside_score_status` ·
  `relative_upside_score_user_notice` · `relativeUpside`
- **허용 위치는 둘뿐**:
  1. **API 타입 정의** — `frontend/lib/api/market.ts` (계약 보존)
  2. **ML 연구 경로** — `MLView.tsx` · `RelativeUpsideRunCard.tsx` ·
     `frontend/lib/api/mlRelativeUpside.ts`
- 그 외 위치에서 위 패턴이 나오면 **실패로 본다** (테스트 fixture 는 예외 —
  fixture 는 점수가 들어와도 화면에 안 나오는 것을 증명하는 데 필요하다).

## 6. 지시문 외 변경 제안 (승인 필요)

**[V1.1] 설계자 수용.** `holdings_compare/CompareCards.tsx:14-17` 주석이 참고점수를
뺀 이유를 **"이 맥 환경에서 항상 null 이고(ML 미실행)"** 로 적고 있다. 사실이 아니다.
제거 이유를 **`relative_upside_v0 REJECT 판정`** 으로 정정한다. 코드 동작 변화 0.

---

## 7. 중단 조건

| # | 조건 | 조치 |
|---|---|---|
| S-1 | 점수 제거가 API 응답·백엔드 코드 변경을 요구하는 상황 | 중단 + 질의 (계약 위반) |
| S-2 | 정렬 제거 후 화면 순서가 API 순서와 달라짐 | 중단 — 다른 정렬 로직이 숨어 있다는 뜻 |
| S-3 | `tsc` 가 잡지 못한 `score` 정렬 잔존 발견 | 중단 + 전수 재조사 |
| S-4 | 설계서에 없는 화면에서 점수 소비 추가 발견 | 중단 + 질의 (§1 전수 조사 갱신) |

---

## 8. [V1.1] 설계자 판정 반영 대조표

판정: **`CONDITIONAL_PASS`**. 모호점 4건 + 주석 1건 전부 확정됐고, 남은 모호점은 **없다**.

| 항목 | 판정 | 확정 내용 | 반영 위치 |
|---|---|---|---|
| M-1 적용 범위 | **수용** | **5곳 모두** 점수 표시·사유·정렬 영향 제거 | §0 · §1.1 · §2 · §5 C-1 |
| M-2 ML→후보 링크 | **수용** | 기존 링크 **제거** | §1.3 · §3.1 · §4 · §5 C-5 |
| M-3 카드 빈 자리 | **1개월 수익률 확정** | 순위 아닌 **실제 1개월 수익률**. 결측은 `0` 아닌 기존 unavailable 계약 | §2.3 · §5 C-8 |
| M-4 검증 경로 | **수용** | 검증자 `VERIFIED` **와** 사용자 실화면 확인 **모두** | §8.2 |
| CompareCards 주석 | **수용** | 제거 이유를 `relative_upside_v0 REJECT 판정` 으로 정정 | §6 |

**필수 보완 4건**

| # | 보완 요구 | 반영 |
|---|---|---|
| 1 | 주문 불변 테스트를 3개 화면 각각 · "API 순서 일치" 는 **최초 진입 기본 상태** 한정 | §5.1 · §2.1.2 (정상 정렬 보존 + C-7) |
| 2 | 표시 제거 범위 5곳 · **ML 연구 화면만 허용** | §1.1 · §2.2 · §5 C-1 · §5.3 |
| 3 | grep 은 **보조 검사** · snake+camel · reasons·status·notice 포함 · 허용 위치 명시 | §5.3 |
| 4 | 문서 정리 규칙 | §8.1 |

### 8.1 [V1.1] 문서 정리 규칙 (구현 종료 시)

| 문서 | 처리 |
|---|---|
| `docs/ai_result/POC3/POC3-ML-02-CLOSEOUT_..._RESULT.md` | **신규 · 짧게** 작성 |
| `docs/PROGRAM_TRUTH.md` | **갱신** — 화면·표시 계약이 바뀐다 |
| `docs/STATE_LATEST.md` | **갱신** |
| `POC3-ML-02_..._RESULT.md` (validity) | **다시 열지 않고 내용도 복제하지 않는다.** 참조만 |
| 기존 DESIGN · PLAN (validity · closeout) | **이력으로 보존** |

### 8.2 [V1.1] 완료 판정 경로

1. 레드팀 검토 → PASS
2. 설계자 최종 개발 지시
3. 구현
4. **검증자 `VERIFIED`**
5. **사용자 실화면 확인 — 4개 화면**: 시장 발굴 표·카드 / 판단 워크벤치 /
   보유와 비교 / ML 연구 화면
6. 양쪽 통과 후 Closeout 종료

**이 Closeout 이 끝나기 전에는 신규 ML 모델이나 다음 기능 Step 을 시작하지 않는다.**

## 9. 본 PLAN 단계에서 하지 않은 것

- 구현 **0건** (문서 2개 작성만)
- 프론트·백엔드 코드 변경 **0건**
- API·DB·artifact·모델 **무변경**
- `compute_topn(asof=...)` 결함 **미수정** (BACKLOG `DEF-COMPUTE-TOPN-ASOF-HISTORICAL`)
- 점수 평가 코드·증거 **미삭제**
- 커밋·푸시 — **별도 승인 필요**. 설계자 명시: 앞서 승인한 커밋·푸시는
  **문서 3개에 대한 승인**이며 **이번 UI 구현의 커밋·푸시를 미리 승인한 것이 아니다**
