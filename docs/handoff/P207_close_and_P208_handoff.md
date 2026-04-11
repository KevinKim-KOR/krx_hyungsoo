# P207 종료 결론 + P208 Hand-off 문서
> asof: 2026-04-10 (최초) / 2026-04-11 (P207 통합 layer cleanup 완료 갱신)
> 상태: P207 종료 / P208 진입 완료 / **P209-CLEAN R4 에서 P207 통합 layer cleanup 완료**

---

## P207 통합 layer cleanup 완료 (2026-04-11, R4/R5v3 적용)

P207-STEP7C 에서 `run_backtest.py` 에 처음 도입된 inline sweep 블록 및
`format_result` meta fallback 패턴이 P208/P209 까지 누적되어, rule 9 (1 파일
1 기능) 와 rule 6/7 (암묵 fallback 금지) 를 위반하는 god file 이 되었다.

P209-CLEAN-R4 에서 이 P207 통합 layer 를 `app/backtest/reporting/allocation_constraints/`
신규 패키지로 완전 추출:

- `sweep.py`: allocation_experiments 실행 로직 (run_backtest.py 에 inline 으로 약 115줄 있던 블록 이전)
- `report_writer.py`: `allocation_constraint_compare.md/.csv` 생성
- `diagnostic.py`: PROMOTE/REJECT 판정 (`allocation_experiment_verdict`)
- `meta_builder.py`: `format_result` 의 P207 meta 필드 8개 빌더 (`build_allocation_meta`)

`run_backtest.py` 의 `run_cli_backtest` 에서 P207 sweep 블록 제거 → 패키지
호출 1줄로 축소. `format_result` 의 P207 meta inline 제거 → `**build_allocation_meta(result)` 주입.

R5v3 에서 `meta_builder.build_allocation_meta` 의 silent fallback (`result.get("allocation_mode", "bucket_portfolio")` 등) 을 모두 제거하고
필수 필드는 KeyError raise, optional 필드는 explicit None 처리로 변경.

Behavior 는 완전 보존 (byte-level): `allocation_constraint_compare.csv` MD5 일치,
`backtest_result.json` 의 P207 allocation meta 필드 8개 모두 완전 일치.

## P207+P208+P209 전체 cleanup 완료 (2026-04-11)

R1~R6 완료 + R7 최종 검증 통과.

- R1: `evidence_writer.py` 추출 (P207+P208+P209 evidence 통합)
- R2: `drawdown_contribution.py` 1064줄 → `drawdown/` 패키지 7모듈
- R3: `holding_structure_compare.py` 378줄 → `holding_structure/` 패키지 4모듈
- R4: `allocation_constraints/` 신규 패키지 (P207 cleanup 본 항목)
- R5 (v1→v2→v3): reporting 전체 fallback 전수 정리, critical path silent fallback 0
- R6: `workflow.py` / `parameter_editor.py` 의 P207/P208/P209 inline 렌더링 ~290줄 → `views/helpers/` 3 helper

다음 챕터 (`P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1` 또는
`P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1`) 진입 시 이 정리된 구조 위에서
시작한다.

---

## 0. 이 문서의 목적
이 문서는 새로운 세션의 GPT가
1) P206까지의 핵심 맥락을 이어받고,
2) P207 (Risk-Aware Allocation) 의 결과를 이해하고,
3) P208 (Holding Structure Redesign) 의 진입 근거와 결과를 즉시 파악할 수 있도록 하기 위한 hand-off 문서다.

---

## 1. P207 결론 (Risk-Aware Allocation 챕터)

### 1.1 무엇을 했는가
P206 종료 시점에서 "타이밍 미세조정만으로는 MDD<10% 벽을 못 깬다"는 결론에 따라, P207은 포트폴리오 엔지니어링 챕터로 진입했다.

P207-STEP7A → P207-STEP7C-FIX4까지 다음을 구현했다:
- `risk_aware_equal_weight_v1` allocation mode 도입 (volatility 기반 비중 클램프 + floor/cap)
- `inverse_volatility_v1` allocation mode (참조용)
- `dynamic_equal_weight` 와 비교 가능한 sweep 구조 (`allocation_experiments`)
- `allocation_constraint_compare.csv/.md` 산출물
- `allocation_rebalance_trace`: 리밸런스별 raw_scores, raw_vols, pre/post-cap weights 노출
- evidence/UI에 allocation experiment name, fallback flag, last rebalance trace 표시

### 1.2 P207 SSOT (최우선 근거)
최신 운영 기준은 다음과 같이 고정되었다:
- `allocation.mode = risk_aware_equal_weight_v1`
- `weight_floor = 0.35`, `weight_cap = 0.65`
- `volatility_lookback = 20`, `volatility_floor = 0.05`, `volatility_cap = 0.6`
- `fallback_mode = dynamic_equal_weight`

