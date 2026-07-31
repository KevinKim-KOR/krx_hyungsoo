# POC3-REF-01 친구 프로젝트 소스 사실 조사 — 결과 문서

* 문서 종류: 소스 조사 결과 문서 (검증자 입력)
* 대응 설계서: `docs/ai_design/POC3/POC3-REF-01_FRIEND_PROJECT_SOURCE_FACT_SURVEY_DESIGN_V1.md`
* 대응 개발계획: `docs/ai_plan/POC3/POC3-REF-01_FRIEND_PROJECT_SOURCE_FACT_SURVEY_PLAN_V1.md`
* 작성일: 2026-07-31 (초안) / 1·2·3·4차 / 5차 (검증자 VERIFIED_WITH_NOTES · 3문서 staged 전환) / **6차 (VERIFIED/CLOSED · commit `16d56702` + push 완료)**
* 상태: **POC3-REF-01 VERIFIED / CLOSED** — 검증자 VERIFIED_WITH_NOTES 의 유일 NOTE(3문서 untracked) 를 3문서 `git add` → commit `16d56702` → `git push origin main` 으로 해소(2026-07-31). 조사 Step 종료. 채택 판단·메뉴 트리 재편은 이후 별도 설계 Step (설계자 영역, 미착수).
* **4차 정정 (검증자 2차 REJECTED — 3차에서도 남은 조사 미완)**:
  - **A-1-1 대시보드 원천**: "daily_snapshots+실시간" 만 적음 → **불완전.** 실제 `load_dashboard_data` 는 `portfolio_master`·`weekly_fund_data`·일/월/연 집계·계좌설정·실보유·실시간 시세 모두 사용. §3 전체 열거.
  - **A-1-2 SSR API 누락**: 클라이언트 `/api/*` 만 봄 → **서버 컴포넌트(page.tsx) SSR `/internal/*` 놓침.** market-trend page.tsx 가 `/internal/market-trend/defaults` 직접 호출 — 추가. (전 page.tsx 재확인: SSR internal 직접호출은 market-trend 1건뿐.)
  - **A-1-3 경로 오기**: 보유상세 `/holding-countries` → 실제 `/api/holdings-components/holding-countries` 로 정정.
  - **A-3**: "모든 API 열거" 단정 철회 — "확인된 직접 호출" 로 표현(전수 보장 아님).
* 성격: **사실 조사만.** 채택 판단·대시보드 반영·구현 지시 없음(AC-11).
* **3차 정정 (검증자 지적 = 제가 2차에서 얕게 확인하고 `[확인]` 으로 단정한 오류들 — 실제 소스 재확인해 정정)**:
  - **A-1-1 레짐 산식**: "MA 교차(0 기준)" → **틀림.** 실제는 **추세% 방향 × 회귀 기울기(비대칭 창 5/7일) × deadband 0.05 × 이력유지** (`_regime_from_slope`·`config.py:207`). §5-A 전면 정정.
  - **A-1-2 weight_allocator**: "scoring→rank_service 호출" → **틀림.** 공개 함수 **호출자 0건 (현재 미사용).** scoring 은 별개 모듈. §5-C 정정.
  - **A-1-3 알림**: "정기 발송형만" → **틀림.** `live_24h_slack` 에 **최근 1h 변동 ≥ 3.0%(`LIVE_24H_ALERT_PCT`) @channel 경고 조건** 존재. §5-B 정정.
  - **A-1-4 스냅샷 저장**: "data_aggregate/cache_refresh 생성" → **틀림.** 실제 저장은 **`slack_asset_summary.py:388`(asset_summary cron 09:20/15:35)**. §3 정정.
  - **A-1-5 메뉴 API**: 대표 API 1개만 적음 → **각 메뉴 디렉토리 전체 grep 으로 모든 `/api/*` 열거** (자산관리 +dashboard/note, 배치 +system, 추세 +history). §2 정정.
  - **A-2 git 상태**: 3문서 untracked 를 §8 에 명시. **A-3 SuperTrend**: §2.5 [확인]↔§6 [확인불가] 모순을 [확인불가] 로 통일.

> 표기 규약: **[확인]** = 소스에서 직접 확인한 사실. **[추정]** = 사실에서 유추(확정 아님). **[확인불가]** = 조사 범위/방식으로 확인 못 함. 민감정보(계정·키·개인정보)는 **존재·역할만** 기록하고 값은 기록하지 않음(사용자 지시).

---

## 1. 참조 소스 기준 버전과 열람 범위 (AC-1)

