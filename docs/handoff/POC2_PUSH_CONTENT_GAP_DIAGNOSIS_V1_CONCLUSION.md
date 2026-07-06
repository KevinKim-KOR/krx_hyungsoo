# PUSH Content Gap Diagnosis v1 — Conclusion (PARTIAL, OCI 실측 대기)

작성일: 2026-07-05
성격: 3개 PUSH 가 "필요한 데이터가 부족하다" 축약 메시지로 도착하는 원인을 read-only 재현·확정. 이번 Step 은 SQLite 동기화·PUSH 문구 개선·OCI 배포 변경을 **하지 않는다**.

---

## 1. 완료 판정 — PARTIAL

**PARTIAL 사유** (Q3 (c) 확정본 준수): OCI 실측 실행이 아직 수행되지 않았음. 지시문 §8.1 은 "동일 commit 을 OCI 에 반영 → OCI 에서 진단 CLI 를 1회 수동 실행" 을 명시. 개발자가 OCI 접속 권한 없어 PC 실측 + OCI 실행 준비까지만 완료.

PC 실측은 완료 상태:

| 항목 | 값 |
|---|---|
| 진단 CLI | `python -m scripts.run_push_content_gap_diagnosis --environment pc` |
| commit | `c05f2c58` (Baseline v2 STEP 종료 상태) |
| status | ok |
| sqlite_integrity | ok |
| 진단 artifact | `state/diagnostics/push_content_gap_diagnosis_latest.json` |
| 발송 · 외부 호출 | 0건 (자동 테스트 `test_2` / `test_3` 검증) |
| 기존 SQLite / state artifact 변경 | 0건 (`test_4` / `test_5` 검증) |
| 비밀정보 · 절대 경로 leak | 없음 (`test_9` 검증) |

---

## 2. PC 실측 잠정 관측 (확정 아님)

**중요**: Q3 (c) 확정본 준수 — OCI 실행 전에는 root cause · next step 을 단정하지 않는다. 아래는 **PC environment 한쪽만 담은 잠정 관측치**이며, 최종 root_cause 는 OCI 실측 후 PC · OCI 비교에서 확정한다. artifact 최상위 `observation_status=single_environment_pending_cross_comparison` 로도 명시.

세 PUSH 모두 PC 시점에서 동일한 관측:

| PUSH | (PC 잠정) primary_root_cause | exact_reason_code | selection_result_count |
|---|---|---|---|
| market_briefing | RUNTIME_CONFIGURATION_GAP (잠정) | `runtime_available_sources_not_supplied` | 0 |
| holdings_briefing | RUNTIME_CONFIGURATION_GAP (잠정) | `runtime_available_sources_not_supplied` | 0 |
| spike_or_falling_alert | RUNTIME_CONFIGURATION_GAP (잠정) | `runtime_available_sources_not_supplied` | 0 |

### 2.1 PARAM runtime 경로 (실운영 경로, Q1 (c) 확정 기준)

- PARAM 파일 (`state/three_push/params/latest_runtime_param.json`) 정상 로드.
- 세 PUSH 모두 PARAM 의 `enabled_push_kinds` 에 포함됨 (`push_kind_enabled_in_param=True`).
- `build_runtime_message(available_sources=None)` 호출 성공 → 메시지 자체는 생성됨 (`message_text_length` 142~177).
- **하지만 `available_sources=None` 하드코딩** (`scripts/run_three_push_runtime_oci.py:177`) 때문에 축약 unavailable 메시지가 만들어짐.

### 2.2 Package fallback 경로 (비교 근거)

- **PC 에서 `state/three_push/packages/` 자체가 존재하지 않음** (`package_dir_missing`).
- Package fallback 경로도 PC 에서 준비되지 않은 상태 → package 경로가 evidence 를 채워주는 대안으로도 작동하지 않음.
- 세 PUSH 모두 package_fallback `applicable=False`.

### 2.3 원인 종합 (PC 잠정, 확정 아님)

