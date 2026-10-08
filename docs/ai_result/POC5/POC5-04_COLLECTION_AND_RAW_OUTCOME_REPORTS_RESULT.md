# POC5-04 개발 결과서 — COLLECTION_AND_RAW_OUTCOME_REPORTS (R0 · R1)

작성 2026-10-08 · 갱신 2026-10-08(검증자 r1 정정 · r2 VERIFIED · 설계자 RESULT PASS) · 작성자: 개발자(VSCode Claude) · 수신: 검증자(Codex)

```text
STATUS                 = IMPLEMENTED_VERIFIED_CLOSED — 검증자 r2 VERIFIED(2026-10-08) · 설계자 RESULT `PASS`(2026-10-08 · 개발 종료 수용 · 지시문 외 변경 5/5 · 재작업 · 추가 검증 없음) · 커밋 · push 는 사용자 승인 · 공식 R0 = 별도 1회 운영 점검(10-22 종가 배치 완료 근거 + 그 뒤 동기화 사본 · 10-23 이후 · 미실행이 이 단계의 미완성이 아님)
STEP_ID                = POC5-04 R0 수집 점검 · R1 원시 결과 리포트
DESIGNER_RESULT        = PASS(2026-10-08 · DEVELOPMENT_ACCEPTANCE ACCEPTED · CODE_REWORK NONE · OFFICIAL_R0 PENDING_SEPARATE_OPERATIONAL_CHECK) — 원문 = 설계서 끝
VERIFIER               = r2 VERIFIED(2026-10-08 · A-1 ~ A-4 통과 · B-1 ~ B-6 없음 · 검증자 시험 12 추가 통과 · PLAN 말미 빈 줄은 검증자가 정리) · r1 REJECTED(2026-10-08 · A-1 · A-3 · B-1 — ① 필수 사본 표 누락을 COLLECTION_OK 로 · 결과 표 생성 기록 뒤 표 누락을 정상 대기로 ② --iterations 0 이하에서 계산 없이 bootstrap OK) → 정정(§6-3) · PLAN 말미 공백은 검증자가 직접 정리
DESIGN                 = docs/ai_design/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_DESIGN_V1.md (개정 1 · 끝에 PLAN 판정 · 전달문 원문)
PLAN                   = docs/ai_plan/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_PLAN_V1.md (PASS_TO_IMPLEMENT · §7 판정 정정 · §8 구현 중 확정 · 정정)
PREDECESSOR            = POC5-03
BASE_COMMIT(코드 기준)  = 1d2fc929
CODE_FILES             = 신규 9(app/ledger_reports 8 · scripts/run_ledger_report.py) · 기존 코드 수정 0 · 화면 · API · DB · cron · SSH · 의존성 0
TESTS                  = 새 테스트 1파일 67 passed(tmp 원장 · tmp 캘린더) · 변이 시험 9종 모두 탐지(§8-3)
REVIEW                 = 독립 검토 1회(읽기 전용 · tmp 재현) — HIGH 1 · MEDIUM 4 · LOW 다수 · 테스트 약점 · 문서 불일치 3 → 반영(§6-2)
KS-10                  = 트리거 0 · 새 모듈 최대 r0.py 295 · 테스트 1,090(단일 Step)
BACKEND_FULL_REGRESSION= 3069 passed / 0 failed · exit 0 · 385.65s(2026-10-08 12:44:03 ~ 12:50:30 · r1 정정 뒤 최종 코드) · PC state/logs 1,153파일 해시 전후 동일 · 회귀 시작 뒤 코드 변경 0
```

## 0. 요약

PC 에서 손으로 돌리는 읽기 전용 리포트 CLI 를 만들었다.

```bash
python scripts/run_ledger_report.py r0 --end 2026-10-22 --reconcile-evidence <대조 근거> --ops-evidence <운영 근거>
python scripts/run_ledger_report.py r1 --end <종료일>
```

