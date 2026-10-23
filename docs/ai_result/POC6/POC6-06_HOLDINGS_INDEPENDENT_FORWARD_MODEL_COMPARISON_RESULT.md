# POC6-06 개발 결과서 — HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON (보유 독립 ETF 대상의 전향 ML 비교 · 기록)

작성 2026-10-23 · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex) · 설계자

```text
STATUS        = IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED(2026-10-23 · §15) — 검증자 r3 VERIFIED(§13) · 설계자 RESULT PASS_TO_DEPLOY(§14) · OCI 반영 · 업로드 · 양쪽 복원 확인
                · 첫 성숙(D+20 = 2026-11-19 종가 뒤) · 월별 학습의 실제 운영 확인 = 별도 상태
                격리 구현 · 시험 → 독립 검토 1회 반영(§4-2) → 변이 63종 → 사용자 승인 묶음 → 초기 조회 24/24 → 첫 run(D = 2026-10-22 · 24종)
                → 전체 회귀 4362 → 검증자 r1 REJECTED(§11 · F1 · F2 P2 · F3 P3) → 개발자 정정(§4-5 · 같은 종류 포함)
                → 정정 독립 검토 1회 반영 → 실제 run 1회(첫 기록의 공개 확인 영수증 11:26 KST) → 변이 · 전체 회귀 4376
                → 검증자 r2 REJECTED(§12 · F1 · F2 CLOSED · F3 잔여 = 자정을 넘는 공개의 날짜) → 정정(§4-5 · 같은 종류 포함) → 변이 · 전체 회귀 4378(§9)
                → 검증자 r3 VERIFIED(§13) → 설계자 RESULT PASS_TO_DEPLOY(§14 · prediction_receipt 수용 · §2 시각 설명 정정 반영)
STEP_ID       = POC6-06 보유 독립 ETF 대상의 전향 ML 비교 · 기록
DESIGN        = docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_DESIGN_V1.md
DECISION      = docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_DECISION_2026-10-22.md(PASS · Q1 = §1 문장 · Q2 = (a))
PLAN          = docs/ai_plan/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_V1.md(§9 판정 반영)
SCOPE         = PC 모듈 `app/forward_compare/` · CLI `scripts/run_forward_compare.py` · 05 보관 허용 형식 한정 확장(`forward_artifacts` 신규 · `store.KINDS` · `transfer` 받기)
                · 기반 문서 3곳 판정 §1 문장 · 시험 2파일
REAL_RUNS     = PC 2026-10-23: 고정 표본 확정 · 초기 조회 24 요청 · 05 pull 1회(기존 경로) · run 2회(10:20 초기 학습 + 전향 기록 · 11:26 정정 코드로 공개 확인)
                — OCI 쓰기 · 커밋 0
VERIFIER      = r3 VERIFIED(2026-10-23 · §13 · 기존 §11·§12 보존 · 코드·시험 직접 수정 0)
COMMITS       = 구현 666fc5c0(코드를 처음 포함한 커밋 = OCI 배포 판) · 종료 기록 = 종료 커밋(git log 로 확인) — 실제 학습 · 예측 run 은 666fc5c0 전의 미커밋 작업 트리 코드(10:20 = r1 이전 · 11:26 = r1 정정)
```

## 0. 요약

- **무엇**: 보유와 무관한 고정 ETF 24종에서, 기존 네 방법(MEDIAN · RIDGE · HGB · MLP_CPU · 02 recipe 그대로)의 D20 예측을 **결과가 나오기 전에** 기록하고, 결과가 성숙하면 같은 행에서 비교하고, 쌓인 행을 다음 학습에 쓰는 연결을 만들었다.
- **흐름**(PC 수동 `run` 한 번): 05 PC 보관본 확인 → 성숙 목표 연결 → 학습 결정(초기 · 월별 · 실패 방법 복구) → 예측 기록 → 비교 보고.
  - `--pull` · `--archive` 를 줄 때만 SSH 를 쓴다. 과거 시각을 입력받는 인자는 없다.
- **실제 연결(2026-10-23 금)**: 초기 조회 24/24 OK → 초기 학습 37,692행(24종 모두 252 이상) → 첫 run = **FORWARD_RESEARCH 주 기록 24종**(D = 2026-10-22 · 10:20 작성 기록 · 11:26:13 KST 까지 존재 확인(영수증) · 마감 15:30).
  - 검증자 r1 정정 뒤 주 기록은 **공개 확인 영수증**(파일 해시 · 놓인 뒤 찍은 시각 = 공개 시각의 상한 < 마감)이 있어야 센다. 첫 기록은 11:26:13 KST run 이 영수증을 남겨 유효(주 기록 24 · 미확인 0).
  - 네 방법 모두 OK. 복원 대조 4방법 일치. 저장 파일만으로 다시 읽은 예측 96개 = 기록값과 차 0.0.
- **성과는 아직 없다**: 첫 성숙은 D+20 = 2026-11-19 종가 뒤. 보고서는 비교 행 0 · MAE null(정상).
- **같은 날 OCI 동작 확인(사용자 요청)**: 05 첫 09:40 정기 실행 OK · 기존 작업 6건 정상(§8-5).
- **운영 영향 0**: 운영 경보 · 추천 · 매매 · PUSH · PARAM · 화면 · API · cron · OCI 쓰기 변경 없음. 라이브 DB 는 mode=ro 읽기만.
  - ML_OPERATION_PROMOTION=NOT_APPROVED · CURRENT_DEPLOYABLE_ML_MODEL=none · Q6 OPEN 그대로.

## 1. 처리한 요구사항

설계 §12 수용 기준과 판정 §1 ~ §7 순서로 적는다.

| # | 요구사항 | 결과 | 근거 |
|---|---|---|---|
| 판정 §1 | 기반 문서 3곳에 연구 한정 예외 문장(원문 그대로 · 날짜 · 판정 경로) | DONE | `PROJECT_ORIGIN_INTENT`(POC5-08 예외 다음) · `ASSUMPTIONS` Q6(POC5-08 연구 계약 다음) · `KILL_SWITCHES` KS-11(POC6-05 인용 다음) |
| 판정 §2 | Q2 (a) — 종목마다 가장 이른 유효 원래 공개 판 | DONE | `inputs.Evidence.select_input` · 시험 `test_input_is_earliest_valid_original_publication_and_skips_ineligible` 외 2 |
| 판정 §3 | 24종 유지 · 보조 3묶음 · 영숫자 식별자 · 선정 요약 고정 | DONE | `cohort.json` = 후보 898종 저장일 요약 · 목록 object · 규칙 · 시각 · `0015K0` 그대로 |
| 판정 §4 | 시각 · 성숙 정정(09:50 예상 · 금요일 D · 늦은 진단 · 21종가 실제 검사) | DONE | `forward.close_cutoff` · `inputs.next_trading_day` · `select_target` |
| 판정 §5 | 저장 · 복원 · 월별 학습 · 자원 실측 | DONE | §8 실측(시간 · 메모리 · 크기) |
| 판정 §6 | 05 허용 확장(정규화 경로 · schema · 참조 · 해시) · 시험 범위 | DONE | `forward_artifacts.classify · problems` · 경로 시험 13종 |
| 1 | 선정이 보유 · 손익 · 평가와 독립 · 고정 목록 · 분모 보존 | DONE | 보유 표를 둔 DB 로 시험 · 고정 뒤 DB 를 바꿔도 다시 순위 매기지 않음 |
| 2 | 제한된 초기 장기 창으로 학습 준비 · 120일 창 접합 없음 · 적격 수 · 미달 사유 | DONE | 24/24 적격 · 제외 사유 = MISSING_PRICE(상장 전 · 반환 시작 전 축 날짜)만 |
| 3 | 네 방법 초기 학습 · 저장/복원 · 실제 feature 입력 예측 | DONE | §8 |
| 4 | 미래 · 늦은 입력 · 미성숙 목표 누출 0 · 마감 · 오래된 기준일 · 같은 날 재실행 | DONE | 시험(§9) · 시작은 마감 전이고 공개가 마감 뒤인 경우 = 진단 |
| 5 | D20 · 미성숙 · 도래 후 결측 · 한 창 · 정정 판 보존 · 월별 예제 · 무학습 · 복원 · 방법별 실패 · 같은 행 비교 | DONE | §9 시험 목록 |
| 6 | 실제 자료로 한 번 실행(유효 시간대 = 전향 기록) | DONE | 2026-10-23 10:20 KST 전향 주 기록 24종(늦은 실행의 진단 경로는 격리 시험으로만 확인) |
| 7 | PC/OCI 사본 · 복구 실제 확인 · 기존 공식 파일 · 05 수집 · 운영 표 · PUSH 불변 근거 | DONE | §15(OCI 배포 666fc5c0 · 업로드 · PC · OCI 빈 경로 복원 · 16파일 해시 일치 · 참조 7곳) · §8-4 |
| 8 | 검증자 · 설계자 RESULT 판정 뒤 반영 · 종료 | DONE | r3 VERIFIED(§13) · RESULT PASS_TO_DEPLOY(§14) · 종료 기록(§15) |
| r1 F1 | 실제 공개 < 마감일 때만 전향 기록 | DONE | 놓기 직전 재검사 · 놓은 뒤 공개 확인 영수증 · 영수증 시각 < 마감만 주 기록(§4-5) |
| r1 F2 | 겹친 실행이 월 학습 · 주 기록 후보를 두 번 만들지 않음 | DONE | 연구 폴더 단일 실행 잠금(쓰는 명령 4종) · 다른 실행 중 = BUSY · 쓰기 0(§4-5) |
| r1 F3 · r2 잔여 | 첫 해석일 = 첫 실제 예측일(공개 확인일 KST) + 3개월 | DONE | 공개 확인 영수증 시각의 KST 날짜(자정을 넘는 공개 = 다음 날) · 실제 2027-01-23(§8-6) |

## 2. 변경된 파일 목록

**신규(코드)**
- `app/forward_compare/__init__.py` — 모듈 표.
- `app/forward_compare/protocol.py` — 고정 상수(24종 · 보조 묶음 · CLOSE_CUTOFF = 기존 상수 참조) · 산출물 머리 · 한 번 쓰면 끝 쓰기(놓기 직전 검사) · 단일 실행 잠금(`exclusive` · `Busy`) · `ClockBehind`.
- `app/forward_compare/cohort.py` — 고정 표본 선정 · 재현 확인 · 고정 뒤 다시 순위 없음.
- `app/forward_compare/bootstrap.py` — 초기 장기 가격 1회 조회(다시 조회 거절) · 초기 회고 예제.
- `app/forward_compare/inputs.py` — 05 보관본 연구 축 · 입력 판 선택 · 성숙 목표 창 선택.
- `app/forward_compare/models.py` — 네 방법 학습 · 저장 · 복원(해시 · 방법별 라이브러리 판) · 예측 · 복원 대조.
- `app/forward_compare/training.py` — 초기 · 월별 · 실패 방법 복구 학습 결정 · 예제 묶음 · 모델 판.
- `app/forward_compare/forward.py` — run(성숙 → 학습 결정 → 예측 기록 → 보고).
- `app/forward_compare/mature.py` — 성숙 목표 첫 평가 고정.
- `app/forward_compare/records.py` — 예측 · 목표 기록 읽기(공개 확인 영수증 · 주 기록 · 재시도 연결 · 진단 분리 · 기록 시각 최댓값).
- `app/forward_compare/report.py` — 같은 행 날짜 균형 MAE · 분모 · 보조 표.
- `app/forward_compare/archive.py` — 05 보관소 등록 · 로컬 상태.
- `app/ml_evidence/forward_artifacts.py` — POC6-06 보관 허용 형식(PC 등록 · OCI 받기 공용 · 표준 라이브러리 + store 만).
- `scripts/run_forward_compare.py` — CLI.

**신규(시험)**
- `tests/test_poc6_06_forward_core.py`(42) · `tests/test_poc6_06_forward_flow.py`(27).

**수정**
- `app/ml_evidence/store.py` — `KINDS` 에 `FORWARD_RESEARCH_ARTIFACTS` 추가(+5 −1).
- `app/ml_evidence/transfer.py` — `UPLOAD_KINDS` · `upload_research` 종류 검사 · `accept_upload` 가 POC6-06 묶음이면 `forward_artifacts.problems` 로 검사(02 · 03 · 04 `_research_problems` 그대로).

