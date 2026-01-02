# KRX Alertor — Future Development Roadmap

> **작성**: 2025-12-11 (최종 수정: 2025-12-21)  
> **Author**: 형수  
> **목적**: 향후 개발 항목 영구 기록

---

## 개요

이 문서는 현재 개발이 완료된 KRX Alertor 시스템의 **향후 고도화 로드맵**을 정리합니다.

### Phase 분류별 개발 필요성 요약

| Phase | 항목 | 개발 필요 여부 | 이유 |
|-------|------|----------------|------|
| **1** | **튜닝/검증 체계** | ✅ **최우선** | Test 봉인, 목적함수 개선, 변수 스키마 표준화 |
| 2 | 미니 Walk-Forward | ✅ 개발 필요 | 롤링 검증으로 안정성 확보 |
| 3 | 정식 Walk-Forward | ✅ 개발 필요 | 오케스트레이션/윈도우 시스템 |
| 4 | TP/SL 고도화 | ✅ 개발 필요 | 현재 단일 stop_loss 기반이라 구조 확장 필요 |
| 5 | Breadth / 이벤트 | ✅ 개발 필요 | 신규 데이터 + 신규 레짐 로직 |

---

## 1. Phase 1 — 튜닝/검증 체계 강화 ⭐ 최우선

> **상세 설계 문서**: `docs/tuning_validation_design.md`

### 1.1 배경

최근 튜닝 결과에서 **Train은 높고 Val은 부진한데 Test가 비정상적으로 높게 튀는** 패턴이 반복됨.  
"미세조정으로 성능 올리기"보다 먼저 **검증 체계(Test 봉인, 목적함수, 재현성)**가 필요.

### 1.2 핵심 개발 항목

#### (1) Test 봉인 원칙 적용

| 항목 | 현재 | 개선 |
|------|------|------|
| Optuna objective | Test Sharpe | **Val Sharpe** |
| 결과 테이블 정렬 | Test 기준 | **Val 기준** |
| Test 컬럼 | 항상 표시 | **🔒 선택 확정 후 공개** |

#### (2) 목적함수 개선

```python
# 현재
return test_sharpe

# 개선 (Option A: Val + MDD 페널티)
return val_sharpe - max(0, abs(val_mdd) - 15) * 0.1
```

#### (3) 변수 스키마 표준화

`config/tuning_variables.yaml` 신규 작성:
- 카테고리 분류 (trend/momentum/risk/market/execution)
- 룩백별 추천 범위
- 의존성/제약 조건
- 전략적 의미/리스크 설명

#### (4) UI 개선

- 변수 카테고리별 접기/펼치기
- 활성 변수 count + 탐색 공간 크기 표시
- 튜닝 모드 프리셋 (Discovery / Stability / Refine)

#### (5) run_manifest 저장

모든 튜닝 실행 조건/결과를 JSON으로 저장하여 재현성 보장.

### 1.3 구현 우선순위

| 순서 | 항목 | 예상 시간 |
|------|------|----------|
| 1 | Test 봉인 UI 적용 | 1일 |
| 2 | Objective 함수 변경 (Val 기반) | 0.5일 |
| 3 | 변수 스키마 YAML 작성 | 1일 |
| 4 | UI 카테고리 분류 | 1일 |
| 5 | 튜닝 모드 프리셋 | 0.5일 |
| 6 | run_manifest 저장 | 1일 |

---

## 2. Phase 2 — 미니 Walk-Forward

### 2.1 목표

정식 Walk-Forward 프레임워크 개발 전, **최소한의 롤링 검증**으로 안정성 확보.

### 2.2 개발 항목

#### (1) 롤링 윈도우 생성

```
전체 기간: 24개월
Window 1: Train 18M | Val 3M | Test 3M
Window 2: Train 18M | Val 3M | Test 3M (stride=2M)
...
```

#### (2) 안정성 점수 계산

```python
stability_score = sharpe_mean / (sharpe_std + 0.1)
```

#### (3) UI 표시

