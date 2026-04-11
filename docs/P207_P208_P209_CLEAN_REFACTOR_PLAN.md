# P207 / P208 / P209 Clean Refactor Plan
> asof: 2026-04-11
> 상태: **APPROVED** — 사용자 승인 완료, STEP R1 진입 대기
> 다음 단계: 매 STEP 승인 방식으로 R1 → R2 → ... → R7 순차 진행 → 완료 후 `P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1` 진입
> 총 STEP / commit 수: 7 (R1~R7)
> 변경 이력: v1 (P208/P209 한정) → v2 P207 통합 layer 본 범위 편입 → **v3 사용자 확정 (A / 가 / R1~R4·R6 byte-level + R5 의미적 / c / I / 1)**

---

## 0. 이 문서의 목적과 범위

P207-STEP7C, P208-STEP8A, P209-STEP9A 가 기능은 통과했지만 `memory/feedback_code_quality_rules.md` 의 코드/구조 품질 규칙(6/7/8/9/10/11) 을 다수 위반한 채 commit 되었다. 이 문서는 동작을 바꾸지 않으면서 (refactor only) 구조 품질만 회복하는 단계별 plan 이다.

**본 plan의 범위는 P207 통합 layer + P208 + P209 cleanup 모두이다.**
P207 은 더 이상 "선택 확장 범위" 가 아니라 **기본 포함 범위** 다. 이유는:

1. P207-STEP7C 가 `run_backtest.py` 에 inline sweep 블록, evidence f-string blob, `format_result` 메타 fallback 패턴을 **처음 도입**한 챕터이며, P208/P209 는 이 안티패턴을 이어받아 키운 것에 불과하다. root cause 를 남긴 채 P208/P209 만 정리하면 같은 패턴이 다음 챕터에 재발생한다.
2. STEP R1 (evidence_writer 추출) 과 STEP R5 (fallback 제거) 가 어차피 `run_backtest.py` 와 evidence md 생성 경로를 손대므로, P207 의 같은 영역을 정리하지 않으면 오히려 어색한 하이브리드 상태 (P208/P209 만 분리, P207 은 inline) 가 된다.
3. `allocation_constraint_compare.md/.csv` 생성 로직도 inline 으로 남아 있어 `holding_structure/` / `drawdown/` 패키지 구조와 대칭성이 깨져 있다.

이 plan 은 사용자가 먼저 검토/승인한 뒤 **각 STEP 별로 순차 진행하며 사용자 검증을 받는다**. plan 자체가 승인 대상이고, 각 STEP 도 별도 승인 대상이다.

위치: `docs/` root. 핸드오프 문서가 아니라 작업 plan 이므로 `docs/handoff/` 가 아니다.

---

## 1. 배경: 왜 이 refactor 가 필요한가

`memory/feedback_code_quality_rules.md` 의 다음 규칙이 위반되어 있다.

- **6번** (암묵 fallback 금지)
- **7번** (필수 설정값 누락 시 명확한 에러)
- **8번** (함수/클래스 단위 모듈화)
- **9번** (1 파일 1 기능, 단일 책임 원칙)
- **10번** (실험/분석 코드가 운영 경로를 오염시키지 않을 것)
- **11번** (하드코딩 stale 상수/과거 결과 재사용 금지)

P207/P208/P209 는 기능적으로는 작동하지만 위 규칙들을 다수 위반한 채 commit 되었고, 사용자가 직접 지적해야 했다.

이 refactor 는 다음을 보장한다.
- **동작 보존**: CAGR / MDD / Sharpe / evidence 핵심 필드 / 모든 산출물 동일
- **구조 정상화**: god module 분할, 운영/실험 경계 분리, 암묵 fallback 제거
- **다음 챕터 안전성**: P209-STEP9B (Track A 필터 설계) 진입 시 god file 을 더 키우지 않음
- **대칭성**: 세 챕터(P207/P208/P209) 모두 `reporting/` 아래 단일 책임 패키지로 통일

---

## 2. 자체 감사 요약

### 2.1 위반 #1 — `app/backtest/reporting/drawdown_contribution.py` (P209)

| 항목 | 현재 상태 | 문제 |
|---|---|---|
| 파일 크기 | 1000+ 줄 | god module |
| 함수 수 | 17개 | SRP 위반 |
| 책임 영역 | 6개 (window, position 복원, attribution, selection quality, bucket aggregation, pipeline orchestration, markdown rendering) | 단일 파일에 혼재 |

**함수 책임 매트릭스**:
| 함수 | 책임 영역 |
|---|---|
| `find_mdd_window` | MDD 식별 |
| `_build_close_series`, `reconstruct_daily_positions` | Position 복원 |
| `compute_ticker_contributions`, `_price_at` | Return attribution |
| `compute_selection_quality`, `_summarize_selection_quality`, `_selection_quality_verdict` | Selection quality |
| `compute_bucket_risk` | Bucket 집계 |
| `analyze_variant`, `run_analysis_pipeline`, `_build_allocation_block`, `_matches_main`, `_build_main_meta_injection` | Pipeline orchestration |
| `write_drawdown_contribution_report`, `_render_markdown`, `_render_one_analysis`, `_render_filter_proposal` | Markdown rendering |

### 2.2 위반 #2 — `app/run_backtest.py` god file 누적 (P207+P208+P209 전부)

P207-STEP7C 에서 처음 도입된 inline 통합 패턴을 P208/P209 가 이어받아 확장했다.

| 챕터 | 추가된 inline 양 | 위치 |
|---|---|---|
| **P207-STEP7C** | `run_cli_backtest` 내 allocation sweep ~115줄, `format_result` allocation 메타 ~30 필드, evidence md 내 Allocation / Last Rebalance Trace 섹션 | 모두 `app/run_backtest.py` |
| P208-STEP8A | `run_cli_backtest` 내 holding_structure sweep 훅, `format_result` holding structure 메타, evidence "Holding Structure" 섹션 | 같은 함수 |
| P209-STEP9A | `run_cli_backtest` 내 drawdown 분석 훅, evidence "Drawdown Contribution" 섹션 (~100줄 inline f-string) | 같은 함수 |