**수정(문서)**
- `docs/PROJECT_ORIGIN_INTENT.md` · `docs/KILL_SWITCHES.md` · `docs/ASSUMPTIONS.md` — 판정 §1 문장.
- `docs/STATE_LATEST.md` — POC6-06 칸 · 05 첫 정기 실행 manifest 확인 사실.
- `docs/PROGRAM_TRUTH.md` — 최종 반영 · §4 · §7.2 · §8 FDR · §11 · §12 · 부록 A.
- `docs/ai_plan/POC6/POC6-06_..._PLAN_V1.md` — STATUS 줄.
- `docs/ai_result/POC6/POC6-05_..._RESULT.md` · `docs/ai_plan/POC6/POC6-05_..._PLAN_V1.md` — 05 "첫 정기 실행 = 정기 운영 확인 대기" → 실측 OK 로 교체(§4-4).

**신규(문서)**
- `docs/ai_design/POC6/POC6-06_..._DESIGN_V1.md` · `..._PLAN_DECISION_2026-10-22.md`(원문 그대로) · `docs/ai_plan/POC6/POC6-06_..._PLAN_V1.md` · 이 결과서.

**git 밖(연구 산출물 · gitignored)**: `state/ml/research/poc6_06/` 16파일(§8-3 · §8-6).

## 3. 신규 추가된 의존성

없음. torch 2.13.0 · scikit-learn 1.9.0 · joblib 1.5.3 · numpy 2.4.6 은 PC 에 이미 있던 판이다(PLAN §4).

## 4. 지시문 외 변경 · 구현 판단

### 4-1. 구현 판단

1. **파일 나눔이 PLAN §6 표와 다르다.** PLAN 의 `examples.py` 는 없다.
   - 예제 · 학습 결정은 `training.py`, 05 입력 · 목표 선택은 `inputs.py`, 기록 읽기는 `records.py`, 보관은 `archive.py`, 상수는 `protocol.py` 로 나눴다(각 400줄 미만).
   - 05 받기 검사는 PLAN 의 `research.py` 수정 대신 새 `app/ml_evidence/forward_artifacts.py` 로 분리했다. OCI 가 torch · sklearn 없이 불러와야 하고, 02 · 03 · 04 등록 계약 코드를 건드리지 않기 위해서다.
2. **초기 조회 범위 = 2014-04-10(05 KOSPI 저장일 첫날 = 연구 축 첫날) ~ 실행일.** PLAN §2 의 "응답 = 전체 이력"은 공급자 동작 설명이다. 축 밖 행은 쓸 수 없어 요청 시작을 축 첫날로 했다.
   - 실제 반환: 가장 긴 5종은 2,999행 · 첫날 2014-07-30(요청 시작보다 늦음). 원인은 확인하지 않았다.
3. **기록 시각(검증자 r1 F1 정정 뒤)**: `times.published_at` = 파일 쓰기 시작 직전 시각(하한). 실제 공개의 상한 = 놓인 뒤 찍은 영수증 `confirmed_at`. 영수증 시각 < 마감인 FORWARD_RESEARCH 만 주 기록이고, 아니면 성과 · 학습에서 뺀다(§4-5).
4. **D 의 정의**: 그 묶음이 보관한 거래일 파일 기준 `expected_previous_trading_day(오늘 KST)`(05 '최근 완료 거래일'과 같은 규칙). 다음 거래일을 14일 안에서 못 찾으면 PENDING_CALENDAR(예측 없음).
5. **재시도 범위**: 주 기록에서 **예측 실행이 실패(FAILED)** 했고 · 같은 모델 판에서 그 방법을 읽을 수 있고 · 아직 재시도하지 않은 방법만, 마감 전 · 같은 입력 · 같은 판일 때 한 번 재시도한다. DATA_SHORT · ENV_MISMATCH · NOT_RUN_ENV · 학습 실패는 같은 판에서 다시 해도 같으므로 재시도하지 않는다.
6. **복구(REPAIR)**: 최신 판에서 OK 가 아닌 방법만 같은 예제 묶음으로 다시 학습한다. 정상 방법 파일은 해시 확인 뒤 bytes 그대로 옮기고, 그 파일을 만든 라이브러리 판 기록도 함께 옮긴다. 하나도 못 고치면 판을 만들지 않는다. 달 학습 기회와는 무관하다.
7. **월별 예제 파일**: 초기 예제(약 8MB)를 다시 쓰지 않고 해시 참조(`initial_examples`)로 잇는다. 읽을 때 두 파일 해시를 기록과 대조한다.
8. **`SAME_DATA_HASH` 분기**: 새 예제가 있으면 해시가 달라 실제로는 닿지 않는 방어 코드다. "같은 자료면 다시 fit 하지 않음"은 새 예제가 없을 때 학습하지 않는 경로(NO_NEW_TRAINING_EXAMPLES)로 시험했다.
9. **CLI rc**: 05 CLI 와 같은 표 + `SKIPPED_TOO_LATE` · `PENDING_CALENDAR` · `NO_INPUT` · `NO_MODEL` · `NO_EVIDENCE` = 2. `CohortError` · `BootstrapRefused` · `ClockBehind` = CHECK_REQUIRED(2) · `Busy` = BUSY(3).

### 4-2. 독립 검토 1회 반영(2026-10-23 · HIGH 0 · MEDIUM 4 · LOW 3 · 모두 고침)

| 등급 | 지적 | 고친 내용 · 시험 |
|---|---|---|
| MEDIUM | 복원 대조 실패를 기록만 하고 그 방법을 계속 씀 | 실패 방법 = `RESTORE_MISMATCH`(예측 · 비교 제외 · 복구 대상) · `test_failed_restore_check_blocks_the_method` |
| MEDIUM | 복구 판이 옮긴 파일에 현재 라이브러리 판을 적어 ENV_MISMATCH 를 우회 | 방법별 라이브러리 판을 상태에 기록 · 옮길 때 함께 옮김 · `Loaded` 가 방법별 판으로 대조 · `test_repair_keeps_library_version_of_copied_files` |
| MEDIUM | 같은 날 재실행이 재시도 · 부가 기록을 계속 새로 씀 | 진단 · 부가 · 재시도 이미 쓴 것 집합으로 막음 · 재시도 조건 = 예측 실행 실패 + 그 판에서 읽을 수 있음 · 시험 3곳(부가 재실행 · 학습 실패 그대로 · 실패 재시도 반복) |
| MEDIUM | 성숙 못 한 항목마다 모든 뒤 묶음 창을 풀어 메모리 · 시간 무한 증가 | 읽는 묶음 = 기준일 D+20 이상 · D+120일 이하 · 원래 공개 순으로 하나씩 읽고 첫 통과에서 멈춤 · 고정 표본 줄만 기억 · `test_target_reads_only_windows_that_can_hold_D` |
| LOW | 같은 날 재실행이 그 달 학습을 쓸 수 있음 | 유효 실행 = 마감 전 + 아직 주 기록이 없는 종목의 입력 있음 · `test_rerun_same_day_is_not_a_valid_training_run` |
| LOW | 성숙 목표가 상태 글자 OK 줄만 봄 | 창 내용(행)으로 판단(입력도 같음) · NO_NEW_ROW 줄의 온전한 창 사용 · `test_target_uses_window_content_not_status_label` |
| LOW | PC_ONLY 표시가 등록만으로 0 | `local_state`: 미등록 수 · 등록 묶음 · `oci_confirmed = null` · "확인 전 = 모두 PC_ONLY" |
| 시험 | 마감 경계 시험이 멈춘 시계뿐 | `test_started_before_cutoff_but_published_after_is_diagnostic` 추가 |

검토가 "확인됨"으로 적은 것: 입력 cutoff 엄격 비교 · 목표 끝 < D · 가용 ≤ 학습 시작 · 진단 · 부가의 성과 · 학습 제외 · 소급 없음 · Q2 선택 · 한 창 · 첫 평가 고정 · 월 1회 · 같은 행 MAE · 받기 검사 · 한 번 쓰면 끝.

### 4-3. 변이 시험(scratch 사본 · 내용 쓰기 + utime 복원 · PYTHONDONTWRITEBYTECODE)

- 최종 목록 78종(기존 63 + r1 정정분 14 + r2 정정분 2 − 정정으로 대체된 옛 규칙 1) = **74 잡힘 + 동등 4**.
- 동등 4:
  - `forward_artifacts.classify` 의 normpath 검사 제거 — 정규식 전체 일치(`..` · 빈 칸 · 점 경로 불허)가 같은 경로를 이미 거부한다.
  - 전향 후보 판정 `published < 마감` 을 `<=` · `계산 시작 < 마감` · `not late_now` 로 바꾼 3종 — 놓기 직전 재검사(`before_link`)가 마감 뒤 공개를 막아 결과 파일이 같다. 바깥 판정은 이미 늦은 경우 임시 파일을 쓰지 않는 빠른 길이다.
- 더해 본 동등 1종(목록 밖): 학습 예제 가용 시각에 영수증 시각 대신 쓰기 시작 시각을 쓰는 변이 — 유효 기록의 영수증은 D 다음 거래일 15:30 전이고 목표 계산은 D+20 뒤라, max() 결과가 늘 같다.
- 첫 회 생존 5종 · 검토 뒤 생존 1종 · 정정 뒤 생존 1종(영수증 없는 기록 + 마감 뒤 run)은 시험을 더해 모두 잡았다.

### 4-4. 지시문 외 변경 — 05 첫 정기 실행 운영 확인 기록(사용자 요청 2026-10-23 10:30)

- 사용자가 "OCI 에서 동작한 것 확인까지도 같이" 요청했다. 개발자가 `ssh oci-krx` 읽기 명령(crontab · 로그 tail/grep · 보관소 ls · `verify`)으로 확인했다(OCI 쓰기 0).
- 결과(§8-5)를 05 결과서 · 05 PLAN · STATE · PROGRAM_TRUTH 의 "정기 운영 확인 대기" 문구 자리에 교체로 반영했다. 설계자 판정 원문 인용 2곳은 그대로 뒀다.
- POC5-04 공식 R0 는 이 단계와 별개로 2026-10-23 14:29 실행했다(COLLECTION_OK · POC5-04 결과서 §10 · 이 단계 종료의 선행 조건 아님).

### 4-5. 검증자 r1 정정(2026-10-23 · F1 · F2 · F3 + 같은 종류 · 정정 독립 검토 1회 반영)

