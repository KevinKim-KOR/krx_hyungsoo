# 승인·알림 화면 역할 분리 및 재배치 — 개발 PLAN

* 문서 종류: 개발 PLAN (모호점 질문 포함 · 설계자 회신용)
* 대응 설계서: `docs/ai_design/POC3/POC3-APPROVAL_ALERT_ROLE_SEPARATION_V1_DESIGN_V1.md` (설계자 제공)
* 작성일: 2026-08-01
* 기준 revision: `041a8c2a` (선행 POC3-03 PASS/CLOSED)
* 상태: **개발 PLAN 확정 (설계자 Q1~Q6 답변 + 설계 정정 2026-08-01 반영).** PLAN 먼저 커밋 후 A구간 착수.
* 성격: 기존 화면(approval key·ApprovalTelegramView) 재배치. 신규 화면·메뉴·route·API·DB 0건(설계서 §1·§8). 독립 Operations Panel 제외·폐기.
* **⚠️ 설계 전제 정정 (Q1)**: `push_kind` 3종(holdings/market/spike)은 **모두 정보 PUSH**. 현재 계약에 "투자 판단 초안" 식별 필드 없음 → 이번 구현에서 판단 초안 영역·승인 대기 표현·자리표시자를 만들지 않는다. 화면 명칭 = **`OCI 적용·알림`** (내부 `approval` route key 는 유지). 판단 초안은 실제 식별 계약 마련 단계에서 연결.

---

## 0. 기반 문서 확인 완료

- `STATE_LATEST`(= POC3-03 PASS/CLOSED · 이 설계서가 다음 Step) · `PROJECT_ORIGIN_INTENT` 목적 · `KILL_SWITCHES` 확인.
- 독립 Operations Panel(P-05) 제외·폐기 · POC3-04 번호 미부여(설계서 §1) 확인.
- A·B·C 순차 게이트(§7): 한 설계 안에서 개발·사용자 확인 시점만 나눔.

---

## 1. 개발 전 사실 확인 결과 (설계서 §6 — 실측 완료)

### 1.1 현재 ApprovalTelegramView 구성 [확인]
`frontend/app/components/ApprovalTelegramView.tsx` 실측 — 현재 한 화면에 순서대로:
1. 제목 "Approval / Telegram" + subtitle + role-banner(STEP 5 안내)
2. `<ThreePushParamCard/>` — OCI 운영 기준 적용 (create→approve→sync→verify)
3. `<UniverseRefreshPanel/>` — 신규 ETF 관찰 후보 갱신 (PUSH-2 보조)
4. `<ThreePushDraftCard onDraftCreated={setRun}/>` — PUSH-1/PUSH-3 초안 생성 진입점
5. `run ? <RunPanel/> : 빈 안내 카드` — 현재 run 승인/거절/상태
6. `<details>개발/테스트용</details>` → `<SampleDraftQuickButton/>` (접힘)

### 1.2 각 컴포넌트 API·부수효과 [확인]
| 컴포넌트 | 호출 API | 부수효과 | props |
|---|---|---|---|
| `RunPanel` | `approveRun`·`rejectRun`·`fetchRun`(polling) | run status 전이 | run·setRun·loading·errorMsg |
| `ThreePushParamCard` | `applyThreePushParamToOci`·`fetchThreePushParamState` | OCI PARAM 적용 | 없음(자체 상태) |
| `ThreePushDraftCard` | `generateMarketBriefingDraft`(PUSH-1)·`generateSpikeAlertDraft`(PUSH-3) | run 생성 → setRun | onDraftCreated |
| `UniverseRefreshPanel` | `refreshUniverseMomentum` | 없음(로컬 state만·mount fetch 안 함) | **없음** |
| `SampleDraftQuickButton` | 샘플 draft 생성 | run 생성 | onDraftCreated |
| `HoldingsClient`(내가 가진 ETF) | `generateDraftFromHoldings`(PUSH-2) | run 생성 → MainPanel setRun → approval 자동 이동 | onDraftCreated |

### 1.3 판단 초안 vs 정보 PUSH run 구분 필드 [확인 — Q1 로 해소]
- **`Run.push_kind` 필드 존재** (`lib/api/runApproval.ts:40`): `"holdings_briefing"`(PUSH-2) / `"market_briefing"`(PUSH-1) / `"spike_or_falling_alert"`(PUSH-3).
- **단, 과거 run 은 `null`/`undefined` 가능** (동 파일 L24·38·40 명시).
- **설계자 확정(Q1-c)**: push_kind 3종은 **모두 정보 PUSH**. 현재 계약에 "투자 판단 초안" 식별 필드 **없음** → 이번 구현에서 판단 초안으로 분류하는 run 없음. push_kind=null 은 `종류 확인 불가`(Q2-b).

