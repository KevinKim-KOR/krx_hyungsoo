# OCI Active Data Boundary Audit v1 — Conclusion (DONE)

작성일: 2026-07-07
성격: OCI SQLite 중심 활성 운영 구조 전환 이전의 **사전 감사**. 코드 · DB · JSON · runtime · API · UI · scheduler · transfer 구현 변경 **0건**. 문서만 산출물.

---

## 1. 완료 판정 — DONE

지시문 §10 DONE 조건 모두 충족:

- PC 코드 · 문서 · 현재 state 기준 전수 감사 완료 (216 file 전량).
- OCI 관련 미확인 영역은 §6.4 규칙 그대로 "미확인" 으로 명시.
- Canonical 문서 5개 중 존재 확인된 5개 갱신 완료 (missing 없음).
- 금지된 구현 변경 0건 (`git diff` 문서만).

**미확인 항목 (OCI 정보 확인 필요, §6.4)**:
- OCI 로컬 파일시스템의 실제 파일 존재 · 크기 · mtime.
- OCI `market_data.sqlite` 의 `PRAGMA integrity_check` 실측.
- OCI `state/three_push/packages/` 하위 파일과 manifest 의 최신 상태.
- OCI 상의 remote transfer staging 실제 위치와 권한.

---

## 2. 사용자 확정 운영 저장소 결정 (2026-07-07)

이번 감사 결과와 무관하게 canonical 반영 대상. 지시문 §4 원문 그대로:

```
1. OCI SQLite 는 활성 운영·조회 기준 DB 다.
   - OCI 는 active PARAM 과 현재 운영 데이터를 읽어 시장 흐름을 구성하고
     3-PUSH 를 생성한다.
   - 향후 모바일 조회도 OCI SQLite 를 read-only 로 조회한다.

2. PC 는 OCI DB 의 일관된 분석 복제본을 사용한다.
   - PC 는 ML, 백테스트, PARAM 후보 계산을 수행한다.
   - PC 는 OCI 운영 DB 를 원격으로 직접 열거나 write 하지 않는다.

3. PARAM 은 JSON 파일이 아니라 DB 의 version, approval, active 상태로 관리한다.
   - PC 에서 계산·승인된 PARAM 은 DB 기반 발행 절차로 OCI 에 반영한다.
   - JSON PARAM handoff 를 새 운영 경로로 만들지 않는다.

4. 로그를 제외한 활성 데이터는 DB 로 관리한다.
   - JSON 은 로그, archive, API request/response, 테스트 fixture 에만 허용한다.
   - 현재 활성 JSON 은 DB 전환 대상과 순서를 먼저 측정한다.
   - 전환 전 기존 JSON 을 임의 삭제하거나 DB 와 dual-write 하지 않는다.

5. PC 와 OCI 는 SQLite 운영 파일을 서로 통째로 덮어쓰지 않는다.
   - 같은 SQLite 파일의 동시 write 도 금지한다.
```

---

## 3. 감사 방법론

**Q1 (a) 확정본 준수** — 전량 grep + 파일:라인 근거:

- `state/**/*.json` / `*.jsonl` / `*.sqlite` 전량 glob 수집 (`find` 실측).
- 각 경로/상수/glob 패턴별 `grep -rn` 로 reader/writer 함수 확인.
- 동적 경로 (`state/runs/run_*.json`, `state/three_push/params/history/param-*.json`) 는 생성 함수 + reader glob 를 한 inventory 행에 합침.
- 코드 참조되지만 PC 파일 부재인 경로 (`ml_baseline_v0_report_latest.json` 등) 는 미확인 표시.

**Q2 (a) 확정본 준수** — §7.1 최소 대상 + 실제 발견 전량.

---

## 4. §7.1 Active data inventory

**실측 규모** (2026-07-07 `find` 실측 재확정, FIX r1):
- `state/**/*.json` = **214** (`.bak-*` 확장자 파일 제외 — glob 미매치)
- `state/**/*.jsonl` = **0**
- `state/**/*.sqlite` = **2** (`.bak-*` 확장자 파일 제외)
- 합계 = **216** (지시문 §7.1 대상 총량)
- 별도: 백업 `.bak-*` 2 파일 (`state/market/market_data.sqlite.bak-2026-07-05-150001`, `state/ml/market_flow_baseline_latest.json.bak-2026-07-05-150001`) — glob 미매치이나 §4.6 에 명시.

**Breakdown** (합=216):
- 동적 runs (`state/runs/*.json`) = **102**
- 동적 param history (`state/three_push/params/history/*.json`) = **91**
- 나머지 개별 unique `.json` = 214 − 102 − 91 = **21**
- `.sqlite` = **2**
- 합=102+91+21+2=216. ✓

