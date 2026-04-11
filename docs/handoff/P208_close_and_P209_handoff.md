# P208 종료 결론 + P209 Hand-off 문서
> asof: 2026-04-11 (최초) / 2026-04-11 (P208/P209 cleanup 완료 갱신)
> 상태: P208 종료 / P209-STEP9A 진입 완료 / **P209-CLEAN R1~R7 완료 (cleanup 종결)** / Step9A baseline realignment 대기

---

## P208/P209 cleanup 완료 (2026-04-11, R1~R7)

P209-CLEAN refactor plan (`docs/analysis/P207_P208_P209_CLEAN_REFACTOR_PLAN.md`) 에
따라 R1~R7 총 7단계로 P207/P208/P209 통합 layer cleanup 완료.

### R1~R6 commit 이력 (총 8 commits)

1. `324e14d0` R1: evidence_writer.py 추출
2. `83aef3b4` R2: drawdown/ 패키지 분할 (1064줄 god module → 7 모듈)
3. `9b1a5be3` R3: holding_structure/ 패키지 분할 (378줄 → 4 모듈)
4. `45c8461b` R4: allocation_constraints/ 패키지 추출 (P207 cleanup)
5. `975771a5` R5: 암묵 fallback 초기 제거
6. `43d4d65c` R5v2: comprehensive fallback audit + remediation
7. `dd7bd62b` R5v3: drawdown/pipeline.py 잔존 silent fallback 3건 제거
8. `ce44fc6b` R6: view helpers 추출 (workflow/parameter_editor)

### 최종 구조 (app/backtest/reporting/)

```
app/backtest/reporting/
├── __init__.py
├── evidence_writer.py                (573줄, dynamic_evidence_latest.md)
├── allocation_constraints/           (P207 cleanup 신규)
│   ├── __init__.py
│   ├── sweep.py
│   ├── report_writer.py
│   ├── diagnostic.py
│   └── meta_builder.py
├── holding_structure/                (P208, R3 분할)
│   ├── __init__.py
│   ├── sweep.py
│   ├── verdict.py
│   ├── report_writer.py
│   └── diagnostic.py
└── drawdown/                         (P209, R2 분할)
    ├── __init__.py
    ├── window.py
    ├── positions.py
    ├── attribution.py
    ├── selection_quality.py
    ├── bucket_risk.py
    ├── pipeline.py
    └── report_writer.py
```

### 최종 구조 (pc_cockpit/views/)

```
pc_cockpit/views/
├── workflow.py                       (740줄 → 484줄, R6)
├── parameter_editor.py               (181줄 → 144줄, R6)
└── helpers/                          (R6 신규)
    ├── __init__.py
    ├── allocation_panel.py           (P207 렌더러)
    ├── holding_structure_panel.py    (P208 렌더러)
    └── drawdown_contribution_panel.py (P209 렌더러)
```

### Behavior 보존 (R7 최종 검증)

- `backtest_result.json` summary: CAGR=12.387 / MDD=12.7446 / Sharpe=1.1019 / total_return=41.8749
- 6개 산출물 모두 정상 생성 (byte-level identical, generated_at timestamp 만 차이)
- P207 allocation meta 8 필드 / P208 holding_structure meta 5+ 필드 / P209 drawdown meta 10+ 필드 모두 동일
- Full Backtest: G1~G8 (P208) + G1/G2A~D/G3 (P207) + A/B (P209) 전체 실행 정상

### R5 fallback 정책 (4 카테고리)

rule 6/7 (암묵 fallback 금지) 를 4개 카테고리로 분류하여 전수 적용:

1. **REQUIRED**: 필수 필드 → 누락 시 `KeyError`/`ValueError` raise
2. **OPTIONAL**: legitimate None → explicit `if x is None` 분기
3. **WHITELIST (display)**: 사용자 표시용 `'N/A'`/`'-'` → 모듈 level 주석
4. **WHITELIST (math)**: 수학적 정의 (미보유=0 등) → 인라인 주석

Critical path (meta_builder, analyze_variant, compute_ticker_contributions,
compute_selection_quality, compute_bucket_risk, _build_main_meta_injection,
_matches_main, write_dynamic_evidence, allocation_constraints.sweep): silent
fallback 0건. Display rendering 은 R6 에서 view helpers 로 추출된 후 whitelist
범위 내 유지.

### 다음 챕터 진입 조건

P209-CLEAN cleanup 이 완료되어 `P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`
또는 `P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1` 로 바로 진입 가능.

- **Baseline realignment**: `drawdown/pipeline.py` 의 `a_spec`/`b_spec` tuple
  (현재 g2_pos2_raew / g5_pos4_eq) 만 수정하면 됨. god module 전체를 건드릴
  필요 없음.
- **Track A toxic asset filter**: `drawdown/attribution.py` 와
  `drawdown/selection_quality.py` 만 import 해서 재사용 가능. 필터 로직은
  BacktestRunner.run 에 별도 훅으로 주입 (운영/실험 경계 유지).

---

