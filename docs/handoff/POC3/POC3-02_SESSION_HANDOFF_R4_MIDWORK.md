# POC3-02 세션 인계 — 검증자 4차 REJECTED 수정 (작업 중 인계)

작성 시각: 2026-07-29
사유: 응답 스트림 반복 출력("course") 장애로 세션 교체. **디스크 파일은 무손상.** 새 세션에서 동일하게 이어받기 위한 인계.

---

## 0. 지금 어디까지 왔나 (한 줄)

POC3-02 UI-2 Judgment Workbench 의 **검증자 4차 REJECTED** 를 수정 완료했다.
**코드 수정 전부 완료 · 전체 자동 검증 통과.** `holdingTopnMatch` 죽은 코드는 사용자 승인 후 제거 완료. 남은 것은 **7섹션 보고서 + 완료 JSON 작성 → 검증자 인계** 뿐이다. **commit 은 아직 하지 않았다** (POC3-02 §14 는 문서 갱신만 지시 · commit 여부 사용자 확인 필요).

---

## 1. 현재 작업 대상

- 지시서: `docs/handoff/POC3/POC3-02_UI2_JUDGMENT_WORKBENCH_DESIGN_V1.md` (REMEDIATION-1 병합본)
- 단일 목표: 후보·보유·근거를 **읽기 전용 판정 Workbench** 로 재조합. 한 화면에서 우선 후보 ETF 선별 + 후보 내 보유 확인 + stale/불가/비교불가 식별 + 선택 종목의 실제 저장 가격 차트·상세 근거 확인.
- REMEDIATION-1 예외 허용: **읽기 전용 API 1개** `GET /market/price-series` (기존 `fetch_price_history` SQLite 재사용). 그 외 신규 DB/source/cache/formula/factor 금지, timeout 증가 금지, Dashboard `/market/topn/latest` 호출 복구 금지, Dashboard 계약 미변경, POC3-03 미착수.

---

## 2. 검증자 4차 REJECTED 지적 → 조치 상태

| # | 지적 | 조치 | 상태 |
|---|------|------|------|
| A-1(1) | 선택 상세(SelectedDetail)가 여전히 과거 Evidence(`held=!!ev`, `holdingTopnMatch`)로 보유/후보 판정 | SelectedDetail 을 **현재 heldTickers/candTickers 집합** 기반으로 전환 (JudgmentWorkbenchView.tsx line 695-696 `relationState`) | ✅ 완료 |
| A-1(4) | 조회 실패 시 관계가 "미포함(—)" 으로 축약됨 (확인 불가로 표시해야) | 3-state 헬퍼 `relationState`(helpers.ts:119) 신설 — 집합 undefined=unknown="확인 불가". 후보표·보유표·선택상세 **세 곳 모두** 적용 | ✅ 완료 |
| A-1(2) | 1440×900 가로 오버플로 — Evidence 열 잘림, 하단 가로 스크롤바 접근 불가 (clientWidth=1141 vs scrollWidth=1239) | `.wb-table` 폰트 13→12px·패딩 5/8→4/6px 로 14열 압축 + `.wb-table-wrap { overflow:auto; max-height:70vh }` 로 스크롤바를 뷰포트 내로 + 헤더 sticky (globals.css line 1604~) | ✅ 완료 |
| A-3 | STATE 문서: 캐시 공유 서술/라인 수/테스트 수 stale | STATE 라인 수 실측 정정(789/276/210/101/91), r4 정정 블록 추가 | ✅ 완료 |
| 잔여 | `holdingTopnMatch` 가 관계 판정에서 제거됐으나 **helpers.ts 에 정의만 남아 참조 0건** (죽은 코드) | 사용자 승인 후 helpers.ts 에서 제거 (210→199줄). tsc/lint/test 재통과 확인 | ✅ 완료 |

---

## 3. 완료된 실측 검증 (이 세션에서 직접 실행)

- `npx tsc --noEmit` → exit 0 (통과)
- `npm run lint` (eslint) → exit 0, 경고 0
- `npm run build` (next build) → exit 0
- `npm run test` (vitest) → **52 passed** (Workbench 24 + queryCache 8 + Dashboard 13 + invalidation 7)
- backend `pytest tests/ -k api` → **101 passed**
- backend `pytest test_api_price_series.py` → **6 passed**
- backend 전체 회귀 → **1072 passed / 4 skipped / 0 failed** (233s) — STATE 기재값과 일치
- backend collected 총 **1076** (= 1072 passed + 4 skipped)

