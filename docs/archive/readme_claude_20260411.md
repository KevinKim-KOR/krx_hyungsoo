# readme_claude.md — Claude의 docs/ 감사 노트

> 작성자: Claude (P209-CLEAN cleanup 세션 말미)
> 작성일: 2026-04-11
> 상태: 분석 완료 / 실행 대기 (사용자 승인 전)
> 목적: `docs/` 폴더의 파일 배치 감사 결과를 기록. 새 세션 Claude 또는 사용자가 이 파일만 보고 현황과 제안을 파악할 수 있도록 한다.

---

## 0. 이 파일의 성격

- Claude 가 `docs_governance.md` + `docs_inventory.md` 정책 vs 실제 배치를 비교 감사한 결과
- Current Truth 가 아님 — 감사 시점(2026-04-11) 의 스냅샷
- 실행되지 않은 이동 제안 목록 포함
- 사용자가 승인하면 이 파일을 따라 실제 이동을 수행하고, 실행 후 이 파일 상단에 "EXECUTED" 마커 추가

---

## 1. 감사 방법

1. `docs/` 이하 전체 파일 목록화 (`find docs -type f`)
2. `docs/docs_governance.md` 의 "폴더 구조 기준" 표 로드 — 정책
3. `docs/docs_inventory.md` 의 기존 분류/플래그 로드 — 현재 분류 상태
4. `docs/README.md` 의 top-level 참조 확인 — README 가 링크하는 문서는 top-level 유지 근거
5. 각 top-level 파일의 첫 줄/헤더 확인 — 내용 성격 판정
6. `docs/handoff/` 14 파일 개별 확인
7. cross-reference grep — 각 의심 파일이 다른 문서/코드에서 어떻게 참조되는지 확인
8. 4 개 카테고리로 분류: 오배치 확정 / 사용자 결정 필요 / 유지 / 정상

---

## 2. 판정 기준 (docs_governance.md "폴더 구조 기준" 요약)

| 폴더 | 용도 |
|---|---|
| `SSOT/` | 불변 원칙, 결정 기록, 프로젝트 헌법 |
| `analysis/` | 설계, 분석, 성과문서 (Phase/Step별) |
| `archive/` | 폐기/레거시 문서 |
| `contracts/` | API/인터페이스 스펙, 계약 문서 |
| `handoff/` | 인계 스냅샷, closeout 문서, ZIP 아카이브 |
| `ops/` | 운영 정책, 매니페스트, 체크리스트 |
| `runbooks/` | 실행 절차서 (배포, 데일리, 라이브) |
| `state/` | 현재 상태 기록 |
| `task_reports/` | 업무 완료 리포트 (JSON) |

**폴더 배치 규칙**:
- 설계/성과문서는 `analysis/` 에 둔다. `handoff/` 에 두지 않는다
- runbook 은 `runbooks/` 에 통합한다. `ops/` 에 두지 않는다
- 인계용 스냅샷 ZIP 은 `handoff/` 에 둔다. 전개(unzip) 하지 않는다
- 스크립트, 로그 파일은 `task_reports/` 에 두지 않는다

---

## 3. 감사 결과

### 3.1 Category 1 — 오배치 확정 (1건, 즉시 이동 권장)

| 현재 경로 | 권장 경로 | 근거 |
|---|---|---|
| `docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md` | `docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md` | 거버넌스 명시: "설계/성과문서는 `analysis/` 에 둔다". 이 파일은 refactor PLAN (설계). Claude 가 2026-04-11 에 생성할 때 top-level 에 둔 실수. |

**참조 갱신 필요 (1곳)**:
- `docs/handoff/P208_close_and_P209_handoff.md` line 9 의 경로 문자열
  `docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md` → `docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`

**인벤토리 갱신 필요**:
- `docs/docs_inventory.md` 의 "Reference / Contract" 섹션에 신규 entry 추가

### 3.2 Category 2 — 사용자 결정 필요 (2건)

| 경로 | inventory 플래그 | 상황 | Claude 권장 |
|---|---|---|---|
| `docs/UI_MAP.json` | `ARCHIVE_OR_DEPRECATE` / 미확인 | `archive/UI_MAP_legacy.md` 의 JSON 페어. MD 버전은 이미 archive/ 에 있음. JSON 은 DEPRECATED 배너를 달 수 없어 이동이 유일한 방법 | `docs/archive/UI_MAP.json` 로 이동 |
| `docs/UI_WIRING_DECISION_V1.json` | `ARCHIVE_OR_DEPRECATE` / 미확인 | S2 분해 이후 current UI 구조 반영 여부 불명 | `docs/archive/UI_WIRING_DECISION_V1.json` 로 이동 |

두 건 모두 `docs_inventory.md` 에 "추가 검토 후보" 로 플래그되어 있고, 사용자가 아직 deprecated 확정을 하지 않은 상태. Claude 가 독단으로 이동하지 않음.

### 3.3 Category 3 — top-level 유지 (9건, 정당한 이유 있음)

| 경로 | 유지 근거 |
|---|---|
| `docs/README.md` | docs/ 진입점 인덱스 |
| `docs/docs_governance.md` | Current Truth, README 직접 링크 |
| `docs/docs_inventory.md` | Current Truth, README 직접 링크 |
| `docs/structure_baseline.md` | Current Truth, README 직접 링크 |
| `docs/OCI_EVIDENCE_RESOLVER_GUIDE_V1.md` | inventory KEEP_REFERENCE, README 직접 링크, `docs/handoff/HANDOFF_P204_ML.md` 에서 현장 백서로 참조 |
| `docs/walkthrough.md` | inventory KEEP_REFERENCE "미확인", README + `SSOT/PROJECT_CONSTITUTION.md` 에서 참조. 내용은 P146 시기(2026-02) 로 오래됐으나 공식 레퍼런스 역할 유지. **갱신 여부는 별도 판단 사항** |

