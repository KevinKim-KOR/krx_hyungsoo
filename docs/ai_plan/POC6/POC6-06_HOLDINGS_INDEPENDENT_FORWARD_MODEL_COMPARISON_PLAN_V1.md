# POC6-06 개발 PLAN V1 — 보유 독립 ETF 대상의 전향 ML 비교 · 기록

작성 2026-10-22 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = PLAN 제출(2026-10-22) · 질문 2(§7) → 설계자 PASS(2026-10-22 · Q1 = 판정 §1 문장 · Q2 = (a) · 정정 반영 = §9 · 재제출 없음) → 격리 구현
           → 사용자 승인 묶음 · 실제 연결(2026-10-23) → 검증자 r1 REJECTED(F1 · F2 · F3) · r2 REJECTED(F3 잔여) → 정정 → 검증자 r3 VERIFIED → 설계자 RESULT PASS_TO_DEPLOY(2026-10-23) → OCI 반영 진행(결과서 docs/ai_result/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_RESULT.md §4-5)
DECISION = docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_DECISION_2026-10-22.md
DESIGN   = docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_DESIGN_V1.md
조사     = PC 증거 보관소 · PC 시장 DB(mode=ro) · POC6-03 사본(mode=ro) 읽기 · 코드 읽기 · 외부 조회 0 · 쓰기 0
```

## 0. 한 줄

POC6-05 가 PC 로 가져온 ETF 목록 판 하나에서 §2 규칙으로 고정 24종(cohort_v1)을 골랐다. 장기 가격은 24종 모두 한 번 새로 받아야 한다(기존 보관 사본과 겹침 0). 이후 PC 수동 명령 하나로 다음을 한다.

- PC 사본 확인 → 성숙 결과 연결 → 필요한 월별 학습 → 새 예측 기록 → 비교 보고서
- 네 방법(MEDIAN · RIDGE · HGB · MLP_CPU) = 02 recipe 그대로 · 학습 가중치도 보관

OCI 는 기존 수집 · 보관만 한다.

## 1. 표본 선정 실측 (§11-1 · 학습 · 성과 계산 0 · 보유 파일 미사용)

- **목록 판**: 05 묶음 `20261022T103723Z_5cae0dd9` 의 `etf_list` effective.
  - object `78c5bcd4…df06824` · 목록 해시 `cbbd8259…a17de` · 1,183종
  - 수신 2026-10-22T10:37:26Z · OCI 공개(available_at) 10:37:34Z · PC 수신(copied_at) 11:30:07Z
  - 같은 목록을 뒤 두 묶음이 SKIPPED 로 재사용했다.
- **후보군**: 목록 1,183 중 PC 시장 DB `etf_daily_price` 에 있는 1,176종이 대상이다. 그 가운데 유효 종가(값 있음 · 0 초과) 저장일이 365개 이상인 898종을 후보로 했다.
  - 기준일 = 목록 판의 05 기준 거래일 2026-10-21 이하. PC DB 최신은 2026-10-20 이다.
  - 365일 이상 = 장기 자료 '가능성' 확인일 뿐이다. 가격 일관성 · 252 예제를 보증하지 않는다.
- **선정**: `SHA-256("poc6-06-v1:" + ticker)` 오름차순(동률 ticker 순) 앞 24종.
  - 계산 중 보유 관련 모듈 불러오기 0. seed · 보유 · 수익률 · D20 · 오차 · 관심도 미사용.

| # | ticker | 해시 앞 12자 | PC 저장일 | 이름 |
|---:|---|---|---:|---|
| 1 | 364960 | 0047bd10176b | 1,478 | TIGER BBIG |
| 2 | 381180 | 00a559db8103 | 1,353 | TIGER 미국필라델피아반도체나스닥 |
| 3 | 445690 | 00d8acbfaa8c | 971 | BNK 주주가치액티브 |
| 4 | 122090 | 01fc92b16350 | 3,072 | PLUS 코스피50 |
| 5 | 271050 | 0209b674fc7e | 2,292 | KODEX WTI원유선물인버스(H) |
| 6 | 458030 | 02379e4620fb | 824 | WON 국공채머니마켓액티브 |
| 7 | 447620 | 023b8e5045a7 | 948 | SOL 미국TOP5채권혼합50 |
| 8 | 354500 | 0397d6564875 | 1,583 | ACE 코스닥150 |
| 9 | 114100 | 03bebdca13ee | 3,072 | RISE 국고채3년 |
| 10 | 211900 | 03f3191faada | 2,903 | KODEX 코리아배당성장 |
| 11 | 108450 | 045da1c12ee0 | 3,072 | ACE 삼성그룹섹터가중 |
| 12 | 461950 | 050ae3b36c22 | 801 | KODEX 2차전지핵심소재10 |
| 13 | 203780 | 052a987e2d01 | 2,978 | TIGER 미국나스닥바이오 |
| 14 | 291890 | 05386aa81d09 | 2,102 | KODEX MSCI EM선물(H) |
| 15 | 476260 | 05447cb7397d | 642 | HANARO 반도체핵심공정주도주 |
| 16 | 414780 | 05603dbf85bb | 1,163 | TIGER 차이나과창판STAR50(합성) |
| 17 | 453660 | 059ac06e5fbe | 872 | KODEX 미국S&P500경기소비재 |
| 18 | 282000 | 05d6be54a5ed | 2,192 | RISE 국고채3년선물인버스 |
| 19 | 300640 | 05dd2cf2e2fa | 2,020 | RISE 게임테마 |
| 20 | 488720 | 05f18816fa31 | 533 | WON 종합채권(AA-이상)액티브 |
| 21 | 0015K0 | 0621a99129a1 | 407 | TIGER 미국소비트렌드액티브 |
| 22 | 130730 | 06250fae70dc | 3,072 | KIWOOM 단기자금 |
| 23 | 433220 | 0628b7dd4667 | 1,053 | 에셋플러스 글로벌대장장이액티브 |
| 24 | 494670 | 062c20111925 | 485 | TIGER 조선TOP10 |

- 구현 때 같은 목록 object · 같은 규칙 · 같은 PC DB 읽기(mode=ro)로 `cohort_v1.json` 을 만들고, 위 24종과 같아야 한다(다르면 멈춤). 결과를 보기 전에 고정한다.
- **관찰(질문 아님 · 규칙 그대로 · 판정 §3-1 정정)**: 유형 혼합에 따라 통합 오차 해석에 주의가 필요한 종목이 있다 — 채권 · 단기자금 · 혼합형으로 관찰한 5종(458030 · 130730 · 114100 · 488720 · 447620) · 인버스 2종(271050 · 282000). 이름만으로 하락폭 · 저위험을 단정하지 않는다. 유형으로 거르지 않고 사전 고정 보조 표(§9-3)로 나눠 본다.

## 2. 초기 장기 자료 · 학습 예제 수 (§11-2)

- **재사용**: 기존 보관 장기 창 = POC6-03 사본(26종). 선정 24종과 겹침 **0** → 재사용 0 · **추가 요청 24**.
- **추가 조회안**(실제 조회는 승인 뒤):
  - POC6-03 과 같은 FDR → 네이버 fchart 경로(`app/price_basis_check/fetch.py` 의 조회 · 저장 방식)로 종목당 1회 · 최대 24 요청 · 재시도 없음 · 요청 20초.
  - 응답 = 전체 이력(최대 6,000봉) · 진행 중(오늘 KST 이상) 봉 제외.
  - 저장 = `state/ml/research/poc6_06/bootstrap/<시각>_<id>/`(새 폴더 · 라이브 DB 쓰기 0).
- **학습 예제 수를 세는 경로**(구조만 · 성과 계산 없음):
  - 연구 축 = 05 가 보관한 KOSPI 저장일 목록 object(OCI 판 · 3,072일 · 날짜 축 판 고정).
  - 종목마다 06 `prices.AxisSeries`(허용 가격 · 연결 끊김 · 축 결측 사유 재사용)로 한 수신 판의 종가를 축에 맞춘다.
  - 위치 t 가 `window_ok(t-60, t+20)` 이고 목표 끝(t+20)이 초기 학습 경계(첫 예측 기준일 D) 보다 이르면 BOOTSTRAP_RETROSPECTIVE 예제 1행으로 센다.
  - 252 이상 = `initial_trainable`. 미달 = DATA_SHORT(분모 유지 · 교체 없음).
- **적격성은 받은 판에서만 센다**(판정 §5): PC 저장일(최소 407 · 0015K0)은 적격성 보장이 아니다. 반환 창 · 축 · 결측 · 연결 · 엄격한 목표 종료 경계로 실제 예제 수를 센다. 252 미달과 가격 기준 실패는 사유를 나눠 적는다.
- 오래된 운영 가격 · 05 120일 창 · KRX 무조정 가격을 이어 붙이거나 대체값으로 쓰지 않는다.

## 3. 재사용 접점 (§11-3 · 기존 공식 코드 동작 변경 0)

| 필요 | 재사용(읽기 · 호출만) |
|---|---|
| feature 5 · D20 | `app/reentry_review/model.features_at` · `target_at` · `FEATURE_NAMES` · `LB=60` · `H=20` |
| 축 · 가격 검사 | `app/reentry_review/prices.research_axis` · `AxisSeries`(window_ok · window_reasons) · `link_break` |
| MEDIAN | `model.median`(짝수 = 가운데 두 값 평균) |
| RIDGE | `model.fit_predict` 와 같은 `StandardScaler → Ridge(alpha=1, svd, intercept)`. 계수 · 변환값을 JSON 으로 남기기 위해 같은 설정을 새 모듈에서 fit 한다(수치 동일 시험) |
| HGB | `app/d20_pooled/study.HGB_PARAMS` · `fit_hgb`(1/n_d 가중) |
| MLP_CPU | `app/d20_pooled/mlp` 의 `standardize_params` · `apply_standardize` · `deterministic` · `new_model` · `to_tensors` · `run_epochs` · `build_net`(device="cpu"). 학습된 net 을 남기는 얇은 함수만 새로 둔다(기존 `train_predict` 그대로) |
| 초기 조회 | `app/price_basis_check/fetch` 의 조회 · 진행 중 봉 · 저장 방식(대상 = cohort 목록) |
| 날짜 · 마감 | `trading_day_lag.expected_previous_trading_day` · `is_trading_day` · `three_push_runtime.ledger_outcome.CLOSE_CUTOFF`("15:30") |
| 05 입력 · 보관 | `ml_evidence.store`(list_runs · read_jsonl_gz · parse_iso · object_ok) · `export.select` 의 공개 시각 규칙 · `transfer`(pull · upload) |

- 02 · 04 · 06 공식 파일 · 실행 경로는 바꾸지 않는다.
- 05 쪽 변경은 §6 의 허용 목록 확장뿐이다.

## 4. CPU MLP · 모델 저장 · 월별 규칙 · 자원 (§11-4)

- **CPU MLP**: PC = macOS arm64 · CPU 8 · 메모리 16GB · torch 2.13.0 · sklearn 1.9.0 · joblib 1.5.3 · numpy 2.4.6. 02 `mlp` 가 `device="cpu"` 를 이미 지원한다. 새 설치 · GPU 묶음 없음. 실행 불가면 방법별 `NOT_RUN_ENV`.
- **저장 · 복원**(모두 내가 만들고 해시를 기록한 파일만 읽음):

| 방법 | 저장 | 복원 확인 |
|---|---|---|
| MEDIAN | JSON(종목별 중앙값 · 예제 수) | 같은 입력의 예측이 학습 직후 값과 정확히 같음 |
| RIDGE | JSON(종목별 scaler mean_ · scale_ · coef_ · intercept_) | numpy 식 예측 = sklearn 예측(차 ≤ 1e-12) |
| HGB | joblib(pickle) 파일 + 라이브러리 판 기록 | 판이 다르면 읽지 않음(`ENV_MISMATCH`) · 같은 입력 예측 일치 |
| MLP_CPU | `torch.save(state_dict)` + 표준화 mean · std JSON | `torch.load(weights_only=True)` · 같은 입력 예측 일치 |

- **월별 학습**: 그 달 첫 유효 run 에서 새 LOGGED_FORWARD 예제가 있을 때만 한 번 한다(없으면 `NO_NEW_TRAINING_EXAMPLES` · 학습 기회는 남음).
  - 예제 = BOOTSTRAP + (feature 입력 · 성숙 목표가 모두 확정된) LOGGED_FORWARD. (ticker, 기준일) 중복 없음.
  - 목표 끝 < 그 회차 첫 예측 기준일 D · 가용 시각 ≤ training_started_at.
  - X · y · 가중치 · 예제 참조 해시가 같으면 다시 fit 하지 않는다. model_version = recipe + cohort + 학습 예제 해시 + 환경.
- **자원 추정**: 초기 예제 최대 약 38,000행(24종 저장일 합 39,888 − 종목당 약 80).
  - HGB · MLP(200 epoch · 5 → 64 → 32 → 1) · Ridge 24 · 중앙값 24 모두 PC CPU 에서 수 초 ~ 수십 초로 본다(첫 실행에서 실측).
  - 월 1회 모델 묶음 = 파일 약 6개(HGB 수백 KB · MLP 수십 KB · JSON 수 KB).
  - 매일 예측 기록 = 24종 × 4방법 JSON 하나(수십 KB).

## 5. 전향 경계 · 성숙 · CLI · 실패 상태 (§11-5)

- **기준일 D**: 05 보관 KOSPI 저장일 · 운영 축으로 확인한 최근 완료 거래일.
  - 각 ETF 입력 = 05 일일 묶음의 네이버 120일 창 한 판(D 까지 · 61 축 날짜).
  - 05 기준일이 D 인 묶음의 창만 쓴다. 오래된 종목을 자기 최신일로 옮기지 않는다.
- **시각**: 입력의 OCI `published_at`(available_at) · PC `copied_at_pc` ≤ input_cutoff ≤ 계산 시작. training_completed_at ≤ 예측 시작. 공개 = 실제 공개 순간(05 `publish_run` 방식).
- **마감**: 공개가 D 다음 거래일(운영 축)의 15:30 KST(`CLOSE_CUTOFF`) 보다 이르면 FORWARD_RESEARCH 주 기록이다.
  - 아니면 `SKIPPED_TOO_LATE` 이고, 별도 진단 예측(`DIAGNOSTIC` · 성과 집계 제외)을 남긴다.
  - 다음 거래일을 확정할 수 없으면 `PENDING_CALENDAR`. 과거 시각 입력 · 우회 인자는 없다.
- **실제 쓰는 시간대(관찰 · 판정 §4 정정)**: D 의 봉은 D+1 09:40 OCI 수집에서 들어온다. 약 09:50 은 예상일 뿐이며, 실제 수집 완료 · 공개 · PC 수신 뒤이고 D 다음 거래일 15:30 전에 정상 공개한 기록만 주 기록이다. 금요일 D 는 다음 거래일 15:30 이 상한이며, 주말 실행도 실제로 금요일 D 창을 확보한 뒤에만 가능하다. 그 밖은 SKIPPED_TOO_LATE + 진단(성과 집계 · LOGGED_FORWARD 학습 예제 제외).
- **중복**: (protocol · cohort · ticker · D) 의 최초 정상 공개 입력 = 주 기록. 재실행은 기존 기록을 돌려준다. 다른 자료 판 재계산 = 부가 기록. 최초 입력에서 실패한 방법의 재시도는 첫 목표 종가 전 · 같은 입력 · 학습 판일 때만 연결한다.
- **성숙**(§8):
  - 운영 축에서 D+20 이 지난 뒤, 05 정상 묶음 중 D ~ D+20 21개 종가가 한 창에 모두 있는 가장 이른 available_at 판(동률 run_id)으로 목표를 계산 · 고정한다.
  - 상태 = `PENDING_NOT_DUE` · `PENDING_CALENDAR` · `DUE_DATA_MISSING` · `DATA_CHECK_REQUIRED`. 기준 종가가 예측 때와 다르면 둘 다 남긴다.
  - 고정 범위로 쓰지 않는다(판정 §4-5). 120일은 요청 달력 범위이며, 실제 창에 D 와 다음 20거래일의 21개 종가가 함께 있는지 검사한다.
- **CLI** `scripts/run_forward_compare.py`:
  - `select-cohort`: 고정 · 확인.
  - `bootstrap-fetch`: 승인 뒤 1회.
  - `run [--pull] [--archive]`: 확인 → 성숙 → 월별 학습 → 예측 → 보고.
  - `report`: 파일 읽기만.
  - `archive`: PC_ONLY 산출물 올리기.
  - `--pull` · `--archive` 를 주지 않으면 SSH 0.
- **실패 상태**: 방법별 `OK` · `FAILED`(사유) · `NOT_RUN_ENV` · `DATA_SHORT`. 다른 방법 값 복사 · 0 대입 · 이전 판 조용히 대체 없음.

## 6. 변경 범위 · 시험 · 승인 묶음 (§11-6)

**새 파일**(각 400줄 미만 목표):

- `app/forward_compare/__init__.py` · `cohort.py` · `bootstrap.py` · `examples.py` · `models.py` · `forward.py` · `mature.py` · `report.py`
- `scripts/run_forward_compare.py`
- 시험 2파일

**수정**:

- `app/ml_evidence/store.py`: KINDS 에 `FORWARD_RESEARCH_ARTIFACTS`.
- `app/ml_evidence/research.py` · `transfer.py`: 받기 허용을 POC6-06 형식 · 상대 경로(`state/ml/research/poc6_06/…` 의 cohort · bootstrap · examples · models · predictions · targets · reports) · 형식 검사로만 넓힘.
  - 02 · 03 · 04 지정 파일 계약은 그대로 둔다. OCI 는 모델 파일을 bytes 로만 보관한다(load · import 0).
- `.gitignore` 변경 없음(`state/ml/research/` 이미 제외).
- 기반 문서 3곳: 판정의 '06 한정 예외' 문장을 그대로 넣는다(Q1).

**시험**(tmp · 가짜 가격 · 가짜 시계):

- 선정 = 보유 · 평가 바꿔도 같은 24종
- feature · 목표 = 06 함수와 같음
- 미래 · 늦은 입력 · 미성숙 목표 누출 0
- 마감 경계(직전 · 직후 · 주말 · 축 미확정)
- 같은 날 재실행 · 부가 기록
- 성숙 상태 4종 · 한 창 규칙 · 정정 판 보존
- 월별 학습(새 예제 · 같은 해시 무학습 · 달 경계)
- 모델 저장 · 복원 일치 · ENV_MISMATCH
- 방법별 실패 분리
- 같은 행 비교 분모 · null MAE
- 05 허용 목록(허용 경로만 · 02 · 03 · 04 계약 유지)

변이 · 관련 회귀 · 마지막 전체 회귀 1회를 한다.

**실제 확인(판정 · 승인 뒤)**:

1. 초기 조회 24종
2. 초기 학습 · 저장 · 복원
3. 첫 run(시간대 안이면 주 기록 · 밖이면 SKIPPED_TOO_LATE + 진단)
4. archive · 양쪽 복원

**승인 묶음(한 번에)**:

1. PC 추가 외부 조회: FDR 네이버 fchart 24 요청 · 종목당 1회 · 재시도 없음 · 새 연구 폴더
2. 커밋 · push · OCI pull(받기 허용 확장 배포 · 평일 08:05 ~ 15:45 회피)
3. POC6-06 산출물 OCI 업로드(같은 형식 · 경로의 이후 추가는 재승인 없음)
4. 종료 기록 커밋 · push

## 7. 질문 (실제 충돌만)

- **Q1. 기반 문서 '06 한정 예외' 문장**: 설계 §0 은 PLAN 판정 뒤 관련 기반 문서에 범위를 기록하라고 한다. 05 처럼 판정문에 그대로 넣을 문장을 주시면 `PROJECT_ORIGIN_INTENT` · `KILL_SWITCHES` · `ASSUMPTIONS` 의 관련 곳에 날짜 · 출처와 함께 원문 그대로 넣겠다. 개발자가 문장을 만들지 않는다.
- **Q2. 05 묶음의 '기준일 D 창' 선택 규칙**: 같은 기준일 D 를 담은 05 묶음이 여럿일 수 있다(예: 오늘처럼 20종목 → 전체 → 수급 재실행). 그중 '정상 공개 + input_cutoff 이하 + 그 종목 창이 OK' 인 것 중 가장 이른 published_at 판을 주 입력으로 고정하는 안을 제안한다(동률 run_id). 더 늦은 판은 부가 기록이다. 설계 §7 '최초 정상 공개 입력'과 같은 뜻으로 보지만 종목마다 판이 다를 수 있어 확인한다.
  - (a) **권장**: 종목마다 가장 이른 정상 판
  - (b) 묶음 단위로 하나의 판(그 묶음에 없는 종목은 그날 입력 없음)

## 8. 하지 않는 것

새 모델 · 새 feature · 튜닝 · 종목 추천 · 자동 매매 · PUSH · PARAM · seed · 화면 · API · OCI 학습 · 예측 · cron 변경 · torch · sklearn OCI 설치 · 05 수집 범위 변경 · 과거 02 · 03 · 04 재실행 · 전 ETF 장기 백필 · 별도 handoff.

## 9. 설계자 판정 반영 (2026-10-22 · 판정 원문 `docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_DECISION_2026-10-22.md`)

판정 = **PASS**(재제출 없음). 아래가 위 본문보다 우선한다.

### 9-1. 질문 판정

- **Q1**: 판정 §1 문단을 `PROJECT_ORIGIN_INTENT`(POC5-06 · 08 예외 다음) · `ASSUMPTIONS`(Q6 별도 연구 계약) · `KILL_SWITCHES`(KS-11 05 예외 다음)에 날짜 · 출처와 함께 원문 그대로 넣었다(2026-10-22 · 기존 제한 · 과거 판정 보존).
- **Q2 (a)**: 종목마다 가장 이른 유효 입력 판(판정 §2 규칙 1 ~ 6).
  - 회차의 D · input_cutoff 를 먼저 고정한다.
  - 정상 공개 manifest · 참조 파일 무결성 · available_at · copied_at_pc ≤ cutoff 를 검사한다.
  - 그 종목의 한 창이 D · feature 날짜 · 가격 · 연결 검사를 통과하는 후보만 쓴다(상태 글자 OK 만으로 판단하지 않음).
  - 원래 공개 시각이 가장 이른 판(동률 run_id)을 고른다. 네 방법은 같은 입력을 쓴다.
  - PARTIAL 의 유효 종목은 쓴다. FAILED · 미완료 · 손상은 쓰지 않는다.
  - SKIPPED · effective 참조는 원본의 가용 시각 · 참조를 보존한다(수급만 재실행한 시각을 가격 수신 시각으로 쓰지 않음).
  - 선택 원본 run · object · 창 · inventory · cutoff 를 남긴다. 주 기록 고정 뒤 새 판은 부가 기록이다. 종목 안에서 다른 판을 이어 붙이지 않는다.

### 9-2. 표본 · 식별자

- 24종 그대로 유지한다(유형으로 다시 뽑지 않음).
- `0015K0` 등 영숫자 6자 식별자를 보존한다(정수 변환 · 문자 제거 · 대체 없음). 조회 · 검사 · 파일명 경로가 보존하는지 시험한다. 원천 미지원 · 실패는 사유와 미확보로 남긴다.
- cohort 고정 때 목록 object · 후보군 ticker · 저장일 수 요약 · 선정 해시 · 규칙 · 시각을 저장한다(PC DB 전체 복사 없음). 그 요약으로 24종이 재현되는지 확인하고, 다르면 원인 보고 · 자동 재선정 없음. 고정 뒤 라이브 DB 로 다시 순위를 매기지 않는다.

### 9-3. 사전 고정 보조 표

주 표는 24종 전체 같은 행 비교로 둔다. 종목별 결과에 더해 아래 보조 표를 둔다(각 표에 비교 가능 날짜 · 종목 · 행 수 · 누락). 보조 표로 주 표본을 바꾸거나 유리한 군만 통과로 판정하지 않는다.

| 보조 묶음 | ticker |
|---|---|
| 채권 · 단기자금 · 혼합형으로 관찰한 5종 | 458030 · 130730 · 114100 · 488720 · 447620 |
| 인버스 2종 | 271050 · 282000 |
| 나머지 17종 | 위 7종을 뺀 고정 목록(순수 주식형 · 투자 적격이라는 뜻 아님) |

### 9-4. 시각 · 성숙 · 학습

- 09:50 은 예상이다. 실제 공개 시각 < D 다음 거래일 15:30 만 주 기록이다. 늦거나 일부 종목 미수신은 지연 · 누락으로 남긴다.
- SKIPPED_TOO_LATE 진단 예측은 성과 집계 · LOGGED_FORWARD 학습 예제에서 뺀다. 늦은 실행에서 초기 모델을 만들어도 학습 경계 · 실제 시각을 남기고, 이후 전향 기록의 학습 판을 소급하지 않는다.
- 성숙 = 한국 연구 축의 다음 20거래일 종가가 모두 확정된 뒤. 축 불확실 = PENDING_CALENDAR. 한 창에 21개 종가가 있는지 실제로 검사한다.
- 월별 재학습 = 새 달 · 유효 신규 예제가 있을 때 한 번(같은 달 재시도 · 재실행에 중복 fit 없음 · 실패 방법 복구와 정상 방법 불필요 재학습 구분). 같은 X · y · 가중치 · 예제 해시면 fit 하지 않는다.
- 자원(38,000행 · 수 초 ~ 수십 초)은 추정이다. 실제 반환 범위 · 학습 행 수 · 시간 · 최대 메모리 · 산출물 크기를 첫 실행에서 기록한다(별도 benchmark 없음).

### 9-5. 05 허용 확장 · 시험 · 승인

- 05 받기 허용은 정규화한 상대 경로 · schema · 참조 · hash 를 함께 확인한다(문자열 접두어만으로 판정하지 않음). 02 · 03 · 04 계약 · 05 수집 그대로.
- 시험 추가: 입력 판 선택 · PARTIAL · effective 참조 · 영숫자 ticker · 고정 cohort 재사용 · 늦은 진단의 학습 제외.
- 승인(판정 §7): 구현 · 명령 · 허용 경로 준비 뒤 한 번에 묶어 받는다(초기 24종 조회 · 커밋 · push · OCI 받기 도구 배포 · POC6-06 산출물 보관 · 종료 기록). 이 판정은 승인이 아니다.
- 순서 = 초기 자료 → 초기 학습 · 저장 · 복원 → 첫 run → 검증자 → 설계자 RESULT → 반영 · 업로드 · 복원 → 종료. 05 첫 정기 실행 · R0 확인은 별도다.
