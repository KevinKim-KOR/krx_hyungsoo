# STATE_LATEST.md

최종 업데이트: 2026-06-01

---

## 0. 현재 상태 — 2026-05-31 ETF Constituents Naver Source Integration

```text
현재 단계: Naver Stock ETFComponent 를 1차 구성종목 source 로 채택
  — 직전 smoke test 결과 (HTTP 200 / JSON list / 3 ETF PASS) 반영
  — 2026-06-01 FIX 라운드: 검증자 A-1 (asof 불일치) / A-3 (인벤토리 정합성) NOTE 반영 완료
이전 단계: ETF Constituents Source Diagnosis 1차 (pykrx hold + 모바일 endpoint unusable)
다음 단계 후보 (사용자 결정 대기):
  - 운영 데이터 누적 후 fetcher 다변화 / fallback chain (BACKLOG)
  - Data Status 실 연결 (기존 BACKLOG)
```

### FIX 라운드 (검증자 A-1 / A-3 / B-6 NOTE 반영, 2026-06-01)

검증자 1차 결과 REJECTED — A-1 (end-to-end asof 불일치로 UI 0건) / A-3
(POC2_FEATURE_INVENTORY 내부 §2.10 vs §4 표기 불일치) / B-6 (end-to-end 회귀
테스트 누락) NOTE. 본 FIX 라운드는 코드 흐름 버그만 수정 (source 교체 X).

검증자 2차 결과 REJECTED — A-3 잔재 (같은 문서 §3.2 / §3.3 Context Bridge
가 "부분 가능" + "source unavailable / 빈 dict" 로 §2.10~12 와 충돌) / A-2
(`frontend/lib/api.ts` 라인수 925 보고 vs 실측 932). FIX2 라운드로 정정.

- **A-1 FIX — end-to-end asof 흐름**:
  - 원인: service 가 응답의 `effective_asof` (예: Naver `referenceDate` =
    2026-06-01) 로 저장하지만, 프론트엔드가 `draft.asof` (예: 2026-05-28) 로
    analysis 를 조회 → SQLite 매칭 0건 → UI `unavailable`.
  - 백엔드 API `/market/constituents/analysis` 의 `asof` 가 이미 Optional
    이고 omit 시 `latest_constituent_asof` MAX 사용하도록 본 STEP 1차에서
    구현되어 있음. **추가 백엔드 변경 X**.
  - 프론트 `fetchConstituentsAnalysis(tickers, asof?, top_k)` 시그니처 변경 —
    `asof` optional + null 시 query param omit.
  - `ETFExposureView.tsx` 마운트 시점 호출 → `asof = null` 전달.
  - `ConstituentsTab.tsx` 수집 직후 재호출 → `asof = null` 전달.
- **A-3 FIX — 인벤토리 내부 정합성**:
  - `docs/handoff/POC2_FEATURE_INVENTORY.md` 의 §2.10 (ETF Exposure) 은
    "사용 가능" 으로 갱신되었으나 §4 (사용 불가/테스트용 목록) 는 직전 STEP
    의 "사용 불가" 표기 잔재. → §6 변경 이력 절을 신규 추가하여 §2.10 /
    §2.11 / §2.12 / §2.6 이 권위 source 임을 명시 + §4 잔재 표기 무효 처리.
- **B-6 FIX — end-to-end 회귀 테스트 신규**:
  - `tests/test_etf_constituents_naver_integration.py` 에
    `test_end_to_end_refresh_then_analysis_without_asof` 추가 — 입력 asof
    (2026-05-28) ≠ effective_asof (2026-05-29) 시나리오 재현. 입력 asof 로
    조회하면 0건, asof omit 시 latest 사용해 1건. 본 회귀 보호.
- **검증**: pytest 328 passed (327 → 328, +1 신규 / 회귀 0) / black PASS /
  flake8 PASS / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0. `tests/test_etf_constituents_naver_integration.py`
  228 → 264 라인 (실측, 신규 테스트 1건 +36). 750+ 미달.

### FIX2 라운드 (검증자 A-3 잔재 / A-2 라인수 정정, 2026-06-01)

- **A-3 잔재 FIX — POC2_FEATURE_INVENTORY §3.2 / §3.3 갱신**:
  - §3.2 Market Discovery → ETF Exposure: "부분 가능" + "source unavailable
    이라 실제 분석 결과 0건" → **"사용 가능"** (2026-05-31 Naver 통합 +
    2026-06-01 asof 흐름 FIX 후). "한계" 행 제거.
  - §3.3 ETF Exposure → AI Sessions: "부분 가능" + "constituent/overlap
    snapshot 은 source 미확보로 빈 dict" → **"사용 가능"**. "한계" 행 제거.
  - §6 변경 이력에 2026-06-01 항목 추가.
- **A-2 FIX — 라인수 실측 재산정**: `frontend/lib/api.ts` 925 → 932 (실측).
  본 §0 의 750+ 보고 줄에 932 로 정정 + FIX 라운드에서 +7 (Optional asof
  처리 + URLSearchParams 분기) 명시.
- **검증 재실행**: pytest 328 passed / black PASS / flake8 PASS / frontend
  lint PASS / frontend build PASS.

### 본 STEP 요약

- **source 교체 (지시문 §4)**: 직전 STEP 의 진단 결과 (pykrx PDF hold + 기존
  모바일 endpoint 404) 이후 새 endpoint 검증 (smoke test 통과) 완료. 본 STEP
  에서 1차 source 로 채택.
  - `default_fetcher()` 가 `naver_stock_etf_component_fetcher` 반환 (1차).
  - service 의 `expected_source` = `NAVER_STOCK_SOURCE` 명시 cache 매칭.
  - pykrx fetcher 함수는 모듈에 남아있음 (향후 chained fallback BACKLOG).
- **신규 fetcher (지시문 §5~§6)**:
  - URL: `https://stock.naver.com/api/domestic/detail/{ticker}/ETFComponent?startIdx=0&pageSize=20`
  - 표준 브라우저 header (User-Agent / Accept / Accept-Language / Referer).
  - 응답 list[dict] 파싱 → 비중 내림차순 → top_k 잘라내기.
  - weight string → float 변환. 변환 불가 (`"-"` / None / 빈 문자열) item 은
    저장 제외 (지시문 §6.1 — 0 임의 대체 금지).
  - `referenceDate` → `FetchResult.effective_asof` 노출 → service 가 그 값으로
    저장 + cache key.
  - 국내 종목: `componentItemCode` → `constituent_ticker`.
  - 해외 종목 (componentItemCode=null): `componentReutersCode` / `componentIsinCode`
    별도 컬럼 보존 + `_build_constituent_key` 가 우선순위로 매칭 키 생성.
- **DB 스키마 확장 (지시문 §7)**: `etf_constituents` 테이블에 4 컬럼 신규.
  - `constituent_key` — 매칭 1차 키 (국내 ticker / 해외 reuters / ISIN / name).
  - `constituent_isin` / `constituent_reuters_code` / `market_type`.
  - `_migrate_add_naver_columns` 가 init 시 자동 ADD COLUMN — 직전 STEP DB
    호환.
- **매칭 보정 (지시문 §11.2)**: `analysis._match_key` 우선순위 확장 —
  `constituent_key` → ticker → reuters → ISIN → 정규화 name. 해외형 ETF 의
  중복률 분석이 가능해짐. 신규 테스트 `test_analysis_matches_overseas_via_reuters_code`
  로 검증.
- **K6 방어 정책 (지시문 §9) 유지**: hard cap 10 / cache-first / 0.5s delay /
  30s budget / partial / unavailable 모두 그대로. source 만 교체.
- **Frontend (지시문 §10)**: UI 대개편 없음.
  - `api.ts` 의 `TopHolding` 에 `constituent_isin` / `constituent_reuters_code`
    / `market_type` optional 추가.
  - `ConstituentsTab.tsx` 의 holdings 행이 ticker 없으면 reuters 또는 ISIN
    표시 (해외 종목 식별).
- **AI 문구 / AI Sessions snapshot (지시문 §12 / §13)**: 기존 흐름 그대로 동작.
  실 데이터 들어오면 자동 노출.
- **검증**: pytest 327 passed (315 → 327, +12 신규 / 회귀 0) / black PASS /
  flake8 PASS / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 백엔드 핵심 모듈 최대 `app/market_topn.py` 590 (기존, 본 STEP 미변경).
  - 신규 fetcher 추가로 `etf_constituents_fetcher.py` 161 → 388 (+227 신규
    함수). near 600 까지 212 라인 여유.
  - `app/etf_constituents_service.py` 326 / `etf_constituents_store.py` 282 /
    `etf_constituents_analysis.py` 279.
  - 신규 tests: `test_etf_constituents_naver_fetcher.py` 191 /
    `test_etf_constituents_naver_integration.py` 228.
  - 프론트 컴포넌트 최대 `MarketDiscoveryView.tsx` 705 (기존).
  - 750+ 보고: `tests/test_holdings_message_text.py` 924 (기존) /
    `frontend/lib/api.ts` 932 (920 → 932, 본 STEP +5 + 2026-06-01 FIX +7
    실측 재산정).

### 신규 / 수정 파일

신규:
- `tests/test_etf_constituents_naver_fetcher.py` (191) — Naver fetcher 단위
  테스트 8건 (HTTP 200/404 / parsing / weight 변환 / top_k / key 우선순위).
- `tests/test_etf_constituents_naver_integration.py` (228) — service + store
  + analysis 통합 4건 (effective_asof / 해외형 reuters / 매칭 / 마이그레이션).

수정:
- `app/etf_constituents_fetcher.py` — Naver fetcher 함수 + NAVER_STOCK_SOURCE
  상수 + FetchResult.effective_asof + FetchedConstituent 의 isin/reuters/
  market_type 필드 + helper 2개 + default_fetcher 교체.
- `app/etf_constituents_store.py` — DDL 4 컬럼 + ConstituentRow 4 필드 +
  자동 마이그레이션 + upsert/fetch SQL 갱신.
- `app/etf_constituents_service.py` — expected_source = NAVER_STOCK_SOURCE +
  effective_asof 우선 저장 + constituent_key 빌드 + 4 컬럼 전달.
- `app/etf_constituents_analysis.py` — _match_key 우선순위 확장 (5 단계) +
  빈 prefix-only 키 제외 + analysis 응답에 isin/reuters/market_type 노출.
- `app/api_etf_constituents.py` — TopHolding Pydantic 모델 확장.
- `frontend/lib/api.ts` — TopHolding interface 확장.
- `frontend/app/components/ConstituentsTab.tsx` — 표시 식별자 fallback
  (ticker → reuters → ISIN).
- `tests/test_etf_constituents_service.py` + `tests/test_etf_constituents_api.py`
  — source 상수 갱신 (PYKRX → NAVER).
- `docs/handoff/POC2_FEATURE_INVENTORY.md` — ETF Exposure / Refresh / Overlap
  3 기능을 사용 가능으로 전환 + AI 문구 부분 가능 → 사용 가능.
- `docs/handoff/STATE_LATEST.md` (본 §0).
- `docs/handoff/POC2_B_NEXT_ACTIONS.md` (최우선 작업 = Naver 통합 완료).
- `docs/backlog/BACKLOG.md` (ETF 구성종목 source 항목 update).

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §17)

- KRX Open API 즉시 전환 / 운용사별 크롤러 / 전체 universe 수집.
- ETF Exposure UI 대개편 / 운영 UI 전면 재설계.
- NAV / 괴리율 / 거래대금 / 변동성 / ML / 매수·매도 판단.
- 구성종목 임의 추정 / AI 보완 / source 불명 ok 처리.

---

## 0.1 직전 상태 — 2026-05-31 ETF Constituents Source Diagnosis 1차

```text
현재 단계: ETF Constituents Source Diagnosis 1차 (2026-05-31)
  — pykrx PDF no_data 원인 격리 + Naver Mobile API smoke test + 기능 인벤토리
이전 단계: ETF Constituents & Overlap 1차 (2026-05-27)
다음 단계 후보 (실측 기반 자동 선정):
  C. KRX Open API / Official Provider Source Design
  (pykrx + Naver 모두 unusable — 지시문 §21.C)
```

### 본 STEP 요약

- **방향 (지시문 §3)**: ETF 구성종목 수집 실패 원인을 단계적으로 격리하고
  Naver Mobile API 를 실전 후보 source 로 검증. **기능 대규모 재구현 X**.
- **진단 script 신규**: `scripts/diagnose_constituents_source.py` (455 라인).
  - pykrx PDF (3 ETF × 5 날짜 = 15 호출) — `069500` / `139260` / `411420`
    × `2026-05-27 / 05-26 / 05-15 / 04-30 / 03-31`.
  - Naver Mobile API (3 ETF × 1 호출 = 3 호출) —
    `m.stock.naver.com/api/etf/<ticker>/component`.
  - 결과 분류 → JSON artifact + Markdown 리포트 자동 생성.
- **실측 결과**:
  - **pykrx**: 15 호출 모두 `no_data` (예외 0건, df 0 rows). 함수는 호출되나
    KRX PDF 페이지가 비어있음. → **pykrx_operational_issue** 분류. **hold**.
  - **Naver Mobile API**: 3 ETF 모두 **HTTP 404**. URL 패턴이 더 이상 유효 X.
    → **unusable**.
  - **다음 단계 자동 선정**: **C. KRX Open API / Official Provider Source
    Design** (지시문 §21.C — 두 source 모두 unusable).
- **artifact**:
  - `state/market/constituents_source_diagnosis_latest.json` — 실측 raw data.
  - `docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md` — 사람이 읽는 리포트.
- **기능 인벤토리 신규**: `docs/handoff/POC2_FEATURE_INVENTORY.md` (지시문
  §11). 15개 기능 + 3 Context Bridge 모두 누락 없이 기록. ETF Exposure /
  Constituents Refresh / Overlap Analysis 3 기능은 **사용 불가 (테스트용)**
  로 정직 기록.
- **코드 변경 0** (지시문 §9): 기존 ETF Exposure / API / store / fetcher /
  analysis / Decision Evidence 흐름 모두 그대로. 진단 script 만 추가.
- **검증**: pytest 315 passed (변동 0) / black PASS / flake8 PASS / frontend
  lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0. `scripts/diagnose_constituents_source.py` 455
  라인 — `scripts/` 디렉토리이고 본 모듈은 단발성 진단이라 KS-10 컴포넌트
  기준 미해당. 750+ 미달.

### 신규 / 수정 파일

신규:
- `scripts/diagnose_constituents_source.py` (455) — 진단 script.
- `state/market/constituents_source_diagnosis_latest.json` — 실측 raw.
- `docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md` — 진단 리포트.
- `docs/handoff/POC2_FEATURE_INVENTORY.md` — 기능 인벤토리.

수정:
- `docs/handoff/STATE_LATEST.md` (본 §0).
- `docs/handoff/POC2_B_NEXT_ACTIONS.md` (다음 STEP 후보 C 확정).
- `docs/backlog/BACKLOG.md` (ETF 구성종목 source 후보 항목 보강).

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §14)

- KRX Open API 즉시 전환 / 운용사별 크롤러 구현.
- ETF Exposure UI 대개편 / 운영 UI 전면 재설계.
- 전체 ETF universe 구성종목 수집.
- 구성종목 추정 / AI 에게 물어서 보완 / source 불명 ok 처리.
- NAV / 괴리율 / 거래대금 / 변동성 / ML / 매수·매도 판단.

---

## 0.1 직전 상태 — 2026-05-27 ETF Constituents & Overlap 1차

```text
현재 단계: ETF Constituents & Overlap 1차 (2026-05-27)
  — pykrx PDF + K6 방어 (10개 cap / 0.5s delay / 30s budget) + 집중도 + 중복률
    + 반복 종목 + AI 문구 [구성종목/중복 노출] + AI Sessions snapshot 영속화
이전 단계: Market Regime & Benchmark Context 1차 (2026-05-27 동일자)
다음 단계 후보 (사용자 결정 대기):
  (a) 시장 국면 판정 고도화 (BACKLOG)
  (b) NAV / 괴리율 / 유동성
  (c) AI 투자세션 결과 기반 개선
```

### 본 STEP 요약

- **방향 (지시문 §1)**: "후보 ETF들이 정말 서로 다른 테마인가? 아니면 같은
  핵심 종목을 여러 ETF 가 반복해서 담고 있는가?" 에 답하기 위한 구성종목
  수집 + 중복률 분석 1차. 매수/매도 판단 X — 실제 노출 구조 확인 까지만.
- **K6 방어 정책 (지시문 §4)**: 외부 KRX 데이터 (pykrx PDF) 의존성 강화 가드.
  - 1회 최대 10개 ticker (rejected when exceeded).
  - 캐시 우선 — (etf_ticker, asof, source) 키 매치 시 외부 호출 안 함.
  - `force=true` 인 경우만 캐시 무시.
  - ticker 별 0.5s delay (첫 외부 호출 제외).
  - 전체 30s budget 초과 시 남은 ETF 는 `skipped_timeout`.
  - 부분 실패 격리 — ETF 단위 실패가 전체 실패로 번지지 않음 (`partial`).
  - source 불명 (`"unknown"` 또는 빈 문자열) 은 ok 처리 금지 — `unavailable`.
- **신규 테이블 2개** (`state/market/market_data.sqlite`):
  - `etf_constituents` (etf_ticker, asof, source, rank PK) — 상위 N 구성종목.
  - `etf_constituent_refresh_log` (etf_ticker, asof, created_at PK) — 수집 결과.
- **Backend 신규 모듈 4 + router**:
  - `app/etf_constituents_store.py` (219) — DDL + upsert/fetch + log + latest.
  - `app/etf_constituents_fetcher.py` (161) — pykrx PDF fetcher (DI 패턴, lazy
    import, source 라벨 명시).
  - `app/etf_constituents_service.py` (307) — refresh 흐름 (cache / cap /
    delay / budget / partial / unavailable).
  - `app/etf_constituents_analysis.py` (267) — pure function. 집중도 (top
    1/3/5/10) + 중복률 (common_count_top10 + weighted_overlap_pct =
    sum(min(left, right))) + repeated_core_holdings.
  - `app/api_etf_constituents.py` (210) — POST refresh + GET analysis.
    db_path 는 호출 시점 module attribute lookup (테스트 monkeypatch 친화).
  - `app/api.py` — `etf_constituents_router` include 1줄.
- **Decision Evidence 확장**:
  - `app/decision_evidence_store.py` — `constituent_snapshot_json` /
    `overlap_snapshot_json` 컬럼 추가 + `_migrate_add_constituent_overlap_snapshots`
    자동 마이그레이션 (ALTER TABLE ADD COLUMN 각각).
  - `app/api_decision_sessions.py` — payload + response 에 두 snapshot 필드.
- **좌측 메뉴**: `etf_exposure` 추가 — Dashboard / Market Discovery /
  **ETF Exposure** / AI Sessions / Holdings / Approval-Telegram / Data Status.
