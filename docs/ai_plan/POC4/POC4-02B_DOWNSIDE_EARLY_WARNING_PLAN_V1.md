# POC4-02B — 위험 구간 조기감지 기준선 PLAN V1

```text
POC4_SEQUENCE_REVISION       = POC4_SEQUENCE_V2 반영 (설계서 docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md)
POC4_02A_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS (docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md §6)
POC4_02B_PLAN              = PASS_WITH_MANDATORY_AMENDMENTS (설계자 판정 2026-09-25 · 확정 13건 §8 · 계약 §3~§7)
PLAN_RESUBMISSION_REQUIRED = NO · IMPLEMENTATION = AUTHORIZED_AFTER_DOCUMENT_SYNC (동기화 2026-09-25 완료) · COMMIT_PUSH = 0

02B:
  EXISTING_RISK_BASELINE_PATH  = scripts/run_ml_baseline_v0.py(수동) · 「ML 실험」 화면 버튼 → POST /ml/jobs/evidence-refresh →
                                 app/ml_job_runner.py → app/ml_baseline_v0.build_baseline_report → app/ml_baseline_targets.build_risk_targets
                                 + app/ml_baseline_risk.evaluate_risk_baseline → state/ml/ml_baseline_v0_report_latest.json · cron 없음
  CLASSIFICATION_UNIT          = 시장일 (날짜마다 점수 1개 · 종목 차원 없음)
  EXISTING_FACTORS             = 시장 축 13개 순위 합성 점수 — KODEX200·ETF universe 종가·거래량·NAV 괴리 · KOSPI·VIX·수급 미사용
  EVENT_LABEL                  = 확정: 분배 중립 계열(KRX_BASEPRICE_CHAIN) future_market_drawdown_10d ≤ −5% · 간격 ≤ 9 병합 (§4)
  HORIZON / THRESHOLD          = 확정: label horizon 10거래일 · 낙폭 −5% · 경보 = t 이전 점수 66.67 분위(시점 기준 · §4 · §6) —
                                 기존 risk_baseline 은 수익률 3/5/10 · 낙폭 5/10 · 하락 비율 5일 · 고정 threshold 없음(전체 기간 3분위 · §2-3)
  EVENT_COUNT                  = PLAN 조사(무조정 · 간격 ≤ h) 36개 — 확정 계약 값은 결과서에 새로 계산(판정 §4)
  REACTIVE_BASELINE            = drawdown_20d_market_proxy 시점 기준 percentile · EARLY 와 같은 경보 규칙(과거 점수 66.67 분위 · §6)
  LEAD_TIME_MEASUREMENT        = 사건 시작 = 실현 고점일 P · 선행일 = P − [P−10, T] 안 첫 경보일(거래일) · 대표값 = 포착 사건 전체의 중앙값 (§5)
  FALSE_ALARM_MEASUREMENT      = W = 10 · 평가 사건 창 [P−10, T] 와도, 제외 사건 창(사전 창 없음 [P−10, T] · 잘림 [F−10, 구간 끝])과도
                                 겹치지 않는 경보 run = false-alarm run (제외 사건 창과만 겹치면 EXCLUDED · 세지 않음) · 경보 100건당 수 (§5)
  EXPECTED_STORAGE / RUNTIME   = 읽기 전용 시제품 실측 — 축에 필요한 값만 계산하면 1회 약 15~23초(봉인 전후 검증 포함 시 23초) ·
                                 종목별 feature 행 전체를 만들면 약 2분 · 최대 메모리 약 0.94 GB · 결과 5 MB 미만(추정) · 결정성 2회 (§11)

COMMON:
  KS10_TRIGGER / NEAR          = TRIGGER 0 · NEAR 7 (02A PLAN §2-14) · risk baseline 생산 경로 모듈(ml_baseline_v0 199 ·
                                 ml_baseline_targets 352 · ml_baseline_risk 390 · ml_feature_builder 455 · ml_feature_primitives 124 ·
                                 ml_job_runner 557 · ml_baseline_evidence 452)은 전부 600 미만 · 소비처 app/draft.py(602)는 NEAR 7 중
                                 하나지만 02B 는 고치지 않는다
  EXTERNAL_CALLS = 0 · NEW_DEPENDENCY = 0 · IMPLEMENTATION = AUTHORIZED (문서 동기화 뒤 · 공용 reader 먼저)
  OCI_PUSH_CHANGE              = 0 — 조건: 기존 보고서를 쓰는 두 입구(수동 스크립트 · 화면 작업)를 02B 가 쓰지 않는다(§3)
  설계 §13 금지 범위           = 위 항목 외에 화면·API 추가 0 · PARAM 승격 0 · 자동 튜닝 0 (RF·XGBoost·LightGBM·새 factor 없음 — §6)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성일**: 2026-09-24
- **입력**: 설계서 Part B·C (§7~§15 · §19~§21)
- **공통 사실**: 봉인 source 사실(테이블·봉인·날짜·종가 품질·069500·ticker 재사용)은 `docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md`
  §1 을 그대로 참조한다(복사하지 않는다). 조사 방법·DB 무결성도 같은 문서 머리말과 같다.
- 이 PLAN 은 **신호의 성과를 하나도 보지 않았다** — 사건 수·깊이 같은 label 쪽 사실만 쟀다(설계 §9 "결과를 본 뒤 조정 금지").

---

## 1. 02B 전용 source 사실 (봉인 v1)

- 069500 분배락일(42일 · 크기)은 02A PLAN §1-4 참조. 02B 전용: `FLUC_RT = CMPPREVDD_PRC / (종가 − CMPPREVDD_PRC) × 100` 이
  069500 3,122일 전부 성립 → **같은 source 안에서** 분배 중립 연결 계열
  (`KRX_BASEPRICE_CHAIN`)을 만들 수 있다. 다른 ETF 의 같은 성립 여부는 구현 전에 확인한다.
- `OBJ_STKPRC_IDX`(069500 은 KOSPI200 지수)가 3,122일 전부 양수. KOSPI 종합지수는 KOSPI 추종 ETF 의 `OBJ_STKPRC_IDX` 로만
  간접적으로 있고 2015-08-24 이후만 있다 — 기존 합성 점수는 KOSPI 를 쓰지 않으므로 영향 없음.
- 거래량(`ACC_TRDVOL`)·NAV 가 모든 v1 행에 있다(거래량 0 행 수는 02A PLAN §1-4 · NAV 는 v1 1,612,728행 전부 양수). 운영 DB 에서는
  거의 비어 있던 축 3개의 입력이 전 기간 있다 — 단 두 거래량 축(`down_day_volume_ratio`·`large_negative_day_proxy`)은 정의상
  KODEX200 하락일(3,018일 중 약 1,364~1,373일)에만 값이 생기고, 전 기간 차는 것은 `nav_discount_abs_avg` 뿐이다(§2-2).

---

## 2. 기존 risk_baseline 사실조사 (설계 §8 의 8개 항목)

### 2-1. 호출 경로 · 현재 산출물 (항목 6)

```text
생산     build_baseline_report() → build_risk_targets → evaluate_risk_baseline → state/ml/ml_baseline_v0_report_latest.json
실행     (1) scripts/run_ml_baseline_v0.py 수동 (2) 화면 「ML 실험」 → POST /ml/jobs/evidence-refresh → app/ml_job_runner.py
         (feature 60일 lookback upsert → sanity → baseline) · cron 없음 · OCI 배포 스크립트에 ML 항목 없음
