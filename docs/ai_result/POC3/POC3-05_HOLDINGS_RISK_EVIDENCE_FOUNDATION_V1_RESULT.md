# POC3-05 Holdings Risk Evidence Foundation V1 — 개발 결과서 (DESIGN_V2 화면 분리)

* 문서 종류: 개발 결과서 (검증자 입력 · 개발자→검증자 보고)
* 대응 설계서: `docs/ai_design/POC3/POC3-05_HOLDINGS_RISK_EVIDENCE_FOUNDATION_V1_DESIGN_V2.md`
* 대응 PLAN: `docs/ai_plan/POC3/POC3-05_HOLDINGS_RISK_EVIDENCE_FOUNDATION_V1_PLAN_V2.md`
* 작성일: 2026-08-02
* 완료 커밋: PLAN_V2 `78d902c2`·`cdf57732`·`9f49547b` · A `a38893b4` · **B `077636e3`** · **C `d05a122e`**
* 레드팀: PASS · 별도 revision 없음 (사용자 확인 2026-08-02)
* 자체 검수(최종): `npx tsc --noEmit` 0 · `npm run lint` 0 · `npx vitest run` **123 passed**
* 사용자 실화면 확인: **B 통과** ("잘 나눠졌네요") · **C 통과** ("화면 쪼개진 것 말고는 크게 와닿는 것 없어요")

---

## 1) 처리한 요구사항

설계서 §9 순차 게이트 A/B/C 전부 수행.

- **A구간 (보존·메뉴 계약 + A-Q5 사실확인)**: DONE — PLAN_V2 §9. A-Q5 실측 결과 "기존 계약 그대로 이동 가능" 판정, 설계자 복귀 §11-5 미해당.
- **B구간 (4하위 화면 분리)**: DONE — 보유 현황·종목 관리·확인 근거·데이터 상태.
- **C구간 (Dashboard·Workbench 이동 + 초안 OCI 이동)**: DONE.
- **전체 검증(AC 1~21)**: DONE — §5 대조표.

## 2) 변경된 파일 목록

### 신규
- `frontend/app/components/HoldingsManageView.tsx` — 종목 관리 화면 (입력·저장 전용)
- `frontend/app/components/HoldingsEvidenceView.tsx` — 확인 근거 화면 (RiskEvidenceSection 래핑)
- `frontend/app/components/HoldingsRiskEvidenceSection.tsx` — 확인 근거 표·선택 상세 (B구간 구현물, 재사용)
- `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx` — 5 케이스
- `frontend/app/components/holdings_risk_evidence/helpers.ts` — evidence ticker 통합·need_check·5일 정렬 순수 헬퍼
- `frontend/app/components/holdings_risk_evidence/helpers.test.ts` — 10 케이스
- `frontend/app/components/_orphaned/README.md` — 고아 컴포넌트 보관 안내

### 수정
- `frontend/app/components/LeftSidebar.tsx` — MenuKey 9→11, manage 그룹 4메뉴, ALL_MENU_KEYS 2 key
- `frontend/app/components/LeftSidebar.test.tsx` — 11 key·라벨 반영
- `frontend/app/components/MainPanel.tsx` — switch 2 case, 초안 자동전환 제거
- `frontend/app/components/HoldingsView.tsx` — 보유 현황(평가·시세 갱신, 입력폼 없음)으로 재작성
- `frontend/app/components/DashboardView.tsx` — 목적별 이동 분기 + 도움말 정정
- `frontend/app/components/DashboardView.test.tsx` — 근거 이동 대상 holdings_evidence 반영
- `frontend/app/components/JudgmentWorkbenchView.tsx` — 목적별 이동 분기
- `frontend/app/components/approval/ManualPreviewSection.tsx` — PUSH-2 초안 버튼 이식
- `frontend/app/components/ThreePushDraftCard.tsx` — PUSH-2 담당 위치 문구 정정
- `frontend/app/components/TodayInvestmentCheckView.test.tsx` — AC-7 금지어에서 `근거` 제외
- `frontend/app/globals.css` — hre-* 스타일 + 선택 상세 NAV·구성종목 스타일

