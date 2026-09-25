# POC4-02 종료 인계 — 공용 봉인 reader · 02A PIT 생존편향 측정 · 02B 위험 조기감지 기준선

> **최종 인계 (2026-09-25 · 검증자 `VERIFIED` · 커밋 `37843fc9` push 뒤).** 정본 증거는 결과서 두 개
> (`docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md` · `POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md`)와 설계서 끝의
> 설계자 판정 원문이다. 이 문서는 다음 챕터(POC4-03)가 이어받는 데 필요한 것만 추린다.

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 챕터(POC4-03) 개발자
- **입력**: 설계서 V2 · 설계자 PLAN 판정(`PASS_WITH_MANDATORY_AMENDMENTS` · 2026-09-25) · 설계자 RESULT 판정(2026-09-25) ·
  검증자 `VERIFIED`(2026-09-25)

```text
POC4-02A   CLOSED — MEASURED_ACCEPTED · 검증자 VERIFIED
           SURVIVORSHIP_EFFECT(PIT − CONTROL) 작고 음수 · CI 0 포함 · 날짜별 방향 일관되지 않음
           KRX_POINT_IN_TIME_UNIVERSE_V1 · REDUCED_NOT_ELIMINATED · RESEARCH_ONLY · UNBIASED_PERFORMANCE_CLAIM = NOT_YET
POC4-02B   CLOSED — REJECT_ACCEPTED · 재실행 없음 · Track B 종료 · 검증자 VERIFIED
           사건 정의 EVENT_DEFINITION_STATUS = RETIRED_AFTER_THIS_STUDY
           Track B 재시도는 새 PLAN · 새 사전 등록이 있는 별도 연구로만
다음        POC4-03 — Track A 최종 Kill Gate 하나만 (설계서 V2 Part D §16~§18)
           RF 가 단순 모멘텀을 이기지 못하면 POC4-04·05 는 열지 않고 Track A 종료 → Track A·B 모두 FAIL 이면 POC4 연구 종료
커밋        37843fc9 (staged 29개 한 커밋) · origin/main push 완료
OCI · PUSH · 외부 호출 · 신규 의존성 = 0 (PC 연구 전용)
```

---

## 1. 이 챕터가 만든 것

### 코드 (줄 수 2026-09-25 실측 · 모두 신규)

```text
362  app/krx_sealed_reader.py            공용 봉인 reader — 두 트랙이 수정 없이 import (§2)
267  app/ml_pit_universe.py              02A arm universe · 이름 필터 · 진입·청산 판정 · 제외 사유
389  app/ml_pit_bias_eval.py             02A 신호일 × arm 평가 — 날짜 분할 · 고정 trainer 호출 · 점수 · label
535  app/ml_pit_bias_report.py           02A 집계 · preflight · 전략 성과(가격 기준 덮어쓰기) · PIT − CONTROL 비교
586  scripts/run_poc4_02a_pit_bias.py    02A 러너 — run / compare · progress · --resume · manifest 두 파일
166  app/ml_ew_reproduce.py              02B 운영 표 재현 감사(읽기 전용 세션 사본)
285  app/ml_ew_market_axes.py            02B KRX 시장 축 13개 · PIT / FS / 전 종목
220  app/ml_ew_signals.py                02B 시점 기준 percentile · EARLY · REACTIVE · 경보 · 진단
407  app/ml_ew_events.py                 02B 사건 · 포착 · run · RANDOM_NULL
443  app/ml_ew_report.py                 02B 판정 1~10 · 변형 · 결과 payload
538  scripts/run_poc4_02b_early_warning.py  02B 러너 — run / compare · 단계별 progress · --resume
```

운영 모듈 · 고정 모듈(`app/ml_relative_upside_*`) · 기준선 `relative_upside_v1_snap_20260921` 수정 0.

### 테스트 (수집 수 실측 · 121건 · 전체 회귀 2,134 passed)

