# POC3-01 오늘의 투자 점검 대시보드 — 개발 결과서

* 문서 종류: 개발 결과서 (검증자 입력)
* 작성일: 2026-07-29 (초안) / r1~r8 / r9 / r10 검증자 REJECTED 수정 (AC-7 툴팁·보고정확성·B-1·테스트) / **2026-08-01 사용자 실화면 확인 완료 (AC-15 충족)**
* 상태: **COMPLETED / VERIFIED** — 검증자 자동 게이트(vitest 82 passed·tsc·eslint) + **사용자 실화면 확인 완료 (2026-08-01, AC-15 충족)**. 개발자 몫 종료.
* 작업명: **POC3-01** (사용자 확정 2026-07-29 — 명명 문제 해소)

---

## 0. 검증 대상 문서 (검증자는 이 3종을 대조한다)

| 종류 | 경로 | 무엇을 담나 |
|---|---|---|
| **설계서** | `docs/ai_design/POC3/POC3-01_TODAY_INVESTMENT_CHECK_DASHBOARD_REDESIGN_DESIGN_V1.md` | 설계자 입력 — 무엇을 만들어야 하는가 (§4 화면 계약 · §12 AC-1~15) |
| **개발계획서** | `docs/ai_plan/POC3/POC3-01_TODAY_INVESTMENT_CHECK_DASHBOARD_REDESIGN_PLAN_V1.md` | 데이터 실측 + Q1~Q9 설계자 판정 — 어떻게 만들기로 했는가 |
| **개발 결과서** | 본 문서 | 실제로 무엇을 만들었는가 + 설계서 AC / 개발계획 항목 1:1 대조 |

> 검증 흐름: 설계서 요구 → 개발계획 확정(실측·판정) → 본 결과서(실제 결과)를 순서대로 대조.

---

## 1. 검증자 r1 REJECTED 지적 → 조치

| # | 지적 | 조치 | 파일 | 상태 |
|---|------|------|------|------|
| A-1(1) AC-1 | 첫 1440×900 화면에 시장 카드만 보이고 판단·정비 큐가 아래로 밀림 | 상단 2열 grid 로 재구성 — 좌: 코스피 헤드라인(compact), 우: 판단 큐 + 정비 큐. 코스피 상세(개발 중 항목)·개발 중 기능은 아래로 이동. `.tc-top-grid` | TodayInvestmentCheckView.tsx · globals.css | ✅ |
| A-1(2) AC-7 | 좌측 메뉴에 Judgment Workbench/Market Discovery/ETF Exposure/Holdings 등 내부 용어 노출 | 설계서 §7 매핑을 좌측 메뉴 라벨에 적용 (요즘 잘 오르는 ETF / 내가 가진 ETF / ETF 비교하기 / ETF 구성종목 / AI 투자 세션 / 승인·알림 / 데이터 상태). key(라우팅)는 불변 | LeftSidebar.tsx | ✅ |
| A-1(3) Q7 | 갱신 성공 후 캐시만 삭제하고 reload() 미호출 → 활성 화면이 재조회하지 않고 loading 갇힘 | invalidateQueries 후 관련 query 의 `reload()` 를 직접 호출 (holdings·evidence). Dashboard 의 검증된 패턴과 동일 | TodayInvestmentCheckView.tsx | ✅ |
| A-1(4) §4.3 | 갱신 후 완료/실패만 표시, "마지막 정상 완료 시각" 누락 | 정비 큐에 마지막 정상 완료 시각 표시(성공 시 기록·KST). 없으면 "이번 세션에서 아직 없음" 명시 | TodayInvestmentCheckView.tsx | ✅ |
| A-1(5) AC-11 | MA20/60 한계 설명이 hover 툴팁이 아니라 항상 노출 `<p>` · title 없음 | `ⓘ 이 값의 한계` 마커 + `title`/`aria-label` hover 툴팁으로 전환. 거래량 미저장 설명도 동일 패턴 | TodayInvestmentCheckView.tsx · globals.css | ✅ |
| B-1 | MA 거리 결측을 `-` 로 표시 (0/정상 위장 우려) | 결측 시 "KODEX200 MA20 대비 자료 없음" 으로 정직 표시 | today/todayHelpers.ts | ✅ |
| B-6 | UI 테스트가 새 View 본문만 렌더해 Sidebar 용어 위반·갱신 GET 재호출을 놓침 | (1) LeftSidebar 실제 렌더 후 내부 용어 부재 검증 (2) MENU_ITEMS 라벨 라틴 용어 검증 (3) 갱신 후 관련 GET 재호출 검증 (4) 마지막 완료 시각 검증 (5) MA 툴팁 title 검증 (6) MA 결측 문구 검증 | TodayInvestmentCheckView.test.tsx | ✅ |
| A-2 | §4.3/§7/§8 을 DONE 으로 보고했으나 실제와 불일치 | 위 조치로 실제 구현을 계약에 맞춤. 본 결과서에서 상태 재보고 | — | ✅ |
| B-5 | 신규 산출물 untracked → 커밋·배포 미포함 | 커밋 시점에 `git add --untracked-files=all`. 커밋 여부는 사용자 확정(이 작업과 묶음) — 아래 §5 | — | 대기 |
| **A-3** | 이번 작업이 POC3-01 로 재명명되어 canonical 진행 상태(MASTER_PLAN=First Real Decision Cycle 활성 · STATE_LATEST=POC3-02 검증대기)와 불일치 | **개발자 판단 아님 — 설계/상태 앵커 명명은 설계자·사용자 영역.** 사용자에게 상신 (아래 §4) | — | 상신 |

