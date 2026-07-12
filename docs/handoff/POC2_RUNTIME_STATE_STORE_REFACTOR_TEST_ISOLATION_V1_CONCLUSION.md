# Runtime State Store Refactor & Test Isolation v1 — Conclusion

작성일: 2026-07-10
성격: PARAM / Runtime State DB Cutover v1 잔여 구조 부채 (B-2 · B-3 · B-6) 해소 STEP. **새 기능 없음.**

## 1. Step 목표와 범위

**목표**: `runtime_state_store.py` 단일 책임 과다 (620줄) 해소 + 테스트 격리 (실제 운영 DB 오염 방지).

**범위**:
- `app/runtime_state_store.py` 를 4개 모듈로 완전 분리 (기존 파일 삭제).
- `three_push_runtime_param.py` / `three_push_runner_common.py` 안의 DB IO 함수 각 신규 store 로 이전.
- 프로덕션 call site 전환 (runner + api + create + cutover CLI + tests).
- `tests/conftest.py` 에 autouse fixture 추가 (`DEFAULT_DB_PATH` 를 `tmp_path` 로 monkeypatch).
- 실제 운영 DB 불변 test 신설.

**범위 밖** (지시문 §4 금지 · §추가 운영 기준):
- `runtime_state.sqlite` schema 변경 · row migration.
- PARAM 정책 변경 · sent registry unique 기준 변경.
- runtime evidence DB 연결 · `available_sources=None` 수정.
- Telegram dry-run · 실제 발송.
- `market_data.sqlite` · `decision_evidence.sqlite` 변경.
- UI · API 기능 추가 · scheduler 변경.

## 2. B-2 · B-3 · B-6 처리 결과

| 부채 | 처리 |
|---|---|
| B-2 단일 책임 과다 | 4개 store 로 분리 (schema + PARAM + execution status + sent registry) |
| B-3 파일 620줄 | 삭제 완료. 각 신규 store 는 개별 책임만 담당 |
| B-6 test isolation 미흡 | `tests/conftest.py` 에 `_isolated_runtime_state_db` autouse fixture 추가. 신규 `tests/test_runtime_state_isolation.py` 로 실제 DB 불변 검증 |

## 3. 분리된 모듈 목록과 각 책임

| 모듈 | 책임 | 비책임 |
|---|---|---|
| `app/runtime_state_db.py` | `DEFAULT_DB_PATH`, `DEFAULT_ACTIVE_SCOPE`, 5 table DDL, `init_db`, `connection` context manager, `list_tables`, `integrity_check`, `table_row_counts`, `canonical_json_sha256`, `utc_now_iso` | 비즈니스 로직 (PARAM/status/registry 도메인 함수 없음) |
| `app/runtime_param_store.py` | PARAM `flatten_param_dict` / `reconstruct_param_dict`, `find_param_version_by_hash`, `insert_param_version`, `read_param_version`, `get_active_pointer`, `set_active_pointer`, `create_param_version`, `activate_param_version`, `read_active_param_dict` (fail-closed) | schema DDL / connection helper (runtime_state_db) |
| `app/runtime_execution_status_store.py` | `insert_execution_status`, `insert_status_from_record`, `latest_execution_status` | history JSONL append (runner Q9 c) |
| `app/runtime_sent_registry_store.py` | `contains`, `insert` (INSERT OR IGNORE), `count`, `is_already_sent`, `mark_sent` | duplicate guard unique 기준 변경 금지 |

## 4. schema 변경 없음 확인 (AC-3, AC-4)

**기존 5 table DDL 을 `runtime_state_db.py` 로 그대로 이동** — 컬럼 이름 · 타입 · PK · FK · INDEX 모두 Cutover v1 원본 유지:

- `runtime_param_version` (PK `param_version_id`, INDEX `source_hash_sha256`).
- `runtime_param_value` (PK `(param_version_id, param_key)`).
- `runtime_param_active` (PK `active_scope`).
- `runtime_execution_status` (PK `run_id AUTOINCREMENT`, INDEX `started_at`).
- `runtime_sent_registry` (PK `(push_kind, param_id, runtime_date_kst)`).

## 5. active PARAM / status / registry 동작 유지 확인 (AC-5 ~ AC-10)

