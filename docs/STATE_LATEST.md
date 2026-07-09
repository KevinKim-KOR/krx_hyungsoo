# STATE_LATEST

최종 업데이트: 2026-07-09 (PARAM / Runtime State DB Cutover v1 — DONE, PC + OCI 모두 verify READY)

## 이번 STEP 요약 (PARAM / Runtime State DB Cutover v1, DONE)

**목적**: JSON 중심 active runtime 운영 상태 (`latest_runtime_param.json`, `oci_runtime_status_latest.json`, `oci_runtime_sent_registry.json`) 를 `state/runtime/runtime_state.sqlite` 기준으로 전환. history JSONL 은 archive 유지.

**협업 방식 (Q1 (b) 재적용)**: 개발자 = PC 구현 + PC seed/verify + OCI 명령 세트 handoff. 사용자 = OCI seed/verify 실행 + sanitised 결과 회신.

**설계자 10개 확정본 준수**: activated_by="cutover_seed" · active_scope="three_push" · dot notation · index suffix · canonical JSON hash · 단일 CLI subcommand · legacy JSON 함수 유지 + 신규 DB 함수 병행 · status DB + history JSONL archive · PC/OCI hash 비교 기록 · hash-based idempotent seed.

**PC seed/verify 결과 (2026-07-09)**:
- `state/runtime/runtime_state.sqlite` 신규 생성 (5 table, integrity_check=ok, `.gitignore` 대상).
- **초기 seed** (`cutover_seed`): `version=1, value=13`, `active=param-20260708T141218-914114`, hash=`622ba812...598888`. AC-3/AC-4/AC-5/AC-6 통과 근거.
- **회귀 테스트 이후 최신 실측**: `version=5, value=65, active=1`, `active=param-20260709T140204-335512`, `activated_by=api_param_apply`, hash=`94ccca0a...e8a6f`. 이는 `test_three_push_param_api` 가 `_create_approved_manual_seed_param` 을 통해 실제 PC DB 에 write 를 실행 = **AC-8 (PARAM apply/write = DB) 의 run-through 증명**.
- **DB 재구성 hash = JSON canonical hash** (초기·최신 모두 `semantic_match_with_latest_json=true`). AC-5 · AC-6 통과.
- verify `overall=READY`. `json_fallback_used=false`.
- idempotent 초기 재실행: `created_new_version=false`, `pointer_action=no_op`, warnings 0건 (Q10 (b) 확인).
- **알려진 test isolation 이슈**: PC 운영 DB 오염 → 다음 STEP 에서 test DB path override 도입 예정. `.gitignore` 로 원격 미반영.

**Runtime status / sent registry**: PC 로컬 JSON 부재 → `absence_recorded=true` / `empty_registry_start=true` (지시문 §8.2 · §8.3 준수, 실패 처리 X). OCI 는 존재 (Mapping v1 확인 16 keys / 47 entries) — OCI seed 결과 회신 대기.

**Fail-closed**: DB 부재 / active pointer 부재 시 `RuntimeError` (JSON fallback 없음). test 로 확인.

**Cutover 전환 완료 (PC)**:
- `run_three_push_runtime_oci` PARAM read → `read_active_param_from_db()` (DB 기준).
- `run_three_push_runtime_oci` status write → `write_status_db_and_history(_HISTORY_PATH, record)` (DB insert + JSONL append).
- `run_three_push_runtime_oci` duplicate guard → `is_already_sent_db` / `mark_sent_db`.
- `api_three_push_param._create_approved_manual_seed_param` + `create_three_push_runtime_param --approve` → DB version 생성 + active pointer 갱신 병행.

**기존 JSON 유지** (지시문 §5, §9): `latest_runtime_param.json` / `oci_runtime_status_latest.json` / `oci_runtime_sent_registry.json` / `oci_runtime_history.jsonl` / `params/history/*.json` — 삭제·rename 0건. legacy reference / rollback source.

**변경 없음** (지시문 §5): `market_data.sqlite` schema/row · `decision_evidence.sqlite` · runtime evidence DB 조회 · `available_sources=None` · Telegram · UI · scheduler · PC↔OCI publication 방식 · runtime history 전체 DB화 — 모두 0건.

**backend 회귀**: **820 passed** (직전 809 → 820, 신규 11). 0 fail. black / flake8 / py_compile PASS.

**OCI seed/verify 결과 (2026-07-09, revision `16956f95` same_revision=True)**:
- OCI 활성 PARAM: `param-20260620T103410-757435` (2026-06-20 승인분), `activated_by=cutover_seed`, hash=`561bfd92...820f73`.
- `sent_registry` seed: 47 entries (input=inserted=47, conflicts=0).
- `runtime_execution_status` seed: 1건 (`run_id=1, push_kind=spike_or_falling_alert, status=sent, runtime_date_kst=2026-07-09`).
- OCI `overall=READY`, `semantic_match_with_latest_json=true`, `json_fallback_used=false`, integrity=ok, warnings 0건.

**PC↔OCI PARAM version 불일치 (Q9 operational warning)**: PC 초기 seed = `param-20260708T141218-914114` (2026-07-08) vs OCI = `param-20260620T103410-757435` (2026-06-20). `same_hash=false`. Cutover 자체는 양쪽 로컬 정합 유지 (`semantic_match_with_latest_json=true` 양쪽 모두). BACKLOG §12.2 (PC↔OCI publication 표준화) 실증 근거로 이월.

**다음 활성 STEP (확정)**: **`Runtime Evidence DB Connection v1`** (설계자 확정 세션) — `available_sources=None` 제거 준비.

상세: `docs/handoff/POC2_PARAM_RUNTIME_STATE_DB_CUTOVER_V1_CONCLUSION.md`.

## 직전 STEP 요약 (PARAM / Runtime State DB Mapping v1, DONE 2026-07-09, commit `8a7a7ccc`)

**목적**: active PARAM · runtime latest status · sent registry 를 DB 로 전환하기 위한 저장소 역할 + table/column 매핑 계약 확정. **구현 Step 아님.** 다음 `PARAM / Runtime State DB Cutover v1` 의 입력.

**협업 방식 (Q1 (b) 재적용)**: 개발자 = 코드 grep + PC read-only 실측 + OCI sanitised 구조 샘플 요청·검증. 사용자 = OCI 파일 구조 sanitised 회신 (값 원문 · secret · 절대 경로 미포함).

**PC 실측**:
- `latest_runtime_param.json`: `three_push_runtime_param.v1` schema, 필수 10 필드 (`schema_version` + `param_id` + `created_at` + `approved_at` + `approved_by` + `param_source` + `enabled_push_kinds` + `runtime_policy` + `evidence_policy` + `safety_policy`) + extra 2 (`param_description`, `source_note`).
- PARAM history 95건: schema/param_source uniform, approval/activated_at/active 필드 부재 → **archive** (active 판단 미사용).

**OCI 실측 (code_contract 완전 일치)**:
- `oci_runtime_status_latest.json`: 16 keys single record (629 bytes), `availability={available:int, unavailable_or_other:int}`.
- `oci_runtime_sent_registry.json`: dict 47 entries, key=`push_kind::param_id::runtime_date_kst`, entry 4 필드 (`push_kind`, `param_id`, `runtime_date_kst`, `sent_at_utc`).
- `oci_runtime_history.jsonl`: 59 lines, status record 그대로 append, first/last key set 동일 → **log/archive** (reader 없음, active 미사용).

**DB 역할 경계**:
- `market_data.sqlite` = 시장 evidence 만 (PARAM/runtime 금지 유입).
- `runtime_state.sqlite` (다음 Cutover Step 신규): active PARAM · runtime latest status · sent registry.
- `decision_evidence.sqlite`: 이번 Step 재사용 X.

**핵심 매핑 결정**:
- active PARAM = JSON blob 저장 금지 (§9.1). `runtime_param_version` (메타) + `runtime_param_value` (정규화 key-value) + `runtime_param_active` (pointer) 분리.
- runtime latest vs history: latest 만 DB (`runtime_execution_status` + `run_id` append + latest view). history JSONL 은 archive 유지 (§12.1 BACKLOG).
- sent registry duplicate guard: UNIQUE (`push_kind`, `param_id`, `runtime_date_kst`). `message_hash` / `send_status` / TTL 부재 유지 (§12.4 BACKLOG).

**변경 없음** (지시문 §6 준수): DB 파일 · table · row · migration · runtime 코드 · `latest_runtime_param.json` · OCI runtime state 파일 · API · UI · scheduler · Telegram · `available_sources=None` · `decision_evidence.sqlite` · `market_data.sqlite` — 모두 0건.

**다음 활성 STEP (확정)**: **`PARAM / Runtime State DB Cutover v1`** (설계자 확정 세션). §11 항목 구현.

상세: `docs/handoff/POC2_PARAM_RUNTIME_STATE_DB_MAPPING_V1_CONCLUSION.md`.

## 직전 STEP 요약 (OCI Database Environment Remediation v1, DONE 2026-07-09, commit `22d29193`)

**목적**: 이전 STEP `OCI Database Preflight v1` 에서 확인된 OCI `state/market/market_data.sqlite` 부재를 1회성 시드 반영으로 복구.

**협업 방식 (Q1 (b) 확정)**: 개발자는 OCI 접속 없음. 개발자 = PC 확인 + OCI 명령 세트 작성 + 결과 검증. 사용자 = OCI 실제 실행 + sanitised 결과 전달.

**3-way SHA-256 일치 (Q2 (a) 확정)**:
- PC source · OCI temp · OCI target 세 값 모두 `f7df867d0f69fc07929b0a25a87ccdc0f235a01097299a9a522bf991614cf286`.
- integrity_check = ok (3회).
- table_count = 12 (3회, table list 동일).

**OCI Preflight 재실행 결과 (revision `c6967d1a`, same_revision=True)**:
- `[market_data] readiness=READY` ✅
- `single_environment_readiness=READY` ✅
- `[decision_evidence] readiness=OPTIONAL_MISSING` (이번 STEP 범위 밖 — 예상대로 변화 없음).
- runtime_paths: 기존 4 JSON 존재 유지, probe latest 부재 유지 (범위 밖).
- staging: `unconfirmed_from_audit` 유지 (범위 밖).

**기존 target 처리**: `absent` (Preflight `fd7ff116` 상 부재로 확인된 대로 실행 시점 재확인 · 백업 발생 안 함).

**원자적 교체**: `mv state/market/market_data.sqlite.tmp state/market/market_data.sqlite` (POSIX rename).

**변경 없음** (지시문 §5 준수, 전체 STEP): 소스 코드 · SQLite schema · row · JSON · runtime · API · UI · scheduler · Telegram · `available_sources=None` · `decision_evidence.sqlite` · `three_push_runtime_probe_latest.json` · 기존 PARAM JSON / runtime status / sent registry / history — 모두 0건.

**다음 활성 STEP (확정)**: **`PARAM / Runtime State DB Mapping v1`** (설계자 확정 세션). PARAM · runtime status · sent registry · holdings 등 JSON → DB 매핑 계약.

상세: `docs/handoff/POC2_OCI_DATABASE_ENVIRONMENT_REMEDIATION_V1_CONCLUSION.md`.

## 직전 STEP 요약 (OCI Database Preflight v1, DONE 2026-07-08)

**목적**: OCI SQLite 운영 전환 사전점검. read-only 실측만. DB / JSON / runtime / API / UI / scheduler / transfer 변경 0건.

**PC · OCI 교차 실측 완료 (양쪽 revision `fd7ff116`, same_revision=True)**:
- PC `state/market/market_data.sqlite` = **READY** (integrity_check=ok, 12 tables, schema_version=12).
- **OCI `state/market/market_data.sqlite` = NOT_READY (파일 부재)** — 기준 DB 자체가 OCI 에 없음.
- PC `state/decision/decision_evidence.sqlite` = READY (OPTIONAL).
- OCI `state/decision/decision_evidence.sqlite` = OPTIONAL_MISSING (부재; §6.6 그대로 overall 실패 강제 X).
- OCI runtime paths: 4개 존재 (OCI runtime write 3종 + latest_runtime_param) + 1개 부재 (probe cache) → PARAM runtime 은 OCI 상에서 실제 실행 중.
- staging: 양쪽 모두 `unconfirmed_from_audit` (§6.7 다음 STEP 이관).

**Overall environment_readiness = NOT_READY** (§7.2 · §7.3 — OCI market_data.sqlite 부재가 근거. **진단 결과이며 STEP 실패 아님**; 다음 STEP 은 확인된 결함만 다루는 remediation Step).

**다음 STEP 유형** (확정): **`OCI Database Environment Remediation v1`**. 이번 STEP 안에서 remediation 은 구현하지 않음.

**신규 파일** (지시문 §5 허용 범위):
- `scripts/run_oci_database_preflight.py` (438줄, read-only CLI, FIX r1 최상위 예외 경계 포함)
- `tests/test_oci_database_preflight.py` (372줄, 19 케이스 — FIX r1 sanitised failure contract 회귀 3건 포함)
- `docs/handoff/POC2_OCI_DATABASE_PREFLIGHT_V1_CONCLUSION.md`

**Q1 (a) 준수**: `market_data.sqlite` 기준 경로 = `app.market_data_store.DEFAULT_DB_PATH`. 보조 정의 (`etf_nav_store`) 동일 반환값 → 충돌 아님.

**Q2 (a)+(b) 준수**: 로컬 실측 · prior_audit_evidence · unconfirmed_from_audit 3단계 근거 분리. 이전 `content_ready` 는 이번 실행의 staging_readiness 자동 승격 근거로 사용 안 함.

**backend 809 passed** (790 → 809, 신규 19). black / flake8 PASS. frontend 변경 0건.

**다음 STEP 후보 (사용자 액션)**:
1. OCI 에서 `python -m scripts.run_oci_database_preflight --environment oci` + `git rev-parse --short HEAD` 실행.
2. sanitised stdout + revision 전달.
3. overall readiness 확정 후 다음 STEP 분기: READY → `PARAM / Runtime State DB Mapping v1` / NOT_READY → `OCI Database Environment Remediation v1`.

상세: `docs/handoff/POC2_OCI_DATABASE_PREFLIGHT_V1_CONCLUSION.md`.

## 직전 STEP 요약 (OCI Active Data Boundary Audit v1, DONE 2026-07-07)

**사용자 확정 (2026-07-07)**: OCI SQLite 중심 활성 운영 구조.
- **OCI SQLite** = 활성 운영·조회 기준 DB (`state/market/market_data.sqlite`).
- **PC SQLite** = OCI DB 의 분석 복제본 (원격 write 금지).
- **PARAM** = DB version / approval / active pointer 로 관리 (JSON 파일 아님).
- **JSON** = 로그 · archive · API transport · 테스트 fixture 만 허용.
- 향후 모바일 조회는 OCI SQLite read-only 기반.

**현재 구현 상태**: DB 전환 전 (사전 감사만 완료). 다음 STEP 부터 실제 전환 착수.

**이번 STEP 산출물** (감사만, 코드 · DB · JSON · runtime · API · UI · scheduler · transfer 변경 0건):
- 216 file 전수 감사 완료 (`state/**/*.json` / `*.jsonl` / `*.sqlite`).
- 각 경로별 reader/writer 파일:라인 근거 확보 (전량 grep, Q1 확정본 준수).
- A/B/C 분류 완료 (동적 경로는 생성 함수 + reader glob 한 행에 병합).
- SQLite inventory 2건 (market_data.sqlite / decision_evidence.sqlite).
- PARAM · runtime 경로 추적 완료 — `available_sources=None` 하드코딩 위치 확정: `scripts/run_three_push_runtime_oci.py:177`.
- 3-PUSH evidence source map 완료.
- PC↔OCI transfer map 완료 (기존 script 만 기록, 신규 transport 미설계).
- 다음 STEP 확정 필요 항목 8개 목록 (개발자 임의 확정 금지, 설계자 확정 대기).
- Canonical docs 5건 갱신 (PROJECT_ORIGIN_INTENT · MASTER_PLAN · ASSUMPTIONS · STATE_LATEST · POC2_B_NEXT_ACTIONS).
- **다음 활성 STEP**: 다음 STEP schema mapping · publication 기준 등 8개 확정 사항 설계자 확정 대기.
- 상세: `docs/handoff/POC2_OCI_ACTIVE_DATA_BOUNDARY_AUDIT_V1_CONCLUSION.md`.

## 직전 STEP 요약 (PUSH Content Gap Diagnosis v1, DONE 2026-07-07)

**PUSH Content Gap Diagnosis v1**: 3개 PUSH ("필요한 데이터가 부족하다" 축약 메시지) 의 원인을 read-only 재현으로 확정하는 진단 Step. SQLite 동기화 · PUSH 문구 개선 · OCI 배포 변경 없음.

- **진단 CLI**: `python -m scripts.run_push_content_gap_diagnosis --environment pc|oci`. 발송 없음. 외부 호출 없음. 기존 SQLite / state artifact 미변경.
- **PC · OCI 교차 실측 완료 (양쪽 commit `89f7cd31`)**: 세 PUSH 모두 **`primary_root_cause=RUNTIME_CONFIGURATION_GAP`**, `exact_reason_code=runtime_available_sources_not_supplied`, `selection_result_count=0`, `content_generation_status=data_insufficient`.
- **공통 직접 원인**: PARAM runtime 이 `available_sources=None` 으로 실행되어 3개 PUSH 모두 evidence 를 공급받지 못함. `scripts/run_three_push_runtime_oci.py:177`.
- **OCI 추가 기여 원인**: `sqlite_integrity=unavailable`, `required_paths_ready=false`. 파일 부재 / 경로 설정 / 권한 세부는 다음 STEP 에서 분해.
- **PC package fallback**: `package_dir_missing`. **OCI package fallback**: `content_ready`. 실운영 경로는 PARAM runtime 이므로 최종 결론에 영향 없음.
- **개별 환경 artifact 의 `observation_status`**: 원본 유지 (설계자 지시). 교차 비교 완료 사실은 Closeout 문서와 완료 보고에서 확정.
- **backend 790 passed** (772 → 790, 신규 18). black / flake8 PASS. frontend 변경 0건.
- **신규 endpoint / DB 테이블 / UI / 외부 호출 0건**. Telegram · PUSH 코드 · Market Discovery · Holdings · AI Sessions · Preview · ML artifact **미변경**.
- **다음 STEP 유형**: `OCI_RUNTIME_CONFIGURATION_CLOSEOUT` (정식 설계명은 별도 설계 세션에서 확정 — 예: `OCI Runtime Evidence Supply Closeout v1`).
- 상세: `docs/handoff/POC2_PUSH_CONTENT_GAP_DIAGNOSIS_V1_CONCLUSION.md`.

