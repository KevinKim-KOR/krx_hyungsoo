# POC4-03 — RF 대 20일 모멘텀 최종 Kill Gate RESULT

```text
FINAL_VERDICT        = REJECT_CLOSED — 근거 "특정 기간·설정 의존" · 실패 조건 C6 · C7
                       (PIT 두 공식 실행 compare 가 쓴 최종 판정 · determinism_compare.json)
KILL_GATE            = POC4-04·05 미개방 · Track A 종료 (설계자 PLAN 판정 §4) · CONTROL 미실행 (필수 보완 C — PIT 가 PASS 후보 아님)
RF_PRIMARY − MOM     = PIT · 146 평가일 모두 짝 · 날짜별 paired 차이
                       IC     +0.0018  (95% CI −0.0467 ~ +0.0497)
                       net25  +0.00039/월 (95% CI −0.00593 ~ +0.00690)
                       → 점추정은 RF 가 아주 조금 높다(C1·C3 참) · CI 가 0 을 포함한다(C2·C4 거짓)
                       → 한 해만 빼도 부호가 뒤집힌다(C6 거짓 · 2022 제외 IC −0.0138 · net25 −0.00119)
                       → 3구간 모두 IC 와 net25 방향이 엇갈린다(C7 거짓 · 둘 다 양수인 구간 0/3)
                       → 2026년(7개 평가일)을 빼면 IC −0.0089 · net25 −0.00105 — 전체 기간의 작은 우위는 2026년 몫이다
ABSOLUTE (참고)       = 여섯 모델 모두 top-decile net25 가 KODEX200 대비 음수 · 전략 CAGR(편도 11.5bp) RF_PRIMARY 9.16% ·
                       MOM 8.14% · LIN 5.19% · KODEX200 14.56%
LINEAR_REPRODUCTION  = PIT 146/146 — 새 경로 선형 기록 = 02A run1 progress record (canonical 텍스트)
DETERMINISM          = 처음부터 두 번 · canonical 3c67331e… 동일 · 입력 지문 6844c8b2… 동일 · determinism_confirmed = true
LEAKAGE · 사후 변경   = 여섯 모델 preflight OK · L1/L2/L3 0 · N-1 통과 · RF 설정 sha edca7023… · recipe sha 00992e6e… 불변
SEALED · LIVE        = krx_etf_universe_v1 SEALED · content c1a87776… 실행 전후 동일 · 라이브 5경로 전후 동일 · 02A 기준 hash 4개 일치
RESOURCE             = perf_counter run1 5,573초 · run2 7,634초 (상한 14,400) · peak RSS 2.63 · 2.56 GB (상한 10)
OCI · PUSH = 0 · EXTERNAL_CALLS = 0 · DEPENDENCY_ADDED = 0 · COMMIT · PUSH = 0 (설계 §9)
```

- **작성**: 개발자(VSCode Claude) · **독자**: 설계자(RESULT 판정) → 검증자(Codex)
- **입력**: 설계서 `docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md` (설계자 원문 + 끝 `# 설계자 PLAN 판정`
  원문 · 2026-09-25) · PLAN `docs/ai_plan/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_PLAN_V1.md` (§2 확정 계약 · §4 Q1~Q17)
- **실행 폴더**(git 추적 밖): `state/ml/research/poc4_03/pit_run1` · `pit_run2` · `pit_run2/determinism_compare.json`
- **코드 상태**: 커밋 전 코드로 실행(설계 §9 커밋 금지) · manifest 기록 `code_clean=false` · 실행 당시 HEAD `73be6948` · 실행 뒤 코드 변경 0(§4-9).

---

