# POC2 — Naver ETF Universe NAV / 괴리율 연동 CONCLUSION

작성: 2026-06-08
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

Naver `finance.naver.com/api/sise/etfItemList.nhn` universe **1회 호출**로
한국 상장 ETF 전체의 NAV / 시장가격 / 괴리율을 수집·저장하고, 기존 Market
Discovery / ETF Exposure / Holdings Evidence 화면에서 unavailable 대신 실제
값을 표시한다. **신규 API 0건. 기존 응답 계약 / `etf_nav_daily` schema /
괴리율 threshold 무변경.** 친구 프로젝트(momentum-etf) 의 패턴을 source 선택
근거로 사용했지만 코드 / 구조는 직접 차용하지 않았다.

---

## 1. AC 달성 현황

```text
AC-1  Naver ETF universe fetcher 추가                       = DONE (app/naver_etf_universe_fetcher.py)
AC-2  전체 ETF NAV 1회 호출 (per-ticker N회 X)              = DONE
AC-3  괴리율 계산 (compute_discount_rate_pct 재사용 가능)    = DONE
AC-4  TTL 30s cache                                         = DONE
AC-5  stale 재사용 (status=partial / message=stale)         = DONE
AC-6  etf_nav_daily 저장 (PK = ticker+asof+source)          = DONE
AC-7  Refresh summary artifact                              = DONE (state/market/nav_discount_refresh_latest.json)
AC-8  Market Discovery 표시 (data_quality.nav_discount)     = DONE (이미 API 단에서 store→payload)
AC-9  ETF Exposure 표시 (NavDiscountPlaceholderCard 전환)   = DONE
AC-10 Holdings Evidence 표시 (Card 종목별 NAV 라인)         = DONE
AC-11 기존 계약 무변경                                       = DONE
AC-12 실패 격리 (Naver 실패 / 일부 필드 누락)               = DONE
AC-13 범위 위반 0건 (매수/매도/threshold/Telegram/MongoDB)   = DONE
AC-14 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY)   = DONE
AC-15 Step CONCLUSION 파일 생성 (본 파일)                    = DONE
```

---

## 2. 변경 파일 (구조)

**신규 (3)**:
- `app/naver_etf_universe_fetcher.py` — Naver `etfItemList.nhn` 호출 + TTL 30s
  + stale 재사용. urllib + socket timeout 만 사용 (신규 라이브러리 0).
- `scripts/refresh_nav_universe.py` — 수동 실행 CLI. asof 자동 결정
  (market_refresh_log 최신 → KST 오늘). `--force` / `--no-summary` 플래그.
- `tests/test_naver_etf_universe.py` — fetcher 단위 + service refresh 12 테스트
  (외부 네트워크 의존 0).

**수정 (Backend)**:
- `app/etf_nav_service.py` — `refresh_nav_universe()` + `NavUniverseRefreshSummary`
  추가. 기존 `refresh_nav()` (per-ticker, MAX 10 cap) 는 호환 보존.
- `app/market_refresh_service.py` — market refresh hook 의 per-ticker NAV 호출
  → universe refresh 로 교체. summary artifact 함께 저장. unused import 정리.

**수정 (Frontend)**:
- `frontend/app/components/HoldingsMarketEvidenceCard.tsx` — `NavDiscountLine`
  컴포넌트 추가. 종목별 NAV / 시장가 / 괴리율 1줄 표시.
- `frontend/app/components/NavDiscountPlaceholderCard.tsx` — props 로 candidates
  받아 NAV ok / unavailable count + 상위 5건 표시. 이전 unavailable 고정 카드
  → 데이터-aware 카드.
- `frontend/app/components/ETFExposureView.tsx` — `NavDiscountPlaceholderCard`
  에 `draft.market_candidates` 전달.
- `frontend/app/components/MarketDiscoveryView.tsx` — SummaryHeader 의 "NAV 미연동"
  배지 → universe 연동 안내 문구로 변경.
- `frontend/app/components/MLTimeseriesReadinessCard.tsx` — NAV / 괴리율 시계열
  axis: `not_integrated` → `partial` (단면 스냅샷 적재됨, 시계열 누적은 미적용).