- **경로**: `e:/AI Study/momentum-etf-main/momentum-etf-main/` (중첩 폴더 안이 실소스).
- **기준 스냅샷 (조사 시작 시점 고정) — 지시6 정정**:
  - 조사 시작: 2026-07-31 19:25 (KST)
  - 전체 파일 수: **302**
  - **파일 목록 지문**(파일 경로 목록만의 SHA256, 내용 아님): `dc2ef18500b8f19d2354f79d4892d2302e562b787cc078015f7322859b4bd0d1`
  - **파일 내용 기반 트리 해시**(각 파일 내용 sha256 → 취합): `335cbf897496d6d9dc57c8173e32ffc27ab707f996a51fa0d96f4cb2524d2034`
  - git 저장소 아님(압축 해제본). 폴더명이 KILL_SWITCHES 의 `momentum-etf-main` 과 같으나 **동일 소스·버전으로 단정하지 않음** — 본 스냅샷 지문/해시로만 고정.
  - **주의**: 위 지문/해시는 **조사 시점 스냅샷 고정용**이며, 이것이 같다는 사실만으로 "소스 내용이 절대 안 바뀌었다" 고 단정하지 않는다(다른 시점·다른 전달본과의 동일성 보장 아님).
- **열람 범위**: 사용자 확정 "전체 열람 허용 · 민감정보 조회 가능하나 결과 문서 기록 불가". 본 조사는 **정적 소스 read 만**(실행 안 함). 민감 파일(`accounts.json` 등) 값은 기록하지 않음.

---

## 2. 전체 메뉴–화면–확인 기능 대응표 (AC-2/3/4)

**[확인] 메뉴 정의 단일 출처**: `web/app/AppShell.tsx` (Next.js App Router · 좌측 사이드바). 아래가 **사용자 노출 메뉴 전수**다. (백엔드 라우터가 아니라 이 사이드바가 조사 모집단 — 설계자 확정 기준.)

> 표 열: **핵심 과업**·**직접 연결 데이터/API·서비스**·**구현 구분**. **2차 보완**: page.tsx → `*PageClient` → `*Manager`(3단 래퍼) 를 직접 열어 실제 호출 API·과업·화면 구현 여부를 확인. 구조 [확인]: page.tsx(7줄 래퍼) → `*PageClient`(PageFrame+title) → `*Manager`(데이터 fetch).

### 2.1 최상위 메뉴 (그룹 없음) — 4개
| 메뉴명 | 경로 | 연결 화면 | 핵심 과업 | 직접 연결 API·서비스 | 구현 구분 |
|---|---|---|---|---|---|
| 홈 | `/` | → `dashboard/DashboardManager` | [확인] 자산 개요 대시보드 | [확인] `/api/dashboard` → `lib/dashboard-store` → `/internal/dashboard` → `utils/dashboard_service`(§3) | [확인] 화면 구현 |
| 시장지수 추세 | `/market-trend` | `market-trend/page.tsx`(SSR) | [확인] 5개 지수 추세·레짐 조회 | [확인] **서버페이지가 `/internal/market-trend/defaults` 직접 호출(SSR, page.tsx:16)** + 클라이언트 `/api/market-trend` + `/api/market-trend/history` → `/internal/market-trend` → `market_trend_service`(§5-A) | [확인] 화면 구현 |
| 보유종목 | `/holdings` | → `HoldingsManager` | [확인] 보유 현황 조회 | [확인] `/api/assets` + `/api/ticker-detail` | [확인] 화면 구현 |
| 보유종목 상세 | `/holdings_details` | → `HoldingsDetailsPageClient` | [확인] 국가별 보유 구성종목 상세 | [확인] `/api/holdings-components/holding-countries` + `/api/holdings-components/by-holding-country?country_code=` | [확인] 화면 구현 |

### 2.2 그룹 "자산" — 7개
| 메뉴명 | 경로 | 핵심 과업 | 직접 연결 API | 구현 구분 |
|---|---|---|---|---|
| 자산 관리 | `/assets` | [확인] 자산(보유) 관리 | [확인] `/api/assets` + **`/api/dashboard` + `/api/note`** | [확인] 화면 구현 |
| 자산 차트 | `/asset-charts` | [확인] 자산 추이 차트 | [확인] → `AssetChartsManager` → `/api/weekly` | [확인] 화면 구현 |
| 일별 | `/daily` | [확인] 일별 실적 | [확인] → `DailyManager` → `/api/daily` | [확인] 화면 구현 |
| 주별 | `/weekly` | [확인] 주별 실적 | [확인] → `WeeklyManager` → `/api/weekly` | [확인] 화면 구현 |
| 월별 | `/monthly` | [확인] 월별 실적 | [확인] → `MonthlyManager` → `/api/monthly` | [확인] 화면 구현 |
| 년별 | `/yearly` | [확인] 년별 실적 | [확인] → `YearlyManager` → `/api/yearly` | [확인] 화면 구현 |
| 스냅샷 | `/snapshots` | [확인] 스냅샷 이력 | [확인] → `SnapshotsManager` → `/api/snapshots` | [확인] 화면 구현 |

