# Reports Folder Inventory
> asof: 2026-04-13
> 목적: `reports/` 하위 모든 산출물의 **생성 엔드포인트 / 생존 상태 / 요약** 정리
> 범위: `reports/**` 의 `latest/` + 최상위 파일만 분석.
> 제외:
> - `reports/*/snapshots/` (회차별 snapshot 아카이브 — 매 실행 누적 저장, 내용 분류는 `latest` 와 동일)
> - `reports/backtest/snapshots/`, `reports/tuning/snapshots/` 포함하여 전부
> - `reports/tuning/dynamic_universe_schedule_YYYYMMDD_HHMMSS.json` (매 실행 ephemeral 로그)
> - `reports/tune/telemetry/` (tune 실행별 telemetry 로그)
> - `reports/tickets/{dryrun,preflight,shadow}/*.json` (UUID 기반 티켓 아카이브)

---

## 0. 상태 판정 기준

| 상태 | 정의 |
|---|---|
| **LIVE** | 최신 backtest/scanner/tune/실험 파이프라인이 매 실행마다 갱신 |
| **RECENT** | 최근 3일 (≥2026-04-11) 내 생성. 현재 챕터 관련 |
| **STALE** | 7일 이상 미갱신. 과거 실험/감도분석 결과, 참고용 |
| **DEAD** | 60일 이상 미갱신. 파이프라인 단절 또는 엔드포인트 DEAD |
| **NOT_FOUND** | 파일은 존재하나 writer 엔드포인트를 grep 에서 찾지 못함 (inline 기록 또는 legacy) |

---

## 1. `reports/tuning/` — 핵심 전략 산출물

### 1.1 LIVE — 매 `--analysis-only` Full Backtest 시 재생성 (2026-04-13 23:52)

| 파일 | Endpoint | 상태 | 요약 |
|---|---|---|---|
| `dynamic_evidence_latest.md` | `app/backtest/reporting/evidence_writer.py` | **LIVE** | 종합 evidence. 상단에 Current Strategy Position 요약 블록, 각 챕터별 compare 표. Main Run + 모든 Track 결과 한눈에 확인 |
| `promotion_verdict.json/.md` | `app/run_tune.py` + `app/tuning/promotion_gate.py` + `evidence_writer.py` | **LIVE** | Main Run 의 CAGR>15 AND MDD<10 판정. 현재 REJECT |
| `drawdown_contribution_report.md/.json/.csv` | `app/backtest/reporting/drawdown/report_writer.py` | **LIVE** | P209A drawdown attribution. A/B/C baseline 의 MDD 기여 분석 |
| `contextual_guard_compare.md/.json/.csv` | `app/backtest/reporting/contextual_guard_compare.py` | **LIVE** | P209C Track A. 8 실험군 (pre-entry / early-stop / combined). B1 pre-entry 만 부분 유효 |
| `predictive_risk_compare.md/.json/.csv` | `app/backtest/reporting/predictive_risk_compare.py` | **LIVE** | P210A-2 Track B. 8 실험군 (mts=50/75/100 × A/B). 차선 = B3 mts100 (CAGR 15.93% / MDD 11.03%) |
| `predictive_risk_training_report.md/.json` | `app/backtest/reporting/predictive_risk_compare.py` | **LIVE** | ML 학습 보고서. label/feature/class_imbalance/leakage/importance |
| `experiment_registry.md/.json` | `app/backtest/reporting/experiment_registry.py` | **LIVE** | P210-STEP10Z. P206~P210A-2 전체 실험 11종 분류 (CURRENT_MAIN / CURRENT_RESEARCH_CANDIDATE / REJECTED / ANALYSIS_ONLY / HISTORICAL_REFERENCE) |
| `current_strategy_state.md` | `app/backtest/reporting/experiment_registry.py` | **LIVE** | 현재 기준선 한 장 요약 (Main Run / Research Candidate / Track B Latest / Rejected Axes / Next Chapter) |
| `decision_ledger.md` | `app/backtest/reporting/experiment_registry.py` | **LIVE** | P206~P210A-2 결정 사유 3줄 요약 |

### 1.2 LIVE — Tune 실행 시 재생성 (2026-04-13 23:51, 최근 `run_tune` 실행됨)

