# POC5-22 개발 PLAN V1 — PC 후보와 KODEX200의 동일 기간 수익률 비교

작성 2026-10-17 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-22_PC_SAME_PERIOD_KODEX200_COMPARISON_DESIGN_V1.md`(V1) · 판정 `docs/ai_design/POC5/POC5-22_PC_SAME_PERIOD_KODEX200_COMPARISON_PLAN_DECISION_2026-10-17.md`

```text
STATUS   = PLAN V1 · 전체 화면 목업 사용자 확인(2026-10-17 '좋습니다. 진행해주세요.' · 권장안 (a) 기준 목업) → 설계자 PLAN 판정 PASS(2026-10-17 · Q1 · Q2 · Q3 모두 (a) · §6) → 구현(재제출 · 추가 목업 없음) → 검증자 r1 VERIFIED(2026-10-18) → 설계자 RESULT PASS · IMPLEMENTED_VERIFIED_CLOSED(종료 2026-10-18 · 결과서 §11)
SCOPE    = 후보 1개월 · 3개월 KODEX200 대비 칸(「요즘 잘 오르는 ETF」 카드 · 표 · 공통 복사문 · 「ETF 비교하기」 · 「보유와 비교」) · AI 전달 candidate_snapshot 선택 필드
           새 메뉴 · 카드 · 순위 · 필터 · API 경로 · DB 표 · 추가 SELECT · 외부 조회 · 의존성 · OCI · PUSH · PARAM 변경 0 · 단기 5/10/20 · 6M · 12M · 3Y 비교 추가 없음
