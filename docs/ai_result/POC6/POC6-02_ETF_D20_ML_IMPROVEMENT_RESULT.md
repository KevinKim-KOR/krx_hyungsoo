# POC6-02 개발 결과서 — ETF_D20_ML_IMPROVEMENT (ML 고도화: ETF D20 추정 개선 검증)

작성 2026-10-21 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_CPU_PARTIAL_GPU_PENDING — 구현 완료(2026-10-21) → 독립 검토 1회 반영(§4 · 13건) → 변이 45종 모두 잡힘(§9)
                → 맥북 공식 CPU 실행 1회(2026-10-21 10:41 · COMPLETED · 완료 범위 CPU_PARTIAL_GPU_PENDING · §8)
                → 검증자 r1(CPU 선행) REJECTED(2026-10-21 · §11 · snapshot 날짜를 해석하지 않은 P2)
                → 개발자 정정(2026-10-21 · §4-5 · 같은 종류 세 층 · 공식 결과 · 묶음 불변 확인)
                → 검증자 r2(CPU 선행) REJECTED(2026-10-21 · §12 · 취합이 행 종목코드 손상을 놓친 P2 · r1 날짜 결함 CLOSED)
                → 개발자 정정(2026-10-21 · §4-6 · 칸별 대조 → 잠긴 입력에서 CPU 보고서 전체 재계산 비교) → 검증자 r3(CPU 선행) VERIFIED(2026-10-21 · §13 · r1/r2 P2 CLOSED)
                → RTX PC GPU 실행 대기(사용자 · §7) → 취합 → 검증자(GPU 부분) → 설계자 RESULT 판정
STEP_ID       = POC6-02 ML 고도화: ETF D20 추정 개선 검증(공동 학습 HGB · CUDA MLP 대 기존 두 기준)
DESIGN        = docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_DESIGN_V1.md(개정 2)
DECISION      = docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md(PASS_TO_IMPLEMENT_WITH_CORRECTIONS)
PLAN          = docs/ai_plan/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_V1.md(§9 판정 반영)
BASE_COMMIT   = e525dc37 (POC6-01 종료)
OFFICIAL_RUN  = state/ml/research/poc6_02/20261021T104103_129a89b0/ (gitignored · 이 맥북)
GPU_BUNDLE    = state/ml/research/poc6_02/20261021T104103_129a89b0/gpu_bundle.zip
SCOPE         = PC 수동 연구 CLI 하나 + 연구 모듈(app/d20_pooled) + RTX PC 실행 묶음 · 화면 · API · OCI · PUSH · PARAM 변경 없음
CHECKS        = §9
VERIFIER_CPU  = r3 VERIFIED(2026-10-21 · CPU 구현·공식 결과·RTX 묶음 준비 범위 한정 · r1/r2 P2 CLOSED · §13 · GPU 실제 실행 미완료)
```

## 0. 요약

- **무엇**: 현재 보유 ETF 의 PC 저장 종가로 D20(다음 20거래일 최저 종가 변화)을 추정한다. 네 방법을 같은 ETF × 시험 날짜 · 같은 정답으로 비교한다.
  - MEDIAN · RIDGE_EXISTING: ETF 별 · 06 그대로.
  - POOLED_HGB: 맥북 CPU · 적격 ETF 공동 학습.
  - POOLED_GPU_MLP: RTX PC CUDA · 같은 공동 학습 표본.
- **맥북 공식 CPU 결과**(기준일 T = 2026-10-19 · 적격 4종 · 3구간 × 63일 · 시험 756행 / 189날짜):
  - 날짜 균형 MAE: MEDIAN 6.9662 · RIDGE_EXISTING 6.8702 · **POOLED_HGB 6.2666 %p**.
  - **POOLED_HGB = RESEARCH_PROMISING**. 대 MEDIAN 10.04% 개선 · 3구간 모두 우위 / 대 RIDGE 8.79% 개선 · 3구간 모두 우위. 경계 근처 없음.
  - **POOLED_GPU_MLP = GPU_NOT_RUN**(RTX PC 실행 결과 취합 전). **CPU · GPU 비교 전체 완료가 아니다**(설계 §5-1 · 판정 §5-4).
- **범위 한정**: 결과는 적격 4종(367760 · 381170 · 395160 · 442580)에 한정한다.
  - 보유 ETF 26종 중 22종이 제외됐다: 상장 기간 부족 14종 · 가격 경계로 시험 날짜 부족 8종.
  - 시장 전체 · 보유 26종의 개선 입증이 아니다. 겹치는 20일 목표라 756행이 756개의 독립 사례가 아니다.
- **운영 아님**: 연구 유망 ≠ 투자 유효성 · 운영 채택(`ML_OPERATION_PROMOTION=NOT_APPROVED` · `CURRENT_DEPLOYABLE_ML_MODEL=none`). 매수/매도 지시가 아니다.
- **다음**: CPU 선행 검증 r3 VERIFIED(§13) · 사용자가 RTX PC 에서 묶음을 한 번 실행한다(§7 · 묶음 경로 그대로) → 맥북 `merge` → 이 결과서의 §0 · §8 · §9 를 GPU 결과로 교체 → 검증자(GPU 부분).

## 1. 처리한 요구사항

| # | 요구(설계 개정 2 · PLAN 판정) | 상태 | 근거 |
|---:|---|---|---|
| 1 | 06 재사용 — 목표 · feature 5 · Ridge · 연구 축 · 가격 경계 · 중앙값(공개 접점 `median` 만 추가) | DONE | `study.py` 가 `m06.target_at` · `features_at` · `fit_predict` · `median` · `prices.AxisSeries` 를 그대로 호출 · 단일 ETF 06 재현 시험 |
| 2 | 한 번 읽기 snapshot · `mode=ro` · 개인 값 없음 · T = KOSPI 저장 최신일 · 연결 닫은 뒤 계산 · 입력 손상 = CHECK_REQUIRED | DONE | `snapshot.py :: build_snapshot` · `snapshot_problem`(실제 해석 · §4-5) · 개인 값 부재 · digest 불변 시험 · 손상 29종 세 층 시험 |
| 3 | 네 방법 고정 설정 · HGB 11개 고정 + 나머지 기본값 기록 · MLP 사양 | DONE | `RECIPE` · `recipe_resolved.hgb_get_params`(§8-6) · `mlp.SPEC` |
| 4 | 공동 학습 가중치 1/n_d · MLP 날짜 균형 가중 표준화(상수 열 0) · 예측 [-1, 0] · 날짜 균형 MAE | DONE | 가중치 합 = 날짜당 1 시험 · 표준화 시험 · clip 시험 |
| 5 | 3구간(anchor = T-20 · 189 = 3 × 63) · 학습 정답 끝 < 구간 시작 · 적격(학습 ≥ 252 · 시험 날짜 ≥ 42 · ETF 별) · 최소 4종(최초 5종 · 변경 이유 보존) · DATA_SHORT | DONE | §8-3 · 누수 불변 시험 · 적격 시험 |
| 6 | 판정 = 두 기준 각각 세 조건 · 기준 0 = REJECT · 반올림 전 · 경계 근처 표시만 | DONE | 경계 parametrize 시험 · §8-4 |
| 7 | 보조 보고(D20 ≤ -8% 행 오차 · 위험 과소 추정 · ETF별 개선/악화) | DONE | §8-5 |
| 8 | CPU 1스레드 · 절반 · 전체 실측 | DONE | §8-6 |
| 9 | GPU microbatch 예비 측정 · 같은 MLP CPU/CUDA 비교 · 재현 ≤ 1e-6 · 결정적 · TF32 끔 | PARTIAL | 코드 · 맥북 CPU 시험 완료. **실제 CUDA 실행은 RTX PC 대기** |
| 10 | RTX PC 작은 묶음(저장소 · DB · 키 · 인터넷 불필요 · CUDA 없으면 GPU_NOT_RUN · 설치 범위 안내) | DONE | `gpu_bundle/` · 맥북에서 실제 묶음 실행 = GPU_NOT_RUN(§9-6) |
| 11 | 취합 — study ID · 입력/recipe/묶음 digest · 구간 · 행 ID 완전 일치 · 누락 · 중복 · 다른 실험 거절 | DONE | 거절 시험(GPU 결과 손상 13종 + CPU 폴더 손상 18종 + digest 까지 맞춘 다시 만든 묶음 + 맥북 묶음 코드 바뀜 + smoke 폴더) · 실제 묶음 사본 취합(§9-6). 실제 GPU 결과 취합은 대기 |
| 12 | 상태 구분(DATA_SHORT · CHECK_REQUIRED · RUN_FAILED · GPU_NOT_RUN) | DONE | snapshot 문제 · 파일 손상 · 실행기 실패 경로 시험 |
| 13 | 결과 폴더 · 원자 쓰기 · 출력 실패 = 실패 · CPU 보고서 덮지 않음 | DONE | 출력 실패 시험 · 취합 쓰기 실패 시험 |
| 14 | 읽기 전용 · 외부 호출 0 · 라이브 불변 · 기존 연구 산출물 불변 | DONE | 네트워크 차단 시험 · 공식 실행 전후 라이브 파일 해시 같음(§9-5) |
| 15 | 공식 실행 1회 · smoke | DONE(CPU) | §8 · smoke 는 구현 중 임시 폴더 |
| 16 | 조건부 아이디어 3건 백로그 등재(설계 §12) | DONE | `BACKLOG.md` #63 · #64 · #65 · 조건부 44 · 합계 65 |
| 17 | 백로그 ML 4건 대조 | DONE | PLAN §6(이번 목표로 해결되지 않음 · 완료 선언 없음) |
| 18 | RESULT — 4종 한정 · 제외 22종 · 가격 경계 · 장비/버전 · 자원 · 판정 이유 · 부분 완료 명시 | DONE(CPU) | 이 문서 §8 · GPU 부분은 취합 뒤 교체 |
| 19 | 독립 검토 1회 · 의미 있는 변이 · 관련 검사 · 전체 회귀 1회 | DONE | §4 · §9 |
| 20 | PROGRAM_TRUTH · STATE 갱신 | DONE | §2 |

**전체 = PARTIAL**: 9 · 11 의 실제 CUDA 실행 · 취합이 남았다(사용자 RTX PC 실행 · §7).

## 2. 변경된 파일 목록

| 파일 | 구분 | 내용 |
|---|---|---|
| `app/d20_pooled/__init__.py` | 신규 | 패키지 설명 |
| `app/d20_pooled/snapshot.py` | 신규 | 보유 ticker · 시장 DB 한 번 읽기 · `--snapshot` 파일 형식 검사 |
| `app/d20_pooled/study.py` | 신규 | 표본 · 구간 · 적격 · 세 CPU 방법 · 지표 · 판정 · 보조 진단 · GPU 입력 · 취합 |
| `app/d20_pooled/mlp.py` | 신규 | MLP 학습 본문(맥북 시험 · RTX PC 공용 · torch 는 함수 안에서만) |
| `app/d20_pooled/gpu_runner.py` | 신규 | RTX PC 실행기(torch + 표준 라이브러리만) |
| `app/d20_pooled/env.py` | 신규 | 환경 · 자원 측정 |
| `app/d20_pooled/report.py` | 신규 | 보고서 · 결과 폴더 · 묶음 · 취합 저장 |
| `app/d20_pooled/runner.py` | 신규 | `run` · `merge` 본문 |
| `scripts/run_d20_pooled_research.py` | 신규 | CLI 진입점 |
| `tests/test_poc6_02_d20_pooled.py` | 신규 | 시험(개수는 §9-2 실측) |
| `app/reentry_review/model.py` | 수정 | 공개 이름 `median = _median` 한 줄(+ 주석) · 동작 같음 |
| `docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_DESIGN_V1.md` | 신규 | 설계 개정 2 원문 |
| `docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md` | 신규 | PLAN 판정 원문 |
| `docs/ai_plan/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_V1.md` | 신규 | 개발 PLAN(§9 판정 반영 · 문구 좁힘 1곳) |
| `docs/ai_result/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_RESULT.md` | 신규 | 이 결과서 |
| `docs/backlog/BACKLOG.md` | 수정 | 조건부 #63 · #64 · #65 등재 · 합계 갱신 |
| `docs/PROGRAM_TRUTH.md` | 수정 | 최종 반영 · §4 · §7.2 · §11 · §12 · 부록 A |
| `docs/STATE_LATEST.md` | 수정 | 최종 업데이트 · POC6 상태 칸 |
| `docs/ai_result/POC6/POC6_DESIGNER_CARRYOVER_FROM_0726_MASTER_HANDOFF_2026-10-21.md` | 신규 | 앞 작업(7-26 문서 설계자 인계 메모 · 사용자 지시 2026-10-21) — 이번 커밋에 함께 |

- 제외: `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(사용자 보존 파일 · stage 하지 않음).
- 연구 산출물 `state/ml/research/poc6_02/` 는 gitignored(`.gitignore:233 state/ml/research/`).

