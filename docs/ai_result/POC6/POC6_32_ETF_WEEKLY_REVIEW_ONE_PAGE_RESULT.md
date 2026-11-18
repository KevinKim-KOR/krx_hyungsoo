# POC6-32 개발 결과서 — 「주간 ETF 점검」(V2)

- 단계 ID: **POC6-32 V2**(STEP_NAME = 주간 ETF 점검 · V1 「오늘의 투자 점검」 ETF 주간 검토 한 장을 재설계)
- 설계 · 판정: 설계 `docs/ai_design/POC6/POC6_32_ETF_WEEKLY_REVIEW_ONE_PAGE_DESIGN_2026-11-17.md` · PLAN 판정 V1 `…_PLAN_DECISION_2026-11-17.md` · 재설계 판정 V2 `…_REDESIGN_DECISION_V2_2026-11-17.md` · **PLAN 판정 V2 `docs/ai_design/POC6/POC6_32_ETF_WEEKLY_REVIEW_PLAN_DECISION_V2_2026-11-17.md`(CONDITIONAL_PASS)**
- 개발 PLAN(V2 확정): `docs/ai_plan/POC6/POC6_32_ETF_WEEKLY_REVIEW_ONE_PAGE_PLAN_V1.md`(§9 개발자 적용 해석 I-1 ~ I-32 = 설계자 확인 요청) · 목업 `…_MOCKUP.html`(V2 확정)
- **코드 위치: 격리 작업 사본** `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_32` · 브랜치 `poc6-32-weekly-review` · 기준 커밋 `2a3ea05f`(main) · `git status` 실측 = 신규 45 · 수정 63 · 삭제 2 · stage 안 된 변경 0 · 추적 안 됨 0 · 커밋 없음. 운영 main · 운영 서버(8000 · 3000)는 그대로.
- 현재 범위: **구현 · 시험 · 변이 · 독립 검토(4관점 · 반박 검증 · 확인 12건 정정) · 형수님 격리 화면 확인(AC4 · 2026-11-18) 완료 → 검증자 r1 REJECTED(F1~F3 · §12) → r1 정정 · AC3 실화면 근거(§13) → 검증자 r2 VERIFIED(F1~F3 · AC3 확인 · §14) → 설계자 RESULT 판정 V2 조건부 PASS → 조건 2건 확인(서버 전체 회귀 · [비교 상세] 선택 인계 · §15) = **설계자 RESULT PASS(2026-11-18)**** → 커밋 · main 합치기(형수님 승인).
- POC6-31 과의 구분: POC6-31 AC4 재확인은 그 Step 의 실제 검토 기록으로 별도 판정한다(판정 V2 끝 문장).

---

## 0. 요약

- **화면:** 메뉴 「오늘 확인」에 형제 메뉴 「주간 ETF 점검」을 두고, 「보유와 후보 비교」 · 「ETF 구성종목」은 메뉴에서 빼 상세 화면이 됐다. 상세를 열면 보낸 화면을 숨겨 두고, [← 보낸 화면으로]로 돌아가면 선택 · 조건 · 열린 행이 그대로다. 「오늘의 투자 점검」은 주간 자료를 읽지 않고 [주간 ETF 점검 열기 →] 한 줄만 둔다.
- **주간 ③ 「선택한 후보 검토」:** 후보를 고르면 보유 한 종목을 고르지 않고 후보 자체 근거를 보인다.
  - 어떤 상품인가: KRX 공식 기준정보(기초지수 · 투자 대상 · 상품 구조 · 파일 날짜)와 구성(주식 상위 3개 · 합 · 구성 기준일 · 상태 넷)
  - 실제로 올랐나: 1 · 3개월 가격 관측 · 실제 기간 · 방향과 '같은 기간 국내시장(KODEX 200) 대비' 문구. 가격 상태가 맞을 때만 붙이고, 둘 다 장중이면 '잠정 비교'
  - 더 확인할 것: 기준일이 다른 자료 · 겹침 확인 범위 · [판단 근거 보기]
  - 내 보유에 무엇이 겹치나: 내 보유 전체 기준
- **[비교 상세]:** 두 칸 모두 빈 선택에서 시작한다. 상품 확인 표와 지수 상태(같은 공식 기초지수 · 다른 지수 · 다른 지수(같은 계열) · 기준 미확인)를 먼저 보이고, 같은 공식 기초지수일 때만 차이 요약을 쓴다.
- **복사 · 기록:**
  - 일일 · 주간 복사가 같은 서버 공통 시장 근거(`GET /market/evidence`)를 쓰고 '최신 공개 자료 확인' 문단으로 시작한다. 60거래일 수급은 다섯 분류다.
  - 주간 답 형식은 최신 확인 · 확인 항목(확인 시각) · 후보별 상태 · 인용 근거 · 이유 · 다음 확인이다.
  - 새 주간 기록의 판단은 '미기록'에서 시작한다.
  - '당시 검토'는 저장 값만으로 복원하고, AI 칸은 저장 원문 해석으로 보인다.
- **검사(r1 정정 뒤):** 서버 black · flake8 33파일 · 바뀐 모듈을 쓰는 시험 31파일 1,057 통과 · 주간 시험 하나씩 따로 실행 158/158 · 화면 tsc 0 · eslint 70파일 · vitest 98파일 1,885 통과 · 변이 총 202건 중 200건 잡힘(초기 1건 같은 동작 · 1건 보조 장치 · r1 정정 25/25 · §9 · §13).

## 1. 처리한 요구사항(PLAN 판정 V2)

| 판정 | 상태 | 반영 |
|---|---|---|
| 목표(후보 하나 → 어떤 상품 · 실제로 올랐나 · 내 보유 겹침을 한 화면에서) | DONE | 주간 ③ 「선택한 후보 검토」 R1 ~ R5 |
| §1 Q11 (d) | DONE | 보유 한 종목 고르는 단계 없음 · 기본 짝 제거 · [비교 상세] 두 칸 빈 선택 · 상품 확인 · 지수 상태 · 같은 공식 지수일 때만 차이 요약 · 구조 다름 표시 |
| §2 Q12 (c) | DONE | 후보 단독 근거 요약이 주간 화면 기본 · '가격 관측' 이름(판정이라 부르지 않음) · 행마다 자료 부족 표시 |
| §3 구성종목 | DONE | 한 ETF 모드(상태 넷 + 읽기 실패 · 저장 행 수 · 구성 기준일 · Top 1 · 3 · 5 · 10) · 목록 모드 머리 · 보유 겹침 카드 '1개월 상위 10개 기준 · 실제 기간' |
| Q1 (a) | DONE | 형제 메뉴 · 두 상세 key · 보낸 화면 숨겨 두기 · [← 보낸 화면으로] · 출처 `today_weekly_review` |
| Q2 (b) | DONE | NAV 4버튼 → 「데이터 상태」('전체 ETF NAV·괴리율 보기 →') · 보유 구성 작업 = [최신 자료 갱신] 그대로 |
| Q3 (a) | DONE | 실제 기간 · 값 · '기간 다름' · 대비는 시작 · 끝 · 가격 상태가 맞을 때만 |
| Q4 (c) 보완 | DONE | 판단 값 'unrecorded'(미기록 · 코드 허용 목록만 · 표 변경 없음) · 주간 기록 시작값 · 세 층 가드 · 표시 규칙(I-12) |
| Q5 (a) | DONE | 확인 항목 줄 이름 붙은 칸 · '확인 시각 미기재' · 한 AI 답으로 저장 |
| Q6 (a) | DONE | '당시 검토' = 저장 값만 · 오늘 시세 · 수집 시각은 기록에 남은 값만 |
| Q7 (a) | DONE | 오늘(KST) 저장 시세 · 마지막 시도 성공일 때만 '오늘 시세 참고' · 없으면 [자료 상태] '오늘 시세 미확보' |
| Q8 (a) | DONE | 일일 복사 저장 없음 · 후보 판단에 쓴 시장 근거 · AI 확인은 주간 기록에 |
| Q9 (a) 보완 | DONE | 목록 경로 · 한 ETF 경로 · 상세 머리 안내 · '1개월 상위 10개 기준' · 주간 겹침 = 고른 ETF 근거 |
| Q10 (a) | DONE | 60거래일 외국인 · 개인 · 기관계 · 기타법인 · 내국인대우외국인 각각 · 실제 날짜 · 집계 구분 · 중복 합산 없음 |
| AC1 · AC2 · AC3 | DONE(시험 · 격리 화면 자동 확인 · AC3 실화면 = 저장 → 갱신 → 다시 열기 §13) | §8 · §9 · §13 |
| AC4 형수님 확인 | DONE(형수님 격리 화면 · 2026-11-18) | '정돈이 잘 된 것 같다 · 메뉴에 없지만 기능은 그대로' · 후보 476070 을 고른 뒤 복사 → 넘기기 → 저장(11:26 · 판단 '쓸 만함' 직접 고름) → 다시 열어 확인(§7) |

