# MASTER_PLAN_CURRENT — 현재 진행 플랜

> asof: 2026-04-11
> status: **P209-STEP9A 완료 (FIX2) / P209-CLEAN R1~R7 cleanup 완료 / Step9A Baseline Realignment 대기**
> 역할: 프로젝트 "전체 플랜"의 단일 진실원. 현재 위치 / 다음 단계 / 금지사항 / 최신 대표 수치를 한 화면으로 복원한다.

---

## 0. 문서 목적

새 세션의 AI 또는 사용자가 **5분 안에** 아래를 복원할 수 있게 한다:

1. 지금 어느 챕터/Step 인가
2. 운영 baseline / 최신 대표 수치
3. 다음에 무엇을 해야 하는가
4. 무엇을 건드리면 안 되는가
5. 어떤 문서를 먼저 읽어야 하는가

과거 히스토리 전체를 복원하는 문서가 아니다. 과거는 [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) 로 보낸다.

---

## 1. 현재 프로젝트 상태 한 줄 요약

> P208 holding structure 확장만으로는 MDD<10% 미달을 인정하고, P209 에서 drawdown 기여 분석으로 "toxic 종목 반복 유발" 을 정량 확인했다. 다음은 **Step9A baseline realignment** (분석 baseline 만 재정렬) → **Step9B Track A toxic drop 규칙 설계**.

---

## 2. 현재 챕터 / 현재 Step

| 항목 | 값 |
|---|---|
| Current Chapter | **P209 — Drawdown Contribution Analysis** |
| Current Step | **P209-STEP9A (완료, FIX2 반영) + P209-CLEAN R1~R7 cleanup 완료** |
| Status | 분석 산출물 확정 / 매매 로직 미변경 / Step9A Baseline Realignment 대기 |
| 최신 commit (cleanup 종결 시점 이후) | `c43ccd0c` docs: D2 — plan 이동 |

---

## 3. 최신 운영 baseline (SSOT)

현재 SSOT ([state/params/latest/strategy_params_latest.json](../state/params/latest/strategy_params_latest.json)):

| 항목 | 값 |
|---|---|
| `params.position_limits.max_positions` | **2** |
| `params.allocation.mode` | **`risk_aware_equal_weight_v1`** |
| `params.allocation.risk_aware_equal_weight.weight_floor` | 0.35 |
| `params.allocation.risk_aware_equal_weight.weight_cap` | 0.65 |
| dynamic scanner | P205 활성 |
| regime filter | P206 hybrid B+D (VIX 글로벌 + 069500 국내) |
| safe asset switching | 활성 |
| `holding_structure_experiments` | 8개 (G1~G8) 유지, 재실행 금지 |

**운영 baseline 별명**: `g2_pos2_raew` (P208 실험명 표기).

---

## 4. 최신 대표 성능 수치

P209-CLEAN R7 byte-level 검증 시점 기준 main `backtest_result.json` summary:

| 지표 | 값 |
|---:|---:|
| CAGR | **12.387%** |
| MDD | **12.7446%** |
| Sharpe | **1.1019** |
| total_return | 41.8749% |
| Verdict | **REJECT** (MDD<10% 미달) |

> 참고: P209-STEP9A 종료 시점 hand-off 기록은 `CAGR 12.5858% / MDD 12.7624% / Sharpe 1.1540` 이다. 이는 R1~R7 cleanup 전후 재실행 기준 차이이며, **동일 로직 / 동일 파라미터** 하에서 byte-level 동일 산출이 유지됨은 R7 에서 확인됨.

### P209-STEP9A 분석 전용 주요 발견
- MDD 구간: `2024-06-20 → 2024-08-05 (32일)` — 2024-08 carry unwind
- A ∩ B 공통 toxic: `102110`, `102970`, `396500` (보유 구조 무관 반복 MDD 유발)
- A (pos2 raew) Selection Quality: `avg_selection_gap_pct = +0.4341%p` (16개 이벤트 중 10건에서 비선택 상위가 더 좋았음) → pos2 집중 구조의 선택 miss 패턴 관찰
- B (pos4 eq) Selection Quality: `avg_selection_gap_pct = −2.859%p` (보유 확대가 상위 포함)
- **결론**: 선택 품질 개선만으로는 부족. **toxic 종목 자체를 거르는 필터 필요** → Step9B Track A 근거 확보

