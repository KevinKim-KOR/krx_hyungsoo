# POC2 기능 인벤토리 (Feature Inventory)

작성일: 2026-05-27 / 갱신: 2026-07-05 (Market Flow ML Dataset + Baseline v1 Closeout — DONE)
성격: **현재까지 만든 기능을 누락 없이 기록하는 운영 인벤토리.** 새 기능 정의가
아니며, 운영 UI 정리의 기준점으로 사용한다.

본 문서는 ETF Constituents Source Diagnosis 1차의 §11 명시 산출물이다.

## 시장 우선 운영 원칙 (2026-07-03) + 직전 STEP (2026-07-05 DONE)

**직전 Step (DONE 2026-07-05)**: Market Flow ML Dataset + Baseline v1 Closeout — scikit-learn 1.9.0 승인/선언, KOSPI 역사 시계열 CLI 보강 (2870 행), real SQLite baseline 실측 (split 1756/572/592, latest_inference=ok). 상세: `docs/handoff/POC2_MARKET_FLOW_ML_DATASET_BASELINE_V1_CONCLUSION.md`.

본 인벤토리의 기능들은 **시장 우선 운영 원칙** (`docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md`) 하에서 역할이 고정된다:

- **시계열 SQLite / Market Risk Reference / 보유·후보 비교**: 주력 운영 흐름 (시장 → 정합성 → 필요한 상세).
- **Decision Draft Preview v1**: 선택적 drill-down 도구. 주력 운영 흐름 아님. 추가 확장 동결.
- **기존 AI Sessions**: 사용자 판단 기록의 중심. 별도 승인 시스템 신설 금지.
- **Market Flow ML Baseline v1 (DONE 2026-07-05)**: 시장 판단 근거 참조점수 (자동 매매 / AI Sessions 연결 금지).

---

## 1. 사용 가능 여부 표기 기준

| 표기 | 의미 |
|---|---|
| **사용 가능** | 운영 데이터로 기능 목적을 수행할 수 있음 |
| **부분 가능** | 화면/구조는 있으나 데이터 소스 또는 일부 조건이 미완성 |
| **사용 불가** | 기능 목적의 핵심 데이터가 없음 |
| **테스트용** | 운영 UI 에 그대로 둘지 재검토 필요 |
| **보류** | 다음 STEP 또는 BACKLOG 로 이동 |

---

## 2. 인벤토리 — 좌측 메뉴 기준

### 2.1 Dashboard

| 항목 | 값 |
|---|---|
| 기능명 | Dashboard |
| 현재 메뉴 위치 | 좌측 1번 |
| 기능 목적 | 시스템 상태 + 다른 화면 바로가기 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | 정적 + 다른 메뉴 링크 |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.2 Market Discovery

| 항목 | 값 |
|---|---|
| 기능명 | Market Discovery — ETF 후보 발굴 |
| 현재 메뉴 위치 | 좌측 2번 |
| 기능 목적 | KRX 상장 ETF universe 에서 TOP N 발굴 (정렬: 일간/1개월/3개월. 표시: 6개월/12개월/1년/3년) |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | `state/market/market_data.sqlite` (FDR universe + ETF 가격) |
| 운영 UI 포함 여부 | 포함 — TopControlsRow 1 카드(갱신+필터+전달 버튼) + 시장 배경 + 그리드 + 요약. |
| 응답 시간 (실측 2026-06-08) | warmup 후 0.85s — 직전 측정 2.4s 대비 65% 단축 (init_db 캐시 + name bulk loader) |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지. 추가 perf 가 필요하면 `fetch_price_history` 도 bulk 화 검토. |

### 2.3 Market Refresh (Market Discovery 카드)

| 항목 | 값 |
|---|---|
| 기능명 | 최신 시장 데이터 갱신 + KOSPI benchmark 수집 |
| 현재 메뉴 위치 | Market Discovery 화면 안 |
| 기능 목적 | FDR ETF universe + 가격 + KOSPI 지수 SQLite upsert |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | FDR (ETF/KR + KS11) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.4 Market Regime Card (시장 배경)

| 항목 | 값 |
|---|---|
| 기능명 | 시장 국면 판정 + KODEX200 / KOSPI 지표 카드 |
| 현재 메뉴 위치 | Market Discovery 상단 카드 |
| 기능 목적 | KODEX200 20/60거래일 수익률 + MA20/60 위치 기반 상승장/보합장/하락장/판정불가 라벨 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | etf_daily_price (069500) + market_benchmark_daily_price (KOSPI) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 1차 점수체계 — 운영 후 고도화 BACKLOG |

### 2.5 Benchmark Excess Return (후보 ETF 대비 KODEX200/KOSPI 초과수익)

| 항목 | 값 |
|---|---|
| 기능명 | 후보 ETF KODEX200 / KOSPI 대비 1m/3m 초과수익 (%p) |
| 현재 메뉴 위치 | Market Discovery 통합 후보 테이블 컬럼 |
| 기능 목적 | 후보가 시장 전체 상승에 따라간 건지 독립적인지 1차 정량 비교 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | compute_topn 응답 확장 (server-side) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.6 AI 투자세션 복사용 문구 (CopyTextCard)

| 항목 | 값 |
|---|---|
| 기능명 | 외부 AI 채널 (GPT/Gemini/Claude) 붙여넣기용 입력문 생성 |
| 현재 메뉴 위치 | Market Discovery 화면 안 |
| 기능 목적 | 시장 판정 + 후보 강도 + (선택) 구성종목/중복률 묶은 해석 요청문 |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 후) |
| 데이터 소스 상태 | 시장 판정 + 후보 강도 + 구성종목/중복률 모두 활성화 |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 검증 |

### 2.7 AI Sessions — 새 기록 저장 탭

| 항목 | 값 |
|---|---|
| 기능명 | 외부 AI 답변 (GPT/Gemini/Claude 3 채널) + 사용자 메모/판정 저장 |
| 현재 메뉴 위치 | 좌측 4번 (Market Discovery 다음) |
| 기능 목적 | AI 투자세션 기록 → 운영 학습 자산 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | `state/decision/decision_evidence.sqlite` (ai_session_records) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.8 AI Sessions — 기록 조회 탭

| 항목 | 값 |
|---|---|
| 기능명 | 저장된 AI 투자세션 목록 + 상세 (snapshot 포함) |
| 현재 메뉴 위치 | AI Sessions 화면 안 탭 |
| 기능 목적 | 과거 기록 검색 + 시장 문맥 / 구성종목 / 중복률 snapshot 재확인 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | 동일 ai_session_records |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.9 Decision Evidence (저장소)

| 항목 | 값 |
|---|---|
| 기능명 | AI Sessions 영속 저장소 (SQLite) |
| 현재 메뉴 위치 | (UI 직접 노출 없음 — AI Sessions 가 사용) |
| 기능 목적 | 질문 / 3 채널 답변 / 메모 / 판정 / 후보 snapshot / 필터 snapshot / market_context_snapshot / constituent_snapshot / overlap_snapshot |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | 자체 (SQLite, 마이그레이션 자동) |
| 운영 UI 포함 여부 | AI Sessions 경유 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 매매 결과 추적은 별도 STEP BACKLOG |

### 2.10 ETF Exposure 화면

| 항목 | 값 |
|---|---|
| 기능명 | ETF 구성종목 + 중복률 분석 화면 |
| 현재 메뉴 위치 | 좌측 3번 (Market Discovery 다음) |
| 기능 목적 | 후보가 정말 다른 테마인지 / 같은 종목 반복인지 판단 |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 후) |
| 데이터 소스 상태 | **`naver_stock_etf_component` 1차 채택** — 3 ETF smoke test PASS (HTTP 200, JSON list, 구성종목+비중+referenceDate). pykrx hold 유지. |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 운영 검증 |

### 2.11 ETF Constituents Refresh (POST /market/constituents/refresh)

| 항목 | 값 |
|---|---|
| 기능명 | 후보 ETF 구성종목 수집 API + K6 방어 (10개 cap / cache-first / 0.5s delay / 30s budget / partial / unavailable) |
| 현재 메뉴 위치 | ETF Exposure 의 [구성종목] 탭 |
| 기능 목적 | Naver Stock ETFComponent 에서 상위 구성종목 + 비중 수집 (해외형은 reuters_code / ISIN 보존) |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 후) |
| 데이터 소스 상태 | `naver_stock_etf_component` (1차) / pykrx hold (fallback 후보) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 검증 |

### 2.12 ETF Overlap Analysis (GET /market/constituents/analysis)

| 항목 | 값 |
|---|---|
| 기능명 | 집중도 (top 1/3/5/10) + 쌍별 중복률 + 반복 핵심 종목 |
| 현재 메뉴 위치 | ETF Exposure 의 [중복률] 탭 |
| 기능 목적 | ETF 간 중복 노출 정량 비교 (해외형은 reuters_code / ISIN 기반 매칭) |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 후) |
| 데이터 소스 상태 | etf_constituents 테이블 (Naver source 채워짐) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 검증 |

### 2.13 Holdings

| 항목 | 값 |
|---|---|
| 기능명 | 보유 종목 입력 / 평가 / refresh |
| 현재 메뉴 위치 | 좌측 5번 |
| 기능 목적 | 사용자 holdings 관리 + 시세 enrichment |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | holdings_latest.json + market_cache (Naver 시세) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.14 Approval / Telegram

| 항목 | 값 |
|---|---|
| 기능명 | Run 승인 / Telegram 발송 결과 |
| 현재 메뉴 위치 | 좌측 6번 |
| 기능 목적 | 승인 게이트 + 발송 결과 모니터링 |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | Run store (JSON SSOT) + Telegram 배관 |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

### 2.13a Short-term Momentum + KODEX200 단기 초과수익

| 항목 | 값 |
|---|---|
| 기능명 | 후보 ETF 별 5/10/20 거래일 수익률 + KODEX200 대비 초과수익 |
| 현재 메뉴 위치 | Market Discovery 통합 후보 응답 (candidates[].short_term_momentum) |
| 기능 목적 | 단기 흐름 + 단기 alpha 정량 재료 제공 (AI 해석용) |
| 사용 가능 여부 | **사용 가능** (2026-06-01 Closeout 1차) |
| 데이터 소스 상태 | etf_daily_price + 후보 ticker (KODEX200=069500 시계열 reuse) |
| 운영 UI 포함 여부 | 통합 후보 응답 — UI 노출 분리 표시는 BACKLOG |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 검증 |

### 2.13b 일간 급등/급락 데이터 품질 플래그

| 항목 | 값 |
|---|---|
| 기능명 | 일간 수익률 ±10% 임계 플래그 (data_quality.daily_return_check) |
| 현재 메뉴 위치 | Market Discovery candidates[].data_quality.daily_return_check |
| 기능 목적 | 가격 데이터 / 분배금/권리락 / 단일 종목 급등 영향 확인 유도 |
| 사용 가능 여부 | **사용 가능** (2026-06-01 Closeout 1차) |
| 데이터 소스 상태 | etf_daily_price (마지막 2 거래일) |
| 운영 UI 포함 여부 | 통합 후보 응답 — UI 노출 BACKLOG |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 임계 재검토 |

### 2.13c NAV / 괴리율 데이터 품질 체크

| 항목 | 값 |
|---|---|
| 기능명 | NAV / 시장가격 / 괴리율 + 3%/5% 임계 플래그 |
| 현재 메뉴 위치 | Market Discovery 후보 테이블 NAV 컬럼 + ETF Exposure NAV 카드 + Holdings Evidence Card NAV 줄 + Data Status 전체 ETF NAV 표 |
| 기능 목적 | 데이터 품질 확인용 (매수/매도 판단 X) |
| 사용 가능 여부 | **사용 가능** (2026-06-08 NAV / Discount Display FIX 로 표시 매트릭스 완료) |
| 데이터 소스 상태 | Naver `finance.naver.com/api/sise/etfItemList.nhn` universe 1회 호출 + TTL 30s + stale 재사용. `etf_nav_daily` 일괄 upsert (source=`naver_etf_item_list`). 1136 ETF 실측. |
| API 진입점 | refresh: market refresh hook 자동 / 수동 CLI. 조회: `GET /market/nav-discount/latest` (read-only) + 기존 Market Discovery / Holdings Evidence API 의 `nav_discount` payload. |
| 운영 UI 포함 여부 | Market Discovery / ETF Exposure / Holdings Evidence / Data Status 4 화면 표시 |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | (선택) NAV / 괴리율 시계열 누적 → 위험 감지 축 2 의 1차 후보로 사용 검토 |

