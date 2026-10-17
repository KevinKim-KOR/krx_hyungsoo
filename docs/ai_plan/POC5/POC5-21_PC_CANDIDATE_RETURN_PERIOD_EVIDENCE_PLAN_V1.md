# POC5-21 개발 PLAN V1 — PC 후보 수익률의 실제 계산 기간 표시

작성 2026-10-17 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-21_PC_CANDIDATE_RETURN_PERIOD_EVIDENCE_DESIGN_V1.md`(V1) · 판정 `docs/ai_design/POC5/POC5-21_PC_CANDIDATE_RETURN_PERIOD_EVIDENCE_PLAN_DECISION_2026-10-17.md`

```text
STATUS   = 설계자 PLAN 판정 PASS(2026-10-17 · Q1 (b) · Q2 (a) · Q3 (b) + 보충 · §4) → 수정 목업 사용자 확인(2026-10-17 '목업 좋습니다.') → 구현(재제출 없음)
SCOPE    = 「요즘 잘 오르는 ETF」 PC 응답 · 후보 카드 / 표 · AI 해석용 복사문
           새 메뉴 · 카드 · 펼침 · API 경로 · DB 표 · DB 쓰기 · 추가 SELECT · 외부 조회 · 의존성 · OCI 문장 · PUSH · PARAM 변경 0
           「보유와 비교」 탭 · 「ETF 비교하기」 화면 표시는 바꾸지 않음(설계 §3 = 후보 목록 · 카드 · 복사문)