### 이동 (git rename)
- `HoldingsClient.tsx` → `_orphaned/HoldingsClient.tsx` (참조 끊김)
- `HoldingsMarketEvidenceCard.tsx` → `_orphaned/HoldingsMarketEvidenceCard.tsx` (고아 HoldingsClient 에서만 참조)

## 3) 신규 추가된 의존성

없음. (신규 API·DB·source·factor·formula·threshold·label·라이브러리 0건 — AC-17.)

## 4) 지시문 외 변경

- **`_orphaned/` 폴더 도입 + 구 컴포넌트 2개 이동**: 설계서 §8.1 "복제본 남기지 않는다" 이행. 삭제 대신 이동은 **사용자 지시**(2026-08-02: "고아가 된 컴포넌트는 별도 폴더로 보냅니다. 오류 없으면 추후 삭제").
- **AC-7 금지어에서 `근거` 제외**: DESIGN_V2 가 `확인 근거` 를 사용자 라벨로 지정(§4.1). POC3-03 테스트의 `근거` 금지와 충돌 → 사용자 확인 후 제외("굳이 그럴 필요는 없는데 꼭 써야하면 써야죠"). V2 AC-19 사용자 금지어에 `근거` 없음. `후보` 는 유지.

## 5) AC 1~21 전수 대조 (실측 근거)

| AC | 판정 | 실측 근거 |
|---:|:---:|---|
| 1 | PASS | OCI·Telegram·PARAM·scheduler·approval 계약 무변경. ApprovalTelegramView 구조 불변(ManualPreviewSection 에 PUSH-2 버튼만 추가). |
| 2 | PASS | LeftSidebar manage 그룹 = 보유 현황→종목 관리→확인 근거→데이터 상태 순(L77~80 실측). |
| 3 | PASS | MenuKey union 11개 + ALL_MENU_KEYS 11개 + `assertMenuGroupsCover()` 로드 시 throw. LeftSidebar.test AC-2 "11개 1회 귀속" 통과. |
| 4 | PASS | `내가 가진 ETF` 부모·중복 메뉴 없음. 2단계 구조(L77~80). |
| 5 | PASS | HoldingsView(보유 현황)에 `holdings-table`·`<input>`·저장 버튼 0건(grep). EnrichedSection 평가 + 시세 갱신만. |
| 6 | PASS | HoldingsManageView 에 EnrichedSection·hre-table·초안 버튼 0건(grep). 입력·저장 전용. |
| 7 | PASS | 확인 근거 표: 평가액·비중·손익·5일·20일·KODEX200 대비·자료 상태 컬럼(HoldingsRiskEvidenceSection thead). |
| 8 | PASS | 확인 근거에 `HoldingsMarketEvidenceCard` import/JSX 0건(comment 만). 고유 정보는 선택 상세 `NavConstituentsDetail` 로 통합. |
| 9 | PASS | 확인 근거 표 ticker 통합 = `aggregateHoldingsByTicker` 재사용(helpers.ts). 종목 관리 저장 행은 원본 유지(합산 없음). |
| 10 | PASS | `computeNeedCheck`(helpers.ts) = §6.2 기준. missing·partial·unavailable 을 0/정상으로 대체 안 함(fmt* 는 null→"자료 확인 필요"). |
| 11 | PASS | `lowestFiveDayRows`(helpers.ts) = status ok & 5일 유효만 로컬 오름차순. DB·cache·rank·signal 저장 0. |
| 12 | PASS | 확인 근거 계열에 `topn_match`·`falling_candidate` 사용 0(helpers·Section 은 comment 만, 표 컬럼 없음). |
| 13 | PASS | Dashboard 보유 카드: `보유 현황 열기`→holdings / `확인 근거`→holdings_evidence. evidence 예외→holdings_evidence(§7). |
| 14 | PASS | Workbench·확인 근거·Dashboard 모두 `fetchEnrichedHoldings`/`fetchHoldingsMarketEvidence` + `aggregateHoldingsByTicker` 공유. 화면별 파생 산식 없음. |
| 15 | PASS | 확인 근거 목록에 ticker별 N+1 시계열 호출 없음. 선택 상세에서만 `PriceChart`(lazy) 1건. |
| 16 | PASS | `generateDraftFromHoldings` 운영 호출처 = ManualPreviewSection 단 1곳. Holdings 계열 0. |
| 17 | PASS | 신규 API·DB·source·factor·formula·threshold·scheduler·OCI·Telegram 변경 0. §3 의존성 0. |
| 18 | PASS | 신규 화면 전환 key = holdings_manage·holdings_evidence 2개뿐. 신규 최상위 그룹·URL 라우터 0. |
| 19 | PASS | 운영 화면에 `저위험/고위험/안전/매도/손절/BUY/SELL` 라벨·액션 0. grep hit 은 전부 "…아님" 중립 안내·comment. |
| 20 | PASS | tsc 0 · eslint 0 · vitest 123 passed. B·C 사용자 실화면 확인 통과. |
| 21 | PASS | 4화면 분리로 보유 평가(보유 현황)·종목 수정(종목 관리)·확인 근거를 좌측 메뉴에서 1회 선택. 사용자 실화면 확인 C 통과. |