- 윈도우별 성과 테이블
- 안정성 점수 뱃지
- 승률 (Sharpe > 0인 윈도우 비율)

---

## 3. Phase 3 — 정식 Walk-Forward Framework

### 3.1 목표

- 단일 백테스트 샘플이 아닌, **여러 시점의 롤링 윈도우**에서의 성능 안정성 검증
- **파라미터 민감도와 안정성 평가** (PSS Score)
- 실전 적용 가능성 판단 기준 강화

### 3.2 개발 필요 요소

#### (1) 윈도우 생성기 (Window Generator)

**기능:**
- 시작일~종료일 범위 내에서 지정된 기간 단위로 윈도우 생성

**예시:**
```
lookback = 24M
test = 3M
stride = 1M
→ (21M train, 3M test) 형태의 다중 윈도우 생성
```

**출력 예:**
```json
[
  {"train": ("2020-01-01", "2021-09-30"), "test": ("2021-10-01", "2021-12-31")},
  {"train": ("2020-02-01", "2021-10-31"), "test": ("2021-11-01", "2022-01-31")},
  ...
]
```

#### (2) 윈도우별 백테스트 실행 오케스트레이터

- 기존 `BacktestRunner`를 그대로 사용
- 각 윈도우에서 같은 전략/파라미터를 반복 실행

**Pseudo:**
```python
for w in windows:
    result = runner.run(window_params)
    collect(results)
```

#### (3) 통합 결과 계산

각 윈도우별 지표를 수집하여 다음을 계산:
- **평균 Sharpe**
- **평균 CAGR**
- **평균 MDD / 최악 MDD**
- **Sharpe 분산**
- **승률** (Window 수 대비 성과 우수 비율)

#### (4) PSS (Parameter Stability Score)

**의미:**
- 파라미터가 여러 시점에서 얼마나 일관적으로 성능을 냈는지 평가하는 지표

**개발 대상:**
- Sharpe의 변동성 (표준편차)
- 윈도우별 Outlier 비율
- 평균 대비 성능 안정성

**공식 예:**
```
PSS = Sharpe_mean / (Sharpe_std + epsilon)
```

#### (5) UI & API

- `/api/v1/backtest/walkforward` 신규
- **결과 표시:**
  - Stability Chart
  - Window-by-Window 라인 차트
  - PSS 요약

---

## 4. Phase 4 — TP / SL 고도화 (Take Profit / Trailing Stop)

### 4.1 목표

현재 단일 `stop_loss%` & 하이브리드 손절 매트릭스를 넘어선  
**프로페셔널한 변동성 기반 리스크 관리 시스템** 구축

### 4.2 개발 요소

#### (1) ATR 기반 Stop Loss

- 14일 ATR 기반 동적 손절

**예:**
```python
stop = entry_price - k * ATR
```

- 변동성 큰 ETF는 더 넓은 손절 범위 확보

#### (2) Trailing Stop (고점 추적)

**기능:**
- "고점 대비 X% 하락 시 매도"

**필요 요소:**
- 고점 갱신 로직
- trailing 기준 동적 업데이트

#### (3) Take Profit (익절)

**전략 예시:**
- 수익률 +25% 도달 시 50% 비중 매도
- +40% 도달 시 전량 매도

**엔진 변경:**
- `Strategy.evaluate_exit()` 로직 확장 필요

#### (4) 파라미터 튜닝 연동

Optuna에 새로운 파라미터 추가:
- `atr_period`, `atr_k`
- `tp_ratio_1`, `tp_ratio_2`
- `trailing_pct`

---

## 5. Phase 5 — Market Breadth & 이벤트 캘린더

### 5.1 목표

- 시장의 **체력(광범위한 상승/하락 참여도)**을 반영해 레짐 정확도 강화
- **이벤트 기반 회피/방어 필터** 추가

### 5.2 Breadth 개발 항목

#### (1) 상승/하락 비율
- 일간 상승 ETF 비율
- 20일 평균 Breadth

#### (2) 52주 신고가 / 신저가
- 강세장 필터로 활용