> 라인 수 실측: JudgmentWorkbenchView 789 · HoldingTable 276 · helpers 210 · PriceChart 101 · api_price_series 91. 모두 KS-10(프론트 900 / 백엔드 650) 이내.

---

## 4. 변경 파일 (git status 스냅샷 · 2026-07-29)

수정(M):
- `app/api.py` (price-series 라우터 등록)
- `docs/STATE_LATEST.md`, `docs/handoff/STATE_LATEST.md`
- `frontend/app/components/LeftSidebar.tsx`, `MainPanel.tsx` (Workbench 진입)
- `frontend/app/globals.css` (wb-* 스타일 + r4 오버플로 수정)
- `frontend/lib/api/dashboardInvalidation.test.ts`, `dashboardKeys.ts`, `index.ts`

신규(??, 전부 untracked):
- `app/api_price_series.py`
- `frontend/app/components/JudgmentWorkbenchView.tsx` (+ `.test.tsx`)
- `frontend/app/components/workbench/HoldingTable.tsx`, `PriceChart.tsx`, `helpers.ts`
- `frontend/lib/api/priceSeries.ts`
- `tests/test_api_price_series.py`

> ⚠️ 신규 파일 전부 아직 `git add` 안 됨. commit 시 `--untracked-files=all` 로 누락 확인 필요.

---

## 5. 미결 결정 (해소 완료)

**`holdingTopnMatch` (helpers.ts) 죽은 코드 제거** — 사용자에게 (a)제거/(b)유지 질의 → **사용자 "제거" 승인 (2026-07-29)**. helpers.ts 에서 함수+주석(구 line 134-143) 삭제, 파일 210→199줄. `HoldingsMarketEvidenceItem` 타입은 다른 함수가 계속 사용하므로 import 유지. 제거 후 tsc/lint/test 재통과 확인 완료.

---

## 6. 남은 순서 (코드 작업 끝 · 보고만 남음)

1. ~~죽은 코드 제거~~ ✅ 완료. ~~tsc/lint/test 재확인~~ ✅ 완료.
2. **7섹션 표준 보고서 작성** (CLAUDE.md §4) — 다음 액션.
3. 지시서 §21 완료 보고 JSON 템플릿 있으면 함께 작성 (verification 필드 실측값으로).
4. 판정: 개발자는 PASS/DONE 선언 금지 → **IMPLEMENTED_AWAITING_VERIFICATION** 으로 검증자에게 인계.
5. commit 은 **사용자 승인 후에만**. POC3-02 §14 는 문서 갱신만 지시했으므로 코드 commit 지시 없음 — commit 여부 자체를 사용자에게 확인.

---

## 7. 핵심 계약/함정 (반드시 지킬 것)

- **후보·보유 관계는 항상 현재 목록(LIST_DIRECT) 기준.** 과거 Evidence(`topn_match`/`matched_topn_count`)로 판정 금지 — 이게 r1~r4 내내 반복된 핵심 결함. 요약·후보표·보유표·선택상세 4곳이 **같은 기준**이어야 정합.
- **조회 실패 = "확인 불가"(unknown), false 아님.** `relationState`: 집합 undefined→unknown, 있음→yes, 없음→no.
- 캐시 키(§9): Holdings/Evidence/NAV 는 Dashboard 와 **동일 endpoint·조건 → 같은 키 공유**. Market topn 만 조건(n=30 vs n=10) 달라 별도 키(`WB_KEY_CAND`). Dashboard 후보 공급 경로로 Workbench 캐시 쓰지 말 것.
- 가격 시계열은 **선택 ticker lazy** (N+1 방지). PriceChart 가 useSharedQuery 로 선택 시에만 호출.
- ticker 정규식: `^[0-9A-Za-z]{6}$` (영숫자 6자 — `0000D0` 같은 실 ETF ticker 허용. `^\d{6}$` 금지).
- commit 메시지: heredoc `@'...'@` (Bash) 는 subject 앞에 `@` 붙는 버그 → `git commit -F <파일>` 사용.

---

## 8. 참조 위치

- 상태 앵커: `docs/STATE_LATEST.md` (canonical) — r1~r4 정정 이력·검증 수치 기재.
- 지시서: `docs/handoff/POC3/POC3-02_UI2_JUDGMENT_WORKBENCH_DESIGN_V1.md`
- 마스터 설계: `docs/handoff/POC3/POC3_PC_JUDGMENT_UI_RECOMPOSITION_MASTER_DESIGN_V1.md`
- 직전 완료: POC3-01 UI-1 Dashboard (VERIFIED + UI 테스터 확인, commit 0b35f9b3)