### 2.13d Holdings × Market Discovery Evidence (보유 vs 시장)

| 항목 | 값 |
|---|---|
| 기능명 | 보유 ETF × Market Discovery 후보 / 시장 국면 / 단기 흐름 / 구성종목 중복 / NAV 비교 |
| 현재 메뉴 위치 | Holdings 화면의 `HoldingsMarketEvidenceCard` + GenerateDraft [판단 사유] 1줄 + GET `/holdings/market-evidence/latest` (read-only API) |
| 기능 목적 | 보유 ETF 가 현재 시장 데이터 기준 어느 위치인지의 raw evidence (매수/매도/교체 판단 X) |
| 사용 가능 여부 | **사용 가능** (2026-06-03 Holdings × Market Discovery Evidence 1차) |
| 데이터 소스 상태 | holdings_latest.json + market_data.sqlite (compute_topn + KODEX200 시계열) + etf_constituents store (Strict Cache-only) + etf_nav store + market_cache |
| 운영 UI 포함 여부 | 포함 (사용자 [Evidence 조회] 버튼 클릭 시 호출 — page load auto X / polling X) |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 운영 데이터 누적 후 evidence_notes 표현 / 보유 ETF 구성종목 외부 source 채택 검토 |

### 2.15 Data Status

| 항목 | 값 |
|---|---|
| 기능명 | 전체 ETF NAV / 시장가 / 괴리율 조회 화면 |
| 현재 메뉴 위치 | 좌측 7번 |
| 기능 목적 | 저장된 etf_nav_daily 의 전체 ETF NAV / 시장가 / 괴리율을 검색 / 필터 / 정렬 (조회 전용) |
| 사용 가능 여부 | **사용 가능** (2026-06-08 NAV / Discount Display FIX 로 placeholder → 운영 화면 전환) |
| 데이터 소스 상태 | `GET /market/nav-discount/latest` (read-only). Naver universe 1회 호출 결과 SQLite 저장값 — 외부 source 호출 0건 |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | 현재 상태 유지 |

### 2.16 ML 최소 데이터 레인 (etf_ml_feature_daily / market_risk_feature_daily)

| 항목 | 값 |
|---|---|
| 기능명 | ML baseline v0 입력용 daily feature dataset |
| 현재 메뉴 위치 | 좌측 4번 ETF Exposure 화면 안 `MLTimeseriesReadinessCard` (조회) + CLI 적재 |
| 기능 목적 | 상승 후보 발굴 + 위험 구간 분류용 feature row 적재 — ML 모델 / 라벨 / 예측 X |
| 사용 가능 여부 | **사용 가능** (2026-06-08 ML 최소 데이터 레인 1차 DONE) |
| 데이터 소스 상태 | SQLite 2 신규 테이블 (`etf_ml_feature_daily` PK=(asof,ticker), `market_risk_feature_daily` PK=asof). 입력은 기존 `etf_daily_price` / `etf_nav_daily` / `market_benchmark_daily_price` 만 (외부 source 0건). |
| API 진입점 | 적재: CLI `scripts/generate_ml_features.py` 만. 조회: `GET /ml/readiness/latest` (read-only row count / latest asof). |
| 운영 UI 포함 여부 | ML readiness 7축 표시 (`MLTimeseriesReadinessCard`). CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목 가격 시계열은 표시 X (BACKLOG). |
| 실측 (2026-06-08) | 1137 ETF × 60거래일 → 65,691 ETF row + 60 market risk row / CLI 4.46초 |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | ML baseline v0 STEP — 본 dataset 입력으로 상승 후보 점수화 + 위험 구간 분류 |

### 2.17 ML Feature Sanity Check (etf/market_risk feature 검산)

| 항목 | 값 |
|---|---|
| 기능명 | ML feature dataset 의 계산 정합성 / 데이터 품질 검산 |
| 현재 메뉴 위치 | 좌측 7번 Data Status 화면 `MLFeatureSanityCard` (조회) + CLI 실행 |
| 기능 목적 | ML baseline v0 입력 직전 데이터 품질 보증 — coverage / calculation / NAV join / risk proxy 4종 |
| 사용 가능 여부 | **사용 가능** (2026-06-08 ML Feature Sanity Check DONE) |
| 데이터 소스 상태 | etf_ml_feature_daily / market_risk_feature_daily / etf_nav_daily / etf_daily_price read-only. 외부 source 호출 0건. |
| API 진입점 | 갱신: CLI `scripts/check_ml_feature_sanity.py` 만 (재계산은 CLI에서만 발생). 조회: `GET /ml/feature-sanity/latest` (snapshot 만 read). |
| 허용 오차 / 정책 | calculation: `abs_tol=1e-4 + rel_tol=1e-4` (사용자 결정 b). risk proxy 이상치: null 비율 + all-null per asof 만 (사용자 결정 f). 위험 threshold / 라벨 / 매수·매도 판단 0건. |
| 실측 (2026-06-08, FIX r3 후) | sanity_status=warn / etf_rows=65,691 / 60거래일 / checked 10 ticker / calc 0 error / future_nav_join=0 / risk all-null=0 / warning 3건 (NAV unavailable 2 + ticker 1137 중 row 누락 69건 신규 감지). |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | ML baseline v0 룩백 검증 (DONE, §2.18). NAV 일별 적재 BACKLOG. |

### 2.18 ML Baseline v0 룩백 검증 (candidate / risk baseline)

| 항목 | 값 |
|---|---|
| 기능명 | ML feature dataset 의 과거 구간 baseline 룩백 검증 — 상승 후보 발굴 + 위험 구간 감지 |
| 현재 메뉴 위치 | 좌측 7번 Data Status 화면 `MLBaselineV0Card` (조회) + CLI 실행 |
| 기능 목적 | feature 가 과거 구간에서 단순 baseline 보다 의미 있었는지 확인. 실시간 매수/매도 판단 / 위험 알림 / 조정장 확정 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-11 ML Baseline v0 룩백 검증 DONE) |
| 데이터 소스 상태 | etf_ml_feature_daily / market_risk_feature_daily read-only. 외부 source 호출 0건. ML 학습 0건. |
| API 진입점 | 갱신: CLI `scripts/run_ml_baseline_v0.py` 만 (재계산은 CLI에서만 발생). 조회: `GET /ml/baseline-v0/latest` (snapshot read-only). |
| 정책 / 사용자 결정 | (a) candidate top group = top quintile 20%. (a) risk group split = market composite tercile 1/3. (a) horizon tail = max horizon 20d 제외. 위험 threshold / 조정장 label 0건. |
| 누수 방지 | structural: future_* target 은 idx + horizon 의 close 만 사용 (구조적 누수 불가). horizon tail 모든 horizon 의 target 측정 가능 구간만 평가. time order ASC 보장. leakage_checks.feature_future_data_leakage_detected = False. |
| 실측 (2026-06-11) | status=ok / feature 60거래일 / 평가 40거래일 / 1099 ticker. candidate top group 5/10/20d return = 3.4% / 5.5% / 13.5% vs universe median 1.1% / 2.1% / 4.7%. risk high vs low future drawdown 10d = -8.1% vs -3.4%. drawdown_capture_rate 10d = 1.44. |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | (1) NAV 일별 적재 / 5년 backfill. (2) 시계열 rolling window 분해. (3) §6.6 제외 source BACKLOG. 본 STEP 이 점수판이 아닌 룩백 baseline 임 — ML 모델 학습 / threshold 확정은 별도 STEP. |

### 2.19 ML Baseline Evidence Draft Integration (보조 evidence)

| 항목 | 값 |
|---|---|
| 기능명 | 저장된 ML baseline v0 룩백 report 를 GenerateDraft / AI Sessions draft 에 보조 evidence 로 연결 |
| 현재 메뉴 위치 | GenerateDraft 흐름 자동 통합 (draft_payload.`ml_baseline_evidence_snapshot` + draft_message [판단 사유] 1줄). 추가로 AI Sessions / Decision Evidence 저장 경로에도 `ai_session_records.ml_baseline_evidence_snapshot_json` 컬럼으로 영속화. 별도 화면 진입점 없음. |
| 기능 목적 | 판단 초안 안에서 ML baseline 결과의 상태 / 검증 기간 / 후보 발굴 근거 / 위험 패턴 근거 / 한계 / AI 외부 context checklist 를 보조 evidence 로 노출. 매수/매도/추천/현금비중/조정장/위험 알림 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-11 DONE) |
| 데이터 소스 상태 | `state/ml/ml_baseline_v0_report_latest.json` 직접 read. baseline 재계산 / feature 재생성 / 외부 source 호출 / ML 학습 / HTTP self-call 0건. |
| API 진입점 | 없음 (draft 생성 시점 자동 통합). 진단용은 §2.18 `GET /ml/baseline-v0/latest`. |
| 정책 / 사용자 결정 | (a) JSON 파일 직접 read. (a) stale 기준 = `feature_asof_range.end` 가 오늘(KST) 대비 **7일 초과**. (a) draft 문구 반영 위치 = draft_message [판단 사유] bullet. |
| draft_payload 신규 키 | `ml_baseline_evidence_snapshot` = {status / report_status / report_generated_at / feature_asof_range / evaluated_asof_range / candidate_summary / risk_summary / leakage_summary / limitations / external_context_checklist (7건) / message}. |
| AI Sessions 저장 (FIX r2) | `ai_session_records.ml_baseline_evidence_snapshot_json` 컬럼 + 자동 ADD COLUMN 마이그레이션. POST `/decision/sessions` 가 필드 수용, GET 응답에 그대로 반환. |
| 데이터 계약 단일화 (FIX r3) | `GET /ml/baseline-v0/evidence-snapshot` 신규 — GenerateDraft 와 동일한 정규화 shape 반환 (status / candidate_summary / risk_summary / leakage_summary / limitations / external_context_checklist). frontend `AISessionsCreateTab` 가 draft 에 snapshot 없으면 본 API 결과로 fallback. fetch 실패 시 status="error" 정규화 snapshot 으로 채움 (silent fallback 금지). |

### 2.20 UI 안전실행 — ML evidence 갱신 background job

| 항목 | 값 |
|---|---|
| 기능명 | Data Status 화면의 "ML evidence 갱신 실행" 버튼 + 3단계 background runner (feature → sanity → baseline) + 단계별 상태 표시. |
| 현재 메뉴 위치 | 좌측 7번 Data Status 화면 최상단 `MLEvidenceRefreshCard`. |
| 기능 목적 | 기존 CLI 3종을 화면에서 안전하게 트리거. HTTP 응답은 즉시 반환되고 실제 실행은 background thread / FastAPI BackgroundTasks. 매수/매도/추천/현금/조정장/위험알림 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-11 DONE). |
| 데이터 소스 상태 | 기존 SQLite (etf_ml_feature_daily / market_risk_feature_daily) read/write. 외부 source 호출 0건. ML 학습 0건. baseline 산식 변경 0건. |
| API 진입점 | 실행: `POST /ml/jobs/evidence-refresh` (background 시작, 즉시 반환). 조회: `GET /ml/jobs/latest` (read-only, job 실행 X). |
| CLI 경로 유지 | `scripts/generate_ml_features.py` / `scripts/check_ml_feature_sanity.py` / `scripts/run_ml_baseline_v0.py` 그대로 동작. UI 는 CLI 대체가 아니라 운영 편의 개선. |
| 중복 실행 차단 | in-process `threading.Lock` + on-disk `state/ml/ml_job_status_latest.json` status 검사. 중복 POST 는 새 job 안 만들고 already_running 응답. |
| Stale lock 자동 해제 | snapshot 의 PID + last_heartbeat_at 기준 — PID 죽었거나 heartbeat 10분 초과 시 stale 자동 해제 후 새 job 허용 (사용자 결정). |
| 실패 격리 | 단계 실패 시 이후 단계 skipped + 전체 failed. **기존 snapshot 3종 삭제하지 않음** (마지막 성공 결과 보존, AC-6). |
| Artifact | `state/ml/ml_job_status_latest.json` (gitignored, UI 실행마다 갱신). 기존 feature/sanity/baseline snapshot 은 단계 성공 시에만 덮어쓰기. |
| 실측 (2026-06-11) | uvicorn 직접 호출 — POST 2.6ms accepted / 중복 2.2ms already_running / 단계 polling 정확 / 운영 SQLite 최종 success (evaluated_days=43). |
| 테스트용/임시 여부 | 아님 — 운영용. |
| 다음 조치 | schedule 기반 자동 실행 / 실행 히스토리 / stale 알림 deeplink 는 BACKLOG. |

