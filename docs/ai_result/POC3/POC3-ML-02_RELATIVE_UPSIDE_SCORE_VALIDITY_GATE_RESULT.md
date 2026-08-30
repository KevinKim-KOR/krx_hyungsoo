# POC3-ML-02 — Relative Upside Score Validity Gate · 개발 결과서

- **작성**: 개발자 (VSCode Claude)
- **수신**: 검증자 (Codex)
- **작성일**: 2026-08-29
- **대응 설계서**: `docs/ai_design/POC3/POC3-ML-02_RELATIVE_UPSIDE_SCORE_VALIDITY_GATE_DESIGN_V1.md`
- **대응 PLAN**: `docs/ai_plan/POC3/POC3-ML-02_RELATIVE_UPSIDE_SCORE_VALIDITY_GATE_PLAN_V1.md`
  (설계자 판정 **`PLAN PASS — IMPLEMENTATION AUTHORIZED`** · 확정사항 5건 반영 완료)
- **상태**: **`PASS` — 설계자 최종 판정 완료 (2026-08-29)**
- **개정 이력**
  | 라운드 | 결과 |
  |---|---|
  | r1 (2026-08-29) | 최초 구현·평가 → 검증자 **`REJECTED`** (계약 누락 7건) |
  | r2 (2026-08-29) | 설계자 보완 지시 8개 항목 반영 + 전체 재평가 → 검증자 **`REJECTED`** (P1 2건) |
  | r3 (2026-08-29) | **실제 실행 차단 CLI 통합 테스트 신설** + 결과서 정합성 정정 → 검증자 **`REJECTED`** (A-2 수치 잔존 1건) |
  | r3.1 (2026-08-29) | 전체 pytest 수치 정정(+ 동류 1건 전수 정정) → **검증자 `VERIFIED`** |
  | 종료 (2026-08-29) | 설계자 **최종 판정**: Step `PASS` · 모델 **`REJECT` 확정** · 화면 **비활성+비노출** · C-4 BACKLOG 등재. **본 문서** |

> ### 최종 상태 (설계자 판정 · 2026-08-29)
> ```text
> step_status       = PASS
> verification      = VERIFIED
> model_verdict     = REJECT
> model_scope       = relative_upside_v0
> ui_action         = DEACTIVATE_AND_HIDE
> oci_push_impact   = NONE
> next_gate         = REJECTED_SCORE_DEACTIVATION
> ```
>
> `verification` 이력: r1 `REJECTED` → r2 `REJECTED` → r3 `REJECTED` → **r3.1 `VERIFIED`**.
> **기술 검증 3회 반려 이력은 지우지 않는다** — 최종 수치가 계약을 통과했다는 근거다.
>
> 본 Step 에서 화면·API·발송은 **하나도 바꾸지 않았다**. 화면 비활성은
> 후속 Step(`POC3-ML-02 REJECT Closeout`)에서 수행한다.

---

## 0. 최종 판정

> ## `REJECT` — **모델 판정 확정** (설계자, 2026-08-29)
>
> 대상은 **`relative_upside_v0` 점수 하나**다.

발동 조건은 **R-3** 단 하나이며, 그것으로 충분하다.

> **R-3 — 상위 10% 순(net, 편도 25bp) 평균 forward excess ≤ 0**
> **r2 실측: −1.214 %/월 · bootstrap 95% CI [−2.495%, −0.213%]** (상한도 0 미만)
>
> (r1 값 `−1.217% · [−2.499%, −0.216%]` 는 warmup 2건이 비용 시계열에 섞여 있던
> 수치다. 현재 판정값이 아니다.)

### 표현의 한계 (설계자 확정 문구 — 넓게 주장하지 않는다)

> **현재 점수가 반대로 예측한다고 통계적으로 확정한 것은 아니다.**
> **점수가 높은 ETF군이 거래비용을 반영한 KODEX200 대비 성과 기준을 통과하지
> 못했으므로 판단 보조지표로 사용할 근거가 없다.**

R-1(음의 예측력)은 발동하지 않았다 — IC 의 CI 상한이 `+0.0011` 로 0 을 포함한다.

### 이 판정이 의미하지 않는 것 (설계자 확정)

- ML 전체가 무효라는 뜻이 **아니다**
- 모멘텀 전략이 무효라는 뜻이 **아니다**
- 단순 20일 모멘텀까지 폐기한다는 뜻이 **아니다**
- 평가 코드와 결과 artifact 를 삭제한다는 뜻이 **아니다**

**현재 `relative_upside_v0` 점수만 `REJECT` 다.**
`E1_UNAVAILABLE` 은 최종 판정을 막지 않는다 — 주 평가 계약은 E2 였고 E2 의 R-3 가
사전 기준대로 발동했다.

### 판정 상한과의 관계

PLAN §2.6 의 판정 상한(`RESEARCH_ONLY`)은 **`ADOPT` 를 막는 장치**이지 `REJECT` 를
막는 장치가 아니다. 설계자 확정문 그대로:

> survivor-only 데이터에서도 실패 → `REJECT`

낙관 방향으로 왜곡됐을 가능성이 있는 데이터에서조차 상위군이 비용 차감 후 손실이므로,
**현재 화면의 참고점수를 판단 근거로 쓸 이유가 없다**는 결론이다.

---

## 1. 처리한 요구사항

| 설계서 요구 | 상태 | 근거 |
|---|---|---|
| §4.1 검증 대상 동결 (모델·score 버전·feature·기준일·식별) | **DONE** | §3.1 재현 기술자 6종 |
| §4.2 시점 정합성·누수 방지 | **DONE** | L-1~L-3 위반 **0건** (§4.3) |
| §4.2 생존편향 한계 명시 | **DONE** | §6.1 |
| §4.3 평가 기간 (1M 주 / 3M 보조 · 연도별 표본) | **DONE** | §4.1 |
| §4.4 필수 평가 지표 11종 | **DONE** | §4 전체 |
| §4.5 운영 가정 | **DONE** | §3.3 |
| §4.6 사전 판정 기준 (수치 · 구현 전 고정) | **DONE** | PLAN §5 에 구현 전 고정 · §5 대조 |
| §4.7 산출물 (JSON · 요약 · 표 · 진단 · 판정 · 시간·노드) | **DONE** | §7 |
| 확정사항 1 panel 선생성 금지 | **DONE** | §3.2 · T-3 |
| 확정사항 2 `target_end <= t` | **DONE** | §4.3 L-3 · T-4 |
| 확정사항 3 bootstrap 계약 고정 | **DONE** | §4.4 |
| 확정사항 4 N-1 수치 기준 | **DONE** | §4.3 |
| 확정사항 5 R-1 정정 | **DONE** | §5.2 |

---

## 2. 변경된 파일 목록