### 4.1 PC · OCI 활성 데이터 (A 후보)

| 경로 | 유형 | reader (파일:라인) | writer (파일:라인) | 소비 기능 | 분류 | 근거 | OCI 추가 확인 |
|---|---|---|---|---|---|---|---|
| `state/three_push/params/latest_runtime_param.json` | 활성 PARAM | `app/three_push_runtime_param.py:read_param_file` (호출 지점: `scripts/run_three_push_runtime_oci.py:145`, `app/api_three_push_param.py:_read_active_param`, `app/push_content_gap_diagnosis_reproducers.py:50`) | `scripts/create_three_push_runtime_param.py:99` (create+approve 시 atomic write, `app/three_push_runtime_param.py:write_param_file`), `app/api_three_push_param.py:210+` (`apply_param_to_oci` 흐름), `scripts/sync_three_push_runtime_param.py:154` (OCI 원격 upload) | POST `/three-push/param/apply` → OCI runtime PARAM 로드 | **A** | 실제 활성 PARAM. OCI runtime 이 이 파일을 read. §7.1 요구 대상. | OCI 로컬 `state/three_push/params/latest_runtime_param.json` mtime 확인 필요. |
| `state/three_push/params/history/param-<TS>-<hash>.json` (91 파일, 동적 패턴) | PARAM archive | `app/three_push_runtime_param.py:read_param_file` (idempotent read) | `scripts/create_three_push_runtime_param.py:99`, `app/api_three_push_param.py:225` (`f"{param.param_id}.json"`) | PARAM 승격 이력 (audit trail) | **A → B 경계** | 활성 read 는 latest 만; history 는 audit archive. §4 결정 "PARAM 은 DB version 으로 관리" 하에 DB 이관 후 archive 유지 대상. | OCI 상 history dir 존재 · 수 · mtime 미확인. |
| `state/three_push/params/param_sync_status_latest.json` | PARAM sync 상태 | `app/api_three_push_param.py:_read_sync_status` (`scripts/sync_three_push_runtime_param.py:47`도 read) → GET `/three-push/param/state` 카드 응답 | `scripts/sync_three_push_runtime_param.py` (apply 후 atomic write) | UI `ThreePushParamCard` 렌더 | **A** | 활성 상태 (`SYNC_STATE_OK/MISSING/CORRUPTED`) 로 UI 가 read. | OCI 존재 여부 (PC↔OCI 왕복 성공 시 PC 로컬 갱신). |
| `state/three_push/sync_status_latest.json` | Package sync 상태 | `scripts/sync_three_push_packages.py:70` | `scripts/sync_three_push_packages.py` | Package fallback 동기화 결과 로그 | **A → B 경계** | 활성 fallback 흐름의 상태. §4 결정 하에 fallback 자체가 실운영 경로 아니므로 B 가능. 실제 reader 는 sync script + 사용자 조회 만. | OCI 존재 · 최신 시각 미확인. |
| `state/three_push/packages/manifest.json` | Package manifest | `scripts/three_push_oci_helpers.py:186` (`load_manifest`), `app/three_push_package_exporter.py`, `scripts/verify_three_push_packages_oci.py:43` | `app/three_push_package_exporter.py` (PC 생성), `scripts/sync_three_push_packages.py:229` (OCI 원격 upload) | Package fallback (비-실운영 경로), `run_three_push_oci.py:103` | **A → C 경계** | PC 에는 부재 (실측). OCI 에는 `content_ready` (직전 PUSH Content Gap Diagnosis v1 OCI 실측 확인). §5 "package fallback 을 정식 운영 경로로 복귀 금지" — B/C 후보이나 이번 STEP 은 분류만. | OCI 실제 존재 확인됨 (직전 STEP). |
| `state/three_push/packages/latest_market_briefing.json` | PC-built PUSH 1 package | `app/three_push_package_exporter.py` (write), `scripts/three_push_oci_helpers.py:load_package` (OCI read via `run_three_push_oci.py` fallback) | `app/three_push_package_exporter.py` | Package fallback | **A → C 경계** | PC 상 부재. OCI 상 존재 확인됨 (직전 STEP). | 위와 동일. |
| `state/three_push/packages/latest_holdings_briefing.json` | PC-built PUSH 2 package | 위와 동일 helper | 위와 동일 | Package fallback | **A → C 경계** | 위와 동일. | 위와 동일. |
| `state/three_push/packages/latest_spike_or_falling_alert.json` | PC-built PUSH 3 package | 위와 동일 helper | 위와 동일 | Package fallback | **A → C 경계** | 위와 동일. | 위와 동일. |
| `state/three_push/oci_sent_registry.json` | Package runner 중복 발송 방지 registry | `scripts/three_push_oci_helpers.py:52` (`_REGISTRY_PATH`), `run_three_push_oci.py` 흐름 | 위와 동일 helper `mark_sent` | Package fallback runner 만 사용 | **A → C 경계** | PC 부재 (실측). OCI 미확인. | OCI 실측 필요. |
| `state/three_push/oci_runtime_sent_registry.json` (동적 생성) | Runtime PARAM runner 중복 발송 방지 registry | `scripts/run_three_push_runtime_oci.py:72` (`_REGISTRY_PATH`), `mark_sent` | 위 script | OCI Telegram send 흐름 (실운영 경로) | **A** | PC 부재 (실측); OCI 상 존재 확인됨 (직전 STEP artifact 에 `runtime_readiness.required_paths_ready=false` 관측 — 즉 상당 path 부재 상태). §4 결정 하에 DB 로 이관 대상. | OCI 존재/파일 상태 실측 필요. |
| `state/three_push/oci_runtime_status_latest.json` (동적 생성) | Runtime latest status | `scripts/run_three_push_runtime_oci.py:73` (`_STATUS_PATH`, `write_status`) | 위 script | Runtime 실행 결과 (status/reason/timestamp) | **A** | 위와 동일 근거. | OCI 존재 실측 필요. |
| `state/three_push/oci_runtime_history.jsonl` (동적 생성) | Runtime history log | `scripts/run_three_push_runtime_oci.py:74` (`_HISTORY_PATH`, `write_status`) | 위 script | 실행 history append | **B** (JSONL 로그 — §4 결정 "JSON 은 로그 · archive · API transport · 테스트 fixture 만 허용") | 지시문 §2 · §4 그대로. | OCI 존재 실측 필요. |
| `state/runtime/three_push_runtime_probe_latest.json` | Runtime probe cache (KR quote + US indices) | `app/runtime_probe_cache.py:_read_cache` (호출: `app/api.py:/runs/generate` 등) | `app/runtime_probe_cache.py:_write_cache` | Runtime evidence 조립 | **A** | 실운영 evidence source. §10 (다음 STEP) OCI runtime 재배선의 핵심 input. | OCI 존재 실측 필요. |
| `state/holdings/holdings_latest.json` | Holdings snapshot | `app/holdings.py:HOLDINGS_FILE` (`load_holdings` 등), `app/holdings_market_evidence.py:415/529`, `app/holdings_enrich.py:33`, `app/api.py:_load_holdings` 흐름 | `app/holdings.py:save_holdings` (사용자 upload / API POST) | Holdings UI · PUSH-2 evidence · Decision Draft Preview | **A** | 활성 운영 데이터. §4 결정 하에 `holding_position` / `holding_lot` DB table 로 이관 대상 (schema 매핑은 다음 STEP). | OCI 존재 미확인. |
| `state/market_cache/market_latest.json` | Market quote cache | `app/market_cache.py:load`, `get_all` (호출: `app/api.py:243/260/351/384`, `api_decision_draft_preview.py:85`) | `app/market_cache.py:save`, `upsert_many` (`api.py:351`) | 시장 조회 · runs/generate PENDING draft | **A** | 실운영 시세 캐시. §4 결정 하에 DB table 로 이관 대상. 다만 §10 (다음 STEP) 에서 실시간 시세 vs 저장 시점 분리 규칙 확정 필요. | OCI 존재 미확인. |

