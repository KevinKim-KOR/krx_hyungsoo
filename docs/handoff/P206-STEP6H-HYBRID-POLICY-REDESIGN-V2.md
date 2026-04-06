# P206-STEP6H: Hybrid Policy Redesign V2

> asof: 2026-04-06
> 상태: 설계 확정 (구현은 Step6I)

---

## 1. 현재 실패 상태

```
CAGR 12.29% | MDD 16.81% | Sharpe 0.7022 | Verdict: REJECT
Hybrid: risk_off | Global: neutral | Domestic: risk_off
neutral 8회 | risk_off 5회
```

**결론**: 방어는 자주 하는데 MDD는 충분히 못 줄이고, CAGR만 크게 깎음.

---

## 2. 실패 원인 분석 (4축)

### 2.1 Domestic threshold가 너무 공격적인가?

**예.** 069500 전일 수익률 -1% 이상이면 neutral, -3% 이상이면 risk_off.
한국장에서 -1~-2%는 일상적 변동. 이 범위에서 neutral 발동이 너무 잦아 cash drag 발생.

- neutral 8/36회 = **22%** — 약 5번 중 1번 반만 투자
- risk_off 5/36회 = **14%** — 약 7번 중 1번 전량 현금

### 2.2 neutral/risk_off 현금 비중 계단이 너무 거친가?

**예.** 현재는 0% → 50% → 100% 3단계뿐.
risk_on에서 바로 50% 현금(neutral)으로 뛰는 것은 과도.
중간 단계(예: 20~30% 현금)가 없어 소폭 불안에도 비중이 크게 줄어듦.

### 2.3 069500 단일 센서가 과민/대표성 부족인가?

**부분적.** 069500(KODEX 200)은 시장 전체 대표성은 양호하나,
ETF 포트폴리오가 섹터/테마 ETF 위주이므로 069500 급락 ≠ 포트폴리오 급락인 경우 존재.
다만 V1 단계에서 센서 다중화는 복잡도 대비 효과 불확실.

### 2.4 cash-only 방어가 cash drag를 키우는가?

**핵심 원인.** neutral(50% 현금) 또는 risk_off(100% 현금) 시 자금이 완전히 유휴.
방어 기간이 길어지면 기회비용이 누적되어 CAGR을 크게 깎음.
**안전자산 스위칭으로 방어 중에도 일부 수익 확보 가능.**

---

## 3. 정책 후보 4안

### 안 A: Threshold 완화형

| 항목 | 현행 | 변경 |
|---|---|---|
| domestic neutral 기준 | -1% | **-2%** |
| domestic risk_off 기준 | -3% | **-4%** |

**장점**: hard gate 빈도 감소, cash drag 완화
**단점**: 진짜 급락에 늦게 반응할 위험
**예상**: neutral 8→4회, risk_off 5→2회 수준

### 안 B: Domestic risk_off softening

| 항목 | 현행 | 변경 |
|---|---|---|
| domestic 단독 risk_off | hard gate (100% cash) | **neutral로 격하** (50% cash) |
| global risk_off | 유지 | 유지 |

**진리표 변경**:

| Global | Domestic | 현행 | 안 B |
|---|---|---|---|
| risk_on | risk_off | risk_off | **neutral** |
| neutral | risk_off | risk_off | **neutral** |
| risk_off | risk_off | risk_off | risk_off (유지) |

**장점**: 한국장 노이즈에 100% 현금화 안 함. 글로벌 패닉만 hard gate.
**단점**: 국내 독자 급락 방어력 약화
**핵심**: "한국장 -3% 만으로는 전량 현금화 불가, 미국도 나빠야 전량 현금"

### 안 C: Neutral 강화형

| 항목 | 현행 | 변경 |
|---|---|---|
| neutral cash pct | 50% | **65%** |
| risk_off 정책 | 100% cash | 유지 |

**장점**: risk_off 발동 줄이면서 중간 방어 강화
**단점**: 여전히 cash-only. cash drag 본질적 해결 안 됨.

### 안 D: Safe Asset Switching

위험 시 자금을 현금으로만 두지 않고, **안전자산 ETF로 스위칭.**