결과: `run_cli_backtest` 함수 하나가 약 800줄을 넘는 god function 이 되었고, `format_result` 의 meta 블록은 `.get(k, default)` chained fallback 패턴을 다수 포함한다. 세 챕터 모두 같은 안티패턴이며, P207 은 그 root cause 다.

특히 `allocation_constraint_compare.md/.csv` 생성 로직이 **`run_backtest.py` 내부에 inline 으로** 존재한다. 별도 모듈 파일이 없다 (`holding_structure_compare.py` / `drawdown_contribution.py` 와 대칭되지 않음).

### 2.3 위반 #3 — UI god file 누적 (`workflow.py` + `parameter_editor.py`)

| 파일 | 챕터 | 추가된 inline 양 |
|---|---|---|
| `pc_cockpit/views/workflow.py` | P207-STEP7C-FIX | ~20줄 (Allocation 비교표 expander + trace expander + caption) |
| `pc_cockpit/views/workflow.py` | P208-STEP8A | ~50줄 (holding_structure 비교 expander + caption) |
| `pc_cockpit/views/workflow.py` | P209-STEP9A | ~215줄 (drawdown contribution summary, A vs B side-by-side, top toxic, worst events, bucket risk) |
| `pc_cockpit/views/parameter_editor.py` | P207-STEP7C-FIX | Allocation 섹션 (mode, floor/cap, experiment name) |
| `pc_cockpit/views/parameter_editor.py` | P208-STEP8A | Holding Structure 섹션 (current experiment, max_positions, allocation_mode) |

UI 렌더링 로직이 view 함수 본체에 inline 으로 누적되었다. **`workflow.py` 뿐 아니라 `parameter_editor.py` 도 cleanup 대상이다.**

### 2.4 위반 #4 — 암묵 fallback / silent skip 패턴 (P207/P208/P209 공통)

다음 패턴들이 광범위하게 존재한다. 단순한 `.get(..., 0)` 뿐 아니라 여러 형태로 나타난다.

**검출 대상 패턴 전체 목록**:
- `.get(key, default)` — default 가 0, 0.0, "", [], {}, None 중 하나이면 의심
- `or {}`, `or []`, `or 0`, `or 0.0`, `or ""` — 좌변 falsy 시 fallback
- silent `continue` in loop — 실패 케이스를 로그 없이 넘김
- silent `return None` — 호출자가 None 을 또 silently 처리
- silent `return {}` / `return []` — 빈 컨테이너로 fallback
- `try ... except (KeyError, TypeError): return None` — 오류 origin 소실
- 조건문 내부의 무언의 pass

**구체 사례**:

```python
# drawdown_contribution.py analyze_variant
nav_history = raw_result.get("nav_history", []) or []
trades = raw_result.get("trades", []) or []
```
→ nav_history 누락 시 분석 자체가 무의미한데 빈 리스트로 fallback. 버그가 묻힘. 이중 fallback (`.get(..., [])` + `or []`).

```python
# drawdown_contribution.py compute_ticker_contributions
prev_nav = nav_map.get(prev["date"], 0.0)
if prev_nav <= 0:
    continue  # silent skip
```
→ nav 누락이 데이터 손상인지 정상 상황인지 구분 안 됨.

```python
# drawdown_contribution.py _price_at
try:
    idx = s.index.asof(ts)
except (KeyError, TypeError):
    return None
```
→ 모든 호출자가 None 을 silently skip. price_data 가 잘못 로드된 건지 ticker 가 거래되지 않은 건지 구분 안 됨.

```python
# drawdown_contribution.py _summarize_selection_quality
if not events:
    return {
        "rebalance_count": 0,
        "positive_forward_ratio": 0.0,
        "avg_forward_return_pct": 0.0,
        ...
    }
```
→ rule 6 이 정확히 금지하는 패턴. events 가 비어있으면 분석이 의미 없는데 0.0 으로 가득 채워서 통과시킴.

```python
# run_backtest.py evidence Holding Structure 섹션 (P208)
f"| Avg Held Positions | {_bt_m.get('avg_held_positions', 0.0)} |"
f"| Blocked By Max Positions | {(_bt_m.get('blocked_reason_totals') or {}).get('BLOCKED_MAX_POSITIONS', 0)} |"
```
→ P208 이 정상 실행되었다면 이 필드들은 반드시 존재해야 함. `0.0`/`0` fallback 은 "P208 비활성화" 와 "0회 발생" 을 동일하게 표시. `or {}` chained fallback.

```python
# run_backtest.py format_result (P207)
"allocation_mode": result.get("allocation_mode", "bucket_portfolio"),
"allocation_fallback_used": result.get("allocation_fallback_used", False),
"allocation_weight_floor": (result.get("allocation_params") or {}).get("weight_floor"),
"allocation_weight_cap": (result.get("allocation_params") or {}).get("weight_cap"),
```
→ dynamic 모드에서 P207 이 정상 실행되었다면 `allocation_mode` 가 반드시 존재해야 함. `bucket_portfolio` 로 fallback 되는 건 "이 백테스트가 dynamic 이 아니었다" 는 의미지만 그걸 명시적으로 구분해야지 silent fallback 하면 안 됨.

```python
# run_backtest.py evidence Allocation 섹션 (P207)
f"| Mode | {_bt_m.get('allocation_mode', 'dynamic_equal_weight')} |"
f"| Experiment Name | {_bt_m.get('allocation_experiment_name', 'N/A')} |"
f"| Weight Floor | {_ev_ap.get('weight_floor', 'N/A')} |"
```
→ `'N/A'`, `'dynamic_equal_weight'` 같은 문자열 fallback. P207 활성 상태에서 이 필드들은 반드시 존재해야 한다.