MEASURED = 2026-10-17 · 시장 DB 읽기 전용 사본(시장 저장 최신일 2026-10-14) · 코드 경로 grep / read
```

## 1. 값별 실제 계산 행 · 날짜 (현재 코드 · BACKLOG POC5-11 관찰은 지금도 같다)

| 화면 · 복사문 값 | 계산 위치 | 시작 행 | 끝 행 | 지금 응답의 날짜 |
|---|---|---|---|---|
| 일간 · 1 / 3 / 6 / 12개월 · 3년 (`returns.*`) | `market_topn_helpers._compute_period` ← `compute_topn` 이 종목마다 `fetch_price_history`(close>0 · 날짜 오름차순) 1회 | 일간 = 끝 바로 앞 저장 행 · 나머지 = 시장 저장 최신일 − 30 / 90 / 180 / 365 / 1,095일 **이상** 첫 행(상장이 짧으면 첫 저장 행) | 그 종목 마지막 저장 행 | `basis_start_date` = 실제 시작 행 · `basis_end_date` = **시장 저장 최신일**(`asof_iso` · 실제 끝 행 아님) |
| `selected_basis_*` | `compute_topn` | `returns[basis]` 복사 | 〃 | 〃 |
| 복사문 [데이터 품질] 일간 | `short_term_momentum.compute_daily_return_check`(별도 읽기 · 호출처는 PC 응답 보강 1곳) | series[-2] | series[-1] | 날짜 없음 |
| 복사문 [단기 흐름] 5 / 10 / 20거래일 | `compute_short_term_momentum_batch`(PC 보강 · 보유 근거 2곳 · 보유 근거는 필드를 하나씩 옮겨 담음) | 끝에서 5 / 10 / 20행 앞 | 마지막 행 | 후보 `start_dates` · `end_date` 는 응답에 있음 · KODEX200 쪽 날짜 없음 |
| KODEX200 대비 1M / 3M(카드 · 표 · 복사문) | 후보 1 / 3개월(위) − KODEX200 1M / 3M(`market_regime.compute_kodex200_metrics` · 같은 `compute_topn` 이 읽은 069500 이력 · 끝에서 20 / 60행 앞) | 두 창 정의가 다름 | — | 날짜 없음 |

- 최상위 `asof` = `_latest_date_in_db` = 가격 표 `etf_daily_price` 전체 `MAX(date)` = **시장 저장 최신일**. 이 표에는 보유 개별주 3종목(000660 · 005930 · 006400)도 있다(사본 실측). 화면 요약 「시장 데이터 기준일」, 복사문 머리말 「{asof} 기준 … 결과」 · 「데이터 기준일」이 이 값이다(후보 끝일을 보증하지 않음). `market_context.asof` = KODEX200 날짜(POC5-11) 그대로.
- 일간도 실제 저장 행(직전 저장일)을 고르므로 날짜를 만들어 붙이는 값이 아니다. 화면 · 복사문은 「직전 저장일 대비 · 사용 종가 A → B」로 쓴다.
- 실측(사본 2026-10-14): 기본 1개월 상위 10 = 10개 모두 2026-09-14 → 10-14. 일간 · 1 · 3개월 × 오름 · 내림 6가지 상위 10에 끝일이 시장 저장 최신일과 다른 후보 없음(가격이 있는 1,195종목 중 16종목은 마지막 저장일이 2026-10-14보다 이름). 3개월 상위 10의 1개(0223A0)는 시작 2026-07-28. 6 · 12개월 · 3년은 상장이 짧은 종목이 첫 저장일부터라 시작일이 갈림(예: 0209D0 세 값 모두 2026-06-23부터 · 같은 +11.89%).
- KODEX200 실측: 1M 2026-09-10 → 10-14 · 3M 2026-07-14 → 10-14(후보 1개월 09-14 · 3개월 07-16 시작과 다름 → 「기간 다른 수익률 차이」). 같은 행으로 `return_1m_pct` −15.06 · `return_3m_pct` −13.23 재계산 일치. 단기 5 / 10 / 20 구간은 후보와 KODEX200 시작일이 같다(10-06 · 09-28 · 09-10).

## 2. 최소 전달 방식

- `_PeriodResult` 에 기본값 있는 `end_date` 추가(성공 시 끝 행 날짜). 기존 필드 · 순서 그대로.
- `compute_topn(..., actual_price_dates: bool = False)` — True 면 (1) 기간 dict 에 `price_start_date`(시작 행) · `price_end_date`(끝 행), (2) `market_context.kodex200` 에 `return_1m_start_date` · `return_3m_start_date` · `return_end_date`(이미 읽은 069500 이력에서 `compute_kodex200_metrics` 와 같은 거르기 · 같은 20 / 60행 · 작은 helper 를 `market_regime.py` 그 함수 옆에). 기본 False 는 출력이 지금과 같다 → 다른 호출 7곳(`api_holdings_market_evidence` · `draft` · `draft_three_push` 2 · `ml_score_validity_screen` · `api_decision_draft_preview` 2) 출력 불변. `basis_*` 의미 · 호환 목록(`daily_topn` 등) · 정렬 · 선정 · 필터 · 수익률 · 차이 숫자 불변.
- `GET /market/topn/latest` 만 True. 모델 `MarketPeriodReturn` 선택 필드 2 · `MarketContextKodex200` 선택 필드 3 · 연결.
- `ShortTermMomentum` 에 `kodex200_start_date_5d / 10d / 20d` · `kodex200_end_date`(batch 가 이미 읽은 KODEX200 이력 · 추가 조회 0) → PC 모델 `kodex200_start_dates` · `kodex200_end_date`. 보유 근거 API 는 필드를 하나씩 옮겨 담아 출력 불변.
- `DailyReturnCheck` · `DailyReturnCheckPayload` 선택 필드 `price_start_date` · `price_end_date`(같은 series 의 [-2] · [-1]).
- 화면 · 복사문 판정 하나(`lib/returnPeriod.ts`): 값 없음 → 지금처럼 `-` · 값은 있는데 날짜 하나라도 없음 → 「계산 기간 확인 불가」(시장 저장 최신일로 채우지 않음) · 둘 다 있음 → 그 날짜.
- 공통 안내(판정 Q3): 선택 기간 값이 있는 표시 후보의 날짜가 **모두 확인되고 모두 같을 때만** 「시작 → 끝 종가 · 표시 후보 N개 모두 같음」. 일부 미확인 = 「날짜 확인된 n개 같음 · m개 계산 기간 확인 불가」 + 그 후보 이름 옆. 여러 종류 = 「종목별 계산 기간 다름」 + 같은 시작 / 끝은 「공통」으로 묶음. 시작일이 여러 종류인 기간은 **모든 값 아래 실제 시작일**. 전부 미확인 = 위 줄 한 번.
- 끝일: 후보 끝일 ≠ 시장 저장 최신일이면 이름 옆 「수익률 끝일 YYYY-MM-DD」(다수의 날짜로 기준을 바꾸지 않음).
- KODEX200 대비(판정 Q1): 값 단위 % → **%p**(숫자 그대로). 후보 목록 위 둘째 줄 「KODEX200 대비 1M · 3M — 기간 다른 수익률 차이 / 같은 기간 수익률 차이 / 후보별로 다름 — 값 아래 표시 (%p)」 · 후보마다 다를 때만 값 아래 「기간 다름 / 같은 기간 / 기간 확인 불가」 · 양쪽 실제 시작 ~ 끝과 '같은 기간 초과수익이나 시장 우위를 확인한 값이 아님'은 그 줄의 [?].
- 그 밖 화면: [?] 에 계산 정의 · 6개 기간 날짜 · 짧은 저장 이력이면 그 기간 전체의 수익률이 아님. 요약 명칭 「시장 저장 최신일 (저장된 전체 종목 가격 중 가장 늦은 저장일)」. 표 아래 안내 「6개월 / 12개월 / 1년 / 3년」 → 「6개월 / 12개월 / 3년」.
- 복사문(공통 생성기 `buildMarketDiscoveryCopyText` 1곳 — 수동 복사 · AI 세션 · ETF 구성종목 전달이 같이 씀): 수익률 줄마다 「(사용 종가 시작 → 끝)」 · 일간 「(직전 저장일 대비 · 사용 종가 …)」 · [데이터 품질] 「(정상 · 사용 종가 …)」 · KODEX200 대비 줄 「… 수익률 차이: +x%p (기간 다름 — 후보 A → B · KODEX200 C → D)」 / 「(같은 기간 A → B)」 / 「(기간 확인 불가 — …)」 · 섹션 제목 [시장 대비 후보 강도] → [KODEX200 대비 수익률 차이] · [요청] 「KODEX200(/KOSPI) 대비 초과수익」 → 「KODEX200 대비 수익률 차이(기간이 다르면 괄호에 두 기간)」 · 머리말은 시장 저장 최신일을 따로 적고 '○○ 기준 결과'라고 쓰지 않음. AI 세션에 저장되는 `candidate_snapshot` 형식은 그대로(날짜는 질문 본문에 실림).
- KS-10: `MarketDiscoveryView.tsx` 861줄 → +5줄 이내(전달만). 기간 표시는 새 `ReturnPeriodLine.tsx` 로.

## 3. 변경 파일 · 시험

- 백엔드 수정: `app/market_topn_helpers.py` · `app/market_topn.py` · `app/market_regime.py`(날짜 helper) · `app/short_term_momentum.py` · `app/api_market_topn.py` · `app/api_market_topn_models.py` · `app/api_market_topn_service.py`.
- 프론트: 신규 `lib/returnPeriod.ts` · `app/components/ReturnPeriodLine.tsx` · 수정 `CandidateCards.tsx` · `CandidateTable.tsx` · `MarketDiscoveryView.tsx` · `lib/api/market.ts` · `lib/api/marketEvidence.ts` · `lib/marketDiscoveryCopyText.ts` · `app/globals.css`.
- 신규 시험 `tests/test_poc5_21_return_period_dates.py`(임시 DB): 실제 선택 행 날짜 ↔ 수익률(두 종가로 재계산) · **실제 끝 가격 행이 같으면 끝일 불변**(다른 종목 최신일이 늘어 시작 행이 바뀌면 시작일은 그 행을 따름 · 판정 §2) · 같은 끝일 · 다른 시작일 · 결측(제외 사유 · 수 그대로) · KODEX200 1M / 3M · 단기 5 / 10 / 20 날짜 ↔ 그 수익률 재계산 · flag 꺼짐 출력 = 변경 전(7곳 경로) · flag 켜고 끔의 수익률 · 정렬 · 선정 같음 · `fetch_price_history` 호출 수 같음(추가 조회 0) · 개별주만 더 최신이면 `asof` = 그 날짜(후보 끝일과 다름) · 보유 근거 단기 흐름 출력 불변 · API 응답에 날짜 실림.
- 프론트 시험: 판정(모두 같음 · 일부 미확인 · 전부 미확인 · 시작 여러 종류 → 모든 값 시작일 · 끝일 ≠ 시장 저장 최신일 · 다수가 옛 끝일이어도 기준 불변) · KODEX200 비교(같음 · 다름 · 섞임 · 미확인 · %p) · 정상 자료에서 표시 줄 2개 · 후보 표시 0 · 화면에 보인 날짜 = 복사문 날짜 · 개별주만 더 최신 명칭 · 기존 복사문 시험 갱신.
- 회귀: 백엔드 전체 pytest · vitest · tsc · eslint · black · flake8.
- 목업(로컬 · 게시 안 함): 1440 · 1000px 정상 / 3개월 실제 시작일 다름 / 끝일 다름 · 확인 불가(한 후보 · 전체) · 개별주만 더 최신(격리 fixture) + [?] 2개 · 표 · 펼침 · 복사문 예시.

## 4. 설계자 PLAN 판정 반영 (2026-10-17 · PASS)

- Q1 (b): KODEX200 쪽 실제 시작 · 끝을 전달 · 표시. 계산 · 숫자 · 정렬 · 선정 그대로. 단위 %p. 기간이 다르면 「기간 다른 수익률 차이」 · 같은 기간 초과수익이나 시장 우위로 설명하지 않음(복사문 제목 · 설명 포함).
- Q2 (a): 복사문 단기 흐름 5 / 10 / 20 · 데이터 품질 일간에도 실제 날짜(이미 있는 날짜 · 같은 계산의 행).
- Q3 (b) + 보충: 끝일은 시장 저장 최신일과 비교 · 과반 기준 폐기 · '모두 같음'은 전부 확인 · 전부 같을 때만 · 여러 종류면 「종목별 계산 기간 다름」 · 시작일 여러 종류면 모든 값 실제 시작일.
- 보충: 요약 명칭 '저장된 전체 종목 가격' · 짧은 이력 값은 그 기간 전체 수익률로 설명하지 않음 · 표 아래 「1년」 문구 같은 작업에서 정정 · 시험 문장 정정(끝 가격 행이 같으면 끝일 불변) · 시험 보충(§3).
- 진행: 수정 목업 사용자 확인 완료(2026-10-17 '목업 좋습니다.') → 바로 구현 · 커밋 · push 는 별도 승인.