| ID | 원인 | 정정 | 시험 |
|---|---|---|---|
| F1 · P2 | 공개 시각 · 전향 여부를 쓰기 전에 확정 → 느린 쓰기로 실제 공개가 마감을 넘어도 전향 기록 | ① `write_once(before_link)`: 임시 파일 쓰기 · fsync 가 끝난 뒤 놓기 직전 `시계 < 마감` 재검사 · 아니면 놓지 않고 진단 기록으로 씀. ② 놓은 뒤 시각으로 **공개 확인 영수증**(`.receipt.json` · 예측 파일 sha256 · `confirmed_at` = 공개의 상한)을 항상 남김. ③ 주 기록 · 재시도 · 학습 · 보고는 영수증이 있고 해시 · id · D 가 맞고 `published_at ≤ confirmed_at < 마감`(실제 해석 비교)일 때만 셈. ④ 놓은 뒤 영수증 전 중단 = 다음 run 이 그 마감 전이면 확인(`confirm_pending`) · 마감 뒤면 미확인으로 남김 · 영수증이 이미 있으면(마감 뒤 확인 · 손상 포함) 다시 확인하지 않음. ⑤ 학습 예제 가용 시각 = max(영수증 시각, 목표 계산 시각). | 쓰기 지연 → 진단 · 놓은 뒤 지연 → 미확인 · 시계 역행 run 거부 · 다음 run 확인 · 마감 정각 영수증 · 하한 위반 · 깨진 · 객체 아닌 · 시각 형식 아닌 영수증 · 영수증 뒤 바뀐 파일 |
| F2 · P2 | run 의 읽기 → 학습 결정 → 공개를 단일 실행으로 보호하지 않음 | 연구 폴더 단일 실행 잠금(`.run.lock` · flock · 기다리지 않음)을 쓰는 명령 4종(`run` · `bootstrap.fetch` · `cohort.select` · `archive.register`)에 `@exclusive` 로 적용 · 다른 실행 중 = `P.Busy` · 아무것도 쓰지 않음 · CLI rc 3 | 다른 **프로세스**가 잠금을 쥔 동안 4종 모두 Busy · 파일 목록 그대로 · 풀린 뒤 정상 |
| F3 · P3(r1 · r2 잔여) | 첫 해석일을 가격 기준일 D 로(r1) · 정정 뒤에도 쓰기 시작 시각(하한)으로(r2 · 자정을 넘는 공개에서 하루 이름) 계산 | 가장 이른 주 기록의 **공개 확인 영수증 시각**(놓인 뒤 · 공개의 상한)의 KST 날짜 + 3개월 · `first_forward_D` · `first_forward_published_kst` 칸. 같은 종류: 재시도 연결 시각 `retried_at` 도 재시도 기록의 영수증 시각으로 · 주 기록이 내보내는 칸 = `write_started_at`(하한) · `visible_by`(상한)로 이름을 나눠 하한을 공개 시각으로 잘못 쓰지 않게 함 · 다음 run 이 늦게 확인한 기록은 날짜가 늦어질 수 있으나 해석일을 앞당기지 않음 | D 10-22 · 공개 10-23 → 2027-01-23 · UTC 날짜가 하루 이른 경우(16:00Z) · 토 23:59:59 쓰기 시작 → 일 00:00:01 공개(흐름 · 보고 단위 두 곳) → 2027-01-25 · 재시도 `retried_at` = 영수증 시각 |
| 같은 종류 | 시계가 뒤로 가면 마감 판정을 믿을 수 없음 | 연구 폴더에 남은 가장 늦은 기록 시각(실행 종료 · 공개 · 확인)보다 지금이 이르면 `ClockBehind` · 쓰기 0 | 위 F1 시험 안 |

정정 독립 검토(1회 · HIGH 0 · MEDIUM 1 · LOW 4 · 모두 고침):
- MEDIUM: 깨진 영수증을 05 받기 검사가 다시 해석하다 예외 → JSON 객체 해석 실패를 문제 문자열로 돌림(PC 등록 · OCI 받기 모두 CHECK_REQUIRED).
- LOW: 깨진 영수증이 기록 읽기 전체를 멈춤 → 그 기록만 미확인 · 확인 시각 하한(≥ 쓰기 시작) 검사 · 마감 뒤 확인도 영수증으로 남겨 재확인 차단.
- LOW: 영수증이 같은 id · D 의 다른 종류 파일(run 기록)을 가리켜도 통과 → 가리키는 파일의 schema · protocol 까지 확인.
- LOW: CLI 결과 줄에 공개 확인 칸 없음 → `publication_confirmed` · `confirmed_at` · `confirmed_earlier` 추가 · 전향 후보 기록의 `status` = `FORWARD_CANDIDATE` + `validity_rule` 문장(영수증 없이 읽는 쪽이 성과로 세지 않게).
- LOW: 낡은 설명(`forward.py` 머리말 · PROGRAM_TRUTH) → 교체.

## 5. 알려진 한계 / 미완성

1. **두 번째 사본은 16파일까지**: 2026-10-23 업로드 · 양쪽 복원으로 산출물 16파일(§8-3의 13 + §8-6의 3)은 PC_ONLY 해소(§15). 이후 run 이 만드는 파일은 `archive --upload` 전까지 PC_ONLY 이며, 같은 형식 · 경로의 추가 보관은 매번 새 승인 없이 한다(판정 §7-5).
2. **성과 · 월별 학습 실제 동작은 아직 없다**: 첫 성숙 = 2026-11-19 종가 뒤. 첫 월별 학습은 그 뒤 11월(또는 12월) 첫 유효 실행. 이 단계 종료 조건이 아니다(설계 §12-6).
3. **마감 직전 학습 시간**: 유효 실행으로 판정한 뒤 학습이 길어져 공개가 마감을 넘으면, 그 달 학습은 이미 한 것으로 남고 기록은 진단이 된다. 실측 초기 학습 6.2초라 실제 영향은 작다.
4. **초기 회고 예제는 PIT 가 아니다**: 2026-10-23 한 번 받은 판(수정주가 · change = 같은 응답 계산)이다. 당시 가용 자료라고 주장하지 않는다(설계 §3-2).
5. **보고서의 비교 · 보조 표는 성숙 행이 생겨야 의미가 있다**: 지금 MAE = null · 첫 누적 해석 시점 = 2027-01-23(첫 공개 확인일 2026-10-23 KST + 3개월). 10:20 · 11:26 실제 보고서 파일은 각각 당시의 가격 기준일 · 쓰기 시작 시각 규칙으로 생성된 파일 그대로 보존한다. 새 코드의 조회와 다음 run 보고서부터 공개 확인일 규칙을 쓴다. 기존 파일을 재측정해 두 보고서의 값이 모두 같다고 확인한 것으로 쓰지 않는다.
6. **시계는 믿는다는 전제**: 마감 판정은 PC 벽시계다. 연구 폴더에 이미 남은 기록보다 이른 시각이면 아무것도 쓰지 않고 멈추지만(ClockBehind), 앞으로 틀린 시계까지 잡지는 못한다.
7. **첫 기록의 영수증은 다음 run 이 남겼다**: 10:20 기록은 정정 전 코드라 영수증이 없었고, 11:26 run 이 "놓여 있음"을 확인해 남겼다(확인 시각 11:26:13 = 공개의 상한 · 마감 전). 영수증 해시는 **11:26 에 확인한 파일의 내용**을 묶는다 — 10:20 부터 11:26 까지 파일이 한 번도 바뀌지 않았음을 증명하지는 않는다. 기록의 유효성은 마감 전 확인된 그 파일과 최종 검사 규칙에 근거한다(설계자 RESULT 판정 §2).

## 6. 다음 검증자(Codex)에게 알릴 점

1. **시각 경계**: 잠금 → 시계 역행 검사 → 입력 cutoff(첫 시계값) ≤ 계산 시작 → 미확인 전향 기록 확인 → 성숙 → 입력 선택 → 학습 결정 → 예측 시작(학습 완료 이하 확인) → 쓰기 시작 시각 → 임시 파일 · fsync → **놓기 직전 마감 재검사** → 놓기 → **영수증(놓인 뒤 시각)**. 영수증 시각 < 마감만 주 기록.
2. **누출 경로 표**(시험 이름은 §9):
   - 입력: OCI 공개 · PC 수신 둘 다 cutoff 이하(실제 시각 해석 비교) · 기준일 D 묶음 창만 · 창 D-60..D 검사.
   - 학습: 초기 = 축 끝 D · 목표 끝 < D · 가용 = 조회 관측 시각 / 월별 = 주 전향 기록 × 성숙 목표 · 목표 끝 < 그 회차 D · 가용 = max(예측 공개, 목표 계산) ≤ 학습 시작 · 진단 · 부가 제외.
   - 목표: 한 창 · 한 축 21종가 · 기준일이 D+20 이상인 묶음만 · 첫 평가 파일 고정.
3. **05 받기 확장**: `accept_upload` 는 kind 가 `FORWARD_RESEARCH_ARTIFACTS` 일 때만 새 검사로 간다. 모델 bytes 는 같은 묶음 training.json 의 해시 참조가 있어야 받는다(load 0).
4. **실제 run 과 코드 판**: 10:20 run = 검증자 r1 이전 코드(영수증 없음) · 11:26 run = r1 정정 코드(첫 기록 공개 확인 · 새 예측 없음). 그 뒤 r2 F3 정정으로 records · report가 바뀌었으며 실제 두 run은 재실행하지 않았다. §9의 전체 회귀는 이번 최종 코드 기준이다.
5. **05 받기 허용 형식에 `prediction_receipt` 를 더했다**: 판정 §6 의 허용 유형 표가 늘었다(경로 `predictions/<D>/<id>.receipt.json` · schema 검사 · 가리키는 예측 파일이 같은 묶음이나 보관소에 있고 같은 id · D 의 예측 기록인지 확인). 설계자 확인이 필요한 변경이다.
6. **변이 동등 4종** 판단(§4-3)을 확인 바람.

## 7. 사용자 확인이 필요한 항목

- 승인 묶음(2026-10-23) 중 남은 것: 설계자 RESULT 판정 뒤 커밋 · push · OCI pull(평일 08:05 ~ 15:45 회피) → 산출물 업로드 · 양쪽 복원 → 종료 기록 커밋 · push. 새로 여쭐 것은 없다.
- 매일 PC 를 켜는 의무는 없다. 켠 날 D 다음 거래일 15:30 전에 `python scripts/run_forward_compare.py run --pull` 을 하면, **최신 D 의 유효 입력(05 수집 · 실제 공개 · PC 수신) · 모델 · 거래일 파일 · 공개 확인이 갖춰진 경우** 그날 기록이 남는다. 시간만 맞으면 늘 새 기록이 생긴다는 보장은 아니다. 토요일 실행도 금요일 자료가 실제 공개 · PC 수신된 뒤이고 다음 거래일 마감 전이어야 한다. 켜지 않은 날 = 예측 없음 · 소급 없음.

## 8. 실제 연결 기록 (2026-10-23 금 · 사용자 승인 묶음 뒤)

### 8-1. 순서 · 결과

| 시각(KST) | 단계 | 결과 |
|---|---|---|
| 10:19 | `select-cohort` | OK · 후보 898 · 24종 = PLAN 표 그대로 |
| 10:19 | `bootstrap-fetch`(24 요청 · 재시도 0) | OK 24 · NO_DATA 0 · FAILED 0 · 6.59초 · 최대 메모리 155,500,544 bytes · 진행 중 봉 각 1행 뺌 |
| 10:19 | 05 `pull`(기존 경로) | 오늘 09:40 정기 수집 `20261023T004002Z_9211e9fb` 받음 · object 30 · 문제 0 |
| 10:20 | `run` | FORWARD_RESEARCH · PRIMARY 24 · INITIAL `mv_e926e0661c261324` · 7.43초 · 최대 메모리 534,298,624 bytes |

- 05 첫 정기 실행 manifest(받은 판): status OK · 모든 자료 OK · 창 1,183/1,183 · 436.3초 · OCI 공개 09:47:18 KST · PC 수신 10:19:57 KST.
- 입력 = 24종 모두 위 묶음(종목별 가장 이른 유효 판). input_cutoff 10:20:12.98 · 쓰기 시작(`times.published_at` = 공개의 하한) 10:20:19.84 · 마감 15:30:00. 실제 공개의 정확한 순간은 측정하지 않았다 — 존재 확인(상한)은 §8-6 의 11:26:13 영수증.

### 8-2. 초기 학습

- 예제 37,692행(BOOTSTRAP_RETROSPECTIVE) · 경계 D = 2026-10-22(모든 목표 끝 < D) · initial_trainable 24 · DATA_SHORT 0.
  - 가장 적은 종목 = 0015K0 328 · 제외 사유 = MISSING_PRICE 만(상장 전 · 반환 시작 전 축 날짜).
- 네 방법 OK. 복원 대조(앞 64행 · 학습 직후 메모리 모델 vs 저장 파일): MEDIAN · HGB · MLP_CPU 차 0.0 · RIDGE 3.5e-18(허용 1e-12).
- 학습 6.2초(학습 시작 10:20:13.56 → 완료 10:20:19.75).
- 별도 확인: 저장 파일만으로 다시 읽어 기록된 입력 feature 로 예측 → 96개(24 × 4) 기록 raw 값과 최대 차 0.0.

### 8-3. 첫 run 산출물(`state/ml/research/poc6_06/` · 13파일 · 11:26 run 3파일은 §8-6 · OCI 보관 · 복원 = §15)

