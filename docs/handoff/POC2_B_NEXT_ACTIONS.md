# POC2 B 방향 — 다음 액션 (NEXT ACTIONS)

작성일: 2026-05-20 / 갱신: 2026-06-11 (UI 안전실행 — ML evidence 갱신 background job)
성격: **방향을 잊지 않기 위한 앵커.** 새로운 가드 문서가 아니다. 설계 결정이
흔들릴 때 PROJECT_ORIGIN_INTENT 원칙과 함께 본 문서로 복귀한다.

---

## 0. 직전 STEP 결과 (2026-06-11 — UI 안전실행, ML evidence 갱신 background job)

기존 CLI 3종 (`generate_ml_features` → `check_ml_feature_sanity` → `run_ml_baseline_v0`) 을
Data Status 화면의 "ML evidence 갱신 실행" 버튼 1개로 안전하게 background 에서
순차 실행. CLI 는 그대로 살아있음 (이중화). Celery / Redis / 신규 DB / 외부 source
0건. 매수/매도/추천/현금비중/조정장/위험알림 0건.

### 결과 요약

- 신규 모듈 1종: `app/ml_job_runner.py` **447 라인** (KS-10 안전 — 임계 600 미진입).
  job state schema + 3단계 runner + threading.Lock (in-process) + on-disk PID +
  heartbeat (10분 stale 자동 해제).
- 신규 API 2종: `POST /ml/jobs/evidence-refresh` (background 시작, FastAPI
  `BackgroundTasks` 사용, 즉시 반환) + `GET /ml/jobs/latest` (read-only).
  `app/api_ml_jobs.py` **101 라인**.
- 신규 frontend Card: `MLEvidenceRefreshCard` **290 라인** + `frontend/lib/api/mlJobs.ts`
  **79 라인**. DataStatusView 최상단 + 실행 중 5초 polling 자동 갱신 + 단계별 상태 표.
- 단계 실패 시: 이후 단계 skipped + 전체 failed. 기존 snapshot 3종은 **삭제 안 함**
  (마지막 성공 결과 사용자 계속 조회 가능, AC-6).
- 중복 실행 차단: in-process Lock + on-disk status 검사 + PID/heartbeat 10분 stale 자동 해제.
- runtime artifact `state/ml/ml_job_status_latest.json` (gitignored).
- 실측 (uvicorn 직접): POST **2.6ms** 만에 accepted / 중복 POST **2.2ms** 만에
  already_running / 단계별 polling 정확 / 운영 SQLite 로 최종 success
  (evaluated_days=43, baseline_report_status=ok).
- pytest **470 passed** (+16 신규 / 회귀 0, FIX r2 후). black / flake8 / Next.js build PASS.
- **FIX r2 (검증자 1차 REJECTED 후속)**: (A-1/B-6) Windows 에서 `os.kill(pid, 0)` 비결정적 동작 (KeyboardInterrupt 유발) 해소 — `_PID_CHECK_SUPPORTED` OS 분기 추가, Windows 는 heartbeat 만으로 stale 판정. (B-1) status 파일 손상을 미실행과 구분 — `get_latest_status()` (state, error) tuple 반환, API status="error" 응답, POST 도 손상 시 새 job 자동 생성 안 함.
- 사용자 결정 (a)+(a)+(a): in-process BackgroundTasks / PID+heartbeat 10분 stale /
  MLEvidenceRefreshCard 신규.

### 다음 분기 후보

1. **schedule 기반 자동 실행** — 사용자가 시간(예: 18:00) 을 지정해 매일 자동 갱신.
2. **단계별 진행률** — 현재는 단계 단위 상태만 표시. feature 생성 progress bar 등.
3. **실행 히스토리** — 현재는 latest 1건만 저장. 최근 10건 보존 + UI 표.
4. **stale 알림 통합** — ML baseline evidence 가 stale 일 때 GenerateDraft 화면
   에서 "갱신이 필요합니다" 안내 + 본 STEP 의 갱신 버튼으로 deeplink.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-11 — ML Baseline Evidence Draft Integration)