### 2.21 3-PUSH Message Contract 정렬 (PUSH-1 / PUSH-2 / PUSH-3 message_text 계약)

| 항목 | 값 |
|---|---|
| 기능명 | 하루 3종 PUSH 메시지의 `message_text` 계약 정리 — `market_briefing` / `holdings_briefing` / `spike_or_falling_alert`. |
| 현재 메뉴 위치 | Approval / Telegram 화면의 `ThreePushDraftCard` (PUSH-1 / PUSH-3 진입점, 임시 위치) + Holdings 화면의 "초안 생성" 버튼 (PUSH-2 재정의). |
| 기능 목적 | 기존 Run → Approval → OCI → Telegram 단일 경로를 유지하면서 3종 PUSH 메시지가 각각 어떤 입력을 쓰고 어떤 문구를 생성하는지 구분 가능하게 만든다. 새 PUSH API / Telegram 직접 발송 / 자동 발송 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-12 DONE). |
| 데이터 소스 상태 | 외부 source 호출 0건. ML baseline evidence snapshot (정규화 read-only) + Market Discovery TopN (`compute_topn`) + universe_momentum_latest.json (기존 PUSH 3 신호 재사용). |
| API 진입점 | PUSH-1: 기존 `POST /runs/generate` + body `input_data.push_kind="market_briefing"`. PUSH-3: 동일 endpoint + `push_kind="spike_or_falling_alert"`. PUSH-2: 기존 `POST /runs/generate-from-holdings` (재정의, holdings 데이터 의존). **신규 PUSH endpoint 0건 — 지시문 §3 / §11 별도 PUSH API 신설 금지선 준수 (FIX r2 — 설계자 수용)**. |
| Run 모델 확장 | `Run.push_kind: Optional[str]` 추가 — `"holdings_briefing"` / `"market_briefing"` / `"spike_or_falling_alert"`. 과거 run 은 None 허용 (하위호환). delivery / OCI consumer 는 본 필드를 읽지 않음 — Telegram 본문은 `message_text` 단일 소스 그대로. |
| message_text 단일 소스 | backend 가 generate 시점에 빌드해 Run 에 저장. frontend / preview / OCI handoff / Telegram 모두 동일 문자열. frontend 본문 조립 0건 (AC-2). |
| 승인 게이트 유지 | PENDING_APPROVAL → DELIVERING → COMPLETED / FAILED 흐름 변경 0건. 본 카드 자체가 Telegram 발송 트리거 X — 인간 승인 후 기존 OCI handoff 경로 사용 (AC-3 / AC-7). |
| delivery fallback 안전 | message_text 누락된 PUSH-1/3 run 이 holdings builder 로 rebuild 되어 raw recommendations 발송되던 분기 차단 (`DeliveryError` raise). |
| 실측 (2026-06-12 FIX r2 후) | `POST /runs/generate` + `input_data.push_kind` 분기 — PUSH-1 496자 / PUSH-3 213자. 양쪽 모두 PENDING_APPROVAL + push_kind 전파 + raw JSON 0건. 신규 PUSH endpoint 2개는 405 (제거 확인). |
| 테스트용/임시 여부 | `ThreePushDraftCard` 의 UI 위치는 임시 진입점 — 발송 시간 / UX 확정은 별도 STEP (지시문 §13). builder / draft / API 계약 자체는 운영용. |
| 다음 조치 | (1) 하루 3회 발송 시간 + 승인 UX 확정. (2) PUSH-1 뉴스 source 도입 여부. (3) PUSH-3 개별 주식 universe 확장 여부. (4) ThreePushDraftCard 정식 화면 위치. 모두 BACKLOG. |
| factor_signals 신규 scope | `ml_baseline_evidence` (1건). is_available=True 면 reason_text, False 면 fallback_text. |
| status 5종 | ok / warn / stale / unavailable / error (report 부재 / 손상 / errors 존재 / 7일 초과 자동 판정). |
| 외부 context checklist (AI 확인용) | CNN Fear&Greed / VIX·VKOSPI 유사 / 원유 / USD-KRW / 미국장·선물 / 지정학 / 한국장 영향 업종 — 7건. 외부 수집 구현 0건 (질문 목록만). |
| 실측 (2026-06-11) | 운영 SQLite 기준 status=ok / candidate evaluated_days=40 / risk evaluated_days=40 / leakage 0 / external checklist 7건 노출. |
| 테스트용/임시 여부 | 아님 — 운영용 |
| 다음 조치 | report stale 시 CLI 재실행 안내 (사용자 결정). 5년 backfill 후 evidence 신호 강도 시계열 분해 (BACKLOG). |

---

### 2.24 3-PUSH Context Cleanup (KS-10 trigger/near 4건 해소)

| 항목 | 값 |
|---|---|
| 기능명 | 구조 안정화 STEP — 직전 STEP 의 KS-10 trigger / near 4건을 helper 모듈 분리로 모두 해소. 기능 추가 0건. |
| 현재 메뉴 위치 | (UI 없음 — 코드 구조 변경) |
| 기능 목적 | 직전 STEP (3-PUSH Message Text Runtime Evidence 반영) 의 PARTIALLY_VERIFIED 판정 사유 (push_context.py 798 trigger / draft_message.py 616 near) 해소 + 기존 보유 KS-10 트리거/near (market_topn.py 613 / diagnose_nav_discount_source.py 984) 도 함께 해소. |
| 사용 가능 여부 | **사용 가능** (2026-06-14 DONE). |
| 데이터 소스 상태 | 변경 없음. |
| API 진입점 | 변경 없음. 신규 endpoint 0건. |
| 분리 결과 (before → after, PowerShell 측정 기준) | `app/push_context.py` 798→72 / `scripts/diagnose_nav_discount_source.py` 984→524 / `app/draft_message.py` 616→299 / `app/market_topn.py` 613→347. |
| 신규 모듈 | `app/push_context_format.py` (59) / `push_context_market.py` (266) / `push_context_holdings.py` (202) / `push_context_spike.py` (191) / `app/draft_message_focus.py` (216) / `app/market_topn_helpers.py` (234) / `scripts/diagnose_nav_discount_source_helpers.py` (391). |
| 호환성 | 기존 import 경로 (`from app.push_context import ...` / `from app.draft_message import ...` / `from app.market_topn import ...`) 모두 유지. 테스트 / 호출자 변경 0건. |
| KS-10 trigger / near 잔여 (git-tracked 기준) | **0건** (backend `.py` 최대 524, frontend `.tsx` 최대 691, tests `.py` 최대 924). |
| 테스트 | pytest **534 passed** (회귀 0). black / flake8 (신규 파일 0 warning) / Next.js build PASS. |
| 테스트용/임시 여부 | 아님 — 구조 안정화 (Cleanup STEP). |
| 다음 조치 | 다음 기능 STEP 진입 가능 — OCI runtime source / 하루 3회 발송 시간 / runtime refresh endpoint / 뉴스 source / ThreePushDraftCard 정식 위치 중 사용자 결정. |

---

### 2.23 3-PUSH Message Text Runtime Evidence 반영 (PUSH-1 / PUSH-2 / PUSH-3 본문 풍부화)

| 항목 | 값 |
|---|---|
| 기능명 | `runtime_package` + `push_context` 의 실제 evidence (미국 지수 실제 등락률 / Market Discovery 상위·하위 흐름 / ML baseline 룩백 / holdings × runtime quote / universe momentum 후보) 를 PUSH-1/2/3 `message_text` 에 사람이 판단에 쓸 수 있는 수준으로 노출. |
| 현재 메뉴 위치 | Approval / Telegram 화면의 `ThreePushDraftCard` (PUSH-1/3 진입) + Holdings 화면 (PUSH-2 진입). 직전 STEP 의 진입점 그대로. |
| 기능 목적 | 직전 STEP 까지의 본문은 "조회 가능 지수" / "score" 같이 사용자가 판단에 사용하기 부족한 표현이었다. 본 STEP 으로 실제 수치 + 관찰 문장 + market_view 연결까지 사용자가 1회 읽고 판단할 수 있게 한다. 매수/매도/추천/현금/조정장/위험알림 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-14 DONE). |
| 데이터 소스 상태 | 직전 STEP 의 runtime probe 그대로. 외부 source 호출 0건. 신규 dependency 0건. ML 산식 / Market Discovery 산식 / NAV·괴리율 산식 / universe momentum 산식 변경 0건. |
| API 진입점 | PUSH-1: `POST /runs/generate + input_data.push_kind="market_briefing"`. PUSH-3: 동일 endpoint + `push_kind="spike_or_falling_alert"`. PUSH-2: `POST /runs/generate-from-holdings`. **신규 PUSH 전용 endpoint 0건**. |
| message_text 생성 흐름 | `pc_evidence + runtime_snapshot → push_context (observations 에 실제 값 + text) → message builder (push_context 우선 + 기존 evidence 섹션 fallback) → message_text`. |
| PUSH-1 신규 섹션 | `[밤사이 미국 시장 (runtime probe)]` 실제 close + change_pct + 섹터 해석 hint. `[국내 시장 내부 신호 (Market Discovery)]` 상위/하위 1줄. `[위험 패턴 참고 (ML baseline 룩백)]` 1줄. |
| PUSH-2 신규 섹션 | `[보유 종목 관찰 포인트]` (holding 별 runtime quote / 비중 / Market Discovery overlap / 국내 기준선 안내). `[시장 흐름 연결 (market_view)]` (밤사이 미국 + Market Discovery 흐름). `[리뷰 포인트]`. |
| PUSH-3 신규 섹션 | `[universe momentum 관찰 (push_context 기반)]` 각 item 마다 수익률 근거 / 방향 / data_quality / holdings overlap 4축 표시. score 단독 표시 폐기 (AC-5). |
| UI placeholder 방지 | runtime probe 실패한 indices 는 행 자체 생략 / 전부 실패면 섹션 자체 생략. "unavailable" / "조회 실패" 본문 substring 0건. |
| KS-10 영향 | `app/push_context.py` 247→**798 라인** (백엔드 핵심 모듈 ≥650 trigger). 본 STEP 범위 안에서 자연 증가 — 후속 Cleanup STEP 으로 분리 필요 (사용자 확인). |
| 실측 (2026-06-14 PC stub probe) | PUSH-1 본문에 NASDAQ +0.85% / SPX +0.41% / SOX +1.25% 실제 값 + 반도체 강세 hint + Market Discovery 흐름 + ML baseline 43거래일 룩백 모두 노출. PUSH-3 본문에 KODEX 200 score +38.60 / ACE 코리아AI테크핵심산업 1d +0.92%, 20d +32.77% · 방향 up · data_quality 이상 없음 · 보유 종목과 겹치지 않음 형태로 풍부 1줄/item. PUSH-2 본문에 KODEX 200 (069500): runtime 시세 +0.42% (가격 36,000) + 국내 기준선 안내 + market_view 1줄 연결. |
| 테스트 | pytest **534 passed** (+15 신규 / 회귀 0). `tests/test_three_push_message_text_runtime_evidence.py` 15건. black / flake8 / Next.js build PASS. |
| 테스트용/임시 여부 | 아님 — 운영용. PC 검증 단계. OCI runtime 으로 옮길 때 본 builder 가 그대로 재사용된다 (산식 변경 0건). |
| 다음 조치 | (1) KS-10 Cleanup — push_context 책임 분리. (2) OCI runtime source 도입. (3) 하루 3회 발송 시간 / 자동 발송 UX. (4) 뉴스 source 도입. (5) ThreePushDraftCard 정식 화면 위치. |

---

### 2.22 3-PUSH Runtime Package PC 검증 (three_push_runtime_package.v1)