| 경로 | bytes |
|---|---:|
| `cohort_v1/cohort.json` | 22,524 |
| `bootstrap/20261023T011918Z_72843194/prices.json` · `fetch.json` | 2,872,270 · 8,506 |
| `examples/20261023T012013Z_6eb886a0.json` | 8,120,699 |
| `models/mv_e926e0661c261324/` hgb.joblib · mlp_state.pt · ridge.json · median.json · mlp_norm.json · training.json | 93,472 · 12,693 · 12,545 · 1,660 · 364 · 4,846 |
| `predictions/2026-10-22/20261023T012012Z_f9953001.json` | 107,303 |
| `reports/…f9953001.json` · `runs/…f9953001.json` | 7,546 · 2,023 |

### 8-4. 바뀌지 않은 것(PC 실측)

- 02 · 03 · 04 공식 22파일: 크기 · sha256 = 등록 목록과 같음 22 · 다름 0.
- 라이브 시장 DB `state/market/market_data.sqlite` 마지막 수정 = 2026-10-20 22:58(이번 작업 전) — 읽기는 mode=ro 만.
- 05 수집 · 02 · 03 · 06 재사용 코드(`daily*.py` · `research.py` · `reentry_review/` · `d20_pooled/` · `price_basis_check/` · `market_data_fdr.py`) git diff 0.
- OCI 쓰기 · cron · PUSH · 화면 · API 변경 0.

### 8-5. 같은 날 OCI 동작 확인(개발자 ssh 읽기 · 2026-10-23 10:30 KST)

| 작업(cron) | 오늘 결과 |
|---|---|
| 08:10 시장 배치 | success · 가격 기준일 2026-10-22 · 가격 결과 성숙 954행 |
| 08:30 시장 브리핑 | sent |
| 09:15 보유 OPEN | sent · 가격 29/32(실패 0) · "이전 상태 비교 불가(date_mismatch)" 경고 = 10-14 부터 매일 같은 기존 모양 |
| 09:20 KRX 보강 | ok · 10-22 이미 확보(재조회 없음) |
| 09:30 · 10:30 급락 알림 | sent · sent |
| 09:40 05 수집(첫 정기 실행) | OK · 창 1,183/1,183 · 436.3초 · 최대 RSS 137,848 KiB · 수급 20/20일 · 09:47:18 공개 |

- OCI 보관소: 묶음 5 · 미완료 폴더 0 · `.incoming` 0 · 21M · 디스크 여유 39G · 메모리 954MB 중 사용 405MB(조회 순간) · 배포 판 `c77a71f3`.
- 같은 묶음 `verify`: OCI OK · PC OK.

### 8-6. 검증자 r1 정정 뒤 실제 run(2026-10-23 11:26 KST · 정정 코드 · 마감 15:30 전)

- 결과 `ALREADY_RECORDED`(새 예측 없음 · 학습 KEEP = 같은 달 · 성숙 PENDING_NOT_DUE 24) · 2.29초 · 최대 메모리 348,880,896 bytes.
- `confirmed_earlier`: 10:20 기록 `20261023T012012Z_f9953001` → 영수증 `confirmed_at` 2026-10-23T02:26:13.696207Z(11:26:13 KST) · how `LATER_RUN_BEFORE_CUTOFF` · sha256 `8e05083e…6b11bee6`.
- 읽기 결과: 주 기록 24 · 미확인 전향 기록 0. 11:26 당시 쓴 보고서 파일은 그때 규칙(쓰기 시작 시각의 날짜)의 산출물이다.
- 최종 코드의 읽기 전용 `report`(2026-10-23 13:52 KST · 쓰기 0 · 파일 수 16 그대로): `first_forward_D` 2026-10-22 · `first_forward_published_kst`(공개 확인일) 2026-10-23 · `first_interpretation_date` **2027-01-23** · 주 기록 24 · 미확인 0.
- 새 파일 3개: 영수증 643 bytes · `reports/20261023T022613Z_d98f2482.json` 7,625 · `runs/20261023T022613Z_d98f2482.json` 7,262(산출물 합계 16파일 · OCI 보관 · 복원 = §15).

## 9. 검증 실측 (2026-10-23)

| 검사 | 결과 |
|---|---|
| black --check(신규 · 수정 py 18파일 · r2 정정 뒤) | 통과 |
| flake8(같은 범위) | 통과 |
| py_compile | 통과 |
| POC6-06 시험(r2 정정 뒤) | 69 passed(core 42 · flow 27) |
| 05 기존 시험(store 32 · daily 46) | 78 passed(위와 함께 147 passed · 44.74초) |
| 변이(r2 정정 뒤 최종 목록) | 78종 · 74 잡힘 · 동등 4(§4-3) |
| 전체 회귀(r2 정정 뒤 최종 코드 · 단독 실행) | **4378 passed** · 실패 0 · 1 warning(기존 starlette 안내) · 703.36초 — 05 종료 때 4309 + 이번 69 |
| (참고) r1 정정 코드의 앞선 1회(변이 시험과 동시 실행 · 고부하) | 4374 passed · 1 failed = `test_poc5_01b_ledger_runner.py::test_ledger_on_off_keeps_body_record_history_db_state_and_order[holdings]` — 끔/켬 두 실행의 `runtime_kst`(초 단위)를 그대로 비교하는 기존 시험 · 이번 변경 범위 밖 · 단독 재실행 3회 25 passed · 위 단독 전체 회귀에서 통과 |

시험이 다루는 계약(대표):
- 표본: 해시 규칙 · 보유 무관 · 고정 뒤 재순위 없음 · 불일치 = 쓰지 않음.
- 입력: 가장 이른 원래 공개 판 · FAILED · cutoff 뒤 공개 · 수신 · receipt 없음 제외 · 재사용 object 의 원래 판 · 손상 → 다음 판 · 가격 기준 변화 · 0 종가 거부 · 영숫자 식별자.
- 성숙: 미도래 · 19일째 · 알려진 D20 값 · 도래 후 결측 vs 확인 필요 · 축 불확실 · 상태 글자 아닌 창 내용 · 읽는 범위 · 정정 판이 와도 첫 평가 고정.
- 학습: 초기 경계(목표 끝 = D 제외) · 06/02 함수와 같은 값(RIDGE ≤ 1e-12 · HGB 같음 · MLP ≤ 1e-6 · 가중치 1/n_d 독립 계산) · 복원 대조 실패 차단 · ENV_MISMATCH · 파일 변조 · DATA_SHORT · 방법별 실패 · 복구(다른 방법 재학습 0 · 라이브러리 판 보존) · 월별(새 예제 없음 = 기회 보존 · 무효 실행 = 기회 보존 · 한 달 1회 · 진단 제외 · 가용 시각 · 초기 예제 참조).
- 기록: 마감 1µs 전 / 정각 · 시작 전 · 공개 후 · 금요일 D → 월요일 마감 · 다음 거래일 미확정 · 같은 날 재실행 · 늦은 진단 1회 · 부가 기록 · 재시도 연결 · 재시도 반복 없음.
- 공개 확인(r1 F1): 쓰기 지연 → 진단 · 놓은 뒤 지연 → 미확인 · 영수증 없는 기록 = 다음 run 이 마감 전이면 확인 · 마감 뒤면 미확인 · 시계 역행 run = 쓰기 0 · 마감 정각 · 하한 위반 · 깨진 · 객체 아닌 · 형식 아닌 영수증 · 영수증 뒤 바뀐 파일.
- 단일 실행(r1 F2): 다른 프로세스가 잠금을 쥔 동안 run · 초기 조회 · 표본 확정 · 보관 등록 모두 Busy · 파일 목록 그대로 · 풀린 뒤 정상.
- 첫 해석일(r1 · r2 F3): 공개 확인일(KST) 기준 · UTC 날짜가 하루 이른 경우 · 자정을 넘는 공개(흐름 · 보고 단위) · 재시도 시각.
- 보고: 같은 행 · 날짜 균형 · null · 깊은 하락 · 보조 묶음 · 진단 · 마감 뒤 기록 제외.
- 보관: 경로 정규화 13종 · schema · 경로 값 · 참조 · 형식 · 받기 공개 / 거부 · 02 · 03 · 04 계약 그대로 · 등록 · 업로드 · OCI 복원 · 내용 바뀐 경로 = CHECK_REQUIRED.

## 10. git 상태 (구현 커밋 직전 실측 · 2026-10-23 · 설계자 RESULT 판정 반영 뒤)

`git status --short --untracked-files=all`:

```text
A  app/forward_compare/__init__.py
A  app/forward_compare/archive.py
A  app/forward_compare/bootstrap.py
A  app/forward_compare/cohort.py
A  app/forward_compare/forward.py
A  app/forward_compare/inputs.py
A  app/forward_compare/mature.py
A  app/forward_compare/models.py
A  app/forward_compare/protocol.py
A  app/forward_compare/records.py
A  app/forward_compare/report.py
A  app/forward_compare/training.py
A  app/ml_evidence/forward_artifacts.py
M  app/ml_evidence/store.py
M  app/ml_evidence/transfer.py
M  docs/ASSUMPTIONS.md
M  docs/KILL_SWITCHES.md
M  docs/PROGRAM_TRUTH.md
M  docs/PROJECT_ORIGIN_INTENT.md
M  docs/STATE_LATEST.md
A  docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_DESIGN_V1.md
A  docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_DECISION_2026-10-22.md
A  docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_RESULT_DECISION_2026-10-23.md
M  docs/ai_plan/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_PLAN_V1.md
A  docs/ai_plan/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_PLAN_V1.md
M  docs/ai_result/POC6/POC6-05_CONTINUOUS_MARKET_DATA_AND_ML_EVIDENCE_RETENTION_RESULT.md
A  docs/ai_result/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_RESULT.md
A  scripts/run_forward_compare.py
A  tests/test_poc6_06_forward_core.py
A  tests/test_poc6_06_forward_flow.py
?? docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md
```

- stage 30경로 = 코드 18(신규 12 + 05 형식 1 + CLI 1 + 시험 2 · 수정 2) · 문서 12(기반 3 · STATE · PROGRAM_TRUTH · 06 설계 · PLAN 판정 · RESULT 판정 · PLAN · 결과서 · 05 PLAN · 05 결과서) · 오른쪽 칸(작업 트리 변경) 없음.
- `??` 1건 = 사용자 소유 handoff 문서(이번 작업과 무관 · stage 하지 않음).
- 이 상태로 구현 커밋 · push 를 한다(RESULT 판정 §4-1). 커밋 기록은 종료 기록에 과거 커밋으로 남긴다.
- 연구 산출물 `state/ml/research/poc6_06/` · 05 보관소 `state/ml/evidence/` 는 git 제외(`.gitignore`).

## 11. 검증자 r1 판정 — 2026-10-23

검증자: Codex · 적용: `.agents/skills/krx-verify/SKILL.md`.
기준 HEAD `c77a71f3de400e9b03ed9d2cd410f01d11327591` · staged 29경로(A 20·M 9) · 시작 시 unstaged 0.
설계 V1·PLAN 판정·PLAN·결과서 및 실제 index 코드를 대조했다. 사용자 handoff·비밀 설정·라이브 시장/보유 DB·OCI는 열지 않았다.
아래 재현과 시험은 저장소 밖 index 사본, 임시 05 보관소, 결정적 가짜 가격·시계 및 가짜 원격만 사용했다. 실제 첫 연구 산출물·가중치·기존 기록을 변경하지 않았다.

### 1) A. 기능/산출물 검증

**A-1 지시 일치: 위반 — P2 2건·P3 1건의 코드 결함.**