Q1 확정본의 특수 규칙 (package_ready + runtime_not_supplied → RUNTIME_CONFIGURATION_GAP) 에는 해당하지 않음. 대신 일반 규칙 (PC 시점 잠정 관측):

- PARAM runtime 이 `runtime_available_sources_not_supplied` 를 반환 → PC 시점 세 PUSH 모두 RUNTIME_CONFIGURATION_GAP 후보.
- PC package 경로도 not-applicable → contributing 원인 후보로 `package_fallback_also_not_ready`.
- **PC 기준 잠정 다음 Step 유형**: `OCI_RUNTIME_CONFIGURATION_CLOSEOUT`. OCI 실측 후 최종 확정.

---

## 3. PC · OCI 비교 결과

**미완료 — OCI 실측 대기**.

지시문 §8.1 순서:
1. ✅ PC 실측 완료 (commit `c05f2c58`).
2. ⏳ 동일 commit 을 OCI 에 반영.
3. ⏳ OCI 에서 `--environment oci` 로 진단 CLI 1회 수동 실행.
4. ⏳ PC · OCI artifact 비교.
5. ⏳ Closeout 문서 · 최종 보고 마무리.

OCI 실측이 도착하면 아래 형태로 비교 표를 추가:

| PUSH | PC path 상태 | OCI path 상태 | 최종 root_cause |
|---|---|---|---|
| market_briefing | ... | ... | ... |
| holdings_briefing | ... | ... | ... |
| spike_or_falling_alert | ... | ... | ... |

---

## 4. OCI 실측 실행 안내 (사용자용)

### 4.1 실행 전제

- **동일 commit** (`c05f2c58`) 이 OCI 에 반영되어 있어야 함 (기존 배포 절차 그대로).
- 별도 배포 · 경로 · 권한 · 스케줄러 · CI/CD 변경 필요 **없음** (지시문 §4, §5, §8.1 금지).

### 4.2 실행 명령

```bash
cd <project_root_on_oci>
python -m scripts.run_push_content_gap_diagnosis --environment oci
```

### 4.3 산출물 위치 (OCI 로컬)

```
state/diagnostics/push_content_gap_diagnosis_latest.json
```

이 파일은 OCI 로컬 파일시스템에만 생성됨. **PC 로 sync 필요 없음** (지시문 §8.2 금지 항목).

### 4.4 사용자가 붙여넣을 sanitised 요약

다음 항목만 새 세션에 전달:

- `environment`: "oci"
- `code_version.commit`
- 각 PUSH 별:
  - `push_id`
  - `param_runtime_path.exact_reason_code`
  - `param_runtime_path.message_text_length`
  - `package_fallback_path.exact_reason_code`
  - `package_fallback_path.content_generation_status`
  - `primary_root_cause`
  - `recommended_next_step_type`

**절대 전달하지 말 것** (지시문 §9 준수): Telegram token / chat id / 환경변수 원문 / 절대 경로 / credential. 진단 CLI 자체가 이를 artifact 에 담지 않도록 이미 필터링돼 있음 (자동 테스트 `test_9` 검증).

---

## 5. AC 충족 (지시문 §14)

