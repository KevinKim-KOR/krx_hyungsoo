# HANDOFF_REQUIRED_FILES — 새 세션 진입 필수 읽기 목록

> asof: 2026-04-11
> 역할: 새 세션의 AI 가 프로젝트 현재 위치를 5분 안에 복원하기 위해 **반드시 읽어야 할 최소 집합**. "많이 읽기" 가 아니라 "최소 읽기" 원칙.
> 원칙: 파일 옆에 왜 읽는지 1줄 이유를 붙인다. 챕터 변경 시 이 문서를 같이 갱신한다.

---

## 0. 문서 목적

- 새 세션이 docs/ 전체를 스캔하지 않고도 **현재 진실원 → 현재 챕터 → 최신 산출물** 순서로 복원 가능하게 한다
- current truth vs closeout vs reference 경계를 강제한다 (잘못된 문서를 current 로 오독하는 실수 방지)

---

## 1. Always Read (새 세션 시작 시 무조건)

순서대로 읽는다.

| 순서 | 파일 | 왜 읽는가 |
|---:|---|---|
| 1 | [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md) | 현재 챕터 / 현재 Step / 운영 baseline / 최신 수치 / 다음 Step / 금지사항 (단일 진실원) |
| 2 | [../README.md](../README.md) | 문서 구조 진입 허브 |
| 3 | [../analysis/STEP_RESULTS_INDEX.md](../analysis/STEP_RESULTS_INDEX.md) | 과거 P204~현재 단계별 결과 인덱스 |
| 4 | **이 문서** ([HANDOFF_REQUIRED_FILES.md](HANDOFF_REQUIRED_FILES.md)) | 다음에 무엇을 더 읽어야 하는지 판단 |
| 5 | [../docs_governance.md](../docs_governance.md) | 문서 분류 체계 (current / closeout / reference / archive 경계) |
| 6 | [../SSOT/INVARIANTS.md](../SSOT/INVARIANTS.md) | 시스템 불변 원칙 6개 (매매 로직 제약) |
| 7 | [../SSOT/DECISIONS.md](../SSOT/DECISIONS.md) | 아키텍처 결정 6개 |
| 8 | [../structure_baseline.md](../structure_baseline.md) | 코드 구조 기준선 |

---

## 2. Current Chapter Read (현재 P209 챕터 진입 시)

현재 활성 챕터인 **P209 — Drawdown Contribution Analysis** 에서 작업할 때 추가로 읽는다.

| 파일 | 왜 읽는가 |
|---|---|
| [P208_close_and_P209_handoff.md](P208_close_and_P209_handoff.md) | P208 종료 사유 + P209-STEP9A 진입 근거 + R1~R7 cleanup 완료 기록 + Step9A Baseline Realignment / Step9B Track A 진입 조건 |
| [P207_close_and_P208_handoff.md](P207_close_and_P208_handoff.md) | P207 risk_aware_equal_weight 운영 전환 + P208 진입 근거 |
| [../analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md](../analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md) | R1~R7 cleanup 계획 + 결과 (god module 분할 / fallback 정책 / view helpers). **byte-level 보존** 원칙 |
| [../SSOT/TRAPS.md](../SSOT/TRAPS.md) | 반복되는 함정 패턴 (암묵 fallback / god module / critical path 오염) |

---

## 3. Latest Artifact Check (현재 상태가 살아있는지 확인)

docs/ 가 아닌 실제 산출물/파라미터. 읽기 전용 확인 용도 (수정 금지, gitignore 대상).

| 파일 | 왜 확인하는가 |
|---|---|
| `state/params/latest/strategy_params_latest.json` | 현재 SSOT — `max_positions`, `allocation.mode`, hybrid regime, `holding_structure_experiments` 8개 |
| `reports/backtest/latest/backtest_result.json` | main summary (CAGR/MDD/Sharpe) + P207/P208/P209 meta 주입 상태 |
| `reports/tuning/dynamic_evidence_latest.md` | P207/P208/P209 각 섹션 렌더링 확인 |
| `reports/tuning/drawdown_contribution_report.md/.json/.csv` | P209-STEP9A 분석 결과 |
| `reports/tuning/holding_structure_compare.md` | P208 G1~G8 비교 결과 |
| `reports/tuning/promotion_verdict.md/.json` | 현재 main verdict (REJECT) 확인 |

