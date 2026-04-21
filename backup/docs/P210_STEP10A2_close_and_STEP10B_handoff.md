# P210-STEP10A-2 min_train_samples Relaxation 종료 + P210-STEP10B Hand-off
> asof: 2026-04-13
> 상태: **완료** — ML 실제 개입 확인, CAGR 훼손폭 분석 완료
> 직전 문서: [P210_STEP10A_close_and_STEP10B_handoff.md](P210_STEP10A_close_and_STEP10B_handoff.md)

---

## 1. 결론: ML 이 실제로 개입했고, mts=100 이 최적 후보

### 1.1 핵심 발견

| mts | Predicted Dates | Soft Gate Hits | CAGR (B) | MDD (B) | ΔCAGR vs B0 |
|---:|---:|---:|---:|---:|---:|
| 50 | 20 | 9 | 10.82% | 11.03% | −5.86%p |
| 75 | 13 | 7 | 10.37% | 11.03% | −6.31%p |
| **100** | **7** | **5** | **15.93%** | **11.03%** | **−0.75%p** |
| - (no_ml) | 0 | 0 | 16.68% | 11.03% | 0 |

- **mts=50/75**: ML 이 과도하게 개입 → CAGR 5~6%p 훼손 (허용 불가)
- **mts=100**: ML 이 적절히 개입 (5회) → CAGR 0.75%p 훼손 (허용 가능)
- **MDD 는 전 구간 11.03% 동일** — soft_gate 가 MDD 를 줄이지는 못했지만 악화시키지도 않음

### 1.2 Q1~Q4 진단 요약

- **Q1**: mts=50 부터 predicted_dates > 0 발생 (20회)
- **Q2**: MDD 변화 없음 (11.03% 유지) — soft_gate 가 MDD 개선에 기여하지 못함
- **Q3**: mts=100 만 CAGR 훼손 허용 범위 (−0.75%p). mts=50/75 는 과도
- **Q4**: CAGR>15 AND MDD<10 동시 충족 없음. 차선 = mts=100 (CAGR 15.93%, MDD 11.03%)

### 1.3 Main Run 대표 성능 (변동 없음)

CAGR 12.4111% / MDD 12.7446% / Sharpe 1.1035 / **REJECT**

---

## 2. Step10A-2 에서 변경된 것

- `strategy_params_latest.json`: 실험군 6→8개 (`min_train_samples_override` 필드 추가)
- `param_loader.py`: mts_override 검증 (50/75/100 only), 8개 실험군 고정
- `predictive_risk_classifier.py`: `build_predictions_for_sweep` 에 override 파라미터
- `predictive_risk_compare.py`: cache_key 에 mts 반영, 비교표 + 정렬 + Q1~Q4 전면 교체
- `evidence_writer.py`: Track B 섹션에 Min Train Samples / Predicted Dates / Burnin Dates 추가

변경하지 않은 것: 라벨/피처/모델/baseline/threshold/regime/scanner/allocation

---

## 3. Step10B 진입 가이드

### 차선 후보

`B3_research_soft_gate_lr_mts100`: CAGR 15.93% / MDD 11.03%
— CAGR>15 통과, MDD<10 미달 (1.03%p 부족)

### 가용 옵션

**Option 1 — probability_threshold_soft 하향 (e.g. 0.45 → 0.40)**
- mts=100 에서 soft_gate 가 5회만 발동했으므로, threshold 낮추면 더 많은 개입 가능
- MDD 개선 가능성 있으나 CAGR 추가 훼손 리스크

**Option 2 — RF 보조군 추가 (B4/B5)**
- LR 의 linear boundary 한계를 RF 로 보강
- mts=100 에서 RF 성능 비교

**Option 3 — P210 종료 선언**
- Track A (규칙) + Track B (ML) 양쪽 다 MDD<10 달성 못함
- 승격 기준 재검토 또는 universe 확장으로 전환

**권장**: Option 1 (threshold 조정) 우선. SSOT 값만 변경으로 재실행 가능.
