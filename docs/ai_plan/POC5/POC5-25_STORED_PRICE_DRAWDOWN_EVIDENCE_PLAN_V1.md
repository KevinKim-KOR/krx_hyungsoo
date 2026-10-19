# POC5-25 개발 PLAN V1 — 현재 저장 종가의 고점 대비 근거 정정

작성 2026-10-19 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_DESIGN_V1.md`(V1)

```text
STATUS   = 설계자 PLAN PASS(2026-10-19 · Q1 (a) · Q2 (a)) · 사용자 목업 확인(2026-10-19) · 구현 완료 · 사용자 실화면 확인(2026-10-19) · 검증자 r1 VERIFIED(2026-10-19 · 결과서 §12) · 설계자 RESULT PASS(2026-10-19 · 결과서 §13) · IMPLEMENTED_VERIFIED_CLOSED(종료 2026-10-19) · 결과서 docs/ai_result/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_RESULT.md
SCOPE    = 「요즘 잘 오르는 ETF」 카드 펼침 · 표 · 「ETF 비교하기」 정렬 · 카드 줄 · 상세의 고점 대비 → 현재 PC 저장 종가 20개 기준
           새 수집 · 외부 조회 · 모델 실행 · feature 적재 · DB 표 · OCI · PUSH · cron · PARAM · ML · 위험 분류 변경 0
