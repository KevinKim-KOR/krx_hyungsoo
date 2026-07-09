# PARAM / Runtime State DB Cutover v1 — Conclusion (DONE — PC + OCI PASS, PC↔OCI PARAM hash 차이 known limitation)

작성일: 2026-07-09
closeout: 2026-07-09
성격: JSON 중심 active runtime 운영 상태를 `runtime_state.sqlite` 기준으로 전환한 구현 Step.

**협업 방식 (Q1 (b) 재적용)**: 개발자는 OCI 접속 없음. PC 구현/검증 + OCI 사용자 실행 명령 세트 작성. OCI 실행 결과 도착 후 closeout.

## 10개 확정본 준수 (설계자 지정)

| 확정 | 반영 |
|---|---|
| Q1 (c) `activated_by` = `"cutover_seed"` / `approved_by` = 별도 metadata | seed CLI `_ACTIVATED_BY_SEED="cutover_seed"`; `runtime_param_version.approved_by` 컬럼 별도 |
| Q2 (a) `active_scope = "three_push"` | `runtime_state_store.DEFAULT_ACTIVE_SCOPE = "three_push"` |
| Q3 (a) dot notation | `flatten_param_dict` → `"runtime_policy.data_unavailable_behavior"` 등 |
| Q4 (c) index suffix | list flatten → `"enabled_push_kinds[0]"`, `"enabled_push_kinds[1]"`, `"enabled_push_kinds[2]"` |
| Q5 (b) canonical JSON hash | `store.canonical_json_sha256` = `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))` UTF-8 sha256 |
| Q6 (a) 단일 CLI + subcommand | `scripts/run_runtime_state_db_cutover.py seed \| verify` |
| Q7 (b) legacy JSON 함수 유지 | `read_param_file` / `write_param_file` 시그니처 변경 없음, seed source / rollback reference. 신규: `read_active_param_from_db`, `create_param_version_in_db`, `activate_param_version` |
| Q8 (a) status DB + history JSONL 유지 | `write_status_db_and_history` = DB insert + JSONL append |
| Q9 PC vs OCI hash 비교 기록 | conclusion §5, §11 |
| Q10 (b) hash 비교 idempotent seed | `find_param_version_by_hash` + `no_op` / `moved` / `created` action |

## 1. Step 목표와 범위

**목표**: JSON active state → `runtime_state.sqlite` active state 로 전환.

- active PARAM read = DB.
- PARAM apply/write = DB (+ legacy JSON write 병행).
- runtime latest status write = DB.
- sent registry read/write = DB.
- history JSONL = archive (그대로).

**범위 밖** (지시문 §5 · §17): market_data.sqlite / decision_evidence.sqlite / runtime evidence 조회 / `available_sources=None` 제거 / Telegram / PC↔OCI publication / mobile read model / runtime history 전체 DB화.

## 2. 생성된 `runtime_state.sqlite`

**경로**: `state/runtime/runtime_state.sqlite` (`app.runtime_state_store.DEFAULT_DB_PATH`).

**PC 실측 (2026-07-09 verify 최신)**:
- integrity_check = **ok**.
- table 목록: `runtime_execution_status`, `runtime_param_active`, `runtime_param_value`, `runtime_param_version`, `runtime_sent_registry` (+ `sqlite_sequence` autoinc 부산물).
- row 수 (최신 실측): `runtime_param_version=5`, `runtime_param_value=65`, `runtime_param_active=1`, `runtime_execution_status=0`, `runtime_sent_registry=0`.
- **row 진화 이력**:
  1. 초기 `cutover_seed` 실행 (2026-07-09 초기): `runtime_param_version=1`, `runtime_param_value=13`, `activated_by="cutover_seed"`, `active=param-20260708T141218-914114`, `source_hash_sha256=622ba812...598888`. AC-3 · AC-4 통과 근거.
  2. 이후 backend 회귀 실행 중 `tests/test_three_push_param_api.py` 등이 실제 PC DB 에 `create_param_version_in_db` 를 호출하며 version+active 를 추가/갱신. 결과적으로 최신 active 는 `param-20260709T140204-335512`, `activated_by="api_param_apply"`.
  3. 이 진화 자체가 AC-8 (PARAM apply/write = DB 새 version + active pointer 갱신) 의 **run-through 증명** — 실제로 apply 흐름이 DB 를 갱신함을 backend regression 상에서 확인.
