# P209-STEP9B Track A Toxic Filter 종료 + P209-STEP9C Hand-off 문서
> asof: 2026-04-12
> 상태: P209-STEP9B **완료** (본 구현 + FIX 라운드) / P209-STEP9C 진입 대기
> 직전 문서: [P209_STEP9A_realignment_close_and_STEP9B_handoff.md](P209_STEP9A_realignment_close_and_STEP9B_handoff.md)

---

## 0. 이 문서의 목적

P209-STEP9B Track A Toxic Filter 챕터를 정식으로 종료하고, 다음 챕터
(`P209-STEP9C-TRACKB-PREP` 또는 `P209-STEP9C-TIGHTER-STOP`)로 넘기는
hand-off 문서다.

---

## 1. P209-STEP9B 종료 결론 (Track A 는 REJECT)

### 1.1 스코프
- A (operational baseline) = `g2_pos2_raew`
- B (research baseline) = `g4_pos3_raew`
- 6개 실험군 고정 (추가 금지): A0~A2 × B0~B2 = {none, primary_drop, extended_drop}
- primary_drop_list = `["102110", "102970"]` (Step9A 공통 toxic)
- extended_drop_list = `["102110", "102970", "395270", "396500"]` (shadow 포함 합집합)
- 필터 적용 위치: `selector_after_ranking_before_final_selection`
- 후보 부족 시: `leave_unfilled_risky_sleeve_as_cash`

### 1.2 최종 6개 실험군 결과 (MDD 오름차순, CAGR 내림차순)

| Rank | Variant | Baseline | Drop Mode | Drop List Size | Max Pos | CAGR | MDD | Sharpe | Avg Held | Filter Hits | Exhausted | Promoted | Verdict |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | `B0_pos3_raew_no_filter` | g4_pos3_raew | none | 0 | 3 | **15.95%** | **11.03%** | 1.4679 | 1.460 | 0 | 0 | 0 | REJECT |
| 2 | `A0_pos2_raew_no_filter` | g2_pos2_raew | none | 0 | 2 | 12.40% | 12.74% | 1.1027 | 1.054 | 0 | 0 | 0 | REJECT |
| 3 | `B1_pos3_raew_primary_drop` | g4_pos3_raew | primary_drop | 2 | 3 | 15.26% | 13.02% | 1.5035 | 1.405 | 15 | 9 | 6 | REJECT |
| 4 | `B2_pos3_raew_extended_drop` | g4_pos3_raew | extended_drop | 4 | 3 | 13.00% | 13.86% | 1.1809 | 1.405 | 31 | 9 | 22 | REJECT |
| 5 | `A1_pos2_raew_primary_drop` | g2_pos2_raew | primary_drop | 2 | 2 | 10.53% | 14.12% | 1.0413 | 1.000 | 13 | 8 | 7 | REJECT |
| 6 | `A2_pos2_raew_extended_drop` | g2_pos2_raew | extended_drop | 4 | 2 | 9.53% | 14.41% | 0.9199 | 0.919 | 24 | 8 | 18 | REJECT |

### 1.3 Q1~Q4 진단 (지시문 4개 질문 답변)

**Q1. Primary drop 만으로 MDD 개선되는가?**
- A baseline: 12.74% → **14.12% (Δ=-1.37%p, 악화)**
- B baseline: 11.03% → **13.02% (Δ=-1.99%p, 악화)**
- **답: 아니오.** primary drop 은 양쪽 baseline 모두 MDD 를 악화시킴.

**Q2. Extended drop 이 과도한 수익 훼손을 유발하는가?**
- A baseline: CAGR 10.53% → 9.53% (−1.00%p), MDD 14.12% → 14.41% (−0.30%p 추가 악화)
- B baseline: CAGR 15.26% → 13.00% (−2.26%p), MDD 13.02% → 13.86% (−0.85%p 추가 악화)
- **답: 네.** extended drop 은 수익을 추가로 훼손하면서 MDD 도 더 나빠짐.