### 2.5 P207/P208/P209 공통 안티패턴 — **범위 확정**

위의 2.1~2.4 를 종합하면, 세 챕터 모두 다음 패턴을 공유한다.

- `run_backtest.py` 에 챕터별 sweep / 메타 주입 / evidence 섹션을 inline 으로 추가
- `format_result` 의 meta dict 를 `.get(k, default)` chain 으로 채움
- UI 에 챕터별 expander 를 `workflow.py` / `parameter_editor.py` 본체에 inline 으로 추가
- 각 챕터의 분석/집계 로직이 단일 파일에 god module 로 몰림 (P207 은 `run_backtest.py` inline, P208/P209 는 자체 god module)

**결론**: P207 통합 layer 는 이번 cleanup plan 의 **본 범위에 포함** 된다. 옵션이 아니다.

근거:
1. P207 이 root cause 이며 cleanup 하지 않으면 같은 패턴이 다음 챕터에 재발생한다
2. `run_backtest.py` 와 evidence md 생성 경로를 어차피 STEP R1 / R5 에서 손대므로 P207 을 남겨두면 하이브리드 상태가 됨
3. `holding_structure/` / `drawdown/` 패키지 구조와 대칭되게 `allocation_constraints/` 패키지를 만들어야 구조 일관성이 확보됨

---

## 3. 목표 구조 (After Refactor)

### 3.1 `app/backtest/reporting/` 의 새 레이아웃

```
app/backtest/reporting/
├── __init__.py
├── evidence_writer.py                ← 신규: dynamic_evidence_latest.md 생성 전담
│                                        (Performance / Hybrid Regime / Allocation /
│                                         Holding Structure / Drawdown Contribution /
│                                         Promotion Verdict 섹션 렌더러 통합)
├── allocation_constraints/           ← 신규 패키지 (P207 cleanup)
│   ├── __init__.py
│   ├── sweep.py                      # allocation_experiments sweep 로직
│   │                                 # (현재 run_backtest.py inline 에 존재)
│   ├── report_writer.py              # allocation_constraint_compare.md/.csv 생성
│   └── diagnostic.py                 # 비교 요약 문구 / verdict 판정
├── holding_structure/                ← 신규 패키지 (P208 cleanup)
│   ├── __init__.py
│   ├── sweep.py                      # run_holding_structure_sweep,
│   │                                 # _build_allocation_block
│   ├── verdict.py                    # _verdict 함수
│   ├── report_writer.py              # _write_outputs (md/csv/json)
│   └── diagnostic.py                 # _diagnostic_summary (Q1~Q4)
└── drawdown/                         ← 신규 패키지 (P209 cleanup)
    ├── __init__.py
    ├── window.py                     # find_mdd_window
    ├── positions.py                  # _build_close_series,
    │                                 # reconstruct_daily_positions
    ├── attribution.py                # compute_ticker_contributions,
    │                                 # _price_at
    ├── selection_quality.py          # compute_selection_quality, summary, verdict
    ├── bucket_risk.py                # compute_bucket_risk
    ├── pipeline.py                   # analyze_variant, run_analysis_pipeline,
    │                                 # meta injection
    └── report_writer.py              # write_drawdown_contribution_report,
                                      # _render_*
```

기존 단일 파일 (`holding_structure_compare.py`, `drawdown_contribution.py`) 은 thin re-export shim 으로 유지하거나 완전히 제거한다 (사용처 import 경로를 함께 갱신).
P207 은 기존에 모듈 파일이 없었으므로 `allocation_constraints/` 를 신규로 만든다.

### 3.2 `pc_cockpit/views/` 의 새 레이아웃

```
pc_cockpit/views/
├── workflow.py                       # 슬림화 — 패널 호출만
├── parameter_editor.py               # 슬림화 — 패널 호출만
└── helpers/                          ← 신규
    ├── __init__.py
    ├── allocation_panel.py           # render_allocation_panel_for_parameters(p),
    │                                 # render_allocation_compare_expander(base_dir),
    │                                 # render_allocation_trace_expander(bt_meta)
    ├── holding_structure_panel.py    # render_holding_structure_panel_for_parameters(p),
    │                                 # render_holding_structure_compare_expander(base_dir),
    │                                 # render_holding_structure_caption(bt_meta)
    └── drawdown_contribution_panel.py # render_drawdown_contribution_panel(bt_meta, base_dir)
```

**`parameter_editor.py` 와 `workflow.py` 둘 다 cleanup 대상**이다.
- `parameter_editor.py`: Allocation 섹션 (P207) + Holding Structure 섹션 (P208) 을 panel helper 호출로 치환
- `workflow.py`: Allocation compare expander (P207) + holding_structure compare expander (P208) + drawdown contribution summary (P209) 를 panel helper 호출로 치환

### 3.3 `app/run_backtest.py` 의 슬림화

`run_cli_backtest` 와 `format_result` 안의 inline 블록들을 함수/모듈로 추출:

- **evidence md 생성** → `evidence_writer.write_dynamic_evidence(formatted, hybrid_state, allocation_trace, hs_meta, dd_analyses, promotion_verdict, output_path)` 호출 1줄로 축소
- **P207 allocation sweep** → `allocation_constraints.sweep.run_allocation_constraint_sweep(experiments, base_params, ...)` 호출 1줄로 축소
- **P208 holding_structure sweep 훅** → 이미 모듈에 있으나 호출 위치를 명시적 함수로 묶음
- **P209 drawdown 분석 훅** → 이미 모듈에 있으나 동일
- **P207 format_result meta 필드** → `allocation_constraints` 모듈의 meta builder 함수로 추출
- **P208 format_result meta 필드** → `holding_structure` 모듈의 meta builder 함수로 추출
- **P209 format_result meta 주입** → 이미 `pipeline._build_main_meta_injection` 에 있음. 유지