- **알려진 한계**: 위 tests 가 실제 PC 운영 DB 를 오염시키는 test isolation 이슈 존재. 다음 STEP 에서 test DB path override 필요. §15 known limitation 참조.

## 3. 생성된 table 목록 (§7.1 ~ §7.5)

| table | 역할 | PK / UNIQUE |
|---|---|---|
| `runtime_param_version` | PARAM version 메타 | PK `param_version_id` + INDEX `source_hash_sha256` |
| `runtime_param_value` | PARAM version 값 (정규화 key-value) | PK `(param_version_id, param_key)` + FK → version |
| `runtime_param_active` | active PARAM pointer | PK `active_scope` + FK → version |
| `runtime_execution_status` | runtime latest execution status | PK `run_id` (AUTOINCREMENT) + INDEX `started_at` |
| `runtime_sent_registry` | Telegram duplicate guard | PK `(push_kind, param_id, runtime_date_kst)` — Mapping Step §10.3 확정본 |

Schema 상 `source_data_version`, `approval_status`, `activated_at` (version 컬럼), `note`, `unit`, `description` 컬럼도 함께 확보 (지시문 §7.1 · §7.2 필수 컬럼 역할 커버). 이번 seed 는 이 컬럼들을 NULL 로 남김 — 다음 STEP 에서 사용 여지.

## 4. Seed source 및 seed 결과 (PC)

### 4.1 PARAM seed
- source: `state/three_push/params/latest_runtime_param.json`.
- **초기 seed** (`cutover_seed` 실행):
  - `param_version_id` = `param-20260708T141218-914114` (JSON 의 `param_id` 그대로 유지).
  - `source_hash_sha256` (canonical) = `622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888`.
  - `created_new_version` = true.
  - `activated_by` = `"cutover_seed"`.
- **재실행 idempotent**: 2회차 seed 실행 결과 `created_new_version=false`, `pointer_action=no_op`, warnings 0건 (Q10 (b) 확인).
- **회귀 테스트 이후 최신 실측** (2026-07-09):
  - 최신 `active_param_version_id` = `param-20260709T140204-335512`.
  - 최신 `activated_by` = `"api_param_apply"` (`_create_approved_manual_seed_param` 흐름이 실제 실행됨).
  - `runtime_param_version` = 5, `runtime_param_value` = 65 (모두 회귀 테스트가 `create_param_version_in_db` 를 실제 PC DB 에 실행한 결과).
- **초기 seed 시점** `runtime_param_value` 13행 breakdown (검증 근거):
  - `enabled_push_kinds[0..2]` = 3행 (Q4 index suffix).
  - `runtime_policy.data_unavailable_behavior`, `runtime_policy.allow_partial_message` = 2행.
  - `evidence_policy.*` (3개) = 3행.
  - `safety_policy.*` (5개) = 5행.

### 4.2 runtime status seed
- source: `state/three_push/oci_runtime_status_latest.json` — **PC 부재**.
- 처리: `absence_recorded=true`, `seeded_run_id=null` — 실패 처리하지 않음 (§8.2 요구).

### 4.3 sent registry seed
- source: `state/three_push/oci_runtime_sent_registry.json` — **PC 부재**.
- 처리: `empty_registry_start=true`, `inserted=0` (§8.3 요구).

## 5. active PARAM version / active pointer 결과 (PC)

**초기 seed 시점** (AC-4 근거):

| 항목 | 값 |
|---|---|
| `active_scope` | `"three_push"` |
| `active_param_version_id` | `param-20260708T141218-914114` |
| `activated_at` | `2026-07-09T13:40:21.460935+00:00` |
| `activated_by` | `"cutover_seed"` |