소비     GET /ml/baseline-v0/latest(화면 카드) · evidence snapshot → app/draft.py(보유 draft 문구) · 시장 브리핑 '위험 참고 데이터'
         (10일 낙폭 · app/draft_three_push.py:299-301) · push_context_market 위험 패턴 관찰 · three_push 패키지
         (app/three_push_package_exporter.py:55 시장 브리핑 → draft_three_push.py:299-301 · :73 보유 브리핑 → app/draft.py:206 ·
         :107 급등락 패키지는 ML JSON 을 읽지 않는다) · AI 세션 탭 → 판단 세션 저장(app/api_decision_sessions.py:84·168 →
         app/decision_evidence_store.py:59 ml_baseline_evidence_snapshot_json) — 모두 JSON 을 읽기만 한다.
         threshold·알림으로 쓰는 곳 없음
현재 값   생성 2026-08-30 (화면 작업) · feature 2014-05-12 ~ 2026-08-27(3,018일) · 평가 2014-05-12 ~ 2026-07-29(2,998일)
         drawdown_capture_rate 5d 1.2300 · 10d 1.1865 · high_minus_low_return 3/5/10d −0.25%p / −0.34%p / −0.55%p
         high/low_risk_group_future_down_ratio_5d 0.4532 / 0.4427 · future_drawdown high 5d −2.24% 10d −3.56% / low −1.54% −2.72%
         evidence snapshot 은 지금 'stale'(feature 끝 2026-08-27 이 7일 넘게 지났다)
```

### 2-2. 분류 단위 · factor (항목 1 · 2)

- **시장일** — `market_risk_feature_daily`(asof PK · 종목 없음). 날짜마다 합성 점수 1개, 날짜를 고·저위험으로 나눈다.
- 합성 = 축 13개 각각을 **전체 기간 날짜 순위**로 바꾼 뒤 −(있는 축 순위의 평균) · 축이 3개 이상일 때만. 클수록 위험.

```text
클수록 위험  volatility_20d_market_proxy · volatility_expansion_20d · down_day_volume_ratio · nav_discount_abs_avg ·
            etf_universe_down_ratio · large_negative_day_proxy · short_term_weakness_proxy · breadth_deterioration_proxy