## 1) 처리한 요구사항

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| 설계 §2 | 봉인 v1 · reader 무수정 · PIT · 146일 · 7 feature · 학습/평가 label · 날짜 분할 purge 20 · 02A 필터·가격·사유 | DONE | 02A 행 수집을 그대로 따른다 · 평가일 목록 sha256 `e5f1be57…` = 02A · reader 수정 0 |
| 설계 §3 · Q14 | 선형 baseline 재현 — 불일치면 RF 전에 멈춤 | PARTIAL | PIT 146/146 일치. CONTROL 146건은 필수 보완 C 로 CONTROL 을 돌리지 않아 실데이터 대조가 없다(fixture 테스트는 두 arm 전 날짜 일치) |
| 설계 §3 · Q1 · Q2 | 모멘텀 = t 행 `return_20d` · 학습 없음 · 여섯 모델 `normalize_to_display_scores` | DONE | §4-2 |
| 설계 §3 · Q3 · Q16 | RF 3설정 동결 · 고정 3개 + `RF_PRIMARY` 모두 보고 · S′ 로만 학습 | DONE | 설정 sha `edca7023…` 실행 전후 같음 · 선택 A 54 · B 32 · C 60일 |
| 필수 보완 A · Q4 · Q17 | 선택 = V 모든 거래일 IC 평균(이름 필터·7 feature 완전·target 있음) · S 에서 label 끝 ≥ V 시작 행 제외 · 날짜별 제외 수 | DONE | 146일 모두 제외 0행(날짜별 기록) · 제외 경로는 간격 fixture 테스트로 확인 · 선택에 E2 `forward_excess` 미사용(테스트) |
| 필수 보완 B · Q5 | 반올림 없음 · finite 원값 · 정확 동률 A→B→C · 전부 None → INVALID | DONE | 146일 모두 사유 `MAX` · 정확 동률 0 · None 0 |
| 필수 보완 C · Q6 · Q10 | PIT 2회 → compare → PASS 후보일 때만 CONTROL | DONE | 최종 판정 REJECT_CLOSED → CONTROL 실행 0 |
| 필수 보완 D · Q13 | 경계 동점 부분 가중을 모든 성과 산식에 · 02A 코드 순서 값은 민감도로 병기 | DONE | gross · net grid · turnover · win rate · 전략 성과 · 민감도 label 블록 · `code_order_reference` 병기(§4-6). 5분위 스프레드는 §5-3 |
| 설계 §4 · Q9 · Q15 | 지표 · 비용(PRIMARY 25bp · 전략 11.5bp · 10·50bp) · bootstrap 10,000회 · seed 42 · 블록 6 · paired | DONE | §4-3 · §4-5 |
| 설계 §5 · Q8 | 강건성 — 연도별 · 3구간 · 가장 유리한 한 해 제외 · 2026 제외 · 고정 설정 3개 · 선택 빈도 · CONTROL 진단 | PARTIAL | CONTROL 진단 외 전부 냈다(§4-4 · §4-5). CONTROL 진단은 필수 보완 C 로 실행하지 않았다 |
| 설계 §6 · Q7 | 판정 조건 · 판정 순서 | DONE | 코드가 PIT 기록으로 계산 · C9 는 compare 에서 확인 뒤 최종 판정(§4-3) |
| 설계 §7 · Q11 | 10 GB · 4시간(perf_counter) · 처음부터 2회 · 재개 불인정 · 새 폴더만 | DONE | §4-8. run2 벽시계는 5.06시간(시스템 잠자기 포함 · §5-4) |
| Q12 | `app/research_run_guard.py` 신규 · POC4-03 에만 적용 | DONE | 기존 러너 import 0 |
| 설계 §9 | 금지 범위 | DONE | feature·label·평가일·설정 변경 0 · 신규 패키지 0 · UI·API·OCI·PUSH 0 · POC4-01·02 결과 덮어쓰기 0 · reader 수정 0 · 커밋·push 0 |
| PLAN §3 · §6 | 문서 — 결과서 · `PROGRAM_TRUTH` §7.1 · `STATE_LATEST` | PARTIAL | 결과서 · `PROGRAM_TRUTH` 완료. `STATE_LATEST` 는 판정 뒤 종료 인계 때 고친다(POC4-02 선례) |

## 2) 변경된 파일 목록