| 항목 | 값 |
|---|---|
| 기능명 | PC 에서 `three_push_runtime_package.v1` 구조를 실제 evidence + runtime probe 로 생성해 Approval/Telegram preview 에서 상태 확인 가능한 상태까지 검증. |
| 현재 메뉴 위치 | Approval / Telegram 화면의 `RunPanel` 안 `RuntimePackageStatusCard` (run 카드 아래). PUSH-1/3 진입은 기존 `ThreePushDraftCard` / PUSH-2 진입은 기존 Holdings 화면. |
| 기능 목적 | 후속 OCI runtime 이 그대로 받을 수 있는 `runtime_package` (pc_evidence_snapshot + runtime_snapshot + push_context + message_contract + safety_guards + generation_status) 를 PC 에서 먼저 생성하고 검증. |
| 사용 가능 여부 | **사용 가능** (2026-06-13 DONE). |
| 데이터 소스 상태 | 기존 evidence builder 결과 (산식 변경 0건) + PC runtime probe 2종. 국내 시세: Naver polling endpoint. 미국 지수 3종: Yahoo Finance chart endpoint (cookie jar priming 으로 rate-limit 회피). 신규 dependency 0건 (`urllib` + `json` + `http.cookiejar` 만). |
| API 진입점 | PUSH-1: `POST /runs/generate + input_data.push_kind="market_briefing"`. PUSH-3: 동일 endpoint + `push_kind="spike_or_falling_alert"`. PUSH-2: `POST /runs/generate-from-holdings` (기존 유지 — Q3 사용자 결정, holdings 데이터 의존성). **신규 PUSH 전용 endpoint 0건**. |
| draft_payload 키 추가 | `draft_payload.runtime_package` 1건 신규 (Q4 — 기존 키 유지). 내부 구조: schema_version / package_id / created_at / asof_date / timezone / source_mode / push_kind / data_cutoff / pc_evidence_snapshot / runtime_snapshot / push_context / message_contract / safety_guards / generation_status. |
| runtime probe cache | `state/runtime/three_push_runtime_probe_latest.json` (gitignored). TTL 30분 (Q5 — refresh endpoint 없음). cache hit → probe 0건, miss/TTL 만료 → probe 1회 + 저장, 손상 → fall-through 후 재조회. |
| 미국 지수 source | Yahoo Finance chart endpoint `query1.finance.yahoo.com/v8/finance/chart/{^IXIC|^GSPC|^SOX}?interval=1d&range=5d`. `finance.yahoo.com` 홈 1회 priming 으로 cookie 받음 (rate-limit 회피). 개별 timeout 3초. |
| 국내 시세 source | Naver `polling.finance.naver.com/api/realtime/domestic/stock/{ticker}`. 기존 `naver_etf_universe_fetcher.py` 와 동일 dependency 범위. |
| generation_status 정책 | ok / partial / failed. 필수 evidence (push_kind 별) 있음 + runtime probe 정상 → ok. 필수 evidence 있음 + runtime probe 일부 실패 → partial. 필수 evidence 누락 → failed. |
| UI placeholder 방지 | `RuntimePackageStatusCard` 가 `kr.status==="unavailable"` / `us.status==="unavailable"` 일 때 해당 행 자체 생략. message_text 에 "unavailable" placeholder substring 0건 (라이브 검증). |
| handoff JSON 영향 | `app/delivery.py` 변경 0건. `store.write_handoff_artifact` 가 draft_payload 전체를 저장하므로 runtime_package 자동 포함. 기존 OCI consumer 는 `message_text` 만 읽어도 깨지지 않음 (계약 §10). |
| 실측 (2026-06-13 KST 오전) | Nasdaq close=25,888.844 +0.70% / SPX close=7,431.46 +0.65% / SOX close=13,371.47 +9.42% / KODEX 200 price=129,270 +4.38% / KODEX 코스닥150 price=18,015 +2.15%. PUSH-1/3 `POST /runs/generate` generation_status=ok / PUSH-2 `/runs/generate-from-holdings` generation_status=ok + message_text 2,507자 = runtime_package.message_contract.message_text (AC-6). |
| 테스트 | pytest 519 passed (+29 신규 / 회귀 0, 직전 STEP 490 → 519, FIX r6 후). `tests/test_runtime_package.py` 22건 + `tests/test_runtime_probe_cache.py` 7건. black / flake8 / Next.js build PASS. |
| FIX r2 (검증자 1차 REJECTED 후속) | (A-1 (1)) message_text 생성 흐름을 `runtime_package → push_context → message_text` 로 정렬. 신규 모듈 `app/push_context.py`. PUSH-1 에 `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션 추가 (probe ok 시). PUSH-3 spike_view 기반 섹션. PUSH-2 market_view 가 §7.2 충족. (A-1 (2)) holdings_briefing generation_status 검증에 market_view/market_discovery 확인 추가. (B-1) broad exception → (OSError, TimeoutError). (B-6) cache 정책 — 두 snapshot 모두 failed 면 저장 안 함. |
| FIX r3 (검증자 2차 REJECTED 후속) | (A-1) push_context view 빌더가 의미 있는 관찰 0건이면 빈 dict 반환 — `bool(market_view)` 가 False 가 되어 holdings_briefing 의 §7.2 조건 정상 차단. `_evaluate_generation_status` 가 `unavailable` runtime 도 warning 으로 처리 → partial 노출 (이전엔 ok 통과). `build_runtime_package` 가 failed package 의 `message_contract.message_text` 를 빈 문자열로 강제 (정상 본문 차단). (A-3) STATE_LATEST 라인 수 실측 갱신. 신규 테스트 4건. |
| FIX r4 (검증자 3차 REJECTED 후속) | (A-1 / B-1) `generate_draft_from_holdings` 의 message_contract 동기화 단계가 FIX r3 의 "failed package 본문 비움" 안전장치를 무력화하던 문제 해소 — 동기화 시점에 generation_status.status 확인 후 failed 면 본문 빈 문자열 유지. (A-3) STATE_LATEST §1 안의 stale 라인 수 정정. 신규 테스트 1건. |
| FIX r5 (검증자 4차 REJECTED 후속) | (A-1 / B-1 / B-6) `Run.message_text` (실제 승인/preview/발송 단일 소스) 도 `runtime_package.generation_status == "failed"` 이면 None 으로 비운다. PUSH-1/2/3 모두 동일 가드 (대칭성). Run.status 는 PENDING_APPROVAL 유지. RunPanel preview 가 정적 fallback 으로 자연스럽게 떨어져 정상 본문이 보이지 않고 RuntimePackageStatusCard 의 failed 상태가 함께 표시되어 사용자가 reject 결정 가능. (A-3) POC2_B_NEXT_ACTIONS.md 의 stale 라인 수 5건 정정. 신규 테스트 2건. |
| FIX r6 (검증자 5차 REJECTED 후속) | (A-1 / B-1 / B-6) `app/delivery.py:deliver()` 의 holdings legacy fallback 분기가 FIX r5 의 Run.message_text=None 가드를 무력화하던 문제 해소 — fallback 진입 전에 runtime_package.generation_status=failed 사전 확인 가드 추가, failed 면 DeliveryError 명시 차단 (PUSH-1/3 의 기존 가드 패턴과 정렬). PUSH-2 holdings 도 failed package 일 때 OCI 로 정상 본문이 발송되지 않는다 (계약 §12 일관 적용). (A-3) `delivery.py` 변경 0건 표기를 233→251 라인 으로 정정. 신규 테스트 1건. |
| 테스트용/임시 여부 | 아님 — 운영용 (PC 검증 게이트). 발송 시간 / 자동 발송은 별도 STEP. |
| 다음 조치 | (1) OCI runtime source 도입. (2) 하루 3회 발송 시간 + 자동 발송 UX. (3) runtime source 수동 refresh endpoint. (4) 뉴스 source 도입. (5) `ThreePushDraftCard` 정식 화면 위치. 모두 BACKLOG. |

---

### 2.25 PC-to-OCI 3-PUSH Evidence Package Sync

| 항목 | 값 |
|---|---|
| 기능명 | PC 에서 생성한 `three_push_runtime_package.v1` package 3종 + manifest 를 OCI 지정 경로로 동기화. OCI crontab runner 가 이후 단계에서 읽을 수 있는 package 공급 경로 확보. |
| 현재 메뉴 위치 | (UI 없음 — 수동 CLI 스크립트) |
| 기능 목적 | OCI crontab runner 구현 전에 PC 에서 만든 최신 3-PUSH package 를 OCI 가 읽을 수 있는 위치로 동기화한다. crontab runner 가 없을 때 partial/failed 없이 evidence package 를 먼저 공급한다. |
| 사용 가능 여부 | **사용 가능** (2026-06-15 DONE). |
| 데이터 소스 상태 | 기존 `draft_three_push.generate_*_via_generic` (PUSH-1/3) + `draft._build_holdings_payload` (PUSH-2) 재사용. 신규 external source / 신규 DB / Telegram 발송 / SQLite 이전 / scheduler 0건. |
| CLI 진입점 | `python scripts/sync_three_push_packages.py [--dry-run] [--export-only]` |
| 환경변수 | `OCI_SSH_TARGET` (필수) / `THREE_PUSH_REMOTE_PACKAGE_DIR` (권장) 또는 `OCI_REMOTE_INBOX` (fallback 자동 구성) / `OCI_SSH_KEY_PATH` (선택). |
| local artifact | `state/three_push/packages/latest_{push_kind}.json` 3종 + `manifest.json`. |
| OCI remote | `~/krx-alertor/state/three_push/packages/` (THREE_PUSH_REMOTE_PACKAGE_DIR 기준). |
| atomic 업로드 | package 3종 → *.tmp 업로드 → mv rename. manifest 는 package 3종 교체 후 마지막에 교체. |
| OCI read verification | `scripts/verify_three_push_packages_oci.py` 를 OCI 에 SCP 후 원격 실행. manifest schema / push_kind 3종 / package schema / generation_status / token 비노출 검증 후 JSON 출력. stdlib 만 사용 (OCI 추가 패키지 설치 불필요). |
| sync status 기록 | `state/three_push/sync_status_latest.json` — status (success/partial/failed) + export 결과 + OCI upload 결과 + verification 결과. |
| safety_guards | token / chat_id 를 package / manifest / sync log 에 절대 포함하지 않도록 재귀 검증 (`_assert_no_sensitive_keys`). |
| 테스트 | pytest **534 passed** (회귀 0). black / flake8 PASS. py_compile PASS. |
| 테스트용/임시 여부 | 수동 실행 스크립트 — 운영용. |
| 다음 조치 | 현재 상태 유지. OCI crontab runner 에서 소비. |

---

### 2.26 OCI 3-PUSH Crontab Runner & Telegram Autosend

| 항목 | 값 |
|---|---|
| 기능명 | OCI 에서 crontab 으로 PUSH-1 / PUSH-2 / PUSH-3 를 자동 실행하고 조건 충족 시 Telegram 발송. |
| 현재 메뉴 위치 | (UI 없음 — OCI crontab 실행 스크립트) |
| 기능 목적 | PC 에서 sync 한 package 를 OCI 가 읽어 하루 3회 Telegram 자동 발송. dry-run / send 2모드 지원. |
| 사용 가능 여부 | **사용 가능** (2026-06-16 FIX r4 최종). OCI 실측 dry-run 3종 + send + duplicate guard 전 항목 PASS. |
| 데이터 소스 상태 | `state/three_push/packages/` (PC sync 경로). 신규 external source / 신규 DB / scheduler framework 0건. |
| CLI 진입점 | `python scripts/run_three_push_oci.py --push-kind {push_kind} --mode {dry-run\|send}` |
| 환경변수 | `THREE_PUSH_PACKAGE_DIR` (기본 `/home/ubuntu/krx_hyungsoo/state/three_push/packages`) / `PUSH_AUTOSEND_ENABLED` / `PUSH_AUTOSEND_{KIND}_ENABLED` / `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `THREE_PUSH_MAX_PACKAGE_AGE_HOURS` (기본 36). |
| guard 목록 | (1) global enable flag (2) push_kind별 enable flag (3) generation_status=failed 차단 (4) 최신성 36h guard (5) 중복 발송 방지 (package_id 기반) (6) 금지 문구 검사 (7) token/chat_id 비노출. |
| 중복 발송 registry | `state/three_push/oci_sent_registry.json` — push_kind + package_id 키로 sent 기록. |
| status 기록 | `state/three_push/oci_runner_status_latest.json` + `state/three_push/oci_runner_history.jsonl` + `logs/three_push_cron.log`. |
| crontab template | `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` (2026-06-18 최신화 — venv 경로 `venv/bin/python` 명시 + .env 자동 로드 안내 + PC sync 선행 시간표 + dry-run/send 등가 실행 절차). |
| PC sync 운영 등록 안내 | `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` (2026-06-18 신규 — schtasks CLI 명령 3종 + GUI 절차 + 등록 확인 / 수동 트리거 / 중단·재개 / 트러블슈팅). |
| PC sync wrapper | `scripts/run_three_push_sync_task.ps1` (2026-06-18 신규 — Task Scheduler 호출용. `.venv\Scripts\python.exe scripts/sync_three_push_packages.py` 실행 + `logs/three_push_sync_task.log` append + exit code 전달). |
| 테스트 | pytest **534 passed** (직전 STEP 시점 / 본 STEP 코드 변경 0건). 2026-06-18 본 STEP 검증 시점에 1 failed (`test_generate_spike_alert_via_unified_endpoint`, Clean tree에서도 동일 실패하는 기존 회귀, 본 STEP 무관). black / flake8 PASS. OCI 실측 (2026-06-18): dry-run 3종 PASS (msg_len market 997 / holdings 1606 / spike 878). send → telegram_sent=true / duplicate guard → status=skipped, reason=duplicate_package PASS. |
| 테스트용/임시 여부 | 운영용 — OCI crontab + PC Task Scheduler 등록으로 하루 3회 자동 실행 가능. |
| 운영 등록 상태 (2026-06-18) | **격하 (manual recovery 전용)**. 정식 운영 경로는 §2.27 PARAM runtime 으로 이전됨 (Step `PARAM_HANDOFF_OCI_RUNTIME_3PUSH`). 본 항목 산출물은 보존되며 manual recovery / smoke test / 비상 fallback 으로만 사용. |
| 운영 시간표 (KST) | (정식 자동 발송 시간표 아님) sync 07:50 / 12:20 / 15:20 + send 08:00 / 12:30 / 15:30 — manual recovery 시 참고용. |
| 다음 조치 | (1) 기존 등록된 PC schtasks 가 있다면 비활성화 또는 제거. (2) 정식 운영은 §2.27 참조. |

