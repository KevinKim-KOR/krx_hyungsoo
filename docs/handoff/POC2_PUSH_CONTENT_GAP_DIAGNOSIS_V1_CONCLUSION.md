# PUSH Content Gap Diagnosis v1 — Conclusion (DONE, Closeout 완료)

작성일: 2026-07-05
성격: 3개 PUSH 가 "필요한 데이터가 부족하다" 축약 메시지로 도착하는 원인을 read-only 재현·확정. 이번 Step 은 SQLite 동기화·PUSH 문구 개선·OCI 배포 변경을 **하지 않는다**.

---

## 1. 완료 판정 — DONE (Closeout)

**기술 진단**: 완료. PC · OCI 양쪽 동일 commit `89f7cd31` 에서 read-only 진단 CLI 실행. artifact sanitised 요약 교차 비교 완료.

**저장소 Closeout**: 이 문서 갱신으로 마감. PC / OCI 개별 artifact 는 각자 원본 상태 그대로 유지 (`observation_status=single_environment_pending_cross_comparison` 필드 미수정 — 설계자 지시). 교차 비교 완료 사실은 본 Closeout 문서와 §15 완료 보고 JSON 에서 확정.

| 항목 | 값 |
|---|---|
| 진단 CLI | `python -m scripts.run_push_content_gap_diagnosis --environment pc|oci` |
| PC 실행 commit | `89f7cd31` |
| OCI 실행 commit | `89f7cd31` (사용자 확인) |
| PC status | ok |
| OCI status | ok |
| 발송 · 외부 호출 | 0건 (자동 테스트 `test_2` / `test_3` 검증) |
| 기존 SQLite / state artifact 변경 | 0건 (`test_4` / `test_5` 검증) |
| 비밀정보 · 절대 경로 leak | 없음 (`test_9` 검증) |

---

## 2. 최종 결론 (설계자 확정본)

```text
공통 직접 원인:
PARAM runtime 이 available_sources=None 으로 실행되어
3개 PUSH 모두 evidence 를 공급받지 못함.

OCI 추가 기여 원인:
sqlite_integrity=unavailable,
required_paths_ready=false.

최종 분류:
RUNTIME_CONFIGURATION_GAP.
```

파일 부재 · 경로 설정 · 권한 중 어느 것인지는 이번 Step 에서 추정하거나 분해하지 않음. 다음 Step 에서 다룸.

**다음 Step 유형** (완료 보고 분류값): `OCI_RUNTIME_CONFIGURATION_CLOSEOUT`.

**다음 Step 정식 설계명** (별도 설계, 개발자가 임의 확정 X): `OCI Runtime Evidence Supply Closeout v1`. `available_sources=None` 보정과 OCI 의 SQLite · 필수 경로 준비가 함께 닫혀야 실제 PUSH 내용이 채워지기 때문.

---

## 3. PC · OCI 비교

### 3.1 환경 비교표

| 항목 | PC | OCI |
|---|---|---|
| 실행 commit | `89f7cd31` | `89f7cd31c13e00acd108f63d701f066864d9711c` |
| SQLite 무결성 | ok | unavailable |
| 필수 logical path 준비 (`required_logical_paths_ready`) | True | false |
| 관측 상태 (`observation_status`) | single_environment_pending_cross_comparison | single_environment_pending_cross_comparison |

`observation_status` 는 개별 환경 진단 artifact 원본 상태 (설계자 지시로 유지). 교차 비교 완료 사실은 본 Closeout 문서로 확정.

### 3.2 PUSH 경로 비교표

| PUSH | PC PARAM runtime 결과 | PC package fallback 결과 | OCI PARAM runtime 결과 | OCI package fallback 결과 | 공통 직접 원인 | 최종 root cause |
|---|---|---|---|---|---|---|
| market_briefing | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=package_dir_missing / content_generation_status=runtime_unavailable | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=None / content_generation_status=content_ready | PARAM runtime 이 available_sources=None 으로 실행 → evidence 미공급 | RUNTIME_CONFIGURATION_GAP |
| holdings_briefing | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=package_dir_missing / content_generation_status=runtime_unavailable | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=None / content_generation_status=content_ready | PARAM runtime 이 available_sources=None 으로 실행 → evidence 미공급 | RUNTIME_CONFIGURATION_GAP |
| spike_or_falling_alert | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=package_dir_missing / content_generation_status=runtime_unavailable | content_generation_status=data_insufficient / exact_reason_code=runtime_available_sources_not_supplied / selection_result_count=0 | exact_reason_code=None / content_generation_status=content_ready | PARAM runtime 이 available_sources=None 으로 실행 → evidence 미공급 | RUNTIME_CONFIGURATION_GAP |

### 3.3 교차 관측 정리

