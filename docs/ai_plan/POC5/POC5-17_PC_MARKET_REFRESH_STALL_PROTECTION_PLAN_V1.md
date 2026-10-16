# POC5-17 개발 PLAN V1 — PC 수동 갱신의 멈춤 보호(`DEF-FDR-TIMEOUT` 잔여)

작성 2026-10-16 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: 설계자 지시 원문 `docs/ai_design/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_REQUEST_2026-10-16.md`

```text
STATUS   = 설계자 PLAN PASS(2026-10-16 · Q1~Q3 (a) · 판정 원문 docs/ai_design/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_PLAN_DECISION_2026-10-16.md · 보충 §7) → 구현(2026-10-16) · 결과서 docs/ai_result/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_RESULT.md → 검증자 r1 REJECTED → 정정 → r2 VERIFIED → 설계자 RESULT PASS · 종료(2026-10-16)
SCOPE    = PC 「요즘 잘 오르는 ETF」 '최신 시장 데이터 갱신'(POST /market/refresh) 한 작업 안의 외부 조회 대기 상한
           OCI · PUSH · 새 메뉴 · 새 대기 시간 · 횟수 제한 · 자동 재시도 · 의존성 · DB 표 변경 0
```

## 1. 조사 결과

### 1-1. 지금 갱신 작업의 구조와 '잠금'
- 버튼 → `app/market_refresh_service.py :: start_refresh_job` → 백그라운드 스레드 하나가 단계를 차례로 돈다.
  - ETF 목록(`:313`) → ETF 가격(`:320` · 약 1,190종목 차례로) → 보유 개별주(`:341`) → KOSPI(`:359`) → VIX(`:401`) → NAV(`:414`) → 마지막 상태 기록(`:443~458`).
- '갱신 잠금' = 상태값 `running`(메모리 + `market_refresh_state` 행). `running` 이면 다시 눌러도 '이미 진행 중'으로 돌려보낸다(`:516`).
- 조회 하나가 응답 없이 멈추면 스레드가 마지막 상태 기록에 닿지 못해 `running` 이 남는다.
  - 화면은 확인 횟수 상한 뒤 '상태 확인 시간이 너무 길어졌습니다'(`MarketDiscoveryView.tsx:385`)를 보인다.
  - 다시 눌러도 막힌다. PC 서버를 다시 켜야 `running → failed` 로 풀린다(`:172` · 첫 읽기 때 정리).

### 1-2. 시간 제한이 없는 호출 (설치된 FinanceDataReader 0.9.202 원문 확인)
| 단계 | 호출 | 대기 상한 |
|---|---|---|
| ETF 목록 | `market_data_fdr.py:57` `fdr.StockListing("ETF/KR")` → `naver/listing.py:107` `requests.get(url)` | **없음** |
| ETF 가격 | `market_data_fdr.py:63` `fdr.DataReader(ticker, ...)` → `naver/data.py:9` `requests.get(url + symbol)` | **없음** |
| 보유 개별주 | `holdings_equity_refresh.py:62 · :76` → 위와 같은 `_default_price_fetcher` | **없음** |
| KOSPI | `market_briefing/krx_sync.py:97` `httpx.get(..., timeout=40)` | 40초 |
| VIX | `pc_vix_refresh.py:94` `fdr_request_timeout()` | 20초 |
| NAV | `naver_etf_universe_fetcher.py:200` `urlopen(timeout=8)` · 소켓 기본 15초 | 8초 · 15초 |

- 보호가 없는 곳은 FinanceDataReader 를 부르는 세 곳(ETF 목록 · ETF 가격 · 보유 개별주)이다. NAV · KOSPI · VIX 는 이미 상한이 있다.

### 1-3. 기존 보호 수단(재사용 대상)
- `app/three_push_runtime/market_data_batch.py :: fdr_request_timeout`(`:176` · 기본 20초 `:165`).
  - 블록 안의 `requests` 호출에 timeout 이 없을 때만 20초를 넣고, 빠져나오면 원래대로 되돌린다.
  - OCI 08:10 배치(OPS-03 · 2026-10-01 배포)와 PC VIX 단계(POC5-11)가 이미 쓴다.
