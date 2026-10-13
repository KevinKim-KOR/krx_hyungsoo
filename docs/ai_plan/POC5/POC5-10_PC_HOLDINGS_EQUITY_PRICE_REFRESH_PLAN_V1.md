# POC5-10 — PC 보유 개별주 가격 수집 대상 보완 개발 PLAN V1

작성 2026-10-13 · 작성자: 개발자(VSCode Claude) · 수신: 설계자(웹 GPT)

```text
STATUS        = PLAN 확정 — 설계자 PASS(2026-10-13 · 원문 = POC5-09 설계서 §10-4 · §10-5 · 재제출 없음) · 반영 = §6 · 구현은 09 검증과 섞이지 않게(§6-4)
DESIGN        = docs/ai_design/POC5/POC5-09_STORED_VOLUME_EVIDENCE_DESIGN_V1.md §9-6(판정 '바로 이어갈 수집 원인 보완') — 별도 설계서 없음
RELATED       = POC5-09(날짜 · 비교 오용 정정 · 로컬 구현 · 검증 대기) · BACKLOG DEF-PRICE-EQUITY-REFRESH(2026-10-13 재개)
BASE_COMMIT   = c5613b6c (+ POC5-09 미커밋 변경과 겹치는 파일 없음 — 이 PLAN 은 app/market_refresh_service.py 만)
QUESTIONS     = 0 — Q-1 POC5-10 확정 · Q-2 (a) · Q-3 별도 로그 행(§6)
USER_APPROVAL = 실제 외부 조회(FDR) 실행 = 사용자가 「요즘 잘 오르는 ETF」 '최신 시장 데이터 갱신'을 누를 때(기존 절차) · 새 의존성 · 스키마 · 파일 삭제 0
```

## 1. 현재 (2026-10-13 실측 · 읽기 전용)

| 확인 | 값 |
|---|---|
| PC 수동 갱신 가격 대상 | `app/market_refresh_service.py:307` `list_etf_tickers(db_path)` = `etf_master` 1,188종목(ETF만) → `market_data_fdr.refresh_price_history(…, lookback_days=120)` |
| 보유 중 `etf_master` 밖 종목 | 3 — 000660 · 005930 · 006400(보유 29종목 중) |
| 그 3종목 PC 저장 가격 | 2026-03-30 ~ **2026-08-12** · 93행 · 출처 FinanceDataReader · 그 뒤 없음 |
| OCI 08:10 배치 | `three_push_runtime/market_data_batch.py :: collect_approved_tickers`(승인 seed ∪ 현재 보유) → `refresh_approved_prices`(종목마다 **마지막 저장일부터** 끝 날짜까지 증분 · 같은 `refresh_price_history` 재사용 · 실패는 종목 단위로 셈) |
| 실패 시 오용 | POC5-09 날짜 판정(`app/pc_price_basis.py`)이 기준일이 다른 값을 현재 비교 · 최대 3개에서 계속 뺀다 — 수집이 실패해도 08-12 값이 다시 들어가지 않는다 |

## 2. 변경 방향 (PC 전용 · `app/market_refresh_service.py` 한 곳)

1. `_execute_refresh_job` 의 ETF 가격 수집 **뒤**에 단계 하나를 더한다.
   - 대상 = 현재 보유 종목 − `etf_master` 종목(중복 없음 · 입력 순서 유지).
   - 개별주를 `etf_master` 에 등록하지 않는다. 그래서 「요즘 잘 오르는 ETF」 후보(`compute_topn`) · ML 특징값(`ml_feature_builder`)의 ETF 목록은 바뀌지 않는다.
2. 그 대상을 OCI 와 같은 기존 함수 `refresh_approved_prices(대상, end_date=…, db_path=…)` 로 받는다.
   - 마지막 저장일(08-12)부터 끝 날짜까지 누락 구간을 채운다. 최신 하루만 붙이지 않는다(판정 §9-6).
   - 저장은 기존 `etf_daily_price` upsert(같은 자료원 FinanceDataReader · 새 자료원 · 스키마 · API 0)다.
   - `refresh_price_history`(OCI 와 공유) 본문은 바꾸지 않는다.
