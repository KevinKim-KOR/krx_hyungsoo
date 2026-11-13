# POC6-29 개발 결과서 — A·B·C 화면 통합(「요즘 잘 오르는 ETF」 정리)

작성 2026-11-12 · 작성자: 개발자(VSCode Claude) · 수신: 사용자(격리 화면 확인) → 검증자(Codex) → 설계자

```text
STATUS   = IMPLEMENTED(2026-11-12 · 격리 작업 사본) · 사용자 격리 화면 확인 완료(2026-11-12 · 대화 회신) → 검증자 r1 REJECTED(F1 P2 · F2 P3 · §11)
           → F1 · F2 정정(§12 · 2026-11-12) → 검증자 r2 REJECTED(F1·F2 해소 · F3 P3 · §13) → F3 정정(§14) → 검증자 r3 VERIFIED(F3 해소 · §15)
           → 설계자 RESULT PARTIAL(2026-11-12 · 보완 4건: 오늘 점검 상단 시장 흐름 · 최신 자료 갱신 실측 · 보유와 후보 비교 카드 · 미사용 기능 메뉴) → 보완 PLAN(PLAN §9 · 목업 R1 ~ R4) → 설계자 보완 PLAN 승인(2026-11-12)
           → 보완 구현 · 시험(§16 · 격리 작업본) → 형수님 격리 화면 실사용(17:51 갱신 1회 · 네이버 지수 조회 · §16-5)
           → 설계자 RESULT 재판정 PARTIAL 유지(2026-11-12 · 판정서 V2 · 실사용 기준 미충족) → 실제 PC 자료일 대조 · 보완 PLAN §10 · 목업 S1 ~ S3
           → 설계자 보완 PLAN §10 승인(2026-11-12 · S 판정 · 수정 3건) → 보완 2차 구현 · 시험 · 격리 확인(§17)
           → 형수님 화면 의견 반영(2026-11-13 · 판정 표 → 코스피 공식 종가 덩어리를 당일 판정 바로 아래로 · 당일 판정 강조 · 20거래일 그래프 크게 · §17-10) → 검증자 보완 검증 REJECTED(2026-11-13 · §18 · 점수 줄 제거 확인 · F4~F6) → F4 · F5 · F6 정정(§19 · 2026-11-13) → 보완 재검증 REJECTED(§20 · F7 P2) → F7 정정(§21 · 2026-11-13) → 보완 재검증 REJECTED(§22 · F8 P2 · F9 P3) → 형수님 결정(당일 판정 = 서버 한 번 읽기) · F8 · F9 정정(§23 · 2026-11-13) → 보완 재검증 REJECTED(§24 · F10 P2) → F10 정정(§25 · 2026-11-13) → 보완 재검증 VERIFIED(§26 · F10 해소) → 설계자 RESULT 재판정 V3 PASS_WITH_CLOSING_CORRECTIONS(2026-11-13 · 격리 구현 수용 · D1 ~ D4 · 복사) → 마감 보완(§27) · Q-S5 (a) 실제 PC 대조 완료(§27-5 · 11/13 16:53 갱신 · 코스피 · KODEX 200 · 수급 모두 11/12 도달) → V3 마감 변경분 검증 REJECTED(§28 · F11 P2) → F11 정정(§29 · 2026-11-13) → V3 마감 재검증 VERIFIED(§30 · F11 해소) → 형수님 마감 뒤 화면 조절(§31 · 카드 머리 안내 줄 뺌 · 아침 요약 정리 = 설계자 정리 + 형수님 선택) → **설계자 RESULT 마감 판정 PASS(2026-11-13 · 근거 §27 ~ §30 · main 반영과 운영 확인 대기 · §32)** → 실제 PC 반영 대기(main 반영 · 커밋 · push = 형수님 승인 순서 → 운영 확인 → 격리 정리 → CLOSED)
           설계 V1(네 번째 개정본) → 개발 PLAN V1 → 설계자 PLAN 판정 PASS_WITH_REQUIRED_CORRECTIONS(2026-11-12)
           → PLAN · 목업 반영 → 격리 작업 사본 구현 · 시험 → 격리 서버(8001 · 3001)로 실제 저장 자료 확인
           → 독립 검토 1회(코드 + 문서 · 5관점 · 관점마다 반박 검증) · 확인된 결함 정정(§10) → 백엔드 전체 회귀 마감 1회(§8)
DESIGN   = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_DESIGN_V1.md
DECISION = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_PLAN_DECISION_2026-11-12.md(PLAN 보다 우선)
RESULT 판정 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_2026-11-12.md(PARTIAL · 보완 4건)
보완 PLAN 판정 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_SUPPLEMENT_PLAN_DECISION_2026-11-12.md(승인 · Q-R1 ~ Q-R6 · 확인할 세 가지)
RESULT 재판정 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_V2_2026-11-12.md(PARTIAL 유지 · 다음 = 실제 PC 자료일 대조 → 보완 PLAN · 화면 → 재판정)
RESULT 재판정 V3 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_V3_2026-11-13.md(PASS_WITH_CLOSING_CORRECTIONS · 출처 변경 · 11/13 배치 수용 · D1 ~ D4 · 복사 · 마감 확인)
RESULT 마감 판정 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_CLOSEOUT_DECISION_2026-11-13.md(PASS · main 반영과 운영 확인 대기 · 근거 §27 ~ §30 · §32)
보완 PLAN §10 판정 = docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_S_PLAN_DECISION_2026-11-12.md(승인 · Q-S1 ~ Q-S6 · 단기 흐름 5거래일 · 당일 판정은 오늘 시장 변화 · 공개 시각은 확인된 것만)
PLAN     = docs/ai_plan/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_PLAN_V1.md
MOCKUP   = docs/ai_plan/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_MOCKUP.html
VERIFIER = Codex r1 REJECTED(2026-11-12 · §11 · 제품 코드/시험 수정 없음) → 개발자 정정 §12 → Codex r2 REJECTED(2026-11-12 · F3 P3 · §13 · 제품 코드/시험 수정 없음) → 개발자 정정 §14 → Codex r3 VERIFIED(2026-11-12 · F3 해소 · §15 · 제품 코드/시험 수정 없음) → Codex 보완 검증 REJECTED(2026-11-13 · §18 · F4 P2 · F5 P2 · F6 P3 · 제품 코드/시험 수정 없음) → 개발자 정정 §19 → Codex 보완 재검증 REJECTED(2026-11-13 · §20 · F7 P2) → 개발자 정정 §21 → Codex 보완 재검증 REJECTED(2026-11-13 · §22 · F8 P2 · F9 P3) → 개발자 정정 §23 → Codex 보완 재검증 REJECTED(2026-11-13 · §24 · F10 P2) → 개발자 정정 §25 → Codex 보완 재검증 VERIFIED(2026-11-13 · §26 · F10 해소) → Codex V3 마감 변경분 검증 REJECTED(2026-11-13 · §28 · F11 P2) → 개발자 정정 §29 → Codex V3 마감 재검증 VERIFIED(2026-11-13 · §30 · F11 해소)
코드     = 작업 트리 /Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_29 · 브랜치 poc6-29-abc-refocus · 기준 커밋 2c40ea69 · 커밋 없음
보관     = archive/poc6_29_market_discovery/(C 전용 30파일 · git mv · README = 원래 경로 → 대신하는 곳)
금액     = 이 문서 · 시험 · 목업에 실제 금액 · 계좌 · 보유 종목명 없음(시험 = 가상 행) · 시장 수치(ETF 수익률 · 분류)만 공개 자료
```

## 0. 요약

- **메뉴**: 「요즘 잘 오르는 ETF」(`market_discovery`)를 없앴다. 왼쪽 메뉴 그룹 「비교·판단」의 이름을 「ETF보유 및 후보 선정」으로 바꾸고 「ETF 비교하기」 폴더는 없앴다. 그룹 바로 아래 = 보유 · 섹터요약 · 후보리스트 · 보유와 후보 비교 · ETF 구성종목 · AI 투자 세션. 메뉴 key 17개(보완: 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」 · §16).
- **A 「오늘의 투자 점검」**:
  - 「보유 점검」 · 「잘 오르는 ETF」 두 카드로 합쳤다(「자세히」 두 칸 없앰).
  - 보유 점검 = 「보유」와 같은 요약 응답의 `price_flow` · 종목 단위(계좌 합산) · 판정 수 따로.
  - 잘 오르는 ETF = 카드 자체 기간(1일 · 1개월 · 3개월 · 기본 저장) · 제외 4종 고정 · 공통 기간 선정 1 ~ 3위.
  - 「자료 · 연구 상태」 바로 위에 [시장 근거와 다른 변화 보기] 접기(처음 접힘): 지금(보완 2차 · 형수님 결정 2026-11-13 뒤) ① 수급 · VIX · 원/달러 · WTI([VIX 다시 받기] 포함) · ② 시장 흐름 상세(기간별 흐름 · 날짜별 사건) · ③ 전일 자료 미완료(미완료일 때만). KODEX 200 판정 근거 · 코스피 공식 종가 · 차트는 접기 밖 당일 판정 아래(§17-10).
  - 머리 버튼 = [요약 다시 읽기] · [최신 자료 갱신] 한 번.
- **[최신 자료 갱신]**: 새 `POST /refresh/all` · `GET /refresh/all/status`. PC 서버가 보유 현재가 → 기존 시장 갱신 시작 순으로 잇는다.
  - 연타 · 다른 탭에서 눌러도 서버가 진행 중 작업으로 연결한다(그 작업이 시작한 시장 갱신이 아직 도는 동안 포함 · 보유 현재가 재조회 없음).
  - 「보유 현황」 [시세 갱신 (Naver)]은 묶음 작업을 만들지 않는다. 겹치면 보유 현재가 조회만 서버에서 한 번(single-flight)으로 묶인다.
  - 시장 단계는 기존 `post_market_refresh` 그대로(6시간 간격 · VIX 다시 받기 중 거절). 대기면 다음 가능 시각과 지금 기준일을 보인다.
- **B 네 메뉴**: 화면마다 조회 조건 · 저장된 기본 기간을 따로 쓴다(`krx.screenBasis.<화면>.v1`). 저장값을 읽지 못하거나 쓸 수 없는 값이면 그렇게 안내한다(저장 없음과 구분 · 처음 열 때 그 이유로 1개월로 시작했으면 그렇게 · 다른 탭 저장 뒤 · 기간을 바꾼 뒤에는 지금 조회 기간을 그대로 적음 · §12 · §14).
  - 새 `GET /market/etf-detail?tickers=`(최대 30): 1 · 3 · 6 · 12개월 · 최근 5 · 20구간 · 20구간 KODEX 200 차이(시작 · 끝이 모두 같을 때만) · 같은 기간 KODEX 200 · 고점 대비 · 시장가 · NAV · 괴리율. 계산된 0 · 값 없음 · 기간 다름 · 개별 주식 NAV 해당 없음을 나눈다.
  - 행 상세는 그 종목만 읽고 [표]는 보이는 30개를 한 번에 읽는다. 「보유와 후보 비교」는 두 종목을 한 번에 읽는다.
  - 판단 근거 미리보기(후보)는 그 화면의 공통 기간 목록(`list_source = "common_period"` · 쪽 · 순위 · 날짜 · 가격 시점 · 화면이 본 수익률)으로 서버가 대조한다. 어긋나면 "목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요."
  - 미리보기는 한 저장 판으로만 만든다: 이 종목 상세를 맨 앞 · 맨 끝에 한 번씩 읽어 같을 때만 승인한다(조립 중 같은 날 재저장 = 같은 안내 · §12).
  - B 화면의 보유 미리보기는 후보 목록과의 관계를 그 화면 조건의 공통 기간 목록으로 확인한 것만 적는다(목록 위치 · 하위 목록 구성종목 노출 · 같은 기간 KODEX 200). 예전 '현재 1개월 상위 10 후보' 줄은 이 경로에서 쓰지 않는다.
  - 「후보리스트」 「이 목록으로 할 일」 = 고른 쪽 최대 30개를 선정 순서로 AI 투자 세션 · ETF 구성종목에 넘긴다. 기존 초안 형식 · 시장 판정 스냅샷 · 6개월 시장 흐름 글(기간 · 날짜 포함). 「ETF 구성종목」 쪽도 넘긴 범위를 화면 머리와 AI 질문 글 머리에 적는다.
- **C 정리**: C 전용 30파일을 `archive/poc6_29_market_discovery/` 로 `git mv`(빌드 · 시험 범위 밖 · README). [신규 ETF 관찰 후보 갱신]은 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」(보완 · §16 · 처음 제출본은 「개발·실험용」 [미사용 기능] 구역). 재진입 창 이동 값 = `today_check`.
- **바꾸지 않은 것**: `market_topn.py` · `pc_etf_compare_summary.py` · DB 표 · OCI · PUSH · Telegram · 새 의존성 · 새 외부 조회 0.

## 1. 처리한 요구사항

### 1-1. PLAN 판정 질문별

| 항목 | 상태 | 근거(코드 · 시험) |
|---|---|---|
| Q1 · Q2 화면별 조건 · 기본 기간 · A 제외 4종 고정 | DONE(§12 · §14 정정 포함) | `frontend/lib/etfCompareCondition.ts`(`setScreenCondition` today 고정 · `readSavedBasis` 네 상태 · `saveScreenBasis` 다시 읽기 확인) · `BasisSaveRow`(`workbench/CompareHead.tsx` · 읽기 실패 · 쓸 수 없는 값 안내) · 「보유」 조회 기준 + 기본 저장 · 시험 `lib/etfCompare.test.ts` 「화면별 조회 기준 · 기본 기간 저장」 5건 · 「저장 기간 상태 넷」 5건 · `SectorSummaryView.test.tsx` 「저장값 안내 = 지금 조회 기간과 맞춤」 34건 · `SectorSummaryView.test.tsx` · `HoldingCandidateCompareView.test.tsx` 조건 분리 |
| Q3 두 메뉴 위치 | DONE | `LeftSidebar.tsx` 「ETF보유 및 후보 선정」 아래 「ETF 구성종목」 · 「AI 투자 세션」 · `LeftSidebar.test.tsx` |
| Q4-1 상세 수치 · [표] 묶음 읽기 · 0 / 없음 / 기간 다름 / NAV 해당 없음 구분 | DONE | `app/pc_etf_row_detail.py` · `GET /market/etf-detail`(`app/api_etf_compare.py`) · `workbench/DetailNumbers.tsx` · `RankingTable.tsx` · `tests/test_poc6_29_etf_detail.py` · `JudgmentWorkbenchView.test.tsx` · `HoldingCandidateCompareView.test.tsx` |
| Q4-2 미리보기 = 화면의 공통 기간 목록 · 어긋나면 다시 읽기 안내 · 보유 미리보기의 후보 관계는 그 화면 조건으로 확인된 것만 | DONE(§10 · §12 정정 포함) | `app/decision_preview_common_period.py :: load_common_period_bundle(상세 두 번 읽기 · 한 저장 판), _matches(basis_value), holding_list_context(같음)` · `app/api_decision_draft_preview.py` · `app/decision_draft_preview_service.py :: _holding_sections` · `EtfRowDetail.tsx :: commonPeriodQuery, holdingScopeQuery` · `tests/test_poc6_29_decision_preview_common.py`(보유 관계 · 값 대조 · 조립 중 재저장 포함) · 화면 시험(후보리스트 · 보유 · 보유와 후보 비교) |
| Q5 목록 넘기기(고른 쪽 최대 30 · 선정 순서 · 범위 글 · 기존 형식 · 시장 흐름 기간 · 날짜) | DONE(§10 정정 포함) | `workbench/ListTransfer.tsx` · `lib/etfExposureDraft.ts`(list_scope) · `lib/marketDiscoveryCopyText.ts`(listScope) · `ETFExposureView.tsx` · 시험 `KospiStatusSurfaces.test.tsx`(시장 판정 스냅샷 · 읽기 실패) · `MarketFlow.test.tsx`(6개월 글) · `JudgmentWorkbenchView.test.tsx`(AI · 구성종목 두 경로) |
| Q6 · Q12 미사용 기능 | DONE(RESULT 판정 §4 보완 · §16) | `UnusedFeatureView.tsx`(「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」) · `LeftSidebar.tsx` 폴더 · `DiagnosticsView.tsx`(옮겼다는 한 줄 + 이동) · `UnusedFeatureView.test.tsx` · `DiagnosticsView.test.tsx` · `LeftSidebar.test.tsx` |
| Q7 [최신 자료 갱신] 기본안 | DONE(실제 갱신은 사용자 화면 확인 · §7) | `app/pc_refresh_all.py` · `app/holdings_quote_refresh.py` · `today/useTodayRefresh.ts` · `useMarketRefresh.adopt` · `useMarketVixRetry.absorbStatus` · `tests/test_poc6_29_refresh_all.py` · `TodayInvestmentCheckView.test.tsx` 갱신 시험 · `TodayMarketFlow.test.tsx` · `today/TodayVixRetry.test.tsx` |
| Q8 시장 근거 기간 | DONE | A 접기 ②(지금 번호 · 처음엔 ③)의 기간은 그 카드 안에서만 · B 미리보기 `flowPeriod = "6M"`(`EtfRowDetail.tsx :: B_FLOW_PERIOD`) |
| Q9 후보리스트 [목록 \| 표] | DONE | `RankingList.tsx` · `RankingTable.tsx` · `JudgmentWorkbenchView.test.tsx` |
| Q10 보유 집계 = `price_flow` · 종목 단위 | DONE | `today/CheckCards.tsx :: countHoldings` · `today/TodayRiskStrip.test.tsx` 11건(모두 판정 못 함 = 셀 수 없음 포함) |
| Q11 섹터 · 순위 자기 조건 | DONE | `SectorSummaryView.tsx`(sector) · `JudgmentWorkbenchView.tsx`(candidates) · 각 화면 시험 |
| Q13 옛 기본 기간 A 만 한 번 | DONE | `readSavedBasis("today")` · `lib/etfCompare.test.ts` 「판정 Q13」 |
| Q14 C 전용 파일 보관 | DONE | `archive/poc6_29_market_discovery/` 30파일 · README · 활성 소스 import 0(§6) |
| Q15 한 Step · 순서 | DONE | A + 갱신 → B 네 메뉴 + 수치 → 미리보기 · 넘기기 · C 진입점 순으로 구현 · 통합 회귀 마감 1회(§8) |
| Q16 이동 안내 = 새 메뉴 이름 · 저장 출처 값 유지 | DONE | 화면 안내 글 정정(§4) · `source_screen` 기존 값 유지 · `describeDraftOrigin` |
| Q17 메뉴 '후보' 예외 세 곳 | DONE | `LeftSidebar.test.tsx` · `TodayInvestmentCheckView.test.tsx` AC-7 |

### 1-2. 판정 §3 완료 확인

| 확인 | 상태 | 근거 |
|---|---|---|
| 1 화면별 조건 | 자동 시험 · 격리 실측 DONE · 저장 후 다시 열기는 사용자 화면 확인 | 시험 = 다섯 화면 조건 분리 · 저장 키 · Q13(§1-1). 실측(§9-1): A 1개월 1 ~ 3위 = 「후보리스트」 1개월 상위 1 ~ 3위(같은 종목 · 같은 값). 3개월 공통 기간 1 ~ 3위는 예전 C 목록과 2위가 다름(예전 2위 488210 은 마지막 가격 9/23 · 공통 기간 목록은 끝일이 달라 뺌). 하락 집계 A '보유 29종목 중 25종목 하락 · 판정 29종목' = POC6-28 「보유」 '최근 하락 25'와 같은 수 |
| 2 판단 근거 | DONE(격리 실측 · 미리보기 · AI 초안은 시험) | §9-2: B 3개월 상위 10위(428560) = 새 경로 정상 · 예전 경로는 '찾지 못했습니다' 재현 · 1개월 상위 15위 · 하위 1위(「섹터요약」) · 보유 한 종목 정상 · 순위 · 가격 시점이 어긋나면 '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.' · 미리보기 글에 '「후보리스트」 3개월 상위 10위 · 공통 기간 8/12 → 11/10' |
| 3 상세와 표 | DONE(격리 실측 · 화면) | §9-3: 같은 종목 단독 = 30개 묶음 = 두 종목 응답이 같은 값 · 1개월 상세 = 요약 같은 값 · 같은 날짜 · 자료 부족 예(9/15 상장) '기간 다름 · 실제 9/15 → 11/10' · 보유 개별 주식 3종목 NAV '해당 없음' · A 시장 근거 접기 = 처음 접힘 · 「자료 · 연구 상태」 바로 위(§9-4) |
| 4 갱신 | 자동 시험 DONE · 실제 갱신은 사용자 화면 확인 | 백엔드 `test_poc6_29_refresh_all.py`(동시 시작 = 같은 작업 · 그 작업이 시작한 시장 갱신이 도는 동안도 같은 작업 · 보유 현재가 single-flight · 시장 대기 · 일부 실패 · 건너뜀 · 보유 단계 예외에도 시장 단계 진행) · 화면 시험(연타 · 다른 탭 이어 보기 · 대기 = 다음 가능 시각 · VIX 다시 받기 진행 · 끝나면 풀림 · 다시 읽기 실패를 완료로 보이지 않음 · 화면을 떠난 뒤 응답 무시). 격리 서버에서 개발자는 누르지 않음(새벽 · 실제 외부 조회 · §7) |
| 5 메뉴 이전 | DONE | 메뉴 16(보완 뒤 17 · §16) · 격리 화면 8메뉴 렌더 · 콘솔 · HTTP 오류 0 · 옛 이름 0(§9-4) · 재진입 창 이동 값 `today_check`(백엔드 · 화면 시험) · 정비 목록 · 「자료 최신화 필요」 = [최신 자료 갱신] · AI · 구성종목 초안 = 「후보리스트」 「이 목록으로 할 일」 · 두 수동 초안 = 「개발·실험용」(실행 버튼 = 보완 뒤 「미사용 기능 › 신규 ETF 관찰 점검」) · 보관 30파일 import 0 · 통합 회귀 마감 1회(§8) |

## 2. 변경된 파일 목록

`git status --short --untracked-files=all` 실측(작업 트리 · 커밋 없음 · 보완 뒤 2026-11-12 16:4x): 수정 68 · 신규(stage · index 추적) 49 · 이름변경(보관 · stage 됨) 30 · 미 stage 0 · 미추적 0. 보완에서 더한 · 바꾼 파일은 §16-6(검증자 r3 때는 123개 = 27 · 66 · 30).

- **백엔드 신규 4**:
  - `app/decision_preview_common_period.py`: 신규
  - `app/holdings_quote_refresh.py`: 신규
  - `app/pc_etf_row_detail.py`: 신규
  - `app/pc_refresh_all.py`: 신규
- **백엔드 수정 7**:
  - `app/api.py`: 수정
  - `app/api_decision_draft_preview.py`: 수정
  - `app/api_etf_compare.py`: 수정
  - `app/decision_draft_preview_service.py`: 수정
  - `app/decision_preview_lines.py`: 수정
  - `app/decision_preview_sources.py`: 수정
  - `app/reentry_review/models.py`: 수정
- **백엔드 시험 신규 3**:
  - `tests/test_poc6_29_decision_preview_common.py`: 신규
  - `tests/test_poc6_29_etf_detail.py`: 신규
  - `tests/test_poc6_29_refresh_all.py`: 신규
- **프론트 신규 10**:
  - `frontend/app/components/HoldingCandidateCompareView.tsx`: 신규
  - `frontend/app/components/SectorSummaryView.tsx`: 신규
  - `frontend/app/components/today/MarketEvidenceFold.tsx`: 신규
  - `frontend/app/components/today/useTodayRefresh.ts`: 신규
  - `frontend/app/components/workbench/DetailNumbers.tsx`: 신규
  - `frontend/app/components/workbench/ListTransfer.tsx`: 신규
  - `frontend/app/components/workbench/RankingTable.tsx`: 신규
  - `frontend/app/components/workbench/compareSelection.ts`: 신규
  - `frontend/lib/api/etfDetail.ts`: 신규
  - `frontend/lib/api/refreshAll.ts`: 신규
- **프론트 수정 40**:
  - `frontend/app/components/AISessionsCreateTab.tsx`: 수정
  - `frontend/app/components/AISessionsView.tsx`: 수정
  - `frontend/app/components/DashboardView.tsx`: 수정
  - `frontend/app/components/DataStatusView.tsx`: 수정
  - `frontend/app/components/DiagnosticsView.tsx`: 수정
  - `frontend/app/components/ETFExposureView.tsx`: 수정
  - `frontend/app/components/JudgmentWorkbenchView.tsx`: 수정
  - `frontend/app/components/LeftSidebar.tsx`: 수정
  - `frontend/app/components/MainPanel.tsx`: 수정
  - `frontend/app/components/NavDiscountPlaceholderCard.tsx`: 수정
  - `frontend/app/components/TodayInvestmentCheckView.tsx`: 수정
  - `frontend/app/components/WorkbenchHoldingsView.tsx`: 수정
  - `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx`: 수정
  - `frontend/app/components/holdings_manage/reentryFixtures.ts`: 수정
  - `frontend/app/components/marketflow/MarketFlowCard.tsx`: 수정
  - `frontend/app/components/today/CheckCards.tsx`: 수정
  - `frontend/app/components/today/FreshnessCard.tsx`: 수정
  - `frontend/app/components/today/MaintenanceQueueSection.tsx`: 수정
  - `frontend/app/components/today/MarketFlowBlock.tsx`: 수정
  - `frontend/app/components/today/maintenanceQueue.ts`: 수정
  - `frontend/app/components/today/summaryLines.ts`: 수정
  - `frontend/app/components/useMarketRefresh.ts`: 수정
  - `frontend/app/components/useMarketVixRetry.ts`: 수정
  - `frontend/app/components/workbench/CompareHead.tsx`: 수정
  - `frontend/app/components/workbench/EtfRowDetail.tsx`: 수정
  - `frontend/app/components/workbench/HoldingRowDetail.tsx`: 수정
  - `frontend/app/components/workbench/RankingList.tsx`: 수정
  - `frontend/app/components/workbench/SectorSummary.tsx`: 수정
  - `frontend/app/components/workbench/holdingParts.tsx`: 수정
  - `frontend/app/globals.css`: 수정
  - `frontend/lib/aiSessionsDraft.ts`: 수정
  - `frontend/lib/api/dashboardKeys.ts`: 수정
  - `frontend/lib/api/decisionDraftPreview.ts`: 수정
  - `frontend/lib/api/index.ts`: 수정
  - `frontend/lib/etfCompare.ts`: 수정
  - `frontend/lib/etfCompareCondition.ts`: 수정
  - `frontend/lib/etfCompareTestFixtures.ts`: 수정
  - `frontend/lib/etfExposureDraft.ts`: 수정
  - `frontend/lib/marketDiscoveryCopyText.ts`: 수정
  - `frontend/vitest.setup.ts`: 수정
- **프론트 시험 신규 4**:
  - `frontend/app/components/DiagnosticsView.test.tsx`: 신규
  - `frontend/app/components/HoldingCandidateCompareView.test.tsx`: 신규
  - `frontend/app/components/SectorSummaryView.test.tsx`: 신규
  - `frontend/app/components/today/TodayVixRetry.test.tsx`: 신규
- **프론트 시험 수정 17**:
  - `frontend/app/components/JudgmentWorkbenchView.test.tsx`: 수정
  - `frontend/app/components/KospiStatusSurfaces.test.tsx`: 수정
  - `frontend/app/components/LeftSidebar.test.tsx`: 수정
  - `frontend/app/components/SelectedPreviewAISession.test.tsx`: 수정
  - `frontend/app/components/TodayInvestmentCheckView.test.tsx`: 수정
  - `frontend/app/components/WorkbenchHoldingsView.test.tsx`: 수정
  - `frontend/app/components/holdings_manage/ReentryReviewDialog.test.tsx`: 수정
  - `frontend/app/components/marketflow/MarketFlow.test.tsx`: 수정
  - `frontend/app/components/today/StoredVolumeAndPriceBasis.test.tsx`: 수정
  - `frontend/app/components/today/TodayFolds.test.tsx`: 수정
  - `frontend/app/components/today/TodayMarketFlow.test.tsx`: 수정
  - `frontend/app/components/today/TodayRiskStrip.test.tsx`: 수정
  - `frontend/app/components/today/TodaySummary.test.tsx`: 수정
  - `frontend/app/components/today/TodayTopCards.test.tsx`: 수정
  - `frontend/app/components/today/maintenanceQueueVix.test.ts`: 수정
  - `frontend/app/components/today/summaryLines.test.ts`: 수정
  - `frontend/lib/etfCompare.test.ts`: 수정
- **문서 신규 6**:
  - `archive/poc6_29_market_discovery/README.md`: 신규
  - `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_DESIGN_V1.md`: 신규
  - `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_PLAN_DECISION_2026-11-12.md`: 신규
  - `docs/ai_plan/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_MOCKUP.html`: 신규
  - `docs/ai_plan/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_PLAN_V1.md`: 신규
  - `docs/ai_result/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT.md`: 신규
- **문서 수정 2**:
  - `docs/PROGRAM_TRUTH.md`: 수정
  - `docs/STATE_LATEST.md`: 수정
- **보관(이름변경) 30**: `frontend/…` → `archive/poc6_29_market_discovery/frontend/…`(같은 상대 경로 · 목록 = 보관 README)

## 3. 신규 추가된 의존성

- 없음

## 4. 지시문 외 변경

설계 · 판정에 이름이 없지만 이번 변경이 만든 낡은 글 · 끊긴 연결을 고치느라 바꾼 것이다.

- **옛 화면 · 버튼 안내 글(판정 Q16 이동 안내의 연장)**: 없어진 화면 · 버튼으로 가라는 글을 새 이름으로 고쳤다.
  - 「AI 투자 세션」(`AISessionsView.tsx` · `AISessionsCreateTab.tsx`) · 「ETF 구성종목」(`ETFExposureView.tsx` · `NavDiscountPlaceholderCard.tsx`) · 「데이터 상태」(`DataStatusView.tsx`) · LEGACY 대시보드(`DashboardView.tsx`) · B 빈 자료 안내(`CompareHead.tsx :: NOT_OK_TEXT`).
  - 예: 'Market Discovery 에서 후보를 조회한 뒤 AI Sessions로 넘기기' → '「후보리스트」에서 목록을 고른 뒤 [이 목록을 AI 투자 세션으로 넘기기]'.
  - 「데이터 상태」의 'Market Discovery' 글은 이번 단계 전부터 낡아 있던 것이다.
- **재진입 창 이동 안내 설명**(`app/reentry_review/models.py :: NAVIGATION` note · `reentryFixtures.ts`): [최신 자료 갱신]이 보유 현재가부터 받으므로 '보유 현재가를 받은 뒤 전체 ETF …'로 고쳤다. 판정 Q14가 요구한 메뉴 값 `today_check` 와 함께 바꿨다.
- **「보유」 보유 근거 실패 안내**(`workbench/holdingParts.tsx :: evidenceNotice`): 행 상세의 '월간 수익률(보유 근거)' 줄을 종목 상세 수치로 바꾸면서(판정 Q4-1) 보유 근거는 가격 흐름 대체에만 쓰인다.
  - 그래서 안내 글에서 '월간 수익률(보유 근거)'을 뺐다.
  - 모든 보유가 요약 가격 흐름으로 보이면 보유 근거 실패는 화면 값에 영향이 없으므로 안내하지 않는다(보이는 값을 '못 보인다'고 하지 않음 · POC6-28 r3 F5 계약).
- **A 두 카드의 '다시 읽기 실패 · 이전 값 표시 중' 줄**(`today/CheckCards.tsx`): 예전 「보유 점검」 카드에 있던 계약(실패 원천만 이전 값 + 그 시각 · 완료로 위장 안 함)을 새 원천(보유 · 잘 오르는 ETF · 보유 하락 판정 요약)으로 이었다.
- **최근 큰 변화 '외 N건' 줄**(`today/MarketFlowBlock.tsx`): 예전 A의 「시장 흐름 자세히」 펼침(전체 사건 목록)이 접기 ③(`MarketFlowCard` · 지금 번호는 ② · §17-10)으로 옮겨져, '외 4건 · 전체 7건은 아래 [시장 근거와 다른 변화 보기] ③에서 · 위 저점 문장과 같은 1건은 요약에서 뺌'으로 자리를 알렸다(지금 문장은 아침 요약 최근 변화의 '전체 N건은 아래 … ②에서' · §17-2).
- **CSS**(`frontend/app/globals.css` 끝 26줄): 새 화면이 쓰는 클래스(표 감싸기 · 표 · 보유와 후보 비교 고르기 · 잘 오르는 ETF 1 ~ 3위 · 시장 근거 접기)가 정의돼 있지 않아 더했다. 12열 표는 가로 스크롤 안에 둔다.
- **방어 · 정정(이번 단계의 새 코드 안)**:
  - 시장 근거 접기가 `regime_reasons` 칸 없는 응답에서 화면 전체를 멈추던 것 → 빈 목록으로 읽음.
  - 상세 수치 hook 이 종목이 아직 없을 때 빈 요청을 보내던 것 → 요청하지 않음.
  - 묶음 작업 상태가 사라지면(서버 재시작) '갱신 중'이 오래 남던 것 → 멈추고 알림.
