# POC5-22 개발 결과서 — PC_SAME_PERIOD_KODEX200_COMPARISON (PC 후보와 KODEX200 의 동일 기간 수익률 비교)

작성 2026-10-18 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 구현 완료(2026-10-18) → 사용자 실화면 확인(2026-10-18 '확인했습니다.') · 사용자 직접 요청 UI(빠른 선택 버튼 중간 크기 · §4) 실화면 확인(2026-10-18 '확인했습니다.') → 검증자 r1 VERIFIED(2026-10-18 · §10) → 설계자 RESULT PASS · 종료(2026-10-18 · §11)
VERIFIER      = Codex · r1 VERIFIED · backend 관련 113 passed · frontend 관련 98 passed · 타입·린트·구문 검사 통과
STEP_ID       = POC5-22 PC 후보와 KODEX200 의 동일 기간 수익률 비교
DESIGN        = docs/ai_design/POC5/POC5-22_PC_SAME_PERIOD_KODEX200_COMPARISON_DESIGN_V1.md
PLAN          = docs/ai_plan/POC5/POC5-22_PC_SAME_PERIOD_KODEX200_COMPARISON_PLAN_V1.md(§6 판정 반영)
DECISION      = docs/ai_design/POC5/POC5-22_PC_SAME_PERIOD_KODEX200_COMPARISON_PLAN_DECISION_2026-10-17.md(PASS · Q1 · Q2 · Q3 모두 (a))
USER_MOCKUP   = 목업 확인 2026-10-17 '좋습니다. 진행해주세요.'(권장안 (a) 기준 · 로컬 · 게시 안 함)
BASE_COMMIT   = 05093286 (POC5-21 종료)
SCOPE         = 후보 1개월 · 3개월 KODEX200 대비 칸 — 「요즘 잘 오르는 ETF」 카드 · 표 · 위 둘째 줄 · 공통 AI 복사문 · 「ETF 비교하기」 후보 · 보유 탭 · 상세 ·
                「보유와 비교」 후보 카드(Q3 정정) · AI 전달 candidate_snapshot 선택 필드
                새 메뉴 · 카드 · 순위 · 필터 · API 경로 · DB 표 · 추가 SELECT · 외부 조회 · 의존성 · OCI · PUSH · PARAM · cron 변경 0