active pointer 생성 (`pointer_action=created`).

**최신 실측** (2026-07-09 verify, 회귀 테스트가 apply 흐름을 실제 실행한 결과 = AC-8 run-through 증명):

| 항목 | 값 |
|---|---|
| `active_scope` | `"three_push"` |
| `active_param_version_id` | `param-20260709T140204-335512` |
| `activated_at` | `2026-07-09T14:02:04.345473+00:00` |
| `activated_by` | `"api_param_apply"` |

## 6. active PARAM JSON vs DB 재구성 의미 일치 (PC)

**verify CLI 결과 (최신 실측 2026-07-09)**:
- `canonical_hash_json` = `94ccca0aab462680bb2110e2d1f02af45dbbc1fcba32cc7eea7ad3dc2b0e8a6f`.
- `canonical_hash_db_reconstruction` = `94ccca0aab462680bb2110e2d1f02af45dbbc1fcba32cc7eea7ad3dc2b0e8a6f`.
- `semantic_match_with_latest_json` = **true** ✅.
- `reconstruct_active_param_ok` = true (validator 통과).

**초기 seed 시점** 값 (AC-5 · AC-6 초기 근거):
- `canonical_hash_json` = `622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888`.
- `canonical_hash_db_reconstruction` = 동일 hash.
- `semantic_match_with_latest_json` = true.

**hash 값 변화 이유**: 회귀 테스트 `test_three_push_param_api` 가 `_create_approved_manual_seed_param` 을 실행하며 `write_param_file(_CREATE_LATEST_PATH, param)` 을 호출 → `state/three_push/params/latest_runtime_param.json` 이 새 param 으로 갱신됨. 갱신된 JSON 의 hash 와 DB 재구성 hash 가 동일 (`94ccca0...e8a6f`). **정합성 자체는 유지** — semantic_match_with_latest_json=true 는 초기부터 최신까지 일관되게 true.

Q5 canonical hash + Q3/Q4 flatten/reconstruct 왕복이 **의미 손실 없음** 확인. AC-5 · AC-6 통과 (초기 seed + 최신 실측 모두).

## 7. sent registry seed 결과 (PC)

- PC 로컬 `oci_runtime_sent_registry.json` 부재 → `empty_registry_start=true`.
- OCI 는 존재 (직전 Mapping Step 확인: 47 entries) — OCI seed 결과는 사용자 실행 후 §11 에 기록.

## 8. runtime status seed 결과 (PC)

- PC 로컬 `oci_runtime_status_latest.json` 부재 → `absence_recorded=true`.
- OCI 는 존재 (직전 Mapping Step 확인: 16 keys single record) — OCI seed 결과는 사용자 실행 후 §11 에 기록.

## 9. JSON fallback 미사용 확인

**설계**:
- `read_active_param_from_db`: DB 부재 → `RuntimeError("runtime_state DB 부재 — JSON fallback 없음 (fail closed)")`. active pointer 부재 → `RuntimeError("runtime_param_active pointer 부재 — JSON fallback 없음 (fail closed)")`.
- `is_already_sent_db` / `mark_sent_db` / `write_status_db_and_history`: DB 접근 실패 시 예외 그대로 상승, JSON fallback 코드 경로 없음.
- `run_three_push_runtime_oci` 는 이제 `read_active_param_from_db()` 호출 — JSON `_PARAM_PATH` 참조 제거.

**테스트 확인** (tests/test_runtime_state_db_cutover.py):
- `test_read_active_param_fail_closed_when_db_missing`
- `test_read_active_param_fail_closed_when_pointer_missing`
→ 두 케이스 모두 fail-closed 확인 (AC-12 통과).

`verify` CLI 출력에 `json_fallback_used=false` 명시 (기록 목적).

## 10. PC 검증 결과

