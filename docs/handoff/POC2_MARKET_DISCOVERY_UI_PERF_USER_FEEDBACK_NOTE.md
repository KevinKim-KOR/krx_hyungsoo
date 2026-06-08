# POC2 — Market Discovery UI / Perf 사용자 즉시 피드백 NOTE

작성: 2026-06-08
성격: **검증자 전달용 짧은 보고**. 사용자 즉시 피드백 5건이 연속 commit 으로
반영되어 별도 STEP Conclusion 을 만들지 않았다. 본 문서는 검증자가 "파일 폭주
/ 책임 누적 / KS-10 진입" 여부를 빠르게 확인할 수 있도록 정리한 단일 페이지.

---

## 1. 사용자 피드백 → commit 매핑 (5 건)

| commit | hash | 사용자 피드백 요지 |
| --- | --- | --- |
| 1 | `6c3728ec` | UI 정리 + 6개월/12개월/1년/3년 수익률 컬럼 추가 (티커/ETF명 합치기는 사용자 의도 오인 — 라운드 2 에서 정정) |
| 2 | `3c066b48` | UI 정리 라운드 2 — 티커/ETF명 원복, asof 컬럼 제거, AI Sessions/ETF Exposure/CopyText 섹션 삭제, MarketContextCard 헤더 `(069500) KODEX 200` / `(KS11) KOSPI` 표기 |
| 3 | `1f8d455a` | AI Sessions / ETF Exposure 버튼을 화면 맨 아래 → 갱신 버튼 바로 아래로 이동 |
| 4 | `15b0ba4b` | 두 버튼이 별도 카드로 떨어져 있던 것을 TopControlsRow 카드 안 2행으로 통합. 현재가/MA20/MA60 천단위 콤마 (`119,560`) |
| 5 | `8fad2bb4` | "조회가 느린 것 같다" — `/market/topn/latest` 응답 2.4s → 0.85s 단축 |

별도 Step 으로 분류하지 않은 이유: 모두 직전 STEP(NAV Display FIX) 직후 사용자
가 보낸 즉시 피드백이라 한 흐름으로 묶여 있고, 신규 기능 / 신규 API / 외부 source
변경은 0건. 책임은 "직전 STEP UI 마무리 + 응답 perf 회복".

---

## 2. 파일 폭주 / KS-10 체크 (검증자 핵심 관심사)

### 2.1 변경 파일 라인 수 실측 (HEAD 시점)

| 파일 | 라인 | KS-10 임계 | 분류 |
| --- | --- | --- | --- |
| `app/api_market_topn.py` | 538 | 600 (near) / 650 (trigger) | 안전 |
| `app/etf_nav_store.py` | 224 | 600 / 650 | 안전 |
| `app/market_data_store.py` | 360 | 600 / 650 | 안전 |
| `app/market_topn.py` | **613** | 600 / 650 | **near (≥600)** ⚠ |
| `frontend/app/components/CandidateTable.tsx` | 236 | 850 / 900 | 안전 |
| `frontend/app/components/MarketContextCard.tsx` | 131 | 850 / 900 | 안전 |
| `frontend/app/components/MarketDiscoveryView.tsx` | 691 | 850 / 900 | 안전 |
| `frontend/app/components/TransferToAISessionsCard.tsx` | 206 | 850 / 900 | 안전 |
| `frontend/app/components/TransferToETFExposureCard.tsx` | 85 | 850 / 900 | 안전 |
| `frontend/lib/api/market.ts` | 235 | 850 / 900 | 안전 |

### 2.2 KS-10 near 진입 1건 — `app/market_topn.py` 613 라인

- **진입 사유 / 변화량**: 직전 측정(NAV Display FIX 시점) 590 → 본 라운드 613.
  +23 라인은 **commit 1 (`6c3728ec`)** 의 `SIX_MONTH_LOOKBACK_DAYS` /
  `TWELVE_MONTH_LOOKBACK_DAYS` / `THREE_YEAR_LOOKBACK_DAYS` 상수 추가 +
  `period_specs` 확장 + `_empty_exclusion_buckets` / `_empty_filter_exclusion_buckets`
  의 신규 기간 키 동기화.
- **perf commit (`8fad2bb4`) 의 영향**: market_topn.py 에는 net +0 — `_name_of`
  fallback 분기만 4 라인 미만 변경.