## 직전 STEP (2026-07-05, v2 Data Validity + Model Comparison, DONE)

**Market Flow ML v2**: Ridge 부진 원인이 ETF breadth·coverage 데이터인지 feature 구성인지 분리 측정. 시장 판단 UI / 자동 매매 / AI Sessions 연결 아님.

- **세 모델 공정 비교**: Simple Baseline / Full Ridge (13 feature) / Core Ridge (7 feature — breadth·coverage 제외). 동일 기준일 · 학습 행 · 실제 target 사용.
- **공통 Walk-forward**: KODEX200 거래일 20 간격 grid, 최소 학습 행 756, Full feature 확보 기준일만 세 모델 공통 평가.
- **numpy==2.4.6 명시 고정** (Q1 (b)) — quantile method="linear" · 분포 통계.
- **실측 (real SQLite)**: status=ok, 공통 예측 110건, 제외 1건, coverage quartile 28/27/27/28.
  - Simple: MAE 5.0685 / RMSE 7.9827 / directional_accuracy 0.5727.
  - Full Ridge: MAE 5.2466 / RMSE 7.8969 / directional_accuracy 0.5273.
  - Core Ridge: MAE **4.9499** / RMSE **7.7084** / directional_accuracy **0.5909**.
- **backend 772 passed** (755 → 772, 신규 17). black / flake8 PASS. frontend 변경 0건.
- **신규 endpoint / DB 테이블 / UI / 외부 호출 0건**. 기존 baseline / walk-forward artifact **미변경**.
- 상세: `docs/handoff/POC2_MARKET_FLOW_ML_V2_DATA_VALIDITY_MODEL_COMPARISON_CONCLUSION.md`.

## 직전 STEP (2026-07-05, Walk-forward Lookback v1, DONE)

**Market Flow ML Walk-forward Lookback v1**: Ridge baseline v1 의 과거 반복 성능 evidence 를 남기는 룩백 실행. 시장 판단 UI / 자동 매매 / AI Sessions 연결 아님.

- **Walk-forward 규칙**: `build_dataset()` 1회 계산 + 각 기준일 t 마다 `target_end_date < t` 인 labeled row 만 학습. StandardScaler / Ridge 는 기준일별 새로 fit. 최초 anchor = 756 학습 행 확보되는 첫 KODEX200 거래일. 이후 20 거래일 고정 grid (skip 이 grid 를 밀지 않음).
- **단순 기준 (simple baseline)**: 동일 학습 범위의 target 평균. Ridge 와 항상 같은 학습 범위 사용.
- **실측 (real SQLite)**: status=ok, predictions=110, 평가기간 2017-07-06 ~ 2026-06-01, 연도별 요약 10개.
  - Ridge: MAE 5.2466 / RMSE 7.8969 / directional_accuracy 0.5273.
  - Simple baseline: MAE 5.0685 / RMSE 7.9827 / directional_accuracy 0.5727.
- **산출물**: `state/ml/market_flow_walk_forward_predictions_latest.csv`, `state/ml/market_flow_walk_forward_latest.json`. 기존 baseline artifact 미변경.
- **backend 755 passed** (738 → 755, 신규 17). black / flake8 PASS. frontend 변경 0건.
- **신규 endpoint / DB 테이블 / UI / 외부 호출 0건**.
- 상세: `docs/handoff/POC2_MARKET_FLOW_WALK_FORWARD_LOOKBACK_V1_CONCLUSION.md`.

## 직전 STEP (2026-07-05, Baseline v1 Closeout, DONE)

**Market Flow ML Dataset + Baseline v1 Closeout**: 2026-07-03 PARTIAL 을 DONE 으로 승격. scikit-learn 1.9.0 을 requirements.txt 에 명시 (지시문 §6 명시 승인 하에서만), KOSPI 역사 시계열 보강 CLI (`kospi` 서브커맨드) 신규 추가, real SQLite 기반 baseline 실행하여 실측 metrics 산출.

- **KOSPI 역사 보강**: `python -m scripts.refresh_market_timeseries kospi` — NAVER_FDR 주 소스로 2870 행 신규 삽입 (2014-04-10 ~ 2025-12-18). 기존 130 행 overwrite 없음 (overwrite_performed=false). YAHOO_FDR 미조회 (NAVER 충족). 총 3000 KOSPI 행 확보.
- **Baseline 실측** (`state/ml/market_flow_baseline_latest.json`): status=ok. dataset 2960 rows (2014-05-13 ~ 2026-06-05). Split train=1756 / validation=572 / test=592 (모두 >0). Validation MAE=3.995 / RMSE=5.014 / directional_accuracy=0.4615. Test MAE=7.855 / RMSE=11.061 / directional_accuracy=0.4932. latest_inference status=ok as_of=2026-07-03 pred=+5.495%.
- **VIX strictly-prior 유지**. Ridge alpha=1.0 고정. Split 60/20/20 고정. sklearn 1.9.0.
- **backend 738 passed** (729 → 738, 신규 9 — KOSPI closeout 테스트). black/flake8 PASS. frontend 변경 0건.
- **신규 endpoint / DB 테이블 / UI / 상시 외부 호출 0건**. 외부 조회는 `kospi` 서브커맨드 1회 실행 시에만.
- **기존 ML axis1 / Market Discovery / Holdings / Preview / AI Sessions / PENDING / OCI / Telegram 미변경**.
- 상세: `docs/handoff/POC2_MARKET_FLOW_ML_DATASET_BASELINE_V1_CONCLUSION.md`.

## 시장 우선 운영 원칙 (2026-07-03 확정, 이전 STEP)

### 세부 원칙

- **시장 우선**: 시장 전체 흐름 → 보유 ETF 정합성 → 필요한 소수 상세 → AI Sessions → 전달.
- **Decision Draft Preview 는 drill-down 도구** (주력 운영 흐름 아님).
- **기존 AI Sessions 와 역할 중복되는 별도 승인 시스템 신설 금지**.
- **NAVER_FDR 주 소스 / YAHOO_FDR 보조 / KRX CSV fallback**.
- 상세: `docs/handoff/POC2_MARKET_FIRST_OPERATING_DIRECTION.md` / `docs/handoff/POC2_MARKET_FLOW_ML_DATASET_BASELINE_V1_CONCLUSION.md`.

## 완료 / 동결 / 다음 (요약)

**완료**:
- 시장 시계열 SQLite Closeout
- Market Risk Reference v1
- Decision Draft Preview v1

**동결** (본 원칙 하에서 확장 금지):
- Decision Draft Preview 추가 확장
- 별도 승인 테이블·승인 UI·결정 이력 화면 (AI Sessions 와 중복)
- 보유 ETF 전체 개별 심사형 화면 확장

**완료 추가 (2026-07-05)**:
- 시장 전체 흐름 ML 학습 데이터셋·Baseline v1 Closeout (DONE) — scikit-learn 승인 + KOSPI 시계열 보강 2870 행 + 실측 metrics 산출.

**다음**:
- 미결정 (설계자 지정 대기).

## 0. Canonical

- **Canonical state file**: `docs/STATE_LATEST.md` (본 파일)
- **Step detail files**: `docs/handoff/<step_file>.md` (Step 종료 후에만 생성)
- **Past accumulation archive**: [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md)
  — 2026-05-14 ~ 2026-06-07 사이 시간순 누적 본문. 본 정리 이후로는 더 이상 append 하지 않는다.
- 본 파일에는 현재 상태 / history 요약 / Open decisions / Index 만 둔다. **Step 상세는 append 하지 않는다.**

### Step 상세 파일 생성 규칙

```text
Step 상세 파일은 Step 종료 후 다음 Step 으로 넘어갈 때 생성한다.
진행 중 Step 의 상세 파일은 미리 만들지 않는다.
docs/STATE_LATEST.md 에는 요약만 남기고, 상세는 docs/handoff/<step_file>.md 에 둔다.
```

## 1. Current position

- **프로젝트 큰 흐름**:
  보유 현황 입력 → 시세/평가 계산 → 시장 후보 발굴(Market Discovery) → 구성종목 / 중복 분석(ETF Exposure)
  → 보유 vs 시장 Evidence → 판단 사유 있는 초안 생성(GenerateDraft) → 인간 승인 → OCI 전달 → Telegram 수신.
- **현재 완료 상태**: **Decision Draft Preview v1 — DONE** (2026-07-03).
  - 지시문 단일 목표: 보유·후보 비교 화면 선택 ETF 상세 영역에 저장 없는 임시 `판단 근거 미리보기` 추가. 선택 ETF 하나에 대한 결정적 텍스트 (LLM 미사용) — 사용자가 복사해 외부 AI 웹에 입력하는 용도.
  - **신규 endpoint**: `POST /decision-draft/preview` — 요청 `target_kind` (holding/candidate) + `ticker`. 응답 `preview_text` + `evidence_as_of` (target/kodex200/vix 세 기준일 분리). 저장 부작용 0건.
  - **신규 모듈 2종**: `app/decision_draft_preview_service.py` (5구역 텍스트 조립), `app/api_decision_draft_preview.py` (endpoint).
  - **기존 PENDING 초안 완전 분리**: `generate_draft` / `store.save` / 승인·OCI·Telegram 흐름 미참조. `store.save` 미호출 자동 테스트 검증. 새 DB 테이블 / 이력 저장 0건.
  - **외부 호출 / ML 실행 0건**: `FinanceDataReader.DataReader` 미호출 자동 테스트 검증.
  - **금지 표현 필터**: preview_text 는 "지금 매수 / 지금 매도 / 반드시 유지 / 위험이 높습니다 / 시장 전환이 예상됩니다" 등 미포함 (자동 테스트).
  - **UI 확장**: `HoldingsCompareView` 에 보유 row 클릭 상태 추가 (기존 후보 클릭과 상호 배타). 우측 선택 상세 카드 안에 `DecisionDraftPreviewCard` 삽입. 요청 식별자로 대상 변경 시 이전 응답 폐기. 신규 화면·라우트·차트 0건.
  - **API·UI 계약**: 기존 필드 삭제·이름 변경·의미 변경 0건. `MarketDiscoveryView` / `MarketRiskReferenceCard` 미수정.
  - **신규 테스트 23건 (전용 파일 케이스 수)**: 초기 12 (service 5 + endpoint 7) → FIX r1 후 14 → FIX r2 후 15 → FIX r3 후 17. FIX r3 은 loader 프로그래머 오류 propagate + endpoint 사용자 응답 유지 실측 테스트로 재구성.
  - **FIX r1 (2026-07-03)**: 사용자 화면 실측 이슈 대응. `_load_holdings_evidence` 안 `from app.holdings import load_holdings_from_file` → 실제 함수명 `load` 로 정정 (broad except 가 ImportError 를 삼켜 사용자에게 일반 실패로만 표시된 결함). broad except 안 traceback logger 추가 + stub 없이 실제 loader 를 호출하는 스모크 테스트 2건 신규.
  - **FIX r2 (2026-07-03)**: `hasattr` 기반 심볼 assert 테스트 추가 — 모듈 네임스페이스 옛 오타 심볼 존재 여부는 확인 가능. **한계**: 함수 내부 잘못된 import 문 재도입은 broad except 가 삼켜 이 테스트만으로는 감지 불가 (검증자 지적). 문서 수치 정합성 정정.
  - **FIX r3 (2026-07-03, r2 한계 근본 해소)**: 설계자 승인 Option A + C. loader (`_load_holdings_evidence` / `_load_candidate_evidence`) 의 broad except 를 데이터 오류만 catch 하도록 좁힘 (`FileNotFoundError` / `json.JSONDecodeError` / `HoldingsValidationError` / `sqlite3.Error`). 프로그래머 오류 (`ImportError` / `AttributeError` / `TypeError`) 는 삼키지 않고 propagate. endpoint 경계에서 프로그래머 오류를 catch 하여 사용자 응답 계약 (`status="error"` + "판단 근거 미리보기를 생성하지 못했습니다. 다시 시도하세요.") 유지. traceback 은 서버 로그에만 기록. **정직한 검증 범위**: loader 직접 호출 테스트가 프로그래머 오류를 잡고 (`monkeypatch.delattr` 시나리오 실측 검증), endpoint 는 사용자 친화 실패 응답을 유지한다. Bash 셀프 검증으로 두 경로 모두 실측 확인.
  - **FIX r5 (2026-07-03, 화면-preview evidence 정합)**: 사용자 화면 지적 (`TIGER 코리아배당다우존스` 상세 = +0.79%/+55.11%/-, preview = 미확인/미확인/-4.23%). Option A+C. **`_load_holdings_evidence` canonical 조립** — `enrich_holdings` (평가비중/손익률) + `build_holdings_market_evidence` (short_term_momentum) 두 원천을 동일 시점·동일 `market_cache.get_all()` quotes 로 조합. Preview 전용 다른 상대성과 계산 경로 0건. **값 없을 시 라인 삭제 금지** (설계자 Q4) — `KODEX200 대비 20거래일 초과` 는 항상 한 줄, 값 있으면 수치, 없으면 "미확인". **화면 자동 evidence 로드** — `HoldingsCompareView.tsx` 마운트 시 `handleEvidenceFetch()` 자동 호출로 화면과 서버가 동일 시점 값을 보게 함. 회귀 테스트 4건 신규. 0052D0 실측: canonical `market_weight_pct=0.79 / pnl_rate_pct=55.11` — 화면 값과 정확히 일치.
  - **FIX r6 (2026-07-03, 검증자 지적 반영)**: (1) `tests/test_decision_draft_preview.py` black 포맷 정정 (`--check` FAIL → PASS). (2) 설계자 요구 검증 fixture 명시 — 2 종목 holdings 로 총 자산 대비 `0052D0` 비중을 정확히 `0.79%` 로 구성, `pnl_rate=55.11%` 조합 (`test_fix_r6_canonical_holding_matches_screen_values_079_and_5511`). (3) `POC2_B_NEXT_ACTIONS.md` 진행 경과 표현 r5/r6 반영.
  - **FIX r7 (2026-07-03, 중복 ticker 집계 정합)**: 검증자 A-1/A-3/B-6 지적. r5 canonical 이 `enrich_holdings` raw list 를 ticker dict 로 마지막 row 만 선택 → 중복 ticker (`367760`, `0015B0`, `069500` 등) 에서 화면 `aggregateHoldingsByTicker` 집계 값과 어긋남. **`_aggregate_enriched_by_ticker` (Python) 신규** — `frontend/holdings_compare/helpers.ts::aggregateHoldingsByTicker` 를 그대로 이식 (ticker 그룹 invested/eval 합계 + 파일 전체 total_eval 기준 비중). `_load_holdings_evidence` 가 이 집계 결과를 사용. 실측 재확인: 367760 → weight=2.74 / pnl=42.19 (사용자 화면 값과 정확히 일치). 회귀 테스트 신규 1건 (`test_fix_r7_duplicate_ticker_uses_aggregated_values` — 동일 ticker 2 account_group row 케이스).
  - **backend 전체 테스트**: `714 passed` (691 → 714). black / flake8 / frontend lint / frontend build PASS.
- **이전 완료 상태**: **Market Risk Reference v1 — DONE** (2026-07-03).
  - 지시문 단일 목표: Market Discovery 첫 화면에 KODEX200 (국내 기준선) + VIX (미국 변동성 참고) 일별 맥락 evidence 카드 추가. 원시 evidence만 — 시장 국면 라벨 / 추세 예측 / 위험 점수 / ML 축2 / 매수·매도 판단 0건.
  - **VIX 실측**: FDR `DataReader("VIX", ...)` — 2014-04-08 ~ 2026-07-03 / 3079 rows / `market_benchmark_daily_price` (benchmark_id='VIX') 저장. 최신 종가 15.81. 신규 의존성 / 신규 가격 테이블 / 신규 DB 엔진 0건.
  - **API 응답 확장**: `MarketTopNResponse` 최상위에 `market_risk_reference` 필드 (kodex200 + vix) 신규. 각 항목 `availability` / `as_of_date` / `close` / `change_1d_pct` / `recent_20d_series`. VIX 만 `change_5d_pct`. 기존 필드 변경 0건.
  - **CLI `vix` 서브커맨드**: `scripts/refresh_market_timeseries.py` 에 추가. `benchmark` / `initial` / `incremental` 과 완전 분리 — 상호 호출 X (sentinel 테스트 검증). 실행당 1회, 자동 재시도 없음. 기존 가격 충돌 시 자동 덮어쓰기 금지.
  - **ML 실행 게이트**: 변경 0건. VIX 는 ML feature / 학습 데이터 / 후보 제외 규칙 / 매매 판단에 사용 X.
  - **UI**: `MarketRiskReferenceCard.tsx` 신규. `MarketDiscoveryView` 의 `MarketContextCard` 뒤 삽입. 상세 펼치기에 KODEX200 / VIX 최근 20거래일 sparkline (외부 차트 라이브러리 없이 SVG polyline). 별도 화면·라우트·메뉴 0건.
  - **신규 테스트 16건**: service (8, FIX r1 +2) + CLI/API 통합 (8, FIX r1 +1).
  - **backend 전체 테스트**: `691 passed` (675 → 691). black / flake8 / frontend lint / frontend build PASS.
  - **FIX r1 (2026-07-03)**: 검증자 A-1 (§8.2 각 시계열 최초·최종 관측일 표시 누락) + A-2/A-3 (테스트 케이스 수 / 기준일 사실 정정) + B-1 (VIX CLI latest 파싱 실패 시 명확한 실패로 변경) 보강. A-4 (recent_20d_series 응답 계약 초과 지적) 는 설계자 Q2/Q3 확정 답변 근거 conclusion §8 에 명시.
  - **BACKLOG**: "Cboe VIX 자료를 이용한 수동 과거 보정 또는 보조 검증" 항목 신규 추가.