### 2.3 그룹 "정보" — 6개
| 메뉴명 | 경로 | 핵심 과업 | 직접 연결 API | 구현 구분 |
|---|---|---|---|---|
| 종목풀 순위 | `/pools` | [확인] 종목풀 순위 조회 | [확인] → `StocksManager` → `/api/rank` · `/api/rank-toolbar` | [확인] 화면 구현 |
| ETF 비교 | `/compare` | [확인] 티커 검색·ETF 비교 | [확인] → `ComparePageClient` → `/api/ticker-detail-compare` · `/api/ticker-tickers` | [확인] 화면 구현 (이전 "placeholder" 매치는 검색 input 의 `placeholder` 속성이었음 — 미구현 아님) |
| 한국 개별주 | `/kor-market-stock` | [확인] 한국 개별주 조회 | [확인] → `KorMarketStockManager` → `/api/kor-market-stocks` | [확인] 화면 구현 |
| 미국 개별주 | `/us-market-stock` | [확인] 미국 개별주 조회 | [확인] → `UsMarketStockManager` → `/api/us-market-stocks` | [확인] 화면 구현 |
| 한국 ETF | `/kor-market-etf` | [확인] 한국 ETF 조회 (`market/MarketPageClient` **재사용**, title만 "🇰🇷 한국 ETF") | [확인] → `MarketManager` → `/api/market` | [확인] 화면 구현 (공용 시장 화면 재사용 — **중복 진입점**, §4.1) |
| 24H 시세 | `/live-24h` | [확인] 24시간 시세 (Hyperliquid) | [확인] → `HyperliquidClient` → `/api/live-24h` | [확인] 화면 구현 |

### 2.4 그룹 "시스템" — 2개
| 메뉴명 | 경로 | 핵심 과업 | 직접 연결 API | 구현 구분 |
|---|---|---|---|---|
| 배치 | `/batch` | [확인] 배치 작업 상태/로그 | [확인] `/api/system` + `/api/system/job-logs` + `/api/system/cancel`→`/internal/system/*` | [확인] 화면 구현 |
| 설정 | `/settings` | [확인] 종목풀 설정 관리 | [확인] → `SettingsManager` → `/api/pool-settings` | [확인] 화면 구현 |

**메뉴 합계: 19개** (최상위 4 + 자산 7 + 정보 6 + 시스템 2). **4차 정정 (검증자 A-1/A-3)**: API 열은 각 메뉴 디렉토리(`web/app/<메뉴>/*.tsx`)의 **클라이언트 `/api/*` 호출 + 서버 컴포넌트(SSR)의 `/internal/*` 직접 호출** 을 확인해 열거. **"모든 API 를 다 열거했다" 고 단정하지 않는다** — 이번 검증에서 시장지수 추세의 **SSR `/internal/market-trend/defaults`(page.tsx) 누락** 이 드러나 추가했고, 보유상세 경로 오기(`/holding-countries`→`/api/holdings-components/holding-countries`)를 정정. 즉 표는 **확인된 직접 호출**이며, 각 route.ts 가 다시 부르는 세부 서비스 체인·미확인 SSR 호출은 조사 범위 밖일 수 있음(전수 보장 아님). placeholder/빈 화면 메뉴 없음(compare 오탐 정정).

### 2.5 캡처 vs 실제 소스 차이 (AC-4)
- **[확인]** 캡처에서 본 "레짐 구간·전고점 대비" 는 **독립 메뉴가 아니라 `시장지수 추세`(`/market-trend`) 화면 안의 표현**이다(별도 메뉴 아님). **단 "공격/방어 비중"·"SuperTrend" 라는 명칭이 이 화면 소스에 있는지는 확정 못 함** — 구현은 회귀기울기+deadband 레짐(§5-A), 명칭 일치는 [확인불가](§6). (A-3 정정: 이전에 SuperTrend 를 [확인]으로 단정한 것과 §6 [확인불가] 가 모순이던 것 해소 — [확인불가] 로 통일.)
- **[확인]** 캡처로 못 본 메뉴 다수 존재: 자산 관리·자산 차트·일/주/월/년별·스냅샷·종목풀 순위·ETF 비교·개별주(한/미)·한국 ETF·24H 시세·배치·설정.
- **[확인]** 로그인(`/login`)은 사이드바 메뉴에 없고 별도 인증 화면(AppShell 이 `isLoginPage` 로 분기).

---

## 3. 대문·대시보드 축 조사 결과 (AC-5)

**[확인] 화면 소스**: `web/app/dashboard/DashboardManager.tsx` (654줄).

