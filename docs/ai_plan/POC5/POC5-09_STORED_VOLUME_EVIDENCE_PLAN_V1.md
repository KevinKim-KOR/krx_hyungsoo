# POC5-09 — 저장 거래량 확인 근거 개발 PLAN V1

작성 2026-10-13 · 작성자: 개발자(VSCode Claude) · 수신: 설계자(웹 GPT)

```text
STATUS        = PLAN 확정 — 설계자 CONDITIONAL_PASS(2026-10-13 · 설계서 §9) · Q-A 제안 순서 · Q-B 판정 문구 · Q-C (b) 날짜 정정을 같은 09 에 먼저 · 보충 = §7(재제출 없음)
DESIGN        = docs/ai_design/POC5/POC5-09_STORED_VOLUME_EVIDENCE_DESIGN_V1.md (V1 · 끝에 전달문 원문)
BASE_COMMIT   = c5613b6c
QUESTIONS     = 3 — Q-A 배수 사유 우선순위 · Q-B 두 안내 카드의 거래량 문구 · 배지 · Q-C 설계 외 발견(PC 개별주 가격 08-12 정지)의 처리(§6)
USER_APPROVAL = 0 — 새 의존성 · 파일 삭제 · DB 스키마 변경 없음
SCOPE         = backend 새 모듈 1 + 기존 API 두 곳에 선택 필드 · frontend 화면 2곳 + 공용 표시 1 · 두 안내 카드 문구 정정 · 시험 · 문서. 수집 · DB · 테이블 · PUSH · 원장 · OCI 변경 0
```

## 0. 요약

- 거래량 자료 = PC 시장 DB `etf_daily_price.volume` · 단위 **주(거래된 주식 수)** · 출처 `FinanceDataReader` · 2026-02-19 이후 행만 값이 있다(그 전 `NAVER_FDR` 행은 모두 비어 있음). 보유 29종목의 직전 20개 저장일은 모두 값이 있다(§1-1).
- 기존 비교 함수(`ml_feature_primitives.volume_ratio_20d`)는 설계 정의와 달라 재사용하지 않는다. 기준일을 평균에 넣고 0을 빼며 유효 2개 이상이면 계산하기 때문이다. 같은 정의의 계산 함수 하나를 새 모듈에 두고 두 API가 같이 쓴다(§2-1).
- 필드는 두 **API 라우트 함수 안에서만** 붙인다. 공유 builder(`build_holdings_market_evidence` · `compute_topn`)는 손대지 않는다. PUSH · 초안 · 런타임 근거 경로는 그 builder를 쓰므로 바뀌지 않는다. 두 엔드포인트는 PC 화면만 부른다. OCI 에는 API 서버가 돌지 않는다(2026-10-13 읽기 전용 확인 · §1-2).
- 조회 비용: 보유 29종목 전체 이력 조회가 실측 12~59ms이고 새 조회 경로는 없다(§1-3).
- **설계 외 발견(§1-5 · Q-C)**: PC 시장 DB의 보유 개별주 3종목(삼성전자 · SK하이닉스 · 삼성SDI) 가격 · 거래량이 **2026-08-12**에서 멈춰 있다.
  - 그런데 「확인 근거」 5일 · 20일 · KODEX200 대비와 「오늘의 투자 점검」 최대 3개에는 날짜 표시 없이 그 값이 쓰인다.
  - 지금 SK하이닉스가 08-12 기준 5일 -9.83%로 「오늘의 투자 점검」 최대 3개에 들어 있다.
  - 이번 범위 밖이라 고치지 않고 판정을 요청한다. 거래량 칸은 설계대로 기준일 08-12를 그대로 보인다.

## 1. 사실조사 (설계 §6 의 4항목)

### 1-1. 거래량 자료 · 단위 · 최근 날짜 · 조회 함수 · 기존 비교 함수 (§6-1)

PC DB `state/market/market_data.sqlite`(읽기 전용 `mode=ro` 조회 · 2026-10-13 00시대):

