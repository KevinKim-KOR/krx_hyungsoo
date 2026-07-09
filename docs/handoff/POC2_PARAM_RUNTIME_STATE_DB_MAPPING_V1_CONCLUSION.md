# PARAM / Runtime State DB Mapping v1 — Conclusion (DONE)

작성일: 2026-07-09
성격: DB 매핑 계약 확정 Step. **구현 Step 아님**. code_contract + OCI observed structure 병행 확인.

## 1. Step 목표와 범위

**목표**: active PARAM, runtime latest status, sent registry 의 DB 전환 기준을 확정한다 (다음 `PARAM / Runtime State DB Cutover v1` 의 입력).

**범위**:
- 코드 grep 으로 각 JSON 의 reader/writer/schema 계약 정리.
- PC 로컬 존재 JSON read-only 실측.
- OCI 존재 JSON 은 사용자 sanitised 구조 샘플로 실측 (Q1 (b) · 지시문 §6 준수).
- `market_data.sqlite` / `runtime_state.sqlite` / `decision_evidence.sqlite` 역할 경계.
- table / column 매핑표 (설계 후보만; 실제 DB 생성 X).

**범위 밖**:
- DB 파일 · table · row · migration · runtime 코드 · UI · scheduler · Telegram · `available_sources=None` 수정.
- PC↔OCI publication 절차 확정.
- decision_evidence 역할 확정.

## 2. 현재 JSON 별 reader / writer / active 여부

| 파일 | Reader | Writer | Active input 여부 |
|---|---|---|---|
| `state/three_push/params/latest_runtime_param.json` | `app.three_push_runtime_param.read_param_file` / `scripts.run_three_push_runtime_oci` (`_PARAM_PATH`) / `app.api_three_push_param` / `scripts.verify_three_push_param_oci` / `scripts.sync_three_push_runtime_param` | `app.three_push_runtime_param.write_param_file` (atomic `.tmp → rename`) / `scripts.create_three_push_runtime_param` / `app.api_three_push_param` (PARAM 승인 API) | ✅ **active** — 파일명 자체가 active pointer. |
| `state/three_push/params/history/param-*.json` | 없음 (grep 상 reader 부재) | `write_param_file(history_path, param)` — `scripts.create_three_push_runtime_param:100` + `app.api_three_push_param:226` (매 승인마다) | ❌ **archive** — active 판단에 미사용. |
| `state/three_push/oci_runtime_status_latest.json` | 없음 (운영자 조회용, 코드에서 재소비 X) | `app.three_push_runner_common.write_status` (atomic `.tmp → replace`, 매 실행 덮어쓰기) | ✅ **active latest** — 최신 실행 record 1개. |
| `state/three_push/oci_runtime_sent_registry.json` | `app.three_push_runner_common.load_registry` / `is_already_sent` (`scripts.run_three_push_runtime_oci:225`) | `save_registry` / `mark_sent` (`run_three_push_runtime_oci:240` — send 성공 시에만) | ✅ **active** — duplicate guard. |
| `state/three_push/oci_runtime_history.jsonl` | 없음 (grep 상 reader 부재) | `write_status` 내부에서 append (`three_push_runner_common:305-307`) | ❌ **archive/log** — latest status / sent registry 재구성에 미사용. |

## 3. `latest_runtime_param.json` 필드 목록과 타입

**Schema class**: `RuntimeParam` (`app/three_push_runtime_param.py:95`). **SCHEMA_VERSION**: `"three_push_runtime_param.v1"`.

**필수 top-level 10 + extra 허용** (`schema_version` 은 `SCHEMA_VERSION` 상수 비교로 별도 검증, 필수 필드 9 는 `validate_param_dict` @ `three_push_runtime_param.py:223-233` 명시 — 합계 10):

