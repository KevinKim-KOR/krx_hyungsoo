# 문서 분류표 (Documentation Inventory)

asof: 2026-03-28

분류 기준: [docs_governance.md](docs_governance.md)

## 핵심 문서 (Current Truth)

| 경로 | 분류 | 상태 | 사유 | 조치 |
|---|---|---|---|---|
| `docs/structure_baseline.md` | KEEP_CURRENT | 정확 | 코드 구조 기준선, asof 2026-03-28 | 유지 |
| `docs/SSOT/INVARIANTS.md` | KEEP_CURRENT | 정확 | 불변 원칙 6개 모두 유효 | 유지 |
| `docs/SSOT/DECISIONS.md` | KEEP_CURRENT | 정확 | 아키텍처 결정 6개 코드 반영됨 | 유지 |
| `docs/contracts/contracts_index.md` | KEEP_CURRENT | 정확 | 계약 색인, 경로 검증 완료 | 유지 |
| `docs/docs_governance.md` | KEEP_CURRENT | 신규 | 문서 거버넌스 규칙 | 유지 |
| `docs/docs_inventory.md` | KEEP_CURRENT | 신규 | 이 문서 | 유지 |

## Closeout / Handoff

| 경로 | 분류 | 상태 | 사유 | 조치 |
|---|---|---|---|---|
| `docs/handoff/P204_closeout.md` | KEEP_CLOSEOUT | 정확 | P204 종료 스냅샷, 검증 가능 | 유지 |
| `docs/handoff/P204_closeout.json` | KEEP_CLOSEOUT | 정확 | P204 종료 메타데이터 | 유지 |
| `docs/handoff/P205_structure_closeout.md` | KEEP_CLOSEOUT | 정확 | P205 구조 정리 종료 기록 | 유지 |
| `docs/handoff/HANDOFF_P204_ML.md` | KEEP_CLOSEOUT | 정확 | P204 ML 핸드오프 | 유지 |
| `docs/handoff/HANDOFF_P204_ML.json` | KEEP_CLOSEOUT | 정확 | P204 ML 핸드오프 메타 | 유지 |
| `docs/handoff/HANDOFF_P204_ML_CHECKLIST.md` | KEEP_CLOSEOUT | 정확 | P204 ML 체크리스트 | 유지 |

## Reference / Contract

| 경로 | 분류 | 상태 | 사유 | 조치 |
|---|---|---|---|---|
| `docs/analysis/P204_MASTER_PLAN_vFinal.md` | KEEP_REFERENCE | 정확 | P204 설계 원칙 참고용 | 유지 |
| `docs/analysis/friend_project_comparison.md` | KEEP_REFERENCE | 정확 | 친구 프로젝트 비교 분석 | 유지 |
| `docs/contracts/*` (78개) | KEEP_REFERENCE | 미전수검증 | 색인 기준 경로 일치 확인 | 유지 |
| `docs/ops/artifact_governance.md` | KEEP_REFERENCE | 정확 | 아티팩트 거버넌스 규칙 | 유지 |
| `docs/ops/runbook_*.md` (5개) | KEEP_REFERENCE | 미전수검증 | 운영 런북 | 유지 |
| `docs/runbooks/runbook_*.md` (6개) | KEEP_REFERENCE | 미전수검증 | 운영 런북 | 유지 |
| `docs/OCI_EVIDENCE_RESOLVER_GUIDE_V1.md` | KEEP_REFERENCE | 정확 | OCI 운영자 가이드 | 유지 |
| `docs/walkthrough.md` | KEEP_REFERENCE | 미확인 | 시스템 워크스루 | 유지 |
| `docs/archive/*` (13개) | KEEP_REFERENCE | 이미 보관됨 | phase_c 시리즈 히스토리 | 유지 |
| `docs/task_reports/*` (26개) | KEEP_REFERENCE | 이미 보관됨 | 작업 보고서 히스토리 | 유지 |

## Deprecated → Archive 이동 완료

아래 4개는 DEPRECATED 배너가 있던 문서로, `docs/archive/`로 이동 완료.

| 이전 경로 | 이동 후 | 사유 |
|---|---|---|
| `docs/README.md` | `docs/archive/README_legacy.md` | P204-STEP2 기준, P205 미반영 |
| `docs/UI_MAP.md` | `docs/archive/UI_MAP_legacy.md` | S2 분해 후 불일치 |
| `docs/UI_CATALOG_V1.md` | `docs/archive/UI_CATALOG_V1_legacy.md` | S2 분해 후 불일치 |
| `docs/task.md` | `docs/archive/task_legacy.md` | P146~P150 시대 |

아래 2개는 DEPRECATED 배너가 있지만 원위치 유지 (archive 이동 대상 아님).

| 경로 | 상태 | 사유 |
|---|---|---|
| `docs/SSOT/STATE_LATEST.md` | DEPRECATED (원위치) | SSOT 폴더 내 기록으로 보존 |
| `docs/handoff/P205_handoff_draft.md` | DEPRECATED (원위치) | handoff 폴더 내 기록으로 보존 |

`docs/README.md`는 새 현재 인덱스로 교체됨.

## 추가 검토 후보

아래 3개는 현재 구조와 불일치 가능성이 있으나, 상단 DEPRECATED 배너가 없으므로 별도 확인이 필요합니다.

| 경로 | 분류 | 상태 | 사유 | 조치 |
|---|---|---|---|---|
| `docs/UI_MAP.json` | ARCHIVE_OR_DEPRECATE | 미확인 | UI_MAP.md의 JSON 버전, S2 분해 후 불일치 가능 | 추가 검토 |
| `docs/UI_WIRING_DECISION_V1.json` | ARCHIVE_OR_DEPRECATE | 미확인 | 배선 결정 JSON, 현행 구조 반영 여부 불명 | 추가 검토 |
| `docs/state/ui_tabs_audit.md` | ARCHIVE_OR_DEPRECATE | 미확인 | UI 탭 감사, S2 이전 기준 가능성 | 추가 검토 |

## 미전수검증 문서 참고

contracts/ 78개, ops/ 런북 5개, runbooks/ 런북 6개는 파일 존재만 확인하고 내용은 전수 검증하지 않았다. 계약 내용 변경 시 해당 문서를 개별 확인해야 한다.