- `app/ml_rf_gate_models.py` (219) · `app/ml_rf_gate_eval.py` (495) · `app/ml_rf_gate_report.py` (498) ·
  `app/ml_rf_gate_verdict.py` (366) · `app/research_run_guard.py` (199) · `scripts/run_poc4_03_rf_kill_gate.py` (562): 신규
- `tests/test_poc4_03_models.py` (222) · `tests/test_poc4_03_eval.py` (303) · `tests/test_poc4_03_report.py` (388) ·
  `tests/test_poc4_03_runner.py` (540): 신규
- `docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md`: 신규 (설계자 원문 + PLAN 판정 원문)
- `docs/ai_plan/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_PLAN_V1.md`: 신규 (확정판)
- `docs/ai_result/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_RESULT.md`: 신규 (이 문서)
- `docs/PROGRAM_TRUTH.md`: 수정 — 머리글 최종 반영 2026-09-26 · §7.1 KRX 연구 DB consumer 에 POC4-03 러너 추가

줄 수는 `wc -l` 실측이다. 기존 코드 파일 수정은 0(02A·02B 모듈·러너 · reader · 고정 모듈 3개 · `tests/conftest.py` ·
`tests/_live_guard.py`). git 상태 실측은 §4-9.

## 3) 신규 추가된 의존성

없음 — scikit-learn 1.9.0 은 `requirements.txt` 에 이미 고정돼 있다(joblib 1.5.3 은 그 설치 의존성).

## 4) 지시문 외 변경

1. **러너 보조 옵션** — `run` 에 `--limit-dates` · `--sealed-db` · `--e2-manifest` · `--reference-dir` 을 뒀다. 테스트(tmp 봉인 DB ·
   tmp 02A 기준 폴더)와 smoke 에 쓴다. `--limit-dates` 를 주면 `official=false` 로 기록되고 판정 후보를 쓰지 않는다.
2. **공식 실행 전 비공식 smoke 1회** — 실데이터로 러너를 처음부터 끝까지 돌려 봤다(`state/ml/research/poc4_03/smoke_pit_last2` ·
   마지막 2개 평가일 · `official=false` · 232.9초 · peak RSS 2.83 GB). 화면에는 자원 · 선형 canonical sha · RF 상태·학습 행 수만
   출력했다. RF·모멘텀 성과 값은 열어 보지 않았다. 설정은 그 전에 이미 동결돼 있었고(sha `edca7023…`), 이후 바꾸지 않았다.
3. **결과 wrapper 필드** — PLAN 에 없던 이름으로 담은 것:
   - `strategy_reference_curves`(11.5bp 전략 곡선)
   - `role_02a`(02A 시나리오 역할 이름 보존)
   - `quantile_spread_note`(§5-3 표시)
   - `ci_note`(02A 공개 CI 는 2,000회라 직접 대조하지 않는다)

   판정 입력은 바꾸지 않는다.

## 5) 알려진 한계 / 미완성

1. **CONTROL 미실행** — 필수 보완 C 에 따른 것이다. 그래서 PIT−CONTROL 괴리 진단(설계 §5)과 CONTROL 선형 재현 146건(Q14)이 없다.
   `summarize` 명령은 구현·테스트만 됐고 실행되지 않았다.
2. **compare · summarize 가드의 빈틈 두 개**(구현 뒤 자체 재검토에서 찾음 · 공식 실행 뒤라 고치지 않음)
   - `compare` 는 PLAN 계약(§1-12 · canonical 동일)대로 결과만 대조한다. 두 실행의 **입력 지문이 같은지는 코드로 대조하지 않는다.**
     이번 두 실행은 manifest 의 `fingerprint_sha256` 을 직접 대조해 같음을 확인했다(§4-8 · 코드 정규화 AST · 패키지 버전 ·
     봉인 · recipe · 설정 · 02A 기준이 모두 이 지문에 들어 있다).
   - `summarize` 의 출력 폴더 검사는 02A 기준 폴더 · E2 manifest 경로를 제외 목록에 넣지 않는다. `summarize` 는 실행되지 않았다.
   - 공식 실행 뒤 코드를 고치면 "실행한 코드 = 제출 코드" 가 깨진다. 그래서 그대로 두었다. Track A 가 종료되므로 이 러너를
     다시 쓸 계획은 없다.