---

## 5. 절대 금지사항 / 불변조건

1. `holding_structure_experiments` 8개 재실행 금지 (P208 결과 확정)
2. P209 는 **분석 전용** — `BacktestRunner.run()` 결정 로직에 `top_candidates_ranked` 주입 금지
3. Tune trial 수 / objective / ML / 예측 필터 / 새 UI 페이지 → Step9B 진입 전까지 미변경
4. god module 재생성 금지 — `app/backtest/reporting/` 의 `drawdown/`, `holding_structure/`, `allocation_constraints/` 패키지 구조 유지
5. Critical path silent fallback 금지 (rule 6/7 4 카테고리 정책 — REQUIRED/OPTIONAL/WHITELIST display/WHITELIST math)
6. 메인 CAGR/MDD/Sharpe 변동 금지 (분석 챕터이므로 매매 로직 불변)
7. `znotes/` 접근 금지

---

## 6. 이번 챕터 목표 (P209)

- toxic asset 반복 유발 패턴을 **정량적으로** 확인 ✅ 완료 (Step9A FIX2)
- baseline realignment 로 최신 UI/G4 기준 재정렬 ⏳ 대기 (Step9A realignment)
- Track A 규칙 기반 toxic drop / momentum crash filter / bucket exposure cap / individual stop 설계 및 실험 ⏳ 대기 (Step9B)

---

## 7. 다음 Step (1~2개)

### 7.1 즉시 처리: `P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`

**전체 재실험 아님**. `drawdown/pipeline.py` 의 `a_spec` / `b_spec` tuple 만 수정:

- A (operational) = `g2_pos2_raew` 유지
- B (research) = `g5_pos4_eq` → **`g4_pos3_raew`** 로 변경
- C (shadow, 선택) = `g3_pos3_eq`
- baseline source 파라미터화 (하드코딩 금지)
- analysis-only 재생성 — Tune / holding_structure sweep 재실행 금지
- 산출물: `dynamic_evidence_latest.md`, `drawdown_contribution_report.*`

### 7.2 후속: `P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1`

realignment 완료 후 즉시 진입. 최신 A/B 기준 toxic ticker 후보를 Track A 규칙으로 설계.

- toxic asset drop
- momentum crash filter
- bucket exposure cap
- individual stop

구현 경계: `drawdown/attribution.py` + `drawdown/selection_quality.py` 만 import 해서 재사용. 필터 로직은 `BacktestRunner.run` 에 별도 훅으로 주입 (운영/실험 경계 유지).

---

## 8. 반드시 먼저 읽을 문서

새 세션 진입 순서 — 자세한 전체 목록은 [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) 참고:

1. **이 문서** ([MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md)) — 현재 위치
2. [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) — 읽기 최소 집합
3. [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) — 과거 단계 결과 인덱스
4. [handoff/P208_close_and_P209_handoff.md](handoff/P208_close_and_P209_handoff.md) — 현재 챕터 상세
5. [analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md](analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md) — R1~R7 cleanup 근거 (완료됨)
6. [SSOT/INVARIANTS.md](SSOT/INVARIANTS.md) — 시스템 불변 원칙
7. [SSOT/DECISIONS.md](SSOT/DECISIONS.md) — 아키텍처 결정

---

## 9. 최신 확인 산출물

분석 결과가 살아있는지 확인할 파일 (git ignored):

- `reports/backtest/latest/backtest_result.json` — main summary + P209 meta
- `reports/tuning/dynamic_evidence_latest.md` — P209 섹션 포함
- `reports/tuning/drawdown_contribution_report.md/.json/.csv`
- `reports/tuning/holding_structure_compare.md`
- `reports/tuning/promotion_verdict.md/.json`
- `state/params/latest/strategy_params_latest.json`

---

## 10. 이 문서 갱신 규칙

- Step 종료 시 갱신 필수 (section 2, 4, 6, 7)
- 챕터 종료 시 section 1, 3, 5 재검토
- `STEP_RESULTS_INDEX.md` 와 함께 갱신 (현재 ↔ 과거 경계 유지)
- 과거 step 상세는 여기 쓰지 말고 `STEP_RESULTS_INDEX.md` 로 보낸다
