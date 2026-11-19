# POC6-33 개발 결과서 — 보유 현황 · 종목 관리 · 확인 근거 · 데이터 상태 화면 정리

- 단계 ID: **POC6-33**(설계자 PLAN 판정 Q0 확정)
- 설계: `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_DESIGN_2026-11-18.md`(설계자 원본 이름 `HOLDINGS_UI_REVIEW_DEVELOPER_HANDOFF_2026-11-18.md` · 본문 원문 그대로)
- 설계자 PLAN 판정: `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_PLAN_DECISION_2026-11-18.md`(조건부 PASS · Q0 ~ Q54 반영 기준 · Q55 는 §5 별도)
- 개발 PLAN(V1 확정): `docs/ai_plan/POC6/POC6_33_HOLDINGS_UI_REVIEW_PLAN_V1.md`(§1 ~ §4 변경 표 H · M · E · D · §5 반영 확인 · §7 Q0 ~ Q55 · §9-1 개발자 적용 해석 I-1 ~ I-15 = RESULT 판정 §3 으로 확정 · §9-2 RESULT 판정 표시 보완)
- 목업: `docs/ai_plan/POC6/POC6_33_HOLDINGS_UI_REVIEW_MOCKUP.html`(RESULT 판정 표시 보완 · 상세 현재가 뺌 반영 · 보유 집계 N · M · ○)
- 설계자 RESULT 판정: `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT_DECISION_2026-11-19.md`(조건부 PASS · 처리 = §15) → 설계자 RESULT **PASS 확정**(2026-11-19 · §16)
- **코드 위치:** 격리 작업 사본 `/Users/hyungsookim/projects/krx_hyungsoo_wt_poc6_33` · 브랜치 `poc6-33-holdings-ui`(기준 main `e87ef4cc` · 처음 `e1ffa546` 에서 시작 · Q55 커밋 뒤 빨리 감기)에서 구현 → **구현 커밋 `7eb7cd0c`**(51파일) → main 빨리 감기 2026-11-19(§16).
- 격리 서버: 백엔드 8001(운영 state 사본 · ML 제외) · 화면 3001(작업 사본).
- **상태:** 설계자 RESULT 조건부 PASS(2026-11-19) → 보완 반영 · 확인 완료 → 설계자 RESULT **PASS 확정**(2026-11-19) → 구현 커밋 `7eb7cd0c` · main 반영 · 운영 화면(3000) 네 곳 확인 완료(2026-11-19 · §16). push · 격리 정리는 형수님 별도 승인 뒤다.
  - 지나온 단계: 갈래별 구현(D · H · M · E) → 통합 → 독립 검토 3관점 정정 → 형수님 격리 화면 확인(상세 현재가 뺌) → 검증자 r1 REJECTED(F1 · B-6) → r1 정정(§13) → 검증자 r2 VERIFIED(§14) → 설계자 RESULT 조건부 PASS → 판정 §1 ~ §3 표시 보완(네 갈래 · 통합 · 독립 검토 4건 정정) → 격리 화면 · 주간 두 화면 대조(§15)
  - 완료: 전체 백엔드 회귀 기록(§15-6) · 구현 커밋 · main 합치기 · PROGRAM_TRUTH 반영일 기록 · 운영 화면 확인(§16). 남은 일: push · 격리 서버 · 작업 사본 · 브랜치 정리(형수님 승인 뒤) · 종료 기록
- **보유 표기(공개 저장소 · RESULT 판정 §4-1):** 이 문서에는 보유 이름 · 코드 · 수량 · 가격 · 금액 · 계좌 이름 · 보유 행 수 · 종목 수 · 상태별 보유 건수를 쓰지 않는다. 종목 수 · 행 수는 N · M, 보유 한 종목은 '보유 A', 그 밖의 보유 집계 · 값은 '○'로 적는다. 날짜(10/19 · 10/21 · 10/22 · 11/18)와 시장 전체 건수(ETF 전체 NAV 행 등)는 그대로 적는다.

---

## 0. 요약

- **상태:** 설계자 RESULT 조건부 PASS(2026-11-19) → 보완 반영 · 확인 완료 → 설계자 RESULT **PASS 확정**(2026-11-19) → 구현 커밋 `7eb7cd0c` · main 반영 · 운영 화면(3000) 네 곳 확인 완료(2026-11-19 · §16). push · 격리 정리 = 형수님 승인 대기.
- **「보유 현황」:** 펼친 상세에서 요약 행과 겹치는 수량 · 평균 매입단가 · 현재가를 뺐다(현재가는 형수님 결정 2026-11-19 · RESULT 판정 §2-0 수용 · PLAN H1 · 목업도 이 결정으로 갱신). 상세 순서는 매입금액 → 평가금액 → 매입 기준 비중 → 가격 기준시각 · 출처다. 현재가는 요약 행 '매입 X → 현재 Y'(값 없음 '현재 미확인')에서 읽는다. 가격 기준시각은 '2026-11-18 15:54:12 KST · 네이버'처럼 초까지 한국 시각과 출처를 한 줄로 쓴다. 행 비중 이름은 '보유 내 비중(평가 기준)'이다. 배너는 '종목 N개 · 보유 행 M개'로 종목 수와 행 수를 나눈다. 자금 카드는 미입력이면 안내 한 줄 · 보유 평가액 · 가격 기준일 · [입력]만 보이고, 계좌별 비중 설명은 [자세히] 안으로 옮겼다. 'Naver' · '캐시'는 '네이버' · '저장'으로 바꿨다.
- **「종목 관리」:** 상단 [가격 비교 기준일 설정] 일괄 버튼을 내렸다. 상단 버튼은 [새 보유 추가] · [입력 정정] 둘이다. 일괄 창 파일은 `_orphaned/` 에 보관했다(삭제 없음). History 머리 줄 · 편집 라벨 · [시장 흐름 보기]의 이름 · 안내 · 기간 줄은 '비교 시작일'로 읽는다(서버 원문 · API 는 그대로 · 화면 사전으로 바꿔 읽음 · RESULT 판정 §2-2). 표 아래 건수는 '보유 행 M개'다(§2-3). 백엔드 다건 저장 경로와 저장된 날짜는 그대로이고, 이 결정을 KS-2 판정 기록에 남겼다.
- **「확인 근거」:**
  - 상세는 누른 행 바로 아래에 펼친다. 같은 행을 다시 누르면 닫히고, 위 상세가 닫혀 행이 밀려도 누른 행의 화면 위치를 지킨다.
  - 상세 순서: 가격 방향 → 주간 후보 여부 · 순위 → 필요한 자료 안내 → 가격 · 거래량 · 흔들림 + 날짜 역할 → 차트 → 주요 편입 · 구성종목 중복 → 순자산가치(NAV) 묶음
  - 주간 순위는 「주간 ETF 점검」과 같은 인자로 `GET /market/etf-compare/summary` 를 화면에 들어올 때마다 한 번 읽는다. 순위 줄은 '1개월 수익률 상위 30 중 n위' · '순위권 밖 · 1개월 수익률 상위 30 밖'이고, 규칙상 제외 · 자료 확인 불가 · 개별 주식은 각각의 사유로 보인다(RESULT 판정 §1).
  - 구성종목 중복은 '비교 범위 확인 불가'를 맨 앞에 두고, 별도 후보 목록의 기준 · 실제 비교 규칙 · 확인된 겹침(이름 · '이 ETF 편입 비중')을 적는다(§2-1).
  - 같은 뜻의 날짜는 '가격 기준일'로 맞췄고, 종목 자신의 마지막 날짜는 '마지막 저장일'(흔들림은 '마지막 유효 가격일')로 구별한다. 요약의 옛 '시장 기준일'은 '기존 후보 목록 기준일'이다(§2-6).
  - [세부 흐름 보기] 창 아래 거래량 줄은 비교 구간 · 유효 수만 보이고, 제공처 원문 'FinanceDataReader'는 그 창의 '세부 흐름' 도움말에서 읽는다(§2-4).
  - NAV 묶음은 시장가 · NAV · 괴리율 · 기준일 · 출처 · 수집 상태 여섯 칸이다. [전체 ETF NAV·괴리율 보기] 버튼은 뺐다.
- **「데이터 상태」:** 영어 · 기계 글자를 한국어로 바꿨다(수집됨 · 이전 목록 재사용 · 확인 불가 · 상태 확인 필요 / 네이버 · 기타 출처 / 재저장일). 요약 날짜 이름은 그 날짜에 재저장일 행이 있으면 '가장 최근 목록 날짜(재저장일 포함)', 없으면 '가장 최근 기준일'이다(RESULT 판정 §3 I-9). 요약 '기타' 건수는 필터 '기타'와 같은 판정 함수로 센다. 공용 낱말은 새 파일 `frontend/lib/navLabels.ts` 한 곳에 두었다.
- **검사(2026-11-19 · 판정 보완 뒤):** tsc 0 · PLAN §5 린트 `npm run lint`(화면 전체 · `eslint .`) exit 0 · eslint(바뀐 frontend ts/tsx 42파일) 0 · vitest 전체 99파일 1,979 통과(R4 반영 뒤) · 백엔드 black · flake8 · py_compile 통과 · pytest 대상 3파일 50 통과. 변이는 이전 110건 + 이번 55건 = **165건 모두 잡힘 · 놓친 것 0**. 자세한 값 = §15-6.
  - 전체 백엔드 회귀: 6,401 passed · 2 skipped · 1 warning(Starlette 지원 중단 경고) · exit 0 · 43분 42초 · 격리 사본 최종본(2026-11-19 · `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider` · `caffeinate -i`)
- **공개 문서 가림(RESULT 판정 §4-1):** PLAN · 목업 · STATE · KILL_SWITCHES · PROGRAM_TRUTH 의 실제 보유 집계를 N · M · ○ 또는 합성 예시로 바꿨다(§15-5).

## 1. 처리한 요구사항

### 1-1. PLAN 항목(§1 ~ §4)

| 항목 | 상태 | 반영(격리 사본 코드 확인) |
|---|---|---|
| H1 상세 순서 · 수량 · 평균 매입단가 제외 | DONE(현재가 줄은 형수님 결정으로 뺌 · RESULT 판정 §2-0 수용 · PLAN H1 · 목업 갱신) | `EnrichedHoldingsSection.tsx` `DetailRowFields` = 매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준시각 · 요약 행 '현재 미확인'은 그대로(§4 · §15) |
| H2 비중 이름 | DONE | 행 '보유 내 비중(평가 기준)' · 상세 '매입 기준 비중' · 자금 카드 부분 평가 문구도 같음 |
| H3 매입 기준 비중 값 없음 | DONE | null · 누락 → '비중 계산 불가'(`fmtPct(null)` = '0%' 라 먼저 거름) |
| H4 가격 기준시각 · 출처 한 줄 | DONE | `lib/holdings_view.ts` `priceSourceLabel` · `fmtKstSeconds` · `priceBasisText`(엄격 해석 `parseIsoInstant` 재사용 · 날짜만 → 날짜만 · 해석 실패 → '확인 불가' · 사전 밖 → '기타 출처') · 실화면 정정으로 이 줄만 `wide2`(§4) |
| H5 미확인 문구 | DONE(변경 없음) | '시세 미확인' · '현재 미확인' · '미확인' · '평가 불가' 그대로 |
| H6 종목 수 · 행 수 구별 | DONE | 배너 '종목 N개 · 보유 행 M개' · 부분 평가 다섯 곳 '행' · 계좌 머리 · 계좌 소계는 PLAN 대로 그대로. 「종목 관리」 표 아래도 '보유 행 M개'(RESULT 판정 §2-3 · §15) |
| H7 자금 카드 미입력 | DONE | 안내 한 줄 + 보유 평가액 · 가격 기준일 한 칸(`.cap-grid.one`) + [입력] · [비우기] 뒤도 같은 모양 |
| H8 입력됨 · 0원 · [자세히] | DONE | 칸 이름 · 0원 금액 표시 · 직접 입력 확인일 문장 그대로 · 계좌별 비중 설명은 [자세히] 안 맨 앞(보유가 있을 때만) |
| H9 '네이버' · '저장' | DONE | `HoldingsView.tsx` 버튼 · 버튼 설명 · 갱신 결과 줄(:125 · :123 · :97) · `EnrichedHoldingsSection.tsx` 목록 위 안내(:318-319) · 실패 사유 코드는 그대로 |
| M1 상단 일괄 버튼 제거 | DONE | `HoldingsBookSection.tsx` 상단 = [새 보유 추가] · [입력 정정] |
| M2 일괄 창 보관 | DONE | `git mv` → `_orphaned/ReferenceDateDialog.tsx`(상대 import 두 줄만 정정 · tsc 대상) · `_orphaned/README.md` 보관 사유 한 줄 |
| M3 '비교 시작일' | DONE | `ReferenceDateEditor.tsx` 머리 줄 · 편집 라벨 · 머리 주석. [시장 흐름 보기] 이름 · 안내 · 기간 줄 · 휴장 이동 글도 '비교 시작일'(RESULT 판정 §2-2 · 서버 원문 그대로 · 화면 사전 `historyText.ts` · §15) |
| M4 백엔드 주석 | DONE | `app/holdings_reference_date.py` docstring 만(동작 무변경) |
| M5 PROGRAM_TRUTH | DONE | POC6-33 줄을 한 가지 문자열 '`POC6-33` 반영 대기(격리 사본)'으로 표시(29회 · 18줄 · 2026-11-19 실측) · 합칠 때 이 문자열만 바꿈 |
| M6 KS-2 판정 기록 | DONE | `docs/KILL_SWITCHES.md` '#### KS-2 판정 기록 (2026-11-18, POC6-33 일괄 기준일 화면 경로)' · KS-2 자체는 바꾸지 않음 · 근거 줄의 보유 건수는 ○(RESULT 판정 §4-1) |
| E1 목록 위 요약 | DONE | `DeclineSummaryBlock.tsx` 머리 '현재 보유 점검 상태' · 세 칸 · '가격 기준일' 한 곳 · 보유 저장 시각(분 단위 한국 시각 · `today/todayHelpers.ts` `fmtKstDate` 재사용) · '기존 후보 목록 기준일'(옛 이름 '시장 기준일' · RESULT 판정 §2-6)은 가격 기준일과 날짜가 다르거나 가격 기준일을 모를 때만 보이고, 보일 때만 ? 도움말에 뜻 문단이 붙음(`DeclineSummaryBlock.tsx:24-28` · `:49`) |
| E2 행 단위 · 기간 | DONE | '최근 5저장일' · '20저장일' · '같은 기간 KODEX 200 대비(%p)' · '손익률(계좌 합산)' · '평가 비중(계좌 합산)' · 확인 사유 줄 · 정렬 이름 '5저장일 변화' · '20저장일 변화' |
| E3 누른 행 바로 아래 상세 | DONE | `.hre-row-wrap` · `aria-expanded` · 다시 누르면 닫힘 · 누르기 전 행 위치를 재고 그린 뒤 차이만큼 스크롤(가까운 스크롤 상자 `scrollTop` · 없으면 `window.scrollBy` · `HoldingsRiskEvidenceSection.tsx:114-123`) · 격리 실화면 실측(§8) |
| E4 방향 줄 · 세 묶음 | DONE | '최근 20저장일 ±x.xx%(올랐음/내렸음) · 같은 기간 KODEX 200 대비 ±x.xx%p' · 보이는 값 0.00 = '0.00%(변화 없음)' · 거래량 첫 칸 '평균 대비' · 흔들림 첫 칸 '직전 대비' · 세부 창 첫 줄(evidenceStrip) 제거 |
| E5 주간 순위 줄 | DONE(r1 F1 정정 · RESULT 판정 §1 이름) | 화면에 들어올 때마다 같은 키로 한 번 새로 읽음 · 이번 진입 조회 전 '불러오는 중' · 다시 읽기 실패(stale) = '조회 실패'(§13) · `WEEKLY_CHECK_CONDITION`(1개월 · 제외 4종 = `app/weekly_review.py` BASIS · FILTERS) · '1개월 수익률 상위 30 중 n위' · '순위권 밖 · 1개월 수익률 상위 30 밖'(기간 이름 = 응답 basis · `helpers.ts` `weeklyRankView` `listName`) · 두 줄에만 끝 가격 상태(장중 · 마감 미확인) · 규칙상 제외 · 저장 가격 없음 · 같은 기간 수익률을 구하지 못함 · 조회 실패 · 개별 주식 |
| E6 필요한 자료 안내 거르기 | DONE | `FILTERED_NOTES` 6문장 · `FILTERED_NOTE_PREFIXES` 2개 · 남는 것 = '단기 흐름은 데이터 부족으로 …'와 모르는 문장 · 백엔드 문장 대조 시험(EV-2 · r1 B-6 · §10 · §13) |
| E7 구성종목 중복 | DONE(RESULT 판정 §2-1 수용 · §15) | 맨 앞 '비교 범위 확인 불가' → '비교 후보 목록(주간 순위 목록과 별도): ' + 그 목록의 기간 · 제외 조건 → 실제 비교 규칙 글(EV-1) → 확인된 겹침 = 이름 · '이 ETF 편입 비중 x.xx%'(비중 없으면 이름만) · '중복 없음' · 건수 · 비율 없음 · PLAN E7 · I-4 · 목업도 이 규칙으로 갱신 |
| E8 주요 편입 | DONE | 상세를 열 때 `GET /market/constituents/summary?ticker=` 1회 · 그 자료의 구성 기준일 · 상태 글 |
| E9 날짜 역할 | DONE | '20저장일 수익률 = 시작 종가 → 끝 종가' · '[세부 흐름 보기] 차트 = 표시 기간 … · 최근 n개 저장일' · '거래량 평균 = 비교 구간 …'(응답 날짜만) |
| E10 NAV 묶음 | DONE | '순자산가치(NAV) · 괴리율' · 여섯 칸 · 괴리율 뜻은 ? 도움말 · 받은 원문 · 사전 밖 원문은 [자세히] · 'not_integrated' 표지는 출처 '-' |
| E11 이동 버튼 제거 | DONE | 버튼 · `onNavigate` 정리(`HoldingsEvidenceView.tsx` · `MainPanel.tsx`) · 「오늘의 투자 점검」 같은 버튼은 그대로 · `maintenanceQueue.ts` 주석 정정 |
| E12 개별 주식 | DONE | 요약 응답 `is_stock` · `out_reason 'stock'` 일 때 'ETF 순위 대상 아님(개별 주식)' · 'NAV·ETF 구성종목 해당 없음(개별 주식)' · 요약 조회 실패면 근거 응답대로 |
| D1 수집 상태 사전 · 요약 건수 | DONE | `statusGroup` 하나로 요약 · 필터를 셈 · 백엔드 `failed_count` 는 '기타'에 쓰지 않음 |
| D2 괴리율 표시 | DONE | '괴리 확인 필요(3% 이상)' · '괴리 주의(5% 이상)' · 기준 · 색 그대로 |
| D3 한국어 글자 | DONE | 제목 '데이터 상태' · 부제 첫 '순자산가치(NAV)' · 표 머리 · 고르기 · 정렬 · 검색 안내 · 빈 · 오류 카드 · 요약 날짜 이름('가장 최근 기준일' / '가장 최근 목록 날짜(재저장일 포함)' · RESULT 판정 §3 I-9 · `DataStatusView.tsx` `summaryDateLabel`) · '재저장일 날짜' |
| D4 출처 사전 | DONE | naver_etf_item_list → '네이버' · 사전 밖 '기타 출처' · null '-' |
| D5 뜻 두 줄 | DONE | 표 위 수집 상태 · 괴리율 표시 뜻 |
| D6 공용 표기 | DONE | `frontend/lib/navLabels.ts`(새 파일) · 「데이터 상태」 · 확인 근거 NAV 묶음 · `workbench/DetailNumbers.tsx` 가 같이 씀 · 괴리율 숫자 글자 `discountPctText` 도 여기(DS-2) |
| D7 화면 시험 새 파일 | DONE | `DataStatusView.test.tsx`(새 파일 · 471줄 · I-9 시험 포함) |

