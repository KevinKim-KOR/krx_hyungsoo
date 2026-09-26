# POC4-03 — RF 대 20일 모멘텀 최종 Kill Gate PLAN V1 (확정)

```text
STEP                        = POC4-03 RF_VS_MOMENTUM_FINAL_KILL_GATE · TRACK A
PLAN_DECISION               = PASS_WITH_MANDATORY_AMENDMENT (설계자 2026-09-25) · 필수 보완 A~D 반영 · Q1~Q17 확정 (§4)
IMPLEMENTATION              = AUTHORIZED — 설계자 재확인은 새 데이터 소스 · RF 설정 변경 · 성과 확인 뒤 기준 변경 · 4시간
                              재초과 때만
COMMIT_PUSH                 = 0 (구현·검증 뒤 별도 지시)
DESIGN                      = docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md (설계자 원문 + PLAN 판정 원문)

사실조사 (설계 §8 · 12항목 · §1):
  1 SKLEARN            = 1.9.0 설치 = requirements.txt:33 `scikit-learn==1.9.0` 일치 · 신규 의존성 0
  2 LINEAR_BASELINE    = 고정 모듈 3개 + 02A 호출 모듈 20개 hash 가 02A run1 기록과 전부 일치 · RF 를 fit 한 같은 프로세스에서
                         02A 선형 기록 재현 4/4 정확 일치(PIT·CONTROL × 2020-06-30·2026-07-31 · smoke 3)
  3 MOMENTUM           = t 행 `return_20d`(클수록 좋음 · Q1 확정) · 결측 행은 점수 없음 · `excess_return_20d` 와 146일 × 2 arm
                         날짜별 순위 상관 1(허용 1e-12)
  4 REUSE_02A          = 146일 · 7 feature · 학습 label · 평가 label · 날짜 분할(purge 20) 모두 그대로
  5 RF_CONFIGS         = 얕음·중간·깊음 3개 동결 · 트리 200 · 표본 25% · seed 42 · 설정 sha256 edca7023… (§1-5)
  6 SELECTION          = 신호일마다 t 이전 검증 구간 V 의 모든 거래일 IC 평균(이름 필터·7 feature 완전·target 있는 행) 최고 설정
                         · finite 원값 비교 · 정확 동률 A→B→C · 전부 None 이면 INVALID_STOP · RF 학습 S 에서 label 끝 ≥ V 시작
                         행 제외 (§1-6 · 필수 보완 A·B)
  7 SMOKE              = 3회 · 성과 지표 0 · seed 42 마지막 날짜(학습 92만 행) RF 3설정 fit 88.3초 · peak RSS 2.62 GB
                         · RF_A 는 t 점수 동점이 크다 → 경계 동점 부분 가중을 모든 성과 산식에 적용 (§1-7 · §2-4 · 필수 보완 D)
  8 OFFICIAL_ESTIMATE  = arm 별 실행 확정 — PIT 1.80시간(부하 ×1.58 이어도 2.85시간) 2회 먼저 → PIT 가 PASS 후보일 때만
                         CONTROL 2회(1.46시간) · perf_counter 4시간 강제 중단 (§1-8 · §2-1 · 필수 보완 C)
  9 FILES              = 신규 app 5 · 러너 1 · 테스트 4 (전부 600줄 미만 계획) · 기존 코드 파일 수정 0 (§3)
 10 KS10               = .py/.ts/.tsx 518개 · 136,182줄 · TRIGGER 0 · NEAR 백엔드 6 · 프론트 1 · 테스트 0
 11 LIVE_SEALED_GUARD  = 02A 방식(라이브 5경로 = 파일 4개 sha256 + `state/runs` 이름 목록 · 봉인 14필드 전후 · guard_failed)
                         + 02A 기준 산출물 hash 대조 + 봉인 밖 DB 열기 차단(`guard_sqlite_paths`)
 12 TESTS              = focused 4파일 · 02A evaluate_point 와 기록 완전 일치 · 전체 회귀 · PIT 처음부터 2회 결정성
                         (CONTROL 은 실행할 때 2회)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자 · **작성일**: 2026-09-25
- **입력**
  - 설계서 `docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md` §1~§9
  - 선행 계약 `docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md` Part D(§16~§18)
  - 02A 확정 계약 `docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md`
- **조사 방법**
  - 에이전트 7개가 영역별로 코드·기록을 읽고 실측했다(읽기 전용).
  - 개발자가 train-only smoke 를 3회 돌렸다. scratchpad 스크립트이고, 봉인 DB 는 `mode=ro&immutable=1` 로만 열었다.
    저장소·`state/` 쓰기는 0 이고, 세 번 모두 전후 봉인이 같았다(`assert_same_source` 통과).
  - smoke 는 **시간·RSS·결정성·점수 동점(label 없음)·선형 재현 참/거짓만** 쟀다. RF·모멘텀의 IC·수익률 같은 성과 값은 test 는
    물론 검증 구간에서도 계산하지 않았다. 설정을 성과로 고르지 않았다는 사전 등록 조건을 지키기 위해서다. 선형은 02A 원본
    `evaluate_point` 로 이미 공개된 02A 기록을 메모리에서 다시 계산해 일치 여부(참/거짓)만 봤고, 값은 출력하지 않았다.
  - PLAN 초안은 검토 에이전트 3개(숫자 대조 · 설계 대응 · 방법론)가 따로 검토했다. 지적은 이 판에 반영했고,
    확인이 필요한 것은 세 번째 smoke 로 다시 쟀다.

---

## 1. 필수 사실조사 (설계 §8)

### 1-1. sklearn 버전 (항목 1)

| 항목 | 실측 |
|---|---|
| 설치 | `scikit-learn 1.9.0` · numpy 2.4.6 · scipy 1.18.0 · joblib 1.5.3 · torch 2.13.0 · Python 3.12.13 |
| requirements.txt | `:33 scikit-learn==1.9.0` · `:38 numpy==2.4.6` 일치 · `:24 torch>=2.6.0`(범위 · 설치 2.13.0 은 02A 기록과 같음) |
| 허용 근거 | `requirements.txt:28-32` · `app/ml_relative_upside_model.py:3-7` 주석 — POC4 연구 경로에서 RF 비교 허용(POC4-00) |
| 저장소 사용 | RF 를 쓰는 코드 0건(`RandomForest` 는 `.py` 주석 1줄뿐) · sklearn 은 Market Flow 계열이 `Ridge`·`StandardScaler` 만 쓴다 |
| 기계 | Apple M1 · 성능 코어 4 + 효율 코어 4 · RAM 16 GiB · CUDA 없음(선형 trainer 는 CPU · 02A 기록 device `cpu` 146/146) |

scipy·joblib 은 requirements.txt 에 고정돼 있지 않다(전이 의존성). 실행 manifest 에 다음을 함께 기록한다.
- 두 패키지 버전 · torch 스레드 수
- `threadpoolctl.threadpool_info()` 요약 · `OMP_*`·`MKL_*` 환경변수. torch 와 sklearn 의 libomp 두 벌이 함께 적재되는 구성이라
  재현 실패를 진단할 때 쓴다. 판정에는 쓰지 않는다.

02A 는 joblib·스레드 정보를 기록하지 않았다.

### 1-2. 선형 baseline 호출 경로 · 고정 모듈 hash (항목 2)

**호출 경로(02A 원본)**:
1. 러너 → `build_context(panel)` → arm·신호일마다 `evaluate_point` → `train_and_score`
2. `train_and_score` 의 순서
   - t 절단 연결 계열 이력 → `build_feature_rows_for_ticker`
   - `date_split`(`make_selection_folds` n_folds=1 · purge 20)
   - `train_walk_forward(S+V, ratio=(|S|+0.5)/(|S|+|V|))`
   - `predict_raw_scores(t 행)` → `normalize_to_display_scores`
   - (`app/ml_pit_bias_eval.py:184-271` · `:283-389`)

모델은 `nn.Linear(7,1)` · MSE · Adam · 전체 배치 · float32 · 200 epoch · lr 1e-3 · seed 42 다.
- 표준화하지 않는다.
- **S 만 학습**한다. V 는 test loss 계산에만 쓰여 점수에 영향이 없다.
- S+V 로 다시 학습하지 않는다(`app/ml_relative_upside_model.py:81-91` · `:189-204`).

**고정 모듈 hash** — `FROZEN_MODULES` 3개(`app/ml_baseline_provenance.py:39-44`)의 현재 sha256 이 02A run1·run2 manifest
기록과 같다.

```text
11910654204c0956486cd5fe9fb37c88f70c7e08c0eee533dd8fd30d0a52d442  app/ml_relative_upside_features.py
b41b2a9ac55a9d5ce1cd53b9b21aef65a0ac4db0fb82dc0d2a0ce03be99083c4  app/ml_relative_upside_model.py
8d53aa56457b43121ddb8a7809d7acb08583a64ffb2bbe14c4628287b55e58b9  app/ml_relative_upside_score.py
```

02A 가 실제로 import 한 `evaluator_modules` 20개도 raw·정규화 AST hash 가 전부 일치한다(불일치 0).
- 예: `ml_pit_bias_eval` `fb125d55…` · `ml_pit_universe` `fa160229…` · `krx_sealed_reader` `e43275ff…`
- 02A run1 은 미커밋 상태(`code_clean=False`)에서 돌았다. 그래서 같은 코드라는 근거는 git SHA 가 아니라 AST hash 일치다.

**02A 기준 산출물**은 실행 전에 아래 값과 대조해 고정한다.

| 파일 | 추적 | sha256 |
|---|---|---|
| `state/ml/research/poc4_02a/run1/result.json` | git 밖(`.gitignore:226`) | `edb1b0f65e55c18a2d3f5f441aa67bfea6b9ac054236d66508639b3b8e5dc57e` |
| `…/run1/run_manifest_final.json` | git 밖 | `4e5cd27c2b296540d6a33a3fc60760a285a64f932e60e64be8478f3f04608719` |
| `…/run1/progress/*.json` 292개 | git 밖 | 목록 digest `d42913404c46878eb8a2229de22d3b641a971f50d156d35e661fa416cf68656e` (`파일명\|sha256\n` 을 이름순으로 이은 문자열) |
| E2 평가일 manifest `state/ml/baselines/relative_upside_v1_snap_20260921/dataset_manifest.json` | **git 추적** | `6b9c893823c8252f148b1cbd237b757189419bec8470e15d06a2b454a0ea7dea` |

- run1 과 run2 의 progress 292개는 **바이트까지 같다**(`cmp` 불일치 0). 그래서 기준 폴더를 어느 쪽으로 해도 같다.
- 02A 전체 canonical(`1e9a88af…`)은 부트스트랩 2,000회와 PIT−CONTROL 블록까지 포함한다. 10,000회로 계산하면 반드시 달라지므로
  POC4-03 재현 판정 기준으로 쓰지 않는다. 재현 판정은 §2-3 의 날짜별 기록 일치로 한다.

**같은 프로세스 선형 재현(smoke 3)**
- 방법: sklearn 을 적재하고 RF(n_jobs=8)를 여러 번 fit 한 **같은 프로세스**에서 02A 원본 `evaluate_point` 를 불렀다.
  그 기록을 02A run1 `progress` 의 `record` 와 canonical JSON 텍스트로 비교했다.
- 결과: PIT·CONTROL × 2020-06-30·2026-07-31 **4/4 일치**했다.
- torch 스레드 수는 RF fit 뒤 같은 프로세스에서 4 였다(smoke 3 실데이터). RF 없는 새 프로세스의 기본값도 4 다.
  RF fit 전후에 바뀌지 않는다는 점은 검토 에이전트가 합성 데이터로 확인한 결과다.
- 이 비교는 이미 공개된 02A 선형 값만 참/거짓으로 봤다. 모멘텀·RF 성과는 계산하지 않았다.

### 1-3. 20일 모멘텀 — 입력 필드·부호·결측 (항목 3)

| 항목 | 실측·확정 |
|---|---|
| 후보 필드 | (a) `return_20d` = chain[t]/chain[t−20행] − 1 (ETF 자체) · (b) `excess_return_20d` = (a) − 069500 같은 두 날짜 수익률 (`app/ml_relative_upside_features.py:123-151`) |
| 날짜별 순위 | 146일 × PIT·CONTROL 에서 (a)·(b) 순위 상관이 모두 1이다(허용 1e-12 · PIT 최소 0.9999999999999998 · 두 arm 모두 순위 다른 날 0). 점수 행의 '20행 전'이 모두 달력 t−20 거래일이고 069500 이 단일 구간이라, 069500 수익률이 그날 모든 종목에 같은 상수다. **이 데이터에서 잰 성질이지 코드가 보장하는 성질은 아니다** |
| 확정 | (a) `return_20d` — 설계 §3 "20일 수익률을 그대로" 를 문자대로 읽은 것 (Q1 확정) |
| 부호 | 값이 클수록 높은 점수 · 정규화는 선형과 같은 `normalize_to_display_scores`(순위 → 0~100 · raw 차이 1e-12 미만 동점) (Q2) |
| 점수 대상 | 선형과 **같은 t 행** · 같은 `is_complete_for_inference`(7개 feature 모두 있음). 실측 대상 수가 02A `scored_count` 와 같다(PIT 75,428 · CONTROL 65,650 · 날짜별 불일치 0) |
| 결측 | 신규 상장(연결 계열 21행 미만)이나 t−20..t 사이 구간 단절이 있으면 t 행이 없거나 불완전하다 → 점수 없음 → 모든 IC·top-decile 에서 빠진다(02A 와 같음) |
| 동점 | 원값의 날짜별 **중복 값 수** 합계 PIT 77 · CONTROL 66 · IC 는 midrank Spearman · top-decile 경계 처리는 §2-4 (Q13) |

기존 E2 진단 `ic_simple_momentum`(+0.0226 · POC4-01 기준선 +0.0202)은 계약이 다르다.
- `excess_return_20d` 를 쓴다.
- 가격 원천이 `etf_daily_price` 다.
- t 행이 아니라 '가장 최근 완전 행'을 쓴다.
- 거래량 조건과 PIT 가 없다.

그래서 POC4-03 모멘텀의 재현 기준이 아니다. 모멘텀 IC·성과는 **일부러 계산하지 않았다**(설계 §3 "결과를 본 뒤 부호·정규화 변경 금지").

### 1-4. 02A 재사용 가능성 (항목 4)

| 항목 | 결론 |
|---|---|
| 146일 | E2 manifest `e2_dates` ∩ `build_calendar(panel.dates)` = 매월 마지막 거래일 2014-06-30 ~ 2026-07-31 · 146개월 빠짐없음 · 연도별 2014·2026 은 7개, 2015~2025 는 12개씩 · 공식 실행은 `assert_evaluation_window` 로 목록 동일을 강제 |
| 7 feature | `return_5d·10d·20d` · `excess_return_5d·10d·20d` · `drawdown_20d` (`FEATURE_COLUMNS` 순서) — 그대로 |
| 학습 label | `future_excess_return_20d` = (chain[i+20]/chain[i]−1) − 069500 같은 두 날짜 수익률 · t 이하에서 끝나는 행만 |
| 평가 label | 02A `label_outcome`(E2 `forward_excess` 식을 연결 계열로) · 진입 t 다음 거래일 → 청산 다음 월말 다음 거래일 · ETF 진입·청산 거래량 > 0 · 민감도 label(거래량 조건 제외)도 그대로 |
| 분할 | `date_split` — 달력 ≤ t · 표본일 index ≥ 20 · 검증일 수 N−int(0.8N) · purge 20 · 두 arm 같은 경계 · 02A 는 146일 × 2 arm 모두 `split.status=OK` |
| 필터·제외 사유 | `passes_name_filter`(t 행 `ISU_NM` 태그) · `is_eligible` · `classify_pair` 사유 — 그대로 |
| 원천 | 봉인 `krx_etf_universe_v1`(`SealedPanel`) 하나뿐 · `etf_master`·운영 DB·생존 DB 로 결측을 채우지 않는다 · E2 manifest 는 날짜 목록 JSON 으로만 읽는다 |

**재사용 방식의 제약**:
- `evaluate_point` 는 선형 `train_and_score` 를 안에서 직접 부르고(`:290`), 점수를 넣을 인자가 없다.
- `train_and_score` 는 S·V·t 행을 돌려주지 않는다.
- 02A 모듈은 수정할 수 없다(설계 §2).

그래서 새 평가 모듈이 행 수집(`:199-236` 과 같은 규칙)과 기록 조립(`:291-389` 와 같은 규칙)을 다시 구현한다.
02A 와 몰래 어긋나는 일은 두 겹으로 막는다(§2-3).
- 공식 실행에서 선형 기록을 02A 기록과 완전 일치로 대조한다.
- 테스트에서 02A `evaluate_point` 와 같은 결과가 나오는지 확인한다.

### 1-5. RF 3설정 — 정확한 값과 근거 (항목 5)

```text
공통   RandomForestRegressor(n_estimators=200, criterion="squared_error", bootstrap=True, max_samples=0.25,
                             random_state=42, n_jobs=8)   ← n_jobs 는 결과에 영향 없음(아래 결정성)
RF_A   얕은 숲    max_depth=4   min_samples_leaf=0.005   max_features=1.0   (분기마다 7개 전부)
RF_B   중간 숲    max_depth=8   min_samples_leaf=0.001   max_features=0.5   (분기마다 3개 · int(0.5×7))
RF_C   깊은 숲    max_depth=16  min_samples_leaf=0.0002  max_features=0.5
나머지 인자는 sklearn 1.9.0 기본값(min_samples_split=2 · max_leaf_nodes=None · min_impurity_decrease=0 · ccp_alpha=0 ·
monotonic_cst=None) — 버전을 1.9.0 으로 고정해 함께 동결한다.
```

설정 sha256 은 아래 문자열의 sha256 이다(`json.dumps(obj, sort_keys=True, separators=(',', ':'))` · n_jobs 제외):

```text
{"RF_A":{"bootstrap":true,"criterion":"squared_error","max_depth":4,"max_features":1.0,"max_samples":0.25,"min_samples_leaf":0.005,"n_estimators":200,"random_state":42},"RF_B":{"bootstrap":true,"criterion":"squared_error","max_depth":8,"max_features":0.5,"max_samples":0.25,"min_samples_leaf":0.001,"n_estimators":200,"random_state":42},"RF_C":{"bootstrap":true,"criterion":"squared_error","max_depth":16,"max_features":0.5,"max_samples":0.25,"min_samples_leaf":0.0002,"n_estimators":200,"random_state":42}}
→ edca7023bb80aebbadceb5812b73aeaf3a3fbf86bbb0209c508830a378dbbe35
```

**recipe sha** — 설정 sha 밖에서 결과에 영향을 주는 규칙을 모두 한 JSON 에 담아 sha256 으로 동결한다. 설정 sha 와 함께
C10 의 '사후 변경 0' 근거가 된다. 동결값은
`00992e6eaa2394680e6d106ececf66f77857eb34b800ad938da3c99feaa11350` 이다(`app/ml_rf_gate_verdict.py` `recipe()` 의
`json.dumps(ensure_ascii=False, sort_keys=True, separators=(',', ':'))` sha256 · 공식 실행 전 확정 · 러너가 시작 때 대조).
대상은 다음과 같다.
- 아래 입력 규칙(행 순서 · 열 순서 · dtype · 예측식)
- 선택 규칙(§1-6 · Q4·Q5)
- top-decile 동점 규칙(§2-4 · Q13)
- bootstrap 인자(10,000회 · seed 42 · 블록 6 · Q15)
- paired·None 규칙(§2-5)
- 강건성 정의(§2-6 · Q8)
- 판정 순서 버전(§2-7 · Q7)

**함께 동결하는 입력 규칙** — 같은 seed 라도 행 순서가 바뀌면 bootstrap 이 다른 행을 뽑기 때문이다:
- **S 행 순서**: (asof_date, ticker) 오름차순. 선형 trainer 와 같다(`app/ml_relative_upside_model.py:134`).
- **열 순서**: `FEATURE_COLUMNS`.
- **dtype**: X 는 float32 로 바꿔 넣는다. sklearn 트리도 내부에서 float32 를 쓴다. y 는 float64.
- **예측**: 트리를 `estimators_` 순서대로 `predict(X32, check_input=False)` 해서 더한 뒤, 트리 수로 나눈다.

날짜·설정마다 입력 지문(X_S·y_S 바이트 sha256)과 숲 지문(트리별 threshold·value 의 hash)을 진행 기록에 남긴다.
재실행 때 입력과 숲이 그대로인지 증명하기 위해서다.

**그 밖의 처리**:
- **결측**: 채우지 않는다. 행은 선형과 같은 완전성 필터(학습 8개 · 추론 7개 None 금지)를 통과한 것만 쓴다. 현 데이터 경로에서
  NaN 이 생기는 길은 확인되지 않았다. fit 전 유한성 검사(`np.isfinite`)가 NaN·inf 를 모두 `INVALID_STOP` 으로 막는다.
  smoke 3 에서는 세 날짜 모두 유한했다.
- **표준화**: 하지 않는다. 트리는 단조 변환에 불변이고, 선형도 표준화하지 않는다.
- **target**: `future_excess_return_20d` 원값을 쓴다(선형과 같은 MSE).
- **학습 행**: 선형과 같은 S 만 쓴다. 설정 선택 뒤 S+V 로 다시 학습하지 않는다(Q3).
- **`min_samples_leaf` 비율**: sklearn 이 ceil(비율 × |S|)로 푼다(`sklearn/tree/_classes.py:320` · n_samples = 전체 S 행).
  S 가 커져도 모델 복잡도가 S 에 비례해 유지된다.

| arm · 날짜 | |S| | A | B | C |
|---|---|---|---|---|
| PIT 첫날 2014-06-30 | 6,405 | 33 | 7 | 2 |
| PIT 마지막 2026-07-31 | 921,424 | 4,608 | 922 | 185 |
| CONTROL 첫날 2014-06-30 | 4,381 | 22 | 5 | **1** |
| CONTROL 마지막 2026-07-31 | 757,891 | 3,790 | 758 | 152 |

RF_C 의 잎 최소는 CONTROL 2014-06-30 하루만 1 이다(깊이 상한 16 만 규제). 그 뒤 초기 몇 달은 2 다(PIT 2일 · CONTROL 3일).
받아들일지는 Q16 이다.

**근거 — 성과가 아니라 문제 구조와 자원으로 정했다.**

1. **target 잡음이 크다.** 20일 초과수익이고, label 이 겹쳐 행끼리 자기상관이 크다. 그래서 세 설정 모두 깊이 상한을 두고
   트리마다 표본을 25% 만 쓰게 했다. 잎 최소 비율도 둔다.
2. **feature 7개가 강하게 겹친다.** 같은 수익률의 창 길이 차이이고, 초과수익은 같은 날 상수 차이다. 그래서 B·C 는 분기마다
   3개만 보게 해 트리끼리 덜 닮게 했다. A 는 7개 전부를 보는 얕은 모델로 남겨 '낮은 차수 비선형'을 대표하게 했다.
3. **세 설정이 복잡도 축을 넓게 덮는다**(얕음 · 중간 · 깊음). 그래서 PASS 조건 "고정 설정 중 최소 2개가 모멘텀보다 나음"은
   우연히 맞은 한 설정이 아니라 **복잡도 선택에 강건한가**를 본다.
4. **트리 수·표본 비율은 4시간 상한에서 정했다.** 1차 smoke 설정(트리 300 · 표본 50%)은 두 arm RF fit 만 약 5.8~6.3시간
   (멱함수~보수)으로 추정돼 상한을 넘었다. 트리 200 · 표본 25% 로 줄였다. 같은 seed 로 잰 2차 기준 fit 시간이 0.35배,
   현 보수 추정(3차 · seed 42) 기준으로는 0.39배다. **test 결과를 보기 전에 자원만 보고 정했다.**
5. **seed** 42 는 프로젝트 관례다(선형 `DEFAULT_RANDOM_SEED` · bootstrap `BOOTSTRAP_SEED`). smoke 3 은 seed 42 로 쟀다.
   smoke 1·2 는 seed 20260925 였다.

**결정성**(실측):
- **fit**: 트리별 정수 seed 를 병렬 실행 전에 순서대로 뽑으므로(`sklearn/ensemble/_base.py:77-84`), n_jobs 와 관계없이
  트리가 같다.
  - 합성 데이터: n_jobs 1 · 4 · −1(=8코어)의 트리 hash 가 같았다.
  - 실데이터: n_jobs 4·8 의 예측 hash 가 같았다.
- **predict**: sklearn `predict` 는 스레드가 끝나는 순서대로 더한다(`_forest.py:704-717`). 그래서 n_jobs>1 이면 마지막 bit
  (약 1e-17)가 실행마다 달라진다(실측). 그래서 위 순서 고정 예측을 쓴다.
  실데이터에서 같은 설정을 두 번 fit 했을 때 예측 hash 가 같았다(1차 RF_B · 2차 RF_C · 3차 RF_B 세 번).
- **병렬 방식**: RF 병렬은 스레드다(`prefer="threads"` · `_forest.py:471`). 러너가 joblib backend 를 바꾸지 않는 한
  하위 프로세스가 생기지 않는다. 그러면 in-process sqlite 가드와 `ru_maxrss` 측정이 그대로 유효하다.
  러너는 backend 를 바꾸지 않고, 이를 테스트로 확인한다.

### 1-6. 신호일별 설정 선택 절차 · 동률 규칙 (항목 6 · 필수 보완 A·B 확정)

각 arm · 각 신호일 t 에서:

1. 선형과 같은 S·V·t 행을 한 번 만든다. V 는 t 이전 검증 구간이고, 그 행들의 학습 label 은 t 이하에서 끝난다.
2. **RF 학습 행 S′** = S 에서 label 끝 날짜(`target_end_date` = 그 종목 연결 이력의 20행 뒤 날짜)가 V 시작일 이상인 행을 뺀 것이다.
   - 뺀 행 수는 날짜별로 기록한다.
   - 이 규칙은 RF A·B·C 에만 똑같이 적용한다. 02A 선형 기록은 S 그대로 재현한다.
   - S′ 가 2행 미만이라 모델을 만들 수 없으면 뺀 행을 되살리지 않고 `INVALID_STOP` 이다.
     RF 만 NO_MODEL 로 두면 여섯 모델의 단면이 달라지기 때문에 NO_MODEL 대신 이쪽을 골랐다.
3. 설정 c ∈ {A, B, C} 마다 S′ 로 fit 한 뒤, 선택용 V 행과 t 행을 예측한다.
4. `val_IC_c` 를 구한다. **V 구간 모든 거래일**마다 Spearman(예측, `future_excess_return_20d`)을 구해 평균한다.
   - 선택용 V 행은 세 조건을 모두 만족하는 행이다.
     - 그 V 날짜의 `ISU_NM` 이 이름 필터를 통과한다.
     - 7개 feature 가 완전하다.
     - 검증 target 이 있다.
   - 날짜 이하 정보만 쓴다. E2 `forward_excess` 와 t 이후 정보는 선택 경로에 들어가지 않는다.
   - 기존 `spearman` 을 쓴다(midrank). 관측 2개 미만이거나 상수인 날은 그 날만 뺀다.
   - 결과가 finite 가 아니면(None·NaN) 그 설정의 `val_IC` 는 None 이다.
5. 설정을 고른다(반올림 없음).
   - None 인 설정은 후보에서 뺀다.
   - 남은 후보 가운데 `val_IC` 원값이 가장 큰 설정을 고른다.
   - 정확히 같으면 A → B → C 순서로 고른다.
   - **세 값이 모두 None 이면 A 를 고르지 않고 `INVALID_STOP`** 이다.
   - 사유 코드를 기록한다: `MAX` · `EXACT_TIE` · `PARTIAL_NONE`.
6. `RF_PRIMARY(t)` 점수 = 선택된 설정이 3단계에서 낸 t 예측이다(S+V 로 다시 학습하지 않는다 · Q3).
7. 날짜별로 기록하는 것: 설정별 `val_IC` · 선택 설정 · 사유 · S′ 제외 행 수.
   선택 함수는 V 행·예측·target 만 받는다. 평가 label 을 받을 수 없다(테스트로 강제).

**RF 입력 실행 중 단언**(선형 `_check_trainer` 에 대응 · 위반 시 `INVALID_STOP`):
- max(S′ 날짜) < V 시작
- S′ label 끝 < V 시작
- V 날짜 ⊆ 검증 날짜
- S′∪V label 끝의 최댓값 ≤ t
- t 행 ∉ S′∪V
- 입력 전부 유한

비용: V 날짜별 Spearman 은 설정 1개당 0.49초다(마지막 날 V 576,443행 · 610일 · 무작위 점수로 시간만 잼).
이름 필터 판정은 이름 문자열마다 한 번만 계산한다(캐시).

### 1-7. train-only smoke — 시간·RSS·동점·재현 (항목 7)

세 번 돌렸다. 대상은 PIT arm 이고 행 수집은 02A 와 같다. fit 은 S 로만 했다. 성과는 계산하지 않았다. RSS 는 모두 10진 GB(10^9 바이트)다.

**fit 시간(초 · A / B / C · n_jobs 8)**

| 회차 | 설정 · seed | 2016-06-30 (S 71,583) | 2020-06-30 (S 294,005) | 2026-07-31 (S 921,424) | 예측 V+t (2026-07-31) | peak RSS |
|---|---|---|---|---|---|---|
| 1차 | 트리 300 · 표본 50% · 20260925 | — | B 만: 34.5(n_jobs 4) · 23.7 · 15.0 | 60.9 / 55.0 / 112.3 | 2.2 / 3.5 / 8.0 | 2.23 GB |
| 2차 | **최종 후보** · 20260925 | — | 6.4 / 5.6 / 10.0 | 22.0 / 20.3 / 37.7 | 1.5 / 2.3 / 4.7 | 2.36 GB |
| 3차 | **최종 후보** · **42** | 1.3 / 1.1 / 1.9 | 10.5 / 7.5 / 10.0 | **23.0 / 21.0 / 44.3** | — | 2.62 GB (02A 선형 재현 포함) |

- 행 수집은 0.65 / 2.1~2.2 / 6.4~6.8초다. 배열 변환은 0.06 / 0.68 / 1.78초로, S+V+t 행당 0.63 / 1.58 / 1.19 µs 다.
  선형 학습은 2.1~2.3초(중간 날짜) / 4.2~4.6초(마지막 날짜)다. 봉인 적재는 16~18초다.
- **부하 편차**:
  - 1차에서 같은 측정(RF_B 중간 날짜 n_jobs 8)이 23.7초와 15.0초로 **58%** 갈렸다. 조사 에이전트가 함께 돌던 때다.
  - 3차에서도 같은 fit(RF_B · 2020-06-30 · seed 42 · 같은 입력)이 본 루프 7.54초, 이어서 연속 반복 5.95 / 6.00 / 5.57초였다.
    다른 작업이 없던 한 실행 안에서도 **최대 1.35배** 갈렸다.
  - 그래서 §1-8 의 ×1.00 기준값(3차 본 루프 88.3초)은 느린 쪽 측정이다.
- **결정성**: 같은 설정을 반복 fit 했을 때 예측 hash 가 모두 같았다. n_jobs 4 대 8 도 같았다.

**t 점수 동점(3차 · label 없음 · k = max(1, round(n×0.1)))**

**점수 대상 전체(t 행) 기준으로 쟀다.** 실제 top-decile 은 이름 필터·`is_eligible`·label 을 통과한 `rows_filter` 에서 고른다.
그래서 모집단과 k 가 다르다(예: 02A PIT 2026-07-31 은 `n_filter` 914 · 상위 91). 평가 모집단의 경계 동점은 label 이 필요해
재지 않았다. 동점 묶음의 시작 순위도 기록하지 않았다.

| 날짜 | n | 모델 | 고유 점수 | 최대 동점 묶음 | top-decile 경계가 동점 묶음 안 |
|---|---|---|---|---|---|
| 2016-06-30 | 210 | RF_A | 194 | 4 | **예**(묶음 2) |
| | | RF_B · RF_C · MOM · LIN | 209 · 210 · 209 · 210 | 2 · 1 · 2 · 1 | 아니오 |
| 2020-06-30 | 443 | RF_A | 418 | 6 | 아니오 |
| | | RF_B · RF_C · MOM · LIN | 435 · 442 · 442 · 443 | 3 · 2 · 2 · 1 | 아니오 |
| 2026-07-31 | 1,137 | **RF_A** | **256** | **119** | **예 — 경계(114위)가 119행 동점 묶음 안 · 묶음 위치는 미기록** |
| | | RF_B · RF_C · MOM · LIN | 1,025 · 1,108 · 1,133 · 1,137 | 18 · 6 · 4 · 1 | 아니오 |

RF_A 는 얕은 트리에 큰 잎(마지막 날 4,608행 이상)을 쓰고, 분기마다 7개 feature 를 모두 본다. 그래서 트리 200개가 비슷해져
예측이 소수의 값으로 모인다.

02A 의 top-decile 규칙은 점수 내림차순 안정 정렬이라, 경계 동점은 **종목코드 오름차순**으로 갈린다. 그러면 RF_A 의 상위
바스켓 일부가 모델이 아니라 코드 순서로 정해질 수 있다. 참고로 선형은 02A PIT·CONTROL 146일 동안 `rows_filter` 기준
경계 동점이 0일이었다(위 표와 모집단이 다르다). 처리 규칙은 사전 등록한다(§2-4 · Q13).

### 1-8. 공식 실행 예상 시간·RSS (항목 8)

규모(02A 기록 · 146일 합):
- PIT: 학습 S 51,398,245 · 검증 V 26,050,919
- CONTROL: S 40,717,468 · V 22,585,406
- 최대 S: 921,424(PIT 2026-07-31)

**보수 추정** — 비용별 산정 근거는 다음과 같다.
- fit: 3차 smoke(seed 42) 마지막 날짜 행당 비용(88.3초 / 921,424행 = 95.85 µs) × S 합
- 예측·검증 IC·배열 변환: 행 수에 비례
- 선형·행 수집·평가: 02A run1 의 arm 별 진행 구간(PIT 872초 · CONTROL 731초 · 파일 시각 기준 대리값)
- 나머지 모델 5개의 기록 조립과 N-1 셔플: arm 당 약 50초로 추정했다(대부분 순수 Python Spearman · 미계측)

| 항목 (초) | PIT | CONTROL |
|---|---|---|
| RF fit 3설정 | 4,927 | 3,903 |
| RF 예측 V+t | 384 | 333 |
| 검증 IC | 66 | 58 |
| 배열 변환 | 92 | 75 |
| 선형 · 행 수집 · 평가 | 872 | 731 |
| 기록 조립 · N-1 (추정) | 50 | 50 |
| 봉인 검증·적재 · 집계 · bootstrap (추정) | 100 | 100 |
| **합** | **6,491 (1.80시간)** | **5,250 (1.46시간)** |

| 부하 배율 | 두 arm 한 실행 (두 arm 합) | PIT 실행 | CONTROL 실행 |
|---|---|---|---|
| ×1.00 (기준값) | 3.26시간 | 1.80시간 | 1.46시간 |
| ×1.33 (02A 선형 루프 편차) | **4.34시간 — 상한 초과** | 2.40시간 | 1.94시간 |
| ×1.58 (1차 smoke 관측 편차) | **5.15시간 — 상한 초과** | 2.85시간 | 2.30시간 |

- 배열 변환은 마지막 날짜 비율(1.19 µs)로 셌다. 2020-06-30 비율(1.58 µs)을 쓰면 arm 당 25~30초 늘어난다.
- 선택용 V 모집단의 이름 필터 판정은 이름 문자열마다 캐시하므로 추가 비용이 작다(확정 Q4 는 `is_eligible` 을 쓰지 않는다).
- 2차 smoke 두 점으로 구한 멱함수(지수 1.131)를 쓰면 RF fit 추정이 약 9% 작아진다(표 전체 합으로는 약 7%). 그래도 두 arm 한
  실행은 부하가 있으면 상한 근처다.

PLAN 에서 "두 arm 한 실행은 4시간 상한을 넘을 수 있다"고 보고했고, 설계자는 다음을 확정했다(Q10·Q11 · 필수 보완 C).
- **arm 별 실행**: PIT 처음부터 2회를 먼저 돈다. 한 번에 1.80시간이고, 부하 ×1.58 이어도 2.85시간이다.
- **CONTROL 조건부**: PIT 최종 판정이 PASS 일 때만 CONTROL 처음부터 2회를 돈다(1회 1.46시간).
- 설정은 가볍게 바꾸지 않는다.

RSS 는 다음과 같다.
- smoke peak 는 2.23 / 2.36 / 2.62 GB(3차는 02A 선형 재현 포함)이고, 02A 선형 실행 peak 는 2.60 / 2.69 GB 다.
- RF 모델은 날짜마다 하나씩 fit → 예측 → 해제한다. 설정 하나의 잎 합계는 최종 후보 설정(2차 · seed 20260925) 두 날짜 기준
  최대 44,719개(RF_C · 2020-06-30)였다. seed 42 는 잎 수를 재지 않았다.
- 예상은 약 3 GB(추정)로 상한보다 충분히 작다. 상한 판정은 `ru_maxrss ≥ 10×10^9` 바이트다.

공식 실행은 순차로만 돌린다. 전체 pytest 와 동시에 돌리지 않는다. pytest 세션 지문이 `state/` 아래 새 파일을 라이브 변경으로
잡기 때문이다(`tests/conftest.py:52-81`). 공식 실행 중에는 다른 무거운 작업을 하지 않는다(전제 조건으로 manifest 에 기록).

**상한 감시**(Q11 확정): 러너가 신호일마다 `perf_counter` 경과 시간과 `ru_maxrss` 를 잰다.
- 4시간 또는 10×10^9 바이트를 넘으면 그 자리에서 멈추고 `guard_failed`(RESOURCE_LIMIT)를 남긴다 → `INVALID_STOP`.
- UTC 시각을 함께 기록한다. `caffeinate -i` 로 잠자기를 막는다.
- 초과 뒤 처리는 §2-8 을 따른다.

### 1-9. 재사용 모듈 · 신규 파일 · 줄 수 (항목 9)

**수정 없이 import 해서 쓰는 것**
- `krx_sealed_reader`: `load_panel` · `verify_sealed_source` · `assert_same_source`
- `ml_pit_universe`: `arm_codes` · `classify_pair` · `benchmark_pair` · `build_facts` · `is_eligible` · `passes_name_filter` ·
  `name_at` · `has_volume` · `empty_reasons`
- `ml_pit_bias_eval`: `build_context` · `date_split` · 상수
- 고정 모듈: `build_feature_rows_for_ticker` · 완전성 함수 · `train_walk_forward` · `predict_raw_scores` · `normalize_to_display_scores`
- `ml_score_validity_metrics`: `spearman` · `top_fraction` · `quantile_means` · `win_rate` · `replaced_fraction` · `cost_drag` ·
  `circular_block_bootstrap_ci`
- `ml_pit_bias_report`: `basket_series` · `strategy_block` · `n1_control` · `public_record`
- `ml_score_validity_report`: `preflight_gate` · `canonical_sha256` · `now_iso`
- `ml_score_validity_eval`: `build_calendar` · `assert_evaluation_window`
- `ml_baseline_snapshot`: `new_run_dir` · `guard_sqlite_paths` · `file_sha256`
- `ml_baseline_provenance`: `code_provenance` · `environment` · `node_info`

**쓰지 않는 것**
- 02A report 의 `_summary`·`_ci`·`_paired`·`arm_metrics` — CI 가 2,000회로 고정돼 있다.
- `recipe_block`·`build_result` — 선형 전용 문구다.
- 02A·02B 러너 — 스크립트라 패키지 import 경로가 아니고, 결합을 피하려고 쓰지 않는다.

| 신규 파일 (예상 줄 수) | 책임 |
|---|---|
| `app/ml_rf_gate_models.py` (~230) | 동결 RF 설정 + sha 검사 · 입력 규칙(정렬·float32·유한성) · fit · 순서 고정 예측 · 숲 지문 · 검증 IC · 설정 선택(동률·결측) · 모멘텀 점수 |
| `app/ml_rf_gate_eval.py` (~400) | 신호일 행 수집(S·V·t · 02A 규칙) · RF 입력 단언 · 선형 학습(02A 호출 그대로) · 공통 단면(universe·사유·label) 한 번 계산 · 모델별 기록 조립(02A 규칙) · 모델 간 단면 동일 단언 |
| `app/ml_rf_gate_report.py` (~450) | 동점 반영 top-decile(§2-4) · 모델별 지표(10,000회 CI) · RF−모멘텀 날짜별 paired 차이 · 전략 성과 · 강건성 블록 · 선택 빈도 · 동점 진단 |
| `app/ml_rf_gate_verdict.py` (~200) | 모델별 preflight · 판정 조건 C1~C10 · 판정 순서(§2-7) · PIT−CONTROL 진단 결합 |
| `app/research_run_guard.py` (~250) | 라이브 5경로 지문 · 배타 쓰기 · `guard_failed` · 실행 폴더 규칙 · peak RSS · 자원 상한 · compare 핵심 규칙 (Q12) |
| `scripts/run_poc4_03_rf_kill_gate.py` (~480) | CLI(`run --arm` · `compare` · `summarize`) · 02A 기준 산출물 대조 · 날짜 루프 · 진행 기록·재개 · 자원 감시 · manifest · 결과 |
| `tests/test_poc4_03_models.py` (~260) · `…_eval.py` (~400) · `…_report.py` (~340) · `…_runner.py` (~470) | §3 |

신규 코드는 app·scripts 약 2,010줄, 테스트 약 1,470줄이다. 모든 파일이 600줄 미만이 되도록 계획했다.
`ml_score_validity_report.py`(626 · NEAR · 기능 추가 금지)와 `ml_score_validity_eval.py`(589)에는 아무것도 추가하지 않는다.

### 1-10. KS-10 전체 측정 (항목 10)

`git ls-files '*.py' '*.ts' '*.tsx'` → **518개 · 136,182줄**(2026-09-25 · working tree = HEAD · 소스 diff 없음).
분류는 02A A10 을 따른다(`scripts/` = 백엔드 · `tests/_live_guard.py` = 테스트 도우미).

| 분류 | TRIGGER | NEAR |
|---|---|---|
| 백엔드(>650 / ≥600) | 0 | 6 — `scripts/run_three_push_runtime_oci.py` 646 · `app/api.py` 641 · `scripts/ops02c/reverse_verify_guards.py` 638 · `app/ml_score_validity_report.py` 626 · `app/holdings_market_evidence.py` 616 · `app/draft.py` 602 |
| 프론트 컴포넌트(>900 / ≥850) | 0 | 1 — `frontend/app/components/JudgmentWorkbenchView.tsx` 855 |
| 테스트(>1,500 / ≥1,450) | 0 | 0 — 최대 `tests/test_intraday_config_integration.py` 1,423 |

POC4-03 은 기존 코드 파일을 고치지 않는다. 그래서 NEAR·TRIGGER 목록은 바뀌지 않는다(신규 파일은 모두 600 미만).

### 1-11. 라이브 5경로 · 봉인 DB 불변 검증 (항목 11)

02A 방식을 그대로 쓴다(`scripts/run_poc4_02a_pit_bias.py:131-140` · `:274-370`).

- **라이브 5경로**:
  - 대상은 파일 4개와 폴더 1개다.
    - sha256 을 재는 파일: `state/market/market_data.sqlite` · `state/market/nav_discount_refresh_latest.json` ·
      `logs/oci_market_data_batch.log` · `logs/three_push_runtime_cron.log`
    - 이름 목록을 재는 폴더: `state/runs`
  - 실행 폴더를 만들기 **전**과 결과를 쓰기 **전**에 잰다. 재개할 때는 시작 시점에도 잰다(02B 방식 추가).
  - 다르면 `guard_failed`(LIVE_PATHS_CHANGED)를 남기고 결과를 쓰지 않는다.
- **봉인 DB**:
  - `guard_sqlite_paths([봉인])` 블록 안에서 `verify_sealed_source` 를 실행 전과 후에 돈다.
  - `assert_same_source` 로 14필드 전체를 대조한다(파일 sha256 `fe3022e9…` · content `c1a87776…` · integrity 포함).
  - 다르면 `guard_failed`(SEALED_SOURCE_CHANGED)를 남긴다.
  - 같은 블록이 봉인 밖 sqlite 열기(운영 DB · E2 스냅샷 DB · `etf_master`)를 막는다.
- **02A 기준 산출물**: §1-2 표의 hash 4개를 시작 전에 대조한다. 다르면 시작하지 않는다(INVALID_STOP · 기준 불일치).
- **입력 지문(재개 판정)**:
  - 봉인 sha 2개 · E2 manifest sha · 02A 기준 hash 4개 · 코드 정규화 AST · RF 설정 sha `edca7023…` · recipe sha(§1-5 입력 규칙 포함) · arm
  - **패키지 버전**(sklearn · numpy · torch · joblib) — 02A 지문에는 없던 항목이다.
- **네트워크 0**: 테스트로 강제한다(02A 와 같음).

### 1-12. 테스트 · 회귀 · 결정성 범위 (항목 12)

- **focused**(4파일 · §3): 새 테스트는 봉인·라이브 DB 를 열 수 없다(`tests/_live_guard.py` · 허용 목록 229건 추가 0).
  `tests/_krx_fixture.py` 로 만든 tmp 봉인 DB 와 tmp 프로젝트 루트만 쓴다.
- **전체 회귀**: 마지막 기록은 2,134 passed · 약 4분(background)이다. 공식 실행과 겹치지 않게 돈다.
- **결정성**:
  - PIT 처음부터 2회 공식 실행한다(`caffeinate -i`). CONTROL 은 PIT 가 PASS 일 때만 처음부터 2회.
  - `compare` 는 canonical(`generated_at` 만 제외)이 같은지 본다. 시간·RSS 는 `run_meta` 에만 둔다.
  - 재개한 실행과 같은 폴더끼리의 비교는 증거로 인정하지 않는다(02A 규칙 · 설계 §7). `guard_failed` 폴더는 명시적으로 거부한다(02B 규칙).
- **품질**: `black --check` · `flake8` · `py_compile`. 결과서의 수집 수는 `pytest --collect-only` 실측으로 적는다.

---

## 2. 실험 계약 (확정 — 설계자 PLAN 판정 2026-09-25)

### 2-1. 실행 단위 · 순서 (Q6·Q10 · 필수 보완 C)

```text
run --arm PIT      # 주 평가 · 판정
  for t in 146 신호일:
    1. S·V·t 행 한 번 수집 (02A 규칙)
    2. LIN = train_walk_forward(S+V, ratio) → t 점수 → 기록 → 02A 기준 기록과 대조   ← 불일치면 즉시 멈춤 (§2-3)
    3. MOM = t 행 return_20d (학습 없음)
    4. RF_A·RF_B·RF_C = S′ 로 fit → 선택용 V·t 예측 → val_IC → RF_PRIMARY (§1-6)
    5. 모델 6개 기록(같은 조립 규칙) + 선택 정보 + 동점 가중치 + 입력·숲 지문 → 진행 기록 1파일
compare  PIT run1 · PIT run2 → 결정성 + 최종 판정
run --arm CONTROL  # PIT 최종 판정이 PASS 일 때만 · 여섯 모델 전부 같은 절차 · 진단만
summarize          # PIT 결과 + CONTROL 결과 → PIT−CONTROL 진단 표 (판정을 뒤집지 않음)
```

**실행 순서**는 다음과 같다.
1. PIT run1 → PIT run2 → `compare` 로 결정성을 대조하고 최종 판정을 낸다.
2. PIT 가 PASS 후보가 아니면 여기서 Track A 를 종료한다. CONTROL 은 실행하지 않는다.
3. PASS 후보면 CONTROL run1 → run2 → `compare` → `summarize` 를 돈다.
4. CONTROL 은 축소하지 않는다. 선형·모멘텀·RF A/B/C·RF_PRIMARY 를 모두 같은 절차로 돌린다. 결과는 진단만 하고 PIT 판정을 뒤집지 않는다.

**모델 6개는 날짜마다 같은 종목 단면을 쓴다.**
- 점수 대상은 t 행 완전성 하나다. 모델마다 같은 조립 함수로 기록을 만든다.
- 날짜마다 여섯 모델의 `rows_filter`·`rows_all`·`rows_sens` 의 (종목, label) 순서열이 같은지 단언한다. 다르면 멈춘다.
- 모멘텀도 선형과 같은 `has_model`·`benchmark_ok` 를 쓴다.
- **NO_MODEL 날 규칙**: 선형에 모델이 없는 날은 모멘텀·RF 도 점수를 가리고, 여섯 모델 모두 NO_MODEL 로 기록한다
  (02A 는 146일 × 2 arm 모두 모델이 있었다).

**로그**: RF·모멘텀의 날짜별 지표(IC 등)는 로그에 찍지 않는다. 진행 상황과 시간·RSS 만 남긴다.

### 2-2. 점수 → 평가 기록

- 모든 모델 점수는 `normalize_to_display_scores` 를 거친다(Q2). 그다음 02A 와 같은 규칙으로 조립한다.
  - `rows_filter` → `ic_filter` · 5분위 · top-decile
  - `rows_all` → `ic_all`
  - `rows_sens` → 민감도
  - coverage · 사유 집계
- 선형 기록은 02A 스키마와 **정확히 같게** 만든다. 모델별 추가 정보(선택·동점 가중치·지문)는 기록 밖 wrapper 에 둔다.
- 모멘텀 기록의 학습 필드: `train_row_count=0` · `max_target_end_date=None` · `split.status="NO_TRAINING"`.
- RF 기록의 학습 필드:
  - `train_row_count=|S′|` · `test_row_count=|V|`
  - `max_target_end_date` = S′∪V label 끝의 최댓값
  - `split` 에 S′ 제외 행 수와 선형 분할 지문을 담는다.
- **누수 게이트**: 모델마다 `preflight_gate` 를 돌린다.
  - 대상: L1 입력 ≤ t · L2 진입 > t · L3 학습 target 끝 ≤ t · coverage ≥ 0.70 · N-1 셔플 대조
  - 하나라도 막히면 `INVALID_STOP` 이다.

### 2-3. 선형 baseline 재현 게이트 (설계 §3 · §6 · Q14)

- **비교 대상**: 신호일마다 새 경로로 만든 **선형 기록 전체**(`_scores`·`_labels` 포함)와 02A run1
  `progress/{arm}_{date}.json` 의 `record` 다.
- **비교 방식**: canonical JSON 텍스트가 같은지 본다.
  `json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))`.
  - 실행하는 arm 의 146일 전부가 대상이다(PIT · 실행 시 CONTROL — 합 292건).
  - 날짜별 canonical sha 를 진행 기록에 남긴다.
- **순서**: 날짜마다 선형을 먼저 만들고 대조한다. 첫 불일치에서 즉시 멈추고 `guard_failed`(LINEAR_REPRODUCTION_FAILED)를 남긴다.
  그 날짜의 모멘텀·RF 는 계산하지 않는다.
- **실행 전 확인**: `ML_RELATIVE_UPSIDE_FORCE_CPU` 가 꺼져 있어야 한다. 켜져 있으면 device 문자열이 달라 불일치가 난다.
- **02A 기준 기록의 사용 범위**: 대조 함수 안에서만 읽고 참/거짓만 돌려준다. 평가·선택 함수로는 넘기지 않는다(테스트로 고정).

### 2-4. 지표 · 경계 동점 부분 가중 (설계 §4 · Q9·Q13 · 필수 보완 D)

모델 6개마다 다음을 낸다.
- IC(`ic_filter`)의 n · 평균 · 중앙값 · sd · 95% CI · `ic_all`
- top-decile gross 와 net 0 · 10 · **25** · 50bp
- turnover · win rate · 5분위−1분위 스프레드
- 전략 성과 CAGR · MDD · Sharpe · 상대 wealth · IR
  - 기존 시나리오 `legacy_all_in_25bp` + 분해형 편도 6.5 · **11.5**(STRATEGY_REFERENCE) · 26.5 · 51.5bp
- 민감도 label 블록
- 동점 진단: 날짜별 고유 점수 수 · 경계 동점 묶음 크기 · 경계 동점 날 수

비용은 설계 §4 를 따른다: PRIMARY = top-decile net 25bp · STRATEGY_REFERENCE = 전략 11.5bp · SENSITIVITY = top-decile net 10·50bp.

**경계 동점 부분 가중 바스켓**(가중치는 점수와 목표 종목 수로만 정한다 · label 을 쓰지 않는다):

```text
rows_filter 를 점수 내림차순 · k = max(1, round(n×0.1)) (02A 와 같음)
s_k = k 번째 점수 · a = 점수 > s_k 인 행 수 · 묶음 G = 점수 == s_k 인 행 (경계 동점 종목 전부 포함)
편입도 m: 위 → 1 · G 안 → (k − a)/|G| · 나머지 → 0            (Σm = k)
top_decile_mean = Σ m·label / k
교체비율 = Σ max(0, m_t − m_(t−1)) / k                         → 편입도가 0/1 이면 02A 의 |cur∖prev|/|cur| 와 같다
net = mean − 교체비율 × bp/10^4 × 2                            (기존 cost_drag 식)
전략 성과 = 같은 바스켓의 (mean + KODEX200 수익률) · 같은 교체비율로 기존 산식(equity·CAGR·MDD·Sharpe·IR)
```

- 이 가중 바스켓을 gross · net · 비용 grid · turnover · win rate · 전략 성과 **전체에 일관되게** 쓴다. 민감도 label 블록도 같다.
- 종목코드 순서로 자르는 02A 값은 **민감도 비교값으로만** 병기한다.
- 경계 동점이 없는 날에는 02A 규칙과 값이 정확히 같다. 테스트로 확인한다.
  - 전략 성과는 기존 공개 순수 함수(`equity_curve`·`max_drawdown`·`cagr`·`annualized_volatility`·`annualized_ratio`·
    `cost_scenarios`·`cost_drag`)로 다시 조립한다.
  - 동점 없는 기록에서 `build_strategy_performance` 와 같은 값이 나오는지 테스트한다.
- RF_A 설정은 바꾸지 않는다.

### 2-5. 통계 (Q15)

- 새 모듈이 `circular_block_bootstrap_ci(series, iterations=10000)` 를 **직접** 부른다.
  - 블록 6 = 신호일 6개 = 6개월 · seed 42 · 2.5/97.5 선형보간 percentile
  - 기존 상수 `BOOTSTRAP_ITERATIONS` 는 바꾸지 않는다.
- **paired 차이**: 날짜별 d_t = RF − MOM 이다. IC 와 net25(각 모델 자기 교체비율)를 쓰고, 그 평균에 CI 를 낸다.
  - 점추정(C1·C3)도 같은 날짜 집합의 paired 평균 차이다.
  - 한쪽 값이 None 인 날은 빼고 계속한다. `n_paired` < 146 이면 빠진 날짜·모델·사유를 결과에 기록한다.
  - 개별 CI 하한끼리 빼는 방식은 쓰지 않는다.

### 2-6. 강건성 (설계 §5 · Q8)

- 판정은 PIT 로 한다. CONTROL 은 같은 표로 진단만 한다.
- **연도별**: 모델별 IC·net25 평균과 RF_PRIMARY−MOM 차이를 낸다.
- **3구간**: 2014-06-30 ~ 2018-06-29(49) · 2018-07-31 ~ 2022-07-29(49) · 2022-08-31 ~ 2026-07-31(48).
- **가장 유리한 한 해 제외**: 모든 해 y 에 대해 y 를 뺀 나머지 날짜의 paired 평균 차이를 지표별로 구한다.
  그 **최솟값 > 0** 이어야 한다. 가장 불리해지는 해를 함께 보고한다.
- **2026년 제외**: 보고만 한다.
- **RF 고정 설정 3개 개별**: 각 설정 − MOM 의 IC·net25 paired 평균 차이와 CI(참고)를 낸다.
- **선택 빈도**: A·B·C 가 RF_PRIMARY 로 뽑힌 날 수와 사유 코드 분포를 낸다.
- **부분 구간 값**: 전체 시계열의 날짜별 값을 잘라 쓴다. 구간마다 교체비율을 다시 계산하지 않는다.
- **부분 구간은 방향(평균 부호)만** 판정에 쓴다. CI 는 참고다.
- **None 처리**: 평균이 None 이면 그 조건은 거짓이다(fail-closed).

### 2-7. 판정 (설계 §6 · Q7 확정 · 코드가 PIT 기록으로 계산)

| 조건 | 정의 |
|---|---|
| C1 | IC: RF_PRIMARY − MOM 날짜별 paired 평균 > 0 |
| C2 | IC paired 차이 95% CI 하한 > 0 |
| C3 | net25(부분 가중 바스켓): RF_PRIMARY − MOM paired 평균 > 0 |
| C4 | net25 paired 차이 95% CI 하한 > 0 |
| C5 | 고정 설정 A·B·C 가운데 IC 차이 > 0 **이고** net25 차이 > 0 인 설정 ≥ 2 |
| C6 | leave-one-year-out 최솟값: IC 차이 > 0 이고 net25 차이 > 0 |
| C7 | 3구간 가운데 IC 차이 > 0 이고 net25 차이 > 0 인 구간 ≥ 2 |
| C8 | PIT 에서 우위: C1 ∧ C3. PIT 가 주 평가라 C1~C7 의 반복이다. 설계자 02B 판정 선례와 같이 읽었다(V2 RESULT 판정 §3 원문: "조건 8은 독립적인 추가 증거가 아니라 조건 1~7의 반복이다") |
| C9 | PIT 처음부터 2회 공식 실행 canonical 동일(`compare`) |
| C10 | 누수·입력 변경·사후 설정 변경 0: preflight 전 모델 OK · 봉인·라이브·02A 기준 불변 · 설정 sha `edca7023…` · recipe sha 불변 · 선형 재현 통과 |

**판정 순서**(위에서 처음 맞는 것 · 설계자 확정):

```text
1. INVALID_STOP        선형 재현 실패 · 봉인/라이브/02A 기준 변경 · 누수(preflight) · 비유한 입력 · RF 입력 단언 위반
                       · val_IC 전부 None · S′ 모델 불가 · 자원 상한 · 결정성 실패(C9) · 설정·recipe sha 불일치
2. REJECT_CLOSED       C1 거짓 그리고 C3 거짓            (두 지표 모두 모멘텀 이하)
3. INCONCLUSIVE_CLOSED C1 · C3 중 하나만 거짓            (한 지표만 열위 · V2 §17 · 설계 §6)
4. REJECT_CLOSED       C5 · C6 · C7 중 하나라도 거짓      (특정 기간·설정 의존)
5. INCONCLUSIVE_CLOSED C2 또는 C4 거짓                   (점추정은 좋지만 CI 가 0 포함)
6. PASS                C1~C10 전부 참
```

- **실행 결과물**:
  - PIT 실행의 `result.json` 에는 판정 후보(C9 제외)를 쓴다.
  - PIT 두 실행을 `compare` 한 뒤 `determinism_compare.json` 에 **최종 판정**을 쓴다. 결정성이 실패하면 `INVALID_STOP` 이다.
  - CONTROL 실행은 판정 후보를 쓰지 않는다. CONTROL `compare` 는 진단의 유효 여부만 정한다.
- **'PIT 에서 무너짐'**: PIT 단독 열위로 읽는다. CONTROL 대비 괴리는 `summarize` 의 'PIT−CONTROL 괴리' 진단으로만 표시한다.
- **최종 kill gate**(설계자 확정):

  | PIT 최종 판정 | 다음 |
  |---|---|
  | PASS | CONTROL 진단 뒤 POC4-04 개방 여부를 판단 |
  | REJECT | POC4-04·05 미개방 · Track A 종료 |
  | INCONCLUSIVE | POC4-04·05 미개방 · Track A 종료 |
  | 결정성·자원 INVALID | 결과 판정 금지 · 지정된 1회 재실행만 허용 |

  코드는 판정만 낸다. 개방 결정은 설계자·사용자가 한다.
- **결정성 조항**: V2 §17 의 '결정성 재실행 실패 → Track A 종료'는 POC4-03 §6(INVALID_STOP · 재실행)으로 대체됐다고 읽었다.

### 2-8. INVALID_STOP · 자원 상한 뒤 처리 (설계 §6 · Q11)

- **자원 상한**:
  - 러너가 신호일마다 `perf_counter` 경과 시간과 `ru_maxrss` 를 잰다.
  - 4시간(14,400초) 또는 10×10^9 바이트를 넘으면 그 자리에서 멈추고 `guard_failed`(RESOURCE_LIMIT) → `INVALID_STOP`.
  - 진행 로그와 manifest 에 UTC 시각을 함께 적는다. `caffeinate -i` 로 잠자기를 막는다.
- **1회 초과**: 시스템 부하만 없앤 뒤 같은 설정으로 **한 번만** 다시 돌린다(새 폴더 run3 이후).
- **2회 초과**: 설정을 가볍게 바꾸지 않는다. 중단하고 설계자에게 보고한다.
- **그 밖의 INVALID_STOP**: 계약 결함만 고쳐, 같은 사전 등록 설정(설정 sha · recipe sha)으로 처음부터 다시 돌린다.
  설정·feature·label·평가일은 바꾸지 않는다. 원인과 고친 내용은 결과서에 적는다.
- **폴더**: `new_run_dir` 는 이미 있는 폴더를 거부한다. `guard_failed` 폴더는 compare 가 거부한다.
  결정성 증거는 처음부터 끝까지 돈 두 실행으로만 낸다.

---

## 3. 파일 계획 · 테스트

신규 파일과 책임은 §1-9 표와 같다.
- **기존 코드 파일 수정은 0** 이다. 02A·02B 모듈·러너, `app/krx_sealed_reader.py`, 고정 모듈 3개, `tests/conftest.py`,
  `tests/_live_guard.py` 모두 해당한다.
- 문서 갱신은 별도다: 결과서 · `PROGRAM_TRUTH` §7.1 · `STATE_LATEST`.

| 테스트 파일 | 확인 내용 |
|---|---|
| `test_poc4_03_models.py` | 동결 설정 sha · 입력 정렬·float32·유한성 검사(NaN·inf → 오류) · 순서 고정 예측이 n_jobs 1·4·8 에서 bit 동일 · 선택 = finite 원값 최대 · 정확 동률 A→B→C · 일부 None 제외 · 전부 None → INVALID · 사유 코드 · 선택 함수가 평가 label 을 받지 않음 · 모멘텀 = t 행 `return_20d` · 부호 · 결측 → 점수 없음 |
| `test_poc4_03_eval.py` | **fixture DB 에서 새 선형 기록 == 02A `evaluate_point` 기록**(canonical 텍스트 · 두 arm · 전 날짜) · S·V·t 행 수 = 02A trainer 경계 · S′ = S − (label 끝 ≥ V 시작) · 제외 수 기록 · RF 입력 단언 · 선택용 V 모집단(이름 필터) · 여섯 모델 단면 동일(다르면 멈춤) · NO_MODEL 날 규칙 · 02A 기준 기록이 평가·선택 함수로 넘어가지 않음 · 봉인 밖 DB 접근 시 실패 |
| `test_poc4_03_report.py` | bootstrap 10,000회 · paired 점추정 = 날짜별 차이 평균 · 부분 가중(동점 없으면 02A 값과 같음 · 묶음 가중 · 교체비율 0/1 환원 · 가중치가 label 과 무관) · 전략 성과(동점 없으면 `build_strategy_performance` 와 같음) · 부분 구간은 전체 값을 자름 · leave-one-year-out · None → 거짓 · 판정 순서 표를 사례별로 고정 |
| `test_poc4_03_runner.py` | tmp 봉인 DB + tmp 02A 기준 폴더로 실행 · 선형 재현 불일치 → `guard_failed` · 02A 기준 hash 불일치 → 시작 거부 · 라이브·봉인 변경 → 결과 없음 · 재개 지문 · compare 규칙(재개·같은 폴더·`guard_failed` 거부 · 최종 판정) · 자원 상한 모의 초과 → 멈춤 · 네트워크 0 · 라이브 경로 아래 출력 거부 · 새 폴더만 · 로그에 RF·모멘텀 지표 없음 · CONTROL 은 판정 후보를 쓰지 않음 · `summarize` 는 판정을 바꾸지 않음 |

산출물은 `state/ml/research/poc4_03/{pit,control}_run{1,2}` 에 쓴다(`new_run_dir` · git 추적 밖 · 재실행은 run3 이후).
결과서는 `docs/ai_result/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_RESULT.md` 다.

---

## 4. 설계자 확정 (2026-09-25 · Q1~Q17)

| # | 확정 |
|---|---|
| Q1 | 모멘텀 = t 행 `return_20d` |
| Q2 | 여섯 모델 모두 `normalize_to_display_scores` |
| Q3 | RF 는 S′ 로만 학습 · S+V 재학습 금지 |
| Q4 | V 모든 거래일 IC 평균 · 모집단 = 날짜별 이름 필터 · 7 feature 완전 · 검증 target 있음 (필수 보완 A) |
| Q5 | 반올림 없음 · finite 원값 비교 · 정확 동률 A→B→C · 일부 None 제외 · 전부 None → `INVALID_STOP` (필수 보완 B) |
| Q6 | CONTROL 은 PIT 가 PASS 후보일 때만 · 여섯 모델 전체 (필수 보완 C) |
| Q7 | 한 지표만 열위 → `INCONCLUSIVE_CLOSED` · C5~C7 실패 → `REJECT_CLOSED` · CONTROL 은 진단만 |
| Q8 | 지표별 leave-one-year-out 최솟값 > 0 |
| Q9 | top-decile net 10·50bp · 기존 전략 시나리오 유지 |
| Q10 | arm 별 실행 · PIT 우선 · CONTROL 조건부 |
| Q11 | `perf_counter` 4시간 강제 중단 · UTC 시각 병기 · 같은 설정 재시도 1회만 · 두 번째 초과 → 중단 보고 |
| Q12 | `app/research_run_guard.py` 신규 · POC4-03 에만 적용 |
| Q13 | 경계 동점 부분 가중을 모든 성과 산식에 일관 적용 · 02A 코드 순서 값은 민감도로만 병기 (필수 보완 D) |
| Q14 | 실행한 arm 의 날짜별 기록 canonical 전체 일치(두 arm 합 292건) |
| Q15 | bootstrap 10,000회 · seed 42 · 블록 6 |
| Q16 | RF_C 비율 그대로 · 결과 확인 뒤 변경 금지 |
| Q17 | RF 학습 S 에서 label 끝 ≥ V 시작 행 제외 · 날짜별 제외 수 기록 · 모델 불가 시 `INVALID_STOP` (필수 보완 A) |

설계자 재확인이 필요한 경우는 네 가지다: 새 데이터 소스 · RF 설정 변경 · 성과 확인 뒤 기준 변경 · 4시간 재초과.

---

## 5. 금지 범위 · 중단 조건 대조 (설계 §2 · §7 · §9)

| 항목 | 이 PLAN |
|---|---|
| feature·label·평가일 변경 | 0 — 7개·`future_excess_return_20d`·E2 `forward_excess`·146일 그대로 |
| 결측 보충 | 0 — 가격·명칭은 봉인 `krx_etf_universe_v1` 의 `SealedPanel` 만 · `etf_master`·운영 DB·생존 DB 열기를 `guard_sqlite_paths` 가 막음(테스트 포함) |
| test 결과 기반 설정 선택 | 0 — 설정은 §1-5 에서 동결 · smoke 는 성과 0 · 선택은 t 이전 V 만 |
| XGBoost·LightGBM · 자동 탐색 | 0 |
| 신규 패키지 | 0 — sklearn 1.9.0 은 이미 고정 |
| UI·API·OCI·PUSH · 외부 네트워크 · 라이브 DB | 0 — 테스트로 강제 |
| 기존 POC4-01·02 결과 덮어쓰기 | 0 — 새 폴더 `poc4_03/…` 만 · 02A 기준은 읽기와 hash 대조만 |
| `app/krx_sealed_reader.py` · 02A 모듈 · 586줄 02A 러너 | 수정 0 |
| 자원 | arm 별 실행 · PIT 1회 예상 1.80시간 · perf_counter 4시간 강제 중단 |
| 커밋·push | 0 — 구현 → 검증 뒤 별도 지시 |

---

## 6. 작업 순서

1. 신규 모듈·러너·테스트를 쓴다.
   - 품질: `black`·`flake8`·`py_compile` · focused 테스트
   - 전체 회귀: background · 공식 실행과 겹치지 않게
2. 공식 실행(각각 처음부터 · `caffeinate -i` · 다른 무거운 작업 없이):
   - PIT run1 → PIT run2 → `compare`(최종 판정)
   - PIT 가 PASS 일 때만 CONTROL run1 → CONTROL run2 → `compare` → `summarize`
3. 결과서를 쓰고 `PROGRAM_TRUTH` §7.1 을 갱신한다. 설계자 판정 → 검증자 순서로 넘긴다. 커밋·push 는 그 뒤 별도 지시를 받는다.