**Q3. 운영 baseline vs 연구 baseline 중 어느 쪽이 필터 효과를 더 잘 흡수하는가?**
- 두 baseline 모두 필터 효과를 "흡수" 하지 못함 (모두 악화)
- 다만 A baseline 이 MDD 악화폭이 작음 (−1.37%p vs −1.99%p)
- **답: 어느 쪽도 흡수하지 못함.** Rule Set 자체가 유효하지 않음.

**Q4. Step9C 로 넘어가기 전 채택할 Rule Set 은?**
- **채택 실패**: 6개 실험군 중 `CAGR > 15 AND MDD < 10` 동시 충족 없음
- **차선 권고**: `B0_pos3_raew_no_filter` (baseline=`g4_pos3_raew`, drop_mode=`none`)
  — MDD 11.03%, CAGR 15.95%. 그러나 이것은 **필터 없음** 상태이므로 사실상 Rule Set 은 없음.
- **다음 단계 분기 근거**: Step9C (tighter stop) 또는 Track B (ML classifier) 로 전환 필요.

### 1.4 핵심 인사이트: 왜 Track A 가 실패했는가

가장 흥미로운 관찰:
1. **필터 없는 B0 가 실제로 최고 성과** (MDD 11.03%, CAGR 15.95%). Step9A drawdown 분석이 식별한 "toxic ticker" 는 MDD window 구간에서 손실을 몰아간 종목이지만, **그 외 기간에는 상승에 크게 기여**하는 종목이기도 했음.
2. **Exhaustion 발생 빈도 높음**: B 실험군은 9/30 리밸런스에서 후보 부족 (Exhausted), A 는 8/30. drop_list 가 커질수록 후보 풀이 작아지고 `leave_unfilled_risky_sleeve_as_cash` 정책으로 인해 현금 비중이 증가 → CAGR 훼손.
3. **Primary drop 도 수익성 저하**: 2개 ticker 만 빼도 MDD 악화 + CAGR 악화. 즉 "반복 toxic" 으로 보였던 것이 실은 **정상적인 momentum follow-up 이었고**, drop 하면 오히려 다음 상승 구간을 놓침.

→ **Step9A 의 "toxic ticker" 는 사후적 드로다운 기여 분석 결과이지, 사전 배제 기준으로는 유효하지 않음.** 이는 Track A 설계 가설 자체의 한계를 증명.

### 1.5 P209-STEP9B FIX 라운드 기록

본 구현은 1차 검증에서 블로커 다수로 미통과 판정을 받았고, 6건 FIX 라운드를 거쳐 완료됨.

**1차 지적 사항** (미통과):
1. **(A-1)** full run 에서 holding/allocation sweep 가 함께 재실행됨 → "holding structure 재실험 금지" 위반
2. **(A-2)** `dynamic_evidence_latest.md` 에 Track A 섹션 실제 반영 안 됨 (evidence 가 compare 보다 먼저 생성됨)
3. **(A-3)** evidence/panel 에 지시문 요구 필드 일부 누락 (Baseline Label, Drop List, Promoted Replacement Count 등)
4. **(A-4)** compare 리포트에 Baseline, Drop List Size, Avg Held 필드 없음
5. **(A-5)** Q4 Rule Set 채택/기각 결론 문구 부재
6. **(B-1)** `baseline_label` 허용 범위 loose (holding_structure_experiments 의 아무 이름이나 허용)
7. **(B-2)** 6개 실험군 고정 강제 없음 (param_loader 가 추가 실험군 차단 안 함)
8. **(B-3)** backtest_runner meta 전체 기록 미충족 (experiment_name, baseline_label, drop_mode, drop_list_used 등 누락)
9. **(B-4)** `black` 실제로 미통과 (param_loader.py reformat 대상)
10. **(B-5)** `toxic_filter_compare.py` 에 `except Exception` swallow 잔존
11. **(B-6)** `.get(k, default)` silent fallback 잔존 (toxic_filter_compare / toxic_filter_panel)