```text
tests/test_krx_sealed_reader.py        12   봉인·hash·읽기 전용·member 조인·관계 검증·연결 계열·구간 분리
tests/test_poc4_02a_pit_bias.py        17   universe · 사유 · 분할 경계 · label = forward_excess
tests/test_poc4_02a_pit_runner.py      18   새 폴더 · 재개 · 지문 · 라이브·봉인 가드 · 네트워크 0 · compare
tests/test_poc4_02b_axes.py             7   축 정의 · universe 변형
tests/test_poc4_02b_events.py          23   사건 · P/T/B · 잘림 · 분류 · run · RANDOM_NULL (DB 없음)
tests/test_poc4_02b_reproduce.py        7   세션 사본 재현 EXACT_MATCH / MISMATCH · 라이브 불변
tests/test_poc4_02b_runner.py           9   러너 · 재개 동일 · 판정
tests/test_poc4_02b_runner_guards.py   13   재개 가드 · 네트워크 0 · 다른 DB 연결 거부 · 원자 쓰기
tests/test_poc4_02b_signals.py         15   시점 기준성 · 동점 · 교정 3건 (DB 없음)
tests/_krx_fixture.py                       KRX 스키마 tmp 고정 DB 도우미 — 봉인 DB·라이브 DB 는 테스트 가드가 거부한다
```

---

## 2. 공용 봉인 reader — POC4-03 에서 KRX 데이터를 쓸 때

```python
from app.krx_sealed_reader import (DEFAULT_SEALED_DB, verify_sealed_source,
                                   assert_same_source, load_panel)
from app.ml_baseline_snapshot import guard_sqlite_paths

before = verify_sealed_source()                 # 파일 sha256 · seal 재계산 · payload hash · integrity (약 4.6초)
with guard_sqlite_paths([DEFAULT_SEALED_DB]):    # 실행 중 다른 DB 접속 차단
    panel = load_panel()                         # 1,419종목 · 3,122일 · 1,612,728행 (약 11.4초 · RSS 약 0.8 GB)
    ...
assert_same_source(before, verify_sealed_source())   # 결과를 쓰기 전에
```

- 봉인 DB 는 `file:<경로>?mode=ro&immutable=1` 로만 열린다. `app/ml_research_krx_universe.connect` · `market_data_store` 는
  DDL 을 하므로 봉인 DB 에 쓰지 않는다.
- 가격 기준 `KRX_BASEPRICE_CHAIN` — `r = CMPPREVDD_PRC / (TDD_CLSPRC − CMPPREVDD_PRC)` 를 `FLUC_RT/100` 과 0.005%p(+1e-9) 로
  검증하고 누적한다(분배 중립). 실제 불일치 0행 · 끊긴 구간 0. 불일치·무효 종가 행이 생기면 보정하지 않고 새 구간을 시작한다
  (`CodeSeries.segment` · `chain_history(upto)` 는 마지막 구간만 준다).
- `SealedPanel.present(date)` = 그날 v1 행이 있는 종목(PIT universe) · `panel.final_date` = 2026-09-21 · 069500 = `panel.benchmark()`.
- **reader 는 고치지 않는다**(설계자 판정 §3 · 공용 계약). 바꿀 일이 생기면 공통 계약 변경으로 설계자에게 올린다.

---

## 3. 02A — 결과와 다시 쓸 수 있는 것

**결과** (146 평가일 · 두 arm 누수 0 · N-1 통과 · 두 공식 실행 canonical `1e9a88af…` 동일)

```text
                          PIT        CONTROL    PIT − CONTROL (95% CI)
IC 평균                    −0.0322    −0.0294    −0.0029 (−0.0120 ~ +0.0048)
top-decile gross /월       −0.00640   −0.00548   −0.00092 (−0.00295 ~ +0.00044)
top-decile net 25bp /월    −0.01050   −0.00958   −0.00092 (−0.00297 ~ +0.00044)
전략 CAGR (편도 11.5bp)    5.19%      6.24%      −1.05%p   (KODEX200 같은 기간 14.56%)
```

모델 자체가 두 arm 모두 IC 음수다 — 생존편향 측정과 별개 기록이며 02A 는 모델 최종 판정을 내리지 않았다(설계자 RESULT 판정 §4).

**POC4-03 이 다시 쓸 수 있는 것**
- **날짜 기준 분할 + 고정 trainer** — `train_walk_forward` 에 학습일 행 S + 검증일 행 V 만 넘기고
  `train_split_ratio = (|S|+0.5)/(|S|+|V|)` · 매 호출 `train_row_count == |S|` · 마지막 학습일 < 검증 시작 assert
  (`app/ml_pit_bias_eval.py` `date_split` · `_check_trainer`). k/n 비율은 부동소수로 약 4% 에서 1행 어긋난다.