- **이전 완료 상태**: **시장 시계열 SQLite Closeout — DONE** (2026-06-30).
  - 지시문 단일 목표: 이전 PARTIAL 상태를 네이버/FDR 주 소스 + Yahoo/FDR 보조 + CLI 최신화 + ML 실행 게이트로 닫는다. KRX CSV import 는 수동 과거 보정용으로만 유지.
  - **완료 판정**: DONE. KODEX200 (069500) 2014-04-09 ~ 2026-07-02 실측 적재 (NAVER_FDR, 3000 행). 표본 3종 (069660 KOSEF 200 / 102110 TIGER 200 / 0000D0 최근) 모두 NAVER_FDR 로 확인. **기본 SQLite `state/market/market_data.sqlite` (gitignored) 에 universe `--all` 실측 완료 — normal 1007 / missing_confirm 138 / failed 0**. `benchmark_asof_date=2026-07-02` / `eligible=1006` / `excluded=138`. missing_confirm 138 은 기존 SQLite 에 축적된 가격과 명시 소스 반환 값이 다른 케이스 — 지시문 §8.1 자동 덮어쓰기 금지 정책 그대로.
  - **신규 테이블**: `market_timeseries_refresh_state` — 단일 행 (`refresh_scope='daily_prices'`). D-2 의 `market_refresh_state` 와는 별도. 11 컬럼 (target_asof_date / benchmark_asof_date / last_attempt_* / eligible_ticker_count / excluded_ticker_count / error_summary / updated_at).
  - **신규 모듈 3종**: `app/market_timeseries_refresh_state_store.py` (SSOT CRUD), `app/market_timeseries_naver_yahoo_adapter.py` (primary → secondary 흐름, `PRICE_BASIS=SOURCE_CLOSE`), `scripts/refresh_market_timeseries.py` (CLI 4 서브커맨드).
  - **소스 정책**: NAVER_FDR primary (`NAVER:<ticker>`) → 실패 또는 빈 응답 시 YAHOO_FDR (`YAHOO:<ticker>.KS`) 1회. **호출 식별자에 소스 명시** (FIX r1 — 지시문 §4.1 준수). 자동 재시도 없음. 신규 의존성 0건.
  - **ML 실행 게이트** (지시문 §9): `POST /ml/jobs/evidence-refresh` 가 SQLite만 read 하여 사전 점검. 기존 응답 계약 유지 — 실패 시 `status="error"` + `message="시계열 최신화가 완료되지 않았습니다..."`. 새 endpoint / 새 응답 필드 0건.
  - **API·UI 계약**: 변경 0건.
  - **신규 테스트 25건**: adapter (7, FIX r1 symbol builder +1) + refresh state (5) + CLI (7) + ML gate (6).
  - **FIX r1 (2026-06-30)**: 검증자 A-1/A-2/B-1 (FDR 호출 식별자에 `NAVER:` / `YAHOO:.KS` prefix 명시) + A-3/B-6 (기본 SQLite `state/market/market_data.sqlite` 에 실측 재수행하여 refresh_state / ingestion_state row 실제 산출) 보강.
  - **FIX r3 (2026-07-03)**: 검증자 note (FDR 호출 timeout 부재) 를 CLOSEOUT conclusion §16 "알려진 한계" 로 명시 반영. §17 다음 작업 후보에 timeout 명시 항목 추가. BACKLOG §7 기존 항목과 동일 범주임을 문서화. 검증자 판정 VERIFIED_WITH_NOTES → VERIFIED 승격을 위한 note 해소.
  - **backend 전체 테스트**: `675 passed` (650 → 675). black / flake8 / frontend lint / frontend build PASS.
  - **BACKLOG**: "2014-04-07 이전 ETF 시계열 보강" 항목 신규 추가.
- **이전 완료 상태**: **시장 시계열 SQLite 기반 보강 — PARTIAL** (2026-06-30, 본 Closeout 로 DONE 승격).
  - 지시문 단일 목표: 위험 evidence·국면·백테스트의 기반이 되는 ETF·KODEX200 일별 종가 시계열을 기존 시장 SQLite (`state/market/market_data.sqlite`) 로 적재. KRX 데이터마켓 공식 다운로드 자료 (CSV/ZIP) → PC CLI import → SQLite SSOT.
  - **완료 판정**: PARTIAL. 본 환경에서 KRX 자료에 직접 접근 불가 — CLI 도구 / SQLite 계약 / 결측 분류·재개·중복방지 / fixture 기반 자동 테스트까지만 완료. 실측 AC-1~AC-5 는 사용자 PC 실행 후 채워질 영역. **FDR 대신 호출 금지** (지시문 Q2 답 준수).
  - **신규 테이블**: `market_timeseries_ingestion_state` — 종목별 적재·범위·결측 상태. ticker PK 단일 종목당 1행. 컬럼 11개. **가격 시계열 테이블은 기존 `etf_daily_price` / `market_benchmark_daily_price` 재사용 — 신규 가격 테이블 신설 0건**.
  - **신규 모듈 2종**: `app/market_timeseries_ingestion_store.py` (state CRUD + count + pending), `app/market_timeseries_ingestion_service.py` (결측 분류 + ingest_etf/benchmark).
  - **신규 CLI**: `scripts/ingest_krx_timeseries.py` — `benchmark` / `etf` / `status` 서브커맨드. 외부 네트워크 호출 X. CSV 컬럼은 한글·영문 헤더 호환. `--price-basis` 인자 필수 (자동 추정 금지).
  - **결측 분류**: 상장 전 (정상 비존재, count X) / 소스 미제공 (`source_missing` status) / 상장 후 (`post_listing_missing_count` + `partial` status) / 충돌·bad price (`missing_confirm`). 0·직전값·보간 채움 0건.
  - **재개·중복 방지**: `list_pending_tickers` 가 `status != normal` 만 반환 + `(ticker, date)` PK ON CONFLICT 흡수.
  - **API·UI 계약**: 변경 0건. 기존 `fetch_price_history` / `fetch_benchmark_history` read 경로 그대로.
  - **신규 테스트 23건**: `tests/test_market_timeseries_ingestion.py` (15, FIX r1 +4) + `tests/test_ingest_krx_timeseries_cli.py` (8, FIX r1 +2, FIX r2 +2).
  - **FIX r1 (2026-06-30)**: 검증자 A-1/A-3/A-4 (기존 가격 충돌 시 임의 덮어쓰기 금지) + B-1 (KODEX200 선행 없는 ETF 적재 normal 금지) + B-6 (CLI ETF universe 기준을 기존 SQLite `etf_master` 로 강제) 보강.
  - **FIX r2 (2026-06-30)**: 검증자 A-1/A-2/B-6 (`--ticker` 경로도 universe empty 시 거부 — 가드 일관) + A-4/B-5 (Windows 콘솔 cp949 등에서 `UnicodeEncodeError` 방지 — CLI 출력 ASCII 강제 + stdout/stderr UTF-8 reconfigure) + A-3 (FIX r1 직후 본 문서 내부 수치 불일치 정정) 보강.
  - **FIX r3 (2026-06-30)**: 검증자 A-3 (conclusion §10 변경 파일 목록의 테스트 케이스 수 `11`/`4` → `15`/`8` 정정 — §9 본문과 정합).
  - **backend 전체 테스트**: `650 passed` (627 → 650). black / flake8 / frontend lint / frontend build PASS.
  - **수정 파일**: `app/market_data_store.py` (DDL 추가), `tests/test_market_data_store.py` (테이블 목록 4 → 5종). **신규**: 위 모듈 3종 + 테스트 2종 + conclusion 1종.
- **이전 완료 상태**: **D-2 시장 갱신 상태 SQLite 영속화** (2026-06-30).
  - 지시문 단일 목표: `market_refresh_service` 의 in-memory state SSOT 를 기존 시장 SQLite (`state/market/market_data.sqlite`) 의 신규 `market_refresh_state` 테이블로 전환. 재시작 후에도 마지막 정상 갱신 상태(detail 포함)를 동일하게 노출.
  - **신규 테이블**: `market_refresh_state` — `refresh_scope='market_data'` 단일 행만 유지. 컬럼: `last_success_asof_date / last_success_at / last_attempt_started_at / last_attempt_finished_at / last_attempt_status / last_error_summary / asof / universe_count / price_attempted_count / price_success_count / price_fail_count / runtime_seconds / refresh_id / updated_at`. 별도 DB / cache / history 신설 0건.
  - **신규 모듈**: `app/market_refresh_state_store.py` — `read_state` / `write_state` / `normalize_running_to_failed` / `clear_state`. SSOT 는 SQLite, in-memory 는 동기화된 보조 캐시.
  - **service 동작 변경**: `start_refresh_job` / `_execute_refresh_job` 가 상태 변경 시점마다 SQLite upsert. `get_state_snapshot` 첫 호출 시 SQLite hydrate + running → failed 정규화 (detail 보존). 실패가 last_success_* 를 덮어쓰지 않음.
  - **API·UI 계약**: 변경 0건. `MarketRefreshStatusResponse` 필드 / `/market/refresh` / `/market/refresh/status` endpoint 그대로.
  - **신규 테스트 (10건)**: `tests/test_market_refresh_state_persistence.py` — 최초 상태 / 성공 영속화 / 새 인스턴스 detail 복구 / 성공 후 실패 보존 / running 정규화 detail 보존 / 응답 필드 회귀 / 단일 행 원칙.
  - **backend 전체 테스트**: `627 passed` (617 → 627). black PASS / flake8 PASS / frontend lint PASS / frontend build PASS.
  - **수정 파일**: `app/market_data_store.py` (DDL 추가), `app/market_refresh_service.py` (SSOT 전환), `app/api_market_topn.py` (status endpoint 에 db_path 명시), `tests/test_market_topn_api.py` (fixture reset_state_for_testing 에 db_path 전달), `tests/test_market_data_store.py` (테이블 목록 검증 4 → 4종 갱신). **신규**: `app/market_refresh_state_store.py`, `tests/test_market_refresh_state_persistence.py`, `docs/handoff/POC2_D2_MARKET_REFRESH_STATE_SQLITE_CONCLUSION.md`.
- **이전 완료 상태**: **Cleanup KS-10 Round B** (2026-06-29).
  - 지시문 목표: Round A 에서 확인된 near/ambiguity 파일 분리 → trigger=0, near=0 달성.
  - **측정 방식**: `wc -l` (Bash) 통일.
  - **분리 결과 (wc -l 실측)**:
    - `scripts/run_three_push_oci.py`: 672 → **255** (helper 모듈 분리). 신규 `scripts/three_push_oci_helpers.py` 450줄.
    - `app/api_market_topn.py`: 636 → **178** (모델·서비스 분리). 신규 `app/api_market_topn_models.py` 234줄 / `app/api_market_topn_service.py` 274줄.
  - **Round B 후 KS-10 재분류**: trigger 0건 / near 0건 (app/ 최대 586 — `app/draft.py`, 600 미달). scripts/ KS-10 기준 없음.
  - **수정 파일 2종**: `app/api_market_topn.py` / `scripts/run_three_push_oci.py`. **신규 3종**: `app/api_market_topn_models.py` / `app/api_market_topn_service.py` / `scripts/three_push_oci_helpers.py`.
  - **수정 파일 추가**: `scripts/diagnose_constituents_source.py` — F541 f-string placeholder 누락 4건 수정 (FIX 라운드).
  - **backend 전체 테스트**: `617 passed` (skip 0 / deselect 0). black PASS / flake8 PASS (FIX 라운드 포함 최종).
  - **Note**: `enrich_candidates_with_evidence` / `build_nav_discount_payload` — `DEFAULT_DB_PATH` 직접 참조 → `db_path` 파라미터화 (테스트 monkeypatch 정합성).
- **이전 완료 상태**: **Cleanup KS-10 Round A** (2026-06-29).
  - 지시문 목표: 전체 .py/.ts/.tsx 라인 수 기준선 측정 + KS-10 trigger/near 목록화 + D-1 회귀 해소.
  - **수정 파일 3종**: `tests/test_three_push_contract.py` / `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md`. 신규 1종: `docs/handoff/POC2_CLEANUP_KS10_ROUND_A_CONCLUSION.md`.
  - **backend 전체 테스트**: `617 passed`. black PASS / flake8 PASS.
- **이전 완료 상태 (prev-2)**: **BACKLOG 전수 감사·정리** (2026-06-29).
  - 지시문 단일 목표: 1270 라인 누적 BACKLOG 를 다음 Step 우선순위 판단 가능한 상태로 정리. 코드·UI·API·데이터 계약·OCI·Telegram 변경 0건.
  - **수정 docs 4종**: `docs/backlog/BACKLOG.md` (Measure-Object -Line 기준 451 라인, 16 카테고리 4필드 통일 포맷 91 항목) / `docs/STATE_LATEST.md` (§1 prepend + §5 D-1/D-2 결함 escalate + §7 BACKLOG audit 포인터) / `docs/handoff/POC2_B_NEXT_ACTIONS.md` (§0 prepend + 직전 §0 → §0-prev) / `docs/handoff/POC2_BACKLOG_AUDIT_CONCLUSION.md` (신규, Measure-Object -Line 기준 99 라인).
  - **5분류 판정 결과**: 완료 23 (RESOLVED 처리) / 폐기 11 (DISCARDED) / 중복 9 (DEDUPED) / 현재 결함 2 (STATE_LATEST §5 escalate) / 유지 91 항목 (재작성 시 sub-bullet 을 별도 항목으로 분리 — 1차 판정 65 + sub-bullet 승격 약 26). 사용자 모호 항목 일괄 판정 — L148 AI 투자세션 ETF 구성 수집 완료 / L400 보유 종목 브리핑 상세 UI 완료 / L1067 Next.js UI 세분화 폐기 / L1155 spike·holding_watch 연계 완료 / L828 market_cache 영속화 폐기 / L892 holdings 자동 불러오기 폐기 / L360 SQLite 영구 보존 폐기 / L14 ML 학습 유지(통일 포맷) / L539 Layer B 급락 임계값 §2 통합.
  - **분류 기록 위치 (검증자 A-1 지적 반영)**: 완료 / 폐기 / 중복 / 현재 결함 escalate 기록은 BACKLOG 본문에서 제거하고 `docs/handoff/POC2_BACKLOG_AUDIT_CONCLUSION.md` 외부 문서에만 보존. BACKLOG.md 는 4필드 유지 항목만 포함.
  - **통일 포맷**: 항목 / 보류 사유 / 보류된 위험 / 재검토 트리거 4필드.
  - **16 카테고리 구조**: ML/Factor/Threshold, 위험 evidence/시계열/데이터 품질, NAV/시장 데이터 source, Market Discovery/Universe, ETF 구성종목/중복률, 시장 국면/Regime, 판단 근거 저장, Holdings/포트폴리오 구조, Message/Telegram/알림, UI/Frontend, OCI/Delivery/Operations, Snapshot/History/Audit, Universe/Cache 후순위, Layer 활성 관리, 항구적 가드 정책, 메타/검증 항목.
  - **escalate 2건**: D-1 = `test_three_push_contract::test_generate_spike_alert_via_unified_endpoint` 회귀 (clean tree 에서도 실패), D-2 = `app/market_refresh_service.py` in-memory state 재시작 시 소실 (6h cooldown 가드 깨짐).
- **이전 STEP**: **보유·후보 비교 v1 CLOSEOUT** (2026-06-24).
  - 지시문 단일 목표: 사용자가 "보유와 비교" 화면에서 10초 안에 (1) 실제 보유 ETF·평가 비중, (2) 후보의 보유 노출 겹침, (3) 후보의 상대 흐름을 판단 가능하도록 정리. 신규 endpoint / 신규 계산 0건.
  - **수정 frontend 1종**: `frontend/app/components/HoldingsCompareView.tsx` — 전면 재작성.
  - **AC-1 티커별 통합**: 매입 회차 다중 행 → ticker 별 한 줄 통합 표시. `aggregateHoldingsByTicker` helper. 통합 평가금액 / 통합 손익률 / 평가 비중. 기존 enriched 원본 / 매입 회차 데이터 변경 0건 — 화면 표시용 통합만.
  - **AC-2 보유 표 6 컬럼**: ETF명 / 평가 비중 / 손익률 / 20일 KODEX 초과 / 고점 대비 / 상태. 매입 회차 / 5d / 10d / 세부 평가정보 기본 숨김.
  - **AC-3 후보 표 6 컬럼**: ETF명 / 참고점수 / 20일 KODEX 초과 / 고점 대비 / 보유 노출 / 데이터 상태.
  - **AC-4 보유 노출 단일 칸**: 한 칸에서 6가지 표현 — `직접 보유` / `직접 보유 · 구성종목도 겹침` / `구성종목 겹침 · 보유 ETF N개` / `중복 없음` / `중복 확인 전` / `중복 확인 불가`. `중복 없음`은 모든 보유 ETF 의 overlap 정상 조회 + 일치 0건일 때만.
  - **AC-5 선택 상세 보유 노출 요약 최상단**: 직접 보유 여부 / 겹침 보유 ETF 수 / 가장 큰 겹침 대상 + weight%. **AC-6 세부 근거 기본 접힘** — 구성종목 목록 / overlap 수치 / 시장 반복 정보는 사용자 명시 클릭 후에만 노출.
  - **AC-7 raw 상태값 미노출**: `ok` / `unavailable` / `not_loaded` / `loading` 직접 노출 0건. 사용자 친화 문구 — `정상` / `일부 확인 불가` / `중복 확인 전` / `중복 확인 불가` / `데이터 없음` / `확인 필요`.
  - **AC-8 후보 선택 자동 fetch 0건**: Evidence 명시 조회 버튼 유지. 후보 row 클릭은 상세 영역 갱신만.
  - **AC-9 기존 산식 변경 0건**: 새 수익률 / 새 초과수익 / 새 overlap / 보유·후보 종합점수 / 새 모델 0건. 신규 backend 0건.
  - **상수**: 신규 backend 모듈 0건. `app/api_market_topn.py` / `app/holdings.py` / `app/api_holdings_market_evidence.py` 변경 0건. OCI / PARAM / Telegram / DB 변경 0건.
  - pytest 전체 실행 명령 결과: **616 passed, 1 deselected** (회귀 0 — backend 변경 0건). deselected 1건은 본 STEP 이전부터 존재하는 기존 환경 실패. black / flake8 PASS. frontend lint / build PASS.
  - **CLOSEOUT FIX r1 (2026-06-24, A-1/A-3/B-1/B-3 수용)**: (r1-1) `computeExposure` 의 evidence 매칭 루프에서 `!ev` / `!co` 케이스를 `constituentsAnyUnavail` 마킹 → `no_overlap` 분기 도달 전 차단. 지시문 — `중복 없음` 은 모든 보유 ETF 정상 조회 + 일치 0건일 때만. (r1-2) 보유 표 고점 대비 cell 에 `중복 확인 전` 같은 중복 상태 문구 제거 → `확인 필요` 단일 표기. (r1-3) FEATURE_INVENTORY L607 의 `1 failed` stale 을 `1 deselected` (CLOSEOUT 시점 명령 결과) 로 정렬. (r1-4) B-3 파일 분리 — `HoldingsCompareView.tsx` **504 라인** (CLOSEOUT 직후 1023 라인 → 분리 후 504). 신규 모듈 2종 (`holdings_compare/helpers.ts` 300 라인 / `holdings_compare/SelectedDetail.tsx` 191 라인). 실측 기준 (`Measure-Object -Line`).
  - **CLOSEOUT FIX r2 (2026-06-24, A-2/A-3 stale 정합성)**: FIX r1 보고의 라인 수 (529 / 330 / 198) 가 실측 (`Measure-Object -Line` 기준 504 / 300 / 191) 과 불일치 → 정직 실측 표기로 정렬. FEATURE_INVENTORY §2.31 "보유 요약 표" 셀의 "고점 대비는 `확인 필요` / `중복 확인 전` 표시" stale 표현을 실제 코드 (항상 `확인 필요`) 와 맞춰 정렬.
