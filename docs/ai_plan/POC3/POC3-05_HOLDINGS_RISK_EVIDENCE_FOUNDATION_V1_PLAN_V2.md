# POC3-05 Holdings Risk Evidence Foundation V1 — 개발 PLAN_V2 (화면 분리)

* 문서 종류: 개발 PLAN_V2 (모호점 질문 포함 · 설계자 회신용)
* 대응 설계서: `docs/ai_design/POC3/POC3-05_HOLDINGS_RISK_EVIDENCE_FOUNDATION_V1_DESIGN_V2.md`
* 대체 관계: 본 PLAN_V2 가 구현 기준. `PLAN_V1` 은 사실확인 근거로만 보존(설계서 §8.2).
* 작성일: 2026-08-02
* 기준 revision: `2a46a042` (DESIGN_V2 + 세션 인계 문서 커밋).
* 레드팀: **PASS · 별도 revision 없음** (사용자 확인 2026-08-02). V2 는 새 문서라 재확인했고 추가 반영 사항 없음.
* 상태: **PLAN_V2 확정 (설계자 Q1~Q5 답변 반영, 2026-08-02).** Q1~Q4 화면구조·운영원칙으로 확정 · Q5는 A구간 사실확인 항목으로 이동. PLAN 먼저 커밋 후 A구간 착수. 화면 분리(B) 코딩은 A 완료 후.
* 성격: 기존 evidence·보유 계약 **재사용 + 화면 재배치**. 신규 API·DB·source·factor·formula·threshold·label 0건. 신규 화면 전환 key 2개(`holdings_manage`·`holdings_evidence`)만(설계서 §4.1·§10·AC-18).

---

## 0. 기반 문서 확인 완료

- `CLAUDE.md`(DEV_RULES) · `docs/STATE_LATEST.md`(선행 POC3-04 승인·알림 CLOSED) · DESIGN_V2 정독.
- 설계서 §5 확정 사실 9개는 다시 전수 조사하지 않음. 본 PLAN 은 지정 화면·직접 호출 경로·현재 미커밋 변경만 실측(§5·§8.2·§9-A).
- 사용자 화면 금지어(§4.4·AC-19): `저위험`·`고위험`·`안전`·`매도`·`손절`·`BUY`·`SELL` 미사용. 화면 명칭 = `확인 근거` / `자료 확인 필요`.

---

## 1. 재조사하지 않는 확정 사실 (설계서 §5 — 그대로 신뢰)

설계서 §5 1~9 항목(evidence 1회 조회·필드 존재·enriched 집계·falling 제외·topn 미사용·ticker 통합·입력행 유지·기존 메뉴 key 존재·판단초안 식별 계약 없음)은 재조사 없이 신뢰한다. 실제 코드가 이 사실과 충돌하는 지점에 한해서만 그 지점을 추가 조사한다(§5 마지막 문단).

---

## 2. 현재 미커밋 변경·구현 완료분 (실측 — 설계서 §9-A)

`git status --short --untracked-files=all` (2026-08-02 실측):

| 상태 | 파일 | V1 성격 | V2 처리 |
|---|---|---|---|
| ` M` | `frontend/app/components/HoldingsView.tsx` | 한 화면 하단에 `<HoldingsRiskEvidenceSection/>` mount + divider | **mount 이동 대상.** 확인 근거를 `holdings_evidence` 별도 화면으로 옮기고 HoldingsView 에서 제거 |
| ` M` | `frontend/app/globals.css` | `hre-*` 스타일 추가 | **재사용** (확인 근거 화면에서 그대로 사용) |
| `??` | `frontend/app/components/HoldingsRiskEvidenceSection.tsx` | 읽기 전용 확인 근거 표 컴포넌트 | **재사용** — `holdings_evidence` 화면 본체로 이동 |
| `??` | `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx` | 컴포넌트 테스트 5 케이스 | 재사용 (경로·mount 위치 변경 시 갱신) |
| `??` | `frontend/app/components/holdings_risk_evidence/helpers.ts` | evidence ticker 통합·need_check·5일 정렬 순수 헬퍼 | **재사용** (변경 없음) |
| `??` | `frontend/app/components/holdings_risk_evidence/helpers.test.ts` | 헬퍼 테스트 10 케이스 | 재사용 (변경 없음) |