| key | type | 필수 | 허용값 / 설명 |
|---|---|---|---|
| `schema_version` | str | ✅ | `"three_push_runtime_param.v1"` 고정 |
| `param_id` | str | ✅ | `param-YYYYMMDDTHHMMSS-microsecond` 포맷 |
| `created_at` | str (ISO8601 UTC) | ✅ | 생성 시각 |
| `approved_at` | str (ISO8601 UTC) | ✅ | 승인 시각 |
| `approved_by` | str | ✅ | 승인 주체 (예: `"user"`) |
| `param_source` | str | ✅ | `manual_seed` / `baseline_static` / `future_ml_placeholder` / `ml_export` |
| `enabled_push_kinds` | list[str] | ✅ | `market_briefing` / `holdings_briefing` / `spike_or_falling_alert` 부분집합 |
| `runtime_policy` | dict | ✅ | `data_unavailable_behavior`(str), `allow_partial_message`(bool) |
| `evidence_policy` | dict | ✅ | `use_runtime_timestamp`(bool), `include_data_availability`(bool), `do_not_infer_missing_sources`(bool) |
| `safety_policy` | dict | ✅ | `block_buy_sell_wording`, `block_cash_allocation_instruction`, `block_regime_confirmation`, `block_risk_threshold_confirmation`, `block_secret_exposure` (모두 bool) |
| `param_description` | str | 선택 (extra) | validator 는 extra dict 로 보존 (초기 1건에만 존재, PC 실측) |
| `source_note` | str | 선택 (extra) | 상동 |

**금지 top-level keys** (`FORBIDDEN_PARAM_TOP_LEVEL_KEYS`, 재귀 검사 · 대소문자 무관): `message_text`, `telegram_text`, `buy_candidates`, `sell_candidates`, `cash_allocation`, `regime_confirmation`, `risk_threshold_confirmation`, `etf_ranking`, `token`, `chat_id`, `bot_token`, `telegram_token`, `telegram_chat_id`.

**Runtime 실제 소비 필드** (`run_three_push_runtime_oci` 기준): `param_id`, `param_source`, `enabled_push_kinds`. `runtime_policy` / `evidence_policy` / `safety_policy` 는 검증만 통과 (현 실행 경로에서 값 소비 X, 향후 확장 여지).

**UI/apply 사용 필드**: `app/api_three_push_param.py` = PARAM 승인 UI/API (`param_id`, `approved_at`, `approved_by`, `param_source`, `enabled_push_kinds` 노출).

**active 판단 근거**: **파일 이름 `latest_runtime_param.json` 자체가 pointer**. 파일 안에 `active` / `approval_status` / `activated_at` 필드 **없음**.

## 4. PARAM history 구조와 latest 차이

**PC 실측**: `state/three_push/params/history/param-*.json` **95건**.

**구조**:
- 모두 `schema_version="three_push_runtime_param.v1"` uniform.
- 모두 `param_source="manual_seed"` uniform (PC 로컬 기준; 향후 다른 source 진입 여지).
- Top-level key 패턴 2종:
  - (a) 초기 1건 (`param-20260618T142511-622384.json`): `param_description` + `source_note` 포함.
  - (b) 나머지 94건: 필수 10 필드만.
- **`approval_status` / `activated_at` / `active` 필드 부재** (모든 파일 검사, 0건).

**Writer 경로**:
- `scripts/create_three_push_runtime_param.py:100` — `write_param_file(history_path, param)` (신규 승인마다 append).
- `app/api_three_push_param.py:226` — API 통한 PARAM 승인 시 동일.

**Reader**: 없음 (grep 상 부재).

**판정**: PARAM history 는 **archive**. **latest 와 동일 구조**. **active 판단에 미사용**. history 를 훑어 최신 activation 을 결정하지 않고, `latest_runtime_param.json` 자체 파일이 pointer.

## 5. `oci_runtime_status_latest.json` 필드 목록과 운영 의미

**Type**: dict (single latest execution record).
**Writer**: `app.three_push_runner_common.write_status` — atomic `.tmp → replace` (매 실행 마지막 record 덮어쓰기).
**OCI 실측 (2026-07-09, size=629 bytes)**: 코드 계약과 top-key 세트 완전 일치 (16 keys).