저장된 ML baseline v0 룩백 report 를 GenerateDraft / AI Sessions draft 의 보조
evidence 로 연결. baseline 재계산 / feature 재생성 / 외부 source 호출 / ML 학습 /
HTTP self-call 0건. 매수/매도/추천/현금비중/조정장/위험 알림 0건.

### 결과 요약

- 신규 모듈 1종: `app/ml_baseline_evidence.py` **452 라인** — JSON 파일 직접 read
  (`state/ml/ml_baseline_v0_report_latest.json`), stale 기준 `feature_asof_range.end`
  7일 초과. snapshot builder + bullet builder + factor signal builder + renderer.
- 수정 모듈 2종: `app/draft.py` (Run payload 에 `ml_baseline_evidence_snapshot`
  키 + factor_signals 에 scope="ml_baseline_evidence" entry 1건 추가),
  `app/draft_message.py` ([판단 사유] 섹션 bullet 1줄).
- draft_payload 신규 키 `ml_baseline_evidence_snapshot`: status / report_status /
  report_generated_at / feature_asof_range / evaluated_asof_range /
  candidate_summary / risk_summary / leakage_summary / limitations /
  external_context_checklist (7건) / message — 총 11항목.
- status 5종 자동 판정: ok / warn / stale (7일 초과) / unavailable (report 부재)
  / error (손상 또는 errors 존재).
- AI 외부 context checklist 7건 (CNN Fear&Greed / VIX·VKOSPI / 원유 / USD-KRW /
  미국장·선물 / 지정학 / 한국장 영향 업종) — 외부 수집 구현 0건 (질문 목록만).
- 실측: 운영 SQLite 기준 status=ok / candidate evaluated_days=40 / risk
  evaluated_days=40 / leakage 0 / external checklist 7건. report 부재 / 손상 /
  stale 모두 draft 실패시키지 않음 (조용히 빠지지 않고 status 명시).
- pytest **454 passed** (+22 신규 / 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- 사용자 결정 (a)+(a)+(a): JSON 직접 read / stale 7일 / [판단 사유] bullet 위치.
- **FIX r2 (검증자 1차 REJECTED 후속)**: AC-2 의 AI Sessions / Decision Evidence
  저장 경로 통합 누락 보완. `ai_session_records.ml_baseline_evidence_snapshot_
  json` 컬럼 + 자동 마이그레이션 + insert/get/SELECT 경로 + API 모델 (Create/
  Detail) + frontend (aiSessionsDraft / decisionSessions 타입 + AISessionsCreateTab
  fallback). 신규 테스트 4건 (decision store 3 + ML evidence 통합 2).
- **FIX r3 (검증자 2차 REJECTED 후속, 데이터 계약 단일화)**: AISessionsCreateTab
  fallback 이 raw `{api_status, report_path, report, message}` 를 저장하던 문제 해결.
  backend `GET /ml/baseline-v0/evidence-snapshot` 신규 (GenerateDraft 와 동일 shape).
  frontend `fetchMlBaselineEvidenceSnapshot()` 신규 + AISessionsCreateTab fallback
  교체. fetch 실패 시에도 status="error" 정규화 snapshot 으로 채움 (silent fallback
  제거). 신규 테스트 2건 (evidence-snapshot API ok / unavailable).

### 다음 분기 후보

1. **report stale 시 CLI 재실행 안내 UI** — Data Status 카드 옆 안내 배지.
2. **5년 backfill 후 evidence 신호 강도 시계열 분해** — rolling window.
3. **§6.6 제외 source** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급) — BACKLOG.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-1. 이전 STEP 결과 (2026-06-11 — ML Baseline v0 룩백 검증)

현재 feature dataset 이 과거 구간에서 (1) 상승 후보 발굴 / (2) 위험 구간 감지
baseline 으로 의미가 있었는지 룩백 검증. CLI 전용. 매수/매도 판단 X,
위험 알림 X, 조정장 확정 X, 위험 threshold X.

### 결과 요약

- 신규 모듈 4종 (FIX r2 후 실측): `app/ml_baseline_targets.py` (352) + `ml_baseline_candidate.py` (426) +
  `ml_baseline_risk.py` (390) + `ml_baseline_v0.py` (199 — orchestrator). KS-10 trigger/near 0건.