### 3.4 암묵 fallback 제거

모든 reporting 모듈과 `run_backtest.py` 의 evidence/format 경로에서 다음을 강제한다.
- 필수 입력값 누락 시 명시적 `KeyError` / `ValueError` raise
- "데이터 없음" 케이스는 explicit `None` 반환 + 호출자가 None 을 명시적으로 분기 처리
- 산출물 메타 필드는 fallback 없이 반드시 존재한다고 가정 (builder 에서 누락 검출 시 KeyError)

**fallback 검출 규칙 (STEP R5 와 최종 검증 게이트 공통)**:

아래 패턴을 전수 검색하고, 각각 "허용 케이스 whitelist" 를 만들어 그 외는 raise 로 변경한다.

| 패턴 | 검출 명령 (예시) |
|---|---|
| `.get(key, default)` with non-None default | `grep -rn "\.get(" app/backtest/reporting/ \| grep -v ", None)"` |
| `or {}`, `or []` | `grep -rn "or \(\\[\\]\|\{\}\)" app/backtest/reporting/` |
| `or 0`, `or 0.0`, `or ""` | `grep -rnE "or (0\\.0\|0\|\\"\\")" app/backtest/reporting/` |
| silent `continue` in loop | 수동 검토 + 로그 누락 확인 |
| silent `return None` | 수동 검토 + 호출자가 None 을 분기하는지 확인 |
| silent `return {}` / `return []` | `grep -rn "return \\[\\]\|return \{\\}" app/backtest/reporting/` |
| 광범위 except | `grep -rn "except (KeyError, TypeError)" app/backtest/reporting/` |

허용 케이스의 예: accumulator 초기화 (`total = 0`), list append 시작 (`items: List = []`), 명시적으로 optional 로 문서화된 함수의 기본값.

---

## 4. STEP 별 진행 계획

각 STEP 은 독립 commit. 각 STEP 종료 시 사용자 승인 후 다음 STEP 진입.
**모든 STEP 의 핵심 검증 기준은 "동작 보존"** — Full Backtest 재실행 후 다음이 동일해야 한다.
- main `CAGR / MDD / Sharpe / total_trades`
- `allocation_constraint_compare.md/.csv` 의 G1/G2A~D/G3 수치
- `holding_structure_compare.md/.csv/.json` 의 G1~G8 수치
- `drawdown_contribution_report.md/.json/.csv` 의 MDD window / top toxic / selection gap
- `dynamic_evidence_latest.md` 의 모든 섹션 핵심 필드
- `backtest_result.json` meta 핵심 필드 (allocation + holding_structure + drawdown 모두)

각 STEP 종료 보고는 반드시 `## A. 기능/산출물 검증` + `## B. 구현 규칙/구조 품질 검증` 2개 섹션.

STEP 순서 rationale:
- R1 에서 evidence_writer 를 먼저 추출해 `run_cli_backtest` 를 슬림화
- R2/R3/R4 는 각 챕터의 god module / inline 블록을 독립적으로 분할 (순서 무관하지만 drawdown → holding → allocation 순으로 규모 큰 것부터)
- R5 에서 fallback 을 전수 감사/제거 (모듈이 분할된 뒤가 더 쉬움)
- R6 에서 UI view helper 추출
- R7 에서 최종 동등성 검증 + handoff 갱신

---

### STEP R1 — `evidence_writer.py` 추출 (P207+P208+P209 evidence 통합)

**목표**: `run_cli_backtest` 의 inline evidence md 생성 블록 전체를 별도 모듈로 추출.

**Why**:
- rule 9 (1 파일 1 기능): evidence 렌더링은 백테스트 오케스트레이션과 분리되어야 함
- rule 10 (실험/분석 vs 운영 경계): evidence 는 운영 경로의 부산물이지 핵심이 아님
- god function 축소 (`run_cli_backtest` 가 800줄+ → 대폭 감소)
- P207/P208/P209 의 evidence 섹션이 같은 곳에서 일관되게 렌더링됨

**범위**:
- 신규 파일: `app/backtest/reporting/evidence_writer.py`
  - 공개 진입점: `def write_dynamic_evidence(formatted, regime_verdict, allocation_trace, hs_meta, dd_analyses, promotion_verdict, output_path) -> None`
  - 내부 섹션 helper (파일 내 `_render_*` 형태 또는 서브 모듈로 분리 검토):
    - `_render_performance_section`
    - `_render_hybrid_regime_section`
    - `_render_allocation_section` (P207)
    - `_render_last_rebalance_trace_section` (P207)
    - `_render_holding_structure_section` (P208)
    - `_render_drawdown_contribution_section` (P209)
    - `_render_promotion_verdict_section`
    - `_render_conclusion_section`
- 수정: `app/run_backtest.py`
  - ~400줄 inline f-string blob 제거 (P207/P208/P209 evidence 모두)
  - `write_dynamic_evidence(...)` 1줄 호출로 대체

**Behavior 보존**:
- 생성된 `dynamic_evidence_latest.md` 파일이 byte-level identical 또는 의미적으로 identical (공백/라인 차이만 허용)

**검증 게이트**:
- black + flake8 + py_compile
- Full Backtest 재실행
- 새 evidence md 와 직전 evidence md diff (의도하지 않은 변경 0줄 또는 공백뿐)
- 새 evidence md 의 모든 섹션 존재 확인:
  - Performance / Hybrid Regime / Allocation / **Last Rebalance Trace (P207)** / Holding Structure (P208) / Drawdown Contribution (P209) / Promotion Verdict / One-line Conclusion

**위험도**: 낮음~중간 (순수 추출, 다만 P207/P208/P209 세 섹션을 한 번에 건드림)

**예상 commit 메시지**:
`refactor(P209-CLEAN-R1): extract evidence_writer from run_backtest.py (P207+P208+P209)`

---

### STEP R2 — `drawdown_contribution.py` 분할 (P209 cleanup)

