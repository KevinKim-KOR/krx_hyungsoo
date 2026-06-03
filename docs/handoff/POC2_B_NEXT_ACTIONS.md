# POC2 B 방향 — 다음 액션 (NEXT ACTIONS)

작성일: 2026-05-20 / 갱신: 2026-06-03 (KS-10 Cleanup: API Client / Type 책임 분리)
성격: **방향을 잊지 않기 위한 앵커.** 새로운 가드 문서가 아니다. 설계 결정이
흔들릴 때 PROJECT_ORIGIN_INTENT 원칙과 함께 본 문서로 복귀한다.

본 문서는 다음 챕터 진입자가 한 번 읽고 "지금 무엇을 해야 하는지" 를 즉시
파악할 수 있도록 작성되었다 — 단기 (현재 STEP) / 중기 (바로 다음 후보) /
보류 (지금 멈춘 것) 의 3 단으로만 구분한다.

---

## 1. 현재 최우선 작업 (2026-06-03 — KS-10 Cleanup 완료, 다음 방향 사용자 결정 대기)

### KS-10 Cleanup: API Client / Type 책임 분리 (DONE)

직전 STEP (Market Discovery Evidence Closeout 1차) 종료 시점에 남은 구조
부채 — `frontend/lib/api.ts` 993 라인 단일 파일의 KS-10 §1.5 trigger — 를
도메인 책임 기준 8개 모듈 + 1개 barrel 로 분리했다. 본 STEP 의 단일 목적은
trigger / near 임계 0 달성이며 기능 추가 / API 계약 변경 / UI 문구 변경 0건.

- 분리 결과: `frontend/lib/api/` 디렉토리에 core / runApproval / holdings /
  universeMomentum / marketEvidence / market / etfExposure / decisionSessions
  + index barrel. `@/lib/api` import 경로 호환 유지 (21 컴포넌트 0건 수정).
- 활성 코드 trigger_files_after = [] / near_threshold_files_after = [].
- 백엔드 / 프론트 / 테스트 모두 회귀 없음 (pytest 354 / build PASS).
- 검증자 NOTE FIX 2건 반영 — A-2 (실측 카운트 정정 86 → 97) / B-6
  (`request` 내부 fetch wrapper 를 barrel public surface 에서 제외).

### 다음 큰 방향 (사용자 결정 대기)

1. **Holdings 판단 연결** — PROJECT_ORIGIN_INTENT §3 PC 작업 4~5단계.
   AI Sessions 기록과 holdings 상태를 연결해 매매 결정 / 보류 사유 기록.
2. **AI Sessions 기록 복기 구조** — 누적 기록의 검색 / 비교 / 후속 판단
   회수율 측정.
3. **ML factor 후보 정리** — ASSUMPTIONS Q1 (여러 factor 를 붙일 수 있는
   구조의 엔진).
4. **ML / 백테스트 연결**.

### 별도 분기 후보 (Market Discovery 영역으로 회귀하는 경우만)

- **NAV / 괴리율 source 진단 STEP** — 직전 ETF Constituents Source
  Diagnosis 패턴 따라 Naver Stock detail endpoint 등 candidate source
  smoke test 후 채택 검토.

### (이전) Market Discovery Evidence Closeout 1차 (DONE 2026-06-01)

본 STEP 으로 Market Discovery 1차 증거 묶음을 마감했다. 단기 흐름 + 일간
플래그 + NAV / 괴리율 인프라 + AI Sessions 증거 snapshot 까지 통합 완료.
**Market Discovery 계열 신규 기능 확장은 일단 중단**한다.

### (이전) ETF Constituents Naver Source Integration (DONE 2026-05-31)

본 STEP 의 산출물은 STATE_LATEST.md §0.1 참조.

- `naver_stock_etf_component` 를 1차 source 로 채택. service 의 cache key 도
  새 source 매칭.
- DB 스키마 4 컬럼 확장 + 자동 마이그레이션 (직전 STEP DB 호환).
- 해외형 ETF (`componentItemCode=null`) 도 `componentReutersCode` /
  `componentIsinCode` 보존 + 매칭 키 우선순위 확장 (constituent_key → ticker →
  reuters → ISIN → name).
