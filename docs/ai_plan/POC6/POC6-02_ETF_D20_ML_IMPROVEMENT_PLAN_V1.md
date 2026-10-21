# POC6-02 개발 PLAN V1 — ML 고도화: ETF D20 추정 개선 검증

작성 2026-10-21 · 작성자: 개발자(VSCode Claude) · 수신: 설계자 · 사용자

```text
STATUS   = PLAN 제출(2026-10-21) · 질문 3 → 설계자 PASS_TO_IMPLEMENT_WITH_CORRECTIONS(2026-10-21 · Q1 (b) 최소 4종 · Q3 개발자 해석 · Q2 맥북 개발 · CPU 실행 + RTX PC 는 작은 GPU 실행 묶음만 · §9) → 구현 2026-10-21 · 독립 검토 1회 반영 · 맥북 공식 CPU 실행 1회(2026-10-21 · POOLED_HGB RESEARCH_PROMISING · POOLED_GPU_MLP GPU_NOT_RUN · 완료 범위 CPU_PARTIAL_GPU_PENDING) · 검증자 r1(CPU 선행) REJECTED → 정정(결과서 §4-5) · 검증자 r2(CPU 선행) REJECTED → 정정(결과서 §4-6) · 검증자 r3(CPU 선행) VERIFIED(결과서 §13) · RTX PC GPU 실행 · 맥북 취합 완료(2026-10-21 · 완료 범위 FULL · POOLED_GPU_MLP REJECT · POOLED_HGB RESEARCH_PROMISING · 4종 한정) · GPU 부분 검증자 r1 VERIFIED(2026-10-21 · 결과서 §14) · 설계자 RESULT PASS · IMPLEMENTED_VERIFIED_CLOSED(2026-10-21 · 결과서 §15 · completion FULL · 운영 채택 없음) · 결과서 `docs/ai_result/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_RESULT.md`
DESIGN   = docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_DESIGN_V1.md(개정 2 · 개정 1 은 전달 전 대체)
DECISION = docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md(판정이 설계와 충돌하면 판정 우선)
범위     = 설계 §9 여섯 확인만 · 코드 변경 0 · 시장 DB mode=ro · 보유 문서 읽기만 · 외부 호출 0
실측     = 2026-10-21 · 성과(시험 오차) 계산 0 — 적격 수 · 자원(학습 시간 · 메모리)만
```

참고 사실: POC6-01 커밋 `e525dc37` 은 원격에 올라가 있다(origin/main 추적 참조 = e525dc37 · 사용자가 직접 push). 설계 §1 의 'push 미완료'는 지금 사실과 다르다.

## 1. 06 재사용 접점 (§9-1)

| 쓰는 것 | 06 위치 | 그대로? |
|---|---|---|
| 목표 D20 · feature 5개 | `app/reentry_review/model.py :: target_at · features_at · FEATURE_NAMES` | 그대로 |
| 3구간 날짜 경계 | 같은 파일 `_validate`: anchor = 축 T−20 · 189 = 63 × 3 · 학습 = `i + 20 < 구간 시작` | 같은 규칙. 공동 비교용으로 새 모듈에 다시 쓴다(06 함수 본문 변경 0) |
| Ridge | `model.fit_predict`(표준화 학습 구간만 · Ridge(alpha=1, svd) · [−1, 0]) | 그대로 호출 |
| 중앙값 | `model._median`(짝수 = 가운데 둘 평균 — 설계와 같음) | **공개 이름 `median = _median` 한 줄만 추가**(POC5-16 `valid_close` 와 같은 방식) |
| 가격 읽기 · ETF 판별 | `app/reentry_review/prices.py :: read_rows · read_kospi_dates · is_etf` · 허용 출처 = `FinanceDataReader` · `NAVER_FDR` | 그대로 |
| 연구 축 · 경계 판정 | `research_axis · axis_problem · AxisSeries.window_ok/window_reason`(누락 · 허용 밖 출처 · 비정상 종가 · FDR change 불일치 BASIS_BREAK · SOURCE_RESWITCH) | 그대로 |
| 보유 목록 | `holdings_store.read_document()["doc"]["holdings"]` 의 ticker | 그대로(수량 · 평단 · 계좌는 읽기만 하고 산출물에 넣지 않음) |
| 해시 | `prices.canonical_hash` | 그대로 |

