# POC2 — ML Baseline v0 룩백 검증 CONCLUSION

작성: 2026-06-11
성격: Step 완료 보고. canonical 상태 (`docs/STATE_LATEST.md`) 의 detail 링크.

---

## 0. 한 줄 요약

현재 ML feature dataset (`etf_ml_feature_daily` / `market_risk_feature_daily`)
이 과거 구간에서 (1) 상승 후보 발굴 baseline 과 (2) 위험 구간 감지 baseline
으로 의미가 있었는지 룩백 검증. CLI 전용 실행 + read-only API + Data Status
표시. **점수 계산기가 아니라 baseline 의 룩백 의미 확인**. ML 모델 학습 /
위험 threshold / 조정장 label / 매수·매도 판단 / 외부 source 호출 0건.

사용자 결정 (a) top quintile / (a) market composite tercile / (a) max horizon
20d tail 제외. 실측: status=ok / 평가 40거래일 / candidate top group return
이 universe median 대비 5d/10d/20d 모두 양호 / risk high vs low future
drawdown 10d = -8.1% vs -3.4% / leakage detected=False.

---

## 1. AC 달성 현황

```text
AC-1  CLI / batch 실행 (화면 진입 자동 실행 X)                    = DONE
AC-2  Candidate target 생성 (future_return / future_excess_return) = DONE
AC-3  Risk target 생성 (future market return / drawdown / down ratio) = DONE
AC-4  Candidate baseline 검증 (top group return / hit rate / rank corr) = DONE
AC-5  Risk baseline 검증 (high vs low / drawdown capture)             = DONE
AC-6  Leakage check (구조적 미래 데이터 누수 0 / time order ASC)        = DONE
AC-7  Report 생성 (state/ml/ml_baseline_v0_report_latest.json)         = DONE
AC-8  Data Status 표시 (MLBaselineV0Card)                             = DONE
AC-9  Read-only 조회 (재계산 / 외부 호출 / 학습 X)                      = DONE
AC-10 기존 흐름 유지 (pytest 429 passed, 회귀 0)                       = DONE
AC-11 범위 위반 0건 (조정장 label / threshold / 신규 ML 라이브러리 0건) = DONE
AC-12 문서 갱신 (STATE / NEXT_ACTIONS / FEATURE_INVENTORY + 본 파일)    = DONE
```

---

## 2. 변경 파일 (구조)

**Backend 신규 (5)**:
- `app/ml_baseline_targets.py` **352 라인** — future return / drawdown /
  down_ratio target 생성 + `evaluate_leakage()`. `MAX_HORIZON=20`.
- `app/ml_baseline_candidate.py` **426 라인 (FIX r2 후)** — top quintile composite
  rank v0 (return_20d / excess_20d / return_10d / volume_ratio_20d DESC rank) +
  단순 baseline 2종 (`simple_return_20d` / `simple_excess_20d` top quintile).
- `app/ml_baseline_risk.py` **390 라인 (FIX r2 후)** — market composite risk score
  (13 axes) tercile 1/3 분할 비교 + 단순 baseline 3종 (5d return / 20d drawdown /
  market breadth).
- `app/ml_baseline_v0.py` **199 라인 (FIX r2 후)** — orchestrator (4 sub-step 통합)
  + `evaluated_asof_range.end` SQL 직접 계산.
- `app/api_ml_baseline.py` **66 라인** — `GET /ml/baseline-v0/latest`
  (snapshot JSON read-only).

**Backend 수정 (1)**:
- `app/api.py` — `ml_baseline_router` include.

**Scripts 신규 (1)**:
- `scripts/run_ml_baseline_v0.py` **92 라인** — CLI. `--db` / `--kodex-ticker` /
  `--no-snapshot`. exit code 0 (status=error 제외) / 1.

**Frontend 신규 (2)**:
- `frontend/lib/api/mlBaselineV0.ts` **95 라인 (FIX r2 후)** — 타입 6종 + fetch +
  `simple_baselines` 필드 추가.
- `frontend/app/components/MLBaselineV0Card.tsx` **357 라인 (FIX r2 후)** — Data
  Status 카드 (§12 허용 문구 전용, 단순 baseline 테이블 추가).

**Frontend 수정 (2)**:
- `frontend/lib/api/index.ts` — barrel re-export.
- `frontend/app/components/DataStatusView.tsx` — `<MLBaselineV0Card />` 추가.

**.gitignore 수정 (1)**:
- `state/ml/ml_baseline_v0_report_latest.json` 운영 artifact.