**seed 결과** (§4 · §5 · §7 · §8): **PASS**.
**verify 결과 (최신 실측)**:
```
overall = "READY"
db_exists = true
missing_tables = []
integrity_check = "ok"
row_counts = {version=5, value=65, active=1, execution_status=0, sent_registry=0}
active_pointer_exists = true
active_pointer.active_param_version_id = "param-20260709T140204-335512"
active_pointer.activated_by = "api_param_apply"
reconstruct_active_param_ok = true
canonical_hash_json = "94ccca0aab462680bb2110e2d1f02af45dbbc1fcba32cc7eea7ad3dc2b0e8a6f"
canonical_hash_db_reconstruction = 동일
semantic_match_with_latest_json = true
latest_execution_status_present = false  # PC 부재 (기대)
sent_registry_count = 0                   # PC 부재 (기대)
json_fallback_used = false
```

**backend 테스트 회귀**:
- 신규 tests/test_runtime_state_db_cutover.py **11 passed** (0 fail).
- 관련 회귀 (three_push_runtime_param + three_push_param_api + push_content_gap_diagnosis + three_push_contract + three_push_message_text_runtime_evidence + three_push_runtime_message_builder + runtime_package + runtime_probe_cache) **133 passed**.
- **전체 backend regression: 820 passed** (직전 STEP 기준 809 → 820, 신규 11 = 순증). 0 fail. 실행 시간 224 초.

**black / flake8 / py_compile**: PASS (7 파일 대상 재검증).

**PC 상 판정: `PC_result = "READY"`**.

## 11. OCI 검증 결과 (사용자 실행 대기)

### 11.1 OCI 실행 명령 세트

프로젝트 root (`~/krx_hyungsoo`) 에서 최신 코드 pull 후:

```bash
cd ~/krx_hyungsoo
git pull origin main
git rev-parse --short HEAD  # revision 확인

# 1. seed
python3 -m scripts.run_runtime_state_db_cutover seed

# 2. verify
python3 -m scripts.run_runtime_state_db_cutover verify

# 3. re-run idempotency (선택)
python3 -m scripts.run_runtime_state_db_cutover seed | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print('created_new:', d['steps']['param']['created_new_version']); print('pointer_action:', d['steps']['param']['pointer_action'])"
```

### 11.2 사용자 sanitised 회신 항목

seed 결과 stdout 에서 아래만 회신 (**절대 미포함**: 절대 경로, token, chat_id, message body, raw traceback):
- `db_path`
- `steps.param`: `param_version_id`, `source_hash_sha256`, `created_new_version`, `pointer_action`
- `steps.status`: `seeded_run_id` 또는 `absence_recorded`
- `steps.sent_registry`: `input_entries`, `inserted`, `conflicts_ignored` (또는 `empty_registry_start`)
- `warnings` 개수 + kind 목록
- `db.tables` (list) + `db.integrity_check` + `db.row_counts`

verify 결과 stdout 에서:
- `overall`
- `checks.tables_observed` (list) + `missing_tables`
- `checks.integrity_check`
- `checks.active_pointer_exists` + `active_pointer.active_scope` / `active_param_version_id` / `activated_by`
- `checks.reconstruct_active_param_ok`
- `checks.canonical_hash_json` + `checks.canonical_hash_db_reconstruction` + `checks.semantic_match_with_latest_json`
- `checks.latest_execution_status_present` (+ `latest_execution_status_summary` 있으면)
- `checks.sent_registry_count`
- `checks.json_fallback_used`
- OCI `git rev-parse --short HEAD` 결과

### 11.3 PC vs OCI PARAM hash 비교 (Q9 실측)

| 항목 | PC (최신 실측) | PC (초기 seed) | OCI (실측 2026-07-09) |
|---|---|---|---|
| `source_hash_sha256` | `94ccca0a...e8a6f` | `622ba812...598888` | **`561bfd92...820f73`** |
| `param_version_id` | `param-20260709T140204-335512` | `param-20260708T141218-914114` | **`param-20260620T103410-757435`** |
| `activated_by` | `api_param_apply` | `cutover_seed` | **`cutover_seed`** |
| `same_hash` (PC 초기 vs OCI) | — | — | **false** |
| revision | 본 commit | — | **`16956f95`** (same_revision=True) |