## 2. 변경된 파일 목록

### 격리 작업 사본(기준 main `2a3ea05f` 대비 · stage 상태 · 줄 수 = `wc -l` 실측 · V1 변경 포함 · r1 정정 뒤)

**서버(app/)** — 신규 13 · 수정 12

| 상태 | 파일 | 줄 수 |
|---|---|---|
| 신규 | `app/api_market_evidence.py` | 67 |
| 신규 | `app/api_weekly_review.py` | 285 |
| 신규 | `app/decision_evidence_readonly.py` | 77 |
| 신규 | `app/etf_official_info.py` | 278 |
| 신규 | `app/holdings_overlap_period.py` | 41 |
| 신규 | `app/market_evidence.py` | 588 |
| 신규 | `app/market_evidence_reads.py` | 123 |
| 신규 | `app/market_evidence_text.py` | 559 |
| 신규 | `app/weekly_candidate_reads.py` | 130 |
| 신규 | `app/weekly_candidate_review.py` | 590 |
| 신규 | `app/weekly_review.py` | 470 |
| 신규 | `app/weekly_review_answers.py` | 370 |
| 신규 | `app/weekly_review_text.py` | 366 |
| 수정 | `app/api.py` | 595 |
| 수정 | `app/api_decision_sessions.py` | 275 |
| 수정 | `app/api_holdings_market_evidence.py` | 326 |
| 수정 | `app/api_supply_fx_oil.py` | 48 |
| 수정 | `app/constituents_pair_exposure_io.py` | 88 |
| 수정 | `app/decision_evidence_store.py` | 589 |
| 수정 | `app/decision_preview_common_period.py` | 381 |
| 수정 | `app/etf_constituents_status.py` | 418 |
| 수정 | `app/pc_quick_quotes.py` | 464 |
| 수정 | `app/supply_fx_oil_calc.py` | 335 |
| 수정 | `app/supply_fx_oil_context.py` | 598 |
| 수정 | `app/supply_fx_oil_fields.py` | 94 |

**서버 시험(tests/)** — 신규 7 · 수정 3

| 상태 | 파일 | 줄 수 |
|---|---|---|
| 신규 | `tests/fixtures/poc6_32_evidence_cases.json` | 47 |
| 신규 | `tests/fixtures/poc6_32_weekly_1116.json` | 2273 |
| 신규 | `tests/test_poc6_32_market_evidence.py` | 880 |
| 신규 | `tests/test_poc6_32_official_info.py` | 833 |
| 신규 | `tests/test_poc6_32_r1_reads.py` | 575 |
| 신규 | `tests/test_poc6_32_weekly_answers.py` | 819 |
| 신규 | `tests/test_poc6_32_weekly_review.py` | 1406 |
| 수정 | `tests/test_decision_evidence_store.py` | 683 |
| 수정 | `tests/test_decision_sessions_api.py` | 377 |
| 수정 | `tests/test_poc6_01_supply_fx_oil_context.py` | 740 |

**화면(frontend/)** — 신규 25 · 수정 47

| 상태 | 파일 | 줄 수 |
|---|---|---|
| 신규 | `frontend/app/components/AISessionsWeeklyRecord.test.tsx` | 401 |
| 신규 | `frontend/app/components/ETFExposureView.test.tsx` | 417 |
| 신규 | `frontend/app/components/MainPanelDetailNav.test.tsx` | 236 |
| 신규 | `frontend/app/components/WeeklyEtfCheckView.test.tsx` | 134 |
| 신규 | `frontend/app/components/WeeklyEtfCheckView.tsx` | 33 |
| 신규 | `frontend/app/components/ai_sessions/WeeklyReviewSnapshot.test.tsx` | 530 |
| 신규 | `frontend/app/components/ai_sessions/WeeklyReviewSnapshot.tsx` | 483 |
| 신규 | `frontend/app/components/today/WeeklyCandidateReview.test.tsx` | 291 |
| 신규 | `frontend/app/components/today/WeeklyCandidateReview.tsx` | 258 |
| 신규 | `frontend/app/components/today/WeeklyFlowTable.tsx` | 169 |
| 신규 | `frontend/app/components/today/WeeklyRecord.tsx` | 213 |
| 신규 | `frontend/app/components/today/WeeklyReviewCard.test.tsx` | 576 |
| 신규 | `frontend/app/components/today/WeeklyReviewCard.tsx` | 269 |
| 신규 | `frontend/app/components/workbench/EtfRowDetail.test.tsx` | 81 |
| 신규 | `frontend/app/components/workbench/ProductCheckTable.test.tsx` | 229 |
| 신규 | `frontend/app/components/workbench/ProductCheckTable.tsx` | 252 |
| 신규 | `frontend/lib/api/etfOfficial.ts` | 81 |
| 신규 | `frontend/lib/api/marketCommonEvidence.ts` | 142 |
| 신규 | `frontend/lib/api/weeklyReview.ts` | 294 |
| 신규 | `frontend/lib/detailNav.test.ts` | 105 |
| 신규 | `frontend/lib/detailNav.ts` | 102 |
| 신규 | `frontend/lib/marketCommonEvidenceCases.test.ts` | 42 |
| 신규 | `frontend/lib/weeklyReview.ts` | 210 |
| 신규 | `frontend/lib/weeklyReviewTestFixtures.json` | 13276 |
| 신규 | `frontend/lib/weeklyReviewTestFixtures.ts` | 15 |
| 수정 | `frontend/app/components/AISessionsCreateTab.tsx` | 448 |
| 수정 | `frontend/app/components/AISessionsListTab.tsx` | 451 |
| 수정 | `frontend/app/components/AISessionsView.tsx` | 117 |
| 수정 | `frontend/app/components/ConstituentsTab.tsx` | 524 |
| 수정 | `frontend/app/components/ETFExposureView.tsx` | 617 |
| 수정 | `frontend/app/components/HoldingCandidateCompareView.test.tsx` | 1200 |
| 수정 | `frontend/app/components/HoldingCandidateCompareView.tsx` | 388 |
| 수정 | `frontend/app/components/HoldingsOverlapBridgeCard.tsx` | 245 |
| 수정 | `frontend/app/components/JudgmentWorkbenchView.test.tsx` | 408 |
| 수정 | `frontend/app/components/JudgmentWorkbenchView.tsx` | 87 |
| 수정 | `frontend/app/components/LeftSidebar.test.tsx` | 483 |
| 수정 | `frontend/app/components/LeftSidebar.tsx` | 422 |
| 수정 | `frontend/app/components/MainPanel.tsx` | 191 |
| 수정 | `frontend/app/components/SelectedPreviewAISession.test.tsx` | 774 |
| 수정 | `frontend/app/components/TodayInvestmentCheckView.test.tsx` | 1244 |
| 수정 | `frontend/app/components/TodayInvestmentCheckView.tsx` | 845 |
| 수정 | `frontend/app/components/UnusedFeatureView.test.tsx` | 223 |
| 수정 | `frontend/app/components/UnusedFeatureView.tsx` | 159 |
| 수정 | `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.test.tsx` | 259 |
| 수정 | `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx` | 361 |
| 수정 | `frontend/app/components/marketflow/MarketFlow.test.tsx` | 539 |
| 수정 | `frontend/app/components/marketflow/MarketFlowCard.tsx` | 307 |
| 수정 | `frontend/app/components/today/CheckCards.tsx` | 174 |
| 수정 | `frontend/app/components/today/SummarySection.tsx` | 145 |
| 수정 | `frontend/app/components/today/TodayMarketFlow.test.tsx` | 1020 |
| 수정 | `frontend/app/components/today/TodayQuickRefresh.test.tsx` | 759 |
| 수정 | `frontend/app/components/today/TodaySummary.test.tsx` | 672 |
| 수정 | `frontend/app/components/today/TodayVixRetry.test.tsx` | 365 |
| 수정 | `frontend/app/components/today/maintenanceQueue.ts` | 243 |
| 수정 | `frontend/app/components/workbench/CompareCards.tsx` | 323 |
| 수정 | `frontend/app/components/workbench/EtfRowDetail.tsx` | 161 |
| 수정 | `frontend/app/components/workbench/PairExposureBlock.test.tsx` | 170 |
| 수정 | `frontend/app/components/workbench/PairExposureBlock.tsx` | 265 |
| 수정 | `frontend/app/components/workbench/compareSelection.ts` | 40 |
| 수정 | `frontend/app/globals.css` | 4356 |
| 수정 | `frontend/lib/aiSessionsDraft.ts` | 198 |
| 수정 | `frontend/lib/api/dashboardInvalidation.test.ts` | 144 |
| 수정 | `frontend/lib/api/dashboardKeys.ts` | 69 |
| 수정 | `frontend/lib/api/decisionDraftPreview.ts` | 89 |
| 수정 | `frontend/lib/api/decisionSessions.ts` | 202 |
| 수정 | `frontend/lib/api/etfExposure.ts` | 209 |
| 수정 | `frontend/lib/api/holdings.ts` | 441 |
| 수정 | `frontend/lib/api/marketFlow.ts` | 282 |
| 수정 | `frontend/lib/api/queryCache.ts` | 273 |
| 수정 | `frontend/lib/compareDiff.test.ts` | 353 |
| 수정 | `frontend/lib/compareDiff.ts` | 231 |
| 수정 | `frontend/lib/etfCompareCondition.ts` | 241 |

