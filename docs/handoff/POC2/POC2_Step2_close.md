# POC2 Step 2 종결 — holdings 시장데이터 enrichment (Naver 1차 소스)

작성일: 2026-04-28
작성자: 개발자(VSCode Claude)
상태: 구현 + 자동 검증 게이트 통과. 사용자 디바이스 [시세 갱신] → 카드 → 초안 → Telegram 수신 운영 E2E 는 다음 사용자 실행 시점에 자연 검증.
대상 독자: 다음 챕터(POC2-Step2A 또는 운영 안정화) 진입자

---

## 1. 단계 목적 (한 줄)

POC2 Step 1A 까지 만든 holdings 기반 draft 의 표시 계층에 **현재가 / 평가금액 / 평가손익 / 평가수익률 / 시장비중** 을 추가한다. 시세 소스는 **Naver 비공식 endpoint** 1차만 사용. 사용자 명시 액션에서만 외부 fetch 발생. holdings 파일·draft 계약·OCI 경로는 변경하지 않는다.

---

## 2. 사용자(설계자) 결정 사항 반영

| Q | 결정 | 적용 위치 |
|---|---|---|
| HTTP 클라이언트 | **httpx** (이미 설치됨, requests/urllib 미도입) | `app/market_naver.py` |
| Naver endpoint | **`https://m.stock.naver.com/api/stock/{ticker}/basic`** (실측 0013P0 / 0015B0 / 069500 모두 200) | `app/market_naver.py::NAVER_BASIC_URL` |
| 외부망 사전 차단 확인 | 없이 진행. 단일 종목 실패는 격리 후 [시세 미확인] 표시 | `app/market_naver.py::fetch_one` (FetchResult 캡슐화) |
| pykrx / yfinance fallback | **POC2 Step 2 한정 금지** — 별도 STEP `POC2-Step2A` 로 deferred | `docs/backlog/BACKLOG.md` |
| BeautifulSoup / desktop scraping / polling stream | 금지 | 도입 안 함 |
| 시세 fetch 트리거 | **`POST /market/refresh` 1곳 한정**. page load / polling / 새로고침 / draft 조회에서 절대 발생 안 함 | `app/api.py` |
| 누락 필드 표시 | `undefined / null / NaN` 절대 노출 금지. 키 자체 생략 + `[시세 미확인]` 텍스트 | `to_recommendation_dict` + `draft_message` + `RunPanel HoldingsCard` |
| draft_payload 메타 flag | `price_missing / calc_missing` 키는 draft_payload 에 포함 금지. 표시 계층은 키 존재 여부로 판단 | `holdings_enrich.to_recommendation_dict` |

---

## 3. 책임 분리 (Step 2 핵심)

```
[사용자]
  └─ [시세 갱신] 버튼 클릭 (명시 액션)
[로컬 FastAPI]
  ├─ POST /market/refresh
  │   └─ market_naver.fetch_many(tickers)  ← 외부 fetch 가 발생하는 유일한 경로
  │       └─ market_cache.upsert_many(quotes)
  ├─ GET /holdings/enriched          (캐시 조회만, fetch 트리거 없음)
  ├─ POST /runs/generate-from-holdings (캐시에 있으면 자동 enrich 주입)
  └─ GET /runs/{run_id}              (fetch 트리거 없음)

[화면/메시지]
  └─ holdings_enrich.to_recommendation_dict 가 draft_payload.recommendations 에
     시세/평가 키를 추가. 누락은 키 자체 생략. RunPanel HoldingsCard +
     draft_message 가 키 존재 여부로 [시세 미확인] 분기.
```

**핵심 규칙**:
- 외부 fetch = 사용자 명시 액션(POST /market/refresh) 에서만
- 캐시 = 메모리 + 디스크 이중 + 원자적 쓰기 + 디스크 병합 보장
- 메시지 텍스트 생성 책임 = 여전히 로컬 백엔드 (Step 1A 원칙 유지)

---

## 4. 추가된 draft_payload.recommendations 키 (Step 2)

기존 Step 1 의 8 키 (ticker / name / quantity / avg_buy_price / invested_amount / buy_weight_pct / action / reason) 그대로 유지하면서, 캐시에 시세가 있을 때만 다음 키가 **존재 시에만** 추가됨:

- `current_price`
- `price_asof`
- `price_source` (현재 단계에서는 항상 `"naver"`)
- `eval_amount`
- `pnl_amount` (음수 가능)
- `pnl_rate_pct` (음수 가능)
- `market_weight_pct`

draft_payload 에 `price_missing / calc_missing` 같은 메타 flag 는 절대 포함하지 않는다. 표시 계층은 `current_price` 키 존재 여부로 [시세 미확인] 을 판단한다.

`EnrichedHolding` dataclass 자체에는 `price_missing / calc_missing` 이 있지만 이는 **enrichment API 응답(`GET /holdings/enriched`) 전용**이다.

---

## 5. 계산 규칙 (Step 2)

```
invested_amount    = quantity × avg_buy_price                   (항상)
buy_weight_pct     = invested_amount / Σinvested × 100          (항상)

eval_amount        = quantity × current_price                   (3 값 모두 유효 양수일 때만)
pnl_amount         = eval_amount - invested_amount              (시세 있을 때만)
pnl_rate_pct       = pnl_amount / invested_amount × 100         (시세 있을 때만)
market_weight_pct  = eval_amount / Σeval × 100                  (해당 종목 + 합계 모두 양수일 때만)
```

미충족 시 해당 키는 응답에서 생략된다. 음수 / 0 / NaN 가격은 `_is_valid_price` 가 차단한다.

---

## 6. 메시지 형식 예시 (Step 2)

```
✅ POC2 holdings 승인 처리
run_id: run_20260428T090500_xxxxxxxx
title: 보유 종목 기반 초안 (2026-04-28)

holdings 항목 2건 기준 자동 생성. 이번 단계는 보유 현황 기반 초안이며 추천 판단(매수/매도 등)은 포함하지 않습니다.

보유 종목:
1. RISE 미국은행TOP10 (0013P0)
   - 수량: 5
   - 평균 매입단가: 10,050원
   - 매입금액: 50,250원
   - 매입비중: 47.6%
   - 현재가: 11,920원
   - 평가금액: 59,600원
   - 평가손익: 9,350원
   - 평가수익률: 18.61%
   - 시장비중: 37.07%
   - 판단: HOLD
   - 사유: 보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)
2. 0015B0
   - 수량: 5
   - 평균 매입단가: 11,063원
   - 매입금액: 55,315원
   - 매입비중: 52.4%
   - [시세 미확인]
   - 판단: HOLD
   - 사유: 보유 종목 현황 (이번 단계는 추천 판단 없이 HOLD 고정)
```

- 시세가 캐시에 없는 종목은 시세/평가 줄을 통째 생략 + `[시세 미확인]` 표기
- "실시간" 단어는 절대 사용하지 않음 (테스트로 차단)

---

## 7. 신규 / 변경 파일

**신규** (3건, staged):
- `app/market_cache.py` — 메모리 + JSON 캐시. 원자적 쓰기 / 디스크 병합 보장 / threading.Lock / 쓰기 실패 시 메모리 롤백
- `app/market_naver.py` — Naver basic endpoint httpx 어댑터. 종목별 5s timeout / FetchResult 캡슐화 / 단일 실패 격리
- `app/holdings_enrich.py` — holdings × market_cache 결합 + eval/pnl/market_weight 계산. 외부 fetch 절대 트리거 안 함

**수정** (9건):
- `app/api.py` — `POST /market/refresh`, `GET /holdings/enriched`. `POST /runs/generate-from-holdings` 가 캐시 자동 주입
- `app/draft.py` — `generate_draft_from_holdings(holdings, market_quotes=None)` 옵션 인자
- `app/draft_message.py` — 시세/평가/손익/시장비중 + `[시세 미확인]` 줄 추가 (키 존재 여부 기반)
- `frontend/lib/api.ts` — `refreshMarket / fetchEnrichedHoldings` + 타입
- `frontend/app/components/HoldingsClient.tsx` — [시세 갱신 (Naver)] 버튼 + EnrichedSection 카드 리스트
- `frontend/app/components/RunPanel.tsx` — HoldingsCard 가 Step 2 시세 필드 + `[시세 미확인]` 표시
- `tests/test_poc1_loop.py` — Step 2 단위 테스트 18건 추가 (총 49)
- `docs/backlog/BACKLOG.md` — POC2 Step 2 deferred 18건 + POC2-Step2A 별도 STEP 등록
- `.gitignore` — `state/market_cache/*.json`