#### 적용 상태

| 상태 | 현행 | 안 D |
|---|---|---|
| neutral | 50% 현금 | 30% 현금 + **20% 안전자산 ETF** |
| risk_off | 100% 현금 | 50% 현금 + **50% 안전자산 ETF** |

#### 대상 안전자산 후보 (2개)

| 후보 | 종목 | 특성 |
|---|---|---|
| **달러 ETF** | 261240 (KOSEF 미국달러선물) 또는 동등 | 원화 약세 시 수익, 한국 급락 시 역상관 경향 |
| **미국채 ETF** | 305080 (TIGER 미국채10년선물) 또는 동등 | 글로벌 리스크오프 시 채권 강세 |

#### 장점

- cash drag 대폭 완화 — 방어 중에도 달러/채권 수익 가능
- 한국 급락 + 원화 약세 동시 발생 시 달러 ETF가 완충
- 글로벌 리스크오프 시 채권 ETF가 완충

#### 단점

- 안전자산도 완전 무위험은 아님 (달러 강세 반전, 금리 급등 시 채권 하락)
- 상관관계 붕괴 가능 (극단 시나리오)
- 정책 복잡도 증가 (현재 1종목 배분 → 2~3종목 배분)
- 안전자산 ETF의 유동성/스프레드 확인 필요

#### 구현 난이도

- 기존 `adjusted_weights` 로직에 안전자산 ticker 추가만 하면 됨
- 기존 `dynamic_equal_weight` 경로 재사용 가능
- 안전자산 ETF도 OHLCV fetch 필요 (기존 인프라로 가능)

---

## 4. 후보 비교

| 항목 | 안 A | 안 B | 안 C | 안 D |
|---|---|---|---|---|
| hard gate 감소 | 크게 | 크게 | 보통 | 보통 |
| cash drag 완화 | 보통 | 보통 | 약간 | **크게** |
| MDD 방어력 | 약화 위험 | 약화 위험 | 유지 | 유지+완충 |
| CAGR 복구 | 보통 | 보통 | 약간 | **크게** |
| 복잡도 | 낮음 | 낮음 | 낮음 | 중간 |
| 구현 난이도 | 1줄 | 진리표 수정 | 1줄 | ETF 추가 |

---

## 5. 추천안: B + D 조합

### 핵심

1. **국내 단독 risk_off를 neutral로 격하** (안 B)
   - hard gate는 글로벌 risk_off 포함 시에만 발동
   - 한국장 노이즈에 100% 현금화 안 함

2. **neutral 시 안전자산 스위칭** (안 D 일부)
   - neutral 발동 시: 50% 위험자산 + 30% 현금 + 20% 달러 ETF
   - risk_off 발동 시: 50% 현금 + 50% 달러 ETF

3. **Threshold는 유지** (안 A 미채택)
   - 센서 감도를 낮추면 진짜 급락도 놓칠 위험
   - 대신 방어 수단(cash vs safe asset)을 다양화

### 추천 이유

- cash drag가 현재 실패의 핵심 원인 → 안전자산으로 방어 중 수익 가능
- 국내 단독 hard gate 폐지로 over-defense 감소
- 글로벌 패닉 시에만 전량 방어 → hard gate 남용 억제
- 직장인형 모델에서 "방어 = 현금 = 0% 수익"의 고정관념 탈피

### 변경된 진리표

| Global | Domestic | Aggregate | 자산 배분 |
|---|---|---|---|
| risk_on | risk_on | risk_on | 100% 위험자산 |
| risk_on | neutral | neutral | 50% 위험 + 30% 현금 + 20% 달러 |
| risk_on | risk_off | **neutral** | 50% 위험 + 30% 현금 + 20% 달러 |
| neutral | risk_on | neutral | 50% 위험 + 30% 현금 + 20% 달러 |
| neutral | neutral | neutral | 50% 위험 + 30% 현금 + 20% 달러 |
| neutral | risk_off | **neutral** | 50% 위험 + 30% 현금 + 20% 달러 |
| risk_off | risk_on | risk_off | 50% 현금 + 50% 달러 |
| risk_off | neutral | risk_off | 50% 현금 + 50% 달러 |
| risk_off | risk_off | risk_off | 50% 현금 + 50% 달러 |

