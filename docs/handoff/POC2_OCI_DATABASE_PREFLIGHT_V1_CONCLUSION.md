# OCI Database Preflight v1 — Conclusion (PARTIAL, OCI 실측 대기)

작성일: 2026-07-08
성격: OCI SQLite 운영 전환 사전점검. **read-only** 실측만. DB / JSON / runtime / API / UI / scheduler / transfer 변경 **0건**.

---

## 1. Step 목표와 read-only 범위

지시문 §3 단일 목표: PC · OCI 각각에서 현재 DB / runtime 관련 경로 / 기존 transfer staging 실제 상태를 read-only 로 확인해 다음 DB 전환 STEP 진입 가능 여부만 확정.

**금지 준수** (§4 · §5 · §6.2 · §6.5): SQLite write / schema · row 변경 / VACUUM · ANALYZE · REINDEX · wal_checkpoint / JSON migration / SSH / 외부 API / Telegram / `.env` 로드 / persistent artifact / 절대 경로 · secret · raw traceback stdout 노출 — 모두 **0건**.

**§6.2 예상 밖 오류 sanitisation 계약 (FIX r1)**: `main()` 은 `_main_impl()` 을 감싸는 최상위 예외 경계. 예상 밖 예외 발생 시 stdout 에 `status=FAILED` + `error_class=<class 이름>` 만 노출하고 raw traceback / exception message / 절대 경로 · secret 은 **미노출**. SystemExit (argparse 등) 은 그대로 상위로 전파. 회귀 방지 테스트 3건 신설: `test_unexpected_error_sanitised_no_raw_traceback`, `test_systemexit_propagates_not_swallowed`, `test_error_class_only_no_message_or_absolute_path`.

**§B-1 fail-loud (FIX r1)**: `app.decision_evidence_store.DEFAULT_DB_PATH` import 를 `try/except` 조용한 하드코딩 fallback 대신 직접 import 로 변경. import 실패 자체가 상위 예외 경계로 노출되어 `status=FAILED / error_class=ImportError` 로 정직 표시.

---

## 2. 실행 revision 과 PC / OCI 비교 표

**PC 실측 완료 (2026-07-08)**:

| 항목 | PC | OCI |
|---|---|---|
| 실행 revision (short git hash) | `13ced48e` | ⏳ 대기 (사용자 실행 필요) |
| `--environment` 인자 | `pc` | `oci` |
| 실행 명령 | `python -m scripts.run_oci_database_preflight --environment pc` | `python -m scripts.run_oci_database_preflight --environment oci` |
| CLI 결과 status | ok (single_environment_readiness=READY) | ⏳ 대기 |

**Same-revision 검증**: 지시문 §6.3 · §9 준수 — OCI 실행 시 `git rev-parse --short HEAD` 값이 `13ced48e` 와 동일해야 DONE 진행 가능.

---

## 3. market_data.sqlite 관찰 결과

**PC 실측**:

| 항목 | 값 |
|---|---|
| 프로젝트 상대 경로 | `state/market/market_data.sqlite` |
| path resolution 상태 | `resolved` (single_canonical_path) |
| 파일 존재 여부 | True |
| regular file 여부 | True |
| parent directory 존재 여부 | True |
| read access | True |
| read-only open (`file:...?mode=ro`) | True |
| PRAGMA integrity_check | `ok` |
| table 목록 (개수) | 12 |
| PRAGMA schema_version | 12 |
| PRAGMA application_id | 0 |
| 파일 크기 | 131538944 bytes |
| **개별 readiness (§7.1)** | **READY** |

**Q1 (a) 확정 준수**: 기준 경로 = `app.market_data_store.DEFAULT_DB_PATH`. 보조 정의 `app.etf_nav_store.DEFAULT_DB_PATH` 는 동일 반환값 별도 선언 — **충돌 아님**. 자동 테스트 `test_q1a_two_modules_with_same_return_is_ready` + `test_q1a_conflict_when_aux_returns_different_path` 로 두 케이스 검증.

**OCI 실측**: ⏳ 대기.

---

## 4. decision_evidence.sqlite 관찰 결과 (§6.6)

**PC 실측**:

| 항목 | 값 |
|---|---|
| 프로젝트 상대 경로 | `state/decision/decision_evidence.sqlite` |
| 존재 여부 | True |
| regular file 여부 | True |
| read-only open | True |
| integrity_check | `ok` |
| table 목록 (개수) | 1 |
| **readiness** | **READY** |

**§6.6 · §7.2 준수**: 부재 시 `OPTIONAL_MISSING` 처리 규칙은 자동 테스트 `test_5_decision_missing_is_optional_missing` 로 검증. overall readiness 실패로 강제하지 않음.

**OCI 실측**: ⏳ 대기.

---

## 5. runtime 관련 경로와 transfer staging 관찰 결과

### 5.1 runtime 관련 경로 (audit §4.1 · §6.4 명시 대상만, PC 실측)

| 경로 | exists | regular_file | read_access | source_of_truth |
|---|---|---|---|---|
| `state/three_push/params/latest_runtime_param.json` | True | True | True | prior_audit_evidence + local_observation |
| `state/three_push/oci_runtime_status_latest.json` | False | False | False | prior_audit_evidence (OCI runtime write 파일, PC 상 부재는 예상) |
| `state/three_push/oci_runtime_sent_registry.json` | False | False | False | 위와 동일 |
| `state/three_push/oci_runtime_history.jsonl` | False | False | False | 위와 동일 |
| `state/runtime/three_push_runtime_probe_latest.json` | True | True | True | prior_audit_evidence + local_observation |

**PC 시점 runtime_paths_status**: `confirmed_from_local_and_prior_audit` (일부 파일 로컬 존재 확인 + audit 근거 인용).

**OCI 실측**: ⏳ 대기. OCI 에서는 `oci_runtime_*` 3개 파일 실제 존재 여부가 확인되어야 함 (audit 상 `runtime_readiness.required_paths_ready=false` 관측 근거 재확인).

### 5.2 transfer staging 관찰 (Q2 (a)+(b) 3단계 근거 분리)

**1. 로컬 실측 (이번 실행)**:
- env 변수 `THREE_PUSH_REMOTE_PACKAGE_DIR` presence: **env_variable_absent** (PC 시점).
- 값 · 절대 경로 stdout 노출 없음.
- `.env` 로드 없음.

**2. 기존 audit 근거 (`prior_audit_evidence`)** — audit §8:
- `scripts/sync_three_push_packages.py` 존재 확인 (로컬).
- `scripts/sync_three_push_runtime_param.py` 존재 확인 (로컬).
- `scripts/verify_three_push_packages_oci.py` 존재 확인 (로컬).
- `scripts/verify_three_push_param_oci.py` 존재 확인 (로컬).
- OCI 상 package fallback `content_ready` (직전 PUSH Content Gap Diagnosis v1 시 사용자 확인).
- PC↔OCI PARAM sync 의 remote `.tmp` rename 방식 (audit §8 명시).

**3. 현재 OCI 환경에서 다시 확인되지 않은 사실 (`unconfirmed_from_audit`)**:
- `remote_staging_absolute_path`
- `remote_permission`
- `remote_atomic_rename_capability`
- `remote_verify_capability`

**staging_status**: **unconfirmed_from_audit** (env 부재 + remote 실제 상태 이번 실행에서 미확인 — Q2 확정본대로 추정 금지).

---

## 6. Readiness 판정과 근거

### 6.1 PC single-environment readiness

| 구성 요소 | 상태 |
|---|---|
| market_data.sqlite | READY |
| decision_evidence.sqlite | READY (OPTIONAL) |
| runtime paths (로컬 실측 + audit 근거) | confirmed_from_local_and_prior_audit |
| staging | unconfirmed_from_audit (env 부재) |
| **PC single_environment_readiness (CLI 출력)** | **READY** |

### 6.2 Overall environment readiness (지시문 §7.2)

**PARTIAL** — 지시문 §7.2 · §9 명시:
> "PC 또는 OCI 중 한쪽 결과가 없음 → PARTIAL"
> "OCI 결과를 실측이 아닌 추정으로 기록함 → PARTIAL"

