# Runtime State Store Refactor & Test Isolation v1 — Conclusion (VERIFIED)

작성일: 2026-07-10 (원본), FIX r1: 2026-07-12
**검증자 최종 판정: VERIFIED** (2026-07-12, HEAD `f43e5565`).
성격: PARAM / Runtime State DB Cutover v1 잔여 구조 부채 (B-2 · B-3 · B-6) 해소 STEP. **새 기능 없음.**

## 0. FIX r1 요약 (2026-07-12, 설계자 11개 확정본 준수)

**원인**: Refactor v1 commit `93539635` 이후 사용자 실행한 실제 verify 결과 상 아래 오염 상태 발견 → 설계자 REJECTED (FIX r1 지시):
- `active_pointer.activated_by = "isolation_test"` (test marker 오염)
- `semantic_match_with_latest_json = false` (DB 재구성 hash `bb46e538...` vs latest JSON canonical hash `d9bd0694...` 불일치)
- 그럼에도 verify `overall = READY` (판정 취약)

**Q2 조건부 판단 근거** (설계자 확정본):
- 현재 `latest_runtime_param.json` (Refactor 이전) 파일 mtime = 2026-07-12 17:37 = Refactor v1 commit (17:32) 직후. 사용자 승인 flow 실행 이력 없음.
- 이 파일은 git tracked 아님 + git log 상 존재한 적 없음 → 원격/역사 복구 불가.
- history 폴더 mtime 역추적 결과: 2026-07-08 ~ 2026-07-12 사이 신규 param 파일 8개 = 모두 회귀 test 오염분 (`test_three_push_param_api._create_approved_manual_seed_param` 매 실행마다 `build_manual_seed_param()` 생성).
- **마지막 정상 사용자 승인 PARAM = `param-20260708T141218-914114`** (2026-07-08 23:12 KST, Cutover v1 CONCLUSION §2 · §4.1 초기 seed source 로 문서 기록). → **Q2 case (2)** 진입: latest JSON 을 이 승인분으로 복구 후 clean seed.

**FIX-before 실측 (오염 상태)**:
- DB: size=69632, sha256=`8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57`, row_counts={version:7, value:91, active:1, exec_status:0, sent_registry:0}.
- active_pointer: `param-20260712T080716-572622`, `activated_by="isolation_test"`, `activated_at=2026-07-12T08:07:16.577421+00:00`.
- latest JSON: size=884, file sha256=`3e9c9ff4854d79b71bd3308a595a33d9240954ea37d8edaf6cfea4e939ed289c`, canonical hash `d9bd0694a995c7440c057ac42acf3d33b96c07a6d421a2c2d6257838724c136a`, param_id `param-20260712T083741-019335`.
- semantic_match_with_latest_json = false. verify (원본) `overall = READY`.

**FIX 작업**:
1. `state/three_push/params/latest_runtime_param.json` ← `state/three_push/params/history/param-20260708T141218-914114.json` 복사로 복구. canonical hash `622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888` (Cutover v1 §2 문서 기록값 정확 일치).
2. `state/runtime/runtime_state.sqlite` 삭제 후 `python -m scripts.run_runtime_state_db_cutover seed` clean 재실행.
3. `scripts/run_runtime_state_db_cutover.py` verify CLI 강화 (Q3 · Q6 확정본):
   - `_TEST_ACTIVATED_BY_MARKERS = {"isolation_test", "test"}` 상수 신설.
   - `active_pointer.activated_by ∈ marker` → `overall=NOT_READY` + `readiness_errors:["active_pointer_activated_by_test_marker:<value>"]`.
   - `semantic_match_with_latest_json == False` → `overall=NOT_READY` + `readiness_errors:["db_reconstruction_diverges_from_latest_json"]`.
   - `readiness_errors: []` 필드 항상 방출. exit code 정책은 유지 (Q5).