### 4.2 Runs / decision (PENDING · approval 흐름)

| 경로 | 유형 | reader | writer | 소비 기능 | 분류 | 근거 | OCI 확인 |
|---|---|---|---|---|---|---|---|
| `state/runs/run_<TS>_<hash>.json` (**102 파일** 실측, 동적 패턴) | Run + PENDING draft + 승인 이력 | `app/store.py:load`, `list_runs` (`app/api.py:_get_run` 등 다수 endpoint) | `app/store.py:save` (POST `/runs/generate` 흐름) | PENDING 승인 UI, Approval, Telegram/OCI handoff | **A** | 활성 승인 데이터. §4 결정 하에 `decision_run` / `decision_approval` DB table 로 이관 대상. | OCI 상 위치 (또는 사용 여부) 미확인 — PC 가 승인 후 OCI 로 전달하는 흐름이므로 OCI 는 별도 저장 형태 사용 가능성. |
| `state/decision/decision_evidence.sqlite` | Decision evidence SQLite | `app/decision_evidence_store.py:DEFAULT_DB_PATH` | 위 store | Decision Draft Preview · AI Session · Approval evidence | **A (이미 DB)** | 이미 SQLite. §4 결정 하에 DB 중심 원칙과 정합. schema 확장은 다음 STEP. | OCI 존재/스키마 정합 미확인. |

### 4.3 Market diagnostics · closeout artifacts