| 확인 | 실측 |
|---|---|
| 칸 | `etf_daily_price.volume INTEGER`(`app/market_data_store.py:38-50` · 기본키 `(ticker, date)`) |
| 적재 | `market_data_fdr.py:172 · 226` — FDR `Volume` 열. `POST /market/refresh` 가 `etf_master` 1,188종목만 받는다(`market_refresh_service.py:307 list_etf_tickers`). 시계열 적재(`market_timeseries_ingestion_service.py:288 · 432`)는 `volume=None` 으로 쓴다 |
| 출처별 | `FinanceDataReader` 165,932행(2026-02-19 ~ 10-08) · 비어 있음 0 · 0 값 962 / `NAVER_FDR` 1,251,396행(2014-04-09 ~ 2026-03-05) · **모두 비어 있음** |
| 단위 | **주(거래된 주식 수)** — FDR `Volume` 열. KODEX 200 2026-10-08 = 23,162,524 · 종가 105,650원. 같은 날 `etf_master.volume`(FDR ETF 목록)과도 같은 값이다. 천 주나 금액 단위라면 값의 규모가 맞지 않는다 |
| 최신 날짜 | 전체 최신 2026-10-08 · 마지막 PC 갱신 2026-10-10 19:00 KST(사용자 수동 · `market_refresh_log` 성공 1,188/1,188). 10-13 기준 다음 거래일인 10-12 자료는 아직 없다(사용자가 갱신하면 들어온다) |
| 보유 29종목 | 26종목 = 기준일 2026-10-08 · 직전 20개 저장일 모두 값 있음 · 0 값 없음 / 3종목(개별주 005930 · 000660 · 006400) = 기준일 **2026-08-12** · 직전 20개 모두 값 있음(§1-5) |
| 조회 함수 | `market_data_store.fetch_price_volume_history(ticker)` — `(date, close, volume)` 날짜 오름차순 · `close` 가 비었거나 0 이하인 행 제외. 「확인 근거」 5일 · 20일이 쓰는 `fetch_price_history` 와 **같은 행 조건**이라 '저장 가격 날짜'가 같다 → 재사용(새 SQL 0) |
| 기존 비교 함수 | `ml_feature_primitives.py:103 volume_ratio_20d` — 창에 **기준일 포함** · `v > 0` 만 유효(0 제외) · 유효 2개 이상이면 평균 · 기준일 0이면 None → 설계 §3 정의(기준일 제외 · 0 유효 · 20개 모두 유효)와 **다름 · 재사용 안 함**(ML 특징값용 그대로 둠) |

### 1-2. 두 API 필드 위치 · 화면 타입 · PUSH 영향 (§6-2)

| 엔드포인트 | 라우트(필드를 붙일 곳) | 그대로 두는 공유 builder · 그 호출자 |
|---|---|---|
| `GET /holdings/market-evidence/latest` | `app/api_holdings_market_evidence.py:171 get_holdings_market_evidence_latest`(221줄) — builder 결과 뒤에 종목별 1회 계산해 각 `HoldingEvidenceItem` 에 선택 필드 | `holdings_market_evidence.build_holdings_market_evidence`(616줄 · KS-10 근접) ← `draft.py:189`(GenerateDraft) · `api_decision_draft_preview.py:91` · `runtime_evidence/composer.py:24`(런타임 근거) |
| `GET /market/topn/latest` | `app/api_market_topn.py:64 get_market_topn_latest`(196줄) — 응답 최상위 선택 필드(KODEX200 한 종목) | `market_topn.compute_topn` · `market_context`(KospiHeadline 이 읽는 KODEX200 판정)는 그대로 |

- 화면 타입: `frontend/lib/api/holdings.ts:218 HoldingsMarketEvidenceItem` · `frontend/lib/api/market.ts:132 MarketTopNResponse` 에 선택 필드(`?: … | null`)를 더한다. 이전 서버 응답에 필드가 없어도 화면이 깨지지 않는다.
- 이 두 엔드포인트를 부르는 화면은 「확인 근거」 · 「오늘의 투자 점검」 · ETF 비교하기 · 요즘 잘 오르는 ETF 등이다. 선택 필드 하나만 늘고 기존 칸은 바뀌지 않는다.
- OCI: 2026-10-13 읽기 전용 확인 결과, OCI 에는 `uvicorn` 프로세스가 없고 crontab 에 `daily_ops.sh` 도 없다. `daily_ops.sh` 가 부르는 것은 `/api/…` 경로(ops · push · reco · order_plan 등)뿐이고 두 엔드포인트는 부르지 않는다. PUSH 경로는 builder · runner를 쓰므로 바뀌지 않는다 → **OCI 배포 · pull 불필요**.

### 1-3. 조회 소요 · 화면 배치 예 (§6-3)

- 조회: 보유 29종목(KODEX 200 포함)에 `fetch_price_volume_history` 와 같은 SQL 실행 시 **12 ~ 59ms**(읽기 전용 실측 2회 · 25,658행). 여러 계좌에 있는 같은 종목은 1회만 계산한다. 「오늘의 투자 점검」은 KODEX200 1종목이다.
- 실데이터 계산 예(2026-10-13 · 읽기 전용):
  - KODEX 200: 기준일 2026-10-08 · 거래량 23,162,524주 · 직전 20개 저장일(2026-09-07 ~ 10-07) 평균 23,710,207.85주 · 평균 대비 0.98배
  - SK하이닉스: 기준일 2026-08-12 · 4,204,301주 · 평균(07-14 ~ 08-11) 6,174,143.20주 · 0.68배