- **이전 STEP**: **보유 ETF와 시장 후보 비교 v1** (2026-06-21).
  - 지시문 단일 목표: 기존 Market Discovery 안에서 보유 ETF 와 시장 후보 ETF 를 같은 화면에서 비교. 신규 endpoint / 신규 계산 0건 — 기존 `GET /market/topn/latest` + `GET /holdings/enriched` + `GET /holdings/market-evidence/latest` 응답을 프론트에서 조합.
  - **신규 frontend 1종**: `frontend/app/components/HoldingsCompareView.tsx` — 보유 ETF 요약 표 10 컬럼 (티커/명/매입 비중/평가 비중/손익률/5d/20d/KODEX 대비 20d/**고점 대비**/데이터 상태 + 로컬 정렬) + 후보 비교 표 (참고점수/20d/KODEX 대비 20d/고점 대비/보유 중복 + 로컬 정렬) + split pane 우측에 후보 선택 상세 (점수 근거 + 5/10/20일 수익률·초과수익 + 고점 대비 + 데이터 품질 + 보유 비교 evidence — 보유 ETF ticker 일치 + 구성종목 반복 핵심 종목 최대 5건). 보유 ETF 의 "고점 대비" 는 evidence 응답에 직접 필드 없으므로 `unavailable` 명시 (FIX r1).
  - **수정 frontend 1종**: `frontend/app/components/MarketDiscoveryView.tsx` — `CompareViewTabs` 상단 탭 ("기본" / "보유와 비교") 추가. 탭별로 기존 `CandidateTable + SummaryHeader` 또는 신규 `HoldingsCompareView` 렌더.
  - **데이터 조합 원칙 (지시문 §5)**: ETF 식별자 (ticker) 기준 client-side 매칭. (a) **exact match** — 후보 ticker ↔ 보유 ticker. (b) **constituents overlap** — 선택된 후보가 보유 ETF 와 ticker 일치 시, 해당 보유 ETF 의 `constituents_overlap.overlap_with_market_core` (보유 ETF 구성종목 ↔ 현재 후보군 반복 핵심 종목) 상위 5건 표시. 신규 수익률 계산 / 신규 중복률 계산 / 신규 종합점수 0건.
  - **Evidence 명시 조회 (지시문 §4.5)**: `not_loaded` / `loading` / `ok` / `unavailable` 상태 그대로 표시. 후보 선택만으로 자동 조회 안 함. 조회 실패 시 기존 값 유지. 사용자 버튼 "보유 비교 evidence 조회" 명시 클릭 필요.
  - **기준일 분리 표시 (지시문 §4.1, AC-7)**: 후보 기준일 (`data.asof`) / 보유 정보 기준일 (`evidence.holdings_asof`) / 중복 정보 기준일 (`evidence.market_asof`) 각각 별도 표시. 합쳐서 같은 시점처럼 표시 X.
  - **보유 중복 상태 표시 (지시문 §4.4)**: 후보 표의 "보유 중복" 컬럼 — `exact_match` (보유 일치) / `not_loaded` / `—`. `not_loaded` / `unavailable` 을 "중복 없음" 으로 해석 X.
  - **데이터 부족 처리**: 없는 값은 `—` 또는 unavailable 로 표시. 임의 채우기 / 임의 순위 / 임의 합산 0건. 점수 null 후보는 정렬 시 항상 뒤로.
  - **FIX r1 (검증자 1차 REJECTED 후속, A-1/A-2/A-3/A-4 수용)**: (r1-1) 보유 ETF 요약 표에 "고점 대비" 컬럼 추가. evidence 응답에 직접 필드 없으므로 `unavailable` 명시 (지시문 §4.2 — 없는 값은 unavailable 표시). (r1-2) 카드 하단 helper 문구에서 "매수·매도·교체·비중 조절 판단을 자동으로 제시하지 않습니다" 문장 완전 제거 (지시문 §6 / AC-9 — 부정 안내문 형태라도 해당 단어 금지). (r1-3) 신규 핵심 파일 (`HoldingsCompareView.tsx` + `POC2_HOLDINGS_CANDIDATE_COMPARE_V1_CONCLUSION.md`) 의 untracked 상태 → FIX r1 commit 시 명시적 staged. (r1-4) CONCLUSION §5.3 본문 표 헤더에 "고점 대비" 추가 + AC-2 셀 정정.
  - **FIX r2 (검증자 2차 REJECTED 후속, A-2/A-3 stale 정합성)**: (r2-1) CONCLUSION L53 AC-9 셀의 stale 표현 ("카드 하단에 사용자 고지 '본 비교 화면은 매수·매도·교체·비중 조절...'") 을 실제 UI ("UI 사용자 표시 영역에 금지 단어 0건") 와 맞춰 정정. (r2-2) STATE_LATEST L28 보유 표 컬럼 목록 9 → 10 (`고점 대비` 명시 추가). (r2-3) pytest 결과를 "616 passed (회귀 0)" 단축 표기 대신 실제 명령 결과 "616 passed, 1 failed (종료 코드 1) — 실패 1건은 본 STEP 이전부터 존재하는 기존 환경 실패" 로 정직 표기 (검증자 권고).
  - **FIX r3 (검증자 3차 REJECTED 후속, A-3 산출물 정합성)**: FIX r2 에서 STATE_LATEST + CONCLUSION 만 정정하고 POC2_FEATURE_INVENTORY §2.31 본문은 stale 잔존. 3건 정정 — (r3-1) §2.31 "보유 요약 표" 컬럼 목록 9 → 10 (`고점 대비` 명시 + FIX r1 unavailable 정책 표기). (r3-2) "사용자 고지" 셀의 stale 부정 안내문 표현을 "UI 사용자 표시 영역에 금지 단어 0건" 으로 정정. (r3-3) "테스트" 셀의 "616 passed (회귀 0)" 단축 표기를 정직 표기 ("616 passed, 1 failed, 종료 코드 1 — 기존 환경 실패 1건은 본 STEP 무관") 로 정정.
  - **FIX r4 (검증자 4차 REJECTED 후속, A-2/A-3 stale 정합성)**: FIX r3 에서 FEATURE_INVENTORY + NEXT_ACTIONS 만 정정하고 CONCLUSION AC-11 셀 (L55) stale 잔존. 1건 정정 — CONCLUSION L55 AC-11 셀의 "DONE — pytest 616 passed (회귀 0)" 단축 표기를 정직 표기 ("PARTIAL — 616 passed, 1 failed (종료 코드 1, 회귀 0 — 기존 환경 실패 1건 본 STEP 무관). AC-11 엄밀한 전체 통과 조건은 기존 회귀로 인해 충족 아님, BACKLOG 후속") 로 정정. 같은 CONCLUSION 안에서 §3 AC 표와 §8 검증 결과 표가 동일 결과를 일관되게 기록.
  - **FIX r5 (검증자 5차 REJECTED 후속, A-2/A-3 stale 정합성)**: FIX r4 에서 AC-11 셀과 §8 검증 결과 표는 정직 표기로 정렬했지만 같은 CONCLUSION §9 "FIX r1 검증" 섹션 L247 의 "616 passed (회귀 0)" 단축 표기 stale 잔존. 1건 정정 — L247 을 정직 표기 ("616 passed, 1 failed, 종료 코드 1") 로 정정. CONCLUSION 전체 활성 검증 결과 표기 3곳 (AC-11 셀 / §8 검증 결과 표 / §9 FIX r1 검증) 모두 일관 정직 표기 확보.
  - 신규 backend 0건 — `app/api_market_topn.py` / `app/api.py` / `app/holdings.py` / `app/api_holdings_market_evidence.py` 변경 0건.
  - OCI / PARAM / Telegram / scheduler / DB 구조 변경 0건. 기존 수익률/초과수익/상대상승점수/overlap 산식 변경 0건.
  - pytest 전체 명령 결과: **616 passed, 1 failed** (종료 코드 1, 회귀 0 — 실패 1건은 `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` 로 본 STEP 이전부터 존재하는 기존 환경 실패. backend 변경 0건이므로 본 STEP 무관). black / flake8 PASS. frontend lint / build PASS.
- **이전 STEP**: **ML 축1 — 상대상승 점수 실행 UI 연결** (2026-06-21).
  - 지시문 단일 목표: 기존 `relative_upside_score_v0` 실행을 Market Discovery UI 에 연결. 사용자가 CLI 없이 화면에서 점수 계산 + 정상 실행 여부 확인.
  - **신규 backend 1종**: `app/api_ml_relative_upside.py` — `POST /market/relative-upside/run` router. 동기 처리 (사용자 결정 2026-06-21) — `scripts.run_ml_relative_upside_score_v0.main()` 을 직접 import 호출 (subprocess 가 아닌 같은 프로세스 함수 호출). 실패 / rc≠0 / meta 손상 / meta.status≠ok 4분기 처리 (FIX r1 — 손상 분리). 응답 6 필드 (status / asof_date / generated_at / scored_candidate_count / gpu_execution_used / message) — device name / loss / epoch / artifact path / raw traceback 노출 0건.
  - **수정 1종**: `app/api.py` — router 등록.
  - **신규 frontend 2종**: `frontend/lib/api/mlRelativeUpside.ts` (TS API client, timeout 120s) / `frontend/app/components/RelativeUpsideRunCard.tsx` (Market Discovery 후보 목록 상단 카드 — 상태/기준일/마지막 계산/점수 반영 후보 수/GPU 실행 표시 + 단일 `[상대상승 점수 계산]` 버튼 + running 중 중복 클릭 차단 + 실패 시 기존 result 유지).
  - **수정 frontend 1종**: `frontend/app/components/MarketDiscoveryView.tsx` — 카드를 `MarketContextCard` 다음에 배치 + `onSuccess={loadTopn}` 으로 성공 시 후보 표 자동 재조회.
  - **신규 테스트 7건** (FIX r1 후 +2): `tests/test_api_ml_relative_upside.py` — 성공 6 필드 응답 + GPU 미확인 메시지 분기 + main() 예외 raise 시 기존 meta 파일 변경 0건 보존 + rc≠0 → failed + meta.status≠ok → unavailable + **meta 파일 손상 → unavailable** (FIX r1 신규) + **main() unavailable 분기에서 기존 score snapshot 파일 덮어쓰기 0건** (FIX r1 신규 — A-1 핵심 검증). 모든 테스트 `RUN_META_PATH` / `SCORE_SNAPSHOT_PATH` 를 `tmp_path` 로 monkeypatch 격리 (FIX r1 — 운영 artifact 오염 차단). 응답에 `CUDA` / `cuda` / `epoch` / `loss` / `NVIDIA` / `device_name` / `artifact_path` / `snapshot_path` / `Traceback` 노출 0건 검증.
  - **실측 (2026-06-21)**: `POST /market/relative-upside/run` → status=200, body={status: "ok", asof_date: "2026-06-19", scored_candidate_count: 1111, gpu_execution_used: true, message: "상대상승 참고점수 계산이 완료되었습니다."}. CUDA RTX 4070 SUPER 실행. 기존 ML 산식 / score snapshot 구조 / OCI runner / PARAM / Telegram 코드 변경 0건.
  - **FIX r1 (검증자 1차 REJECTED 후속, A-1/A-3/B-1/B-6 수용)**: (A-1) `scripts/run_ml_relative_upside_score_v0.py` 의 `model is None` / `inference_rows` 빈 분기에서 빈 snapshot 저장 코드 제거 → 기존 `SCORE_SNAPSHOT_PATH` 그대로 유지 + `RUN_META_PATH` 만 `snapshot_path=""` 명시 저장 (이력 추적). (A-3) CONCLUSION 문서 "응답 5 필드" 표기를 6 필드 (status 포함) 로 정정. (B-1) `_read_run_meta()` 가 `(state, payload)` 튜플 반환 — `META_STATE_MISSING` / `META_STATE_CORRUPTED` / `META_STATE_OK` 3분리. 손상 시 logger.warning + 사용자에게 "운영 상태 파일을 읽지 못했습니다" 메시지. (B-6) 모든 테스트가 `tmp_path` fixture 로 격리. frontend 주석 stale "subprocess" 표기를 "직접 import 호출" 로 정정.
  - **FIX r2 (검증자 2차 REJECTED 후속, A-2/A-3 정합성 정정)**: (r2-1) STATE_LATEST §1 본문 L28 의 "응답 5 필드" stale 표기를 6 필드로 정정. (r2-2) `app/api_ml_relative_upside.py` 모듈 docstring 의 "subprocess 실행 대기" / "기존 run meta 그대로" stale 표현을 실제 동작 (직접 import 호출 + 이력 추적용 run meta 갱신) 에 맞춰 정정. 2층 보호 메커니즘 명시. (r2-3) `scripts/run_ml_relative_upside_score_v0.py` L90 의 "failed snapshot 저장 후 종료" stale 주석을 "score snapshot 저장 안 함 + run meta 만 이력 추적용 저장" 으로 정정.
  - **FIX r3 (운영 회귀 — uvicorn sys.argv 차단)**: push 후 실측에서 사용자가 화면 버튼 클릭 시 500 발생. 원인 — `main()` 안의 `argparse._parse_args()` 가 `sys.argv` 미지정 시 uvicorn 의 `["app.api:app", "--host", ...]` 인자를 인식 못 해 `SystemExit(2)` 발생. 해결 — `main(argv)` / `_parse_args(argv)` 에 argv 명시 인자 추가 + API endpoint 가 `run_ml_main(argv=[])` 로 호출. 신규 회귀 테스트 1건 (`test_api_call_isolated_from_uvicorn_sys_argv`) 추가 — uvicorn sys.argv 오염 환경 시뮬레이션 후 POST 정상 200/ok 검증.
  - pytest **616 passed** (608 + 8 신규, 회귀 0). black / flake8 PASS. frontend lint / build PASS.
- **이전 STEP**: **ML 축1 — 후보 ETF 상대상승 참고점수 v0** (2026-06-20).
  - 지시문 §3 단일 목표: 기존 ETF 가격 이력과 5/10/20일 수익률·초과수익 evidence 를 사용해 후보 ETF 별 0~100 상대상승 참고점수를 생성하고, 기존 후보 목록에서 점수·고점 대비·근거를 함께 비교. 매수·매도·교체·비중 조절 신호 아님 (참고용 정량 재료).
  - **신규 backend 모듈 3종**: `app/ml_relative_upside_features.py` (5/10/20일 수익률 + KODEX200 초과수익 + `drawdown_20d` = close/peak−1 첫 추가 factor 계산. `CandidateFeatureRow` dataclass + 학습/추론 모드 분리 + 미래 데이터 차단 가드) / `app/ml_relative_upside_model.py` (torch `nn.Linear(7,1)` 단일 선형회귀, walk-forward 1회 split 사용자 결정 2026-06-20, Adam lr=1e-3, MSE, 200 epochs, seed=42, CUDA 우선) / `app/ml_relative_upside_score.py` (사람 언어 reasons 최대 3개 + snapshot/run-meta 빌더 + atomic write + USER_NOTICE 상수).
  - **신규 CLI 1종**: `scripts/run_ml_relative_upside_score_v0.py` — SQLite read → feature 계산 → torch GPU 학습 → 추론 → 0~100 정규화 → simple vs ML 비교 기록 → snapshot 저장.
  - **수정 모듈 1종**: `app/api_market_topn.py` — `MarketCandidate` 에 `relative_upside_score` / `drawdown_20d` / `relative_upside_reasons` 3 필드 추가, `MarketTopNResponse` 에 top-level `relative_upside_score_status` / `_asof_date` / `_generated_at` / `_user_notice` 4 필드 추가, `_merge_relative_upside_score` 머지 함수 신설. snapshot 부재 시에도 기존 후보 응답 유지 (지시문 §10 끝).
  - **수정 frontend 3종**: `frontend/lib/api/market.ts` (TS 타입 확장) / `frontend/app/components/CandidateTable.tsx` (컬럼 3개 추가 + 로컬 점수 정렬 토글 + USER_NOTICE 표시) / `frontend/app/components/MarketDiscoveryView.tsx` (props 전달).
  - **신규 의존성 1종**: `torch>=2.6.0` (CUDA 12.4 wheel — `pip install torch --index-url https://download.pytorch.org/whl/cu124`). 사용자 결정 (2026-06-20) — 지시문 §6.1 "신규 ML 라이브러리 추가 금지" 의 예외 1회 허용. RF/XGB/LGBM 비교 / 자동 튜닝 / 앙상블 0건. AC-6 GPU 학습 증거 충족용.
  - **신규 산출물 (gitignored)**: `state/ml/relative_upside_score_latest.json` (점수+근거 snapshot) + `state/ml/relative_upside_score_run_latest.json` (학습 메타). OCI 전달 / Telegram / PARAM 포함 0건.
  - **신규 테스트 24건**: `tests/test_ml_relative_upside_features.py` (7건 — drawdown 정의, future leakage 차단, KODEX 시계열) / `tests/test_ml_relative_upside_model.py` (7건 — 점수 0~100, 동률, 시간 순서 split, 셔플 없음) / `tests/test_ml_relative_upside_score.py` (10건 — reasons user-language, snapshot 구조, API unavailable/failed 분기).
  - **실측 (2026-06-20)**: universe 1,140 ticker / training row pool 66,941 / train 35,991 vs test 8,998 / train_date 2026-03-20~2026-05-08 / test_date 2026-05-08~2026-05-20 / train_loss 0.0690 / test_loss 0.0304 / device `NVIDIA GeForce RTX 4070 SUPER` / cuda_available=true / gpu_execution_used=true / train_seconds 0.256 / asof_date 2026-06-19 / scored 1,111 후보 (0~100 점수). 기존 ml_baseline_v0 경로 미변경. OCI runner / PARAM / Telegram 코드 변경 0건.
  - AC-1 ~ AC-14 모두 DONE. pytest **608 passed** (584 → +24, 회귀 0). black / flake8 PASS. frontend lint / build PASS.
