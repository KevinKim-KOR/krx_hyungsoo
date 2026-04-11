# P209-STEP9A Baseline Realignment 종료 + P209-STEP9B Hand-off 문서
> asof: 2026-04-11
> 상태: P209-STEP9A realignment **완료** (본 구현 + FIX 라운드 + fallback cleanup) / P209-STEP9B 진입 준비 완료

---

## 0. 이 문서의 목적

이 문서는 새로운 세션의 GPT/Claude 가
1) P209-STEP9A baseline realignment 의 최종 상태를 이어받고,
2) 곧바로 `P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1` 로 진입할 수 있게 하기 위한 hand-off 문서다.

직전 문서: [P208_close_and_P209_handoff.md](P208_close_and_P209_handoff.md)

---

## 1. P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1 종료 결론

### 1.1 스코프
전체 재실험이 아니라 **Step9A Drawdown Contribution 분석의 연구 baseline 만** 최신 UI 기준에 맞춰 재고정:

- A (operational baseline) = `g2_pos2_raew` **유지**
- B (research baseline) = `g5_pos4_eq` → **`g4_pos3_raew`**
- C (shadow reference) = `g3_pos3_eq` 신규 (정식 baseline 아님, 교집합 계산 제외)

### 1.2 무엇을 건드리지 않았는가
dynamic scanner / hybrid B+D / safe asset / allocation / Tune / holding_structure sweep / objective / 승격 기준 / ML / 실거래 로직 / 새 UI 페이지 — **전부 미변경**.

### 1.3 구현 파일

- [state/params/latest/strategy_params_latest.json](../../state/params/latest/strategy_params_latest.json): `drawdown_analysis_baselines` 블록 신규 (operational/research/shadow)
- [app/utils/param_loader.py](../../app/utils/param_loader.py): `_validate_drawdown_analysis_baselines` + `dynamic_etf_market` 모드에서 REQUIRED fail-loud 검증
- [app/backtest/reporting/drawdown/pipeline.py](../../app/backtest/reporting/drawdown/pipeline.py): `run_analysis_pipeline` 에 `a_spec/b_spec` **required kwarg** + `c_spec` optional, `_build_main_meta_injection` 에 shadow 필드
- [app/backtest/reporting/drawdown/toxic_summary.py](../../app/backtest/reporting/drawdown/toxic_summary.py): **신규 모듈**. `compute_common_toxic_primary(analyses, top_n=3)` — shadow 제외 교집합 단일 책임 함수
- [app/backtest/reporting/drawdown/__init__.py](../../app/backtest/reporting/drawdown/__init__.py): `compute_common_toxic_primary` export
- [app/backtest/reporting/drawdown/report_writer.py](../../app/backtest/reporting/drawdown/report_writer.py): baseline realignment 섹션 + shadow 표시 + 공유 함수 호출
- [app/backtest/reporting/evidence_writer.py](../../app/backtest/reporting/evidence_writer.py): Drawdown Contribution 섹션에 Shadow 서브섹션 + 공유 함수 호출
- [pc_cockpit/views/helpers/drawdown_contribution_panel.py](../../pc_cockpit/views/helpers/drawdown_contribution_panel.py): C (shadow) row + realignment caption
- [app/run_backtest.py](../../app/run_backtest.py):
  - SSOT baseline block → spec tuple 변환 + pipeline 전달
  - 과거 `except Exception` swallow **제거** (fail-loud)
  - `--analysis-only` CLI flag + sweep 가드 (holding_structure / allocation_experiments sweep 차단)
  - `_dd_result["main_meta_injection"]` / `_dd_result["analyses"]` 직접 subscript (`.get(k, default)` silent fallback 제거)

### 1.4 재생성된 산출물 (analysis-only 모드, 2026-04-11 18:25)

```
reports/backtest/latest/backtest_result.json      18:25 ← main summary + meta injection
reports/tuning/drawdown_contribution_report.md    18:25
reports/tuning/drawdown_contribution_report.json  18:25
reports/tuning/drawdown_contribution_report.csv   18:25
reports/tuning/dynamic_evidence_latest.md         18:25
reports/tuning/promotion_verdict.json             18:25
reports/tuning/holding_structure_compare.md       17:38 ← 미갱신 (sweep 차단)
reports/tuning/allocation_constraint_compare.md   17:38 ← 미갱신 (sweep 차단)
```

sweep 차단 로그:
```
[P209-STEP9A] analysis_only=True — holding_structure sweep 스킵
[P209-STEP9A] analysis_only=True — allocation_experiments sweep 스킵
```

### 1.5 최신 대표 성능 (변동 없음)

| 지표 | 값 |
|---|---:|
| CAGR | 12.387% |
| MDD | 12.7446% |
| Sharpe | 1.1019 |
| Total Trades | 53 |
| Verdict | **REJECT** (CAGR>15, MDD<10 둘 다 미달) |

### 1.6 baseline 별 drawdown 비교 (Step9B 입력 근거)