---

## 4. Selective / Optional Reference (필요 시)

범용 참조. 특정 상황에서만 읽는다.

| 파일 | 언제 읽는가 |
|---|---|
| [../SSOT/PROJECT_CONSTITUTION.md](../SSOT/PROJECT_CONSTITUTION.md) | 프로젝트 헌법적 원칙이 필요할 때 |
| [../SSOT/STATE_LATEST.md](../SSOT/STATE_LATEST.md) | **DEPRECATED** — 참고만, current 로 사용 금지 |
| [../contracts/contracts_index.md](../contracts/contracts_index.md) | 계약 문서 색인이 필요할 때 |
| [../OCI_EVIDENCE_RESOLVER_GUIDE_V1.md](../OCI_EVIDENCE_RESOLVER_GUIDE_V1.md) | OCI 운영자 가이드 (evidence resolver 관련) |
| [../walkthrough.md](../walkthrough.md) | **주의** — P146 시대 기준, 현재 구조와 일부 불일치 가능. 대체 자료 없을 때만 |
| [AI_HANDOFF_GUIDE.md](AI_HANDOFF_GUIDE.md) | AI 인계 메타 가이드 |
| [KRX_Alertor_SP_구현지시문.md](KRX_Alertor_SP_구현지시문.md) | 새 세션 SP 프롬프트 원본 |
| [../analysis/P204_MASTER_PLAN_vFinal.md](../analysis/P204_MASTER_PLAN_vFinal.md) | P204 설계 원칙 필요 시 |
| [../analysis/P205_STEP5A_Dynamic_Universe_Architecture.md](../analysis/P205_STEP5A_Dynamic_Universe_Architecture.md) | dynamic scanner 내부 구조 필요 시 |
| [../analysis/P206-STEP6I-HYBRID-BD-IMPLEMENTATION-V1.md](../analysis/P206-STEP6I-HYBRID-BD-IMPLEMENTATION-V1.md) | hybrid regime 내부 구조 필요 시 |
| [../analysis/P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1.md](../analysis/P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1.md) | risk-aware equal weight 내부 구조 필요 시 |

---

## 5. Do Not Read / 주의사항

### 5.1 절대 읽지 말아야 할 것
- `znotes/` — 사용자 지시로 AI 세션에서는 접근 금지

### 5.2 읽되 current truth 로 오인 금지
- `../archive/` 전체 — 모두 legacy 기록, 현행 반영 아님
- `P205_handoff_draft.md` — DEPRECATED (원위치 보존)
- `../SSOT/STATE_LATEST.md` — DEPRECATED (원위치 보존)
- `readme_claude.md`, `readme_gpt.md` — 특정 세션의 감사 메모. **장기 운영 기준 아님**

### 5.3 closeout 을 current 로 읽지 말 것
- `P204_closeout.md` / `P205_structure_closeout.md` / `HANDOFF_P204_ML.md` — 과거 종료 기록. 현재 상태는 [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md) 우선

### 5.4 "추가 검토 후보" 상태 파일 (현행 반영 여부 불명)
- `../UI_MAP.json`, `../UI_WIRING_DECISION_V1.json`, `../state/ui_tabs_audit.md` — 사용자 승인 전 건드리지 말 것

---

## 6. 갱신 규칙

- **챕터 변경 시** (P209 → P210 등): Section 2 의 "Current Chapter Read" 목록 전면 갱신
- **Step 종료 시**: Section 3 (Latest Artifact Check) 목록 검토
- **새 closeout 생성 시**: Section 2 에 추가
- **DEPRECATED 전환 시**: Section 5 로 이동
- 이 문서가 "최소 읽기 집합" 원칙을 어기고 커져가면 Section 을 재편한다