**FIX 해결 방식**:
| # | 해결 |
|---|---|
| A-1 | `run_backtest.py` 에서 toxic_filter sweep 을 evidence 생성 이전으로 이동. legacy P207/P208 sweep 은 `analysis_only` 플래그로 계속 차단. toxic_filter sweep 은 `analysis_only` 에서도 실행 (Step9B = 현재 챕터이므로) |
| A-2 | 실행 순서 재정렬: toxic_filter sweep → write_dynamic_evidence → (legacy sweeps skip). compare.json 이 먼저 생성되어 evidence 가 정상 반영 |
| A-3 | `evidence_writer._render_tracka_toxic_filter_section` 에 지시문 요구 필드 전체 (Baseline Label, Drop Mode, Drop List, Drop List Size, Filter Hits, Exhausted, Promoted Replacement, Avg Before/After, Verdict) 추가. Main Run Filter State 서브표 추가 |
| A-3 panel | `toxic_filter_panel.render_toxic_filter_panel_for_parameters` 에 baseline/drop_mode/실험군 DataFrame 표시 추가 |
| A-4 | `toxic_filter_compare._render_md` 에 Baseline, Drop List Size, Avg Held 컬럼 추가 + 정렬 설명 |
| A-5 | `_render_md` 의 Q4 섹션에 "채택" / "채택 실패 + 차선 권고 + 다음 단계 분기 근거" 결론 문구 출력 로직 추가 |
| B-1 | `param_loader._ALLOWED_TRACKA_BASELINE_LABELS = {"g2_pos2_raew", "g4_pos3_raew"}` 상수로 고정. 이 외 값은 즉시 ValueError |
| B-2 | `param_loader._REQUIRED_TRACKA_EXPERIMENT_NAMES` 6개 고정 집합. 누락/초과 시 ValueError |
| B-3 | `BacktestRunner.run` 에 `tracka_filter_experiment_name/baseline_label/drop_mode` 파라미터 추가 + result dict 에 `tracka_filter_experiment_name/baseline_label/drop_mode/drop_list_used/promoted_total` 모두 기록. `format_result` 가 main meta 로 주입 |
| B-4 | black 재실행 → 모든 파일 clean 확인 (`black --check` 통과) |
| B-5 | `toxic_filter_compare.run_toxic_filter_sweep` 의 `except Exception` 블록 제거. 실패는 즉시 propagate |
| B-6 | `_require_raw` 헬퍼 추가하여 raw result 에서 REQUIRED 필드 직접 subscript. `.get(k, default)` 제거. panel 의 display fallback 도 의미적 "데이터 없음" 표현으로만 유지 |

### 1.6 FIX 후 재검증 증거 (2026-04-12 00:34, `--analysis-only`)

**타임스탬프 검증**:
```
holding_structure_compare.md   23:51:13 ← 미갱신 (sweep 차단)
allocation_constraint_compare.md 23:51:17 ← 미갱신 (sweep 차단)
toxic_filter_compare.md        00:34:50 ← 재생성
toxic_filter_compare.json      00:34:50 ← 재생성
toxic_filter_compare.csv       00:34:50 ← 재생성
dynamic_evidence_latest.md     00:34:50 ← 재생성 (compare 이후)
backtest_result.json           00:34:46 ← 재생성
```

로그:
```
[P209-STEP9B] toxic_filter_compare 실험군 6개 실행
[P209-STEP9B] B2_pos3_raew_extended_drop: baseline=g4_pos3_raew drop_mode=extended_drop pos=3 CAGR=13.0012 MDD=13.8625 hits=31 exhausted=9 promoted=22
[P209-STEP9B] toxic_filter_compare 산출물 → reports/tuning
[WRITE] dynamic_evidence → reports/tuning/dynamic_evidence_latest.md
[P209-STEP9A] analysis_only=True — holding_structure sweep 스킵
[P209-STEP9A] analysis_only=True — allocation_experiments sweep 스킵
```