| 파일 | 구분 | 줄수 |
|---|---|---|
| `app/ml_score_validity_metrics.py` | **신규** | 332 |
| `app/ml_score_validity_eval.py` | **신규** | 581 |
| `app/ml_score_validity_report.py` | **신규 (PLAN 예상 외 — §9-4 참조)** | 626 |
| `app/ml_score_validity_screen.py` | **신규 (PLAN 예상 외 — §9-4 참조)** | 181 |
| `scripts/run_ml_score_validity_eval_v1.py` | **신규** | 554 |
| `tests/test_ml_score_validity_metrics.py` | **신규** | 206 |
| `tests/test_ml_score_validity_eval.py` | **신규** | 492 |
| `tests/test_ml_score_validity_contracts.py` | **신규 (r2)** | 529 |
| `tests/test_ml_score_validity_cli.py` | **신규 (r3)** | 245 |
| `state/ml/validity/relative_upside_validity_v1_latest.json` | **신규 산출물** | |
| `state/ml/validity/relative_upside_validity_v1_run_latest.json` | **신규 산출물** | |
| `docs/ai_design/POC3/POC3-ML-02_..._DESIGN_V1.md` | **신규** | |
| `docs/ai_plan/POC3/POC3-ML-02_..._PLAN_V1.md` | **신규 + 개정** | |
| `docs/ai_result/POC3/POC3-ML-02_..._RESULT.md` | **신규 (본 문서)** | |
| `.gitignore` | 수정 | +4 |
| `docs/STATE_LATEST.md` | 수정 | |

**운영 코드 변경 0건.** 아래는 **import 만** 했고 한 줄도 고치지 않았다:
`ml_relative_upside_features.py` · `ml_relative_upside_model.py` ·
`ml_relative_upside_score.py` · `run_ml_relative_upside_score_v0.py` ·
`market_topn.py` · `market_topn_helpers.py` · `market_regime.py` ·
`market_data_store.py` · 프론트 전체 · `.env` · cron · OCI 경로.

---

## 3. 검증 대상과 평가 계약

### 3.1 재현 기술자 (PLAN §2.1) — 실측

model artifact 가 존재하지 않으므로(C-1) 아래 6종으로 검증 대상을 식별한다.

| 항목 | 실측값 |
|---|---|
| score 버전 | `relative_upside_score.v0` / `relative_upside_v0_linear` |
| `ml_relative_upside_features.py` sha256 | `11910654204c0956486cd5fe9fb37c88f70c7e08c0eee533dd8fd30d0a52d442` |
| `ml_relative_upside_model.py` sha256 | `8cb88f9e196428b3fa232f4f9773696e9036d888cf179dae8295a1bc7f97a004` |
| `ml_relative_upside_score.py` sha256 | `8d53aa56457b43121ddb8a7809d7acb08583a64ffb2bbe14c4628287b55e58b9` |
| `(ticker,date,close)` 전 구간 sha256 | `8b52d065944a6b6b27007b9de7a218d943719b5481637893ddb663e8df0c43a7` |
| 동 · **2026-08-20 절단** sha256 | `b6d74651a3533472c63e86e7e19d85274ffb42fb4645520601faf5b6a66aecd2` |
| hyperparameter | seed 42 / epochs 200 / lr 1e-3 / split 0.8 / `nn.Linear(7,1)` |
| 실행 환경 | torch **2.13.0** · cpu · python 3.12.13 · macOS-26.5.2-arm64 |

feature 컬럼 7종: `return_5d`, `return_10d`, `return_20d`, `excess_return_5d`,
`excess_return_10d`, `excess_return_20d`, `drawdown_20d`.

### 3.2 E2 — v0 레시피의 PIT 재현 (확정사항 1·2)

기준일 `t` 마다 아래 5단계만 수행했다. **별도 purge·embargo 규칙 0건.**

1. `date <= t` 로 가격 이력 절단
2. `build_feature_rows_for_ticker` 무변경 호출
3. `train_walk_forward` 를 **기본 인자 그대로** 호출 (80/20 split · 200 epoch ·
   lr 1e-3 · seed 42) — 인자 주입 0건을 T-3 이 강제
4. `predict_raw_scores` → `normalize_to_display_scores` 로 그 시점 점수 재현
5. 추가 규칙 없음

**확정사항 1 준수**: 전 구간 feature panel 을 만들어 `asof_date` 로 자르지 않았다.
매 기준일 절단된 가격 이력을 feature 함수에 전달했다.

**확정사항 2 준수**: 절단만으로 `target_end <= t` 가 성립한다.
`build_feature_rows_for_ticker` 는 `i + 20 < n` 일 때만 target 을 채우므로 target
보유 행의 최대 종료 index 는 `n-1`, 즉 절단 이력의 마지막 날짜(≤ t)다.
T-4 가 실제 값으로 이를 검사한다.

### 3.3 신호일 ≠ 진입일 (확정사항 3 / PLAN §2.4)

| 항목 | 값 |
|---|---|
| 판단일 `t` | 월말 거래일 (KODEX200 유효종가 기준) |
| 진입일 `e(t)` | `t` 다음 거래일 |
| 진입가격 | `e(t)` 종가 |
| 청산일 | 다음 리밸런싱 진입일 `e(t')` |
| benchmark | ETF·KODEX200 **동일 날짜** |
| 결측 | 제외 + 사유 기록. 보간·이월 0건 |

운영 가정: 월 1회 저빈도 · 동일가중 · 상위 10% 및 top-10 · 신규상장은 첫 유효종가
+20거래일 이후 편입 · 매수·매도 신호 산출 0건.

---

## 4. 실측 결과

**주 기준 = E2 · 1M · 필터 universe(인버스·레버리지·합성·선물 제외).**
모든 CI 는 확정 계약(circular moving-block · block 6개월 · 2,000회 · seed 42 ·
percentile 2.5/97.5)으로 산출했다. **t 값은 참고 수치**다.

### 4.1 평가 기간과 표본 [r2 정정]

| 항목 | 실측 |
|---|---|
| 거래일 (KODEX200 유효종가) | **3,038** · 2014-04-09 ~ 2026-08-27 |
| 월말 거래일 | 149 |
| 리밸런싱 점 (1M) 총계 | 147 |
| **`PRE_EVALUATION_WARMUP`** | **2** — `2014-04-30` · `2014-05-30` (`train_rows=0`) |
| **E2 평가일** | **145** · **2014-06-30 ~ 2026-06-30** |
| 3M 리밸런싱 점 | 145 |
| 3M **비중첩**(분기말) 사용 | **48** / 분기말 49 (1건 제외 — 3M 청산일 부재) |
| 평가 가능 달력연도 | **13** |

warmup 2건은 coverage·IC·연도별·시장별·top_decile·score_top10·3M·화면 슬레이트
**모든 집계에서 제외**되고 `pre_evaluation_warmup` 블록에 별도 기록된다.
`assert_evaluation_window()` 가 시작일 `2014-06-30` · 145개를 강제한다.

**fail-closed 게이트 결과**: `preflight_gate.status = OK` ·
평가일 145 · L-1/L-2/L-3 위반 `{L1:0, L2:0, L3:0}` · N-1 통과.

### 4.2 순위상관 (주 지표)

| 계열 | n | 평균 IC | sd | **95% CI** | t(참고) |
|---|---|---|---|---|---|
| **필터 universe (주)** | 145 | **−0.0435** | 0.3030 | **[−0.0906, +0.0011]** | −1.73 |
| 전체 universe (진단) | 145 | −0.0472 | 0.3231 | [−0.1009, +0.0066] | −1.76 |
| **단순 20일 초과수익 모멘텀 (진단)** | 145 | **+0.0226** | 0.3175 | [−0.0325, +0.0727] | +0.86 |
| 3M 중첩 | 143 | −0.0425 | 0.2952 | [−0.0930, +0.0065] | NW t = **−1.76** |

> **부호 오류가 아니다.** 동일한 라벨·동일한 파이프라인에서 단순 모멘텀은 **양(+)**,
> ML 점수는 **음(−)** 이다. 방향이 뒤집혀 있었다면 둘 다 음수여야 한다.

### 4.3 분위 · 상위군 · 비용