---

## 1-2. 검증자 r2 REJECTED 지적 → 조치

| # | 지적 | 조치 | 파일 | 상태 |
|---|------|------|------|------|
| 사용자 | "오늘의 투자 점검" 화면 가로 폭이 다른 메뉴 화면과 다름 | `.tc-root` 의 `max-width:1000px` 제거 → 다른 화면과 동일하게 `.app-content`(1400px) 폭 사용. 코스피 대표 영역도 넉넉한 폭 확보(§4.1) | globals.css | ✅ |
| A-1(1) AC-7 | 좌측 메뉴 **hint** 에 금지 용어 `후보` 노출 | 모든 hint 에서 금지 용어 제거 ("관심·보유 ETF 한 화면 비교" 등). 테스트가 label+hint 전체 검사 | LeftSidebar.tsx | ✅ |
| A-1(2) AC-1 | 정비 항목 총 건수 미표시 → "몇 건" 즉답 불가 | 정비 큐 제목에 총 건수 배지(`N건`) 표시 | TodayInvestmentCheckView.tsx | ✅ |
| A-1(3) §4.1 | 코스피 대표가 2열 중 왼쪽 499px 만 사용 | 위 폭 정정으로 좌측 열이 넓어짐(1400px 기준 grid 1.15fr) | globals.css | ✅ |
| A-1(4) B-1 | reload() 결과를 안 기다리고 즉시 완료·시각 기록 → GET 실패해도 완료 | `reloadAsync()` 신설(promise 반환) · `Promise.all` await 후 **성공 시에만** 완료·시각 기록. 실패 시 "실패" | queryCache.ts · TodayInvestmentCheckView.tsx | ✅ |
| A-1(5) B-1 | 기준일 결측을 `-` 로 표시 | `fmtKstDate` 결측 반환을 "자료 없음" 으로 변경 (call site 안전 확인) | today/todayHelpers.ts | ✅ |
| B-6 | 테스트가 label 만 검사·재조회 실패 미탐지 | (1) label+hint 금지 용어 검사 (2) 재조회 실패 시 "완료" 미표시 검사 (3) 정비 건수 검사 추가 | TodayInvestmentCheckView.test.tsx | ✅ |
| A-2/B-5 | 변경 파일 수 보고 부정확 · untracked | 아래 §3-2 에 실측 재보고 | — | ✅ |

## 1-3. 검증자 r3 REJECTED + 사용자 레이아웃 요청 → 조치

**r3 핵심 원인(개발자 자인)**: r1 의 "첫 화면에 큐가 안 보임(AC-1)" 을 해결하려고 코스피를 **왼쪽 반쪽**으로 줄이고 오른쪽에 큐를 붙이는 2열로 만든 것이 **설계서 §4.1 "코스피 대표 = 최상단 전체 폭" 및 사용자 "가로로 제일 길게" 요청을 위반**. 한 AC 를 맞추려다 더 중요한 계약을 깬 잘못된 트레이드오프.