PC 단독으로는 READY 라도 OCI 실측 없이는 overall 판정 불가. **staging_confirmed_or_proven_unused 는 별도로 OCI 실측 후에도 unconfirmed_from_audit 유지 가능** (§6.7: OCI 상 remote 절대 경로 · 권한 · atomic rename 등은 이번 STEP 범위 밖).

---

## 7. OCI 미확인 항목

지시문 §10 · §6.4 규칙 그대로:

- OCI 상 `state/market/market_data.sqlite` 실제 파일 존재 · integrity_check · table_count.
- OCI 상 `state/decision/decision_evidence.sqlite` 존재 여부.
- OCI runtime write 파일 3종 (`oci_runtime_status_latest.json` / `oci_runtime_sent_registry.json` / `oci_runtime_history.jsonl`) 실제 상태.
- OCI 상 `state/runtime/three_push_runtime_probe_latest.json` 존재 여부.
- OCI 상 `state/three_push/params/latest_runtime_param.json` 존재 및 read access.
- OCI 상 `THREE_PUSH_REMOTE_PACKAGE_DIR` env 변수 presence.
- OCI 실행 revision (`git rev-parse --short HEAD`) — PC 와 동일 여부.

**추정 금지**: 위 항목은 사용자 sanitised OCI stdout 출력 도착 시에만 conclusion 에 반영.

---

## 8. 다음 Step 분기

지시문 §3 · §11 그대로:

| overall readiness | 다음 STEP 후보 |
|---|---|
| READY | PARAM / Runtime State DB Mapping v1 (다음 STEP 설계) |
| **PARTIAL (이번 시점)** | **같은 OCI Database Preflight v1 의 부족한 실측 완료 → OCI 실측 후 재판정** |
| NOT_READY | OCI Database Environment Remediation v1 (다음 STEP 설계) |

**현재 시점 다음 액션 (사용자)**:
1. 동일 commit (본 PR 병합 후 최신 `main`) 을 OCI 에 반영.
2. OCI 에서:
   ```
   python -m scripts.run_oci_database_preflight --environment oci
   git rev-parse --short HEAD
   ```
   두 줄만 실행.
3. sanitised stdout + revision 값을 새 세션에 전달.
4. 개발자가 PC · OCI 비교 → overall readiness 확정 → conclusion 최종 갱신.

**절대 전달 X**: Telegram token · chat id · 환경변수 값 원문 · 절대 경로 · credential · raw traceback (CLI 가 애초에 이를 stdout 에 담지 않음, 자동 테스트 `test_9` / `test_10` 검증).

---

## 9. 코드 · DB · JSON · runtime · API · UI · scheduler · transfer 변경 0건 확인

**git status 실측**:
```
A  scripts/run_oci_database_preflight.py       (신규 CLI, main() 에 sanitised 예외 경계 포함)
A  tests/test_oci_database_preflight.py        (신규 tests 19 케이스)
A  docs/handoff/POC2_OCI_DATABASE_PREFLIGHT_V1_CONCLUSION.md   (본 문서)
M  docs/STATE_LATEST.md
M  docs/handoff/POC2_B_NEXT_ACTIONS.md
```

**변경 없음 확인**:
- 기존 `app/**` — 0 파일 수정.
- 기존 `frontend/**` — 0 파일 수정.
- 기존 `scripts/**` — 0 파일 수정 (신규 파일 1개만 추가).
- 기존 `tests/**` — 0 파일 수정 (신규 파일 1개만 추가).
- `state/**/*.sqlite` — 자동 테스트 `test_7_db_bytes_unchanged_after_preflight` + `test_8_no_schema_or_row_change` 로 write 없음 검증.
- `state/**/*.json` — CLI 가 애초에 write 안 함, `test_11_no_persistent_artifact_created` 로 검증.
- Telegram / 외부 API / SSH — CLI 코드에서 호출 없음 (import 없음).
- scheduler / crontab / systemd — 변경 없음.

**자동 테스트 결과**:
- 신규 테스트: 19 케이스 (§8 요구 12건 + Q1 (a) 검증 2건 + argparse · revision 검증 2건 + FIX r1 sanitised failure contract 회귀 3건).
- backend 전체: **809 passed** (790 → 809, 신규 19).
- black / flake8: PASS (app / tests / scripts 전량).
- frontend: 변경 없음.