화면 배치 예 — 「확인 근거」 종목 상세(PriceChart 바로 아래 · NAV 위 · 넓으면 4칸 한 줄, 좁으면 2칸 두 줄):

```text
┌ KODEX 200 거래량 ─────────────────────────────────────────────────── ⓘ ┐
│ 기준일        거래량            직전 20개 저장일 평균      평균 대비 │
│ 2026-10-08    23,162,524주      23,710,207.85주            0.98배    │
│ 출처 FinanceDataReader · 비교 구간 2026-09-07 ~ 2026-10-07 · 유효 20/20 │
└──────────────────────────────────────────────────────────────────────┘
```

「오늘의 투자 점검」 KOSPI 카드 오른쪽 열 — 'KODEX200 기준선 대비 위치' 아래 같은 양식의 칸(좁은 열이라 2칸 × 2줄):

```text
KODEX200 거래량  ⓘ
  기준일 2026-10-08        거래량 23,162,524주
  직전 20개 저장일 평균    평균 대비
  23,710,207.85주          0.98배
  출처 FinanceDataReader · 비교 구간 2026-09-07 ~ 2026-10-07 · 유효 20/20
```

- ⓘ(마우스를 올리면 보이는 도움말): "기준일 거래량을 그 앞 20개 저장일 평균과 비교한 배수입니다. 거래가 많고 적음만 보여 주며, 오르내림의 원인이나 매매 신호가 아닙니다."
- KODEX200 칸의 ⓘ 끝에 한 문장을 더한다: "KODEX 200 ETF 한 종목의 거래량이며 코스피 시장 전체 거래량이 아닙니다." 'KOSPI 거래량' 같은 이름은 쓰지 않는다.
- 상태별 표시(표시만 · 값을 지어내지 않음):

| 경우 | 거래량 | 평균 | 평균 대비 |
|---|---|---|---|
| 정상 | 23,162,524주 | 23,710,207.85주 | 0.98배 |
| 앞 20개 중 유효 N < 20 | 값 | 자료 부족 (N/20) | 자료 부족 |
| 기준일 거래량 없음 | 자료 없음 | 계산 가능하면 값 | 자료 없음 |
| 평균 0 | 값 | 0.00주 | 계산 불가 |
| 가격 행 자체 없음 | 칸 전체 대신 '거래량 자료 없음' 한 줄 | | |

- 거래량은 정수에 천 단위 쉼표를 넣는다. 평균 · 배수는 소수 둘째 자리이고 표시할 때만 반올림한다(설계 §3).
- 확정 전 실제 폭 목업을 사용자에게 먼저 보인다(§5).

### 1-4. 시험 (§6-4) — §3 에 목록

### 1-5. 설계 외 발견 — PC 개별주 가격 정지 (Q-C · 고치지 않음)

| 확인(2026-10-13 · 읽기 전용) | 값 |
|---|---|
| PC `etf_daily_price` 005930 · 000660 · 006400 | 2026-03-30 ~ **2026-08-12** · 93행 · 그 뒤 없음 |
| 원인 | PC `POST /market/refresh` 는 `etf_master`(ETF 1,188)만 받는다. 개별주는 대상이 아니다(BACKLOG `DEF-PRICE-EQUITY-REFRESH` 2026-09-06 철회 기록에 '개발 환경 한계'로 적힌 것과 같다. OCI 배치는 보유를 합쳐 받으므로 운영 PUSH 는 정상) |
| 지금 PC 화면 영향 | 「확인 근거」 개별주 3종목의 5일 · 20일 · KODEX200 대비 = 08-12까지의 자료로 계산된다. KODEX200 쪽은 10-08까지의 자료라 기간이 어긋나고, 날짜 표시도 없다 |
| | SK하이닉스 5일 -9.83% · 20일 -21.38% · KODEX200 대비 -16.71%p 가 「오늘의 투자 점검」 '내가 가진 ETF' 최대 3개(`judgment_summary.top_holdings`)에 들어 있다. 보유 비중은 13.0% |

- 9월에는 '개발 환경 한계'로 결함 등록을 철회했다. 그러나 지금은 PC 「오늘의 투자 점검」 · 「확인 근거」가 사용자가 매일 보는 화면이라 판단을 요청한다(Q-C).
- 이번 거래량 칸은 이 3종목에 기준일 2026-08-12를 그대로 보인다. 오래된 날을 최신처럼 보이지 않는다(설계 §3 · §4).

