# MASTER_PLAN_CURRENT — 현재 진행 플랜

> asof: 2026-04-15
> status: **P210-STEP10C Track B closeout 완료 / Phase 1 current-engine validation 종료 / Phase 2 진입 준비**
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

> P209 Track A (blacklist / contextual guard) 와 P210 Track B (ML classifier + label/action redesign) 양쪽을 모두 검증한 결과, 현재 엔진 축만으로는 `CAGR>15 AND MDD<10` 동시 충족 불가를 확정했다. **Phase 1 current-engine validation 종료**. 다음은 **Phase 2 진입** — 친구 소스 규칙 추출 (P211-STEP11A) 또는 operator UX 재설계 (P211-STEP11B).

---

## 2. 현재 챕터 / 현재 Step

| 항목 | 값 |
|---|---|
| Current Chapter | **P210 — Track B ML Closeout** |
| Current Step | **P210-STEP10C (완료)** — Track B `CLOSED_REJECTED`, canonical state/registry/ledger/handoff 동기화 |
| Status | Phase 1 엔진 축 포화 확정 / Track B 동일 축 micro-tuning 금지 / Phase 2 진입 준비 |
| 최신 commit | `f5607323` feat(P210-STEP10C): Track B limit verdict & closeout |

---

## 3. 최신 운영 baseline (SSOT)

현재 SSOT ([state/params/latest/strategy_params_latest.json](../state/params/latest/strategy_params_latest.json)):

| 항목 | 값 |
|---|---|
| `params.position_limits.max_positions` | **2** |
| `params.allocation.mode` | **`risk_aware_equal_weight_v1`** |
| `params.allocation.weight_floor` | 0.35 |
| `params.allocation.weight_cap` | 0.65 |
| dynamic scanner | P205 활성 |
| regime filter | P206 hybrid B+D (VIX 글로벌 + 069500 국내) |
| safe asset switching | 활성 |
| `holding_structure_experiments` | 8개 (G1~G8) 유지, 재실행 금지 |
| `tracka_contextual_guard_experiments` | 8개 (A0~A3 / B0~B3) 유지, 재실행 금지 |
| `trackb_predictive_risk_classifier_experiments` | 8개 (A0~A3 / B0~B3) **CLOSED_REJECTED** |

**운영 baseline 별명**: `g2_pos2_raew`.

---

## 4. 최신 대표 성능 수치 (canonical, asof 2026-04-15)

`reports/tuning/current_strategy_state.json` 기준:

| 역할 | 식별자 | CAGR | MDD | Sharpe | 판정 |
|---|---|---:|---:|---:|---|
| **Main Run** | `g2_pos2_raew` | 11.83% | 14.10% | 1.1522 | REJECT (운영 유지) |
| Research Baseline (pos3 no-guard) | `g4_pos3_raew` | 15.12% | 13.00% | 1.2521 | REJECT (MDD<10 미달) |
| **Research Candidate** | `B1_pos3_raew_pre_entry_guard` | 16.32% | 13.00% | 1.5456 | REJECT (MDD<10 미달) |
| **Track B Latest (Best Failed)** | `B2_research_L1_softgate` | 14.74% | 13.00% | 1.4826 | REJECT (DO_NOT_PROMOTE) |

**Phase 1 포화 확인**: `CAGR>15 AND MDD<10` 동시 충족 실험군 없음.

### Track B Closeout 상태 (P210-STEP10C)

- `TRACK_B_STATUS`: `CLOSED_REJECTED`
- `TRACK_B_CLOSEOUT_VERDICT`: Activated but did not improve MDD
- `TRACK_B_LIMIT_REASON`: MDD not improved across activated variants
- `DO_NOT_PROMOTE`: `B1_research_L0_softgate`, `B2_research_L1_softgate`, `B3_research_L2_rerank`

---

## 5. 절대 금지사항 / 불변조건

1. `holding_structure_experiments` 8개 재실행 금지 (P208 확정)
2. `tracka_contextual_guard_experiments` 8개 재실행 금지 (P209C 확정)
3. `trackb_predictive_risk_classifier_experiments` 재설계 / 미세조정 금지 (P210C closeout)
4. Track B 동일 축 확장 금지 — `random_forest` / `xgboost` / deep learning / threshold / mts / label / action 재탐색 금지
5. Tune trial 수 / objective / 새 UI 페이지 / 친구 소스 규칙 **직접** 이식 → Phase 2 지시문 없이는 미변경
6. god module 재생성 금지 — `app/backtest/reporting/` 의 `drawdown/`, `holding_structure/`, `allocation_constraints/` 패키지 구조 유지
7. Critical path silent fallback 금지 (rule 6/7 4 카테고리 정책 — REQUIRED/OPTIONAL/WHITELIST display/WHITELIST math)
8. 메인 CAGR/MDD/Sharpe 변동 금지 (Phase 2 는 entry 지시문 없이는 매매 로직 불변)
9. `znotes/` 접근 금지
10. `freiends_project/` 규칙을 **직접** 이식 금지 — 반드시 추출/분석 단계 (Step11A) 를 거쳐야 함