| # | 지적/요청 | 조치 | 상태 |
|---|------|------|------|
| A-1 §4.1 | 코스피 대표가 grid 52.5% 만 사용 (반쪽) | **코스피 = 최상단 전체 폭** 카드로 복원. 그 아래에 판단 큐 + 정비 큐를 2열(`.tc-queue-grid`)로 → 첫 화면에 세 영역 모두 노출(AC-1 도 충족). 헤드라인 내부는 차트(좌·넓게) + 통계 패널(우) | ✅ |
| 사용자 1 | 부제 괄호 안내 작은 글씨 | 부제를 `.tc-subnote`(13px)로 | ✅ |
| 사용자 2 | 코스피 상세 지표 한 줄로 | 개발 중 항목을 `.tc-dev-row` 가로 나열 | ✅ |
| 사용자 3 | "코스피는 지금 어디쯤인가" 문구 → KOSPI | 대표 제목을 **`KOSPI`** 로. aria-label "KOSPI 현재 위치" | ✅ |
| 사용자 4 | 친구처럼 자세한 정보 | **범위 확인 후 진행**: 친구 화면의 지속일·전고점·공격방어비중·SuperTrend·거래량은 설계서 §11 금지 / Q3·Q5 개발 중 확정 항목. **사용자 "설계 범위 유지" 확정** → 저장값만으로 밀도 향상: 코스피 **기간 수익률 1M/3M**(기존 `market_context.kospi` 재사용) 헤드라인 추가. 금지 항목은 개발 중 유지 | ✅ |

**친구 화면 vs 이번 Step 경계 (사용자 확정 "설계 범위 유지")**:
- 넣음: 코스피 차트(전체 폭)·현재가·기간 수익률 1M/3M·KODEX200 국면(별도)·MA20/60 거리.
- 개발 중 유지: 흐름 지속 거래일 수·전고점 대비·거래량 (Q3/Q5).
- **이번 Step 미도입(설계 §11 금지)**: 공격/방어 비중·SuperTrend 전환선. → 후속 `내가 가진 ETF 위험 신호` Step 또는 별도 설계에서만.

## 1-4. 사용자 직접 지시 4건 (r4 · 검증자 참고) — 설계서 외 사용자 명시 요청

> 아래는 설계자 지시문이 아니라 **사용자(Hyungsoo)의 직접 지시**로 수정한 항목이다. 검증자는 이 부분이 사용자 요청대로 반영됐는지 함께 확인 바람.

| # | 사용자 지시 | 조치 | 파일/위치 |
|---|------|------|------|
| U-1 | 코스피 상세 지표를 KOSPI 헤드라인 위/함께 올라가게 (순서) | 컨테이너 순서를 **KOSPI 헤드라인 → 코스피 상세 지표 → (판단·정비 큐 2열) → 개발 board** 로. 코스피 정보가 상단에 모임 | TodayInvestmentCheckView.tsx 컨테이너 render |
| U-2 | KOSPI 에서 이번 Step 에 **안 되는 것을 전부 기록** | 코스피 상세 지표 board 에 지속일·전고점·**일간 등락률·1년 수익률**(개발 중) + **거래량·공격/방어 비중·SuperTrend**(이번 단계 미도입) 전부 명시 + 각 사유 hover 툴팁 | `KospiDetailSection` / `KOSPI_IN_DEV`·`KOSPI_NOT_IN_STEP` |
| U-3 | 자료 업데이트 필요를 **바로 갱신 vs 상세 페이지 이동** 으로 분리 (설계 §4.3) | 정비 큐를 `여기서 바로 해결`(light · 지금 다시 불러오기) / `상세 화면에서 업데이트`(heavy · 항목별 이동) 2그룹으로 분리. 각 항목에 `kind: light/heavy` | `collectMaintenance` + `MaintenanceQueueSection` |
| U-4 | 개발 중 판단 기능 카드를 **빠진 기능 전체 board** 로 | `InDevelopmentSection` 을 `준비 중(앞으로 추가)` + `이번 단계 미도입(후속·별도 설계)` 두 부류 board 로 확장. 위험 신호·전환 거리·지속일/전고점·일간/1년·거래량·공격방어·SuperTrend 모두 기록 | `InDevelopmentSection` / `DEV_IN_PROGRESS`·`DEV_NOT_IN_STEP` |

**배지 구분**: `개발 중`(회색 · 앞으로 이 화면에 추가) vs `이번 단계 미도입`(점선 · 설계 §11 금지 또는 후속 Step). 사용자가 "무엇이 왜 아직 없는지" 를 화면에서 직접 보게 함.