**이번 Step 무관 untracked (POC3-05 산출물 아님 · 커밋·보고 제외):** `design/DESIGN-apple.md`, `docs.zip`. 본 Step 에서 생성·이동·삭제하지 않는다.

**마지막 실행 검증(참고, 재현 예정):** vitest 123 passed · tsc 0 · eslint 0. (LF/CRLF 의존 절대 라인 수는 보고에 쓰지 않음.)

---

## 3. 재사용 컴포넌트·헬퍼 (실측 대조 완료)

### 3.1 `holdings_risk_evidence/helpers.ts` — 그대로 재사용
- `buildRiskEvidenceRows(enriched, evidenceItems)` → `RiskEvidenceResult{rows, coverage}`. 신규 계산 0건.
- enriched 집계는 기존 `holdings_compare/helpers.ts`의 `aggregateHoldingsByTicker` 재사용 — 반환 필드 `eval_amount`·`eval_partial_unavail`·`pnl_rate_pct`·`market_weight_pct`·`data_missing` 실측 확인(설계서 §5-6·AC-9 동일 의미). **§11 복귀조건 3(집계 의미 변경) 미해당.**
- `computeNeedCheck` = 설계서 §6.2 기준(enriched 결측 / evidence not_loaded·conflict·partial·unavailable / 5·20·KODEX200 null). NAV·구성종목·topn 제외.
- `lowestFiveDayRows(rows, limit)` = §6.3 정렬(status=ok & 5일 유효만 오름차순, 동률 ticker 오름차순, 최대 N). Dashboard 요약(최대 3건, C구간)에 재사용 예정.

### 3.2 `HoldingsRiskEvidenceSection.tsx` — `holdings_evidence` 화면으로 재사용
- 조회: `useSharedQuery(DASH_KEY_HOLDINGS, fetchEnrichedHoldings)` + `useSharedQuery(DASH_KEY_EVIDENCE, fetchHoldingsMarketEvidence)` — Dashboard 와 캐시 키 공유(N+1 없음 · AC-15). 목록에서 ticker별 시계열 재호출 없음.
- 요약(기준일·coverage) · 빠른 보기(전체/자료 확인 필요) · ticker 통합 한 줄 표 · 선택 상세 lazy `PriceChart` = 설계서 §4.4 노출 요구 충족.
- `자료 확인 필요` 문구만 사용 · 위험 등급/매도 없음(AC-19). Holdings·Market 기준일 분리 표시(§6.4).

---

## 4. 이동·삭제할 mount 지점 (실측 — 설계서 §9-A)

### 4.1 LeftSidebar — MenuKey 9→11, `manage` 그룹 재구성
- `frontend/app/components/LeftSidebar.tsx`
  - `MenuKey` union(L23~32): `holdings`·`data_status` 존재. **`holdings_manage`·`holdings_evidence` 2개 추가**(AC-18).
  - `ALL_MENU_KEYS` 배열(L100~110): 2 key 추가 → `assertMenuGroupsCover()`(L112~131)가 11개 "정확히 1회 귀속" 자동 검증. 누락·중복 시 throw(fail-closed 유지 · AC-3).
  - `MENU_GROUPS` `manage` 그룹(L67~73): 현재 `holdings`("내가 가진 ETF") + `data_status` 2개 → **4개**: `보유 현황`(holdings) · `종목 관리`(holdings_manage) · `확인 근거`(holdings_evidence) · `데이터 상태`(data_status), 이 순서(AC-2). `내가 가진 ETF` 라벨은 `보유 현황`으로 변경, 부모·5번째 메뉴 없음(AC-4).

### 4.2 MainPanel — switch 2 case 추가
- `frontend/app/components/MainPanel.tsx`
  - switch(L46~77): `case "holdings"`(L68)·`case "data_status"`(L74) 존재. **`case "holdings_manage"`·`case "holdings_evidence"` 2개 추가.**
  - `holdings` → `보유 현황`(평가·시세 갱신, 입력폼 제거) · `holdings_manage` → `종목 관리`(입력·저장) · `holdings_evidence` → `확인 근거`(HoldingsRiskEvidenceSection). B구간에서 HoldingsView 를 세 역할로 분해.