- OCI 는 단계 전체 상한 180초(`:169`)도 쓴다. PC 정상 갱신이 그보다 길어(아래) 그대로 옮기지 않는다.
- 로컬 실측(외부 조회 0): 연결만 받고 응답하지 않는 로컬 소켓 서버에 `requests.get` → 상한을 1초로 줄여 감싸면 `ReadTimeout` · 1.01초 · 블록을 나오면 원래 함수로 돌아온다.
  - FDR 의 `requests.get(url)` 도 같은 경로(`Session.request`)라 이 함수로 상한이 걸린다.
- `requests` 를 바꿔 끼우는 곳은 저장소에서 이 함수뿐이다(`grep 'Session.request ='`).
  - PC 서버 안에서는 VIX 단계만 쓴다. 전체 갱신과 'VIX 다시 받기'는 같은 잠금이라 동시에 돌지 않는다.
- 갱신 뒤 단계(장중 설정 재계산 · VIX 다시 받기 표식)에는 외부 호출이 없다. KOSPI 는 날짜 몇 개를 차례로 받지만 요청마다 40초 상한이 있다.

### 1-4. 실제 소요 시간 (`market_refresh_log` · 읽기 전용 실측 · 최근 8회)
- ETF 목록 0.3 ~ 1.6초 · ETF 가격 1,174 ~ 1,192종목 80.6 ~ 362.6초(종목당 평균 0.07 ~ 0.31초) · 보유 개별주 3종목 1.4 ~ 1.8초 · 실패 0.
- 마지막 갱신 2026-10-14 전체 300.8초 · 완료.

## 2. 최소 변경안

1. **조회마다 대기 상한 20초** — `market_refresh_service.py` 에서 ETF 목록 · 가격 단계와 보유 개별주 단계를 기존 `fdr_request_timeout()` 으로 감싼다(약 +6줄).
   - 근거: 목록 최대 1.6초 대비 약 12.5배. 종목당 평균(0.07 ~ 0.31초)은 개별 요청의 최대값이 아니다(판정 §3 정정 · 처음 '60배 이상'). OCI · VIX 와 같은 값 · 같은 원천(네이버).
   - 20초는 연결 · 읽기 대기 설정이다. 종목 하나나 작업 전체가 20초 안에 끝난다는 뜻이 아니다(판정 §3).
   - 멈춘 요청은 20초 뒤 예외가 되어 **그 종목만 실패**로 세고 다음 종목으로 간다(기존 종목별 예외 처리 그대로).
   - 작업이 끝까지 가므로 마지막 상태 기록에서 `running` 이 풀린다. 잠금을 따로 지우는 코드는 필요 없다.
2. **원천 전체가 응답하지 않을 때 일찍 끝내기**(§4 Q1) — 공유 함수 `market_data_fdr.refresh_price_history` 에 선택 인자 하나.
   - **연속 5종목이 시간 초과**면 남은 종목은 시작하지 않고 실패로 센다(기본값 없음 → OCI 배치 동작 그대로).
   - 요청 하나가 종목마다 약 20초에 끝난다는 단순 가정의 계산 예: 없으면 1,190종목 × 20초 ≈ 6.6시간, 있으면 약 100초. 최대 시간이나 종료 보장이 아니고 다른 단계 시간도 뺀 값이다(판정 §3).
   - 이 경우 갱신 결과는 **`failed`**(대기 시간 시작 안 함 → 바로 다시 누를 수 있음)이고, 짧은 한국어 사유를 남긴다.
     - 문구(판정 §5): '가격 조회가 연속으로 시간 초과되어 남은 N종목은 받지 않았습니다. 앞서 받은 자료는 보존했습니다. 갱신 작업 종료 후 다시 실행할 수 있습니다.'
3. 화면 · API · DB 표 · 다른 단계(KOSPI · VIX · NAV) · OCI 배치 함수 · 서버 재시작 정리는 바꾸지 않는다.
   - 화면은 지금처럼 `error_summary` 를 '갱신 실패: …' · '확인 필요: …' 줄에 그대로 보인다.
   - `market_refresh_service.py` 는 576줄이다. 판단은 `market_data_fdr.py`(300줄)에 두고, 서비스 파일에는 감싸는 줄만 더한다(600줄 미만 유지).