**main backtest_result.json Track A meta**:
```json
{
  "tracka_filter_experiment_name": null,
  "tracka_baseline_label": null,
  "tracka_drop_mode": "none",
  "tracka_drop_list_used": [],
  "tracka_filter_hits_total": 0,
  "tracka_filter_exhausted_count": 0,
  "tracka_promoted_total": 0,
  "tracka_avg_candidates_before_filter": null,
  "tracka_avg_candidates_after_filter": null,
  "tracka_dropped_by_rebalance_date": [],
  "tracka_promoted_by_rebalance_date": []
}
```
(main run 은 필터 미실행이므로 None / 0 / 빈 리스트. 명시적 "필터 없음" 의미)

**validator sanity check**:
- 6개 실험군 정확 일치 검증 통과
- baseline_label = g2_pos2_raew, g4_pos3_raew 만 허용 (g3_pos3_eq 입력 시 즉시 ValueError)

**정적 게이트**: black/flake8/py_compile 모두 pass.

---

## 2. 제약사항 준수 체크 (변경 없음)

| 금지사항 | 준수 |
|---|---|
| dynamic scanner 수정 | ✅ |
| hybrid B+D regime 수정 | ✅ |
| safe asset 수정 | ✅ |
| allocation 로직 수정 | ✅ |
| holding structure 재실험 | ✅ (sweep 차단) |
| Tune 재실행 | ✅ |
| ML classifier 적용 | ✅ |
| 확률 예측 필터 | ✅ |
| trailing stop 도입 | ✅ |
| 새 UI 페이지 | ✅ (기존 Parameters/Backtest/Evidence 탭 재사용) |
| objective / verdict 기준 수정 | ✅ |

---

## 3. 현재 SSOT 상태

`state/params/latest/strategy_params_latest.json` 의 `params` 하위:
- `position_limits.max_positions = 2` (운영 SSOT 유지)
- `allocation.mode = risk_aware_equal_weight_v1`
- `holding_structure_experiments` 8개 (P208 그대로)
- `drawdown_analysis_baselines` (P209-STEP9A): operational=g2, research=g4, shadow=g3
- **신규**: `tracka_toxic_filter` (primary/extended/apply_stage/reseat/on_exhausted)
- **신규**: `tracka_toxic_filter_experiments` (A0~A2, B0~B2 = 6개 고정)

main 대표 성능 (변동 없음):
- CAGR 12.387% / MDD 12.7446% / Sharpe 1.1019 / **Verdict REJECT**

---

## 4. P209-STEP9C 진입 가이드

### 4.1 가용 옵션

Track A (규칙기반 blacklist) 는 본 단계에서 검증 실패. 다음 옵션 중 택일:

**Option 1 — P209-STEP9C-TIGHTER-STOP (규칙기반 연장)**
- Track A 는 실패했지만 개별 종목 level tighter stop 은 아직 시도 안 함
- 현재 `stop_loss = -0.04` → `-0.03` / `-0.02` 등 더 타이트하게
- trailing stop 은 지시문에 의해 금지 → 고정 stop 만 실험
- 장점: 구현 단순, 규칙기반 유지
- 단점: MDD 방어가 단일 종목 level 에 국한, 전체 포트폴리오 drawdown 과 상관 없음

**Option 2 — P209-STEP9C-TRACKB-PREP (ML 방향 선회)**
- Track B = 확률 예측 기반 필터
- Step9B FIX 로 얻은 인사이트: "사후 toxic" 은 사전 배제 기준으로 유효하지 않음 → 예측 기반 접근 필요
- 준비 작업: feature engineering (volatility regime, momentum z-score, drawdown proximity 등), 라벨링 파이프라인 (다음 N 영업일 return), train/test split
- 장점: 본질적 문제 해결 시도
- 단점: 구현 복잡, 모델 해석성 낮음, overfit 리스크 높음