- **정보 구성**: (a) 헤더 — 기준일 3종(스냅샷 날짜·주별 날짜·갱신 시각) + 기간 선택 버튼(지난 N개월) + "수익/손실 종목 수" + "금액 가리기" 토글. (b) 좌측 지표 카드 그리드(`metrics_row1`+`row2` 를 `DASHBOARD_LEFT_LABELS` 순서로 정렬). (c) 기간 수익 카드 4개: **금일·금주·금월·금년** (금액 + 수익률%).
- **시각화 [확인]**: **Recharts** 사용 (`AreaChart`·`PieChart`·`Pie`·`Cell`·`Tooltip`·`XAxis`·`YAxis`). 지표 카드에 **스파크라인**(`sparklines`) 포함.
- **갱신 방식 (지시2 명확화)**:
  - **수동 갱신 버튼: [확인] 없음.** `DashboardManager.tsx` 에 새로고침/refresh/reload 버튼 grep 0건. (기간 선택·금액 가리기 버튼은 있으나 데이터 재조회 버튼 아님.)
  - **자동 polling: [확인] 없음.** `setInterval` grep 0건. 마운트 시 `useEffect` 로 `fetch("/api/dashboard", {cache:"no-store"})` **1회** 로드. 브라우저 `pageshow` 이벤트 시 상단바(AppShell) top-bar 만 재로드(대시보드 본문 아님).
  - **서버 캐시: [확인] 명시적 서버 캐시 없음.** `route.ts` 는 `export const dynamic = "force-dynamic"` + `jsonNoStore()` (캐시 무효화). `dashboard_service.py` 에 `lru_cache`/캐시 데코레이터 없음 — 매 요청 계산. (단 MongoDB 자체 캐시층은 조사 범위 밖.)
  - **데이터 원천 [확인·4차 정정 — 초안/2차 불완전]**: `dashboard_service.load_dashboard_data`(`utils/dashboard_service.py:167~`) 는 다음을 **모두 직접 사용**(이전 "daily_snapshots + 실시간 시세" 만 적은 것은 누락):
    - MongoDB 컬렉션: **`portfolio_master`**(GLOBAL 마스터, `:173`) · **`daily_snapshots`**(최근 2개, `:174`) · **`weekly_fund_data`**(`:177`)
    - 서비스/집계: **계좌 설정** `load_account_configs`(`:172`) · **실보유** `load_real_holdings_table`(`:211`) · **일별 집계** `load_daily_docs_for_aggregation`(`:278`) · **월별** `_load_monthly_docs`(`:289`) · **연별** `_load_yearly_docs`(`:297`) · **계좌 벤치마크** `_load_account_benchmarks`
    - **실시간 시세**: `services.price_service.get_realtime_snapshot` (`df_live`)
  - **실시간 vs 스냅샷 [확인]**: 저장 스냅샷/집계 문서 + 실시간 시세를 **혼합해 요청 시 계산**.
  - **batch·cron 관계 [확인·3차 정정 — 2차 오류]**: `daily_snapshots` 저장(생성) 실제 위치는 **`scripts/slack_asset_summary.py:388~`("Save Snapshots for next time")** 다 (계좌별 + TOTAL 스냅샷 저장). 이 스크립트는 cron `asset_summary` 잡으로 **평일 09:20·15:35** 실행(§5-B). → **대시보드가 읽는 `daily_snapshots` 는 `data_aggregate`/`cache_refresh` 가 아니라 `slack_asset_summary`(asset_summary cron) 가 생성.** (초안/2차의 "data_aggregate·cache_refresh 가 생성" 은 오류.)
- **캐싱/재사용 [확인]**: 프론트 `cache:"no-store"` + 서버 `force-dynamic` → 캐시 안 함.
- **데이터 흐름 [확인·정정]**: `DashboardManager` → `/api/dashboard`(Next route, `force-dynamic`) → **`lib/dashboard-store.loadDashboardData` → `fetchFastApiJson("/internal/dashboard")` → FastAPI `utils/dashboard_service`**. (초안에서 "route.ts 자체처리·internal 미경유" 라 한 것은 `lib/dashboard-store` 한 단계를 놓친 오류 — **실제로는 `/internal/dashboard` 경유**로 2차 정정.)
- **부가 [확인]**: `hideMoney` 컨텍스트로 금액 마스킹("••••••") 기능. `is_deploying` 플래그로 "🚧 배포 진행 중" 배지.

---

## 4. 메뉴 트리·라우팅 축 조사 결과 (AC-6)