3. **5분위 스프레드(Q5−Q1)의 경계 동점은 02A 규칙(종목코드 순서)으로 갈린다** — 부분 가중은 top-decile 바스켓과 그 성과 산식에
   적용했고 5분위에는 적용하지 않았다. 판정에 쓰지 않는 보고 지표다. 결과에 `quantile_spread_note` 로 표시했다.
4. **`caffeinate -i` 는 덮개를 닫아 생긴 잠자기를 막지 못했다** — PLAN §1-8 · §2-8 의 "`caffeinate -i` 로 잠자기를 막는다"는
   run2 에서 성립하지 않았다.
   - pmset 기록: 2026-09-26 02:02:36 KST `Clamshell Sleep` → 이후 짧은 DarkWake 와 잠자기 반복(`Dark Wake Thermal Emergency`
     포함) → 04:51:34~05:53:48 깨어 있음.
   - 그래서 run2 는 벽시계로 18,214초(5.06시간 · 01:24:31~06:28:05 KST)가 걸렸다. `perf_counter`(macOS `mach_absolute_time` ·
     잠자기 동안 멈춤)는 7,633.85초였다.
   - Q11 확정 기준은 `perf_counter` 4시간이다 → 충족.
   - 결과 영향은 없다. run1 은 잠자기 없이 돌았고(벽시계 5,573초 = perf_counter 5,573.2초) run2 와 canonical 이 같다.
   - run2 의 perf_counter 가 run1 보다 37% 길다. 원인은 재지 않았다.
5. **절대 성과는 여섯 모델 모두 KODEX200 에 못 미친다** — top-decile net25 가 모두 음수이고, 전략 CAGR 이 모두 14.56% 아래다.
   kill gate 질문(RF 가 모멘텀을 이기는가)과 별개 사실이다.
6. 결과·실행 폴더는 git 추적 밖이다. 이 문서의 hash 로 대조한다.

## 6) 다음 검증자(Codex)에게 알릴 점

- **판정 순서 적용**(PLAN §2-7):
  1. INVALID 사유 0.
  2. C1·C3 참이라 2단계(둘 다 거짓)·3단계(하나만 거짓)에 걸리지 않는다.
  3. C5 참 · C6·C7 거짓 → 4단계 `REJECT_CLOSED`.

  C2·C4 도 거짓이지만 4단계가 먼저다. `result.json` 의 `verdict_candidate` 와 `determinism_compare.json` 의 `final_verdict` 가
  같다.
- **C6 은 "모든 해 y 에 대해 y 를 뺀 paired 평균의 최솟값 > 0"** 이다(Q8). IC 는 13개 해 중 6개(2016 · 2018 · 2019 · 2022 · 2025 ·
  2026)를 빼면 음수가 되고, net25 는 5개(2015 · 2016 · 2018 · 2022 · 2026)를 빼면 음수가 된다(§4-4).
- **S′ 제외는 실데이터 146일 모두 0행**이다. 제외 코드 경로는 `tests/test_poc4_03_eval.py` 의 간격 fixture 로 확인했다.
  실데이터에서는 RF 학습 행이 선형 학습 행과 같다(마지막 날 921,424 = 02A PIT 학습 행).
- **실행 뒤 코드 변경 0**: run1·run2 manifest 의 불러온 모듈 25개(새 파일 6개 포함)와 고정 모듈 3개의 raw sha256 이 현재 파일과
  전부 같다(§4-9 실측).
- **§5-2 가드 빈틈 두 개**를 먼저 봐 달라 — 이번 결과에는 영향이 없다(입력 지문 직접 대조 · summarize 미실행).
- **고정 설정 개별 결과는 C5 와 보고에만 쓴다** — RF_C 는 자기 IC 의 CI 하한이 0 보다 크다(+0.0118). 하지만 모멘텀 대비 차이의
  CI 는 0 을 포함하고, 결과를 보고 설정을 고르는 것은 금지(설계 §3 · §9)다. 검증 구간으로 고른 `RF_PRIMARY` 는 고정 설정 B·C 보다
  IC·net25 가 낮다.