- **trigger 여유**: 650 라인까지 37 라인 여유. 추가 책임 누적 없으면 안정.
- **사후 조치 제안**: 신규 기간 처리 부분(period_specs / exclusion dict 동기화)을
  별도 helper 모듈로 분리하면 빠르게 580 라인대로 복귀 가능. **본 라운드에서는
  실행하지 않음** (사용자 피드백 처리 + perf 우선, 분리는 별도 STEP).

### 2.3 책임 누적 / KS-10 §1.5 점검

KS-10 §1.5: "한 Step 에서 같은 대형 파일에 신규 책임 추가됨".

- `market_topn.py` 의 본 라운드 변경: (a) 기간 상수 + dict 동기화 (commit 1 만),
  (b) name bulk prefetch (commit 5, +4 라인). 본질은 기존 책임 보강이며 새 도메인
  책임 신설 X. **§1.5 발동 안 함.**
- `MarketDiscoveryView.tsx` 691 라인: 본 라운드에서 +56 / -115 (net -59).
  TopControlsRow 신규 컴포넌트가 본 파일 내부에 정의되어 +라인 발생했지만 전체
  적으로 감소. near 진입과 무관.

### 2.4 다른 대형 파일 영향 (참조)

본 라운드와 무관한 750+ 라인 기존 파일 — 참고만:

- `scripts/diagnose_nav_discount_source.py` 984 라인 (NAV 진단 1차 STEP 산출물,
  scripts/ — KS-10 trigger 대상 모듈 아님. 운영 코드 아님)
- `tests/test_holdings_message_text.py` 903 라인 (테스트 임계 1500/1450 미달)

---

## 3. perf commit 상세 (`8fad2bb4`)

### 3.1 측정 방법

`fastapi.testclient.TestClient` warmup 1회 후 3회 측정.

```
[before]
[1] 2483 ms  status=200  candidates=10  universe=1137
[2] 2298 ms  status=200
[3] 2167 ms  status=200

[after]
[1] 831 ms  status=200
[2] 842 ms  status=200
[3] 903 ms  status=200
```

### 3.2 원인 (cProfile)

| 함수 | 호출 횟수 | tottime |
| --- | --- | --- |
| `_connection` | 4596 | (cumulative 4.07s) |
| `init_db` (via `_connection`) | 2298 | (`CREATE TABLE IF NOT EXISTS × 3` 반복) |
| `fetch_price_history` | 1159 | 0.81s |
| `get_etf_name` | 1137 | 0.64s |

→ 한 요청당 SQLite `connect()` 가 4600 회 발생, 각 connection 마다 init_db 중복.

### 3.3 수정 내용

1. **`app/market_data_store.py`**: `_INITIALIZED_DBS: set[str]` process-level 캐시 +
   `_ensure_initialized()` 추가. `_connection` 이 같은 `db_path` 에 대해서는 init 1회만.
2. **`app/etf_nav_store.py`**: 동일 패턴 (`_INITIALIZED_NAV_DBS`).
3. **`app/market_data_store.py`**: `get_etf_name_map()` 신규 — `etf_master` 전체를
   1 쿼리로 ticker→name dict 반환.
4. **`app/market_topn.py`**: `compute_topn` 의 `name_cache` 를 universe-wide
   prefetch 로 교체 (1137 SQL → 1 SQL). master 미등록 ticker 는 단건 fallback 유지.

### 3.4 회귀 안전성

- **테스트 격리**: `_INITIALIZED_DBS` 는 `db_path.resolve()` 절대경로 key. pytest
  의 `tmp_path` 가 fixture 마다 다른 절대경로를 부여하므로 테스트 간 init 상태
  공유되지 않음 (각 tmp DB 가 첫 호출 시 자신만의 init 진행).
- **동시성**: SQLite connection 은 매 호출마다 새로 열고 닫음. `init_db()` 는
  `CREATE TABLE IF NOT EXISTS` 이므로 동일 path 에 race condition 발생 시 중복
  init 도 idempotent. set add 는 atomic.
- **fallback 보존**: name bulk prefetch 가 누락한 ticker (master 미등록) 는
  단건 `get_etf_name` 으로 fallback — silent skip 0건.

---

## 4. UI 정리 commit (`6c3728ec` ~ `15b0ba4b`) 검증 포인트

### 4.1 backend 모델 확장 — net 신규 책임 검증