**문서(docs/)** — 신규 0 · 수정 1

| 상태 | 파일 | 줄 수 |
|---|---|---|
| 수정 | `docs/PROGRAM_TRUTH.md` | 1293 |


**삭제(형수님 승인 2026-11-18)**

| 상태 | 파일 | 줄 수(삭제 전) |
|---|---|---|
| 삭제 | `frontend/lib/todayMarketCopyText.ts` | 164 |
| 삭제 | `frontend/lib/todayMarketCopyText.test.ts` | 203 |

### main 저장소(문서 · 커밋 전 · stage)
- `docs/ai_design/POC6/POC6_32_ETF_WEEKLY_REVIEW_ONE_PAGE_DESIGN_2026-11-17.md` · `…_PLAN_DECISION_2026-11-17.md` · `…_REDESIGN_DECISION_V2_2026-11-17.md` · `…_PLAN_DECISION_V2_2026-11-17.md`: 신규(설계자 문서 원문)
- `docs/ai_plan/POC6/POC6_32_ETF_WEEKLY_REVIEW_ONE_PAGE_PLAN_V1.md`(V2 확정) · `…_MOCKUP.html`(V2 확정): 신규
- `docs/ai_result/POC6/POC6_32_ETF_WEEKLY_REVIEW_ONE_PAGE_RESULT.md`(이 문서): 신규
- `docs/STATE_LATEST.md`: 수정
- 형수님 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 추적 안 됨 그대로(stage 하지 않음)

## 3. 신규 추가된 의존성
- 없음

## 4. 지시문 외 변경
- `frontend/lib/api/queryCache.ts` `invalidateQueryKey`(정확히 같은 키 하나만 지움) 추가. 기존 `invalidateQueries` 는 앞부분으로 지워서 숨겨 둔 보낸 화면의 다른 종목 키까지 지웠다(검토 NAV-1).
- 공통 시장 근거의 '계산하지 않음 · 읽지 못함' 사유를 같은 원인인 VIX 6개월 · [가능한 해석] 줄에도 적용. `vix_card` 를 `app/market_evidence_reads.py` 로 옮김(동작 같음 · `market_evidence.py` 600줄 이하 유지).
- 60거래일 다섯 분류 안전 가드(다시 읽은 합이 시장 흐름 응답과 다르면 '확인 불가') · 국가 · 지자체 문구는 실제 합으로 = PLAN I-27.
- 방향 문구 보완(I-25) · 구성 읽기 실패 상태(I-26) · 새 읽기 경로 2개(I-28) · ② 묶음 글자(I-29) · 복사 기준 대조 범위(I-30) · ① 출처 변경(I-31) · '당시 검토' 가격 상태(I-32) = PLAN §9 에 적음.
- 화면 글자 정리: 「AI 투자 세션」 저장 출처 · 초안 출처 이름을 「주간 ETF 점검」으로, 상세를 못 찾을 때 서버 영어 안내 대신 '기록을 찾을 수 없습니다.'(모든 기록), 「미사용 기능」 '옮긴 곳' 줄을 상세 화면 경로로, 「보유와 후보 비교」 구성종목 안내를 [구성종목 보기] 경로로.
- 주간 ③ 에서 V1 [후보리스트 보기 →] · [고른 후보 지우기]는 남김(지시 범위 밖 기능 삭제를 피함 · 목업에는 없음).
- 시험 파일 새로 나눔: `tests/test_poc6_32_weekly_answers.py`(주간 시험 파일 1,447줄 근접 · KS-10) · 화면 새 시험 파일 V2 10개(§2 표의 화면 시험 신규 11개 중 `today/WeeklyReviewCard.test.tsx` 는 V1 에서 만든 파일).

## 5. 알려진 한계 / 미완성
- **AC4 형수님 격리 화면 확인 완료(2026-11-18)** · §7.
- **같은 공식 기초지수 사례(I-18):** [비교 상세] 후보는 그 조건의 상 · 하위 30 이다. 11/16 실측으로 보유 ETF 26개 중 같은 기초지수 후보가 목록에 있는 보유가 0개다. 그래서 실화면에서는 대부분 '다른 지수' · '기준 미확인'이 나오고, 차이 요약 경로는 고정 자료 시험으로만 확인했다. 같은 상품군 대안을 고를 목록이 필요한지는 설계자 확인 대상이다.
- **'당시 검토' AI 칸(I-14):** 저장 원문을 읽을 때마다 지금 해석기로 나눈다. 해석 규칙이 바뀌면 옛 기록의 나눈 모양도 바뀐다.
- **일일 복사:**
  - 누를 때마다 서버가 아침 기준 · 시장 흐름 · VIX · 빠른 시세 · 60거래일 합을 다시 읽는다(쓰기 없음). 응답 동안 버튼이 '읽는 중'이다.
  - 화면 확인 창 행(화면 계산)과 복사 글 [자료 상태](서버 계산)는 코스피 행 판정 경로가 달라, 드물게 문장이 다를 수 있다.
  - 클립보드는 누른 순간 쓰기를 시작한다(ClipboardItem). 실제 Safari · Chrome 동작은 실화면에서 확인하지 않았다.
- **숨겨 둔 보낸 화면:** 화면 갱신 따라가기 등 effect 가 계속 돈다. 돌아갈 때도 맨 위로 스크롤하므로(I-3), 복원된 열린 행이 아래에 있으면 바로 보이지 않는다.
- **옛 일일 복사 파일:** `frontend/lib/todayMarketCopyText.ts`(164줄)와 짝 시험(203줄 · 시험 11개)은 형수님 승인으로 삭제했다(§2).
- **60거래일 기타법인 +58.3조원(8/18 ~ 11/13 저장값) — 대조 완료(2026-11-18):** 형수님이 찾은 네이버 11/16 코스피 투자자별 값과 PC 보관소(OCI 수급 보관본 · 키움 ka10051) 11/16 값이 기타법인 +4,945억 · 연기금 −5,647억 · 보험 +13억 · 투신+사모 −4,229억으로 같다. 개인 · 외국인 · 기관계 · 금융투자는 70 ~ 86억(1% 안쪽) 차이로, 표시 시점이나 집계 방식 차이로 보인다(차이가 금융투자 한 곳에 모이고 나머지 분류는 같음). 기타법인의 큰 순매수는 수집 오류가 아니라 실제 저장 원천값이다.
- **변이 미검출 2건:**
  - A2b 1건은 같은 동작이다(빈 값이 이미 None 으로 정리됨).
  - F5 M14 는 읽는 동안 시장 갱신 완료 표시 대조를 끄는 변이다. 화면 키 지움 보호가 먼저 멈추게 해 보조 장치만 남는다.