작을수록 위험 kodex200_return_5d · kodex200_return_20d · etf_universe_median_return_5d · distance_from_20d_high · drawdown_20d_market_proxy
입력        KODEX200 종가·거래량 · ETF universe 종가(universe = 현재 etf_master) · NAV 괴리 · KOSPI·VIX·수급 없음
```

**측정된 특이점** — 운영 표 재현(감사)은 결함 그대로 둔다. 주 평가 EARLY 는 아래 첫째(중복 축) · 둘째(방향) · 넷째(정규화)를 교정한다(확정 B3 · §6)

- `drawdown_20d_market_proxy` 와 `distance_from_20d_high` 는 같은 함수다(3,018일 전부 같은 값) → 낙폭이 두 번 들어간다.
- `short_term_weakness_proxy` 는 3일 연속 하락이면 음수 합, 아니면 0 인데 "클수록 위험" 으로 선언돼 방향이 **반대**다 — 연속 하락
  끝 288일이 가장 안전한 순위를 받고, 0 인 2,730일은 날짜 순서대로 순위가 매겨진다.
- 운영 DB 에서 거래량·NAV 축 3개는 거의 비어 있다(48 · 48 · 50일) → 2,942일은 실제로 축 10개로 계산된다.
- 축 순위를 축별 '값 있는 날 수' 로 정규화하지 않는다(`app/ml_baseline_risk.py:94-105` — 축마다 1..그 축의 값 있는 날 수 순위를
  그대로 평균). 값 있는 날이 적은 축이 있는 날은 합성 점수가 위험 쪽으로 밀린다 — 운영 DB 평가일 중 해당 56일 전부 밀렸다(순위
  +42.5 ~ +458.6 · 중앙 +137.7). 3분위 소속이 바뀐 날은 4일(중→고 1 · 저→중 3)이다. 두 거래량 축은 정의상 KODEX200 하락일에만 값이
  있어(`app/ml_feature_builder.py:379-391`) KRX 로 다시 계산해도 하락일(약 1,364~1,373일)만 차므로, 이 효과는 KRX 에서도 사라지지
  않고 모든 하락일에 걸린다.

### 2-3. threshold (항목 3)

**고정 threshold 없음.** 날짜를 합성 점수로 정렬해 상위 k = max(1, int(n/3)) 일을 HIGH, 하위 k 일을 LOW 로 나눈다(현재 n 2,998 ·
k 999 → 사실상 1/3 경보 빈도). 순위와 3분위 모두 **전체 기간**으로 정해서 각 날짜 뒤의 정보가 섞인다 — 시점 기준(point-in-time)이
아니다. walk-forward·purge·embargo 없음. 모듈·테스트가 "위험 threshold" 를 명시적으로 금지한다.

### 2-4·5. horizon · 하락 label (항목 4 · 5)

```text
future_kodex200_return_hd     (close[t+h] − close[t]) / close[t]      h = 3 · 5 · 10
future_market_drawdown_hd     t 종가에서 시작한 running peak 대비 t+1..t+h 최악 하락(≤ 0)   h = 5 · 10
future_universe_down_ratio_5d t+1..t+5 의 '1일 수익률 < 0 인 ETF 비율' 평균 (universe = 현재 etf_master)
꼬리 제외                      마지막 20일 (MAX_HORIZON = 20 — 후보 baseline 기준)
```

모두 **연속값**이다 — 이진 "하락 사건" label 이 없다. 보고서의 `drawdown_capture_rate` 는 **고위험군 평균 낙폭 / 전체 평균 낙폭**
(평균의 비, 1 보다 크면 고위험군이 더 깊다)이지 사건 포착률(recall)이 아니다. 문장으로 쓰는 소비처(draft 근거 줄 · 시장 브리핑 ·
위험 패턴)는 10일 값만 쓴다. evidence snapshot 자체는 5d·10d 낙폭·capture 를 함께 담아 API·판단 세션·runtime package 로 넘기지만
5d 값을 읽는 코드는 없다. 「ML 실험」 화면 카드는 보고서 전체(수익률 3/5/10d · 낙폭 5/10d · 하락 비율 5d)를 보여 준다.

### 2-6. 재현 가능 여부 (항목 7)

**그대로 재현된다.** 입력은 라이브 시장 DB 의 두 표(`market_risk_feature_daily` · `etf_ml_feature_daily` 069500)다. (a) 독립
재구현이 비교한 11개 지표 전부 차이 0.0 · (b) 저장소 함수를 수정 없이(연결만 읽기 전용으로) 불러 모든 키가 비트 단위로 같다
(PYTHONHASHSEED 5종 · 저장소 .venv Python 3.12 기준 — `_avg_target`·`_avg` 가 set 을 순회해 합산하므로 시드에 따라 합산 순서가
바뀌고, 비트 일치는 3.12 의 보정 합산 덕분이다. Python 3.9 에서는 9개 키가 시드마다 마지막 비트에서 달라진다 → 02B 결정성 2회 검사는
같은 3.12 런타임에서 돌린다) · 라이브 DB sha256 전후 동일. 단 feature 표는 물질화된 값이다 — 오늘 원가격으로 다시 만들면 2026년 일부
날짜의 universe 축이 달라진다(원가격·etf_master 가 그 뒤 바뀌었다). 즉 **저장된 표로는 정확히 재현, 새로 만들면 조금 다르다.**

### 2-7. KRX 봉인 데이터만으로 다시 계산 (항목 8)

**가능하다 — 필요한 입력(069500 종가·거래량 · universe 종가 · NAV)이 봉인 v1 에 전부 있다.** 그러나 숫자는 현재 보고서와 다르다:

```text
가격 기준     운영 KODEX200 은 분배 조정(2014-04-09 20,843 대 KRX 26,280 · 겹치는 3,055일 중 2,965일 다름) · KRX 는 무조정
universe      운영 축·하락 비율 label 은 현재 etf_master(생존자) · KRX 는 날짜별 실재 universe(PIT)
거래량·NAV    운영은 거의 비어 대부분 축 10개 · KRX 는 NAV 축이 전 기간 · 거래량 축 2개가 하락일마다 차서 실제 합성 구성이 달라진다
NAV 괴리 정의 운영: 네이버 ETF 목록(naver_etf_item_list) 수집 시점의 현재가(nowVal)·NAV 로 계산한 (가격−NAV)/NAV×100 ·
              스냅샷은 2026-06-17 이후 10일뿐 · 기준일 이하 최신 스냅샷 이월(기한 없음) · KRX: 같은 날 (TDD_CLSPRC − NAV)/NAV