**06 과 다른 점(설계대로)**
- 기준일 T 를 ETF 마다 쓰지 않고 **공통 T = KOSPI 저장 최신일 하나**로 둔다. 06 은 ETF 마지막 저장일을 기준일로 쓴다.
- 연구 축은 `research_axis(T, 보유 ETF 중 가장 이른 저장일, KOSPI 저장일)` 하나다.

**기준 재현 fixture**: 06 시험 계열(`tests/test_poc5_06_reentry_model.py`)과 같은 합성 가격으로 새 모듈의 ETF 하나 · 한 구간 Ridge · 중앙값 예측이 06 `evaluate` 와 소수 끝자리까지 같은지 시험한다.

## 2. 지금 자료 — 보유 · 가격 · 적격 수 (§9-2 · 성과 미열람)

- 보유 문서 V2 · 행 32 · 고유 ticker 29 = **ETF 26 · 개별주 3 · 확인 불가 0**.
- T = **2026-10-19**(KOSPI 저장 최신일). 연구 축은 3,070일(2014-04-10 ~ 2026-10-19 · axis_problem 없음).
- anchor = 2026-09-15. 시험 구간 = ① 2025-12-08 ~ 2026-03-13 · ② 2026-03-16 ~ 2026-06-16 · ③ 2026-06-17 ~ 2026-09-15.
- 모든 ETF 의 저장 끝일(10-20)은 T 이후다(적용 불가 0).
- 적격 조건 = 각 구간 학습 ≥ 252 · 그 구간 유효 시험 날짜 ≥ 42(Q3 해석).
  - **세 구간 모두 맞는 ETF = 4종 → 설계 §6 '5종 미만 = DATA_SHORT'**.
  - 4종 = 367760 RISE 네트워크인프라 · 381170 TIGER 미국테크TOP10 INDXX · 395160 KODEX AI반도체TOP2플러스 · 442580 PLUS 글로벌HBM반도체.
- 탈락 22종의 사유:
  - **상장이 짧아 학습 252 미달: 14종**(2024-12 ~ 2026 상장).
  - **이력은 충분한데 끊김 때문에만 탈락: 8종.**
    - **2026-04-20 기준 끊김 하나로 6종**: KODEX 200 · TIGER 200 IT · KODEX 코스피100 · KODEX 미국S&P500 · KODEX 미국나스닥100 · KODEX 미국반도체.
    - 그날은 보유 ETF 16종이 동시에 BASIS_BREAK 이다. 06 은 끊김을 걸치는 창(앞 60 · 뒤 20 축일)을 모두 빼서 ② 구간 시험 날짜가 63 중 5일만 남는다.
    - 여러 끊김으로 2종(161510 · 441800): 04-20 에 더해 02-19 · 03-03 · 05-07 · 06-08 이다(FDR · 네이버 출처 오감 · change 불일치).
- **04-20 끊김의 성격(읽기 전용 대조)**: 저장 묶음이 이어 붙은 자리다.
  - 04-17 이전 행은 2026-07-04 에, 04-20 이후 행은 2026-08-17 에 받았다.
  - 나중 묶음의 FDR `change` 로 거꾸로 계산한 04-17 종가가 저장값보다 0.07 ~ 0.7% 낮다. 수정주가 기준(분배금 조정)이 다른 두 수집이 이어진 것으로 보인다.
  - 즉 06 판정이 맞다. 그날 끊김을 무시하면 기준이 다른 가격이 한 창에 섞인다.
- 참고(성과 아님): 04-20 하루를 끊김으로 보지 않으면 적격 10종이다. 그러나 위 이유로 이것을 추천하지 않는다.
- 공동 학습 표본 규모: ① 구간 학습 행 = 4종 3,925 · (참고) 10종 14,959.

## 3. 시간 경계 · 동일 시험 행 · 날짜 균형 가중치 (§9-3)

