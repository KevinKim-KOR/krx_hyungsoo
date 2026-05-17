# STATE_LATEST.md

최종 업데이트: 2026-05-17

---

## 0. 현재 상태 — 2026-05-17 PC Market Discovery TOP N 최소 표시 완료

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