```

기존 공개 함수는 `db_path` 의 두 표 이름을 전제한다 — KRX 로 돌리려면 그 스키마의 **파생 연구 DB** 를 실행 폴더에 만들거나 새 모듈이
필요하다(운영 모듈 수정 없이). 축을 만드는 `build_features`(`app/ml_feature_builder.py:236`)는 봉인 DB 에 쓸 수 없다 —
`market_data_store` 의 `fetch_price_volume_history`·`list_etf_tickers`·`get_etf_name_map` 가 읽기쓰기 연결을 열고, 프로세스·경로당
첫 연결에서 폴더 생성·`CREATE TABLE IF NOT EXISTS`(6개)·commit 을, 이후 연결마다 commit 을 하고(`_connection` :200-208), KOSPI(`market_benchmark_store`, :171)와 `NavLookup`(:272 · `etf_nav_daily` 괴리율 이월)도 읽는다. → KRX 축은 02B 새 모듈에서
기존 축 정의를 그대로 옮겨 계산한다(§9 `app/ml_ew_market_axes.py`). 그래서 KRX 합성 점수는 계약은 같아도 숫자는 운영 보고서와 다르다 — 운영 숫자 재현은 감사 단계에서만 한다(확정 B11 · §3).

### 2-8. 코드·문서 불일치

`capture` 주석은 "worst drawdown 의 몇 %" 라고 하지만 코드는 평균의 비다 · 문서들은 옛 40일 실행 숫자(10d −8.09% 대 −3.40% ·
capture 1.72/1.44)를 인용하고 현재 보고서는 2,998일(−3.56% 대 −2.72% · 1.23/1.19)이다 · "13축" 중 둘은 같은 축이다.

---

## 3. 신호 구성 (확정 · 설계자 판정 §5 · §10)

```text
LEGACY_REPRODUCTION  감사용 · 결과 입력 아님 — 운영 표 2개를 읽기 전용 세션 사본으로 재현(아래)
EARLY_WARNING        주 평가 — KRX 봉인 · 시점 기준 교정 합성(§6)
REACTIVE_BASELINE    주 평가 — drawdown_20d_market_proxy 의 시점 기준 percentile(§6)
진단(판정 미사용)     LEGACY_FULL_SAMPLE_DIAGNOSTIC · EXACT_K_DIAGNOSTIC — LOOKAHEAD=true (§6)
```

**운영 표 재현(B11 · 판정 §10)** — 라이브 DB 에 직접 연결하지 않는다.

1. 라이브 `state/market/market_data.sqlite` 파일을 실행 폴더로 복사(POC4-01 `READONLY_SESSION_COPY` 방식): 복사 전후 라이브
   sha256 이 같고 · 사본 sha256 이 그와 같고 · 사본 `PRAGMA integrity_check = ok` 여야 한다. 사본은 0444.
2. `guard_sqlite_paths([사본])` 안에서 기존 `build_risk_targets` · `evaluate_risk_baseline` 을 수정 없이 사본 경로로 부른다.
3. 결과를 저장 보고서 `state/ml/ml_baseline_v0_report_latest.json` 의 `risk_baseline` 과 모든 키 비교 → `EXACT_MATCH` 여부 기록.
4. 사본 hash 를 다시 재고(바뀌면 실패) 사본을 지운다. 이후 KRX 평가에는 쓰지 않는다.
5. **쓰지 않는 입구**: `scripts/run_ml_baseline_v0.py`(`--no-snapshot` 없이 돌리면 보고서를 덮어씀 · :81-84) · 「ML 실험」 화면
   작업(`app/ml_job_runner.py` — 보고서 쓰기 :392-398 · 라이브 feature 표 upsert :305-306). 보고서·feature 표 쓰기 0 ·
   실행 전후 라이브 5경로(conftest 감시 목록) 동일.

---

## 4. 하락 사건 label (확정 B1·B4·B6 · 아래 후보표는 PLAN 조사 시점 값)

```text
EVENT_LABEL     = future_market_drawdown_10d <= -5%      (069500 · 기존 _kodex_future_drawdown 산식)
PRICE_BASIS     = KRX_BASEPRICE_CHAIN                    (FLUC_RT 기반 분배 중립 계열 · 02A PLAN §4 와 같은 식)
EVENT_GROUPING  = label 날짜 간격 <= 9거래일일 때 병합     (간격이 정확히 10 이면 다른 사건)
EVENT_START     = 실현 고점일 P
PRE_WINDOW      = P 이전 10거래일
```

사건 수는 이 계약으로 다시 계산해 결과서에 적는다(36 과 달라도 정의 정정 — 판정 §4). 아래 §4-1~§4-5 는 PLAN 조사 때(무조정
종가 · R2 간격 ≤ h) 잰 사실이다.

### 4-1. 구조

- 단위 = 시장일(기존 계약). label 일 = `future_market_drawdown_hd ≤ −k` 인 날(경계 포함).
- **구조적 사실(측정)**: 낙폭 label 은 첫 label 일 F 가 실현 돌파일 B(고점 대비 −k 에 처음 닿은 날)보다 **정확히 h 거래일 앞**이다
  (dd5 5/5/5 · dd10 10/10/10 · 모든 threshold·가격 기준). 그래서 사건 시작을 F 가 아니라 실현 고점일 P 로 둔다(B5).
  실현 고점은 F 뒤 중앙 1~2일(최대 34일). **확정 계열 실행에서** 사건 34·35 는 T 가 F 다음 날로 잡혀(깊이 −1.06% · −0.82% · B 없음)
  이 서술과 다르다 — 결과서 §5-1. 설계자 RESULT 판정(2026-09-25): 재실행 없음 · 이 사건 정의는 이번 연구 뒤 폐기
  (`EVENT_DEFINITION_STATUS = RETIRED_AFTER_THIS_STUDY`) — 향후 Track B 는 새 PLAN·새 사전 등록으로만.
- 간격 기준 하나로 사건 수가 바뀐다: dd10 ≤ −5% 에서 간격 ≤ h 면 36개 · ≤ h−1 이면 37개(차이는 간격이 정확히 10 인 쌍 하나 —
  2020-01-23 · 2020-02-10). 확정은 ≤ h−1(= 9).

### 4-2. 후보별 사건 수 (PLAN 조사 · KRX 무조정 종가 · 2014-01-02 ~ 2026-09-21 · 약 12.7년)

```text
label ≤ −k        label 일(비율)       R1 사건   R2 사건(간격 ≤ h · 연)
dd10 ≤ −5%        440 (14.14%)          44        36 (2.83)    ← 확정 label (계열·병합 규칙은 위 확정값)
dd10 ≤ −7%        228 (7.33%)           27        23 (1.81)
dd10 ≤ −10%        96 (3.08%)           11         7 (0.55)
dd5  ≤ −5%        188 (6.03%)           38        33 (2.59)
dd5  ≤ −7%         85 (2.73%)           16        13 (1.02)
dd5  ≤ −10%        47 (1.51%)            9         6 (0.47)
```

### 4-3. 사건 깊이 · 연도 분포 (PLAN 조사 · dd10 ≤ −5% · R2 36개)

- 실현 깊이(첫 label 일 고점 대비 최악): 최소 −40.93% · p10 −15.24% · p25 −10.00% · 중앙 −8.28% · p75 −6.37% · 최대 −5.01%.
- 연도별 R2 사건(첫 label 일 F 의 연도 기준): 2014 1 · 2015 4 · 2016 0 · 2017 0 · 2018 3 · 2019 2 · 2020 4 · 2021 4 · 2022 4 ·
  2023 4 · 2024 5 · 2025 3 · 2026 2. P_j 의 연도 기준으로는 2023 3 · 2024 6(F 2023-12-22 사건의 P = 2024-01-02).
- **2026년 쏠림**: label 일의 28.4%(125/440)가 2026년(거래일 177 중 dd10 계산 가능 167일)에 있다. 2026-03-04 −12.46% ·
  06-23 −10.47% · 07-28 −11.19% · 07-31 +24.17% 같은 큰 일간 변동이 KRX 종가·지수·스냅샷 모두에 있다(데이터 그대로).
- **오른쪽이 잘린 사건**: 2026 의 긴 사건(2026-04-29 ~ 09-07)은 dd10 을 계산할 수 있는 마지막 날에 끝난다 → `RIGHT_CENSORED_EVENT`(B12).

### 4-4. 가격 기준에 따른 차이 (PLAN 조사)

- 공통 구간(2014-05-12 ~ 2026-07-29 · 2,998일)에서 dd10 ≤ −5% 사건 R2: KRX 무조정 36 · KRX 연결 계열 35 · KOSPI200 지수 35 ·
  스냅샷 35 · 라이브 운영 35 — **KRX 연결 계열은 조정 가격과 거의 같다.**
- 무조정 종가는 label 일을 **늘리기만** 한다(연결 계열에만 있는 label 일 0) — 분배락 하락이 경계 근처 사건 1~2개를 만든다
  (dd10 ≤ −5% 2015-04-22~23 · ≤ −7% 2021-01 · 2023-10). 확정(B4)은 연결 계열이라 이 가짜 사건이 빠진다.

### 4-5. universe 에 따라 달라지는 것

KODEX200 낙폭 label 과 사건은 universe 와 무관하다. universe 에 따라 달라지는 것은 universe 축 4개(하락 비율 · universe 5일 중앙
수익률 · breadth · NAV 괴리 평균)뿐이다. PLAN 조사의 하락 비율 label 차이(PIT − 최종 생존): 평균 −0.0024 · |차이| 중앙 0.0049 ·
최대 0.0404 · 대체로 줄어든다(공통 구간 연평균 |차이| 2014 0.0105 → 2026 0.0009 · 2015·2017·2019·2023·2024 는 전년보다 큼).
universe 축 4개의 두 universe 차이는 결과서에 신호 성과보다 먼저 적는다.

---

## 5. 측정 정의 (확정 B5~B7·B12 + 구현 정의 — 결과 전 고정)

```text
K       069500 연결 계열(KRX_BASEPRICE_CHAIN)
dd10(t) t+1..t+10 에서 K_t 를 시작 고점으로 한 running peak 대비 최악 하락 (기존 _kodex_future_drawdown 과 같은 식)
L       label 일 = dd10(t) ≤ −0.05 (t+10 이 있는 날만 계산)
E_j     label 일을 날짜 순으로 놓고 앞 label 일과 간격 ≤ 9거래일이면 같은 사건 · F_j 첫 label 일 · Last_j 마지막 label 일
T_j     [F_j, Last_j+10] 에서 K 가 가장 낮은 날(같으면 이른 날)     — 저점
P_j     [F_j, T_j] 에서 K 가 가장 높은 날(같으면 이른 날)            — 실현 고점 = 사건 시작
depth_j K_T / K_P − 1 · B_j = [P_j, T_j] 에서 처음 K ≤ 0.95·K_P 인 날(참고표)
RIGHT_CENSORED_EVENT   Last_j + 9 가 label 계산 가능 마지막 날 뒤 → 사건이 이어질 수 있다 → 주 판정 전부 제외 · 설명표에만
PRE_WINDOW_UNAVAILABLE P_j − 10 이 경보 평가 시작일 D_0 앞 → 사전 창을 볼 수 없다 → 주 판정 제외 · 설명표에만
평가 사건              위 두 경우가 아닌 사건
A       경보일 · 경보 평가 구간 = [D_0, label 계산 가능 마지막 날] (D_0 = EARLY·REACTIVE 경보 판정이 모두 가능한 첫날)
사전 포착              [P−10, P−1] 에 경보
시작 후에만 포착        사전 경보 없이 [P, T] 에만 경보
완전 미포착             [P−10, T] 에 경보 없음
선행일                 P − ([P−10, T] 안 첫 경보일) (거래일 · 양수 = 먼저 · 시작 후 포착은 ≤ 0) · 대표값 = 포착 사건 전체의 중앙값
사전 포착 비율          사전 포착 / (사전 + 시작 후)
severe                 평가 사건 깊이의 25% 분위(선형보간) 이하 사건(B7) · severe 완전 미포착 수
경보 run               경보 평가 구간에서 연속 경보일 묶음
  TRUE run             평가 사건의 창 [P−10, T] 와 겹친다
  EXCLUDED run         평가 사건 창과는 안 겹치고 제외 사건의 창과만 겹친다 — 세지 않음. 제외 사건 창: 사전 창 없음 = [P−10, T] ·
                       잘림 = 관측 구간 전체 [F−10, 구간 끝] (판정 §8 "precision 에서 전부 제외" — 구현 검토에서 이 PLAN 의
                       처음 문구 [P−10, 구간 끝] 이 판정보다 좁은 것을 발견해 판정 문구에 맞췄다 · **스모크 결과를 본 뒤 수정** ·
                       조건 1~7 참·거짓 불변 — 결과서 §4 지시문 외 변경 1 · 설계자 RESULT 판정 §2 승인)
  FALSE run            어느 창과도 안 겹친다