MEASURED = 2026-10-17 · 시장 DB 읽기 전용 사본(시장 저장 최신일 2026-10-14) · 코드 경로 grep / read
```

## 1. 세 화면의 실제 이용 필드 (현재 코드)

| 화면 · 자리 | 지금 쓰는 값 | 출처 응답 |
|---|---|---|
| 「요즘 잘 오르는 ETF」 카드 'KODEX200 대비 1M' · 펼침 '3M' · 표 두 열 · 위 비교 줄(POC5-21) | `excess_return.vs_kodex200_1m_pctp` · `_3m_pctp` | PC `GET /market/topn/latest`(n=10) |
| 공통 복사문 [KODEX200 대비 수익률 차이] · AI 세션 `market_context_snapshot.candidate_excess_returns` | 같은 두 값 | 같은 응답(전달 초안) |
| 「ETF 비교하기」 후보 탭 'KODEX초과' 칸 · 정렬 · 상세 'KODEX 초과' | `candExcess` = `vs_kodex200_1m_pctp` | PC `GET /market/topn/latest`(n=30) |
| 「ETF 비교하기」 보유 탭 'KODEX초과' · 상세 칸의 보유 대체값 | `evidenceExcess` = 보유 근거 `excess_return.vs_kodex200_1m_pctp` | `GET /holdings/market-evidence/latest` — 이 API 가 `compute_topn`(n=10 · 기본)을 따로 돌려 **상위 10 후보에 든 보유 종목만** 후보 값을 옮겨 담는다(지금 보유 29종목 중 0개 → 모두 '—') → Q2 |
| 「보유와 비교」 후보 카드 '20일 KODEX 초과' | **`vs_kodex200_1m_pctp`(1개월 값)** — 칸 이름 · 정렬(`short_term_momentum.excess_vs_kodex200_20d_pctp`) · 보유 쪽 칸(같은 20일 단기 값)과 다름(2026-08-16 카드 전환 `edd7fdeb` 때 생김) | PC 시장 응답 → Q3 |
| 「보유와 비교」 보유 카드 · 상세 5 / 10 / 20일 · 「확인 근거」 · 「오늘의 투자 점검」 | 단기 흐름 20(5 · 10)거래일 차이(보유 근거 · 같은 행 위치) | 별도 단기 계산 — 이번 대상 아님(설계 §2) |

- 지금 차이 값 = 후보 1개월 · 3개월(시장 저장 최신일에서 달력 30 · 90일 · 실제 행 A → B) − KODEX200 1M · 3M(마지막 행에서 20 · 60 저장일 앞) → 기간이 다르다(POC5-21).

## 2. 계산 · 전달 (PC 선택 경계)

- 후보 A · B = `_compute_period` 가 실제로 고른 시작 · 끝 행(POC5-21 `price_start_date` · `price_end_date` · 짧은 이력은 첫 저장 행).
- 후보 수익률 = 그 계산의 반올림 전 값(`_PeriodResult.return_pct` · 단위 %) — 응답 `return_pct` 는 소수 4자리.
- KODEX200 = `compute_topn` 이 시장 판정용으로 이미 읽은 069500 이력(`fetch_price_history` · close > 0 · 2014-04-09 ~)을 한 번 {날짜: 종가}로 정리해 A · B 와 **같은 날짜**의 종가만 쓴다(전후 · 최근 · 보간 없음). 후보마다 다시 읽지 않는다.
- 동일 기간 차이(%p) = 후보 수익률 − KODEX200 수익률(둘 다 반올림 전 · 저장은 소수 4자리).
- 선택 필드(후보마다 · `compute_topn(same_period_kodex200=True)` 일 때만 · 기본 False 는 출력 그대로):

```text
same_period_kodex200 = {
  one_month:   {status, reason, start_date, end_date, candidate_return_pct, kodex200_return_pct, diff_pctp},
  three_month: {…}
}
status = ok | unavailable
reason = candidate_period_unknown(후보 값 · 실제 기간 없음) | kodex200_start_price_missing | kodex200_end_price_missing
단위   = candidate_return_pct · kodex200_return_pct = % · diff_pctp = %p · 소수 4자리 · 계산 불가면 값 null(0 · 다른 차이로 채우지 않음)
```

- 화면 API 만 켠다(`GET /market/topn/latest` · Q2 (a) 면 보유 근거 API 도). 기존 `excess_return.*` · `basis_*` · `market_context.kodex200.return_1m_*`(POC5-21) 의미 · 값 그대로. 새 필드가 없는 응답(이전 응답 · 다른 호출)은 '동일 기간 값 없음'으로 보이고 기존 차이로 대신하지 않는다.
- 실측(사본 · 1개월 상위 10): 10개 모두 2026-09-14 → 10-14 · KODEX200 −9.86% → 1위 동일 기간 +32.13%p(기존 기간 다른 차이 +37.33). 3개월 상위 10: 9개 07-16 → 10-14 · KODEX200 −12.65% · 짧은 이력 0223A0 07-28 → 10-14 · KODEX200 −0.49% → +31.73%p(기존 +44.47). 상위 30 · 1M / 3M 의 A · B 는 KODEX200 에 모두 있다.

## 3. 화면 · 복사문 · AI 자료

- 공통 helper 하나(`lib/samePeriodKodex.ts` · 값 / 계산 불가 사유 / 값 없음)와 작은 표시 컴포넌트를 세 화면 · 복사문 · AI 자료가 함께 쓴다.
- 「요즘 잘 오르는 ETF」: 카드 'KODEX200 대비 1M'(펼침 3M) · 표 두 열을 **동일 기간** 값(%p)으로 교체. 위 둘째 줄(POC5-21 '기간 다른 수익률 차이')을 '동일 기간 KODEX200 대비 1M · 3M — 후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 계산 (%p)'로 바꾸고, 그 ? 에 기간별(같은 A · B 묶음) KODEX200 수익률 · 뺄셈 뜻 · 저장 종가(배당 포함 총수익 아님). 계산 불가는 칸에 짧은 사유(회색 · 위험 표시 아님).
- 「ETF 비교하기」: 후보 탭 칸 · 정렬 · 상세 칸을 같은 값으로(상세는 '후보 +x% · KODEX200 +y% · A → B' 한 줄로 양쪽 수익률 · 기간 확인). `JudgmentWorkbenchView.tsx` 849줄 → 늘리지 않게 helper 쪽에서 처리.
- 공통 복사문: [KODEX200 대비 수익률 차이] → [동일 기간 KODEX200 대비] — '1개월: +32.13%p (후보 +22.27% · KODEX200 −9.86% · 사용 종가 2026-09-14 → 2026-10-14)' · 계산 불가 사유 · 이전 '기간 다름' 설명 줄 삭제 · [요청] 문구 정정. 단기 흐름 줄은 21 그대로.
- AI 자료: 새로 만드는 전달 초안의 `candidate_snapshot` 항목에 같은 `same_period_kodex200` 객체를 선택 필드로(`toDecisionCandidateSnapshot` · 'AI Sessions로 넘기기' · ETF 구성종목 초안). 백엔드 저장 모델 `DecisionCandidateSnapshot` 에 선택 필드 1개(지금은 모르는 필드를 버림 · 표 구조 · 마이그레이션 없음 · JSON 안). 과거 기록은 그대로('당시 자료 없음').

## 4. 변경 파일 · 시험

- 백엔드: `app/market_topn.py`(flag · 정리 1회 · 후보별 객체) · 새 작은 모듈 `app/same_period_kodex200.py`(순수 계산 · 연구 모듈 import 없음) · `app/api_market_topn.py` · `app/api_market_topn_models.py` · `app/api_market_topn_service.py` · `app/api_decision_sessions.py`(선택 필드) · (Q2 (a)) `app/api_holdings_market_evidence.py` + 모델.
- 프론트: 신규 `lib/samePeriodKodex.ts` · 표시 컴포넌트 · 수정 `CandidateCards` · `CandidateTable` · `ReturnPeriodLine` · `lib/returnPeriod.ts`(21 의 기간 다름 비교 helper 정리) · `lib/marketDiscoveryCopyText.ts` · `workbench/helpers.ts` · `JudgmentWorkbenchView.tsx` · (Q2) `workbench/HoldingTable.tsx` · (Q3) `holdings_compare/CompareCards.tsx` · `TransferToAISessionsCard.tsx` · `lib/etfExposureDraft.ts` · `lib/api/decisionSessions.ts` · `lib/api/market.ts`.
- 시험: 알려진 두 가격 계산 예(+10% · +5% → +5%p) · 실제 A · B 선택 · 짧은 이력 · 정확한 날짜 결측(시작 · 끝) · 0 이하 · 빈 종가 · 후보 기간 없음 · 이전 응답에 새 필드 없음 · 기본 호출 출력 · 수익률 · 순위 · 조회 수 불변 · KODEX200 재조회 0 · 화면 = 복사문 = AI 스냅샷(같은 날짜 · 수치) · 세 화면 같은 helper · 저장 모델 왕복 · 변이 · 백엔드 · 프론트 회귀 · 타입 · 린트.
- 목업(로컬 · 게시 안 함): 1440 · 1000px 「요즘 잘 오르는 ETF」 카드 · 표 / 「ETF 비교하기」 후보 · 상세 / 「보유와 비교」 — 정상 · 짧은 후보 이력(3개월 기준 실제) · 후보 끝일이 이른 경우 · KODEX200 필요한 날짜 없음 · 이전 응답(격리 fixture).

## 5. 질문 (설계자 판단 · 권장은 (a))

### Q1. 가격 기준 연결 확인
기존 PC 가격 기준 규칙(POC5-06 `link_break` · POC5-16 · 20 재사용)은 행마다 자료원 · 저장 change 가 필요한데, 후보 계산(`compute_topn`)은 날짜 · 종가만 읽는다. 비교 대상인 후보 수익률 자체도 연결 확인 없이 계산된 값이다. 실측(상위 30 · 1M / 3M 창 · 후보 · KODEX200)은 끊김 0.
(a) 같은 종가만 쓰고 연결 확인은 하지 않는다 — ? · 복사문에 '저장 종가 · 가격 기준 연결 미확인(후보 수익률과 같은 기준)'을 적고 BACKLOG 관찰. 읽기 · 연구 모듈 import 변화 0. · (b) PC flag 일 때만 같은 조회에 자료원 · change 열을 더 읽어 A → B 사이 `link_break` 를 후보 · KODEX200 에 적용(끊기면 `price_basis_unconfirmed` · 연구 모듈은 flag 안에서만 import) — 조회 수는 같지만 1,195종목 읽기 열이 늘고 PC 경로의 읽기 함수가 기본 경로와 갈린다.

### Q2. 「ETF 비교하기」 보유 탭 · 상세 대체값
보유 근거 API 가 따로 돌린 후보 계산(n=10)의 기간 다른 1M 차이를 상위 10 안 보유 종목에만 옮긴다(지금 0종목).
(a) 그 API 도 같은 flag 로 계산하고 PC 응답 사본에만 같은 `same_period_kodex200` 를 붙여(공유 builder 불변 · POC5-09 사본 방식) 보유 탭 · 상세도 같은 helper 로 표시 · (b) 이번 범위 밖 — 보유 탭은 그대로 두고 칸 이름만 '기간 다른 차이'로 구분.

### Q3. 「보유와 비교」 후보 카드 '20일 KODEX 초과'
칸 이름 · 정렬 · 보유 쪽 칸은 20일 단기 값인데 후보 카드 숫자만 1개월 값이다.
(a) 후보 카드 숫자를 단기 20일 값(`short_term_momentum.excess_vs_kodex200_20d_pctp`)으로 바로잡아 이름 · 정렬 · 보유 쪽과 맞춘다(단기 흐름 = 21 계약 · 이 화면은 1M 칸이 없어짐) · (b) 동일 기간 1M 값으로 바꾸고 칸 이름을 '동일 기간 KODEX200 대비 1M'로(보유 쪽 20일과 다른 지표가 나란히 · 정렬 기준은 별도 정리 필요).

## 6. 설계자 PLAN 판정 반영 (2026-10-17 · PASS · 재제출 없이 구현)

- Q1 (a): 후보 계산과 같은 저장 날짜 · 종가만 쓴다(자료원 · change 열 확장 · 연결 검사 없음 · 연구 모듈 import 없음). 도움말과 복사문 공통 설명에 한 번 '저장 종가로 계산하며 가격 조정 기준의 연속성은 검사하지 않습니다.'(칸마다 경고 · 새 배지 없음). `status=ok` = 필요한 날짜 · 유효 가격으로 산술 비교가 됐다는 뜻(연결 확인 아님). 상위 30 창 끊김 0 은 참고 관측. BACKLOG 관찰로 보존(자동 후속 단계 없음). 정확한 A · B · 양수 · 유한 종가 · 다른 날짜로 대체 안 함은 유지.
- Q2 (a): 보유 근거 API 의 PC 응답 사본에 `same_period_kodex200`(상위 10 후보와 연결된 보유 종목만 · 기존 제공 범위) · 보유 탭 · 상세는 같은 helper. 없으면 '동일 기간 값 없음'(기간 다른 값 · 단기 20구간 값으로 채우지 않음) · 상위 10 밖 보유 종목의 새 계산 경로 없음 · 공유 builder 불변 · 가용 범위는 결과서에 명시.
- Q3 (a): 「보유와 비교」 후보 카드 숫자 = 기존 단기 20구간 값(정렬 · 보유 카드와 같은 지표) · 칸 이름 '20구간 KODEX200 차이' · %p · 1/3개월 값을 넣지 않음 · 그 단기 값의 비교 날짜를 맞췄다고 기록하지 않음.
- 그 밖: 반올림 전 값으로 빼고 마지막에 소수 4자리 · 추가 SELECT · 외부 조회 없이 이미 읽은 069500 이력을 한 번 정리 · 다른 호출 · 공유 builder · `excess_return.*` · `basis_*` · 시장 판정 · PUSH 그대로 · 「ETF 비교하기」 기존 사용자 선택 KODEX 정렬은 새 표시값으로 정렬 · 「보유와 비교」 20구간 정렬 그대로 · 새 `candidate_snapshot.same_period_kodex200` 와 질문 본문 · 화면이 같은 객체 · `market_context_snapshot.candidate_excess_returns` 는 기존 정의대로 보존(새 값의 입력 · 대체값 아님) · 1/3개월과 단기 20구간은 서로 바꿔 끼우지 않음.
- 시험 보충: Q1 미검사 설명(도움말 · 복사문 한 번) · Q2 자료 없음 · Q3 표시 숫자와 20구간 정렬의 연결 · 「ETF 비교하기」 사용자 정렬 = 표시값.