- 신규 API: `GET /ml/baseline-v0/latest` (snapshot read-only, 재계산 X / 외부 호출 X).
- CLI: `scripts/run_ml_baseline_v0.py` + Snapshot `state/ml/ml_baseline_v0_report_latest.json` (gitignored).
- Frontend 신규: `MLBaselineV0Card` (DataStatusView 하단). 매수/매도/위험 알림 문구 0건.
- 사용자 결정: (a) candidate top group = top quintile 20%, (a) risk group split = market composite tercile 1/3, (a) horizon tail = max horizon 20d 제외.
- 실측 (1137 ETF × 60거래일 / 평가 40거래일): **status=ok**. leakage 0. candidate top group 5d/10d/20d future return = 3.4%/5.5%/13.5% vs universe median 1.1%/2.1%/4.7%. risk high vs low future drawdown 10d = -8.1% vs -3.4% (위험 group 약 2.4x), drawdown_capture_rate 10d = 1.44.
- pytest **432 passed** (+15 신규, 회귀 0, FIX r2 후). black / flake8 / ESLint / Next.js build PASS.

### 다음 분기 후보

1. **NAV 일별 적재 / backfill** — Sanity 가 노출한 unavailable_ratio 0.98 해소.
2. **5년 backfill** — `--start-date 2021-06-08` 로 평가 가능 거래일 ≫ 40일 확장.
3. **Baseline v0 후속 — 시계열 rolling window 평가**: 본 STEP 의 단일-기간 평균을 rolling window 별로 분해.
4. **§6.6 제외 항목** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등) — BACKLOG.

본 문서는 다음 STEP 을 임의 확정하지 않는다. 사용자 결정 대기.

---

## 0-2. 이전 STEP 결과 (2026-06-08 — ML Feature Sanity Check)

ML baseline v0 입력 직전 데이터 품질 검산. CLI 전용. 4 sub-check
(coverage / calculation / NAV join / risk proxy).

### 결과 요약

- 신규 모듈 2종: `app/ml_feature_sanity.py` (561 라인 — FIX r3 후) +
  `ml_feature_sanity_helpers.py` (141 라인). KS-10 trigger/near 0건.
- 신규 API: `GET /ml/feature-sanity/latest`. CLI: `scripts/check_ml_feature_sanity.py`.
- Snapshot: `state/ml/ml_feature_sanity_latest.json` (gitignored).
- Frontend: `MLFeatureSanityCard`.
- FIX r3 (검증자 1차 REJECTED 반영): coverage §4.3 누락 보강 (ticker별 row 누락 + asof drop) + snapshot 손상 fail-loud + untracked staging.
- 실측 (FIX r3 후): sanity_status=warn / ticker 1137 중 row 누락 69건 신규 감지 / calc 0 err / future_nav_join=0. pytest 417 passed.

### 다음 분기 후보 (당시)

→ 본 STEP (ML Baseline v0 룩백 검증) 으로 진입 (사용자 결정).

---

## 0-3. 이전 STEP 결과 (2026-06-08 — ML 최소 데이터 레인 1차)

ML baseline v0 입력 직전 데이터 품질 검산. CLI 전용 실행. ML 모델 / 위험 threshold /
매수·매도 판단 X.

### 결과 요약

- 신규 모듈: `app/ml_feature_sanity.py` (491 라인) + `app/ml_feature_sanity_helpers.py`
  (141 라인, FIX r2 분리). 4 검산 (coverage / calculation / NAV join / risk proxy).
- 신규 API: `GET /ml/feature-sanity/latest` (snapshot read-only, 재계산 X).
- CLI: `scripts/check_ml_feature_sanity.py` + Snapshot `state/ml/ml_feature_sanity_latest.json` (gitignored).
- Frontend: `MLFeatureSanityCard` (DataStatusView) — 7축 sub-check 상태 + 샘플 ETF 10건.
- 허용 오차 (사용자 결정 b): `abs_tol=1e-4 + rel_tol=1e-4`. risk proxy 이상치는 null 비율만 (사용자 결정 f).
- 실측: 1137 ETF × 60일 / sanity_status=warn / calc 0 error / future_nav_join=0 /
  risk all-null=0 / warning 2건 (NAV 분포 unavailable_ratio 0.983 — universe NAV refresh 1회만 적재된 운영 상태).