| AC | 검증 방식 |
|---|---|
| AC-5 active PARAM reconstruction 동일 | `test_flatten_and_reconstruct_roundtrip` — canonical hash 왕복 (Q5 기준). Cutover v1 결과와 동일 알고리즘 (`sort_keys+separators`). |
| AC-6 PARAM apply/write DB version + active pointer | `test_idempotent_version_reuse_by_hash` — 같은 hash 재실행 시 재사용. `_create_approved_manual_seed_param` / `create --approve` 는 `create_param_version` + `activate_param_version` 병행 호출. |
| AC-7 runtime latest status writer DB | `run_three_push_runtime_oci._finish` 가 `insert_status_from_record(record)` 호출. |
| AC-8 sent registry read/write DB | runner 가 `is_already_sent` / `mark_sent` 호출 (신규 store, INSERT OR IGNORE 유지). |
| AC-9 JSON fallback fail-closed | `read_active_param_dict` — DB 부재 / pointer 부재 시 RuntimeError. `test_read_active_param_fail_closed_when_db_missing` / `test_read_active_param_fail_closed_when_pointer_missing`. |
| AC-10 history JSONL log/archive 유지 | runner 가 별도로 `_HISTORY_PATH.open("a")` append. DB store 안에 JSONL append 없음 (Q9 c 분리). |

## 6. test isolation 방식 (AC-11, AC-12)

**tests/conftest.py 신규 autouse fixture**:

```python
@pytest.fixture(autouse=True)
def _isolated_runtime_state_db(tmp_path, monkeypatch):
    from app import runtime_state_db as _rt_db
    test_db_path = Path(tmp_path) / "runtime_state.sqlite"
    monkeypatch.setattr(_rt_db, "DEFAULT_DB_PATH", test_db_path)
    _rt_db.reset_init_cache_for_testing()
    yield
    _rt_db.reset_init_cache_for_testing()
```

**격리 범위**:
- `runtime_state_db.DEFAULT_DB_PATH` 만 override. `market_data.sqlite` / `decision_evidence.sqlite` 등 다른 DB path 는 건드리지 않음.
- 각 store 는 `db_path` 가 명시적으로 주어지지 않으면 `DEFAULT_DB_PATH` 를 사용 → monkeypatch 만으로 전 store 격리.
- `_INITIALIZED_DBS` init cache 도 test 마다 reset.

## 7. 실제 운영 DB 오염 방지 확인 (AC-11)

**신규 test**: `tests/test_runtime_state_isolation.py`
- `test_default_db_path_is_monkeypatched_to_tmp_path` — `DEFAULT_DB_PATH` 가 실제 path 가 아닌지 확인.
- `test_param_apply_writes_to_tmp_not_real_db` — `create_param_version` + `activate_param_version` 실행 후 실제 `state/runtime/runtime_state.sqlite` 의 size/mtime/sha256 (또는 absent) 이 그대로인지 확인.

**리팩토링 전후 실측 (`state/runtime/runtime_state.sqlite`)**:

| 시점 | exists | size | sha256 | mtime |
|---|---|---|---|---|
| Refactor 착수 시 (Cutover v1 마지막 실행 뒤) | True | 69632 | `5d09a0068bf659720aa1cc1c81a8f5f8ecc02422345b0f5cb880ec1421442861` | 1783605724.35 |
| Refactor 첫 test 실행 후 (conftest fixture 활성화 전) | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |
| conftest fixture 활성화 이후 | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |
| **backend 823 passed 회귀 실행 후** | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |

**해석**:
- **첫 hash 변화** (`5d09a006... → 8ae7f118...`): conftest fixture 를 아직 넣지 않은 상태에서 신규 isolation test 를 처음 실행할 때 (그리고 그 전에 잠깐 실제 store 사용 회귀 test 가 실행될 때) 실제 PC DB 가 `api_param_apply` 흐름에 의해 1회 오염됨. 이는 **B-6 이슈가 재현된 것이며, isolation fixture 부재 상황의 정확한 증거**.
- **conftest fixture 활성화 후**: `test_param_apply_writes_to_tmp_not_real_db` 안에서 실측한 before/after snapshot 이 동일함을 assert. `create_param_version` + `activate_param_version` 이 실제 DB 를 건드리지 않음이 확인됨. `.gitignore` 로 tracked 되지 않으므로 원격에 오염 미전파.

