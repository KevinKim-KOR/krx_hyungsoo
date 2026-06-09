# POC2 — ML 최소 데이터 레인 1차 CONCLUSION

작성: 2026-06-08
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

ML baseline v0 가 바로 읽을 수 있는 **daily feature dataset 2종**을 SQLite 에
적재. CLI 전용 실행 (`scripts/generate_ml_features.py`) — 화면 / refresh 흐름에
hook 0건. **ML 모델 / 라벨 / 예측 / 매수·매도 판단 / 위험 threshold X**. 외부
크롤링 0건. 1137 ETF × 60거래일 → 65,691 row / 4.46초 실측.

---

## 1. AC 달성 현황

```text
AC-1  CLI 배치 실행 (화면 조회 중 실행되지 않음)                = DONE
AC-2  ETF daily feature (return 5/10/20d + 초과수익 + vol + dd + vr + NAV) = DONE
AC-3  Market risk feature (시장 수익률 + universe breadth + NAV 분포 + proxy) = DONE
AC-4  조정장 전조 feature 5종                                  = DONE
AC-5  Join 정합성 (latest available ≤ asof, 미래 데이터 금지)   = DONE (테스트 보장)
AC-6  Feature snapshot 생성                                    = DONE
AC-7  ML readiness 갱신 — 실제 row 기준 7축                   = DONE
AC-8  외부 크롤링 0건                                          = DONE
AC-9  기존 흐름 유지                                          = DONE (pytest 405 passed, 회귀 0)
AC-10 범위 위반 0건                                           = DONE
AC-11 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY / 본 파일) = DONE
```

---

## 2. 변경 파일 (구조)

**Backend 신규 (6 — FIX r2 분리 반영)**:
- `app/ml_feature_store.py` (376 라인) — 2 테이블 schema + EtfMlFeatureRow / MarketRiskFeatureRow
  dataclass + upsert + fetch_readiness. process-level `_INITIALIZED_ML_DBS` 캐시.
- `app/ml_feature_builder.py` (**455 라인**) — orchestrator (build_features) + ETF feature
  + market risk row + 조정장 전조 proxy 산출. **KS-10 near (≥600) 미만** (FIX r2 후).
- `app/ml_feature_primitives.py` (124 라인) — **FIX r2 신규**. 시계열 primitives
  (`PriceSeries`, `build_series`, `return_pct`, `daily_returns`, `volatility_20d`,
  `drawdown_20d`, `volume_ratio_20d`, `excess_vs_kodex200`). 외부 의존 X (statistics 만).
- `app/ml_feature_nav_lookup.py` (78 라인) — **FIX r2 신규**. NAV join 책임 분리.
  `NavRow` + `NavLookup` (etf_nav_daily 1쿼리 인덱싱 + latest available ≤ asof 검색).
- `app/api_ml_readiness.py` (157 라인) — `GET /ml/readiness/latest` 라우터. row 수 + latest asof
  + 7축 status 결정. 외부 source 호출 0건.
- `tests/test_ml_feature_lane.py` — 10 테스트 (store / builder / join 정합성 /
  readiness API / build 미호출 보장). FIX r2 분리 후 회귀 0.

**Backend 수정 (3)**:
- `app/market_data_store.py` — `fetch_price_volume_history()` 신규 (가격+volume
  동시 조회 — 기존 `fetch_price_history` 는 close 만).
- `app/api.py` — `ml_readiness_router` include 2줄.
- `.gitignore` — `state/ml/ml_feature_snapshot_latest.json` 운영 artifact 처리.

**Scripts 신규 (1)**:
- `scripts/generate_ml_features.py` — CLI. `--start-date` / `--end-date` /
  `--lookback-days` (기본 60거래일) / `--ticker` (반복) / `--db` / `--no-snapshot`.

**Frontend 신규 (1)**:
- `frontend/lib/api/mlReadiness.ts` — `fetchMlReadinessLatest()` + 타입 3종.