| Baseline | Role | Max Pos | Alloc Mode | MDD % | Selection Verdict | avg_selection_gap %p |
|---|---|---:|---|---:|---|---:|
| `g2_pos2_raew` | operational | 2 | raew | **12.7446** | HEALTHY | +0.6575 |
| `g4_pos3_raew` | research | 3 | raew | **11.0281** | HEALTHY | −0.7622 |
| `g3_pos3_eq` | shadow (참고) | 3 | eq | 11.0964 | HEALTHY | −0.993 |

**주요 발견**: pos3 + raew 연구 baseline 의 MDD 가 pos2 raew 운영 baseline 대비 **1.7%p 낮음**. pos3 계열은 selection gap 도 음수 (선택이 비선택보다 더 좋음).

### 1.7 공통 Toxic Tickers (Step9B Track A 1순위 후보)

양쪽 산출물에서 **단일 소스** (`compute_common_toxic_primary`) 로 계산, 결과 완전 일치:

- **정식 baseline 공통 Toxic (top 3 교집합, shadow 제외)**: **`['102110', '102970']`**
- 모든 실험군 합집합 (shadow 포함): `['102110', '102970', '395270', '396500']`

A (g2_pos2_raew) 의 MDD 구간 (2024-06-20 → 2024-08-05) 에서 `102110` 이 −6.88%p (share_of_mdd 54%), `102970` 이 −4.93%p (38.7%) 기여. B (g4_pos3_raew) 에서도 동일 순서로 `102110` (−4.42%p, 40.1%), `102970` (−3.34%p, 30.2%) 이 상위.

---

## 2. FIX 라운드 기록 (참고용)

Step9A realignment 는 본 구현 후 사용자 검증에서 4건의 블로커가 발견되어 FIX 라운드를 거쳤다.

### 2.1 지적 4건

1. **(A-1 차단)** 분석 전용 재생성이라고 보고했지만 `holding_structure_compare.md` / `allocation_constraint_compare.md` 가 부수적으로 재생성되고 있었음 → `--analysis-only` 모드 미구현
2. **(A-2 차단)** 공통 toxic 계산 기준이 산출물마다 달랐음 — `drawdown_contribution_report.md` 는 `[102110, 102970]`, `dynamic_evidence_latest.md` 는 `102110, 102970, 261240, 396500`
3. **(B-1 차단)** baseline source 가 완전한 명시 파라미터 방식 아님 — param_loader None 허용, pipeline 하드코딩 기본값, run_backtest 에서 optional branch
4. **(B-2 차단)** drawdown 분석 전체를 `except Exception` 으로 감싸 warning 만 남기고 진행 — 필수 설정 오류 silent

추가로 FIX 완료 검증 중 사용자 재지적:
5. `run_backtest.py` 에서 `_dd_result.get("main_meta_injection", {})` / `_dd_result.get("analyses", [])` 2곳의 silent fallback 잔존 — pipeline 이 REQUIRED key 로 항상 반환하므로 직접 subscript 로 교체

### 2.2 해결

| # | 해결 방식 |
|---|---|
| 1 | `--analysis-only` CLI flag 신규. holding/allocation sweep 조건에 `and not analysis_only` 가드 추가. skip 로그 명시 출력 |
| 2 | `drawdown/toxic_summary.py` 신규 모듈. `report_writer` 와 `evidence_writer` 양쪽이 동일 함수 호출 |
| 3 | 3 레이어 모두 하드코딩 제거 — param_loader REQUIRED 검증, pipeline required kwarg, run_backtest 직접 subscript |
| 4 | try/except 블록 제거, 에러 propagate |
| 5 | `_dd_result["main_meta_injection"]` / `_dd_result["analyses"]` 직접 subscript |

### 2.3 검증 (2026-04-11 18:25 analysis-only 재실행)

- 정적 게이트: black / flake8 / py_compile 모두 clean
- sweep 타임스탬프 불변 확인 → 17:38 유지
- 공통 toxic 일치 확인 → 양쪽 산출물 `[102110, 102970]`
- fail-loud 검증 → SSOT 에 `drawdown_analysis_baselines` 임시 제거 시 즉시 `KeyError` (테스트 후 복구)
- main CAGR/MDD/Sharpe 변동 없음

---

## 3. 현재 SSOT 상태 (변동 없음)

```json
{
  "params": {
    "position_limits": { "max_positions": 2 },
    "allocation": {
      "mode": "risk_aware_equal_weight_v1",
      "weight_floor": 0.35,
      "weight_cap": 0.65
    },
    "holding_structure_experiments": [ g1_pos2_eq ~ g8_pos5_raew ],
    "drawdown_analysis_baselines": {
      "operational": "g2_pos2_raew",
      "research": "g4_pos3_raew",
      "shadow": "g3_pos3_eq"
    }
  }
}
```

---

## 4. P209-STEP9B 진입 근거