AC 1~21 **전부 PASS**.

## 6) 다음 검증자(Codex)에게 알릴 점

- **AC-7 `근거` 금지어 제외 (B 섹션 우선 검토 요망)**: POC3-03 테스트가 메뉴 텍스트에 `근거` 를 금지했으나 DESIGN_V2 §4.1 이 `확인 근거` 를 사용자 라벨로 지정. 사용자 확인 후 `TodayInvestmentCheckView.test` FORBIDDEN_TERMS 에서 `근거` 제거(`후보` 유지). V2 AC-19 사용자 금지어에 `근거` 없음 — 계약 훼손 아님으로 판단.
- **고아 컴포넌트 이동**: `HoldingsClient.tsx`·`HoldingsMarketEvidenceCard.tsx` 를 `_orphaned/` 로 git mv. 운영 경로에서 import 0(grep). tsc/eslint/vitest 통과. 삭제는 사용자 방침상 추후.
- **선택 상세 NAV·구성종목**: `NavConstituentsDetail`(HoldingsRiskEvidenceSection) 이 기존 HoldingsMarketEvidenceCard 의 NAV·괴리율·구성종목 표시 의미를 재사용. constituents status 는 `ok` 만 available(타입상 `partial` 없음 — tsc 로 확인).
- **초안 버튼 이동의 자동 전환**: Q4 확정대로 MainPanel 초안→approval 자동 전환 제거. 초안은 OCI 화면 안에서 실행되어 그 화면에 머문다.

## 7) 사용자 확인이 필요한 항목

- **미커밋 무관 파일**: `design/DESIGN-apple.md`·`docs.zip` 은 POC3-05 무관 잡파일로 커밋 제외. 처리 필요 시 별도 지시.
- **push 미실행**: 규칙상 push 별도 승인. 현재 미push 커밋 다수 — push 시 실측 후 개수 명시 예정.
- **[설계자 전달] krx 그리드 디자인 개선**: 사용자가 2026-08-02 지적 — krx 그리드(테이블) 완성도가 사용자 자체 제작 화면(안티그래비티) 대비 낮음. 사용자 지시로 **이번 Step 에 넣지 않고 설계자에게 다음 개선 후보로 전달**. (Closeout 시 통합지도/다음 게이트 제안에 포함.)

문서 끝.