- **실행 규율** — 새 폴더(`new_run_dir`) · progress 배타 생성 · 입력 지문 일치 때만 `--resume` · 가드 실패 폴더는 재개 거부
  (`guard_failed.json`) · manifest 두 파일(시작 `run_manifest.json` · 끝 `run_manifest_final.json` — 설계자 승인) · `compare` 는
  재개 없는 두 실행만 결정성 확인으로 인정.
- **실행 비용** — 1회 24~27분 · 최대 RSS 2.6~2.7 GB. 맥은 긴 실행 중 잠든다 → `caffeinate -i` 로 감싼다(§6-4).

---

## 4. 02B — 결과와 종료 조건

```text
판정      REJECT (조건 1~11 중 거짓 1·5·6·7·8·9·10 · 11 결정성 참)
EARLY     사전 포착 28 · 선행 중앙 8.0 · run precision 0.282 · 경보 100건당 오경보 run 23.6
REACTIVE  사전 포착 22 · 선행 중앙 8.0 · run precision 0.446 · 8.1
무작위     run precision 95% 분위 0.326 (EARLY 는 평균 0.296 보다도 낮다)
운영 표 재현  65개 값 EXACT_MATCH (라이브 DB 파일 읽기 전용 세션 사본 · 직접 연결 0)
```

- **Track B 는 이번 REJECT 로 닫혔다.** 이 방식은 운영 후보·추가 모델 입력으로 승격하지 않는다.
- **사건 정의는 폐기**(`RETIRED_AFTER_THIS_STUDY`) — 강한 상승장에서 길게 묶인 사건의 저점이 시작 다음 날로 잡히는 결함이 있다
  (사건 34·35). 사후 민감도로 창 정의 두 가지를 바꿔도 조건 5·6·7 이 거짓이었다(진단 · 판정 미사용).
- Track B 를 다시 하려면 **새 PLAN · 새 사전 등록**이 있는 별도 연구로만 한다(설계자 RESULT 판정 §1).
- 운영 표 재현 방식(라이브 DB 파일 복사 → 전후 sha256 · 사본 integrity · 0444 → 가드 안에서 기존 함수 무수정 호출 → 사본 삭제)은
  옛 운영 숫자를 확인할 때 다시 쓸 수 있다(`app/ml_ew_reproduce.py`).

---

## 5. 실행 산출물 (git 추적 밖 `state/ml/research/` — 결과서 hash 로 대조)

```text
state/ml/research/poc4_02a/run1 · run2          result.json canonical 1e9a88af… · run2/determinism_compare.json
state/ml/research/poc4_02b/run1 · run2          canonical 4de43c0c… · 결과 파일 sha256 67015d25… · run2/determinism_compare.json
state/ml/research/poc4_02b/post_hoc_window_sensitivity/   사후 민감도 스크립트 · 출력 (판정 미사용)
```

---

## 6. 남은 기술부채 · 열린 항목 (모두 비차단)

1. **KS-10 근접** — `scripts/run_poc4_02a_pit_bias.py` 586줄(근접선 600) · `app/ml_pit_bias_report.py` 535줄. 붙이기 **전에** 분리한다.
2. **02A 거래량 0 기록 범위** — 판정 §2 "`zero_volume=true` 기록" 을 점수 쌍 t 행 수로만 남겼다(feature 창 t−20..t−1 은 세지 않음).
3. **02B exact-k 진단 이름** — 코드 이름은 `EXACT_K_DIAGNOSTIC`(필드 `LOOKAHEAD: true` · `judged: false`)이고 판정 토큰
   `LOOKAHEAD_DIAGNOSTIC_ONLY` 는 PLAN·결과서 문구로만 적었다.
4. **POC4-01 에서 넘어온 것** — 기존 테스트 229건 고정 fixture 전환(비차단) 그대로.
5. `ASSUMPTIONS Q6` — 연구 계약은 POC4-02B 용으로 고정됐고 이번 REJECT 로 닫혔다 · 운영 계약(`OPERATIONAL_CONTRACT`)은 OPEN.

---

## 7. 이 챕터에서 배운 것 (반복하지 말 것)