| ID | 위치(검증 시작 index 소스) | 발견·재현 | 계약 영향 |
|---|---|---|---|
| F1 · P2 | `app/forward_compare/forward.py:203-205`·`:244`; `app/forward_compare/protocol.py:92-96` | 공개 시각과 전향 여부를 먼저 확정한 뒤 JSON 조립·직렬화·임시 파일 쓰기·flush·fsync를 하고 최종 이름으로 공개한다. 이 마지막 쓰기 구간에서 시간이 지나도 다시 판정하지 않는다. 가짜 시계로 2026-10-26 15:29:59 KST에 판정하고, 실제 `os.link` 직전 I/O 지연을 모사해 15:30:01로 진행시킨 결과 `status=OK`, `record_type=FORWARD_RESEARCH`, 저장된 공개 시각 15:29:59, 해당 D의 주 기록 24개가 남았다. 지연 없는 마감 전 대조군은 정상 전향, 마감 후 대조군은 DIAGNOSTIC이다. | 설계 §6·§7·§12-4, 판정 §4-1/3의 **실제 공개 < D 다음 거래일 15:30** 계약을 충족하지 못한다. 예측 계산 중 마감을 넘는 기존 시험은 통과하지만, 파일 공개 지연 경로는 남아 있다. 잠자기·디스크 지연 등으로 실제 공개가 늦어져도 주 비교·LOGGED_FORWARD 입력으로 읽힐 수 있다. 오늘 10:20의 실제 기록이 이 문제를 겪었다고 판정한 것은 아니다. |
| F2 · P2 | `app/forward_compare/training.py:240`·`:294-321`; `app/forward_compare/forward.py:120-142`; `scripts/run_forward_compare.py:144-153` | run의 읽기→학습 결정→모델/예측 공개를 단일 실행으로 보호하지 않는다. 신규 성숙 예제가 있는 11월의 같은 임시 연구 폴더에 두 프로세스를 실행하고 `versions()`에서 기존 판을 읽은 직후만 동기화했다. 두 실행의 시각을 1ms 다르게 두면 둘 다 정상 종료하고 `MONTHLY` 모델 판 **2개**가 생긴다. 둘의 `trained_month`는 `2026-11`, 학습 자료 해시는 `a1a3cc5b…444b1`로 동일하다. 같은 D `2026-11-23`의 예측 파일 2개도 각각 PRIMARY 항목을 담았다. `records.primaries`는 그중 최초 하나를 선택하므로 MAE가 두 배로 집계된다고 주장하지 않는다. | 설계 §5·§7, 판정 §5의 **월 최대 1회**, 같은 자료의 불필요한 재학습 방지 및 같은 요청 재실행 계약 위반이다. `write_once`는 같은 파일명 덮어쓰기만 막고, 서로 다른 실행 ID/모델 판으로 생기는 중복은 막지 않는다. 최초 시험에서는 목표 파일 동시 생성 충돌도 관측됐으며, 최종 재현은 목표를 이미 확정한 정상 상태에서 수행했다. |
| F3 · P3 | `app/forward_compare/report.py:177-179` | `first_interpretation_date`를 최초 실제 예측 공개일이 아니라 주 기록의 가격 기준일 D에 3개월을 더해 계산한다. 정상 임시 기록의 최초 공개는 2026-10-23 10:00 KST이고 D는 10-22인데 코드 산출은 `2027-01-22`다. 설계상 날짜는 실제 예측일 기준 `2027-01-23`이다. | 설계 §9의 **최초 실제 예측일부터 3개월 뒤** 계약과 다르다. 결과서 문장만의 오기가 아니라 CLI/report 코드가 계속 잘못된 기준으로 결과 필드를 생성하는 문제다. 문서의 계약상 날짜는 검증자가 직접 정정했으며 코드 결함은 별도로 남긴다. |

- **A-2 보고 정확성: 위반(동작 완료 주장).** 파일 목록·29경로·시험 수·형식 검사 및 모듈 규모는 실제와 일치한다. 다만 공개 마감·월 1회·최초 해석일 완료 주장은 F1~F3의 조건에서 코드와 다르다. 실제 연결·OCI 운영 확인 수치는 개발자 보고를 근거로 인용했으며 검증자가 OCI나 라이브 DB에서 재측정한 수치로 쓰지 않는다.
- **A-3 산출물 정합성: 위반.** 위 경로에서 주 기록·모델 판·리포트 날짜가 승인된 계약과 다르게 생성된다. 관련 시험 통과와 별개로 실제 수정 소스의 임시 재현에서 확인됐다.
- **A-4 금지사항 위반: 없음.** 새 의존성·운영 가격/보유/원장 쓰기·공개 API·UI·PUSH·PARAM·cron 변경은 없다. PC 학습과 05 보관 허용 확장은 판정 범위다. 이번 검증에서는 실제 추가 조회·SSH·업로드·커밋·push를 실행하지 않았다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 방법별 실패·환경 불일치를 다른 방법 값이나 0으로 채우지 않는다. 손상 가격/축과 입력 누락도 구분한다. F1은 공개 경계 확정 시점의 결함이다.
- **B-2 단일 책임 위반: 없음.** 표본·초기 자료·입력·학습·예측·성숙·기록·보고·보관 책임이 나뉜다. PLAN과 다른 파일 나눔의 사유도 구현과 일치한다.
- **B-3 파일 책임 과다: 없음.** 새 PC 모듈 최대 `training.py` 388줄, 기존 보관 모듈은 store 557·transfer 453줄, 시험은 915·634줄로 KS-10 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 기존 운영 러너·배치·화면·API는 변경되지 않았다. OCI 받기용 `forward_artifacts`는 표준 라이브러리와 store만 사용하며 모델을 load하지 않는다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·새 패키지·시험은 모두 index에 추적돼 실행 안내 경로와 일치한다. 이동/삭제·Dockerfile 변경은 없다. OCI 도구 배포·업로드·양쪽 복원은 대기로 명시돼 있다.
- **B-6 기술부채/구조적 퇴행: 있음 — F2.** 겹친 실행이 같은 월·같은 데이터의 모델 판과 주 기록 후보를 중복 생성한다. 단순 파일명별 write_once로는 회차 단위 계약을 지키지 못한다. 그 밖의 stale 성과 재사용·튜닝 추가는 발견되지 않았다.

### 3) 기반 문서 준수

- 판정 §1의 한정 예외가 PROJECT_ORIGIN_INTENT·KILL_SWITCHES·ASSUMPTIONS에 원문·날짜·출처를 유지해 추가됐다. Q6 OPEN·운영 ML 승격 금지·기존 연구 판정은 그대로다.
- 신규 문서는 승인된 설계·판정·PLAN·결과서이며 별도 handoff는 만들지 않았다. MongoDB·새 UI 프레임워크·새 의존성 흔적이 없다.
- **문서 메타 직접 정정(반려 사유 제외):** STATE 첫머리에 남은 05 정기 운영 확인 대기 1곳, PROGRAM_TRUTH의 OCI 증거 폴더·cron·두 표 '없음' 4곳을 같은 문서의 후속 배포/운영 확인 기록과 맞췄다. 과거 판정 원문은 변경하지 않았다. 결과서 §5-5의 계약상 해석일은 2027-01-23으로 정정하고 현재 코드 출력 01-22는 F3로 분리했다. 문서 숫자·메타만을 이유로 반려하지 않았다.

### 4) 코드 안전성

- **위험 수준: MEDIUM.** F1의 전향 시각 계약 위반과 F2의 중복 실행 계약 위반이 확인됐다. 실제 운영 ML이나 발송으로 확장된 위험을 주장하는 것은 아니다.
- 검증자가 직접 실행: **관련 시험 131 passed, 2 warnings in 44.61s**(이번 53 + 기존 05 78); **black --check·flake8·py_compile 18파일 통과**; F1 공개 I/O 지연 재현과 마감 전/후 대조; F2 두 프로세스 겹침 재현; F3 실제 공개일과 리포트 필드 대조; Git 범위·추적·줄 수 확인.
- 경고 2개는 기존 Starlette/httpx 안내와 격리 환경의 joblib 물리 코어 수 조회 실패 후 논리 코어 사용 안내다. 시험 실패는 없다.
- 개발자 최종 전체 회귀 **4,362 passed** 및 변이 **63종 중 62 탐지·동등 1** 근거를 재사용했다. 전체 회귀·변이 전체·공식 연구 실행은 반복하지 않았다. 경로 검사 중 normpath 검사 제거 변이는 나머지 fullmatch가 같은 경로를 거절해 결과가 같다는 설명과 코드가 일치한다.
- 근거: `/private/tmp/poc606-r1-verify-yfaflnr6/`의 `scope.json`, `related.log`, `static-checks.json`, `lines.json`, `repro_publication.py`·`publication-repro.json`, `publication_controls.py`·`publication-controls.json`, `repro_overlap3.py`·`overlap-repro.json`·`repro-overlap3/`, `interpretation-repro.json`, `check.json`.

### 5) 범위 폭주

- **폭주 수준: NONE.** 사전 고정 보조 표·자료 유형 한정 확장·파일 책임 분리와 사용자 요청에 따른 05 운영 확인 기록은 설명된 범위다. 실제 OCI 작업 승인을 이번 검증이 대신하지 않는다.

### 6) 종합 판정

**REJECTED — 코드 결함 P2 2건(F1·F2), P3 1건(F3).** 문서의 줄 수·수치·메타 오기 때문에 반려한 것이 아니다. 검증자는 운영 코드·시험을 직접 수정하지 않았고, 위 문서 메타 정정과 이 검증 기록만 반영했다.

### 7) 사용자에게 한마디

다음은 개발자의 코드 정정과 검증자 재검증이다. 가장 큰 문제는 실제 공개가 마감 뒤인데 주 기록으로 남는 경로와, 겹친 실행에서 같은 달 학습을 두 번 하는 경로다. 현재의 실제 첫 24종 기록이 손상됐다고 판정한 것은 아니며, 커밋·push·OCI 작업은 하지 않았다.

## 12. 검증자 r2 판정 — 2026-10-23

검증자: Codex · 적용: `.agents/skills/krx-verify/SKILL.md` · 기준 HEAD `c77a71f3de400e9b03ed9d2cd410f01d11327591`.
대상 = staged 29경로(A 20·M 9) · 시작 시 unstaged 0. 설계·PLAN 판정 및 변경 없는 소스는 r1과 같으며, PLAN은 상태 줄만 바뀌었다. r1 대비 정정 코드·시험·문서와 기존 재현을 대조했다. §11은 보존했다.
실제 연구 산출물·05 라이브 보관소·시장/보유 DB·비밀 설정·사용자 handoff·OCI는 열거나 바꾸지 않았다. 아래 재현·시험은 저장소 밖 index 사본과 임시 보관소·가짜 가격·시계·원격으로만 실행했다.

### 1) A. 기능/산출물 검증

**A-1 지시 일치: 위반 — F1·F2는 해소됐고, F3에 잔여 P3 코드 결함 1건이 있다.**

| 항목 | 수정본 확인 | 판정 |
|---|---|---|
| r1 F1 · 실제 공개 마감 | r1과 같은 방식으로 15:29:59 KST에 기록을 준비하고 최종 `os.link` 직전 시각을 15:30:01로 진행시켰다. 수정본은 `SKIPPED_TOO_LATE`, `publication_confirmed=false`, 영수증 확인 시각 15:30:01, 해당 D의 주 기록 0개다. 놓기 직전 재검사·영수증 없는 후보·나중 run의 마감 전/후 확인·깨진 영수증·시계 역행 시험도 통과했다. 성과·성숙·학습은 영수증을 통과한 주 기록만 사용한다. | CLOSED |
| r1 F2 · 월별 중복 학습/기록 | r1과 같은 신규 성숙 예제를 가진 임시 연구 폴더에 두 프로세스를 겹쳤다. 첫 실행이 기존 모델 판을 읽은 직후 잠금을 유지한 상태에서 두 번째 실행은 `BUSY`로 끝났다. 첫 실행만 MONTHLY 학습, 11월 모델 판 1개, 같은 D 예측 파일 1개이며 이후 순차 재실행은 `ALREADY_RECORDED`다. 다른 프로세스가 잠금을 쥔 동안 네 쓰기 함수 모두 Busy·연구 파일 목록 불변인 시험도 통과했다. | CLOSED |
| r1 F3 · 가격 기준일 대신 실제 공개일 | 일반 경로는 D 10-22·공개일 10-23 → 2027-01-23으로 정정됐다. UTC/KST 날짜가 다른 경우도 통과한다. 다만 아래 자정 경로에서 쓰기 시작일을 실제 공개일로 쓰는 문제가 남는다. | PARTIAL — 잔여 P3 |

**F3 잔여 · P3 — 자정을 넘는 쓰기에서 공개일과 최초 해석일이 하루 앞당겨진다.**