## 1-5. 검증자 r5 REJECTED → 조치

| # | 지적 | 조치 | 상태 |
|---|------|------|------|
| A-1 | NAV 를 "여기서 바로 해결"(light)로 분류했으나 갱신 시 Holdings·Evidence 만 재조회, **NAV 미재조회** → 캐시 그대로인데 완료 표시 | `onLightRefresh` 에 `nav.reloadAsync()` 추가. light 3소스(Holdings·Evidence·NAV) 모두 await → 계약과 동작 일치. `void holdings` 죽은 주석 정리 | ✅ |
| A-2 | 변경 파일 수 부정확 (20/19 보고) | 실측 재보고 §3-2: **M13+R1+D3+??8=25 · 개발산출물 24** | ✅ |
| A-3 | "stale 참조 전수 정정" 과장 (과거 POC2 문서 2건이 옛 경로 참조) | §6 정정: 활성 문서만 정정 · 과거 기록은 사용자 (가) 결정으로 의도적 보존 | ✅ |
| B-5 | `git add --untracked-files=all` 은 잘못된 플래그(`git status` 전용) | §5 정정: `git add -A` 사용 안내 | ✅ |
| B-6 | 갱신 테스트가 NAV 재조회 미검증 | 테스트 추가: light 3소스 재조회 검증 + NAV 재조회 실패 시 거짓 완료 금지 검증 | ✅ |

## 1-6. 사용자 실화면 UI 오류 2건 (r6 · 실화면 확인 중 발견)

> 검증자 VERIFIED_WITH_NOTES(r5) 이후 **사용자 실화면 확인**에서 발견한 UI 오류. 기능 오류 아님(사용자 명시) · 표시/상호작용 문제.

| # | 오류 | 원인 | 조치 |
|---|------|------|------|
| UI-1 | "지금 다시 불러오기" 버튼이 2개 동시 동작 | 상단 전역 refresh 버튼 + "여기서 바로 해결" 그룹의 항목별 버튼이 같은 `onLightRefresh` 호출 → 중복 | 전역 refresh-row 제거. 경량 갱신 버튼을 **light 그룹 헤더에 1개만** 배치. 항목은 텍스트만 나열 |
| UI-2 | 갱신 완료 후에도 문구가 "불러오는 중..." 유지 | (주원인) dev `.next` 캐시 겹침으로 옛 JS 서빙 + 상태 문구가 버튼과 분리돼 있던 구조 | 버튼 라벨 자체가 `불러오는 중.../지금 다시 불러오기` 로 전환 + 상태 문구(완료/실패)를 그룹 헤더에 통합. 테스트로 "완료 표시 + 버튼 재활성" 고정 |

**테스트 추가**: (1) "지금 다시 불러오기" 버튼 **정확히 1개** 검증 (2) 갱신 완료 후 "완료" 표시 + 버튼 재활성 검증.

> UI-2 는 실제로는 dev 서버 stale 캐시 영향이 컸다(코드 상태 전이는 정상). 재기동 후 재확인 권장. 구조 개선(버튼 1개 + 라벨 전환)으로 표시 혼동 자체를 제거했다.

## 1-7. 사용자 실화면 정비 큐 UI 6건 + 분류 버그 (r7)

> 사용자 실화면 확인에서 나온 정비 큐("자료 최신화 필요") 개선 5건 + **분류 버그 1건**. 특히 마지막은 계약·동작 불일치(진짜 버그).

| # | 사용자 지시/발견 | 조치 |
|---|------|------|
| 1 | "자료 업데이트 필요" → "자료 최신화 필요" | 제목·aria-label·빈 상태 문구 변경 |
| 2 | "여기서 바로 해결" 문구 삭제 | 라벨 제거 |
| 3 | 갱신 버튼을 제목 옆으로 | 버튼을 제목 행(`tc-maint-title-row`)에 1개 배치 |
| 4 | 항목을 하단에 배치 | light 항목을 버튼 아래 목록으로 |
| 5 | 건수 정합 | 총 건수 = light+heavy 실제 합 반영 |
| **6** | **갱신 후에도 "…비교 자료가 오래되었습니다" 문구가 안 사라짐 (버그)** | **원인**: evidence stale·NAV 를 light(경량 갱신으로 해소)로 분류했으나 `POST /holdings/market/refresh` 는 **현재가만** 갱신 → 그 항목들은 안 사라짐. **조치**(사용자 "evidence·NAV heavy 재분류" 확정): light = 보유 종목 **현재가 결측**(refresh 로 실제 해소)만. evidence stale·NAV·구성종목·VIX 는 전부 **heavy**(상세 화면 이동). 갱신 후 현재가 결측이 해소되면 light 항목이 실제로 목록에서 사라짐 |