run precision          TRUE / (TRUE + FALSE)
경보 100건당 false-alarm run  FALSE / (TRUE·FALSE run 에 든 경보일 수) × 100
보조 표                일 단위 precision · false alarm day · 경보 수·비율 · 연도별 · 사건별 표 · B 기준 선행일
```

**RANDOM_NULL (판정 §6)** — EARLY 경보열을 달력 연도별로 나눠, 그해 경보 평가 구간의 경보 0/1 열을 [0, 그해 날수) 에서 뽑은
오프셋만큼 원형 이동한다. 그해 run 길이 구성(개수·길이)이 원래와 같은 오프셋만 받는다(최대 1,000번 다시 뽑고 · 없으면 이동 0 ·
연도 경계를 넘는 run 은 연도별로 잘라 센다). `REPEATS = 1,000` · `SEED = 20260925`(`random.Random`) · 매 반복의 run precision
분포의 95% 분위(선형보간)를 기준으로 쓴다.

---

## 6. 신호 계산 (확정 B2·B3·B9·B10·B13 + 구현 정의)

**축(KRX · 날짜 t · 기존 `app/ml_feature_builder.py` 정의를 그대로 옮김 — 가격은 연결 계열, 단위 %)**

```text
069500 축        kodex200_return_5d · kodex200_return_20d · volatility_20d_market_proxy(20일 일간 수익률 표준편차) ·
                 drawdown_20d_market_proxy(K_t / max K_{t−19..t} − 1) · volatility_expansion_20d(5일 / 20일 표준편차) ·
                 down_day_volume_ratio(하락일에만 · 거래량 / 20일 양수 거래량 평균) · large_negative_day_proxy(하락일에만 ·
                 |일간 %| × 거래량비) · short_term_weakness_proxy(최근 3일 모두 음수면 합 · 아니면 0)