- **[확인] 구조**: 3-tier. **Next.js 페이지(`web/app/*/page.tsx`) → Next API route(BFF, `web/app/api/*/route.ts`) → FastAPI `/internal/*`(`fastapi_app/routes/`) → utils 서비스 → DB.**
- **[확인] 메뉴 그룹↔라우팅**: 사이드바 그룹(자산/정보/시스템)은 UI 그룹핑일 뿐, URL 은 평면(`/assets`·`/pools` 등). 그룹 접힘 상태는 `openGroups` 로컬 상태.
- **[확인] 프론트 API route → FastAPI internal 매핑 (교차검증)**:
  - `/api/assets`→`/internal/holdings` · `/api/fear-greed`→`/internal/market/fear-greed` · `/api/fx`→`/internal/market/fx` · `/api/vkospi`→`/internal/market/vkospi` · `/api/market-trend`→`/internal/market-trend?ma_type=` · `/api/market-trend/history`→`/internal/market-trend/history` · `/api/holdings-components*`→`/internal/holdings-components*` · `/api/kor-market-stocks`→`/internal/kor-market-stocks` · `/api/us-market-stocks`→`/internal/us-market-stocks/index` · `/api/pool-settings`→`/internal/pool-settings` · `/api/system/*`→`/internal/system/*` · `/api/ticker-*`→`/internal/ticker-detail/*` · `/api/health`→`/internal/health` · `/api/live-24h`→`/internal/live-24h`.
  - **API 전용 라우터 (메뉴 아님)**: 위 `/api/*` 는 화면이 쓰는 데이터 경로이지 사용자 메뉴가 아님 → 메뉴 목록에 등록 안 함(설계 기준 준수).
- **route.ts 처리 방식 [부분 확인·2차 정정]**: `/api/dashboard` 는 **`lib/dashboard-store` 경유로 `/internal/dashboard` 호출**(초안의 "자체처리" 오류 정정 — §3). 나머지 `/api/daily·monthly·weekly·yearly·market·snapshots·rank·stocks*·note·ticker-detail*·auth/*` 는 route.ts 가 `/internal/*` 를 직접 grep 으로 안 잡히는 방식(lib 경유 또는 자체 처리)으로 처리 — **각 route.ts 의 lib 경유 여부는 dashboard 처럼 한 단계 더 확인해야 확정**(대시보드 외 route 는 조사 범위 밖, [확인불가]).
- **[확인] 동적 라우트**: `/ticker`(+`/ticker/XXX`) — `isNavItemActive` 가 `/ticker/` prefix 매칭 처리. `ticker` 는 사이드바 메뉴엔 없고 GlobalTickerSearch(상단 검색)로 진입 → **비메뉴 진입점**(§7).
- **[확인] 인증**: Google OAuth (`/api/auth/google/start`·`callback/google`·`logout`). 로그인 안 하면 `/login` 분기.

### 4.1 메뉴 구조 특이 항목 (지시3 — 없으면 단정 말고 "확인되지 않음")
- **숨김 메뉴**: **[확인] 없음.** `AppShell.tsx` `navGroups`+최상위 4항목은 모두 렌더됨. 역할/권한 기반 조건 렌더링 grep 0건.
- **조건부 메뉴**: **[확인] 1건 — 로그인 화면 분기.** `isLoginPage`(`pathname === "/login"`)면 사이드바 전체를 숨기고 로그인 화면만 렌더. 그 외 메뉴별 조건부 표시는 **조사 범위에서 확인되지 않음**.
- **미구현 메뉴**: **[확인] 없음.** 19개 메뉴 모두 `page.tsx`+`*Manager`(또는 Client) 실재하고, 2차 보완에서 각 Manager 를 열어 데이터 fetch·과업을 확인함(§2). placeholder/빈 화면으로 확인된 메뉴 없음(compare 오탐은 검색 input 속성으로 정정). 각 Manager 내부 세부 위젯 전수는 조사 범위 밖.
- **중복 진입점**: **[확인] 2건**. (a) **홈(`/`)** — 사이드바 "홈" + 브랜드 로고 + 모바일 브랜드가 모두 `/` (3진입점). (b) **`/kor-market-etf` 와 `/market`(비메뉴)** — 둘 다 `MarketPageClient`→`MarketManager`→`/api/market` 재사용, title 만 다름(한국 ETF 는 "🇰🇷 한국 ETF"). 즉 **같은 화면 컴포넌트를 title 만 바꿔 여러 진입점**으로 씀(2차 확인).

---

## 5. 위험·알람 축 조사 결과 (AC-7/8)

지시4 에 따라 두 흐름으로 분리 정리한다.