- **독립 검토 정정 중 지시문 밖 파일을 건드린 것(§10)**:
  - `lib/marketDiscoveryCopyText.ts` · `lib/etfExposureDraft.ts` · `ETFExposureView.tsx` · `NavDiscountPlaceholderCard.tsx`: 「ETF 구성종목」 경로가 넘긴 목록의 범위를 잃던 것(판정 Q5). 넘긴 범위가 없는 예전 초안은 기존 글 그대로.
  - `app/decision_preview_lines.py :: same_period_lines`(`scoped` 선택 인자) · `app/decision_draft_preview_service.py :: _holding_sections`: 보유 미리보기 후보 관계(판정 Q4-2 둘째 항목). 화면 조건을 보내지 않는 기존 호출은 그대로.
  - `useMarketVixRetry.ts :: absorbStatus`: 다른 경로 상태로 받은 진행 중 다시 받기를 따라감(C 에서 옮긴 hook · A 에서 버튼이 막힌 채 남던 것).
  - `workbench/CompareHead.tsx :: ConditionPanel` [기본값으로] = 이 화면에 저장한 기본 기간(화면별 저장을 넣으며 뜻이 바뀐 버튼).
- **검증자 r1 F2 정정 중 되살린 예전 C 계약**(`lib/etfCompareCondition.ts` · §12): 예전 「요즘 잘 오르는 ETF」 기본 기간(`marketBasisPreference.ts` · `MarketBasisDefaultRow.tsx`)에 있던 '저장 뒤 다시 읽어 같을 때만 성공' · '다른 탭에서 저장하면 저장 표시만 다시 읽음'을 화면별 저장으로 옮기며 빠뜨렸던 것을 되살렸다(지금 조회 조건은 바꾸지 않음).
  - `app/holdings_quote_refresh.py` · `app/pc_refresh_all.py` 주석의 「보유 현황」 버튼 이름 '[시세 갱신 (Naver)]'.

## 5. 알려진 한계 / 미완성

- **`market_topn.py` 의 빈 DB 오류 글**: '가격 데이터가 SQLite 에 아직 없습니다. 최신 시장 데이터 갱신을 실행하세요.'가 옛 버튼 이름 그대로다. PLAN §0 이 이 파일을 고치지 않기로 해서(OCI PUSH 가 함수로 직접 부름) 두었다. 시장 DB 가 아예 없을 때만 보인다.
- **보유 근거 응답의 'Market Discovery' 문구**: `holdings_market_evidence` 의 evidence note '현재 Market Discovery 후보에 포함되어 있지 않습니다.'(「확인 근거」에 보임)는 기존 백엔드 계약 · 시험 문장이라 두었다.
- **목록 넘기기 초안의 일부 스냅샷**: 공통 기간 목록 응답에 없는 단기 흐름(5 · 10 · 20일) · 자료 품질(NAV 포함) 스냅샷은 비운다(null). 「ETF 구성종목」 NAV 카드는 '넘긴 목록에는 NAV 없음 — 「후보리스트」 [표] · 행 상세'로 안내한다. AI 투자 세션 경로의 후보별 초과수익은 같은 기간 KODEX 200 1개월만 채우고 3개월 · KOSPI 대비는 비운다. 「ETF 구성종목」 경로는 넘길 때 종목 상세를 읽어 같은 기간 1 · 3개월을 채운다(못 읽으면 1개월만 목록 값).
- **A 진입 때 시장 갱신 상태 읽기 2회**: 시장 갱신 hook 과 VIX 다시 받기 hook(C 에서 옮김)이 각각 `GET /market/refresh/status` 를 1회씩 읽는다(읽기만 · C 화면과 같은 방식).
- **쓰이지 않는 코드**: `workbench/helpers.ts :: evidenceReturn`(예전 월간 수익률 줄) · `marketflow/TodayFlowLines.tsx`(POC6-27 부터 화면에서 안 씀 · 안의 글 '「요즘 잘 오르는 ETF」 시장 흐름에서 봅니다'가 낡음)는 지우지 않았다(파일 삭제 · 정리 범위 밖).
- **시험 파일 크기**: PLAN §0 은 `TodayInvestmentCheckView.test.tsx` 에 새 시험을 더하지 않겠다고 했으나, 옛 버튼 시험을 [최신 자료 갱신] 시험으로 바꾸고 대기 안내 시험 1건을 더했다(1,015 → 1,032줄 · 기준 1,450 안). VIX 흐름 시험은 새 파일(`today/TodayVixRetry.test.tsx`)에 썼다.
- **미리보기의 계산 비용**: 누를 때만 · 읽기 전용. 후보 미리보기 = 요약 1회 + 그 종목 상세 2회(§12) · 격리 서버 실측 약 0.8초. B 화면 보유 미리보기 = 기존 보유 근거 + 요약 1회 + 상세 2회 · 실측 약 2.1초(§12-3).
- **본 저장소의 같은 문서 사본**: 설계 · 판정 · PLAN · 목업 4개는 본 저장소(main 작업 폴더)에도 추적 안 된 사본이 있다(내용 같음 · `cmp` 확인). main 으로 옮길 때 이 사본과 겹친다.

## 6. 다음 검증자(Codex)에게 알릴 점

- **묶음 작업 상태는 프로세스 메모리**(`app/pc_refresh_all.py :: _job`): 서버를 다시 켜면 진행 기록이 사라진다. 화면은 '상태를 찾지 못했습니다'로 멈춘다(§4). 시장 단계는 시작 결과만 기록하고, 진행 · 완료는 기존 `GET /market/refresh/status` 가 계속 맡는다.
- **끝난 묶음 작업에 연결하는 조건**(`start_refresh_all` · `_market_running`): 지난 작업의 시장 단계가 `accepted` · `running` 이고 기존 시장 갱신 상태(메모리)가 같은 `refresh_id` 로 `running` 이면 새 작업 없이 그 작업 상태(`status = "running"` · `state = "done"`)를 준다. 상태를 못 읽으면 새 작업을 허용한다.
- **보유 현재가 single-flight**(`app/holdings_quote_refresh.py`): `POST /holdings/market/refresh` 와 묶음 작업이 같은 비행을 공유한다. 겹친 호출은 같은 결과를 받는다(네이버 조회 1번).
- **미리보기 대조 경계**(`app/decision_preview_common_period.py :: load_common_period_bundle` · `_matches`): 그 화면 조건의 요약을 다시 계산해 요청 `side` 쪽 목록에서 종목을 찾고, `rank` · 시작일 · 끝일 · 끝 가격 상태 · (보냈으면) `basis_value`(오차 1e-6)가 모두 같을 때만 받아들인다(같은 종목이 상 · 하위에 모두 있어도 고른 쪽으로 대조). 어긋나면 HTTP 200 · `status = "error"` · '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.'(`api_decision_draft_preview.py` `except ListChanged`). `list_source` 가 없으면 기존 경로 그대로다.
- **한 저장 판 확인의 범위**(§12-1): 맨 앞 · 맨 끝 상세 두 번이 같은지 본다. 상세 = 이 종목의 저장 가격으로 계산한 모든 구간 값(1일 · 5 · 20구간 · 1 · 3 · 6 · 12개월 · 고점 대비) · 끝일 행 저장 시각 · 069500 의 같은 기간 · 20구간 값 · 이 종목 최신 NAV 1행. 이 값들을 바꾸지 않는 저장(예: 069500 저장 시각만 · 이 종목 과거 행의 거래량만)은 같은 판으로 본다. 두 읽기 사이 A → B → A 로 되돌아간 저장은 구분하지 못한다. 보유 · 구성종목 자료(직접 보유 · 중복)는 가격 판 대조 대상이 아니다.
- **20구간 KODEX 200 차이**는 종목과 KODEX 200 의 실제 시작일 · 끝일이 모두 같을 때만 계산한다. 다르면 `period_differs` 와 두 쪽 날짜를 함께 돌려준다(`pc_etf_row_detail.py :: _excess`).
- **화면별 조건 저장 키**: `krx.screenBasis.<today|holdings|sector|candidates|compare>.v1`. 옛 `krx.marketDiscovery.defaultBasis.v1` 은 today 만, today 저장값이 비었을 때 한 번 옮긴다(옛 키는 지우지 않음 · 옮겨 적기만 실패하면 읽은 값을 쓰고 다음에 다시 옮김). 저장값 상태 = 저장됨 · 없음 · 허용 밖 값 · 읽기 실패(예전 C 판정 그대로 · §12-2). 안내 문구는 지금 저장 상태와 화면이 처음 조건을 만들 때의 저장 상태(`getStartStatus`)를 함께 보고 고른다(§14).
- **백엔드 전체 회귀 환경**: 작업 트리에는 실 DB 가 없어 시험 안전장치(라이브 DB 읽기 전용 사본)가 쓰는 세 DB 를 본 저장소에서 sqlite 백업으로 작업 트리 `state/` 에 복사해 돌렸다(git 무시 대상 · 회귀 전후 해시 §8).

## 7. 사용자 확인이 필요한 항목

- **사용자 격리 화면 확인: 완료**(2026-11-12 대화 회신). 사용자는 추가로 바꾸고 싶은 화면 사항은 설계자를 통해 후속 수정한다고 했다. 실제 [최신 자료 갱신] 외부 실행 여부는 이 회신으로 확대 해석하지 않는다. 해당 동작의 검증은 가짜 공급자·임시 자료 시험으로 구분한다.
- **지시문 외 변경 §4 의 안내 글 정정**(「AI 투자 세션」 · 「ETF 구성종목」 · 「데이터 상태」 · LEGACY 대시보드)이 화면 검토 범위를 넘는지.

## 8. 시험 결과

### 8-1. 백엔드(작업 트리)

- 정적 검사(바뀐 · 새 파이썬 14파일 · §10 정정 뒤): `black --check` = '14 files would be left unchanged' · `flake8` 종료 0 · `py_compile` 통과.
- 전체 회귀(마감 · §10 정정 뒤 · 2026-11-12 02:57:15 ~ 03:27:26): `5665 passed, 2 skipped, 1 warning in 1806.82s (0:30:06)` · 실패 0.
  - 회귀 시작 뒤 바뀐 코드 파일(`app` · `scripts` · `tests` · `frontend/app` · `frontend/lib` 의 py · ts · tsx · css) 0개(`find -newermt` 실측).
  - 회귀 환경: 작업 트리에 실 DB 가 없어 세 DB(시장 · 실행 상태 · 판단 근거)를 본 저장소에서 sqlite 백업으로 작업 트리 `state/` 에 복사했다(git 무시 대상). 회귀 전후 sha256 같음: `4b8eed1b…f925`(시장) · `bedbd24b…d04d`(실행 상태) · `a8be7288…c0ca5`(판단 근거).
  - 정정 전 1차 회귀(01:42 ~ 02:12)는 `1 failed, 5654 passed` 였다. 실패 1건(`test_ml_baseline_snapshot.py::test_same_snapshot_same_result_even_after_live_db_changes` · 두 실행의 불러온 모듈 해시 비교)은 회귀 도중 `app/market_topn.py` 를 HEAD 로 되돌린 시각(01:43:27)이 그 시험의 두 실행 사이였기 때문이다. 최종 `market_topn.py` 는 HEAD 와 같고, 2차 회귀에서 통과했다.
- 회귀 뒤 · 검증자 r1 전에 바꾼 파일 = `tests/test_poc6_29_etf_detail.py` 하나: 공개 저장소 대조에서 개별 주식 예시 코드가 실제 보유 종목 코드와 같아 가짜 코드(`STK001`)로 바꿨다. 이번 작업의 새 시험 파일만 바뀌어 전체 회귀는 다시 돌리지 않았다(그 파일 단독 `23 passed` · black · flake8 통과).
- 검증자 r1 정정 뒤(§12): 전체 회귀는 다시 돌리지 않았다. 바뀐 백엔드 파일 = 이번 작업의 새 모듈 `app/decision_preview_common_period.py` 와 그 새 시험 파일뿐이고, 이 모듈을 쓰는 곳은 `app/api_decision_draft_preview.py` 하나다(grep). 미리보기 관련 6파일 `211 passed` · 정적 검사는 §12-4.
- 공개 대조(stage 된 93파일의 더한 줄 · 실제 보유 29종목 · 기준 지수 069500 제외): 위 1건 외에 걸린 줄은 ① 기존 공개 시험 문장(`SelectedPreviewAISession.test.tsx` · 앞 글자만 바꾼 줄) ② 목업의 공개 순위 자료 ETF 이름(보유 표시 없음)뿐이다.
- 새 시험: `tests/test_poc6_29_etf_detail.py` · `test_poc6_29_decision_preview_common.py`(보유 관계 · 값 대조 · 조립 중 재저장 포함) · `test_poc6_29_refresh_all.py`(진행 중 시장 갱신 연결 · 보유 단계 예외 포함). 새 시험은 실 DB 를 열지 않는다(임시 DB · 가짜 조회).

### 8-2. 프론트(`frontend/` · 프로덕션 빌드 안 함)

- 마감 실측(2026-11-12 14:01 · §14 정정 뒤): `npx vitest run` = `Test Files 78 passed (78)` · `Tests 1235 passed (1235)` · `npx tsc --noEmit` 종료 0 · `npx eslint .` 종료 0.
- 새 시험 파일: `HoldingCandidateCompareView.test.tsx` · `SectorSummaryView.test.tsx` · `DiagnosticsView.test.tsx` · `today/TodayVixRetry.test.tsx`(보관 파일의 C 전용 시험 14개는 `archive/` 로 옮김 · README).
- 변이 확인(§10): 정정 3가지를 하나씩 되돌리면 `today/TodayVixRetry.test.tsx` 가 각각 1건씩 실패하고, 되돌린 내용을 복원하면 11건 모두 통과(복원 = 백업 내용 쓰기 · `cmp` 같음).
- 격리 화면 점검(headless Chrome · §9-4 · §10-1): 8메뉴 렌더 · 콘솔 · HTTP 오류 0 · 가로 넘침 0.

## 9. 격리 서버 · 실제 저장 자료 확인

- **백엔드 8001**: 작업 트리 `app` 을 scratch 감싸기(`iso_app.py` · 3001 출처만 CORS 허용)로 띄움 · `--reload` 없음 · `--lifespan off`(기동 작업 · OCI 기동 읽기 없음 → OCI 카드는 '확인 불가'가 정상).
- **프론트 3001**: 작업 트리 `next dev -p 3001` · `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8001`.
- **자료**: 작업 트리 `state/` 사본(본 저장소 2026-11-12 사본 · git 제외 · 큰 ML 연구 폴더는 06 전향 비교만). ETF 가격 끝일 11/10(961개 모두 장중 13:17 ~ 13:20 저장 · 잠정).
- 캡처 · 응답 본문은 실제 보유 종목명이 보여 저장소에 두지 않았다(scratch). 아래 표에는 공개 시장 자료(ETF 순위 · 수익률)와 개수만 적는다.

### 9-1. 화면별 조건 · 공통 기간 목록(`GET /market/etf-compare/summary` · 제외 4종)

| 기준 | 공통 기간 | 비교 | 기간 다름 | 상위 1 ~ 3위 |
|---|---|---|---|---|
| 1개월 | 10/12 → 11/10 | 961 | 17 | KODEX 인도Nifty50(453810) +16.03% · KODEX 글로벌비만치료제TOP2 Plus(476070) +15.37% · TIGER 인도니프티50(453870) +15.25% |
| 3개월 | 8/12 → 11/10 | 944 | 41 | TIGER 국고채30년스트립액티브(451530) +24.85% · RISE KIS국고채30년Enhanced(385560) +18.19% · KODEX 국고채30년액티브(439870) +14.68% |

- A 「잘 오르는 ETF」 카드(1개월) 1 ~ 3위 = 위 1개월 1 ~ 3위(화면 실측). 「후보리스트」 [표] 상위 1 ~ 3위도 같다.
- 예전 C 목록(`/market/topn/latest` 3개월) 1 ~ 3위 = 451530 · **488210** · 385560. 488210 은 상세 응답 마지막 가격일이 9/23(3개월 = `period_differs` · `end_differs`)인데 예전 목록은 끝일 11/10 으로 셌다. 공통 기간 목록은 끝일이 달라 뺀다(그래서 A · B 3개월 2위 = 385560).

### 9-2. 판단 근거 미리보기(`POST /decision-draft/preview` · 읽기 전용)

| 요청 | 결과 |
|---|---|
| B 3개월 상위 10위 428560 · 「후보리스트」 · 공통 기간 | `status = ok` · '- KODEX 미국ETF산업Top10 Indxx (428560) · 후보 ETF · 「후보리스트」 3개월 상위 10위 · 공통 기간 8/12 → 11/10' |
| 같은 종목 · 예전 경로(`list_source` 없음 · 상위 10 목록) | `status = error` · '현재 목록 조건에서 이 후보를 찾지 못했습니다. 목록을 다시 불러온 뒤 시도하세요.'(PLAN §1 재현 그대로) |
| 1개월 상위 15위 0048K0 | `ok` · '「후보리스트」 1개월 상위 15위 · 공통 기간 10/12 → 11/10' |
| 1개월 하위 1위 475300 · 「섹터요약」 | `ok` · '「섹터요약」 1개월 하위 1위 · 공통 기간 10/12 → 11/10' |
| 1개월 상위 10위인데 순위 11로 보냄 · 「보유와 후보 비교」 | `error` · '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.' |
| 1개월 상위 10위인데 가격 시점을 다르게 보냄 | `error` · 같은 안내 |
| 보유 한 종목(가림) | `ok` |

### 9-3. 상세 수치(`GET /market/etf-detail`)

- 1개월 상위 30개 묶음 · 상위 10위 단독 · 두 종목 요청에서 상위 10위 항목이 모두 같다. 상위 10위 1개월 상세 = 요약 같은 값 · 같은 날짜(13.3238% · 10/12 → 11/10).
- 1개월 상위 30: 모든 기간 · 20구간 차이 · NAV `ok`. 하위 · 3개월 목록에는 9 ~ 10월 상장 ETF 가 `period_differs`(`start_differs`)로 나온다. 예: 0239Y0(PLUS 코리아HBM반도체) 1개월 -34.32% · 3 · 6 · 12개월 = 값 없음 · 실제 9/15 → 11/10(0 으로 채우지 않음).
- 보유 연결 29종목 중 개별 주식 3종목: NAV `not_applicable` 3.

### 9-4. 화면(headless Chrome · 1400px · 8메뉴)

- 왼쪽 메뉴: 「오늘 확인」 오늘의 투자 점검 · 「ETF보유 및 후보 선정」 보유 · 섹터요약 · 후보리스트 · 보유와 후보 비교 · ETF 구성종목 · AI 투자 세션 · (이하 기존). 「요즘 잘 오르는 ETF」 없음.
- 8메뉴(오늘의 투자 점검 · 보유 · 섹터요약 · 후보리스트 · 보유와 후보 비교 · ETF 구성종목 · AI 투자 세션 · 개발·실험용) 모두 렌더 · 콘솔 오류 0 · 8001 HTTP 오류 0 · 페이지 가로 넘침 0 · 화면 글자의 옛 이름(「요즘 잘 오르는 ETF」 · 「ETF 비교하기」 · [최신 시장 데이터 갱신] · Market Discovery) 0.
- 「오늘의 투자 점검」: 머리 버튼 [요약 다시 읽기] · [?] · [최신 자료 갱신] · [시장 근거와 다른 변화 보기] 처음 접힘 · 「자료 · 연구 상태」 바로 위 · 보유 점검 '보유 29종목 중 25종목 하락 · 판정 29종목'.
- 「후보리스트」 [표]: 30행 · 12열 · 표 감싸기 안 가로 넘침 없음(1085 = 1085). 첫 확인 때 순위 칸이 '상위 / 10' 두 줄로 꺾여 순위 칸 줄바꿈을 막았다(CSS 한 줄).
- 「보유와 후보 비교」: 12항목 두 열(예: 1개월 = 각 종목 값 · 10/12 → 11/10).
- 「개발·실험용」: [미사용 기능] → 구역 열림.
- 실제 [최신 자료 갱신]은 개발자가 누르지 않았다(새벽 · 실제 외부 조회) — 사용자 화면 확인 항목(§7).

## 10. 독립 검토 1회와 정정(2026-11-12)

검증자에게 넘기기 전에 개발자가 읽기 전용 검토를 한 번 돌렸다. 관점 5개(백엔드 · A 화면 · B 화면 · 판정서 대조 · 문서 정확성)에서 각각 찾고, 관점마다 반박 검증을 1번 붙였다. 확인된 결함 26건(관점 사이 중복 포함 · 기각 1건)을 원인별 18가지로 묶어 모두 고쳤다.

| # | 결함(확인됨) | 정정 | 확인 시험 |
|---|---|---|---|
| 1 | B 보유 미리보기가 화면 조건과 무관한 '현재 1개월 상위 10 후보' 관계를 적음(판정 Q4-2 둘째 항목) | 보유 요청에 화면 조건(`list_source` · `screen` · 기간 · 제외)을 보내고, 서버가 그 조건의 공통 기간 목록 위치 · 하위 목록 구성종목 노출 · 같은 기간 KODEX 200(종목 상세)만 적음(`holding_list_context`) | 백엔드 2기간 × 2화면 · 조건 없는 기존 호출 그대로 · 잘못된 조건 실패 · 「보유」 · 「보유와 후보 비교」 화면 시험 · 격리 서버 실측(§10-1) |
| 2 | 같은 날 장중 재저장으로 가격만 바뀌어도 순위 · 날짜 · 상태가 같으면 대조를 통과 | 화면이 본 선정 기간 수익률(`basis_value`)도 보내고 서버가 비교 | 백엔드 값만 다름 → 다시 읽기 안내 · 화면 요청 칸 · 격리 실측 |
| 3 | 묶음 작업이 시장 갱신 시작 직후 끝나, 시장 갱신 중 다른 탭에서 누르면 보유 현재가를 다시 조회 | 그 작업이 시작한 시장 갱신이 아직 돌면 새 작업 없이 그 작업으로 연결 | 백엔드 연결 · 끝난 뒤 새 작업 · 대기 · 거절이면 묻지 않음 |
| 4 | 갱신 전 시세 시각(표시용) 읽기 오류가 보유 단계를 멈추고 시장 단계를 건너뜀 | 표시용 읽기 오류는 비움 · 보유 단계 예외에도 시장 단계 진행 | 백엔드 2건 |
| 5 | [VIX 다시 받기] 성공 뒤 A 카드 · 시장 흐름이 '불러오는 중'에 멈춤(지운 키를 다시 읽지 않음) | 지운 시장 자료(시장 판정 · 시장 흐름 · KOSPI · 보유 근거 · 요약)를 모두 다시 읽음 | `TodayVixRetry.test.tsx` · 변이(시장 판정만 다시 읽기)로 실패 확인 |
| 6 | '다시 받기 중' 깃발이 풀리지 않아 [최신 자료 갱신]이 막힌 채 남음 · 들어올 때 이미 도는 다시 받기를 따라가지 않음 | 깃발 대신 VIX hook 의 실제 진행 상태 · 다른 경로 상태로 받은 진행 중 다시 받기도 따라감 · 머리 줄 문장 '진행 중입니다(시장 자료 갱신은 끝난 뒤 시작할 수 있습니다)' | `TodayVixRetry.test.tsx` 3건 · 변이(따라가지 않음)로 실패 확인 |
| 7 | 보유를 하나도 판정 못 했을 때 A 가 '0종목 하락 · 비중 0%' | '하락 판정을 하지 못했습니다(판정 0종목)' · '비중 셀 수 없음'(「보유」 '—'와 같은 뜻) | `TodayRiskStrip.test.tsx` |
| 8 | 화면을 떠난 뒤 온 묶음 작업 응답이 멈추지 않는 시장 상태 확인을 시작 | 응답 처리 전 화면 생존 확인 | `TodayVixRetry.test.tsx` · 변이로 실패 확인 |
| 9 | ① 결과 줄은 3초 뒤 사라지는데 ② 대기 줄이 '위 ①' 을 가리킴 | '(보유 현재가는 이 대기와 별개로 받습니다)' | 화면 시험 |
| 10 | 보유 없음 결과 줄에 서버 원문의 영어 낱말 'holdings' | 서버 사유 코드를 한국어 문장으로 | `TodayInvestmentCheckView.test.tsx` |
| 11 | 「보유와 후보 비교」 [다시 불러오기] 뒤 상세가 '확인 중'에 멈춤 | 두 종목 상세를 바로 다시 읽음 | `HoldingCandidateCompareView.test.tsx` |
| 12 | 「ETF 구성종목」 NAV 카드가 늘 '데이터 없음 · 갱신하면 재수집' | 넘긴 목록이면 '넘긴 목록에는 NAV 없음 — 「후보리스트」 [표] · 행 상세' | `JudgmentWorkbenchView.test.tsx` |
| 13 | 「ETF 구성종목」 → AI 질문 글이 'Market Discovery 결과 [후보 ETF]'로 시작 · 상위/하위 · 기간 · 건수 없음 · 같은 기간 KODEX 200 '값 없음'(판정 Q5) | 넘긴 범위를 초안 · 화면 머리 · 질문 글 머리에 · '[목록 ETF — 선정 순서]' · 같은 기간 1 · 3개월 = 넘길 때 읽은 종목 상세 | `JudgmentWorkbenchView.test.tsx` |
| 14 | 비교 표 '최근 고점 대비'가 기간 다름 · 값 없음 사유를 숨김 | 행 상세와 같은 문장(`drawdownText`) | `HoldingCandidateCompareView.test.tsx` |
| 15 | [기본값으로]가 이 화면 저장 기간이 아니라 늘 1개월 | 이 화면에 저장한 기본 기간(없으면 1개월) · 4종 제외 | `SectorSummaryView.test.tsx` |
| 16 | [표] 아래 안내가 기간 시작을 '끝일에서 N일 뒤'로 거꾸로 적음 | '끝일 30 · 90 · 180 · 365일 전 이후 첫 저장일부터' | — |
| 17 | 보관한 VIX 버튼 흐름 시험(활성 hook)이 활성 시험에서 빠짐(판정 Q14) | A 조합으로 옮긴 `today/TodayVixRetry.test.tsx` 11건(표식 · 다른 id 무시 · 빠른 완료 · 실패 · 해당 없음 · 진행 따라감 · 거절 따라감 · 전체 갱신 뒤 다시 받기 · 화면 떠난 뒤) · README 정정 | 같은 파일 |
| 18 | 문서: 「보유 현황」 버튼 이름 · '이어 봄' 범위 · 메뉴 구조(그룹 이름 변경 · 폴더 없음) | PROGRAM_TRUTH · 결과서 · 주석 정정 | — |

기각 1건: '요약 다시 읽기만 실패해도 보유 현재가 업데이트 실패로 표시' — 반박 검증 판단: 보유 현재가 뒤 다시 읽기가 하나라도 실패하면 '실패'로 보이고 '완료'로 보이지 않는 것은 HEAD 부터의 계약(시험 'r5 A-1' · 'A-1(4) 거짓 완료 금지')이고, PLAN §3-2 가 그 다시 읽기 목록에 요약을 더하라고 했다. 새 문장은 실패한 원천을 '다시 읽기 실패: …'로 적어 더 구체적이다.

### 10-1. 정정 뒤 격리 서버 실측(8001 새 코드 · 실제 저장 자료 · 읽기 전용)

| 요청 | 결과 |
|---|---|
| 보유 ETF 한 종목(가림) · 화면 조건 없음(기존 호출) | `ok` · '현재 1개월 상위 10 후보' 문구 있음(기존 그대로) |
| 같은 종목 · 「보유」 3개월 조건 | `ok` · 그 문구 없음 · '후보 목록 위치(「보유」 조건 3개월 상·하위 30 …)' · '하위 목록과의 구성종목 노출' · '(이 종목 …)' 같은 기간 줄 있음 |
| 보유 개별 주식 한 종목(가림) · 같은 조건 | 위와 같음 |
| 후보 3개월 1위 · 본 수익률 그대로 / 값만 0.01 다르게 | `ok` / `error` · '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.' |
| 3001 8메뉴 다시 점검 | 콘솔 · HTTP 오류 0 · 가로 넘침 0 · 옛 이름 0 · 접기 처음 접힘 |



## 11. 검증자 r1 구현 검증(Codex · 2026-11-12)

대상은 작업 트리 `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_29`, 브랜치 `poc6-29-abc-refocus`의 staged 코드다. 기준 HEAD는 `2c40ea69cc569c875338df5055fc201b808d3440`이다. 설계 개정본·PLAN 판정·PLAN·개발 결과서·실제 변경을 확보해 대조했다. 사용자의 격리 화면 확인 완료 회신을 반영하며, 아직 구체화되지 않은 추가 화면 변경은 설계자 후속 작업으로 구분한다. 검증자는 실제 보유·금액·state·라이브 DB·로그·사용자 handoff를 읽지 않았다.

### 11-1. A. 기능/산출물 검증

- **A-1 지시 일치: 위반(F1 P2·F2 P3).** 화면별 조회 조건, A 상위 3개와 보유 판정 집계, B 메뉴·상세·표·비교, 갱신 단계 공유, VIX 후 다시 읽기, 공통 기간 미리보기·목록 전달·보관은 관련 코드와 집중 시험에서 확인했다. 다만 선택 목록을 대조한 뒤 상세를 다시 읽는 사이의 같은 날 가격 변경을 거절하지 못하며(Q4-2), 저장 기본 기간 읽기 실패를 저장 없음으로 표시한다(PLAN §3-1).
- **A-2 보고 정확성: 메타 실측 정정 및 기능 완료 한계 보고.** `git status --short --untracked-files=all`, `git diff --name-only HEAD`, `git ls-files`와 index 내용을 대조했다. 총 staged 123개 = 신규 27·수정 66·이름변경 30, 미 stage·미추적 0이다. §2의 ‘신규(추적 안 됨)’은 현재 Git 상태와 달라 검증자가 ‘stage·index 추적’으로 정정했다. 이 메타 오기는 반려 사유가 아니다. 실제 결함 F1·F2와 구분한다. 신규 실행/API 모듈·화면·시험·결과서는 실제 경로에서 추적된다. 결과서가 아직 본 저장소에 없다는 보고도 맞으며, 검증자가 main으로 복사하지 않았다.
- **A-3 산출물 정합성: 위반(F1·F2).** 일반 입력에서는 상세 값·날짜·부족 사유 및 화면 조건이 관련 시험과 일치한다. 그러나 재저장 경계에서는 선택 당시 +7.5602%였던 목록의 위치를 그대로 인증하면서 +29.0723%로 바뀐 상세 미리보기를 `status=ok`로 생성한다. 저장소 접근이 거절된 화면은 ‘기본 기간 1개월·저장 없음’으로 표시하고 읽기 실패를 알리지 않는다. 개발자의 실제 화면 수치는 개발자 근거로 유지하며 검증자가 실제 저장 자료를 새로 대조했다고 주장하지 않는다.
- **A-4 금지사항 위반: 없음.** 새 의존성·DB 스키마 변경·새 외부 공급자는 없고, 새 endpoint 3개는 판정 Q4-1·Q7이 허용한 PC 상세/갱신·상태 경로다. 보관 30건은 판정 Q14에 따른 rename이며 원본 삭제로 보지 않는다. 검증자는 제품 코드·제품 시험·실서버·OCI·커밋·push를 변경하거나 실행하지 않았다.

#### F1(P2) — 목록 대조와 상세 조회 사이의 같은 날 재저장을 놓침

- 위치: `app/decision_preview_common_period.py:222~243`, `load_common_period_bundle`의 `_matches` 뒤 `build_etf_detail` 및 `same_end` 검사.
- 요구: 판정 Q4-2와 PLAN §3-4는 화면의 조건·실제 날짜·가격 시점·선정 순위를 현재 결과와 대조하고 가격이 바뀌면 목록을 다시 읽게 한다. 개발자 §10 #2의 `basis_value` 검사도 이 목적이다.
- 실제: `_matches`는 첫 요약 읽기의 값만 검사한다. 그 뒤 상세를 별도 읽고, 첫 요약과 비교하는 것은 공통 끝 날짜뿐이다. 같은 날짜·같은 저장 상태의 가격이 바뀌면 그 새 상세 값으로 미리보기를 계속 조립한다. 이후 추가 근거 읽기도 같은 잠긴 입력을 공유하지 않는다.
- 독립 재현: 기존 `seeded` fixture의 임시 DB에서 상위 1위 요청에 화면 값 `basis_value=7.5602`를 보냈다. 요약 대조가 끝난 직후, 상세 함수가 읽기 직전에 그 종목 끝일 가격만 1.2배로 재저장했다. 날짜·상태는 그대로다. 실제 SQL 갱신과 실제 상세 계산을 사용했으며 공급자 호출·운영 데이터는 없다.
- 결과: 다시 읽기 안내 대신 HTTP 200·`status=ok`. [대상]은 같은 ‘「후보리스트」 1개월 상위 1위·10/12→11/10’이고 [가격 흐름]은 `1개월 +29.07%`, 상세 원값은 `29.0723`이다. 선택 당시 목록의 `7.5602`와 다른 가격 판인데 정상으로 인증된다. 재저장하지 않는 정상 대조군은 `ok`로 통과한다.
- 근거: 저장소 밖 `backend-boundary.py`, `backend-boundary.log`의 독립 재현 **1 failed·정상 대조군 1 passed**. 재현은 요약과 상세 사이 한 경계만 바꾸며 데이터 형식 손상이나 없는 API를 가정하지 않는다.