이 SSOT 기준으로 최신 evidence 성능:
- `CAGR ≈ 12.59%`
- `MDD ≈ 12.76%`
- `Sharpe ≈ 1.154`
- `Verdict = REJECT`

### 1.3 무엇이 실패했는가
risk_aware_equal_weight 구조 자체는 잘 동작했지만, 운영 SSOT 성능은 다음과 같이 평가되었다:
- CAGR > 15 미달
- MDD < 10 미달

즉 "동일비중에서 위험 인식형 비중으로 바꾸는 것"만으로는 두 기준을 모두 통과시키지 못했다.

### 1.4 종료 사유
P207은 allocation 챕터로서 충분히 실험했다. weight_floor/cap, volatility lookback, inverse_volatility 등의 변형으로 trade-off가 옮겨갈 뿐 두 기준을 동시에 만족시키지 못했다.

따라서 P207은 **allocation 엔지니어링 챕터로서 종료**한다.

---

## 2. P208 진입 근거

P206 핸드오프의 교훈 ("무엇을 얼마나 들고 있어야 덜 아플까") 중 P207에서는 "어떤 비중으로"를 다뤘다. P208에서는 "얼마나 (몇 종목을)" 을 다룬다.

핵심 가정:
- 현재 SSOT는 `position_limits.max_positions = 2`로 매우 집중 보유 구조
- max_positions가 실제 병목인지, 보유 수 확대가 MDD 감소로 이어지는지 정량 검증 필요
- 이번 챕터는 holding structure **검증** 챕터이며 allocation 개선 챕터가 아님

---

## 3. P208-STEP8A 구현 결과

### 3.1 구현 범위
`P208-STEP8A-HOLDING-STRUCTURE-REDESIGN-V1`

`max_positions = 2/3/4/5` × `allocation_mode ∈ {dynamic_equal_weight, risk_aware_equal_weight_v1}` = 8개 비교군 (G1~G8) sweep 구조 구축.

### 3.2 수정/추가 파일
- 신규 모듈
  - `app/backtest/reporting/__init__.py`
  - `app/backtest/reporting/holding_structure_compare.py` — sweep + 비교 요약 생성기
- 수정
  - `app/utils/param_loader.py` — `holding_structure_experiments` 스키마 검증 + `_ALLOWED_HOLDING_ALLOC_MODES` (대표 2개만)
  - `state/params/latest/strategy_params_latest.json` — `holding_structure_experiments` 블록 8개 추가 (g1~g8)
  - `app/backtest/runners/backtest_runner.py` — `actual_held_positions_by_rebalance_date`, `avg_held_positions`, `max_held_positions_observed`, `rebalances_with_more_than_2_candidates`, `turnover_proxy` 추적 + result dict 노출
  - `app/run_backtest.py` — sweep 훅 (`run_holding_structure_sweep`) 추가, `format_result` 메타 확장, evidence md "Holding Structure (P208-STEP8A)" 섹션 추가
  - `pc_cockpit/views/parameter_editor.py` — Parameters 탭에 "Holding Structure (P208)" 섹션
  - `pc_cockpit/views/workflow.py` — Backtest 탭에 G1~G8 비교표 expander + caption
- 신규 산출물 (gitignore — 매 실행마다 재생성)
  - `reports/tuning/holding_structure_compare.md/.csv/.json`

### 3.3 SSOT는 그대로
P208-STEP8A는 분석/검증 챕터이므로 SSOT의 `position_limits.max_positions`는 여전히 `2`로 유지된다. 운영 baseline은 `g2_pos2_raew`에 매칭된다.

### 3.4 G1~G8 결과 (FIX1 반영 후, MDD 오름차순)

| Rank | Variant | Pos | Mode | CAGR | MDD | Sharpe | Avg Held | Blocked MaxPos | Verdict |
|---:|---|---:|---|---:|---:|---:|---:|---:|---|
| 1 | g2_pos2_raew | 2 | raew | 12.59% | 12.76% | 1.154 | 1.027 | 9 | REJECT |
| 2 | g1_pos2_eq | 2 | eq | 12.78% | 12.84% | 1.163 | 1.027 | 9 | REJECT |
| 3 | g5_pos4_eq | 4 | eq | **16.01%** | 13.09% | 1.427 | 1.892 | 9 | REJECT |
| 4 | g6_pos4_raew | 4 | raew | 16.00% | 13.10% | 1.427 | 1.892 | 9 | REJECT |
| 5 | g8_pos5_raew | 5 | raew | 15.48% | 13.47% | 1.384 | 2.297 | 6 | REJECT |
| 6 | g7_pos5_eq | 5 | eq | 15.48% | 13.47% | 1.384 | 2.297 | 6 | REJECT |
| 7 | g4_pos3_raew | 3 | raew | 13.46% | 15.00% | 1.184 | 1.487 | 3 | REJECT |
| 8 | g3_pos3_eq | 3 | eq | 13.57% | 15.02% | 1.190 | 1.487 | 3 | REJECT |