#### (3) AD Line (Advance–Decline)
- 중기 추세 필터

#### (4) Breadth Score → 레짐에 반영

**예:**
```python
if breadth_score >= 0.6:
    # Bull 강화
elif breadth_score <= 0.3:
    # Bear 주의
```

### 5.3 이벤트 캘린더

**수집 대상:**
- FOMC
- CPI / PPI
- 고용지표
- 옵션 만기일
- Quadruple Witching Day

**기능:**
- 이벤트 하루 전 → 비중 축소
- 이벤트 당일 → 매수 중단, 손절 강화

**구현:**
```python
# EventCalendarService 신규
if event_today:
    risk_level *= 0.7
```

---

## 현재 코드 구조와의 연결

| 현재 모듈 | Phase 1 연결 | Phase 2-3 연결 | Phase 4 연결 | Phase 5 연결 |
|-----------|--------------|----------------|--------------|---------------|
| `web/dashboard/Strategy.tsx` | Test 봉인 UI | - | - | - |
| `app/services/backtest_service.py` | Objective 변경 | 윈도우별 실행 | - | - |
| `config/tuning_variables.yaml` | 변수 스키마 | - | - | - |
| `core/engine/backtest.py` | - | 롤링 백테스트 | TP/SL 로직 확장 | - |
| `core/strategy/` | - | - | 익절/손절 전략 | Breadth 필터 |
| `extensions/monitoring/regime.py` | - | - | - | Breadth Score 연동 |

---

## 우선순위 제안

1. **Phase 1 (튜닝/검증 체계)** ⭐ - 현재 튜닝 결과의 신뢰도 확보 **최우선**
2. **Phase 2 (미니 Walk-Forward)** - 최소한의 롤링 검증
3. **Phase 3 (정식 Walk-Forward)** - 본격적인 안정성 검증 프레임워크
4. **Phase 4 (TP/SL)** - 실전 운용 시 리스크 관리 강화
5. **Phase 5 (Breadth/이벤트)** - 고급 기능, 리서치 병행 필요

---

## Archive — 구현 완료 항목

---

### ✅ Phase 2.1 — 멀티룩백 증거 강화 & Real Data Gate0 (2025-12-21)

#### 배경
- 3M/6M/12M 룩백이 실제로 다른 결과를 만드는지 증거가 부족했음
- 실데이터 튜닝 전 데이터 건전성 검사가 미흡했음

#### 구현 내용

**1) DebugInfo 필드 추가** (`extensions/tuning/types.py`)
```python
@dataclass
class DebugInfo:
    # Phase 2.1 추가: 멀티룩백 증거 강화
    effective_eval_start: Optional[date] = None  # 룩백 적용 후 성과 계산 시작일
    bars_used: int = 0  # 룩백 적용 후 실제 계산에 사용된 봉 수
    signal_days: int = 0  # 신호 발생 일수
    order_count: int = 0  # 주문 횟수
```

**2) BacktestMetrics 필드 추가** (`extensions/tuning/types.py`)
```python
@dataclass
class BacktestMetrics:
    # Phase 2.1 추가
    signal_days: int = 0
    order_count: int = 0
    first_trade_date: Optional[str] = None
```

**3) Manifest by_lookback debug 저장** (`tools/run_phase15_realdata.py`)
```python
debug_fields = {
    "effective_eval_start": bt_result.debug.effective_eval_start.isoformat(),
    "bars_used": bt_result.debug.bars_used,
    "signal_days": bt_result.debug.signal_days,
    "order_count": bt_result.debug.order_count,
    "lookback_start_date": bt_result.debug.lookback_start_date.isoformat(),
}
by_lookback[lb] = {..., "debug": debug_fields}
```

**4) replay_manifest debug 검증** (`tools/replay_manifest.py`)
- 원본 debug 필드와 재실행 debug 필드 비교 출력
- `lookback_start_date`가 룩백별로 다른지 확인