- **경계 동점**: RF_A 51일 · 최대 묶음 371행이 가장 크다. 그래도 net25 의 부분 가중과 코드 순서 값 차이는 RF_PRIMARY
  0.00008/월(−0.00748 대 −0.00756) · RF_A 0.00002/월이다(§4-6).
- 러너 562줄 — 600 미만이다.

## 7) 사용자 확인이 필요한 항목

1. **Track A 종료 · POC4-04·05 미개방** — 설계자 kill gate 에 따른 결과다. 코드는 판정만 냈고, 다음 방향은 설계자·사용자가 정한다.
2. **비공식 smoke 폴더** `state/ml/research/poc4_03/smoke_pit_last2`(git 밖 · §4-2)를 남겨 두었다 — 파일 삭제는 승인이 필요하다.
3. **공식 실행 중 Mac 덮개가 닫혀 잠자기에 들어갔다**(§5-4) — 결과에는 영향이 없다. 다만 pmset 에 `Dark Wake Thermal Emergency`
   기록이 있다. 긴 실행 때는 덮개를 열어 두는 편이 안전하다.
4. **커밋 범위** — 검증자 통과 전에는 커밋·push 0 이다. 통과 뒤 staged 파일을 함께 커밋한다(사용자 소유
   `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md` 제외).

---

## 4. 증거

### 4-1. 봉인 source · 02A 기준 · 입력 지문

```text
봉인        krx_etf_universe_v1 SEALED · file fe3022e9… · content c1a87776… · integrity ok · quick ok · 3,122 거래일
            (20140102~20260921) · payload/row 불일치 0 · 두 실행 모두 전후 14필드 동일
02A 기준     result.json edb1b0f6… · run_manifest_final 4e5cd27c… · progress digest d4291340… · E2 manifest 6b9c8938…
            (시작 전 대조 · 네 개 모두 일치)
평가일       146 (2014-06-30 ~ 2026-07-31) · 목록 sha256 e5f1be57… (02A 와 같음)
설정·recipe  RF 설정 sha256 edca7023bb80aebb… · recipe sha256 00992e6eaa239468… (코드 상수와 대조 · 실행 전후 같음)
패키지       scikit-learn 1.9.0 · joblib 1.5.3 · numpy 2.4.6 · torch 2.13.0 · scipy 1.18.0 · pandas 2.3.3 · Python 3.12.13 · cpu
입력 지문    run1 = run2 = 6844c8b222b2347dbb1c816c00b2e0b9e66bf81a1c7f3d07902642aef097874f
```

### 4-2. RF 설정 · 선택 · 모멘텀

```text
설정         RF_A depth 4 · leaf 0.005 · max_features 1.0 │ RF_B 8 · 0.001 · 0.5 │ RF_C 16 · 0.0002 · 0.5
             공통 트리 200 · 표본 25% · seed 42 · n_jobs 8 · 순서 고정 예측(estimators_ 순서 합 / 트리 수)
학습 행 S′   6,405 (2014-06-30) ~ 921,424 (2026-07-31) · label 끝 ≥ V 시작 제외 146일 모두 0행
선택 모집단  2,040 ~ 455,646 행 (V 모든 거래일 · 이름 필터 · 7 feature 완전 · target 있음)
선택 결과    RF_A 54 · RF_B 32 · RF_C 60 일 · 사유 MAX 146 · 정확 동률 0 · val_IC None 0
             최고 val_IC 범위 −0.2846 ~ +0.1734
연도별 선택  2014 A5 C2 · 2015 A6 B4 C2 · 2016 A4 B1 C7 · 2017 A2 B3 C7 · 2018 A7 B1 C4 · 2019 B1 C11 · 2020 A3 C9 ·
             2021 A6 C6 · 2022 A4 B8 · 2023 A2 B6 C4 · 2024 A3 B4 C5 · 2025 A10 C2 · 2026 A2 B4 C1
모멘텀       t 행 return_20d · 학습 없음 · 부호 +
표본         날짜별 평가 표본 n 102 ~ 914 (여섯 모델 같은 단면 · 날짜마다 단언)
```