| 파일 | Endpoint | 상태 | 요약 |
|---|---|---|---|
| `tuning_results.json` | `app/run_tune.py` + `app/tuning/results_io.py` + `promotion_gate.py` | **LIVE** | Optuna trial 전체 결과 + promotion verdict |
| `tuning_summary.md` | `app/run_tune.py` | **LIVE** | Tune 실행 요약 (best/top N/segments) |
| `best_params_latest.json` | `app/run_tune.py` | **LIVE** | Optuna best trial 파라미터 |
| `best_score_latest.json` | `app/run_tune.py` | **LIVE** | Optuna best score |
| `best_trial_segments.csv` | `app/run_tune.py` | **LIVE** | best trial segment 평가 |
| `trials_top20.csv` | `app/run_tune.py` | **LIVE** | top 20 trial 결과 |
| `last_completed_trial.json` | `app/run_tune.py` | **LIVE** | 마지막 완료 trial (resume 용) |
| `study.sqlite3` | `app/run_tune.py` | **LIVE** | Optuna study DB (TPE sampler 영속화) |
| `universe_ab_summary.md/.json` | `app/run_tune.py` | **LIVE** | universe A/B 비교 요약 |
| `dynamic_risk_calibration_summary.md/.json` | `app/run_tune.py` | **LIVE** | 동적 리스크 캘리브레이션 요약 |

### 1.3 LIVE — Scanner 실행 시 재생성 (2026-04-13 23:51)

| 파일 | Endpoint | 상태 | 요약 |
|---|---|---|---|
| `universe_snapshot_latest.json` | `app/scanner/run_scanner.py` | **LIVE** | 동적 universe 스냅샷 (15종목) |
| `universe_feature_matrix_latest.csv` | `app/scanner/run_scanner.py` | **LIVE** | universe 후보군 feature matrix |
| `universe_selection_reason_latest.md` | `app/scanner/run_scanner.py` | **LIVE** | universe 선정 근거 설명 |
| `dynamic_scanner_smoke_result.json` | `app/scanner/run_scanner.py` | **LIVE** | scanner smoke test 결과 |

### 1.4 LIVE — Backtest 시 regime 파이프라인으로 생성

| 파일 | Endpoint | 상태 | 요약 |
|---|---|---|---|
| `hybrid_regime_schedule_latest.json/.csv` | `app/run_backtest.py` | **LIVE** | VIX+domestic hybrid regime 스케줄 (risk_on/neutral/risk_off) |
| `hybrid_regime_verdict_latest.json` | `app/run_backtest.py` + `evidence_writer.py` | **LIVE** | hybrid regime 판정 |
| `hybrid_regime_reason_latest.md` | `app/run_backtest.py` | **LIVE** | hybrid regime 근거 설명 |
| `hybrid_policy_compare.csv` | `app/run_backtest.py` | **LIVE** | hybrid policy B+D 비교 |
| `hybrid_policy_summary.md` | `app/run_backtest.py` | **LIVE** | hybrid policy 요약 |
(legacy 기본 regime 3종 — `regime_schedule_latest.*`, `regime_verdict_latest.json`,
`regime_reason_latest.md` — 생성 시각 2026-04-05 이므로 STALE. §1.6 참조.
현재는 `hybrid_regime_*` 가 유효한 활성 경로.)

### 1.5 STALE — 지난 실험 산출물 (이틀 이내, 현재 챕터 관련)

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `holding_structure_compare.md/.json/.csv` | 2026-04-12 15:48 | `app/backtest/reporting/holding_structure/report_writer.py` | **STALE** | P208. analysis_only 모드에서 sweep 스킵 중이라 갱신 안 됨. 결과 자체는 여전히 유효 (g4_pos3_raew 연구 baseline) |
| `allocation_constraint_compare.md/.csv` | 2026-04-12 15:48 | `app/backtest/reporting/allocation_constraints/report_writer.py` | **STALE** | P207. legacy sweep. Step9C+10A 실험 중 skip. 결과 유효 |
| `toxic_filter_compare.md/.json/.csv` | 2026-04-12 01:24 | `app/backtest/reporting/toxic_filter_compare.py` | **STALE** | P209B static drop. 실험 종료 후 기각 확정 |

