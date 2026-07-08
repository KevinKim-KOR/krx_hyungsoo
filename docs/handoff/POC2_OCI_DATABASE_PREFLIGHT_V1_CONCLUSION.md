# OCI Database Preflight v1 — Conclusion (DONE, overall NOT_READY)

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

**PC · OCI 교차 실측 완료 (2026-07-08)**:

| 항목 | PC | OCI |
|---|---|---|
| 실행 revision (short git hash) | `fd7ff116` | `fd7ff116` |
| `--environment` 인자 | `pc` | `oci` |
| 실행 명령 | `python -m scripts.run_oci_database_preflight --environment pc` | `python -m scripts.run_oci_database_preflight --environment oci` |
| CLI 결과 single_environment_readiness | **READY** | **NOT_READY** |

**Same-revision 검증**: PC `fd7ff116` = OCI `fd7ff116` → **same_revision=True** (지시문 §6.3 · §9 준수).

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

**OCI 실측 (revision `fd7ff116`)**:

| 항목 | 값 |
|---|---|
| 프로젝트 상대 경로 | `state/market/market_data.sqlite` |
| path resolution 상태 | `resolved` (single_canonical_path) |
| 파일 존재 여부 | **False** |
| regular file 여부 | False |
| read access | False |
| read-only open | False |
| PRAGMA integrity_check | None |
| table 목록 (개수) | None |
| 파일 크기 | None |
| **개별 readiness (§7.1)** | **NOT_READY** |

**결정적 관측**: 기준 DB (`state/market/market_data.sqlite`) 가 OCI 에 부재. 다음 STEP `OCI_DATABASE_ENVIRONMENT_REMEDIATION` 의 최우선 대상.

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

**OCI 실측 (revision `fd7ff116`)**:

| 항목 | 값 |
|---|---|
| 프로젝트 상대 경로 | `state/decision/decision_evidence.sqlite` |
| 존재 여부 | **False** |
| **readiness** | **OPTIONAL_MISSING** (지시문 §7.2 그대로 overall 실패 강제 X) |

OCI 상 부재는 향후 역할이 확정되지 않은 optional DB 이므로 이번 STEP overall 판정에서 제외 (§6.6 준수). 다음 STEP 매핑에서 다룸.

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

**OCI 실측 (revision `fd7ff116`)**:

| 경로 | exists | regular_file | read_access |
|---|---|---|---|
| `state/three_push/params/latest_runtime_param.json` | True | True | True |
| `state/three_push/oci_runtime_status_latest.json` | **True** | True | True |
| `state/three_push/oci_runtime_sent_registry.json` | **True** | True | True |
| `state/three_push/oci_runtime_history.jsonl` | **True** | True | True |
| `state/runtime/three_push_runtime_probe_latest.json` | False | False | False |

**OCI runtime_paths_status**: `confirmed_from_local_and_prior_audit`.

**핵심 관측 (OCI 만의 신규 확인)**:
- OCI runtime write 파일 3종 (`oci_runtime_status_latest.json` / `oci_runtime_sent_registry.json` / `oci_runtime_history.jsonl`) 모두 실제 존재 → PARAM runtime 이 OCI 상에서 실제 실행되고 있음.
- 반면 `three_push_runtime_probe_latest.json` 은 OCI 상 부재 → OCI runtime probe cache 가 아직 채워지지 않음 (audit 상 `sqlite_integrity=unavailable` + `required_paths_ready=false` 관측 근거 재확인).

**PC · OCI 교차 관측**:

| 경로 | PC | OCI |
|---|---|---|
| `latest_runtime_param.json` | True | True |
| `oci_runtime_status_latest.json` | False | **True** |
| `oci_runtime_sent_registry.json` | False | **True** |
| `oci_runtime_history.jsonl` | False | **True** |
| `three_push_runtime_probe_latest.json` | True | **False** |

OCI runtime write 파일은 OCI 에서만, PC 로컬 probe cache 는 PC 에서만 채워짐 — 각자 역할대로 분리 실행되고 있음.

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

### 6.2 OCI single-environment readiness (revision `fd7ff116`)