- **화면 시험 흔들림:** 서버 시험과 동시에 돌린 전체 실행에서 1건이 실패했고, 이름은 출력 거르기로 확인하지 못했다. 단독 재실행에서는 99파일 1,889/1,889 통과였고, 옛 복사 파일 삭제 뒤 98파일 1,878/1,878 통과다.
- **서버 전체 회귀:** 커밋 전 1회 실행 완료(2026-11-18 · 6,399 passed · 2 skipped · §15).
- **시장 DB 의 빠진 표(r1 정정 범위 밖):** 새 GET 은 시장 DB 파일이 없으면 아무것도 만들지 않는다. 다만 파일은 있고 일부 시장 표가 빠진 경우에는, 함께 쓰는 기존 읽기 함수(`market_data_store` 연결)가 빠진 표를 만든다(공유 저장소라 바꾸지 않음 · 합성 DB 실측 · PROGRAM_TRUTH 에 그대로 적음).
- **동작 변화(r1 F1):** 후보 구성과 노출을 한 읽기로 묶어, 시장 DB 읽기가 실패하면 구성 요약과 겹침이 함께 '읽지 못함'이 된다(한쪽만 성공하는 경우 없음). 보유 시세만 실패하면 전처럼 겹침만 실패한다.
- **r1 작은 정정의 독립 재확인:** 시험 빈틈 · '-' 처리 · 줄 수 정정(G1 ~ G4)의 독립 검토 작업자는 네트워크 끊김으로 돌지 못했다. 대신 개발자가 변이 18건을 확인했다(17건 자동 + 남은 1건은 시험을 더해 제자리 변이로 잡힘 확인 · 원래 내용 · 수정 시각 같음).
- **격리 자료 상태:** §8 실측은 11/17 14:14 장중 저장값 기준이다. §13의 11/18 11:44~11:48 갱신으로 주간 화면의 가격 끝일은 11/18 장중으로 바뀌었다.
- **크기:** 주간 시험 고정 자료 `tests/fixtures/poc6_32_weekly_1116.json` 은 2,273줄(자료 파일 · 시험 코드 아님)이다. 코드 파일은 모두 근접선 아래이고, 가장 큰 것은 `TodayInvestmentCheckView.tsx` 845 · `app/market_evidence.py` 599 · `app/weekly_candidate_review.py` 592 · `app/decision_evidence_store.py` 589 다.

## 6. 다음 검증자(Codex)에게 알릴 점
- **PLAN §9 I-1 ~ I-32:** 판정 글에 없는 세부를 개발자가 정한 것이다. 특히 다음을 먼저 봐 주세요.
  - I-6 · I-29: '같은 공식 기초지수'는 지수명이 같을 때만, 계열은 '다른 지수 · 같은 계열'
  - I-12: '사용자 판단 미확인' 범위
  - I-18: 후보 출처 그대로
  - I-30: 복사 기준 대조 범위
- **뒤로 가기 방식:** 보낸 화면을 내리지 않고 숨겨 둔다(`MainPanel.tsx` · `lib/detailNav.ts`). 그래서 상세 화면의 캐시 지우기가 숨겨 둔 화면의 구독을 끊지 않아야 한다. [다시 불러오기]는 자기 키만 지운다(NAV-1 정정).
- **'미기록' 가드는 세 층이다:** 요청 모델 · 처리 함수 · 저장소. 다른 출처에서 'unrecorded' 는 422 다. 요청 모델이 먼저 거절하므로 저장소 검사는 직접 저장 경로용이다.
- **새 GET 경로 다섯:**
  - `/weekly/etf-check`
  - `/weekly/etf-check/records/{id}/review`
  - `/market/evidence`
  - `/market/etf-official`
  - `/market/constituents/summary`
  - 이와 별도로 `/holdings/market-evidence/latest` 에 `topn_basis` 칸을 더했다.
  - 주간 GET 두 곳(마지막 기록 · 기록 해석)은 새 읽기 전용 모듈 `app/decision_evidence_readonly.py`(mode=ro · 파일 없으면 만들지 않음 · 마이그레이션 없음)로 읽는다(검증자 r1 F3 정정 · §13). 처음 독립 검토의 BE-3 반박은 이 정정으로 대체됐다.
- **일일 복사 글:** 서버가 만든다(`app/market_evidence_text.py`). 화면 사건 문장 · 같은 근거 한 번 규칙을 서버로 옮겼고, 서버 · 화면이 같은 고정 자료(`tests/fixtures/poc6_32_evidence_cases.json` · 사건 24 · 같은 행 16)로 같은 글을 내는지 시험한다.
- **화면 고정 자료:** `frontend/lib/weeklyReviewTestFixtures.json` 은 서버 조립 출력으로 다시 만들었다. 시장 근거는 합성 시장 DB 값이다(실제 시장 값 아님 · `_note`). 서버 시험 `test_front_fixture_matches_server_assembly` 가 대조한다.

## 7. 사용자 확인이 필요한 항목
- 형수님 격리 화면 의견(2026-11-18): '정돈이 잘 된 것 같네요. 메뉴에 없지만 기능들은 그대로 있는 거구요.' — 메뉴 정리 · 상세 화면 열기 확인.
- 형수님 기록 저장(2026-11-18 10:57 · 격리 기록 DB 읽기 전용 확인): 주간 기록 `decision_20261118105730_6ee45ad8` · AI 답 2개(GPT · Claude) · 판단 '보류' · 근거 목록 24줄 · 후보 30 저장. 질문 원문에 '[근거 24] 고른 ETF 없음 — 내 보유와 겹침은 대조 전'이 있어 **후보를 고르기 전 글로 저장**됐다(넘기기에서 빠진 것 아님 · 고른 후보 · 구성 · 겹침 칸 비어 있음 · 기록 해석 경로 `selected.status = none` · `answer_count = 2`). [최신 자료 갱신]은 하지 않음(격리 자료 11/17 14:14 그대로).
- **AC4 확인(2026-11-18 11:26 · 형수님 · 격리 기록 DB 읽기 전용 대조):** 후보 476070 [고르기] → 복사 → AI 답 → [AI 투자 세션으로 넘기기] → 저장 `decision_20261118112626_a7664353`(판단 '쓸 만함' 직접 고름 · AI 답 GPT · Claude) → 다시 열어 확인. 저장값: `data_quality_snapshot.selected` = 476070 · R2 문구 '올랐고 국내시장보다 24.19%p 높음 · 잠정 비교' / '내렸지만 국내시장보다 21.59%p 덜 내림 · 잠정 비교' · 근거 목록 30줄 · 구성 · 겹침 칸 있음 · 기록 해석 경로 = 두 AI 최신 확인 '새 값 있음'(확인 항목 10 · 16줄) · 후보별 상태 · 인용 근거 · 이유 읽힘. 형수님이 두 버튼 차이(복사 = 클립보드 · 넘기기 = 같은 글 + 화면 자료를 기록 초안으로)를 물어 설명함.
- **AC4 격리 화면 확인(형수님):** `http://localhost:3001`(격리 · 운영과 따로)
  1. 메뉴 「주간 ETF 점검」 → 후보 하나 [고르기] → ③ 에서 '무엇을 담았는지 · 실제로 올랐는지 · 내 보유에 무엇이 겹치는지' 읽기
  2. [AI용 주간 검토 복사] → AI 들에 붙이고 답 받기 → [AI 투자 세션으로 넘기기] → 답 붙여 저장(판단은 '미기록' 그대로 또는 직접 고름)
  3. 「오늘의 투자 점검」 [최신 자료 갱신] → 「주간 ETF 점검」 ⑤ [기록 열기] → '당시 검토'에서 저장한 근거 · 다음 확인 찾기
- `frontend/lib/todayMarketCopyText.ts` 삭제 = 형수님 승인(2026-11-18) · 짝 시험 `todayMarketCopyText.test.ts` 와 함께 삭제(`git rm` · stage).
- 60거래일 기타법인 저장값 = 형수님 네이버 11/16 값으로 대조 완료(§5 · 기타법인 +4,945억 같음)