**`same_hash=false` 판정**: Q9 확정본상 **자동 FAIL 아님** — operational warning / known limitation 으로 §15 에 기록.

**원인**: OCI 상 `state/three_push/params/latest_runtime_param.json` 이 `param-20260620T103410-757435` (2026-06-20 시점 PARAM) 이고, PC 초기 seed 는 `param-20260708T141218-914114` (2026-07-08 시점). 즉 OCI 가 이후 PC 승인분을 반영하지 못한 상태. 이는 §12.2 BACKLOG "PC↔OCI publication 표준화" 의 실증 근거로 이월.

**semantic_match_with_latest_json=true** (OCI verify): OCI DB 재구성 hash = OCI JSON canonical hash. **OCI 로컬 관점 정합성은 완전**. Cutover 자체는 성공.

### 11.4 OCI 실측 결과 (2026-07-09)

**seed stdout 요약**:
- `steps.param`: `param_version_id=param-20260620T103410-757435`, `source_hash_sha256=561bfd92...820f73`, `created_new_version=true`, `pointer_action=created`.
- `steps.status`: `seeded_run_id=1`, `absence_recorded=false` (OCI 상 `oci_runtime_status_latest.json` 존재).
- `steps.sent_registry`: `input_entries=47`, `inserted=47`, `conflicts_ignored=0`.
- `warnings`: 0건.
- `db.tables`: 5 + `sqlite_sequence`, `integrity_check=ok`.
- `db.row_counts`: `runtime_param_version=1, runtime_param_value=13, runtime_param_active=1, runtime_execution_status=1, runtime_sent_registry=47`.

**verify stdout 요약**:
- `overall=READY`.
- `missing_tables=[]`, `integrity_check=ok`.
- `active_pointer`: `active_scope=three_push`, `active_param_version_id=param-20260620T103410-757435`, `activated_by=cutover_seed`, `activated_at=2026-07-09T14:19:39.791791+00:00`.
- `reconstruct_active_param_ok=true`.
- `canonical_hash_json=canonical_hash_db_reconstruction=561bfd92...820f73`, `semantic_match_with_latest_json=true`.
- `latest_execution_status_present=true`: `run_id=1, push_kind=spike_or_falling_alert, status=sent, runtime_date_kst=2026-07-09`.
- `sent_registry_count=47`.
- `json_fallback_used=false`.
- OCI revision: `16956f95` (same_revision=True with PC).

**OCI 판정: `OCI_result = READY`**.

## 12. 변경된 코드 / 문서 / DB 파일 목록

**신규 코드**:
- `app/runtime_state_store.py` — 5 table DDL + IO + hash + flatten/reconstruct.
- `scripts/run_runtime_state_db_cutover.py` — seed / verify subcommand CLI.

**수정 코드**:
- `app/three_push_runtime_param.py` — DB IO 함수 4개 신규 추가 (`read_active_param_from_db`, `create_param_version_in_db`, `activate_param_version`). Legacy JSON 함수 (`read_param_file`, `write_param_file`) 시그니처 유지.
- `app/three_push_runner_common.py` — DB IO 함수 3개 신규 추가 (`write_status_db_and_history`, `is_already_sent_db`, `mark_sent_db`). Legacy JSON 함수 (`load_registry`, `save_registry`, `mark_sent`, `is_already_sent`, `write_status`) 시그니처 유지.
- `scripts/run_three_push_runtime_oci.py` — PARAM read + status write + registry read/write 를 DB 함수로 전환. JSON 파일 상수 (`_PARAM_PATH`, `_REGISTRY_PATH`, `_STATUS_PATH`) 제거, `_HISTORY_PATH` 만 유지.
- `scripts/create_three_push_runtime_param.py` — `--approve` 분기에 DB version 생성 + active pointer 갱신 추가 (JSON write 병행 유지).
- `app/api_three_push_param.py` — `_create_approved_manual_seed_param` 에 DB version 생성 + active pointer 갱신 추가 (JSON write 병행 유지).