- ETF Exposure / 구성종목 Refresh / 중복률 / AI 문구 [구성종목/중복 노출] 섹션
  모두 사용 가능 으로 전환 (POC2_FEATURE_INVENTORY 반영).

### 다음 후보 (참고만): C. KRX Open API / Official Provider Source Design (기존)

**실측 근거** (2026-05-31 Source Diagnosis 1차):
- pykrx `get_etf_portfolio_deposit_file` — 3 ETF × 5 날짜 = 15 호출 모두
  `no_data` (예외 0건, df 0 rows). **pykrx_operational_issue** 분류. **hold**.
- Naver Mobile ETF Component API — 3 ETF 모두 HTTP 404. **unusable**.
- 지시문 §21.C: "Naver Mobile API 사용 불가 + pykrx 사용 불가" → KRX Open API
  설계 후속 후보.

본 다음 STEP 의 범위 (지시문 §8 / §21.C):
- KRX Open API 인증키 필요 여부 확인.
- 호출 한도 / 응답 구조 / ETF 별 커버리지 / 구성종목 비중 제공 여부.
- K6 방어 가능 여부 (기존 service 의 10개 cap / 0.5s delay / 30s budget /
  partial / unavailable 정책에 fit 하는지).
- 인증키 활성화 대기 동안에는 ETF Exposure 메뉴를 사용 불가 상태로 인벤토리
  명시 (`docs/handoff/POC2_FEATURE_INVENTORY.md` §2.10~12).

### (이전) ETF Constituents & Overlap 1차

- 좌측 메뉴에 `ETF Exposure` 추가 (Market Discovery 와 화면 분리).
- Market Discovery → ETF Exposure draft 전달 (sessionStorage Context Bridge).
- pykrx PDF (`get_etf_portfolio_deposit_file`) 1차 fetcher + K6 방어 (10개
  cap / cache-first / 0.5s delay / 30s budget / partial / unavailable).
- POST /market/constituents/refresh + GET /market/constituents/analysis.
- 집중도 (top 1/3/5/10) + 쌍별 중복률 (common_count_top10 +
  weighted_overlap_pct = sum(min(left, right))) + 반복 등장 핵심 종목.
- AI 투자세션 복사용 문구에 [구성종목 / 중복 노출] 섹션 + 새 요청 문구
  (독립 테마 vs 반복 노출 판단).
- AI Sessions Context Bridge / POST /decision/sessions / 상세 화면 모두에
  `constituent_snapshot` / `overlap_snapshot` 영속화 (마이그레이션 포함).

본 STEP 의 범위는 "실제 노출 구조 확인" 까지다. 매수/매도 판단 / 리밸런싱 /
NAV / 유동성 점수화는 본 STEP 의 작업이 아니다.

### (이전) Market Regime & Benchmark Context 1차

- 시스템이 KODEX200 (필수) / KOSPI (보조) 기준으로 **1차 시장 국면 판정** 산출.
- 라벨: 상승장 / 보합장 / 하락장 / 판정불가 (regime_code: bull / neutral /
  bear / unavailable).
- 점수 방식: KODEX200 20거래일 / 60거래일 수익률 + MA20/MA60 위치 4 항목을
  +1/-1/0 으로 합산 → +2 이상 bull / -2 이하 bear / 그 외 neutral.
- Market Discovery 응답 (`GET /market/topn/latest`) 에 `market_context` +
  각 candidate 의 `excess_return` (vs KODEX200 / KOSPI 1m / 3m %p) 포함.
- Market Discovery 화면에 시장 배경 카드 + 후보 테이블에 KODEX200 대비 1m/3m
  컬럼 추가.
- AI 투자세션 복사용 문구에 [시스템 시장 판정] + [시장 대비 후보 강도] 섹션 추가.
- AI 요청 문구를 **AI 에게 장세 판정을 맡기지 않고** 시스템 판정 전제 + 해석/
  반론 요청으로 변경.
- Market Discovery → AI Sessions Context Bridge draft 에
  `market_context_snapshot` 포함. POST /decision/sessions 가 저장하고 GET
  상세에서 노출.