## 3. 자료 보존 · 실패 표시 · 다시 실행

| 경우 | 받은 자료 | 결과 · 화면 | 다시 누르기 |
|---|---|---|---|
| 한두 종목만 시간 초과 | 받은 종목은 받는 즉시 저장(`upsert`) · 실패 종목은 예전 값 그대로 | `completed` · '확인 필요: price_partial_failure: fail=N'(기존) | 기존 6시간 대기(성공 갱신 뒤 규칙 그대로) |
| 연속 5종목 시간 초과(원천 멈춤) | 위와 같음 · 남은 종목 시작 안 함 | `failed` · 한국어 사유 한 줄 | **바로 가능**(실패는 대기 시간 시작 안 함) |
| ETF 목록 시간 초과 | ETF 목록 · 가격 그대로(목록 실패면 가격 단계 생략 · 기존) | `failed` · 'universe_fetch_failed: …Timeout'(기존) | 바로 가능 |
| 보유 개별주 시간 초과 | 받은 종목 저장 | ETF 결과대로 · '보유 개별주 가격 갱신 일부 실패(N종목)'(기존 문구) | ETF 결과대로 |

- 기록: ETF 가격 기록 행(`FinanceDataReader/prices`)에 시도 · 성공 · 실패(시작 안 한 종목 포함)와 사유가 남는다. 지금은 멈추면 이 행이 아예 안 남는다.
- 서버 재시작 때 `running → failed` 정리(`:172`)는 마지막 안전장치로 그대로 둔다.

## 4. 질문 (설계자 판단 · 권장은 (a))

### Q1. 원천 전체가 응답하지 않을 때 일찍 끝내기
- (a) **권장** — §2-2 대로 연속 5종목 시간 초과면 남은 종목을 멈추고 `failed`(바로 다시 누를 수 있음).
  - 정상 갱신에는 영향이 없다(실측 8회 실패 0 · 시간 초과 0). 작업 전체 시간 상한이나 강제 종료가 아니다.
- (b) 조회마다 20초만 둔다. 원천 전체가 멈추면 단순 가정 계산으로 약 6.6시간 동안 `running` 이다(그동안 다시 누를 수 없음).

### Q2. 일부 종목만 실패한 '완료'의 다시 누르기
- (a) **권장** — 기존 규칙 그대로. 완료면 6시간 대기, 받은 종목은 최신 · 실패 종목은 예전 값이다.
- (b) 시간 초과가 하나라도 있으면 바로 다시 누를 수 있게 한다. 성공 판정 규칙을 바꾸는 일이라 이번 범위 밖으로 본다.

### Q3. PC 수동 스크립트(`scripts/refresh_market_timeseries.py`)
- (a) **권장** — 이번 범위에서 뺀다.
  - 터미널에서 직접 돌리는 별도 도구라 Ctrl+C 로 멈출 수 있다. 다음 실행 때 남은 `running` 을 스스로 정리한다(`:218`).
  - 버튼 갱신의 잠금과도 무관하다.
- (b) 같은 대기 상한을 넣는다.

## 5. 시험 · 확인 (라이브 DB · 외부 조회 0 · tmp DB)
- 공유 함수: 시간 초과 예외를 내는 가짜 fetcher.
  - 연속 5번이면 멈춤 · 남은 종목 미호출 · 건수 · 사유를 확인한다.
  - 연속이 아니면 끝까지 간다. 인자를 주지 않으면 지금과 같다(OCI 경로).
- 대기 상한이 실제로 걸리는지: 연결만 받고 응답하지 않는 로컬 소켓 서버를 띄운다. 단계 안에서 `requests` 로 부르는 가짜 fetcher 가 (시험용으로 줄인) 상한 뒤 실패로 집계되고 작업이 끝나는지 확인한다.
- 서비스 · 보유 개별주 단계도 감싸졌는지 확인하고, 끝난 뒤 `requests` 원래 함수로 되돌아오는지 확인한다.
- 멈춤 보호 뒤 상태가 `failed` · `running` 아님인지, 그리고 바로 다시 누르면 `accepted` 인지 확인한다.
- 일부 실패면 `completed` + 기존 대기 시간 그대로인지 확인한다.
- 기존 시험(`test_market_data_fdr.py` · `test_market_topn_api.py` · `test_holdings_equity_refresh.py` · `test_pc_vix_refresh.py` · `test_market_vix_retry.py` · OPS-03 배치 시험)은 그대로 통과해야 한다.
- 변이 몇 개: 상한 미적용 · 보유 개별주 미감쌈 · 연속 판정 초기화 누락 · 멈춤 뒤 completed 판정.
- 검사: black · flake8 · py_compile · 관련 pytest · 전체 pytest 1회. 화면 변경은 없다.