## 3. 신규 추가된 의존성

없음.

- `threadpoolctl`(3.6.0)을 HGB 스레드 제한에 직접 import 한다. scikit-learn 1.9.0 의 필수 하위 의존성으로 이미 설치돼 있고, `requirements.txt` 에 추가하지 않았다(§6).
- torch(2.13.0 · 맥북 CPU 판)는 기존 `requirements.txt:24` 그대로다.

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 구현 판단(PLAN 범위 안)

- `app/reentry_review/model.py`: `median = _median` 공개 이름 한 줄(PLAN §1 · 06 계산 불변).
- **완료 범위 칸 `completion`**: 판정 §5-4 '부분 완료 명시'를 보고서 최상위에 둔다.
  - 값: `CPU_PARTIAL_GPU_PENDING`(CPU 단계) · `FULL`(GPU OK 취합) · `PARTIAL_GPU_NOT_RUN` · `PARTIAL_GPU_CHECK_REQUIRED` · `PARTIAL_GPU_RUN_FAILED`.
  - DATA_SHORT · SMOKE · CHECK_REQUIRED 는 그 상태 그대로다.
- **취합 저장 위치**: PLAN 에는 `report_with_gpu.*` 를 같은 폴더에 쓴다고 적었다. 독립 검토 지적(§4-2 B)으로 하위 폴더로 바꿨다. 파일 이름은 같다.
  - GPU OK = `gpu_merged/`(한 번만).
  - GPU OK 아님 = `gpu_attempts/<시각>_<상태>_<id>/`. 부분 완료 기록이며, 뒤의 OK 취합을 막지 않는다.

### 4-2. 독립 검토 1회 반영(13건 · 모두 정정 · 미룬 것 없음)

| | 지적 | 정정 |
|---|---|---|
| A | (높음) Windows 실행 파일이 실패하면 `py -3` 로 한 번 더 실행해 결과를 덮을 수 있음 | 인터프리터를 먼저 하나 고르고 실행기는 한 번만(`set "PY=py -3"` → `where python` 이면 `python` → `%PY% gpu_runner.py`) |
| B | (중간) GPU_NOT_RUN 취합이 최종 파일을 만들어 뒤의 OK 취합을 막음 · 최상위가 COMPLETED 로만 보임 | §4-1 저장 위치 · `completion` |
| C | (중간/낮음) HGB 나머지 기본값 미기록 | `recipe_resolved.hgb_get_params`(설치 판 `get_params()` 전체) |
| D | (낮음) `--snapshot` 손상 · 칸 누락이 RUN_FAILED | `load_snapshot` 형식 검사 → CHECK_REQUIRED(rc 2) |
| E | (낮음) 가격 표 없음 · 보유 파일 없음이 DATA_SHORT | 둘 다 CHECK_REQUIRED. 보유 파일은 있는데 ETF 가 없을 때만 DATA_SHORT(§6) |
| F | (낮음) PC 실행기: 입력 파일 못 읽음 = 결과 파일 없이 종료 · 예측 NaN 통과 · 전부 OOM 이면 microbatch 1 로 진행 | 입력 읽기를 보호 구간 안으로(CHECK_REQUIRED) · 유한값 확인(RUN_FAILED) · 전부 OOM = RUN_FAILED |
| G | (낮음) 묶음 digest 가 실행 코드를 덮지 않음 | `code_sha256`(mlp.py · gpu_runner.py)을 묶음 입력에 넣고 PC · 취합 양쪽에서 대조 |
| H | (낮음) 알 수 없는 GPU 상태도 취합 | 허용 목록(OK · GPU_NOT_RUN · CHECK_REQUIRED · RUN_FAILED) — runner · report 두 층 |
| I | (낮음) 취합 md → json 두 번 rename 비원자 | 임시 폴더에 둘 다 쓴 뒤 폴더 이름 바꾸기 |
| J | (낮음) 한계 문구에 '보유 ETF 26종' 고정 | snapshot 의 ETF 수로 채움 |
| K | (낮음) ETF × 구간 manifest(제외 사유 수 · 마지막 학습 정답 끝일) · 날짜별 ETF 수 분포 없음 | `train_excluded_by_reason` · `test_excluded_by_reason` · `train_label_end` · `dates_by_etf_count` |
| L | (낮음 · 문구) '묶음에 시험 정답 없음'이 넓음 | '각 구간이 예측하는 시험 행의 정답은 그 구간 학습에 없음 · 앞 구간 시험 정답은 뒤 구간 학습에 들어감(앞으로 굴려 가는 학습)'으로 좁힘(코드 설명 · PLAN · 이 문서) |
| M | (낮음) README '더블클릭'은 켜 둔 가상환경을 물려받지 않음 | '명령 프롬프트에서 가상환경을 켠 같은 창에서 실행'으로 |

### 4-3. 그 밖의 정정

- **CLI 요약 줄**: `상태 · 완료 범위` 를 함께 출력한다. 실제 묶음 취합에서 '부분 완료'가 화면 요약에 안 보였다.
- **보고서 글**: ETF별 MAE 표 · 구간별 방법 시간 · 설치 메모리를 추가했다. JSON 에는 이미 있던 값이다.
  - 공식 CPU 폴더의 `report.md` 는 이 변경 전에 쓰였다.
  - 최종 네 방법 보고서(취합 때 새로 씀)에는 들어간다. 사본 취합으로 확인했다(§9-6).

### 4-4. 지시문 밖

- 앞 작업의 설계자 인계 메모(`POC6_DESIGNER_CARRYOVER_...md`)는 사용자 지시로 만든 것이다. 이번 커밋에 함께 넣는다.

### 4-5. 검증자 r1 정정 (2026-10-21 · §11 · P2 1건 + 같은 종류)

원인: `--snapshot` 형식 검사가 날짜 칸이 **글자인지**만 보고 실제로 해석하지 않았다. 손상된 축 날짜가 '가격 없음'으로 흡수돼 정상 계산 · 정상 묶음이 나왔다(검증자 재현 = 해석 불가 · 중복 · 역순).