CHECKS        = §8
```

## 0. 요약

- **계산(설계 §3 · 판정 §2)**: 후보 수익률이 실제로 쓴 시작 · 끝 저장 행(A · B · `_compute_period` 가 고른 행 · 짧은 이력은 첫 저장 행)의 **같은 날짜** KODEX200(069500) 저장 종가로 KODEX200 수익률을 다시 계산하고, 반올림 전 후보 수익률에서 뺀 차이(%p)를 마지막에 소수 4자리로 전달한다. 전후 날짜 · 최근 날짜 · 보간 없음 · 양수 · 유한 종가만.
  - 순수 계산 모듈 `app/same_period_kodex200.py`(조회 · 연구 모듈 import 없음 · `compare` · `close_by_date`).
  - `compute_topn(same_period_kodex200=True)` — 시장 판정용으로 이미 읽은 069500 이력을 한 번 {날짜: 종가}로 정리해 후보마다 1개월 · 3개월 객체를 더한다(추가 조회 0). 기본 False 는 출력 그대로.
  - 객체: `{status: ok|unavailable, reason, start_date, end_date, candidate_return_pct(%), kodex200_return_pct(%), diff_pctp(%p)}` · reason = `candidate_period_unknown` · `kodex200_start_price_missing` · `kodex200_end_price_missing` · 계산 불가면 값 null(0 · 기존 차이로 채우지 않음 · 후보 수익률은 남김).
  - `status=ok` 는 필요한 날짜 · 유효 가격으로 산술 비교가 됐다는 뜻이다. 가격 조정 기준(자료원 · change)의 연속성은 검사하지 않는다(판정 Q1 (a)).
- **전달(설계 §4 · 판정 Q2 (a))**: `GET /market/topn/latest` · `GET /holdings/market-evidence/latest` 두 PC API 만 flag 를 켠다.
  - 시장 응답: 후보 선택 필드 `same_period_kodex200`(모델 `SamePeriodKodex200`).
  - 보유 근거 응답: PC 사본의 보유 항목에 같은 객체 — 이 API 가 돌리는 후보 계산(상위 10)과 연결된 보유 종목만(기존 `excess_return` 과 같은 제공 범위). 연결 안 된 종목은 None. 공유 builder 는 그대로다.
  - 기존 `excess_return.*`(기간 다른 차이) · `basis_*` · POC5-21 `market_context.kodex200.return_*_date` · 시장 판정 · 다른 호출 6곳(`draft` · `draft_three_push` 2 · `ml_score_validity_screen` · `api_decision_draft_preview` 2 · 보유 근거 API 는 이번에 flag 를 켬) 출력은 그대로.
- **화면(공통 helper `lib/samePeriodKodex.ts` · 칸 컴포넌트 `SamePeriodValue.tsx`)**
  - 「요즘 잘 오르는 ETF」: 카드 '동일 기간 KODEX200 1M' · 펼침 '동일 기간 KODEX200 3M' · 표 두 열을 동일 기간 값(%p)으로 교체(기존 기간 다른 값은 화면에서 빠짐). 위 둘째 줄 「동일 기간 KODEX200 대비 1M · 3M — 후보와 같은 시작 · 끝 날짜의 KODEX200 종가로 뺀 차이 (%p)」(+ 'n칸 계산 불가 · n칸 값 없음') · 그 ? = 뺄셈 뜻 · 예(+10% · +5% → +5%p) · 같은 기간 묶음별 KODEX200 수익률 · 뜻 · 한계 문장 한 번.
  - 계산 불가 = 그 칸에 회색 짧은 사유(위험 표시 아님 · `.sp-na`). 응답 전체에 새 객체가 없으면 위 줄 '응답에 동일 기간 비교가 없습니다' 한 번 · 칸 '—'.
  - 「ETF 비교하기」: 후보 칸 · 기존 사용자 선택 정렬 '동일기간 KODEX 1M'(정렬 값 = 칸 값 · 계산 불가 · 없음은 기존 정렬 규칙대로 −∞ — 내림차순이면 맨 뒤 · 오름차순이면 맨 앞) · 보유 탭 같은 칸(보유 근거 사본 객체 · 없으면 '동일 기간 값 없음') · 상세 '동일 기간 KODEX200 대비 1M — +x%p — 후보 +a% · KODEX200 +b% · 사용 종가 A → B'(후보에 있으면 후보 객체 · 보유만 고르면 보유 근거 객체).
  - 「보유와 비교」(판정 Q3 (a)): 후보 카드 숫자를 기존 단기 20구간 값(`short_term_momentum.excess_vs_kodex200_20d_pctp` · 이 화면 정렬과 같은 값)으로 바로잡고, 두 카드 칸 이름을 '20구간 KODEX200 차이' · %p 로(§4). 1/3개월 값은 넣지 않는다.
- **복사문 · AI 자료**: 공통 생성기 [KODEX200 대비 수익률 차이](POC5-21) 섹션 → [동일 기간 KODEX200 대비] · '- 차이(%p) = … 저장 종가로 계산하며 가격 조정 기준의 연속성은 검사하지 않습니다.' 한 번 · 후보마다 '동일 기간 KODEX200 대비 1개월: +32.13%p (후보 +22.27% · KODEX200 -9.86% · 사용 종가 2026-09-14 → 2026-10-14)' · 계산 불가 '계산 불가 — 사유 (후보 기간 A → B)' · 없음 '동일 기간 값 없음' · [요청] '동일 기간 KODEX200 대비 수익률 차이'. 이전 '기간 다른 수익률 차이' 설명은 남기지 않음. 새 전달 초안의 `candidate_snapshot` 항목에 같은 객체(`same_period_kodex200` · 없으면 null) · 백엔드 저장 모델 `DecisionCandidateSnapshot` 선택 필드(JSON 안 · 표 구조 · 마이그레이션 없음). 기존 `market_context_snapshot.candidate_excess_returns` 는 기존 정의대로 보존.
- **실제 PC 응답(2026-10-18 · 사용자 백엔드 `--reload` · GET 읽기만 · 시장 저장 최신일 2026-10-14)**: 1위 후보 1M `diff_pctp` +32.1304 · KODEX200 −9.8615 · 3M +46.4479 · 표시 10후보 × 2기간 20칸 모두 `ok`. 보유 근거 32줄 모두 키 있음 · 값 0줄(지금 보유 종목 중 상위 10 후보에 든 것 없음).

## 1. 처리한 요구사항

| 출처 | 요구 | 상태 |
|---|---|---|
| 설계 §2 | 1개월 · 3개월 KODEX200 대비 칸 · 「요즘 잘 오르는 ETF」 카드 · 표 · 공통 복사문 | DONE |
| 설계 §2 · 판정 Q2 · Q3 | 「ETF 비교하기」 · 「보유와 비교」 같은 지표 연결 · 실제 이용 필드 확인 · 다른 계산 계약은 보고 | DONE(PLAN §1 · 보유 탭 = 보유 근거 사본 · 「보유와 비교」 = 20구간으로 정정) |
| 설계 §2 | 6개월 이상 · 새 메뉴 · 카드 · 순위 · 필터 없음 · 후보 수익률 · 선정 · 정렬 유지 · 단기 5/10/20 은 21 계약 유지 | DONE |
| 설계 §3 | 같은 A · B · 같은 날짜 양수 종가 · 반올림 전 값 뺄셈 · 비율로 나누지 않음 · 계산 불가 사유 구분 · 0 · 다른 차이로 채우지 않음 · 후보 수익률 숨기지 않음 | DONE |
| 설계 §3 · 판정 Q1 | 가격 기준 연결 = 이번에 검사하지 않음 · 한계 문장 한 번(도움말 · 복사문) · ok = 산술 비교 가능 | DONE |
| 설계 §3 | 저장 종가 같은 기간 비교 · 총수익 · 개인 손익 · 우위 지속 보증으로 설명 안 함 | DONE(? · 복사문 설명) |
| 설계 §4 | 후보별 선택 필드(A · B · 양쪽 수익률 · 차이 · 상태 · 사유) · 필드명 · 단위 고정 | DONE(§0) |
| 설계 §4 | 기존 다른 기간 차이 · `basis_*` 보존 · 새 필드 없으면 기존 값으로 대체 안 함 | DONE |
| 설계 §4 | PC API 선택 경계에서만 · 이미 읽은 KODEX200 한 번 정리 · 추가 조회 0 · 기본 호출 출력 · 계산 · 조회 수 유지 · 연구 모듈 import 없음 | DONE(§8) |
| 설계 §4 · 판정 §2 | 새 AI 전달 자료 `candidate_snapshot.same_period_kodex200` · 질문 본문과 같은 날짜 · 수치 · 과거 기록 그대로 · 보유 수량 · 평단 · 손익 없음 | DONE |
| 설계 §5 | '동일 기간 KODEX200 대비'로 교체(나란히 두지 않음) · 21 기간 표시 재사용 · 차이 기본 + ? 에 기간 · 양쪽 수익률 · 뜻 · 계산 불가 짧은 사유 · 기존 색 | DONE |
| 설계 §5 | 세 화면 · 복사문이 같은 객체 · 같은 helper · 이전 '기간 다른' 설명 삭제 · 매매 의견 · 위험 순위 없음 | DONE |
| 판정 §2 | 「ETF 비교하기」 사용자 선택 KODEX 정렬 = 새 표시값 · 「보유와 비교」 20구간 정렬 그대로 | DONE |
| 판정 §2 | 1/3개월과 단기 20구간을 서로 바꿔 끼우지 않음 | DONE |
| 설계 §6 | 목업 1440 · 1000px · 사용자 확인 | DONE(2026-10-17) |
| 설계 §6-3 · 판정 §2 | 시험(계산 예 · A · B · 짧은 이력 · 날짜 결측 · 유효하지 않은 가격 · 이전 응답 · Q1 설명 · Q2 자료 없음 · Q3 숫자 = 20구간 정렬 · KODEX 정렬 = 표시값 · 화면 = 복사문 = 스냅샷 · 기존 호출 · 수익률 · 순위 · 조회 수 불변) · 회귀 · 타입 · 린트 | DONE(§8) |
| 설계 §6 | 사용자 실화면 · 검증자 | 실화면 DONE(2026-10-18 '확인했습니다.') · 검증자 r1 VERIFIED(§10) |

## 2. 변경된 파일 목록

- 백엔드 신규: `app/same_period_kodex200.py`
- 백엔드 수정: `app/market_topn.py` · `app/api_market_topn.py` · `app/api_market_topn_models.py` · `app/api_market_topn_service.py` · `app/api_holdings_market_evidence.py` · `app/api_decision_sessions.py`
- 프론트 신규: `frontend/lib/samePeriodKodex.ts` · `frontend/app/components/SamePeriodValue.tsx`
- 프론트 수정: `CandidateCards.tsx` · `CandidateTable.tsx` · `ReturnPeriodLine.tsx` · `MarketDiscoveryView.tsx` · `JudgmentWorkbenchView.tsx` · `workbench/HoldingTable.tsx` · `workbench/helpers.ts` · `holdings_compare/CompareCards.tsx` · `TransferToAISessionsCard.tsx` · `frontend/app/globals.css` · `frontend/lib/returnPeriod.ts` · `frontend/lib/marketDiscoveryCopyText.ts` · `frontend/lib/etfExposureDraft.ts` · `frontend/lib/api/market.ts` · `frontend/lib/api/holdings.ts` · `frontend/lib/api/decisionSessions.ts`
- 시험 신규: `tests/test_poc5_22_same_period_kodex200.py` · `frontend/lib/samePeriodKodex.test.ts` · `frontend/app/components/holdings_compare/CompareCards.test.tsx` · `frontend/app/components/TransferToAISessionsCard.test.tsx`
- 시험 수정: `frontend/app/components/CandidateCards.test.tsx` · `ReturnPeriodLine.test.tsx` · `JudgmentWorkbenchView.test.tsx` · `RejectedScoreCloseout.test.tsx` · `frontend/lib/marketDiscoveryCopyText.test.ts` · `frontend/lib/returnPeriod.test.ts`
- 문서: 설계 V1 · PLAN 판정 · PLAN V1 · 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

- **POC5-21 의 '기간 다른 비교' 판정 삭제**: `lib/returnPeriod.ts` 의 `kodexRange` · `cmpState` · `cmpGroup` · `cmpLabel` · `cmpNote` 와 그 시험, 복사문의 1/3개월 비교 꼬리를 지웠다(새 동일 기간 값으로 교체 · 설계 §5 '나란히 두지 않음'). 단기 흐름 5/10/20 의 두 기간 꼬리(`compareTail`)는 21 계약대로 남긴다. 화면이 쓰지 않게 된 `ReturnPeriodLine` · `CandidateCards` · `CandidateTable` 의 `kodex` prop 과 `MarketDiscoveryView` 의 전달 2줄을 지웠다(866 → 864줄).
- **POC5-21 백엔드 필드는 그대로**: `market_context.kodex200.return_1m_start_date` · `return_3m_start_date` · `return_end_date`(21 PC 전용 선택 필드)는 응답에 남는다(화면이 더는 쓰지 않음 · 계약 · 출력 보존).
- **「보유와 비교」 칸 이름 두 카드 모두**: 판정 Q3 '해당 칸 = 20구간 KODEX200 차이 · %p' 를 후보 카드와 같은 지표인 보유 카드 칸에도 적용했다(같은 화면 · 같은 값 · 이름이 갈리면 혼동). 정렬 버튼 이름('20일 초과')은 바꾸지 않았다.
- **「ETF 비교하기」 칸 이름**: 좁은 3칸 자리라 '동일기간 KODEX 1M'(상세 칸은 '동일 기간 KODEX200 대비 1M').
- **? 묶음 순서**: 같은 수의 묶음은 시작일 → 끝일 순(변이 F10 을 잡는 시험을 더하면서 순서를 정함).
- **보유 근거 API flag**: 이 API 의 후보 계산에도 flag 를 켰다(같은 객체를 옮기기 위함 · 공유 builder 는 그 키를 쓰지 않음 · 응답 변화는 새 선택 필드뿐 · §8).
- **AI 세션 저장**: 새 기록의 `candidate_snapshot` 항목은 값이 없을 때도 `same_period_kodex200: null` 키가 생긴다(모델 기본값 · 다른 키 · 값 그대로).
- **사용자 직접 요청 UI(2026-10-18 · 실화면 확인 완료 '확인했습니다.' · UI 전용)**: 「ETF 비교하기」 빠른 선택 버튼 4개(전체 · 보유 중 · 비교 가능 · 확인 필요 · `.wb-filter`)를 POC5-UI-01 중간 버튼 규격(높이 40px · 글자 14px · 좌우 12px)으로 — 사용자 '중간크기로만 변경해주세요'. `frontend/app/globals.css` 만(UI-01 '선택 묶음' 제외 목록에서 빼고 중간 버튼 목록에 넣음) · 둥근 모양 · 색 · 동작 그대로 · 이 클래스는 이 화면에서만 쓴다.
- **독립 검토 반영 정리**: 호출처가 없어진 `workbench/helpers.ts :: evidenceExcess` 삭제(보유 탭 칸은 `HoldingTable` 이 `sameViewOf` 로 직접) · 21 '비교 묶음' · 'KODEX초과' 낡은 주석 정정 · `market_topn.py` 새 import 를 POC2 re-export 주석 위로 · `returnPeriod.test.ts` 안 쓰는 인자 삭제 · `.sp-na` 를 `!important` 없이 같은 무게 선택자로.

## 5. 알려진 한계 / 미완성

- **가격 조정 기준 연속성 미검사(판정 Q1 (a))**: 후보 수익률과 같은 저장 종가만 쓴다. 상위 30 · 1M / 3M 창의 연결 끊김 0 은 개발자 조사 범위의 참고 관측이다(전체 이력 검증 아님 · BACKLOG 관찰).
- **보유 탭 · 보유 근거 가용 범위(판정 Q2)**: 보유 근거 API 가 돌리는 후보 계산 상위 10 과 연결된 보유 종목만 값이 있다. 지금 보유 29종목 중 0종목 → 보유 탭 칸은 모두 '동일 기간 값 없음'. 상위 10 밖 보유 종목의 새 계산 경로는 만들지 않았다.
- **「보유와 비교」 20구간 값**: 기존 단기 계산(저장 행 위치 기준) 그대로다. 이 값의 비교 날짜를 이번에 다시 맞췄다고 기록하지 않는다.
- 끝일이 이른 후보 · KODEX200 날짜 없음 · 이전 응답 상태는 실제 사례가 없어 격리 fixture(목업 · 시험)로만 확인했다.
- 동일 기간 값은 저장 종가 같은 기간 비교다(배당 포함 총수익 · 개인 손익 · 우위 지속 아님 · ? · 복사문에 명시).
- 이 작업 전에 만든 전달 초안(브라우저 세션)으로 복사문을 다시 만들면 새 객체가 없어 '동일 기간 값 없음'으로 나온다.
- 「ETF 비교하기」 보유 탭 '확인 필요' 배지는 기존대로 보유 근거의 `excess_return.status` 등으로 판정한다(`holdingNeedsAttention`). 상위 후보와 연결된 보유 종목에서 KODEX200 날짜가 없어 동일 기간 칸만 '계산 불가'인 경우 배지는 정상으로 남을 수 있다(칸에 사유는 보임 · 확인 필요 수 계약은 바꾸지 않음).
- 「보유와 비교」 정렬 버튼('20일 초과') · 상세 '후보 흐름'('KODEX 대비 초과수익 · 20d · %') · 보유 상세('20일 · %')의 이름 · 단위는 그대로다(판정 Q3 의 칸 이름 · %p 는 두 카드 칸에만 적용).

## 6. 다음 검증자(Codex)에게 알릴 점

- 기본 호출 불변 근거: (1) 시험 `test_flag_off_unchanged_and_flag_only_adds_object`(기준 3 × 정렬 2 · flag 켠 출력에서 새 키를 빼면 기본 출력과 같음) · (2) 사본 DB(`mode=ro` 백업) · 사본 상태 폴더 변경 전후 실측 — `compute_topn` 기본 호출(기준 3 × 정렬 2 · n=30) + POC5-21 인자 호출 = **바뀐 값 · 추가 키 0** · PC 시장 응답 = 후보 10개에 `same_period_kodex200` 추가만 · 보유 근거 응답 = 32줄에 `same_period_kodex200` 키 추가만(값 변화 0).
- 추가 조회 0: 시험이 `fetch_price_history` 호출 목록(069500 포함)이 flag 켜고 끔에 같은지 본다.
- 연구 모듈: 새 서브프로세스에서 `app.market_topn` · `app.same_period_kodex200` 만 import 했을 때 `app.reentry_review.prices` · `app.pc_price_volatility` 가 실리지 않는지 본다(보유 근거 API 는 POC5-16 부터 `pc_price_volatility` 를 이미 import — 기존 그대로).
- 화면 = 복사문 = 스냅샷: 같은 `sameViewOf` · `sameCopyText` · 같은 응답 객체. 시험이 카드 칸 값과 복사문 줄 · 초안 `candidate_snapshot` 객체와 질문 본문 줄을 대조한다.
- 독립 검토 1회(2026-10-18 · high 0 · medium 4 · low 5 · nit 1 묶음): HEAD 와 작업 트리 `compute_topn` 을 격리 DB 90조합(KODEX 공백 3 × 기준 3 × 정렬 2 × 인자 5)으로 대조 — 기본 출력 같음 · flag 출력에서 새 키를 빼면 같음 · 계산 · 경계 · Q2 · Q3 · 화면 계약 깨끗. 반영: 결과서 과장 2(정렬 방향 · 다른 호출 수) · §8 · §9 채움 · 시험 보강 2(보유만 고른 상세에 보유 근거 객체 · 상위 후보 밖 보유 ETF = None) · PROGRAM_TRUTH 낡은 줄 2 · 미사용 helper 삭제 · 낡은 주석 · import 위치 · CSS. 기록만: 배지 vs 칸 · 「보유와 비교」 다른 자리 이름(§5). 커밋 위험(새 파일 미추적)은 경로를 하나씩 지정해 스테이징(§9).

## 7. 사용자 확인이 필요한 항목

- 실화면 확인 완료(2026-10-18 · 사용자 '확인했습니다.'): 「요즘 잘 오르는 ETF」 카드 · 표 · 위 둘째 줄과 ? · 펼침 3M · 'AI Sessions로 넘기기' 질문 본문 · 「ETF 비교하기」 후보 칸 · 정렬 · 상세 · 보유 탭 · 「보유와 비교」 후보 · 보유 카드 '20구간 KODEX200 차이'.
- 같은 확인 때 사용자 요청: 「ETF 비교하기」 빠른 선택 버튼(전체 · 보유 중 · 비교 가능 · 확인 필요)이 너무 작음 → 중간 크기로만(§4 반영) — 실화면 확인 완료(2026-10-18 '확인했습니다.').
- 커밋 · push 는 별도 승인.

## 8. 검증 실측 (2026-10-18)

- 새 시험: 백엔드 `tests/test_poc5_22_same_period_kodex200.py` **28 passed**(계산 예 · 같은 날짜만 · 유효하지 않은 가격 7종 · 후보 기간 없음 4종 · 반올림 전 뺄셈 · 실제 A · B · 짧은 이력 · 끝이 이른 후보 · KODEX200 시작 / 끝 날짜 결측 · flag 꺼짐 = 변경 전(기준 3 × 정렬 2) · 추가 조회 0 · flag 켜는 곳 = 두 PC API · 기본 경로 연구 모듈 import 없음 · PC 시장 / 보유 근거 API(상위 후보 밖 보유 = None) · AI 세션 왕복). 프론트 신규 `lib/samePeriodKodex.test.ts` 10 · `holdings_compare/CompareCards.test.tsx` 2 · `TransferToAISessionsCard.test.tsx` 2 · `JudgmentWorkbenchView.test.tsx` +4 · `marketDiscoveryCopyText.test.ts` +1 · `returnPeriod.test.ts` −2(삭제한 21 비교 판정) — 기존 시험 6파일은 새 계약으로 갱신(§2).
- 회귀(최종 코드): 백엔드 전체 `pytest tests/` **3760 passed**(exit 0 · 7분 3초 · 라이브 DB 사본 해시 세션 전후 같음 · 라이브 경로 변경 경고 없음) · 프론트 전체 vitest **61 files · 708 passed** · `npx tsc --noEmit` 오류 0 · `npm run lint` 오류 0 · 바뀐 백엔드 7 + 시험 1 파일 `black --check` · `flake8` · `py_compile` 통과.
- 변이(최종 코드 · 사본 폴더 · 복원 = 내용 쓰기 + 시각 되돌림 · `PYTHONDONTWRITEBYTECODE=1`): 백엔드 **14/14** — KODEX200 시작일 앞 날짜로 대체 · 반올림한 후보 값으로 뺄셈 · 비율로 나눔 · 0 종가 허용 · 후보 날짜 없음 판정 빠짐 · 시작일 = 시장 최신일 · 끝일 = 시장 최신일 · flag 무시 · 후보마다 KODEX200 다시 읽기 · 보유 사본에 안 붙임 · 보유 사본 없는 종목 다른 값으로 채움 · 시장 API flag 빠짐 · AI 세션 모델 필드 빠짐 · 모델 연결 빠짐. 프론트 **14/14** — 새 객체 없으면 excess_return 으로 · 「ETF 비교하기」 정렬 = 기존 차이 · 보유 탭 값 없음 '—' · 도움말 한계 문장 빠짐 · 복사문 한계 문장 빠짐 · 「보유와 비교」 후보 칸 = 1개월 값 · 그 단위 % · AI 초안 객체 빠짐 · 일부 값 없음도 '응답에 없음' · ? 묶음이 시작일만 봄 · 계산 불가를 값 색으로 · 상세가 늘 보유 근거 객체 · 복사문 3개월 = 1개월 · 카드 펼침 3M = 1M. 처음 돌렸을 때 '? 묶음이 시작일만 봄' 1개가 살아남아 시작일은 같고 끝일만 다른 묶음 시험을 더했다(묶음 순서에 끝일 기준 추가).
- 기본 호출 불변(사본 DB `mode=ro` 백업 · 사본 상태 폴더 · 변경 전후): `compute_topn` 기본 호출(기준 3 × 정렬 2 · n=30) + POC5-21 인자 호출 = 바뀐 값 · 추가 키 0 · PC 시장 응답 = 후보 10개에 `same_period_kodex200` 추가만 · 보유 근거 응답 = 32줄에 키 추가만(값 변화 0). 독립 검토도 HEAD 와 작업 트리를 격리 DB 90조합으로 대조해 같음을 확인(§6).
- 실제 PC 응답(사용자 백엔드 `--reload` · GET 읽기만): §0 값 그대로.

## 9. git 상태 (보고 직전 실측)

- `git status --short --untracked-files=all`: 이 결과서를 포함한 42파일 staged(`M` 31 · `A` 11 · 오른쪽 칸 공백 = 작업 트리 = staged). 새 파일(`app/same_period_kodex200.py` · `frontend/lib/samePeriodKodex.ts` · `SamePeriodValue.tsx` · 새 시험 4)은 경로를 하나씩 지정해 스테이징했다(`app/market_topn.py` 가 새 모듈을 import — 빠지면 OCI 기본 경로 ImportError). 추적 밖은 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 1개뿐(스테이징하지 않음).
- 커밋 · push 없음(사용자 승인 대기).

## 10. 검증자 r1 — VERIFIED (2026-10-18 · Codex)

검증 기준: HEAD `05093286c619e5e019a33d0d2ce3260a52812aa3` 대비 staged 42파일(A 11 · M 31), 작업 트리와 일치. 설계 V1·PLAN 판정·PLAN·이 결과서와 실제 변경을 대조했다. 실화면과 빠른 선택 버튼 확인은 사용자 전달 및 §7 기록을 승인 근거로 수용하며 검증자가 화면을 별도로 조작한 확인은 아니다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 기존 후보 수익률이 선택한 A·B와 반올림 전 수익률을 사용하며, 같은 날짜의 양수·유한 KODEX200 종가로 수익률을 계산한 뒤 뺀 차이를 마지막에 소수 4자리로 전달한다. 날짜 결측은 앞뒤 날짜·보간·기존 차이로 채우지 않고 사유를 구분한다. Q1의 가격 조정 기준 연속성 미검사는 도움말·복사문에 명시한다. Q2의 보유 근거는 상위 10 후보와 연결된 종목만 같은 객체를 옮기며, Q3의 「보유와 비교」 두 카드 칸은 기존 단기 20구간 값·%p를 사용한다. 「ETF 비교하기」의 KODEX 사용자 정렬은 새 표시값을 사용한다. 빠른 선택 버튼 크기는 사용자 직접 요청·확인에 따른 UI 전용 변경으로 인정하며 CSS 외 판정·조회 동작은 바뀌지 않았다.
- **A-2 보고 정확성: 통과.** 변경 목록은 staged 42개(A 11 · M 31), unstaged 0, 사용자 소유 untracked 인계 문서 1개와 일치한다. 새 계산 모듈 82줄·helper 141줄·표시 컴포넌트 25줄, `MarketDiscoveryView.tsx` 864줄·`JudgmentWorkbenchView.tsx` 845줄이다. 이번 검증에서 문서 수치만의 정정 사항은 발견하지 못했다. 개발자 전체 회귀·변이·실자료 실측은 §8 근거로 구분하며 검증자가 재실행한 것으로 보고하지 않는다.
- **A-3 산출물 정합성: 통과.** 시장 API 모델·조립 및 보유 근거 사본에 같은 객체가 연결된다. 기존 `excess_return`·`basis_*`와 21의 날짜 필드는 보존된다. 공통 helper를 사용하는 카드·표·상세·복사문과 새 AI 전달 스냅샷의 수치·날짜·미확인 처리가 일치한다. AI 저장 모델의 선택 필드 왕복 시험도 통과했다. 기존 JSON 안 선택 필드 추가이며 DDL·마이그레이션·과거 기록 재계산은 없다.
- **A-4 금지사항 위반: 없음.** 새 API 경로·DB 표·외부 조회·의존성·운영 DB 쓰기·발송·PUSH·PARAM·cron 변경이 없다. 새 옵션을 True로 주는 위치는 시장·보유 근거 두 PC API이며 다른 6개 호출은 기존 기본 옵션을 사용한다. 기본 경로에서 연구 모듈을 새로 import하지 않는다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 값 없음·계산 불가를 구분하고, 새 객체가 없는 응답을 기존 기간 차이나 단기 20구간 값으로 대체하지 않는다. 사유를 알 수 없을 때도 정상 숫자로 채우지 않고 계산 불가로 표시한다.
- **B-2 단일 책임 위반: 없음.** 순수 계산, 공통 표시 helper, 칸 컴포넌트, 기존 API·JSON 전달 경계로 책임이 나뉜다.
- **B-3 파일 책임 과다: 없음.** 백엔드 변경 파일 최장 480줄. 기존 근접 파일인 시장 화면은 866→864줄, 비교 화면은 849→845줄로 증가하지 않았고 새 책임은 작은 모듈로 분리됐다.
- **B-4 실험/운영 경계 위반: 없음.** 연구 모듈 의존과 새 운영 판정을 추가하지 않았다. 공유 보유 builder·기본 호출·시장 후보 선정·기본 수익률 정렬은 유지한다.
- **B-5 배포 경로 영향: 없음.** 변경 파일 42개가 모두 Git 추적 상태이며 계산 모듈·프론트 import 대상과 실제 경로가 일치한다. 새 계산 모듈이 index에 있어 기본 경로 import 누락 위험은 없다. 파일 이동·삭제·배포 스크립트 변경은 없고 Docker 경로에 별도 수정이 필요한 변경도 없다.
- **B-6 기술부채/구조적 퇴행: 없음.** 후보별 추가 조회나 화면별 별도 비교 공식을 두지 않는다. 삭제된 POC5-21 비교 helper는 같은 화면 지표가 새 객체로 교체된 범위이며, 단기 5/10/20 복사문의 날짜 계약은 유지된다.

### 3) 기반 문서 준수

승인 밖 문서·라이브러리·프레임워크·DB 스키마 추가 및 KILL_SWITCHES 발동 사항은 발견하지 못했다. POC5-20 연구 결론·Q6 운영 계약·기존 다른 기간 차이의 운영 의미는 바뀌지 않았다. 가격 조정 기준 연속성 미검사는 설계자 확정 범위로 남으며 전체 이력 검증을 완료했다고 보지 않는다.

### 4) 코드 안전성

**위험 수준: NONE.** 검증 범위에서 추가 위험은 발견하지 못했다. 날짜 조회용 SELECT나 외부 호출·새 비밀값이 없으며, 검증자는 실제 `.env`·보유·시세 DB·원장·로그·사용자 인계 문서를 열지 않았다. 시험은 저장소 밖 소스 사본과 tmp 자료로만 수행했고 발송·서버 재시작·운영 쓰기를 실행하지 않았다.

### 5) 범위 폭주

**폭주 수준: NONE.** Q1·Q2·Q3의 설계자 보충, 같은 객체의 AI JSON 전달, §4의 구현 정리와 사용자 직접 요청 버튼 크기 변경은 요구·승인과 연결된다. 기존 기간 비교와 단기 20구간 비교를 혼용하거나 새로운 순위·필터를 만들지 않았다.

### 6) 종합 판정 및 실측 근거

**종합 판정: VERIFIED.** A/B 전 영역 통과. 코드 결함이나 정정이 필요한 문서 수치 불일치는 발견하지 못했다.

- backend: 이번 단계 28건과 기존 실제 기간·시장 TOP N·API·시장 날짜 시험을 함께 실행해 **5파일 113 passed, 1 warning in 2.51s**. 기존 Git 검색 시험은 검색 작업 트리를 사본으로 지정하고 원본 index를 읽기 전용으로 참조했다. 기존 Starlette/httpx 경고 외 오류는 없다.
- frontend: 변경·신규 관련 **9파일 98 passed**. `tsc --noEmit --incremental false`와 변경 TS/TSX **26파일 eslint** 통과. 사본에 기존 의존성 읽기 경로를 연결하고 Vite 캐시는 별도 tmp 경로를 사용했다.
- Python `black --check`·`flake8`·구문 검사 각 8파일 및 `git diff --cached --check` 통과.
- 기본 옵션 출력·수익률·선정·순서 보존 및 추가 조회 없음은 관련 시험과 실제 변경 대조로 확인했다. 고정 HEAD 대비 90조합 대조·전체 backend 3,760건·frontend 708건·변이 14+14종 및 라이브 해시는 개발자 §6·§8 근거로 유지하며 중복 실행하지 않았다. 실제 PC 응답을 검증자가 새로 조회했다고 보고하지 않는다. build와 실화면 재조작도 하지 않았다.
- 검증 근거는 저장소 밖 `/private/tmp/poc522-verifier-hteuk6r3/`에 보관했다. 검증 시작 후 원본 코드·시험·설계·PLAN 변경 0, 기존 문서의 검증 기록·현재 상태만 반영했다. 사용자 소유 인계 문서는 읽거나 stage하지 않았다. 커밋·push·배포는 하지 않았다.

### 7) 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 검증은 통과했으며 커밋·push는 기존 순서대로 설계자 판정과 사용자 별도 승인 뒤 진행한다. 가격 조정 기준 연속성과 상위 10 밖 보유 종목의 자료 없음은 결과서 §5의 승인된 범위·한계로 함께 전달한다.

## 11. 설계자 RESULT 판정 · 종료 (2026-10-18)

- 판정: **PASS — 추가 코드 수정 없이 종료**(문서 기반 판정 · 설계자가 맥북 소스 · DB · 서버를 직접 실행한 확인 아님).
- 종료 상태: **IMPLEMENTED_VERIFIED_CLOSED(2026-10-18)**. RESULT · PLAN · STATE · PROGRAM_TRUTH · BACKLOG 를 같은 상태로 맞췄다. **POC5-21 ~ 22 의 PC 후보 1 · 3개월 비교 정정은 이 범위에서 마무리**한다. 별도 인계 문서 없음.
- 해소 범위: PC 「요즘 잘 오르는 ETF」 카드 · 표 · 공통 복사문 · 「ETF 비교하기」 후보 · 보유 탭 · 상세 · 사용자 선택 정렬 · 새 AI 전달 스냅샷의 1개월 · 3개월 KODEX200 대비 = 동일 기간 값 · 「보유와 비교」 후보 카드 1개월 값 오연결 → 기존 단기 20구간 값으로 정정 · 사용자 요청 빠른 선택 버튼 4개 중간 크기.
- 해소로 기록하지 않는 것(한계 · §5): 가격 조정 기준 연속성 미검사(`ok` = 산술 비교 가능) · 보유 탭은 기존 상위 10 후보와 연결된 종목만(지금 보유 전부 '동일 기간 값 없음' · 전체 보유 비교 제공 완료 아님) · 단기 20구간 계산의 비교 날짜 · 남은 이름 · 단위 · 확인 필요 배지 · 결측 정렬 정책 · 기존 `excess_return`(기간 다른 차이)과 그 산식 차이(다른 호출 · OCI 근거용) · 추가 명칭 정리 · 계산 확장 · 가격 기준 연구 · 리팩터 단계는 열지 않음.
- 판정 · 종료 문서만 반영 — 재검증 · 재판정 · 추가 실화면 · PC 재기동 · OCI pull · 거래일 대기 없음. 커밋 · push 는 사용자 승인 뒤(사용자 소유 handoff 문서 제외).

### 판정 원문 (설계자 · 2026-10-18)

# POC5-22 동일 기간 KODEX200 비교 — RESULT 판정

작성일: 2026-10-18 · 작성자: 설계자 · 수신: 개발자 / 사용자

**판정: PASS. 추가 코드 수정 없이 종료 기록과 커밋·push로 진행한다.**

근거는 제출 결과서, 설계 V1·PLAN 판정, 결과서 §10의 검증자 r1 VERIFIED와 §7의 사용자 실화면 확인이다. 설계자가 맥북 소스·DB·서버를 직접 실행해 확인한 판정은 아니다.

## 1. 구현과 검증 수용

- 후보가 실제 사용한 시작일·끝일 A·B와 반올림 전 수익률을 사용하고, 같은 날짜의 KODEX200 수익률을 빼 %p로 전달하는 구현을 수용한다. 필요한 날짜·유효 가격이 없으면 사유를 표시하며 다른 날짜나 기존 차이로 채우지 않는다.
- PC 화면·사용자 선택 정렬·공통 복사문·새 AI 전달 스냅샷에 같은 객체를 연결한 것을 수용한다. 기본 호출, 기존 필드의 의미, 후보 자동 선정·기본 정렬, 공유 builder·PUSH 경계 보존도 검증 기록을 근거로 수용한다.
- 「보유와 비교」는 PLAN Q3대로 잘못 연결된 1개월 값을 기존 단기 20구간 값으로 정정한 범위다. 이 단기 계산까지 실제 동일 날짜로 다시 맞췄다는 뜻은 아니다.
- 결과서 §4의 구현 판단을 수용한다. 사용자 요청·실화면 확인을 마친 빠른 선택 버튼 4개의 중간 크기 변경도 포함한다.
- 검증자 직접 실행(백엔드 관련 113건·프런트 관련 98건)과 개발자 보고의 전체 회귀·변이 시험을 구분해 근거로 수용한다. 추가 시험·재조사는 요구하지 않는다.

## 2. 한계의 처리

- 결과서 §5를 이번 종료의 한계로 수용한다. 가격 조정 기준의 연속성은 미검사이며, `ok`는 산술 비교 가능을 뜻한다. 도움말·복사문에 반영한 설명을 유지한다.
- 보유 탭은 기존 상위 10 후보와 연결된 종목에만 값이 제공된다. 현재 보유 전부가 '동일 기간 값 없음'인 사실도 명시된 가용 범위로 수용한다. 이를 전체 보유 비교 제공 완료로 기록하지 않는다.
- 기존 단기 20구간 계산·잔여 이름과 단위·확인 필요 배지·결측 정렬 정책은 보고된 한계로 둔다. 이번에 추가 명칭 정리, 계산 확장, 가격 기준 연구나 리팩터 단계를 열지 않는다.

## 3. 종료 지시

1. 본 판정 원문을 기존 결과서 끝에 붙이고, RESULT·PLAN·STATE·PROGRAM_TRUTH·BACKLOG의 해당 상태를 맞춘다. POC5-21~22의 PC 후보 1·3개월 비교 정정은 이 범위에서 마무리한다.
2. 동일 범위의 기존 커밋·push 승인이 있으면 그 승인을 사용한다. 없으면 정리한 변경으로 사용자 승인을 받아 커밋·push한다. 사용자 소유 handoff 문서는 포함하지 않는다.
3. 종료 기록과 커밋·push를 마치면 상태를 `IMPLEMENTED_VERIFIED_CLOSED`로 확정한다. 문서 종료 기록만으로 재검증·재판정을 요구하지 않는다.

사용자 실화면 확인은 완료로 인정한다. 추가 화면 확인·PC 재기동·OCI pull·거래일 대기·별도 인계 문서는 종료 조건이 아니다. 이 판정은 이번 비교 정정의 종료이며, 전체 프로젝트나 다른 미구현 요구가 모두 끝났다는 판정은 아니다.