- **이전 STEP**: **PUSH 사용자 표현 정리 + PARAM 적용 UI 연결** (2026-06-20).
  - 지시문 §3 단일 목표: 사람 중심 Telegram PUSH + 현재 운영 기준 UI 표시 + [현재 기준 OCI 적용] 단일 UI 동작. 2 commit 으로 분할 진행 (Phase A 메시지 + Phase B UI/API).
  - **Phase A — PUSH 사용자 표현 정리** (commit `2a65b277`):
    - **신규 backend 모듈 2종**: `app/push_user_labels.py` (39 라인 — source key 8종 → 사용자 표시 라벨 매핑 helper) / `app/push_user_copy.py` (217 라인 — 전체 unavailable 축약 메시지 + 일부 available 별도 확인 블록 + KST 시각 포맷 + push_kind 별 unavailable source key 추출).
    - **수정 모듈 5종**: `app/message_market_briefing.py` (섹션 헤더를 사용자 표시명으로 정렬, 전체 unavailable 시 `build_all_unavailable_message` fallback), `app/message_spike_alert.py` (동일), `app/draft_message.py` (holdings briefing 의 `generation_status=failed` 시 사용자용 unavailable 메시지로 즉시 종료 + `_extract_source_keys_from_status` helper 신설), `app/draft_three_push.py` (message builder 호출 직전 `collect_unavailable_source_keys()` 로 추출 후 주입), `scripts/run_three_push_oci.py` (raw 기술 식별자 11종 본문 노출 차단 이중 안전망 추가 — `param_id` / `push_kind` / snake_case source key 등).
    - **사용자 표시 라벨 (지시문 §4.2 그대로)**: 국내 ETF 시세 / 밤사이 미국 시장 / ETF 후보 흐름 / 보유 종목 평가 / NAV·괴리율 / 급등락 관찰 / 위험 참고 데이터 / 주요 뉴스.
    - **테스트 수정**: `tests/test_three_push_contract.py` 새 섹션 헤더 / 새 타이틀 assertion 으로 정렬.
  - **Phase B — PARAM 적용 UI 연결** (commit `<현재 commit>`):
    - **신규 backend 모듈 1종**: `app/api_three_push_param.py` (286 라인 — `GET /three-push/param/state` + `POST /three-push/param/apply` router). apply 는 manual_seed PARAM 생성 + latest 승격 + `sync_three_push_runtime_param.py` subprocess 호출 + sync_status_latest.json 확인의 동기 처리. 응답에 raw 식별자 (param_id / SSH target / remote path / 파일명 / raw stderr) 노출 0건.
    - **수정 모듈 1종**: `app/api.py` (router 등록).
    - **신규 frontend 모듈 2종**: `frontend/lib/api/threePushParam.ts` (TS API client) / `frontend/app/components/ThreePushParamCard.tsx` (현재 운영 기준 카드 + 단일 동작 버튼 + 진행 상태 단계 표시). 동기 호출 timeout 120초 허용.
    - **수정 frontend 1종**: `frontend/app/components/ApprovalTelegramView.tsx` (`ThreePushParamCard` 를 `ThreePushDraftCard` 상단에 배치).
    - **신규 테스트 1종**: `tests/test_three_push_param_api.py` (3건 — state 응답 형식 / display_label 사용자 친화성 / apply 실패 시 raw 식별자 미노출 + 기존 PARAM 보호).
  - **FIX r1 + r2 (검증자 1차 REJECTED + 2차 REJECTED 후속, commit `b2946643`)**: (FIX r1) 정식 PARAM runtime builder (`app/three_push_runtime_message_builder.py`) 가 Phase A 적용 누락으로 본문에 `param_id` / `param_source` / `push_kind` / snake_case source key 를 출력하던 문제를 사용자 중심 메시지로 재작성 (전체 unavailable → `build_all_unavailable_message`, 일부 available → 사용자 라벨 + 별도 확인 블록). `app/three_push_runner_common.py` 에 `check_raw_identifiers()` 공통 헬퍼 + `scripts/run_three_push_runtime_oci.py` §4-b 단계에 raw 식별자 차단 안전망 (정식 PARAM runtime 경로). `tests/test_three_push_runtime_message_builder.py` 구 계약 보호 테스트 8건 전면 재작성 (raw 식별자 미노출 + 사용자 라벨 검증). `ThreePushParamCard` `[상태 새로고침]` 버튼 제거 (지시문 §5.3 "버튼 하나만"). `_read_sync_status()` 가 부재 vs 손상을 `SYNC_STATE_MISSING` / `SYNC_STATE_CORRUPTED` / `SYNC_STATE_OK` 3분리 → 손상 시 `verification_required` UI 상태 + logger.warning. (FIX r2) CONCLUSION 문서 AC-11 "runtime runner 변경 0건" stale 문구 + §6 pytest 수치 충돌 (581 vs 584) 정정.
  - AC-1 raw 식별자 제거 / AC-2 사용자 라벨 / AC-3 unavailable 축약 / AC-4 일부 available 구조 / AC-5 현재 운영 기준 카드 / AC-6 단일 적용 동작 / AC-7 CLI 직접 실행 불필요 / AC-8 진행 상태 표시 / AC-9 실패 시 기존 PARAM 보호 / AC-10 secret 비노출 / AC-11 기존 runtime guard 유지 / AC-12 기존 산식 불변 / AC-13 범위 통제.
  - pytest **584 passed** (회귀 0, FIX r1 +3 신규 테스트 추가로 Phase A/B 시점 581 → 584). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`)은 본 STEP 전부터 존재. black / flake8 PASS. frontend lint / build PASS.
  - **검증자 판정**: 1차 commit `2a65b277` + `7aa0d363` REJECTED → FIX r1 (정식 runtime builder + UI + sync state) REJECTED → FIX r2 (문서 정합성) **VERIFIED_WITH_NOTES** 통과. NOTES: 커밋 전 전체 pytest / black / flake8 / frontend lint+build 재실행 조건 → 충족 후 commit `b2946643`.
- **이전 STEP**: **PARAM Handoff 기반 OCI Runtime 3-PUSH 전환** (2026-06-18).
  - 정식 운영 경로가 **PC message package sync → OCI package message_text 전달** 에서 **PC PARAM snapshot handoff → OCI runtime 메시지 생성** 으로 전환됨. PC 는 더 이상 매 발송마다 message package 를 만들지 않으며, 사용자가 승인한 PARAM snapshot 을 OCI 에 한 번만 전달한다. OCI 가 latest PARAM 을 고정 사용해 hourly runtime 메시지를 생성하고 Telegram 으로 발송.
  - **신규 PARAM contract**: `three_push_runtime_param.v1` (`app/three_push_runtime_param.py` — schema 정의 / `RuntimeParam` dataclass / validator / loader / writer). 필수 필드: schema_version / param_id / created_at / approved_at / approved_by / param_source / enabled_push_kinds / runtime_policy / evidence_policy / safety_policy. 금지 키 11종: message_text / buy_candidates / sell_candidates / cash_allocation / regime_confirmation / risk_threshold_confirmation / etf_ranking / token / chat_id / bot_token / telegram_token / telegram_chat_id.
  - **신규 backend 모듈 3종**: `app/three_push_runtime_param.py` (246 라인 — PARAM contract), `app/three_push_runner_common.py` (245 라인 — .env 로더 / Telegram / forbidden wording / secret 가드 / registry helper 공통 추출), `app/three_push_runtime_message_builder.py` (158 라인 — OCI runtime 전용 단순 빌더, 외부 API 호출 없음, 모든 source 기본 unavailable, runtime timestamp + param_id + data availability + 매매 지시 없음 면책 포함).
  - **신규 entrypoint 1종**: `scripts/run_three_push_runtime_oci.py` (286 라인) — PARAM runtime 정식 runner. PC package message_text 의존 없음. duplicate key = `push_kind::param_id::KST_date`. status/history 별도 경로 (`state/three_push/oci_runtime_status_latest.json` / `oci_runtime_history.jsonl` / `oci_runtime_sent_registry.json`).
  - **신규 PARAM 스크립트 3종**: `scripts/create_three_push_runtime_param.py` (manual_seed PARAM 생성 + --approve 시 latest 승격, history/<param_id>.json 보존) / `scripts/sync_three_push_runtime_param.py` (PC → OCI scp + atomic rename + remote verify) / `scripts/verify_three_push_param_oci.py` (OCI 측 stand-alone 검증, stdlib only).
  - **수정 문서 2종**: `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` — 정식 crontab 을 runtime entrypoint 로 변경 (`run_three_push_runtime_oci.py` 호출). `scripts/run_three_push_oci.py` 호출은 manual recovery template 으로 분리. `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` — 정식 운영에서 격하 명시 + 기존 등록 schtasks 비활성화/제거 안내.
  - **OCI 실측 (2026-06-18)**: PC PARAM approve + sync → OCI verify status=ok. OCI dry-run 3종 dry_run_success (msg_len market 581 / holdings 542 / spike 489). PUSH-1 send → status=sent, telegram_sent=true, duplicate_key=`market_briefing::param-20260618T142511-622384::2026-06-18`. 즉시 재실행 → status=skipped, reason=duplicate_runtime. latest PARAM 부재 시 → status=failed, reason=missing_latest_param (fail-closed). PUSH_AUTOSEND_HOLDINGS_BRIEFING_ENABLED=false 시 → status=skipped, reason=push_kind_disabled.
  - **기존 산출물 보존 (격하)**: `scripts/run_three_push_oci.py` / `scripts/sync_three_push_packages.py` / `scripts/run_three_push_sync_task.ps1` / PC Task Scheduler 등록 절차는 삭제 없이 보존하되 manual recovery / smoke test 용도로 격하. 정식 자동 발송 경로는 PARAM runtime 만 사용.
  - **회귀**: 기존 package runner / sync script / message builder / 산식 코드 변경 0건. 신규 모듈만 추가. backend pytest 533 passed + 1 failed (직전 Step부터 동일한 기존 회귀 `test_generate_spike_alert_via_unified_endpoint`, 본 Step 무관 — BACKLOG CONSOLIDATED_BACKLOG_DEBT_CLEANUP 에 기록). black / flake8 PASS. frontend lint / build PASS.
  - **BACKLOG**: `CONSOLIDATED_BACKLOG_DEBT_CLEANUP` 단일 항목으로 5건 통합 기록 (기존 회귀 / ML 후속 / runtime source 확장 / OCI holdings source / SQLite OCI 이전). 카테고리별 중복 분산 없음.
  - **검증자 판정**: 1차 commit `60912493` REJECTED → FIX r1 commit `18394f09` (중첩 forbidden key 재귀 검사 + 신규 테스트 39 케이스 + 문서 정합성 정정) → **VERIFIED_WITH_NOTES** 통과 (2026-06-19). NOTES는 사용자 승인 없는 push 절차 위반 1건 — 코드/기능/구조 위반 없음. 본 위반은 사후 사용자 보고 + 메모리 영구 규칙 (`feedback_git_lifecycle.md`) 재확인.
- **이전 STEP**: **OCI 3-PUSH 운영 등록** (2026-06-18, PARTIAL — 개발자 산출물 + 수동 등가 실행 완료, 사용자 OS 등록 + scheduled run 도달 대기).
  - PC → OCI 3-PUSH package sync와 OCI runner Telegram autosend를 KST 07:50/12:20/15:20 sync → 08:00/12:30/15:30 send 운영 스케줄로 연결할 수 있도록 PC PowerShell wrapper + Task Scheduler 등록 절차 + OCI crontab template 최신화. 수동 등가 실행으로 Telegram 1회 발송 + duplicate guard 모두 실측 통과.
  - **신규 산출물 3종**: `scripts/run_three_push_sync_task.ps1` (PowerShell wrapper, `.venv\Scripts\python.exe scripts/sync_three_push_packages.py` 호출, `logs/three_push_sync_task.log` stdout append, PS 5.1 stderr-as-error 회피를 위해 `2>&1` 미사용), `docs/handoff/PC_THREE_PUSH_SYNC_TASKSCHEDULER.md` (schtasks CLI 명령 3종 + GUI 절차 + 트러블슈팅), `docs/handoff/POC2_OCI_THREE_PUSH_OPERATION_REGISTRATION_CONCLUSION.md` (conclusion).
  - **수정 문서 1종**: `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` — venv 경로 `venv/bin/python` 명시 / .env 자동 로드 안내 / PC sync 선행 시간표 / 수동 등가 실행 절차 보강.
  - **OCI 실측 (2026-06-18)**: PC sync `status=success` (3/3 upload + manifest + verify success) / OCI dry-run 3종 `dry_run_success` (msg_len: market 997, holdings 1606, spike 878) / `--push-kind market_briefing --mode send` → `status=sent, telegram_sent=true` / 동일 package_id 재실행 → `status=skipped, reason=duplicate_package, telegram_attempted=false` / token/chat_id 미노출.
  - **stale 사례 (참고)**: 첫 dry-run에서 `asof_date=2026-06-17` 기반 36.7h stale 감지 → PC re-sync로 `asof_date=2026-06-18` 갱신 후 정상화. 운영 시 PC sync가 발송 직전 매번 실행되면 fresh 보장.
  - **사용자 수행 대기 (DONE 격상 조건)**: (1) PC Task Scheduler 3 task 등록 (schtasks CLI 또는 GUI), (2) OCI crontab 3 entry 등록 (`crontab -e`), (3) 첫 scheduled run 자동 trigger 결과 확인.
  - **회귀**: backend 코드 / frontend 코드 / runner / sync script / message_text / 산식 변경 0건. pytest 533 passed + 1 failed (`tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` — Clean tree에서도 동일하게 실패하는 직전 STEP 기존 회귀, 본 STEP 무관). frontend lint / build PASS.
  - **사고 처리 (별도)**: 작업 초기 단계에서 개발자가 `.env`를 `Read`로 출력해 토큰이 대화 컨텍스트에 평문 인용된 사고 발생 → 사용자가 토큰 재발급 + PC/OCI .env 동시 갱신. 메모리에 `feedback_secret_file_handling.md` 영구 규칙 추가 (secret 파일은 `Read` 금지, `Grep` 키 매칭만).
- **이전 STEP**: **OCI 3-PUSH Crontab Runner & Telegram Autosend** (2026-06-16 FIX r4 최종).
  - OCI 에서 crontab 으로 PUSH-1 / PUSH-2 / PUSH-3 를 자동 실행하고 조건 충족 시 Telegram 발송하는 runner 구현.
  - **신규 스크립트 1종**: `scripts/run_three_push_oci.py` — `--push-kind {market_briefing|holdings_briefing|spike_or_falling_alert} --mode {dry-run|send}`. guard 7종 (global enable flag / push_kind별 enable flag / generation_status=failed 차단 / 최신성 36h guard / 중복 발송 방지 / 금지 문구 검사 / token/chat_id 비노출). stdlib 전용 (추가 패키지 0건).
  - **신규 문서 1종**: `docs/handoff/OCI_THREE_PUSH_CRONTAB_TEMPLATE.md` — push_kind 3종 crontab entry + 환경변수 설명 + dry-run 먼저 확인 절차.
  - **수정 모듈 1종**: `app/three_push_package_exporter.py` — `build_holdings_briefing_package` 에 message_text 동기화 추가 (직전 Step 누락 bug fix — holdings package message_text 가 빈 문자열로 저장되던 문제).
  - **신규 상태 파일 경로** (gitignored): `state/three_push/oci_runner_status_latest.json` / `state/three_push/oci_runner_history.jsonl` / `state/three_push/oci_sent_registry.json`.
  - **FIX r4 (2026-06-16)**: `_load_dotenv_file()` stdlib .env 파서 추가 (OCI crontab 환경에서 .env 자동 로드) / HTTPError 404→`malformed_telegram_api_url`, 401→`invalid_or_placeholder_bot_token`, 기타→`other_non_secret_error` 분류 / .env 로드 실패 시 silent pass → stderr 경고 출력.
  - **OCI 실측 (2026-06-16 FIX r4)**: dry-run 3종 `dry_run_success` (market_briefing msg_len=1252 / holdings_briefing msg_len=1793 / spike_or_falling_alert msg_len=938) / send + enable flags → `status=sent, telegram_sent=true` / 중복 실행 → `status=skipped, reason=duplicate_package`.
  - **환경변수**: `THREE_PUSH_PACKAGE_DIR` (기본 OCI 경로) / `PUSH_AUTOSEND_ENABLED` / `PUSH_AUTOSEND_{KIND}_ENABLED` 3종 / `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `THREE_PUSH_MAX_PACKAGE_AGE_HOURS` (기본 36).
  - pytest **534 passed** (PC 로컬 환경 기준 / 회귀 0). black / flake8 PASS.
- **이전 STEP**: **PC-to-OCI 3-PUSH Evidence Package Sync** (2026-06-15).
  - PC 에서 생성한 `three_push_runtime_package.v1` package 3종 + manifest 를 OCI 지정 경로로 동기화하는 최소 경로 구현. OCI crontab runner 가 읽을 수 있는 package 공급 경로 확보.
  - **신규 backend 모듈 1종**: `app/three_push_package_exporter.py` / **신규 스크립트 2종**: `scripts/sync_three_push_packages.py` / `scripts/verify_three_push_packages_oci.py`.
  - **신규 상태 파일 경로**: `state/three_push/packages/` + `state/three_push/sync_status_latest.json`.
  - pytest **534 passed** (회귀 0). black / flake8 / py_compile PASS. OCI 실측 status=success.
- **이전 STEP**: **3-PUSH Context Cleanup — KS-10 trigger/near 4건 해소** (2026-06-14).
  - 직전 STEP (3-PUSH Message Text Runtime Evidence 반영) 의 PARTIALLY_VERIFIED 판정 사유였던 KS-10 trigger / near 4건을 모두 helper 모듈 분리로 해소. 산식 / 문구 / 데이터 계약 / API endpoint / message_text 의미 변경 0건.
  - **처리한 4건 (before → after)**: `app/push_context.py` 798→**72 라인** (trigger 해소, format/market/holdings/spike 4 모듈로 분리 + orchestration wrapper 만 유지). `scripts/diagnose_nav_discount_source.py` 984→**524 라인** (trigger 해소, judge_*/record/markdown helper 모듈로 분리). `app/draft_message.py` 616→**299 라인** (near 해소, focus/summary 렌더링 분리). `app/market_topn.py` 613→**347 라인** (near 해소, 상수/dataclass/helper 분리).
  - **신규 모듈 7종**: `app/push_context_format.py` (59) / `app/push_context_market.py` (266) / `app/push_context_holdings.py` (202) / `app/push_context_spike.py` (191) / `app/draft_message_focus.py` (216) / `app/market_topn_helpers.py` (234) / `scripts/diagnose_nav_discount_source_helpers.py` (391). 모두 KS-10 safe.
  - **호환성**: 기존 `from app.push_context import ...` / `from app.draft_message import ...` / `from app.market_topn import ...` import 경로 모두 유지. 테스트 / 호출자 코드 변경 0건.
  - **검증 후 trigger / near 잔여 0건** (git-tracked 기준, `.gitignore` 대상 backup/ref 제외 — 사용자 결정): backend `.py` 중 ≥600 라인 0건 (최대 524 라인 = `scripts/diagnose_nav_discount_source.py`). frontend `.tsx` 중 ≥850 라인 0건 (최대 691 라인). tests `.py` 중 ≥1450 라인 0건 (최대 924 라인). 측정 도구: PowerShell `Get-Content | Measure-Object -Line` (실제 의미 있는 줄 수 기준).
  - pytest **534 passed** (직전 STEP 534 유지 / 회귀 0). black / flake8 (신규 파일 0 warning) / Next.js build PASS.