### 1-2. 설계자 PLAN 판정 묶음(판정 문서 §1 ~ §5)

| 판정 묶음 | 상태 | 비고 |
|---|---|---|
| §1 Q5 · Q9 · Q10 | DONE(상세 현재가는 형수님 결정으로 뺌 · RESULT 판정 §2-0 수용) | H1 · H3 · H5 |
| §1 Q4 · Q6 ~ Q8 · Q11 · Q12 | DONE | H2 · H4 · H6 · H9 · E1 · E2 |
| §1 Q13 ~ Q16 | DONE | H7 · H8 |
| §2 Q17 · Q46 | DONE | M1 · M2 · M6 |
| §2 Q18 ~ Q21 | DONE | M3 · M4 · '그래프 시작점' 정정은 PLAN · 목업에서 처리 · [시장 흐름 보기] 흐름 줄은 RESULT 판정 §2-2 로 '비교 시작일'(§15) |
| §3 Q22 · Q24 · Q49 · Q52 | DONE | E5 |
| §3 Q23 · Q28 · Q33 | DONE | E2 · E6 · E12 |
| §3 Q25 ~ Q27 · Q51 | DONE | E7 · E8 · E7 설명 글 = EV-1 · RESULT 판정 §2-1 수용(§15) |
| §3 Q29 ~ Q32 · Q47 · Q48 · Q50 | DONE | E1 ~ E4 |
| §3 Q34 ~ Q37 | DONE | E4 · E9 · E10 |
| §4 Q3 · Q53 · Q54 | DONE | E10 · E11 · D3 · D4 · H4 |
| §4 Q38 ~ Q42 · Q44 | DONE | D1 ~ D3 · D6 · E10 |
| §4 Q43 · Q45 | DONE | D1 · D7 |
| §5 Q0 ~ Q2 | DONE | 번호 · 상세 배치 · 순서 · 표기 |
| §5 PLAN §5 로 검증(격리 화면 동선) | DONE | 렌더 시험 · 개발자 격리 실화면(2026-11-18 · 2026-11-19) · 형수님 격리 화면 확인(보유 상세 · 2026-11-19) · 주간 두 화면 같은 시각 대조(§8-1 · §15-3 · §15-4) |
| §5 Q55 PROGRAM_TRUTH POC6-32 정정 단독 커밋 | DONE | main 커밋 `e87ef4cc`(`git show --stat` = `docs/PROGRAM_TRUTH.md` 한 파일 · 37 추가 37 삭제) · RESULT 판정에서 이 기록으로 수용 |

### 1-3. 설계자 RESULT 판정(2026-11-19 · 판정 §1 ~ §4)

| 판정 항목 | 상태 | 비고(자세히 = §15) |
|---|---|---|
| §1 순위 이름 · 진입마다 1회 조회 | DONE | '1개월 수익률 상위 30 중 n위' · '순위권 밖 · 1개월 수익률 상위 30 밖' · 조회는 r1 정정 그대로 |
| §2-0 보유 상세 한 줄 | DONE | 형수님 확인 완료 · PLAN H1 · 목업 갱신 |
| §2-1 구성종목 중복(EV-1 · I-4) | DONE | 순서 · 별도 후보 목록 기준 · '이 ETF 편입 비중' |
| §2-2 History 이름(I-2) | DONE | 화면 사전 · 서버 원문 그대로 · 공용 고정 자료 |
| §2-3 종목 관리 건수(H-1) | DONE | '보유 행 M개' |
| §2-4 거래량 출처(EV-3) | DONE | 창 아래 = 비교 구간 · 유효 수 · 원문 = 도움말(도움말은 흐름 점 1개 이상일 때만 · §5) |
| §2-5 추가 안내 문구 | DONE | r1 구현 그대로 |
| §2-6 남은 옛 표현 | DONE | 「확인 근거」 안 '가격 기준일' · '저장일' · 'KODEX 200' · '기존 후보 목록 기준일' · 서버 원문 거르기 상수는 원문 그대로 |
| §2-7 F1 | 종결 | §13 · §14 |
| §2-8 · §3 I-1 ~ I-15 | DONE | I-9 요약 날짜 이름을 새로 반영 · 나머지는 r1 구현 그대로 |
| §4-1 공개 문서 가림 | DONE | §15-5 |
| §4-2 최종 화면 확인 | DONE | §15-3 표(형수님 확인 · 개발자 확인 따로) · §15-4 주간 두 화면 대조 |
| §4-3 완료 검사 | DONE | 화면 관련 시험 · 타입 검사 · PLAN §5 린트(`npm run lint`) · vitest 전체 · 대상 pytest · 전체 백엔드 회귀(6,401 passed · 2 skipped) 모두 최종본에서 실행(§15-6) · 420px 가로 스크롤 · React `act` 경고는 §5 · §15-6 에 기록 |
| §4-4 결과 · 상태 갱신 | DONE | 판정서 보관 · 이 문서 §15 · `STATE_LATEST.md` POC6-33 줄 · PROGRAM_TRUTH 머리 · 반영일(main 반영 2026-11-19 · '최종 반영' 줄 · 본문 표시 '`POC6-33`(main 반영 2026-11-19)' · §16) |

## 2. 변경된 파일 목록

### 격리 작업 사본(기준 main `e87ef4cc` 대비 · 줄 수 = `git show HEAD:<경로> | wc -l` → `wc -l` 실측 · 2026-11-19)

`git diff HEAD --name-status` + 새 파일 실측 = **51경로**: 수정 46 · 이름변경 1 · 신규 4(r1 공용 고정 자료 · 이번 History 공용 고정 자료 포함). 아래 git 칸은 보고 직전 경로 하나씩 stage 한 뒤의 최종 상태다('M ' · 'A ' · 'R ' · 오른쪽 칸 공백 · '??' 0건 · stage 와 그 뒤 `git status --short --untracked-files=all` 확인은 main 세션 · `git add -A` · 폴더 add 안 씀).

| 파일 | git | 줄 수(전 → 후) | 항목 |
|---|---|---|---|
| `frontend/app/components/EnrichedHoldingsSection.tsx` | 'M ' | 735 → 746 | H1 ~ H4 · H6 · H9 · wide2 |
| `frontend/app/components/EnrichedHoldingsSection.eval.test.tsx` | 'M ' | 165 → 298 | H 시험 · 상세 현재가 없음 |
| `frontend/app/components/holdings/CapitalContextPanel.tsx` | 'M ' | 408 → 420 | H2 · H6 ~ H8 |
| `frontend/app/components/holdings/CapitalContextPanel.test.tsx` | 'M ' | 449 → 519 | H 시험(HoldingsView 렌더 시험 1개 포함) |
| `frontend/app/components/HoldingsView.tsx` | 'M ' | 166 → 166 | H9 |
| `frontend/lib/holdings_view.ts` | 'M ' | 186 → 232 | H4(새 함수 3개 · 기존 함수 무변경) |
| `frontend/app/components/holdings_manage/HoldingsBookSection.tsx` | 'M ' | 376 → 356 | M1 · RESULT §2-3 '보유 행 M개' |
| `frontend/app/components/holdings_manage/ReferenceDateEditor.tsx` | 'M ' | 109 → 111 | M3 |
| `frontend/app/components/holdings_manage/HistoryCycle.tsx` | 'M '(주석만) | 172 → 174 | M3 · I-2 주석 |
| `frontend/app/components/holdings_manage/MarketFlowPanel.tsx` | 'M ' | 206 → 208 | RESULT §2-2(이름 · 안내 사전 적용 · 기간 줄 · '설정한 비교 시작일') |
| `frontend/app/components/holdings_manage/historyText.ts` | 'M ' | 108 → 131 | RESULT §2-2 사전(`Map`) · `referenceFlowName` · `referenceNoteText` |
| `frontend/app/components/holdings_manage/MarketFlowPanel.test.tsx` | 'M ' | 130 → 213 | RESULT §2-2 시험 5개(고정 자료 대조 · History 패널 · 재진입 검토 창 · 사전 밖 원문 · 휴장 이동) |
| `frontend/app/components/holdings_manage/ReferenceDate.test.tsx` | 'M ' | 241 → 324 | M1 ~ M3 시험 · RESULT §2-2 흐름 줄 · §2-3 시험 1개 |
| `frontend/app/components/holdings_manage/ReferenceDateDialog.tsx` → `frontend/app/components/_orphaned/ReferenceDateDialog.tsx` | 'R '(+ import 두 줄 수정) | 146 → 146 | M2 |
| `frontend/app/components/_orphaned/README.md` | 'M ' | 16 → 17 | M2 |
| `frontend/app/components/HoldingsRiskEvidenceSection.tsx` | 'M ' | 490 → 680 | E1 ~ E12 · r1 F1 · RESULT §2-1 |
| `frontend/app/components/HoldingsRiskEvidenceSection.test.tsx` | 'M ' | 599 → 1155 | E 시험 · r1 F1 시험 4개 · RESULT §1 · §2-1 · §2-6 · R4 · act 정정 |
| `frontend/app/components/HoldingsRiskEvidenceDecline.test.tsx` | 'M ' | 699 → 770 | E 시험 · RESULT §2-4 창 시험 1개 · §2-6 · R4 |
| `frontend/app/components/holdings_risk_evidence/helpers.ts` | 'M ' | 333 → 618 | E2 · E4 ~ E10 · EV-1 · DS-2 · r1 F1(stale) · RESULT §1 `listName` · §2-1 `OVERLAP_LIST_PREFIX` · `overlapFoundText` |
| `frontend/app/components/holdings_risk_evidence/helpers.test.ts` | 'M ' | 428 → 721 | E 시험 · r1 F1 · r1 B-6 고정 자료 대조 · RESULT §1 · §2-1 |
| `frontend/app/components/holdings_risk_evidence/DeclineSummaryBlock.tsx` | 'M ' | 47 → 107 | E1 · RESULT §2-6 '기존 후보 목록 기준일' · 뜻 문단 |
| `frontend/app/components/holdings_risk_evidence/EvidenceGroups.tsx` | 'M ' | 116 → 121 | E4 · RESULT §2-6 · R4 묶음 아래 날짜 이름 |
| `frontend/app/components/holdings_risk_evidence/DetailFlowsBody.tsx` | 'M ' | 154 → 143 | E4 · E9 · RESULT §2-4 창 아래 거래량 줄 · 도움말 원문 |
| `frontend/app/components/holdings_risk_evidence/evidenceStrip.ts` | 'M ' | 72 → 20 | E4(창 첫 줄 함수 제거 · 파일 삭제 없음) |
| `frontend/app/components/holdings_risk_evidence/declineSummary.ts` | 'M ' | 113 → 113 | RESULT §2-6(사유 글 '이 종목 마지막 저장일' · '가격 기준일' · 'KODEX 200') |
| `frontend/app/components/holdings_risk_evidence/declineSummary.test.ts` | 'M ' | 301 → 302 | RESULT §2-6 |
| `frontend/app/components/holdings_risk_evidence/priceVolatility.ts` | 'M ' | 87 → 89 | RESULT §2-6('가격 기준일' · 공유 도움말 두 상수는 그대로) |
| `frontend/app/components/holdings_risk_evidence/priceVolatility.test.ts` | 'M ' | 139 → 144 | RESULT §2-6 |
| `frontend/app/components/holdings_risk_evidence/riskCombination.ts` | 'M ' | 172 → 172 | RESULT §2-6('KODEX 200') |
| `frontend/app/components/holdings_risk_evidence/riskCombination.test.ts` | 'M ' | 219 → 221 | RESULT §2-6 |
| `frontend/app/components/holdings_risk_evidence/volumeTrend.ts` | 'M ' | 26 → 26 | RESULT §2-6(도움말 '20거래일' → '최근 20개 저장일') |
| `frontend/app/components/holdings_risk_evidence/VolumeBars.test.tsx` | 'M ' | 90 → 93 | RESULT §2-6 도움말 단정 |
| `frontend/lib/priceBasis.ts` | 'M ' | 62 → 65 | E1 · E2 · RESULT §2-6 · R4 `priceFlowLine` |
| `frontend/lib/priceBasis.test.ts` | 'M ' | 63 → 68 | E 시험 · RESULT §2-6 · R4 · 합성 이름 |
| `frontend/lib/storedVolume.ts` | 'M ' | 62 → 71 | RESULT §2-4 `volumeProviderHelp` · §2-6 `pastVolumeNote` 이름 인자(기본값 = 옛 글) |
| `frontend/lib/storedVolume.test.ts` | 'M ' | 92 → 110 | RESULT §2-4 · §2-6 시험 2개 |
| `frontend/app/components/HoldingsEvidenceView.tsx` | 'M ' | 30 → 27 | E11 |
| `frontend/app/components/MainPanel.tsx` | 'M ' | 191 → 192 | E11 |
| `frontend/app/components/today/maintenanceQueue.ts` | 'M '(주석만) | 243 → 244 | E11 |
| `frontend/lib/navLabels.ts` | 'A ' | — → 94 | D6 · DS-2 |
| `frontend/app/components/DataStatusView.tsx` | 'M ' | 357 → 487 | D1 ~ D5 · DS-1 · DS-2 · RESULT §3 I-9 `summaryDateLabel` |
| `frontend/app/components/DataStatusView.test.tsx` | 'A ' | — → 471 | D7 · DS-1 · DS-2 · 라벨 줄바꿈 · I-9 시험 4개 |
| `frontend/app/components/workbench/DetailNumbers.tsx` | 'M ' | 155 → 152 | D6 |
| `frontend/app/globals.css` | 'M ' | 4356 → 4552 | H · D · E 화면 묶음 · wide2(RESULT 판정 보완에서는 바꾸지 않음) |
| `app/holdings_reference_date.py` | 'M '(docstring 만) | 160 → 163 | M4 |
| `tests/test_holdings_market_evidence.py` | 'M '(시험 1개 추가) | 444 → 524 | EV-2 · r1 B-6(고정 자료 읽기) |
| `tests/fixtures/poc6_33_filtered_notes.json` | 'A ' | — → 18 | r1 B-6(서버 · 화면 시험 공용 거르기 문장 · 합성 문장) |
| `tests/test_poc5_07_reference_date.py` | 'M '(시험 1개 + `import json`) | 673 → 697 | RESULT §2-2(서버 상수 · 실제 출력 ↔ 공용 고정 자료 · tmp 시세 DB) |
| `tests/fixtures/poc6_33_market_flow_labels.json` | 'A ' | — → 11 | RESULT §2-2(서버 글 · 화면 글 한 쌍씩 · 보유 자료 없음) |
| `docs/KILL_SWITCHES.md` | 'M ' | 214 → 224 | M6 · 근거 줄 보유 건수 가림(R3) |
| `docs/PROGRAM_TRUTH.md` | 'M ' | 1293 → 1299 | M5 · RESULT 판정 반영(`git diff --numstat HEAD` = 18 추가 · 12 삭제 · POC6-33 만) |