- 위치: `app/forward_compare/report.py:154-158`·`:186`; 연결: `app/forward_compare/forward.py:273-274`, `app/forward_compare/records.py:147-148`.
- F1 정정으로 `times.published_at`은 **실제 공개 시각이 아니라 파일 쓰기 시작의 하한**이 됐다. 그런데 report는 계속 주 기록의 이 필드를 실제 공개일로 변환한다.
- 재현: 최초 예측 기록이 없는 임시 연구 폴더에서 금요일 D `2026-10-23`의 입력과 기존 모델로 실행했다. 쓰기 시작은 토요일 `2026-10-24 23:59:59 KST`, 최종 `os.link` 직전 2초의 I/O 지연을 모사해 실제 공개와 영수증 확인은 일요일 `2026-10-25 00:00:01 KST`다. 월요일 15:30 마감 전이므로 전향 기록 자체는 정상 `OK`다.
- 실제 결과는 `first_forward_published_kst=2026-10-24`, `first_interpretation_date=2027-01-24`다. 재현에서 확인한 실제 공개일은 10-25이며 그날부터 3개월인 계약상 날짜는 **2027-01-25**다.
- 사용자 재검증 요청의 F3 기준인 '실제 공개일' 및 설계 §9·r1 F3와 다르다. 결과서 숫자 한 곳만 고쳐도 코드가 계속 같은 오류를 생성한다. 문서 수치만의 반려가 아니다. 오늘 실제 10:20/11:26 기록은 날짜를 넘지 않아 이 재현의 영향을 받았다고 주장하지 않는다.

- **A-2 보고 정확성: 위반(잔여 동작).** staged 29경로·변경 파일·67+78 시험 수·18파일 검사·정정 방식은 실측 및 코드와 일치한다. 다만 F3 완료 주장은 위 경로에서 충족되지 않는다. 실제 11:26 run·OCI 확인 수치는 개발자 근거를 인용하며 검증자가 라이브에서 재측정한 것으로 쓰지 않는다.
- **A-3 산출물 정합성: 위반.** 자정을 넘는 정상 전향 기록에서 리포트의 실제 공개일·최초 해석일이 생성 근거와 다르다.
- **A-4 금지사항 위반: 없음.** 새 라이브러리·API·화면·운영 DB·PUSH·cron 변경은 없다. 영수증 형식은 F1 정정에 직접 연결된 연구 산출물의 한정 확장이다. 설계자 RESULT 확인 항목(§6-5)과 OCI 반영 대기는 유지한다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 깨진·누락된·마감 뒤 영수증은 미확인으로 분리하고 성과/학습에 넣지 않는다. 방법별 실패도 대체값으로 채우지 않는다.
- **B-2 단일 책임 위반: 없음.** 잠금·파일 공개는 protocol, 영수증 검사·주 기록 연결은 records, 날짜/통계는 report로 나뉜다.
- **B-3 파일 책임 과다: 없음.** 새 PC 모듈 최대 training 391줄, 기존 store 557·transfer 453줄, 시험 1,056·778줄로 KS-10 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 기존 운영 경로 변경이 없고 OCI 영수증 검사는 표준 라이브러리·store만 사용한다. 모델 load는 추가하지 않았다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·새 모듈·시험은 모두 index 추적 경로와 맞는다. OCI 영수증 받기 도구 배포·업로드·양쪽 복원은 아직 대기로 명시돼 있다.
- **B-6 기술부채/구조적 퇴행: 없음.** r1의 중복 실행 문제는 해소됐다. F3 잔여는 공개일을 계산하는 필드 선택의 기능 결함이며 별도 구조 위반으로 중복 판정하지 않는다.

### 3) 기반 문서 준수

- r1에서 확인한 한정 예외·원문·출처 및 운영 ML 금지는 유지된다. 신규 문서/라이브러리/프레임워크는 추가되지 않았다.
- **문서 메타 직접 정정(반려 사유 제외):** §5-1의 PC_ONLY 13파일을 §8-3(13)+§8-6(3)의 목록 기준 16파일로 맞췄다. §6의 뒤바뀐 항목 번호와 남은 '동등 1종'을 현재 §4-3의 4종으로 맞췄다. 원본 연구 폴더를 다시 조사한 숫자로 주장하지 않는다.
- 영수증 `prediction_receipt`의 보관 허용 형식 확장은 설계자 RESULT 확인 항목으로 보존한다. 검증자가 새 원격 쓰기를 승인하지 않는다.

### 4) 코드 안전성

- **위험 수준: LOW.** F1 전향 마감·F2 단일 실행의 P2 결함은 해소됐다. 남은 P3는 리포트 날짜 경계 오류이며 예측값·D20 목표·MAE가 바뀐다고 확대하지 않는다.
- 직접 실행: **관련 시험 145 passed, 2 warnings in 49.50s**(이번 67 + 기존 05 78), **black --check·flake8·py_compile 18파일 통과**, F1 기존 공개 지연 재현, F2 기존 두 프로세스 중복 경로 재현, F3 일반 경로 및 자정 경로 대조, Git 추적·줄 수·소스 일치 확인.
- 경고는 기존 Starlette/httpx 안내 및 격리 환경에서 joblib의 물리 코어 수 조회 실패 후 논리 코어 사용 안내다.
- 최종 단독 전체 회귀 **4,376 passed**와 변이 **76종 중 72 탐지·동등 4**는 개발자 근거를 재사용했다. 전체 회귀·변이 전체·공식 실행을 반복하지 않았다. 변이와 동시에 실행한 앞선 회귀의 실패 1건 및 최종 단독 통과 기록도 보존했다.
- 실제 연구 기록·가중치·보유·라이브 DB·OCI를 열거나 쓰지 않았다. 신규 영수증·잠금 재현 자료는 모두 임시 경로에만 남겼다.
- 근거: `/private/tmp/poc606-r2-verify-syhpzfyr/` — `scope.json`, `r1-r2.diff`, `related.log`, `static-checks.json`, `lines.json`, `repro_publication_r2.py`·`publication-repro.json`, `repro_overlap_r2.py`·`overlap-repro.json`, `repro_midnight.py`·`midnight-repro.json`, `check.json`.

### 5) 범위 폭주

- **폭주 수준: NONE.** 공개 확인 영수증·쓰기 잠금·시계 검사와 보관 형식 확장은 r1 정정에 직접 연결된다. 새로운 모델·feature·튜닝·외부 조회·운영 권한을 추가하지 않았다.

### 6) 종합 판정

**REJECTED — F3 잔여 코드 결함 P3 1건(자정을 넘는 실제 공개일 계산). F1·F2 CLOSED.**
검증자는 코드·시험을 직접 수정하지 않았고 문서 메타 정정 및 이 판정 기록만 반영했다. 문서 줄 수·수치 오류 때문에 반려한 것이 아니다.

### 7) 사용자에게 한마디

다음은 개발자의 F3 잔여 정정과 재검증이다. 핵심 P2 두 건은 해소됐으며 남은 것은 자정을 넘는 공개의 리포트 날짜 계산이다. 오늘 실제 첫 기록을 다시 만들거나 전체 회귀를 반복 실행하는 작업은 이번 검증에서 하지 않았다. 커밋·push·OCI 작업도 하지 않았다.

## 13. 검증자 r3 판정 — 2026-10-23

검증자: Codex · 적용: `.agents/skills/krx-verify/SKILL.md` · 기준 HEAD `c77a71f3de400e9b03ed9d2cd410f01d11327591`.
대상 = staged 29경로(A 20·M 9), 시작 시 unstaged 0. 설계·PLAN 판정·변경 없는 구현은 기존 검증 근거를 유지했다. 이번 코드 변경은 records · report 2파일이며, 시험 2파일과 문서 4파일을 포함한 r2 대비 변경을 대조했다. §11·§12는 보존했다.
검증은 저장소 밖 index 사본·임시 05 보관소·가짜 가격/시계/원격에서 수행했다. 사용자 handoff·비밀 설정·라이브 시장/보유 DB·05 보관소·실제 연구 산출물·OCI는 열거나 변경하지 않았다.

### 1) A. 기능/산출물 검증

- **A-1 지시 일치: 통과.** r2 F3 잔여가 해소됐고, r1 F1·F2 해소도 유지된다.

| 항목 | 확인 결과 | 판정 |
|---|---|---|
| F3 자정을 넘는 공개일 | r2 재현 스크립트를 수정본의 저장소 밖 사본에서 실행했다. 쓰기 시작 `2026-10-24T14:59:59Z`(토 23:59:59 KST), 실제 최종 파일 공개/영수증 `2026-10-24T15:00:01Z`(일 00:00:01 KST)일 때 `status=OK`, `first_forward_published_kst=2026-10-25`, `first_interpretation_date=2027-01-25`다. 기존 r2 출력의 10-24/01-24가 재현되지 않는다. | CLOSED |
| 주 기록·재시도 시각 | 주 기록은 `write_started_at`(하한)과 `visible_by`(영수증 상한)를 나눠 내보낸다. 보고서와 학습 가용 시각은 visible_by를 사용하고, 재시도의 retried_at도 해당 재시도 영수증 시각이다. 기존 호출처에 제거된 주 기록 published_at 참조가 남지 않았고 재시도 시험도 통과했다. | 일치 |
| F1 공개 마감·영수증 | 해당 코드와 보관 검사 형식은 r2와 같으며, 마감 전/정각/뒤·쓰기 지연·영수증 누락/손상·시계 역행 및 학습 제외 시험이 이번 관련 회귀에서도 통과했다. | CLOSED 유지 |
| F2 단일 실행 | 잠금·월별 학습 코드는 r2와 같다. 다른 프로세스가 잠금을 잡은 동안 네 쓰기 함수가 Busy로 차단되는 시험과 월별 1회·동일 날짜 재실행 시험이 다시 통과했다. r2의 두 프로세스 재현에서 월별 모델/예측 파일 각각 1개인 근거를 유지한다. | CLOSED 유지 |

- **A-2 보고 정확성: 통과.** Git 범위는 staged 29·A 20/M 9·unstaged 0이며 파일 목록과 일치한다. 이번 69개와 기존 05 78개를 합한 시험 수 및 18파일 정적 검사도 실측과 맞는다. 실제 run·OCI 확인은 개발자의 기존 근거를 인용하며 검증자가 재실행/재측정한 것으로 쓰지 않는다.
- **A-3 산출물 정합성: 통과.** 일반 날짜·UTC/KST 날짜 차이·자정을 넘는 공개 모두 영수증 확인일 기준으로 계산된다. 늦은 run이 확인하면 날짜가 늦어질 수 있다는 보수적 한계는 명시돼 있고, 쓰기 시작일로 해석일을 앞당기는 경로는 해소됐다. 기존 불변 보고서 파일과 새 코드 조회 결과도 구분했다.
- **A-4 금지사항 위반: 없음.** 코드·시험 원본 직접 수정, 신규 의존성, 실제 추가 조회, 라이브 DB·보유 쓰기, 커밋·push·OCI 작업은 하지 않았다. 운영 경보·PUSH·화면·API·cron도 변경되지 않았다.

### 2) B. 구현 규칙/구조 품질 검증

- **B-1 fallback 위반: 없음.** 영수증이 없거나 무효이면 공개 시각을 쓰기 시작 시각으로 대체하지 않고 주 기록에서 제외한다. 방법 실패·자료 부족도 대체값으로 채우지 않는다.
- **B-2 단일 책임 위반: 없음.** records가 시각 의미를 분리하고 report가 공개 확인일을 계산한다. 운영 코드로 분석 책임을 옮기지 않았다.
- **B-3 파일 책임 과다: 없음.** 새 PC 모듈 최대 training 391줄, records 198·report 199줄이며 기존 store 557·transfer 453줄, 시험 1,077·809줄로 KS-10 기준 안이다.
- **B-4 실험/운영 경계 위반: 없음.** 기존 운영 경로 변경이 없고, OCI 보관 코드는 모델을 load하지 않는다. 연구 한정 예외가 유지된다.
- **B-5 배포/실행 경로 영향: 없음.** CLI·모듈·시험 모두 index에 추적돼 실행 안내와 일치한다. OCI 받기 도구 반영·업로드·양쪽 복원은 후속 단계로 남아 있다.
- **B-6 기술부채/구조적 퇴행: 없음.** 공개일·재시도 연결이 영수증 시각으로 일관되고, 쓰기 시작 시각과 구분된다. 기존 기록·가중치·공식 연구 결과를 덮지 않았다.

### 3) 기반 문서 준수