## 2. 구현 계획

### 2-1. backend — 새 모듈 `app/stored_volume_evidence.py`(약 120줄 · 한 책임)

- `compute_stored_volume_evidence(rows)` — 순수 계산. `rows` = `(date, close, volume)` 날짜 오름차순(위 조회 함수 결과).
  - D = 마지막 행 날짜. 창 = D 바로 앞 행 **최대 20개**(그 종목의 저장 가격 날짜 · 달력 날짜 아님 · 21번째 이전으로 메우지 않음).
  - 유효 거래량 = `None` 아님 · 유한수 · 0 이상(0 유효 · 음수 무효).
  - 평균 = 창 20개가 **모두 유효할 때만** `math.fsum(…) / 20`. 아니면 `None` + `avg_status="insufficient"`.
  - 기준일 거래량이 무효면 `volume=None`.
  - 배수 = `volume / avg`(둘 다 있고 avg > 0). 사유 코드는 Q-A 순서.
- `build_stored_volume_evidence(ticker, *, db_path)` — `fetch_price_volume_history` 1회 + 위 계산. 새 SQL · 새 쓰기 0.
- 응답 모델 `StoredVolumeEvidence`(pydantic · 같은 모듈 — 두 API가 같이 쓴다):

```text
ticker            str
status            "ok" | "no_price_data"        # 가격 행 자체 없음이면 no_price_data · 나머지 null/0
asof_date         str | null                    # D
source            str | null                    # D 행의 source
volume            int | null                    # D 거래량(주) · 무효면 null
window_size       20
window_start_date str | null                    # 창 첫날(창이 20개보다 짧으면 실제 첫날)
window_end_date   str | null                    # D 바로 앞 저장일
window_date_count int                           # 창에 든 저장일 수 0~20
valid_count       int                           # 그중 유효 거래량 수 0~20
avg_prev20        float | null                  # valid_count == 20 일 때만
avg_status        "ok" | "insufficient"
ratio             float | null
ratio_status      "ok" | "volume_missing" | "avg_insufficient" | "avg_zero"
```

- `source` 는 `etf_daily_price` 와 같이 행마다 저장된다. 비교 구간 행의 source 가 D와 다를 수 있으므로 D 행 값만 보인다. 지금 실데이터는 창 전체가 `FinanceDataReader` 다.

### 2-2. backend — 두 라우트

- `api_holdings_market_evidence.py`
  - `HoldingEvidenceItem` 에 `stored_volume: Optional[StoredVolumeEvidence] = None`.
  - 라우트에서 `evidence["holdings"]` 의 서로 다른 ticker마다 1회 계산해 각 행 dict 에 넣은 뒤 모델로 만든다. builder 반환 dict 는 바꾸지 않고 사본에 붙인다.
- `api_market_topn.py` · `api_market_topn_models.py`
  - `MarketTopNResponse` 에 `kodex200_stored_volume: Optional[StoredVolumeEvidence] = None`.
  - 라우트에서 `market_regime.KODEX200_TICKER`("069500")로 1회 계산.
- 예외를 삼켜 다른 값으로 대신하지 않는다. 자료 없음은 위 상태 칸으로 나타낸다. DB 자체 오류는 기존 조회처럼 그대로 오류가 된다.

### 2-3. frontend

- 타입: 공용 `StoredVolumeEvidence` 를 `lib/api/market.ts` 에 두고 `holdings.ts` 가 가져다 쓴다. 두 응답에 선택 필드를 둔다.
- 공용 표시 `frontend/lib/storedVolume.ts`(문구 · 숫자 형식 · 상태별 표시) + `frontend/app/components/StoredVolumeBlock.tsx`(4칸 · `columns` 2 | 4 · 제목 · ⓘ · 설명 줄).
  - 같은 폭 칸: CSS grid `repeat(4, minmax(0, 1fr))`. 좁은 화면(≤ 640px)이나 `columns=2` 면 `repeat(2, …)` 로 2 × 2(3 + 1 배치 없음). 새 CSS 클래스 몇 줄은 `globals.css` 에 둔다.
- 「확인 근거」(`HoldingsRiskEvidenceSection.tsx` 409줄)
  - 선택 상세의 `PriceChart` 아래, `NavConstituentsDetail` 위에 `<StoredVolumeBlock title="{종목명} 거래량" columns={4}>`.
  - 값은 `selectedEvidence?.stored_volume`(같은 종목 여러 계좌 = 같은 값). 없으면 '거래량 자료 없음' 한 줄을 보이고 차트 · NAV · 정렬 · 안내는 그대로 둔다.