- PLAN §6 에 있었지만 바꾸지 않은 파일: `HoldingsOverlapBridgeCard.tsx`(`topnBasisText` import 만).
- 무변경 확인(2026-11-19): `git diff HEAD --stat` 이 `app/holdings_market_evidence.py` · `app/etf_constituents_analysis.py` · `app/pc_price_basis.py` · `app/api_nav_discount.py` · `app/market_topn.py` · `app/api_weekly_review.py` · `app/stored_volume_evidence.py` · `app/holdings_capital.py` · `app/holdings_market_flow.py` · `app/api.py` · `frontend/app/components/HoldingsOverlapBridgeCard.tsx` · `frontend/app/components/StoredVolumeBlock.tsx` 에 대해 빈 출력. `app/` 아래 바뀐 파일은 `app/holdings_reference_date.py`(주석) 하나다. 백엔드 쪽 나머지 변경은 시험 2파일 · 고정 자료 2파일이다.
- 배포 영향(DEV_RULES 2.3): 저장소에 Dockerfile 이 없다. `deploy/` 에는 옮긴 파일 · 새 파일 경로를 가리키는 곳이 없다(grep 0건).

### main 저장소(문서 · 커밋 전)

| 파일 | 구분 · git(stage 뒤 최종) | 줄 수(`wc -l` · 2026-11-19) |
|---|---|---|
| `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_DESIGN_2026-11-18.md` | 신규 · 'A ' | 54 |
| `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_PLAN_DECISION_2026-11-18.md` | 신규 · 'A ' | 43 |
| `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT_DECISION_2026-11-19.md` | 신규 · 'A '(설계자 RESULT 판정 보관) | 61 |
| `docs/ai_plan/POC6/POC6_33_HOLDINGS_UI_REVIEW_PLAN_V1.md` | 신규 · 'A '(RESULT 판정 보완 · 가림 · §9-2) | 319 |
| `docs/ai_plan/POC6/POC6_33_HOLDINGS_UI_REVIEW_MOCKUP.html` | 신규 · 'A '(RESULT 판정 보완 · 가림) | 759 |
| `docs/STATE_LATEST.md` | 수정 · 'M '(POC6-33 줄만) | 3340(`git diff --stat HEAD` = POC6-33 19줄 추가) |
| `docs/PROGRAM_TRUTH.md`(main · 구현 커밋 뒤 반영일 기록) | 수정 · 'M ' | 1299(19 추가 · 19 삭제 · §16) |
| `docs/ai_result/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT.md` | 신규(이 문서) · 'A ' | — |

- 형수님 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 는 추적 안 됨 그대로(stage 하지 않음 · main 저장소의 '??' 는 이 한 줄만).

## 3. 신규 추가된 의존성
- 없음

## 4. 지시문 외 변경

- **검토 정정(§10)으로 생긴 것**
  - 구성종목 중복 설명 글 `OVERLAP_CAP_TEXT` 를 실제 builder 규칙으로 바꿈(EV-1). 확정 PLAN I-4 · 목업 E7 의 첫 글과 달랐고, RESULT 판정 §2-1 이 이 규칙을 수용해 PLAN E7 · I-4 · 목업을 이 규칙으로 갱신했다.
  - 백엔드 시험 `tests/test_holdings_market_evidence.py::test_builder_notes_match_shared_filter_fixture` 추가(EV-2 · r1 B-6 로 고정 자료 방식으로 바꿈). 공용 고정 자료 `tests/fixtures/poc6_33_filtered_notes.json` 의 거르기 문장 · 앞부분 · 남기는 문장을 builder `_build_evidence_notes` 의 상태 조합 4 × 3 × 4 × 3 = 144가지 문장과 대조한다(순수 함수 · DB 열지 않음). 화면 상수 ↔ 같은 고정 자료 대조는 `helpers.test.ts` 가 한다(POC6-32 `marketCommonEvidenceCases.test.ts` 방식).
  - 괴리율 숫자 글자를 공용 `navLabels.discountPctText` 하나로 모음(DS-2). 「데이터 상태」의 옛 `fmtPct` 와 확인 근거의 `fmtDiscount` 는 없앴다.
  - 「데이터 상태」 기준일 칸에 `white-space: nowrap`(DS-1).
- **형수님 격리 화면 확인(2026-11-19)으로 바꾼 것**
  - 「보유 현황」 펼친 상세의 현재가 줄을 뺐다. 요약 행에 '매입 X → 현재 Y'(값 없음 '현재 미확인')로 이미 있는 값이라는 형수님 의견 · 결정. RESULT 판정 §2-0 이 수용했고, PLAN H1 · 목업을 이 결정으로 갱신했다. 1440 폭에서 상세가 한 줄(§8). 시험 6곳을 '상세 현재가 없음'으로 고침 · 변이 M11(현재가 줄 되살림) 잡힘(실패 6). PROGRAM_TRUTH §5.2 holdings 줄도 같이 고침.
- **개발자 격리 화면에서 찾아 고친 것**
  - 「보유 현황」 상세 '가격 기준시각' 값 '… KST · 네이버'가 200px 칸 하나에 들어가 3줄로 꺾이고 '네 / 이버'로 낱말 중간에서 끊겼다. 목업의 `li.wide2` 를 따라 그 항목에 `wide2` class 를 주고 `globals.css`(:1131-1138)에 `ul.detail-fields li.wide2 .v { word-break: keep-all }` · `@media (min-width: 900px) { ul.detail-fields li.wide2 { grid-column: span 2 } }` 를 넣었다. span 을 900px 이상에서만 쓰는 이유는 한 열 격자에서 span 2 가 가로로 넘치기 때문이다. 시험 = `EnrichedHoldingsSection.eval.test.tsx`.
  - 「데이터 상태」 조회 옵션 라벨 '검색'이 '검 / 색'으로 세로로 꺾였다. 세 라벨(검색 · 수집 상태 · 정렬)에 인라인 `whiteSpace: "nowrap"` 를 넣었다. 시험 = `DataStatusView.test.tsx`.
- **RESULT 판정 보완(2026-11-19)에서 판정 글보다 더 한 것**
  - 「확인 근거」 묶음 아래 날짜 이름(R4 · §15-5): 판정 §2-6 은 '가격 기준일'을 가리키는 낱말을 맞추라고 했다. 종목 자신의 마지막 날짜가 한 상세 안에서 '이 종목 마지막 저장일'과 맨 '기준일'로 섞여 보여, 묶음 아래 · [세부 흐름 보기] 흐름 줄도 '마지막 저장일 D'(흔들림 '마지막 유효 가격일 D')로 맞췄다.
  - 공유 함수는 다른 화면 글을 지키도록 바꿨다: `pastVolumeNote` 에 셋째 인자 이름(기본값 = 「오늘의 투자 점검」 옛 글 그대로), 제공처 문단은 새 함수 `volumeProviderHelp`. 「보유와 후보 비교」가 쓰는 `VOL_HELP_MEANING` · `VOL_HELP_BASIS` 와 「오늘의 투자 점검」이 쓰는 `volumeSourceParts` 출력은 그대로.
  - '기존 후보 목록 기준일'의 뜻은 별도 ? 를 만들지 않고 기존 요약 머리 ? 도움말 끝 문단으로 붙였다(그 날짜가 보일 때만).
  - History 사전은 일반 객체 대신 `Map` 으로 만들었다(서버 글이 'constructor' 같아도 객체 속성을 읽지 않음). 서버 상수 ↔ 화면 사전 대조를 위해 공용 고정 자료 `tests/fixtures/poc6_33_market_flow_labels.json` 과 서버 시험 `test_reference_texts_match_shared_label_fixture` 를 더했다(r1 B-6 과 같은 방식).
  - 「데이터 상태」 요약 날짜 이름 판정은 행 날짜 칸과 같은 공용 사전(`navDateLabel(status) === '재저장일'`)을 쓴다. 기존 시험 1건의 기대값이 바뀌었다(고정 자료 최댓값 날짜에 재저장일 행이 있어 '요약 — 날짜 · 출처'로 이름을 바꿈).
  - `priceBasis.test.ts` 에 있던 실제 상장 종목 이름 · 코드 두 줄과 `priceBasis.ts` 주석의 실제 종목 이름 예시를 합성 값으로 바꿨다.
  - 보유 건수 가림을 PLAN · 목업 · STATE 밖으로도 넓혔다: `docs/KILL_SWITCHES.md` KS-2 근거 줄(R3) · `docs/PROGRAM_TRUTH.md` '지금 일괄 대상' 줄.
  - 시험 정리: `HoldingsRiskEvidenceSection.test.tsx` 'E3 · 판정 Q30' 시험의 마지막 클릭을 `act` 안에서 기다리고 '주요 편입' 줄이 다 읽혔는지 단정을 하나 더했다(React `act` 경고 1줄 제거 · 동작 무변경).
  - 목업: 「데이터 상태」 요약 날짜 이름 예시 상자 추가 · 좁은 폭에서 긴 파일 경로가 넘치지 않게 CSS 한 줄(`.note code { overflow-wrap:anywhere }`).
- **갈래 · 통합에서 PLAN 보다 더 한 것(r1 이전)**
  - H: 한쪽 값만 없을 때 규칙(시각 없음 + 출처 있음 → '확인 불가 · 네이버' · 출처 없음 → 시각만) · `HoldingsView` 렌더 시험 1개를 기존 `CapitalContextPanel.test.tsx` 에 더함.
  - M: `HistoryCycle.tsx` 머리 주석(동작 무변경) · `HoldingsBookSection.tsx` 머리 주석을 지우는 대신 현재 동작 2줄로 바꿈 · `_orphaned/README.md` 표 머리를 '사유 (출처 = 사유 앞에 적은 단계 · 적지 않은 행은 POC3-05 DESIGN_V2)'로 고침(:8) · 잔고 등록 기간 '비교 시작일: 없음 → 설정 → 다시 읽기' 시험 1개 추가(가상 자료).
  - D: 괴리율 숫자 색 함수를 「데이터 상태」의 옛 `pctColor` 에서 공용 `navLabels.ts` `discountRateColor` 로 옮김(색 규칙 그대로 · 확인 근거 NAV 묶음도 씀). 같은 파일의 `navDateLabel` · `navDateCell`(PLAN D6 '재저장일 판정') · `isKnownNavStatus` · `isKnownNavSource` · `isKnownDiscountFlag`(D6 '사전 밖 글' 판정)는 PLAN 범위 안이다. 그 밖에 사전 밖 괴리율 표시 원문도 [자세히]에 · 불러오기 실패 카드 = 쉬운 결론 + 원문은 [자세히] · 건수 쉼표 · 열 폭(기준일 140 · 출처 100 · 수집 상태 130) · `data-testid` 4개.
  - E: 새 파일 없이 상세 함수를 `HoldingsRiskEvidenceSection.tsx` 안에 둠(680줄 · 근접 850 아래) · 기간 다름 문장(`windowMismatchText` · `WINDOW_MISMATCH_OTHER_TEXT`)도 저장일 · KODEX 200 으로 · 보조 줄에 기존 '구간 판정 가능 a/b' 남김 · PLAN 에 없던 갈래 글(요약 status 가 ok 아님 · 응답에 그 종목 없음 · 보유 목록 읽기 실패 · 조회 중 · 구성 자료 불러오는 중 · 조회 실패 · 미수집 · 시장 자료 파일 없음 · RESULT 판정 §2-5 수용) · NAV 도움말 3문단 새로 씀 · 방향 줄 KODEX 200 대비 0.00 = '0.00%p' · 날짜 역할 · 순위 날짜는 M/D · 기존 시험 '저장 버튼 없음' 단정을 `/저장(?!일)/` 로 좁힘(정렬 버튼 '5저장일 변화'와 겹침).
  - 통합: 세 갈래 CSS 를 `globals.css` 의 관련 규칙 옆 세 묶음으로 합침 · `MainPanel.tsx` 의 `onNavigate` 넘기기 제거 · `maintenanceQueue.ts` 주석.

