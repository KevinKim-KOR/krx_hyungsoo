# STEP_RESULTS_INDEX — 단계별 결과 인덱스

> asof: 2026-04-11
> 역할: P204 ~ 현재까지 각 Chapter/Step 이 무엇을 했고, 어떤 결과를 얻었고, 어떤 문서를 보면 되는지 요약하는 **인덱스**. 상세 내용은 반드시 링크된 원문을 참조한다.
> 상태 기준: `completed` (종료), `rejected` (실험 후 부결), `analysis_only` (분석 전용), `active` (진행 중)

---

## 0. 문서 목적

- 단계별 성과의 "단일 인덱스" — 각 Step 이 무엇을 했고, 성공/실패 여부, 그리고 원문 링크를 한 화면에서 제공
- 현재 활성 챕터는 [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md) 로 넘긴다
- 이 문서에 step 상세를 다시 장문으로 쓰지 않는다

---

## 1. 단계별 결과 테이블

| Chapter / Step | 목적 | 대표 결과 | Verdict | 상태 | 핵심 문서 | 비고 |
|---|---|---|---|---|---|---|
| **P204** | ML 튜닝 & reconnaissance | tune / promotion 파이프라인 확립 | PASS | completed | [P204_MASTER_PLAN_vFinal.md](P204_MASTER_PLAN_vFinal.md), [../handoff/P204_closeout.md](../handoff/P204_closeout.md), [../handoff/HANDOFF_P204_ML.md](../handoff/HANDOFF_P204_ML.md) | |
| **P205-STEP5A** | Dynamic ETF Universe Scanner | 월간 리밸런스 + dynamic pool | PASS | completed | [P205-STEP5A-DYNAMIC-SCANNER-DESIGN-V1.md](P205-STEP5A-DYNAMIC-SCANNER-DESIGN-V1.md), [P205_STEP5A_Dynamic_Universe_Architecture.md](P205_STEP5A_Dynamic_Universe_Architecture.md), [../handoff/P205_structure_closeout.md](../handoff/P205_structure_closeout.md) | 운영에 반영됨 |
| **P206-STEP6A** | Exogenous regime filter 초기 설계 | 탐색 | analysis_only | completed | [P206-STEP6A-EXOGENOUS-REGIME-FILTER-DESIGN-V1.md](P206-STEP6A-EXOGENOUS-REGIME-FILTER-DESIGN-V1.md) | 이후 6F/6H 로 승계 |
| **P206-STEP6C** | Fear index 기반 regime 설계 | 탐색 | analysis_only | completed | [P206-STEP6C-FEAR-INDEX-REGIME-DESIGN-V1.md](P206-STEP6C-FEAR-INDEX-REGIME-DESIGN-V1.md) | |
| **P206-STEP6F** | Hybrid global fear + domestic shock 설계 | 탐색 | analysis_only | completed | [P206-STEP6F-HYBRID-GLOBAL-FEAR-AND-DOMESTIC-SHOCK-DESIGN-V1.md](P206-STEP6F-HYBRID-GLOBAL-FEAR-AND-DOMESTIC-SHOCK-DESIGN-V1.md) | |
| **P206-STEP6H** | Hybrid policy 재설계 v2 | 탐색 | analysis_only | completed | [P206-STEP6H-HYBRID-POLICY-REDESIGN-V2.md](P206-STEP6H-HYBRID-POLICY-REDESIGN-V2.md) | |
| **P206-STEP6I** | Hybrid B+D 구현 (VIX + 069500) | 운영 반영 | PASS | completed | [P206-STEP6I-HYBRID-BD-IMPLEMENTATION-V1.md](P206-STEP6I-HYBRID-BD-IMPLEMENTATION-V1.md), [../handoff/P206_close_and_P207_handoff.md](../handoff/P206_close_and_P207_handoff.md) | 현재 운영 regime 로직 |
| **P206-STEP6J (SENSITIVITY)** | hybrid 파라미터 민감도 | 확정 | PASS | completed | [P206-STEP6J-SENSITIVITY-SCAN-V1.md](P206-STEP6J-SENSITIVITY-SCAN-V1.md) | |
| **P206-STEP6J (FIX)** | 리밸런스 날짜 스냅 FIX | 버그 수정 | PASS | completed | [P206-STEP6J-FIX-REBAL-DATE-SNAP-V1.md](P206-STEP6J-FIX-REBAL-DATE-SNAP-V1.md) | |
| **P207-STEP7A** | Risk-aware Equal Weight allocation 설계 | 운영 반영 (`risk_aware_equal_weight_v1`) | PASS | completed | [P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1.md](P207-STEP7A-RISK-AWARE-ALLOCATION-DESIGN-V1.md), [../handoff/P207_close_and_P208_handoff.md](../handoff/P207_close_and_P208_handoff.md) | weight_floor=0.35, weight_cap=0.65 |
| **P207-STEP7C / FIX1~FIX4** | Allocation experiment UI + evidence 강화 | 운영 UI + raw score 컬럼 | PASS | completed | [../handoff/P207_close_and_P208_handoff.md](../handoff/P207_close_and_P208_handoff.md) | allocation_experiment_name, raw_scores, evidence Raw Score 컬럼 |
| **P208-STEP8A** | Holding structure 실험 (G1~G8, `max_positions=2~5` × 2 allocation mode) | pos2 MDD 12.76 / pos4 CAGR 16 / MDD 13.1 | **REJECT (MDD<10% 미달)** | completed | [../handoff/P207_close_and_P208_handoff.md](../handoff/P207_close_and_P208_handoff.md), [../handoff/P208_close_and_P209_handoff.md](../handoff/P208_close_and_P209_handoff.md) | 보유 구조 확장만으로는 trade-off 이동뿐 |
| **P209-STEP9A** | Drawdown contribution / toxic ticker / selection quality / bucket risk 분석 | A∩B 공통 toxic `102110/102970/396500` / A selection_gap `+0.43%p` / B selection_gap `−2.86%p` | analysis_only — **toxic filter 필요** 근거 확보 | completed (FIX2) | [../handoff/P208_close_and_P209_handoff.md](../handoff/P208_close_and_P209_handoff.md) | MDD window `2024-06-20 → 2024-08-05`, baseline A=`g2_pos2_raew`, B=`g5_pos4_eq` |
| **P209-CLEAN R1~R7** | P207~P209 layer cleanup (god module 분할 / fallback 정책 적용 / view helpers 추출) | byte-level preserve: CAGR=12.387 / MDD=12.7446 / Sharpe=1.1019 | PASS | completed | [P207_P208_P209_CLEAN_REFACTOR_PLAN.md](P207_P208_P209_CLEAN_REFACTOR_PLAN.md), [../handoff/P208_close_and_P209_handoff.md](../handoff/P208_close_and_P209_handoff.md) | 8 commits (`324e14d0`~`ce44fc6b`), R5v1→v2→v3 반복 강화 |
| **P209-STEP9A-BASELINE-REALIGNMENT** | 분석 baseline 재정렬 (B: `g5_pos4_eq` → `g4_pos3_raew`, C: `g3_pos3_eq` 보조) | TBD | — | **active / 다음 step** | [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md#71-즉시-처리-p209-step9a-baseline-realignment-to-latest-ui-v1) | `drawdown/pipeline.py` 의 `a_spec`/`b_spec` tuple 만 수정, 재실행 금지 원칙 유지 |
| **P209-STEP9B-TRACKA** | Toxic asset drop / momentum crash filter / bucket exposure cap / individual stop | TBD | — | 다음 후보 | [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md#72-후속-p209-step9b-tracka-toxic-asset-drop-rules-v1) | `drawdown/attribution.py` + `drawdown/selection_quality.py` 재사용 |

---

## 2. 현재 활성 챕터

- **P209 — Drawdown Contribution Analysis**
- Step9A 분석 종료 + R1~R7 cleanup 종료
- 다음 Step: Step9A Baseline Realignment → Step9B Track A
- 상세: [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md)

---

## 3. Reject / Analysis-only 로 종료된 중요 챕터

### P208 (REJECT)
보유 구조 단순 확장으로는 `CAGR ≥ 15% + MDD ≤ 10%` 동시 통과 불가능함을 확정. pos2 는 MDD 최저지만 CAGR 미달, pos4 는 CAGR 최고지만 MDD 초과. 보유구조 diversification 만으로 해결 안 됨이 명확 → 다음 병목은 **종목 선정 quality / toxic 종목 기여** 로 이동.

### P206-STEP6A / 6C / 6F / 6H (analysis_only)
단계적 설계 반복. 최종적으로 STEP6I 의 hybrid B+D (VIX global + 069500 domestic) 에 통합됨.

---

## 4. 다음 진입 후보

| 후보 | 근거 | 비고 |
|---|---|---|
| **P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1** | Step9A 분석 baseline 이 최신 UI / G4 기준과 불일치 | 재실험 아님. `a_spec`/`b_spec` tuple 수정 |
| **P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1** | A∩B 공통 toxic 확정. 보유구조 무관 반복 유발 | realignment 완료 후 즉시 |
| (후속) P209-Track B (ML) | Step9B 규칙기반 결과에 따라 판단 | 미확정 |

---

## 5. 갱신 규칙

- Step 종료 시 1행 추가 또는 갱신
- Verdict / 상태 / 대표 결과 / 핵심 문서 링크 필수
- 상세 논의는 여기에 쓰지 않고 반드시 원문 링크로 연결
- 활성 챕터 섹션은 [../MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md) 와 동기화