| key | type | 운영 의미 |
|---|---|---|
| `push_kind` | str | market_briefing / holdings_briefing / spike_or_falling_alert |
| `mode` | str | dry-run / send |
| `status` | str | failed / skipped / sent / dry_run_success |
| `reason` | str/null | push_kind_disabled / push_kind_not_in_param / autosend_disabled / duplicate_runtime / registry_corrupted / missing_latest_param / param_load_error / param_secret_exposed / forbidden_wording / raw_identifier_exposed / runtime_message_build_error / telegram_send_error 등 |
| `started_at` | str (ISO8601 UTC) | 실행 시작 |
| `finished_at` | str (ISO8601 UTC) | 실행 종료 |
| `runtime_kst` | str (ISO8601 KST) | runtime 기준 시각 |
| `runtime_date_kst` | str (YYYY-MM-DD) | duplicate guard 날짜 축 |
| `param_id` | str | 로드된 PARAM |
| `param_source` | str | 로드된 PARAM 의 source |
| `message_text_length` | int | 생성된 메시지 길이 |
| `availability` | dict `{available: int, unavailable_or_other: int}` | data source readiness 요약 (`availability_summary` @ `three_push_runtime_message_builder:195`) |
| `duplicate_key` | str | `"{push_kind}::{param_id}::{runtime_date_kst}"` |
| `telegram_attempted` | bool | 발송 시도 여부 |
| `telegram_sent` | bool | 발송 성공 여부 |
| `error` | str/null | 에러 메시지 (400자 truncate) |

**data_insufficient / source_readiness / Telegram 결과**: `availability` (source readiness), `reason` (data insufficient / error category), `telegram_attempted` · `telegram_sent` · `error` (Telegram 결과) 로 표현됨.

**운영자가 확인해야 하는 필드**: `push_kind`, `status`, `reason`, `runtime_kst`, `param_id`, `availability`, `telegram_sent`, `error`.

## 6. `oci_runtime_sent_registry.json` 필드와 duplicate guard 의미

**Type**: dict (key → entry).
**OCI 실측 (2026-07-09, size=11834 bytes)**: 47 entries. key part count = 3 (코드 계약 `push_kind::param_id::runtime_date_kst` 일치). Entry keys 4 → 코드 계약 일치.

**Registry key**: `"{push_kind}::{param_id}::{runtime_date_kst}"` (`run_three_push_runtime_oci.py:80-81`).

**Registry entry (dict)**:

| key | type | 의미 |
|---|---|---|
| `push_kind` | str | |
| `param_id` | str | |
| `runtime_date_kst` | str (YYYY-MM-DD) | |
| `sent_at_utc` | str (ISO8601 UTC) | 실제 발송 성공 시각 |

**Duplicate guard 기준** (`is_already_sent` @ `three_push_runner_common:283`): key 존재 여부로만 판단.

- **날짜 기준**: `runtime_date_kst` (KST 기준 YYYY-MM-DD).
- **push 종류 기준**: `push_kind`.
- **PARAM 기준**: `param_id` (같은 날 다른 PARAM 이면 별도 key = 재발송 허용).
- **message hash/fingerprint**: **부재** (registry key = fingerprint 대체).
- **send_status 필드**: **부재** (registry 존재 = 발송 성공 확정, 실패 시 `mark_sent` 호출 X @ `run_three_push_runtime_oci:238`).
- **TTL/보존**: **부재** (매 발송 시 전체 dict 재기록, 삭제 로직 없음).
- **재발송 허용 조건**: 다른 `param_id` 또는 다른 `runtime_date_kst` 로 전이.

## 7. `oci_runtime_history.jsonl` active 판정

**Type**: JSONL append log.
**Writer**: `write_status` 내부에서 status record 를 그대로 append (`three_push_runner_common:305-307`).
**Reader**: **없음** (grep 상 부재).

**OCI 실측 (2026-07-09, size=33590 bytes, 59 lines)**:
- FIRST_LINE_KEYS = LAST_LINE_KEYS = status latest 16 keys 완전 동일.
- KEY_SET_DIFF (first XOR last) = (same).
- FIRST `status=dry_run_success` / LAST `status=sent` — 정상 운영 이력.

**판정**: **log / archive**. latest status 재구성 · sent registry 판단에 사용 X. **이번 DB 전환 대상에서 제외**. history 전체 DB 화 는 §12.1 BACKLOG 후보로 보류.

## 8. DB 파일 역할 경계

### 8.1 `state/market/market_data.sqlite`

**역할** (지시문 §8.1 확정):
- 시장 가격 (`market_benchmark_daily_price`)
- benchmark (`market_refresh_state`, `market_refresh_log`)
- ETF NAV (`etf_nav_daily`)
- ETF constituents (`etf_constituents`, `etf_constituent_refresh_log`)
- ETF master (`etf_master`)
- ETF daily price (`etf_daily_price`)
- ML feature input (`etf_ml_feature_daily`, `market_risk_feature_daily`)
- timeseries ingestion / refresh state (`market_timeseries_*`)

