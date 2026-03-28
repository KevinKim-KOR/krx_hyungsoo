# 문서 분류표 (Documentation Inventory)

asof: 2026-03-28

분류 기준: [docs_governance.md](docs_governance.md)

## 핵심 문서

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
| `docs/contracts/*` (90+개) | KEEP_REFERENCE | 미전수검증 | 색인 기준 경로 일치 확인 | 유지 |
| `docs/ops/artifact_governance.md` | KEEP_REFERENCE | 정확 | 아티팩트 거버넌스 규칙 | 유지 |
| `docs/ops/runbook_*.md` (6개) | KEEP_REFERENCE | 미전수검증 | 운영 런북 | 유지 |
| `docs/runbooks/runbook_*.md` (6개) | KEEP_REFERENCE | 미전수검증 | 운영 런북 | 유지 |
| `docs/OCI_EVIDENCE_RESOLVER_GUIDE_V1.md` | KEEP_REFERENCE | 정확 | OCI 운영자 가이드 | 유지 |
| `docs/walkthrough.md` | KEEP_REFERENCE | 미확인 | 시스템 워크스루 | 유지 |

## Deprecated / Archive

| 경로 | 분류 | 상태 | 사유 | 조치 |
|---|---|---|---|---|
| `docs/README.md` | DEPRECATED | stale | 버전 10.2 (P204-STEP2) 표기, P205 미반영 | 상단 DEPRECATED 표시 |
| `docs/SSOT/STATE_LATEST.md` | DEPRECATED | stale | asof 2026-02-25, P204/P205 미반영 | 상단 DEPRECATED 표시 |
| `docs/UI_MAP.md` | DEPRECATED | stale | cockpit.py 라인 번호 기준, S2 분해 후 불일치 | 상단 DEPRECATED 표시 |
| `docs/UI_CATALOG_V1.md` | DEPRECATED | stale | cockpit.py 기반, S2 분해 후 views/ 구조와 불일치 | 상단 DEPRECATED 표시 |
| `docs/handoff/P205_handoff_draft.md` | DEPRECATED | 역할 종료 | P205 closeout 완료로 draft 역할 끝남 | 상단 DEPRECATED 표시 |
| `docs/task.md` | DEPRECATED | stale | P146~P150 시대 체크리스트, P204/P205 없음 | 상단 DEPRECATED 표시 |
| `docs/UI_MAP.json` | DEPRECATED | stale | UI_MAP.md와 동일 사유 | 상단 처리 불가 (JSON) |
| `docs/UI_WIRING_DECISION_V1.json` | DEPRECATED | 미확인 | 배선 결정 JSON, 현행 구조 반영 여부 불명 | 확인 후 판단 |
| `docs/state/ui_tabs_audit.md` | DEPRECATED | 미확인 | UI 탭 감사, S2 이전 기준 가능성 | 확인 후 판단 |
| `docs/archive/*` (9개) | KEEP_REFERENCE | 이미 보관됨 | phase_c 시리즈 히스토리 | 유지 (이미 archive) |
| `docs/task_reports/*` (20+개) | KEEP_REFERENCE | 이미 보관됨 | 작업 보고서 히스토리 | 유지 |

## 미전수검증 문서 참고

contracts/ 90+개, ops/ 런북, runbooks/ 런북은 파일 존재만 확인하고 내용은 전수 검증하지 않았다. 계약 내용 변경 시 해당 문서를 개별 확인해야 한다.
