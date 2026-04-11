# 문서 거버넌스 (Documentation Governance)

asof: 2026-04-11

## 문서 분류 체계

docs/ 내 모든 문서는 아래 4종 중 하나로 분류한다.

### A. Current Truth (현재 진실원)

현재 상태의 공식 기준 문서. 코드 변경 후 함께 갱신해야 한다.

- "지금 뭘 믿어야 하나?"에 답하는 문서만 둔다
- 현재 상태와 안 맞으면 안 된다
- 중복 설명 금지

### B. Closeout / Handoff (단계 종료 기록)

특정 단계 종료 시점의 스냅샷. 현재 상태 문서가 아니라 기록 문서.

- 나중에 덮어쓰지 않는다
- 그 시점 기록으로만 보존한다
- current truth와 혼동되지 않게 제목/서두에 성격 명시

### C. Reference / Contract (참고/계약)

버전 계약, 스키마, 분석 참고 문서.

- 계약/분석 목적 유지
- 현재 구조 안내문 역할은 하지 않음

### D. Deprecated / Archive (비활성)

현재 기준으로 더 이상 공식 참조 대상이 아닌 문서.

- archive 폴더 이동 또는 문서 상단에 DEPRECATED 명시
- current truth처럼 보이면 안 된다

---

## 현재 공식 진실원 목록 (Current Truth)

| 문서 | 역할 |
|---|---|
| `docs/README.md` | docs 진입 허브 (3축 핵심 문서로 유도) |
| `docs/MASTER_PLAN_CURRENT.md` | 3축 #1 — 현재 챕터 / 운영 baseline / 금지사항 / 다음 Step |
| `docs/analysis/STEP_RESULTS_INDEX.md` | 3축 #2 — P204~현재 단계별 결과 인덱스 |
| `docs/handoff/HANDOFF_REQUIRED_FILES.md` | 3축 #3 — 새 세션 진입 필수 읽기 목록 |
| `docs/structure_baseline.md` | 코드 구조 기준선 |
| `docs/SSOT/INVARIANTS.md` | 시스템 불변 원칙 6개 |
| `docs/SSOT/DECISIONS.md` | 아키텍처 결정 기록 |
| `docs/contracts/contracts_index.md` | 계약 문서 색인 |
| `docs/docs_governance.md` | 문서 거버넌스 (이 문서) |
| `docs/docs_inventory.md` | 문서 분류표 |

---

## 3축 핵심 문서 관리 규칙 (2026-04-11 신설)

새 세션 진입용 핵심 문서는 아래 3축으로만 관리한다. 이 외 문서는 top-level `docs/` 에 추가하지 않는다.

| 축 | 문서 | 갱신 시점 |
|---|---|---|
| 1. 전체 플랜 | `docs/MASTER_PLAN_CURRENT.md` | 현재 챕터 / Step 변경 시, 매 Step 종료 시 |
| 2. 단계별 성과 | `docs/analysis/STEP_RESULTS_INDEX.md` | 모든 Step 종료 시 (1행 추가/갱신) |
| 3. 인계 읽기 | `docs/handoff/HANDOFF_REQUIRED_FILES.md` | 챕터 변경 시 (Current Chapter Read 섹션 갱신) |

필수 원칙:

- top-level `docs/` 는 최소 집합만 유지 — 설계/성과 문서는 `analysis/`, closeout/인계는 `handoff/` 로 보낸다
- Current Truth 와 audit memo (`readme_claude.md`, `readme_gpt.md` 등 세션 감사 메모) 를 구분한다 — audit memo 는 장기 운영 기준 문서로 승격하지 않는다
- closeout 문서를 current truth 로 읽지 않는다 — 3축 문서가 우선

---

## 소스 수정 후 문서화 규칙

### 구조 변경 시

반드시 갱신:
- `structure_baseline.md`

### 단계(Phase/Step) 완료 시

반드시 생성:
- `docs/analysis/` 에 설계/성과문서 (P2XX-STEPXA-*.md)
- `docs/handoff/` 에 closeout/인계 문서 (필요 시)

### UI 구조/화면 흐름 변경 시

반드시 판단:
- 기존 UI 문서가 아직 current truth인지
- deprecated 처리해야 하는지

### 계약/API/산출물 변경 시

반드시 갱신:
- 관련 contract 문서
- 필요 시 contracts_index.md

---

## 문서 정리 판단 기준

문서별로 아래 3가지를 체크한다.

1. 현재 진실원인가?
2. 기록 문서인가?
3. 이미 낡았는가?

판정은 아래 4개 중 하나:
- `KEEP_CURRENT` — 현재 진실원으로 유지
- `KEEP_CLOSEOUT` — 기록 문서로 유지
- `KEEP_REFERENCE` — 참고/계약 문서로 유지
- `ARCHIVE_OR_DEPRECATE` — 비활성 처리

---

## Deprecated 처리 기준

### Deprecated 완료

- 문서 상단에 `> **DEPRECATED**` 배너가 실제로 추가된 문서만 해당
- inventory에서 "DEPRECATED 완료"로 집계 가능

### Deprecated 후보 (review later)

- 현재 구조와 불일치 가능성이 있으나 상단 배너가 아직 없는 문서
- inventory에서 "추가 검토 후보"로 별도 분리
- JSON/보조 파일은 상단 배너 추가가 불가능하므로, deprecated 완료로 간주하지 않는다

### 처리 규칙

- deprecated 후보와 deprecated 완료는 반드시 구분한다
- 상단 배너가 없는 문서를 inventory에서 deprecated 완료로 표기하지 않는다
- 후보 확인 후 deprecated로 확정하려면 해당 문서에 배너를 추가한 뒤 inventory를 갱신한다

---

## 폴더 구조 기준

| 폴더 | 용도 | 예시 |
|---|---|---|
| `docs/SSOT/` | 불변 원칙, 결정 기록, 프로젝트 헌법 | INVARIANTS.md, DECISIONS.md |
| `docs/analysis/` | 설계, 분석, 성과문서 (Phase/Step별) | P206-STEP6I-*.md, P207-STEP7A-*.md |
| `docs/archive/` | 폐기/레거시 문서 | legacy_*.md, phase_c_*.md |
| `docs/contracts/` | API/인터페이스 스펙, 계약 문서 | contract_*.md |
| `docs/handoff/` | 인계 스냅샷, closeout 문서, ZIP 아카이브 | HANDOFF_P204_ML.md, handoff_0403.zip |
| `docs/ops/` | 운영 정책, 매니페스트, 체크리스트 | push_policy_v1.md, artifact_governance.md |
| `docs/runbooks/` | 실행 절차서 (배포, 데일리, 라이브) | runbook_deploy_v1.md |
| `docs/state/` | 현재 상태 기록 | ui_tabs_audit.md |
| `docs/task_reports/` | 업무 완료 리포트 (JSON) | P172-Fix_report.json |

### 폴더 배치 규칙

- 설계/성과문서는 `analysis/`에 둔다. `handoff/`에 두지 않는다.
- runbook은 `runbooks/`에 통합한다. `ops/`에 두지 않는다.
- 인계용 스냅샷 ZIP은 `handoff/`에 둔다. 전개(unzip)하지 않는다.
- 스크립트, 로그 파일은 `task_reports/`에 두지 않는다.