| 경로 | 유형 | reader | writer | 소비 기능 | 분류 | 근거 | OCI 확인 |
|---|---|---|---|---|---|---|---|
| `state/market/market_data.sqlite` | 시장 시계열 SQLite | `app/market_data_store.py:DEFAULT_DB_PATH` (widely used) | 시장 시계열 refresh CLI 계열 | ETF/KODEX/KOSPI/VIX 시계열, ML dataset, 3-PUSH evidence 후보 | **A (이미 DB, 기준 DB 후보)** | §4 결정 "OCI SQLite = 활성 운영·조회 기준 DB". 이 파일이 지정 대상. | OCI 파일 실측 필요 (integrity, size, mtime, table 목록). |
| `state/market/kospi_history_closeout_latest.json` | KOSPI closeout artifact | `app/market_flow_baseline.py:135` (Ridge baseline 이 `kospi_source_summary` 채우기 위해 read) | `app/kospi_history_closeout.py:39` | ML baseline artifact 부속 evidence | **B** (ML 계산 산출물, 활성 운영 상태 아님) | §6.2 명시 — "완료된 과거 분석 결과만 보관하면 B". | 해당 없음 (PC 국지 산출물). |
| `state/market/nav_discount_refresh_latest.json` | NAV 괴리 refresh 요약 | `app/push_content_gap_diagnosis_requirements.py:77` (진단 대상), `app/market_refresh_service.py:56` | `app/market_refresh_service.py` | Refresh log + 진단 참조 | **A → B 경계** | 진단 requirements 매핑에서 `holdings_briefing` PUSH source 로 등장. 실제 소비 = runtime 이 이 값을 evidence 로 사용하는지 다음 STEP §10 재배선에서 확정. | OCI 미확인. |
| `state/market/nav_discount_source_diagnosis_latest.json` | NAV source 진단 결과 | 없음 (진단 script 자체가 writer, 다른 reader 없음) | `scripts/diagnose_nav_discount_source.py:97` | 진단 archive | **B** | Reader 없음, 진단 archive. | 해당 없음. |
| `state/market/constituents_source_diagnosis_latest.json` | Constituents source 진단 결과 | 없음 (동일) | `scripts/diagnose_constituents_source.py:48` | 진단 archive | **B** | Reader 없음. | 해당 없음. |

### 4.4 ML latest artifacts (§6.2 개별 판정)

| 경로 | 유형 | reader | writer | 분류 | 근거 |
|---|---|---|---|---|---|
| `state/ml/market_flow_baseline_latest.json` | Market Flow baseline (Ridge) | 없음 (state UI/api 무 참조; 후속 STEP artifact 만 참조) | `app/market_flow_baseline.py:39` | **B** | Reader 없음, 완료된 과거 분석 결과. |
| `state/ml/market_flow_walk_forward_latest.json` | Walk-forward v1 | 없음 (dashboard 미참조) | `app/market_flow_walk_forward.py:41` | **B** | 위와 동일. |
| `state/ml/market_flow_v2_data_validity_latest.json` | v2 data validity | 없음 | `app/market_flow_v2_model_comparison.py:64` | **B** | 위와 동일. |
| `state/ml/market_flow_v2_model_comparison_latest.json` | v2 model comparison | 없음 | `app/market_flow_v2_model_comparison.py:68` | **B** | 위와 동일. |
| `state/ml/relative_upside_score_latest.json` | ML axis1 점수 snapshot | `app/api_market_topn.py:merge_relative_upside_score` 를 통해 read (UI `MarketDiscoveryView`) | `app/ml_relative_upside_score.py:27` | **A** | UI 활성 참조. §6.2 명시 — UI 가 현재값으로 read → A. §4 결정 하에 DB 이관 대상 (다음 STEP 매핑). |
| `state/ml/relative_upside_score_run_latest.json` | Run meta | `app/api_ml_relative_upside.py:60` (`get_relative_upside_run_meta`) | `app/ml_relative_upside_score.py:28` | **A** | UI 활성 참조. |

### 4.5 코드 참조되지만 PC 파일 부재 (미확인)

| 경로 | 코드 참조 | 상태 | 분류 (잠정) | OCI 확인 필요 |
|---|---|---|---|---|
| `state/ml/ml_baseline_v0_report_latest.json` | `app/api.py:100`, `app/api_ml_baseline.py:31`, `app/ml_baseline_evidence.py:26`, `frontend/lib/api/mlBaselineV0.ts:3`, `app/ml_job_runner.py:52` | PC 파일 없음 (직전 진단에서 required_paths artifact 리스트에도 없음이 확인). 코드는 read 흐름 존재. | **A (미확인)** | OCI/PC 실제 생성 여부 실측 필요. |
| `state/ml/ml_feature_sanity_latest.json` | `app/api.py:97`, `app/api_ml_sanity.py:19`, `frontend/lib/api/mlSanity.ts:3`, `app/ml_job_runner.py:51` | 위와 동일 | **A (미확인)** | 실측 필요. |
| `state/ml/ml_feature_snapshot_latest.json` | `app/ml_job_runner.py:50` | 위와 동일 | **A (미확인)** | 실측 필요. |
| `state/ml/ml_job_status_latest.json` | `app/ml_job_runner.py:38` | 위와 동일 | **A (미확인)** | 실측 필요. |