| 구성 요소 | 상태 |
|---|---|
| market_data.sqlite | **NOT_READY** (파일 부재) |
| decision_evidence.sqlite | OPTIONAL_MISSING (§6.6 준수, overall 실패 강제 X) |
| runtime paths | confirmed_from_local_and_prior_audit (4 exists / 1 부재) |
| staging | unconfirmed_from_audit (env 부재, Q2 확정본 준수) |
| **OCI single_environment_readiness (CLI 출력)** | **NOT_READY** |

### 6.3 Overall environment readiness (지시문 §7.2) — 확정

**NOT_READY** — 지시문 §7.2 명시:
> "PC 와 OCI 실행은 모두 완료됐으나 market_data.sqlite, path resolution, read access, integrity, runtime path, staging 중 하나 이상이 준비되지 않음 → NOT_READY"

**판정 근거**:
- PC · OCI 양쪽 실행 완료 ✅
- same_revision (`fd7ff116` = `fd7ff116`) ✅
- OCI `market_data.sqlite` **부재** → 이 하나로 NOT_READY 판정 확정
- staging 은 `unconfirmed_from_audit` 유지 (§6.7 명시: 이번 STEP 범위 밖)

**진단 결과이며 STEP 실패가 아님** (지시문 §7.3): "이후 schema, PARAM migration, runtime rewire 로 진행 금지 / 확인된 OCI 환경 결함만 다루는 remediation Step 이 필요".

---

## 7. OCI 실측 후 확인된 사실 vs 여전히 미확인

### 7.1 이번 OCI 실측에서 확인된 사실

- OCI `state/market/market_data.sqlite`: **부재** (exists=False).
- OCI `state/decision/decision_evidence.sqlite`: **부재** (exists=False).
- OCI runtime write 파일 3종 (`oci_runtime_status_latest.json` / `oci_runtime_sent_registry.json` / `oci_runtime_history.jsonl`): **모두 존재** — PARAM runtime 이 OCI 상에서 실제 실행되고 있음 (write 결과물 존재가 이를 증명).
- OCI `state/runtime/three_push_runtime_probe_latest.json`: **부재** — OCI 상 probe cache 미형성.
- OCI `state/three_push/params/latest_runtime_param.json`: **존재** (read_access=True) — active PARAM 이 OCI 에 반영되어 있음.
- OCI 실행 revision: `fd7ff116` = PC revision `fd7ff116` (**same_revision=True**).

### 7.2 여전히 미확인 (§6.4 · §6.7 규칙 그대로 유지)

- OCI 상 `THREE_PUSH_REMOTE_PACKAGE_DIR` env 변수 presence: `env_variable_absent` (Q2 확정본대로 추정 · `.env` 로드 · 기본 경로 추론 없음).
- OCI 상 remote transfer staging 실제 절대 경로 · 권한 · atomic rename · verify 가능 여부: `unconfirmed_from_audit` (§6.7: 이번 STEP 범위 밖, 다음 STEP 에서 다룸).

**추정 금지 원칙 준수**: 이번 실측에서 확인되지 않은 항목은 "확인됨" 으로 표기하지 않음.

---

## 8. 다음 Step 분기 (확정)

지시문 §3 · §11 그대로:

| overall readiness | 다음 STEP 후보 | 이번 판정 |
|---|---|---|
| READY | PARAM / Runtime State DB Mapping v1 | — |
| **NOT_READY** | **`OCI Database Environment Remediation v1`** | **✅ 확정** |
| PARTIAL | 같은 OCI Database Preflight v1 이어서 완료 | — |

**다음 STEP 유형**: `OCI Database Environment Remediation v1`.

**주요 remediation 대상** (OCI 실측 근거):
- OCI `state/market/market_data.sqlite` 부재 → 초기화 / 시드 반영 방식 설계.
- OCI `state/runtime/three_push_runtime_probe_latest.json` 부재 → probe cache 형성 흐름 확인.
- OCI staging 실제 경로 · 권한 · atomic rename · verify 가능 여부 확인 (§6.7 다음 STEP 이관 항목).

**이번 STEP 안에서는 remediation 을 구현하지 않음** (지시문 §7.3): "이후 schema, PARAM migration, runtime rewire 로 진행 금지".

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