- **Frontend 신규 컴포넌트 4 + util**:
  - `frontend/lib/etfExposureDraft.ts` — sessionStorage Context Bridge
    (Market Discovery → ETF Exposure).
  - `frontend/app/components/ETFExposureView.tsx` (234) — 탭 컨테이너 +
    draft 처리 + 마운트 시 캐시 기반 analysis 자동 호출 + "AI Sessions 로
    넘기기" 카드 (구성종목/중복률 snapshot 포함 draft 생성).
  - `frontend/app/components/ConstituentsTab.tsx` (191) — 수집 버튼 +
    상위 holdings + 집중도 + status 배지.
  - `frontend/app/components/OverlapTab.tsx` (106) — 쌍별 중복률 + 반복
    핵심 종목.
  - `frontend/app/components/TransferToETFExposureCard.tsx` (61) — Market
    Discovery 에 추가될 전달 카드.
- **AI 문구 / AI Sessions 연계 (지시문 §10 / §11)**:
  - `frontend/lib/marketDiscoveryCopyText.ts` — `constituentsAnalysis`
    optional 인자 + [구성종목 / 중복 노출] 섹션 + 새 AI 요청 문구 (analysis
    있을 때만 "독립 테마 vs 반복 노출" 해석 요청).
  - `frontend/lib/aiSessionsDraft.ts` — `constituent_snapshot` /
    `overlap_snapshot` 필드 추가 (schema v3).
  - `frontend/app/components/AISessionsCreateTab.tsx` — POST payload 확장.
  - `frontend/app/components/AISessionsListTab.tsx` — 상세에 "구성종목 (저장
    시점)" / "중복률 (저장 시점)" 섹션.
- **fetcher 1차**: pykrx 1.0.51 의 `get_etf_portfolio_deposit_file` 함수
  존재 확인 (PROJECT_ORIGIN_INTENT §8 자산 활용). 실패 시 명시 `unavailable`
  반환 (지시문 §3 1순위 KRX 공식 데이터 경로).
- **검증**: pytest **312 passed** (286 → 312, +26 신규 / 회귀 0) /
  black PASS / flake8 PASS / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 1차 측정에서 `MarketDiscoveryView.tsx` 695 → 705 (+10, TransferToETFExposure
    추가). near 850 까지 145 라인 여유.
  - 백엔드 핵심 모듈 최대 `app/market_topn.py` 590 (기존, 본 STEP 미변경,
    near 600 까지 10 라인 여유) / `decision_evidence_store.py` 416 → 452 (+36).
  - 신규 backend: 219 / 161 / 307 / 267 / 210 — 모두 trigger/near 한참 미달.
  - 신규 tests: store 145 / service 232 / analysis 138 / api 142 — 모두 미달.
  - 신규 frontend: ETFExposureView 234 / ConstituentsTab 191 / OverlapTab
    106 / TransferToETFExposureCard 61 — 모두 미달.
  - 750 라인 이상 보고: `tests/test_holdings_message_text.py` 924 (기존) /
    `frontend/lib/api.ts` 920 (786 → 920, 본 STEP +134 — constituents/overlap
    타입 + 함수). `.ts` 라이브러리라 KS-10 컴포넌트 기준 미해당이지만 다음
    STEP 에서 분리 후보.

### 신규 / 수정 파일 (28 + 문서 3)

신규 (10):
- `app/etf_constituents_store.py` (219)
- `app/etf_constituents_fetcher.py` (161)
- `app/etf_constituents_service.py` (307)
- `app/etf_constituents_analysis.py` (267)
- `app/api_etf_constituents.py` (210)
- `tests/test_etf_constituents_store.py` (145)
- `tests/test_etf_constituents_service.py` (232)
- `tests/test_etf_constituents_analysis.py` (138)
- `tests/test_etf_constituents_api.py` (142)
- `frontend/lib/etfExposureDraft.ts` (136)
- `frontend/app/components/ETFExposureView.tsx` (234)
- `frontend/app/components/ConstituentsTab.tsx` (191)
- `frontend/app/components/OverlapTab.tsx` (106)
- `frontend/app/components/TransferToETFExposureCard.tsx` (61)

수정 (Backend): `app/api.py` / `app/decision_evidence_store.py` /
`app/api_decision_sessions.py` / `tests/test_decision_evidence_store.py` /
`tests/test_decision_sessions_api.py`.

수정 (Frontend): `frontend/lib/api.ts` / `frontend/lib/aiSessionsDraft.ts` /
`frontend/lib/marketDiscoveryCopyText.ts` / `frontend/app/components/LeftSidebar.tsx`
/ `MainPanel.tsx` / `MarketDiscoveryView.tsx` / `AISessionsCreateTab.tsx` /
`AISessionsListTab.tsx` / `globals.css`.

문서: `STATE_LATEST.md` (본 §0 신규) / `POC2_B_NEXT_ACTIONS.md` (최우선 작업
갱신) / `BACKLOG.md` (ETF 구성 종목 1차 PARTIAL + 추가 BACKLOG).

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §14)

- 전체 ETF universe 구성종목 수집 / 서버 draft 저장소.
- NAV / 괴리율 / 거래대금 / 순자산 / 설정좌수 / 변동성 / 베타 / 환율 효과.
- ML 점수화 / 매수·매도 판단 / 리밸런싱 판단.
- 친구 UI 복제 / UI Grid 재개편.
- AI 에게 구성종목 추정시키기.

### FIX 라운드 (검증자 A-1 / A-3 / B-6 NOTE 반영, 2026-05-27)

5가지 지적 수정:

1. **A-1 / B-1 (ETF Exposure → AI Sessions 질문문에서 시장 판정 손실)**:
   - `ETFExposureDraft` schema v1 → **v2** 로 승격. `market_context_full:
     MarketContext | null` + `market_candidates: MarketCandidate[]` (excess_return
     포함) 필드 추가.
   - `ETFExposureView.handleTransferToSessions` 가 `buildMarketDiscoveryCopyText`
     호출 시 `marketContext: draft.market_context_full` + `candidates:
     draft.market_candidates` 명시 전달 → AI 문구의 [시스템 시장 판정] /
     [시장 대비 후보 강도] 가 정상 노출.
   - `TransferToETFExposureCard` 가 `marketContext` 도 draft 에 함께 저장.

2. **A-3 (copy text 자기모순)**:
   - `marketDiscoveryCopyText.ts` 의 [주의] 섹션을 `constituentsAnalysis` 유무에
     따라 분기. analysis 가 있으면 "구성종목 데이터는 수집된 스냅샷" 문구로
     교체 — 직전까지의 "구성 종목 정보가 아직 포함되지 않았다" 와의 자기
     모순 차단.

3. **B-6 #1 (asof 필수 → optional)**:
   - `GET /market/constituents/analysis` 의 `asof` query 를 optional 로 변경.
     누락 시 `latest_constituent_asof(ticker)` 중 MAX 사용. 데이터 1건도
     없으면 today (UTC) 로 fallback (compute_analysis 가 모두 unavailable
     로 반환).
   - 회귀 테스트 2건 신규.

4. **B-6 #2 (cache key source 일치)**:
   - 지시문 §4.3 cache key 원칙 `ticker+asof+source` 일치. 1차 단일 fetcher
     (pykrx PDF) 시점 — service 가 `PYKRX_SOURCE` 를 명시 import 후 cache
     check (`fetch_constituents(..., source=PYKRX_SOURCE)`). 다른 source 의
     기존 row 는 cache hit 처리되지 않음.
   - 회귀 테스트 1건 신규 (`test_refresh_cache_first_matches_pykrx_source`).

5. **A-2 (staged 외 unstaged 변경)**:
   - 직전 1차 commit 시점에 unstaged 잔재 (`MM app/decision_evidence_store.py`
     / `AM app/etf_constituents_store.py`) 가 있었음을 검증자 지적. 본 FIX
     라운드에서 모든 unstaged 를 명시 git add 로 재 staging.

**검증 재실행**: pytest **315 passed** (312 → 315, +3 FIX 회귀 / 회귀 0) /
black PASS / flake8 PASS / frontend lint PASS / frontend build PASS.

**KS-10 재측정**: trigger 0 / near 0. 주요 변경 파일:
- `etfExposureDraft.ts` 136 → ~150 (+14, 새 필드).
- `ETFExposureView.tsx` 234 → 215 (-19, 변환 코드 단순화).
- `marketDiscoveryCopyText.ts` 232 → 247 (+15, [주의] 분기).
- `etf_constituents_service.py` 307 → 305 (-2, cache check 통합).
- `api_etf_constituents.py` 210 → 240 (+30, asof optional fallback).
- `tests/test_etf_constituents_api.py` 142 → 232 (+90, 신규 3건).

---

## 0.1 직전 상태 — 2026-05-27 Market Regime & Benchmark Context 1차

```text
현재 단계: Market Regime & Benchmark Context 1차 (2026-05-27)
  — KODEX200 기준 시장 국면 판정 + KOSPI 보조 + 후보 ETF 초과수익 + Copy Text /
    AI Sessions 연계
이전 단계: AI Sessions / Decision Evidence 화면 분리 + Context Bridge (2026-05-21)
다음 단계 후보 (사용자 결정 대기):
  (a) ETF 구성 종목 / 중복률 (직전 BACKLOG)
  (b) 상승장 / 보합장 / 하락장 시장 국면 고도화 (본 STEP 1차의 다음)
  (c) NAV / 괴리율 / 유동성
  (d) AI 투자세션 결과 기반 개선
```

### 본 STEP 요약

- **방향**: 시스템이 **1차 시장 국면 판정** 을 한다 (지시문 §1) — AI 에게
  장세 판단을 맡기지 않고, KODEX200 (필수) / KOSPI (보조) 의 정량 지표로
  라벨을 산출한 뒤 AI 는 그 판정을 검토/해석/반론한다.
- **판정 로직 (지시문 §6)**: KODEX200 20거래일 / 60거래일 수익률 + 20일 /
  60일 이동평균 위치를 +1/-1/0 점수로 환산. 총점 +2 이상 상승장, -2 이하
  하락장, 그 외 보합장. KODEX200 데이터 부족 시 판정불가.
- **저장소 (지시문 §4.1)**: market_benchmark_daily_price 신규 테이블
  (`state/market/market_data.sqlite` 내). KOSPI 같이 ETF 가 아닌 지수만 별도
  보관. KODEX200 (069500) 은 기존 etf_daily_price 재사용 — API 응답에서는
  둘 다 benchmark 로 정규화.
- **Backend 신규 모듈 3개**:
  - `app/market_benchmark_store.py` (198 라인) — 테이블 DDL + upsert/fetch +
    KOSPI FDR refresh 함수 (`KS11`, 실패 격리).
  - `app/market_regime.py` (253 라인) — pure function 모듈. KODEX200 metrics /
    KOSPI metrics / regime score → label 매핑 / 후보 excess_return 계산.
  - 신규 테이블 1개: `market_benchmark_daily_price` (benchmark_id, date PK).
- **Backend 확장**:
  - `app/market_refresh_service.py` — `_execute_refresh_job` 끝부분에 KOSPI
    benchmark fetch 추가. 실패 시 격리 (전체 refresh 흐름 중단 X). 별도 log
    row 로 결과 기록 (`kospi-benchmark-{refresh_id}`).
  - `app/market_topn.py` — `compute_topn` 결과에 `market_context` 키 +
    각 candidate 에 `excess_return` 객체 추가. SQLite read-only 유지.
  - `app/api_market_topn.py` — Pydantic 모델 확장 (`MarketContextResponse` /
    `MarketContextKodex200` / `MarketContextKospi` /
    `MarketCandidateExcessReturn`).
  - `app/decision_evidence_store.py` + `app/api_decision_sessions.py` —
    `market_context_snapshot_json` 컬럼 추가 + 마이그레이션
    (`_migrate_add_market_context_snapshot`, ALTER TABLE ADD COLUMN). payload /
    response 에 `market_context_snapshot: dict` 추가.
- **Frontend 신규 컴포넌트 2개**:
  - `frontend/app/components/MarketContextCard.tsx` (120 라인) — 시장 배경
    카드 (라벨 + KODEX200/KOSPI 지표 + 판정 근거 + warnings).
  - `frontend/app/components/CandidateTable.tsx` (198 라인) — 통합 후보 테이블
    분리 (MD KS-10 회피용). KODEX200 대비 1m/3m %p 컬럼 추가.
- **Frontend 확장**:
  - `frontend/lib/api.ts` — `MarketContext` / `MarketCandidateExcessReturn` /
    `MarketRegimeCode` 타입 + decision_session 의 `market_context_snapshot`.
  - `frontend/lib/aiSessionsDraft.ts` — schema v2 + `market_context_snapshot`.
  - `frontend/lib/marketDiscoveryCopyText.ts` — [시스템 시장 판정] / [시장
    대비 후보 강도] 섹션 추가 + 요청 문구를 "시스템 판정 전제 + 해석/반론
    요청" 으로 변경 (지시문 §11 / AC-19).
  - `MarketDiscoveryView.tsx` — MarketContextCard 렌더 + CandidateTable 분리
    호출 + CopyTextCard/TransferToAISessionsCard 에 marketContext 전달.
  - `TransferToAISessionsCard.tsx` — `_toMarketContextSnapshot` 헬퍼 +
    draft 에 `market_context_snapshot` 포함.
  - `AISessionsCreateTab.tsx` — POST payload 에 `market_context_snapshot`.
  - `AISessionsListTab.tsx` — 상세 카드에 "시장 문맥 (저장 시점)" 섹션.
  - `globals.css` — `.market-context-card` / `.market-regime-label.regime-*`
    / `.market-regime-benchmarks` / `.market-regime-reasons` 스타일.
- **AI 요청 문구 (지시문 §11)**:
  > 시스템의 시장 국면 판정과 KODEX200/KOSPI 대비 초과수익을 전제로,
  > 이 후보들이 시장 전체 상승에 따라간 것인지, 독립적인 섹터/테마 강세인지
  > 해석해주세요. 매수/매도 추천은 하지 말고, 시스템 판정이 틀릴 수 있는
  > 반대 근거와 추가 확인 포인트를 제시해주세요.
- **AI Sessions 저장 (지시문 §13 / AC-21~22)**: `POST /decision/sessions` 가
  `market_context_snapshot` (free schema dict) 을 저장하고 `GET /{id}` 가
  그대로 반환. AI Sessions 상세 화면에 시장 문맥 섹션 노출.
- **검증**: pytest **286 passed** (262 → 286, +24 신규 / 기존 회귀 0) /
  black PASS / flake8 PASS / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 1차 측정 시 `MarketDiscoveryView.tsx` 856 라인 (near 850) 진입 → 즉시
    `CandidateTable` 별도 파일로 분리 → 686 라인 (near 미달 164 여유). 신규
    market 배경 카드도 별도 파일.
  - 백엔드 핵심 모듈 최대 `app/market_topn.py` 590 (near 600 까지 10 라인
    여유) / `app/draft_message.py` 564 (기존).
  - 신규 backend: `market_regime.py` 253 / `market_benchmark_store.py` 198 /
    decision_evidence_store +38 (378 → 416).
  - 신규 tests: regime 127 / benchmark 149 / topn_api +151 / decision_sessions
    +51 / decision_evidence +44.
  - 750 라인 이상 보고: `tests/test_holdings_message_text.py` 924 (기존) /
    `frontend/lib/api.ts` 786 (582 → 786, 본 STEP +65 — `.ts` 라이브러리라
    KS-10 컴포넌트 기준에는 미해당, 별도 보고만).

### 신규 / 수정 파일

신규:
- `app/market_benchmark_store.py` (198) — benchmark 테이블 + KOSPI FDR refresh.
- `app/market_regime.py` (253) — pure function regime + excess_return.
- `tests/test_market_regime.py` (127) — regime + excess_return 단위 테스트 11건.
- `tests/test_market_benchmark_store.py` (149) — store + KOSPI refresh 6건.
- `frontend/app/components/MarketContextCard.tsx` (120) — 시장 배경 카드.
- `frontend/app/components/CandidateTable.tsx` (198) — KS-10 회피 분리.

수정:
- `app/api.py` — 변경 없음 (router 는 기존 `market_topn_router` 그대로).
- `app/market_refresh_service.py` — KOSPI benchmark fetch + log_refresh +
  실패 격리.
- `app/market_topn.py` — `market_context` + candidate `excess_return` 추가.
- `app/api_market_topn.py` — 신규 Pydantic 응답 모델 5개.
- `app/decision_evidence_store.py` — `market_context_snapshot_json` 컬럼 +
  `_migrate_add_market_context_snapshot` 마이그레이션 + insert signature 확장.
- `app/api_decision_sessions.py` — payload + response 에 `market_context_snapshot`.
- `tests/test_market_topn_api.py` — 신규 5건 (context unavailable / ok /
  partial / excess_return / kospi null).
- `tests/test_decision_sessions_api.py` — 신규 2건 (store / default empty).
- `tests/test_decision_evidence_store.py` — 신규 1건 (column 자동 추가).
- `frontend/lib/api.ts` — `MarketContext*` / `MarketCandidateExcessReturn` /
  `decision_session.market_context_snapshot`.
- `frontend/lib/aiSessionsDraft.ts` — schema v2 + `market_context_snapshot`.
- `frontend/lib/marketDiscoveryCopyText.ts` — [시스템 시장 판정] / [시장 대비
  후보 강도] 섹션 + 새 AI 요청 문구.
- `frontend/app/components/MarketDiscoveryView.tsx` — 카드/테이블 분리 통합 +
  marketContext prop 전달.
- `frontend/app/components/TransferToAISessionsCard.tsx` — draft 에 시장
  문맥 스냅샷 포함.
- `frontend/app/components/AISessionsCreateTab.tsx` — POST payload 확장.
- `frontend/app/components/AISessionsListTab.tsx` — 상세에 시장 문맥 섹션.
- `frontend/app/globals.css` — `.market-context-card` / regime 라벨 스타일.
- `docs/handoff/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/backlog/BACKLOG.md`.

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §16)

- 친구 UI 전체 복제 / 완성형 시장 정권 모델.
- KOSDAQ 비교 (사용자가 코스피 중심 — 지시문 §3).
- ETF 구성 종목 수집 / 구성 종목 중복률.
- NAV / 괴리율 / 거래대금·유동성 점수화.
- ML 연결 / 매수·매도 판단 / 리밸런싱 판단.
- Telegram 문구 변경 / OCI PUSH 연결.
- UI Grid 재개편.

### FIX 라운드 (검증자 A-1 NOTE 반영, 2026-05-27)

- **지적**: `TransferToAISessionsCard._toMarketContextSnapshot` 가 시장 국면
  요약만 저장하고 **후보별 KODEX200/KOSPI 초과수익** 을 누락. 지시문 §12 의
  "포함 내용 — 후보별 KODEX200 대비 초과수익 / 후보별 KOSPI 대비 초과수익,
  있으면 포함" 명시와 불일치.
- **수정** (`frontend/app/components/TransferToAISessionsCard.tsx`):
  `_toMarketContextSnapshot` signature 에 `candidates: MarketCandidate[]` 추가
  + 반환 dict 에 `candidate_excess_returns: [{rank, ticker, name,
  vs_kodex200_1m_pctp, vs_kodex200_3m_pctp, vs_kospi_1m_pctp,
  vs_kospi_3m_pctp}]` 배열 포함. 호출부 `handleTransfer` 에서 현재 candidates
  를 전달.
- AI Sessions 상세 화면은 `JSON.stringify(detail.market_context_snapshot, null,
  2)` 로 raw JSON 노출 중이라 별도 UI 변경 없이 후보별 초과수익이 자동 표시.
- **검증 재실행**: pytest 286 (백엔드 미변경) / frontend lint PASS / frontend
  build PASS.