- **입력**: PC 원장 사본(03)을 `mode=ro` · 읽기 트랜잭션 1개로 읽는다. 02 의 대상 목록(`ledger_outcome._load_targets`)도 같은 트랜잭션에서 그대로 실행한다. 입력 행과 event 마다 최신 평가의 SHA-256 digest 를 남긴다(평가가 바뀌면 digest 는 달라진다 · 통계는 그대로).
- **날짜**: 02 와 같은 운영 거래일 캘린더(`state/market_meta`) · 종료일 기본 = 오늘 이전 마지막 거래일 · `--end` 는 YYYY-MM-DD · 오늘 이전 · 거래일만.
- **출력**: `state/ml/research/poc5_04/<r0|r1>_<종료일>_<생성시각>/report.md · report.json`(기존 PC 연구 산출물 관례 · gitignore · 새 폴더만 · DB 쓰기 0).
- **R0**: OCI 대조(개발자 제공 근거) · 예정 실행 11 슬롯 · 무결성 · 운영 실패 기록 · 가격 슬롯 · 대기(`PENDING_NOT_DUE` · `PENDING_DUE` = 평가일 도래 · 결과 미기록 · 원인 미확인) · 운영 근거(종료일 배치 완료 · 그 뒤 동기화 · `ops_error_count`) → `COLLECTION_OK / CHECK_REQUIRED / NOT_READY`.
- **R1**: 02 결과 대상 중 관측 5종 처리 item 을 노출 세 구분(PRIMARY · SECONDARY · '노출 분류 없음') × 관측 / 전달로 나눠 MATURED 원시 수익률 통계(평균 · 중앙값 · 25/75 분위 · 최소 · 최대 · max_up/down 중앙값 · n_event/n_item/n_price_observation/n_signal_date)와 날짜 묶음 비원형 block bootstrap 평균 95% 구간을 낸다. 평가는 부가 표만.

## 1. 처리한 요구사항

설계 개정 1 §8 수용 기준 + 판정 정정.

| 항목 | 상태 | 근거(테스트) |
|---|---|---|
| AC1 연결 정상 · 누락 · STARTED · orphan · NOT_READY 구분 | DONE | `test_missing_required_table_is_never_collection_ok` 6종 · `test_outcome_table_dropped_after_it_was_created` · `test_outcome_table_absent_before_maturity_is_normal`(r1 정정) · `test_r0_collection_ok_after_ten_days` · `…not_ready_before_ten_days` · `…missing_slot_started_and_orphans…` · `test_each_integrity_problem_alone_is_check_required` 7종 · `test_each_reconcile_error_kind_is_check_required` 3종 |
| AC1 판정 fixture(유효한 오류 대조 = CHECK_REQUIRED · 근거 부재 = NOT_READY · 09:30 경과만 ≠ 배치 완료) | DONE | `…reconcile_errors_are_check_required_even_if_status_not_ok` · `test_r0_unusable_reconcile_is_not_checked` 4종 · `…time_passing_alone_is_not_batch_completion` |
| AC2 +20 미도래 · 채우기 창 대기를 결측 · 실패로 오인 안 함 | DONE | `test_r0_pending_split_not_due_and_due` · `test_pending_alone_keeps_collection_ok` · `test_matured_after_end_is_not_due_not_statistic` |
| AC3 다중 ticker · PRIMARY/SECONDARY/NONE · 관측/전달 · partial · LEGACY · off_schedule 분모 · NULL 누락 없음 | DONE | `test_r1_three_exposure_tables_and_none_kept` · `…denominators_delivered_partial_and_exclusions`(LEGACY = 시작일 전 실행) · `…known_values_and_multi_ticker_counts` |
| AC4 평가 변경 → 통계 불변 · digest 변경 허용 · 조회가 평가를 만들지 않음 | DONE | `test_r1_feedback_changes_digest_not_statistics` |
| AC5 알려진 값 평균 · 분위 · max_up/down · 같은 입력/seed 동일 | DONE | `…known_values…` · `test_r1_zero_and_single_observation` · `…same_input_same_seed_is_identical` |
| AC6 날짜 묶음 · 연속 블록(비원형) · 빈 날 보존 · 소표본 구간 없음 | DONE | `test_bootstrap_needs_at_least_one_iteration` · `test_cli_rejects_non_positive_iterations`(r1 정정) · `test_bootstrap_non_circular_contiguous_date_bundles` · `…insufficient_and_undefined_resamples` · `test_r1_block_and_empty_days_on_axis` · `test_long_period_axis_is_not_cut_at_120_days` |
| AC7 입력 DB · 원장 행 · 라이브 파일 불변 · SSH · Telegram · 외부 0 | DONE | `test_cli_writes_new_folder_and_never_touches_db`(sha256) · `test_new_modules_have_no_network_ssh_or_telegram`(AST) · 전체 회귀 전후 라이브 해시(§8-5) |
| AC8 전체 회귀 · 정적 검사 · KS-10 | DONE | §8 |
| 공식 R0 실행(2026-10-23 이후) | SKIPPED | 설계 §10 — 개발 종료와 무관한 별도 1회 운영 점검 |