#### F2(P3) — 저장 기간 읽기 실패를 ‘저장 없음’으로 단정

- 위치: `frontend/lib/etfCompareCondition.ts:47~70`의 `readSavedBasis`·`savedOf`·`getScreenCondition`, 표시 `workbench/CompareHead.tsx:42~62`의 `BasisSaveRow`.
- 요구: PLAN §3-1은 저장·읽기 실패를 알리고 지금 조회를 유지한다고 명시한다. ‘저장값 없음’과 저장소에 접근하지 못한 상태는 다르다.
- 실제: `localStorage.getItem`이 예외를 내면 `readSavedBasis`는 null을 반환하고 이를 저장값 없음과 같은 상태로 캐시한다. 화면은 1개월로 시작하면서 ‘저장 없음·새로 고치면 1개월로 시작’이라고 적는다. 읽기 오류 표시는 없고, 저장 버튼 클릭 실패만 별도 안내한다.
- 독립 재현: 실제 「섹터요약」 컴포넌트를 가짜 요약 응답으로 렌더하고 `Storage.prototype.getItem`만 `SecurityError`를 던지게 했다. 표시 결과는 `기본 기간: 1개월 (저장 없음 · 새로 고치면 1개월로 시작)`이며 실패 안내가 없다. **독립 시험 1 failed**. 정상 화면별 저장·저장 버튼 실패·기간 독립성 시험은 계속 통과한다.
- 근거: 저장소 밖 `storage-boundary.test.tsx`, `storage-boundary.log`. 사용자 브라우저의 저장값이나 설정은 건드리지 않았다.

#### 실행한 검증과 재사용 범위

근거 폴더는 `/private/tmp/poc629-r1-verify-81lscypj/`다. index 소스를 이 폴더의 `src/`에 복사했고 실제 환경 파일·state·logs·사용자 handoff는 복사하지 않았다. 기존 라이브 쓰기 가드는 유지했다.

| 이번 검증자가 실행한 검사 | 결과 |
|---|---|
| 변경 프런트 시험 21파일 | **405 passed** |
| 관련 백엔드 시험 6파일 | **202개 고유 시험 통과** — 1차 200 passed 및 아래 합성 환경의 기존 smoke 2 passed |
| F1 독립 임시 DB 재현·정상 대조군 | **1 failed·1 passed** |
| F2 독립 화면 재현 | **1 failed** |
| staged 사본 타입 검사·변경 프런트 파일 eslint | 종료 0·오류 출력 없음 |
| 변경 Python 14파일 black --check·flake8·py_compile | 모두 종료 0(서식 변경 없음) |
| 보관 rename 30건 | **30/30 원문 바이트 동일·R100**, 활성 import 참조 0 |
| 검증 중 HEAD·index·작업 소스 대조 | `changes: []`, `problems: []`(결과서 기록 전) |

백엔드 1차 실행은 200 passed 외에 기존 smoke 2건이 사본의 기본 시장 DB 부재/표 부족으로 쓰기 가드에 걸렸다(2 failed·2 errors). 사본 안에 합성 가격과 기존 조회용 표를 준비해 이 2건만 다시 실행했고 모두 통과했다. 빈 DB와 가격만 있는 중간 준비 단계에서의 실패도 로그로 보존했다. 가드를 끄거나 실제 DB를 복사하지 않았으며, 이 시험 환경 의존을 제품 결함으로 집계하지 않는다. 최종 합성 DB 사본 hash도 전후 같았다.

개발자 전체 백엔드 5,665 passed·2 skipped, 프런트 78파일·1,193 passed 및 변이 근거는 반복하지 않았다. 회귀 뒤 실제 종목 예시를 가상 코드로 바꾼 새 상세 시험 23건은 이번 집중 시험에 포함됐다. build·브라우저 조작·실서버 조회·갱신 버튼·외부 조회·발송·실제 DB/보유 읽기·서버 재시작은 실행하지 않았다.

### 11-2. B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 있음(F2).** 저장소 읽기 예외를 값 없음으로 바꾼 뒤 기본 기간과 ‘저장 없음’ 표시로 진행한다. 출처 실패를 정상 값 부재로 간주하는 문제다.
- **B-2 단일 책임 위반: 추가 발견 없음.** 공통 기간 미리보기·종목 상세·보유 시세 single-flight·갱신 묶음과 화면 표시가 각 모듈로 분리됐다. `api.py`의 기존 본문 이동은 새 모듈을 통한 동일 endpoint 호출로 연결된다.
- **B-3 파일 책임 과다: 없음.** 변경 Python 최대는 `api.py` 584줄이다. 화면 최대 `DashboardView.tsx` 770줄, `TodayInvestmentCheckView.tsx` 682줄, 시험 최대 1,032줄로 KS-10 근접·임계 초과를 발견하지 않았다. fixture의 기존 책임도 같은 범위다.
- **B-4 실험/운영 경계 위반: 없음.** 관찰 후보 갱신 버튼은 승인된 「개발·실험용 › 미사용 기능」에 있고 자동 실행을 추가하지 않았다. 실험·수동 초안과 일상 탐색의 진입을 구분하며 저장 기록 출처 값은 유지한다.
- **B-5 배포/실행 경로 영향: 제출 범위 통과.** 보관 30파일은 HEAD의 원래 파일과 바이트 동일하며 `frontend/` 밖에 있다. frontend tsconfig·vitest 탐색 루트와 활성 import를 대조했다. 활성 frontend는 archive를 읽지 않고 기존 배포 스크립트에 옮긴 파일 경로 의존은 없다. 신규 라우터와 화면은 `api.py`·MainPanel·메뉴에서 연결되고 index 추적된다. 작업 트리 제출이며 main 또는 실사용 반영 완료를 뜻하지 않는다.
- **B-6 기술부채/구조적 퇴행: F1·F2 외 추가 발견 없음.** 공통 함수·응답 모양 재사용과 화면별 저장 범위는 명확하다. 목록과 상세를 서로 다른 판으로 섞어 조립하는 F1은 A의 동일 결함으로 묶고 새 구조 요구로 확대하지 않는다.

### 11-3. 기반 문서 준수

새 Markdown 5개(보관 README·설계·PLAN 판정·PLAN·결과서)는 보고된 보관/개발 문서 범위다. 신규 라이브러리·MongoDB·엔터프라이즈 패턴·새 UI 프레임워크·KS-10 발동은 발견하지 않았다. 기존 API와 운영 모델·OCI 수집/발송·`market_topn.py`는 이 변경에서 바꾸지 않았다. 화면별 공통 기간과 새 조회/미리보기/갱신 endpoint는 설계 판정의 직접 범위다.

### 11-4. 코드 안전성

**위험 수준: MEDIUM(F1), LOW(F2).** F1은 다른 저장 판의 가격을 선택 당시 목록의 검증 결과로 받아들이는 문제이고 F2는 확인 못 한 기본 설정을 없다고 단정하는 문제다. 새 외부 공급자·비밀값 노출은 없고, 기존 네이버 조회의 종목별 timeout은 유지된다. 실제 자금·계좌·보유·라이브 자료를 검증에 사용하지 않았다.

### 11-5. 범위 폭주

**폭주 수준: NONE.** 삭제된 메뉴를 가리키는 「AI 투자 세션」·「ETF 구성종목」·「데이터 상태」·LEGACY 대시보드 안내의 새 이름 정정은 판정 Q16 및 이번 메뉴 통합과 직접 연결된다. 추가 동작·판정 산식 변경으로 확대되지 않아 이번 검증에서 별도 반려 사유로 보지 않는다. 사용자가 언급한 향후 화면 변경은 아직 요구가 정해지지 않아 이번 검증에서 구현을 요구하지 않는다.

### 11-6. 종합 판정

**REJECTED(F1 P2·F2 P3).** 사용자 격리 화면 확인은 완료로 유지한다. 메뉴 통합·보관·일반 상세/미리보기·갱신 경로의 집중 시험 통과와 두 경계 결함을 구분한다. 기존 설계 판정 범위 안의 정정 사항이며 새 설계 결정을 요구하지 않는다. 커밋·push·main 반영·실사용 적용은 하지 않았다.

### 11-7. 검증자 수정 내역

검증자가 수정·stage한 저장소 파일은 **작업 트리의 이 결과서 하나**다. STATUS/VERIFIER, §2의 Git 추적 메타, §7의 사용자 화면 확인 완료 사실을 갱신하고 §11을 추가했다. 제품 코드·제품 시험·개발자 독립 검토 §10·설계·PLAN·STATE·PROGRAM_TRUTH는 수정하지 않았다. 본 저장소에 이 문서를 새로 복사하지 않았다. 독립 재현은 저장소 밖에만 작성했다.

## 12. 검증자 r1 정정(개발자 · 2026-11-12)

F1 · F2 모두 고쳤다. 같은 뿌리의 옆 경로(보유 미리보기 · 예전 C 저장 계약)도 함께 고쳤다. 설계 · PLAN 변경은 없다.

### 12-1. F1 — 미리보기를 한 저장 판으로만 승인

- 원인: 요약 대조 → 상세 → 추가 근거(단기 흐름 · 일간 점검 · NAV · 거래량 · 흔들림 · 이동평균)를 따로 읽고 끝일만 비교했다. 그 사이 같은 날 재저장이 있으면 다른 판의 값이 섞인다.
- 정정(`app/decision_preview_common_period.py :: load_common_period_bundle`): 이 종목 상세(`build_etf_detail`)를 **맨 앞**에 읽고 → 요약 대조(기존) → 추가 근거 → **맨 끝**에 상세를 다시 읽어 맨 앞과 같을 때만 승인한다. 다르면 `ListChanged` → '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.'
  - 맨 앞 · 맨 끝이 같으면 그 사이 요약 · 추가 근거도 같은 판을 읽은 것이다(요약이 본 이 종목 값 = 화면이 본 값은 기존 대조가 확인).
  - 확인 범위와 못 보는 경우는 §6 '한 저장 판 확인의 범위'.
- 같은 뿌리(`holding_list_context`): B 화면 보유 미리보기의 목록 위치(요약)와 같은 기간 KODEX 200(상세)도 같은 방식으로 묶었다. 다르면 관계를 적지 않고 '후보 목록과의 관계: 확인 불가 — {화면} 조건 {기간} 상·하위 30 목록을 읽는 동안 저장 자료가 바뀌었습니다. [다시 생성]으로 다시 확인하세요.'(미리보기는 열림 · 같은 기간 값은 '값 없음').
- 시험(`tests/test_poc6_29_decision_preview_common.py` · 임시 DB · 실제 SQL 재저장 · 실제 계산):
  - 후보 9건 = 재저장 시점 3(첫 상세 직후 · 요약 대조 직후 · 추가 근거 직전) × 재저장 3(이 종목 끝일 가격 1.2배 · 이 종목 끝일 저장 시각만 · KODEX 200 끝일 가격 0.1%) → 모두 '목록이 바뀌었습니다'.
  - KODEX 200 은 0.1% 로 바꾼다. 1.2배면 069500 자체가 상위 1위가 되어 순위 대조가 먼저 걸러, 다시 읽기 대조를 시험하지 못한다(임시 시험으로 확인).
  - 대조군 1건(같은 끼워 넣기 · 재저장 없음 → 정상) · 보유 3건(요약 직후 재저장 → 확인 불가 문장 · 위치 줄 없음).
- 변이 · 재현:
  - 고치기 전(stage 된 판) 코드 = 새 시험 **12 failed**(후보 9 · 보유 3).
  - 맨 끝 다시 읽기만 끔 = 후보 **8 failed**. 남은 1건(첫 상세 직후 이 종목 가격 변경)은 화면 값(`basis_value`) 대조가 잡는다.
  - 보유 경로 다시 읽기만 끔 = **3 failed**.
  - 복원 = 백업 내용 쓰기 · `cmp` 같음 · `PYTHONDONTWRITEBYTECODE=1`.

### 12-2. F2 — 저장 기간 상태를 넷으로(예전 C 판정 그대로)

- 원인: `readSavedBasis` 가 읽기 예외를 null(저장 없음)로 바꿨다. 예전 「요즘 잘 오르는 ETF」 코드(`archive/…/lib/marketBasisPreference.ts`)는 저장됨 · 없음 · 허용 밖 · 읽기 실패를 나눴고, 저장 뒤 다시 읽어 확인했고, 다른 탭 저장을 다시 읽었다. 화면별 저장으로 옮기며 이 셋을 잃었다.
- 정정(`frontend/lib/etfCompareCondition.ts` · `workbench/CompareHead.tsx :: BasisSaveRow`):
  - `readSavedBasis` → `{ basis, status }`(`saved` · `none` · `invalid` · `read_failed`). today 는 자기 칸이 `none` 일 때만 예전 값(허용 값)을 이어받는다. 옮겨 적기만 실패하면 읽은 예전 값을 쓴다.
  - 화면 문구(예전 C 문구 · `BASIS_READ_NOTICE`): 처음 열 때 읽기 실패 = '저장된 기본을 읽지 못해 1개월로 시작했습니다' · 허용 밖 값 = '저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다'. 지금 조회는 1개월 그대로 · [이 기준을 기본으로(1개월)]은 눌러서 바로잡을 수 있다. (이 문구를 쓰는 조건은 r2 F3 정정으로 좁혔다 → §14.)
  - `saveScreenBasis` = setItem 뒤 다시 읽어 같을 때만 성공(조용히 버려지는 저장 = 실패 안내).
  - 다른 탭 저장(`storage` 이벤트 · 화면 저장 키 · 예전 키 · 전체 지우기) → 저장 표시만 다시 읽는다. 지금 조회 조건 · 요약 요청은 그대로.
- 시험: `lib/etfCompare.test.ts` 「저장 기간 상태 넷」 5건 · `SectorSummaryView.test.tsx` 3건(검증자 재현과 같은 `SecurityError` = 실패 안내 · '저장 없음' 없음 · 1개월 조회 · 저장 성공 뒤 '저장됨' / 허용 밖 값 / 다른 탭 저장).
- 변이(각각 되돌린 뒤 복원 · `cmp` 같음): 읽기 실패 → 없음 = **3 failed** · 저장 뒤 다시 읽기 끔 = **1 failed** · 다른 탭 다시 읽기 끔 = **1 failed**.

### 12-3. 격리 서버 실측(8001 정정 코드로 다시 띄움 · 작업 폴더 사본 · 읽기 전용)

| 요청(제외 4종 · 화면이 본 값 포함) | 결과 |
|---|---|
| 「후보리스트」 3개월 상위 10위 | `ok` · 0.83초 · [대상] '「후보리스트」 3개월 상위 10위 · 공통 기간 8/14 → 11/12' |
| 1개월 상위 15위 · 1개월 하위 1위 | 둘 다 `ok` · 약 0.8초 |
| 위 셋을 화면 값만 0.01 다르게 | 셋 다 `error` · '목록이 바뀌었습니다 — 목록을 다시 읽고 다시 고르세요.' |
| 「보유」 보유 한 종목(1개월 · 종목은 적지 않음) | `ok` · 2.09초 · 목록 위치 줄 있음 · 섞임 안내 없음 · 예전 '현재 1개월 상위 10' 문구 없음 |

조립 중 재저장 자체는 실서버에서 일으키지 않았다(외부 갱신 미실행 · 시험 §12-1 로 확인).

### 12-4. 자체 검수

- 백엔드: 바뀐 2파일 `black --check`(2 files would be left unchanged) · `flake8` 종료 0 · `py_compile` 통과 · 미리보기 관련 6파일(`test_decision_draft_preview.py` · `test_holdings_selection_preview.py` · `test_poc5_23_decision_preview_bundles.py` · `test_poc5_24_selected_preview_session.py` · `test_poc6_29_decision_preview_common.py` · `test_poc6_29_etf_detail.py`) `211 passed`. 전체 회귀 생략 사유는 §8-1.
- 프론트: `npx vitest run` 78파일 `1201 passed`(정정 전 1,193 + 8) · `npx tsc --noEmit` 종료 0 · `npm run lint` 오류 0.
- 줄 수(KS-10): `decision_preview_common_period.py` 366 · `etfCompareCondition.ts` 188 · `CompareHead.tsx` 224 · 시험 `test_poc6_29_decision_preview_common.py` 493 · `etfCompare.test.ts` 391 · `SectorSummaryView.test.tsx` 219.
- 바뀐 파일 6개는 모두 §2 목록에 이미 있는 파일이다(신규 · 수정 구분 변화 없음).


## 13. 검증자 r2 재검증(Codex · 2026-11-12)

기준은 작업 트리 `poc6-29-abc-refocus`의 staged 코드다. r1 대비 변경은 백엔드 제품 1개·시험 1개, 프런트 제품 2개·시험 2개 및 문서 3개이며 개발자 보고와 같다. 원본 PLAN 판정·PLAN·결과서 §12·실제 diff를 대조했다. 사용자의 실화면 확인 완료와 설계자를 통한 후속 화면 변경 방침은 유지한다. §11의 r1 원문과 §12의 개발자 정정 기록은 보존한다.

### 13-1. A. 기능/산출물 검증

- **A-1 지시 일치: F1·F2 해소, F3(P3) 위반.** 후보 미리보기의 앞뒤 상세 대조, 보유 관계의 대조 실패 시 확인 불가 처리, 저장 기간의 상태 넷·저장 후 재확인·다른 탭 저장 표시 갱신을 확인했다. 기존 F1·F2 재현은 원문 그대로 통과한다. 다만 새로 복구한 다른 탭 갱신 뒤 오류/허용 밖 상태가 생기면, 실제 조회가 3개월인데 ‘1개월로 시작했습니다’라고 표시한다. 화면별 실제 조건과 저장 상태를 맞춰 읽는 판정 Q1·PLAN §3-1의 안내 계약에 남은 불일치다.
- **A-2 보고 정확성: 파일·수치 메타 일치.** 최소 Git 명령(`git status --short --untracked-files=all`, `git diff --name-only HEAD`, `git ls-files`)과 index를 대조했다. staged 123개(신규 27·수정 66·보관 rename 30), 미 stage·미추적 0이다. 정정 코드·시험 6개는 모두 기존 제출 목록에 있다. 실측 줄 수는 `decision_preview_common_period.py` 366·시험 493, `etfCompareCondition.ts` 188·`CompareHead.tsx` 224·`etfCompare.test.ts` 391·`SectorSummaryView.test.tsx` 219로 보고와 같다. 별도 숫자·줄 수 정정은 필요하지 않았다.
- **A-3 산출물 정합성: F1·F2 재현 통과, F3 안내 불일치.** 앞뒤 대조가 값 변경을 거절하고, 보유 관계를 확인할 수 없으면 정상 위치/같은 기간 수치로 채우지 않는다. 읽기 실패는 이제 저장 없음과 구분된다. 현재 조회를 보존하는 다른 탭 동작도 맞지만, 그때 표시되는 오류 문구가 실제 시작 기간과 모순된다. 정상 자료의 사용자 확인을 취소하거나 실제 서버 재확인을 요구하지 않는다.
- **A-4 금지사항 위반: 없음.** 새 파일·의존성·외부 공급자·DB 스키마·파일 삭제·운영 작업은 없다. 검증자는 제품 코드·제품 시험을 수정하지 않았고 실제 DB·보유·금액·서버·OCI·커밋·push에 접근하거나 쓰지 않았다.

**F1(P2) 해소 확인**

- r1 `backend-boundary.py`의 같은 날 재저장 및 정상 대조군 2건을 변경하지 않고 새 staged 사본에서 실행해 모두 통과했다. 개발자가 추가한 실제 SQL 재저장 9건과 보유 관계 3건·정상 대조군도 함께 통과했다.
- 후보는 첫 상세 → 목록/선택값 대조 → 추가 근거 → 마지막 상세 순서이며 상세가 다르면 `ListChanged`다. 보유 관계도 상세 둘 사이 목록 읽기를 두고 다르면 확인 불가 문장과 같은 기간 값 없음으로 처리한다.
- 이 판정은 결과서 §6에 공개된 **상세 값 대조 범위**의 확인이다. 모든 원시 행의 불변·DB 트랜잭션 일관성을 검증한 것으로 확대하지 않는다. 상세 밖 값만 바뀐 저장, A→B→A, 보유/구성종목 자료 제외 등 공개된 한계는 유지한다. 실서버에서 재저장·외부 갱신을 일으키지 않았다.

**F2(P3) 해소 확인**

- r1 `storage-boundary.test.tsx`의 SecurityError 재현을 수정하지 않고 재실행해 통과했다. 처음부터 읽기가 실패하면 ‘저장 없음’ 대신 읽지 못했다는 안내가 나오며, 이 경우 시작 조회는 실제로 1개월이다.
- 저장됨·없음·invalid·read_failed 구분과 today의 이전 기본값 이관, 저장 후 같은 값 재확인, 정상적인 다른 탭 저장 시 저장 표시만 갱신하고 조회/요청은 유지하는 시험이 통과한다.

#### F3(P3) — 다른 탭 상태 재조회 뒤 실제 3개월 화면에 ‘1개월로 시작’ 안내

- 위치: `frontend/app/components/workbench/CompareHead.tsx:46~55`의 `BASIS_READ_NOTICE`·`BasisSaveRow`. 상태 갱신 경로는 `frontend/lib/etfCompareCondition.ts:147~150`의 `onStorage`다.
- 원인: `read_failed`와 `invalid`라는 **현재 저장 상태**만으로 ‘1개월로 시작했습니다’라는 **시작 조회 이력**을 고정 표시한다. 다른 탭 저장은 현재 조회를 바꾸지 않으므로 이 두 사실은 같지 않다.
- 독립 재현은 실제 「섹터요약」 컴포넌트·가짜 요약 응답으로 진행했다.
  1. 이 화면 기본 기간을 3개월로 저장하고 연다. 실제 요청과 화면 조건은 3개월이다.
  2. 같은 키의 storage 이벤트에서 ① 저장소 재읽기 SecurityError 또는 ② 다른 탭의 허용 밖 값 `weekly`를 재현한다.
  3. 현재 조회는 3개월이고 요약 요청도 최초 1회 그대로임을 확인한다.
  4. 그러나 안내는 각각 ‘저장된 기본을 읽지 못해 1개월로 시작했습니다’, ‘저장된 기본 값을 쓸 수 없어 1개월로 시작했습니다’다. 실제로 1개월로 시작하거나 전환된 적이 없다.
- 결과: **독립 시험 2 failed**. 3개월 조회 유지·추가 요청 없음 단언은 통과했고, 실제 시작 기간과 모순되는 안내만 실패한다. 두 경우는 같은 원인의 표시 결함 한 건으로 묶는다. 계산·조회 조건 자체가 잘못됐다고 확대하지 않는다.
- 근거: 저장소 밖 `/private/tmp/poc629-r2-verify-20sbzp9o/storage-event-boundary.test.tsx`, `storage-event-boundary.log`. r1의 초기 읽기 실패 정정과 새 다른 탭 경로의 안내 실패를 구분한다.

**실행 결과와 재사용 범위**

모든 시험은 index에서 복사한 저장소 밖 `/private/tmp/poc629-r2-verify-20sbzp9o/src/`에서 가짜 자료로 실행했다. 기존 쓰기 가드를 유지했고, 기존 loader smoke가 요구하는 표와 가격만 이 사본의 합성 DB에 준비했다. 실제 DB를 복사하지 않았다.

| 이번 검증자가 실행한 검사 | 결과 |
|---|---|
| 미리보기 관련 백엔드 6파일 | **211 passed** |
| r1 독립 백엔드 재현·정상 대조군 원문 | **2 passed**(위와 합계 213 passed) |
| 관련 프런트 6파일·r1 독립 F2 재현 1파일 | **147 passed**(r1 재현 1건 포함) |
| 새 다른 탭 오류/허용 밖 상태 경계 | **2 failed(F3)** |
| staged 사본 타입 검사·변경 프런트 4파일 eslint | 종료 0·오류 출력 없음 |
| 변경 Python 2파일 black --check·flake8·py_compile | 모두 종료 0 |
| 검증 중 HEAD·index·작업 소스 대조 | `changes: []`, `problems: []`(결과서 기록 전) |

개발자의 전체 프런트 78파일·1,201 passed·변이 확인 및 r1 이전 전체 백엔드 5,665 passed·2 skipped는 반복하지 않았다. r1의 변하지 않은 메뉴·보관·배포·기존 갱신 경로 검증은 유지한다. 프런트 React act 경고와 백엔드 Starlette 사용 중단 예정 경고는 시험 통과와 구분해 남기며 새 제품 결함으로 세지 않는다. build·브라우저·실서버 조회·외부 갱신·발송·서버 재기동은 하지 않았다.

### 13-2. B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 없음.** F2의 읽기 실패를 저장 없음으로 취급하던 경로는 상태 넷으로 구분됐다. 기본 기간 1개월의 사용도 시작 시 오류 안내와 함께 공개된다. F3는 새 오류 안내의 문맥 불일치이며 값 없음으로 숨기는 동일 위반이 남았다고 보지 않는다.
- **B-2 단일 책임 위반: 없음.** 상세 판 대조는 기존 공통 기간 모듈 안, 저장 상태는 조건 저장 모듈, 표시는 기존 공통 행 안에 있다. 독립 모듈·패턴·새 책임을 추가하지 않았다.
- **B-3 파일 책임 과다: 없음.** 변경 Python 제품 366줄·시험 493줄, 프런트 제품 188·224줄·시험 391·219줄로 KS-10 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 운영·실험 기능을 추가하지 않았고 독립 재현은 저장소 밖에서만 수행했다.
- **B-5 배포/실행 경로 영향: 제출 범위 통과.** 신규 경로·파일 이동·Dockerfile·배포 스크립트 변경이 없다. 변경 6파일은 실제 경로에서 index 추적되며 r1의 보관·라우터·메뉴 경로 근거는 유지한다. main/실사용 반영 완료를 뜻하지 않는다.
- **B-6 기술부채/구조적 퇴행: F3 외 추가 발견 없음.** 상세 확인의 공개된 한계와 반복 읽기 비용은 보고돼 있다. 새 다른 탭 경로의 표시 문제는 F3 한 건으로만 집계하고 추가 구조 경고로 확대하지 않는다.

### 13-3. 기반 문서 준수

추가 기반 문서 위반 없음. 새 Markdown·라이브러리·프레임워크·DB 표·KS-10 발동은 없다. 저장 뒤 재확인과 다른 탭 저장 표시 갱신은 보관된 이전 C 계약의 화면별 이관 누락을 복구한 직접 변경이다. 이번 재검증에서 새 설계 승인이나 전체 회귀·공식 재실행을 요구하지 않는다.

### 13-4. 코드 안전성

**위험 수준: LOW(F3 표시 불일치).** F1의 다른 가격 판 정상 승인 재현은 해소됐고 F2 초기 읽기 실패도 구분된다. F3에서도 실제 3개월 조건은 유지되며 자료 손상·잘못된 수익률 계산·보안 문제는 발견하지 않았다. 실제 개인정보·운영 자료·비밀값·서버를 검증에 사용하지 않았다.

### 13-5. 범위 폭주

**폭주 수준: NONE.** 제품 3파일과 시험 3파일 정정은 F1·F2 및 이전 저장 계약 복구와 직접 연결된다. 새 기능·외부 호출·운영 작업·불필요한 전체 회귀 반복을 추가하지 않았다. 사용자 후속 화면 변경 요청은 설계자 경로로 남긴다.

### 13-6. 종합 판정

**REJECTED(F3 P3 · 다른 탭 재조회 안내 1건).** 기존 F1·F2의 정정은 통과했다. 남은 것은 실제로 유지되는 3개월 조회와 모순되는 1개월 시작 안내다. 새 설계 판단이 필요한 사안으로 보지 않는다. 사용자 실화면 확인은 유지하며 커밋·push·main 반영·실사용 적용은 하지 않았다.

### 13-7. 검증자 수정 내역

검증자가 수정·stage한 저장소 파일은 **작업 트리의 이 결과서 하나**다. STATUS/VERIFIER에 이번 r2 판정을 기록하고 §13을 추가했다. 검증자 §11과 개발자 §12·기반 문서·설계/PLAN·STATE·PROGRAM_TRUTH·제품 코드·제품 시험은 수정하지 않았다. 숫자·줄 수의 별도 정정은 없으며 재현 시험은 저장소 밖에만 남겼다. 본 저장소에 결과서를 복사하지 않았다.

## 14. 검증자 r2 정정(개발자 · 2026-11-12)

F3 를 고쳤다. 같은 줄의 다른 문구 중 다른 탭 저장 · 기간 변경 뒤 사실과 어긋날 수 있는 것(저장 실패 안내)도 함께 맞췄다. 백엔드 · 설계 · PLAN 변경은 없다.

### 14-1. 원인과 정정

- 원인: 안내 '…해 1개월로 시작했습니다'를 **지금 저장 상태**만 보고 골랐다. r1 에서 되살린 다른 탭 다시 읽기는 저장 상태만 바꾸고 지금 조회는 그대로 두므로, 3개월로 시작한 화면에도 '1개월로 시작'이 나왔다.
- 정정:
  - `frontend/lib/etfCompareCondition.ts`: 화면 조건을 처음 만들 때의 저장 상태를 기록한다(`started` · `getStartStatus`). 다른 탭 다시 읽기로 바뀌지 않는다.
  - `frontend/app/components/workbench/CompareHead.tsx :: basisReadNotice`:
    - '…해 1개월로 시작했습니다'는 이 화면이 바로 그 이유(같은 상태)로 1개월로 시작했고 지금도 1개월일 때만 쓴다.
    - 그 밖은 '저장된 기본을 읽지 못했습니다 — 지금 조회(3개월)는 그대로입니다' · '저장된 기본 값을 쓸 수 없습니다 — 지금 조회(…)는 그대로입니다'.
  - 저장 실패 안내(`BasisSaveRow`):
    - 실패한 기간을 적는다: '기본값(1개월) 저장을 확인하지 못했습니다 — 지금 조회는 그대로입니다'.
    - 그 뒤 다른 탭에서 같은 기간이 저장된 것으로 다시 읽히면 내린다. 다른 기간이 저장되면 남긴다.
    - 실패 뒤 기간을 바꿔도 어느 저장이 실패했는지 맞게 읽힌다.

### 14-2. 조합 표(실제 「섹터요약」 화면 · `SectorSummaryView.test.tsx` 「저장값 안내 = 지금 조회 기간과 맞춤」)

| 축 | 값 |
|---|---|
| 처음 열 때 저장 상태 | 저장됨(3개월) · 없음 · 읽기 실패 · 쓸 수 없는 값 |
| 기간 바꿈 | 안 바꿈 · 바꿈(3개월 ↔ 1개월) |
| 다른 탭 저장 뒤 다시 읽기 | 저장됨(1일) · 없음 · 읽기 실패 · 쓸 수 없는 값 |

- 32건 모두 처음 · 기간 바꾼 뒤 · 다시 읽은 뒤의 문구를 확인한다.
- 지금 조회 조건 그대로 · 요약 추가 요청 0 · '1개월로 시작했습니다'는 위 조건일 때만 나오는지도 확인한다.
- 그 밖에 2건을 더 둔다: 검증자 재현(저장된 3개월로 시작 → 쓸 수 없는 값 → 읽기 실패) · 저장 실패 안내(내림 · 남김 · 기간을 바꾼 뒤).

### 14-3. 변이 · 재현(각각 되돌린 뒤 복원 · `cmp` 같음)

| 바꾼 것 | 결과 |
|---|---|
| 고치기 전(stage 된 판) `CompareHead.tsx` · `etfCompareCondition.ts` | 「섹터요약」 시험 **20 failed** |
| 안내를 늘 '1개월로 시작'으로 | **19 failed** |
| 시작 상태 대조를 뺌(지금 1개월이면 '1개월로 시작') | **6 failed** |
| 시작 상태가 다시 읽기를 따라감 | **6 failed** |
| 저장 실패 안내를 내리지 않음 | **1 failed** |

### 14-4. 자체 검수