**목표**: 1000줄 god module 을 7개 단일 책임 모듈로 분할.

**Why**:
- rule 8/9: 17 함수, 6 책임 → SRP 명백 위반
- 다음 챕터 (Step9B) 에서 toxic asset filter 설계 시 attribution 로직만 import 해서 재사용해야 하는데, 현재는 god module 전체가 묶여있음

**범위**:
- 신규 디렉토리: `app/backtest/reporting/drawdown/`
- 신규 파일 7개:
  1. `window.py` — `find_mdd_window`
  2. `positions.py` — `_build_close_series`, `reconstruct_daily_positions`
  3. `attribution.py` — `compute_ticker_contributions`, `_price_at`
  4. `selection_quality.py` — `compute_selection_quality`, `_summarize_selection_quality`, `_selection_quality_verdict`
  5. `bucket_risk.py` — `compute_bucket_risk`
  6. `pipeline.py` — `analyze_variant`, `run_analysis_pipeline`, `_build_allocation_block`, `_matches_main`, `_build_main_meta_injection`
  7. `report_writer.py` — `write_drawdown_contribution_report`, `_render_markdown`, `_render_one_analysis`, `_render_filter_proposal`
- `__init__.py` 에서 외부 진입점만 re-export (`run_analysis_pipeline`, `analyze_variant`)
- 기존 `app/backtest/reporting/drawdown_contribution.py` 는 thin shim 또는 삭제
- 사용처 `app/run_backtest.py` 의 import 경로 갱신
- evidence_writer (R1 결과물) 가 import 하는 경로도 갱신

**Behavior 보존**:
- 모든 함수 시그니처 보존
- 반환 dict 의 키/값 동일
- `drawdown_contribution_report.md/.json/.csv` byte-level identical

**검증 게이트**:
- black + flake8 + py_compile
- Full Backtest 재실행
- A/B 분석 결과 동일성 (top toxic, selection gap, bucket risk, verdict)
- main meta injection 필드 동일성

**위험도**: 중간

**예상 commit 메시지**:
`refactor(P209-CLEAN-R2): split drawdown_contribution into drawdown/ package`

---

### STEP R3 — `holding_structure_compare.py` 분할 (P208 cleanup)

**목표**: holding_structure 모듈을 패키지로 분할.

**Why**:
- rule 9: sweep + reporting + diagnostic + verdict 가 한 파일에 혼재
- R2 의 drawdown 패키지 패턴과 대칭

**범위**:
- 신규 디렉토리: `app/backtest/reporting/holding_structure/`
- 신규 파일 4개:
  1. `sweep.py` — `run_holding_structure_sweep`, `_build_allocation_block`
  2. `verdict.py` — `_verdict`
  3. `report_writer.py` — `_write_outputs`
  4. `diagnostic.py` — `_diagnostic_summary`
- `__init__.py` 에서 `run_holding_structure_sweep` re-export
- 기존 `holding_structure_compare.py` 는 thin shim 또는 삭제
- `app/run_backtest.py` 및 evidence_writer import 경로 갱신

**Behavior 보존**:
- `holding_structure_compare.md/.csv/.json` byte-level identical

**검증 게이트**:
- black + flake8 + py_compile
- Full Backtest 재실행
- G1~G8 비교표 수치 / 진단 요약 Q1~Q4 동일성

**위험도**: 낮음

**예상 commit 메시지**:
`refactor(P209-CLEAN-R3): split holding_structure_compare into holding_structure/ package`

---

### STEP R4 — `allocation_constraints/` 패키지 추출 (**P207 cleanup**)

**목표**: `run_backtest.py` 에 inline 으로 존재하는 P207 allocation sweep / compare 생성 로직을 `allocation_constraints/` 패키지로 추출.

**Why**:
- **P207 cleanup 의 핵심 STEP**. 이 STEP 이 없으면 plan 은 P207 을 실제로 정리할 수 없다.
- rule 9/10: P207 의 sweep + compare md/csv 생성 + format_result 메타 주입이 모두 `run_backtest.py` 에 inline 으로 남아 있음 (별도 모듈 파일 없음)
- `holding_structure/` (R3) / `drawdown/` (R2) 패키지와 대칭성 확보

**범위**:
- 신규 디렉토리: `app/backtest/reporting/allocation_constraints/`
- 신규 파일:
  1. `sweep.py` — `run_allocation_constraint_sweep(experiments, base_params, price_data, start, end, run_backtest_fn, format_result_fn, project_root)` — 현재 `run_backtest.py` line 1603~1718 의 inline sweep 로직 이전
  2. `report_writer.py` — `allocation_constraint_compare.md/.csv` 생성 로직 이전
  3. `diagnostic.py` — 비교 요약 문구 / `verdict` 판정 로직
  4. `meta_builder.py` (선택) — `format_result` 의 P207 meta 필드 (`allocation_mode`, `allocation_experiment_name`, `allocation_weight_floor/cap`, `allocation_fallback_used`, `allocation_trace_by_rebalance_date`) 를 빌드하는 순수 함수. 누락 시 KeyError raise.
- 수정: `app/run_backtest.py`
  - `run_cli_backtest` 내 P207 sweep 블록 제거 → `run_allocation_constraint_sweep(...)` 1줄 호출
  - `format_result` 내 P207 meta 필드 inline 구축 제거 → `allocation_constraints.meta_builder.build_allocation_meta(result)` 호출
- evidence_writer (R1 결과물) 의 `_render_allocation_section`, `_render_last_rebalance_trace_section` 가 `allocation_constraints` 의 데이터 구조를 import/참조

**Behavior 보존**:
- `allocation_constraint_compare.md` byte-level identical
- `allocation_constraint_compare.csv` byte-level identical
- `backtest_result.json` 의 allocation meta 필드 동일:
  - `allocation_mode`
  - `allocation_experiment_name`
  - `allocation_weight_floor`
  - `allocation_weight_cap`
  - `allocation_fallback_used`
  - `allocation_params`
  - `allocation_rebalance_trace_count`
  - `allocation_trace_by_rebalance_date`
