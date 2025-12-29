# 튜닝 엔진 개발 이력 (AI 인수인계용)

> **작성**: 2025-12-21  
> **Author**: 형수  
> **목적**: 다른 AI가 튜닝 작업을 이어받을 때 참조할 상세 개발 이력

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [핵심 파일 구조](#2-핵심-파일-구조)
3. [개발 타임라인](#3-개발-타임라인)
4. [Phase별 상세 구현](#4-phase별-상세-구현)
5. [현재 상태 및 검증 결과](#5-현재-상태-및-검증-결과)
6. [다음 작업 제안](#6-다음-작업-제안)
7. [트러블슈팅 이력](#7-트러블슈팅-이력)

---

## 1. 프로젝트 개요

### 1.1 목표

KRX ETF 전략의 **파라미터 튜닝 파이프라인**을 구축하여:
- **과적합 방지**: Test 봉인, Walk-Forward 검증
- **재현성 보장**: Manifest 저장, Replay 검증
- **데이터 건전성**: Preflight 검사, data_digest 해시

### 1.2 핵심 개념

| 개념 | 설명 |
|------|------|
| **Gate 시스템** | 단계별 필터링 (Gate0 → Gate1 → Gate2 → Gate3) |
| **멀티 룩백** | 3M/6M/12M 룩백으로 안정성 검증 |
| **Walk-Forward** | 롤링 윈도우로 Out-of-Sample 성능 평가 |
| **Manifest** | 튜닝 결과 JSON 저장 (재현성 추적) |
| **Telemetry** | 실행 로그 JSONL 저장 |

### 1.3 Gate 시스템 흐름

```
Gate0 (Preflight)
  ↓ 데이터 건전성 검사 (parquet 읽기, 커버리지, 결측)
  ↓ data_digest 해시 생성
  
Gate1 (Top-N 선정)
  ↓ Optuna 튜닝 → Val Sharpe 기준 Top-N 선정
  ↓ 중복 제거 (deduplicate_top_n_candidates)
  ↓ 가드레일 검사 (MDD 일관성, RSI 실효성)
  
Gate2 (Walk-Forward 안정성)
  ↓ 6개 윈도우 롤링 백테스트
  ↓ stability_score = mean(outsample_sharpe) / (std + 0.1)
  ↓ win_rate = outsample_sharpe > 0인 윈도우 비율
  
Gate3 (최종 Test)
  ↓ Gate2 통과 후에만 Test 계산
  ↓ 최종 보고서 생성
```

---

## 2. 핵심 파일 구조

### 2.1 튜닝 엔진 코어 (`extensions/tuning/`)

| 파일 | 역할 | 주요 함수/클래스 |
|------|------|-----------------|
| `types.py` | 데이터 타입 정의 | `BacktestMetrics`, `BacktestRunResult`, `DebugInfo`, `Period` |
| `runner.py` | 백테스트 실행 | `run_backtest_for_tuning()`, `_run_single_backtest()` |
| `split.py` | 기간 분할 | `calculate_split()`, `create_period()` |
| `gates.py` | Gate 로직 | `deduplicate_top_n_candidates()`, `apply_gate1_filters()` |
| `guardrails.py` | 가드레일 검사 | `check_mdd_consistency()`, `check_rsi_effectiveness()` |
| `objective.py` | 목적함수 | `calculate_objective()` |
| `walkforward.py` | Walk-Forward | `MiniWalkForward`, `generate_windows()` |
| `manifest.py` | Manifest 저장 | `save_manifest()`, `validate_manifest()` |
| `telemetry.py` | 텔레메트리 | `emit_*()` 함수들 |
| `cache.py` | 캐시 관리 | `BacktestCache` |

### 2.2 실행 스크립트 (`tools/`)

| 파일 | 역할 | 주요 옵션 |
|------|------|----------|
| `run_phase15_realdata.py` | 메인 튜닝 실행 | `--runs`, `--trials`, `--seed`, `--top-n`, `--analysis-mode`, `--force-gate2` |
| `run_phase20_real_gate2.py` | Gate2 전용 실행 | `--stop-at-gate2` |
| `replay_manifest.py` | Manifest 재현성 검증 | `--mode mock/real`, `--tolerance` |

### 2.3 테스트 (`tests/tuning/`)

| 파일 | 테스트 대상 |
|------|------------|
| `test_smoke.py` | 기본 동작 검증 |
| `test_gate_e2e.py` | Gate 전체 흐름 |
| `test_gate2_loop.py` | Gate2 Walk-Forward |
| `test_replay_determinism.py` | Replay 재현성 |
| `test_cache_isolation.py` | 캐시 격리 |
| `test_lookback_effect_sanity.py` | 룩백 효과 검증 |

### 2.4 문서 (`docs/tuning/`)

| 파일 | 내용 |
|------|------|
| `00_overview.md` | 설계 원칙, 배경, 용어 정의 |
| `01_metrics_guardrails.md` | 지표 정의, 가드레일 |
| `02_objective_gates.md` | 목적함수, Gate 로직 |
| `03_walkforward_manifest.md` | Walk-Forward, Manifest 스키마 |
| `04_implementation.md` | 구현 세부사항 |
| `05_development_history.md` | **이 문서** (개발 이력) |

### 2.5 데이터 (`data/`)

| 폴더 | 내용 |
|------|------|
| `data/price/` | 종목별 parquet 파일 |
| `data/tuning_test/` | Manifest JSON 파일 |
| `data/telemetry/` | 텔레메트리 JSONL 파일 |

---

## 3. 개발 타임라인

### Phase 1.0 ~ 1.7 (2025-12-15 ~ 12-17)

| 버전 | 날짜 | 주요 작업 |
|------|------|----------|
| 1.0 | 12-15 | 기본 튜닝 UI/UX 개선 |
| 1.1 | 12-16 | Test 봉인 원칙 적용, Objective 함수 변경 |
| 1.2 | 12-16 | 캐시 설계, 이상치 감지 |
| 1.3 | 12-16 | Split 충돌 규칙, 룩백 정의 |
| 1.4 | 12-17 | WF 윈도우 스냅, Manifest 스키마 |
| 1.5 | 12-17 | BacktestRunResult 도입, 캐시 키 강화 |
| 1.6 | 12-17 | MDD 일관성 Gate, RSI 실효성 Logic Check |
| 1.7 | 12-17 | Manifest 검증, Replay 도구 |

### Phase 2.0 ~ 2.1 (2025-12-20 ~ 12-21)

| 버전 | 날짜 | 주요 작업 |
|------|------|----------|
| 2.0 | 12-20 | Real Data Gate2, `--force-gate2` 옵션 |
| 2.1 | 12-21 | 멀티룩백 증거 강화, Real Data Gate0 (Preflight) |

---

## 4. Phase별 상세 구현

### 4.1 Phase 2.0 — Real Data Gate2 & Force-Gate2

**문제**: 실데이터에서 Gate1 후보가 0개일 때 Gate2를 테스트할 수 없음

**해결**:
1. `--force-gate2` 옵션 추가
2. Gate1 후보가 없어도 `completed_trials`에서 직접 Top-N 추출
3. `analysis_mode`에서만 허용, manifest에 `force_gate2: true` 기록

**구현 파일**:
- `tools/run_phase15_realdata.py`: `--force-gate2` CLI 옵션
- `tools/run_phase20_real_gate2.py`: Gate2 전용 실행 스크립트

**핵심 코드** (`run_phase15_realdata.py` 659-682행):
```python
if len(deduped_candidates) == 0 and force_gate2 and analysis_mode:
    # completed_trials에서 직접 Top-N 추출
    sorted_trials = sorted(
        completed_trials, key=lambda x: x["val_sharpe"], reverse=True
    )[:top_n]
    deduped_candidates = [
        {"params": t["params"], "val_sharpe": t["val_sharpe"]}
        for t in sorted_trials
    ]
```

### 4.2 Phase 2.1 — 멀티룩백 증거 강화

**문제**: 3M/6M/12M 룩백이 실제로 다른 결과를 만드는지 증거가 부족

**해결**:
1. `DebugInfo`에 증거 필드 추가
2. Manifest `by_lookback`에 debug 필드 저장
3. `replay_manifest`에서 검증 로그 출력

**추가된 필드** (`extensions/tuning/types.py`):
```python
@dataclass
class DebugInfo:
    # 기존 필드
    lookback_months: int = 0
    lookback_start_date: Optional[date] = None
    params_hash: str = ""
    cache_key: str = ""
    
    # Phase 2.1 추가: 멀티룩백 증거 강화
    effective_eval_start: Optional[date] = None  # 룩백 적용 후 성과 계산 시작일
    bars_used: int = 0  # 룩백 적용 후 실제 계산에 사용된 봉 수
    signal_days: int = 0  # 신호 발생 일수
    order_count: int = 0  # 주문 횟수
```

**검증 결과**:
```
[Lookback 3M]  lookback_start=2024-03-30
[Lookback 6M]  lookback_start=2023-12-30
[Lookback 12M] lookback_start=2023-06-30
→ 룩백별로 확실히 다른 시작일 기록됨
```

### 4.3 Phase 2.1 — Real Data Gate0 (Preflight)

**문제**: 실데이터 튜닝 전 데이터 건전성 검사 부족

**해결**:
1. `DataPreflightService`에 `data_digest` 해시 추가
2. `common_period` (공통 기간) 계산
3. Manifest에 기록

**추가된 필드** (`app/services/data_preflight.py`):
```python
@dataclass
class PreflightReport:
    # 기존 필드
    ok: bool
    fail_count: int
    total_count: int
    
    # Phase 2.1 추가
    data_digest: str = ""  # 데이터 상태 해시 (16자)
    common_period_start: Optional[date] = None
    common_period_end: Optional[date] = None
```

**data_digest 계산 로직**:
```python
def _compute_data_digest(self, ticker_results, start_date, end_date):
    digest_parts = [
        f"period:{start_date}~{end_date}",
        f"tickers:{len(ok_results)}",
    ]
    for r in ok_results:
        digest_parts.append(f"{r.ticker}:{r.row_count}:{r.data_start}:{r.data_end}")
    
    digest_str = "|".join(digest_parts)
    return hashlib.sha256(digest_str.encode()).hexdigest()[:16]
```

### 4.4 Gate1 로그 문구 정리

**변경 전**:
```
Gate1 Top-N 선정: 13개 → 3개 (중복 제거)
```

**변경 후**:
```
Gate1 Top-N 선정: candidates=13, selected_top_n=3, dedup_removed=0
```

**구현 파일**:
- `extensions/tuning/gates.py` 238-241행
- `tools/run_phase15_realdata.py` 553-554행

---

## 5. 현재 상태 및 검증 결과

### 5.1 Mock 모드 테스트 결과 (2025-12-21)

```bash
python -m tools.run_phase20_real_gate2 --runs 1 --trials 10 --seed 42 --top-n 3 --analysis-mode --force-gate2 --stop-at-gate2
```

**결과**:
```
Gate1: candidates=7, selected_top_n=3, dedup_removed=0
Gate2: stability=2.68, win_rate=100% (6 windows)
Manifest: analysis_20251221_175517_8c9e4d.json
```

### 5.2 Replay 재현성 검증

```bash
python -m tools.replay_manifest "data\tuning_test\analysis_20251221_175517_8c9e4d.json" --mode mock --tolerance 1e-6
```

**결과**:
```
✅ REPLAY PASS - 재현성 검증 통과 (3개 룩백 모두 tol=1e-6 이내)

멀티룩백 증거:
  [3M]  lookback_start=2024-03-30, eval_start=2023-06-15, bars=128
  [6M]  lookback_start=2023-12-30, eval_start=2023-06-15, bars=128
  [12M] lookback_start=2023-06-30, eval_start=2023-06-15, bars=128
```

### 5.3 테스트 스위트 상태

```bash
pytest tests/tuning/ -v
```

| 테스트 | 상태 |
|--------|------|
| `test_smoke.py` | ✅ PASS |
| `test_gate_e2e.py` | ✅ PASS |
| `test_gate2_loop.py` | ✅ PASS |
| `test_replay_determinism.py` | ✅ PASS |

---

## 6. 다음 작업 제안

### 6.1 단기 (우선순위 높음)

| 작업 | 설명 | 예상 시간 |
|------|------|----------|
| **실데이터 테스트** | Mock이 아닌 실제 parquet으로 전체 파이프라인 검증 | 2시간 |
| **Gate3 구현** | Test 봉인 해제 및 최종 보고서 생성 | 1시간 |
| **UI 연동** | 튜닝 결과를 React 대시보드에 표시 | 3시간 |

### 6.2 중기

| 작업 | 설명 |
|------|------|
| **정식 Walk-Forward** | 더 많은 윈도우, PSS 점수 계산 |
| **파라미터 민감도 분석** | 파라미터 변화에 따른 성능 변화 시각화 |
| **자동 리포트 생성** | Manifest → PDF/HTML 보고서 |

### 6.3 장기

| 작업 | 설명 |
|------|------|
| **TP/SL 고도화** | ATR 기반 동적 손절, Trailing Stop |
| **Market Breadth** | 시장 체력 지표 추가 |
| **이벤트 캘린더** | FOMC, CPI 등 이벤트 기반 필터 |

---

## 7. 트러블슈팅 이력

### 7.1 `MiniWalkForward` universe_codes 누락

**증상**: Gate2 실행 시 `universe_codes` 미전달로 백테스트 실패

**원인**: `MiniWalkForward.__init__()`에 `universe_codes` 파라미터 없음

**해결** (`extensions/tuning/walkforward.py`):
```python
class MiniWalkForward:
    def __init__(self, ..., universe_codes: Optional[List[str]] = None):
        self.universe_codes = universe_codes
    
    def run(self, params):
        # _run_single_backtest 호출 시 universe_codes 전달
        train_metrics = _run_single_backtest(
            ...,
            universe_codes=self.universe_codes,
        )
```

### 7.2 `WFResult` 객체 접근 오류

**증상**: `AttributeError: 'WFResult' object has no attribute 'windows'`

**원인**: `MiniWalkForward.run()`이 `List[WFResult]`를 반환하는데, 단일 객체로 접근

**해결** (`tools/replay_manifest.py`):
```python
# 변경 전
wf_result = wf.run(params)
windows = len(wf_result.windows)

# 변경 후
wf_results_list = wf.run(params)
windows = len(wf_results_list)
```

### 7.3 Gate1 후보 0개 문제

**증상**: 실데이터에서 가드레일 통과 후보가 0개

**원인**: MDD 일관성, RSI 실효성 등 가드레일이 너무 엄격

**해결**: `--force-gate2` 옵션으로 가드레일 우회 (분석 모드 전용)

---

## 📌 AI 인수인계 체크리스트

다른 AI가 이 작업을 이어받을 때:

1. **필독 문서**:
   - `docs/tuning/00_overview.md` — 설계 원칙
   - `docs/tuning/05_development_history.md` — 이 문서
   - `docs/AI_CONTEXT_PACK.md` — 전체 시스템 컨텍스트

2. **핵심 코드 파악**:
   - `extensions/tuning/types.py` — 데이터 타입
   - `extensions/tuning/runner.py` — 백테스트 실행
   - `tools/run_phase15_realdata.py` — 메인 실행 스크립트

3. **테스트 실행**:
   ```bash
   # 기본 동작 확인
   pytest tests/tuning/test_smoke.py -v
   
   # Mock 모드 튜닝 실행
   python -m tools.run_phase20_real_gate2 --runs 1 --trials 10 --seed 42 --top-n 3 --analysis-mode --force-gate2 --stop-at-gate2
   
   # Replay 검증
   python -m tools.replay_manifest "data\tuning_test\<manifest>.json" --mode mock --tolerance 1e-6
   ```

4. **주의사항**:
   - Test 봉인 원칙 준수 (Gate2 통과 전 Test 계산 금지)
   - Manifest 스키마 변경 시 `replay_manifest.py`도 함께 수정
   - 캐시 키 변경 시 기존 캐시 무효화 필요

---

**마지막 업데이트**: 2025-12-29
**작성자**: Cascade AI (Claude)

---

## 4.5 Phase 13.5 & 14 — Operational Hardening & UI Integration (2025-12-29)

### 1. Active Surface & Legacy Quarantine (Phase 13.5)
- **Active Surface**: `deploy/`, `app.cli`, `tools.paper_trade`, `backend`.
- **Legacy Quarantine**: `web/`, `pc/`, `scripts/daily/` 등 구형 코드를 `_archive/`로 격리.
- **Audit**: Antigravity Rule(한국어 주석, 하드코딩 등) 감사 수행.

### 2. Read-Only API Backend (Phase 14.1 ~ 14.2)
- **Observer Pattern**: 엔진 코드 import 없이 오직 `logs/`, `state/`, `reports/` 파일만 읽는 FastAPI 백엔드 구축 (`backend/main.py`).
- **Robustness**: PowerShell 생성 로그(UTF-16) 등 다양한 인코딩에 대응하는 `safe_read_text_advanced` 구현.
- **Evidence-Based**: 로그 내 `[OK]`, `[ERROR]` 키워드를 카운트하여 상태 배지(`OK`, `FAIL`, `SKIP`) 판정.

### 3. React Dashboard (Phase 14.3)
- **Single HTML**: 빌드 과정 없이 `dashboard/index.html` 단일 파일로 동작하는 React 앱.
- **Warning Indicator**: 로그 인코딩 손상 시 `read_quality: partial` 감지하여 🟡 노란 배지 표시.
- **Features**: 
    - Dashboard (Equity/Cash)
    - Portfolio Table
    - Daily Signals
    - Raw Log Viewer

