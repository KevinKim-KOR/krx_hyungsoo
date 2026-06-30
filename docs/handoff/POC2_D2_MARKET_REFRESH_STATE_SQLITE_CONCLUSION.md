# D-2 시장 갱신 상태 SQLite 영속화 — Conclusion

작성일: 2026-06-30
측정 방식: `wc -l` (Bash) 통일.

이 문서는 D-2 결함 (`app/market_refresh_service.py` in-memory state 재시작 시 소실, 6h cooldown 가드 깨짐) 해소 STEP 의 종료 기록이다.

---

## 1. SSOT 전환

- **SSOT**: 기존 시장 SQLite (`state/market/market_data.sqlite`) 의 신규 단일 상태 테이블 `market_refresh_state`.
- **단일 행 원칙**: `refresh_scope='market_data'` 한 행만 유지. 별도 DB / cache / history / JSON 보조 SSOT 신설 0건.
- **in-memory**: SQLite 와 동기화된 보조 캐시. 첫 `get_state_snapshot` / `start_refresh_job` 호출 시 SQLite hydrate.
- **JSON / 파일**: 시장 갱신 상태의 기준 저장소가 아니다. `NAV_REFRESH_SUMMARY_PATH` 등 기존 artifact 는 export 용도로만 유지.

---

## 2. SQLite 스키마

`app/market_data_store.py` 의 `MARKET_REFRESH_STATE_DDL` 로 정의. `init_db` 가 CREATE TABLE IF NOT EXISTS 로 생성.

| 컬럼 | 타입 | 역할 |
|---|---|---|
| `refresh_scope` | TEXT PRIMARY KEY | 고정값 `market_data` |
| `refresh_id` | TEXT | 마지막 시도 id |
| `last_success_asof_date` | TEXT | 마지막 정상 갱신 시장 기준일 |
| `last_success_at` | TEXT | 마지막 정상 갱신 완료 시각 |
| `last_attempt_started_at` | TEXT | 마지막 시도 시작 시각 |
| `last_attempt_finished_at` | TEXT | 마지막 시도 종료 시각 |
| `last_attempt_status` | TEXT | `running` / `ok`(=completed) / `failed` / `idle` |
| `last_error_summary` | TEXT | 짧은 내부 원인 (raw traceback / secret / 응답 전문 저장 X) |
| `asof` | TEXT | 마지막 시도 asof |
| `universe_count` | INTEGER | detail |
| `price_attempted_count` | INTEGER | detail |
| `price_success_count` | INTEGER | detail |
| `price_fail_count` | INTEGER | detail |
| `runtime_seconds` | REAL | detail |
| `updated_at` | TEXT NOT NULL | 행 최종 갱신 시각 |

`RefreshState` 가 노출하는 12 필드 전체를 SQLite 에서 복원 가능.

---

## 3. 상태 기록 규칙

### 3.1 갱신 시작 (`start_refresh_job` lock-block 내)

- `last_attempt_status = running`
- `last_attempt_started_at = 현재 시각`
- `last_attempt_finished_at = null`
- `last_error_summary = null`
- `last_success_*` 는 SQLite prior row 에서 읽어 보존 (`_persist_current_state` 가 자동 처리).

### 3.2 갱신 성공 (`_execute_refresh_job` 종료 시 `success_overall=True`)

- `last_attempt_status = completed`
- `last_attempt_finished_at = 현재 시각`
- `last_success_asof_date = end_date_for_prices`
- `last_success_at = 현재 시각`
- `last_error_summary = null`
- detail 필드 (universe_count / price_* / runtime_seconds / asof) 갱신.

### 3.3 갱신 실패 (`_execute_refresh_job` 종료 시 `success_overall=False`)

- `last_attempt_status = failed`
- `last_attempt_finished_at = 현재 시각`
- `last_error_summary = 짧은 내부 원인`
- detail 필드는 마지막 시도 결과로 갱신.
- `last_success_asof_date / last_success_at` 은 유지 (보존 규칙은 §3.5 참조).

### 3.4 재시작 중단 정규화 (`normalize_running_to_failed`)

`get_state_snapshot` 또는 `start_refresh_job` 첫 호출 시 `_ensure_loaded` 가 `normalize_running_to_failed` 를 호출.

- SQLite 에 남아 있는 `running` 상태 → `failed` 로 정규화.
- `last_attempt_finished_at` 을 정규화 시각으로 채움.
- `last_error_summary = "interrupted_before_finish"`.
- detail 필드 (universe_count / price_* / runtime_seconds / asof) 는 그대로 보존 — null 또는 임의값으로 초기화 X.
- `last_success_*` 유지.

### 3.5 마지막 성공 보존 메커니즘