**PARAM / runtime status / sent registry 미포함**. 다음 Cutover Step 에서 절대 섞지 않음.

### 8.2 `state/runtime/runtime_state.sqlite` (다음 Cutover Step 신규 예정)

**역할**:
- active PARAM
- PARAM version / history
- PARAM approval / activation 상태
- runtime latest execution status
- sent registry / duplicate guard

**이번 Step 에서 생성하지 않음.** 파일 존재 확인 · 스키마 정의 · row insert 모두 다음 Step.

### 8.3 `state/decision/decision_evidence.sqlite`

**역할**: 이번 Step 에서 runtime_state 로 재사용하지 않음 (지시문 §8.3 확정). Preflight `fd7ff116` 상 OPTIONAL_MISSING (PC 만 존재, OCI 부재). 판단 evidence 저장소로서 별도 STEP 에서 검토.

## 9. table 후보와 각 table 의 책임

DB 파일 및 실제 table 은 **다음 Cutover Step에서 생성**. 이번 Step 은 후보 계약만.

### 9.1 `runtime_param_version`
PARAM version 별 메타정보.

### 9.2 `runtime_param_value`
PARAM version 별 개별 설정값 (JSON blob 저장 대신 정규화된 key-value).

### 9.3 `runtime_param_active`
현재 active PARAM pointer (파일명 pointer 를 DB row 로 승격).

### 9.4 `runtime_execution_status`
runtime latest execution status (latest 는 `run_id` = 최신 record 1개, history 는 별도 다음 Step 논의).

### 9.5 `runtime_sent_registry`
Telegram 중복 발송 방지 상태. duplicate guard = (`push_kind`, `param_id`, `runtime_date_kst`) 튜플 유일성.

## 10. JSON field → DB table / column 매핑표

**중요**: 실제 column 타입 · NOT NULL · UNIQUE 는 다음 Cutover Step 에서 확정. 여기는 매핑 계약만.

### 10.1 `latest_runtime_param.json` → `runtime_param_version` + `runtime_param_value` + `runtime_param_active`

| JSON field | 목적지 table.column | 참고 |
|---|---|---|
| `schema_version` | `runtime_param_version.schema_version` | 고정값 검증 필드 |
| `param_id` | `runtime_param_version.param_id` (PK) | 파일 시스템 param_id 유지 |
| `created_at` | `runtime_param_version.created_at` | ISO8601 |
| `approved_at` | `runtime_param_version.approved_at` | ISO8601 |
| `approved_by` | `runtime_param_version.approved_by` | 승인 주체 |
| `param_source` | `runtime_param_version.param_source` | 허용값 4종 enum |
| `param_description` (extra) | `runtime_param_version.description` | nullable |
| `source_note` (extra) | `runtime_param_version.source_note` | nullable |
| `enabled_push_kinds[i]` | `runtime_param_value` row-per-item (`param_key='enabled_push_kinds'`, `text_value=<kind>`) | list flatten |
| `runtime_policy.data_unavailable_behavior` | `runtime_param_value` (`param_key`, `text_value`) | |
| `runtime_policy.allow_partial_message` | `runtime_param_value` (`param_key`, `boolean_value`) | |
| `evidence_policy.*` (3필드) | `runtime_param_value` (각 필드 별 row, `boolean_value`) | |
| `safety_policy.*` (5필드) | `runtime_param_value` (각 필드 별 row, `boolean_value`) | |

**active pointer**: `runtime_param_active` 1 row = `(active_scope='three_push', active_param_version_id=<param_id>, activated_at=<UTC>, activated_by='user')`.

**§9.1 준수**: active PARAM 을 JSON blob 하나로 저장 X. `runtime_param_value` 는 정규화. Raw snapshot 이 필요하면 별도 archive 목적 컬럼/테이블 (미확정, BACKLOG 후보).

### 10.2 `oci_runtime_status_latest.json` → `runtime_execution_status`