| 지표 | 실측 | 95% CI |
|---|---|---|
| Q5 − Q1 (최상위 − 최하위 분위) | **−0.831 %/월** | [−1.897%, +0.035%] |
| 상위 10% gross 평균 | −0.804 %/월 | [−2.090%, +0.195%] |
| 상위 10% **중앙값** (pooled) | **−0.280 %** | — |
| 상위 10% net **10bp** | −0.968 %/월 | [−2.251%, +0.031%] |
| **상위 10% net 25bp (주 기준)** | **−1.214 %/월** | **[−2.495%, −0.213%]** |
| 상위 10% net 50bp | −1.624 %/월 | [−2.895%, −0.620%] |
| 월간 turnover (실측 평균) | **82.61 %** (중앙값 85.84% · n=144) | — |
| 상위군 바스켓 월간 승률 | **44.83 %** | — |

> r1 대비 소수 4째자리 차이는 warmup 2건이 turnover·비용 시계열에서 빠졌기
> 때문이다(첫 평가일은 직전 바스켓이 없어 비용 0). IC 계열은 **완전히 동일**하다 —
> warmup 2건은 애초에 점수가 없어 IC 표본이 아니었다.

비용은 **월별 실측 turnover** 에 각각 적용했다(평균 turnover 사용 금지 — T-8 이 강제).

### 4.4 연도별 안정성

| 연도 | n | 평균 IC | | 연도 | n | 평균 IC |
|---|---|---|---|---|---|---|
| 2014 | 7 | −0.0883 | | 2021 | 12 | −0.0659 |
| 2015 | 12 | **+0.0753** | | 2022 | 12 | −0.1428 |
| 2016 | 12 | −0.0847 | | 2023 | 12 | −0.0221 |
| 2017 | 12 | **+0.0487** | | 2024 | 12 | −0.0725 |
| 2018 | 12 | −0.1617 | | 2025 | 12 | **+0.0740** |
| 2019 | 12 | **+0.0997** | | 2026 | 6 | −0.3143 |
| 2020 | 12 | −0.0648 | | | | |

**양(+) 연도 4 / 13** (A-3 기준 9 미달).

### 4.5 시장 상태별 (`market_regime._label_at` — 신규 규칙 0건)

| 상태 | n | 평균 IC | 95% CI |
|---|---|---|---|
| bull | 67 | −0.0291 | [−0.0860, +0.0321] |
| neutral | 38 | −0.0594 | [−0.1264, +0.0110] |
| bear | 39 | −0.0623 | [−0.1786, +0.0604] |
| (판정불가) | 1 | +0.3255 | 60거래일 미만이라 라벨 산출 불가 |

**세 상태 모두 음수.** 다만 셋 다 CI 가 0 을 포함하므로 R-4 는 발동하지 않았다.

### 4.6 U2 — 실제 화면 슬레이트

필터 → `one_month desc` Top 10 → 점수 결합 → 점수 재정렬 순서를 그대로 재현했다.

| 지표 | 실측 |
|---|---|
| 평가된 기준일 | **145** |
| 점수 상위 절반 − 하위 절반 평균 | **−0.176 %/월** · CI [−2.083%, +1.198%] |
| 상위 절반이 이긴 월 비율 | 55.17 % |

평균이 음수라 A-4 미충족(승월 비율만으로는 충족 불가 — 두 조건 모두 필요).

### 4.7 커버리지

| 항목 | 실측 (E2 평가일 145 기준) |
|---|---|
| 평균 | **99.99 %** |
| **최소** | **99.34 %** — 70% 미만 기준일 **0건** |
| 분모 정의 | PIT 편입 가능 **필터** universe = 태그 제외 **AND** 유효종가 ≥ 21 **AND** 첫 종가 후 20거래일 경과 |
| 결측 사유 | `lookback_부족` **0** · `KODEX_날짜없음` **0** · `close_결측` 0 · `진입일_가격없음` **2** · `청산일_가격없음` **6** |

> **r1 대비 변화**: r1 은 분모에 상장 직후·관측치 부족 ticker 를 포함해
> `lookback_부족 924` · `KODEX_날짜없음 78` 이 잡히고 평균이 97.00% 였다.
> r2 는 그 ticker 들이 **분모에서 빠지므로** 결측 사유가 0 이 되고 평균이 99.99%
> 로 올라간다. **분모 정의가 바뀐 것이지 데이터가 좋아진 것이 아니다.**
>
> **S-3**: E2 평가일 145개 중 coverage < 70% 는 **0건**이라 `preflight_gate` 가
> 통과했다. r1 의 "min = 0%" 두 날짜는 평가일이 아니라 `PRE_EVALUATION_WARMUP`
> 이다 (§11.1).

### 4.8 무결성 — 누수 · negative control

| 검사 | 결과 |
|---|---|
| **L-1 미래 입력 제거** | 위반 **0 / 147** |
| **L-2 날짜 assertion** (`e(t) > t`) | 위반 **0 / 147** |
| **L-3 `target_end <= t`** | 위반 **0 / 147** |
| **L-4 결정성** | §8.3 — **전체 결과 객체 canonical SHA-256 2회 실행 일치** |
| **N-1 negative control** | **통과** — 100회 permutation 평균 **−0.000651**, 구간 [−0.01130, +0.01346] 이 **0 포함** |

N-1 은 설계자 확정대로 **metric 구현의 negative control** 이며 누수 판정 수단이 아니다.
누수 판정은 L-1~L-3 이 한다.

### 4.9 3M 비중첩 (분기말) — r2 신설

중첩본과 **분리**해 집계했다.

| 지표 | 실측 | 95% CI |
|---|---|---|
| 분기말 기준일 / 사용 | 49 / **48** (제외 1건 — `3M 청산일 부재 (달력 끝)`) |
| 평균 rank IC | **−0.0717** | [−0.1615, +0.0087] |
| Q5 − Q1 | **−2.395 %/3M** | — |
| 상위 10% gross | −3.843 %/3M | — |
| **상위 10% net 25bp** | **−4.259 %/3M** | **[−8.871%, −1.307%]** |
| 월간(구간) turnover | 85.08 % | — |
| 승률 | **31.25 %** | — |

**중첩본(−0.0425, NW t −1.76)과 방향이 같고, 비중첩 표본에서는 net 25bp 의
CI 상한(−1.307%)도 0 미만**이다. 즉 3M 보조 기준도 R-3 방향을 뒷받침한다.

### 4.10 점수 기준 top-10 바스켓 — r2 신설

**화면 슬레이트(§4.6)와 다른 것**이다. 필터 universe 에서 참고점수 상위 10개만
동일가중으로 담았다.

| 지표 | 실측 | 95% CI |
|---|---|---|
| 사용 기준일 | **145** (결측 0건) | — |
| gross 평균 | −0.625 %/월 | [−2.127%, +0.535%] |
| pooled 중앙값 | −0.588 % | — |
| net 10bp | −0.800 %/월 | [−2.307%, +0.361%] |
| **net 25bp** | **−1.062 %/월** | [−2.568%, **+0.098%**] |
| net 50bp | −1.500 %/월 | [−3.006%, −0.339%] |
| 월간 turnover | **88.13 %** | — |
| 월 승률 | 44.83 % | — |

**판정에는 쓰지 않는다.** R-3 은 r1 과 동일하게 **상위 10%(≈90종) net 25bp** 로
판정하며, 그 사실을 테스트로 고정했다. 참고로 top-10 바스켓은 25bp 에서 CI 가
0 을 포함해(상한 +0.098%) **상위 10% 만큼 결정적이지 않다** — 표본이 10종뿐이라
분산이 크기 때문이다. 이 차이를 근거로 R-3 을 완화하지 않았다.