### 2.27 OCI 3-PUSH PARAM Runtime (정식 자동 발송 — 2026-06-18 신규)

| 항목 | 값 |
|---|---|
| 기능명 | PC 가 승인한 PARAM snapshot 을 OCI 에 한 번만 전달하고, OCI 가 latest PARAM 을 고정 사용해 hourly runtime 메시지를 생성 + Telegram 발송. |
| 현재 메뉴 위치 | (UI 없음 — PC CLI + OCI crontab) |
| 기능 목적 | PC 가 매 발송마다 message package 를 만드는 부담을 제거하고, OCI 가 runtime 시점의 데이터 가용성을 직접 보고 메시지를 만들도록 책임 분리. |
| 사용 가능 여부 | **사용 가능** (2026-06-18 OCI 실측 dry-run 3종 + send 1회 + duplicate guard + disabled guard + missing_latest_param fail-closed 모두 PASS). |
| 데이터 소스 상태 | `state/three_push/params/latest_runtime_param.json` (PC + OCI 동일 경로). 신규 external source / 신규 DB / scheduler framework 0건. |
| PARAM 계약 | `app/three_push_runtime_param.py` (schema_version=`three_push_runtime_param.v1`). 필수 필드: schema_version / param_id / created_at / approved_at / approved_by / param_source / enabled_push_kinds / runtime_policy / evidence_policy / safety_policy. 금지 키 11종 (완성 메시지 / 매매 판단 / secret). param_source 허용값: manual_seed / baseline_static / future_ml_placeholder / ml_export. |
| runtime 빌더 | `app/three_push_runtime_message_builder.py` — OCI runtime 시점 timestamp + param_id + push_kind + data availability + unavailable source 명시 + 매매 지시 없음 면책. 외부 API 호출 0건. PC package message_text 재사용 0건. |
| 공통 헬퍼 | `app/three_push_runner_common.py` — `.env` 로더 / Telegram send / forbidden wording / secret guard / registry helper. package runner 와 runtime runner 가 공유. |
| 정식 entrypoint | `scripts/run_three_push_runtime_oci.py --push-kind {push_kind} --mode {dry-run\|send}` |
| PARAM 생성 CLI | `scripts/create_three_push_runtime_param.py --source manual_seed --approve [--description ...] [--note ...]` |
| PARAM handoff CLI | `scripts/sync_three_push_runtime_param.py` (env: `OCI_SSH_TARGET`, `THREE_PUSH_REMOTE_PARAM_DIR`) |
| OCI 측 검증 CLI | `scripts/verify_three_push_param_oci.py --path <PATH>` (stdlib only) |
| guard 7종 | (1) latest PARAM 부재 fail-closed (2) PARAM schema 검증 (3) PARAM secret 비노출 (4) PARAM 의 enabled_push_kinds 확인 (5) PUSH_AUTOSEND_{global,KIND}_ENABLED (6) duplicate guard (key = `push_kind::param_id::KST_date`) (7) forbidden wording / token noexposure. |
| status 기록 | `state/three_push/oci_runtime_status_latest.json` + `oci_runtime_history.jsonl` + `oci_runtime_sent_registry.json` + `logs/three_push_runtime_cron.log` (정식). |
| crontab template | `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` §3 (정식 운영) + §3-fallback (manual recovery). |
| 다음 조치 | (1) 사용자 OCI 에서 `crontab -e` 로 정식 entry 3종 갱신 (`run_three_push_oci.py` → `run_three_push_runtime_oci.py`). (2) PARAM 변경 운영 사이클 검증 (manual_seed → baseline_static 등). (3) runtime data source 점진 확장 (BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP). |

### 2.28 PUSH 사용자 표현 정리 + PARAM 적용 UI 연결 (2026-06-20 신규)

| 항목 | 값 |
|---|---|
| 기능명 | Telegram PUSH 본문을 사용자 친화 메시지로 정리 + UI 한 번으로 OCI 에 PARAM 적용. |
| 현재 메뉴 위치 | Approval / Telegram 화면 — `ThreePushParamCard` (`ThreePushDraftCard` 상단). |
| 기능 목적 | (1) 운영 진단 로그 형식(`param_id`, `kr_realtime_price_snapshot=unavailable` 등)을 사람이 읽을 수 있는 짧은 안내로 변환. (2) CLI 없이 UI 단일 버튼으로 manual_seed PARAM 생성 + latest 승격 + OCI sync + verify. |
| 사용 가능 여부 | **사용 가능** (2026-06-20 commit `b2946643` 검증자 VERIFIED_WITH_NOTES 통과). |
| 데이터 소스 상태 | 신규 source 0건. 기존 latest PARAM + sync_status_latest.json read-only. |
| 사용자 표시 라벨 | `app/push_user_labels.py` — source key 8종 → 사용자 라벨 (국내 ETF 시세 / 밤사이 미국 시장 / ETF 후보 흐름 / 보유 종목 평가 / NAV·괴리율 / 급등락 관찰 / 위험 참고 데이터 / 주요 뉴스). |
| 사용자 메시지 빌더 | `app/push_user_copy.py` — 전체 unavailable 시 `build_all_unavailable_message` (헤더 + 기준 시각 + 안내 + 별도 확인 필요 + 짧은 주의 문장) + 일부 available 시 `render_unavailable_block`. |
| PC builder 정렬 | `app/message_market_briefing.py` / `app/message_spike_alert.py` / `app/draft_message.py` 섹션 헤더를 사용자 표시명으로 정렬 + 전체 unavailable fallback 으로 사용자 중심 축약 메시지 호출. |
| 정식 PARAM runtime builder | `app/three_push_runtime_message_builder.py` 가 사용자 중심 메시지로 재작성 — PARAM (`param_id` / `param_source`) 본문 노출 0건. duplicate guard / status 기록 / 로그용으로만 사용. |
| raw 식별자 차단 안전망 | `app/three_push_runner_common.py:check_raw_identifiers()` 공통 헬퍼 (11종 식별자) — 정식 runtime runner + fallback package runner 양쪽에서 §4-b 단계로 차단. 감지 시 `status=failed, reason=raw_identifier_exposed` (정식) / `status=skipped, reason=raw_identifier_exposed` (fallback). |
| API endpoint | `GET /three-push/param/state` (현재 운영 기준 카드 표시용 read-only state) + `POST /three-push/param/apply` (manual_seed PARAM 생성 + latest 승격 + sync subprocess + verify 동기 처리). 응답에 raw 식별자 (param_id / SSH target / remote path / 파일명 / raw stderr) 노출 0건. |
| sync state 3분리 | `_read_sync_status()` 가 `(state, payload)` 튜플 반환. state ∈ {`SYNC_STATE_MISSING`, `SYNC_STATE_CORRUPTED`, `SYNC_STATE_OK`}. 손상은 logger.warning + UI `verification_required` 상태로 표시. |
| UI 카드 | `frontend/app/components/ThreePushParamCard.tsx` — 현재 적용 기준 / OCI 반영 상태 (적용 완료 / 적용 중 / 적용 실패 / 확인 필요 / 미적용) / 마지막 적용 시각 (YYYY-MM-DD HH:MM, KST) / 단일 버튼 `[현재 기준 OCI 적용]` (지시문 §5.3) + 진행 단계 표시 (운영 기준 생성 중 → OCI 에 적용 중 → OCI 반영 확인 중 → 적용 완료). |
| API client | `frontend/lib/api/threePushParam.ts` (apply timeout 120s). |
| 테스트 | `tests/test_three_push_runtime_message_builder.py` (17건 — raw 식별자 미노출 + 사용자 라벨 + 전체/일부 unavailable 검증) + `tests/test_three_push_param_api.py` (3건 — state 응답 형식 + display_label 사용자 친화성 + apply 실패 시 raw 식별자 미노출). |
| 다음 조치 | (1) 사용자가 UI 한 번으로 PARAM 적용 운영 사이클 검증. (2) `news_snapshot` 사용자 라벨 등록만 됐고 실제 뉴스 source 도입은 별도 STEP. (3) scheduled run 관찰 + 운영 진단 UI (OCI runner status/history read-only). |

### 2.29 ML 축1 — 후보 ETF 상대상승 참고점수 v0 (2026-06-20 신규)

| 항목 | 값 |
|---|---|
| 기능명 | 후보 ETF 별 0~100 상대상승 참고점수 (torch GPU baseline) + 기존 후보 목록에서 점수·고점 대비·근거 비교. |
| 현재 메뉴 위치 | Market Discovery 화면 — `CandidateTable` 컬럼 3개 추가 (상대상승 참고점수 / 고점 대비 / 점수 근거). |
| 기능 목적 | 사용자가 AI 투자세션에서 후보 ETF 사이의 상대상승 가능성을 모델 기반으로 비교. 매수·매도·교체·비중 조절 신호 아님. |
| 사용 가능 여부 | **사용 가능** (2026-06-20 1,111 후보 점수 부여 PASS). |
| 데이터 소스 상태 | SQLite `etf_daily_price` 전체 universe (1,140 ticker, ~80 거래일) + KODEX200 (069500) 기준. 신규 external source / 신규 DB 0건. |
| 점수 정의 | `relative_upside_score` ∈ 0~100. 후보군 내 raw prediction 의 상대 순위 정규화. 0~100 절대 비교 X (기준일 후보군 내에서만 의미). |
| 첫 추가 factor | `drawdown_20d` = `close / rolling_20d_high - 1` (음수). 예: 현재가 90 / 20일 고점 100 → -0.10. UI 컬럼명 "고점 대비". |
| 모델 | torch `nn.Linear(7,1)` 단일 선형회귀. Adam lr=1e-3, MSE, 200 epochs, seed=42. 자동 튜닝 / 앙상블 / RF/XGB/LGBM 비교 0건. |
| 학습 target | 이후 20거래일 KODEX200 대비 상대수익 (`future_excess_return_20d`). 마지막 horizon row 의 target=None (미래 데이터 차단). |
| 분할 방식 | walk-forward 1회 split (사용자 결정 2026-06-20) — 시간 순서 정렬 후 앞 80% / 뒤 20%. 랜덤 셔플 0건. |
| feature 컬럼 7개 | `return_5d` / `return_10d` / `return_20d` / `excess_return_5d` / `excess_return_10d` / `excess_return_20d` / `drawdown_20d`. |
| GPU 실행 증거 | `device_name=NVIDIA GeForce RTX 4070 SUPER`, `cuda_available=true`, `gpu_execution_used=true`, train_seconds=0.256. requirements.txt 에 `torch>=2.6.0` 추가 (CUDA 12.4 wheel). |
| 산출물 (gitignored) | `state/ml/relative_upside_score_latest.json` (점수+근거) + `state/ml/relative_upside_score_run_latest.json` (학습 메타). |
| CLI 진입점 | `python scripts/run_ml_relative_upside_score_v0.py [--candidates ticker1,ticker2,...]` |
| API 노출 | 기존 `GET /market/topn/latest` 확장 (신규 endpoint 0건). top-level `relative_upside_score_status` / `_asof_date` / `_generated_at` / `_user_notice` 4 필드 + 후보당 `relative_upside_score` / `drawdown_20d` / `relative_upside_reasons` 3 필드. snapshot 부재 시 status=unavailable + candidate score=null, 후보 응답 자체는 유지. |
| 사용자 고지 (USER_NOTICE) | "상대상승 참고점수는 과거 데이터 기반의 후보 비교용 참고값이며, 매수·매도 판단을 자동으로 제시하지 않습니다." 카드 하단에 항상 표시. |
| 점수 근거 (reasons) | 사람 언어 짧은 요약 최대 3개 — KODEX200 대비 성과 / 20일 고점 대비 하락폭 / 데이터 품질. 모델 내부 식별자 (loss / epoch / device / feature_vector) 노출 0건 (단위 테스트 검증). |
| 점수 정렬 | 헤더 클릭 로컬 정렬 (off → 내림차 → 오름차 → off). 점수 null 후보는 항상 점수 있는 후보 뒤로. 신규 API 정렬 파라미터 0건. |
| 단순 vs ML 비교 | snapshot 의 `simple_vs_ml_rank_comparison` 블록 — 기존 20일 KODEX200 초과수익 순위 vs ML 점수 순위 (AC-5). |
| 테스트 | 24건 — `tests/test_ml_relative_upside_features.py` (7) + `tests/test_ml_relative_upside_model.py` (7) + `tests/test_ml_relative_upside_score.py` (10). pytest 608 passed (회귀 0). |
| OCI 영향 | **0건** — OCI runner / PARAM / Telegram 메시지 / crontab 구조 변경 X. PC 분석 평면에만 머문다. 향후 OCI read model snapshot handoff 가 결정된 뒤 별도 STEP. |
| 다음 조치 | (1) ML 축2 위험 감지 빈자리 하나 채우기 STEP. (2) 점수·위험·보유 비교가 모이는 PC 판단 화면. (3) OCI read model foundation 준비 단계. |