| JSON field | column | 참고 |
|---|---|---|
| `push_kind` | `push_kind` | enum 3종 |
| `mode` | `mode` | dry-run / send |
| `status` | `status` | failed/skipped/sent/dry_run_success |
| `reason` | `reason` | nullable |
| `started_at` | `started_at` | ISO8601 UTC |
| `finished_at` | `finished_at` | ISO8601 UTC |
| `runtime_kst` | `runtime_kst` | ISO8601 KST |
| `runtime_date_kst` | `runtime_date_kst` | YYYY-MM-DD |
| `param_id` | `param_id` | FK → `runtime_param_version.param_id` |
| `param_source` | `param_source` | 로드된 PARAM source |
| `message_text_length` | `message_text_length` | int |
| `availability.available` | `availability_available` | int |
| `availability.unavailable_or_other` | `availability_unavailable_or_other` | int |
| `duplicate_key` | `duplicate_key` | str |
| `telegram_attempted` | `telegram_attempted` | bool |
| `telegram_sent` | `telegram_sent` | bool |
| `error` | `error` | nullable, 400자 truncate 유지 |

**Latest 선정 원칙**: `run_id` 신설 (auto-increment) — 매 실행 append. Latest = `MAX(run_id)` 또는 별도 `latest_pointer` 테이블.
- **선택**: `run_id` append + latest view (`ORDER BY started_at DESC LIMIT 1`). 별도 latest 테이블 불필요 (index 로 충분).

### 10.3 `oci_runtime_sent_registry.json` → `runtime_sent_registry`

| JSON entry field | column | 참고 |
|---|---|---|
| entry key (`push_kind::param_id::runtime_date_kst`) | `registry_key` (unique) | 원본 key 문자열 보존 |
| `push_kind` | `push_kind` | |
| `param_id` | `param_id` | FK → `runtime_param_version.param_id` |
| `runtime_date_kst` | `runtime_date_kst` | YYYY-MM-DD |
| `sent_at_utc` | `sent_at_utc` | ISO8601 UTC |

**Duplicate guard 계약** (§9.4):
- UNIQUE (`push_kind`, `param_id`, `runtime_date_kst`) 또는 UNIQUE (`registry_key`) — 다음 Step 에서 확정.
- `send_status` 필드 신설 여부: **부재 유지** (JSON 계약과 동일). registry row 존재 = 발송 성공.
- `message_hash` 필드 신설 여부: **부재 유지** (JSON 계약과 동일). 필요 시 별도 STEP.
- TTL: **부재 유지** (JSON 계약과 동일). 정리 정책은 별도 STEP.

## 11. 다음 Cutover Step 에서 구현할 항목

1. `state/runtime/runtime_state.sqlite` 파일 생성.
2. table 5개 DDL 확정 (§9.1 ~ §9.5).
3. `runtime_param_version` / `runtime_param_value` / `runtime_param_active` 정규화된 write path.
4. `run_three_push_runtime_oci` writer 경로 전환:
   - `_STATUS_PATH` → DB insert (`runtime_execution_status`).
   - `_REGISTRY_PATH` → DB upsert (`runtime_sent_registry`).
   - `_HISTORY_PATH` → JSONL 유지 (archive, DB화 미포함 — §12.1 BACKLOG).
5. `read_param_file` reader 경로 전환 (latest active row 조회).
6. 기존 JSON → DB migration (1회 seed).
7. Cutover 후 JSON 파일 처리 정책 (backup / read-only shadow / 제거) — 별도 결정.
8. duplicate guard 동시 실행 안전성 (SQLite UNIQUE 제약 + 예외 처리).
9. API (`app/api_three_push_param.py`) reader/writer 전환.
10. 테스트: DB read/write 회귀, migration 검증, duplicate guard 재현.

## 12. BACKLOG 후보

### 12.1 runtime history 전체 DB 화
- **항목**: `oci_runtime_history.jsonl` 을 `runtime_execution_history` table 로 이전.
- **보류 사유**: latest status DB 화 만으로 운영 화면 요구 충족. history 는 현재 어떤 코드도 read 하지 않음.
- **보류된 위험**: Telegram 장애 분석 / 운영 리포트 / AI Sessions 이력 연결 시 JSONL 파싱 필요.
- **재검토 트리거**: history 분석 요구 발생, 운영 리포트 대시보드 도입.