### 4.11 E1 — `E1_UNAVAILABLE`

| 게이트 | 기준 | 실측 | 판정 |
|---|---|---|---|
| G-1 후보 집합 | 완전 일치 | snapshot 1,157 = 재현 1,157 · 차집합 0 | **통과** |
| **G-3 점수 최대 절대오차** | ≤ 1.0 | **8.99** | **실패** |
| G-4 Spearman | ≥ 0.999 | **0.99994692** | 통과 |
| G-4 Top-100 일치율 | ≥ 0.95 | **1.000** | 통과 |

**기준을 완화하지 않고 `E1_UNAVAILABLE` 로 처리했고 E2 만 수행했다.**

**실패 원인 (실측)**: 운영 snapshot 은 2026-08-24T14:23:58Z 에 생성됐는데,
**2026-08-27 에 `date <= 2026-08-20` 인 행 86,376개(1,171 ticker)가 재수집**됐다.
입력 데이터 자체가 바뀌었으므로 비트 수준 재현이 불가능하다.
1,157종 중 **971종(84%)은 오차 0**, 1.0 초과는 **4종**뿐이다. 최악 종목(`407300`)은
raw prediction 차이 0.0029(상대 5.2%)인데, raw 예측값의 인접 간격 중앙값이
1.8e-05 로 매우 촘촘해 순위가 약 104계단 이동했다.

**G-2(계수)는 게이트가 아니라 기록**이다(참조 계수 부재). 재현된 계수:

```
return_5d      +0.135760      excess_return_5d   +0.188345
return_10d     +0.171520      excess_return_10d  -0.198516
return_20d     -0.220873      excess_return_20d  +0.174845
drawdown_20d   -0.026335      bias               +0.066135
train 1,064,287행 (2014-05-12 ~ 2025-07-01) / test 266,072행
```

`return_20d` 와 `excess_return_10d` 에 **큰 음수 가중치**가 실려 있다 — 모델이
20일 모멘텀을 **반대 방향**으로 학습했음을 보여주며, §4.2 의 부호 대비와 일치한다.

---

## 5. 사전 판정 기준 대조

임계값은 **PLAN §5 에 구현 전 고정**됐고 결과를 본 뒤 바꾸지 않았다.

### 5.1 수치 기준

| # | 조건 | 기준 | 실측 | 판정 |
|---|---|---|---|---|
| A-1 | 평균 IC ≥ 0.03 **그리고** CI 하한 > 0 | 0.03 / >0 | −0.0435 / 하한 −0.0906 | **미충족** |
| A-2 | 상위 10% net(25bp) ≥ +0.30%/월 · 중앙값 > 0 · CI 하한 > 0 | +0.003 | −1.214% / 중앙값 −0.280% / 하한 −2.495% | **미충족** |
| A-3 | 13개 연도 중 9개 이상 양(+) **그리고** 3개 시장 상태 모두 양(+) | 9 / 전부 | **4 / 13**, 3개 상태 모두 음수 | **미충족** |
| A-4 | 화면 Top10 상위−하위 평균 > 0 **그리고** 승월 비율 > 50% | >0 / >0.5 | −0.176% / 55.17% | **미충족** (평균 조건 실패) |
| A-5 | 누수 0 · N-1 통과 · 커버리지 ≥ 90% | — | 위반 0 · 통과 · **99.99%** | **충족** |
| A-6 | E1 의 명백한 반박 없음 | — | `E1_UNAVAILABLE` | **`NOT_EVALUABLE` · `passed=null`** |

`all_numeric_passed = False` (A-1~A-4 미충족). A-6 은 `null` 이므로 어떤 경우에도
**"전부 충족" 으로 집계되지 않는다** (§11.6).

### 5.2 REJECT 조건 (확정사항 5 반영)

| # | 조건 | 실측 | 발동 |
|---|---|---|---|
| R-1 | 평균 IC < 0 **그리고** CI **상한 < 0** | −0.0435 / 상한 **+0.0011** | 미발동 |
| R-2 | \|평균 IC\| < 0.01 **그리고** CI 가 0 포함 | 0.0435 (≥0.01) | 미발동 |
| **R-3** | **상위 10% net(25bp) ≤ 0** | **−1.214 %/월** (CI 상한 **−0.213%** 도 0 미만) | **발동** |
| R-4 | bear n ≥ 12 **그리고** IC < −0.02 **그리고** CI 상한 < 0 | n=39 · −0.0623 · 상한 **+0.0604** | 미발동 |

**R-3 발동 → `REJECT`.**

R-1 은 CI 상한이 +0.0011 로 간발의 차이로 미발동했다. 즉 **"음의 예측력"은 통계적으로
단정하지 못한다.** 그러나 R-3(비용 차감 후 상위군 손실)은 CI 상한까지 0 미만으로
명확하다. 결론의 근거는 **"점수가 반대로 맞힌다"가 아니라 "상위군이 비용을 넘지
못한다"** 이며, 결과서는 이 구분을 유지한다.

### 5.3 판정 상한과의 관계

PLAN §2.6 · P-1 의 상한 `RESEARCH_ONLY` 는 **`ADOPT` 를 막는 장치**다.
설계자 확정문대로 `REJECT` 는 상한과 무관하게 가능하며, 본 실행이 그 경우다.

---

## 6. 한계 (판정에 반영됨)

### 6.1 생존편향 — 복원 불가

| 측정 | 결과 |
|---|---|
| 최신 유효종가 < 2026-08-27 인 ticker | 21 |
| **2020-01-01 이전 시작 & 2026-01-01 이전 종료 ticker** | **0** |
| `etf_master` 상장·폐지일 컬럼 | 없음 |
| `market_timeseries_ingestion_state.confirmed_listing_date` 채워진 행 | **0 / 1,145** |

12년 구간에 "과거에 시작해 중간에 사라진" 종목이 0건이다. DB 는 현재 상장 종목만
담고 있고 상장폐지 ETF 는 가격까지 부재하다.

**편향의 크기와 방향을 정량화할 수 없으므로 `ADOPT` 의 충분한 근거로 사용할 수 없다.**
(설계자 확정 문구) 본 Step 에서는 `REJECT` 가 나왔으므로 이 상한이 결론을 바꾸지 않는다.

### 6.2 가격 의미 — `price return`

`price_basis = SOURCE_CLOSE` (§8 근거). 모든 수익률은 **분배금 미반영 price return**
이다. 분배금 성향이 높은 ETF 는 체계적으로 불리하게 측정되며, 분배금 데이터가 DB 에
없어 크기를 정량화할 수 없다.

### 6.3 그 밖

- **종목명 태깅 시점**: `classify_etf_tags` 가 **현재 이름**으로 분류한다. 과거 개명
  ETF 는 오분류 가능.
- **horizon 불균질**: 학습 target 은 ticker index 기반이라 종목별 달력 길이가 다르다
  (C-3). 동결 대상이라 수정하지 않았고, **평가 라벨은** 달력 기준으로 별도 정의했다.
- **초기 2개 기준일**: 2014-04-30 · 2014-05-30 은 v0 레시피가 아직 모델을 만들 수
  없어(`train_rows=0`) 점수·IC 가 없다. r2 에서 `PRE_EVALUATION_WARMUP` 으로
  분리해 모든 집계에서 제외했다(§11.1).