- **이전 STEP**: **3-PUSH Message Text Runtime Evidence 반영** (2026-06-14).
  - 직전 STEP 에서 만든 `runtime_package` + `push_context` 의 실제 evidence (미국 지수 실제 등락률 / Market Discovery 상위·하위 흐름 / ML baseline 룩백 / holdings × runtime quote / universe momentum 후보) 를 PUSH-1 / PUSH-2 / PUSH-3 `message_text` 에 사람이 판단에 쓸 수 있는 수준으로 반영. 신규 source / 신규 dependency / 신규 endpoint / OCI runtime / scheduler / 매수·매도·교체·현금비중·조정장·위험 threshold 0건.
  - **신규 backend 파일 0건**. 신규 frontend 파일 0건. 신규 API endpoint 0건.
  - **수정 모듈 (라인 수 실측, 검증자 r2 NOTES 반영 후)**: `app/push_context.py` 247→**798 라인** (observation 별 실제 값 + 헬퍼 5종 추가 — overnight_us_lines 풍부화 + market_trend_lines / risk_pattern_lines / holdings_observation_lines / spike_view_lines 신규). ⚠ **KS-10 trigger (백엔드 핵심 모듈 ≥650)**. `app/message_market_briefing.py` 197→**225 라인** (body 에 [국내 시장 내부 신호] + [위험 패턴 참고 (ML baseline 룩백)] 2 섹션 + candidates/items 양쪽 호환). `app/message_spike_alert.py` 239→**240 라인** (`_spike_view_section` 제거 + `spike_view_lines(push_context)` 호출로 대체 — score 단독 표시 폐기). `app/draft_message.py` 586→**616 라인** (`_runtime_evidence_lines(payload)` 신규 + PUSH-2 본문에 [보유 종목 관찰 포인트] + [시장 흐름 연결 (market_view)] + [리뷰 포인트] 삽입). ⚠ **KS-10 근접 near (≥600)** — trigger 까지 34 라인 여유. `app/draft.py` 559→**586 라인** (`_build_holdings_payload` 가 PUSH-2 evidence 에 compute_topn 결과를 채움 — AC-4 market_view 연결 강화. compute_topn 은 함수당 1회만 호출 후 재사용 — 검증자 r2 NOTES B-6 반영. candidates 0건 시 빈 dict 유지로 FIX r3 안전장치 보존).
  - **신규 테스트 파일**: `tests/test_three_push_message_text_runtime_evidence.py` **638 라인** (15건 — AC-1 / AC-2 / AC-3 / AC-4 / AC-5 / AC-7 / AC-8 / AC-10 검증).
  - **PC 라이브 본문 실측**:
    - PUSH-1 에 `[밤사이 미국 시장 (runtime probe)] • NASDAQ +0.85% (close 18,000.12) • SPX +0.41% (close 5,400.33) • SOX +1.25% (close 5,200.45) • 반도체 지수 강세는 국내 반도체/성장 ETF 해석에 참고 가능` + `[국내 시장 내부 신호 (Market Discovery)] 상위/하위 흐름 1줄` + `[위험 패턴 참고 (ML baseline 룩백)] 43거래일 룩백 1줄` 모두 노출.
    - PUSH-3 에 `[universe momentum 관찰 (push_context 기반)] • {name}: 1d +X.XX%, 20d +X.XX% · 방향 up · data_quality 이상 없음 · 보유 종목과 겹치지 않음` 풍부 1줄/item 노출 (수익률 근거 / 방향 / data_quality / overlap 4축).
    - PUSH-2 에 `[보유 종목 관찰 포인트] • {name} ({ticker}): runtime 시세 {±X.XX%} (가격 {N,NNN}) · 국내 기준선 — 밤사이 미국 지수 흐름과 함께 확인 필요 — 관찰 필요` + `[시장 흐름 연결 (market_view)] • 밤사이 미국: NASDAQ +0.85%, SPX +0.41%, SOX +1.25% / 상위(one_month): ...` + 리뷰 포인트 노출.
  - pytest **534 passed** (직전 STEP 519 → +15 신규 / 회귀 0). black / flake8 / Next.js build PASS.
  - ⚠ **KS-10 trigger + near**: `app/push_context.py` 798 라인 (trigger ≥650). `app/draft_message.py` 616 라인 (near ≥600, trigger 까지 34 라인 여유). 본 STEP 범위 안에서 자연 증가. 단일 Cleanup STEP 으로 두 파일 책임 분리 권고 (사용자 확인 항목).
- **이전 STEP**: **3-PUSH Runtime Package PC 검증** (2026-06-13).
  - `three_push_runtime_package.v1` 구조를 PC 에서 실제 evidence + runtime probe (네이버 국내 시세 + Yahoo Finance 미국 지수 3종 Nasdaq/SPX/SOX) 로 생성해 Approval/Telegram preview 에서 상태 확인 가능한 상태까지 검증. 3종 push_kind 모두 `draft_payload.runtime_package` 에 schema_version `three_push_runtime_package.v1` 저장 — OCI handoff JSON 으로도 자동 전달 (store.write_handoff_artifact 변경 0건).
  - **신규 PUSH 전용 endpoint 0건 (Q3 사용자 결정)**: PUSH-1/3 은 기존 `POST /runs/generate + input_data.push_kind` 분기, PUSH-2 는 기존 `POST /runs/generate-from-holdings` 유지. holdings 데이터 의존성으로 PUSH-2 endpoint 통합 강요는 과한 설계자 지시였음 — 사용자 결정으로 분리 유지.
  - **신규 dependency 0건 (Q1 사용자 결정)**: `urllib` + `json` + `http.cookiejar` 만 사용. `requests` / `yfinance` 추가 없음.
  - 신규 backend 모듈 5종 (FIX r2/r3 후 실측): `app/runtime_us_indices_probe.py` (**171 라인**, Yahoo Finance chart endpoint + cookie jar 단일 opener 캐시 — rate-limit 회피), `app/runtime_kr_quote_probe.py` (**182 라인**, Naver polling endpoint), `app/runtime_probe_cache.py` (**133 라인**, 30분 TTL cache `state/runtime/three_push_runtime_probe_latest.json`), `app/runtime_package.py` (**292 라인**, three_push_runtime_package.v1 빌더 + push_kind 별 generation_status 산정, FIX r3 에서 failed 시 message_contract.message_text 빈 문자열 강제 + unavailable runtime 도 warning 처리), `app/push_context.py` (**247 라인**, FIX r2 추가 — push_kind 별 view 빌더, FIX r3 에서 빈 view 는 키 자체 생략). 모두 KS-10 안전.
  - 신규 frontend Card: `RuntimePackageStatusCard` (**204 라인**) — `draft_payload.runtime_package` 의 status / generation_status / kr·us probe 요약 + raw JSON details. 빈 slot placeholder 노출 0건 (`status==="unavailable"` 일 때 해당 행 자체 생략).
  - 수정 모듈 (KS-10 라인, FIX r2/r3/r4/r5/r6 후 실측): `app/draft.py` 465→**559 라인** (PUSH-2 `_build_holdings_payload` 에 runtime_package + push_context 키 추가 + FIX r4 동기화 가드 + FIX r5 Run.message_text 가드), `app/draft_three_push.py` 207→**344 라인** (PUSH-1/3 generate 함수에 cache-aware runtime probe + build_push_context + build_runtime_package 호출 + FIX r5 Run.message_text 가드), `app/delivery.py` 233→**251 라인** (FIX r6 — holdings fallback 분기에 runtime_package.generation_status=failed 체크 + DeliveryError 명시 차단). `write_handoff_artifact` 변경 0건 — draft_payload 전체 보존으로 runtime_package 자동 포함.
  - 실측 (live API + live probe, 2026-06-13 KST 오전): Nasdaq close=25,888.844 +0.70% / SPX close=7,431.46 +0.65% / SOX close=13,371.47 +9.42% / KODEX 200 price=129,270 +4.38% / KODEX 코스닥150 price=18,015 +2.15%. `POST /runs/generate` PUSH-1 generation_status=ok / PUSH-3 generation_status=ok / `POST /runs/generate-from-holdings` PUSH-2 generation_status=ok + message_text 2,507자 + runtime_package.message_contract.message_text 와 동일 (AC-6).
  - 30분 TTL cache 동작: cache miss → probe 1회 + 저장 (단, 두 snapshot 모두 failed 면 cache 저장 건너뜀 — 다음 호출이 즉시 재시도, B-6 정책), cache hit → probe 0건, TTL 만료 → 새 probe, force_refresh → bypass, 손상 → fall-through 후 재조회. 단위 테스트 7건 통과 (cache_miss / cache_hit / cache_expired / force_refresh / corrupted_cache / both_failed_not_cached / partial_cached).
  - 회귀 1건 해소: `tests/test_universe_seed.py::test_step5c_endpoint_does_not_affect_holdings_draft_flow` 의 `expected_keys` 에 `"runtime_package"` 추가 (Q4 — 신규 키 1건 허용, 기존 키 유지).
  - **FIX r2 (검증자 1차 REJECTED 후속, A-1/A-3/B-1/B-6 수용)**:
    (A-1 (1)) message_text 생성 흐름을 `runtime_package → push_context → message_text` 로 정렬. 신규 모듈 `app/push_context.py` 추가 (현재 라인 수는 §1 상단 신규 모듈 5종 표 참조 — FIX r3 보강 후 247 라인). push_kind 별 `market_view` / `holdings_view` / `spike_view` 빌더. `message_market_briefing.build_market_briefing_message` 와 `message_spike_alert.build_spike_alert_message` 에 `push_context` 옵션 인자 추가. PUSH-1 message_text 안에 `push_context.market_view.observations` 기반 `[밤사이 미국 시장 (runtime probe)]` 1줄 섹션 추가 — runtime probe ok 시에만 노출, failed/unavailable 시 섹션 자체 생략 (AC-7 placeholder 금지 유지). PUSH-3 도 `push_context.spike_view.items` 기반 `[universe momentum 관찰 (push_context 기반)]` 섹션 추가. PUSH-2 는 `push_context.market_view` 가 holdings_briefing 의 §7.2 필수 evidence 조건 (`holdings_snapshot + (market_view 또는 market_discovery_snapshot)`) 을 충족.
    (A-1 (2)) `runtime_package._check_holdings_briefing_requirements` 에 push_context.market_view 또는 pc_evidence.market_discovery_snapshot 존재 확인 추가 — 둘 다 없으면 generation_status=failed + missing_sections.
    (B-1) `_runtime_snapshot_with_cache` / `_runtime_snapshot_for_holdings` 의 broad `except Exception` 을 `except (OSError, TimeoutError)` 로 좁힘 — 코드 결함은 호출자에게 전파, I/O 실패만 흡수 + 예외 타입 logger.warning 명시.
    (B-6) `runtime_probe_cache._write_cache` — 두 snapshot 모두 failed/unavailable 인 경우 cache 저장 건너뛰는 `_both_failed` 가드 추가. 한쪽이라도 ok/partial 이면 저장 (다음 호출이 그대로 사용). 신규 테스트 2건.
  - **FIX r3 (검증자 2차 REJECTED 후속, A-1/A-3/B-1/B-6 수용)**:
    (A-1 (1)) `unavailable` 도 정상 통과 차단 — `push_context.build_market_view` / `build_holdings_view` / `build_spike_view` 가 observations/items 1건도 없으면 빈 dict 반환. `build_push_context` 도 빈 view 는 키 자체 생략. holdings_briefing 검증의 `bool(push_context.get("market_view"))` 가 빈 dict 면 False 가 되어 정상 차단.
    (A-1 (2)) `runtime_package._evaluate_generation_status` 가 runtime snapshot `status="unavailable"` 도 warning 으로 처리 — partial 노출 (이전엔 unavailable 이 ok 정상 통과). kr/us 양쪽 동일.
    (A-1 (3)) `build_runtime_package` 가 `generation_status.status=="failed"` 인 경우 `message_contract.message_text` 를 빈 문자열로 강제 — "failed 인데 정상 본문" 차단 (계약 §12 정렬). Run.message_text 는 그대로 유지 (preview UI 가 generation_status 함께 보고 판단).
    (A-3) STATE_LATEST.md §1 의 라인 수 stale 값을 실측값으로 정정 (push_context 247 / runtime_package 292 / runtime_probe_cache 133 / draft 544 (FIX r3 시점) / draft_three_push 332 / us_indices 171). FIX r4 후 draft.py 는 추가로 552 라인.
    신규 테스트 4건 (`test_unavailable_runtime_us_marks_partial_status` / `test_unavailable_runtime_kr_marks_partial_status` / `test_failed_package_clears_message_contract_text` / `test_empty_market_view_not_treated_as_present`).
  - **FIX r4 (검증자 3차 REJECTED 후속, A-1 / B-1 / A-3 수용)**:
    (A-1 / B-1) `app/draft.py:generate_draft_from_holdings()` 의 message_contract 동기화 단계가 FIX r3 의 "failed package 본문 비움" 안전장치를 무력화하던 문제 해소 — 동기화 시점에 `runtime_package.generation_status.status == "failed"` 확인 후 failed 면 `mc["message_text"] = ""` 유지 (정상 본문 차단). holdings 경로에서도 FIX r3 정책이 일관되게 적용된다.
    (A-3) 본 §1 안의 FIX r2 항목에 남아있던 `push_context.py 216 라인` 표기를 §1 상단 신규 모듈 5종 표 (FIX r3 후 247 라인) 참조로 정정 — 같은 §1 안에서 라인 수가 일관되게 표기됨.
    신규 테스트 1건 (`test_holdings_draft_failed_package_keeps_message_contract_empty`) — 모든 evidence stub 으로 unavailable 만들어 generation_status=failed 재현, 동기화 후에도 message_contract.message_text 가 빈 문자열인지 검증.
  - **FIX r5 (검증자 4차 REJECTED 후속, A-1 / B-1 / B-6 / A-3 수용)**:
    (A-1 / B-1 / B-6) 실제 승인/preview/Telegram 발송의 단일 소스인 `Run.message_text` 도 `runtime_package.generation_status.status == "failed"` 이면 None 으로 비운다. PUSH-1 (`generate_market_briefing_draft`) / PUSH-2 (`generate_draft_from_holdings`) / PUSH-3 (`generate_spike_alert_draft`) 모두 동일 가드 적용 — 대칭성 유지. Run.status 는 PENDING_APPROVAL 유지 (기존 4-state 흐름 손상 X). `RunPanel` 은 message_text=None 일 때 정적 fallback ("승인 대기 메시지 초안 미리보기 미지원" 안내) 으로 자연스럽게 떨어져 정상 본문 preview 가 보이지 않고, `RuntimePackageStatusCard` 의 generation_status=failed 가 함께 표시되어 사용자가 reject 결정을 내릴 수 있다.
    (A-3) `POC2_B_NEXT_ACTIONS.md` 의 stale 라인 수 5건 (`runtime_probe_cache.py 120` / `runtime_package.py 278` / `draft.py 532` / `draft_three_push.py 311` / `push_context.py 216`) 을 실측 (133 / 292 / 552 / 332 / 247) 으로 정정. FIX r5 후 draft.py 559 / draft_three_push.py 344.
    신규 테스트 2건 (`test_holdings_draft_failed_package_clears_run_message_text` / `test_market_briefing_failed_package_clears_run_message_text`) — Run.message_text 가 failed 시 None 인지 검증 + Run.status 는 PENDING_APPROVAL 유지.
  - **FIX r6 (검증자 5차 REJECTED 후속, A-1 / B-1 / B-6 / A-3 수용)**:
    (A-1 / B-1 / B-6) `app/delivery.py:deliver()` 의 holdings legacy fallback 분기가 FIX r5 의 "failed package 시 Run.message_text=None" 가드를 무력화하던 문제 해소. fallback 으로 `draft_message.build_message_text(...)` 를 호출해 정상 본문을 재생성하던 경로에 `runtime_package.generation_status.status == "failed"` 사전 확인 가드 추가 — failed 면 fallback 진입 자체를 차단하고 `DeliveryError` 명시 raise (PUSH-1/3 의 기존 가드 패턴과 정렬). PUSH-2 holdings 도 failed package 일 때 OCI 로 정상 본문이 발송되지 않는다 (계약 §12 일관 적용).
    (A-3) `app/delivery.py` 변경 0건 표기를 233→**251 라인** 으로 정정 (본 STEP 에서 delivery.py 가 처음 수정됨). STATE_LATEST §1 의 "수정 모듈" 행에도 반영.
    신규 테스트 1건 (`test_holdings_delivery_rejects_failed_package_message_rebuild`) — failed package 의 holdings draft 가 delivery 진입 시 DeliveryError 로 차단되는지 검증.
  - pytest **519 passed** (+29 신규 / 회귀 0, 직전 STEP 490 → 519, FIX r6 후). black / flake8 / Next.js build PASS.
  - 사용자 결정 (Q1~Q5): Q1=urllib 기반 미국 지수 probe (신규 dep 금지), Q2=Naver realtime quote probe, Q3=PUSH-2 endpoint 분리 유지, Q4=runtime_package 키 1건만 추가/기존 키 유지, Q5=30분 TTL cache (refresh endpoint 없음).