3. ETF 단계 결과(attempted / success / fail · error_summary)의 뜻은 그대로 둔다. 보유 개별주 단계 결과는 Q-3 대로 따로 남긴다.
4. 수집 뒤 3종목 기준일이 PC 비교 기준일(KODEX200)과 같아지면, POC5-09 날짜 판정이 그 값을 자동으로 현재 비교에 돌려놓는다.
   - 20일 비교 기간이 KODEX200 과 다르면(예: 거래 정지일) 그 KODEX200 대비만 비운 채 남는다 — 기존 정정 규칙.
   - 추가 복귀 코드는 없다.
5. 범위 밖: 자동 · 정기 갱신 · 갱신 횟수 · 대기 시간 제한 · 새 버튼 · OCI 변경. PC FDR 요청 시간 상한(`DEF-FDR-TIMEOUT` PC 경로 · 조건부)은 이번에 더하지 않는다. 추가 대상은 지금 3종목이다(실제 외부 요청 수는 종목 · 수집 함수 동작에 따라 다르다).

## 3. 시험 (tmp DB · 가짜 fetcher · 외부 호출 0)

- 대상 = 보유 − `etf_master`(ETF 보유는 중복 수집 안 함) · `etf_master` 에 새 행 없음
- 증분 시작 = 그 종목 마지막 저장일(08-12) · 끝 날짜까지 행이 채워짐 · 그 이전 행은 다시 받지 않음
- 그 종목만 실패해도 ETF 단계 결과 · 상태가 바뀌지 않음 · 실패가 기록됨(Q-3)
- 수집 뒤 `apply_pc_price_basis` 가 그 종목을 `ok` 로 보고 최대 3개 후보로 돌려놓음(기준일 · 20일 기간 같을 때)
- 보유 읽기 실패 처리(Q-2)
- 기존 `market_refresh_service` 시험 · `market_data_batch` 시험 회귀 0 · `refresh_price_history` 불변

## 4. 문서 · 배포

- 결과서 · PROGRAM_TRUTH(§13-8 '수집 원인 = OPEN' → 해소) · BACKLOG `DEF-PRICE-EQUITY-REFRESH`(수집 원인 해소) · STATE 를 고친다.
- PC 전용이라 OCI pull 은 없다. 실제 확인은 사용자가 갱신 버튼을 1회 누른 뒤 3종목 기준일 · 「확인 근거」 · 「오늘의 투자 점검」 복귀로 한다.

## 5. 설계자 질문

- **Q-1 단계 번호**: 이 작업을 `POC5-10` 으로 둘지(제안), 다른 번호로 둘지.
- **Q-2 보유 파일을 읽지 못할 때**(손상 등)
  - 제안 (a): ETF 갱신은 그대로 마치고, 보유 개별주 단계만 실패로 기록한다. 기존 KOSPI 단계와 같은 방식이다(실패해도 전체 갱신을 멈추지 않고 별도 기록). 개별주 값은 날짜 판정이 계속 막는다.
  - (b): 갱신 전체를 실패로 둔다.
- **Q-3 결과 기록 위치**
  - 제안: `market_refresh_log` 에 별도 행(`holdings-equity-prices-<refresh_id>` · 시도 · 성공 · 실패 · 실패 예)을 남긴다. 실패가 있으면 갱신 상태 `error_summary` 끝에 'holdings_equity_partial_failure: fail=N' 을 붙여 화면에도 보이게 한다.
  - 다른 안: ETF 수와 합쳐 센다 — 1,188 의 뜻이 바뀌므로 비추천.

## 6. 설계자 판정 반영 (2026-10-13 · PASS · 원문 = POC5-09 설계서 §10-4 · §10-5)

1. **번호** = `POC5-10`. **보유 파일 읽기 실패** = (a): ETF 갱신은 그대로 마치고, 보유 개별주 단계만 실패로 기록한다. 읽기 실패를 빈 보유로 바꾸지 않는다. 유효한 빈 보유 · 대상 0종목은 정상인 '대상 없음'이다.
2. **기록**: `market_refresh_log` 별도 행 `holdings-equity-prices-<refresh_id>`(시도 · 성공 · 실패 · 실패 예)을 남기고, ETF 수와 합치지 않는다.
   - 실패는 기존 갱신 상태 `error_summary` 에 한국어로도 알린다: '보유 개별주 가격 갱신 일부 실패(N종목)' / '보유 목록을 읽지 못해 개별주 가격을 갱신하지 못했습니다'.
   - 기술 식별자는 로그 행에만 남긴다.