**부수 개선**: 완료/실패 상태 문구를 light 항목 유무와 무관하게 유지(갱신으로 light 항목이 0이 돼도 "완료" 피드백 보임).

**테스트 추가**: (1) 갱신으로 현재가 결측 해소 시 light 항목 사라짐 (2) evidence/NAV 는 heavy(상세 이동)·경량 버튼 없음 (3) 버튼 1개·완료 문구 전환.

**light/heavy 최종 계약**: light(지금 다시 불러오기) = 보유 현재가 결측만. heavy(상세 화면 이동) = evidence stale·NAV 미연동·구성종목 미수집·VIX stale.

**갱신 버튼 표시 (사용자 확정 2026-07-30 "항상 보이되 상황별 상태")**: "지금 다시 불러오기" 버튼은 light 항목 유무와 무관하게 **항상 표시**. 현재가 결측이 없으면 "보유 현재가는 최신 상태입니다" 힌트, 누르면 "완료 · 현재가는 최신 상태입니다". 버튼이 나타났다 사라지는 깜빡임 제거.

## 1-8. 정비 큐 UI 통일 3건 (r8 · 사용자 실화면 지시)

| # | 지시 | 조치 |
|---|------|------|
| 1 | 제목과 그룹 라벨 글자 크기 통일 | 그룹 라벨(`상세 화면에서 업데이트`·`보유 현재가`)을 제목급 20px(`tc-maint-group-label`)로 |
| 2 | 경량 갱신을 항목 행으로 통일 + "업데이트" 문구 | 상단 별도 버튼 제거. 경량 갱신도 heavy 와 동일 "문구 + 우측 `업데이트` 버튼" 행. 완료/실패/마지막 시각은 그룹 상태줄(항목 문구 15px)에 |
| 3 | 최신이면 파란 배지 "최신" | 보유 현재가 결측 0건이면 제목 옆 파란 박스·흰 글자 `최신` 배지(`tc-fresh-badge`) |

**테스트 갱신**: 버튼명 "업데이트"·상태줄·최신 배지 반영. 79 passed 유지.

## 1-9. 정비 큐 실화면 UI 정리 (r9 · 사용자 지시) — 이후 정비큐 세부는 설계 이관

> r8 이후 사용자 실화면 확인에서 나온 정리 지시들. **정비 큐의 "제대로 된 정의(문구·판정 근거·ⓘ 표준)"는 사용자 확정으로 후속 설계 대상**. r9 는 그 전까지의 실화면 정리 + ⓘ 근거 임시 문구.

| # | 사용자 요청 | 어떻게 개발했는지 (조치) |
|---|------|------|
| r9-1 | "보유 현재가" 라벨·상태줄 삭제, light 를 heavy 와 같은 행 형태로 | 그룹 라벨·별도 상태줄(`이번 세션에서 아직 없음` 포함) 전부 제거. 모든 항목을 단일 `tc-maint-list` 안의 동일 행(`문구 + ⓘ + 우측 버튼`)으로 통일 |
| r9-2 | "최신" 배지를 문구 옆으로 | 제목 옆이 아니라 `보유 종목 현재가는 최신 상태입니다` 문구 **앞**에 파란 `최신` 배지 |
| r9-3 | 각 항목에 ⓘ 근거(무엇과 무엇을 비교해 최신이 아닌지) | `MaintenanceItem.reason` 필드 신설 + `MaintInfo` ⓘ 컴포넌트(hover 툴팁). **실제 값 기반 문구**: VIX=기준일 비교(VIX asof < 시장 asof) · 구성종목=수집 안 됨 · 시장비교=보유 ETF 시장위치 재계산 필요 · 기준가=NAV vs 시장가 괴리. 임시 숫자 없음(AC-9) |
| r9-4 | 보유 현재가 행에 ⓘ 없음 (통일 깨짐) | "최신 상태입니다" 행에도 ⓘ 추가 — 다른 항목과 통일 |
| r9-5 | "완료" 가 안 사라짐 | `refreshing` done/failed 를 **3초 뒤 자동 idle 복귀**(`REFRESH_FEEDBACK_MS`). "· 완료"/"· 실패" 잠깐 보여주고 사라짐 |