**수정 (Docs)**:
- `docs/STATE_LATEST.md` — Current position / Latest step / Recent history / Next
  action 갱신.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md` — §0 직전 빈자리 STEP 결과 갱신.
- `docs/handoff/POC2_FEATURE_INVENTORY.md` — §2.13c NAV 데이터 품질 row 갱신.
- 본 파일 (`POC2_NAVER_ETF_UNIVERSE_NAV_INTEGRATION_CONCLUSION.md`) — 신규.

---

## 3. 핵심 설계 결정 (사용자 확정 + 절충)

### 3.1 asof 결정 — (a) market 기준일

지시문 §5.3 의 4단계 순서 중 1순위(응답 명시 asof)는 Naver universe API 에
존재하지 않는다 (분석 보고서 §2.2 비교 표 참조). 따라서 실제로는:

- market refresh hook 안에서 호출되는 경우 → **`end_date_for_prices.isoformat()`** 사용
  (이미 market refresh 가 결정한 asof, SQLite `market_refresh_log` 와 일치).
- 수동 CLI 의 경우 → `market_refresh_log` 최신 성공 row 의 asof → 없으면 KST 오늘.

### 3.2 refresh 실행 — (C) 자동 hook + CLI

지시문 §5.4 의 4가지 허용 방식 중:

- **자동**: `market_refresh_service` 내부 NAV hook 을 universe refresh 로 교체.
  사용자가 "최신 시장 데이터 갱신" 버튼을 누르면 SQLite 시장 갱신 후 자동으로
  Naver universe NAV 도 갱신된다 (1회 호출).
- **수동 CLI**: `scripts/refresh_nav_universe.py` — 디버그 / 강제 백필 용도. 운영
  API / 정기 job 에 연결 X.
- **UI 신규 버튼**: 추가하지 않음 (사용자 학습 비용 0 + 단일 STEP 범위 보존).

### 3.3 stale 캐시 표현 — status=partial 재사용

지시문 §5.2 — 새 enum 추가하지 않고 기존 `status` 분류 (`ok` / `partial` /
`unavailable` / `skipped_timeout`) 안에서 표현. stale 응답으로 채워진 row 는
`status=partial` + `message="stale cache reused"`.

---

## 4. 운영 동작

```
사용자: Market Discovery [최신 시장 데이터 갱신] 버튼 클릭
  ↓ POST /market/refresh
  ↓ market_refresh_service._run_refresh()
  ↓ FDR ETF universe + 가격 수집 + KOSPI benchmark 저장
  ↓ refresh_nav_universe(asof=end_date_for_prices)
  ↓     ├─ TTL 30s 안이면 cache 사용 (외부 호출 0)
  ↓     ├─ TTL 만료 시 GET finance.naver.com/api/sise/etfItemList.nhn (1회)
  ↓     ├─ Naver 실패 시 stale cache 있으면 partial 재사용
  ↓     └─ 전체 universe 일괄 upsert → etf_nav_daily
  ↓ _write_nav_refresh_summary() → state/market/nav_discount_refresh_latest.json
  ↓ market_refresh_log 기록 + state.status=completed
화면 자동 재로드:
  - Market Discovery candidates[].data_quality.nav_discount = 실제 NAV / 괴리율
  - ETF Exposure NavDiscountPlaceholderCard = 상위 5건 표 + ok/unavailable count
  - Holdings Evidence Card 종목 row = "NAV {} · 시장가 {} · 괴리율 {}%"
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §7)

- per-ticker 1,000회 호출 / 대량 병렬 호출.
- MongoDB / 신규 대형 DB.
- 친구 프로젝트(momentum-etf) 의 services / cron / Parquet on Mongo 구조 직접 복제.
- 매수 / 매도 / 교체 / 리밸런싱 / 진입 / 비중 확대 어휘.
- 괴리율 threshold 변경 (`DISCOUNT_CHECK_THRESHOLD_PCT=3.0`, `DISCOUNT_WARNING_THRESHOLD_PCT=5.0` 그대로).
- 신규 API endpoint 추가 / 정기 job 추가 / Telegram 문구 변경 / OCI push 연결.
- NAV / 괴리율 기준 자동 매매 정책 / 투자 추천.
- ML / 백테스트 / threshold / label / factor 확정.
- 새 Workbench 화면 / Dashboard 대개편 / UI 리디자인.

---

## 6. 검증 결과

- **backend pytest** — PASS (391 passed in 138s, 회귀 0 / +12 신규).
- **black --check** — PASS.
- **flake8** — PASS (0건).
- **frontend ESLint** — PASS.
- **frontend Next.js build** — PASS (4 static pages, TypeScript types check PASS).
- **외부 호출 1회 보장** — `refresh_nav_universe()` 내부 fetcher 1회 (caller
  당) + TTL 30s 안에서는 0건. 테스트 `test_fetch_universe_snapshot_uses_ttl_cache`.
- **per-ticker 대량 호출 0건** — 기존 `refresh_nav()` (MAX 10 per-ticker) 의
  market refresh hook 호출이 제거되었다. service 함수 자체는 호환 보존.
- **stale 재사용 동작** — `test_fetch_universe_snapshot_stale_reused_on_failure`
  / `test_refresh_nav_universe_stale_marks_partial`.

---

## 7. 다음 분기 후보 (사용자 결정 영역)

빈자리 후속 원칙 (§POC2_B_NEXT_ACTIONS) 유효. 다음 STEP 후보:

1. **NAV / 괴리율 시계열 누적 활용** — 본 STEP 으로 매 market refresh 마다
   `etf_nav_daily` 에 asof 일자별 row 가 자동 적재된다. 누적된 시계열을 ML
   readiness 의 partial → available 로 승격 + 위험 감지 축 2 의 1차 후보로
   사용할지는 별도 결정.
2. **위험 감지 지표 시계열 적재 1차** — VKOSPI / Fear&Greed / 외국인·기관 수급 /
   시장 폭. ML 2축 중 축 2 선행 조건.
3. **구성종목 가격 시계열 source 진단** — ETF Exposure 등락률 unavailable 해소.
4. **MDD / Sharpe 계산 도입**.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