**5) Gate1 로그 문구 정리** (`extensions/tuning/gates.py`)
```python
# 변경 전: "Gate1 Top-N 선정: 13개 → 3개 (중복 제거)"
# 변경 후: "Gate1 Top-N 선정: candidates=13, selected_top_n=3, dedup_removed=0"
```

**6) Real Data Gate0 (Preflight)** (`app/services/data_preflight.py`)
```python
@dataclass
class PreflightReport:
    # Phase 2.1 추가
    data_digest: str = ""  # 데이터 상태 해시 (16자)
    common_period_start: Optional[date] = None
    common_period_end: Optional[date] = None
```

#### 검증 결과 (Mock 모드)
```
Gate1: candidates=7, selected_top_n=3, dedup_removed=0
Gate2: stability=2.68, win_rate=100% (6 windows)
Replay: ✅ PASS (tol=1e-6)

멀티룩백 증거:
  [3M]  lookback_start=2024-03-30
  [6M]  lookback_start=2023-12-30
  [12M] lookback_start=2023-06-30
→ 룩백별로 확실히 다른 시작일 기록됨
```

#### 수정된 파일
- `extensions/tuning/types.py` — DebugInfo, BacktestMetrics 필드 추가
- `extensions/tuning/runner.py` — debug 필드 채우기
- `extensions/tuning/gates.py` — Gate1 로그 문구 변경
- `tools/run_phase15_realdata.py` — by_lookback debug 저장, preflight data_digest 저장
- `tools/replay_manifest.py` — debug 필드 검증 로그 출력
- `app/services/data_preflight.py` — data_digest, common_period 추가

---

### ✅ Phase 2.0 — Real Data Gate2 & Force-Gate2 (2025-12-20~21)

#### 배경
- 실데이터에서 Gate1 후보가 0개일 때 Gate2를 테스트할 수 없었음
- MiniWalkForward에 universe_codes가 전달되지 않아 백테스트 실패

#### 구현 내용

**1) `--force-gate2` 옵션** (`tools/run_phase15_realdata.py`)
```python
# Gate1 후보가 없어도 completed_trials에서 직접 Top-N 추출
if len(deduped_candidates) == 0 and force_gate2 and analysis_mode:
    sorted_trials = sorted(completed_trials, key=lambda x: x["val_sharpe"], reverse=True)[:top_n]
    deduped_candidates = [{"params": t["params"], "val_sharpe": t["val_sharpe"]} for t in sorted_trials]
```

**2) `run_phase20_real_gate2.py` 스크립트** (`tools/`)
- Gate2 전용 실행 스크립트
- `--stop-at-gate2` 옵션으로 Gate3 이전 중단

**3) MiniWalkForward universe_codes 전달** (`extensions/tuning/walkforward.py`)
```python
class MiniWalkForward:
    def __init__(self, ..., universe_codes: Optional[List[str]] = None):
        self.universe_codes = universe_codes
    
    def run(self, params):
        train_metrics = _run_single_backtest(..., universe_codes=self.universe_codes)
```

**4) replay_manifest Gate2 WF 검증** (`tools/replay_manifest.py`)
```python
def replay_gate2_wf(config, use_mock):
    wf = MiniWalkForward(..., universe_codes=config["universe_codes"])
    wf_results_list = wf.run(params)
    # stability, win_rate 비교
```

#### 수정된 파일
- `tools/run_phase15_realdata.py` — `--force-gate2` CLI 옵션
- `tools/run_phase20_real_gate2.py` — 신규 스크립트
- `extensions/tuning/walkforward.py` — universe_codes 파라미터 추가
- `tools/replay_manifest.py` — Gate2 WF 검증 로직

---

### ✅ Phase 1.5 ~ 1.7 — 튜닝 엔진 코어 (2025-12-17)

#### 구현 내용

**1) BacktestRunResult 도입** (`extensions/tuning/types.py`)
```python
@dataclass
class BacktestRunResult:
    train: Optional[BacktestMetrics] = None
    val: Optional[BacktestMetrics] = None
    test: Optional[BacktestMetrics] = None
    debug: Optional[DebugInfo] = None
    guardrail_failures: List[str] = field(default_factory=list)
    logic_check_failures: List[str] = field(default_factory=list)
```

