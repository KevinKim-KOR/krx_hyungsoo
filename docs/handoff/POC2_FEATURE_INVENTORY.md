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
| 기능 목적 | KRX 상장 ETF universe 에서 TOP N 발굴 (일간/1개월/3개월 수익률 기준) |
| 사용 가능 여부 | **사용 가능** |
| 데이터 소스 상태 | `state/market/market_data.sqlite` (FDR universe + ETF 가격) |
| 운영 UI 포함 여부 | 포함 |
| 테스트용/임시 여부 | 아님 |
| 다음 조치 | 현재 상태 유지 |

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
| 기능명 | 시장 데이터 상태 placeholder |
| 현재 메뉴 위치 | 좌측 7번 |
| 기능 목적 | 시장 데이터 갱신 상태 확인 (계획) |
| 사용 가능 여부 | **테스트용** |
| 데이터 소스 상태 | placeholder — 실제 연결 미구현 |
| 운영 UI 포함 여부 | 포함 (placeholder) |
| 테스트용/임시 여부 | 예 |
| 다음 조치 | BACKLOG: "Data Status 실제 연결" |

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