### 2.30 ML 축1 — 상대상승 점수 실행 UI 연결 (2026-06-21 신규)

| 항목 | 값 |
|---|---|
| 기능명 | 사용자가 CLI 없이 화면 버튼 1개로 상대상승 참고점수 v0 계산을 실행하고 결과를 확인. §2.29 의 후속 — 모델 / feature / 산식은 그대로. |
| 현재 메뉴 위치 | Market Discovery 화면 — `MarketContextCard` 다음에 `RelativeUpsideRunCard` 배치. |
| 기능 목적 | UI 한 번으로 점수 계산 + 정상 실행 여부 확인 (상태 / 기준일 / 마지막 계산 시각 / 점수 반영 후보 수 / GPU 실행 여부). |
| 사용 가능 여부 | **사용 가능** (2026-06-21 commit 예정. POST 실측 status=ok, scored 1,111, gpu=true). |
| API endpoint | `POST /market/relative-upside/run` (`app/api_ml_relative_upside.py`). 동기 처리 — `scripts.run_ml_relative_upside_score_v0.main()` 을 직접 import 호출 (subprocess 가 아님 — 사용자 결정 2026-06-21). 응답 timeout 120 초. |
| 응답 6 필드 | `status` (ok / failed / unavailable) / `asof_date` / `generated_at` / `scored_candidate_count` / `gpu_execution_used` / `message`. raw 식별자 (`CUDA` / `device_name` / `loss` / `epoch` / `artifact_path` / `snapshot_path` / `Traceback`) 노출 0건 (단위 테스트 검증). FIX r1 — meta 파일 손상 시 별도 사용자 친화 메시지 ("운영 상태 파일을 읽지 못했습니다. 기존 점수는 유지됩니다.") + status=unavailable. |
| 사용자 친화 message | 성공+GPU "상대상승 참고점수 계산이 완료되었습니다." / 성공+GPU 미확인 "계산은 완료됐지만 GPU 실행은 확인되지 않았습니다." / 실패 "새 점수를 계산하지 못했습니다. 기존 점수는 유지됩니다." / unavailable "계산은 시도했지만 점수를 생성하지 못했습니다. 기존 점수는 유지됩니다." |
| UI 카드 | `frontend/app/components/RelativeUpsideRunCard.tsx` — 상태 badge (미실행 / 계산 중 / 완료 / 실패 / 데이터 부족) + 기준일 + 마지막 계산 시각 + 점수 반영 후보 수 + GPU 실행 여부 + 단일 버튼 `[상대상승 점수 계산]`. running 중 중복 클릭 차단. 실패 시 기존 result 유지 (지시문 — 실패 시 기존 점수 보존). |
| API client | `frontend/lib/api/mlRelativeUpside.ts` (timeout 120s). |
| 자동 갱신 | 성공 시 `onSuccess={loadTopn}` 콜백으로 `GET /market/topn/latest` 재호출 → 후보 표의 점수 / 고점 대비 / 근거 자동 최신화. |
| 실패 보호 | **2층 보호** — (1) `main()` 예외 raise 시 atomic write 가 호출되지 않아 두 파일 변경 0건. (2) **FIX r1**: `main()` 이 `model is None` / `inference_rows` 빈 분기로 들어와도 `save_score_snapshot()` 호출하지 않고 `RUN_META_PATH` 만 `snapshot_path=""` 명시 저장 → 기존 `SCORE_SNAPSHOT_PATH` 그대로 유지. 단위 테스트 `test_main_unavailable_branch_does_not_overwrite_existing_snapshot` 로 검증. UI 는 직전 result 유지 + 사용자용 generic 실패 메시지 표시 (raw traceback 미노출). |
| 모델 / feature / 산식 | **변경 0건** — §2.29 의 `nn.Linear(7,1)` / walk-forward 1회 split / `drawdown_20d` / 0~100 정규화 그대로. 새 모델 / 새 factor / 새 학습 흐름 0건. |
| OCI / PARAM / Telegram | **0건** — `scripts/run_three_push_runtime_oci.py` / `app/three_push_runtime_message_builder.py` / PARAM 구조 / Telegram 메시지 변경 X. |
| 테스트 | 7건 (FIX r1 후 +2) — `tests/test_api_ml_relative_upside.py`. pytest 615 passed (608 + 7 신규, 회귀 0). 모든 테스트 `tmp_path` 격리로 운영 artifact 오염 0건. |
| 다음 조치 | (1) 사용자가 화면 운영 사이클 검증. (2) ML 축2 위험 감지 빈자리 STEP 진입 시 동일 UI 패턴 재사용. |

### 2.31 보유 ETF와 시장 후보 비교 v1 (2026-06-21 신규)

| 항목 | 값 |
|---|---|
| 기능명 | Market Discovery 안에서 보유 ETF 와 시장 후보 ETF 를 같은 화면에서 비교. 신규 endpoint / 신규 계산 0건 — 기존 응답을 client-side 조합. |
| 현재 메뉴 위치 | Market Discovery 화면 — 상단 탭 "기본" / "보유와 비교". |
| 기능 목적 | 사용자가 후보 ETF 가 강해 보일 때 (a) 보유 ETF 와 겹치는가, (b) 기존 보유보다 최근 상대 흐름이 강한가, (c) 중복 정보가 조회된 상태인가, (d) 데이터 부족으로 비교 보류해야 하는가를 한 화면에서 판단 가능. |
| 사용 가능 여부 | **사용 가능** (2026-06-21 commit 예정). |
| UI 구성 | **상단**: 탭 토글 (CompareViewTabs). **기본 탭**: 기존 `CandidateTable` + `SummaryHeader`. **보유와 비교 탭**: `HoldingsCompareView` — (1) 기준일 헤더 (후보 / 보유 / 중복 정보 각각 별도) + Evidence 명시 조회 버튼. (2) 좌측 70% — 보유 요약 표 + 후보 비교 표. (3) 우측 30% — 후보 선택 상세 (split pane, sticky). |
| 데이터 출처 | 기존 3개 endpoint 조합 — `GET /market/topn/latest` (후보 + 상대상승점수 + 단기 흐름) + `GET /holdings/enriched` (보유 + 평가금액/손익 — 캐시 기반 자동 로드) + `GET /holdings/market-evidence/latest` (보유별 evidence — 명시 조회). |
| 보유 요약 표 | **CLOSEOUT (2026-06-24)** 컬럼 6종: ETF명 / 평가 비중 / 손익률 / 20일 KODEX 초과수익 / 고점 대비 / 상태. 매입 회차가 아닌 **티커별 통합** 한 줄로 표시 (`aggregateHoldingsByTicker`). 평가 비중 = 티커별 통합 평가금액 / 전체 평가금액. 손익률 = 티커별 통합 손익 / 통합 매입금액. 로컬 정렬: 평가 비중 / 손익률 / 20일 KODEX 초과. **고점 대비 (CLOSEOUT FIX r1)**: evidence 응답에 직접 필드 없으므로 evidence 로드 여부와 무관하게 `확인 필요` 단일 표기. 중복 상태 문구 (`중복 확인 전` 등) 를 가격 위치에 섞지 않는다. 기존 enriched 원본 / 매입 회차 데이터 변경 0건 — 화면 표시용 통합만 수행. |
| 후보 비교 표 | **CLOSEOUT (2026-06-24)** 컬럼 6종: ETF명 / 참고점수 / 20일 KODEX 초과수익 / 고점 대비 / 보유 노출 / 데이터 상태. 로컬 정렬: 참고점수 / 20일 KODEX 초과 / 고점 대비 / 보유 노출. `null` 후보는 항상 뒤로. 행 클릭으로 후보 선택. 정렬 키 4 종. |
| 보유 노출 단일 칸 (AC-4) | **CLOSEOUT 핵심**. 한 칸에서 6가지 표현 — `직접 보유` / `직접 보유 · 구성종목도 겹침` / `구성종목 겹침 · 보유 ETF N개` / `중복 없음` / `중복 확인 전` / `중복 확인 불가`. 직접 보유 = ticker exact match. 구성종목 겹침 = client-side reverse-lookup (보유 ETF 의 `overlap_with_market_core[].ticker` 가 후보 ticker 와 일치). `중복 없음` 은 모든 보유 ETF 의 overlap 정상 조회 + 일치 0건일 때만. `unavailable` 을 "중복 없음" 으로 해석 X. |
| Overlap 상태 분기 | 사용자 화면에서 raw 상태값 (`not_loaded` / `loading` / `ok` / `unavailable`) 노출 0건. 사용자 친화 문구로 변환 — `정상` / `일부 확인 불가` / `중복 확인 전` / `중복 확인 불가` / `데이터 없음` / `확인 필요`. 후보 선택만으로 자동 fetch 안 함. 조회 실패 시 기존 값 유지. |
| 선택 상세 영역 (AC-5/AC-6) | sticky split pane 우측 30%. **순서 고정 (CLOSEOUT)**: (1) 보유 노출 요약 (직접 보유 여부 / 겹침 보유 ETF 수 / 가장 큰 겹침 대상 + weight%) — 카드 최상단. (2) 후보 흐름 (참고점수 + 점수 근거 + 5/10/20일 수익률·초과수익 + 고점 대비 + 데이터 품질). (3) 세부 근거 (구성종목 목록 + overlap 수치 + 시장 반복 정보) — **기본 접힘**, 사용자가 명시적으로 펼치기 버튼 클릭 시에만 노출. |
| 기준일 분리 표시 (지시문 §4.1) | 후보 기준일 (`data.asof`) / 보유 정보 기준일 (`evidence.holdings_asof`) / 중복 정보 기준일 (`evidence.market_asof`) 모두 각각 별도 표시. 합쳐서 같은 시점처럼 표시 X. |
| 사용자 고지 | (FIX r1) 부정 안내문 형태도 금지 단어 포함 금지 — UI 사용자 표시 영역에 매수·매도·추천·교체·비중 조절 단어 0건. 카드 하단 helper 는 후보별 보유 중복 설명 + 데이터 부재 표시 원칙만 유지. |
| 신규 backend | **0건** — `app/api_market_topn.py` / `app/api.py` / `app/holdings.py` / `app/api_holdings_market_evidence.py` 변경 0건. |
| OCI / PARAM / Telegram / DB | **0건**. |
| 기존 산식 변경 | **0건** — 수익률 / 초과수익 / 상대상승점수 / overlap 산식 변경 X. |
| 테스트 | backend pytest 전체 실행 명령 결과 (CLOSEOUT 2026-06-24, deselect 옵션 사용): **616 passed, 1 deselected** (회귀 0 — backend 변경 0건). deselected 1건은 `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` 로 본 STEP 이전부터 존재하는 기존 환경 실패. frontend lint / build PASS. (참고: deselect 옵션 미사용 시 동일 명령이 1 failed / 종료 코드 1 로 표기됨 — 실제 회귀 0건의 의미는 동일.) |
| 다음 조치 | (1) 사용자가 운영 사이클 검증. (2) ML 축2 위험 감지 빈자리 STEP 진입 시 위험 evidence 도 본 UI 패턴 재사용. |