| AC | 결과 (PC 시점) |
|---|---|
| AC-1 3개 PUSH 각각의 입력 · artifact · 최소 관측 기간 · 필터 조건 식별 | ✅ (`PUSH_REQUIREMENTS` 매핑) |
| AC-2 데이터 부족 · 빈 선택이 정확한 조건으로 재현 | ✅ (세 PUSH 모두 `runtime_available_sources_not_supplied`) |
| AC-3 동일 commit 진단 CLI PC · OCI 각각 1회 수동 실행 | ⏳ PC ✅ / OCI 대기 |
| AC-4 PC · OCI SQLite · artifact · 기준일 · 행 수 · commit · 실행 조건 차이 비교 | ⏳ OCI 실측 후 |
| AC-5 각 PUSH primary root cause + contributing causes + 증거 기록 | ⏳ PC 잠정 관측만 기록 / OCI 실측 후 최종 확정 |
| AC-6 SQLite / 기존 state artifact / Telegram 실행 이력 미변경 | ✅ (자동 테스트 검증) |
| AC-7 외부 시세 호출 · Telegram 발송 없음 | ✅ (자동 테스트 검증) |
| AC-8 비밀정보 · 절대 경로 leak 없음 | ✅ (자동 테스트 검증) |
| AC-9 다음 Step 유형 하나 결정 | ⏳ PC 기준 잠정 `OCI_RUNTIME_CONFIGURATION_CLOSEOUT` / OCI 실측 후 최종 확정 |
| AC-10 PUSH 문구 · 선택 기준 · ML artifact · Discovery · Holdings · AI Sessions · Preview 미변경 | ✅ |
| AC-11 기존 전체 테스트 · 정적 검사 통과 | ✅ 790 passed (772 → 790, 신규 18). black / flake8 PASS |

---

## 6. 자동 테스트 결과

| 항목 | 결과 |
|---|---|
| backend 전체 | 790 passed (772 → 790, 신규 18) |
| black / flake8 (app, tests, scripts) | PASS |
| frontend | 변경 없음 |

**신규 테스트 18건** — `tests/test_push_content_gap_diagnosis.py`:
§12.1 helper 호출 / §12.2 telegram_send 미호출 / §12.3 외부 호출 없음 / §12.4 SQLite 미변경 / §12.5 기존 artifact 미변경 / §12.6 새 artifact 만 생성 / §12.7 requirements 기록 / §12.8 exact reason code / §12.9 secret · 절대 경로 미포함 / §12.10 environment 인자 일치 / §12.11 RUNTIME_CONFIGURATION_GAP (PARAM 부재) / **§12.12 OCI_EVIDENCE_GAP (지시문 원문 fixture — environment=oci + artifact 부재) [FIX r1 재작성]** / **§12.13 OBSERVATION_HISTORY_GAP (지시문 원문 fixture — sqlite lookback 부족) [FIX r1 재작성]** / **§12.14 CONTENT_SELECTION_GAP (지시문 원문 fixture — 데이터 충족 + 선택 empty) [FIX r1 재작성]** / **`test_14c_mixed_when_two_independent_causes` (§11 MIXED — 서로 독립인 원인 둘 동시 관찰) [FIX r2 신규]** / §12.15 environment 검증 + `test_14b_unresolved` + `requirements_map_covers_three_pushes`.

**FIX r1 정정 요약**: 초안 테스트 (`test_12` ~ `test_14`) 가 지시문 §12 원문 원인 분류 fixture 를 실제로 검증하지 못하고 `RUNTIME_CONFIGURATION_GAP` 또는 `UNRESOLVED` 만 확인하는 우회 검증이었음. FIX r1 에서 (a) `_decide_primary_root_cause` 에 `OCI_EVIDENCE_GAP` / `OBSERVATION_HISTORY_GAP` / `CONTENT_SELECTION_GAP` 실제 분기를 추가하고 (b) 세 테스트를 지시문 원문 fixture 그대로 재작성.

**FIX r2 정정 요약**: 검증자 B-2/B-3 (단일 파일 649줄) + B-6 (MIXED 분류 실제 반환 경로 부재) 지적 해소. (a) core 를 4 모듈로 분리: `push_content_gap_diagnosis_requirements.py` (195줄, 상수 + readiness) / `push_content_gap_diagnosis_reproducers.py` (152줄, PARAM · package 재현) / `push_content_gap_diagnosis_classifier.py` (171줄, 원인 분류 + MIXED 분기 신규) / `push_content_gap_diagnosis.py` (210줄, main runner + artifact writer). (b) classifier 에 `_count_independent_causes()` 로 MIXED 실제 분기 신설 + 테스트 `test_14c_mixed_when_two_independent_causes` 로 검증. (c) 리팩터 전후 실측 값 (환경 정보 / 각 PUSH root_cause · exact_reason_code · selection_result_count · message_text_length · observation_status) 완전 동일. artifact 파일의 SHA256 은 `generated_at` (실행마다 갱신되는 ISO timestamp) 때문에 실행별로 다름 — "해시 동일" 이 아니라 "재현 계약 필드 값 동일".