| 층 | 정정 |
|---|---|
| 검사 함수 `snapshot.py :: snapshot_problem` | 모양 검사(`_shape_problem`)를 교체. 날짜는 실제 해석 + 정규 글자(`YYYY-MM-DD` 로 되돌아와야 함 · `20230601` 같은 기본형 거절) · 엄격한 오름차순(중복 · 역순 거절) — 연구 축 · 건너뛴 평일 · ETF 저장 행 모두. 최상위 · axis · holdings · ETF 칸 목록 정확히 일치. 종가 = 수 또는 없음 · change = 유한한 수 또는 없음 · 출처 = 글자 또는 없음 · 수집 시각 = 해석 가능 또는 없음 · 이름 = 글자 또는 없음 · ticker = 영숫자. 보유 건수(etf = ETF 수 · ticker = ETF + 개별주 · 행 ≥ ticker). 연구 축 내부 일치 — 축 날짜 ∈ [첫 저장일, T] · 주말 없음 · 연도별 방식 = 연도 파일 유무 · 건너뛴 평일 = 축 밖 평일 · KOSPI 보정 해 · 저장된 축 문제 = 06 `axis_problem` 으로 다시 판정한 값 · 라벨 = 06 상수 |
| 만들 때 `build_snapshot` | DB 에서 온 값도 같은 검사(해석 불가 날짜 · 수 아닌 종가 → '시세 DB 값이 snapshot 계약과 다름' CHECK_REQUIRED) |
| 파일 읽을 때 `load_snapshot` | 같은 검사(SnapshotError → CLI rc 2) |
| 계산 시작 `study.prepare` | 같은 검사(StudyError) — 시험 · 다른 호출 경로로 와도 손상 입력은 계산 전에 거절 |
| 취합 `runner.merge`(같은 종류: 디스크에서 다시 읽는 파일) | CPU 폴더 자기 일치 — `input_snapshot.json` 계약 · digest = 보고서 입력 digest · `report.json` recipe 해시 = recipe digest · 시험 행 ID = 묶음 입력 · 정답 · CPU 예측 = [-1, 0] 유한한 수 · 점수 · HGB 판정을 시험 행에서 다시 계산해 같음 · `gpu_input.json` 내용 해시 = bundle digest. GPU 결과 — env · resources 형식 · reason 형식 · OK 이면 재현 차가 유한하고 ≤ 1e-6 |

- 값의 품질(비정상 종가 · 허용 밖 출처 · 경계)은 여전히 06 판정이 표본 제외 사유로 센다. 검사는 '손상 · 계약 위반'만 거절한다.
- **공식 결과는 그대로 유효**:
  - 공식 `input_snapshot.json` 은 새 검사를 통과한다.
  - 정정 코드로 같은 입력을 다시 계산하면 입력 · recipe digest · 점수 · 판정 · 시험 행 예측 · 진단 · 구간 정보(시간 제외) · 묶음 입력(study_id 제외)이 완전히 같다.
  - PC 실행 코드(`mlp.py` · `gpu_runner.py`)는 바뀌지 않아 코드 해시도 같다.
  - 그래서 공식 폴더 · RTX 묶음을 다시 만들지 않았다(공식 실행 1회 유지).
- 검증자의 `git diff --cached --check` 지적(PLAN 끝 빈 줄)도 지웠다.

### 4-6. 검증자 r2 정정 (2026-10-21 · §12 · P2 1건)

- **원인**: r1 정정 때 취합 검사를 칸별로 넣었다(행 ID · 정답 · 예측 범위 · 점수 · HGB 판정). 그런데 최종 ETF별 집계가 쓰는 `ticker` 칸과 행 ID 의 관계는 보지 않았다. 행의 종목코드만 바꾸면 전체 점수는 같아서 통과했고, ETF별 집계가 바뀐 최종 보고서가 나왔다.
- **정정 — 방식 교체(칸 추가가 아님)**: `runner.py :: _cpu_folder_problem` 이 디스크의 `report.json` 을 믿지 않는다.
  - 잠긴 `input_snapshot.json`(계약 검사 · digest 대조 뒤)으로 CPU 단계 전체를 다시 계산한다(세 방법 재학습 · 같은 입력 두 번 학습 확인은 생략).
  - 같은 `build_report` 로 보고서를 다시 만들고, 구간별 학습 · 예측 시간(`blocks[].seconds`)만 빼고 `report.json` 전체와 완전히 같아야 한다. 대상은 시험 행(ID · 종목 · 날짜 · 정답 · 세 예측) · 점수 · 판정 · 진단(ETF별 · 큰 하락) · 적격 · 제외 사유 · 경계 · 구간 정보 · 보유 건수 · 한계 · recipe · 상태 · 완료 범위다.
  - 묶음 표본(`gpu_input.json` 의 구간별 학습 feature · 정답 · 가중치 · 표준화 값 · 시험 feature · 행 ID · feature 이름)도 같은 입력에서 다시 만들어 같아야 한다. 묶음 내용과 digest 를 함께 바꿔 맞춘 경우도 거절한다.
  - 다르면 '`report.json` 이 잠긴 입력에서 다시 계산한 결과와 다름(칸 <첫 다른 칸>)'으로 거절한다. CPU 계산 환경(Python · CPU 라이브러리 판)이 실험 때와 다르면 그 사실을 문구에 덧붙인다.
  - 생성 시각 · 환경 · 자원은 다시 만들 수 없는 실행 기록이다. 다시 계산할 때 보고서 값을 그대로 넘겨 취합 보고서에 옮긴다(그래서 비교에서 따로 뺄 필요가 없다 — 변이 W3 가 살아남아 확인 · 그 제외 코드를 지움).
  - r1 때 넣은 칸별 검사(`_unit` · 행 ID · 점수 · 판정 재계산)는 전체 비교에 포함되므로 지웠다. input_snapshot 계약 · digest · recipe 해시 · 묶음 내용 digest · GPU 결과 칸 검사는 그대로다.
- **비용**: 공식 폴더 사본 취합 2.7초(벽시계 · 재학습 포함).
- **확인**:
  - 공식 폴더 사본에 실제 묶음 결과(GPU_NOT_RUN)를 취합하면 PARTIAL_GPU_NOT_RUN · rc 0.
  - 검증자 r2 재현(`rows_by_block[0][0].ticker` 367760 → 381170 · ID 그대로)은 '칸 rows_by_block'으로 거절된다(rc 2 · 폴더 생성 0).

## 5. 알려진 한계 / 미완성

1. **GPU 미실행(부분 완료)**: POOLED_GPU_MLP 는 실제 CUDA 학습 전이다. RTX PC 실행 → 취합 전에는 'CPU · GPU 비교 완료'나 'RTX 활용 완료'가 아니다.
2. **4종 한정**: 적격 4종은 이름상 모두 기술 · 반도체 · 네트워크 관련 테마 ETF 이고, 4종 모두 가격 경계가 없다(§8-2). 비슷한 스타일의 소수 ETF 결과다. HGB 유망이 공동 학습과 비선형성 중 무엇 때문인지는 구분하지 않았다(설계 §5).
3. **가격 경계**: 06 판정 그대로이며 연결 · change 수정 · 재수집은 하지 않았다.
   - 2026-04-20 경계(16종 공통) 하나로 6종이 2 · 3구간 시험 날짜 부족(5 · 41 < 42)이 됐다.
   - 원인(수집 묶음 간 수정주가 기준 차이 · 분배금 조정)은 추정이며 확인된 사실이 아니다(§8-2).
4. **T = 2026-10-19(KOSPI 저장 최신일)**: ETF 저장 끝일(2026-10-20)보다 하루 이르다.
   - KOSPI 출처는 `KRX_OPEN_API/idx_kospi_dd_trd` 이고, KRX 는 다음 영업일 08:00 에 공개한다.
   - PC 마지막 시장 갱신은 2026-10-20 22:56 KST(`etf_daily_price.fetched_at` · KOSPI `created_at` 모두 2026-10-20T13:56Z)이고, 2026-10-21 갱신은 아직 없다.
   - 지연이 아니라 공개 일정이다. 연구는 공통 T 를 쓰므로 영향은 시험 기간이 하루 앞서는 것뿐이다.
5. **시간 분리는 지키지만 진정한 당시 가용 자료 검증은 아니다.** 저장 종가는 사후 수정이 가능하다. 이미 조사한 역사 구간이라 신규 독립 확증도 아니다.
6. **가속 비교는 RTX PC 안에서만**: 같은 MLP 의 CPU/CUDA 비교만 가속 근거다. 맥북 HGB 시간과 PC MLP 시간을 비교하지 않는다.
7. **HGB 스레드**: 1구간 공동 학습 3,925행에서는 스레드를 늘리면 오히려 느려졌다(1 = 0.119초 · 4 = 0.134초 · 8 = 0.299초). 자료가 작아 병렬 이득이 없다는 실측이며, 장비 한계 시험이 아니다.
8. **관찰(범위 밖 · 이 연구와 무관)**: PC 시장 DB 의 US500 · IXIC · ^SOX 저장 최신일은 2026-09-04 다.
   - 이 셋은 OCI 배치(`app/market_benchmark_batch.py`)가 받는다. PC 갱신 경로에서 찾은 벤치마크 수집은 KOSPI(`market_benchmark_kospi_retry`) · VIX(`pc_vix_refresh`)뿐이다(grep).
   - PC 코드는 이 셋을 읽지 않는다(`app/api_price_series.py` 허용 = KOSPI).
   - 운영 영향은 확인되지 않았고 수정하지 않았다.

## 6. 다음 검증자(Codex)에게 알릴 점

1. **보유 파일 없음 = CHECK_REQUIRED**(검토 E): 구현 초기에는 NO_FILE → 빈 모집단 → DATA_SHORT 였다. 설계 §7 'CHECK_REQUIRED = 입력 손상'과 경로 문제를 자료 부족으로 넘기지 않는 쪽으로 바꿨다. 보유 파일은 있는데 ETF 가 0이면 DATA_SHORT 다(시험 `test_no_holdings_file_is_check_required_but_no_etf_is_data_short`).
2. **취합 위치 변경**(§4-1): PLAN 문구 '같은 폴더'와 다르다. 파일 이름 · 내용 계약은 같다.
3. **recipe digest 범위**: `recipe_digest` = `RECIPE`(고정 11개 포함) 해시다.
   - `hgb_get_params`(설치 판 기본값)는 `recipe_resolved` 에 따로 기록하고 digest 에 넣지 않았다.
   - scikit-learn 판이 바뀌어 기본값이 달라져도 digest 는 같다. 대신 판 번호와 전체 설정이 보고서에 남는다.