본 STEP 의 범위는 "정량 1차 판정 + benchmark context + 화면/문구/저장소
연계" 까지다. 완성형 시장 정권 모델 / KOSDAQ 비교 / ETF 구성 종목 / NAV /
ML 연결 / 매수·매도 판단은 본 STEP 의 작업이 아니다.

---

## 2. 바로 다음 후보 (사용자 결정 대기)

순서는 우선순위가 아니다 — 사용자가 명시 지시문으로 선택한다.

1. **시장 국면 판정 고도화** (2026-05-27 본 STEP 1차 후 후속)
   - 본 1차는 단순 점수 합산. 다음 단계 후보: 변동성 / 시장 폭 (advance-decline) /
     장기 추세 / 외인·기관 수급 등을 점수에 반영해 라벨 신뢰도 향상.
   - 운영 데이터로 1차 판정의 적중률을 검증한 뒤 진행.
2. **NAV / 괴리율 / 유동성**
   - 종목 선정 단계 진입 시 필요. ETF 가격이 NAV 와 얼마나 떨어져 있는지,
     거래량이 충분한지.
4. **AI 투자세션 결과 기반 개선**
   - 누적된 `ai_session_records` 를 1개월 운영 후 들여다보고, 어떤 판정 / 메모 /
     다음 확인 항목이 반복되는지 분석. 운영 데이터를 기반으로 다음 발굴 단위 /
     비교 기간 / 점수체계 후보를 도출.

---

## 3. 지금 멈춘 것 (보류 / 제외)

본 항목들은 영구 제외가 아니라 **현재 단계에서는 진행 중단**.

- **KOSDAQ 비교** — 기본 비교 대상에서 제외 (사용자가 코스피 중심으로 투자).
- **UI Grid 재정리** — 컬럼 추가 / 정렬 옵션 증설 / 차트 도입 등은 멈춘다.
  Grid 사용성은 직전 STEP (2026-05-19 GRID 우선 + 컬럼 클릭 정렬) 로 충분.
- **ML 연결** — 아직 아님. 점수 산식 / factor weight 자동 결정 모두 보류.
  ML 단계는 ASSUMPTIONS L-2 가 답 나올 때 다시.
- **매수 / 매도 자동 판단** — 시스템 책임 경계에 명시적으로 없다
  (PROJECT_ORIGIN_INTENT §3 "매수/매도 API 자동화 없음").
- **자동 AI 토론 / AI API 직접 호출** — 본 STEP 까지의 모든 AI 사용은
  외부 채널 + 사용자 손으로 paste. AI API 직접 호출은 다른 STEP 으로 분리.

---

## 4. 중요한 사용자 결정 (불변 앵커)

본 결정은 다음 STEP 진입 전 흔들리면 안 된다. 흔들리면 KS-11
(의사결정 24시간 룰) 발동 — 새 데이터 / 근거를 ASSUMPTIONS 또는
PROJECT_ORIGIN_INTENT 에 기록 후 변경.

1. **사용자는 코스피 중심으로 투자한다.**
2. **KODEX200 / KOSPI 비교는 유효하다.** — 발굴 ETF 의 alpha 측정 기준.
3. **KOSDAQ 비교는 기본 비교 대상이 아니다.**
4. **AI 질문 / 답변은 반드시 기록되어야 한다.** — 본 STEP 의 핵심 동기.
   기록 없는 AI 토론은 향후 검증 불가능 → 운영 학습 자산 손실.
5. **AI 답변은 GPT / Gemini / Claude 로 분리 기록한다.** — 2026-05-21 추가.
   3 채널 답변을 같은 셀에 합쳐 저장하지 않는다. 채널별 해석 차이를 사후
   복기할 수 있어야 한다.

---

## 5. 이 문서의 사용 규칙

- 본 문서는 **새 STEP 진입 시 가장 먼저 읽는 1개 문서** 다.
- 본 문서는 설계서가 아니다 — 결정 변경 시 PROJECT_ORIGIN_INTENT.md 또는
  ASSUMPTIONS.md 를 변경하고, 본 문서는 그 변경을 짧게 반영한다.
- 본 문서는 시간이 지나면 **현재 STEP** 만 갱신한다 — "바로 다음 후보" 와
  "지금 멈춘 것" 의 큰 흐름은 분기 1회 사용자 본인이 검토한다.