---

## 7. 산출물

| 경로 | 내용 |
|---|---|
| `state/ml/validity/relative_upside_validity_v1_latest.json` | 재현 기술자 · E1 게이트 4종 · 기준일별 IC/커버리지/학습행수 · 연도별 · 시장 상태별 · turnover · 비용 4종 · bootstrap CI · L-1~L-3 · N-1 · 판정 |
| `state/ml/validity/relative_upside_validity_v1_run_latest.json` | status · 시각 · 실행 시간 · 실행 노드 · **`canonical_sha256`** · 제외 필드 목록 |

게이트에 막히면 `run_latest` 에 `BLOCKED_*` 와 해당 날짜만 기록하고 **`validity_latest` 를 발행하지 않는다**(§11.1).

**OCI 전달 0건 · Telegram 0건 · PARAM 0건 · 운영 snapshot 갱신 0건.**

---

## 8. 실행 · 검수 실측

### 8.1 실행

| 항목 | 실측 |
|---|---|
| 상태 (모델 판정 후보) | `REJECT` |
| **실행 시간** | **780.70 초** (1차) · **777.78 초** (2차) |
| **canonical SHA-256** | `a0a905fd7877ee7a4a14c66f040b37e6da83c27bcb910f8de75fbf50759c8fd2` (양쪽 동일) |
| **실행 노드** | `HyungSooui-MacBookPro.local` · macOS-26.5.2-arm64 · python 3.12.13 · **torch 2.13.0** · device `cpu` · `cuda_available=False` |
| 명령 | `python scripts/run_ml_score_validity_eval_v1.py` |

### 8.2 자체 검수

| 항목 | 결과 |
|---|---|
| `black --check` | 신규 **9파일** unchanged (r1 보고 "6파일" 정정 — §11.8) |
| `flake8` | 신규 9파일 **0건** |
| 신규 테스트 | **105 passed** (metrics 30 · eval 29 · contracts 39 · **cli 7**) |
| 관련 회귀 | **67 passed** (`ml_relative_upside_*` 4파일 + `market_topn`) |
| 백엔드 전체 `pytest tests/` | **1,268 passed** (132.62초) — `.env` 기본값(PUSH_AUTOSEND 4개 전부 `false`) 그대로, 별도 환경변수 전제 없음 |
| **라이브 산출물 무결성** | 실행 전후 sha256 **완전 동일** (아래) |

```
84ed9c755fc807b7034f2600ec9f6d54e9e1f9d95d4d884ba26b7d20d5341151  state/ml/relative_upside_score_latest.json
1e06f52bd824f5e7db90addaf574716aaa8fe074e3e876cd2777bf2cd382828f  state/ml/relative_upside_score_run_latest.json
575577064492076764b7f391981ab4fc6c212b3e0fc72e8fa93a0e68e13cf093  state/ml/ml_baseline_v0_report_latest.json
```

### 8.3 결정성 (L-4) — 전체 결과 객체 실측 [r2 강화]

**일부 지표 비교가 아니라 결과 객체 전체를 비교한다.**

동일 seed 로 전체 평가를 **2회** 실행하고, `relative_upside_validity_v1_latest.json`
을 canonicalize(`sort_keys`) 한 뒤 SHA-256 을 대조했다.

| 항목 | 값 |
|---|---|
| 제외한 필드 | `generated_at` · `e1.elapsed_seconds` |
| 자기참조 정규화 | `determinism.canonical_sha256` 는 **제거가 아니라 `null` 로 되돌림** |
| **1차 canonical SHA-256** | `a0a905fd7877ee7a4a14c66f040b37e6da83c27bcb910f8de75fbf50759c8fd2` |
| **2차 canonical SHA-256** | `a0a905fd7877ee7a4a14c66f040b37e6da83c27bcb910f8de75fbf50759c8fd2` |
| 일치 | **True** |
| `run_latest.canonical_sha256` 기록값 | 동일 · **저장 파일에서 재계산 시 일치** |
| `generated_at` (다름이 정상) | 1차 `2026-08-29T13:04:17.184141+00:00` / 2차 `2026-08-29T13:17:16.077622+00:00` |

> **구현 중 발견·수정 1건**: 최초에는 해시가 자기 자신을 담는 필드를 정규화하지
> 않아, **기록된 해시를 저장 파일에서 재계산할 수 없었다**(검증자 재현 불가).
> `determinism.canonical_sha256` 을 계산 시 `null` 로 되돌리도록 고쳤다.
> 기록 시점에도 그 필드는 `null` 이었으므로 **해시 값 자체는 바뀌지 않았고**,
> 위 두 artifact 는 최종 코드로 재계산해도 같은 값을 낸다(실측 확인).
> 테스트 `test_l4_stored_hash_is_reproducible_from_stored_payload` 로 고정했다.

참고로 r1→r2 사이 모듈 구성을 바꿨을 때도 기준일별 IC 는 전량 일치했다.

### 8.4 테스트 유의미성 — 역검증 실측

보호 장치를 제거하면 실제로 실패하는지 확인했다.

| 라운드 | 제거한 보호 | 결과 |
|---|---|---|
| r1 | 진입일 분리 (`e(t)` → `t`) | T-2 **3건 실패** (`entry_after_signal` · `exit_after_next_signal` · `label_uses_entry_and_exit`) |
| r1 | U2 증분 절단 (전량 적재 후 산출) | T-10 `pit_replay_ignores_prices_after_signal_date` **실패** |
| r1 | E1 임계값 완화 (1.0 → 100.0) | T-12 `gate_thresholds_are_the_approved_values` **실패** |
| r2 | A-6 fallback 을 `passed=True` 로 되돌림 | **2건 실패** |
| r2 | coverage 게이트 무력화 | **2건 실패** |
| r2 | 20거래일 조건 제거 | **1건 실패** |
| **r3** | **차단 분기 무력화** (`if gate["status"] != "OK":`) | **CLI 4건 실패** |
| **r3** | **차단 시 기존 결과파일 삭제 제거** | **CLI 1건 실패** |

전부 원복 후 **105 passed** 재확인 (r3 시점 집중 테스트 총계).

> r2 역검증 중 20거래일 조건 제거가 처음에는 통과했다. 21관측 조건에 가려 분기까지
> 도달하지 못했기 때문이다. benchmark 보다 조밀한 날짜를 가진 fixture 로 분기를
> 직접 치도록 고쳤고, 이제 조건을 빼면 실패한다(§11.2 한계 참조).

### 8.5 파일 줄수 (KS-10 임계 650 대조)

| 파일 | 줄수 |
|---|---|
| `app/ml_score_validity_metrics.py` | 332 |
| `app/ml_score_validity_eval.py` | 581 |
| `app/ml_score_validity_report.py` | **626** |
| `app/ml_score_validity_screen.py` | 181 |
| `scripts/run_ml_score_validity_eval_v1.py` | 554 |
| `tests/test_ml_score_validity_metrics.py` | 206 |
| `tests/test_ml_score_validity_eval.py` | 492 |
| `tests/test_ml_score_validity_contracts.py` | 529 (r2 신규) |
| `tests/test_ml_score_validity_cli.py` | 245 (r3 신규) |

전부 650 미만.

---

## 9. 표준 7섹션 보고

### 1) 처리한 요구사항

§1 표 참조. 설계서 §4.1~§4.7 및 확정사항 1~5 **전부 DONE**.
E1 만 `E1_UNAVAILABLE` 인데, 이는 **미처리가 아니라 계약대로의 처리 결과**다
(게이트 실패 시 완화 없이 E2 만 수행 — §4.9).

