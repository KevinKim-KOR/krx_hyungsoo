# POC3-03 Navigation Information Architecture v1 — 개발 PLAN

* 문서 종류: 개발 PLAN (모호점 질문 포함 · 설계자 회신용)
* 대응 설계서: `docs/ai_design/POC3/POC3-03_..._DESIGN_V1.md` (설계자 제공, 사용자 배치 예정)
* 작성일: 2026-08-01
* 기준 revision: `3345d504` (선행 POC3-REF-02 VERIFIED / CLOSED)
* 상태: **개발 PLAN 확정 (설계자 Q1~Q6 답변 + 보완 3사항 반영, 2026-08-01).** 개발 착수 가능 · BLOCKED 없음.
* 성격: 순수 Navigation Step. 신규 API·DB·source·산식·화면·화면 전환 key 없음(설계서 §9).

---

## 0. 기반 문서 확인 완료

- `PROJECT_ORIGIN_INTENT` 목적 / `KILL_SWITCHES` / `STATE_LATEST`(= POC3-REF-02 CLOSED · next_gate POC3-03) 확인.
- 이번 Step은 데이터 작업 없음 → 데이터 선행 소Step 만들지 않음(설계서 §0).
- POC3-02 Workbench 재개발·benchmark 시계열(P-16) 미착수 유지.

---

## 1. 개발 전 사실 확인 결과 (설계서 §7 — 실측 완료)

### 1.1 현재 MenuKey 전체(9개) · MainPanel 화면 분기 [확인]
`frontend/app/components/LeftSidebar.tsx` `MenuKey` + `MainPanel.tsx` switch 실측:

| # | MenuKey | 현재 라벨(LeftSidebar) | MainPanel 분기 컴포넌트 |
|---|---|---|---|
| 1 | `today_check` | 오늘의 투자 점검 | `TodayInvestmentCheckView` (기본 진입) |
| 2 | `dashboard` | 기존 대시보드 | `DashboardView` |
| 3 | `workbench` | ETF 비교하기 | `JudgmentWorkbenchView` |
| 4 | `market_discovery` | 요즘 잘 오르는 ETF | `MarketDiscoveryView` |
| 5 | `etf_exposure` | ETF 구성종목 | `ETFExposureView` |
| 6 | `ai_sessions` | AI 투자 세션 | `AISessionsView` |
| 7 | `holdings` | 내가 가진 ETF | `HoldingsView` |
| 8 | `approval` | 승인 / 알림 | `ApprovalTelegramView` |
| 9 | `data_status` | 데이터 상태 | `DataStatusView` |

- **9개 화면 전환 key = 설계서 §3.2의 9개 메뉴와 정확히 1:1** (중복·누락·신규 key 없음). 설계서에 없는 메뉴 없음 → BLOCKED 사유 없음.

### 1.2 최초 진입 기본 key [확인]
`MainPanel.tsx:31` `useState<MenuKey>("today_check")` → 기본 진입 = `today_check`. (설계서 §3.3·§4.1과 일치)

### 1.3 프로그램 방식 화면 이동(onNavigate/setActive) [확인]
- **MenuKey 간 이동 = `onNavigate(key)`** (MainPanel의 `setActive` 주입). 실측 호출:
  - `TodayInvestmentCheckView`: → `workbench`(L432) · 정비항목 `it.target`(L561, 동적: `market_discovery`/`etf_exposure`)
  - `DashboardView`: → `market_discovery`(L308) · `holdings`(L447) · `ex.action`(L562, 동적)
  - `JudgmentWorkbenchView`: → `market_discovery`(L243·L773) · `holdings`(L250) · `etf_exposure`(L766) · `r.action`(L662, 동적)
  - `ETFExposureView`: → `ai_sessions`(L202) · `TransferToAISessionsCard`(→`ai_sessions`)
  - `MarketDiscoveryView` / `TransferToETFExposureCard`(→`etf_exposure`) / `TransferToAISessionsCard`(→`ai_sessions`)
  - `MainPanel.handleDraftCreated`: draft 생성 시 자동 → `approval`(L39)
- **주의(구분 필요)**: `AISessionsView`의 `setActive("create"/"list")`, `ETFExposureView`의 `setActive("constituents"/"overlap")`는 **화면 내부 탭 상태**이지 MenuKey 이동이 아니다 → 그룹 재편과 무관(건드리지 않음).

### 1.4 좌측 메뉴 테스트 · CSS [확인]
- **LeftSidebar/MainPanel 전용 테스트 없음.** 좌측 메뉴 관련 검사는 `TodayInvestmentCheckView.test.tsx`가 View+Sidebar 금지어(AC-7)를 스캔하는 수준.
- CSS: `frontend/app/globals.css` L697~776. `.app-shell`(flex) · `.app-sidebar`(width 220px 고정·sticky) · `.sidebar-menu`(평면 `<ul>`) · `.sidebar-menu-btn`(flex-column: label+hint) · `.sidebar-menu li.active`(배경+좌측 border+accent). **현재 그룹 구조·접힘 없음.**