---

### 2.32 Cleanup KS-10 Round A — 기준선 측정 + D-1 회귀 해소 (2026-06-29)

| 항목 | 값 |
|---|---|
| 기능명 | 구조 안정화 STEP — 전체 .py/.ts/.tsx 라인 수 기준선 측정 + KS-10 trigger/near 목록화 + D-1 회귀 해소. 기능 추가 0건. |
| 현재 메뉴 위치 | (UI 없음 — 코드 구조 + 테스트 수정) |
| 기능 목적 | KS-10 기준선 확정 + 회귀 테스트 격리 복구. |
| 사용 가능 여부 | **사용 가능** (2026-06-29 VERIFIED_WITH_NOTES). |
| KS-10 기준선 (측정 전) | `app/api_market_topn.py` **636** (near ≥600). `scripts/run_three_push_oci.py` **672** (classification_ambiguity). |
| D-1 해소 | `tests/test_three_push_contract.py` stub 2개 추가 (505→531 라인, wc -l). |
| 테스트 | pytest **617 passed** (회귀 0). black / flake8 PASS. |
| 테스트용/임시 여부 | 아님 — 구조 안정화. |
| 다음 조치 | Round B — near/ambiguity 파일 분리 (2.33 참조). |

---

### 2.33 Cleanup KS-10 Round B — 파일 분리 + trigger/near 0 달성 (2026-06-29)

| 항목 | 값 |
|---|---|
| 기능명 | 구조 안정화 STEP — Round A near/ambiguity 파일 2종을 책임 단위로 분리. KS-10 trigger=0, near=0 달성. 기능 추가 0건. |
| 현재 메뉴 위치 | (UI 없음 — 코드 구조 변경) |
| 기능 목적 | `scripts/run_three_push_oci.py` 672→255 / `app/api_market_topn.py` 636→178. 신규 3종: `three_push_oci_helpers.py` 450 / `api_market_topn_models.py` 234 / `api_market_topn_service.py` 274. |
| 사용 가능 여부 | **사용 가능** (2026-06-29). |
| KS-10 재분류 | trigger 0건 / near 0건. app/ 최대 586 (`app/draft.py`). |
| 호환성 | 기존 endpoint / 응답 필드 / OCI runner CLI / 테스트 모두 변경 0건. `api_market_topn._merge_relative_upside_score` + `MarketCandidate` re-export 유지. |
| 설계 결정 | `enrich_candidates_with_evidence` / `build_nav_discount_payload` — `DEFAULT_DB_PATH` 직접 참조 → `db_path` 파라미터화 (테스트 monkeypatch 정합성). |
| 테스트 | pytest **617 passed** (회귀 0). black / flake8 PASS. |
| 테스트용/임시 여부 | 아님 — 구조 안정화. |
| 다음 조치 | D-2 결함 해소 (2026-06-30 §2.34 로 진행됨). |

---

### 2.34 D-2 시장 갱신 상태 SQLite 영속화 (2026-06-30)

| 항목 | 값 |
|---|---|
| 기능명 | `market_refresh_service` 의 in-memory state SSOT 를 기존 시장 SQLite 의 `market_refresh_state` 테이블 (단일 행) 로 전환. 재시작 후에도 마지막 정상 갱신 상태(detail 포함)를 동일하게 노출. |
| 현재 메뉴 위치 | (UI 없음 — 내부 영속화 변경) |
| 기능 목적 | D-2 결함 해소 — 서버 재시작 시 cooldown 가드 / frontend polling idle 오인 / 마지막 정상 갱신 정보 소실 방지. |
| 사용 가능 여부 | **사용 가능** (2026-06-30). |
| 신규 테이블 | `market_refresh_state` — `refresh_scope='market_data'` 단일 행. 컬럼 14개 (RefreshState 외부 노출 필드 전체 포함). |
| 신규 모듈 | `app/market_refresh_state_store.py` — `read_state` / `write_state` / `normalize_running_to_failed` / `clear_state`. |
| API·UI 계약 | 변경 0건. `MarketRefreshStatusResponse` 응답 필드 12개 그대로. endpoint 변경 X. |
| 재시작 동작 | `_ensure_loaded` 가 첫 호출 시 SQLite hydrate + `running → failed` 정규화 (detail 보존, `last_success_*` 유지). 새 인스턴스는 다음 호출에서 다시 hydrate. |
| 실패 보존 | `_persist_current_state` 가 prior row 의 `last_success_*` 를 자동 보존 — 실패·중단·running 진입이 마지막 정상 성공 기록을 덮어쓰지 않음. |
| 테스트 | pytest **627 passed** (617 → 627, 신규 10 케이스). black / flake8 PASS / frontend lint / frontend build PASS. |
| 테스트용/임시 여부 | 아님 — 결함 해소. |
| 다음 조치 | 시장 시계열 SQLite 기반 보강 (§2.35 로 진행됨). |

---

### 2.35 시장 시계열 SQLite 기반 보강 — PARTIAL (2026-06-30)

| 항목 | 값 |
|---|---|
| 기능명 | KRX 데이터마켓 공식 자료 (CSV/ZIP) → PC CLI → SQLite 적재. 종목별 적재·범위·결측 상태 SSOT. 위험 evidence·국면·백테스트 기반 데이터 STEP. |
| 현재 메뉴 위치 | (UI 없음 — 데이터 기반 STEP) |
| 기능 목적 | KODEX200 / ETF universe 의 장기 일별 종가 시계열을 SQLite 에 점진 적재 + 결측 분류 + 중단 후 재개. 위험 evidence·ML 축2·백테스트 진입 전 데이터 기반 확보. |
| 사용 가능 여부 | **PARTIAL** (2026-06-30) — 본 환경 KRX 자료 접근 불가. CLI / 계약 / fixture 테스트 완료. 실측은 사용자 PC 실행 필요. |
| 신규 테이블 | `market_timeseries_ingestion_state` — ticker PK 11 컬럼 (확인된 상장일 / 시계열 시작·종료 / 관측 거래일 수 / 상장 후 결측 수 / 적재 상태 / 소스 / 가격 기준 / 마지막 확인 시각 / 오류 요약). |
| 신규 모듈 | `app/market_timeseries_ingestion_store.py` (state CRUD + pending), `app/market_timeseries_ingestion_service.py` (결측 분류 + ingest). |
| 신규 CLI | `scripts/ingest_krx_timeseries.py` — `benchmark` / `etf` / `status` 서브커맨드. 외부 네트워크 X. `--price-basis` 인자 필수. |
| 결측 분류 | 상장 전 (count X) / source_missing (CSV 에 ticker 없음) / post_listing_missing (KODEX200 거래일 기준) / missing_confirm (충돌·bad price). 0/직전값/보간 채움 0건. |
| 재개 / 중복 방지 | `list_pending_tickers` 가 `status != normal` 만 반환. (ticker, date) PK ON CONFLICT 흡수. `--force` 로 강제 재적재. |
| 가격 시계열 SSOT | 기존 `etf_daily_price` (KODEX200 포함 ETF) / `market_benchmark_daily_price` (KOSPI 등 지수). 신규 가격 테이블 신설 0건. |
| API·UI 계약 | 변경 0건. `fetch_price_history` / `fetch_benchmark_history` 그대로. |
| 테스트 | pytest **650 passed** (627 → 650, 신규 23 케이스, FIX r1 +6, FIX r2 +2). black / flake8 / frontend lint / frontend build PASS. |
| 테스트용/임시 여부 | 아님 — 데이터 기반. |
| 다음 조치 | 2026-06-30 Closeout STEP §2.36 으로 네이버/FDR 주 소스 + Yahoo 보조 + ML 게이트로 DONE 승격됨. KRX CSV import 는 수동 과거 보정용으로만 유지. |

---

### 2.36 시장 시계열 SQLite Closeout — Naver/FDR 주 소스 + Yahoo 보조 + ML 게이트 (2026-06-30, DONE)

| 항목 | 값 |
|---|---|
| 기능명 | 이전 PARTIAL 시장 시계열 STEP 을 네이버/FDR primary + Yahoo/FDR secondary + CLI 최신화 + ML 실행 게이트로 완료. KRX CSV 는 수동 과거 보정용으로 유지. |
| 현재 메뉴 위치 | (UI 변경 없음 — 내부 데이터 기반) |
| 기능 목적 | PC CLI 로 KODEX200 + ETF universe 시계열을 SQLite 로 누적/갱신. ML 실행은 SQLite 준비 상태만 확인 후 진입. UI 대량 외부 호출 0건. |
| 사용 가능 여부 | **사용 가능** (2026-06-30 DONE). |
| 소스 정책 | NAVER_FDR primary (`NAVER:<ticker>`) → 실패 또는 빈 응답 시 YAHOO_FDR (`YAHOO:<ticker>.KS`) 1회. 호출 식별자에 소스 명시 (FIX r1). 자동 재시도 없음. 신규 의존성 0건. |
| 신규 테이블 | `market_timeseries_refresh_state` — 단일 행 (`refresh_scope='daily_prices'`) 11 컬럼. D-2 `market_refresh_state` 와 별도. |
| 신규 모듈 | `app/market_timeseries_refresh_state_store.py`, `app/market_timeseries_naver_yahoo_adapter.py`, `scripts/refresh_market_timeseries.py`. |
| CLI 서브커맨드 | `benchmark` (KODEX200 먼저) / `initial` (`--max-tickers N` 또는 `--all` 필수) / `incremental` (last date+1 이후만 요청, `--retry-pending` 옵션) / `status`. |
| ML 실행 게이트 | `POST /ml/jobs/evidence-refresh` 진입 전 SQLite 만 read 하여 확인 (refresh status ok + benchmark_asof_date + KODEX200 normal + eligible>0). 기존 응답 계약 유지. 실패 시 `status="error"` + 짧은 안내 문구. 새 endpoint 0건. |
| 실측 (기본 SQLite `state/market/market_data.sqlite`, gitignored) | KODEX200 3000 행 (2014-04-09 ~ 2026-07-02), 069660 / 102110 / 0000D0 표본 3종 확인, universe normal 1007 / missing_confirm 138 / failed 0 (missing_confirm 은 기존 저장값과 명시 소스 반환값 차이 — 자동 덮어쓰기 금지 정책 그대로). |
| 재개·중복 방지 | `list_pending_tickers` + `(ticker, date)` PK ON CONFLICT + `_split_by_existing_conflict`. `_incremental_start_for` 가 정상 종목의 last date+1 부터만 요청. |
| API·UI 계약 | 변경 0건. 기존 `MlJobStartResponse` 필드 그대로. |
| 테스트 | pytest **675 passed** (650 → 675, 신규 25, FIX r1 +1). black / flake8 / frontend lint / frontend build PASS. |
| 테스트용/임시 여부 | 아님 — 데이터 기반 운영. |
| 다음 조치 | 2026-07-03 Market Risk Reference v1 (§2.37) 로 KODEX200 + VIX 일별 맥락 카드 진행 완료. 이후 위험 evidence / ML 축2 진입 (사용자 결정). |

---

### 2.37 Market Risk Reference v1 — KODEX200 + VIX 일별 맥락 (2026-07-03, DONE)