**판정 근거 표준은 임시**: 위 ⓘ 문구는 실제 값 기반이나 **정식 판정 기준(며칠 지나면 오래됨 등)은 이번 Step 범위 밖 · 후속 설계 대상**(사용자 2026-07-31 확정). 신규 신선도 산식은 만들지 않음.

**검증(r9)**: vitest **82 passed** (신규 View 30 + 기존 52) · tsc 0 · eslint 0. dev 서버 실측 HTTP 200(캐시 정상 · 재기동 불필요).

## 1-10. 검증자 REJECTED → 조치 (r10)

| # | 지적 | 조치 |
|---|------|------|
| A-1 AC-7 | r9 ⓘ 툴팁(`title`/`aria-label`)에 금지 용어 **"후보"** 노출 | 해당 reason 문구를 "요즘 잘 오르는 ETF 목록에 드는지" 로 교체. 사용자 노출 텍스트에 금지 용어 0건(grep 확인 — 나머지 히트는 코드 식별자·주석) |
| A-2 | staged 상태를 반대로 보고(22 staged) | §3-2 재실측 정정: **staged 0 · M13+D4+??9=26** (stage 취소 이력 명시) |
| A-3 | AC-7 충족 기록이 실제 툴팁과 불일치 | A-1 수정으로 실제 충족. AC 표(AC-7) 유지 |
| B-1 | NAV 집계 필드 누락 시 `?? 0` 으로 정상 0건 위장 | 필드가 숫자가 아니면(손상 응답) 0 위장 대신 "ETF 기준가 자료 상태를 확인할 수 없습니다" heavy 항목으로 표시 |
| B-6 | AC-7 테스트가 `textContent` 만 검사 → title/aria-label 금지어 놓침 | 테스트를 본문 + 모든 `title`·`aria-label` 스캔으로 강화(이 강화가 있었으면 "후보" 를 잡았음) |
| B-6 | 3초 자동 소멸 테스트 `act(...)` 경고 | 타이머 진행을 `act()` 로 감싸 경고 제거. microtask flush 분리로 3초 타이머 조기 발화 방지 |

**검증(r10)**: vitest **82 passed** · tsc 0 · eslint 0 · **act 경고 0**.

## 2. 설계서 AC 1:1 대조 (수정 후)

| AC | 요구 | 결과 |
|---|------|------|
| AC-1 10초 과업 | 첫 화면에서 코스피 위치·판단·정비 구분 | 상단 2열로 세 영역 동시 노출 (실화면 판정은 사용자 몫 AC-15) |
| AC-2 코스피 위치 | 흐름·지속일·고점대비·기준선거리·거래량·기준일 | 코스피 차트+기준일 O · 국면(KODEX200 별도) O · MA20/60 거리 O · 지속일/고점/거래량 = 개발 중 (Q3/Q5 확정) |
| AC-3 기존 데이터·산식 재사용 | 임의 산식 금지, 없으면 개발 중 | KOSPI 저장 시계열 read + KODEX200 저장 MA 산술만. 나머지 개발 중 |
| AC-4 판단 항목 제한 | 판단 큐에 투자 판단 항목만 | 요즘 잘 오르는 ETF + 내가 가진 ETF(개발 중)만 |
| AC-5 정비 분리 | 정비 항목은 정비 큐에만 | 자료 상태 전부 정비 큐. 테스트로 큐 분리 고정 |
| AC-6 상세 분리 | 대시보드에 상세표 없음 | 건수·한 줄·버튼만. 상세표 없음 |
| AC-7 사용자 언어 | 내부 용어 비노출 | View + Sidebar 모두 §7 매핑. 테스트 2건 |
| AC-8 관찰 가능 판정 | 형용사 아닌 참·거짓 | 테스트가 DOM 사실로 판정 |
| AC-9 정직 표시 | 미구현/미저장 개발 중, 임시 숫자 금지 | 지속일/고점/거래량/보유위험 = 개발 중. 거래량=미저장 툴팁. MA 결측=자료 없음 |
| AC-10 기존 보존 | 기존 대시보드 별도 화면 유지 | dashboard key 보존, 라벨 "기존 대시보드" |
| AC-11 MA 한계 툴팁 | hover 툴팁 | title/aria 툴팁으로 전환 |
| AC-12 신규 위험 산식 금지 | 미추가 | 추가 없음 (개발 중 표시만) |
| AC-13 표 가독성 | 세로 줄바꿈·붕괴 없음 | 대시보드에 표 없음(상세 분리) → 붕괴 위험 최소 |
| AC-14 이동 버튼 | 실제 목적 화면 이동 | ETF 비교하기→workbench, 정비 항목별→market_discovery/etf_exposure. 테스트 |
| AC-15 사용자 실화면 | 자동 통과만으론 완료 아님 | **충족 — 사용자 실화면 확인 완료 (2026-08-01)** |