## 8. 실측(2026-11-18 · 격리 작업 사본 · 격리 서버 8001 · 3001)
- **격리 환경:**
  - 서버 = `uvicorn iso_app:app --port 8001`(격리 사본 app · 3001 출처만 허용)
  - 화면 = 격리 사본 `next dev` 3001
  - 상태 = 이 절 실측 당시 격리 사본 `state/`(11/17 14:14 저장값 · 이후 갱신은 §13)
- **응답(GET만):**
  - `/weekly/etf-check?selected=476070`
    - 공통 근거 partial(아침 판정 미확인 · KODEX 200 11/17 마감 가격 없음)
    - 476070 공식 기초지수 'iSelect 글로벌 비만치료제TOP2 Plus 지수(PR)' · 해외 · 주식 · 일반 · 실물(패시브) · 총보수 0.45%
    - 구성 '전체 확인' 11/16 · 11행 · 상위 3개 합 57.85%
    - 1개월 +11.13%(10/19 → 11/17 · '올랐고 국내시장보다 24.19%p 높음 · 잠정 비교')
    - 3개월 −1.58%(8/19 → 11/17 · '내렸지만 국내시장보다 21.59%p 덜 내림 · 잠정 비교')
  - `/market/evidence`: 일일 글에 [시장 판정 · 아침/당일] · 코스피 1 · 3 · 6개월(3 · 6개월 시작 종가 출처 FDR 표기) · 60거래일 다섯 분류 · 원/달러 · WTI · VIX(최신 값 날짜 11/16 · 6개월 끝 11/13 따로) · 최근 큰 변화 4건(종가 기준) · [자료 상태](오늘 시세 미확보 포함)
- **화면(자동 브라우저):**
  - 메뉴에 「보유와 후보 비교」 · 「ETF 구성종목」 없음 · 「주간 ETF 점검」 있음
  - 고르기 → ③ → [비교 상세](「주간 ETF 점검」에서 고른 후보로 열렸습니다) → [← 보낸 화면으로] → 고른 표시 · ③ 그대로
  - [구성종목 보기] → 한 ETF 모드(전체 확인 · 11행)
  - 1440 · 1000 · 420px 가로 스크롤 없음

## 9. 검사 결과(실측 · 2026-11-18)
- **서버:**
  - `black --check`: stage 된 .py 33개 'would be left unchanged'(r1 정정 뒤)
  - `flake8`: 통과
  - `pytest`(PYTHONDONTWRITEBYTECODE · r1 정정 뒤): 바뀐 서버 모듈을 가져오는 시험 31개 파일 **1,057 passed** · 주간 · 답 · r1 시험 158개를 하나씩 새 프로세스로 실행 158/158(정정 전 131/148)
- **화면:**
  - `npx tsc --noEmit`: 오류 0
  - `npx eslint`: stage 된 ts/tsx 70개 통과
  - `npx vitest run`(단독 · r1 정정 뒤): **98파일 1,885 passed**(옛 복사 파일 · 짝 시험 11개 삭제 뒤 · 삭제 전 99파일 1,889 · 동시 부하 실행 1건 실패 = §5)
- **변이(갈래별 · 저장소 밖 사본 또는 복원 확인):**
  - 공통 근거 서버 8/8 · 주간 서버 24/24 · 메뉴 4/4
  - 주간 글 · 답 23/24(1 같은 동작) · 주간 화면 25/25 · 비교 상세 15/15
  - AI 세션 28/28 · 구성종목 · NAV 10/10 · 일일 복사 15/16(1 보조 장치)
  - 검토 정정 23/23
  - 검증자 r1 정정 25/25(F1 ~ F3 · T1 7 · 시험 빈틈 · '-' · 줄 수 18)
  - **합계 200/202**
- **git:** `git diff --cached --check` 통과 · `git status` 실측 신규 45 · 수정 63 · 삭제 2 · stage 안 된 변경 0 · 추적 안 됨 0

## 10. 독립 검토(2026-11-18 · 서버 · 이동/상세 · 주간/세션/복사 · 판정 대조 4관점 · 관점마다 반박 검증)
- 지적 17건: 확인 15건(겹침 3쌍 → 고유 12건) · 반박 1건(BE-3 · 기록 해석 GET 의 `init_db` 경유 = 기존 GET 경로와 같은 방식 · 사용자에게 보이는 결함 없음) · 불확실 1건(NAV-2 · 문구 정정으로 처리)

| 지적 | 내용 | 처리 |
|---|---|---|
| NAV-1 | [비교 상세] [다시 불러오기]가 모든 ETF 상세 캐시를 지워 돌아간 보낸 화면의 펼친 행이 '확인 중'에 멈춤 | 자기 키만 지움(`invalidateQueryKey`) · 시험 2 |
| 복사 클립보드 | 서버 응답을 기다린 뒤 쓰기 → 누른 순간만 허용하는 브라우저에서 실패 가능 | 누른 순간 ClipboardItem(약속 값) · 없으면 예전 방식 · 시험 6 |
| 복사 안내 | '새로 읽는 중'이 확인 창 · 취소 뒤에도 남음 | 창 열 때 지움 · 취소 안내 · 시험 |
| '당시 검토' 대비 | 저장 칸에 가격 상태가 없어 '잠정 비교'가 사라짐 | 고른 후보 R2 결과 · 30행 · KODEX 끝 가격 상태 저장 · I-8 적용 · 없으면 '가격 상태 대조 기록 없음' |
| BE-1 · BE-2 | 코스피 자료 없음 · 시장 흐름 읽기 실패를 '없음 · 저장 자료 없음'으로 씀 | '계산하지 않음' · '읽지 못함' 사유 · 시험 3 |
| BE-5 | ② 계열 묶음을 '같은 공식 기초지수'라 부름 | '같은 기초지수 계열' · 지수명이 섞이면 상품마다 표시(I-29) |
| ⑤ | 고른 후보 · AI 답 수 없음 · '이 한 장에서' | 고른 후보 · AI 답 N개 · '이 화면에서' |
| 낡은 안내 | 사라진 메뉴 「ETF 구성종목」으로 보냄 | [구성종목 보기] 경로 |
| NAV-2 | '메뉴로 다시 열면' 문구가 실제 동작과 다름 | '다른 화면에 갔다가 다시 열면'(I-1 갱신) |
| BE-4 · 계획 밖 경로 | 다섯째 문구 · 새 경로 2개가 §9 에 없음 | PLAN I-25 · I-28 |
| PROGRAM_TRUTH | V2 미반영 | 메뉴 표 · 오늘 점검 · 주간 · 상세 두 화면 · AI 세션 · API 표 · 부록 갱신(옛 경로 · 이름 검색 0건) |

## 11. 경과(형수님 의견 → V2)
- 2026-11-17 V1 격리 화면 확인에서 형수님이 'ETF 주간 검토는 오늘의 투자 점검 목적과 맞지 않음 · 다른 화면으로', '「ETF 구성종목」 메뉴 정리', 'AI 세션에 담을 정보 · 활용 검토', '[AI용 시장 정보 복사]는 만들다 만 정보'라고 의견을 주셨다. → 설계자 재설계 판정 V2 → 개정 PLAN · 목업.
- 목업 확인 의견: '고른 후보' 표시가 쪼그라들어 보임 → [고르기]와 같은 40px · 파란 바탕 '✓ 고른 후보' · 왼쪽 파란 줄(W9).
- 질문 3건(「보유와 후보 비교」가 엉뚱한 두 상품을 비교 · 후보 단독 판정 기능 없음 · 「ETF 구성종목」 쓰임) → 사실 조사 · 독립 검증 → PLAN Q11 · Q12 → 설계자 PLAN 판정 V2(CONDITIONAL_PASS · Q11 (d) · Q12 (c)).

## 12. 검증자 r1 판정(Codex · 2026-11-18)

### A. 기능·산출물 검증

