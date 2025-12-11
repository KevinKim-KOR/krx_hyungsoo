# KRX Alertor — Future Development Roadmap

> **작성**: 2025-12-11  
> **Author**: 형수  
> **목적**: 향후 개발 항목 영구 기록

---

## 개요

이 문서는 현재 개발이 완료된 KRX Alertor 시스템의 **향후 고도화 로드맵**을 정리합니다.

### Phase 분류별 개발 필요성 요약

| Phase | 항목 | 개발 필요 여부 | 이유 |
|-------|------|----------------|------|
| 1 | 장기 백테스트 | ❌ 개발 아님 | Runner로 직접 돌리면 됨 |
| 2 | Walk-Forward | ✅ 개발 필요 | 오케스트레이션/윈도우 시스템 자체가 없음 |
| 3 | TP/SL 고도화 | ✅ 개발 필요 | 현재 단일 stop_loss 기반이라 구조 확장 필요 |
| 4 | Breadth / 이벤트 | ✅ 개발 필요 | 신규 데이터 + 신규 레짐 로직 |

---

## 1. Phase 2 — Walk-Forward Framework

### 1.1 목표

- 단일 백테스트 샘플이 아닌, **여러 시점의 롤링 윈도우**에서의 성능 안정성 검증
- **파라미터 민감도와 안정성 평가** (PSS Score)
- 실전 적용 가능성 판단 기준 강화

### 1.2 개발 필요 요소

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

## 2. Phase 3 — TP / SL 고도화 (Take Profit / Trailing Stop)

### 2.1 목표

현재 단일 `stop_loss%` & 하이브리드 손절 매트릭스를 넘어선  
**프로페셔널한 변동성 기반 리스크 관리 시스템** 구축

### 2.2 개발 요소

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

## 3. Phase 4 — Market Breadth & 이벤트 캘린더

### 3.1 목표

- 시장의 **체력(광범위한 상승/하락 참여도)**을 반영해 레짐 정확도 강화
- **이벤트 기반 회피/방어 필터** 추가

### 3.2 Breadth 개발 항목

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

### 3.3 이벤트 캘린더

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

| 현재 모듈 | Phase 2 연결 | Phase 3 연결 | Phase 4 연결 |
|-----------|--------------|--------------|--------------|
| `core/engine/backtest.py` | 윈도우별 실행 | TP/SL 로직 확장 | - |
| `core/strategy/` | - | 익절/손절 전략 | Breadth 필터 |
| `extensions/monitoring/regime.py` | - | - | Breadth Score 연동 |
| `scripts/nas/` | - | - | 이벤트 캘린더 알림 |
| `api_backtest.py` | Walk-Forward API | - | - |

---

## 우선순위 제안

1. **Phase 2 (Walk-Forward)** - 현재 튜닝 결과의 신뢰도 검증에 필수
2. **Phase 3 (TP/SL)** - 실전 운용 시 리스크 관리 강화
3. **Phase 4 (Breadth/이벤트)** - 고급 기능, 리서치 병행 필요