- pytest 414 passed (회귀 0). Next.js build PASS.

### 다음 분기 후보

1. **ML baseline v0** — 본 sanity check 통과한 dataset 입력. 상승 후보 점수화 +
   위험 구간 분류 binary 모델. threshold / label 확정 (별도 STEP).
2. **NAV 일별 적재 / backfill** — sanity 가 노출한 unavailable_ratio 0.983 해소.
   `etf_nav_daily` 가 universe refresh 1회만 적재 → 일별 누적 흐름 설계.
3. **5년 backfill** — `--start-date 2021-06-08` 로 장기 시계열 적재.
4. **§6.6 제외 항목 (CNN Fear&Greed / VKOSPI / 외국인·기관 수급 등)** — BACKLOG.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — ML 최소 데이터 레인 1차)

ML baseline v0 가 바로 읽을 수 있는 daily feature dataset 을 SQLite 에 적재.
CLI 전용 실행 — 화면 / refresh 흐름 hook 0건. ML 모델 / 라벨 / 예측 / threshold X.

### 결과 요약

- 신규 테이블 2종 (`etf_ml_feature_daily` PK=(asof,ticker), `market_risk_feature_daily` PK=asof).
- 신규 모듈 3종: `app/ml_feature_store.py` / `app/ml_feature_builder.py` /
  `app/api_ml_readiness.py`.
- 신규 CLI: `scripts/generate_ml_features.py` (`--start-date` / `--end-date` /
  `--lookback-days` 기본 60거래일 / `--ticker` / `--no-snapshot`).
- 신규 read-only API: `GET /ml/readiness/latest`.
- `MLTimeseriesReadinessCard` 7축으로 갱신 (정적 9축 → API 응답 기반 7축).
- Snapshot: `state/ml/ml_feature_snapshot_latest.json` (gitignored).
- 실측: 1137 ETF × 60일 → 65,691 ETF row + 60 market risk row / 4.46초.
- pytest 405 passed (395 → 405 / 회귀 0). Next.js build PASS.

### 다음 분기 후보

ML baseline v0 가 본 dataset 을 입력으로 바로 시작 가능. 분기:

1. **ML baseline v0** — 본 feature dataset 을 입력으로 상승 후보 점수화 모델 +
   위험 구간 분류 (binary). 모델 / threshold / label 확정은 본 STEP 내용을 기반
   으로 새 STEP 에서 진행.
2. **CLI hook** — market refresh 직후 자동 ml_features generation hook 추가
   (현재는 의도적으로 분리).
3. **NAV / 괴리율 시계열 누적** — 이미 본 feature 에 join 되어 일부 노출. 별도
   feature 시계열로 분리 누적 검토.
4. **CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목
   가격 시계열** — 본 STEP §6.6 에서 제외 명시. BACKLOG 후보.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — Market Discovery UI / Perf 후속 정리)

NAV / Discount Display FIX 직후 사용자가 즉시 보낸 UI 정리 요청 / perf 지적 5건을
연속 commit (`6c3728ec` → `8fad2bb4`) 으로 반영. 별도 STEP 보고서는 만들지 않고
검증자 전달용 note 만 생성 (`POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md`).

핵심:
- CandidateTable 컬럼 정리 (source/status/정렬기준/태그 제거, 6m/12m/1y/3y 추가).
- TopControlsRow 1 카드 안에 갱신+필터 + AI Sessions·ETF Exposure 전달 버튼 묶기.
- MarketContextCard 헤더에 `(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)` 표기 +
  현재가/MA20/MA60 천단위 콤마.
- 백엔드 `MarketReturns` 모델 6m/12m/3y 필드 추가 (lookback 180/365/1095).
- `/market/topn/latest` 응답 2.4s → 0.85s (process-level init_db 캐시 + name bulk).