## 0. 이 문서의 목적
이 문서는 새로운 세션의 GPT가
1) P208 (Holding Structure Redesign) 의 종료 사유를 이해하고,
2) P209-STEP9A (Drawdown Contribution Analysis) 의 진입 근거 및 결과를 파악하며,
3) 직후 진행할 `P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1` → `P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1` 로 즉시 이어받을 수 있게 하기 위한 hand-off 문서다.

---

## 1. P208 종료 결론

### 1.1 무엇을 했는가
P208-STEP8A에서 `max_positions = 2/3/4/5` × 대표 2개 allocation mode 8개 비교군(G1~G8)을 동일 dynamic universe / hybrid B+D / safe asset 정책 하에서 sweep 실행했다. 자세한 결과는 `docs/handoff/P207_close_and_P208_handoff.md` 를 참조한다.

### 1.2 무엇이 실패했는가
- 어떤 조합도 `MDD < 10%` 달성 실패
- pos4가 CAGR 16%로 최고지만 MDD 13.1%로 여전히 REJECT
- pos2 (운영) 는 MDD 12.76%로 가장 낮지만 CAGR 12.59%로 미달
- 보유 구조 확장만으로는 trade-off만 옮길 뿐 두 기준 동시 통과 불가

### 1.3 종료 사유
P208은 holding structure 챕터로서 충분히 검증했다. 단순 max_positions 튜닝으로는 문제 해결 불가가 명확하다. **다음 병목은 종목 선정 quality / 개별 종목의 drawdown 기여**로 이동했다.

---

## 2. P209 진입 근거

### 2.1 기본 원칙
- 분석 챕터로 시작 (Step9A). 필터/ML을 실제 매매 로직에 적용하지 않음
- 운영 baseline `g2_pos2_raew` 유지
- "어떤 종목/구간/선택이 drawdown을 키웠는지" 정량 분석 → Step9B (Track A 규칙기반) / Track B (ML) 설계 근거 확보

### 2.2 가설
- 동일 dynamic universe + 동일 regime 정책 하에서, 특정 종목이 반복적으로 MDD를 키우고 있을 가능성
- pos2의 집중 구조 때문에 toxic 종목이 들어오면 손실이 극대화될 가능성
- 해결책은 보유 구조 확대가 아니라 toxic 종목 자체를 거르는 selection 필터일 가능성

---

## 3. P209-STEP9A 구현 결과

### 3.1 구현 범위
`P209-STEP9A-DRAWDOWN-CONTRIBUTION-ANALYSIS-V1`

분석 대상 baseline:
- A (operational baseline) = `g2_pos2_raew` (현재 SSOT)
- B (research baseline) = `g5_pos4_eq` (CAGR 최고)

### 3.2 수정/추가 파일
- 신규 모듈
  - `app/backtest/reporting/drawdown_contribution.py` — 분석 모듈 (find_mdd_window, reconstruct_daily_positions, compute_ticker_contributions, compute_selection_quality, compute_bucket_risk, analyze_variant, run_analysis_pipeline, write_drawdown_contribution_report)
- 수정
  - `app/backtest/runners/backtest_runner.py` — `top_candidates_ranked` (max_positions cap 이전 상위 15 후보 + score) 를 `_rebalance_trace` entry에 저장 (Step9A selection_gap 계산용; 매매 로직과 무관)
  - `app/run_backtest.py` — `run_cli_backtest` 에 drawdown 분석 훅 추가 (main result 재사용 A + 별도 B 실행), `formatted["meta"]` 주입, evidence md "Drawdown Contribution (P209-STEP9A)" 섹션 추가
  - `pc_cockpit/views/workflow.py` — Backtest 탭에 "Drawdown Contribution Summary (P209-STEP9A, analysis-only)" expander (A vs B 요약 + side-by-side Top Toxic / Worst Events / Bucket Risk + 공통 toxic 하이라이트)
- 신규 산출물 (gitignore)
  - `reports/tuning/drawdown_contribution_report.md/.json/.csv`

### 3.3 알고리즘 핵심
- **MDD window 식별**: cummax 기반으로 (peak_date, trough_date) 추출
- **종목별 기여 attribution**:
  - daily per-ticker mark-to-market value 복원 (trades replay + close prices)
  - daily cash_flow per ticker 분리 추적 (P&L = ΔV − cash_flow)
  - 기여 = Σ (P&L_i,t / nav_(t-1))
  - 기여 합계 ≈ MDD return (수수료/슬리피지 노이즈 ~0.5%p)
- **선택 vs 비선택 비교** (FIX1 라운드 보강):
  - 리밸런스별로 cap 이전 상위 15 후보 중 비선택 top-5 추출
  - entry = 리밸런스일 close, exit = 다음 리밸런스 close
  - `selection_gap_pct = avg_unselected - avg_selected` (양수 = selection miss)
- **bucket / group**: 종목 → bucket 매칭, 매칭 안 되면 `dynamic_pool` 분류
- **Selection Quality Verdict**: HEALTHY / MIXED / DEGRADED (gap > +2%p이면 우선 DEGRADED)

### 3.4 주요 발견 (P209-STEP9A 결과, FIX2 반영 후)