`MarketReturns` Pydantic 모델 / `period_specs` / exclusion dict 에 `six_month`,
`twelve_month`, `three_year` 3 종 추가.

- **응답 계약 변경 여부**: 기존 필드 의미 / 정렬 가능 basis (`daily` / `one_month` /
  `three_month`) 변경 0건. 신규 필드는 Optional — 기존 클라이언트는 미인지하므로
  비호환 없음.
- **시계열 미적재 ETF**: 신규 기간 lookback (180/365/1095) 이상 시계열이 없는
  ETF 는 자동으로 `None` 반환 + exclusions dict 의 missing 카운트로 분류. 무음
  fallback 아님.

### 4.2 frontend 컴포넌트 책임 분리 / compact 모드

`TransferToAISessionsCard` / `TransferToETFExposureCard` 에 `compact?: boolean`
prop 추가. true 일 때 카드 wrapper 없이 button 만 렌더, false (기본) 은 기존 카드
UI 유지. **기존 호출처 호환 보존** — 다른 화면에서 카드로 호출하는 경로 (ETF
Exposure 화면 → AI Sessions 전달) 동작 변경 없음.

### 4.3 KODEX 200 / KS11 표기

`MarketContextCard` 헤더 → `(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)`.
backend `MarketContext.primary_benchmark` 필드는 그대로 (`KODEX200` 문자열).
표시 측에서만 상수 매핑 (`069500`, `KS11`) — 사용자가 "ticker 와 ETF 명을 함께
표시" 요청한 의도를 반영.

`fmtMoney()` 신규 — `value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })`.
정수/실수 모두 천단위 콤마.

---

## 5. 검증 결과

- **pytest**: 395 passed (회귀 0). 테스트 총 시간이 165s → 66s 로 단축됨 —
  init_db 반복 제거 효과가 테스트에도 적용됨.
- **black --check**: PASS.
- **flake8**: PASS.
- **Next.js build**: PASS (warnings 0).
- **KS-10 trigger**: 0 건.
- **KS-10 near**: 1 건 (`app/market_topn.py` 613, +23 from 590, 본질은 기간
  상수 추가 — §1.5 미발동).

---

## 6. 검증자 확인 요청 항목

1. **`app/market_topn.py` 613 라인 near 진입**이 §1.5 미발동으로 분류된 근거(§2.3)
   에 동의하는지.
2. **`_INITIALIZED_DBS` 캐시 패턴**이 테스트 격리 + 동시성 측면에서 안전한지(§3.4).
3. **UI 컬럼 제거 (source / status / asof / 정렬기준 / 태그)** 가 표시 매트릭스
   (직전 STEP NAV Display FIX 의 4 화면 × 6 필드) 와 정합하는지 — Market Discovery
   그리드의 6 필드 중 asof/source/status 는 본 라운드에서 Data Status 화면(전체
   ETF 조회) 으로 이전된 형태. NAV/시장가/괴리율 3 필드는 그리드 컬럼에 유지.
4. **`MarketReturns` 신규 필드 3 종**이 기존 응답 계약을 깨지 않는지 (Optional + 신규
   클라이언트만 인지).

---

## 7. 본 라운드에서 의도적으로 하지 않은 것

- 별도 STEP Conclusion 파일 (사용자 피드백 처리 흐름 — 단일 note 로 통합).
- `MarketReturns` 신규 기간의 정렬 가능 basis 확장 (사용자 요청 없음, 명시 보존).
- `fetch_price_history` 의 bulk 화 — 1137 SQL → 1 SQL 이론적으로 가능하지만
  메모리 부담 + 변경 폭이 큼. 현재 0.85s 로 운영 체감 충분.
- `app/market_topn.py` 의 helper 분리 (near 진입 해소). 별도 STEP 으로 처리 권고.

---

## 8. 다음 분기 후보 (변동 없음)

§POC2_B_NEXT_ACTIONS §0-1 과 동일:

1. NAV / 괴리율 시계열 누적 활용.
2. 위험 감지 지표 시계열 적재 1차.
3. 구성종목 가격 시계열 source 진단.
4. MDD / Sharpe 계산 도입.

추가로 본 라운드에서 발견된 후속 후보:

5. `app/market_topn.py` near 600 해소 — period helper 분리.
6. `/market/topn/latest` 추가 perf — `fetch_price_history` bulk 화 (필요 시).