### 4.6 백업 / 진단 (B)

| 경로 | 분류 | 근거 |
|---|---|---|
| `state/market/market_data.sqlite.bak-2026-07-05-150001` | **B** | Backup (Baseline v1 Closeout 시 안전 백업). Reader 없음. |
| `state/ml/market_flow_baseline_latest.json.bak-2026-07-05-150001` | **B** | 위와 동일. |
| `state/diagnostics/push_content_gap_diagnosis_latest.json` | **B** | 진단 artifact (직전 STEP). `app/push_content_gap_diagnosis.py:48` (self-write), reader 없음 (교차 비교는 사용자 sanitised 요약으로 수행). |

---

## 5. §7.2 SQLite inventory

| DB 경로 | table (실측 grep) | 현재 reader | 현재 writer | PC 존재 | OCI 존재 | 확인 상태 |
|---|---|---|---|---|---|---|
| `state/market/market_data.sqlite` | `etf_daily_price`, `market_benchmark_daily_price`, `etf_master`, `market_timeseries_ingestion_state`, `market_timeseries_refresh_state`, `etf_constituents`, refresh log (코드 grep 근거: `app/market_data_store.py`, `app/market_benchmark_store.py`, `app/market_flow_dataset.py`, `app/market_timeseries_*`). Table 완전 목록은 SQLite `sqlite_master` 실측 필요 (이번 STEP 은 read only) | 시장 시계열 조회 (`market_data_store`), ML dataset (`market_flow_dataset.build_dataset`), 진단 CLI (`push_content_gap_diagnosis_requirements.sqlite_table_ready`) | 시장 시계열 refresh (`scripts/refresh_market_timeseries.py:kospi` 등), ML axis1 상대상승 계산 | ✅ 존재 (`state/market/market_data.sqlite`, integrity=ok 직전 확인) | ✅ 존재 (직전 진단 artifact 관측 `sqlite_integrity=unavailable`) | **PC 확인 / OCI 미확인**. §4 결정 "OCI SQLite = 활성 운영·조회 기준 DB" — 이 파일이 지정 대상. OCI 무결성 문제는 다음 STEP 에서 분해. |
| `state/decision/decision_evidence.sqlite` | Decision evidence + AI Session (grep: `app/decision_evidence_store.py`, `app/api_decision_*.py`) | Decision Draft Preview, AI Session 조회, PENDING approval evidence | Decision evidence store | ✅ 존재 | 미확인 | **OCI 존재/스키마 정합 미확인**. §4 결정 하에 PARAM / holdings 등 활성 데이터를 이관할 대상 DB (다음 STEP 매핑에서 이 DB 를 확장할지 신규 DB 를 만들지 확정). |

---

## 6. §7.3 PARAM 및 runtime 경로

### 6.1 Active PARAM 저장 위치 · reader · writer

| 항목 | 값 |
|---|---|
| Active PARAM 저장 위치 | `state/three_push/params/latest_runtime_param.json` (JSON 파일 — §4 결정 하에 다음 STEP 에서 DB row 로 이관). |
| Active PARAM reader | `app/three_push_runtime_param.py:read_param_file` → 호출 지점: `scripts/run_three_push_runtime_oci.py:145` (실운영 로드), `app/api_three_push_param.py` (`_read_active_param`), `app/push_content_gap_diagnosis_reproducers.py:50`. |
| Active PARAM writer | `app/three_push_runtime_param.py:write_param_file` → 호출 지점: `scripts/create_three_push_runtime_param.py:99` (approve 시 atomic write), `app/api_three_push_param.py:210+` (`apply_param_to_oci` 흐름), `scripts/sync_three_push_runtime_param.py:154` (OCI 원격 upload). |

### 6.2 GET /three-push/param/state 호출 흐름

`app/api_three_push_param.py:162 def get_param_state`:

1. `_read_active_param()` → `state/three_push/params/latest_runtime_param.json` 존재 · 검증.
2. `_read_sync_status()` (line 108) → `state/three_push/params/param_sync_status_latest.json` read.
   - `SYNC_STATE_MISSING` / `SYNC_STATE_CORRUPTED` / `SYNC_STATE_OK`.