4. **threadpoolctl 직접 import**: 하위 의존성이다(§3). requirements 에 명시할지는 판단에 맡긴다.
5. **실행 파일의 `where python`**: Windows 'App 실행 별칭'(Microsoft Store 의 python.exe)이 먼저 잡히면 실행되지 않을 수 있다. README 의 '명령 프롬프트 · 가상환경 같은 창' 안내로 대응한다. 실제 Windows 실행은 아직이다.
6. **변이 P1**: '이미 있음' 거절 검사를 지우면 운영체제 이름 바꾸기도 실패해 같은 오류 종류가 나와 처음엔 살아남았다. 거절 문구까지 시험에 고정해 잡았다.
7. **변이 S16 시간 초과**: 큰 JSON 문자열의 `not in` 단언에서 pytest 가 차이 설명을 만드느라 멈췄다. 칸 목록 비교 + 참/거짓 단언으로 바꿔 잡았다.
8. **학습 정답 끝 < 시작**: 공동 학습 최댓값(구간 표)과 ETF 별 값(ETF × 구간 표)을 둘 다 보고서에 남겼다. 4종 모두 각 구간 직전 거래일이다(§8-3).
9. **snapshot 검사의 범위(r1 정정 · §4-5)**:
   - 축 날짜에 주말이 없어야 한다는 검사는 06 축 규칙(연도 파일 = 거래일 · 파일 없는 해 = 평일 ∩ KOSPI 저장일)에서 나온다.
   - 연도별 방식의 연도 범위 = [첫 저장일 연도, T 연도]는 06 `research_axis` 의 반복 범위 그대로다.
   - KOSPI 저장일 전체는 snapshot 에 없어서 'KOSPI 보정 해의 축 날짜 = 실제 KOSPI 저장일'은 다시 확인할 수 없다(검사 범위 밖 · 06 과 같음). 대신 저장된 축 문제는 06 `axis_problem` 으로 다시 판정해 같아야 한다.
10. **취합 재계산의 전제**(r2 정정 · §4-6):
   - 취합 때 CPU 세 방법을 같은 맥북 환경에서 다시 학습해 보고서와 완전히 같아야 한다. 같은 장비 · 같은 입력의 재현은 공식 실행 때 확인됐다(`repro_cpu_identical`).
   - scikit-learn 등 CPU 라이브러리 판을 바꾼 뒤 취합하면 결과가 달라져 거절될 수 있다. 그때 문구에 환경 차이를 함께 적는다. 해결은 `run --snapshot <공식 입력>` 으로 새 공식 실행이다.
   - 비교는 JSON 왕복에서 float 가 정확히 보존되는 것(Python `json` repr 왕복)에 기댄다. 시험과 공식 폴더 사본에서 같음을 확인했다.
11. **공식 폴더는 정정 전 코드로 만들었다**: 정정 코드로 같은 입력을 다시 계산한 결과가 완전히 같아(§4-5 · §9-6) 다시 만들지 않았다. 검증자가 정정 코드로 새 공식 실행을 원하면 `run --snapshot <공식 input_snapshot.json>` 한 번이며, 새 study ID · 새 묶음이 생긴다.
12. **파일 크기**: `study.py` 623줄(r1 때 620 · `prepare` 의 검사 호출 3줄 · r2 변경 없음). 검사 본문은 `snapshot.py`(335줄)에, 취합 재계산은 `runner.py` 에 두었다.

## 7. 사용자 확인이 필요한 항목

1. **RTX PC 에서 GPU 실행 1회**(판정 §5-3):
   1. `state/ml/research/poc6_02/20261021T104103_129a89b0/gpu_bundle.zip` 을 RTX 4070 SUPER PC 로 옮겨 풉니다.
   2. 명령 프롬프트에서 그 폴더로 이동해 (가상환경이 있으면 켜고) `run_gpu.bat` 를 실행합니다.
   3. 생긴 `gpu_result.json` 을 맥북으로 옮겨 주시면 개발자가 `merge` 합니다.
2. **CUDA 용 PyTorch 가 없으면** 결과는 GPU_NOT_RUN(원인 기록)입니다. 설치 범위는 PyTorch 하나이며(README 예: `pip install torch --index-url https://download.pytorch.org/whl/cu124`), 설치는 사용자 승인 뒤에만 합니다.
3. GPU 실행을 하지 않기로 명시하시면 '부분 완료(GPU 미실행)'로 검증자에게 넘깁니다(설계 §5-1).

## 8. 공식 실행 결과 (맥북 CPU · 2026-10-21 10:41 KST · study `20261021T104103_129a89b0`)

```text
명령        PYTHONDONTWRITEBYTECODE=1 caffeinate -i .venv/bin/python scripts/run_d20_pooled_research.py run → rc 0
상태        COMPLETED · 완료 범위 CPU_PARTIAL_GPU_PENDING
입력 digest 31d766ce1cd225113f6761a47108c393c09dad0f067f4155a4fea54eff3c65a9
recipe      e4488634a49d168254e0189b63430991dd2b83a0c02d75f178f904936bbf1418 (poc6_02.v1)
보유        행 32 · ticker 29 · ETF 26 · 개별주 3(대상 밖 · 건수만)
```

### 8-1. 적격 4종 · 제외 22종

- 적격: 367760 RISE 네트워크인프라 · 381170 TIGER 미국테크TOP10 INDXX · 395160 KODEX AI반도체TOP2플러스 · 442580 PLUS 글로벌HBM반도체.
- 제외 — 상장 기간 부족(어느 구간 학습 < 252) 14종: 0005G0 · 0015B0 · 0035T0 · 0052D0 · 0097L0 · 0107F0 · 0131V0 · 0137V0 · 0137W0 · 0167Z0 · 0174B0 · 0181B0 · 0193T0 · 498860. 첫 저장일은 2024-12-10 ~ 2026-05-27.
- 제외 — 학습은 충분하나 가격 경계로 시험 날짜 부족 8종:
  - 069500 · 139260 · 237350 · 379800 · 379810 · 390390: 경계 = 2026-04-20 BASIS_BREAK 하나. 2구간 시험 58일 · 3구간 22일이 경계 사유로 빠져 시험 날짜 5 · 41 < 42.
  - 161510 · 441800: 경계 5개(02-19 · 03-03 재전환 · 04-20 · 05-07 · 06-08). 세 구간 시험 날짜 27 · 0 · 10.
- ETF 별 구간 사유 전체: `report.json → eligibility.excluded[].reasons` · 표본 제외 사유 수: `eligibility.etfs[t].excluded_by_reason` · 구간별 `blocks[].train_excluded_by_reason` · `test_excluded_by_reason`.

### 8-2. 가격 경계(06 판정 · 검출 사실)

| 날짜 | 종류 | ETF 수 | 앞 → 뒤 행 수집일 |
|---|---|---:|---|
| 2026-02-19 | BASIS_BREAK | 4 | 2026-07-02 → 2026-06-17 |
| 2026-03-03 | SOURCE_RESWITCH | 4 | 2026-06-22 → 2026-07-02 |
| 2026-04-20 | BASIS_BREAK | 16 | 2026-07-04 → 2026-08-17 |
| 2026-05-07 | BASIS_BREAK | 4 | 2026-08-27 → 2026-09-04 |
| 2026-05-26 | BASIS_BREAK | 2 | 2026-09-04 → 2026-09-21 |
| 2026-06-08 | BASIS_BREAK | 4 | 2026-09-21 → 2026-10-05 |
| 2026-06-16 | BASIS_BREAK | 2 | 2026-10-13 → 2026-10-14 |

- 사실: 모든 경계에서 앞뒤 행의 수집 시각이 다르다(수집 묶음이 이어진 자리).
- 원인 추정(사실 아님): 나중 수집의 수정주가 기준(분배금 조정)이 달랐을 가능성이 있다.
- 적격 4종에는 경계가 없다(저장 출처 NAVER_FDR + FinanceDataReader 153행씩).

### 8-3. 구간 · 시간 경계

| 구간 | 시험 날짜 | 공동 학습 행 | 시험 행 / 날짜 | 날짜별 ETF | 학습 정답 끝(최댓값) |
|---|---|---:|---|---|---|
| 1 | 2025-12-08 ~ 2026-03-13 | 3,925 | 252 / 63 | 4(63일 모두) | 2025-12-05 < 2025-12-08 |
| 2 | 2026-03-16 ~ 2026-06-16 | 4,177 | 252 / 63 | 4(63일 모두) | 2026-03-13 < 2026-03-16 |
| 3 | 2026-06-17 ~ 2026-09-15 | 4,429 | 252 / 63 | 4(63일 모두) | 2026-06-16 < 2026-06-17 |

ETF × 구간 학습 행(마지막 학습 정답 끝일은 4종 모두 위 표와 같음):

| ETF | 1구간 | 2구간 | 3구간 |
|---|---:|---:|---:|
| 367760 | 1,173 | 1,236 | 1,299 |
| 381170 | 1,063 | 1,126 | 1,189 |
| 395160 | 985 | 1,048 | 1,111 |
| 442580 | 704 | 767 | 830 |

### 8-4. 날짜 균형 MAE(%p · 판정은 반올림 전 값)

| 방법 | 전체 | 1구간 | 2구간 | 3구간 | 날짜 | 행 |
|---|---:|---:|---:|---:|---:|---:|
| MEDIAN | 6.9662 | 3.6090 | 4.9033 | 12.3862 | 189 | 756 |
| RIDGE_EXISTING | 6.8702 | 3.9767 | 5.1177 | 11.5164 | 189 | 756 |
| POOLED_HGB | 6.2666 | 3.3973 | 4.8783 | 10.5242 | 189 | 756 |
| POOLED_GPU_MLP | GPU_NOT_RUN | | | | | |

- **POOLED_HGB = RESEARCH_PROMISING**:
  - 대 MEDIAN: 전체 개선 10.04%(≥ 5%) · 이긴 구간 3(≥ 2) · 5% 넘게 나빠진 구간 없음.
  - 대 RIDGE_EXISTING: 전체 개선 8.79% · 이긴 구간 3 · 5% 넘게 나빠진 구간 없음.
  - 경계 근처 표시 없음(비율 1e-6 · 구간 MAE 1e-9 %p 안).