**Frontend 수정 (2)**:
- `frontend/lib/api/index.ts` — barrel re-export.
- `frontend/app/components/MLTimeseriesReadinessCard.tsx` — 정적 9축 표 →
  API 응답 기반 7축. row 수 / latest asof 동적 표시. 제외 항목 BACKLOG 주석.

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md` — 본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정 + 절충)

### 3.1 적재 범위 — (c) CLI `--start-date` / `--end-date` + 기본 60거래일

지시문 §6.1 / §6.2 는 적재 기간을 명시하지 않았다. (c) 결정에 따라:

- 기본 `--lookback-days=60`: ~3개월 시계열. ML baseline v0 가 첫 학습할 때
  과부족하지 않게 출발.
- `--start-date` / `--end-date` 지정 시 해당 구간만 backfill — 후속 STEP 에서
  5년 backfill 등 자유롭게 확장.

### 3.2 ML readiness 화면 — (γ) 신규 read-only API + 7축 동적 표시

- 기존 `MLTimeseriesReadinessCard` 9축 (정적 status) → 7축 (API 응답 기반).
- 제외 5항목 (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 /
  구성종목 가격 시계열) 은 화면에서 표시하지 않고 BACKLOG 후보로만 관리 — 사용자
  가 "보여주기식 unavailable 줄"을 보지 않도록.

### 3.3 NAV join — latest available ≤ asof, 미래 금지

- `_NavLookup` 이 `etf_nav_daily` 전체를 1 쿼리로 메모리에 인덱싱.
  ticker 별 (asof DESC, created_at DESC) 정렬 → 첫 row.asof ≤ ETF asof 인 row 사용.
- 동일 asof 가 있으면 그것 사용 (NAV refresh 직후 정상 케이스).
- 다른 asof 사용 시 `source_flags="nav_asof=YYYY-MM-DD"` 로 row 에 명시 —
  silent fallback 방지.
- 테스트 `test_build_features_no_future_nav_join` — 미래 NAV 가 절대 join 되지
  않음을 보장.

### 3.4 조정장 전조 feature 5종 — proxy raw value 만, label/threshold X

지시문 §6.3 / §9 — 조정장 label / regime 확정 / 알림 X. 본 라운드에서 저장하는
proxy 는 모두 raw numeric:

- `distance_from_20d_high`: `(close[t] / max(close[t-19..t]) - 1) × 100` — drawdown 과 동의어.
- `volatility_expansion_20d`: `stdev(5d returns) / stdev(20d returns)`. 1.0 초과
  = 단기 변동성 확대.
- `down_day_volume_ratio`: 오늘 KODEX200 수익률 < 0 일 때만 `volume_ratio_20d`.
- `large_negative_day_proxy`: `abs(today_return) × volume_ratio_20d` (음수일 때만).
- `short_term_weakness_proxy`: 최근 3일 모두 음수면 sum, 아니면 0 / None.
- `breadth_deterioration_proxy`: `down_ratio − up_ratio` (universe 일간 breadth).

threshold / label 확정은 ML baseline v0 / 사용자 결정 영역.

---

## 4. 운영 동작

```
사용자: 터미널에서 CLI 실행
  $ python scripts/generate_ml_features.py
  ↓ build_features (KODEX200 거래일 시퀀스 기준, default 60거래일)
  ↓     ├─ KODEX200 시계열 → 거래일 sequence + KODEX returns map
  ↓     ├─ KOSPI benchmark 시계열 → KOSPI returns map
  ↓     ├─ NAV lookup: etf_nav_daily 1쿼리 메모리 인덱스 (ticker DESC asof)
  ↓     ├─ ETF universe (1137) 시계열 prefetch (per-ticker SQL)
  ↓     └─ asof 별 ETF feature row + market risk feature row 생성
  ↓ upsert_etf_features() → etf_ml_feature_daily 65,691건
  ↓ upsert_market_risk_features() → market_risk_feature_daily 60건
  ↓ state/ml/ml_feature_snapshot_latest.json 작성 (gitignored)
  [END] elapsed=4.46s

사용자: ETF Exposure 화면 진입
  ↓ MLTimeseriesReadinessCard mount
  ↓ GET /ml/readiness/latest (외부 source 호출 0건, row count + latest asof + 7축)
  ↓ 7축 표 표시 — etf_rows=65,691 / asofs=60 / latest 2026-06-08 / 7 축 모두 available
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §9 / §7)

- ML 모델 학습 / 예측 결과 / 조정장 결론 / 매수·매도 판단 / 리밸런싱 판단.
- 위험 threshold / label / 상승장·조정장·하락장 최종 판정.
- CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목
  가격 시계열 신규 source.
- Selenium / Playwright / Headless browser / 신규 크롤링 라이브러리.
- Market refresh 자동 hook (지시문 §4 — 화면 / refresh 결합 위험 회피).
- MongoDB / 친구 프로젝트 구조 복제.
- 새 UI 대개편 / Dashboard 변경 / Telegram 문구 변경 / OCI push 연결.

---

## 5.5 FIX r2 (검증자 REJECTED 대응)

검증자 NOTES 2건:

- **A-2 (보고 정확성)**: 보고서에 `ml_feature_builder.py 약 470라인 / near 미만`이라고 했으나 실측 615 라인. backend KS-10 near (≥600) 진입. → **STATE_LATEST §1 + 본 §2 정정 완료**.
- **B-3 / B-6 (파일 책임 과다 / 기술부채)**: 615 라인 = ETF feature + market risk + NAV lookup + breadth/proxy 계산 모두 단일 파일. → **2 모듈 분리**:
  - `app/ml_feature_primitives.py` 124 라인 — `PriceSeries` + 시계열 primitives 함수 (return / volatility / drawdown / volume_ratio / excess).
  - `app/ml_feature_nav_lookup.py` 78 라인 — `NavRow` + `NavLookup` (etf_nav_daily 1쿼리 인덱싱).
  - `app/ml_feature_builder.py` 615 → **455 라인** (near 이탈, builder 책임 = orchestrator + ETF row + market risk row + 조정장 proxy 산출).