### 1.5 9개 화면 → 4그룹 1:1 귀속 [확인]
설계서 §3.2 매핑을 실제 key로 해석:

| 그룹(노출 문구) | 메뉴명(노출) | key |
|---|---|---|
| 오늘 확인 | 오늘의 투자 점검 | `today_check` |
| 비교·판단 | ETF 비교하기 | `workbench` |
| 비교·판단 | 요즘 잘 오르는 ETF | `market_discovery` |
| 비교·판단 | ETF 구성종목 | `etf_exposure` |
| 비교·판단 | AI 투자 세션 | `ai_sessions` |
| 보유·자료 관리 | 내가 가진 ETF | `holdings` |
| 보유·자료 관리 | 데이터 상태 | `data_status` |
| 보유·자료 관리 | 기존 대시보드 | `dashboard` |
| 승인·운영 | 승인 / 알림 | `approval` |

→ 9 key가 4그룹에 **정확히 1회씩** 귀속. 중복·고아 0.

---

## 2. 구현 방침 (설계서 확정 사항 반영 · 초안)

> 아래는 답변 확정 시 진행할 방향. 모호점(§3) 답변에 따라 조정.

1. **`LeftSidebar.tsx`**: 평면 `MENU_ITEMS`를 4그룹 구조(`MENU_GROUPS`: 그룹명 + 소속 MenuItem[])로 재편. `MenuKey`·key 문자열 불변. 그룹 제목(접힘 토글)·소속 메뉴 렌더. 접힘 상태는 `LeftSidebar` 내부 `useState`(세션 UI 상태만, 저장 없음 — §4.2·AC-9).
2. **자동 펼침(§4.3·AC-5)**: `active` key가 접힌 그룹에 속하면 그 그룹을 자동으로 펼쳐 선택 메뉴가 항상 보이게. `active` 변화 감지(`useEffect` 또는 파생 상태). 다른 그룹의 사용자 접힘 상태는 유지.
3. **`MainPanel.tsx`**: switch 분기·`setActive`·`onNavigate` 주입·기본 `today_check`·draft→approval 자동전환 **전부 불변**. 그룹 개념은 LeftSidebar 표현 계층에만.
4. **`globals.css`**: 그룹 제목/메뉴 정보 계층 구분(§6). 사이드바 폭 220px·전체 레이아웃 유지. 신규 아이콘/디자인 시스템 없음. 접힘 표시(예: ▸/▾ 텍스트) 추가.
5. **테스트(AC 자동 검증)**: LeftSidebar 신규 테스트 — (a) 4그룹 렌더 (b) 9 key 1회 귀속·중복/누락 0 (c) 기본 active=today_check (d) active↔활성표시 일치 (e) 접힌 그룹으로 이동 시 자동 펼침 (f) 그룹 토글이 onSelect(화면전환) 호출 안 함 (g) AC-7 금지어(Workbench/Market Discovery/Holdings/ETF Exposure/Data Status/Operations Panel) 비노출.

---

## 3. 설계서 모호점 — 설계자 확인 질문

> 아래는 자체 추측으로 진행하지 않고 설계자 답변을 받아야 하는 항목이다. (a)/(b) 중 택일 또는 보완 요청.

### Q1. "승인·운영" 그룹명 vs "승인 / 알림" 메뉴명, 그리고 현재 라벨 표기
- 설계서 §3.1 그룹 순서는 **"승인·운영"**, §3.2 표의 메뉴명은 **"승인·알림"**. 실제 현재 라벨은 **"승인 / 알림"**(슬래시).
- **질문**: (a) 그룹명 = "승인·운영", 메뉴명 = "승인·알림"으로 **라벨을 변경**한다 / (b) 메뉴명은 현재 "승인 / 알림" 유지, 그룹명만 "승인·운영" 추가. → **AC-14는 "승인·알림"으로 이동 가능해야 한다고 명시**하므로 라벨 문구를 "승인·알림"으로 통일할지 확정 필요.

### Q2. "기존 대시보드"의 그룹 귀속
- §3.2 표에서 "기존 대시보드"는 **보유·자료 관리** 그룹에 있으나, §3.3은 "기존 대시보드를 일상 진입 흐름의 중심으로 다시 올리지 않는다"고만 함.
- **질문**: "기존 대시보드"를 **보유·자료 관리 그룹의 마지막 메뉴**로 두는 것이 맞는가? (그룹 내 표시 순서: 내가 가진 ETF → 데이터 상태 → 기존 대시보드 로 추정 — 맞는지 확인)

### Q3. 그룹 내 메뉴 표시 순서
- 설계서는 그룹 순서(§3.1)와 귀속(§3.2)은 정하나, **각 그룹 안 메뉴의 나열 순서**는 "ETF 비교하기가 비교·판단 첫 번째"(§3.3)만 명시.
- **질문**: 나머지 순서를 아래로 확정해도 되는가?
  - 비교·판단: ETF 비교하기 → 요즘 잘 오르는 ETF → ETF 구성종목 → AI 투자 세션
  - 보유·자료 관리: 내가 가진 ETF → 데이터 상태 → 기존 대시보드
  - (오늘 확인·승인·운영은 각 1개라 순서 무관)