### 2) 변경된 파일 목록

| 파일 | 구분 |
|---|---|
| `app/ml_score_validity_metrics.py` | 신규 (untracked) |
| `app/ml_score_validity_eval.py` | 신규 (untracked) |
| `app/ml_score_validity_report.py` | 신규 (untracked) |
| `app/ml_score_validity_screen.py` | 신규 (untracked) |
| `scripts/run_ml_score_validity_eval_v1.py` | 신규 (untracked) |
| `tests/test_ml_score_validity_metrics.py` | 신규 (untracked) |
| `tests/test_ml_score_validity_eval.py` | 신규 (untracked) |
| `tests/test_ml_score_validity_contracts.py` | **신규 (r2)** |
| `tests/test_ml_score_validity_cli.py` | **신규 (r3)** |
| `docs/ai_design/POC3/POC3-ML-02_..._DESIGN_V1.md` | 신규 (untracked) |
| `docs/ai_plan/POC3/POC3-ML-02_..._PLAN_V1.md` | 신규 (untracked) |
| `docs/ai_result/POC3/POC3-ML-02_..._RESULT.md` | 신규 (untracked · 본 문서) |
| `.gitignore` | **수정** — §4 참조 |
| `docs/STATE_LATEST.md` | 수정 |
| `state/ml/validity/*.json` | 신규 산출물 (**gitignore 대상**) |

**운영 코드 변경 0건.** 커밋 전이며 위 상태는 커밋 시점에 달라진다 —
검증자는 `git status` 로 재확인 바람.

### 3) 신규 추가된 의존성

**없음.** Spearman · circular moving-block bootstrap · Newey–West 를 표준
라이브러리로 직접 구현했다. scipy · statsmodels 는 **추가하지 않았다**
(신규 의존성은 사용자 승인 대상이라 애초에 배제).

### 4) 지시문 외 변경

**4건. 전부 사유와 함께 보고한다.**

1. **`app/ml_score_validity_screen.py` 신규 (PLAN §6 예상 파일 외)**
   — U2 재현을 위해 절단 임시 DB + `compute_topn` 무수정 호출을 담는 모듈.
   PLAN 은 2개 모듈을 예상했으나 C-4(§10) 대응에 별도 책임이 필요했다.

2. **`app/ml_score_validity_report.py` 신규 (PLAN §6 예상 파일 외)**
   — 최초 구현에서 CLI 스크립트가 **827줄**이 되어 **KS-10 트리거 #4(백엔드 650줄
   초과)** 에 걸렸다. 진행 중이던 실행을 중단하고 집계·판정 책임을 분리했다.
   결과는 §8.5 대로 전부 650 미만이다.

3. **`.gitignore` 수정** — `state/ml/validity/*.json` 2줄 추가.
   기존 ML artifact 전부(`ml_feature_sanity_latest` · `ml_baseline_v0_report_latest` ·
   `relative_upside_score_latest` 등)가 "실행마다 갱신되는 운영 artifact" 로
   gitignore 되어 있어 **같은 규약을 따랐다**. 결과 JSON 은 498KB 이고 실행마다
   재생성된다.

4. **PLAN V1 §1.4 정정 + §1.10 신설** — §10 의 C-4 발견을 PLAN 에 반영했다.
   설계자 지시("같은 파일 수정")대로 V2 를 만들지 않았다.

### 5) 알려진 한계 / 미완성

- **E1 미수행** — `E1_UNAVAILABLE`(§4.9). 따라서 A-6(E1 반박 여부)은 **판정 불가**이며
  판정에 반영되지 않았다. 재현 가능하려면 snapshot 생성 시점의 DB 상태가 보존돼야 한다.
- **생존편향 정량화 불가**(§6.1) — 상장폐지 ETF 가 가격까지 부재. 외부 데이터 추가는
  이번 Step 제외 범위.
- **price return** — 분배금 미반영(§6.2). 분배금 성향이 높은 ETF 는 불리하게 측정된다.
- **초기 2개 기준일**(2014-04-30 · 2014-05-30)은 `PRE_EVALUATION_WARMUP` 으로
  분리했다 — E2 평가 대상이 아니며 모든 집계에서 제외된다(§11.1).
- **종목 태그가 현재 이름 기준** — 과거 개명 ETF 오분류 가능(§6.3).
- **coverage 분모의 20거래일 조건**은 실제 데이터에서 21관측 조건과 사실상
  겹친다(§11.2). 독립 구속력은 ticker 가 benchmark 보다 조밀한 날짜를 가질 때만
  발생하며, 그 분기는 테스트로만 확인했다.
- **동일 기초지수 중복 처리 미구현** — 기초지수 매핑이 DB 에 없어 진단조차 근사다.

### 6) 다음 검증자에게 알릴 점

1. **판정 근거를 좁게 읽어야 한다.** `REJECT` 는 **R-3(비용 차감 후 상위군 손실)**
   단독 발동이다. **R-1(음의 예측력)은 미발동**했다 — CI 상한이 +0.0011 로 0 을
   아슬아슬하게 포함한다. "점수가 반대로 맞힌다"는 **단정하지 않았다**. §5.2 참조.
2. **부호 검증 방법**을 봐 달라. 같은 라벨에서 단순 모멘텀 IC **+0.0226**, ML IC
   **−0.0435** 다. 파이프라인 부호가 뒤집혔다면 둘 다 음수여야 한다.
   재현 계수의 `return_20d = −0.2209` 가 이를 뒷받침한다(§4.9).
3. **C-4 (`compute_topn(asof=…)`)** 는 제 PLAN 의 **사실 오류**였고 §10 에서 정정했다.
   **운영 영향 0건**(호출자 7곳 모두 `asof` 미전달)을 근거와 함께 확인해 달라.
4. **KS-10 분리**(지시문 외 변경 2)로 모듈 구성이 PLAN 과 다르다. L-4 는 §8.3 에
   **전체 결과 객체 canonical SHA-256 2회 일치**로 실측해 뒀다.
5. **커버리지**: r2 기준 E2 평가일 145개의 **최소 99.34% · 평균 99.99%** 이고
   70% 미만은 **0건**이다. r1 의 "min = 0%" 는 warmup 2건을 평가일로 잘못 센
   결과였고, r2 에서 `PRE_EVALUATION_WARMUP` 으로 분리했다(§11.1). 분모 정의도
   바뀌었으므로 r1 커버리지 수치와 직접 비교하면 안 된다(§4.7).
6. `_aggregate` 의 `unknown` regime **n=1** — `_label_at` 이 60거래일 미만에서
   None 을 반환하는 첫 기준일이다. 판정에 쓰이는 3개 상태와 분리해 표기했다.

### 7) 사용자 확인이 필요한 항목

1. **설계자 판정: 화면 `DEACTIVATE_AND_HIDE`** — 후속 Step
   `POC3-ML-02 REJECT Closeout` 에서 수행한다. 본 Step 에서는 화면·API·발송을
   **하나도 바꾸지 않았고**, 점수는 지금도 표시되며 후보 정렬에 쓰인다.
   확정된 처리 원칙: `CandidateTable`·`JudgmentWorkbench` 의 점수 기반 재정렬 중단 ·
   기본 화면에서 참고점수·점수 사유 비노출 · 후보 순서는 `compute_topn` 기본 순서 유지 ·
   **`0`/`미제공`/`참고용` 으로 대체 표시하지 않음** · 경고 문구를 붙여 계속 노출하지 않음 ·
   모델/평가 코드·JSON artifact 는 **삭제하지 않고 연구 baseline·실패 근거로 보존** ·
   OCI·PUSH·cron 무변경.