### 3.4 Category 4 — handoff/ 내부 (14건 전부 정상)

handoff/ 폴더 내 모든 파일이 거버넌스 정책에 부합:

- `P204_closeout.md/.json`, `P205_structure_closeout.md`, `P206_close_and_P207_handoff.md`, `P207_close_and_P208_handoff.md`, `P208_close_and_P209_handoff.md` — 전형적 closeout/handoff 기록 (7 파일)
- `HANDOFF_P204_ML.md/.json/CHECKLIST.md`, `P205_handoff_draft.md` — 기타 P204/P205 인계 문서 (4 파일)
- `handoff_0403.zip` — "인계용 스냅샷 ZIP 은 `handoff/` 에 둔다" 정책 부합
- `AI_HANDOFF_GUIDE.md` — AI 핸드오프 메타 가이드, 위치 적절
- `KRX_Alertor_SP_구현지시문.md` — 새 세션용 SP 프롬프트, handoff 맥락 적절
- `handoff.md` — 일반 핸드오프 메모

### 3.5 Category 5 — 하위 폴더 내부 (모두 정책 부합)

- `analysis/P2XX-STEP*.md` (11 파일): 설계/분석 올바른 위치
- `contracts/contract_*.md` (78+ 파일): 계약 문서 올바른 위치
- `ops/` / `runbooks/`: 운영 정책 vs 런북 구분 정확
- `archive/` (13 파일): 폐기 문서 보관
- `SSOT/` (5 파일): 불변 원칙/결정
- `state/` (1 파일): 상태 기록
- `task_reports/` (25 파일): JSON 보고서

---

## 4. 실행 옵션

### 옵션 A — 최소 이동 (Claude 권장)

Category 1 만 이동. 확실히 잘못된 것만 고치고 사용자 판단 필요 항목은 건드리지 않음.

**작업**:
1. `git mv docs/P207_P208_P209_CLEAN_REFACTOR_PLAN.md docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`
2. `docs/handoff/P208_close_and_P209_handoff.md` line 9 경로 갱신
3. `docs/docs_inventory.md` 에 신규 entry 추가
4. commit + push

### 옵션 B — 최소 + JSON archive 이동

옵션 A + Category 2. inventory 의 "추가 검토 후보" 2건을 archive 로 이동 확정.

**추가 작업**:
5. `git mv docs/UI_MAP.json docs/archive/UI_MAP.json`
6. `git mv docs/UI_WIRING_DECISION_V1.json docs/archive/UI_WIRING_DECISION_V1.json`
7. `docs_inventory.md` 의 "추가 검토 후보" 섹션 → "Deprecated → Archive 이동 완료" 섹션으로 entry 이동

### 옵션 C — 옵션 B + walkthrough.md 현행화 결정

walkthrough.md 가 P146 시기 내용이라 현재 구조와 어긋날 가능성. 사용자 판단 필요.
- 옵션 C1: walkthrough.md 를 현행화 (내용 갱신)
- 옵션 C2: walkthrough.md 를 archive 로 이동 + README 에서 참조 제거
- 옵션 C3: 현상 유지 (내용 갱신 없이 레퍼런스 유지)

---

## 5. 구조 품질 관점 메모

### 잘된 점
- `docs_governance.md` 가 이미 4 카테고리 분류 체계 + 폴더 규칙을 정의해둠
- `docs_inventory.md` 가 각 파일의 분류/상태/조치를 명시
- `README.md` 가 Current Truth / Closeout / Reference 섹션으로 나뉘어 있음
- rule 9 (1 파일 1 기능) / rule 10 (경계 분리) 측면에서 **이 프로젝트의 docs 구조는 이미 잘 설계되어 있음**

### 이번에 발견한 문제 (1건)
- Claude 가 R1~R7 cleanup 중 생성한 `P207_P208_P209_CLEAN_REFACTOR_PLAN.md` 를 top-level 에 둠. 거버넌스 정책의 "설계 문서는 analysis/" 규칙 위반
- inventory 에도 등재되지 않음 (신규 문서 등재 절차 누락)

이 한 건만이 이번 세션 중 Claude 의 실책이며, 나머지 top-level 파일들은 모두 의도된 배치.

---

## 6. 실행 후 이 파일 처리 방침

옵션이 실행된 뒤에는:
- 이 파일 상단에 `> EXECUTED: <commit hash>` 라인 추가
- 이 파일 자체도 `docs/archive/readme_claude_<date>.md` 로 아카이브하거나, 또는 Current 상태로 유지하며 다음 감사 때 업데이트
- `docs_inventory.md` 에 이 파일 entry 추가 (category 미정 — meta 감사 노트는 현재 분류 체계에 완벽히 들어맞지 않음)

---

## 7. 다음 세션 Claude 를 위한 주석

만약 다음 세션 Claude 가 이 파일을 읽고 docs/ 를 정리하려 한다면:

1. 먼저 `docs_governance.md` + `docs_inventory.md` 를 다시 로드하여 이 파일 작성 이후 정책이 변경되지 않았는지 확인
2. 이 파일의 "4. 실행 옵션" 중 어느 것이 이미 실행되었는지 git log 로 확인 (`git log --all --oneline | grep "docs.*move\|docs.*cleanup"`)
3. 사용자 승인 없이 이동 작업을 개시하지 말 것 (rule 2)
4. 이동 후 반드시 `docs_inventory.md` 갱신 + cross-reference grep 으로 깨진 링크 탐지

---

작성 끝.