다음 분기 후보 영향: 없음 (분류는 §0-1 유지).

---

## 0-2. 직전 빈자리 채우기 STEP 결과 (2026-06-08 — NAV / Discount Display FIX)

직전 STEP(Naver ETF Universe NAV / 괴리율 연동)이 저장은 완료했지만 사용자가
주요 화면에서 NAV 값을 한눈에 확인하기 어려운 표시 누락이 있었다. 본 FIX 로
표시 매트릭스 6필드 × 4화면 모두 visible 상태로 정정.

### 결과 요약

- 신규 read-only API `GET /market/nav-discount/latest` — 저장된 `etf_nav_daily`
  전체 ETF (1136건 실측) 1회 응답. 외부 source 호출 X, refresh X.
- Data Status 화면 재설계 — placeholder → 전체 ETF NAV / 시장가 / 괴리율 표 +
  검색(ticker/이름) + status 필터 + 괴리율 정렬.
- Market Discovery CandidateTable — NAV / 시장가 / 괴리율 / asof / source /
  status 6 컬럼 직접 노출 (FIX 라운드 2 에서 tooltip → 직접 컬럼으로 정정).
- ETF Exposure NavDiscountPlaceholderCard — flag/source 통합 컬럼 → asof / source /
  status 분리 컬럼 + flag 인라인.
- Holdings Evidence NavDiscountLine — asof / status 추가 (이전 NAV·시장가·괴리율·source).
- 표시 매트릭스 (지시문 §5): MD/ETF Exposure/Holdings Evidence/전체 ETF 조회 × NAV·시장가·괴리율·asof·source·status = 모두 visible.
- 기존 `data_quality.nav_discount` 응답 계약 / `etf_nav_daily` schema 무변경.
- pytest 395 passed (391→395 / 회귀 0). Next.js build PASS.

---

## 0-1. 이전 STEP 결과 (2026-06-08 — Naver ETF Universe NAV / 괴리율 연동)

NAV / Discount Source Diagnosis 1차 (2026-06-07) 에서 발굴한 source 후보 +
친구 프로젝트(momentum-etf) 분석으로 확인한 `finance.naver.com/api/sise/etfItemList.nhn`
universe 단일 호출 패턴을 운영 fetcher 로 채택.

### 연동 결과

- 신규 모듈: `app/naver_etf_universe_fetcher.py` — TTL 30s + stale 재사용.
- `etf_nav_service.refresh_nav_universe()` 추가 — 1회 호출 → 전체 ETF universe
  `etf_nav_daily` upsert (per-ticker N회 호출 패턴 폐기).
- `market_refresh_service`: 기존 NAV hook(per-ticker 10건 cap)을 universe refresh
  로 교체. 실패 격리 정책 유지.
- `scripts/refresh_nav_universe.py`: 수동 실행 CLI (운영 API / 정기 job 연결 X).
- summary artifact: `state/market/nav_discount_refresh_latest.json`.
- Frontend: Market Discovery / ETF Exposure NavDiscountPlaceholderCard /
  Holdings Evidence Card 모두 unavailable 고정 → 실제 NAV / 시장가 / 괴리율 표시.
- 기존 `data_quality.nav_discount` 응답 계약 / `etf_nav_daily` schema /
  괴리율 threshold 무변경. 신규 API 0건. MongoDB 추가 0건.

### 다음 분기 후보 (사용자 결정 영역)

1. **NAV / 괴리율 시계열 누적** — universe 단면 스냅샷 → asof 일자별 누적.
   `etf_nav_daily` PK 가 이미 `(ticker, asof, source)` 라 자동 누적되지만,
   누적된 시계열을 ML readiness 카드에 반영하고 위험 감지 축 2 의 1차 후보로
   사용할지는 별도 결정.
2. **위험 감지 지표 시계열 적재 1차** — VKOSPI / Fear&Greed / 외국인·기관 수급 /
   시장 폭 후보 진단.
3. **구성종목 가격 시계열 source 진단** — ETF Exposure 등락률 unavailable 해소.
4. **MDD / Sharpe 계산 도입**.