- 프론트: `npx vitest run` 78파일 `1235 passed`(r1 정정 뒤 1,201 + 34) · `npx tsc --noEmit` 종료 0 · `npx eslint .` 종료 0.
- 줄 수(KS-10): `etfCompareCondition.ts` 199 · `CompareHead.tsx` 244 · 시험 `SectorSummaryView.test.tsx` 342.
- 백엔드는 바꾸지 않았다(전체 회귀 · 관련 시험 다시 실행 안 함 · r2 검증자 실행 결과 유지).
- 바뀐 파일은 모두 §2 목록에 이미 있다: `frontend/lib/etfCompareCondition.ts` · `frontend/app/components/workbench/CompareHead.tsx` · `frontend/app/components/SectorSummaryView.test.tsx` · 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`.
- 독립 검토 1건을 백그라운드로 띄웠으나 네트워크 오류(API 서버 연결 실패)로 시작 직후 멈췄다. 같은 범위를 개발자가 직접 다시 봤다.
  - 문제 없음: 상태 읽기 함수가 같은 값을 돌려줌 · 다른 탭 감시를 붙이고 떼는 시점 · 서버 렌더(`window` 없음 → 예외를 잡아 넘어감 · 화면 문구 같음) · '이미 기본' · '저장됨' · '저장 없음' 문구.
  - 고친 것: 저장 실패 안내에 실패한 기간을 넣었다(14-1).


## 15. 검증자 r3 재검증(Codex · 2026-11-12)

기준은 작업 트리 `poc6-29-abc-refocus`의 staged 코드이며 HEAD는 `2c40ea69cc569c875338df5055fc201b808d3440`이다. r2 대비 제품 2개(`etfCompareCondition.ts`·`CompareHead.tsx`)·시험 1개(`SectorSummaryView.test.tsx`)와 문서 3개만 바뀌었다. 원본 PLAN 판정·PLAN·개발자 §14·실제 diff 및 기존 F3 재현을 대조했다. 백엔드와 나머지 제출 파일은 r2 지문과 같으며 기존 검증자 §11·§13 및 개발자 §12·§14를 보존한다.

### 15-1. A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 최초 조건을 만들 때 저장 상태를 별도로 고정하고, 현재 저장 상태·현재 조회 기간과 함께 안내를 고른다. 바로 그 오류/허용 밖 상태 때문에 1개월로 시작했고 현재도 1개월일 때만 시작 안내가 나온다. 3개월을 유지할 때는 실제 기간을 적으며 저장 상태만 바뀌어도 조회 조건과 요약 요청은 바뀌지 않는다. F3의 기존 재현 두 건과 32조합 표 모두 통과한다.
- **A-2 보고 정확성: 통과.** `git status --short --untracked-files=all`, `git diff --name-only HEAD`, `git ls-files`로 확인했다. staged 123개(신규 27·수정 66·보관 rename 30), 미 stage·미추적 0으로 보고와 같다. 변경 3파일은 기존 목록에 있으며 index 추적된다. 실측 줄 수는 제품 199·244줄, 시험 342줄로 §14와 같다. 별도 수치·줄 수 정정은 필요하지 않았다.
- **A-3 산출물 정합성: 통과.** r2의 독립 `storage-event-boundary.test.tsx`를 수정하지 않고 재실행했다. 3개월로 시작한 뒤 다른 탭 저장 재조회가 실패하거나 invalid가 돼도 ‘1개월로 시작’이 나오지 않고, 현재 3개월 조건·요청 1회가 유지된다. 저장 실패 안내도 실패한 기간을 적고 같은 기간의 저장 확인이 되면 표시에서 내려간다. 일반 저장·조회·목록·비교·보유 화면의 접점 시험도 통과했다. 사용자 실화면 확인 완료는 유지한다.
- **A-4 금지사항 위반: 없음.** 새 파일·라이브러리·외부 API·DB 스키마·파일 삭제·운영 작업이 없다. 검증자는 제품 코드·제품 시험을 수정하지 않았고 실제 state·DB·보유·금액·서버·OCI·커밋·push에 접근하거나 쓰지 않았다.

**F3: 해소.** r2 독립 재현 원문과 결과는 저장소 밖 `/private/tmp/poc629-r3-verify-_x064fp3/r2-original-boundary.test.tsx`, `frontend-related.log`에 보존한다.

| 이번에 확인한 범위 | 결과 |
|---|---|
| 기존 F3 독립 재현: 저장된 3개월 시작 → 다른 탭 재조회 SecurityError | 통과 — 실제 3개월 조회 유지, ‘1개월로 시작’ 없음 |
| 기존 F3 독립 재현: 저장된 3개월 시작 → 다른 탭의 허용 밖 값 | 통과 — 실제 3개월 조회 유지, ‘1개월로 시작’ 없음 |
| 초기 저장 상태 4 × 기간 변경 2 × 다른 탭 재조회 결과 4 | **32조합 통과** — 문구·조회 조건·추가 요청 없음 |
| 추가 저장 실패 안내·직접 재현 시험 | 통과 — 실패한 기간 표시·저장 확인 시 안내 내림 |
| 관련 프런트 6파일 + 기존 독립 재현 1파일 | **182 passed**(독립 2건 포함·섹터요약 시험 45건 포함) |
| 격리 staged 사본 `tsc --noEmit` | 종료 0·출력 없음 |
| 변경 프런트 3파일 eslint | 종료 0·출력 없음 |
| 검증 중 HEAD·index·작업 소스 대조 | `changes: []`, `problems: []`(결과서 기록 전) |

전체 프런트 78파일·1,235 passed와 변이 결과는 개발자 근거로 유지하며 반복하지 않았다. 백엔드 무변경을 지문으로 확인했으므로 r2의 관련 211건+독립 2건 통과와 기존 Python 정적 검사, 개발자의 전체 5,665 passed·2 skipped 근거를 재사용했다. F1의 상세 값 대조 범위와 공개 한계는 기존 §6·§12·§13대로 유지하며 원시 자료 전체의 불변 보장으로 확대하지 않는다. r1의 메뉴·보관·배포·갱신 검증도 유지한다. 프런트의 기존 React act 경고는 시험 통과와 구분해 남긴다. build·브라우저·실서버 조회·외부 갱신·발송·서버 재기동은 실행하지 않았다.

### 15-2. B. 구현 규칙/구조 품질 검증

- **B-1 암묵 fallback 위반: 없음.** 저장됨·없음·invalid·read_failed 구분을 유지한다. 초기 상태와 현재 상태를 섞어 시작 기간을 단정하던 F3가 해소됐고 조회를 임의로 바꾸지 않는다.
- **B-2 단일 책임 위반: 없음.** 시작 상태는 기존 화면별 조건 모듈, 표시 판단은 기존 공통 저장 행 안에 있다. 저장 실패 표시도 같은 행의 책임 범위다.
- **B-3 파일 책임 과다: 없음.** 변경 제품 199·244줄, 시험 342줄로 KS-10 기준 안이다. 새 구조나 파일 책임 확장은 없다.
- **B-4 실험/운영 경계 위반: 없음.** 실험 로직·운영 판정·외부 작업을 추가하지 않았고 검증 재현은 저장소 밖 사본에서만 실행했다.
- **B-5 배포/실행 경로 영향: 제출 범위 통과.** 파일 추가·이동·삭제·배포 설정 변경이 없고 변경 경로는 index 추적된다. r1의 라우터·메뉴·보관 경로 근거를 유지한다. 작업 트리 검증이며 main 또는 실사용 적용 완료를 뜻하지 않는다.
- **B-6 기술부채/구조적 퇴행: 없음.** 화면 시작 상태와 현재 저장 상태의 의미가 분리됐으며, 현재 조회 조건은 그대로다. 실패한 기간을 표시해 기간 변경 뒤에도 무엇을 확인하지 못했는지 알 수 있다.

### 15-3. 기반 문서 준수

추가 위반 없음. 새 Markdown·의존성·프레임워크·DB 표·KS-10 발동은 없다. 저장 안내 정정은 기존 F3와 같은 줄의 직접 범위이며 새 설계 승인을 요구하지 않는다. 백그라운드 검토 실패 뒤 개발자가 직접 확인했다는 보고는 외부 독립 검토 완료와 구분돼 있고, 검증자는 이번 재현·시험·코드 대조로 판단했다.

### 15-4. 코드 안전성

**위험 수준: NONE(이번 범위에서 새 위험 발견 없음).** F3 안내 불일치는 해소됐다. 계산·조회·저장 출처 계약과 r2에서 통과한 F1·F2 정정은 그대로다. 실제 개인정보·운영 자료·비밀값·서버를 검증에 사용하지 않았다.

### 15-5. 범위 폭주

**폭주 수준: NONE.** 제품 2파일·시험 1파일의 변경은 F3와 같은 줄의 저장 실패 안내를 맞추는 범위다. 백엔드·전체 회귀·새 기능·운영 작업을 추가하지 않았다. 사용자가 원한 추가 화면 변경은 설계자 후속 작업으로 유지한다.

### 15-6. 종합 판정

**VERIFIED.** F3 해소와 A/B 전 영역 통과를 확인했다. 추가 차단 결함은 없다. 다음은 결과서를 설계자 RESULT 판정으로 넘기는 순서다. 커밋·push·main 반영·실제 PC 적용은 기존대로 별도 사용자 승인을 따른다.

### 15-7. 검증자 수정 내역

이번 r3에서 검증자가 수정·stage한 저장소 파일은 **작업 트리의 이 결과서 하나**다. STATUS/VERIFIER를 갱신하고 §15를 추가했다. 받은 §10~§14·설계/PLAN·STATE·PROGRAM_TRUTH·제품 코드·제품 시험은 수정하지 않았고, 별도 수치 정정도 없었다. 본 저장소에 결과서를 복사하거나 커밋·push·실사용 반영하지 않았다. 독립 재현은 저장소 밖에만 남겼다.

## 16. RESULT PARTIAL 보완 구현(개발자 · 2026-11-12)

RESULT 판정(PARTIAL · 보완 4건)과 보완 PLAN 판정(승인 · Q-R1 ~ Q-R6 · 구현에서 확인할 세 가지)을 같은 격리 작업본에 반영했다. 갱신 원인 실측은 PLAN §9-0 · §9-0-1. 실제 네이버 지수 조회를 포함한 '버튼 → 빠른 시세 → 화면 세 칸' 실측 1회는 형수님 확인(판정서 '격리 검증과 사용자 확인') 뒤에 한다 — §16-5.

### 16-1. R1 「오늘의 투자 점검」 맨 위 '지금 시장'(RESULT 판정 §1 · Q-R3 · Q-R6)

- 빠른 시세 3칸(`today/MarketNowBlock.tsx` · 저장값 `GET /market/quick-quotes` 만 · 실패면 마지막 성공 값 + 실패 안내 · 기록 없으면 '시세 미확인' · '변동 없음'이면 이번 확인 시각 + '시세 변동 없음')은 그대로다.
- 흐름 문장 네 줄 · 칸마다 시각 줄 · 그 아래 배치(코스피 숫자 줄 · 차트 · 외국인 수급 · 최근 큰 변화)는 보완 2차에서 아침 요약 · 오늘 시장 변화 · 근거 접기로 바뀌었다 → §17-2 · §17-3.

### 16-2. R2 [최신 자료 갱신] — ⓪ 빠른 시세 · 같은 거래일 다시 받음(RESULT 판정 §2 · Q-R1 · Q-R2 · 확인할 것 1 · 2)

- 서버(`app/pc_quick_quotes.py` 새 · `app/pc_refresh_all.py` · `app/api.py` 라우터 1줄): 묶음 작업 첫 단계 `quick` = 네이버 지수 `m.stock.naver.com/api/index/{KOSPI 또는 KOSDAQ}/basic`(새 경로) · KODEX 200 = 기존 종목 경로. 6시간 대기와 무관 · 실패(일부 · 전부 · 예외)해도 보유 · 시장 단계 진행 · 연타 · 다른 탭은 같은 작업(빠른 시세도 그 작업에서 한 번). 저장 = `state/market_cache/quick_quotes_latest.json`(원자적 쓰기 · 항목별 마지막 성공 + 마지막 시도).
  - '변동 없음'(`unchanged`) = 같은 거래일 · 값 · 등락 · 장 상태가 모두 같음(원천 시각만 바뀐 경우 포함 — 실측: 코스피 15:36 → 15:58 같은 값). 이때 저장 성공 값은 이전 그대로 두고 시도만 새로 적는다. 거래일 · 장 상태 · 값이 바뀌면 `updated`.
  - 실패 사유 = `http_error` · `timeout` · `bad_value` · `missing_time` · 저장 실패 `store_error`(전체 failed). 저장 파일이 손상되면 읽기 응답 `invalid`(한 칸이라도 이상하면 · 시각은 실제로 해석) · 다음 받기 때 새로 저장하고 안내.
- 화면(`today/useTodayRefresh.ts` · `TodayInvestmentCheckView.tsx` · `lib/refreshCompare.ts` 새): ⓪ 이 끝나는 대로 저장값을 다시 읽어 3칸에 먼저 반영(시장 대기와 무관) · 결과 줄 '⓪ … 새 시세 받음(시세 시각 · 장 상태) · … 조회 성공 · 시세 변동 없음 · … 받지 못함(사유) — 마지막 시세 M/D HH:MM 표시 / 시세 미확인'.
  - 대기 줄 = '② 시장 자료는 대기 중입니다(6시간 간격) — 다음 갱신 가능 … · 지금 표시 = ETF 가격 M/D(저장 시각 · 가격 시점 저장) · 코스피 공식 종가 … · …(빠른 시세 · 보유 현재가는 이 대기와 별개로 받습니다)'.
  - 완료 대조 = 자료별 날짜 + 저장 시각 + 값. 재현 사례 문구: 'ETF 가격 11/12 같은 거래일에 다시 받음(09:53 장중 → 15:56 마감 뒤 저장 · KODEX 200 85,045원 → 84,240원)'. 저장일이 자료일과 다르면 저장 날짜까지(예: '11/9(11/10 13:18 마감 뒤 저장)').
  - ETF 가격의 기준 = KODEX 200 상세(`GET /market/etf-detail?tickers=069500`). 상세를 못 읽으면 '확인 불가'(시장 판정 응답의 날짜로 채우지 않음 — 처음 구현에서 '11/12 → 11/6' 같은 거짓 변화가 나는 것을 시험으로 찾아 고침).
  - 다시 읽기 실패 = '다시 읽기 실패: …(표시 중인 값 기준: …)'.

### 16-3. R3 「보유와 후보 비교」 카드(RESULT 판정 §3 · Q-R4 (a) · 확인할 것 3)

- 차이 줄의 판정 순서(상세 없음 → 값 없음 → 기간 다름 → 가격 시점 확인 필요 → 가격 상태 다름 → 비교 · 둘 다 장중 = 잠정 비교) · 표시한 값끼리 차이 규칙 · 거래량 · 흔들림 제외(Q-R4 (a))는 그대로다.
- 좌우 카드 · 접기 3개 · 별도 판단 근거 카드는 보완 2차에서 기본 비교 표(최근 5 · 20구간 · 고점 대비 추가) · 종목별 근거로 바뀌었다 → §17-5.

### 16-4. R4 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」(RESULT 판정 §4 · Q-R5)

- `LeftSidebar.tsx`(폴더 `unused_features` · MenuKey `unused_universe_watch` · 메뉴 key 17) · `MainPanel.tsx` · `UnusedFeatureView.tsx`(새 · 기능마다 같은 틀) · `DiagnosticsView.tsx`([미사용 기능] 구역 없앰 → 옮겼다는 한 줄 + 이동 버튼) · 보관 README 한 줄.
- 펼치지 않고 보이는 것: 어떤 기능이었는지 · 왜 빠졌는지 · 지금 어디서 · 기존 [신규 ETF 관찰 후보 갱신] 패널(열 때 요청 없음) · [「개발·실험용」으로]. 「자세히」(처음 접힘) = 없앤 「요즘 잘 오르는 ETF」 기능별 옮긴 곳 8줄(메뉴가 있는 줄은 이동 버튼) · 보관 경로는 이 안에만.

### 16-5. 격리 화면 · 실제 갱신

- 격리 서버 8001 을 보완 코드로 다시 띄우고 3001 에서 확인(16:35 · 버튼 누르지 않음 · 메뉴 이동만 · 캡처는 저장소 밖): 「오늘의 투자 점검」 · 「보유와 후보 비교」 · 「신규 ETF 관찰 점검」 · 「개발·실험용」 — 콘솔 · HTTP 오류 0 · 가로 넘침 0(1400px) · 갱신 요청(POST) 0. 빠른 시세는 아직 한 번도 받지 않아 3칸 = '시세 미확인 · [최신 자료 갱신]을 누르면 받습니다'(저장 파일 없음 · `GET /market/quick-quotes` = `empty`).
- 캡처에서 찾아 고친 것: 코스피 공식 종가 줄의 최신성 배지가 앞 글자에 붙어 보임 → 띄어쓰기.
- **격리 실제 갱신 1회(형수님이 격리 화면에서 누름 · 11/12 17:51 · 묶음 작업 `refresh_all_20261112_085123_2633e7`)**: ⓪ 빠른 시세 3건 모두 `updated` — 코스피 5,342.73(-0.61%) · 코스닥 696.53(-1.22%) · 시세 시각 16:15 · `CLOSE` / KODEX 200 84,240원(-0.35%) · 15:59:45 · `CLOSE` (값 = 같은 날 15:36 · 15:59 네이버 응답의 마감 값과 같음 · 저장 파일 `state/market_cache/quick_quotes_latest.json` 17:51:23) · ① 보유 29/29 · 시세 시각 15:56 → 17:51 · ② 시장 `skipped_cooldown`(마지막 성공 15:59:48 · 다음 21:59:47) → KRX · OCI 단계는 이번에 돌지 않음(앞선 15:56 실행에서 KRX `api_key_missing` · OCI 가져오기 실패 = 격리 작업 폴더에 `.env` 없음 · 판정서 V2 뒤 원인 대조는 PLAN §10-0). 이 상태의 화면(21:15 캡처)으로 설계자가 재판정했다(판정서 V2 · PARTIAL 유지).

### 16-6. 바뀐 파일(보완분 · 모두 stage)

- 서버 새: `app/pc_quick_quotes.py`(461줄). 서버 수정: `app/pc_refresh_all.py`(349) · `app/api.py`(라우터 1줄 · 주석).
- 서버 시험: `tests/test_poc6_29_quick_quotes.py`(새 · 598) · `tests/test_poc6_29_refresh_all.py`(628) · `tests/conftest.py`(빠른 시세 저장 경로 격리 · 모든 시험) · `tests/fixtures/poc6_29_quick_quotes/`(새 · 네이버 공개 응답 사본 4개 + README).
- 화면 새: `today/MarketNowBlock.tsx` · `workbench/CompareCards.tsx` · `UnusedFeatureView.tsx` · `lib/api/quickQuotes.ts` · `lib/marketNowText.ts` · `lib/refreshCompare.ts` · `lib/compareDiff.ts` · 시험 자료 `lib/quickQuotesTestFixtures.ts`.
- 화면 수정: `TodayInvestmentCheckView.tsx`(697) · `today/MarketFlowBlock.tsx` · `today/useTodayRefresh.ts` · `HoldingCandidateCompareView.tsx` · `LeftSidebar.tsx` · `MainPanel.tsx` · `DiagnosticsView.tsx` · `lib/api/refreshAll.ts` · `lib/todayMarketLines.ts` · `globals.css`(지금 시장 9줄 · 쓰지 않게 된 비교 표 1줄 뺌).
- 화면 시험: 새 `today/TodayQuickRefresh.test.tsx` · `lib/marketNowText.test.ts` · `lib/refreshCompare.test.ts` · `lib/compareDiff.test.ts` · `UnusedFeatureView.test.tsx` / 수정 `TodayInvestmentCheckView.test.tsx` · `today/TodayMarketFlow.test.tsx` · `today/TodaySummary.test.tsx` · `today/TodayVixRetry.test.tsx` · `HoldingCandidateCompareView.test.tsx` · `LeftSidebar.test.tsx` · `DiagnosticsView.test.tsx`.
- 문서: 보완 PLAN 판정 · RESULT 판정(새 · 설계자 원문) · PLAN §9 · 목업 R1 ~ R4(⓪ 줄 = 구현 예정 예시 표시) · PROGRAM_TRUTH · STATE · 이 결과서 · 보관 README.
- git 실측: 수정 68 · 신규 49 · 보관 30 · 미 stage 0 · 미추적 0.

### 16-7. 시험 · 변이

- 프런트: `npx vitest run` 83파일 `1324 passed` · `npx tsc --noEmit` 종료 0 · `npx eslint .` 종료 0(2026-11-12 16:32).
- 백엔드 관련: `test_poc6_29_quick_quotes.py` · `test_poc6_29_refresh_all.py` · `test_poc6_29_decision_preview_common.py` · `test_poc6_29_etf_detail.py` = `150 passed`(conftest 격리 추가 뒤) · black · flake8 통과. 시험은 실제 HTTP 전송을 막고 시도 자체를 실패로 본다(네트워크 0).
- 백엔드 전체 회귀(보완 뒤 · 2026-11-12 16:35:19 ~ 17:02:39): `5747 passed, 2 skipped, 1 warning in 1638.44s (0:27:18)` · 실패 0. 회귀 시작 뒤 바뀐 `app` · `scripts` · `tests` 파일 0개 · 새 `.pyc` 0개(실측). 회귀 중 바뀐 것은 화면 파일(`today/MarketFlowBlock.tsx` 배지 띄어쓰기)과 문서뿐이며, 그 뒤 화면 시험 12파일 `220 passed` · 타입 · eslint 0.
- 변이(각각 되돌린 뒤 복원 · `cmp` 같음):

| 바꾼 것 | 결과 |
|---|---|
| '변동 없음' 비교에 원천 시각을 넣음(서버) | 1 failed |
| 차이 줄이 가격 상태를 보지 않음 | 9 failed |
| 메뉴에서 「미사용 기능」 폴더를 뺌 / 화면 연결을 뺌 | 모듈 계약 오류로 두 시험 파일 실패 / 2 failed |
| 갱신 전후 대조에서 저장 시각을 안 봄 | 5 failed |
| 흐름 문장에 넣은 사건을 목록에서 안 뺌 | 1 failed |
| ⓪ 뒤 빠른 시세를 다시 읽지 않음 | 2 failed |
| '변동 없음' 조회 시각 표시를 끔 | 1 failed |

### 16-8. 검증자 · 설계자에게 알릴 점

- **'변동 없음'의 시각**: 저장 시세의 원천 시각 · 받은 시각은 이전 성공 그대로이고, 새로 확인한 시각은 `last_attempt.at`. 화면은 조회 시각에 이 시각을 쓰고 '시세 변동 없음'을 붙인다.
- **등락 부호 검사(서버)**: 네이버 `compareToPreviousClosePrice` 와 `fluctuationsRatio` 부호가 반대면 등락 금액만 비운다(기존 `market_naver.py` 의 부호 빠짐 사례 계약과 같음 · 그 항목은 성공).
- **차이 줄**: 화면에 보이는 소수 둘째 자리 값끼리 뺀다(보이는 두 수와 차이가 맞게 · 원값 차이 0.008 이면 '같음'). '확인된 가격 상태' = 가격 날짜가 그 기간 끝일과 같을 때만(서버 ok 기간이면 늘 같음 · 보수적).
- **지시 밖 작은 정정**: 비교 카드의 하락 판정 라벨이 비면 'null' 대신 '하락 구간'. 비교 카드 후보 쪽 가격 기준 = 상세 응답 `end_price`(예전 표는 요약 응답).
- **화면의 영어 낱말**: 미사용 기능 설명의 'pykrx' · 'PUSH-2' · 'PUSH-3'(설계자 원문) · 기존 [신규 ETF 관찰 후보 갱신] 패널 안 문구(동작 그대로 옮김)는 그대로다.
- **격리 환경 한계**: 작업 폴더에 `.env` 가 없어 코스피(KRX) · 수급(OCI) 단계는 격리 실측에서 실패로 남는다(판정서가 `.env` 연결을 범위에서 뺌 · 실제 PC 는 키 있음).

## 17. RESULT 재판정 PARTIAL 유지 보완 2차 구현(개발자 · 2026-11-12 ~ 11-13)

판정서 = `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_V2_2026-11-12.md`(재판정) · `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_S_PLAN_DECISION_2026-11-12.md`(보완 PLAN §10 승인 · Q-S1 ~ Q-S6 · 수정 3건). PLAN §10 · 목업 S1 ~ S3. 실제 PC 자료일 대조(판정서 V2 §1)는 PLAN §10-0.

### 17-1. 백엔드(새 읽기 두 개 · ③ 전일 자료 보충)

| 파일 | 내용 |
|---|---|
| `app/pc_morning_basis.py`(새 · `GET /market/morning-basis`) | 기준일 = 직전 국내 거래일(`expected_previous_trading_day`). 필수 3 = 코스피 공식 종가(국내 T-1 판정 `_kr_item`) · KODEX 200 판정 근거(**기준일 행이 마감 뒤 저장이고 그 이력으로 아침 판정이 계산될 때**만 충족 · `price_state` · 최신 행이 오늘이어도 기준일 행이 장중 · 저장 시점 확인 불가 · 없음 · 판정 이력 부족이면 미충족 · S 판정 §3 · 검증자 F5 · §19) · 투자자 수급. 해외 = VIX(`vix_freshness`) · 원/달러(국내 T-1) · WTI(관측일만) · 필수 아님. 아침 판정 = 기준일까지 자른 069500 이력으로 `compute_market_context` → `compute_regime_streak` → `kodex200_return_dates`(지금 판정과 같은 순서 · 새 산식 없음) · 실제 산출 기준일 `basis_date` · 근거 없으면 `unconfirmed`. 당일 판정 `today_regime`(이력 전체로 같은 산식 + 끝 행 저장 시점 · §23) — KODEX 200 이력 · 저장 시각은 SQL 한 문장으로 한 번만 읽어 항목 · 아침 · 당일 판정을 모두 만든다. 점수 산식 경계값 `score_rule`(기존 판정 상수 · 판정 표 [?] · 설계자 V3 D1 · §27). 사유 = 확인된 결과만(코스피 = 전체 갱신 기록 · ③ 결과 중 최근 · `kospi_reason` · 수급 = 수급 연결 상태 문장 · PC 보관소 · 시도 없으면 '아직 받지 않음 — [최신 자료 갱신]' · KODEX 200 = 실제 대기 중일 때만 다음 시각). 저장값 · 기록 · 달력 · 보관소 목록만(외부 조회 · 쓰기 0) |
| `app/pc_short_flows.py`(새 · `GET /market/short-flows`) | 주체(외국인 · 기관계 · 개인)별 끝일 값 · 최근 5거래일 합 · 직전 5거래일 합(거래일 달력 끝일 포함 10일 · 기존 `window()` · 하루라도 빠지면 계산 안 함 → '5거래일 자료 부족') · 비교 문장(기존 `_trend` 를 n=5 로) |
| `app/pc_prevday_fill.py`(새) | ③ = 모자란 것만 기존 경로로: 코스피 `refresh_kospi_benchmark`(기록 행 남기지 않음 → '마지막 전체 갱신' 그대로) · 수급(PC 보관소에 기준일을 채운 미반영 OK · PARTIAL 묶음이 있으면 `refresh_flows_from_oci(skip_pull=True)` · 없으면 가져오기 + 반영) · VIX `refresh_pc_vix`(미국 완료일 기준) · 원/달러 · WTI `refresh_fx_wti`(원/달러가 늦을 때 · 기록 행 = 시장 흐름 출처 + ③ id). 항목마다 예외 격리. 결과 = `state/market_cache/prevday_fill_latest.json`(임시 파일 뒤 교체). 시작 확인 · 표시 = 전체 갱신 잠금 안(전체 갱신 · VIX 다시 받기 · ③ 진행 중이면 `skipped` · 사유) |
| `app/pc_refresh_all.py` | 단계 `prevday` = ② 가 `skipped_cooldown` 일 때만 실행 · 그 밖은 `skipped` + 사유(시작 · 진행 중 = '같은 수집에서 받습니다') · 예외 = `failed` · 작업은 ③ 이 끝난 뒤 done |
| `app/market_refresh_service.py` · `app/market_refresh_vix_retry.py` | ③ 진행 중이면 전체 갱신 · VIX 다시 받기 시작을 새 상태값 `prevday_running`(한국어 문구)으로 거절(POC5-12 `vix_retry_running` 과 같은 방식) |
| `app/oci_flow_import.py` | `refresh_flows_from_oci(skip_pull=False)` 인자 — 건너뛴 가져오기는 기록 행 '시도 0 · 성공 0 · 실패 0' → 수급 연결 상태가 '가져오기 실패'가 아닌 '수급은 OCI 수집본을 PC에 반영'으로 읽힘 |
| `app/supply_fx_oil_context.py` | `_trend(a, b, n=20)` — 기간 수 인자(20 그대로 같은 문장 · 시험으로 고정) |
| `app/api.py` · `app/api_market_topn_models.py` · `tests/conftest.py` | 새 라우터 2 · 상태값 설명 · ③ 결과 파일 시험 격리 |

### 17-2. 「오늘의 투자 점검」 처음 화면(판정서 V2 §2 · S 판정 §3 · PLAN §10-1 · §10-2)

- `today/MarketFlowBlock.tsx`(다시 씀) = 머리 → `today/MorningSummary.tsx`(새) → `today/MarketNowBlock.tsx`(바뀜).
- 아침 요약 = 'M/D 마감 기준' · 준비 상태 한 줄(`lib/morningText.ts :: readiness` · 같은 날짜 자료를 한 묶음 · 조사 은/는 · '전일 자료 미완료 · 코스피 공식 종가 · 수급은 11/9까지') · 서버 사유 줄 · 아침 판정(기준일 마감 기준 · 미확인이면 '아침 판정 미확인 — …') · 기준을 채운 자료만 문장(코스피 공식 종가 · 외국인 5거래일 · VIX · 원/달러 · WTI) · 최근 변화 1 ~ 2건(기준을 채운 계열만 · `recentChanges(…, allow)` · '전체 N건은 아래 … ②에서').
- 오늘 시장 변화 = 공통 시점 머리 한 번(`quoteHeader` · 거래일 · 장 상태가 다수와 다르거나 실패한 칸만 그 칸에 시각 · 장 상태) · 당일 판정('당일 판정 — …' + KODEX 200 저장 시점 · 강조 상자 · 출처 = 아침 기준 응답 `today_regime`(판정 값과 그 판정이 쓴 끝 행의 저장 시점이 서버의 같은 한 번 읽기) · 그 칸이 없으면 시장 판정 응답의 판정 · 날짜만 · 형수님 결정 2026-11-13 · 검증자 F4 · F7 · F8 · §23 · 아침 · 당일이 같은 마감 행이면 상자 = '아침과 같은 M/D 마감 뒤 저장값 기준'만 · §27) → 바로 아래 시장 판정 근거 표(`today/RegimeBasisTable.tsx` · 아침 · 당일 또는 '아침·당일 공통' 한 행 · 점수 열 · 제목 옆 [?] 산식 · 이동평균 = 가격 + 거리 · §27) → 코스피 공식 종가 덩어리(`today/KospiCloseBlock.tsx` · 직전 대비 + 비교 날짜 · 5회 전 대비 · 기준일 · 배지 · [?] · 저점 문장 + 비교 기준 · 20 · 60 · 6개월 칸 · 바로 아래 차트 · 코스피 지표(`KospiHeadline startOpen`)) — 형수님 결정 2026-11-13 · §17-10.

### 17-3. 근거 접기(판정서 V2 §2 · S 판정 §1 · Q-S1 · PLAN §10-3 · 형수님 결정 2026-11-12)

- `today/MarketEvidenceFold.tsx`(다시 씀) · `today/MarketEvidenceTable.tsx`(새) · `today/SourceHint.tsx`(새 · 상태 옆 `[?]` = `details` · 출처 · 받은 시각 · 시작 · 끝일). (`today/KospiHeadline.tsx`(`startOpen`)는 지금 접기 밖 `today/KospiCloseBlock.tsx` 안 · §17-2 · §17-10.)
- ① 근거 표(외국인 = 두 구간 일평균 방향 + 기간 · 기관계 · 개인 = 60거래일 + 기간 · 5거래일 합 · VIX = 직전(날짜) 대비 · 5거래일 전 대비 · [VIX 다시 받기] · 원/달러 · WTI = 직전(날짜) 대비 · 5회 전 대비) · '1개월 해석 · 실제 기간' · 시장 위험 참고(KODEX 200 · VIX 20거래일 차트 · 펼친 채) → ② 기간별 흐름 · 날짜별 사건(기존 카드) → ③ 전일 자료 미완료. 시장 판정 근거 표 · 코스피 공식 종가 덩어리는 접기 밖 당일 판정 바로 아래(형수님 결정 2026-11-13 · §17-2 · §17-10).
- 지킨 기존 계약: 코스피 비교 날짜 직접(RESULT 판정 §3-1) · 외국인 두 구간 방향(검토 F2) · '없음' 단정 금지(F9 · 확인 못 한 자료 안내는 ②) · 차트 = 코스피 숫자 바로 아래(결정 ① · 형수님 결정 2026-11-13 으로 다시 처음 화면).

### 17-4. [최신 자료 갱신] ③ · 끝 줄(판정서 V2 §3 · PLAN §10-4)

- `today/useTodayRefresh.ts`: `onPrevdayDone`(③ 이 pending · running 이 아니게 되면 한 번) · 상태 확인 상한 120 → 240회(6분 · ③ 포함).
- `TodayInvestmentCheckView.tsx`(761줄): 새 조회 2(`morning` · `short`) · ③ 완료(done)면 시장 자료 키를 비우고 아침 기준 · 5거래일 · 시장 판정 · 시장 흐름 · KOSPI 시계열 · 보유 근거 다시 읽기 · ③ 줄(`prevdayLine`) · 끝 줄(`endLine` · 다시 읽은 아침 기준 그대로) · ② 완료 · VIX 다시 받기 뒤에도 아침 기준 다시 읽기 · [요약 다시 읽기]에 아침 요약 기준 · 수급 5거래일 · 의존 목록 보완.
- `useMarketRefresh.ts`: 상태 `blocked`(`prevday_running` → '② 전일 자료 보충이 진행 중입니다. 끝난 뒤 다시 누르세요' · 실패 아님). VIX 다시 받기 훅은 이미 그 밖 상태를 안내로 보임.

### 17-5. 「보유와 후보 비교」(판정서 V2 §4 · S 판정 Q-S6 · §4-4 · 별도 작업자 구현 · 개발자 확인)

- `lib/compareDiff.ts`(168줄) · `workbench/CompareCards.tsx`(304줄 · 다시 씀) · `HoldingCandidateCompareView.tsx`(225줄) · `globals.css`(비교 묶음 32줄).
- 기본 비교 표 = 1 · 3개월(+ KODEX 200 대비) · 최근 5 · 20구간 · 고점 대비(20저장일 창 · 고점일). 차이 판정 순서는 §16-3 그대로 모든 줄에 · 고점 대비 = 창 시작 · 끝일 같음 + 확인된 같은 가격 상태일 때 '후보 하락폭이 x.xx%p 작음/큼' · '하락폭 같음'. 종목별 근거 = [후보 판단 근거 | 보유 판단 근거] · 시장가 · NAV · 괴리율 · 6 · 12개월 · 20구간 KODEX 200 차이 · 하락 판정 · 구성종목 겹침 · 판단 근거 미리보기 · [AI 세션에서 검토](요청 그대로).
- 문구: 가격 상태가 다른 경우는 기존 시험이 지키는 '가격 상태가 달라 비교하지 않음(보유 장중 · 후보 마감 뒤)'을 모든 줄에 그대로 썼다(목업의 '가격 시점이 달라'와 다름 · 바꾸려면 한 줄).

### 17-6. 격리 확인(판정 Q-S5 (c) · S 판정 §4)

- **입력 사본**: 실제 PC 보관소의 11/12 09:40 OCI 수집 묶음(`20261112T004001Z_51ba935a` · 수급 11/11까지 · 실제 PC 에는 11/12 10:05 이미 복사돼 있던 것)과 객체 34개를 격리 보관소에 복사(실제 PC 쪽은 읽기만).
- **③ 실제 함수 실행**(11/12 23:58 KST 고정 시각 · 기준일 11/11 · 네트워크 연결을 막고 실행 → 외부 조회 0 · 쓰는 곳 = 격리 작업본 `state/` 만): `prevday_20261112_145800_f504d7` = 코스피 `failed`(설정 확인 필요(KRX 키 없음) · 부르기 전에 멈춤) · 수급 `applied` · `via=local`(11/9 → 11/11 · 가져오기 없음) · VIX · 원/달러 `already` · WTI `skipped`(원/달러가 최신이라 함께 받지 않음). 아침 기준 = 미완료(코스피 · 수급) → 미완료(코스피만).
- **준비됨 사례**: OCI 보관 KRX 공식 종가(11/10 5,239.13 · 11/11 5,375.36)를 격리 사본에 넣은 뒤 아침 기준(같은 고정 시각) = `ready=true` · 필수 3 모두 11/11 · 아침 판정 `ok` · 기준일 11/11 · 하락장 24거래일째 · KODEX 200 20거래일 -10.70% · 60거래일 -18.01%(당일 11/12 판정은 25거래일째 · -3.06% · -21.36% — 두 판정이 따로 보임 · S 판정 §4-1).
- 고정 시각 확인의 한계: ③ 결과 파일의 끝난 시각은 실제 시각(11/13 00:13)이라 고정한 '오늘'(11/12)과 날짜가 달라, 그 순간의 코스피 사유가 '아직 받지 않음'으로 보였다(실제 운영에서는 두 시각이 같다).
- **화면(3001 · 버튼 누르지 않음 · 캡처는 저장소 밖)**: 11/12 23:47(기준일 11/11 · 미완료 사례) — 아침 요약 '전일 자료 미완료 · 코스피 공식 종가 · 수급은 11/9까지' · 사유 두 줄 · 아침 판정 11/11 마감 기준 24거래일째 · 오늘 시장 변화 머리 '11/12 마감 · 네이버 시세 · 마지막 조회 11/12 17:51' · 당일 판정 25거래일째 · 근거 접기 ① ~ ⑤ · [?] · 「보유와 후보 비교」 / 11/13 00:15(자정이 지나 기준일 11/12) — '코스피 공식 종가 · 수급은 11/11까지'(11/12 자료는 원천에도 아직 없음 · OCI 는 11/13 09:40 수집) · 아침 판정 11/12 마감 기준. 두 번 모두 콘솔 · HTTP 오류 0 · 갱신 요청(POST) 0 · 1400px 가로 넘침 0. 400px 은 오늘 점검 565px(넘치는 요소 = 바꾸지 않은 맨 위 두 카드 · 기존 복사 버튼 — 앱 왼쪽 메뉴가 좁은 폭에서 접히지 않아 본문 약 165px · 이번 변경 밖) · 비교 화면 400px 넘침 0.
- **남은 확인(판정 Q-S5 (a))**: 실제 PC 에서 평소처럼 [최신 자료 갱신]을 누른 때의 전 · 후 자료일 대조(읽기 전용)와 '② 대기 중 버튼 한 번 → ③ → 화면' 실제 경로. 격리 환경은 ② 대기를 만들 수 없어(마지막 전체 갱신 11/12 15:59 · 대기 21:59 까지) 버튼 경로는 시험(묶음 작업 · 화면)으로 확인했다.

### 17-7. 시험 · 변이

| 확인 | 결과 |
|---|---|
| 백엔드 새 시험 | `tests/test_poc6_29_morning_basis.py` 19건(기준일 · 필수 3 · 기준일 행 장중이면 미충족 · 대기일 때만 다음 시각 · 확인된 사유 조합 · ③ 결과가 더 최신 · 사유 없는 더 늦은 시도 · PC 보관소 안내 · 해외 규칙 · 읽기 실패 · 엔드포인트 쓰기 0 · 5거래일 완성 · 하루 누락 · 직전만 누락 · 빈 DB · `_trend` 20 문장 고정) · `tests/test_poc6_29_prevday_fill.py` 20건(② 대기일 때만 · 시작 · 진행 중 · VIX · ③ · 실패면 건너뜀 · 예외 · 잠금 세 가지 · 진행 중 전체 갱신 · VIX 다시 받기 거절 · 예외 때 잠금 풀림 · 모자란 것만 · PC 보관본 반영(가져오기 0 · 기록 '시도 0 · 실패 0' · 연결 상태 '반영') · 기준일 못 채운 사본 = 가져오기 경로 · 코스피 결과 5가지 · 코스피 기록 행 없음 · 전체 갱신 상태 그대로 · VIX · 원/달러 기록 출처 · 항목 예외 격리) |
| 백엔드 기존 시험 갱신 | `tests/test_poc6_29_refresh_all.py`(③ 가짜 · 단계 목록에 `prevday` · 대기 때 ③ 결과) · `tests/conftest.py`(③ 결과 파일 격리) |
| 백엔드 관련 | 18개 파일 527건 통과(바꾼 기존 모듈을 쓰는 시험 포함) · 마감 정정 뒤 4개 파일 162건 통과 |
| 백엔드 전체 회귀 1회 | `5785 passed, 2 skipped, 1 warning in 1668.80s (0:27:48)`(11/12 23:44:43 ~ 11/13 00:12:39 · 실패 0 · 도는 동안 코드 파일 변경 0 · 새 pyc 0). 그 뒤 정정 1건(§17-8 사유 고르기)은 이번 라운드 새 파일(`app/pc_morning_basis.py` · 사용처 = 새 라우터 · 시험뿐)만 바꿔 전체 회귀를 다시 돌리지 않고 관련 162건으로 확인 |
| 프런트 | `npx tsc --noEmit` 0 · `npm run lint` 오류 0 · 경고 0(정리한 경고 5건 = 이전 라운드부터 있던 4건(안 쓰는 가져오기 · 상수 · 함수 · [요약 다시 읽기] 의존 목록) + 이번 1건) · `npx vitest run` 84개 파일 1,399건 통과(§17-10 반영 뒤 · 11/13) · 새 `lib/morningText.test.ts` 21건 · 화면 시험 7건(`TodayQuickRefresh.test.tsx` 보완 2차 묶음 6 + 시세 머리 1) · 기존 오늘 점검 시험 갱신(새 조회 가짜 · '불러오기 끝' 표시 = 당일 판정 줄 · 배치 · 차트 위치 · 근거 표 · 코스피 지연 배지 위치 · 펼친 코스피 지표) |
| 백엔드 변이(되돌리면 실패하는가 · 복원 = 내용 쓰기 + 바이트 대조) | M1 ③ 은 ② 대기일 때만 · M2 수급 PC 보관본 먼저 · M3 KODEX 200 기준일 행(최신 행 아님) · M4 ③ 진행 중 전체 갱신 거절 · M5 가져오기 건너뜀 = 실패 0 기록 · M6 사유 = 사유 있는 시도 — 6종 모두 잡힘 · 복원 일치 |
| 프런트 변이 | F1 날짜 묶음 조사 · F2 미충족 수급 문장 숨김 · F3 다른 칸만 그 칸에 시각 · F4 미완료 계열 사건 거르기 — 4종 모두 잡힘 · 복원 일치. 비교 화면(별도 작업자) — 고점 대비 창 비교 · 작음/큼 방향 2종 잡힘 |
| 공개 저장소 | 기준 커밋 대비 추가된 모든 줄에서 보유 종목 코드 · 이름 새로 들어간 것 0(KODEX 200 은 기준 지표로만 · 일치 1건 = POC5-24 부터 공개 커밋에 있던 시험 자료 줄의 앞 글자만 바꾼 것) |
| 파일 크기(KS-10) | 화면 `TodayInvestmentCheckView.tsx` 787줄(§29 · 경고 850 아래) · 근거 접기 128 · 판정 표 202(§27) · 코스피 덩어리 119 · 근거 표 173 · 아침 요약 118 · 백엔드 `pc_prevday_fill.py` 441 · `pc_morning_basis.py` 491(§27) · `pc_refresh_all.py` 402 · **`market_refresh_service.py` 630줄(경고 600 위 · 이전 616 · 한도 650 아래)** · 시험 최대 1,082(`TodayInvestmentCheckView.test.tsx`) |

### 17-8. 확인 중 찾아 고친 것 · 검증자 · 설계자에게 알릴 점

- 고친 것: ① 새 코스피 줄에서 직전 대비 비교 날짜가 빠졌던 것(RESULT 판정 §3-1 계약) → 되살림 ② 근거 표 외국인 변화에서 직전 구간 값이 빠졌던 것(검토 F2 계약 · 두 구간 방향) → 두 구간 · 기간 함께 ③ 같은 때 사유 없는 ③ 기록이 더 늦으면 사유가 '아직 받지 않음'으로 바뀌던 것(격리 확인에서 발견) → 오늘 시도 중 사유 있는 가장 최근 것 · 시험 · 변이 M6 ④ 묶음 작업이 ③ 때문에 길어지면 화면 상태 확인 상한(3분)에 걸리던 것 → 6분.
- 묶음 작업은 이제 ② 가 대기면 ③ 이 끝날 때까지 `running` 이다(수급 가져오기 상한 150초 + KRX · 해외 지표). 그동안 다른 탭 · 연타는 같은 작업을 이어 본다.
- ③ 의 코스피는 기록 행을 남기지 않는다('마지막 전체 갱신' · 코스피 화면 상태의 기준 기록이 ③ 으로 바뀌지 않게). 그래서 ③ 이 코스피를 받지 못한 경우의 화면 코스피 배지는 직전 전체 갱신 기록을 따른다(아침 요약 사유는 ③ 결과 파일에서 읽음).
- 비교 화면의 '가격 상태가 다른 경우' 문구는 기존 시험 문구('가격 상태가 달라 비교하지 않음')를 그대로 썼다(목업 '가격 시점이 달라'와 다름).
- 사용자 결정 ① ③(POC6-27)은 판정 Q-S1 로 접기 배치가 됐다가, 형수님 결정(2026-11-13)으로 시장 판정 근거 표 → 코스피 공식 종가 덩어리(차트는 코스피 숫자 바로 아래)가 다시 처음 화면 당일 판정 바로 아래로 올라왔다 — PLAN §10-3 · 목업 S1(접기 ① · ②)과 다르다(§17-10). 최근 변화는 위에 1 ~ 2건 그대로.

### 17-9. 바뀐 파일(보완 2차 · 모두 stage)

- 백엔드 새 파일 3: `app/pc_morning_basis.py` · `app/pc_short_flows.py` · `app/pc_prevday_fill.py`
- 백엔드 수정 7: `app/api.py` · `app/api_market_topn_models.py` · `app/market_refresh_service.py` · `app/market_refresh_vix_retry.py` · `app/oci_flow_import.py` · `app/pc_refresh_all.py` · `app/supply_fx_oil_context.py`
- 백엔드 시험: 새 `tests/test_poc6_29_morning_basis.py` · `tests/test_poc6_29_prevday_fill.py` · 수정 `tests/conftest.py` · `tests/test_poc6_29_refresh_all.py`
- 화면 새 파일 10: `frontend/app/components/today/RegimeBasisTable.tsx` · `today/KospiCloseBlock.tsx`(둘 다 §17-10) · `today/MorningSummary.tsx` · `today/MarketEvidenceTable.tsx` · `today/SourceHint.tsx` · `frontend/lib/morningText.ts` · `lib/morningText.test.ts` · `lib/morningTestFixtures.ts` · `lib/api/morningBasis.ts` · `lib/api/shortFlows.ts`
- 화면 수정: `TodayInvestmentCheckView.tsx` · `today/MarketFlowBlock.tsx` · `today/MarketNowBlock.tsx` · `today/MarketEvidenceFold.tsx` · `today/KospiHeadline.tsx` · `today/useTodayRefresh.ts` · `useMarketRefresh.ts` · `lib/marketNowText.ts` · `lib/todayMarketLines.ts` · `lib/api/market.ts` · `lib/api/refreshAll.ts` · `globals.css` · `MarketRiskReferenceCard.tsx` · `useMarketVixRetry.ts`(주석)(둘 다 §17-10) · 비교 화면 `HoldingCandidateCompareView.tsx` · `workbench/CompareCards.tsx` · `lib/compareDiff.ts`
- 화면 시험 수정: `charts/ChartCallers.test.tsx`(§17-10) · `TodayInvestmentCheckView.test.tsx` · `today/TodayMarketFlow.test.tsx` · `today/TodayQuickRefresh.test.tsx` · `today/TodaySummary.test.tsx` · `today/TodayVixRetry.test.tsx` · `HoldingCandidateCompareView.test.tsx` · `lib/compareDiff.test.ts`
- 문서: 판정서 저장 `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_S_PLAN_DECISION_2026-11-12.md` · PLAN §10 · 목업 S1 · 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`