## 6. 알려진 한계(지금 판단)
- `requests` 의 대기 상한은 연결 · 읽기마다 걸린다. 주소 찾기(DNS)가 멈추거나 아주 느리게 조금씩 오는 응답은 다 막지 못한다. 서버 재시작 정리가 마지막 수단으로 남는다.
- `fdr_request_timeout` 은 감싼 동안 같은 서버 안 다른 요청 중 timeout 없는 것에도 20초를 넣는다. OCI · VIX 와 같은 방식이고 늘어나는 쪽이 아니라 막히지 않게 하는 쪽이다.

## 7. 설계자 PLAN 판정 반영 (2026-10-16 · PASS)
- 판정 원문: `docs/ai_design/POC5/POC5-17_PC_MARKET_REFRESH_STALL_PROTECTION_PLAN_DECISION_2026-10-16.md`. Q1 · Q2 · Q3 모두 (a). PLAN 재제출은 필요 없다.
- **20초의 뜻(판정 §3)**: 연결 · 읽기 대기 설정이다. 여러 주소 연결 · DNS 대기 · 조금씩 오는 응답은 남는 한계다.
  - 100초 · 6.6시간은 단순 가정의 계산 예로만 적는다. '60배 이상'은 '목록 최대 1.6초 대비 약 12.5배'로 정정했다(§2-1).
  - 종료 때 `DEF-FDR-TIMEOUT` 은 'PC 버튼 경로에 요청 timeout · 연속 timeout 중단 적용 · DNS · 느린 연속 응답에 대한 전체 종료 보장 없음'으로 범위를 적는다. 모든 경로가 해소됐다고 기록하지 않는다.
- **연속 5종목(판정 §4)**
  - 단위는 조회한 ETF 종목의 결과다. `requests` Timeout 계열 · 내장 `TimeoutError` · 본문 읽기 중 시간 초과(`requests` 가 `ConnectionError(urllib3 ReadTimeoutError)` 로 올림 · 구현 중 로컬 실측)만 센다. 예외 종류로 판단하고 메시지 문자열로 판단하지 않는다.
  - 시간 초과 아닌 결과(성공 · 빈 자료 · HTTP 오류 · 연결 거부 · 파싱 오류 · 저장 실패)가 끼면 0으로 되돌린다. 다섯 번째 시간 초과를 처리한 뒤 남은 종목은 조회하지 않는다.
  - PC 가 인자를 넘길 때만 켠다. 인자 없는 공유 함수 · OCI 배치는 그대로다.
  - 뒤 단계(보유 개별주 · KOSPI · VIX · NAV)는 기존 흐름대로 돈다. 그래도 이 회차는 `failed` 로 남고, 작업이 실제로 끝난 뒤 마지막 기록에서 `running` 이 풀린다.
- **기록(판정 §5)**: 조회하지 않은 종목을 시도 · 시간 초과로 세지 않는다.
  - 기존 기록 행의 뜻(시도 = 대상 · 실패 = 대상 − 성공)은 그대로 두고, 사유 앞에 `stopped_after_consecutive_timeouts=5 queried=Q not_started=N` 을 적는다.
  - 화면 사유는 판정 문장 그대로다(저장 수 숫자는 넣지 않음).
- **보호 범위(판정 §6)**: `Session.request` 바꿔 끼우기가 프로세스 공통인 점은 한계로 적는다. 감싸는 범위는 PC FDR 단계 블록(ETF 목록 · 가격 · 보유 개별주)만이다. 공유 보호 함수 · 다른 호출부는 고치지 않는다.
