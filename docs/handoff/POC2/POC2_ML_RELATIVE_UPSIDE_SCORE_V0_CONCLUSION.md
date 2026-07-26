# POC2 — ML 축1: 후보 ETF 상대상승 참고점수 v0 Conclusion

작성일: 2026-06-20
STEP: ML_RELATIVE_UPSIDE_SCORE_V0
상태: DONE

---

## 1. 목표 요약

지시문 §3 단일 목표:

기존 ETF 가격 이력과 5/10/20일 수익률·초과수익 evidence 를 사용해 후보 ETF 별
**상대상승 참고점수 v0** 를 생성하고, 기존 후보 목록에서 점수·고점 대비·근거를
함께 비교할 수 있게 한다.

이 점수는 매수·매도·교체·비중조절 신호가 아니다 — 사용자가 AI 투자세션에서
참고할 수 있는 **추가 정량 재료**.

---

## 2. 구현 결과

### 신규 backend 모듈

| 파일 | 역할 |
|---|---|
| `app/ml_relative_upside_features.py` | feature 계산 — 5/10/20일 수익률 + KODEX200 초과수익 + drawdown_20d. `CandidateFeatureRow` dataclass. `is_complete_for_training` / `is_complete_for_inference` helper. 미래 데이터 차단 가드. |
| `app/ml_relative_upside_model.py` | torch 단일 선형회귀 (`RelativeUpsideRegressor` = `nn.Linear(7,1)`). walk-forward 1회 split. CUDA 우선 device 선택. `normalize_to_display_scores` — 후보군 내 상대 순위 기반 0~100. |
| `app/ml_relative_upside_score.py` | 사람 언어 reasons 빌더 (최대 3개) / snapshot + run meta 빌더 / atomic write / load helper. USER_NOTICE 상수. |

### 신규 CLI

| 파일 | 역할 |
|---|---|
| `scripts/run_ml_relative_upside_score_v0.py` | end-to-end runner — SQLite read → feature 계산 → torch GPU 학습 → 추론 → 0~100 정규화 → simple vs ML 비교 기록 → snapshot 저장. |

### 신규 테스트 (24건)

| 파일 | 건수 | 범위 |
|---|---|---|
| `tests/test_ml_relative_upside_features.py` | 7 | drawdown 정의 / future leakage 차단 / KODEX 시계열 / 최소 lookback |
| `tests/test_ml_relative_upside_model.py` | 7 | 점수 범위 0~100 / 동률 / 시간 순서 split / 셔플 없음 |
| `tests/test_ml_relative_upside_score.py` | 10 | reasons user-language / snapshot 구조 / API unavailable 분기 / failed 분기 |

### 수정 backend

| 파일 | 변경 |
|---|---|
| `app/api_market_topn.py` | `MarketCandidate` 모델에 `relative_upside_score` / `drawdown_20d` / `relative_upside_reasons` 필드 추가. `MarketTopNResponse` 에 top-level `relative_upside_score_status` / `_asof_date` / `_generated_at` / `_user_notice` 추가. `_merge_relative_upside_score` 머지 함수 + endpoint 합성 단계 통합. snapshot 부재 시 후보 응답 유지 (지시문 §10 끝). |
| `requirements.txt` | torch>=2.6.0 추가 (사용자 결정 — 지시문 §6.1 의 "신규 ML 라이브러리 추가 금지" 예외 1회 허용. CUDA 12.4 wheel 설치). |

### 수정 frontend

| 파일 | 변경 |
|---|---|
| `frontend/lib/api/market.ts` | `MarketCandidate` 에 ML score 3 필드 / `MarketTopNResponse` 에 top-level 메타 4 필드 추가. `RelativeUpsideScoreStatus` 타입. |
| `frontend/app/components/CandidateTable.tsx` | 컬럼 3개 추가 (상대상승 참고점수 / 고점 대비 / 점수 근거). 점수 정렬 로컬 토글 (off → desc → asc → off). 사용자 고지 (USER_NOTICE) 표시. |
| `frontend/app/components/MarketDiscoveryView.tsx` | `CandidateTable` 호출에 새 props 전달. |

### .gitignore

`state/ml/relative_upside_score_latest.json` + `state/ml/relative_upside_score_run_latest.json` 추가 (runtime artifact, commit 대상 아님).

---

## 3. AC 달성 현황