### 1.6 STALE — 지난 감도 분석 (참고용, 재생성 안 함)

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `hybrid_bd_sensitivity_grid.csv` | 2026-04-09 | `app/tuning/hybrid_bd_sensitivity_scan.py` | **STALE** | P206 hybrid B+D 감도. 실험 종료 |
| `hybrid_bd_sensitivity_summary.md` | 2026-04-09 | 동일 | **STALE** | 감도 요약 |
| `regime_schedule_latest.json/.csv` | 2026-04-05 | `app/run_backtest.py` | **STALE** | legacy 기본 regime 스케줄. 현재 hybrid 로 대체 |
| `regime_verdict_latest.json` | 2026-04-05 | `app/run_backtest.py` | **STALE** | legacy 기본 regime 판정 |
| `regime_reason_latest.md` | 2026-04-05 | `app/run_backtest.py` | **STALE** | legacy 기본 regime 근거 |
| `fear_regime_reason_latest.md` | 2026-04-06 | NOT_FOUND | **STALE** | P206 VIX regime 근거. legacy |
| `fear_regime_schedule_latest.json/.csv` | 2026-04-06 | NOT_FOUND | **STALE** | P206 VIX schedule. legacy |
| `fear_regime_verdict_latest.json` | 2026-04-06 | NOT_FOUND | **STALE** | P206 VIX verdict. legacy |
| `fear_sensitivity_grid.csv` | 2026-04-06 | `app/tuning/fear_sensitivity_scan.py` | **STALE** | P206 VIX 감도 |
| `fear_sensitivity_summary.md` | 2026-04-06 | 동일 | **STALE** | 감도 요약 |
| `sensitivity_entry_threshold.csv` | 2026-03-28 | `app/tuning/sensitivity_scan.py` | **STALE** | P204 entry threshold 감도 |
| `sensitivity_volatility_period.csv` | 2026-03-28 | 동일 | **STALE** | P204 volatility period 감도 |
| `sensitivity_summary.md` | 2026-03-28 | 동일 | **STALE** | P204 감도 요약 |

---

## 2. `reports/backtest/latest/` — Backtest 실행 trace

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `backtest_result.json` | 2026-04-13 23:52 | `app/run_backtest.py` | **LIVE** | Main Run 대표 결과 + 전체 meta (scanner/regime/allocation/holding_structure/drawdown/toxic/guard/ML 메타 통합) |
| `metric_integrity_audit_latest.json` | 2026-04-13 23:52 | `app/run_backtest.py` | **LIVE** | metric 무결성 감사 |
| `dynamic_execution_trace_latest.json/.csv` | 2026-04-13 23:51 | `app/run_backtest.py` | **LIVE** | dynamic universe 실행 trace |
| `order_generation_trace_latest.json/.csv` | 2026-04-13 23:51 | `app/run_backtest.py` | **LIVE** | 주문 생성 trace |
| `reliability_check.json` | 2026-03-08 | `app/run_backtest.py` | **STALE** | Reliability 체크 (한달 전) |

---

## 3. `reports/live/` — Live 운영 파이프라인

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `live/cycle/latest/live_cycle_latest.json` | 2026-02-21 | `app/run_live_cycle.py` | **DEAD** | live cycle 로그 (2개월+ 미실행) |
| `live/execution_prep/latest/execution_prep_latest.json` | 2026-03-12 | `app/generate_order_plan.py` | **STALE** | 실행 준비 |
| `live/order_plan/latest/order_plan_latest.json` | 2026-03-12 | `app/generate_order_plan.py` | **STALE** | 주문 플랜 |
| `live/order_plan_export/latest/order_plan_export_latest.json` | 2026-03-12 | `app/generate_order_plan.py` | **STALE** | 주문 플랜 export |
| `live/manual_execution_ticket/latest/*.json/.csv/.md` | 2026-03-12 | `app/generate_order_plan.py` | **STALE** | 수동 실행 티켓 |
| `live/manual_execution_record/latest/manual_execution_record_latest.json` | 2026-02-17 | NOT_FOUND | **DEAD** | 수동 실행 기록 (2달+ 미갱신) |
| `live/reco/latest/reco_latest.json` | 2026-02-22 | `app/generate_reco_report.py` | **DEAD** | 추천 리포트 (2달+ 미갱신) |

→ 전반적으로 live/ 경로는 **현재 활성 챕터(P210)와 단절**. 백테스트 연구 중이므로 live 실행 안 됨.

---

## 4. `reports/oci/` + `reports/pc/` — OCI/PC 헬퍼

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `oci/holding_timing/latest/holding_timing_latest.json` | 2026-02-08 | NOT_FOUND | **DEAD** | OCI 보유 타이밍 (2달+) |
| `pc/holding_timing/latest/holding_timing_latest.json` | 2026-02-14 | `app/pc/holding_timing.py` | **DEAD** | PC 보유 타이밍 (2달+) |
| `pc/param_review/latest/param_review_latest.json/.md` | 2026-02-21 | `app/pc/param_review.py` | **DEAD** | PC 파라미터 리뷰 (2달+) |
| `pc/param_search/latest/param_search_latest.json` | 2026-02-08 | NOT_FOUND | **DEAD** | PC 파라미터 검색 (2달+) |