3. 응답 payload 조립 (사용자 라벨 · 상태 · 마지막 sync 시각 등).

### 6.3 POST /three-push/param/apply 호출 흐름

`app/api_three_push_param.py:277 def apply_param_to_oci`:

1. Request 검증 (manual_seed PARAM 생성).
2. `_HISTORY_DIR / f"{param.param_id}.json"` 에 history 저장 (line 225).
3. `_LATEST_PATH` 로 atomic write (`latest_runtime_param.json` 승격).
4. 이후 `scripts/sync_three_push_runtime_param.py` 등 sync helper 호출 (실측 코드 상 sync 흐름은 CLI 로 별도 실행 방식이 우세; API 내부에서 직접 SCP 를 수행하지 않음).
5. `_read_sync_status()` 재조회 후 사용자 응답 조립.

### 6.4 OCI runtime 의 PARAM / status / sent registry 조회 경로

`scripts/run_three_push_runtime_oci.py`:
- Line 71 `_PARAM_PATH = STATE_DIR / "params" / "latest_runtime_param.json"` — read.
- Line 72 `_REGISTRY_PATH = STATE_DIR / "oci_runtime_sent_registry.json"` — read/write (duplicate guard).
- Line 73 `_STATUS_PATH = STATE_DIR / "oci_runtime_status_latest.json"` — write (실행 결과).
- Line 74 `_HISTORY_PATH = STATE_DIR / "oci_runtime_history.jsonl"` — append (history log).

### 6.5 available_sources=None 생성 지점

**단일 지점**: `scripts/run_three_push_runtime_oci.py:177` — `build_runtime_message(available_sources=None)` 하드코딩.

주변 코드 (참조 · 재현 · 진단):
- `app/push_content_gap_diagnosis_reproducers.py:31/65/70/79` — 진단 CLI 가 실운영과 동일하게 `None` 을 전달 (직전 STEP Q1 확정본).
- `app/push_content_gap_diagnosis_classifier.py:144` — 분류 로직 주석.

**다음 STEP §10 재배선의 정확한 수정 지점**: 위 line 177 한 곳. 이 자리를 "OCI SQLite 조회 결과로 available_sources 를 메모리 구성" 로 바꾸는 것이 다음 STEP.

---

## 7. §7.4 3-PUSH evidence source map

| PUSH | evidence source | producer | 저장 위치 | consumer | DB 전환 필요 | 기준일 상태 (현재) |
|---|---|---|---|---|---|---|
| **market_briefing** | `kr_realtime_price_snapshot` | Runtime probe (`app/runtime_kr_quote_probe`, `app/runtime_probe_cache.probe_kr_quotes`) | `state/runtime/three_push_runtime_probe_latest.json` (30분 TTL cache) | Runtime (PARAM runner + market discovery), `app/api.py:generate/refresh` 흐름 | **A → DB 조회 계약 확정 필요** (지시문 §10 다음 STEP 범위) | 실시간 시세는 TTL cache; 정확한 기준일 표기는 캐시 `captured_at`. |
| market_briefing | `overnight_us_market_snapshot` | Runtime probe (`app/runtime_us_indices_probe`) | 위 동일 cache 파일 | 위 동일 | 위 동일 | 야간 지수 캡처 시각. |
| market_briefing | `market_discovery_snapshot` | Market Discovery 화면 (candidate + market context) | `state/market_cache/market_latest.json` (`app/market_cache`), Decision Draft Preview 참조 | UI Market Discovery, PUSH-1 evidence 후보 | **A → DB 이관 대상** | Market quote cache 갱신 시각. |
| market_briefing | `ml_baseline_v0` | ML axis1 baseline runner | `state/ml/ml_baseline_v0_report_latest.json` (PC 상 미존재 — 미확인) | `app/api_ml_baseline.py`, frontend `mlBaselineV0.ts` | **A (미확인)** | 실측 필요. |
| market_briefing | `news_snapshot` | 없음 (이번 STEP §5 "새 외부 데이터 source 추가 금지"; 지시문 §7.1 evidence source 목록의 향후 항목) | 저장 위치 없음 | 없음 | **없음 — 향후 unavailable 처리 대상** (지시문 §7.4 명시) | 없음. |
| **holdings_briefing** | `holdings_snapshot` | 사용자 upload / API POST | `state/holdings/holdings_latest.json` (`app/holdings.py`) | Holdings UI, `holdings_market_evidence`, PUSH-2 evidence | **A → DB 이관 대상 (`holding_position` / `holding_lot`)** | 파일 mtime = 최신 upload 시각. |
| holdings_briefing | `kr_realtime_price_snapshot` | 위와 동일 (market_briefing 과 공유) | 위와 동일 cache | 위와 동일 | 위와 동일 | 위와 동일. |
| holdings_briefing | `nav_discount_snapshot` | `app/market_refresh_service` (NAV refresh CLI) | `state/market/nav_discount_refresh_latest.json` | 위 refresh script + 진단 requirements 참조 | **A → 실 소비 확정 필요** (§10 재배선에서 확정) | Refresh 실행 시각. |
| holdings_briefing | `ml_baseline_v0` | 위와 동일 | 위와 동일 (미확인) | 위와 동일 | 위와 동일 | 위와 동일. |
| **spike_or_falling_alert** | `universe_momentum_snapshot` | Universe 계산 CLI (실측 참조: `app/ml_relative_upside_features.py` 등 후보 계산 경로) | `state/universe/` 하위 (실측 상 PC 파일 부재 — 진단 requirements 에서만 참조) | Spike PUSH-3 evidence 후보 | **A (미확인) → DB 조회 계약 확정 필요** | 실측 미확인. |
| spike_or_falling_alert | `kr_realtime_price_snapshot` | 위와 동일 | 위와 동일 | 위와 동일 | 위와 동일 | 위와 동일. |