| AC | 내용 | 결과 |
|---|---|---|
| AC-1 | 첫 추가 factor (drawdown_20d) 계산 | DONE — `app/ml_relative_upside_features.py` |
| AC-2 | 시간 순서 기반 ML 실행 | DONE — `train_walk_forward()` walk-forward 1회 split |
| AC-3 | 미래 데이터 차단 | DONE — `include_future_target=False` 추론 모드 + 마지막 horizon row target=None |
| AC-4 | 상대상승 참고점수 생성 | DONE — 1,111 후보, 0~100 점수 부여, asof=2026-06-19 |
| AC-5 | 기존 단순 기준 비교 | DONE — `simple_vs_ml_rank_comparison` 블록 snapshot 에 저장 |
| AC-6 | 4070 GPU 실행 증거 | DONE — `device_name=NVIDIA GeForce RTX 4070 SUPER`, `cuda_available=True`, `gpu_execution_used=True`, train 0.256초 |
| AC-7 | 후보 목록 표시 (점수/고점대비/근거) | DONE — `CandidateTable.tsx` 컬럼 3개 추가 |
| AC-8 | 점수 정렬 | DONE — 헤더 클릭 로컬 정렬 (off → desc → asc → off). 신규 API 정렬 파라미터 0건 |
| AC-9 | 점수 미생성 처리 | DONE — snapshot 부재 → status=unavailable + candidate score=null + "점수 미생성" 라벨. 후보 응답 자체는 유지 |
| AC-10 | 사용자 표현 (raw 식별자 금지) | DONE — reasons 에 loss / epoch / device / feature key 노출 0건 (테스트로 검증) |
| AC-11 | 기존 산식 불변 | DONE — `compute_topn` / `_enrich_candidates_with_evidence` / `ml_baseline_v0` 산식 변경 0건. ML score 는 응답 합성 단계의 추가 머지 |
| AC-12 | OCI 영향 없음 | DONE — `scripts/run_three_push_runtime_oci.py` / `app/three_push_runtime_message_builder.py` / PARAM 구조 / Telegram 메시지 변경 0건 |
| AC-13 | 범위 통제 | DONE — 위험 감지 / 버킷 / threshold / 신규 데이터 source / DB 이전 / 모바일 메뉴 0건 |
| AC-14 | 문서 갱신 | DONE — STATE_LATEST / POC2_B_NEXT_ACTIONS / POC2_FEATURE_INVENTORY / ASSUMPTIONS / 본 CONCLUSION |

---

## 4. 제외 범위 준수 확인

| 항목 | 결과 |
|---|---|
| 매수/매도/교체/비중 조절 판단 | 0건 |
| 위험 구간 분류 | 0건 |
| 위험 점수 | 0건 |
| 점수 threshold 확정 | 0건 |
| 점수 등급·버킷 확정 | 0건 |
| RSI 추가 | 0건 |
| 신규 외부 데이터 source | 0건 |
| 뉴스 데이터 | 0건 |
| OCI runtime score 반영 | 0건 |
| Telegram PUSH 에 ML 점수 포함 | 0건 |
| OCI DB 이전 | 0건 |
| 모바일/외부 조회 메뉴 | 0건 |
| 고밀도 메인 판단 화면 | 0건 |
| RF/XGB/LGBM 비교 | 0건 |
| 자동 튜닝 | 0건 |

---

## 5. 모델 / 학습 세부

지시문 §6 — 단일 모델 baseline.

| 항목 | 값 |
|---|---|
| 모델 | `nn.Linear(in_features=7, out_features=1, bias=True)` |
| feature 컬럼 (7개) | return_5d / return_10d / return_20d / excess_return_5d / excess_return_10d / excess_return_20d / drawdown_20d |
| target | 이후 20거래일 KODEX200 대비 상대수익 (`future_excess_return_20d`) |
| 분할 방식 | walk-forward 1회 (사용자 결정 2026-06-20) — 시간 순서 정렬 후 앞 80% / 뒤 20% |
| 랜덤 셔플 | 없음 (지시문 §6.3) |
| optimizer | Adam (lr=1e-3) |
| loss | MSE |
| epochs | 200 (고정 — 자동 튜닝 0건) |
| seed | 42 |

### 학습 실측 (2026-06-20)

| 메트릭 | 값 |
|---|---|
| universe ticker 수 | 1,140 |
| training row pool | 66,941 |
| train_row_count | 35,991 |
| test_row_count | 8,998 |
| train_date_range | 2026-03-20 ~ 2026-05-08 |
| test_date_range | 2026-05-08 ~ 2026-05-20 |
| train_loss_final | 0.0690 |
| test_loss_final | 0.0304 |
| device_name | NVIDIA GeForce RTX 4070 SUPER |
| cuda_available | true |
| gpu_execution_used | true |
| train_seconds | 0.256 |