### 4.3 HoldingsView — 세 역할로 분해
- `frontend/app/components/HoldingsView.tsx`
  - 현재: `HoldingsClient`(입력+평가+초안버튼) + `<HoldingsRiskEvidenceSection/>` 한 화면.
  - V2: `보유 현황`(평가·시세 갱신 읽기 중심, 입력폼·초안·긴 evidence 표 제거 · AC-5) / `종목 관리`(입력·수정·삭제·저장 · AC-6) / `확인 근거`(RiskEvidenceSection · AC-7)로 분리. **B구간 §5 모호점 Q1~Q3 확정 후 확정.**

### 4.4 수동 초안 생성 — Holdings 제거 (C구간)
- `frontend/app/components/HoldingsClient.tsx`
  - `generateDraftFromHoldings`(L203~214 `onGenerate`) + 버튼 `저장된 보유 종목으로 초안 만들기`(L375~377).
  - 설계서 §4.6: Holdings 계열 세 화면에서 **제거**, 기존 실행 계약은 삭제 금지. `OCI 적용·알림 > 미리보기·수동 전달 점검`에 동일 기능이 이미 있으면 중복 생성 금지 → **A-Q5 사실확인(§6 A구간)** 으로 A구간에서 해소.
  - `MainPanel.handleDraftCreated`(L34~43): 초안 생성 시 `approval` 자동 전환. 초안 버튼을 Holdings 에서 떼면 이 콜백 경로 정리 필요 → Q4 확정(자동 전환 불필요)에 따라 정리.

### 4.5 Dashboard·Workbench 이동 연결 (C구간)
- `frontend/app/components/DashboardView.tsx`: 보유 관련 이동이 현재 모두 `holdings`(L157·L216·L447·L562 `ex.action`)로 감. 설계서 §7·AC-13 = 평가 연결 → `보유 현황`, 확인 대상 연결 → `확인 근거`로 분기 필요. "판단 초안 생성" 카드 문구(L655)는 §4.6 이동에 맞춰 정정. **C구간에서 처리.**
- `JudgmentWorkbenchView`: 보유·근거 이동 연결(§7·AC-14) — C구간에서 실측 후 처리.
- **A-Q5(수동 초안 위치 사실확인)만은 §6 A구간에서 먼저 실측**(C구간 미룸 금지). 위 Dashboard·Workbench 이동 연결 자체는 C구간 유지.

---

## 5. 모호점 — 설계자 확정 답변 반영 (2026-08-02)

> 설계자 확정: Q1~Q4는 화면 구조·운영 원칙으로 결정됨(사용자 추가 선택 불필요, 사용자 판단 시점은 B·C 실화면 확인). Q5는 사용자 질문이 아니라 **A구간 사실확인 항목** → §6 A구간으로 이동(C구간 미룸 금지).

**Q1. `보유 현황`(holdings) 화면 구성 → (a) 확정.**
기존 `HoldingsClient`의 **입력 영역과 평가·시세 영역을 분리해 재사용**한다. `보유 현황`은 평가·시세부만, `종목 관리`는 입력부만 렌더. **새 평가 계산·중복 조회 로직은 만들지 않는다.** 세부 컴포넌트 분할 방식은 개발자 판단.

**Q2. 기존 시장 Evidence(`HoldingsMarketEvidenceCard`, HoldingsClient L407) → (a) 보정 확정.**
기존 카드를 다른 화면(`종목 관리`·`보유 현황`)에서 **제거**하고, 허용된 고유 정보만 `확인 근거`의 **표 → 선택 상세 흐름에 통합**한다. 기존 카드를 별도 대형 패널로 그대로 붙이지 않는다(AC-8). 카드 컴포넌트 자체를 유지할지는 구현 세부 — 핵심은 **정보 누락 없이 중복 대형 카드가 남지 않는 것**.

`확인 근거` 통합 범위(설계자 명시):
- **기본 표:** 평가액 · 평가 비중 · 손익 · 5일 · 20일 · KODEX200 대비 · 자료 상태
- **ticker 선택 상세:** 기존 가격 차트 · NAV · 괴리율 · 구성종목 · 중복률
- **제외:** `topn_match` · 급락 신호 · 신규 위험 판정
  → 현재 `HoldingsRiskEvidenceSection` 선택 상세는 `PriceChart` 만 있고 NAV·괴리율·구성종목·중복률은 미포함. B구간에서 기존 `HoldingsMarketEvidenceCard`가 제공하던 이 정보를 선택 상세로 이식 필요(신규 계산 아님, 기존 표시 재사용).

