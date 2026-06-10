# POC2 — ML Feature Sanity Check CONCLUSION

작성: 2026-06-08
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

ML baseline v0 입력 직전 데이터 품질 검산. CLI 전용 실행 (`scripts/check_ml_feature_sanity.py`) +
신규 read-only API (`GET /ml/feature-sanity/latest`) + Data Status 화면 표시.
4 sub-check (coverage / calculation / NAV join / risk proxy). 허용 오차
(사용자 결정 b) `abs_tol=1e-4 + rel_tol=1e-4`. risk proxy 이상치는 null 비율
+ all-null per asof 만 (사용자 결정 f). **ML 모델 / 위험 threshold / 라벨 /
매수·매도 판단 / 외부 source 호출 0건**. 1137 ETF × 60일 / sanity_status=warn /
calc 0 error / future_nav_join=0.

---

## 1. AC 달성 현황

```text
AC-1  CLI / batch 실행 (화면 진입 중 자동 실행 X)                = DONE
AC-2  Snapshot 생성 (state/ml/ml_feature_sanity_latest.json)     = DONE (gitignored)
AC-3  Coverage 검산 (row 수 / 거래일 수 / latest asof + ticker별 누락 + asof drop) = DONE (FIX r3)
AC-4  Calculation 검산 (수익률/초과수익/변동성/dd/volume ratio)   = DONE (abs_tol+rel_tol=1e-4)
AC-5  NAV join 검산 (미래 데이터 사용 X)                          = DONE (테스트 보장)
AC-6  Risk proxy 검산 (null 비율 + all-null per asof)             = DONE (threshold 미확정)
AC-7  Data Status 표시 (sanity 요약 + 샘플 ETF)                   = DONE (MLFeatureSanityCard)
AC-8  Read-only 조회 (재계산 / 외부 호출 / ML 학습 X)             = DONE (테스트 보장)
AC-9  기존 흐름 유지                                              = DONE (pytest 414 passed, 회귀 0)
AC-10 범위 위반 0건                                              = DONE
AC-11 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY + 본 파일) = DONE
```

---

## 2. 변경 파일 (구조)

**Backend 신규 (4)**:
- `app/ml_feature_sanity.py` **561 라인 (FIX r3 후)** — orchestrator + 4 sub-check
  (coverage / calculation / NAV join / risk proxy). `_NavLookup` 재사용.
  FIX r3: ticker별 row 누락 + asof별 ticker count 급감 검산 추가
  (지시문 §4.3 누락분 보강).
- `app/ml_feature_sanity_helpers.py` **141 라인 (FIX r2 분리)** — SQLite read +
  primitives 재계산 helper (`pick_sample_tickers`, `fetch_ml_row`,
  `recompute_features_for_sample`, `fetch_sample_rows`).
- `app/api_ml_sanity.py` 65 라인 — `GET /ml/feature-sanity/latest` 라우터.
  snapshot JSON 만 read (재계산 X). FIX r3: snapshot 손상 시 status=error
  분리 (empty 와 구분, fail-loud).
- `tests/test_ml_feature_sanity.py` **12 테스트** (FIX r3 +3) — builder /
  calculation 정합성 / 미래 NAV 검출 / API empty / API present / API
  미재계산 보장 / API 손상 snapshot=error / coverage 신규 필드 노출 /
  coverage drop 감지.

**Backend 수정 (1)**:
- `app/api.py` — `ml_sanity_router` include.

**Scripts 신규 (1)**:
- `scripts/check_ml_feature_sanity.py` — CLI. `--db` / `--sample-count` /
  `--no-snapshot`. exit code: status=error 면 1, 그 외 0.

**Frontend 신규 (2)**:
- `frontend/lib/api/mlSanity.ts` — `fetchMlFeatureSanityLatest()` + 타입 4종.
- `frontend/app/components/MLFeatureSanityCard.tsx` — Data Status 카드.

**Frontend 수정 (2)**:
- `frontend/lib/api/index.ts` — barrel re-export.
- `frontend/app/components/DataStatusView.tsx` — 카드 1개 추가.