- 「오늘의 투자 점검」(`today/KospiHeadline.tsx` 151줄)
  - 'KODEX200 기준선 대비 위치' 블록 아래에 `tc-stat-block tc-divider` 양식으로 `<StoredVolumeBlock title="KODEX200 거래량" columns={2}>`.
  - 값 = `market.data.kodex200_stored_volume`. KOSPI 기준일 줄(맨 아래)은 그대로 두고, 거래량 칸은 자기 기준일 · 출처를 따로 보인다.
- 새 조회 · 버튼 · 메뉴 · 갱신 0.

### 2-4. 낡은 '거래량 자료 미저장' 문구 정정(설계 §5 · 카드 삭제 아님 · 문구는 Q-B)

| 위치 | 지금 | 제안 |
|---|---|---|
| `today/InDevelopmentSection.tsx:30-32`('개발 중인 판단 기능' · 이번 단계 미도입) | 거래량 흐름 · '거래량 자료 미저장 — 신규 수집 필요.' | 'ETF · KODEX200 저장 거래량(기준일 · 직전 20개 저장일 평균 대비)은 「확인 근거」 종목 상세와 위 KOSPI 카드에서 봅니다. KOSPI 지수 거래량은 저장하지 않으며, 거래량으로 흐름을 판단하는 기능은 아직 없습니다.' · 배지는 Q-B |
| `today/KospiDetailSection.tsx:22-24`('코스피 상세 지표' · ⓘ 사유) | 거래량 흐름 · '현재 거래량 자료를 저장하지 않아 …' | 이름 '코스피 지수 거래량'(Q-B) · 사유 'KOSPI 지수 거래량은 저장하지 않아 표시할 수 없습니다. 위 KOSPI 카드의 KODEX200 거래량은 ETF 한 종목의 거래량이며 코스피 전체 거래량이 아닙니다.' |
| 주석 `TodayInvestmentCheckView.tsx:13` · `today/KospiChart.tsx:7` | '거래량 = 개발 중' · '거래량은 미저장' | 지금 동작(KOSPI 지수 거래량 미저장 · KODEX200 거래량 = KospiHeadline 보조 칸)으로 고침 |

- 그 문구를 고정하는 기존 시험 `TodayInvestmentCheckView.test.tsx:266-277`(AC-13 · '거래량 흐름' 이름 · '거래량 자료를 저장하지 않아' 툴팁)은 확정 문구에 맞춰 단언만 바꾼다. 다른 항목(공격·방어 · SuperTrend 등) · 카드 구조는 바꾸지 않는다.

## 3. 검증 계획 (설계 §6-4 · §7 · 줄인 방식)

- backend `tests/test_stored_volume_evidence.py`(새 파일 · tmp DB만 · 라이브 DB 열지 않음)
  - 계산: 정상(150만 / 100만 = 1.5) · 기준일 제외(D 값이 아주 커도 평균 불변) · 창은 바로 앞 20개만(21번째 이전 값 무시 · 창 안 결측을 더 오래된 날로 메우지 않음) · 19개 → 자료 부족 N/20 · 창 안 None · 음수 · NaN → 무효 · 0 유효(기준일 0 → 배수 0 · 창에 0 포함 평균) · 평균 0 → `avg_zero` · 기준일 무효 → `volume_missing`(평균은 계산) · 가격 행 없음 → `no_price_data` · close 비어 있는 행은 날짜에서 빠짐(가격 날짜 기준) · 다른 종목 날짜는 창에 안 섞임
  - API(TestClient · tmp DB · 기존 `api_client` 격리 방식): market-evidence 각 항목 `stored_volume` · 같은 종목 여러 계좌 같은 값 · 기존 칸 값 그대로 · `build_holdings_market_evidence` 반환에 새 키 없음(PUSH · 초안 불변) / topn `kodex200_stored_volume` · 기존 `market_context` 등 그대로
- frontend(vitest)
  - `storedVolume` 형식: 천 단위 · 소수 둘째 자리 · 상태별 문구 4종 · N/20
  - 「확인 근거」: 고른 종목의 거래량 칸 · 종목명 제목 · 자료 없음일 때 차트 · NAV 그대로 · 재조회 0
  - KospiHeadline: 'KODEX200 거래량' 제목 · 'KOSPI 거래량' · '코스피 거래량' 문구 없음 · 자체 기준일 · 필드 없을 때 기존 칸 그대로
  - 두 카드 새 문구