**향후 규칙**: Refactor 완료 후 test 는 모두 tmp DB 만 사용. 실제 PC DB 는 사용자 수동 seed (`python -m scripts.run_runtime_state_db_cutover seed`) 로만 갱신.

## 8. 테스트 결과 (AC-13)

- 신규 `tests/test_runtime_state_db_cutover.py`: 12 케이스 (기존 11 + `test_insert_status_from_record_maps_availability`).
- 신규 `tests/test_runtime_state_isolation.py`: 2 케이스 (isolation 검증).
- **전체 backend regression: 823 passed** (직전 820 → 823, 신규 3 = isolation 2 + status_from_record 1). 0 fail. 실행 시간 206s.
- **실제 DB 불변 확인**: 회귀 전 hash `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57`, 회귀 후 동일. mtime 도 동일. **conftest fixture 가 823 test 실행 중 실제 PC DB 를 단 1 byte 도 건드리지 않음** = AC-11 · AC-12 완전 통과.
- black / flake8 / py_compile PASS.

## 9. 금지 항목 변경 0건 확인 (AC-3, AC-14)

- runtime_state.sqlite schema 변경: 0.
- DB row migration: 0.
- PARAM 정책 변경: 0.
- sent registry unique 기준 변경: 0.
- `available_sources=None` 수정: 0.
- Telegram dry-run / 실제 발송: 0.
- market_data.sqlite / decision_evidence.sqlite 변경: 0.
- runtime evidence DB 연결: 0.
- UI / API 신규 기능 · scheduler 변경: 0.

## 10. `runtime_state_store.py` 삭제 사유 및 대체 모듈 (Q1c · Q3)

- 삭제 사유: B-2 (단일 책임 과다) 완전 해소. shim/re-export 유지 시 검증자 판정상 "한 파일이 여전히 3 책임의 관문" 으로 이월됨. Q3 확정본 상 삭제 진행.
- 대체 모듈 매핑:

| 삭제 심볼 | 대체 위치 |
|---|---|
| `DEFAULT_DB_PATH`, `DEFAULT_ACTIVE_SCOPE`, DDL 상수, `init_db`, `_connection`, `list_tables`, `integrity_check`, `table_row_counts`, `canonical_json_sha256`, `TABLE_NAMES`, `reset_init_cache_for_testing` | `app/runtime_state_db.py` |
| `flatten_param_dict`, `_walk`, `_split_value_columns`, `_value_of`, `_assign_by_path`, `find_param_version_by_hash`, `insert_param_version`, `read_param_version`, `reconstruct_param_dict`, `get_active_pointer`, `set_active_pointer` | `app/runtime_param_store.py` (동명 + 신규 high-level API `create_param_version` / `activate_param_version` / `read_active_param_dict`) |
| `insert_execution_status`, `latest_execution_status` | `app/runtime_execution_status_store.py` (+ 신규 `insert_status_from_record`) |
| `registry_contains`, `registry_insert`, `registry_count` | `app/runtime_sent_registry_store.py` (`contains`, `insert`, `count` 로 명명 · `is_already_sent`, `mark_sent` high-level API 추가) |

`three_push_runtime_param.py` 안의 legacy DB wrapper (`read_active_param_from_db`, `create_param_version_in_db`, `activate_param_version`) 3개 및 `three_push_runner_common.py` 안의 legacy DB wrapper (`write_status_db_and_history`, `is_already_sent_db`, `mark_sent_db`) 3개도 신규 store 로 이전 후 삭제 (Q7a · Q8a 확정).

## 11. 다음 Step 게이트

**PASS 판정 시**:
- `PARAM / Runtime State DB Cutover v1` 을 최종 PASS 상태로 고정.
- 다음 활성 Step: **`Runtime Evidence DB Connection v1`** (설계자 확정 세션).

**Q10 legacy JSON 함수 유지** (Cutover v1 계약 그대로): `read_param_file`, `write_param_file` (three_push_runtime_param.py), `write_status`, `load_registry`, `save_registry`, `mark_sent`, `is_already_sent` (three_push_runner_common.py) — active runtime 경로에서는 호출되지 않으며, legacy reference / rollback source 로 유지. conclusion 반영.

**Q11 `.gitignore` 유지** (Cutover v1 확정): `state/runtime/runtime_state.sqlite{,-journal,-wal,-shm}` 4줄 유지.