## 5. 알려진 한계 / 미완성

- **남은 일:** push · 격리 서버 · 작업 사본 · 브랜치 정리(형수님 승인 뒤). 전체 백엔드 회귀 기록(§15-6) · 커밋 · main 반영 · 운영 화면 확인(§16)은 완료.
- **좁은 화면:** 420px 폭에서 모든 화면에 가로 스크롤이 있다(바꾸지 않은 「오늘의 투자 점검」 scrollWidth 506 · 보유 현황 457 · 확인 근거 425 · 종목 관리 478 · 데이터 상태 표 962 · 2026-11-18 실측). 앱 전체 옆 메뉴 배치 때문이고 POC6-33 이 만든 것이 아니다.
- **React `act` 경고:** main `e87ef4cc` 의 전체 vitest 로그에 'not wrapped in act' 31줄이 원래 있다. 이 작업 사본은 32줄이었고, 늘어난 1줄(`HoldingsRiskEvidenceSection.test.tsx` 'E3 · 판정 Q30' 시험의 주요 편입 줄)은 고쳐 그 파일 0줄이다(이 문서 작성 때 그 파일만 다시 돌려 0줄 · 38 passed 확인). 최종 전체 수 = §15-6. 실패가 아니라 경고다.
- **[세부 흐름 보기] 제공처 원문:** 그 창의 '세부 흐름' 도움말은 거래량 흐름 점이 1개 이상일 때만 그려진다(`DetailFlowsBody.tsx` · 흐름 점 0개 갈래에는 도움말 없음). 저장 거래량은 있는데 흐름 점이 없으면 창 아래 비교 구간 · 유효 수는 보이지만 원문 'FinanceDataReader'를 그 창에서 볼 곳이 없다.
- **다른 화면의 거래량 출처:** 「오늘의 투자 점검」 KODEX200 거래량 칸(`StoredVolumeBlock.tsx` · `today/KospiHeadline.tsx` · 공유 `volumeSourceParts`)은 '출처 FinanceDataReader'를 그대로 보인다. 이 칸은 KODEX 200 ETF 한 종목의 거래량이다(코스피 시장 전체 거래량 아님 · `lib/storedVolume.ts` `KODEX200_VOLUME_HELP`). RESULT 판정 §2-4 는 [세부 흐름 보기]만 다룬다.
- **서버 원문 그대로 보이는 것:** 「확인 근거」에서 거르지 않는 서버 `evidence_notes` 문장(모르는 문장)은 원문 그대로 보이고, 그 안의 'KODEX200'은 띄어쓰기 없이 보일 수 있다. History · 확인 근거 · 데이터 상태 모두 사전에 없는 서버 글은 원문 그대로 보인다.
- **'시장 국면 N거래일째':** 저장일 수가 아니라 시장 국면이 이어진 날수라 그대로 두었다(다른 화면과 같은 글 · 갈래 조사 6곳).
- **재진입 검토 창:** [시장 흐름 보기]의 '비교 시작일' 바꿔 읽기는 같은 `MarketFlowView` 를 쓰는 재진입 검토 창(History 에서 여는 창)에도 적용된다.
- **「확인 근거」 안 화면 글의 옛 낱말:** 「확인 근거」 화면 글의 'PC 가격 흐름 기준일' · 'PC 비교 기준일' · 'KODEX200' · '20거래일'은 정리됐다. 그 화면 파일에서는 주석에만 남는다(`declineSummary.ts:84-85` · `DeclineSummaryBlock.tsx:8` · `HoldingsRiskEvidenceSection.tsx:96` · `:444` · `helpers.ts:5` · `:278` · `:306` · `:356`). `helpers.ts:362` 거르기 접두어 '20거래일 KODEX200 대비 …'는 서버 원문과 대조하는 상수라 원문 그대로여야 한다.
  - 이 범위 밖에는 남는다. 공유 코드 `lib/storedVolume.ts:58` `pastVolumeNote` 의 기본 이름 'PC 비교 기준일'은 주석이 아니라 코드다. 「오늘의 투자 점검」 `StoredVolumeBlock` 이 쓰는 기본값이고, 지금은 `today/KospiHeadline.tsx` 가 기준일(referenceDate)을 넘기지 않아 화면에 나오지 않는다. 「확인 근거」는 '가격 기준일'을 넘긴다(`EvidenceGroups.tsx:36`).
  - 「오늘의 투자 점검」 칸 제목 'KODEX200 거래량'(`today/KospiHeadline.tsx:99`)은 다른 화면 글이라 바꾸지 않았다.
- **I-5 결과서 목록(같은 NAV 원문이 남는 다른 곳 · 바꾸지 않음):** `frontend/app/components/NavDiscountPlaceholderCard.tsx` · `frontend/lib/marketDiscoveryCopyText.ts:349-358`(AI 복사 글) · `frontend/app/components/_orphaned/HoldingsMarketEvidenceCard.tsx`.
- **화면에 보이지 않는 주석의 옛 낱말:** `HoldingsView.tsx:10` '시세 갱신(Naver)' · `:11` · `:59` · `:71` '캐시'.
- **「보유 현황」 계좌 머리 'N종목' · 계좌 소계 'a/b종목 기준'**(`EnrichedHoldingsSection.tsx:558` · `:593`)은 PLAN 대로 그대로라 배너의 '행'과 낱말이 다르다.
- **'기존 후보 목록 기준일':** 응답 `market_asof` 는 구성종목 중복 비교에 쓰는 옛 상위 목록(top-N) 응답의 asof 다(`app/holdings_market_evidence.py:488`). 가격 기준일과 날짜가 다르거나 가격 기준일을 모를 때만 보인다(값이 없으면 보이지 않음).
- **누른 행 위치 유지:** jsdom 은 배치를 계산하지 않는다. 시험은 `getBoundingClientRect` 를 대신 주어 `scrollBy` 값만 확인한다. 실제 동작은 격리 실화면 실측으로만 확인했다(§8).
- **괴리율 반올림 경계(DS-3 · 변경 전 동작 · 판정 기준 그대로):** 표시 · 색은 반올림 전 값의 절대값으로 정한다. 그래서 4.996 은 '+5.00%' 인데 '괴리 확인 필요(3% 이상)'가 붙는다. 격리 자료 1,212행 가운데 반올림으로 구간이 달라지는 행은 0건이다.
- **배지 색:** PLAN D1('배지 색 그대로')에 따라 원값 기준 기존 class 를 쓴다. 그래서 '확인 불가'는 회색이고, 목업 그림(빨강)과 다르다.
- **쓰지 않게 된 CSS(지우지 않음):** `.hre-summary` · `.hre-detail` · `.hre-detail-hint` · `.hre-detail-evidence` · `.hre-risk-row` · `.hre-risk-row .k` · `.dfw-strip` · `.dfw-strip-line` · `.dfw-strip-k` · `.dfw-strip-date` · `.dfw-strip-v` · `.dfw-strip-note`(통합 단계 전수 비교).
- **PROGRAM_TRUTH 옛 이력 줄:** 머리 이력의 지난 기록(POC5-09 · POC5-13 · POC5-15 · POC5-UI-02)에는 옛 낱말이 남아 있다. 문서 관례(지난 기록은 고치지 않음)를 따랐다. §5.1 · §5.2 의 POC6-33 표시가 우선한다고 적었다.
- **`api_nav_discount.py:143`** 주석 '가장 흔한 값 사용' ↔ 코드 = 최댓값(`max(asof_values)` · :145). PLAN M4 대로 결과서 기록만 하고 고치지 않았다.
- **오래된 주석(범위 밖):** `declineSummary.ts` · `riskCombination.ts` 머리 주석에 '오늘 점검 띠와 같은 함수'라는 설명이 있지만, 지금 「오늘의 투자 점검」에서 `riskCombination` 을 가져다 쓰는 곳은 0건이다(사용처 = 「확인 근거」 세 파일).

## 6. 다음 검증자(Codex)에게 알릴 점

- **stage 상태:** 격리 사본 51경로(수정 46 · 이름변경 1 · 신규 4 = `frontend/lib/navLabels.ts` · `frontend/app/components/DataStatusView.test.tsx` · `tests/fixtures/poc6_33_filtered_notes.json` · `tests/fixtures/poc6_33_market_flow_labels.json`)와 main 저장소 문서 7건을 보고 직전 경로 하나씩 stage 한다(main 세션 · `git add -A` · 폴더 add 안 씀). `tests/test_poc5_07_reference_date.py` 와 `MarketFlowPanel.test.tsx` 는 새 고정 자료를 모듈을 읽을 때 연다. 고정 자료가 stage 에서 빠지면 두 시험 파일이 통째로 실패한다(독립 검토 R1).
- **백엔드 변경 = 주석 1곳 + 시험 2개(두 파일) + 고정 자료 2개.** 두 서버 시험은 프론트 소스를 읽지 않는다. 화면 상수 · 사전과 고정 자료의 대조는 프론트 시험이 한다(`helpers.test.ts` · `MarketFlowPanel.test.tsx`). 서버 글 · 고정 자료 · 화면 글 중 하나만 바뀌면 서버 또는 화면 시험이 깨진다(변이 B6-a ~ f · §13 · 갈래 B F1 ~ F4 · S1 · S2 · §15-6).
- **판정 §2-6 의 범위를 넓게 읽은 곳(R4):** 판정 글은 '가격 기준일'을 가리키는 낱말만 말한다. 같은 상세에서 종목 자신의 마지막 날짜가 두 이름으로 보여, 묶음 아래 · 흐름 줄까지 '마지막 저장일 D'로 맞췄다. 가격 흔들림은 거른 뒤 마지막 유효 가격일(`price_volatility.end_date`)이라 다른 날일 수 있어 '마지막 유효 가격일'로 둔다. `priceFlowLine` 사용처는 `DetailFlowsBody.tsx` 하나(「확인 근거」)다.
- **공유 함수 보호:** `pastVolumeNote` 기본값 · `volumeSourceParts` · `VOLUME_HELP` · `KODEX200_VOLUME_HELP` · `VOL_HELP_MEANING` · `VOL_HELP_BASIS` 는 다른 화면 글 그대로다. 갈래 A 가 사용처를 grep 하고 그 공유 함수를 쓰는 다른 화면 시험(「오늘의 투자 점검」 · 「보유와 후보 비교」 미리보기 등)을 같이 돌렸다. 전체 vitest 도 통과했다(§15-6).
- **구성종목 중복 비중의 뜻:** '이 ETF 편입 비중'은 builder `_build_constituents_overlap` 의 `weight_pct` = 보유 ETF 자신의 구성 행 비중이다(갈래 A · 통합에서 코드 확인). 목록 머리에 '30개' 숫자는 넣지 않았다(서버 `LIST_N` 을 코드에 다시 적지 않기 위해 '주간 순위 목록과 별도'로만 적음).
- **I-11 ④:** NAV 행이 없는 ETF 의 builder 표지 출처 'not_integrated' 는 공용 사전이 아니라 `helpers.ts` `navCells` 에서 null 로 바꿔 '-'로 보인다.
- **PROGRAM_TRUTH:** 격리 사본에서는 POC6-33 줄을 '`POC6-33` 반영 대기(격리 사본)' 한 가지 표시(29회 · 18줄 · numstat 18 추가 · 12 삭제)로 적었다. main 반영 때(2026-11-19) 머리 줄을 '최종 반영 2026-11-19 · 구현 커밋 7eb7cd0c'로, 본문 표시 28곳을 '`POC6-33`(main 반영 2026-11-19)'로 바꿨다(남은 '반영 대기(격리 사본)' 0건 · §16).
- **목업과 코드의 작은 차이:** 목업 「확인 근거」 거래량 · 흔들림 묶음 아래에는 '· 비교 구간 10/21 ~ 11/17' · '· 최근 구간 10/21 ~ 11/18'이 더 적혀 있다(그림 설명 · 이번 보완 전부터 있던 글). 코드 묶음 아래는 날짜 이름 + 날짜만 보이고, 구간은 날짜 역할 줄 · [세부 흐름 보기] 창 아래 줄에서 읽는다.
- **변이 표식:** 갈래 변이 실행이 격리 dev 서버(3001)의 지난 HMR 조각(`.next/static/webpack/app/*.hot-update.js`)에 표식을 남겼다. 소스(`frontend/app` · `frontend/lib` · `tests` · `app`)와 현재 결과물(page.js · server)은 0건이다(통합 단계 grep). 저장소 밖 빌드 산출물이다.
- **크기(KS-10):** 화면 컴포넌트 최대 `EnrichedHoldingsSection.tsx` 746 · `HoldingsRiskEvidenceSection.tsx` 680 · `DataStatusView.tsx` 487 · `CapitalContextPanel.tsx` 420 · `HoldingsBookSection.tsx` 356 · `MarketFlowPanel.tsx` 208(모두 근접 850 아래). `holdings_risk_evidence/helpers.ts` 는 333 → 618줄로 순수 함수가 늘었다. 시험 최대 `HoldingsRiskEvidenceSection.test.tsx` 1,155(1,500 아래). 백엔드 시험 `tests/test_poc5_07_reference_date.py` 697 · `tests/test_holdings_market_evidence.py` 524.
- **검사:** 전체 백엔드 회귀는 최종본에서 1회 돌렸다(6,401 passed · 2 skipped · §15-6). PLAN §5 의 화면 전체 린트(`npm run lint` = `eslint .`)도 최종본에서 exit 0(§15-6). 남은 검사 없음(커밋 뒤 운영 화면 확인은 별도).

## 7. 사용자 확인이 필요한 항목

- **형수님 확인 결과(2026-11-19 · 격리 화면) — 기록 완료:**
  - 「보유 현황」 상세 현재가 = 요약 행과 반복 → **뺌**(설계자 RESULT 판정 §2-0 수용).
  - 「확인 근거」 목록 순서가 「후보리스트」 선정 순서와 다르다는 의견 → **지금처럼 둠**. 설계자 판정 §1 이 두 순서를 설명했다(「후보리스트」 = 고른 기간 하나의 가격 수익률 · 「확인 근거」 = 보유 목록 기본 '5저장일 변화' 순 + 행을 펼치면 「주간 ETF 점검」과 같은 조건의 순위 · 상태).
  - 추가매수 부분 = 형수님 확인함.
  - 형수님 확인 · 개발자 확인 구분 표 = §15-3.
