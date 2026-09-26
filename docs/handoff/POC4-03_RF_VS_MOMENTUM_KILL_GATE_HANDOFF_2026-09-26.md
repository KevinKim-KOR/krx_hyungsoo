# POC4-03 종료 인계 — RF 대 20일 모멘텀 최종 Kill Gate (REJECT_CLOSED · Track A 종료)

> **최종 인계 (2026-09-26 · 검증자 `VERIFIED_WITH_NOTES` · 커밋 `aa83a621` · push 전).** 정본 증거는 결과서
> `docs/ai_result/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_RESULT.md` 와 설계서 끝의 설계자 PLAN 판정 원문이다.
> 이 문서는 다음 챕터가 이어받는 데 필요한 것만 추린다.

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 챕터 개발자
- **입력**
  - 설계서 `docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md`
  - 설계자 PLAN 판정(`PASS_WITH_MANDATORY_AMENDMENT` · 2026-09-25)
  - 검증자 `VERIFIED_WITH_NOTES`(2026-09-26)
  - 설계자 RESULT 판정은 이 인계를 쓸 때까지 전달되지 않았다.

```text
POC4-03    CLOSED — REJECT_CLOSED · 근거 "특정 기간·설정 의존" · 실패 조건 C6 · C7 · 검증자 VERIFIED_WITH_NOTES
           설계자 RESULT 판정 대기(kill gate 결과는 설계자 PLAN 판정 §4 가 미리 정했다)
           Track A 종료 · POC4-04·05 미개방 · CONTROL 미실행(필수 보완 C — PIT 가 PASS 후보가 아니면 돌리지 않는다)
POC4 전체   Track A FAIL(이번) · Track B FAIL(POC4-02B REJECT) → 설계서 V2 §18 표의 다음 = "POC4 연구 종료"
           종료 확정과 다음 방향은 설계자·사용자가 정한다(코드는 판정만 냈다)
커밋        aa83a621 (staged 14개 한 커밋) · push 전 — caacc42f · 73be6948 과 함께 origin/main 보다 앞서 있다
OCI · PUSH · 외부 호출 · 신규 의존성 = 0 (PC 연구 전용)
```

---

## 1. 이 챕터가 만든 것

### 코드 (줄 수 2026-09-26 `wc -l` 실측 · 모두 신규)

```text
219  app/ml_rf_gate_models.py            RF 설정 동결 · 입력 규칙 · fit · 순서 고정 예측 · 설정 선택 · 모멘텀 점수
495  app/ml_rf_gate_eval.py              신호일 행 수집(02A 규칙) · 선형 재현 · RF S′ · 여섯 모델 기록 · 단면 동일 단언
498  app/ml_rf_gate_report.py            경계 동점 부분 가중 바스켓 · 지표 · paired 차이 · 전략 성과 · 강건성
366  app/ml_rf_gate_verdict.py           모델별 preflight · 조건 C1~C8 · 판정 순서 · recipe 동결 · 결과 payload
199  app/research_run_guard.py           라이브 5경로 지문 · 실행 폴더 규칙 · guard_failed · 자원 상한 · compare 규칙 (Q12)
562  scripts/run_poc4_03_rf_kill_gate.py  러너 — run --arm · compare · summarize · 02A 기준 hash 대조 · 재개 지문
```

기존 코드 파일 수정 0(02A·02B 모듈·러너 · `app/krx_sealed_reader.py` · 고정 모듈 3개 · `tests/conftest.py` · `tests/_live_guard.py`).

### 테스트 (`--collect-only` 실측 · 95건 · 전체 회귀 2,229 passed)

```text
tests/test_poc4_03_models.py   23   설정 sha · 입력 규칙 · n_jobs 와 무관한 bit 동일 예측 · 선택 규칙 · 모멘텀
tests/test_poc4_03_eval.py     16   02A evaluate_point 와 선형 기록 canonical 일치 · S′ 제외 · 선택 모집단 · 단면 동일
tests/test_poc4_03_report.py   30   부분 가중 · 동점 없으면 02A 값과 같음 · paired · 연도별 · 판정 순서 표
tests/test_poc4_03_runner.py   26   tmp 봉인 DB + tmp 02A 기준 폴더 · 가드 · 재개 · compare · summarize · 자원 상한
```

모두 tmp 고정 DB 또는 DB 없는 순수 함수다. 봉인·라이브 DB 는 열지 않고, 허용 목록 추가는 0 이다.

---

## 2. 결과 (PIT · 146 평가일 · 두 공식 실행 canonical `3c67331e…` 동일)

**판정 조건 (RF_PRIMARY − MOM · 날짜별 paired)**