### 17-10. 형수님 화면 의견 반영(2026-11-13 · 검증 전)

형수님 의견(격리 화면 · 세 번): ⓐ 「시장 위험 참고」 20거래일 그래프가 너무 작다(원래 있었나 · 이런 그래프는 크게) ⓑ 「① 시장 판정 근거 · KODEX 200」은 접기가 아니라 위로 — 당일 판정('당일 판정 — … · KODEX 200 11/12 가격(15:56 마감 뒤 저장)') 바로 아래 ⓒ 당일 판정을 더 강조 ⓓ (첫 반영 확인 뒤) 코스피 공식 종가 구역(숫자 · 20 · 60 · 6개월 칸 · KOSPI 가격 흐름 차트 · 코스피 일간 변화 · KODEX200 기준선 대비 위치 · 이 값의 한계 · 마지막 자료 기준일) **전체**를 함께 올려 달라는 뜻이었다 — 판정 표만 올라간 것은 부분. ⓔ (두 번째 반영 확인 뒤) 판정 표 아래 '당일 판정 근거(4건) · … · 점수 -4' 줄이 바로 위 당일 판정 상자와 같은 근거라 중복 → 그 줄은 빼고, 점수(처음 알게 된 값)를 표에 둘지 · 기준이 맞는지는 설계자 판정으로(아래 '설계자 판정 요청').

- **확인한 사실**: ⓐ 그래프는 2026-07-04 `market-risk-reference-v1`(d021a921)부터 「요즘 잘 오르는 ETF」의 [상세 펼치기] 안에 있던 200×40 미니 선이고, 이번 POC 에서 크기를 바꾸지 않고 그대로 옮겼다(PLAN 판정 Q14 '공용 파일은 활성 경로에 남김'). 문서에서 이 그래프 크기에 대한 이전 요청 기록은 찾지 못했다. ⓑ ⓓ 판정 근거 · 코스피 공식 종가를 접기 안에 둔 것은 설계 V1 표('시장 근거와 다른 변화 보기 — 펼치면 KODEX 200 판정 근거와 이동평균 …')와 PLAN §10-3 · 목업 S1(접기 ① · ②) · S 판정 Q-S1(S1 채택)을 따른 배치였다.
- **바꾼 것(화면만 · 새 계산 · 새 조회 없음 · 숫자 · 시험 ID 그대로 · 바뀐 문구 = 아래 셋)**:
  - 처음 화면 「오늘 시장 변화」 = 시세 3칸 → 당일 판정(강조 상자) → 시장 판정 근거 표(`today/RegimeBasisTable.tsx` · 새 · 접기에서 그대로 옮김 · 아침 · 당일 · 표 아래 '당일 판정 근거(N건) · … · 점수' 줄은 ⓔ 로 뺌) → 코스피 공식 종가 덩어리(`today/KospiCloseBlock.tsx` · 새 · 접기 ① 구역을 그대로 옮김 · 제목 '코스피 공식 종가(KRX)' · 칸 · 바로 아래 차트 · 코스피 지표 `KospiHeadline startOpen`('시장 수치와 거래량' 펼친 채 · 접을 수 있음)). `today/MarketFlowBlock.tsx` 가 `MarketNowBlock` children 으로 이 순서로 둔다.
  - 당일 판정 강조(`today/MarketNowBlock.tsx` · `globals.css`) — 옅은 파랑 바탕 · 왼쪽 파란 줄 · 16px 굵게 · 그 아래 'KODEX 200 M/D 가격(… 저장)' = 13.5px 굵게 진한 파랑. 문장은 그대로(지금은 아침 · 당일이 같은 마감 자료면 상자 = '아침과 같은 M/D 마감 뒤 저장값 기준'만 · 설계자 V3 D2 · §27).
  - 근거 접기(`today/MarketEvidenceFold.tsx`) = ① 수급 · VIX · 원/달러 · WTI(근거 표 · 1개월 해석 · 시장 위험 참고) · ② 기간별 흐름 · 날짜별 사건 · ③ 전일 자료 미완료(미완료일 때만). `kodex` 인자 제거(`TodayInvestmentCheckView.tsx` 호출도). 번호를 가리키던 문장도 맞춤: 아침 요약 '전체 N건은 아래 … ②에서'(`today/MorningSummary.tsx`) · [VIX 다시 받기] 진행 중 안내 '결과는 아래 … ①에서'(`TodayInvestmentCheckView.tsx`).
  - 바뀐 문구 셋: 코스피 덩어리 제목 '① 코스피 공식 종가(KRX)' → '코스피 공식 종가(KRX)'(번호 없음 · 접기 밖) · 접기 번호 · 카드 머리 안내 '… · 오늘 시장 변화 = 오늘 네이버 시세 · 근거는 아래 [시장 근거와 다른 변화 보기]' → '… / 오늘 시장 변화 = 오늘 네이버 시세 · 당일 판정 · 판정 근거 · 코스피 공식 종가 / 수급 · 해외 지표 근거 = 아래 [시장 근거와 다른 변화 보기]'(위에 있는 것과 접기에 있는 것을 갈라 적음 · 독립 검토에서 첫 고친 문장이 판정 근거 · 코스피도 접기에 있는 것처럼 읽힌다는 지적을 받아 다시 고침). (카드 머리 안내 줄은 마감 뒤 형수님 결정으로 뺌 · §31)
  - 시장 위험 참고(`MarketRiskReferenceCard.tsx`) — 미니 선(`MiniSeries` · 200×40) 대신 코스피 차트와 같은 공용 차트 `charts/ReadableLineChart`(날짜 눈금 · 값 눈금 · 고른 날 값 줄 · 높이 180) · KODEX 200 = 원 · VIX = pt · 응답의 최근 20거래일 그대로. `startOpen`(근거 접기 안에서는 펼친 채 · S 판정 Q-S1 '한 번 열면 바로 보임' — 이 카드만 안쪽 [상세 펼치기]가 남아 있었다) · 기본값은 예전처럼 접힘 · [상세 접기]로 접을 수 있음.
- **시험(배치 계약)**: `TodayInvestmentCheckView.test.tsx`(아침 요약 → 당일 판정 → 판정 표 → 코스피 공식 종가 → 칸 → 차트 → 코스피 지표 순서 · 판정 표 바로 다음 = 코스피 덩어리 · 칸 · 차트 · 지표가 덩어리 안 · 접기 안에는 코스피 덩어리 · 차트 없음 · 근거 표 있음 · '시장 수치와 거래량'은 덩어리 안에서 펼친 채) · `TodaySummary.test.tsx`(접기 안 = VIX · 시장 흐름 상세 · 판정 표 · 코스피 공식 종가는 접기에 없음 · 당일 판정 다음 = 판정 표 · 그 다음 = 코스피 공식 종가) · `charts/ChartCallers.test.tsx` 2건(새 · 펼친 채 두 차트 · 첫 날짜 눈금 = 응답 첫 날 · 단위 원 · pt · 고른 날 줄 · 높이 180 · 미니 선 없음 · 접기 / 기본 접힘 · 펼치면 같은 차트) · 제목 · 번호 바뀐 문구(`TodayMarketFlow.test.tsx` · `TodayQuickRefresh.test.tsx`) · 번호 안내 대조(독립 검토 지적 · 접기 제목 ① · ② = `TodaySummary.test.tsx` · VIX 진행 중 안내 '…①에서'와 접기 ① 제목 = `TodayMarketFlow.test.tsx` · 카드 머리 안내 문장 = `TodaySummary.test.tsx`). 전체 84개 파일 1,399건 통과 · `npx tsc --noEmit` 0 · `npm run lint` 문제 0(마지막 수치는 §17-10 끝 '자체 검수'에 실측).
- **변이(되돌리면 실패하는가 · 복원 = 내용 쓰기 + touch + `cmp` 같음)**: 판정 표를 당일 판정 위로 · 판정 표를 위에서 빼기 · 위험 참고 펼친 채 시작 무시 · 차트 높이 40 · 코스피 덩어리를 접기 안으로 되돌림(배치 계약 시험 2건만 실패 · 나머지 90건 통과) · 판정 표와 코스피 덩어리 순서 뒤집기 · 코스피 지표를 덩어리에서 빼기 · VIX 안내 번호를 ②로 · 접기 제목 번호 바꿈 · 카드 머리 안내를 첫 고친 문장으로 — 10종 모두 잡힘.
- **격리 화면(3001 · 11/13 10:17 · 문구 정정 뒤 10:28 다시 · 버튼 누르지 않음 · 캡처는 저장소 밖)**: 카드 머리 안내 = 새 문장 · 당일 판정 다음 = 판정 표 · 그 다음 = 코스피 공식 종가 덩어리(「오늘 시장 변화」 안 · 접기 밖) · 차트 · 코스피 지표가 덩어리 안 · 접기 제목 = '① 수급 · VIX · 원/달러 · WTI' · '② 기간별 흐름 · 날짜별 사건' · '③ 전일 자료 미완료' · 위험 참고 두 차트 각 964×200 · 콘솔 · HTTP 오류 0 · 갱신 요청(POST) 0 · 1400px 넘침 0 · 400px 565px(이전 캡처와 같은 값 · 앱 왼쪽 메뉴 · 이번 변경 밖).
- **범위**: 화면(UI)만 바꿨다. 백엔드 · 응답 · 계산은 그대로라 백엔드 전체 회귀는 다시 돌리지 않았다.
- **ⓔ 확인**: 표 아래 줄이 없음(`tc-regime-reasons` 없음 · 「오늘 시장 변화」 안에 '당일 판정 근거(' · '점수 ±N' 글자 없음 = `TodaySummary.test.tsx`) · 줄을 되살리는 변이 = 잡힘 · 관련 11개 파일 205건 → 전체 84개 파일 1,399건 통과 · eslint 문제 0 · 격리 화면 12:52 = 「시장 흐름」 카드에 '당일 판정 근거(' · '점수 -' 글자 0 · 배치 그대로 · 콘솔 · HTTP 오류 0. 이 줄을 뺀 뒤 점수는 설계자 V3 D1 로 판정 표 '점수' 열에 다시 보인다(§27).

#### 17-10-1. 설계자 판정 요청(형수님 요청 · 2026-11-13 · 요청 당시 코드는 바꾸지 않음 · 판정 = 설계자 RESULT 재판정 V3 D1 ~ D4 · 반영 §27)

새 배치에서 위아래로 붙으면서 드러난 중복 · 형수님이 처음 알게 된 판정 점수다. 개발자 분류(결함 아님 · 설계 판단 필요)와 함께 남긴다.

| # | 항목 | 요청 당시 화면(지금은 §27) | 판정 받을 것 |
|---|---|---|---|
| D1 | **시장 판정 점수**(`app/market_regime.py :: _score_kodex200` · `_label_from_score`) | 화면에 없음(ⓔ 로 뺀 줄에만 있었음) | 판정 표에 점수를 둘지(형수님: '있으면 좋다') · **기준이 맞는지** 점검. 지금 기준 = 근거 4개 각 +1 · -1 · 0: KODEX 200 20거래일 수익률 +2% 이상 +1 · -2% 이하 -1 · 그 사이 0 / 60거래일 +5% 이상 +1 · -5% 이하 -1 · 그 사이 0 / 현재가가 20일 이동평균 위 +1 · 아래 -1 / 60일 이동평균 위 +1 · 아래 -1 → 합 -4 ~ +4 · **+2 이상 상승장 · -2 이하 하락장 · 그 사이 보합장**(검증자 §18-3 참고: 현재가가 이동평균과 **같아도 -1**)(상수 `SCORE_THRESHOLD_20D_PCT = 2.0` · `SCORE_THRESHOLD_60D_PCT = 5.0` · `REGIME_BULL_MIN_SCORE = 2` · `REGIME_BEAR_MAX_SCORE = -2`). 11/12 사례 = -1 · -1 · -1 · -1 = -4 → 하락장 |
| D2 | 아침 판정(아침 요약 문장 · 판정 표 '아침' 줄)과 당일 판정(강조 상자 · 표 '당일' 줄)이 같은 값 | 오늘 KODEX 200 가격을 [최신 자료 갱신] ② 로 받기 전에는 당일 판정도 직전 거래일 저장 행으로 계산된다 → 그 행이 마감 뒤 저장이면 **아침 판정과 같은 값**(11/13 화면 = 둘 다 11/12 마감 · 하락장 25거래일째 · -3.06% · -21.36%) · 장중 저장이면 아침 판정은 '미확인'(S 판정 §3)이라 같지 않다 | 둘이 같을 때 보이는 방법(S 판정 §3 · §4-1 의 '두 판정을 따로 보임'을 유지할지 · 같을 때 한쪽을 줄일지) |
| D3 | 코스피 구역의 'KODEX200 기준선 대비 위치(MA20 -3.63% 아래 · MA60 -16.11% 아래)'와 판정 표 '가격 · 이동평균(20일선 87,415원 아래 · 60일선 100,419원 아래)' | 같은 사실을 %(거리)와 원(값)으로 두 번 | 한쪽만 둘지(기존 계약 POC5-UI-03 'MA20 · MA60 각각 명시' · '코스피와 KODEX200 을 하나로 묶지 않는다'가 걸린 부품) |
| D4 | '시장 수치와 거래량'(펼친 채) 안 '기존 시장 판정 참고 · 하락장 · 25거래일째 · KODEX200 기준일' | 당일 판정 · 판정 표 '당일' 줄과 같음 | 뺄지 · 그대로 둘지(같은 부품 · 같은 계약) |
- **독립 검토 1회(코드 계약 · 문서-코드 대조 · 읽기 전용 2명)**: 코드 이동 누락 0(접기의 옛 코스피 구역과 `KospiCloseBlock.tsx` 공백 무시 대조 = 의도한 세 곳만 다름) · 지적 = 카드 머리 안내 문장 오해 소지 · 번호 안내 시험 없음 · 이 결과서 · PROGRAM_TRUTH 의 옛 번호 · 줄 수 · 파일 목록 → 모두 고침(위 문구 · 시험 · 변이 · 이 문서 §0 · §1 · §4 · §17-3 · §17-4 · §17-7 · PROGRAM_TRUTH 최종 반영 · 관련 파일 · 공통 차트 호출자).

## 18. 검증자 보완 구현 검증(Codex · 2026-11-13)

검증 기준: 작업 사본의 stage, 기준 커밋 `2c40ea69`. §15의 r3 판정은 해당 제출본에 유효하다. 이번에는 이후 §16~17 보완, 특히 §17-10의 표 아래 줄 제거와 V2/S 판정의 자료일·아침 준비 상태 계약을 대조했다. 사용자 화면 의견은 §17-10에 기록된 요구 근거로 사용했다. Q-S5(a) 실제 PC 갱신 전후 대조는 대기 상태를 유지한다.

### 18-1. A. 기능/산출물 검증

- **A-1 지시 일치: 위반.** 근거 4건·점수 −4가 있는 응답에서 표 아래 중복 줄은 없어졌고 강조 상자의 근거와 표의 수익률은 유지됐다. 다만 아래 F4~F6은 판정이 실제 사용한 날짜와 확인된 상태를 표시해야 한다는 V2 §2~3, S 판정 §3·Q-S4를 충족하지 못한다.
- **A-2 보고 정확성:** 점수 줄 제거 및 D1~D4 기록을 확인했다. 작업 사본 총 173개 stage(신규 66·수정 77·내용 동일 이동 30), 미 stage·미추적 0. 이번 줄 제거를 화면에 적용한 사실과 보완 구현 전체의 기능 통과를 구분한다.
- **A-3 산출물 정합성: 위반.** F4에서 계산값과 날짜가 엇갈리고, F5~F6에서 아침 준비 여부·사유가 실제 자료와 어긋난다.
- **A-4 금지사항 위반: 없음.** 이번 줄 제거는 표시 변경이다. 점수 산식·응답 필드는 기준 커밋과 같고, 신규 의존성·스키마 변경·배포 경로 변경은 확인되지 않았다. 앞 보완의 네이버 빠른 시세 경로와 읽기 API는 관련 판정의 범위에 있다.

#### F4(P2) — 당일 판정 값에 다른 날짜의 저장 시점이 붙음

- 시장 판정과 ETF 상세는 독립 요청이다(`TodayInvestmentCheckView.tsx:184,197`). `MarketFlowBlock.tsx:65~69`와 `RegimeBasisTable.tsx:91~95`는 판정이 사용한 날짜와 대조하지 않고 상세 날짜·상태를 표시한다.
- 격리 화면 시험에서 시장 판정은 11/11, 20거래일 수익률 −3.06%로 두고, 상세만 11/12 16:00 마감 뒤 저장으로 응답시켰다. 강조 상자와 표 모두 11/11 값에 **11/12 마감 뒤 저장**을 붙였다. 실제 PC 자료나 외부 조회는 사용하지 않았다.
- 서로 다른 판의 값으로도 날짜·저장 상태가 한 근거로 표시된다. §17-10-1 D2(같은 판정값의 배치 결정)와 별개다.

#### F5(P2) — 판정에 필요한 이력이 없어도 아침 필수 자료가 모두 준비됐다고 표시

- `app/pc_morning_basis.py:271~274,328~337,396~405`에서 기준일 행의 마감 뒤 저장 여부로 KODEX 200을 충족 처리하지만, 아침 판정 산출 실패는 `ready/missing`에 반영하지 않는다. 화면의 아침 요약과 갱신 끝 줄은 이 항목의 충족 여부를 사용한다(`frontend/lib/morningText.ts:33~35`).
- 임시 DB에 기준일의 마감 뒤 가격 한 행만 두고, 코스피·수급을 갖췄다. 아침 판정은 `unconfirmed`(저장 이력 부족)였지만, `ready=true · missing=[]`으로 나왔다. 그 응답은 화면에서 ‘필수 자료 준비됨’으로 표시된다.

#### F6(P3) — 저장 시점 미확인을 장중 저장으로 단정

- `app/pc_morning_basis.py:275~283`에서 미충족인 행이 존재하면 저장 상태를 확인하지 않고 ‘장중 저장값만 있음’이라고 적는다.
- 기준일 행의 저장 시각이 해석 불가인 임시 DB에서 `basis_row.state=unknown`, `met=false`, 아침 판정 `unconfirmed`를 확인했다. 미완료 판정 자체는 맞았으나, 사유에는 ‘10/29 장중 저장값만 있음’이 적혔다.

검증자가 실행한 검사: stage 사본의 관련 프런트 19파일 **364건 통과**, 백엔드 4파일 **124건 통과**, 타입 검사·대상 ESLint 통과. 독립 확인 4건 중 점수 줄 제거 1건 통과, F4~F6 3건 재현. 개발자 전체 회귀(프런트 1,399건·백엔드 5,785건, 적용 범위 §17-7)는 반복하지 않았다. 증거는 저장소 밖 `/private/tmp/poc629-supplement-verify-mh917gwl/`에 보관했다.

### 18-2. B. 구현 규칙/구조 품질 검증