### 5-A. 흐름 A — 시장 데이터 → 레짐 계산 → API → 화면 표시
- **[확인] 소스**: `utils/market_trend_service.py`(815줄) · 진입 `compute_market_trend(ma_type, ma_months)`.
- **입력 [확인]**: 5개 시장지수(코스피·코스피200·S&P500·나스닥·나스닥100) 종가 시계열(네이버/yfinance).
- **레짐 계산 [확인·3차 정정 — 초안/2차 오류]**: **MA 단순 교차(0 기준)가 아님.** 실제(`_build_daily_regime_ranges` + `_regime_from_slope` + `_trend_slope`, `utils/market_trend_service.py`):
  - 일별 추세% = `(close/ma - 1) * 100` (MA 괴리율) — 여기까지는 방향(부호).
  - **추가로**: 추세% 시계열에 **최소제곱 회귀 기울기**(`_trend_slope`, %/일)를 **비대칭 창**으로 계산 — 상승 강화는 짧은 창(`MARKET_TREND_REGIME_SLOPE_UP_WINDOW = 5`일), 약화는 긴 창(`MARKET_TREND_REGIME_SLOPE_WINDOW = 7`일).
  - **deadband**(`MARKET_TREND_REGIME_SLOPE_DEADBAND = 0.05`): `up_slope > +0.05` → 강화, `down_slope < −0.05` → 약화. deadband 안이면 라벨 유지.
  - **이력(hysteresis)**: 이전 상태(`strengthening_prev`)를 유지 로직에 사용 → 3단계 레짐(방향 부호 × 가속/감속) 분류.
  - **임계값 상수 위치 [확인]**: `config.py:207~` (`MARKET_TREND_REGIME_SLOPE_UP_WINDOW=5`·`_WINDOW=7`·`_DEADBAND=0.05`).
  - 산출: `trend_pct`·`pct_from_high`·`current_regime`·`current_regime_days`. MA 종류: SMA/EMA/WMA/DEMA/TEMA/HMA/ALMA.
- **결과 저장 [확인]**: `compute_market_trend` 는 요청 시 계산해 API 응답으로 반환. 함수 내 DB save/insert 없음.
- **API→화면 [확인]**: `/api/market-trend`(+`/history`)→`/internal/market-trend` → `market-trend/page.tsx`.
- **"SuperTrend" [확인불가]**: 구현은 위 **회귀 기울기+deadband 레짐**이며 `supertrend` 함수/변수명은 소스에 없음. 캡처의 "SuperTrend 기준" 문구가 이 구현을 가리키는지 명칭상 확정 못 함(§2.5·§6).

### 5-B. 흐름 B — 보유 데이터 → 알림 조건 → 실행 주기 → Slack → 사용자 확인
- **[확인] 소스**: `scripts/portfolio_notifier.py`(256줄) · `live_24h_slack.py` · `slack_asset_summary.py` · `utils/notification.py`(`send_slack_message_v2`).
- **보유 데이터 [확인]**: 계정별 `load_real_holdings_table` → **버킷(bucket)별 그룹핑** → 종목별 누적/일간 수익률·손익.
- **알림 조건 [확인·3차 정정 — 2차 "정기 발송형만" 오류]**: 트리거 3종:
  - (a) **캐시 누락 시 경고**(`MissingPriceCacheError` → "알림 발송 중단" Slack).
  - (b) **정기 포트폴리오 요약 브리핑**(`slack_asset_summary`, 버킷별 수익률·손익 · cron 정기).
  - (c) **[확인] 수치 조건 알림 존재**: `live_24h_slack.py:62~` — 종목별 **최근 1시간 변동률 절댓값 ≥ `LIVE_24H_ALERT_PCT`(= `config.py:112` **3.0%**)** 이면 `@channel` 경고 플래그. → **"손절 임계형은 아니지만, 급변동(3%) 수치 조건 알림은 존재."** (초안/2차의 "정기 발송형만" 은 이 조건을 놓친 오류.)
  - 손절/손실제한 임계 알림: `손절`/`stop_loss` grep 0건 → **발견 못 함**(부재 단정 아님).
- **실행 주기 [확인·2차]**: `infra/cron/crontab` 실측 —
  - `slack_asset_summary`(포트폴리오 요약 Slack): **평일 09:20, 15:35** (2회)
  - `live_24h_slack`(24H 시세 Slack): **매시 정각**
  - 데이터 갱신: `cache_refresh`(매시 · 월~토), `data_aggregate`(평일 09:10·09:40~15:40 매 30분), `metadata_updater`(평일 09:45~17:45), `us_market_stocks`(평일 08:00), `market_hours_analysis`(평일 07:00)
- **결과 저장 [확인불가]**: 알림 판정 결과의 DB 저장 여부는 조사 범위 밖(notifier 는 발송까지 확인).
- **Slack→사용자 [확인]**: 알림은 **Slack 통지까지**. 이후 행동은 사용자.

### 5-C. 자동 주문·손절·비중 조절 연결 (AC-8) — **보수적 결론 (지시5)**
- **자동 주문 교차확인 (지정 범위: `*.py`·`*.ts`·`*.tsx` grep)**:
  - `place_order`/`submit_order`/`execute_trade`/매수·매도 실행 호출 → **발견 못 함.**
  - 걸린 `holdings.py` `@router.patch("/order")` = **`reorder_holdings`(보유 종목 표시 순서 재정렬)** [확인] — 증권 주문 집행 아님. `post_one_holding` = 보유 종목 **수동 입력(add)**.
  - 증권 API(토스=미국 주식 실시간 가격 · KIS=국내 ETF 종목마스터)는 **시세·마스터 조회 용도**.