---

## 7. 변경 파일 목록

**신규** (FIX r2 로 core 를 책임별 4 모듈로 분리 — B-2/B-3 해소):
- `app/push_content_gap_diagnosis_requirements.py` (195줄) — `PUSH_REQUIREMENTS` 상수 + SQLite integrity · 테이블 · artifact readiness helper.
- `app/push_content_gap_diagnosis_reproducers.py` (152줄) — PARAM runtime + package fallback 재현 (기존 pure helper 재사용).
- `app/push_content_gap_diagnosis_classifier.py` (171줄) — `readiness_signals` + `decide_primary_root_cause` (§11 6종 + Q1 특수 + MIXED 분기 신규).
- `app/push_content_gap_diagnosis.py` (210줄) — main runner + artifact writer (얇게 유지, 하위 호환 재-export).
- `scripts/run_push_content_gap_diagnosis.py` — 수동 CLI (`--environment pc|oci` 필수).
- `tests/test_push_content_gap_diagnosis.py` — 18 케이스 (§12.12/13/14 지시문 원문 fixture + `test_14b_unresolved` + `test_14c_mixed_when_two_independent_causes` [FIX r2 신규]).
- `docs/handoff/POC2_PUSH_CONTENT_GAP_DIAGNOSIS_V1_CONCLUSION.md` (본 문서).

**수정**:
- `.gitignore` (`state/diagnostics/push_content_gap_diagnosis_latest.json` 추가 — 환경별 로컬 artifact).
- `docs/STATE_LATEST.md`
- `docs/handoff/POC2_B_NEXT_ACTIONS.md`
- `docs/handoff/POC2_FEATURE_INVENTORY.md`
- `docs/backlog/BACKLOG.md`

`docs/MASTER_PLAN.md`, 기존 PUSH 코드 · SQLite schema · Telegram 발송 경로 · Market Discovery · Holdings · AI Sessions · Decision Draft Preview · ML artifact — **일체 미변경** (§4, §5, §10).

---

## 8. 알려진 한계

- **OCI 실측 대기**: 지시문 §8.1 순서상 OCI 실행 없이는 DONE 처리 금지 (Q3 (c) 확정).
- **root cause 를 PC 실측만으로 확정한 것은 아님**: 세 PUSH 모두 `runtime_available_sources_not_supplied` 라는 정황 증거는 강함. 다만 OCI 에서 (a) 동일 commit 이 반영되었는지, (b) OCI runtime 이 실제로 동일한 축약 메시지를 생성하는지, (c) OCI 쪽에만 다른 요인 (예: PARAM 파일 위치 · 권한 문제) 이 있는지 실측이 필요.
- **PC package 경로 not-applicable**: PC 에도 `state/three_push/packages/` 자체가 없음. 즉 현재 PC 는 package fallback 경로를 통해 evidence 를 준비해두는 상태도 아님. package 경로를 되살리는 별도 STEP 이 필요할 수 있으나, 이번 STEP 범위는 아님.

---

## 9. 다음 활성 Step 후보

PC 기준 잠정 결정 (OCI 실측 후 최종 확정):

**`OCI_RUNTIME_CONFIGURATION_CLOSEOUT`** — `scripts/run_three_push_runtime_oci.py:177` 의 `available_sources=None` 하드코딩을 실제 evidence 를 전달받는 구성으로 교체하는 별도 STEP.

이번 STEP 안에서는 그 다음 STEP 을 구현하지 않음 (지시문 §11 명시).