- **B-1 암묵 기본값:** 줄 제거에는 추가 없음. F4·F6은 확인되지 않은 시점을 표시하는 기능 결함으로 분류했다.
- **B-2 단일 책임:** 줄 제거는 판정 표의 표시 책임 안에 있다. 보완의 아침 기준 읽기·전일 보충·단기 수급은 별도 모듈이다.
- **B-3 파일 책임 과다:** 판정 표 142줄·해당 시험 619줄. 보완에서 바뀐 `market_refresh_service.py` 630줄은 KS-10 사전 경고 범위이며 650줄을 넘지 않았다.
- **B-4 실험/운영 경계:** 이 변경에서 운영 경로에 연구·백테스트 삽입 없음.
- **B-5 배포 경로:** 관련 파일은 모두 index에서 확인했다. Dockerfile·배포 스크립트·패키지 잠금 변경 없음.
- **B-6 구조적 퇴행:** F4는 별도 응답을 확인 없이 조합하는 문제로 확인했다. D1~D4 때문에 새 계산·저장 규칙이 추가되지는 않았다.

### 18-3. 기반 문서 준수

사용자 화면 결정과 기존 점수 규칙을 구분해 기록했다. §17-10-1의 D1~D4는 설계자 판정 항목이며 이번 반려 사유에 포함하지 않는다. D1 검토 참고: 기존 구현은 현재가가 이동평균과 **같을 때도** ‘아래’와 같은 −1로 처리한다(`app/market_regime.py:376~389`). 점수식은 변경하지 않았다.

### 18-4. 코드 안전성

**MEDIUM.** 다른 날짜의 판정 근거가 현재 값처럼 보일 수 있고, 판단 불가인데 필수 자료 준비 완료로 보인다. 검증은 격리 사본·가짜 응답·임시 DB에서 했다. 운영 조회·발송·서버 조작을 하지 않았다.

### 18-5. 범위 폭주

**NONE.** §17-10의 사용자 요청에 따른 표시 변경과 관련 시험·문서 범위에 해당한다. 설계자 판단 대기 항목의 동작은 바뀌지 않았다.

### 18-6. 종합 판정

**REJECTED (보완 구현).** 표 아래 중복 줄 제거는 확인했다. 보완의 날짜·준비 상태·저장 시점 표시 F4~F6을 재검증해야 한다. D1~D4와 Q-S5(a)는 별도로 남긴다.

### 18-7. 검증자 수정 내역

이 결과서의 `STATUS`·`VERIFIER`를 갱신하고 §18을 추가했다. 기존 본문, 제품 코드, 제품 시험, PLAN, STATE_LATEST, PROGRAM_TRUTH는 수정하지 않았다. 커밋·push·main 반영·실제 PC 반영은 하지 않았다.

## 19. 검증자 보완 검증 F4 · F5 · F6 정정(개발자 · 2026-11-13)

§18 의 세 결함을 고쳤다. D1 ~ D4(§17-10-1)와 Q-S5 (a)는 그대로 남긴다(설계자 · 실제 PC 몫).

### 19-1. F4(P2) — 당일 판정 값에 다른 날짜의 저장 시점이 붙음

> 지금 동작은 §23(당일 판정 = 서버 한 번 읽기) — 아래 날짜 대조는 §23 에서 없어졌다(아침 줄 대조만 방어로 남음).

- 원인: 시장 판정(`GET /market/topn/latest` 의 `market_context`)과 KODEX 200 상세(`fetchEtfDetail`)는 따로 받는 응답인데, 당일 판정 상자(`MarketFlowBlock.tsx` → `kodexBasisText`)와 판정 표 '당일' 줄(`RegimeBasisTable.tsx`)이 상세의 끝일 · 저장 상태를 판정 날짜와 대조하지 않고 붙였다.
- 판정이 쓴 날짜 = 같은 069500 이력의 끝일(`kodex200.return_end_date` · POC5-21) · 없으면 KODEX200 기준일(`asof` · PC 화면 API 는 이력 끝일 · `market_topn.py` 계약 ⑤). 새 `lib/marketNowText.ts :: regimeBasisDate`.
- 정정(같은 규칙을 이 조합을 하는 모든 자리에 · `regimeSentence(` · `kodexSnap(` · `end_price` 사용처 전수 grep — 판정과 상세를 합치는 곳은 아래 둘뿐 · `snapshotOf` 갱신 전후 대조는 판정에 붙이지 않는 자료별 대조라 해당 없음):

| 자리 | 판정이 쓴 행 = 상세 끝일 행(§19 = 날짜 · §21 에서 종가까지) | 다름(상세가 더 새 날 · 더 옛 날 · 같은 날 다른 저장값 = §21) · 상세 없음 · 판정 날짜 모름 |
|---|---|---|
| 당일 판정 상자 아래 줄(`kodexBasisText(detail, basisDate)` → `regimeSentence`) | 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)'(그대로) | 'KODEX 200 M/D 가격 기준(저장 시점 확인 필요)' — M/D = 판정 날짜(예전 대체 문장 'KODEX 200 M/D 저장값'도 이 문장으로 · 날짜 출처 = `regimeBasisDate`) |
| 판정 표 '당일' 줄 기준일 · 상태 · [?] | 판정 날짜 · 상세 저장 상태 · 'FDR 일별 가격 · HH:MM 저장' | 판정 날짜 · '저장 시점 확인 필요' · [?] = '판정 기준일 11/11 · 가격 상세 끝일 11/12 — 날짜가 달라 저장 시점을 붙이지 않음'(상세 없으면 [?] 없음) |
| 판정 표 '아침' 줄(같은 결함이 날 수 있는 자리 · 함께 막음) | 아침 판정 기준일 행(`basis_row.date == morning_regime.basis_date`)의 상태 · 출처 | 상태 · 출처 붙이지 않음 |

### 19-2. F5(P2) — 판정 이력이 없어도 '필수 자료 준비됨'

- 원인: `app/pc_morning_basis.py` 가 KODEX 200 '판정 근거'를 기준일 행이 마감 뒤 저장인지만으로 충족 처리했고, 그 뒤 아침 판정(`morning_regime`)이 이력 부족으로 계산되지 않아도 `ready` · `missing` 에 반영하지 않았다.
- 정정: 아침 판정을 계산한 뒤, 기준일 행은 마감 뒤 저장인데 판정이 `ok` 가 아니면 KODEX 200 항목을 미충족(`met=false` · `state=late` · 사유 'KODEX 200 근거 미확인 · M/D 마감 가격은 있으나 판정 근거 부족(저장 이력)')으로 바꾼다 → `missing` 에 `kodex200` · `ready=false`. 화면의 준비 상태 줄 · 갱신 끝 줄 · ④ 미완료는 이 응답을 그대로 쓰므로 함께 '전일 자료 미완료 · KODEX 200 근거 미확인'(Q-S4 · 화면이 따로 판정하지 않음). 다시 받아도 이력이 늘지 않으면 그대로라 이 사유에는 갱신 안내를 붙이지 않는다.
- 결과 불변식(시험으로 고정): 준비됨이면 아침 판정 있음 — `ready is False or morning_regime.status == "ok"`.

### 19-3. F6(P3) — 저장 시점 미확인을 '장중 저장'으로 단정

- 원인: 기준일 행이 있고 미충족이면 저장 상태를 보지 않고 'M/D 장중 저장값만 있음'으로 적었다.
- 정정: 저장 상태대로 — 장중(`intraday`) = 'M/D 장중 저장값만 있음' · 그 밖(`unknown` = 시간대 없는 시각 · 읽을 수 없는 시각 · 가격 날짜보다 앞선 시각 — `price_state` 기존 규칙) = 'M/D 가격의 저장 시점 확인 불가'. 대기 다음 시각 · [최신 자료 갱신] 꼬리는 그대로(다시 받으면 새 저장 시각이 생김).

### 19-4. 조합 시험 · 변이

| 시험 | 내용 |
|---|---|
| `tests/test_poc6_29_morning_basis.py` 새 7건 | 기준일 행 저장 시각 × 이력: 마감 뒤 + 이력 충분 = 충족 · 준비됨 · 판정 ok / 장중 / 시간대 없음 / 읽을 수 없음 / 날짜보다 앞섬 = 미충족 · 사유가 상태대로('장중'은 장중일 때만) / 마감 뒤 + 이력 부족(9/1 부터 · 61행 미만) = 미충족 · `missing=["kodex200"]` · 판정 unconfirmed · 준비됨 아님 · 불변식 / 엔드포인트도 같은 판단 → 26건 통과 |
| `lib/refreshCompare.test.ts` | `kodexBasisText` 같은 날 · 다음 날 저장(그대로) + 다른 날(상세가 더 새 · 더 옛) · 판정 날짜 모름 = null |
| `lib/marketNowText.test.ts` | 대체 문장 = 'KODEX 200 M/D 가격 기준(저장 시점 확인 필요)' · 판정 날짜는 `return_end_date` 가 `asof` 보다 먼저 |
| `today/TodayQuickRefresh.test.tsx` 새 4건 | 화면: 같은 날 / 다른 날(판정 11/11 · 상세 11/12 마감 뒤 — 상자 · 표에 '마감 뒤 저장' 없음 · [?] 문장) / 상세 읽기 실패 / 아침 줄 기준일과 다른 행 = 상태 · 출처 없음. 기존 흐름 문장 시험의 자료는 판정 기준일(11/6)과 상세 끝일(11/12)이 어긋난 바로 F4 조합이었다 → 판정 기준일을 상세와 같은 11/12 로 맞춤(실제 응답 모양 · 기대 문장 그대로) |

- 변이(되돌리면 실패하는가 · 복원 = 내용 쓰기 + touch + `cmp` · `PYTHONDONTWRITEBYTECODE=1`): 백엔드 F5 정정 빼기(2건 실패) · F6 늘 '장중'(3건) / 프런트 문장 날짜 대조 빼기(4건) · 표 '당일' 줄 대조 빼기(1건) · 표 '아침' 줄 대조 빼기(1건) · 판정 날짜를 `asof` 먼저(1건) — 6종 모두 잡힘.

### 19-5. 자체 검수 · 범위

- 백엔드: `black --check` · `flake8` · `py_compile`(바꾼 두 파일) 통과 · 관련 3개 파일(`test_poc6_29_morning_basis.py` · `test_poc6_29_prevday_fill.py` · `test_poc6_29_refresh_all.py`) 67건 통과. **백엔드 전체 회귀는 다시 돌리지 않았다** — 바뀐 백엔드 코드는 이번 POC 의 새 파일 `app/pc_morning_basis.py` 하나이고 사용처는 `app/api.py`(라우터 등록) · 그 시험뿐(grep `pc_morning_basis|morning-basis`). 직전 전체 회귀 = §17-7.
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,406건** 통과(새 7건).
- 격리 서버: 8001 을 정정 코드로 다시 띄움 · 아침 기준 응답(11/13 · 기준일 11/12) = KODEX 200 충족(기준일 행 마감 뒤 · 이력 충분 · 판정 ok) · 준비 상태는 코스피 · 수급 때문에 미완료(그대로). 화면 13:23 = 판정 날짜와 상세 끝일이 같은 평소 경우라 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)' 그대로 · 콘솔 · HTTP 오류 0 · 1400px 넘침 0.
- 바뀐 파일(이번 정정): `app/pc_morning_basis.py` · `tests/test_poc6_29_morning_basis.py` · `frontend/lib/marketNowText.ts` · `frontend/lib/refreshCompare.ts` · `frontend/app/components/today/MarketFlowBlock.tsx` · `frontend/app/components/today/RegimeBasisTable.tsx` · 시험 `frontend/lib/marketNowText.test.ts` · `frontend/lib/refreshCompare.test.ts` · `frontend/app/components/today/TodayQuickRefresh.test.tsx` · 문서 이 결과서(STATUS · §17-1 · §17-2 · §17-7 · §17-10-1 D1 · §19) · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`. 새 의존성 · 스키마 · 배포 경로 변경 없음.

## 20. 검증자 보완 재검증(Codex · 2026-11-13)

§19 정정 제출을 검증했다. 기준 커밋은 `2c40ea69`이며 §18 검증 스냅샷과 비교해 제품 5개, 시험 4개, 문서 3개가 달라졌다. V2 §2~3, S 판정 §3·Q-S4, PLAN §10에서 정한 판정의 자료일과 확인된 저장 상태를 기준으로 삼았다.

### 20-1. A. 기능과 산출물

- **A-1 지시 일치 위반.** §18의 날짜가 다른 F4 재현, 이력이 부족한 F5 재현, 저장 시각을 해석할 수 없는 F6 재현은 모두 통과했다. 같은 날짜에 저장값을 교체하는 경우에는 아래 F7이 재현됐다.
- **A-2 보고 정확성 통과.** §19의 변경 파일과 Git 스냅샷이 일치한다. 총 173개 stage(신규 66, 수정 77, 내용이 같은 이동 30)이며 미 stage·미추적은 0이다.
- **A-3 산출물 정합성 위반.** 판정 상자와 판정 표의 당일 줄에서 같은 거래일의 다른 가격에 속한 저장 시점이 붙는다.
- **A-4 금지사항 위반 없음.** 이번 정정의 코드와 설정에서 신규 의존성, 외부 API 추가, 파일 삭제, 스키마 변경을 확인하지 않았다.

#### F7(P2) — 같은 거래일에 가격을 다시 저장하면 다른 가격의 저장 시점이 판정에 붙음

`frontend/lib/refreshCompare.ts:50~53`과 `frontend/app/components/today/RegimeBasisTable.tsx:76~81`은 시장 판정과 가격 상세의 날짜가 일치하면 상세의 저장 시점과 상태를 붙인다. 같은 날짜의 가격을 갱신할 수 있으므로 날짜만 일치해도 두 응답이 가리키는 저장값은 다를 수 있다. PLAN §9-0-1에도 장중에서 마감 뒤로 같은 날짜를 갱신한 사례가 있다.

임시 SQLite DB에서 KODEX 200의 11/12 장중 저장값 85,045원(09:53)으로 시장 판정 응답과 상세 응답을 읽었다. 같은 행을 84,240원(15:56 마감 뒤 저장)으로 갱신한 다음 두 응답을 다시 읽었다. 전후 응답을 실제 화면 컴포넌트에 각각 전달했다.

| 판정 응답 | 가격 상세 응답 | 실제 표시 |
|---|---|---|
| 85,045원, 20거래일 −2.25% | 84,240원, 15:56 마감 뒤 저장 | 판정 상자와 표 모두 장중 계산값에 ‘마감 뒤 저장’ 표시 |
| 84,240원, 20거래일 −3.17% | 85,045원, 09:53 장중 저장 | 판정 상자와 표 모두 마감 뒤 계산값에 ‘장중 저장’ 표시 |

같은 저장본의 응답을 맞춰 넣은 대조군 2건은 가격과 저장 상태가 올바르게 표시됐다. 날짜가 다른 경우는 이번 정정으로 해결됐지만, 같은 날짜의 서로 다른 저장값에서는 사용자가 판정에 쓰인 가격의 저장 상태를 잘못 읽을 수 있다.

검증자 실측은 격리 사본 프런트 15파일 304건, 백엔드 69건 통과다. 이전 독립 재현 3건이 이 수에 포함된다. 같은 날짜 독립 시험 4건은 불일치 재현 2건, 정상 대조군 통과 2건이다. 타입 검사, 변경 프런트 파일 ESLint, 변경 Python 파일 black·flake8·컴파일을 통과했다. flake8에는 저장소의 `setup.cfg`를 적용했다. 개발자 전체 회귀는 §17-7과 §19-5의 범위를 인용했다. 격리 근거 경로는 `/private/tmp/poc629-f4f6-verify-eDYAMKyE/`다.

### 20-2. B. 구현 구조

- **B-1 암묵 기본값.** 판정의 `return_end_date`가 없을 때 PC API의 KODEX 200 기준일 `asof`를 쓰는 것은 기존 응답 계약과 맞는다. 저장 상태 혼합은 F7에 기록했다.
- **B-2 단일 책임.** 판정 계산과 표시가 기존 모듈 경계 안에 있다.
- **B-3 파일 크기.** 아침 기준 모듈 429줄, 판정 표 152줄, 가장 긴 이번 변경 시험 607줄이다.
- **B-4 운영 경계.** 연구·백테스트 경로의 변경은 없다.
- **B-5 배포 경로.** 변경한 코드·시험·결과서는 Git index에서 확인했다. 배포 스크립트·패키지 파일 변경은 없다.
- **B-6 유지보수.** 판정과 상세가 독립 응답인 두 표시 경로에서 동일하게 F7을 재현했다.

### 20-3. 기반 문서

이번 수정 범위에 KS-10 임계 초과나 신규 의존성은 없다. D1~D4는 §17-10-1의 설계자 판단 항목이며 Q-S5(a) 실제 PC 갱신 전후 대조도 대기 상태다.

### 20-4. 코드 안전성

**MEDIUM.** 가격이 장중인지 마감 뒤에 저장됐는지에 관한 정보가 판정이 실제로 사용한 값과 어긋날 수 있다. 재현에는 임시 DB와 격리 렌더 시험을 사용했다.

### 20-5. 범위

**NONE.** 변경은 판정 날짜·상태, 아침 필수 자료 준비 판정, 관련 시험·문서 범위에 해당한다.

### 20-6. 종합 판정

**REJECTED.** 기존 재현 3건은 해소됐다. F7은 날짜가 같아도 판정과 다른 저장값의 상태가 붙는 재현 사례다.

### 20-7. 검증자 수정 내역

결과서 머리말 `STATUS`와 `VERIFIER`를 갱신하고 §20을 추가했다. 끝의 여분 빈 줄 1개를 정리했다. 제품 코드·시험, PLAN, STATE_LATEST, PROGRAM_TRUTH는 수정하지 않았다.

## 21. 검증자 보완 재검증 F7 정정(개발자 · 2026-11-13)

### 21-1. F7(P2) — 같은 거래일에 다시 저장한 다른 값의 저장 시점이 판정에 붙음

> 지금 동작은 §23 — 아래 날짜 · 종가 대조(당일 상자 · 표 '당일' 줄)와 서버 '읽는 사이 다시 저장됨' 막기는 §23 의 한 번 읽기로 바뀌어 없어졌다(표 '아침' 줄 대조만 방어로 남음).

- 원인: §19 의 대조는 날짜만 봤다. KODEX 200 은 같은 거래일에 장중 값(예: 09:53 85,045원)을 마감 뒤 값(15:56 84,240원)으로 다시 저장하므로, 날짜가 같아도 판정 응답과 상세 응답이 서로 다른 저장값을 가리킬 수 있다.
- 판정 응답에는 판정이 쓴 행의 저장 시각은 없지만 그 행의 종가(`market_context.kodex200.close` · 같은 계산)가 있다. 상세에는 끝일 행의 저장 상태 · 시각과 끝일 종가(기간 끝 종가 `end_close` · `kodexSnap` 의 값)가 있다. → **날짜와 종가가 모두 같을 때만 같은 저장값**으로 보고 저장 시점을 붙인다(`lib/marketNowText.ts :: regimeBasisClose` · `sameStoredPrice` · 어느 한쪽이라도 모르면 같다고 하지 않음).
- 적용 자리(§19 와 같은 셋 · 일괄): 당일 판정 상자 아래 줄(`kodexBasisText(detail, {date, close})`) · 판정 표 '당일' 줄(같은 저장값이 아니면 '저장 시점 확인 필요' · [?] = '판정 종가 85,045원 · 가격 상세 84,240원 — 같은 날 다른 저장값이라 저장 시점을 붙이지 않음') · 판정 표 '아침' 줄(아침 판정이 계산됐으면 그 종가와 기준일 행 종가도 대조).
- 같은 종류의 틈을 서버에서도 막음(`app/pc_morning_basis.py :: morning_regime`): 아침 기준은 저장 상태를 본 기준일 행과 판정 이력을 따로 읽는다 — 그 사이 같은 날 값이 다시 저장되면(이력 끝 행 종가 ≠ 확인한 기준일 행 종가 · 끝 행 날짜 ≠ 기준일) 판정하지 않고 'KODEX 200 M/D 가격을 읽는 사이 다시 저장됨 — [요약 다시 읽기]' → KODEX 200 판정 근거 미충족(§19 F5 규칙 그대로) · 준비됨 아님.
- 남는 한계(구조상): 판정 응답과 상세 응답은 따로 읽는다. 날짜 · 끝 종가가 같아도 그 사이 과거 가격 행이 다시 저장되면(전체 ETF 갱신은 과거 행도 다시 씀) 이동평균 · 수익률 · 판정이 달라질 수 있어, 이 대조만으로는 판정이 쓴 저장본을 확인하지 못한다(검증자 §22 F8 로 재현 · 정정 방향은 §23).

### 21-2. 시험 · 변이

| 시험 | 조합 |
|---|---|
| `lib/refreshCompare.test.ts` | 같은 저장값(날짜 · 종가) = 저장 시점 붙음 2 / null: 다른 날 2 · 판정 날짜 모름 · **F7 장중 판정 · 마감 뒤 상세 · F7 마감 뒤 판정 · 장중 상세** · 판정 종가 모름 · 상세 끝일 종가 모름 |
| `today/TodayQuickRefresh.test.tsx` | 화면 상자 + 표 '당일' 줄: 같은 저장값 마감 뒤 · 같은 저장값 장중(85,045 · '09:53 장중 저장') · F4 다른 날 · **F7 두 방향**(상자 · 표에 '마감 뒤 저장' · '장중 저장' 글자 없음 · [?] 문장) · 상세 읽기 실패 / 표 '아침' 줄: 다른 날 행 · **같은 날 판정 종가와 다른 저장값** = 상태 · 출처 없음. 기존 흐름 문장 시험 자료에 판정 종가(84,240 · 상세 끝일 값과 같음)를 넣음 |
| `tests/test_poc6_29_morning_basis.py` | 기준일 행과 판정 이력 사이 다시 저장(끝 종가 +805) = 판정 unconfirmed · 사유 · KODEX 200 미충족 · 준비됨 아님 · `missing=["kodex200"]` |

- 변이(복원 = 내용 쓰기 + touch + `cmp` · `PYTHONDONTWRITEBYTECODE=1`): 같은 저장값 = 날짜만(7건 실패) · 상자 문장 날짜만(6건) · 표 '당일' 줄 날짜만(2건) · 표 '아침' 줄 종가 대조 빼기(1건) · 서버 다시 저장 막기 빼기(1건) — 5종 모두 잡힘.

### 21-3. 자체 검수 · 범위

- 백엔드: `black --check` · `flake8`(저장소 `setup.cfg`) · `py_compile` 통과 · 관련 3개 파일 68건 통과. 백엔드 전체 회귀는 다시 돌리지 않았다 — 바뀐 백엔드 코드는 이번 POC 의 새 파일 `app/pc_morning_basis.py` 하나 · 사용처 = `app/api.py` 라우터 · 그 시험뿐(§19-5 와 같음).
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,414건** 통과(새 8건).
- 격리 서버: 8001 을 정정 코드로 다시 띄움 · 아침 기준(기준일 11/12) = 기준일 행 84,240원 마감 뒤 · 판정 종가 84,240 · 판정 ok(다시 저장 막기에 걸리지 않음). 화면 13:37 = 판정 종가 · 상세 끝일 종가가 같은 평소 경우라 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)' · 표 아침 · 당일 줄 '11/12 마감 뒤 저장' 그대로 · 콘솔 · HTTP 오류 0 · 1400px 넘침 0.
- 바뀐 파일(이번 정정): `app/pc_morning_basis.py` · `tests/test_poc6_29_morning_basis.py` · `frontend/lib/marketNowText.ts` · `frontend/lib/refreshCompare.ts` · `frontend/app/components/today/MarketFlowBlock.tsx` · `frontend/app/components/today/RegimeBasisTable.tsx` · 시험 `frontend/lib/refreshCompare.test.ts` · `frontend/app/components/today/TodayQuickRefresh.test.tsx` · 문서 이 결과서(STATUS · VERIFIER · §17-2 · §17-7 · §19-1 표 머리 · §21) · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`. 새 의존성 · 스키마 · 배포 경로 변경 없음.

## 22. 검증자 F7 정정 재검증(Codex · 2026-11-13)

§21의 정정 제출을 stage 기준으로 확인했다. 기준 커밋은 `2c40ea69`이며 §20 스냅샷과 비교해 제품 5개, 시험 3개, 문서 3개가 달라졌다. V2 §2~3과 PLAN §10-2·§10-3에 따라 판정 수치와 함께 표시되는 저장 시점과 근거를 검증했다.

### 22-1. A. 기능과 산출물

- **A-1 지시 일치 위반.** §20의 같은 날짜·다른 종가 두 방향과 정상 대조군 두 건이 통과했다. 아침 판정은 기준일 행과 이력의 끝 종가가 달라지면 미확인·미완료로 표시한다. 같은 날짜·같은 종가에서 이력이 바뀐 경우와 상세 종가를 읽을 수 없는 경우에는 F8·F9가 재현됐다.
- **A-2 보고 정확성 위반.** §21에 적은 변경 파일 목록은 실측과 같다. 같은 날 같은 종가이면 이력과 판정 값도 같다는 §21-1 설명은 F8 재현 결과와 어긋난다. 총 173개 stage(신규 66, 수정 77, 내용이 같은 이동 30)이며 미 stage·미추적은 0이다.
- **A-3 산출물 정합성 위반.** 당일 판정 상자와 표가 다른 이력의 저장 시점을 붙일 수 있다. 표 도움말은 값이 확인되지 않은 경우에도 서로 다른 값이라고 설명한다.
- **A-4 금지사항 위반 없음.** 이번 변경에는 신규 의존성, 외부 API 추가, 파일 삭제, DB 스키마 변경이 없다.

#### F8(P2) — 같은 날 같은 종가라도 이력이 달라지면 다른 판정의 저장 시점이 붙음

`frontend/lib/marketNowText.ts:138~142`는 거래일과 끝 종가를 대조한다. `frontend/lib/refreshCompare.ts:52~59`와 `frontend/app/components/today/RegimeBasisTable.tsx:90~92`는 두 값이 같으면 상세의 저장 시점을 표시한다. 전체 ETF 갱신은 과거 120일 범위의 가격 행도 같은 저장 작업에서 갱신한다(`app/market_refresh_service.py:338~342`, `app/market_data_fdr.py:279~313`, `app/market_data_store.py:279~289`). 끝 종가가 같아도 이동평균·수익률에 쓰인 과거 값은 바뀔 수 있다.

임시 SQLite DB에서 11/12 09:53 저장본(끝 종가 85,045원, 이전 행 85,050원)으로 판정을 계산했다. 기존 가격 갱신 함수에 가짜 공급 응답을 넣어 15:56에 같은 끝 종가와 바뀐 과거 가격(85,040원)을 저장했다. 외부 호출 없이 기존 함수가 실제 DB 행을 갱신했다.

| 자료 | 끝 종가 | 판정 |
|---|---:|---|
| 09:53 장중 저장본 | 85,045원 | 하락장 −2점 |
| 15:56 마감 뒤 저장본 | 85,045원 | 상승장 +2점 |

이전 판정 응답과 새 상세 응답을 화면에 넣자 판정 상자와 표가 **하락장에 ‘15:56 마감 뒤 저장’**을 붙였다. §21에 이미 적힌 저장 시각 식별 한계에 더해, 같은 끝 종가에서도 산출값이 달라지는 실제 코드 경로를 확인했다. 과거 이력이 그대로인 경우에는 계산 결과가 동일할 수 있지만, 응답의 끝 종가로 그 조건을 확인할 수 없다.

#### F9(P3) — 상세 끝일 종가를 확인하지 못한 경우를 ‘다른 저장값’으로 설명

`frontend/app/components/today/RegimeBasisTable.tsx:109~117`의 도움말은 날짜가 같고 저장 시점 표시 조건이 충족되지 않으면 종가가 있는지와 관계없이 ‘같은 날 다른 저장값’이라고 쓴다. 가상 ETF 한 종목의 11/13 가격만 추가한 임시 DB에서 KODEX 200 상세는 끝일 11/12의 상태를 보냈지만, 시장 공통 끝일과 달라 `daily/w5/w20/m1`의 끝 종가가 모두 비었다. 상자와 표 본문은 ‘저장 시점 확인 필요’로 표시했지만, 도움말은 **‘가격 상세 — — 같은 날 다른 저장값’**으로 표시했다.

검증자 실측은 격리 사본 프런트 제품 시험 14파일 282건, 이전 독립 화면 재현·대조군 6건, 백엔드 70건 통과다. 신규 독립 재현 2건에서 F8·F9를 확인했다. 타입 검사, 변경 프런트 파일 ESLint, 변경 Python 파일 black·flake8(저장소 설정)·컴파일이 통과했다. 이전 독립 화면 파일의 복제된 제품 시험 2건은 이전에 사용하던 가짜 응답에 새로 필수인 종가가 빠져 실패했다. 해당 검증 사본에서는 이전 재현 6건을 선별 실행하고, 제출한 제품 시험 282건은 별도 실행해 통과했다. 전체 회귀는 §17-7 및 §21-3의 개발자 실측 범위를 인용했다. 독립 재현과 로그는 `/private/tmp/poc629-f7-verify-qe3ziFQW/`에 보관했다.

### 22-2. B. 구현 구조

- **B-1 암묵 기본값.** 값이 없을 때 저장 시점을 표시하지 않는 본문 분기는 확인했다. F9는 같은 경우에 잘못된 사유를 내보내는 표시 문제다.
- **B-2 단일 책임.** 날짜·종가 대조는 공통 함수에 모였다.
- **B-3 파일 크기.** 아침 기준 모듈 442줄, 판정 표 164줄, 변경 화면 시험 616줄로 해당 파일 크기 한도 이내다.
- **B-4 운영 경계.** 연구나 백테스트 경로 변경이 없다.
- **B-5 배포 경로.** 변경 파일은 Git index에서 확인했다. 배포 스크립트·패키지 설정 변경이 없다.
- **B-6 정합성.** F8은 끝 종가가 판정에 쓰인 전체 가격 이력을 식별하지 못하는 한계에서 발생한다.

### 22-3. 기반 문서

이번 변경에서 KS-10 임계 초과와 신규 의존성은 없다. D1~D4는 설계자 판단 대기이며 Q-S5(a) 실제 PC 갱신 전후 대조가 남아 있다.

### 22-4. 코드 안전성

**MEDIUM.** 판정이 계산된 저장본과 다른 시점이 표시될 수 있다. 독립 검증은 가짜 공급 응답, 임시 DB 및 격리 렌더 시험에서 수행했다.

### 22-5. 범위

**NONE.** 제출은 F7의 화면 표시와 같은 원인의 아침 판정 보완, 관련 시험과 문서 범위에 있다.

### 22-6. 종합 판정

**REJECTED.** 이전 F7 재현과 정상 대조군은 통과했다. 같은 끝 종가에서도 가격 이력과 판정이 달라지는 F8, 종가를 모를 때 불일치로 설명하는 F9를 확인했다.

### 22-7. 검증자 수정 내역

결과서의 `STATUS`와 `VERIFIER`를 갱신하고 §22를 추가했다. 끝의 여분 빈 줄을 정리했다. 검증자가 stage한 파일은 이 결과서 한 개다.

## 23. 검증자 F8 · F9 정정 — 당일 판정을 서버 한 번 읽기로(개발자 · 2026-11-13)

### 23-1. 형수님 결정(2026-11-13 · 대화 선택)

§22 F8 은 '판정 응답'과 '가격 상세'를 따로 받는 구조에서 생긴다 — 날짜 · 끝 종가를 대조해도 판정에 쓰인 과거 가격 행까지 같은지는 알 수 없다. 완전히 막는 길은 판정과 그 판정이 쓴 가격의 저장 시점을 한 번에 읽는 것뿐이라, 정정 방향을 형수님께 물었다(① 서버 한 번 읽기 · ② 저장 시점 빼고 날짜만 · ③ 설계자 판정 먼저). **형수님 선택 = ① 서버 한 번 읽기**. PLAN §10-2 의 '당일 판정 = `GET /market/topn/latest` 의 `market_context` 그대로'에서 출처가 바뀐다(설계자 S 판정 §3 '당일 판정은 오늘 시장 변화에 날짜를 붙여 표시'와 PLAN 의 '장 상태' 표시는 그대로) — 설계자 RESULT 재판정 때 확인받을 PLAN 변경이다. 기존 시장 판정 모듈(`app/market_topn.py` · `app/market_regime.py`)은 바꾸지 않았다.

### 23-2. 정정(F8)