### 1.4 UniverseRefreshPanel 이동 안전성 [확인]
- props 없음 · mount 시 fetch 없음 · POST 응답을 자기 `useState` 로만 보관 → **공유 상태·캐시 없음.** MarketDiscoveryView(요즘 잘 오르는 ETF)로 이동해도 다른 화면 상태 안 깨짐. queryCache 미사용.
- MarketDiscoveryView 에는 이미 `RefreshControlCard`(최신 시장 데이터 갱신)가 있음 — UniverseRefreshPanel(신규 ETF 관찰 후보)과 **다른 기능**. 이동 시 자리 있음.

### 1.5 OCI 자동 PUSH 이력 조회 계약 [확인 — 부재]
- 현재 프론트에 "OCI 자동 발송 이력" 을 읽는 API 없음(runApproval·threePushParam 은 run 승인·PARAM 적용만). → 설계서 §5.4·§9 대로 **자동 발송 이력은 표시하지 않음**(신규 API 필요 → BACKLOG). 최근 처리 결과는 run 처리·PARAM 적용·수동 미리보기 범위만.

---

## 2. 구현 방침 (설계자 정정 반영 · 확정)

> ApprovalTelegramView 를 `OCI 적용·알림` 화면으로 재배치. 컴포넌트 재사용, 배치·문구·위계 변경. **판단 초안 영역·승인 대기 표현·빈 자리표시자 생성 금지.**

- **화면 명칭**: 제목·설명을 **`OCI 적용·알림`** 기준으로. 내부 `approval` route key·MainPanel 분기·draft→approval 자동 이동 경로는 불변.
- **상단 요약**: OCI 적용 상태(ThreePushParamCard 기준) + 정보 PUSH 운영 방식 안내. 실측 조회값 없으면 **"운영 기준(정책 안내)"** 만 — `정상`·`운영 중`·`최근 성공` 등 실측 상태 위장 금지(Q4).
- **주 작업 = OCI 적용**: `ThreePushParamCard`(create→approve→sync→verify 계약 불변)를 상단 주 작업으로 배치. 이 버튼은 정보 PUSH 개별 승인 버튼 아님.
- **정보 PUSH 3카드 = 운영 방식 안내만**(Q3-a): Market/Holdings/Spike 를 같은 위계 3카드로, 각 자동 발송 방식 안내. **승인 run 을 담지 않음.** 메시지별 승인 필요처럼 보이는 문구 금지.
- **미리보기·수동 전달 점검 영역**: `ThreePushDraftCard`(PUSH-1/3 수동 생성)와 `RunPanel`(현재 run 수동 처리)을 이 영역으로 이동. **RunPanel 은 "투자 판단 초안" 이 아니라 기존 수동 처리 기능으로 표시.** 발송 버튼과 시각 구분. 자동 PUSH ↔ PC 수동 run 을 다른 것으로 표시.
- **현재 미리보기·수동 처리 상태**(Q5-a): MainPanel 메모리의 현재 run 1건만 표시. 명칭 = `최근 처리 결과` 아니라 **`현재 미리보기·수동 처리 상태`**. PARAM 적용 결과는 ThreePushParamCard 내부 유지. run_id·raw status·JSON 은 상세 펼침 안.
- **push_kind=null run**(Q2-b): `종류 확인 불가 — 기존 기록` 으로 개발·호환 점검 영역에만. 임의 기본 분류 금지.
- **개발·호환 점검**: 최하단 기본 접힘 — SampleDraftQuickButton + push_kind=null run 등.
- **UniverseRefreshPanel(§5.6)**: ApprovalTelegramView 에서 제거 → MarketDiscoveryView `RefreshControlCard` **바로 다음 별도 카드**(Q6-b)로. 명칭 `신규 ETF 관찰 후보 다시 계산`, RefreshControlCard 는 `시장 데이터 갱신` — 두 갱신 차이 명시, 합치지 않음. 1회만.
- **A·B·C 게이트**(정정본 §3): A(운영 기능 역할 정리) → 확인1·2 → B(수동 점검·현재 run) → 확인3·4 → C(이동·정리) → 확인5 → 최종 검증.

---

## 3. 설계자 확정 답변 (2026-08-01)

| 질문 | 확정 판단 |
|---|---|
| Q1 | **(c)** push_kind 3종 모두 정보 PUSH. 현재 run 중 "투자 판단 초안" 으로 분류할 수 있는 것 없음. |
| Q2 | **(b)** `push_kind=null` = `종류 확인 불가 — 기존 기록`, 개발·호환 점검에만 표시. 임의 기본 분류 금지. |
| Q3 | **(a)** 정보 PUSH 3카드 = 운영 방식 안내만. 승인 run 미포함. |
| Q4 | 실행 이력 API 없음 → `운영 기준` 만 표시. `정상`·`운영 중`·`최근 성공` 실측 상태 표시 금지. |
| Q5 | **(a)** 메모리 현재 run 1건만. 명칭 = `현재 미리보기·수동 처리 상태`(≠ 최근 처리 결과). PARAM 결과는 ThreePushParamCard 내부 유지. |
| Q6 | **(b)** `RefreshControlCard`(시장 데이터 갱신) 바로 다음 별도 카드(`신규 ETF 관찰 후보 다시 계산`). 두 갱신 차이 명시, 합치지 않음. |