- **커밋 · main 합치기 · push:** 형수님 승인 뒤(전체 백엔드 회귀는 최종본에서 통과 · §15-6). 운영 화면 확인과 격리 정리(서버 · 작업 사본 · 브랜치 삭제는 형수님 승인)까지 끝나면 종료를 기록한다.
- **보관 파일:** `frontend/app/components/_orphaned/ReferenceDateDialog.tsx` 는 지우지 않고 보관했다(삭제는 형수님 판단).
- **420px 가로 스크롤:** 앱 전체 배치 문제로 모든 화면에 있다(§5). 이번 범위 밖이다.
- **공개 저장소 보유 정보:** PLAN · 목업 · STATE · KILL_SWITCHES · PROGRAM_TRUTH 의 실제 보유 집계는 이번에 가렸다(§15-5). 기존 화면 시험 자료(`EnrichedHoldingsSection.eval.test.tsx` · `CapitalContextPanel.test.tsx` 의 일부 입력)에는 실제 상품 이름 · 코드 모양 값이 남아 있다(POC6-33 이 넣은 것 아님 · 새로 넣은 시험 자료는 '보유 A' · 'TEST01' 같은 합성값 · `priceBasis.test.ts` 의 실제 이름 두 줄은 이번에 합성값으로 바꿈).

## 8. 실측(2026-11-18 · 격리 서버 8001 · 화면 3001 · GET 만)

- 실화면 확인 중 8000 · 3000 으로 나간 요청은 보지 못했다(main 세션 관찰).
- **「확인 근거」:**
  - 상세가 누른 행의 묶음(`.hre-row-wrap`) 안에 열린다.
  - 위치 유지: 위쪽 행 상세를 연 채 아래쪽 행을 누르기 전 · 뒤 그 행 top 447 → 447.
  - 같은 행을 다시 누르면 닫힌다.
  - 상세 안 '[전체 ETF NAV…]' 버튼 0개 · NAV 묶음 6칸.
  - 순서: 방향 → 주간 후보 여부 · 순위 → (필요한 자료 안내) → 가격 흐름 · 거래량 · 가격 흔들림 → 날짜 역할 → 차트 → 주요 편입 → 구성종목 중복 → NAV.
  - 날짜 역할: 20저장일 수익률 = 시작 종가 10/21 → 끝 11/18 · 차트 표시 기간 10/22 ~ 11/18 · 거래량 평균 비교 구간 10/21 ~ 11/17.
- **「보유 현황」 가격 기준시각 줄(정정 뒤):** 1440 · 1100 · 900 폭에서 1줄.
- **「보유 현황」 상세 한 줄(현재가 뺀 뒤 · 2026-11-19):** 항목 4개 · 1440 폭 격자 5열(가격 기준시각 두 칸 폭) → 1줄 · 1680 · 1920 폭 1줄 · 1280 폭은 격자 4열이라 2줄(뺀 앞은 1440 에서 2줄 · 현재가가 둘째 줄).
- **「데이터 상태」:**
  - 기준일 칸(DS-1 정정 뒤): GET 가로채기로 200행을 이전 목록 재사용(partial)으로 바꿔 그림 → 1280 · 1440 · 1920 폭에서 1줄 · 칸 폭 153px.
  - 조회 옵션 라벨(정정 뒤): 1100 · 1440 폭에서 1줄.
  - 검토 단계 실측: 격리 응답 1,212행 모두 수집됨 · 그중 18행이 −0.005 < 괴리율 < 0(정정 전 「데이터 상태」 '-0.00%' · 확인 근거 '0.00%') · 정정 뒤 두 화면 같은 함수(`navLabels.discountPctText`) = 시험으로 확인(`DataStatusView.test.tsx` · `helpers.test.ts` · 실화면 재측정 없음).
- **420px 폭:** 모든 화면 가로 스크롤(§5).
- RESULT 판정 보완 뒤 실측(2026-11-19)은 §15-3 · §15-4.

### 8-1. PLAN §5 반영 확인 표의 상태

| 설계 §5 동선 | 렌더 시험 | 개발자 격리 실화면 | 형수님 확인 |
|---|---|---|---|
| 보유 현황 요약 · 행 펼침 | 있음(미입력 · 0원 · 입력 · 부분 · 시각 형식 · 매입 비중 null · 사전 밖 출처 · wide2 · 상세 현재가 없음) | 가격 기준시각 줄 1줄 · 상세 4항목 1440 폭 1줄(§8) | **완료(사용자 확인 · 2026-11-19 · 상세 현재가 뺌 결정 · 추가매수 부분 확인)** |
| 종목 관리 · 보유 이력 | 있음(상단 두 버튼 · '비교 시작일' · 없음 → 설정 · [시장 흐름 보기] '비교 시작일' · 사전 밖 원문 · '보유 행 2개') | 표 아래 '보유 행 M개' · History 머리 '비교 시작일' · [시장 흐름 보기] '비교 시작일부터 종가 변화' · 창 안 '가격 비교 기준일' 0회(2026-11-19 · §15-3) | — (개발자 확인) |
| 확인 근거 보유 ETF 선택 | 있음(행 아래 상세 · 순서 · 날짜 역할 · NAV 여섯 칸 · 위치 보정 값 · 순위 이름 · 겹침 순서 · 날짜 이름) | 위치 유지 · 순서 · 날짜 역할 · NAV 6칸(2026-11-18) · 순위 조건 줄 · 겹침 블록 · 묶음 아래 날짜 이름 · [세부 흐름 보기] 줄 · 진입마다 1회(2026-11-19 · §13 · §15-3) | 목록 순서 = 지금처럼 둠(형수님 의견 · §7) |
| 후보 기준 · 자료 예외 | 있음(상위 30 안 n위 · 순위권 밖 · 제외 · 저장 가격 없음 · 기간 · 조회 실패 · 개별 주식 · 끝 가격 상태) | 「주간 ETF 점검」 ↔ 「확인 근거」 같은 시각 대조 = 조건 · 기간 · 상위 30 종목 · 순서 · 순위 번호 같음 · 보유 행 순위 글이 판정 §1 글 규칙 안임을 확인(종류 · 건수는 가림 · 2026-11-19 · §15-3) · 순위 숫자 사례 = 고정 시험 자료(보유 여부와 무관 · §15-4) | — (개발자 확인) |
| 데이터 상태 | 있음(partial 포함 '기타' 건수 · 경계 · 음수 · 출처 · 재저장일 · nowrap · 요약 날짜 이름 4경우) | 기준일 칸 · 라벨 1줄(2026-11-18) · 요약 날짜 이름 실자료 · GET 가로채기 두 경우(2026-11-19 · §15-3) | — (개발자 확인) |
| 문서 · 기록 | — | — | 검증자 대상(M2 · M4 · M5 · M6 · RESULT 판정 §4-1 가림) |

## 9. 검사 결과(r1 정정 시점 · 2026-11-18 ~ 19 · 검증자 r2 대상) — 최종 검사 = §15-6

- **화면(main 세션 실측):**
  - `npx tsc --noEmit`: exit 0
  - `npx eslint --report-unused-disable-directives`(그때 바뀐 · 새 frontend ts/tsx 29개): exit 0
  - `npx vitest run`(전체 · r1 정정 뒤): **99파일 1,963 passed**
- **백엔드:**
  - main 세션 실측: `black --check` · `flake8` · `py_compile` = `app/holdings_reference_date.py` · `tests/test_holdings_market_evidence.py` 통과 · `pytest tests/test_holdings_market_evidence.py` 15 passed · `tests/test_poc5_07_reference_date.py` 11 passed
  - 그때 다시 잼: `black --check` 두 파일 'would be left unchanged' · `flake8` exit 0 · `PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider` 두 파일 **26 passed**(가져온 모듈 경로 = 격리 사본 `app/` 확인)
  - 전체 백엔드 회귀: §15-6
- **변이(되돌린 뒤 내용 cmp 확인 · H · M 갈래는 수정 시각도 되돌림 · 합계 100/100 잡힘 · 검토 · 화면 확인 뒤 11건은 개발자가 같은 세션에서 내용 다시 쓰기 + 수정 시각(os.utime) 되돌림 · 되돌린 뒤 바이트 같음 assert · 화면 서버 다시 읽게 touch):**
  - D 갈래 18/18(요약 '기타' = failed_count · 건수 판정 ≠ 필터 · partial 제외 · 사전 밖 원문 · 재저장일 · 3 · 5% 경계 · 음수 · 오류 원문 · 전체 건수 등)
  - H 갈래 25/25(상세에 수량 되살림 · 순서 · null 비중 · 초 · 시간대 · 자정 표기 · 날짜만 · 느슨한 해석 · 사전 밖 출처 · 비중 이름 · 종목 수 = 행 수 · '행'/'종목' 낱말 · Naver · 캐시 · 미입력 칸 · [자세히] 밖 등)
  - M 갈래 6/6(a 일괄 버튼 되살림 · b 머리 줄 · c 편집 라벨 · d 잔고 등록 편집기 숨김 · e 보관 파일 import 되돌림(tsc) · f 백엔드 MAX_TARGETS 200 → 1)
  - E 갈래 40/40(열기 · 닫기 · 위치 보정 · aria-expanded · 거르기 · 하위 30 · 끝 가격 상태 · 사유 · 개별 주식 · 조회 실패 · 0.00 · 창 기간 · 겹침 · not_integrated · 재저장일 · 미수집 · 시장 기준일 · 정렬 · 저장일 단위 등)
  - 검토 · 화면 확인 뒤 11/11: M11 상세 현재가 줄 되살림(실패 6) · M1 0 반올림 부호 · M2 nowrap 제거 · M3 옛 「데이터 상태」 숫자 함수 · M4 옛 겹침 글 · M5 builder 문장 바꿈 · M6 거르기 항목 하나 제거 · M7 낡은 거르기 항목 · M8 남겨야 할 문장을 거름 · M9 wide2 제거 · M10 라벨 nowrap 제거
  - r1 정정 10/10(§13 · F1-a ~ d · B6-a ~ f) → r1 시점 합계 110/110
- **git(r1 정정 시점):** 격리 사본 36줄 · main 문서 6건(지금 상태 = §2).

## 10. 독립 검토(2026-11-18 · 3관점 · 관점마다 반박 검증)

지적 7건: 확인 5건 · 불확실 1건 · 반박 1건.

| 지적 | 등급 · 판정 | 내용 | 처리 |
|---|---|---|---|
| EV-1 | 중간 · 확인 | 구성종목 중복 설명이 실제 규칙과 다름. 화면은 '1개월 상위 10개' · '상위 10행까지 비교'만 적었지만 builder 는 후보 2곳 이상의 상위 10행에 함께 나온 종목(반복 핵심 종목)하고만 대조한다(`min_appears=2`). 그 사실을 적던 builder 문장은 E6 에서 걸러졌다. 격리 자료 대략 대조에서 후보 한 곳의 상위 10행에만 있는 종목을 가진 보유 ETF 가 여럿 있었고, 이들은 '확인된 겹침'에 나오지 않는다. | 고침: `OVERLAP_CAP_TEXT` 새 글 · `HoldingsRiskEvidenceSection.test.tsx` 가 새 글 단정 · 변이 M4 잡힘 → RESULT 판정 §2-1 수용 · PLAN · 목업 갱신(§15) |
| EV-2 | 낮음 · 확인(잠재) | 거르기 시험이 builder 문장을 화면 쪽에 적어 두고 서로 대조할 뿐이라, builder 문장이 바뀌면 거르기가 소리 없이 풀린다('캐시' · 'source' 문장이 다시 보임). | 고침: 백엔드 시험 `test_builder_notes_match_shared_filter_fixture`(r1 B-6 뒤 이름 · 공용 고정 자료 · 144 조합 · 남는 문장 = 자료 부족 한 문장 · 화면 정확 일치 목록 ⊆ builder 문장 · 앞부분 거르기가 후보 네 문장 · KODEX200 두 부호를 덮음) · 변이 M5 · M6 · M7 · M8 잡힘 |
| EV-3 | 낮음 · 불확실 | [세부 흐름 보기] 창에 '거래량 · 출처 FinanceDataReader' 원문. 원래 있던 표기(POC5-09 확정)이고 공유 함수라 고치면 범위 밖 화면도 바뀐다. 사용자 규칙(영어 기술 용어 노출 금지)에는 어긋난다. | 검토 시점 고치지 않음 → RESULT 판정 §2-4 로 창 아래 = 비교 구간 · 유효 수 · 원문 = 도움말(공유 출력 그대로 · §15) |
| H-1 | 낮음 · 확인 | 「종목 관리」 '{행 수}종목'이 「보유 현황」 '종목 N개 · 보유 행 M개'와 숫자가 다름. PLAN H6 은 「보유 현황」만이라 범위 밖. | 검토 시점 고치지 않음 → RESULT 판정 §2-3 으로 '보유 행 M개'(§15) |
| DS-1 | 낮음 · 확인 | 「데이터 상태」 기준일 칸 140px 에서 '재저장일 2026-11-18'이 '재저장일 2026-11-' / '18'로 갈라짐. 네이버 조회가 실패한 날 그날 행 전체가 이렇게 보인다(지금 partial 0행). | 고침: 날짜 칸 `whiteSpace: "nowrap"` · 시험 · 실화면 1줄(§8) · 변이 M2 잡힘 |
| DS-2 | 낮음 · 확인 | 같은 저장값이 「데이터 상태」 '-0.00%' · 확인 근거 '0.00%'. | 고침: 공용 `discountPctText`(보이는 값 0.00 → '0.00%' · 양수만 '+') 두 화면에서 사용 · 시험 −0.004 → '0.00%' · 변이 M1 · M3 잡힘 |
| DS-3 | 낮음 · 반박 | 괴리율 표시 · 색은 반올림 전 값으로 정해 '+5.00%'에 '3% 이상' 표시가 붙을 수 있음. | 반박: PLAN D2 · 판정 Q38 · Q44 가 기존 기준(원값 절대값 3 · 5)을 그대로 쓰라고 함 · 두 화면 같은 동작 · 변경 전부터 있던 동작 · 격리 자료 0건 → 한계로만 기록(§5) |

## 11. 설계자 확인 요청 목록(검증자 r2 시점 · RESULT 판정 2026-11-19 §2 · §3 에서 모두 판정 · 처리 = §15)

0. **형수님 결정 — 「보유 현황」 상세 현재가 줄 뺌(2026-11-19).** 판정 §1 Q5 · Q9 · Q10 · PLAN H1 · 목업의 '상세에 현재가'와 다르다. 요약 행 '매입 X → 현재 Y' · 값 없음 '현재 미확인'(POC6-25)은 그대로. PLAN · 목업 글을 이 결정에 맞출지.

1. **I-4 + EV-1 구성종목 중복 줄.**
   - 확인된 겹침 이름 · 비중까지 숨길지(PLAN I-4 확인 요청 · 지금은 이름 · 비중을 보임 · 건수는 보이지 않음).
   - 비교 설명 글을 확정 PLAN I-4 · 목업 E7 의 '각 ETF 구성 상위 10행까지 비교(비교 상한) …'에서 '보유 ETF 구성 상위 10행을, 후보 가운데 2곳 이상의 구성 상위 10행에 함께 나온 종목(반복 핵심 종목)과 비교 · 상위 10행 = 비교 상한 · 실제 비교에 쓴 구성 기준일 · 행 수는 이 응답에 없음'으로 바꾼 것(실제 builder 규칙). PLAN · 목업 글을 이 글로 맞출지.