- **새 모듈 `app/d20_pooled/study.py`**:
  - 구간마다 학습 = 적격 ETF 의 `i + 20 < s` 표본만이다(모든 ETF 같은 축 경계 · 구간 안 재학습 없음).
  - 시험 = 구간의 축 날짜 × 적격 ETF 중 유효 표본이다.
  - 네 방법 예측은 같은 (ETF, 날짜) 행 키로 맞춘다. 한 방법이라도 그 행 예측이 없으면 `RUN_FAILED` 로 하고 몰래 빼지 않는다.
- **가중치**:
  - 공동 학습(HGB · MLP)은 학습 날짜 d 의 행마다 1/n_d 다.
  - MLP 표준화는 같은 가중 평균 · 모집단 표준편차(상수 열 = 0)로 한다.
  - MEDIAN · RIDGE 는 06 그대로 같은 비중이다.
- **평가**: 날짜 균형 MAE = 날짜별 적격 ETF 절대오차 평균 → 날짜 평균(%p). 전체 · 구간 · ETF 별로 낸다. 판정은 반올림 전 값으로 한다.
- **표본 manifest**(report.json):
  - ETF × 구간별 학습 수 · 시험 수 · 제외 사유별 수 · 학습 마지막 정답 종료일.
  - 시험 행 목록(ETF · 날짜 · 정답 · 네 방법 예측).

## 4. 장비 · 환경 · 자원 (§9-4)

| 항목 | 이 맥북(개발 · CPU) | RTX PC(GPU) |
|---|---|---|
| CPU · RAM | Apple M1 8코어 · 16GB | 미확인(Q2) |
| GPU | 없음(CUDA 없음 · MPS 는 쓰지 않음) | RTX 4070 SUPER — 2026-06-21 기존 ML 축1 GPU 실행 기록(`gpu_execution_used: true`) · 지금 환경 미확인 |
| Python · 라이브러리 | 3.12.13 · scikit-learn 1.9.0 · numpy 2.4.6 · torch 2.13.0(CPU) · threadpoolctl 3.6.0 · psutil 없음 | 미확인 · `requirements.txt` 는 torch(cu124 설치 안내) · scikit-learn 1.9.0 |
| 고정 HGB | 지원 확인 — 설정 그대로 · `sample_weight` 학습됨(나머지 기본값은 recipe 에 기록) | 같은 버전이면 같음 |

- **짧은 자원 실측**(이 맥북 · ① 구간 학습만 · 시험 예측 0):
  - HGB 학습: 4종(3,925행) 0.11초(1스레드) · 0.14초(4) · 0.26초(8). 스레드를 늘리면 오히려 느리다(자료가 작아 병렬 비용이 더 큼).
  - CPU MLP 200 epoch: 1초 안쪽(첫 측정은 준비 시간 포함).
  - 최대 메모리 412MB.
  - **이 규모로는 CPU · GPU 를 한계까지 쓰지 못한다.** 설계 §5-1 대로 '자료가 작아 GPU 가 느리거나 여유가 남음'을 그대로 결과로 보고한다. 자료를 복제해 부하를 키우지 않는다.
- **측정 방식**:
  - CPU 병렬도는 HGB · CPU MLP 를 `threadpoolctl` · `torch.set_num_threads` 로 {1, 논리 코어 절반, 전체} 에서 잰다.
  - GPU 는 microbatch {min(N,256), min(N,4096), N} 로 잰다(warm-up 1 + 3 epoch · 시험 성과 안 봄).
  - 메모리: POSIX 는 `resource.ru_maxrss`, Windows 는 `ctypes` 로 `GetProcessMemoryInfo`, GPU 는 `torch.cuda.max_memory_allocated`. **psutil 은 넣지 않는다**(새 의존성 0).
- **장비 간 전달**: CLI 를 두 단계로 나눈다.
  - `snapshot`(이 맥북): 시장 DB · 보유를 한 번 읽어 `input_snapshot.json` 을 만든다. 담는 것은 ticker · 날짜 · 종가 · 출처 · change · 연구 축이고, 개인 값 · 비밀값은 없다.
  - `run --snapshot <파일> --device cpu|cuda`: snapshot 만 읽는다(DB · 보유 불필요).
  - RTX PC 에는 같은 저장소 커밋 + snapshot 파일만 옮긴다.
  - 같은 장비에서 CPU 와 CUDA 를 비교하려면 **공식 실행은 RTX PC 에서 네 방법 모두** 돌리는 것을 추천한다(Q2). 맥북 실행은 GPU_NOT_RUN 인 CPU 부분 결과다.