```text
C1  IC 평균 > 0                  +0.00185                         참
C2  IC CI 하한 > 0               −0.0467 (상한 +0.0497)            거짓
C3  net25 평균 > 0               +0.00039/월                      참
C4  net25 CI 하한 > 0            −0.0059 (상한 +0.0069)            거짓
C5  고정 설정 둘 이상 양쪽 우위   RF_B · RF_C (RF_A 는 IC 열위)      참
C6  한 해 제외 최솟값 > 0         IC −0.0138 · net25 −0.0012 (2022) 거짓
C7  3구간 중 둘 이상 양쪽 우위    0/3                              거짓
판정 순서 4단계(C5~C7 중 거짓) → REJECT_CLOSED
```

- 2026년(7개 평가일)을 빼면 IC −0.0089 · net25 −0.00105 로 RF 가 오히려 낮다.
- RF 가 모멘텀보다 높은 날은 IC 75일 · net25 68일(146일 중)이다.
- 3구간 모두 IC 와 net25 의 방향이 엇갈린다.

**여섯 모델 (전략 = 편도 11.5bp · 2014-07-01 ~ 2026-09-01)**

```text
                 LIN       MOM       RF_A      RF_B      RF_C      RF_PRIMARY   KODEX200
IC 평균(필터)     −0.0322   +0.0224   +0.0136   +0.0337   +0.0423   +0.0243
net25 /월        −0.01050  −0.00787  −0.00630  −0.00724  −0.00684  −0.00748
전략 CAGR         5.19%     8.14%     10.60%    9.37%     10.08%    9.16%        14.56%
```

- 여섯 모델 모두 비용 전부터 KODEX200 보다 낮다(top-decile gross · net25 전부 음수 · gross 최고 RF_A −0.00219/월).
- 선형 baseline 은 모멘텀보다 IC −0.055 · net25 −0.0026 낮다(CI 는 0 을 걸친다).
- 검증 구간으로 고른 RF_PRIMARY(A 54 · B 32 · C 60일)가 고정 설정 B·C 보다 낮다. 결과를 보고 설정을 고르는 것은 금지라
  고정 설정 개별 값은 C5 와 보고에만 쓴다.

---

## 3. 다음 연구가 다시 쓸 수 있는 것

- **`app/research_run_guard.py`** — 연구 러너 공용 가드. POC4-03 에만 적용하기로 확정(Q12)했으므로, 다른 연구에 쓰려면 그 연구의
  PLAN 에서 설계자에게 먼저 묻는다.
  - `live_fingerprint` · `live_changes`: 라이브 5경로(파일 4개 sha256 + `state/runs` 이름 목록) 전후 대조
  - `check_out_dir` · `open_run_dir`: 새 폴더만 · 감시 경로 아래 거부 · 재개 규칙
  - `mark_guard_failed`: `guard_failed.json` 표식
  - `ResourceGuard`: `perf_counter` 경과 + peak RSS 상한
  - `compare_side`: `guard_failed` 폴더 · 다른 `schema_version` 은 예외로 거부
  - `determinism`: 재개 실행 · 같은 폴더 · 비공식 실행은 예외 없이 `determinism_confirmed=false`(→ PIT 최종 판정 INVALID_STOP · C9)
- **경계 동점 부분 가중** — `app/ml_rf_gate_report.py` 의 `partial_top` · `weighted_basket_series` · `weighted_strategy`.
  점수와 k 로만 편입도를 정하고, 동점이 없으면 02A 값과 정확히 같다(테스트).
- **RF 결정성** — `app/ml_rf_gate_models.py` 의 `ordered_predict` 는 `estimators_` 순서대로 합한다. 그래서 n_jobs 1·4·8 에서
  예측이 bit 단위로 같다(테스트). `forest_fingerprint` 로 숲 지문을 남긴다.
- **02A 선형 재현 게이트** — 새 경로 기록을 02A run1 `progress/{arm}_{date}.json` 의 `record` 와 canonical 텍스트로 대조한다.
  기존 모델을 다른 러너로 옮길 때 같은 방식으로 "같은 모델인지" 먼저 확인할 수 있다.
- **실행 비용 실측** — PIT 1회 perf_counter run1 5,573초 · run2 7,634초(PLAN 추정 6,491초 · run2 가 37% 긴 원인은 재지 않음) ·
  peak RSS 2.63 · 2.56 GB(smoke 2.83 GB).

---

## 4. 실행 산출물 (git 추적 밖 `state/ml/research/poc4_03/` — 결과서 hash 로 대조)

```text
pit_run1           result.json sha256 7354eaf1… · canonical 3c67331e… · 입력 지문 6844c8b2…
pit_run2           result.json sha256 13cbbe8c… · canonical 같음 · 입력 지문 같음 · determinism_compare.json(최종 판정)
smoke_pit_last2    비공식 smoke(마지막 2개 평가일 · official=false · 판정 후보 없음) — 삭제는 사용자 승인 필요
```

---

## 5. 남은 기술부채 · 열린 항목 (모두 비차단)