- 설계·판정 및 세 기반 문서의 한정 예외는 r2와 같다. Q6 OPEN·운영 ML 승격 금지·기존 02/04 판정·미완료 요구도 유지된다. 새 문서/라이브러리/프레임워크는 추가되지 않았다.
- 문서 메타 직접 정정: §5-5에서 과거 두 보고서의 값이 모두 같다고 단정한 문장을 당시 규칙·불변 파일과 새 조회 규칙을 구분하는 설명으로 바꿨다. §6-4의 '11:26 뒤 코드 변경 없음'은 이번 records/report 변경 및 실제 run 재실행 없음으로 맞췄다. 원본 산출물을 열어 확인한 숫자라고 주장하지 않는다. 이 문서 메타 정정을 반려 사유로 삼지 않았다.
- `prediction_receipt` 보관 허용 형식 추가와 공개 확인일의 보수적 의미는 설계자 RESULT 확인 항목으로 유지한다. 검증 판정은 실제 OCI 반영 승인을 대신하지 않는다.

### 4) 코드 안전성

- **위험 수준: NONE(이번 구현 검증 범위의 미해결 코드 결함 없음).** 실제 OCI 반영·업로드·양쪽 복원까지 완료됐다는 판정은 아니다.
- 검증자가 직접 실행: **관련 시험 147 passed, 2 warnings in 49.79s**(이번 69 + 기존 05 78), **black --check·flake8·py_compile 18파일 통과**, r2 자정 경계 재현, 호출처 전수 검색, 줄 수·Git 추적·최종 소스 일치 검사.
- 경고는 기존 Starlette/httpx 안내 및 격리 환경에서 joblib의 물리 코어 수 조회 실패 후 논리 코어 사용 안내다. 시험 실패는 없다.
- 개발자의 최종 단독 전체 회귀 **4,378 passed** 및 변이 **78종 중 74 탐지·동등 4** 근거를 재사용했다. 전체 회귀·변이 전체·공식 실행을 반복하지 않았다. F1/F2·학습·보관의 변경 없는 부분은 r1/r2 검증 근거와 이번 관련 회귀를 함께 사용했다.
- 근거: `/private/tmp/poc606-r3-verify-5u1rmn1e/` — `scope.json`, `r2-r3.diff`, `related.log`, `static-checks.json`, `lines.json`, `repro_midnight_r3.py`·`midnight-repro.json`·`midnight-repro.log`, `check.json`.

### 5) 범위 폭주

- **폭주 수준: NONE.** 공개일·재시도 연결 시각·주 기록 필드 의미를 같은 종류로 정정한 범위이며 새 모델·feature·튜닝·운영 권한은 추가하지 않았다.

### 6) 종합 판정

**VERIFIED — POC6-06 PC 구현·연결 검증 범위. F1·F2·F3 CLOSED.**
검증자는 운영 코드·시험을 수정하지 않았고 결과서 메타 정정과 이 판정 기록만 반영했다. OCI 반영·업로드·양쪽 복원은 설계자 RESULT 판정 이후의 별도 단계다.

### 7) 사용자에게 한마디

다음은 설계자 RESULT 판정이다. 영수증 보관 형식 추가와 공개 확인일의 보수적 의미를 함께 전달한다. 커밋·push·OCI 작업은 이번 검증에서 실행하지 않았으며 기존 승인·반영 순서를 유지한다.

## 14. 설계자 RESULT 판정 원문 (2026-10-23 · `docs/ai_design/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_RESULT_DECISION_2026-10-23.md`)

판정일: 2026-10-23 · 판정자: 설계자

**판정: PASS_TO_DEPLOY. PC 구현·실제 연결과 검증자 r3 VERIFIED를 수용한다. 이미 승인받은 순서로 커밋/push → OCI 받기 도구 반영 → 산출물 업로드 → 양쪽 복구 확인을 진행한다. 아래 종료 조건을 충족하면 추가 RESULT 재판정 없이 종료 기록을 남긴다. 현재는 OCI 반영·복구 확인 전이므로 CLOSED가 아니다.**

대상: `docs/ai_result/POC6/POC6-06_HOLDINGS_INDEPENDENT_FORWARD_MODEL_COMPARISON_RESULT.md`
기준: POC6-06 DESIGN V1 · PLAN V1 · PLAN_DECISION_2026-10-22.

### 0. 수용 근거와 확인 범위

- 보유와 독립된 고정 24종을 유지했고, 초기 조회 24/24·학습 예제 37,692행·전 종목 252개 이상·네 방법의 학습/복원과 실제 예측 기록을 완료했다는 개발자 근거를 수용한다.
- 모델 파일만으로 다시 읽은 실제 feature의 예측 96개가 기록값과 일치했다는 확인, 같은 입력·같은 행 비교·한 수신 판 목표·월별 학습·방법별 실패 분리의 검증을 수용한다.
- 검증자 r3가 F1 실제 공개 마감, F2 중복 실행, F3 공개 확인일의 날짜 경계를 모두 CLOSED로 확인했다. 관련 147개 직접 시험·18파일 정적 검사·자정 경계 재현 및 개발자의 최종 전체 회귀 4,378 passed 근거를 재사용한다.
- r1/r2의 재현·정정 기록과 당시 불변 산출물은 보존한다. 문서 정정과 배포를 위해 학습·전체 회귀·변이 전체를 다시 실행하지 않는다.
- 실제 수집·10:20/11:26 실행·OCI 정기 운영 수치는 개발자 보고를 근거로 한다. 검증자는 격리 코드·재현을 확인했으며 설계자가 라이브 자료·OCI·가중치를 직접 재측정했다는 뜻은 아니다.

### 1. 공개 확인 영수증 형식 추가 — 수용

`prediction_receipt`를 POC6-06 증거의 필수 부속 형식으로 수용한다. 경로 `predictions/<D>/<id>.receipt.json`, 예측 파일의 hash·id·D·schema·protocol 연결 및 받기 검사는 결과서의 최종 구현을 따른다.

이는 예측 파일이 마감 전에 존재했음을 확인하는 연구 기록이며, 같은 연구 산출물 보관 범위의 확장이다. 전송 목적지·계정 권한·모델 사용 범위를 넓히지 않으므로 이미 승인받은 POC6-06 산출물 업로드 범위에 포함한다. 이 형식 때문에 사용자 승인을 다시 받지 않는다. OCI에서는 JSON·참조·hash만 검사하며 모델을 load/import하지 않는다.

시각의 의미는 다음과 같이 확정한다.

| 항목 | 의미 |
|---|---|
| write_started_at | 예측 파일 쓰기를 시작한 시각. 실제 공개 시각의 하한 |
| visible_by / confirmed_at | 해당 hash의 파일이 놓여 있음을 확인한 시각. 실제 공개 시각의 상한 |
| 주 전향 기록 | 정상 영수증과 참조 검사가 있고, write_started_at ≤ confirmed_at < D 다음 거래일 마감인 기록 |

기존 원시 파일의 `times.published_at`은 쓰기 시작 시각을 담은 필드로 보존하되, 이를 정확한 실제 공개 시각으로 해석하지 않는다. 최종 records/report가 내보내는 분리된 의미를 사용한다. 무효·누락 영수증을 쓰기 시작 시각으로 대체하지 않는다.

시계 역행 검사·같은 hash 확인·마감 뒤 재확인 배제는 수용한다. PC 벽시계를 신뢰한다는 결과서의 한계도 유지한다. 외부 시각 공증이나 악의적인 파일 변조까지 방지하는 체계로 설명하지 않으며 이를 위한 새 서비스를 추가하지 않는다.

### 2. 첫 24종 기록 — 유효, 증명하는 시각은 보수적으로 표기

첫 기록의 입력 기준일은 D=2026-10-22다. 2026-10-23 10:20 실행에서 작성한 예측 파일을 같은 날 **11:26:13 KST에 확인한 영수증**이 있으며, 이는 다음 거래일 마감 15:30 전이다. 새 목표 종가가 확정되기 전에 해당 파일의 존재와 내용이 확인됐으므로 첫 주 기록 24종을 유효하게 수용한다. 새 예측이나 재학습으로 첫 기록을 다시 만들지 않는다.

다음 설명은 현재 요약·결과서 §5-7 등 해당 위치에서 정확히 고친다. 코드 정정이나 과거 불변 파일 수정은 요구하지 않는다.

- “공개 10:20:19”라고 단정하는 대신 “10:20 작성 기록 · 11:26:13까지 존재 확인”으로 구분한다. 실제 공개의 정확한 순간을 측정한 것처럼 쓰지 않는다.
- 11:26의 해시는 **그때 확인한 파일의 내용**을 묶는다. 그것만으로 10:20부터 11:26까지 파일이 한 번도 바뀌지 않았음을 증명하지는 않는다. 결과서의 그 표현은 삭제·정정한다.
- 10:20 이전 입력 cutoff·학습·feature 근거는 그대로 보존한다. 기록의 유효성은 마감 전 확인된 예측 파일과 최종 검사 규칙에 근거한다.
- 첫 누적 해석 기준일은 공개 확인일 2026-10-23 KST에서 3개월 뒤인 **2027-01-23**을 사용한다. 나중 run이 확인한 기록의 확인일이 더 늦을 수 있다는 보수적 의미를 유지한다.
- 10:20·11:26 당시 생성한 보고서 파일은 당시 규칙의 산출물로 그대로 둔다. 최종 코드의 새 조회·보고서와 구분하고, 기존 파일까지 모두 최종 규칙으로 생성됐다고 쓰지 않는다.

### 3. 구현 판단과 알려진 한계 — 수용

- PLAN과 달라진 모듈 분리와 `forward_artifacts` 공통 받기 검사, 연구 축 시작일로 제한한 초기 조회, 모델별 저장·환경 검사·복구 판의 파일/환경 근거 보존을 수용한다. 기존 02/03/04 공식 결과와 05 수집을 바꾸지 않은 범위다.
- 네 쓰기 명령의 단일 실행 잠금, 영수증 검사, 방법별 재시도·복구, 초기 예제의 hash 참조 및 CLI 상태·rc를 수용한다. 정상 방법을 실패 방법 복구 때문에 다시 학습하지 않는다.
- `SAME_DATA_HASH` 분기의 도달 여부와 별개로, 신규 예제가 없을 때 fit하지 않는 실제 경로·동일 날짜 무학습·월별 중복 차단의 검증으로 해당 계약을 수용한다. 분기를 실행시키기 위한 새 공식 학습은 하지 않는다.
- 결과가 동등하다고 분류한 변이 4종은 다른 검사 경계가 같은 결과를 유지한다는 검증 근거를 수용한다. 78종 중 74 탐지·동등 4로 기록하며 78종 모두가 결함 탐지였다고 바꾸지 않는다.
- 마감 전 유효 회차로 시작했으나 학습 후 공개가 늦어진 경우, 완료된 월별 학습은 남고 예측은 진단이 되는 한계를 수용한다. 이때 진단은 성과·LOGGED_FORWARD 예제에서 제외하고 실제 학습 판·월별 횟수는 그대로 보고한다. 학습 기회를 다시 만들려고 같은 달 재학습하지 않는다.
- 초기 회고 예제의 비PIT 성격, 실제 월별 갱신·성숙 결과가 아직 없다는 점, PC 시계 전제를 수용한다. 확인된 실행 환경은 PLAN/실측의 macOS arm64 CPU다. 다른 장비·운영체제나 GPU에서의 동일 실행을 확인했다고 확대하지 않는다. 이를 이번 종료의 새 시험 과제로 붙이지 않는다.

첫 성숙 예정은 결과서의 현 캘린더 기준 2026-11-19 종가 뒤다. 실제 평가는 그 기간의 확정 종가를 담은 보관본을 가져와 실행할 때 이뤄진다. 비교 행 0·MAE null은 현재 정상이며, 20거래일·두 번째 달·3개월을 기다리는 조건은 없다.

### 4. 배포·업로드·복구 — 기존 승인으로 진행

결과서 §7의 사용자 승인 완료 기록에 따라 진행한다. 같은 작업을 다시 승인받지 않는다.