2. **I-2 History 흐름 줄.** 머리 줄 '비교 시작일'과 [시장 흐름 보기] 흐름 줄 '가격 비교 기준일 …'(백엔드 글 · 재진입 검토 창과 공유)이 한 창에 함께 보인다. 흐름 줄까지 맞추면 백엔드 응답 글자 · 시험 · 고정 자료가 함께 바뀌어 검증 대상이 된다.
3. **H-1 「종목 관리」 '종목' 숫자.** 「보유 현황」(H6)처럼 '보유 행 M개' 또는 '종목 N개 · 보유 행 M개'로 맞출지.
4. **EV-3 거래량 출처 원문.** '출처 FinanceDataReader'(`lib/storedVolume.ts` · `StoredVolumeBlock.tsx` 와 공유)를 쉬운 한국어로 바꿀지 · 바꾸면 공유 화면도 함께 바뀜.
5. **PLAN 에 없던 새 화면 글(§4 E · D).** 주간 요약 status 가 ok 가 아닐 때 · 응답에 그 종목이 없을 때 · 보유 목록 읽기 실패 · 구성 요약 미수집 · 조회 실패 글, NAV 도움말 3문단, 「데이터 상태」 사전 밖 괴리율 표시 원문의 [자세히] 표시.
6. **남은 옛 낱말(r2 시점).** 'PC 가격 흐름 기준일' · 'PC 비교 기준일' 사유 문장 · 'KODEX200'(띄어쓰기 없음) · 도움말 '20거래일'을 이번 범위 밖으로 둘지(I-15 를 좁게 읽어 남김).
7. **(정리됨)** 주간 순위 조회 횟수 — 검증자 r1 F1 에 따라 '화면에 들어올 때마다 한 번'으로 고쳤다(§13 · 해석 확인 불필요).
8. **I-1 ~ I-15 전체.** PLAN §9-1 의 개발자 적용 해석은 모두 확인 대기다. 다르게 정하면 그 I-n 에 적힌 파일 · 시험만 바꾼다.

## 12. 검증자 r1 판정(Codex · 2026-11-19)

- **종합 판정** `REJECTED`. 보유 상세 현재가 제거는 사용자 결정과 일치한다. 「확인 근거」 주간 순위 조회가 설계자 판정 §3과 PLAN E5를 충족하지 못했다.
- **기준** 격리 작업 사본 `poc6-33-holdings-ui`의 staged 35개와 main 문서 staged 6개. 기준 커밋 `e87ef4cc`. 설계·판정·PLAN·목업·개발 결과서를 실제 diff와 대조했다.

### 12-1. A. 기능·산출물 검증

- **A-1 지시 일치 — 위반. F1(P2) 주간 순위의 재진입 조회 생략과 실패 표시 누락.** 판정 Q22·Q24·Q49·Q52와 PLAN E5는 화면 진입 때 같은 기본 인자로 1회 조회하도록 정했다. PLAN의 캐시 키 공유는 확인했으며, §6의 세션 단위 조회에는 별도 판정 근거가 없다. `frontend/app/components/HoldingsRiskEvidenceSection.tsx:358–360`은 일반 공유 조회를 쓰고, `frontend/lib/api/queryCache.ts:236–243`은 성공값이 남으면 요청을 생략한다. `frontend/app/components/holdings_risk_evidence/helpers.ts:441–448`은 이전 성공값을 보존하는 다시 읽기 실패 상태를 순위에 표시하지 않는다.
  - **독립 재현 1.** 합성 응답으로 첫 진입에서 3위를 표시한 뒤 화면을 닫았다. 다음 서버 응답을 25위로 바꿔 재진입하자 3위가 남았고, 두 진입의 GET 합계는 1회였다.
  - **독립 재현 2.** 같은 키의 다시 읽기 실패를 캐시에 기록한 뒤 재진입하자 3위가 그대로 표시됐다. 새 요청과 순위 조회 실패 표시는 없었다. 「오늘의 투자 점검」의 자료 다시 읽기에도 이 실패 기록을 남기는 경로가 있다.
  - **사용자 결정 확인.** 격리 화면(3001)에서 보유 행을 펼쳐 매입금액·평가금액·매입 기준 비중·가격 기준시각과 요약 행의 현재가를 직접 확인했다. 상세 현재가는 표시되지 않았다. 시세 미확인 표시는 관련 렌더 시험으로 확인했다. 「확인 근거」의 정렬 유지와 상세 현재가 제거 결정은 §7·§11에 기록돼 있다. 전체 실화면 동선의 재확인으로 집계하지 않았다.
- **A-2 보고 정확성 — 통과.** 두 저장소의 변경 파일·추적 상태·§2 표의 줄 수를 대조했다. 격리 사본은 수정 32·이름변경 1·신규 2, main은 문서 6개다. stage 밖에는 사용자 소유 handoff 문서만 있었다. 백엔드 변경은 설명 문자열과 시험이다. Q55 기준 커밋의 파일은 PROGRAM_TRUTH 한 개다.
- **A-3 산출물 정합성 — 위반(F1).** 같은 조건의 기존 조회값이 남으면 그 뒤의 순위 변화와 조회 실패가 화면에 반영되지 않는다. 데이터 상태의 ‘기타’ 집계·필터, 행 아래 상세, 개별 기준일 편집, 누락 시세 관련 렌더 시험은 통과했다. 구성 중복 설명 EV-1은 기존 계산이 실제 사용하는 ‘후보 2곳 이상’ 조건과 일치하며, 확정 문장과 목업의 변경 여부는 §11에 남아 있다.
- **A-4 금지사항 — 위반 없음.** 신규 의존성·외부 API·DB 스키마 변경은 없다. 일괄 기준일 창은 추적 상태로 보관됐고 다건 저장 API 계약 시험이 통과했다.

### 12-2. B. 구현 규칙·구조 품질 검증

- **B-1 fallback — 있음(F1).** 순위의 이전 성공값을 재사용할 때 조회 실패를 표시하지 않는다.
- **B-2 단일 책임 — 위반 없음.** NAV 한국어 표기는 공용 순수 함수에 있고, 화면별 조회와 표시는 기존 화면 경계 안에 있다.
- **B-3 파일 크기 — 임계 초과 없음.** 변경 컴포넌트 최대 746줄, 시험 최대 1,056줄이다. 확인 근거의 함수 모듈은 600줄이다.
- **B-4 실험·운영 경계 — 위반 없음.** 운영 계산이나 저장 경로에 실험 코드가 추가되지 않았다.
- **B-5 배포 경로 — 영향 없음.** 새 파일과 이동된 파일이 추적된다. OCI 스크립트와 의존성 파일 변경이 없다.
- **B-6 구조적 퇴행 — 시험 결합 있음.** `test_builder_notes_match_front_filter_constants`는 현재 통과한다. 백엔드 시험이 프런트 소스의 파일 위치와 TypeScript 배열 선언 형태에 의존하므로 동일한 문구를 유지해도 선언 형식 변경이나 프런트 소스가 없는 시험 환경에서 실패할 수 있다. 영향 범위는 시험이다.

### 12-3. 기반 문서 준수

- 신규 Markdown 4개는 제출된 설계·판정·PLAN·결과서다. KS-2는 일괄 기준일 화면 경로에 대한 판정 기록만 추가했다. PROGRAM_TRUTH의 POC6-33 표기가 격리 사본 반영 대기 상태임을 확인했다.
- 공식 설계 문구와 다른 현재가 표시는 사용자가 직접 결정했고, EV-1 등 설계자 확인 항목은 §11에 기록돼 있다.

### 12-4. 코드 안전성

- **위험 수준** MEDIUM. F1 때문에 사용자가 이전 주간 순위를 당시 확인 가능한 순위로 읽을 수 있다. 읽기 실패 처리는 각 조회 경로에 있고 공용 API 요청 시간 제한이 유지된다. 새 비밀값이나 운영 데이터 쓰기 경로는 발견되지 않았다.

### 12-5. 범위 폭주

- **수준** MINOR. EV-1의 문구 변경과 공용 문구의 생산자·소비자를 대조하는 백엔드 시험이 PLAN에 적힌 범위를 넘었다. 사용자 직접 결정인 상세 현재가 제거는 승인 범위에 포함했다.

### 12-6. 종합 판정과 검사

- **REJECTED.** F1의 기준은 판정 §3·PLAN E5다.
- **검증자 실측** 격리 복사본에서 프런트 관련 8파일 187건, 백엔드 관련 3파일 31건 통과. 독립 재현 2건에서 F1의 동작을 확인했다. 타입 검사·변경된 프런트 29개 파일 eslint·black·flake8·py_compile·두 저장소의 Git 공백 검사 통과.
- **검사 범위** 개발자가 보고한 프런트 전체 1,958건을 다시 돌리지 않았다. 백엔드 전체 회귀는 아직 미실행이다. 검증자 재현 시험은 저장소 밖 사본에 있다.

### 12-7. 사용자에게

보유 상세의 현재가 제거를 확인했다. 재검증이 필요한 문제는 「확인 근거」 재진입 때 이전 순위를 재사용하고 조회 실패가 표시되지 않는 동작이다.

## 13. 검증자 r1 지적 처리(개발자 · 2026-11-19)

| 지적 | 처리 | 확인 |
|---|---|---|
| **F1(P2)** 재진입 때 주간 순위를 새로 읽지 않음 · 다시 읽기 실패에 실패 표시 없음 | `HoldingsRiskEvidenceSection.tsx` — 마운트(화면 진입)마다 `weekly.reloadAsync()`(강제 · 같은 `etfCompareKey` · 진행 중 요청이 있으면 그 요청을 같이 씀)로 한 번 새로 읽고, 그 조회가 끝나기(성공 · 실패) 전에는 상세에 `{ phase: "loading" }` 을 넘김(이전 순위 안 보임). `helpers.ts :: weeklyRankView` — `phase: "success"` 라도 `stale`(다시 읽기 실패로 이전 성공값만 남음)이면 '자료 확인 불가 — 주간 순위 조회 실패'(조건 줄 없음). 실패해도 목록 · 요약 · 그 종목 가격 · 구성 · NAV 근거는 그대로(판정 Q52). | 렌더 시험 4개(재진입 → 새 응답 25위 · 진입마다 요청 1회 · 같은 진입 안 상세 재열기 = 요청 없음 / 재진입 조회 중 '불러오는 중' / 재진입 조회 실패 → '조회 실패' · 3위 글 없음 · 가격 근거 그대로 / 보는 중 다른 화면 다시 읽기 실패(`markQueryFailed`) → '조회 실패') · 단위 시험(stale → 실패 · 아니면 n위). 변이 F1-a(새로 읽기 없음) · F1-b(조회 전 이전 값) · F1-c(stale 무시) · F1-d(강제 아님) **4/4 잡힘**. 격리 실화면(3001 · GET 만): 확인 근거 1차 진입 요청 1 → 보유 현황 다녀온 2차 진입 누적 2 → 주간 ETF 점검 다녀온 3차 진입 누적 3(진입마다 1회 · 8000 · 3000 요청 없음). |
| **B-6** 백엔드 시험이 프론트 소스 파일 위치 · TypeScript 선언 모양에 묶임 | POC6-32 공용 고정 자료 방식으로 바꿈: `tests/fixtures/poc6_33_filtered_notes.json`(거르기 정확 일치 6 · 앞부분 2 · 남기는 문장 1 · 합성 문장) 신규. 서버 시험 `test_builder_notes_match_shared_filter_fixture` 는 이 파일만 읽어 builder 144 조합과 대조(프론트 소스 안 읽음 · `import re` 뺌). 화면 `helpers.test.ts` 가 `FILTERED_NOTES` · `FILTERED_NOTE_PREFIXES` = 같은 고정 자료 · 남기는 문장은 거르지 않음을 대조. | 변이 B6-a(builder 문장 바꿈 → 서버) · b(화면 상수 한 줄 빠짐) · c(화면 낡은 줄) · d(화면 앞부분 바뀜) · e(고정 자료 한 줄 빠짐 → 서버) · f(같은 변이 → 화면) **6/6 잡힘**. |
| 범위 MINOR(EV-1 글 · 생산자 · 소비자 대조 시험) | 고치지 않음 — EV-1 은 실제 builder 규칙 글(§11-1 설계자 확인 대기) · 대조 시험은 B-6 대로 구조만 바꿈. | — |

- **act 경고 1건**(MainHoldingsLine · 'E3 · 판정 Q30' 시험)은 r1 정정 전에도 같은 수(1)로 났다(정정 전 · 후 같은 명령으로 셈). 다만 main `e87ef4cc` 에는 없던 경고로, POC6-33 이 새로 만든 MainHoldingsLine 에서 나왔다(2026-11-19 전체 로그 비교로 확인 · RESULT 보완 때 시험을 고쳐 없앰 · §15-6).
- **stage:** 격리 사본 36건 · main 문서 6건을 경로 하나씩 다시 stage 했다(§2).
- **이번 정정 범위의 검사:** tsc 0 · 바뀐 4파일 eslint 0 · vitest 전체 99파일 1,963 passed · pytest(`test_holdings_market_evidence.py` · `test_poc5_07_reference_date.py` · `test_pc_price_basis.py`) 49 passed · black · flake8 통과. 전체 pytest 는 커밋 전 1회(아직 안 돌림).

## 14. 검증자 r2 판정(Codex · 2026-11-19)

**종합 판정** `VERIFIED`. r1의 F1과 B-6 정정을 확인했다. 판정 기준은 `e87ef4cc` 위 격리 사본 staged 36건과 main 문서 staged 6건이다.

### 14-1. A. 기능·산출물 검증

- **A-1 지시 일치 — 통과.** 판정 Q22·Q24·Q49·Q52와 PLAN E5에 따라 「확인 근거」에 진입할 때마다 같은 기본 조건으로 조회한다. 이전 순위가 있는 상태에서 새 응답이 25위로 바뀌면 25위를 표시한다. 진행 중에는 불러오는 중을, 조회 실패 및 같은 키의 다시 읽기 실패에서는 조회 실패를 표시하며 이전 순위는 숨긴다.
- **A-2 보고 정확성 — 통과.** r1 검증본과 해시를 비교했다. 화면 코드·시험 4개와 서버 시험·PROGRAM_TRUTH가 변경됐고, 공용 고정 자료 한 개가 추가됐다. 격리 사본은 수정 32·이름변경 1·신규 3, main은 문서 6개가 staged 상태다. 사용자 소유 handoff는 미추적이다. §4·§6의 줄 수를 실측값으로 정정했다.
- **A-3 산출물 정합성 — 통과.** r1 재현은 제품 시험에서 재확인했다. 검증자 독립 시험에서는 조회 중 화면을 나갔다 다시 들어와도 GET은 한 번이고 완료 후에만 순위를 표시했다. 다시 읽기 실패 상태에서 재진입하면 진행 중 안내 뒤 새 순위를 표시했고 가격·NAV 근거도 유지됐다. 격리 실화면 요청 횟수는 개발자의 §13 기록을 사용했다.
- **A-4 금지사항 — 위반 없음.** 기존 GET을 재사용한다. 신규 의존성·외부 API·DB 스키마·운영 쓰기 경로의 추가가 없다.

### 14-2. B. 구현 규칙·구조 품질 검증