2. **커밋·푸시** — 검증자 `VERIFIED` 후 사용자 지시로 수행했다.
3. `.gitignore` 수정을 기존 ML artifact 규약에 맞춰 진행했다(§4-3).
   결과 JSON 을 저장소에 남기길 원하면 되돌리겠다.
4. **C-4 → `DEF-COMPUTE-TOPN-ASOF-HISTORICAL`** 로 `docs/backlog/BACKLOG.md`
   **결함 섹션에 등재했다**(설계자 승인). 원장 항목 수 55건은 불변 — 결함은 원장 밖 관리다.

---

## 10. 발견 사항 — C-4 `compute_topn(asof=…)` 는 과거를 재현하지 않는다

**PLAN 최초본 §1.4 의 제 주장이 틀렸다.** 구현 착수 시 실측으로 확인했다.

`app/market_topn_helpers.py:140 _compute_period()` 는 최신가를 **`history[-1]`** 에서
가져오고, `app/market_topn.py:207` 은 `fetch_price_history(tk)` 를 **날짜 제한 없이**
호출한다. 따라서 `asof` 는 **기준(base) 날짜만** 바꾸고 **최신(latest) 날짜는 바꾸지
못한다**.

실측 — `compute_topn(n=10, asof="2016-06-30")`:

```
rank 1  139260  TIGER 200 IT  selected_return_pct = 1017.2577
```

139260 의 2016-05-20 ~ 2016-07-05 종가는 11,785 → 12,804 로 연속적이고 급등이 없다.
1017% 는 **2026년 최신가 대 2016-05-31 기준가**다.

### 운영 영향 — **0건 (실측)**

`compute_topn(` 호출자 전수 확인:

| 호출자 | `asof` 전달 |
|---|---|
| `app/api_market_topn.py:83` | **없음** |
| `app/draft.py:183` | **없음** |
| `app/draft_three_push.py:302` · `:328` | **없음** |
| `app/api_decision_draft_preview.py:90` · `:216` | **없음** |
| `app/api_holdings_market_evidence.py:196` | **없음** |

전부 default(`None`) → `_latest_date_in_db()` → DB 최신일이므로 `history[-1]` 과
일치한다. **운영 결함이 아니라, 과거 날짜로 쓰인 적 없는 미사용 인자다.**

### 조치

운영 코드를 고치지 않았다(제외 범위). 대신 `date <= t` 로 절단한 **임시 SQLite** 를
만들어 `compute_topn(asof=t, db_path=<임시>)` 를 **무수정 호출**했다. §3.1 의
"기준일 이후 가격을 입력에서 제거" 와 같은 원리다.

검증: 같은 기준일이 **1017.26% → 5.38%** 로 정정됐다.
임시 DB 는 리밸런싱 순서대로 증분 적재하고 실행 후 삭제하며, 라이브 DB 는
`mode=ro` 로만 연다(T-15).

---

## 11. r2 보완 — 검증자 `REJECTED` 대응 이력

r1 의 수치와 결과를 **삭제하지 않고** 정정 형태로 보존한다. 아래는 설계자 보완
지시문 8개 항목의 처리 결과다.

| # | 보완 지시 | 처리 | 근거 |
|---|---|---|---|
| 1 | E2 warmup + S-3 fail-closed | **DONE** | §11.1 |
| 2 | coverage 분모 20거래일 조건 | **DONE** | §11.2 |
| 3 | 3M 비중첩 결과 집계 연결 | **DONE** | §11.3 |
| 4 | 점수 기준 top-N 바스켓 | **DONE** | §11.4 |
| 5 | L-4 전체 결정성 | **DONE** | §11.5 |
| 6 | A-6 tri-state | **DONE** | §11.6 |
| 7 | 테스트 연결 보강 | **DONE (r3 재보완)** | §11.7 |
| 8 | 결과서·STATE 정정 (Black 파일 수 오기 포함) | **DONE** | §11.8 |

### 11.1 E2 warmup 과 S-3 fail-closed

r1 은 `2014-04-30` · `2014-05-30` 을 **0% coverage 평가일로 포함**하고 S-3 을
사후 보고했다. 이것이 잘못이었다.

r2 계약 (`app/ml_score_validity_eval.py`):

```python
PRE_EVALUATION_WARMUP_DATES = ("2014-04-30", "2014-05-30")
E2_FIRST_SIGNAL_DATE = "2014-06-30"
E2_EXPECTED_POINT_COUNT = 145
BLOCKING_MIN_COVERAGE = 0.70
```

- 두 날짜는 `PRE_EVALUATION_WARMUP` 으로 분류되어 **coverage · IC · 연도별 ·
  시장별 · top_decile · score_top10 · 3M · 화면 슬레이트 집계에서 전부 제외**된다.
- 제외 날짜 · `train_rows=0` · 사유는 `pre_evaluation_warmup` 블록에 별도 기록된다.
- `assert_evaluation_window()` 가 **시작일 2014-06-30 · 145개**를 강제한다.
  위반 시 `RuntimeError` 로 즉시 중단한다.
- **warmup 집합은 사전 고정**이다. `classify_phase()` 는 실행 결과(`train_rows=0`)를
  보지 않는다 — 이후 발생하는 `train_rows=0` 은 warmup 으로 재분류되지 않고
  그대로 평가일에 남아 fail-closed 를 유발한다.

**fail-closed** (`preflight_gate()`): 집계·판정 **이전에** 실행 코드가 멈춘다.

| 조건 | status |
|---|---|
| 145개 평가일 중 coverage < 70% 또는 None 이 하나라도 존재 | `BLOCKED_COVERAGE` |
| L-1 / L-2 / L-3 위반 존재 | `BLOCKED_LEAKAGE` |
| N-1 negative control 실패 | `BLOCKED_METRIC_CONTROL` |

막히면 `run_latest` 에 status·해당 날짜를 기록하고 **`validity_latest` 를 정상
결과로 발행하지 않는다**(기존 파일도 삭제). 종료코드 3.
N-1 은 게이트 입력이므로 집계 **전에** 계산하도록 순서를 바꿨다.

### 11.2 coverage 분모 — PIT 편입 3조건

`is_pit_eligible()` 이 **셋을 모두** 요구한다.

1. 인버스·레버리지·합성·선물 제외 (`is_filter_universe`)
2. 기준일 이전 유효 종가 **≥ 21개** (`MIN_OBSERVATIONS`)
3. 첫 유효종가 이후 **benchmark 거래일 20일 경과** (`MIN_TRADING_DAYS_SINCE_LISTING`)

종가 한 건만 있는 ticker 는 분모에 들어가지 않는다.
결측 사유 카운트도 `in_filter` 가 아니라 `eligible` 기준으로 집계한다.

> **정직한 보고 1건**: 실제 데이터에서 ticker 가 benchmark 거래일에만 종가를
> 가지면 조건 2가 조건 3을 함의한다. 조건 3이 독립적으로 구속력을 갖는 것은
> ticker 가 benchmark 보다 조밀한 날짜를 가질 때(휴장일 혼입 등)다.
> 그 분기를 직접 치는 테스트를 넣었고(§11.7), 조건 3을 제거하면 그 테스트가
> 실패함을 역검증했다.

### 11.3 3M 비중첩 결과