1. 위 문서 설명과 본 판정 반영 후 구현 커밋·push를 한다. 실제 학습 시점의 미커밋 코드 근거, 코드를 처음 포함한 커밋, OCI 배포 커밋은 구별한다. 나중 커밋을 과거 실행 commit으로 소급 대입하지 않는다. 불변 연구 파일은 수정하지 않는다.
2. **거래일 08:05~15:45를 피해서** OCI pull로 받기 도구를 반영한다. 새 kind와 prediction_receipt를 검증할 수 있는 배포 판을 확인한다. torch/sklearn 설치·모델 load·학습/예측·cron 변경은 없다.
3. 기존 전용 업로드 경로로 POC6-06 산출물을 등록·업로드한다. 현재 보고 기준은 16파일이며, 이후 정상 보고서 등이 추가됐다면 그 증분을 구분해 실제 목록·수·hash를 기록한다. 실패·중단한 업로드를 완료로 쓰지 않는다.
4. PC와 OCI에서 빈 별도 경로로 복구 확인을 한다. 파일 목록·bytes/hash·참조 무결성과 영수증→예측, training→모델/예제 연결을 확인한다. OCI에서 모델을 실행하는 검사를 추가하지 않는다. 기존 원본 위에 복구하지 않는다.
5. 기존 02/03/04 22파일과 05 보관·수집 계약을 유지한다. 기존 운영 표·PUSH·PARAM·화면·API가 바뀌지 않은 근거를 결과서에 남긴다. 파일/등록 범위가 예상과 다르면 그 차이만 확인하고 임의로 허용 범위를 넓히지 않는다.

복구 확인에 실패하면 이미 있는 증거를 보존하고 해당 단계의 미완료·사유를 보고한다. 이를 모델 성능 실패로 기록하거나 성과를 다시 계산하지 않는다. 정상 확인에는 새로운 학습·전체 회귀·사용자 화면 확인·PC 재기동이 필요 없다.

### 5. 종료 조건과 기록

§4의 실제 배포·업로드·양쪽 복구가 정상이고 코드 계약을 더 바꾸지 않았다면 **추가 검증자 재검증·설계자 재판정 없이** 종료한다.

- 결과서에 본 판정 원문과 배포/업로드/복구 결과, 구현·배포·종료 commit, 실제 산출물 목록·hash·두 번째 사본 상태를 기록한다.
- 상태는 `IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED`로 맞춘다. PLAN·STATE·PROGRAM_TRUTH의 현재 대기 문구도 같은 실제 상태로 정리한다. 과거 r1/r2/r3 기록과 판정 원문은 보존한다.
- 남은 성숙 결과·월별 학습의 실제 운영 확인은 별도 상태로 둔다. PC_ONLY는 실제 OCI 보관·복구가 확인된 범위에서만 해소한다.
- 승인된 종료 기록 커밋·push까지 진행한다. 사용자 소유 handoff 문서는 포함하지 않는다. 같은 POC6 안이므로 새 handoff는 만들지 않는다.

### 6. 운영 확인과 성과 판정은 구분

- 05 첫 09:40 정기 실행과 개발자가 함께 확인한 기존 작업의 정상 결과는 수용한다. 05의 정기 운영 확인 대기는 해소할 수 있다. 기존 `date_mismatch` 경고를 이번 단계가 고친 것으로 쓰지 않는다.
- POC5-04 공식 R0는 이번에 **미실행**이다. 05 로그 확인으로 완료 처리하지 않는다. 기존 인계의 수집/배치 완료 근거와 그 뒤 동기화 사본을 갖춰, 정해 둔 읽기 전용 점검 1회를 별도로 수행·보고한다. 새 PLAN이나 새 기능 개발로 만들지 않으며 POC6-06 종료의 선행 조건으로도 붙이지 않는다.
- 일상 사용의 “15:30 전에 실행하면 기록이 남는다”는 안내는 **최신 D의 유효 입력·모델·달력·공개 확인이 갖춰진 경우**라는 조건을 함께 적는다. 시간만 맞으면 항상 새 기록이 생기는 보장은 아니다. 토요일 실행도 금요일 자료의 실제 공개·PC 수신 뒤이며 다음 거래일 마감 전이어야 한다.
- PC 미실행일은 예측 없음이다. 나중에 자료를 가져와 실제 남긴 예측의 목표를 평가할 수 있으나 지난 예측을 소급 생성하지 않는다. OCI의 일일 자료 수집과 PC의 수동 연구 실행을 구분한다.

이번 단계는 연구 예측을 계속 남기고 비교하는 연결의 완료다. **예측이 쌓이기 시작했다는 사실과 모델의 유효성이 입증됐다는 판정은 다르다.** 운영 ML 미승격, Q6 OPEN, 이전 02/04 결과, #3·#55·#57·#62 미완료는 유지한다. 이 결과가 쌓이는 동안 다른 미완료 사용자 기능의 설계·개발을 진행할 수 있다.

**개발자 전달: RESULT PASS_TO_DEPLOY입니다. prediction_receipt와 구현 판단을 수용합니다. §2의 시각 설명을 문서에 정정하고 이미 승인받은 커밋/push·OCI 반영·업로드·양쪽 복구를 진행해 주세요. 정상 완료하면 §5대로 추가 재판정 없이 종료 기록과 push까지 마무리합니다.**

## 15. 종료 기록 — 실제 배포 · 업로드 · 양쪽 복원 (2026-10-23 · RESULT 판정 §4 · §5)

판정 §5 의 종료 조건(배포 · 업로드 · 양쪽 복원 정상 · 코드 계약 추가 변경 없음)을 충족해, 추가 재검증 · 재판정 없이 `IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED` 로 닫는다.

| 순서 | 시각(KST) | 결과 |
|---|---|---|
| 판정 반영 | 13:50 ~ 13:52 | 판정 원문 저장(`..._RESULT_DECISION_2026-10-23.md` · §14) · §2 시각 설명 정정(10:20 작성 · 11:26:13 존재 확인 · 해시가 묶는 범위 · 당시 보고서 파일 = 당시 규칙) · §6 사용 안내 조건 |
| 구현 커밋 · push | 13:53 | `666fc5c0`(30파일 · `git show --stat 666fc5c0`) → `c77a71f3..666fc5c0 main` · 이 커밋이 POC6-06 코드를 처음 포함한 커밋이자 OCI 배포 판이다. 실제 학습 · 예측 run(10:20 · 11:26)은 그 전의 미커밋 작업 트리 코드로 실행했다(과거 실행 commit 으로 소급하지 않음) |
| PC 등록 · 복원 | 13:54 ~ 13:55 | 05 보관소 등록 `20261023T045432Z_e3570691`(16파일 · object 16 · manifest `cc344698…19d62`) · PC 빈 경로 복원 OK(같은 해시 · 목록 · 읽기) |
| OCI 반영 | 15:50 | 15:40 보유 CLOSE 완료(sent) · 실행 중 작업 0 · 추적 파일 변경 0 확인 뒤 `git pull --ff-only` → `666fc5c0` · `store.KINDS` · `transfer.UPLOAD_KINDS` 에 새 종류 · `prediction_receipt` 받기 형식 확인 · torch · sklearn import 0 · cron 15줄(작업 14 + PATH) 그대로 |
| 업로드 | 15:50 | `archive --upload` → `up_20261023T065016Z_21e9a0e8` · object 16 전송 · OCI `accept-upload` OK(created · manifest 해시 같음) · OCI receipt `received_at` 2026-10-23T06:50:24.694283Z |
| OCI 복원 · 무결성 | 15:51 | OCI 빈 경로(`/tmp/poc606_restore_…`) 복원 OK(같은 해시 · 목록 · 읽기) · OCI `verify` OK(묶음 6) · 미완료 0 · `.incoming` 0 · 보관소 32M |
| 참조 대조(양쪽 같은 스크립트 · 읽기) | 13:55 · 15:51 | 05 받기 검사 문제 0 · bytes 불일치 0 · 참조 7곳 모두 일치(영수증 → 예측 · training → 예제 · training → 모델 5파일) · PC 복원본 = PC 연구 폴더 원본 해시 일치 · **PC · OCI 16파일 해시 · bytes 목록 diff 0** · 합계 11,281,981 bytes |

두 번째 사본(OCI) 16파일 — sha256 · bytes · 경로(`state/ml/research/poc6_06/` 기준):

```text
9c9cd30a7d7db4d1eae51cd1a154ec18a4422ad8ce84dff0900cf28d43098994      8506 bootstrap/20261023T011918Z_72843194/fetch.json
428f56a7e1f7a5b7d91ad53b5edba6404fa06d357ef69b12bcfd489d86fe8c8b   2872270 bootstrap/20261023T011918Z_72843194/prices.json
f11f45201d272c6ea4a3c0240e1ec2be7a1733ae57c8951942ce0c178b86f7d0     22524 cohort_v1/cohort.json
757a177857e71ad82904e85a6d605be8f0c17a806eec5ec1e5c0e77ba8ac71b9   8120699 examples/20261023T012013Z_6eb886a0.json
c42826f6484d68fe119298a8731b06ceeafb1fdbd9b439a5695d5d873d3cff5c     93472 models/mv_e926e0661c261324/hgb.joblib
4ab7ea45e4318826bbe56c27517a0b39982da80c87cad203b0f764ef8910eca1      1660 models/mv_e926e0661c261324/median.json
f820ee9959d9b1170de13cc2b5ebfcda155b6ad7c207d7f9d2ee36016a78b7e6       364 models/mv_e926e0661c261324/mlp_norm.json
f564fce7dc919a994713e637c4088a8f163421a93b4c39ec44cd6467d99a03f5     12693 models/mv_e926e0661c261324/mlp_state.pt
6c0da7541425e45c014eeac24875cda408a6df823b9c4291c333bd8fb019054d     12545 models/mv_e926e0661c261324/ridge.json
0f4d86418298214f636d34cf332d2293c7e7f7668cabef8d88e78e184f4cfdc1      4846 models/mv_e926e0661c261324/training.json
8e05083e2c22071ee7accbfc12c37fc5da1af51707e03e3f83656a576b11bee6    107303 predictions/2026-10-22/20261023T012012Z_f9953001.json
bb1120dd66aea4b1e38c00d574758d4ceb4362d7354063d598496185cdd577b5       643 predictions/2026-10-22/20261023T012012Z_f9953001.receipt.json
f16700edd38ec3be791ada1421a2af44e81eb5d4801113690ee4cc731fafc93a      7546 reports/20261023T012012Z_f9953001.json
5e9522e3e3aca8f6b05ee9314d97331a38757c8dcaf88c30cfc3d9eb34b09a46      7625 reports/20261023T022613Z_d98f2482.json
a2189f210e48af108222f39d7509095751d09c6bc8ff3ea14dc722471de71409      2023 runs/20261023T012012Z_f9953001.json
c8326273b50df6ec5e6efc1251caeaed1da70b4ac9d09c43ce5c8fe33f95df52      7262 runs/20261023T022613Z_d98f2482.json
```

바뀌지 않은 것:

- 02 · 03 · 04 공식 22파일: PC 해시 대조 22 같음(§8-4) · OCI 의 기존 등록 묶음 포함 `verify` OK.
- 배포 diff(`c77a71f3..666fc5c0`)의 기존 코드 변경 = `app/ml_evidence/store.py`(KINDS) · `transfer.py`(받기 분기)뿐 · 05 수집(`daily*.py`) · 러너 · 배치 · API · 화면 · 배포 스크립트 변경 0.
- OCI cron 그대로(15줄) · OCI 에서 모델 load · 학습 · 예측 0 · PUSH · PARAM · 화면 · API 변경 0.
- 사용자 소유 handoff 문서는 커밋에 넣지 않았다 · 같은 POC6 안이라 새 handoff 없음.

남은 것(별도 상태 · 이 단계 종료 조건 아님): 첫 성숙(D+20 = 2026-11-19 종가 뒤 · 그 기간의 확정 종가를 담은 보관본을 가져와 run 할 때) · 첫 월별 학습 · 3개월 해석(2027-01-23). 예측이 쌓이기 시작했다는 사실과 모델 유효성 입증은 다르다 — ML_OPERATION_PROMOTION=NOT_APPROVED · CURRENT_DEPLOYABLE_ML_MODEL=none · Q6 OPEN · #3 · #55 · #57 · #62 미완료 유지.