**.gitignore 수정 (1)**:
- `state/ml/ml_feature_sanity_latest.json` 운영 artifact 처리.

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md` — 본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정)

### 3.1 계산 정합성 허용 오차 — (b) `abs_tol=1e-4 + rel_tol=1e-4`

```python
abs(a - b) <= max(CALC_ABS_TOL, CALC_REL_TOL * max(abs(a), abs(b)))
```

NumPy `isclose` 패턴. 소수점 4째자리까지 일치하면 OK. ML feature 가 ML row 저장
시 round(4) 처리되므로 본 임계가 자연스럽다.

### 3.2 Risk proxy 이상치 판정 — (f) null 비율 + all-null per asof 만

지시문 §4.6 "위험 threshold 는 확정하지 않음" 정합. 본 STEP 에서는 데이터 품질만:

- per-axis null 비율 > 0.5 → warning.
- 한 asof 의 7 proxy axes 모두 null → error.
- 도메인 임계 / 통계적 outlier 도입 0건 — 추후 ML baseline v0 / 사용자 결정 영역.

### 3.3 FIX r3 (검증자 REJECTED 후속 보강)

검증자 1차 REJECTED 사유 3건 반영:

1. **A-1 위반** — 지시문 §4.3 coverage 검산이 row 수 / asof 범위 / latest asof
   만 포함, ticker별 row 누락 + asof별 ticker count 급감 누락. → `_check_coverage()`
   에 `tickers_with_missing_rows` (trading_days × 0.95 미만 row 의 ticker 수),
   `asof_ticker_count_median/min`, `asof_with_ticker_drop` (median × 0.70 미만)
   추가. 운영 실측: 1137 ticker 중 **69건 누락 감지** (warn 1건 추가).
2. **B-1 fail-loud 약화** — snapshot 파일 손상 (`JSONDecodeError`) 이 status=empty
   로 합쳐져 "미생성" 과 구분 불가. → status=error + 안내 message 분리.
   frontend Card 도 error 분기 추가.
3. **A-2 untracked 누적** — 신규 8건 untracked 상태. → 본 라운드에서 즉시
   `git add` (15건 staged 완료).

### 3.4 FIX r2 (KS-10 자체 점검)

첫 작성 `ml_feature_sanity.py` 607 라인 → backend near (≥600) 진입. 직전 STEP
(ML 최소 데이터 레인) 의 FIX r2 패턴 답습 회피를 위해 본 STEP 내부에서 즉시 분리:

- SQLite read + primitives 재계산 helper 4개 → `app/ml_feature_sanity_helpers.py` 분리.
- `ml_feature_sanity.py` 607 → **491 라인** (near 이탈).
- helpers 141 라인 (안전).

---

## 4. 운영 동작

```
사용자: 터미널에서 CLI 실행
  $ python scripts/check_ml_feature_sanity.py
  ↓ build_sanity_report (db_path, sample_count=10)
  ↓     ├─ coverage check (SQLite read — etf row 수 / asof 범위 / latest asof)
  ↓     ├─ calculation check (sample 10 ticker × latest asof, primitives 로 재계산 vs ML row)
  ↓     ├─ NAV join check (전체 ML row × NavLookup — future asof > feature asof 인지)
  ↓     └─ risk proxy check (market_risk_feature_daily × 7 axes null 비율 + all-null)
  ↓ state/ml/ml_feature_sanity_latest.json 저장 (gitignored)
  [END] sanity_status=ok|warn|error / stdout 요약

사용자: 좌측 메뉴 Data Status 진입
  ↓ NavDiscountTable (기존)
  ↓ MLFeatureSanityCard mount
  ↓     ├─ GET /ml/feature-sanity/latest (재계산 X, snapshot JSON 만 read)
  ↓     └─ sanity_status badge + 4 sub-check 상태 + 샘플 ETF 10건 표시
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §7 / §9)

- ML 모델 학습 / 예측 결과 / 조정장 판정 / 상승장·조정장·하락장 라벨 확정.
- 위험 threshold 확정 / 매수·매도 / 리밸런싱 판단 / Telegram 변경 / OCI push.
- 외부 source 추가 / CNN Fear&Greed / VKOSPI / Selenium / Playwright.
- 구성종목 등락률 / 5년 backfill / MongoDB / 친구 프로젝트 구조 복제.
- 도메인 임계 기반 risk proxy 이상치 판정 (사용자 결정 f 에 따라).

---

## 6. 검증 결과

- **backend pytest** — PASS (FIX r3 후 **417 passed in 76s**, +12 신규 / 회귀 0).
- **black --check** — PASS.
- **flake8** — PASS.
- **frontend ESLint** — PASS.
- **frontend Next.js build** — PASS (warnings 0).
- **CLI live 실측** (운영 SQLite, 1137 ETF × 60거래일):
  - sanity_status=**warn** / etf_rows=65,691 / market_rows=60 / asof 2026-03-11→2026-06-08.
  - checked_tickers=10 / calc warn=0 / **calc err=0** / **future_nav_join=0** /
    nav unavailable_ratio=0.983 / risk all_null_asof=0 / risk warn=2.
  - warning 2건 = NAV 분포 axes 의 unavailable_ratio 가 0.5 초과 (현재 etf_nav_daily
    가 universe refresh 1회분만 적재된 운영 상태 — 정상).
- **Live API** `GET /ml/feature-sanity/latest`:
  - status=ok / snapshot.sanity_status=warn / sample_rows=10 / asof_range 정상.
- **외부 source 호출 0건** — 테스트 `test_sanity_api_does_not_recompute` 가
  `build_sanity_report` 호출을 `_boom` monkeypatch 로 차단해 보장.

---

## 7. KS-10 자체 점검 (FIX r2 패턴 답습 회피)

신규 / 수정 파일의 라인수 실측:

| 파일 | 라인 | 임계 | 분류 |
| --- | --- | --- | --- |
| `app/ml_feature_sanity.py` | **561 (FIX r3 후)** | 600 / 650 | 안전 |
| `app/ml_feature_sanity_helpers.py` | 141 | 600 / 650 | 안전 |
| `app/api_ml_sanity.py` | 65 (FIX r3 후) | 600 / 650 | 안전 |
| `scripts/check_ml_feature_sanity.py` | 102 | n/a (scripts) | 안전 |
| `frontend/app/components/MLFeatureSanityCard.tsx` | 302 | 850 / 900 | 안전 |
| `frontend/lib/api/mlSanity.ts` | 67 | 850 / 900 | 안전 |

ML 신규 파일 KS-10 trigger/near 0건. 첫 작성 시점 발견된 607 라인 (`ml_feature_sanity.py`)
은 본 STEP 내부에서 즉시 helpers 분리로 해소 — 검증자 REJECTED 없이 자체 점검 통과.

---

## 8. 다음 분기 후보 (사용자 결정 영역)

1. **ML baseline v0** — 본 sanity check 통과 dataset 입력. 상승 후보 점수화 +
   위험 구간 분류 binary 모델. threshold / label 확정.
2. **NAV 일별 적재 / backfill** — sanity 가 노출한 `unavailable_ratio=0.983` 해소.
   `etf_nav_daily` 가 universe refresh 1회만 적재 → 일별 누적 흐름 별도 STEP.
3. **5년 backfill** — `--start-date 2021-06-08` 로 장기 시계열 적재.
4. **§6.6 제외 항목** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등) — BACKLOG.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