### 설계 정정 (설계자 확정 — 기존 설계의 RunPanel=판단초안 배치 오류 수정)

- 투자 판단 초안 상단 영역: **이번 구현에서 제외.** 빈 카드·자리표시자 생성 금지.
- `ThreePushDraftCard`·`RunPanel`: `미리보기·수동 전달 점검` 영역으로 이동.
- 3종 push_kind: 모두 정보 PUSH 의 수동 점검 결과로 취급.
- 자동 PUSH ↔ PC 생성 수동 run: 서로 다른 것으로 표시.
- 화면 명칭: **`OCI 적용·알림`**. 내부 `approval` route key 유지.
- 판단 초안은 실제 식별 계약 마련 단계에서 연결(이번엔 없는 기능 위장 금지).

---

## 4. A·B·C 순차 게이트 (설계자 정정본)

### A구간 — 운영 기능 역할 정리
- 화면 제목·설명을 `OCI 적용·알림` 기준으로 정리.
- OCI 적용(ThreePushParamCard)을 주 작업으로 배치.
- Market·Holdings·Spike 운영 기준 카드 배치(안내만).
- 메시지별 승인 없는 자동 PUSH 임을 명시.
- **투자 판단 초안 영역·승인 대기 표현 만들지 않음.**
- 사용자 확인: (1) OCI 적용과 정보 PUSH 역할이 바로 구분되나 (2) 정보 PUSH 마다 승인 필요처럼 보이지 않나.

### B구간 — 수동 점검과 현재 run 정리
- `ThreePushDraftCard` → `미리보기·수동 전달 점검` 이동.
- `RunPanel` = 투자 판단 아닌 기존 수동 처리 기능으로 표시.
- 현재 run 1건만 `현재 미리보기·수동 처리 상태` 에 표시.
- `push_kind=null` → 개발·호환 점검으로 이동.
- 자동 발송 이력처럼 보이는 표현 금지.
- 사용자 확인: (3) 자동 PUSH ↔ PC 수동 미리보기 혼동 없나 (4) 기존 수동 전달 기능을 찾을 수 있나.

### C구간 — 잘못 배치된 기능 이동
- `UniverseRefreshPanel` 이동(MarketDiscoveryView).
- 개발·호환 기능 기본 접힘.
- 기능 누락·중복 확인.
- 전체 정보 위계 정리.
- 사용자 확인: (5) 화면에 OCI 적용·알림 기능만 남고 기존 기능도 빠짐없이 찾을 수 있나.

> 각 구간 개발 후 멈추고 사용자 확인. 미통과 시 해당 구간만 수정. A 통과 전 B, B 통과 전 C 진행 금지. C 통과 후에만 전체 검증·최종 PASS.

---

## 6. 개발 완료 후 산출물(예정)

- 수정: `ApprovalTelegramView.tsx`(재배치·`OCI 적용·알림`) · `MarketDiscoveryView.tsx`(UniverseRefreshPanel 수용) · 필요 시 하위 카드 wrapper · `globals.css`(영역 스타일) · 관련 테스트.
- 백엔드·API·DB·화면 전환 key·데이터 계약 **무변경**.
- 결과서: `docs/ai_result/POC3/POC3-APPROVAL_ALERT_ROLE_SEPARATION_V1_RESULT.md`.
- **통합지도·STATE 정정(설계서 §10)은 구현 완료 후 최종 Closeout 에서** 함께 반영. 착수 선행조건 아님(설계서 §1). 본 정정 내용은 확정 PLAN 에 기록.

---

## 7. 착수 계획 (확정)

1. **PLAN 먼저 커밋** (개발과 분리 — 설계자 지시). 이 커밋에는 PLAN 문서만 포함.
2. **A구간 개발 착수** (운영 기능 역할 정리 · 판단 초안 영역 미생성).
3. A구간 사용자 확인(1·2) 통과 후 B구간, B 통과 후 C구간.
4. 과거 설계서·통합지도·STATE 는 착수 전에 고치지 않음 — 최종 Closeout 에서 §10 대로 일괄 정정.

착수 전 소스 수정 없음. Q1~Q6 확정으로 추가 질문 없이 진행 가능. 신규 API 필요는 자동 발송 이력 1건(설계서 §9 BACKLOG) 외 없음.
