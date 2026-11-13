# POC6-29 보관 — 「요즘 잘 오르는 ETF」(C) 전용 파일

POC6-29(PLAN 판정 2026-11-12 Q14)에서 「요즘 잘 오르는 ETF」 메뉴를 없애면서, 그 화면에서만 쓰던 파일을 지우지 않고 이 폴더로 옮겼다(`git mv` · 이력 유지).

- 이 폴더는 `frontend/` 밖이다. 타입 검사(`npx tsc --noEmit`) · eslint · vitest · Next 빌드 · 백엔드 pytest 어느 쪽도 이 폴더를 읽지 않는다.
- 운영 화면은 이 폴더의 파일을 import 하지 않는다. 남은 언급은 다른 파일의 주석뿐이다(예: `useMarketVixRetry.ts` · `MarketContextCard.tsx` · `etfExposureDraft.ts` 주석의 옛 파일 이름).
- 되살릴 때는 아래 "원래 경로"로 다시 `git mv` 한 뒤, "대신하는 곳"과 겹치지 않는지 먼저 확인한다.
- 기능별로 옮긴 곳은 화면 「진단·상태 › 미사용 기능 › 신규 ETF 관찰 점검」의 「자세히」에서도 보인다(POC6-29 보완 · 보완 PLAN 판정 Q-R5).

## 원래 경로 → 대신하는 곳

| 원래 경로(`frontend/` 기준) | 하던 일 | 대신하는 곳(POC6-29) |
|---|---|---|
| `app/components/MarketDiscoveryView.tsx` | 「요즘 잘 오르는 ETF」 화면 전체(후보 카드 · 표 · 시장 배경 · 갱신 · 넘기기) | 「오늘의 투자 점검」(시장 근거 접기 · [최신 자료 갱신]) · 「ETF보유 및 후보 선정」 네 메뉴 |
| `app/components/CandidateCards.tsx` | 후보 카드 | 「후보리스트」 [목록] (`workbench/RankingList.tsx`) |
| `app/components/CandidateTable.tsx` | 후보 표 | 「후보리스트」 [표] (`workbench/RankingTable.tsx`) |
| `app/components/ReturnPeriodLine.tsx` | 후보 기간 수익률 한 줄 | 행 상세 수치(`workbench/DetailNumbers.tsx`) |
| `app/components/SamePeriodValue.tsx` | 같은 기간 KODEX 200 비교 값 | 행 상세 수치 '같은 기간 KODEX 200'(`workbench/DetailNumbers.tsx`) |
| `app/components/MarketBasisDefaultRow.tsx` | [이 기준을 기본으로] 한 줄 | 화면별 `BasisSaveRow`(`workbench/CompareHead.tsx`) |
| `app/components/useMarketTopnLoad.ts` | 후보 목록 조회 · 조건 | 화면별 공통 기간 요약(`useEtfCompareSummary` · `lib/etfCompareCondition.ts`) |
| `app/components/TransferToAISessionsCard.tsx` | 목록을 AI 투자 세션으로 넘기기 | 「후보리스트」 「이 목록으로 할 일」(`workbench/ListTransfer.tsx`) |
| `app/components/TransferToETFExposureCard.tsx` | 목록을 ETF 구성종목으로 넘기기 | 같은 곳(`workbench/ListTransfer.tsx`) |
| `app/components/HoldingsCompareView.tsx` | 「보유와 비교」 탭 | 「보유와 후보 비교」(`HoldingCandidateCompareView.tsx`) |
| `app/components/holdings_compare/CompareCards.tsx` | 보유 · 후보 카드 비교 | 「보유와 후보 비교」 두 열 표 |
| `app/components/holdings_compare/SelectedDetail.tsx` | 고른 후보 상세 | 「보유와 후보 비교」 표 · 판단 근거 미리보기 |
| `app/components/holdings_compare/SelectedHoldingDetail.tsx` | 고른 보유 상세 | 같은 곳 |
| `app/components/today/JudgmentQueueSection.tsx` | 「오늘의 투자 점검」 판단 대기 목록(C 연결) | 「보유 점검」 · 「잘 오르는 ETF」 카드(`today/CheckCards.tsx`) |
| `lib/marketBasisPreference.ts` | C 기본 기간 저장(`krx.marketDiscovery.defaultBasis.v1`) | 화면별 저장(`krx.screenBasis.<화면>.v1`) · 옛 값은 「오늘의 투자 점검」만 한 번 이어받음(판정 Q13) |
| `lib/marketConditionStore.ts` | C 조회 조건 공유 | `lib/etfCompareCondition.ts`(화면별 조건) |

## 함께 옮긴 시험(그 파일만 보던 시험)

`app/components/` 아래 `MarketDiscoveryVixRetry.test.tsx` · `MarketDiscoveryRefreshNote.test.tsx` · `ReturnPeriodLine.test.tsx` · `MarketBasisDefault.test.tsx` · `CandidateCards.test.tsx` · `StoredDrawdownTable.test.tsx` · `RejectedScoreCloseout.test.tsx` · `TransferToAISessionsCard.test.tsx` · `holdings_compare/HoldingsComparePreviewWiring.test.tsx` · `holdings_compare/CompareCards.test.tsx` · `holdings_compare/SelectedDetail.test.tsx` · `today/TopHoldingsAggregate.test.tsx`, `lib/` 아래 `marketBasisPreference.test.ts` · `marketConditionStore.test.ts`.

같은 계약 중 살아 있는 화면에 남은 것은 그 화면 시험으로 옮겼다(예: [VIX 다시 받기] 버튼 흐름 = `today/TodayVixRetry.test.tsx`(A 의 실제 조합 · 표식 · 다른 id 무시 · 빠른 완료 · 실패 · 해당 없음 · 진행 따라감 · 전체 갱신 거절 · 전체 갱신 뒤 다시 받기) · 시장 갱신 이어 보기 = `today/TodayMarketFlow.test.tsx` · KOSPI 상태 문장의 AI 초안 = `KospiStatusSurfaces.test.tsx` · 기본 기간 저장 = `lib/etfCompare.test.ts` · `SectorSummaryView.test.tsx`). 보관 파일의 시장 GET 응답 처리 시험(같은 입력 1회 · 늦은 응답 무시 · 조건 바꾼 뒤 실패)은 C 화면의 목록 조회(`useMarketTopnLoad`) 전용이라 옮기지 않았다(공용 요청 공유 자체는 `lib/api/marketTopnInflight.test.ts` 가 계속 본다).

## 남겨 둔 것

- `lib/returnPeriod.ts` · `lib/marketDiscoveryCopyText.ts` 는 「ETF 구성종목」 복사문과 「후보리스트」 목록 넘기기의 [시스템 시장 판정] 글이 계속 써서 옮기지 않았다.
- 저장 기록의 출처 값(`source_screen = "market_discovery"` 등)은 기존 계약 그대로 둔다(판정 Q16 — 화면 글자만 새 메뉴 이름).