- **→ 보수적 결론 [확인]**: **"이번 조사의 지정 범위에서 자동 주문/자동 매매 실행 코드를 발견하지 못했다."** 별도 저장소·미조사 경로·런타임 연동 가능성은 배제 못 하므로 **"없다" 고 단정하지 않는다.**
- **손절 [확인·2차]**: `손절`/`stop_loss`/`청산`/`liquidat` grep **0건**. 걸린 `target_ratio`·`cash_target_ratio` 는 **손절이 아니라 목표 비중(cash/종목 target ratio)**. → **손절 관련 조건/호출을 지정 경로에서 발견 못 함**(부재 단정 아님).
- **비중(weight) 산식 성격 [확인·3차 정정 — 2차 호출관계 오류]**:
  - `core/strategy/weight_allocator.py` 함수 = `calculate_score_weights`(점수→비중)·`_apply_guardrails`·`should_rebalance`.
  - **호출자 [확인]**: `calculate_score_weights`·`should_rebalance` 의 호출자를 저장소 전체 grep → **0건.** 즉 **weight_allocator 의 공개 함수는 현재 아무 곳에서도 호출되지 않음.** (2차에서 "scoring→rank_service 로 연결" 이라 한 것은 **오류** — `scoring.py`(`calculate_maps_score` 등)는 **별개 모듈**이고 `rank_service`/`rankings` 가 그걸 쓰는 것이지, `weight_allocator` 를 쓰는 게 아님. 두 모듈을 잘못 엮었음.)
  - → **`weight_allocator` 는 현재 순위 화면 등에서 직접 사용되지 않는 것으로 확인**(호출자 부재). 저장·주문 연결 이전에 **호출 자체가 없음.** `should_rebalance` 도 정의만 있고 호출 안 됨.
  - 별개로 `scoring.py`(점수 계산)는 `utils/rankings.py`·`rank_service.py` 가 사용 → 순위 화면. (이건 weight_allocator 와 무관.)
  - "버킷(bucket)" = 포트폴리오 그룹핑 축. 공격/방어 대응 여부는 [확인불가](§6).

---

## 6. 확인 불가·추가 조사 필요 항목 (AC-10)

> 2차 보완으로 다수 해소. 아래는 **여전히 확인 못 한 것만** (직접 경로 밖 = 조사 범위 밖).

- **"버킷(bucket)" 의 정의·공격/방어 대응 여부** — 버킷이 포트폴리오 그룹핑 축인 것은 확인. 그 분류 기준(공격/방어 성격인지)은 `core/strategy/*` 더 깊은 조사 필요. **[확인불가]**
- **"SuperTrend" 명칭 일치** — 구현은 회귀 기울기+deadband 레짐(§5-A)으로 확인. 캡처 문구 "SuperTrend" 가 이걸 가리키는지 명칭상 확정 불가. **[확인불가]**
- **알림/레짐 판정 결과의 DB 저장 여부** — notifier 는 발송까지, market_trend 는 요청 시 계산까지 확인. 배치 사전계산 저장 여부는 DB 스키마 조사 범위 밖. **[확인불가]**
- **MongoDB 자체 캐시층** — 앱 레벨 서버 캐시 없음은 확인. DB 내부 캐시는 조사 범위 밖. **[확인불가]**
- **각 Manager 내부 세부 UI 요소 전수** — 메뉴별 과업·API 는 확인. 화면 내 개별 위젯/컬럼 전수는 조사 범위 밖(설계서 §4: 심층은 3축 한정).

> **해소·정정된 항목(2·3차)**: 15개 메뉴 전체 API(§2) · 대시보드 원천/캐시/스냅샷 생성처(§3) · **레짐 산식 정정(회귀+deadband, §5-A)** · 알림 3% 조건(§5-B) · cron 주기 · **weight_allocator 호출자 0건(§5-C)** · 손절 발견 못 함.

---

## 7. 조사 범위 밖 발견 (현재 추적 안 함) — 비메뉴 발견 기능

> 지시7: 우리 프로젝트에 대한 채택·비교·허용/금지 판단은 삭제. **친구 소스에서 확인된 기술 사용 사실만** 기록.

- **[확인] 비메뉴 진입점**: `/ticker`(종목 상세) — 사이드바 메뉴 없이 상단 `GlobalTickerSearch` 로만 진입.
- **[확인] 상단바 위젯(메뉴 아님)**: CNN 공포탐욕지수(외부 링크)·VKOSPI·환율(USD/AUD)·기간 수익률(금일/금주/금월). 사이드바 하단에 CNN·VKOSPI 센티먼트 위젯.
- **[확인] 친구 소스의 기술 사용 사실 (사실 기록만 · 우리 프로젝트 판단 없음)**:
  - **DB**: MongoDB 사용 (`fastapi_app/main.py` mongo 참조 · AppShell 에 "⚠️ 몽고디비 이슈" 표시 문구 존재).
  - **인증**: Google OAuth (`/api/auth/google/*`).
  - **UI 스택**: Next.js(App Router) + Tabler CSS + Recharts + AG Grid(`AppAgGrid.tsx`).