분기말 기준일 부분집합을 **실제 집계에 연결**했다.
`e2.three_month_non_overlapping` 에 다음을 담는다 — `quarter_end_dates` ·
`dates_used` · `exclusion_reasons` · `ic`(평균·CI) · `quantile_spread_q5_minus_q1` ·
`top_decile_gross` · `top_decile_net_by_cost_bp`(4종) · `turnover` ·
`win_rate_by_date`. 중첩본(`ic_3m_overlapping`)과 **분리**해 기록한다.

### 11.4 점수 기준 top-N 바스켓

`e2.score_top10_basket` 을 신설했다. **화면 슬레이트와 명확히 구분**한다.

| 블록 | 정의 |
|---|---|
| `score_top10_basket` | 필터 universe 에서 **참고점수 상위 10개** |
| `screen_slate_u2` | **1개월 수익률 Top 10** 을 점수로 재정렬한 실제 화면 후보 |

산출: gross 평균·중앙값(pooled) · 0/10/25/50bp net · 월별 turnover · 월 승률 ·
표본 수 · 결측 사유.

**이 지표는 R-3 판정 기준을 사후 변경하지 않는다.** R-3 은 r1 과 동일하게
**상위 10% net(25bp)** 로 판정하며, 그 사실을 테스트로 고정했다
(`test_score_top10_basket_does_not_alter_r3_criterion`).

### 11.5 L-4 전체 결정성

r1 은 일부 지표만 비교했다. r2 는 **결과 객체 전체**를 비교한다.

`canonical_sha256(payload)` — 승인된 비결정 메타데이터만 제외하고 나머지 JSON
전체를 `sort_keys` 직렬화해 SHA-256 을 구한다.

```
NON_DETERMINISTIC_FIELDS = ("generated_at", "e1.elapsed_seconds")
```

이 목록 밖의 어떤 필드도 제외하지 않는다. 해시는 `validity_latest.determinism`
과 `run_latest.canonical_sha256` 양쪽에 기록된다.

### 11.6 A-6 tri-state

`E1_UNAVAILABLE` 을 `passed=true` 로 바꾸던 fallback 을 **제거**했다.

```json
{"status": "NOT_EVALUABLE", "passed": null, "reason": "E1_UNAVAILABLE"}
```

`all_numeric_passed` 도 3상태다 — 하나라도 `False` 면 `False`, `False` 는 없고
`None` 이 있으면 **`None`**(전부 충족이라고 말할 수 없음), 전부 `True` 여야 `True`.
결과서에서도 `충족` 이 아니라 **`판정 불가`** 로 유지한다.

### 11.7 테스트 연결 보강

**두 층으로 나눈다.**

- `tests/test_ml_score_validity_contracts.py` — **함수 단위**. `preflight_gate()` 가
  올바른 `BLOCKED_*` 를 만들어내는가.
- `tests/test_ml_score_validity_cli.py` — **실행 경로 통합** (r3 신설).
  CLI `main()` 을 실제로 돌려 **차단이 발행을 막는지**를 확인한다.

> **r2 보고 정정**: r2 는 함수 단위 테스트만 두고 "실패가 실제 실행을 막는지까지
> 검증" 이라고 적었다. **과장이었다.** `aggregate()` 미호출 · `run_latest` 의
> `BLOCKED_*` 기록 · `validity_latest` 미발행 · 종료코드는 검증하지 않았다.
> r3 에서 아래 통합 테스트로 실제로 닫았다.

| CLI 통합 테스트 | 확인 내용 |
|---|---|
| `test_cli_emits_validity_latest_when_gate_passes` | 통과 시에만 `aggregate` 1회 호출 · `validity_latest` 발행 · rc=0 · `canonical_sha256` 기록 |
| `test_cli_blocks_and_does_not_emit_when_coverage_below_threshold` | **실제 게이트**가 coverage 로 막고 → `aggregate` **미호출** · `validity_latest` **미발행** · `run_latest.status = BLOCKED_COVERAGE` + 해당 날짜 · **rc=3** |
| `test_cli_removes_stale_validity_latest_when_blocked` | 직전 정상 결과가 남아 있어도 차단 시 **제거**된다 (stale 발행 금지) |
| `test_cli_blocks_on_leakage_violation` | L-1 위반 → `BLOCKED_LEAKAGE` · 미발행 · rc=3 |
| `test_cli_blocks_on_n1_metric_control_failure` | N-1 실패 → `BLOCKED_METRIC_CONTROL` · 미발행 · rc=3 |
| `test_cli_reports_warmup_dates_separately_in_payload` | warmup 날짜가 `per_date` 에서 빠지고 `pre_evaluation_warmup` 에만 남는다 |
| `test_cli_enforces_evaluation_window_contract_on_full_run` | `--limit-dates` 없이 돌리면 **2014-06-30·145개 계약 위반 시 `RuntimeError`** |

무거운 경로(라이브 DB 적재 · U2 재현 · E1 재현)만 monkeypatch 로 대체하고,
**게이트 판정과 발행 분기는 실제 코드**를 그대로 태운다.

**역검증**: 차단 분기(`if gate["status"] != "OK":`)를 무력화하면 **4건 실패**,
차단 시 기존 결과파일 삭제를 빼면 **1건 실패**.

아래는 함수 단위 계약 대조표다.

| 요구 | 테스트 |
|---|---|
| S-1 위반 → 집계·판정 미발행 | `test_s1_leakage_violation_blocks_aggregation` · `test_s1_entry_not_after_signal_blocks` · `test_s1_target_end_after_signal_blocks` · `test_n1_failure_blocks_with_metric_control` |
| coverage <70% → `BLOCKED_COVERAGE` | `test_coverage_below_threshold_blocks_with_blocked_coverage` · `test_missing_coverage_is_blocked` · `test_coverage_exactly_at_threshold_is_not_blocked` |
| 3M 비중첩이 최종 JSON 에 존재 | `test_three_month_non_overlapping_is_present_in_final_payload` 외 3건 |
| score top-10 이 최종 JSON 에 존재 | `test_score_top10_basket_is_present_in_final_payload` 외 3건 |
| 20거래일 미충족 제외 | `test_pit_eligibility_20_trading_day_branch_is_reachable_and_binding` 외 4건 (T-13 보강) |
| L-4 전체 결과 객체 결정성 | `test_l4_full_payload_is_deterministic_across_two_builds` 외 3건 |
| A-6 `NOT_EVALUABLE / passed=null` | `test_a6_is_not_evaluable_when_e1_unavailable` 외 4건 |
| warmup 계약 | `test_warmup_dates_are_pre_declared_not_derived` 외 4건 |

T-14 도 다중 기준일 재현 결정성으로 확장했다(`test_t14_multi_date_reproduction_is_deterministic`).

### 11.8 r1 보고 정정

| r1 기재 | 정정 |
|---|---|
| "`black --check` 신규 **6파일**" | r1 시점 실제는 **7파일** (metrics · eval · report · screen · script · test_metrics · test_eval). r2 는 `test_contracts` · `test_cli` 추가로 **9파일** |
| "커버리지 min=0.00% — S-3 고지" | **오분류**. 두 날짜는 평가일이 아니라 `PRE_EVALUATION_WARMUP` 이다 (§11.1) |
| "A-6 `passed=True` (판정 불가)" | **`passed=null`, `status=NOT_EVALUABLE`** (§11.6) |
| "1M 기준일 147" | 총 리밸런싱 점 147 중 **E2 평가일 145** + warmup 2 |