---

## 0-1. 이전 빈자리 채우기 STEP 결과 (2026-06-07 — NAV / Discount Source Diagnosis 1차)

ETF Exposure Data Unfolding 1차 §0 "빈자리 후속 원칙" 에 따라 NAV / 괴리율
source 진단을 수행. 운영 fetcher 교체 X, source integration X.

### 진단 결과 요약

- pykrx (ohlcv / price_deviation): 모든 ticker × 날짜 empty → **unusable**
- FinanceDataReader: 시장가격 안정, NAV 직접 제공 X → **hold_unstable**
  (NAV source 와 결합 시 괴리율 계산 후보)
- Naver Mobile stock integration API: NAV + 시장가격 4/4 ticker OK
  (`$.etfKeyIndicator.nav`, `$.dealTrendInfos[0].closePrice`)
  → **hold_unstable** (비공식 endpoint — 운영 안정성 추가 진단 권고)
- Naver ETF dedicated endpoint 후보: 전부 HTTP 404 → **unusable**

**adopt_candidate 0건**. 단, naver_mobile_stock_integration 은 운영 안정성
추가 검증 STEP 거치면 adopt 승격 가능.

### 다음 분기 후보 (사용자 결정 영역)

빈자리 후속 원칙은 그대로 유효하다 — 다음 기능 STEP 은 여전히 빈자리 중
하나를 채우는 STEP 으로 제한한다.

1. **Naver Mobile NAV Source Stability 1차** — naver_mobile_stock_integration
   응답시간 / TTL / schema 변경 모니터링 / 다일 sample 확장. 결과에 따라
   adopt_candidate 승격 또는 unusable 하향.
2. **다른 빈자리로 전환** — 구성종목 가격 시계열 source 진단, 위험 감지 지표
   시계열 적재 후보 진단 등 (BACKLOG 참고).
3. **KRX OPEN API 인증키 확보 검토** — hold_auth_required 후보 발굴.

위 분기 중 어느 것을 선택할지는 사용자 결정. 본 문서에서 임의 확정하지 않는다.

---

## 0. 현재 최우선 작업 (2026-06-06 — ETF Exposure Data Unfolding 1차 완료)

### ETF Exposure Data Unfolding 1차 (DONE)

기존 ETF Exposure 화면의 구성종목 / 중복률 / 반복 핵심 종목 데이터를 펼쳐서
비교 가능하게 표시. Holdings Evidence 와는 State Bridge (명시 호출 버튼) 로
결합. ML / 위험 감지에 필요한 시계열 데이터 9축의 준비 상태를 화면 + 문서에
명시.

- 신규 API 0건. 신규 source 0건. 시계열 적재 job 0건.
- 신규 컴포넌트 3건: HoldingsOverlapBridgeCard / NavDiscountPlaceholderCard /
  MLTimeseriesReadinessCard.
- 위험 감지는 "하락 예측"이 아니라 "위험 구간 분류" 로 정의 — INTENT §9.5,
  ASSUMPTIONS Q6.
- pytest 379 passed (회귀 0). frontend Next.js build PASS.

### 빈자리 후속 원칙 (불변)

**ETF Exposure Data Unfolding 1차 이후 다음 기능 STEP 은 본 STEP 에서 드러난
빈자리 중 하나를 채우는 STEP 으로 제한한다.**

화면 + 문서에 명시된 빈자리:

1. **NAV / 괴리율 source** — `not_integrated`. source 진단 STEP 후보.
2. **구성종목 가격 시계열** — `not_integrated`. 구성종목 등락률 unavailable
   해소.
3. **위험 감지 지표 시계열** (변동성 / 거래량 급변 / 외국인·기관 수급 / 시장 폭) —
   `not_collected` / `not_calculated`. 축 2 선행 조건.
4. **MDD / Sharpe 계산** — 현재 미구현. 시계열 적재 후 1차 지표.

어떤 빈자리를 먼저 채울지는 **사용자 판단 영역**이다. 본 문서에서 임의로
순서를 확정하지 않는다.