1. **PLAN 의 "구현 정의" 도 결과 전에 틀릴 수 있다** — 02B 사건 T·P 정의 결함은 스모크 뒤 검토에서 드러났다. 공식 판정은 사전
   정의로 내고, 결함은 민감도로 영향을 재서 설계자에게 넘겼다(설계자: 재실행 없이 폐기). 정의를 결과 뒤 몰래 고치지 않는다.
2. **PLAN 운영 정의가 설계자 판정 문구보다 좁으면 판정이 이긴다** — 잘린 사건 제외 창이 그랬다. 실행 전에 PLAN 의 각 정의를 판정
   원문과 한 줄씩 대조한다.
3. **재개 경로가 가드 실패를 세탁할 수 있다** — 가드가 결과를 거부한 폴더를 `--resume` 하면 새 지문으로 통과했다(구현 검토가
   잡음). 첫 시작 지문 보관 · 실패 표식 · 결과는 모든 가드 통과 뒤에만 쓴다.
4. **맥은 긴 실행 중 잠든다** — 02A run2 에 623초 `Maintenance Sleep` 이 끼어 벽시계와 실행 기록이 어긋났다(결과는 같음).
   긴 공식 실행은 `caffeinate -i` · 시간이 이상하면 `pmset -g log | grep Sleep`.
5. **결과서는 검증자에게 넘기기 전에 산출물과 전수 대조한다** — 수치 오류는 없었지만 "모두 tmp DB" · "방향 일관" · "가장
   깊음" 같은 과장 표현이 여럿 나왔다.
6. **다중 에이전트 작업은 세션 한도로 중간에 끊길 수 있다** — 저널(`journal.jsonl`)로 끝난 에이전트 결과를 먼저 거두고 남은
   것만 다시 돌린다.

---

## 8. 다음 사람이 바로 할 일

1. 설계자에게 POC4-02 종료 보고(사용자 경유) → **POC4-03 설계서 수신**.
2. POC4-03 은 **설계서 → 개발 PLAN(모호점 질문) → 설계자 확정 → 구현** 순서. 설계서 V2 Part D 가 이미 정한 것:
   - 비교 대상 셋뿐 — 기존 선형 baseline · 단순 20일 모멘텀 · RandomForest(sklearn · 사전 고정 설정 최대 3개)
   - 자동 튜닝 금지 · XGBoost·LightGBM 미개방 · RF 설정 3개는 같은 분할(`app/ml_research_split.split_fingerprint`)
   - Kill 조건(§17): RF IC ≤ 모멘텀 · 비용 반영 성과 ≤ 모멘텀 · 개선 CI 가 0 을 못 넘음 · PIT 에서만 붕괴 · 특정 기간·단일 설정
     의존 · 결정성 실패 → Track A 종료. 한 지표만 이기면 `INCONCLUSIVE → CLOSED`.
3. **scikit-learn 1.9.0 은 이미 `requirements.txt` 에 있다** — RF 에 신규 의존성 승인은 필요 없다(설계서 §16 범위 안).
4. 봉인 KRX 데이터를 쓰면 §2 reader 를 수정 없이 쓰고, 02A 의 분할·실행 규율(§3)을 재사용할지 PLAN 에서 설계자에게 묻는다.

---

## 9. 문서

```text
설계서 · 설계자 판정   docs/ai_design/POC4/POC4-02_PARALLEL_RESEARCH_TRACKS_DESIGN_V2.md (V2 · # 설계자 PLAN 판정 · # 설계자 RESULT 판정)
PLAN                 docs/ai_plan/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_PLAN_V1.md · POC4-02B_DOWNSIDE_EARLY_WARNING_PLAN_V1.md
결과서                docs/ai_result/POC4/POC4-02A_KRX_PIT_UNIVERSE_BIAS_RESULT.md · POC4-02B_DOWNSIDE_EARLY_WARNING_RESULT.md
Master Plan          docs/ai_plan/POC4/POC4-00_ML_QUANT_ADVANCEMENT_MASTER_PLAN_V1.md §11
기반 문서 정정         docs/PROJECT_ORIGIN_INTENT.md §9.5 (2026-09-25 예외) · docs/ASSUMPTIONS.md Q6
현행 동작             docs/PROGRAM_TRUTH.md §7.1 (KRX 연구 DB consumer)
현재 상태             docs/STATE_LATEST.md
```

## 10. 사용자 확인

- 화면 확인 없음 · OCI 적용 없음(PC 연구 전용).