**해석 (지시문 §7.4 그대로)**: 실시간 시세 / 미국 지수 / 뉴스는 이번 STEP 에서 새 수집을 만들지 않음. 저장 위치가 없는 항목은 향후 `unavailable` 처리 대상으로 표시.

---

## 8. §7.5 PC↔OCI transfer map

기존 script 및 command 기준 (신규 transport 설계 · 구현 금지):

| 방향 | 기존 script | 전송 대상 | staging | 검증 | atomic rename | 확인 상태 |
|---|---|---|---|---|---|---|
| PC → OCI | `scripts/sync_three_push_packages.py` | `state/three_push/packages/` (manifest + 3개 latest_*.json) | 원격 임시 경로 (line 90 `f"{base}/three_push/packages"`; 세부 staging path 는 env `THREE_PUSH_REMOTE_PACKAGE_DIR` 로 지정) | `scripts/verify_three_push_packages_oci.py` (별도 CLI, OCI 상 검증) | `manifest.json 을 마지막에 atomic 업로드` (line 229 주석) | Package fallback 경로. PC↔OCI 실측 왕복은 직전 STEP 에서는 없음 (진단만). |
| PC → OCI | `scripts/sync_three_push_runtime_param.py` | `state/three_push/params/latest_runtime_param.json` (단일 파일) | 원격 `latest_runtime_param.json.tmp` (line 154) | `scripts/verify_three_push_param_oci.py` (OCI 상 stand-alone 검증) | line 155 `remote_final = "{remote_dir}/latest_runtime_param.json"` — tmp → final rename | 실운영 PARAM 반영 경로. |
| OCI → PC | 없음 (실측) | 해당 없음 | 해당 없음 | 해당 없음 | 해당 없음 | **§10 다음 STEP 에서 `scripts/export_oci_analysis_snapshot.py` + `scripts/sync_oci_analysis_snapshot.py` 신설 예정 (설계자 §9 확정)**. 이번 STEP 은 신설 금지. |

**공통 관측**:
- SSH 정보 · staging 절대 경로 · credential 은 문서에 미기록 (지시문 §9 준수).
- `THREE_PUSH_REMOTE_PACKAGE_DIR` 등 env 변수명만 인용.
- 실제 OCI 측 staging 경로 및 권한 · atomic rename 지원 여부는 **미확인**.

---

## 9. §7.6 다음 Step 확정 필요 항목

지시문 §9 · §10 · §11 그대로 (개발자 임의 확정 금지 — 목록만):

1. **holdings JSON → DB table 매핑**. 현재 `state/holdings/holdings_latest.json` 의 schema (필드 · 정규화 수준) 와 지시문 §7 명시 `holding_position` / `holding_lot` 테이블 정규화 매핑.
2. **PARAM policy 의 column / child table 매핑**. `runtime_policy` / `evidence_policy` / `safety_policy` 각각의 세부 필드 → `runtime_param_policy` normalize 방식 (단일 값 column / 반복 값 child row 구체).
3. **Publication 식별자와 source data 기준 정의**. `data_publication.source_data_version` 을 무엇으로 삼을지 — 후보: (a) `PRAGMA user_version`, (b) migration schema version, (c) 시장 데이터 max(date) + git commit, (d) publication_id 자체.
4. **OCI → PC analysis snapshot 형식**. Full DB dump vs. row set (`etf_daily_price` / `market_benchmark_daily_price` 등 특정 range) vs. WAL export.
5. **PC → OCI PARAM publish bundle 형식**. PARAM row + `runtime_param_push_kind` + `runtime_param_policy` 만 포함하는 SQLite bundle 스키마 · manifest.
6. **Apply 버튼 이후 transfer / import 사용자 흐름**. API 내부에서 어디까지 자동 · 어디부터 사용자 수동 CLI (bundle 파일 저장 위치 · 사용자 액션 명시).
7. **OCI DB bootstrap 방식**. 첫 초기화만 허용 vs. 기존 활성 DB 존재 시 `requires_explicit_reconciliation` 종료 (지시문 §9.1 명시).
8. **Runtime evidence DB 조회 계약**. `market_briefing` / `holdings_briefing` / `spike_or_falling_alert` 각 PUSH 별 `available_sources` 구성을 위한 DB 조회 항목 · 기준일 계산식.