**핵심 변경**: domestic 단독 risk_off → neutral 격하 (행 3, 6)

---

## 6. Safe Asset 상세

### V1 대상: 달러 ETF 1종

| 항목 | 값 |
|---|---|
| 종목 | 261240 (KOSEF 미국달러선물) 또는 동등 |
| 이유 | 한국 급락 시 원화 약세 → 달러 강세 → 역상관 완충 |
| 데이터 | 기존 OHLCV 인프라로 fetch 가능 |
| 리스크 | 원화 강세 구간에서 마이너스 |

미국채 ETF는 V2에서 추가 검토.

### 배분 비율

| 상태 | 위험자산 | 현금 | 달러 ETF |
|---|---|---|---|
| risk_on | 100% | 0% | 0% |
| neutral | 50% | 30% | 20% |
| risk_off | 0% | 50% | 50% |

---

## 7. 장중 대응 한계

- 하루 4~6회 체크포인트 대응
- 상시 실시간 대응 아님
- 장중 완벽 포착 목표 아님
- 목표: 직장인 조건에서 MDD를 덜 맞는 것
- 안전자산 스위칭도 체크포인트 시점에만 판단

---

## 8. 비교 지표

Step6I 구현 후 아래로 비교:

| 지표 | 설명 |
|---|---|
| CAGR | 수익률 |
| MDD | 최대 낙폭 |
| Sharpe | 위험조정 수익 |
| Total Trades | 거래 횟수 |
| Neutral Count | neutral 발동 횟수 |
| Risk-off Count | risk_off 발동 횟수 |
| Verdict | CAGR>15 + MDD<10 |
| Cash Drag Proxy | neutral/risk_off 기간 동안 유휴 현금 비율 |
| Safe Asset Switch Count | 안전자산 스위칭이 발동된 리밸런스 횟수 |
| Safe Asset 적용률 | 전체 리밸런스 중 안전자산 배분 비율 |
| Safe Asset Return | 안전자산 구간 수익률 |

---

## 9. 산출물 계약 (Step6I 이후)

1. `reports/tuning/hybrid_policy_compare.csv` — A/B/C/D 비교표
2. `reports/tuning/hybrid_policy_summary.md` — 추천안 + 분석
3. `reports/tuning/dynamic_evidence_latest.md` — 아래 확장

확장 필드:
- `Policy Variant: B+D (domestic softening + safe asset)`
- `Domestic Handling: neutral_only (no domestic hard gate)`
- `Safe Asset Mode: dollar_etf_20pct_neutral / 50pct_risk_off`
- `Checkpoint Summary: K1~K6`
- `One-line Conclusion: 정책 효과 요약 (예: "B+D 적용, CAGR 회복 중, MDD 미달")`

---

## 10. 구현 경계 (Step6I)

### 수정 대상 파일

| 파일 | 변경 |
|---|---|
| `exo_regime_filter.py` | 진리표 수정 (domestic risk_off → neutral 격하) |
| `backtest_runner.py` | neutral 시 안전자산 배분 로직 |
| `run_backtest.py` | 달러 ETF fetch + hybrid 산출물 갱신 |
| `run_tune.py` | 동일 |

### 안전자산 ETF 처리

- 투자 universe에 달러 ETF를 **조건부 추가** (neutral/risk_off 시에만 배분)
- 기존 `dynamic_equal_weight` 가중치 계산에 안전자산 비중 삽입
- target_weights에 달러 ETF 비중 추가 → 기존 rebalance 로직으로 실행

---

## 11. 비교군 (Step6I 이후)

| # | 구성 | 기대 |
|---|---|---|
| 1 | no regime | 높은 CAGR, 높은 MDD |
| 2 | VIX baseline | 글로벌만 |
| 3 | Hybrid 현행 (현금만) | CAGR 12%, MDD 17% |
| 4 | **Hybrid B+D (안전자산)** | CAGR 회복 + MDD 유지/개선 |