- `dynamic_evidence_latest.md` 의 Allocation 섹션 및 Last Rebalance Trace 테이블 의미적 동등

**검증 게이트**:
- black + flake8 + py_compile
- Full Backtest 재실행
- G1/G2A~D/G3 compare 수치 동일성
- evidence Allocation 섹션 raw_scores / raw_vols / pre_cap / post_cap / final weights 동일성
- backtest_result.json allocation meta 필드 7개 모두 동일성

**위험도**: 중간 (P207 은 현재 모듈 파일이 없어 inline 블록을 처음으로 모듈화하는 것이므로 경계가 불분명한 부분이 있을 수 있음)

**예상 commit 메시지**:
`refactor(P209-CLEAN-R4): extract allocation_constraints/ package from run_backtest.py inline (P207 cleanup)`

---

### STEP R5 — 전 reporting 모듈의 암묵 fallback 제거

**목표**: 2.4 의 검출 패턴을 `app/backtest/reporting/` 전체 (drawdown/, holding_structure/, allocation_constraints/, evidence_writer.py) 에서 전수 감사 및 제거.

**Why**:
- rule 6/7: 현재 fallback 패턴은 데이터 손상과 정상 빈 케이스를 구분 못 함
- 다음 챕터에서 필터를 도입할 때 잘못된 데이터로 인한 오류가 묻혀서 잘못된 결정을 내릴 위험

**범위 (R2/R3/R4 가 끝난 뒤의 분할된 모듈 기준)**:

`drawdown/pipeline.py` `analyze_variant`:
- `nav_history`, `trades`, `rebalance_trace` 누락 시 `KeyError` raise
- 빈 리스트일 때 분석 skip 은 명시적 분기 + 명시적 verdict 표시

`drawdown/attribution.py`:
- `compute_ticker_contributions`: `prev_nav <= 0` 케이스를 정상 vs 비정상 분기
- `_price_at`: docstring 강화 + 호출자가 명시적 None 처리 확인

`drawdown/positions.py` `_build_close_series`:
- price_data 가 MultiIndex 가 아니면 `ValueError` raise (현재는 `return {}` silent fail)

`drawdown/selection_quality.py`:
- `_summarize_selection_quality([])` 의 0.0 fallback 제거. 빈 events 는 explicit `None` 또는 raise

`holding_structure/*` 및 `allocation_constraints/*`:
- 같은 패턴으로 감사 수행

`evidence_writer.py` (R1 결과물):
- `_bt_m.get('avg_held_positions', 0.0)` 같은 패턴 제거 (P208)
- `_bt_m.get('allocation_mode', 'dynamic_equal_weight')` 같은 P207 fallback 제거
- 섹션 자체를 conditional 호출로 변경 (필드 누락이 아니라 섹션 자체 미생성). P208 비활성 모드에서도 호출될 수 있으므로 섹션 존재 여부는 데이터 유무로 판정
- P207/P208/P209 결과가 메타에 존재해야 함을 가정하고 누락 시 builder 에서 KeyError

**fallback 검출 전수 감사 절차**:
```
cd app/backtest/reporting/
# 1. .get with non-None default
grep -rn "\.get(" . | grep -v ", None)"
# 2. or fallback operators
grep -rnE "or (\\[\\]|\\{\\}|0|0\\.0|\"\")" .
# 3. silent returns
grep -rnE "return (\\[\\]|\\{\\}|None)" .
# 4. broad except clauses
grep -rn "except (KeyError" .
```
검출된 각 케이스에 대해:
- (a) 허용 (accumulator, 초기화 등) → 허용 케이스 whitelist 에 추가
- (b) raise 로 변경 → 명시적 에러
- (c) explicit None 반환 + 호출자 분기 → 호출자 코드에서 None 처리 추가

**Behavior 보존**:
- 정상 데이터에서는 동일한 결과
- 비정상 데이터에서는 silent 0 대신 명시적 에러 (이건 의도된 변경)

**검증 게이트**:
- black + flake8 + py_compile
- Full Backtest 재실행 → 정상 통과 (현재 데이터에는 누락이 없으므로 raise 발생 안 함)
- 모든 산출물 동일성 재확인
- 일부러 잘못된 입력으로 unit-level smoke test → 명시적 에러 발생 확인
- 감사 절차 결과물 (허용 케이스 whitelist) 을 commit log 에 첨부

**위험도**: 중간 (실패 모드를 silent → loud 로 바꿈, 잠재 버그 표면화 가능)

**예상 commit 메시지**:
`refactor(P209-CLEAN-R5): remove implicit fallbacks across reporting (P207+P208+P209)`

---

### STEP R6 — UI view helper 추출 (`workflow.py` + `parameter_editor.py`)

**목표**: 두 view 파일의 inline UI 블록을 `pc_cockpit/views/helpers/` 로 추출.

**Why**:
- rule 9: `workflow.py` 와 `parameter_editor.py` 가 god view 가 됨
- UI 렌더링이 view orchestration 과 분리되어야 함
- P207/P208/P209 세 챕터의 UI 블록이 같은 파일에 inline 으로 누적된 상태 해소

**범위**:
- 신규 디렉토리: `pc_cockpit/views/helpers/`
- 신규 파일 3개:
  1. `allocation_panel.py` (P207)
     - `render_allocation_panel_for_parameters(p)` — parameter_editor 의 Allocation 섹션
     - `render_allocation_compare_expander(base_dir)` — workflow 의 allocation 비교표
     - `render_allocation_trace_expander(bt_meta)` — workflow 의 마지막 trace
  2. `holding_structure_panel.py` (P208)
     - `render_holding_structure_panel_for_parameters(p)` — parameter_editor 의 Holding Structure 섹션
     - `render_holding_structure_compare_expander(base_dir)` — workflow 의 G1~G8 비교
     - `render_holding_structure_caption(bt_meta)` — workflow 의 요약 caption
  3. `drawdown_contribution_panel.py` (P209)
     - `render_drawdown_contribution_panel(bt_meta, base_dir)` — workflow 의 A vs B summary, top toxic, worst events, bucket risk, 공통 toxic 하이라이트