**이번 챕터 (검증자 메모 포함)**
1. **compare 가 두 실행의 입력 지문 동일을 코드로 강제하지 않는다**(검증자 B-6). 이번 두 실행은 직접 대조로 같았다.
   공식 실행 뒤라 "실행한 코드 = 제출 코드" 를 지키려고 고치지 않았다. 이 러너를 다시 쓰면 먼저 고친다.
2. **summarize 출력 폴더 검사에 02A 기준 폴더 · E2 manifest 경로가 빠져 있다**(검증자 B-6). summarize 는 실행되지 않았다.
   다시 쓰면 1번과 함께 고친다.
3. **5분위 스프레드의 경계 동점은 종목코드 순서로 갈린다** — 판정 미사용 보고 지표다.
4. 러너 562줄 · 리포트 498줄 · eval 495줄 — 600줄에 가깝다. 붙이기 **전에** 분리한다.

**앞 챕터에서 넘어와 아직 열린 것** (상세는 `docs/handoff/POC4-02_PARALLEL_RESEARCH_TRACKS_HANDOFF_2026-09-25.md` §6)
5. `scripts/run_poc4_02a_pit_bias.py` 586줄 KS-10 근접 · 02A 거래량 0 기록 범위 · 02B exact-k 진단 이름.
6. POC4-01 기존 테스트 229건 고정 fixture 전환.
7. `ASSUMPTIONS Q6` 운영 계약 OPEN.

---

## 6. 이 챕터에서 배운 것 (반복하지 말 것)

1. **`caffeinate -i` 는 덮개 닫힘 잠자기를 막지 못한다** — PIT run2 중 02:02 KST `Clamshell Sleep` 이 들어왔다. 이후
   `Dark Wake Thermal Emergency` 잠자기가 반복됐고, 벽시계 18,214초 · perf_counter 7,634초로 어긋났다(결과는 run1 과 같음).
   macOS `perf_counter` 는 `mach_absolute_time` 이라 잠자기 동안 멈춘다. 여러 시간 실행 전에는 덮개를 열어 두라고 먼저 말한다.
2. **가드 검토는 공식 실행 전에 끝낸다** — compare·summarize 빈틈을 공식 실행 뒤에 찾았다. 그때는 고치면 코드 동일성이 깨지므로
   공개만 할 수 있었다. 공식 실행 전에 compare·summarize 까지 포함해 자체 검토를 한 번 더 돈다.
3. **smoke 는 성과를 보지 않는 방식으로 돌린다** — 실데이터 smoke(마지막 2개 평가일)는 자원·선형 sha·RF 상태만 출력했다.
   설정은 그 전에 동결했다. 사전 등록 조건은 이런 절차로 지켜진다.
4. **얕은 RF 는 점수가 몇 개 값으로 뭉친다** — RF_A 는 경계 동점 51일 · 최대 묶음 371행이었다. 동점 규칙을 PLAN 에서 먼저 정해
   두어서 결과 뒤 논쟁이 없었다(부분 가중과 코드 순서 차이 RF_PRIMARY net25 0.00008/월).

---

## 7. 다음 사람이 바로 할 일

1. 설계자에게 POC4-03 결과 · 검증 결과를 보고한다(사용자 경유). 설계서 V2 §18 에 따른 **POC4 연구 종료 확정 여부**와 다음
   방향을 받는다.
2. push 는 사용자가 한다 — `caacc42f` · `73be6948` · `aa83a621` · 이 종료 문서 커밋.
3. 새 연구는 새 설계서 → 개발 PLAN(모호점 질문) → 설계자 확정 → 구현 순서다. POC4-04·05 는 번호가 있다는 이유로 열지 않는다
   (설계서 V2 §17).
4. 봉인 KRX 데이터를 다시 쓰면 `app/krx_sealed_reader.py` 를 수정 없이 쓴다(POC4-02 인계 §2).

---

## 8. 문서

```text
설계서 · 설계자 판정   docs/ai_design/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_DESIGN_V1.md (# 설계자 PLAN 판정)
선행 설계            docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md Part D §16~§18
PLAN                 docs/ai_plan/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_PLAN_V1.md
결과서                docs/ai_result/POC4/POC4-03_RF_VS_MOMENTUM_FINAL_KILL_GATE_RESULT.md
Master Plan          docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md §11 (단계 상태표)
현행 동작             docs/PROGRAM_TRUTH.md §7.1 (KRX 연구 DB consumer)
현재 상태             docs/STATE_LATEST.md
직전 챕터             docs/handoff/POC4-02_PARALLEL_RESEARCH_TRACKS_HANDOFF_2026-09-25.md
```

## 9. 사용자 확인

- 화면 확인 없음 · OCI 적용 없음(PC 연구 전용).
- smoke 폴더 삭제 여부(§4)는 사용자 승인 사항이다.