## 2. 변경된 파일 목록

- `app/ledger_reports/__init__.py`: 신규(7)
- `app/ledger_reports/source.py`: 신규(182) — 읽기 전용 스냅샷 · digest · 입력 요약 · 입력 사본 손상(`problems`)
- `app/ledger_reports/dates.py`: 신규(116) — 캘린더 · 종료일 · `validate_end` · 날짜 축 · D10 · 평가일 · `rows_known_by`
- `app/ledger_reports/evidence.py`: 신규(189) — 대조 근거 · 운영 근거 해석 · 메모 가리기
- `app/ledger_reports/r0.py`: 신규(295)
- `app/ledger_reports/r1.py`: 신규(282)
- `app/ledger_reports/bootstrap.py`: 신규(90)
- `app/ledger_reports/render.py`: 신규(169)
- `scripts/run_ledger_report.py`: 신규(99)
- `tests/test_poc5_04_ledger_reports.py`: 신규(1,090)
- `docs/ai_design/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_DESIGN_V1.md`: 신규(개정 1 원문 + 전달문 · 판정)
- `docs/ai_plan/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_PLAN_V1.md`: 신규
- `docs/ai_result/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_RESULT.md`: 신규(이 문서)
- `docs/PROGRAM_TRUTH.md`: 수정(머리 · §4 진입점 · §11 분류 · 부록 A)
- `docs/STATE_LATEST.md`: 수정(머리)
- `docs/ai_design/POC5/POC5-02_PRICE_OUTCOME_MATURITY_DESIGN_V1.md` · `docs/ai_result/POC5/POC5-02_PRICE_OUTCOME_MATURITY_RESULT.md`: 수정(설계자 '게이트 전 배포 사후 수용' 2026-10-08 기록)

## 3. 신규 추가된 의존성

없음(numpy 도 쓰지 않는다 · 난수 = 표준 라이브러리 `random.Random(seed)` · 분위 = 기존 `ml_score_validity_metrics.percentile`).

## 4. 지시문 외 변경

1. **R0 운영 실패 기록 → `CHECK_REQUIRED`** — 기간 안 실행 `status=failed` · 전달 `failed` · `partial`. 설계 §3 끝 문장('확인된 배치 · 운영 오류 … 실제 오류를 COLLECTION_OK 로 처리하지 않는다')을 원장이 이미 기록한 사실에 적용했다. PLAN §2-1 목록에는 없던 항목이다(§6-1-1 확인 요청).
2. **운영 근거 `ops_error_count` 필수 키** — 개발자가 읽기 전용으로 확인한 배치 · 원장 · PUSH 오류 건수. 없거나 정수가 아니면 `NOT_READY` · > 0 이면 `CHECK_REQUIRED`(같은 설계 문장 · 근거 형식은 PLAN 에서 정하기로 한 부분).
3. **운영 메모 가리기** — 비밀값 단어(token · secret · password · api_key · chat_id 등)가 든 줄은 통째로 가리고 32자 이상 토큰은 `[가림]`(PLAN §2-1 '본문 · 비밀값은 싣지 않는다').
4. **`--end` 검사** — YYYY-MM-DD · 오늘(KST)보다 이전 · 운영 거래일만(설계 §2 '오늘 장중을 완료 일자로 간주하지 않는다').
5. **비공개 이름 재사용** — `ledger_outcome._load_targets` · `_expected` · `_TARGET_KINDS`(02 대상 · 슬롯 · subject 를 복사하지 않으려고 · PLAN §1-1 명시 · POC5-03 선례).