위 제약은 ML / 백테스트 / 자동 매수·매도 판단 추가를 금지하는 의미가 아니라,
**시계열 데이터가 부족한 상태에서 ML 모델로 점프하지 않는다**는 의미다.

본 문서는 다음 챕터 진입자가 한 번 읽고 "지금 무엇을 해야 하는지" 를 즉시
파악할 수 있도록 작성되었다 — 단기 (현재 STEP) / 중기 (바로 다음 후보) /
보류 (지금 멈춘 것) 의 3 단으로만 구분한다.

---

## 1. 현재 최우선 작업 (2026-06-03 — Holdings × Market Discovery Evidence 1차 완료)

### Holdings × Market Discovery Evidence 1차 (DONE)

사용자의 실제 holdings 를 Market Discovery evidence (TOP N 후보 일치 여부 /
시장 국면 / KODEX200 대비 1m·3m 초과수익 / 5·10·20거래일 단기 흐름 / 구성종목
중복 / NAV) 와 raw evidence 수준에서 연결했다. PROJECT_ORIGIN_INTENT §3 PC
작업 4~5단계 (매매 결정 / 보류 + 결정 기록) 의 정량 재료 1차.

- 신규 read-only API `GET /holdings/market-evidence/latest` — 외부 fetch 0건.
- GenerateDraft 가 같은 evidence builder 를 재사용 — draft_payload.holdings_market_evidence_snapshot
  + factor_signals scope="holdings_market_evidence" + [판단 사유] 1줄.
- Strict Cache-only: 보유 ETF 구성종목 외부 source 신규 호출 0건.
- NAV source 신규 채택 0건 (기존 unavailable 흐름 유지).
- 매수/매도/교체 판단 어휘 0건 (회귀 테스트로 보장).
- pytest 379 passed (354 → 379, +25 신규 / 회귀 0).

### 다음 큰 방향 (사용자 결정 대기)

1. **AI Sessions 기록 복기 구조** — 누적 기록의 검색 / 비교 / 후속 판단
   회수율 측정.
2. **NAV / 괴리율 source 진단 STEP** — 직전 ETF Constituents Source Diagnosis
   패턴 따라 source 후보 smoke test 후 채택 검토.
3. **보유 ETF 구성종목 외부 source 채택** — Strict Cache-only 가 본 STEP
   범위였으므로 보유 ETF 의 구성종목 cache 가 없는 경우 후속 STEP 에서 채택
   여부 결정 (BACKLOG 후보).
4. **ML factor 후보 정리** — ASSUMPTIONS Q1 (여러 factor 를 붙일 수 있는
   구조의 엔진).
5. **ML / 백테스트 연결**.

### 별도 분기 후보 (Market Discovery 영역으로 회귀하는 경우만)

- **NAV / 괴리율 source 진단 STEP** — 직전 ETF Constituents Source
  Diagnosis 패턴 따라 Naver Stock detail endpoint 등 candidate source
  smoke test 후 채택 검토.

### (이전) KS-10 Cleanup: API Client / Type 책임 분리 (DONE 2026-06-03)

`frontend/lib/api.ts` 993 라인 단일 파일을 도메인 8개 모듈 + barrel 로 분리.
`@/lib/api` import 호환 유지 (21 컴포넌트 0건 수정). 활성 코드 trigger / near 0.
검증자 NOTE FIX 2건 반영 — A-2 카운트 정정, B-6 `request` barrel public 제외.

### (이전) Market Discovery Evidence Closeout 1차 (DONE 2026-06-01)

본 STEP 으로 Market Discovery 1차 증거 묶음을 마감했다. 단기 흐름 + 일간
플래그 + NAV / 괴리율 인프라 + AI Sessions 증거 snapshot 까지 통합 완료.
**Market Discovery 계열 신규 기능 확장은 일단 중단**한다.

### (이전) ETF Constituents Naver Source Integration (DONE 2026-05-31)

본 STEP 의 산출물은 [docs/handoff/STATE_LATEST_ARCHIVE.md](STATE_LATEST_ARCHIVE.md) §0.1 (2026-05-31 ETF Constituents Naver Source Integration) 참조.

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