| 항목 | 값 |
|---|---|
| 기능명 | Market Discovery 첫 화면 카드 — KODEX200 (국내 기준선) + VIX (미국 변동성 참고) 일별 evidence. 원시 evidence 만, 판단 라벨 / 시장 국면 / 위험 점수 / 예측 없음. |
| 현재 메뉴 위치 | `MarketDiscoveryView` — `MarketContextCard` 뒤 신규 `MarketRiskReferenceCard`. |
| 기능 목적 | 국내 기준선과 외부 위험 맥락을 한 화면에 놓아 사용자 판단 전 참고. VIX 최근 1일·5거래일 변화율 노출. |
| 사용 가능 여부 | **사용 가능** (2026-07-03 DONE). |
| VIX 소스 | FDR `fdr.DataReader("VIX", ...)` 단일 경로. 신규 의존성 0건. Cboe 미사용. |
| VIX 저장 | 기존 `market_benchmark_daily_price` 재사용 (benchmark_id='VIX'). 신규 가격 테이블 0건. |
| VIX 실측 | 2014-04-08 ~ 2026-07-03 / 3079 rows. |
| API 응답 | `MarketTopNResponse.market_risk_reference` 최상위 신규 필드. kodex200 + vix 각각 as_of_date / close / change_1d_pct + recent_20d_series. VIX 만 change_5d_pct. 기존 필드 변경 0건. |
| CLI | `scripts/refresh_market_timeseries.py vix` 서브커맨드 신규. `benchmark` / `initial` / `incremental` 완전 분리 (sentinel 테스트로 검증). 실행당 1회, 자동 재시도 없음. 충돌 자동 덮어쓰기 금지. |
| ML 실행 게이트 | 변경 0건. VIX 를 ML feature / 학습 데이터 / 후보 제외 / 매매 판단에 사용 X. |
| UI | 카드 좌우 KODEX200 / VIX 패널 + 기준일 차이 안내 문구 + 상세 펼치기 최근 20거래일 sparkline. 두 시계열 별도 축. 외부 차트 라이브러리 0건. |
| 테스트 | pytest **691 passed** (675 → 691, 신규 16, FIX r1 +3). black / flake8 / frontend lint / frontend build PASS. |
| 테스트용/임시 여부 | 아님 — 운영 evidence. |
| 다음 조치 | 2026-07-03 Decision Draft Preview v1 (§2.38) 로 선택 ETF 판단 근거 미리보기 진행 완료. 이후 위험 evidence / ML 축2 진입 (사용자 결정). |

---

### 2.38 Decision Draft Preview v1 — 선택 ETF 임시 판단 근거 미리보기 (2026-07-03, DONE)

| 항목 | 값 |
|---|---|
| 기능명 | 보유·후보 비교 화면 선택 ETF 상세 영역에 저장 없는 임시 판단 근거 미리보기 (5구역 결정적 텍스트). LLM 미사용 — 사용자가 결과를 복사해 외부 AI 웹에 입력. |
| 현재 메뉴 위치 | `HoldingsCompareView` 우측 선택 상세 카드 (기존 후보 클릭 + 신규 보유 클릭). |
| 기능 목적 | 무엇이 확인됐는지 / 무엇이 아직 불확실한지 / 승인 전에 무엇을 확인해야 하는지 짧게 읽을 수 있게 함. |
| 사용 가능 여부 | **사용 가능** (2026-07-03 DONE). |
| 신규 endpoint | `POST /decision-draft/preview` — 요청 target_kind + ticker. 응답 preview_text + evidence_as_of (세 기준일 분리). 저장 부작용 0건. |
| 신규 모듈 | `app/decision_draft_preview_service.py`, `app/api_decision_draft_preview.py`, `frontend/lib/api/decisionDraftPreview.ts`, `frontend/app/components/holdings_compare/DecisionDraftPreviewCard.tsx`. |
| 분리 원칙 | 기존 `POST /runs/generate` PENDING 흐름과 완전 분리. `generate_draft` / `store.save` 미호출. 승인·OCI·Telegram 미연결. 새 DB 테이블 / 이력 저장 0건. |
| 외부 호출 / ML | 0건. FDR 미호출 자동 테스트 검증. SQLite / 기존 서비스 read only. |
| 금지 표현 필터 | preview_text 에 "지금 매수 / 지금 매도 / 반드시 유지 / 위험이 높습니다 / 시장 전환이 예상" 등 미포함 (자동 테스트). |
| 대상 변경 처리 | 요청 식별자 (`currentReqIdRef`) 로 응답 도착 시 대상 일치 확인 → 이전 응답 폐기. |
| 실패 처리 | "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요." 단일 문구. 이전 preview 재사용 / raw evidence 대체 표시 0건. |
| API·UI 계약 | 기존 필드 삭제·이름 변경·의미 변경 0건. `MarketDiscoveryView` / `MarketRiskReferenceCard` 미수정. |
| 테스트 | pytest **714 passed** (691 → 714, 전용 파일 23 케이스, FIX r1 +2 / FIX r2 +1 / FIX r3 +2 / FIX r5 +4 / FIX r6 +1 / FIX r7 +1). black / flake8 / frontend lint / frontend build PASS. |
| 테스트용/임시 여부 | 아님 — 사용자 판단 지원 evidence. |
| 다음 조치 | 위험 evidence / 시장 국면 / ML 축2 진입 (사용자 결정). |

---

### 2.39 Market Flow ML Dataset + Baseline v1 Closeout — KOSPI 역사 보강 + real baseline 실측 (2026-07-05, DONE)

| 항목 | 값 |
|---|---|
| 기능명 | (1) `kospi` 서브커맨드 — KOSPI 역사 시계열 보강 CLI (NAVER 주 / YAHOO 보조). (2) Ridge baseline 실측 metrics 산출. |
| 현재 위치 | `python -m scripts.refresh_market_timeseries kospi` (역사 보강). `python -m scripts.run_market_flow_baseline` (baseline). |
| 기능 목적 | 2026-07-03 PARTIAL 두 조건 (sklearn 승인 + KOSPI 시계열 보강) 해소하여 DONE 승격. |
| 사용 가능 여부 | **사용 가능** (2026-07-05 DONE). |
| KOSPI 역사 보강 실측 | NAVER_FDR 로 2870 행 삽입 (2014-04-10 ~ 2025-12-18). overwrite=false. YAHOO 미조회. 기존 130 행 유지. 총 3000 KOSPI 행. artifact `state/market/kospi_history_closeout_latest.json`. |
| Baseline 실측 | status=ok. dataset 2960 rows (2014-05-13 ~ 2026-06-05). Split train=1756 / validation=572 / test=592. Validation MAE=3.995 / RMSE=5.014 / directional_accuracy=0.4615. Test MAE=7.855 / RMSE=11.061 / directional_accuracy=0.4932. latest_inference status=ok / as_of=2026-07-03 / pred=+5.495%. sklearn 1.9.0. |
| 신규 파일 | `app/kospi_history_closeout.py`, `tests/test_kospi_history_closeout.py`. |
| 수정 파일 | `requirements.txt` (+scikit-learn), `app/market_flow_baseline.py` (sklearn_version 필드), `scripts/refresh_market_timeseries.py` (`kospi` 서브커맨드). |
| 신규 endpoint / UI / DB 테이블 | 0건. |
| 외부 호출 | `kospi` 서브커맨드 실행 시에만 NAVER_FDR / YAHOO_FDR 1회 (상시 호출 X). `build_dataset` / `run_baseline` 은 SQLite 만 read. |
| 제약 유지 | Ridge alpha=1.0 / 60/20/20 split / VIX strictly-prior. RF/XGB/LGBM/자동 튜닝/모델 비교 금지. |
| 소스 혼합 금지 | NAVER + YAHOO 신규 행 혼합 금지 (한 source 만 저장) — 자동 테스트 검증. |
| Overwrite 금지 | 기존 KOSPI 행 overwrite 금지 (동일 date 재기록 X) — 자동 테스트 검증. |
| 테스트 | pytest **738 passed** (729 → 738, 신규 9 KOSPI closeout). black / flake8 PASS. frontend 변경 0건. |
| 다음 조치 | 미결정 (설계자 지정 대기). Ridge baseline v1 은 시장 판단 근거 참조점수 이상의 용도로 사용하지 말 것 (자동 매매 / AI Sessions 연결 금지). |

---

## 3. Context Bridges (화면 간 전달)

### 3.1 Market Discovery → AI Sessions

| 항목 | 값 |
|---|---|
| 기능명 | "AI Sessions 로 넘기기" 버튼 + sessionStorage draft (v3) |
| 사용 가능 여부 | **사용 가능** |
| 전달 데이터 | asof / filters / candidate_snapshot / question_text / market_context_snapshot / candidate_excess_returns |
| 다음 조치 | 현재 상태 유지 |

### 3.2 Market Discovery → ETF Exposure

| 항목 | 값 |
|---|---|
| 기능명 | "ETF Exposure 로 넘기기" 버튼 + sessionStorage draft (v2) |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 + 2026-06-01 asof 흐름 FIX 후) |
| 전달 데이터 | asof / tickers / candidate_snapshot / market_context_full / market_candidates (excess_return 포함) |
| 다음 조치 | 운영 데이터 누적 후 검증 |

### 3.3 ETF Exposure → AI Sessions

| 항목 | 값 |
|---|---|
| 기능명 | ETF Exposure 의 "AI Sessions 로 넘기기" 버튼 |
| 사용 가능 여부 | **사용 가능** (2026-05-31 Naver 통합 + 2026-06-01 asof 흐름 FIX 후) |
| 전달 데이터 | 시장 판정 + 후보 excess_return + constituent_snapshot + overlap_snapshot (Naver source 채워짐) |
| 다음 조치 | 운영 데이터 누적 후 검증 |

---

## 4. 운영 UI 정리 우선순위 (인벤토리 기반 권고)

본 문서는 인벤토리이지 설계가 아니다. 단 명시적으로 드러난 사항만 기록.

1. **ETF Exposure / 구성종목 Refresh / 중복률** 3 기능은 2026-05-31 Naver 통합으로 **사용 가능** 으로 전환. 운영 데이터 누적 후 검증 진행.
2. **AI 투자세션 복사용 문구**의 [구성종목 / 중복 노출] 섹션은 실 데이터가 채워지면 자동 출력.
3. **AI 투자세션 복사용 문구** (§2.6) 자동으로 **사용 가능** 으로 전환 (구성종목 데이터 흐름 활성화).
4. **Data Status** placeholder — 실 연결은 별도 BACKLOG (이전 동일).
5. 그 외 메뉴 모두 사용 가능.

---

## 5. 참조

- 진단 실측 (직전 source diagnosis): `state/market/constituents_source_diagnosis_latest.json`
- 진단 리포트 (직전 STEP, 현재는 stale — Naver 통합 완료 상태에서는 §2.10 의
  현재 상태 표가 우선): `docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md`
- 다음 STEP 후보: `docs/handoff/POC2_B_NEXT_ACTIONS.md`
- BACKLOG: `docs/backlog/BACKLOG.md`

## 6. 변경 이력

- 2026-05-27 초안 (Source Diagnosis 1차 시점 — ETF Exposure 3 기능 사용 불가
  로 기록).
- 2026-05-31 갱신 (Naver Stock ETFComponent 1차 채택 — ETF Exposure 3 기능 +
  AI 문구 4 기능을 사용 가능 으로 전환). §2.6 / §2.10 / §2.11 / §2.12 의
  현재 상태 표가 권위 있는 기록이며, 이전 분류 (§4 운영 UI 정리 권고의 1번
  항목) 의 "사용 불가" 표현은 §2.6/§2.10~12 의 현재 상태로 대체됨.
- 2026-06-01 갱신 (검증자 A-3 NOTE 반영 — end-to-end asof 흐름 FIX 후속).
  §3.2 (Market Discovery → ETF Exposure) / §3.3 (ETF Exposure → AI Sessions)
  의 "부분 가능" / "source 미확보" 표기를 §2.10~12 와 정합되게 "사용 가능"
  으로 전환. 한 문서 내 같은 기능에 상충 표기가 남지 않도록 정리.
- 2026-06-01 추가 (Market Discovery Evidence Closeout 1차). §2.13a 단기 흐름
  + §2.13b 일간 급등/급락 플래그 + §2.13c NAV / 괴리율 데이터 품질 신규.
  단기 흐름 / 일간 플래그는 사용 가능. NAV / 괴리율은 인프라만 — source 채택
  은 별도 진단 STEP 으로 분기.
- 2026-06-03 추가 (Holdings × Market Discovery Evidence 1차). §2.13d 보유 vs
  시장 evidence 신규 — 사용 가능. 신규 read-only API + Holdings 화면 카드 +
  GenerateDraft [판단 사유] 1줄 통합. Strict Cache-only 정책 (보유 ETF 구성
  종목 외부 source 신규 호출 0건). NAV source 신규 채택 0건 (§2.13c 상태 그대로).