- 검사: `black --check` · `flake8` · `py_compile`(바뀐 .py) · 관련 pytest + backend 전체 회귀 1회(백그라운드) · `npx tsc --noEmit` · `npm run lint` · `npx vitest run` · 변이 몇 개(기준일 포함 · 0 무효 처리 · 창 메우기 · 사유 순서). OCI 거래일 확인 · 라이브 전수 해시는 넣지 않는다(설계 §7).

## 4. 문서 · 배포

- 결과서 `docs/ai_result/POC5/POC5-09_STORED_VOLUME_EVIDENCE_RESULT.md`. PROGRAM_TRUTH(두 API 선택 필드 · 두 화면 · 두 카드 문구)를 고친다.
- BACKLOG · 통합지도 P-10(`docs/ai_design/POC3/POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md:102`) · STATE 에는 'ETF · KODEX200 저장 거래량 관찰 근거 제공분 해소'만 적는다. KOSPI 전체 거래량 · 종합 위험 구간 분류는 미완료로 남긴다.
- PC 화면은 파일 자동 다시 읽기로 반영된다(재기동 · OCI pull 불필요). 10-23 R0 와는 무관하다.

## 5. 사용자 확인 항목

1. frontend 구현 전 **실제 폭 목업**(두 위치 · 4칸 / 2 × 2 정렬)을 확인받는다.
2. 실화면: 「확인 근거」 종목 상세 거래량 칸(종목명 · 단위 주 · 기준일) · 「오늘의 투자 점검」 'KODEX200 거래량' · 두 카드 새 문구.
3. 시장 자료 최신화: PC 시장 DB 최신이 2026-10-08이다(10-12 자료 없음). 실화면 전에 사용자가 「요즘 잘 오르는 ETF」의 '최신 시장 데이터 갱신'을 누르면 10-12 기준으로 보인다. 누르지 않으면 기준일 10-08이 그대로 표시된다.

## 6. 설계자 질문

- **Q-A 배수 칸의 사유가 겹칠 때 표시 순서**
  - 예: 기준일 거래량도 없고 평균도 부족한 경우.
  - 제안: '자료 없음'(기준일 거래량 없음) → '자료 부족'(평균용 N < 20) → '계산 불가'(평균 0) 순서로 첫 사유 하나만 보인다. 평균 칸은 따로 자기 상태('자료 부족 (N/20)')를 보인다.
- **Q-B 두 안내 카드의 거래량 항목**
  - '개발 중인 판단 기능'의 배지를 지금처럼 '이번 단계 미도입'으로 둘지, 새 배지(예: '일부 제공')로 바꿀지.
  - '코스피 상세 지표'의 이름을 '코스피 지수 거래량'으로 바꿀지.
  - §2-4 문구 제안이 맞는지. 새 라벨은 정해 주시는 대로 쓴다.
- **Q-C PC 개별주 가격 08-12 정지(§1-5)** — 이번 POC5-09 범위에서는 거래량 칸에 기준일만 그대로 보이고 나머지는 고치지 않는다. 처리를 정해 주십시오.
  - (a) 지금대로 두고 BACKLOG에 PC 화면 영향만 다시 기록
  - (b) 별도 단계에서 「확인 근거」 · 「오늘의 투자 점검」에 가격 흐름 기준일 표시 · 기준일이 어긋난 종목 구분
  - (c) 별도 단계에서 PC 갱신 대상에 보유 개별주를 더하기(PC 수집 범위 변경)

## 7. 설계자 판정 반영 (2026-10-13 · CONDITIONAL_PASS · 원문 = 설계서 §9 · 재제출 없이 보충)

### 7-1. 순서

① 가격 날짜 정정(backend → 화면) → ② 거래량 → ③ 두 카드 문구(판정 §3 그대로). 화면 구현 전에 실제 날짜 · 자료 확인 사유가 든 실제 폭 목업을 사용자에게 확인받는다. backend 는 목업과 따로 먼저 진행한다.

### 7-2. 날짜 키 — 실제 계산 이력에서

- **읽기 함수(새 · 읽기만)**: `market_data_store.fetch_recent_price_rows(ticker, *, limit=21, db_path)`.
  - 반환: `(date, close, volume, source)` 최신순.
  - 행 조건은 `fetch_price_history` 와 같다(`close` 있음 · 0 초과).
  - 기존 `fetch_price_history` · `fetch_price_volume_history` 의 반환 계약은 그대로 둔다.
  - **거래량 source 는 이 읽기의 D 행 값**이다(판정 §5).