**Option 3 — P209 전체 종료 선언**
- P206/P207/P208 타이밍·배분·보유·P209 분석/규칙 필터 모두 실험 완료
- 현재까지의 결론: CAGR > 15 AND MDD < 10 동시 달성은 현재 universe/regime 조합에서 불가능
- P210 이후로 범위를 확장하거나, 승격 기준 자체를 재검토할지 사용자 결정

**권장 순서**: Option 1 (STEP9C-TIGHTER-STOP) 을 먼저 시도 → 실패 시 Option 2 로 이동 → 그래도 미달이면 Option 3.

### 4.2 Step9C 진입 시 설계 원칙

- `app/backtest/reporting/stop_loss_experiments/` 또는 `tighter_stop/` 같은 신규 패키지로 분리 (god file 재발 금지)
- 기존 Step9A drawdown 분석 모듈 재사용 (`drawdown/attribution.py` 등)
- SSOT 에 `stop_loss_experiments` 블록 신규 — 필수 검증 + 고정 실험군 집합
- `BacktestRunner.run` 에 `stop_loss_override` 파라미터 추가 (기존 `stop_loss` 와 별개 경로)
- `analysis_only` 모드와 호환 — Step9C 실험 sweep 은 analysis_only 에서도 실행, legacy sweep 만 차단
- 검증 보고는 반드시 A (기능) / B (구조) 2섹션

### 4.3 재사용 가능한 Step9B 산출물

- `drawdown/toxic_summary.py::compute_common_toxic_primary` — 후속 Track 분석에서 toxic 후보 재추출 용
- `toxic_filter_compare.py` 의 sweep + Q1~Q4 문구 패턴 — Step9C 실험 sweep 의 템플릿
- `toxic_filter_panel.py` 의 3 helper — UI 위치 고정 (새 페이지 금지 원칙)

---

## 5. 새 세션에서 이해해야 할 것

1. P204~P209-STEP9B 모두 완료
2. 최신 SSOT: CAGR 12.387 / MDD 12.7446 / REJECT
3. Track A 는 **검증 후 기각**. `102110, 102970` 등은 사후 drawdown 기여 상위이지만 사전 배제 기준으로는 유효하지 않음
4. B0_pos3_raew_no_filter (필터 없음) 이 실제 최고 성과 (MDD 11.03%, CAGR 15.95%) — 그러나 여전히 MDD < 10 미달
5. Step9C 는 tighter stop (Option 1) 우선 권장, 실패 시 Track B ML 로 전환
6. fail-loud 원칙 엄수, memory/feedback_code_quality_rules.md 규칙 1~13 준수
7. 검증 보고는 항상 A (기능) / B (구조) 2섹션
8. Step9B FIX 라운드의 11개 지적사항은 모두 해결 완료 (본 문서 §1.5 참조)

---

## 6. 첨부 권장 파일

- [reports/tuning/toxic_filter_compare.md](../../reports/tuning/toxic_filter_compare.md)
- [reports/tuning/toxic_filter_compare.json](../../reports/tuning/toxic_filter_compare.json)
- [reports/tuning/toxic_filter_compare.csv](../../reports/tuning/toxic_filter_compare.csv)
- [reports/tuning/dynamic_evidence_latest.md](../../reports/tuning/dynamic_evidence_latest.md) (Track A 섹션 포함)
- [reports/backtest/latest/backtest_result.json](../../reports/backtest/latest/backtest_result.json)
- [state/params/latest/strategy_params_latest.json](../../state/params/latest/strategy_params_latest.json) (tracka_toxic_filter / tracka_toxic_filter_experiments 블록)
- [app/backtest/reporting/toxic_filter_compare.py](../../app/backtest/reporting/toxic_filter_compare.py) (Step9C sweep 템플릿용)