- `app/pc_morning_basis.py`: `_kodex_rows` — KODEX 200 `(date, close, fetched_at)` 을 SQL 한 문장으로 한 번 읽는다(기존 이력 거르기와 같음: close null · 0 이하 제외 · 읽기 전용 연결 · 파일 없음 = 빈 목록 · 읽기 오류 = 응답 '읽지 못함'). KODEX 200 항목(기준일 행 · 저장 상태) · 아침 판정(기준일까지) · **새 당일 판정 `today_regime`**(이력 전체 · `compute_market_context(asof=끝일)` → `compute_regime_streak` → `kodex200_return_dates` — 시장 판정 응답과 같은 함수 · 같은 이력 거르기 · 같은 순서) + 끝 행 `basis_row{date, close, state, fetched_at_kst}`(`price_state` 기존 규칙)를 모두 이 한 번의 결과로 만든다. 이력 없음 = 'KODEX 200 저장 가격 없음' · 이력 부족 = 'KODEX 200 판정 근거 부족(저장 이력)'(unconfirmed). §21 의 '읽는 사이 다시 저장됨' 막기는 한 번 읽기로 틈이 없어져 뺐다.
- 화면: `lib/morningText.ts :: todayBasis` — 당일 판정 출처 = `today_regime`(판정 · 끝 행 저장 시점) · 칸이 없거나(옛 서버) 아침 기준을 못 읽으면 — 다시 읽기에 실패해 남은 이전 응답 포함(§25 · F10) — 시장 판정 응답의 판정과 그 날짜만(저장 시점 확인 필요 · 저장 시점 없음) · 미확인이면 '당일 판정 미확인 — 사유'. 당일 판정 상자(`MarketFlowBlock.tsx`) · 판정 표 '당일' 줄(`RegimeBasisTable.tsx`) · AI용 복사(§27)가 이 하나를 쓴다(아침 · 당일이 같은 마감 행이면 표는 '아침·당일 공통' 한 행 = 같은 이력으로 계산한 아침 판정 · §27). 저장 시점 문장 = `lib/refreshCompare.ts :: storedRowText`(같은 날 = 시각 · 다른 날 = 날짜까지 · 시각 모름 = '저장 시점 확인 필요' · 시각은 있으나 장중/마감 뒤 판단 불가 = '… 저장 · 장중인지 마감 뒤인지 확인 필요'). **따로 받은 KODEX 200 가격 상세는 판정 문장 · 표에 더는 쓰지 않는다**(`kodexBasisText` 와 §19 · §21 의 날짜 · 종가 대조 · F9 도움말 문장은 이 출처 변경으로 없어짐 · `MarketFlowBlock` · `RegimeBasisTable` 의 `kodex` 인자 제거).
- F9: 도움말 '같은 날 다른 저장값' 단정이 나오던 자리(상세 대조)가 없어졌다. 당일 줄 [?] = 같은 읽기의 'FDR 일별 가격 · HH:MM 저장'(저장 시각 있을 때만) · 출처가 시장 판정 응답(대체)일 때는 [?] 없음.
- 남는 차이(§27 반영 뒤): 「시장 수치와 거래량」 안 '기존 시장 판정 참고'는 설계자 V3 D4 로 뺐고, AI용 복사(시장 판정 줄 · [자료 상태]의 시장 판정 줄 · 확인 창)는 V3 §3 으로 같은 선택 결과를 쓴다. 화면 맨 위 「자료 최신화 필요」의 '시장 판정(KODEX 200)' 줄은 지금도 시장 판정 응답의 기준일로 판정한다(그 응답을 읽은 상태를 알리는 줄 · 이번 판정 범위 밖).

### 23-3. 시험 · 변이

| 시험 | 내용 |
|---|---|
| `tests/test_poc6_29_morning_basis.py` | 한 번 읽기(`_kodex_rows` 호출 1회 · 항목 기준일 행 · 아침 판정 · 당일 판정 끝 종가가 모두 그 결과) · 당일 판정 = 시장 판정과 같은 계산(같은 함수로 만든 기대값과 국면 · 점수 · 근거 · asof · KODEX 200 수치 · 지속일 전부 같음) × 끝 행 3가지(오늘 장중 · 기준일 마감 뒤 · 저장 시각 해석 불가 = unknown · 시각 없음) · 미확인 2가지(이력 부족 · 이력 없음) → 32건 통과 |
| `lib/refreshCompare.test.ts` | `storedRowText` 5가지(같은 날 마감 뒤 · 같은 날 장중 · 다음 날 저장 · 시각 모름 · 가격 날짜보다 앞선 시각) |
| `today/TodayQuickRefresh.test.tsx` | 당일 판정 출처 6가지(같은 읽기 마감 뒤 + 장중 상세 · 같은 읽기 장중 + 마감 뒤 상세(F7) · **F8 같은 날 같은 종가의 다른 저장본 상세** · 칸 없음 · 아침 기준 읽기 실패 · 미확인) — 상자 문장 전체 · 표 '당일' 줄 상태 · [?] 문장 · 판정 값(같은 읽기 26거래일째 ↔ 시장 판정 응답 25거래일째로 출처 구분). 흐름 문장 시험에 같은 읽기 응답을 넣음 |

- 변이(복원 = 내용 쓰기 + touch + `cmp` · `PYTHONDONTWRITEBYTECODE=1`): 당일 판정을 따로 한 번 더 읽기(1건 실패) · 저장 시점을 다른 행에서(4건) · 같은 읽기 무시하고 늘 시장 판정 응답(5건) · 표 '당일' 줄 판정만 시장 판정 응답(3건) · 장중/마감 뒤 구분 빼기(1건) — 5종 모두 잡힘.

### 23-4. 자체 검수 · 범위

- 백엔드: `black --check` · `flake8`(저장소 `setup.cfg`) · `py_compile` 통과 · 관련 3개 파일 **73건** 통과. 백엔드 전체 회귀는 다시 돌리지 않았다 — 바뀐 백엔드 코드는 이번 POC 새 파일 `app/pc_morning_basis.py` 하나 · 사용처 = `app/api.py` 라우터 · 그 시험뿐(grep `pc_morning_basis|morning-basis|morning_regime|_kodex_item`).
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,411건** 통과(§21 의 날짜 · 종가 대조 시험을 같은 읽기 출처 시험으로 바꾸며 3건 줄어듦).
- 격리 서버(8001 다시 띄움 · 14:03): 아침 기준 `today_regime` = ok · 끝 행 11/12 84,240원 15:56:59 마감 뒤 · 하락장 · -4 · 25거래일째 · -3.06% · -21.36% — 같은 시각 `GET /market/topn/latest` 의 `market_context` 와 국면 · 점수 · 지속일 · 수익률 · 종가 모두 같음. 화면 = 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)' · 콘솔 · HTTP 오류 0 · 1400px 넘침 0.
- 바뀐 파일(이번 정정): `app/pc_morning_basis.py` · `tests/test_poc6_29_morning_basis.py` · `frontend/lib/api/morningBasis.ts` · `frontend/lib/morningText.ts` · `frontend/lib/refreshCompare.ts` · `frontend/app/components/today/MarketFlowBlock.tsx` · `frontend/app/components/today/RegimeBasisTable.tsx` · `frontend/app/components/TodayInvestmentCheckView.tsx`(시장 흐름 블록 `kodex` 인자 제거) · 시험 `frontend/lib/refreshCompare.test.ts` · `frontend/app/components/today/TodayQuickRefresh.test.tsx` · 문서 이 결과서(STATUS · VERIFIER · §17-1 · §17-2 · §17-7 · §21-1 · §23) · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`. 새 의존성 · 스키마 · 배포 경로 변경 없음.

## 24. 검증자 F8 · F9 정정 재검증(Codex · 2026-11-13)

§23 정정 제출을 stage 기준으로 검증했다. 기준 커밋은 `2c40ea69`다. §22 스냅샷과 비교해 제품 7개, 시험 3개, 문서 3개가 달라졌다. §23-1에 기록된 사용자의 서버 한 번 읽기 결정과 V2 §2~3의 자료 표시·갱신 뒤 재조회 기준을 적용했다.

### 24-1. A. 기능과 산출물

- **A-1 지시 일치 위반.** 서버 한 번 읽기와 F8·F9 정정은 확인했다. 아침 기준 재조회 실패 시 시장 판정 응답과 날짜를 사용한다는 §23-2의 동작은 아래 F10에서 어긋났다.
- **A-2 보고 정확성.** 제출 파일 목록은 스냅샷과 일치한다. 총 173개가 stage됐다(신규 66, 수정 77, 내용이 같은 이동 30). 미 stage·미추적은 0개다. §23-4의 시험 수 차이와 §17-7의 화면 파일 줄 수를 정정했다.
- **A-3 산출물 정합성 위반.** 전체 갱신 후 새 시장 판정 응답을 받았더라도 아침 기준 재조회가 실패하면 이전 당일 판정과 저장 시점이 그대로 표시된다.
- **A-4 금지사항 위반 없음.** 신규 의존성, 외부 API 추가, 파일 삭제, 스키마 변경은 확인되지 않았다. 기존 시장 판정 모듈 두 곳도 기준 커밋과 같다.

#### F8 · F9 정정 확인

임시 DB에서 KODEX 200 가격 이력을 읽은 직후, 끝 종가 85,045원은 유지하고 이전 행 가격과 끝 행의 저장 시각을 갱신했다. SQL 추적으로 KODEX 200 이력·시각 조회가 한 번임을 확인했다. 기존 읽기의 장중 하락장(−2점)과 새 읽기의 마감 뒤 상승장(+2점)은 각각 자기 저장 시각과 결합됐다. 같은 DB로 기존 시장 판정 계산을 실행해 국면, 점수, 근거, 지속일과 KODEX 200 수치를 대조했다.

이전 응답과 새 상세를 화면에 넣어도 하락장은 ‘09:53 장중 저장’을 유지했다. 상세 응답에 끝일 종가가 비어 있어도, 새 응답의 상승장과 ‘15:56 마감 뒤 저장’이 함께 표시됐고 ‘같은 날 다른 저장값’ 도움말은 나오지 않았다.

#### F10(P2) — 갱신 뒤 아침 기준 재조회만 실패하면 이전 당일 판정이 남음

공유 조회는 재조회가 실패해도 이전 성공 응답을 `phase: "success", stale: true`로 보존한다(`frontend/lib/api/queryCache.ts:242~252`). 판정 상자와 표는 `phase`만 확인해 그 응답을 `todayBasis`에 넘긴다(`frontend/app/components/today/MarketFlowBlock.tsx:64`, `frontend/app/components/today/RegimeBasisTable.tsx:116`). 이 때문에 최초 읽기 실패는 시장 판정으로 대체되지만, 이전 값이 있는 재조회 실패에서는 §23-2의 대체 경로에 도달하지 않는다.

실제 화면 컴포넌트에 ‘10/29 09:53 장중 저장 · 하락장’을 먼저 표시했다. 전체 갱신 완료 뒤 시장 판정 조회는 ‘상승장’으로 성공시키고 아침 기준 재조회만 실패시켰다. 두 조회가 모두 다시 호출된 것을 확인했다. 당일 판정 상자와 표에는 **기존 하락장과 09:53 장중 저장**이 계속 표시됐다. 별도 갱신 결과 줄은 아침 기준 재조회 실패를 알리지만, 상자와 표는 이전 판정을 사용하며 ‘저장 시점 확인 필요’를 표시하지 않는다. 아침 기준 재조회까지 성공시킨 대조군은 상승장과 15:56 마감 뒤 저장으로 바뀌었다.

검증자 실측은 격리 사본 프런트 제품 시험 14파일 279건, 백엔드 관련·이전 재현 75건 통과다. 독립 SQL·산출 대조 1건과 독립 화면 3건이 통과했고, 화면 1건에서 F10을 재현했다. 타입 검사, 변경 프런트 ESLint, 변경 Python black·flake8·컴파일도 통과했다. 전체 회귀는 §17-7 및 §23-4의 개발자 실측 범위를 인용했다. 재현과 로그는 `/private/tmp/poc629-f8f9-verify-kU7RuzZU/`에 보관했다.

### 24-2. B. 구현 구조

- **B-1 암묵 기본값.** 첫 조회가 실패하거나 옛 서버 응답에 새 항목이 없을 때 적용하는 대체 경로가 명시돼 있다. 이전 응답이 남는 재조회 실패는 F10에 기록했다.
- **B-2 단일 책임.** 아침·당일 판정은 같은 읽기 결과에서 구성하고, 화면은 출처 선택 함수를 공통으로 사용한다.
- **B-3 파일 크기.** 아침 기준 모듈 475줄, 판정 표 148줄, 변경 화면 시험 646줄이다.
- **B-4 운영 경계.** 연구·백테스트 경로에 변경이 없다.
- **B-5 배포 경로.** 관련 파일은 Git index에서 확인했다. 배포 스크립트·패키지 설정 변경은 없다.
- **B-6 정합성.** 가격 상세를 판정과 합치던 경로가 제거됐다. 대체 출처는 캐시의 재조회 실패 상태와 연결되지 않았다.

### 24-3. 기반 문서

이번 변경에는 KS-10 임계 초과가 없다. PLAN §10-2의 출처 변경은 §23-1에 기록된 사용자 결정에 해당하며 설계자 RESULT 재판정에서 확인할 사항이다. D1~D4와 실제 PC 갱신 전후 대조 Q-S5(a)도 남아 있다.

### 24-4. 코드 안전성

**MEDIUM.** 갱신 뒤 새 판정을 받았는데도 이전 당일 판정이 표시될 수 있다. 검증에는 임시 DB와 격리 렌더 시험을 사용했다.

### 24-5. 범위

**NONE.** 제출 변경은 사용자 결정에 따른 당일 판정 출처 변경과 관련 시험·문서 범위에 해당한다.

### 24-6. 종합 판정

**REJECTED.** F8·F9는 해소됐다. 갱신 뒤 아침 기준만 재조회에 실패하는 F10을 확인했다.

### 24-7. 검증자 수정 내역

결과서 머리말 `STATUS`와 `VERIFIER`를 갱신하고 §24를 추가했다. §17-7의 화면 파일 줄 수를 761에서 760으로, §23-4의 시험 감소 수를 4에서 3으로 정정했다. 끝의 여분 빈 줄을 정리했다. 검증자가 stage한 파일은 결과서 한 개다.

## 25. 검증자 F10 정정 — 다시 읽기 실패로 남은 이전 응답을 당일 판정에 쓰지 않음(개발자 · 2026-11-13)

### 25-1. 원인 · 정정

- 원인: 공유 조회 캐시는 다시 읽기가 실패해도 이전 성공 응답을 `phase: "success", stale: true` 로 남긴다(`lib/api/queryCache.ts` · 화면이 이전 값을 '이전 조회값'으로 보이게 하는 기존 계약). 당일 판정 출처 함수(`lib/morningText.ts :: todayBasis`)가 아침 기준 응답의 `phase` 만 보고 받았기 때문에, 갱신 뒤 아침 기준만 다시 읽기에 실패하면 이전 당일 판정 · 저장 시점이 그대로 남았다(대체 경로 = 첫 조회 실패 · 칸 없음만 탔다).
- 정정: `todayBasis(morning: QueryState, marketCtx)` — 아침 기준 응답이 **지금 성공**(`phase === "success"` 이고 `stale` 아님)일 때만 같은 읽기의 당일 판정을 쓴다. 이전 응답 · 첫 조회 실패 · 불러오는 중 · 칸 없음 · 읽기 실패 응답은 모두 시장 판정 응답의 판정 · 날짜만('KODEX 200 M/D 가격 기준(저장 시점 확인 필요)' · 저장 시점 없음). 규칙은 이 함수 한 곳이고 당일 판정 상자(`MarketFlowBlock.tsx`)와 판정 표 '당일' 줄(`RegimeBasisTable.tsx`)이 같은 조회 상태를 넘긴다. 표 '아침' 줄 · 아침 요약은 이전 응답이어도 그대로 보인다(아래 안내가 함께).
- 안내(같은 카드의 원천 전수): 카드 아래 '다시 읽기 실패' 줄(`joinStale`)이 지금까지 수급 · 환율 · 유가 · KOSPI 가격 흐름만 알렸다 — 이 카드가 쓰는 원천을 다시 세어(아침 기준 · 시장 판정 · 수급 · 환율 · 유가 · 수급 5거래일 · KOSPI 가격 흐름 · 빠른 시세) **아침 요약 기준 · 시장 판정 · 수급 5거래일의 '다시 읽기 실패 · HH:MM 에 읽은 값을 표시 중'** 을 더했다. 첫 조회 실패는 각 자리에서 이미 보인다(아침 요약 '불러오지 못했습니다' · 당일 판정 '불러오지 못했습니다' · 5거래일 '확인 불가'). 빠른 시세는 3칸 자리에 따로 안내가 있다(기존).

### 25-2. 시험 · 변이

| 시험 | 내용 |
|---|---|
| `lib/morningText.test.ts` | `todayBasis` 조합 7가지: 지금 성공 + 같은 읽기 = 같은 읽기 · **다시 읽기 실패로 남은 이전 응답(stale)** = 시장 판정 · 날짜만 · 첫 조회 실패 · 불러오는 중 · 칸 없음 · 읽기 실패 응답(`today_regime: null`) = 시장 판정 · 날짜만 · 같은 읽기 미확인 = '당일 판정 미확인 — 사유' |
| `today/TodayQuickRefresh.test.tsx` | 화면 2경로: **③ 전일 자료 보충 완료 뒤 시장 판정 = 새 값(상승장 3거래일째) · 아침 기준만 다시 읽기 실패**(검증자 재현 경로) → 상자 · 표 '당일' 줄 = 상승장 · 날짜만 · 하락장 · '09:53 장중 저장' 없음 · 카드 아래 '아침 요약 기준: 다시 읽기 실패' · 끝 줄 '아침 요약 기준을 다시 읽지 못했습니다' / [요약 다시 읽기](시장 판정은 다시 읽지 않는 기존 동작)에서 아침 기준만 실패 → 그대로인 시장 판정 · 날짜만 · 이전 같은 읽기(26거래일째 · 09:53) 없음 · 안내 |

- 변이(복원 = 내용 쓰기 + touch + `cmp`): 이전 응답도 출처로(3건 실패) · 카드 아래 줄에서 아침 기준 빼기(2건) · 표 '당일' 줄만 이전 응답 사용(2건) · 상자만 이전 응답 사용(2건) — 4종 모두 잡힘.

### 25-3. 자체 검수 · 범위

- 이번 정정은 화면만 바꿨다(서버 · 응답 그대로 · 백엔드 시험 · 회귀 대상 없음).
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,420건** 통과(새 9건 = 출처 조합 7 + 화면 2).
- 격리 화면(14:26 · 다시 읽기 실패 없는 평소 경우): 'KODEX 200 11/12 가격(15:56 마감 뒤 저장)' 그대로 · 카드 아래 '다시 읽기 실패' 줄 없음 · 콘솔 · HTTP 오류 0 · 1400px 넘침 0.
- 바뀐 파일: `frontend/lib/morningText.ts` · `frontend/app/components/today/MarketFlowBlock.tsx` · `frontend/app/components/today/RegimeBasisTable.tsx` · 시험 `frontend/lib/morningText.test.ts` · `frontend/app/components/today/TodayQuickRefresh.test.tsx` · 문서 이 결과서(STATUS · VERIFIER · §23-2 규칙 문장 · §25) · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`. 새 의존성 · 스키마 · 배포 경로 변경 없음.

## 26. 검증자 F10 정정 재검증(Codex · 2026-11-13)

§25 정정 제출을 stage 기준으로 검증했다. 기준 커밋은 `2c40ea69`다. §24 스냅샷과 비교해 제품 프런트 3개, 시험 2개, 문서 3개가 바뀌었다. V2 §2~3의 갱신 뒤 표시 기준과 §23에 기록한 사용자의 판정 출처 결정을 기준으로 삼았다.

### 26-1. A. 기능과 산출물

- **A-1 지시 일치 통과.** 당일 상자와 표가 공통 `todayBasis`에서 아침 기준의 재조회 실패 상태를 확인한다. 전체 갱신 뒤 아침 기준만 실패시킨 §24 독립 재현에서 상자와 표가 이전 장중 하락장에서 새 시장 응답의 상승장으로 바뀌었고 ‘저장 시점 확인 필요’가 표시됐다. 전일 자료 보충 완료와 요약 다시 읽기에서도 개발자 시험으로 확인했다.
- **A-2 보고 정확성 통과.** 제출 변경 파일 목록과 Git 스냅샷이 일치한다. 총 173개 stage(신규 66, 수정 77, 내용이 같은 이동 30), 미 stage·미추적 0개다.
- **A-3 산출물 정합성 통과.** 갱신 뒤 아침 기준이 성공하면 같은 응답에서 받은 새 판정과 저장 시각이 함께 표시됐다. 두 재조회가 모두 실패하면 당일 판정을 불러오지 못했다고 알린다. 아침 요약에 남은 이전 응답은 카드 아래 재조회 실패 안내와 함께 표시된다. F8·F9 독립 화면 사례도 통과했다.
- **A-4 금지사항 위반 없음.** 외부 호출, 의존성, 파일 삭제, 스키마 변경을 추가하지 않았다.

격리 사본에서 프런트 제품 시험 14파일 288건, 이전 독립 재현·대조 4건, 두 재조회 동시 실패 1건이 통과했다. 타입 검사와 변경 파일 ESLint도 통과했다. 백엔드는 §24 스냅샷과 일치해 당시 관련 75건과 독립 SQL 확인 1건을 근거로 사용했다. 프런트 전체 1,420건은 §25-3의 개발자 실측이다. 검증 사본과 로그는 `/private/tmp/poc629-f10-verify-NkjXk5fd/`에 보관했다.

### 26-2. B. 구현 구조

- **B-1 암묵 기본값 위반 없음.** 아침 기준을 사용할 수 없을 때 시장 판정과 날짜만 쓰는 기존 대체 경로에 재조회 실패 상태가 연결됐다.
- **B-2 단일 책임 위반 없음.** 판정 출처 선택은 `todayBasis`, 안내 문구는 기존 `staleOf`에 맡긴다.
- **B-3 파일 책임 과다 없음.** 판정 상자 모듈 115줄, 판정 표 149줄, 변경 화면 시험 742줄로 각 한도 안이다.
- **B-4 운영 경계 위반 없음.** 연구·백테스트 경로에는 변경이 없다.
- **B-5 배포 경로 영향 없음.** 변경 파일과 결과서의 Git 추적 상태를 확인했다. 패키지 설정과 배포 스크립트 변경은 없다.
- **B-6 구조적 퇴행 없음.** 상자와 표가 동일 조회 상태와 공통 출처 규칙을 사용한다. 시험 파일 `frontend/lib/morningText.test.ts` 끝에 빈 줄 하나가 있어 `git diff --cached --check`가 이를 지적한다. 기능·구조 판정에는 영향이 없다.

### 26-3. 기반 문서

변경 범위에서 KS-10 임계 초과는 없다. 당일 판정 출처 변경과 D1~D4는 설계자 RESULT 재판정 항목이다. 실제 PC 갱신 전후 대조 Q-S5(a)는 대기다.

### 26-4. 코드 안전성

**NONE.** 검증 범위에서 새 결함이 확인되지 않았다. 이전 아침 응답의 저장 시점이 새 당일 판정에 붙지 않는 것을 격리 화면 시험에서 확인했다.

### 26-5. 범위

**NONE.** 당일 판정 출처 선택, 같은 카드의 재조회 실패 안내, 관련 시험과 문서 변경이다.

### 26-6. 종합 판정

**VERIFIED (격리 구현 재검증).** F10 재현과 인접 경로를 확인했다. 다음은 설계자 RESULT 재판정이다.

### 26-7. 검증자 수정 내역

결과서 한 파일의 `STATUS`와 `VERIFIER`를 갱신하고 §26을 추가했다. §17-7의 판정 표 줄 수를 148에서 149로 맞추고 결과서 끝의 여분 빈 줄을 정리했다. 검증자가 수정하고 stage한 파일은 이 결과서 한 개다.

## 27. 설계자 RESULT 재판정 V3 마감 보완(개발자 · 2026-11-13)

판정서 = `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_V3_2026-11-13.md`(PASS_WITH_CLOSING_CORRECTIONS · §26 격리 검증 · 당일 판정 출처 변경 · 11/13 배치 수용). 마감 전 할 일 = D1 ~ D4 · §3 복사 · 변경 화면 확인 · Q-S5 (a) 실제 PC 대조 · 종료 기록.

### 27-1. 형수님 선택(D2 상자 · 2026-11-13 · 대화 선택)

D2 의 '당일 상자는 … 기준만 짧게 알린다'가 두 갈래로 읽혀(상자에서 판정 문장을 빼고 기준만 · 판정 문장은 두고 기준 줄만 짧게) 미리보기와 함께 물었다. **형수님 선택 = 상자는 기준만**: 같은 마감 자료일 때 상자 = '당일 판정 — 아침과 같은 M/D 마감 뒤 저장값 기준' + 아래 줄 '하락장(25거래일째) · 판정 근거는 위 아침 요약 · 아래 표'(고른 미리보기 그대로 · 판정 문장 · 근거는 위 아침 요약과 아래 표에). 날짜 · 저장 상태가 다르거나 같은 자료인지 확인할 수 없으면 예전처럼 판정 문장 + 저장 시점.

### 27-2. 구현

| 항목 | 바꾼 것 |
|---|---|
| D1 점수 | 판정 표 '점수' 열(국면 다음) = 그 행 판정과 같은 응답의 `regime_score`('-4점' · '0점' · '+2점' · `morningText.ts :: scoreText`) · 판정이 없는 행 = '확인 불가'. 제목 옆 [?](이름 '점수 산식 보기' · 열면 제목 아래로 펼침 — 떠 있는 상자는 좁은 화면에서 옆으로 넘쳐서) = 네 조건 · 경계 · 판정 기준 + 이동평균 거리 한계 문장(예전 코스피 구역 'ⓘ 이 값의 한계' — D3 로 그 구역이 빠져 옮김). 경계값은 화면에 숫자를 따로 두지 않고 서버가 기존 판정 상수를 그대로 싣는다(`app/pc_morning_basis.py :: SCORE_RULE` ← `market_regime.SCORE_THRESHOLD_20D_PCT` · `SCORE_THRESHOLD_60D_PCT` · `REGIME_BULL_MIN_SCORE` · `REGIME_BEAR_MAX_SCORE` · 응답 `score_rule` · 읽기 실패 응답에도). 아침 기준을 불러오는 중이면 '점수 산식을 불러오는 중입니다.' · 못 읽으면 '점수 산식을 불러오지 못했습니다(아침 요약 기준 읽기 실패).'(둘 다 한계 문장은 남김) |
| D2 공통 한 행 | `morningText.ts :: commonClosedRow` — 아침 기준 응답이 지금 성공(이전 응답 아님 · `status: ok`)이고 아침 · 당일 판정이 모두 ok 이며, 당일 끝 행과 KODEX 200 기준일 행이 같은 날짜 · 둘 다 마감 뒤 저장 · 같은 종가일 때만 '아침·당일 공통(M/D 마감)' 한 행(값 = 아침 판정 · 같은 한 번 읽기의 같은 이력으로 계산돼 당일 판정과 같음) · 상자는 27-1. 그 밖(새 당일 자료 · 장중 · 저장 시점 확인 불가 · 종가 다름 · 아침 미확인 · 당일 미확인 · 칸 없음 · 읽기 실패 · 이전 응답)은 두 행 |
| D3 이동평균 | 판정 표 '가격 · 이동평균' 칸 = '84,240원 · 20일선 87,415원 · 3.63% 아래 · 60일선 100,419원 · 16.11% 아래'(그 행 판정의 같은 응답 `ma20` · `ma20_distance_pct` · `ma20_position` · 값 없음 = '20일선 자료 없음' · 거리 없음 = '거리 자료 없음'). 코스피 구역(`today/KospiHeadline.tsx`)의 'KODEX200 기준선 대비 위치'(MA 거리 · 기준일 · ⓘ 한계) 블록과 `kodex200BaseDate` 를 뺐다. 같은 날 판정 기준은 '가격이 이동평균과 같으면 아래(-1)'라 거리 0 이면 '0.00% 아래'(점수 산식과 같은 말) |
| D4 기존 판정 참고 | 코스피 구역 「시장 수치와 거래량」의 '기존 시장 판정 참고'(국면 · 지속일 · KODEX200 기준일) 블록과 그에 딸린 접힌 칸 안내('시장 판정 확인 불가' · '기존 시장 판정 지속일 자료 없음')를 뺐다. 코스피 수익률 · 위치(자기 배지 · 기준일 · 한계) · KODEX200 거래량(자기 기준일)은 그대로 |
| §3 복사 | `lib/todayMarketCopyText.ts` — '[시장 판정]' 줄 = 화면과 같은 선택 결과(`todayBasis`) · 'KODEX 200 {국면} · N거래일째 · {기준일} · KODEX 200 M/D 가격(HH:MM … 저장)' / 저장 시점 모름 = '· 저장 시점 확인 필요' / 미확인 · 실패 = 화면과 같은 사유. 같은 글의 [자료 상태] '시장 판정(KODEX 200)' 줄 · 복사 전 확인 창도 같은 선택 결과로 판정(`todayFreshness.ts :: FreshSources.verdict` · 복사에서만 · 한 글 안에서 두 날짜로 갈리지 않게) |

### 27-3. 독립 검토 1회(코드 계약 · 문서-코드 대조 · 읽기 전용 2명) → 정정

- **복사 글 안 두 날짜(중간)**: [시장 판정] 줄은 같은 선택 결과인데 [자료 상태]의 '시장 판정(KODEX 200)' 줄 · 확인 창은 시장 판정 응답 기준일을 써서, 시장 판정 응답만 실패하거나 이전 값이면 같은 글에 '2026-11-12'와 '자료 없음 · 11/11 늦음'이 함께 나올 수 있었다 → 27-2 §3 대로 정정.
- **두 응답 모두 못 쓸 때 사유가 셋**(상자 '당일 판정을 불러오지 못했습니다' · 표 '시장 판정을 불러오지 못했습니다' · 복사 '확인 불가') → 사유를 `todayBasis` 한 곳에서 정해(시장 판정 응답 실패 = '당일 판정을 불러오지 못했습니다' · 응답은 왔으나 판정 칸 없음 = '당일 판정 확인 불가(시장 판정 자료 없음)' · 불러오는 중 = 없음) 상자 · 표 · 복사가 같은 문장. 응답은 왔는데 판정 칸이 없으면 예전에는 상자가 그려지지 않고 표가 '불러오는 중'에 머물렀다(이번에 함께 고침).
- **표 '아침' 줄 '불러오는 중' 고착**(아침 기준 첫 조회 실패 · 읽기 실패 응답) → '아침 요약 기준을 불러오지 못했습니다' · 응답 메시지 · '아침 판정 확인 불가'.
- **[?] 문구**: 불러오는 중에도 '읽지 못했습니다(… 응답 없음)'라 나오던 것 → 27-2 D1 의 두 문장('응답' 같은 개발 용어 뺌).
- **쓰이지 않게 된 함수**: `today/todayHelpers.ts :: maDistanceText`(D3 로 사용처 없음) 삭제.
- 문서: PROGRAM_TRUTH · 이 결과서(§17-1 · §17-2 · §17-10 · §17-10-1 머리 · §23-2)의 낡은 문장을 지금 동작으로 바꿈.
- 검토 지적 중 유지: 공통 행 상자 둘째 줄(국면 · 지속일)은 형수님이 고른 미리보기에 있던 그대로라 두었다.

### 27-4. 시험 · 변이

| 시험 | 내용 |
|---|---|
| `tests/test_poc6_29_morning_basis.py` | `score_rule` = 기존 판정 상수 그대로(정상 · 읽기 실패 응답 둘 다) → 33건 |
| `lib/morningText.test.ts` | `scoreText` 5가지(-4 · 0 · +2 · null · 없음) · `scoreRuleText`(다른 경계값 3 · 6 · 3 · -3 으로 응답 값 그대로임 확인 · 불러오는 중 · 못 읽음 · 한계 문장 유지) · `commonClosedRow` 11가지(같은 행 / 이전 응답 · 다른 날 · 장중 · 저장 시점 확인 불가 · 종가 다름 · 아침 미확인 · 당일 미확인 · 칸 없음 · 읽기 실패 응답 · 첫 조회 실패) · `todayBasis` 시장 판정 응답 상태 3가지(실패 · 판정 칸 없음 · 불러오는 중) |
| `lib/todayFreshness.test.ts` | 복사의 '시장 판정(KODEX 200)' 줄 = 선택 결과(시장 판정 응답 실패여도 같은 읽기 날짜 · 다른 날 이전 값이어도 선택 결과 날짜 · 둘 다 못 쓰면 화면 사유 · 미확인 사유 · 불러오는 중이면 줄 없음 · verdict 없으면 예전대로) |
| `lib/todayMarketCopyText.test.ts` | 시장 판정 줄 4가지(같은 읽기 저장 시점 · 대체 날짜만 · 미확인 사유 · 둘 다 없음) · 시장 판정 응답이 없으면 화면과 같은 사유 |
| `today/TodayMarketFlow.test.tsx` | 화면: D2 공통 한 행 + 상자 문장 전체 + 점수 '-4점' + 복사 줄이 같은 판정 · 두 행 5가지(새 당일 자료 · 같은 날 장중 · 아침 미확인 · 종가 다름 · 칸 없음) · D1 행마다 점수(+2점 · 확인 불가) · [?] 산식 문장 · D3 '20일선 87,415원 · 3.63% 아래 · 60일선 100,419원 · 16.11% 아래' · 두 응답 실패 = 상자 · 표 · 복사 같은 사유 + 아침 줄 실패 안내 + [?] '불러오지 못했습니다' · 시장 판정 응답만 실패 = 복사의 시장 판정 줄 · [자료 상태]가 같은 날짜(자료 없음 아님) |
| 기존 시험(D3 · D4 계약으로) | `TodayInvestmentCheckView.test.tsx`(시장 응답 반영 대기 신호 = 판정 표 '당일' 줄 · §3.1 강제 분리 = 'KODEX 200' 판정 표에만 · MA 거리 = 판정 표 · AC-11 한계 = 제목 옆 [?] 닫힌 채 · B-1 결측 = '20일선 자료 없음' · 지속일 = 판정 표) · `today/TodayFolds.test.tsx`(기본 칸 = 일간 변화만 · 판정 · 기준선 날짜 없음 · 거래량은 자기 기준일 · 접힌 칸 안내에 시장 판정 없음) · `today/StoredVolumeAndPriceBasis.test.tsx` · `KospiStatusSurfaces.test.tsx` |