- **종목 날짜**: 기준일 = 최신 행 날짜. n일 시작일 = n번째 앞 행 날짜(n = 5 · 10 · 20). `short_term_momentum._window_start_date(series, n)` = `series[-(n+1)]` 과 같은 행이다.
- **PC 비교 기준일** = KODEX200(069500)에 같은 읽기를 한 기준일. 기존 단기 흐름 계산(`compute_short_term_momentum_batch`)의 KODEX200 비교 계열 마지막 날과 같다. 오늘 · 기대 거래일과는 비교하지 않는다(판정 §4-1).
- **판정**(builder 의 단기 흐름 status 가 ok 인 항목만):
  - 종목 기준일 ≠ PC 비교 기준일 → `date_mismatch`. 5 · 10 · 20일 변화와 KODEX200 대비 5 · 10 · 20 모두 null · status `unavailable`.
  - 기준일은 같으나 n일 시작일 ≠ KODEX200 의 n일 시작일 → `window_mismatch`. 그 n 의 KODEX200 대비만 null · status 는 `ok` 그대로라 자기 5일 값으로 최대 3개 후보에 남는다(판정 §9-4-3 '기준일에 맞는 유효 후보' · 독립 검토 반영 2026-10-13 — 처음 적은 `partial` 은 후보에서 설명 없이 빠지게 해 고침).
  - 그 밖 → `ok`(값 보존). builder 가 이미 `unavailable` 이면 그대로 둔다.
- 비운 KODEX200 대비 20일로 만든 메모('20거래일 KODEX200 대비 단기 흐름 차이 …%p.')도 사본에서 뺀다. 원래 값으로 만든 같은 문구 하나만 빼고 다른 메모는 그대로 둔다.

### 7-3. 변경 위치

- **새 모듈 `app/pc_price_basis.py`** — `apply_pc_price_basis(evidence, *, db_path)`. builder 결과의 깊은 사본에 다음을 붙인다.
  - 위 정규화
  - 항목별 `price_dates`
  - 최상위 `price_basis`
  - `judgment_summary.holdings` 재계산
- **PC 최대 3개 생성 위치**: 같은 함수 안. 정규화된 사본의 보유 목록을 기존 `market_summary_composer.summarize_holdings` 에 넘긴다.
  - 그 함수가 기존 `select_top_holdings`(status ok · 5일 값 있음 · 5일 오름차순 · 동점 종목코드 · 최대 3)를 부른다.
  - 날짜가 맞는 후보 안에서 다시 채우고, 자료 확인 필요 건수(`coverage`)도 같이 다시 센다.
  - builder 가 만든 `judgment_summary`(PUSH · 초안 · 런타임 근거가 쓰는 것)는 그대로 둔다.
- **후보 전달 위치**: `api_holdings_market_evidence.get_holdings_market_evidence_latest` 에서 builder 호출 직후 `apply_pc_price_basis` → 응답 모델.
- **응답 선택 필드**
  - 항목: `price_dates {end_date, start_date_5d, start_date_20d, comparison: ok | date_mismatch | window_mismatch | unavailable}`
  - 최상위: `price_basis {reference_date, reference_ticker, kodex200_start_date_5d, kodex200_start_date_20d, date_mismatch: [{ticker, name, end_date}]}`
- **「확인 근거」**
  - 정렬 줄 아래 한 줄: '가격 흐름 기준: PC 저장 가격 기준일 D(KODEX200) · KODEX200 20일 비교 기간 S ~ D'.
  - `date_mismatch` 행: 5일 · 20일 · KODEX200 대비 칸 '—' · '자료 확인 필요' 배지(기존 판정 · 값 없음) · 정렬 맨 뒤.
  - 상세 '자료 확인 안내' 맨 위
    - 날짜 불일치: '저장 가격 기준일: A / PC 비교 기준일: D — 기준일이 달라 현재 비교에 사용하지 않습니다.'
    - 기간 불일치: 'KODEX200 대비 20일: 종목 비교 기간 S1 ~ D / KODEX200 비교 기간 S2 ~ D — 기간이 달라 비교값을 비워 두었습니다.'
  - 상세 '가격 흐름 기준' 줄(모든 종목): '기준일 A · 5일 S5 ~ A · 20일 S20 ~ A'.
  - 보유 행 · 수량 · 평단 · 보유 시세 · NAV · 과거 가격 차트는 그대로 둔다.
- **「오늘의 투자 점검」**
  - 최대 3개 설명 줄 끝에 ' · PC 저장 가격 기준일 D'.
  - 제외 종목이 있으면 한 줄: '가격 기준일이 달라 이 비교에서 뺀 보유: 삼성전자 · SK하이닉스 · 삼성SDI(저장 가격 기준일 2026-08-12) — 자료 확인 필요'. 정상 · 안전 표현은 쓰지 않는다.