---

## 8. 조사 준수 확인 (AC-9/11/12)

- **AC-9**: 확인 사실 [확인] / 추정 [추정] / 확인불가 [확인불가] 를 문장마다 표기해 구분함.
- **AC-11**: 채택 여부·적용 화면·개발 우선순위·대시보드 반영·구현 지시 **미포함**.
- **AC-12**: 전수 분석 안 함. 메뉴는 전수 목록화(얕게), 심층은 대문·라우팅·위험/알람 3축으로 제한.
- **민감정보**: 값·개인정보 기록 안 함(존재·역할만).
- **스냅샷 재확인 [확인]**: 조사 시작·종료 시 파일 목록 지문 `dc2ef185...`·파일 수 302 **동일**로 재확인됨. → **조사 세션 중 파일 목록에 변화가 없었다**는 사실까지만 기록. "소스 내용이 절대 안 바뀌었다" 단정 아님(지시6).
- **git 상태 [확인·6차 — commit + push 완료]**: 검증자 VERIFIED_WITH_NOTES 의 유일 NOTE(3문서 untracked) 를 해소. 본 결과서 + 설계서 + 개발계획서 **3문서를 `git add` → commit `16d56702` → `git push origin main`** (2026-07-31, 사용자 승인). 커밋 3파일:
  - `docs/ai_design/POC3/POC3-REF-01_..._DESIGN_V1.md` (committed)
  - `docs/ai_plan/POC3/POC3-REF-01_..._PLAN_V1.md` (committed)
  - `docs/ai_result/POC3/POC3-REF-01_..._RESULT_V1.md` (committed · 본 문서)
  - **사용자 참고 파일 `design/DESIGN-apple.md` 는 검증 범위 밖 — 커밋 제외(로컬 untracked 유지).**
  - 커밋: `16d56702 docs(poc3-ref-01): 친구 프로젝트 소스 사실 조사 — 설계서·개발계획·결과서`. push: `2603d3dd..16d56702 main -> main`. → **NOTE 해소 완료 · POC3-REF-01 CLOSED.**

---

## 9. 검증자 안내

- 이 Step 은 코드 산출물이 없다. 검증자는 **문구만 읽지 말고 표본 항목을 실제 소스 위치와 대조**해 사실성·메뉴 누락·범위 준수를 확인(설계자 Q6).
- 대조 표본 예:
  - (a) §2 메뉴 19개 = `web/app/AppShell.tsx` 의 `navGroups` + 최상위 4항목(homeItem·marketTrendItem·holdingsItem·holdingsDetailsItem)과 일치하는지.
  - (b) §5-C 자동주문 = `place_order`/`submit_order`/`execute_trade` grep 0건이고 `holdings.py` `/order` 가 `reorder_holdings`(정렬)인지 → "발견 못 함" 이 정확한지("없음" 단정 아님).
  - (c) §3 Recharts·`no-store`·갱신버튼/폴링 없음 = `DashboardManager.tsx` 실측인지.
  - (d) §5-A 레짐 = `_regime_from_slope`(회귀 기울기)+`config.py` `MARKET_TREND_REGIME_SLOPE_DEADBAND=0.05`·`UP_WINDOW=5`·`WINDOW=7` 인지 (MA 단순 교차 아님).
  - (e) §5-B 3% 알림 = `live_24h_slack.py` `LIVE_24H_ALERT_PCT`(config.py `=3.0`) 인지. §5-C weight_allocator `calculate_score_weights` 호출자 grep 0건인지.
  - (f) §3 스냅샷 저장 = `slack_asset_summary.py` "Save Snapshots" 인지.
  - (g) §3 대시보드 원천 = `dashboard_service.py:167~` 이 `portfolio_master`·`weekly_fund_data`·일/월/연 집계·`load_account_configs`·`load_real_holdings_table` 를 다 쓰는지.
  - (h) §2 시장지수 추세 = `market-trend/page.tsx:16` 이 SSR 로 `/internal/market-trend/defaults` 직접 호출하는지 · 보유상세 경로가 `/api/holdings-components/holding-countries` 인지.
- 스냅샷 재확인: 경로 `momentum-etf-main/momentum-etf-main` 에서
  - 파일 목록 지문: `find . -type f | LC_ALL=C sort | sha256sum` → `dc2ef185...`
  - 내용 트리 해시: `find . -type f | LC_ALL=C sort | xargs sha256sum | sha256sum` → `335cbf89...`