- **PARAM runtime 경로 (실운영)**: PC · OCI 완전 동일 — 세 PUSH 모두 `data_insufficient` + `runtime_available_sources_not_supplied` + `selection_result_count=0`. `scripts/run_three_push_runtime_oci.py:177` 의 `available_sources=None` 하드코딩이 공통 직접 원인.
- **Package fallback 경로 (비교 근거만)**: PC 는 `package_dir_missing` (PC 에는 `state/three_push/packages/` 자체가 부재), OCI 는 `content_ready` (OCI 에는 package 가 존재해서 fallback 이 정상 로드 가능). 이 차이는 최종 root cause 를 바꾸지 않음 — 실운영 경로는 PARAM runtime.
- **환경 공통 결함이 아닌 OCI 만의 추가 관측**: `sqlite_integrity=unavailable` + `required_paths_ready=false`. 이 두 신호는 OCI 추가 기여 원인으로 기록되지만, 세부 (파일 부재 / 경로 설정 / 권한) 분해는 다음 Step 범위.

---

## 4. OCI 실측 실행 안내 (사용자용)

### 4.1 실행 전제

- **동일 commit** (`89f7cd31`) 이 OCI 에 반영되어 있어야 함 (기존 배포 절차 그대로). 실측에서 PC · OCI 양쪽 동일 `89f7cd31` 확인.
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

이 파일은 OCI 로컬 파일시스템에만 생성됨. **PC 로 sync 하지 않음** (지시문 §8.2 금지 항목). 교차 비교는 sanitised 값만 사용.

### 4.4 실제 수집한 sanitised 요약

**OCI 실측 완료값** (사용자 확인):
- `environment`: `"oci"`
- `code_version.commit`: `89f7cd31c13e00acd108f63d701f066864d9711c`
- `runtime_readiness.sqlite_integrity`: `unavailable`
- `runtime_readiness.required_logical_paths_ready`: `false`
- 각 PUSH 별 세 값 (§3.2 비교표 참조):
  - `param_runtime_path`: `content_generation_status=data_insufficient` / `exact_reason_code=runtime_available_sources_not_supplied` / `selection_result_count=0`
  - `package_fallback_path`: `exact_reason_code=None` / `content_generation_status=content_ready`

**Secret / 절대 경로 leak 없음** (진단 CLI 가 이를 artifact 에 담지 않도록 이미 필터링, 자동 테스트 `test_9` 검증).

---

## 5. AC 충족 (지시문 §14)

| AC | 결과 |
|---|---|
| AC-1 3개 PUSH 각각의 입력 · artifact · 최소 관측 기간 · 필터 조건 식별 | ✅ (`PUSH_REQUIREMENTS` 매핑) |
| AC-2 데이터 부족 · 빈 선택이 정확한 조건으로 재현 | ✅ (PC · OCI 세 PUSH 모두 `runtime_available_sources_not_supplied`) |
| AC-3 동일 commit 진단 CLI PC · OCI 각각 1회 수동 실행 | ✅ 양쪽 commit `89f7cd31` |
| AC-4 PC · OCI SQLite · artifact · 기준일 · 행 수 · commit · 실행 조건 차이 비교 | ✅ §3.1 환경 비교표 + §3.2 PUSH 경로 비교표 |
| AC-5 각 PUSH primary root cause + contributing causes + 증거 기록 | ✅ §2 최종 결론 (공통 직접 원인 + OCI 추가 기여 원인 + 최종 분류) |
| AC-6 SQLite / 기존 state artifact / Telegram 실행 이력 미변경 | ✅ (자동 테스트 검증) |
| AC-7 외부 시세 호출 · Telegram 발송 없음 | ✅ (자동 테스트 검증) |
| AC-8 비밀정보 · 절대 경로 leak 없음 | ✅ (자동 테스트 검증) |
| AC-9 다음 Step 유형 하나 결정 | ✅ `OCI_RUNTIME_CONFIGURATION_CLOSEOUT` (정식 설계명은 별도 설계 세션에서 확정) |
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

## 8. 알려진 한계 · 다음 Step 로 이관 항목

- **OCI 의 `sqlite_integrity=unavailable` + `required_paths_ready=false` 세부**: 파일 부재 / 경로 설정 / 권한 중 어느 것인지 이번 Step 에서 추정 · 분해하지 않음. 다음 Step 범위 (`OCI Runtime Evidence Supply Closeout v1`).
- **PC package fallback 경로 not-applicable**: PC 에도 `state/three_push/packages/` 부재. 실운영 경로는 PARAM runtime 이므로 이번 STEP 결론에는 영향 없음. package 경로 부활 필요 여부는 별도 판단 (BACKLOG 이관 상태).
- **개별 환경 진단 artifact 의 `observation_status=single_environment_pending_cross_comparison`**: 원본 상태 유지 (설계자 지시). 교차 비교 완료 사실은 본 Closeout 문서와 §15 완료 보고 JSON 으로만 확정.

---

## 9. 다음 활성 Step

**분류값**: `OCI_RUNTIME_CONFIGURATION_CLOSEOUT` (완료 보고 §15 JSON `overall.next_step_type` 기록값).

**정식 설계명**: `OCI Runtime Evidence Supply Closeout v1` (별도 설계 세션에서 최종 확정 — 개발자가 임의로 정하지 않음).

**이유**: `scripts/run_three_push_runtime_oci.py:177` 의 `available_sources=None` 보정과 OCI 의 SQLite · 필수 경로 준비가 **함께 닫혀야** 실제 PUSH 내용이 채워짐. 두 조건 중 하나만 해결해서는 부족.

이번 STEP 안에서는 그 다음 STEP 을 구현하지 않음 (지시문 §11 명시).