- **A-1 지시 일치 · 위반.** F1은 V2 §1~§3과 PLAN R1·R4·§4-3의 한 후보 검토 근거를 어긋나게 한다. F2는 V2 §1과 PLAN D4의 확인된 상품 구조 표시에 어긋난다. I-6·I-29의 공식 지수명과 지수 계열 구분, I-12의 주간·기존 판단 표시, I-18의 목록과 전달한 후보 사용, I-30의 일일 복사 기준 대조는 코드와 관련 시험에서 확인했다. I-18의 대안 목록 필요성은 설계자 판단 항목이다.
- **A-2 보고 정확성 · 일부 불일치.** 작업 사본의 A 42·M 61·D 2와 main 문서 8건을 확인했다. 양쪽 unstaged 0이며 사용자 handoff는 제출에서 제외됐다. 보고된 코드와 자료의 줄 수 및 삭제 2건의 승인 기록을 대조했다. §5의 이전 AC4 상태를 현재 §1·§7과 맞췄다. 새 GET의 읽기 전용 설명과 실제 파일 초기화가 F3에서 어긋난다.
- **A-3 산출물 정합성 · 위반.** F1의 혼합은 응답·복사문·저장 후 다시 읽은 기록에서 재현됐다. V2 AC3의 저장 후 갱신 복원은 합성 자료 변경 시험을 확인했다. §7에는 사용자의 선택·저장·다시 열기 근거가 있고, §8에는 격리 상태가 저장 전 갱신 시점(11/17 14:14)에 머문다고 적혀 있다. 실제 선택 기록을 저장한 뒤 새로 갱신하고 다시 연 실화면 근거는 확인되지 않았다. AC4 확인은 §7을 근거로 인정한다.
- **A-4 금지사항 · F3.** 신규 의존성·스키마 정의 변경은 없고, 옛 복사 파일과 짝 시험 삭제는 결과서의 승인 범위다. 새 GET 두 곳은 기존 초기화에 의해 기록 DB가 없는 경우 파일과 표를 생성했다.

| 지적 | 재현과 영향 |
|---|---|
| **F1 (P2) 같은 검토 건의 구성과 노출이 서로 다른 저장본에서 나옴** | `app/api_weekly_review.py:232`에서 구성 요약을 읽고 `:243`에서 노출 계산이 같은 후보의 구성을 다시 읽는다. 임시 DB에서 직접 보유한 주식 A를 65% 편입한 후보를 조회하고, 첫 읽기 직후 같은 구성일의 후보 저장본을 주식 B 65%로 교체했다. 교체 전 정상 대조군에서 확인된 노출은 100.00%였다. 혼합 응답은 구성 요약의 주식 A 65%를 유지하면서 주식 B로 계산한 0.00% 노출을 표시했다. 두 표시는 같은 11/16 기준이다. 그 조합이 복사문에 들어가고 세션 저장·다시 읽기에서 그대로 남았다. |
| **F2 (P3) 비어 있는 총보수를 상품 구조 차이로 확정** | `app/etf_official_info.py:196`에서 한쪽 값이 비어 있어도 두 값이 다르면 구조 차이에 넣는다. 임시 KRX 형식 CSV에 같은 공식 지수와 같은 확인된 구조 항목을 가진 ETF 두 개를 넣고 한쪽 총보수만 비웠다. `GET /market/etf-official`은 `structure_diffs=[{필드: 총보수, 보유: null, 후보: 0.15}]`와 ‘상품 구조 다름’을 반환한다. 화면의 구조 문장도 빈 값을 ‘—’로 넣어 두 상품의 확인된 차이로 제시한다(`frontend/app/components/workbench/ProductCheckTable.tsx:90`). |
| **F3 (P3) 새 주간 GET이 기록 저장소를 초기화함** | 기록 파일이 없는 임시 경로에서 `GET /weekly/etf-check/records/unknown/review`는 404를 반환하면서 DB를 생성했다. 새 빈 경로 조건에서 일반 `GET /weekly/etf-check`도 기록 DB를 생성했다. 두 경로의 읽기는 `app/decision_evidence_store.py:282`의 연결에서 `init_db`를 실행한다. 이 함수는 이전 스키마에 대한 마이그레이션도 포함한다. 새 경로의 읽기 전용·쓰기 없음 설명 및 검증의 부작용 경계에 영향을 준다. |

### B. 구현 규칙·구조 품질 검증

- **B-1 암묵 fallback · 위반.** F2에서 미확인 값을 구조 차이로 해석한다. 일반 출처의 미기록 거절, 주간 판단 생략과 명시적 null 처리, 직접 선택한 보류와 미기록의 구분은 관련 시험에서 확인했다.
- **B-2 단일 책임 · 위반 없음.** 메인 화면 기록과 상세 전송은 화면 코드와 `detailNav.ts`에 분리됐다. 공통 시장 근거 조립과 문장 생성이 분리돼 있다.
- **B-3 파일 책임 과다 · 상한 초과 없음.** 오늘 화면 845줄, 공통 근거 599줄, 후보 검토 592줄, 기록 저장소 589줄이다. 13,276줄·2,273줄 항목은 JSON 시험 자료다.
- **B-4 실험·운영 경계 · 위반 없음.** 합성 시장 근거와 화면 고정 자료의 서버 조립 대조 시험을 확인했다. 제품 모듈이 시험 자료에 의존하는 경로는 발견하지 않았다.
- **B-5 배포·실행 경로.** 새 GET 다섯 곳과 보유 근거의 `topn_basis`를 접점 시험으로 확인했다. Git 추적과 라우터 연결은 확인됐다. Dockerfile·배포 스크립트 변경은 없다. 주간 GET의 파일 쓰기는 F3에 기록했다.
- **B-6 구조적 퇴행 · 있음.** 동일한 후보 구성의 요약·노출이 별도 조회다(F1). 상세에서 숨긴 발신 화면 복원·단계별 뒤로 가기·정확한 키 무효화는 관련 시험에서 통과했다. 주간 API 시험 1건(`tests/test_poc6_32_weekly_review.py:641`)은 모듈 묶음에서 통과하나 새 프로세스에서 그 시험만 실행하면 `fake_mev`와 `_mev_json`이 서로 호출해 `RecursionError`가 난다. 독립 재현에서는 시장 근거를 고정 입력으로 지정해 이 시험 준비 의존성을 피했다.

### 3. 기반 문서 준수

- 화면과 시장 복사 기준은 서버·프런트 공통 고정 자료 시험에서 대조했다. 신규 문서는 제출된 설계·판정·PLAN·결과서다. 신규 런타임 의존성이나 운영 프레임워크의 도입은 발견하지 않았다.

### 4. 코드 안전성

- **MEDIUM.** F1의 근거 혼합은 사용자에게 보이고 보존된다. F3의 조회 시 DB 생성은 임시 경로에서 재현했다. 운영 자료, 실제 기록, 외부 조회는 검증에서 사용하지 않았다.

### 5. 범위 폭주

- **NONE.** 공식 지수, 주간 기록, 상세 복원과 복사 경로는 V2와 PLAN §9 범위다. I-12의 과거 판단 추정과 I-18의 후보 출처는 개발자 해석으로 설계자 확인 대상이다.

### 6. 종합 판정

**REJECTED.** F1~F3 및 실제 갱신 뒤 AC3 복원 근거를 확인한 뒤 재검증한다.

- 검증 실측은 백엔드 관련 10파일 502건 통과, 프런트 관련 13파일 410건 통과, 독립 재현 3건이다. F1~F3 독립 시험의 통과는 지적한 동작을 재현했다는 뜻이다. 타입 검사, 변경 TS·TSX 70개 ESLint, 변경 파이썬 28개 black·flake8·컴파일, 양쪽 공백 검사는 통과했다. ESLint는 격리 소스 사본에서 설정 플러그인 초기화가 실패해 작업 사본에서 수정 옵션 없이 다시 실행했다.
- 전체 회귀와 기존 변이 시험은 반복하지 않았다. 실제 브라우저 클립보드와 실화면 갱신을 검증자가 새로 실행하지 않았고, 합성 복사·기록 시험 및 개발자·사용자 확인 근거를 사용했다.

### 7. 사용자에게 한마디

지적 내용을 이 절에 기록했다. 검증자가 수정한 곳은 결과서 상단 단계, §5의 AC4 상태 한 줄, §12 판정이다. 제품 코드·시험과 상태 문서는 수정하지 않았다.

## 13. 검증자 r1 지적 처리(개발자 · 2026-11-18)