- 변이(되돌리면 실패하는가 · 복원 = 내용 쓰기 + touch + `cmp` · `PYTHONDONTWRITEBYTECODE=1`): 서버 경계값 바꿈 · 공통 행 늘 없음 · 공통 행 장중 허용 · 공통 행 이전 응답 허용 · 상자 기준만 끄기 · 복사가 시장 판정 응답 · 판정 없는 행 점수 칸 빼기 · 이동평균 거리 빼기 · 산식 숫자 고정 · 복사 [자료 상태]가 선택 결과 무시 · 화면이 복사 선택 결과를 안 넘김 · 둘 다 실패 사유 빼기 · 아침 줄 실패를 '불러오는 중'으로 · [?] 불러오는 중 구분 빼기 — 14종 모두 잡힘.

### 27-5. 마감 확인

- **변경 화면 확인(격리 3001 · 8001 다시 띄움 · 버튼 누르지 않음 · 캡처는 저장소 밖)**: 아침 기준(11/13 · 기준일 11/12)과 당일 판정이 같은 11/12 15:56:59 마감 뒤 저장 행 → 표 '아침·당일 공통(11/12 마감)' 한 행 · 하락장 · 25거래일째 · '-4점' · '-3.06% (10/15 → 11/12)' · '-21.36% (8/13 → 11/12)' · '84,240원 · 20일선 87,415원 · 3.63% 아래 · 60일선 100,419원 · 16.11% 아래' · '11/12 마감 뒤 저장'. 상자 = '당일 판정 — 아침과 같은 11/12 마감 뒤 저장값 기준' / '하락장(25거래일째) · 판정 근거는 위 아침 요약 · 아래 표'. [?] = 산식(서버 경계값 2 · 5 · 2 · -2) + 한계 문장. 코스피 구역 = 숫자 → 칸 → 차트 → 일간 변화 → 마지막 자료 기준일 · 출처 → 「시장 수치와 거래량」(코스피 수익률 · 위치 · KODEX200 거래량 자기 기준일 11/12) — 기준선 · 기존 판정 블록 없음. 복사의 시장 판정 줄(브라우저 안에서 가로챔) = '[시장 판정] KODEX 200 하락장 · 25거래일째 · 2026-11-12 · KODEX 200 11/12 가격(15:56 마감 뒤 저장)'(화면과 같은 판정 · 기준일 · 저장 상태). 콘솔 · HTTP 오류 0 · 1400px 넘침 0 · 400px 565px(닫힘 · [?] 열림 모두 · 이전과 같은 값 · 앱 왼쪽 메뉴). '새 당일 자료에서 두 행' · 재조회 실패 안내는 격리 자료로 만들 수 없어 위 화면 시험으로 확인.
- **Q-S5 (a) 실제 PC(저장소 본 작업 폴더 · 8000 · 기존 화면 · 읽기 전용 · `sqlite mode=ro` + GET · 스냅숏 스크립트와 JSON 은 저장소 밖)**: 형수님이 11/13 실제 PC 에서 평소처럼 [최신 자료 갱신]을 누름 → 시장 갱신 `market_refresh_20261113_075344_fa1bbe` 16:53:44 ~ 16:59:02 KST `completed`(갱신 기록 5줄 모두 실패 0 · KRX 코스피 · 보유 가격 · 원/달러 · WTI · OCI 수급 가져오기 · 반영). 기준일(직전 국내 거래일) = 11/12.

| 자료 | 직전(11/13 15:31) | 직후(11/13 17:18) | 기준일 11/12 |
|---|---|---|---|
| 코스피 공식 종가(PC 저장 · 화면) | 11/9 · 화면 '지연'(stale) | **11/12 5,342.73** · 16:58:55 저장(KRX) · 화면 `display_state=ok` · 시장 흐름 표시일 11/12 | 충족 |
| KODEX 200 마감 가격 · 판정 기준일 | 마지막 11/10 81,345원 장중 저장(13:18) · 11/12 행 없음 · 화면 판정 11/10 기준 하락장 23거래일째 | **11/12 84,240원**(11/13 16:54:48 저장 = 가격일 뒤 · 마감 뒤) · 마지막 행 11/13 83,115원(16:54:48 = 15:30 뒤 · 마감 뒤) · 화면(기존 코드) 판정 = 11/13 기준 하락장 26거래일째 | 충족 |
| 투자자 수급(PC 저장 · 표시) | 11/9 | **11/12** · OCI 수집본(11/13 09:47 수집) PC 반영 16:59 · 화면 '수급은 OCI 수집본을 PC에 반영(11/13 16:59 KST · 11/12까지)' | 충족 |
| 원/달러 · WTI(필수 아님) | — | 11/12 · 11/12 | — |

  원천 대기 · 실패 없음(직전에 늦었던 원인 = 11/10 13:21 뒤 실제 PC 에서 갱신을 하지 않음 · PLAN §10-0 과 같음). 이 대조는 **기존 PC 경로(② 시장 전체 갱신 · 대기 없음)**의 실제 반영 근거다. ③ 전일 자료 보충은 이번 PC 에 없는 새 코드라 격리 직접 실행 · 화면 시험(§17-6)으로 따로 확인했고, 새 버튼(② 대기 → ③)의 실제 PC 동작은 반영 후 확인한다(판정 §4-2). 참고: 이 직후 자료를 새 화면 규칙으로 읽으면 아침 기준 = 준비됨(코스피 11/12 · KODEX 200 11/12 마감 뒤 행 · 수급 11/12) · 당일 판정 = 11/13 마감 뒤 행이라 표는 아침(11/12) · 당일(11/13) 두 행(D2 공통 아님).

### 27-6. 자체 검수 · 바뀐 파일

- 백엔드: `black --check` · `flake8`(저장소 `setup.cfg`) · `py_compile` 통과 · 관련 3개 파일 74건 통과. 백엔드 전체 회귀는 다시 돌리지 않았다 — 바뀐 백엔드는 이번 POC 새 파일 `app/pc_morning_basis.py`(상수 읽어 싣기만) · 사용처 = `app/api.py` 라우터 · 그 시험뿐.
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,457건** 통과(§26 때 1,420건 → 새 시험 · 바뀐 계약 시험 반영).
- 바뀐 파일(이번 마감 보완): 판정서 저장 `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_DECISION_V3_2026-11-13.md` · `app/pc_morning_basis.py` · `tests/test_poc6_29_morning_basis.py` · `frontend/lib/api/morningBasis.ts` · `frontend/lib/morningText.ts` · `frontend/lib/todayFreshness.ts` · `frontend/lib/todayMarketCopyText.ts` · `frontend/app/components/today/RegimeBasisTable.tsx` · `today/MarketFlowBlock.tsx` · `today/KospiHeadline.tsx` · `today/SourceHint.tsx` · `today/todayHelpers.ts`(`maDistanceText` 삭제) · `TodayInvestmentCheckView.tsx` · `globals.css` · 시험 `lib/morningText.test.ts` · `lib/morningTestFixtures.ts` · `lib/todayFreshness.test.ts` · `lib/todayMarketCopyText.test.ts` · `today/TodayMarketFlow.test.tsx` · `today/TodayFolds.test.tsx` · `today/StoredVolumeAndPriceBasis.test.tsx` · `TodayInvestmentCheckView.test.tsx` · `KospiStatusSurfaces.test.tsx` · 문서 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`. 새 의존성 · 스키마 · 배포 경로 변경 없음.

## 28. 검증자 V3 마감 변경분 검증(Codex · 2026-11-13)

V3 판정서와 §27 개발 결과서를 작업 사본의 stage와 대조했다. 기준 커밋은 `2c40ea69`다. §26 검증 이후 제품 12개, 시험·시험 자료 10개, 문서 4개가 달라졌다.

### 28-1. A. 기능과 산출물

- **A-1 지시 일치 위반.** D1 점수·서버 산식, D2 공통 한 행과 분리 두 행, D3 이동평균 가격과 거리, D4 중복 판정 제거를 관련 시험과 코드로 확인했다. V3 §3의 화면·복사 정합성은 아래 F11에서 어긋났다.
- **A-2 보고 정확성.** §27의 변경 목록과 stage가 일치한다. 총 179개(신규 67, 수정 82, 내용이 같은 이동 30)이며 미 stage·미추적은 0개다. 개발자 전체 프런트 실측은 §27-6의 1,457건이다.
- **A-3 산출물 정합성 위반.** 복사 확인을 기다리는 사이 선택 결과가 바뀌면 복사문은 화면과 다른 판정·기준일·저장 상태를 내보낸다. Q-S5(a)의 전후 대조는 별도로 확인했다.
- **A-4 금지사항 위반 없음.** 신규 의존성, 외부 API 추가, 파일 삭제, 스키마 변경은 확인되지 않았다. 기존 판정 모듈의 내용도 기준 커밋과 같다.

#### F11(P2) — AI 복사 확인 창이 열린 동안 화면 판정이 바뀌면 이전 판정을 복사

`frontend/app/components/TodayInvestmentCheckView.tsx:491~525`에서 복사 버튼을 처음 누를 때 선택 결과로 문장을 만든다. 확인 창에서 [이 자료로 계속]을 선택하면 그때 만든 문장이 클립보드로 전달된다. 아침 기준 조회의 완료로 화면의 당일 판정이 바뀌어도 해당 확인 창은 열린 채 남는다.

격리 화면 시험에서 시장 판정 응답만 먼저 받아 **11/6 하락장 21거래일째**를 표시했다. 외국인 수급이 늦어 복사 확인 창이 열렸고, 창에는 시장 판정이 확인 대상에 포함되지 않았다. 창이 열린 뒤 아침 기준 응답을 받아 상자와 표가 **11/12 상승장 1거래일째 · 15:56 마감 뒤 저장**으로 바뀌었다. [이 자료로 계속]을 누르자 복사문의 [시장 판정]에는 **11/6 하락장 21거래일째 · 저장 시점 확인 필요**가 남았다. 같은 응답을 복사 버튼보다 먼저 받은 대조군은 화면과 복사문이 일치했다.

V3 §3은 시장 판정 한 줄과 그 기준일·저장 상태를 화면 당일 상자·표와 같은 선택 결과로 복사하도록 한다. 이 재현의 차이는 다른 자료에 대한 확인을 기다리던 중에 발생한다.

#### Q-S5(a) 실제 PC 전후 자료

저장소 밖의 `qs5a_before.json`, `qs5a_after.json`과 작성 스크립트를 읽어 §27-5와 대조했다. 이 스크립트는 SQLite를 읽기 전용으로 열고 화면 자료를 GET으로 읽는다.

- 코스피 공식 종가는 11/9에서 11/12의 5,342.73으로 바뀌었고, 화면 상태는 `stale`에서 `ok`로 바뀌었다.
- KODEX 200은 직전에 11/12 행이 없었고 직후에는 11/12의 84,240원 행이 확인됐다. 화면 당일 판정 기준일은 11/10에서 11/13으로 바뀌었다.
- 투자자 수급의 저장일과 화면 표시일은 11/9에서 11/12로 바뀌었다. 직후 기록에 든 최근 다섯 행의 실패 수는 모두 0이다.

따라서 Q-S5(a)의 기존 PC 갱신 경로에서 세 자료가 기대일 11/12를 충족한 근거를 확인했다. 새 버튼의 ② 대기 → ③ 보충 경로는 V3 §4-2에 따라 PC 반영 후 확인할 항목이다.

검증자 실측은 격리 사본의 프런트 관련 16파일 351건, 백엔드 74건, 타입 검사, 변경 프런트 ESLint, 변경 Python black·flake8·컴파일 통과다. 이전 독립 화면 시험 4건도 통과했다. 이 중 기존 두 행을 전제로 했던 대조군 2건은 격리 사본에서 V3 공통 행의 표시 기대값을 반영했다. 이번 독립 복사 시험은 대조군 1건 통과, F11 1건 재현이다. 검증 사본과 로그는 `/private/tmp/poc629-v3-verify-1bVxGyNV/`에 보관했다.

### 28-2. B. 구현 구조

- **B-1 암묵 기본값 위반 없음.** 점수·거리 미확인은 표시로 구분하며 산식 경계는 서버 상수를 읽는다.
- **B-2 단일 책임 위반 없음.** 점수 설명, 판정 출처, 공통 행 판단은 표시 헬퍼에 있다.
- **B-3 파일 크기.** 화면 진입 모듈 762줄, 판정 표 202줄, 아침 기준 모듈 491줄로 각 임계 아래다.
- **B-4 운영 경계 위반 없음.** 연구·백테스트·OCI 배치 경로 변경이 없다.
- **B-5 배포 경로 영향 없음.** 변경 파일과 판정서를 Git index에서 확인했다. 패키지 설정과 배포 스크립트 변경이 없다.
- **B-6 정합성.** 최초 복사 요청은 화면과 같은 출처를 고른다. F11은 그 결과를 보관한 확인 창과 이후 화면 사이의 불일치다. 결과서 끝 빈 줄은 정리했고 소스·시험 다섯 파일의 끝 빈 줄은 `git diff --cached --check` 지적으로 남아 있다.

### 28-3. 기반 문서

이번 변경 파일은 KS-10 임계 안이다. V3 원문은 설계 문서로 stage됐다. 마감 판정과 PC 반영 후 새 버튼 확인은 후속 단계다.

### 28-4. 코드 안전성

**MEDIUM.** AI 검토에 사용하는 복사문에 화면과 다른 시장 국면과 날짜가 들어갈 수 있다.

### 28-5. 범위

**NONE.** D1~D4와 복사 정합성, 관련 표시·시험·문서는 V3 마감 범위에 해당한다.

### 28-6. 종합 판정

**REJECTED.** D1~D4와 Q-S5(a) 근거는 확인했다. F11로 V3 §3의 마감 조건을 충족하지 못했다.

### 28-7. 검증자 수정 내역

결과서 한 파일의 `STATUS`와 `VERIFIER`를 갱신하고 §28을 추가했다. §17-7의 현재 줄 수를 화면 진입 모듈 760→762, 판정 표 149→202, 아침 기준 모듈 475→491로 정정했다. 끝의 여분 빈 줄을 정리하고 이 결과서만 stage했다.

## 29. 검증자 V3 마감 변경분 F11 정정(개발자 · 2026-11-13)

### 29-1. 원인 · 정정

- 원인: [AI용 시장 정보 복사]는 버튼을 누를 때 복사 글을 만들어 두고, 늦은 자료가 있으면 확인 창을 연 뒤 [이 자료로 계속]에서 그 글을 복사한다. 창이 열린 동안 아침 기준 응답이 도착해 화면 당일 판정(상자 · 표)이 바뀌어도 창이 남아, 받아 둔 이전 판정 · 기준일 · 저장 상태가 복사됐다(설계자 V3 §3 위반). 화면에는 같은 종류의 보호가 시장 갱신 완료 때만 있었다(`onMarketCompleted` — 열린 복사 창을 닫고 '시장 자료를 새로 읽어 복사를 멈췄습니다 — 다시 눌러 주세요.').
- 정정(`TodayInvestmentCheckView.tsx`): 확인 창을 열 때 복사 글에 쓰는 원천(시장 판정 응답 · 시장 흐름 응답 · 아침 기준 응답의 값과 상태(불러오는 중 · 성공 · 이전 응답))을 적어 두고, 창이 열린 동안 그중 하나라도 바뀌면 받아 둔 글을 복사하지 않고 창을 닫은 뒤 '복사에 쓰는 시장 자료가 바뀌어 복사를 멈췄습니다 — 다시 눌러 주세요.'를 보인다(기존 보호와 같은 방식 · 다시 누르면 지금 화면 값으로 새로 만들고 늦은 자료 확인도 다시 한다). 복사 글을 [이 자료로 계속] 때 다시 만드는 방식은 쓰지 않았다 — 창에 보인 확인 대상(늦은 자료 목록)과 실제 복사 글이 어긋날 수 있어서.

### 29-2. 시험 · 변이 · 자체 검수

- `today/TodayMarketFlow.test.tsx` 새 1건(검증자 재현 경로): 시장 판정 응답만 먼저(하락장 21거래일째) · 외국인 수급이 늦어 복사 확인 창 열림 → 창이 열린 사이 아침 기준 도착(같은 읽기 당일 판정 = 상승장 1거래일째 · 11/12 15:56 마감 뒤) → 상자가 바뀌고 창이 닫히며 안내 문장 · 복사 0 → 다시 누르고 [이 자료로 계속] → 복사의 시장 판정 줄 = '[시장 판정] KODEX 200 상승장 · 1거래일째 · 2026-11-12 · KODEX 200 11/12 가격(15:56 마감 뒤 저장)'(화면과 같음). 기존 복사 시험(바로 복사 · 늦은 자료 고르기 · 취소 · 계속)은 그대로 통과.
- 변이: 원천이 바뀌어도 창을 닫지 않음 → 위 시험 실패(1건) · 복원 일치.
- 파일 끝 빈 줄(검증자 §28-2 `git diff --cached --check` 지적 5파일)을 정리 — stage 전체 공백 검사 지적 0.
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 **1,458건** 통과(새 1건) · 이번 정정은 화면만(서버 · 응답 그대로 · 백엔드 시험 대상 없음).
- 바뀐 파일: `frontend/app/components/TodayInvestmentCheckView.tsx` · 시험 `frontend/app/components/today/TodayMarketFlow.test.tsx` · 끝 빈 줄 `today/todayHelpers.ts` · `lib/morningText.test.ts` · `lib/todayFreshness.test.ts` · `lib/todayMarketCopyText.test.ts` · 문서 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/STATE_LATEST.md`.

## 30. 검증자 V3 마감 F11 정정 재검증(Codex · 2026-11-13)

V3 §3과 §29 정정 내용을 작업 사본의 stage와 대조했다. 기준 커밋은 `2c40ea69`다. §28 검증 이후 동작 변경은 프런트 화면 파일 1개, 시험 추가는 1개 파일이다. 나머지는 끝 빈 줄 정리 4개 파일과 문서 3개다.

### 30-1. A. 기능과 산출물

- **A-1 지시 일치 통과.** 복사 확인 창을 연 뒤 아침 기준 응답이 도착하는 §28의 F11 재현을 다시 실행했다. 당일 판정은 11/6 하락장에서 11/12 상승장으로 바뀌었다. 확인 창이 닫히고 다시 누르라는 안내가 표시됐으며 클립보드 호출은 0회였다. 새 판정을 먼저 받은 대조군에서는 화면과 복사문의 날짜·판정·저장 시점이 일치했다.
- **A-2 보고 정확성 통과.** §29의 파일 목록과 Git 스냅샷이 일치한다. 총 179개 stage(신규 67, 수정 82, 내용이 같은 이동 30), 미 stage·미추적 0개다. `git diff --cached --check`는 지적 0건이다.
- **A-3 산출물 정합성 통과.** 다시 누르면 늦은 자료 확인을 새로 거쳐 화면의 상승장·기준일·마감 뒤 저장이 복사된다. 시장 판정이나 시장 흐름만 갱신한 독립 시험에서도 창을 닫았으며, 다시 눌러 각각 새 지속일과 자료 상태를 복사했다.
- **A-4 금지사항 위반 없음.** 새 의존성, 외부 API, 파일 삭제, DB 스키마 변경은 확인되지 않았다.

격리 사본에서 프런트 관련 16파일 352건, 독립 화면 시험 4건, 타입 검사와 변경 파일 ESLint가 통과했다. 전체 프런트 1,458건은 §29의 개발자 실측이다. 백엔드와 해당 시험이 §28 기준과 일치해 관련 74건 근거를 재사용했다. D1~D4 및 실제 PC 갱신 전후 대조는 §28 근거를 사용했다. 독립 시험과 로그는 `/private/tmp/poc629-f11-verify-UNOSACSO/`에 보관했다.

### 30-2. B. 구현 구조

- **B-1 암묵 기본값 위반 없음.** 확인 창을 열 때 읽은 응답과 상태를 기록해 변경 여부를 판단한다.
- **B-2 단일 책임 위반 없음.** 복사 확인 창과 문구를 관리하는 기존 화면 흐름 안에서 정정했다.
- **B-3 파일 크기.** 화면 진입 파일 787줄, 변경 화면 시험 654줄로 각 임계 안이다.
- **B-4 운영 경계 위반 없음.** 연구·백테스트·OCI 배치 경로에 변경이 없다.
- **B-5 배포 경로 영향 없음.** 변경 파일은 Git index에서 확인했다. 배포 스크립트와 패키지 설정 변경이 없다.
- **B-6 구조적 퇴행 없음.** 기존 확인·취소·계속과 갱신 완료 보호 시험이 통과했다.

### 30-3. 기반 문서

변경 범위에 KS-10 임계 초과가 없다. Q-S5(a)의 기존 PC 갱신 전후 근거는 §27-5와 §28에 있다. V3 §4-2의 새 버튼 경로는 실제 PC 반영 후 확인할 항목이다.

### 30-4. 코드 안전성

**NONE.** 검증 범위에서 새 결함을 확인하지 않았다.

### 30-5. 범위

**NONE.** F11 보호와 관련 시험, 끝 빈 줄 정리 및 문서 갱신에 해당한다.

### 30-6. 종합 판정

**VERIFIED.** F11 재현과 인접 경로가 통과했다. 다음은 설계자 마감 판정이다.

### 30-7. 검증자 수정 내역

결과서 한 파일의 `STATUS`와 `VERIFIER`를 갱신하고 §30을 추가했다. §17-7의 화면 파일 787줄 표기에 겹쳐 있던 절 참조를 정리했다. 검증자가 수정하고 stage한 파일은 이 결과서 한 개다.

## 31. 마감 뒤 형수님 화면 조절(개발자 · 2026-11-13)

- 형수님 질문: 카드 맨 위 '아침 요약 = 직전 국내 거래일 마감 기준 · 오늘 시장 변화 = 오늘 네이버 시세 · 근거는 아래 […]' 뜻을 잘 모르겠다. 설명(아침 요약 = 어제 장 마감까지 자료 · 오늘 시장 변화 = 오늘 시세와 당일 판정 · 근거 = 아래 접기) 뒤 세 안(줄 없애기 · 쉬운 세 줄 · 한 문장)을 미리보기와 함께 보임 → **형수님 선택 = 안내 줄 없애기**(각 구역 제목 옆에 기준이 이미 있음 — '아침 요약 · M/D 마감 기준 · 직전 국내 거래일 · 그날까지 저장된 자료' · '오늘 시장 변화 M/D 마감 · 네이버 시세 · 마지막 조회 …' · 근거는 접기 제목 [시장 근거와 다른 변화 보기]). 지금 문장은 11/13 배치 뒤 '오늘 시장 변화 = 오늘 네이버 시세'가 그 안의 코스피 공식 종가(KRX · 어제 마감)와도 맞지 않았다.
- 바꾼 것: `today/MarketFlowBlock.tsx` 카드 머리의 안내 줄 삭제(화면 문구만 · 데이터 · 계산 · 판정 그대로) · 시험 `today/TodaySummary.test.tsx`(안내 줄이 없고 구역 제목 옆 기준은 그대로) · 변이(줄 되살림) = 잡힘.
- 화면 표시만 바꾼 조절이라 형수님 화면 확인으로 마감한다(바뀐 시험 1곳은 이 조절의 계약 — 검증자 확인 대상이면 그 부분만).
- 프런트: `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 1,458건 통과.

### 31-2. 아침 요약 정리(설계자 정리 · 형수님 선택 · 2026-11-13)

- 형수님 의견: 시장 흐름(판단)이 나오기 전에 정보가 너무 많다(제목 · 설명 줄 · '전일 자료 미완료 …' · 사유 두 줄). 개발자 설명: 격리 사본은 KRX 키가 없어 미완료라 사유가 붙었고, 실제 PC 는 11/13 갱신으로 준비됨(두 줄)이다. 정리 방법을 묻자 형수님이 설계자 답을 전달: '기준일 아래 세 줄은 자료 상태 안내 — 원인 · 확인 시각까지 앞에 붙어 시장 판단이 뒤로 밀렸다. **시장 판단과 핵심 근거를 먼저**, 빠진 자료는 요약 끝에 한 줄 + [자료 상태 보기](KRX 키 없음 · OCI 수집본 반영 · 확인 시각은 그 안). 요약 본문에는 기준일을 충족한 자료, 60거래일 수익률 · 환율 · 유가의 과거 사건은 근거 표 · 날짜별 상세.' 예시가 미완료 한 경우뿐이라 두 가지를 형수님께 물음 → **최근 변화 줄 = 그냥 보이기**(POC6-27 결정 ③ 유지 · 과거 환율 · 유가 사건도 이 줄에는 그대로) · **준비됨일 때 끝 줄 = 짧게 한 줄**.
- 바꾼 것(화면 · 새 계산 없음 · 응답 칸 그대로):
  - `today/MorningSummary.tsx`: 제목 한 줄('직전 국내 거래일 · 그날까지 저장된 자료' 설명 뺌) → 판단 문단(`tc-morning-regime` · 굵은 판단 + KODEX 200 핵심 근거) → 기준을 채운 자료 문장(코스피 공식 종가 · 외국인 5거래일 · VIX · 원/달러 · WTI) → 최근 변화(그대로) → 끝 한 줄(`tc-morning-ready`).
  - `lib/morningText.ts :: morningVerdict`(예전 `morningRegime` 을 바꿈) — '국내 시장은 {국면} N거래일째입니다.' + 'KODEX 200은 최근 20거래일간 3.06% 하락했고, 20일선과 60일선 아래에 있습니다.'(20거래일 수익률 · `ma20_position` · `ma60_position` · 엇갈리면 '20일선 위, 60일선 아래' · 없는 칸은 빼고) · 미확인 = '아침 판정 미확인 — 사유'. 60거래일 수익률은 요약에 쓰지 않음(판정 표).
  - `lib/morningText.ts :: morningStatus` — 빠진 필수 자료 = '코스피 공식 종가 · 수급은 11/11까지 있습니다.' · 자료 없음 = '수급 자료가 없습니다.' · KODEX 200 미확인 = 'KODEX 200 판정 근거는 확인되지 않았습니다.' + [자료 상태 보기](처음엔 닫힘 · 서버 사유 그대로) / 준비됨 = '필수 자료 준비됨(코스피 공식 종가 · KODEX 200 · 수급)'(짧게) / 불러오는 중 · 실패 = 그 문장. 판단 묶음은 기존 `readiness` 와 같음(갱신 끝 줄 · 근거 접기 ③ 은 `readiness` 그대로).
  - `lib/marketNowText.ts :: vixSentence` — 'VIX(미국 변동성)는 17.49로 전일보다 10.12% 낮아졌습니다.'(설계자 예시 말투 · '(미국 변동성)'은 쉬운 말로 남김 · 날짜 '11/11 미국'은 그대로) · `fxwtiSentence(flow, withEvents)` — 아침 요약은 값만(과거 사건은 최근 변화 줄로) · 원/달러가 기준일을 채웠을 때만 문장.
  - `globals.css` — 판단 문단 · 자료 문장 같은 크기(15px) · 끝 줄 색(준비됨 초록 · 미완료 주황) · [자료 상태 보기] 글자 단추.
- 격리 화면(오류 0 · 1400px 넘침 0 · 400px 565px 그대로): '아침 요약 · 11/12 마감 기준' → '**국내 시장은 하락장 25거래일째입니다.** KODEX 200은 최근 20거래일간 3.06% 하락했고, 20일선과 60일선 아래에 있습니다.' → 'VIX(미국 변동성)는 17.49로 전일보다 10.12% 낮아졌습니다. 11/11 미국' → 최근 변화(11/10 원/달러 · 11/10 WTI 사건) → '코스피 공식 종가 · 수급은 11/11까지 있습니다. [자료 상태 보기]'(원/달러는 1거래일 늦어 요약 문장 없음).
- 시험: `lib/morningText.test.ts`(`morningVerdict` 6가지 · 60거래일 없음 · `morningStatus` 5가지) · `lib/marketNowText.test.ts`(VIX 말투) · `today/TodayQuickRefresh.test.tsx`(준비됨 끝 줄 · 판단 문단 · 순서 = 판단 → 자료 문장 → 끝 줄 · 설명 줄 없음 · 미완료 끝 줄 + [자료 상태 보기] 닫힘 · 사유 그대로 · KODEX 200 미확인) · `today/TodayMarketFlow.test.tsx`(요약에 과거 환율 · 유가 사건 없음 · 최근 변화 줄 그대로 · 원/달러 기준일 충족 · 늦음 2가지) · 변이 6종(원/달러 기준일 조건 빼기 · 과거 사건 다시 넣기 · 핵심 근거 문장 빼기 · 원인을 늘 펼침 · 설명 줄 되살리기 · KODEX 20거래일 문구 빼기) 모두 잡힘. 프런트 `npx tsc --noEmit` 0 · `npm run lint` 문제 0 · `npx vitest run` 84개 파일 1,470건 통과(그 뒤 글자 크기 CSS 만 바꿈).
- 화면 표시 정리(설계자 정리 + 형수님 선택)라 형수님 화면 확인으로 마감한다 · 바뀐 시험은 검증자 확인 대상이면 그 부분만.

## 32. 설계자 RESULT 마감 판정 PASS(설계자 · 2026-11-13 · 개발자 기록)

판정서 `docs/ai_design/POC6/POC6_29_ETF_MARKET_DISCOVERY_REFOCUS_RESULT_CLOSEOUT_DECISION_2026-11-13.md`(형수님 전달 원문 그대로 저장). 판정서는 '§30 뒤에 기록'을 지시했고, §31(마감 뒤 화면 조절)이 먼저 있어 그 다음 번호로 둔다.

### 32-1. 판정

- **PASS · main 반영과 운영 확인 대기.** 근거 = 결과서 §27 ~ §30. D1 ~ D4 표시 · AI용 복사(F11 정정 · §30 확인) · Q-S5 (a) 기존 PC 갱신 전후 대조(§27-5 · §28 — 코스피 공식 종가 · 투자자 수급 11/9 → 11/12 · KODEX 200 11/12 마감 뒤 가격 행 · 세 자료 모두 그 실행의 전일 기준 11/12 충족)를 수용. §30 VERIFIED 를 마감 보완 검증 근거로 사용.
- 상태 문서 표기 = `설계자 RESULT PASS · 실제 PC 반영 대기`(`STATE_LATEST` · `PROGRAM_TRUTH` 같은 날 반영).

### 32-2. 판정서 근거 밖 — §31 · §31-2

- 판정서 근거는 §27 ~ §30 이다. §31(카드 머리 안내 줄 뺌 · 형수님 선택)과 §31-2(아침 요약 정리 · 설계자 정리 문구 — 이 판정서와 함께 형수님이 다시 전달 · 형수님 선택 2건)는 그 뒤의 화면 표시 조절이다. 서버 · 데이터 · 계산 · 판정 변경 없음.
- 마감 기준 = 형수님 화면 확인. 격리 화면(3001)은 세션 교체로 멈춰 있어(아래 32-3) 확인은 main 반영 뒤 운영 화면(3000)에서 한다. 바뀐 시험(§31 · §31-2 에 적은 시험 파일)은 검증자 확인 대상이면 그 부분만.
- 설계자 정리 문구와 다른 곳 1개: VIX 문장 = 'VIX(미국 변동성)는 17.49로 전일보다 10.12% 낮아졌습니다.' + 날짜 '11/11 미국'(설계자 예시는 'VIX는 17.49로 …'). '(미국 변동성)'은 화면 글자를 쉬운 한국어로 쓰는 규칙에 따라 남겼다(§31-2).

### 32-3. 남은 순서(판정서 §2 · 형수님 승인 순서)

1. **기록과 반영** — 이 절과 `STATE_LATEST` · `PROGRAM_TRUTH` 기록(완료 · stage). main 반영 · 커밋은 형수님 승인 뒤, push 는 따로 승인.
2. **운영 화면 확인(3000 · 8000)** — main 반영 뒤 주요 화면과 [최신 자료 갱신]에서 ② 시장 전체 갱신이 대기할 때 ③ 전일 자료 보충으로 이어지는 실제 동작 · 화면 결과. 실행 시점의 직전 국내 거래일, 자료별 저장 · 표시일을 남긴다(보충 대상이 이미 준비돼 있으면 그 상태 · 기준일 / 보충을 실행하면 항목별 저장 · 표시 또는 실패 사유). 근거 구분: §27-5 = 기존 PC 전체 갱신 · §17-6 = 격리 ③ 직접 실행 · 화면 시험. 2026-11-13 이 기록 시점 실측: 3000 · 8000 · 3001 · 8001 모두 듣는 프로세스 없음(`lsof -iTCP:<포트> -sTCP:LISTEN` 결과 없음 · `curl http://127.0.0.1:8000/health` 연결 실패) — 운영 확인 때 3000 · 8000 을 띄워야 한다.
3. **격리 사본 정리** — main 에 검증분과 기록이 모두 반영됐고 격리 사본에만 남은 변경이 없음을 대조한다. 3001 · 8001 은 위 실측처럼 이미 멈춤. 작업 사본 `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_29` · 로컬 브랜치 `poc6-29-abc-refocus` 삭제는 형수님 승인 뒤. 종료 · 제거를 확인해 기록한다.
4. **POC6-29 종료** — 운영 확인과 격리 정리 기록 뒤 `CLOSED`. 운영 · 개발 기준은 main 으로 돌아오고 다음 작업은 POC6-30 으로 시작한다.