- **재현 · 허용 오차**(성과 열람 전 제시):
  - seed(Python · numpy · torch) = 42 · `torch.use_deterministic_algorithms(True)` · `CUBLAS_WORKSPACE_CONFIG=:4096:8` · TF32 끔.
  - 예비 재현은 **같은 장비에서 두 번 학습한 예측끼리**만 비교한다(정답과 비교하지 않음).
  - 허용: MEDIAN · RIDGE · HGB = 완전히 같음 · MLP = 최대 |Δ예측| ≤ 1e-6. 넘으면 `CHECK_REQUIRED`(다른 seed 고르지 않음).
  - 판정 경계: 판정은 공식 1회의 반올림 전 값 그대로 한다. 개선율이 5% 경계와 1e-6 안이거나 구간 MAE 차가 1e-9 %p 안이면 '경계 근처'를 표시만 한다(판정은 바꾸지 않음).

## 5. 파일 · 출력 · 읽기 전용 · 보존 (§9-5)

- **새 파일**:
  - `app/d20_pooled/__init__.py`
  - `snapshot.py`(읽기 · snapshot)
  - `study.py`(표본 · 구간 · 적격 · MEDIAN/RIDGE/HGB · 평가 · 판정)
  - `mlp.py`(torch 를 이 안에서만 import · 없으면 GPU_NOT_RUN)
  - `report.py`(report.md/json · 임시 폴더 뒤 이름 바꾸기 = 06 방식)
  - `scripts/run_d20_pooled_research.py`
  - `tests/test_poc6_02_d20_pooled.py`
- **수정**: `app/reentry_review/model.py` 공개 이름 1줄.
- **출력**: `state/ml/research/poc6_02/<KST시각>_<id>/`(git 제외 확인 · `.gitignore:233`)에 report.md · report.json · input_snapshot.json 을 둔다. 쓰기 실패는 실패로 끝난다.
- **읽기**: 시장 DB 는 06 과 같은 `open_ro` 한 읽기 트랜잭션으로 읽고 닫은 뒤 계산한다. 보유 문서는 읽기만 한다. 외부 HTTP · SSH 는 0 이다.
- **라이브 가드**: `tests/_live_guard.py`(conftest 자동 설치)를 그대로 쓴다. 새 시험은 tmp DB · 합성 snapshot 만 쓰고, 출력 경로는 tmp 로 바꾼다. POC4 러너는 쓰지 않는다.
- **보존 시험**: 기존 `state/ml/research/poc5_06` · `poc5_08` 산출물 해시 불변 · 06 시험 그대로 통과.

## 6. 백로그 ML 통합 4건 대조 (§9-6)

| # | 원 요구 | 이번 목표와의 관계 |
|---:|---|---|
| 3 | 종합 위험 구간 분류 | 해당 안 됨 — D20 은 하락 크기 추정이며 등급 · 구간 분류를 만들지 않는다. 미완료 유지 |
| 55 | 무릎 · 머리 · 어깨 정량 기준 | 해당 안 됨 — 진입 · 보유 설명 규칙을 다루지 않는다. 미완료 유지 |
| 57 | RS · 거래량 · 정배열 복합 | 해당 안 됨 — 입력은 06 가격 5개뿐(거래량 · RS 결합 없음). POC5-20 기록 보존 |
| 62 | ML · 백테스트 기반 seed 품질 | 해당 안 됨 — 후보 선별을 다루지 않는다. #59 · PC3/OCI20 정합 · 자동 교체는 보류 유지 |

네 항목 모두 완료라고 선언하지 않는다.

설계 §12 의 보류 아이디어 3건(업종 Treemap · 후보 초과수익 순위 보조 차트 · Holdings 마지막 슬롯 시각)은 BACKLOG 에 해당 항목이 없다(grep 확인). 구현 때 '조건부' 3건으로 사유 · 위험 · 재검토 조건을 넣는다. Treemap 은 #20 Category(업종 분류) 와 연결 표시한다. 그러면 합계 62 → 65 · 조건부 41 → 44 가 된다.

## 7. 질문