4. verify 강화 자체 검증: `activate_param_version(..., activated_by="isolation_test")` 삽입 → verify NOT_READY 확인 → 원상 (`cutover_seed`) 복구.

**FIX-after clean baseline**:
- DB: size=53248, sha256=`324393d6c77b3f6be75769eb5890db028e5c2a94e14eae2698512465109df79c` (clean seed 직후 실측).
- active_pointer: `param-20260708T141218-914114`, `activated_by="cutover_seed"`.
- canonical_hash_json = canonical_hash_db_reconstruction = `622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888`.
- semantic_match_with_latest_json = true. verify `overall = READY`, `readiness_errors: []`, `json_fallback_used = false`.
- row_counts: {version:1, value:13, active:1, exec_status:0, sent_registry:0} (Q7: PC 환경 exec_status/sent_registry=0 정상).

**추가 발견 & 대응** (첫 pytest 회귀 실행 중 발견):
- 첫 회귀 실행 후 real DB (`state/runtime/runtime_state.sqlite`) 는 완전 불변 확인 (isolation fixture 정상). 그러나 `state/three_push/params/latest_runtime_param.json` 이 pytest 중 갱신 (mtime + hash 변경) 발견. 원인: `_create_approved_manual_seed_param` (api_three_push_param.py) / `create_three_push_runtime_param --approve` 가 legacy JSON write 병행 → 실제 파일 오염 유발. 다음 회귀에서 verify 가 다시 `semantic_match_with_latest_json=false` 로 판정할 root cause.
- 조치 (`tests/conftest.py` `_isolated_runtime_state_db` fixture 확장):
  - `app.api_three_push_param._LATEST_PATH` → `tmp_path/three_push/params/latest_runtime_param.json` 로 monkeypatch.
  - `scripts.create_three_push_runtime_param._LATEST_PATH` / `_HISTORY_DIR` / `_PARAM_DIR` → `tmp_path/...` 로 monkeypatch.
  - 설계자 지시문 §2 원문은 DB 만 명시하나, verify 재실행 조건 (semantic_match=true) 을 실질 만족하려면 legacy JSON 도 격리 필요 = 이번 FIX 안에서 함께 해소가 옳음.
- 이후 latest JSON 을 다시 복구 (`param-20260708T141218-914114`) + DB 삭제 + clean seed 재실행 → 이 시점 baseline 을 기준으로 pytest 재회귀.

**test isolation 재검증 최종** (Q9 확정본, pytest 전/후 실측 대조):

| 항목 | BEFORE pytest | AFTER pytest | 결과 |
|---|---|---|---|
| `state/runtime/runtime_state.sqlite` size | 53248 | 53248 | ✅ 불변 |
| `state/runtime/runtime_state.sqlite` sha256 | `f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e` | 동일 | ✅ 불변 |
| `state/runtime/runtime_state.sqlite` mtime | 1783846900.8138113 | 동일 | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` size | 884 | 884 | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` sha256 | `84151b5659abba0a8622af3e418856e5512e3f290c6fd50a0697b0609af422aa` | 동일 | ✅ 불변 |
| `state/three_push/params/latest_runtime_param.json` mtime | 1783846900.6387017 | 동일 | ✅ 불변 |
| active_pointer.active_param_version_id | `param-20260708T141218-914114` | 동일 | ✅ 불변 |
| active_pointer.activated_by | `cutover_seed` | 동일 | ✅ 불변 |

**FIX r1 최종 backend regression**: **827 passed** (Refactor v1 823 → FIX r1 827, verify 강화 4 순증). 0 fail, 202s. black / flake8 / py_compile PASS.