### 4-3. 판정 조건 (PIT · RF_PRIMARY − MOM · 146일 paired)

| 조건 | 정의 | 값 | 결과 |
|---|---|---|---|
| C1 | IC paired 평균 > 0 | +0.00185 | 참 |
| C2 | IC paired 95% CI 하한 > 0 | −0.04671 (상한 +0.04973) | 거짓 |
| C3 | net25 paired 평균 > 0 | +0.000385 | 참 |
| C4 | net25 paired 95% CI 하한 > 0 | −0.005930 (상한 +0.006902) | 거짓 |
| C5 | 고정 설정 중 IC·net25 차이 둘 다 > 0 인 설정 ≥ 2 | RF_A 아님(IC −0.0089) · RF_B 맞음 · RF_C 맞음 → 2 | 참 |
| C6 | leave-one-year-out 최솟값 > 0 (IC · net25) | IC −0.01378 · net25 −0.00119 (둘 다 2022 제외 때) | 거짓 |
| C7 | 3구간 중 IC·net25 둘 다 > 0 인 구간 ≥ 2 | 0 구간 | 거짓 |
| C8 | PIT 우위 (C1 ∧ C3) | — | 참 |
| C9 | 처음부터 2회 canonical 동일 | 3c67331e… = 3c67331e… | 참 |
| C10 | 누수·입력·사후 변경 0 | `invalid_reasons = []` — 여섯 모델 preflight OK · 누수 L1/L2/L3 0 · N-1 통과 · 봉인·라이브·02A 기준·설정·recipe 불변 · 선형 146/146 | 참 |

- 짝 날 수는 146/146이고 빠진 날은 없다.
- RF 가 모멘텀보다 높은 날은 IC 75일 · net25 68일이다.
- 짝 차이의 중앙값은 IC +0.0028 · net25 −0.0010 이다. net25 는 평균과 부호가 반대다.

**고정 설정 · 선형 대 MOM (paired 평균 · 95% CI · 참고)**

```text
               IC 차이                               net25 차이
RF_A − MOM     −0.00886 (−0.06460 ~ +0.04510)        +0.00157 (−0.00525 ~ +0.00817)
RF_B − MOM     +0.01129 (−0.03830 ~ +0.06318)        +0.00063 (−0.00500 ~ +0.00621)
RF_C − MOM     +0.01993 (−0.03175 ~ +0.07335)        +0.00103 (−0.00473 ~ +0.00697)
LIN  − MOM     −0.05463 (−0.11351 ~ +0.00114)        −0.00264 (−0.00940 ~ +0.00402)
```

### 4-4. 강건성 (RF_PRIMARY − MOM)

```text
연도별        날짜   IC 차이     net25 차이
2014           7    −0.1423     −0.02640
2015          12    +0.0112     +0.00687
2016          12    +0.0564     +0.01469
2017          12    −0.1350     −0.00788
2018          12    +0.1554     +0.00505
2019          12    +0.0307     −0.00082
2020          12    −0.1982     −0.00370
2021          12    −0.0655     −0.00514
2022          12    +0.1764     +0.01803
2023          12    −0.0262     −0.00401
2024          12    −0.0476     −0.00712
2025          12    +0.0228     −0.01270
2026           7    +0.2145     +0.02882

한 해 제외     2014 +0.0091 / +0.00173 · 2015 +0.0010 / −0.00020 · 2016 −0.0030 / −0.00090 · 2017 +0.0141 / +0.00113 ·
(IC / net25)   2018 −0.0119 / −0.00003 · 2019 −0.0007 / +0.00049 · 2020 +0.0198 / +0.00075 · 2021 +0.0079 / +0.00088 ·
               2022 −0.0138 / −0.00119 · 2023 +0.0044 / +0.00078 · 2024 +0.0063 / +0.00106 · 2025 −0.00003 / +0.00156 ·
               2026 −0.0089 / −0.00105
               최솟값 IC −0.01378 · net25 −0.00119 (둘 다 2022 제외) · 13개 해 모두 계산됨

3구간          2014-06-30 ~ 2018-06-29 (49)   IC −0.0193   net25 +0.00058   둘 다 양수 아님
               2018-07-31 ~ 2022-07-29 (49)   IC −0.0181   net25 +0.00082   둘 다 양수 아님
               2022-08-31 ~ 2026-07-31 (48)   IC +0.0439   net25 −0.00026   둘 다 양수 아님

2026 제외      139일   IC −0.0089   net25 −0.00105   (보고만)
```