**MDD Window**: `2024-06-20 → 2024-08-05 (32일)` — 2024년 8월 carry unwind 시점. A/B 동일.

**A (g2_pos2_raew) Top Toxic Tickers**:
| Rank | Ticker | Contribution | Share of MDD | Days |
|---:|---|---:|---:|---:|
| 1 | 102110 | -6.89% | 54.01% | 3 |
| 2 | 102970 | -4.94% | 38.68% | 3 |
| 3 | 396500 | -1.19% | 9.29% | 6 |
| 4 | 261240 | -0.19% | 1.51% | 6 |

**B (g5_pos4_eq) Top Toxic Tickers**:
| Rank | Ticker | Contribution |
|---:|---|---:|
| 1 | 102110 | -4.04% |
| 2 | 396500 | -3.84% |
| 3 | 102970 | -3.33% |
| 4 | 395270 | -2.05% |
| 5 | 091160 | -0.39% |

**A ∩ B 공통 Toxic**: `102110`, `102970`, `396500` — 보유구조 무관 반복 MDD 유발

**Selection Quality 비교**:
| Metric | A (pos2 raew) | B (pos4 eq) |
|---|---:|---:|
| MDD | 12.76% | 13.09% |
| positive_forward_ratio | 0.7368 | 0.8095 |
| avg_forward_return | 5.77% | 7.77% |
| avg_selection_gap_pct | **+0.4341%p** | **−2.859%p** |
| events_with_better_unselected | 10/16 | 6/16 |
| Verdict | HEALTHY | HEALTHY |

**핵심 인사이트**:
- A군(pos2)은 16개 비교 가능 이벤트 중 **10회(63%)에서 비선택 상위가 더 좋았음** → pos2 집중 구조가 더 좋은 momentum 상위 종목을 놓치는 패턴
- B군(pos4)은 gap이 −2.86%p → 보유 확대로 진짜 상위를 더 많이 포함
- 그러나 B군 MDD가 여전히 13.09%로 REJECT → **선택 품질 개선만으로는 부족, toxic 자체를 거르는 필터 필요**

### 3.5 FIX 라운드 요약
- **FIX1 (P1+P1+P2)**:
  - `compute_selection_quality` 에 비선택 상위 후보 forward return / gap 추가
  - `_summarize_selection_quality` 에 `avg_selection_gap_pct` / `events_with_better_unselected` 추가
  - `_selection_quality_verdict` 에 gap 임계값 추가
  - main meta `drawdown_analysis_comparison` 에 B군 데이터 주입
  - workflow.py 에 A vs B side-by-side UI 추가
- **FIX2 (P1)**:
  - main meta `drawdown_analysis_comparison` 에 `operational_/research_positive_forward_ratio`, `..._avg_forward_return_pct`, `..._events_with_better_unselected` 추가
  - workflow.py A vs B 비교 표의 B행 `positive_ratio` / `avg_fwd_pct` 채움 (이전엔 None)

---

## 4. 제약사항 준수 (P209-STEP9A)
- dynamic scanner / hybrid B+D / safe asset / cash policy / allocation / holding structure / objective / 승격 기준 / Tune trial 수 / ML / 예측 필터 / 새 UI 페이지 → 모두 미변경
- 메인 CAGR/MDD/Sharpe 변동 없음 (분석 전용)
- `top_candidates_ranked` 필드는 trace 진단용이며 `BacktestRunner.run()` 결정 로직과 무관

---

## 5. 다음 단계: 즉시 처리할 2건

### 5.1 `P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`
**전체 재실험이 아님**. 분석 baseline만 재정렬:
- A (operational) = `g2_pos2_raew` 유지
- B (research) = `g5_pos4_eq` → **`g4_pos3_raew`** 로 변경
- C (shadow) = `g3_pos3_eq` 선택적 보조표시
- baseline source 파라미터화 (하드코딩 금지)
- analysis-only 재생성 (Tune / holding_structure sweep 재실행 금지)
- 산출물: `dynamic_evidence_latest.md`, `drawdown_contribution_report.*`

### 5.2 `P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1`
realignment 완료 후 즉시 진입. 최신 A/B 기준 toxic ticker 후보를 Track A 규칙 (toxic asset drop / momentum crash filter / bucket exposure cap / individual stop) 으로 설계 및 실험.

---

## 6. P209-STEP9A 종료 시점의 SSOT (변동 없음)
- `params.position_limits.max_positions = 2`
- `params.allocation.mode = risk_aware_equal_weight_v1`
- main backtest: `CAGR 12.5858%, MDD 12.7624%, Sharpe 1.1540, Verdict = REJECT`
- `holding_structure_experiments` 8개 (P208 그대로)

---

## 7. 첨부 권장 파일
- `reports/tuning/drawdown_contribution_report.md`
- `reports/tuning/dynamic_evidence_latest.md` (P209 섹션 포함)
- `reports/tuning/holding_structure_compare.md`
- `reports/backtest/latest/backtest_result.json` (P209 메타 주입 확인)
- `state/params/latest/strategy_params_latest.json`
