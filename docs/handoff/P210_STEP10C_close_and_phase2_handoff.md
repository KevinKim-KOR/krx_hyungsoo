# P210-STEP10C Track B Limit Verdict & Closeout + Phase 2 Hand-off

> asof: 2026-04-15
> 상태: **완료** — Track B closeout 공식 판정. canonical state/registry/ledger/handoff 동기화
> 직전 문서: [P210_STEP10A2_close_and_STEP10B_handoff.md](P210_STEP10A2_close_and_STEP10B_handoff.md)

---

## 1. 결론: Track B 는 승격 불가 축으로 종료

### 1.1 핵심 판정

| 항목 | 값 |
|---|---|
| `TRACK_B_STATUS` | `CLOSED_REJECTED` |
| `TRACK_B_CLOSEOUT_VERDICT` | Activated but did not improve MDD |
| `TRACK_B_LIMIT_REASON` | MDD not improved across activated variants |
| Best failed candidate | `B2_research_L1_softgate` (CAGR 14.74% / MDD 13.00% / Sharpe 1.4826) |
| `PROMOTION_STATUS` | DO_NOT_PROMOTE |

### 1.2 Do Not Promote 실험군

- `B1_research_L0_softgate`
- `B2_research_L1_softgate`
- `B3_research_L2_rerank`

### 1.3 Track B 단계별 누적 증거

| Step | 검증 | 결론 |
|---|---|---|
| Step10A | walk-forward LR + soft_gate 파이프라인 구축 | 구현 PASS / mts=200 > labeled=183 → no-op |
| Step10A-2 | mts=50/75/100 relaxation | 활성화 성공 (mts=100 soft_gate 5회). CAGR −0.75%p 허용 가능. **MDD 미개선** |
| Step10B | label_profile (L0/L1/L2) × action_policy (softgate/rerank) | positive_ratio 71% → 45.9% 축소 성공. L1 severe softgate CAGR 훼손 최소 (−0.49%p). **MDD 전 구간 동일값 불변** |
| Step10C | 위 3단계 closeout 공식화 | Track B 설계축 **MDD 개선 실패** → `CLOSED_REJECTED` |

### 1.4 최신 canonical 수치 snapshot (asof 2026-04-15)

| 역할 | 식별자 | CAGR | MDD | Sharpe | 판정 |
|---|---|---:|---:|---:|---|
| Main Run | `g2_pos2_raew` | 11.83% | 14.10% | 1.1522 | REJECT (운영 유지) |
| Research Baseline (pos3 no-guard) | `g4_pos3_raew` | 15.12% | 13.00% | 1.2521 | REJECT (MDD<10 미달) |
| Research Candidate | `B1_pos3_raew_pre_entry_guard` | 16.32% | 13.00% | 1.5456 | REJECT (MDD<10 미달) |
| Track B Latest (Best Failed) | `B2_research_L1_softgate` | 14.74% | 13.00% | 1.4826 | REJECT (DO_NOT_PROMOTE) |

`CAGR>15 AND MDD<10` 동시 충족 실험군 없음. Phase 1 엔진 축은 포화.

---

## 2. Step10C 에서 변경된 것

### 2.1 코드 (commit `f5607323`)

- `app/backtest/reporting/experiment_registry.py`
  - 모듈 상수: `TRACK_B_STATUS`, `TRACK_B_CLOSEOUT_VERDICT`, `TRACK_B_LIMIT_REASON`, `TRACK_B_DO_NOT_PROMOTE`, `PHASE_TRANSITION_NOTE`
  - `LAST_COMPLETED_CHAPTER = "P210-STEP10C"`, `NEXT_PLANNED_CHAPTER` = Phase 2 진입 준비
  - state JSON 에 `track_b_status / track_b_closeout_verdict / track_b_limit_reason / do_not_promote / phase_transition_note` 필드 추가
  - registry row `CURRENT_TRACK_B_LATEST` → `closeout_tag=TRACK_B_CLOSED`, `promotion_eligibility=False`, `decision="Best failed Track B candidate; do not promote"`
  - ledger `P210C` chapter 추가
  - `patch_evidence_trackb_closeout` helper 신설 (evidence MD Track B 섹션 in-place closeout 주석)
  - `g4_pos3_raew` / `B1_pos3_raew_pre_entry_guard` decision 문구 정합 (최신 수치 기준)