`_persist_current_state` 가 SQLite write 직전 prior row 를 read 하여 `last_success_*` 가 in-memory mirror 에 비어 있으면 prior row 의 값을 채움. 실패·중단·running 진입이 마지막 정상 성공 기록을 덮어쓰지 않는다.

---

## 4. 읽기 규칙

- `get_state_snapshot(cooldown_hours, db_path)` 첫 호출 시 `_ensure_loaded` 가 SQLite hydrate + running 정규화.
- in-memory `_service.state` 는 SQLite 와 동기화된 미러. 동일 db_path 에 대해 1회 hydrate 후 캐시 사용.
- 새 서비스 인스턴스 (`_service = _ServiceState()`) 가 만들어지면 다음 호출에서 다시 hydrate.
- 상태 행이 없는 최초 상태에서는 과거 성공 기록 추정 0건 — `status=idle`, 모든 detail `null`.

---

## 5. 기존 API·UI 계약

변경 0건.

- endpoint: `POST /market/refresh` / `GET /market/refresh/status` 그대로.
- 응답 모델: `MarketRefreshResponse` / `MarketRefreshStatusResponse` 필드·의미 변경 X.
- status enum: `idle / running / completed / failed / skipped_cooldown` 유지.
- 화면 / 신규 카드 / 버튼 / raw error 노출 / CUDA·ML 변경 없음.

---

## 6. 자동 테스트 결과

신규 테스트 10건 — `tests/test_market_refresh_state_persistence.py`.

| 케이스 | 검증 |
|---|---|
| `test_initial_state_does_not_infer_success` | AC-6 — 최초 상태에서 과거 성공 추정 X |
| `test_success_persisted_to_sqlite` | AC-2 — 성공 후 SQLite 영속화 |
| `test_new_instance_recovers_full_state` | AC-3 — 새 인스턴스 detail 전체 복구 |
| `test_failure_preserves_last_success` | AC-4 — 실패가 last_success_* 보존 |
| `test_restart_running_normalized_to_failed_preserving_detail` | AC-5 — running 정규화 + detail 보존 |
| `test_status_response_fields_unchanged` | 응답 필드 회귀 |
| `test_new_instance_detail_fields_all_recovered` | detail 전체 복구 보강 |
| `test_failure_after_success_keeps_last_success_in_new_instance` | 성공 후 실패 후 새 인스턴스에서 last_success 유지 |
| `test_running_state_persisted_during_job` | running 상태 영속화 (정규화 전제) |
| `test_single_row_principle` | 단일 행 원칙 |

**backend 전체 테스트**: `627 passed` (이전 617 → +10). black PASS / flake8 PASS / frontend lint PASS / frontend build PASS.

---

## 7. 변경 파일 목록

- `app/market_data_store.py`: 수정 (`MARKET_REFRESH_STATE_DDL` 추가, `init_db` 에 포함).
- `app/market_refresh_service.py`: 수정 (SSOT 전환, `_ServiceState` 확장, `_persist_current_state` / `_hydrate_from_sqlite` / `_ensure_loaded` 도입, `get_state_snapshot` / `start_refresh_job` / `reset_state_for_testing` 에 db_path).
- `app/api_market_topn.py`: 수정 (`get_state_snapshot` 에 `db_path=DEFAULT_DB_PATH` 명시 전달).
- `app/market_refresh_state_store.py`: 신규 (`MarketRefreshStateRow` / `read_state` / `write_state` / `normalize_running_to_failed` / `clear_state`).
- `tests/test_market_topn_api.py`: 수정 (fixture `reset_state_for_testing(db_path=fake_db)`).
- `tests/test_market_data_store.py`: 수정 (테이블 목록 검증에 `market_refresh_state` 추가, 테스트명 `four_tables_only` 의미로 변경).
- `tests/test_market_refresh_state_persistence.py`: 신규 (10 케이스).
- `docs/STATE_LATEST.md`: 수정.
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`: 수정.
- `docs/handoff/POC2_FEATURE_INVENTORY.md`: 수정 (§2.34 추가).
- `docs/handoff/POC2_D2_MARKET_REFRESH_STATE_SQLITE_CONCLUSION.md`: 신규 (본 파일).

---

## 8. 남은 D-2 관련 부채

없음. D-2 결함은 본 STEP 으로 해소. STATE_LATEST §5 에서 DEFECT → RESOLVED.

추가로 확장이 필요할 가능성이 있는 항목 (현재 STEP 범위 외):

- 갱신 이력 전체 보관 (성공률 / 통계) — 본 STEP 범위 제외. BACKLOG 이관 대상이 아니라 의도적 비범위.
- 다중 서비스 인스턴스 (HA 구성) 의 row-level lock — 현 PoC 단일 인스턴스 가정.