- **거래량**: D 가 PC 비교 기준일과 다르면 거래량 칸에 '과거 저장 자료 · PC 비교 기준일 D 와 다름'을 붙인다. 개별주를 ETF 로 재분류하지 않는다.
- 공유 builder · `select_top_holdings` 본문 · OCI PUSH · 원장 · 가격 DB · 보유 · 갱신 버튼 제한 변경 0.

### 7-4. 검증 보충(판정 §5)

- 날짜가 같은 정상 자료의 값 보존
- 종목 기준일 불일치 → 6값 null · status `unavailable`
- 기간 불일치 → 그 KODEX200 대비만 null · status `ok` 유지 · 최대 3개 후보 유지
- 비운 값의 메모 제거 · 다른 메모 유지
- 최대 3개 재선정: 오래된 종목을 뺀 뒤 다음 종목으로 채우고 기존 동점 규칙을 따른다 · 날짜 맞는 후보가 3개 미만이면 그 수만큼
- 자료 확인 필요 건수 재계산
- 보유 · 현재 시세 · NAV 보존
- 공유 경로 불변: builder 반환이 사본 처리 전후로 같다 · builder `judgment_summary` 불변
- 화면: '—' · 사유 문구(실제 날짜) · 제외 줄 · 정렬 맨 뒤 · 재조회 0

### 7-5. 이어서 — PC 보유 개별주 수집 대상 보완(판정 §6)

- 09 구현과 별도로 짧은 PLAN 을 준비한다.
  - 방향: PC 수동 갱신 가격 수집 대상 = ETF 목록 ∪ 현재 보유(중복 없음 · `etf_master` 등록 없음)
  - 마지막 저장일 이후 누락 구간까지 보완
  - 실패 시 오래된 값이 현재 비교에 다시 들어가지 않게 한다 — 7-2 날짜 판정이 계속 막는다
- `DEF-PRICE-EQUITY-REFRESH` 는 이번에 재개 기록만 한다. 날짜 정정만으로 닫지 않는다.


## 8. 설계자 검증 요청 보충 반영 (2026-10-13 · 원문 = 설계서 §10 · 재제출 없음)

- **§10-2-1 계산값과 날짜를 같은 입력에서**
  - 재현: builder 가 10-08 자료로 계산한 5일 -10% 에 그 뒤 읽은 10-09 날짜가 붙어 `ok` 로 나가는 것을 작은 fixture 로 확인했다(결함).
  - 정정: PC 사본(`app/pc_price_basis.py`)이 날짜를 얻는 **같은 읽기**(`fetch_recent_price_rows` · 종목 · KODEX200 각 21행)로 5 · 10 · 20일 변화 · KODEX200 대비를 다시 구한다. 산식은 builder 와 같은 `short_term_momentum._window_return_pct` 이고, 상태 규칙도 같다(21행 이상이면 ok).
  - builder 의 단기 흐름 메모 한 줄도 이 값에 맞는 줄로 바꾼다. 기준일 불일치는 줄을 지우고 사유는 `price_dates` 로 보인다.
  - 공유 builder · PUSH · 초안은 그대로다. 두 읽기 사이 자료가 같으면 응답 값 = builder 값임을 실제 GET 시험으로 확인한다.
- **§10-2-2 최대 3개 비중 · 손익 = 종목 합산**
  - `today/JudgmentQueueSection.tsx` 가 이미 받은 보유 조회(`GET /holdings/enriched`)를 「확인 근거」와 같은 `holdings_compare/helpers.ts :: aggregateHoldingsByTicker` 로 묶어 표시한다(비중 = 종목 평가 합 ÷ 전체 평가 합 · 손익 = (평가 합 − 매입 합) ÷ 매입 합).
  - 선정 · 순서 · 5일 · 20일 · KODEX200 대비는 backend 요약 그대로다. 보유 조회 전 · 실패면 비중 · 손익을 보이지 않는다(첫 계좌 값으로 대신하지 않음). 새 조회 · API 0.
- **검증자 r1 정정(2026-10-13)**: 판정 순서 = 기준일 비교 → 이력 길이 → 비교 기간(이력이 짧아도 기준일이 다르면 `date_mismatch`) · 상태 조합 10가지 시험.
- 시험: 같은 읽기 재현 · builder unavailable → 같은 읽기 ok · 응답 = builder(경합 없음) · 이익 / 손실 계좌 합산 두 화면 일치 · 보유 조회 실패. 변이는 바이트코드를 쓰지 않고 돌리고, 복원 뒤 수정 시각을 갱신한다.
