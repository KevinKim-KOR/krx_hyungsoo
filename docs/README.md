# KRX Alertor Modular — 문서 진입 허브

> **Start Here** — 이 파일은 docs/ 폴더의 진입점입니다.
> 새 세션의 AI/사용자는 아래 **핵심 3문서** 부터 순서대로 읽으십시오.

---

## 0. 핵심 3문서 (필수 진입)

프로젝트 흐름 복원용 단일 진실원 3축. **다른 문서보다 우선 읽습니다.**

| 축 | 문서 | 역할 |
|---|---|---|
| 1. 전체 플랜 | [MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md) | 현재 챕터 / Step / 운영 baseline / 최신 수치 / 다음 Step / 금지사항 |
| 2. 단계별 성과 | [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) | P204 ~ 현재까지 단계별 결과 인덱스 |
| 3. 인계 읽기 목록 | [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) | 새 세션 진입 시 반드시 읽을 최소 집합 |

---

## 1. Current Chapter (현재 진행)

- **P209 — Drawdown Contribution Analysis**
- Step9A 분석 완료 (FIX2) / P209-CLEAN R1~R7 cleanup 완료
- 다음 Step: **Step9A Baseline Realignment → Step9B Track A (toxic drop)**
- 상세: [MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md) / [handoff/P208_close_and_P209_handoff.md](handoff/P208_close_and_P209_handoff.md)

---

## 2. Handoff Start (새 세션 진입 순서)

1. [MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md) — 현재 위치
2. [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) — 읽을 파일 목록
3. [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) — 과거 단계 인덱스
4. [handoff/P208_close_and_P209_handoff.md](handoff/P208_close_and_P209_handoff.md) — 현재 챕터 상세
5. [SSOT/INVARIANTS.md](SSOT/INVARIANTS.md) + [SSOT/DECISIONS.md](SSOT/DECISIONS.md) — 불변 제약

---

## 3. Current Truth (문서 거버넌스 축)

| 문서 | 역할 |
|---|---|
| [structure_baseline.md](structure_baseline.md) | 코드 구조 기준선 |
| [docs_governance.md](docs_governance.md) | 문서 분류 체계 + 갱신 규칙 |
| [docs_inventory.md](docs_inventory.md) | 전체 문서 분류표 |

---

## 4. Detailed References (필요 시)

| 문서 | 언제 읽는가 |
|---|---|
| [OCI_EVIDENCE_RESOLVER_GUIDE_V1.md](OCI_EVIDENCE_RESOLVER_GUIDE_V1.md) | OCI 운영자 가이드 |
| [contracts/contracts_index.md](contracts/contracts_index.md) | 계약 문서 색인 |
| [analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md](analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md) | P207~P209 cleanup 계획 (R1~R7 완료) |
| [analysis/P204_MASTER_PLAN_vFinal.md](analysis/P204_MASTER_PLAN_vFinal.md) | P204 설계 원칙 |
| [SSOT/PROJECT_CONSTITUTION.md](SSOT/PROJECT_CONSTITUTION.md) | 프로젝트 헌법 |
| [walkthrough.md](walkthrough.md) | 시스템 워크스루 (**P146 시대 — 일부 불일치 가능**) |

---

## 5. Closeout (과거 종료 기록 — current 로 오독 금지)

| 문서 | 기록 대상 |
|---|---|
| [handoff/P204_closeout.md](handoff/P204_closeout.md) | P204 ML 튜닝 종료 |
| [handoff/P205_structure_closeout.md](handoff/P205_structure_closeout.md) | P205 구조 정리 종료 |
| [handoff/P206_close_and_P207_handoff.md](handoff/P206_close_and_P207_handoff.md) | P206 종료 + P207 인계 |
| [handoff/P207_close_and_P208_handoff.md](handoff/P207_close_and_P208_handoff.md) | P207 종료 + P208 인계 |
| [handoff/P208_close_and_P209_handoff.md](handoff/P208_close_and_P209_handoff.md) | P208 종료 + P209 인계 (+R1~R7 cleanup) |

---

## 6. 폴더 구조

| 폴더 | 내용 |
|---|---|
| [analysis/](analysis/) | 설계/분석/성과 문서 + STEP_RESULTS_INDEX |
| [handoff/](handoff/) | 단계 종료 기록 + HANDOFF_REQUIRED_FILES |
| [SSOT/](SSOT/) | 불변 원칙, 결정, 헌법 |
| [contracts/](contracts/) | 스키마/계약 정의 |
| [ops/](ops/) | 운영 문서 |
| [runbooks/](runbooks/) | 운영 런북 |
| [state/](state/) | 상태 기록 |
| [task_reports/](task_reports/) | 작업 보고서 (JSON) |
| [archive/](archive/) | 비활성 / legacy 문서 |

---

## 7. 갱신 규칙

- Step 종료 시 [MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md) + [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) 동시 갱신
- 챕터 변경 시 [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) 의 "Current Chapter Read" 갱신
- 신규 문서 생성 시 [docs_inventory.md](docs_inventory.md) entry 추가 (거버넌스 규칙)
- closeout 문서는 current truth 로 승격하지 말 것
