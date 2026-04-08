# P206-STEP6J-FIX: Regime Schedule 리밸런스 날짜 보정

> asof: 2026-04-09
> 상태: 수정 완료, 검증 완료

---

## 1. 버그 현상

Step6J 민감도 스캔(216조합) 결과, 모든 조합에서 CAGR/MDD/Sharpe가 동일.
domestic threshold를 변경해도 regime state가 바뀌지 않는 것처럼 보임.

---

## 2. 근본 원인

### regime schedule 날짜 ≠ runner 리밸런스 날짜

| 구분 | 날짜 소스 | 예시 |
|---|---|---|
| regime schedule | 캘린더 월초 1일 | `2024-01-01`, `2024-03-01` |
| runner 실제 리밸런스 | OHLCV 데이터의 첫 거래일 | `2024-01-02`, `2024-03-04` |

runner는 `_exo_sched.get(str(d), "risk_on")`으로 조회. 키 불일치 시 기본값 `"risk_on"` 반환.

### 영향 범위

| 항목 | 값 |
|---|---|
| schedule 날짜 수 | 36 |
| runner 리밸런스 날짜 수 | 37 |
| 일치 | **17** (47%) |
| 불일치 (무시됨) | **19** (53%) |

53%의 regime state가 무시되어 사실상 대부분 risk_on으로 동작.
이로 인해 CAGR이 실제보다 높게(inflated) 보고됨.

---

## 3. 수정 내용

### 3.1 _rebal_dates 거래일 snap

`run_backtest.py`와 `run_tune.py` 모두에 동일 로직 적용:

```python
# 캘린더 날짜 → 실제 거래일로 snap
_trading_dates = sorted(set(
    d.date() for d in price_data.index.get_level_values("date").unique()
))
_snapped = []
for rd in _rebal_dates:
    _found = None
    for td in _trading_dates:
        if td >= rd:
            _found = td
            break
    _snapped.append(_found if _found is not None else rd)
_rebal_dates = _snapped
```

각 캘린더 날짜를 해당일 이후 가장 가까운 실제 거래일로 snap.

### 3.2 적용 위치

| 파일 | 위치 |
|---|---|
| `app/run_backtest.py` | `_rebal_dates` 생성 직후 (L196~L215) |
| `app/run_tune.py` | `_tune_rebal_dates` 생성 직후 (L299~L316) |

---

## 4. 수정 전후 비교

### 날짜 일치율

| 항목 | Before | After |
|---|---|---|
| 일치 | 17/36 (47%) | **36/36 (100%)** |
| 무시됨 | 19/36 (53%) | 0 |

### 성능 지표 (기본 정책 nrp=0.35)

| 지표 | Before | After |
|---|---|---|
| Neutral Count | 11 | **14** |
| Risk-off Count | 2 | **4** |
| CAGR | 17.65% | **12.58%** |
| MDD | 12.27% | **12.26%** |
| Sharpe | 1.20 | **1.15** |
| Verdict | REJECT | REJECT |

CAGR 하락은 정상: 이전에 무시되던 neutral/risk_off가 정상 적용되어 위험자산 비중이 줄어든 결과.

### 민감도 스캔

| 항목 | Before (216조합) | After (405조합) |
|---|---|---|
| 결과 패턴 | 1개 (전부 동일) | **135개** |
| domestic threshold 효과 | 없음 | N=9~16으로 변동 |
| CAGR 범위 | 18.13% 고정 | 5.09% ~ 19.18% |

---

## 5. 검증

| 검증 항목 | 결과 |
|---|---|
| 날짜 일치율 36/36 | PASS |
| nrp 변경 시 CAGR 변동 | PASS (0.35→17.65, 0.70→18.74) |
| dnt 변경 시 neutral count 변동 | PASS (-0.005→16, -0.03→9) |
| black --check | PASS |
| flake8 | PASS |
| py_compile | PASS |

---

## 6. 커밋 이력

| 커밋 | 내용 |
|---|---|
| `5af9d799` | run_backtest.py 날짜 보정 + 스캔 스크립트 |
| `310381c5` | run_tune.py 동일 보정 적용 |