| 지적 | 처리 | 시험 · 변이 |
|---|---|---|
| **F1 (P2)** 한 검토 건에 다른 구성 저장본이 섞임 | 새 `app/weekly_candidate_reads.py` `read_candidate` 가 ETF 목록 · 고른 후보와 보유 ETF 구성 · 원천일 확인 기록 · 후보 저장 최신 구성을 **mode=ro 연결 하나 · 한 읽기 트랜잭션(BEGIN)**에서 읽는다. ③ 구성 요약 · 겹침 · 복사 글 · 넘기기 묶음 · 공식 정보 이름은 모두 이 사본으로만 만든다. 같은 뿌리였던 ETF 목록 두 번 읽기도 없앴다. `GET /market/constituents/summary` 도 같은 함수를 쓴다. 이를 위해 기존 모듈 두 곳(`etf_constituents_status` · `constituents_pair_exposure_io`)에서 읽기 본문만 연결 단위 함수(`snapshots_in` · `analysis_rows_in` · `master_in`)로 뺐다(기존 함수 이름 · 결과 같음) | `tests/test_poc6_32_r1_reads.py`: 요청 도중 같은 구성일 저장본을 A → B 로 바꿔도 응답 · 복사 글 · 넘기기 묶음 · 저장 후 다시 연 기록이 같은 짝(A · 100.00), 읽기 트랜잭션 안 쓰기는 기다림, 트랜잭션 뒤 다시 읽기 변이 3종 · BEGIN 제거 변이 모두 잡힘 |
| **F2 (P3)** 빈 총보수를 구조 차이로 | `pair_state` 는 두 값이 모두 확인된 칸만 `structure_diffs` 에 넣는다. 빈 값 · 공백 · '-' 류(—, –, －)는 `structure_unconfirmed[{field, side}]` 로 따로 낸다. 같은 지수면 '같은 공식 기초지수'를 유지하고 사유 끝에 '상품 구조 일부 확인 안 됨'을 붙인다. 화면은 '확인 안 된 구조 항목: 총보수(보유 쪽)'를 따로 적는다. 실제 공식 CSV(2026-09-27 · 1,175행)의 네 구조 칸에는 빈 값 · '-' 가 0건이다 | 서버 · 화면 경우별 시험 · 변이(빈 값만 미확인 · 하이픈만 · 부분 문자열 · strip 없음 등) 모두 잡힘 |
| **F3 (P3)** 주간 GET 이 기록 DB 를 만듦 | 새 `app/decision_evidence_readonly.py`: mode=ro 로 열고, 파일이 없으면 None(폴더 · 파일을 만들지 않음), PRAGMA table_info 로 있는 칸만 읽으며, 마이그레이션은 하지 않는다. 주간 GET 두 곳(마지막 기록 · 기록 해석)이 이 모듈로 읽는다. 같은 뿌리인 `GET /market/evidence` 는 시장 DB 파일이 없으면 저장소를 부르지 않고 '읽지 못함'을 돌려준다. `/market/etf-official` · `/market/constituents/summary` 는 원래 만들지 않음을 시험으로 고정했다. 설명 문구 · PROGRAM_TRUTH 를 실제 동작으로 고쳤다 | DB 없음 → 두 GET 모두 만들지 않음 · 있는 DB 는 sha · mtime 그대로 · 옛 스키마 2종 마이그레이션 없이 읽음 · 시장 DB 없음 → 만들지 않음 · 최근 주간 기록 고르기(저장 시각 내림차순 · 같으면 id · 다른 화면 기록 제외) 정렬 변이 6종 잡힘 |
| **시험 순서 의존** RecursionError | 시험 준비가 진짜 공통 근거 빌더를 모듈을 읽을 때 잡아 두게 했다(`_BUILD_MEV`). 범위는 검증자가 적은 1건보다 넓은 17건이었다 | 주간 · 답 · r1 시험을 하나씩 새 프로세스로 실행: 정정 전 131/148 → 정정 후 158/158 · 세 가지 순서 · 수집 순서 뒤집기 통과 |
| **AC3 실화면 근거** | 아래 | 아래 |

**AC3 실화면(2026-11-18 · 격리 화면 3001 · 서버 8001 · r1 정정 코드)**
- 형수님이 11:26 에 후보 476070 을 고른 검토를 저장했다(`decision_20261118112626_a7664353`). 그 뒤 격리 화면에서 [최신 자료 갱신]을 눌렀다(11:44 ~ 11:48 · ETF 가격 11/18 장중 1,046종목 · KODEX 200 11/18 장중 · 수급은 격리 사본에 OCI 보관소가 없어 11/13 그대로).
- 갱신 뒤 「주간 ETF 점검」(지금 자료):
  - 조건 줄이 '10/19 → 11/18 · 11/18 가격 = 장중 저장값 포함 · 잠정(장중 833개) · 3개월 공통 기간 8/20 → 11/18' 로 바뀌었다.
  - 476070 은 11/18 가격 행이 없어 ② 목록에 없다.
- ⑤ 최근 검토 기록에는 '저장 2026-11-18 11:26 · 원자료 기준일 11/17 · 고른 후보 476070 · 사용자 판단 쓸 만함(직접 고름) · AI 답 2개'가 나온다.
- [기록 열기] → 「AI 투자 세션」 '당시 검토'는 저장 당시 값 그대로다(다시 계산 없음).
  - 공식 기초지수 · 상품 구조 · 상위 3개 합 57.85% · 구성 기준일 11/16
  - '1개월 +11.13%(10/19 → 11/17) · 국내시장 −13.06% · 올랐고 국내시장보다 24.19%p 높음 · 잠정 비교'
  - '3개월 −1.58%(8/19 → 11/17) · 국내시장 −23.17% · 내렸지만 국내시장보다 21.59%p 덜 내림 · 잠정 비교'
  - AI 칸: GPT · Claude 최신 확인 '새 값 있음'(예: GPT 코스피 11/17 종가 4,968.48 을 새 값으로 적음 · 확인 항목 10 · 16줄) · 후보별 상태 · 인용 근거 · 이유
- 화면 캡처는 세션 임시 폴더에 있다(저장소 밖): `/private/tmp/claude-501/-Users-hyungsookim-projects-krx-hyungsoo/a6c4c2ec-40d4-4eb9-a7ff-9759f33e21bb/scratchpad/pw/out/ac3final_live_cond.png` · `…_live_last.png` · `…_record.png`.

**r1 정정 검사(실측)**
- 서버:
  - black · flake8: stage 된 .py 33개 통과
  - 바뀐 모듈을 쓰는 시험 31개 파일: 1,057 passed
  - 공통 근거 시험 86 passed
- 화면:
  - tsc 0
  - eslint: stage 된 ts/tsx 70개 통과
  - vitest 98파일 1,885 passed
- 변이 25/25:
  - F1 ~ F3 · T1 정정 7종
  - 작은 정정 18종: 정렬 6 · 다시 읽기 4 · '-' 처리 5 · 옮긴 코드 3. 이 중 출처 이름표 1종은 처음에 살아남아 시험을 더한 뒤 제자리 변이로 잡힘(원래 내용 · 수정 시각 같음 확인)
- F1 ~ F3 · T1 은 다른 작업자가 원래 재현 시나리오로 반증해 '고쳐짐'을 확인했다. 작은 정정의 독립 재확인은 네트워크 끊김으로 돌지 못했다(§5).
- `app/market_evidence.py` 588줄이다(정정 중 602 → 도움 함수를 `market_evidence_reads.py` 로 옮김).
- git(격리 사본):
  - 신규 45 · 수정 63 · 삭제 2 · stage 안 된 변경 0 · 추적 안 됨 0
  - 새 파일 = `app/weekly_candidate_reads.py`(130) · `app/decision_evidence_readonly.py`(77) · `tests/test_poc6_32_r1_reads.py`(575)

## 14. 검증자 r2 판정(Codex · 2026-11-18)

### A. 기능·산출물 검증