### 4-5. 여섯 모델 지표 (PIT · 146일 · 부분 가중 바스켓)

```text
                        LIN          MOM          RF_A         RF_B         RF_C         RF_PRIMARY
IC 평균 (필터 · 판정)    −0.0322      +0.0224      +0.0136      +0.0337      +0.0423      +0.0243
  95% CI (10,000회)     −.0764~+.0112 −.0303~+.0730 −.0259~+.0547 −.0021~+.0710 +.0118~+.0749 −.0125~+.0628
IC 중앙값                −0.0216      +0.0347      +0.0094      +0.0191      +0.0217      −0.0108
IC 전 종목               −0.0399      +0.0181      +0.0163      +0.0364      +0.0457      +0.0294
Q5−Q1 (코드 순서 · §5-3) −0.00581     +0.00658     +0.00593     +0.00794     +0.00972     +0.00729
top-decile gross /월     −0.00640     −0.00381     −0.00219     −0.00309     −0.00269     −0.00327
net 10bp                 −0.00804     −0.00543     −0.00383     −0.00475     −0.00435     −0.00495
net 25bp (PRIMARY)       −0.01050     −0.00787     −0.00630     −0.00724     −0.00684     −0.00748
net 50bp                 −0.01461     −0.01192     −0.01041     −0.01138     −0.01099     −0.01169
turnover                 0.826        0.816        0.827        0.835        0.836        0.848
win rate (날짜)          0.459        0.466        0.479        0.479        0.493        0.493
전략 (편도 11.5bp · 146기간 · 2014-07-01 ~ 2026-09-01 · KRX_BASEPRICE_CHAIN)
  CAGR                   5.19%        8.14%        10.60%       9.37%        10.08%       9.16%
  MDD                    −35.81%      −40.34%      −31.93%      −33.01%      −28.53%      −37.69%
  Sharpe_0rf             0.370        0.489        0.638        0.578        0.636        0.570
  상대 wealth (끝)       0.354        0.496        0.652        0.569        0.616        0.556
  IR                     −0.505       −0.421       −0.319       −0.376       −0.361       −0.405
  KODEX200 (같은 기간)   CAGR 14.56% · MDD −32.19% · 끝 equity 5.229
전략 legacy all-in 25bp  2.44%        5.35%        7.72%        6.48%        7.18%        6.24%
민감도 label (판정 미사용 · 거래량 0 진입·청산 허용)
  IC                     −0.0321      +0.0223      +0.0121      +0.0325      +0.0411      +0.0223
  net 25bp               −0.01061     −0.00777     −0.00647     −0.00732     −0.00761     −0.00773
```

LIN 열은 02A PIT 공개값(IC −0.0322 · 전 종목 −0.0399 · net25 −0.01050 · CAGR 5.19% · 상대 wealth 0.354)과 같다. CI 는
10,000회라 02A 공개 CI(2,000회)와 다르다.

### 4-6. 경계 동점 · 02A 코드 순서 민감도 (필수 보완 D)

```text
                      LIN      MOM      RF_A      RF_B     RF_C     RF_PRIMARY
경계 동점 날           0        0        51        17       4        28
최대 경계 묶음 (행)    1        1        371       92       16       220
최소 고유 점수 비율    0.997    0.972    0.102     0.276    0.605    0.157
net25 부분 가중        −0.01050 −0.00787 −0.00630  −0.00724 −0.00684 −0.00748
net25 코드 순서        −0.01050 −0.00787 −0.00632  −0.00724 −0.00684 −0.00756
CAGR 11.5 부분 가중    5.19%    8.14%    10.60%    9.37%    10.08%   9.16%
CAGR 11.5 코드 순서    5.19%    8.14%    10.58%    9.37%    10.08%   9.06%
```