### 4.1 지금까지 확인된 것
- 타이밍 방어 (P206) 만으로 MDD<10 불가
- 보유 구조 확장 (P208) 만으로 MDD<10 불가
- 리스크 인식형 allocation (P207) 만으로 MDD<10 불가
- 심지어 최적 baseline (g4_pos3_raew) 도 MDD 11.03% → REJECT
- 반복적으로 2024-06-20 → 2024-08-05 MDD window 에서 **특정 종목이 손실을 몰아감**
- 정식 baseline (A, B) 양쪽에서 동일하게 반복 상위 toxic: `102110`, `102970`

### 4.2 가설
- 타이밍/allocation/보유수를 바꿔도 toxic asset 이 들어오면 손실을 막을 수 없다
- 해결책은 **toxic 종목 자체를 선택에서 거르는 규칙기반 필터**
- Track A: 규칙기반 (본 단계)
- Track B: ML classifier (후속, 별도 챕터)

---

## 5. P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1 진입 가이드

### 5.1 목표
Step9A 분석 결과로 식별된 toxic ticker / 패턴을 **실제 매매 로직에 규칙기반 필터로 적용** 하여 MDD 감소 효과를 정량 검증한다.

### 5.2 설계 원칙

1. **운영/실험 경계 분리 (rule 10)**:
   - 필터 로직은 `BacktestRunner.run()` 에 inline 으로 넣지 말고 별도 훅 (`filter_hooks/toxic_drop.py` 등) 으로 분리
   - 실험 sweep 은 신규 패키지 (예: `app/backtest/reporting/toxic_filter/`) 로, 기존 `reporting/drawdown/` / `holding_structure/` / `allocation_constraints/` 패턴 재사용

2. **분석 전용 모듈 재사용**:
   - `drawdown/attribution.py` (compute_ticker_contributions) 와 `drawdown/selection_quality.py` 는 read-only 로 재사용
   - `drawdown/toxic_summary.compute_common_toxic_primary` 로 Step9A 결과에서 toxic ticker 후보 자동 추출 가능

3. **fail-loud 원칙**:
   - 필터 설정 (blacklist ticker, stop 조건, cap 수치) 는 SSOT 에 명시 필수
   - None fallback 금지, 누락 시 param_loader 에서 즉시 KeyError

4. **승격 기준 유지**: `CAGR > 15 AND MDD < 10`. 변경 금지.

### 5.3 제안 Track A 규칙 후보 (drawdown_contribution_report.md 초안 기반)

- **R1 (toxic asset drop)**: 리밸런스 선택 시 blacklist ticker 배제
  - 초기 blacklist: `102110`, `102970` (정식 baseline 공통 top 3 교집합)
- **R2 (momentum crash filter)**: 리밸런스 직후 N영업일 내 −X% 이상 하락 종목 강제 청산
- **R3 (bucket exposure cap)**: 특정 bucket/그룹의 총 노출을 상한으로 제한
- **R4 (individual stop)**: 종목별 개별 stop — 현재 stop_loss 대비 더 타이트하게

### 5.4 첫 단계 권장 스코프
Step9B 전체를 한 번에 하지 말고 **R1 (가장 단순한 toxic drop) 만 먼저 설계/구현/검증**. R2~R4 는 별도 FIX 라운드 또는 Step9B-v2 로 미룬다.

설계 문서 먼저: `docs/analysis/P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1-DESIGN.md` 작성 후 사용자 승인 → 구현.

### 5.5 절대 금지 사항

- Tune 재실행
- holding_structure_experiments 재설계
- allocation 로직 변경
- ML classifier 진입 (Track B 용)
- 새 UI 페이지 추가
- objective / 승격 기준 변경
- main backtest 경로에 inline 필터 코드 삽입

---

## 6. 새 세션에서 즉시 이해해야 할 것

1. P204~P208 + P209-STEP9A 본 구현 + realignment 모두 완료
2. 현재 SSOT 는 `g2_pos2_raew` 운영 유지, REJECT 상태
3. P209-STEP9A 분석 baseline 은 최신 UI 기준으로 재고정됨: A=g2, B=g4, C shadow=g3
4. Step9B 진입 가능 — 첫 작업은 설계 문서 작성 (`P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1-DESIGN.md`)
5. 필터 로직은 반드시 BacktestRunner 에 inline 으로 넣지 말고 훅으로 분리
6. fail-loud 원칙 엄수, memory/feedback_code_quality_rules.md 규칙 1~13 준수
7. 검증 보고는 항상 A(기능) / B(구조) 2섹션

---

## 7. 첨부 권장 파일

- [reports/tuning/drawdown_contribution_report.md](../../reports/tuning/drawdown_contribution_report.md) (최신 baseline)
- [reports/tuning/dynamic_evidence_latest.md](../../reports/tuning/dynamic_evidence_latest.md) (P209 섹션 포함)
- [reports/backtest/latest/backtest_result.json](../../reports/backtest/latest/backtest_result.json) (drawdown meta 주입 확인)
- [state/params/latest/strategy_params_latest.json](../../state/params/latest/strategy_params_latest.json) (drawdown_analysis_baselines 블록 확인)
- [app/backtest/reporting/drawdown/toxic_summary.py](../../app/backtest/reporting/drawdown/toxic_summary.py) (Step9B 에서 재사용)