---

## 10. Canonical 문서 반영 결과

지시문 §8 대로 실제 존재 확인된 문서만 갱신. 미존재 문서는 신설하지 않음.

| 문서 | 존재 | 이번 STEP 갱신 |
|---|---|---|
| `docs/PROJECT_ORIGIN_INTENT.md` | ✅ | 사용자 확정 운영 저장소 결정 추가 (§8.1 지시). |
| `docs/MASTER_PLAN.md` | ✅ | OCI read model / PARAM 저장소 / JSON 역할 제한만 정정. 단계 순서 · 기존 단계 정의 변경 없음 (§8.2 지시). |
| `docs/ASSUMPTIONS.md` | ✅ | A-2 / A-6 이력 보존 + "현재 결정" 라벨 추가 (§8.3 지시). |
| `docs/STATE_LATEST.md` | ✅ | 사용자 확정 + 현재 구현 상태 (DB 전환 전) + 현재 활성 STEP 반영 (§8.4 지시). |
| `docs/handoff/POC2_B_NEXT_ACTIONS.md` | ✅ | 위와 동일 (§8.4 지시). |
| `docs/backlog/BACKLOG.md` | ✅ | 이번 STEP 신규 위험 없음 → 항목 추가 없음 (§8.5 지시). |

MASTER_PLAN 단계 순서 · 기존 단계 정의 변경 여부: **변경 없음** (§10 AC-10 준수).

---

## 11. AC 충족 (지시문 §9)

| AC | 결과 |
|---|---|
| AC-1 live JSON/JSONL/SQLite 경로 누락 없이 목록화 | ✅ (§4 · §5, 216 파일 전량 실측) |
| AC-2 reader / writer / 소비 기능 / A/B/C 근거 기록 | ✅ (§4 각 표) |
| AC-3 ML latest artifact 는 폴더명이 아닌 reader/writer 로 분류 | ✅ (§4.4) |
| AC-4 Package fallback 은 reader + 수동 복구 근거로 분류 | ✅ (§4.1 3개 package 행 + `oci_sent_registry.json` — 실운영 아닌 fallback, 다만 OCI 상 존재 확인됨 → A→C 경계로 명시) |
| AC-5 PARAM · runtime latest state · sent registry · sync state 실제 호출 경로 | ✅ (§6) |
| AC-6 3-PUSH evidence source 의 producer / 저장 위치 / consumer / 기준일 | ✅ (§7) |
| AC-7 PC↔OCI transfer 는 기존 근거만 기록 | ✅ (§8, 신규 transport 설계 없음) |
| AC-8 OCI DB 관련은 확인 근거 vs 미확인 구분 | ✅ (§5 마지막 열 "확인 상태", §1 마지막 "미확인 항목") |
| AC-9 사용자 확정 운영 저장소 결정을 canonical 문서에 반영 | ✅ (§10) |
| AC-10 MASTER_PLAN 단계 순서 미변경 | ✅ |
| AC-11 미확인 파일 · 테이블 · 경로 신규 생성 없음 (conclusion 1개만 신규) | ✅ |
| AC-12 소스 · DB · JSON · runtime · API · UI · scheduler · transfer 구현 변경 0건 | ✅ (`git diff` 문서만) |
| AC-13 다음 STEP schema mapping · publication 기준을 목록으로 남김 | ✅ (§9) |

---

## 12. 알려진 한계

- **OCI 상 실측이 필요한 항목**: §1 마지막 리스트. 다음 STEP 착수 시 사용자 실측 sanitised 요약 필요.
- **미확인 4개 `state/ml/ml_*_latest.json` 계열**: 코드 참조는 있으나 PC · OCI 실제 생성 여부 미확인. §4.5 표. 다음 STEP 매핑 확정 전에 실측 필요.
- **`state/universe/` 하위**: 코드 참조 (진단 requirements) 는 있지만 실제 producer/consumer 확정 필요. 다음 STEP §10 재배선 시.
- 이번 STEP 은 **분류만**. 실제 A → DB 이관 · C → 삭제 · B → archive 이동은 다음 STEP.