### 12.2 PC↔OCI publication 표준화
- **항목**: 승인된 PARAM 을 PC 에서 OCI 로 반영하는 절차 계약.
- **보류 사유**: 이번 Step 은 DB 매핑 확정.
- **보류된 위험**: 시장 DB · runtime DB 장기 동기화 정책 분리 상태.
- **재검토 트리거**: PARAM DB Cutover 후 첫 신규 PARAM 승인 필요 시.

### 12.3 mobile read model
- **항목**: 모바일이 조회할 DB table 및 view 정의.
- **보류 사유**: Telegram contentful PUSH 완료 전.
- **보류된 위험**: 이후 view/table 재정리 필요 가능.
- **재검토 트리거**: OCI runtime state DB · decision evidence DB 역할 안정화.

### 12.4 message_hash / send_status / TTL 정책
- **항목**: sent registry 에 fingerprint / status / 만료 시각 도입.
- **보류 사유**: 현 JSON 계약에 부재. 도입 시 duplicate guard 기준 변경 발생.
- **보류된 위험**: 동일 PARAM · 동일 날짜 재발송 시나리오 (예: 재시도) 미대응.
- **재검토 트리거**: 재발송 요구 명확화.

### 12.5 raw PARAM JSON archive
- **항목**: `runtime_param_version` 에 원본 JSON blob 컬럼 도입 여부.
- **보류 사유**: §9.1 (JSON blob 금지) 상 정규화 후보만 채택. archive 목적 원본 보존 필요 시 별도 컬럼/테이블 신설.
- **보류된 위험**: 정규화 손실 시 원본 재현 불가.
- **재검토 트리거**: 정규화 미커버 필드 발견, 감사 요구.

## 13. 금지 항목 변경 0건 확인

지시문 §6 금지 항목 실측 검증:

- SQLite DB 파일 생성: 0건.
- SQLite table 생성: 0건.
- SQLite row insert/update/delete: 0건.
- JSON → DB migration: 0건.
- active PARAM 전환: 0건 (`latest_runtime_param.json` 미변경).
- runtime 이 DB 를 읽도록 수정: 0건.
- sent registry 를 DB 로 쓰도록 수정: 0건.
- `available_sources=None` 수정: 0건.
- Telegram dry-run · 실제 발송: 0건.
- API / UI / scheduler 변경: 0건.
- `market_data.sqlite` schema 변경: 0건.
- `decision_evidence.sqlite` 생성 · 복사 · 역할 확정: 0건.
- PC↔OCI publication 방식 확정: 0건 (§12.2 BACKLOG).
- OCI→PC analysis replica 방식 확정: 0건.
- 새 CLI / script / test 생성: 0건.
- 외부 API 호출: 0건.
- OCI SSH 접속 자동화: 0건 (Q1 (b) 유지).

**변경 파일 목록**:
- 신규: `docs/handoff/POC2_PARAM_RUNTIME_STATE_DB_MAPPING_V1_CONCLUSION.md` (본 문서).
- 수정: `docs/STATE_LATEST.md`, `docs/handoff/POC2_B_NEXT_ACTIONS.md`.

## 14. code_contract vs OCI observed structure 일치 확인

| 파일 | code_contract | OCI observed (2026-07-09) | 일치 |
|---|---|---|---|
| `oci_runtime_status_latest.json` | dict, 16 keys (`run_three_push_runtime_oci.py:93-110`) | dict, 16 keys 완전 동일 세트 | ✅ |
| `oci_runtime_status_latest.json` `availability` | `{available: int, unavailable_or_other: int}` (`availability_summary` @ `three_push_runtime_message_builder:195`) | nested_keys=`['available','unavailable_or_other']` | ✅ |
| `oci_runtime_sent_registry.json` | dict, key=`push_kind::param_id::runtime_date_kst`, entry 4 keys (`run_three_push_runtime_oci.py:80-81, 240-249`) | dict, 47 entries, key part=3, entry keys=`['param_id','push_kind','runtime_date_kst','sent_at_utc']` | ✅ |
| `oci_runtime_history.jsonl` | append log of status record (`three_push_runner_common:305-307`) | 59 lines, first=last key set = status 16 keys | ✅ |

**mismatch 없음**. 이번 매핑표는 code_contract 와 OCI observed 양쪽 모두 근거로 확정.