## 5. 알려진 한계 / 미완성

1. **공식 R0 는 아직 실행하지 않았다** — D10 = 2026-10-22(운영 캘린더 실측). 10-22 종가를 적재한 배치(10-23 08:10 · 09:20)의 완료 근거와 그 뒤 동기화한 PC 사본으로 개발자가 1회 실행한다.
2. **대조 근거 · 운영 근거는 개발자가 만든 텍스트다** — 01B 대조 CLI 에 실행 시각 출력이 없어 `captured_at=` 줄을 붙인다. 근거의 진위 자체는 리포트가 검증하지 않는다(형식 · 기간 · 시작 일치만).
3. **누적 대조 근거** — 01B CLI 는 누적 결과라, 종료일 뒤 실행까지 포함한 오류 건수를 종료일 이전 정확한 건수로 바꿀 수 없다(`includes_after_end` 로 표시).
4. **digest 범위** — 입력 원장 행 + 최신 평가만. 대조 · 운영 근거 · 캘린더 파일 · 동기화 시각은 digest 밖이고 리포트 본문에 그대로 싣는다.
5. **비거래일 사건의 성숙 관측** — 평균 · 건수에는 들어가지만 bootstrap 날짜 축(운영 거래일)에는 없다 → `n_matured_outside_axis` 로 표시(실제로는 거의 생기지 않음). `n_matured_outside_axis` 가 양수인 보고서의 구간은 거래일 축 자료를 재표집한 범위이며, 비거래일 관측까지 포함한 전체 평균의 구간으로 해석하지 않는다(설계자 RESULT 수용 · V1 한계).
6. **R1 상태 라벨** — state 는 원장 코드(D5_8 · UP 등) 그대로다(연구용 리포트 · 화면 라벨표를 쓰지 않음).

## 6. 다음 검증자(Codex)에게 알릴 점

### 6-1. 판단이 어려웠던 부분

1. **운영 실패를 CHECK_REQUIRED 로 둔 것(§4-1)** — 설계자 RESULT 수용(2026-10-08): 이미 기록된 운영 실패 · 불완전 전달을 점검 대상으로 남긴다는 뜻이며, 원장 수집 결함 확정이 아니다(실패를 충실히 기록한 원장은 수집 자체가 정상일 수 있다). 정상 skipped · no_selection · 반복 억제 · 상한 제외는 실패로 분류하지 않는다. 공식 R0 보고에는 원인 · 영향 · 현재 조치 상태를 남기고, 과거 기록 삭제 · 재발송 · PRIMARY 시작일 재설정은 하지 않는다.
2. **bootstrap 계산 불가 재표본** — 하나라도 있으면 구간 전체 NULL(`RESAMPLE_UNDEFINED`). 사건 날짜가 듬성한 그룹에서는 2×block 을 넘어도 구간이 안 나올 수 있다(위장 금지를 우선).
3. **PENDING_DUE 에 '평가일 = 종료일' 인 +1 이 들어간다** — KRX 는 종가를 다음 영업일 08:00 에 공개하므로 종료일 당일 +1 은 정상적으로도 미기록일 수 있다. 원인은 단정하지 않고 '원인 미확인' 으로만 적는다.
4. **대조 근거 판정 순서(§1-2 · PLAN §8)** — 시작 · 기간 정보 → 오류 → 기간 포함. 다른 원장 근거의 오류 건수로 CHECK_REQUIRED 를 내지 않는다.