- 수정: `pc_cockpit/views/workflow.py`
  - P207/P208/P209 inline 블록 (~285줄) 제거
  - 세 패널 함수 호출 1~3줄로 대체
- 수정: `pc_cockpit/views/parameter_editor.py`
  - P207 Allocation 섹션 + P208 Holding Structure 섹션 제거
  - 두 패널 함수 호출 1줄씩으로 대체

**Behavior 보존**:
- Streamlit UI 렌더링 결과 동일

**검증 게이트**:
- black + flake8 + py_compile
- import 경로 검증 (`python -c "from pc_cockpit.views.helpers.drawdown_contribution_panel import render_drawdown_contribution_panel"`)
- Streamlit 앱 수동 실행은 사용자 검증 (스크린샷 확인 권장)

**위험도**: 낮음 (순수 추출)

**예상 commit 메시지**:
`refactor(P209-CLEAN-R6): extract allocation/holding_structure/drawdown view panels (P207+P208+P209)`

---

### STEP R7 — 최종 동등성 검증 + 핸드오프 갱신

**목표**: 모든 STEP 완료 후 회귀 없음 확인 및 다음 챕터 진입 준비.

**범위**:
- Full Backtest 1회 재실행
- 산출물 동등성 비교 (R1~R6 시작 이전 reference 스냅샷과 비교):
  - `backtest_result.json` 의 summary + 핵심 meta (allocation + holding_structure + drawdown 모두)
  - `allocation_constraint_compare.md/.csv`
  - `holding_structure_compare.md/.csv/.json`
  - `drawdown_contribution_report.md/.json/.csv`
  - `dynamic_evidence_latest.md` (Performance / Hybrid Regime / Allocation / Last Rebalance Trace / Holding Structure / Drawdown Contribution / Promotion Verdict / Conclusion 섹션)
- `git log` 로 R1~R7 commit 7개 확인 (R7 자체 commit 포함)
- 구조 품질 최종 감사:
  - `app/backtest/reporting/` 아래 단일 파일 500줄 초과 없음
  - `run_cli_backtest` 함수 300줄 이하
  - `format_result` 함수 300줄 이하
  - `pc_cockpit/views/workflow.py` / `parameter_editor.py` 에 P207/P208/P209 inline 블록 0개
  - STEP R5 의 fallback 검출 명령들 결과 모두 whitelist 내 케이스만 남음
- handoff 문서 갱신 (둘 다):
  - `docs/handoff/P207_close_and_P208_handoff.md` 에 "P207 통합 layer cleanup 완료" 섹션 추가
  - `docs/handoff/P208_close_and_P209_handoff.md` 에 "P208/P209 cleanup 완료" 섹션 추가
  - 두 문서 모두 다음 챕터 (`P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`) 진입 가능 상태로 표시

**검증 게이트**:
- 모든 산출물 byte-level 또는 의미적 동등성
- 구조 감사 명령들 모두 통과
- handoff 문서 2개 갱신 확인

**예상 commit 메시지**:
`docs(P209-CLEAN-R7): finalize P207+P208+P209 refactor + update handoff docs`

---

## 5. 이번 plan 에서 확정된 사항 (더 이상 사용자 결정 아님)

- **P207 통합 layer cleanup 은 본 범위에 포함**. 옵션 아님. (기존 v1 plan 의 5.1 옵션 A/B/C 삭제)
- **`parameter_editor.py` 도 UI cleanup 범위에 포함**. workflow.py 만 다루지 않음.
- **`allocation_constraint_compare.md/.csv` 는 동등성 검증 대상**. holding_structure / drawdown 산출물과 동등한 우선순위.
- **fallback 검출은 `.get(..., 0)` 만이 아니라 `or {}`, `or []`, `or 0`, `or 0.0`, `or ""`, silent continue/return None/return {} 까지 전수 감사**.
- **handoff 갱신은 P207 과 P208 두 handoff 문서 모두 대상**.

---

## 6. 위험 평가

| STEP | 위험도 | 주요 리스크 | 완화책 |
|---|---|---|---|
| R1 | 낮음~중간 | f-string blob 추출 시 들여쓰기/공백 차이, P207/P208/P209 세 섹션 동시 건드림 | byte-level diff + 섹션별 존재 확인 |
| R2 | 중간 | cross-module import 누락, 함수 시그니처 변경 실수 | 모든 함수 시그니처 보존, `__init__.py` re-export 로 외부 진입점 보존 |
| R3 | 낮음 | R2 와 동일 패턴 | 동일 |
| R4 | 중간 | P207 는 기존 모듈 파일이 없어 경계 추출 시 의도하지 않은 로직 누락 가능 | allocation 관련 메타/사이드 이펙트 목록을 체크리스트로 만들고 하나씩 확인 |
| R5 | 중간 | silent fallback 을 loud error 로 바꾸면서 잠재 버그 표면화 | 정상 데이터에서 동일 결과를 보장하는 회귀 테스트 |
| R6 | 낮음 | Streamlit 자동 검증 어려움 | 사용자 수동 확인 |
| R7 | 낮음 | 최종 검증만 | — |

---

## 7. 완료 판정 기준