**FIX-after 최종 verify (강화 CLI)**:
```
overall = READY
readiness_errors = []
active_pointer = { active_scope: three_push, active_param_version_id: param-20260708T141218-914114,
                   activated_at: 2026-07-12T09:01:40.811910+00:00, activated_by: cutover_seed }
canonical_hash_json           = 622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888
canonical_hash_db_reconstruction = 622ba812b43a03373c9efb80fbd9c74480bb2b46838574fd46c9f6a499598888
semantic_match_with_latest_json = true
json_fallback_used = false
row_counts = {version:1, value:13, active:1, exec_status:0, sent_registry:0}
```

**verify 강화 자체 검증**: `activate_param_version(..., activated_by="isolation_test")` 인위 삽입 → verify `overall=NOT_READY`, `readiness_errors=["active_pointer_activated_by_test_marker:isolation_test"]` 확인 → 원상 복구. 강화 정상 작동.

**FIX r1 판정: PASS**
- 실제 DB active_pointer.activated_by = `cutover_seed` (test marker 아님).
- semantic_match_with_latest_json = true (정상 승인분 = DB reconstruction 일치).
- pytest 전/후 실제 DB + latest JSON 모두 완전 불변.
- verify CLI 판정 강화 완료 (test marker + semantic mismatch → NOT_READY + readiness_errors 기록).

**최종 상태**: `PARAM / Runtime State DB Cutover v1` 최종 PASS 자격 확보. 다음 STEP `Runtime Evidence DB Connection v1` 진입 가능.

**Q10**: DB 는 `.gitignore` 대상 → commit 안 함. commit 대상: `scripts/run_runtime_state_db_cutover.py` (verify 강화) + docs (본 CONCLUSION, STATE_LATEST, POC2_B_NEXT_ACTIONS) + `state/three_push/params/latest_runtime_param.json` 복구 (테스트 오염 복구로 명시적 기록).

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

**리팩토링 착수부터 FIX r1 최종까지 이력 실측 (`state/runtime/runtime_state.sqlite`)**:

⚠️ 아래 표의 hash 는 **각 시점 개별 이력 기록**이며 서로 다른 실행 세션의 값이다. FIX r1 최종 baseline 은 §0 · 아래 표 마지막 두 행 (`f72dd796...`) 이 유일하다.

| # | 시점 | exists | size | sha256 | mtime |
|---|---|---|---|---|---|
| 1 | Refactor 착수 시 (Cutover v1 마지막 실행 뒤) | True | 69632 | `5d09a0068bf659720aa1cc1c81a8f5f8ecc02422345b0f5cb880ec1421442861` | 1783605724.35 |
| 2 | Refactor v1 첫 conftest fixture 도입 직후 (초기 검증) | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |
| 3 | Refactor v1 commit `93539635` 시점 823 passed 후 (사용자 실행 verify 상 오염 발견) | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |
| 4 | **FIX r1 착수 시 오염 실측** (`activated_by=isolation_test`, semantic_match=false) | True | 69632 | `8ae7f1185309730203f8cea25ce249a312ee05162138bedb2e44af0337d78a57` | 1783843636.58 |
| 5 | FIX r1 DB 삭제 + latest JSON 복구 (`param-20260708T141218-914114`) + clean seed 직후 (1차) | True | 53248 | `324393d6c77b3f6be75769eb5890db028e5c2a94e14eae2698512465109df79c` | 1783846545.30 |
| 6 | FIX r1 legacy JSON path 확장 발견 후 latest JSON 재복구 + DB 재삭제 + clean seed (2차, **FIX r1 최종 baseline**) | True | 53248 | **`f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e`** | **1783846900.8138113** |
| 7 | **FIX r1 최종 backend 827 passed 회귀 실행 후** (pytest 전·후 대조 결과 6행과 완전 동일 → 불변 확인) | True | 53248 | **`f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e`** | **1783846900.8138113** |