### 6-2. 독립 검토(2026-10-08 · 읽기 전용 · tmp 재현) 반영

| 지적 | 반영 |
|---|---|
| HIGH 날짜 축이 120 달력일에서 잘림(`Calendar.days_from` 걷기 한도) → 그 뒤 누락이 COLLECTION_OK · bootstrap 이 일부 날만 봄 | 하루씩 직접 걸으며 `is_trading` · `test_long_period_axis_is_not_cut_at_120_days`(2026-10-08 ~ 2027-03-31 · 누락 = 전 기간 × 11 − 2) |
| MEDIUM 배치 적재일 형식 미검사(`unknown` · `20261022` 등 통과) | 엄격한 YYYY-MM-DD · `test_ops_batch_date_must_be_strict_and_cover_end` 5종 |
| MEDIUM R1 Markdown 표 깨짐(가격 기준의 `\|`) | 칸 이스케이프 · `test_markdown_table_rows_keep_column_count` |
| MEDIUM 확인된 운영 오류가 판정에 안 들어감 | §4-1 · §4-2 · `test_ops_error_count_drives_verdict` 3종 · `test_operational_failures_are_not_collection_ok` 3종 |
| MEDIUM LEGACY 제외 건수가 구조상 0(LEGACY = 시작일 전 실행) | `before_primary_start` · `after_end` 건수 · fixture 를 실제 모양(시작 전날)으로 |
| LOW 대조 오류 판정이 시작 · 기간 확인보다 먼저 | 순서 정정 · `test_reconcile_errors_from_another_ledger_are_not_checked` |
| LOW `--end` 미검사 | `validate_end` · `test_validate_end` |
| LOW 종료일 뒤 평가일 결과가 통계에 들어감 | `rows_known_by` · `test_matured_after_end_is_not_due_not_statistic` |
| LOW 대조 오류 사유에 기간 없음 | 사유에 `[floor, captured_at]` · 종료일 뒤 포함 표시 |
| LOW 운영 메모 비밀값 | §4-3 · `test_ops_notes_hide_secrets` |
| LOW 대상 아닌 item 의 outcome 미점검 · 알 수 없는 exposure 로 멈춤 · 비거래일 관측 | `outcome_on_non_target` · 별도 표 · `n_matured_outside_axis` |
| 테스트 약점 — 무결성 항목별 단독 판정 · PENDING 만 있을 때 판정 · block=20 · 빈 날 · 대조 오류 종류별 | 각 테스트 추가(위 표) |
| 문서 불일치 3(PLAN §1-5 · §1-6 · §2-2) | PLAN 문장을 코드와 맞춤 |

### 6-3. 검증자 r1 REJECTED(2026-10-08) 정정

| 지적 | 원인 | 정정 · 테스트 |
|---|---|---|
| A-1 · A-3 · B-1 `signal_item` 등 필수 사본 표가 없어도 빈 자료로 받아 `COLLECTION_OK` · `schema_version.price_outcome` 기록 뒤 `price_outcome` 이 없어도 정상 대기 | `source._rows` 가 없는 표를 `[]` 로 돌려줬다(POC5-03 r1 과 같은 계열) | `source.REQUIRED_TABLES`(원장 4 + PC 전용 2) · 결과 표 생성 기록 검사 → `Snapshot.problems`. R0 = 다른 조건과 무관하게 `CHECK_REQUIRED`('입력 사본 손상 — …') · R1 = `InvalidInput`(통계를 만들지 않음 · CLI `status=FAILED reason=invalid_input` · exit 3 · 출력 폴더 0). 결과 표가 아직 없는 원장(생성 기록 없음)은 정상. `test_missing_required_table_is_never_collection_ok` 6종 · `test_outcome_table_dropped_after_it_was_created` · `test_outcome_table_absent_before_maturity_is_normal` · `test_cli_r1_fails_on_damaged_input` |
| A-1 · A-3 `--iterations 0` · `-1` 에서 재표집 0회인데 bootstrap `OK`(구간 null) · exit 0 | 반복 횟수를 검사하지 않았다 | `date_block_ci` 가 1 미만이면 `ValueError` · CLI `--iterations` 는 1 이상만(argparse · exit 2 · 출력 폴더 0) · `test_bootstrap_needs_at_least_one_iteration` · `test_cli_rejects_non_positive_iterations` |