분리 후 실측:
- builder 455 / primitives 124 / nav_lookup 78. 모두 backend near (≥600) 미만 (가장 가까운 builder 도 145 라인 여유).
- pytest 405 → 405 passed (회귀 0). 변수 shadowing 1건 발견 + 수정 (build_features 내부 `daily_returns` 지역 변수 → `universe_daily_returns` 로 rename. primitives.daily_returns 함수 import 와 충돌 회피).
- CLI live: 1137 ETF × 60거래일 → 65,691 ETF row + 60 market risk row / 4.28초 (분리 전 4.46초와 동일 — perf 영향 0).

## 6. 검증 결과

- **backend pytest** — PASS (405 passed in 61s, +10 신규 / 회귀 0).
- **black --check** — PASS.
- **flake8** — PASS (slice E203 3건은 black 포맷이라 `# noqa: E203`).
- **frontend ESLint** — PASS.
- **frontend Next.js build** — PASS (warnings 0).
- **CLI live 실측** (운영 SQLite, 1137 ETF × 60거래일):
  - etf_rows=65,691 / market_rows=60 / asofs=60 / elapsed=4.46s / last_asof=2026-06-08.
  - missing_data_summary: etf_universe_count=1137, etf_series_missing=0,
    asof_without_kospi=1 (1일 KOSPI benchmark 누락 — 정상 / `nav_join_status=ok`).
- **Live API** `GET /ml/readiness/latest`:
  - etf_feature_row_count=65,691 / etf_distinct_asof_count=60 / latest=2026-06-08.
  - market_risk_row_count=60 / latest=2026-06-08.
  - 7축 모두 `available`.
- **외부 source 호출 0건** — `_boom` monkeypatch 테스트로 readiness API 가
  build_features 를 호출하지 않음을 보장.

---

## 7. 다음 분기 후보 (사용자 결정 영역)

1. **ML baseline v0** — 본 dataset 입력. 상승 후보 점수화 모델 + 위험 구간 분류
   (binary). 모델 / threshold / label 확정.
2. **CLI hook 추가** — market refresh 직후 자동 ml_features generation
   (현재는 의도적으로 분리).
3. **NAV / 괴리율 시계열 누적 활용** — 본 STEP 에 partial join 형태로 들어가
   있음. 별도 feature 시계열로 분리 누적 검토.
4. **5년 backfill** — 본 STEP 60일은 시작점. `--start-date 2021-06-08` 로 1회
   장기 backfill 가능.
5. **§6.6 제외 항목 (CNN Fear&Greed / VKOSPI 등)** — BACKLOG. 진단 STEP 부터.

본 문서는 다음 STEP 을 임의 확정하지 않는다.

---

## 8. 데이터 스키마 요약 (참조용)

### 8.1 `etf_ml_feature_daily`

PK: `(asof, ticker)`. 컬럼 19종 + `created_at`:

```
asof TEXT NOT NULL
ticker TEXT NOT NULL
name TEXT
close_price REAL
volume INTEGER
return_5d REAL
return_10d REAL
return_20d REAL
excess_return_5d_vs_kodex200 REAL
excess_return_10d_vs_kodex200 REAL
excess_return_20d_vs_kodex200 REAL
volatility_20d REAL                    -- 일간 수익률 stdev (ddof=1, %단위)
drawdown_20d REAL                      -- (close[t] / max(close[t-19..t]) - 1) × 100
volume_ratio_20d REAL                  -- volume[t] / mean(volume[t-19..t])
nav REAL                               -- latest available ≤ asof
nav_market_price REAL
nav_discount_rate_pct REAL
nav_status TEXT                        -- ok / partial / unavailable
source_flags TEXT                      -- "nav_asof=2026-05-29;vol_short" 등
created_at TEXT NOT NULL
```

### 8.2 `market_risk_feature_daily`

PK: `asof`. 컬럼 25종 + `created_at`:

```
asof TEXT PRIMARY KEY
kodex200_return_1d/5d/20d REAL
kospi_return_1d/5d/20d REAL
etf_universe_up_count/down_count/flat_count INTEGER
etf_universe_up_ratio/down_ratio REAL
etf_universe_median_return_1d/5d REAL
nav_discount_avg/abs_avg REAL
nav_discount_extreme_count INTEGER     -- |괴리율| ≥ 3% ETF 수
volatility_20d_market_proxy REAL       -- KODEX200 20d returns stdev
drawdown_20d_market_proxy REAL
distance_from_20d_high REAL            -- drawdown alias
volatility_expansion_20d REAL          -- 5d stdev / 20d stdev
down_day_volume_ratio REAL
large_negative_day_proxy REAL
short_term_weakness_proxy REAL
breadth_deterioration_proxy REAL       -- down_ratio - up_ratio
created_at TEXT NOT NULL
```