**해석 (이력별)**:
- **1 → 2 hash 변화 (`5d09a006... → 8ae7f118...`)**: Refactor v1 착수 초기 (conftest fixture 활성화 이전) `_create_approved_manual_seed_param` 흐름이 실제 PC DB 를 1회 오염시킨 증거. **B-6 재현**.
- **2 → 3 hash 동일**: conftest fixture (Refactor v1 초안) 이후 backend regression 이 DB 는 건드리지 않음 확인 — 그러나 **당시에는 latest_runtime_param.json 도 별도로 오염되고 있었음이 FIX r1 착수 시 밝혀짐**.
- **4 상태**: 사용자 실행 verify 결과 `activated_by=isolation_test` + `semantic_match_with_latest_json=false` 발견 → 설계자 REJECTED / FIX r1 지시.
- **5**: DB 삭제 + latest JSON 을 `param-20260708T141218-914114` 로 복구 + clean seed. 이 시점 verify overall=READY, activated_by=`cutover_seed`, semantic_match=true. 그러나 첫 pytest 회귀 실행 결과 실제 latest JSON 이 다시 회귀 test 로 오염되는 것을 발견 (`_create_approved_manual_seed_param` 이 `write_param_file(_CREATE_LATEST_PATH, ...)` 를 호출) → conftest fixture 확장 결정.
- **6**: conftest fixture 를 legacy JSON path (`_LATEST_PATH`, `_HISTORY_DIR`, `_PARAM_DIR`) 까지 monkeypatch 하도록 확장. 이후 latest JSON 을 다시 복구 후 DB clean seed → 이 실측이 **FIX r1 최종 baseline (기준값)**.
- **7**: FIX r1 최종 backend 827 passed 회귀 실행 완료. pytest 전 (`6`) = pytest 후 (`7`) size · sha256 · mtime **완전 일치** → 실제 DB 완전 불변 확인.

**향후 규칙**: 실제 PC DB 는 사용자가 수동 `python -m scripts.run_runtime_state_db_cutover seed` 로만 갱신. test 는 conftest fixture 로 tmp DB + tmp legacy JSON path 만 사용.

## 8. 테스트 결과 (AC-13)

- 신규 `tests/test_runtime_state_db_cutover.py` (FIX r1 최종): **16 케이스** = 기존 12 + FIX r1 verify CLI 판정 강화 회귀 4 (`test_verify_cli_flags_test_marker_isolation_test`, `test_verify_cli_flags_test_marker_bare_test`, `test_verify_cli_flags_semantic_mismatch`, `test_verify_cli_clean_seed_passes`).
- 신규 `tests/test_runtime_state_isolation.py`: 2 케이스 (isolation 검증).
- **focused (`test_runtime_state_db_cutover.py`) 재실행 결과: 16 passed**.
- **FIX r1 최종 backend full regression: 827 passed** (Refactor v1 823 → FIX r1 827, verify 강화 4 순증). 0 fail. 실행 202s.
- **실제 PC DB / latest JSON 은 827 test 실행 전·후 완전 불변** (§7 6행/7행 baseline `f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e` / `84151b5659abba0a8622af3e418856e5512e3f290c6fd50a0697b0609af422aa` 그대로).
- **B-6 검증자 지적 (verify 판정 강화 자동 회귀 test 부재) 해소**: 위 4 신규 케이스가 marker 오염 · semantic mismatch · clean seed 각 경로를 자동 재현 · assert.
- **실제 `runtime_state.sqlite` 불변 확인 (FIX r1 최종)**: pytest 전 `f72dd796b20441c8d89ab59815c546cbdf74cac318f27eabede011750d1b386e` (size=53248, mtime=1783846900.8138113), pytest 후 동일. **conftest fixture 가 827 test 실행 중 실제 PC DB 를 단 1 byte 도 건드리지 않음** = AC-11 · AC-12 완전 통과.
- **실제 `latest_runtime_param.json` 불변 확인 (FIX r1 확장)**: pytest 전 `84151b5659abba0a8622af3e418856e5512e3f290c6fd50a0697b0609af422aa` (size=884, mtime=1783846900.6387017), pytest 후 동일.
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