- R1~R7 commit 7개가 git log 에 존재 (R7 의 docs/handoff 갱신 commit 포함)
- Full Backtest 재실행 후 main `CAGR / MDD / Sharpe` 가 refactor 이전과 동일
- **P207 산출물 동등성** (신규 추가):
  - `allocation_constraint_compare.md` 의미적 동등
  - `allocation_constraint_compare.csv` 의미적 동등
  - `dynamic_evidence_latest.md` 의 Allocation 섹션 + Last Rebalance Trace 테이블 의미적 동등
  - `backtest_result.json` 의 allocation meta 필드 동등:
    - `allocation_mode`
    - `allocation_experiment_name`
    - `allocation_weight_floor`
    - `allocation_weight_cap`
    - `allocation_fallback_used`
    - `allocation_params`
    - `allocation_rebalance_trace_count`
    - `allocation_trace_by_rebalance_date`
- **P208 산출물 동등성**:
  - `holding_structure_compare.md/.csv/.json` 의미적 동등
  - `dynamic_evidence_latest.md` 의 Holding Structure 섹션 의미적 동등
  - `backtest_result.json` 의 holding_structure meta 필드 동등
- **P209 산출물 동등성**:
  - `drawdown_contribution_report.md/.json/.csv` 의미적 동등
  - `dynamic_evidence_latest.md` 의 Drawdown Contribution 섹션 의미적 동등
  - `backtest_result.json` 의 drawdown 관련 meta 필드 동등
- **구조 감사**:
  - `app/backtest/reporting/` 아래 단일 파일 500줄 초과 없음
  - `run_cli_backtest` 함수 300줄 이하
  - `format_result` 함수 300줄 이하
  - `pc_cockpit/views/workflow.py` 에 P207/P208/P209 inline UI 블록 0개
  - `pc_cockpit/views/parameter_editor.py` 에 P207/P208 inline UI 블록 0개
  - STEP R5 의 fallback 검출 명령들 결과: 허용 케이스 whitelist 만 남음
- **handoff 갱신**:
  - `docs/handoff/P207_close_and_P208_handoff.md` 에 cleanup 완료 섹션 추가
  - `docs/handoff/P208_close_and_P209_handoff.md` 에 cleanup 완료 섹션 추가
- 다음 챕터 (`P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`) 진입 가능

---

## 8. 사용자 확정 사항 (6건)

사용자 승인 완료. 이하 6개 결정은 실행 단계에서 그대로 따른다.

**결정 1 — R1 과 R4 순서** → **확정: A**
- R1 (evidence_writer) 먼저 → R2/R3/R4 (각 패키지 분할) → R5 (fallback) → R6 (view helpers) → R7
- evidence_writer 가 각 패키지의 data 만 받고 렌더링하는 단방향 의존 구조

**결정 2 — R4 의 meta_builder.py 포함 여부** → **확정: 가**
- `allocation_constraints/meta_builder.py` 파일을 추가해 `format_result` 의 P207 meta 필드를 순수 함수로 분리
- holding_structure / drawdown 과 대칭되는 구조 유지

**결정 3 — 동등성 기준** → **확정: R1/R2/R3/R4/R6 = byte-level (ㄱ), R5 = 의미적 (ㄴ)**
- R1~R4, R6 는 순수 추출이므로 생성된 markdown/json 파일이 byte-level identical 이어야 함
- R5 는 에러 분기 추가로 공백/라인 변경이 불가피하므로 의미적 동등성 (필드/수치 동일)

**결정 4 — R5 fallback 제거 강도** → **확정: (c) 혼합**
- 산출물 메타 필드 (필수): 누락 시 `KeyError` / `ValueError` raise
- 조회 함수 (선택): `_price_at` 같은 lookup 함수는 explicit `None` 반환 + 호출자가 명시적으로 None 분기 처리
- 허용 케이스 whitelist 를 R5 commit log 에 첨부

**결정 5 — `parameter_editor.py` cleanup 을 R6 에 포함할지** → **확정: I**
- R6 에서 `workflow.py` 와 `parameter_editor.py` 를 묶어서 처리
- 두 파일 모두 view helper 호출로 치환하는 동일 패턴

**결정 6 — STEP 진행 방식** → **확정: (1) 매 STEP 승인**
- 매 STEP 종료 시 사용자 승인 받은 후 다음 STEP 진입
- 각 STEP 종료 보고는 반드시 `## A. 기능/산출물 검증` + `## B. 구현 규칙/구조 품질 검증` 2개 섹션
- 특히 R4 (P207) 와 R5 (fallback) 는 사용자 검증이 중요

---

**다음 단계**: R1 진입 승인을 받는 즉시 `STEP R1 — evidence_writer.py 추출` 을 시작한다.

---

## 9. 이 plan 이 다음 챕터에 미치는 영향

이 cleanup 이 끝나면 다음 두 챕터가 훨씬 안전하게 진입 가능하다.

- **`P209-STEP9A-BASELINE-REALIGNMENT-TO-LATEST-UI-V1`**:
  - baseline 설정이 `drawdown/pipeline.py` 한 곳에 모이므로 변경이 최소화됨
  - 현재 god module 에서는 baseline spec 변경이 17 함수 사이에 흩어진 영향도 검토를 요구함
  - evidence_writer 의 `_render_drawdown_contribution_section` 만 수정하면 evidence md 의 A/B 표시가 일관되게 변경됨

- **`P209-STEP9B-TRACKA-TOXIC-ASSET-DROP-RULES-V1`**:
  - filter 설계 시 `drawdown/attribution.py` 와 `drawdown/selection_quality.py` 만 import 해서 재사용 가능
  - 현재는 god module 전체를 import 해야 함
  - toxic ticker 리스트 기반 필터를 `BacktestRunner.run()` 에 주입할 때, 분석 모듈의 orchestration 코드를 실수로 운영 경로에 섞지 않음

- **향후 allocation 관련 실험 (P210+ 가상)**:
  - `allocation_constraints/` 패키지가 존재하므로 P207 패턴을 흉내낼 필요 없이 같은 구조로 추가 가능
  - 새 실험은 `allocation_constraints/sweep.py` 또는 같은 위치에 추가되며 `run_backtest.py` god file 로 흘러 들어가지 않음