### 3.5 FIX1 라운드에서 보강된 3건
- `rebalances_with_more_than_2_candidates` 정의 교정: max_positions cap 이후가 아닌 **pre-cap 후보 풀** 기준으로 계산 (pos2도 22회로 정상 측정)
- `holding_structure_experiment_name` 자동 도출: SSOT 조합 매칭으로 main result에서도 `g2_pos2_raew` 표시
- compare summary Q1 문구 평균/합계 교정: `pos2 실험군당 평균 9회 (합 18회), pre-cap 후보>2 리밸런스=22회`

### 3.6 P208-STEP8A 진단 결과 (4개 질문 답변)
1. **Q1 max_positions=2 가 실제 병목이었는가**: pos2 BLOCKED_MAX_POSITIONS 평균 9회/실험군, pre-cap>2 리밸런스 22회 → **병목 존재**
2. **Q2 보유 수 확대가 MDD를 줄였는가**: 평균 MDD `pos2=12.80%, pos3=15.01%, pos4=13.10%, pos5=13.47%` → **단순 확대로는 MDD 감소 안 됨**. 오히려 pos3에서 악화
3. **Q3 CAGR 훼손폭은 허용 가능한가**: 평균 CAGR `pos2=12.68%, pos3=13.52%, pos4=16.00%, pos5=15.48%` → pos4에서 CAGR 15% 기준 통과 (+3.3%p 향상)
4. **Q4 다음 단계 기본 search space**: 자동 판정은 pos2 (MDD 최저), 단 어떤 구간도 MDD<10 달성 실패 → **단순 max_positions 튜닝이 아니라 종목 선정 품질 개선이 필요**

### 3.7 핵심 결론
- 보유 구조 확장만으로는 MDD<10% 목표 달성 불가
- pos4가 CAGR 16%로 최고지만 MDD 13.1%로 여전히 REJECT
- 다음 병목은 holding structure가 아니라 **selection quality / 개별 종목의 drawdown 기여** 쪽으로 이동
- 즉 다음 챕터(P209)는 "어떤 종목/선택이 drawdown을 키우는지" 분석으로 진행

---

## 4. 제약사항 준수

이번 챕터에서 절대 변경하지 않은 것:
- dynamic scanner / hybrid B+D / safe asset / cash policy
- objective / 승격 기준 (`CAGR > 15`, `MDD < 10`)
- Tune trial 수 / Tune 로직
- inverse_volatility 재도입 (대표 2개 mode만 사용)
- 새 UI 페이지 추가
- ML classifier

---

## 5. P209 진입 권장

다음 챕터 권장:
**`P209-STEP9A-DRAWDOWN-CONTRIBUTION-ANALYSIS-V1`**

설계 원칙:
- 분석 챕터. 필터/ML을 실제 매매 로직에 적용하지 않음
- 대표 2개 비교군(`g2_pos2_raew` 운영 기준 + `g5_pos4_eq` 연구 기준)에 대해
  - MDD window 내 종목별 drawdown 기여
  - 리밸런스별 선택 품질 (forward return)
  - bucket/group 수준 위험 요약
  - 다음 단계 필터 후보 규칙 초안 도출
- Track A (규칙기반 toxic asset filter) / Track B (ML classifier) 설계 근거 제공

---

## 6. P208 종료 시점의 SSOT (최신 상태)
- `params.position_limits.max_positions = 2`
- `params.allocation.mode = risk_aware_equal_weight_v1`
- `params.allocation.weight_floor = 0.35`, `weight_cap = 0.65`
- `params.holding_structure_experiments = [g1_pos2_eq, g2_pos2_raew, g3_pos3_eq, g4_pos3_raew, g5_pos4_eq, g6_pos4_raew, g7_pos5_eq, g8_pos5_raew]`
- main backtest 결과: `CAGR 12.5858%, MDD 12.7624%, Sharpe 1.1540, Verdict = REJECT`

---

## 7. 첨부 권장 파일
- `reports/tuning/holding_structure_compare.md`
- `reports/tuning/dynamic_evidence_latest.md`
- `state/params/latest/strategy_params_latest.json`
- `reports/backtest/latest/backtest_result.json`