---

## 3. 검증 실측 (r10 수정 후 · 직접 실행 · 2026-07-31)

- Frontend: **vitest 82 passed** (신규 View 30 + 기존 52). tsc 0 · eslint 0 · **act 경고 0**.
  - build 는 dev 서버 켜둔 상태라 미실행(검증 3종은 `.next` 미변경 → dev 안전). dev 서버 실측 HTTP 200.
- Backend: r2~r10 FIX 는 frontend 만 수정 (backend 무변경). 직전 backend 회귀 **1079 passed / 4 skipped / 0 failed** 유지 · black/flake8 clean.
- KS-10 라인수(실측): TodayInvestmentCheckView **768** · test 576 · KospiChart 101 · todayHelpers 86 · LeftSidebar 82 · queryCache 202 — 전부 한계(프론트 900 / 백엔드 650) 이내.

## 3-2. 변경 파일 실측 (git status --short --untracked-files=all · 2026-07-31 재실측)

**staged 0 · unstaged M 13 + D 4 + ?? 9 = 26 경로.** (기존 방식대로 stage 안 함 · 사용자 확정 2026-07-31 — 검증은 staged 불필요.) 사용자 참고 파일 `design/DESIGN-apple.md`(??) 제외 시 개발 산출물 = **25 경로**.

> **A-2 정정 이력**: 직전 결과서는 사용자의 "unstaged 없게" 지시로 잠깐 `git add` 후 "staged 22" 로 보고했으나, 그 지시가 취소돼 `git reset` 으로 원복 → **현재 staged 0.** 아래가 현재 실측이다. rename 이 reset 으로 분리돼 archive 이동이 `D`(옛 경로)+`??`(새 경로) 두 줄로 나타난다(파일 이동은 정상).

수정(M · 13): `CLAUDE.md` · `docs/agent/DEV_RULES.md` · `app/api_market_topn_models.py` · `app/api_price_series.py` · `app/market_regime.py` · `frontend/app/components/LeftSidebar.tsx` · `MainPanel.tsx` · `globals.css` · `frontend/lib/api/marketEvidence.ts` · `priceSeries.ts` · `queryCache.ts` · `tests/test_api_price_series.py` · `tests/test_market_regime.py`

삭제(D · 4): `docs/handoff/DEVELOPER_ONBOARDING.md`(→ CLAUDE.md 통합) · `docs/handoff/cleanup_fix_r7/ROUND1_MEASUREMENT.md` · `docs/handoff/cleanup_fix_r7/round1_full_measurement.csv` · `docs/ops/POC2_STEP8_OPERATION_LOG.md`(→ archive 로 이동, 아래 신규에 새 경로)

신규(?? · 9, 사용자 파일 1 포함):
- `frontend/app/components/TodayInvestmentCheckView.tsx` · `.test.tsx` · `today/KospiChart.tsx` · `today/todayHelpers.ts`
- `docs/ai_design/POC3/...DESIGN_V1.md` · `docs/ai_plan/POC3/...PLAN_V1.md` · `docs/ai_result/POC3/...RESULT.md`(본 문서) · `docs/archive/POC2_STEP8_OPERATION_LOG.md`(이동 결과)
- (사용자 파일 · 커밋 대상 아님) `design/DESIGN-apple.md`

> 커밋 전 상태. 검증은 staged 불필요(검증자 확인). 커밋 시 신규 포함은 `git add -A`, `design/DESIGN-apple.md` 만 제외.

---

## 4. 작업명 · 상태 앵커 (A-3 — 해소)