### 추론 실측

| 메트릭 | 값 |
|---|---|
| asof_date | 2026-06-19 |
| candidate_count | 1,111 |
| scored_candidate_count | 1,111 |
| score_min | 0.00 |
| score_max | 100.00 |

---

## 6. 데이터 계약 (지시문 §10)

신규 endpoint 없음. 기존 `GET /market/topn/latest` 응답을 확장.

### Top-level 추가 필드

```json
{
  "relative_upside_score_status": "ok" | "unavailable" | "failed",
  "relative_upside_score_asof_date": "YYYY-MM-DD" | null,
  "relative_upside_score_generated_at": "ISO-8601" | null,
  "relative_upside_score_user_notice": "상대상승 참고점수는 과거 데이터 기반의 후보 비교용 참고값이며, 매수·매도 판단을 자동으로 제시하지 않습니다."
}
```

### Candidate 추가 필드

```json
{
  "relative_upside_score": 0~100 (number) | null,
  "drawdown_20d": close/peak-1 (음수) | null,
  "relative_upside_reasons": ["..."] | []
}
```

기존 필드 (returns, excess_return, data_quality 등) 변경 없음. snapshot 부재 시
top-level status=unavailable + candidate score=null + reasons=[] 로 처리.
**기존 후보 응답 전체를 실패시키지 않는다** (지시문 §10 끝).

---

## 7. 사용자 화면 (지시문 §9)

기존 Market Discovery 화면의 `CandidateTable` 에 컬럼 3개 추가:

| 컬럼 | 내용 |
|---|---|
| 상대상승 참고점수 | 0~100 또는 "점수 미생성". 헤더 클릭으로 로컬 정렬 (off → 내림차 → 오름차 → off) |
| 고점 대비 | drawdown_20d 를 % 표기 (음수 — 빨강) |
| 점수 근거 | reasons 1~3개 bullet list |

**사용자 고지 문구** (USER_NOTICE — backend → frontend 통과):

> 상대상승 참고점수는 과거 데이터 기반의 후보 비교용 참고값이며, 매수·매도
> 판단을 자동으로 제시하지 않습니다.

---

## 8. 산출물

지시문 §11 — 운영 artifact (gitignored):

| 경로 | 내용 |
|---|---|
| `state/ml/relative_upside_score_latest.json` | 점수 + 근거 snapshot. UI 가 API 응답 합성 시 머지 |
| `state/ml/relative_upside_score_run_latest.json` | 실행 메타 — train/test row 수, 날짜 범위, loss, device, train_seconds 등 |

**OCI 전달 / Telegram 포함 / PARAM 포함 0건** (지시문 §11 끝).

---

## 9. 검증 결과

| 항목 | 결과 |
|---|---|
| backend pytest | **608 passed** (584 + 24 신규, 회귀 0건). 기존 환경 실패 1건 (`test_generate_spike_alert_via_unified_endpoint`)은 본 STEP 이전부터 존재 |
| black | PASS (본 STEP 변경 파일 전부) |
| flake8 | PASS (본 STEP 변경 파일 전부) |
| frontend npm run lint | PASS |
| frontend npm run build | PASS |
| 실측 GPU 학습 | CUDA RTX 4070 SUPER, 0.256초 |
| 실측 추론 | 1,111 후보 모두 0~100 점수 부여 |
| 미래 데이터 누수 차단 | 단위 테스트로 검증 (마지막 20일 row target=None) |
| 점수 미생성 처리 | 단위 테스트 + API 통합 테스트로 검증 |
| 기존 ml_baseline_v0 경로 보존 | `state/ml/ml_baseline_v0_report_latest.json` 변경 0건 (별도 경로) |
| OCI runner / PARAM / Telegram 회귀 | 코드 변경 0건 |

---

## 10. 다음 단계 (사용자 결정 대기)

지시문 §14 (제외) 와 PC_OCI_ARCHITECTURE_DIRECTION 의 순서에 따라:

1. **위험 감지용 시계열 빈자리 하나 채우기** (ML 축2 의 첫 빈자리).
2. **점수·위험·보유 비교가 모이는 PC 판단 화면** 의 좁은 STEP.
3. **OCI read model foundation** — PC 판단 화면 + ML 1차 결과 확보 뒤.

본 STEP 의 ML 점수는 PC 분석 평면에만 머문다. OCI runtime 반영은 향후 PC read
model snapshot handoff 가 결정된 뒤 별도 STEP.