### Q1(설계자) — 지금 자료로는 공식 결과가 DATA_SHORT 로 정해진다

06 판정 그대로면 적격 4종(5 미만)이다. 공식 실행은 비교 · CPU/GPU 학습 전에 `DATA_SHORT` 로 끝나고, 7-26 의 CPU · GPU 실사용도 실제 자료로는 일어나지 않는다.

| 안 | 내용 | 결과 |
|---|---|---|
| **(a) 설계 그대로** | 06 판정 · 최소 5종 유지 | 공식 결과 DATA_SHORT(사유 = 04-20 수집 묶음 경계 · 짧은 상장). 도구는 구현 · 시험하지만 실데이터 비교는 없음 |
| **(b) 최소 ETF 수 5 → 4** | 가격 의미 판정은 그대로(섞임 없음) · 성과 미열람 상태의 잠금 전 변경 | 4종 × 3구간 비교 · CPU/GPU 실학습 가능(작은 표본임을 보고) |
| (c) 가격을 같은 기준으로 다시 받기 | 보유 ETF 이력을 한 번에 다시 수집해 04-20 경계를 없앰 | 적격이 늘 수 있음(참고: 04-20 하나만 빼고 센 값 = 10종 · 실제는 다시 받은 자료로 다시 세야 함) · '신규 수집 없음' 계약 변경 · 외부 호출 승인 필요 |

**개발자 추천 = (b)**.
- 이유: 가격 의미 계약(06 판정)을 그대로 지키면서 비교와 CPU · GPU 실학습이 실제 자료로 일어난다.
- 5종은 설계 §6 이 '실험 길이와 최소 비교 범위를 정한 설계 선택'이라고 적은 값이다. 성과를 보기 전(잠그기 전)이라 결과에 맞춘 조정이 아니다.
- (a) 를 고르면 그대로 구현하고, 공식 결과 DATA_SHORT 를 사실대로 보고한다.

### Q2(사용자) — RTX PC 실행

- 공식 실행(네 방법 · 같은 장비 CPU/CUDA 비교)을 RTX PC 에서 할 수 있는가?
- 그 PC 에 이 저장소 최신 커밋 · Python 3.12 · scikit-learn 1.9.0 · CUDA 용 torch 가 지금도 있는가?
- 실행 방법: 맥북에서 만든 snapshot 파일을 그 PC 로 옮기고(USB · 클라우드 등) 명령 한 줄을 실행한다. 결과 폴더를 다시 맥북으로 가져오면 내가 결과서를 쓴다.
- 안 되면 맥북 CPU 결과 + `GPU_NOT_RUN` 으로 두고, GPU 실행 전에는 'CPU · GPU 비교 전체 완료'를 선언하지 않는다(설계 §5-1).

### Q3(설계자 · 확인) — '구간별 공통 시험 날짜 42/63일 이상'의 뜻

내 해석:
- ETF 마다 그 구간 63 축일 중 유효 표본(feature · 정답 창이 온전) ≥ 42 다.
- '공통'은 네 방법이 같은 행으로 비교한다는 뜻으로 본다.

다른 뜻(예: 적격 ETF 전부가 유효한 날짜 ≥ 42)이면 알려 달라. 위 적격 수는 내 해석으로 센 값이다.

## 8. 진행

판정 → 구현(독립 검토 1회 · 변이 · 관련 시험) → 맥북 CPU smoke(형식 · 시간 · 누수 · 표본 수만) → 공식 1회(Q2 장비) → 전체 회귀 1회 → RESULT → 검증자 → 설계자 결과 판정 → 커밋 · push(사용자 승인). 화면 변경이 없어 목업은 없다.

## 9. 설계자 판정 반영 (2026-10-21 · 판정 원문 `docs/ai_design/POC6/POC6-02_ETF_D20_ML_IMPROVEMENT_PLAN_DECISION_2026-10-21.md`)

- **Q1 (b) 최소 ETF 4종**:
  - recipe · 보고서에 '최초 기준 5종 · 변경 4종 · 이유 = 성과 미열람 · 잠금 전 · 범위 선택값'을 남긴다.
  - 가격 경계(04-20 포함)는 06 판정 그대로다. 경계 검출 사실(날짜 · 종류 · 앞뒤 수집 시각)과 원인 추정(분배금 조정 가능성)을 나눠 적는다. 가격 재수집 · DB 수리는 없다.
  - **결과 범위는 4종 한정**이다. 실제 snapshot 에서 4종 미만이면 DATA_SHORT.