**Tests 신규 (1)**:
- `tests/test_ml_baseline_v0.py` **288 라인 (FIX r2 후)** — 15 테스트
  (targets tail / leakage / report status / evaluated_range.end /
  simple_baselines 키 / API empty/present/error/no-recompute).

**Docs 수정 (3)** + **신규 (1)**:
- `docs/STATE_LATEST.md` / `docs/handoff/POC2_B_NEXT_ACTIONS.md` /
  `docs/handoff/POC2_FEATURE_INVENTORY.md`.
- `docs/handoff/POC2_ML_BASELINE_V0_LOOKBACK_CONCLUSION.md` — 본 파일.

---

## 3. 핵심 설계 결정 (사용자 확정)

### 3.1 Candidate top group — (a) Top quintile 20%

universe ETF 1099 → composite rank v0 (return_20d + excess_return_20d +
return_10d + volume_ratio_20d DESC rank 평균) 의 하위 20% (= 가장 강한 그룹).
hit rate / rank correlation 가 안정적으로 측정 가능.

### 3.2 Risk group split — (a) Market composite tercile (상하 1/3)

13 axes (변동성/시장폭/distance_from_20d_high/조정장 전조 proxy 등) rank 평균을
시장 단일 시계열로 보고 상하 1/3 비교. 위험 threshold / label 확정 X.

### 3.3 FIX r2 (검증자 1차 REJECTED 후속)

검증자 NOTES 3건 반영:

1. **A-1 단순 baseline 누락** — 지시문 §7.4 (단순 return_20d / excess_20d 의
   top quintile) + §8.4 (단순 5일 시장 수익률 / 20일 drawdown / 시장폭) 단순
   baseline 비교가 report 에 없었음. → candidate `simple_baselines` 2종 +
   risk `simple_baselines` 3종 노출. 실측: candidate.simple_return_20d top
   future 20d = +15.3% vs universe median +4.7%. risk.drawdown_20d 단순
   기준 high vs low future drawdown 10d = -8.78% vs -3.42% (2.6x, composite
   v0 와 일관).