- **KS-10 재측정**: trigger 0 / near 0. TransferToAISessionsCard 130 → 146
  (+16). MarketDiscoveryView 695 그대로.

---

## 0.1 직전 상태 — 2026-05-21 AI Sessions / Decision Evidence + Context Bridge

```text
현재 단계: AI Sessions / Decision Evidence 화면 분리 + Context Bridge (2026-05-21)
이전 단계: AI 투자세션 기록 / Decision Evidence 1차 (2026-05-20) — Market Discovery 안 인라인
다음 단계 후보 (사용자 결정 대기):
  (a) KODEX200 / KOSPI 대비 초과수익 (alpha)
  (b) 상승장 / 보합장 / 하락장 시장 국면 판단
  (c) ETF 구성 종목 / 정적 데이터 수집
  (d) AI 투자세션 결과 기반 개선
```

### 본 STEP 요약

- **방향**: Market Discovery 와 AI Sessions 를 **화면 책임 분리**. Market Discovery
  는 ETF 후보 발굴 + 복사용 문구 + "AI Sessions로 넘기기" 까지만 남기고, 외부
  AI 답변 / 사용자 메모 / 1차 판정 / 다음 확인 항목은 AI Sessions 화면에서 저장.
  AI Sessions 화면은 [새 기록 저장] / [기록 조회] 2 탭으로 분리.
- **AI 답변 채널 분리 (스키마 변경)**: 기존 단일 `answer_text` → `gpt_answer_text`
  / `gemini_answer_text` / `claude_answer_text` 3 컬럼. 저장 시 3 채널 중 최소
  1개 이상 비어있지 않아야 한다 (store-level + frontend gating). 직전 STEP 의
  단일 answer_text DB 는 `init_db()` 시점에 자동 무손실 마이그레이션 (SQLite
  권장 패턴: new table + copy + drop + rename. 기존 answer_text 값은
  gpt_answer_text 로 이관).
- **Context Bridge**: Market Discovery → AI Sessions draft 전달은
  `frontend/lib/aiSessionsDraft.ts` 가 sessionStorage 로 처리. 서버 draft
  저장소 없음 (지시문 §5.2 / §14). 브라우저 새로고침으로 draft 가 사라지는
  것은 본 STEP 허용 범위.
  - Market Discovery 의 "AI Sessions로 넘기기" 클릭 시 — buildMarketDiscoveryCopyText
    로 question_text 자동 생성 + sessionStorage 저장 + setActive("ai_sessions").
  - AI Sessions 마운트 시 draft 있으면 [새 기록 저장] 탭 default, 없으면 [기록 조회]
    탭 default.
- **Frontend 좌측 메뉴**: AI Sessions 항목 추가 (Dashboard / Market Discovery /
  **AI Sessions** / Holdings / Approval-Telegram / Data Status).
- **Backend API 변경**:
  - `POST /decision/sessions` — 3 답변 필드 + "최소 1개 이상" group-required 검증
    (422). filters 4 필드 모두 required (직전 STEP fail-loud 정책 유지).
  - `GET /decision/sessions` — summary 응답에 `has_gpt_answer / has_gemini_answer
    / has_claude_answer` 추가 (목록에서 채널별 답변 입력 여부 한눈에 확인).
  - `GET /decision/sessions/{id}` — record 에 3 답변 분리 필드.
- **검증**: pytest 261 passed (253 → 261, +8 신규 / 기존 18 갱신) / black PASS /
  flake8 PASS / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 1차 측정 시 `MarketDiscoveryView.tsx` 891 라인 (near 850 진입) → 즉시 분리.
    `TransferToAISessionsCard.tsx` (88 라인) 를 별도 파일로 추출 → 824 라인 (near
    미달 26 라인 여유).
  - 백엔드 핵심 모듈 최대 564 (`app/draft_message.py`, 기존). 신규
    `decision_evidence_store.py` 354 / `api_decision_sessions.py` 195.
  - 테스트 최대 924 (`tests/test_holdings_message_text.py`, 기존).
  - 750 라인 이상: 924 / 824.

### 신규 / 수정 / 삭제 파일

신규:
- `frontend/lib/aiSessionsDraft.ts` (69 라인) — sessionStorage Context Bridge util.
- `frontend/app/components/AISessionsView.tsx` (98 라인) — 탭 컨테이너.
- `frontend/app/components/AISessionsCreateTab.tsx` (308 라인) — 새 기록 저장 탭.
- `frontend/app/components/AISessionsListTab.tsx` (273 라인) — 기록 조회 + 상세 탭.
- `frontend/app/components/TransferToAISessionsCard.tsx` (88 라인) — Market
  Discovery 에서 분리된 전달 카드 (KS-10 회피).

삭제:
- `frontend/app/components/AISessionRecordPanel.tsx` — 직전 STEP 의 Market
  Discovery 인라인 패널. 본 STEP §4.2 명시 제거 항목 (Market Discovery 내
  기록 패널 금지).

수정:
- `app/decision_evidence_store.py` — 3 답변 컬럼 + 마이그레이션 + 그룹 필수 검증
  (263 → 354).
- `app/api_decision_sessions.py` — Pydantic 모델 3 분리 + has_* 필드 (189 → 195).
- `frontend/lib/api.ts` — DecisionSession 타입의 3 분리 필드 + has_* + 변환 헬퍼.
- `frontend/app/components/MarketDiscoveryView.tsx` — AISessionRecordPanel
  제거 + "AI Sessions로 넘기기" 버튼 + onNavigate prop (812 → 891 → 824, 분리 후).
- `frontend/app/components/LeftSidebar.tsx` — `ai_sessions` MenuKey + MENU_ITEMS 항목.
- `frontend/app/components/MainPanel.tsx` — `ai_sessions` 분기 + MarketDiscovery
  로 onNavigate 전달.
- `frontend/app/globals.css` — `.decision-tab-row` / `.decision-tab-btn` /
  `.decision-answer-badges` 스타일.
- `tests/test_decision_evidence_store.py` + `tests/test_decision_sessions_api.py`
  — 3 답변 필드 / has_* / 그룹 필수 / 마이그레이션 검증 (기존 18 갱신 + 신규 8).
- `docs/handoff/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/backlog/BACKLOG.md` — 본 STEP 반영.

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §14)

- Market Discovery 안에 기록 패널 붙이기 (직전 STEP 의 인라인 패턴은 폐기).
- 저장과 조회를 같은 덩어리 화면으로 섞기.
- 서버 draft 저장소 만들기 (sessionStorage 만 사용, 새로고침 시 draft 소멸 허용).
- KODEX200 / KOSPI 초과수익 / 시장 국면 판정 / ETF 구성 종목 / NAV / 유동성.
- ML / 매수·매도 판단 / 매매 결과 추적.
- AI API 직접 호출 / 자동 AI 토론 / Telegram 변경 / OCI PUSH 연결.

### HOTFIX 라운드 #2 (refresh polling 사고 1건 후속, 2026-05-22)

- **현상**: 사용자가 Market Discovery 의 "최신 시장 데이터 갱신" 버튼을 누른
  뒤 frontend 가 "상태 확인 시간이 너무 길어졌습니다. 잠시 후 다시 시도하세요."
  오류를 표시. 그러나 새로고침 시 새 asof 로 정상 조회됨.
- **원인 (로그 분석)**: 백엔드 refresh job 자체는 1115/1115 성공 / 0 실패 /
  `error_summary=None` 로 **정상 완료**. 그러나 가격 수집이 약 6분 8초
  (368초) 걸렸고, frontend 의 polling 상한 (`POLL_MAX_TICKS=90 ×
  POLL_INTERVAL_MS=4000ms = 360초 = 6분`) 을 **8초 초과**. 그 시점에 frontend
  가 fail 표시로 빠지면서도 백엔드는 묵묵히 SQLite 에 데이터 정상 저장.
- **수정** (`frontend/app/components/MarketDiscoveryView.tsx`):
  - (a) `POLL_MAX_TICKS` 90 → 120 (6분 → **8분**). 1115 ETF 6분+ 케이스 흡수.
  - (b) timeout 진입 시점에 한 번 더 `fetchMarketRefreshStatus()` 명시 조회.
    `completed / failed / skipped_cooldown / idle` 4 가지 응답은 그대로
    `applyStatus` 가 처리 (completed 면 loadTopn 호출). running 으로 남아
    있거나 fetch 자체 실패하면 fallback fail 표시. polling tick 사이의 짧은
    틈에 백엔드가 완료한 케이스 차단.
- **검증**: pytest 262 (백엔드 미변경) / frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0. `MarketDiscoveryView.tsx` 824 → 845 (+21).
  near 850 까지 5 라인 여유.