- **A-1 지시 일치 · 통과.** F1의 구성과 노출은 같은 SQLite 읽기 트랜잭션에서 나온다. WAL 모드에서 ETF 목록 읽기 직후 다른 연결로 같은 구성일 저장본을 교체하고 커밋했다. 그 응답은 주식 A 65%와 A로 계산한 노출 최댓값 100.00%를 유지했고, 복사문과 저장 기록에도 같은 값이 남았다. 다음 조회부터 주식 B 65%와 노출 0.00%를 함께 반환했다. F2는 공식 CSV 총보수가 공란 또는 하이픈이어도 확인된 추적배수 차이만 구조 차이로 반환하고, 총보수는 보유 쪽 확인 불가로 남겼다. F3의 주간 GET 두 곳은 기록 DB와 상위 폴더가 없는 상태에서 그대로 404 또는 기록 없음으로 응답했다. 기존 DB와 이전 스키마 읽기는 바이트·수정 시각·열 보존 시험으로 확인했다.
- **A-2 보고 정확성 · 통과.** 작업 사본의 신규 45·수정 63·삭제 2와 main 문서 8건을 확인했다. 양쪽 unstaged 0이고 사용자 handoff는 제외됐다. §13의 신규 파일 줄 수 130·77·575와 공통 시장 근거 588줄을 실측했다. §5의 갱신 시점을 바로잡고 §8의 실측이 §13 갱신 전 사례임을 표시했다.
- **A-3 산출물 정합성 · 통과.** §13의 격리 캡처를 대조했다. 갱신된 주간 화면은 11/18 자료를 사용하고, 다시 연 기록은 11:26 저장 시각, 11/17 원자료, 선택 ETF와 1·3개월 수치, 겹침과 미확인 범위를 보존한다. AC3의 실제 갱신 뒤 복원 근거를 확인했다. AI 최신 확인과 당시 근거의 원문 복원은 저장 자료 시험과 §13의 기록을 함께 사용했다.
- **A-4 금지사항 · 정정 범위 통과.** F3 기록 조회는 파일 생성이나 마이그레이션 없이 읽는다. 공통 시장 근거는 시장 DB 파일이 없으면 생성하지 않는다. 기존 파일에서 시장 표가 빠진 경우의 공유 초기화는 §5의 공개 한계이며, 임시 DB로 재현했다. 신규 의존성·배포·스키마 정의 변경은 없다.

### B. 구현 규칙·구조 품질 검증

- **B-1 암묵 fallback · 위반 없음.** 공란과 자리표시자는 미확인 사유로 반환된다. 이전 기록의 생략 가능 칸과 단일 AI 답변은 기존 저장소 계약에 맞게 읽는다.
- **B-2 단일 책임 · 위반 없음.** 새 모듈이 후보 읽기와 기록 읽기를 각각 담당한다. 구성 조회의 연결 단위 함수 추출은 기존 진입점의 날짜·행·확인 규칙을 유지한다.
- **B-3 파일 책임 과다 · 위반 없음.** 후보 읽기 130줄, 기록 읽기 77줄, 공통 시장 근거 588줄, 관련 신규 시험 575줄이다.
- **B-4 실험·운영 경계 · 위반 없음.** 제품 경로의 시험 자료 의존을 발견하지 않았다.
- **B-5 배포·실행 경로 · 위반 없음.** 새 모듈의 Git 추적과 호출 연결을 확인했다. Dockerfile·배포 스크립트 변경은 없다.
- **B-6 구조적 퇴행 · 위반 없음.** POC6-31의 구성 수집·계열·노출·저장 접점을 다시 실행했다. r1에서 단독 실패한 시험은 새 프로세스에서 성공했다.

### 3. 기반 문서 준수

- PLAN의 후보 노출·보존 및 확인된 상품 구조 표시 계약과 대조했다. PROGRAM_TRUTH에 기록 조회와 공통 시장 근거의 초기화 범위가 일반적인 동작과 구분돼 있다. 개발자 해석 I-12와 I-18은 설계자 검토 항목으로 남아 있다.

### 4. 코드 안전성

- **LOW.** 시장 DB 파일이 이미 있고 필요한 표가 빠져 있으면 공통 시장 근거 조회가 기존 저장소 초기화를 통해 해당 표를 생성할 수 있다. 이 경계는 §5의 공개 한계다. 검증은 임시 DB와 제출된 캡처를 사용했다.

### 5. 범위 폭주

- **NONE.** r1 정정, 읽기 경로 분리, 시험 준비의 순서 의존 정리와 AC3 근거 보완 범위다.

### 6. 종합 판정

**VERIFIED.** F1~F3와 r1 단독 시험을 재확인했고 AC3의 갱신 뒤 복원 근거를 확인했다.

- 검증자 실측은 관련 백엔드 12파일 539건, 프런트 6파일 227건, 독립 확인 5건, 지적된 주간 API 시험 단독 실행 1건 통과다. 변경 파이썬 14개 black·flake8·컴파일, 타입 검사, 변경 프런트 5개 ESLint 및 공백 검사도 통과했다. ESLint는 설치된 설정을 쓰는 작업 사본에서 실행했다.
- 백엔드 전체 회귀와 변이 시험은 다시 실행하지 않았다. 개발자 §13의 전체 프런트·사용처·변이·개별 시험 수는 개발자 실행 근거다.

### 7. 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 검증자가 수정한 곳은 결과서 상단 단계, §5와 §8의 격리 자료 시점, §14 판정이다. 제품 코드와 시험은 수정하지 않았다.

## 15. 설계자 RESULT 판정 V2 · PASS 확정 조건 확인(개발자 · 2026-11-18)

- 판정서: `docs/ai_design/POC6/POC6_32_ETF_WEEKLY_REVIEW_RESULT_DECISION_V2_2026-11-18.md`(조건부 PASS · I-18 후속 보완 등록).
- **조건 1 · 서버 전체 회귀:** 격리 작업 사본 최종 stage 상태(신규 45 · 수정 63 · 삭제 2 · stage 안 된 변경 0)에서 `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider`(caffeinate) → **6,399 passed · 2 skipped · 1 warning · 실패 0 · 28분 2초**. 회귀 뒤 작업 사본 변경 0(최종 반영 대상과 같음). 화면은 같은 최종 상태에서 vitest 98파일 1,885 passed · tsc 0(§13).
- **조건 2 · [비교 상세] 선택 인계(11/17 Q11 기준):** 격리 화면 3001 · 서버 8001 에서 자동 브라우저로 세 진입 동선을 확인했다(보유 이름 · 코드는 적지 않음).

| 진입 | 넘긴 쪽 | 상대 칸 |
|---|---|---|
| 「주간 ETF 점검」 ③ [비교 상세](고른 후보 TIGER 인도니프티50(453870) · 1개월 상위 1위) | 후보 칸 = '상위 1위 · TIGER 인도니프티50 · +11.51%' | 보유 칸 = '보유를 고르세요'(사용자에게 맡김) |
| 「보유」 줄 상세 [보유와 후보 비교에서 보기 →] | 보유 칸 = 넘긴 보유로 채워짐 | 후보 칸 = '후보를 고르세요' |
| 「후보리스트」 줄 상세 [비교 상세 →] | 후보 칸 = 그 ETF | 보유 칸 = '보유를 고르세요' |
| 넘긴 것 없이 직접 열기 | — | 두 칸 모두 빈 선택 |

  - 시험 근거: `HoldingCandidateCompareView.test.tsx` :158(직접 열면 두 칸 빈 선택) · :227(「보유」에서 넘긴 보유만 채우고 후보는 빈칸 · 한 번만) · :755(「주간 ETF 점검」에서 고른 후보로 열림) · `WeeklyEtfCheckView.test.tsx`(주간 넘김 관통).
- **후속 항목 등록 — `I-18 · 같은 공식 기초지수 교체 대안 조회`:** [비교 상세]에서 한쪽 ETF 를 고르면 보관된 전체 ETF 기준정보에서 같은 공식 기초지수의 다른 ETF 를 고를 수 있게 한다(기준정보 날짜 · 지수 확인 불가 · 확인 범위에 다른 상품 없음 표시 · 상품 구조 · 환헤지 · 비용의 확인된 차이). 재검토 시점 = 실제 보유 상품의 교체 대안을 고를 필요가 생겼을 때(그때 전체 보관 목록에서 공식 지수 일치 사례 먼저 확인).
- **운영 첫 사용 확인:** 실제 Safari · Chrome 의 일일 복사 클립보드 동작은 운영 화면에서 처음 복사할 때 사용 브라우저로 확인한다.
- **판정: 설계자 RESULT PASS(2026-11-18 · 판정 V2 §4 두 조건 충족).** 다음 = 형수님 승인에 따른 커밋 · main 합치기(push 는 따로 승인).