- 3구간(2026-06-17 ~ 09-15)은 세 방법 모두 오차가 크다(10.5 ~ 12.4 %p).

### 8-5. 보조 보고(주 판정을 바꾸지 않음)

- D20 ≤ -8% 행 230 · 날짜 82: MAE / 위험 과소 추정 평균 = MEDIAN 17.0585 / 17.0585 · RIDGE 14.3797 / 14.2555 · HGB 14.3406 / 14.3370 %p.
  - 큰 하락 구간에서 HGB 는 RIDGE 와 거의 같다(0.04 %p 차).
  - 세 방법 모두 위험을 크게 작게 추정한다. 유망이어도 큰 하락 경고 용도로 넓히지 않을 근거다(설계 §7).
- ETF별 MAE(%p · ETF 당 189행):

| ETF | MEDIAN | RIDGE_EXISTING | POOLED_HGB |
|---|---:|---:|---:|
| 367760 | 8.6069 | 8.6675 | 8.0836 |
| 381170 | 2.8742 | 2.5662 | 2.5218 |
| 395160 | 8.5814 | 8.4894 | 7.6332 |
| 442580 | 7.8023 | 7.7579 | 6.8278 |

- HGB 대 MEDIAN · 대 RIDGE 모두 ETF 개선 4 · 악화 0(한 ETF 가 전체를 끌어올린 모양은 아님).

### 8-6. 장비 · 버전 · 자원(맥북)

- macOS-27.0.1-arm64 · Apple M1(PLAN §4 실측) · 논리 CPU 8 · 메모리 16GB · Python 3.12.13 · numpy 2.4.6 · scikit-learn 1.9.0 · scipy 1.18.0 · threadpoolctl 3.6.0 · joblib 1.5.3 · torch 2.13.0(CUDA 없음).
- 전체 벽시계 5.91초(snapshot 읽기 · 3구간 × 3방법 학습 · 예측 · 재현 확인 · 스레드 측정 · 묶음 입력 계산까지 · 보고서 · 묶음 파일 쓰기는 제외 · `runner.run`) · 최대 메모리 177.4MB.
- 구간별 학습 · 예측 초:
  - MEDIAN 0.006 / 0.007 / 0.007.
  - RIDGE 0.856 / 0.035 / 0.034(1구간만 큰 것은 첫 호출 준비 때문으로 보임 · 추정).
  - HGB 0.379 / 0.333 / 0.321.
- HGB 학습 스레드(1구간 · 3회 중앙값): 1 = 0.119초 · 4 = 0.134초 · 8 = 0.299초.
- HGB 전체 설정(`recipe_resolved.hgb_get_params`)은 고정 11개 + `interaction_cst None · max_features 1.0 · monotonic_cst None · n_iter_no_change 10 · quantile None · scoring loss · tol 1e-07 · validation_fraction 0.1 · verbose 0 · warm_start False` 이다(early_stopping=False 라 n_iter_no_change · validation_fraction 은 쓰이지 않음).
- RTX PC 묶음 입력: 구간 학습 3,925 / 4,177 / 4,429행 · 시험 252행씩 · `gpu_input.json` 2,369,207B · zip 733,466B.
  - `code_sha256`: mlp.py `930095c0…593a2` · gpu_runner.py `13909933…538102`.

## 9. 검증 실측 (2026-10-21 · 검증자 r2 정정 뒤 · 마지막 코드)