- **B-1 fallback 위반 — 없음.** 다시 읽기가 실패한 때에는 이전 순위를 숨기고 실패를 명시한다.
- **B-2 단일 책임 위반 — 없음.** 화면 진입 시점의 상태와 순위 문구 계산이 분리돼 있다.
- **B-3 파일 책임 과다 — 없음.** 변경 컴포넌트 최대 746줄, 시험 최대 1,120줄로 기존 크기 기준 이내다.
- **B-4 실험·운영 경계 위반 — 없음.** 공용 고정 자료는 시험에서만 사용한다.
- **B-5 배포 경로 영향 — 없음.** 고정 자료를 포함한 시험 대상은 Git 추적 상태다. 배포 스크립트·의존성 파일 변경이 없다.
- **B-6 구조적 퇴행 — r1 지적 해소.** 서버 시험은 JSON 고정 자료를 읽어 builder 출력과 대조하고, 화면 시험은 같은 자료와 화면 상수를 대조한다. 프런트 폴더를 제거한 검증 사본에서 해당 서버 시험을 따로 실행해 통과했다.

### 14-3. 기반 문서 준수

r2 코드 변경은 r1 정정 범위에 있다. PROGRAM_TRUTH는 격리 사본 반영 대기로 기록돼 있다. 구성종목 중복 문구 EV-1과 사용자 결정에 따른 상세 현재가 제거 등 설계자 확인 사항은 §11에 남아 있다.

### 14-4. 코드 안전성

**위험 수준** NONE. r2 정정에서 신규 위험을 발견하지 못했다. 읽기 요청은 기존 공용 시간 제한을 쓰며, 실패 시 가격·구성·NAV 근거가 유지된다.

### 14-5. 범위 폭주

**r2 수준** NONE. 변경 범위는 주간 순위 재조회와 공용 시험 자료다. r1에서 기록한 문구 차이(EV-1)는 §11의 설계자 확인 대상이다.

### 14-6. 종합 판정과 검사

**VERIFIED**. 격리 사본에서 프런트 관련 4파일 116건, 검증자 독립 시험 2건, 관련 백엔드 49건이 통과했다. 타입 검사, 변경 프런트 4파일 eslint, black·flake8·py_compile, 두 저장소의 Git 공백 검사도 통과했다. 관련 프런트 시험에서 기존 React `act` 경고가 한 건 나왔다. 프런트 전체 1,963건은 개발자 실측을 참고했으며 전체 pytest는 커밋 전 검사로 남아 있다.

### 14-7. 사용자에게

r1 지적 두 건이 해소됐다. 이 결과서로 설계자 RESULT 판정을 진행할 수 있다.

## 15. 설계자 RESULT 판정과 보완 확인(2026-11-19)

### 15-1. 판정과 지금 상태

- 판정서: `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT_DECISION_2026-11-19.md`(설계자 원문 · 판정 §4-4 대로 보관).
- **조건부 PASS.** 검증자 r2 VERIFIED 를 수용했다(F1 · B-6 해소). 형수님이 정한 보유 상세 한 줄도 수용했다. 화면 표기와 문서를 맞추고 커밋 전 확인을 기록하면 RESULT 를 PASS 로 확정한다(판정 §4).
- 판정 §1: 세 화면의 정렬 기준은 다르다. 「후보리스트」 = 고른 기간 하나(기본 1개월)의 가격 수익률, 「주간 ETF 점검」 = 1개월 가격 수익률 상위 30(제외 4종), 「확인 근거」 = 보유 목록 기본 '5저장일 변화' 순이고 행을 펼치면 「주간 ETF 점검」과 같은 조건의 순위 · 상태를 보인다. 형수님 의견(「확인 근거」 순서 ≠ 「후보리스트」 → 지금처럼 둠)은 이 설명대로 둔다.
- 판정 §2 · §3: 결과서 §11 확인 요청 0 ~ 8 과 PLAN I-1 ~ I-15 를 모두 판정했다(수용 · 표시 보완 · 종결 · 확정). Q55 는 §1-2 의 POC6-32 상태 문서 단독 반영 기록으로 수용했다.
- **상태:** 설계자 RESULT 조건부 PASS(2026-11-19) → 보완 반영 · 확인 완료 → 설계자 RESULT **PASS 확정**(2026-11-19) → 구현 커밋 `7eb7cd0c` · main 반영 · 운영 화면(3000) 네 곳 확인 완료(2026-11-19 · §16). push · 격리 정리는 형수님 별도 승인 뒤이고, 그 뒤 종료를 기록한다.

### 15-2. 판정 §1 ~ §3 반영(격리 사본 코드 대조)

| 판정 | 판정 내용 | 반영(코드 확인) | 시험 · 변이 |
|---|---|---|---|
| §1 순위 이름 | 수용 | `helpers.ts` `weeklyRankView` — `listName` = 응답 basis 의 기간 이름 + '수익률 상위' + 응답 n. 상위 30 안 = '1개월 수익률 상위 30 중 n위 · 기간 · 제외 조건(· 끝 가격 상태)', 순위권 밖 = '순위권 밖 · 1개월 수익률 상위 30 밖 · 기간(· 끝 가격 상태)', 조건 줄 = '「주간 ETF 점검」과 같은 조회 · 1개월 수익률 상위 30 · M/D → M/D · 제외 4종'. 규칙상 제외 · 개별 주식 · 자료 부족 · 조회 실패 · 불러오는 중은 각각의 사유 글. 진입마다 1회 조회는 r1 정정 그대로 | `helpers.test.ts` 표(3위 · 장중 · 마감 미확인 · 상·하위 공통 7위 · 3개월 basis) · Section 시험 · 변이 A 3건 |
| §2-0 보유 상세 한 줄 | 수용 | r1 구현 그대로(매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준시각 · 출처). PLAN H1 · H5 · Q5 · Q10 · 목업에 11/19 형수님 결정 표시(갈래 D). 목업 상세 4항목 = 1440 · 1100 한 줄 · 820 · 420 줄바꿈 · 가로 스크롤 없음(갈래 D 렌더) | 렌더 시험 · 변이 M11(§9) |
| §2-1 구성종목 중복 | 수용 | `HoldingsRiskEvidenceSection.tsx` `OverlapLine`: ① '비교 범위 확인 불가'(맨 앞) ② '비교 후보 목록(주간 순위 목록과 별도): ' + 그 목록의 기간 · 제외 조건(`topnBasisText`) ③ 실제 비교 규칙 글(`OVERLAP_CAP_TEXT` · 상위 10행 = 비교 상한) ④ '확인된 겹침:' 이름 · '이 ETF 편입 비중 x.xx%'(builder `weight_pct` = 보유 ETF 자신의 구성 행 비중 · 없으면 이름만 · `overlapFoundText`). '중복 없음' · 건수 · 비율 없음. '주요 편입'의 날짜 · 범위는 그 자료에 붙임(E8). PLAN E7 · I-4 · 목업을 같은 규칙으로 갱신 | 변이 A 5건 |
| §2-2 History 이름(I-2) | 표시 보완 | 서버 원문 · API · 저장 계약 그대로. 화면 사전 `historyText.ts`(`Map`): '가격 비교 기준일 이후 종가 변화' → '비교 시작일부터 종가 변화' · 안내 → '비교 시작일은 종가 비교의 출발점이다 — …'. `MarketFlowPanel.tsx` 기간 줄 '비교 시작일 A → 마지막 매도일 B' · 휴장 이동 '설정한 비교 시작일 D'. 사전 밖 글은 원문 그대로. 같은 `MarketFlowView` 를 쓰는 재진입 검토 창에도 적용. 공용 고정 자료 `tests/fixtures/poc6_33_market_flow_labels.json` 을 서버 시험(`test_reference_texts_match_shared_label_fixture` · 서버 상수 · 실제 출력)과 화면 시험(`MarketFlowPanel.test.tsx` · 사전 열쇠 · 보이는 글)이 함께 대조 | 화면 시험 5개 · 서버 시험 1개 · 변이 B 16건(M1 ~ M10 · F1 ~ F4 · S1 · S2 · 그중 고정 자료 · 서버 상수 표류 6건) |
| §2-3 종목 관리 건수(H-1) | 표시 보완 | `HoldingsBookSection.tsx:280` '보유 행 {행 수}개 · 수익률은 …'(「보유 현황」 배너 '종목 N개 · 보유 행 M개'와 같은 단위) | `ReferenceDate.test.tsx` 가상 종목 하나를 두 계좌에 → '보유 행 2개' · 'N종목' 없음 · 변이 B 2건(M11 · M12) |
| §2-4 거래량 출처(EV-3) | 표시 보완 | `DetailFlowsBody.tsx` 창 아래 '거래량 · 비교 구간 A ~ B · 유효 N/M'(`volumeSourceParts` 의 둘째 부분) · 제공처 원문은 그 창 기존 '세부 흐름' ? 도움말 마지막 문단 '거래량 제공처 원문: <source>'(`volumeProviderHelp` · source 없으면 '거래량 제공처: 확인 불가'). 공유 출력은 그대로 | `HoldingsRiskEvidenceDecline.test.tsx` 창 시험 · `storedVolume.test.ts` · 변이 A 4건 |
| §2-5 추가 안내 문구 | 수용 | r1 구현 그대로(조회 중 · 조회 실패 · 미수집 · 해당 없음 · 자료 부족 · '자료 확인 불가' 구별 · NAV 뜻은 도움말 · 사전 밖 원문은 [자세히]) | (§9 · §13) |
| §2-6 남은 옛 표현 | 표시 보완 | 「확인 근거」 안: 'PC 가격 흐름 기준일' · 'PC 비교 기준일' · 'PC 저장 가격 기준일' → '가격 기준일'(`priceBasis.ts` · `declineSummary.ts` · `priceVolatility.ts` · `EvidenceGroups.tsx` 의 `pastVolumeNote(…, "가격 기준일")`). 종목 자신의 마지막 날짜 = '이 종목 마지막 저장일'(여러 종목 줄 '마지막 저장일'). 묶음 아래 = '마지막 저장일 D · PC 저장 종가' / '마지막 저장일 D' / '마지막 유효 가격일 D'(R4). [세부 흐름 보기] '가격 흐름 · 마지막 저장일 D · 5저장일 … · 20저장일 …'(`priceFlowLine` · R4). 도움말 '20거래일' → '최근 20개 저장일이 거래일로 빠짐없이 이어졌는지는 따로 확인하지 않습니다'(`volumeTrend.ts`). 'KODEX200' → 'KODEX 200'(`declineSummary.ts` · `riskCombination.ts`). 요약 '시장 기준일' → '기존 후보 목록 기준일'(+ 보일 때만 ? 뜻 문단 `HELP_MARKET_ASOF`). 서버 원문 거르기 접두어는 원문 그대로(고정 자료 시험이 지킴) | 변이 A 16건 · R4 4건 |
| §2-7 F1 | 종결 | — | §13 · §14 |
| §2-8 · §3 I-1 ~ I-15 | 확정 | I-9: `DataStatusView.tsx` `summaryDateLabel` — 응답 items 전체에서 응답 asof(최댓값 날짜)에 '재저장일'(`navDateLabel`) 행이 하나라도 있으면 '가장 최근 목록 날짜(재저장일 포함)', 아니면 '가장 최근 기준일'. 날짜 값 = 응답 asof 그대로 · 고르기 · 검색 · 200건 표시와 무관. 나머지 I-n 은 r1 구현 그대로(I-2 · I-4 · I-15 는 위 §2 줄) | `DataStatusView.test.tsx` 시험 4개 · 변이 C 5건 |

### 15-3. 최종 화면 확인(판정 §4-2) — 형수님 확인과 개발자 확인

개발자 확인은 격리 화면 3001 · 백엔드 8001 · GET 만 · 8000 · 3000 으로 나간 요청 없음(2026-11-19 · main 세션 관찰)이다.

| 확인 항목 | 확인한 사람 | 결과 | 근거 |
|---|---|---|---|
| 「보유 현황」 펼친 상세(매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준시각 · 출처) | **형수님**(격리 화면 · 2026-11-19) | 상세 현재가 = 요약 행과 반복 → 뺌(판정 §2-0 수용) · §8-1 완료 | 형수님 결정 · 렌더 시험(`EnrichedHoldingsSection.eval.test.tsx` · 상세 현재가 없음 · '현재 미확인' · '평가 불가' · '비중 계산 불가') · 변이 M11 · 1440 폭 한 줄(§8) · 검증자 r1 격리 화면 직접 확인(§12-1) |
| 「확인 근거」 목록 순서 ↔ 「후보리스트」 선정 순서 | **형수님**(2026-11-19) | 지금처럼 둠 | 판정 §1 두 순서 설명 · 「확인 근거」 정렬은 POC5-UI-02 그대로(이번 무변경) |
| 추가매수 부분 | **형수님**(2026-11-19) | 확인함 | 형수님 격리 화면 확인 |
| 「종목 관리」 표 아래 건수 | 개발자 | '보유 행 M개 · 수익률은 …' | 실화면 · `HoldingsBookSection.tsx:280` · 시험 · 변이 B 2건 |
| History 비교 시작일 | 개발자 | 창 머리 '비교 시작일' · [시장 흐름 보기] '비교 시작일부터 종가 변화' · 안내 '비교 시작일은 종가 비교의 출발점이다 — …' · 창 안 '가격 비교 기준일' 0회 | 실화면 · `historyText.ts:109-125` · `MarketFlowPanel.tsx` · 공용 고정 자료 서버 · 화면 시험 · 변이 B |
| 「확인 근거」 행 아래 상세 | 개발자 | 누른 행 아래 · 스크롤 위치 유지 · NAV 여섯 칸 · 진입마다 순위 조회 1회 | 2026-11-18 실측(§8) · r1 실측(§13) 그대로 유효 · 렌더 시험 |
| 「확인 근거」 순위 라벨 | 개발자 | 조건 줄 '「주간 ETF 점검」과 같은 조회 · 1개월 수익률 상위 30 · 10/19 → 11/18 · 인버스 · 레버리지 · 합성 · 선물 제외'. 보유 행을 모두 펼쳐 순위 글을 읽었고, 모두 판정 §1 의 글 규칙 안이었다(옛 이름 · 사전 밖 글 없음 · 어떤 글이 몇 행에 보였는지는 보유 집계라 가림 · RESULT 판정 §4-1). 순위 숫자 글('… 중 n위')은 보유 여부와 상관없이 고정 시험 자료로 확인(§15-4) | 실화면 · `helpers.ts` `weeklyRankView` · `helpers.test.ts` · Section 시험 |
| 「확인 근거」 구성종목 중복 | 개발자 | '비교 범위 확인 불가' → '비교 후보 목록(주간 순위 목록과 별도): 1개월 상위 10개 기준 · 시작 10/19 → 끝 11/18 · …' → '보유 ETF 구성 상위 10행을, 후보 가운데 2곳 이상의 … 비교 · 상위 10행 = 비교 상한 · …' | 실화면 · `OverlapLine` · 변이 A |
| 「확인 근거」 묶음 아래 날짜 이름 | 개발자 | '마지막 저장일 D · PC 저장 종가' / '마지막 저장일 D' / '마지막 유효 가격일 D' | 실화면 · `EvidenceGroups.tsx:66` · `:90` · `:117` · 변이 R4 |
| [세부 흐름 보기] 창 아래 줄 · 도움말 | 개발자 | '거래량 · 비교 구간 2026-10-21 ~ 2026-11-17 · 유효 20/20'(FinanceDataReader 없음) · '가격 흐름 · 마지막 저장일 D · 5저장일 D ~ D · 20저장일 D ~ D' · 도움말 안 '거래량 제공처 원문: FinanceDataReader' | 실화면 · `DetailFlowsBody.tsx:76-77` · `:136` · `:138` · 변이 A · R4 |
| 「데이터 상태」 요약 날짜 이름 · 재저장일 | 개발자 | 실자료: '… 가장 최근 기준일 2026-11-18 · 출처 네이버 …'(재저장일 행 없음). GET 가로채기로 최댓값 날짜 3행을 재저장(partial)으로 바꿈 → '가장 최근 목록 날짜(재저장일 포함) 2026-11-18' · 행 '재저장일 2026-11-18'. 더 옛 날짜만 재저장 → '가장 최근 기준일 2026-11-18' · 행 '재저장일 2026-11-10'. 재저장일이 새 원천 자료일로 읽히지 않는다 | 실화면 · `DataStatusView.tsx` `summaryDateLabel` · 시험 4개 · 변이 C |
| 「데이터 상태」 수집 상태 · 괴리율 표시 | 개발자 | 괴리율 표시 배지는 괴리율 열, 수집 상태 배지는 수집 상태 열로 따로 보이고, 표 위 뜻 두 줄(D5)이 둘을 따로 설명한다 | 코드(`DataStatusView.tsx` 표 머리 · 행) · 렌더 시험(`DataStatusView.test.tsx`) |