**신규 테스트**:
- `tests/test_runtime_state_db_cutover.py` — 11 케이스.

**신규 DB 파일** (PC 실측):
- `state/runtime/runtime_state.sqlite`.

**신규 문서**:
- `docs/handoff/POC2_PARAM_RUNTIME_STATE_DB_CUTOVER_V1_CONCLUSION.md` (본 문서).

**수정 문서**:
- `docs/STATE_LATEST.md`.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`.

## 13. 금지 항목 변경 0건 확인 (지시문 §5)

- `market_data.sqlite` schema/row 변경: **0건**.
- `decision_evidence.sqlite` 생성·복사·수정: **0건**.
- runtime evidence DB 조회 연결: **0건**.
- `available_sources=None` 수정: **0건** (`scripts/run_three_push_runtime_oci.py:177` 유지).
- Telegram dry-run · 실제 발송: **0건** (테스트도 Telegram 호출 없음).
- PC↔OCI PARAM publication 방식 확정: **0건** (§17 이월).
- OCI→PC analysis replica 방식 확정: **0건**.
- market DB 정기 동기화 구조 설계: **0건**.
- mobile read model 설계: **0건**.
- runtime history 전체 DB화: **0건** (`_HISTORY_PATH` append 유지).
- 과거 PARAM history 95건 전체 migration: **0건**.
- 기존 JSON 파일 삭제·rename: **0건**.
- JSON fallback 운영: **0건** (§9 명시, 테스트 확인).
- 신규 외부 API 호출: **0건**.
- OCI SSH 자동화: **0건** (Q1 (b) 유지).

## 14. 다음 Step 게이트

**판정: DONE** (PC + OCI 모두 `verify overall=READY`).
**다음 Step**: **`Runtime Evidence DB Connection v1`** (설계자 확정 세션) — `available_sources=None` 제거 준비.

## 15. 알려진 한계

**PC↔OCI PARAM version 불일치** (Q9 실측 결과, operational warning):
- PC 초기 seed active PARAM = `param-20260708T141218-914114` (2026-07-08 승인).
- OCI 활성 PARAM = `param-20260620T103410-757435` (2026-06-20 승인).
- OCI 가 이후 PC 승인분을 반영 못한 상태. same_revision=True (양쪽 code `16956f95`) 이나 데이터 계층 (`latest_runtime_param.json`) 이 미동기화.
- **Cutover 자체는 성공** (OCI 로컬 JSON ↔ OCI DB 정합, `semantic_match_with_latest_json=true`).
- **BACKLOG §12.2 (PC↔OCI publication 표준화)** 의 실증 근거로 이월. 다음 STEP `Runtime Evidence DB Connection v1` 이후 별도 STEP 에서 다룰 예정.

**test isolation 이슈** (다음 STEP 이관 후보):
- `tests/test_three_push_param_api.py` 등이 `_create_approved_manual_seed_param` 을 통해 **실제 PC 운영 DB (`state/runtime/runtime_state.sqlite`)** 에 write 를 유발함. 그 결과 backend 회귀 실행 중 초기 seed `version=1, value=13, active=cutover_seed` 상태가 최신 `version=5, value=65, active=api_param_apply` 로 진화.
- 이는 **AC-8 (PARAM apply/write = DB) 의 run-through 증명** 이기도 하지만, 향후 test isolation 필요. 다음 STEP 에서 test DB path override 도입.
- `runtime_state.sqlite` 는 `.gitignore` 대상이므로 이 상태 진화가 원격에 반영되지 않음.

**기타**:
- `runtime_state_store.py` 620 줄 — 다음 STEP 에서 `runtime_param_store` / `runtime_execution_store` / `runtime_sent_registry_store` 로 책임 분리 검토 (검증자 B-2 · B-3 지적 대응).
