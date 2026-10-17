# POC5-21 개발 결과서 — PC_CANDIDATE_RETURN_PERIOD_EVIDENCE (PC 후보 수익률의 실제 계산 기간 표시)

작성 2026-10-17 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_CLOSED — 구현 완료(2026-10-17) → 사용자 실화면 확인(2026-10-17 '확인했습니다.') → 검증자 r1 VERIFIED(2026-10-17 · §10) → 설계자 RESULT PASS · 종료(2026-10-17 · §11)
VERIFIER      = Codex · r1 VERIFIED · backend 관련 105건 · frontend 관련 35건 통과 · 고정 HEAD 대조 12조합 출력·SELECT 동일
STEP_ID       = POC5-21 PC 후보 수익률의 실제 계산 기간 표시
DESIGN        = docs/ai_design/POC5/POC5-21_PC_CANDIDATE_RETURN_PERIOD_EVIDENCE_DESIGN_V1.md
PLAN          = docs/ai_plan/POC5/POC5-21_PC_CANDIDATE_RETURN_PERIOD_EVIDENCE_PLAN_V1.md(§4 판정 반영)
DECISION      = docs/ai_design/POC5/POC5-21_PC_CANDIDATE_RETURN_PERIOD_EVIDENCE_PLAN_DECISION_2026-10-17.md(PASS · Q1 (b) · Q2 (a) · Q3 (b) + 보충)
USER_MOCKUP   = 수정 목업 확인 2026-10-17 '목업 좋습니다.'(로컬 · 게시 안 함)
BASE_COMMIT   = 704d84a1 (POC5-20 종료)
SCOPE         = 「요즘 잘 오르는 ETF」 PC 응답 · 후보 카드 / 표 · 요약 명칭 · AI 해석용 복사문
                새 메뉴 · 카드 · 펼침 · API 경로 · DB 표 · DB 쓰기 · 추가 SELECT · 외부 조회 · 의존성 · OCI 문장 · PUSH · PARAM 변경 0
                「보유와 비교」 탭 · 「ETF 비교하기」 표시 변경 0