1. **정적 검사**(마지막 수정 뒤):
   - `black --check` · `flake8`: app/d20_pooled · app/reentry_review/model.py · 스크립트 · 시험 모두 통과.
   - `py_compile`: app/d20_pooled/*.py · 스크립트 통과.
   - `git diff --check`: 0건.
2. **시험**: `tests/test_poc6_02_d20_pooled.py` **107개**(`--collect-only` 실측 · 처음 51 → r1 정정 97 → r2 정정 107).
   - r1 정정 추가: snapshot 손상 29종 × 세 층 · GPU 결과 손상 4종 · DB 값 손상 2종 · 축 문제 정상/손상 분리.
   - r2 정정 추가: CPU 폴더 손상 10 → 18종(종목코드 · 날짜 · 적격 · 구간 정보 · 진단 · 경계 · 한계 · 보유 건수) · digest 까지 맞춘 다시 만든 묶음 · 실행 기록 값만 다를 때 취합 허용.
3. **전체 백엔드 회귀 1회**(마지막 코드 · 시험 뒤): `PYTHONDONTWRITEBYTECODE=1 caffeinate -i .venv/bin/python -m pytest -q -p no:cacheprovider tests/` → **4179 passed, 1 warning in 566.30s**(실패 0).
   - r1 전 4123 · r1 뒤 4169 → 늘어난 56개 = POC6-02 시험 증가분.
4. **변이 70종 실행 · 69종 잡힘 · 1종(W3)은 불필요 코드로 판명해 지움**(사본 `mut_be602` · 복원 = 내용 쓰기 + 시각 되돌림 · `PYTHONDONTWRITEBYTECODE=1`):
   - 1차(정정 전 사본) S1 ~ S15: 누수 경계 · 적격 기준 · 최소 종수 · 가중치 · MAE 방식 · 세 조건 경계 · 기준 0 · 범위 제한 · 행 ID · 자료 부족 · 축 문제 · 중앙값.
   - 2차(독립 검토 정정 반영 사본) 30종: S16 · S17 · N1 ~ N6 · L1 ~ L6 · G1 ~ G5 · R1 ~ R5 · P1 ~ P6.
     - 첫 실행에서 S16(시간 초과) · P1(살아남음)은 시험 보강 뒤 잡혔다.
     - P6 은 변이 스크립트의 대상 문자열을 정정한 뒤 재실행해 잡혔다(§6-6 · 6-7).
   - 3차(검증자 r1 정정 반영 사본) 21종 — 21/21:
     - V1 ~ V12: 기본형 날짜 · 중복 · 정렬 · 주말 · 축 문제 재판정 · 연도 방식 · 보유 건수 · change 유한 · DB 값 · 계산 시작 층 · 파일 읽기 층 · 수집 시각.
     - M1 ~ M9: 입력 snapshot digest · recipe 내용 · 묶음 내용 · 점수 재계산 · 판정 재판정 · 정답 범위 · 행 ID · OK 재현 차 · GPU 결과 칸 형식. 이 중 M4 ~ M7 의 칸별 검사는 r2 정정에서 전체 재계산으로 바뀌었다.
   - 4차(검증자 r2 정정 반영 사본) 4종:
     - W1 전체 재계산 비교 없음 · W2 구간별 시간 안 뺌 · W4 묶음 표본 재생성 비교 없음 → 잡힘.
     - W3(환경 · 자원을 비교에서 안 뺌)은 살아남았다. 다시 계산할 때 보고서 값을 넘겨 처음부터 같으므로 그 제외 코드가 필요 없었다 → 코드를 지웠다(§4-6).
5. **라이브 불변**: 공식 실행 전후 `state/market/market_data.sqlite`(424,931,328B · sha256 앞 16자 `fe2df845218ff744`)와 `state/holdings/holdings_latest.json`(47,656B · `284c06b52d959652`)의 크기 · 수정 시각 · 해시가 같다(diff 0). `-wal` · `-shm` 없음. 기존 연구 폴더(poc4_* · poc5_*)의 수정 시각은 이번 실행 전 날짜(2026-09-25 ~ 10-17)다.
6. **재현 · 끝까지 흐름**:
   - 같은 `input_snapshot.json` 으로 임시 폴더에 재실행했다. 입력 · recipe digest · 점수 · 판정 · 시험 행 예측 · 묶음 입력(study_id 제외)이 완전히 같다. `repro_cpu_identical` 은 두 실행 모두 True.
   - 실제 `gpu_bundle.zip` 을 임시 폴더에 풀어 맥북에서 `python -I gpu_runner.py` → GPU_NOT_RUN('CUDA 사용 불가(torch 2.13.0 · torch.version.cuda=None …)') · rc 0.
   - 공식 폴더 **사본**에 `merge` → `gpu_attempts/…_GPU_NOT_RUN_…/` · 완료 범위 PARTIAL_GPU_NOT_RUN · 공식 폴더에는 기록 없음.
   - **r1 정정 뒤 다시**:
     - 공식 `input_snapshot.json` 이 새 검사를 통과한다.
     - 정정 코드로 같은 입력을 임시 폴더에 다시 계산했다. digest · 점수 · 판정 · 시험 행 · 진단 · 구간 정보(시간 제외) · 묶음 입력(study_id 제외) · 코드 해시가 모두 같다.
     - 실제 묶음을 다시 맥북에서 실행하고, 공식 폴더 새 사본에 취합했다(새 자기 일치 검사 통과). 결과 = PARTIAL_GPU_NOT_RUN · rc 0.
     - 검증자 r1 재현 3건(축 날짜 해석 불가 · 중복 · 역순)은 새 검사가 각각 '날짜 해석 불가' · '중복 · 역순'으로 거절한다.
   - **r2 정정 뒤 다시**:
     - 공식 폴더 사본에 실제 묶음 결과(GPU_NOT_RUN)를 취합했다. 전체 재계산 비교를 통과해 PARTIAL_GPU_NOT_RUN · rc 0 · 2.7초.
     - 검증자 r2 재현(공식 폴더 사본 `rows_by_block[0][0].ticker` 367760 → 381170 · ID 그대로)은 '`report.json` 이 잠긴 입력에서 다시 계산한 결과와 다름(칸 rows_by_block)'으로 거절됐다. rc 2 · 폴더 생성 0.
7. **외부 호출 0**: 결과 폴더 시험에서 `socket.connect` 를 막은 채 `run` 이 완료된다.

## 10. git 상태 (검증자 r2 정정 뒤 다시 stage · 실측 2026-10-21)

`git status --short --untracked-files=all`:

```text
A  app/d20_pooled/__init__.py
A  app/d20_pooled/env.py
A  app/d20_pooled/gpu_runner.py
A  app/d20_pooled/mlp.py
A  app/d20_pooled/report.py
A  app/d20_pooled/runner.py
A  app/d20_pooled/snapshot.py
A  app/d20_pooled/study.py
M  app/reentry_review/model.py
M  docs/PROGRAM_TRUTH.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md
A  docs/ai_plan/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_V1.md
A  docs/ai_result/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_RESULT.md
A  docs/ai_result/POC6/POC6_DESIGNER_CARRYOVER_FROM_0726_MASTER_HANDOFF_2026-10-21.md
M  docs/backlog/BACKLOG.md
A  scripts/run_d20_pooled_research.py
A  tests/test_poc6_02_d20_pooled.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- staged 19파일(A 15 · M 4) · 오른쪽 칸 공백(unstaged 0).
- untracked 1 = 사용자 보존 handoff(의도적 제외 · stage 하지 않음).
- 커밋 · push 없음(종료 때 사용자 승인으로).
- `git diff --cached --check` 0건.
- 라이브 `market_data.sqlite` · `holdings_latest.json` 의 크기 · 수정 시각 · 해시가 공식 실행 전 기록과 같다(r2 정정 작업 뒤 재확인).


## 11. 검증자 r1 — CPU 구현·공식 결과·RTX 실행 묶음 선행 검증 (2026-10-21)

독자: 개발자 · 사용자. 사용자가 **CPU 범위부터 검증**을 선택했다. 실제 RTX CUDA 실행·실제 GPU 결과 취합은 이번 판정 범위 밖이며, `IMPLEMENTED_CPU_PARTIAL_GPU_PENDING` 상태와 GPU 미완료를 유지한다. GPU 미실행을 반려 사유로 삼지 않았다.

### 11-1. A. 기능/산출물 검증

- **A-1 지시 일치: 위반(P2 1건).** 설계 §7의 `CHECK_REQUIRED = 입력 손상·계열 계약 위반` 및 PLAN §9의 손상/학습 오류 구분과 달리, `--snapshot`으로 받은 연구 축의 해석 불가 날짜를 정상 입력으로 수용한다. `app/d20_pooled/snapshot.py:150~153`은 각 항목이 문자열인지까지만 검사한다. `study.prepare`도 축 끝과 T의 일치만 확인해 손상된 중간 날짜가 이후 가격 누락으로 흡수된다.
- **A-2 보고 정확성: CPU 수치·변경 목록 통과, 손상 대응 완료 표현은 위 P2에 한정해 불충족.** staged 19(A 15 · M 4)·unstaged 0·제외 handoff 1개가 시작 시점 실측과 같다. 공식 CPU 세 방법의 예측·점수·판정과 입력/recipe digest를 그대로 재현했다. 개발자의 전체 회귀 4,123건·변이 45건은 이번 검증자가 다시 실행한 수치가 아니다.
- **A-3 산출물 정합성: 위반(같은 P2).** 손상 snapshot으로도 정상 완료 보고서·연구 유망 판정·RTX 실행 묶음이 생성된다. 정상 공식 산출물 자체의 수치 불일치는 발견하지 않았다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·외부 API·DB 스키마·운영 코드 경로·화면·OCI·PUSH 변경 없음. 기존 06 변경은 공개 별칭 추가뿐이다.

**P2 재현(저장소 밖 사본만 사용)**

1. 공식 `input_snapshot.json`의 임시 사본에서 `axis.dates[2391]`의 `2024-01-02` 한 값만 `invalid-date`로 바꿨다. 실제 공식 폴더·시세 DB·보유 파일은 수정하지 않았다.
2. staged 소스 사본의 CLI `run --snapshot <손상 사본>`을 실행했다. 종료 코드 **0**, 상태 **COMPLETED**, 완료 범위 **CPU_PARTIAL_GPU_PENDING**, HGB **RESEARCH_PROMISING**, `gpu_bundle.zip` 생성으로 끝났다.
3. 공동 학습 행은 정상 3,925 / 4,177 / 4,429에서 **3,601 / 3,853 / 4,105**로 달라졌다. HGB 전체 MAE도 **6.26660827207083 → 6.264918937324782 %p**로 달라졌다. 입력 손상이 정상적인 표본 제외와 학습으로 이어진 코드 결함이다.
4. 같은 경계 점검으로 해당 위치의 날짜 **중복**(`2024-01-02` 두 번)과 **역순**(`2024-01-03`, `2024-01-02`)도 확인했다. 두 경우 모두 `load_snapshot → prepare`가 거절하지 않고 적격 4종을 유지했다. 이 두 경우는 입력/표본 준비까지만 확인했으며 전체 학습을 재실행하지 않았다.

### 11-2. B. 구현 규칙/구조 품질 검증

- **B-1 fallback:** 손상 연구 축을 단순 가격 누락으로 흡수하고 나머지 표본으로 정상 계산하는 경계 위반 있음(위 P2와 동일 원인).
- **B-2 단일 책임:** 별도 위반 없음. snapshot·표본/평가·MLP·실행기·보고서·계측을 분리했다.
- **B-3 파일 책임 과다:** 임계 초과 없음. `study.py` **620줄**로 KS-10 근접 구간(600 이상)이다. 나머지 신규 Python 모듈은 520줄 이하, 시험 파일 915줄이다.
- **B-4 실험/운영 경계:** 위반 없음. 새 연구 모듈의 호출은 연구 CLI 내부이며 06 계산 본문은 그대로다.
- **B-5 배포/실행 경로:** 위반 없음. 연구 코드·CLI가 모두 Git index에 있다. 실행 묶음은 승인된 gitignored 연구 산출물이며 원격 pull 전달 대상이 아니라 사용자가 zip을 옮기는 경로다. 기존 배포 스크립트·cron 변경 없음. Windows/CUDA 실실행은 미확인으로 유지한다.
- **B-6 기술부채/구조적 퇴행:** 위 P2 외 별도 결함 없음. 과거 점수를 재사용하지 않고 같은 snapshot의 세 CPU 방법을 다시 계산했다.

### 11-3. 기반 문서 준수

MongoDB·새 UI 프레임워크·새 서비스 도입 없음. 새 문서는 승인 설계/판정/PLAN/결과서 및 보고서에 명시된 선행 사용자 인계 메모다. 기존 사용자 소유 7-26 handoff 파일은 읽거나 변경·stage하지 않았다. 연구 유망을 운영 채택으로 승격하지 않으며 `ML_OPERATION_PROMOTION=NOT_APPROVED`·`CURRENT_DEPLOYABLE_ML_MODEL=none`·Q6 OPEN 유지다.

### 11-4. 코드 안전성

**위험 수준: MEDIUM.** 손상 입력으로 학습 표본·점수가 바뀌어도 정상 연구 산출물로 유통될 수 있다. 외부 호출·비밀값·운영 DB 쓰기 결함은 발견하지 않았다. 실제 시장 DB·보유 파일은 검증 중 열지 않았다. 사용자 지정 공식 연구 폴더만 읽어 임시 사본을 만들었으며, 원본 **9파일 SHA-256은 검증 전후 동일**하다.

### 11-5. 범위 폭주

**폭주 수준: NONE.** 설계자 판정의 맥북 CPU/RTX 묶음 분리, 별도 계측/실행 모듈, CPU 원본을 보존하는 취합 하위 폴더는 보고된 범위다. GPU 실제 실행·설치·운영 채택·커밋·push를 수행하지 않았다.

### 11-6. 검증 실측·종합 판정

- 기준 HEAD **e525dc3796fe9f2efc627a079635773246cc6799**, staged 19파일을 저장소 밖으로 꺼내 검증했다.
- 관련 시험: `test_poc6_02_d20_pooled.py` + `test_poc5_06_reentry_model.py` = **68 passed, 2 warnings, 66.34초**. 경고는 기존 Starlette/httpx 폐기 안내와 joblib 물리 코어 수 조회 실패다.
- 정적 검사: 변경 Python **11파일** black·flake8·별도 경로 py_compile 통과. 전체 회귀와 전체 변이 반복은 하지 않았다. `git diff --cached --check`는 기존 PLAN의 마지막 빈 줄 1곳을 지적했다(187행·문서 공백이며 판정 사유 아님).
- 정상 공식 snapshot 재계산: CPU 세 방법의 표본별 예측·점수·판정 **정확히 일치**. 학습 feature/정답 **12,531행**, 시험 정답 **756행**을 저장 가격으로 별도 대조했다. 날짜 균형 MAE와 HGB의 두 기준 대비 세 조건도 별도 계산해 일치했다.
- 공식 zip의 5항목은 폴더 내용과 바이트가 같으며, 묶음 입력 digest와 두 실행 코드 hash가 staged 소스와 일치했다.
- 실제 zip 내용의 임시 사본을 맥북에서 실행: **GPU_NOT_RUN·exit 0**. 임시 공식 폴더에 취합: **PARTIAL_GPU_NOT_RUN**, 최종 `gpu_merged` 생성 없음, CPU 점수 보존.
- torch import가 불가능한 독립 프로세스에서도 CPU 실행 **COMPLETED**, 외부 socket 연결을 금지한 상태에서 정상 종료했다. 최초 검증 스크립트의 `sys.modules['torch']=None` 방식은 SciPy가 설치 여부를 판단하는 방식과 충돌해 폐기했고, 실제 미설치처럼 import를 거절하는 방식으로 확인했다. 제품 코드 결함으로 집계하지 않았다.
- 추가 손상 재현: 날짜 해석 불가 **CLI 전체 경로 1건**, 중복·역순 **입력/표본 준비 2건**이 모두 거절되지 않았다(위 P2).
- 검증 근거: `/private/tmp/poc602-cpu-verifier-kmbbu_od/`의 `related.log`, `cpu_audit.json`, `bad-axis-observed.json`, `axis-neighbors.json`, `boundaries.log` 등. 원본 운영 코드·시험 변경 0.

**종합 판정: REJECTED — CPU 구현·RTX 묶음 준비 범위의 입력 검증 결함 P2 1건.**

### 11-7. 사용자에게 한마디

정상 CPU 공식 결과는 재현됐습니다. 반려 사유는 문서 숫자나 GPU 미실행이 아니라 손상된 연구 축으로도 정상 학습 결과와 RTX 묶음이 나오는 코드 결함입니다. GPU는 계속 미완료이며 전체 연구 종료·커밋·push 승인은 포함하지 않습니다.


## 12. 검증자 r2 — CPU 범위 재검증 (2026-10-21)

독자: 개발자 · 사용자. 대상은 HEAD `e525dc3796fe9f2efc627a079635773246cc6799` 대비 staged 19파일(A 15 · M 4)이다. 사용자 지정 CPU 선행 검증이며, 실제 RTX CUDA 학습·GPU 실측·실제 GPU 결과 취합은 미완료 상태를 유지한다.

### 12-1. A. 기능/산출물 검증

- **r1 P2: CLOSED.** 당시 공식 snapshot 사본으로 만든 날짜 해석 불가·중복·역순 3파일을 그대로 재사용했다. 세 경우 모두 `load_snapshot`은 SnapshotError, `study.prepare`는 StudyError로 거절한다. CLI도 각각 **exit 2**, 연구 출력 폴더 생성 0이다. 정상 공식 snapshot은 새 검사에서 통과한다.
- **A-1 지시 일치: 위반(P2 1건).** 설계 §6의 같은 ETF×날짜 비교와 PLAN 판정 §3-1의 구간·행 연결 계약에 대해, 추가한 CPU 폴더 자기 일치 검사가 행 ID와 실제 집계 종목의 불일치를 놓친다. `runner.py:133~141`은 `id` 목록과 수치 범위를 검사하지만, 최종 ETF별 집계에 쓰는 `ticker`와 행 ID의 관계는 확인하지 않는다.
- **A-2 보고 정확성: 정상 CPU 수치·변경 목록·시험 수 통과.** 원본 공식 입력의 세 CPU 방법을 다시 계산해 표본별 예측·점수·판정이 정확히 일치했다. staged 19(A 15 · M 4)·unstaged 0·제외 handoff 1건도 실측과 같다. 다만 손상 CPU 보고서의 최종 산출 차단은 아래 사례까지 충족하지 못한다. 개발자의 전체 4,169건·변이 66종은 이번 검증자가 반복 실행한 수치가 아니다.
- **A-3 산출물 정합성: 위반(같은 P2).** 종목코드 한 칸이 손상돼도 merge가 정상 완료 보고서를 쓰며, 한 ETF의 행을 다른 ETF에 집계한다. 전체 CPU 점수 재계산은 이 불일치를 검출하지 못한다.
- **A-4 금지사항 위반: 없음.** 이번 정정의 연구 코드는 snapshot·study·runner 3파일이다. MLP·PC 실행기·CPU 모델 계산 본문·의존성·DB·화면·API·OCI·PUSH 변경 없음.

**P2 재현 — 정상 대조군과 손상 사본 비교**

1. 공식 연구 폴더를 저장소 밖으로 복사했다. 취합용 GPU 결과는 행 ID·digest·실행 코드 hash가 같은 **합성 시험 fixture**이며, 모든 예측은 -0.05, 재현 차는 0이다. 실제 GPU 실행이나 GPU 성과의 근거로 쓰지 않았다. 두 경우에 정확히 같은 fixture를 사용했다.
2. 정상 대조군은 `runner.merge`가 정상 처리하고, 4종 모두 189행이다.
3. 손상 사본에서는 `report.json → rows_by_block[0][0].ticker` **한 칸만** `367760`에서 `381170`으로 바꿨다. 같은 행의 `id`는 `367760|2025-12-08`, `date`는 `2025-12-08`로 그대로다. 입력 snapshot·묶음·정답·예측·scores·판정은 변경하지 않았다.
4. 손상 사본도 거절되지 않고 `gpu_merged/report_with_gpu.json`·`.md`를 생성하며 **completion = FULL**로 끝난다. 첫 행은 ID의 종목과 ticker가 서로 다르게 남는다.
5. 최종 ETF별 집계는 다음처럼 달라진다. 전체 CPU 점수는 그대로라 현재 자기 일치 검사에서 통과한다.

| ETF | 정상 행 | 손상 후 행 | 정상 HGB MAE(%p) | 손상 후 HGB MAE(%p) |
|---|---:|---:|---:|---:|
| 367760 | 189 | 188 | 8.08356518432111 | 8.11797301745863 |
| 381170 | 189 | 190 | 2.521816881135808 | 2.517043595205975 |

이것은 문서 줄 수나 숫자 오기가 아니라, 손상된 CPU 행을 받아 통계를 다시 계산하는 코드 결함이다. 정상 공식 CPU 결과나 기존 zip이 손상됐다는 뜻은 아니다.

### 12-2. B. 구현 규칙/구조 품질 검증

- **B-1 fallback:** r1의 손상 축 정상 진행은 해소됐다. 새 검사에는 명시적인 오류 종료가 있다. 위 P2는 종목 연결 검사 누락으로 A-1·A-3에 기록한다.
- **B-2 단일 책임:** 별도 위반 없음. 입력 검사와 CPU 결과 취합 검사를 각 책임에 배치했다.
- **B-3 파일 책임 과다:** 임계 초과 없음. 실측 `study.py` **623줄**로 KS-10 근접 구간이다. snapshot 335 · runner 200 · report 520 · 시험 1,128줄이다.
- **B-4 실험/운영 경계:** 위반 없음. 기존 운영 경로에 연구 계산을 넣지 않았다.
- **B-5 배포/실행 경로:** 위반 없음. 승인된 코드·CLI 모두 Git index에 있으며, Windows zip은 사용자가 옮기는 승인된 연구 산출물이다. 기존 배포 스크립트·cron 변경 없음.
- **B-6 기술부채/구조적 퇴행:** 위 P2 외 별도 위반 없음. 정상 결과를 같은 snapshot으로 새로 계산해 비교했다.

### 12-3. 기반 문서 준수

MongoDB·신규 UI 프레임워크·새 서비스·새 의존성 도입 없음. 신규 문서 범위는 r1 때와 같으며, 사용자 소유 7-26 handoff는 읽거나 수정·stage하지 않았다. Q6 OPEN·ML_OPERATION_PROMOTION NOT_APPROVED·CURRENT_DEPLOYABLE_ML_MODEL none과 연구/운영 경계를 유지한다.

### 12-4. 코드 안전성

**위험 수준: MEDIUM.** 손상 보고서의 행이 다른 ETF로 귀속돼 ETF별 오차·행 수가 달라져도 정상 최종 산출물이 된다. 운영 DB·외부 호출·비밀값 관련 결함은 발견하지 않았다. 시세 DB·보유 파일을 열지 않았으며, 사용자 지정 공식 연구 폴더만 읽어 사본을 만들었다. 공식 원본 **9파일 SHA-256은 검증 전후 동일**하다.

### 12-5. 범위 폭주

**폭주 수준: NONE.** 확대된 snapshot 검사와 merge 자기 일치 검사는 r1 입력 손상 결함과 직접 연결된 보고 범위다. 검증자는 운영 코드·시험을 수정하지 않았고, GPU 실제 실행·설치·커밋·push·OCI 작업을 수행하지 않았다.

### 12-6. 검증 실측·종합 판정

- 저장소 밖 staged 사본에서 관련 시험: POC6-02 **97건** + 기존 06 모델 **17건** = **114 passed, 2 warnings in 110.30초**. 경고는 r1과 같은 Starlette/httpx 폐기 안내와 joblib 물리 코어 수 조회 실패다.
- 변경 Python **11파일** black·flake8·별도 경로 py_compile 통과. `git diff --cached --check` 통과(PLAN 끝 공백 정정 확인).
- 전체 회귀 4,169건·변이 66종은 개발자 최종 코드 실행 근거를 재사용했으며 반복하지 않았다.
- 원본 공식 snapshot으로 세 CPU 방법의 예측·점수·판정 정확히 일치. 학습 feature/정답 **12,531행**, 시험 정답 **756행** 및 날짜 균형 MAE·HGB 세 조건을 별도 대조해 일치했다.
- 기존 RTX zip 5항목과 폴더 내용이 바이트 단위로 같고, 입력/recipe/묶음 digest와 `mlp.py`·`gpu_runner.py` hash가 수정 코드와 일치한다. 정상 입력의 RTX 묶음은 그대로 재사용 가능하다.
- 실제 zip을 임시 폴더에 풀어 맥북에서 실행: **GPU_NOT_RUN·exit 0**. 새 자기 일치 검사로 공식 폴더 사본에 실제 결과 파일을 취합: **PARTIAL_GPU_NOT_RUN·exit 0**, 최종 gpu_merged 생성 없음.
- r1 재현 3건 모두 거절 확인. 별도 merge 재현은 정상 대조군·ticker 한 칸 손상군 각 1건이며, 손상군도 정상 완료된 것이 위 P2다. 합성 GPU fixture의 FULL 출력은 제품 오류 재현용이며 실제 CUDA 완료로 집계하지 않았다.
- 근거: `/private/tmp/poc602-r2-verifier-7v6jg00z/`의 `related.log`, `cpu_audit.json`, `repro_r2.json`, `actual_merge.json`, `artifact-hashes.json` 등.

**종합 판정: REJECTED — r1 날짜 결함 CLOSED, CPU 보고서 취합의 종목 연결 불일치 수용 P2 1건 잔존.** GPU 실제 실행은 미완료 상태를 유지한다.

### 12-7. 사용자에게 한마디

r1 정정과 정상 CPU 결과·기존 RTX 묶음의 동일성은 확인됐습니다. 이번 재작업 사유는 merge가 잘못된 종목에 행을 집계하고도 정상 최종 보고서를 만드는 코드 결함 1건입니다. 문서 수치·GPU 미실행 때문에 반려한 것이 아닙니다.


## 13. 검증자 r3 — CPU 범위 재검증 (2026-10-21)

독자: 개발자 · 사용자. **CPU 구현·공식 CPU 결과·RTX 실행 묶음 준비에 한정한 검증**이다. 실제 RTX CUDA 학습·자원 실측·실제 GPU 결과 취합 검증은 남아 있다. 전체 상태 `IMPLEMENTED_CPU_PARTIAL_GPU_PENDING`은 유지하며 전체 연구 완료·설계자 RESULT 판정·커밋·push를 대신하지 않는다.

### 13-1. A. 기능/산출물 검증

- **A-1 지시 일치: 통과(CPU 범위).** 잠긴 snapshot으로 CPU 세 방법을 다시 학습·계산한 뒤 보고서를 재구성하여 비교한다. 시험 행의 종목·날짜·정답·예측, 점수·판정·진단·적격·경계·구간·한계가 전체 비교에 포함된다. 구간별 실행 시간만 비교에서 제거하고, 다시 만들 수 없는 환경·자원·생성 기록은 원본 값을 그대로 넘긴다는 범위도 명시돼 있다. 묶음의 학습/시험 자료와 표준화 근거도 같은 snapshot에서 재생성해 비교한다.
- **r1 P2: CLOSED 유지.** 당시 재현 3파일(날짜 해석 불가·중복·역순)을 그대로 재사용했다. `load_snapshot`과 `study.prepare`가 모두 거절하며, CLI는 각각 **exit 2·출력 폴더 생성 0**이다.
- **r2 P2: CLOSED.** 동일한 공식 폴더 사본·합성 GPU fixture로 정상 대조군과 종목코드 한 칸 손상군을 다시 비교했다. 정상군은 4종 모두 189행으로 취합된다. `rows_by_block[0][0].ticker`만 367760 → 381170으로 바꾼 군은 **MergeError('report.json 이 잠긴 입력에서 다시 계산한 결과와 다름(칸 rows_by_block)')**로 거절되고 `gpu_merged`·`gpu_attempts` 모두 생성되지 않는다. 합성 fixture는 취합 계약 시험용이며 실제 GPU 실행의 근거가 아니다.
- **A-2 보고 정확성: 통과.** staged 19(A 15·M 4)·unstaged 0·제외 사용자 handoff 1건과 목록이 일치한다. r2 대비 연구 코드 변경은 `runner.py`뿐이며, 기존 CPU 계산·snapshot 검사·RTX 실행 코드·설계/판정은 같다. 정상 CPU 수치와 RTX 묶음 불변 주장을 직접 대조했다.
- **A-3 산출물 정합성: 통과(CPU 범위).** 공식 snapshot 재계산의 CPU 표본별 예측·점수·판정이 정확히 같다. 새 전체 비교가 정상 공식 폴더를 받아들이며, 기존 RTX 묶음과 입력/recipe/코드 hash도 일치한다. GPU 미실행은 정상 점수나 GPU 성공으로 대체하지 않는다.
- **A-4 금지사항 위반: 없음.** 신규 의존성·외부 API·DB 스키마·화면·API·OCI·PUSH·PARAM 변경 없음. 검증자는 운영 코드·시험을 직접 수정하지 않았다.

### 13-2. B. 구현 규칙/구조 품질 검증

- **B-1 fallback:** 위반 없음. 입력 손상·CPU 재계산 불일치·묶음 불일치를 명시적으로 거절한다.
- **B-2 단일 책임:** 위반 없음. runner는 기존 계산·보고서 조립 함수를 호출해 대조하며 모델 계산을 중복 구현하지 않는다.
- **B-3 파일 책임 과다:** 임계 초과 없음. 실측 `study.py` 623줄은 KS-10 근접 구간이다. runner 227·snapshot 335·report 520·시험 1,206줄로 임계 미만이다. 근접 사실을 구조 위반이나 전체 완료로 바꾸지 않는다.
- **B-4 실험/운영 경계:** 위반 없음. 연구 코드 호출은 연구 CLI 내부이며 기존 06 계산 변경은 공개 median 별칭뿐이다.
- **B-5 배포/실행 경로:** 위반 없음. 연구 코드·CLI는 모두 Git index에 있으며, RTX zip은 사용자 전달 경로의 승인된 gitignored 산출물이다. 기존 배포 스크립트·cron 변경 없음.
- **B-6 기술부채/구조적 퇴행:** 위반 없음. 과거 점수를 비교 기준으로 재사용하지 않고 잠긴 입력에서 CPU 결과·묶음 자료를 재계산한다. 성과에 맞춘 재설정·대상 변경 없음.

### 13-3. 기반 문서 준수

MongoDB·신규 UI 프레임워크·새 서비스 도입 없음. 신규 문서 범위는 이전 라운드와 같다. Q6 OPEN·ML_OPERATION_PROMOTION NOT_APPROVED·CURRENT_DEPLOYABLE_ML_MODEL none 유지다. 적격 4종에 한정한 회고 연구이며 HGB 연구 유망을 운영 채택으로 승격하지 않는다. 사용자 소유 7-26 handoff는 읽거나 수정·stage하지 않았다.

### 13-4. 코드 안전성

**위험 수준: NONE(검증한 CPU 범위의 발견 결함 기준).** r1·r2 손상 재현은 모두 차단됐다. 시세 DB·보유 파일을 열지 않았고, 외부 호출·GPU 설치·원격 실행·운영 쓰기를 하지 않았다. 사용자 지정 공식 연구 폴더만 읽어 임시 사본을 만들었으며, 공식 원본 **9파일 SHA-256은 검증 전후 동일**하다. 실제 Windows/CUDA 경로는 별도 미검증으로 남긴다.

### 13-5. 범위 폭주

**폭주 수준: NONE.** 전체 재계산 대조는 r2 무결성 결함과 직접 연결된 정정이다. 고정 연구 설정·모집단·공식 폴더·RTX 실행 코드는 바뀌지 않았다. 검증 기록만 이 결과서에 추가했고 커밋·push·배포는 하지 않았다.

### 13-6. 검증 실측·종합 판정

- 기준 HEAD **e525dc3796fe9f2efc627a079635773246cc6799**의 staged 19파일을 저장소 밖 사본으로 꺼내 검증했다.
- 관련 시험: `test_poc6_02_d20_pooled.py` + `test_poc5_06_reentry_model.py` = **124 passed, 2 warnings in 166.77초**. 경고는 이전과 같은 Starlette/httpx 폐기 안내와 joblib 물리 코어 수 조회 실패다.
- 변경 Python **11파일** black·flake8·별도 경로 py_compile 통과. `git diff --cached --check` 통과.
- 개발자의 최종 전체 회귀 **4,179건**과 누적 변이 **70종 실행·69종 검출·1종 불필요 코드 제거** 근거를 재사용했으며 전체 회귀·전체 변이를 반복하지 않았다. 이번 검증자가 직접 실행한 관련 시험 수와 구분한다.
- 공식 snapshot의 CPU 세 방법을 다시 계산해 표본별 예측·점수·판정 정확히 일치. 학습 feature/정답 **12,531행**, 시험 정답 **756행**, 날짜 균형 MAE·HGB의 두 기준 대비 세 조건도 별도 대조했다.
- 기존 zip 5항목은 폴더와 바이트가 같으며, 입력/recipe/묶음 digest·두 실행 코드 hash가 수정 소스와 일치한다. **기존 RTX 묶음 재사용 가능**을 확인했다.
- 기존 zip의 임시 사본 실행 = **GPU_NOT_RUN·exit 0**. 정상 공식 폴더 사본에 이 실제 결과를 취합 = **PARTIAL_GPU_NOT_RUN·exit 0**, 최종 `gpu_merged` 없음. 재계산·취합 벽시계 **2.55초**(이번 검증자 실측), CPU 시험 행·점수·진단·HGB 판정 보존. GPU 후보 사유는 실제 CUDA 부재 사유로 갱신된다.
- 검증용 정상/손상 취합 비교에서 합성 GPU fixture를 쓴 경우의 FULL 출력은 시험 경로 확인일 뿐 실제 CUDA 완료로 집계하지 않았다.
- 정상 취합 확인의 최초 검증 스크립트는 GPU 후보의 '취합 전' 사유까지 보존돼야 한다고 잘못 단언해 실패했다. 제품의 정상적인 GPU 부재 사유 갱신을 확인한 뒤 CPU 결과 보존과 GPU 사유 갱신을 구분해 바로잡았고 재실행이 통과했다. 제품 코드 결함이나 기존 시험 실패로 집계하지 않았다.
- 근거: `/private/tmp/poc602-r3-verifier-0bpp7rco/`의 `related.log`, `repro_r3.json`, `cpu_audit.json`, `actual_merge.json`, `artifact-hashes.json` 등.

**종합 판정: VERIFIED — CPU 구현·공식 CPU 결과·RTX 실행 묶음 준비 범위 한정. r1·r2 P2 모두 CLOSED.**

전체 연구 상태는 **CPU_PARTIAL_GPU_PENDING**이다. 실제 RTX 실행 → 결과 취합 → GPU 부분 검증 → 설계자 RESULT 판정 → 사용자 별도 커밋·push 승인 순서를 유지한다.

### 13-7. 사용자에게 한마디

CPU 범위 검증은 통과했습니다. 기존 경로의 RTX 묶음을 사용하면 되며, GPU 실제 실행·최종 결과 확인이 남아 있습니다. 이번 VERIFIED는 전체 연구 종료·운영 모델 채택·커밋·push 승인이 아닙니다.