---

## 6. 이번 챕터 목표 (P210) — 완료

- Track B ML classifier 파이프라인 구축 ✅ Step10A (2026-04-13)
- `min_train_samples` relaxation 으로 activation 확인 ✅ Step10A-2 (2026-04-13)
- label profile × action policy 재설계 ✅ Step10B (2026-04-14)
- canonical state/registry/ledger/handoff realign ✅ Step10Z-3 (2026-04-15)
- Track B limit verdict & closeout 공식화 ✅ Step10C (2026-04-15)

---

## 7. 다음 Step (Phase 2 진입)

### 7.1 택일 또는 병행

#### `P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1`

- 친구 프로젝트 (`freiends_project/`) 의 규칙 / overlay 후보 **추출 분석** (직접 이식 금지)
- 현재 엔진에 이식 가능한 축 (entry / exit / filter / allocation overlay 등) 식별
- 이식 타당성 평가표 작성
- 산출물: `docs/analysis/FRIEND_SOURCE_EXTRACTION_V1.md` 또는 유사

#### `P211-STEP11B-OPERATOR-UX-REDESIGN-V1`

- 운영자 UX 재설계 (workflow / dashboard / 수기 실행 루프)
- 현재 엔진 결과 (Track B closeout / Research Candidate MDD 초과 등) 를 운영자가 더 잘 활용할 수 있도록 인터페이스 개선
- 산출물: `docs/analysis/OPERATOR_UX_REDESIGN_V1.md` 또는 유사

### 7.2 진입 전 준비

- `docs/handoff/P210_STEP10C_close_and_phase2_handoff.md` 읽기 (본 closeout 문서)
- `reports/handoff/latest/handoff_manifest.json` 으로 canonical snapshot 확인
- Phase 2 지시문 대기

---

## 8. 반드시 먼저 읽을 문서

새 세션 진입 순서 — 자세한 전체 목록은 [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) 참고:

1. **이 문서** ([MASTER_PLAN_CURRENT.md](MASTER_PLAN_CURRENT.md)) — 현재 위치
2. [handoff/P210_STEP10C_close_and_phase2_handoff.md](handoff/P210_STEP10C_close_and_phase2_handoff.md) — 최신 챕터 closeout + Phase 2 진입 가이드
3. [handoff/HANDOFF_REQUIRED_FILES.md](handoff/HANDOFF_REQUIRED_FILES.md) — 읽기 최소 집합
4. [analysis/STEP_RESULTS_INDEX.md](analysis/STEP_RESULTS_INDEX.md) — 과거 단계 결과 인덱스
5. [analysis/ROOT_SUSPICIOUS_PATHS_INVESTIGATION_V1.md](analysis/ROOT_SUSPICIOUS_PATHS_INVESTIGATION_V1.md) — root 정리 조사 (2026-04-15 기준)
6. [SSOT/INVARIANTS.md](SSOT/INVARIANTS.md) — 시스템 불변 원칙
7. [SSOT/DECISIONS.md](SSOT/DECISIONS.md) — 아키텍처 결정

---

## 9. 최신 확인 산출물

분석 결과가 살아있는지 확인할 파일 (git ignored):

- `reports/backtest/latest/backtest_result.json` — main summary
- `reports/tuning/dynamic_evidence_latest.md` — 상단 Step10C 요약 + Track B 섹션 closeout 주석
- `reports/tuning/current_strategy_state.{md,json}` — Track B closeout 필드 포함
- `reports/tuning/experiment_registry.{md,json}` — CURRENT_TRACK_B_LATEST 재해석
- `reports/tuning/decision_ledger.{md,json}` — P210C chapter
- `reports/tuning/predictive_risk_compare.{json,md,csv}` — Track B 비교표
- `reports/tuning/contextual_guard_compare.{json,md}` — Track A 비교표
- `reports/handoff/latest/*` — curated mirror + manifest + source_index
- `state/params/latest/strategy_params_latest.json` — SSOT

Sync-only regenerate 경로:

```
.venv/Scripts/python -m app.run_backtest --regenerate-canonical-only
```

Full Backtest / Tune 재실행 없이 canonical state/registry/ledger/handoff 만 재정렬한다.

---

## 10. 이 문서 갱신 규칙

- Step 종료 시 갱신 필수 (section 2, 4, 6, 7)
- 챕터 종료 시 section 1, 3, 5 재검토
- `STEP_RESULTS_INDEX.md` 와 함께 갱신 (현재 ↔ 과거 경계 유지)
- 과거 step 상세는 여기 쓰지 말고 `STEP_RESULTS_INDEX.md` 와 `docs/handoff/` 로 보낸다