- **read-only 진단 → fix 까지**: 사용자 명시 요청 ("로그만 확인" → "(a) + (b)
  둘 다 진행"). market_refresh_log / etf_master / etf_daily_price 조회만으로
  근본 원인 식별, 소스 변경은 사용자 승인 후에만.

### HOTFIX 라운드 (운영 사고 1건 후속, 2026-05-21)

- **현상**: 사용자 PC 의 운영 DB (`state/decision/decision_evidence.sqlite`)
  에서 AI Sessions 화면 진입 시 `GET /decision/sessions` 가
  `sqlite3.OperationalError: no such column: answer_text` 로 500. 원인:
  `_migrate_legacy_answer_text` 가 1차 시점에 부분 진행되어 `ai_session_records`
  는 이미 신규 (3 분리) 스키마인데 `ai_session_records_new` 테이블이 잔재로
  남은 상태. PRAGMA 결과와 실제 SELECT 가능 컬럼 사이의 불일치 가능성도 함께
  관찰.
- **즉시 조치**: 사용자 PC DB 의 `ai_session_records_new` 잔재 drop (양쪽 테이블
  모두 0 rows 였으므로 데이터 손실 0).
- **코드 방어 강화** (`app/decision_evidence_store.py`):
  - `_migrate_legacy_answer_text` 진입 시 `DROP TABLE IF EXISTS
    ai_session_records_new` 로 잔재를 먼저 cleanup (정상 path 에서는 영향 0).
  - PRAGMA 통과 후 `SELECT answer_text FROM ai_session_records LIMIT 0` 으로
    실제 컬럼 존재를 한 번 더 확인 — PRAGMA 와 SELECT 가 어긋나는 race 가
    있을 때 안전 skip.
  - INSERT 단계에서 `sqlite3.OperationalError` 발생 시 `ai_session_records_new`
    drop 후 raise — 다음 호출이 stale 잔재 위에서 동작하지 않도록.
- **회귀 테스트 1건 추가**:
  `test_init_db_cleans_up_stale_ai_session_records_new` — 잔재 _new 테이블을
  의도적으로 주입한 뒤 init_db() 호출 시 자동 cleanup 되는지 검증 + 정상
  insert/조회 동작 확인.
- **검증 재실행**: pytest 262 passed (261 → 262) / black PASS / flake8 PASS.
- **KS-10 재측정**: trigger 0 / near 0. `decision_evidence_store.py` 354 → 378
  라인 (+24, trigger 650 미달). 750 라인 이상 파일 변동 없음.

---

## 0.1 직전 상태 — 2026-05-20 AI 투자세션 기록 / Decision Evidence 1차

```text
현재 단계: AI 투자세션 기록 / Decision Evidence 1차 (2026-05-20) — 외부 AI 채널 답변 + 사용자 메모/판정 저장
이전 단계: AI 투자세션 복사용 문구 1차 (2026-05-20) — 외부 AI 채널 입력문 생성
다음 단계 후보 (사용자 결정 대기):
  (a) KODEX200 / KOSPI 대비 초과수익 (alpha)
  (b) 상승장 / 보합장 / 하락장 시장 국면 판단
  (c) ETF 구성 종목 / 정적 데이터 수집 (직전 STEP BACKLOG)
  (d) AI 투자세션 결과 기반 개선
```

### 본 STEP 요약

- **방향**: Market Discovery 후보 → 외부 AI 질문 → AI 답변 → 사용자 메모 + 1차
  판정을 시스템에 저장하고 다시 조회할 수 있는 최소 기록 구조. AI API 직접
  호출 / 자동 토론 / 매매 결과 추적은 본 STEP 의 작업이 아니다 (지시문 §2 / §11).
- **저장소 분리**: 시장 데이터 (`state/market/market_data.sqlite`) 와 별도로
  `state/decision/decision_evidence.sqlite` 신설. PROJECT_ORIGIN_INTENT §10 의
  "데이터 종류별 SSOT 분리" 정신과 정합. MongoDB / 신규 대형 DB 도입 없음.
- **테이블 1개 신설**: `ai_session_records` — id / created_at / updated_at /
  asof / source_screen / filters_json / candidate_snapshot_json / question_text /
  answer_text / user_memo / user_verdict / next_checks_json /
  linked_market_refresh_id. created_at 은 KST iso 마이크로초 포함 (정렬 안정성).
- **Backend (신규 모듈)**:
  - `app/decision_evidence_store.py` (263 라인) — DDL + SQLite store + 검증
    (`DecisionValidationError`) + `insert_record` / `list_recent_records` /
    `get_record`.
  - `app/api_decision_sessions.py` (186 라인) — FastAPI APIRouter.
    `POST /decision/sessions` (422 on invalid verdict / empty snapshot / 빈 텍스트),
    `GET /decision/sessions?limit=10` (목록, 요약 우선순위 memo → answer → question
    의 앞 50자), `GET /decision/sessions/{id}` (없으면 status=not_found / record=null).
  - `app/api.py` 에 `decision_sessions_router` include 1줄 추가.
- **사용자 1차 판정 enum**: `useful / needs_constituents / needs_market_compare /
  hold` — FastAPI Literal 가 422 가드. 기본값 `hold`.
- **Frontend (KS-10 회피용 분리)**:
  - `frontend/app/components/AISessionRecordPanel.tsx` (365 라인) — Market
    Discovery 안에서 사용되는 기록 패널. 별도 파일로 분리해서 MarketDiscoveryView
    의 KS-10 트리거 회피.
  - `frontend/lib/api.ts` — `DecisionUserVerdict` / `DECISION_VERDICT_LABEL` /
    `DecisionFilters` / `DecisionCandidateSnapshot` / `CreateDecisionSessionRequest`
    / 응답 모델 + `createDecisionSession` / `fetchDecisionSessions` /
    `fetchDecisionSession` + `toDecisionCandidateSnapshot` 변환 헬퍼.
  - `MarketDiscoveryView.tsx` — `data.asof && data.filters` guard 안에서
    CopyTextCard + AISessionRecordPanel 둘 다 렌더 (직전 STEP fail-loud 패턴
    그대로 유지).
- **자동 채움**: 패널 내 "현재 복사용 문구를 질문에 채우기" 버튼 — 동일한
  `buildMarketDiscoveryCopyText` 사용 → CopyTextCard 와 같은 텍스트.
- **저장 시 snapshot**: candidate / filters 는 저장 시점 그대로 JSON 으로
  영속화. Market Discovery 데이터가 바뀌어도 과거 기록의 후보는 불변
  (지시문 §4 / §7.1).
- **검증**: pytest 253 passed (235 → 253, +18 신규) / black PASS / flake8 PASS /
  frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 백엔드 핵심 모듈 최대 564 (`app/draft_message.py`, 기존, 본 STEP 미변경).
    신규 `decision_evidence_store.py` 263 / `api_decision_sessions.py` 186.
  - 테스트 최대 924 (`tests/test_holdings_message_text.py`, 기존). 신규
    테스트 154 + 155.
  - 프론트 컴포넌트 최대 812 (`MarketDiscoveryView.tsx`, 802 → 812, +10) — near
    850 까지 **38 라인 여유**. 신규 `AISessionRecordPanel.tsx` 365.

### 신규 / 수정 파일

신규:
- `app/decision_evidence_store.py` (263 라인) — SQLite store.
- `app/api_decision_sessions.py` (186 라인) — FastAPI router.
- `tests/test_decision_evidence_store.py` (154 라인) — store 단위 테스트 9건.
- `tests/test_decision_sessions_api.py` (155 라인) — API 통합 테스트 9건.
- `frontend/app/components/AISessionRecordPanel.tsx` (365 라인) — 기록 패널.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md` — 방향 앵커 문서 (지시문 §8).

수정:
- `app/api.py` — `decision_sessions_router` include.
- `frontend/lib/api.ts` — decision 타입 / 함수 / 변환 헬퍼 (+139 라인, 582 → 721).
- `frontend/app/components/MarketDiscoveryView.tsx` — 패널 import + 렌더 통합
  (802 → 812, +10).
- `frontend/app/globals.css` — `.decision-card` / `.decision-textarea` /
  `.decision-select` / `.decision-pre` / `.decision-detail-card`.
- `docs/handoff/STATE_LATEST.md` — 본 §0 갱신.
- `docs/backlog/BACKLOG.md` — "판단 근거 저장 (decision evidence)" 항목을
  REACTIVATED → 본 STEP 처리로 상태 갱신 (단, 매매 결과 추적은 별도 STEP
  유지).
- `.gitignore` — `state/decision/decision_evidence.sqlite` (+ journal/wal/shm)
  운영 DB 추적 금지 추가.

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §11)

- KODEX200 / KOSPI 초과수익 계산 / 시장 국면 판정.
- ETF 구성 종목 수집 / NAV / 괴리율 / 유동성 점수화.
- ML 연결 / 매수·매도 판단 / 매매 결과 추적.
- Telegram 문구 변경 / OCI PUSH 연결 / UI Grid 추가 개편.
- AI API 직접 호출 / 자동 AI 토론.

### FIX 라운드 (검증자 B-1 NOTE 반영, 2026-05-20)

- **지적**: `DecisionFiltersModel` 의 4 필드 (`exclude_inverse / exclude_leveraged
  / exclude_synthetic / exclude_futures`) 가 모두 `bool = True` default — 요청에
  `filters: {}` 같은 incomplete payload 가 들어와도 4 필드가 모두 True 로 채워져
  저장돼서 실제 적용 필터와 어긋날 위험. snapshot 핵심 데이터의 fail-loud 위반.
- **수정**: 4 필드를 `Field(...)` 로 변경 (required). 누락 시 FastAPI/Pydantic
  자동 422.
- **신규 테스트 1건 추가**: `test_post_decision_sessions_rejects_incomplete_filters`
  — `filters: {}` 와 `filters: {exclude_inverse: True, exclude_leveraged: True}`
  모두 422 응답을 명시 검증.
- **검증 재실행**: pytest 254 passed (253 → 254) / black PASS / flake8 PASS /
  frontend lint PASS / frontend build PASS.
- **KS-10 재측정**: trigger 0 / near 0. `app/api_decision_sessions.py` 186 → 189
  (+3 주석), `tests/test_decision_sessions_api.py` 155 → 171 (+16 새 테스트).
  프론트 컴포넌트 최대 812 (`MarketDiscoveryView.tsx`) 그대로 — near 850 까지
  38 라인 여유 유지.

---

## 0.1 직전 상태 — 2026-05-20 AI 투자세션 복사용 문구 1차

```text
현재 단계: AI 투자세션 복사용 문구 1차 (2026-05-20) — Market Discovery → 외부 AI 채널 복사 입력문
이전 단계: Market Discovery Grid 사용성 FIX (2026-05-19) — GRID 우선 + 컬럼 클릭 정렬
다음 단계 후보:
  (a) 운영 사용 후 ETF 구성 종목 / 정적 데이터 수집 (본 STEP 신규 BACKLOG)
  (b) Data Status 실제 연결 (기존 BACKLOG)
  (c) 사용자 결정 — Settings / decision evidence 등
```

### 본 STEP 요약

- **방향**: Market Discovery 후보를 사용자가 GPT / Gemini / Claude 투자세션에 그대로
  붙여넣을 수 있는 1차 시장 해석 요청문 (복사용 입력문) 생성. AI 직접 호출 / 자동
  토론 / AI 응답 저장은 하지 않는다.
- **새 API 없음**: 이미 조회된 `GET /market/topn/latest` 응답
  (`asof` / `filters` / `candidates`) 을 그대로 사용해서 frontend 가 문구를 빌드한다.
  조회 API 재설계 없음. 백엔드 변경 0 라인.
- **Frontend**:
  - 신규 모듈 `frontend/lib/marketDiscoveryCopyText.ts` — pure function
    `buildMarketDiscoveryCopyText({asof, filters, candidates})` 가 지시문 §5 구조의
    문구를 빌드한다. (데이터 기준 / 필터 조건 / 주의 / 후보 ETF / 요청 섹션)
  - `MarketDiscoveryView.tsx` 에 `CopyTextCard` 컴포넌트 추가. 2 버튼 + 1 textarea:
    "AI 투자세션 문구 생성" / "클립보드 복사" / textarea.
    - 생성 → textarea 에 문구 표시.
    - 복사 → `navigator.clipboard.writeText` 시도. 성공 시 안내, 실패 시 안내 +
      textarea 에서 직접 선택 복사 (AC-10).
    - textarea 는 editable — 사용자가 직접 수정 후 복사 가능.
  - 배치: GRID + SortStatusLine 직후, RefreshControlCard 앞 — 후보를 본 직후
    바로 복사할 수 있도록.
- **문구 한계 명시 (AC-6)**:
  - "이 입력은 ETF명과 기간별 수익률 기반의 1차 시장 해석용입니다."
  - "ETF 구성 종목과 구성 비중 정보는 아직 포함되지 않았습니다."
  - 요청 섹션은 시장 테마 / 섹터 흐름 해석 + 추가 확인 포인트 도출. 매수 / 매도
    추천 요구 없음.
- **검증**: pytest 235 passed (변화 없음 — 백엔드 미변경) / black PASS / flake8 PASS /
  frontend lint PASS / frontend build PASS.
- **KS-10**: trigger 0 / near 0.
  - 백엔드 핵심 모듈 최대 564 (`app/draft_message.py`, 기존) — trigger 650 미달.
  - 테스트 최대 924 (`tests/test_holdings_message_text.py`, 기존) — trigger 1500 미달.
  - 프론트 컴포넌트 최대 790 (`frontend/app/components/MarketDiscoveryView.tsx`,
    700 → 790, +90) — trigger 900 / near 850 미달 (60 라인 여유).
  - 신규 ts 97 라인 (`frontend/lib/marketDiscoveryCopyText.ts`).
  - 750 라인 이상: `tests/test_holdings_message_text.py` 924 (기존) /
    `frontend/app/components/MarketDiscoveryView.tsx` 790 (본 STEP +90).

### 신규 / 수정 파일

신규:
- `frontend/lib/marketDiscoveryCopyText.ts` — 복사용 문구 빌더 (pure function, 97 라인).

수정:
- `frontend/app/components/MarketDiscoveryView.tsx` — `CopyTextCard` 컴포넌트 +
  렌더 위치 + import 1줄 추가 (700 → 790).
- `frontend/app/globals.css` — `textarea.market-copy-textarea` 최소 스타일.
- `docs/handoff/STATE_LATEST.md` — 본 §0 갱신.
- `docs/backlog/BACKLOG.md` — "ETF 구성 종목 / 정적 데이터 수집" 항목 신규.

### 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §7 그대로)

- GPT / Gemini / Claude API 직접 호출 / 자동 AI 토론 / AI 응답 저장.
- decision evidence 구현 / 구성 종목 추출 / 섹터 자동 분류 / ML 연결.
- 점수 산식 추가 / 매수·매도 판단 / Telegram 문구 변경 / OCI PUSH 연결.
- Market Discovery GRID 추가 개편 / 조회 API 재설계.

### FIX 라운드 (검증자 B-1 NOTE 반영, 2026-05-20)

- **지적**: `marketDiscoveryCopyText.ts` 가 `asof` 누락 시 `"YYYY-MM-DD"` placeholder
  로 대체하고, `MarketDiscoveryView.tsx` 가 `data.filters` 누락 시
  `DEFAULT_MARKET_TOPN_FILTERS` 로 진행 — 필수 출력 데이터 누락이 명확한 오류로
  드러나지 않는 fallback 구조 (frontend/lib/api.ts 의 `apiBase()` fail-loud
  패턴과 충돌).
- **수정**:
  - `buildMarketDiscoveryCopyText` 의 `asof` 타입을 `string | null | undefined`
    → `string` 으로 좁히고, 빈 문자열이면 `Error` 를 throw (silent fallback 금지).
  - `MarketDiscoveryView` 의 CopyTextCard 호출을 `data.asof && data.filters` 가드로
    감싸고 false 일 경우 명시 에러 카드 표시. `data.filters ?? DEFAULT_*` fallback
    제거.
  - `CopyTextCard` 컴포넌트의 `asof` prop 타입도 `string` 으로 좁힘.
- **검증 재실행**: pytest 235 passed / black PASS / flake8 PASS / frontend lint PASS /
  frontend build PASS.
- **KS-10 재측정**: trigger 0 / near 0. `MarketDiscoveryView.tsx` 790 → 802 라인
  (+12, near 850 까지 48 라인 여유). `marketDiscoveryCopyText.ts` 97 → 107 라인.

---

## 0.1 직전 상태 — 2026-05-19 Market Discovery Grid 사용성 FIX

```text
현재 단계: Market Discovery Grid 사용성 FIX (2026-05-19) — GRID 우선 + 컬럼 클릭 정렬 + order=asc 지원
이전 단계: Market Discovery 통합 후보 테이블 1차 (2026-05-19) — basis selector + 1 통합 표
다음 단계 후보:
  (a) AI 투자세션 복사용 문구 / Data Status 실제 연결 (기존 BACKLOG)
  (b) 사용자 결정 — Settings 화면 / decision evidence 등
```

### 본 STEP 요약

- **방향**: Market Discovery 진입 시 GRID 우선 노출 + 수익률 컬럼 클릭으로 정렬. 별도
  basis selector 버튼 영역 제거 (컬럼 클릭으로 통합).
- **Backend**:
  - `GET /market/topn/latest` 에 `order: Literal["desc", "asc"]` query param 추가
    (default `desc`).
  - desc → 전체 후보 기준 TOP N, asc → 전체 후보 기준 BOTTOM N.
  - 정렬 순서: SQLite 전체 후보 → 태깅 → exclude → selected basis None 제외 →
    `kept.sort(reverse=(order=='desc'))` → TOP N → rank 재부여.
  - **프론트 로컬 reverse 금지** — `test_compute_topn_order_asc_returns_bottom_n` 가
    명시 검증 (전체 5건 중 BOTTOM 2 = B02 / B01, 로컬 reverse 면 T03 / T02 가 됨).
  - 응답 model 에 `order: Optional[str]` 추가.
  - invalid order 는 FastAPI Literal → HTTP 422.
- **Frontend**:
  - `BasisSelector` 컴포넌트 제거. 컬럼 클릭으로 basis 변경.
  - `SortableHeader` 컴포넌트 — 헤더 클릭 + 정렬 아이콘 (↓ / ↑) 표시.
  - `handleSort(column)`:
    - 같은 컬럼 재클릭 → `order` 토글 (desc ↔ asc).
    - 다른 컬럼 클릭 → basis 변경 + `order=desc` 리셋.
  - 라벨 통일: `MARKET_BASIS_COLUMN_LABEL` → "일간 수익률 / 1개월 수익률 / 3개월 수익률".
    "일간 급등 / 1개월 모멘텀 / 3개월 추세" 표현 제거.
  - `SortStatusLine` — "정렬 기준: 1개월 수익률 ↓ 내림차순" 짧은 표시.
  - **GRID 우선 배치**: `<CandidateTable>` 이 가장 위, 보조 컨트롤 (RefreshControl /
    FilterCard / SummaryHeader) 은 그 아래.
  - subtitle 축소: "SQLite 기준 최신 시장 데이터에서 일반 ETF 후보를 보여줍니다.
    수익률 컬럼을 클릭하면 정렬됩니다." (긴 설명 제거).
- **운영 1회 검증 (uvicorn + curl)**:
  - default → `basis=one_month order=desc`, rank 1 = 139260 (1m +49.87%).
  - `?order=asc` → BOTTOM 3 = 290080 / 451530 / 476000 (전체 후보 기준 하위, 로컬
    reverse 가 아님).
  - `?basis=daily&order=desc` → rank 1 = 0183J0 (daily +5.42%).
  - `?order=random` → HTTP 422.
- **검증**: pytest 235 passed (231 → +4). black PASS / flake8 PASS / lint+build PASS.
- **KS-10**: trigger 0 / near 0.

### 신규 / 수정 파일

수정:
- `app/market_topn.py` — `ALLOWED_ORDER` / `DEFAULT_ORDER` + `compute_topn` 에 `order`
  파라미터 + `kept.sort(reverse=(order=='desc'))` + 응답에 `order` 키 추가.
- `app/api_market_topn.py` — `OrderLiteral` + endpoint `order` 파라미터 + `MarketTopNResponse`
  에 `order` 필드.
- `frontend/lib/api.ts` — `MarketOrder` 타입 + `DEFAULT_MARKET_ORDER` +
  `MARKET_BASIS_COLUMN_LABEL` + `fetchMarketTopnLatest(n, {basis, order, ...})`.
  검증자 B-6 NOTE 반영 — UI 미사용 + 이전 표현 잔존 상수 `MARKET_BASIS_LABEL` 제거.
- `frontend/app/components/MarketDiscoveryView.tsx` — BasisSelector 제거 →
  `SortableHeader` + `SortStatusLine` + `handleSort` + GRID 우선 배치. subtitle 축소.
- `frontend/app/globals.css` — `.market-topn-sortable` / `.market-topn-sort-indicator` /
  `.market-topn-sort-status` / `.market-discovery-subtitle`.
- `tests/test_market_topn.py` — 4 신규 테스트 (default desc / asc 가 전체 BOTTOM N /
  invalid order fallback / asc rank 1 부터 재부여).
- `docs/handoff/STATE_LATEST.md` — 본 §0 갱신.

### 이번 STEP 에서 의도적으로 하지 않은 것

- 섹터 / 테마 분류 / 구성 종목 추출 / AI 투자세션 복사용 문구.
- Settings 화면 / 기본 조회 기준 설정 UI / 컬럼 표시·숨김 / 시가총액·거래량 정렬.
- 차트 / ML / 매수·매도 판단 / OCI / Data Status 상세.
- refresh endpoint 경로 변경 (POST /market/refresh / GET /market/refresh/status 유지).

---

## 0.1 직전 상태 — 2026-05-19 Market Discovery 통합 후보 테이블 1차

```text
현재 단계: Market Discovery 통합 후보 테이블 1차 (2026-05-19) — basis selector + 1 통합 표
이전 단계: Market Discovery 후보 정제 1차 (2026-05-18) — 4 exclude 옵션
다음 단계 후보:
  (a) Market Discovery 기본 조회 기준 설정 UI (BACKLOG, 본 STEP 신규)
  (b) AI 투자세션 복사용 문구 / Data Status 실제 연결 / decision evidence (기존 BACKLOG)
```

### 본 STEP 요약

- **방향**: 기존 일간 / 1개월 / 3개월 분리 표 (3개) → **단일 통합 후보 테이블** (1개).
  각 row 에 3 기간 수익률을 모두 표시. 사용자는 상단 `basis selector` 로 정렬 기준
  (`daily / one_month / three_month`) 선택.
- **기본 조회 기준**: `one_month` (1개월 모멘텀). 추후 운영 중 변경 가능 — 설정 UI 는
  본 STEP 에서 만들지 않음 (BACKLOG).
- **Backend**:
  - `GET /market/topn/latest` 에 `basis` query param 추가 — FastAPI Literal
    (`daily / one_month / three_month`) 로 검증. invalid 는 422 응답.
  - 응답에 `candidates: list[MarketCandidate]` 배열 추가. 각 entry 는:
    `rank / ticker / name / tags / selected_return_pct / selected_basis_start_date /
    selected_basis_end_date / returns: {daily, one_month, three_month}`.
  - TOP N 산출 순서 (지시문 §6):
    1. SQLite 산출 가능 후보 전체 → 2. 3 기간 수익률 모두 계산 → 3. 태깅 → 4. exclude 적용 →
    5. selected basis 의 return 이 None 인 후보 제외 → 6. selected basis 내림차순 정렬 →
    7. TOP N → 8. rank 재부여.
  - 기존 `daily_topn / one_month_topn / three_month_topn` 배열은 호환용으로 응답에 유지
    (frontend 미사용).
- **Frontend**:
  - `CandidateTable` 컴포넌트 — 8 컬럼 (순위 / 티커 / ETF명 / 일간 / 1개월 / 3개월 /
    정렬 기준 기간 / 태그). 선택된 basis 컬럼은 헤더 + 셀 모두 강조 (`.basis-active`).
    태그 컬럼은 별도 표시 (검증자 A-1 NOTE 반영 후 FIX — ETF명 셀 안 배지에서 별도 컬럼으로
    이동).
  - `BasisSelector` 컴포넌트 — 3 버튼 (`일간 급등 / 1개월 모멘텀 / 3개월 추세`).
    기본 선택 = `1개월 모멘텀`. 활성 버튼은 `.basis-btn-active`.
  - `MarketDiscoveryView` 에 `basis` state 추가. 변경 시 GET 재호출.
  - 후보 정제 4 체크박스 유지.
  - 기존 3개 `TopNTable` 호출 제거 → 1개 `CandidateTable` 로 통합.
- **레이아웃**: `.app-content` 기본 max-width `960px` 유지. Market Discovery 화면에서만
  `MainPanel` 이 `app-content--wide` 클래스를 부착하여 `max-width: 1400px` 적용.
  Dashboard / Holdings / Approval / Data Status 는 영향 없음 (검증자 NOTE 반영 후 FIX).
- **운영 1회 검증 (uvicorn + curl)**:
  - default `basis=one_month`: candidates 1위 = 139260 TIGER 200 IT (1m +49.87%,
    3m +82.05%). 각 candidate 에 3 기간 returns 모두 노출.
  - `basis=daily`: 정렬 기준 변경, 1위 = 0183J0 TIGER 미국우주테크 (daily +5.42%).
  - `basis=weekly` (invalid) → HTTP 422 (FastAPI Literal 가드 작동).
- **검증**: pytest 231 passed (223 → +8 신규). black PASS / flake8 PASS / frontend lint+build PASS.
- **KS-10**: trigger 0 / near 0. backend max 564 (기존) / 테스트 max 924 (기존) /
  프론트 max 705 (MarketDiscoveryView.tsx 본 STEP — trigger 900 / near 850 미달).

### 신규 / 수정 파일

수정:
- `app/market_topn.py` — `compute_topn` 의 `basis` 파라미터 + `candidates` 빌드 로직 +
  per-ticker returns 캐시. `ALLOWED_BASIS` / `DEFAULT_BASIS` 상수.
- `app/api_market_topn.py` — `BasisLiteral` (FastAPI Literal) + 신규 응답 model
  (`MarketPeriodReturn / MarketReturns / MarketCandidate`) + endpoint 시그니처 확장.
- `frontend/lib/api.ts` — `MarketBasis` 타입 + `MarketCandidate` / `MarketReturns` /
  `MarketPeriodReturn` / `DEFAULT_MARKET_BASIS` / `MARKET_BASIS_LABEL` +
  `fetchMarketTopnLatest(n, options.basis)`.
- `frontend/app/components/MarketDiscoveryView.tsx` — 3 TopNTable → 1 CandidateTable +
  BasisSelector + basis state + 통합 렌더.
- `frontend/app/globals.css` — `.market-candidate-table .basis-active` + `.basis-btn-active`
  + `app-content max-width: 960px → 1400px`.
- `tests/test_market_topn.py` — 8 신규 테스트 (default basis / 정렬 / candidates
  3 returns / selected_basis dates / invalid fallback / rank 재부여 / missing basis 제외).
- `docs/handoff/STATE_LATEST.md` — 본 §0 갱신.
- `docs/backlog/BACKLOG.md` — "Market Discovery 기본 조회 기준 설정 UI" 항목 신규.

### 이번 STEP 에서 의도적으로 하지 않은 것

- Settings 화면 / TOP N 설정 UI / 기본 조회 기준 설정 UI (BACKLOG).
- 컬럼 클릭 정렬 / 시가총액·거래량 정렬.
- 섹터 자동 분류 / 구성 종목 추출 / AI 투자세션 복사용 문구.
- ML / OCI / 매수·매도 판단 / 점수 산식 / 백테스트 / Data Status 상세 연결.

---

## 0.1 직전 상태 — 2026-05-18 Market Discovery 후보 정제 1차

```text
현재 단계: Market Discovery 후보 정제 1차 (2026-05-18) — 일반 후보 기본 표시 + 특수상품 제외 옵션
이전 단계: Market Discovery SQLite Direct Refresh (2026-05-18 동일자)
다음 단계 후보:
  (a) AI 투자세션 복사용 문구 / Data Status 실제 연결 / decision evidence (기존 BACKLOG)
  (b) 사용자 결정 — 섹터 자동 분류 / TOP N 설정 UI / 구성 종목 추출 등
```

### 본 STEP 요약

- **방향**: Market Discovery TOP N 결과에 ETF 이름 기반 상품 태그를 붙이고, 기본 화면은
  인버스 / 레버리지 / 합성 / 선물형 ETF 를 제외한 일반 후보 TOP N 만 표시.
- **필터링 순서 (지시문 §3.1)**: SQLite 산출 가능 후보 전체 → 태깅 → exclude 옵션 적용 →
  정렬 → TOP N 자르기 → rank 재부여. **filter-before-limit**. SQLite 에서 먼저 TOP N
  자른 뒤 필터링하는 방식은 금지 (필터 후 N 미만 회피).
- **태깅 규칙 (이름 기반)**:
  - `인버스` → `inverse`
  - `레버리지` / `2X` (대/소문자 무시) / `2배` → `leveraged`
  - `합성` → `synthetic`
  - `선물` → `futures`
  - 한 ETF 에 multi-tag 가능 (예: `TIGER 차이나전기차레버리지(합성)` → `[leveraged, synthetic]`).
  - 금현물 / 배당 / 반도체 / AI / 조선 / 방산 / 원자재 등은 분류하지 않음.
- **Backend**:
  - `GET /market/topn/latest` 에 4 query param 추가 (모두 default true):
    `exclude_inverse / exclude_leveraged / exclude_synthetic / exclude_futures`.
  - 응답 entry 에 `tags: list[str]` 추가.
  - 응답 최상위에 `filters` (활성 필터) + `filter_exclusions` (기간별 태그별 제외 카운트) 추가.
  - `compute_topn` 의 단일 sort 를 `_topn_with_filter` 로 교체 — 태깅된 후보를 필터링 후 정렬.
  - **원본 SQLite 데이터는 변경 0** (테스트 `test_compute_topn_does_not_modify_raw_sqlite` 가드).
- **Frontend**:
  - `MarketDiscoveryView` 상단에 후보 정제 카드 — 4 체크박스 (모두 기본 체크).
  - 체크 변경 시 GET `/market/topn/latest?...` 재호출.
  - 각 TOP N 행에 `TagBadges` — `인버스 / 레버리지 / 합성 / 선물형` 한글 라벨로 색상 칩 표시.
  - **전체보기 버튼 미생성** (지시문 §11 명시).
- **운영 1회 검증 (uvicorn + curl, SQLite asof=2026-05-15)**:
  - default 요청 → universe 1107, daily TOP 5 모두 일반 ETF, `filter_exclusions.daily =
    {inverse: 40, leveraged: 56, synthetic: 100, futures: 81}`.
  - `exclude_leveraged=false` 요청 → 레버리지 다시 포함 가능 (filters 응답에 반영).
- **검증**: pytest 223 passed (211 → +12). black PASS / flake8 PASS / frontend lint+build PASS.
- **KS-10**: trigger 0 / near 0.

### 신규 / 수정 파일

수정:
- `app/market_topn.py` — `classify_etf_tags()` + `PRODUCT_TAG_TYPES` + `compute_topn`
  의 4 exclude 파라미터 + filter-before-limit 로직 (`_topn_with_filter`) +
  응답에 `filters` / `filter_exclusions` 추가.
- `app/api_market_topn.py` — `GET /market/topn/latest` 에 4 query param + entry `tags` 필드 +
  응답 model 에 `MarketTopNFilters` / `filter_exclusions`.
- `frontend/lib/api.ts` — `MarketProductTag` / `MarketTopNFilters` / `MarketTopNFilterOptions` /
  `DEFAULT_MARKET_TOPN_FILTERS` + `fetchMarketTopnLatest(n, options)` 시그니처 확장.
- `frontend/app/components/MarketDiscoveryView.tsx` — `FilterCard` 추가 + `TagBadges` +
  filter state + 체크 변경 시 재호출.
- `frontend/app/globals.css` — `.market-topn-filter-row` + `.market-topn-tag.*` 4 색상 변형 추가.
- `tests/test_market_topn.py` — 12 신규 테스트 (태깅 5건, filter-before-limit / default exclude /
  opt-in / multi-tag count / entries.tags / raw SQLite 미변경).
- `docs/handoff/STATE_LATEST.md` — 본 §0 갱신.

### 이번 STEP 에서 의도적으로 하지 않은 것

- 전체보기 버튼 / 섹터 자동 분류 / 구성 종목 추출 / AI 투자세션 복사용 문구.
- ML / OCI / 매수·매도 판단 / 점수 산식 / 백테스트 / Settings / TOP N 설정 UI.
- 원본 SQLite 데이터 변경 (필터링은 read-only 변환 — DB 미변경 가드 테스트 포함).

---

## 0.1 직전 상태 — 2026-05-18 Market Discovery SQLite Direct Refresh

```text
현재 단계: Market Discovery 의 시장 데이터 기준을 JSON artifact → SQLite 로 단일화 (2026-05-18)
이전 단계: PC Market Discovery TOP N 최소 표시 (artifact 기반, 2026-05-17)
다음 단계 후보:
  (a) refresh running 상태 서버 재시작 복구 (BACKLOG)
  (b) AI 투자세션 복사용 문구 / 레버리지·인버스 필터 / Data Status 실제 연결 / decision evidence (기존 BACKLOG)
  (c) KRX OPEN API fallback 검증
```

### 본 STEP 요약

- **시장 데이터 SSOT 전환** — JSON artifact (`state/market/etf_universe_topn_latest.json`)
  → SQLite (`state/market/market_data.sqlite`) 단일.
  - artifact 파일 로컬 삭제.
  - `.gitignore` 에서 해당 파일 entry 제거 (SQLite 패턴만 유지).
  - 코드 참조 0건 (`tests/test_market_topn_api.py::test_no_etf_universe_topn_latest_json_path_in_code` 가드).
- **Backend (3 endpoints)**:
  - `GET /market/topn/latest` (수정) — SQLite 직접 계산. `?n=` query param 추가.
    응답 status `ok | missing | empty | invalid` + `latest_refresh` + `period_exclusions`.
  - `POST /market/refresh` (신규) — FDR 수집을 background thread 로 실행 (ETF universe
    + 가격). single-flight + 6h cooldown 가드. JSON artifact 생성 0건.
  - `GET /market/refresh/status` (신규) — in-memory state + cooldown remaining 반환.
  - **namespace 결정** (2026-05-18, 설계자 직접 확인 후 환원):
    · 초안 1차에서 기존 holdings naver 시세 갱신 endpoint (`POST /market/refresh`)
      와 경로 충돌 → 본 STEP 의 새 endpoint 를 자체로 `/market/topn/*` 로 변경했다가
      설계자 검토에서 기각.
    · FIX 라운드 (2026-05-18) — 본 STEP 의 새 endpoint 를 지시문 그대로 `/market/refresh`
      / `/market/refresh/status` 로 환원. 기존 holdings naver 시세 endpoint 는
      `POST /holdings/market/refresh` 로 이동 (의미 namespace 분리, backward
      compatibility alias 미제공).
- **Frontend**:
  - `lib/api.ts` — `fetchMarketTopnLatest(n)`, `postMarketRefresh()`, `fetchMarketRefreshStatus()` + 타입.
  - `MarketDiscoveryView` — "최신 시장 데이터 갱신" 버튼 + status polling
    (idle / starting / running / completed / failed / cooldown 6 UI 상태).
    "SQLite 에 저장된 시장 데이터 기준" 라벨 명시.
  - 결측 필드는 `-` 표시 (0% 보정 금지 — 검증자 NOTE 반영).
- **결측 처리 (지시문 §6)**:
  - 결측 데이터 0% 보정 금지. `period_exclusions` 로 5 reason 분류 집계
    (`missing_latest_price` / `missing_base_price` / `insufficient_history` /
    `invalid_price` / `stale_price`).
- **KS-11 문서 정합성 보정**:
  - `PROJECT_ORIGIN_INTENT.md §10 #2` — "JSON SSOT 유지" → "데이터 종류별 SSOT 분리"
    (시장 데이터 = SQLite, 운영 상태 = JSON).
  - `ASSUMPTIONS.md A-2` — REOPENED → ANSWERED (재정리). 시장 데이터 SQLite 기록.
  - `STATE_LATEST.md` 본 §0 갱신.
  - `BACKLOG.md` — "refresh running 상태 서버 재시작 복구" 신규 등록.
- **검증**: pytest 211 passed (200 → +11). black PASS / flake8 PASS / frontend lint + build PASS.
- **운영 1회 검증**: `uvicorn + curl` 로 `GET /market/topn/latest` 응답 `status=ok`,
  `universe=1107`, `?n=3` 도 정상. `GET /market/refresh/status` 는 `idle` 응답.
- **KS-10**: trigger 0 / near 0.

### 신규 / 수정 파일

신규:
- `app/market_refresh_service.py` (single-flight + 6h cooldown + background thread).
- 테스트 — 본 STEP 에서는 기존 2 테스트 파일 (test_market_topn.py / test_market_topn_api.py) 을
  재작성. 새 파일 추가는 0건.

수정:
- `app/market_topn.py` — artifact 함수 폐기 (save_topn_artifact / compute_and_save_topn / DEFAULT_TOPN_PATH 제거).
  status 분기 + latest_refresh + period_exclusions + `_compute_period` 3-way reason 추가.
- `app/api_market_topn.py` — read_topn_artifact 폐기 → compute_topn() 호출 + 2 신규 endpoint.
- `frontend/lib/api.ts` — TOP N response schema 확장 + refresh / status API 추가.
- `frontend/app/components/MarketDiscoveryView.tsx` — refresh 버튼 + polling + SQLite 기준 라벨.
- `tests/test_market_topn.py` — artifact 테스트 폐기, status / period_exclusions / 결측 처리 추가.
- `tests/test_market_topn_api.py` — artifact 기반 폐기, SQLite + refresh + status + cooldown + single-flight 추가.
- `.gitignore` — `etf_universe_topn_latest.json` entry 제거.
- `docs/PROJECT_ORIGIN_INTENT.md §10 #2` — SSOT 분리 정정.
- `docs/ASSUMPTIONS.md A-2` — REOPENED → ANSWERED 재정리.
- `docs/handoff/STATE_LATEST.md` — §0 갱신.
- `docs/backlog/BACKLOG.md` — refresh running 재시작 복구 신규.

### 이번 STEP 에서 의도적으로 하지 않은 것

- 레버리지 / 인버스 / 합성 ETF 필터 (BACKLOG).
- AI 투자세션 복사용 문구.
- Data Status 상세 연결 (placeholder 유지).
- 구성 종목 추출 / ML 연결 / OCI 자동 PUSH 연결 / 매수·매도 판단 / 차트 / Settings UI / TOP N 설정 UI.
- cron / scheduler / refresh 자동 실행.
- decision evidence 저장.
- 서버 재시작 시 running 상태 복구 (BACKLOG).

---

## 0.1 직전 상태 — 2026-05-17 PC Market Discovery TOP N 최소 표시 완료

```text
현재 단계: PC Market Discovery TOP N 최소 표시 완료 (2026-05-17)
이전 단계: PC UI Shell 1차 완료 (2026-05-17) — 좌측 메뉴 + 5 View 분리
다음 단계 후보:
  (a) AI 투자세션 복사용 문구 생성 (BACKLOG)
  (b) 레버리지 / 인버스 / 합성 ETF 필터 정책 (BACKLOG)
  (c) Data Status 실제 연결 (read-only refresh-log API + view) (BACKLOG)
  (d) decision evidence 별도 STEP
  (e) KRX OPEN API fallback 검증 (인증키 승인 후)
```

### 본 STEP 요약

- **방향**: 이미 생성된 `state/market/etf_universe_topn_latest.json` artifact 를 PC
  Market Discovery 메뉴에서 표 형태로 보여준다. 새 데이터 수집은 일으키지 않는다.
- **Backend**: `GET /market/topn/latest` read-only API 1개 신규 — artifact 파일만
  읽는다. SQLite 직접 조회 / FDR 호출 / refresh / TOP N 재계산 0건.
  - 응답 status: `ok` / `missing` / `invalid` 3분기. 모두 HTTP 200 정상 응답.
  - 신규 모듈: `app/api_market_topn.py` (161라인) — APIRouter 패턴.
  - `app/api.py` 에 `market_topn_router` include 만 추가 (+2라인).
- **Frontend**:
  - `frontend/lib/api.ts` (363→399) — `fetchMarketTopnLatest()` + `MarketTopNResponse` /
    `MarketTopNEntry` 타입.
  - `MarketDiscoveryView.tsx` (38→207) — 요약 헤더 + 일간/1개월/3개월 TOP N 3 표.
    loading / error / ok / missing / invalid 5 상태 처리.
  - `DashboardView.tsx` (84→157) — Market Discovery 데이터 상태 카드 추가.
    데이터 존재 여부 (`ok` / `missing` / `invalid` / 확인 실패) 만 노출, TOP N 상세표는
    절대 두지 않음 (지시문 §3.3 / AC-8).
  - `globals.css` (798→834) — TOP N 표 스타일 추가.
- **운영 실측**: 로컬 uvicorn + curl 로 `GET /market/topn/latest` 검증 — `status=ok`,
  `universe_count=1107`, daily TOP 1 = `491630 RISE 미국반도체인버스(합성 H) +4.89%`.
- **금지 회피** (지시문 §6 / AC-9):
  - 새 데이터 수집 / FDR refresh / SQLite 직접 조회 화면 / TOP N 재계산 0건.
  - 차트 / 필터·정렬 고도화 / 레버리지·인버스·합성 ETF 임의 제외 0건.
  - AI 투자세션 복사용 문구 / 구성 종목 추출 / ML / OCI / Telegram / 매수·매도 판단 0건.
  - backend 기존 구조 변경 0건 (api.py 의 router include 1줄 추가만).
- **테스트**: pytest 200 passed (191 → +9 신규). 본 STEP 신규 9 tests 매핑:
  - artifact ok / missing / invalid (broken JSON) / invalid (missing keys) — 4 tests.
  - endpoint ok / missing / invalid — 3 tests.
  - FDR refresh 호출 0 / SQLite 직접 조회 0 — 2 tests.
- **KS-10**: trigger 0 / near 0. 본 STEP 신규/수정 모두 안전 범위.

### 신규 / 수정 파일

신규:
- `app/api_market_topn.py` (161라인) — read-only TOP N artifact router.
- `tests/test_market_topn_api.py` (263라인) — 9 tests.

수정:
- `app/api.py` (497→499라인) — router include 1줄 + import 1줄.
- `frontend/lib/api.ts` (363→399라인) — `fetchMarketTopnLatest()` + 타입.
- `frontend/app/components/MarketDiscoveryView.tsx` (38→207라인) — placeholder → 3 TOP N 표.
- `frontend/app/components/DashboardView.tsx` (84→157라인) — Market Discovery 상태 카드.
- `frontend/app/globals.css` (798→836라인) — TOP N 표 스타일.
- `docs/handoff/STATE_LATEST.md` — §0 갱신 (본 STEP), 이전 §0 은 §0.1 격하.
- `docs/backlog/BACKLOG.md` — "PC Market Discovery TOP N 최소 표시 후 신규" 섹션 신규.
  AI 투자세션 복사용 문구 / 레버리지·인버스·합성 필터 정책 / Data Status 실제 연결 3건.

### 이번 STEP 에서 의도적으로 하지 않은 것

- 새 데이터 수집 실행 버튼 / FDR refresh / SQLite 직접 조회 화면 / TOP N 재계산.
- 차트 / 필터 / 정렬 고도화 / 임의 ETF 제외 정책.
- AI 투자세션 복사용 문구 자동 생성 / 구성 종목 추출 / 매수·매도 판단.
- ML 연결 / OCI 일 3회 PUSH 연결 / Telegram 문구 변경.
- Dashboard 에 TOP N 상세표 추가 (Dashboard 는 상태 요약 + 이동 버튼만).

---

## 0.1 직전 상태 — 2026-05-17 PC UI Shell 1차 완료

```text
현재 단계: PC UI Shell 1차 완료 (2026-05-17) — 좌측 메뉴 + 5 View 분리
이전 단계: FDR + SQLite Market Data Foundation 1차 구현 완료 (2026-05-15)
다음 단계 후보:
  (a) Market Discovery TOP N 상세표 구현 — SQLite artifact → UI 연결
  (b) Data Status 화면에 SQLite refresh 상태 연결 (API 신설 필요)
  (c) decision evidence 별도 STEP
  (d) KRX OPEN API fallback 검증 (인증키 승인 후)
```

### 본 STEP 요약

- **방향**: 기존 POC 단일 화면 (HoldingsClient + UniverseRefreshPanel + RunPanel +
  SampleDraft 가 모두 섞여 있던 구조) 을 **좌측 메뉴 기반 5 View 구조** 로 분리.
- **라우팅**: App Router 디렉토리 분기 미사용 — `MainPanel` 의 클라이언트 상태
  (`active: MenuKey`) 로 view 전환. 지시문 §3.1 "메뉴 폴더 구조 만들지 않음" 준수.
- **5 메뉴**: Dashboard (기본 화면) / Market Discovery (placeholder) / Holdings /
  Approval & Telegram / Data Status (placeholder).
- **승인 전/후 용어 분리** (지시문 §3.5, 검증자 NOTE 반영 후 3-way 분류):
  - `classifyApprovalPhase(status)` → `"pending" | "delivered" | "terminated"`.
  - `pending` (PENDING_APPROVAL) → "승인 대기 메시지 초안".
  - `delivered` (DELIVERING / COMPLETED) → "Telegram 발송 결과 — 발송 완료 메시지".
  - `terminated` (REJECTED / FAILED) → "거절 / 실패된 메시지 초안 (Telegram 미발송)".
  - RunPanel §3 헤더 + MessagePreview header + ApprovalTelegramView 안내 +
    LEGACY_FALLBACK_NOTICE 모두 본 phase 분류 적용.
  - "PUSH 메시지" / "발송 메시지" 표현 사용 0건 (주석 포함 grep 검증).
- **신규 컴포넌트 6 + 수정 3**:
  - 신규: `LeftSidebar.tsx` (65) / `DashboardView.tsx` (84) / `MarketDiscoveryView.tsx`
    (38) / `HoldingsView.tsx` (32) / `ApprovalTelegramView.tsx` (78) /
    `DataStatusView.tsx` (37).
  - 수정: `MainPanel.tsx` (69→64, 재구성) / `RunPanel.tsx` (444→486, 용어 3-way 분류) /
    `globals.css` (691→798, sidebar 레이아웃).
- **금지 회피** (지시문 §5): 신규 API 0건 / Telegram 문구 변경 0건 / SQLite 조회 API
  0건 / TOP N 상세 화면 0건 / 차트 0건 / 매수·매도 판단 0건 / ML 연결 0건 / OCI
  연결 0건 / 모바일 UI 0건 / backend 변경 0건.
- **자동 메뉴 전환**: HoldingsClient 가 draft 를 생성하면 ApprovalTelegramView 로
  자동 이동 — 기존 단일 페이지에서 즉시 노출되던 운영 동작 보존 (AC-11).
- **검증**: pytest 191 passed / black PASS / flake8 PASS / frontend lint PASS /
  frontend build PASS / dev server SSR 5 메뉴 렌더링 확인.
- **KS-10**: trigger 0 / near 0. 신규 6 컴포넌트 모두 84라인 이하. RunPanel 468라인
  (기존 444 + 24 — 용어 동적 전환). globals.css 798 (CSS 는 임계 대상 아님).

### 신규 / 수정 파일

신규 (Frontend, 라인 수 실측):
- `frontend/app/components/LeftSidebar.tsx` (65라인) — 5 메뉴 sidebar.
- `frontend/app/components/DashboardView.tsx` (84라인) — 시스템 상태 + 바로가기 카드.
- `frontend/app/components/MarketDiscoveryView.tsx` (38라인) — placeholder.
- `frontend/app/components/HoldingsView.tsx` (32라인) — HoldingsClient 래퍼.
- `frontend/app/components/ApprovalTelegramView.tsx` (78라인) — RunPanel + UniverseRefresh
  + SampleDraft 호스팅 + 승인 전/후 용어 명시.
- `frontend/app/components/DataStatusView.tsx` (37라인) — placeholder.

수정:
- `frontend/app/components/MainPanel.tsx` — 좌측 메뉴 + view 라우터로 재구성.
  run state 보유 + draft 생성 시 자동 메뉴 전환.
- `frontend/app/components/RunPanel.tsx` — §3 헤더 status 기반 동적
  (PENDING → "승인 대기 메시지 초안", 그 외 → "Telegram 발송 결과") +
  MessagePreview header dynamic + LEGACY_FALLBACK_NOTICE 정정.
- `frontend/app/globals.css` — sidebar/menu/dashboard/placeholder 스타일 추가.

### 이번 STEP 에서 의도적으로 하지 않은 것

- TOP N 상세표 (Market Discovery placeholder).
- SQLite 조회 API / 실시간 refresh 버튼 (Data Status placeholder).
- AI 투자세션 / 매수·매도 판단 / 차트 / 시장 국면 표시.
- backend 변경 (lint 가드 / 데이터 계약 / Telegram / OCI / ML 모두 손 안 댐).
- 모바일 UI / 신규 라우트 / 신규 API.

---

## 0.1 직전 상태 — 2026-05-15 FDR + SQLite Market Data Foundation 1차 구현 완료

```text
현재 단계: FDR + SQLite Market Data Foundation 1차 구현 완료 (2026-05-15)
이전 단계: 가능성 확인 STEPs — pykrx 1.0.51 / 1.2.8 / KRX 인증 (FAIL) → FDR (PASS)
다음 단계 후보: (a) PC ETF Universe TOP N 화면 구현, (b) decision evidence 별도 STEP,
              (c) KRX OPEN API fallback 검증 (인증키 승인 후)
```

### 본 STEP 요약

- **방향**: B 방향 PC 작업 1~2단계 (한국 상장 ETF 전체 universe 조회 → 일간/1개월/3개월
  TOP N 산출) 의 데이터 기반 구축. UI 단계는 본 STEP 의 대상 아님.
- **1순위 데이터 소스**: FinanceDataReader 채택 (가능성 확인 PASS — 2026-05-15).
  `StockListing("ETF/KR")` 단일 호출로 1,107개 ETF universe + Name + Category + 현재가
  + 거래량 + 시가총액 한 번에 확보.
- **저장소**: SQLite (`state/market/market_data.sqlite`) — 3 테이블만 도입.
- **신규 모듈 3개**:
  - `app/market_data_store.py` — SQLite 스키마 + upsert (etf_master / etf_daily_price /
    market_refresh_log).
  - `app/market_data_fdr.py` — FDR universe + price fetch 래퍼. 테스트는 stub 으로
    monkeypatch.
  - `app/market_topn.py` — SQLite 가격 데이터 기준 일간/1개월/3개월 TOP N + JSON artifact.
- **N+1 호출 금지 가드**: `refresh_etf_universe` 는 `StockListing("ETF/KR")` 단일 호출
  결과만 etf_master 에 저장. ticker 별 추가 가격 호출은 본 함수 안에서 발생 0건 —
  테스트가 이를 명시 검증.
- **금지 사항 (본 STEP 에서 명시 회피)**:
  · `decision_evidence` 테이블 신설 / writer 연결 — BACKLOG.
  · AI 투자세션 / 사용자 매매 판단 / approval / Telegram / Run 상태 저장 — 본 저장소
    책임 아님.
  · PC UI 화면 구현 / API 추가 / Telegram 변경 / OCI 일 3회 PUSH 연결 / ML 연결.
  · etf_master 의 ticker 별 N+1 보강 호출.
- **검증**: pytest 191 passed (이전 173 + 신규 18 — store 6 / fdr 6 / topn 6).
- **의존성 변화**: `finance-datareader>=0.9.202` 추가. **pandas 2.3.3 유지** (메이저
  업그레이드 발생 안 함 — R2 위험 해소).
- **artifact**: `state/market/etf_universe_topn_latest.json` — 1회 운영 fetch 시 생성.

### 신규 / 수정 파일

신규 (코드, black 적용 후 실측):
- `app/market_data_store.py` (332라인) — SQLite DDL + upsert + log + helpers.
- `app/market_data_fdr.py` (300라인) — FDR universe / price wrapper + refresh_log.
- `app/market_topn.py` (206라인) — daily / 1m / 3m TOP N 산출 + artifact.
- `tests/test_market_data_store.py` (224라인) — 6 tests.
- `tests/test_market_data_fdr.py` (214라인) — 6 tests.
- `tests/test_market_topn.py` (193라인) — 6 tests.

KS-10 임계 (실측):
- 백엔드 max 564 (app/draft_message.py, 기존) — trigger 650 / near 600 미달.
- 테스트 max 924 (test_holdings_message_text.py, 기존) — trigger 1500 / near 1450 미달.
- 프론트 max 515 (EnrichedHoldingsSection.tsx, 기존) — trigger 900 / near 850 미달.
- 본 STEP 신규 6개 파일 모두 안전 범위 (백엔드 max 332 / 테스트 max 224).

수정:
- `requirements.txt` — `finance-datareader>=0.9.202` 추가.
- `docs/PROJECT_ORIGIN_INTENT.md` §8 — FDR / SQLite 자산 추가, pykrx universe 폐기 명시.
- `docs/backlog/BACKLOG.md` — decision evidence + FDR 약관 + Category 라벨 + SQLite
  영구 보존 정책 4건 신규 등록.
- `.gitignore` — SQLite 바이너리 / 자동 생성 artifact 운영 위생.

### 가능성 확인 STEP 결과 흐름 (2026-05-15 동일자 누적)

1. pykrx 1.0.51 ETF universe — FAIL.
2. pykrx 1.2.8 ETF universe — FAIL (KRX 인증 요구 메시지 발견).
3. pykrx 1.2.8 + KRX_ID/KRX_PW 인증 — FAIL (KRX 서버 거부).
4. FinanceDataReader — **PASS** (1,107 ETF / 234초 / 76.1% 가격 데이터 성공률).
5. 본 STEP — FDR + SQLite 구현 1차 완료.

---

## 0.1 직전 상태 (2026-05-14 B 방향 전환)

```text
현재 단계: B 방향 전환 직후 (2026-05-14) — PC 작업 1~2단계 가능성 확인 진입 전
이전 단계: POC2-Step8 운영 검증 중단 (사용자 결정, 2026-05-14)
다음 단계: PC 작업 1단계 — pykrx 가능성 확인 (코드 변경 전 가능성 검토)
```

### 방향 결정

- **A 기각**: 기존 Telegram PUSH 운영 검증을 메인 경로로 계속 끌고가는 방향은 기각.
- **B 채택**: 원래 PROJECT_ORIGIN_INTENT §2 목표로 회귀.
  - 잘 올라가는 섹터/테마 발굴 → AI 와 토론/판단.
  - 상황별 factor 부착 ML 판단 시스템.
  - 투자 초보자 단계에서 벗어나 사용자에게 맞는 투자 형태 발견.

### 핵심 목표 (B 방향)

1. **섹터/테마 발굴** — 한국 상장 ETF universe 기반 정량 발굴.
2. **AI 투자세션 시스템 내재화** — 발굴 후보를 AI 와 함께 해석하는 흐름을
   시스템 안에서 다룬다.
3. **ML 연결 검토** — 발굴 + AI 토론 흐름이 정착한 뒤 ML 모듈 연결 여부를 별도 판단.

### 기존 자산 처리 (3분류)

**살릴 것 (B 방향 메인 경로의 1차 후보)**:
- pykrx 가격 조회 배관 (`app/price_history_pykrx.py`).
- universe refresh 배관 (`app/universe_refresh.py`).
- PROJECT_ORIGIN_INTENT 의 §2 / §4 / §5 / §10 (불변 앵커 유지).
- KILL_SWITCHES + ASSUMPTIONS + BACKLOG 운영 가드 구조.

**보조로 남길 것 (메인 경로 아님, 보존만)**:
- 3-PUSH 배관 (PUSH 1 / PUSH 2 / PUSH 3) — Step7 시리즈 산출물.
- Telegram 발송 경로 — 보조 알림 채널.
- 승인 초안 UI (`HoldingsClient`, `UniverseRefreshPanel` 등) — PC 작업 정착
  전까지 보조 화면.
- OCI handoff 배관 — 일 3회 자동 PUSH 흐름 연결은 PC 작업 정착 후.

**중단·격하 (B 방향 메인 경로에서 제외)**:
- POC2-Step8 3-PUSH First Operational Cycle Validation 운영 검증 — 중단.
- 3-PUSH 를 메인 의사결정 입력으로 사용하는 운영 시나리오 — 격하.
- "1일 3회 PC 분석 (장초/점심/장마감 전)" 운영 빈도 정의 — 격하.
  · §7 운영 원칙이 "PC 작업 주 2회 예상 + OCI 작업 일 3회 자동 PUSH" 로 갱신됨.

### 전체 흐름 12단계 (B 방향)

**PC 작업 (1~7단계 — 사용자 발굴/판단)**:

1. universe 갱신 — pykrx 로 한국 상장 ETF universe / 수익률 산출.
2. TOP N 후보 산출 — 일간 / 1개월 / 3개월 수익률 기준. N 값 가변.
3. 후보 해석 — PC 화면에서 후보 검토.
4. AI 투자세션 토론 — 후보를 AI 와 함께 해석.
5. 매매 결정 또는 보류 — 명시적 결정.
6. 결정 기록 — 사유 누적 (운영 데이터).
7. 다음 PC 작업 시점 결정.

**OCI 작업 (8~11단계 — 자동 보조 알림)**:

8. 보유 종목 상태 브리핑 (보조 PUSH 1) — 일 3회.
9. 신규 ETF 관찰 후보 (보조 PUSH 2) — 일 3회.
10. 급락 ETF 주의 신호 (보조 PUSH 3) — 일 3회.
11. 알림 수신 후 사용자가 PC 작업으로 넘어갈지 판단.

**모바일 UI (12단계 — 후순위)**:

12. 모바일 UI — PC 작업 1~7단계 + OCI 작업 8~11단계가 충분히 검증된 뒤 다룬다.
    현재 단계의 작업 대상 아님.

### 현재 위치

- PC 작업 1~2단계 진입 **전** — 가능성 확인 단계.
- 다음 작업은 새 기능 구현이 아니라 **pykrx 가능성 확인**:
  1. pykrx 로 한국 상장 ETF 전체 universe 조회 가능 여부.
  2. ETF 별 일간 / 1개월 / 3개월 수익률 계산 가능 여부.
  3. 수익률 기준 TOP N 산출 가능 여부.
- 위 1~3 가능성 확인 결과에 따라 PC 작업 1단계의 형태가 확정된다.

### 다음 작업

- 위 가능성 확인 1~3 항목을 코드 변경 없이 검토 (기존 `price_history_pykrx.py` /
  `universe_refresh.py` 의 한계 확인).
- 가능성 확인 결과 정리 후 PC 작업 1단계 진입 여부 결정.
- 출력 정의 (PROJECT_ORIGIN_INTENT §3) 는 가능성 확인 이후 확정.

### 이번에 하지 않는 것

- 구성 종목 추출 (ETF 구성 종목 분해).
- 정적 데이터 화면 (단순 표시 화면 추가).
- AI 투자세션 자동화 (AI 가 자동으로 매매 의견 생성).
- ML 연결 (predictive_risk_classifier 자동 연결).
- OCI 일 3회 자동 PUSH script 연결 (PC 작업 정착 전).
- 모바일 UI (12단계 후순위).
- 새 step box 분기.
- BACKLOG 대규모 재작성.
- 3-PUSH 배관 삭제 또는 disable.

---

## 1. 직전 상태 (POC2-Step8 진입 — 2026-05-13, B 방향 전환으로 중단)

```text
현재 단계: POC2-Step8 진입 (2026-05-13) — 3-PUSH First Operational Cycle Validation (운영 검증 단계, 코드 변경 0)
다음 단계: 운영 사이클 3회 이상 또는 조기 종료 또는 첫 의사결정 도달까지 운영 기록 누적
```

POC2-Step8 진입 요약 (본 STEP):
- **성격**: 기능 개발 / 코드 변경 단계가 아닌 **문서 + 운영 검증 단계**.
- **3-PUSH 최소 운영 구조 완성 (Step7 시리즈 종결)** 후 첫 운영 사이클 검증.
- **단일 목표**: 사용자가 받은 PUSH 가 해석 가능하며 행동 또는 명시적 보류 판단으로
  이어지는지 기록.
- "행동" 정의: 매수/매도 외에도 AI 투자세션 / 보류 / 무시 / 개선 필요 / 메시지 이해
  실패 / 운영 절차 번거로움 모두 포함.

Step8 운영 로그 문서: `docs/ops/POC2_STEP8_OPERATION_LOG.md`
Step8 설계서: `docs/handoff/POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md`

Step8 완료 기준 (3가지 경로):
- **표준 완료**: 서로 다른 영업일 3회 이상 운영 기록 + AI 투자세션 1회 이상 +
  사용자 운영 가능성 명시 판단.
- **조기 종료**: 메시지 이해 불가 / 운영 번거로움 / Telegram 무가치 / 알림 빈도 부적절 /
  운영 병목 재발 — 실패 아님, 검증 결과로 기록.
- **첫 의사결정 도달** (Q5 BACKLOG 복귀 핵심 트리거): PUSH 수신 → AI 투자세션 →
  매수/매도/보류 중 하나 명시적 결정.

본 STEP 진행 동안 코드 / API / UI / Telegram / 데이터 계약 변경 0건 정책.
docs/STATE_LATEST.md 포인터 stub 본문 변경 없음.

---

## 1.1 직전 상태 (POC2-Step7C VERIFIED + Step7 시리즈 종결)

```text
이전 단계: POC2-Step7C 완료 (검증자 VERIFIED_WITH_NOTES, 2026-05-13) — 3-PUSH 모두 최소 운영 가능
Step7 시리즈 종결 commit chain:
- f6a64ead docs(poc2-step7): conclusion + next handoff for Step7 series
- 88ae8bf1 docs(poc2-step7c): address Codex NOTES — extend scope type + mark BACKLOG resolved
- d7075bfd feat(poc2-step7c): falling ETF caution signal (PUSH 3) minimal push
- 5dcb207c fix(poc2-step7b): address Codex REJECTED — remove UI placeholder + revert pointer
- 531ffbf6 feat(poc2-step7b): unify holdings status briefing (PUSH 1) bullet
- d84bc7df docs(poc2-step7a): mark VERIFIED_WITH_NOTES + record Step7 design in pointer
- 3d9112d5 feat(poc2-step7a): align label + starter seed for new ETF watch candidate
- 1c7881d9 docs(poc2-step7): save 3-Push Realignment Design (CONDITIONAL_PASS)
```

POC2-Step7C 요약 (본 STEP):
- **3-PUSH 모두 최소 구현 완료**: PUSH 1 보유 종목 상태 브리핑 (Step7B) + PUSH 2 신규
  ETF 관찰 후보 (Step7A) + PUSH 3 급락 ETF 주의 신호 (Step7C).
- **급락 ETF 주의 신호**: 기존 pykrx 1개월 수익률 재사용. score_value <= -10.0 후보를
  결정론적 tie-breaker (score ASC → ticker ASC → candidate_id ASC) 로 1건 선택.
- **신호 없음 = bullet 자체 미추가**: Telegram 에 "신호 없음" 매번 메시지 미발송 (KS-5 가드).
- **초기 기준 -10.0% 는 확정값 아님**: 코드 주석 + BACKLOG 항목으로 운영 검증 명시.
- **draft_payload 키 신설 0건**: factor_signals 안의 scope="universe_falling" signal 1건
  으로 표현 (Step7A 의 universe scope 와 동일 패턴).
- 신규 endpoint 0건. 신규 API 0건.

검증:
- pytest 159 → **173 passed** (Step7C 회귀 14개 추가).
- black / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계: 백엔드 max 564 (draft_message.py — 본 STEP 안에서 분리 작업 1회 후 복귀) /
  프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0.

신규 / 수정 파일:
신규:
- app/message_falling_etf_bullet.py (78라인) — 급락 bullet 빌더 + picker 단독 모듈
- docs/handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md
- tests/test_step7c_falling_etf_caution.py (Step7C 회귀 14개)

수정:
- app/momentum/universe_mode.py (_select_falling_candidate + _build_falling_candidate_dict + summary.falling_candidate / falling_threshold_pct)
- app/universe_refresh.py (FALLING_THRESHOLD_PCT 상수)
- app/api_universe.py (응답 summary 에 falling_candidate / falling_threshold_pct 노출)
- app/draft.py (_build_falling_etf_factor_signal — factor_signals 에 scope=universe_falling 추가)
- app/draft_message.py (3번째 bullet 통합 + 미사용 _factor_bullet / _momentum_bullet 제거)
- frontend/lib/api.ts (UniverseRefreshSummary 에 falling_candidate / falling_threshold_pct 옵셔널 추가)
- frontend/app/components/JudgmentReasonSection.tsx (pickFallingEtfCautionBullet + 3번째 bullet 렌더링)
- frontend/app/components/UniverseRefreshPanel.tsx (급락 신호 / "신호 없음" 안내 추가)

다음 단계 후보:
- 운영 빈도 문서 정합성 보정 (PROJECT_ORIGIN_INTENT §7 / Step7 §7 통합).
- 운영 사이클 1회 시작 → ASSUMPTIONS Q5 BACKLOG 복귀 트리거 데이터 수집.

---

## 1.1 직전 상태 (POC2-Step7B 완료)

```text
이전 단계: POC2-Step7B 완료 (2026-05-12) — 보유 종목 상태 브리핑 (PUSH 1) 최소 정리
```

POC2-Step7B 요약 (본 STEP):
- **[판단 사유] 통합**: 기존 별도 2 bullet ("보유 비중 영향" + "모멘텀 점검") 을 공식
  PUSH 1 명칭 **"보유 종목 상태 브리핑"** 1줄로 통합. 두 데이터 소스 (portfolio reason
  첫 문장 + holdings momentum top reason 첫 문장) 를 자연 1줄로 묶고 "이 내용은 매수/매도
  의견이 아닙니다" 중립 안내 항상 부착.
- **placeholder 사용자 노출 제거**: holdings_mode.py 의 사용자 노출 문구 ("placeholder
  기준으로 ...") 를 "현재 보유 종목 점검 기준으로 ..." 로 정정. 내부 식별자 / 함수명 /
  테스트명 / 상수 키명은 유지.
- **새 모듈 분리**: `app/message_holdings_briefing.py` 신규 (draft_message.py 의
  KS-10 trigger 해소 — 673 → 586라인). 빌더 책임 단독.
- **Frontend JudgmentReasonSection**: pickHoldingsStatusBriefing 1개로 통합. 두 별도
  picker (pickPortfolioFactorSignal / pickMomentumBullet) 사용 제거.
- 새 endpoint 미도입. 새 draft_payload 키 미도입. 데이터 계약 변경 0건.

검증:
- pytest 147 → **159 passed** (Step7B 회귀 12개 추가).
- black / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계: 백엔드 max 586 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0.

신규 / 수정 파일:
신규:
- app/message_holdings_briefing.py (110라인) — Step7B 통합 bullet 빌더 단독 책임
- docs/handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md
- tests/test_step7b_holdings_status_briefing.py (Step7B 회귀 12개)

수정:
- app/draft_message.py (Step7B 통합 + KS-10 trigger 해소)
- app/momentum/holdings_mode.py (사용자 노출 placeholder 표현 정정)
- frontend/app/components/JudgmentReasonSection.tsx (통합 picker 로 재작성)
- tests/test_factor_signals.py / test_momentum_holdings.py / test_step7a_etf_watch_candidate.py /
  test_universe_momentum_step6.py / test_universe_seed.py (Step7B 후 bullet 구조 검증 갱신)

다음 단계:
- 사용자 협의 후 후속 구현 Step 1개 선택 (한 번에 하나의 PUSH 원칙).
- 후보: PUSH 3 급락 ETF 주의 신호 최소 구현 / 운영 빈도 문서 정합성 보정.

---

## 1.1 직전 상태 (POC2-Step7A 검증 통과)

```text
이전 단계: POC2-Step7A 완료 (검증자 VERIFIED_WITH_NOTES, 2026-05-11) — 신규 ETF 관찰 후보 (PUSH 2) 최소 운영화
```

POC2-Step7A 검증 통과 commit chain:
- 3d9112d5 feat(poc2-step7a): align label + starter seed for new ETF watch candidate

검증자(Codex) 라운드 흐름:
- 1차 검증: VERIFIED_WITH_NOTES (B-6 KST 시간대 의존 NOTE 1건).
- B-6 처리: 본 STEP §5 알려진 한계로 이미 명시 + PROJECT_ORIGIN_INTENT §7 K6/EOD
  KST 전제 부합 → 수정 불필요 판정 (사유 1줄 보고).
- A-1 / A-2 / A-3 / A-4 + B-1 ~ B-5 모두 통과.
- 잔존 NOTE 는 운영 주의 수준이며 향후 timezone 도입 시 재검토.

POC2-Step7A 요약 (본 STEP):
- **명칭 정렬**: 사용자 노출 "외부 후보 점검" → 공식 PUSH 2 명칭 **"신규 ETF 관찰 후보"**
  로 정렬. 내부 함수명 / 파일명 / factor_id 는 변경 없음.
- **starter seed 도입**: seed 파일 부재 시 KODEX 200 + KODEX 미국S&P500 + KODEX
  미국나스닥100 3개 후보로 starter seed 자동 생성. **기존 사용자 seed 는 절대 덮어쓰지
  않음**. starter seed 는 투자전략 확정값이 아니며 기능 작동 확인용.
- **POST 응답 source 노출**: `summary.source` 필드로 UI 가 "기본 후보군 사용" 안내 표시.
- 새 endpoint 미도입. 새 draft_payload 키 미도입. 데이터 계약 변경 0건.

검증:
- pytest 119 → **147 passed** (Step6 16 + Step7A 11 추가).
- black / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계: 백엔드 max 572 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0 유지.

신규 / 수정 파일:
신규:
- docs/handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md (Step7A 종결 문서)
- tests/test_step7a_etf_watch_candidate.py (Step7A 회귀 11개)

수정:
- app/draft_message.py (EXTERNAL_UNIVERSE_BULLET_LABEL 정렬)
- app/draft.py (_build_universe_factor_signal 의 factor_name 정렬)
- app/universe_seed.py (STARTER_SEED_ITEMS + ensure_seed_file_exists 신규)
- app/api_universe.py (ensure_seed_file_exists 호출 + summary.source 노출)
- frontend/lib/api.ts (UniverseRefreshSummary 에 source 옵셔널 필드 추가)
- frontend/app/components/JudgmentReasonSection.tsx (default factor_name 정렬)
- frontend/app/components/UniverseRefreshPanel.tsx (헤더 / 버튼 / 안내 문구 정렬 + starter seed 안내)
- frontend/app/components/MainPanel.tsx (주석 정렬)
- tests/test_universe_momentum_step6.py / tests/test_universe_seed.py (라벨 정렬)

다음 단계:
- 사용자 협의 후 후속 구현 Step 1개 선택 (한 번에 하나의 PUSH 원칙 — Step7 §13).
- 후보: PUSH 1 보유 종목 상태 브리핑 / PUSH 3 급락 ETF 주의 신호 / 운영 빈도 문서 정합성 보정.

---

## 1.1 직전 상태 (POC2-Step7 설계서 저장)

```text
이전 단계: POC2-Step7 설계서 저장 완료 (CONDITIONAL_PASS, 2026-05-11) — 구조 재정렬 설계 단계
```

POC2-Step7 저장 요약 (본 작업):
- 신규 설계서: docs/handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md
- 레드팀 결과: **CONDITIONAL_PASS** (MINOR 결함 1건 수용 — "보유 종목 상태 브리핑이
  향후 매수/매도 의견으로 드리프트될 수 있는 표현" 중립화).
- **Step7 은 구현 단계가 아니라 구조 재정렬 설계 단계**. 코드 / API / UI / Telegram /
  데이터 계약 변경 0건.

공식 PUSH 명칭 (중립형 — 매매 의견 드리프트 차단):
1. **보유 종목 상태 브리핑** (PUSH 1) — 매매 의견이 아니라 상태 브리핑 재료.
2. **신규 ETF 관찰 후보** (PUSH 2) — Step6 universe momentum 결과를 이어받은 관찰 후보.
3. **급락 ETF 주의 신호** (PUSH 3) — 자리만 잡음, 현재 구현 없음.

기존 산출물 3-PUSH 매핑:
- Step3 보유 비중 영향 → PUSH 1 재료
- Step5B holdings momentum → PUSH 1 재료
- Step6 universe momentum → PUSH 2 재료
- 급락 ETF 경고 → PUSH 3 자리만 잡음

Step6 의미 제한 (드리프트 방지):
- ETF 개별 후보 모멘텀 점검 배관 검증 완료. 섹터/테마 발굴 / 매수 추천 체계 / 매수·매도 판단
  체계 / 급락 경고 / ML 검증 — 어느 것도 완료되지 않음.

다음 상태:
- 사용자와 협의 후 후속 구현 Step 1개 선택.
- **후속 구현은 한 번에 하나의 PUSH 만 다룬다** (Step7 §13 분리 원칙).
- 후속 구현 Step 후보: PUSH 1 / PUSH 2 / PUSH 3 / 운영 빈도 문서 정합성 보정 중 택일.

---

## 1.1 직전 상태 (POC2-Step6 최종 PASS)

```text
이전 단계: POC2-Step6 최종 PASS (Telegram 수신 확인, 2026-05-11) — 문서 정합성 보정 완료
```

POC2-Step6 최종 PASS 요약:
- pykrx 1개월 수익률 기반 universe scoring 성공.
- top_candidate 1개가 message_text / Telegram 판단 사유 3번째 bullet 로 도달.
- Telegram 수신 확인됨 (사용자 운영 테스트 — 2026-05-11).

Step6 의 의미 제한:
- **ETF 개별 후보 모멘텀 점검 배관 검증 완료** — 잘 오르는 ETF 1건을 PUSH 까지 도달시키는 데이터 흐름이 정상 작동함을 확인.
- 섹터/테마 발굴 완료 아님 — 발굴 단위 / 시간 측정 기간은 Layer A (ASSUMPTIONS Q4) 로 관리, 운영 첫 달 데이터로 검증.

ASSUMPTIONS 정리 (2026-05-11):
- **Q1**: OPEN 유지 (여러 factor 부착 가능 구조).
- **Q4**: OPEN 유지 (잘 올라가는 섹터/ETF 발굴 단위 — Layer A 항목 2개 추가).
- **Q5**: BACKLOG 이관 (AI 토론 점수체계 검증 — docs/backlog/BACKLOG.md "AI 토론 점수체계 검증" 항목).
- **활성 질문**: Q1 / Q4 2개 (3개 채울 필요 없음).

BACKLOG 정리 (2026-05-11):
- AI 토론 점수체계 검증 (Q5 이관) + 와이프 UI 이해도 검증 항목 신규.
- OPEN 6개 항목을 Layer A / B / C 3단계로 분류.
- Layer A = ASSUMPTIONS Q4 활성 관리 (발굴 단위 세부 / 시간 측정 기간).
- Layer B = BACKLOG + 향후 코드 주석 대상 (무릎머리어깨 / 급락 임계값 / 보유-외부 가중치).
- Layer C = ML 단계 보류 (RS / 거래량 / 정배열 등 복합 지표).

Step6 검증 통과 commit chain:
- 6810e697 feat(poc2-step6): minimal universe momentum scoring (pykrx 1m return)
- 2a225473 fix(poc2-step6): remove new API + new draft_payload key per Codex REJECTED
- 8bd76072 chore(poc2-step6): address Codex VERIFIED_WITH_NOTES — type + docstring touch-ups
- aa1253e1 docs(poc2-step6): mark VERIFIED + add handoff document for next session
- 9518f749 docs: integrate strategy definition decisions into anchors
- 93025d18 chore(deps): pin setuptools<81 for pykrx pkg_resources compatibility

검증자(Codex) 라운드 흐름:
1차 REJECTED (신규 GET endpoint + 신규 draft_payload 키 + stale __init__ docstring)
→ Fix 라운드로 3건 모두 수용 수정
→ VERIFIED_WITH_NOTES (FactorSignal.scope 타입 + 테스트 docstring stale 표기 + 라인 수 수치 차이)
→ NOTES 대응 commit (8bd76072) 으로 타입/docstring 정정
→ 최종 VERIFIED_WITH_NOTES (남은 NOTES 2건: pykrx timeout MEDIUM + 배포 dependency 주의 — 사유 1줄 명시 후 수정 불필요 판정).

Step6 Fix 라운드 요약 (본 라운드, 검증자 1차 REJECTED 대응):
검증자(Codex) 1차 REJECTED 항목 3건 — A-3 (__init__.py stale docstring) / A-4 (신규 API
추가) / A-4 (신규 draft_payload 키 추가) — 모두 수용 + 수정.

핵심 변경:
- **app/momentum/__init__.py docstring 정정**: Step5C 시점 표기 ("universe 결과는 어디에도
  실리지 않는다", "draft_payload 6번째 키까지") 를 Step6 현재 구조로 갱신.
  universe 결과는 factor_signals 안의 scope="universe" signal 1건으로만 표현된다는
  점 명시. draft_payload 키 추가 없음 명시.
- **GET /universe/momentum/latest endpoint 제거**: 신규 API 추가 금지 가드 준수.
  POST /universe/momentum/refresh 응답에 summary_reason_text / top_candidate 필드를
  추가하여 UI 가 응답 1번으로 상태 패널 표시 가능.
- **draft_payload.external_universe_check 키 제거**: BACKLOG `factor_signals 외 메타 키
  추가 금지` 가드 준수. 사용자(설계자) 결정 — universe momentum 결과는 기존 factor_signals
  5번째 키 안의 scope="universe" signal 1건으로 표현.
  · factor_id="universe_one_month_return", scope="universe"
  · is_available + reason_text / fallback_text + value(%) + input_basis(asof, basis_date,
    scored, total, refresh_status) + computed_at
- **draft_message.py 의 _external_universe_bullet 재작성**: factor_signals 의 universe
  scope signal 에서 reason_text / fallback_text 를 그대로 bullet 본문으로 사용 (label
  은 signal.factor_name).
- **app/message_universe_bullet.py 단순화**: 외부 bullet 형식 문자열 만들기 책임만.
  draft.py 의 _build_universe_factor_signal 이 본 모듈의 build_universe_signal_texts 를
  호출해서 reason_text / fallback_text 두 문자열을 만든다.
- **UI**: UniverseRefreshPanel 의 mount 시 GET 호출 제거. POST refresh 응답 → frontend
  state 로 표시. 페이지 reload 시 state 비워짐 → 안내 문구만 표시. (사용성 trade-off
  명시 — 페이지 reload 시 갱신 1회 더 필요.)
- **JudgmentReasonSection**: pickExternalUniverseBullet 을 factor_signals scope==universe
  에서 추출하도록 재작성. draft_payload.external_universe_check 참조 제거.

draft_payload 키 신설 0건 (Step6 Fix 후):
- 1) title, 2) asof, 3) note, 4) recommendations, 5) factor_signals, 6) momentum_result
- universe 결과는 factor_signals 안의 scope="universe" signal 1건으로 표현 (키 추가 0).

검증:
- pytest 119 → **135 passed** (Step6 회귀 16개 추가 — GET endpoint 테스트 1건은 removed
  검증 1건으로 통합).
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS.
- KS-10 임계 (실측): 백엔드 max 569 / 프론트 max 515 / 테스트 max 924 — 트리거 0 + 근접 0.

직전 라운드 (Step6 1차) 요약:
"잘 달리는 말 찾기" 의 첫 실제 계산 단계. manual universe seed 후보군에 pykrx 기반
1개월 기간 수익률 1개를 적용해 상위 1개를 UI / Telegram [판단 사유] 1줄에 반영.

핵심 변경:
- 점검값: **pykrx 기반 1개월 수익률** (one_month_return_pct = (latest/base - 1)*100).
  복합 점수체계 / MA / RSI / 보너스 / Top N / BUY·SELL 일체 미도입.
- pykrx 호출은 **app/price_history_pykrx.py 1개 모듈에만**. fetch_one_month_basis 함수.
- bounded sync refresh: MAX_UNIVERSE_ITEMS_PER_REFRESH=20 / per_ticker_delay=0.5s /
  budget=30s. seed >20 hard fail. candidate 단위 실패 격리.
- POST /universe/momentum/refresh : status (ok / partial / failed) + scored/total 응답.
- GET /universe/momentum/latest : UI 상태 패널용 latest artifact 조회 (refresh 안 된
  상태는 status="absent").
- universe_momentum_latest.json 확장: refresh_status / data_source="pykrx" /
  score_basis="one_month_return_pct" / lookback_days=30 / fetch_window_days=45 /
  top_candidate (rank=1).
- candidate scored: score_value(%) / score_unit="%" / ranking_basis / price_history_basis
  (base_date/base_close/latest_date/latest_close).
- candidate unscored: exclusion_reason 만 기록. rank 키 미생성.
- GenerateDraft → universe_momentum_latest.json 의 top_candidate 를 draft_payload
  의 7번째 키 external_universe_check 로 병합. **pykrx 직접 호출 0건** (AC-20).
- message_text [판단 사유] 3번째 bullet 추가 — "외부 후보 점검: pykrx 1개월 수익률
  기준 {name} 이 가장 높습니다({value}%, 기준일 {date}, 계산 가능 {scored}/{total}개).
  이 값은 매수 추천이 아닙니다."
- 실패 시 bullet: "외부 후보 점검: pykrx 가격 데이터 부족으로 1개월 점검값을 계산하지
  못했습니다(기준일 {basis_date})."
- 기준일 우선순위: top_candidate.price_history_basis.latest_date → universe.asof →
  "기준일 확인 불가".
- [판단 사유] 헤더 1번 유지 (factor → 모멘텀 → 외부 후보 3 bullets).
- UI: HoldingsClient 아래 별도 UniverseRefreshPanel — 외부 후보 점검 갱신 버튼 +
  상태 패널 (마지막 asof / refresh_status / 기준일 / 계산 가능/전체 / top_candidate
  1건 / 실패 사유). 후보 전체 목록 미노출.
- 버튼 정책: 요청 중 disabled. Telegram / Approve / GenerateDraft 자동 실행 금지.

신규 / 수정 파일:
신규:
- app/price_history_pykrx.py (138라인) — pykrx 단일 호출 모듈
- app/universe_refresh.py (258라인) — bounded sync refresh service
- app/api_universe.py (151라인) — POST refresh + GET latest 라우터 분리
- app/message_universe_bullet.py (90라인) — 외부 후보 점검 bullet 빌더
- frontend/app/components/UniverseRefreshPanel.tsx (210라인) — UI refresh 버튼 + 상태 패널
- tests/test_universe_momentum_step6.py (391라인) — 17개 회귀 테스트

수정:
- app/momentum/universe_mode.py 147→314 (build_universe_momentum_result_scored 추가)
- app/momentum/__init__.py (re-export 추가)
- app/api.py 557→497 (universe endpoint → api_universe 로 분리, 라우터 include 만)
- app/draft.py 160→221 (external_universe_check 로딩 함수 추가)
- app/draft_message.py 525→536 (3번째 bullet 헤더 통합 — 본체는 message_universe_bullet)
- frontend/lib/api.ts 290→380 (universe refresh / latest 엔드포인트 클라이언트)
- frontend/app/components/MainPanel.tsx 65→69 (UniverseRefreshPanel embed)
- frontend/app/components/JudgmentReasonSection.tsx 108→173 (3번째 bullet picker)
- requirements.txt (pykrx>=1.0.51 추가)
- tests/conftest.py 86→118 (pykrx fetcher stub + universe path patch)
- tests/test_universe_seed.py (Step6 동작 반영 — external_universe_check 키 검증)

KS-10 임계 상태 (실측):
- 백엔드: max draft_message.py 536 / api.py 497 — 트리거 4 (650) 미달, 근접 (>=600) 0건 ✓
- 프론트: max EnrichedHoldingsSection.tsx 515 — 트리거 3 (900) 미달, 근접 (>=850) 0건 ✓
- 테스트: max test_holdings_message_text.py 924 — 트리거 1 (1500) 미달, 근접 (>=1450) 0건 ✓
- **모든 트리거 0건 + 모든 근접 0건 유지** ✓ (Step5D-2 Final 이후 회귀 없음)

검증:
- pytest 119 → 136 passed (1.17s) — Step6 회귀 17개 추가
- black --check / flake8 / TypeScript build / Next.js lint 모두 PASS
- pykrx 의존성 추가 (requirements.txt) — pykrx>=1.0.51

Q5 첫 실전 검증 기록 (ASSUMPTIONS.md Q5 보강):
- 채택: pykrx 1개월 기간 수익률 (단일 가격 기반 변수)
- 기각/보류: 수동 recent_return_pct (보수적) / 당일 등락률 (노이즈) / manual_score (근거 약함)
- Q5 상태: OPEN 유지 — 운영 사이클 1회 후 1차 검토

직전 상태 (Step5D-2 Final Round):

Step5D-2 Final Round 요약 (본 라운드):
직전 라운드의 §4.3 "관찰만" 대상이었던 HoldingsClient.tsx (906라인 = 트리거 3 충족) 와 draft_message.py (600라인 = 트리거 4 근접) 까지 모두 해소. 동시에 RunPanel ↔ EvidenceDetails 양방향 import 정돈.
- frontend/lib/holdings_view.ts (186라인) 신규 — RunPanel ↔ EvidenceDetails 가 공유하던 helpers/types 단일 출처. JSX 미포함 (.ts).
  · DEFAULT_GROUP, fmt 5종 (Money/SignedMoney/Pct/SignedPct/pnlClass), NormRec/Summary/AccountSummary 타입, normalizeRec/isPriced/isCalcAvailable/rowKey/computeSummaryFor.
- frontend/app/components/RunPanel.tsx 606 → 444라인. helpers/types 본문 제거 + lib import 로 전환. OverallSummaryCard 만 잔존 (JSX 컴포넌트라 lib 이동 부적합).
- frontend/app/components/EvidenceDetails.tsx 343라인. import 출처를 "./RunPanel" → "@/lib/holdings_view" 로만 변경 (양방향 import 해소). 본문 / 동작 / 렌더 동일.
- frontend/app/components/EnrichedHoldingsSection.tsx (515라인) 신규 — HoldingsClient.tsx 의 시세평가 compact UI 책임 분리.
  · EnrichedSection (default) + 8개 자식 컴포넌트 (OverallSummaryCard / AccountSummaryCards / AccountSummaryRow / CompactHoldingsTable / CompactRow / DetailRowFields / SummaryItem / KV).
  · 로컬 helpers (Summary/AccountSummary/isPriced/isCalcAvailable/computeSummaryFor/groupByAccount/rowKey) — EnrichedHolding 기반이라 holdings_view.ts 의 NormRec 기반 helpers 와 분리.
  · fmt helpers 는 holdings_view.ts 에서 import (중복 제거).
- frontend/app/components/HoldingsClient.tsx 906 → 394라인. EnrichedSection 추출 + fmt helpers 중복 제거. DEFAULT_GROUP 도 lib 사용.
- app/message_helpers.py (124라인) 신규 — draft_message.py 의 leaf-level format / 항목 식별 helpers 분리.
  · _to_finite_float, _format_money/_format_pct/_format_signed_money/_format_signed_pct, _is_priced/_is_calc_available/_is_default_hold/_item_label, DEFAULT_HOLD_REASON.
- app/draft_message.py 600 → 525라인. leaf helpers 본문 제거 + message_helpers 재공개. 공개 API (`is_holdings_draft` / `compute_summary` / `build_message_text` / `DEFAULT_HOLD_REASON` / `MAX_LENGTH_CHARS`) 동일 import 경로 유지.
- pytest 119 passed (1.16s). black --check / flake8 / TypeScript build / Next.js lint 모두 PASS.
- message_text / UI 렌더 / Telegram payload / [판단 사유] 헤더 / 2 bullets 모두 동일 (본문 이동만, 로직 변경 0).

KS-10 트리거 상태 (본 라운드 보고 직전 실측):
- 백엔드: app/api.py 557 / draft_message.py 525 / 그 외 모두 250 이하 — 트리거 4 (650) 미달, **근접(>=600) 0건** ✓
- 프론트: EnrichedHoldingsSection.tsx 515 / RunPanel.tsx 444 / HoldingsClient.tsx 394 / 그 외 모두 350 이하 — 트리거 3 (900) 미달, **근접(>=850) 0건** ✓
- 테스트: test_holdings_message_text.py 924 / 그 외 모두 510 이하 — 트리거 1 (1,500) 미달, **근접(>=1,450) 0건** ✓
- **모든 트리거 0건 + 모든 근접 0건 동시 달성** ✓

직전 라운드 (Step5D-2 1차) 요약:
Step5D-2 지시문 §1.2 가 명시한 트리거 2건만 해소.
- tests/test_holdings_draft_flow.py 1,982 → 244라인. 3개 파일로 도메인별 분리.
- frontend/app/components/RunPanel.tsx 905 → 606라인. EvidenceDetails.tsx (343라인) 추출.

Step5D Cleanup 요약:
검증자 NOTES B-3 누적 지적(단일 파일 책임 누적) 에 대응해 신규 기능 추가 없이 구조만 정돈.
- 백엔드 테스트 파일 분리: tests/test_poc1_loop.py 3,452라인 → 298라인.
  conftest.py / _helpers.py / 4개 신규 테스트 파일 (holdings_draft_flow / factor_signals / momentum_holdings / universe_seed) 로 분산.
  pytest 119 passed 그대로 유지 — 의미/개수/검증 강도 변경 0건.
- 프론트 컴포넌트 분리: RunPanel.tsx 1,055라인 → 905라인.
  JudgmentReasonSection.tsx + MomentumCandidatesSection.tsx 로 표시 책임 일부 추출.
  렌더링 / 문구 / 배치 / 동작 / message_text 모두 동일.
- KS-10 (단일 파일 라인 수 / 책임 누적 임계 초과) 가드 추가: KILL_SWITCHES.md 명문화.
- PROJECT_ORIGIN_INTENT 배움 자산 / ASSUMPTIONS Q3 보강 / Q5 확인 방법 보강.
- BACKLOG CLEANUP CANDIDATES 신규 섹션: holdings_draft_flow 추가 분리, EvidenceDetails 분리, HoldingsClient 분리, draft_message 패키지화, api.py 라우터 분리.

Step5C 요약 (직전 단계):
manual universe seed 파일을 읽어 score 없는 universe mode momentum_result 를 생성하고
state/universe/universe_momentum_latest.json 에 latest 1건 덮어쓰기 artifact 로 저장.
실행 트리거: POST /universe/momentum/refresh 수동 backend API 1곳.
universe 결과는 draft_payload / Run top-level / message_text / UI / Telegram 어디에도 노출 안 함.

Step5C 요약:
manual universe seed (state/universe/etf_universe_latest.json) 를 읽어 universe mode
momentum_result 를 생성하고 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기)
artifact 로 저장한다. 실행 트리거는 POST /universe/momentum/refresh 수동 backend API 1곳
이며, holdings draft 생성 / Approve / OCI handoff / Telegram / scheduler 어디에서도
자동 호출되지 않는다.
asof 는 YYYY-MM-DD 필수 + 미래 날짜 차단. UNIVERSE_SEED_MAX_AGE_DAYS=30 초과 = stale
(hard fail 아님, summary.source_freshness="stale" + summary_reason_text 에 명시).
universe mode 는 점수 미부여 (score_result.is_scored=false, rank 미생성) — 이번 Step 은
입력 통로 + latest artifact 저장만 검증.
universe 결과는 draft_payload / Run top-level / message_text / UI / Telegram 어디에도
실리지 않는다.
pytest 119 passed (Step5B 107 + Step5C 신규 12).

Step5B 요약 (직전 단계):
placeholder 산식(pnl_rate)으로 Momentum Engine holdings mode 를 1회 실행했다.
결과는 draft_payload.momentum_result (Step5B 한정 명시 승인된 6번째 키) 에 저장되며,
승인 초안 UI 의 [판단 사유] 섹션과 message_text/Telegram 에 1줄 bullet 으로 추가된다.
별도 [모멘텀 점검] 헤더는 만들지 않으며 [판단 사유] 헤더는 1번만 등장한다.
candidates 의 row 매핑은 source_index + ticker + account_group + avg_buy_price 4 요소로
보존되어 동일 ticker 분할매수 row 의 매핑 충돌을 방지한다.

Step5A 요약 (직전 단계):
Momentum Engine 의 최소 입력/출력 계약을 정의했다.
Momentum Engine 은 holdings mode 와 universe mode 가 공유한다.
universe mode 에서 엔진은 후보군을 직접 수집하지 않고, 외부에서 주입된 candidates 를 평가한다.
rank 는 optional 이며 score / ranking_basis 가 없으면 생략 가능하다.

이전 단계 누적:
- Step4: Momentum Engine 방향 정리 (holdings mode / universe mode 두 축, 친구 시스템은 결과물 아닌 과정만 참고)
- Step3: 보유 비중 영향 factor 1개를 draft_payload.factor_signals + 승인 초안 UI + message_text + Telegram/Push 까지 통합
- Step2 전체 종료: holdings 입력/저장, account_group, Naver 시세, 평가 계산, compact UI, message compaction, 승인 초안 preview 분리

ASSUMPTIONS:
- Q3 → A-5 ANSWERED 이동 (Step4 시점 — KS-3 비건설적 핑퐁 패턴 재발 없음)
- Q5 → OPEN 신규 등록 (검증 대상 = 사용자 본인)
- 활성 질문은 Q1 / Q4 / Q5 유지 (3개)

주의:
- Step5B 의 placeholder 산식(pnl_rate) 은 최종 투자 판단 산식이 아니다 — UI/메시지 모두 명시.
- Step5C 는 universe 후보군 입력 통로와 latest artifact 저장만 만든 단계. 잘 달리는 말 후보를 평가한 것이 아니다 — 점수 미부여, rank 미생성.
- 외부 ETF 자동 수집, MA/RSI/수익률 기간 산식, 유니버스 종목 수 / ETF 후보군 자동 결정, ML 모델, 화면 대개편, Telegram Top N, BUY/SELL/리밸런싱, 운영 결과 별도 DB, history 누적은 아직 구현하지 않았다.
- universe mode 결과 저장 위치는 state/universe/universe_momentum_latest.json (latest 1건 덮어쓰기). draft_payload / Run top-level / DB / history 미도입.
- holdings mode 결과 저장 위치는 draft_payload.momentum_result 6번째 키 (Step5B 결정 그대로).
- 운영 결과 기록 / AI 해석 로그 / ML dataset 구조는 Step5C 까지 미도입 — 별도 Step 에서 판단.
- "잘 달리는 말 찾기" 는 holdings factor 가 아니라 universe mode 에서 다룬다 — 단 엔진은 후보군을 직접 수집하지 않는다.
- 와이프는 UI 가독성 검증 대상이며 Q5 의 투자 판단/운영 방식 적합성 검증 대상이 아니다.
- Q1 은 ANSWERED 가 아니라 OPEN 유지. Step3 결과는 1차 긍정 증거에 불과.

직전 종결/설계 문서:
- `docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md` (Step5A 설계서)
- `docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md` (Step4 설계서)
- `docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md` (Step3 종료 선언)
- `docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md` (Step2 종료 선언)
- `docs/backlog/BACKLOG.md` (Step5 진입 전 정돈 완료 — ACTIVE REVIEW BEFORE STEP5 / CONSOLIDATED DEFERRED / CLOSED)

Step5B / 5C 구현 진입점 (코드):
- `app/momentum/holdings_mode.py` — placeholder 산식 빌더 (pnl_rate, Step5B)
- `app/momentum/universe_mode.py` — universe candidates 변환 + latest artifact 저장 (Step5C)
- `app/momentum/__init__.py` — 패키지 진입점 (holdings_mode + universe_mode export, 추상 클래스 / registry 미도입)
- `app/universe_seed.py` — manual seed loader + asof 검증 + UNIVERSE_SEED_MAX_AGE_DAYS=30 staleness (Step5C)
- `app/draft.py` — _build_holdings_payload 에서 holdings momentum_result 빌드 + draft_payload 6번째 키 부착 (Step5B). universe 와 무관.
- `app/draft_message.py::_render_judgment_lines` — factor + holdings momentum 두 bullet 을 1개의 [판단 사유] 헤더 아래에 합침 (Step5B). universe 는 메시지 미반영.
- `app/api.py` — POST /universe/momentum/refresh 수동 endpoint (Step5C, holdings draft 흐름과 분리)
- `frontend/lib/api.ts` — MomentumResult / MomentumCandidate / ... 타입 (Step5B holdings mode UI 한정. universe 는 UI 미노출)
- `frontend/app/components/RunPanel.tsx::JudgmentReasonSection` — 모멘텀 bullet 1줄 추가, EvidenceDetails 안 MomentumCandidatesSection (Step5B)
- `docs/examples/etf_universe_latest.example.json` — universe seed 예시 (Step5C)

---

## 2. Step2 완료 요약

```text
POC2-Step2는 holdings 입력/저장, account_group, Naver 시세 갱신, 평가 계산, compact table,
Telegram message compaction, 승인 초안 preview 분리까지 완료했다.
사용자 테스트 기준 Telegram 수신까지 확인했다.
```

세부 종결 문서:
- `docs/handoff/POC2_Step2_close.md` — Naver 시세 enrichment
- `docs/handoff/POC2_Step2B_close.md` — Telegram message compaction
- `docs/handoff/POC2_Step2C_close.md` — Holdings UI compaction + account grouping
- `docs/handoff/POC2_Step2D_close.md` — Approval draft preview separation
- `docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md` — Step2 전체 종료 선언 + Step3 진입 가드

---

## 3. 완료된 Step (이력)

### POC1
- POC1-Step1: 최소 승인 루프 상태 모델 (PENDING_APPROVAL / REJECTED / DELIVERING / FAILED / COMPLETED)
- POC1-Step2: Next.js + TypeScript + App Router UI + FastAPI CORS
- POC1-Step3: 실 OCI handoff (SCP + outbox reconciliation) + Telegram 발송 end-to-end 검증

### POC2
- POC2-Step1: holdings 기반 draft 생성 + JSON SSOT 저장
- POC2-Step1A: raw JSON 표시 제거 + holdings 초안 사람이 읽는 렌더링 + handoff message_text top-level
- POC2-Step2: Naver 1차 시세 enrichment + 평가/손익/시장비중 계산
- POC2-Step2B: Telegram 메시지 요약형 + 길이 제한 방어 (MAX_LENGTH_CHARS=3500)
- POC2-Step2C: Compact UI + account_group + React key 안정성 + polling 펼침 상태 유지
- POC2-Step2D: 승인 초안 preview 분리 (Run.message_text top-level + 단일 소스 보장)
- POC2-Step3: 첫 factor signal 통합 (portfolio_concentration_v1 / "보유 비중 영향")
  · draft_payload.factor_signals 5번째 키 (Step3 한정 명시 승인)
  · portfolio scope 1개 + max_weight_row holding_row scope 0~1개 고정
  · message_text 에 [판단 사유] 1줄 (portfolio reason 또는 fallback)
  · 승인 초안 UI 에 판단 사유 섹션 기본 노출
  · BUY/SELL/리밸런싱/Top N/위험 등급 등 일체 미도입

---

## 4. 다음 단계 주의사항

```text
다음 세션은 Step3 설계에 진입한다.
Step3의 factor 종류, 라벨, 산식, threshold는 이 handoff에서 확정하지 않는다.
Step3 설계서에서 다시 검토한다.
추가 UI polish Step으로 우회하지 않는다.
ASSUMPTIONS Q1과 명시적으로 연결한다.
BUY/SELL/리밸런싱/ML 확장은 금지한다.
```

다음 Step 명칭 (잠정):

```text
POC2-Step3 — First Factor Signal Integration
```

Step3 종료 조건 (POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md §7 참조):
1. factor 1개가 계산된다.
2. factor 결과가 `draft_payload`에 반영된다.
3. factor 결과가 승인 초안 화면에 표시된다.
4. factor 결과가 `message_text`에 반영된다.
5. 승인 후 Telegram 에서 factor 기반 판단 사유를 확인한다.
6. 기존 승인/OCI/Telegram 경로가 유지된다.
7. BUY / SELL / 리밸런싱 / ML 확장은 발생하지 않는다.

---

## 5. 금지사항 (Step3 진입 가드)

```text
- Step3 factor 종류 선확정 금지
- WATCH/REVIEW 등 라벨 선확정 금지
- 다음다음 단계 로드맵 선설계 금지
- UI polish로 Step3 진입 지연 금지
- 친구 프로젝트 통째 복제 금지
```

추가 (Step2 까지 누적된 절대 금지 — Step3 도 동일 적용):
- pykrx / yfinance fallback (POC2-Step2A 별도 STEP 에서만 검토)
- BeautifulSoup / desktop scraping / polling stream / WebSocket / SSE
- DB / MongoDB / SQLite / PostgreSQL / Redis
- 새 UI 프레임워크 (shadcn/MUI/Tailwind) / 전역 상태 관리 라이브러리
- snapshot / history / 전일 대비 변화 감지
- 메시지 split 발송
- 계좌번호/증권사/세금/오픈뱅킹 API 연동
- "실시간" 단어 사용
- 신규 의존성 / 파일 삭제 / DB 스키마 변경 — 사용자 명시 승인 필수

---

## 6. 확정 기술 스택 (Step2 종료 시점 스냅샷)

Backend:
- FastAPI
- JSON 파일 기반 SSOT
- httpx + Naver 금융 JSON endpoint
- OCI handoff (SCP + outbox)
- existing daily_ops.sh 소비
- Telegram 기존 발송 경로
- Run.message_text top-level optional metadata

Frontend:
- Next.js 15 + TypeScript + App Router
- FastAPI 분리 + CORS
- HTML datalist (account_group 입력)
- preview block + evidence-details (Step 2D)

Storage:
- holdings: state/holdings/holdings_latest.json (account_group 키 포함)
- market cache: state/market_cache/market_latest.json
- runs: state/runs/{run_id}.json (message_text top-level 키 포함, 과거 run 은 누락 허용)

---

## 7. 현재 설계 원칙 (Step2 종료 시점 누적)

- 한 Step 은 하나의 목표만 가진다.
- 기능 확장보다 운영 장애 해결을 우선한다.
- Telegram 은 전체 보고서가 아니라 요약 알림이다. 전체 상세는 UI 에서 본다.
- 외부 조회는 명시적 갱신 액션(POST /market/refresh)에서만 수행한다.
- 화면 조회, polling, draft 조회에서 외부 fetch 금지.
- 누락 데이터는 0/null/undefined/NaN 으로 노출하지 않는다. 키 자체 생략 + 별도 플래그.
- "시세 확인" ≠ "평가 계산 가능". 평가 집계는 평가 계산 가능 종목만 사용.
- account_group 은 표시/그룹용 라벨이며 계좌번호/세금/증권사 판정값이 아니다.
- 백엔드 정규화가 최종 방어선. 프론트엔드 정규화는 보조.
- React key / 펼침 상태 식별자는 source_index + ticker + account_group + avg_buy_price 조합.
- 승인 초안 화면의 message_text 는 백엔드가 generate 시점에 빌드한 원본을 그대로 렌더 — 프론트엔드는 조립/파싱하지 않는다.
- preview / OCI handoff / Telegram 발송은 모두 동일한 Run.message_text 단일 소스를 사용한다.
- raw JSON 은 어떤 분기에서도 기본 화면에 노출되지 않는다 (필요 시 기본 접힘 details 안으로만).

---

## 8. 다음 세션 첫 액션

다음 세션은 아래 순서로 진행한다.

1. CLAUDE.md 읽기
2. docs/PROJECT_ORIGIN_INTENT.md 읽기
3. docs/agent/INSTRUCTION_RULES.md 읽기 (선택)
4. docs/KILL_SWITCHES.md 읽기
5. docs/ASSUMPTIONS.md 읽기 (Q1 OPEN 유지 / Q4 OPEN / Q5 OPEN 명시 연결, A-4 / A-5 ANSWERED 확인)
6. docs/MASTER_PLAN.md 읽기
7. docs/handoff/STATE_LATEST.md 읽기 (본 문서)
8. docs/handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md 읽기 (Step5A 설계서 — 다음 STEP 의 입력/출력 계약)
9. docs/handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md 읽기 (Step4 설계서 — Momentum Engine 방향 가드)
10. docs/handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md 읽기 (Step3 종료 선언, 필요 시)
11. docs/handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md 읽기 (Step2 종료 선언, 필요 시)
12. docs/backlog/BACKLOG.md 읽기 (ACTIVE REVIEW BEFORE STEP5 5건 + CONSOLIDATED DEFERRED + CLOSED)
13. "기반 문서 확인 완료" 응답 후 사용자/설계자 의 Step5B (Momentum result 저장 위치 결정) 설계 지시 대기

다음 세션이 절대 하지 않을 것:
- universe mode 에 실제 모멘텀 산식을 추가 (Step5C 다음 별도 STEP — 산식·데이터 소스·UI 노출은 별도 결정)
- universe 결과를 draft_payload / Run top-level / message_text / Telegram / UI 어디에도 자동 노출 (Step5C 가드)
- POST /universe/momentum/refresh 를 GenerateDraft / Approve / scheduler / cron 에서 자동 호출
- 외부 ETF 자동 수집 (Naver / pykrx / yfinance / KIS) — universe seed 는 사용자가 수기로 작성
- DB / history 저장소 / AI 해석 로그 / ML dataset 도입
- ML 바로 구현 / BUY·SELL·리밸런싱 구현
- 친구 UI 복제 / 친구 산식 통째 이식
- holdings mode 와 universe mode 동시 산식 도입 강제
- Q1 / Q5 를 ANSWERED 로 임의 이동
- "와이프 = 투자 판단/운영 방식 적합성 검증 대상" 으로 혼동 (와이프는 UI 가독성 전용)
- rank 를 Telegram Top N 또는 매수 우선순위로 해석
- draft_payload 7번째 키 신설 (Step5B 6번째 키까지가 한정 승인)