- **Q3**: ETF 마다 각 구간 유효 시험 날짜 ≥ 42 다. 날짜 균형 MAE 와 함께 날짜별 ETF 수 · 실제 평가 날짜 수 · 제외 사유를 남긴다.
- **Q2 맥북 · PC 분리**(PLAN §4 의 'RTX PC 에서 네 방법 모두' 추천은 철회):

| 위치 | CLI 동작(`scripts/run_d20_pooled_research.py`) | 내용 |
|---|---|---|
| 맥북 | `run` | 시장 DB · 보유를 한 번 읽어 snapshot → 표본 · 적격 → MEDIAN · RIDGE · HGB 공식 실행 · CPU 자원 측정 · 재현 확인 → 결과 폴더(report.md/json · input_snapshot.json) + **`gpu_bundle/`**(MLP 코드 · 실행기 · 입력 · 실행 안내 · Windows 실행 파일). MLP 후보 = GPU_NOT_RUN |
| RTX PC | `gpu_bundle/run_gpu.bat`(= `python gpu_runner.py`) | Python · torch · CUDA · 장치만 확인 → CUDA 없으면 원인을 적고 GPU_NOT_RUN 파일 · 있으면 microbatch 예비 측정 · 같은 MLP 의 CPU/CUDA 짧은 속도 비교 · 구간별 200 epoch 학습 · 예측 · 재현 확인 → `gpu_result.json` |
| 맥북 | `merge --run-dir <폴더> --gpu-result <파일>` | study ID · 입력/recipe digest · 구간 · 행 ID 완전 일치 확인(누락 · 중복 · 다른 실험 = 거절) → 네 방법 지표 · 최종 보고서(새 파일 · 기존 CPU 보고서는 덮지 않음) |

  - MLP 학습 본문은 `app/d20_pooled/mlp.py` 하나다. torch · 표준 라이브러리만 쓰고 저장소의 다른 모듈은 import 하지 않는다. 그래서 그대로 묶음에 복사되고, 맥북 시험(CPU torch)과 PC 실행이 같은 코드를 쓴다.
  - 묶음 입력 = 구간별 학습 feature · 정답 · 가중치(1/n_d) · 시험 feature · 행 ID · 맥북이 학습 구간에서 확정한 날짜 균형 가중 표준화 값 · study ID · digest. 시험 정답 · 개인 값 · 비밀값은 없다.
    - 문구 좁힘(2026-10-21 · 구현 뒤 독립 검토): '시험 정답 없음' = 각 구간이 예측하는 시험 행의 정답이 그 구간 학습에 없고 시험 정답 칸(truth)이 없다는 뜻이다. 앞 구간 시험 행의 정답은 뒤 구간 학습 정답으로 들어간다(앞으로 굴려 가는 학습 · 누수 아님). 실행 코드 해시(mlp.py · gpu_runner.py sha256)도 묶음 입력에 넣어 PC · 취합에서 대조한다.
  - PC 요구 = 사용 가능한 Python + CUDA 용 torch 뿐이다(전체 저장소 · DB · scikit-learn · numpy · 서버 · 키 불필요). 실행 환경 버전은 결과 파일에 그대로 적는다.
  - GPU 가속 효과는 PC 안 같은 MLP 의 CPU/CUDA 비교로만 쓴다. 맥북 HGB 와 PC MLP 시간을 가속 배수로 쓰지 않는다.
- 재현 허용값(MEDIAN · RIDGE · HGB 같음 · MLP 최대 |Δ예측| ≤ 1e-6) · 경계 근처 표시는 §4 그대로다. torch 없음 · CUDA 없음 = GPU_NOT_RUN 이고, 데이터 손상(CHECK_REQUIRED) · 학습 오류(RUN_FAILED)와 구분한다.
- 백로그 4건 대조 수용 · 조건부 아이디어 3건 기록은 §6 그대로다. POC6-01 push = 완료(e525dc37).
