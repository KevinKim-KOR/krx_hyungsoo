# POC2 기능 인벤토리 (Feature Inventory)

작성일: 2026-05-27 / 갱신: 2026-05-31 (Naver Stock ETFComponent 1차 채택)
성격: **현재까지 만든 기능을 누락 없이 기록하는 운영 인벤토리.** 새 기능 정의가
아니며, 운영 UI 정리의 기준점으로 사용한다.

본 문서는 ETF Constituents Source Diagnosis 1차의 §11 명시 산출물이다.

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