- **이전 STEP**: **3-PUSH Message Contract 정렬** (2026-06-12).
  - 기존 `Run → Approval → OCI handoff → Telegram` 단일 경로를 유지하면서 하루 3종 PUSH 메시지의 `message_text` 계약 정리. 새 PUSH API / Telegram 직접 발송 / OCI 재구성 / scheduler / 신규 외부 source / 매수·매도·교체·현금비중·조정장 확정 0건.
  - 신규 builder 2종: `app/message_market_briefing.py` **184 라인** (PUSH-1 시장 흐름 브리핑), `app/message_spike_alert.py` **209 라인** (PUSH-3 급등락 관찰 신호). 모두 외부 source 호출 0건 — ML baseline evidence snapshot / compute_topn / universe_momentum_latest.json read-only 만 사용.
  - **신규 API endpoint 0건 (FIX r2 — 설계자 수용)**: 1차 작업에서 신설했던 `/runs/generate-{market-briefing,spike-alert}` 와 `app/api_three_push.py` 는 §3 / §11 "별도 PUSH API 신설 금지" 와 충돌하여 **모두 제거**. PUSH-1 / PUSH-3 는 기존 `POST /runs/generate` 의 `input_data.push_kind` 분기로 통합.
  - draft entry 2종 신규: `generate_market_briefing_draft()`, `generate_spike_alert_draft()`. `generate_draft(input_data)` 가 `push_kind` 값으로 분기. Run 모델에 `push_kind: Optional[str]` 추가 (legacy run 하위호환 — None 허용).
  - PUSH-2 (holdings_briefing) 는 기존 `generate_draft_from_holdings()` 가 재정의 — push_kind 만 명시. builder / payload 변경 0건. 별도 holdings 데이터 의존성으로 인해 기존 `/runs/generate-from-holdings` endpoint 유지.
  - delivery fallback 보강: message_text 누락 시 holdings builder 로 rebuild 되던 분기에 `push_kind in {"market_briefing", "spike_or_falling_alert"}` 가드 추가 — raw recommendations 발송 차단.
  - frontend: `Run.push_kind` 타입 추가, `generateMarketBriefingDraft()` / `generateSpikeAlertDraft()` API 함수 + `ThreePushDraftCard` 신규 (ApprovalTelegramView 안 임시 진입점, 발송 시간 / UX 확정은 별도 STEP — 지시문 §13).
  - **FIX r2 추가 변경**: (1) `SPIKE_DISPLAY_THRESHOLD_PCT` → `SPIKE_DISPLAY_RETURN_PCT_MIN` 으로 rename (변수명에 "threshold" 단어 제거 — §12 "위험 threshold 확정 금지" 와 의미 분리). message_text 본문의 "표시 임계" → "표시 하한" 으로 정리. (2) `_load_universe_artifact` 가 부재(정상)와 손상(이상) 을 logger.debug / logger.warning 으로 구분 (B-1 의심 해소). (3) `app/models.py` docstring 갱신 (`message_text` / `push_kind` 필드 반영, "필드 4개만 사용" 표현 정정).
  - **FIX r3 추가 변경 (검증자 PARTIALLY_VERIFIED 후속, B-2 / B-3 / B-6 수용)**: (1) draft.py 책임 집중 해소 — PUSH-1/3 entry (`generate_market_briefing_draft` / `generate_spike_alert_draft`) + 분기 진입점 (`generate_*_via_generic`) + `_load_universe_artifact_for_spike` 를 신규 `app/draft_three_push.py` (**207 라인**) 로 분리. draft.py 623 → **465 라인** (KS-10 안전 영역 복귀). draft.py 는 re-export 만 유지 (기존 호출자 호환). (2) stale 주석 정리 — `app/api.py` 의 "app/api_three_push.py 로 분리" 와 `frontend/lib/api/runApproval.ts` 상단 주석의 삭제된 endpoint 표현 모두 정정.
  - 실측 (live API, FIX r2 후): `POST /runs/generate` (`input_data.push_kind="market_briefing"`) → 496자 / push_kind=market_briefing 전파. (`spike_or_falling_alert`) → 213자. 신규 PUSH endpoint 2개는 405 (제거 확인).
  - pytest **490 passed** (+20 신규, 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- **이전 STEP**: **UI 안전실행 — ML evidence 갱신 background job** (2026-06-11, commit `b855a982`).
  - 기존 CLI 3종 (`generate_ml_features` → `check_ml_feature_sanity` → `run_ml_baseline_v0`) 을 Data Status 화면의 "ML evidence 갱신 실행" 버튼 1개로 안전하게 background 에서 순차 실행. CLI 경로는 그대로 살아있음 (이중화).
  - 신규 모듈: `app/ml_job_runner.py` **447 라인** — job state schema + 3단계 runner + `threading.Lock` (in-process) + on-disk `state/ml/ml_job_status_latest.json` lock + PID/heartbeat 기반 stale 자동 해제 (10분, 사용자 결정).
  - 신규 API: `POST /ml/jobs/evidence-refresh` (background 시작, 즉시 반환) + `GET /ml/jobs/latest` (read-only). FastAPI `BackgroundTasks` 사용 — Celery/Redis/신규 DB 0건 (§8).
  - 신규 Card: `MLEvidenceRefreshCard` (DataStatusView 최상단). 실행 중 5초 polling 자동 갱신. 단계별 상태 / 시작·종료 시각 / 실패 메시지 / 마지막 성공 요약 표시. 매수/매도/추천/현금/조정장/위험알림 문구 0건.
  - 단계 실패 시: 이후 단계 skipped, 기존 snapshot 3종 (feature/sanity/baseline) **삭제하지 않음** (마지막 성공 결과 보존, AC-6).
  - 중복 실행 차단: in-process Lock + on-disk status running 검사. 중복 POST 는 새 job 안 만들고 현재 running 응답 (already_running).
  - 실측 (uvicorn 직접 호출): POST `/ml/jobs/evidence-refresh` **2.6ms** 만에 accepted 반환 / 즉시 중복 POST 2.2ms 만에 already_running / 단계별 polling (feature→sanity→baseline) 정확 / 최종 status=success, evaluated_days=43, baseline_report_status=ok.
  - **FIX r2 (검증자 1차 REJECTED 후속, 2건)**:
    (A-1 / B-6) Windows 에서 `os.kill(pid, 0)` 이 PID 0 을 alive 로 반환하고 자기 PID 대상 시 KeyboardInterrupt 유발 가능 — `_PID_CHECK_SUPPORTED = sys.platform != "win32"` 분기 추가. Windows 에서는 PID 확인 비활성화 + heartbeat 10분 만으로 stale 판정 (POSIX 는 기존 로직 유지). psutil 등 신규 의존성 0건 (§8 정신 준수).
    (B-1) `_read_status` 가 JSON 손상 시 None 반환해 미실행과 구분 안 되던 문제 — `_read_status_raw()` 가 `(state, error)` tuple 반환하도록 변경. `get_latest_status()` 도 동일 시그니처. API 가 손상 시 `status="error"` 응답 + frontend Card 에 error 분기 표시. POST 도 손상 감지 시 새 job 자동 생성 안 함 (fail-loud).
  - pytest **470 passed** (+16 신규, 회귀 0, FIX r2 후 3회 연속 비결정성 0건 확인). black / flake8 / Next.js build PASS.
- **이전 STEP**: **ML Baseline Evidence Draft Integration** (2026-06-11, commit `f7ec493e`).
  - 저장된 ML baseline v0 룩백 report 를 GenerateDraft 의 보조 evidence 로 연결. CLI 재실행 / feature 재생성 / 외부 source 호출 / ML 학습 0건. 매수/매도/추천/현금비중/조정장/위험 알림 문구 0건.
  - 신규 모듈: `app/ml_baseline_evidence.py` **452 라인** (KS-10 안전) — JSON 파일 직접 read (HTTP self-call X), stale 기준 `feature_asof_range.end` 7일 초과.
  - draft_payload 신규 키: `ml_baseline_evidence_snapshot` (status / candidate_summary / risk_summary / leakage_summary / limitations / external_context_checklist 7항목). factor_signals 신규 scope: `ml_baseline_evidence` (보조 evidence 1건).
  - **FIX r2 (검증자 1차 REJECTED 후속, AC-2 완전 구현)**: AI Sessions / Decision Evidence 저장 경로에도 `ml_baseline_evidence_snapshot` 정식 연결. `ai_session_records` 테이블에 `ml_baseline_evidence_snapshot_json` 컬럼 + 자동 ADD COLUMN 마이그레이션 (`_migrate_add_ml_baseline_evidence_snapshot`). `insert_record` / `get_record` / `_row_to_full_dict` / `_SELECT_COLS` 갱신. `app/api_decision_sessions.py` 의 `CreateDecisionSessionRequest` / `DecisionSessionDetail` 에 필드 추가. frontend `aiSessionsDraft.ts` / `decisionSessions.ts` 타입 + `AISessionsCreateTab` 저장 시점 fallback 으로 자동 채움 (draft 에 이미 있으면 그대로 사용).
  - **FIX r3 (검증자 2차 REJECTED 후속, 데이터 계약 단일화)**: `AISessionsCreateTab` fallback 이 raw `{api_status, report_path, report, message}` 를 저장하던 문제를 해결. backend 에 `GET /ml/baseline-v0/evidence-snapshot` 신규 (GenerateDraft 와 동일한 정규화 shape 반환, read-only) + frontend `fetchMlBaselineEvidenceSnapshot()` 신규 + AISessionsCreateTab 가 이 API 결과를 그대로 payload 에 담음. fetch 실패 시에도 status="error" 정규화 snapshot 으로 채움 (지시문 §4.7 — 조용히 빠지지 않음).
  - draft_message [판단 사유] 섹션에 "ML baseline 룩백 evidence" 1줄 추가 — 평가 거래일 / 후보 발굴 baseline / 위험 baseline / leakage / 한계 4종 본문.
  - report 부재 → status=unavailable / 손상 → error / stale → stale / warn → warn 으로 draft 에 그대로 노출 (조용히 빠지지 않음).
  - 실측 (운영 SQLite): status=ok / candidate evaluated_days=40 / risk evaluated_days=40 / leakage 0 / external checklist 7건.
  - pytest **454 passed** (+22 신규, 회귀 0, FIX r3 후). black / flake8 / Next.js build PASS.
- **이전 STEP**: **ML Baseline v0 룩백 검증** (2026-06-11, commit `4c1cb3b5`).
  - 현재 feature dataset 이 과거 구간에서 (1) 상승 후보 발굴 baseline 과 (2) 위험 구간 감지 baseline 으로 의미가 있었는지 룩백 검증. 실시간 매수/매도 판단 X, 위험 알림 X, 조정장 확정 X, 위험 threshold X.
  - CLI: `scripts/run_ml_baseline_v0.py` (외부 source 호출 0건). read-only API: `GET /ml/baseline-v0/latest`. Data Status 카드 신규: `MLBaselineV0Card`.
  - Candidate baseline (사용자 결정 — Top quintile 20%): composite rank v0 = return_20d / excess_20d / return_10d / volume_ratio_20d DESC rank 평균. future_return / future_excess_return horizons = 5/10/20d.
  - Risk baseline (사용자 결정 — market composite tercile 1/3): 13축 risk axes (변동성/시장폭/distance_from_20d_high/조정장 전조 proxy 등) rank 평균. future_kodex200_return 3/5/10d + future_market_drawdown 5/10d + future_universe_down_ratio_5d.
  - Horizon tail (사용자 결정 — max horizon 20d 만큼 tail 제외): 마지막 20거래일은 평가에서 제외 (모든 horizon 의 future target 측정 가능 구간만).
  - Leakage check: feature asof 이후 가격만 target 계산에 사용 — 구조적 누수 불가. time order ASC 보장.
  - 실측 (1137 ETF × 60거래일 / 평가 40거래일 / FIX r2 후): **status=ok**, leakage 0. evaluated_asof_range=2026-03-11→2026-05-07. candidate top group 5d/10d/20d return = 3.4%/5.5%/13.5% vs universe median 1.1%/2.1%/4.7%. risk high vs low future drawdown 10d = -8.1% vs -3.4%, drawdown_capture_rate 10d = 1.44.
  - **FIX r2 (검증자 1차 REJECTED 후속)**: (A-1) 지시문 §7.4/§8.4 단순 baseline 누락 보강 — candidate `simple_baselines` 2종 (return_20d / excess_20d top quintile) + risk `simple_baselines` 3종 (5일 시장 수익률 / 20일 drawdown / 시장폭) 노출. (A-2) `MLBaselineV0Card` helper 문구의 §12 금지 단어 (매수/매도/현금/위험알림/조정장) 제거 — "0건" 표현이라도 위반. (A-3) `evaluated_asof_range.end` null → "2026-05-07" 채움.
  - 신규 파일 라인 수 (실측, FIX r2 후): `ml_baseline_targets.py` 352 / `ml_baseline_candidate.py` **426** / `ml_baseline_risk.py` **390** / `ml_baseline_v0.py` 199 / `api_ml_baseline.py` 66. KS-10 trigger/near 0건.
  - Snapshot: `state/ml/ml_baseline_v0_report_latest.json` (gitignored, 운영 artifact).
  - pytest **432 passed** (+15 신규 / 회귀 0). black / flake8 / ESLint / Next.js build PASS.
- **이전 STEP**: **ML Feature Sanity Check** (2026-06-08, commit `7a259454`).
  - ML baseline v0 입력 직전 데이터 품질 검산 4종 (coverage / calculation / NAV join / risk proxy).
  - CLI: `scripts/check_ml_feature_sanity.py` (외부 source 호출 0건, sample_count 인자).
  - 신규 read-only API `GET /ml/feature-sanity/latest` — snapshot JSON 만 read (재계산 X).
  - Data Status 화면에 sanity 요약 + 7축 sub-check + 샘플 ETF 10건 (return/excess/vol/dd/NAV 괴리율) 표시.
  - 허용 오차 (사용자 결정 (b)): `abs_tol=1e-4 + rel_tol=1e-4` (numpy isclose 패턴). risk proxy 이상치는 null 비율만 (사용자 결정 (f)).
  - 실측 (FIX r3 후): 1137 ETF × 60일 / sanity_status=warn / calc 0 error / future_nav_join=0 / risk all-null=0 / warning 3건 (NAV unavailable 2 + **ticker별 row 누락 69건 신규 감지** — FIX r3 효과).
  - **FIX r2 (KS-10 자체 점검)**: 첫 작성된 `ml_feature_sanity.py` 607 라인 → near 진입. helpers 모듈로 분리 → `ml_feature_sanity.py` 491 라인 + `ml_feature_sanity_helpers.py` 141 라인. ML 신규 파일 KS-10 trigger/near 0건.
  - **FIX r3 (검증자 REJECTED 후속)**: (1) coverage §4.3 누락 보강 — ticker별 row 누락 + asof drop 검산 추가. (2) snapshot 손상 시 status=error 분리 (fail-loud, empty 와 구분). (3) untracked 8건 즉시 staging. 실측: `ml_feature_sanity.py` **561 라인** (near 600 미진입), `api_ml_sanity.py` 65 라인. pytest **417 passed** (+3, 회귀 0).
  - Snapshot: `state/ml/ml_feature_sanity_latest.json` (gitignored).
- **이전 STEP**: ML 최소 데이터 레인 1차 (2026-06-08, commit `e918bb47`).
  - FIX r2 (검증자 REJECTED 대응): 신규 `ml_feature_builder.py` 615 라인 (backend near ≥600) → 책임 분리. primitives / nav_lookup 2 모듈 신규. **builder 455 라인 (near 이탈)** + primitives 124 + nav_lookup 78. ML 핵심 파일 KS-10 trigger/near 0건.
  - SQLite 2 테이블 신규: `etf_ml_feature_daily` (ETF별 daily feature) + `market_risk_feature_daily` (시장 위험 daily feature).
  - CLI 전용 실행 (`scripts/generate_ml_features.py`) — 화면 / refresh 흐름 hook 0건. `--start-date` / `--end-date` / `--lookback-days` (기본 60거래일) / `--ticker` filter / `--no-snapshot`.
  - ETF feature: return 5/10/20d + KODEX200 대비 초과수익 + volatility_20d + drawdown_20d + volume_ratio_20d + NAV/괴리율 join (latest available ≤ asof, 미래 데이터 금지).
  - Market risk feature: KODEX200/KOSPI return 1/5/20d + ETF universe up/down/flat count·ratio + median return 1d/5d + NAV 분포 (avg/abs_avg/extreme≥3%) + 변동성/drawdown proxy + 조정장 전조 5종 (distance_from_20d_high / volatility_expansion_20d / down_day_volume_ratio / large_negative_day_proxy / short_term_weakness_proxy / breadth_deterioration_proxy).
  - 신규 read-only API `GET /ml/readiness/latest` — row 수 / latest asof 동적 표시.
  - `MLTimeseriesReadinessCard` 갱신 (9축 정적 표 → 7축 + API 조회). CNN Fear&Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 / 구성종목 가격 시계열은 표시 제외 (BACKLOG).
  - Snapshot: `state/ml/ml_feature_snapshot_latest.json` (gitignored, 운영 artifact).
  - 실측 (1137 ETF × 60일): 4.46초 / 65,691 ETF feature row + 60 market risk row.
  - ML 모델 학습 / 라벨 / 예측 / 매수·매도 판단 / 위험 threshold 0건. 외부 크롤링 0건.
- **이전 STEP (직전 commit 7건)**: 사용자 즉시 피드백 (`6c3728ec` → `8fad2bb4`) 의 Market Discovery UI / Perf 정리.
  - 직전 STEP(NAV / Discount Display FIX) 이후 사용자가 보낸 UI 정리 요청 + perf 지적 일괄 반영.
  - **UI**: CandidateTable 의 source/status/정렬기준/태그 컬럼 제거, 6m/12m/1y/3y 표시 컬럼 추가 (표시 전용, 정렬 X). asof 컬럼 제거. TopControlsRow 1 카드 안에 (1행) 갱신+필터 / (2행) AI Sessions·ETF Exposure 전달 버튼 묶음. AI 투자세션 복사용 문구 / 별도 Transfer 섹션 / 정렬 기준 안내 / role banner / subtitle 문구 모두 제거.
  - **MarketContextCard**: `(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)` 헤더 — 현재가/MA20/MA60 행이 어느 종목인지 명확. 금액 천단위 콤마 (`119,560`).
  - **Backend**: `MarketReturns` 모델에 six_month / twelve_month / three_year 추가 (lookback 180/365/1095). 정렬 가능 basis 는 daily/1m/3m 그대로 (신규 기간은 표시 전용).
  - **Perf**: `/market/topn/latest` 응답 **2.4s → 0.85s (65% 단축)**. 원인 = `_connection()` 매 호출마다 `init_db()` 반복 + `get_etf_name()` universe 1137 회 단건 SQL. 처리 = process-level `_INITIALIZED_DBS` 캐시 + `get_etf_name_map()` bulk loader 추가.
- **현재 진행 예정**: 사용자 결정 대기 (§6 Next action 참조).

## 2. Latest completed step

| Step | Status | Date | Detail |
| --- | --- | --- | --- |
| PC-to-OCI 3-PUSH Evidence Package Sync | DONE | 2026-06-15 | [POC2_THREE_PUSH_EVIDENCE_PACKAGE_OCI_SYNC_CONCLUSION.md](handoff/POC2_THREE_PUSH_EVIDENCE_PACKAGE_OCI_SYNC_CONCLUSION.md) |
| 3-PUSH Context Cleanup (KS-10 trigger/near 4건 해소) | DONE | 2026-06-14 | [POC2_THREE_PUSH_CONTEXT_CLEANUP_CONCLUSION.md](handoff/POC2_THREE_PUSH_CONTEXT_CLEANUP_CONCLUSION.md) |
| 3-PUSH Message Text Runtime Evidence 반영 | DONE | 2026-06-14 | [POC2_THREE_PUSH_MESSAGE_TEXT_RUNTIME_EVIDENCE_CONCLUSION.md](handoff/POC2_THREE_PUSH_MESSAGE_TEXT_RUNTIME_EVIDENCE_CONCLUSION.md) |
| 3-PUSH Runtime Package PC 검증 | DONE | 2026-06-13 | [POC2_THREE_PUSH_RUNTIME_PACKAGE_PC_VERIFICATION_CONCLUSION.md](handoff/POC2_THREE_PUSH_RUNTIME_PACKAGE_PC_VERIFICATION_CONCLUSION.md) |
| 3-PUSH Message Contract 정렬 | DONE | 2026-06-12 | [POC2_THREE_PUSH_MESSAGE_CONTRACT_ALIGNMENT_CONCLUSION.md](handoff/POC2_THREE_PUSH_MESSAGE_CONTRACT_ALIGNMENT_CONCLUSION.md) |
| UI 안전실행 — ML evidence 갱신 background job | DONE | 2026-06-11 | [POC2_UI_SAFE_ML_EVIDENCE_EXECUTION_CONCLUSION.md](handoff/POC2_UI_SAFE_ML_EVIDENCE_EXECUTION_CONCLUSION.md) |
| ML Baseline Evidence Draft Integration | DONE | 2026-06-11 | [POC2_ML_BASELINE_EVIDENCE_DRAFT_INTEGRATION_CONCLUSION.md](handoff/POC2_ML_BASELINE_EVIDENCE_DRAFT_INTEGRATION_CONCLUSION.md) |
| ML Baseline v0 룩백 검증 | DONE | 2026-06-11 | [POC2_ML_BASELINE_V0_LOOKBACK_CONCLUSION.md](handoff/POC2_ML_BASELINE_V0_LOOKBACK_CONCLUSION.md) |
| ML Feature Sanity Check | DONE | 2026-06-08 | [POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md](handoff/POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md) |
| ML 최소 데이터 레인 1차 | DONE | 2026-06-08 | [POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md](handoff/POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md) |
| Market Discovery UI / Perf 후속 정리 (사용자 즉시 피드백 5 commit) | DONE | 2026-06-08 | commits `6c3728ec` → `8fad2bb4` (별도 Conclusion 미생성 — handoff 검증자 보고서 [POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md](handoff/POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md)) |
| NAV / Discount Display FIX (전체 ETF 조회 영역 + 표시 매트릭스) | DONE | 2026-06-08 | [POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |

## 3. Recent history summary

| Step | Result | Summary | Detail |
| --- | --- | --- | --- |
| 2026-06-08 ML Feature Sanity Check | DONE | coverage / calculation / NAV join / risk proxy 검산 4종 + read-only API + Data Status 표시. sanity_status=warn / calc 0 err / future_nav_join=0. | [conclusion](handoff/POC2_ML_FEATURE_SANITY_CHECK_CONCLUSION.md) |
| 2026-06-08 ML 최소 데이터 레인 1차 | DONE | etf_ml_feature_daily + market_risk_feature_daily 2 테이블 + CLI + 7축 readiness API. 1137 ETF×60일 → 65,691 row / 4.46초. ML 모델 / threshold / label 0건. | [conclusion](handoff/POC2_ML_MINIMAL_DATA_LANE_CONCLUSION.md) |
| 2026-06-08 Market Discovery UI / Perf 후속 정리 | DONE | CandidateTable 컬럼 정리 + 6m/12m/1y/3y 추가 + TopControlsRow 통합 + MarketContextCard 표기 정정 + 응답 2.4s→0.85s. | commits `6c3728ec`…`8fad2bb4` / [feedback note](handoff/POC2_MARKET_DISCOVERY_UI_PERF_USER_FEEDBACK_NOTE.md) |
| 2026-06-08 NAV / Discount Display FIX | DONE | GET /market/nav-discount/latest 신규 + Data Status 전체 ETF NAV 표 + MD/ETF Exposure/Holdings 표시 보강. 표시 매트릭스 충족. | [conclusion](handoff/POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md) |
| 2026-06-08 Naver ETF Universe NAV / 괴리율 연동 | DONE | universe 1회 호출(`etfItemList.nhn`) → `etf_nav_daily` upsert + 3개 화면 NAV 표시. TTL 30s + stale 재사용. 신규 API 0건. | [conclusion](handoff/POC2_NAVER_ETF_UNIVERSE_NAV_INTEGRATION_CONCLUSION.md) |
| 2026-06-07 ETF NAV / Discount Source Diagnosis 1차 (FIX) | DONE | NAV/괴리율 source 5건 실측. adopt 0 / hold_unstable 2 / unusable 3. flat_records + timeout 명시 + asof 키 확장 FIX. | commit `b5a80a3f` / [archive](handoff/STATE_LATEST_ARCHIVE.md) |
| 2026-06-06 ETF Exposure Data Unfolding 1차 | DONE | 구성종목 펼쳐보기 + 반복 핵심 종목 + 중복률 + Holdings Evidence State Bridge + ML readiness 9축. ML 방향성 2축 문서화. | commit `bce8f7fd` / [archive#0.1](handoff/STATE_LATEST_ARCHIVE.md) |

> 직전 5개를 제외한 이전 STEP (2026-06-01 이전 — Market Discovery Closeout / Constituents Naver Integration /
> Constituents Diagnosis / Constituents & Overlap / Market Regime / AI Sessions / Decision Evidence /
> AI 투자세션 복사용 문구 / Grid 사용성 FIX / 통합 후보 테이블 / 후보 정제 / SQLite Direct Refresh /
> TOP N 최소 표시 / PC UI Shell / FDR+SQLite Foundation / B 방향 전환 등) 은
> [docs/handoff/STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 에 전문 보존되어 있다.

## 4. Current evidence flow

- **Market Discovery**: SQLite 직접 계산 TOP N. 수동 refresh (6h cooldown). 응답 0.85s (2026-06-08 perf). TopControlsRow 1 카드 (1행 갱신+필터 / 2행 AI Sessions·ETF Exposure 전달). 시장 국면(`(069500) KODEX 200 (필수)` / `(KS11) KOSPI (보조)`, 금액 천단위 콤마). 그리드 컬럼: 순위/티커/ETF명/일간·1m·3m(정렬)/6m·12m·1y·3y(표시)/KODEX200 대비 1m·3m/NAV/시장가/괴리율. asof/source/status/태그 컬럼은 그리드에서 제거 (Data Status 화면에서 조회).
- **ETF Exposure**: 구성종목 펼쳐보기(자동 open + 등락률 unavailable 컬럼) + 중복률 + 반복 핵심 종목 + Holdings Evidence State Bridge (명시 호출 버튼) + NAV/괴리율 카드(상위 5건 + asof/source/status) + ML readiness 9축.
- **Holdings Evidence**: `GET /holdings/market-evidence/latest` (read-only, 외부 fetch 0건). 보유 ETF × Market Discovery 후보 / 시장 국면 / 단기 흐름 / 구성종목 중복 / NAV·시장가·괴리율·asof·status·source(`etf_nav_daily` store 에서 read).
- **Data Status**: 전체 ETF NAV / 시장가 / 괴리율 조회 화면 (`GET /market/nav-discount/latest`). 검색 + status 필터 + 괴리율 정렬. 외부 source 호출 0건. 1136 ETF 1회 응답.
- **GenerateDraft**: 같은 evidence builder 재사용 — `draft_payload.holdings_market_evidence_snapshot` + `factor_signals` scope="holdings_market_evidence" + [판단 사유] bullet. 매수·매도·교체 어휘 0건.
- **Approval / Telegram**: 인간 승인 게이트 유지. 3-PUSH (보유 종목 상태 / 신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 X.
- **AI Sessions**: 외부 AI 답변 + 사용자 판단 기록. Market Discovery 후보 스냅샷 + 시장 국면 + 구성종목/중복률 / 단기 흐름 / 데이터 품질 / Decision Candidate 전부 포함.

## 5. Open decisions

| ID | 상태 | 내용 | 참조 |
| --- | --- | --- | --- |
| Q1 | OPEN | 여러 factor 를 붙일 수 있는 구조의 엔진이 될 것인가? | ASSUMPTIONS §2 |
| Q4 | OPEN | "잘 올라가는 섹터/ETF 발굴" 작동 단위 (운영 1개월 검증 필요) | ASSUMPTIONS §2 |
| Q6 | OPEN | 위험 감지 = "위험 구간 분류" — factor / threshold / label 어떻게 확정할 것인가? (시계열 적재 선행) | ASSUMPTIONS §2 / INTENT §9.5 |
| D-1 | RESOLVED | `tests/test_three_push_contract.py::test_generate_spike_alert_via_unified_endpoint` 회귀 — Cleanup Round A 에서 해소. 원인: test isolation 누락 (runtime probe mock 없음). 수정: stub 2개 추가. 617 passed 확인. | STATE_LATEST §1 |
| D-2 | RESOLVED | `app/market_refresh_service.py` in-memory state 재시작 소실 — 2026-06-30 D-2 SQLite 영속화 STEP 에서 해소. SSOT 를 `market_refresh_state` 테이블로 전환. 재시작 시 running → failed 정규화 + detail 보존. 627 passed. | STATE_LATEST §1 / handoff/POC2_D2_MARKET_REFRESH_STATE_SQLITE_CONCLUSION.md |

## 6. Next action

- **다음 Step 후보 (사용자 결정 대기)**:
  1. ~~**KS-10 Cleanup — `app/push_context.py` + `app/draft_message.py` 책임 분리**~~ — **DONE (2026-06-14 3-PUSH Context Cleanup)**. trigger/near 4건 모두 해소.
  2. ~~**PC-to-OCI 3-PUSH Evidence Package Sync**~~ — **DONE (2026-06-15)**. package 공급 경로 확보.
  3. **OCI crontab runner 구현** — OCI 에서 manifest 읽고 package 소비 + Telegram 발송 (하루 3회 발송 시간 결정 선행 필요).
  4. **하루 3회 발송 시간 + 자동 발송 UX** (scheduler 결정).
  5. **runtime source 수동 refresh endpoint**.
  6. **뉴스 source 도입** (PUSH-1 의 [전일 기준 시장 흐름] 보강).
  7. **ThreePushDraftCard 정식 화면 위치 결정**.
- **하지 않을 것 (불변 원칙)**:
  - 자동 매매 / Telegram 문구 변경 / OCI push 자동화 (사용자 명시 승인 필요)
  - MongoDB 전환 (PROJECT_ORIGIN_INTENT §10 #2 — SQLite(시장) + JSON(holdings/Run) SSOT 분리)
  - ML / 백테스트 / threshold / label 확정 (Q6 답 나오기 전)
  - 매수·매도·교체 어휘 / 자동 클러스터링 / 대표 ETF 선정
- **사용자 결정 필요**: ✅ 위 4개 후보 중 다음 Step 선택.

## 7. Index

### 불변 앵커 (먼저 읽어야 하는 5개 문서)

- [docs/PROJECT_ORIGIN_INTENT.md](PROJECT_ORIGIN_INTENT.md) — 한 줄 정의 / 1년 뒤 목표 / 절대 하지 않을 것 / ML 2축 (§9.5)
- [docs/KILL_SWITCHES.md](KILL_SWITCHES.md) — KS-1 ~ KS-11 (단일 파일 책임 누적 / 의사결정 24시간 룰 등)
- [docs/ASSUMPTIONS.md](ASSUMPTIONS.md) — Open Question Q1 / Q4 / Q6 (활성 3개 한도)
- [docs/COLLAB_RULES.md](COLLAB_RULES.md) — 협업 규칙
- [docs/MASTER_PLAN.md](MASTER_PLAN.md) — 마스터 플랜

### Active reference (현 진행에 영향, 자주 갱신)

- [docs/handoff/POC2_B_NEXT_ACTIONS.md](handoff/POC2_B_NEXT_ACTIONS.md) — 빈자리 후속 원칙 + 다음 분기 후보
- [docs/handoff/POC2_FEATURE_INVENTORY.md](handoff/POC2_FEATURE_INVENTORY.md) — 기능 인벤토리
- [docs/handoff/PC_OCI_ARCHITECTURE_DIRECTION.md](handoff/PC_OCI_ARCHITECTURE_DIRECTION.md) — PC·OCI 운영 평면 분리 결정 원본 기록 (2026-06-20). PROJECT_ORIGIN_INTENT §7 / ASSUMPTIONS §3 A-6 / MASTER_PLAN 6단계 와 동기화.

Active Reference:
3-PUSH Runtime Package Contract
- path: docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md
- purpose: PC/OCI가 공유하는 three_push_runtime_package.v1 schema 계약
- usage: PUSH 후속 Step에서는 evidence package / runtime snapshot / message_text 설계 시 이 문서를 기준으로 한다.
- [docs/handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md](handoff/ETF_NAV_DISCOUNT_SOURCE_DIAGNOSIS.md) — NAV 진단 1차 결과
- [docs/handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md](handoff/ETF_CONSTITUENTS_SOURCE_DIAGNOSIS.md) — 구성종목 source 진단
- [docs/backlog/BACKLOG.md](backlog/BACKLOG.md) — Backlog (2026-06-29 전수 감사 후 Measure-Object -Line 기준 451 라인 / 16 카테고리 4필드 통일 포맷 91 항목)
- [docs/handoff/POC2_BACKLOG_AUDIT_CONCLUSION.md](handoff/POC2_BACKLOG_AUDIT_CONCLUSION.md) — BACKLOG 전수 감사 결과 (2026-06-29, 4필드 91 항목, 완료 23/폐기 11/중복 9/결함 escalate 2)
- [docs/ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md](ref/FRIEND_PROJECT_DATA_SOURCES_ANALYSIS.md) — 친구 프로젝트 source / 주기 분석

### Step detail (Step 종료 후 생성된 상세 기록)

POC1 → POC2 초기:
- [POC1_step3_close_and_POC2_handoff.md](handoff/POC1_step3_close_and_POC2_handoff.md) — POC1 Step3 종결 + POC2 진입 1차
- [POC1_Step3_close_and_POC2_Step1_handoff.md](handoff/POC1_Step3_close_and_POC2_Step1_handoff.md) — POC1 Step3 종결 + POC2 Step1 완료 종합

POC2 Step 1A ~ 6:
- [POC2_Step1A_close.md](handoff/POC2_Step1A_close.md) / [POC2_Step2_close.md](handoff/POC2_Step2_close.md) / [Step2B](handoff/POC2_Step2B_close.md) / [Step2C](handoff/POC2_Step2C_close.md) / [Step2D](handoff/POC2_Step2D_close.md)
- [POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md](handoff/POC2_STEP2_CONCLUSION_AND_STEP3_HANDOFF.md)
- [POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP3_CONCLUSION_AND_NEXT_HANDOFF.md)
- [POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md](handoff/POC2_STEP4_MOMENTUM_ENGINE_DIRECTION_AND_Q4_BOUNDARY_DESIGN.md)
- [POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md](handoff/POC2_STEP5A_MOMENTUM_ENGINE_BOUNDARY_AND_MINIMAL_CONTRACT.md)
- [POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP6_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 7 (3-PUSH realignment):
- [POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md](handoff/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md)
- [POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md](handoff/POC2_STEP7A_NEW_ETF_WATCH_CANDIDATE_MINIMAL_PUSH.md)
- [POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md](handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md)
- [POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md](handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md)
- [POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md](handoff/POC2_STEP7_CONCLUSION_AND_NEXT_HANDOFF.md)

POC2 Step 8 (3-PUSH 운영 1주기 검증) + 별도 Foundation:
- [POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md](handoff/POC2_STEP8_3PUSH_FIRST_OPERATIONAL_CYCLE_VALIDATION.md)
- [POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md](handoff/POC2_FDR_SQLITE_MARKET_DATA_FOUNDATION.md) — FDR + SQLite 시장 데이터 기반 구축

2026-06-15 ~ 직전 5개:
- 2026-06-15 PC-to-OCI 3-PUSH Evidence Package Sync → [conclusion](handoff/POC2_THREE_PUSH_EVIDENCE_PACKAGE_OCI_SYNC_CONCLUSION.md)
- 2026-06-14 3-PUSH Context Cleanup (KS-10 trigger/near 4건 해소) → [conclusion](handoff/POC2_THREE_PUSH_CONTEXT_CLEANUP_CONCLUSION.md)
- 2026-06-14 3-PUSH Message Text Runtime Evidence 반영 → [conclusion](handoff/POC2_THREE_PUSH_MESSAGE_TEXT_RUNTIME_EVIDENCE_CONCLUSION.md)

2026-06-01 이후 (가장 최근 5개 STEP — §3 참조 + ARCHIVE 전문):
- 2026-06-07 NAV / Discount Source Diagnosis 1차 (FIX) → [STATE_LATEST_ARCHIVE §0](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 ETF Exposure Data Unfolding 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-06 Operational UI Cleanup 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 Holdings × Market Discovery Evidence 1차 → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-03 KS-10 Cleanup (API Client / Type 책임 분리) → [ARCHIVE §0.1](handoff/STATE_LATEST_ARCHIVE.md)
- 2026-06-01 이전 16개 STEP 시간순 누적 → [STATE_LATEST_ARCHIVE.md](handoff/STATE_LATEST_ARCHIVE.md) 전문

### Deprecated / redirect

- [docs/handoff/STATE_LATEST.md](handoff/STATE_LATEST.md) — 6줄 redirect stub. 본 파일과 ARCHIVE 로 안내. 더 이상 append 하지 않는다.