3. **기존 조회와 섞이지 않는지 확인**: 별도 행이 '마지막 전체 갱신' 조회(`latest_refresh_log` · 화면 `latest_refresh`) · ETF 건수 · 전체 작업 ID 를 잘못 대신하지 않는지 확인한다. 문제가 있으면 그 조회의 행 구분만 보완한다(새 로그 체계 · 표 없음).
4. **경계**
   - `refresh_approved_prices(대상, end_date=같은 갱신 작업의 end_date, db_path=PC DB)` 로 마지막 저장일부터 증분 수집한다. 경계일 중복 조회 · upsert 는 기존 방식대로 허용한다.
   - 실제 반환 자료 없이 기준일을 앞당기지 않는다.
   - 공유 수집 함수 본문 · OCI 상태 · cron · PUSH 는 바꾸지 않는다. 재사용 함수가 지정한 PC DB 만 쓰는지 확인한다.
   - **09 검증 중에는 09 검증 대상 소스를 바꾸지 않는다** — 10 코드는 09 판정 · 커밋 뒤 작업 트리에서 시작한다(두 작업의 변경 · 검증 근거를 구분).
5. **시험**: 격리 DB · 가짜 수집기. 대상 선정 · 증분 구간 · 종목별 실패 · 보유 읽기 실패 · 대상 없음 · 로그 구분 · 09 날짜 판정 연결(날짜 맞으면 복귀 · 실패로 옛 자료가 남으면 계속 제외).
6. **완료 확인**: 사용자가 기존 갱신 버튼을 1회 누른 뒤 실제 저장 날짜 · 누락 구간 · 화면을 확인하고 나서 수집 원인 결함(`DEF-PRICE-EQUITY-REFRESH`)을 닫는다. OCI pull 은 없다.


## 7. 구현 메모 (2026-10-13 · 09 종료 커밋 `7f394deb` 뒤 시작)

- 단계 본문은 새 모듈 `app/holdings_equity_refresh.py`(KS-10 — 서비스 파일이 근접 600줄을 넘지 않게). `market_refresh_service._execute_refresh_job` 는 ETF 가격 단계 뒤 · KOSPI 단계 앞에서 부르고, 문구를 `error_summary` 끝에 붙인다.
- 순서 이유: 기존 '마지막 refresh'(`latest_refresh_log()` · 출처 구분 없음)가 KOSPI 단계 행을 가리키므로, 그 앞에 두어 화면 · 연결 ID 를 바꾸지 않는다(§6-3 확인 결과 — 조회는 고치지 않음).
- 실패 수 = 시도 − 성공(공유 함수가 수집 실패 · 저장 행 없음 종목을 두 번 셀 수 있음 · 본문 변경 0).
- **사용자 결정(2026-10-13)**: 갱신 완료 줄은 예전에 사유를 보이지 않았다. 사유가 있으면 '확인 필요: …'를 붙인다(`MarketDiscoveryView.tsx`). 기존 ETF · KOSPI 부분 실패 사유(영문)도 함께 보인다.
- 독립 검토 반영(2026-10-13): 성공 · 실패는 종목마다 직접 센다(공유 함수는 이중 집계로 다른 종목 성공까지 깎을 수 있음) · 보유 파일 없음도 읽기 실패(정상 빈 보유 = 파일 있음 · 0행 — `holdings.py` 계약 · OCI 와 같음) · 단계 안 실패도 로그 행 · 로그 기록 실패는 결과 문구를 바꾸지 않음.
- 검증자 r1 정정(2026-10-13): '마지막 전체 갱신' 보존을 순서가 아니라 조회 행 구분으로 — 이 단계는 종목별 기록 행 없이 수집 · 저장(`_fetch_and_store_without_log` → `refresh_approved_prices`) · 요약 행 출처를 `latest_refresh_log(exclude_source=…)` 로 뺀다(`market_topn_helpers._latest_refresh_payload`).