RF_PRIMARY − MOM net25 는 부분 가중 +0.00039 · 코드 순서 +0.00031 이다. 방향이 같다. 경계 동점이 없는 날은 두 방식의 값이
정확히 같다(테스트).

### 4-7. 참고 — PLAN 예상 대비

```text
PIT 1회 예상 6,491초 (1.80시간 · ×1.00) → 실측 perf_counter run1 5,573초 · run2 7,634초
RSS 예상 약 3 GB → 실측 peak 2.63 · 2.56 GB (smoke 2.83 GB)
```

### 4-8. 실행 · 결정성 · 자원

```text
run1   2026-09-25 14:51:35Z ~ 16:24:28Z · perf_counter 5,573.2초 · peak RSS 2,627,911,680 B · resumed=false · 146 계산 · 0 재사용
       canonical 3c67331e0dac4c971734b5ba412717b73c3fec6fdc7433f65018a8d384dbcd5b · result.json sha256 7354eaf1…
       라이브 5경로 전후 동일(unchanged=true) · 봉인 전후 동일
run2   2026-09-25 16:24:31Z ~ 21:28:05Z · perf_counter 7,633.85초 · 벽시계 18,214초(잠자기 포함 · §5-4)
       peak RSS 2,556,952,576 B · resumed=false · 146 계산 · 0 재사용 · canonical 같음
       result.json sha256 13cbbe8c… (generated_at 만 다름 — canonical 제외 필드)
       라이브 5경로 전후 동일(unchanged=true) · 봉인 전후 동일
compare 21:28:08Z · identical = true · both_official = true · determinism_eligible = true(두 폴더 모두 재개 없음)
       determinism_confirmed = true · 두 폴더의 저장 canonical = 다시 계산한 canonical
입력 지문 run_manifest.json fingerprint_sha256 두 실행 같음 6844c8b2… (직접 대조 · §5-2)
선형 재현 146/146 (linear_reproduction.all_equal = true)
누수    여섯 모델 L1 0 · L2 0 · L3 0 · coverage 차단 0 · N-1 셔플 통제 통과(평균 +0.00018 ~ +0.00075)
자원    상한 perf_counter 14,400초 · RSS 10×10^9 B — 두 실행 모두 신호일마다 확인 · 결과 쓰기 직전 한 번 더 확인
```

### 4-9. 코드 hash · 자체 검수 · git 상태

```text
실행 당시 = 지금 (run1·run2 manifest 의 불러온 모듈 25개 raw sha256 전부 현재 파일과 일치)
  app/ml_rf_gate_models.py f9b1c97a… · app/ml_rf_gate_eval.py 9154b662… · app/ml_rf_gate_report.py d18d4c8a…
  app/ml_rf_gate_verdict.py 8cbeb60a… · app/research_run_guard.py 9407fb98… · scripts/run_poc4_03_rf_kill_gate.py 490f626b…
  app/krx_sealed_reader.py e43275ff… · 고정 모듈 features 11910654… · model b41b2a9a… · score 8d53aa56… (git HEAD 와 같음 · 수정 0)
black --check · flake8 · py_compile   새 파일 10개 통과
POC4-03 테스트                        95 passed (models 23 · eval 16 · report 30 · runner 26 — --collect-only 실측) · 76.9초 — tmp 고정 DB · 봉인·라이브 DB 미접속 · 허용 목록 추가 0
전체 회귀                             2,229 passed (0:05:30) · 경고 1건 = 기존 starlette `httpx` 사용 중단 경고(POC4-03 무관)
git 상태                              staged 신규 A 13 · 수정 M 1 (§2 목록과 같음) · 미추적 1 = 사용자 소유 handoff(제외) — 보고 직전 실측
```