**2) 캐시 키 강화** (`extensions/tuning/cache.py`)
- params_hash + period_signature + lookback_months 조합
- 룩백별 캐시 격리

**3) MDD 일관성 Gate** (`extensions/tuning/guardrails.py`)
```python
def check_mdd_consistency(train_mdd, val_mdd, threshold_ratio=1.2):
    # Val MDD가 Train MDD의 1.2배 이상이면 실패
```

**4) RSI 실효성 Logic Check** (`extensions/tuning/guardrails.py`)
```python
def check_rsi_effectiveness(params, metrics):
    # RSI 파라미터가 실제로 신호에 영향을 주는지 확인
```

**5) Manifest 검증** (`extensions/tuning/manifest.py`)
- 필수 필드 검증
- by_lookback 구조 검증

**6) Replay 도구** (`tools/replay_manifest.py`)
- Manifest 재현성 검증
- Mock/Real 모드 지원
- tolerance 기반 비교

---

### ✅ Phase 1.0 ~ 1.4 — 기본 설계 (2025-12-15~16)

#### 구현 내용

**1) Test 봉인 원칙**
- Optuna objective = Val Sharpe만 사용
- Gate2 통과 전 Test 계산 금지

**2) Chronological Split**
- 시간 순서 분할 강제
- 최소 기간 규칙 (Val ≥ 6M, Test ≥ 6M)

**3) 단위 통일**
- 엔진 내부: 소수 (0.25 = 25%)
- UI 표시: 퍼센트

**4) 거래일 스냅**
- 시작일: 다음 영업일로 스냅
- 종료일: 이전 영업일로 스냅

---

### ✅ 튜닝 UI/UX 기본 개선 (2025-12-15~16)

| 항목 | 상태 |
|------|------|
| 튜닝 설정 패널 신설 (기간, 룩백, Trials) | ✅ 완료 |
| 튜닝 실행 확인 모달 (Confirm 전용) | ✅ 완료 |
| AI 분석 활성화 조건 강화 (4개 중 2개 이상) | ✅ 완료 |
| 모달 문구 개선 (단일 백테스트 vs 범위 탐색 명확화) | ✅ 완료 |
| AI 분석 프롬프트에 백테스트 기간 추가 | ✅ 완료 |

---

## 📌 다음 AI 인수인계 안내

### 필독 문서 (우선순위 순)

1. **[`docs/tuning/05_development_history.md`](tuning/05_development_history.md)** — AI 인수인계용 상세 개발 이력
2. **[`docs/tuning/00_overview.md`](tuning/00_overview.md)** — 설계 원칙, 배경, 용어 정의
3. **[`docs/AI_CONTEXT_PACK.md`](AI_CONTEXT_PACK.md)** — 전체 시스템 컨텍스트

### 핵심 코드 파악

1. `extensions/tuning/types.py` — 데이터 타입
2. `extensions/tuning/runner.py` — 백테스트 실행
3. `tools/run_phase15_realdata.py` — 메인 실행 스크립트

### 테스트 실행

```bash
# 기본 동작 확인
pytest tests/tuning/test_smoke.py -v

# Mock 모드 튜닝 실행
python -m tools.run_phase20_real_gate2 --runs 1 --trials 10 --seed 42 --top-n 3 --analysis-mode --force-gate2 --stop-at-gate2

# Replay 검증
python -m tools.replay_manifest "data\tuning_test\<manifest>.json" --mode mock --tolerance 1e-6
```

### 다음 작업 제안

| 우선순위 | 작업 | 설명 |
|----------|------|------|
| 1 | 실데이터 테스트 | Mock이 아닌 실제 parquet으로 전체 파이프라인 검증 |
| 2 | Gate3 구현 | Test 봉인 해제 및 최종 보고서 생성 |
| 3 | UI 연동 | 튜닝 결과를 React 대시보드에 표시 |