### Q4. 그룹 제목 클릭의 접힘 vs 이동 (AC 명시와 §4.2)
- §4.2 "그룹 제목 자체는 화면으로 이동하지 않는다"는 명확. 단 접근성(키보드·aria) 처리 방식은 미지정.
- **질문**: 그룹 제목을 `<button aria-expanded>`(접힘 토글 전용, role=button)로 구현하면 되는가? (메뉴 이동 버튼과 시각·동작 구분) — 별도 지시 없으면 이 방식으로 진행.

### Q5. 접힘 상태 표시 방식(§6 "접힘을 알 수 있는 표시")
- §6은 "그룹 제목에 접힘 상태 표시" 요구, §9는 "신규 아이콘 체계 도입 금지".
- **질문**: 아이콘 라이브러리 없이 **텍스트 기호(▸ 접힘 / ▾ 펼침)** 또는 CSS로 그린 삼각형으로 표시하면 되는가? (신규 아이콘 체계 아님으로 간주) — 이 방식으로 진행 예정.

### Q6. "승인·운영" 그룹에 approval 1개만 — Operations Panel 자리
- §3.2에서 "승인·운영" 그룹에는 현재 `approval`(승인·알림) 1개만 귀속. Operations Panel(P-05)은 이번 Step 미구현(§9).
- **질문**: 이번 Step에서 "승인·운영" 그룹은 **메뉴 1개(승인·알림)만** 두면 되는가? (그룹은 만들되 이후 Operations Panel이 붙을 자리 — 빈 그룹 아님, 확인)

---

## 4. 개발 완료 후 산출물(예정)

- 수정: `LeftSidebar.tsx`(그룹 구조) · `MainPanel.tsx`(변경 최소 — 필요 시만) · `globals.css`(그룹 스타일) · 신규 `LeftSidebar.test.tsx`.
- 백엔드·API·DB·화면 전환 key·데이터 계약 **무변경**.
- 결과서: `docs/ai_result/POC3/POC3-03_..._RESULT.md`.

---

## 5. 설계자 답변 (2026-08-01 확정)

| 질문 | 확정 답변 |
|---|---|
| Q1 라벨 | **(a)** 그룹명 = `승인·운영`, 메뉴명 = `승인·알림`. 현재 `승인 / 알림`의 공백·슬래시 표기만 변경. `approval` key·기능 불변. |
| Q2 기존 대시보드 | (설계자 답변) 보유·자료 관리 그룹의 **마지막**. **→ 이후 사용자 실화면 지시(2026-08-01)로 "점검대상" 그룹으로 분리** — 결과서 §4 참조. UI 최종 판단은 사용자. |
| Q3 그룹 내 순서 | 비교·판단: ETF 비교하기 → 요즘 잘 오르는 ETF → ETF 구성종목 → AI 투자 세션 / 보유·자료 관리: 내가 가진 ETF → 데이터 상태 → 기존 대시보드. |
| Q4 그룹 제목 | `<button type="button" aria-expanded>`. 접기·펼치기만, 화면 이동·`onSelect` 발생 금지. |
| Q5 접힘 표시 | `▸/▾` 또는 CSS 삼각형 허용. 외부 아이콘 라이브러리 금지. 방식은 개발자 선택 → **텍스트 기호 `▸/▾` 채택**. |
| Q6 승인·운영 | `승인·알림` 메뉴 1개만. Operations Panel 메뉴·자리표시자·`개발 중` 문구 추가 금지. |

> Q4·Q5는 동일 계약 내 구현 세부 → 이후 별도 설계자 확인 없이 개발자 판단 가능(설계자 명시).

## 6. 보완 필수사항 (설계자 지시 · AC 직결)

1. **최초 진입 시 네 그룹 모두 펼쳐진 상태** — 테스트 포함 (§4.1·AC 신규).
2. **현재 메뉴 + 그 메뉴가 속한 그룹도 활성 식별** — 그룹 활성 표시 (§6·AC 신규).
3. **접힌 그룹으로 내부 이동해 자동 펼침 시, 다른 그룹의 접힘 상태는 유지** — 테스트 포함 (§4.3·AC-5).
4. **`today_check` 기본값은 `MainPanel` 책임** — LeftSidebar 컴포넌트 계약을 억지로 바꿔 검사하지 말 것. 최초 화면 동작 기준으로 확인 (설계자 명시).

## 7. 확정 — 개발 착수

Q1~Q6 + 보완 4항 반영으로 **추가 질문 없이 개발 착수.** 설계서에 없는 메뉴·유지 불가 key 없음 → BLOCKED 없음. §2 구현 방침에 위 답변·보완을 병합해 진행.