CHECKS        = §8
```

## 0. 요약

- **백엔드(PC 화면 API 만)**: `compute_topn(actual_price_dates=True)` 를 `GET /market/topn/latest` 만 넘긴다. 기본 False 인 다른 호출 7곳(`api_holdings_market_evidence` · `draft` · `draft_three_push` 2 · `ml_score_validity_screen` · `api_decision_draft_preview` 2)의 출력은 그대로다.
  - 기간 dict 선택 필드 `price_start_date` · `price_end_date` = 그 수익률을 계산한 시작 · 끝 저장 행(`_compute_period` 가 이미 고른 행 · `_PeriodResult.end_date` 추가).
  - `market_context.kodex200` 선택 필드 `return_1m_start_date` · `return_3m_start_date` · `return_end_date` = KODEX200 1M · 3M 수익률이 쓴 069500 행(`market_regime.kodex200_return_dates` · `compute_kodex200_metrics` 와 같은 거르기 · 같은 20 / 60행 · 같은 부족 조건 · `status == "ok"` 일 때만).
  - 단기 흐름 `kodex200_start_dates` · `kodex200_end_date`(batch 가 이미 읽은 KODEX200 이력) · 일간 점검 `price_start_date` · `price_end_date`(같은 series 의 [-2] · [-1]).
  - `basis_start_date` · `basis_end_date`(= 시장 저장 최신일) 이름 · 값 · 호환 목록 · 수익률 · 차이 · 정렬 · 선정 · 필터는 그대로. 추가 조회 0.
- **화면(카드 · 표 공통 `ReturnPeriodLine` · 판정 `lib/returnPeriod.ts`)**
  - 후보 목록 위 두 줄 + 각 줄 클릭형 ?.
    - 「{선택 기간} 수익률 계산 기간」 — 값이 있는 표시 후보의 날짜가 전부 확인되고 전부 같을 때만 '시작 → 끝 종가 · 표시 후보 N개 모두 같음'. 일부 미확인 = '날짜 확인된 n개 같음 · m개 계산 기간 확인 불가'. 여러 종류 = '종목별 계산 기간 다름' + 한 종류인 시작 / 끝만 '공통'. 전부 미확인 = '확인 불가 — 응답에 사용 종가 날짜가 없습니다'.
    - 「KODEX200 대비 1M · 3M」 — '기간 다른 수익률 차이' / '같은 기간 수익률 차이' / '후보별로 다름 — 값 아래 표시' (+ 'm개 기간 확인 불가') · (%p).
  - 이름 옆: 끝일 ≠ 시장 저장 최신일이면 '수익률 끝일 YYYY-MM-DD'(다수의 날짜를 기준 삼지 않음) · 날짜가 하나도 없으면 '계산 기간 확인 불가'(선택 기간이 전부 미확인이면 위 줄만).
  - 값 아래: 시작일이 여러 종류인 기간은 **모든 값**에 '시작 YYYY-MM-DD'. KODEX200 대비 값은 비교 관계가 후보별로 섞일 때만 '기간 다름 / 같은 기간', 미확인은 '기간 확인 불가'.
  - KODEX200 대비 값 단위 % → **%p**(숫자 그대로). 요약 '시장 데이터 기준일' → '시장 저장 최신일 (저장된 전체 종목 가격 중 가장 늦은 저장일)'. 표 아래 '6개월 / 12개월 / 1년 / 3년' → '6개월 / 12개월 / 3년'.
- **복사문(`buildMarketDiscoveryCopyText` · 수동 복사 · AI 세션 · ETF 구성종목 전달 공통)**: 머리말 '○○ 기준 결과' 대신 '시장 저장 최신일: D (저장된 전체 종목 가격 중 가장 늦은 저장일 — 후보별 수익률 계산 기간은 각 값 뒤 괄호)' · 수익률 줄마다 '(사용 종가 A → B)' · 일간 '(직전 저장일 대비 · …)' · [데이터 품질] '(정상 · …)' · KODEX200 대비 줄 '… 수익률 차이: +x%p (기간 다름 — 후보 A → B · KODEX200 C → D)' / '(같은 기간 A → B)' / '(기간 확인 불가 — …)' · 단기 5 / 10 / 20 같은 방식 · 섹션 [시장 대비 후보 강도] → [KODEX200 대비 수익률 차이] · [요청] '초과수익' → '수익률 차이(기간이 다르면 괄호에 두 기간)'. 날짜 판정은 화면과 같은 함수.
- **실제 PC 응답(2026-10-17 · 사용자 백엔드 `--reload` · GET 읽기만 · 시장 저장 최신일 2026-10-14)**: 1위 후보 1개월 `price_start_date` 2026-09-14 · `price_end_date` 2026-10-14 · KODEX200 1M 2026-09-10 · 3M 2026-07-14 · 끝 2026-10-14 · 단기 KODEX200 5 / 10 / 20 = 10-06 · 09-28 · 09-10 · 일간 점검 10-13 → 10-14 · 표시 10후보 1개월 끝일 모두 2026-10-14.

## 1. 처리한 요구사항

| 출처 | 요구 | 상태 |
|---|---|---|
| 설계 §2 | 기존 계산이 실제로 고른 시작 · 끝 행 날짜를 그 값의 근거로 전달 · 시장 최신일로 대체 안 함 | DONE(`price_*` · 이미 고른 행) |
| 설계 §2 | 기간 정의 · 기간 선택 · 정렬 · 숫자 · 선정 · 필터 불변 · 새 탈락 · 재계산 없음 | DONE(flag 켜고 끔 비교 · §8) |
| 설계 §2 | 날짜는 계산 행에서 · 월말 · 휴장 추정 · 화면 역산 없음 | DONE |
| 설계 §2 | 일간 = 직전 저장일 대비 · 임의 전날 아님 | DONE('직전 저장일 대비' · 실제 직전 저장 행) |
| 설계 §2 | 시장 저장 최신일 · 종목 마지막 가격일 · 각 수익률 날짜 구분 · 공통 기준일 필드 뜻 확인 | DONE(PLAN §1 · 요약 명칭) |
| 설계 §2 | 자료 부족 값 · 사유 보존 · 날짜 미확인 = '계산 기간 확인 불가' | DONE |
| 설계 §3 | 기존 목록 · 카드 자리 · 새 메뉴 · 카드 · 펼침 없음 | DONE(목록 위 두 줄 · 기존 ?) |
| 설계 §3 · 판정 Q3 | 전부 확인 · 전부 같을 때만 공통 한 줄 · 일부 미확인 알림 · 여러 종류 '종목별 계산 기간 다름' · 시작일 여러 종류 = 모든 값 시작일 | DONE |
| 설계 §3 · 판정 Q3 | 끝일 ≠ 시장 저장 최신일 = '수익률 끝일 YYYY-MM-DD' · 다수 날짜 기준 아님 | DONE |
| 설계 §3 | 여러 기간 — 선택 기간 기본 화면 · 나머지는 기존 자리 · ? | DONE(값 아래 · ? 안 6개 기간) |
| 설계 §3 · 판정 Q2 | 복사문 수익률마다 실제 기간 · 단기 5 / 10 / 20 · 데이터 품질 일간 포함 · 화면과 같은 날짜 | DONE |
| 설계 §3 | 복사문 머리말 시장 저장 최신일 = 후보 끝일 보증 아님 · 공통 생성기 정정 · 새 외부 전송 없음 | DONE |
| 판정 Q1 | KODEX200 쪽 실제 기간 전달 · 표시 · %p · '기간 다른 수익률 차이' · 양쪽 기간 ? · 복사문 두 기간 · 미확인 숨김 없음 · 초과수익 · 시장 우위 설명 안 함 | DONE |
| 판정 §2 | 요약 명칭 '저장된 전체 종목 가격' · 짧은 이력 값 = 그 기간 전체 수익률 아님 · 표 '1년' 문구 정정 | DONE |
| 설계 §4 | 이미 읽은 행 재사용 · 새 API · DB · 의존성 없음 · PC 응답 · 복사문만 | DONE |
| 설계 §4 | `MarketDiscoveryView.tsx` 줄 수 확인 · 필요하면 작은 컴포넌트 | DONE(861 → 866 · 기간 표시는 `ReturnPeriodLine.tsx` 97줄) |
| 설계 §5 · 판정 §2 | 시험(실제 선택 행 · 끝 행이 같으면 끝일 불변 · 같은 끝 다른 시작 · 결측 · 화면 = 복사문 · 추가 조회 0 · 다른 호출 불변 · 두 비교 기간 일치 / 불일치 / 미확인 · 다수 옛 끝일 · 일부 날짜 없음 · 개별주만 더 최신) | DONE(§8) |
| 설계 §5 | 목업 1440 · 1000px 4상태 · 사용자 확인 | DONE(2026-10-17) |
| 설계 §5 | 사용자 실화면 · 검증자 | 실화면 DONE(2026-10-17 '확인했습니다.') · 검증자 r1 VERIFIED(§10) |

## 2. 변경된 파일 목록

- 백엔드 수정: `app/market_topn.py` · `app/market_topn_helpers.py` · `app/market_regime.py` · `app/short_term_momentum.py` · `app/api_market_topn.py` · `app/api_market_topn_models.py` · `app/api_market_topn_service.py`
- 프론트 신규: `frontend/lib/returnPeriod.ts` · `frontend/app/components/ReturnPeriodLine.tsx`
- 프론트 수정: `frontend/app/components/CandidateCards.tsx`(목록 전체가 fragment 안으로 한 단계 들여쓰기 — 공백 제외 차이 `git diff -w`) · `CandidateTable.tsx` · `MarketDiscoveryView.tsx` · `frontend/app/globals.css` · `frontend/lib/api/market.ts` · `frontend/lib/api/marketEvidence.ts` · `frontend/lib/marketDiscoveryCopyText.ts`
- 시험 신규: `tests/test_poc5_21_return_period_dates.py` · `frontend/lib/returnPeriod.test.ts` · `frontend/app/components/ReturnPeriodLine.test.tsx` · `frontend/lib/marketDiscoveryCopyText.test.ts`
- 시험 수정: `frontend/app/components/CandidateCards.test.tsx`(KODEX200 대비 기대값 `+11.91%` → `+11.91%p` 1줄)
- 문서: 설계 V1 · PLAN 판정 · PLAN V1 · 이 결과서 · `docs/PROGRAM_TRUTH.md` · `docs/backlog/BACKLOG.md` · `docs/STATE_LATEST.md`

## 3. 신규 추가된 의존성

없음.

## 4. 지시문 외 변경 · 구현 판단

- 단기 흐름 단건 함수 `compute_short_term_momentum` 에도 KODEX200 날짜를 채웠다(batch 와 같은 결과 · 같은 이력 · 호출처 시험만).
- KODEX200 날짜는 `compute_kodex200_metrics` 를 고치지 않고 옆에 같은 거르기 · 같은 행 수 helper 로 뒀다(공유 함수 출력 불변 · 같은 행 재계산 시험 · 변이 B6 · B7).
- 「KODEX200 대비」 줄은 표의 열 머리말을 바꾸지 않고 목록 위 공통 줄에 한 번 둔다(카드 · 표 같은 자리).
- 복사문 [요청]의 'KODEX200/KOSPI 대비 초과수익' → 'KODEX200 대비 수익률 차이 …'. 복사문에 실린 차이 값은 KODEX200 쪽뿐이라 KOSPI 를 뺐다(판정 Q1 '복사문의 해당 제목 · 설명도 이 뜻에 맞춘다').
- 복사문 [KODEX200 대비 수익률 차이] 제목 아래 설명 한 줄: '수익률 차이 = 후보 수익률 − KODEX200 수익률(%p). 괄호의 두 기간이 다르면 같은 기간 초과수익이나 시장 대비 우위를 확인한 값이 아닙니다.'(화면 ? 와 같은 뜻 · 독립 검토 반영).
- AI 세션 저장 자료: 'AI Sessions로 넘기기' · ETF 구성종목 화면의 `data_quality_snapshot` 은 기존부터 `daily_return_check` 객체를 통째로 담는다(`TransferToAISessionsCard.tsx :: _toDataQualitySnapshot` · `ETFExposureView.tsx :: _toDataQualitySnapshot`). 그래서 이번부터 저장되는 AI 세션 기록에 `price_start_date` · `price_end_date` 두 키가 더해진다(추가만 · 기존 키 · 값 그대로 · 질문 본문의 날짜와 같은 값). `market_context_snapshot` · `short_term_momentum_snapshot` · `candidate_snapshot` 은 필드를 골라 담아 그대로다. 저장 형식 코드는 바꾸지 않았다.

## 5. 알려진 한계 / 미완성

- OCI 근거 문장 · `basis_end_date` 이름과 값 · 다른 호출자는 그대로다(설계 §4 · 범위 밖 · BACKLOG 관찰 유지).
- 후보 1개월 · 3개월(달력 30 · 90일)과 KODEX200 1M · 3M(20 · 60 저장일)의 기간 차이는 계산을 맞추지 않고 표시만 한다(판정 Q1 · BACKLOG 관찰 기록).
- AI 세션에 저장되는 `candidate_snapshot` 형식은 그대로다(날짜는 질문 본문에만). 이 작업 전에 만든 전달 초안(브라우저 세션 저장)으로 복사문을 다시 만들면 날짜가 없어 '계산 기간 확인 불가'로 나온다.
- 실제 자료(2026-10-14)에는 끝일이 다른 표시 후보 · 날짜 없는 응답이 없어 그 상태는 격리 fixture(목업 · 시험)로만 확인했다.
- 판정 Q3 대로 시작일이 한 종목만 달라도 그 기간의 모든 값 아래 시작일이 붙는다(목업 4번 · 3개월 기준 1000px 카드가 길어짐 · 사용자 목업 확인).
- 같은 PC 응답 값을 쓰는 다른 화면의 예전 이름은 그대로다(범위 밖): 「ETF 비교하기」 `JudgmentWorkbenchView.tsx` 'KODEX초과' · 「보유와 비교」 `holdings_compare/SelectedDetail.tsx` 'KODEX 대비 초과수익' 등.
- 응답 안에서 선택 기간 값만 날짜가 없고 다른 기간은 있는 후보는 이름 옆 표시가 없다(위 줄은 미확인 수를 센다 · 값 아래 '기간 확인 불가'). 지금 백엔드는 한 응답에서 날짜가 모두 있거나 모두 없어 생기지 않는다. 최상위 `asof` 가 없으면 '수익률 끝일' 비교를 하지 않는다(정상 응답에는 늘 있다).
- 0 인 차이 값의 부호: 카드는 '+0.00%p'(카드의 기존 `fmtPct` 와 같은 `>= 0`) · 표 · 복사문은 '0.00%p'(각 파일 기존 규칙). 날짜와 숫자는 같다.

## 6. 다음 검증자(Codex)에게 알릴 점

- 기본 호출 불변 근거: (1) 시험 `test_flag_off_is_unchanged_and_flag_only_adds_dates`(기준 3 × 정렬 2 · 새 키 없음 · flag 켠 출력에서 새 키를 빼면 같음) · (2) 변경 전후 사본 DB 실측 — `compute_topn` 기본 호출(기준 3 × 정렬 2 · n=30 · PC 와 같은 KOSPI / KODEX200 인자 호출)의 출력이 변경 전과 **바뀐 값 · 추가 키 0**, PC 화면 API 응답은 새 날짜 키만 추가(값 변화 0 · §8).
- 보유 근거 API 의 단기 흐름은 필드를 하나씩 옮겨 담아(`_build_short_term_payload`) 새 KODEX200 날짜가 나가지 않는다(시험).
- 화면 = 복사문: 같은 `valuePeriod` · `cmpState` · `kodexRange` 를 쓴다. 화면 시험이 카드에 보인 시작일 · 끝일 표시 · ? 안 공통 날짜로 후보 4 × 일간 · 1개월 · 3개월의 복사문 괄호를 대조한다(날짜 있는 9칸 + 확인 불가 3칸).
- `CandidateCards.tsx` 차이의 대부분은 들여쓰기다(`git diff -w` 88줄).
- 독립 검토 1회(2026-10-17 · high · medium 0 · low 6 · nit 4) 반영: 도움말 문구('값 아래에도' — 시작일이 종목마다 다를 때만) · 복사문 설명 한 줄 · 시험 보강(단기 10거래일 KODEX200 날짜 · API 5 / 10 / 20 날짜 값 · 일간 점검 급등 / 급락 경로 날짜 · 호출처 검사를 git grep → app · scripts 모든 .py 정규식 읽기) · STATE 갱신. 기록만: AI 세션 `data_quality_snapshot` 추가 키(§4) · 다른 화면 '초과' 이름 · 선택 기간만 날짜 없는 경우 · 0 부호(§5).

## 7. 사용자 확인이 필요한 항목

- 실화면 확인 완료(2026-10-17 · 사용자 '확인했습니다.'): 「요즘 잘 오르는 ETF」 카드 · 표(3개월 기준 '종목별 계산 기간 다름') · 두 ? · 펼침 6개월 / 12개월 / 3년 시작일 · 요약 명칭 · 'AI Sessions로 넘기기' 질문 본문의 날짜. 화면 의견 없음.
- 커밋 · push 는 별도 승인.

## 8. 검증 실측 (2026-10-17)

- 새 시험: 백엔드 `tests/test_poc5_21_return_period_dates.py` 23 passed · 프론트 `lib/returnPeriod.test.ts` 13 · `app/components/ReturnPeriodLine.test.tsx` 9 · `lib/marketDiscoveryCopyText.test.ts` 7 = 29 passed.
- 회귀: 백엔드 전체 `pytest tests/` **3732 passed**(exit 0 · 6분 51초 · 라이브 DB 사본 해시 세션 전후 같음) · 프론트 전체 vitest **58 files · 691 passed** · `npx tsc --noEmit` 오류 0 · `npm run lint` 오류 0 · 바뀐 백엔드 7 + 시험 1 파일 `black --check` 통과 · `flake8` 통과 · `py_compile` 통과.
- 변이(최종 시험 기준 · 사본 폴더 · 복원 = 내용 쓰기 + 시각 되돌림 · `PYTHONDONTWRITEBYTECODE=1`): 백엔드 **13/13** — 끝일 = 시장 저장 최신일 · 시작일 = 첫 행 · 계산 함수 끝일 = 직전 행 · flag 무시 · 화면 API flag 빠짐 · KODEX200 1M 한 행 어긋남 · KODEX200 0 이하 거르기 없음 · KODEX200 날짜 flag 없이 · 단기 KODEX200 시작 = 후보 날짜 · 일간 점검 시작 한 행 앞 · 모델 연결 날짜 빠짐 · 추가 조회 · 단기 KODEX200 끝 = 후보 끝. 프론트 **18/18** — 날짜 없으면 basis_end_date · 일부 미확인 '모두 같음' · 다수 시작일 표시 생략 · 끝일 기준 = 후보 최신 끝일 · 전부 미확인도 후보마다 · 비교 같음에 끝일 빠짐 · 카드 % 단위 · 복사문 끝일 = basis_end_date · 복사문 '○○ 기준' 머리말 · 복사문 같은 기간에 끝일 빠짐 · 단기 KODEX200 기간 = 후보 · 요약 '전체 ETF 가격' · 표 '1년' 복원 · 표 6개월 시작일 빠짐 · 섞이지 않아도 값 아래 표시 · KODEX200 줄 늘 나눔 · 데이터 품질 일간 날짜 빠짐 · 위 줄 늘 1개월. 처음 돌렸을 때 살아남은 3개(단기 KODEX200 끝일 · 비교 같음 판정 끝일 · 복사문 같은 기간 끝일)는 끝이 이른 종목 · 시작만 같고 끝이 다른 경우 시험을 더해 잡았다.
- 기본 호출 불변(사본 DB `mode=ro` 백업 · 변경 전후): `compute_topn` 기본 호출 기준 3 × 정렬 2(n=30) + PC 와 같은 KOSPI / KODEX200 인자 호출 = **바뀐 값 0 · 추가 키 0** · 단기 흐름 · 일간 점검 결과 객체는 새 날짜 속성만 추가 · PC 화면 API 응답은 새 날짜 키만 추가(후보 10 × 기간 6 × 2 · KODEX200 3 · 단기 2 · 일간 2 · 바뀐 값 0).
- 실제 PC 응답(사용자 백엔드 `--reload` · GET 읽기만): §0 값 그대로.

## 9. git 상태 (보고 직전 실측)

- `git status --short --untracked-files=all`: 이 결과서를 포함한 28파일이 staged(`M` 18 · `A` 10 · 오른쪽 칸 공백 = 작업 트리 = staged). 추적 밖은 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 1개뿐(스테이징하지 않음).
- 커밋 · push 없음(사용자 승인 대기).

## 10. 검증자 r1 — VERIFIED (2026-10-17 · Codex)

검증 기준: HEAD `704d84a1ea25bc52a8dec6041590aa37bc2b1cff` 대비 staged 28파일(A 10 · M 18), 작업 트리와 일치. 설계 V1·PLAN 판정·PLAN·이 결과서와 실제 변경을 대조했다. 사용자 실화면 완료는 이번 사용자 전달 및 §7 기록을 근거로 확인하며 검증자가 별도로 실화면을 조작한 것은 아니다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** 실제 계산이 선택한 시작·끝 행 날짜가 후보 수익률에 연결된다. KODEX200 날짜도 같은 이력·거르기·20/60행·자료 부족 조건을 사용한다. 단기 5/10/20구간 및 일간 점검은 각각 계산에 쓴 행 날짜를 전달한다. 날짜가 없으면 공통 최신일로 채우지 않는다. 공통 안내의 전부 확인·전부 일치 조건, 시작일 여러 종류일 때 모든 값 표시, 시장 저장 최신일과 후보 끝일 비교, KODEX200 비교의 같은 기간/기간 다름/확인 불가와 %p 단위를 확인했다. 카드·표·복사문의 공통 날짜 판정과 요약 명칭·표 안내 정정도 일치한다.
- **A-2 보고 정확성: 통과.** staged 28개(A 10 · M 18), unstaged 0, 사용자 소유 untracked 인계 문서 1개가 보고와 같다. 백엔드 수정 7개·새 시험 1개, 새 기간 helper·컴포넌트와 프론트 변경·시험·문서 목록이 일치한다. `MarketDiscoveryView.tsx` 866줄·`ReturnPeriodLine.tsx` 97줄이며, `CandidateCards.tsx`의 공백 제외 변경량은 추가 82+삭제 6=88줄이다. 전체 회귀·변이는 §8의 개발자 근거로 구분하며 검증자가 반복했다고 보고하지 않는다.
- **A-3 산출물 정합성: 통과.** API 모델과 조립 경로에 실제 기간 필드가 연결되며, 추가 날짜를 제외한 계산·선정·정렬은 유지된다. 고정 HEAD와 staged 코드를 같은 tmp DB로 12조합(기준 3×정렬 2×기존 시장 날짜 옵션 2) 대조해 기본 출력의 변경·추가 키 0, SELECT 내용·순서 차이 0을 확인했다(실행 시간 필드 제외). 카드·표·복사문의 날짜·불일치·미확인 시험과 API 날짜 시험이 통과했다. 일간 점검 객체를 그대로 저장하는 기존 AI 세션 경로의 날짜 키 추가는 §4에 공개돼 있으며 신규 저장 경로·DDL 변경은 없다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·API 경로·DB 표·수집·외부 전송·운영 DB 쓰기·PUSH·PARAM·OCI 문장 변경이 없다. 실제 기간 옵션을 True로 주는 운영 코드 위치는 PC 화면 API 한 곳이다. 다른 7개 `compute_topn` 호출은 기존 기본 옵션을 사용한다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 수익률 없음과 날짜 미확인을 구분하며 시장 저장 최신일을 실제 기간 대신 사용하지 않는다. 선택 메타데이터의 기본 비활성은 승인된 호환 계약이다.
- **B-2 단일 책임 위반: 없음.** 기간 판정 helper와 작은 표시 컴포넌트를 분리하고, 계산 모듈은 이미 선택한 행 날짜만 전달한다.
- **B-3 파일 책임 과다: 없음.** 백엔드 변경 파일 최장 513줄. `MarketDiscoveryView.tsx`는 861→866줄로 기존 근접 구간이지만 신규 기간 표시 책임을 별도 97줄 컴포넌트에 둬 승인된 범위 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 분석·연구 코드를 운영 판정에 삽입하지 않았으며 기존 수익률 산식·시장 판정·PUSH 계약을 바꾸지 않았다.
- **B-5 배포 경로 영향: 없음.** 보고된 계산·API·프론트·시험 파일은 모두 index에 있고 import 경로가 일치한다. 파일 이동·삭제와 Docker·배포 스크립트 영향은 없다. 사용자 소유 인계 문서는 제외했다.
- **B-6 기술부채/구조적 퇴행: 없음.** 시점 추정·날짜 역산·다수 날짜를 기준으로 한 예외 판정과 과거 결과 재사용을 추가하지 않았다. KODEX200 날짜 helper는 기존 계산과 같은 행을 쓰는지 시험으로 대조된다.

### 3) 기반 문서 준수

승인된 설계·PLAN·결과서 외 문서 생성, MongoDB·신규 UI 프레임워크·의존성 주입 프레임워크 도입 및 KILL_SWITCHES 발동 사항은 발견하지 못했다. POC5-20 연구 결론·Q6 운영 계약과 OCI 날짜 관찰은 바꾸지 않는다.

### 4) 코드 안전성

**위험 수준: NONE.** 검증 범위에서 추가 위험은 발견하지 못했다. 검증자는 실제 `.env`·보유·시세 DB·원장·로그·사용자 인계 문서를 열지 않았다. 시험·대조는 저장소 밖 소스 사본과 tmp DB에서 수행했고 외부 API·발송·서버 재시작은 실행하지 않았다.

### 5) 범위 폭주

**폭주 수준: NONE.** §4의 단건 단기 흐름 날짜 전달·KODEX200 날짜 helper·복사문 제목·설명 및 기존 AI 세션 JSON의 추가 날짜 키는 요구와 직접 연결되며 공개돼 있다. 새 비즈니스 판정이나 전송 경로는 없다.

### 6) 종합 판정 및 실측 근거

**종합 판정: VERIFIED.** A/B 전 영역 통과. 추가 코드 결함이나 정정이 필요한 문서 수치 불일치는 발견하지 못했다.

- backend: 이번 단계 23건을 포함한 6파일의 고유 관련 시험 **105건 통과**. 첫 실행은 104 passed·1 failed였으나, 실패는 사본에 `.git`이 없어 기존 POC5-11 시험의 `git grep`이 빈 결과를 낸 환경 문제다. 원본 시험은 수정하지 않고 검색의 작업 트리를 사본으로 지정하고 원본 Git index를 읽기 전용으로 참조해 해당 1건을 다시 실행했으며 **1 passed**였다. 기존 Starlette/httpx 경고 외 오류는 없다.
- frontend: 새 시험 29건과 기존 후보 카드 6건, **4파일 35 passed**. `tsc --noEmit --incremental false`·변경 TS/TSX 12파일 eslint 통과. 사본에 기존 의존성 읽기 경로를 연결하고 Vite 캐시를 별도 tmp 경로로 지정했다.
- Python `black --check` 8파일·`flake8` 8파일·구문 검사 8파일 및 `git diff --cached --check` 통과.
- 고정 HEAD 대조: 같은 tmp DB에서 두 소스를 별도 프로세스로 실행했다. 기본 `compute_topn` 출력 12조합 모두 동일(실행 시간 제외), 각 조합의 SELECT 12회·문장·순서도 동일했다. 추가 날짜 옵션의 값 불변·조회 불변은 이번 단계 시험으로도 확인했다.
- 전체 backend 3,732건·frontend 691건·변이 backend 13종·frontend 18종은 개발자 §8 근거를 유지하고 자동 반복하지 않았다. 개발자 실데이터·라이브 해시 실측을 검증자가 직접 수행한 것으로 적지 않는다. build·실화면 재조작도 하지 않았다.
- 근거 보관: 저장소 밖 `/private/tmp/poc521-verifier-d4letobw/`. 검증 시작 후 원본 코드·시험·설계·PLAN 변경 0. 기존 문서의 검증 기록·현재 상태만 반영했다. 커밋·push·배포는 하지 않았다.

### 7) 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 검증은 통과했으며 커밋·push는 기존 순서대로 설계자 판정과 사용자 별도 승인 뒤 진행한다. OCI 날짜 문장과 후보/KODEX200 산식 차이 관찰은 이번 단계에서 해소했다고 기록하지 않는다.

## 11. 설계자 RESULT 판정 · 종료 (2026-10-17)

- 판정: **PASS — 추가 코드 보완 없이 종료**(문서 기반 판정 · 설계자가 저장소 · PC 서버 · 실화면을 직접 조작한 확인 아님).
- 종료 상태: **IMPLEMENTED_VERIFIED_CLOSED(2026-10-17)**. STATE · PROGRAM_TRUTH · BACKLOG 를 같은 상태로 맞췄다. 별도 인계 문서 없음.
- 해소 범위: PC 「요즘 잘 오르는 ETF」 화면 · AI 해석용 복사문의 후보 수익률 실제 계산 기간 표시(BACKLOG `DEF-MARKET-CONTEXT-ASOF-MEANING` 아래 POC5-11 관찰의 PC 표시 부분). 해소로 기록하지 않는 것: OCI 날짜 문장 · 호환 `basis_*` 필드 의미 · 다른 화면의 예전 '초과' 이름 · 후보와 KODEX200 의 산식(기간) 차이.
- 판정 · 종료 문서만 반영 — 재검증 · 재판정 · 추가 실화면 · PC 재기동 · OCI pull · 거래일 대기 없음. 커밋 · push 는 사용자 승인 뒤.

### 판정 원문 (설계자 · 2026-10-17)

# POC5-21 후보 수익률 실제 기간 표시 — RESULT 판정

작성일: 2026-10-17 · 작성자: 설계자 · 수신: 개발자 / 사용자

**판정: PASS — 추가 코드 보완 없이 종료 처리한다.**

제출된 결과서 §0~§10을 설계 V1·PLAN 판정과 대조했다. 사용자 수정 목업·실화면 확인 및 검증자 r1 VERIFIED 기록을 근거로 한 문서 기반 판정이다. 설계자가 저장소·PC 서버를 직접 실행하거나 실화면을 조작한 확인은 아니다.

## 1. 구현 수용

- 수익률을 실제로 계산한 시작·끝 가격 행의 날짜를 PC 응답에 전달하고, 시장 저장 최신일로 대체하지 않는 구현을 수용한다. 기존 수익률·차이 값·선정·정렬·필터를 보존한 계약도 충족했다.
- KODEX200의 실제 사용 기간, 기간 같음·다름·미확인 구분과 %p 표기를 수용한다. 서로 다른 기간을 같은 기간 초과수익으로 설명하지 않도록 화면·복사문을 정정한 것은 PLAN 판정대로다. 계산 기간 자체를 통일한 것으로 기록하지 않는다.
- 공통 기간의 전부 확인·전부 일치 조건, 실제 시장 저장 최신일과 후보 끝일 비교, 시작일이 여러 종류일 때의 표시, 일부·전체 미확인 구분을 수용한다. 단기 흐름·일간 점검까지 같은 날짜 판정을 쓰는 복사문도 충족했다.
- 결과서 §4의 구현 판단을 모두 수용한다. 단건 단기 흐름의 날짜 전달, 기존 계산과 같은 행을 선택하는 KODEX200 날짜 helper, 공통 비교 안내, 복사문 제목·설명 정정은 승인 범위 안이다.
- 기존 AI 세션 `data_quality_snapshot`에 날짜 두 키가 추가되는 것도 수용한다. 기존 객체를 저장하는 경로의 부가 정보이며, 후보 스냅샷 형식·기존 키와 값·저장 경로를 바꾸거나 과거 기록을 다시 쓰는 작업은 아니다.

## 2. 검증과 한계 수용

- 사용자 수정 목업·실화면 확인과 검증자 r1 VERIFIED를 수용한다. 검증자의 관련 backend 105건·frontend 35건, 고정 HEAD 대비 기본 호출 12조합 출력 및 SELECT 내용·순서 일치가 핵심 직접 근거다.
- 전체 backend 3,732건·frontend 691건·변이 backend 13종·frontend 18종은 개발자 수행 근거로 구분해 수용한다. 이를 검증자가 전체 재실행한 수치로 합치지 않는다.
- 결과서 §5의 한계를 수용한다. 기존 전달 초안의 날짜 미확인, 격리 fixture로 확인한 상태, 선택 기간만 날짜가 없는 경우의 값 아래 안내, 0의 부호 표기 차이는 추가 수정 조건이 아니다.
- OCI 날짜 문장과 호환 `basis_*` 필드의 기존 의미, 다른 화면의 예전 '초과' 명칭, 후보와 KODEX200의 산식 차이는 이번에 해소한 것으로 기록하지 않는다. 기존 관찰을 보존하며 해당 화면까지 임의로 수정 범위를 넓히지 않는다.
- `MarketDiscoveryView.tsx` 866줄은 기존 근접 상태로 수용한다. 기간 표시 책임을 별도 컴포넌트에 둔 현재 구현을 종료하기 위해 선행 리팩터를 추가하지 않는다.

## 3. 종료 지시

1. 기존 결과서 끝에 본 판정 원문과 종료 기록을 붙이고 상태를 `IMPLEMENTED_VERIFIED_CLOSED`로 정리한다. STATE·PROGRAM_TRUTH·BACKLOG의 이번 단계 상태와 PC 기간 표시 관찰의 해소 범위를 맞춘다. 별도 인계 문서는 필요 없다.
2. 이번 단계의 사용자 승인 범위에서 구현·시험·종료 기록을 함께 커밋·push한다. 동일 범위 승인이 이미 있으면 재요청하지 않고, 없으면 사용자에게 한 번 받는다. 본 RESULT 판정이 사용자 push 승인을 대신하지는 않는다.
3. 판정·종료 문서만 반영하는 경우 재검증·재판정은 필요 없다. 추가 실화면·PC 재기동·OCI pull·거래일 대기도 종료 조건에 붙이지 않는다.