**Q3. `종목 관리` 저장 후 이동 → 자동 전환 안 함 확정.**
저장 성공 상태를 유지하고 `보유 현황 보기` 버튼을 제공한다. **사용자가 클릭할 때만 이동**(신규 자동 전환 도입 금지).

**Q4. 초안 실행 후 전환 → 자동 전환 불필요 확정.**
실행 성공 후 사용자가 기존 `미리보기·수동 전달 점검`에 도달하거나 그 화면에 머무는 결과를 유지한다. **이미 해당 화면에서 실행한다면 별도 자동 전환은 불필요**하다. → `MainPanel.handleDraftCreated`의 초안→approval 자동 전환은 초안 버튼이 그 화면으로 이동하면 자연히 불필요해짐. Q5(§6 A구간) 실측 결과에 따라 정리.

---

## 6. 개발 게이트 계획 (설계서 §9 순서)

1. **PLAN_V2 확정 → PLAN_V2 먼저 커밋**(개발과 분리 · 설계서 §14).
2. **A구간 — 보존 목록·메뉴 계약 + Q5 사실확인 (코딩 재개 전 완료)**
   - 보존 목록·재사용 컴포넌트·메뉴 귀속(11 key)·목적별 이동 매핑 확정(본 §2~4).
   - **A-Q5 (수동 초안 기능 위치 사실확인):** POC3-04 결과물(`ApprovalTelegramView` 계열)과 `generateDraftFromHoldings` **직접 호출 경로만** 확인. 전체 저장소 재조사 아님(설계서 §5·§9-A). 실측 결과별 처리:

     | 실측 결과 | 처리 |
     |---|---|
     | 동일 기능이 이미 있음 | Holdings 버튼만 제거하고 기존 기능 사용 |
     | 동일 기능 없으나 기존 계약 그대로 이동 가능 | 중복 없이 C구간에서 위치만 이동 |
     | 신규 run·승인·발송 계약 필요 | **구현하지 않고 설계자 복귀**(§11-5) |

   - A 완료 전 화면 분리 코딩 재개 금지(설계서 §9-A).
3. **B구간** — LeftSidebar 4메뉴 + MainPanel 2 case + HoldingsView 3분해(Q1) + 확인근거 이동·시장 Evidence 통합·선택 상세에 NAV·괴리율·구성종목·중복률 이식(Q2). → **사용자 실화면 확인 B(1~4).** 미통과 시 B 안에서 수정, C 전진 금지.
4. **C구간** — Dashboard·Workbench 목적별 이동 연결 + 초안 Holdings 제거·수동 점검 귀속(Q3·Q4 확정 반영, 위치 이동은 A-Q5 실측 처리에 따름). → **사용자 실화면 확인 C(5~7).**
5. **전체 검증** — 변경 범위 vitest·tsc·eslint. AC 1~21 전수 대조. 하나라도 미충족이면 PASS 아님.
6. RESULT·STATE·통합지도·BACKLOG Closeout → 설계자 PASS/CLOSED.

각 구간: 개발 → 사용자 실화면 확인 → 커밋. 결과서까지 만든 뒤 함께 push.

---

## 7. 하지 않는 것 (설계서 §10 재확인)

신규 API·DB·table·source·proxy / factor·formula·threshold·위험 label / 급락 GET 신설 / topn_match 위험 근거 사용 / 위험 점수·등급·순위 저장 / BUY·SELL·주문 / 신규 최상위 그룹·URL 라우터 / `내가 가진 ETF` 부모 3단계 메뉴 — 전부 안 함.

---

## 8. 설계자 복귀 조건 감시 (설계서 §11)

§11 1~8 중 하나라도 확인되면 자체 판단 없이 설계자 복귀. 특히:
- (5) 초안 이동에 신규 run 종류·승인·외부 발송 변경 필요 시(A-Q5 실측 결과) → 즉시 복귀.
- (3) ticker 통합 의미가 `aggregateHoldingsByTicker`와 달라져야 할 때 → 복귀. (현재 §3.1 실측상 동일 의미 재사용이라 미해당.)
- (7) 화면 분리 과정에서 보유 입력·저장 의미가 달라질 때 → 복귀.

문서 끝.