MEASURED = 2026-10-19 · 코드 grep / read(HEAD 9df40437) · 수치 = 사본 DB(시장 저장 최신일 2026-10-14 · 라이브와 같은 날짜) · 라이브 DB 는 mode=ro 읽기만
```

## 1. 지금 고점 대비의 원천 · 소비처 (설계 §4-1)

- **원천**: `app/api_market_topn_service.py :: merge_relative_upside_score` 가 `state/ml/relative_upside_score_latest.json`(참고점수 v0 · POC3-ML-02 REJECT · 스냅샷 `asof_date` 2026-08-27 · 생성 2026-08-30 · 1,162종목 중 08-27 1,144 · 08-26 8 · 06-24 ~ 07-08 10)의 `drawdown_20d` 를 PC 시장 목록 응답(`GET /market/topn/latest` · `app/api_market_topn.py`) 후보에 붙인다. 응답에는 스냅샷 전체 날짜(`relative_upside_score_asof_date`)만 있고 종목별 날짜가 없다. 보유 근거 API · OCI 경로에는 붙지 않는다.
- **옛 정의**(`app/ml_relative_upside_features.py`): 거른 읽기(종가 null · 0 이하 행 제외) 이력의 i−19 ~ i 20행 · 창 안 양수 종가만 최대 · 비율(−0.10) · 출처 · 가격 기준 연결 검사 없음 · 스냅샷 생성 시점 값. 새 PC 관측값(설계 §2)과 다른 점: 원본 행(비정상 행이 있으면 값 없음 · 거르지 않음) · 연결 검사 · 현재 기준일 D · % 단위 · 기간 · 고점 날짜.
- **소비처(화면 3곳 · 정렬 1)** — 모두 같은 PC 시장 목록 API(「요즘 잘 오르는 ETF」 n=10 · 「ETF 비교하기」 n=30):
  - 「요즘 잘 오르는 ETF」 카드 펼침 '고점 대비'(`CandidateCards.tsx` · `drawdown_20d × 100`) · 표 '고점 대비' 칸(`CandidateTable.tsx` · 정렬 없음 · 표 정렬은 서버 기준 일간 · 1개월 · 3개월만).
  - 「ETF 비교하기」(`JudgmentWorkbenchView.tsx` · `workbench/helpers.ts :: candDrawdown`): 정렬 버튼 '고점대비'(화면 로컬 · 처음 누르면 오름 = 값 작은 순 · 다시 누르면 내림 · 값 없음 = `-Infinity` 라 오름에서 맨 앞 · 내림에서 맨 뒤) · 카드 아래 '고점대비' 줄 · 상세 '고점 대비' 칸.
  - 서버 조회 조건에 고점 정렬 없음(basis = 일간 · 1개월 · 3개월).
  - **복사문 · AI 전달: 고점 대비를 싣는 곳 없음** — `lib/marketDiscoveryCopyText.ts` · `TransferToAISessionsCard`(`candidate_snapshot`) · 「ETF 구성종목」 초안 · POC5-23 미리보기(그때 제거). 새 항목을 더하지 않는다(설계 §3).
  - 다른 '고점 대비'(범위 밖 · 다른 원천): 코스피 최근 1년 고점 대비(「오늘의 투자 점검」) · OCI 보유 브리핑 `holdings_selection.drawdown_20d_pct` · ML 실험 카드 · `MLFeatureSanityCard`.

## 2. 계산 · 연결안 (설계 §2 · §3 · §4-2)

- **새 모듈 `app/pc_stored_drawdown.py`**(POC5-16 `app/pc_price_volatility.py` 방식):
  - 기준일 D = 후보 응답의 POC5-21 실제 끝 행 날짜 `returns.*.price_end_date`(= 그 종목 마지막 유효 종가 행 · `fetch_price_history` 거른 읽기 · POC5-16 E 와 같은 정의). 시장 최신일 · 스냅샷 날짜로 대신하지 않는다.
  - 창 = D 이하 원본 저장 행 최근 20개(`etf_daily_price` · `mode=ro` 연결 하나 · 후보마다 `LIMIT 20` · n=10 이면 10번 · 30 이면 30번). 기존 `fetch_price_history` 는 걸러진 행이라 재사용하지 않는다(설계 '비정상 행을 빼고 채우지 않음').
  - 판정 순서: D 없음 → `no_price` · 20행 미만 → `insufficient_history` · 비정상 종가(`reentry_review.prices.valid_close`) · 허용 밖 출처(`ALLOWED_SOURCES`) → `invalid_price` · 연결 확인 불가(`pc_price_volatility._link_unconfirmed` = POC5-06 `link_break` 그대로) → `basis_unconfirmed` · 통과 → H = 20개 종가 최대 · 고점일 = H 와 같은 가장 최근 날짜 · 값 = (D 종가 ÷ H − 1) × 100 · 소수 4자리.
  - 응답 선택 객체 `stored_drawdown_20`(`MarketCandidate`): `status`(ok · unavailable) · `reason` · `value_pct` · `end_date`(D) · `start_date`(창 첫 행) · `close` · `peak_close` · `peak_date` · `rows`.
- **연결 위치**: `app/api_market_topn.py :: get_market_topn_latest` 에서만(기존 enrich · 머지 뒤 · POC5-21 · 22 와 같은 'PC 화면 API 만'). `compute_topn` · 다른 호출(보유 근거 API · OCI · 스크립트) 그대로. 옛 `drawdown_20d` 머지 · 필드 · 연구 정의 그대로(설계 §2 '과거 필드 의미 그대로') — 화면 · 정렬은 새 객체만 읽고, 없으면 옛 값으로 채우지 않는다.
- **화면(공통 helper `frontend/lib/storedDrawdown.ts` 하나)**: 표시 · 사유 · 기간 묶음 · 정렬 값 · ? 문구.
  - 이름 '20저장일 종가 고점 대비'. 숫자는 각 화면의 기존 % 함수(카드 · 표 `fmtPct` · 「ETF 비교하기」 `fmtPlainPct`). 0%(고점과 같음)는 중립 색.
  - 값 아래: 고점 날짜 · 공통 기간과 다를 때만 그 기간(POC5-21 '값 아래' 방식). 값이 없으면 값 자리에 사유('저장 종가 20개 미만' · '기간 안 비정상 종가' · '가격 기준 확인 필요' · '저장 종가 없음').
  - 「ETF 비교하기」 정렬: 같은 버튼 · 같은 방향 뜻(오름 = 값 작은 순) · **값 없음은 방향과 무관하게 맨 뒤**(지금은 오름에서 맨 앞) · 같은 값은 기존 순서(안정 정렬). 비교 규칙은 `workbench/helpers.ts` 로(화면 파일 845줄 · KS-10 근접 850 을 넘지 않게).
  - 펼침 칸 이름이 좁은 칸에서 글자 단위로 끊겨 `.cand-dcell .k` 에 `word-break: keep-all` 한 줄.
- **변경 파일(예정)**: 백엔드 `app/pc_stored_drawdown.py`(신규) · `app/api_market_topn_models.py` · `app/api_market_topn.py` / 화면 `frontend/lib/storedDrawdown.ts`(신규) · `lib/api/market.ts` · `ReturnPeriodLine.tsx` · `CandidateCards.tsx` · `CandidateTable.tsx` · `JudgmentWorkbenchView.tsx` · `workbench/helpers.ts` · `globals.css` / 시험(임시 DB) · PROGRAM_TRUTH · STATE.
- **시험**: D 포함 20행 · 21번째 이전 행 무시 · 고점 중복 날짜 = 가장 최근 · 고점 = D(0%) · 19행 · 창 안 비정상 종가(null · 0 · 음수 · 문자) · 허용 밖 출처 · 연결 끊김 · 더 오래된 행으로 채우지 않음 · D = 실제 끝 행(시장 최신일 아님) · 실제 API 응답(tmp DB) · 옛 `drawdown_20d` 가 있어도 새 객체 없으면 화면 값 없음 · 정렬(오름 · 내림 · 값 없음 맨 뒤 · 동률 순서) · 기존 호출 보존 · 변이 · 전체 회귀.

## 3. 실제 ETF 대조 (설계 §4-3 · 사본 · 시장 저장 최신일 2026-10-14)

| ETF | 옛 스냅샷(2026-08-27) | 새 값(현재 저장 종가 20개) |
|---|---|---|
| SOL 반도체전공정 475300 | 0.00% | −13.84% · 2026-09-11 ~ 2026-10-14 · 고점 2026-10-06 28,550 · 10-14 종가 24,600 |
| HANARO 반도체핵심공정주도주 476260 | −1.35% | −11.85% · 고점 2026-10-06 |
| TIGER 글로벌AI사이버보안 418670 | −9.36% | −3.27% · 고점 2026-10-12 |
| SOL 전고체배터리&실리콘음극재 0005D0 | 0.00% | 0.00% · 고점 = 2026-10-14 |
| PLUS AI반도체소부장액티브 0239Z0 | 없음 | 값 없음 · 저장 종가 18개(20개 미만) |

- 「ETF 비교하기」 후보 30개(1개월 · 네 필터): 계산 29 · 20개 미만 1 · D 모두 2026-10-14(시장 저장 최신일과 같음) · 비정상 · 가격 기준 확인 필요 0(이번 자료). 기간 줄은 '2026-09-11 ~ 2026-10-14 저장 종가 20개 · 표시 후보 10개 모두 같음'.
- 기준일 불일치 · 가격 기준 확인 필요는 이번 자료에 없어 목업에서 응답 두 후보만 바꿔 보였다(§5).

## 4. 질문

**Q1. 기준일 D 가 시장 저장 최신일과 다른 후보**(예: 마지막 저장이 하루 늦게 빠진 종목). POC5-21 은 이런 후보 이름 옆에 '수익률 끝일 날짜'를 이미 보인다.
(a) **권장** — 그 종목 자신의 D 로 계산하고 값 아래 그 기간을 보인다(기간 줄은 '종목별 기간 다름 · 끝일 …'). 다른 종목 날짜 · 시장 최신일로 맞추지 않는다.
(b) D ≠ 시장 저장 최신일이면 값 없음 '기준일 다름'(POC5-16 보유 방식).

**Q2. 설명 · 기간 표시 위치.**
(a) **권장** — 「요즘 잘 오르는 ETF」 목록 위 기존 기간 상자에 셋째 줄 '20저장일 종가 고점 대비 · 기간(모두 같음 / 종목별 다름) · ?'(POC5-22 둘째 줄과 같은 방식 · 새 카드 · 펼치기 버튼 없음). 「ETF 비교하기」에는 ? 가 없으므로 상세 칸 한 줄에 기간 · 고점(날짜 · 종가).
(b) 기간 상자 줄 없이 값마다 기간 · 고점 날짜를 늘 보인다(? 없음).

## 5. 목업 (로컬 · 게시 안 함)

- 두 화면 전체 1440 · 1000px · 지금 / 바꾼 뒤: 카드(SOL 반도체전공정 펼침) · ? 펼침 · 표(오른쪽 끝까지 민 상태) · 「ETF 비교하기」 정렬 오름 · 내림 · 목록 끝 값 없음 · 상세.
- 사본 자료 · 백엔드 사본에 §2 계산을 시험 구현해 실제 값으로 그렸다(저장소 코드 변경 0). 만든 사례 2개(8위 기준일 10-13 · 5위 가격 기준 확인 필요)는 응답에서만 바꿨다고 그림 설명에 적었다.

## 6. 설계자 판정 반영 (2026-10-19 · 판정 원문 `docs/ai_design/POC5/POC5-25_STORED_PRICE_DRAWDOWN_EVIDENCE_PLAN_DECISION_2026-10-19.md`)

**PASS · Q1 (a) · Q2 (a) · 재제출 없음. 사용자 전체 화면 목업 확인(2026-10-19 · '확인함 · 그대로 진행') 뒤 구현.**

- Q1 (a) — 종목 자신의 D 로 계산 · 시장 최신일과 다르면 기존 '수익률 끝일' 안내 + 실제 기간(값 아래). 보유 근거 날짜 가드 · 동일 기간 KODEX200 규칙은 그대로.
- Q2 (a) — 「요즘 잘 오르는 ETF」 기간 상자 셋째 줄 + ? · 공통 기간 한 번 · 다른 종목만 기간 · 「ETF 비교하기」 상세 칸에 기간 · 고점 날짜 · 종가 · 새 카드 · 펼치기 버튼 없음.
- 판정 §3 그대로: 원본 20행 별도 읽기(종목별 LIMIT 20 · 읽기 전용 연결 하나) · 비정상 행 대체 없음 · 기존 유효 가격 · 허용 자료원 · 연결 검사 재사용 · 가장 늦은 고점일 · `stored_drawdown_20` 하나에서 값 · 단위 · 사유 · 옛 `drawdown_20d` 의미 · 연구 자료 그대로(대체 없음 · 100배 없음) · 값 없음 양방향 맨 뒤 · 동률 기존 순서 · 복사문 · AI 전달 변경 0 · 정렬 helper 분리 · 줄바꿈 CSS.
- 구현 중 정한 것: 허용 밖 출처 = `invalid_price`(§2 그대로 · POC5-06 `SOURCE_NOT_ALLOWED` · `BAD_CLOSE` 와 같은 묶음 · 처음 구현에서 연결 사유로 묶었던 것을 독립 검토 지적으로 되돌림) · D 를 정할 수 없거나 창 마지막 행이 D 가 아니면 `end_date_unknown` '기준일 확인 불가'(§2 의 `no_price` 이름 정정 · 창 끝 확인 추가) · 0%(고점과 같음)는 중립 색 · '+' 없이 '0.00%'(카드 · 「ETF 비교하기」의 기존 % 함수가 0 에 '+'를 붙여 `ddPct` 로 맞춤) · 「ETF 비교하기」 화면 파일 845 → 849줄(KS-10 근접 850 미만 · 정렬 규칙은 `workbench/helpers.ts :: drawdownMissingLast`).
- 별첨 백로그 처리 판정(`docs/ai_design/POC5/POC5_BACKLOG_DISPOSITION_DECISION_2026-10-19.md`)은 이번 문서 갱신에 함께 반영(BACKLOG 머리 '현재 처리 요약' · 통합지도 §6 · STATE) — 25 구현의 선행 조건 아님.