2. **A-2 UI 금지 문구** — `MLBaselineV0Card.tsx` helper 문구에 "매수/매도 /
   현금비중 / 위험 알림 / 조정장" 단어가 "0건" 표현이라도 §12 화면 금지 문구
   위반. → 허용 문구 ("후보 발굴 baseline 검증 결과 / 위험 패턴 baseline
   검증 결과 / high-risk group 의 이후 drawdown 비교") 만 사용. 코드 주석에
   §12 금지 문구 사용 정책 명시.
3. **A-3 evaluated_asof_range.end=null** — 지시문 §6 / §11.1 요구. →
   orchestrator 가 SQL 로 평가 마지막 asof 직접 계산. 실측: end=2026-05-07
   (feature_end 2026-06-08 - MAX_HORIZON 20거래일).

### 3.4 Horizon tail — (a) max horizon 20d 만큼 제외

평가 구간 = feature 전체 기간 - 20거래일. 모든 horizon 의 future target 이
측정 가능한 구간만 평가 → 누수 risk 0 보장.

---

## 4. 운영 동작

```
사용자: 터미널에서 CLI 실행
  $ python scripts/run_ml_baseline_v0.py
  ↓ build_baseline_report (db_path, kodex_ticker)
  ↓     ├─ build_candidate_targets — ticker 별 future_return / future_excess
  ↓     ├─ build_risk_targets — asof 별 future_kodex / drawdown / down_ratio
  ↓     ├─ evaluate_candidate_baseline — asof 별 composite top 20% vs universe
  ↓     ├─ evaluate_risk_baseline — asof 별 market composite tercile 비교
  ↓     └─ evaluate_leakage — 구조적 누수 / tail / time order 확인
  ↓ state/ml/ml_baseline_v0_report_latest.json 저장 (gitignored)
  [END] status=ok|warn|insufficient_history|error / stdout 요약

사용자: 좌측 메뉴 Data Status 진입
  ↓ MLFeatureSanityCard (기존, sanity)
  ↓ MLBaselineV0Card mount
  ↓     ├─ GET /ml/baseline-v0/latest (재계산 X)
  ↓     ├─ candidate / risk baseline 결과 표시
  ↓     └─ leakage / coverage / warnings expandable
```

---

## 5. 이번 STEP 에서 의도적으로 하지 않은 것 (지시문 §15 / §10)

- 실시간 매수 / 매도 판단 / 현금비중 조절 / Telegram 위험 알림.
- 조정장 확정 라벨 / 위험 threshold 확정.
- 외부 source 추가 / 공포지수 / VKOSPI / 원유 / 환율 / 미국 선물.
- 신규 ML 라이브러리 추가 (XGBoost / LightGBM / 딥러닝).
- Optuna 튜닝 / 복잡한 ensemble / RandomForest.
- 친구 프로젝트 구조 복제 / OCI push 연결.

---

## 6. 검증 결과

- **backend pytest** — PASS (FIX r2 후 **432 passed in 65s**, +15 신규 (총 15 테스트) / 회귀 0).
- **black --check / flake8 / frontend ESLint / Next.js build** — PASS.
- **CLI live 실측** (운영 SQLite, 1137 ETF × 60거래일):
  - status=**ok** / trading_days=60 / evaluated_days=40 / candidate ticker=1099.
  - leakage.future_data_detected=**False** / tail_excluded=True / time_order=True.
  - candidate.top_group_avg_future_return: 5d=**+3.43%** / 10d=**+5.54%** / 20d=**+13.51%**.
  - candidate.universe_median_future_return: 5d=+1.11% / 10d=+2.10% / 20d=+4.67%.
  - candidate.rank_correlation: 5d=+0.220 / 10d=+0.133 / 20d=+0.188 (모두 양수).
  - risk.high_risk_group_future_drawdown: 5d=**-5.83%** / 10d=**-8.09%**.
  - risk.low_risk_group_future_drawdown: 5d=-1.08% / 10d=-3.40%.
  - risk.drawdown_capture_rate: 5d=**1.72** / 10d=**1.44** (>1 = high group 이 universe 평균보다 큰 낙폭).
  - warnings=0 / errors=0.
- **외부 source 호출 0건** — `test_baseline_api_does_not_recompute` 가
  `build_baseline_report` 를 `_boom` monkeypatch 로 차단해 보장.

---

## 7. KS-10 자체 점검

신규 / 수정 파일의 라인수 실측 (`wc -l`):

| 파일 | 라인 | 임계 | 분류 |
| --- | --- | --- | --- |
| `app/ml_baseline_targets.py` | **352** | 600 / 650 | 안전 |
| `app/ml_baseline_candidate.py` | **426 (FIX r2 후)** | 600 / 650 | 안전 |
| `app/ml_baseline_risk.py` | **390 (FIX r2 후)** | 600 / 650 | 안전 |
| `app/ml_baseline_v0.py` | **199 (FIX r2 후)** | 600 / 650 | 안전 |
| `app/api_ml_baseline.py` | **66** | 600 / 650 | 안전 |
| `scripts/run_ml_baseline_v0.py` | **92** | n/a (scripts) | 안전 |
| `frontend/app/components/MLBaselineV0Card.tsx` | **357 (FIX r2 후)** | 850 / 900 | 안전 |
| `frontend/lib/api/mlBaselineV0.ts` | **95 (FIX r2 후)** | 850 / 900 | 안전 |
| `tests/test_ml_baseline_v0.py` | **288 (FIX r2 후)** | n/a (tests) | 안전 |

KS-10 trigger/near 0건. 첫 작성 시점 분할 설계로 600 라인 진입 회피.

---

## 8. 결과 해석 (참고용, 사용자 판단 영역)

- **Candidate**: top group future return 이 universe median 대비 5d 약 3x,
  20d 약 2.9x. rank correlation 양수. 즉 composite rank v0 가 단순 random
  대비 의미 있는 신호. 단, future_excess_return (vs KODEX200) 은 음수 —
  KODEX200 자체가 universe 강세 종목보다 안정적 → 상대 비교 한계.
- **Risk**: high-risk group 이후 drawdown 이 low-risk 대비 5x ~ 2.4x 큼.
  drawdown_capture_rate > 1 → composite risk score 가 시장 낙폭과 연동.
- **단, 평가 거래일 40일은 짧다**. 본 결과는 단일 시점 baseline 의 룩백 신호
  존재 확인일 뿐. 5년 backfill 후 rolling window 평가가 후속 분기.

---

## 9. 다음 분기 후보 (사용자 결정 영역)

1. **NAV 일별 적재 / 5년 backfill** — 평가 가능 거래일 40일 → 1000일 수준.
   본 baseline 결과의 시계열 안정성 검증.
2. **Baseline v0 시계열 rolling window 분해** — 본 STEP 의 평균을 30일/
   90일 window 로 분해해 시기별 신호 강도 노출.
3. **§6.6 제외 항목** (CNN Fear&Greed / VKOSPI / 외국인·기관 수급) — BACKLOG.
4. **ML 모델 학습 (baseline v0 통과 후)** — 본 STEP 이 baseline 의 룩백
   설명력만 확인. 모델 학습 / threshold 확정은 별도 STEP.

본 문서는 다음 STEP 을 임의 확정하지 않는다.