### 15-4. 주간 두 화면 대조(같은 시각 · 격리 8001 · 2026-11-19)

- `GET /weekly/etf-check` 조건 = one_month · 상위 · n 30 · 제외 4종 · 2026-10-19 → 2026-11-18.
- `GET /market/etf-compare/summary`(「확인 근거」와 같은 인자) = one_month · 같은 제외 · 기간 2026-10-19 → 2026-11-18 · n 30.
- 두 응답의 상위 30 종목이 같은 순서 · 같은 순위 번호였다.
- 코드 근거: `/weekly/etf-check` 는 `build_summary` 를 `app/weekly_review.py` `BASIS`("one_month") · `FILTERS` 로 부른다(`app/api_weekly_review.py:195-198`). 「확인 근거」는 `WEEKLY_CHECK_CONDITION`(1개월 · 같은 제외 4종)으로 `/market/etf-compare/summary` 를 부르고, 그 경로도 `build_summary` 다(`app/api_etf_compare.py`).
- 보유 가운데 주간 상위 30 안 = ○건(보유 집계 · 가림). 순위 숫자 사례('1개월 수익률 상위 30 중 n위')는 보유 여부와 상관없이 고정 시험 자료로 확인했다: `helpers.test.ts` 표(3위 · 장중 · 마감 미확인 · 7위) · `HoldingsRiskEvidenceSection.test.tsx` r1 F1 시험(3위 → 재진입 뒤 25위).

### 15-5. 이번 라운드 독립 검토(판정 보완 뒤 · 지적 4건 · 반박 검증 4건 모두 확인)

| 지적 | 등급 | 내용 | 처리 |
|---|---|---|---|
| R1 | 중간 | 이번 보완이 stage 되지 않음(새 History 고정 자료 '??' · 작업 트리에만 있는 파일들). stage 된 PLAN · 목업 · STATE 는 가리기 전 보유 집계를 담고 있었다. 새 고정 자료가 빠진 채 시험 파일만 stage 되면 두 시험 파일이 통째로 실패한다 | 처리 완료(2026-11-19 · main 세션): 두 저장소 모든 경로를 하나씩 stage(`git add -A` · 폴더 add 안 씀) · 오른쪽 칸 공백 · '??' 는 형수님 소유 handoff 하나 · stage 본(`git show :<경로>`) PLAN · 목업 · STATE POC6-33 줄에서 보유 집계 grep 0건(목업의 '계좌 1 · 2'는 합성 이름). 참고: STATE 431행의 보유 평가 비중 수치는 예전 단계(POC6-31) 기록이라 이번 가림 범위(판정 §4-1 '이번에 넣은 보유 집계') 밖 |
| R2 | 중간 | 결과서 §15 없음 · 머리 · §1-2 · §2 · §5 · §7 · §8-1 이 판정 전 상태 · §2 · §5 가 코드와 어긋남 · STATE POC6-33 줄이 '다음 = 설계자 RESULT 판정' | 이 문서 갱신(옛 문장 교체) · STATE POC6-33 줄 갱신 |
| R3 | 낮음 | 격리 사본 `docs/KILL_SWITCHES.md` KS-2 근거 줄에 보유 상태 건수가 숫자로 남음(다른 문서는 가림) | 근거 줄을 '2026-10-11 일괄 실행 뒤 일괄 창 대상은 ○건이다(보유 집계라 공개 문서에서 가림 · RESULT 판정 §4-1). 기준일 없는 보유 기간이 없으면 …'으로 바꿈(코드 확인 `KILL_SWITCHES.md:25`) |
| R4 | 낮음 | 「확인 근거」 한 상세 안에서 종목 자신의 마지막 날짜가 '이 종목 마지막 저장일'과 맨 '기준일'로 섞여 보임(가격 기준일과 다른 종목이면 '가격 기준일'과 다른 날짜가 '기준일'로 보임) | 묶음 아래 · 흐름 줄 이름을 §15-2 §2-6 줄대로 고침 · `priceFlowLine` 은 「확인 근거」에서만 씀(사용처 grep) · 시험(`HoldingsRiskEvidenceSection.test.tsx` · `HoldingsRiskEvidenceDecline.test.tsx` · `lib/priceBasis.test.ts`) · 변이 R4-a ~ d 4/4 잡힘 · 목업 묶음 아래 · PROGRAM_TRUTH §5.2 문장도 같이 고침 |

### 15-6. 완료 검사(판정 §4-3 · 2026-11-19)

- **화면:**
  - `npx tsc --noEmit`: exit 0 · 오류 0
  - `npm run lint`(PLAN §5 · `frontend/package.json` `"lint": "eslint ."` · 화면 전체): exit 0 · 출력 없음(2026-11-19 · 격리 사본 작업 트리 · act 정정 뒤)
  - `npx eslint --report-unused-disable-directives`(바뀐 frontend ts/tsx 42개): exit 0
  - `npx vitest run`(전체): 99파일 **1,979 passed**(R4 반영 뒤 · act 정정 앞 · act 정정은 시험 수를 바꾸지 않고 단정 하나만 더함)
  - `HoldingsRiskEvidenceSection.test.tsx` 만(act 정정 뒤 · 이 문서 작성 때 다시 돌림): 38 passed · 'not wrapped in act' 0줄
  - 최종본 재확인(2026-11-19 · main 세션): `npx tsc --noEmit` exit 0 · `npm run lint`(= `eslint .`) exit 0 · `npx vitest run` 전체 **99파일 1,979 passed** · 'not wrapped in act' **31줄 = main `e87ef4cc` 의 31줄과 같음**(이번 작업이 더한 경고 0 · 실패 아님) · 변이 표식 grep 0건
- **백엔드:**
  - `black --check` · `flake8` · `py_compile`(`app/holdings_reference_date.py` · `tests/test_holdings_market_evidence.py` · `tests/test_poc5_07_reference_date.py`): 통과
  - `PYTHONDONTWRITEBYTECODE=1 pytest tests/test_holdings_market_evidence.py tests/test_poc5_07_reference_date.py tests/test_pc_price_basis.py`: **50 passed**(가져온 모듈 = 격리 사본 `app/`)
  - 전체 백엔드 회귀: 6,401 passed · 2 skipped · 1 warning(Starlette 지원 중단 경고) · exit 0 · 43분 42초 · 격리 사본 최종본(2026-11-19 · `PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider` · `caffeinate -i`)
- **변이(이번 라운드 55건 모두 잡힘 · `git stash` 안 씀):**
  - 되돌림: 갈래 A · C 는 바꾼 파일을 매번 원래 바이트로 다시 쓰고 `os.utime` 으로 수정 시각을 되돌린 뒤 바이트 · 수정 시각이 같은지 assert 했다. 갈래 B 는 원래 바이트로 다시 쓰고 `os.utime` 으로 수정 시각을 맞춘 뒤 바이트 같음을 확인했다(S1 · S2 는 파일을 바꾸지 않고 시험 실행 안에서만 서버 상수를 바꿈). R4-a ~ d 는 main 세션이 같은 방식으로 되돌렸다(원래 바이트 다시 쓰기 + `os.utime` 으로 수정 시각 되돌림 · 되돌린 뒤 바이트 같음 assert · `git stash` 안 씀 · 화면 서버가 다시 읽게 touch).
  - 지금 격리 사본 소스(`frontend/app` · `frontend/lib` · `tests` · `app` · `docs`)에서 갈래 A 변이 표식('ZZMUT') grep = 0건(2026-11-19). 갈래 B · C 는 표식 없이 글을 바꾸는 변이라 위 바이트 같음 확인이 근거다.
  - 갈래 A 28/28(순위 이름 3 · 구성종목 중복 5 · 거래량 출처 4 · 옛 표현 16)
  - 갈래 B 18/18(사전 우회 · 기간 줄 · 휴장 이동 · 사전 열쇠 · 사전 밖 · 객체 함정 · '보유 행' · 고정 자료 server · display 표류 · 서버 상수 표류)
  - 갈래 C 5/5(최댓값 날짜 대조 제거 · 표시 200건 · 고르기 결과 · '기타' 묶음으로 넓힘 · 늘 옛 이름)
  - R4 4/4(R4-a ~ d)
  - **합계: 이전 110 + 이번 55 = 165건 잡힘 · 놓친 것 0**
- **문서(갈래 D):** 목업을 1440 · 1100 · 820 · 420 폭으로 그려 가로 스크롤 없음 · 콘솔 오류 없음 · 태그 짝 확인. 보유 집계 패턴 grep 을 바꾸기 전 · 뒤로 재고 남은 것을 하나씩 확인(규칙 번호 · 시험 문자열 · 시장 전체 건수만 남음).
- **공개 문서 가림(판정 §4-1 · 값은 적지 않고 건수만):** PLAN 47값 · 14곳 · 목업 28값 · 13곳 · STATE 3값 · 1곳 · 이 결과서 0 · 격리 사본 `docs/KILL_SWITCHES.md` 1곳(R3) · `docs/PROGRAM_TRUTH.md` '지금 일괄 대상' 1곳(통합).
- **React `act` 경고 · 420px 가로 스크롤:** 한계로 기록(§5).
- **git:** 최종 stage 상태 = §2(stage · 확인은 main 세션 · 보고 직전).

## 16. main 반영 · 운영 화면 확인(개발자 · 2026-11-19)

- **설계자 RESULT PASS 확정(2026-11-19):** §15 의 보완 · 주간 두 화면 순위 일치 · 프런트 1,979 · 백엔드 6,401 통과를 확인. 로컬 커밋 · main 반영 · 운영 화면 확인까지 진행하고, push 와 격리 정리는 운영 확인 결과를 본 뒤 별도 승인(형수님 전달).
- **구현 커밋 `7eb7cd0c`**(격리 브랜치 `poc6-33-holdings-ui` · 51파일 · 3,797 추가 · 865 삭제 · stage 된 51건 그대로) → main `git merge --ff-only`(main `e87ef4cc` → `7eb7cd0c` · main 작업 트리의 stage 문서 7건과 겹치는 파일 0).
- **PROGRAM_TRUTH 반영일(판정 §4-4):** main 에서 머리 줄을 '**최종 반영**: 2026-11-19 — `POC6-33` … main 반영(… 구현 커밋 7eb7cd0c · main 빨리 감기 2026-11-19 …)'로 바꾸고, 직전 '최종 반영'(POC6-32)은 '(그 전)'으로 내렸다. 본문의 '`POC6-33` 반영 대기(격리 사본)' 표시는 모두 '`POC6-33`(main 반영 2026-11-19)'로 바꿨다(남은 '반영 대기(격리 사본)' 0건 · 28곳). 합치기 전 동작 설명은 '(그 앞 동작)'으로 남겼다. 이 변경은 아래 문서 커밋에 함께 들어간다.
- **운영 화면 확인(3000 · 운영 서버 8000 · 1440 폭):** 브라우저에서 GET · HEAD · OPTIONS 밖 요청은 모두 막았다(막힌 쓰기 요청 0건). 격리 서버(8001 · 3001)로 간 요청도 0건이다. 값 · 건수는 적지 않는다.

| 화면 | 확인 내용 | 결과 |
|---|---|---|
| 「보유 현황」 | 배너 · 첫 행 펼친 상세 항목 · 줄 수 · 가격 기준시각 모양 | 배너 '종목 N개 · 보유 행 M개' 있음 · 상세 = 매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준시각(현재가 없음) · 1440 에서 1줄 · 'YYYY-MM-DD HH:MM:SS KST · 네이버' |
| 「종목 관리」 · History | 상단 일괄 버튼 · 표 아래 건수 · History 이름 · [시장 흐름 보기] | 일괄 버튼 0개 · '보유 행 M개 · 수익률은 …' · History '비교 시작일' 보임 · [시장 흐름 보기] '비교 시작일부터 종가 변화' 보임 · 창 안 '가격 비교 기준일' 0 |
| 「확인 근거」 | 모든 보유 행을 차례로 펼쳐 상세 위치 · 순위 글 · 조건 줄 · 구성종목 중복 · 묶음 아래 · 옛 이름 · 진입마다 주간 요청 | 상세가 누른 행 묶음 안(전 행) · 순위 글은 모두 판정 §1 글 규칙 안(종류 · 건수는 보유 집계라 적지 않음) · 조건 줄 '「주간 ETF 점검」과 같은 조회 · 1개월 수익률 상위 30 · 기간 · 인버스 · 레버리지 · 합성 · 선물 제외' · 첫 줄 '비교 범위 확인 불가' · '마지막 저장일 D · PC 저장 종가 / 마지막 저장일 D / 마지막 유효 가격일 D' · 옛 이름(1개월 상위 30 중 · Market Discovery · PC 가격 흐름 기준일 · PC 비교 기준일 · '시장 기준일 ') 0 · 1차 진입 주간 요청 1 · 다른 화면 다녀온 2차 진입 1 |
| 「데이터 상태」 | 표 머리 · 요약 날짜 이름 · 영어 상태값 | 머리 '코드 · ETF명 · NAV · 시장가 · 괴리율 · 기준일 · 출처 · 수집 상태' · 운영 자료에 재저장 행이 없어 '가장 최근 기준일' · 표 안 영어 상태값(ok · partial · unavailable · naver_etf_item_list) 0 |

- 운영 백엔드는 다시 띄우지 않았다(바뀐 백엔드 코드는 `app/holdings_reference_date.py` 머리 주석뿐 · API 동작 무변경). 운영 화면(3000 · next dev)은 바뀐 파일을 다시 읽어 위 결과를 보였다.
- **문서 커밋:** 설계 · PLAN 판정 · RESULT 판정 · PLAN · 목업 · 이 결과서 · STATE · PROGRAM_TRUTH 반영일을 main 에서 한 커밋으로 남긴다(커밋 번호는 이 문서에 적지 않음 · `git log` 로 확인).
- **남은 일:** push · 격리 서버(8001 · 3001) 정지 · 격리 작업 사본 · 브랜치 삭제(형수님 별도 승인) → 종료 기록.