universe 축      etf_universe_down_ratio · breadth_deterioration_proxy(down − up 비율) · etf_universe_median_return_5d ·
                 nav_discount_abs_avg(같은 날 |(TDD_CLSPRC − NAV) / NAV| × 100 평균) — universe 는 t 에 행이 있고 t−1 행도 있는 ETF
                 (069500 포함 · 기존 builder 와 같음)
universe 변형    PIT(주) = t 에 행이 있는 ETF · FS = 그중 2026-09-21 에도 행이 있는 ETF — 둘 다 t 행 ISU_NM 으로 인버스·레버리지·
                 2X·2배·합성·선물 제외(B10). 전 종목(필터 없음)은 legacy 진단에만
```

**EARLY_WARNING (B3 교정 · 새 factor 0)** — 축 12개(`distance_from_20d_high` 는 `drawdown_20d_market_proxy` 와 같은 함수라 뺀다).
위험 방향: 클수록 위험 = 변동성 · 변동성 확대 · 하락일 거래량비 · NAV 괴리 · 하락 비율 · 큰 하락일 · breadth 악화 / 작을수록 위험 =
5일·20일 수익률 · universe 5일 중앙 수익률 · 20일 낙폭 · `short_term_weakness_proxy`(교정 — 음수 합이 작을수록 위험).
정규화: 축마다 t **이전** 날짜의 값(결측 제외)이 60개 이상일 때만 `위험 percentile = (현재보다 덜 위험한 과거값 수 + 0.5 × 같은
값 수) / 과거값 수` (0~1). 결측·이력 부족 축은 빼고 평균 · 축 3개 이상일 때만 점수.

**REACTIVE_BASELINE** — `drawdown_20d_market_proxy` 하나의 같은 위험 percentile.

**경보(B9 · 주 비교)** — `현재 점수 ≥ t 이전 날짜 점수들의 66.67 percentile`(선형보간 · 과거 점수 60개 이상) · 경계 동점은 경보.
두 신호에 똑같이 적용하고 실제 경보 수·비율을 보고한다. 학습·threshold fit 이 없으므로 purge·embargo 는
`NOT_APPLICABLE_TO_NO_FIT_RULE`(B13).

**진단(판정 미사용 · LOOKAHEAD=true)**
- `EXACT_K_DIAGNOSTIC` (= 판정 §6 `LOOKAHEAD_DIAGNOSTIC_ONLY`) — 경보 평가 구간 전체에서 EARLY·REACTIVE 점수 상위 k = int(구간 일수/3) 일(동점은 이른 날).
- `LEGACY_FULL_SAMPLE_DIAGNOSTIC` — 기존 합성(`app/ml_baseline_risk._compute_composite_scores` 를 수정 없이 호출 · 13축 · 결함
  그대로 · 전 종목 universe)를 전체 기간 순위로 만든 뒤 경보 평가 구간 안 상위 1/3(k = max(1, int(n/3))). "결함이 있는 legacy
  결과" 를 교정 결과와 나란히 적는 용도(판정 §5).

RF·XGBoost·LightGBM·새 factor·결과 뒤 threshold 조정 없음.

---

## 7. PASS / REJECT (확정 · 설계자 판정 §7 + 구현 정의)

주 평가 universe = PIT. 아래 1~7 은 PIT 결과로 판정하고, FS 결과는 나란히 적기만 한다.

```text
1  EARLY 의 포착 사건 전체 선행일 중앙값 > REACTIVE
2  EARLY 의 사전 capture(사전 포착 사건 수) >= REACTIVE
3  EARLY 의 severe 완전 미포착 수 <= REACTIVE
4  포착 사건 중 사전 포착 비율 EARLY > REACTIVE
5  경보 run precision EARLY > REACTIVE
6  경보 100건당 false-alarm run EARLY < REACTIVE
7  EARLY 경보 run precision > RANDOM_NULL 95% 분위
8  PIT universe 에서 1~7 성립 (주 평가가 PIT 이므로 1~7 과 같은 판정 — FS 에서만 성립하는 우위는 PASS 근거가 아니다)
9  2026년을 뺀 평가(P 가 2026 인 사건 · 2026 경보일 제외)에서 핵심 방향 유지
10 평가 사건 하나를 뺄 때마다(그 사건 창은 EXCLUDED) · 평가 사건이 있는 연도 하나를 뺄 때마다(그해 사건·경보일 제외) 핵심 우위 부호 유지
11 처음부터 두 번 실행한 결과 canonical sha256 동일
핵심 = {1 선행일 중앙값 >, 2 사전 capture ≥, 5 run precision >}  (EARLY 대 REACTIVE)
```

- 판정: 11개 모두 참 → `PASS_CANDIDATE`(`TRACK_B_PASS ≠ PUSH_ACTIVATION` — 운영 후보화는 별도 설계). 하나라도 거짓 → `REJECT`.
  거짓은 없고 계산할 수 없는 조건(포착 사건 0 · run 0 등)이 있으면 `INCONCLUSIVE → CLOSED`. 결과를 보고 threshold 를 바꾸는
  재시도는 없다.
- 조건 11 은 두 번째 실행 뒤 비교 단계가 따로 기록한다(결과 canonical 에 넣지 않는다).

---

## 8. 설계자 확정 13건 (2026-09-25) · 구현 정의

| # | 확정 | 반영 위치 |
|---|---|---|
| B1 | 주 사건 label = 분배 중립 계열의 `dd10 ≤ −5%` | §4 |
| B2 | 조기감지 평가는 시점 기준 점수 | §6 |
| B3 | 기존 합성 결함 3개 교정(낙폭 축 중복 · short_term_weakness 방향 · 축별 0~1 과거 percentile 정규화) | §6 EARLY |
| B4 | KRX `FLUC_RT` 기반 분배 중립 계열 | §4 · 02A PLAN §4 식 |
| B5 | 사건 시작 = 실현 고점일 P | §5 |
| B6 | 사전 창 W=10 · label 간격 ≤ h−1(=9) 일 때만 병합 | §4 · §5 |
| B7 | severe = 완결 사건 중 실현 깊이 하위 25% | §5 |
| B8 | 연도·사건 제외 안정성 검사 유지 | §7 조건 9·10 |
| B9 | 시점 기준 누적 분위가 주 비교 · 전체 기간 exact-k 는 참고만 | §6 경보 · 진단 |
| B10 | universe 축은 날짜별 이름으로 인버스·레버리지·합성·선물 제외 | §6 universe 변형 |
| B11 | 운영 표 재현은 읽기 전용 동결 사본 진단 단계로만 | §3 |
| B12 | 오른쪽이 잘린 사건은 주 판정 제외 | §5 |
| B13 | 학습 없는 시점 기준 규칙에는 purge·embargo 비적용 | §6 |

**구현 정의** — 판정이 정하지 않은 세부를 결과를 보기 전에 여기서 고정한다(결과를 본 뒤 바꾸지 않는다).

1. 사건 T·P 의 정의(§5 표) · 잘림 판정 = `Last + 9 > label 계산 가능 마지막 날` · 사전 창이 경보 시작 전인 사건은
   `PRE_WINDOW_UNAVAILABLE` 로 주 판정 제외(판정에 없던 경우 — 사전 창을 볼 수 없는 사건을 미포착으로 세지 않기 위해).
2. 축 정규화의 최소 과거값 60개 · 과거 = t 미만(t 제외) · 같은 값은 0.5 로 센다. 경보 threshold 도 과거 점수 60개 이상.
3. run 분류 TRUE · EXCLUDED · FALSE (§5) · 경보 100건당 false-alarm run 의 분모 = 센 run 에 든 경보일 수.
4. RANDOM_NULL 의 연도별 원형 이동 · run 구성 보존 확인 · seed 20260925 (§5).
5. 핵심 우위 = 조건 1·2·5. 조건 9·10 의 변형마다 이 셋이 모두 성립해야 한다.
6. universe 는 t 와 t−1 에 행이 있는 ETF(기존 builder 의 "idx < 1 이면 건너뜀" 과 같음) · 069500 포함.
7. 주 평가 universe = PIT · 조건 8 은 PIT 판정 그대로 · FS 는 기록만.
8. 판정 규칙: 거짓 하나라도 → REJECT · 거짓 없이 계산 불가 조건 → INCONCLUSIVE → CLOSED.

---

## 9. 파일 계획 · 테스트

**신규**(각각 600줄 미만 · 운영 모듈·고정 모듈·기준선 파일 수정 0 · 봉인 KRX 는 공용 `app/krx_sealed_reader.py` 를 수정 없이 import)

```text
app/ml_ew_reproduce.py         운영 표 재현(감사) — 세션 사본 · 검증 · 기존 함수 호출 · 저장 보고서 비교 · 사본 삭제
app/ml_ew_market_axes.py       KRX 봉인 → 시장일 축 13개(기존 정의 그대로) · PIT / FS / 전 종목 universe
app/ml_ew_signals.py           시점 기준 percentile 정규화 · EARLY(교정) · REACTIVE · legacy 진단 · 경보 규칙 · exact-k 진단
app/ml_ew_events.py            dd10 label · 사건 묶음 · P/T/B · 잘림 · 사전 포착·선행일·run·precision·severe · RANDOM_NULL
app/ml_ew_report.py            판정 1~10 · 2026 제외 · leave-one-event/year-out · 표 · canonical hash
scripts/run_poc4_02b_early_warning.py  러너 — 새 폴더 · 봉인 전후 검증 · 라이브 5경로 전후 · progress/ · --resume · 두 실행 비교
```

**테스트**(tmp 고정 DB · 봉인 DB·라이브 DB 는 테스트 가드가 거부하므로 열지 않는다 · 새 테스트는 허용 목록에 없음) — 설계 §15 공통
항목 + 02B 전용: 점수가 t 이후 정보를 쓰지 않음(미래 날짜 값을 바꿔도 t 점수·경보 불변) · 정규화 60개 미만이면 결측 · 경계 동점은
경보 · 교정 3건(중복 축 제거 · 방향 · 정규화) · 사건 묶음(간격 9 는 병합 · 10 은 분리) · P/T/B · 잘림·사전 창 없음 제외 · 사전 포착·
시작 후·미포착 분류 · run TRUE/EXCLUDED/FALSE · RANDOM_NULL 이 run 구성을 보존하고 seed 로 재현됨 · 판정 규칙(REJECT/INCONCLUSIVE) ·
운영 표 재현이 차이를 잡음(tmp 사본) · `state/ml/ml_baseline_v0_report_latest.json`·라이브 feature 표에 쓰지 않음 · 재개는 지문이
같을 때만 · 끊은 뒤 재개한 결과 = 끊지 않은 결과 · 두 번 실행 동일 · 외부 네트워크 0.

---

## 10. 중단 조건 점검 (설계 §20 · 판정 반영 후)

```text
봉인 KRX 만으로 가격·label 생성 불가                 아니다 — 연결 계열·축·label 모두 봉인 version
현재 etf_master·운영 가격 DB 필요                     아니다 — 운영 표 2개 읽기는 판정 §10 에 따라 감사용 세션 사본으로만(중단 조건 아님)
KODEX200 을 다른 source 에서                         아니다
risk baseline factor·threshold·label 재현 불가         아니다 — 운영 표 재현 차이 0.0(PLAN 조사) · 이진 사건·threshold 는 확정 계약
결과 전 Track B 성공 기준 고정 불가                   아니다 — 판정 §7 11개 조건 + §8 구현 정의로 결과 전 고정
추가 네트워크·신규 의존성                             아니다
기존 기준선 수정                                     아니다 — 기존 파일 무수정 · EARLY 는 결함 교정본(판정 §5 — 같은 factor 집합)
KS-10 trigger                                       아니다
라이브 DB·상태 파일 변경                              아니다 — 세션 사본 · 결과는 새 폴더 · 보고서 쓰는 두 입구 사용 금지 · 라이브 5경로 전후 동일
두 PLAN 이 같은 운영 모듈을 동시에 수정               아니다
```

## 11. 작업 리듬 · 재개

순서(판정 §12): 공용 reader 먼저 → 02B 구현·테스트 → 전체 회귀 → 실행 1 → 실행 2(결정성) → 두 실행 비교 → 결과서
`docs/ai_result/POC4/POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md`. 02A 장시간 실행과 동시에 돌리지 않는다. 설계자는 02B 결과를
먼저 판정한다.

실행시간(PLAN 조사 뒤 읽기 전용 시제품): 축에 필요한 값만 계산하면 1회 약 15~23초 · 최대 메모리 약 0.94 GB. 설계 §21 에 따라
러너는 02A 와 같은 재개 구조를 둔다 — 단계(재현 · 축 · 신호 · 사건 · 무작위 기준 · 판정)마다 결과를 실행 폴더 안 `progress/` 에
한 번씩만 쓰고, 입력 지문(봉인 content·파일 hash · 운영 DB 파일·저장 보고서 sha256 · 모듈 정규화 AST sha256 · 설정 hash · 평가일
목록 hash)이 모두 같을 때만 `--resume` 으로 남은
단계를 잇는다. 결정성 확인은 재개 없이 처음부터 두 번 돈 결과로 한다.