- 변이 시험: 손상 기록 지우기 → 7 실패 · 반복 횟수 검사 제거 → 4 실패.

반영하지 않은 것: digest 를 근거 파일 · 캘린더까지 넓히는 것(§5-4 · 설계 §2 는 '입력 행 snapshot' digest · 근거는 본문에 그대로 기록).

## 7. 사용자 확인이 필요한 항목

없음(화면 없음 · 리포트는 개발자가 실행). 공식 R0 는 2026-10-23 이후 개발자가 실행해 보고한다.

## 8. 검증 실측 (2026-10-08)

### 8-1. 테스트

- `tests/test_poc5_04_ledger_reports.py`: **67 passed**

### 8-2. 정적 검사

- `black --check` · `flake8` · `py_compile`: 새 파일 전부 통과

### 8-3. 변이 시험(정정 · 핵심 계약을 되돌린 상태에서 새 테스트가 실패하는지)

| 변이 | 실패한 테스트 |
|---|---|
| status≠OK 면 대조 오류를 NOT_CHECKED 로 | `…reconcile_errors_are_check_required_even_if_status_not_ok` |
| 배치 근거 대신 '확인됨' 강제 | `…time_passing_alone_is_not_batch_completion` |
| 관측에서 not_selected 제외 | `…three_exposure_tables_and_none_kept` |
| 원형 bootstrap | `…non_circular_contiguous_date_bundles` · `…insufficient_and_undefined_resamples` |
| 날짜 축 120일 절단(수정 전 코드) | `…long_period_axis_is_not_cut_at_120_days` |
| 적재일 형식 검사 제거 | `…batch_date_must_be_strict…` 4종 |
| 운영 실패 0 으로 | `…operational_failures_are_not_collection_ok` 3종 |
| 입력 손상 기록 지우기(r1 정정 전) | `…missing_required_table_is_never_collection_ok` 6종 · `…outcome_table_dropped_after_it_was_created` |
| 반복 횟수 검사 제거(r1 정정 전) | `…bootstrap_needs_at_least_one_iteration` 2종 · `…cli_rejects_non_positive_iterations` 2종 |

### 8-4. 실데이터 시험(복사본 · 출력 scratchpad)

- PC 사본(2026-10-08 10:15:49 동기화)의 복사본 · `--end 2026-10-08`(시험용 · 지금은 `--end` 검사로 오늘 불가): R0 `NOT_READY`(10일 미만 · 운영 근거 없음 · 대조 근거 없음) · 예상 가격 슬롯 279 · R1 표본 item 88 · event 3 · 노출 PRIMARY · NONE 표.

### 8-5. 백엔드 전체 회귀 · 라이브 보호

- 최종(r1 정정 뒤): `.venv/bin/python -m pytest -q -p no:cacheprovider` → **3069 passed · exit 0 · 385.65s**(2026-10-08 12:44:03 시작 · 12:50:30 끝 · 직전 POC5-03 회귀 3002 + 이 단계 67) · 회귀 전후 PC `state/` · `logs/` 1,153파일 sha256 **동일**(r1 제출 때 = 3056 passed · exit 0).

## 9. git 상태

`git status --short --untracked-files=all`(보고 직전 실측 · 커밋 전):

- staged **17** = 신규(`A`) 13 · 수정(`M`) 4 · unstaged 0
- `??` 1 = `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` — 사용자 소유 · 이 작업과 무관 · stage 하지 않는다(작업 중 `git add -A docs/` 로 한 번 올라갔다가 `git restore --staged` 로 내림 · 파일 내용 불변)
- 배포 경로(OCI) 파일 0 — PC 수동 도구