- `app/backtest/reporting/handoff_pack.py` — manifest 에 closeout 4필드 추가
- `app/backtest/reporting/evidence_writer.py` — Track B 섹션 하단에 closeout 주석 inline
- `app/run_backtest.py` — `regenerate_canonical_only` 에 closeout patch hook
- `pc_cockpit/views/workflow.py` — state expander 상단 closeout metrics + phase transition info

### 2.2 변경하지 않은 것

- ML 모델 / label profile / action policy / feature set / min_train_samples / threshold
- allocation / holding / regime / scanner
- 전략 로직
- 운영 SSOT 자동 승격 경로

### 2.3 canonical 산출물 (sync-only 재생성)

- `reports/tuning/{current_strategy_state,experiment_registry,decision_ledger}.{md,json}`
- `reports/tuning/dynamic_evidence_latest.md` (상단 블록 + Track B 섹션 closeout 주석)
- `reports/handoff/latest/*` (mirror 동기화)

---

## 3. Phase 2 진입 가이드

### 3.1 다음 분기

**Phase 1 (current-engine validation) 완료 → Phase 2 진입 준비.** 이하 두 챕터 중 택일 또는 병행:

- **P211-STEP11A-FRIEND-SOURCE-RULE-EXTRACTION-V1**
  - 친구 프로젝트(`freiends_project/`) 의 규칙 / overlay 후보 추출
  - 현재 엔진에 이식 가능한 축 식별
- **P211-STEP11B-OPERATOR-UX-REDESIGN-V1**
  - 운영자 UX 재설계 (workflow / dashboard / 수기 실행 루프)
  - 현재 엔진 결과를 더 잘 활용할 수 있도록 인터페이스 개선

### 3.2 금지사항 (이월 고정)

- Track B 동일 축 micro-tuning 금지 (threshold / mts / label / action / model)
- `random_forest` / `xgboost` / deep learning 등 Track B 확장 추가 금지
- allocation / holding / regime / scanner 구조 변경 금지 (Phase 1 확정)
- Full Backtest / Tune 재실행 금지 (Phase 2 지시문 없이는)
- 새 UI 페이지 추가 금지
- 친구 소스 규칙 **직접 이식 금지** — 반드시 추출/분석 단계 (Step11A) 를 거쳐야 함

### 3.3 다음 세션 진입 시 읽을 것

1. [docs/MASTER_PLAN_CURRENT.md](../MASTER_PLAN_CURRENT.md) — 현재 위치
2. [docs/handoff/HANDOFF_REQUIRED_FILES.md](HANDOFF_REQUIRED_FILES.md) — 필수 파일 목록
3. 본 문서 (`P210_STEP10C_close_and_phase2_handoff.md`)
4. `reports/handoff/latest/handoff_manifest.json` — 최신 canonical snapshot
5. `reports/handoff/latest/current_strategy_state.json` — Track B closeout 필드 확인

---

## 4. 검증 체크리스트 (Step10C 완료 판정)

- [x] `current_strategy_state.json` 에 `track_b_status=CLOSED_REJECTED`, `do_not_promote` 3개, `phase_transition_note` 반영
- [x] `experiment_registry.json` CURRENT_TRACK_B_LATEST 가 `closeout_tag=TRACK_B_CLOSED`, `promotion_eligibility=False`
- [x] `decision_ledger.json` P210C chapter 추가
- [x] `dynamic_evidence_latest.md` 상단 `Last Completed Chapter = P210-STEP10C`, `Last Rejected Axis = Track B closeout ...`, Track B 섹션 하단 `_Step10C closeout: ... No further same-axis micro-tuning._`
- [x] `handoff_manifest.json` `track_b_closeout_status` / `do_not_promote_variants` / `phase_transition_note` 반영
- [x] handoff mirror 4-way 일치 (MDD 13.00% 전 필드)
- [x] decision 문구와 canonical 수치 정합 (g4: CAGR>15 통과+MDD<10 미달, B1: CAGR>15 통과+MDD<10 미달)
- [x] Full Backtest / Tune / sweep 재실행 없음 (sync-only)
- [x] `--regenerate-canonical-only` 재실행 가능 경로 확보