---

## 8. 검증 게이트 통과 기록

```
.venv/Scripts/black.exe --check app/ tests/   → exit 0 (16 files unchanged)
.venv/Scripts/flake8.exe  app/ tests/         → exit 0
.venv/Scripts/python.exe -m pytest tests/ -q  → 49 passed
py_compile app/* tests/*                      → OK
cd frontend && npm run lint                   → exit 0
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run build → Compiled successfully (5.42 kB / 108 kB First Load JS)

Naver endpoint 실측:
  0013P0  → OK (RISE 미국은행TOP10, closePrice 11,920)
  0015B0  → OK (KoAct 미국..., closePrice 20,205)
  069500  → OK (KODEX 200, closePrice 100,240)
```

---

## 9. 알려진 한계 / 미완성

- **운영 E2E 미검증** — 사용자 디바이스에서 [시세 갱신] → 카드 → 초안 → Telegram 수신 흐름은 다음 사용자 실행 시점 자연 검증. UI 흐름의 자동화 브라우저 테스트는 없음 (BACKLOG)
- **fetch_many 직렬 호출** — 보유 종목 수에 비례 응답 지연. 동시성 / 배치 / rate limit 도입 없음 (BACKLOG)
- **TTL / 만료 정책 없음** — 사용자 [시세 갱신] 누르기 전까지 캐시값 재사용. stale 표시 위험 (BACKLOG)
- **해외 종목 미지원** — Naver 한국 endpoint 한정. 미국/홍콩 등 모두 [시세 미확인] (BACKLOG)
- **pykrx / yfinance fallback 없음** — Naver 차단 시 [시세 미확인] 으로 표시. POC2-Step2A 가 별도 STEP 으로 정의됨 (BACKLOG)
- **enrichment 시계열 미보존** — 매 generate 시점 즉석 결합. 일자별 비교 불가 (BACKLOG)

---

## 10. 다음 챕터 진입자에게

### 건드리지 말아야 할 것 (Step 2 까지 확정 계약)

- 5 state 모델 / 4필드 draft_payload / handoff 5필드 (run_id / asof / approved_at / draft_payload / message_text)
- 상태 전이 규칙 / terminal state 차단 / 422 입력 차단
- holdings 식별 규약 (recommendations 첫 항목에 quantity 또는 avg_buy_price)
- holdings 파일은 4 키(ticker / quantity / avg_buy_price / name) 그대로 유지. 시세 데이터 섞지 말 것
- 외부 fetch 는 `POST /market/refresh` 단 1곳에서만. 다른 모든 경로에서 fetch 트리거 금지
- draft_payload 메타 flag(`price_missing / calc_missing`) 절대 추가 금지. 표시 계층은 키 존재 여부로 판단
- action 은 'HOLD' 고정, score 도입 금지
- "실시간" 단어 사용 금지
- ASCII 정책 (`start.bat` / `stop.bat`)
- `.gitignore` `backup/` / `state/holdings/holdings_latest.json` / `state/market_cache/*.json` 룰

### 즉시 진행 가능한 후보

- **(A) 운영 E2E 자연 검증** — 사용자가 [시세 갱신] 클릭 → Telegram 새 형식 수신 확인 (다음 09:05 KST cron 또는 수동 실행)
- **(B) POC2-Step2A — pykrx EOD fallback 도입** (BACKLOG 트리거 충족 시)
- **(C) holdings 자동 import** (KIS API / CSV — BACKLOG)
- **(D) ML 연결** (backup/ 의 predictive_risk_classifier 와 holdings 결합 — BACKLOG)
- **(E) market_cache TTL / 시세 stale 경고** — Step 2 BACKLOG

---

## 11. 한 줄 당부

POC2 Step 2 의 책임 분리 원칙 — **외부 fetch 는 사용자 명시 액션에서만, 메시지 생성은 로컬 백엔드, OCI 는 발송만, draft_payload 는 도메인 키만** — 을 깨지 말고 위에 쌓아라. fallback 추가(POC2-Step2A) 시에는 1차/2차 우선순위 / 캐시 메타데이터 / 채택 조건을 BACKLOG 에서 먼저 정리할 것.