- **작업명 = POC3-01** (사용자 확정 2026-07-29). 명명 문제 자체는 해소됨.
- STATE_LATEST 갱신은 **사용자 실화면 PASS(AC-15) 이후**에 수행한다 (설계서 §15 절차: PASS 일 때만 conclusion·상태 문서 갱신). **2026-08-01 사용자 실화면 확인 완료로 AC-15 충족** → POC3-01 = COMPLETED/VERIFIED. STATE_LATEST 의 POC3-01 블록을 COMPLETED 로 정정한다.

---

## 5. 커밋 방침

- 신규 산출물 untracked 8건 (B-5). 커밋 시 **`git add -A`**(신규·수정·삭제·이름변경 일괄) 사용. `git status --short --untracked-files=all` 로 먼저 확인. (`git add --untracked-files=all` 은 잘못된 플래그 — B-5 정정)
- 단, `design/DESIGN-apple.md`(사용자 참고 파일)는 커밋 대상 아님 → `git add -A` 대신 대상 경로만 지정하거나 add 후 `git reset -- design/DESIGN-apple.md` 로 제외.
- 커밋은 사용자 확정대로 **이 작업 + 문서 재구성(§6)을 한 커밋으로 묶음**. push 별도 승인.

---

## 6. 문서 구조 재구성 (r5 · 사용자 직접 지시 · 검증자 별도 노티)

> 사용자(Hyungsoo)가 2026-07-29 직접 지시한 문서 체계 개편이다. 코드 로직 변경 아님 · 문서/규칙 파일만. 검증자는 이 재구성을 A-4(금지 · 파일 삭제)·B-5(배포 경로)와 함께 확인 바람.

**폴더 재구성 (git 반영)**:
- `docs/design/` → **`docs/ai_design/`**, `docs/plan/` → **`docs/ai_plan/`**, 개발 결과서는 **`docs/ai_result/`** 신설로 이동. (기존 `handoff` 는 유지 · 개발 결과서만 result 로 분리)
- 세 폴더 밑 POC1/POC2/POC3 분류 유지.

**개발자 문서 1개로 통합 (사용자 질문2-(a) 확정)**:
- `docs/handoff/DEVELOPER_ONBOARDING.md` **삭제** → 고유 내용(문서 관리·환경 함정·누적 교훈)을 **`CLAUDE.md`(=`docs/agent/DEV_RULES.md`)** 에 §9~11 로 통합. 다음 세션 개발자용 문서는 CLAUDE.md 하나.
- CLAUDE.md 와 docs/agent/DEV_RULES.md 는 기존에도 동일 내용 → 통합 후에도 동기화 유지.

**일회성/과거 문서 정리 (사용자 질문3·4 확정)**:
- **삭제**: `docs/handoff/cleanup_fix_r7/` (2026-07-14 KS-10 라인수 일회성 실측 · 갱신 안 하는 스냅샷). 사용자 "삭제" 지시.
- **archive**: `docs/ops/POC2_STEP8_OPERATION_LOG.md` → `docs/archive/` (POC2 Step8 한정 과거 운영 로그 · 상시 갱신 대상 아님). 사용자 "archive" 지시. 빈 `docs/ops/` 제거.

**파일 삭제 승인**: 위 삭제 3건(ONBOARDING · cleanup_fix_r7 2파일)은 **사용자 직접 지시**로 수행 (룰상 파일 삭제는 사용자 승인 필수 → 충족).

**stale 참조 처리 (A-3 정정 · 정확히 재보고)**:
- grep 전수 확인 결과 옛 경로를 참조하는 문서는 3부류: (1) 본 결과서·PLAN(내 문서) — 새 경로로 정정 완료. (2) `docs/ops/POC2_STEP8_OPERATION_LOG.md` 를 가리키는 **과거 POC2 문서 2건** (`docs/handoff/POC2/POC2_STEP8_..._VALIDATION.md`, `docs/handoff/STATE_LATEST_ARCHIVE.md`).
- (2)는 **완료된 POC2 STEP 의 역사적 기록**이라 사용자 결정으로 **그대로 보존**한다 (사용자 2026-07-29 "(가) 역사적 기록 유지" 확정). archive 는 원래 프리즈 대상이므로 사후 경로 정정하지 않는다.
- 따라서 "전수 정정" 이 아니라 **"활성 문서만 정정 · 과거 기록은 의도적 보존"** 이 정확한 상태다.