→ `pc/` / `oci/` 경로는 대부분 DEAD. 현재 연구 챕터에서 사용 안 함.

---

## 5. `reports/ops/` — Ops 자동화 파이프라인

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `ops/daily/ops_report_latest.json` | 2026-01-31 | `app/run_ops_cycle.py` / `app/run_ticket_worker.py` | **DEAD** | ops 데일리 리포트 (2.5달+) |
| `ops/balance/balance_latest.json` | 2026-02-15 | NOT_FOUND | **DEAD** | 잔고 |
| `ops/summary/latest/ops_summary_latest.json` | 2026-03-28 | `app/run_live_cycle.py` / `app/run_ops_drill.py` | **STALE** | ops 요약 |
| `ops/summary/ops_summary_latest.json` | 2026-02-17 | 동일 | **DEAD** | 이전 위치의 legacy 복사본 |
| `ops/contract5/latest/ai_report_latest.json` | 2026-02-02 | NOT_FOUND | **DEAD** | AI 리포트 |
| `ops/contract5/latest/human_report_latest.md` | 2026-02-02 | NOT_FOUND | **DEAD** | 사람용 리포트 |
| `ops/drill/latest/drill_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | ops drill |
| `ops/evidence/health/health_latest.json` | 2026-02-15 | NOT_FOUND | **DEAD** | health evidence |
| `ops/evidence/index/evidence_index_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | evidence index |
| `ops/push/console_out_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | push console |
| `ops/push/preview/preview_latest.json` | 2026-02-16 | NOT_FOUND | **DEAD** | push preview |
| `ops/push/outbox/outbox_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | outbox |
| `ops/push/send/send_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | send 로그 |
| `ops/push/live_fire/live_fire_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | live fire |
| `ops/push/postmortem/*.json` | 2026-01-31 | NOT_FOUND | **DEAD** | postmortem |
| `ops/push/push_delivery_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | push delivery |
| `ops/push/holding_watch/latest/holding_watch_latest.json` | - | NOT_FOUND | **DEAD** | |
| `ops/push/spike/latest/` | 2026-01-31 | NOT_FOUND | **DEAD** | spike |
| `ops/push/spike_watch/latest/` | 2026-02-01 | NOT_FOUND | **DEAD** | spike watch |
| `ops/scheduler/latest/ops_run_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | scheduler 로그 |
| `ops/secrets/self_test_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | secrets self-test |
| `ops/summary/evidence_click_proof_latest.json` | 2026-01-31 | NOT_FOUND | **DEAD** | evidence click proof |

→ `ops/` 경로 **대부분 DEAD (2달+)**. ops 자동화 파이프라인은 현재 연구 모드에서 완전히 정지 상태.

---

## 6. `reports/phase_c/`, `reports/push/`, `reports/tickets/`, `reports/tune/`

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `phase_c/latest/recon_daily.jsonl` | 2026-01-31 | NOT_FOUND | **DEAD** | phase_c 정찰 |
| `phase_c/latest/recon_summary.json` | 2026-01-31 | NOT_FOUND | **DEAD** | 동일 |
| `phase_c/latest/report_ai.json` | 2026-01-31 | NOT_FOUND | **DEAD** | |
| `phase_c/latest/report_human.json` | 2026-02-02 | NOT_FOUND | **DEAD** | |
| `push/latest/push_messages.json` | 2026-01-31 | NOT_FOUND | **DEAD** | push 메시지 legacy |
| `tickets/dryrun/*.json` | - | NOT_FOUND | **DEAD** | 티켓 dryrun 아카이브 |
| `tickets/preflight/*.json` | - | NOT_FOUND | **DEAD** | 티켓 preflight 아카이브 |
| `tickets/shadow/*.json` | - | NOT_FOUND | **DEAD** | 티켓 shadow 아카이브 |
| `tune/latest/tune_result.json` | 2026-03-22 | NOT_FOUND | **STALE** | legacy tune 결과 (현재는 `tuning/` 경로 사용) |

---

## 7. `reports/` 루트

| 파일 | 생성 시각 | Endpoint | 상태 | 요약 |
|---|---|---|---|---|
| `active_surface_lint_result.json` | 2026-03-22 | NOT_FOUND | **STALE** | UI 노출 표면 lint 결과 (D 재정비 작업물) |
| `archive_rebuild_result.json` | 2026-01-31 | NOT_FOUND | **DEAD** | 아카이브 재구축 결과 |
| `smoke_result.json` | 2026-01-31 | NOT_FOUND | **DEAD** | smoke 테스트 결과 |

---

## 8. 요약 판정

### 현재 활성 엔드포인트 (매 실행마다 재생성)

| 카테고리 | Endpoint | 핵심 산출물 |
|---|---|---|
| Main Backtest | `app/run_backtest.py` | `backtest_result.json`, hybrid_regime 산출물 |
| Scanner | `app/scanner/run_scanner.py` | `universe_snapshot_latest.json`, feature matrix |
| Tune | `app/run_tune.py` | `tuning_results.json`, study.sqlite3, best params |
| Drawdown | `app/backtest/reporting/drawdown/report_writer.py` | `drawdown_contribution_report.*` |
| P209C Track A | `app/backtest/reporting/contextual_guard_compare.py` | `contextual_guard_compare.*` |
| P210A-2 Track B | `app/backtest/reporting/predictive_risk_compare.py` | `predictive_risk_compare.*`, training_report |
| P210-STEP10Z | `app/backtest/reporting/experiment_registry.py` | `experiment_registry.*`, `current_strategy_state.md`, `decision_ledger.md` |
| Evidence | `app/backtest/reporting/evidence_writer.py` | `dynamic_evidence_latest.md` (최상위 종합) |

### Legacy / Conditional 엔드포인트 (현재 챕터에서 sweep skip 중)

| 카테고리 | Endpoint | 상태 | 비고 |
|---|---|---|---|
| P207 Allocation | `app/backtest/reporting/allocation_constraints/report_writer.py` | **STALE** | analysis_only / Step9C+10A 존재 시 sweep skip. 마지막 산출물 2026-04-12 15:48 |
| P208 Holding | `app/backtest/reporting/holding_structure/report_writer.py` | **STALE** | 동일. 마지막 산출물 2026-04-12 15:48 |
| P209B Track A toxic | `app/backtest/reporting/toxic_filter_compare.py` | **STALE** | P209B 기각 확정 후 재실행 없음. 마지막 2026-04-12 01:24 |

### DEAD 경로 (60일 이상 미갱신)

- `reports/ops/` — ops 자동화 전체 정지 (push/scheduler/drill/secrets/contract5/evidence 등)
- `reports/live/cycle/`, `reports/live/reco/`, `reports/live/manual_execution_record/` — live 실행 정지
- `reports/pc/`, `reports/oci/` — PC/OCI helper 정지
- `reports/phase_c/`, `reports/push/`, `reports/tickets/` — 과거 챕터 아카이브
- `reports/smoke_result.json`, `reports/archive_rebuild_result.json` — legacy

→ 현재 연구 모드 (P210) 에서는 **`reports/tuning/` 과 `reports/backtest/latest/` 만 살아있음**.

### NOT_FOUND — grep 에서 writer 를 찾지 못한 파일

- `reports/tune/latest/tune_result.json` (legacy tune 경로)
- `reports/tuning/fear_regime_schedule_latest.json/.csv/.md`, `fear_regime_verdict_latest.json` (P206 Fear regime, 현재 hybrid 로 대체)
- `reports/ops/**` 대부분
- `reports/live/manual_execution_record/**`, `reports/live/reco/**`

→ inline 기록, legacy 코드 삭제, 또는 writer 가 외부 서비스/OCI backend 쪽에 있을 가능성.

---

## 9. 다음 세션에서 보면 되는 최소 증거 묶음

현재 P210-STEP10Z closeout 상태에서는 **3개 파일만 보면 현재 위치 파악 가능**:

1. **[current_strategy_state.md](../../reports/tuning/current_strategy_state.md)** — Main/Research/Rejected 1장 요약
2. **[experiment_registry.md](../../reports/tuning/experiment_registry.md)** — 11개 실험 분류표
3. **[dynamic_evidence_latest.md](../../reports/tuning/dynamic_evidence_latest.md)** — 최상위 evidence (Current Strategy Position 블록 포함)

나머지 compare 산출물은 특정 질문이 있을 때만 drill-down 용.
